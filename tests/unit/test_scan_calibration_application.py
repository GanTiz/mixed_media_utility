"""Story 5.19: la correction couleur du lot est **appliquee**, et les pixels le montrent.

Ce que cette suite mesure et ce qu'aucune autre ne mesurait avant elle. Les stories 5.4b
et 5.16 ont livre toute la machinerie -- deux formes de correction, la page de
calibration imprimee, le transport par `imported_profile`, la garde de divergence, le
champ de provenance -- et **rien ne la consommait**: `color_calibration_status` valait
invariablement `not_applied` et aucun pixel de master n'avait jamais ete corrige.

Deux niveaux, et les deux sont necessaires:

* **unites** -- `fit_lot_correction_from_page`, `derive_lot_calibration_status`,
  `write_lot_output_frames(page_profiles=...)`. Elles isolent une propriete a la fois, et
  ce sont elles qui peuvent epingler un appariement ou une frontiere negative;
* **chaine complete par la CLI** -- une planche est **composee, rendue, scannee,
  detectee, redressee, decoupee, corrigee, ecrite, declaree**. Aucun maillon n'est simule.
  C'est le seul niveau ou « les pixels du master changent » veut dire quelque chose:
  l'AC 3 interdit explicitement de se contenter d'un champ de manifest, parce qu'une
  correction **identite** produirait exactement le meme document.

**La fabrique de pages de cette suite peint les pastilles en aplat**, la ou celle de
`test_color_calibration` peint une couronne de contraste sur le retrait. Ce n'est pas un
relachement, c'est le bon modele a ce niveau-ci: une pastille imprimee **est** un aplat,
et la couronne est un dispositif de test dont l'objet -- attraper un retrait
d'echantillonnage faux -- est deja couvert, a l'unite, par la fabrique de la moitie
couleur. La reprendre ici melangerait sa mesure a celle du redressage: la couronne
deborde dans le carre echantillonne au reechantillonnage, et le biais qu'elle introduit
sur les pastilles de 6 mm d'une planche d'images suffit **a lui seul** a faire franchir
le seuil de divergence a une feuille parfaitement nominale. Mesure: exces +1,14 dE76
contre un seuil de 1,00, sur une feuille imprimee sous la presse de la page de
calibration. Le test aurait alors mesure sa propre fabrique.

**Regle des fabriques, appliquee trois fois.** Les planches d'un meme lot sont imprimees
sous des presses **differentes** (variation de tirage), donc leurs mesures diffferent et
un appariement page -> profil permute se voit; les quatre zones de frame portent quatre
couleurs **distinctes**, donc un appariement emplacement -> frame permute se voit; et la
page de calibration est posee **en dernier** au scanner, donc une recherche qui rendrait
toujours la premiere page lue corrigerait tout le lot avec le treillis d'une planche
d'images.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import pathlib
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import (  # noqa: E402
    cli,
    color_calibration as cc,
    color_pipeline,
    encode as encode_module,
    layout,
    page_roles,
    page_templates,
    patch_presets,
    patch_values,
    qr_codes,
    scan_output_frames as sof,
    scan_sorting,
)
from mixed_media_utility.io import payload as payload_io  # noqa: E402
from mixed_media_utility.io import project_layout  # noqa: E402
from mixed_media_utility.io import scan_manifest as sm  # noqa: E402

# `desactivation_regime_vrac` n'est plus importe ici: la story 5.24 a livre, et
# aucun test de ce fichier ne dort plus sous `EPIC5-ARB-84` (AC 8).
import test_calibration_page_source as couleur  # noqa: E402
import test_scan_manifest as scan  # noqa: E402


#: Gabarit **v2** et preset par defaut (`EPIC5-ARB-67`): ce sont les seuls qui portent a
#: la fois une page de calibration et un jeu de pastilles place sur les planches. Un
#: gabarit v1 ne peut pas porter de page de calibration -- `calibration_page_refusal` le
#: refuse avec son motif chiffre --, donc un test de cette story sur un v1 ne mesurerait
#: rien de ce qu'elle cable.
TEMPLATE = "tpl-a4-portrait-4f-v2"
PRESET = "patches-14-v3"

#: 300 ppp, comme les tests d'orchestration de 5.7, et pour la meme raison: en dessous,
#: les modules ArUco du gabarit ne portent plus assez de pixels pour etre detectes. Le
#: seuil de fiabilite du QR est plus haut encore, et l'ingestion le signale -- c'est bien
#: ce qu'elle doit faire.
DPI = 300

#: Les quatre zones de frame d'une planche, chacune d'une couleur **differente** (regle
#: des fabriques): un appariement emplacement <-> frame permute est invisible sur un
#: remplissage uniforme, et c'est litteralement le mutant `M33` de ce depot.
FRAME_COLOURS_BGR = ((40, 90, 200), (180, 60, 45), (60, 170, 90), (150, 150, 60))

#: Deux feuilles du **meme tirage**, distinguables. Un lot dont les deux planches
#: porteraient exactement les memes mesures rendrait invisible toute permutation entre
#: elles -- et leurs entrees de manifest seraient identiques au chiffre pres, donc un
#: test qui les confond passerait.
PRESSES_DU_TIRAGE = (couleur._press(0.930, (0.0250, 0.0240, 0.0260)),
                     couleur._press(0.926, (0.0257, 0.0233, 0.0264)))

#: La presse de la page de calibration: celle de la **premiere** feuille du tirage. Le
#: meme couple imprimante+scanner imprime la page de calibration et les planches.
PRESSE_CALIBRATION = PRESSES_DU_TIRAGE[0]


# ---------------------------------------------------------------------------
# Fabriques: une planche imprimee **puis numerisee**
# ---------------------------------------------------------------------------


def _paint_patches(page, patches, press, *, dpi: int = DPI) -> None:
    """Peindre les pastilles a leurs vraies positions, sous une presse donnee.

    Les deux repliques d'une meme valeur recoivent des offsets **opposes**, donc leur
    moyenne par valeur reste la mesure nominale exacte -- l'agregation H4 reste
    verifiable -- tandis que le bruit par paires n'est pas nul. Sans lui, le seuil
    d'indiscernabilite des sentinelles est degenere et le verdict d'ecretage ne se
    calcule pas: une page de synthese trop parfaite rendrait `clipped: None` partout.
    """
    seen: dict[str, int] = {}
    for patch in patches:
        replicate = seen.get(patch.value_id, 0)
        seen[patch.value_id] = replicate + 1
        rgb = np.asarray(patch.rgb, dtype=np.float64) / 255.0
        bgr = press(rgb[::-1])
        signed = 1.0 if replicate % 2 == 0 else -1.0
        bgr = np.clip(bgr + signed / 255.0, 0.0, 1.0)
        x0, y0 = page_templates.mm_to_px(patch.x_mm, patch.y_mm, dpi)
        x1, y1 = page_templates.mm_to_px(
            patch.x_mm + patch.size_mm, patch.y_mm + patch.size_mm, dpi)
        page[y0:y1, x0:x1] = np.clip(bgr * 255.0, 0, 255).round().astype(np.uint8)


def build_page(payload: dict, *, press, patches=None, dpi: int = DPI) -> np.ndarray:
    """Une planche **imprimee puis numerisee**, telle que l'operateur la pose.

    Les marqueurs de coin sont poses aux positions nominales du **vrai** gabarit et
    dessines par le **vrai** generateur; le QR porte le payload **serialise** par
    `io.payload`, place dans la zone reservee que le gabarit resout **pour le role de
    cette page**. Ce dernier point n'est pas un detail: la zone du QR d'une page de
    calibration n'est pas celle d'une planche d'images, et poser le QR a la place de
    l'autre le fait recouvrir par le treillis -- la page ressort alors sans payload, donc
    invisible en tant que page de calibration, et tout le lot sort `not_applied` sans
    qu'aucune assertion de couleur ne soit fausse.

    `patches` permet de fabriquer une page de calibration **illisible** en n'en peignant
    aucune: c'est le cas de l'AC 9, et il doit se construire sans truquer le code.
    """
    spec = page_templates.get_template(payload["template_id"])
    width_px, height_px = page_templates.page_size_px(spec, dpi)
    page = np.full((height_px, width_px, 3), 255, np.uint8)

    marker_px = int(round(layout.MARKER_SIZE_MM / 25.4 * dpi))
    for marker_id, (x_mm, y_mm) in page_templates.corner_marker_centers_mm(spec).items():
        marker = layout.generate_aruco_marker_image(marker_id, marker_px)
        centre_x, centre_y = page_templates.mm_to_px(x_mm, y_mm, dpi)
        left, top = centre_x - marker_px // 2, centre_y - marker_px // 2
        page[top:top + marker_px, left:left + marker_px] = cv2.cvtColor(
            marker, cv2.COLOR_GRAY2BGR)

    page_layout = patch_presets.resolve_page_layout(
        payload["template_id"], payload["page_role"])
    zone = next(z for z in page_layout.reserved_zones_mm if z["name"] == "qr_zone")
    side = int(round(qr_codes.QR_PRINT_SIZE_TARGET_MM / 25.4 * dpi))
    symbol = cv2.resize(
        qr_codes.encode_qr_image(payload_io.serialize_payload(payload)),
        (side, side), interpolation=cv2.INTER_NEAREST)
    qr_x, qr_y = page_templates.mm_to_px(zone["x"], zone["y"], dpi)
    page[qr_y:qr_y + side, qr_x:qr_x + side] = cv2.cvtColor(symbol, cv2.COLOR_GRAY2BGR)

    if payload["page_role"] == page_roles.PAGE_ROLE_CALIBRATION:
        defaut = patch_presets.resolve_calibration_page_patches(payload["template_id"])
    else:
        defaut = patch_presets.resolve_patch_layout(
            payload["template_id"], payload["patch_preset_id"])
        for index, frame_zone in enumerate(spec.frame_zones_mm):
            colour = np.asarray(
                FRAME_COLOURS_BGR[index % len(FRAME_COLOURS_BGR)], dtype=np.float64)
            printed = press(colour / 255.0)
            x0, y0 = page_templates.mm_to_px(frame_zone["x"], frame_zone["y"], dpi)
            x1, y1 = page_templates.mm_to_px(
                frame_zone["x"] + frame_zone["width"],
                frame_zone["y"] + frame_zone["height"], dpi)
            page[y0:y1, x0:x1] = np.clip(
                printed * 255.0, 0, 255).round().astype(np.uint8)

    _paint_patches(page, defaut if patches is None else patches, press, dpi=dpi)
    return page


def lot_payloads(*, sheet_count: int = 2, with_calibration: bool = True,
                 slot_count: int = 4, **surcharges) -> list[dict]:
    """Les payloads d'un lot: la page de calibration en index 0, puis les planches.

    `page_count` **compte** la page de calibration: c'est le contrat de `page_roles`, et
    la seule facon qu'a le rapport de sortie de declarer la page de calibration
    manquante quand elle l'est (AC 8).
    """
    page_count = sheet_count + (1 if with_calibration else 0)
    payloads = []
    if with_calibration:
        payloads.append(scan.make_payload(
            page_index=0, page_count=page_count, template_id=TEMPLATE,
            patch_preset_id=PRESET, page_role=page_roles.PAGE_ROLE_CALIBRATION,
            **surcharges))
    for rank in range(sheet_count):
        payloads.append(scan.make_payload(
            page_index=rank + (1 if with_calibration else 0), page_count=page_count,
            template_id=TEMPLATE, patch_preset_id=PRESET,
            first_slot=rank * slot_count, slot_count=slot_count, **surcharges))
    return payloads


def write_scan_folder(folder: Path, ordered) -> Path:
    """Ecrire le dossier de scan, **dans l'ordre ou l'operateur a pose ses feuilles**.

    `ordered` est une suite de couples `(payload, presse)`. L'ordre est un parametre du
    test et non une propriete du lot: c'est ce qui permet de poser la page de calibration
    ailleurs qu'en premiere position.
    """
    folder.mkdir(parents=True, exist_ok=True)
    for rank, (payload, press) in enumerate(ordered, start=1):
        cv2.imwrite(str(folder / f"page_{rank:02d}.tiff"),
                    build_page(payload, press=press))
    return folder


def run_scan(project_dir: Path, folder: Path, *args: str) -> int:
    return cli.main(["scan", "--project", str(project_dir), "--scan", str(folder),
                     "--dpi", str(DPI), *args])


#: **Le code d'un lot INCOMPLET ou tout en mires, depuis la story 11.4c** (lot
#: V2, AC 9.3). Trois sites le portent : deux ou le lot declare trois pages et
#: n'en pose que deux (la page de calibration manque a l'appel), un ou **toutes**
#: les planches ont perdu leur geometrie et n'ecrivent que des mires. Dans les
#: trois cas la persistance emet `LOT_INCOMPLET` -- le journal et le manifeste le
#: disaient deja -- et l'inventaire atteint desormais le code de sortie.
#:
#: **Ce n'est pas un refus** (`1`) : le lot est ecrit, et les assertions de ces
#: trois tests portent sur le document produit, pas sur le code. Tous les autres
#: sites de ce banc restent a `0` : leurs lots sont complets, et c'est ce qui
#: mesure que la degradation n'est pas systematique.
#:
#: Valeur ecrite en clair, jamais lue de `scan_write.CODE_SUCCES_PARTIEL` : lire
#: la constante que l'on mesure serait le test tautologique de la story 5.9.
LOT_INCOMPLET_MAIS_ECRIT = 4


def nominal_lot(tmp_path: Path, *, name: str = "lot",
                calibration_last: bool = True) -> tuple[Path, Path, list[dict]]:
    """Un lot nominal: une page de calibration et deux planches du meme tirage.

    La page de calibration est posee **en dernier** par defaut. Un lot dont elle serait
    toujours premiere laisserait passer une recherche qui rend la premiere page lue.
    """
    payloads = lot_payloads()
    feuilles = [(payloads[1], PRESSES_DU_TIRAGE[0]),
                (payloads[2], PRESSES_DU_TIRAGE[1])]
    calibration = (payloads[0], PRESSE_CALIBRATION)
    ordered = feuilles + [calibration] if calibration_last else [calibration] + feuilles
    folder = write_scan_folder(tmp_path / name, ordered)
    return tmp_path / f"projet-{name}", folder, payloads


# ---------------------------------------------------------------------------
# Le regime nominal DEPUIS `EPIC5-ARB-82`/`-83`: profil designe, lot de planches
# ---------------------------------------------------------------------------
#
# Les fabriques ci-dessous remplacent `nominal_lot()` et `_lot_deviant()` dans les
# tests rebases par la story 5.24 (AC 8, classe A). Elles ne sont pas un contournement
# du vrac: elles sont le regime **nominal** du depot depuis que l'operateur **designe**
# son profil. La page de calibration y est scannee dans une passe **separee**
# (`scan ... calibrate`), ce qui est exactement ce que 5.22 et 5.23 ont installe, et le
# lot ne porte plus que des planches d'images.
#
# Ce que les 19 tests de la classe A mesurent -- drapeaux, motifs, provenance, octets
# corriges -- porte sur la **correction d'un lot**, jamais sur le routage d'une page.
# Leur seul lien au vrac etait la fabrique qui posait la page de calibration dans la
# pile ; ils n'en ont donc pas besoin, et les rebaser ici les rend **plus** proches de
# ce que fait un operateur aujourd'hui.


#: **Deux** libelles de chaine differents. Deux feuilles au meme libelle
#: produiraient le meme nom de fichier de profil, donc un profil ecrase par
#: l'autre -- et « deux profils distincts » cesserait d'etre mesurable
#: (regle des fabriques, point 1).
LIBELLES_DE_CHAINE = ("hp envy 4520 tiff 300 dpi", "epson v600 tiff 300 dpi")


def page_de_calibration_autonome(**surcharges) -> dict:
    """La page de calibration **telle que le depot l'imprime depuis 5.22**.

    `page_count` vaut 1 et `page_index` vaut 0
    (`pdf_composition.CALIBRATION_ONLY_PAGE_COUNT`): cette feuille est composee
    **seule**, elle n'appartient a aucun lot et ne compte dans le cardinal
    d'aucun. `lot_payloads()[0]`, lui, modelise le regime **par lot** de 5.16 --
    ou elle etait litteralement la page 0 d'un lot --, et son `page_count`
    compte les planches: l'employer comme feuille autonome ferait declarer un
    lot de trois pages a une feuille qui en est seule.
    """
    surcharges.setdefault("page_count", 1)
    return scan.make_payload(
        page_index=0, template_id=TEMPLATE, patch_preset_id=PRESET,
        page_role=page_roles.PAGE_ROLE_CALIBRATION, **surcharges)


def consigner_le_profil_de_la_chaine(project_dir: Path, tmp_path: Path, *,
                                     name: str) -> Path:
    """Consigner le profil de la chaine dans une passe **separee**, et le rendre.

    C'est le geste 1 d'`EPIC5-ARB-83`: la page de calibration se scanne seule,
    `scan ... calibrate` en consigne le profil. Rien n'est **designe** ici --
    designer est le geste 2, et c'est l'appelant qui le pose (`--profil`).
    """
    folder = write_scan_folder(tmp_path / f"{name}-calibration",
                               [(page_de_calibration_autonome(), PRESSE_CALIBRATION)])
    assert cli.main(["scan", "--project", str(project_dir), "--scan", str(folder),
                     "--dpi", str(DPI), "calibrate"]) == 0
    (profil,) = sorted(
        (project_dir / project_layout.VERSIONS_DIRNAME / "calibration").glob("*.json"))
    return profil


def profil_du_projet(project_dir: Path) -> Path:
    """Le profil unique consigne dans ce projet. Le cardinal est **verifie**.

    Un projet qui en porterait deux rendrait ce raccourci ambigu, et un test qui
    designerait « un » profil ne prouverait plus lequel.
    """
    (profil,) = sorted((project_dir / project_layout.VERSIONS_DIRNAME / "calibration").glob("*.json"))
    return profil


def source_page_id_du_profil(project_dir: Path) -> str:
    """L'identifiant de la page qui a **ajuste** le profil du projet.

    C'est lui que la provenance d'un lot corrige doit porter depuis
    `EPIC5-ARB-83`: la correction vient du profil **designe**, donc sa source est
    la feuille de calibration de la chaine -- jamais une page du lot, et jamais
    une constante. Il est **relu au profil ecrit**, pas recopie ici: une chaine
    ecrite en dur figerait la recette au lieu de la verifier.
    """
    document = json.loads(profil_du_projet(project_dir).read_text(encoding="utf-8"))
    return document["source_page_id"]


def run_scan_designe(project_dir: Path, folder: Path, *args: str) -> int:
    """`scan` avec le profil du projet **designe** par `--profil`.

    Aucun profil n'est choisi a la place de l'operateur (`EPIC5-ARB-83`): les
    tests rebases le designent donc explicitement, exactement comme la commande
    l'exige.
    """
    return run_scan(project_dir, folder, cli.PROFILE_FLAG,
                    str(profil_du_projet(project_dir)), *args)


def lot_a_profil_designe(tmp_path: Path, *, name: str = "lot",
                         presses=None, sheet_count: int = 2):
    """Un projet dont la chaine a **deja** son profil, et un lot de planches seules.

    Les planches portent les index `0..n-1` et un `page_count` qui ne compte
    qu'elles: la page de calibration n'appartient a aucun lot depuis
    `EPIC5-ARB-82`, donc elle ne peut plus entrer dans le cardinal attendu d'un
    lot. C'est le decalage d'index a garder en tete en relisant les tests
    rebases -- les planches sont `payloads[0]` et `payloads[1]`.

    Elles sont imprimees sous des presses **differentes** (variation de tirage):
    un appariement planche -> resultat permute se verrait, et deux entrees de
    manifest identiques au chiffre pres ne prouveraient rien.
    """
    project_dir = tmp_path / f"projet-{name}"
    consigner_le_profil_de_la_chaine(project_dir, tmp_path, name=name)
    payloads = lot_payloads(sheet_count=sheet_count, with_calibration=False)
    presses = presses if presses is not None else PRESSES_DU_TIRAGE
    folder = write_scan_folder(tmp_path / name, list(zip(payloads, presses)))
    return project_dir, folder, payloads


def _lot_deviant_a_profil_designe(tmp_path: Path, *, name: str):
    """Meme regime, mais **la seconde** planche derive. La premiere est nominale.

    La feuille deviante n'est pas en premiere position, et ce n'est pas un detail
    de confort: un refus qui porterait sur « la premiere planche du lot » plutot
    que sur la page mesuree passerait un test ou la deviante est premiere.
    """
    return lot_a_profil_designe(
        tmp_path, name=name,
        presses=(PRESSES_DU_TIRAGE[0], couleur._DEVIANT_PRESS))


def manifest_of(project_dir: Path) -> dict:
    return json.loads((project_dir / "project.json").read_text(encoding="utf-8"))


def calibration_entries(document: dict) -> dict:
    return {entry["page_index"]: entry
            for entry in document["reconstruction"]["page_calibration_results"]}


def written_frames(project_dir: Path, document: dict) -> list[Path]:
    return sorted((project_dir / document["lots"][0]["output_frames_dir"]).glob("*.tiff"))


# ---------------------------------------------------------------------------
# AC 1 -- l'ajustement a lieu **une seule fois par lot**
# ---------------------------------------------------------------------------


class _Compteur:
    """Enrober une fonction du module `color_calibration` **vue par `cli`**.

    L'enrobage porte sur l'attribut du module et non sur une copie locale: c'est le
    chemin que `cli` emprunte reellement, et un test qui compterait les appels d'une
    reference qu'il tient lui-meme ne mesurerait que lui-meme.
    """

    def __init__(self, monkeypatch, nom: str) -> None:
        self.appels: list[dict] = []
        original = getattr(cc, nom)

        def enrobe(*args, **kwargs):
            self.appels.append(dict(kwargs))
            return original(*args, **kwargs)

        monkeypatch.setattr(cc, nom, enrobe)

    def __len__(self) -> int:
        return len(self.appels)


def test_la_correction_du_lot_est_ajustee_une_seule_fois_pour_tout_le_lot(
    tmp_path, monkeypatch,
) -> None:
    """AC 1. Un ajustement par planche serait le re-ajustement qu'`EPIC5-ARB-57` interdit.

    Les deux compteurs sont lus ensemble, et c'est ce qui rend l'assertion falsifiable:
    « une fois » ne veut rien dire si l'on ne dit pas **par rapport a quoi**. Le lot porte
    deux planches, donc un ajustement par planche compterait deux, et un ajustement par
    frame en compterait huit.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    ajustements = _Compteur(monkeypatch, "fit_lot_correction_from_page")
    calibrations = _Compteur(monkeypatch, "calibrate_page")
    project_dir, folder, payloads = lot_a_profil_designe(tmp_path)

    assert run_scan_designe(project_dir, folder) == 0

    assert len(ajustements) == 1, ajustements.appels
    # Une confrontation **par planche** et non un ajustement: deux planches, deux appels,
    # tous en regime transporte.
    assert len(calibrations) == 2, calibrations.appels
    assert all(appel["imported_profile"] is not None for appel in calibrations.appels)


