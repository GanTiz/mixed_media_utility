"""Story 5.23, AC 8quater: **l'operateur nomme son profil de calibration**.

Mandat: `EPIC5-ARB-83`, geste 3 -- le dernier des quatre. Verbatim d'Egan:

    « La commande de scan pour generer ce fichier demande a l'utilisateur un **nom
    personnalise** pour le fichier de calibration genere (le titre dans le qr a pu etre
    "hp envy 4520 tiff 600 dpi auto corr off" mais l'utilisateur veut lire "scanner
    maison default tiff" comme nom de fichier). On peut egalement demander un
    **commentaire (facultatif)** qu'on verra par survol sur le fichier de calibration
    dans la GUI. On stockera bien les infos officielles mais on laissera l'utilisateur
    nommer les choses. »

Ce que cette suite mesure, et **ce qu'elle mesure contre**. Le piege de cette AC n'est
pas le nommage, qui est mecanique: c'est que l'etiquette devienne une seconde **cle**.
La story precedente (AC 12) vient de supprimer le dernier appariement automatique --
un profil se resout **par le chemin ecrit**, jamais par recomposition depuis le
`chain_id`. Une etiquette qu'un chemin de code consulterait pour *choisir* un profil
reintroduirait exactement ce que `EPIC5-ARB-83` supprime, sous un nom plus sympathique.
La moitie de ce fichier est donc ecrite contre cette possibilite, et deux tests posent
la question a l'envers: ils **detournent** le chemin, l'etiquette et l'identite les uns
des autres, et exigent que seul le chemin decide.

Le second piege, mesure et non suppose: l'ancienne formulation de l'AC craignait que
**renommer** un profil le rende introuvable. L'AC 12 a rendu cette crainte sans objet
-- c'est le chemin qui fait foi -- et deux tests le **prouvent** au lieu de l'affirmer.

Regle des fabriques (`CLAUDE.md`), appliquee partout ou une collection est manipulee:

* les profils vont par **trois**, distinguables au coefficient pres (trois presses),
  et la cible n'est jamais la premiere -- ni dans l'ordre d'ecriture, ni dans l'ordre
  alphabetique du dossier `versions/calibration/`;
* les etiquettes des trois sont **deux a deux distinctes**, et leurs slugs aussi: une
  fabrique qui les remplirait d'un meme nom rendrait invisible toute collision.

AC 9: ce fichier ne synthetise aucun raster de scan complet. Les seuls passages par la
CLI substituent `_fit_lot_correction` -- l'ajustement lui-meme est eprouve contre les
vrais producteurs dans la moitie couleur -- et ingerent une page unie de 400x600.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import cli  # noqa: E402
from mixed_media_utility import color_calibration as cc  # noqa: E402
from mixed_media_utility import scan_calibrate  # noqa: E402
from mixed_media_utility.io import calibration_profile  # noqa: E402
from mixed_media_utility.io import extraction_manifest  # noqa: E402
from mixed_media_utility.io import manifest as manifest_module  # noqa: E402
from mixed_media_utility.io import naming  # noqa: E402
from mixed_media_utility.io import profile_designation as designation  # noqa: E402

import test_calibration_page_source as couleur  # noqa: E402
import test_profil_designe as designe  # noqa: E402


# ---------------------------------------------------------------------------
# Fabriques -- trois de tout, cible jamais en premiere position
# ---------------------------------------------------------------------------

#: Trois etiquettes **deux a deux distinctes**, dont les slugs le sont aussi. La
#: deuxieme est celle du mandat d'Egan, mot pour mot; la troisieme porte des accents,
#: parce que c'est ce qu'un operateur tape reellement.
#:
#: Elle portait aussi une ponctuation (`"Zone Nord Été 2026 essai"`) jusqu'au
#: 2026-08-19: `EPIC5-ARB-99` geste 1 la **refuse** desormais, et ce refus est mesure
#: par `test_une_etiquette_portant_des_caracteres_speciaux_est_refusee`, qui reprend
#: cette valeur exacte. Le slug attendu, lui, est inchange -- c'est ce qui prouve que
#: la ponctuation ne portait aucune information de nom.
#:
#: L'ordre alphabetique des slugs (`atelier-...`, `scanner-maison-...`, `zone-...`) ne
#: suit **pas** l'ordre des chaines de `test_profil_designe` (`chaine-alpha`,
#: `chaine-zeta`, `chaine-mu`): un test qui prendrait « le premier fichier du dossier »
#: se demasque, quel que soit le critere de tri qu'il emploie.
_ETIQUETTES = (
    "atelier du fond 300 dpi",
    "scanner maison default tiff",
    "Zone Nord Été 2026 essai",
)

#: Les slugs attendus, **ecrits en litteral**. Les deriver par `slugify_label` serait la
#: tautologie deja payee deux fois dans ce depot: le test rejouerait le calcul qu'il est
#: cense verifier, et toute recette fautive resterait verte.
_SLUGS = (
    "atelier-du-fond-300-dpi",
    "scanner-maison-default-tiff",
    "zone-nord-ete-2026-essai",
)


def test_la_fabrique_tient_sa_promesse_trois_etiquettes_et_trois_slugs() -> None:
    """Trois etiquettes distinctes, trois slugs distincts, et trois presses distinctes.

    Sans ce garde-fou, tout ce fichier serait vert sur des profils indiscernables --
    exactement le defaut que la regle des fabriques existe pour empecher, et qui a
    coute trois stories dans ce depot.
    """
    assert len(set(_ETIQUETTES)) == 3, _ETIQUETTES
    assert len(set(_SLUGS)) == 3, _SLUGS
    assert len(set(designe._CHAINES)) == 3, designe._CHAINES
    coefficients = [
        json.dumps(designe._document(chaine, presse)["coefficients"], sort_keys=True)
        for chaine, presse in zip(designe._CHAINES, designe._PRESSES)]
    assert len(set(coefficients)) == 3, coefficients


def _document_etiquete(rang: int, *, commentaire: str = "") -> dict:
    """Le document du rang donne, **etiquete**: identite, presse et nom lies au rang."""
    profil = couleur._calibration_profile(press=designe._PRESSES[rang])
    return cc.profile_to_document(
        profil,
        chain_id=designe._CHAINES[rang],
        source_page_id=f"{designe._CHAINES[rang]}-p0",
        template_id=couleur.TEMPLATE,
        read_patch_count=18,
        retained_patch_count=18,
        ink_floor_excluded=cc.correction_form_excludes_ink_floor(profil.correction_id),
        label=_ETIQUETTES[rang],
        comment=commentaire,
    )


def _dossier_des_profils(project_dir: Path) -> Path:
    return (project_dir / calibration_profile.VERSIONS_DIRNAME
            / calibration_profile.CALIBRATION_DIRNAME)


def _noms_des_profils(project_dir: Path) -> list[str]:
    dossier = _dossier_des_profils(project_dir)
    return sorted(chemin.name for chemin in dossier.glob("*.json"))


# ---------------------------------------------------------------------------
# Le nommage: le fichier porte le nom de l'operateur, pas le `chain_id` brut
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("etiquette,slug", list(zip(_ETIQUETTES, _SLUGS)))
def test_le_slug_d_une_etiquette_est_celui_attendu_en_litteral(etiquette, slug) -> None:
    """La recette du slug, confrontee a des valeurs **ecrites a la main**.

    Le cas du milieu est le mandat d'Egan mot pour mot: il veut lire
    `scanner maison default tiff`, il doit obtenir `scanner-maison-default-tiff`.
    Le troisieme prouve que les accents sont deplies (« Ete » -> `ete`) et que la
    ponctuation ne survit pas -- une etiquette reelle en porte toujours.
    """
    assert calibration_profile.slugify_label(etiquette) == slug


def test_deux_etiquettes_distinctes_font_deux_fichiers(tmp_path) -> None:
    """AC 8quater, test (nommage): « Deux noms distincts -> deux fichiers. »

    Les deux profils portent la **meme** identite de chaine et des coefficients
    differents: si le nom du fichier descendait encore du `chain_id`, le second
    ecraserait le premier et le dossier n'en porterait qu'un. La mesure porte sur les
    **coefficients relus**, pas sur la seule presence des fichiers (`EPIC5-ARB-39`).
    """
    projet = tmp_path / "projet"
    premier = _document_etiquete(0)
    second = dict(_document_etiquete(1))
    second["chain_id"] = premier["chain_id"]

    chemin_premier = calibration_profile.write_profile(
        projet, premier)
    chemin_second = calibration_profile.write_profile(
        projet, second)

    assert chemin_premier != chemin_second
    assert _noms_des_profils(projet) == [
        "atelier-du-fond-300-dpi.json", "scanner-maison-default-tiff.json"]
    relu_premier = json.loads(chemin_premier.read_text(encoding="utf-8"))
    relu_second = json.loads(chemin_second.read_text(encoding="utf-8"))
    assert relu_premier["coefficients"] == premier["coefficients"]
    assert relu_second["coefficients"] == second["coefficients"]
    assert relu_premier["coefficients"] != relu_second["coefficients"]


def test_un_profil_sans_etiquette_reste_nomme_par_sa_chaine(tmp_path) -> None:
    """Le repli, et il n'a rien d'un detail: c'est la retrocompatibilite du chemin.

    Un profil que personne n'a nomme s'ecrit exactement la ou la story 5.22 l'ecrivait.
    Un slug qui s'appliquerait aussi au `chain_id` deplacerait, en silence, tous les
    profils deja poses sur les projets d'Egan.
    """
    projet = tmp_path / "projet"
    document = designe._document(designe._CHAINES[1], designe._PRESSES[1])
    assert calibration_profile.LABEL_FIELD not in document

    chemin = calibration_profile.write_profile(projet, document)

    assert chemin.name == "chaine-zeta.json"
    assert _noms_des_profils(projet) == ["chaine-zeta.json"]


def test_une_etiquette_qui_ne_nomme_aucun_fichier_est_refusee(tmp_path) -> None:
    """Frontiere: `'!!!'` n'est pas un nom, et le silence serait pire que le refus.

    Se rabattre sur le `chain_id` ferait croire a l'operateur que son nom a ete pris.
    Rien n'est ecrit: le dossier des profils n'existe meme pas.
    """
    projet = tmp_path / "projet"
    document = dict(_document_etiquete(1))
    # Amende le 2026-08-19: la valeur d'origine (`"!!! ??? ***"`) tombe desormais sur le
    # refus **des caracteres speciaux**, en amont. Celle-ci ne porte que des caracteres
    # admis et ne laisse pourtant aucun slug -- c'est le seul materiau qui atteint
    # encore ce refus-ci, et c'est ce qui le garde vivant plutot que mort.
    document[calibration_profile.LABEL_FIELD] = "- _ -"

    with pytest.raises(calibration_profile.ProfileValidationError) as excinfo:
        calibration_profile.write_profile(projet, document)

    assert "nommable" in str(excinfo.value)
    assert not _dossier_des_profils(projet).exists()


#: Les etiquettes de `EPIC5-ARB-99`, mot pour mot: deux d'entre elles portent des
#: caracteres speciaux, la troisieme n'en porte aucun. Ecrites ensemble parce que c'est
#: leur **contraste** qui porte la decision -- le refus des caracteres speciaux ne ferme
#: pas la collision, il la reduit.
_ETIQUETTES_DE_LA_COLLISION = (
    "HP Envy 4520",
    "hp  envy  4520!",
    "HP ENVY /4520/",
)


@pytest.mark.parametrize("etiquette", [
    "hp  envy  4520!", "HP ENVY /4520/", "!!! ??? ***", "../../evade",
    "Zone Nord -- Été 2026 (essai)", "scanner;maison", "profil\ttabule",
])
def test_une_etiquette_portant_des_caracteres_speciaux_est_refusee(
    tmp_path, etiquette,
) -> None:
    """`EPIC5-ARB-99`, geste 1: « refus des caracteres speciaux ».

    Ce qui change, et ce n'est pas cosmetique: ces etiquettes s'ecrivaient toutes
    **sans un mot**, reduites en tirets. `"HP ENVY /4520/"` devenait `hp-envy-4520`,
    c'est-a-dire le nom d'un **autre** profil, et l'operateur n'apprenait jamais que le
    nom qu'il lisait n'etait pas celui qu'il avait tape.

    Le refus est nomme, il cite les caracteres, et **rien n'est ecrit**: le dossier des
    profils n'existe meme pas.
    """
    projet = tmp_path / "projet"
    document = dict(_document_etiquete(1))
    document[calibration_profile.LABEL_FIELD] = etiquette

    with pytest.raises(calibration_profile.ProfileValidationError) as excinfo:
        calibration_profile.write_profile(projet, document)

    assert "caracteres refuses" in str(excinfo.value)
    assert not _dossier_des_profils(projet).exists()


def test_le_refus_des_caracteres_speciaux_ne_ferme_pas_la_collision(tmp_path) -> None:
    """Frontiere negative du precedent, et c'est **elle** qui porte `EPIC5-ARB-99`.

    Verbatim de la decision: « attention, cela ne suffit pas: `"HP Envy 4520"` et
    `"hp envy 4520"` sont tous deux sans caractere special et collisionnent quand
    meme. C'est l'invite qui ferme le defaut, pas ce refus ».

    Le test le **mesure** au lieu de le repeter: les deux etiquettes passent le refus,
    et leur slug est le meme. Un correctif qui se serait arrete au geste 1 rougirait
    ici -- et c'est exactement l'erreur qu'un lecteur presse aurait commise.
    """
    assert calibration_profile.slugify_label("HP Envy 4520") == "hp-envy-4520"
    assert calibration_profile.slugify_label("hp envy 4520") == "hp-envy-4520"
    assert _ETIQUETTES_DE_LA_COLLISION[0] != "hp envy 4520"
    # Et les deux autres du mandat, elles, sont bien refusees en amont.
    for etiquette in _ETIQUETTES_DE_LA_COLLISION[1:]:
        with pytest.raises(calibration_profile.ProfileValidationError):
            calibration_profile.slugify_label(etiquette)


#: Deux etiquettes **distinctes** dont les slugs partagent leurs 48 premiers caracteres
#: et divergent apres. Elles sont le materiel du mutant « le slug collisionne deux noms
#: distincts en un seul fichier », dans sa seule forme realiste: une troncature au
#: budget d'identifiant du depot.
_ETIQUETTES_LONGUES = (
    "scanner maison de l atelier du fond en tiff a six cents dpi",
    "scanner maison de l atelier du fond en tiff a six cent cinquante dpi",
)

#: Le nom de fichier **unique** que produirait une troncature des deux precedentes,
#: ecrit en litteral: c'est la collision elle-meme, nommee.
_PREFIXE_TRONQUE = "scanner-maison-de-l-atelier-du-fond-en-tiff-a-si"


def test_une_etiquette_trop_longue_est_refusee_et_non_tronquee(tmp_path) -> None:
    """Frontiere de collision: deux etiquettes distinctes partageant leur debut.

    Tronquer les ferait porter le **meme** fichier, donc ecraser le premier profil par
    le second, en silence, sur le geste meme que cette AC existe pour rendre fiable.
    Elles sont donc refusees, et l'operateur raccourcit lui-meme -- c'est lui qui nomme.
    """
    projet = tmp_path / "projet"
    assert len(_PREFIXE_TRONQUE) == calibration_profile.CANONICAL_ID_MAX_LENGTH
    assert _ETIQUETTES_LONGUES[0] != _ETIQUETTES_LONGUES[1]
    for etiquette in _ETIQUETTES_LONGUES:
        document = dict(_document_etiquete(1))
        document[calibration_profile.LABEL_FIELD] = etiquette
        with pytest.raises(calibration_profile.ProfileValidationError) as excinfo:
            calibration_profile.write_profile(projet, document)
        assert "trop longue" in str(excinfo.value)
    assert not _dossier_des_profils(projet).exists()


@pytest.mark.parametrize("etiquette", [
    "../../evade", "..\\..\\evade", "versions/calibration/evade", "profil.json",
])
def test_une_etiquette_ne_peut_pas_sortir_du_dossier_des_profils(
    tmp_path, etiquette,
) -> None:
    """Frontiere de securite: une etiquette est du texte libre, et elle nomme un fichier.

    C'est le second chemin -- avec le `chain_id` d'un profil externe -- par lequel une
    valeur non derivee atteint un nom de fichier. Une remontee de chemin ecrirait hors
    du projet.

    **Durci le 2026-08-19** (`EPIC5-ARB-99`, geste 1): jusque-la `../../evade` etait
    *neutralise* en `evade.json` -- sur, mais muet. La neutralisation silencieuse est
    precisement ce que la decision retire: elle ecrivait un fichier sous un nom que
    l'operateur n'avait pas demande, et le meme mecanisme confondait deux etiquettes
    distinctes en un seul fichier. Le refus est nomme, et rien n'est ecrit.
    """
    projet = tmp_path / "projet"
    document = dict(_document_etiquete(1))
    document[calibration_profile.LABEL_FIELD] = etiquette

    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.write_profile(projet, document)

    assert not _dossier_des_profils(projet).exists()


# ---------------------------------------------------------------------------
# L'identite officielle reste intacte: l'etiquette s'ajoute, elle ne remplace rien
# ---------------------------------------------------------------------------


def test_l_etiquette_ne_remplace_rien_du_document(tmp_path) -> None:
    """AC 8quater, test (l'identite officielle reste).

    Les champs officiels sont **enumeres en litteral** et confrontes a des valeurs
    litterales la ou elles sont connues: les lire sur une constante du code serait la
    tautologie deja payee sur l'AC 12 et sur la story 5.9.
    """
    projet = tmp_path / "projet"
    document = _document_etiquete(1, commentaire="scanner du salon, vitre nettoyee")

    chemin = calibration_profile.write_profile(projet, document)
    relu = json.loads(chemin.read_text(encoding="utf-8"))

    assert relu["chain_id"] == "chaine-zeta"
    assert relu["source_page_id"] == "chaine-zeta-p0"
    assert relu["template_id"] == "tpl-a4-portrait-2f-v1"
    assert relu["read_patch_count"] == 18
    assert relu["retained_patch_count"] == 18
    assert relu["schema_version"] == 1
    assert relu["correction_form_id"] == document["correction_form_id"]
    assert relu["ink_floor_excluded"] == document["ink_floor_excluded"]
    assert relu["coefficients"] == document["coefficients"]
    # Et l'etiquette est bien la, a cote et non a la place.
    assert relu["label"] == "scanner maison default tiff"
    assert relu["comment"] == "scanner du salon, vitre nettoyee"


def test_l_etiquette_ne_chasse_pas_les_temoins_bruts(tmp_path) -> None:
    """Frontiere du precedent, sur le champ le plus recent et le plus fragile.

    `witness_raw_bgr` est arrive dans le document trois jours avant l'etiquette
    (`e2baf70`). Un document construit avec les deux doit porter les deux: c'est la
    mesure de la divergence brute a brute qui disparaitrait sinon, et elle ne se
    remarquerait que des mois plus tard, sur un manifeste.
    """
    projet = tmp_path / "projet"
    profil = couleur._calibration_profile(press=designe._PRESSES[1])
    document = cc.profile_to_document(
        profil,
        chain_id=designe._CHAINES[1],
        source_page_id="page-temoin",
        template_id=couleur.TEMPLATE,
        read_patch_count=18,
        retained_patch_count=18,
        ink_floor_excluded=cc.correction_form_excludes_ink_floor(profil.correction_id),
        witness_raw_bgr=(("neutral-065", (0.245, 0.248, 0.251)),
                         ("neutral-120", (0.470, 0.472, 0.469))),
        label=_ETIQUETTES[1],
    )

    chemin = calibration_profile.write_profile(projet, document)
    relu = json.loads(chemin.read_text(encoding="utf-8"))

    assert chemin.name == "scanner-maison-default-tiff.json"
    assert relu["witness_raw_bgr"] == [
        ["neutral-065", [0.245, 0.248, 0.251]],
        ["neutral-120", [0.47, 0.472, 0.469]],
    ]
    assert relu["label"] == "scanner maison default tiff"


# ---------------------------------------------------------------------------
# La resolution ne change pas: le chemin ecrit fait foi, jamais l'etiquette
# ---------------------------------------------------------------------------


def _projet_a_trois_profils_etiquetes(tmp_path: Path) -> tuple:
    """Un projet portant **trois** profils etiquetes, la cible en **derniere** position.

    Les trois sont ecrits dans l'ordre 0, 1, 2 et leurs slugs sont dans l'ordre
    alphabetique 0, 1, 2: la cible (rang 2) n'est donc ni la premiere ecrite, ni la
    premiere du dossier trie, ni la premiere du registre trie par `chain_id`
    (`chaine-alpha` < `chaine-mu` < `chaine-zeta`, la cible portant `chaine-mu`).
    """
    projet = designe._trois_projets(tmp_path)[1]
    chemins = []
    for rang in range(3):
        document = _document_etiquete(rang, commentaire=f"note du rang {rang}")
        externe = tmp_path / f"ailleurs-{rang}" / "profil.json"
        externe.parent.mkdir(parents=True, exist_ok=True)
        externe.write_text(calibration_profile.serialize_profile(document),
                           encoding="utf-8")
        chemins.append(externe)
    return projet, chemins


def test_trois_profils_etiquetes_le_designe_est_celui_qui_s_applique(tmp_path) -> None:
    """AC 8quater, test (resolution au scan), reecrit le 2026-08-18.

    Trois profils etiquetes dans le meme projet, la cible **ailleurs qu'en premiere
    position**: le profil applique est celui que l'operateur **designe par son chemin**.
    La mesure porte sur les coefficients rendus, jamais sur la presence d'un champ.
    """
    projet, chemins = _projet_a_trois_profils_etiquetes(tmp_path)
    for chemin in chemins:
        designation.import_designated_profile(projet, chemin)

    correction = cli._resolve_designated_correction(
        projet, chemins[2], designe._logger(projet), correction_requested=True)

    assert correction is not None
    attendu = cc.profile_from_document(_document_etiquete(2))
    assert designe._memes_coefficients(correction.profile, attendu)
    # Temoin negatif: ce n'est pas le premier profil du projet qui est rendu.
    premier = cc.profile_from_document(_document_etiquete(0))
    assert not designe._memes_coefficients(correction.profile, premier)


def test_l_etiquette_n_est_jamais_une_cle_de_resolution(tmp_path) -> None:
    """Le piege central: l'etiquette **ne choisit rien**, meme quand elle le pourrait.

    Le montage detourne les trois designations les unes des autres. Le defaut du projet
    pointe, **par son chemin**, sur le fichier du rang 2; l'entree porte pourtant
    l'etiquette et le `chain_id` du rang 0. Une resolution par etiquette rendrait le
    fichier du rang 0 (`atelier-du-fond-300-dpi.json`, present sur le disque), une
    resolution par identite le rendrait aussi; seule une resolution **par le chemin
    ecrit** rend celui du rang 2.
    """
    projet, chemins = _projet_a_trois_profils_etiquetes(tmp_path)
    for chemin in chemins:
        designation.import_designated_profile(projet, chemin)
    assert cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", str(projet),
                     cli.PROFILE_FLAG, str(chemins[0])]) == 0

    manifest_path = projet / "project.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entree = manifest["color"][designation.DEFAULT_PROFILE_KEY]
    assert entree["label"] == _ETIQUETTES[0]
    assert entree["chain_id"] == designe._CHAINES[0]
    entree[designation.ENTRY_PATH_KEY] = (
        f"{calibration_profile.VERSIONS_DIRNAME}/"
        f"{calibration_profile.CALIBRATION_DIRNAME}/{_SLUGS[2]}.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")

    resolu = designation.default_profile_path(projet)

    assert resolu is not None
    assert resolu.name == "zone-nord-ete-2026-essai.json"
    document = designation.read_designated_document(resolu)
    assert document["chain_id"] == designe._CHAINES[2]


def test_renommer_le_fichier_d_un_profil_ne_le_rend_pas_introuvable(tmp_path) -> None:
    """AC 8quater: « renommer un profil ne le rend pas introuvable ».

    C'etait la crainte qui justifiait l'ancienne formulation de cette AC, et l'AC 12 l'a
    rendue sans objet -- ce test le **prouve** au lieu de l'affirmer. Le fichier designe
    est renomme sur le disque en un nom qui ne ressemble ni a son `chain_id`, ni au slug
    de son etiquette; il s'applique exactement pareil, parce que c'est le chemin que
    l'operateur ecrit qui fait foi.
    """
    projet, chemins = _projet_a_trois_profils_etiquetes(tmp_path)
    renomme = chemins[2].with_name("un-nom-que-personne-ne-devine.json")
    chemins[2].rename(renomme)
    assert not chemins[2].exists()

    correction = cli._resolve_designated_correction(
        projet, renomme, designe._logger(projet), correction_requested=True)

    assert correction is not None
    assert designe._memes_coefficients(
        correction.profile, cc.profile_from_document(_document_etiquete(2)))


def test_un_defaut_dont_le_fichier_a_ete_renomme_ne_se_recompose_pas(tmp_path) -> None:
    """Frontiere negative du precedent, et c'est elle qui compte.

    Le fichier du defaut est renomme **sans** que l'entree de manifest le suive. Deux
    replis seraient tentants et sont tous deux interdits: recomposer
    `versions/calibration/<chain_id>.json`, ou retrouver le fichier par le slug de son
    etiquette -- les deux existent encore ailleurs dans le dossier. La resolution rend
    `None`, l'operateur redesigne. Un repli ici serait l'appariement automatique que
    `EPIC5-ARB-83` supprime, reintroduit par une porte que personne ne regarde.
    """
    projet, chemins = _projet_a_trois_profils_etiquetes(tmp_path)
    for chemin in chemins:
        designation.import_designated_profile(projet, chemin)
    assert cli.main([cli.SET_DEFAULT_PROFILE_COMMAND, "--project", str(projet),
                     cli.PROFILE_FLAG, str(chemins[2])]) == 0
    assert designation.default_profile_path(projet) is not None

    dossier = _dossier_des_profils(projet)
    deplace = dossier / "deplace-a-la-main.json"
    (dossier / f"{_SLUGS[2]}.json").rename(deplace)
    # Et les deux noms qu'un repli irait chercher sont **poses sur le disque**, pour que
    # la mesure porte sur un repli possible et non sur une absence: l'identite de la
    # chaine du defaut, et le slug de l'etiquette d'un autre profil.
    (dossier / f"{designe._CHAINES[2]}.json").write_text(
        deplace.read_text(encoding="utf-8"), encoding="utf-8")
    assert (dossier / f"{_SLUGS[0]}.json").is_file()

    assert designation.default_profile_path(projet) is None


# ---------------------------------------------------------------------------
# Le commentaire: optionnel, stocke, et son absence n'est pas un refus
# ---------------------------------------------------------------------------


def test_le_commentaire_est_stocke_tel_quel(tmp_path) -> None:
    """AC 8quater, test (commentaire): il est stocke, et relu a l'identique."""
    projet = tmp_path / "projet"
    texte = "scanner du salon; auto-correction coupee le 12/08, vitre nettoyee"
    document = _document_etiquete(1, commentaire=texte)

    chemin = calibration_profile.write_profile(projet, document)

    assert json.loads(chemin.read_text(encoding="utf-8"))["comment"] == texte


def test_l_absence_de_commentaire_n_est_pas_un_refus(tmp_path) -> None:
    """AC 8quater: le commentaire est **facultatif**. Un profil sans lui s'ecrit.

    Le mutant vise est « le commentaire absent traite comme un refus »: un profil
    etiquete mais sans commentaire s'ecrit, se relit, et son commentaire vaut la chaine
    vide -- jamais `None`, jamais une exception.
    """
    projet = tmp_path / "projet"
    document = _document_etiquete(1)
    assert calibration_profile.COMMENT_FIELD not in document

    chemin = calibration_profile.write_profile(projet, document)

    assert chemin.name == "scanner-maison-default-tiff.json"
    # Le fichier ecrit porte le **defaut** du champ, comme `acceptance` depuis 5.22:
    # l'ecriture serialise le document normalise, et la normalisation est idempotente.
    assert json.loads(chemin.read_text(encoding="utf-8"))["comment"] == ""
    relu = calibration_profile.read_profile(projet, "scanner-maison-default-tiff")
    assert relu["comment"] == ""
    assert relu["label"] == "scanner maison default tiff"


def test_le_commentaire_n_est_pas_affiche_par_la_commande(tmp_path, monkeypatch,
                                                          capsys) -> None:
    """AC 8quater: « il est stocke, il n'est pas affiche par la CLI ».

    Il est destine au survol dans la GUI (Epic 7). Le message de fin nomme l'etiquette
    -- l'operateur doit pouvoir verifier que son fichier porte bien son nom -- et
    n'imprime pas le commentaire.
    """
    projet, dossier = _scan_calibrable(tmp_path, monkeypatch)
    assert cli.main([
        "scan", "--project", str(projet), "--scan", str(dossier), "--dpi", "600",
        "calibrate", cli.PROFILE_NAME_FLAG, _ETIQUETTES[1],
        cli.PROFILE_COMMENT_FLAG, "vitre nettoyee le 12 aout",
    ]) == 0

    sortie = capsys.readouterr().out
    assert "scanner maison default tiff" in sortie
    assert "vitre nettoyee" not in sortie


# ---------------------------------------------------------------------------
# Retrocompatibilite: un profil ecrit AVANT cette AC se relit sans refus
# ---------------------------------------------------------------------------


def test_un_profil_ecrit_avant_cette_ac_se_relit_sans_refus(tmp_path) -> None:
    """AC 8quater, test (champs optionnels): la fusion pure donne leur defaut.

    Le document est ecrit **a la main sur le disque**, sans `label` ni `comment`, comme
    l'aurait fait la story 5.22. La relecture ne refuse pas, et complete les deux par
    la chaine vide. C'est le meme dispositif que celui deja tenu pour `witness_raw_bgr`,
    a une difference pres, qui est le motif du choix: pour les temoins, « pas mesure »
    et « mesure, rien trouve » sont deux faits distincts, donc le defaut est l'absence;
    pour une etiquette, « rien nomme » et « nomme vide » disent la meme chose.
    """
    projet = tmp_path / "projet"
    ancien = designe._document(designe._CHAINES[1], designe._PRESSES[1])
    assert "label" not in ancien and "comment" not in ancien
    chemin = calibration_profile.profile_path(projet, ancien["chain_id"])
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(ancien, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")

    relu = calibration_profile.read_profile(projet, ancien["chain_id"])

    assert relu["label"] == ""
    assert relu["comment"] == ""
    assert relu["chain_id"] == "chaine-zeta"
    assert relu["coefficients"] == ancien["coefficients"]


def test_un_profil_ancien_se_designe_et_s_inscrit_au_manifest_sans_etiquette(
    tmp_path,
) -> None:
    """Retrocompatibilite du bout de la chaine: l'entree autoportante se construit.

    Le mutant vise est « la retrocompatibilite cassee sur un profil ancien » dans sa
    forme la plus probable: une entree de manifest construite par acces **nu** aux deux
    champs neufs. C'est la famille des six acces nus payes dans l'AC 10 de cette meme
    story, et elle ne se voit qu'ici -- le fichier, lui, se relit tres bien.
    """
    projet = designe._trois_projets(tmp_path)[1]
    ancien = designe._document(designe._CHAINES[1], designe._PRESSES[1])
    externe = tmp_path / "ailleurs" / "vieux-profil.json"
    externe.parent.mkdir(parents=True, exist_ok=True)
    externe.write_text(calibration_profile.serialize_profile(ancien), encoding="utf-8")

    document, chemin = designation.import_designated_profile(projet, externe)

    assert chemin.name == "chaine-zeta.json"
    entree = designe._entree_de_chaine(
        designe._color(projet)[designation.DESIGNATED_PROFILES_KEY],
        designe._CHAINES[1])
    assert entree is not None
    assert entree["label"] == ""
    assert entree["comment"] == ""
    assert entree["chain_id"] == "chaine-zeta"


def test_un_document_sans_etiquette_est_octet_pour_octet_celui_de_5_22(
    tmp_path,
) -> None:
    """Frontiere: les deux champs neufs sont **absents du document** quand ils sont vides.

    C'est le producteur (`profile_to_document`) qui les omet, pas l'ecriture: le fichier
    ecrit, lui, porte leur defaut, exactement comme `acceptance` depuis 5.22 -- il
    serialise le document **normalise**, et la normalisation est idempotente. La
    distinction compte parce que le producteur est le seul endroit ou un champ vide
    pourrait devenir un fait: passer `label=""` ne doit pas produire un autre document
    que ne pas passer `label` du tout.
    """
    profil = couleur._calibration_profile(press=designe._PRESSES[1])
    commun = dict(chain_id=designe._CHAINES[1], source_page_id="p0",
                  template_id=couleur.TEMPLATE, read_patch_count=18,
                  retained_patch_count=18,
                  ink_floor_excluded=cc.correction_form_excludes_ink_floor(
                      profil.correction_id))
    sans = cc.profile_to_document(profil, **commun)
    avec_vides = cc.profile_to_document(profil, label="", comment="", **commun)

    assert calibration_profile.serialize_profile(sans) == (
        calibration_profile.serialize_profile(avec_vides))
    assert "label" not in calibration_profile.serialize_profile(sans)


def test_un_document_sans_dossier_de_scan_est_celui_qui_n_en_recoit_AUCUN(
    tmp_path,
) -> None:
    """Le meme invariant, pour le champ neuf d'`EPIC11-ARB-262` : `scan_dir`.

    **Ce banc ferme un mutant survivant, mesure le 2026-09-07** (couche 1 de la
    revue) : `color_calibration.py`, `if scan_dir:` -> `if True:`, **survivait**
    aux 188 tests de `test_profil_nomme_par_l_operateur`,
    `test_calibration_profile`, `test_profil_designe` et
    `test_calibration_provenance_wiring` reunis. L'invariant etait ecrit **juste
    au-dessus de l'instruction** -- « un appelant qui transmet `""` et un
    appelant qui ne transmet rien doivent produire le MEME document » -- et
    n'etait mesure nulle part.

    Ce que le mutant produisait : `scan_dir: ''` dans le document, c'est-a-dire
    un champ qui **dit** d'ou vient le profil en disant « de nulle part ». Ce
    n'est pas cosmetique du cote qui LIT :
    `calibration_profile.dossiers_de_scan_declares` ecarte deja les valeurs
    vides, donc l'inventaire ne se tromperait pas -- mais il le fait par une
    seconde garde, et deux gardes qui se rattrapent l'une l'autre sont
    exactement la configuration ou aucune n'est mesuree.

    **L'assertion porte sur le document PRODUIT, pas sur le fichier ecrit**, et
    c'est la meme distinction que le banc voisin etablit : le fichier porte le
    defaut du champ, le producteur est le seul endroit ou un champ vide
    pourrait devenir un fait.
    """
    profil = couleur._calibration_profile(press=designe._PRESSES[1])
    commun = dict(chain_id=designe._CHAINES[1], source_page_id="p0",
                  template_id=couleur.TEMPLATE, read_patch_count=18,
                  retained_patch_count=18,
                  ink_floor_excluded=cc.correction_form_excludes_ink_floor(
                      profil.correction_id))
    sans = cc.profile_to_document(profil, **commun)
    avec_vide = cc.profile_to_document(profil, scan_dir="", **commun)

    assert sans == avec_vide
    assert calibration_profile.SCAN_DIR_FIELD not in sans
    # Le symetrique, sans lequel la frontiere ne mesurerait qu'une omission :
    # une valeur non vide est bien ecrite, et sous son nom.
    porte = cc.profile_to_document(profil, scan_dir="scans/ma-mire", **commun)
    assert porte[calibration_profile.SCAN_DIR_FIELD] == "scans/ma-mire"


# ---------------------------------------------------------------------------
# L'entree de manifest reste ecrivable: la garde de portabilite v2
# ---------------------------------------------------------------------------


def test_le_miroir_du_pattern_de_chemin_absolu_ne_derive_pas() -> None:
    """Le pattern recopie dans `io/calibration_profile` est celui de `io/manifest`.

    Une derive entre les deux rendrait le refus faux dans un sens ou dans l'autre: soit
    des etiquettes refusees pour rien, soit -- et c'est le sens qui coute -- des
    entrees de manifest perdues en silence. `io/calibration_profile` reste pur, il ne
    peut pas importer `io/manifest`; l'egalite est donc une assertion, pas un import.
    """
    assert (calibration_profile._MANIFEST_ABSOLUTE_PATH_PATTERN.pattern
            == manifest_module._ABSOLUTE_PATH_PATTERN.pattern)


@pytest.mark.parametrize("champ", ["label", "comment"])
@pytest.mark.parametrize("valeur", ["/home/egan/scans", r"C:\scans", r"\\nas\profils"])
def test_une_etiquette_ressemblant_a_un_chemin_absolu_est_refusee(
    tmp_path, champ, valeur,
) -> None:
    """Frontiere mesuree: le contrat v2 interdit ces chaines **partout** au manifest.

    Sans ce refus, le profil s'ecrirait tres bien et c'est son **entree autoportante**
    qui serait refusee plus tard -- sur un chemin qui, depuis le bloquant `C2` de la
    revue de 5.22, se contente d'avertir. La trace du profil disparaitrait donc sans
    autre bruit qu'une ligne de journal.
    """
    projet = tmp_path / "projet"
    document = dict(_document_etiquete(1))
    document[champ] = valeur

    with pytest.raises(calibration_profile.ProfileValidationError) as excinfo:
        calibration_profile.write_profile(projet, document)

    assert "chemin absolu" in str(excinfo.value)
    assert not _dossier_des_profils(projet).exists()


def test_un_profil_etiquete_ecrit_vraiment_son_entree_au_manifest(tmp_path) -> None:
    """Bout en bout: le manifest **valide** accepte l'entree d'un profil etiquete.

    C'est la preuve que le couple d'Egan tient (« un profil = un fichier autoportant +
    une entree autoportante au manifest ») pour un profil nomme: la GUI d'Epic 7 lit le
    registre du manifest, et sans etiquette ni commentaire elle n'aurait a afficher que
    des identites de chaine -- c'est-a-dire exactement ce qu'Egan ne veut pas lire.
    """
    projet = designe._trois_projets(tmp_path)[1]
    document = _document_etiquete(2, commentaire="essai du 14 aout, bac a plat")
    externe = tmp_path / "ailleurs" / "profil.json"
    externe.parent.mkdir(parents=True, exist_ok=True)
    externe.write_text(calibration_profile.serialize_profile(document), encoding="utf-8")

    designation.import_designated_profile(projet, externe, as_default=True)

    manifest_module.validate_manifest(projet / "project.json")
    couleur_section = designe._color(projet)
    entree = designe._entree_de_chaine(
        couleur_section[designation.DESIGNATED_PROFILES_KEY], designe._CHAINES[2])
    assert entree is not None
    assert entree["label"] == "Zone Nord Été 2026 essai"
    assert entree["comment"] == "essai du 14 aout, bac a plat"
    assert entree["chain_id"] == "chaine-mu"
    assert entree[designation.ENTRY_PATH_KEY] == (
        "versions/calibration/zone-nord-ete-2026-essai.json")
    assert (projet / entree[designation.ENTRY_PATH_KEY]).is_file()
    defaut = couleur_section[designation.DEFAULT_PROFILE_KEY]
    assert defaut["label"] == "Zone Nord Été 2026 essai"


def test_l_entree_se_construit_sur_un_document_qui_ne_porte_pas_les_deux_champs(
    tmp_path,
) -> None:
    """Le mutant `M12`, epingle apres avoir survecu au premier tour de campagne.

    `manifest_entry` lit les deux champs neufs par `.get` et non par acces nu, et cela
    ne se voit **pas** sur le chemin de la designation: `read_designated_document`
    valide, donc fusionne, donc le document y porte toujours les deux. Le chemin qui
    mord est l'autre -- celui ou l'entree est construite depuis un document sortant
    directement de `profile_to_document`, qui les **omet** quand ils sont vides. Un
    acces nu y leve un `KeyError`, et c'est la sixieme occurrence de cette famille dans
    cette seule story (cf. AC 10).

    Le defaut est reel: c'est ainsi que la trace d'un profil ancien, non etiquete,
    disparaitrait du manifest -- et elle disparaitrait avec un avertissement, la revue
    de 5.22 ayant rendu cette ecriture non fatale (bloquant `C2`).
    """
    projet = designe._trois_projets(tmp_path)[1]
    ancien = designe._document(designe._CHAINES[1], designe._PRESSES[1])
    assert "label" not in ancien and "comment" not in ancien
    ecrit = calibration_profile.write_profile(projet, ancien)

    entree = designation.record_designated_profile(
        projet, ancien, project_path=ecrit, source=tmp_path / "ailleurs" / "vieux.json")

    assert entree["label"] == ""
    assert entree["comment"] == ""
    assert entree["chain_id"] == "chaine-zeta"
    assert entree[designation.ENTRY_SOURCE_KEY] == "vieux.json"
    inscrite = designe._entree_de_chaine(
        designe._color(projet)[designation.DESIGNATED_PROFILES_KEY], "chaine-zeta")
    assert inscrite == entree


def test_le_chemin_inscrit_au_manifest_est_celui_du_fichier_etiquete(tmp_path) -> None:
    """L'entree autoportante pointe sur le fichier **reellement ecrit**, etiquette comprise.

    Correctif trouve en chemin: le point d'appel du scan recomposait le chemin de
    l'entree par `profile_path(project_dir, chain_id)`. C'etait exact tant que les deux
    coincidaient; des qu'un profil porte le nom de son operateur, l'entree pointe sur un
    fichier **inexistant** -- et le defaut du projet, qui se resout par ce chemin ecrit,
    cesse de se resoudre. Le symptome serait un lot livre brut sans que rien n'ait
    change, des semaines apres la designation.
    """
    projet = designe._trois_projets(tmp_path)[1]
    document = _document_etiquete(2, commentaire="bac a plat")
    externe = tmp_path / "ailleurs" / "profil.json"
    externe.parent.mkdir(parents=True, exist_ok=True)
    externe.write_text(calibration_profile.serialize_profile(document), encoding="utf-8")
    ecrit = calibration_profile.write_profile(projet, document)

    entree = designation.record_designated_profile(
        projet, document,
        project_path=calibration_profile.profile_path_for_document(projet, document),
        source=externe)

    assert entree[designation.ENTRY_PATH_KEY] == (
        "versions/calibration/zone-nord-ete-2026-essai.json")
    assert (projet / entree[designation.ENTRY_PATH_KEY]) == ecrit
    assert ecrit.is_file()
    # Et le chemin recompose depuis l'identite, lui, ne designe rien.
    assert not calibration_profile.profile_path(projet, document["chain_id"]).exists()


def test_le_scan_ne_recompose_plus_le_chemin_du_profil_depuis_l_identite() -> None:
    """Frontiere negative, sur le **point d'appel** que le test precedent ne traverse pas.

    Exercer ce point-la demanderait un scan complet, que l'AC 9 ne paie pas. La mesure
    est donc portee sur la source: le chemin de scan n'appelle plus `profile_path` -- une
    recomposition depuis le `chain_id` --, il appelle `profile_path_for_document`. Un
    retour en arriere fait rougir ce test au lieu d'attendre un lot livre brut sur le
    materiel d'Egan.

    Adaptation 5.26 (extraction, AC 2): le point d'appel vit desormais dans
    `_ecrire_le_lot_detecte`, la moitie aval extraite de `scan_command` que `scan` et
    `scan-write` appellent tous deux -- le temoin positif et l'interdit se mesurent a
    l'endroit ou le code est parti.
    """
    # Story 11.4b (lot S1) : le corps a quitte `cli.py` pour le module de coeur
    # `scan_write` -- le temoin positif et l'interdit se mesurent, comme en
    # 5.26, a l'endroit ou le code est parti.
    from mixed_media_utility import scan_write

    arbre = ast.parse(inspect.getsource(scan_write.ecrire_le_lot_detecte))
    appels = {noeud.func.attr for noeud in ast.walk(arbre)
              if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)}
    assert "profile_path" not in appels, sorted(appels)
    assert "profile_path_for_document" in appels, sorted(appels)


@pytest.mark.parametrize("champ,valeur", [
    ("label", 42), ("comment", ["une", "liste"]), ("label", "deux\nlignes"),
])
def test_une_etiquette_mal_formee_est_refusee(tmp_path, champ, valeur) -> None:
    """Refus de forme: ces deux champs sont du **texte**, et l'etiquette tient sur une ligne.

    Un nombre ou une liste finirait recopie dans une entree de manifest sous un champ
    dit textuel; un saut de ligne couperait en deux le nom affiche au survol.
    """
    projet = tmp_path / "projet"
    document = dict(_document_etiquete(1))
    document[champ] = valeur

    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile.write_profile(projet, document)

    assert not _dossier_des_profils(projet).exists()


# ---------------------------------------------------------------------------
# `scan calibrate`: la question, les options, et le mode non interactif
# ---------------------------------------------------------------------------


def _scan_calibrable(tmp_path: Path, monkeypatch) -> tuple:
    """Un projet et un dossier de scan ingerable, l'ajustement du lot substitue.

    Le seul point substitue est `cli._fit_lot_correction`, comme dans
    `test_scan_calibrate_command`: son contenu est eprouve contre les vrais producteurs
    dans la moitie couleur, et le synthetiser ici couterait les 10 s de l'AC 9.
    """
    dossier = tmp_path / "scan-calibration"
    dossier.mkdir()
    assert cv2.imwrite(str(dossier / "page.tif"),
                       np.full((400, 600, 3), 200, dtype=np.uint8))
    profil = couleur._calibration_profile(press=designe._PRESSES[1])
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction", lambda *a, **k: cc.LotCorrection(
        source_page_id="calibration-0", template_id=couleur.TEMPLATE,
        profile=profil, correction_form_id=profil.correction_id))
    return tmp_path / "projet", dossier


