"""Story 5.23, tache 10 (AC 12): **l'operateur designe le profil, la machine ne le
devine plus**.

Mandat: `EPIC5-ARB-83`, elargi a cette story par `EPIC5-ARB-89`.

Ce que cette suite mesure, et qu'aucune autre ne mesurait: le profil applique a un lot
est celui que l'operateur **designe** -- par `--profil` sur le scan, ou a defaut par le
profil pose au projet avec une commande dediee --, et **plus aucun chemin de code ne
compare un `chain_id`** pour en choisir un.

Pourquoi c'est une suppression et non un correctif. La derivation automatique de
l'identite de chaine est **mesuree defaillante sur le materiel d'Egan**: les tags
scanner y sont absents, donc deux scanners physiquement differents rendaient tous les
deux `600-tiff-e2168f9b2b81`. Le mauvais profil s'appliquait en silence, et aucun
raffinement ne ferme ce trou -- les tags n'existent pas. Quand l'operateur designe, le
defaut **cesse d'etre possible**.

Le piege central de l'AC, celui contre lequel la moitie de ce fichier est ecrite: un
**repli automatique** quand rien n'est designe. Se rabattre sur « le seul profil du
projet », ou sur « le premier de `versions/calibration/` », reintroduirait exactement le
defaut supprime, sous une forme plus difficile a voir que la derivation -- elle, au
moins, etait ecrite quelque part. Le comportement voulu est un **avertissement** et un
lot livre **brut** (Egan, note 8: « Oui bon comportement. Avertissement. »).

Regle des fabriques (CLAUDE.md), appliquee partout ou une collection est manipulee:

* les projets vont par **trois**, distinguables par leur `project_id`, et la cible
  n'est jamais le premier;
* les profils vont par **trois**, distinguables **au coefficient pres** (trois presses),
  et le profil vise n'est jamais le premier -- ni dans l'ordre d'ecriture, ni dans
  l'ordre alphabetique du dossier `versions/calibration/`;
* les mesures portent sur les **coefficients** appliques, jamais sur la presence d'un
  champ (`EPIC5-ARB-39`).

AC 9: ce fichier ne synthetise **aucun** raster de scan et ne passe par aucune
ingestion. Les trois etages qu'il exerce -- la designation, la resolution, la commande
dediee -- se testent a l'unite, et le cout d'une campagne de mutation sur eux doit
rester payable.
"""

from __future__ import annotations

import ast
import inspect
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import cli  # noqa: E402
from mixed_media_utility import color_calibration as cc  # noqa: E402
from mixed_media_utility.io import calibration_profile  # noqa: E402
from mixed_media_utility.io import extraction_manifest  # noqa: E402
from mixed_media_utility.io import profile_designation as designation  # noqa: E402
from mixed_media_utility.io import project_layout  # noqa: E402

import test_calibration_page_source as couleur  # noqa: E402


# ---------------------------------------------------------------------------
# Fabriques -- trois de tout, cible jamais en premiere position
# ---------------------------------------------------------------------------

#: Trois presses **deux a deux distinctes**, donc trois jeux de coefficients distincts.
#: La troisieme est construite ici plutot que reprise d'une constante existante, parce
#: qu'il n'en existait que deux: reutiliser la premiere aurait rendu deux des trois
#: profils indiscernables, et un appariement permute entre ces deux-la serait reste
#: invisible. C'est la famille des mutants `M33` / `M25`, sept occurrences dans ce
#: depot, chacune trouvee par mutation et par aucun test.
#:
#: L'assertion `_les_trois_presses_sont_distinguables` en fait une propriete verifiee
#: plutot qu'une intention de commentaire.
_PRESSES = (
    couleur._NOMINAL_PRESS,
    couleur._DEVIANT_PRESS,
    couleur._press(0.960, (0.0200, 0.0310, 0.0180)),
)

#: Trois identites de chaine, **volontairement pas dans l'ordre alphabetique de leur
#: rang**: la cible usuelle des tests (`_CHAINES[1]`) est la derniere du dossier une
#: fois trie, et la premiere ecrite ne l'est jamais. Une resolution qui prendrait « le
#: premier fichier de `versions/calibration/` » ou « le premier ecrit » se demasque.
_CHAINES = ("chaine-alpha", "chaine-zeta", "chaine-mu")


def test_les_trois_presses_sont_distinguables() -> None:
    """La fabrique tient sa promesse: trois profils **deux a deux** differents.

    Sans ce garde-fou, tous les temoins negatifs de ce fichier seraient verts sur des
    profils identiques -- exactement le defaut que la regle des fabriques existe pour
    empecher, et qui a coute trois stories dans ce depot.
    """
    documents = [_document(chaine, presse)
                 for chaine, presse in zip(_CHAINES, _PRESSES)]
    coefficients = [json.dumps(document["coefficients"], sort_keys=True)
                    for document in documents]
    assert len(set(coefficients)) == 3, coefficients


def _document(chain_id: str, press) -> dict:
    """Un document de profil valide, ajuste par les **vrais** producteurs.

    `press` est un parametre et non une constante: c'est ce qui rend deux profils
    distinguables au coefficient pres.
    """
    profil = couleur._calibration_profile(press=press)
    return cc.profile_to_document(
        profil, chain_id=chain_id, source_page_id=f"{chain_id}-p0",
        template_id=couleur.TEMPLATE, read_patch_count=18, retained_patch_count=18,
        ink_floor_excluded=cc.correction_form_excludes_ink_floor(profil.correction_id))


def _fichier_externe(dossier: Path, chain_id: str, press) -> tuple[Path, dict]:
    """Un profil pose **hors de tout projet**: un fichier autonome, et rien d'autre.

    C'est la forme dans laquelle un profil voyage (`EPIC5-ARB-83`, decision 4): il porte
    son identite, sa forme de correction et ses coefficients, et se suffit.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    document = _document(chain_id, press)
    chemin = dossier / f"{chain_id}.json"
    chemin.write_text(calibration_profile.serialize_profile(document), encoding="utf-8")
    return chemin, document


def _trois_profils_externes(tmp_path: Path) -> list[tuple[Path, dict]]:
    """Trois profils autonomes, distinguables, dans trois dossiers distincts.

    Trois dossiers et non un seul: un profil designe peut venir de n'importe ou, et
    les grouper ferait ressembler leur dossier commun a un registre -- donc a quelque
    chose qu'un repli pourrait balayer.
    """
    return [_fichier_externe(tmp_path / f"ailleurs-{rang}", chaine, presse)
            for rang, (chaine, presse) in enumerate(zip(_CHAINES, _PRESSES))]


#: Squelette de `project.json` **valide au schema v2**, reduit au minimum qui passe la
#: validation: l'ecriture atomique valide son temporaire avant la bascule, donc un
#: manifest bricole ne serait pas ecrit du tout et le test mesurerait le mauvais refus.
_LOT_TEMOIN = {
    "expected_frame_count": 20,
    "first_frame_timecode": "01:01:42:05",
    "fps_target": 25.0,
    "fps_target_exact": "25/1",
    "frame_timecodes_digest": (
        "sha256-v1:2491dd7fc618e3bea6bf10eb4195eea266e74c5bec73ec2c62b517397"
        "eabc519"),
    "frames_dir": "frames/rush-temoin_25-7f152a04",
    "gamut_map_id": "gamut-map-none-1",
    "last_frame_timecode": "01:01:42:24",
    "lot_id": "rush-temoin_25-7f152a04",
    "output_bit_depth": 16,
    "patch_preset_id": "patches-14-v3",
    "rounding_policy": "floor-index-ceil-count-v1",
    "rush_id": "rush-temoin",
    "selection_warnings": [],
    "source_frame_count": 106,
    "source_frame_count_is_exact": True,
    "source_in_timecode": "01:01:42:05",
    "source_out_timecode": "01:01:42:24",
    "source_tail_frames": 18,
    "state": "extraction",
    "template_id": "tpl-a4-portrait-8f-v2",
    "timecode_base": "source",
    "timecode_base_fps": "25/1",
}


def _projet(racine: Path, project_id: str, *, color: dict | None = None) -> Path:
    """Un projet **reel** avec son `project.json` valide, nomme par `project_id`.

    Le nom est un parametre parce que les tests de frontiere ont besoin de projets
    **distinguables**: « aucun refus lie au projet » ne se mesure qu'entre projets qu'on
    peut nommer separement.
    """
    project_dir = racine / project_id
    project_layout.ensure_project_layout(project_dir)
    manifest = {
        "schema_version": "2.1",
        "project_id": project_id,
        "created": "2026-08-18T00:00:00Z",
        "artifacts": {"frames_dir": "frames", "outputs_dir": "outputs"},
        "color": dict(color or {}),
        "video": {},
        "reconstruction": {},
        "rushes": [{"rush_id": "rush-temoin", "source_path": "rushes/temoin.mov"}],
        "lots": [dict(_LOT_TEMOIN)],
    }
    (project_dir / extraction_manifest.MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return project_dir


def _trois_projets(tmp_path: Path) -> list[Path]:
    """Trois projets distinguables. La cible des tests n'est **jamais** le premier."""
    return [_projet(tmp_path / "projets", nom)
            for nom in ("projet-amont", "projet-aval", "projet-de-passage")]


def _logger(project_dir: Path) -> logging.Logger:
    project_layout.ensure_project_layout(project_dir)
    return cli._configure_scan_logger(project_dir)


def _journal(project_dir: Path) -> str:
    chemin = project_dir / project_layout.LOGS_DIRNAME / "scan.log"
    return chemin.read_text(encoding="utf-8") if chemin.is_file() else ""


