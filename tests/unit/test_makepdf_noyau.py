"""Banc du coeur de `makepdf` (story 11.7, lot B).

Ce fichier ne mesure pour l'instant que la tache **B4** -- le canal de
progression du rendu (AC 2.6). Les taches B1 a B3 et B5 a B7 -- le deplacement
du corps de `makepdf_command` vers un module de coeur -- viendront s'y ajouter ;
le nom du fichier est celui que la fiche de story lui a reserve.

**Ce que ce banc mesure, et pourquoi trois de ses frontieres sont NEGATIVES.**
Le contrat d'AC 2.6 est celui deja gele par `ecrire_le_lot_detecte` /
`write_lot_output_frames` : `rappel_progression` optionnel, un jalon **par page
reellement ecrite**, `total` valant `plan.page_count`, et **aucun jalon avant la
premiere page**. Les deux moities positives de ce contrat (« il y a des jalons »,
« ils vont jusqu'au bout ») se mesurent seules ; les deux moities negatives --
« aucun jalon quand un refus dur precede la boucle », « aucun jalon pour une page
que le rendu n'a pas ecrite » -- sont les seules qui attrapent le mutant nomme
par la table de la story : *emettre un jalon avant la premiere page*.

**Fabrique** (`CLAUDE.md`, regle des fabriques) : le lot porte **trois** pages
distinguables -- pages 1, 2 et 3, portant des frames differentes -- et la cible
des deux mesures d'echec est celle du **MILIEU**. Une fabrique a deux pages
placerait la cible en seconde ET en derniere position, ou un mutant de
terminaison de boucle (`continue` -> `break`) est indiscernable d'un rendu
complet.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import gamut_map, pdf_composition, pdf_render  # noqa: E402
from mixed_media_utility.frame_selection import select_source_frames  # noqa: E402
from mixed_media_utility.io import naming, project_layout  # noqa: E402
from mixed_media_utility.io.extraction_manifest import (  # noqa: E402
    ExtractionRecord,
    build_extraction_manifest,
)

PROJECT_ID = "proj-makepdf-noyau"
RUSH_ID = "rush-001"
FPS_SOURCE = 25.0
FPS_TARGET = 5.0
SOURCE_FRAME_COUNT = 50  # -> 10 frames extraites

#: Cardinal choisi pour que le lot fasse **trois** planches : `ceil(10 / 4) = 3`.
#: Il n'est pas recopie dans les tests -- le `page_count` du plan fait foi --,
#: mais la fabrique doit garantir qu'il y a bien un milieu a viser.
FRAMES_PAR_PAGE = 4
PAGES_ATTENDUES = 3

#: L'index (0-fonde) de la page du MILIEU dans `plan.pages`. C'est la cible des
#: deux mesures d'echec : ni premiere, ni derniere.
PAGE_DU_MILIEU = 1

STAMP = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)

#: La chaine de scan de la page de calibration -- une donnee de fabrique, pas
#: une valeur du produit.
CHAINE_DE_SCAN = "banc-noyau-11-7"

#: Une compression de gamut **differente** de celle que les QR du plan
#: declarent : lue du vocabulaire du coeur, jamais inventee, pour que la garde
#: de coherence du rendu refuse.
_UNE_AUTRE_COMPRESSION = next(
    identifiant
    for identifiant in gamut_map.GAMUT_MAPS
    if identifiant != gamut_map.DEFAULT_GAMUT_MAP
)


@pytest.fixture()
def projet_a_trois_planches(tmp_path: Path) -> dict:
    """Projet reel sur disque dont le lot compose **trois** planches.

    Meme fabrique que `test_makepdf_command.project_with_lot` -- manifest 3.4
    construit par `build_extraction_manifest`, TIFF ecrits sous les noms de la
    convention 2.3, jamais par un glob.
    """
    project_dir = tmp_path / "projet"
    project_layout.ensure_project_layout(project_dir)

    selection = select_source_frames(
        fps_source=FPS_SOURCE,
        fps_target=FPS_TARGET,
        source_frame_count=SOURCE_FRAME_COUNT,
    )
    lot_id = naming.build_lot_id(RUSH_ID, FPS_TARGET)
    frames_dir_relative = (
        f"{project_layout.FRAMES_DIRNAME}/"
        f"{project_layout.rush_dir_slug(RUSH_ID, FPS_TARGET)}"
    )
    record = ExtractionRecord(
        project_id=PROJECT_ID,
        rush_id=RUSH_ID,
        rush_source_name=f"{RUSH_ID}.mov",
        lot_id=lot_id,
        frames_dir_relative=frames_dir_relative,
        selection=selection,
        fps_source=FPS_SOURCE,
        fps_target=FPS_TARGET,
        source_width=1920,
        source_height=1080,
        source_fields={},
        confirmation_mode="non_interactif",
        unknown_color_accepted=True,
        confirmed_at="2026-08-06T00:00:00Z",
    )
    manifest = build_extraction_manifest(None, record)
    manifest["color"]["target_colorspace"] = "rec709"
    (project_dir / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    frames_path = project_dir / Path(frames_dir_relative)
    frames_path.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    for frame in selection.frames:
        name = naming.build_extracted_frame_filename(
            RUSH_ID, FPS_TARGET, frame.frame_timecode
        )
        # Un bruit **different par frame** (le generateur avance) : des pages
        # uniformes rendraient une permutation invisible.
        image = rng.integers(0, 65535, size=(108, 192, 3), dtype=np.uint16)
        assert cv2.imwrite(str(frames_path / name), image)

    plan = pdf_composition.compose_lot_plan(
        manifest=manifest,
        lot_id=lot_id,
        frames_per_page=FRAMES_PAR_PAGE,
    )
    # Garde de la fabrique elle-meme : sans trois pages, les mesures d'echec
    # ci-dessous ne viseraient plus un milieu, et le banc mesurerait moins que
    # ce qu'il annonce.
    assert plan.page_count == PAGES_ATTENDUES
    assert len(plan.pages) == PAGES_ATTENDUES
    # ... et les trois pages sont **distinguables** : trois index distincts.
    assert len({page.page_index for page in plan.pages}) == PAGES_ATTENDUES

    return {
        "project_dir": project_dir,
        "manifest": manifest,
        "lot_id": lot_id,
        "plan": plan,
    }


def _cardinal_de_pages(pdf_path: Path) -> int:
    # reportlab ecrit les dictionnaires de pages non compresses (meme lecture
    # que `test_makepdf_command.count_pdf_pages`).
    data = pdf_path.read_bytes()
    return data.count(b"/Type /Page") - data.count(b"/Type /Pages")


# ---------------------------------------------------------------------------
# AC 2.6 -- le contrat positif : `total` exact, suite exacte
# ---------------------------------------------------------------------------


def test_le_total_de_chaque_jalon_vaut_EXACTEMENT_plan_page_count(
    projet_a_trois_planches,
) -> None:
    """`total` vaut `plan.page_count` -- pas « au moins », pas « environ »."""
    plan = projet_a_trois_planches["plan"]
    jalons: list[tuple[int, int]] = []

    pdf_render.render_lot_pdf(
        plan,
        projet_a_trois_planches["project_dir"],
        projet_a_trois_planches["project_dir"] / "planches.pdf",
        generated_at=STAMP,
        rappel_progression=lambda faites, total: jalons.append((faites, total)),
    )

    assert jalons, (
        "aucun jalon : le canal est eteint alors qu'un rappel appelable a ete "
        "fourni -- c'est le defaut « optionnel devenu casse » d'`AR3`."
    )
    assert {total for _, total in jalons} == {plan.page_count}


def test_la_suite_des_jalons_est_EXACTEMENT_1_a_page_count_sans_trou_ni_doublon(
    projet_a_trois_planches,
) -> None:
    """Egalite de SUITE, jamais une appartenance.

    « Le jalon 3 est present » laisserait passer un doublon, un trou, un
    desordre et tout jalon supplementaire : c'est exactement la famille de
    mesures que `CLAUDE.md` nomme (« une assertion positive laisse passer toute
    divergence supplementaire »).
    """
    plan = projet_a_trois_planches["plan"]
    jalons: list[tuple[int, int]] = []

    pdf_render.render_lot_pdf(
        plan,
        projet_a_trois_planches["project_dir"],
        projet_a_trois_planches["project_dir"] / "planches.pdf",
        generated_at=STAMP,
        rappel_progression=lambda faites, total: jalons.append((faites, total)),
    )

    assert jalons == [
        (rang, plan.page_count) for rang in range(1, plan.page_count + 1)
    ]


def test_la_page_de_calibration_seule_emet_son_unique_jalon(
    projet_a_trois_planches,
) -> None:
    """Le second appelant du rendu -- `makepdf calibration-page` -- a un plan
    a **une** page, et son unique jalon vaut `(1, 1)`."""
    plan = pdf_composition.compose_calibration_page_plan(
        manifest=projet_a_trois_planches["manifest"],
        scan_chain_label=CHAINE_DE_SCAN,
    )
    jalons: list[tuple[int, int]] = []

    pdf_render.render_lot_pdf(
        plan,
        projet_a_trois_planches["project_dir"],
        projet_a_trois_planches["project_dir"] / "calibration.pdf",
        generated_at=STAMP,
        rappel_progression=lambda faites, total: jalons.append((faites, total)),
    )

    assert jalons == [(1, plan.page_count)]
    assert plan.page_count == pdf_composition.CALIBRATION_ONLY_PAGE_COUNT


# ---------------------------------------------------------------------------
# AC 2.6 -- les frontieres NEGATIVES : aucun jalon avant la premiere page
# ---------------------------------------------------------------------------


def test_un_refus_dur_ANTERIEUR_a_la_boucle_n_emet_AUCUN_jalon(
    projet_a_trois_planches,
) -> None:
    """Mutant vise : *emettre un jalon avant la premiere page*.

    `_assert_declared_gamut_map_matches` est le refus dur le plus haut du
    rendu. Un canal ouvert -- ou un jalon emis -- au-dessus de lui ferait
    afficher une tache qui a commence alors que rien n'a ete ecrit, ce que
    `EPIC7-ARB-79` interdit. La mesure est un ensemble **vide**, pas un
    cardinal « petit ».
    """
    plan = dataclasses.replace(
        projet_a_trois_planches["plan"],
        gamut_map_id=_UNE_AUTRE_COMPRESSION,
    )
    jalons: list[tuple[int, int]] = []
    cible = projet_a_trois_planches["project_dir"] / "refuse.pdf"

    with pytest.raises(pdf_render.PdfRenderError):
        pdf_render.render_lot_pdf(
            plan,
            projet_a_trois_planches["project_dir"],
            cible,
            generated_at=STAMP,
            rappel_progression=lambda faites, total: jalons.append((faites, total)),
        )

    assert jalons == []
    assert not cible.exists()


def test_un_echec_sur_la_page_du_MILIEU_n_emet_que_les_jalons_des_pages_ECRITES(
    projet_a_trois_planches, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le jalon suit l'ecriture, il ne la precede pas.

    La cible est la page du **MILIEU** : une fabrique a deux pages la placerait
    aussi en derniere, et le jalon de la derniere page est indiscernable d'un
    jalon emis en tete de boucle.

    Deux mutants meurent ici :

    * `emetteur.emettre(...)` **remonte avant** `_render_page` -- le jalon 2
      serait emis alors que la page 2 n'a jamais ete dessinee ;
    * l'ouverture du canal remonte au-dessus de la boucle **avec** un premier
      jalon -- le jalon 1 apparaitrait avant tout dessin.
    """
    plan = projet_a_trois_planches["plan"]
    page_visee = plan.pages[PAGE_DU_MILIEU]
    jalons: list[tuple[int, int]] = []
    dessinees: list[int] = []
    veritable = pdf_render._render_page

    def _render_page_qui_echoue_au_milieu(canvas, plan_, page, *args, **kwargs):
        if page.page_index == page_visee.page_index:
            raise RuntimeError("echec injecte sur la page du milieu")
        dessinees.append(page.page_index)
        return veritable(canvas, plan_, page, *args, **kwargs)

    monkeypatch.setattr(
        pdf_render, "_render_page", _render_page_qui_echoue_au_milieu
    )
    cible = projet_a_trois_planches["project_dir"] / "interrompu.pdf"

    with pytest.raises(RuntimeError):
        pdf_render.render_lot_pdf(
            plan,
            projet_a_trois_planches["project_dir"],
            cible,
            generated_at=STAMP,
            rappel_progression=lambda faites, total: jalons.append((faites, total)),
        )

    # Une seule page dessinee, donc un seul jalon -- et surtout PAS de jalon 2.
    assert dessinees == [plan.pages[0].page_index]
    assert jalons == [(1, plan.page_count)]
    # L'ecriture est atomique : ni PDF partiel, ni temporaire survivant.
    assert not cible.exists()
    restes = [p.name for p in cible.parent.glob(".*.tmp-*")]
    assert restes == []


# ---------------------------------------------------------------------------
# AC 2.6 -- `AR3` : optionnel, et jamais silencieusement eteint
# ---------------------------------------------------------------------------


def test_l_absence_de_rappel_ne_change_RIEN_a_l_observable(
    projet_a_trois_planches,
) -> None:
    """Sans rappel, meme PDF, meme cardinal de pages, aucune levee."""
    plan = projet_a_trois_planches["plan"]
    project_dir = projet_a_trois_planches["project_dir"]

    sans = pdf_render.render_lot_pdf(
        plan, project_dir, project_dir / "sans.pdf", generated_at=STAMP
    )
    avec = pdf_render.render_lot_pdf(
        plan,
        project_dir,
        project_dir / "avec.pdf",
        generated_at=STAMP,
        rappel_progression=lambda faites, total: None,
    )

    assert sans.exists() and avec.exists()
    assert _cardinal_de_pages(sans) == plan.page_count
    assert _cardinal_de_pages(avec) == _cardinal_de_pages(sans)


def test_un_rappel_qui_LEVE_est_absorbe_et_le_PDF_est_quand_meme_ecrit(
    projet_a_trois_planches,
) -> None:
    """`EPIC7-ARB-79` : « aucune de ses defaillances ne peut faire echouer le
    travail qu'elle observe »."""
    plan = projet_a_trois_planches["plan"]
    project_dir = projet_a_trois_planches["project_dir"]
    appels: list[int] = []

    def _rappel_fautif(faites, total):
        appels.append(faites)
        raise RuntimeError("le consommateur du canal a lache")

    cible = pdf_render.render_lot_pdf(
        plan,
        project_dir,
        project_dir / "malgre-tout.pdf",
        generated_at=STAMP,
        rappel_progression=_rappel_fautif,
    )

    assert cible.exists()
    assert _cardinal_de_pages(cible) == plan.page_count
    # Le canal continue d'appeler : l'absorption ne l'eteint pas.
    assert appels == list(range(1, plan.page_count + 1))


