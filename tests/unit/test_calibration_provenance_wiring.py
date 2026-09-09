"""Story 5.16: les deux branchements que la moitie couleur avait laisses ouverts.

Deux fils, et chacun n'existait qu'en intention avant cette moitie de story:

* **AC 10** -- la forme de la provenance de correction etait declaree et projetee par
  `color_calibration`, mais **aucun `PageCalibration` ne remontait** jusqu'a
  `io.scan_manifest._build_calibration_results`. L'AC n'etait donc tenue nulle part sur
  un document reellement ecrit;
* **AC 15** -- le drapeau de contournement etait declare et consomme par
  `calibrate_page`, mais **aucun chemin de ligne de commande ne le posait**.

Les deux sont eprouves contre les **vrais producteurs**, jamais contre un
`SimpleNamespace`: un renommage de champ entre `color_calibration` et `io/` ne casserait
sinon que chez le premier consommateur reel, en `AttributeError` brute et tous tests
verts (action item 3 de la retro Epic 4). C'est la raison pour laquelle les fabriques de
pages rectifiees sont **importees** du module de test de la moitie couleur au lieu d'etre
recopiees ici: deux fabriques de synthese divergeraient, et celle de la moitie couleur
est celle dont les mesures sont publiees.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import cli  # noqa: E402
from mixed_media_utility import color_calibration as cc  # noqa: E402
from mixed_media_utility.io import calibration_profile  # noqa: E402
from mixed_media_utility.io import scan_manifest as sm  # noqa: E402

import test_calibration_page_source as couleur  # noqa: E402
import test_scan_calibration_application as app  # noqa: E402
import test_scan_manifest as scan  # noqa: E402
from test_color_calibration import (  # noqa: E402
    _profil_affine_distinguable, _synthetic_rectified_page)


TEMPLATE = couleur.TEMPLATE
PRESET = couleur.PRESET


def _payloads(count: int) -> list[dict]:
    """Un lot de ``count`` pages, par le **vrai** producteur de payload.

    Deux pages au moins partout ou l'appariement compte: une fabrique mono-page rend
    invisible un `find` qui rend toujours la premiere entree.
    """
    return [scan.make_payload(page_index=index, page_count=count)
            for index in range(count)]


def _own_sheet_result() -> cc.PageCalibration:
    """Une page calibree sur **ses propres** pastilles: le regime de repli."""
    page = _synthetic_rectified_page(
        template_id=TEMPLATE, preset_id=PRESET, distort=couleur._NOMINAL_PRESS)
    return cc.calibrate_page(page, template_id=TEMPLATE, patch_preset_id=PRESET,
                             dpi=600, page_id="page-propre")


def _transported_result(*, bypass: bool = False,
                        deviant: bool = False) -> cc.PageCalibration:
    """Une page corrigee **depuis la page de calibration du lot**.

    ``deviant`` choisit la feuille qui depasse le seuil de divergence, et ``bypass`` la
    demande de contournement. Les trois combinaisons utiles sont donc atteignables, et
    c'est ce qui permet d'eprouver la garde de coherence **dans les deux sens**.
    """
    profile = couleur._calibration_profile()
    press = couleur._DEVIANT_PRESS if deviant else couleur._NOMINAL_PRESS
    page = _synthetic_rectified_page(
        template_id=TEMPLATE, preset_id=PRESET, distort=press)
    return cc.calibrate_page(
        page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600,
        page_id="page-deviante" if deviant else "page-calme",
        imported_profile=profile, imported_source_page_id="calibration-0",
        divergence_bypass=bypass)


# ---------------------------------------------------------------------------
# AC 10 -- la provenance remonte jusqu'au document, et elle y distingue
# ---------------------------------------------------------------------------


def test_the_scan_record_carries_page_calibrations_up_to_the_document(tmp_path) -> None:
    """Le fil de l'AC 10, de bout en bout: `calibrate_page` -> `ScanRecord` -> document.

    Deux pages et non une, avec **deux regimes de correction differents**: c'est la
    condition sous laquelle « le champ distingue les deux regimes » veut dire quelque
    chose. Une seule page rendrait l'assertion vraie pour n'importe quelle valeur.
    """
    payloads = _payloads(2)
    pages = [scan.scanned_page(payload) for payload in payloads]
    report = scan.write_report(tmp_path, pages)
    transporte = _transported_result()
    propre = _own_sheet_result()
    record = scan.make_record(
        payloads, report,
        page_calibrations=((0, transporte), (1, propre)),
    )
    merge = sm.build_scan_manifest(None, record)
    entrees = {entry["page_index"]: entry
               for entry in merge.manifest["reconstruction"]["page_calibration_results"]}
    assert set(entrees) == {0, 1}
    # Le champ est present dans les **deux** regimes...
    for entry in entrees.values():
        assert "correction_source" in entry
        assert "correction_form_id" in entry
    # ... et il y porte des valeurs **differentes**. Sans ce volet, un champ present
    # partout avec la meme valeur satisferait la premiere moitie et ne distinguerait
    # rien -- ce qui est le cas que l'AC 10 existe pour interdire.
    assert entrees[0]["correction_source"] == cc.CORRECTION_SOURCE_CALIBRATION_PAGE
    assert entrees[1]["correction_source"] == cc.CORRECTION_SOURCE_OWN_SHEET
    assert entrees[0]["correction_source"] != entrees[1]["correction_source"]
    assert entrees[0]["correction_source_page_id"] == "calibration-0"
    assert entrees[1]["correction_source_page_id"] == "page-propre"


def test_the_projection_is_the_producers_own_and_never_a_second_writing(tmp_path) -> None:
    """La forme projetee **est** celle que `correction_provenance_summary` rend.

    Appelee et non recopiee: la story qui produit la donnee possede sa forme, celle qui
    possede le manifest en possede l'ecriture. Une seconde redaction divergerait a la
    premiere evolution du bloc de divergence, et le symptome serait un manifest qui
    decrit une correction avec les champs d'une autre.
    """
    payloads = _payloads(1)
    report = scan.write_report(tmp_path, [scan.scanned_page(payloads[0])])
    resultat = _transported_result()
    record = scan.make_record(payloads, report,
                              page_calibrations=((0, resultat),))
    entry = sm.build_scan_manifest(None, record).manifest[
        "reconstruction"]["page_calibration_results"][0]
    attendu = cc.correction_provenance_summary(resultat)
    for cle, valeur in attendu.items():
        assert entry[cle] == valeur, cle
    # Et le statut de la page vient du **resultat**, pas du rapport de 5.6: c'est la
    # calibration qui sait si elle a ete appliquee.
    assert entry["status"] == resultat.status


def test_a_page_without_a_calibration_result_keeps_the_reports_status(tmp_path) -> None:
    """Additivite (AC 12): sans resultat, le document est **exactement** l'ancien.

    Le regime nouveau ne s'obtient qu'en le demandant. C'est la forme falsifiable de
    « octet a octet »: les entrees rendent les deux memes cles qu'avant la story tant
    qu'aucune provenance ne remonte.
    """
    payloads = _payloads(2)
    pages = [scan.scanned_page(payload) for payload in payloads]
    report = scan.write_report(tmp_path, pages)
    entrees = sm.build_scan_manifest(
        None, scan.make_record(payloads, report)
    ).manifest["reconstruction"]["page_calibration_results"]
    for entry in entrees:
        assert set(entry) == {"page_index", "status"}
        assert entry["status"] == "not_applied"


def test_a_calibration_result_for_a_page_the_lot_does_not_declare_is_refused(
    tmp_path,
) -> None:
    """Un resultat mal apparie est **refuse**, jamais ignore ni deplace.

    La cible est placee **ailleurs qu'en premiere position** -- deux pages declarees, un
    resultat pour une troisieme -- parce qu'un appariement qui rendrait toujours la
    premiere page ne se demasque pas autrement. C'est la forme que prend ici le risque
    R12, applique a la couleur.
    """
    payloads = _payloads(2)
    pages = [scan.scanned_page(payload) for payload in payloads]
    report = scan.write_report(tmp_path, pages)
    record = scan.make_record(
        payloads, report,
        page_calibrations=((1, _own_sheet_result()), (7, _own_sheet_result())),
    )
    with pytest.raises(sm.ScanPersistenceError) as refus:
        sm.build_scan_manifest(None, record)
    message = str(refus.value)
    assert "[7]" in message, message
    assert "Le manifest precedent est intact" in message


def test_two_results_for_the_same_page_are_refused(tmp_path) -> None:
    """Une page a **une** correction (AC 5 de 5.4b).

    En accepter deux laisserait l'ordre de lecture decider laquelle est inscrite, ce qui
    est la definition d'un document non deterministe.
    """
    payloads = _payloads(1)
    report = scan.write_report(tmp_path, [scan.scanned_page(payloads[0])])
    with pytest.raises(sm.ScanPersistenceError) as refus:
        scan.make_record(payloads, report,
                         page_calibrations=((0, _own_sheet_result()),
                                            (0, _transported_result())))
    assert "meme page_index" in str(refus.value)


#: Les cinq champs du typage structurel, **ecrits a la main** et non derives.
#:
#: Mutant `Q05` de la campagne de la couche 1, et c'est la preuve la plus courte que ce
#: depot ait produite d'un test tautologique: le mutant retire `"divergence"` de
#: `_CALIBRATION_REQUIRED_ATTRIBUTES` -- le champ dont depend tout le bloc de divergence du
#: manifest -- et la suite reste **verte avec un test de moins**, 1690 au lieu de 1691. Le
#: mutant n'a pas fait echouer un test: il en a **supprime** un, parce que les deux tests
#: qui gardent l'enumeration tiraient leurs cas de l'enumeration elle-meme. Retirer le test
#: et le satisfaire produisaient le meme resultat, ce qui est la definition exacte d'une
#: tautologie.
#:
#: Consequence de methode, a garder au-dela de cette story: **un mutant qui fait baisser le
#: nombre de tests passants est un detecteur de tautologie.** Comparer les comptes, et pas
#: seulement le verdict vert / rouge, attrape les tests auto-referentiels que rien d'autre
#: ne voit.
#:
#: Le mutant `Q04` (vider la boucle) **meurt**, lui, et sa mort delimite ce que la garde
#: couvre reellement: ce que les tests ne pouvaient pas voir n'etait pas l'absence de garde,
#: c'etait un **retrecissement de l'enumeration** -- la direction qu'un renommage ou un
#: allegement de champ emprunte.
#: `not_applied_reason` ajoute a la deuxieme passe de revue d'`EPIC5-ARB-78`
#: (2026-08-14): meme trou que celui ferme pour `acceptance` ci-dessus au meme commit
#: -- `correction_provenance_summary` le lit a chaque projection
#: (`io/scan_manifest.py:1113-1125`), et il manquait a l'enumeration.
#:
#: **Trois champs ajoutes le 2026-08-17** (revue de 5.22, bloquant trouve independamment
#: par les trois couches, et **quatrieme et cinquieme occurrences** du meme defaut pour
#: deux d'entre eux): `correction_chain_id` -- lu par la projection depuis 5.22 --,
#: `failure_reason` -- lu depuis 5.19, et jamais remarque par aucune des trois passes de
#: revue intermediaires -- et `chain_profile_acceptance`, ajoute par le correctif du
#: bloquant `C2`. Ce que ce litteral seul ne pouvait pas voir est explique sous le test
#: derive ci-dessous: recopier une enumeration a la main est exactement le geste qui a
#: rate trois fois.
_CHAMPS_ATTENDUS_DU_TYPAGE = (
    "status",
    "correction_source",
    "correction_source_page_id",
    "correction_form_id",
    "divergence",
    "acceptance",
    "not_applied_reason",
    "correction_chain_id",
    "failure_reason",
    "chain_profile_acceptance",
    # **Sixieme champ ajoute a l'enumeration, story 5.23**: `raw_divergence`, l'ecart brut
    # a brut d'`EPIC5-ARB-82`, lu en acces nu par la projection au meme titre que
    # `divergence`. Inscrit **dans la story qui l'ajoute** et non a la revue suivante --
    # c'est la seule discipline connue qui evite la sixieme occurrence du defaut que les
    # cinq paragraphes ci-dessus racontent.
    "raw_divergence",
)

#: Les cles publiees dont le nom **ne coincide pas** avec l'attribut lu pour les produire.
#:
#: Jusqu'a `EPIC5-ARB-78` la table etait vide et l'egalite des noms tenait par
#: coincidence -- la projection ne publiait que des champs qu'elle recopiait tels quels.
#: Le bloc `distortion` est le premier a etre **derive** (il vient de `acceptance`), et
#: ecrire la correspondance est ce qui garde le second volet du test ci-dessous
#: falsifiable: sans elle, il faudrait soit interdire toute cle derivee, soit renoncer a
#: verifier que la projection ne lit rien hors de l'enumeration.
_CLE_PUBLIEE_VERS_ATTRIBUT_LU = {"distortion": "acceptance"}


def test_the_declared_structural_fields_are_pinned_against_a_written_list() -> None:
    """L'enumeration est confrontee a un **litteral**, jamais a elle-meme.

    C'est le geste qui ferme le mutant `Q05`: un champ retire de
    `_CALIBRATION_REQUIRED_ATTRIBUTES` fait echouer **ce** test au lieu de retirer
    silencieusement un cas parametre. L'egalite porte sur l'ordre aussi, parce que
    l'enumeration est un tuple et qu'un test d'ensembles laisserait passer une permutation
    -- la famille d'erreurs qui a coute cinq regressions a ce depot.

    Le second volet est aussi important que le premier: chaque champ enumere doit etre
    **consomme** par la projection du manifest ou par la garde de contournement. Une
    enumeration qui grandirait sans que rien ne lise le champ ajoute serait un refus sans
    domaine d'activation, ce que ce depot compte comme une non-garantie.

    **Amendement du 2026-08-17, et il deplace une propriete au lieu de l'affaiblir.** Les
    deux volets « lu / enumere » de ce test tiraient leur mesure des cles **publiees** par
    un fixture (`_own_sheet_result()`), avec une liste d'exceptions pour les cles que ce
    fixture ne publie pas. Cette redaction ne pouvait pas voir les champs a publication
    **conditionnelle** -- elle avait deja une exception ecrite pour `divergence`, puis une
    seconde pour `not_applied_reason` --, et c'est precisement par la que
    `correction_chain_id` et `failure_reason` sont passes. Une liste d'exceptions qui
    grandit a chaque champ conditionnel est le symptome, pas la solution: la mesure porte
    desormais sur ce que la projection **lit** (derivation par AST, test suivant), et non
    sur ce qu'un fixture lui fait publier. Ce qui reste ici est ce que l'AST ne dit pas:
    que le bloc derive est reellement produit **par un vrai producteur**.
    """
    assert sm._CALIBRATION_REQUIRED_ATTRIBUTES == _CHAMPS_ATTENDUS_DU_TYPAGE

    # Le volet que seul un vrai producteur peut rendre: la cle derivee est effectivement
    # publiee sur un resultat sorti de `calibrate_page`, et l'attribut dont elle vient est
    # enumere. Sans lui, la table de correspondance deviendrait une porte de sortie -- y
    # ajouter une ligne suffirait a excuser un champ que personne ne lit.
    reel = _own_sheet_result()
    publies = set(cc.correction_provenance_summary(reel))
    for cle, attribut in _CLE_PUBLIEE_VERS_ATTRIBUT_LU.items():
        assert cle in publies, cle
        assert attribut in _CHAMPS_ATTENDUS_DU_TYPAGE, attribut


#: Les attributs lus **ailleurs** que dans `correction_provenance_summary`, avec leur site.
#:
#: La derivation par AST ci-dessous ne couvre qu'un lecteur -- la projection --, et deux
#: champs de l'enumeration sont lus par d'autres. Les nommer ici plutot que de les excuser
#: en bloc est ce qui garde le volet « aucun champ decoratif » falsifiable: un champ dont
#: le site nomme cesserait de le lire ferait echouer le test, pas un `pass`.
_AUTRES_LECTEURS = {
    # `_build_calibration_results` pose le statut de la page a part de la provenance.
    "status": "io.scan_manifest._build_calibration_results",
    # `_check_bypass_was_requested`, ou vit la trace du contournement (AC 15 de 5.16).
    "divergence": "io.scan_manifest._check_bypass_was_requested",
}


def _attributs_lus_par(fonction, parametre: str) -> set[str]:
    """Les attributs de `parametre` que `fonction` lit, **derives de son AST**.

    C'est le geste que la revue de 5.22 demandait: rendre l'enumeration derivee de ce que
    la projection lit reellement, plutot que recopiee a la main. La lecture est **statique**
    et c'est tout son interet -- elle ne depend d'aucun fixture, donc elle voit les acces
    places sous condition (`if result.<champ> is not None`), qui sont exactement ceux que
    trois passes de revue successives ont laisses passer.

    Ce que la methode ne couvre pas, et il faut le dire: un acces indirect
    (`getattr(result, nom)` avec `nom` calcule) resterait invisible. La projection n'en
    fait aucun -- elle lit ses champs en clair --, et un tel acces devrait de toute facon
    etre refuse en revue: un champ dont le nom se calcule ne peut etre enumere par
    personne, donc le typage structurel de `io/` cesserait d'etre verifiable.
    """
    import ast
    import inspect
    import textwrap

    arbre = ast.parse(textwrap.dedent(inspect.getsource(fonction)))
    return {
        noeud.attr
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Attribute)
        and isinstance(noeud.value, ast.Name)
        and noeud.value.id == parametre
    }


def test_lenumeration_couvre_tout_attribut_que_la_projection_lit() -> None:
    """L'enumeration est **derivee** de ce que la projection lit, jamais recopiee.

    Le defaut que ce test ferme a ete referme **trois fois au meme endroit** -- `acceptance`
    le 2026-08-13, `not_applied_reason` le 2026-08-14, `correction_chain_id` le 2026-08-17
    --, chaque fois par une ligne ajoutee a la main a `_CALIBRATION_REQUIRED_ATTRIBUTES`,
    chaque fois avec un commentaire disant que c'etait la regle. La troisieme passe a en
    plus revele que `failure_reason` manquait **depuis 5.19** sans que personne ne le voie.
    Un defaut ferme trois fois au meme endroit est un defaut de conception du garde-fou.

    Ce que le garde-fou precedent ne pouvait pas voir: il mesurait les cles **publiees**
    par un fixture, et ces quatre champs sont publies **sous condition**. Le fixture ne les
    portant pas, il ne les publiait pas, et le test etait vert pour la raison meme qui
    rendait le defaut possible.

    La derivation, elle, est statique: elle lit l'AST de `correction_provenance_summary` et
    recense tout `result.<champ>`, condition ou pas. Le jour ou la projection lira un champ
    de plus, **ce** test echouera avant qu'aucun `AttributeError` n'atteigne le fond d'une
    projection -- et il echouera sans qu'aucun fixture n'ait besoin de porter le champ.

    Le sens inverse est tenu aussi: aucun champ de l'enumeration n'est decoratif. Il est lu
    par la projection ou par l'un des deux sites nommes dans `_AUTRES_LECTEURS`. Une
    enumeration qui grandirait sans lecteur serait un refus sans domaine d'activation.
    """
    lus_par_la_projection = _attributs_lus_par(
        cc.correction_provenance_summary, "result")
    # Confronte a l'enumeration **du module**, celle qui garde reellement la frontiere, et
    # non au litteral de ce fichier: un champ retire la-bas doit faire echouer ici aussi.
    # Le litteral garde son role -- fermer le mutant `Q05` -- dans le test ci-dessus.
    enumeres = set(sm._CALIBRATION_REQUIRED_ATTRIBUTES)

    # Le volet qui ferme le defaut: tout ce que la projection lit est exige par la garde,
    # donc un resultat qui ne le porte pas sort en `ScanPersistenceError` nomme et jamais
    # en `AttributeError` nue au fond de la projection.
    manquants = lus_par_la_projection - enumeres
    assert not manquants, (
        f"lus par correction_provenance_summary et absents de "
        f"_CALIBRATION_REQUIRED_ATTRIBUTES: {sorted(manquants)}")

    # Et le volet symetrique, sans lequel le premier se satisferait d'une enumeration
    # gonflee de champs que personne ne lit.
    sans_lecteur = enumeres - lus_par_la_projection - set(_AUTRES_LECTEURS)
    assert not sans_lecteur, (
        f"enumeres et lus par personne: {sorted(sans_lecteur)}")

    # `_AUTRES_LECTEURS` ne doit pas devenir la porte de sortie que la liste d'exceptions
    # precedente etait: chacune de ses entrees nomme un champ **enumere** et un site qui le
    # lit **reellement**, verifie sur le source de ce site et non sur sa promesse. Sans ce
    # volet, y ajouter une ligne suffirait a excuser n'importe quel champ mort.
    import inspect

    for champ, site in _AUTRES_LECTEURS.items():
        assert champ in enumeres, champ
        fonction = getattr(sm, site.rsplit(".", 1)[1])
        assert champ in inspect.getsource(fonction), (
            f"{site} ne lit pas {champ}: l'entree de _AUTRES_LECTEURS est perimee")


def test_la_derivation_par_ast_voit_un_acces_conditionnel() -> None:
    """Le domaine d'activation de la garde ci-dessus, construit et mesure.

    « Une garde annoncee sans son domaine d'activation n'est pas une garantie »: le test
    precedent est vert sur le code livre, donc il faut montrer qu'il **mord**. Le regime
    exact ou il devait mordre et ne mordait pas est celui d'un acces place sous condition
    -- la forme que prennent les quatre champs qui sont passes entre les mailles.
    """
    def projection_temoin(result):
        entree = {"correction_source": result.correction_source}
        if result.champ_conditionnel is not None:
            # Exactement la forme de `if result.correction_chain_id is not None`: aucun
            # fixture ne publie cette cle tant qu'il ne porte pas le champ, et c'est la
            # que l'ancien garde-fou etait aveugle.
            entree["conditionnel"] = result.champ_conditionnel
        return entree

    lus = _attributs_lus_par(projection_temoin, "result")
    assert lus == {"correction_source", "champ_conditionnel"}
    # Et le temoin negatif: un attribut lu sur **un autre** objet n'entre pas dans le
    # compte. Sans ce volet, la derivation gonflerait l'enumeration de champs qui ne sont
    # pas ceux du resultat de calibration -- `acceptance.detail`, par exemple, que la vraie
    # projection lit sur le verdict et non sur le resultat.
    def projection_indirecte(result):
        return {"detail": result.acceptance.detail}

    assert _attributs_lus_par(projection_indirecte, "result") == {"acceptance"}


@pytest.mark.parametrize("champ", _CHAMPS_ATTENDUS_DU_TYPAGE)
def test_a_result_missing_a_declared_field_is_refused_at_the_boundary(
    champ, tmp_path,
) -> None:
    """Le typage structurel est **verifie**, champ par champ, et il l'est ici.

    `io/` ne peut pas dependre de `color_calibration` a l'import -- la couche de
    persistance tirerait numpy et OpenCV --, donc la forme consommee est enumeree. Le
    prix de ce choix est qu'un renommage passerait inapercu; l'enumeration transforme ce
    prix en refus explicite, et ce test parametre verifie qu'aucun des champs enumeres
    n'est decoratif.

    **Le parametrage tire ses cas d'un litteral ecrit** et non de l'enumeration qu'il
    garde (mutant `Q05`): sinon, retirer une entree de l'enumeration retire le cas de test
    qui la couvrait, et le refus disparait avec son propre gardien.
    """
    reel = _own_sheet_result()

    class Ampute:
        def __init__(self) -> None:
            for nom in _CHAMPS_ATTENDUS_DU_TYPAGE:
                if nom != champ:
                    setattr(self, nom, getattr(reel, nom))

    payloads = _payloads(1)
    report = scan.write_report(tmp_path, [scan.scanned_page(payloads[0])])
    with pytest.raises(sm.ScanPersistenceError) as refus:
        scan.make_record(payloads, report, page_calibrations=((0, Ampute()),))
    assert champ in str(refus.value)


def test_the_real_producer_carries_every_field_this_module_consumes() -> None:
    """Le temoin positif du test ci-dessus: le **vrai** producteur les porte tous.

    Sans lui, l'enumeration pourrait nommer un champ que `PageCalibration` n'a jamais
    eu, et tous les refus ci-dessus seraient vrais pour la mauvaise raison.

    La liste est celle du litteral, pour la meme raison que ci-dessus: derivee de
    l'enumeration, elle aurait rendu ce temoin vide en meme temps que le refus.
    """
    reel = _own_sheet_result()
    for champ in _CHAMPS_ATTENDUS_DU_TYPAGE:
        assert hasattr(reel, champ), champ


# ---------------------------------------------------------------------------
# Famille `Q` de la campagne de la couche 1: le bloc entier des gardes de
# forme et de type de `page_calibrations` n'etait exerce par aucun test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entree", [
    "pas-un-couple",                       # une chaine se deballe, et en trois morceaux
    42,                                    # ni tuple ni sequence
    None,
    (0,),                                  # un tuple, mais de cardinal 1
    (0, "resultat", "de trop"),            # cardinal 3
    [0, "resultat"],                       # une **liste**, pas un tuple
], ids=["chaine", "entier", "none", "cardinal-1", "cardinal-3", "liste"])
def test_a_calibration_entry_that_is_not_a_pair_is_refused(entree, tmp_path) -> None:
    """**Mutant `Q01`**: la forme du couple n'etait verifiee par aucun test.

    Les dix appels a `page_calibrations=` de la suite passaient tous un couple bien forme
    `(int, resultat)`, donc le refus « chaque resultat de calibration est un couple
    (page_index, resultat) » n'etait jamais exerce -- et le mutant qui le remplace par
    `if False:` restait vert. Sans lui, une entree malformee sortirait en `ValueError` de
    deballage: exactement le « decouvert plus loin en erreur sans rapport » que le
    commentaire du bloc dit vouloir eviter.

    Les six formes couvrent les trois facons de rater un couple: le type, le cardinal
    au-dessous et au-dessus, et le **tuple contre la liste** -- une liste de deux elements
    se deballe parfaitement, donc c'est le cas qu'une garde ecrite avec `len(...) == 2`
    seule laisserait passer.
    """
    payloads = _payloads(2)
    report = scan.write_report(
        tmp_path, [scan.scanned_page(payload) for payload in payloads])
    with pytest.raises(sm.ScanPersistenceError) as refus:
        scan.make_record(payloads, report, page_calibrations=(entree,))
    message = str(refus.value)
    assert "couple" in message, message
    assert "page_index" in message


@pytest.mark.parametrize("page_index", [True, False], ids=["vrai", "faux"])
def test_a_boolean_page_index_is_refused_instead_of_being_paired_with_a_page(
    page_index, tmp_path,
) -> None:
    """**Mutant `Q02`**: un `page_index` booleen traversait la garde.

    `True` est un `int` en Python et vaut 1: un `page_calibrations=((True, resultat),)`
    serait donc apparie **a la page 1**, et `False` a la page 0. Le refus existe et nomme
    la faute -- « un entier base zero est attendu, et **jamais un booleen** » -- mais rien
    ne l'eprouvait, alors que `numeric_guards.is_strict_int` a ete ecrit dans ce depot
    precisement pour ce piege.

    C'est la meme famille d'appariement silencieux que le mutant `P02`, par un autre
    chemin: la ou `P02` se trompe de cle, `Q02` en **fabrique** une. Les deux booleens sont
    exerces parce que chacun designe une page reelle du lot de deux pages construit ici --
    un refus qui ne regarderait que `True` laisserait passer `False`.
    """
    payloads = _payloads(2)
    report = scan.write_report(
        tmp_path, [scan.scanned_page(payload) for payload in payloads])
    with pytest.raises(sm.ScanPersistenceError) as refus:
        scan.make_record(payloads, report,
                         page_calibrations=((page_index, _own_sheet_result()),))
    message = str(refus.value)
    assert "booleen" in message, message
    assert repr(page_index) in message, message
    # Temoin positif: l'entier que le booleen imite, lui, passe. Sans lui, un refus qui
    # refuserait **tout** page_index passerait ce test.
    scan.make_record(payloads, report,
                     page_calibrations=((int(page_index), _own_sheet_result()),))


@pytest.mark.parametrize("page_index", [-1, -7])
def test_a_negative_page_index_is_refused_at_the_boundary(page_index, tmp_path) -> None:
    """**Mutant `Q03`**: le volet `>= 0` de la garde n'etait exerce nulle part.

    C'est lui qui empeche un resultat de calibration d'etre indexe hors de l'espace d'index
    du lot. Le refus survivrait en aval -- `_build_calibration_results` verifie que l'index
    appartient bien aux pages declarees -- mais avec **un autre message** que celui que ce
    bloc annonce, et c'est precisement la raison d'etre d'un refus a la frontiere: il dit
    quelle donnee est fautive, la ou le refus d'aval dit qu'un appariement a echoue.
    """
    payloads = _payloads(2)
    report = scan.write_report(
        tmp_path, [scan.scanned_page(payload) for payload in payloads])
    with pytest.raises(sm.ScanPersistenceError) as refus:
        scan.make_record(payloads, report,
                         page_calibrations=((page_index, _own_sheet_result()),))
    message = str(refus.value)
    assert "page_index de calibration invalide" in message, message
    assert str(page_index) in message
    # Et le refus vient bien de **cette** frontiere et non de l'appariement d'aval: le
    # message de l'aval parle de pages absentes du lot, celui-ci de la valeur recue.
    assert "absentes du lot" not in message


# ---------------------------------------------------------------------------
# AC 15 -- le contournement est explicite, et le document le prouve
# ---------------------------------------------------------------------------


def test_a_bypass_constated_without_an_explicit_request_is_refused(tmp_path) -> None:
    """**« Explicite, jamais un repli automatique » devient verifiable.**

    Le symetrique de la regle de la moitie couleur (« le drapeau se declare sur le
    constat et non sur la demande »): le manifest decrit ce qui s'est passe, donc un
    contournement **constate** ne peut pas y etre inscrit si personne ne l'a demande.
    Sans cette garde, un repli automatique produirait exactement le meme document qu'une
    demande explicite -- et l'AC 15 resterait une phrase.
    """
    payloads = _payloads(1)
    report = scan.write_report(tmp_path, [scan.scanned_page(payloads[0])])
    contourne = _transported_result(deviant=True, bypass=True)
    assert contourne.divergence.bypassed is True
    record = scan.make_record(payloads, report,
                              page_calibrations=((0, contourne),),
                              divergence_bypass_requested=False)
    with pytest.raises(sm.ScanPersistenceError) as refus:
        sm.build_scan_manifest(None, record)
    message = str(refus.value)
    # Le refus nomme **la page**, jamais le lot: une feuille se rescanne seule.
    assert "page 0" in message, message
    assert cc.DIVERGENCE_BYPASS_FLAG in message, message
    assert "Le manifest precedent est intact" in message


def test_the_same_bypass_with_the_flag_reaches_the_document_with_its_gap(
    tmp_path,
) -> None:
    """Et avec le drapeau, il passe -- **avec l'ecart qui l'a motive**.

    Sans la trace, une page corrigee apres contournement et une page corrigee
    normalement seraient indistinguables a posteriori, ce qui est precisement le defaut
    que la garde existe pour eviter.
    """
    payloads = _payloads(1)
    report = scan.write_report(tmp_path, [scan.scanned_page(payloads[0])])
    contourne = _transported_result(deviant=True, bypass=True)
    record = scan.make_record(payloads, report,
                              page_calibrations=((0, contourne),),
                              divergence_bypass_requested=True)
    entry = sm.build_scan_manifest(None, record).manifest[
        "reconstruction"]["page_calibration_results"][0]
    divergence = entry["divergence"]
    assert divergence["bypassed"] is True
    assert divergence["excess_residual_de76"] == pytest.approx(
        contourne.divergence.excess_residual_de76)
    assert divergence["threshold_de76"] == contourne.divergence.threshold_de76
    assert divergence["guard_id"] == contourne.divergence.divergence_id


def test_asking_for_the_bypass_on_a_page_that_does_not_diverge_marks_nothing(
    tmp_path,
) -> None:
    """La demande seule n'inscrit rien: le manifest decrit **ce qui s'est passe**.

    C'est la regle tranchee par la moitie couleur, verifiee ici sur un document ecrit:
    une page qui ne diverge pas et qu'on demande de contourner n'est pas marquee
    contournee. La garde de coherence ne mord donc que dans un sens, et c'est le bon.
    """
    payloads = _payloads(1)
    report = scan.write_report(tmp_path, [scan.scanned_page(payloads[0])])
    calme = _transported_result(deviant=False, bypass=True)
    assert calme.divergence.bypassed is False
    entry = sm.build_scan_manifest(
        None,
        scan.make_record(payloads, report, page_calibrations=((0, calme),),
                         divergence_bypass_requested=True),
    ).manifest["reconstruction"]["page_calibration_results"][0]
    assert entry["divergence"]["bypassed"] is False


def test_the_request_flag_is_a_boolean_and_never_a_value_to_guess(tmp_path) -> None:
    payloads = _payloads(1)
    report = scan.write_report(tmp_path, [scan.scanned_page(payloads[0])])
    with pytest.raises(sm.ScanPersistenceError) as refus:
        sm.ScanRecord(page_payloads=tuple(payloads), output_report=report,
                      scan_dpi=600, ingest_slug="lot-a",
                      divergence_bypass_requested="oui")
    assert "booleen" in str(refus.value)


# ---------------------------------------------------------------------------
# AC 15 -- le drapeau existe en ligne de commande, et il est nomme
# ---------------------------------------------------------------------------


def _parse_scan(argv: list[str], monkeypatch) -> object:
    """Faire traverser le **vrai** chemin de ligne de commande et capturer ses `args`.

    `cli.main` construit son parseur lui-meme; on ne l'extrait pas pour les besoins d'un
    test -- ce serait deplacer de la production pour la commodite d'un banc. On capture
    donc a la sortie du parseur, en substituant le seul handler concerne: ce qui est
    verifie est bien ce que `scan_command` recevra, pas ce qu'un parseur reconstruit
    aurait rendu.
    """
    from mixed_media_utility import cli

    vus: list[object] = []

    def capture(args):
        vus.append(args)
        return 0

    monkeypatch.setattr(cli, "scan_command", capture)
    assert cli.main(argv) == 0
    assert len(vus) == 1
    return vus[0]


def test_the_scan_subcommand_carries_the_bypass_flag_under_its_declared_name(
    monkeypatch,
) -> None:
    """Le drapeau vient du module qui **possede** le contournement.

    Un second nom ecrit dans `cli.py` divergerait du message de refus qui l'annonce a
    l'operateur, et le refus deviendrait une impasse: il nommerait une option qui
    n'existe pas. Le test le verifie en **passant le nom declare**, jamais un litteral
    recopie -- si les deux divergeaient, le parseur refuserait l'argument ici.
    """
    base = ["scan", "--project", "p", "--scan", "s", "--dpi", "600"]
    args = _parse_scan([*base, cc.DIVERGENCE_BYPASS_FLAG], monkeypatch)
    assert args.divergence_bypass is True
    # Et il n'est **jamais** actif tout seul: c'est la moitie de l'AC 15 qu'un drapeau
    # `store_true` garantit, et qu'un defaut a `True` aurait perdue en silence.
    nu = _parse_scan(base, monkeypatch)
    assert nu.divergence_bypass is False


def test_the_bypass_flag_reaches_the_record_the_writing_layer_confronts(
    monkeypatch, tmp_path,
) -> None:
    """Le fil complet de l'AC 15: `cli` -> `ScanRecord` -> garde de coherence.

    Le drapeau n'a de valeur que s'il arrive jusqu'a la couche qui ecrit: c'est la, et
    nulle part ailleurs, qu'un contournement constate est confronte a une demande
    explicite. Un drapeau parse et jamais transporte serait un drapeau mort, ce qui est
    pire qu'aucun -- il aurait l'air d'un mecanisme.
    """
    payloads = _payloads(1)
    report = scan.write_report(tmp_path, [scan.scanned_page(payloads[0])])
    contourne = _transported_result(deviant=True, bypass=True)
    # Le champ existe sur `ScanRecord`, il est booleen, et c'est lui que la garde lit.
    for demande, attendu in ((True, True), (False, False)):
        record = scan.make_record(payloads, report,
                                  page_calibrations=((0, contourne),),
                                  divergence_bypass_requested=demande)
        assert record.divergence_bypass_requested is attendu
        if demande:
            sm.build_scan_manifest(None, record)
        else:
            with pytest.raises(sm.ScanPersistenceError):
                sm.build_scan_manifest(None, record)


@pytest.mark.parametrize("mot", ["seuil", "tolerance", "threshold"])
def test_the_flag_and_its_help_contain_no_setting_word(mot) -> None:
    """Frontiere negative de l'AC 16, etendue a l'aide de la ligne de commande.

    L'operateur recoit de quoi juger, pas un seuil a arbitrer. Une option qui
    s'appellerait `--seuil-de-divergence`, ou dont l'aide invite a en regler un,
    reintroduirait exactement l'invitation que cette AC interdit -- et l'aide est ce que
    l'operateur lit en premier.
    """
    import io as _io
    import contextlib

    from mixed_media_utility import cli

    assert mot not in cc.DIVERGENCE_BYPASS_FLAG.lower()
    sortie = _io.StringIO()
    with contextlib.redirect_stdout(sortie), pytest.raises(SystemExit):
        cli.main(["scan", "--help"])
    aide = sortie.getvalue()
    # Le balayage doit avoir vu le drapeau: sans ce temoin, l'absence du mot de reglage
    # serait vraie par vacuite si l'aide n'etait pas celle de la bonne sous-commande.
    assert cc.DIVERGENCE_BYPASS_FLAG in aide
    assert mot not in aide.lower()


# ---------------------------------------------------------------------------
# Mutants `Q08` / `Q09`, mesures pour la premiere fois a la passe de correction:
# la garde de collision de champs avait un domaine d'activation VIDE
# ---------------------------------------------------------------------------


def _provenance_forcee(monkeypatch, forme: dict) -> None:
    """Substituer la provenance publiee par le producteur, et **elle seule**.

    Le point de substitution est `color_calibration.correction_provenance_summary`, que
    `io.scan_manifest._calibration_entry` importe **a l'appel** et non a l'import du
    module -- c'est ce qui rend la substitution possible sans toucher a `io/`.

    Pourquoi une substitution ici, alors que ce fichier eprouve partout les **vrais**
    producteurs: parce que le domaine de cette garde est, avec le producteur reel,
    **vide par construction**. Le resume de provenance publie trois champs
    (`correction_source`, `correction_source_page_id`, `correction_form_id`) plus le bloc
    `divergence`, et **jamais** `page_index` ni `status`. Aucune page, aucun preset, aucun
    regime de correction ne peut donc faire mordre la garde. Une garde forward-looking dont
    le domaine est vide ne s'eprouve pas avec le producteur du jour: la substitution est le
    seul moyen de la mesurer, et le refus d'en poser une l'aurait laissee non garantie.
    """
    from mixed_media_utility import color_calibration as module

    monkeypatch.setattr(module, "correction_provenance_summary", lambda result: dict(forme))


def test_a_provenance_that_would_redefine_page_index_is_refused(monkeypatch, tmp_path) -> None:
    """**Mutant `Q08`**: la garde de collision de champs n'etait exercee par aucun test.

    Le schema de 5.7 ouvre `additionalProperties` sur les entrees de
    `page_calibration_results`, ce qui autorise l'**ajout** de champs et non
    l'**ecrasement**. La garde existe pour cette raison, et elle est forward-looking: elle
    protege du jour ou la provenance gagnerait un champ dont le nom collide avec un champ
    deja declare par l'entree.

    Mesure de la passe de correction, et c'est ce qui a rendu ce test necessaire: avec le
    producteur reel le domaine de la garde est **vide**, donc les deux mutants qui la
    detruisent (`Q08`, qui la retire; `Q09`, qui exclut le mauvais champ) survivaient tous
    les deux -- ils etaient **semantiquement equivalents** a l'original. C'est le motif
    `F7` du depot, une garde dont le domaine d'activation est peut-etre vide, et il faut
    ici le lever explicitement plutot que conclure que la garde est superflue: le jour ou
    un champ de provenance s'appellera `page_index`, c'est cette garde qui dira pourquoi le
    document est refuse au lieu de le laisser s'ecrire faux.
    """
    payloads = _payloads(2)
    report = scan.write_report(
        tmp_path, [scan.scanned_page(payload) for payload in payloads])
    record = scan.make_record(payloads, report,
                              page_calibrations=((1, _own_sheet_result()),))
    # La cible est en seconde position du lot, jamais la premiere (regle des fabriques).
    _provenance_forcee(monkeypatch, {"page_index": 99, "correction_source": "peu importe"})
    with pytest.raises(sm.ScanPersistenceError) as refus:
        sm.build_scan_manifest(None, record)
    message = str(refus.value)
    assert "redefinirait" in message, message
    assert "page_index" in message, message
    # Le refus nomme **la page**, et le document precedent est intact: une collision de
    # champs est une erreur d'ecriture, pas une raison de perdre le manifest.
    assert "page 1" in message, message
    assert "Le manifest precedent est intact" in message, message


def test_a_provenance_that_shares_only_status_is_accepted(monkeypatch, tmp_path) -> None:
    """**Mutant `Q09`**: le champ **exclu** de la garde est `status`, et c'est deliberé.

    Le temoin symetrique du test ci-dessus, et celui qui distingue les deux mutants. Le
    `status` de l'entree vient **deja** du resultat de calibration (`entry["status"] =
    calibration.status`, juste au-dessus de la garde): une provenance qui le porterait
    ecrirait la meme valeur, donc ce n'est pas une redefinition et la garde doit le
    laisser passer. `page_index`, lui, n'a aucune raison d'etre republie par une
    provenance.

    Sans ce volet, `Q09` -- qui exclut `page_index` au lieu de `status` -- resterait
    vivant: il refuserait une provenance qui partage `status` et accepterait celle qui
    redefinit `page_index`, soit l'exact inverse du contrat, **et les deux tests le
    verraient si et seulement si les deux existent**. C'est la meme lecon que la regle des
    fabriques: une garde ne se mesure que par les deux cotes de sa frontiere.
    """
    payloads = _payloads(2)
    report = scan.write_report(
        tmp_path, [scan.scanned_page(payload) for payload in payloads])
    resultat = _own_sheet_result()
    record = scan.make_record(payloads, report,
                              page_calibrations=((1, resultat),))
    _provenance_forcee(monkeypatch, {"status": resultat.status,
                                     "correction_source": "peu importe"})
    entrees = {entry["page_index"]: entry
               for entry in sm.build_scan_manifest(None, record).manifest[
                   "reconstruction"]["page_calibration_results"]}
    # Accepte, et la valeur partagee est bien celle du resultat -- pas celle du rapport.
    assert entrees[1]["status"] == resultat.status
    assert entrees[1]["correction_source"] == "peu importe"


# ---------------------------------------------------------------------------
# Revue de 5.22, bloquant `C3` -- la feuille de calibration restee dans la pile
# ---------------------------------------------------------------------------


def _profil_de_chaine(chain_id: str, *, page_id: str) -> dict:
    """Le document de profil que `scan calibrate` consigne, par son **vrai** projecteur.

    Le verdict d'acceptation y est peuple: c'est la moitie de la mesure que le bloquant
    `C2` avait laissee sans lecteur, et sans elle le scenario ci-dessous ne pourrait pas
    verifier qu'elle atteint le manifest.
    """
    from test_color_calibration import (_profil_affine_distinguable,
                                        _verdict_mesurable)

    return cc.profile_to_document(
        _profil_affine_distinguable(), chain_id=chain_id, source_page_id=page_id,
        template_id=scan.TPL_V2, read_patch_count=14, retained_patch_count=13,
        ink_floor_excluded=False, acceptance=_verdict_mesurable())


def test_la_feuille_du_vrac_declare_sa_chaine_au_rapport_et_au_profil_cree(
    tmp_path,
) -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 7 et AC 10) -- **`M25` transpose**.

    C'est le deuxieme des trois de `deferred-work.md`, et il etait **sans
    substitut actif**: « la seule entree fausse etait celle que personne ne
    regardait ». L'assertion morte etait « l'entree d'index 0 DU LOT declare la
    chaine »: une page de calibration n'appartient plus a aucun lot
    (`EPIC5-ARB-82`), donc cette entree n'existe plus.

    Ce qui survit est la propriete de fond -- **la feuille routee declare sa
    chaine au document, et le profil cree pour elle porte la meme** --, et elle
    vit desormais dans le rapport de tri.

    **Deux feuilles de calibration**, aux libelles differents et separees par une
    planche: l'appariement feuille -> profil se fait par **localisateur**, jamais
    par rang. Une projection qui poserait la meme chaine partout, ou qui
    apparierait la premiere feuille au premier profil quel que soit l'ordre,
    tomberait ici -- et c'est litteralement la classe du mutant `M25`.
    """
    libelles = ("hp envy 4520 tiff 300 dpi", "epson v600 tiff 300 dpi")
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    feuilles = [app.page_de_calibration_autonome(scan_chain_label=libelle)
                for libelle in libelles]
    folder = app.write_scan_folder(tmp_path / "vrac", [
        (payloads[0], app.PRESSES_DU_TIRAGE[0]),
        (feuilles[0], app.PRESSE_CALIBRATION),
        (payloads[1], app.PRESSES_DU_TIRAGE[1]),
        (feuilles[1], app.PRESSE_CALIBRATION)])
    project_dir = tmp_path / "projet-vrac"

    assert app.run_scan(project_dir, folder) == 0

    rapport = json.loads(
        (project_dir / "scans" / "vrac" / cli.TRI_DOCUMENT_FILENAME).read_text(
            encoding="utf-8"))
    # Chaque feuille routee **declare sa chaine**, et les deux sont distinctes.
    declarees = {entree["locator"]["source_path"]: entree["scan_chain_label"]
                 for entree in rapport["calibration"]}
    assert len(set(declarees.values())) == 2, declarees
    # Et le profil cree pour chacune porte **la meme** chaine, apparie par
    # localisateur.
    crees = {profil["locator"]["source_path"]: profil["etiquette"]
             for profil in rapport["profils_crees"]}
    assert set(crees) == set(declarees), (crees, declarees)
    assert crees == declarees, (crees, declarees)
    # Les deux fichiers existent reellement, et ils sont deux.
    chemins = {profil["chemin_relatif"] for profil in rapport["profils_crees"]}
    assert len(chemins) == 2, chemins
    for chemin in chemins:
        assert (project_dir / chemin).is_file(), chemin


def test_le_profil_cree_par_le_vrac_est_celui_que_calibrate_produirait(
    tmp_path,
) -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 7) -- le troisieme de `deferred-work.md`.

    Il avait recu un substitut actif **partiel** (`EPIC5-ARB-96`,
    `test_le_verdict_du_profil_de_chaine_atteint_le_project_json_ecrit`): ce qui
    restait a couvrir etait l'entree **de la page de calibration elle-meme**, qui
    n'existait que dans une passe mixte. Cette entree a disparu du lot avec
    `EPIC5-ARB-82`.

    Ce qui la remplace est plus fort, et c'est la lettre de l'AC 7: la feuille
    trouvee dans le vrac « produit un profil, **exactement celui que
    `scan ... calibrate` produirait de la meme feuille** ». Le tri **appelle**
    `_consigner_le_profil_de_chaine` et n'en reecrit rien ; ce test le mesure sur
    le **document ecrit**, verdict d'acceptation compris -- la seule forme sous
    laquelle « c'est le meme profil » est falsifiable.

    Les deux passes lisent la **meme** feuille, sous la meme presse et au meme
    dpi: tout ecart entre les deux documents vient donc du chemin et de rien
    d'autre.
    """
    feuille = app.page_de_calibration_autonome(
        scan_chain_label="hp envy 4520 tiff 300 dpi")

    # Voie 1 -- `scan ... calibrate`, la feuille scannee seule.
    projet_calibrate = tmp_path / "projet-calibrate"
    dossier_seul = app.write_scan_folder(
        tmp_path / "seule", [(feuille, app.PRESSE_CALIBRATION)])
    assert cli.main(["scan", "--project", str(projet_calibrate), "--scan",
                     str(dossier_seul), "--dpi", str(app.DPI), "calibrate"]) == 0

    # Voie 2 -- le vrac: la meme feuille, au milieu de deux planches.
    projet_vrac = tmp_path / "projet-vrac"
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    dossier_vrac = app.write_scan_folder(tmp_path / "vrac", [
        (payloads[0], app.PRESSES_DU_TIRAGE[0]),
        (feuille, app.PRESSE_CALIBRATION),
        (payloads[1], app.PRESSES_DU_TIRAGE[1])])
    assert app.run_scan(projet_vrac, dossier_vrac) == 0

    (par_calibrate,) = sorted(
        (projet_calibrate / "versions" / "calibration").glob("*.json"))
    (par_le_vrac,) = sorted(
        (projet_vrac / "versions" / "calibration").glob("*.json"))
    gauche = json.loads(par_calibrate.read_text(encoding="utf-8"))
    droite = json.loads(par_le_vrac.read_text(encoding="utf-8"))

    # UN SEUL champ differe volontairement -- le **commentaire**, ou le vrac
    # ecrit d'ou vient la feuille, seul moyen pour l'operateur de retrouver la
    # passe qui l'a produite.
    #
    # **L'ETIQUETTE N'EN FAIT PLUS PARTIE** (constat de terrain `D2`,
    # 2026-09-06), et ce test a rougi sur cette convergence. Il posait
    # `droite["label"] != gauche["label"]` : le vrac prenait le
    # `scan_chain_label` de la feuille, tandis que `scan ... calibrate` hors
    # terminal gardait le defaut silencieux de 5.23. La question laissee
    # ouverte a la redaction (« quel nom porte le profil cree quand le vrac
    # tourne sans personne devant l'ecran ? ») recevait donc deux reponses
    # differentes selon la voie -- ce qui est exactement ce que l'invariant du
    # module refuse depuis `EPIC5-ARB-92` : « aucune des voies ne peut ecrire un
    # profil que l'autre n'ecrirait pas ».
    #
    # `D2` a ferme l'ecart en posant la precedence **saisie -> libelle du QR ->
    # `chain_id`** en un seul endroit (`scan_calibrate.etiquette_du_profil`),
    # pour les trois appelants. Les deux voies lisant la meme feuille, elles
    # rendent maintenant la meme etiquette -- donc le meme nom de fichier. La
    # divergence que ce test mesurait n'etait pas une propriete a tenir : c'etait
    # le defaut, et il est ferme.
    # **`scan_dir` rejoint le commentaire dans les volatiles** (`EPIC11-ARB-262`,
    # 2026-09-07), et pour exactement son motif : il dit D'OU vient la feuille, et
    # les deux voies la lisent depuis deux dossiers reellement differents
    # (`scans/seule` d'un cote, `scans/vrac` de l'autre). Ce n'est pas une
    # divergence de profil : c'est de la provenance, et l'invariant
    # d'`EPIC5-ARB-92` porte sur ce que la FEUILLE dicte -- identite de chaine,
    # forme, coefficients, cardinaux, temoins, verdict, etiquette. Le confondre
    # avec la correction ferait de deux dossiers de scan un ecart de calibration.
    #
    # Il est mesure a part, plus bas, plutot qu'ecarte en silence.
    volatiles = {"comment", "generated_at_utc", "created",
                 calibration_profile.SCAN_DIR_FIELD}
    assert {cle: valeur for cle, valeur in droite.items() if cle not in volatiles} == {
        cle: valeur for cle, valeur in gauche.items() if cle not in volatiles}
    # Le verdict d'acceptation en fait partie, et il est **non vide**: sans cette
    # assertion, deux documents sans verdict passeraient la comparaison ci-dessus.
    assert droite["acceptance"], droite.get("acceptance")
    assert droite["acceptance"] == gauche["acceptance"]
    assert droite["source_page_id"] == gauche["source_page_id"]
    assert droite["chain_id"] == gauche["chain_id"]
    # La provenance, mesuree des DEUX cotes : chaque profil nomme SON dossier, en
    # relatif POSIX, et les deux ne se confondent pas. Sans cette paire, ecarter
    # `scan_dir` des volatiles suffirait a rendre le champ muet sans que rien ne
    # rougisse -- c'est-a-dire a rouvrir le faux orphelin d'`EPIC11-ARB-262`.
    champ = calibration_profile.SCAN_DIR_FIELD
    assert gauche[champ] == "scans/seule", gauche[champ]
    assert droite[champ] == "scans/vrac", droite[champ]
    # Et l'anti-tautologie, sans laquelle la comparaison ci-dessus serait verte
    # pour deux voies redevenues muettes ensemble : l'etiquette est celle que la
    # FEUILLE porte, des deux cotes. Un repli conjoint sur le `chain_id`, ou sur
    # une chaine vide, ferait rougir ces deux lignes.
    assert droite["label"] == feuille["scan_chain_label"], droite["label"]
    assert gauche["label"] == feuille["scan_chain_label"], gauche["label"]
    assert par_le_vrac.name == par_calibrate.name, (
        "les deux voies lisent la meme feuille : elles doivent la nommer "
        "pareil. `EPIC5-ARB-92` -- aucune des voies ne peut ecrire un profil "
        f"que l'autre n'ecrirait pas ({par_le_vrac.name} / "
        f"{par_calibrate.name})")
    assert par_le_vrac.stem != droite["chain_id"], (
        "le nom du fichier est retombe sur l'identite de chaine : la "
        "precedence de `D2` ne joue plus alors que la feuille porte un libelle")


# ---------------------------------------------------------------------------
# `EPIC5-ARB-96` -- substitut actif pour le bout **aval** du bloquant `C2`
# ---------------------------------------------------------------------------
#
# Le test juste au-dessus dort depuis l'AC 11 de 5.23: sa mise en situation etait une
# **pile mixte** (page de calibration a l'index 0, planches ensuite), regime que l'AC 10
# refuse desormais. Ce qui dormait avec lui n'est pas une propriete perimee: « le verdict
# consigne dans le profil atteint le manifest **ecrit** » reste vraie, et c'est la moitie
# aval du bloquant `C2` -- un renommage de cle entre `color_calibration` et
# `io.scan_manifest` ne serait plus attrape par aucun test de bout en bout (action item 3
# de la retro Epic 4).
#
# Le regime qui la porte **sans** pile mixte existe depuis `EPIC5-ARB-82`: un lot est
# corrige par le **profil de sa chaine** (`correction_source = chain_profile`) sans
# qu'aucune page de calibration ne soit dans la passe -- c'est le cas nominal de la v2.1,
# le profil etant ajuste une fois par chaine puis reutilise. Les planches transportent
# alors `chain_profile_acceptance`, et c'est sur elles qu'on mesure la traversee.
#
# Deux verdicts distincts et une chaine muette, parce que la collection est le point
# fragile: l'entree visee n'est **pas** la premiere, sa voisine porte un verdict aux
# grandeurs toutes differentes, et la troisieme n'en porte aucun. Une projection qui
# poserait le bloc sur la premiere entree, sur toutes, ou sur aucune, se voit.


def _verdict_de_la_chaine_visee() -> cc.AcceptanceVerdict:
    """Le verdict consigne dans le profil de la chaine **visee**.

    Onze champs, dont les **sept grandeurs numeriques sont deux a deux distinctes**:
    regle des fabriques appliquee a un enregistrement plat (famille `M33`), sans quoi deux
    champs echanges a la serialisation rendraient un bloc d'apparence normale. Les deux
    identifiants restent ceux des registres reels -- il n'y a qu'une entree dans chacun --,
    donc ce sont les grandeurs et le booleen de budget qui portent la distinction.
    """
    return cc.AcceptanceVerdict(
        status="applied",
        mean_delta_e=3.25,
        max_delta_e=7.5,
        mean_delta_e_before=11.75,
        acceptance_id="color-acceptance-1",
        distortion_budget_id="color-distortion-budget-1",
        mean_degradation_de76=0.5,
        max_neutral_degradation_de76=1.25,
        max_degradation_de76=2.75,
        distortion_budget_met=True,
        neutral_axis_channel_spread_8bit=4.5,
    )


def _verdict_de_la_chaine_voisine() -> cc.AcceptanceVerdict:
    """Le verdict d'une **autre** chaine, portee par une autre page de la meme passe.

    Aucune de ses valeurs ne coincide avec celles de la chaine visee, booleen de budget
    compris: c'est ce qui fait mourir le mutant « le bloc est pose sur la mauvaise
    entree » (classe `M25`), qui survit integralement a une fabrique uniforme.
    """
    return cc.AcceptanceVerdict(
        status="applied",
        mean_delta_e=1.5,
        max_delta_e=2.25,
        mean_delta_e_before=6.75,
        acceptance_id="color-acceptance-1",
        distortion_budget_id="color-distortion-budget-1",
        mean_degradation_de76=0.125,
        max_neutral_degradation_de76=0.375,
        max_degradation_de76=0.875,
        distortion_budget_met=False,
        neutral_axis_channel_spread_8bit=1.75,
    )


def _planche_corrigee_par_une_chaine(page_rectifiee, *, chain_id: str, page_id: str,
                                     source_page_id: str,
                                     acceptance: "cc.AcceptanceVerdict | None"):
    """Une planche corrigee par le profil d'une chaine, par ses **vrais** producteurs.

    Le document de profil est ecrit par `profile_to_document`, relu par
    `chain_correction_from_document`, et la planche est calibree par `calibrate_page` avec
    la provenance nommee -- exactement la sequence que `cli._scanned_pages_for_output`
    construit dans ce regime. Un `SimpleNamespace` ferait passer un renommage de champ
    inapercu, ce que cette famille de tests existe pour empecher.

    ``acceptance=None`` produit le **domaine inerte**: un profil sans verdict consigne,
    dont la planche ne doit faire apparaitre aucun bloc au document.
    """
    correction = cc.chain_correction_from_document(cc.profile_to_document(
        _profil_affine_distinguable(), chain_id=chain_id, source_page_id=source_page_id,
        template_id=scan.TPL_V2, read_patch_count=14, retained_patch_count=13,
        ink_floor_excluded=False, acceptance=acceptance))
    return cc.calibrate_page(
        page_rectifiee, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600,
        page_id=page_id,
        imported_profile=correction.profile,
        imported_source_page_id=correction.source_page_id,
        imported_correction_source=cc.CORRECTION_SOURCE_CHAIN_PROFILE,
        imported_chain_id=correction.chain_id,
        imported_acceptance=correction.imported_acceptance)


def test_le_verdict_du_profil_de_chaine_atteint_le_project_json_ecrit(tmp_path) -> None:
    """`EPIC5-ARB-96`: la traversee `color_calibration` -> `io.scan_manifest` -> disque.

    Le substitut actif du bout aval du bloquant `C2`. Ce qui est mesure ici n'est pas la
    projection -- `correction_provenance_summary` est deja gardee en amont par
    `test_color_calibration.py` -- mais le fait que le bloc **traverse** jusqu'au
    `project.json` reellement ecrit sur le disque. L'assertion porte donc sur le fichier
    relu, jamais sur la valeur de retour de `build_scan_manifest`: c'est la seule forme
    sous laquelle « atteint le manifest » est falsifiable.

    La passe ne contient **aucune** page de calibration: trois planches, chacune corrigee
    par le profil de sa chaine (`EPIC5-ARB-82`). Aucune pile mixte n'est donc requise, et
    aucun test endormi n'est reveille.
    """
    page = _synthetic_rectified_page(
        template_id=TEMPLATE, preset_id=PRESET, distort=couleur._NOMINAL_PRESS)
    # La cible est a l'index **1**: un `find` ou une projection qui rendrait toujours la
    # premiere entree de la collection ne se demasque pas autrement.
    planches = (
        (0, _planche_corrigee_par_une_chaine(
            page, chain_id="chaine-m", page_id="lot-a-p0",
            source_page_id="feuille-de-chaine-m",
            acceptance=_verdict_de_la_chaine_voisine())),
        (1, _planche_corrigee_par_une_chaine(
            page, chain_id="chaine-z", page_id="lot-a-p1",
            source_page_id="feuille-de-chaine-z",
            acceptance=_verdict_de_la_chaine_visee())),
        # Le domaine inerte, sans lequel la presence du bloc ne prouverait pas qu'il vient
        # du profil: une chaine dont le profil ne consigne aucun verdict.
        (2, _planche_corrigee_par_une_chaine(
            page, chain_id="chaine-c", page_id="lot-a-p2",
            source_page_id="feuille-de-chaine-c", acceptance=None)),
    )

    # Les pages arrivent **dans le desordre**, et la cible n'est ni la premiere arrivee ni
    # la premiere de l'ordre trie: l'ordre de scan n'est pas une donnee, et une collection
    # dont l'ordre d'arrivee coincide avec l'ordre attendu ne distingue pas les deux.
    ordre_d_arrivee = (2, 0, 1)
    assert list(ordre_d_arrivee) != sorted(ordre_d_arrivee)
    payloads = [scan.make_payload(page_index=index, page_count=3, slot_count=1)
                for index in ordre_d_arrivee]
    # Le regime est bien celui de la story: pas une seule page de calibration dans la pile.
    assert all(payload["page_role"] == scan.page_roles.PAGE_ROLE_IMAGES
               for payload in payloads)

    projet = tmp_path / "projet"
    scan.scan_once(projet, payloads, page_calibrations=planches)

    ecrit = json.loads((projet / sm.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    consignees = ecrit["reconstruction"]["page_calibration_results"]
    entrees = {entree["page_index"]: entree for entree in consignees}
    assert set(entrees) == {0, 1, 2}
    # La collection est ecrite dans l'ordre des pages et non dans celui ou la passe les a
    # lues: sans cette clause, un ordre d'iteration inverse rendait deux documents
    # differents pour la meme passe sans qu'aucun test ne rougisse (mutant survivant du
    # premier tour d'injection).
    assert [entree["page_index"] for entree in consignees] == [0, 1, 2]

    # --- l'entree visee, grandeur par grandeur et en litteral -------------------------
    publie = entrees[1]["chain_profile_acceptance"]
    # Le jeu de cles est verifie **en entier**: une cle renommee entre les deux modules
    # ferait autrement disparaitre une grandeur sans qu'aucune egalite ne rougisse.
    assert set(publie) == {
        "status", "acceptance_id", "mean_delta_e", "max_delta_e", "mean_delta_e_before",
        "distortion_budget_id", "mean_degradation_de76", "max_neutral_degradation_de76",
        "max_degradation_de76", "distortion_budget_met",
        "neutral_axis_channel_spread_8bit",
    }
    assert publie["status"] == "applied"
    assert publie["acceptance_id"] == "color-acceptance-1"
    assert publie["mean_delta_e"] == 3.25
    assert publie["max_delta_e"] == 7.5
    assert publie["mean_delta_e_before"] == 11.75
    assert publie["distortion_budget_id"] == "color-distortion-budget-1"
    assert publie["mean_degradation_de76"] == 0.5
    assert publie["max_neutral_degradation_de76"] == 1.25
    assert publie["max_degradation_de76"] == 2.75
    assert publie["distortion_budget_met"] is True
    assert publie["neutral_axis_channel_spread_8bit"] == 4.5
    # Et c'est bien la planche de la chaine visee: sans ce volet, le bloc pourrait etre
    # juste et pose sur la mauvaise page.
    assert entrees[1]["correction_source"] == cc.CORRECTION_SOURCE_CHAIN_PROFILE
    assert entrees[1]["correction_chain_id"] == "chaine-z"
    assert entrees[1]["correction_source_page_id"] == "feuille-de-chaine-z"

    # --- la voisine porte **son** verdict, pas celui de la cible ----------------------
    voisin = entrees[0]["chain_profile_acceptance"]
    assert entrees[0]["correction_chain_id"] == "chaine-m"
    assert entrees[0]["correction_source_page_id"] == "feuille-de-chaine-m"
    assert voisin["mean_delta_e"] == 1.5
    assert voisin["max_delta_e"] == 2.25
    assert voisin["mean_delta_e_before"] == 6.75
    assert voisin["mean_degradation_de76"] == 0.125
    assert voisin["max_neutral_degradation_de76"] == 0.375
    assert voisin["max_degradation_de76"] == 0.875
    assert voisin["distortion_budget_met"] is False
    assert voisin["neutral_axis_channel_spread_8bit"] == 1.75

    # --- le domaine inerte -------------------------------------------------------------
    assert "chain_profile_acceptance" not in entrees[2]
    assert entrees[2]["correction_chain_id"] == "chaine-c"

    # --- les deux mesures ne se recouvrent pas ------------------------------------------
    # `distortion` dit ce que la correction a deforme **sur cette planche et lors de ce
    # scan**; `chain_profile_acceptance` ce que le profil avait mesure le jour ou il a ete
    # ajuste. Sans cette clause, un manifest qui republierait la mesure de la passe sous la
    # cle du profil satisferait toutes les egalites ci-dessus le jour ou les deux
    # coincideraient par hasard.
    assert entrees[1]["distortion"]["mean_degradation_de76"] != publie[
        "mean_degradation_de76"]