def test_la_page_de_calibration_est_routee_par_son_role_et_non_par_son_rang(
    tmp_path,
) -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 3) -- **devient une propriete du tri**.

    L'assertion morte etait « la page de calibration se cherche par son role DANS
    LA PILE DU LOT » : elle n'appartient plus a aucun lot (`EPIC5-ARB-82`). Ce qui
    survit -- et qui est la propriete de fond -- est que **le role se lit dans le
    payload, jamais au rang**.

    La meme pile est scannee deux fois, la page de calibration posee **en dernier**
    puis **en premier**. Une recherche par rang de lecture (`report.pages[0]`)
    passerait la seconde et echouerait la premiere ; une recherche par `page_index`
    passerait les deux et se casserait sur une pile ou l'operateur a interverti deux
    feuilles, ce qui est le cas que `read_rank` existe pour enregistrer.
    """
    resultats = []
    for dernier in (True, False):
        nom = "pile-fin" if dernier else "pile-debut"
        payloads = lot_payloads(sheet_count=2, with_calibration=False)
        calibration = (page_de_calibration_autonome(
            scan_chain_label=LIBELLES_DE_CHAINE[0]), PRESSE_CALIBRATION)
        planches = [(payloads[0], PRESSES_DU_TIRAGE[0]),
                    (payloads[1], PRESSES_DU_TIRAGE[1])]
        folder = write_scan_folder(
            tmp_path / nom,
            planches + [calibration] if dernier else [calibration] + planches)
        project_dir = tmp_path / f"projet-{nom}"

        assert run_scan(project_dir, folder) == 0

        rapport = json.loads(
            (project_dir / project_layout.SCANS_DIRNAME / nom / cli.TRI_DOCUMENT_FILENAME).read_text(
                encoding="utf-8"))
        # Une seule page de calibration, un seul lot de deux planches -- quel que
        # soit l'ordre d'arrivee.
        resultats.append((
            [entree["scan_chain_label"] for entree in rapport["calibration"]],
            [len(lot["pages"]) for lot in rapport["lots"]],
            [profil["etiquette"] for profil in rapport["profils_crees"]],
        ))
        # Et la page de calibration n'a **aucune** entree dans le lot.
        assert set(calibration_entries(manifest_of(project_dir))) == {0, 1}
    assert resultats[0] == resultats[1], resultats
    assert resultats[0] == ([LIBELLES_DE_CHAINE[0]], [2], [LIBELLES_DE_CHAINE[0]])


def test_deux_pages_de_calibration_dans_une_passe_sont_deux_entrees_de_chaine(
    tmp_path,
) -> None:
    """REECRIT PAR 5.24 (AC 7 et AC 8, classe B) -- le sujet a bascule.

    Ce test exigeait un **refus**: choisir entre deux pages de calibration
    revenait a ajuster tout le lot au hasard entre deux treillis. Cette assertion
    est morte pour de bon avec `EPIC5-ARB-82` -- une page de calibration
    n'appartient plus a aucun lot --, donc deux d'entre elles dans une meme passe
    ne sont plus un conflit **de lot**: ce sont **deux entrees de chaine**, et le
    vrac les consigne toutes les deux (`EPIC5-ARB-107`).

    Les deux regimes sont mesures sur la **meme** pile, et c'est ce qui empeche
    le test d'etre vrai par accident:

    * **avec `--lot-slug`**, l'operateur promet un lot unique: la pile mixte
      recoit toujours son refus nomme, et rien n'est ecrit;
    * **sans `--lot-slug`**, le tri par QR range: le lot sort, et **deux** profils
      distincts sont consignes -- pas un ecrase par l'autre.
    """
    payloads = lot_payloads(sheet_count=2, with_calibration=False)
    calibrations = [page_de_calibration_autonome(scan_chain_label=libelle)
                    for libelle in LIBELLES_DE_CHAINE]
    # La cible n'est ni premiere ni derniere, et les deux feuilles de calibration
    # sont separees par une planche.
    feuilles = [
        (payloads[0], PRESSES_DU_TIRAGE[0]),
        (calibrations[0], PRESSE_CALIBRATION),
        (payloads[1], PRESSES_DU_TIRAGE[1]),
        (calibrations[1], PRESSE_CALIBRATION),
    ]
    promis = write_scan_folder(tmp_path / "melange-promis", feuilles)
    trie = write_scan_folder(tmp_path / "melange-trie", feuilles)

    projet_promis = tmp_path / "projet-melange-promis"
    assert run_scan(projet_promis, promis, "--lot-slug", "melange-promis") == 1
    # Rien n'a ete ecrit: le refus precede l'ecriture des frames.
    assert not (projet_promis / project_layout.SCAN_FRAMES_DIRNAME).exists()

    projet_trie = tmp_path / "projet-melange-trie"
    assert run_scan(projet_trie, trie) == 0
    profils = sorted((projet_trie / project_layout.VERSIONS_DIRNAME / "calibration").glob("*.json"))
    assert len(profils) == 2, [chemin.name for chemin in profils]
    # Le lot, lui, ne compte **aucune** des deux: elles n'appartiennent a aucun lot.
    entrees = calibration_entries(manifest_of(projet_trie))
    assert set(entrees) == {0, 1}, entrees


# ---------------------------------------------------------------------------
# AC 2 -- le transport, et la frontiere negative qui le garde
# ---------------------------------------------------------------------------


def test_chaque_planche_recoit_la_correction_du_lot_et_aucune_ne_s_ajuste_sur_elle_meme(
    tmp_path, monkeypatch,
) -> None:
    """AC 2, dans ses deux moities.

    La moitie positive: chaque planche est calibree avec `imported_profile` = le profil
    du lot **et** `imported_source_page_id` = la page de calibration. La moitie negative,
    qui est celle qui compte: **aucun** appel du chemin des planches ne se fait sans
    profil importe. Un repli « si le transport echoue, ajuste sur soi-meme » produirait
    des pixels corriges plausibles et un manifest qui les declare corriges, et c'est
    exactement la clause qu'`EPIC5-ARB-57` interdit.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    calibrations = _Compteur(monkeypatch, "calibrate_page")
    project_dir, folder, payloads = lot_a_profil_designe(tmp_path)

    assert run_scan_designe(project_dir, folder) == 0

    # La source de la correction est desormais la page qui a ajuste le **profil
    # designe** (`EPIC5-ARB-83`), relue au profil ecrit -- jamais une page du lot,
    # et surtout jamais une constante.
    attendu = source_page_id_du_profil(project_dir)
    assert attendu not in {f"{payloads[0]['lot_id']}-p{index}" for index in (0, 1)}
    assert calibrations.appels, "aucune planche calibree: le test ne mesurerait rien"
    profils = {id(appel["imported_profile"]) for appel in calibrations.appels}
    assert len(profils) == 1, "les deux planches doivent recevoir le **meme** profil"
    for appel in calibrations.appels:
        assert appel["imported_profile"] is not None
        assert appel["imported_source_page_id"] == attendu, appel
        assert appel["page_id"] != attendu, "une planche n'est pas sa page de calibration"


def test_aucune_planche_n_est_calibree_sans_profil_importe_dans_le_source() -> None:
    """Frontiere negative de l'AC 2, lue sur l'**arbre syntaxique** du chemin de scan.

    Le test de comportement ci-dessus mesure les appels d'un lot nominal; celui-ci
    mesure qu'il n'existe **aucun** autre appel dans `cli.py`, y compris sur une branche
    qu'aucun lot du depot ne fait prendre. C'est le meme geste que la frontiere du
    contournement de 5.16, et pour la meme raison: une branche jamais prise est un cas
    jamais observe.

    Il ne grep pas du texte -- c'est ce qui a laisse passer un bloquant sur 5.17 -- il
    parcourt l'AST et regarde les **mots-cles de chaque appel**.
    """
    import ast

    # Story 11.4b (lot S1): la calibration page par page a suivi la moitie aval
    # du scan dans le module de coeur `scan_write`. Meme mesure, meme
    # assertion, a l'endroit ou le code est parti.
    source = ast.parse(
        (REPO_ROOT / "src" / "mixed_media_utility" / "scan_write.py").read_text(
            encoding="utf-8"))
    appels = [
        noeud for noeud in ast.walk(source)
        if isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Attribute)
        and noeud.func.attr == "calibrate_page"
    ]
    assert appels, ("aucun appel a calibrate_page dans scan_write.py: la story "
                    "n'est pas cablee")
    for appel in appels:
        mots = {mot.arg for mot in appel.keywords}
        assert "imported_profile" in mots, ast.dump(appel)
        assert "imported_source_page_id" in mots, ast.dump(appel)


# ---------------------------------------------------------------------------
# AC 3 -- **les pixels**, et rien d'autre
# ---------------------------------------------------------------------------


