# -*- coding: utf-8 -*-
"""Demo JETABLE de la vague 2 -- pour juger les stories 11.2 et 11.3 a la main.

**Ce fichier n'est pas un livrable et n'est couvert par aucun test.** Il existe
pour la meme raison que `demo_vague_1.py` : `bin/mmu-tui` nu ne monte que les
trois paliers temoins de la story 11.0. Les ecrans de la vague 2 -- l'ecran de
projet (`E0-1` a `E0-4`), le menu des ateliers (`E1-1`) et le palier Projet --
sont ecrits, testes, et **inatteignables au clavier** tant que rien ne les
empile. Le cablage complet arrive avec les ateliers, en vague 3.

**Ce qui est reel ici, et c'est l'essentiel :** les trois ecrans, la grille, les
jetons, le clavier, les diagnostics, les compteurs, le pied du projet, les deux
panneaux chiffres et tous les refus sont le **code de production**, importe tel
quel de `mixed_media_utility.tui`. Les projets sont crees par le coeur
(`depot_projets.creer_projet`), leurs manifestes par le vrai producteur
(`build_extraction_manifest`), le profil de calibration par
`cc.profile_to_document`, et les payloads par `payload.serialize_payload`.

**Ce qui est faux, et le reste assume :**

* le bac a sable est jetable et **recree a chaque lancement** -- son chemin est
  imprime avant de dessiner, et rien n'est ecrit hors de lui ;
* la liste des projets recents est lue dans **ce** bac a sable, jamais dans les
  reglages de ta machine : la demo ne peut pas polluer tes vrais recents ;
* les deux commandes du palier Projet s'arretent au panneau de confirmation.
  L'issue qui ecrit ecrit vraiment, mais dans le bac a sable.

Lancer, depuis n'importe ou :

    python _bmad-output/planning-artifacts/ux-designs/ux-tui-2026-08-27/demo_vague_2.py

Options : `--ascii` (repli sans Unicode), `--sans-couleur` (ou `NO_COLOR` dans
l'environnement), `--bac <chemin>` (bac a sable ailleurs que dans le temporaire).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# `src/` ET `tests/unit/` sur le chemin d'import sans rien installer -- calcule
# depuis la position de CE fichier, jamais depuis le repertoire courant.
# `tests/unit` y est parce que la fabrique d'`ExtractionRecord` du depot y vit :
# fabriquer un manifest a la main donnerait un document que `validate_manifest`
# refuse, donc que `diagnostiquer` refuse, donc que l'ecran de projet refuse
# d'ouvrir -- et la demo montrerait un refus au lieu du menu.
_DEPOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_DEPOT / "src"))
sys.path.insert(0, str(_DEPOT / "tests" / "unit"))

from mixed_media_utility import color_calibration as cc  # noqa: E402
from mixed_media_utility.gui.depot_projets import creer_projet  # noqa: E402
from mixed_media_utility.io import calibration_profile  # noqa: E402
from mixed_media_utility.io import payload as payload_io  # noqa: E402
from mixed_media_utility.io.extraction_manifest import (  # noqa: E402
    build_extraction_manifest)
from mixed_media_utility.tui import ecran_ateliers, palier_projet, projets  # noqa: E402
from mixed_media_utility.tui.coque import (  # noqa: E402
    Contexte, CoqueTui, EcranPasEncore)
from mixed_media_utility.tui.ecran_projet import EcranCreation, EcranProjet  # noqa: E402
from mixed_media_utility.tui.execution import PanneauConfirmation  # noqa: E402
from mixed_media_utility.tui.panneau import ChoixExclusif, Issue  # noqa: E402

import test_calibration_page_source as couleur  # noqa: E402
from test_extraction_manifest import make_record, make_selection  # noqa: E402

#: Trois lots, **distinguables**, et le plus recemment confirme n'est **pas** le
#: premier : la regle des fabriques du depot vaut aussi pour une demo. Un pied
#: qui prendrait « le premier lot » au lieu du plus recemment confirme se verrait
#: ici a l'oeil, sans lire une ligne de code.
LOTS = (
    ("rush-001", 12.5, "2026-08-25T16:46:00Z", "extraction"),
    ("rush-002", 24.0, "2026-08-27T09:12:00Z", "encode"),
    ("rush-003", 25.0, "2026-08-26T11:03:00Z", "reconstruction"),
)


# ---------------------------------------------------------------------------
# Le bac a sable : cinq situations, une par chose a juger
# ---------------------------------------------------------------------------

def batir_le_bac(racine: Path) -> dict:
    if racine.exists():
        shutil.rmtree(racine)
    racine.mkdir(parents=True)

    riche = _projet_riche(racine)
    neuf = creer_projet(racine, "projet_tout_neuf").chemin

    # Un dossier qui n'est pas un projet : le premier des trois refus nommes.
    sans_manifest = racine / "dossier_sans_project_json"
    sans_manifest.mkdir()
    (sans_manifest / "une_photo.tiff").write_bytes(b"pas un projet")

    # Un project.json illisible : le deuxieme refus.
    casse = creer_projet(racine, "projet_casse").chemin
    (casse / "project.json").write_text("{ ceci n'est pas du json",
                                        encoding="utf-8")

    # Un recent dont le dossier a disparu : le troisieme refus, et le seul qui
    # se voit **dans la liste** plutot qu'apres une saisie.
    disparu = creer_projet(racine, "projet_efface").chemin
    shutil.rmtree(disparu)

    # Les recents vivent dans le bac -- **jamais** dans les reglages de la
    # machine. Le plus recemment ouvert est en tete de liste.
    recents = projets.Recents(racine / "recents-v1.json")
    for dossier, quand in ((casse, "2026-08-24T08:00:00Z"),
                           (disparu, "2026-08-25T09:30:00Z"),
                           (neuf, "2026-08-26T14:05:00Z"),
                           (riche, "2026-08-27T10:20:00Z")):
        recents.noter_ouverture(dossier, quand=quand)

    return {"racine": racine, "recents": recents, "riche": riche,
            "profil": _profil_externe(racine), "payloads": _payloads(racine)}


def _projet_riche(racine: Path) -> Path:
    """Un projet a trois lots, **par le vrai producteur de manifest**."""
    dossier = creer_projet(racine, "projet_demo").chemin
    manifest = json.loads((dossier / "project.json").read_text(encoding="utf-8"))
    # L'identite du projet est celle que le coeur a posee : la persistance
    # « refuse de reecrire l'identite d'un projet existant », et elle a raison.
    identite = manifest["project_id"]
    for rush_id, cadence, confirme, etat in LOTS:
        # La selection est fabriquee a la MEME cadence : le producteur refuse
        # un enregistrement dont la cadence typee contredit la selection.
        manifest = build_extraction_manifest(manifest, make_record(
            make_selection(fps_source=30, fps_target=cadence),
            project_id=identite, rush_id=rush_id, fps_target=cadence,
            confirmed_at=confirme, rush_source_name=f"{rush_id}.mov"))
    # L'etat de lot n'est pas ce que l'extraction pose : on le force ici pour
    # que les entrees conditionnees du menu aient trois cas a montrer.
    for lot in manifest["lots"]:
        for rush_id, _cadence, _confirme, etat in LOTS:
            if lot["rush_id"] == rush_id:
                lot["state"] = etat
    (dossier / "project.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return dossier


def _profil_externe(racine: Path) -> Path:
    """Un profil de calibration **hors de tout projet** : la forme dans laquelle
    un profil voyage (`EPIC5-ARB-83`)."""
    profil = couleur._calibration_profile(press=couleur._NOMINAL_PRESS)
    document = cc.profile_to_document(
        profil, chain_id="chaine-du-labo", source_page_id="chaine-du-labo-p0",
        template_id=couleur.TEMPLATE, read_patch_count=18,
        retained_patch_count=18,
        ink_floor_excluded=cc.correction_form_excludes_ink_floor(
            profil.correction_id))
    dossier = racine / "profils_venus_d_ailleurs"
    dossier.mkdir()
    chemin = dossier / "chaine-du-labo.json"
    chemin.write_text(calibration_profile.serialize_profile(document),
                      encoding="utf-8")
    return chemin


def _payloads(racine: Path) -> list[Path]:
    """Quatre pages de QR, ecrites par le **vrai** producteur du texte imprime.

    Un `json.dumps` du dictionnaire produirait un document a cles longues, que
    `parse_payload` refuse comme perime : la reconstruction echouerait pour une
    raison qui n'a rien a voir avec ce qu'on juge.
    """
    dossier = racine / "qr_relus"
    dossier.mkdir()
    chemins = []
    for page in range(4):
        document = {
            "schema_version": payload_io.PAYLOAD_SCHEMA_VERSION,
            "project_id": "demo-001", "rush_id": "rush-002",
            "lot_id": "lot-relu", "page_index": page, "page_count": 4,
            "page_role": payload_io.PAGE_ROLE_IMAGES,
            "fps_target": 24.0, "timecode_base_fps": "25/1",
            "template_id": "template-a4-16x9",
            "patch_preset_id": "patch-preset-mvp",
            "target_colorspace": "rec709", "gamut_map_id": "gamut-map-none-1",
            "slots": [{"slot_index": page,
                       "frame_timecode": f"00:00:0{page}:00"}],
        }
        chemin = dossier / f"page_{page}.txt"
        chemin.write_text(payload_io.serialize_payload(document),
                          encoding="utf-8")
        chemins.append(chemin)
    return chemins


# ---------------------------------------------------------------------------
# Le cablage des trois paliers -- ce que la vague 3 fera pour de bon
# ---------------------------------------------------------------------------

def cabler(bac: dict, sans_couleur: bool, ascii_seul: bool) -> CoqueTui:
    menu = ecran_ateliers.EcranAteliers()
    palier = palier_projet.EcranPalierProjet()
    ecran = EcranProjet(recents=bac["recents"])

    app = CoqueTui(paliers=[ecran, menu, palier],
                   contexte=Contexte(projet="-"),
                   sans_couleur=sans_couleur, ascii_seul=ascii_seul)

    def ouvrir(dossier) -> None:
        """Nommer le projet, poser le dossier sur les deux paliers du bas,
        relire, descendre. **Dans cet ordre** : le menu lit son manifest avant
        d'etre monte, faute de quoi il se dessinerait vide une fois."""
        dossier = Path(dossier)
        app.contexte = Contexte(projet=dossier.name)
        menu.dossier = palier.dossier = dossier
        menu.charger()
        app.descendre()

    def creer(cible) -> None:
        app.descendre(EcranCreation(
            dossier_parent=str(cible.parent) if cible else str(bac["racine"]),
            nom=cible.name if cible else "",
            apres_creation=ouvrir))

    def entrer_atelier(entree) -> None:
        if entree.nom == "Projet":
            app.descendre()
            return
        app.descendre(EcranPasEncore(entree.nom,
                                     app.QUAND_ARRIVENT_LES_ATELIERS))

    def entrer_commande(issue) -> None:
        app.descendre(_confirmation(app, palier.dossier, bac, issue))

    ecran._ouvrir, ecran._creer = ouvrir, creer
    menu._entrer = entrer_atelier
    palier._entrer = entrer_commande
    return app


