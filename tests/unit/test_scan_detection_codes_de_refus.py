"""Codes de refus enumeres de `scan_detection` (story 5.27, `EPIC7-ARB-66`).

Trois familles de tests, et il faut les trois:

1. **l'enumeration statique** -- un parcours de l'arbre syntaxique du module qui
   releve **tout** `raise` d'une exception de refus et echoue si l'un d'eux ne
   passe pas par la fabrique `_refus`. C'est la seule forme qui attrape un site
   **ajoute plus tard**: un test comportemental ne peut mesurer que les sites
   qu'il connait deja. L'analyseur lui-meme est eprouve contre des sources de
   synthese (`test_l_analyseur_*`), sans quoi rien ne prouverait qu'il echoue
   quand il doit echouer;
2. **les cas comportementaux** -- chacun des dix-huit sites est provoque par une
   entree reelle et rend son code;
3. **le mapping des exceptions etrangeres** -- rattrapees et traduites au site de
   rattrapage de `_detect_one_page`, du plus specifique au plus general. C'est le
   piege le plus cher de la story: `PayloadSchemaVersionRefused` est une
   **sous-classe** de `PayloadValidationError`, et un mapping mal ordonne replie
   silencieusement « planche perimee » sur « payload invalide ».
"""

from __future__ import annotations

import ast
import functools
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# La regle de regime -- « une reference de perimetre inatteignable est-elle un
# historique tronque, ou un AUTRE depot ? » -- vit dans `tests/_regime_du_depot.py`,
# ecrite une fois pour ses sept appelants.
sys.path.insert(0, str(REPO_ROOT / "tests"))
from _regime_du_depot import echoue_ou_saute  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import layout, page_templates, qr_codes, scan_detection
from mixed_media_utility.io import payload as payload_io

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "scan_detection.py"

PORTRAIT_2F = page_templates.build_template_id("portrait", 2, "2")
PAYSAGE_4F = page_templates.build_template_id("paysage", 4, "2")
SCAN_DPI = 300


# --------------------------------------------------------------------------
# L'analyseur syntaxique: releve des sites de refus d'un module
# --------------------------------------------------------------------------

def exceptions_de_refus() -> frozenset[str]:
    """Les exceptions dont une construction **doit** passer par la fabrique.

    Derive de la **hierarchie reelle** du module -- tout ce qui est
    `issubclass(..., ScanDetectionError)` dans son espace de noms -- et non
    d'une liste de noms litteraux (finding `F1` de la revue de vague 2 bis).

    Le motif, mesure: une liste litterale ne connait que les classes qui
    existaient le jour ou elle a ete ecrite. Une sous-classe neuve de
    `PageDetectionRefused` ajoutee plus tard et levee sans `_refus` etait
    classee « etranger » par l'analyseur, forme qu'aucun test n'interroge: le
    banc restait vert de bout en bout, et au rattrapage de `_detect_one_page`
    le nouveau motif sortait sous `REFUS_NON_CLASSE` -- c'est-a-dire
    exactement le « refus sans motif nomme » que cette story existe pour
    supprimer. La derivation est refaite a chaque appel, ce qui rend
    l'aveuglement lui-meme testable
    (`test_une_sous_classe_neuve_ne_passe_pas_sous_le_radar`).
    """
    return frozenset(
        nom
        for nom, objet in vars(scan_detection).items()
        if isinstance(objet, type)
        and issubclass(objet, scan_detection.ScanDetectionError)
    )

#: **Exclusion nommee**, et son motif: `validate_warning_code` et
#: `validate_refusal_code` levent un `ValueError` nu quand un **appelant du
#: module** demande un code inconnu. C'est un defaut de programmation, pas un
#: refus de planche: aucune page n'est en cause, rien n'est rattrape par
#: `_detect_one_page`, et exiger un code de refus la ou aucun refus n'existe
#: reviendrait a en inventer un. Toute autre fonction qui leverait un
#: `ValueError` nu fait echouer le test.
FONCTIONS_A_ERREUR_DE_PROGRAMMATION = frozenset(
    {"validate_warning_code", "validate_refusal_code"}
)


@dataclass(frozen=True)
class SiteDeRefus:
    """Un `raise` releve dans la source, avec ce que l'analyseur en conclut."""

    ligne: int
    fonction: str
    #: `fabrique`, `construction-directe`, `nom-non-resolu`, `reprise`,
    #: `erreur-de-programmation` ou `etranger`.
    forme: str
    #: Nom de la constante `REFUS_*` passee a la fabrique, quand il y en a une.
    code: str | None


@dataclass
class _Portee:
    """Une portee lexicale: son nom, ses `raise`, ses affectations, ses captures."""

    nom: str
    raises: list[ast.Raise]
    affectations: dict[str, ast.expr]
    noms_rattrapes: set[str]


def _portees(arbre: ast.AST) -> list[_Portee]:
    """Decouper l'arbre en portees, une par fonction (plus la portee module).

    Une portee par fonction et non un unique parcours a plat: `raise erreur`
    ne se resout qu'en regardant les affectations **de la meme fonction**, et
    deux fonctions peuvent tres bien nommer `erreur` deux choses differentes.
    """
    portees: list[_Portee] = []

    def visiter(noeud: ast.AST, portee: _Portee) -> None:
        for enfant in ast.iter_child_nodes(noeud):
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                sous = _Portee(getattr(enfant, "name", "<lambda>"), [], {}, set())
                portees.append(sous)
                visiter(enfant, sous)
                continue
            if isinstance(enfant, ast.Raise):
                portee.raises.append(enfant)
            elif isinstance(enfant, ast.Assign):
                for cible in enfant.targets:
                    if isinstance(cible, ast.Name):
                        portee.affectations[cible.id] = enfant.value
            elif isinstance(enfant, ast.ExceptHandler) and enfant.name:
                portee.noms_rattrapes.add(enfant.name)
            visiter(enfant, portee)

    racine = _Portee("<module>", [], {}, set())
    portees.append(racine)
    visiter(arbre, racine)
    return portees


