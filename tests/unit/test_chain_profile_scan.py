"""Story 5.22, taches 4 a 6: le profil de chaine au scan (AC 3, 4, 5, 6, 7, 9).

Ce que cette suite mesure, et que rien ne mesurait avant elle: la correction
couleur d'un lot vient desormais du **profil de la chaine de scan**, ajuste une
seule fois par `scan calibrate`, et **reutilise** -- jamais re-ajuste a la volee
sur une page du lot. C'est le correctif du declencheur de la story: le mecanisme
par lot de 5.16 ajustait la correction a chaque scan, si bien qu'une feuille
reposee autrement derivait au-dela de `color-divergence-1` et etait refusee,
alors que la chaine et le scanner etaient les memes.

Trois regimes, chacun de bout en bout par la CLI (aucun maillon simule):

* **profil present** -> les planches recoivent le profil de la chaine, la
  provenance du manifest designe le profil et sa chaine (AC 5, AC 9);
* **profil absent** -> la commande **n'echoue pas**, elle avertit en nommant les
  deux gestes possibles, et le lot est livre en brut (AC 3, AC 7);
* **planche deviante** -> avertissement chiffre au manifest et frames brutes sans
  geste explicite; profil applique tel quel **avec** le geste (AC 6).

Regle des fabriques (CLAUDE.md), appliquee quatre fois:

* les lots portent **deux planches** imprimees sous des presses **differentes**,
  donc un appariement page -> profil permute se voit;
* le lot deviant place sa planche deviante **en seconde position**, donc une
  garde qui ne regarderait que la premiere planche se demasque;
* les deux chaines des tests d'appariement chaine -> profil sont **distinguables**
  (deux dpi declares), et la chaine visee n'est pas celle du premier profil
  ecrit dans le projet;
* le lot du test de journal porte **trois** planches, une par regime -- corrigee,
  livree non corrigee (deviante, en seconde position), en echec -- parce que
  l'interdit du mot « refusee » ne se mesure qu'en face de l'endroit ou ce mot
  reste vrai.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import MappingProxyType

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# La regle de regime -- « une reference de perimetre inatteignable est-elle un
# historique tronque, ou un AUTRE depot ? » -- vit dans `tests/_regime_du_depot.py`,
# ecrite une fois pour ses sept appelants.
sys.path.insert(0, str(REPO_ROOT / "tests"))
from _regime_du_depot import echoue_ou_saute  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import (  # noqa: E402
    cli,
    color_calibration as cc,
    color_metrics,
    color_pipeline,
    page_roles,
    scan_chain,
    scan_ingest,
)
from mixed_media_utility.io import calibration_profile  # noqa: E402

import test_calibration_page_source as couleur  # noqa: E402
import test_scan_calibration_application as app  # noqa: E402
from test_color_calibration import _synthetic_rectified_page  # noqa: E402


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


def _write_calibration_scan(folder: Path) -> Path:
    """Un dossier de scan ne contenant que la **page de calibration** de la chaine.

    C'est ce que `scan calibrate` consomme depuis la story 5.22: la page est
    generee a la demande (tache 3), imprimee, scannee **seule**. Elle est peinte
    sous la presse du tirage, donc le profil ajuste est celui de cette chaine.
    """
    payload = app.lot_payloads()[0]
    assert payload["page_role"] == page_roles.PAGE_ROLE_CALIBRATION
    folder.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(folder / "calibration.tiff"),
                app.build_page(payload, press=app.PRESSE_CALIBRATION))
    return folder


def _write_images_lot(folder: Path, *, presses=None, sheet_count: int = 2) -> list:
    """Un lot **sans page de calibration**: le regime nominal depuis la story 5.22.

    Les planches sont imprimees sous des presses **differentes** (variation de
    tirage): un appariement planche -> resultat permute se verrait, et deux
    entrees de manifest identiques au chiffre pres ne prouveraient rien.
    """
    presses = presses if presses is not None else app.PRESSES_DU_TIRAGE
    payloads = app.lot_payloads(sheet_count=sheet_count, with_calibration=False)
    app.write_scan_folder(folder, list(zip(payloads, presses)))
    return payloads


def _calibrate_chain(project_dir: Path, tmp_path: Path, *args: str) -> int:
    """Lancer `scan ... calibrate` sur la page de calibration de la chaine."""
    folder = _write_calibration_scan(tmp_path / "scan-calibration")
    return cli.main(["scan", "--project", str(project_dir), "--scan", str(folder),
                     "--dpi", str(app.DPI), *args, "calibrate"])


def _chain_id_of(project_dir: Path, folder: Path) -> str:
    """L'identite de chaine **derivee** par les vrais producteurs, jamais recopiee.

    Un test qui ecrirait le condensat en dur figerait la recette au lieu de la
    verifier, et cesserait de mordre au premier changement de materiel capture.
    """
    report = scan_ingest.ingest_scan_lot(project_dir, folder, dpi=app.DPI)
    return scan_chain.derive_chain_id(
        declared_dpi=report.declared_dpi,
        scan_input_format=scan_chain.report_scan_input_format(report),
        *(),
        **dict(zip(("make", "model", "software"),
                   scan_chain.read_scan_tags(folder))))


def _profiles_in(project_dir: Path) -> list[Path]:
    versions = (project_dir / calibration_profile.VERSIONS_DIRNAME
                / calibration_profile.CALIBRATION_DIRNAME)
    return sorted(versions.glob("*.json")) if versions.is_dir() else []


# --- la forme de l'invocation a change, pas le sujet (5.23, AC 11, 2026-08-18) ---
#
# Ce fichier a ete ecrit sous 5.22, quand `scan` **devinait** le profil: il derivait
# l'identite de la chaine puis lisait `versions/calibration/<chain_id>.json`. La story
# 5.23 (AC 12, `EPIC5-ARB-83`) supprime cet appariement -- la derivation est mesuree
# defaillante sur le materiel d'Egan, deux scanners differents rendant tous deux
# `600-tiff-e2168f9b2b81` --, et l'operateur **designe** desormais son profil.
#
# Les tests dont le sujet survit a ce changement sont **repares** plutot que desactives
# (AC 11): ils passent le profil a `--profil`, et mesurent exactement ce qu'ils
# mesuraient. Ceux dont le sujet etait l'appariement lui-meme sont **retires**, avec
# leur table de reprise, plus bas dans ce fichier.
def _profil_de(project_dir: Path) -> str:
    """Le chemin du profil que `scan calibrate` vient d'ecrire, a designer au scan.

    Le cardinal est verifie: un projet qui en porterait deux rendrait ce raccourci
    ambigu, et un test qui designerait « un » profil ne prouverait plus lequel.
    """
    (profil,) = _profiles_in(project_dir)
    return str(profil)


def _designe(project_dir: Path) -> tuple[str, str]:
    """Le couple d'arguments `--profil <chemin>` a passer a `app.run_scan`."""
    return (cli.PROFILE_FLAG, _profil_de(project_dir))


def _write_lot_deviant(folder: Path) -> list:
    """Un lot de deux planches **sans page de calibration**, la seconde deviante.

    Remplace `app._lot_deviant()` dans ce fichier: cette fabrique-la pose la page de
    calibration dans la meme passe que les planches, ce qui est le regime que l'AC 10
    refuse et que l'AC 11 desactive ailleurs. Ici la deviance n'a rien a voir avec la
    pile: elle se mesure contre le profil **designe**.

    Regle des fabriques: la planche deviante n'est **pas** en premiere position, donc
    une garde qui ne regarderait que la premiere planche se demasque.
    """
    return _write_images_lot(
        folder, presses=(app.PRESSES_DU_TIRAGE[0], couleur._DEVIANT_PRESS))


# ---------------------------------------------------------------------------
# AC 5 -- les lots de la meme chaine sont calibres avec le profil REUTILISE
# ---------------------------------------------------------------------------