def _interactif(monkeypatch, reponses: list) -> list:
    """Simuler un terminal: `isatty()` vrai et des reponses servies dans l'ordre.

    Les questions posees sont **collectees** et rendues: un test qui verifie qu'une
    question n'a **pas** ete posee ne peut pas se contenter de compter les reponses
    consommees.
    """
    posees: list = []

    class _Entree:
        def isatty(self):
            return True

    monkeypatch.setattr(cli.sys, "stdin", _Entree())

    def _input(invite=""):
        posees.append(invite)
        if not reponses:
            raise EOFError
        return reponses.pop(0)

    monkeypatch.setattr("builtins.input", _input)
    return posees


def test_calibrate_nomme_le_fichier_avec_le_nom_donne_en_option(
    tmp_path, monkeypatch,
) -> None:
    """AC 8quater, mandat: le fichier porte le nom de l'operateur, pas l'identite brute.

    L'identite derivee est ecrite **dans** le document et ne nomme plus le fichier: les
    deux se lisent separement, et c'est toute la demande d'Egan.
    """
    projet, dossier = _scan_calibrable(tmp_path, monkeypatch)

    assert cli.main([
        "scan", "--project", str(projet), "--scan", str(dossier), "--dpi", "600",
        "calibrate", cli.PROFILE_NAME_FLAG, _ETIQUETTES[1],
        cli.PROFILE_COMMENT_FLAG, "auto-correction coupee",
    ]) == 0

    assert _noms_des_profils(projet) == ["scanner-maison-default-tiff.json"]
    document = calibration_profile.read_profile(projet, "scanner-maison-default-tiff")
    assert document["label"] == "scanner maison default tiff"
    assert document["comment"] == "auto-correction coupee"
    # L'identite officielle est intacte, et ce n'est pas le nom du fichier.
    assert document["chain_id"] != "scanner-maison-default-tiff"
    assert document["chain_id"].startswith("600-")
    assert document["source_page_id"] == "calibration-0"