def _confirmation(app, dossier, bac: dict, issue: Issue) -> PanneauConfirmation:
    """Le panneau chiffre de la 11.1, construit sur **l'apercu**.

    C'est le point le plus important a juger : les chiffres montres sont ceux
    que l'ecriture produira, et **rien n'est encore ecrit** (`EPIC11-ARB-4`).
    """
    if issue.cle == palier_projet.ENTREE_PROFIL:
        apercu = palier_projet.apercu_de_profil(dossier, bac["profil"])
        panneau = palier_projet.panneau_de_profil(apercu)
        libelle = "Poser ce profil par defaut"

        def ecrire():
            return palier_projet.poser_le_profil_par_defaut(
                dossier, bac["profil"])
    else:
        apercu = palier_projet.apercu_de_reconstruction(dossier, bac["payloads"])
        panneau = palier_projet.panneau_de_reconstruction(apercu)
        libelle = "Reconstruire le projet"

        def ecrire():
            return palier_projet.reconstruire_le_projet(dossier, bac["payloads"])

    ecran = PanneauConfirmation(panneau, ChoixExclusif([
        Issue("ecrire", libelle, ecrit=True),
        Issue("annuler", "Annuler, ne rien ecrire"),
    ]))

    def suite(retenue: Issue) -> None:
        if retenue.cle == "ecrire":
            ecrire()
        remonter_au_palier_projet(app)

    ecran._sur_issue = suite
    return ecran


def remonter_au_palier_projet(app) -> None:
    """`revenir_aux_ateliers` remonterait d'un palier de trop : le point de
    depart des deux commandes est le palier Projet, pas le menu."""
    while app.rang > 2:
        app.action_remonter()


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(prog="demo_vague_2")
    analyseur.add_argument("--ascii", dest="ascii_seul", action="store_true")
    analyseur.add_argument("--sans-couleur", dest="sans_couleur",
                           action="store_true",
                           default="NO_COLOR" in os.environ)
    analyseur.add_argument("--bac", default=None,
                           help="bac a sable jetable (defaut : temporaire)")
    options = analyseur.parse_args(argv)

    racine = Path(options.bac) if options.bac else \
        Path(tempfile.gettempdir()) / "mmu-demo-vague-2"
    bac = batir_le_bac(racine)
    print(f"Bac a sable jetable, recree a chaque lancement : {racine}")
    print("Rien n'est ecrit hors de ce dossier, y compris la liste des recents.")
    print("Entree pour dessiner...")
    input()

    cabler(bac, options.sans_couleur, options.ascii_seul).run()
    print(f"Bac a sable conserve : {racine}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