def test_un_lot_sans_page_de_calibration_est_corrige_par_le_profil_de_la_chaine(
        tmp_path: Path) -> None:
    """Le regime nominal de la story: calibrer la chaine une fois, scanner ensuite.

    Le lot ne porte **aucune** page de calibration -- c'est ce que la tache 3 rend
    possible -- et il est pourtant corrige. Avant cette story, ce lot ressortait
    `not_applied` sans un pixel corrige.
    """
    project_dir = tmp_path / "projet"
    assert _calibrate_chain(project_dir, tmp_path) == 0
    assert len(_profiles_in(project_dir)) == 1

    folder = tmp_path / "lot"
    payloads = _write_images_lot(folder)
    # `--profil`: depuis `EPIC5-ARB-83` le profil se DESIGNE. Le sujet du test est
    # inchange -- un lot sans page de calibration est corrige par le profil de sa
    # chaine --, seule la forme de l'invocation l'est.
    assert app.run_scan(project_dir, folder, *_designe(project_dir)) == 0

    document = app.manifest_of(project_dir)
    assert document["color"]["color_calibration_status"] == color_pipeline.APPLIED_STATUS
    entrees = app.calibration_entries(document)
    # **Les deux planches**, et pas seulement la premiere: une garde qui ne
    # regarderait qu'une page passerait sur un lot mono-planche.
    assert set(entrees) == {p["page_index"] for p in payloads}
    for entree in entrees.values():
        assert entree["status"] == color_pipeline.APPLIED_STATUS, entree


def test_la_provenance_designe_le_profil_de_chaine_et_non_une_page_du_lot(
        tmp_path: Path) -> None:
    """AC 5 et AC 9: le champ source designe le **profil**, pas une page du lot.

    Sans lui, une frame corrigee depuis le profil de la chaine et une frame
    corrigee depuis la page de calibration d'un ancien tirage sont
    indistinguables a posteriori -- et la question « avec quoi ce master a-t-il
    ete corrige » n'a plus de reponse dans le seul artefact persistant.
    """
    project_dir = tmp_path / "projet"
    assert _calibrate_chain(project_dir, tmp_path) == 0
    (profil,) = _profiles_in(project_dir)
    document_profil = json.loads(profil.read_text(encoding="utf-8"))
    # L'identite se lit DANS le document, plus jamais dans le nom du fichier :
    # depuis le constat `D2` (2026-09-06) le fichier porte le libelle imprime
    # sur la page, et les deux ne coincident que sur une feuille anterieure a
    # `scan_chain_label`. Prendre `profil.stem` pour une identite de chaine
    # etait exactement ce que ce test faisait, et il a rougi pour cela.
    chain_id = document_profil["chain_id"]
    assert chain_id != profil.stem, (
        "cette fabrique doit porter un libelle de chaine, sinon les deux "
        "moities de l'assertion ci-dessous mesurent la meme valeur")

    folder = tmp_path / "lot"
    _write_images_lot(folder)
    assert app.run_scan(project_dir, folder, cli.PROFILE_FLAG, str(profil)) == 0

    for entree in app.calibration_entries(app.manifest_of(project_dir)).values():
        assert entree["correction_source"] == cc.CORRECTION_SOURCE_CHAIN_PROFILE
        # La chaine, sous une cle **a elle**. Elle ne nomme PLUS le fichier
        # (`D2`) : celui-ci se retrouve par son chemin, que le manifeste porte
        # ailleurs et que `io/profile_designation` resout. Ce que cette cle
        # porte est la PROVENANCE -- avec quelle chaine ce lot a ete corrige --,
        # et c'est a cette question-la qu'elle repond seule.
        assert entree["correction_chain_id"] == chain_id
        # Et la page qui a **ajuste** les coefficients reste designee: c'est la
        # feuille physique a rescanner si la calibration devait etre reprise. Les
        # deux champs repondent a deux questions et ne se confondent pas.
        assert entree["correction_source_page_id"] == document_profil["source_page_id"]
        assert entree["correction_source_page_id"] != entree["correction_chain_id"]


def test_deux_lots_de_la_meme_chaine_recoivent_le_meme_profil_au_coefficient_pres(
        tmp_path: Path, monkeypatch) -> None:
    """AC 5: deux lots scannes separement recoivent la **meme** correction.

    C'est la propriete que le mecanisme par lot ne pouvait pas tenir: il
    re-ajustait a chaque scan, donc deux scans de la meme chaine recevaient deux
    corrections differentes -- et la seconde pouvait etre refusee pour divergence.

    **Amende le 2026-08-17 (revue, finding C4), et l'amendement deplace la
    propriete au lieu de la diluer.** La premiere redaction annoncait en docstring
    l'egalite des coefficients, puis comparait des `chain_id` -- des chaines de
    caracteres -- et enfin le fichier de profil **a lui-meme** (deux relectures du
    meme fichier). Elle etait donc verte quel que soit le profil reellement
    applique aux planches, y compris si aucune n'en avait recu. C'est
    `EPIC5-ARB-39` mot pour mot: un test d'integration qui n'asserte pas sur les
    valeurs ne prouve rien.

    Ce que la version ci-dessous mesure: les coefficients du profil **reellement
    transmis a chaque planche des deux lots**, captures sur le chemin de
    production (`calibrate_page`, par le meme geste que l'espion de la frontiere
    negative), et leur egalite avec ceux du fichier de chaine. Les `chain_id` sont
    conserves -- ils portent la provenance au manifest -- mais ils ne portent plus
    seuls la promesse.

    Les deux lots restent **distinguables** (presses inversees d'un lot a l'autre,
    regle des fabriques): un appariement lot -> profil qui rendrait toujours le
    premier resultat ne se demasquerait pas sur deux lots identiques.
    """
    project_dir = tmp_path / "projet"
    assert _calibrate_chain(project_dir, tmp_path) == 0
    (profil,) = _profiles_in(project_dir)
    attendu = cc.profile_from_document(
        json.loads(profil.read_text(encoding="utf-8")))

    # L'espion porte sur l'attribut du module **vu par `cli`**: c'est le chemin que la
    # production emprunte reellement, et il rend le profil transmis a chaque planche.
    appliques: list[tuple[str, object]] = []
    vrai_calibrate_page = cc.calibrate_page

    def espion(*args, **kwargs):
        appliques.append((kwargs.get("page_id"), kwargs.get("imported_profile")))
        return vrai_calibrate_page(*args, **kwargs)

    monkeypatch.setattr(cc, "calibrate_page", espion)

    empreintes = []
    for rang, presses in enumerate(
            (app.PRESSES_DU_TIRAGE, tuple(reversed(app.PRESSES_DU_TIRAGE)))):
        folder = tmp_path / f"lot-{rang}"
        _write_images_lot(folder, presses=presses)
        assert app.run_scan(
            project_dir, folder, "--overwrite", *_designe(project_dir)) == 0
        document = json.loads(
            (project_dir / "project.json").read_text(encoding="utf-8"))
        empreintes.append({
            index: entree["correction_chain_id"]
            for index, entree in app.calibration_entries(document).items()})

    # Les deux passes designent la meme chaine, donc le meme fichier de profil.
    assert empreintes[0] == empreintes[1], empreintes

    # **La clause de l'AC 5, assertee sur les valeurs.** Deux lots x deux planches:
    # le cardinal est verifie d'abord, sans quoi une boucle vide passerait tout.
    assert len(appliques) == 4, appliques
    reference = _coefficients(attendu)
    assert reference, "un profil sans coefficient ne prouverait rien"
    assert any(bloc.size for bloc in reference.values()), reference
    for page_id, profil_applique in appliques:
        assert profil_applique is not None, (
            f"{page_id}: aucune planche ne doit etre calibree sans profil importe")
        obtenus = _coefficients(profil_applique)
        # Les **cles** aussi: une forme qui perdrait un bloc de coefficients passerait
        # une comparaison bloc a bloc menee sur les seules cles communes.
        assert sorted(obtenus) == sorted(reference), (page_id, sorted(obtenus))
        for nom, bloc in reference.items():
            assert np.array_equal(bloc, obtenus[nom]), (page_id, nom)


def _coefficients(profile) -> dict:
    """Les tableaux de coefficients d'un profil, par nom, pour comparer valeur a valeur.

    Rend un **dictionnaire** et non une suite ordonnee: une comparaison par `zip`
    de deux suites tronque silencieusement sur la plus courte, donc une forme qui
    perdrait un bloc de coefficients passerait sans un mot.
    """
    document = cc.profile_to_document(
        profile, chain_id="x", source_page_id="p", template_id="t",
        read_patch_count=0, retained_patch_count=0, ink_floor_excluded=False)
    return {key: np.asarray(value, dtype=float)
            for key, value in document["coefficients"].items()}


