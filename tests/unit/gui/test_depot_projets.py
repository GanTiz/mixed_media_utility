# -*- coding: utf-8 -*-
"""Creation et lecture d'un dossier de projet (story 7.1, AC 1 et AC 4).

Volet **C** de l'AC 1 : ce que la GUI ecrit, le coeur doit l'accepter --
l'interface ne redefinit aucune regle du coeur. Les tests d'ecriture
comparent donc l'arborescence produite a l'attendu, relisent le document
par le vrai ``validate_manifest``, et poussent jusqu'a une extraction REELLE
dans le projet cree : un format parallele que seule la GUI saurait relire
passerait les deux premiers tests et echouerait au troisieme.

Volet **T** de l'AC 4 : les trois familles d'echec du coeur -- fichier
absent, JSON corrompu, version de schema inconnue -- deviennent une ligne
portant le motif **verbatim**. L'assertion porte a chaque fois sur une
sous-chaine discriminante du message reel (par exemple la version fautive
citee), jamais sur un litteral que la GUI aurait recopie.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from mixed_media_utility.frame_selection import select_source_frames
from mixed_media_utility.gui import depot_projets
from mixed_media_utility.io.extraction_manifest import (
    ExtractionRecord,
    persist_extraction,
)
from mixed_media_utility.io.manifest import validate_manifest
from mixed_media_utility.io.naming import (
    build_extracted_frame_filename,
    build_lot_id,
    normalize_identifier,
)
from mixed_media_utility.io import project_layout
from mixed_media_utility.io.project_layout import FRAMES_DIRNAME, rush_dir_slug

CHAMPS_SOURCE_TAGGES = {
    "source_codec": "prores",
    "source_pix_fmt": "yuv422p10le",
    "source_bit_depth": 10,
    "source_sample_aspect_ratio": "1:1",
    "source_color_primaries": "bt709",
    "source_color_trc": "bt709",
    "source_colorspace": "bt709",
    "source_color_range": "tv",
}


def _arborescence(racine):
    """Tous les chemins relatifs sous ``racine``, dossiers compris."""
    return sorted(str(chemin.relative_to(racine)) for chemin in racine.rglob("*"))


# ---------------------------------------------------------------------------
# AC 1 -- creation
# ---------------------------------------------------------------------------


def test_creer_fabrique_le_dossier_de_projet_sous_le_dossier_designe(tmp_path):
    """`EPIC7-ARB-82` : on designe le PARENT, l'outil cree le dossier de projet.

    Ce test mesurait l'inverse jusqu'au 2026-08-27 -- que rien ne naisse sous
    le dossier choisi (`EPIC7-ARB-28` pt 1). Les deux ne se contredisent pas :
    ce qui nait sous le dossier designe porte le **nom du projet saisi par
    l'operatrice**, jamais le nom de l'outil, et `project.json` est bien a la
    racine de ce dossier-la. Ce qu'`EPIC7-ARB-28` interdisait -- un
    sous-dossier fabrique par l'outil A L'INTERIEUR du dossier de projet --
    reste interdit, et c'est l'egalite d'ensembles ci-dessous qui le tient.
    """
    destination = tmp_path / "travail"
    destination.mkdir()

    depot_projets.creer_projet(destination, "Mon Film")

    dossier = destination / "Mon Film"
    assert dossier.is_dir(), "l'outil cree lui-meme le dossier de projet"
    assert (dossier / depot_projets.NOM_FICHIER_PROJET).is_file()
    # L'attendu se LIT de `project_layout` : une seconde liste de dossiers
    # ecrite dans un test serait la meme faute que dans le code.
    attendus = {depot_projets.NOM_FICHIER_PROJET} | {
        chemin.name for chemin in project_layout.base_layout_dirs(dossier).values()
    }
    assert set(_arborescence(dossier)) == attendus


def test_creer_ne_touche_a_rien_d_autre_dans_le_dossier_de_destination(tmp_path):
    """Le dossier de destination n'appartient pas a l'outil.

    Un voisin y vit deja et doit y rester intact : la creation ajoute UN
    dossier, elle ne range pas le dossier de l'operatrice. Le voisin est
    nomme de sorte a preceder la cible dans l'ordre alphabetique -- une
    creation qui ecraserait « le premier dossier venu » se verrait ici.
    """
    destination = tmp_path / "travail"
    destination.mkdir()
    voisin = destination / "Archive 2025"
    voisin.mkdir()
    (voisin / "note.txt").write_text("intacte", encoding="utf-8")

    depot_projets.creer_projet(destination, "Mon Film")

    assert (voisin / "note.txt").read_text(encoding="utf-8") == "intacte"
    assert sorted(c.name for c in destination.iterdir()) == [
        "Archive 2025",
        "Mon Film",
    ]


def test_le_projet_cree_valide_contre_le_coeur(tmp_path):
    (tmp_path / "travail").mkdir()

    dossier = depot_projets.creer_projet(tmp_path / "travail", "Mon Film").chemin

    manifeste = validate_manifest(dossier / depot_projets.NOM_FICHIER_PROJET)
    assert manifeste["rushes"] == []
    assert manifeste["lots"] == []
    assert manifeste["created"].endswith("Z")


def test_le_projet_cree_accueille_une_extraction_reelle(tmp_path):
    """Le projet cree par la GUI est un VRAI projet du coeur.

    Regle des fabriques : deux extractions, deux lots distinguables
    (cadences 5 et 12,5), et l'assertion vise le SECOND. Un chemin qui
    rendrait toujours la premiere entree passerait un scenario mono-lot.
    """
    (tmp_path / "travail").mkdir()
    ligne = depot_projets.creer_projet(tmp_path / "travail", "Mon Film")
    dossier = ligne.chemin

    identifiant = ligne_identifiant(dossier)
    premier = _enregistrement(identifiant, fps_target=5)
    second = _enregistrement(identifiant, fps_target=12.5)
    assert premier.lot_id != second.lot_id

    for enregistrement in (premier, second):
        _ecrire_les_frames(dossier, enregistrement)
        persist_extraction(dossier, enregistrement)

    manifeste = validate_manifest(dossier / depot_projets.NOM_FICHIER_PROJET)
    assert [lot["lot_id"] for lot in manifeste["lots"]] == [
        premier.lot_id,
        second.lot_id,
    ]
    vise = next(lot for lot in manifeste["lots"] if lot["lot_id"] == second.lot_id)
    assert vise["fps_target"] == pytest.approx(12.5)
    # La date de creation posee par la GUI survit a l'extraction.
    assert manifeste["created"] == ligne.date_creation


def ligne_identifiant(dossier):
    return depot_projets.identifiant_declare(dossier)


def _enregistrement(identifiant_projet, *, fps_target, rush_id="rush-001"):
    selection = select_source_frames(
        fps_source=25, fps_target=fps_target, source_frame_count=50
    )
    fps_source_type = float(selection.fps_source)
    fps_target_type = float(selection.fps_target)
    return ExtractionRecord(
        project_id=identifiant_projet,
        rush_id=rush_id,
        rush_source_name=f"{rush_id}.mov",
        lot_id=build_lot_id(rush_id, fps_target_type),
        frames_dir_relative=(
            f"{FRAMES_DIRNAME}/{rush_dir_slug(rush_id, fps_target_type)}"
        ),
        selection=selection,
        fps_source=fps_source_type,
        fps_target=fps_target_type,
        source_width=1920,
        source_height=1080,
        source_fields=dict(CHAMPS_SOURCE_TAGGES),
        confirmation_mode="non_interactif",
        unknown_color_accepted=False,
        confirmed_at="2026-08-25T09:30:00Z",
    )


def _ecrire_les_frames(dossier_projet, enregistrement):
    dossier = dossier_projet / enregistrement.frames_dir_relative
    dossier.mkdir(parents=True, exist_ok=True)
    for frame in enregistrement.selection.frames:
        nom = build_extracted_frame_filename(
            enregistrement.rush_id, enregistrement.fps_target, frame.frame_timecode
        )
        (dossier / nom).write_bytes(b"tiff")


@pytest.mark.parametrize(
    "nom",
    ["Mon Film", "Café Crème", "Été 2026 -- prises 1"],
    ids=["simple", "accentue", "accentue-et-ponctue"],
)
def test_l_identifiant_vient_du_helper_du_coeur(tmp_path, nom):
    """`project_id` derive du nom du dossier par ``normalize_identifier``.

    Le cas accentue est nomme par l'AC : il doit rendre l'identifiant NFKD
    attendu, celui du coeur -- aucune seconde normalisation n'existe cote
    GUI. Trois noms DISTINGUABLES, pas un seul nom temoin (regle des
    fabriques appliquee aux fixtures intermediaires).
    """
    (tmp_path / "travail").mkdir()

    dossier = depot_projets.creer_projet(tmp_path / "travail", nom).chemin

    attendu = normalize_identifier(nom, label="le nom du dossier de projet")
    assert depot_projets.identifiant_declare(dossier) == attendu


def test_creer_dans_un_dossier_qui_porte_deja_un_projet_est_refuse(tmp_path):
    """Aucun ecrasement destructeur sans avertissement, et pas de modale :
    refus simple -- le geste nominal sur ce dossier-la, c'est « ouvrir »."""
    (tmp_path / "travail").mkdir()
    dossier = depot_projets.creer_projet(tmp_path / "travail", "Mon Film").chemin
    avant = (dossier / depot_projets.NOM_FICHIER_PROJET).read_text(encoding="utf-8")

    with pytest.raises(depot_projets.ProjetExistantError):
        depot_projets.creer_projet(tmp_path / "travail", "Mon Film")

    apres = (dossier / depot_projets.NOM_FICHIER_PROJET).read_text(encoding="utf-8")
    assert apres == avant, "le projet preexistant a ete touche"