def _frame_centre(path: Path) -> np.ndarray:
    """La couleur au centre d'une frame ecrite, ramenee dans [0, 1] en BGR."""
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    assert image is not None and image.dtype == np.uint16, path
    height, width = image.shape[:2]
    return image[height // 2, width // 2].astype(np.float64) / 65535.0


def test_les_pixels_du_master_changent_et_vont_vers_la_reference(tmp_path) -> None:
    """AC 3, la plus importante de la story, et elle se mesure **sur les fichiers**.

    Le meme lot est scanne deux fois: avec sa page de calibration, puis sans. Les deux
    passes ecrivent les memes frames a partir des **memes** rasters de planche, donc tout
    ecart entre les fichiers vient de la correction et de rien d'autre.

    Trois assertions, et la troisieme est celle qui interdit la correction identite:

    1. les fichiers different -- une correction qui ne change aucun octet n'a pas ete
       appliquee;
    2. la couleur corrigee est **plus proche** de la couleur d'origine (celle qui a ete
       imprimee) que la couleur mesuree ne l'etait;
    3. l'ecart residuel est petit dans l'absolu. Sans elle, « plus proche » serait tenu
       par une correction qui rapproche d'un centieme de code.

    Les quatre zones portent quatre couleurs distinctes et l'assertion porte sur chacune:
    une correction qui ne marcherait que sur un bleu passerait un test a une couleur.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    corrige_dir, folder, payloads = lot_a_profil_designe(tmp_path, name="avec")
    assert run_scan_designe(corrige_dir, folder) == 0

    # Le meme lot, aux memes pixels de planche, mais sans sa page de calibration: c'est
    # le temoin, et il est produit par la **meme** fabrique.
    # Le temoin est le **meme lot sans profil designe**: aucun profil n'etant
    # choisi a la place de l'operateur (`EPIC5-ARB-83`), il sort brut. C'est
    # exactement le role que tenait « le meme lot sans sa page de calibration »
    # avant la rebase, et le raster des planches est identique des deux cotes.
    nu_dir = tmp_path / "projet-sans"
    nu_folder = write_scan_folder(tmp_path / "sans", [
        (payloads[0], PRESSES_DU_TIRAGE[0]), (payloads[1], PRESSES_DU_TIRAGE[1])])
    assert run_scan(nu_dir, nu_folder) == 0

    corriges = written_frames(corrige_dir, manifest_of(corrige_dir))
    nus = written_frames(nu_dir, manifest_of(nu_dir))
    assert len(corriges) == len(nus) == 8

    for corrige, nu in zip(corriges, nus):
        assert corrige.name == nu.name
        assert corrige.read_bytes() != nu.read_bytes(), (
            f"{corrige.name}: la correction n'a change aucun octet")

    # Et l'ecart va **dans le sens de la reference**, couleur par couleur.
    for index, (corrige, nu) in enumerate(zip(corriges[:4], nus[:4])):
        vraie = np.asarray(FRAME_COLOURS_BGR[index], dtype=np.float64) / 255.0
        ecart_corrige = float(np.abs(_frame_centre(corrige) - vraie).max())
        ecart_nu = float(np.abs(_frame_centre(nu) - vraie).max())
        assert ecart_corrige < ecart_nu, (corrige.name, ecart_corrige, ecart_nu)
        # **Le plafond est relatif d'abord, absolu ensuite**, et cet ordre est le
        # correctif de la story 5.21. La borne d'origine etait un absolu de 2 codes,
        # mesure sous la forme affine (~0,75 code corrige contre ~27,7 non corrige).
        # Sous la forme active, la meme fabrique rend 1,33 a 5,36 codes corriges contre
        # 19 a 28 non corriges (mesure du 2026-08-14, `EPIC5-ARB-79`).
        #
        # **Ce n'est pas une regression, et c'est pourquoi la borne bouge au lieu que le
        # code bouge**: la presse de cette fabrique est un gain-decalage par canal,
        # c'est-a-dire exactement la deformation que la forme affine est construite pour
        # inverser -- elle y est quasi exacte par construction. La forme active a ete
        # choisie sur les **captures reelles**, ou les deux formes existantes sont
        # refusees (`H9`). Une fixture de synthese ne reproduit pas le regime de terrain,
        # lecon deja payee le 2026-08-10 sur le seuillage ArUco.
        #
        # Ce que la borne doit interdire reste ce qu'elle interdisait: « plus proche »
        # tenu par une correction qui rapproche d'un centieme de code. Un rapport le dit
        # mieux qu'un absolu -- il ne se redate pas a chaque changement de forme et il
        # mord d'autant plus que le scan est deforme.
        assert ecart_corrige < ecart_nu / 3.0, (
            corrige.name, ecart_corrige * 255.0, ecart_nu * 255.0)
        assert ecart_corrige < 6.0 / 255.0, (corrige.name, ecart_corrige * 255.0)


def _page_de_planche(colour_bgr, *, slot_count: int = 1, page_index: int = 0,
                     page_count: int = 1, first_slot: int | None = None
                     ) -> sof.ScannedPage:
    """Une planche minimale dont les frames portent une couleur connue.

    Fabrique d'unite, distincte de la fabrique de raster ci-dessus: ici on entre
    directement dans la couche qui ecrit, pour isoler l'application aux pixels de tout ce
    qui la precede. `page_index` et `page_count` sont des parametres parce que
    l'identite de lot les confronte entre pages: une fabrique qui les figerait ne pourrait
    produire qu'un lot d'une page, donc aucun appariement.
    """
    payload = scan.make_payload(
        page_index=page_index, page_count=page_count, template_id=TEMPLATE,
        patch_preset_id=PRESET,
        first_slot=page_index * slot_count if first_slot is None else first_slot,
        slot_count=slot_count)
    plan = scan.crop_plan_for(payload)
    codes = np.asarray(colour_bgr, dtype=np.uint16) * 257
    frames = []
    for frame in plan.frames:
        image = np.empty((frame.height_px, frame.width_px, 3), np.uint16)
        image[:, :] = codes
        frames.append(image)
    return sof.ScannedPage(payload=payload, crop_plan=plan, frames=tuple(frames))


def _profil_de_gain(gain: float) -> cc.CorrectionProfile:
    """Un profil qui multiplie la lumiere lineaire par `gain`. Volontairement trivial.

    Il n'est pas ajuste sur des mesures: cette unite mesure l'**application**, pas
    l'ajustement, et un profil dont on connait l'effet exact est ce qui permet d'affirmer
    que les pixels ont bouge du bon cote.
    """
    return cc.CorrectionProfile(stage_a=np.array([[gain, 0.0]] * 3, dtype=np.float64),
                                stage_m=np.eye(3, dtype=np.float64))


def test_la_meme_page_ecrite_avec_et_sans_profil_rend_des_fichiers_differents(
    tmp_path,
) -> None:
    """AC 3 a l'unite: `write_lot_output_frames` applique, il ne se contente pas de declarer.

    Le temoin negatif est dans le meme test et il est indispensable: un profil **identite**
    doit rendre les fichiers identiques. Sans lui, la premiere assertion serait tenue par
    n'importe quelle difference -- une date, un chemin -- et non par la correction.
    """
    page = _page_de_planche((40, 90, 200))
    sans = sof.write_lot_output_frames(tmp_path / "sans", [page])
    avec = sof.write_lot_output_frames(tmp_path / "avec", [page],
                                       page_profiles=((0, _profil_de_gain(0.5)),),
                                       color_calibration_status="applied")
    identite = sof.write_lot_output_frames(
        tmp_path / "identite", [page], page_profiles=((0, _profil_de_gain(1.0)),),
        color_calibration_status="applied")

    fichier_sans = tmp_path / "sans" / sans.output_dir
    fichier_avec = tmp_path / "avec" / avec.output_dir
    fichier_identite = tmp_path / "identite" / identite.output_dir
    nom = sans.frames[0].filename

    octets_sans = (fichier_sans / nom).read_bytes()
    assert (fichier_avec / nom).read_bytes() != octets_sans, (
        "un profil qui assombrit de moitie doit changer les octets")
    assert (fichier_identite / nom).read_bytes() == octets_sans, (
        "temoin: un profil identite ne change rien, donc la premiere assertion mesure "
        "bien la correction et pas un artefact d'ecriture")

    # Et le sens de l'ecart est celui du profil: un gain de 0,5 en lumiere lineaire
    # assombrit.
    assert (_frame_centre(fichier_avec / nom) < _frame_centre(fichier_sans / nom)).all()


def test_les_deux_bornes_de_plausibilite_du_treillis_ont_des_domaines_distincts() -> None:
    """Finding `m1`: la moitie haute de la garde est inatteignable, et il faut le dire.

    `fit_lot_correction_from_page` recopie de `calibrate_page` la garde
    `measured.min() < low or measured.max() > high` avec `PLAUSIBLE_RANGE == (0.01, 1.0)`.
    Or `sample_patches` normalise en divisant par `255` ou `65535`: une pastille saturee
    rend **exactement** `1.0`, donc la borne haute ne peut pas mordre. Le commentaire la
    declarait active -- forme exacte du piege paye sept fois par ce depot.

    Le test epingle la garde **par ses deux bouts**: la borne basse mord sur un domaine
    construit, la borne haute est inerte a la valeur livree et on mesure *pourquoi* --
    l'invariant de normalisation -- plutot que de le supposer.
    """
    spec = page_templates.get_template(TEMPLATE)
    width_px, height_px = page_templates.page_size_px(spec, DPI)
    patches = patch_presets.resolve_calibration_page_patches(TEMPLATE)

    # Borne haute: une page **entierement saturee** en 8 comme en 16 bits. La mesure
    # atteint le maximum et ne le depasse jamais.
    for saturee in (np.full((height_px, width_px, 3), 255, np.uint8),
                    np.full((height_px, width_px, 3), 65535, np.uint16)):
        mesures, _ids = cc.sample_patches(saturee, patches, DPI)
        assert mesures.max() == 1.0
        assert mesures.max() <= cc.PLAUSIBLE_RANGE[1]

    # Borne basse: une page noire tombe sous `0.01` et la garde rend son motif. C'est le
    # seul des deux domaines qui soit atteignable par un raster.
    noire = np.zeros((height_px, width_px, 3), np.uint8)
    mesures, _ids = cc.sample_patches(noire, patches, DPI)
    assert mesures.min() < cc.PLAUSIBLE_RANGE[0]
    resultat = cc.fit_lot_correction_from_page(
        noire, template_id=TEMPLATE, dpi=DPI, source_page_id="lot-a-p0")
    assert resultat.failure_reason == cc.FAILURE_PATCHES_OUT_OF_RANGE


def test_l_echelle_de_mesure_suit_la_largeur_du_type_et_non_son_ordre_d_octets() -> None:
    """Finding `F3`: la moitie « ordre d'octets » de l'ecart que B3 avait ferme a moitie.

    `color_pipeline.validate_bgr_input` declare licite -- et normalise -- un TIFF 16 bits
    gros-boutien (`>u2`, l'ordre `MM` des scanners), mais la page de calibration ne passe
    pas par cette normalisation et `sample_patches` choisissait son echelle par
    `dtype == np.uint16`, **faux** pour `>u2`. L'echelle 255 etait donc appliquee a des
    codes 16 bits: la mesure sortait a `44,3`-`242,9` au lieu de `0,17`-`0,95`, et tout le
    lot ressortait `failed` sous un motif qui accusait l'impression pour un reglage de
    scanner.

    Les **trois** dtypes sont mesures ensemble et doivent rendre la meme chose a l'echelle
    pres: c'est la seule forme qui distingue « l'echelle est correcte » de « le refus tombe
    par accident d'arithmetique ».
    """
    spec = page_templates.get_template(TEMPLATE)
    width_px, height_px = page_templates.page_size_px(spec, DPI)
    patches = patch_presets.resolve_calibration_page_patches(TEMPLATE)
    huit = build_page(payload_de_calibration := lot_payloads()[0], press=PRESSE_CALIBRATION)
    assert payload_de_calibration["page_role"] == page_roles.PAGE_ROLE_CALIBRATION
    assert huit.shape == (height_px, width_px, 3)

    seize = (huit.astype(np.uint16)) * 257
    gros_boutien = seize.astype(">u2")
    assert gros_boutien.dtype != np.uint16, (
        "le montage exige un dtype non natif, sinon il ne mesure pas l'ordre d'octets")

    mesures = {}
    for nom, raster in (("uint8", huit), ("uint16", seize), (">u2", gros_boutien)):
        valeurs, _ids = cc.sample_patches(raster, patches, DPI)
        mesures[nom] = (float(valeurs.min()), float(valeurs.max()))
        assert valeurs.max() <= cc.PLAUSIBLE_RANGE[1], (nom, mesures[nom])

    assert mesures[">u2"] == pytest.approx(mesures["uint16"], abs=1e-12)
    assert mesures[">u2"] == pytest.approx(mesures["uint8"], abs=2e-3), mesures
    # Et la consequence de bout en bout: le lot est ajustable sur le raster gros-boutien.
    assert cc.fit_lot_correction_from_page(
        gros_boutien, template_id=TEMPLATE, dpi=DPI,
        source_page_id="lot-a-p0").failure_reason != cc.FAILURE_PATCHES_OUT_OF_RANGE


def test_le_chemin_de_lot_filtre_le_treillis_pour_la_forme_qu_il_ajuste() -> None:
    """`EPIC5-ARB-77`: le meme `correction_form_id` gouverne le filtre **et** l'ajustement.

    C'est ce qui rend le desaccord de politique de plancher d'encrage **inatteignable**
    depuis la production: `lattice_adjustment_source` filtre pour la forme que
    `fit_from_external_source` va ajuster, jamais pour une autre. Sans ce cablage, la
    garde `InkFloorPolicyMismatchError` ferait echouer toute page de calibration ajustee
    sous la forme nouvelle -- le cas est donc atteignable et le temoin est necessaire.

    **Le cardinal retenu est ce qui le prouve**, et non le seul succes: il differe
    d'exactement le cardinal du plancher entre les deux politiques. Un cablage qui
    passerait toujours la forme par defaut rendrait les trois cardinaux egaux.
    """
    page = build_page(lot_payloads()[0], press=PRESSE_CALIBRATION)
    # Le cardinal compte des **pastilles placees**, pas des valeurs distinctes:
    # `retained_patch_count` est ce que le filtre a garde avant l'agregation H4 par
    # valeur, et le treillis imprime chaque valeur en replicat. Deriver le chiffre du
    # placement plutot que du nombre de valeurs sous le plancher est ce qui garde ce
    # test juste si le replicat change.
    sous_plancher = set(patch_values.ink_floor_lattice_value_ids())
    plancher = sum(1 for pose in patch_presets.resolve_calibration_page_patches(TEMPLATE)
                   if pose.value_id in sous_plancher)
    assert plancher >= 1, "aucune pastille sous le plancher: ce test serait vide"

    retenus = {}
    for form_id in cc.CORRECTION_FORMS:
        lot = cc.fit_lot_correction_from_page(
            page, template_id=TEMPLATE, dpi=DPI, source_page_id="lot-a-p0",
            correction_form_id=form_id)
        assert lot.failure_reason is None, (form_id, lot.failure_reason)
        assert lot.correction_form_id == form_id
        retenus[form_id] = lot.retained_patch_count

    assert retenus[cc.CORRECTION_FORM_TONE_CHROMA_ID] == \
        retenus[cc.CORRECTION_FORM_ID] + plancher, retenus
    # Les deux formes qui **partagent** la politique gardent le meme cardinal: sans
    # cette ligne, un filtre qui varierait avec n'importe quoi d'autre que la politique
    # satisferait l'assertion precedente.
    assert retenus[cc.CORRECTION_FORM_LAB_ID] == retenus[cc.CORRECTION_FORM_ID], retenus


def _appels_de_cli(*noms: str) -> list[ast.Call]:
    """Tous les appels de `cli.py` qui portent l'un de ces noms, lus a l'AST.

    Lecture par AST et non par `grep`: un `grep` sur `correction_form_id` dans `cli.py`
    rendrait aussi la **lecture** du champ pour le manifest (le site qui transporte
    `lot_correction.correction_form_id`), qui est licite et n'a rien a voir avec le fait
    de **nommer une forme a l'appel**. Ce qui se mesure ici est le mot-cle d'appel, seul.

    **Story 11.4b (lot S1) : le balayage porte sur les DEUX fichiers du chemin
    de scan.** La moitie aval -- correction du lot, recadrage, calibration page
    par page -- a suivi l'orchestration dans le module de coeur `scan_write`,
    exactement comme la moitie amont avait suivi `scan_detect` en 7.3. Ne
    compter que `cli.py` ferait tomber les cardinaux a zero sans qu'un seul
    appel n'ait disparu : c'est l'erosion de garde deja payee en 5.24, pas un
    progres. Les cardinaux ci-dessous sont donc inchanges.
    """
    from mixed_media_utility import scan_write

    cibles = []
    for module in (cli, scan_write):
        arbre = ast.parse(
            pathlib.Path(module.__file__).read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            fonction = noeud.func
            nom = fonction.attr if isinstance(fonction, ast.Attribute) else (
                fonction.id if isinstance(fonction, ast.Name) else None)
            if nom in noms:
                cibles.append(noeud)
    return cibles


def test_le_defaut_de_transport_du_lot_suit_la_forme_active_et_ses_appelants_le_laissent_muet(
) -> None:
    """AC 2 de la story 5.21, sur le seul defaut de transport **atteint en production**.

    Trou de couverture mesure le 2026-08-19 par injection ciblee (tache 7 de 5.21) : le
    mutant qui remet ce defaut de champ sur `CORRECTION_FORM_ID` **survivait** au lot
    entier de la story (282 tests). Ce n'est pas un defaut theorique : `cli.py` construit
    `LotCorrection` directement sur ses deux chemins d'echec amont -- page de calibration
    presente mais non redressable, et raster non relisable -- **sans nommer de forme**,
    parce qu'aucune n'a encore tourne a ce stade. Sous le mutant, le manifest de ces deux
    lots declare que le lot devait etre corrige sous la forme affine alors que la commande
    `scan` demandait la forme active : un enregistrement faux sur precisement les lots
    qu'on relit.

    Les deux moities sont necessaires et ne se remplacent pas. La premiere fixe la valeur
    du defaut ; la seconde mesure que ce defaut est bien ce qui decide en production --
    un appelant qui se mettrait a nommer la forme rendrait la premiere vraie et sans
    portee.
    """
    muet = cc.LotCorrection(source_page_id="lot-a-p0", template_id=TEMPLATE)
    assert muet.correction_form_id == cc.ACTIVE_CORRECTION_FORM_ID
    # Non-egalite explicite : sans elle, un revert de `ACTIVE_CORRECTION_FORM_ID` a la
    # forme affine laisserait l'assertion precedente vraie et vide.
    assert muet.correction_form_id != cc.CORRECTION_FORM_ID

    constructions = _appels_de_cli("LotCorrection")
    assert len(constructions) == 2, (
        "les deux chemins d'echec amont de `cli.py` sont ce qui rend ce defaut atteint ; "
        f"{len(constructions)} construction(s) lue(s) -- si le cardinal a change, ce test "
        "doit etre requalifie plutot qu'ajuste")
    for appel in constructions:
        assert "correction_form_id" not in {mot.arg for mot in appel.keywords}, (
            "un appelant de production nomme la forme a la construction du lot : le "
            "defaut de champ cesse alors de decider, et l'AC 2 ne porte plus")


def test_aucun_appel_de_cli_ne_nomme_de_forme_de_correction() -> None:
    """AC 3 de la story 5.21 : le silence de `cli.py` **est** le comportement de production.

    L'AC 3 avait ete verifiee par lecture exhaustive au moment du developpement, jamais
    par une mesure. L'injection ciblee du 2026-08-19 (tache 7) l'a montre : le mutant qui
    ajoute `correction_form_id=color_calibration.CORRECTION_FORM_ID` a l'appel de
    `fit_lot_correction_from_page` dans `cli.py` **survivait** au lot entier -- la
    commande `scan` serait revenue a la forme affine sans qu'aucun test ne rougisse.

    Ce que ce test ne pretend pas etre : une garde contre un flag de forme. Il n'en existe
    aucun sur ce depot (option (b) de `H9`, non retenue), et le jour ou l'un serait ajoute,
    c'est ce test qu'il faudra amender -- explicitement, ce qui est le point.
    """
    appels = _appels_de_cli("fit_lot_correction_from_page", "calibrate_page",
                            "LotCorrection")
    assert len(appels) >= 3, (
        f"{len(appels)} appel(s) lu(s) dans cli.py : le perimetre de cette frontiere a "
        "change, elle doit etre requalifiee plutot que rendue vide")
    nommes = [ast.unparse(appel.func) for appel in appels
              if "correction_form_id" in {mot.arg for mot in appel.keywords}]
    assert nommes == [], (
        f"cli.py nomme une forme de correction a l'appel de {nommes} : le defaut de "
        "production (`ACTIVE_CORRECTION_FORM_ID`) cesse de decider, et la bascule de la "
        "story 5.21 est annulee en silence")


@pytest.mark.parametrize("forme,canaux", [("monochrome", 1), ("bgra", 4)])
def test_une_page_qui_n_est_pas_bgr_est_refusee_par_un_motif_et_non_par_une_trace(
    forme, canaux,
) -> None:
    """Bloquant B3 de la revue: un scan en niveaux de gris tuait la commande.

    Le regime est **licite** en amont -- `color_pipeline.validate_bgr_input`, par laquelle
    toute page passe a l'ingestion, accepte `ndim == 2` et les cardinaux 1, 3 et 4 --,
    donc la page arrivait jusqu'a `sample_patches`, qui fait `reshape(-1, 3)`. Deux sorties
    possibles, et la seconde est la dangereuse:

    * `1` canal: le reshape leve une `ValueError` nue qui traversait `main`, et l'operateur
      recevait une trace Python au lieu du refus motive dont la commande est proprietaire ;
    * `4` canaux: le reshape **reussit** des que l'aire du carre echantillonne fois quatre
      est divisible par trois, et rend des triplets qui melangent les canaux -- une
      correction plausible ajustee sur des gris, declaree `applied`, appliquee a tout le
      lot.

    Les deux formes sont donc exercees ensemble: une garde qui ne fermerait que la
    premiere laisserait passer exactement le cas ou rien ne se plaint.
    """
    spec = page_templates.get_template(TEMPLATE)
    width_px, height_px = page_templates.page_size_px(spec, DPI)
    if canaux == 1:
        page = np.full((height_px, width_px), 128, np.uint8)
    else:
        page = np.full((height_px, width_px, 4), 128, np.uint8)

    resultat = cc.fit_lot_correction_from_page(
        page, template_id=TEMPLATE, dpi=DPI, source_page_id="lot-a-p0")
    assert not resultat.available
    assert resultat.failure_reason == cc.FAILURE_NOT_THREE_CHANNELS, forme

    # Meme garde, meme motif, sur le regime des **planches**: `calibrate_page` a un
    # appelant de production depuis 5.19, et il recoit le meme raster.
    planche = cc.calibrate_page(
        page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=DPI, page_id="lot-a-p1",
        imported_profile=_profil_de_gain(1.0), imported_source_page_id="lot-a-p0")
    assert planche.status == "failed"
    assert planche.failure_reason == cc.FAILURE_NOT_THREE_CHANNELS, forme

    # Et le temoin qui rend les deux assertions precedentes non vides: la **meme** page a
    # trois canaux passe la garde et va plus loin -- le motif rendu n'est plus celui-ci.
    trois = np.full((height_px, width_px, 3), 128, np.uint8)
    assert cc.page_has_three_channels(trois)
    assert cc.fit_lot_correction_from_page(
        trois, template_id=TEMPLATE, dpi=DPI,
        source_page_id="lot-a-p0").failure_reason != cc.FAILURE_NOT_THREE_CHANNELS


def test_une_feuille_de_calibration_monochrome_va_au_reliquat_sans_contaminer_le_lot(
    tmp_path,
) -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 4 et AC 7).

    L'assertion morte etait « le **lot** ressort `failed` » : le lot heritait du
    sort d'une feuille qui ne lui appartient pas. Ce qui survit est la propriete de
    fond -- une feuille de calibration inexploitable est un **refus motive et non
    une trace** --, et elle bascule sur le reliquat : la feuille y va **avec son
    motif**, et le verdict des lots de la passe n'en depend pas.

    Le mecanisme du bloquant d'origine etait un `ValueError` nu traversant `main` :
    le seul test qui en rende compte est celui qui appelle la commande.
    """
    payloads = lot_payloads(sheet_count=2, with_calibration=False)
    folder = write_scan_folder(tmp_path / "monochrome", [
        (payloads[0], PRESSES_DU_TIRAGE[0]),
        (page_de_calibration_autonome(scan_chain_label=LIBELLES_DE_CHAINE[1]),
         PRESSE_CALIBRATION),
        (payloads[1], PRESSES_DU_TIRAGE[1])])
    # **Seule la feuille de calibration est monochrome** -- c'est exactement ce que
    # la propriete mesure : elle ne doit contaminer aucun lot.
    calibration_tiff = folder / "page_02.tiff"
    cv2.imwrite(str(calibration_tiff),
                cv2.cvtColor(cv2.imread(str(calibration_tiff), cv2.IMREAD_UNCHANGED),
                             cv2.COLOR_BGR2GRAY))
    project_dir = tmp_path / "projet-monochrome"

    assert run_scan(project_dir, folder) == 0, (
        "une feuille monochrome est une entree licite: les planches du lot "
        "s'ecrivent, non corrigees")

    document = manifest_of(project_dir)
    assert len(written_frames(project_dir, document)) == 8
    rapport = json.loads(
        (project_dir / project_layout.SCANS_DIRNAME / "monochrome" / cli.TRI_DOCUMENT_FILENAME).read_text(
            encoding="utf-8"))
    # **Aucun profil n'est consigne** pour cette feuille, et elle est au reliquat
    # avec son motif.
    assert rapport["profils_crees"] == [], rapport["profils_crees"]
    assert [entree["motif"] for entree in rapport["reliquat"]] == [
        scan_sorting.RELIQUAT_CALIBRATION_INEXPLOITABLE], rapport["reliquat"]
    assert rapport["reliquat"][0]["locator"]["source_path"].endswith("page_02.tiff")
    # **Le lot n'herite pas de son sort**: il porte deux planches intactes.
    assert len(rapport["lots"]) == 1
    assert len(rapport["lots"][0]["pages"]) == 2


def test_une_mire_de_remplacement_n_est_jamais_corrigee(tmp_path) -> None:
    """Une mire n'est pas le contenu source, et elle est achromatique par construction.

    La corriger la teinterait, et le manifest de 5.7 tient deja `applied` pour
    incompatible avec une page entierement synthetique. Le test ecrit **deux** pages -- une
    reelle et une en echec -- pour que la comparaison porte sur le meme lot: une page
    unique laisserait passer un code qui ne corrige jamais rien.
    """
    reelle = _page_de_planche((40, 90, 200), slot_count=2, page_count=2)
    payload = scan.make_payload(page_index=1, page_count=2, template_id=TEMPLATE,
                                patch_preset_id=PRESET, first_slot=2, slot_count=2)
    mire = sof.ScannedPage(payload=payload, crop_plan=scan.crop_plan_for(payload),
                           failure="page_detection_failed")
    profil = _profil_de_gain(0.5)

    sans = sof.write_lot_output_frames(tmp_path / "sans", [reelle, mire])
    avec = sof.write_lot_output_frames(
        tmp_path / "avec", [reelle, mire], color_calibration_status="applied",
        page_profiles=((0, profil), (1, profil)))

    par_nom_sans = {frame.filename: frame for frame in sans.frames}
    for frame in avec.frames:
        chemin_avec = Path(tmp_path / "avec") / avec.output_dir / frame.filename
        chemin_sans = Path(tmp_path / "sans") / sans.output_dir / frame.filename
        if frame.synthetic:
            assert chemin_avec.read_bytes() == chemin_sans.read_bytes(), (
                f"{frame.filename}: une mire ne se corrige pas")
        else:
            assert chemin_avec.read_bytes() != chemin_sans.read_bytes(), frame.filename
        assert par_nom_sans[frame.filename].synthetic == frame.synthetic


def test_la_profondeur_du_scan_source_survit_a_la_correction(tmp_path) -> None:
    """Un scan 8 bits corrige reste declare **8 bits**, pas 16.

    La correction travaille en flottant, donc son resultat est requantifie sur 16 bits
    quelle que soit l'entree: laisser l'export deduire la profondeur du tableau qu'il
    recoit ferait declarer un scan 8 bits qui n'existe pas. Le champ dit ce que **le
    scan** portait, et c'est ce qui permettra a une correction future de savoir que seuls
    256 des 65536 niveaux sont peuples.

    Les deux profondeurs sont exercees, parce qu'un code qui declarerait toujours 8
    passerait un test qui n'en verifie qu'une.
    """
    payload = scan.make_payload(page_index=0, page_count=1, template_id=TEMPLATE,
                                patch_preset_id=PRESET, first_slot=0, slot_count=1)
    plan = scan.crop_plan_for(payload)
    frame = plan.frames[0]
    profil = _profil_de_gain(0.8)
    attendu = {np.uint8: 8, np.uint16: 16}
    for dtype, profondeur in attendu.items():
        valeur = 90 if dtype is np.uint8 else 23000
        page = sof.ScannedPage(
            payload=payload, crop_plan=plan,
            frames=(np.full((frame.height_px, frame.width_px, 3), valeur, dtype),))
        rapport = sof.write_lot_output_frames(
            tmp_path / f"depth-{profondeur}", [page],
            color_calibration_status="applied", page_profiles=((0, profil),))
        assert rapport.frames[0].source_bit_depth == profondeur, dtype
        assert rapport.frames[0].output_bit_depth == 16
        # Et le chemin **non corrige** rend la meme chose: la story n'a pas deplace la
        # lecture, elle a ajoute une valeur portee quand la lecture ne peut plus servir.
        nu = sof.write_lot_output_frames(tmp_path / f"nu-{profondeur}", [page])
        assert nu.frames[0].source_bit_depth == profondeur, dtype


# ---------------------------------------------------------------------------
# AC 4 -- le statut de lot, derive et jamais pose
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "page,disponible,corrigeables,corrigees,attendu",
    [
        (False, False, 2, 0, "not_applied"),
        (True, False, 2, 0, "failed"),
        (True, True, 2, 2, "applied"),
        (True, True, 2, 1, "applied"),
        (True, True, 2, 0, "failed"),
        (True, True, 0, 0, "not_applied"),
        # Les deux bornes du cardinal a **un**, et elles ne sont pas decoratives: un lot
        # d'une seule planche est parfaitement ordinaire, et la campagne mutmut a montre
        # que le seuil `<= 0` pouvait devenir `<= 1` sans qu'aucun cas ne le voie -- un
        # lot d'une planche corrigee se serait alors declare `not_applied`.
        (True, True, 1, 1, "applied"),
        (True, True, 1, 0, "failed"),
    ],
)
def test_le_statut_de_lot_derive_des_cas_et_de_rien_d_autre(
    page, disponible, corrigeables, corrigees, attendu,
) -> None:
    """AC 4: les trois valeurs du contrat 5.5 restent fermees, et chacune a son cas.

    Le tableau est **exhaustif sur les combinaisons atteignables** et non un echantillon:
    c'est ce qui distingue une derivation d'une suite de `if` dont un seul est exerce. Les
    deux lignes du milieu sont les plus instructives -- une planche corrigee sur deux rend
    `applied`, aucune rend `failed` -- parce qu'elles disent que le champ de lot parle de
    ce qui a **reellement** ete corrige et non de ce qui a ete tente.
    """
    assert color_pipeline.derive_lot_calibration_status(
        calibration_page_present=page,
        lot_correction_available=disponible,
        correctable_page_count=corrigeables,
        corrected_page_count=corrigees,
    ) == attendu


def test_les_trois_valeurs_rendues_sont_celles_du_contrat_ferme() -> None:
    """Aucune valeur rendue hors du vocabulaire ferme, sur tout le domaine.

    Balayage complet des combinaisons de booleens et de cardinaux 0..2: une derivation
    qui rendrait une chaine libre sur une branche oubliee ne se verrait pas autrement.
    """
    rendus = {
        color_pipeline.derive_lot_calibration_status(
            calibration_page_present=page, lot_correction_available=disponible,
            correctable_page_count=corrigeables, corrected_page_count=corrigees)
        for page in (True, False) for disponible in (True, False)
        for corrigeables in range(3) for corrigees in range(3)
    }
    assert rendus <= set(color_pipeline.CALIBRATION_STATUS_VALUES), rendus
    # Et les trois sont atteintes: un ensemble reduit a `not_applied` serait « ferme »
    # aussi, et ne dirait rien.
    assert rendus == set(color_pipeline.CALIBRATION_STATUS_VALUES), rendus


def test_le_choix_de_l_operateur_est_teste_avant_tous_les_autres_cas() -> None:
    """`EPIC5-ARB-78`: `--cc off` descend jusqu'a la fonction qui **decide** le statut.

    Le test porte sur la combinaison la plus favorable qui soit -- page presente,
    correction disponible, deux planches corrigeables et deux corrigees --, c'est-a-dire
    le seul cas qui rendrait `applied`. C'est ce qui fait la difference entre « le choix
    est pris en compte » et « le choix arrive deguise en aucune planche corrigeable »:
    la seconde forme rendrait la bonne valeur par accident sur le chemin reel, et cette
    ligne-ci la refuse.

    **Le drapeau ne peut jamais creer un `applied`, mais il ne masque plus non plus un
    `failed` reel** (deuxieme passe de revue, 2026-08-14): sur tout le domaine ou la
    correction n'a **pas** echoue (`lot_correction_available=True` ou page absente),
    refuser d'appliquer rend `not_applied`. Le domaine ou elle **a** echoue
    (`lot_correction_available=False`, page presente) est exclu de ce balayage et
    couvert separement par `test_l_echec_de_calcul_reel_n_est_jamais_masque_par_le_choix_de_l_operateur`
    ci-dessous.
    """
    commun = dict(calibration_page_present=True, lot_correction_available=True,
                  correctable_page_count=2, corrected_page_count=2)
    assert color_pipeline.derive_lot_calibration_status(**commun) == "applied"
    assert color_pipeline.derive_lot_calibration_status(
        **commun, correction_requested=False) == "not_applied"
    rendus = {
        color_pipeline.derive_lot_calibration_status(
            calibration_page_present=page, lot_correction_available=disponible,
            correctable_page_count=corrigeables, corrected_page_count=corrigees,
            correction_requested=False)
        for page in (True, False) for disponible in (True, False)
        for corrigeables in range(3) for corrigees in range(3)
        # Exclu: c'est precisement le cas ou un vrai `failed` doit rester visible malgre
        # `--cc off`, verifie a part ci-dessous.
        if not (page and not disponible)
    }
    assert rendus == {"not_applied"}, rendus


def test_l_echec_de_calcul_reel_n_est_jamais_masque_par_le_choix_de_l_operateur() -> None:
    """`EPIC5-ARB-78`, deuxieme passe de revue (2026-08-14): l'echec de calcul reel passe
    **avant** le choix de l'operateur dans l'ordre de decision.

    Avant ce correctif, `--cc off` sur un lot dont la page de calibration est illisible
    ou degeneree (`lot_correction_available=False`) rendait `not_applied` au niveau du
    lot -- masquant un vrai `failed` que chaque entree de **page** portait deja. Ce test
    epingle le contraire: sur tout le sous-domaine ou la page est presente mais la
    correction indisponible, le statut de lot reste `failed`, que l'operateur ait demande
    `--cc off` ou non.
    """
    for corrigeables in range(3):
        for corrigees in range(3):
            avec_choix = color_pipeline.derive_lot_calibration_status(
                calibration_page_present=True, lot_correction_available=False,
                correctable_page_count=corrigeables, corrected_page_count=corrigees,
                correction_requested=False)
            sans_choix = color_pipeline.derive_lot_calibration_status(
                calibration_page_present=True, lot_correction_available=False,
                correctable_page_count=corrigeables, corrected_page_count=corrigees,
                correction_requested=True)
            assert avec_choix == sans_choix == "failed", (
                corrigeables, corrigees, avec_choix, sans_choix)


def test_le_lot_corrige_se_declare_applied_de_bout_en_bout(tmp_path) -> None:
    """AC 4, par la commande reelle: le champ de projet **et** les entrees de page."""
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    project_dir, folder, payloads = lot_a_profil_designe(tmp_path)
    assert run_scan_designe(project_dir, folder) == 0
    document = manifest_of(project_dir)

    assert document["color"]["color_calibration_status"] == "applied"
    entrees = calibration_entries(document)
    # **Le lot ne porte que ses planches**: la page de calibration n'appartient a
    # aucun lot (`EPIC5-ARB-82`), donc elle n'a plus d'entree ici -- et c'est la
    # forme que l'AC 8 de 5.24 annonce, « le cardinal attendu d'un lot ne compte
    # jamais une page de calibration ».
    assert set(entrees) == {0, 1}
    assert [entrees[index]["status"] for index in (0, 1)] == ["applied", "applied"]
    # La provenance est celle du profil **designe**, et elle nomme la feuille de
    # calibration de la chaine -- jamais une planche de ce lot.
    source = source_page_id_du_profil(project_dir)
    for index in (0, 1):
        assert entrees[index]["correction_source_page_id"] == source, entrees[index]
        assert entrees[index]["correction_source_page_id"] != (
            f"{payloads[index]['lot_id']}-p{index}")


# ---------------------------------------------------------------------------
# AC 5 -- la provenance porte un identifiant, jamais une constante
# ---------------------------------------------------------------------------


def test_la_provenance_porte_l_identifiant_de_la_page_source_et_non_une_constante(
    tmp_path,
) -> None:
    """AC 5: deux lots, deux pages de calibration, **deux** identifiants de provenance.

    Un champ constant satisferait « le champ est present » et « le champ nomme une page
    de calibration »: il faut deux lots pour que « il nomme **la** page source » veuille
    dire quelque chose. C'est la meme raison qui fait qu'une fabrique de collection
    produit deux elements distinguables.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    provenances = []
    for rush, libelle in zip(("rush-aa1", "rush-bb2"), LIBELLES_DE_CHAINE):
        project_dir = tmp_path / f"projet-{rush}"
        # **Deux chaines aux libelles differents**, donc deux profils dont les
        # pages sources portent deux identifiants differents. Un champ constant
        # satisferait « le champ nomme une page de calibration »: il faut deux
        # chaines pour que « il nomme **la** page source » veuille dire quelque
        # chose -- c'est la meme raison qui fait qu'une fabrique de collection
        # produit deux elements distinguables.
        calibration = write_scan_folder(
            tmp_path / f"{rush}-calibration",
            [(page_de_calibration_autonome(scan_chain_label=libelle),
              PRESSE_CALIBRATION)])
        assert cli.main(["scan", "--project", str(project_dir), "--scan",
                         str(calibration), "--dpi", str(DPI), "calibrate"]) == 0
        payloads = lot_payloads(rush_id=rush, with_calibration=False)
        folder = write_scan_folder(tmp_path / rush, [
            (payloads[0], PRESSES_DU_TIRAGE[0]),
            (payloads[1], PRESSES_DU_TIRAGE[1])])
        assert run_scan_designe(project_dir, folder) == 0
        entrees = calibration_entries(manifest_of(project_dir))
        provenances.append(entrees[0]["correction_source_page_id"])
        assert entrees[0]["correction_source"] == cc.CORRECTION_SOURCE_CHAIN_PROFILE
        assert entrees[0]["correction_source_page_id"] == source_page_id_du_profil(
            project_dir)
        assert entrees[0]["correction_source_page_id"] != f"{payloads[0]['lot_id']}-p0"
    assert provenances[0] != provenances[1], provenances


# ---------------------------------------------------------------------------
# AC 6 et 7 -- la divergence, et son contournement, de bout en bout
# ---------------------------------------------------------------------------


def _lot_deviant(tmp_path: Path, *, name: str) -> tuple[Path, Path, list[dict]]:
    """Un lot dont **la seconde** planche derive. La premiere est nominale.

    La feuille deviante n'est pas en premiere position, et ce n'est pas un detail de
    confort: un refus qui porterait sur « la premiere planche du lot » plutot que sur la
    page mesuree passerait un test ou la deviante est premiere.
    """
    payloads = lot_payloads()
    folder = write_scan_folder(tmp_path / name, [
        (payloads[1], PRESSES_DU_TIRAGE[0]),
        (payloads[2], couleur._DEVIANT_PRESS),
        (payloads[0], PRESSE_CALIBRATION)])
    return tmp_path / f"projet-{name}", folder, payloads


def test_une_planche_deviante_est_corrigee_comme_les_autres_et_l_ecart_est_publie(
        tmp_path) -> None:
    """AC 3 de 5.23: la divergence est mesuree, publiee, et **sans consequence**.

    Ce que ce test protegeait de 5.16 et 5.19 est intact: la mesure porte **la page** et
    pas le lot (`EPIC5-ARB-57`), le voisin nominal ne diverge pas, et l'ecart chiffre
    atteint le manifest. Un verdict de lot ne survit toujours pas a cette collection.

    **AMENDE PAR LA STORY 5.23** (`EPIC5-ARB-82` decision 1), et c'est la bascule
    elle-meme: la planche deviante etait `not_applied` avec ses frames ecrites telles
    quelles, elle est desormais **corrigee**. Le nom de la fonction change avec, faute de
    quoi le fichier garderait un titre qui dit le contraire de ce qu'il verifie.

    Motif mesure, sur le lot reel `chendj-mat` le 2026-08-17: le regime que ces
    assertions figeaient faisait sortir les deux planches d'Egan non corrigees pour un
    exces de +2,13 et +2,50 dE76 contre un seuil a 1,00 -- alors que la correction refusee
    divise par 2,7 a 3,3 l'ecart au rush d'origine.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    project_dir, folder, payloads = _lot_deviant_a_profil_designe(tmp_path, name="deviant")
    assert run_scan_designe(project_dir, folder) == 0

    document = manifest_of(project_dir)
    entrees = calibration_entries(document)
    assert entrees[0]["status"] == "applied", entrees[0]
    assert entrees[1]["status"] == "applied", entrees[1]
    # **Les deux cles d'absence de correction sont absentes**, et pas seulement d'une
    # autre valeur: un lecteur qui filtre les pages en panne ou en attente le fait sur la
    # presence du champ.
    assert "failure_reason" not in entrees[1], entrees[1]
    assert "not_applied_reason" not in entrees[1], entrees[1]
    # Le domaine d'activation est verifie avant la conclusion: la planche diverge
    # **reellement**, sinon ce test confirmerait la bascule sur une planche ordinaire.
    divergence = entrees[1]["divergence"]
    assert divergence["diverges"] is True
    assert divergence["bypassed"] is False
    assert divergence["excess_residual_de76"] > divergence["threshold_de76"]
    # Le voisin nominal porte le meme bloc et n'y diverge pas: sans ce volet, « diverge »
    # ne serait confronte a rien.
    assert entrees[0]["divergence"]["diverges"] is False

    # Le lot reste exploitable: toutes ses frames sont ecrites, la deviante comprise.
    assert len(written_frames(project_dir, document)) == 8
    assert document["color"]["color_calibration_status"] == "applied"


def test_les_frames_de_la_planche_deviante_sont_corrigees_dans_les_octets(
        tmp_path) -> None:
    """AC 3 de 5.23, **sur les pixels et non sur un champ de manifest** (`EPIC5-ARB-39`).

    **AMENDE PAR LA STORY 5.23, et c'est le test qui compte le plus du fichier.** Il
    exigeait exactement l'inverse: que les frames de la planche deviante soient
    **identiques** a celles du meme lot scanne sans page de calibration -- c'est-a-dire le
    volet pixel du refus. C'est cette egalite-la qu'`EPIC5-ARB-82` supprime.

    Sa structure ne change pas d'un cran, et c'est ce qui le garde concluant: le meme lot
    est scanne deux fois, avec et sans page de calibration, et les octets sont compares
    emplacement par emplacement. Ce qui change est l'attendu -- les **huit** frames
    different desormais, la deviante comprise, la ou seules les quatre premieres le
    faisaient. Un code qui n'appliquerait la correction qu'a la planche nominale tomberait
    donc exactement comme avant, et un code qui ne l'appliquerait a personne aussi.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    project_dir, folder, payloads = _lot_deviant_a_profil_designe(tmp_path, name="pixels-deviant")
    assert run_scan_designe(project_dir, folder) == 0

    # Le temoin est le meme lot **sans profil designe**: aucun profil n'etant
    # choisi a la place de l'operateur (`EPIC5-ARB-83`), il sort brut. Meme role
    # que « le meme lot sans sa page de calibration » avant la rebase.
    nu_dir = tmp_path / "projet-pixels-nu"
    nu_folder = write_scan_folder(tmp_path / "pixels-nu", [
        (payloads[0], PRESSES_DU_TIRAGE[0]),
        (payloads[1], couleur._DEVIANT_PRESS)])
    assert run_scan(nu_dir, nu_folder) == 0

    corriges = {chemin.name: chemin
                for chemin in written_frames(project_dir, manifest_of(project_dir))}
    nus = {chemin.name: chemin for chemin in written_frames(nu_dir, manifest_of(nu_dir))}
    assert set(corriges) == set(nus)
    # Les quatre premiers emplacements sont ceux de la planche nominale (page 1), les
    # quatre suivants ceux de la deviante (page 2).
    noms = sorted(corriges)
    assert len(noms) == 8, noms
    for nom in noms[:4]:
        assert corriges[nom].read_bytes() != nus[nom].read_bytes(), (
            f"{nom}: la planche nominale doit etre corrigee")
    for nom in noms[4:]:
        assert corriges[nom].read_bytes() != nus[nom].read_bytes(), (
            f"{nom}: la planche deviante doit etre corrigee elle aussi -- c'est la "
            "bascule d'`EPIC5-ARB-82`, et elle se verifie dans les octets")
    # Temoin negatif indispensable: la planche deviante **diverge**, sinon les huit
    # egalites ci-dessus seraient tenues par un lot ou rien ne diverge, donc par rien.
    assert calibration_entries(manifest_of(project_dir))[1]["divergence"]["diverges"] \
        is True


def test_le_contournement_applique_la_correction_du_lot_telle_quelle(tmp_path) -> None:
    """AC 7: le contournement fait appliquer, il ne **re-ajuste** rien.

    La preuve que rien n'est re-ajuste est portee par la provenance: la page contournee
    declare la meme forme de correction et la **meme page source** que la page de
    calibration, et non elle-meme. Un re-ajustement local aurait pose `own_sheet_patches`
    et l'identifiant de la page elle-meme -- c'est le seul endroit du document ou les deux
    regimes se distinguent.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    project_dir, folder, payloads = _lot_deviant_a_profil_designe(tmp_path, name="contourne")
    assert run_scan_designe(project_dir, folder,
                    cc.DIVERGENCE_BYPASS_FLAG) == 0

    entrees = calibration_entries(manifest_of(project_dir))
    contournee = entrees[1]
    assert contournee["status"] == "applied", contournee
    assert contournee["divergence"]["bypassed"] is True
    assert contournee["divergence"]["diverges"] is True
    # **La source est le profil de chaine**, pas une page du lot: c'est la
    # traduction exacte de la propriete d'origine dans le regime de profil
    # designe (`EPIC5-ARB-83`). Un re-ajustement local aurait pose
    # `own_sheet_patches` -- le vocabulaire les separe toujours.
    assert contournee["correction_source"] == cc.CORRECTION_SOURCE_CHAIN_PROFILE
    assert contournee["correction_source"] != cc.CORRECTION_SOURCE_OWN_SHEET
    # La page source est celle du profil **designe** (`EPIC5-ARB-83`), relue au
    # profil ecrit -- jamais la planche elle-meme, ce qui est tout l'enjeu: un
    # re-ajustement local aurait pose l'identifiant de la page contournee.
    assert contournee["correction_source_page_id"] == source_page_id_du_profil(
        project_dir)
    assert contournee["correction_source_page_id"] != f"{payloads[1]['lot_id']}-p1"
    assert contournee["correction_form_id"] == entrees[0]["correction_form_id"]
    # **Chemin de production complet, forme active** (AC 2 de la story 5.21): ce que le
    # manifest porte ici est ce que la commande `scan` a reellement ajuste, sans qu'aucun
    # appelant ne nomme de forme. L'attendu suit donc le defaut, et le second volet
    # verifie que la bascule mord: avant 5.21 cette meme ligne rendait la forme affine.
    assert contournee["correction_form_id"] == cc.ACTIVE_CORRECTION_FORM_ID
    assert contournee["correction_form_id"] != cc.CORRECTION_FORM_ID


def test_la_page_contournee_recoit_exactement_le_profil_du_lot(tmp_path,
                                                               monkeypatch) -> None:
    """« Les memes parametres que la page de calibration », mesure sur le profil lui-meme.

    L'egalite porte sur les **coefficients**, pas sur un identifiant de forme: deux
    profils de la meme forme et de coefficients differents porteraient le meme
    `correction_form_id`, donc l'assertion du test precedent serait tenue par un
    re-ajustement local. C'est le second bout de l'AC 7, et sans lui elle est declarative.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    calibrations = _Compteur(monkeypatch, "calibrate_page")
    project_dir, folder, _ = _lot_deviant_a_profil_designe(tmp_path, name="profil-contourne")
    assert run_scan_designe(project_dir, folder, cc.DIVERGENCE_BYPASS_FLAG) == 0

    profils = [appel["imported_profile"] for appel in calibrations.appels]
    assert len(profils) == 2 and all(profil is not None for profil in profils)
    reference, contournee = profils
    # **La comparaison est faite champ par champ et non sur des noms de champs figes**
    # (story 5.21): les deux etages de la forme affine s'appelaient `stage_a` et
    # `stage_m`, ceux de la forme active s'appellent autrement, et une comparaison qui
    # nomme les champs d'une forme cesse de compiler des que le defaut bascule -- sans
    # rien dire de faux sur la forme nouvelle. Ce que l'AC 7 demande est « les memes
    # parametres », quelle que soit la liste de ces parametres.
    champs = [champ.name for champ in dataclasses.fields(reference)]
    assert champs, "le profil de lot n'est pas une dataclasse: la comparaison serait vide"
    assert len(champs) >= 3, (
        "moins de trois parametres compares: une forme reduite a son seul identifiant "
        "rendrait ce test vrai sans rien verifier")
    for nom in champs:
        gauche = getattr(reference, nom)
        droite = getattr(contournee, nom)
        if isinstance(gauche, np.ndarray):
            assert np.array_equal(gauche, droite), nom
        else:
            assert gauche == droite, nom
    assert reference.correction_id == cc.ACTIVE_CORRECTION_FORM_ID


def test_un_contournement_non_demande_ne_peut_pas_etre_inscrit(tmp_path) -> None:
    """Temoin symetrique: sans le drapeau, la page deviante n'est **pas** contournee.

    Sans ce volet, « le contournement est explicite » serait tenu par un code qui
    contourne toujours. La garde de coherence de 5.7 ferme l'autre cote -- un
    contournement constate sans demande est refuse au manifest --, et c'est ici qu'on
    verifie que le chemin nominal ne le produit jamais.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    project_dir, folder, _ = _lot_deviant_a_profil_designe(tmp_path, name="sans-drapeau")
    assert run_scan_designe(project_dir, folder) == 0
    entrees = calibration_entries(manifest_of(project_dir))
    assert entrees[1]["divergence"]["bypassed"] is False
    # **AMENDE PAR LA STORY 5.23**: sans le drapeau la planche n'est plus livree en brut,
    # elle est corrigee comme les autres (`EPIC5-ARB-82` decision 1). Ce que ce test
    # verifie est intact et c'est la seule chose qu'il ait jamais verifiee: le
    # contournement n'est **jamais** marque tout seul. Le domaine d'activation est
    # conserve par la ligne suivante -- la planche diverge, donc `bypassed` avait
    # quelque chose a marquer.
    assert entrees[1]["divergence"]["diverges"] is True
    assert entrees[1]["status"] == "applied"
    assert "not_applied_reason" not in entrees[1]


# ---------------------------------------------------------------------------
# AC 8 et 9 -- les deux cas limites, et le fait qu'ils ne se confondent pas
# ---------------------------------------------------------------------------


def test_un_lot_sans_page_de_calibration_reste_exploitable_et_le_declare(
    tmp_path,
) -> None:
    """AC 8. Refuser le lot ferait perdre les autres feuilles pour **une** qui manque.

    Le motif n'est plus la v1 -- `EPIC5-ARB-66` l'a declaree obsolete --, c'est le
    principe de refus **par page** d'`EPIC5-ARB-57`: une page de calibration peut manquer
    au scan d'un lot v2 parfaitement compose, feuille perdue ou mal empilee.

    L'absence est **declaree** (la page sort dans `missing_pages`) et aucun avertissement
    ne suggere une divergence: les deux cas se traitent de facon opposee, donc les
    confondre enverrait rescanner la mauvaise feuille.
    """
    payloads = lot_payloads()
    folder = write_scan_folder(tmp_path / "sans-calib", [
        (payloads[1], PRESSES_DU_TIRAGE[0]), (payloads[2], PRESSES_DU_TIRAGE[1])])
    project_dir = tmp_path / "projet-sans-calib"

    assert run_scan(project_dir, folder) == LOT_INCOMPLET_MAIS_ECRIT

    document = manifest_of(project_dir)
    assert document["color"]["color_calibration_status"] == "not_applied"
    assert len(written_frames(project_dir, document)) == 8
    entrees = calibration_entries(document)
    assert set(entrees) == {1, 2}
    for entree in entrees.values():
        # Aucun regime nouveau ne s'obtient sans le demander: les entrees rendent les
        # deux memes cles qu'avant la story.
        assert set(entree) == {"page_index", "status"}, entree
        assert entree["status"] == "not_applied"


def _lot_calibration_illisible(tmp_path: Path, *, name: str):
    """Un lot dont la page de calibration ne porte **aucune** pastille.

    C'est le cas de l'AC 9 construit sans truquer le code: la feuille est bien la, son QR
    se lit, sa geometrie se resout -- et son treillis est illisible. Une page blanche
    donne des mesures toutes egales, donc un jeu d'ajustement sous-determine: la
    correction du lot n'existe pas.
    """
    payloads = lot_payloads()
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    for rank, (payload, press) in enumerate(
            [(payloads[1], PRESSES_DU_TIRAGE[0]), (payloads[2], PRESSES_DU_TIRAGE[1])],
            start=1):
        cv2.imwrite(str(folder / f"page_{rank:02d}.tiff"),
                    build_page(payload, press=press))
    cv2.imwrite(str(folder / "page_03.tiff"),
                build_page(payloads[0], press=PRESSE_CALIBRATION, patches=()))
    return tmp_path / f"projet-{name}", folder, payloads


def test_une_feuille_de_calibration_illisible_n_est_pas_le_sort_du_lot(
    tmp_path,
) -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 4) -- **le lot n'herite plus**.

    L'assertion morte etait « le lot rend `failed` » : elle disait a l'operateur
    qu'une correction avait ete tentee **sur ce lot**, alors que la feuille en cause
    n'appartient a aucun lot depuis `EPIC5-ARB-82`. Ce qui survit est la
    distinction qui comptait -- un echec motive n'est pas une absence --, et elle
    vit desormais dans le **reliquat**, ou l'operateur va voir ce qui a resiste.

    La feuille est bien la, son QR se lit, sa geometrie se resout -- et son treillis
    est illisible (page blanche : mesures toutes egales, ajustement
    sous-determine).
    """
    payloads = lot_payloads(sheet_count=2, with_calibration=False)
    folder = tmp_path / "illisible"
    folder.mkdir(parents=True, exist_ok=True)
    for rang, (payload, press) in enumerate(
            [(payloads[0], PRESSES_DU_TIRAGE[0]), (payloads[1], PRESSES_DU_TIRAGE[1])],
            start=1):
        cv2.imwrite(str(folder / f"page_{rang:02d}.tiff"),
                    build_page(payload, press=press))
    cv2.imwrite(str(folder / "page_03.tiff"),
                build_page(page_de_calibration_autonome(
                    scan_chain_label=LIBELLES_DE_CHAINE[0]),
                    press=PRESSE_CALIBRATION, patches=()))
    project_dir = tmp_path / "projet-illisible"

    assert run_scan(project_dir, folder) == 0

    document = manifest_of(project_dir)
    assert len(written_frames(project_dir, document)) == 8
    # Les deux planches sont intactes et rien n'a ete mesure sur elles: elles ne
    # portent pas l'echec d'une autre feuille (`EPIC5-ARB-69`, dans son sens
    # symetrique).
    entrees = calibration_entries(document)
    assert set(entrees) == {0, 1}, entrees
    for index in (0, 1):
        assert entrees[index]["status"] == "not_applied", entrees[index]
    lot = next(entry for entry in document["lots"]
               if entry["lot_id"] == payloads[0]["lot_id"])
    assert "color_calibration_status" not in lot, lot
    assert encode_module.calibration_summary_line(lot).startswith("not_applied")
    # Le motif, lui, n'est pas perdu: il est au **reliquat**, nomme.
    rapport = json.loads(
        (project_dir / project_layout.SCANS_DIRNAME / "illisible" / cli.TRI_DOCUMENT_FILENAME).read_text(
            encoding="utf-8"))
    assert [entree["motif"] for entree in rapport["reliquat"]] == [
        scan_sorting.RELIQUAT_CALIBRATION_INEXPLOITABLE], rapport["reliquat"]
    assert rapport["profils_crees"] == []


def _planche_a_geometrie_perdue(payload, *, press, dpi: int = DPI) -> np.ndarray:
    """Une **planche d'images** dont un marqueur de coin est efface: geometrie perdue.

    Distincte de la fabrique de page de calibration ci-dessous parce que les deux regimes
    ne se confondent pas: ici c'est le contenu source qui est perdu, la ou la correction du
    lot reste ajustable.
    """
    page = build_page(payload, press=press, dpi=dpi)
    spec = page_templates.get_template(payload["template_id"])
    marker_px = int(round(layout.MARKER_SIZE_MM / 25.4 * dpi))
    x_mm, y_mm = next(iter(page_templates.corner_marker_centers_mm(spec).values()))
    centre_x, centre_y = page_templates.mm_to_px(x_mm, y_mm, dpi)
    left, top = centre_x - marker_px // 2, centre_y - marker_px // 2
    page[top:top + marker_px, left:left + marker_px] = 255
    return page


def test_une_passe_qui_n_ecrit_aucune_frame_ne_touche_pas_le_statut_du_lot(
    tmp_path,
) -> None:
    """Finding `F1` de la revue de la passe de correction: le champ decrit le **disque**.

    Le regime est banal -- une pile mal posee, toutes les planches cornees -- et il est
    exactement celui ou aucune mire n'est *formable*: aucune frame reelle ne donne sa forme
    aux mires, donc zero fichier est ecrit et les frames de la passe precedente restent
    intactes. Le champ redescendait pourtant a `not_applied`, et le recapitulatif d'`encode`
    disait alors trois faussetes en une ligne, dont « le lot ne porte pas de page de
    calibration lue » d'une feuille qui etait la, lisible, et sur les pastilles de laquelle
    la correction venait d'etre ajustee -- le dommage meme qu'`EPIC5-ARB-70` ferme.

    Les octets sont la mesure: si les huit fichiers n'ont pas bouge, aucune declaration sur
    les pixels n'a le droit de bouger.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    project_dir, folder, payloads = lot_a_profil_designe(tmp_path, name="sans-ecriture")
    assert run_scan_designe(project_dir, folder) == 0
    avant = {chemin.name: chemin.read_bytes()
             for chemin in written_frames(project_dir, manifest_of(project_dir))}
    assert len(avant) == 8

    # Passe 2: **les deux planches** cornees, la page de calibration intacte.
    cornees = tmp_path / "sans-ecriture-cornees"
    cornees.mkdir()
    for rang, (payload, press) in enumerate(
            [(payloads[0], PRESSES_DU_TIRAGE[0]), (payloads[1], PRESSES_DU_TIRAGE[1])],
            start=1):
        cv2.imwrite(str(cornees / f"page_{rang:02d}.tiff"),
                    _planche_a_geometrie_perdue(payload, press=press))
    # **Plus de page de calibration dans la pile**: la correction du lot vient du
    # profil designe, et c'est ce qui rend ce regime atteignable sans elle.

    assert run_scan_designe(project_dir, cornees, "--overwrite") == 0
    document = manifest_of(project_dir)
    apres = {chemin.name: chemin.read_bytes()
             for chemin in written_frames(project_dir, document)}
    assert apres == avant, (
        "le montage doit laisser les frames intactes, sinon il ne mesure pas ce regime")

    lot = next(entry for entry in document["lots"]
               if entry["lot_id"] == payloads[0]["lot_id"])
    assert lot["color_calibration_status"] == "applied", (
        "les pixels du disque sont ceux de la passe 1, corriges: le champ ne descend pas")
    assert encode_module.calibration_summary_line(lot).startswith("applied")