def test_aucune_planche_n_est_ajustee_sur_ses_propres_pastilles_avec_un_profil(
        tmp_path: Path, monkeypatch) -> None:
    """AC 5, frontiere negative (style 5.19): `_fit_lot_correction` n'est PAS atteint.

    La frontiere est posee sur le **chemin d'execution** et non sur un grep de
    source: c'est la seule forme qui mord. Un ajustement a la volee ressuscite par
    une branche de repli passerait un grep si le nom de la fonction changeait, et
    passerait une inspection du manifest si la correction resultante etait proche.
    """
    project_dir = tmp_path / "projet"
    assert _calibrate_chain(project_dir, tmp_path) == 0

    # Story 11.4b (lot S1) : `_fit_lot_correction` a suivi la moitie aval du
    # scan dans le module de coeur `scan_write`. Substituer
    # `cli._fit_lot_correction` n'intercepterait plus rien -- et le volet
    # negatif serait vert pour rien, ce que le temoin positif de la fin mesure.
    from mixed_media_utility import scan_write

    appels = []
    vrai = scan_write._fit_lot_correction

    def espion(*args, **kwargs):
        appels.append(kwargs)
        return vrai(*args, **kwargs)

    monkeypatch.setattr(scan_write, "_fit_lot_correction", espion)
    folder = tmp_path / "lot"
    _write_images_lot(folder)
    assert app.run_scan(project_dir, folder, *_designe(project_dir)) == 0
    assert appels == [], (
        "un profil de chaine est present: aucun ajustement a la volee ne doit avoir "
        "lieu, sur aucune page")

    # **Temoin positif, indispensable**: sans profil, la fonction EST appelee. Sans
    # lui, un espion mal branche rendrait le volet ci-dessus vert pour rien.
    autre = tmp_path / "projet-sans-profil"
    folder2 = tmp_path / "lot2"
    _write_images_lot(folder2)
    assert app.run_scan(autre, folder2) == 0
    assert len(appels) == 1, appels


# ---------------------------------------------------------------------------
# AC 4 -- l'identite de chaine, surchargeable, et l'appariement chaine -> profil
# ---------------------------------------------------------------------------


def test_le_profil_est_ecrit_sous_l_identite_derivee_du_scan(tmp_path: Path) -> None:
    """AC 4: l'identite du profil est celle que les producteurs derivent -- et
    le NOM DU FICHIER ne l'est plus (constat de terrain `D2`, 2026-09-06).

    **Ce que ce test disait avant, et pourquoi il avait raison de rougir.** Il
    posait `profil.stem == chain_id`, ce qui etait vrai tant que le nom du
    fichier n'avait pas d'autre source. Depuis `D2`, la precedence est
    **saisie -> libelle du QR -> `chain_id`**, et la feuille de cette fabrique
    porte un libelle : le fichier s'appelle donc du libelle, pas du condensat.
    Le raster reel d'Egan est ce qui l'a impose -- son profil s'affichait sous
    un nom que rien sur la page ne portait.

    Les deux moities se separent donc, et les mesurer separement vaut mieux
    qu'en mesurer une :

    * **l'IDENTITE** (`chain_id` dans le document) reste ce que
      `scan_chain.derive_chain_id` produit, et c'est elle qui porte la
      provenance au manifeste. Rien de `D2` ne la touche ;
    * **le NOM DU FICHIER** est ce que `calibration_profile.profile_file_stem`
      decide a partir du document. Il est **demande au producteur**, jamais
      recompose ici -- une seule autorite, comme pour l'identite.

    La derniere assertion est celle qui fait de ce test autre chose qu'une
    tautologie : les deux valeurs doivent **differer**. Sans elle, un
    `profile_file_stem` qui serait revenu au `chain_id` passerait inapercu, et
    `D2` serait defait en silence.
    """
    project_dir = tmp_path / "projet"
    assert _calibrate_chain(project_dir, tmp_path) == 0
    (profil,) = _profiles_in(project_dir)
    document = json.loads(profil.read_text(encoding="utf-8"))

    attendu = _chain_id_of(tmp_path / "derive", tmp_path / "scan-calibration")
    assert document["chain_id"] == attendu

    assert profil.stem == calibration_profile.profile_file_stem(document)
    assert profil.stem != attendu, (
        "le nom du fichier est retombe sur l'identite de chaine : la "
        "precedence de `D2` (saisie -> libelle du QR -> chain_id) ne joue plus "
        f"alors que la page porte le libelle {document.get('label')!r}")


# --- six tests RETIRES, et non desactives (story 5.23, AC 11, 2026-08-18) ----
#
# La distinction est celle du mandat `EPIC5-ARB-84`, et elle decide du geste. Les tests
# **desactives** de cette story posent une page de calibration dans la meme passe que
# des planches: leur **mise en situation** redevient valide avec l'ingest en vrac, seules
# leurs assertions meurent. Les six ci-dessous sont l'inverse -- leur **sujet** est
# l'appariement `chain_id` -> profil, que `EPIC5-ARB-83` (AC 12) supprime pour de bon
# parce que la derivation d'identite est mesuree defaillante sur le materiel d'Egan, et
# `--chain-id`, que `EPIC5-ARB-88` (AC 13) retire. Aucune story a venir ne les fait
# revenir. Les garder endormis promettrait un reveil qui n'arrivera pas.
#
# **Ce qu'ils protegeaient et qui reste vrai est repris nom pour nom**, jamais perdu en
# silence (AC 11, troisieme test):
#
# | test retire | motif du retrait | reprise |
# | --- | --- | --- |
# | `test_chain_id_explicite_relie_la_calibration_et_le_scan` | `--chain-id` n'existe plus (`EPIC5-ARB-88`), et le lien qu'il etablissait entre les deux temps n'existe plus non plus | `test_profil_designe.py::test_le_profil_designe_est_celui_qui_est_applique` -- trois profils, la cible en **deuxieme** position, mesure sur les **coefficients** et non sur un `chain_id`; et `..._le_chemin_de_scan_ne_derive_plus_aucune_identite_de_chaine` |
# | `test_une_chaine_sans_profil_ne_prend_pas_celui_d_une_autre` | c'etait le temoin negatif de l'appariement: il n'y a plus d'appariement dont ce soit la frontiere | `test_profil_designe.py::test_aucun_profil_designe_avertit_et_ne_se_rabat_sur_rien` et `..._ne_lit_aucun_fichier_de_profil` -- **plus fort**: rien n'est repris, meme pas le profil d'une autre chaine, et c'est mesure sur les **lectures** |
# | `test_un_profil_externe_est_valide_consigne_puis_reutilise` | `--charger-profil-de-calibration` a ete **remplace** par `--profil` (AC 12), et « un second scan le retrouve **sans** le drapeau » est desormais faux par decision: aucun profil n'est choisi automatiquement | `test_profil_designe.py::test_un_profil_hors_du_projet_est_applique_sans_refus_lie_au_projet` (validation + application) et `test_l_import_verse_au_manifest_une_entree_autoportante` (le versement). La reutilisation sans drapeau passe desormais par `test_la_commande_dediee_pose_le_defaut_et_le_scan_l_utilise` |
# | `test_un_profil_externe_d_une_autre_chaine_est_refuse_et_jamais_consigne` | **morte**: il n'y a plus de refus de chaine, un profil appartient a une chaine et pas a un projet (`EPIC5-ARB-82`) | la moitie qui survit -- « un profil refuse n'ecrit rien » -- est `test_profil_designe.py::test_un_profil_designe_refuse_n_ecrit_rien_dans_le_projet` |
# | `test_un_lot_dont_toutes_les_planches_divergent_n_est_pas_declare_en_panne` | il epinglait la branche `not_applied` que `declined_page_count` gouvernait; l'AC 3 supprime le regime « toutes les planches divergent » et l'AC 13 le parametre. Le rendre vert en restaurant le parametre reintroduirait ce que `EPIC5-ARB-88` supprime | les six autres cas de `derive_lot_calibration_status` restent couverts par `test_scan_calibration_application.py::test_le_statut_de_lot_derive_des_cas_et_de_rien_d_autre` et `..._les_trois_valeurs_rendues_sont_celles_du_contrat_ferme`, tous deux verts |
# | `test_le_projet_consigne_les_chaines_qui_l_ont_reellement_corrige` | il etablissait « liste triee et monotone » en passant par `--chain-id` deux fois, sur **deux** chaines deja dans l'ordre alphabetique | `test_scan_manifest.py::test_les_chaines_du_projet_sont_triees_et_non_dans_l_ordre_de_scan` (**six** chaines en desordre, cible scannee en derniere position) et `..._les_chaines_deja_connues_du_projet_sont_fusionnees_et_retriees` (dedoublonnage + monotonie). C'est le finding `E-F1` de la revue de 5.22, deja plus fort que ce test |
#
# La frontiere negative correspondante -- `--chain-id` absent du parseur -- vit dans
# `test_restes_inertes_retires.py` (AC 13), et l'absence de toute comparaison de
# `chain_id` dans `test_profil_designe.py::test_aucune_comparaison_de_chain_id_ne_subsiste_dans_la_designation`.