def test_un_rappel_NON_APPELABLE_n_eteint_pas_le_rendu(
    projet_a_trois_planches,
) -> None:
    """Volet symetrique du precedent : un mauvais type ne fait ni lever ni
    perdre une page. C'est le regime `EmetteurProgression` deja gele -- le
    canal part inactif --, mesure ici pour que « optionnel » ne devienne pas
    « casse » du cote du rendu."""
    plan = projet_a_trois_planches["plan"]
    project_dir = projet_a_trois_planches["project_dir"]

    cible = pdf_render.render_lot_pdf(
        plan,
        project_dir,
        project_dir / "type-faux.pdf",
        generated_at=STAMP,
        rappel_progression=object(),
    )

    assert cible.exists()
    assert _cardinal_de_pages(cible) == plan.page_count


def test_le_rendu_n_ouvre_AUCUN_second_mecanisme_de_progression() -> None:
    """Le canal passe par `progression.EmetteurProgression`, jamais par un
    compteur redige a cote -- meme frontiere que `write_lot_output_frames`."""
    source = Path(pdf_render.__file__).read_text(encoding="utf-8")
    assert "progression.EmetteurProgression(" in source


def test_chaque_jalon_arrive_APRES_le_dessin_de_SA_page_ordre_EXACT(
    projet_a_trois_planches, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La frontiere negative la plus forte : l'ENTRELACEMENT, pas le contenu.

    Un mutant qui pose `emetteur.emettre(1)` juste avant la boucle survit a
    toutes les mesures de contenu -- la suite des jalons reste `1, 2, 3`, parce
    que `EmetteurProgression` refuse un jalon qui ne progresse pas. Ce qui le
    distingue est l'**ordre** : son jalon 1 tombe avant que la premiere page
    n'ait ete dessinee.

    On mesure donc la suite exacte des evenements des deux cotes -- un dessin,
    puis son jalon, trois fois --, jamais une appartenance ni un cardinal.
    """
    plan = projet_a_trois_planches["plan"]
    evenements: list[tuple[str, int]] = []
    veritable = pdf_render._render_page

    def _render_page_espionne(canvas, plan_, page, *args, **kwargs):
        evenements.append(("dessin", page.page_index))
        return veritable(canvas, plan_, page, *args, **kwargs)

    monkeypatch.setattr(pdf_render, "_render_page", _render_page_espionne)

    pdf_render.render_lot_pdf(
        plan,
        projet_a_trois_planches["project_dir"],
        projet_a_trois_planches["project_dir"] / "ordre.pdf",
        generated_at=STAMP,
        rappel_progression=lambda faites, total: evenements.append(
            ("jalon", faites)
        ),
    )

    attendu: list[tuple[str, int]] = []
    for rang, page in enumerate(plan.pages, start=1):
        attendu.append(("dessin", page.page_index))
        attendu.append(("jalon", rang))
    assert evenements == attendu


def test_le_total_est_page_count_et_NON_le_cardinal_de_pages_du_plan(
    projet_a_trois_planches,
) -> None:
    """`total` est lu sur `plan.page_count`, jamais recalcule d'a cote.

    Les deux coincident sur tout plan que `compose_lot_plan` produit -- et
    c'est precisement ce qui rend un mutant `len(plan.pages)` invisible sur la
    fabrique nominale. On les fait donc **diverger** sur un plan fabrique a la
    main : le contrat de l'AC 2.6 nomme `plan.page_count`, et c'est lui qui
    doit sortir.
    """
    plan = dataclasses.replace(
        projet_a_trois_planches["plan"],
        page_count=PAGES_ATTENDUES + 2,
    )
    assert plan.page_count != len(plan.pages)
    jalons: list[tuple[int, int]] = []

    pdf_render.render_lot_pdf(
        plan,
        projet_a_trois_planches["project_dir"],
        projet_a_trois_planches["project_dir"] / "divergent.pdf",
        generated_at=STAMP,
        rappel_progression=lambda faites, total: jalons.append((faites, total)),
    )

    assert {total for _, total in jalons} == {PAGES_ATTENDUES + 2}


# ===========================================================================
# Tache B1 -- le DOSSIER D'IDENTITE de `mmu makepdf`
# ===========================================================================
#
# AC 2.5, verbatim : « **Aucun comportement observable de `mmu makepdf` ne
# change, HORS les trois changements que les lots B0 / B0 bis / B0 ter portent
# explicitement** -- memes messages sur `stderr`, memes codes (`0`, `1`, `130`),
# meme `logs/makepdf.log`, meme manifest. »
#
# **C'est la premiere tache du lot, et elle est jouee AVANT le deplacement du
# corps de `makepdf_command`.** Sans elle, « l'identite est preservee » serait
# une affirmation ; avec elle, c'est une mesure a ensemble exact, sur
# **trente-sept** invocations reelles de `cli.main`.
#
# Deux references, parce que deux questions differentes se posent :
#
# * `identite-makepdf-950370eb.json` -- l'etat de la branche **juste avant le
#   deplacement**, lots B0 compris. Contre elle, l'ensemble des scenarios qui
#   divergent doit etre **VIDE** : c'est la mesure du deplacement lui-meme, et
#   c'est celle qui rougira si B2/B3/B5 reecrivent au lieu de deplacer ;
# * `identite-makepdf-484b932.json` -- le `baseline_commit` de la story, donc
#   **avant** les lots B0. Contre elle, l'ensemble des divergents doit etre
#   exactement les huit scenarios qui ECRIVENT une planche, et leur divergence
#   doit porter exactement sur le nom du tirage (AC 2.9). C'est la mesure qui
#   dit qu'aucun **quatrieme** ecart ne s'est glisse avec les trois nommes.
#
# Les deux references sont produites par le meme code de releve
# (`outils_identite_makepdf.py`, qui porte le mode d'emploi de leur
# regeneration), joue sous le `src/` de chaque commit, sur des entrees **octet
# pour octet identiques** -- et cette derniere propriete est desormais mesuree
# et non supposee, par l'empreinte des entrees que le releve embarque.

import outils_identite_makepdf as identite  # noqa: E402
import fabriquer_les_entrees_makepdf as fabrique_identite  # noqa: E402
import outils_traduction_du_vocabulaire as vocabulaire  # noqa: E402
from sens_des_planches import (  # noqa: E402
    PlanchesAuMemeSens, chemins_au_sens_DIFFERENT)

#: Story 11.14, lot E1 -- **les deux references ne se REGENERENT pas, elles se
#: TRADUISENT.**
#:
#: Une reference d'identite n'est pas un fichier d'or : c'est le releve joue
#: sous le `src/` d'un commit fige, sur des entrees octet pour octet
#: identiques. La rejouer rendrait exactement les memes octets, puisque le
#: commit ne bouge pas -- une regeneration ne repare donc RIEN et perd la
#: propriete qui fait la valeur du dossier. Ce qu'il faut est de rendre le
#: releve d'hier dans les mots d'aujourd'hui, segment de chemin par segment de
#: chemin, avec cardinal exact. C'est le geste deja pose par `EPIC11-ARB-171`
#: pour le nom d'un tirage, et par le lot C pour le dossier d'identite du scan.
#:
#: Deux lignes, et **deux seulement**, parce que le dossier de `makepdf` ne
#: touche pas aux frames scannees : `output-frames` n'y figure pas une fois
#: (mesure : 0 occurrence dans les deux references). Y poser une troisieme
#: ligne a cardinal nul ferait croire a une couverture qui n'existe pas.
#:
#: Le cardinal est **par ligne** et non global : un compte global serait juste
#: alors qu'une des deux traductions serait morte et l'autre deux fois trop
#: large -- le mode de panne exact que le lot B a mesure sur son propre releve
#: (147 avant, 147 apres, une ambiguite neuve pour deux retirees).
TRADUCTIONS_DU_VOCABULAIRE = (
    # Le dossier comme SEGMENT de chemin. Il vit dans les CLES de l'arbre des
    # artefacts (135 fois) autant que dans les valeurs (30) -- une traduction
    # qui ne porterait que sur les feuilles ferait diverger chaque fichier
    # renomme deux fois : absent d'un cote, present de l'autre.
    ("frames/", r"(?<![\w-])frames/", r"(?<![\w-])frames/",
     f"{project_layout.EXTRACT_FRAMES_DIRNAME}/", True, 165,
     "frames/lot-a/f.tiff",
     f"{project_layout.EXTRACT_FRAMES_DIRNAME}/lot-a/f.tiff"),
    # Le dossier NU, sans slash : c'est la valeur d'`artifacts.frames_dir` dans
    # les documents aplatis, 30 fois par reference. Elle ne se voit PAS au
    # motif de segment ci-dessus -- il exige un slash -- et c'est la mesure,
    # jamais la relecture, qui l'a trouvee.
    #
    # `sur_les_cles` vaut **False**, et c'est `EPIC11-ARB-221` qui le decide :
    # cette forme est exactement celle d'une cle de manifeste, et l'appliquer
    # aux cles renommerait la cle que l'arbitrage gele.
    ("frames (dossier NU)", r"\Aframes\Z", r'"frames"',
     project_layout.EXTRACT_FRAMES_DIRNAME, False, 30,
     "frames", project_layout.EXTRACT_FRAMES_DIRNAME),
    # `EPIC11-ARB-225` -- le dossier des planches, TROISIEME ligne de la table.
    #
    # Elle n'existe qu'en SEGMENT : la forme nue n'apparait dans aucune des
    # deux references (mesure : 0 occurrence de `"patches"`), le dossier
    # n'ayant jamais eu de champ de manifeste a la maniere d'`artifacts
    # .frames_dir`. Y poser une quatrieme ligne a cardinal nul ferait croire a
    # une couverture qui n'existe pas -- c'est ce que le commentaire d'en-tete
    # dit deja d'`output-frames`.
    #
    # **Le cardinal est PAR REFERENCE, et c'est une mesure, pas un confort** :
    # 113 dans le releve d'avant le deplacement, 73 dans celui du
    # `baseline_commit`. Les deux lignes ci-dessus portent un entier parce que
    # leurs deux comptes coincident (165 et 30 des deux cotes) ; celle-ci ne le
    # peut pas, et un cardinal unique serait donc faux d'un cote. Le prendre
    # comme un maximum, ou le retirer, rendrait le test vert sur une traduction
    # a moitie morte -- exactement le mode de panne que le compte par ligne
    # existe pour attraper.
    ("patches/", r"(?<![\w-])patches/", r"(?<![\w-])patches/",
     f"{project_layout.PLANCHES_DIRNAME}/", True,
     {"identite-makepdf-950370eb.json": 113,
      "identite-makepdf-484b932.json": 73},
     "patches/demo_rush-001_5_2f-por.pdf",
     f"{project_layout.PLANCHES_DIRNAME}/demo_rush-001_5_2f-por.pdf"),
)


def _cardinal_attendu(cardinal, chemin) -> int:
    """Le cardinal de CETTE reference, qu'il soit unique ou par fichier.

    Une ligne dont les deux references portent le meme compte l'ecrit en
    entier ; celle du dossier des planches ne le peut pas -- 113 contre 73 --,
    et une table qui n'accepterait que l'entier aurait pousse a inventer un
    seuil. La table dit donc, fichier par fichier, ce qu'elle a mesure.
    """
    if isinstance(cardinal, Mapping):
        assert chemin.name in cardinal, (
            f"{chemin.name} n'a pas de cardinal mesure dans {cardinal}")
        return cardinal[chemin.name]
    return cardinal

_TRADUCTIONS = vocabulaire.compiler(TRADUCTIONS_DU_VOCABULAIRE)

#: L'etat de la branche **juste avant** le deplacement du corps (taches B2/B3).
#: Contre lui, l'ensemble des divergents doit rester VIDE pour toujours.
REFERENCE_AVANT_DEPLACEMENT = (
    REPO_ROOT / "tests" / "fixtures" / "identite-makepdf-950370eb.json"
)

#: Le `baseline_commit` de la story 11.7, **avant** les lots B0 / B0 bis /
#: B0 ter. Contre lui, les seuls ecarts admis sont les trois nommes.
REFERENCE_BASELINE_DE_LA_STORY = (
    REPO_ROOT / "tests" / "fixtures" / "identite-makepdf-484b932.json"
)

#: Les commits d'ou sortent les deux references. Ils sont nommes ici parce
#: qu'un nom de fichier ne se relit pas dans un message d'echec.
COMMIT_AVANT_DEPLACEMENT = "950370eb"
COMMIT_BASELINE_DE_LA_STORY = "484b932"

#: Les **huit** scenarios que les lots B0 / B0 bis / B0 ter font diverger du
#: `baseline_commit`, et **eux seuls**. Ce sont exactement les invocations qui
#: ECRIVENT une planche : les sept de la sequence d'ecriture, plus celle qui
#: ecrit sous une compression non triviale. Aucun refus, aucune mire n'y figure
#: -- et c'est le fait le plus fort du dossier, parce qu'il dit que les trois
#: ecarts nommes n'ont debord'e ni sur les refus de `makepdf`, ni sur la mire.
#:
#: L'ensemble est **exact** : « ces scenarios divergent » ne mesurerait rien,
#: « l'ensemble des scenarios qui divergent est exactement celui-ci » mesure
#: l'exception ET son unicite.
SCENARIOS_QUE_LES_LOTS_B0_FONT_DIVERGER = frozenset({
    "01-nominal",
    "02-relance-identique",
    "03-relance-nouvelle-version",
    "04-relance-overwrite",
    "05-autre-mise-en-page-4f",
    "06-autre-mise-en-page-1f",
    "07-par-rush-et-fps",
    "20-compression-non-triviale",
})

#: Les quatre scenarios dont le **code de sortie** change, et il n'y en a pas
#: d'autre : au `baseline_commit`, relancer un lot deja imprime -- meme forme ou
#: forme differente -- butait sur le refus « existe deja » (`1`) ; depuis le lot
#: B0 bis le rang avance a chaque passe, donc le nom vise est toujours neuf et
#: la planche s'ecrit (`0`). C'est `EPIC11-ARB-175` consequence 3 (« changer de
#: mise en page ne declenche PLUS l'ecran de conflit ») et l'effet, nomme dans
#: la fiche, qui rend ce refus **defensif**.
#:
#: Ils sont nommes **a part** des quatre autres divergents parce qu'un code de
#: sortie qui bouge est le seul ecart que ce dossier ne peut pas expliquer par
#: le nom du tirage. Le noyer dans la liste des huit l'aurait rendu invisible.
SCENARIOS_DONT_LE_REFUS_DE_CONFLIT_A_DISPARU = frozenset({
    "02-relance-identique",
    "05-autre-mise-en-page-4f",
    "06-autre-mise-en-page-1f",
    "07-par-rush-et-fps",
})

#: Le fragment de nom que le `baseline_commit` ecrivait, et qui disparait
#: (AC 2.9 : « le mot `planches` disparait »). Le fragment est `_planches` et
#: non `_planches.pdf` : un tirage de rang 2 s'y appelait
#: `..._planches_v2.pdf`, et la forme longue aurait rate ce cas -- c'est-a-dire
#: exactement le scenario que `--nouvelle-version` couvre.
FRAGMENT_D_AVANT = "_planches"


@pytest.fixture(scope="module")
def racine_d_identite(tmp_path_factory) -> Path:
    """Le dossier ou le releve joue, garde a part de son resultat.

    Il est nomme parce que la cinquieme famille de tolerance
    (`EPIC11-ARB-250`) doit RETROUVER les tirages sur le disque pour en
    decoder les symboles : un dossier d'observables ne porte que des
    condensats, pas les fichiers qui les portent.
    """
    return tmp_path_factory.mktemp("identite-makepdf")


@pytest.fixture(scope="module")
def dossier_d_identite(racine_d_identite) -> dict:
    """Le releve joue sous le `src/` d'AUJOURD'HUI, une seule fois.

    Portee module : les trente-sept invocations coutent quelques secondes, et
    les trois mesures qui suivent lisent le meme dossier -- le rejouer une fois
    par test triplerait le cout sans rien mesurer de plus.
    """
    entrees = racine_d_identite / "entrees"
    fabrique_identite.fabriquer(entrees)
    return identite.collecter(entrees, racine_d_identite / "travail")


def _planches(chemin: Path, dossier: dict, racine: Path) -> PlanchesAuMemeSens:
    """La cinquieme famille, dressee contre une reference donnee.

    Une par reference, et non une pour les deux : la table de substitution
    d'une famille est faite des couples `(condensat d'avant, condensat
    d'aujourd'hui)` que CETTE reference-la fait diverger. Les melanger
    excuserait, dans l'une, un couple que l'autre n'a jamais produit.
    """
    return PlanchesAuMemeSens(_reference(chemin)["scenarios"],
                              dossier["scenarios"], racine / "travail")


@pytest.fixture(scope="module")
def planches_avant_deplacement(dossier_d_identite,
                               racine_d_identite) -> PlanchesAuMemeSens:
    return _planches(REFERENCE_AVANT_DEPLACEMENT, dossier_d_identite,
                     racine_d_identite)


@pytest.fixture(scope="module")
def planches_du_baseline(dossier_d_identite,
                         racine_d_identite) -> PlanchesAuMemeSens:
    return _planches(REFERENCE_BASELINE_DE_LA_STORY, dossier_d_identite,
                     racine_d_identite)


def _scenarios_divergents(gauche: dict, droite: dict, planches=None) -> set:
    """Les noms de scenario dont **le moindre** observable differe.

    Le releve d'un scenario porte le code de sortie, `stdout`, `stderr`,
    l'arbre des artefacts (condensats), chaque document JSON aplati et les
    lignes de journal : une egalite de scenario est donc une egalite sur tout
    cela a la fois.

    **`planches` est la cinquieme famille de tolerance** (`EPIC11-ARB-250`) :
    un tirage dont seul le motif d'encre du QR a change, mais dont le symbole
    redit ce que le manifest du baseline attendait de lui, ne compte pas comme
    divergent. Sans elle, la comparaison redevient une egalite d'octets -- et
    c'est ce que les temoins de ce fichier lui demandent.
    """
    assert set(gauche) == set(droite), (
        "les deux releves ne portent pas le meme jeu de scenarios : "
        f"{sorted(set(gauche) ^ set(droite))}"
    )
    return {nom for nom in gauche
            if chemins_au_sens_DIFFERENT(gauche[nom], droite[nom], planches)}


def _reference_brute(chemin: Path) -> dict:
    """La reference telle qu'elle est versionnee, **sans** traduction.

    Elle sert aux temoins : sans elle, « la traduction a mordu 165 fois » ne
    pourrait pas etre confronte a ce que le fichier porte reellement.
    """
    return json.loads(chemin.read_text(encoding="utf-8"))


def _reference(chemin: Path) -> dict:
    """La reference, **traduite** dans le vocabulaire d'aujourd'hui.

    Toute comparaison de ce banc passe par ici -- y compris celle des
    `entrees`, dont l'empreinte est un `chemin relatif -> condensat` et porte
    donc le nom du dossier dans ses cles.
    """
    return vocabulaire.traduire(_reference_brute(chemin), _TRADUCTIONS, {})


def test_le_dossier_d_identite_porte_bien_TRENTE_SEPT_invocations(
    dossier_d_identite,
) -> None:
    """Temoin de cardinal : un releve qui cesserait de jouer ne se verrait pas.

    Les trois mesures qui suivent comparent deux dossiers ; deux dossiers vides
    sont egaux. Le cardinal est donc mesure a part, et il l'est **des deux
    cotes** -- la reference comprise, qui pourrait avoir ete regeneree sur un
    releve ampute.
    """
    joues = set(dossier_d_identite["scenarios"])
    assert len(joues) == 37
    for chemin in (REFERENCE_AVANT_DEPLACEMENT, REFERENCE_BASELINE_DE_LA_STORY):
        assert set(_reference(chemin)["scenarios"]) == joues, (
            f"{chemin.name} ne porte pas les memes scenarios que le releve "
            "d'aujourd'hui : la reference est perimee, il faut la regenerer "
            "(mode d'emploi dans outils_identite_makepdf.py)."
        )


def test_les_ENTREES_des_deux_references_sont_celles_d_aujourd_hui(
    dossier_d_identite,
) -> None:
    """Sans cette mesure, un ecart de FABRIQUE se lirait comme un ecart de produit.

    Les entrees sont ecrites par `fabriquer_les_entrees_makepdf`, qui vit dans
    `tests/` et peut changer. Le releve embarque leur empreinte ; les trois
    doivent coincider, sinon la comparaison ne porte plus sur les memes octets
    et ne mesure plus rien.
    """
    empreinte = dossier_d_identite["entrees"]
    assert empreinte, "le releve n'a releve aucune entree"
    for chemin in (REFERENCE_AVANT_DEPLACEMENT, REFERENCE_BASELINE_DE_LA_STORY):
        assert _reference(chemin)["entrees"] == empreinte, (
            f"{chemin.name} a ete joue sur d'autres entrees que celles "
            "d'aujourd'hui."
        )


def test_le_deplacement_du_corps_ne_change_STRICTEMENT_RIEN_a_l_observable(
    dossier_d_identite, planches_avant_deplacement,
) -> None:
    """AC 2.5 -- la mesure du deplacement lui-meme, en ensemble VIDE.

    C'est la mesure qui rougit si les taches B2/B3/B5 **reecrivent** au lieu de
    deplacer : une seconde redaction diverge, et l'ecart ne se verrait sinon
    que sur les PDF produits.

    L'assertion est celle de l'**ensemble**, jamais « au moins un scenario
    coincide » : une assertion positive laisse passer toute divergence
    supplementaire.
    """
    reference = _reference(REFERENCE_AVANT_DEPLACEMENT)
    if not (dossier_d_identite["rendu_pdf_gele"] and reference["rendu_pdf_gele"]):
        pytest.skip(
            "reportlab n'expose pas `rl_config.invariant` : les octets d'un PDF "
            "ne sont pas reproductibles, la comparaison ne mesurerait rien."
        )
    divergents = _scenarios_divergents(
        reference["scenarios"], dossier_d_identite["scenarios"],
        planches_avant_deplacement,
    )
    assert divergents == set(), (
        f"le deplacement du corps de `makepdf_command` a change l'observable de "
        f"{sorted(divergents)} par rapport a {COMMIT_AVANT_DEPLACEMENT}."
    )


def test_les_seuls_ecarts_avec_le_BASELINE_sont_les_HUIT_ecritures_de_planche(
    dossier_d_identite, planches_du_baseline,
) -> None:
    """AC 2.5 -- les trois ecarts nommes, et **aucun quatrieme**.

    Contre le `baseline_commit` de la story, l'ensemble des scenarios qui
    divergent doit etre exactement celui des invocations qui ecrivent une
    planche. Tout autre scenario qui divergerait -- un refus, une mire -- serait
    un quatrieme ecart, c'est-a-dire un defaut ; et tout scenario de cette liste
    qui **cesserait** de diverger dirait qu'un des trois ecarts nommes a ete
    perdu en route.
    """
    reference = _reference(REFERENCE_BASELINE_DE_LA_STORY)
    if not (dossier_d_identite["rendu_pdf_gele"] and reference["rendu_pdf_gele"]):
        pytest.skip("reportlab sans `rl_config.invariant` : PDF non reproductible")
    divergents = _scenarios_divergents(
        reference["scenarios"], dossier_d_identite["scenarios"],
        planches_du_baseline,
    )
    assert divergents == set(SCENARIOS_QUE_LES_LOTS_B0_FONT_DIVERGER)


#: Les tirages que la cinquieme famille (`EPIC11-ARB-250`) excuse contre
#: `950370eb`, **nommes**. Ils ne servent pas a la reconnaissance -- elle est a
#: la forme, et `PlanchesAuMemeSens` ne lit jamais cette liste -- mais a la
#: MESURE de ce qu'elle avale : sans elle, une tolerance qui s'elargirait d'un
#: tirage resterait verte.
#:
#: Six planches de lot et trois mires. Les mires sont les seules que la
#: comparaison au `baseline_commit` de la story retrouve aussi : les six autres
#: y portent encore le nom d'avant (`_planches.pdf`), donc leur chemin differe
#: des deux cotes et la famille (d) -- le NOM du tirage -- les prend d'abord.
TIRAGES_AU_MEME_SENS = (
    "planches/proj-identite-makepdf_banc-identite-1200-dpi-e6c223d3_calibration.pdf",
    "planches/proj-identite-makepdf_banc-identite-600-dpi-6f5e6f71_calibration.pdf",
    "planches/proj-identite-makepdf_banc-identite-commentee-6eaebfc5_calibration.pdf",
    "planches/proj-identite-makepdf_rush-001_5_1f-por_v5.pdf",
    "planches/proj-identite-makepdf_rush-001_5_2f-por.pdf",
    "planches/proj-identite-makepdf_rush-001_5_2f-por_v2.pdf",
    "planches/proj-identite-makepdf_rush-001_5_2f-por_v3.pdf",
    "planches/proj-identite-makepdf_rush-001_5_2f-por_v6.pdf",
    "planches/proj-identite-makepdf_rush-001_5_4f-por_v4.pdf",
)

#: Les mires, seules planches que les DEUX references nomment pareil.
MIRES_AU_MEME_SENS = tuple(chemin for chemin in TIRAGES_AU_MEME_SENS
                           if chemin.endswith("_calibration.pdf"))


def test_la_CINQUIEME_famille_avale_EXACTEMENT_les_tirages_qu_elle_NOMME(
    planches_avant_deplacement, planches_du_baseline,
) -> None:
    """L'ensemble exact de ce que la tolerance de condensat excuse ici.

    Une tolerance de condensat est la plus large qu'un banc d'identite puisse
    porter : elle doit donc etre la plus etroitement mesuree. L'assertion est
    celle de l'**ensemble** -- « ces tirages sont excuses » ne dirait rien
    d'un dixieme qui le serait aussi -- et elle est posee sur les DEUX
    references, parce qu'elles n'excusent pas le meme jeu et que le dire est la
    moitie de la mesure.

    **Aucun verdict FAUX n'est tolere.** Un tirage que la famille examine et
    refuse ne serait pas une tolerance trop large : ce serait une planche qui
    ne redit plus ce que le manifest du baseline attendait d'elle, c'est-a-dire
    un vrai defaut, et il doit se lire ici plutot que dans un ensemble de
    scenarios divergents.
    """
    for famille, attendus, quoi in (
        (planches_avant_deplacement, TIRAGES_AU_MEME_SENS,
         COMMIT_AVANT_DEPLACEMENT),
        (planches_du_baseline, MIRES_AU_MEME_SENS, COMMIT_BASELINE_DE_LA_STORY),
    ):
        vus = {artefact for artefact, _, _ in famille.verdicts}
        assert vus == set(attendus), (
            f"contre {quoi}, la cinquieme famille ne se prononce pas sur les "
            f"tirages declares : {sorted(vus ^ set(attendus))}"
        )
        refuses = sorted(cle for cle, verdict in famille.verdicts.items()
                         if not verdict)
        assert not refuses, (
            f"contre {quoi}, un tirage ne redit plus ce que le manifest du "
            f"baseline attendait de lui : {refuses}"
        )


def test_un_contenu_de_TIRAGE_change_HORS_du_QR_fait_ROUGIR(
    planches_avant_deplacement,
) -> None:
    """Le controle qui ferme la cinquieme famille sur les tirages.

    Quatre greffes, toutes sur des fichiers **reels** de l'arbre de travail :

    1. **un autre RANG du meme lot sous le meme condensat** -- le `_v3` a la
       place du `_v2`. Les deux portent un symbole parfaitement lisible, du
       meme lot, du meme rush, du meme preset, de la meme cadence : le
       `version_rank` est le SEUL fait qui les separe, et le manifest le
       consigne par tirage. Une tolerance qui ne comparerait que l'identite
       du lot confondrait les six tirages qu'il porte ;
    2. **une PAGE EN MOINS** -- le tirage est recopie sans sa derniere page,
       ses QR restent intacts et redisent tout ce que le manifest attend, mais
       ils annoncent un `page_count` que le document ne porte plus. C'est le
       mutant que l'arbitrage nomme, et il ne demande rien au baseline ;
    3. **une mire a la place d'un tirage** -- role de page different ;
    4. **un condensat introuvable** : refus, plutot qu'une excuse par defaut ;
    5. **un suffixe qui n'est pas celui d'une planche** : refus.

    **Ce que ce controle ne couvre pas, dit plutot que tu** : une planche dont
    l'encre changerait SANS que son QR change et SANS que son cardinal de pages
    bouge -- une frame deplacee de quelques dixiemes de millimetre, un libelle
    reecrit -- serait avalee, parce que le dossier de reference ne garde du
    tirage qu'un condensat et aucun temoin non-QR de son rendu. La dette est
    ouverte sous `ARB250-N2` dans `deferred-work.md`, avec la piste mesurable
    (masquer la boite du symbole avant de condenser la page).
    """
    famille = planches_avant_deplacement
    par_artefact = {artefact: (avant, apres)
                    for artefact, avant, apres in famille.verdicts}
    rang_2 = "planches/proj-identite-makepdf_rush-001_5_2f-por_v2.pdf"
    rang_3 = "planches/proj-identite-makepdf_rush-001_5_2f-por_v3.pdf"
    mire = MIRES_AU_MEME_SENS[0]
    avant, apres = par_artefact[rang_2]
    assert famille.porte_le_meme_SENS(rang_2, avant, apres), (
        "le temoin doit d'abord etre EXCUSE, sinon les refus ci-dessous ne "
        "mesurent rien"
    )

    assert not famille.porte_le_meme_SENS(
        rang_2, avant, par_artefact[rang_3][1]), (
        "le tirage de rang 3 a ete accepte a la place de celui de rang 2 : la "
        "tolerance ne compare plus le rang que le QR declare, et elle "
        "confondrait donc les six tirages du meme lot"
    )
    # (2) la page en moins, fabriquee a partir du tirage REEL : on recopie le
    # document sans sa derniere page, et on inscrit la copie dans l'index sous
    # son propre condensat, comme si le produit l'avait ecrite ainsi.
    original = famille.par_condensat[apres]
    ampute = original.with_name("ampute.pdf")
    entier = pdfium.PdfDocument(str(original))
    try:
        assert len(entier) > 1, "le temoin doit porter plus d'une page"
        copie = pdfium.PdfDocument.new()
        copie.import_pages(entier, list(range(len(entier) - 1)))
        copie.save(str(ampute))
    finally:
        entier.close()
    condensat_ampute = hashlib.sha256(ampute.read_bytes()).hexdigest()
    famille.par_condensat[condensat_ampute] = ampute
    assert not famille.porte_le_meme_SENS(rang_2, avant, condensat_ampute), (
        "un tirage ampute d'une page a ete excuse : la tolerance ne compare "
        "plus le cardinal de pages que les symboles declarent"
    )

    assert not famille.porte_le_meme_SENS(
        rang_2, avant, par_artefact[mire][1]), (
        "une mire a ete acceptee a la place d'un tirage"
    )
    assert not famille.porte_le_meme_SENS(rang_2, avant, "0" * 64)
    assert not famille.porte_le_meme_SENS(
        rang_2.replace(".pdf", ".txt"), avant, apres)


def test_les_ecarts_avec_le_BASELINE_portent_TOUS_sur_le_nom_du_tirage(
    dossier_d_identite,
) -> None:
    """Le contenu de l'ecart, pas seulement sa localisation.

    Le test precedent dit **ou** ca diverge ; celui-ci dit **quoi**. Sur chacun
    des huit scenarios, chaque ligne imprimee qui differe doit differer par le
    seul fragment de nom : le cote du `baseline_commit` porte
    `_planches.pdf` (AC 2.9, « le mot `planches` disparait ») et le cote
    d'aujourd'hui ne le porte plus. Une ligne qui differerait autrement -- un
    message reformule, un cardinal de pages qui bouge -- serait un quatrieme
    ecart que le test precedent ne pourrait pas voir, puisqu'il vit dans un
    scenario deja compte comme divergent.
    """
    reference = _reference(REFERENCE_BASELINE_DE_LA_STORY)
    if not (dossier_d_identite["rendu_pdf_gele"] and reference["rendu_pdf_gele"]):
        pytest.skip("reportlab sans `rl_config.invariant` : PDF non reproductible")

    # 1. l'ensemble EXACT des scenarios dont le code de sortie bouge.
    codes_qui_bougent = {
        nom for nom in reference["scenarios"]
        if reference["scenarios"][nom]["code"]
        != dossier_d_identite["scenarios"][nom]["code"]
    }
    assert codes_qui_bougent == set(SCENARIOS_DONT_LE_REFUS_DE_CONFLIT_A_DISPARU)
    # ... et ils bougent tous dans le meme sens, du refus vers l'ecriture. Sans
    # cette moitie, un scenario qui passerait de `0` a `1` -- une regression --
    # serait accepte par l'ensemble ci-dessus.
    for nom in sorted(SCENARIOS_DONT_LE_REFUS_DE_CONFLIT_A_DISPARU):
        avant, apres = reference["scenarios"][nom], dossier_d_identite["scenarios"][nom]
        assert (avant["code"], apres["code"]) == (1, 0), nom
        assert any("existe deja" in ligne for ligne in avant["stderr"]), (
            f"{nom}: le `baseline_commit` ne refusait pas pour conflit -- le "
            "motif du changement de code n'est donc pas celui qui est ecrit ici."
        )

    # 2. sur les quatre AUTRES divergents, chaque ligne qui differe ne differe
    #    que par le fragment de nom.
    inexplicables: list[str] = []
    autres = (set(SCENARIOS_QUE_LES_LOTS_B0_FONT_DIVERGER)
              - set(SCENARIOS_DONT_LE_REFUS_DE_CONFLIT_A_DISPARU))
    for nom in sorted(autres):
        avant, apres = reference["scenarios"][nom], dossier_d_identite["scenarios"][nom]
        for flux in ("stdout", "stderr"):
            assert len(avant[flux]) == len(apres[flux]), (
                f"{nom}: {flux} n'a plus le meme nombre de lignes "
                f"({len(avant[flux])} -> {len(apres[flux])})."
            )
            for rang, (ligne_avant, ligne_apres) in enumerate(
                zip(avant[flux], apres[flux])
            ):
                if ligne_avant == ligne_apres:
                    continue
                if FRAGMENT_D_AVANT in ligne_avant and FRAGMENT_D_AVANT not in ligne_apres:
                    continue
                inexplicables.append(
                    f"{nom}/{flux}[{rang}]: {ligne_avant!r} -> {ligne_apres!r}"
                )
    assert inexplicables == [], (
        "des lignes divergent autrement que par le nom du tirage -- c'est un "
        "QUATRIEME ecart:\n  " + "\n  ".join(inexplicables)
    )


def test_le_comparateur_VOIT_une_divergence_qu_on_lui_pose(
    dossier_d_identite,
) -> None:
    """Temoin : un banc vert ne dit rien de ce qu'il ne mesure pas.

    Les trois mesures ci-dessus reposent entierement sur `_scenarios_divergents`.
    Si le comparateur cessait d'observer -- une egalite trop laxiste, un champ
    oublie --, elles rendraient toutes vert sans rien mesurer. On lui pose donc
    une divergence dans **chacune** des trois familles d'observables (le code,
    une ligne imprimee, un condensat d'artefact) et on verifie qu'il les voit
    toutes les trois, chacune sur un scenario **different**.
    """
    import copy

    releve = copy.deepcopy(dossier_d_identite["scenarios"])
    releve["01-nominal"]["code"] = 42
    releve["13-vocabulaire-refuse"]["stderr"].append("une ligne de trop")
    # Un artefact dont le condensat change : la cible est prise **au milieu**
    # de l'arbre, ni la premiere entree ni la derniere.
    arbre = releve["30-mire-nominale"]["projet"]["arbre"]
    cible = sorted(arbre)[len(arbre) // 2]
    arbre[cible] = "0" * 64

    vus = _scenarios_divergents(dossier_d_identite["scenarios"], releve)
    assert vus == {"01-nominal", "13-vocabulaire-refuse", "30-mire-nominale"}


def test_la_reference_du_BASELINE_sort_bien_d_un_arbre_D_AVANT_les_lots_B0() -> None:
    """Temoin : la reference mesure-t-elle vraiment autre chose qu'aujourd'hui ?

    Une reference regeneree par megarde sous le `src/` d'aujourd'hui rendrait le
    test des huit divergents **rouge** -- donc visible. Mais l'inverse ne l'est
    pas : une reference du `baseline_commit` qui aurait perdu le fragment
    `_planches.pdf` ne se distinguerait pas d'un releve d'aujourd'hui sur les
    scenarios qui ne l'ecrivent pas. On mesure donc directement la marque de
    l'arbre d'avant : le mot que l'AC 2.9 fait disparaitre y est **present**.
    """
    def _porteurs(dossier: dict) -> set:
        return {
            nom for nom, scenario in dossier["scenarios"].items()
            if any(FRAGMENT_D_AVANT in ligne
                   for ligne in scenario["stdout"] + scenario["stderr"])
        }

    assert _porteurs(_reference(REFERENCE_BASELINE_DE_LA_STORY)) == set(
        SCENARIOS_QUE_LES_LOTS_B0_FONT_DIVERGER), (
        f"{REFERENCE_BASELINE_DE_LA_STORY.name} ne porte pas la marque de "
        f"l'arbre du commit {COMMIT_BASELINE_DE_LA_STORY}."
    )
    # Le volet symetrique : la reference d'AVANT LE DEPLACEMENT, elle, n'en
    # porte plus aucune. Sans lui, deux references identiques passeraient la
    # premiere moitie sans que rien ne le dise.
    assert _porteurs(_reference(REFERENCE_AVANT_DEPLACEMENT)) == set()


# ===========================================================================
# Story 11.14, lot E1 -- la TRADUCTION des deux references se MESURE
# ===========================================================================
#
# Les trois comparaisons ci-dessus passent toutes par `_reference()`, donc par
# la traduction. Si celle-ci mordait une fois de trop ou une fois de trop peu,
# elles resteraient **vertes** : deux dossiers traduits de la meme facon fausse
# restent egaux. La traduction se mesure donc pour elle-meme, et elle se mesure
# des DEUX cotes -- ce qu'elle change, et ce qu'elle ne change pas.
#
# Chaque reference est parametree separement plutot que sommee : un cardinal
# global de 330 serait juste alors qu'une des deux references serait traduite
# 165 fois et l'autre 165 aussi... ou 100 et 230. Le compte qui vaut est celui
# du fichier, pas celui de la paire.

_REFERENCES = (
    (REFERENCE_AVANT_DEPLACEMENT, COMMIT_AVANT_DEPLACEMENT),
    (REFERENCE_BASELINE_DE_LA_STORY, COMMIT_BASELINE_DE_LA_STORY),
)


@pytest.mark.parametrize("chemin,commit", _REFERENCES, ids=lambda v: str(v)[-12:])
@pytest.mark.parametrize(vocabulaire.COLONNES, TRADUCTIONS_DU_VOCABULAIRE)
def test_la_TRADUCTION_MORD_le_nombre_EXACT_de_fois(
    retire, motif, brut, neuf, sur_les_cles, cardinal, avant, apres,
    chemin, commit,
) -> None:
    """Le cardinal est confronte au compte BRUT du litteral dans le fichier.

    Les deux coincident parce que **toutes** les occurrences sont des segments
    de chemin ; si l'une cessait d'en etre un -- un mot du vocabulaire tombant
    dans une phrase plutot que dans un chemin --, les deux nombres
    divergeraient, et c'est exactement ce qu'il faudrait savoir.
    """
    compteur: dict = {}
    cardinal = _cardinal_attendu(cardinal, chemin)
    vocabulaire.traduire(_reference_brute(chemin), _TRADUCTIONS, compteur)
    assert compteur.get(retire, 0) == cardinal, (
        f"{chemin.name} : {compteur.get(retire, 0)} substitutions de {retire!r} "
        f"pour {cardinal} attendues -- {compteur}"
    )

    dans_le_fichier = len(re.findall(brut, chemin.read_text(encoding="utf-8")))
    assert dans_le_fichier == cardinal, (
        f"{dans_le_fichier} occurrences de {retire!r} dans {chemin.name} pour "
        f"{cardinal} substitutions : une occurrence n'est pas un segment de "
        "chemin, et la traduction la laisse passer en silence"
    )


@pytest.mark.parametrize("chemin,commit", _REFERENCES, ids=lambda v: str(v)[-12:])
@pytest.mark.parametrize(vocabulaire.COLONNES, TRADUCTIONS_DU_VOCABULAIRE)
def test_la_reference_TRADUITE_ne_porte_plus_AUCUN_nom_retire(
    retire, motif, brut, neuf, sur_les_cles, cardinal, avant, apres,
    chemin, commit,
) -> None:
    """Volet symetrique du precedent.

    Le compte pourrait etre juste et le travail inacheve si une occurrence
    echappait au motif -- le cardinal ne compte que ce que le motif a vu.
    """
    traduite = json.dumps(_reference(chemin), ensure_ascii=False, sort_keys=True)
    restants = re.findall(brut, traduite)
    assert restants == [], (
        f"{len(restants)} occurrence(s) de {retire!r} survivent dans "
        f"{chemin.name} traduite"
    )


#: Les sept voisins que la traduction doit EPARGNER. Ils sont ecrits en clair,
#: et c'est necessaire : une cible derivee du module qu'on mesure serait
#: tautologique -- elle suivrait le renommage au lieu de le contredire.
#: La frontiere `test_chemins_de_banc_famille_extract.py` connait cette
#: constante par son nom, et n'epargne qu'elle.
VOISINS_QUE_LA_TRADUCTION_EPARGNE = (
    # La CLE de manifeste, qui ne bouge PAS (`EPIC11-ARB-221`).
    "artifacts.frames_dir",
    "lots[0].frames_dir",
    # Le nom NEUF, qui ne doit pas etre traduit une seconde fois.
    "extract-frames/rush-001_5/f.tiff",
    # Des voisins de sous-chaine : une traduction par `str.replace` les
    # casserait. C'est le defaut n°2 du lot A -- `lot` attrapait `slot`.
    "frames-scannees/rush-001_5/scan.tiff",
    "vieux-frames/f.tiff",
    "sheet_frames",
    # Le mot dans une PHRASE : ce n'est pas un chemin, il ne se traduit pas.
    "12 frames extraites dans <PROJET>",
)

#: Le manifeste POC de `cli.py` en miniature : la CLE et la VALEUR portent le
#: meme mot et n'ont pas le meme sort. La valeur est ecrite dans le mot
#: D'AVANT, puisque c'est elle que la traduction doit deplacer.
DOCUMENT_TEMOIN_DE_LA_CLE_GELEE = {
    "inputs": {"frames": "frames/", "raw": "inputs/"}}


@pytest.mark.parametrize("voisin", VOISINS_QUE_LA_TRADUCTION_EPARGNE)
def test_la_TRADUCTION_ne_touche_ni_les_CLES_ni_un_nom_VOISIN(voisin) -> None:
    """Sept voisins, mesures en cle ET en valeur a la fois.

    La cle de manifeste echappe au motif par le souligne, les chemins voisins
    par la frontiere de segment, et la phrase par l'exigence du slash.
    """
    compteur: dict = {}
    assert vocabulaire.traduire({voisin: voisin}, _TRADUCTIONS, compteur) == {
        voisin: voisin}
    assert sum(compteur.values()) == 0, compteur


def test_une_CLE_nommee_frames_ne_bouge_PAS_quand_sa_VALEUR_bouge() -> None:
    """`EPIC11-ARB-221` mesure a l'endroit exact ou il mord.

    Le manifeste POC de `cli.py` (`_build_sheet_manifest`) porte
    `"inputs": {"frames": "<dossier>/"}` : **la cle et la valeur portent le
    meme mot et n'ont pas le meme sort**. Renommer la cle casserait la lecture
    des projets deja sur disque -- et aucune commande de conversion n'existe
    (`EPIC11-ARB-222`) ; laisser la valeur designerait un dossier qui n'existe
    plus.

    Sans ce test, la garde `sur_les_cles` de la table serait une declaration :
    aucune des deux references ne porte aujourd'hui de cle egale a `frames`
    (mesure : 0), donc aucune mesure sur elles ne verrait la garde disparaitre.
    """
    compteur: dict = {}
    traduit = vocabulaire.traduire(
        DOCUMENT_TEMOIN_DE_LA_CLE_GELEE, _TRADUCTIONS, compteur)
    assert set(traduit["inputs"]) == {"frames", "raw"}, (
        "la CLE `frames` a ete traduite : EPIC11-ARB-221 l'interdit")
    assert traduit["inputs"]["frames"] == (
        f"{project_layout.EXTRACT_FRAMES_DIRNAME}/")
    assert traduit["inputs"]["raw"] == "inputs/"


@pytest.mark.parametrize("position", vocabulaire.POSITIONS_DE_BORD)
@pytest.mark.parametrize(vocabulaire.COLONNES, TRADUCTIONS_DU_VOCABULAIRE)
def test_la_TRADUCTION_MORD_a_CHAQUE_BORD(
    retire, motif, brut, neuf, sur_les_cles, cardinal, avant, apres, position,
) -> None:
    """Regle des fabriques, point 4 (2026-09-03) -- en TETE et en QUEUE.

    « La cible au milieu demasque un `find` fautif ; elle ne demasque pas un
    balayage tronque. » Un parcours qui sauterait la premiere ou la derniere
    entree d'un document resterait vert sur une cible au milieu -- et l'arbre
    d'un scenario reel porte des dizaines d'entrees, dont celles des dossiers
    renommes ne sont ni les premieres ni les dernieres.

    Le corpus est **ecrit** (`VALEURS_TEMOINS`), jamais derive de la sortie du
    parcours : un temoin calcule depuis ce qu'il mesure deplace le bord au lieu
    de le perdre, et reste vert -- defaut mesure sur le lot D3.
    """
    document = {
        f"champ_{rang}": (avant if rang == position else valeur)
        for rang, valeur in enumerate(vocabulaire.VALEURS_TEMOINS)
    }
    compteur: dict = {}
    traduit = vocabulaire.traduire(document, _TRADUCTIONS, compteur)
    assert compteur.get(retire, 0) == 1, compteur
    assert traduit[f"champ_{position}"] == apres, (
        f"la traduction de {retire!r} rate la cible en position {position} "
        f"sur {len(vocabulaire.VALEURS_TEMOINS)}"
    )
    # ... et elle n'a touche a rien d'autre.
    for rang, valeur in enumerate(vocabulaire.VALEURS_TEMOINS):
        if rang != position:
            assert traduit[f"champ_{rang}"] == valeur


@pytest.mark.parametrize("position", vocabulaire.POSITIONS_DE_BORD)
@pytest.mark.parametrize(
    vocabulaire.COLONNES,
    [ligne for ligne in TRADUCTIONS_DU_VOCABULAIRE if ligne[4]])
def test_la_TRADUCTION_DES_CLES_MORD_aussi_a_CHAQUE_BORD(
    retire, motif, brut, neuf, sur_les_cles, cardinal, avant, apres, position,
) -> None:
    """Le meme bord, mais sur les CLES de l'arbre des artefacts.

    C'est la que vit le nom du dossier -- 135 des 165 occurrences de ce
    dossier, dans chaque reference, sont des cles. Une traduction qui ne
    porterait que sur les feuilles laisserait chaque fichier renomme diverger
    deux fois. Seules les lignes declarees valables sur les cles sont
    parametrees ici.
    """
    arbre = {
        (avant if rang == position else chemin): f"condensat-{rang}"
        for rang, chemin in enumerate(vocabulaire.ARBRE_TEMOIN)
    }
    compteur: dict = {}
    traduit = vocabulaire.traduire(
        {"scenarios": {"arbre": arbre}}, _TRADUCTIONS, compteur)
    assert compteur.get(retire, 0) == 1, compteur
    assert traduit["scenarios"]["arbre"][apres] == f"condensat-{position}", (
        f"la traduction de {retire!r} rate la cible en position {position} "
        f"sur {len(vocabulaire.ARBRE_TEMOIN)}"
    )


@pytest.mark.parametrize("position", vocabulaire.POSITIONS_DE_BORD)
@pytest.mark.parametrize(vocabulaire.COLONNES, TRADUCTIONS_DU_VOCABULAIRE)
def test_la_TRADUCTION_MORD_a_CHAQUE_BORD_D_UNE_LISTE(
    retire, motif, brut, neuf, sur_les_cles, cardinal, avant, apres, position,
) -> None:
    """La troisieme structure du parcours, et celle qu'aucun temoin ne voyait.

    **Trouve par la mutation, pas par la relecture** (2026-09-04) : remplacer
    la descente dans les listes par un `list(valeur)` laissait les 111 tests
    de ce banc VERTS. Le mutant etait invisible aux deux references -- zero de
    leurs 195 occurrences ne vit dans une liste --, mais `stdout` et `stderr`
    d'un releve SONT des listes, et un message qui nommerait le dossier y
    tomberait. Le meme noyau sert le dossier du scan, ou ils en portent.

    C'est « le collecteur, pas seulement l'appariement » : un temoin qui ne
    traverse pas la structure ne mesure pas le parcours qui l'alimente. La
    cible est posee en tete, au milieu et en queue de la liste, pour la meme
    raison qu'elle l'est dans le document.
    """
    lignes = [
        (avant if rang == position else ligne)
        for rang, ligne in enumerate(vocabulaire.LIGNES_TEMOINS)
    ]
    compteur: dict = {}
    traduit = vocabulaire.traduire(
        {"scenarios": {"01-nominal": {"stderr": lignes}}}, _TRADUCTIONS,
        compteur)
    rendu = traduit["scenarios"]["01-nominal"]["stderr"]
    assert compteur.get(retire, 0) == 1, compteur
    assert rendu[position] == apres, (
        f"la traduction de {retire!r} rate la cible en position {position} "
        f"sur {len(vocabulaire.LIGNES_TEMOINS)} lignes de journal"
    )
    for rang, ligne in enumerate(vocabulaire.LIGNES_TEMOINS):
        if rang != position:
            assert rendu[rang] == ligne


def test_le_COLLECTEUR_de_frames_du_releve_LEVE_plutot_que_de_rendre_VIDE(
    tmp_path,
) -> None:
    """Le defaut le plus cher n'est pas un rouge, c'est un VERT (lot D2).

    `outils_identite_makepdf` composait `projet / "frames"` en dur pour retirer
    une frame du lot du scenario 21. Apres le renommage, le `rglob` rendait
    `[]` et l'appelant levait un `IndexError` nu : visible ici, mais c'est un
    accident, pas une mesure -- le meme collecteur pose devant un
    `shutil.rmtree` ou un `for` aurait vide un dossier absent **en restant
    vert**, ce que le lot D2 a mesure sur deux scenarios d'`encode`.

    Les trois moities sont mesurees : le nom NEUF est lu, le nom ANCIEN l'est
    aussi (`EPIC11-ARB-222` -- un projet existant ne se convertit pas), et
    l'absence des deux LEVE en nommant les deux dossiers cherches.

    **Les deux noms sont ECRITS ici, jamais lus du module mesure**, et c'est
    une correction faite sur mutant survivant (2026-09-04) : la premiere
    redaction bouclait sur `identite.DOSSIERS_DE_FRAMES_EXTRAITES`, si bien que
    retirer `"frames"` de ce tuple -- c'est-a-dire retirer `EPIC11-ARB-222` --
    faisait simplement boucler une fois de moins, et le test restait VERT sur
    117 autres. Un temoin qui derive son corpus de ce qu'il mesure est
    tautologique ; c'est le defaut du lot D3, et il se reproduit un cran plus
    haut a chaque fois.
    """
    attendus = ("extract-frames", "frames")
    assert identite.DOSSIERS_DE_FRAMES_EXTRAITES == attendus, (
        "le collecteur ne cherche plus les deux noms : le NEUF d'abord, "
        "l'ANCIEN ensuite (`EPIC11-ARB-222`)")
    # Le neuf est bien celui de `project_layout`, et l'ancien aussi -- sans quoi
    # ce module d'identite mesurerait un dossier que le produit n'ecrit pas.
    assert attendus == (project_layout.EXTRACT_FRAMES_DIRNAME,
                        project_layout.LEGACY_FRAMES_DIRNAME)

    for nom in attendus:
        projet = tmp_path / f"projet-{nom}"
        # Trois frames DISTINGUABLES, pas un remplissage uniforme : une
        # troncature du balayage ne se voit pas autrement.
        lot = projet / nom / "rush-001_5"
        lot.mkdir(parents=True)
        for rang in range(3):
            (lot / f"rush-001_5_00-00-0{rang}-00.tiff").write_bytes(
                bytes([rang]))
        trouvees = identite.frames_extraites_du_projet(projet)
        assert [chemin.name for chemin in trouvees] == [
            "rush-001_5_00-00-00-00.tiff",
            "rush-001_5_00-00-01-00.tiff",
            "rush-001_5_00-00-02-00.tiff",
        ], f"le collecteur ne lit pas {nom}/"

    vide = tmp_path / "projet-sans-frames"
    (vide / "planches").mkdir(parents=True)
    with pytest.raises(AssertionError) as refus:
        identite.frames_extraites_du_projet(vide)
    for nom in attendus:
        assert f"{nom}/" in str(refus.value), (
            "le refus ne nomme pas les dossiers cherches : le lecteur du rouge "
            "chercherait la panne dans le produit plutot que dans le nom")


# ===========================================================================
# Tache B6 -- les FRONTIERES du paquet de coeur (AC 2.7 et 2.8)
# ===========================================================================
#
# Les deux AC sont des **frontieres negatives** -- des comptages a zero --, et
# c'est le seul moyen d'attraper la reintroduction d'un defaut : aucun test
# positif ne verrait revenir un `print` dans le coeur ni un `ceil` de
# pagination dans un ecran.
#
# **Chacune porte son volet symetrique**, et ce n'est pas une formalite : c'est
# le defaut que la revue de la 11.3 a paye -- une frontiere unilaterale mesure
# qu'une chose est absente sans mesurer que son symetrique est present, donc
# elle reste verte le jour ou elle cesse de regarder quoi que ce soit. Ici les
# volets sont de deux natures :
#
# * **le temoin qui MORD** : la meme mesure, appliquee a un module fabrique qui
#   viole la regle, doit rougir ;
# * **le volet POSITIF** : la fonction unique dont l'absence dans `tui/` est
#   exigee doit exister et etre appelable. Une frontiere « personne ne calcule
#   la pagination » serait verte dans un depot ou personne ne la calcule nulle
#   part -- ce qui n'est pas ce qu'on veut mesurer.
#
# **Les mesures sont faites a l'AST, jamais au texte** : les docstrings de ce
# depot expliquent justement pourquoi tel module ne fait pas ce qu'on lui
# interdit, donc ils portent les mots -- un grep de texte y mordrait et se
# ferait affaiblir a la premiere prose (defaut mesure sur `tui/jetons.py` a la
# story 11.0). Le lecteur est celui du depot, `outils_frontiere`, **repris et
# non recopie** : deux predicats pour un seul interdit divergeraient, et c'est
# le module couvert par le plus laxiste des deux qui passerait.

import ast  # noqa: E402

if str(REPO_ROOT / "tests" / "unit" / "tui") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tests" / "unit" / "tui"))
from outils_frontiere import chaines_de_code, identifiants  # noqa: E402

SOURCES = REPO_ROOT / "src" / "mixed_media_utility"

#: Le module de coeur que cette story ecrit. Nomme, et non devine : une
#: frontiere qui balaierait « tous les modules de coeur » cesserait de dire
#: **lequel** a rouvert l'interdit.
MODULE_DE_COEUR = SOURCES / "makepdf.py"

#: Ce par quoi le coeur ecrirait sur le terminal. Une TUI a l'ecran dessine :
#: une ligne imprimee par le coeur atterrit **sous** l'ecran, corrompt le rendu
#: et n'est lue par personne. Mesure heritee de la story 11.4b, lot S1, ou une
#: injection ciblee a montre qu'un `print` glisse sur le chemin de REFUS
#: survivait au banc du noyau -- qui n'exerce que le chemin nominal. Une
#: frontiere de source, elle, ne depend d'aucun chemin exerce.
ECRITURES_SUR_LE_TERMINAL = ("print", "stdout", "stderr")

#: Ce par quoi le coeur lirait l'entree standard. Sous `textual`, `stdin`
#: appartient a la boucle d'evenements et un appel bloquant y gele l'interface
#: entiere -- la regression exacte payee cote GUI avec `QMessageBox.exec()`
#: (`EPIC7-ARB-106`).
LECTURES_DE_STDIN = ("input", "stdin", "getpass", "readline")

#: Les quatre regles que la TUI n'a **pas** le droit de rediger une seconde
#: fois (AC 2.8), et le nom de l'unique fonction qui les porte. La table est le
#: volet POSITIF de la frontiere : chaque interdit y est apparie a ce qui le
#: rend inutile, et un interdit sans fonction serait une interdiction de
#: penser plutot qu'une source unique.
REGLES_A_SOURCE_UNIQUE = {
    "pagination": ("mixed_media_utility.pdf_composition", "nombre_de_planches"),
    "identifiant de gabarit": ("mixed_media_utility.page_templates",
                               "build_template_id"),
    "nom du tirage": ("mixed_media_utility.io.naming",
                      "build_sheets_pdf_filename"),
    "domination des geometries": ("mixed_media_utility.page_templates",
                                  "bilan_de_domination"),
}

#: Les deux pieces geometriques dont la **domination** se calcule (lot B8). Un
#: module de `tui/` qui les referencerait redigerait la comparaison de surfaces
#: a cote, ce que `EPIC11-ARB-154` et `-173` confient a `bilan_de_domination`.
PIECES_DE_LA_DOMINATION = ("frame_zones_mm", "frame_image_rect_mm")

#: Les fragments litteraux par lesquels un module de `tui/` **composerait** un
#: identifiant de gabarit ou un nom de tirage, au lieu de les demander au
#: coeur. Ils sont cherches dans les chaines du CODE, docstrings exclus : la
#: prose d'un ecran a le droit d'expliquer ce qu'elle n'ecrit pas.
FRAGMENTS_INTERDITS_DANS_TUI = ("tpl-", ".pdf", "_planches")


def _modules_tui() -> list[Path]:
    return sorted((SOURCES / "tui").rglob("*.py"))


def _ceil_d_une_division(chemin: Path) -> list[int]:
    """Les lignes ou ce module arrondit **une division** vers le haut.

    Deux formes, et deux seulement, parce que ce sont les deux qui s'ecrivent :

    * `ceil(a / b)` -- un appel dont le nom termine par `ceil` et dont
      l'argument porte une division ;
    * `-(-a // b)` -- l'idiome sans `math`, reconnu a sa forme exacte.

    **Ce que cette mesure ne voit pas, dit plutot que tu** : un `ceil` dont la
    division serait calculee une ligne plus haut, dans une variable. Aucune
    lecture d'AST raisonnable ne l'attrape sans ramasser tout le paquet -- et
    l'attraper mal ferait rougir `avancement.py`, qui arrondit des **secondes**
    (`math.ceil(max(float(secondes), 0.0))`) et n'a rien a voir avec la
    pagination. La frontiere borne la derive par la forme la plus courante ;
    elle ne pretend pas a l'exhaustivite semantique. C'est la meme reserve, et
    pour le meme motif, que celle de `test_conformite_sorties_nommees`.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
    fautives: list[int] = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call):
            nom = getattr(noeud.func, "attr", None) or getattr(noeud.func, "id", None)
            if nom == "ceil" and any(
                isinstance(sous, ast.BinOp)
                and isinstance(sous.op, (ast.Div, ast.FloorDiv))
                for argument in noeud.args for sous in ast.walk(argument)
            ):
                fautives.append(noeud.lineno)
        # L'idiome `-(-a // b)` : une negation d'une division entiere dont le
        # membre gauche est lui-meme negatif.
        if (isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, ast.USub)
                and isinstance(noeud.operand, ast.BinOp)
                and isinstance(noeud.operand.op, ast.FloorDiv)
                and isinstance(noeud.operand.left, ast.UnaryOp)
                and isinstance(noeud.operand.left.op, ast.USub)):
            fautives.append(noeud.lineno)
    return fautives