def test_la_branche_sans_planche_corrigeable_est_atteinte_en_production(tmp_path) -> None:
    """Finding `F2`: le domaine de `correctable_page_count <= 0` n'est **pas** vide.

    Deux chemins y menent et un seul avait ete mesure. Celui-ci -- page de calibration
    intacte, **toutes** les planches en echec de geometrie -- sort en code 0 avec son
    manifest: `page_calibrations` est vide puisqu'une planche en echec ne passe jamais par
    `calibrate_page`, et la correction du lot est pourtant disponible.

    La branche n'est donc pas du code mort: la supprimer ferait tomber ce regime dans
    `corrected_page_count <= 0`, c'est-a-dire dans `failed` -- « une correction a echoue »
    la ou il n'y avait aucune frame a corriger.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    payloads = lot_payloads(sheet_count=2, with_calibration=False)
    project_dir = tmp_path / "projet-sans-corrigeable"
    # La correction du lot est **disponible** -- elle vient du profil designe --
    # et **toutes** les planches sont en echec de geometrie: c'est exactement le
    # regime que la branche existe pour porter.
    consigner_le_profil_de_la_chaine(project_dir, tmp_path, name="sans-corrigeable")
    folder = tmp_path / "sans-corrigeable"
    folder.mkdir()
    for rang, (payload, press) in enumerate(
            [(payloads[0], PRESSES_DU_TIRAGE[0]), (payloads[1], PRESSES_DU_TIRAGE[1])],
            start=1):
        cv2.imwrite(str(folder / f"page_{rang:02d}.tiff"),
                    _planche_a_geometrie_perdue(payload, press=press))

    assert run_scan_designe(project_dir, folder) == LOT_INCOMPLET_MAIS_ECRIT
    document = manifest_of(project_dir)
    assert document["color"]["color_calibration_status"] == "not_applied"
    # Aucune frame ecrite, donc le lot ne declare rien: les deux findings se rejoignent ici.
    lot = next(entry for entry in document["lots"]
               if entry["lot_id"] == payloads[0]["lot_id"])
    assert "color_calibration_status" not in lot, lot
    # Et la valeur derivee est bien celle de la branche, non celle de `failed`.
    assert color_pipeline.derive_lot_calibration_status(
        calibration_page_present=True, lot_correction_available=True,
        correctable_page_count=0, corrected_page_count=0) == "not_applied"


def _page_de_calibration_a_geometrie_perdue(payload, *, dpi: int = DPI) -> np.ndarray:
    """La page de calibration **presente**, QR intact, un marqueur de coin efface.

    C'est la panne de terrain la plus banale -- feuille cornee, marqueur macule -- et elle
    se construit sans truquer le code: le raster est celui du vrai gabarit, on blanchit un
    seul des quatre marqueurs. Le QR reste lisible, donc le lot **sait** que cette feuille
    est sa page de calibration; c'est l'homographie qui ne se resout plus.
    """
    page = build_page(payload, press=PRESSE_CALIBRATION, dpi=dpi)
    spec = page_templates.get_template(payload["template_id"])
    marker_px = int(round(layout.MARKER_SIZE_MM / 25.4 * dpi))
    x_mm, y_mm = next(iter(page_templates.corner_marker_centers_mm(spec).values()))
    centre_x, centre_y = page_templates.mm_to_px(x_mm, y_mm, dpi)
    left, top = centre_x - marker_px // 2, centre_y - marker_px // 2
    page[top:top + marker_px, left:left + marker_px] = 255
    return page


def test_une_feuille_de_calibration_non_redressable_est_un_reliquat_motive(
    tmp_path,
) -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 4 et AC 7) -- reliquat motive, lots intacts.

    `EPIC5-ARB-70` a tranche que cette feuille est **perdue** et non absente, et que
    le document doit le dire. L'assertion morte etait l'endroit ou il le disait --
    l'entree de page **du lot**. Depuis `EPIC5-ARB-82` elle n'appartient a aucun
    lot ; le motif vit donc au reliquat, et les planches intactes n'en portent pas
    la faute.

    La panne est celle du terrain -- feuille cornee, marqueur macule -- et elle se
    construit sans truquer le code : le QR reste lisible, donc la passe **sait**
    que cette feuille est une page de calibration ; c'est l'homographie qui ne se
    resout plus.
    """
    payloads = lot_payloads(sheet_count=2, with_calibration=False)
    folder = write_scan_folder(tmp_path / "perdue", [
        (payloads[0], PRESSES_DU_TIRAGE[0]), (payloads[1], PRESSES_DU_TIRAGE[1])])
    cv2.imwrite(str(folder / "page_03.tiff"),
                _page_de_calibration_a_geometrie_perdue(
                    page_de_calibration_autonome(
                        scan_chain_label=LIBELLES_DE_CHAINE[1])))
    project_dir = tmp_path / "projet-perdue"

    assert run_scan(project_dir, folder) == 0, (
        "une page de calibration perdue ne fait pas perdre les planches de la passe")

    document = manifest_of(project_dir)
    assert len(written_frames(project_dir, document)) == 8
    lot = next(entry for entry in document["lots"]
               if entry["lot_id"] == payloads[0]["lot_id"])
    assert "color_calibration_status" not in lot, lot
    rapport = json.loads(
        (project_dir / project_layout.SCANS_DIRNAME / "perdue" / cli.TRI_DOCUMENT_FILENAME).read_text(
            encoding="utf-8"))
    assert [entree["motif"] for entree in rapport["reliquat"]] == [
        scan_sorting.RELIQUAT_CALIBRATION_INEXPLOITABLE], rapport["reliquat"]
    assert rapport["profils_crees"] == []
    # Les deux planches sont intactes: rien n'a ete mesure sur elles.
    entrees = calibration_entries(document)
    for index in (0, 1):
        assert entrees[index]["status"] == "not_applied", entrees[index]