def test_calibrate_hors_terminal_ne_demande_rien_et_nomme_par_la_chaine(
    tmp_path, monkeypatch,
) -> None:
    """**Le mode non interactif, et c'est le regime par defaut de cette commande.**

    Hors terminal -- script, CI, ces 4800 tests --, aucune question n'est posee et rien
    n'est refuse: le profil prend le nom de son `chain_id`, exactement ce que 5.22
    ecrivait. Un `input()` inconditionnel leverait ici `EOFError`, et c'est la panne que
    ce test existe pour rendre impossible: `input` est substitue par une fonction qui
    **echoue** si elle est appelee.
    """
    projet, dossier = _scan_calibrable(tmp_path, monkeypatch)

    def _interdit(invite=""):
        raise AssertionError(f"question posee hors terminal: {invite!r}")

    monkeypatch.setattr("builtins.input", _interdit)

    assert cli.main([
        "scan", "--project", str(projet), "--scan", str(dossier), "--dpi", "600",
        "calibrate",
    ]) == 0

    (nom,) = _noms_des_profils(projet)
    document = calibration_profile.read_profile(projet, nom[:-len(".json")])
    assert nom == f"{document['chain_id']}.json"
    assert document["label"] == ""
    assert document["comment"] == ""


def test_calibrate_pose_les_deux_questions_sur_un_terminal(tmp_path, monkeypatch) -> None:
    """Le geste du mandat: sur un terminal, la commande **demande** le nom et le commentaire."""
    projet, dossier = _scan_calibrable(tmp_path, monkeypatch)
    posees = _interactif(monkeypatch, [_ETIQUETTES[2], "bac a plat, essai"])

    assert cli.main([
        "scan", "--project", str(projet), "--scan", str(dossier), "--dpi", "600",
        "calibrate",
    ]) == 0

    assert len(posees) == 2, posees
    assert "Nom du profil" in posees[0]
    assert "facultatif" in posees[1].lower()
    assert _noms_des_profils(projet) == ["zone-nord-ete-2026-essai.json"]
    document = calibration_profile.read_profile(projet, "zone-nord-ete-2026-essai")
    assert document["label"] == "Zone Nord Été 2026 essai"
    assert document["comment"] == "bac a plat, essai"