# ---------------------------------------------------------------------------
# AC 2.7 -- le module de coeur, et le paquet `tui/`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("interdit", ECRITURES_SUR_LE_TERMINAL)
def test_le_module_de_coeur_n_ECRIT_JAMAIS_sur_le_terminal(interdit) -> None:
    """AC 2.7 : « aucun `print` », sur le SOURCE donc sur tous les chemins.

    Parametre nom par nom plutot qu'en un seul balayage : un echec dit **quel**
    chemin a ete rouvert, et un `print` glisse sur une branche de refus ne peut
    pas se cacher derriere le silence des deux autres.
    """
    assert MODULE_DE_COEUR.is_file(), MODULE_DE_COEUR
    assert interdit not in identifiants(MODULE_DE_COEUR)


@pytest.mark.parametrize("interdit", LECTURES_DE_STDIN)
def test_le_module_de_coeur_ne_LIT_JAMAIS_stdin(interdit) -> None:
    """AC 2.7, second interdit : le coeur ne pose aucune question bloquante."""
    assert interdit not in identifiants(MODULE_DE_COEUR)


def test_le_module_de_coeur_n_appelle_JAMAIS_cli() -> None:
    """AC 2.7 : le coeur ne remonte pas vers l'enveloppe qui l'appelle.

    Le predicat est celui de `tests/unit/tui/test_frontiere_cli.py`, mot pour
    mot -- un import `mixed_media_utility.cli`, un `from ... import cli`, ou un
    acces d'attribut `.cli`. Le reprendre a l'identique est delibere : deux
    predicats pour un seul interdit divergeraient.
    """
    noms = identifiants(MODULE_DE_COEUR)
    assert {n for n in noms if n == "cli" or n.endswith(".cli")} == set()