def _entree_de_chaine(entrees, chain_id: str) -> dict | None:
    """L'entree du registre qui porte **cette** chaine, ou `None`. **Helper de test.**

    Il vivait en production sous le nom `find_registered_profile` jusqu'au 2026-08-19:
    un comparateur de `chain_id` **sans aucun appelant de production**, retire par
    `EPIC5-ARB-101`. Il descend ici parce que c'est le seul role qu'il ait jamais eu --
    permettre a un test de designer une entree dans une liste triee -- et l'y laisser
    en production, dans le module precis dont toute la doctrine est « aucun appariement
    par `chain_id` », etait une invitation a l'y reutiliser.
    """
    for entree in entrees:
        if entree.get("chain_id") == chain_id:
            return dict(entree)
    return None


def _color(project_dir: Path) -> dict:
    manifest = json.loads(
        (project_dir / extraction_manifest.MANIFEST_FILENAME).read_text(
            encoding="utf-8"))
    return manifest.get("color") or {}


#: Les defauts optionnels que ce banc **recopie**, nom et valeur, pour dire ce qu'une
#: relecture rend. Ils sont ecrits **en litteral** plutot que lus sur
#: `calibration_profile._OPTIONAL_DEFAULTS`: les lire sur la constante du code rendrait
#: toutes les assertions de relecture de ce fichier vertes quel que soit le defaut, y
#: compris `None`. C'est le defaut tautologique que la campagne de la story 5.9 a
#: trouve sur la constante centrale de la calibration, et il n'est pas rejoue ici.
#:
#: **Le prix de ce litteral est qu'il PERIME**, et il a peri: le 2026-09-07,
#: `EPIC11-ARB-262` a ajoute `scan_dir` a la table du code, et cinq assertions de ce
#: fichier ont rougi sur `Left contains 1 more item: {'scan_dir': ''}` -- sans rien
#: mesurer de plus que leur propre retard. La sortie n'est pas de lire la table (ce
#: serait la tautologie), c'est de la **confronter une fois**, dans un test qui porte
#: son nom: `test_les_DEFAUTS_OPTIONNELS_du_code_sont_EXACTEMENT_ceux_recopies_ici`.
#: Un champ optionnel neuf fera desormais rougir **ce test-la**, qui dit quoi faire,
#: plutot que cinq egalites de documents qui ne disent rien.
DEFAUTS_RELUS_RECOPIES = {"label": "", "comment": "", "scan_dir": ""}

#: Les defauts optionnels que ce banc ne recopie **pas**, parce que les fabriques les
#: ecrivent deja: `profile_to_document` pose toujours `acceptance`, si bien qu'aucune
#: fusion ne s'y voit. Ils sont nommes plutot que tus, sans quoi la confrontation
#: ci-dessous accuserait la table du code d'un champ de trop.
DEFAUTS_DEJA_ECRITS_PAR_LES_FABRIQUES = ("acceptance",)


def _tel_qu_ecrit(document: dict) -> dict:
    """Le document **tel que le projet le relit**: ses champs, plus les defauts optionnels.

    Amende le 2026-08-18 par l'AC 8quater: un profil porte desormais une etiquette et un
    commentaire **facultatifs**, et un profil qui n'en a pas se relit avec leur defaut --
    la chaine vide -- par fusion pure. C'est exactement le regime d'`acceptance` depuis
    5.22, et c'est la retrocompatibilite que l'AC 8quater doit tenir: un profil ecrit
    avant elle se relit sans refus.

    Amende le 2026-09-07 par `EPIC11-ARB-262`: `scan_dir` rejoint les deux precedents.
    Ce n'est **pas** une mise a jour de confort, c'est un arbitrage, et il se tranche
    contre `witness_raw_bgr` -- le champ que la meme table exclut deliberement. Le
    critere est ecrit dans le module: un champ prend un defaut de relecture quand
    l'**absence** de la mesure et une mesure **vide** disent la meme chose. Mesure aux
    deux consommateurs reels de `scan_dir`, et non supposee:
    `test_scan_dir_est_du_COTE_de_label_et_PAS_du_cote_de_witness_raw_bgr`.

    Les valeurs viennent de :data:`DEFAUTS_RELUS_RECOPIES`, litteral de ce fichier et
    jamais de la table du code -- voir la note qui l'accompagne.
    """
    return {**document, **DEFAUTS_RELUS_RECOPIES}


def _coefficients(profile) -> dict:
    """Les coefficients d'un profil, tableau par tableau: la mesure porte sur eux."""
    return {nom: np.asarray(valeur, dtype=float)
            for nom, valeur in vars(profile).items()
            if isinstance(valeur, (list, tuple, np.ndarray))}


def _memes_coefficients(gauche, droite) -> bool:
    a, b = _coefficients(gauche), _coefficients(droite)
    return sorted(a) == sorted(b) and all(
        np.array_equal(a[nom], b[nom]) for nom in a)


# ---------------------------------------------------------------------------
# Ce que la RELECTURE ajoute au document, et pourquoi elle a le droit
# ---------------------------------------------------------------------------


def test_les_DEFAUTS_OPTIONNELS_du_code_sont_EXACTEMENT_ceux_recopies_ici() -> None:
    """La confrontation, faite **une fois**, entre le litteral de ce banc et la table.

    Elle existe parce que le litteral a peri sans rien dire. Le 2026-09-07,
    `EPIC11-ARB-262` a ajoute `scan_dir` a `_OPTIONAL_DEFAULTS` et cinq egalites de
    documents de ce fichier ont rougi -- sur un `Left contains 1 more item`, c'est-a-dire
    sur le retard du banc et sur rien d'autre. Cinq rouges muets valent moins qu'un
    rouge qui dit quoi faire.

    **Elle porte sur les NOMS et sur les VALEURS, et ce n'est pas la meme mesure.** Les
    noms attrapent le champ neuf: c'est la panne du 2026-09-07. Les valeurs attrapent
    un defaut qui changerait sans qu'on l'ait voulu -- une chaine vide devenue `None`
    rendrait `_tel_qu_ecrit` faux partout, et les egalites de documents le diraient sans
    jamais nommer la cause.

    **Elle ne rend pas ce banc tautologique**, et c'est tout l'equilibre: les valeurs
    servies aux assertions viennent du litteral de :data:`DEFAUTS_RELUS_RECOPIES`, jamais
    de la table. Si la table se mettait a rendre `None`, ce test-ci rougirait -- et les
    autres continueraient de mesurer la chaine vide, qui est ce que le contrat promet.
    """
    du_code = dict(calibration_profile._OPTIONAL_DEFAULTS)

    attendus = set(DEFAUTS_RELUS_RECOPIES) | set(DEFAUTS_DEJA_ECRITS_PAR_LES_FABRIQUES)
    assert set(du_code) == attendus, (
        "la table des defauts optionnels du code et ce que ce banc en dit ont diverge: "
        f"{sorted(set(du_code) ^ attendus)}. Un champ optionnel NEUF s'ajoute a "
        "`DEFAUTS_RELUS_RECOPIES` (avec sa valeur, en litteral) apres avoir tranche "
        "qu'il prend bien un defaut de relecture -- le critere est celui de "
        "`witness_raw_bgr`: l'absence de la mesure et une mesure vide doivent dire la "
        "MEME chose.")

    for nom, valeur in DEFAUTS_RELUS_RECOPIES.items():
        assert du_code[nom] == valeur, (
            f"le defaut de relecture de {nom!r} vaut {du_code[nom]!r} dans le code et "
            f"{valeur!r} dans ce banc")

    # Le symetrique, sans lequel la mesure ci-dessus dirait seulement que la table est
    # ce qu'elle est: le champ dont l'absence est un FAIT n'y entre pas. Il est nomme,
    # parce que c'est lui qui donne son sens au critere.
    assert calibration_profile.WITNESS_RAW_FIELD not in du_code, (
        "`witness_raw_bgr` a pris un defaut de relecture: son absence -- « rien n'a ete "
        "mesure » -- se confondrait desormais avec une mesure vide -- « mesure, aucun "
        "temoin trouve », qui s'ecrit sous un autre motif au manifeste.")