# ---------------------------------------------------------------------------
# AC 3 et AC 7 -- profil absent: avertir, nommer les deux gestes, livrer en brut
# ---------------------------------------------------------------------------


def _journal_de_scan(project_dir: Path) -> str:
    """Le journal `logs/scan.log` du projet, tel que l'operateur le relit.

    **Et non `caplog`**: le logger de `scan` pose `propagate = False`
    (`_configure_scan_logger`), donc aucun enregistrement n'atteint la racine que
    `caplog` ecoute -- un test pose sur `caplog` y lirait une chaine vide et
    passerait des qu'on cesserait d'asserter dessus. Le journal sur disque est de
    surcroit l'artefact que l'operateur relit deux jours plus tard, donc c'est de
    lui que la promesse « les deux gestes sont nommes » doit etre vraie.
    """
    from mixed_media_utility.io import project_layout

    chemin = project_dir / project_layout.LOGS_DIRNAME / "scan.log"
    assert chemin.is_file(), f"aucun journal de scan sous {chemin}"
    return chemin.read_text(encoding="utf-8")


def test_un_scan_sans_profil_de_chaine_n_echoue_pas_et_livre_le_lot_en_brut(
        tmp_path: Path) -> None:
    """AC 3 et 7: la commande rend `0`, avertit, et les frames sortent brutes.

    Refuser la commande ferait perdre l'ingestion et les frames pour un fichier
    que l'operateur peut produire en une passe. Le message doit porter **les deux**
    options, sans quoi l'operateur en decouvre une seule.
    """
    project_dir = tmp_path / "projet"
    folder = tmp_path / "lot"
    payloads = _write_images_lot(folder)

    assert app.run_scan(project_dir, folder) == 0
    journal = _journal_de_scan(project_dir)

    # **Les deux gestes, nommes.** Ce ne sont plus les memes qu'en 5.22 -- « regenerer »
    # et « charger depuis le disque » supposaient une resolution automatique par
    # `chain_id`, supprimee par `EPIC5-ARB-83` --, mais la propriete est la meme et
    # c'est elle que ce test garde: l'operateur ne doit pas decouvrir une seule des
    # deux portes. Designer pour ce scan, ou poser un defaut au projet.
    assert cli.PROFILE_FLAG in journal, journal
    assert cli.SET_DEFAULT_PROFILE_COMMAND in journal, journal

    document = app.manifest_of(project_dir)
    assert document["color"]["color_calibration_status"] == (
        color_pipeline.NOT_APPLIED_STATUS)
    # Le lot **est ecrit**: il n'est pas refuse (AC 7).
    frames = app.written_frames(project_dir, document)
    assert frames, "le lot est livre, pas refuse"
    assert len(frames) == sum(len(p["slots"]) for p in payloads)


def test_un_profil_present_mais_corrompu_est_refuse_et_le_lot_livre_en_brut(
        tmp_path: Path) -> None:
    """Present mais invalide n'est pas absent, et n'est jamais un repli sur un defaut.

    Un profil dont on ne peut pas garantir le contenu ne doit pas etre applique:
    ce sont des pixels qu'on ne saurait plus interpreter.
    """
    project_dir = tmp_path / "projet"
    assert _calibrate_chain(project_dir, tmp_path) == 0
    (profil,) = _profiles_in(project_dir)
    profil.write_text('{"schema_version": 1, "chain_id"', encoding="utf-8")

    folder = tmp_path / "lot"
    _write_images_lot(folder)
    assert app.run_scan(project_dir, folder) == 0
    assert app.manifest_of(project_dir)["color"]["color_calibration_status"] == (
        color_pipeline.NOT_APPLIED_STATUS)


# ---------------------------------------------------------------------------
# AC 10 -- l'ancien tirage continue de fonctionner
# ---------------------------------------------------------------------------


# --- RETIRE PAR LA STORY 5.24 (AC 8, classe C) -----------------------------
#
# `test_un_ancien_tirage_avec_sa_page_de_calibration_reste_lu` vivait ici. Il
# n'est pas desactive, il est **supprime**, et son motif est ecrit a
# l'emplacement du retrait comme la doctrine du depot l'exige: **un test dont le
# SUJET a disparu ne se desactive pas**.
#
# Son sujet etait « un lot imprime AVANT la story 5.22, dont la page de
# calibration est a l'index 0, reste lu ». `EPIC5-ARB-90` a tranche qu'aucune
# compatibilite n'existe pour les feuilles imprimees avant le 17 aout, et
# `io.payload.validate_payload` refuse cette feuille **en amont du tri**: elle ne
# porte pas `scan_chain_label`, exige sous le role `c` depuis 5.23. Le sujet
# n'existe donc plus a aucun etage -- ni au payload, ni a la detection, ni au
# tri -- et le rejouer demanderait de rouvrir un arbitrage rendu.
#
# Ce que la propriete gardait de vivant -- « la lecture d'une page de calibration
# presente n'est pas retiree avec le placement automatique » -- est desormais
# porte par le regime de vrac, et epingle par
# `test_le_profil_designe_gagne_et_la_feuille_du_vrac_est_seulement_consignee`
# juste en dessous.
# ---------------------------------------------------------------------------