def test_le_paquet_tui_n_importe_JAMAIS_cli() -> None:
    """AC 2.7, seconde moitie : comptage a zero sur les modules de `tui/`.

    La meme propriete est mesuree depuis la 11.4b par
    `tests/unit/tui/test_frontiere_cli.py`. Elle est **remesuree ici** parce
    que l'AC 2.7 la nomme, et les deux mesures ne peuvent pas diverger : elles
    lisent l'AST par la meme fonction `outils_frontiere.identifiants`. Ce qui
    serait dangereux serait un second **predicat**, pas une seconde assertion.
    """
    modules = _modules_tui()
    # La frontiere doit regarder quelque chose : un paquet vide la rendrait
    # verte sans rien mesurer.
    assert len(modules) >= 20, modules
    fautifs = {
        chemin.name: sorted(n for n in identifiants(chemin)
                            if n == "cli" or n.endswith(".cli"))
        for chemin in modules
    }
    assert {nom: noms for nom, noms in fautifs.items() if noms} == {}


@pytest.mark.parametrize("interdit", ECRITURES_SUR_LE_TERMINAL + LECTURES_DE_STDIN)
def test_la_mesure_du_coeur_MORD_sur_un_module_fautif(tmp_path, interdit) -> None:
    """AC 2.7, volet symetrique : chacun des SEPT noms, pas seulement le premier.

    Le module fabrique porte le nom interdit dans son docstring **et** dans son
    code : si la mesure lisait le texte, elle mordrait deja sur le docstring et
    serait donc inapplicable au depot reel, dont les docstrings expliquent
    precisement ces interdits.
    """
    fautif = tmp_path / "coeur_bavard.py"
    fautif.write_text(
        f'"""Un docstring qui parle de {interdit} sans jamais s\'en servir."""\n'
        "import sys\n"
        "def agir(message):\n"
        f"    return {interdit}\n",
        encoding="utf-8")
    assert interdit in identifiants(fautif)

    innocent = tmp_path / "coeur_muet.py"
    innocent.write_text(
        f'"""Ce module explique pourquoi il n\'emploie ni {interdit} ni cli."""\n'
        f"# Encore un commentaire qui nomme {interdit}.\n"
        f"MOTIF = 'voir la frontiere sur {interdit}'\n",
        encoding="utf-8")
    assert interdit not in identifiants(innocent), "la prose n'est pas un usage"