def _nom_appele(func: ast.expr) -> str | None:
    """Le nom simple d'un appelable: `X()` et `mod.X()` rendent tous deux `X`."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _code_de_la_fabrique(appel: ast.Call) -> str | None:
    """Le nom de la constante passee en premier argument a `_refus`."""
    if not appel.args:
        return None
    premier = appel.args[0]
    return premier.id if isinstance(premier, ast.Name) else None


def _classer(
    noeud: ast.Raise, portee: _Portee, exceptions: frozenset[str]
) -> SiteDeRefus:
    ligne = noeud.lineno
    if noeud.exc is None:
        # `raise` nu: une reprise a l'identique, aucun refus n'est construit ici.
        return SiteDeRefus(ligne, portee.nom, "reprise", None)
    if isinstance(noeud.exc, ast.Call):
        nom = _nom_appele(noeud.exc.func)
        if nom == "_refus":
            return SiteDeRefus(
                ligne, portee.nom, "fabrique", _code_de_la_fabrique(noeud.exc)
            )
        if nom in exceptions:
            return SiteDeRefus(ligne, portee.nom, "construction-directe", None)
        if nom == "ValueError":
            return SiteDeRefus(ligne, portee.nom, "erreur-de-programmation", None)
        return SiteDeRefus(ligne, portee.nom, "etranger", None)
    if isinstance(noeud.exc, ast.Name):
        nom = noeud.exc.id
        if nom in portee.noms_rattrapes:
            # `except X as erreur: ... raise erreur`: une reprise, pas une
            # construction -- l'exception vient d'ailleurs.
            return SiteDeRefus(ligne, portee.nom, "reprise", None)
        valeur = portee.affectations.get(nom)
        if isinstance(valeur, ast.Call) and _nom_appele(valeur.func) == "_refus":
            return SiteDeRefus(
                ligne, portee.nom, "fabrique", _code_de_la_fabrique(valeur)
            )
        return SiteDeRefus(ligne, portee.nom, "nom-non-resolu", None)
    return SiteDeRefus(ligne, portee.nom, "nom-non-resolu", None)


def releve_les_sites_de_refus(source: str) -> list[SiteDeRefus]:
    """Tous les `raise` de la source, classes, tries par numero de ligne.

    L'ensemble des exceptions de refus est **re-derive a chaque appel** de la
    hierarchie du module: un banc qui le figerait a l'import ne pourrait plus
    mesurer son propre angle mort.
    """
    exceptions = exceptions_de_refus()
    sites = [
        _classer(noeud, portee, exceptions)
        for portee in _portees(ast.parse(source))
        for noeud in portee.raises
    ]
    return sorted(sites, key=lambda site: site.ligne)


# --------------------------------------------------------------------------
# L'analyseur est lui-meme eprouve: sans ca, rien ne prouve qu'il echoue
# --------------------------------------------------------------------------


def test_l_analyseur_denonce_une_construction_directe() -> None:
    """Le cas exact du « site ajoute plus tard » que l'AC 2 exige d'attraper."""
    source = (
        "def refuser():\n"
        "    raise PageGeometryRefused('un coin manque')\n"
    )
    assert [site.forme for site in releve_les_sites_de_refus(source)] == [
        "construction-directe"
    ]


def test_l_ensemble_des_exceptions_de_refus_est_derive_de_la_hierarchie() -> None:
    """La base et ses trois filles d'aujourd'hui, mais pas par leurs noms.

    L'ancrage reste utile -- une derivation qui rendrait l'ensemble vide
    laisserait passer *tous* les sites --, mais il est ecrit en inclusion:
    ajouter une sous-classe au module doit **agrandir** l'ensemble sans
    toucher a ce test.
    """
    derive = exceptions_de_refus()
    assert derive >= {
        "ScanDetectionError",
        "LotIdentityError",
        "PageDetectionRefused",
        "PageGeometryRefused",
    }
    # Et il ne ratisse pas au-dela de la hierarchie: l'espace de noms du module
    # porte d'autres classes, et une derivation qui se contenterait de
    # `isinstance(objet, type)` les emporterait toutes.
    for hors_hierarchie in ("DetectedPage", "LotDetectionReport", "Path"):
        assert hors_hierarchie not in derive


def test_une_sous_classe_neuve_ne_passe_pas_sous_le_radar(monkeypatch) -> None:
    """`F1`, la mesure au niveau de l'analyseur.

    La sous-classe est definie **ici**, dans le test: aucune liste de noms
    ecrite ailleurs ne peut la connaitre. C'est tout l'objet du finding --
    l'ancien `frozenset` litteral classait ce `raise` en « etranger », forme
    qu'aucun test n'interroge, et le banc restait vert.
    """

    class PagePayloadRefused(scan_detection.PageDetectionRefused):
        """Le site ajoute plus tard, tel qu'il serait ecrit un jour."""

    monkeypatch.setattr(
        scan_detection, "PagePayloadRefused", PagePayloadRefused, raising=False
    )
    source = (
        "def refuser():\n"
        "    raise PagePayloadRefused('un site neuf sans code')\n"
    )
    assert [site.forme for site in releve_les_sites_de_refus(source)] == [
        "construction-directe"
    ]


def test_l_analyseur_accepte_la_fabrique_directe_et_indirecte() -> None:
    source = (
        "def a():\n"
        "    raise _refus(REFUS_UN, 'phrase')\n"
        "def b():\n"
        "    erreur = _refus(REFUS_DEUX, 'phrase', classe=LotIdentityError)\n"
        "    erreur.extra = 1\n"
        "    raise erreur\n"
    )
    sites = releve_les_sites_de_refus(source)
    assert [(site.forme, site.code) for site in sites] == [
        ("fabrique", "REFUS_UN"),
        ("fabrique", "REFUS_DEUX"),
    ]


def test_l_analyseur_denonce_un_nom_construit_sans_la_fabrique() -> None:
    source = (
        "def b():\n"
        "    erreur = LotIdentityError('deux lots')\n"
        "    raise erreur\n"
    )
    assert [site.forme for site in releve_les_sites_de_refus(source)] == [
        "nom-non-resolu"
    ]


def test_l_analyseur_ne_confond_pas_une_reprise_avec_une_construction() -> None:
    source = (
        "def c():\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as erreur:\n"
        "        erreur.qr_status = 'decoded'\n"
        "        raise\n"
        "def d():\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as erreur:\n"
        "        raise erreur\n"
    )
    assert [site.forme for site in releve_les_sites_de_refus(source)] == [
        "reprise",
        "reprise",
    ]


def test_l_analyseur_separe_les_portees() -> None:
    """Deux fonctions peuvent nommer `erreur` deux choses differentes.

    Un analyseur a plat resoudrait `raise erreur` de `b` sur l'affectation de
    `a` et declarerait conforme un site qui ne l'est pas.
    """
    source = (
        "def a():\n"
        "    erreur = _refus(REFUS_UN, 'phrase')\n"
        "    raise erreur\n"
        "def b():\n"
        "    erreur = ScanDetectionError('phrase')\n"
        "    raise erreur\n"
    )
    assert [site.forme for site in releve_les_sites_de_refus(source)] == [
        "fabrique",
        "nom-non-resolu",
    ]


# --------------------------------------------------------------------------
# AC 2, volet statique: le module reel
# --------------------------------------------------------------------------

#: La table site -> code, **explicite** (AC 3). Elle est ordonnee comme les
#: `raise` du module, ce qui la rend sensible a un site ajoute, retire ou
#: deplace autant qu'a un code echange entre deux sites.
SITES_ATTENDUS: tuple[tuple[str, str], ...] = (
    ("__post_init__", "REFUS_ECHELLE_NON_FINIE"),
    ("__post_init__", "REFUS_ECHELLE_NON_POSITIVE"),
    ("_validate_scan_dpi", "REFUS_DPI_DE_SCAN_INVALIDE"),
    ("resolve_page_geometry", "REFUS_TEMPLATE_ID_INVALIDE"),
    ("_assert_marker_shape", "REFUS_MARQUEUR_MAL_FORME"),
    ("_assert_marker_shape", "REFUS_MARQUEUR_ID_INVALIDE"),
    ("_assert_marker_shape", "REFUS_MARQUEUR_CENTRE_INVALIDE"),
    ("compute_template_homography", "REFUS_COINS_EN_DOUBLE"),
    ("compute_template_homography", "REFUS_COINS_MANQUANTS"),
    ("compute_template_homography", "REFUS_PAGE_EN_MIROIR"),
    ("compute_template_homography", "REFUS_HOMOGRAPHIE_INCALCULABLE"),
    ("_assert_convex_quadrilateral", "REFUS_COINS_DEGENERES"),
    ("_assert_convex_quadrilateral", "REFUS_QUADRILATERE_NON_CONVEXE"),
    ("_measure_scale", "REFUS_COINS_DEGENERES"),
    ("_similarity_residual_px", "REFUS_COINS_DEGENERES"),
    ("resolve_page_identity", "REFUS_PLUSIEURS_QR"),
    ("resolve_page_identity", "REFUS_QR_SANS_MANIFEST"),
    ("_reconcile_lot", "REFUS_PLUSIEURS_LOTS"),
)


@pytest.fixture(scope="module")
def sites() -> list[SiteDeRefus]:
    return releve_les_sites_de_refus(MODULE_PATH.read_text(encoding="utf-8"))