def test_scan_dir_est_du_COTE_de_label_et_PAS_du_cote_de_witness_raw_bgr(
        tmp_path) -> None:
    """L'arbitrage d'`EPIC11-ARB-262`, tranche **sur les consommateurs** et pas en prose.

    La question posee par la table des defauts optionnels est toujours la meme:
    l'**absence** du champ et une valeur **vide** disent-elles la meme chose ? Pour
    `label` et `comment`, oui -- « l'operateur n'a rien nomme ». Pour `witness_raw_bgr`,
    non -- « rien n'a ete mesure » n'est pas « mesure, aucun temoin ». `scan_dir` se
    range du premier cote, et ce banc le mesure aux **deux** endroits du module qui le
    lisent reellement, plutot que de le declarer:

    * `dossiers_de_scan_declares`, l'unique lecture produit: un profil sans le champ et
      un profil dont le champ est vide declarent tous deux **rien**, et un profil qui
      nomme un dossier le declare. Trois profils, donc, et pas un seul: c'est ce qui
      distingue « la lecture ecarte le vide » de « la lecture ne rend jamais rien »;
    * `_validate_scan_dir`, la garde d'ecriture: elle **accepte** l'absence et la chaine
      vide de la meme facon (`if not valeur: return`), la ou elle refuse quatre formes
      nommees. Un champ dont le vide serait un fait distinct aurait ici un traitement
      distinct, et il n'en a pas.

    **La consequence qui rend l'arbitrage sur, et qui a ete mesuree**: la table est
    appliquee a la RELECTURE, donc un aller-retour `read_profile` puis `write_profile`
    ecrirait `scan_dir: ""` dans un fichier qui ne le portait pas. C'est sans effet --
    les deux lectures ci-dessus rendent le meme verdict avant et apres --, la ou le meme
    aller-retour sur `witness_raw_bgr` detruirait une distinction. C'est exactement le
    motif que le docstring de `_OPTIONAL_DEFAULTS` invoque pour l'exclure.

    Fabriques (CLAUDE.md): trois profils distinguables, la cible n'est ni en tete ni en
    queue pour la lecture nominale, et les deux bords sont exerces -- le profil MUET est
    en tete, le profil VIDE en queue.
    """
    projet = tmp_path / "projet"
    dossier = projet / calibration_profile.VERSIONS_DIRNAME / \
        calibration_profile.CALIBRATION_DIRNAME
    dossier.mkdir(parents=True)

    # Trois profils distinguables, poses dans un ordre qui met les deux bords a
    # l'epreuve: le muet en tete alphabetique, le declarant au milieu, le vide en queue.
    muet = _document(_CHAINES[0], _PRESSES[0])
    muet.pop(calibration_profile.SCAN_DIR_FIELD, None)
    declarant = {**_document(_CHAINES[1], _PRESSES[1]),
                 calibration_profile.SCAN_DIR_FIELD: "scans/calibration"}
    vide = {**_document(_CHAINES[2], _PRESSES[2]),
            calibration_profile.SCAN_DIR_FIELD: ""}
    for radical, document in (("a-muet", muet), ("m-declarant", declarant),
                              ("z-vide", vide)):
        (dossier / f"{radical}.json").write_text(
            calibration_profile.serialize_profile(document), encoding="utf-8")

    # (1) La lecture produit: le vide et l'absence rendent le MEME verdict -- rien --,
    # et seul le dossier nomme sort.
    assert calibration_profile.dossiers_de_scan_declares(projet) == {
        "scans/calibration"}

    # (2) La garde d'ecriture: l'absence et le vide passent toutes deux, la ou les
    # quatre formes refusees sont refusees. Sans ces quatre-la, « elle accepte tout »
    # expliquerait aussi bien la mesure.
    calibration_profile._validate_scan_dir(muet)
    calibration_profile._validate_scan_dir(vide)
    for refusee in ("/scans/calibration", "C:/scans", "../dehors",
                    "scans\\calibration"):
        with pytest.raises(calibration_profile.ProfileValidationError):
            calibration_profile._validate_scan_dir(
                {calibration_profile.SCAN_DIR_FIELD: refusee})

    # (3) L'aller-retour, qui est ce que la table du code provoque reellement: le profil
    # MUET relu porte le champ vide, et cela ne change aucun des deux verdicts.
    calibration_profile.write_profile(projet, muet)
    relu = calibration_profile.read_profile(projet, muet["chain_id"])
    assert relu[calibration_profile.SCAN_DIR_FIELD] == ""
    calibration_profile.write_profile(projet, relu,
                                      confirm_overwrite=lambda *_: True)
    assert calibration_profile.dossiers_de_scan_declares(projet) == {
        "scans/calibration"}


# ---------------------------------------------------------------------------
# `--profil <chemin>` applique CE profil, meme hors du projet
# ---------------------------------------------------------------------------


def test_le_profil_designe_est_celui_qui_est_applique(tmp_path) -> None:
    """AC 12, test 1: `--profil <chemin>` applique **ce** profil.

    Trois profils autonomes existent; celui qui est designe est le **deuxieme**, et la
    mesure porte sur ses coefficients. Un `--profil` qui rendrait le premier profil
    trouve -- classe du mutant `M25` -- se demasque ici, et le temoin negatif
    (« ce ne sont pas les coefficients des deux autres ») est ce qui rend l'assertion
    concluante.
    """
    profils = _trois_profils_externes(tmp_path)
    project_dir = tmp_path / "projet-courant"
    logger = _logger(project_dir)
    chemin_vise, document_vise = profils[1]

    correction = cli._resolve_designated_correction(
        project_dir, chemin_vise, logger, correction_requested=True)

    assert correction is not None
    assert correction.available
    attendu = cc.profile_from_document(document_vise)
    assert _memes_coefficients(correction.profile, attendu)
    # Temoin negatif: ce ne sont ni ceux du premier, ni ceux du troisieme.
    for rang in (0, 2):
        autre = cc.profile_from_document(profils[rang][1])
        if profils[rang][1]["coefficients"] != document_vise["coefficients"]:
            assert not _memes_coefficients(correction.profile, autre), rang


def test_un_profil_hors_du_projet_est_applique_sans_refus_lie_au_projet(
    tmp_path,
) -> None:
    """AC 12, test 1 et 2: le chemin peut pointer **hors du projet courant**.

    `EPIC5-ARB-82`, confirme par Egan: « on peut utiliser la page d'un autre projet dans
    un projet donne. Cela ne doit pas donner lieu a un refus de calibration. »

    Le profil vient du **premier** des trois projets, il est designe depuis le
    **deuxieme**, et le troisieme sert de temoin: aucun des trois noms de projet
    n'apparait dans une raison de refus, parce qu'il n'y a pas de refus.
    """
    amont, aval, _ = _trois_projets(tmp_path)
    document = _document(_CHAINES[1], _PRESSES[1])
    dans_amont = calibration_profile.write_profile(amont, document)

    logger = _logger(aval)
    correction = cli._resolve_designated_correction(
        aval, dans_amont, logger, correction_requested=True)

    assert correction is not None, _journal(aval)
    assert _memes_coefficients(
        correction.profile, cc.profile_from_document(document))
    # Le profil est **verse** au projet courant, sous sa propre identite.
    assert calibration_profile.read_profile(aval, _CHAINES[1]) == _tel_qu_ecrit(
        document)
    # Frontiere negative: le projet d'origine n'est nomme dans **aucun** refus. Il
    # peut apparaitre au journal comme provenance -- c'est ce qui s'est passe --, mais
    # jamais accompagne d'un mot de refus.
    journal = _journal(aval)
    for ligne in journal.splitlines():
        assert "refus" not in ligne.lower(), ligne
        assert "ERROR" not in ligne, ligne


def test_le_profil_designe_est_applique_meme_quand_sa_chaine_n_est_celle_de_personne(
    tmp_path,
) -> None:
    """AC 12, test 6: le `chain_id` **n'est plus une cle d'appariement**.

    Le profil designe declare une chaine qui n'est celle d'aucun profil du projet, et
    qu'aucun scan ne deriverait. Il s'applique quand meme -- et son `chain_id` descend
    dans la correction comme **identite et provenance**, jamais comme critere.

    C'est le test qui prouve la suppression plutot que de l'affirmer: une comparaison
    de `chain_id` reintroduite ici, sous quelque forme que ce soit, rend `None`.
    """
    project_dir = tmp_path / "projet-courant"
    logger = _logger(project_dir)
    # Le projet porte deja trois profils, aucun n'ayant l'identite du profil designe.
    for chaine, presse in zip(_CHAINES, _PRESSES):
        calibration_profile.write_profile(
            project_dir, _document(chaine, presse))
    etrangere = "chaine-inconnue-au-projet"
    externe, document = _fichier_externe(tmp_path / "ailleurs", etrangere, _PRESSES[1])

    correction = cli._resolve_designated_correction(
        project_dir, externe, logger, correction_requested=True)

    assert correction is not None, _journal(project_dir)
    assert correction.chain_id == etrangere
    assert _memes_coefficients(
        correction.profile, cc.profile_from_document(document))


# ---------------------------------------------------------------------------
# L'import verse au projet courant: fichier + entree autoportante
# ---------------------------------------------------------------------------


def test_l_import_verse_au_manifest_une_entree_autoportante(tmp_path) -> None:
    """AC 12, test 2, et la moitie manifest du couple d'Egan (note 1).

    « Un profil = un fichier autonome + **une entree autoportante au manifeste**. Les
    deux se suffisent: le fichier voyage seul, et le manifest dit ce que le projet a
    reellement utilise **sans avoir a ouvrir le fichier**. »

    La mesure est litterale: le fichier de profil designe est **efface** apres l'import,
    et l'entree doit continuer de repondre a « quel profil, quelle chaine, quelle forme,
    quelle page source, combien de pastilles, d'ou il venait ». Une entree qui ne
    porterait qu'un chemin passerait un test de presence et echouerait celui-ci.
    """
    projets = _trois_projets(tmp_path)
    cible = projets[1]
    externe, document = _fichier_externe(
        tmp_path / "ailleurs", _CHAINES[1], _PRESSES[1])

    designation.import_designated_profile(cible, externe)
    externe.unlink()

    entrees = _color(cible)[designation.DESIGNATED_PROFILES_KEY]
    entree = _entree_de_chaine(entrees, _CHAINES[1])
    assert entree is not None, entrees
    # **Les champs sont enumeres en litteral ici, et non lus sur
    # `ENTRY_DOCUMENT_FIELDS`.** Les lire sur la constante que le code utilise serait
    # une tautologie: retirer un champ de la constante retirerait la question du test
    # en meme temps que la reponse, et le test resterait vert sur une entree devenue
    # incomplete. Le defaut est mesure -- un mutant qui retire `correction_form_id` de
    # la constante survivait a la premiere redaction de ce test. Cette liste est la
    # question a laquelle l'entree doit repondre **sans ouvrir le fichier**, et elle
    # doit etre modifiee a la main quand la question change.
    attendus = (
        "schema_version", "chain_id", "correction_form_id", "source_page_id",
        "template_id", "read_patch_count", "retained_patch_count",
        "ink_floor_excluded",
    )
    for champ in attendus:
        assert champ in entree, champ
        assert entree[champ] == document[champ], champ
    # Et la constante du code couvre bien cette liste: si elle s'appauvrit, la boucle
    # ci-dessus rougit deja, mais ce garde-fou nomme la cause au lieu du symptome.
    assert set(attendus) <= set(designation.ENTRY_DOCUMENT_FIELDS), (
        sorted(set(attendus) - set(designation.ENTRY_DOCUMENT_FIELDS)))
    assert entree[designation.ENTRY_SOURCE_KEY] == externe.name
    # Le chemin **dans le projet** est relatif au projet, et il pointe sur un fichier
    # reel: c'est ce qui rend un projet copiable tel quel.
    assert not Path(entree[designation.ENTRY_PATH_KEY]).is_absolute()
    assert (cible / entree[designation.ENTRY_PATH_KEY]).is_file()