def test_sur_un_terminal_une_reponse_vide_vaut_le_nom_derive(tmp_path, monkeypatch) -> None:
    """Frontiere: l'operateur presse Entree deux fois. Ce n'est pas un refus.

    C'est le defaut annonce dans l'invite, et il ramene exactement au comportement de
    5.22 -- le fichier prend le nom de la chaine, et rien n'est etiquete.
    """
    projet, dossier = _scan_calibrable(tmp_path, monkeypatch)
    posees = _interactif(monkeypatch, ["   ", ""])

    assert cli.main([
        "scan", "--project", str(projet), "--scan", str(dossier), "--dpi", "600",
        "calibrate",
    ]) == 0

    assert len(posees) == 2, posees
    (nom,) = _noms_des_profils(projet)
    document = calibration_profile.read_profile(projet, nom[:-len(".json")])
    assert nom == f"{document['chain_id']}.json"
    assert document["label"] == ""


def test_l_option_repond_a_la_place_de_la_question(tmp_path, monkeypatch) -> None:
    """Frontiere: une option passee **remplace** la question, elle ne s'y ajoute pas.

    Sinon la commande serait impossible a scripter a moitie: un `--nom` donne sur un
    terminal declencherait quand meme l'invite, et l'operateur repondrait deux fois a
    la meme question. Une seule question est posee, et c'est celle du commentaire.
    """
    projet, dossier = _scan_calibrable(tmp_path, monkeypatch)
    posees = _interactif(monkeypatch, ["note du commentaire"])

    assert cli.main([
        "scan", "--project", str(projet), "--scan", str(dossier), "--dpi", "600",
        "calibrate", cli.PROFILE_NAME_FLAG, _ETIQUETTES[0],
    ]) == 0

    assert len(posees) == 1, posees
    assert "facultatif" in posees[0].lower()
    assert _noms_des_profils(projet) == ["atelier-du-fond-300-dpi.json"]
    document = calibration_profile.read_profile(projet, "atelier-du-fond-300-dpi")
    assert document["comment"] == "note du commentaire"