def test_aucun_site_de_refus_ne_contourne_la_fabrique(sites) -> None:
    """`EPIC7-ARB-66`, verbatim: « un test qui enumere les sites de refus de
    `scan_detection` et echoue si l'un d'eux ne pose pas de code »."""
    fautifs = [
        site for site in sites if site.forme in {"construction-directe", "nom-non-resolu"}
    ]
    assert fautifs == [], (
        "ces `raise` construisent un refus sans passer par `_refus`, donc sans "
        "code: une page refusee la sortirait avec sa phrase et sans code, et "
        "aucun ecran ne pourrait brancher dessus"
    )


def test_le_garde_fou_rougit_sur_une_sous_classe_neuve_du_module() -> None:
    """`F1`, la mesure de fermeture: le garde-fou lui-meme, sur le module reel.

    Le test precedent mesure l'analyseur sur une source de synthese. Celui-ci
    rejoue exactement l'injection de la couche 3 -- une sous-classe neuve
    ajoutee a `scan_detection.py`, levee sans passer par `_refus` -- sur la
    **vraie** source du module, et exige que
    `test_aucun_site_de_refus_ne_contourne_la_fabrique` echoue. Sans lui, rien
    ne prouve que la derivation de la hierarchie atteint le garde-fou.

    La sous-classe est posee dans l'espace de noms du module puis retiree: on
    ne peut pas ecrire dans `scan_detection.py`, la source est lue sur disque
    par les autres tests du fichier.
    """

    class PagePayloadRefused(scan_detection.PageDetectionRefused):
        pass

    source_augmentee = MODULE_PATH.read_text(encoding="utf-8") + (
        "\n\n"
        "def _refuser_un_payload_illisible():\n"
        "    raise PagePayloadRefused('un site neuf sans code')\n"
    )
    setattr(scan_detection, "PagePayloadRefused", PagePayloadRefused)
    try:
        sites_augmentes = releve_les_sites_de_refus(source_augmentee)
    finally:
        delattr(scan_detection, "PagePayloadRefused")

    fautifs = [
        site
        for site in sites_augmentes
        if site.forme in {"construction-directe", "nom-non-resolu"}
    ]
    assert [(site.fonction, site.forme) for site in fautifs] == [
        ("_refuser_un_payload_illisible", "construction-directe")
    ], (
        "une sous-classe de `ScanDetectionError` ajoutee plus tard et levee sans "
        "`_refus` doit faire rougir le garde-fou: sinon son motif sort sous "
        "`REFUS_NON_CLASSE` au rattrapage de `_detect_one_page`"
    )
    # Temoin symetrique, et c'est le finding lui-meme: la **meme** source, la
    # sous-classe retiree de la hierarchie, ne fait plus rougir personne. Ce qui
    # attrape le site neuf est bien la derivation, et rien d'autre.
    assert [
        site
        for site in releve_les_sites_de_refus(source_augmentee)
        if site.forme in {"construction-directe", "nom-non-resolu"}
    ] == []


def test_les_seuls_valueerror_nus_sont_les_defauts_de_programmation(sites) -> None:
    fonctions = {
        site.fonction for site in sites if site.forme == "erreur-de-programmation"
    }
    assert fonctions == FONCTIONS_A_ERREUR_DE_PROGRAMMATION


def test_la_table_site_vers_code_est_celle_attendue(sites) -> None:
    releve = tuple(
        (site.fonction, site.code) for site in sites if site.forme == "fabrique"
    )
    assert releve == SITES_ATTENDUS


def test_les_dix_huit_sites_sont_bien_dix_huit(sites) -> None:
    assert len([site for site in sites if site.forme == "fabrique"]) == 18


def test_chaque_constante_citee_par_un_site_existe_et_est_au_vocabulaire() -> None:
    for _fonction, constante in SITES_ATTENDUS:
        valeur = getattr(scan_detection, constante)
        assert valeur in scan_detection.SCAN_REFUSAL_CODES


def test_un_code_par_cause_terrain_pas_un_code_par_ligne() -> None:
    """AC 3: les trois gardes de degenerescence des coins partagent leur code,
    et **seules** elles. Une fusion accidentelle de deux causes distinctes fait
    tomber le compte."""
    codes = [constante for _fonction, constante in SITES_ATTENDUS]
    assert len(set(codes)) == 16
    partages = {code for code in codes if codes.count(code) > 1}
    assert partages == {"REFUS_COINS_DEGENERES"}


# --------------------------------------------------------------------------
# AC 1: le vocabulaire ferme et sa fabrique
# --------------------------------------------------------------------------


def test_chaque_constante_de_refus_est_dans_le_tuple() -> None:
    constantes = {
        nom: valeur
        for nom, valeur in vars(scan_detection).items()
        if nom.startswith("REFUS_") and isinstance(valeur, str)
    }
    assert constantes, "aucune constante REFUS_* n'existe"
    assert set(constantes.values()) == set(scan_detection.SCAN_REFUSAL_CODES)


def test_le_vocabulaire_ne_porte_aucun_doublon() -> None:
    codes = scan_detection.SCAN_REFUSAL_CODES
    assert len(codes) == len(set(codes))
    assert isinstance(codes, tuple)


def test_les_codes_sont_en_kebab_case_comme_ceux_de_relink() -> None:
    """Meme gabarit que `relink.REFUS_*`: un vocabulaire dont la moitie serait
    en `SCREAMING_SNAKE` se confondrait avec les codes d'avertissement."""
    for code in scan_detection.SCAN_REFUSAL_CODES:
        assert code == code.lower()
        assert " " not in code and "_" not in code


def test_un_code_hors_vocabulaire_est_refuse_a_l_emission() -> None:
    with pytest.raises(ValueError) as excinfo:
        scan_detection.validate_refusal_code("motif-invente")
    assert "motif-invente" in str(excinfo.value)
    with pytest.raises(ValueError):
        scan_detection._refus("motif-invente", "phrase")


def test_la_fabrique_pose_le_code_le_message_et_les_attributs() -> None:
    erreur = scan_detection._refus(
        scan_detection.REFUS_PLUSIEURS_QR,
        "deux planches sur la vitre",
        classe=scan_detection.PageDetectionRefused,
        qr_status=qr_codes.DECODE_MULTIPLE,
    )
    assert isinstance(erreur, scan_detection.PageDetectionRefused)
    assert erreur.refusal_code == scan_detection.REFUS_PLUSIEURS_QR
    assert str(erreur) == "deux planches sur la vitre"
    assert erreur.qr_status == qr_codes.DECODE_MULTIPLE


def test_la_fabrique_rend_par_defaut_la_base_du_module() -> None:
    erreur = scan_detection._refus(scan_detection.REFUS_ECHELLE_NON_FINIE, "phrase")
    assert type(erreur) is scan_detection.ScanDetectionError


def test_le_vocabulaire_et_la_fabrique_sont_exportes() -> None:
    for nom in ("SCAN_REFUSAL_CODES", "validate_refusal_code"):
        assert nom in scan_detection.__all__


# --------------------------------------------------------------------------
# AC 2 volet comportemental / AC 3 / AC 5: les dix-huit sites, un par un
# --------------------------------------------------------------------------


def _markers(template_id: str = PORTRAIT_2F, dpi: int = SCAN_DPI) -> list[dict]:
    spec = page_templates.get_template(template_id)
    centres = page_templates.corner_marker_centers_mm(spec)
    return [
        {
            "id": marker_id,
            "center": [
                float(v) for v in page_templates.mm_to_px(*centres[marker_id], dpi)
            ],
        }
        for marker_id in layout.CORNER_MARKER_IDS
    ]