def test_le_registre_est_trie_sans_doublon_et_ne_desapprend_rien(tmp_path) -> None:
    """Trois profils verses, puis l'un des trois redesigne: trois entrees, pas quatre.

    Trois proprietes, chacune repondant a une objection:

    * **liste** et non valeur unique, parce qu'un projet peut porter des lots numerises
      sur plusieurs chaines -- un champ scalaire aurait fait ecrire la derniere chaine
      par-dessus les precedentes;
    * **triee**, pour que deux projets ayant vu les memes profils dans un ordre
      different rendent le meme document;
    * **sans doublon**, parce qu'une chaine recalibree remplace son entree -- deux
      entrees pour une chaine feraient deux verites, dont une perimee.

    La reecriture porte sur le **deuxieme** profil, jamais sur le premier: un `upsert`
    qui remplacerait toujours la premiere entree se demasque ici et nulle part ailleurs.
    """
    cible = _trois_projets(tmp_path)[1]
    profils = _trois_profils_externes(tmp_path)
    for chemin, _document in profils:
        designation.import_designated_profile(cible, chemin)

    entrees = _color(cible)[designation.DESIGNATED_PROFILES_KEY]
    assert [entree["chain_id"] for entree in entrees] == sorted(_CHAINES)

    # Le **deuxieme** profil est redesigne depuis un autre emplacement, avec une autre
    # presse: son entree est remplacee, les deux autres sont intactes.
    ailleurs, redesigne = _fichier_externe(
        tmp_path / "seconde-main", _CHAINES[1], _PRESSES[2])
    # Le fichier redesigne porte un **autre nom de base** que le premier: c'est le nom
    # qui est ecrit comme provenance, donc deux fichiers homonymes rendraient
    # l'assertion de remplacement vraie sans rien prouver.
    ailleurs = ailleurs.rename(ailleurs.with_name("profil-recalibre.json"))
    designation.import_designated_profile(cible, ailleurs)

    entrees = _color(cible)[designation.DESIGNATED_PROFILES_KEY]
    assert [entree["chain_id"] for entree in entrees] == sorted(_CHAINES)
    vise = _entree_de_chaine(entrees, _CHAINES[1])
    assert vise[designation.ENTRY_SOURCE_KEY] == ailleurs.name
    assert vise[designation.ENTRY_SOURCE_KEY] != profils[1][0].name
    assert vise["source_page_id"] == redesigne["source_page_id"]
    # Le **fichier** du projet a suivi: c'est le profil recalibre qui s'y trouve, pas
    # celui du premier import. Une entree mise a jour au-dessus d'un fichier inchange
    # serait deux verites, dont une fausse.
    assert calibration_profile.read_profile(cible, _CHAINES[1]) == _tel_qu_ecrit(
        redesigne)
    assert redesigne["coefficients"] != profils[1][1]["coefficients"]
    # Les deux autres n'ont pas bouge de provenance.
    for rang in (0, 2):
        autre = _entree_de_chaine(entrees, _CHAINES[rang])
        assert autre[designation.ENTRY_SOURCE_KEY] == profils[rang][0].name, rang


def test_l_upsert_remplace_la_chaine_visee_et_non_la_premiere() -> None:
    """Classe du mutant `M25` (`_find_lot`, story 5.7), a l'unite, sur `_upsert`.

    Reecrit le 2026-08-19: il portait jusque-la sur `find_registered_profile`, retire
    par `EPIC5-ARB-101` faute d'appelant de production. `_upsert` est desormais le
    **seul** endroit du module qui compare un `chain_id`, donc le seul ou cette classe
    de mutant peut mordre -- et elle y mord bien plus fort: un `upsert` qui ecarterait
    la premiere entree au lieu de celle qui porte la chaine visee ferait declarer au
    projet l'usage d'un profil qu'il n'a jamais applique.

    Les trois entrees sont distinguables, la cible est en **troisieme** position, et le
    registre entrant n'est **pas** trie: un `upsert` qui se fierait a l'ordre recu
    plutot qu'a la comparaison se demasque ici.
    """
    entrees = [{"chain_id": chaine, "source_page_id": f"{chaine}-p0"}
               for chaine in _CHAINES]
    neuve = {"chain_id": _CHAINES[2], "source_page_id": "page-recalibree"}

    registre = designation._upsert(entrees, neuve)

    assert [entree["chain_id"] for entree in registre] == sorted(_CHAINES)
    vise = _entree_de_chaine(registre, _CHAINES[2])
    assert vise["source_page_id"] == "page-recalibree"
    # Les deux autres n'ont pas bouge: ce sont elles qu'un `upsert` fautif ecarterait.
    assert _entree_de_chaine(registre, _CHAINES[0])["source_page_id"] == (
        f"{_CHAINES[0]}-p0")
    assert _entree_de_chaine(registre, _CHAINES[1])["source_page_id"] == (
        f"{_CHAINES[1]}-p0")
    # Frontiere: une chaine absente du registre s'y **ajoute**, elle n'en remplace
    # aucune -- quatre entrees, et les trois d'origine intactes.
    elargi = designation._upsert(registre, {"chain_id": "chaine-absente",
                                            "source_page_id": "page-neuve"})
    assert len(elargi) == 4
    assert _entree_de_chaine(elargi, _CHAINES[2])["source_page_id"] == (
        "page-recalibree")


# ---------------------------------------------------------------------------
# Le profil par defaut du projet, pose par une commande dediee
# ---------------------------------------------------------------------------


def test_la_commande_dediee_pose_le_defaut_et_le_scan_l_utilise(tmp_path) -> None:
    """AC 12, test 3: une commande **dediee et separee** pose le defaut du projet.

    Le profil pose est le **deuxieme** des trois, et la mesure porte sur les
    coefficients que la resolution rend ensuite sans `--profil`.
    """
    profils = _trois_profils_externes(tmp_path)
    cible = _trois_projets(tmp_path)[1]
    chemin_vise, document_vise = profils[1]

    code = cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", str(cible),
                     cli.PROFILE_FLAG, str(chemin_vise)])
    assert code == 0

    args = SimpleNamespace(profil=None)
    source, origine = cli._designated_profile_source(args, cible, _logger(cible))
    assert source is not None
    assert origine is not None
    correction = cli._resolve_designated_correction(
        cible, source, _logger(cible), correction_requested=True)
    assert correction is not None
    assert correction.chain_id == _CHAINES[1]
    assert _memes_coefficients(
        correction.profile, cc.profile_from_document(document_vise))


def test_le_defaut_du_projet_se_resout_par_le_chemin_ecrit_et_non_par_la_chaine(
    tmp_path,
) -> None:
    """Frontiere du test 6: le defaut ne se recompose **pas** depuis le `chain_id`.

    Recomposer `versions/calibration/<chain_id>.json` ferait de l'identite une cle de
    resolution -- ce que `EPIC5-ARB-83` supprime -- et le ferait de la seule facon qui
    passe inapercue: en marchant, tant que les deux coincident.

    La mesure les fait diverger: l'entree est reecrite pour designer un **autre**
    fichier du projet que celui que son `chain_id` nommerait. Une resolution par chemin
    rend l'autre fichier; une resolution par `chain_id` rend le premier.
    """
    cible = _trois_projets(tmp_path)[1]
    profils = _trois_profils_externes(tmp_path)
    for chemin, _doc in profils:
        designation.import_designated_profile(cible, chemin)
    assert cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", str(cible),
                     cli.PROFILE_FLAG, str(profils[0][0])]) == 0

    manifest_path = cible / extraction_manifest.MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entree = manifest["color"][designation.DEFAULT_PROFILE_KEY]
    assert entree["chain_id"] == _CHAINES[0]
    # Le chemin est detourne vers le profil de la **troisieme** chaine; le `chain_id`
    # de l'entree, lui, reste celui de la premiere.
    entree[designation.ENTRY_PATH_KEY] = calibration_profile.profile_path(
        cible, _CHAINES[2]).relative_to(cible).as_posix()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")

    resolu = designation.default_profile_path(cible)
    assert resolu == calibration_profile.profile_path(cible, _CHAINES[2]), resolu


def test_un_scan_ne_pose_jamais_le_defaut_du_projet(tmp_path) -> None:
    """AC 12, test 3, versant negatif: « **jamais un effet de bord d'un scan** ».

    `EPIC5-ARB-83`, decision 2, mot pour mot. Un scan qui poserait le defaut au passage
    ferait qu'un `--profil` tape une fois pour essayer resterait ensuite en vigueur sans
    que personne l'ait voulu -- et le lot suivant sortirait corrige par un profil que
    son operateur n'a pas designe. C'est la meme classe de defaut que la derivation
    automatique, par une autre porte.
    """
    cible = _trois_projets(tmp_path)[1]
    chemin, _document = _trois_profils_externes(tmp_path)[1]

    correction = cli._resolve_designated_correction(
        cible, chemin, _logger(cible), correction_requested=True)
    assert correction is not None

    assert designation.DEFAULT_PROFILE_KEY not in _color(cible), _color(cible)
    assert designation.default_profile_path(cible) is None
    # Temoin positif: la commande dediee, elle, le pose -- sans quoi l'assertion
    # ci-dessus serait verte sur un mecanisme qui n'existe pas.
    assert cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", str(cible),
                     cli.PROFILE_FLAG, str(chemin)]) == 0
    assert designation.default_profile_path(cible) is not None


# ---------------------------------------------------------------------------
# Precedence
# ---------------------------------------------------------------------------