def test_la_mesure_de_la_frontiere_cli_MORD_sur_un_module_fautif(tmp_path) -> None:
    """AC 2.7, volet symetrique de la frontiere `cli`, sur ses quatre formes."""
    for source in (
        "from mixed_media_utility import cli\n",
        "import mixed_media_utility.cli\n",
        "from mixed_media_utility import cli as noyau\nnoyau.makepdf_command(None)\n",
        "import mixed_media_utility as mmu\nmmu.cli.makepdf_command(None)\n",
    ):
        fautif = tmp_path / "fautif.py"
        fautif.write_text(source, encoding="utf-8")
        noms = identifiants(fautif)
        assert {n for n in noms if n == "cli" or n.endswith(".cli")}, source


# ---------------------------------------------------------------------------
# AC 2.8 -- aucune SECONDE regle de pagination, de nommage ni de domination
# ---------------------------------------------------------------------------


def test_aucun_module_de_tui_n_arrondit_une_DIVISION_vers_le_haut() -> None:
    """AC 2.8 : la pagination est ecrite une seule fois, dans le coeur.

    Le mutant que cette frontiere tue est nomme par la table de la story :
    `//` au lieu de `ceil` dans la pagination. Il ne peut mordre qu'a un seul
    endroit tant qu'il n'y a qu'un seul endroit ou la pagination se calcule.
    """
    fautifs = {chemin.name: _ceil_d_une_division(chemin)
               for chemin in _modules_tui()}
    assert {nom: lignes for nom, lignes in fautifs.items() if lignes} == {}