def _geometrie(template_id: str = PORTRAIT_2F) -> dict:
    return scan_detection.resolve_page_geometry(template_id, SCAN_DPI)


def _sans_coin(absent: int) -> list[dict]:
    return [marker for marker in _markers() if marker["id"] != absent]


def _en_miroir() -> list[dict]:
    markers = _markers()
    par_id = {m["id"]: m for m in markers}
    par_id[0]["center"], par_id[1]["center"] = par_id[1]["center"], par_id[0]["center"]
    par_id[3]["center"], par_id[2]["center"] = par_id[2]["center"], par_id[3]["center"]
    return markers


def _en_double() -> list[dict]:
    markers = _markers()
    markers.append(dict(markers[0]))
    return markers


def _deux_coins_confondus() -> list[dict]:
    markers = _markers()
    markers[1]["center"] = list(markers[0]["center"])
    return markers


_QUAD_PLAT = np.array(
    [[100.0, 100.0], [200.0, 100.0], [300.0, 100.5], [400.0, 101.0]], dtype=np.float64
)
_QUAD_CONFONDU = np.array([[7.0, 7.0]] * 4, dtype=np.float64)


def _payload_serialise() -> str:
    """Un payload de production, serialise: le contenu du QR n'est pas en cause."""
    return payload_io.serialize_payload(
        payload_io.build_page_payload(
            project_id="demo-project-01",
            rush_id="rush-a1",
            lot_id="lot-0007",
            page_index=0,
            page_count=2,
            fps_target=24.0,
            timecode_base_fps="25/1",
            template_id=PORTRAIT_2F,
            patch_preset_id="patch-default-v1",
            target_colorspace="bt709",
            gamut_map_id="gamut-map-none-1",
            slots=[
                {"slot_index": index, "frame_timecode": f"00:00:{index:02d}:00"}
                for index in range(2)
            ],
        )
    )


@functools.lru_cache(maxsize=1)
def _vitre_a_deux_planches() -> np.ndarray:
    """Deux symboles QR dans le meme champ: deux planches posees sur la vitre.

    Une **entree reelle**, pas un monkeypatch: le decodeur y compte deux
    symboles de lui-meme. Meme forme que le cas terrain de `test_qr_codes` --
    deux tuiles imprimees a 35 mm cote a cote, separees d'une gouttiere
    blanche -- parce que c'est ainsi que la panne se produit: la feuille
    suivante depasse sur le bord de la vitre.
    """
    tuile = qr_codes.render_for_print(
        qr_codes.encode_qr_image(_payload_serialise()), 35.0, 600
    )
    gouttiere = np.full((tuile.shape[0], 200), 255, np.uint8)
    return np.hstack([tuile, gouttiere, tuile])


def _feuille_sans_symbole() -> np.ndarray:
    """Une feuille blanche: aucun symbole a decoder, donc aucune identite."""
    return np.full((400, 400), 255, np.uint8)


#: Un declencheur reel par site, et le code qu'il doit poser. Les trois derniers
#: passent par les gardes internes: elles ne sont atteignables que directement,
#: `compute_template_homography` refusant plus tot sur une geometrie degeneree.
DECLENCHEURS: tuple[tuple[str, object, str], ...] = (
    (
        "echelle non finie",
        lambda: scan_detection.PageScaleMeasurement(float("inf"), 1.0, 0.0),
        "REFUS_ECHELLE_NON_FINIE",
    ),
    (
        "echelle nulle",
        lambda: scan_detection.PageScaleMeasurement(0.0, 1.0, 0.0),
        "REFUS_ECHELLE_NON_POSITIVE",
    ),
    (
        "dpi hors bornes",
        lambda: scan_detection.resolve_page_geometry(PORTRAIT_2F, 0),
        "REFUS_DPI_DE_SCAN_INVALIDE",
    ),
    (
        "template_id non hachable",
        lambda: scan_detection.resolve_page_geometry(["tpl"], SCAN_DPI),
        "REFUS_TEMPLATE_ID_INVALIDE",
    ),
    (
        "marqueur sans cle",
        lambda: scan_detection._partition_markers([{"center": [1.0, 2.0]}]),
        "REFUS_MARQUEUR_MAL_FORME",
    ),
    (
        "identifiant de marqueur non entier",
        lambda: scan_detection._partition_markers([{"id": 1.5, "center": [1.0, 2.0]}]),
        "REFUS_MARQUEUR_ID_INVALIDE",
    ),
    (
        "centre de marqueur invalide",
        lambda: scan_detection._partition_markers([{"id": 0, "center": [1.0]}]),
        "REFUS_MARQUEUR_CENTRE_INVALIDE",
    ),
    (
        "coins en double",
        lambda: scan_detection.compute_template_homography(
            _en_double(), _geometrie(), SCAN_DPI
        ),
        "REFUS_COINS_EN_DOUBLE",
    ),
    (
        "coins manquants",
        lambda: scan_detection.compute_template_homography(
            _sans_coin(2), _geometrie(), SCAN_DPI
        ),
        "REFUS_COINS_MANQUANTS",
    ),
    (
        "page en miroir",
        lambda: scan_detection.compute_template_homography(
            _en_miroir(), _geometrie(), SCAN_DPI
        ),
        "REFUS_PAGE_EN_MIROIR",
    ),
    (
        "deux coins confondus",
        lambda: scan_detection.compute_template_homography(
            _deux_coins_confondus(), _geometrie(), SCAN_DPI
        ),
        "REFUS_COINS_DEGENERES",
    ),
    (
        "quadrilatere non convexe",
        lambda: scan_detection._assert_convex_quadrilateral(_QUAD_PLAT),
        "REFUS_QUADRILATERE_NON_CONVEXE",
    ),
    (
        "distance entre centres nulle",
        lambda: scan_detection._measure_scale(
            _QUAD_CONFONDU,
            np.array(
                [[0.0, 0.0], [100.0, 0.0], [100.0, 200.0], [0.0, 200.0]],
                dtype=np.float64,
            ),
        ),
        "REFUS_COINS_DEGENERES",
    ),
    (
        "aucune similitude ajustable",
        lambda: scan_detection._similarity_residual_px(
            _QUAD_CONFONDU,
            np.array(
                [[0.0, 0.0], [100.0, 0.0], [100.0, 200.0], [0.0, 200.0]],
                dtype=np.float64,
            ),
        ),
        "REFUS_COINS_DEGENERES",
    ),
    # --- Les deux sites de `resolve_page_identity` (finding `F2`) ---------
    #
    # Ils n'etaient atteints par aucun cas comportemental de ce banc:
    # `REFUS_PLUSIEURS_QR` n'apparaissait que dans un appel direct a la
    # fabrique, et `REFUS_QR_SANS_MANIFEST` de biais, par un test qui ne
    # nomme pas le code. Le voisin `test_les_dix_huit_sites_sont_bien_dix_huit`
    # compte l'AST, ce qui se lit facilement comme une couverture qu'il
    # n'apporte pas.
    (
        "deux QR dans le champ",
        lambda: scan_detection.resolve_page_identity(
            # Le manifest declare bien le lot: sans lui, la page serait refusee
            # faute de substitut et le test passerait pour la mauvaise raison.
            _vitre_a_deux_planches(),
            manifest_template_id=PORTRAIT_2F,
        ),
        "REFUS_PLUSIEURS_QR",
    ),
    (
        "QR inexploitable et aucun manifest",
        lambda: scan_detection.resolve_page_identity(
            _feuille_sans_symbole(), manifest_template_id=None
        ),
        "REFUS_QR_SANS_MANIFEST",
    ),
)