def test_profil_l_emporte_sur_le_defaut_du_projet(tmp_path) -> None:
    """AC 12, test 4: `--profil` l'emporte sur le defaut du projet.

    Trois profils, **le defaut est le premier**, la cible de `--profil` est le
    **troisieme**: une precedence inversee rendrait le premier, et une resolution qui
    prendrait « le premier profil connu » aussi. Les deux mutants sont distincts, et ce
    placement les tue tous les deux.

    La mesure porte sur les coefficients rendus, jamais sur le chemin choisi: un test
    qui n'irait pas jusqu'a la correction laisserait passer une precedence correcte
    suivie d'une lecture fautive.
    """
    profils = _trois_profils_externes(tmp_path)
    cible = _trois_projets(tmp_path)[1]
    assert cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", str(cible),
                     cli.PROFILE_FLAG, str(profils[0][0])]) == 0

    args = SimpleNamespace(profil=str(profils[2][0]))
    source, origine = cli._designated_profile_source(args, cible, _logger(cible))
    correction = cli._resolve_designated_correction(
        cible, source, _logger(cible), correction_requested=True, origine=origine)

    assert correction is not None
    assert correction.chain_id == _CHAINES[2]
    assert _memes_coefficients(
        correction.profile, cc.profile_from_document(profils[2][1]))
    # Temoin negatif: ce n'est pas le defaut, et le defaut existe bien.
    assert designation.default_profile_path(cible) is not None
    assert correction.chain_id != _CHAINES[0]


# ---------------------------------------------------------------------------
# Aucun profil designe: avertissement, lot brut, JAMAIS un repli
# ---------------------------------------------------------------------------


def test_aucun_profil_designe_avertit_et_ne_se_rabat_sur_rien(tmp_path) -> None:
    """AC 12, test 5, **le piege central de cette AC**.

    « Aucun profil designe -> avertissement, lot livre en brut. Jamais un refus, jamais
    un choix automatique de repli -- un profil choisi par defaut serait la
    reintroduction du defaut que cette decision supprime » (`EPIC5-ARB-83`, decision 5).

    Le projet porte **trois** profils parfaitement lisibles dans
    `versions/calibration/`, et aucun ne doit etre applique. C'est le regime ou un repli
    est le plus tentant et le plus dangereux: il marcherait, silencieusement, et
    rejouerait exactement le « mauvais profil applique en silence » que la story
    supprime.

    La mesure porte sur les deux volets, parce qu'un seul ne conclut pas: rien n'est
    rendu, **et** aucune lecture de profil n'a lieu. Un repli qui lirait un profil pour
    le rejeter ensuite serait un repli sous surveillance, pas une absence de repli.
    """
    project_dir = _trois_projets(tmp_path)[1]
    for chaine, presse in zip(_CHAINES, _PRESSES):
        calibration_profile.write_profile(
            project_dir, _document(chaine, presse))
    logger = _logger(project_dir)

    args = SimpleNamespace(profil=None)
    source, origine = cli._designated_profile_source(args, project_dir, logger)
    assert source is None
    assert origine is None

    correction = cli._resolve_designated_correction(
        project_dir, source, logger, correction_requested=True, origine=origine)
    assert correction is None

    journal = _journal(project_dir)
    assert "WARNING" in journal, journal
    # **Avertissement, pas refus**: aucun `ERROR`, et les deux gestes sont nommes.
    assert "ERROR" not in journal, journal
    assert cli.PROFILE_FLAG in journal, journal
    assert cli.SET_DEFAULT_PROFILE_COMMAND in journal, journal
    # Aucun des trois profils du projet n'est nomme: rien n'a ete cherche, donc rien
    # n'a ete trouve, donc rien n'a pu etre choisi.
    for chaine in _CHAINES:
        assert chaine not in journal, (chaine, journal)


def test_aucun_profil_designe_ne_lit_aucun_fichier_de_profil(tmp_path,
                                                             monkeypatch) -> None:
    """Second volet du meme piege, mesure sur les **lectures** et non sur le rendu.

    Un test pose sur le seul `None` rendu ne distinguerait pas « rien n'a ete cherche »
    de « quelque chose a ete cherche puis rejete ». C'est le second qui est dangereux:
    il suffit d'assouplir un refus pour que le repli reapparaisse, sans qu'aucune ligne
    de choix n'ait ete ecrite.

    Le **temoin positif** est ce qui rend le volet negatif concluant: sans lui, un
    espion mal branche rendrait le test vert pour rien.
    """
    project_dir = _trois_projets(tmp_path)[1]
    for chaine, presse in zip(_CHAINES, _PRESSES):
        calibration_profile.write_profile(
            project_dir, _document(chaine, presse))
    logger = _logger(project_dir)

    lectures: list = []
    vrai = designation.read_designated_document

    def espion(source):
        lectures.append(Path(source))
        return vrai(source)

    monkeypatch.setattr(designation, "read_designated_document", espion)

    assert cli._resolve_designated_correction(
        project_dir, None, logger, correction_requested=True) is None
    assert lectures == [], lectures

    # Temoin positif: designe, le profil est bien lu -- une fois, et c'est celui-la.
    chemin, _doc = _fichier_externe(tmp_path / "ailleurs", _CHAINES[1], _PRESSES[1])
    assert cli._resolve_designated_correction(
        project_dir, chemin, logger, correction_requested=True) is not None
    assert lectures == [chemin], lectures


def test_un_profil_designe_illisible_ne_se_rabat_pas_sur_un_profil_du_projet(
    tmp_path,
) -> None:
    """Frontiere du meme piege: un profil designe **corrompu** ne declenche aucun repli.

    C'est la porte la plus etroite et la plus plausible: « il a designe quelque chose,
    ce quelque chose est cassé, prenons ce que le projet a ». Le regime correct est le
    meme que l'absence de designation -- le lot sort brut --, a ceci pres que c'est
    cette fois une **erreur** et non un avertissement: l'operateur a designe un fichier,
    et son geste n'a pas pu etre honore.
    """
    project_dir = _trois_projets(tmp_path)[1]
    for chaine, presse in zip(_CHAINES, _PRESSES):
        calibration_profile.write_profile(
            project_dir, _document(chaine, presse))
    corrompu = tmp_path / "ailleurs" / "profil-tronque.json"
    corrompu.parent.mkdir(parents=True, exist_ok=True)
    corrompu.write_text('{"schema_version": 1, "chain_id"', encoding="utf-8")
    logger = _logger(project_dir)

    assert cli._resolve_designated_correction(
        project_dir, corrompu, logger, correction_requested=True) is None
    journal = _journal(project_dir)
    assert str(corrompu) in journal, journal
    # Aucun profil du projet n'est nomme: le refus ne s'accompagne d'aucun repli.
    for chaine in _CHAINES:
        assert chaine not in journal, (chaine, journal)


def test_un_defaut_dont_le_fichier_a_disparu_ne_se_rabat_sur_rien(tmp_path) -> None:
    """Meme piege, troisieme porte: l'entree de defaut survit a son fichier.

    L'entree de manifest reste vraie de ce que le projet a utilise -- c'est le sens de
    son autoportance --, mais elle ne fabrique pas un profil absent, et surtout elle ne
    justifie pas d'aller en chercher un autre. Le projet porte deux autres profils
    parfaitement lisibles: aucun ne doit prendre la place.
    """
    cible = _trois_projets(tmp_path)[1]
    profils = _trois_profils_externes(tmp_path)
    for chemin, _doc in profils:
        designation.import_designated_profile(cible, chemin)
    assert cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", str(cible),
                     cli.PROFILE_FLAG, str(profils[1][0])]) == 0
    assert designation.default_profile_path(cible) is not None

    calibration_profile.profile_path(cible, _CHAINES[1]).unlink()

    assert designation.default_profile_path(cible) is None
    # L'entree, elle, est toujours la: elle dit ce qui a servi, meme sans le fichier.
    assert _color(cible)[designation.DEFAULT_PROFILE_KEY]["chain_id"] == _CHAINES[1]
    # Et les deux autres profils sont bien la, lisibles, et non choisis.
    for rang in (0, 2):
        assert calibration_profile.profile_exists(cible, _CHAINES[rang])
    args = SimpleNamespace(profil=None)
    source, _origine = cli._designated_profile_source(args, cible, _logger(cible))
    assert source is None


def test_un_profil_designe_refuse_n_ecrit_rien_dans_le_projet(tmp_path) -> None:
    """Reprise d'une propriete de 5.22 qui survit a la refonte de l'appariement.

    `test_consigner_un_profil_externe_refuse_sans_rien_ecrire` la tenait pour
    `_consign_external_profile`, dont la moitie « refus de chaine » est morte avec
    `EPIC5-ARB-83`. L'autre moitie reste vraie et importe autant: un profil qu'on ne
    sait pas lire ne laisse **aucun** fichier derriere lui, sans quoi le projet
    porterait un profil tronque qu'une relecture ulterieure prendrait pour un vrai.

    Le **temoin positif** est ce qui rend l'absence concluante: le meme geste, sur un
    fichier sain, ecrit bien quelque chose.
    """
    cible = _trois_projets(tmp_path)[1]
    corrompu = tmp_path / "ailleurs" / "tronque.json"
    corrompu.parent.mkdir(parents=True, exist_ok=True)
    corrompu.write_text('{"schema_version": 1, "chain_id"', encoding="utf-8")

    with pytest.raises(designation.ProfileDesignationError):
        designation.import_designated_profile(cible, corrompu)
    dossier = (cible / calibration_profile.VERSIONS_DIRNAME
               / calibration_profile.CALIBRATION_DIRNAME)
    assert not dossier.exists() or list(dossier.iterdir()) == []
    assert designation.DESIGNATED_PROFILES_KEY not in _color(cible)

    # Temoin positif: sain, le meme geste ecrit le fichier et l'entree.
    sain, document = _fichier_externe(tmp_path / "ailleurs", _CHAINES[1], _PRESSES[1])
    designation.import_designated_profile(cible, sain)
    assert calibration_profile.read_profile(cible, _CHAINES[1]) == _tel_qu_ecrit(
        document)