def test_le_profil_designe_gagne_et_la_feuille_du_vrac_est_seulement_consignee(
        tmp_path: Path) -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 7) -- **devient le test de l'AC 7**.

    « La priorite ne se mesure que quand les deux sont la », et c'est le vrac qui
    restaure ce regime: une passe porte a la fois des planches et une feuille de
    calibration, alors qu'un profil est **designe**. Les deux moities
    d'`EPIC5-ARB-107` s'y verifient ensemble:

    1. **la feuille se consigne** -- un profil est cree pour elle, exactement
       celui que `scan ... calibrate` produirait ;
    2. **elle ne s'applique pas** -- aucun lot n'est corrige par elle du seul fait
       qu'elle etait dans la pile. La correction vient du profil **designe**
       (`EPIC5-ARB-83`), et le profil qui vient d'etre cree n'est designe par
       rien.

    Les deux profils portent des coefficients **distinguables** -- ils sont
    ajustes sur deux presses differentes --, sans quoi « c'est bien le bon qui
    s'est applique » n'est pas mesurable.
    """
    project_dir = tmp_path / "projet-priorite"
    # Le profil DESIGNE: ajuste sur la presse du tirage, dans une passe separee.
    assert _calibrate_chain(project_dir, tmp_path) == 0
    designe = _profil_de(project_dir)
    avant = json.loads(Path(designe).read_text(encoding="utf-8"))

    # La passe de vrac: deux planches **et** une feuille de calibration d'une
    # AUTRE chaine, posee au milieu (ni premiere, ni derniere).
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    feuille = app.page_de_calibration_autonome(
        scan_chain_label="epson v600 tiff 300 dpi")
    folder = app.write_scan_folder(tmp_path / "vrac", [
        (payloads[0], app.PRESSES_DU_TIRAGE[0]),
        (feuille, couleur._DEVIANT_PRESS),
        (payloads[1], app.PRESSES_DU_TIRAGE[1])])

    assert app.run_scan(project_dir, folder, cli.PROFILE_FLAG, designe) == 0

    # 1. Un second profil a ete **cree**, distinct du premier.
    profils = _profiles_in(project_dir)
    assert len(profils) == 2, [chemin.name for chemin in profils]
    cree = next(chemin for chemin in profils if str(chemin) != designe)
    apres = json.loads(Path(designe).read_text(encoding="utf-8"))
    assert apres == avant, "le profil designe n'a pas ete touche"
    # Les coefficients des deux profils **different**: sans cela, « c'est bien le
    # bon qui s'est applique » ne voudrait rien dire. La comparaison se fait cle
    # par cle -- un `!=` sur deux dictionnaires de tableaux est ambigu, et deux
    # suites comparees par `zip` tronqueraient sur la plus courte.
    gauche = _coefficients(cc.chain_correction_from_document(avant).profile)
    droite = _coefficients(cc.chain_correction_from_document(
        json.loads(cree.read_text(encoding="utf-8"))).profile)
    assert set(gauche) == set(droite)
    assert any(not np.allclose(gauche[cle], droite[cle]) for cle in gauche), (
        "les deux profils ont les memes coefficients: le test ne mesure rien")

    # 2. Le lot est corrige par le profil **designe**, jamais par la feuille trouvee.
    entrees = app.calibration_entries(app.manifest_of(project_dir))
    assert set(entrees) == {0, 1}, entrees
    for entree in entrees.values():
        assert entree["correction_source"] == cc.CORRECTION_SOURCE_CHAIN_PROFILE, entree
        assert entree["correction_chain_id"] == avant["chain_id"], entree
        assert entree["correction_source_page_id"] == avant["source_page_id"], entree

    # 3. Le defaut de profil du projet est **inchange**: creer n'est pas designer.
    couleur_projet = app.manifest_of(project_dir).get("color") or {}
    assert not couleur_projet.get("default_calibration_profile"), couleur_projet


# ---------------------------------------------------------------------------
# AC 6 -- divergence: avertir et proposer, jamais un repli automatique
# ---------------------------------------------------------------------------


def test_une_planche_deviante_est_corrigee_et_son_ecart_reste_chiffre_au_manifest(
        tmp_path: Path) -> None:
    """AC 3 de 5.23: l'ecart est mesure et publie, il ne retire plus rien a la planche.

    **AMENDE PAR LA STORY 5.23** (`EPIC5-ARB-82` decision 1). La redaction de 5.22
    exigeait `not_applied` avec un motif sous `not_applied_reason`, c'est-a-dire le
    regime qui, mesure sur le lot reel `chendj-mat` le 2026-08-17, faisait sortir les
    deux planches d'Egan non corrigees pour un exces de +2,13 et +2,50 dE76.

    Ce que le test verifie n'a pas ete affaibli, il a ete deplace d'un cran vers la
    mesure: l'ecart est toujours **chiffre au manifest avec le seuil du registre**, et
    les deux cles d'absence de correction sont desormais absentes toutes les deux --
    `failure_reason` comme avant, `not_applied_reason` en plus.
    """
    project_dir = tmp_path / "projet-deviant"
    assert _calibrate_chain(project_dir, tmp_path) == 0
    folder = tmp_path / "deviant"
    _write_lot_deviant(folder)
    assert app.run_scan(project_dir, folder, *_designe(project_dir)) == 0
    document = app.manifest_of(project_dir)
    entrees = app.calibration_entries(document)

    deviantes = [e for e in entrees.values()
                 if (e.get("divergence") or {}).get("diverges") is True]
    assert len(deviantes) == 1, entrees
    entree = deviantes[0]
    # Ni echec ni decision en attente: **les deux cles sont absentes**, et un lecteur
    # qui filtre sur la presence du champ ne compte donc cette planche dans aucune des
    # deux familles.
    assert "failure_reason" not in entree, entree
    assert "not_applied_reason" not in entree, entree
    assert entree["status"] == color_pipeline.APPLIED_STATUS
    # L'ecart est **chiffre** au manifest, avec le seuil du registre.
    divergence = entree["divergence"]
    assert divergence["excess_residual_de76"] > divergence["threshold_de76"]
    # Et une planche **non** deviante du meme lot est corrigee elle aussi: sans ce
    # volet, « corrigee » serait tenu par un code qui corrige tout sans rien mesurer.
    autres = [e for e in entrees.values()
              if (e.get("divergence") or {}).get("diverges") is False]
    assert autres and all(e["status"] == color_pipeline.APPLIED_STATUS for e in autres)


def test_le_geste_explicite_applique_le_profil_tel_quel_a_la_planche_deviante(
        tmp_path: Path) -> None:
    """AC 6: avec le drapeau, le profil est applique tel quel; rien n'est re-ajuste.

    Les deux volets sont mesures. Sans le second, une garde qui appliquerait
    toujours passerait le premier.
    """
    project_dir = tmp_path / "projet-bypass"
    assert _calibrate_chain(project_dir, tmp_path) == 0
    folder = tmp_path / "bypass"
    _write_lot_deviant(folder)
    assert app.run_scan(
        project_dir, folder, cc.DIVERGENCE_BYPASS_FLAG, *_designe(project_dir)) == 0
    entrees = app.calibration_entries(app.manifest_of(project_dir))
    contournees = [e for e in entrees.values()
                   if (e.get("divergence") or {}).get("bypassed")]
    assert len(contournees) == 1, entrees
    entree = contournees[0]
    assert entree["status"] == color_pipeline.APPLIED_STATUS, entree
    assert entree.get("not_applied_reason") is None, entree


def test_la_frontiere_de_divergence_est_stricte_au_seuil_du_registre(
        monkeypatch) -> None:
    """AC 6, frontiere: un exces **egal** au seuil ne diverge pas, au-dela si.

    **Reecrit le 2026-08-17 (revue, finding C3).** La premiere redaction
    construisait un `DivergenceAssessment` en calculant elle-meme
    `diverges=excess > seuil`, puis relisait le champ qu'elle venait de poser:
    elle mesurait sa propre comparaison et jamais celle de la production. Prouve
    inerte par injection du mutant `>` -> `>=` dans `assess_divergence` -- le test
    survivait, alors que le test herite `test_la_frontiere_du_seuil_est_stricte`
    de `test_calibration_page_source` mourait. La frontiere du seuil est de la
    classe **critique** de la politique de revue (constante centrale du calcul):
    zero survivant y est exige.

    La version ci-dessous traverse le vrai producteur (`calibrate_page` ->
    `assess_divergence`) sur une page deviante reelle.

    **AMENDE PAR LA STORY 5.23**: la bascule assertee n'est plus `applied` contre
    `not_applied` -- la divergence ne retire plus rien a une planche (`EPIC5-ARB-82`
    decision 1) --, c'est celle de `divergence.diverges` lui-meme, de part et d'autre
    du seuil substitue. Le mutant vise est le **meme** (`>` en `>=` dans
    `assess_divergence`) et il est desormais atteint plus directement: l'ancienne
    redaction passait par deux niveaux d'indirection, la garde puis la branche de
    refus, si bien qu'un mutant de la branche l'aurait tuee aussi -- elle ne prouvait
    donc pas a elle seule que la frontiere du seuil etait couverte.

    Le volet ajoute par la story et conserve ici: la planche est **corrigee des deux
    cotes** de la frontiere. C'est ce qui empeche un retour du refus de passer.

    Le seuil n'est jamais ecrit (`EPIC5-ARB-52`): il est **pose a l'exces mesure**
    par le producteur lui-meme, ce qui est la seule facon de construire l'egalite
    exacte -- de mesure nulle sur des flottants -- et donc le seul point ou `>` et
    `>=` different. Les autres champs de l'entree de registre substituee sont
    repris de l'entree reelle, pour ne pas fabriquer une garde qui n'existe pas.
    """
    profil = couleur._calibration_profile()
    deviante = _synthetic_rectified_page(
        template_id=couleur.TEMPLATE, preset_id=couleur.PRESET,
        distort=couleur._DEVIANT_PRESS)
    arguments = dict(
        template_id=couleur.TEMPLATE, patch_preset_id=couleur.PRESET, dpi=600,
        page_id="planche-2", imported_profile=profil,
        imported_source_page_id="calibration-0",
        # **Le regime de cette story**: la correction vient du profil de la chaine,
        # pas d'une page de calibration du lot.
        imported_correction_source=cc.CORRECTION_SOURCE_CHAIN_PROFILE,
        imported_chain_id="chaine-egan")

    au_dela = cc.calibrate_page(deviante, **arguments)
    exces = au_dela.divergence.excess_residual_de76
    assert au_dela.divergence.diverges is True
    # Au-dela du seuil, la planche est **corrigee**: c'est la bascule de la story 5.23.
    assert au_dela.status == color_pipeline.APPLIED_STATUS
    assert au_dela.not_applied_reason is None, au_dela
    assert au_dela.failure_reason is None, au_dela
    assert au_dela.profile is profil, (
        "le profil de la chaine est applique tel quel malgre la divergence")

    reference = cc.get_divergence_guard(cc.ACTIVE_DIVERGENCE_GUARD_ID)
    au_seuil_exact = color_metrics.DivergenceGuard(
        divergence_id=reference.divergence_id,
        max_excess_residual_de76=exces,
        null_distribution_max_de76=reference.null_distribution_max_de76,
        null_distribution_pairs=reference.null_distribution_pairs,
        reservations=reference.reservations)
    monkeypatch.setattr(
        color_metrics, "DIVERGENCE_REGISTRY",
        MappingProxyType({reference.divergence_id: au_seuil_exact}))

    au_bord = cc.calibrate_page(deviante, **arguments)
    # Meme entree, meme mesure: sans cette egalite, l'exces aurait derive et le
    # « exactement au seuil » ci-dessous ne serait pas celui qu'on croit exercer.
    assert au_bord.divergence.excess_residual_de76 == exces
    assert au_bord.divergence.threshold_de76 == exces
    # **Le mutant `>` -> `>=` meurt ici**: sous lui, un exces egal au seuil diverge, et
    # cette assertion tombe. C'est la seule des quatre qui le tue, les trois suivantes
    # etant desormais vraies des deux cotes de la frontiere -- elles sont conservees
    # parce qu'elles disent l'autre moitie de la story: la correction s'applique quel
    # que soit le verdict.
    assert au_bord.divergence.diverges is False, au_bord.divergence
    assert au_bord.not_applied_reason is None, au_bord
    assert au_bord.status == color_pipeline.APPLIED_STATUS, au_bord
    assert au_bord.profile is profil, (
        "le profil de la chaine est applique **tel quel**: rien n'est re-ajuste")


def test_dans_le_regime_de_chaine_l_ecart_brut_est_declare_non_mesure_et_non_nul(
        tmp_path) -> None:
    """**Ce test remplace `test_le_message_de_divergence_dit_que_les_frames_sont_ecrites`.**

    L'ancien portait sur `divergence_warning_message`, retiree par la story 5.23 avec la
    branche de refus qui etait son seul producteur. Ses deux proprietes ont demenage:
    l'interdit de vocabulaire est desormais celui de `raw_divergence_warning_message` et
    vit dans `test_divergence_par_defaut.py`; l'interdit sur la **ligne complete du
    journal** vit dans le test suivant, ou il a toujours vecu.

    Ce qui est verifie a la place est propre a **ce** fichier, c'est-a-dire au regime
    nominal depuis 5.22: quand la correction vient du profil de la chaine, la feuille de
    calibration n'est pas dans le scan, donc l'ecart brut a brut de l'AC 2 n'est pas
    calculable. Le manifest doit le **declarer** -- et surtout ne pas publier un ecart de
    zero, qui est la lecture de deux feuilles identiques et serait donc le meilleur
    verdict possible la ou rien n'a ete mesure.

    **Amende le 2026-08-19 (`EPIC5-ARB-104`), et c'est la mesure de bout en bout du
    correctif.** Le motif attendu etait `raw_divergence_no_calibration_sheet`, c'est-a-dire
    « aucune feuille de calibration »; il est desormais
    `raw_divergence_witness_band_not_printed`, c'est-a-dire « la feuille a bien ete lue,
    son bandeau de temoins n'etait pas imprime ». La feuille de cette fixture **a** ete
    scannee et calibree deux lignes plus haut (`_calibrate_chain`): l'ancien motif etait
    donc faux, et c'est exactement la faussete que la revue a trouvee -- le profil ne
    transportait pas le motif du bandeau, donc l'appelant ne pouvait que se rabattre sur
    le motif generique.

    La propriete que ce test porte, elle, ne bouge pas d'un cran: l'ecart n'est **pas**
    mesure et ne se publie **pas** a zero. Ce qui change est ce que l'operateur apprend
    de la raison -- et les deux raisons appellent deux gestes opposes: reimprimer la page
    avec son bandeau, contre chercher une feuille qui manque.
    """
    project_dir = tmp_path / "projet"
    assert _calibrate_chain(project_dir, tmp_path) == 0
    folder, _payloads = _lot_deviant_et_planche_en_panne(tmp_path, name="lot-brut")
    assert app.run_scan(project_dir, folder, *_designe(project_dir)) == 0

    entrees = app.calibration_entries(app.manifest_of(project_dir))
    mesurables = [e for e in entrees.values() if "raw_divergence" in e]
    assert mesurables, entrees
    for entree in mesurables:
        brut = entree["raw_divergence"]
        assert brut["mean_raw_de76"] is None, brut
        assert brut["exceeds"] is None, brut
        # **Le motif du bandeau, transporte par le profil** (`EPIC5-ARB-104`). Ecrit en
        # litteral et non lu sur `RAW_DIVERGENCE_BAND_REASONS`: une assertion qui
        # passerait par la constante resterait vraie apres le mutant qui renomme le
        # vocabulaire, alors que tous les manifests deja ecrits porteraient l'ancien mot.
        assert brut["reason"] == "raw_divergence_witness_band_not_printed", brut
        # Et il n'est **pas** le motif generique: c'est tout l'objet du correctif. La
        # feuille de cette fixture a ete lue, elle ne manque pas.
        assert brut["reason"] != cc.RAW_DIVERGENCE_NO_CALIBRATION_SHEET, brut
        # Le seuil est porte quand meme: il vient du registre et ne depend pas de la
        # reussite de la mesure.
        assert brut["guard_id"] == color_metrics.ACTIVE_RAW_DIVERGENCE_GUARD_ID
        assert brut["threshold_de76"] == color_metrics.get_raw_divergence_guard(
            color_metrics.ACTIVE_RAW_DIVERGENCE_GUARD_ID).max_mean_raw_de76


def _lot_deviant_et_planche_en_panne(tmp_path: Path, *, name: str):
    """Un lot de **trois** planches distinguables, chacune dans un regime different.

    Regle des fabriques, et les trois regimes sont necessaires ensemble: la nominale
    (corrigee) rend les deux autres non vides, la **deviante** est livree non
    corrigee -- et elle n'est **pas en premiere position** --, et la troisieme est en
    **vrai echec** (monochrome, `FAILURE_NOT_THREE_CHANNELS`), donc le seul regime ou
    le mot « refusee » est vrai. Sans cette derniere, un correctif qui supprimerait le
    mot partout passerait.

    Aucune page de calibration dans la pile: c'est le regime nominal de la story, la
    correction vient du profil de la chaine.
    """
    payloads = app.lot_payloads(sheet_count=3, with_calibration=False)
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    presses = (app.PRESSES_DU_TIRAGE[0], couleur._DEVIANT_PRESS,
               app.PRESSES_DU_TIRAGE[1])
    for rang, (payload, press) in enumerate(zip(payloads, presses), start=1):
        raster = app.build_page(payload, press=press)
        if rang == 3:
            # Monochrome: entree licite a l'ingestion, refusee par un motif du
            # vocabulaire ferme au moment de calibrer. C'est un **echec**, pas une
            # decision en attente.
            raster = cv2.cvtColor(raster, cv2.COLOR_BGR2GRAY)
        cv2.imwrite(str(folder / f"page_{rang:02d}.tiff"), raster)
    return folder, payloads


def _lignes_de_page(journal: str, page_index: int) -> list[str]:
    """Toutes les lignes du journal qui parlent de **cette** page, telles qu'elles sortent.

    **Rendait une ligne unique avant la story 5.23**, sur un `assert len(lignes) == 1`.
    Ce cardinal est devenu faux dans les deux sens: une planche corrigee sans
    avertissement n'a plus **aucune** ligne, et une planche qui declenche les
    avertissements chiffres de l'AC 4 et de l'AC 7 peut en avoir deux. Figer le cardinal
    aurait fait echouer le test pour une raison qui n'est pas la sienne -- il porte sur ce
    que les lignes **disent**, pas sur combien il y en a.
    """
    return [ligne for ligne in journal.splitlines()
            if f"Page {page_index} " in ligne]


def _ligne_de_page(journal: str, page_index: int) -> str:
    """La ligne unique du journal qui parle de cette page. Leve s'il n'y en a pas une."""
    lignes = _lignes_de_page(journal, page_index)
    assert len(lignes) == 1, (page_index, lignes)
    return lignes[0]


def test_le_journal_ne_dit_pas_refusee_d_une_planche_qu_il_livre(tmp_path) -> None:
    """AC 6 et 7: le mot interdit l'est sur le **message complet**, prefixe compris.

    **Trouve en revue le 2026-08-17 sur le terrain d'Egan** (`projects/chendj-mat`,
    scan `scan-WIN`), et c'est le seul defaut de ce lot que l'operateur voyait:
    `logs/scan.log` ecrivait « Page 1 refusee: [...] et les frames de celle-ci sont
    ecrites telles quelles ». Le prefixe contredisait la phrase qu'il introduisait, et
    c'est le prefixe qu'on lit en premier -- Egan repartait rescanner une feuille
    effectivement livree, c'est-a-dire exactement la panne que cette story existe pour
    supprimer.

    `test_le_message_de_divergence_dit_que_les_frames_sont_ecrites` posait deja
    l'interdit, mais sur le **fragment** rendu par `divergence_warning_message`: son
    enrobage le reintroduisait sans le contredire. Ce test-ci porte donc sur la ligne
    **telle qu'elle sort du journal**, qui est ce que l'operateur relit deux jours plus
    tard.

    Les deux regimes sont mesures dans le meme scan, sans quoi un correctif qui
    supprimerait le mot partout passerait: la planche corrigee ne dit pas « refusee », la
    planche en **echec** le dit toujours.

    **AMENDE PAR LA STORY 5.23.** La planche deviante n'est plus livree en brut, elle est
    **corrigee** (`EPIC5-ARB-82` decision 1), donc les assertions positives de l'ancienne
    redaction -- « livree non corrigee », le motif `NOT_APPLIED_PAGE_DIVERGES`, le geste
    explicite nomme -- decrivaient un regime qui n'existe plus. Ce qui reste, et qui est
    la raison d'etre du test, est **l'interdit sur la ligne complete du journal**: le mot
    que le fragment n'a jamais contenu ne doit pas revenir par l'enrobage. Il est meme
    plus fort qu'avant, parce qu'il porte desormais sur **toutes** les lignes de cette
    page, y compris zero: une planche corrigee sans rien de notable n'en a plus aucune.
    """
    project_dir = tmp_path / "projet"
    assert _calibrate_chain(project_dir, tmp_path) == 0
    folder, payloads = _lot_deviant_et_planche_en_panne(tmp_path, name="lot-mixte")
    assert app.run_scan(project_dir, folder, *_designe(project_dir)) == 0

    journal = _journal_de_scan(project_dir)
    entrees = app.calibration_entries(app.manifest_of(project_dir))
    deviante = next(index for index, entree in entrees.items()
                    if (entree.get("divergence") or {}).get("diverges") is True)
    en_panne = next(index for index, entree in entrees.items()
                    if entree.get("failure_reason") is not None)
    # La deviante n'est pas la premiere planche du lot: un message pose sur « la
    # premiere page » se demasquerait ici.
    assert deviante != min(entrees), entrees
    # Et elle est bien corrigee: sans ce volet, l'interdit ci-dessous serait tenu par une
    # page dont le journal ne parle pas parce qu'elle a echoue autrement.
    assert entrees[deviante]["status"] == color_pipeline.APPLIED_STATUS, entrees[deviante]

    # **L'interdit, sur toutes les lignes completes de cette page.** Il porte sur la
    # racine et non sur la seule forme « refusee »: « refus », « refuse », « refusees »
    # diraient la meme chose fausse a l'operateur. Aucun mot de reglage non plus
    # (frontiere negative de l'AC 16 de 5.16, conservee a l'enrobage).
    for livree in _lignes_de_page(journal, deviante):
        assert "refus" not in livree.lower(), livree
        for interdit in ("seuil", "tolerance"):
            assert interdit not in livree.lower(), (interdit, livree)

    # **Et le lot est vrai**: les frames de cette planche sont sur le disque.
    frames = app.written_frames(project_dir, app.manifest_of(project_dir))
    assert len(frames) == sum(len(p["slots"]) for p in payloads)

    # **Temoin positif**: une planche reellement en echec garde le mot, parce qu'il y
    # est vrai et que le geste attendu est bien le rescan.
    refusee = _ligne_de_page(journal, en_panne)
    assert "refusee" in refusee.lower(), refusee
    assert entrees[en_panne]["failure_reason"] in refusee, refusee


# ---------------------------------------------------------------------------
# AC 9 -- le contrat de donnees de la previz, fige et teste sur les deux regimes
# ---------------------------------------------------------------------------

#: **Le contrat de donnees de la previz d'acceptation** (AC 9), fige ici parce que la
#: previz visuelle est differee a la GUI (5.8 / Epic 7) et que rien ne consommera ces
#: champs avant elle. Sans un test qui les epingle, un champ pourrait disparaitre entre
#: cette story et la GUI sans que rien ne le signale -- et la GUI decouvrirait le trou.
#:
#: Les quatre familles que l'AC nomme -- profil, brut, corrige, divergence -- se lisent
#: dans ces cles: la **provenance** dit avec quoi la planche a ete corrigee (donc quel
#: fichier de profil relire), la **distorsion** dit ce que la correction a deforme (le
#: couple brut/corrige), et le bloc de **divergence** dit de combien la planche s'ecarte
#: de sa source.
CONTRAT_PREVIZ_PROVENANCE = (
    "correction_source", "correction_source_page_id", "correction_form_id")
CONTRAT_PREVIZ_DIVERGENCE = (
    "guard_id", "diverges", "excess_residual_de76", "imported_residual_de76",
    "own_residual_de76", "threshold_de76", "bypassed")

#: **Le second bloc de divergence, ajoute par la story 5.23** (`EPIC5-ARB-82`). Il
#: repond a une question que le premier ne pose pas -- « ces deux feuilles imprimees se
#: comportent-elles pareil ? » -- et il y repond **sans profil**, sur les mesures brutes
#: des memes pastilles temoins. La previz doit pouvoir lire les deux: le premier dit a
#: quel point la correction d'une feuille est sous-optimale pour l'autre, le second de
#: combien les deux feuilles different avant toute correction.
#:
#: `mean_raw_de76` et `exceeds` sont exclus de la verification `is not None` du test:
#: ils valent legitimement `None` dans le regime nominal de cette story-la, ou la feuille
#: de calibration n'est pas dans le scan. C'est `reason` qui dit alors pourquoi.
CONTRAT_PREVIZ_DIVERGENCE_BRUTE = (
    "guard_id", "threshold_de76", "mean_raw_de76", "exceeds", "paired_value_ids",
    "excluded")


def _entrees_par_regime(tmp_path: Path) -> tuple[dict, dict]:
    """Une planche **non deviante** et une **deviante**, du meme lot, du meme scan.

    Les deux regimes sortent de la **meme** passe: un test qui les obtiendrait de deux
    scans differents ne prouverait pas que le contrat est le meme des deux cotes.
    """
    project_dir = tmp_path / "projet-contrat"
    assert _calibrate_chain(project_dir, tmp_path) == 0
    folder = tmp_path / "contrat"
    _write_lot_deviant(folder)
    assert app.run_scan(project_dir, folder, *_designe(project_dir)) == 0
    entrees = app.calibration_entries(app.manifest_of(project_dir))
    deviantes = [e for e in entrees.values()
                 if (e.get("divergence") or {}).get("diverges") is True]
    calmes = [e for e in entrees.values()
              if (e.get("divergence") or {}).get("diverges") is False]
    assert len(deviantes) == 1 and len(calmes) == 1, entrees
    return calmes[0], deviantes[0]


def test_le_contrat_de_donnees_de_la_previz_est_tenu_dans_les_deux_regimes(
        tmp_path: Path) -> None:
    """AC 9: les memes cles, presentes et renseignees, avec et sans divergence.

    C'est la propriete que l'AC 10 de 5.16 avait deja etablie pour la provenance et que
    cette story etend au bloc de divergence: **un champ absent d'un des deux regimes ne
    distingue rien** -- il faut alors deviner, et deviner sur un manifest est ce que ce
    projet refuse partout ailleurs.
    """
    calme, deviante = _entrees_par_regime(tmp_path)
    for entree in (calme, deviante):
        for cle in CONTRAT_PREVIZ_PROVENANCE:
            assert entree.get(cle), (cle, entree)
        assert entree["correction_source"] == cc.CORRECTION_SOURCE_CHAIN_PROFILE
        # La chaine: c'est **elle** qui permet a la previz de relire le profil applique.
        assert entree["correction_chain_id"], entree
        divergence = entree["divergence"]
        for cle in CONTRAT_PREVIZ_DIVERGENCE:
            assert cle in divergence, (cle, divergence)
            assert divergence[cle] is not None, (cle, divergence)
    # Et les deux regimes portent des **valeurs differentes** la ou c'est leur objet:
    # des cles presentes des deux cotes avec la meme valeur ne distingueraient rien.
    assert calme["divergence"]["diverges"] is False
    assert deviante["divergence"]["diverges"] is True
    # **AMENDE PAR LA STORY 5.23**: le statut ne distingue plus les deux regimes, la
    # divergence ne retirant plus rien a une planche (`EPIC5-ARB-82` decision 1). Le
    # contrat de donnees de la previz, lui, est **intact et elargi**: c'est le bloc de
    # divergence qui porte la distinction, et il la porte toujours -- plus un second bloc,
    # `raw_divergence`, que la previz doit pouvoir lire pour dire « ces deux feuilles se
    # comportent-elles pareil ? » sans passer par un profil ajuste.
    assert calme["status"] == color_pipeline.APPLIED_STATUS
    assert deviante["status"] == color_pipeline.APPLIED_STATUS
    for entree in (calme, deviante):
        brut = entree["raw_divergence"]
        for cle in CONTRAT_PREVIZ_DIVERGENCE_BRUTE:
            assert cle in brut, (cle, brut)


def test_une_chaine_qui_n_a_rien_corrige_ne_s_inscrit_pas_au_projet(
        tmp_path: Path) -> None:
    """Frontiere negative: le champ dit « a corrige », pas « a ete resolu ».

    Un profil charge dont **aucune** planche n'a ete corrigee n'a rien corrige. L'y
    inscrire ferait croire, a la relecture, que ce projet porte des masters corriges par
    cette chaine -- le faux succes que ce depot refuse.
    """
    from mixed_media_utility.io import scan_manifest as sm

    project_dir = tmp_path / "projet"
    assert _calibrate_chain(project_dir, tmp_path) == 0
    folder = tmp_path / "lot"
    _write_images_lot(folder)
    # `--cc off`: le profil est resolu, la correction mesuree, et posee sur aucun pixel.
    assert app.run_scan(
        project_dir, folder, cli.CC_FLAG, cli.CC_OFF, *_designe(project_dir)) == 0
    document = app.manifest_of(project_dir)
    assert sm.CALIBRATION_CHAINS_KEY not in document["color"], document["color"]
    assert document["color"]["color_calibration_status"] == (
        color_pipeline.NOT_APPLIED_STATUS)

    # Temoin positif sur la **meme** fabrique: sans le drapeau, la chaine s'inscrit.
    assert app.run_scan(
        project_dir, folder, "--overwrite", *_designe(project_dir)) == 0
    document = app.manifest_of(project_dir)
    assert document["color"][sm.CALIBRATION_CHAINS_KEY], document["color"]


# ---------------------------------------------------------------------------
# AC 10 -- frontiere de perimetre: la story ne touche que ce qu'elle declare
# ---------------------------------------------------------------------------

#: Les fichiers de **production** que la story 5.22 modifie, et rien d'autre. Chacun
#: porte sa raison, parce qu'une enumeration sans motif redevient une liste de souhaits:
#:
#: * `scan_chain.py` (neuf) -- l'identite de chaine et la derive du `chain_id`;
#: * `io/calibration_profile.py` (neuf) -- le format de fichier de profil, **pur**;
#: * `io/__init__.py` -- l'export du module neuf;
#: * `io/project_layout.py` -- le sous-dossier `versions/`, ajout additif;
#: * `io/naming.py` -- le nom du PDF de page de calibration, distinct de `_planches`;
#: * `color_calibration.py` -- serialisation/relecture de profil, provenance de chaine,
#:   et la bascule de la divergence du refus vers l'avertissement;
#: * `color_pipeline.py` -- le septieme cas du statut de lot (aucune planche corrigee
#:   **sans** qu'un echec ait eu lieu);
#: * `io/scan_manifest.py` -- les chaines consignees a la section `color` du projet;
#: * `pdf_composition.py` -- retrait de l'insertion automatique, composition a la demande;
#: * `cli.py` -- `scan calibrate`, `makepdf ... calibration-page`, resolution chaine ->
#:   profil, et les deux options de chaine.
#:
#: **`scan_output_frames.py` n'y est pas**, et son absence est une mesure: les Dev Notes
#: l'annoncaient « si besoin », et il ne l'a pas ete -- `page_profiles=()` exprimait deja
#: le regime brut. L'enumeration etant **exacte**, l'y laisser par prudence ferait
#: echouer ce test.
_FICHIERS_DE_PRODUCTION_5_22 = frozenset({
    "src/mixed_media_utility/cli.py",
    "src/mixed_media_utility/color_calibration.py",
    "src/mixed_media_utility/color_pipeline.py",
    "src/mixed_media_utility/io/__init__.py",
    "src/mixed_media_utility/io/calibration_profile.py",
    "src/mixed_media_utility/io/naming.py",
    "src/mixed_media_utility/io/project_layout.py",
    "src/mixed_media_utility/io/scan_manifest.py",
    "src/mixed_media_utility/pdf_composition.py",
    "src/mixed_media_utility/scan_chain.py",
})

#: Borne basse: le `baseline_commit` de la story, tel que son frontmatter le porte.
_BASELINE_5_22 = "a5390b3"

#: Borne haute: le dernier commit de 5.22, qui est aussi le `baseline_commit` de 5.23 --
#: donc le point exact ou le perimetre de cette story-ci s'arrete et ou celui de la
#: suivante commence. Epingle plutot que `HEAD` pour le motif ecrit sous
#: `_diff_de_production`.
_FIN_5_22 = "ae6ac2f"


def _git_disponible() -> None:
    """Echouer si `git` manque -- **jamais** un skip, qui se lirait comme un vert."""
    import shutil
    if shutil.which("git") is None:
        pytest.fail(
            "git absent: la frontiere de perimetre ne s'evalue pas, et un skip se "
            "lirait comme un vert dans le total")


def _diff_de_production() -> list[str]:
    """Fichiers de production modifies par la story, ou echec nomme.

    **La borne haute etait `HEAD` et elle est desormais epinglee a la fin de 5.22**
    (`ae6ac2f`, qui est le `baseline_commit` de la story 5.23). La redaction `HEAD` etait
    juste **pendant que 5.22 etait ouverte**: elle obligeait tout elargissement ulterieur
    a passer par cette enumeration. Elle a cesse de l'etre le jour ou une **autre** story
    a commence a travailler sur la meme branche -- des le premier commit de 5.23, ce test
    a echoue en accusant `patch_presets.py`, `patch_values.py`, `page_templates.py` et
    `color_metrics.py` d'etre « en trop » dans le perimetre de 5.22, alors qu'ils sont
    exactement dans celui de 5.23.

    Une frontiere qui echoue pour le perimetre d'une autre story ne mesure plus rien: elle
    se lit comme un faux positif permanent, donc elle se desapprend. Chaque story epingle
    donc desormais **ses deux bornes**, et celle de 5.23 vit dans son propre fichier
    (`test_divergence_par_defaut.py`), avec son propre baseline.
    """
    import subprocess
    try:
        return subprocess.run(
            ["git", "diff", "--name-only", _BASELINE_5_22, _FIN_5_22, "--", "src"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=60,
        ).stdout.split()
    except (subprocess.SubprocessError, OSError) as error:
        echoue_ou_saute(
            REPO_ROOT, _BASELINE_5_22,
            f"commit de reference {_BASELINE_5_22} inatteignable ({error}): la frontiere "
            "de perimetre ne s'evalue pas, et un skip se lirait comme un vert. Arbre "
            "exporte, historique tronque ou clone superficiel (`git fetch --unshallow`)")


def test_la_story_ne_touche_aucun_module_de_production_hors_de_son_perimetre() -> None:
    """AC 10, frontiere de perimetre sur le diff de production isole (style 5.19).

    Un module de production qui apparaitrait ici sans figurer dans l'enumeration serait
    un elargissement de scope -- ce que `CLAUDE.md` interdit explicitement -- et il
    faudrait alors soit le retirer, soit l'inscrire **avec sa raison**, ce qui en fait une
    decision lisible plutot qu'un accident.
    """
    _git_disponible()
    touches = _diff_de_production()
    assert touches, (
        "aucun fichier de production modifie depuis le baseline: la frontiere ne "
        "mesurerait rien")
    assert set(touches) == set(_FICHIERS_DE_PRODUCTION_5_22), {
        "en trop": sorted(set(touches) - _FICHIERS_DE_PRODUCTION_5_22),
        "annonces et non touches": sorted(_FICHIERS_DE_PRODUCTION_5_22 - set(touches)),
    }


def test_la_frontiere_de_perimetre_mord_dans_les_deux_sens() -> None:
    """Le second volet: la frontiere **echoue** quand elle doit.

    Une comparaison d'ensembles devenue une inclusion, ou dont le membre de gauche serait
    vide, passerait le test precedent sans rien garantir -- c'est le motif « un test peut
    etre vert et vide » que ce depot a paye trois fois. Les deux directions sont exercees,
    parce qu'une egalite remplacee par une inclusion ne se voit que d'un cote a la fois.
    """
    declares = set(_FICHIERS_DE_PRODUCTION_5_22)
    assert declares | {"src/mixed_media_utility/encode.py"} != declares, (
        "un fichier en trop doit faire echouer la comparaison")
    assert declares - {"src/mixed_media_utility/scan_chain.py"} != declares, (
        "un fichier annonce et non touche doit faire echouer la comparaison aussi")
    # Et le diff reel est bien ce qui est confronte, pas un ensemble vide.
    _git_disponible()
    touches = _diff_de_production()
    assert touches and all(chemin.startswith("src/") for chemin in touches), touches