def test_un_nom_de_dossier_sans_caractere_utilisable_est_refuse(tmp_path):
    """Volet symetrique du precedent : le refus vient du coeur
    (``NamingError``), il n'est pas reimplemente ici."""
    destination = tmp_path / "travail"
    destination.mkdir()

    with pytest.raises(depot_projets.NamingError):
        depot_projets.creer_projet(destination, "###")

    # Le refus tombe AVANT le premier `mkdir` : pas meme un dossier vide.
    assert _arborescence(destination) == [], "un refus a laisse quelque chose"


# ---------------------------------------------------------------------------
# AC 4 -- lecture : les trois familles d'echec, et les sources introuvables
# ---------------------------------------------------------------------------


def _projet_valide(dossier, *, identifiant="projet-lisible", cree_le="2026-08-01T10:00:00Z"):
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / depot_projets.NOM_FICHIER_PROJET).write_text(
        json.dumps(depot_projets.manifeste_minimal(identifiant, cree_le=cree_le)),
        encoding="utf-8",
    )
    return dossier


def test_un_projet_lisible_rend_ses_deux_dates_et_aucun_motif(tmp_path):
    dossier = _projet_valide(tmp_path / "Lisible")

    ligne = depot_projets.lire_projet(dossier)

    assert ligne.ouvrable
    assert ligne.motif is None
    assert ligne.nom == "Lisible"
    assert ligne.date_creation == "2026-08-01T10:00:00Z"
    assert ligne.date_modification is not None