@pytest.mark.parametrize("degat", ["json-invalide", "schema-invalide"])
def test_un_profil_designe_est_valide_avant_d_etre_applique(tmp_path, degat) -> None:
    """La validation du **contenu** est exercee, pas seulement celle du JSON.

    Deux degats, parce qu'ils empruntent **deux branches distinctes** et qu'une seule
    des deux etait couverte: un fichier tronque meurt au decodage JSON, un document bien
    forme mais incomplet ne meurt qu'a la validation du profil. Un mutant qui rendait le
    document **sans le valider** survivait a la premiere redaction de ce fichier -- il
    passait le premier cas, qui n'atteint jamais la validation.

    Un profil dont on ne peut pas garantir le contenu ne doit pas etre applique: ce sont
    des pixels qu'on ne saurait plus interpreter.
    """
    cible = _trois_projets(tmp_path)[1]
    mauvais = tmp_path / "ailleurs" / f"{degat}.json"
    mauvais.parent.mkdir(parents=True, exist_ok=True)
    if degat == "json-invalide":
        mauvais.write_text('{"schema_version": 1, "chain_id"', encoding="utf-8")
    else:
        # JSON parfaitement valide, et **pas** un profil: les coefficients manquent,
        # donc rien ne dit quelle correction ce document decrit.
        document = _document(_CHAINES[1], _PRESSES[1])
        del document["coefficients"]
        mauvais.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(designation.ProfileDesignationError):
        designation.read_designated_document(mauvais)
    with pytest.raises(designation.ProfileDesignationError):
        designation.import_designated_profile(cible, mauvais)
    assert not calibration_profile.profile_exists(cible, _CHAINES[1])
    assert designation.DESIGNATED_PROFILES_KEY not in _color(cible)

    logger = _logger(cible)
    assert cli._resolve_designated_correction(
        cible, mauvais, logger, correction_requested=True) is None
    assert str(mauvais) in _journal(cible)


def test_un_manifest_illisible_ne_tue_pas_la_correction_du_lot(tmp_path) -> None:
    """Famille du bloquant `C2` de la revue de 5.22, sur le chemin neuf.

    Le defaut d'origine: un scan entier mourait en traceback parce que la consignation
    d'un profil n'avait pas pu ecrire, alors que les frames etaient parfaitement
    extractibles. Le meme risque revient par une autre porte -- l'entree **de manifest**
    du profil designe --, et il faut le fermer par la meme regle: la **trace** d'un
    profil n'est pas de la meme urgence que le profil lui-meme.

    Le regime est reel: le `project.json` est un JSON valide mais un manifest refuse au
    schema, donc l'ecriture atomique refuse son temporaire. La resolution doit rendre la
    correction quand meme.
    """
    cible = _trois_projets(tmp_path)[1]
    (cible / extraction_manifest.MANIFEST_FILENAME).write_text(
        json.dumps({"schema_version": "2.1", "project_id": "sans-lots"}),
        encoding="utf-8")
    chemin, document = _fichier_externe(tmp_path / "ailleurs", _CHAINES[1],
                                        _PRESSES[1])
    logger = _logger(cible)

    correction = cli._resolve_designated_correction(
        cible, chemin, logger, correction_requested=True)

    assert correction is not None, _journal(cible)
    assert _memes_coefficients(
        correction.profile, cc.profile_from_document(document))
    # Le fichier de profil, lui, est bien la: c'est ce qui rend la correction rejouable.
    assert calibration_profile.read_profile(cible, _CHAINES[1]) == _tel_qu_ecrit(
        document)


def test_une_ecriture_de_profil_impossible_ne_tue_pas_le_scan(tmp_path) -> None:
    """Reprise du bloquant `C2` de la revue de 5.22, sur le chemin neuf.

    Le defaut d'origine: `write_profile` n'etait dans aucun `except` du chemin de scan,
    donc un scan entier mourait en traceback parce que la **consignation** d'un profil
    n'avait pas pu ecrire -- alors que les frames, elles, etaient parfaitement
    extractibles. Le chemin a change; le regime de panne, non (disque plein,
    `versions/` en lecture seule).

    La construction du regime est reelle et non simulee: `versions/calibration` est un
    **fichier**, donc le `mkdir` de `write_profile` leve. Elle a l'avantage de mordre
    aussi sous `root`, ou un `chmod` ne bloque rien.
    """
    cible = _trois_projets(tmp_path)[1]
    dossier = (cible / calibration_profile.VERSIONS_DIRNAME
               / calibration_profile.CALIBRATION_DIRNAME)
    dossier.parent.mkdir(parents=True, exist_ok=True)
    dossier.write_text("ceci n'est pas un dossier", encoding="utf-8")
    chemin, _document = _fichier_externe(tmp_path / "ailleurs", _CHAINES[1],
                                         _PRESSES[1])
    logger = _logger(cible)

    correction = cli._resolve_designated_correction(
        cible, chemin, logger, correction_requested=True)

    assert correction is None
    journal = _journal(cible)
    assert str(chemin) in journal, journal
    # Temoin: sans le dossier bloque, la meme designation reussit. Sans lui, une
    # resolution qui rendrait toujours `None` passerait.
    libre = _trois_projets(tmp_path / "libre")[1]
    assert cli._resolve_designated_correction(
        libre, chemin, _logger(libre), correction_requested=True) is not None


# ---------------------------------------------------------------------------
# La forme des gestes en ligne de commande
# ---------------------------------------------------------------------------


def test_le_drapeau_de_designation_est_reconnu_par_le_scan(tmp_path, monkeypatch,
                                                           capsys) -> None:
    """`--profil` est branche sur `scan`, et il atteint le handler sous `profil`.

    Le temoin negatif -- un drapeau inconnu sort en `SystemExit(2)` -- est ce qui rend
    la reconnaissance concluante: sans lui, l'assertion serait verte sur un parseur qui
    accepterait n'importe quoi.
    """
    vus: list = []
    monkeypatch.setattr(cli, "scan_command", lambda args: vus.append(args) or 0)
    assert cli.main(["scan", "--project", "p", "--scan", "s", "--dpi", "600",
                     cli.PROFILE_FLAG, "chemin/du/profil.json"]) == 0
    (args,) = vus
    assert args.profil == "chemin/du/profil.json"

    with pytest.raises(SystemExit) as sortie:
        cli.main(["scan", "--project", "p", "--scan", "s", "--dpi", "600",
                  "--profil-inconnu", "x"])
    assert sortie.value.code == 2


def test_l_ancien_drapeau_de_chargement_n_existe_plus(tmp_path, monkeypatch) -> None:
    """`--charger-profil-de-calibration` a disparu avec sa semantique d'appariement.

    L'option de 5.22 consignait un profil externe **sous l'identite derivee du scan** et
    refusait un `chain_id` divergent: c'etait le dernier appariement automatique du
    chemin de scan. La garder a cote de `--profil` aurait laisse deux gestes pour la
    meme intention, dont l'un porte le defaut que la story supprime.

    `argparse` refuse bruyamment, donc aucun script ne continue en silence avec un
    comportement change.
    """
    monkeypatch.setattr(cli, "scan_command", lambda args: 0)
    with pytest.raises(SystemExit) as sortie:
        cli.main(["scan", "--project", "p", "--scan", "s", "--dpi", "600",
                  "--charger-profil-de-calibration", "x.json"])
    assert sortie.value.code == 2
    assert not hasattr(cli, "CHAIN_PROFILE_FLAG")


def test_la_commande_de_defaut_est_separee_de_scan(monkeypatch) -> None:
    """AC 12, test 3: la commande est **dediee**, au premier niveau, pas sous `scan`.

    Declaree sous `scan`, elle serait un geste qu'on tape en scannant -- c'est-a-dire, a
    une distraction pres, l'effet de bord que l'arbitrage interdit mot pour mot.
    """
    vus: list = []
    monkeypatch.setattr(cli, "set_default_profile_command",
                        lambda args: vus.append(args) or 0)
    assert cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", "p",
                     cli.PROFILE_FLAG, "x.json"]) == 0
    (args,) = vus
    assert args.project == "p"
    assert args.profil == "x.json"
    # Elle n'est pas une sous-commande de `scan`.
    with pytest.raises(SystemExit) as sortie:
        cli.main(["scan", "--project", "p", "--scan", "s", "--dpi", "600",
                  cli.SET_DEFAULT_PROFILE_COMMAND])
    assert sortie.value.code == 2


def test_la_calibration_dit_le_geste_de_designation_et_ne_promet_plus_rien() -> None:
    """La boucle operateur `scan calibrate` -> `scan` est **nommee**, plus automatique.

    Le message de fin de `scan calibrate` annoncait « les lots de cette chaine la
    reutiliseront ». C'etait vrai tant que le scan appariait un profil par `chain_id`;
    depuis `EPIC5-ARB-83` c'est **faux**, et faux de la pire facon -- il promet un
    enchainement qui n'a pas lieu, si bien que le lot suivant sort brut pendant que
    l'operateur croit sa chaine calibree. Le seul moment ou il peut apprendre le geste
    est celui-la.

    La mesure porte sur le **texte source** de la commande, parce que le fait est la
    redaction d'un message et que l'exercer demanderait une page de calibration scannee
    -- ce que l'AC 9 exclut de ce fichier. Le temoin positif (le message existe, et il
    nomme les deux gestes par leurs constantes) est ce qui rend la frontiere negative
    concluante.
    """
    source = (REPO_ROOT / "src" / "mixed_media_utility" / "cli.py").read_text(
        encoding="utf-8")
    debut = source.index("def scan_calibrate_command(")
    fin = source.index("def extract_command(")
    corps = source[debut:fin]
    # La mesure porte sur les **litteraux de chaine** de la commande, jamais sur son
    # texte brut: la prose des commentaires cite la phrase fautive precisement pour
    # dire qu'elle est retiree, et un balayage textuel se declencherait dessus. C'est le
    # meme piege que la frontiere du mot « seuil » de l'AC 16 de 5.16, deja paye.
    corps_ast = ast.parse(corps)
    litteraux = " ".join(
        noeud.value for noeud in ast.walk(corps_ast)
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str))
    assert "reutiliseront" not in litteraux, (
        "le message promet encore une reutilisation automatique")
    # Temoin positif: la commande dit bien quelque chose a l'operateur, et les deux
    # gestes y sont nommes par leurs constantes -- jamais par un litteral recopie, qui
    # divergerait au premier renommage.
    assert "calibration ecrite pour la chaine" in litteraux, litteraux[-800:]
    assert "PROFILE_FLAG" in corps, corps[-1200:]
    assert "SET_DEFAULT_PROFILE_COMMAND" in corps, corps[-1200:]
    assert "designent" in litteraux, litteraux[-800:]