# **Motif corrige le 2026-08-19, apres mesure** (voir le journal de la story 5.23): la
# situation ecrite ici decrivait `REFUS_PILE_MIXTE`, comme ses 23 voisines de ce fichier.
# C'est faux pour ce test-ci, et pour une raison qui lui est propre: son QR de page de
# calibration est **efface**, donc la feuille ne decode pas, donc la pile qui atteint la
# reconstruction ne porte que des planches. Un motif faux est plus dangereux qu'un motif
# absent -- c'est lui qu'on relira pour decider quoi reactiver.
def test_un_qr_illisible_reste_une_absence_visible_et_non_un_echec(tmp_path) -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 4) -- **le cas exact de la zone tampon**.

    `EPIC5-ARB-70` tranche **par ce que le code peut savoir** : sans payload, rien
    ne dit que la feuille etait une page de calibration, donc la declarer en echec
    serait inventer une information. Ce qui change avec le tri, c'est qu'elle ne
    disparait plus : elle va au **reliquat** sous le motif « QR absent ou illisible
    », qui est distinct de celui d'une feuille de calibration inexploitable. Une
    absence **visible**, jamais un echec de passe.

    Sans ce volet, une garde qui rendrait « inexploitable » pour **toute** page
    muette passerait le test precedent -- exactement la forme « une garde annoncee
    sans son domaine d'activation », huit fois payee par ce depot.
    """
    payloads = lot_payloads(sheet_count=2, with_calibration=False)
    folder = write_scan_folder(tmp_path / "sans-qr", [
        (payloads[0], PRESSES_DU_TIRAGE[0]), (payloads[1], PRESSES_DU_TIRAGE[1])])
    # Meme feuille que ci-dessus, mais le QR est efface **en plus** du marqueur: le
    # role devient inconnaissable.
    autonome = page_de_calibration_autonome(scan_chain_label=LIBELLES_DE_CHAINE[0])
    page = _page_de_calibration_a_geometrie_perdue(autonome)
    page_layout = patch_presets.resolve_page_layout(
        autonome["template_id"], autonome["page_role"])
    zone = next(z for z in page_layout.reserved_zones_mm if z["name"] == "qr_zone")
    side = int(round(qr_codes.QR_PRINT_SIZE_TARGET_MM / 25.4 * DPI))
    qr_x, qr_y = page_templates.mm_to_px(zone["x"], zone["y"], DPI)
    page[qr_y:qr_y + side, qr_x:qr_x + side] = 255
    cv2.imwrite(str(folder / "page_03.tiff"), page)
    project_dir = tmp_path / "projet-sans-qr"

    assert run_scan(project_dir, folder) == 0

    document = manifest_of(project_dir)
    lot = next(entry for entry in document["lots"]
               if entry["lot_id"] == payloads[0]["lot_id"])
    # Le lot ne porte **aucun** statut: c'est le chemin non corrige, inchange, et
    # son absence se lit `not_applied` (`EPIC5-ARB-68`).
    assert "color_calibration_status" not in lot, lot
    assert document["color"]["color_calibration_status"] == "not_applied"
    # **Et elle ne disparait pas**: elle est nommee au reliquat, sous le motif du
    # QR muet -- distinct de celui d'une feuille de calibration inexploitable.
    rapport = json.loads(
        (project_dir / project_layout.SCANS_DIRNAME / "sans-qr" / cli.TRI_DOCUMENT_FILENAME).read_text(
            encoding="utf-8"))
    assert len(rapport["reliquat"]) == 1, rapport["reliquat"]
    entree = rapport["reliquat"][0]
    assert entree["motif"] in {scan_sorting.RELIQUAT_QR_MUET,
                               scan_sorting.RELIQUAT_PAYLOAD_REFUSE}
    assert entree["motif"] != scan_sorting.RELIQUAT_CALIBRATION_INEXPLOITABLE
    assert entree["locator"]["source_path"].endswith("page_03.tiff")


def test_les_deux_motifs_ne_se_confondent_pas(tmp_path) -> None:
    """AC 9, le coeur: **illisible** et **deviante** sont deux mots differents.

    L'un rend la correction du lot impossible -- aucun profil, tout le lot --, l'autre
    concerne une page et laisse les autres corrigees. Le test asserte les deux chaines et
    leur **disjonction**: le motif de la page de calibration ne parle pas de divergence,
    et celui de la planche deviante en parle.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    spec = page_templates.get_template(TEMPLATE)
    width_px, height_px = page_templates.page_size_px(spec, DPI)
    blanche = np.full((height_px, width_px, 3), 255, np.uint8)
    illisible = cc.fit_lot_correction_from_page(
        blanche, template_id=TEMPLATE, dpi=DPI, source_page_id="lot-x-p0")

    assert not illisible.available
    assert illisible.profile is None
    assert illisible.failure_reason != cc.FAILURE_PAGE_DIVERGES
    # RESSERRE PAR LA REVUE DE VAGUE (couche 3, AC 8 ligne « a resserrer en meme temps
    # que la reactivation »). L'assertion acceptait SIX motifs ; sur cette fixture exacte
    # -- page blanche, `tpl-a4-portrait-4f-v2`, 600 dpi -- `fit_lot_correction_from_page`
    # n'en rend qu'UN, et les cinq autres sont inatteignables. Mesure : la couche 3 a
    # remplace le motif au site de production par `FAILURE_DISTORTION_BUDGET` et **ce
    # test restait vert** -- il ne mesurait donc pas quel motif est rendu, alors que
    # c'est litteralement son sujet.
    #
    # Le commentaire d'origine justifiait la largeur de l'ensemble en affirmant que
    # `correction_distortion_exceeds_budget` « rejoint la liste avec la story 5.20 ».
    # C'est **faux tel que mesure** : la garde de conditionnement d'`EPIC5-ARB-78` mord
    # plus tot et rend `adjustment_set_underdetermined`. Une tolerance justifiee par un
    # fait qui n'a pas lieu.
    #
    # Deux assertions, et il faut les deux : l'egalite mesure QUEL motif est rendu,
    # l'appartenance mesure la propriete que l'AC 9 demande (le motif vit dans le
    # vocabulaire ferme du lot, et aucun de ses mots ne parle de divergence).
    assert illisible.failure_reason == cc.FAILURE_UNDERDETERMINED_ADJUSTMENT
    assert illisible.failure_reason in {
        cc.FAILURE_UNDERDETERMINED_ADJUSTMENT, cc.FAILURE_PATCHES_NOT_FOUND,
        cc.FAILURE_PATCHES_OUT_OF_RANGE, cc.FAILURE_METRIC,
        cc.FAILURE_DEGRADES_RESIDUAL, cc.FAILURE_DISTORTION_BUDGET}
    assert "diverg" not in illisible.failure_message.lower(), illisible.failure_message
    assert "lot-x-p0" in illisible.failure_message
    # Le geste demande est celui du **lot**, pas d'une feuille: c'est ce qui distingue les
    # deux messages a la lecture.
    assert "page de calibration" in illisible.failure_message.lower()

    # Et le message symetrique, lui, **parle** de divergence: sans ce volet, l'assertion
    # ci-dessus serait tenue par un code qui ne dit jamais le mot nulle part.
    project_dir, folder, _ = _lot_deviant_a_profil_designe(tmp_path, name="motifs")
    assert run_scan_designe(project_dir, folder) == 0
    entrees = calibration_entries(manifest_of(project_dir))
    # **Le contraste entre les deux familles est a son maximum depuis la story 5.23**: une
    # page de calibration illisible reste un `failed` motive (ci-dessus), tandis qu'une
    # planche deviante est desormais `applied` -- deux statuts opposes, en plus de deux
    # vocabulaires disjoints. Les confondre, ce qui est le fond de l'AC 9, n'est plus
    # possible sans se tromper deux fois dans deux directions contraires.
    assert entrees[1]["status"] == "applied"
    assert "not_applied_reason" not in entrees[1]
    assert entrees[1]["divergence"]["diverges"] is True
    # Et le mot « diverg » vit toujours quelque part dans le document: sans ce volet,
    # l'assertion negative du haut serait tenue par un code qui ne le dit nulle part.
    assert "divergence" in entrees[1]