def _entrees_de_tout(chemin) -> set:
    """Les chaines qui ne sont que des NOMS exportes par `__all__`.

    Un `__all__` porte des identifiants, pas du texte compose : `"ligne_des_planches"`
    y est le nom d'une fonction, jamais un nom de fichier. Les compter ferait
    rougir la frontiere sur une chaine que personne ne concatene.
    """
    arbre = ast.parse(Path(chemin).read_text(encoding="utf-8"))
    noms = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Assign):
            continue
        if not any(isinstance(c, ast.Name) and c.id == "__all__"
                   for c in noeud.targets):
            continue
        for element in ast.walk(noeud.value):
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                noms.add(element.value)
    return noms


@pytest.mark.parametrize("fragment", FRAGMENTS_INTERDITS_DANS_TUI)
def test_aucun_module_de_tui_ne_COMPOSE_un_gabarit_ni_un_nom_de_tirage(
    fragment,
) -> None:
    """AC 2.8 : ni `tpl-...`, ni un nom de PDF de planches.

    Un ecran a le droit d'**afficher** un nom que le manifeste lui donne ; il
    n'a pas le droit d'en **composer** un. La difference se lit sur les
    litteraux : afficher n'en demande aucun, composer en demande au moins un.
    `_planches` y figure bien qu'il ait disparu du produit avec le lot B0 : une
    frontiere qui ne nommerait que la forme d'aujourd'hui laisserait revenir
    l'ancienne.
    """
    fautifs = {
        chemin.name: [texte for texte in chaines_de_code(chemin)
                      if fragment in texte
                      and texte not in _entrees_de_tout(chemin)]
        for chemin in _modules_tui()
    }
    assert {nom: textes for nom, textes in fautifs.items() if textes} == {}


def test_l_exception_d_un_TOUT_ne_masque_QUE_des_noms_de_fonctions() -> None:
    """L'exception ci-dessus est nommee **et** bornee, pas une permission.

    Exclure `__all__` est legitime : on y ecrit des **identifiants**, jamais un
    nom de fichier compose. Mais une exclusion non bornee finit par avaler un
    vrai defaut -- il suffirait qu'une chaine reellement composee porte le meme
    texte qu'un nom exporte. On mesure donc l'ensemble EXACT de ce que
    l'exception laisse passer, et il ne contient que des noms de fonctions du
    module qui les exporte.

    Trouve le 2026-09-02 : `ligne_des_planches` et `noms_des_planches`, deux
    **fonctions** d'`atelier_pdf_confirmation.py`, faisaient rougir la frontiere
    par leur seule presence dans son `__all__`. Un faux positif laisse en place
    finit par faire desactiver la mesure entiere -- c'est le motif de cette
    borne, pas le confort.

    Troisieme entree le 2026-09-06, et la frontiere a fait exactement son
    travail : `ouvrir_la_composition_des_planches`, la fonction que le lot
    `MQ-A` a ajoutee a `atelier_pdf.py` (l. 624, exportee l. 673) pour que la
    suite « Composer les planches de ces lots » atteigne enfin son atelier,
    porte `_planches` dans son nom. Elle n'a ete vue par aucune mesure du lot
    -- la non-regression de `MQ-A` portait sur `tests/unit/tui`, et cette
    frontiere-ci vit dans `test_makepdf_noyau.py`. C'est la premiere course
    LARGE posterieure a la fusion qui l'a rendue.

    L'ensemble reste EXACT et se maintient a la main : chaque entree est un nom
    de fonction du module qui l'exporte, verifie comme tel avant d'etre
    ajoutee. Une entree de plus sans motif ecrit serait le debut de la
    permission que ce test refuse.
    """
    masques = {}
    for chemin in _modules_tui():
        exportes = _entrees_de_tout(chemin)
        vus = {texte for texte in chaines_de_code(chemin)
               if any(f in texte for f in FRAGMENTS_INTERDITS_DANS_TUI)
               and texte in exportes}
        if vus:
            masques[chemin.name] = sorted(vus)
    assert masques == {
        "atelier_pdf.py": ["ouvrir_la_composition_des_planches"],
        "atelier_pdf_confirmation.py": ["ligne_des_planches", "noms_des_planches"],
    }


@pytest.mark.parametrize("piece", PIECES_DE_LA_DOMINATION)
def test_aucun_module_de_tui_ne_COMPARE_deux_surfaces_de_dessin(piece) -> None:
    """AC 2.8 : la domination vient du lot B8, jamais d'un calcul d'ecran.

    Les deux pieces sont les seules entrees du calcul (`EPIC11-ARB-154`,
    `-173`) : un module qui les referencerait redigerait la comparaison a cote,
    et deux verdicts de domination cohabiteraient sans que rien ne le montre.
    """
    fautifs = [chemin.name for chemin in _modules_tui()
               if piece in identifiants(chemin)]
    assert fautifs == []


@pytest.mark.parametrize("regle", sorted(REGLES_A_SOURCE_UNIQUE))
def test_la_regle_interdite_a_la_TUI_est_bien_ECRITE_ailleurs(regle) -> None:
    """AC 2.8, volet POSITIF -- et c'est celui sans lequel les trois precedents
    ne mesurent rien.

    « Aucun module de `tui/` ne calcule la pagination » est vrai d'un depot ou
    personne ne la calcule nulle part. La frontiere ne dit quelque chose que si
    la regle **existe** ailleurs, en un seul endroit nomme. C'est exactement le
    volet symetrique dont l'absence a ete payee a la revue de la 11.3.
    """
    import importlib

    nom_de_module, nom_de_fonction = REGLES_A_SOURCE_UNIQUE[regle]
    module = importlib.import_module(nom_de_module)
    fonction = getattr(module, nom_de_fonction, None)
    assert callable(fonction), (
        f"la regle « {regle} » est interdite a la TUI mais "
        f"{nom_de_module}.{nom_de_fonction} n'existe pas : la frontiere "
        "interdirait de penser au lieu de nommer une source unique."
    )