def _homographie_incalculable() -> None:
    """Le seul site qu'aucune entree plausible n'atteint (voir le test dedie)."""
    import cv2

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cv2, "findHomography", lambda *a, **k: (None, None))
        scan_detection.compute_template_homography(_markers(), _geometrie(), SCAN_DPI)


def _deux_lots_sur_la_vitre() -> None:
    """Le seul refus de **lot**: il n'a pas de page a lui, il les emporte toutes."""
    scan_detection._reconcile_lot(
        [
            _page_detectee(1, lot_id="lot-0008", page_index=1),
            _page_detectee(0, lot_id="lot-0007", page_index=0),
        ],
        ingest_slug="lot-0007",
        ingested_count=2,
    )


#: **Tous** les cas comportementaux du banc, les deux non declenchables par une
#: entree d'image comprises. C'est cette table, et non `DECLENCHEURS`, que la
#: couverture des dix-huit sites confronte a `SITES_ATTENDUS`.
CAS_COMPORTEMENTAUX: tuple[tuple[str, object, str], ...] = DECLENCHEURS + (
    (
        "homographie incalculable",
        _homographie_incalculable,
        "REFUS_HOMOGRAPHIE_INCALCULABLE",
    ),
    ("deux lots sur la vitre", _deux_lots_sur_la_vitre, "REFUS_PLUSIEURS_LOTS"),
)

#: Le releve d'un refus rend le **code publie**; la table des sites nomme la
#: **constante**. Les deux se rejoignent ici, et l'inversion est licite parce que
#: `test_le_vocabulaire_ne_porte_aucun_doublon` interdit deux constantes de meme
#: valeur.
_CONSTANTE_PAR_CODE = {
    valeur: nom
    for nom, valeur in vars(scan_detection).items()
    if nom.startswith("REFUS_") and isinstance(valeur, str)
}


def _site_provoque(declencheur) -> tuple[str, str]:
    """`(fonction qui a leve, constante du code)`, releves sur l'exception reelle.

    La fonction est lue dans le **dernier cadre de la trace**, donc celle qui
    porte le `raise`, et non celle que le test appelle: `_partition_markers`
    delegue a `_assert_marker_shape`, `compute_template_homography` a
    `_assert_convex_quadrilateral`. C'est ce qui rend la confrontation avec
    `SITES_ATTENDUS` -- releve, lui, sur l'arbre syntaxique -- non circulaire.
    """
    try:
        declencheur()
    except scan_detection.ScanDetectionError as erreur:
        trace = erreur.__traceback__
        while trace.tb_next is not None:
            trace = trace.tb_next
        return trace.tb_frame.f_code.co_name, _CONSTANTE_PAR_CODE[erreur.refusal_code]
    raise AssertionError("le declencheur n'a leve aucun refus")


@pytest.mark.parametrize(
    "libelle, declencheur, constante",
    CAS_COMPORTEMENTAUX,
    ids=[libelle for libelle, _d, _c in CAS_COMPORTEMENTAUX],
)
def test_chaque_site_pose_son_code(libelle, declencheur, constante) -> None:
    with pytest.raises(scan_detection.ScanDetectionError) as excinfo:
        declencheur()
    attendu = getattr(scan_detection, constante)
    assert excinfo.value.refusal_code == attendu, libelle
    assert attendu in scan_detection.SCAN_REFUSAL_CODES


def test_les_dix_huit_sites_sont_TOUS_provoques_par_une_entree_reelle() -> None:
    """`F2`: l'AC 2 dit dix-huit, le banc doit en **mesurer** dix-huit.

    Le voisin `test_les_dix_huit_sites_sont_bien_dix_huit` compte les `raise`
    de l'arbre syntaxique: c'est le volet statique, et il ne dit rien de ce
    qu'une entree reelle atteint. Avant ce test, le recensement etait de 17
    sur 18 -- `REFUS_PLUSIEURS_QR` n'etait provoque par rien, et le compte
    n'aurait ete rendu par aucune mesure.

    La confrontation n'est pas circulaire: le membre de gauche est releve dans
    la **trace d'execution** de chaque refus, celui de droite sur l'**arbre
    syntaxique** du module. Un site deplace d'une fonction a l'autre, un code
    echange entre deux sites, ou un site ajoute sans cas comportemental font
    diverger les deux releves.
    """
    provoques = {_site_provoque(declencheur) for _l, declencheur, _c in CAS_COMPORTEMENTAUX}
    assert provoques == set(SITES_ATTENDUS), {
        "provoques et non declares": sorted(provoques - set(SITES_ATTENDUS)),
        "declares et jamais provoques": sorted(set(SITES_ATTENDUS) - provoques),
    }
    assert len(provoques) == 18


def test_l_homographie_incalculable_pose_son_code(monkeypatch) -> None:
    """Le seul site que `cv2.findHomography` n'atteint pas depuis une entree
    plausible: il rend une matrice de rang deficient plutot que `None` sur les
    geometries degenerees, toutes deja refusees en amont."""
    import cv2

    monkeypatch.setattr(cv2, "findHomography", lambda *a, **k: (None, None))
    with pytest.raises(scan_detection.PageGeometryRefused) as excinfo:
        scan_detection.compute_template_homography(_markers(), _geometrie(), SCAN_DPI)
    assert excinfo.value.refusal_code == scan_detection.REFUS_HOMOGRAPHIE_INCALCULABLE


def _page_detectee(rank: int, *, lot_id: str, page_index: int) -> scan_detection.DetectedPage:
    return scan_detection.DetectedPage(
        read_rank=rank,
        status=scan_detection.PAGE_OK,
        locator_source=f"scans/p{rank}.tif",
        locator_page_index=None,
        qr_status="decoded",
        project_id="demo-project-01",
        rush_id="rush-a1",
        lot_id=lot_id,
        page_index=page_index,
        page_count=2,
    )


def test_le_refus_de_lot_porte_son_code_et_garde_ses_identites() -> None:
    """AC 8: `LotIdentityError` emporte le lot -- il n'atteint aucun document --
    et c'est justement pourquoi son code voyage sur l'exception."""
    with pytest.raises(scan_detection.LotIdentityError) as excinfo:
        scan_detection._reconcile_lot(
            [
                _page_detectee(0, lot_id="lot-0007", page_index=0),
                _page_detectee(1, lot_id="lot-0008", page_index=1),
            ],
            ingest_slug="lot-0007",
            ingested_count=2,
        )
    erreur = excinfo.value
    assert erreur.refusal_code == scan_detection.REFUS_PLUSIEURS_LOTS
    assert erreur.identities_by_read_rank == (
        (0, "demo-project-01", "rush-a1", "lot-0007"),
        (1, "demo-project-01", "rush-a1", "lot-0008"),
    )


def test_les_identites_du_refus_de_lot_sont_TRIEES_par_rang_de_lecture() -> None:
    """`EC-1`: l'ordre d'entree differe de l'ordre des `read_rank`.

    Le test precedent fournit la collection **deja triee** -- la cible en
    premiere position -- donc la permutation ne peut pas s'y voir: le mutant
    `sorted(identified, key=...)` -> `list(identified)` y survivait, et avec
    lui tout le banc (379 passed a la couche 2). Manquement au point 2 de la
    checklist des fabriques, quatrieme occurrence de cette famille dans le
    depot.

    Ce que le tri porte, et pourquoi il n'est pas cosmetique: cet attribut
    existe **pour que l'operateur trie ses feuilles**. Les trois planches sont
    sur la vitre, deux lots melanges; l'ordre annonce est celui dans lequel il
    doit les reprendre. Un ordre faux le fait piocher la mauvaise planche --
    c'est-a-dire fabriquer le lot que ce refus existe pour empecher.
    """
    # Ordre d'entree 2, 0, 1: aucun des trois n'est a sa place, et les trois
    # identites sont distinguables (un lot different par rang).
    with pytest.raises(scan_detection.LotIdentityError) as excinfo:
        scan_detection._reconcile_lot(
            [
                _page_detectee(2, lot_id="lot-0009", page_index=2),
                _page_detectee(0, lot_id="lot-0007", page_index=0),
                _page_detectee(1, lot_id="lot-0008", page_index=1),
            ],
            ingest_slug="lot-0007",
            ingested_count=3,
        )
    assert excinfo.value.identities_by_read_rank == (
        (0, "demo-project-01", "rush-a1", "lot-0007"),
        (1, "demo-project-01", "rush-a1", "lot-0008"),
        (2, "demo-project-01", "rush-a1", "lot-0009"),
    )