@pytest.mark.parametrize("etiquette,attendu", [
    ("- _ -", "nommable"),
    ("!!!", "caracteres refuses"),
    ("HP ENVY /4520/", "caracteres refuses"),
])
def test_calibrate_refuse_une_etiquette_qui_ne_nomme_aucun_fichier(
    tmp_path, monkeypatch, capsys, etiquette, attendu,
) -> None:
    """Frontiere de la commande: le refus est nomme, et rien n'est ecrit.

    Les deux refus remontent jusqu'a l'operateur par la meme porte, et ils sont
    **distincts**: « je ne sais pas nommer un fichier avec ca » n'est pas « tu as tape
    un caractere que je refuse ». Un seul message pour les deux ferait chercher a
    l'operateur un caractere special dans une etiquette qui n'en porte aucun.
    """
    projet, dossier = _scan_calibrable(tmp_path, monkeypatch)

    assert cli.main([
        "scan", "--project", str(projet), "--scan", str(dossier), "--dpi", "600",
        "calibrate", cli.PROFILE_NAME_FLAG, etiquette,
    ]) == 1

    assert attendu in capsys.readouterr().err
    assert not _dossier_des_profils(projet).exists()


def test_les_options_de_nommage_n_ecrasent_pas_celles_du_parent(monkeypatch) -> None:
    """Non-regression du piege argparse mesure le 2026-08-17.

    Une option declaree sur le parent **et** sur le sous-parseur voit sa valeur ecrasee
    par le defaut du sous-parseur. `--nom` et `--commentaire` n'existent que sur la
    sous-commande, mais les ajouter ne doit rien changer aux trois options du parent:
    ce test les relit apres coup, sur le vrai parseur.
    """
    vus: list = []
    monkeypatch.setattr(cli, "scan_calibrate_command",
                        lambda args: vus.append(args) or 0)

    assert cli.main([
        "scan", "--project", "projet-x", "--scan", "scan-s", "--dpi", "600",
        "calibrate", cli.PROFILE_NAME_FLAG, "un nom", cli.PROFILE_COMMENT_FLAG, "note",
    ]) == 0

    (args,) = vus
    assert args.project == "projet-x"
    assert args.scan == "scan-s"
    assert args.dpi == 600
    assert args.nom == "un nom"
    assert args.commentaire == "note"