def test_la_commande_de_defaut_refuse_un_dossier_qui_n_est_pas_un_projet(
    tmp_path, capsys,
) -> None:
    """Le seul refus de cette commande porte sur la **cible**, jamais sur la provenance.

    Le distinguo est celui de l'AC: « aucun refus lie au projet » interdit de refuser un
    profil **a cause d'ou il vient**. Refuser un dossier qui n'est pas un projet est un
    autre fait, et le message le dit.
    """
    chemin, _document = _fichier_externe(tmp_path / "ailleurs", _CHAINES[1],
                                         _PRESSES[1])
    code = cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project",
                     str(tmp_path / "pas-un-projet"), cli.PROFILE_FLAG, str(chemin)])
    assert code == 1
    erreur = capsys.readouterr().err
    assert extraction_manifest.MANIFEST_FILENAME in erreur, erreur


def test_la_commande_de_defaut_refuse_un_profil_illisible_sans_rien_poser(
    tmp_path, capsys,
) -> None:
    """Un profil refuse ne devient pas le defaut, et n'efface pas celui qui l'etait."""
    cible = _trois_projets(tmp_path)[1]
    profils = _trois_profils_externes(tmp_path)
    assert cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", str(cible),
                     cli.PROFILE_FLAG, str(profils[1][0])]) == 0
    avant = _color(cible)[designation.DEFAULT_PROFILE_KEY]

    corrompu = tmp_path / "ailleurs" / "tronque.json"
    corrompu.parent.mkdir(parents=True, exist_ok=True)
    corrompu.write_text('{"schema_version": 1,', encoding="utf-8")
    assert cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", str(cible),
                     cli.PROFILE_FLAG, str(corrompu)]) == 1
    assert capsys.readouterr().err.strip()
    assert _color(cible)[designation.DEFAULT_PROFILE_KEY] == avant


# ---------------------------------------------------------------------------
# Le `chain_id` n'est plus compare -- la preuve structurelle
# ---------------------------------------------------------------------------


def test_le_chemin_de_scan_ne_derive_plus_aucune_identite_de_chaine(tmp_path) -> None:
    """AC 12, test 6, versant structurel: `scan` ne **calcule** meme plus l'identite.

    La calculer sans s'en servir serait le reste inerte que l'AC 13 vient de retirer
    ailleurs -- et surtout, la rebrancher tiendrait alors en une ligne.

    La mesure porte sur le **texte source** de `scan_command`, parce que le fait est
    l'absence d'un appel: un test d'execution demanderait un scan complet, ce que l'AC 9
    exclut de ce fichier. La borne est prise sur les deux fonctions reelles, jamais sur
    un numero de ligne.

    Le **temoin positif** est ce qui rend l'absence concluante: `scan calibrate`, lui,
    derive toujours -- il **nomme** ce qu'il produit --, donc l'appel existe encore dans
    le fichier et le balayage ne mesure pas une constante.
    """
    source = (REPO_ROOT / "src" / "mixed_media_utility" / "cli.py").read_text(
        encoding="utf-8")
    debut = source.index("def scan_command(")
    fin = source.index("def _configure_default_profile_logger(")
    corps = source[debut:fin]
    assert "_derive_chain_id(" not in corps, (
        "scan_command derive encore une identite de chaine")
    # Temoin positif: l'appel existe bien ailleurs, dans la commande qui nomme.
    #
    # **Story 11.6 (lot B): il a suivi `calibrate` au coeur** (`EPIC11-ARB-129`).
    # `cli._derive_chain_id` n'est plus qu'un alias de
    # `scan_calibrate.derive_chain_id`, et le seul appel vit dans le
    # consignateur de coeur. Le chercher dans `cli.py` seul rendrait le temoin
    # muet, donc l'assertion d'absence ci-dessus creuse -- c'est exactement ce
    # que ce temoin existe pour empecher.
    consignateur = (REPO_ROOT / "src" / "mixed_media_utility"
                    / "scan_calibrate.py").read_text(encoding="utf-8")
    assert "derive_chain_id(report, scan_locator, logger)" in consignateur


def test_aucune_comparaison_de_chain_id_ne_subsiste_dans_la_designation(tmp_path) -> None:
    """AC 12, test 6: le `chain_id` reste ecrit, et n'est **compare a rien**.

    La preuve est **comportementale** et non textuelle. Trois profils sont designes
    tour a tour dans le meme projet, dont deux dont l'identite ne correspond a rien de
    ce projet: les trois s'appliquent, et chacun rend **ses** coefficients. Une
    comparaison reintroduite, quelle qu'elle soit et quel que soit son cote, ferait
    echouer au moins l'un des trois.

    Ce que le `chain_id` continue de faire, et qui est verifie ici: il descend dans la
    correction comme identite, et il nomme le fichier verse au projet.
    """
    cible = _trois_projets(tmp_path)[1]
    profils = _trois_profils_externes(tmp_path)
    logger = _logger(cible)

    for rang, (chemin, document) in enumerate(profils):
        correction = cli._resolve_designated_correction(
            cible, chemin, logger, correction_requested=True)
        assert correction is not None, (rang, _journal(cible))
        assert correction.chain_id == document["chain_id"], rang
        assert _memes_coefficients(
            correction.profile, cc.profile_from_document(document)), rang
        assert calibration_profile.read_profile(
            cible, document["chain_id"]) == _tel_qu_ecrit(document), rang


# ---------------------------------------------------------------------------
# `EPIC5-ARB-103`: aucun profil par defaut, c'est `None` -- jamais un repli
# ---------------------------------------------------------------------------


def test_sans_defaut_pose_l_entree_par_defaut_est_none_malgre_un_registre_garni(
    tmp_path,
) -> None:
    """Le mutant que la couche 1 a trouve **survivant**, tue ici (`EPIC5-ARB-103`).

    `default_profile_entry` ne se rabat pas sur la premiere entree du registre, et son
    docstring dit pourquoi. Mais aucun test ne le mesurait: un mutant qui introduit ce
    repli restait vert sur les deux lots. Ce n'etait pas un defaut vivant, c'etait un
    trou de couverture -- et le repli en question est celui que `EPIC5-ARB-83`,
    decision 5, interdit **mot pour mot**.

    Le montage rend le repli **possible et tentant**: le registre porte trois entrees,
    les trois fichiers de profil sont sur le disque, et il n'y a qu'une chose qui
    manque -- la designation. C'est le regime nominal d'un scan avec `--profil` mais
    sans `set-default-profile`.

    Classe `M25`, donc trois entrees distinguables et cible **jamais** en premiere
    position: la seconde moitie du test pose le defaut sur le **troisieme** profil et
    exige que ce soit celui-la qui remonte -- un repli sur la premiere entree rendrait
    `chaine-alpha`, qui est la premiere du registre trie **et** la premiere ecrite.
    """
    cible = _trois_projets(tmp_path)[1]
    profils = _trois_profils_externes(tmp_path)
    for chemin, _document in profils:
        designation.import_designated_profile(cible, chemin)

    registre = _color(cible)[designation.DESIGNATED_PROFILES_KEY]
    assert [entree["chain_id"] for entree in registre] == sorted(_CHAINES)
    assert designation.DEFAULT_PROFILE_KEY not in _color(cible)
    for chaine in _CHAINES:
        assert calibration_profile.profile_exists(cible, chaine), chaine

    assert designation.default_profile_entry(cible) is None
    assert designation.default_profile_path(cible) is None

    # Temoin positif, sans lequel les deux assertions ci-dessus seraient vertes sur un
    # mecanisme qui n'existe pas: le defaut **pose** remonte, et c'est le troisieme.
    assert cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", str(cible),
                     cli.PROFILE_FLAG, str(profils[2][0])]) == 0
    entree = designation.default_profile_entry(cible)
    assert entree is not None
    assert entree["chain_id"] == _CHAINES[2]
    assert entree["chain_id"] != registre[0]["chain_id"]
    assert entree["source_page_id"] == profils[2][1]["source_page_id"]


def test_un_defaut_efface_du_manifest_ne_se_recompose_pas_depuis_le_registre(
    tmp_path,
) -> None:
    """Frontiere du precedent, sur le chemin ou le repli serait le plus invisible.

    Le defaut a **existe** puis a ete retire du manifest, le registre gardant ses trois
    entrees. Un repli « il y a bien eu un defaut, prenons-en un » rejouerait ici le
    « mauvais profil applique en silence » que toute la story supprime -- et il le
    rejouerait sur un projet ou tout a l'air normal.
    """
    cible = _trois_projets(tmp_path)[1]
    profils = _trois_profils_externes(tmp_path)
    for chemin, _document in profils:
        designation.import_designated_profile(cible, chemin)
    assert cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", str(cible),
                     cli.PROFILE_FLAG, str(profils[2][0])]) == 0
    assert designation.default_profile_entry(cible) is not None

    chemin_manifest = cible / extraction_manifest.MANIFEST_FILENAME
    manifest = json.loads(chemin_manifest.read_text(encoding="utf-8"))
    del manifest["color"][designation.DEFAULT_PROFILE_KEY]
    chemin_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")

    assert designation.default_profile_entry(cible) is None
    assert designation.default_profile_path(cible) is None
    # Le registre, lui, est intact: c'est bien un repli qui est refuse, pas une
    # absence de donnees.
    assert len(_color(cible)[designation.DESIGNATED_PROFILES_KEY]) == 3