# --------------------------------------------------------------------------
# AC 5: la phrase francaise est conservee, caractere pour caractere
# --------------------------------------------------------------------------


PHRASES_DU_BASELINE: tuple[tuple[object, str], ...] = (
    (
        lambda: scan_detection.PageScaleMeasurement(0.0, 1.0, 0.0),
        "Echelle non strictement positive: scale_x=0.0, scale_y=1.0.",
    ),
    (
        lambda: scan_detection._partition_markers([{"id": 0, "center": [1.0]}]),
        "Centre de marqueur invalide pour l'ID 0: [1.0]. "
        "Deux coordonnees finies sont attendues.",
    ),
    (
        lambda: scan_detection.compute_template_homography(
            _sans_coin(2), _geometrie(), SCAN_DPI
        ),
        "Marqueurs ArUco de coin manquants: [2]. IDs attendus: [0, 1, 2, 3].",
    ),
    (
        lambda: scan_detection.compute_template_homography(
            _en_miroir(), _geometrie(), SCAN_DPI
        ),
        "Les marqueurs de coin sont en disposition miroir: la page a ete "
        "retournee. La redresser produirait des frames inversees sans erreur.",
    ),
    (
        lambda: scan_detection._assert_convex_quadrilateral(_QUAD_PLAT),
        "Les marqueurs de coin ne forment pas un quadrilatere convexe utilisable "
        "(page pliee, prise de vue rasante, ou marqueur parasite).",
    ),
)


@pytest.mark.parametrize("declencheur, phrase", PHRASES_DU_BASELINE)
def test_la_phrase_francaise_est_inchangee(declencheur, phrase) -> None:
    """Cinq refus de familles differentes, la phrase litterale dans le test.

    L'AC 5 se joue au caractere: un code pose a cote de la phrase ne doit rien
    lui retirer, et surtout pas la remplacer -- un consommateur actuel lit
    `refusal_reason` et rien d'autre.
    """
    with pytest.raises(scan_detection.ScanDetectionError) as excinfo:
        declencheur()
    assert str(excinfo.value) == phrase


# --------------------------------------------------------------------------
# AC 4: le mapping des exceptions etrangeres, et son ORDRE
# --------------------------------------------------------------------------


def test_le_mapping_etranger_va_du_plus_specifique_au_plus_general() -> None:
    """Le piege le plus cher de la story, mesure mecaniquement.

    `PayloadSchemaVersionRefused` et `PayloadVersionMissing` heritent de
    `PayloadValidationError`. Une base ecrite avant ses filles replie
    silencieusement « planche perimee » sur « payload invalide » -- et aucun
    test qui n'assert que « un code est pose » ne le voit.
    """
    familles = [famille for famille, _code in scan_detection._REFUS_ETRANGERS]
    for rang, famille in enumerate(familles):
        for suivante in familles[rang + 1:]:
            # La chaine rend la **premiere** entree qui matche: une entree
            # ecrite tot et plus generale qu'une entree ecrite tard absorbe
            # celle-ci sans que rien ne le signale.
            assert not issubclass(suivante, famille), (
                f"{suivante.__name__} est une sous-classe de {famille.__name__} "
                "mais lui est ecrite APRES: le refus specifique serait absorbe "
                "par le general"
            )


@pytest.mark.parametrize(
    "exception, constante",
    [
        (payload_io.PayloadSchemaVersionRefused("perimee"), "REFUS_PLANCHE_PERIMEE"),
        (payload_io.PayloadVersionMissing("sans version"), "REFUS_PAYLOAD_SANS_VERSION"),
        (payload_io.PayloadValidationError("invalide"), "REFUS_PAYLOAD_INVALIDE"),
        (page_templates.UnknownTemplateError("inconnu"), "REFUS_TEMPLATE_INCONNU"),
    ],
)
def test_chaque_famille_etrangere_a_son_code(exception, constante) -> None:
    assert scan_detection._code_de_refus_etranger(exception) == getattr(
        scan_detection, constante
    )


def test_les_quatre_familles_d_ingestion_sont_illisibles_de_la_meme_facon() -> None:
    from mixed_media_utility import scan_ingest

    familles = (
        scan_ingest.ScanIngestError,
        scan_ingest.UnsupportedScanInputError,
        scan_ingest.EmptyScanLotError,
        scan_ingest.InvalidScanDpiError,
        scan_ingest.PdfIngestError,
    )
    for famille in familles:
        assert (
            scan_detection._code_de_refus_etranger(famille("illisible"))
            == scan_detection.REFUS_PAGE_ILLISIBLE
        )


def test_la_planche_perimee_ne_se_replie_pas_sur_le_payload_invalide() -> None:
    """AC 4, l'assertion qui compte: **quel** code, sur les deux sous-classes
    separement, et distinct de celui de la base."""
    perimee = scan_detection._code_de_refus_etranger(
        payload_io.PayloadSchemaVersionRefused("planche 1.0")
    )
    sans_version = scan_detection._code_de_refus_etranger(
        payload_io.PayloadVersionMissing("aucune cle de version")
    )
    invalide = scan_detection._code_de_refus_etranger(
        payload_io.PayloadValidationError("champ absent")
    )
    assert len({perimee, sans_version, invalide}) == 3


def test_une_exception_etrangere_sans_entree_recoit_le_code_generique() -> None:
    """Repli explicite: **jamais `None`** sur un chemin de refus, et un code qui
    dit qu'il est generique plutot que de se faire passer pour une cause."""
    class RefusInconnu(RuntimeError):
        pass

    code = scan_detection._code_de_refus_etranger(RefusInconnu("venu d'ailleurs"))
    assert code == scan_detection.REFUS_NON_CLASSE
    assert code in scan_detection.SCAN_REFUSAL_CODES
    assert "non-classe" in code


def test_le_code_generique_n_est_pose_par_aucun_site_du_module(sites) -> None:
    """Il ne doit exister qu'au repli: un site qui l'emettrait rendrait un refus
    precis indiscernable d'un refus inconnu."""
    codes = {site.code for site in sites if site.forme == "fabrique"}
    assert "REFUS_NON_CLASSE" not in codes