@pytest.mark.parametrize("dpi", [0, -1, 600.0, True])
def test_un_dpi_absurde_refuse_l_ajustement_du_lot_au_lieu_de_mesurer_faux(dpi) -> None:
    """Le dpi gouverne toutes les conversions en millimetres: faux, toute mesure l'est.

    Les quatre valeurs couvrent les quatre facons d'etre invalide, `True` compris: un
    booleen **est** un entier en Python, et il valait 1 ppp sans que rien ne sonne.
    """
    spec = page_templates.get_template(TEMPLATE)
    width_px, height_px = page_templates.page_size_px(spec, DPI)
    page = np.full((height_px, width_px, 3), 255, np.uint8)
    resultat = cc.fit_lot_correction_from_page(
        page, template_id=TEMPLATE, dpi=dpi, source_page_id="lot-x-p0")
    assert resultat.failure_reason == cc.FAILURE_INVALID_DPI
    assert resultat.profile is None


def test_un_gabarit_sans_page_de_calibration_est_un_echec_motive() -> None:
    """Un gabarit v1 ne peut pas porter de page de calibration: on le **dit**.

    Le refus est celui du registre de placements, pas une exception nue remontant dans la
    CLI: il porte le vocabulaire ferme de l'AC 8 de 5.4b comme tous les autres motifs.
    """
    resultat = cc.fit_lot_correction_from_page(
        np.full((100, 100, 3), 255, np.uint8), template_id="tpl-a4-portrait-2f-v1",
        dpi=DPI, source_page_id="lot-v1-p0")
    assert resultat.failure_reason == cc.FAILURE_PLACEMENT_UNDEFINED
    assert resultat.profile is None