def test_les_options_de_nommage_ne_sont_pas_offertes_au_scan_de_lot() -> None:
    """Frontiere negative: `scan --nom ...` est **refuse**, jamais accepte puis ignore.

    Une option acceptee sur `scan` et sans effet serait le reste inerte que l'AC 13 de
    cette meme story retire ailleurs. `argparse` la refuse bruyamment (code 2).
    """
    for drapeau in (cli.PROFILE_NAME_FLAG, cli.PROFILE_COMMENT_FLAG):
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["scan", "--project", "p", "--scan", "s", "--dpi", "600",
                      drapeau, "x"])
        assert excinfo.value.code == 2, drapeau


# ---------------------------------------------------------------------------
# `EPIC5-ARB-99`: deux chaines ne partagent JAMAIS un fichier de profil
# ---------------------------------------------------------------------------


def _document_de(chaine: str, rang_presse: int, etiquette: str) -> dict:
    """Un profil valide, etiquete, dont l'identite et les coefficients sont choisis.

    Les trois parametres sont libres **exactement** parce que la collision se mesure en
    les faisant diverger: meme etiquette, chaines differentes, coefficients differents.
    Une fabrique qui les lierait entre eux rendrait le defaut invisible -- c'est la
    regle des fabriques de `CLAUDE.md`, appliquee au cas qu'elle vise.
    """
    profil = couleur._calibration_profile(press=designe._PRESSES[rang_presse])
    return cc.profile_to_document(
        profil,
        chain_id=chaine,
        source_page_id=f"{chaine}-p0",
        template_id=couleur.TEMPLATE,
        read_patch_count=18,
        retained_patch_count=18,
        ink_floor_excluded=cc.correction_form_excludes_ink_floor(profil.correction_id),
        label=etiquette,
    )