def test_un_projet_sans_date_de_creation_laisse_la_date_vide(tmp_path):
    """« Sinon vide -- jamais deduite » (AC 2) : aucun repli sur le `mtime`,
    qui donnerait deux dates egales par construction et mentirait sur l'age
    du projet."""
    dossier = tmp_path / "Sans date"
    dossier.mkdir()
    manifeste = depot_projets.manifeste_minimal("sans-date")
    del manifeste["created"]
    (dossier / depot_projets.NOM_FICHIER_PROJET).write_text(
        json.dumps(manifeste), encoding="utf-8"
    )

    ligne = depot_projets.lire_projet(dossier)

    assert ligne.ouvrable
    assert ligne.date_creation is None
    assert ligne.date_modification is not None


def test_un_projet_aux_sources_introuvables_s_ouvre_normalement(tmp_path):
    """Fixture aux chemins morts : le document est valide, les fichiers
    qu'il designe n'existent pas. L'ecran de gestion ne verifie RIEN du
    contenu (`EPIC7-ARB-27`) -- la ligne ne porte donc aucun signe
    particulier, et elle reste ouvrable."""
    dossier = tmp_path / "Sources parties"
    dossier.mkdir()
    manifeste = depot_projets.manifeste_minimal("sources-parties")
    manifeste["rushes"] = [
        {"rush_id": "rush-001", "source_path": "srcs/disparu-1.mov"},
        {"rush_id": "rush-002", "source_path": "srcs/disparu-2.mov"},
    ]
    (dossier / depot_projets.NOM_FICHIER_PROJET).write_text(
        json.dumps(manifeste), encoding="utf-8"
    )
    assert not (dossier / "srcs").exists(), "la fixture doit avoir des chemins MORTS"

    ligne = depot_projets.lire_projet(dossier)

    assert ligne.ouvrable
    assert ligne.motif is None


def test_un_dossier_sans_fichier_de_projet_est_une_ligne_en_erreur(tmp_path):
    dossier = tmp_path / "Vide"
    dossier.mkdir()

    ligne = depot_projets.lire_projet(dossier)

    assert not ligne.ouvrable
    # Le motif est celui de l'exception du coeur : il cite le fichier
    # introuvable, nommement.
    assert depot_projets.NOM_FICHIER_PROJET in ligne.motif
    assert ligne.date_creation is None


def test_un_fichier_de_projet_tronque_est_une_ligne_en_erreur(tmp_path):
    dossier = tmp_path / "Tronque"
    dossier.mkdir()
    tronque = '{"schema_version": "2.1", "project_id": "tron'
    (dossier / depot_projets.NOM_FICHIER_PROJET).write_text(tronque, encoding="utf-8")

    ligne = depot_projets.lire_projet(dossier)

    assert not ligne.ouvrable
    # Le motif est celui de `json.JSONDecodeError`, mot pour mot -- releve en
    # provoquant la MEME exception sur le MEME contenu plutot qu'en figeant
    # un texte, qui varierait d'une version de Python a l'autre.
    with pytest.raises(json.JSONDecodeError) as leve:
        json.loads(tronque)
    assert ligne.motif == str(leve.value)
    # ... et il localise la coupure, ce qu'aucune paraphrase ne ferait.
    assert "line 1" in ligne.motif