def test_une_forme_de_correction_inconnue_leve_au_lieu_de_replier() -> None:
    """L'identifiant est ici un argument de l'appelant, donc une faute de programmation.

    Asymetrie deliberee avec le regime transporte de `calibrate_page`, ou l'identifiant
    vient du profil importe -- donc d'une **donnee** -- et rend un motif ferme. Un repli
    sur la forme active rendrait le manifest menteur sur ce qui a ete applique.
    """
    with pytest.raises(cc.UnknownCorrectionFormError):
        cc.fit_lot_correction_from_page(
            np.full((100, 100, 3), 255, np.uint8), template_id=TEMPLATE, dpi=DPI,
            source_page_id="lot-x-p0", correction_form_id="forme-inventee-1")


# ---------------------------------------------------------------------------
# Appariement page -> profil: la classe de defaut M33 / M25
# ---------------------------------------------------------------------------


def test_un_profil_pour_une_page_absente_du_lot_est_refuse(tmp_path) -> None:
    """Un profil mal apparie corrigerait une feuille avec la correction d'une autre.

    Le resultat serait **plausible** -- une image corrigee, juste pas avec la bonne
    correction --, donc invisible a toute relecture. La cible est placee ailleurs qu'en
    premiere position: deux pages declarees, un profil pour une troisieme.
    """
    premiere = _page_de_planche((40, 90, 200), slot_count=2, page_count=2)
    payload = scan.make_payload(page_index=1, page_count=2, template_id=TEMPLATE,
                                patch_preset_id=PRESET, first_slot=2, slot_count=2)
    plan = scan.crop_plan_for(payload)
    seconde = sof.ScannedPage(
        payload=payload, crop_plan=plan,
        frames=tuple(np.full((frame.height_px, frame.width_px, 3), 20000, np.uint16)
                     for frame in plan.frames))
    profil = _profil_de_gain(0.5)

    with pytest.raises(sof.ScanOutputError, match="absente du lot"):
        sof.write_lot_output_frames(
            tmp_path / "mal-apparie", [premiere, seconde],
            color_calibration_status="applied",
            page_profiles=((1, profil), (7, profil)))
    assert not (tmp_path / "mal-apparie" / project_layout.SCAN_FRAMES_DIRNAME).exists()


def test_deux_profils_pour_la_meme_page_sont_refuses(tmp_path) -> None:
    """Une page a **une** correction: en accepter deux laisse l'ordre de lecture decider."""
    page = _page_de_planche((40, 90, 200))
    with pytest.raises(sof.ScanOutputError, match="meme page_index"):
        sof.write_lot_output_frames(
            tmp_path / "double", [page], color_calibration_status="applied",
            page_profiles=((0, _profil_de_gain(0.5)), (0, _profil_de_gain(0.8))))


def test_un_objet_sans_apply_linear_est_refuse_avant_la_premiere_ecriture(
    tmp_path,
) -> None:
    """Decouvert en planification, pas a mi-dossier: un refus tardif laisse des fichiers."""
    page = _page_de_planche((40, 90, 200), slot_count=2)
    with pytest.raises(sof.ScanOutputError, match="apply_linear"):
        sof.write_lot_output_frames(
            tmp_path / "sans-profil", [page], color_calibration_status="applied",
            page_profiles=((0, object()),))
    assert not (tmp_path / "sans-profil" / project_layout.SCAN_FRAMES_DIRNAME).exists()


def test_deux_pages_recoivent_deux_profils_differents_et_pas_le_meme(tmp_path) -> None:
    """Regle des fabriques: deux pages, deux profils **distinguables**, et la permutation
    se voit.

    Un remplissage uniforme -- deux pages au meme profil -- rendrait invisible un
    appariement inverse, qui est litteralement le mutant `M33` de ce depot. Les deux
    profils ont des gains opposes autour de 1, donc echanger les deux echange le sens de
    l'ecart sur chaque page.
    """
    premiere = _page_de_planche((100, 100, 100), slot_count=1, page_count=2)
    payload = scan.make_payload(page_index=1, page_count=2, template_id=TEMPLATE,
                                patch_preset_id=PRESET, first_slot=1, slot_count=1)
    plan = scan.crop_plan_for(payload)
    seconde = sof.ScannedPage(
        payload=payload, crop_plan=plan,
        frames=(np.full((plan.frames[0].height_px, plan.frames[0].width_px, 3),
                        100 * 257, np.uint16),))

    rapport = sof.write_lot_output_frames(
        tmp_path / "apparie", [premiere, seconde], color_calibration_status="applied",
        page_profiles=((0, _profil_de_gain(0.5)), (1, _profil_de_gain(1.6))))
    par_page = {frame.page_index: frame for frame in rapport.frames}
    assert set(par_page) == {0, 1}
    dossier = Path(tmp_path / "apparie") / rapport.output_dir
    sombre = _frame_centre(dossier / par_page[0].filename)
    clair = _frame_centre(dossier / par_page[1].filename)
    # La page 0 recoit le gain qui assombrit, la page 1 celui qui eclaircit. Une
    # permutation inverse strictement les deux inegalites.
    assert (sombre < 100 / 255.0).all(), sombre
    assert (clair > 100 / 255.0).all(), clair


# ---------------------------------------------------------------------------
# AC 12 -- non-regression du chemin **non corrige**
# ---------------------------------------------------------------------------


def test_le_chemin_non_corrige_rend_le_meme_document_qu_avant_la_story(
    tmp_path,
) -> None:
    """AC 12: octet a octet, sur le rapport de 5.6 **et** sur le manifest.

    Le filet ne protege pas une version -- `EPIC5-ARB-66` a declare la v1 obsolete --, il
    protege le **chemin non corrige**, qui reste celui de tout lot dont la page de
    calibration manque (AC 8) ou est illisible (AC 9). Le lot exerce est donc un lot
    **v2** sans page de calibration.

    La forme falsifiable retenue: les deux nouveaux parametres, passes a leur valeur
    d'absence, rendent le **meme texte** que lorsqu'ils ne sont pas passes du tout. C'est
    l'additivite, et elle se mesure sur la serialisation canonique, pas sur un dictionnaire
    compare champ par champ -- un champ ajoute a `None` echapperait au second.
    """
    payloads = lot_payloads(with_calibration=False, sheet_count=2)
    pages = [scan.scanned_page(payload) for payload in payloads]

    ancien = sof.write_lot_output_frames(tmp_path / "ancien", pages)
    nouveau = sof.write_lot_output_frames(
        tmp_path / "nouveau", pages, page_profiles=(),
        color_calibration_status=color_pipeline.NOT_APPLIED_STATUS)
    assert sof.report_json(ancien) == sof.report_json(nouveau)

    avant = sm.build_scan_manifest(None, sm.ScanRecord(
        page_payloads=tuple(payloads), output_report=ancien, scan_dpi=DPI,
        ingest_slug="lot"))
    apres = sm.build_scan_manifest(None, sm.ScanRecord(
        page_payloads=tuple(payloads), output_report=nouveau, scan_dpi=DPI,
        ingest_slug="lot", page_calibrations=(), divergence_bypass_requested=False))
    assert json.dumps(avant.manifest, sort_keys=True) == json.dumps(
        apres.manifest, sort_keys=True)
    assert avant.manifest["color"]["color_calibration_status"] == "not_applied"


def test_le_statut_de_projet_monte_a_applied_et_ne_redescend_jamais(tmp_path) -> None:
    """La promotion est **monotone**, et les deux sens sont exerces.

    Un `setdefault` seul interdisait le desapprentissage *et* l'apprentissage: il suffisait
    d'avoir scanne un premier lot sans page de calibration -- le cas le plus courant du
    terrain -- pour que le champ de projet reste `not_applied` a jamais, y compris apres
    un lot reellement corrige. Le test exerce la montee **et** la non-descente, parce
    qu'une regle qui ecrirait toujours la valeur de la passe passerait la premiere.
    """
    payloads = lot_payloads(with_calibration=False, sheet_count=2)
    pages = [scan.scanned_page(payload) for payload in payloads]
    rapport_nu = sof.write_lot_output_frames(tmp_path / "nu", pages)
    rapport_corrige = sof.write_lot_output_frames(
        tmp_path / "corrige", pages, color_calibration_status="applied")

    def fusion(existant, rapport):
        return sm.build_scan_manifest(existant, sm.ScanRecord(
            page_payloads=tuple(payloads), output_report=rapport, scan_dpi=DPI,
            ingest_slug="lot")).manifest

    premier = fusion(None, rapport_nu)
    assert premier["color"]["color_calibration_status"] == "not_applied"
    # Montee: une passe qui a reellement corrige releve le champ.
    monte = fusion(premier, rapport_corrige)
    assert monte["color"]["color_calibration_status"] == "applied"
    # Non-descente: une passe non corrigee ne desapprend pas.
    assert fusion(monte, rapport_nu)["color"]["color_calibration_status"] == "applied"
    # Et le champ **de lot**, lui, suit la passe dans les deux sens (`EPIC5-ARB-68`): la
    # monotonie du champ projet n'est defendable que parce qu'un autre champ dit la verite
    # sur le lot. Sans cette assertion, la non-descente ci-dessus resterait indistinguable
    # d'un document qui mente sur des frames reecrites.
    redescendu = fusion(monte, rapport_nu)
    lot_redescendu = next(entry for entry in redescendu["lots"]
                          if entry["lot_id"] == payloads[0]["lot_id"])
    assert lot_redescendu["color_calibration_status"] == "not_applied"


def test_un_rescan_non_corrige_du_meme_lot_ne_laisse_pas_le_document_dire_corrige(
    tmp_path,
) -> None:
    """Bloquant B2 de la revue, mesure sur les **octets** et non sur le champ.

    Le geste est celui que la garde de divergence demande a l'operateur -- rescanner --, et
    le regime est celui du terrain: la seconde passe oublie la page de calibration. Les
    huit frames reviennent alors au scan brut, et le document disait quand meme `applied`,
    par la regle monotone du champ projet. Le recapitulatif d'`encode` affirmait donc
    « correction active appliquee aux pixels » a un master dont aucun pixel ne l'etait:
    litteralement le faux succes de R12, dans le seul endroit ou l'operateur le lit.

    Un test qui ne regarderait que le champ ne prouverait rien: c'est la comparaison des
    octets, passe 1 contre passe 2, qui etablit que les pixels ont bien change de camp.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    project_dir, folder, payloads = lot_a_profil_designe(tmp_path, name="rescan")
    assert run_scan_designe(project_dir, folder) == 0
    document = manifest_of(project_dir)
    corrigees = {chemin.name: chemin.read_bytes()
                 for chemin in written_frames(project_dir, document)}
    assert len(corrigees) == 8
    lot_corrige = next(entry for entry in document["lots"]
                       if entry["lot_id"] == payloads[0]["lot_id"])
    assert lot_corrige["color_calibration_status"] == "applied"

    # Passe 2: **le meme lot**, la page de calibration oubliee sur le scanner.
    # **La seconde passe ne designe aucun profil**: c'est le geste de terrain que
    # ce test mesure -- l'operateur rescanne et oublie de redesigner --, et c'est
    # ce qui fait revenir les huit frames au scan brut.
    nu = write_scan_folder(tmp_path / "rescan-nu",
                           [(payloads[0], PRESSES_DU_TIRAGE[0]),
                            (payloads[1], PRESSES_DU_TIRAGE[1])])
    assert run_scan(project_dir, nu, "--overwrite") == 0

    apres = manifest_of(project_dir)
    brutes = {chemin.name: chemin.read_bytes()
              for chemin in written_frames(project_dir, apres)}
    assert set(brutes) == set(corrigees)
    assert all(brutes[nom] != corrigees[nom] for nom in brutes), (
        "les huit frames doivent etre revenues au scan brut, sinon le test ne mesure "
        "pas le regime du bloquant")

    lot_apres = next(entry for entry in apres["lots"]
                     if entry["lot_id"] == payloads[0]["lot_id"])
    assert lot_apres["color_calibration_status"] == "not_applied"
    assert encode_module.calibration_summary_line(lot_apres).startswith("not_applied")
    # Le champ **projet** reste `applied`, et c'est correct: un autre lot du projet a pu
    # etre corrige, et ce champ ne parle que du projet. Ce qui etait faux n'etait pas sa
    # valeur, c'etait le fait qu'`encode` la lise pour parler d'un lot.
    assert apres["color"]["color_calibration_status"] == "applied"


def test_la_constante_recopiee_du_statut_applique_ne_diverge_pas_de_son_proprietaire(
) -> None:
    """`io/` recopie l'orthographe faute de pouvoir importer `color_pipeline`.

    La recopie est forcee par la regle de couches -- `io/` ne charge pas OpenCV a
    l'import --, donc ce qu'on peut faire est la **confronter**. Sans ce test, une
    renommage cote proprietaire ferait diverger les deux en silence, et le symptome serait
    un champ de projet qui ne monte plus jamais.
    """
    assert sm.CALIBRATION_APPLIED == color_pipeline.APPLIED_STATUS
    assert sm.CALIBRATION_APPLIED in color_pipeline.CALIBRATION_STATUS_VALUES
    # Meme confrontation pour la seconde recopie, posee par `EPIC5-ARB-69`. Les deux
    # orthographes sont **distinctes**, sans quoi le test passerait en confondant les
    # deux constantes: une page sans mesure et une page corrigee ne se declarent pas
    # pareil, et c'est tout l'objet de l'arbitrage.
    assert sm.CALIBRATION_NOT_APPLIED == color_pipeline.NOT_APPLIED_STATUS
    assert sm.CALIBRATION_NOT_APPLIED in color_pipeline.CALIBRATION_STATUS_VALUES
    assert sm.CALIBRATION_NOT_APPLIED != sm.CALIBRATION_APPLIED


# ---------------------------------------------------------------------------
# AC 11 -- le constat d'encode, et le second champ
# ---------------------------------------------------------------------------


def test_le_constat_srgb_reste_vrai_et_perd_la_seule_phrase_qui_ne_l_est_plus() -> None:
    """AC 11: on retire la phrase fausse, et **rien d'autre**.

    Le constat porte sur la **courbe de transfert** -- sRGB tague bt709 --, ce que la
    correction active ne change pas: elle ajuste la reponse du couple imprimante/scanner.
    Confondre les deux sujets aurait fait retirer un constat vrai, et c'est nommement ce
    que l'AC interdit.
    """
    note = encode_module.SRGB_APPROXIMATION_NOTE
    for morceau in ("sRGB", "bt709", "courbe de transfert", "primaires"):
        assert morceau in note, morceau
    assert "aucune correction colorimetrique active" not in note, note
    # Le code du constat, lui, ne bouge pas: il nomme l'approximation de courbe.
    assert encode_module.ENCODE_SRGB_APPROXIMATION == "APPROXIMATION_SRGB_TAGUEE_REC709"
    assert (encode_module.ENCODE_SRGB_APPROXIMATION
            in encode_module.ENCODE_INFORMATIONAL_CODES)


@pytest.mark.parametrize("statut", ["not_applied", "applied", "failed"])
def test_le_second_champ_dit_ce_que_la_correction_a_fait(statut) -> None:
    """Les trois valeurs du contrat ont chacune leur phrase, et elles different.

    Un libelle unique satisferait « le champ existe » sans rien dire. La phrase nomme en
    outre le **geste**: un `failed` doit envoyer l'operateur au manifest, un `not_applied`
    ne doit envoyer nulle part.
    """
    ligne = encode_module.calibration_summary_line(
        {"color_calibration_status": statut})
    assert ligne.startswith(statut)
    autres = {encode_module.calibration_summary_line(
        {"color_calibration_status": valeur})
        for valeur in color_pipeline.CALIBRATION_STATUS_VALUES}
    assert len(autres) == 3, autres


def test_un_champ_absent_se_lit_non_applique_et_une_valeur_inconnue_se_dit() -> None:
    """Les deux bords: l'absence a un sens, l'inconnu n'en a pas et ne s'invente pas.

    Un manifest ecrit avant que le champ n'existe decrit correctement ses pixels par
    `not_applied`. Une valeur **hors contrat**, en revanche, est rendue telle quelle et
    nommee: la traduire ferait dire au recapitulatif ce que le manifest ne dit pas.
    """
    assert encode_module.calibration_summary_line({}).startswith("not_applied")
    assert encode_module.calibration_summary_line(
        {"lot_id": "rush-001_5"}).startswith("not_applied")
    inconnue = encode_module.calibration_summary_line(
        {"color_calibration_status": "presque"})
    assert inconnue.startswith("presque")
    assert "hors du contrat" in inconnue


def test_la_frontiere_de_perimetre_de_la_passe_de_correction_tient_sur_la_source() -> None:
    """Frontiere **negative** de la passe de correction, posee sur le code et non sur un
    condensat de commit.

    5.19 n'en avait aucune pour elle-meme -- la frontiere de 5.16 est devenue une propriete
    de l'histoire (deux condensats figes), donc plus rien ne pouvait echouer. Celle-ci porte
    sur la seule chose qui doit rester vraie quoi qu'il arrive au fil des stories: le
    recapitulatif d'`encode` ne lit **pas** la section `color` du projet. Un futur
    developpeur qui « reparerait » un champ absent en retombant sur le projet reintroduirait
    le faux succes mot pour mot, et le test unitaire par les deux bouts ne le verrait pas
    s'il posait un repli en second choix.
    """
    source = inspect.getsource(encode_module.calibration_summary_line)
    corps = source.split('"""')[-1]
    assert '"color"' not in corps, corps
    assert "'color'" not in corps, corps
    assert "manifest" not in corps, (
        "la fonction prend un lot: reintroduire le manifest entier ramene la portee projet")