def test_deux_chaines_dont_les_etiquettes_collisionnent_font_deux_fichiers(
    tmp_path,
) -> None:
    """`EPIC5-ARB-99`, **le finding le plus grave de la revue de 5.23**, ferme.

    Le defaut, mesure de bout en bout par la couche 2: `"HP Envy 4520"` et
    `"hp envy 4520"` rendent le meme slug, donc deux profils de **deux chaines
    differentes** ecrivaient un seul fichier. Le second ecrasait le premier, le manifest
    declarait deux entrees sur un seul chemin, et le defaut du projet rendait ensuite
    **les coefficients de l'autre chaine**. Sans un mot.

    La mesure porte sur les **coefficients relus**, jamais sur la presence des fichiers
    (`EPIC5-ARB-39`): un correctif qui ecrirait deux fichiers dont l'un porte le contenu
    de l'autre passerait un test de presence.

    Trois profils, la cible en **troisieme** position, et les trois etiquettes se
    reduisent au **meme** slug: une fabrique qui n'en aurait mis que deux laisserait
    passer un correctif qui ne separe que la premiere paire.
    """
    projet = tmp_path / "projet"
    etiquettes = ("HP Envy 4520", "hp envy 4520", "HP  ENVY  4520")
    documents = [_document_de(chaine, rang, etiquette)
                 for rang, (chaine, etiquette)
                 in enumerate(zip(designe._CHAINES, etiquettes))]
    # La fabrique tient sa promesse: trois etiquettes distinctes, trois chaines
    # distinctes, trois jeux de coefficients distincts -- et **un seul** slug.
    assert len(set(etiquettes)) == 3
    assert {calibration_profile.slugify_label(e) for e in etiquettes} == {
        "hp-envy-4520"}
    assert len({json.dumps(d["coefficients"], sort_keys=True)
                for d in documents}) == 3

    chemins = [calibration_profile.write_profile(projet, d)
               for d in documents]

    assert len(set(chemins)) == 3, chemins
    for chemin, document in zip(chemins, documents):
        relu = json.loads(chemin.read_text(encoding="utf-8"))
        assert relu["chain_id"] == document["chain_id"], chemin
        assert relu["coefficients"] == document["coefficients"], chemin
    # Le premier -- celui qui portait le nom nu -- n'a pas bouge d'un octet: c'est lui
    # que l'ancien code ecrasait, et c'est sur lui que porte tout le defaut.
    assert chemins[0].name == "hp-envy-4520.json"
    assert json.loads(chemins[0].read_text(encoding="utf-8"))["coefficients"] == (
        documents[0]["coefficients"])
    # Les deux suivants portent l'empreinte differenciante, et elle est **stable**:
    # rejouer l'ecriture ne fabrique pas un troisieme fichier.
    for rang in (1, 2):
        assert chemins[rang].name.startswith("hp-envy-4520-")
        assert calibration_profile.write_profile(
            projet, documents[rang]) == chemins[rang]
    assert len(_noms_des_profils(projet)) == 3


def test_l_empreinte_differenciante_est_celle_du_depot_et_pas_une_horodate(
    tmp_path,
) -> None:
    """Frontiere de la precedente: **quelle** empreinte, et pourquoi elle est stable.

    Une empreinte tiree d'une horodate ou du `hash()` de Python separerait les deux
    profils une fois puis en fabriquerait un nouveau a chaque passe -- le dossier des
    profils grossirait sans fin, et aucun chemin de manifest ne resterait vrai. La
    recette est celle du depot (`naming.scan_chain_suffix`, un `sha256` tronque),
    calculee sur l'identite **et** l'etiquette brute.

    L'egalite est confrontee au producteur du depot plutot que recopiee en litteral: ce
    qui doit tenir, c'est qu'il n'y ait **qu'une** recette d'empreinte.
    """
    document = _document_de(designe._CHAINES[1], 1, "HP Envy 4520")
    empreinte = calibration_profile.profile_collision_suffix(document)

    assert empreinte == naming.scan_chain_suffix(
        f"{designe._CHAINES[1]}\x00HP Envy 4520")
    assert len(empreinte) == naming.BOUNDS_SUFFIX_LENGTH
    # Deterministe: deux appels, deux fois la meme valeur.
    assert empreinte == calibration_profile.profile_collision_suffix(document)
    # Et differenciante: l'etiquette **brute** entre dans le materiau, donc deux
    # etiquettes que le slug confond rendent deux empreintes.
    autre = _document_de(designe._CHAINES[1], 1, "hp envy 4520")
    assert calibration_profile.profile_collision_suffix(autre) != empreinte
    # L'identite y entre aussi: deux chaines de meme etiquette se separent.
    encore = _document_de(designe._CHAINES[2], 1, "HP Envy 4520")
    assert calibration_profile.profile_collision_suffix(encore) != empreinte


def test_hors_terminal_la_collision_prend_l_empreinte_et_n_ecrase_jamais(
    tmp_path,
) -> None:
    """`EPIC5-ARB-99`, le regime que la note d'Egan ne couvre pas: script, CI, ces tests.

    Il n'y a personne pour repondre `Y/N`. Le defaut y est **l'empreinte**, jamais
    l'ecrasement -- un ecrasement silencieux serait exactement le defaut que cette
    decision supprime -- et jamais l'echec: un profil parfaitement mesure ne se perd pas
    parce que personne ne regardait l'ecran.

    La preuve que ce chemin ne demande rien: `input` est substitue par une fonction qui
    **echoue** si elle est appelee. C'est le meme dispositif que
    `test_calibrate_hors_terminal_ne_demande_rien_et_nomme_par_la_chaine`.
    """
    projet = tmp_path / "projet"
    premier = _document_de(designe._CHAINES[0], 0, "HP Envy 4520")
    second = _document_de(designe._CHAINES[1], 1, "hp envy 4520")
    calibration_profile.write_profile(projet, premier)

    chemin = calibration_profile.write_profile(projet, second)

    assert chemin.name != "hp-envy-4520.json"
    # Le premier est intact, coefficients compris.
    intact = json.loads(
        (_dossier_des_profils(projet) / "hp-envy-4520.json").read_text(
            encoding="utf-8"))
    assert intact["chain_id"] == designe._CHAINES[0]
    assert intact["coefficients"] == premier["coefficients"]
    assert intact["coefficients"] != second["coefficients"]
    # Et le second est ecrit, entier: on n'a ni ecrase, ni echoue.
    assert json.loads(chemin.read_text(encoding="utf-8"))["coefficients"] == (
        second["coefficients"])