def test_la_mesure_de_la_pagination_MORD_sur_les_DEUX_formes(tmp_path) -> None:
    """AC 2.8, volet symetrique, et il porte sur les deux ecritures.

    Le module innocent est calque sur le vrai cas du depot : `avancement.py`
    arrondit des **secondes** par `math.ceil`, sans aucune division. Une
    frontiere qui se contenterait de chercher le nom `ceil` le declarerait
    fautif -- donc elle serait retiree, et la pagination cesserait d'etre
    mesuree.
    """
    innocent = tmp_path / "innocent.py"
    innocent.write_text(
        "import math\n"
        "def secondes(valeur):\n"
        "    return max(math.ceil(max(float(valeur), 0.0)), 1)\n"
        "def moitie(elements):\n"
        "    return elements[len(elements) // 2]\n",
        encoding="utf-8")
    assert _ceil_d_une_division(innocent) == []

    for source in (
        "import math\ndef pages(frames, cardinal):\n"
        "    return math.ceil(frames / cardinal)\n",
        "from math import ceil\ndef pages(frames, cardinal):\n"
        "    return ceil(frames / cardinal)\n",
        "def pages(frames, cardinal):\n"
        "    return -(-frames // cardinal)\n",
    ):
        fautif = tmp_path / "fautif.py"
        fautif.write_text(source, encoding="utf-8")
        assert _ceil_d_une_division(fautif), source


@pytest.mark.parametrize("fragment", FRAGMENTS_INTERDITS_DANS_TUI)
def test_la_mesure_des_litteraux_MORD_et_epargne_la_PROSE(tmp_path, fragment) -> None:
    """AC 2.8, volet symetrique : elle voit le code, jamais le docstring.

    Les deux moities comptent autant l'une que l'autre. Sans la premiere, la
    frontiere pourrait ne rien regarder ; sans la seconde, elle mordrait sur
    les docstrings du depot qui expliquent ces interdits, et serait retiree.
    """
    fautif = tmp_path / "compositeur.py"
    fautif.write_text(
        f'"""Un docstring innocent."""\n'
        f"def nom(o, n):\n"
        f"    return f'{fragment}' + str(n)\n",
        encoding="utf-8")
    assert [t for t in chaines_de_code(fautif) if fragment in t], fragment

    innocent = tmp_path / "prose.py"
    innocent.write_text(
        f'"""Cet ecran affiche un nom donne par le manifeste, il ne compose '
        f'aucun {fragment}."""\n'
        f"# Ni ici : {fragment}\n"
        "def afficher(nom):\n"
        "    return nom\n",
        encoding="utf-8")
    assert [t for t in chaines_de_code(innocent) if fragment in t] == []


def test_les_QUATRE_regles_a_source_unique_sont_bien_QUATRE() -> None:
    """Temoin de cardinal : l'AC 2.8 en nomme quatre, la table en porte quatre.

    Sans lui, retirer une entree de `REGLES_A_SOURCE_UNIQUE` retirerait une
    mesure en silence -- le test parametre ci-dessus tournerait simplement une
    fois de moins, et rien ne rougirait.
    """
    assert len(REGLES_A_SOURCE_UNIQUE) == 4
    assert set(REGLES_A_SOURCE_UNIQUE) == {
        "pagination", "identifiant de gabarit", "nom du tirage",
        "domination des geometries",
    }


# ===========================================================================
# Taches B2/B3 -- la SIGNATURE de producteur de coeur, l'ensemble EXACT des
# refus, et l'ORDRE des gardes (AC 2.1, 2.3, 2.4)
# ===========================================================================

import inspect  # noqa: E402

from mixed_media_utility import makepdf as makepdf_noyau  # noqa: E402

#: Les deux points d'entree de coeur de cette story. Nommes, jamais decouverts
#: par balayage : une frontiere qui prendrait « toutes les fonctions publiques
#: du module » cesserait de dire laquelle a perdu sa forme.
POINTS_D_ENTREE = (
    makepdf_noyau.generer_les_planches_du_lot,
    makepdf_noyau.generer_la_page_de_calibration,
)

#: Les trois classes de refus nomme que ce module leve lui-meme.
CLASSES_DE_REFUS = (
    makepdf_noyau.RefusDeMakepdf,
    makepdf_noyau.LotNonConforme,
    makepdf_noyau.ConflitDeSortie,
)


def _motifs_leves_par_le_source() -> set:
    """L'ensemble des motifs que les `raise` du module peuvent porter.

    Lu a l'AST, sur **tous** les chemins -- y compris ceux qu'aucun scenario du
    dossier d'identite n'atteint. Un releve fait a l'execution ne verrait que
    les branches exercees, et c'est precisement la ou un refus se perd.

    Quand le `raise` ne nomme pas `motif=`, c'est le defaut de la classe qui
    s'applique : il est relu dans la signature, jamais recopie ici.
    """
    source = Path(makepdf_noyau.__file__).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    noms_de_classe = {classe.__name__ for classe in CLASSES_DE_REFUS}
    motifs = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Raise) or not isinstance(noeud.exc, ast.Call):
            continue
        nom = getattr(noeud.exc.func, "id", None)
        if nom not in noms_de_classe:
            continue
        nomme = next((mot for mot in noeud.exc.keywords if mot.arg == "motif"), None)
        if nomme is not None:
            motifs.add(getattr(makepdf_noyau, nomme.value.id))
        else:
            defaut = inspect.signature(
                getattr(makepdf_noyau, nom)).parameters["motif"].default
            motifs.add(defaut)
    return motifs