def test_le_recapitulatif_ne_lit_jamais_le_champ_de_portee_projet() -> None:
    """`EPIC5-ARB-68`: le libelle parle du lot encode, donc il lit **le lot**.

    Frontiere du faux succes mesure a la revue de 5.19: sur le cas nominal de la v2.1 --
    deux lots du meme rush a deux cadences, un seul avec sa page de calibration -- le
    master du lot **non corrige** s'annoncait « correction active appliquee aux pixels ».
    Le champ etait lu exactement; il parlait d'autre chose.

    Le test est ecrit par les deux bouts, sans quoi il ne prouverait rien: un lot muet
    dans un projet qui declare `applied` ne doit **pas** remonter, et un lot qui declare
    `applied` dans un projet muet doit remonter. Une fonction qui lirait les deux
    sections, ou qui les fondrait par un `or`, echoue sur la premiere moitie.
    """
    lot_muet: dict = {"lot_id": "rush-001_12"}
    lot_corrige = {"lot_id": "rush-001_5", "color_calibration_status": "applied"}
    # Le projet declare `applied` parce qu'un **autre** lot est corrige: c'est la valeur
    # monotone, vraie a l'echelle du projet, et elle ne doit pas atteindre ce master-ci.
    assert encode_module.calibration_summary_line(lot_muet).startswith("not_applied")
    assert encode_module.calibration_summary_line(lot_corrige).startswith("applied")
    # Et la forme qui piegeait: passer le manifest entier ne rend plus le statut du
    # projet, parce que le champ n'y vit pas au niveau ou la fonction lit.
    manifest = {"color": {"color_calibration_status": "applied"}, "lots": [lot_muet]}
    assert encode_module.calibration_summary_line(manifest).startswith("not_applied")


@pytest.mark.parametrize("statut,attendu", [(None, "not_applied"), ("applied", "applied")])
def test_le_recapitulatif_porte_les_deux_champs_et_les_lit_au_manifest(
    tmp_path, statut, attendu,
) -> None:
    """Le recapitulatif rend les **deux** lignes, et la seconde vient du manifest.

    Le plan est construit par le **vrai** `plan_encode` sur un projet reellement scanne
    (fabrique de la suite d'encode, importee et non recopiee): c'est ce qui verifie que le
    champ est cable du document jusqu'au texte et pas seulement calculable. Les deux
    valeurs sont exercees, sinon un plan qui porterait toujours `not_applied` passerait.
    """
    import test_encode_command as enc

    project_dir, manifest = enc.scanned_project(tmp_path, name=f"resume-{attendu}")
    if statut is not None:
        # Le statut se pose sur **le lot** (`EPIC5-ARB-68`), pas sur la section projet:
        # c'est ce que `plan_encode` transporte jusqu'au texte.
        for lot in manifest["lots"]:
            if lot.get("lot_id") == enc.LOT:
                lot["color_calibration_status"] = statut
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=enc.LOT)
    texte = encode_module.render_summary(plan)

    assert f"Colorimetrie        : {encode_module.SRGB_APPROXIMATION_NOTE}" in texte
    assert f"Correction couleur  : {attendu} --" in texte
    # Les deux lignes disent deux choses differentes: fondues, la premiere redevenait
    # fausse des que la correction etait appliquee.
    assert plan.calibration_summary.startswith(attendu)
    assert plan.calibration_summary != encode_module.SRGB_APPROXIMATION_NOTE


# ---------------------------------------------------------------------------
# `EPIC5-ARB-78` -- `--cc {on|off}`: un choix d'operateur, jamais un echec
# ---------------------------------------------------------------------------


def test_le_drapeau_cc_off_ecrit_des_frames_non_corrigees(tmp_path) -> None:
    """`EPIC5-ARB-78`, mot pour mot d'Egan: « si le resultat est rate l'utilisateur peut
    relancer la commande avec un flag --cc off ».

    Le meme lot est passe deux fois, avec et sans le drapeau, et ce sont les **pixels**
    qui tranchent: un test qui ne lirait que le manifest passerait sur une implementation
    qui declare `not_applied` et corrige quand meme. Le defaut n'est pas theorique --
    c'est exactement la classe de faux succes que le champ `color_calibration_status`
    existe pour empecher.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    project_on, folder_on, _payloads = lot_a_profil_designe(tmp_path, name="avec")
    project_off, folder_off, _autres = lot_a_profil_designe(tmp_path, name="sans")
    assert run_scan_designe(project_on, folder_on) == 0
    assert run_scan_designe(project_off, folder_off, "--cc", "off") == 0

    frames_on = written_frames(project_on, manifest_of(project_on))
    frames_off = written_frames(project_off, manifest_of(project_off))
    assert [chemin.name for chemin in frames_on] == [
        chemin.name for chemin in frames_off], "meme lot, memes frames attendues"
    assert frames_on and len(frames_on) == 8
    differentes = [a.name for a, b in zip(frames_on, frames_off)
                   if a.read_bytes() != b.read_bytes()]
    assert differentes == [chemin.name for chemin in frames_on], (
        f"toutes les frames doivent differer, seules {differentes} different")


def test_le_drapeau_cc_off_declare_un_choix_et_non_une_panne(tmp_path) -> None:
    """Le motif au manifest est **distinct** du repli automatique, et c'est tout l'enjeu.

    Les deux regimes produisent des frames non corrigees; un seul appelle un rescan. Le
    document doit donc les separer, sans quoi l'operateur qui relit son lot trois jours
    plus tard ira rescanner une page de calibration que personne n'a jugee mauvaise.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    project_dir, folder, payloads = lot_a_profil_designe(tmp_path)
    assert run_scan_designe(project_dir, folder, "--cc", "off") == 0

    document = manifest_of(project_dir)
    assert document["color"]["color_calibration_status"] == "not_applied"
    entrees = calibration_entries(document)
    assert set(entrees) == {0, 1}, entrees
    for index in (0, 1):
        assert entrees[index]["status"] == "not_applied", entrees[index]
        assert "failure_reason" not in entrees[index], (
            "rien n'a echoue: le champ d'echec doit rester absent")
    # **La correction EXISTAIT, et le document le montre**: le profil designe est
    # inscrit au manifest avec sa page source et ses cardinaux de pastilles. C'est
    # ce qui distingue ce lot d'un lot sans profil du tout -- et c'est la moitie
    # de la propriete d'origine qui survit au regime de profil designe.
    profils = document["color"]["calibration_profiles"]
    assert len(profils) == 1, profils
    assert profils[0]["source_page_id"] == source_page_id_du_profil(project_dir)
    assert profils[0]["retained_patch_count"] > 0, profils[0]
    # **Le motif nomme un choix et non une panne**, et il est lu au **journal**:
    # l'entree de page qui le portait etait celle de la page de calibration, et
    # une page de calibration n'appartient plus a aucun lot (`EPIC5-ARB-82`). La
    # moitie « motif au manifest » de la propriete d'origine n'a donc plus de
    # porteur dans ce regime -- verse a `deferred-work.md` avec son origine
    # plutot qu'enterree, et hors du perimetre de 5.24.
    journal = (project_dir / project_layout.LOGS_DIRNAME / "scan.log").read_text(encoding="utf-8")
    assert cc.NOT_APPLIED_OPERATOR_OPT_OUT in journal, journal
    assert "NON appliquee sur demande" in journal, journal
    del payloads


def test_le_drapeau_cc_off_ne_fait_ajuster_aucune_planche_sur_elle_meme(
    tmp_path, monkeypatch,
) -> None:
    """La frontiere negative du drapeau, et elle n'est pas decorative.

    « Ne pas appliquer » a une traduction naive qui reintroduirait exactement ce
    qu'`EPIC5-ARB-57` interdit: calibrer chaque planche sans lui passer le profil du lot,
    c'est-a-dire la faire s'ajuster sur ses propres pastilles. Le compteur porte donc sur
    `calibrate_page`, qui ne doit **jamais** etre appele.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    calibrations = _Compteur(monkeypatch, "calibrate_page")
    ajustements = _Compteur(monkeypatch, "fit_lot_correction_from_page")
    project_dir, folder, _payloads = lot_a_profil_designe(tmp_path)
    assert run_scan_designe(project_dir, folder, "--cc", "off") == 0
    assert len(calibrations) == 0, (
        "aucune planche n'est calibree quand la correction n'est pas appliquee")
    # Et la correction du lot est tout de meme ajustee: c'est elle qui permet au document
    # de dire qu'il y en avait une, et de la mesurer.
    assert len(ajustements) == 1


def test_le_cablage_de_correction_requested_est_distinct_de_son_absence(
    tmp_path, monkeypatch,
) -> None:
    """Mutant survivant de la deuxieme passe de revue (2026-08-14):
    `correction_requested=apply_correction` fige a `True` dans `scan_command` ne fait
    echouer aucun des tests dedies a `--cc off`, parce que sur un lot nominal
    `--cc off` vide deja `correctable_page_count` par un **autre** chemin
    (`_scanned_pages_for_output` ne calibre aucune planche quand `apply_correction` est
    faux) -- la branche `correctable_page_count <= 0` de
    `derive_lot_calibration_status` rend alors `not_applied` par accident, que le
    cablage soit correct ou fige.

    Ce test isole le **cablage lui-meme**, independamment de cet effet de bord, en
    interceptant l'appel reel a `color_pipeline.derive_lot_calibration_status` que `cli`
    emet: c'est le seul point qui distingue « le choix descend jusqu'a la fonction qui
    decide » de « le choix arrive deguise en aucune planche corrigeable ».
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    recus: list[bool] = []
    original = color_pipeline.derive_lot_calibration_status

    def _espion(**kwargs):
        recus.append(kwargs["correction_requested"])
        return original(**kwargs)

    monkeypatch.setattr(color_pipeline, "derive_lot_calibration_status", _espion)

    project_off, folder_off, _p = lot_a_profil_designe(tmp_path, name="off")
    assert run_scan_designe(project_off, folder_off, "--cc", "off") == 0
    assert recus == [False], recus

    project_on, folder_on, _q = lot_a_profil_designe(tmp_path, name="on")
    assert run_scan_designe(project_on, folder_on) == 0
    assert recus == [False, True], recus


def test_le_drapeau_cc_off_sur_un_lot_sans_page_de_calibration_ne_declare_rien(
    tmp_path,
) -> None:
    """Contre-epreuve: un motif pose systematiquement ne distinguerait plus rien.

    Sans page de calibration il n'y avait **aucune** correction a decliner, donc rien a
    declarer: le document doit rester celui d'un lot ordinaire non corrige, celui-la meme
    que le filet octet a octet de l'AC 12 protege.
    """
    payloads = lot_payloads()
    folder = write_scan_folder(tmp_path / "sans-calib", [
        (payloads[1], PRESSES_DU_TIRAGE[0]), (payloads[2], PRESSES_DU_TIRAGE[1])])
    project_dir = tmp_path / "projet-sans-calib"
    assert run_scan(project_dir, folder, "--cc", "off") == LOT_INCOMPLET_MAIS_ECRIT

    document = manifest_of(project_dir)
    assert document["color"]["color_calibration_status"] == "not_applied"
    for entree in calibration_entries(document).values():
        assert set(entree) == {"page_index", "status"}, entree


def test_le_defaut_du_drapeau_est_on_et_son_vocabulaire_est_ferme(tmp_path) -> None:
    """Deux proprietes que l'arbitrage impose, et qui se perdent l'une sans l'autre.

    * le **defaut** est `on`: une option nouvelle ne change pas ce que fait une commande
      deja tapee. Mesure en comparant a un appel sans le drapeau, pas en lisant le code;
    * le vocabulaire est **ferme** a deux valeurs, et il n'existe aucun reglage numerique
      a cote. C'est la meme frontiere negative que le contournement de divergence porte
      depuis 5.16 -- « il ne regle aucun seuil » --, et elle compte double ici: le sens
      meme d'`EPIC5-ARB-78` est qu'on ne regle plus rien par un seuil.
    """
    # REBASE 5.24 (AC 8, classe A): ce test mesurait la correction d'un lot, et son
    # seul lien au vrac etait la fabrique qui posait la page de calibration dans la
    # pile. Il tourne desormais sur le regime NOMINAL du depot -- page de calibration
    # scannee a part, profil DESIGNE (`EPIC5-ARB-82`/`-83`) -- et ses planches portent
    # donc les index 0 et 1, non plus 1 et 2.
    project_defaut, folder_defaut, _p = lot_a_profil_designe(tmp_path, name="defaut")
    project_on, folder_on, _q = lot_a_profil_designe(tmp_path, name="explicite")
    assert run_scan_designe(project_defaut, folder_defaut) == 0
    assert run_scan_designe(project_on, folder_on, "--cc", "on") == 0
    assert manifest_of(project_defaut)["color"]["color_calibration_status"] == "applied"
    assert manifest_of(project_on)["color"]["color_calibration_status"] == "applied"
    for defaut, explicite in zip(
            written_frames(project_defaut, manifest_of(project_defaut)),
            written_frames(project_on, manifest_of(project_on))):
        assert defaut.read_bytes() == explicite.read_bytes(), defaut.name

    # Le vocabulaire est exerce par le **point d'entree reel** et non sur un parseur
    # reconstruit: `cli` n'expose pas le sien, et un parseur fabrique par le test ne
    # prouverait rien de celui que l'operateur rencontre.
    for refuse in (["--cc", "peut-etre"], ["--cc-reglage", "2.5"], ["--cc"]):
        with pytest.raises(SystemExit) as sortie:
            cli.main(["scan", "--project", str(tmp_path / "refus"), "--scan",
                      str(folder_on), "--dpi", str(DPI), *refuse])
        assert sortie.value.code == 2, refuse