# --------------------------------------------------------------------------
# AC 10: les frontieres de perimetre, mesurees sur le diff REEL de la story
# --------------------------------------------------------------------------
#
# La forme usuelle du depot (`test_chain_profile_scan.py`, 5.22) confronte
# `git diff <baseline> <fin> -- src`. Elle ne s'applique pas telle quelle ici,
# et pour une raison mesuree dans ce meme fichier: la borne haute `HEAD` a cesse
# d'etre juste « le jour ou une AUTRE story a commence a travailler sur la meme
# branche », et la frontiere s'est mise a accuser les fichiers d'autrui d'etre
# en trop. Or `claude/correctif-ouverture-projet-gui` porte simultanement le
# travail de deux autres agents -- l'interface, et la story 5.28.
#
# La frontiere porte donc sur les fichiers des commits **de cette story**,
# reperes par le prefixe de leur sujet. C'est ce que l'AC 10 demande de mesurer
# (« dans le diff de cette story »), et c'est la seule borne qui ne se
# desapprenne pas au premier commit d'un voisin.
#
# --- Et ce releve a une duree de vie bornee (finding `BH-9`) ----------------
#
# Mesure de la couche 1: `a37e16d..HEAD` rend 7 chemins, `a37e16d..5feba99` en
# rend **zero**. Des que la plage ne porte plus de commit du sujet -- et le
# depot squashe a la fusion sur `main` --, les neuf parametrages de
# `test_les_chemins_interdits_restent_hors_du_diff` deviennent **vacants**:
# liste vide, aucun fautif, vert vide. Un test qui devient vert parce qu'il n'a
# plus rien a mesurer est pire que pas de test.
#
# La section est donc a deux etages, et c'est le premier qui porte la garantie:
#
#  1. une **garde permanente**, independante de git, qui ne peut pas devenir
#     vacante: le vocabulaire de refus est confine a `scan_detection`, aucun des
#     modules interdits n'en porte trace, l'ecran de 7.4 n'est pas cable au
#     vocabulaire ferme du coeur, et `[tool.mutmut]` est reste generique. C'est
#     la **substance** de chaque interdit, pas la trace de son diff, et elle
#     survit au squash, au rebase, a `git archive` et au clone superficiel;
#  2. le **releve git**, plus fin tant que l'historique porte la story -- il
#     voit un fichier touche puis remis en etat, ce que l'etage 1 ne voit pas --
#     et qui, quand la plage ne rend plus rien, **se declare inapplicable** par
#     un `skip` nomme plutot que de passer en silence.

#: `baseline_commit` de la fiche 5.27.
_BASELINE_5_27 = "a37e16d"

#: Prefixe de sujet des commits de cette story.
_PREFIXE_5_27 = "5.27"

#: Les seuls fichiers de production que cette story a le droit de toucher.
_PRODUCTION_5_27 = frozenset(
    {
        "src/mixed_media_utility/scan_detection.py",
        "src/mixed_media_utility/scan_previz.py",
    }
)

#: Les interdits de l'AC 10, par prefixe de chemin, avec leur motif.
_INTERDITS_5_27: tuple[tuple[str, str], ...] = (
    ("src/mixed_media_utility/gui/", "7.4 est `done` et son repli est permanent"),
    ("tests/unit/gui/", "7.4 est `done` et son repli est permanent"),
    (
        "src/mixed_media_utility/layout.py",
        "l'etat « marqueurs incomplets » n'a pas de producteur et cette story "
        "n'en cree pas (EPIC7-ARB-66, geste 3)",
    ),
    (
        "src/mixed_media_utility/io/payload.py",
        "les exceptions etrangeres sont traduites au site de rattrapage",
    ),
    (
        "src/mixed_media_utility/page_templates.py",
        "les exceptions etrangeres sont traduites au site de rattrapage",
    ),
    (
        "src/mixed_media_utility/scan_ingest.py",
        "les exceptions etrangeres sont traduites au site de rattrapage",
    ),
    ("src/mixed_media_utility/color_calibration.py", "chemin fragile intact"),
    ("src/mixed_media_utility/color_pipeline.py", "chemin fragile intact"),
    (
        "pyproject.toml",
        "la section [tool.mutmut] s'edite localement et ne se commite jamais "
        "scopee a une story",
    ),
)


# --------------------------------------------------------------------------
# Etage 1: la garde permanente, qui ne depend d'aucun historique
# --------------------------------------------------------------------------

#: Chaque interdit de l'AC 10, avec la **propriete de source** qui en porte la
#: substance et les motifs dont la presence la ferait tomber. Un chemin de
#: repertoire est parcouru recursivement.
_CONFINEMENT_DU_VOCABULAIRE: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "src/mixed_media_utility/layout.py",
        ("REFUS_", "refusal_code", "SCAN_REFUSAL_CODES"),
        "l'etat « marqueurs incomplets » n'a pas de producteur et cette story "
        "n'en cree pas (EPIC7-ARB-66, geste 3)",
    ),
    (
        "src/mixed_media_utility/io/payload.py",
        ("REFUS_", "refusal_code", "SCAN_REFUSAL_CODES"),
        "les exceptions etrangeres sont traduites au site de rattrapage, jamais "
        "amendees a la source",
    ),
    (
        "src/mixed_media_utility/page_templates.py",
        ("REFUS_", "refusal_code", "SCAN_REFUSAL_CODES"),
        "les exceptions etrangeres sont traduites au site de rattrapage, jamais "
        "amendees a la source",
    ),
    (
        "src/mixed_media_utility/scan_ingest.py",
        ("REFUS_", "refusal_code", "SCAN_REFUSAL_CODES"),
        "les exceptions etrangeres sont traduites au site de rattrapage, jamais "
        "amendees a la source",
    ),
    (
        "src/mixed_media_utility/color_calibration.py",
        ("REFUS_", "refusal_code", "SCAN_REFUSAL_CODES"),
        "chemin fragile intact",
    ),
    (
        "src/mixed_media_utility/color_pipeline.py",
        ("REFUS_", "refusal_code", "SCAN_REFUSAL_CODES"),
        "chemin fragile intact",
    ),
    (
        "src/mixed_media_utility/gui/",
        ("SCAN_REFUSAL_CODES", "validate_refusal_code"),
        "7.4 est `done` et son repli est permanent: l'ecran lit le code sans se "
        "cabler au vocabulaire ferme du coeur, sans quoi une version ulterieure "
        "du logiciel rendrait tout un scan illisible sur un champ informatif",
    ),
)


def _sources_sous(chemin: str) -> list[Path]:
    """Le fichier vise, ou tous les `.py` du repertoire vise, jamais rien."""
    cible = REPO_ROOT / chemin
    fichiers = sorted(cible.rglob("*.py")) if cible.is_dir() else [cible]
    assert fichiers, f"{chemin} n'existe pas: la garde ne mesurerait rien"
    return fichiers


@pytest.mark.parametrize(
    "chemin, motifs, motif_de_l_interdit",
    _CONFINEMENT_DU_VOCABULAIRE,
    ids=[chemin for chemin, _m, _r in _CONFINEMENT_DU_VOCABULAIRE],
)
def test_le_vocabulaire_de_refus_ne_deborde_d_aucun_module_interdit(
    chemin, motifs, motif_de_l_interdit
) -> None:
    """AC 10, etage permanent: la substance de l'interdit, pas la trace du diff.

    Ne depend d'aucun historique: un squash-merge, un rebase, un `git archive`
    ou un clone superficiel ne peuvent pas la rendre vacante (`BH-9`).
    """
    fautifs = [
        f"{fichier.relative_to(REPO_ROOT).as_posix()}:{numero}: {motif}"
        for fichier in _sources_sous(chemin)
        for numero, ligne in enumerate(
            fichier.read_text(encoding="utf-8").splitlines(), start=1
        )
        for motif in motifs
        if motif in ligne
    ]
    assert fautifs == [], f"{chemin} -- {motif_de_l_interdit}"