@pytest.mark.parametrize("valeur", [None, [], "chaine-alpha", 42])
def test_un_defaut_mal_forme_rend_none_et_ne_se_rabat_sur_rien(tmp_path, valeur) -> None:
    """Frontiere de type: une entree qui n'est pas un objet ne designe aucun profil.

    Le repli serait ici d'autant plus tentant que « le manifest dit bien quelque
    chose ». Une chaine (`"chaine-alpha"`) est le cas qui mord: elle **ressemble** a une
    identite de chaine, et s'en servir pour recomposer un chemin serait exactement la
    resolution par identite que `EPIC5-ARB-83` supprime.
    """
    cible = _trois_projets(tmp_path)[1]
    for chemin, _document in _trois_profils_externes(tmp_path):
        designation.import_designated_profile(cible, chemin)
    chemin_manifest = cible / extraction_manifest.MANIFEST_FILENAME
    manifest = json.loads(chemin_manifest.read_text(encoding="utf-8"))
    manifest["color"][designation.DEFAULT_PROFILE_KEY] = valeur
    chemin_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")

    assert designation.default_profile_entry(cible) is None
    assert designation.default_profile_path(cible) is None


# ---------------------------------------------------------------------------
# `EPIC5-ARB-101` (voisin): les cles de manifest, epinglees EN LITTERAL
# ---------------------------------------------------------------------------


def test_les_cles_du_manifest_de_profil_sont_epinglees_en_litteral(tmp_path) -> None:
    """Les quatre cles que le `project.json` porte, ecrites **a la main**.

    Asymetrie relevee par la couche 1 de la revue de 5.23: `"color"` etait epingle en
    litteral, ces quatre-la ne l'etaient **nulle part**. Les renommer n'aurait fait
    rougir aucun test, et aurait pourtant orpheline en silence tous les `project.json`
    deja ecrits sur les projets d'Egan -- un profil designe des semaines plus tot
    cessant simplement de s'appliquer.

    Elles sont ecrites en litteral et **pas** lues sur les constantes que le code
    utilise: boucler sur `designation.DESIGNATED_PROFILES_KEY` rejouerait le calcul
    qu'on verifie, et le test resterait vert sous n'importe quel renommage. C'est la
    tautologie que ce depot a payee cinq fois en une semaine.
    """
    assert designation.COLOR_SECTION_KEY == "color"
    assert designation.DESIGNATED_PROFILES_KEY == "calibration_profiles"
    assert designation.DEFAULT_PROFILE_KEY == "default_calibration_profile"
    assert designation.ENTRY_PATH_KEY == "path"
    assert designation.ENTRY_SOURCE_KEY == "designated_from"
    assert designation.ENTRY_DESIGNATED_AT_KEY == "designated_at"

    # Et elles sont bien **celles qui sont ecrites sur le disque**: un renommage cote
    # code qui laisserait les constantes intactes se demasque ici. Les cles sont lues
    # sur le JSON brut, jamais par les accesseurs du module.
    cible = _trois_projets(tmp_path)[1]
    profils = _trois_profils_externes(tmp_path)
    for chemin, _document in profils:
        designation.import_designated_profile(cible, chemin)
    assert cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", str(cible),
                     cli.PROFILE_FLAG, str(profils[2][0])]) == 0

    manifest = json.loads(
        (cible / extraction_manifest.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    section = manifest["color"]
    assert "calibration_profiles" in section, sorted(section)
    assert "default_calibration_profile" in section, sorted(section)
    entrees = section["calibration_profiles"]
    assert [entree["chain_id"] for entree in entrees] == sorted(_CHAINES)
    # La **troisieme** chaine, jamais la premiere: un acces qui prendrait l'entree de
    # tete rendrait `chaine-alpha` et passerait sur une cible en premiere position.
    vise = _entree_de_chaine(entrees, _CHAINES[2])
    assert "path" in vise, sorted(vise)
    assert "designated_from" in vise, sorted(vise)
    assert "designated_at" in vise, sorted(vise)
    assert vise["path"] == "versions/calibration/chaine-mu.json"
    assert vise["designated_from"] == profils[2][0].name
    assert (cible / vise["path"]).is_file()
    assert section["default_calibration_profile"]["chain_id"] == _CHAINES[2]


# ---------------------------------------------------------------------------
# Un fichier de profil non-UTF-8: refus nomme, jamais un traceback
# ---------------------------------------------------------------------------


#: Des octets qui ne sont **pas** de l'UTF-8: une nomenclature UTF-16 suivie de texte.
#: C'est ce qu'un operateur designe reellement par erreur -- un profil exporte par un
#: outil Windows, ou une image renommee.
_OCTETS_NON_UTF8 = b"\xff\xfe{ \x00\"\x00c\x00h\x00a\x00i\x00n\x00\"\x00 \x00}\x00"


def test_un_profil_designe_non_utf8_est_un_refus_nomme(tmp_path) -> None:
    """Le bloquant de la revue de 5.23, ferme: `--profil <fichier binaire>`.

    `read_text(encoding="utf-8")` leve un `UnicodeDecodeError`, qui derive de
    `ValueError` et **pas** d'`OSError`: il traversait donc le garde-fou du module et
    tuait le scan en traceback, **avant l'ecriture des frames**. C'est la famille du
    bloquant `C2` de la revue de 5.22 -- que ce module cite lui-meme comme motif de son
    propre `record=False` --, sur le seul chemin par lequel un fichier que le projet
    n'a pas produit entre ici.

    La mesure porte sur le **type** de l'exception, parce que c'est lui qui decide si la
    commande rend un refus ou un traceback, et sur le fait qu'elle nomme le chemin --
    la seule chose que l'operateur puisse corriger.
    """
    binaire = tmp_path / "ailleurs" / "profil.json"
    binaire.parent.mkdir(parents=True)
    binaire.write_bytes(_OCTETS_NON_UTF8)

    with pytest.raises(designation.ProfileDesignationError) as excinfo:
        designation.read_designated_document(binaire)

    assert str(binaire) in str(excinfo.value)
    assert "UTF-8" in str(excinfo.value)


def test_le_scan_ne_meurt_pas_sur_un_profil_designe_non_utf8(tmp_path) -> None:
    """Bout de chaine du precedent: la commande **rend** au lieu de lever.

    C'est ce qui separe « le lot est livre brut avec un refus nomme » de « le scan
    meurt en traceback avant d'ecrire une seule frame ». Un `UnicodeDecodeError` nu
    remonterait jusqu'ici sans etre rattrape -- `cli` n'attrape que
    `ProfileDesignationError` --, et
    le test l'attraperait sous `pytest.raises(Exception)` s'il etait ecrit ainsi: il ne
    l'est pas, la mesure est que l'appel **rende**.
    """
    cible = _trois_projets(tmp_path)[1]
    binaire = tmp_path / "ailleurs" / "profil.json"
    binaire.parent.mkdir(parents=True)
    binaire.write_bytes(_OCTETS_NON_UTF8)
    logger = _logger(cible)

    correction = cli._resolve_designated_correction(
        cible, binaire, logger, correction_requested=True)

    assert correction is None or not correction.available
    assert "UTF-8" in _journal(cible)


def test_un_profil_du_projet_non_utf8_est_un_refus_nomme_et_non_un_traceback(
    tmp_path,
) -> None:
    """Le meme defaut sur l'autre porte: `calibration_profile.read_profile`.

    Les deux modules ouvrent un fichier de profil, les deux le faisaient sous le seul
    `except OSError`. Fermer une porte et laisser l'autre aurait deplace le traceback
    au lieu de le supprimer -- et c'est celle-ci qui s'ouvre sur un fichier **du
    projet**, donc sur un scan qui ne designe rien du tout.

    Le refus est un `ProfileValidationError` et non un `ProfileNotFoundError`: le
    fichier est bien la. Les confondre ferait dire « regenerez-le » a un operateur dont
    le profil existe et n'est pas du texte.
    """
    cible = _trois_projets(tmp_path)[1]
    chemin = calibration_profile.profile_path(cible, _CHAINES[1])
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(_OCTETS_NON_UTF8)

    with pytest.raises(calibration_profile.ProfileValidationError) as excinfo:
        calibration_profile.read_profile(cible, _CHAINES[1])

    assert not isinstance(excinfo.value, calibration_profile.ProfileNotFoundError)
    assert "UTF-8" in str(excinfo.value)
    assert _CHAINES[1] in str(excinfo.value)


# ---------------------------------------------------------------------------
# `EPIC5-ARB-101`: la frontiere negative du reste inerte retire
# ---------------------------------------------------------------------------


def test_aucun_comparateur_de_chain_id_ne_survit_hors_de_l_upsert() -> None:
    """`EPIC5-ARB-101`: `find_registered_profile` est retire, et il ne revient pas.

    C'etait un comparateur de `chain_id` **sans aucun appelant de production**, dans le
    module precis dont toute la doctrine est « aucun appariement par `chain_id` ». Son
    docstring lui pretait un role -- dedoublonner le registre -- que `_upsert` tient
    seul. Un reste inerte de cette nature n'est pas neutre: c'est la fonction qu'une
    story suivante reutilise pour apparier, en toute bonne foi.

    La frontiere est **negative et mesuree sur la source**, pas sur un `hasattr`: une
    fonction reintroduite sous un autre nom passerait le `hasattr`. Elle compte les
    fonctions du module qui comparent un `chain_id`, et il doit y en avoir exactement
    une.
    """
    assert not hasattr(designation, "find_registered_profile")

    arbre = ast.parse(inspect.getsource(designation))
    comparateurs = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.FunctionDef):
            continue
        for interne in ast.walk(noeud):
            if isinstance(interne, ast.Compare) and any(
                    isinstance(operateur, (ast.Eq, ast.NotEq))
                    for operateur in interne.ops):
                texte = ast.dump(interne)
                if "'chain_id'" in texte or "chain_id" in texte:
                    comparateurs.add(noeud.name)
    assert comparateurs == {"_upsert"}, sorted(comparateurs)