def test_une_version_de_schema_inconnue_est_une_ligne_en_erreur(tmp_path):
    """Le motif cite la version fautive ET les versions connues : c'est
    exactement ce que ``validate_manifest`` ecrit, et c'est pour cela qu'on
    l'affiche verbatim plutot que de le paraphraser."""
    dossier = tmp_path / "Version inconnue"
    dossier.mkdir()
    manifeste = depot_projets.manifeste_minimal("version-inconnue")
    manifeste["schema_version"] = "9.9"
    (dossier / depot_projets.NOM_FICHIER_PROJET).write_text(
        json.dumps(manifeste), encoding="utf-8"
    )

    ligne = depot_projets.lire_projet(dossier)

    assert not ligne.ouvrable
    assert "9.9" in ligne.motif
    assert "2.1" in ligne.motif, "le motif du coeur liste les versions connues"

    # Le motif est bien celui de l'exception, mot pour mot.
    with pytest.raises(ValidationError) as leve:
        validate_manifest(dossier / depot_projets.NOM_FICHIER_PROJET)
    assert ligne.motif == leve.value.message


def test_les_trois_motifs_sont_distincts(tmp_path):
    """Regle des fabriques, volet « valeurs distinguables » : trois echecs
    de familles differentes ne doivent pas rendre trois fois le meme texte
    generique -- sinon l'operatrice en panne ne saurait pas laquelle des
    trois pannes elle a."""
    absent = tmp_path / "Absent"
    absent.mkdir()
    tronque = tmp_path / "Tronque"
    tronque.mkdir()
    (tronque / depot_projets.NOM_FICHIER_PROJET).write_text("{", encoding="utf-8")
    inconnue = tmp_path / "Inconnue"
    inconnue.mkdir()
    manifeste = depot_projets.manifeste_minimal("inconnue")
    manifeste["schema_version"] = "9.9"
    (inconnue / depot_projets.NOM_FICHIER_PROJET).write_text(
        json.dumps(manifeste), encoding="utf-8"
    )

    motifs = [
        depot_projets.lire_projet(dossier).motif
        for dossier in (absent, tronque, inconnue)
    ]

    assert all(motifs), "un motif vide ne dit rien de la panne"
    assert len(set(motifs)) == 3


def test_l_identifiant_declare_est_lu_jamais_recalcule(tmp_path):
    """AC 5 : un projet dont le `project_id` diverge du nom de son dossier
    n'est PAS une erreur -- l'import lit le manifeste, il ne le refait pas."""
    dossier = _projet_valide(tmp_path / "Un nom de dossier", identifiant="tout-autre-id")

    ligne = depot_projets.lire_projet(dossier)

    assert ligne.ouvrable
    assert depot_projets.identifiant_declare(dossier) == "tout-autre-id"
    assert depot_projets.identifiant_depuis_le_dossier(dossier) == "Un-nom-de-dossier"


def test_l_apercu_ne_ment_pas_sur_un_nom_a_point_final(tmp_path):
    """Windows retire les espaces ET les points de fin d'un nom de dossier.

    `dossier_cible(parent, "mon_projet.")` annoncait `.../mon_projet.` alors
    que le dossier cree s'appelle `mon_projet` : l'apercu mentait sur ce qui
    allait naitre -- le defaut precis que cette fonction dit exister pour
    empecher. Le `.strip()` traitait l'espace, pas le point.

    La cible n'est pas le premier caractere retire : le nom porte les deux, un
    point PUIS un espace, pour qu'un retrait qui ne ferait qu'un tour se voie.
    """
    assert depot_projets.dossier_cible(tmp_path, "mon_projet. ") == tmp_path / "mon_projet"
    assert depot_projets.dossier_cible(tmp_path, "mon_projet") == tmp_path / "mon_projet"
    # Un point INTERIEUR n'est pas touche : ce n'est pas une normalisation de
    # nom, c'est le seul alignement sur ce que le systeme de fichiers fera.
    assert depot_projets.dossier_cible(tmp_path, "v1.2") == tmp_path / "v1.2"


def test_l_apercu_et_le_dossier_cree_portent_le_MEME_nom(tmp_path):
    """Volet symetrique, et c'est le contrat : une seule fonction calcule le
    chemin annonce et le chemin cree. Mesure sur le DISQUE."""
    annonce = depot_projets.dossier_cible(tmp_path, "mon_projet. ")

    ligne = depot_projets.creer_projet(tmp_path, "mon_projet. ")

    assert Path(ligne.chemin) == annonce
    assert annonce.is_dir()
    assert (annonce / "project.json").is_file()