def test_la_garde_permanente_mord_la_ou_le_vocabulaire_vit_vraiment() -> None:
    """Le second volet: la garde **trouve** quand il y a a trouver.

    Sans lui, une faute de motif (`REFUSE_` pour `REFUS_`) ou une lecture de
    fichier muette rendrait les sept parametrages ci-dessus verts et vides --
    exactement le defaut que `BH-9` reproche a la forme git.
    """
    motifs = ("REFUS_", "refusal_code", "SCAN_REFUSAL_CODES")
    # `scan_detection` **declare** le vocabulaire: les trois motifs y sont.
    detection = (
        REPO_ROOT / "src/mixed_media_utility/scan_detection.py"
    ).read_text(encoding="utf-8")
    trouves = {motif for motif in motifs if motif in detection}
    assert trouves == set(motifs), (
        "le module qui declare le vocabulaire ne porte pas les motifs cherches: "
        "la garde cherche des chaines que le depot n'ecrit pas, elle ne mesure "
        f"rien. Manquants: {sorted(set(motifs) - trouves)}"
    )
    # `scan_previz` le **transporte**: il nomme le champ et valide contre le
    # tuple ferme, sans redeclarer aucune constante -- c'est bien deux roles
    # differents, et la garde distingue les deux.
    previz = (
        REPO_ROOT / "src/mixed_media_utility/scan_previz.py"
    ).read_text(encoding="utf-8")
    assert "refusal_code" in previz and "SCAN_REFUSAL_CODES" in previz
    assert "REFUS_" not in previz, (
        "le vocabulaire est declare dans un seul module (EPIC7-ARB-66)"
    )
    # Et la garde du repertoire ne se contente pas d'un fichier: `gui/` en
    # porte plusieurs, et la GUI nomme bien le champ (cle gelee de 7.4).
    fichiers_gui = _sources_sous("src/mixed_media_utility/gui/")
    assert len(fichiers_gui) > 1
    assert any(
        "refusal_code" in fichier.read_text(encoding="utf-8")
        for fichier in fichiers_gui
    ), "l'ecran de 7.4 nomme le champ: si plus personne ne le nomme, la cle a bouge"


def test_la_section_mutmut_est_restee_generique() -> None:
    """AC 10, l'interdit `pyproject.toml`, mesure sur son contenu.

    L'interdit ne porte pas sur le fichier -- il vit dans le depot -- mais sur
    l'etat dans lequel il est commite: une campagne scope `[tool.mutmut]` aux
    fichiers de la story, et cette version scopee ne doit jamais atteindre un
    commit (CLAUDE.md, « Travail en parallele sur la meme branche »).
    """
    import tomllib

    section = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["tool"]["mutmut"]
    assert section["source_paths"] == ["src/mixed_media_utility"]
    assert section["pytest_add_cli_args_test_selection"] == ["tests/unit"]


# --------------------------------------------------------------------------
# Etage 2: le releve git, plus fin -- et qui se declare inapplicable
# --------------------------------------------------------------------------


def _fichiers_des_commits_de_la_story() -> list[str]:
    """Les chemins touches par les commits de 5.27, ou echec nomme.

    Un `skip` se lirait comme un vert dans le total: si git est absent ou le
    baseline inatteignable, la frontiere ne s'evalue pas et il faut le dire.
    """
    import subprocess

    try:
        sortie = subprocess.run(
            [
                "git", "log", "--name-only", "--format=%x00%s",
                f"{_BASELINE_5_27}..HEAD",
            ],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=60,
        ).stdout
    except (subprocess.SubprocessError, OSError) as error:
        echoue_ou_saute(
            REPO_ROOT, _BASELINE_5_27,
            f"commit de reference {_BASELINE_5_27} inatteignable ({error}): la "
            "frontiere de perimetre ne s'evalue pas, et un skip se lirait comme "
            "un vert. Arbre exporte, historique tronque ou clone superficiel "
            "(`git fetch --unshallow`)"
        )
    chemins: list[str] = []
    a_moi = False
    for ligne in sortie.splitlines():
        if ligne.startswith("\x00"):
            a_moi = ligne[1:].startswith(_PREFIXE_5_27)
            continue
        if a_moi and ligne.strip():
            chemins.append(ligne.strip())
    return chemins


def _releve_git_ou_skip() -> list[str]:
    """Le releve, ou un `skip` **nomme** -- jamais un vert vide (`BH-9`).

    Deux causes se ressemblent et n'ont pas le meme verdict:

    * git absent ou baseline inatteignable: la mesure **aurait du** s'evaluer,
      donc `pytest.fail` (dans `_fichiers_des_commits_de_la_story`);
    * git present, baseline atteint, mais plus aucun commit du sujet dans la
      plage: la story a ete **squashee a la fusion**, ou l'historique reecrit.
      La mesure n'est plus applicable, definitivement, et le dire est le seul
      verdict honnete. La garantie de l'AC 10, elle, n'est pas perdue: elle est
      portee par la garde permanente de l'etage 1, qui ne depend pas de git.

    Ce que ce repli remplace, et c'est le finding: sans lui, les neuf
    parametrages de `test_les_chemins_interdits_restent_hors_du_diff`
    passaient au vert **sur une liste vide** des le squash-merge.
    """
    chemins = _fichiers_des_commits_de_la_story()
    if not chemins:
        pytest.skip(
            f"aucun commit de sujet {_PREFIXE_5_27!r} dans "
            f"{_BASELINE_5_27}..HEAD: historique squashe, rebase ou reecrit. Le "
            "releve git de l'AC 10 n'est plus applicable -- la substance des "
            "interdits reste mesuree par "
            "`test_le_vocabulaire_de_refus_ne_deborde_d_aucun_module_interdit`, "
            "qui ne depend d'aucun historique"
        )
    return chemins


def test_la_story_ne_touche_aucun_module_de_production_hors_de_son_perimetre() -> None:
    """AC 10, frontiere de perimetre sur le diff de production de la story."""
    chemins = _releve_git_ou_skip()
    production = {chemin for chemin in chemins if chemin.startswith("src/")}
    assert production == set(_PRODUCTION_5_27), {
        "en trop": sorted(production - _PRODUCTION_5_27),
        "annonces et non touches": sorted(_PRODUCTION_5_27 - production),
    }


@pytest.mark.parametrize(
    "interdit, motif", _INTERDITS_5_27, ids=[i for i, _m in _INTERDITS_5_27]
)
def test_les_chemins_interdits_restent_hors_du_diff(interdit, motif) -> None:
    chemins = _releve_git_ou_skip()
    fautifs = [chemin for chemin in chemins if chemin.startswith(interdit)]
    assert fautifs == [], f"{interdit} doit rester hors du diff -- {motif}"


def test_la_frontiere_de_perimetre_mord_dans_les_deux_sens() -> None:
    """Le second volet: la frontiere **echoue** quand elle doit.

    Une comparaison d'ensembles devenue une inclusion, ou dont le membre de
    gauche serait vide, passerait le test precedent sans rien garantir -- c'est
    le motif « un test peut etre vert et vide » que ce depot a paye trois fois.

    Ce test s'ouvrait sur deux assertions portant sur `_PRODUCTION_5_27`, une
    constante litterale de ce fichier: vraies quel que soit l'etat du depot,
    donc de la meme famille que le test tautologique paye en 5.9. Elles sont
    retirees (finding `F3`); la mesure qui suit, elle, mord.
    """
    # Le releve reel est bien ce qui est confronte, pas un ensemble vide.
    chemins = _releve_git_ou_skip()
    assert any(chemin.startswith("src/") for chemin in chemins)
    # Le filtre par sujet **selectionne** vraiment: l'historique depuis le
    # baseline porte aussi les commits des deux autres agents, et ceux-la ne
    # doivent pas entrer dans le releve.
    import subprocess

    tous = subprocess.run(
        ["git", "log", "--name-only", "--format=", f"{_BASELINE_5_27}..HEAD"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=60,
    ).stdout.split()
    assert set(chemins) < set(tous), (
        "le filtre par sujet ne retient pas moins que l'historique complet: il "
        "ne filtre donc rien, et la frontiere est vide de sens"
    )