@pytest.mark.parametrize("entree", POINTS_D_ENTREE, ids=lambda f: f.__name__)
def test_le_point_d_entree_a_la_SIGNATURE_d_un_producteur_de_coeur(entree) -> None:
    """AC 2.1 -- parametres nommes, **aucun objet `args`**.

    Le modele est `scan_detect.run_scan_detect` et
    `scan_write.ecrire_le_lot_detecte` : un seul parametre positionnel, le
    dossier projet, et tout le reste **nomme**. Un `args` argparse est ce qui
    rendait ce corps inappelable depuis une interface -- c'est le fait F1 de la
    11.4b, et la raison d'etre de ce deplacement.
    """
    parametres = inspect.signature(entree).parameters
    assert "args" not in parametres
    positionnels = [nom for nom, p in parametres.items()
                    if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    assert positionnels == ["project_dir"], positionnels
    # Le canal de progression du lot B4 est CABLE sur les deux (tache B5), et
    # il est optionnel : l'absence de rappel ne change rien a l'observable.
    assert "rappel_progression" in parametres
    assert parametres["rappel_progression"].default is None
    # Et le journal est optionnel lui aussi : une interface n'en passe aucun.
    assert parametres["logger"].default is None


def test_l_ensemble_des_motifs_de_refus_est_EXACTEMENT_la_table(  ) -> None:
    """AC 2.3 -- ensemble **exact**, jamais une inclusion.

    Les deux moities comptent : un motif leve hors de la table serait un refus
    qu'aucune interface ne saurait nommer, et un motif de la table qu'aucun
    `raise` n'atteint serait une promesse vide. « Ce refus existe » ne mesure
    rien ; « l'ensemble des motifs atteignables est exactement celui-ci »
    mesure l'exception ET son unicite.
    """
    assert _motifs_leves_par_le_source() == set(makepdf_noyau.MOTIFS_DE_REFUS)


def _instance_de(classe: type) -> BaseException:
    """Une instance de `classe`, quel que soit ce que son `__init__` exige.

    Les familles qui demandent plus d'un argument sont nommees une a une : un
    `except` generique fabriquerait `object()` et mesurerait autre chose.
    """
    if classe is json.JSONDecodeError:
        return classe("motif de banc", "{", 0)
    return classe("motif de banc")


class _ArgsDeBanc:
    """Le `args` que l'enveloppe lit, reduit a ce qu'elle lit vraiment."""

    lot = "un-lot"
    rush = fps = orientation = frames_par_page = marge = None
    nombre_patchs = gamut_map = dpi = format = geometrie = None
    overwrite = False

    def __init__(self, project) -> None:
        self.project = str(project)


@pytest.mark.parametrize(
    "classe", makepdf_noyau.REFUS_NOMMES,
    ids=lambda c: c.__name__)
def test_chaque_refus_de_la_table_sort_de_l_enveloppe_en_CODE_1(
    classe, projet_a_trois_planches, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """AC 2.3, volet symetrique -- la table est celle que la CLI sait traiter.

    Un refus que le coeur leve et que l'enveloppe n'attrape pas sortirait de
    `mmu makepdf` en **trace Python nue** au lieu du `Erreur: ...` + code `1`
    que le contrat exige. C'est ce que mesure ce test, et il le mesure en
    **jouant** l'enveloppe : le corps est remplace par une levee de chaque
    famille de la table, une par une, et le code rendu doit valoir `1`.

    Le motif de la forme est celui du dossier d'identite du scan : chaque
    entree de la table se construit **avec un seul message**, pour que le
    parcours couvre y compris les familles qu'aucun refus reel n'atteint. Une
    exception qui exigerait deux arguments sortirait de la mesure -- et c'est
    exactement le survivant qui a fait ecrire ce banc-la.
    """
    from mixed_media_utility import cli

    def _corps_qui_refuse(*args, **kwargs):
        raise _instance_de(classe)

    monkeypatch.setattr(makepdf_noyau, "generer_les_planches_du_lot",
                        _corps_qui_refuse)
    code = cli.makepdf_command(
        _ArgsDeBanc(projet_a_trois_planches["project_dir"]))
    assert code == 1, (classe, code)


def test_une_exception_HORS_table_remonte_au_lieu_d_etre_deguisee(
    projet_a_trois_planches, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC 2.3, l'autre moitie de l'ensemble exact -- la table est FERMEE.

    Sans ce volet, un `except Exception` large rendrait le test precedent vert
    pour toutes les familles **et** deguiserait les bugs internes en erreurs
    operateur. C'est le defaut nomme par la revue 4.1 du 2026-08-06, et
    l'enveloppe l'evite en enumerant ses familles par classe.
    """
    from mixed_media_utility import cli

    class _BugInterne(Exception):
        pass

    def _corps_qui_bugue(*args, **kwargs):
        raise _BugInterne("ceci n'est pas un refus operateur")

    monkeypatch.setattr(makepdf_noyau, "generer_les_planches_du_lot",
                        _corps_qui_bugue)
    with pytest.raises(_BugInterne):
        cli.makepdf_command(
            _ArgsDeBanc(projet_a_trois_planches["project_dir"]))


def test_une_interruption_clavier_sort_de_l_enveloppe_en_CODE_130(
    projet_a_trois_planches, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC 2.5 -- le troisieme code du contrat, `130`, et lui seul.

    `KeyboardInterrupt` derive de `BaseException` et non d'`Exception` : elle
    ne figure dans aucune table de refus, et c'est pour cela qu'elle se mesure
    a part. Sans ce test, le seul code jamais mesure serait `1`.
    """
    from mixed_media_utility import cli

    def _corps_interrompu(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(makepdf_noyau, "generer_les_planches_du_lot",
                        _corps_interrompu)
    code = cli.makepdf_command(
        _ArgsDeBanc(projet_a_trois_planches["project_dir"]))
    assert code == 130


def test_l_ordre_des_gardes_est_DECLARE_et_complet() -> None:
    """AC 2.4 -- l'ordre est ecrit, et il porte les neuf etapes du corps.

    Une declaration ne mesure rien a elle seule ; c'est le test suivant qui
    mesure **laquelle** parle. Celui-ci tient le cardinal : retirer une etape
    de la table retirerait une etape de la mesure en silence.
    """
    assert makepdf_noyau.ORDRE_DES_GARDES == (
        "projet", "manifest", "designation_du_lot", "conformite_du_lot",
        "rang_de_version", "composition", "conflit_de_sortie", "rendu",
        "declaration_au_manifest",
    )


@pytest.mark.parametrize(
    "premiere, seconde, arguments",
    [
        # Deux gardes fautives a la fois : c'est la PREMIERE de l'ordre qui
        # parle. « Un refus qui arrive apres une destruction n'est pas un
        # refus » (`EPIC5-ARB-34`, transpose du scan a l'impression).
        ("manifest", "designation_du_lot", {}),
        ("designation_du_lot", "conformite_du_lot",
         {"lot": "lot-inconnu", "rush": "rush-001", "fps": 5.0}),
        ("conformite_du_lot", "composition",
         {"lot": "lot-inconnu", "frames_per_page": 7}),
    ],
)
def test_c_est_la_PREMIERE_garde_de_l_ordre_qui_parle(
    projet_a_trois_planches, premiere, seconde, arguments, tmp_path
) -> None:
    """AC 2.4 -- l'ordre, mesure sur des couples ou DEUX gardes pourraient parler.

    Sans couple, un ordre ne se mesure pas : chaque garde prise seule refuse
    correctement quel que soit son rang. C'est en les faisant tomber ensemble
    que le rang devient observable.
    """
    ordre = makepdf_noyau.ORDRE_DES_GARDES
    assert ordre.index(premiere) < ordre.index(seconde), (premiere, seconde)

    projet = projet_a_trois_planches["project_dir"]
    if premiere == "manifest":
        # Le manifest disparait ET la designation est fautive (ni lot, ni couple).
        projet = tmp_path / "sans-manifest"
        projet.mkdir()
    with pytest.raises(makepdf_noyau.RefusDeMakepdf) as leve:
        makepdf_noyau.generer_les_planches_du_lot(projet, **arguments)

    motifs = {
        "manifest": makepdf_noyau.MOTIF_MANIFEST_ABSENT,
        "designation_du_lot": makepdf_noyau.MOTIF_DESIGNATION_DU_LOT,
        "conformite_du_lot": makepdf_noyau.MOTIF_LOT_NON_CONFORME,
    }
    assert leve.value.motif == motifs[premiere]


def test_la_declaration_au_manifest_vient_APRES_l_ecriture_du_PDF(
    projet_a_trois_planches, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC 2.4, derniere etape de l'ordre -- et elle se mesure a l'ENVERS.

    On fait echouer la declaration : si elle precedait le rendu, aucun PDF ne
    serait sur le disque. Le PDF DOIT y etre -- « un manifest qui declarerait
    `state: "pdf"` alors que le rendu a echoue decrirait une planche que
    personne n'a » (story 5.11).

    La mesure porte aussi sur le **chemin porte par l'exception** : c'est lui
    que l'enveloppe imprime (« Le PDF ... a bien ete ecrit et reste en place »),
    et sans lui la phrase nommerait `None`.
    """
    from mixed_media_utility.io import pdf_manifest as manifeste

    def _persistance_qui_echoue(*args, **kwargs):
        raise manifeste.PdfPersistenceError("declaration impossible")

    monkeypatch.setattr(manifeste, "persist_pdf_generation", _persistance_qui_echoue)

    with pytest.raises(manifeste.PdfPersistenceError) as leve:
        makepdf_noyau.generer_les_planches_du_lot(
            projet_a_trois_planches["project_dir"],
            lot=projet_a_trois_planches["lot_id"],
            frames_per_page=FRAMES_PAR_PAGE,
        )

    chemin = getattr(leve.value, "pdf_path", None)
    assert chemin is not None, "l'echec ne porte pas le chemin du PDF ecrit"
    assert Path(chemin).is_file(), (
        "le PDF n'est pas sur le disque : la declaration au manifest est "
        "passee AVANT le rendu."
    )


# ===========================================================================
# Fermetures de la CAMPAGNE DE MUTATION du lot B (suite)
# ===========================================================================
#
# Trente-quatre mutants declares, trente-trois injectes, vingt-six tues d'emblee.
# Les sept survivants sont fermes ici, et chacun disait la meme chose sous une
# forme differente : **le dossier d'identite mesure le chemin que la CLI
# emprunte, jamais celui qu'elle n'emprunte pas.** Un banc de bout en bout ne
# voit que les branches que ses scenarios traversent -- c'est la raison meme
# pour laquelle la politique exige une campagne, et pas une relecture.
#
# Aucune de ces fermetures ne touche le produit : elles n'ajoutent que des
# tests. La regle `la-reprise-d-un-finding-se-revoit-aussi` (`CLAUDE.md`, 5 bis)
# ne demande donc rien de plus que la reinjection du mutant, verdict porte a la
# ligne de chaque test.
#
# Un piege d'outillage a ete paye pendant cette campagne, et le garde-fou l'a
# attrape : une course tuee par le harnais **au milieu** d'un mutant laisse
# l'arbre mute, et les mutants suivants mesurent alors l'arbre du voisin -- le
# faux vert exact que `CLAUDE.md` decrit. L'injecteur verifie `git diff` APRES
# restauration et refuse de journaliser un arbre sale ; c'est ce refus qui a
# rendu la contamination visible au lieu de la laisser passer en verdicts.


def test_le_canal_de_progression_est_CABLE_du_point_d_entree_au_rendu(
    projet_a_trois_planches,
) -> None:
    """Ferme `M17` -- `rappel_progression=rappel_progression` -> `=None`.

    **C'est la tache B5 elle-meme**, et rien ne la mesurait : le canal etait
    livre par le lot B4 et branche nulle part, exactement l'etat qu'Egan a fait
    corriger le 2026-09-02 (« Il faut le faire »). Le mutant qui coupe le fil
    entre le point d'entree et `render_lot_pdf` survivait a soixante-seize
    tests -- le dossier d'identite ne pouvait pas le voir, la CLI ne passant
    aucun rappel.

    La mesure est l'egalite de SUITE, jamais une appartenance : un jalon
    present laisserait passer un doublon, un trou et tout jalon supplementaire.

    *Mutant reinjecte : TUE.*
    """
    jalons: list[tuple[int, int]] = []
    resultat = makepdf_noyau.generer_les_planches_du_lot(
        projet_a_trois_planches["project_dir"],
        lot=projet_a_trois_planches["lot_id"],
        frames_per_page=FRAMES_PAR_PAGE,
        rappel_progression=lambda faites, total: jalons.append((faites, total)),
    )
    attendu = [(rang, resultat.plan.page_count)
               for rang in range(1, resultat.plan.page_count + 1)]
    assert jalons == attendu
    assert resultat.plan.page_count == PAGES_ATTENDUES


def test_le_canal_de_progression_est_CABLE_aussi_sur_la_MIRE(
    projet_a_trois_planches,
) -> None:
    """Ferme `M18` -- le meme fil, coupe sur le second point d'entree.

    Deux points d'entree, deux fils : mesurer l'un ne dit rien de l'autre, et
    `M17` et `M18` ont survecu **independamment**. La mire n'a qu'une page,
    donc son unique jalon vaut `(1, 1)` -- ce qui est aussi ce que le lot B4
    avait gele au niveau du rendu.

    *Mutant reinjecte : TUE.*
    """
    jalons: list[tuple[int, int]] = []
    resultat = makepdf_noyau.generer_la_page_de_calibration(
        projet_a_trois_planches["project_dir"],
        scan_chain_label=CHAINE_DE_SCAN,
        rappel_progression=lambda faites, total: jalons.append((faites, total)),
    )
    assert jalons == [(1, resultat.plan.page_count)]
    assert resultat.plan.page_count == pdf_composition.CALIBRATION_ONLY_PAGE_COUNT


def test_l_ABSENCE_de_rappel_ne_change_rien_aux_deux_points_d_entree(
    projet_a_trois_planches, tmp_path
) -> None:
    """`AR3`, volet symetrique du cablage : optionnel ne veut pas dire casse.

    Sans ce volet, le cablage pourrait devenir **obligatoire** sans que rien ne
    rougisse -- et la CLI, qui n'en passe aucun, se mettrait a lever.
    """
    resultat = makepdf_noyau.generer_les_planches_du_lot(
        projet_a_trois_planches["project_dir"],
        lot=projet_a_trois_planches["lot_id"],
        frames_per_page=FRAMES_PAR_PAGE,
    )
    assert resultat.output_path.is_file()
    assert _cardinal_de_pages(resultat.output_path) == resultat.plan.page_count


def test_le_defaut_d_espace_couleur_est_ECRIT_au_manifest_et_journalise(
    projet_a_trois_planches, caplog
) -> None:
    """Ferme `M10` et `M11` -- deux survivants d'une meme branche jamais prise.

    Le dossier d'identite part d'un projet dont `color.target_colorspace` est
    **deja** renseigne : la branche du defaut n'y est jamais traversee, donc ni
    la seconde validation du manifest (`M10`) ni la valeur ecrite (`M11`) n'y
    etaient mesurees. C'est la branche qu'Egan a fait poser le 2026-08-13 pour
    que `makepdf` cesse de refuser un projet ou personne n'a saisi cette
    valeur a la main.

    **La valeur est EPINGLEE, et ce n'est pas une recopie de commodite** : elle
    est une decision produit, alignee sur ce que les projets existants du depot
    portent deja. C'est un gel de sortie, du meme genre que les formes
    canoniques du depot, et c'est la seule facon de tuer le mutant qui la
    remplace par sa voisine `MVP_TARGET_COLORSPACE` -- un test qui la relirait
    du module serait tautologique.

    *Mutants reinjectes : TUES tous les deux.*
    """
    import logging

    projet = projet_a_trois_planches["project_dir"]
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    couleur = dict(manifest.get("color") or {})
    couleur.pop("target_colorspace", None)
    manifest["color"] = couleur
    (projet / "project.json").write_text(json.dumps(manifest, indent=2),
                                         encoding="utf-8")

    with caplog.at_level(logging.INFO):
        resultat = makepdf_noyau.generer_les_planches_du_lot(
            projet, lot=projet_a_trois_planches["lot_id"],
            frames_per_page=FRAMES_PAR_PAGE,
        )

    assert resultat.espace_couleur_par_defaut == "bt709"
    assert makepdf_noyau.DEFAULT_TARGET_COLORSPACE == "bt709"
    # La valeur est bien PERSISTEE, pas seulement rendue.
    ecrit = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    assert ecrit["color"]["target_colorspace"] == "bt709"
    # ... et le manifest RELU est celui qui a servi : sans la seconde
    # validation, la composition aurait travaille sur le manifest d'avant.
    assert resultat.plan.page_count == PAGES_ATTENDUES
    assert any("color.target_colorspace absent du manifest" in ligne.message
               for ligne in caplog.records)


def test_le_defaut_d_espace_couleur_vaut_aussi_pour_la_MIRE(
    projet_a_trois_planches,
) -> None:
    """Ferme `M10`, second point d'entree -- la mire relit elle aussi.

    Le mutant `M10` porte sur la seconde `validate_manifest` de la **mire** :
    sans elle, `compose_calibration_page_plan` recevrait le manifest d'avant
    l'ecriture du defaut, donc un manifest sans espace couleur cible.
    """
    projet = projet_a_trois_planches["project_dir"]
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    couleur = dict(manifest.get("color") or {})
    couleur.pop("target_colorspace", None)
    manifest["color"] = couleur
    (projet / "project.json").write_text(json.dumps(manifest, indent=2),
                                         encoding="utf-8")

    resultat = makepdf_noyau.generer_la_page_de_calibration(
        projet, scan_chain_label=CHAINE_DE_SCAN)
    assert resultat.espace_couleur_par_defaut == "bt709"
    assert resultat.output_path.is_file()


def test_les_avertissements_du_plan_sont_TOUS_relayes_au_journal(
    projet_a_trois_planches, monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    """Ferme `M08` -- `for warning in plan.warnings:` suivi d'un `break`.

    Aucun scenario du dossier d'identite ne compose un plan qui porte des
    avertissements structurels, donc la boucle n'etait jamais parcourue au-dela
    de zero tour. Un mutant de terminaison y survit par construction.

    **Trois avertissements DISTINGUABLES, et la cible est celui du MILIEU**
    (regle des fabriques, point 2 bis) : deux suffiraient a montrer qu'on
    depasse le premier tour, mais placeraient la cible en seconde ET en
    derniere position, ou un `break` et un rendu complet sont indiscernables.

    *Mutant reinjecte : TUE.*
    """
    import logging

    veritable = pdf_composition.compose_lot_plan
    avertissements = ("AVERTISSEMENT_PREMIER", "AVERTISSEMENT_DU_MILIEU",
                      "AVERTISSEMENT_DERNIER")

    def _plan_bavard(*args, **kwargs):
        return dataclasses.replace(veritable(*args, **kwargs),
                                   warnings=list(avertissements))

    monkeypatch.setattr(pdf_composition, "compose_lot_plan", _plan_bavard)

    with caplog.at_level(logging.WARNING):
        makepdf_noyau.generer_les_planches_du_lot(
            projet_a_trois_planches["project_dir"],
            lot=projet_a_trois_planches["lot_id"],
            frames_per_page=FRAMES_PAR_PAGE,
        )

    releves = [ligne.message for ligne in caplog.records
               if ligne.message in avertissements]
    assert releves == list(avertissements)


def test_le_refus_DEFENSIF_de_conflit_protege_encore_un_tirage_existant(
    projet_a_trois_planches, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ferme `M04` -- le conflit de sortie des planches, devenu inatteignable.

    Depuis le lot B0 bis, le rang avance a chaque passe : le nom vise est
    toujours neuf, **aucun parcours d'operateur ne mene plus a ce refus**, et
    c'est pour cela qu'il survivait a l'ensemble du dossier d'identite. Le
    retirer serait pourtant la faute exacte qu'il existe pour ecarter.

    On mesure donc la seule route qui y mene encore, et elle n'est pas
    theorique : **un resolveur de rang qui sous-estime**. C'est le mode de
    panne que le lot B0 ter vient de fermer par une autre porte (un tirage
    d'une autre mise en page invisible a l'enumeration), et la question que ce
    test tranche est ce qui se passe **s'il revenait** : le tirage present
    est-il detruit, ou le refus parle-t-il ? Il doit parler, et porter le
    chemin reellement vise.

    *Mutant reinjecte : TUE.*
    """
    projet = projet_a_trois_planches["project_dir"]
    premier = makepdf_noyau.generer_les_planches_du_lot(
        projet, lot=projet_a_trois_planches["lot_id"],
        frames_per_page=FRAMES_PAR_PAGE)
    octets = premier.output_path.read_bytes()

    # Le resolveur sous-estime : il rend a nouveau le rang de l'origine.
    monkeypatch.setattr(pdf_composition, "resolve_sheets_version_rank",
                        lambda *args, **kwargs: 1)

    with pytest.raises(makepdf_noyau.ConflitDeSortie) as leve:
        makepdf_noyau.generer_les_planches_du_lot(
            projet, lot=projet_a_trois_planches["lot_id"],
            frames_per_page=FRAMES_PAR_PAGE)

    assert leve.value.output_path == premier.output_path
    assert leve.value.motif == makepdf_noyau.MOTIF_CONFLIT_DE_SORTIE
    # Et le tirage present est INTACT : « un refus qui arrive apres une
    # destruction n'est pas un refus ».
    assert premier.output_path.read_bytes() == octets


def test_la_table_des_refus_est_EXACTEMENT_ce_que_l_enveloppe_attrape() -> None:
    """Ferme `M24` -- retirer `ValidationError` de `REFUS_NOMMES`.

    Le test qui parcourt la table ne pouvait pas voir ce mutant : retirer une
    entree lui fait simplement jouer un cas de moins. C'est le defaut que
    `CLAUDE.md` nomme -- « une assertion positive laisse passer toute
    divergence supplementaire » --, ici dans sa forme symetrique : une table
    amputee laisse passer toute famille manquante.

    La mesure lit la pile d'`except` des **deux** enveloppes a l'AST et la
    confronte a la table. L'ecart admis est un ensemble **exact** de deux
    classes, chacune avec son motif : `LotNonConforme`, qui est une
    sous-classe de `RefusDeMakepdf` deja presente et que l'enveloppe traite a
    part pour mettre en forme ses constats ; et `KeyboardInterrupt`, qui derive
    de `BaseException` et n'est pas un refus metier -- elle rend `130`, pas `1`.

    *Mutant reinjecte : TUE.*
    """
    from mixed_media_utility import cli

    def _resoudre(noeud):
        if isinstance(noeud, ast.Name):
            return getattr(cli, noeud.id, None) or getattr(
                __import__("builtins"), noeud.id, None)
        if isinstance(noeud, ast.Attribute):
            porteur = _resoudre(noeud.value)
            return getattr(porteur, noeud.attr, None) if porteur else None
        return None

    arbre = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
    attrapees = set()
    for noeud in ast.walk(arbre):
        if not (isinstance(noeud, ast.FunctionDef)
                and noeud.name in ("makepdf_command",
                                   "makepdf_calibration_page_command")):
            continue
        for gestionnaire in ast.walk(noeud):
            if not isinstance(gestionnaire, ast.ExceptHandler):
                continue
            types = (gestionnaire.type.elts
                     if isinstance(gestionnaire.type, ast.Tuple)
                     else [gestionnaire.type])
            for cible in types:
                classe = _resoudre(cible)
                assert classe is not None, ast.dump(cible)
                attrapees.add(classe)

    assert attrapees, "aucune enveloppe trouvee : la lecture ne mesure rien"
    assert attrapees - set(makepdf_noyau.REFUS_NOMMES) == {
        makepdf_noyau.LotNonConforme, KeyboardInterrupt,
    }
    assert set(makepdf_noyau.REFUS_NOMMES) - attrapees == set()
