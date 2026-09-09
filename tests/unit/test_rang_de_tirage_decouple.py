"""Le rang de tirage se decouple de `--nouvelle-version` -- lot B0 bis, AC 2.10.

**C'est une correction de DEFAUT, et le defaut n'existait pas encore quand la
mesure l'a trouve** (`mesure-2026-09-02-rebond-de-coeur-arb-171.md`). Il nait au
moment ou le nom d'un tirage porte sa mise en page, et personne ne l'avait vu :
ni la relecture d'Egan, ni les deux arbitrages qui le produisent ensemble.

Le mecanisme, en trois lignes de code separees par trente-sept :

* le rang n'avancait que derriere `if getattr(args, "nouvelle_version", False)` ;
* le conflit se declenchait plus bas, sur `output_path.exists()` ;
* les deux etaient **couples par le parcours de l'operateur** -- le seul
  evenement qui poussait a passer le drapeau etait le message de conflit.

Des que le nom porte la mise en page, relancer le meme lot dans une autre forme
ne declenche plus de conflit -- c'est ce qu'`EPIC11-ARB-175` veut -- mais ne
calcule plus le rang non plus. Le PDF sort **sans fragment `_vN`**,
`rang_ecrit = record.version_rank or 1` le declare **au rang 1**, et l'en-tete
imprime comme le QR portent « tirage 1 » sur un lot qui en est a son quatrieme.
C'est le mensonge sur papier qu'`EPIC11-ARB-92` existe pour interdire.

Ce banc mesure les **quatre porteurs** en ensemble exact, parce qu'un rang pose
sur trois d'entre eux est exactement la panne : c'est le quatrieme, sur le
papier, que plus rien ne rattrape une fois l'encre seche.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from mixed_media_utility import cli, page_templates, pdf_composition
from mixed_media_utility.frame_selection import select_source_frames
from mixed_media_utility.io import naming, pdf_manifest, project_layout
from mixed_media_utility.io import payload as payload_io
from mixed_media_utility.io.extraction_manifest import (
    ExtractionRecord,
    build_extraction_manifest,
)


PROJET = "proj-rang"
RUSH = "rush-rang"
FPS_SOURCE = 25.0
FPS_TARGET = 5.0
SOURCE_FRAME_COUNT = 50  # -> 10 frames extraites

#: **Derive, jamais recopie** : c'est `build_lot_id` qui compose
#: `<rush>_<cadence-courte>`, et l'ecrire a la main ici perimerait a la
#: premiere convention de cadence qui bougerait.
LOT = naming.build_lot_id(RUSH, FPS_TARGET)


def _gabarit(orientation: str, cardinal: int) -> str:
    return page_templates.build_template_id(
        orientation, cardinal, page_templates.DEFAULT_MARGIN_PRESET)


#: **TROIS formes distinctes, la cible AU MILIEU.** La liste que le code
#: parcourt est celle des gabarits du registre ; ce qui est vise ici est la
#: forme du QUATRIEME tirage, et elle n'est ni la premiere ni la derniere de
#: celles deja posees -- une fabrique a deux formes placerait la cible en second
#: ET en dernier, ou un mutant de terminaison de boucle survit (regle des
#: fabriques, point 2 bis).
FORMES_DEJA_TIREES = (
    (page_templates.ORIENTATION_PORTRAIT, 2),
    (page_templates.ORIENTATION_PAYSAGE, 4),
    (page_templates.ORIENTATION_PORTRAIT, 8),
)
#: La forme de la relance : une quatrieme, differente des trois.
FORME_DE_LA_RELANCE = (page_templates.ORIENTATION_PAYSAGE, 8)


def _projet_reel(racine: Path) -> dict:
    """Un projet **reel** sur disque : manifest de la vraie fabrique + TIFF.

    Ce banc ne se paie pas un manifeste de synthese : la commande valide son
    manifeste contre le schema avant tout le reste, et un dictionnaire ecrit a
    la main ferait echouer `makepdf` **avant** le point que ce banc mesure --
    c'est-a-dire qu'il rendrait vert un banc qui n'observe rien.
    """
    projet = racine / "projet"
    project_layout.ensure_project_layout(projet)

    selection = select_source_frames(fps_source=FPS_SOURCE, fps_target=FPS_TARGET,
                                     source_frame_count=SOURCE_FRAME_COUNT)
    lot_id = LOT
    frames_relatif = (f"{project_layout.FRAMES_DIRNAME}/"
                      f"{project_layout.rush_dir_slug(RUSH, FPS_TARGET)}")
    manifest = build_extraction_manifest(None, ExtractionRecord(
        project_id=PROJET, rush_id=RUSH, rush_source_name=f"{RUSH}.mov",
        lot_id=lot_id, frames_dir_relative=frames_relatif, selection=selection,
        fps_source=FPS_SOURCE, fps_target=FPS_TARGET,
        source_width=1920, source_height=1080, source_fields={},
        confirmation_mode="non_interactif", unknown_color_accepted=True,
        confirmed_at="2026-09-02T00:00:00Z"))
    manifest["color"]["target_colorspace"] = "rec709"

    dossier = projet / Path(frames_relatif)
    dossier.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    for frame in selection.frames:
        nom = naming.build_extracted_frame_filename(
            RUSH, FPS_TARGET, frame.frame_timecode)
        image = rng.integers(0, 65535, size=(108, 192, 3), dtype=np.uint16)
        assert cv2.imwrite(str(dossier / nom), image)
    return {"projet": projet, "manifest": manifest, "lot_id": lot_id}


@pytest.fixture()
def projet_a_trois_tirages(tmp_path: Path) -> dict:
    """Un lot qui a DEJA trois tirages, de trois mises en page distinctes.

    Les trois sont declares au manifeste **et** poses sur le disque : les deux
    routes que `sheets_version_watermark` consulte doivent dire la meme chose,
    et une fixture qui n'en peuplerait qu'une laisserait l'autre non mesuree.

    Le lot vise est place **au milieu** de trois lots : le code retrouve son
    `rush_id` par un `next(... if lot_id == ...)`, et un `find` fautif rendant
    toujours le premier -- ou une boucle qui s'arreterait au dernier -- ne se
    demasque pas autrement.
    """
    monde = _projet_reel(tmp_path)
    projet, manifest, lot_id = monde["projet"], monde["manifest"], monde["lot_id"]

    inventaire = []
    for rang, (orientation, cardinal) in enumerate(FORMES_DEJA_TIREES, start=1):
        nom = naming.build_sheets_pdf_filename(
            PROJET, RUSH, lot_id, version_rank=None if rang == 1 else rang,
            template_id=_gabarit(orientation, cardinal))
        (projet / project_layout.PLANCHES_DIRNAME / nom).write_bytes(
            f"tirage-{rang}".encode())
        entree = {pdf_manifest.SHEETS_INVENTORY_KEY:
                  f"{project_layout.PLANCHES_DIRNAME}/{nom}"}
        if rang > 1:
            entree["version_rank"] = rang
        inventaire.append(entree)

    cible = manifest["lots"][0]
    cible[pdf_manifest.SHEETS_INVENTORY_FIELD] = inventaire
    cible[pdf_manifest.SHEETS_WATERMARK_FIELD] = len(FORMES_DEJA_TIREES)
    leurre_avant = {"lot_id": "AVANT_12", "rush_id": "rush-avant"}
    leurre_apres = {"lot_id": "APRES_25", "rush_id": "rush-apres"}
    manifest["lots"] = [leurre_avant, cible, leurre_apres]

    (projet / "project.json").write_text(json.dumps(manifest, indent=2),
                                         encoding="utf-8")
    return {"projet": projet, "manifest": manifest, "lot_id": lot_id}


# ---------------------------------------------------------------------------
# B0b.1 / B0b.3 -- le rang est calcule SANS le drapeau, et il vaut 4
# ---------------------------------------------------------------------------


def test_relancer_dans_une_AUTRE_forme_SANS_drapeau_donne_le_rang_4(
        projet_a_trois_tirages):
    """**La mesure qui tue le defaut** (AC 2.10a), sur les QUATRE porteurs.

    Le lot a trois tirages ; on le relance dans une quatrieme mise en page,
    **sans** `--nouvelle-version`. C'est exactement le parcours que la mesure du
    2026-09-02 decrit, et celui qui produisait « tirage 1 » sur un quatrieme
    tirage.

    Les quatre porteurs sont assertes en **ensemble exact** et non l'un d'eux :
    le nom du fichier protege le disque, l'etiquette imprimee protege l'oeil, le
    champ `vr` du QR protege la machine qui scanne, et l'inventaire protege le
    calcul du rang suivant. Un rang pose sur trois d'entre eux est la panne.
    """
    projet = projet_a_trois_tirages["projet"]
    manifest = projet_a_trois_tirages["manifest"]
    orientation, cardinal = FORME_DE_LA_RELANCE

    rang = pdf_composition.resolve_sheets_version_rank(
        projet, project_id=PROJET, rush_id=RUSH, lot_id=LOT, manifest=manifest)
    assert rang == 4, rang

    # Porteur 1 -- le NOM.
    nom = naming.build_sheets_pdf_filename(
        PROJET, RUSH, LOT, version_rank=rang,
        template_id=_gabarit(orientation, cardinal))
    assert nom.endswith(f"_{cardinal}f-{orientation[:3]}_v4.pdf"), nom

    # Porteurs 2 et 3 -- l'ETIQUETTE imprimee et le champ `vr` du QR, lus sur un
    # plan reellement compose.
    plan = _composer(projet_a_trois_tirages, rang, orientation, cardinal)
    assert plan.pdf_filename == nom
    for page in plan.pages:
        assert page.text.sheet_label.endswith(
            naming.format_version_suffix(4)), page.text.sheet_label
        assert page.qr.payload[payload_io.VERSION_RANK_FIELD] == 4

    # Porteur 4 -- l'INVENTAIRE, apres declaration au manifeste. Le chemin
    # declare est le chemin REELLEMENT ecrit (`EPIC11-ARB-90`), pas un chemin
    # recompose.
    pdf_manifest.persist_pdf_generation(
        projet,
        pdf_manifest.PdfRecord.from_plan(
            plan, pdf_path=f"{project_layout.PLANCHES_DIRNAME}/{nom}",
            version_rank=rang))
    document = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    lot = next(entree for entree in document["lots"] if entree["lot_id"] == LOT)
    rangs = {entree.get("version_rank", 1)
             for entree in lot[pdf_manifest.SHEETS_INVENTORY_FIELD]}
    assert rangs == {1, 2, 3, 4}, rangs
    assert lot[pdf_manifest.SHEETS_WATERMARK_FIELD] == 4


def _composer(fixture, rang, orientation, cardinal):
    """Le plan reel, compose par le coeur -- jamais un plan de synthese."""
    return pdf_composition.compose_lot_plan(
        manifest=fixture["manifest"],
        lot_id=fixture["lot_id"],
        orientation=orientation,
        frames_per_page=cardinal,
        version_rank=rang,
    )


# ---------------------------------------------------------------------------
# B0b.2 / B0b.5 -- le drapeau n'est plus la condition, et le conflit disparait
# ---------------------------------------------------------------------------


def test_le_drapeau_ne_change_RIEN_au_rang_calcule(projet_a_trois_tirages):
    """AC 2.10b : `--nouvelle-version` cesse d'etre la **condition** du calcul.

    Le resolveur ne le connait pas et ne l'a jamais connu -- c'est `cli.py` qui
    le consultait. Ce test tient la moitie mesurable au coeur : le rang est un
    fait des que le lot et son inventaire sont connus, ce qui est aussi ce
    qu'`EPIC11-ARB-172` exige de l'ecran de confirmation.
    """
    projet, manifest = (projet_a_trois_tirages["projet"],
                        projet_a_trois_tirages["manifest"])
    rangs = {pdf_composition.resolve_sheets_version_rank(
        projet, project_id=PROJET, rush_id=RUSH, lot_id=LOT, manifest=manifest)
        for _ in range(3)}
    assert rangs == {4}, rangs
    # Et **lire un rang ne le consomme pas** : la ligne d'eau du manifeste est
    # inchangee, et rien n'a ete depose dans `planches/`.
    lot = next(e for e in manifest["lots"] if e["lot_id"] == LOT)
    assert lot[pdf_manifest.SHEETS_WATERMARK_FIELD] == 3
    assert len(list((projet / project_layout.PLANCHES_DIRNAME).iterdir())) == 3


def test_changer_de_mise_en_page_ne_declenche_PLUS_de_conflit(
        projet_a_trois_tirages):
    """AC 2.10d, mesuree comme une **ABSENCE** (`EPIC11-ARB-175`, cons. 3).

    Le chemin de sortie de la relance ne doit exister nulle part sur le disque :
    aucun conflit ne peut donc se declencher, et il n'y a rien a ecraser. C'est
    une propriete plus forte que « le code de retour est 0 » -- celui-la serait
    vert sur un ecrasement silencieux.
    """
    projet = projet_a_trois_tirages["projet"]
    orientation, cardinal = FORME_DE_LA_RELANCE
    rang = pdf_composition.resolve_sheets_version_rank(
        projet, project_id=PROJET, rush_id=RUSH, lot_id=LOT,
        manifest=projet_a_trois_tirages["manifest"])
    nom = naming.build_sheets_pdf_filename(
        PROJET, RUSH, LOT, version_rank=rang,
        template_id=_gabarit(orientation, cardinal))

    patches = projet / project_layout.PLANCHES_DIRNAME
    assert not (patches / nom).exists(), nom
    # Volet symetrique : les trois tirages deja poses, eux, existent bien -- sans
    # quoi l'absence ci-dessus serait celle d'un dossier vide.
    assert len(sorted(patches.glob("*.pdf"))) == 3


# ---------------------------------------------------------------------------
# B0b.4 -- le repli de rang 1, et la garde DEJA ECRITE qui n'est pas reecrite
# ---------------------------------------------------------------------------


def test_un_lot_JAMAIS_imprime_rend_le_rang_1_et_AUCUN_fragment(tmp_path):
    """AC 2.10b : le tirage d'ORIGINE, pas une « version 2 de rien ».

    La garde vit deja dans `resolve_sheets_version_rank` (« aucun tirage,
    jamais : le prochain est l'ORIGINE ») et n'est **pas** reecrite par cette
    story : ce test la mesure, il ne la double pas.
    """
    projet = tmp_path / "vierge"
    (projet / project_layout.PLANCHES_DIRNAME).mkdir(parents=True)
    manifest = {"project_id": PROJET,
                "lots": [{"lot_id": LOT, "rush_id": RUSH}]}

    rang = pdf_composition.resolve_sheets_version_rank(
        projet, project_id=PROJET, rush_id=RUSH, lot_id=LOT, manifest=manifest)
    assert rang == 1

    nom = naming.build_sheets_pdf_filename(
        PROJET, RUSH, LOT, version_rank=None,
        template_id=_gabarit(*FORME_DE_LA_RELANCE))
    assert "_v" not in nom, nom


def test_le_payload_OMET_STRICTEMENT_le_rang_1(projet_a_trois_tirages):
    """`EPIC11-ARB-91` : « `v` absent vaut 1 ».

    L'omission est **stricte** : la cle ne doit pas apparaitre avec la valeur 1.
    Un payload qui l'ecrirait couterait des octets dans un budget QR deja
    mesure, et ferait mentir la convention de lecture.
    """
    plan = _composer(projet_a_trois_tirages, None, *FORME_DE_LA_RELANCE)
    for page in plan.pages:
        assert payload_io.VERSION_RANK_FIELD not in page.qr.payload
        assert payload_io.payload_version_rank(page.qr.payload) == 1
        assert not page.text.sheet_label.endswith("_v1")


# ---------------------------------------------------------------------------
# Le decouplage, mesure sur la VRAIE commande
# ---------------------------------------------------------------------------


def test_la_commande_resout_le_rang_SANS_qu_on_lui_passe_le_drapeau(
        projet_a_trois_tirages, monkeypatch):
    """La moitie qui vit dans `cli.py`, et c'est la ou le defaut logeait.

    La sonde remplace le resolveur pour compter ses appels : le point mesure
    n'est pas la valeur rendue -- les tests ci-dessus s'en chargent -- mais le
    fait que la commande l'APPELLE alors qu'aucun drapeau n'est passe. Un
    mutant qui remettrait le calcul derriere `if args.nouvelle_version` rendrait
    ce compteur a zero.
    """
    appels: list[dict] = []

    def sonde(project_dir, **kwargs):
        appels.append(kwargs)
        return 4

    monkeypatch.setattr(pdf_composition, "resolve_sheets_version_rank", sonde)
    # La commande echouera plus loin (le projet de cette fixture ne porte pas de
    # frames) : ce qui est mesure est ce qui se passe AVANT, et l'ordre des
    # gardes veut que le rang se resolve apres la conformite du lot.
    cli.main(["makepdf", "--project", str(projet_a_trois_tirages["projet"]),
              "--lot", LOT])
    assert len(appels) == 1, (
        "le rang n'a pas ete resolu sans drapeau : le calcul est reste derriere "
        "`--nouvelle-version`, et la feuille imprimee mentira au premier "
        "changement de mise en page")
    assert appels[0]["lot_id"] == LOT and appels[0]["rush_id"] == RUSH


def _lancer(projet: Path, *options: str) -> int:
    return cli.main(["makepdf", "--project", str(projet), "--lot", LOT,
                     *options])


def test_le_drapeau_reste_SANS_EFFET_plutot_que_refuse_sur_un_lot_vierge(tmp_path):
    """AC 2.10c, et c'est desormais le comportement **nominal**.

    Le repli etait un cas de bord tant que le rang ne se calculait que derriere
    le drapeau ; il devient la regle. Refuser serait un blocage sec sur une
    intention parfaitement realisable (`EPIC11-ARB-89`), et ecrire un `_v2`
    serait une « version 2 de rien ».
    """
    monde = _projet_reel(tmp_path)
    projet = monde["projet"]
    (projet / "project.json").write_text(
        json.dumps(monde["manifest"], indent=2), encoding="utf-8")

    assert _lancer(projet, "--nouvelle-version") == 0
    ecrits = sorted(p.name for p in
                    (projet / project_layout.PLANCHES_DIRNAME).glob("*.pdf"))
    assert len(ecrits) == 1 and "_v" not in ecrits[0], ecrits


def test_overwrite_vise_le_tirage_EXISTANT_et_non_son_voisin(tmp_path):
    """La branche destructive d'`EPIC11-ARB-104` survit au decouplage.

    **Ce test mesure un ecart assume**, et il est ecrit pour qu'il soit visible
    plutot que subi. Le decouplage fait avancer le rang a chaque passe : sans
    disposition particuliere, `--overwrite` n'aurait plus rien a ecraser -- le
    nom serait toujours neuf --, et la moitie « OU ecrase » d'`EPIC11-ARB-104`
    disparaitrait **en silence**, en meme temps que l'issue que le message de
    refus prescrit. `--overwrite` vise donc la LIGNE D'EAU, c'est-a-dire le
    dernier tirage a date.

    La mesure porte sur le disque et non sur un code de retour : deux passes
    avec le drapeau ne laissent **qu'un** tirage, et c'est le meme chemin.
    """
    monde = _projet_reel(tmp_path)
    projet = monde["projet"]
    (projet / "project.json").write_text(
        json.dumps(monde["manifest"], indent=2), encoding="utf-8")
    patches = projet / project_layout.PLANCHES_DIRNAME

    assert _lancer(projet) == 0
    origine = sorted(patches.glob("*.pdf"))
    assert len(origine) == 1, origine

    # Sans le drapeau : un VOISIN, et l'original reste.
    assert _lancer(projet) == 0
    assert len(sorted(patches.glob("*.pdf"))) == 2

    # Avec le drapeau : le dernier tirage est REECRIT, aucun troisieme fichier.
    avant = sorted(p.name for p in patches.glob("*.pdf"))
    assert _lancer(projet, "--overwrite") == 0
    apres = sorted(p.name for p in patches.glob("*.pdf"))
    assert apres == avant, (avant, apres)
    assert apres[-1].endswith("_v2.pdf"), apres
