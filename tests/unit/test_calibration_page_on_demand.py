"""Story 5.22, tache 3: la page de calibration generee a la demande (AC 8).

`EPIC5-ARB-80` decision 7 retire l'insertion automatique de la page de
calibration a l'index 0 de chaque lot. Ce fichier porte les trois volets de
l'AC 8:

* la **frontiere negative** -- un lot compose apres cette story ne contient plus
  de page de role `c` inseree automatiquement;
* la **generation a la demande** -- la commande dediee produit une page de
  calibration seule, de role `c`, avec son treillis et son QR, telle que
  `scan calibrate` peut la lire. Le « telle que » est verifie de bout en bout par
  les vrais producteurs: composition -> raster synthetise -> ingestion 5.1 ->
  `detect_lot_pages` -> `cli._read_calibration_pages`, et non par une inspection
  du plan, qui ne prouverait rien sur ce que le scan retrouve;
* la **non-regression de pagination** des planches d'images, verifiee ici par la
  reconstruction (l'espace d'index du lot est celui que `missing_pages` decrit),
  et dans `test_pdf_composition` / `test_makepdf_command` sur les cardinaux.

Regle des fabriques (CLAUDE.md) appliquee partout ou une collection intervient:
le manifest de reference porte **deux lots distinguables** (deux cadences, donc
deux `lot_id` et deux cardinaux de frames), et le lot vise dans les tests
d'appariement n'est **jamais** le premier de la liste -- un `find` fautif qui
rendrait toujours le premier lot ne se demasque pas autrement.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import (  # noqa: E402
    cli,
    page_roles,
    page_templates,
    patch_presets,
    pdf_composition,
    scan_detection,
)
from mixed_media_utility.io import naming, reconstruction  # noqa: E402
from mixed_media_utility.io import payload as payload_io  # noqa: E402
from mixed_media_utility.io.payload import PayloadValidationError  # noqa: E402

import test_scan_detection as detection_fixtures  # noqa: E402

#: Les deux cadences du manifest de reference. **Deux et non une**: une fabrique
#: mono-lot rendrait invisible un appariement lot -> page qui rendrait toujours le
#: premier, et c'est litteralement le mutant `M25` de la story 5.7.
FPS_PREMIER = 5.0
FPS_VISE = 12.5

PROJECT_ID = "proj-ondemand"
RUSH_ID = "rush-ondemand"


def _manifest_deux_lots() -> dict:
    """Un manifest a **deux** lots distinguables, le lot vise en seconde position.

    Les deux lots partagent leur rush et divergent par leur cadence, donc par leur
    `lot_id`, leur `frames_dir` et leur cardinal de frames attendu: c'est le cas
    nominal v2.1 (deux tirages du meme rush a deux cadences) et c'est la
    configuration sous laquelle un `_find_entry` fautif se voit.
    """
    def lot(fps: float, source_frame_count: int) -> dict:
        lot_id = naming.build_lot_id(RUSH_ID, fps)
        return {
            "lot_id": lot_id,
            "rush_id": RUSH_ID,
            "state": "extraction",
            "fps_target": fps,
            "fps_target_exact": f"{int(fps * 2)}/2",
            # Story 2.7 (payload 2.1): requis par `_lot_identity` pour composer. Les
            # deux lots partagent le meme rush, donc la meme cadence source physique
            # (`fps_source = 25.0` ci-dessous) -- ce n'est pas le champ que ce fichier
            # teste par appariement (c'est `fps_target`/`lot_id`, deja distinguables
            # par lot, regle des fabriques).
            "timecode_base_fps": "25/1",
            "expected_frame_count": int(source_frame_count * fps // 25),
            "frames_dir": (f"frames/{naming.derive_short_id(RUSH_ID)}_"
                           f"{naming.format_fps_short(fps)}"),
            "source_frame_count": source_frame_count,
            "source_frame_count_is_exact": True,
            "rounding_policy": "floor",
        }

    return {
        "schema_version": "2.1",
        "project_id": PROJECT_ID,
        "created": "2026-08-17T00:00:00Z",
        "rushes": [
            {
                "rush_id": RUSH_ID,
                "source_name": f"{RUSH_ID}.mov",
                "fps_source": 25.0,
                "fps_source_exact": "25/1",
                "resolution_source": {"width": 1920, "height": 1080},
            }
        ],
        # Le lot **vise** est le second: voir la docstring de module.
        "lots": [lot(FPS_PREMIER, 50), lot(FPS_VISE, 80)],
        "artifacts": {"frames_dir": "frames"},
        "color": {"target_colorspace": "rec709"},
        "video": {},
        "reconstruction": {},
    }


def _lot_id_vise() -> str:
    return naming.build_lot_id(RUSH_ID, FPS_VISE)


def _compose_lot(**kwargs):
    return pdf_composition.compose_lot_plan(
        manifest=_manifest_deux_lots(), lot_id=_lot_id_vise(), **kwargs)


#: **Deux chaines de scan distinguables**, regle des fabriques. Un projet en porte
#: desormais autant que de chaines (correction d'Egan du 2026-08-18): une fabrique
#: mono-chaine rendrait invisible un nom de fichier ou un QR qui ignorerait le libelle.
#: La seconde n'est pas une variante typographique de la premiere: autre marque, autre
#: format, autre resolution.
CHAINE_VISEE = "hp envy 4520 tiff 600 dpi auto corr off"
AUTRE_CHAINE = "epson v600 tiff 48 bits 1200 dpi corr auto off"

#: Date de generation **figee**: elle s'imprime, donc elle entre dans la composition,
#: et une horloge rendrait le plan different a chaque execution.
DATE_GENERATION = date(2026, 8, 18)


def _compose_calibration(**kwargs):
    """Le plan de la page de calibration, **sans lot** (story 5.23).

    `--rush`, `--fps` et `--lot` ne sont plus requis: une page de calibration se genere
    avant toute extraction. Le libelle de chaine, lui, est obligatoire.
    """
    kwargs.setdefault("scan_chain_label", CHAINE_VISEE)
    kwargs.setdefault("generated_on", DATE_GENERATION)
    return pdf_composition.compose_calibration_page_plan(
        manifest=_manifest_deux_lots(), **kwargs)


# ---------------------------------------------------------------------------
# AC 8, volet 1: frontiere negative -- plus aucune page de role `c` dans un lot
# ---------------------------------------------------------------------------


def test_a_composed_lot_carries_no_automatically_inserted_calibration_page() -> None:
    """Aucune page de role `c` ne sort du plan de lot par defaut.

    La frontiere porte sur le **role declare au QR** et non sur « la page n'a pas de
    frame »: c'est le role que le scan lit, donc c'est le role qui decide si une
    feuille sera traitee comme page de calibration. Une page sans frame dont le QR
    declarerait `i` passerait un test pose sur les frames seules.
    """
    plan = _compose_lot()
    roles = [page.qr.payload["page_role"] for page in plan.pages]
    assert roles, "un lot compose porte au moins une planche"
    assert page_roles.PAGE_ROLE_CALIBRATION not in roles, roles
    assert set(roles) == {page_roles.PAGE_ROLE_IMAGES}
    # Et le cardinal: `page_count` ne compte plus que les planches d'images.
    frames_attendues = _manifest_deux_lots()["lots"][1]["expected_frame_count"]
    assert plan.page_count == -(-frames_attendues // plan.frames_per_page)
    assert len(plan.pages) == plan.page_count
    for page in plan.pages:
        assert page.frames, "une planche d'images porte au moins une frame"


def test_the_lot_plan_never_declares_a_page_count_that_counts_a_calibration_page() -> None:
    """Le `page_count` du QR de **chaque** planche vaut le cardinal des planches.

    C'est la propriete que la reconstruction consomme: `page_count` est de niveau
    lot (`io.reconstruction._LOT_LEVEL_FIELDS`), donc une planche qui declarerait
    l'ancien cardinal (planches + 1) rendrait le lot eternellement `partial`, avec
    une page manquante que personne n'a imprimee.
    """
    plan = _compose_lot()
    for page in plan.pages:
        assert page.qr.payload["page_count"] == plan.page_count
    section = reconstruction.reconstruct_project_manifest(
        [page.qr.payload for page in plan.pages])["reconstruction"]
    assert section["status"] == "complete", section
    assert "missing_pages" not in section, section


# ---------------------------------------------------------------------------
# AC 8, volet 2: la page seule, generee a la demande
# ---------------------------------------------------------------------------


def test_the_on_demand_page_is_a_single_calibration_page_with_lattice_and_qr() -> None:
    """Une page, de role `c`, avec son treillis et son QR autoportant."""
    plan = _compose_calibration()
    assert plan.page_count == pdf_composition.CALIBRATION_ONLY_PAGE_COUNT == 1
    assert len(plan.pages) == 1
    page = plan.pages[0]
    assert page.page_index == pdf_composition.CALIBRATION_PAGE_INDEX == 0
    assert page.frames == ()
    assert page.qr.payload["page_role"] == page_roles.PAGE_ROLE_CALIBRATION
    assert page.qr.payload["page_count"] == 1
    assert page.qr.payload["slots"] == []
    # Le treillis vient du **role**, jamais du preset du lot: c'est la propriete de
    # 5.16 (AC 3) que le deplacement de la page ne doit pas perdre.
    # **Amende par la story 5.23** (AC 1): la page porte desormais son treillis **et** le
    # bandeau de temoins du lot, pose par le mecanisme de bordure existant depuis le meme
    # preset que les planches d'images -- sans quoi les deux feuilles n'ont aucun
    # identifiant de valeur en commun et la mesure brute a brute n'a rien a apparier. La
    # propriete de 5.16 est conservee telle quelle: le **treillis** vient du role, jamais
    # du preset, et c'est ce que la premiere egalite dit toujours.
    assert page.patches[:len(patch_presets.resolve_calibration_page_patches(
        plan.template_id))] == patch_presets.resolve_calibration_page_patches(
        plan.template_id)
    assert page.patches == (
        patch_presets.resolve_calibration_page_patches(plan.template_id)
        + patch_presets.resolve_calibration_page_witnesses(
            plan.template_id, plan.patch_preset_id))
    assert len(page.patches) == patch_presets.calibration_page_patch_count(
        plan.patch_preset_id)
    assert (len(page.patches) - len(patch_presets.resolve_calibration_page_witnesses(
        plan.template_id, plan.patch_preset_id))
        == patch_presets.calibration_lattice_patch_count())
    assert len(page.markers) == 4


def test_the_on_demand_page_resolves_its_geometry_from_the_options_not_from_a_lot() -> None:
    """Le gabarit **suit les options**, et il ne vient pas d'un lot (story 5.23).

    C'est ce qui rend la page scannable: `scan calibrate` resout le treillis depuis le
    `template_id` du QR. Composer la page sous un gabarit et scanner sous un autre
    echantillonnerait les pastilles a cote -- silencieusement.

    AMENDE PAR 5.23: la page se compose **sans lot**, et le fait qu'elle rende le meme
    gabarit qu'un lot compose avec les memes options est desormais une **consequence**
    -- les deux points d'entree appellent `_resolve_parameters`, qui ne lit pas le
    manifest -- et non un couplage. Le test est conserve tel quel parce que c'est
    precisement cette egalite qui doit continuer de tenir: elle est ce qui garantit
    qu'une chaine calibree sous un gabarit scanne les planches du meme.

    Les deux regimes sont mesures (defaut et option explicite) parce qu'un
    `template_id` pose en litteral passerait le premier et pas le second.
    """
    defaut = _compose_calibration()
    assert defaut.template_id == _compose_lot().template_id
    assert defaut.pages[0].qr.payload["template_id"] == defaut.template_id

    paysage = _compose_calibration(orientation="paysage", frames_per_page=4)
    assert paysage.template_id == _compose_lot(
        orientation="paysage", frames_per_page=4).template_id
    assert paysage.template_id != defaut.template_id, (
        "temoin negatif: sans lui, un template_id pose en litteral passerait")
    assert paysage.pages[0].qr.payload["template_id"] == paysage.template_id


def test_the_file_name_carries_the_project_and_the_chain_and_separates_two_chains() -> None:
    """Un projet porte **autant** de pages de calibration que de chaines de scan.

    AMENDE DEUX FOIS, et le chemin explique la propriete. La redaction de 5.22 nommait
    le fichier `<projet>_<rush>_<lot>_calibration.pdf` -- reste du regime par lot. Le
    2026-08-17 l'AC 8bis en a retire le rush et le lot, ce qui a produit
    `<projet>_calibration.pdf`, et Egan a corrige le lendemain: ce nom-la n'autorise
    qu'**une** page par projet, donc calibrer une seconde chaine exigerait d'ecraser la
    premiere.

    La propriete exigee est donc l'**injectivite** sur le libelle, et c'est la classe de
    defaut la plus payee du depot (collision d'identite). Elle est verifiee sur deux
    libelles distinguables **et** sur deux libelles qui se normalisent en un meme slug:
    c'est ce second couple qui tue une recette qui n'utiliserait que le slug.
    """
    plan = _compose_calibration()
    autre = _compose_calibration(scan_chain_label=AUTRE_CHAINE)

    # Deux chaines distinguables -> deux fichiers distincts.
    assert plan.pdf_filename != autre.pdf_filename
    assert plan.pdf_filename == naming.build_calibration_pdf_filename(
        PROJECT_ID, CHAINE_VISEE)
    # Le projet et un fragment lisible de la chaine sont dans le nom: un condensat seul
    # ne se distinguerait de son voisin qu'en ouvrant les deux fichiers.
    assert PROJECT_ID in plan.pdf_filename
    assert "hp-envy-4520" in plan.pdf_filename

    # Deux libelles qui se **normalisent pareil** restent deux fichiers: c'est le
    # condensat, calcule sur le libelle brut, qui les separe. Sans lui, `normalize_
    # identifier` etant non injective, le second ecraserait le premier en silence.
    espaces = _compose_calibration(scan_chain_label="hp envy 4520")
    tirets = _compose_calibration(scan_chain_label="hp-envy 4520")
    assert espaces.pdf_filename != tirets.pdf_filename, (
        espaces.pdf_filename, tirets.pdf_filename)

    # Ni rush, ni lot: ils n'ont jamais decrit cette feuille.
    assert _lot_id_vise() not in plan.pdf_filename
    assert RUSH_ID not in plan.pdf_filename
    # Le suffixe reste distinct de celui des planches: les deux PDF coexistent dans
    # `planches/`, et un nom partage en ferait ecraser un par l'autre en silence.
    assert plan.pdf_filename != naming.build_sheets_pdf_filename(
        PROJECT_ID, RUSH_ID, _lot_id_vise(),
        template_id=plan.template_id)


def test_the_payload_declares_the_chain_and_nothing_that_ties_the_sheet_to_a_project() -> None:
    """Le QR: le libelle de chaine **oui**, projet / rush / lot / cadence **non**.

    Verifie par **egalite d'ensembles de cles** et non par absence d'une seule: une cle
    oubliee doit faire echouer ce test.

    Le retrait de `project_id` est la precision d'Egan du 2026-08-18 -- « on peut
    utiliser la page d'un autre projet dans un projet donne, cela ne doit pas donner
    lieu a un refus ». Une page et un profil appartiennent a une **chaine de scan**; le
    projet n'est qu'un lieu de rangement. Un champ de projet dans la charge utile
    inviterait une garde future a le comparer, et cette garde refuserait exactement le
    geste qu'Egan autorise.
    """
    payload = _compose_calibration().pages[0].qr.payload
    assert set(payload) == {
        "schema_version", "page_index", "page_count", "page_role",
        "template_id", "patch_preset_id", "target_colorspace", "gamut_map_id",
        "slots", "scan_chain_label",
    }, sorted(payload)
    assert payload["scan_chain_label"] == CHAINE_VISEE
    # Frontiere negative sur le **texte serialise**, qui est ce que le papier porte:
    # le projet n'y est ni sous sa cle longue, ni sous sa cle courte, ni en valeur.
    texte = _compose_calibration().pages[0].qr.payload_text
    assert PROJECT_ID not in texte, texte
    assert RUSH_ID not in texte, texte


def _lignes(plan) -> list[str]:
    """Les lignes reellement imprimees dans l'entete de la page."""
    blocs = plan.pages[0].text.blocks
    assert len(blocs) == 1, blocs
    return list(blocs[0].lines)


def test_the_sheet_prints_the_five_mentions_and_none_of_the_three_that_were_false() -> None:
    """Les mentions d'Egan, et **le retrait** des trois qui etaient fausses.

    L'entete portait `lot_id`, « page 1/1 » et une cadence. Les trois sont faux au sens
    propre sur cette feuille: elle sert toute une chaine de scan, elle n'a qu'une page,
    elle ne porte aucune frame donc aucune cadence. Le QR avait ete epure le 2026-08-17
    (AC 8bis); l'imprime l'est ici.

    La verification porte sur le texte **concatene** des lignes reellement posees dans
    le plan, et non sur une ligne en particulier: la repartition en lignes depend de la
    largeur de la bande, donc un test pose ligne par ligne serait faux au premier
    changement de gabarit sans qu'aucune mention n'ait bouge.
    """
    plan = _compose_calibration(comment="vitre nettoyee, lampe froide")
    texte = " ".join(_lignes(plan))

    assert PROJECT_ID in texte
    assert CHAINE_VISEE in texte
    assert pdf_composition.CALIBRATION_SHEET_MENTION in texte
    assert pdf_composition.CALIBRATION_USAGE_MENTION in texte
    assert "vitre nettoyee, lampe froide" in texte
    assert DATE_GENERATION.isoformat() in texte

    # Frontiere negative: les trois mentions retirees, sur le texte complet.
    assert _lot_id_vise() not in texte, texte
    assert RUSH_ID not in texte, texte
    assert "page 1/1" not in texte, texte
    assert "im/s" not in texte, texte
    assert str(FPS_VISE) not in texte, texte
    # Le commentaire est **facultatif**: sans lui, la mention n'est pas imprimee vide.
    assert pdf_composition.CALIBRATION_COMMENT_PREFIX not in " ".join(
        _lignes(_compose_calibration()))


def test_the_date_is_printed_only_and_never_enters_any_identity() -> None:
    """La date **s'imprime** et n'entre ni dans le QR ni dans le nom du fichier.

    `io.naming` interdit l'horodate dans tout ce qui est condense ou compare: deux
    generations de la **meme** page produiraient sinon deux identites, et la feuille
    reimprimee cesserait d'etre la meme feuille. Le test l'epingle par les deux bouts --
    la date est bien la sur le papier, et bien absente des deux identites -- et sur
    **deux dates distinctes**, sans quoi une recette qui ignorerait le parametre
    passerait.
    """
    hier = _compose_calibration(generated_on=date(2026, 8, 17))
    aujourdhui = _compose_calibration(generated_on=date(2026, 8, 18))

    assert "2026-08-17" in " ".join(_lignes(hier))
    assert "2026-08-18" in " ".join(_lignes(aujourdhui))

    # Deux dates, une seule identite: c'est la propriete de determinisme.
    assert hier.pdf_filename == aujourdhui.pdf_filename
    assert hier.pages[0].qr.payload_text == aujourdhui.pages[0].qr.payload_text
    for plan, jour in ((hier, "2026-08-17"), (aujourdhui, "2026-08-18")):
        assert jour not in plan.pages[0].qr.payload_text
        assert jour not in plan.pdf_filename
        assert "2026" not in plan.pdf_filename


def test_the_comment_is_printed_and_never_enters_the_payload() -> None:
    """Le commentaire est **de la prose pour le lecteur humain**: il ne va pas au QR.

    Frontiere negative exercee avec un commentaire **reellement fourni** -- un test a
    commentaire vide ne prouverait rien (`EPIC5-ARB-39`) -- et sur le **texte serialise**
    du payload, qui est ce que le papier porte, plutot que sur les cles du dict.

    Le libelle de chaine, lui, y est: c'est la dissymetrie qu'Egan a tranchee le
    2026-08-18, et elle a un motif operationnel -- `scan ... calibrate` pourra relire le
    libelle depuis la feuille au lieu de le faire ressaisir, alors qu'il n'a rien a
    faire d'un commentaire.
    """
    commentaire = "profil verifie le 18 aout, pilote 3.2.1"
    plan = _compose_calibration(comment=commentaire)
    assert commentaire in " ".join(_lignes(plan))
    texte = plan.pages[0].qr.payload_text
    assert commentaire not in texte, texte
    assert "profil verifie" not in texte, texte
    assert "scan_chain_label" not in texte  # cle courte a l'impression
    assert CHAINE_VISEE in texte
    # Et il n'entre pas non plus dans le nom du fichier: deux commentaires differents
    # sur la meme chaine designent la meme feuille.
    assert plan.pdf_filename == _compose_calibration(
        comment="autre commentaire entierement different").pdf_filename


def test_the_maximum_lengths_are_pinned_at_both_ends() -> None:
    """Le couple (libelle, commentaire) tient la bande d'entete, et un cran de plus non.

    Une longueur maximale annoncee sans son point de rupture n'est pas une garantie:
    elle est epinglee **par les deux bouts**, sur le pire cas adversarial -- les deux
    mentions **sans aucune espace**, donc insecables, et un `project_id` de la longueur
    maximale que le schema autorise.
    """
    manifest = _manifest_deux_lots()
    manifest["project_id"] = "p" * naming.CANONICAL_ID_MAX_LENGTH

    def compose(longueur_chaine: int, longueur_commentaire: int):
        return pdf_composition.compose_calibration_page_plan(
            manifest=manifest,
            scan_chain_label="x" * longueur_chaine,
            comment="y" * longueur_commentaire,
            generated_on=DATE_GENERATION,
        )

    maxi_chaine = payload_io.SCAN_CHAIN_LABEL_MAX_LENGTH
    maxi_commentaire = pdf_composition.SCAN_CHAIN_COMMENT_MAX_LENGTH
    # Le maximum passe...
    plan = compose(maxi_chaine, maxi_commentaire)
    assert len(_lignes(plan)) == page_templates.calibration_header_line_count(
        plan.orientation)
    # ... et les deux debordements sont refuses **avant** la composition, chacun par le
    # contrat qui le possede: le libelle par le contrat 2.3 (il voyage dans le QR), le
    # commentaire par la composition (il ne voyage nulle part).
    with pytest.raises(PayloadValidationError):
        compose(maxi_chaine + 1, maxi_commentaire)
    with pytest.raises(pdf_composition.ParameterVocabularyError):
        compose(maxi_chaine, maxi_commentaire + 1)

    # Et le **point de rupture typographique** lui-meme, mesure sur le repartiteur: un
    # caractere de plus sur l'une ou l'autre mention exige une sixieme ligne, que le
    # portrait ne finance pas. Sans ce volet, les deux refus ci-dessus prouveraient
    # seulement que deux constantes existent, pas qu'elles sont **les bonnes**.
    grille = page_templates.get_geometry("v2").calibration_grid(
        page_templates.ORIENTATION_PORTRAIT, patch_presets.CALIBRATION_PATCH_SIZE_MM)
    largeur = grille.header_zone_mm()[2]

    def lignes(longueur_chaine: int, longueur_commentaire: int) -> int:
        segments = [
            "p" * naming.CANONICAL_ID_MAX_LENGTH,
            pdf_composition.CALIBRATION_CHAIN_PREFIX + "x" * longueur_chaine,
            pdf_composition.CALIBRATION_SHEET_MENTION,
            pdf_composition.CALIBRATION_USAGE_MENTION,
            pdf_composition.CALIBRATION_DATE_PREFIX + DATE_GENERATION.isoformat(),
            pdf_composition.CALIBRATION_COMMENT_PREFIX + "y" * longueur_commentaire,
        ]
        return len(pdf_composition._wrap_verbatim(
            segments, largeur, pdf_composition.BODY_FONT_MIN_PT))

    budget = page_templates.calibration_header_line_count(
        page_templates.ORIENTATION_PORTRAIT)
    assert lignes(maxi_chaine, maxi_commentaire) == budget
    assert lignes(maxi_chaine, maxi_commentaire + 1) == budget + 1
    assert lignes(maxi_chaine + 8, maxi_commentaire) == budget + 1


def test_a_landscape_sheet_refuses_the_overflow_instead_of_truncating() -> None:
    """En paysage la grille ne finance qu'**une** rangee d'entete: le refus est chiffre.

    C'est la contrepartie assumee du budget par orientation. Une mention tronquee sur
    une feuille imprimee est indetectable apres coup; un refus qui nomme le nombre de
    lignes exigees, celui qu'il finance, et l'orientation qui en finance davantage est
    recuperable. Le temoin positif est dans le meme test: le cas nominal d'Egan passe
    en paysage, donc le refus n'est pas un refus general.
    """
    nominal = _compose_calibration(orientation="paysage", frames_per_page=4)
    assert len(_lignes(nominal)) <= page_templates.calibration_header_line_count(
        page_templates.ORIENTATION_PAYSAGE)

    with pytest.raises(pdf_composition.GeometryOverflowError) as refus:
        _compose_calibration(orientation="paysage", frames_per_page=4,
                             comment="un commentaire qui ne tient pas en paysage")
    motif = str(refus.value)
    assert "paysage" in motif and page_templates.ORIENTATION_PORTRAIT in motif, motif
    assert str(patch_presets.calibration_lattice_patch_count()) in motif, motif


def test_the_command_needs_neither_rush_nor_fps_nor_lot() -> None:
    """`--rush`, `--fps` et `--lot` ne sont plus requis (story 5.23).

    Une page de calibration se genere **avant tout lot**, avant toute extraction: c'est
    l'ordre de travail que la calibration par chaine rend possible, et l'exiger
    l'interdirait. Le test le mesure sur un manifest **sans aucun lot**, qui est
    litteralement l'etat d'un projet neuf -- une signature qui accepterait encore un lot
    optionnel passerait un test pose sur le manifest a deux lots.
    """
    manifest = _manifest_deux_lots()
    manifest["lots"] = []
    plan = pdf_composition.compose_calibration_page_plan(
        manifest=manifest, scan_chain_label=CHAINE_VISEE,
        generated_on=DATE_GENERATION)
    assert plan.page_count == 1
    assert plan.pages[0].qr.payload["page_role"] == page_roles.PAGE_ROLE_CALIBRATION
    # Et la feuille ne declare aucune identite de lot, ni dans le plan ni au QR.
    assert plan.lot_id == pdf_composition.CALIBRATION_NO_LOT == ""
    assert plan.rush_id == pdf_composition.CALIBRATION_NO_RUSH == ""


def test_an_anonymous_chain_is_refused() -> None:
    """Le libelle est **obligatoire**: une page anonyme ne se distingue pas d'une autre.

    Les deux formes du vide sont refusees, la chaine vide et la chaine blanche: un
    libelle de trois espaces produirait un nom de fichier sans fragment lisible et une
    mention imprimee vide, c'est-a-dire une feuille anonyme par un autre chemin.
    """
    for vide in ("", "   "):
        with pytest.raises(PayloadValidationError):
            _compose_calibration(scan_chain_label=vide)
    # Et le libelle est **rogne une fois**, avant l'impression, le QR et le nom: sans
    # cela, une espace de bord venue d'un copier-coller ferait deux fichiers pour une
    # seule chaine, et le QR ne dirait pas la meme chose que le papier.
    borde = _compose_calibration(scan_chain_label=f"  {CHAINE_VISEE}  ")
    propre = _compose_calibration(scan_chain_label=CHAINE_VISEE)
    assert borde.pdf_filename == propre.pdf_filename
    assert borde.pages[0].qr.payload["scan_chain_label"] == CHAINE_VISEE


# ---------------------------------------------------------------------------
# AC 8, volet 2 (suite): « telle que `scan calibrate` peut la lire »
# ---------------------------------------------------------------------------


def _synthesize(plan) -> np.ndarray:
    """Un raster de la page composee, par les **vrais** producteurs.

    Marqueurs de coin par `layout.generate_aruco_marker_image` et QR par
    `qr_codes`, aux positions du plan: c'est le seul niveau ou le decodage, la
    resolution de geometrie et le role existent reellement. Un plan inspecte en
    memoire ne dirait rien de ce que le scan retrouve.
    """
    page = plan.pages[0]
    return detection_fixtures._render_page(
        plan.template_id, page.qr.payload, dpi=detection_fixtures.SCAN_DPI)


def test_the_on_demand_page_is_read_back_as_the_calibration_page_of_the_scan(
        tmp_path: Path) -> None:
    """Bout en bout: la page generee est celle que `scan calibrate` va chercher.

    C'est le « telle que `scan calibrate` peut la lire » de l'AC 8, et il se mesure
    sur le predicat que la commande utilise reellement --
    `cli._read_calibration_pages` --, pas sur le role lu a la main. Les deux
    conditions de ce predicat (role declare **et** geometrie resolue) sont ainsi
    exercees ensemble.
    """
    plan = _compose_calibration()
    project_dir, ingested = detection_fixtures._ingest(
        tmp_path, [_synthesize(plan)], slug="chaine-0001")
    detection = scan_detection.detect_lot_pages(
        project_dir, ingested, dpi=detection_fixtures.SCAN_DPI)

    assert len(detection.pages) == 1
    page = detection.pages[0]
    assert page.status == scan_detection.PAGE_OK, page.status
    assert page.homography is not None
    assert page.payload is not None
    assert page.payload["page_role"] == page_roles.PAGE_ROLE_CALIBRATION
    assert page.payload["template_id"] == plan.template_id
    # AMENDE PAR 5.23 (AC 8bis): le payload d'une page de calibration ne porte plus
    # de lot. La propriete relue ici est donc l'ABSENCE, et elle est verifiee par
    # egalite d'ensembles plutot que clef par clef -- une clef oubliee doit faire
    # echouer ce test, pas passer inapercue.
    assert set(page.payload) & {
        "project_id", "rush_id", "lot_id", "fps_target"} == set(), sorted(page.payload)
    # Et la lecture aboutit quand meme: c'est tout l'enjeu, un acces nu a `rush_id`
    # dans `scan_detection` rendait cette page illisible sans message. `project_id` a
    # rejoint la liste le 2026-08-18 et le meme acces nu y attendait.
    assert page.rush_id is None
    assert page.lot_id is None
    assert page.project_id is None
    # Le libelle de la chaine, lui, **est** relu depuis la feuille: c'est le motif de
    # son entree dans le QR -- `scan ... calibrate` pourra le proposer a l'operateur au
    # lieu de le lui faire ressaisir.
    assert page.payload["scan_chain_label"] == CHAINE_VISEE

    # Le predicat de production, celui que `scan calibrate` appelle.
    lues = cli._read_calibration_pages(detection)
    assert len(lues) == 1
    assert lues[0].payload["page_role"] == page_roles.PAGE_ROLE_CALIBRATION
    # Et la geometrie que le scan resout est bien celle du gabarit declare: c'est ce
    # qui fait tomber les pastilles au bon endroit.
    spec = page_templates.get_template(page.payload["template_id"])
    assert spec.template_id == plan.template_id


def test_a_sheet_from_another_project_is_read_without_refusal_and_not_confused(
        tmp_path: Path) -> None:
    """Temoin negatif du predicat **et** page d'un autre projet, sur la meme pile.

    Deux proprietes sur un seul balayage, parce qu'elles portent sur le meme geste --
    une pile de feuilles heterogenes posee sur la vitre -- et parce qu'un second
    balayage de bout en bout couterait deux secondes au lot de la story (AC 9, plafond
    de 10 s).

    **Temoin negatif.** Sans lui, un predicat qui rendrait toutes les pages lues
    passerait le test precedent. La page de calibration est placee **en seconde
    position**: un predicat qui rendrait la premiere page de la pile -- l'ordre de
    lecture du scanner, que l'operateur ne controle pas -- se demasque ici et nulle part
    ailleurs.

    **Page d'un autre projet.** Precision d'Egan du 2026-08-18: « on peut utiliser la
    page d'un autre projet dans un projet donne. Cela ne doit pas donner lieu a un refus
    de calibration. » La page de calibration vient donc du projet A et la planche
    d'images du projet B -- **deux projets reellement distincts** --, et les deux se
    lisent sans refus. Ce qui rend la propriete vraie par construction plutot que par
    tolerance: le payload du role `c` ne porte plus de `project_id`, donc il n'y a rien
    a comparer.
    """
    projet_a = _manifest_deux_lots()
    projet_a["project_id"] = "projet-a-ailleurs"
    projet_b = _manifest_deux_lots()
    projet_b["project_id"] = "projet-b-ici"
    assert projet_a["project_id"] != projet_b["project_id"]

    calibration = pdf_composition.compose_calibration_page_plan(
        manifest=projet_a, scan_chain_label=CHAINE_VISEE,
        generated_on=DATE_GENERATION)
    lot = pdf_composition.compose_lot_plan(
        manifest=projet_b, lot_id=_lot_id_vise())
    pile = [
        detection_fixtures._render_page(
            lot.template_id, lot.pages[0].qr.payload,
            dpi=detection_fixtures.SCAN_DPI),
        _synthesize(calibration),
    ]
    project_dir, ingested = detection_fixtures._ingest(
        tmp_path, pile, slug="chaine-0002")
    detection = scan_detection.detect_lot_pages(
        project_dir, ingested, dpi=detection_fixtures.SCAN_DPI)

    assert len(detection.pages) == 2
    lues = cli._read_calibration_pages(detection)
    assert len(lues) == 1, [p.payload["page_role"] for p in detection.pages]
    assert lues[0].payload["page_role"] == page_roles.PAGE_ROLE_CALIBRATION
    assert lues[0].payload["page_count"] == 1
    assert lues[0].payload["scan_chain_label"] == CHAINE_VISEE
    # Aucun refus, et aucun message qui nomme un projet: frontiere negative de la
    # precision d'Egan.
    for page in detection.pages:
        assert page.status != scan_detection.PAGE_REFUSED, page.refusal_reason
        motif = page.refusal_reason or ""
        assert projet_a["project_id"] not in motif, motif
        assert projet_b["project_id"] not in motif, motif
    # La planche d'images de l'autre projet, elle, declare l'autre role, l'autre
    # cardinal, **et son projet**: l'epuration ne vaut que pour le role `c`. Sans ce
    # temoin positif, une epuration generale -- qui casserait la reconstruction --
    # passerait ce test.
    autres = [p for p in detection.pages if p not in lues]
    assert len(autres) == 1
    assert autres[0].payload["page_role"] == page_roles.PAGE_ROLE_IMAGES
    assert autres[0].payload["page_count"] == lot.page_count
    assert autres[0].payload["project_id"] == projet_b["project_id"]


# ---------------------------------------------------------------------------
# AC 8, volet 2 (suite): le geste CLI `makepdf ... calibration-page`
# ---------------------------------------------------------------------------


def _router(monkeypatch) -> dict:
    """Substituer les deux handlers de `makepdf` et capturer lequel est appele.

    Meme geste que `_capturer_args` de la tache 2: le parser est construit **dans**
    `cli.main` et n'est pas expose, donc le routage se mesure en interceptant les
    handlers plutot qu'en analysant un parser. Un `pytest.skip` aurait ete pire que
    rien ici -- un skip se lit comme un vert.
    """
    vus: dict = {}

    def faire(nom):
        def handler(args):
            vus["nom"] = nom
            vus["args"] = args
            return 0
        return handler

    monkeypatch.setattr(cli, "makepdf_command", faire("planches"))
    monkeypatch.setattr(
        cli, "makepdf_calibration_page_command", faire("calibration"))
    return vus


def test_the_subcommand_does_not_change_any_existing_makepdf_invocation(
        monkeypatch) -> None:
    """`makepdf` sans sous-commande garde **exactement** son handler.

    Le pattern est celui de `scan calibrate` (et de `poc` avant lui): un
    `add_subparsers` **non requis**. La compatibilite est un AC implicite de la story
    -- le tutoriel et les tests d'integration appellent `makepdf --project ...` --, et
    elle se mesure sur le handler reellement atteint, pas sur l'absence d'exception.
    """
    vus = _router(monkeypatch)
    assert cli.main(["makepdf", "--project", "p", "--lot", "l"]) == 0
    assert vus["nom"] == "planches"

    # AMENDE PAR 5.23: la sous-commande n'exige plus de lot, mais elle exige `--chaine`.
    vus.clear()
    assert cli.main(
        ["makepdf", "--project", "p", "calibration-page",
         "--chaine", CHAINE_VISEE]) == 0
    assert vus["nom"] == "calibration"
    assert vus["args"].chaine == CHAINE_VISEE
    assert vus["args"].commentaire is None

    # Les options de geometrie sont portees par le **parent** et donc partagees: c'est
    # ce qui interdit de composer la page sous un gabarit et les planches sous un autre.
    # `--chaine` et `--commentaire`, eux, sont portes par la **sous-commande**: ils n'ont
    # aucun sens sur un lot de planches, et les poser sur le parent les aurait rendus
    # acceptables la ou ils ne decrivent rien.
    vus.clear()
    assert cli.main(
        ["makepdf", "--project", "p", "--orientation", "paysage",
         "calibration-page", "--chaine", CHAINE_VISEE,
         "--commentaire", "vitre nettoyee"]) == 0
    assert vus["nom"] == "calibration"
    assert vus["args"].orientation == "paysage"
    assert vus["args"].commentaire == "vitre nettoyee"

    # Frontiere: une page anonyme n'est pas exprimable en ligne de commande.
    with pytest.raises(SystemExit):
        cli.main(["makepdf", "--project", "p", "calibration-page"])


def test_the_command_writes_the_page_under_patches_and_never_touches_the_manifest(
        tmp_path: Path, monkeypatch) -> None:
    """Le PDF sort sous `planches/`, et `project.json` est intact **a l'octet**.

    `lots[].state = "pdf"` declare que les **planches** du lot sont imprimees (story
    5.11, `EPIC5-ARB-20`): le declarer ici mentirait sur un lot dont aucune planche
    n'existe. L'egalite d'octets est la seule forme de cette promesse qui ne se
    contourne pas.
    """
    from mixed_media_utility.io import project_layout

    project_dir = tmp_path / "projet"
    project_layout.ensure_project_layout(project_dir)
    manifest = _manifest_deux_lots()
    manifest_path = project_dir / "project.json"
    import json as _json
    manifest_path.write_text(_json.dumps(manifest, indent=2), encoding="utf-8")
    avant = manifest_path.read_bytes()

    monkeypatch.chdir(tmp_path)
    code = cli.main([
        "makepdf", "--project", str(project_dir),
        "calibration-page", "--chaine", CHAINE_VISEE,
    ])
    assert code == 0

    attendu = naming.build_calibration_pdf_filename(PROJECT_ID, CHAINE_VISEE)
    pdf_path = project_dir / project_layout.PLANCHES_DIRNAME / attendu
    assert pdf_path.is_file(), sorted(
        p.name for p in (project_dir / project_layout.PLANCHES_DIRNAME).iterdir())
    # **Une** page dans le PDF: la page de calibration, et rien d'autre.
    data = pdf_path.read_bytes()
    assert data.count(b"/Type /Page") - data.count(b"/Type /Pages") == 1
    # Le manifest est intact a l'octet, et le PDF de planches n'existe pas.
    assert manifest_path.read_bytes() == avant
    assert not (project_dir / project_layout.PLANCHES_DIRNAME
                / naming.build_sheets_pdf_filename(
                    PROJECT_ID, RUSH_ID, _lot_id_vise(),
                    template_id=page_templates.build_template_id(
                        page_templates.ORIENTATION_PORTRAIT,
                        page_templates.DEFAULT_FRAMES_PER_PAGE,
                        page_templates.DEFAULT_MARGIN_PRESET))).exists()


def test_the_command_refuses_to_overwrite_without_being_asked(
        tmp_path: Path, monkeypatch) -> None:
    """Un PDF present n'est jamais remplace implicitement, et l'est avec `--overwrite`.

    Les deux volets sont mesures: sans le second, une garde posee sur « le fichier
    existe » et jamais levee passerait le premier.
    """
    from mixed_media_utility.io import project_layout

    project_dir = tmp_path / "projet"
    project_layout.ensure_project_layout(project_dir)
    import json as _json
    (project_dir / "project.json").write_text(
        _json.dumps(_manifest_deux_lots(), indent=2), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    parent = ["makepdf", "--project", str(project_dir)]
    argv = parent + ["calibration-page", "--chaine", CHAINE_VISEE]

    assert cli.main(argv) == 0
    pdf_path = (project_dir / project_layout.PLANCHES_DIRNAME
                / naming.build_calibration_pdf_filename(PROJECT_ID, CHAINE_VISEE))
    empreinte = pdf_path.read_bytes()
    assert cli.main(argv) == 1
    assert pdf_path.read_bytes() == empreinte, "le refus n'a rien touche"
    # `--overwrite` est une option du **parent**, donc elle se place avant la
    # sous-commande. C'est la contrainte du pattern de sous-parseurs, la meme que sur
    # `scan ... calibrate` (tache 2), et elle est deliberee: dupliquer les options sur
    # la sous-commande aurait rendu exprimable un desaccord entre les deux niveaux.
    assert cli.main(
        parent + ["--overwrite", "calibration-page", "--chaine", CHAINE_VISEE]) == 0
    # Et une **autre** chaine ne se heurte a aucun refus, sans `--overwrite`: les deux
    # pages coexistent, ce qui est la propriete que le nom porte desormais.
    assert cli.main(parent + ["calibration-page", "--chaine", AUTRE_CHAINE]) == 0
    autre = (project_dir / project_layout.PLANCHES_DIRNAME
             / naming.build_calibration_pdf_filename(PROJECT_ID, AUTRE_CHAINE))
    assert autre.is_file() and autre != pdf_path


def test_a_geometry_that_cannot_carry_the_lattice_is_refused_not_warned(
        tmp_path: Path, monkeypatch) -> None:
    """Sous la v1, la commande **echoue**; elle ne rend pas un PDF sans treillis.

    Tant que la page etait inseree dans le lot, ce constat devait rester un
    avertissement: refuser aurait fait perdre l'impression de tout le lot pour une
    page annexe. Maintenant que la page **est** le produit demande, un avertissement
    rendrait un PDF vide en annoncant un succes.
    """
    from mixed_media_utility.io import project_layout

    project_dir = tmp_path / "projet"
    project_layout.ensure_project_layout(project_dir)
    import json as _json
    (project_dir / "project.json").write_text(
        _json.dumps(_manifest_deux_lots(), indent=2), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert cli.main([
        "makepdf", "--project", str(project_dir),
        "--geometrie", "v1", "calibration-page", "--chaine", CHAINE_VISEE,
    ]) == 1
    # Rien n'a ete ecrit: un refus qui laisse un fichier derriere lui n'est pas un
    # refus.
    patches = project_dir / project_layout.PLANCHES_DIRNAME
    assert not any(p.suffix == ".pdf" for p in patches.iterdir())
    # Et le temoin positif, sur la meme fabrique: la v2 passe.
    assert cli.main([
        "makepdf", "--project", str(project_dir),
        "--geometrie", "v2", "calibration-page", "--chaine", CHAINE_VISEE,
    ]) == 0