def test_sur_un_terminal_la_reponse_oui_ecrase_et_la_reponse_non_prend_l_empreinte(
    tmp_path,
) -> None:
    """`EPIC5-ARB-99`, gestes 3 et 4: l'invite `Y/N`, et ses deux issues.

    L'invite elle-meme vit cote CLI -- c'est elle qui sait s'il y a un terminal
    (`cli._stdin_is_interactive`, la seule machinerie d'interactivite du depot). Ce
    module rend la **question** (`COLLISION_PROMPT`) et prend la **reponse**; le test
    joue les deux roles de l'appelant, sans dupliquer l'interactivite.

    Les deux issues sont mesurees dans le meme test parce que c'est leur **contraste**
    qui porte la decision: un correctif qui ecraserait toujours, ou qui n'ecraserait
    jamais, en passerait une et raterait l'autre.
    """
    for reponse, ecrase in ((True, True), (False, False)):
        projet = tmp_path / f"projet-{reponse}"
        premier = _document_de(designe._CHAINES[0], 0, "HP Envy 4520")
        second = _document_de(designe._CHAINES[1], 1, "hp envy 4520")
        calibration_profile.write_profile(projet, premier)
        posees = []

        def _repondre(occupant, radical, _reponse=reponse):
            posees.append((occupant, radical))
            return _reponse

        chemin = calibration_profile.write_profile(
            projet, second, confirm_overwrite=_repondre)

        # La question a bien ete posee, et elle nomme ce qu'il faut pour y repondre.
        assert posees == [(designe._CHAINES[0], "hp-envy-4520")], posees
        nomme = calibration_profile.COLLISION_PROMPT.format(
            stem="hp-envy-4520", chaine=designe._CHAINES[0])
        assert "hp-envy-4520" in nomme and designe._CHAINES[0] in nomme
        assert "ecraser" in nomme.lower()
        if ecrase:
            assert chemin.name == "hp-envy-4520.json"
            assert _noms_des_profils(projet) == ["hp-envy-4520.json"]
        else:
            assert chemin.name != "hp-envy-4520.json"
            assert len(_noms_des_profils(projet)) == 2
        assert json.loads(chemin.read_text(encoding="utf-8"))["chain_id"] == (
            designe._CHAINES[1])


def test_recalibrer_la_meme_chaine_reste_un_remplacement_sans_question(
    tmp_path,
) -> None:
    """Frontiere negative, et c'est elle qui empeche l'invite de devenir du bruit.

    Reecrire le profil **de la meme chaine** sous le meme nom n'est pas une collision:
    c'est la recalibration, que ce module documente comme un remplacement voulu depuis
    5.22. Poser la question a chaque recalibration apprendrait a l'operateur a repondre
    « oui » sans lire -- donc l'inverse de ce que `EPIC5-ARB-99` cherche.

    Le rappel `confirm_overwrite` est une fonction qui **echoue** si elle est appelee:
    la mesure porte sur le fait qu'aucune question n'est posee, pas sur un compteur.
    """
    projet = tmp_path / "projet"
    ancien = _document_de(designe._CHAINES[1], 0, "HP Envy 4520")
    recalibre = _document_de(designe._CHAINES[1], 2, "HP Envy 4520")
    assert ancien["coefficients"] != recalibre["coefficients"]
    premier = calibration_profile.write_profile(projet, ancien)

    def _interdit(*args):
        raise AssertionError(f"question posee sur une recalibration: {args!r}")

    second = calibration_profile.write_profile(
        projet, recalibre, confirm_overwrite=_interdit)

    assert second == premier
    assert _noms_des_profils(projet) == ["hp-envy-4520.json"]
    assert json.loads(second.read_text(encoding="utf-8"))["coefficients"] == (
        recalibre["coefficients"])


def test_un_fichier_de_profil_illisible_n_est_jamais_ecrase(tmp_path) -> None:
    """Frontiere: le fichier occupant est present mais on ne peut pas lire sa chaine.

    Tronque, binaire, ecrit par autre chose: dans les trois cas on ne peut pas prouver
    qu'il appartient au profil entrant, donc on ne l'ecrase pas. C'est la lecture sure
    de « je ne sais pas », et c'est la meme doctrine que `cli._stdin_is_interactive`
    applique a l'incertitude.
    """
    projet = tmp_path / "projet"
    dossier = _dossier_des_profils(projet)
    dossier.mkdir(parents=True)
    occupe = dossier / "hp-envy-4520.json"
    occupe.write_bytes(b"\xff\xfe ce ne sont pas des octets utf-8")
    document = _document_de(designe._CHAINES[1], 1, "HP Envy 4520")

    chemin = calibration_profile.write_profile(projet, document)

    assert chemin != occupe
    assert occupe.read_bytes() == b"\xff\xfe ce ne sont pas des octets utf-8"


def test_l_entree_de_manifest_porte_la_date_et_l_heure_de_la_designation(
    tmp_path,
) -> None:
    """`EPIC5-ARB-99`, geste 2: « date et heure au manifeste ».

    Elle ne resout rien: elle existe pour que **deux entrees se distinguent a la
    lecture** -- c'est exactement ce qui manquait quand deux chaines partageaient un
    chemin. Le format est celui du reste du manifest (RFC 3339, UTC, suffixe `Z`), et il
    est confronte a `extraction_manifest._utc_now_rfc3339` plutot que recopie: deux
    serialisations d'horodate divergeraient a la premiere evolution du format.
    """
    projet = designe._trois_projets(tmp_path)[1]
    document = _document_etiquete(2)
    ecrit = calibration_profile.write_profile(projet, document)

    entree = designation.record_designated_profile(
        projet, document, project_path=ecrit, source=tmp_path / "ailleurs" / "p.json")

    horodate = entree[designation.ENTRY_DESIGNATED_AT_KEY]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", horodate), horodate
    assert len(horodate) == len(extraction_manifest._utc_now_rfc3339())
    # Elle descend jusqu'au manifest, et le manifest reste valide au schema v2.
    manifest_module.validate_manifest(projet / "project.json")
    inscrite = designe._entree_de_chaine(
        designe._color(projet)[designation.DESIGNATED_PROFILES_KEY],
        designe._CHAINES[2])
    assert inscrite[designation.ENTRY_DESIGNATED_AT_KEY] == horodate
    # Et elle est **injectable**, sans quoi aucun test ne pourrait comparer deux entrees.
    fige = designation.manifest_entry(
        document, project_path=ecrit, project_dir=projet,
        source=tmp_path / "ailleurs" / "p.json",
        designated_at="2026-08-19T11:22:33Z")
    assert fige[designation.ENTRY_DESIGNATED_AT_KEY] == "2026-08-19T11:22:33Z"


def test_une_etiquette_au_budget_maximal_collisionne_sans_faire_un_nom_illegal(
    tmp_path,
) -> None:
    """Frontiere de longueur de l'empreinte, sur l'etiquette **la plus longue admise**.

    Trouvee survivante par la campagne d'injection du 2026-08-19 (mutant `M13`): en
    retirant la troncature de `_stem_avec_empreinte`, le lot restait entierement vert.
    Le defaut est pourtant reel et atteignable **sans rien taper d'anormal** -- une
    etiquette de 48 caracteres est legale, et lui coller l'empreinte en fait un radical
    de 57, refuse par `_validate_chain_id`. L'operateur verrait son second profil,
    parfaitement mesure, disparaitre sur un refus de longueur qu'il n'a pas provoque.

    Ici la troncature est **sure**, la ou `slugify_label` la refuse: c'est l'empreinte
    qui porte l'identite, donc deux etiquettes partageant leur debut restent separees.
    C'est la meme forme que `naming.build_calibration_pdf_filename` -- un fragment
    lisible pour l'oeil, un condensat pour l'identite.
    """
    projet = tmp_path / "projet"
    etiquette = "scanner maison de l atelier du fond en tiff a si"
    assert len(calibration_profile.slugify_label(etiquette)) == (
        naming.CANONICAL_ID_MAX_LENGTH)
    premier = _document_de(designe._CHAINES[0], 0, etiquette)
    second = _document_de(designe._CHAINES[1], 1, etiquette.upper())
    assert (calibration_profile.slugify_label(premier["label"])
            == calibration_profile.slugify_label(second["label"]))

    calibration_profile.write_profile(projet, premier)
    chemin = calibration_profile.write_profile(projet, second)

    radical = chemin.name[:-len(".json")]
    assert len(radical) <= naming.CANONICAL_ID_MAX_LENGTH, radical
    assert calibration_profile._CHAIN_ID_PATTERN.fullmatch(radical), radical
    # Le fragment lisible survit a la troncature: le fichier reste reconnaissable.
    assert radical.startswith("scanner-maison-de-l-atelier-du-fond-en")
    # Les deux profils sont entiers, et ce sont bien deux fichiers.
    assert len(_noms_des_profils(projet)) == 2
    assert json.loads(chemin.read_text(encoding="utf-8"))["coefficients"] == (
        second["coefficients"])
    intact = json.loads(
        (_dossier_des_profils(projet)
         / f"{calibration_profile.slugify_label(etiquette)}.json").read_text(
             encoding="utf-8"))
    assert intact["chain_id"] == designe._CHAINES[0]
