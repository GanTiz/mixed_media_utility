"""Tests de la story 6.5: persistance au manifest de ce qu'`encode` produit.

Trois exigences structurent ce fichier.

**Contre les vrais producteurs** (action item 3 de la retro de l'Epic 4): le
document d'entree vient de `build_extraction_manifest` **reel**, jamais d'un
dict ecrit a la main; le `lot_id` de `io.naming.build_lot_id`; et le test
d'integration fait un **vrai encodage** par la chaine complete
(`plan_encode` -> `execute_plan` -> `persist_encode`), de sorte que l'etat
`encode` que le manifest porte a la fin vient de la persistance reelle et
d'aucune fixture.

**Regle des fabriques du `CLAUDE.md`** (septieme et huitieme occurrence du
defaut dans ce depot): toute fabrique de manifest produit **trois lots
distinguables** -- trois cadences ou fenetres, donc trois `lot_id`, trois
cardinaux --, et le lot vise par la persistance est celui du **milieu**. Le
mutant `M25` de la story 5.7 rendait le premier lot au lieu du lot vise et 257
tests restaient verts, parce que toutes les fixtures multi-lots placaient la
cible en tete.

**Un troisieme lot, et son `lot_id` prefixe celui de la cible.** Correction de
revue: une fabrique a deux lots `rush-001_1` et `rush-001_5` respecte la lettre
de la regle et ne distingue pourtant pas une **egalite** d'un `startswith` --
mesure, remplacer `lot.get("lot_id") == lot_id` par un appariement de prefixe
laissait 148 tests verts, et ecrivait sur le mauvais lot du manifest reel
`projects/projet_demo/project.json` (`..._25fps_1` vise, `..._25fps_10` ecrit).
La fabrique porte donc en **premiere** position un lot borne par timecodes,
`rush-001_5-<condensat>`, forme que `naming.build_lot_id` produit reellement et
dont l'identifiant **prefixe** celui de la cible. La cible reste au milieu: ni
premiere (mutant « le premier lot »), ni derniere (mutant « le dernier »), et
precedee d'un homonyme par prefixe (mutant « appariement par prefixe »).

**Mesurer, jamais raisonner.** Les trois bloquants de la revision 2 de cette
story etaient des enonces « X, donc Y » que personne n'avait lances. Les faits
sur lesquels la story s'appuie -- la garde a une branche de refus atteignable,
`lots[].items` refuse un champ non declare, un manifest v2.0 le refuse aussi --
sont donc **exerces ici**, pas cites.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import cli, codec_profiles, encode as encode_module  # noqa: E402
from mixed_media_utility.frame_selection import select_source_frames  # noqa: E402
from mixed_media_utility.io import (  # noqa: E402
    encode_manifest,
    extraction_manifest,
    naming,
    project_layout,
)
from mixed_media_utility.io.extraction_manifest import (  # noqa: E402
    ExtractionPersistenceError,
    ExtractionRecord,
    LegacyManifestError,
    LotStateConflictError,
    ManifestWriteError,
    build_extraction_manifest,
    persist_extraction,
)
from mixed_media_utility.io.manifest import (  # noqa: E402
    CURRENT_SCHEMA_VERSION,
    LOT_STATES,
    validate_manifest,
    validate_manifest_completeness,
)

PROJECT_ID = "proj-encodemanifest"
RUSH_ID = "rush-001"
FPS_SOURCE = 25.0
#: Deux cadences cibles, donc **deux lots distinguables** dans toute fixture.
#: La cible des tests est la **seconde**, `FPS_TARGET`.
FPS_OTHER = 1.0
FPS_TARGET = 5.0
SOURCE_FRAME_COUNT = 50

#: Bornes du **troisieme** lot: meme rush, meme cadence que la cible, mais une
#: fenetre de timecodes. `naming.build_lot_id` lui ajoute un condensat de bornes,
#: si bien que son `lot_id` (`rush-001_5-<condensat>`) **prefixe** celui de la
#: cible (`rush-001_5`). C'est la seule forme qui distingue une egalite d'un
#: `startswith`, et le depot la produit reellement depuis la story 3.7.
BOUNDS_IN = "00:00:00:05"
BOUNDS_OUT = "00:00:01:10"

PROFILE = "prores_hq"
OTHER_PROFILE = "prores_422"


# ---------------------------------------------------------------------------
# Fabriques: le vrai producteur, et jamais un seul element
# ---------------------------------------------------------------------------


def _frames_dir_relative(fps_target: float, *, bounded: bool = False) -> str:
    bornes = (
        {"source_in_timecode": BOUNDS_IN, "source_out_timecode": BOUNDS_OUT}
        if bounded
        else {}
    )
    return (
        f"{project_layout.FRAMES_DIRNAME}/"
        f"{project_layout.rush_dir_slug(RUSH_ID, fps_target, **bornes)}"
    )


def _extraction_record(fps_target: float, *, bounded: bool = False) -> ExtractionRecord:
    """Enregistrement d'extraction reel, coherent avec `naming.build_lot_id`.

    `bounded` produit le lot **borne par timecodes** de la story 3.7, dont
    l'identifiant porte un condensat de bornes et prefixe donc celui du lot non
    borne de la meme cadence.
    """
    bornes = (
        {"source_in_timecode": BOUNDS_IN, "source_out_timecode": BOUNDS_OUT}
        if bounded
        else {}
    )
    selection = select_source_frames(
        fps_source=FPS_SOURCE,
        fps_target=fps_target,
        source_frame_count=SOURCE_FRAME_COUNT,
        **bornes,
    )
    return ExtractionRecord(
        project_id=PROJECT_ID,
        rush_id=RUSH_ID,
        rush_source_name=f"{RUSH_ID}.mov",
        lot_id=naming.build_lot_id(RUSH_ID, fps_target, **bornes),
        frames_dir_relative=_frames_dir_relative(fps_target, bounded=bounded),
        selection=selection,
        fps_source=FPS_SOURCE,
        fps_target=fps_target,
        source_width=1920,
        source_height=1080,
        source_fields={},
        confirmation_mode="non_interactif",
        unknown_color_accepted=True,
        confirmed_at="2026-08-08T00:00:00Z",
    )


def _prefix_lot_id() -> str:
    return naming.build_lot_id(
        RUSH_ID,
        FPS_TARGET,
        source_in_timecode=BOUNDS_IN,
        source_out_timecode=BOUNDS_OUT,
    )


@pytest.fixture()
def lot_id() -> str:
    """Le lot **vise**: celui de `FPS_TARGET`, au milieu des trois."""
    return naming.build_lot_id(RUSH_ID, FPS_TARGET)


@pytest.fixture()
def other_lot_id() -> str:
    """Le lot de queue: autre cadence, donc `lot_id` sans parente avec la cible."""
    return naming.build_lot_id(RUSH_ID, FPS_OTHER)


@pytest.fixture()
def prefix_lot_id() -> str:
    """Le lot de tete, dont le `lot_id` **prefixe** celui de la cible.

    `rush-001_5-<condensat>` commence par `rush-001_5`: un appariement par
    prefixe le rendrait a la place de la cible, et il est en premiere position
    pour que ce soit le cas.
    """
    return _prefix_lot_id()


@pytest.fixture()
def manifest() -> dict:
    """Manifest v2.1 reel a **trois lots distinguables**, cible au milieu.

    Les trois lots different par leur `lot_id`, leur `expected_frame_count` et
    leurs bornes: une permutation ne se voit que si les elements different, et un
    remplissage uniforme rendrait invisible toute erreur d'appariement.

    L'ordre est normatif pour trois mutants d'appariement a la fois:

    * en **tete**, le lot borne dont l'identifiant prefixe celui de la cible --
      seul cas ou `==` et `startswith` divergent;
    * au **milieu**, la cible -- donc ni « le premier lot », ni « le dernier »;
    * en **queue**, un lot d'une autre cadence.
    """
    document = build_extraction_manifest(
        None, _extraction_record(FPS_TARGET, bounded=True)
    )
    document = build_extraction_manifest(document, _extraction_record(FPS_TARGET))
    document = build_extraction_manifest(document, _extraction_record(FPS_OTHER))
    document["color"]["target_colorspace"] = "rec709"
    assert [lot["lot_id"] for lot in document["lots"]] == [
        _prefix_lot_id(),
        naming.build_lot_id(RUSH_ID, FPS_TARGET),
        naming.build_lot_id(RUSH_ID, FPS_OTHER),
    ]
    return document


def _master(
    lot_id: str,
    *,
    profile_id: str = PROFILE,
    segment: str = "",
    frame_count: int = 10,
    incomplete: bool = False,
) -> encode_manifest.EncodedMaster:
    """Entree d'inventaire batie sur le vrai constructeur de nom de master."""
    filename = naming.build_master_filename(
        lot_id=lot_id,
        profile_id=profile_id,
        container=codec_profiles.get_profile(profile_id).container,
        resolution_segment=segment,
    )
    return encode_manifest.EncodedMaster(
        path=f"{project_layout.OUTPUTS_DIRNAME}/{filename}",
        profile_id=profile_id,
        frame_count=frame_count,
        incomplete=incomplete,
    )


def _record(lot_id: str, **kwargs) -> encode_manifest.EncodeRecord:
    return encode_manifest.EncodeRecord(
        lot_id=lot_id,
        master=_master(lot_id, **kwargs),
        codec_target=kwargs.get("profile_id", PROFILE),
        outputs_dir=encode_manifest.outputs_dir_value(),
        # La cle de famille suit le profil de la fabrique : la resolution par
        # defaut ne porte aucun segment, donc la cle est le profil seul.
        masters_family_key=kwargs.get("profile_id", PROFILE),
    )


def _project(tmp_path: Path, manifest: dict, name: str = "projet") -> Path:
    project_dir = tmp_path / name
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return project_dir


def _lot_of(document: dict, lot_id: str) -> dict:
    return next(lot for lot in document["lots"] if lot.get("lot_id") == lot_id)


def _manifest_v2_0(lot_id: str, other_lot_id: str) -> dict:
    """Manifest **v2.0** ecrit a la main, et le motif de cette exception.

    La regle du depot est « contre les vrais producteurs ». Elle est levee ici,
    explicitement: **aucun producteur de v2.0 n'existe plus**. La
    restructuration `decisions-2026-08-04.md` a fait ecrire `"2.1"` a toute la
    chaine, et le schema v2.0 est **gele** -- il interdit sur `lots[]` et sur
    `rushes[]` la moitie des champs que le producteur d'extraction ecrit
    aujourd'hui. Reshaper un document v2.1 ne donnerait donc pas un v2.0 valide,
    et un v2.0 invalide ne mesurerait rien du refus que ce test vise.

    **Trois** lots distinguables malgre tout, dans le meme ordre normatif que la
    fabrique v2.1: le lot dont l'identifiant prefixe la cible en tete, la cible
    au milieu, un lot d'une autre cadence en queue. La regle des fabriques ne se
    leve pas avec celle des producteurs, et la migration v2.0 -> v2.1 est
    precisement un endroit ou une permutation de lots passerait inapercue.
    """
    return {
        "schema_version": "2.0",
        "project_id": PROJECT_ID,
        "created": "2026-08-08T00:00:00Z",
        "rushes": [{"rush_id": RUSH_ID, "source_name": f"{RUSH_ID}.mov"}],
        "lots": [
            {
                "lot_id": _prefix_lot_id(),
                "rush_id": RUSH_ID,
                "state": "extraction",
                "expected_frame_count": 7,
                "frames_dir": _frames_dir_relative(FPS_TARGET, bounded=True),
            },
            {
                "lot_id": lot_id,
                "rush_id": RUSH_ID,
                "state": "scan",
                "expected_frame_count": 10,
                "frames_dir": _frames_dir_relative(FPS_TARGET),
            },
            {
                "lot_id": other_lot_id,
                "rush_id": RUSH_ID,
                "state": "extraction",
                "expected_frame_count": 2,
                "frames_dir": _frames_dir_relative(FPS_OTHER),
            },
        ],
        "artifacts": {"frames_dir": project_layout.FRAMES_DIRNAME},
        "color": {"target_colorspace": "rec709"},
        "video": {
            "fps_source": FPS_SOURCE,
            "fps_target": FPS_TARGET,
            "resolution_source": {"width": 1920, "height": 1080},
        },
        "reconstruction": {},
    }


# ---------------------------------------------------------------------------
# AC 4 / AC 16 -- la table est le contrat, teste en EGALITE d'ensembles
# ---------------------------------------------------------------------------


def test_le_lot_ne_gagne_exactement_que_les_cles_de_la_table(
    manifest: dict, lot_id: str
) -> None:
    """Egalite d'ensembles, jamais une liste de presences.

    Une liste de presences ne verrait pas un champ **de trop**, ce qui est
    precisement ce que l'AC 4 interdit: toute donnee absente de la table n'est
    pas ecrite.
    """
    # Garde contre la **vacuite**: une table videe rendrait vraie toute
    # inclusion, et c'est la famille de defauts qui a survecu le plus longtemps
    # a la campagne de la story 6.1.
    assert encode_manifest.ENCODE_LOT_FIELDS

    avant = set(_lot_of(manifest, lot_id))
    merge = encode_manifest.build_encode_manifest(manifest, _record(lot_id))
    apres = set(_lot_of(merge.manifest, lot_id))

    # Egalite, pas inclusion: l'ensemble d'arrivee est exactement l'ensemble de
    # depart augmente de la table, ni plus ni moins. `state` etait deja present
    # (pose par l'extraction) mais il est **reecrit**, et un test qui ne
    # regarderait que les cles nouvelles le manquerait.
    assert apres == avant | set(encode_manifest.ENCODE_LOT_FIELDS)
    # Story 11.8, AC 4.3 : la ligne d'eau des masters est le SECOND champ neuf,
    # et elle l'est pour toute ecriture, rang d'origine compris -- c'est ce qui
    # fait qu'elle se pose a la CONSOMMATION et non au seul retrait.
    assert apres - avant == {
        encode_manifest.MASTER_INVENTORY_FIELD,
        encode_manifest.MASTERS_WATERMARK_FIELD,
    }
    assert avant - apres == set()
    assert _lot_of(merge.manifest, lot_id)["state"] == encode_manifest.ENCODE_LOT_STATE


def test_la_fusion_est_pure_et_ne_modifie_pas_son_entree(
    manifest: dict, lot_id: str
) -> None:
    """« Fusion **pure**: aucune I/O, aucune horloge, aucun acces disque » -- et
    aucun effet de bord sur le document recu.

    Une copie superficielle ferait partager les entrees de `lots[]` entre
    l'entree et la sortie: l'appelant verrait son propre document change sous
    lui, et un refus survenu **apres** la fusion laisserait derriere lui un
    document deja modifie en memoire.
    """
    temoin = copy.deepcopy(manifest)
    encode_manifest.build_encode_manifest(manifest, _record(lot_id))
    assert manifest == temoin


def test_l_entree_de_master_porte_exactement_les_champs_de_sa_table(
    manifest: dict, lot_id: str
) -> None:
    assert len(encode_manifest.ENCODE_MASTER_FIELDS) == 4
    merge = encode_manifest.build_encode_manifest(manifest, _record(lot_id))
    entree = _lot_of(merge.manifest, lot_id)[encode_manifest.MASTER_INVENTORY_FIELD][0]
    assert set(entree) == set(encode_manifest.ENCODE_MASTER_FIELDS)


def test_les_sections_de_tete_ne_gagnent_exactement_que_leurs_tables(
    manifest: dict, lot_id: str
) -> None:
    avant_video = set(manifest.get("video") or {})
    avant_artifacts = set(manifest.get("artifacts") or {})
    merge = encode_manifest.build_encode_manifest(manifest, _record(lot_id))

    assert set(merge.manifest["video"]) - avant_video == set(
        encode_manifest.ENCODE_VIDEO_FIELDS
    )
    assert set(merge.manifest["artifacts"]) - avant_artifacts == set(
        encode_manifest.ENCODE_ARTIFACT_FIELDS
    )


def test_rien_d_autre_que_le_lot_vise_et_les_deux_sections_ne_bouge(
    manifest: dict, lot_id: str, other_lot_id: str, prefix_lot_id: str
) -> None:
    """Les **deux** lots non vises sont intacts, celui de tete comme celui de queue.

    C'est la moitie « appariement » de la regle des fabriques: si `_find_lot`
    rendait le premier lot au lieu du lot vise, ce test verrait le lot borne
    changer et celui de `FPS_TARGET` rester nu.
    """
    avant = copy.deepcopy(manifest)
    merge = encode_manifest.build_encode_manifest(manifest, _record(lot_id))

    assert _lot_of(merge.manifest, other_lot_id) == _lot_of(avant, other_lot_id)
    assert _lot_of(merge.manifest, prefix_lot_id) == _lot_of(avant, prefix_lot_id)
    assert merge.manifest["rushes"] == avant["rushes"]
    assert merge.manifest["color"] == avant["color"]
    assert merge.manifest["reconstruction"] == avant["reconstruction"]
    assert merge.manifest["created"] == avant["created"]
    assert merge.manifest["project_id"] == avant["project_id"]


def test_le_lot_vise_au_milieu_est_bien_celui_qui_recoit(
    manifest: dict, lot_id: str, other_lot_id: str, prefix_lot_id: str
) -> None:
    """Mutant `M25` de la story 5.7, transpose: la cible n'est ni la premiere ni
    la derniere."""
    merge = encode_manifest.build_encode_manifest(manifest, _record(lot_id))
    vise = _lot_of(merge.manifest, lot_id)

    assert encode_manifest.MASTER_INVENTORY_FIELD in vise
    for indemne in (other_lot_id, prefix_lot_id):
        lot = _lot_of(merge.manifest, indemne)
        assert encode_manifest.MASTER_INVENTORY_FIELD not in lot
        assert lot["state"] == "extraction"
    assert vise[encode_manifest.MASTER_INVENTORY_FIELD][0]["path"].endswith(".mov")
    assert lot_id in vise[encode_manifest.MASTER_INVENTORY_FIELD][0]["path"]


def test_l_appariement_du_lot_est_une_egalite_et_non_un_prefixe(
    manifest: dict, lot_id: str, prefix_lot_id: str
) -> None:
    """**Le test que la fabrique a deux lots ne pouvait pas porter.**

    Mesure de revue: remplacer `lot.get("lot_id") == lot_id` par
    `startswith(lot_id)` laissait 148 tests verts, et sur le manifest reel
    `projects/projet_demo/project.json` le master atterrissait sur
    `..._25fps_10` alors qu'on visait `..._25fps_1`. Le depot **livre** quatre
    paires de ce genre dans ce seul fichier. Ici le lot de tete porte le meme
    genre d'identifiant -- `rush-001_5-<condensat>`, produit par la
    desambiguisation de bornes de la story 3.7 -- et c'est lui qu'un appariement
    par prefixe rendrait.
    """
    assert prefix_lot_id.startswith(lot_id)
    assert prefix_lot_id != lot_id
    assert manifest["lots"][0]["lot_id"] == prefix_lot_id

    merge = encode_manifest.build_encode_manifest(manifest, _record(lot_id))

    assert (
        encode_manifest.MASTER_INVENTORY_FIELD not in _lot_of(merge.manifest, prefix_lot_id)
    )
    assert _lot_of(merge.manifest, prefix_lot_id)["state"] == "extraction"
    assert _lot_of(merge.manifest, lot_id)["state"] == encode_manifest.ENCODE_LOT_STATE


def test_la_fabrique_produit_bien_trois_lots_reellement_distinguables(
    manifest: dict, lot_id: str, other_lot_id: str, prefix_lot_id: str
) -> None:
    """Garde de la garde: une fabrique uniforme rendrait tous les tests ci-dessus
    vrais **par vacuite** d'appariement.

    Trois faits sont normatifs et chacun ferme un mutant: la cible n'est pas en
    tete, elle n'est pas en queue, et le lot de tete porte un identifiant dont
    elle est un **prefixe strict**.
    """
    tete, milieu, queue = manifest["lots"]
    assert tete["lot_id"] == prefix_lot_id
    assert milieu["lot_id"] == lot_id
    assert queue["lot_id"] == other_lot_id
    assert len({tete["lot_id"], milieu["lot_id"], queue["lot_id"]}) == 3
    assert tete["lot_id"].startswith(milieu["lot_id"])
    assert tete["lot_id"] != milieu["lot_id"]
    assert not queue["lot_id"].startswith(milieu["lot_id"])
    assert (
        len(
            {
                tete["expected_frame_count"],
                milieu["expected_frame_count"],
                queue["expected_frame_count"],
            }
        )
        == 3
    )


# ---------------------------------------------------------------------------
# AC 7 -- idempotence octet a octet, et le tuple vide
# ---------------------------------------------------------------------------


def test_les_champs_non_idempotents_sont_le_tuple_vide() -> None:
    assert encode_manifest.ENCODE_NON_IDEMPOTENT_FIELDS == ()


def test_deux_encodes_identiques_laissent_le_manifest_octet_a_octet_identique(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    project_dir = _project(tmp_path, manifest)
    record = _record(lot_id)

    encode_manifest.persist_encode(project_dir, record)
    premier = (project_dir / "project.json").read_bytes()
    persisted = encode_manifest.persist_encode(project_dir, record)
    second = (project_dir / "project.json").read_bytes()

    assert premier == second
    # Une repetition a l'identique ne **nomme** rien: le constat de remplacement
    # dirait un changement qui n'a pas eu lieu.
    assert persisted.findings == ()


def test_l_ordre_des_encodages_ne_change_pas_le_document(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """AC 5: `sort_keys` canonise les mappings, **pas** les listes.

    Sans tri explicite, l'inventaire porterait son ordre d'insertion, donc
    l'ordre chronologique des encodages -- un signal d'horloge dans un document
    dont l'AC 6 interdit toute valeur derivee de l'horloge.
    """
    hq = _record(lot_id, profile_id=PROFILE)
    natif = _record(lot_id, profile_id=PROFILE, segment="3307x1860")

    dir_a = _project(tmp_path, manifest, name="ordre-a")
    encode_manifest.persist_encode(dir_a, hq)
    encode_manifest.persist_encode(dir_a, natif)

    dir_b = _project(tmp_path, copy.deepcopy(manifest), name="ordre-b")
    encode_manifest.persist_encode(dir_b, natif)
    encode_manifest.persist_encode(dir_b, hq)

    assert (dir_a / "project.json").read_bytes() == (dir_b / "project.json").read_bytes()


def test_l_inventaire_est_trie_par_sa_cle(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    project_dir = _project(tmp_path, manifest)
    for record in (
        _record(lot_id, profile_id=PROFILE, segment="3307x1860"),
        _record(lot_id, profile_id=OTHER_PROFILE),
        _record(lot_id, profile_id=PROFILE),
    ):
        persisted = encode_manifest.persist_encode(project_dir, record)

    chemins = [
        entree[encode_manifest.MASTER_INVENTORY_KEY]
        for entree in _lot_of(persisted.manifest, lot_id)[
            encode_manifest.MASTER_INVENTORY_FIELD
        ]
    ]
    assert chemins == sorted(chemins)
    assert len(chemins) == 3


# ---------------------------------------------------------------------------
# AC 5 -- l'inventaire a une cle, et ce n'est pas `profile_id`
# ---------------------------------------------------------------------------


def test_deux_profils_donnent_deux_entrees(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    project_dir = _project(tmp_path, manifest)
    encode_manifest.persist_encode(project_dir, _record(lot_id, profile_id=PROFILE))
    persisted = encode_manifest.persist_encode(
        project_dir, _record(lot_id, profile_id=OTHER_PROFILE)
    )
    inventaire = _lot_of(persisted.manifest, lot_id)[
        encode_manifest.MASTER_INVENTORY_FIELD
    ]
    assert {entree["profile_id"] for entree in inventaire} == {PROFILE, OTHER_PROFILE}


def test_deux_resolutions_du_meme_profil_donnent_deux_entrees(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """**Le cas qui invalide une cle `profile_id`.**

    La story 6.1 produit `<lot>_mmu_prores_hq.mov` a la resolution par defaut et
    `<lot>_mmu_prores_hq_3307x1860.mov` en natif: deux masters distincts, du
    **meme** profil, tous deux voulus et tous deux sur le disque. Une cle par
    profil ecraserait le premier, c'est-a-dire exactement le tort que
    l'inventaire existe pour eviter.
    """
    project_dir = _project(tmp_path, manifest)
    encode_manifest.persist_encode(project_dir, _record(lot_id, profile_id=PROFILE))
    persisted = encode_manifest.persist_encode(
        project_dir, _record(lot_id, profile_id=PROFILE, segment="3307x1860")
    )
    inventaire = _lot_of(persisted.manifest, lot_id)[
        encode_manifest.MASTER_INVENTORY_FIELD
    ]
    assert len(inventaire) == 2
    assert {entree["profile_id"] for entree in inventaire} == {PROFILE}
    assert len({entree["path"] for entree in inventaire}) == 2


def test_le_meme_chemin_remplace_son_entree_et_le_dit(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Reencodage apres un rescan qui a comble les trous: meme fichier, autre
    contenu declare. L'entree est remplacee, pas doublee, et le fait est nomme."""
    project_dir = _project(tmp_path, manifest)
    encode_manifest.persist_encode(
        project_dir, _record(lot_id, frame_count=8, incomplete=True)
    )
    persisted = encode_manifest.persist_encode(
        project_dir, _record(lot_id, frame_count=10, incomplete=False)
    )
    inventaire = _lot_of(persisted.manifest, lot_id)[
        encode_manifest.MASTER_INVENTORY_FIELD
    ]
    assert len(inventaire) == 1
    assert inventaire[0]["frame_count"] == 10
    assert inventaire[0]["incomplete"] is False
    assert persisted.findings == (encode_manifest.ENCODE_MASTER_ENTRY_REPLACED,)
    assert (
        encode_manifest.ENCODE_MASTER_ENTRY_REPLACED
        in encode_manifest.ENCODE_PERSISTENCE_CODES
    )


@pytest.mark.parametrize("cible", [1, 2])
def test_l_entree_remplacee_est_choisie_par_sa_cle_et_non_par_sa_position(
    tmp_path: Path, manifest: dict, lot_id: str, cible: int
) -> None:
    """**Septieme occurrence du defaut de fabrique, fermee.**

    Les trois tests de remplacement partaient tous d'un inventaire a **une**
    entree, donc la cible etait en position 0. Mesure de revue: choisir l'entree
    a remplacer par la position 0 au lieu de la cle laissait 148 tests verts --
    et sur l'etat reel a deux masters, cela **supprimait** le master
    `prores_422` en laissant deux fois le meme `path` avec deux `frame_count`
    differents, que `validate_manifest` accepte faute de contrainte d'unicite.

    Ici l'inventaire porte **trois** entrees distinguables et la cible est
    parametree ailleurs qu'en tete. Le test verifie les deux moities: l'entree
    visee change, et **aucune** des autres ne bouge.
    """
    project_dir = _project(tmp_path, manifest)
    # Trois masters distincts du meme lot, tries par `path` a l'ecriture: le
    # profil `prores_422` passe avant `prores_hq`, et le derive resolu apres.
    departs = (
        _record(lot_id, profile_id=OTHER_PROFILE, frame_count=7),
        _record(lot_id, profile_id=PROFILE, frame_count=8),
        _record(lot_id, profile_id=PROFILE, segment="3307x1860", frame_count=9),
    )
    for record in departs:
        encode_manifest.persist_encode(project_dir, record)

    avant = _lot_of(
        json.loads((project_dir / "project.json").read_text(encoding="utf-8")), lot_id
    )[encode_manifest.MASTER_INVENTORY_FIELD]
    assert len(avant) == 3
    assert len({entree["path"] for entree in avant}) == 3
    assert len({entree["frame_count"] for entree in avant}) == 3

    vise = avant[cible]
    rejoue = next(
        record
        for record in departs
        if record.master.path == vise[encode_manifest.MASTER_INVENTORY_KEY]
    )
    persisted = encode_manifest.persist_encode(
        project_dir,
        encode_manifest.EncodeRecord(
            lot_id=rejoue.lot_id,
            master=encode_manifest.EncodedMaster(
                path=rejoue.master.path,
                profile_id=rejoue.master.profile_id,
                frame_count=rejoue.master.frame_count + 100,
                incomplete=False,
            ),
            codec_target=rejoue.codec_target,
            outputs_dir=rejoue.outputs_dir,
            masters_family_key=rejoue.masters_family_key,
        ),
    )

    apres = _lot_of(persisted.manifest, lot_id)[
        encode_manifest.MASTER_INVENTORY_FIELD
    ]
    assert len(apres) == 3
    assert [entree["path"] for entree in apres] == [
        entree["path"] for entree in avant
    ]
    assert apres[cible]["frame_count"] == vise["frame_count"] + 100
    for index, entree in enumerate(apres):
        if index != cible:
            assert entree == avant[index], index
    assert encode_manifest.ENCODE_MASTER_ENTRY_REPLACED in persisted.findings


def test_une_entree_d_inventaire_sans_cle_est_refusee_sans_rien_ecrire(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Ce module est le seul producteur du champ: une entree sans `path` est une
    edition manuelle, et la refuser vaut mieux que la reecrire ou la perdre."""
    _lot_of(manifest, lot_id)[encode_manifest.MASTER_INVENTORY_FIELD] = [
        {"profile_id": PROFILE}
    ]
    project_dir = _project(tmp_path, manifest)
    avant = (project_dir / "project.json").read_bytes()

    with pytest.raises(encode_manifest.EncodePersistenceError) as excinfo:
        encode_manifest.persist_encode(project_dir, _record(lot_id))

    # Le diagnostic nomme la **vraie** cause: une entree sans cle, et non « pas
    # une liste ». Deux gardes voisines qui rendraient le meme message
    # laisseraient l'une des deux indetectable.
    assert f"ne porte pas de `{encode_manifest.MASTER_INVENTORY_KEY}` textuel" in str(
        excinfo.value
    )
    assert "Aucune ecriture n'a eu lieu" in str(excinfo.value)
    assert (project_dir / "project.json").read_bytes() == avant


def test_un_inventaire_qui_n_est_pas_une_liste_est_refuse(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Et le refus vient bien de la garde de **type**, pas de celle des entrees.

    Sans l'assertion sur le message, ce test resterait vert la garde retiree:
    iterer un dict rend ses cles, qui ne sont pas des mappings, si bien que la
    garde suivante rattrapait le cas et le diagnostic devenait faux.
    """
    _lot_of(manifest, lot_id)[encode_manifest.MASTER_INVENTORY_FIELD] = {"path": "x"}
    project_dir = _project(tmp_path, manifest)

    with pytest.raises(encode_manifest.EncodePersistenceError) as excinfo:
        encode_manifest.persist_encode(project_dir, _record(lot_id))
    assert "n'est pas une liste" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC 1 / AC 2 / AC 3 -- la garde de transition, ses six oui et ses refus
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("etat", [None, *LOT_STATES])
def test_les_six_transitions_acceptees_posent_encode(
    manifest: dict, lot_id: str, etat: str | None
) -> None:
    """Six, et non cinq: les cinq etats **plus** `None`.

    `encode` est le maximum de `LOT_STATES`, donc la porte de l'**ordre** ne
    refuse jamais; `encode -> encode` est acceptee et c'est la condition meme de
    l'idempotence.
    """
    lot = _lot_of(manifest, lot_id)
    if etat is None:
        lot.pop("state", None)
    else:
        lot["state"] = etat

    merge = encode_manifest.build_encode_manifest(manifest, _record(lot_id))
    assert merge.state_written == encode_manifest.ENCODE_LOT_STATE
    assert _lot_of(merge.manifest, lot_id)["state"] == "encode"


def test_il_y_a_bien_six_transitions_acceptees_et_pas_cinq() -> None:
    assert len(LOT_STATES) == 5
    assert LOT_STATES.index("encode") == len(LOT_STATES) - 1


@pytest.mark.parametrize("etat", ["", "encoded", "ENCODE", 42, ["encode"]])
def test_un_etat_courant_hors_vocabulaire_est_refuse_durement(
    tmp_path: Path, manifest: dict, lot_id: str, etat
) -> None:
    """**La garde a bien une branche de refus, et elle est atteignable.**

    Elle est orthogonale a l'ordre: `current_state not in LOT_STATES`. Elle est
    atteignable parce que `_load_existing_manifest` relit par `load_manifest`,
    qui fait un `json.load` **sans validation** -- un `project.json` edite a la
    main ou produit par un outil tiers arrive tel quel jusqu'ici.
    """
    _lot_of(manifest, lot_id)["state"] = etat
    project_dir = _project(tmp_path, manifest)
    avant = (project_dir / "project.json").read_bytes()

    with pytest.raises(encode_manifest.EncodeLotStateRefused) as excinfo:
        encode_manifest.persist_encode(project_dir, _record(lot_id))

    message = str(excinfo.value)
    # L'erreur typee porte **les deux** etats **en propre**, et non seulement au
    # travers du message de la garde qu'elle enveloppe: sans cette precision,
    # masquer les deux valeurs dans le message du module laissait le test vert,
    # parce que `validate_lot_state_transition` nomme deja l'etat courant dans
    # le sien. Un diagnostic qui ne tient que par ce qu'il cite se perd au
    # premier reformulage de la brique citee.
    assert f"state={etat!r}" in message
    assert f"la transition {etat!r} -> {encode_manifest.ENCODE_LOT_STATE!r}" in message
    assert "Aucune ecriture n'a eu lieu" in message
    assert (project_dir / "project.json").read_bytes() == avant


def test_le_refus_de_vocabulaire_est_atteignable_depuis_un_manifest_sur_disque(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Mesure et non raisonnement: `load_manifest` ne valide pas, donc la valeur
    fautive traverse bien la relecture jusqu'a la garde."""
    _lot_of(manifest, lot_id)["state"] = "encoded"
    project_dir = _project(tmp_path, manifest)

    # Le document est refuse par le schema... et lu sans broncher par la
    # relecture que la persistance emploie.
    with pytest.raises(ValidationError):
        validate_manifest(project_dir / "project.json")
    relu = extraction_manifest._load_existing_manifest(project_dir / "project.json")
    assert _lot_of(relu, lot_id)["state"] == "encoded"

    with pytest.raises(encode_manifest.EncodeLotStateRefused):
        encode_manifest.persist_encode(project_dir, _record(lot_id))


def test_l_etat_est_pose_par_la_garde_et_jamais_en_dur(
    manifest: dict, lot_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La garde est le **seul** juge: si elle refuse tout, rien n'est pose.

    Un module qui affecterait `lot["state"] = "encode"` sans passer par elle
    resterait vert ici; c'est ce que ce test interdit.
    """

    def refuse_tout(current_state, new_state):
        raise ValidationError("refus force par le test")

    monkeypatch.setattr(encode_manifest, "validate_lot_state_transition", refuse_tout)
    with pytest.raises(encode_manifest.EncodeLotStateRefused):
        encode_manifest.build_encode_manifest(manifest, _record(lot_id))


def test_encode_avait_bien_le_depot_pour_seul_etat_sans_ecrivain() -> None:
    """Constat de depart, verifie a l'execution et non recopie de la story.

    Les quatre autres etats ont chacun une constante de module qui les pose;
    `encode` n'en avait aucune avant cette story, qui la fournit.
    """
    from mixed_media_utility.io import pdf_manifest, reconstruction, scan_manifest

    ecrivains = {
        extraction_manifest.EXTRACTION_LOT_STATE,
        pdf_manifest.PDF_LOT_STATE,
        scan_manifest.SCAN_LOT_STATE,
        reconstruction.DEFAULT_LOT_STATE,
        encode_manifest.ENCODE_LOT_STATE,
    }
    assert ecrivains == set(LOT_STATES)


# ---------------------------------------------------------------------------
# AC 9 -- les trois versions de manifest, sur le motif de 5.7
# ---------------------------------------------------------------------------


def test_un_manifest_legacy_est_refuse_sans_rien_ecrire(
    tmp_path: Path, lot_id: str
) -> None:
    legacy = {"id": "poc", "meta": {"lot": {"state": "scan"}}}
    project_dir = _project(tmp_path, legacy)
    avant = (project_dir / "project.json").read_bytes()

    with pytest.raises(LegacyManifestError) as excinfo:
        encode_manifest.persist_encode(project_dir, _record(lot_id))

    assert "schema_version" in str(excinfo.value)
    assert (project_dir / "project.json").read_bytes() == avant


def test_une_version_de_schema_inconnue_est_refusee(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    manifest["schema_version"] = "3.0"
    project_dir = _project(tmp_path, manifest)

    with pytest.raises(LegacyManifestError) as excinfo:
        encode_manifest.persist_encode(project_dir, _record(lot_id))
    assert "3.0" in str(excinfo.value)


def test_un_champ_d_encode_sur_un_manifest_v2_0_serait_refuse_apres_ecriture(
    tmp_path: Path, lot_id: str, other_lot_id: str
) -> None:
    """**Le trou du modele 5.11, mesure.**

    `project.schema.v2-0.json` porte lui aussi `lots[].items` en
    `additionalProperties: false`: poser l'inventaire sur un document v2.0 sans
    le migrer le ferait echouer a la validation du temporaire, donc **apres**
    que la video a ete ecrite. C'est le fait que l'AC 9 existe pour fermer.
    """
    v2_0 = _manifest_v2_0(lot_id, other_lot_id)
    chemin = tmp_path / "v2-0-sain.json"
    chemin.write_text(json.dumps(v2_0), encoding="utf-8")
    # Le document v2.0 est valide **tel quel**: il n'y a donc rien d'autre que
    # l'inventaire pour expliquer le refus qui suit.
    validate_manifest(chemin)

    _lot_of(v2_0, lot_id)[encode_manifest.MASTER_INVENTORY_FIELD] = [
        _master(lot_id).to_entry()
    ]
    chemin = tmp_path / "v2-0.json"
    chemin.write_text(json.dumps(v2_0), encoding="utf-8")

    with pytest.raises(ValidationError) as excinfo:
        validate_manifest(chemin)
    assert "Additional properties are not allowed" in str(excinfo.value)
    assert encode_manifest.MASTER_INVENTORY_FIELD in str(excinfo.value)


def test_un_manifest_v2_0_est_migre_en_memoire_et_persiste(
    tmp_path: Path, lot_id: str, other_lot_id: str, prefix_lot_id: str
) -> None:
    """La v2.0 est **migree**, jamais refusee: elle est declaree lisible par
    `SCHEMA_PATHS_BY_VERSION`, et la refuser ferait d'un projet v2.0 reel un
    chemin de panne sans issue -- la section `video` de la v2.0 est interdite par
    le contrat v2.1, donc toute relance echouerait a l'identique."""
    project_dir = _project(tmp_path, _manifest_v2_0(lot_id, other_lot_id))

    persisted = encode_manifest.persist_encode(project_dir, _record(lot_id))

    ecrit = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert ecrit["schema_version"] == CURRENT_SCHEMA_VERSION
    assert _lot_of(ecrit, lot_id)["state"] == "encode"
    assert _lot_of(ecrit, lot_id)[encode_manifest.MASTER_INVENTORY_FIELD]
    assert persisted.state_written == "encode"
    # Les deux lots **non** vises n'ont rien recu et l'ordre est preserve: la
    # migration ne deplace pas la cible, et le lot de tete -- dont l'identifiant
    # prefixe celui de la cible -- reste indemne.
    for indemne in (other_lot_id, prefix_lot_id):
        assert encode_manifest.MASTER_INVENTORY_FIELD not in _lot_of(ecrit, indemne)
    assert [lot["lot_id"] for lot in ecrit["lots"]] == [
        prefix_lot_id,
        lot_id,
        other_lot_id,
    ]
    # Et le document ecrit est valide contre le schema courant.
    validate_manifest(project_dir / "project.json")


def test_le_module_n_expose_aucun_controle_prealable(tmp_path: Path) -> None:
    """**Finding de la campagne de mutation, ferme ici.**

    La premiere version de cette story branchait un `check_encode_persistable`
    dans `cli.encode_command`, entre `plan_encode` et le recapitulatif, pour ne
    pas payer des minutes d'encodage a un refus connaissable au depart. Deux
    mutants qui le neutralisaient ont **survecu**, et la mesure qui suit dit
    pourquoi: il etait inatteignable. `cli.encode_command` valide le manifest
    contre son schema **avant** de rien decider, et cette validation refuse deja
    les quatre cas. Le controle a donc ete retire plutot que teste: du code que
    rien ne peut atteindre n'est pas une garde, c'est une garde apparente.
    """
    assert not hasattr(encode_manifest, "check_encode_persistable")


@pytest.mark.parametrize(
    "mutation, attendu",
    [
        (lambda d: d["lots"][0].__setitem__("state", "encoded"), "lots.0.state"),
        (lambda d: d.__setitem__("schema_version", "9.9"), "schema_version"),
        (lambda d: d.pop("schema_version"), "Additional properties"),
        (lambda d: d.__setitem__("schema_version", "2.0"), "Additional properties"),
    ],
)
def test_les_quatre_refus_de_persistance_sont_deja_opposes_avant_l_encodage(
    tmp_path: Path, mutation, attendu: str, capsys
) -> None:
    """Mesure, et non raisonnement: qui refuse, et avant quoi.

    Les quatre documents que `_assert_mergeable` et `_resolve_state`
    refuseraient -- etat hors vocabulaire, `schema_version` inconnue, manifest
    legacy, document etiquete v2.0 -- sont refuses par le `validate_manifest` de
    la commande, en tete, **avant** `plan_encode`. Aucun master n'est produit, et
    le code de sortie est `1`.

    **Precision issue de la revue, et elle porte sur le quatrieme cas.** Ce que
    ce test etiquette `"2.0"` est un document v2.1 **re-etiquete**, refuse parce
    que le schema v2.0 gele ne connait ni `output_frames_dir` ni
    `synthetic_frames`. Un v2.0 **authentique**, lui, traverse `validate_manifest`
    sans un mot: il est refuse plus loin, par `plan_encode` -- voir
    `test_integration_un_v2_0_authentique_traverse_la_validation_et_est_refuse_par_le_plan`.
    Les deux objets ne sont pas le meme, et seul le second dit qui refuse
    reellement un projet v2.0 du terrain.
    """
    from test_encode_command import LOT, scanned_project

    project_dir, _ = scanned_project(tmp_path)
    chemin = project_dir / "project.json"
    document = json.loads(chemin.read_text(encoding="utf-8"))
    mutation(document)
    chemin.write_text(json.dumps(document), encoding="utf-8")

    code = cli.main(["encode", "--project", str(project_dir), "--lot", LOT, "--yes"])
    capture = capsys.readouterr()

    assert code == 1
    assert attendu in capture.err
    # Rien n'a ete encode: le refus est bien en amont, pas apres coup.
    outputs = project_dir / project_layout.OUTPUTS_DIRNAME
    assert not outputs.exists() or not list(outputs.glob("*.mov"))
    assert "Recapitulatif de l'encodage" not in capture.out


# ---------------------------------------------------------------------------
# AC 10 -- le schema, et ce qu'il refuse
# ---------------------------------------------------------------------------


def test_un_champ_non_declare_fait_echouer_la_validation_du_lot(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Mesure du piege: `lots[].items` est en `additionalProperties: false`.

    Un champ non declare au schema ne se voit pas a la fusion: il se voit a la
    validation du temporaire, c'est-a-dire **apres** que la video a ete ecrite.
    """
    _lot_of(manifest, lot_id)["encoded_master_size_bytes"] = 42
    chemin = tmp_path / "avec-champ-inconnu.json"
    chemin.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValidationError) as excinfo:
        validate_manifest(chemin)
    assert "Additional properties are not allowed" in str(excinfo.value)


def test_le_document_produit_valide_contre_le_schema_reel(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    project_dir = _project(tmp_path, manifest)
    encode_manifest.persist_encode(project_dir, _record(lot_id, incomplete=True))
    validate_manifest(project_dir / "project.json")


def test_le_schema_impose_les_quatre_champs_d_une_entree_de_master(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Chaque champ de `ENCODE_MASTER_FIELDS` est `required` au schema: une
    entree amputee est refusee, champ par champ."""
    entree = _master(lot_id).to_entry()
    assert len(encode_manifest.ENCODE_MASTER_FIELDS) == 4
    for champ in encode_manifest.ENCODE_MASTER_FIELDS:
        ampute = {cle: valeur for cle, valeur in entree.items() if cle != champ}
        document = copy.deepcopy(manifest)
        _lot_of(document, lot_id)[encode_manifest.MASTER_INVENTORY_FIELD] = [ampute]
        chemin = tmp_path / f"sans-{champ}.json"
        chemin.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ValidationError):
            validate_manifest(chemin)


@pytest.mark.parametrize(
    "champ, valeur",
    [
        # `type: integer`, et non `number`: un cardinal de frames fractionnaire
        # n'existe pas, et le declarer ferait echouer la commande **apres**
        # l'encodage a la premiere relecture typee.
        ("frame_count", 1.5),
        # `minimum: 0`: un cardinal negatif est une corruption, pas une valeur.
        ("frame_count", -1),
        # `minLength: 1`: un profil vide ne designe aucune entree du catalogue.
        ("profile_id", ""),
        # `type: boolean`: la chaine "true" est le piege classique du JSON ecrit
        # a la main, et `incomplete` est precisement le champ qu'un operateur
        # serait tente d'editer.
        ("incomplete", "true"),
        # L'antislash est interdit sur la cle: un chemin en separateurs Windows
        # ne designe aucun fichier sous POSIX, et la cle est aussi ce par quoi
        # l'inventaire est apparie et trie.
        ("path", "outputs\\master.mov"),
    ],
)
def test_le_schema_contraint_chaque_champ_d_une_entree_de_master(
    tmp_path: Path, manifest: dict, lot_id: str, champ: str, valeur
) -> None:
    """**Les cinq contraintes ajoutees par la story, mesurees une par une.**

    La suite ne mesurait que `additionalProperties`, `required` et le
    `minLength` de `path`: mesure de revue, cinq mutants qui relachaient les
    autres survivaient tous les cinq. Le schema est ici un organe de la story et
    non une annexe -- un champ mal declare fait echouer la commande **apres**
    que la video a ete ecrite.
    """
    entree = _master(lot_id).to_entry()
    entree[champ] = valeur
    _lot_of(manifest, lot_id)[encode_manifest.MASTER_INVENTORY_FIELD] = [entree]
    chemin = tmp_path / f"contrainte-{champ}.json"
    chemin.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValidationError):
        validate_manifest(chemin)


def test_le_schema_refuse_un_champ_de_trop_dans_une_entree_de_master(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """L'entree d'inventaire est en `additionalProperties: false`, comme le lot
    qui la porte: c'est ce qui empeche une story ulterieure d'y glisser une
    taille de fichier ou une horodate sans passer par la table."""
    entree = _master(lot_id).to_entry()
    entree["encoded_at"] = "2026-08-11T00:00:00Z"
    _lot_of(manifest, lot_id)[encode_manifest.MASTER_INVENTORY_FIELD] = [entree]
    chemin = tmp_path / "champ-de-trop.json"
    chemin.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValidationError) as excinfo:
        validate_manifest(chemin)
    assert "Additional properties are not allowed" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC 6 -- `video.codec_target` recoit son premier producteur
# ---------------------------------------------------------------------------


def test_la_completude_du_manifest_devient_satisfaite_apres_encode(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """La fonction dont la docstring dit « before a final encode » etait
    insatisfiable sur le manifest reel: `video.codec_target` n'avait aucun
    producteur. Elle l'a maintenant."""
    with pytest.raises(ValidationError) as excinfo:
        validate_manifest_completeness(manifest)
    assert "video.codec_target" in str(excinfo.value)

    project_dir = _project(tmp_path, manifest)
    persisted = encode_manifest.persist_encode(project_dir, _record(lot_id))
    assert persisted.manifest["video"]["codec_target"] == PROFILE
    validate_manifest_completeness(persisted.manifest)


def test_codec_target_est_reecrit_par_le_profil_retenu_et_le_dit(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Reecrire une cible **deja posee** est un changement, donc un constat."""
    manifest.setdefault("video", {})["codec_target"] = "valeur-precedente"
    project_dir = _project(tmp_path, manifest)
    persisted = encode_manifest.persist_encode(
        project_dir, _record(lot_id, profile_id=OTHER_PROFILE)
    )
    assert persisted.manifest["video"]["codec_target"] == OTHER_PROFILE
    assert encode_manifest.ENCODE_CODEC_TARGET_REPLACED in persisted.findings
    assert (
        encode_manifest.ENCODE_CODEC_TARGET_REPLACED
        in encode_manifest.ENCODE_PERSISTENCE_CODES
    )


def test_le_premier_producteur_de_codec_target_ne_constate_rien(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Poser la valeur la ou il n'y en avait aucune n'ecrase rien.

    Le manifest reel du depot porte une section `video` **vide**: c'est le cas
    nominal du premier encodage d'un projet, et il ne doit rien constater.
    """
    assert "codec_target" not in manifest.get("video", {})
    project_dir = _project(tmp_path, manifest)
    persisted = encode_manifest.persist_encode(project_dir, _record(lot_id))
    assert persisted.manifest["video"]["codec_target"] == PROFILE
    assert encode_manifest.ENCODE_CODEC_TARGET_REPLACED not in persisted.findings


def test_reecrire_la_meme_cible_d_encodage_ne_constate_rien(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Le constat nomme un **changement**, pas une repetition: sinon toute
    relance idempotente le porterait."""
    project_dir = _project(tmp_path, manifest)
    encode_manifest.persist_encode(project_dir, _record(lot_id))
    persisted = encode_manifest.persist_encode(project_dir, _record(lot_id))
    assert persisted.findings == ()


def test_encoder_un_second_lot_a_un_autre_profil_est_constate(
    tmp_path: Path, manifest: dict, lot_id: str, other_lot_id: str
) -> None:
    """**La portee du champ est le document, la decision est le lot.**

    Mesure de revue, reproduite ici au niveau du module: encoder un lot en
    `prores_hq` puis un autre en `prores_422` **change** `video.codec_target`
    pour le projet entier, et relancer le premier a l'identique le rechange --
    sans qu'aucune information neuve n'arrive. Le champ n'est pas deplace vers
    le lot (contrat de l'Epic 2, et `CRITICAL_PROJECT_FIELDS_V2_1` le designe au
    niveau document); ce que cette story ferme est le **silence**: chacun de ces
    deux ecrasements porte desormais son constat.

    La verite par master, elle, reste dans l'inventaire: les deux lots gardent
    chacun le `profile_id` de leur propre master.
    """
    project_dir = _project(tmp_path, manifest)

    premier = encode_manifest.persist_encode(
        project_dir, _record(lot_id, profile_id=PROFILE)
    )
    assert premier.findings == ()

    second = encode_manifest.persist_encode(
        project_dir, _record(other_lot_id, profile_id=OTHER_PROFILE)
    )
    assert second.manifest["video"]["codec_target"] == OTHER_PROFILE
    assert encode_manifest.ENCODE_CODEC_TARGET_REPLACED in second.findings

    # Relance **a l'identique** du premier lot: rien de neuf, et pourtant le
    # document change. C'est la limite; elle est desormais dite.
    rejeu = encode_manifest.persist_encode(
        project_dir, _record(lot_id, profile_id=PROFILE)
    )
    assert rejeu.manifest["video"]["codec_target"] == PROFILE
    assert encode_manifest.ENCODE_CODEC_TARGET_REPLACED in rejeu.findings
    assert encode_manifest.ENCODE_MASTER_ENTRY_REPLACED not in rejeu.findings

    inventaire = {
        identifiant: _lot_of(rejeu.manifest, identifiant)[
            encode_manifest.MASTER_INVENTORY_FIELD
        ][0]["profile_id"]
        for identifiant in (lot_id, other_lot_id)
    }
    assert inventaire == {lot_id: PROFILE, other_lot_id: OTHER_PROFILE}


def test_la_limite_de_portee_de_codec_target_est_ecrite_en_tete_de_module() -> None:
    """L'AC 7 disait « deux `encode` identiques ne changent pas le manifest,
    octet a octet » sans restriction. C'est vrai du **meme lot** et faux des
    qu'un projet melange deux profils: la restriction est ecrite la ou le
    prochain lecteur regardera."""
    doc = encode_manifest.__doc__ or ""
    assert "portee document" in doc
    assert "portee lot" in doc
    # La restriction de l'invariant d'idempotence est ecrite a cote de la table
    # qui le porte, et non seulement en tete de fichier.
    module_source = Path(encode_manifest.__file__).read_text(encoding="utf-8")
    assert "du meme lot" in module_source


# ---------------------------------------------------------------------------
# AC 11 -- `artifacts.outputs_dir`, ancre sur la constante
# ---------------------------------------------------------------------------


def test_outputs_dir_est_ancre_sur_la_constante_et_non_sur_un_litteral(
    tmp_path: Path, manifest: dict, lot_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le test qui distingue reellement l'ancrage du litteral: on deplace la
    constante, et la valeur ecrite doit suivre."""
    project_dir = _project(tmp_path, manifest)
    persisted = encode_manifest.persist_encode(project_dir, _record(lot_id))
    assert persisted.manifest["artifacts"]["outputs_dir"] == (
        project_layout.OUTPUTS_DIRNAME
    )

    monkeypatch.setattr(project_layout, "OUTPUTS_DIRNAME", "sorties")
    assert encode_manifest.outputs_dir_value() == "sorties"
    # Le **chemin du master** est ancre sur la meme constante, et pas sur un
    # second litteral qui divergerait au premier ajustement.
    racine = Path("/tmp/projet")
    assert encode_manifest.master_relative_path(
        racine, racine / "sorties" / "m.mov"
    ) == "sorties/m.mov"


def test_outputs_dir_n_ecrase_pas_frames_dir(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    avant = manifest["artifacts"]["frames_dir"]
    project_dir = _project(tmp_path, manifest)
    persisted = encode_manifest.persist_encode(project_dir, _record(lot_id))
    assert persisted.manifest["artifacts"]["frames_dir"] == avant


# ---------------------------------------------------------------------------
# AC 12 -- mise a jour en place, jamais de perte
# ---------------------------------------------------------------------------


def test_un_lot_absent_echoue_sans_rien_ecrire(
    tmp_path: Path, manifest: dict
) -> None:
    project_dir = _project(tmp_path, manifest)
    avant = (project_dir / "project.json").read_bytes()

    with pytest.raises(encode_manifest.EncodeLotAbsentError) as excinfo:
        encode_manifest.persist_encode(project_dir, _record("lot-qui-n-existe-pas"))

    assert "ne cree aucun lot" in str(excinfo.value)
    assert (project_dir / "project.json").read_bytes() == avant


def test_un_manifest_sans_liste_lots_echoue_sans_rien_ecrire(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    manifest.pop("lots")
    project_dir = _project(tmp_path, manifest)
    with pytest.raises(encode_manifest.EncodeLotAbsentError):
        encode_manifest.persist_encode(project_dir, _record(lot_id))


def test_aucun_champ_d_un_manifest_riche_n_est_perdu(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Non-perte **champ par champ**, sur tout le document."""
    avant = copy.deepcopy(manifest)
    project_dir = _project(tmp_path, manifest)
    apres = encode_manifest.persist_encode(project_dir, _record(lot_id)).manifest

    for cle, valeur in avant.items():
        assert cle in apres, cle
        if cle not in ("lots", "video", "artifacts"):
            assert apres[cle] == valeur, cle
    for lot_avant in avant["lots"]:
        lot_apres = _lot_of(apres, lot_avant["lot_id"])
        for cle, valeur in lot_avant.items():
            if cle == "state":
                continue
            assert lot_apres[cle] == valeur, (lot_avant["lot_id"], cle)


def test_le_document_n_est_pas_reconstruit_mais_mis_a_jour_en_place(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Contre-exemple du depot: `reconstruct_project_manifest` reconstruit de
    zero et reposait `artifacts: {}` et `video: {}`."""
    manifest["artifacts"]["un_champ_tiers"] = "conserve"
    manifest["video"]["un_champ_tiers"] = "conserve aussi"
    project_dir = _project(tmp_path, manifest)
    apres = encode_manifest.persist_encode(project_dir, _record(lot_id)).manifest
    assert apres["artifacts"]["un_champ_tiers"] == "conserve"
    assert apres["video"]["un_champ_tiers"] == "conserve aussi"


def test_une_section_de_tete_qui_n_est_pas_un_objet_est_refusee(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """Sans garde, `dict("x")` levait une erreur **nue**, hors hierarchie."""
    manifest["video"] = "pas un objet"
    project_dir = _project(tmp_path, manifest)
    with pytest.raises(encode_manifest.EncodePersistenceError):
        encode_manifest.persist_encode(project_dir, _record(lot_id))


def test_un_manifest_qui_n_est_pas_un_objet_json_est_refuse(
    tmp_path: Path, lot_id: str
) -> None:
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    (project_dir / "project.json").write_text("42", encoding="utf-8")
    with pytest.raises(encode_manifest.EncodeManifestAbsentError) as excinfo:
        encode_manifest.persist_encode(project_dir, _record(lot_id))
    assert "n'est pas un objet JSON (int)" in str(excinfo.value)


def test_un_projet_sans_manifest_echoue_sans_en_creer_un(
    tmp_path: Path, lot_id: str
) -> None:
    """Et le diagnostic dit **manifest absent**, pas « manifest mal forme ».

    Les deux cas partagent leur classe d'erreur; seul le message les distingue.
    Sans cette assertion, retirer la branche « absent » laissait le cas tomber
    dans la garde de type, qui annoncait alors a l'operateur un `project.json`
    « qui n'est pas un objet JSON (NoneType) » -- pour un fichier qui n'existe
    pas. Un diagnostic faux coute plus cher qu'un diagnostic absent.
    """
    project_dir = tmp_path / "projet"
    project_dir.mkdir()
    with pytest.raises(encode_manifest.EncodeManifestAbsentError) as excinfo:
        encode_manifest.persist_encode(project_dir, _record(lot_id))
    assert "Aucun project.json lisible" in str(excinfo.value)
    assert "objet JSON" not in str(excinfo.value)
    assert list(project_dir.iterdir()) == []


# ---------------------------------------------------------------------------
# AC 8 -- ecriture atomique, validee AVANT bascule
# ---------------------------------------------------------------------------


def test_un_document_invalide_laisse_le_manifest_precedent_strictement_intact(
    tmp_path: Path, manifest: dict, lot_id: str
) -> None:
    """`minLength: 1` sur `encoded_masters[].path`: une chaine vide fait echouer
    la validation du **temporaire**, donc `_atomic_write`, donc la persistance --
    et le `project.json` precedent ne bouge pas d'un octet."""
    project_dir = _project(tmp_path, manifest)
    avant = (project_dir / "project.json").read_bytes()
    invalide = encode_manifest.EncodeRecord(
        lot_id=lot_id,
        master=encode_manifest.EncodedMaster(
            path="", profile_id=PROFILE, frame_count=10, incomplete=False
        ),
        codec_target=PROFILE,
        outputs_dir=encode_manifest.outputs_dir_value(),
        masters_family_key=PROFILE,
    )

    with pytest.raises(ManifestWriteError):
        encode_manifest.persist_encode(project_dir, invalide)

    assert (project_dir / "project.json").read_bytes() == avant
    assert [p.name for p in project_dir.iterdir()] == ["project.json"]


def test_un_dossier_non_inscriptible_reste_dans_la_hierarchie_du_depot(
    tmp_path: Path, manifest: dict, lot_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_atomic_write` ouvre son temporaire **avant** son propre `try`: la panne
    la plus probable de ce chemin remonte en `OSError` nue.

    Simulee a la source plutot que par un `chmod`: la suite tourne en root dans
    l'environnement de reference, et root traverse les permissions POSIX -- un
    dossier en lecture seule y « reussit » l'ecriture. Le correctif de fond
    appartient au module de la story 3.4 et reste transverse: ici on verifie que
    l'erreur arrive dans la bonne famille et que rien n'est ecrit.
    """
    project_dir = _project(tmp_path, manifest)
    avant = (project_dir / "project.json").read_bytes()

    def disque_plein(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(
        extraction_manifest.tempfile, "NamedTemporaryFile", disque_plein
    )

    with pytest.raises(ExtractionPersistenceError) as excinfo:
        encode_manifest.persist_encode(project_dir, _record(lot_id))

    assert "intact" in str(excinfo.value)
    assert (project_dir / "project.json").read_bytes() == avant
    assert [p.name for p in project_dir.iterdir()] == ["project.json"]


def test_les_fonctions_d_ecriture_sont_importees_et_non_redefinies() -> None:
    """« Il n'existe pas de seconde version de ces fonctions dans le depot, et il
    ne doit pas en exister. »"""
    assert encode_manifest._atomic_write is extraction_manifest._atomic_write
    assert encode_manifest._load_existing_manifest is (
        extraction_manifest._load_existing_manifest
    )
    assert encode_manifest._migrate_v2_0 is extraction_manifest._migrate_v2_0
    assert encode_manifest._relative_posix is extraction_manifest._relative_posix
    # `_serialize` n'est pas importee: elle est atteinte **par** `_atomic_write`,
    # et l'importer sans l'appeler serait du code mort. Ce qui compte est qu'il
    # n'en existe pas de seconde version -- verifie ici.
    source = Path(encode_manifest.__file__).read_text(encoding="utf-8")
    for interdit in ("def _serialize", "def _atomic_write", "json.dumps"):
        assert interdit not in source, interdit


# ---------------------------------------------------------------------------
# AC 15 -- frontieres tenues, verrouillees par coherence ET par statique
# ---------------------------------------------------------------------------


def test_le_module_ne_nomme_aucun_recalcul_d_identifiant() -> None:
    """Verrou **statique** de la story 5.11: ces noms n'apparaissent pas.

    Un test de coherence seul ne prouverait rien -- deux chemins independants
    qui se trouvent d'accord le satisferaient.
    """
    source = Path(encode_manifest.__file__).read_text(encoding="utf-8")
    for interdit in ("get_profile", "build_lot_id", "build_master_filename"):
        assert not re.search(rf"\b{interdit}\b", source), interdit


def test_le_module_n_importe_rien_hors_de_son_perimetre() -> None:
    """Porte sur les **imports reels**, jamais sur le texte du fichier.

    Un `grep` nu confondrait une reference en prose -- le module cite
    `codec_profiles` et `video_metadata` pour dire precisement qu'il ne les
    appelle pas -- avec une dependance. L'arbre syntaxique, lui, ne se trompe
    pas.
    """
    import ast

    arbre = ast.parse(Path(encode_manifest.__file__).read_text(encoding="utf-8"))
    modules: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            modules.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            modules.add(noeud.module or "")
            modules.update(alias.name for alias in noeud.names)

    for interdit in (
        "codec_profiles",
        "video_metadata",
        "scan_manifest",
        "pdf_manifest",
        "reconstruction",
        "metadata_matrix",
        "scan_output_frames",
        "subprocess",
        "encode",
    ):
        assert not any(
            nom == interdit or nom.endswith(f".{interdit}") for nom in modules
        ), (interdit, sorted(modules))


def test_le_chemin_declare_est_celui_que_le_constructeur_de_nom_produit(
    lot_id: str,
) -> None:
    """Test de **coherence**: le chemin persiste designe bien le fichier que la
    story 6.1 ecrit. Bati par le vrai constructeur, cote test seulement."""
    attendu = naming.build_master_filename(
        lot_id=lot_id,
        profile_id=PROFILE,
        container=codec_profiles.get_profile(PROFILE).container,
        resolution_segment="",
    )
    chemin = encode_manifest.master_relative_path(
        Path("/tmp/projet"), Path("/tmp/projet") / project_layout.OUTPUTS_DIRNAME / attendu
    )
    assert chemin == f"{project_layout.OUTPUTS_DIRNAME}/{attendu}"


@pytest.mark.parametrize(
    "ailleurs",
    [
        # Le parent differe **et** son nom aussi: le cas facile.
        "/tmp/ailleurs/master.mov",
        # Le parent porte le **meme nom** sans etre le meme dossier: le
        # `outputs/` d'un **autre projet**. Sans ce cas, la garde pouvait etre
        # reduite a « le dossier s'appelle outputs » sans qu'un test bronche --
        # mesure de revue, 148 tests verts --, et le master d'un autre projet
        # aurait ete declare sous un chemin relatif ne designant aucun fichier du
        # projet courant, c'est-a-dire exactement le tort que la garde evite.
        "/tmp/autre-projet/outputs/master.mov",
    ],
)
def test_un_master_hors_du_dossier_de_sortie_est_refuse(ailleurs: str) -> None:
    """Sans cette confrontation, le manifest declarerait un chemin qui ne designe
    aucun fichier -- un mensonge silencieux, et permanent."""
    with pytest.raises(encode_manifest.EncodePersistenceError) as excinfo:
        encode_manifest.master_relative_path(Path("/tmp/projet"), Path(ailleurs))
    assert "Aucune ecriture n'a eu lieu" in str(excinfo.value)
    assert str(Path(ailleurs)) in str(excinfo.value)


def test_la_garde_du_dossier_de_sortie_compare_le_dossier_et_pas_son_nom() -> None:
    """Le meme fait, pris par l'autre bout: le **bon** dossier passe.

    Les deux assertions ensemble distinguent une egalite de chemin d'une egalite
    de nom: la premiere accepte, la seconde refuse, et le nom du dossier est
    identique dans les deux cas.
    """
    accepte = encode_manifest.master_relative_path(
        Path("/tmp/projet"),
        Path("/tmp/projet") / project_layout.OUTPUTS_DIRNAME / "m.mov",
    )
    assert accepte == f"{project_layout.OUTPUTS_DIRNAME}/m.mov"
    with pytest.raises(encode_manifest.EncodePersistenceError):
        encode_manifest.master_relative_path(
            Path("/tmp/projet"),
            Path("/tmp/voisin") / project_layout.OUTPUTS_DIRNAME / "m.mov",
        )


def test_le_chemin_declare_est_relatif_et_en_separateurs_posix(lot_id: str) -> None:
    project_dir = Path("/tmp/projet")
    chemin = encode_manifest.master_relative_path(
        project_dir, project_dir / project_layout.OUTPUTS_DIRNAME / "m.mov"
    )
    assert not Path(chemin).is_absolute()
    assert "\\" not in chemin
    assert chemin.startswith(f"{project_layout.OUTPUTS_DIRNAME}/")


# ---------------------------------------------------------------------------
# AC 3 / AC 13 -- integration: l'etat vient de la persistance REELLE
# ---------------------------------------------------------------------------


def _projet_scanne(tmp_path: Path):
    """Projet reel scanne, emprunte a la suite de la story 6.1.

    Reutiliser sa chaine plutot que d'en ecrire une seconde: c'est la meme
    exigence « contre les vrais producteurs », et une seconde chaine de fixture
    divergerait de la premiere au premier ajustement.
    """
    from test_encode_command import LOT, scanned_project

    project_dir, manifest = scanned_project(tmp_path)
    return project_dir, manifest, LOT


def test_integration_l_etat_encode_vient_de_la_persistance_reelle(tmp_path: Path):
    """Chaine complete: `plan_encode` -> `execute_plan` -> `persist_encode`.

    Ce qui est nouveau par rapport aux six tests parametres deja verts sur
    `"encode"` (extraction, pdf, scan): l'etat est **produit par le depot** au
    lieu d'etre injecte par une fixture.
    """
    project_dir, manifest, lot = _projet_scanne(tmp_path)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=lot)
    swept = encode_module.prepare_output_directory(plan)
    result = encode_module.execute_plan(plan, swept=swept)

    # Le master est a son chemin **final**: c'est la condition de l'AC 13.
    master = Path(result.outcome.output_path)
    assert master.is_file()
    assert master == plan.output_path

    record = encode_manifest.EncodeRecord.from_command_result(result)
    persisted = encode_manifest.persist_encode(project_dir, record)

    ecrit = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    lot_ecrit = _lot_of(ecrit, lot)
    assert lot_ecrit["state"] == "encode"
    entree = lot_ecrit[encode_manifest.MASTER_INVENTORY_FIELD][0]
    assert (project_dir / entree["path"]).is_file()
    assert entree["path"] == persisted.master_path
    assert entree["profile_id"] == plan.profile_id
    assert entree["frame_count"] == result.outcome.frame_count
    assert entree["incomplete"] is False
    assert ecrit["video"]["codec_target"] == plan.profile_id
    assert ecrit["artifacts"]["outputs_dir"] == project_layout.OUTPUTS_DIRNAME
    validate_manifest(project_dir / "project.json")


def test_integration_un_lot_encode_ne_peut_plus_etre_re_extrait(tmp_path: Path):
    """Consequence sur les etats voisins, mesuree depuis l'etat **produit**."""
    project_dir, manifest, lot = _projet_scanne(tmp_path)
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=lot)
    result = encode_module.execute_plan(
        plan, swept=encode_module.prepare_output_directory(plan)
    )
    encode_manifest.persist_encode(
        project_dir, encode_manifest.EncodeRecord.from_command_result(result)
    )

    ecrit = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert _lot_of(ecrit, lot)["state"] == "encode"

    # Re-extraction du **meme** lot, par le vrai producteur d'extraction et avec
    # l'identite reelle du projet: elle bute sur l'etat que la persistance vient
    # de poser, et non sur une divergence d'identifiants.
    from test_encode_command import PROJECT, RUSH, real_selection

    with pytest.raises(LotStateConflictError) as excinfo:
        persist_extraction(
            project_dir,
            ExtractionRecord(
                project_id=PROJECT,
                rush_id=RUSH,
                rush_source_name=f"{RUSH}.mov",
                lot_id=lot,
                frames_dir_relative=(
                    f"{project_layout.FRAMES_DIRNAME}/"
                    f"{project_layout.rush_dir_slug(RUSH, 5.0)}"
                ),
                selection=real_selection(),
                fps_source=30.0,
                fps_target=5.0,
                source_width=1920,
                source_height=1080,
                source_fields={},
                confirmation_mode="non_interactif",
                unknown_color_accepted=True,
                confirmed_at="2026-08-11T00:00:00Z",
            ),
        )
    assert "encode" in str(excinfo.value)


def test_integration_le_lot_incomplet_assume_est_declare_incomplet(tmp_path: Path):
    """Ligne conditionnelle d'`EPIC6-ARB-3`: le drapeau existe, la donnee aussi.

    Le master d'un lot troue encode sous `--accept-incomplete-lot` **declare**
    son incompletude, et son `frame_count` est celui des frames reellement
    encodees -- inferieur a `lots[].expected_frame_count`.
    """
    from test_encode_command import LOT, scanned_project

    project_dir, manifest = scanned_project(tmp_path, absent_pages=(1,))
    plan = encode_module.plan_encode(
        project_dir, manifest, lot_id=LOT, accept_incomplete=True
    )
    assert encode_module.ENCODE_INCOMPLETE_ACCEPTED in plan.findings
    assert plan.verdict.complete is False

    result = encode_module.execute_plan(
        plan, swept=encode_module.prepare_output_directory(plan)
    )
    record = encode_manifest.EncodeRecord.from_command_result(result)
    assert record.master.incomplete is True

    persisted = encode_manifest.persist_encode(project_dir, record)
    entree = _lot_of(persisted.manifest, LOT)[
        encode_manifest.MASTER_INVENTORY_FIELD
    ][0]
    assert entree["incomplete"] is True
    assert entree["frame_count"] < _lot_of(persisted.manifest, LOT)[
        "expected_frame_count"
    ]
    validate_manifest(project_dir / "project.json")


def test_integration_les_mires_ne_rendent_pas_un_master_incomplet(tmp_path: Path):
    """Une mire porte un fichier et un contenu **voulu**: elle est deja comptee
    par `lots[].synthetic_frame_count` depuis la story 5.7, et la confondre avec
    un trou ferait declarer incomplet un lot dont aucune page ne manque."""
    from test_encode_command import LOT, SYNTHETIC_REASON, scanned_project

    project_dir, manifest = scanned_project(tmp_path, failures={1: SYNTHETIC_REASON})
    lot = _lot_of(manifest, LOT)
    assert lot["synthetic_frame_count"] > 0
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=LOT)
    assert plan.verdict.complete is True

    result = encode_module.execute_plan(
        plan, swept=encode_module.prepare_output_directory(plan)
    )
    record = encode_manifest.EncodeRecord.from_command_result(result)
    assert record.master.incomplete is False


def test_integration_la_commande_ecrit_le_manifest_de_bout_en_bout(
    tmp_path: Path, capsys
):
    """Cablage reel de la CLI: l'appel est **branche**, pas seulement ecrit.

    Muter la garde sans muter le fil est le defaut que la famille `H` de la
    campagne de la story 6.1 a rendu visible; ici c'est un test qui le tient.
    """
    project_dir, _manifest, lot = _projet_scanne(tmp_path)
    code = cli.main(
        ["encode", "--project", str(project_dir), "--lot", lot, "--yes"]
    )
    assert code == 0
    sortie = capsys.readouterr().out
    assert "Manifest mis a jour" in sortie

    ecrit = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert _lot_of(ecrit, lot)["state"] == "encode"
    assert _lot_of(ecrit, lot)[encode_manifest.MASTER_INVENTORY_FIELD]
    assert ecrit["video"]["codec_target"]
    assert ecrit["artifacts"]["outputs_dir"] == project_layout.OUTPUTS_DIRNAME


def test_integration_les_constats_de_persistance_sont_affiches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    """Un vocabulaire ferme qui n'est jamais affiche est du vocabulaire mort.

    Le constat de remplacement d'entree ne se produit que sur un reencodage dont
    le contenu declare change (un rescan a comble des trous, le `frame_count`
    monte): impossible a provoquer de bout en bout sans falsifier le manifest
    entre deux passes. Le **cablage de l'affichage**, lui, se teste tel quel.
    """
    project_dir, _manifest, lot = _projet_scanne(tmp_path)
    vraie = encode_manifest.persist_encode

    def avec_constat(project_dir_arg, record):
        resultat = vraie(project_dir_arg, record)
        return encode_manifest.PersistedEncode(
            manifest_path=resultat.manifest_path,
            lot_id=resultat.lot_id,
            manifest=resultat.manifest,
            state_written=resultat.state_written,
            master_path=resultat.master_path,
            findings=(encode_manifest.ENCODE_MASTER_ENTRY_REPLACED,),
        )

    monkeypatch.setattr(encode_manifest, "persist_encode", avec_constat)
    assert cli.main(
        ["encode", "--project", str(project_dir), "--lot", lot, "--yes"]
    ) == 0
    assert (
        f"  Constat: {encode_manifest.ENCODE_MASTER_ENTRY_REPLACED}"
        in capsys.readouterr().out
    )


def _journal(project_dir: Path) -> str:
    return (project_dir / project_layout.LOGS_DIRNAME / "encode.log").read_text(
        encoding="utf-8"
    )


def test_integration_la_commande_annonce_le_lot_le_manifest_et_le_master(
    tmp_path: Path, capsys
):
    """**Tout ce que la commande annonce apres l'ecriture, confronte.**

    Mesure de revue: le seul test qui regardait cette sortie asserait
    `"Manifest mis a jour" in sortie`, c'est-a-dire l'intitule et rien d'autre.
    Quatre mutants survivaient -- `lot_id` vide dans le rapport, chemin du
    manifest remplace par le dossier projet, ligne entiere reduite a son
    intitule, entree de journal supprimee. C'est pourtant la seule sortie qui
    dit a l'operateur ce qui vient d'etre ecrit, et le seul endroit ou il
    pourrait constater qu'un master a ete declare sur un lot qu'il ne visait
    pas.
    """
    project_dir, _manifest, lot = _projet_scanne(tmp_path)
    assert cli.main(
        ["encode", "--project", str(project_dir), "--lot", lot, "--yes"]
    ) == 0
    sortie = capsys.readouterr().out

    ecrit = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    entree = _lot_of(ecrit, lot)[encode_manifest.MASTER_INVENTORY_FIELD][0]
    ligne = next(
        ligne for ligne in sortie.splitlines() if ligne.startswith("Manifest mis a jour")
    )

    # La ligne nomme les trois donnees dont l'operateur a besoin: **quel**
    # fichier a ete ecrit, **quel** lot a change d'etat, **quel** master est
    # declare.
    assert str(project_dir / "project.json") in ligne
    assert f"lots[{lot}].state={encode_manifest.ENCODE_LOT_STATE}" in ligne
    assert entree["path"] in ligne

    # Le journal porte la meme trace: c'est la seule apres coup, sur une
    # commande qui dure des minutes.
    journal = _journal(project_dir)
    assert "Manifest mis a jour" in journal
    assert lot in journal
    assert entree["path"] in journal


def test_integration_un_refus_de_persistance_laisse_le_master_et_rend_un(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    """AC 13: master ecrit mais manifest non ecrit = echec `1`, master conserve
    pour diagnostic, `project.json` precedent intact, reprise proposee."""
    project_dir, _manifest, lot = _projet_scanne(tmp_path)
    avant = (project_dir / "project.json").read_bytes()

    def refuse(*args, **kwargs):
        raise encode_manifest.EncodePersistenceError(
            "refus force par le test. Le project.json precedent est intact"
        )

    monkeypatch.setattr(encode_manifest, "persist_encode", refuse)
    code = cli.main(["encode", "--project", str(project_dir), "--lot", lot, "--yes"])

    assert code == 1
    capture = capsys.readouterr()
    assert (project_dir / "project.json").read_bytes() == avant
    masters = list((project_dir / project_layout.OUTPUTS_DIRNAME).glob("*.mov"))
    assert masters, "le master doit rester sur le disque pour diagnostic"
    assert "conserve pour diagnostic" in capture.err
    assert "intact" in capture.err
    assert "--overwrite" in capture.err


#: Trois sabotages appliques au `project.json` **pendant** l'encodage, c'est-a-dire
#: dans la fenetre que le module declare (« aucun verrou »): chacun provoque un
#: refus reel de `persist_encode`, et la classe levee est nommee ici parce que
#: c'est **elle** qui mesure la largeur de la capture de la commande.
_SABOTAGES_DE_LA_FENETRE = [
    pytest.param(
        lambda chemin: chemin.write_text('{"schema_version": "2.1", "lo',
                                        encoding="utf-8"),
        ExtractionPersistenceError,
        "n'est pas un JSON valide",
        id="project.json tronque",
    ),
    pytest.param(
        lambda chemin: chemin.write_text(
            json.dumps(
                {
                    cle: valeur
                    for cle, valeur in json.loads(
                        chemin.read_text(encoding="utf-8")
                    ).items()
                    if cle != "schema_version"
                }
            ),
            encoding="utf-8",
        ),
        LegacyManifestError,
        "schema_version",
        id="schema_version retiree",
    ),
    pytest.param(
        lambda chemin: chemin.write_text("42", encoding="utf-8"),
        encode_manifest.EncodeManifestAbsentError,
        "n'est pas un objet JSON",
        id="manifest reduit a un scalaire",
    ),
]


@pytest.mark.parametrize("saboter, classe, extrait", _SABOTAGES_DE_LA_FENETRE)
def test_la_largeur_de_la_capture_est_mesuree_par_les_classes_reellement_levees(
    tmp_path: Path, saboter, classe, extrait: str
) -> None:
    """**Quelles classes ce chemin leve reellement, et lesquelles echappent a
    `EncodePersistenceError`.**

    Mesure de revue: le seul test du chemin de refus `monkeypatch`ait
    `persist_encode` pour lever `EncodePersistenceError` -- c'est-a-dire la
    **seule** classe qu'aucun retrecissement de la capture n'atteint. Un test qui
    ne peut pas echouer. Or les classes que ce chemin leve reellement sont
    ordinaires: un `project.json` tronque (« coupure de courant, disque plein,
    copie interrompue », dit la docstring de `_load_existing_manifest`) rend une
    `ExtractionPersistenceError` **nue**.

    Ce test-ci mesure la classe; celui qui suit mesure que la commande la
    capture. Les deux ensemble interdisent le resserrement « pour typer plus
    proprement l'erreur du module », qui rendrait une trace Python nue a
    l'operateur **apres** que la video a ete encodee.
    """
    project_dir, manifest, lot = _projet_scanne(tmp_path)
    chemin = project_dir / "project.json"
    plan = encode_module.plan_encode(project_dir, manifest, lot_id=lot)
    result = encode_module.execute_plan(
        plan, swept=encode_module.prepare_output_directory(plan)
    )

    saboter(chemin)
    with pytest.raises(classe) as excinfo:
        encode_manifest.persist_encode(
            project_dir, encode_manifest.EncodeRecord.from_command_result(result)
        )

    assert extrait in str(excinfo.value)
    # Le fait qui porte la mesure: deux des trois classes ne sont **pas** des
    # `EncodePersistenceError`, donc une capture resserree sur elle les
    # laisserait passer.
    assert isinstance(excinfo.value, ExtractionPersistenceError)
    assert issubclass(classe, ExtractionPersistenceError)


@pytest.mark.parametrize("saboter, classe, extrait", _SABOTAGES_DE_LA_FENETRE)
def test_integration_un_refus_reel_de_la_fenetre_est_capture_et_rend_un(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, saboter, classe, extrait: str
) -> None:
    """Le meme refus, **par la commande**, sans aucune exception injectee.

    Le sabotage a lieu au retour d'`execute_plan`, c'est-a-dire exactement dans
    la fenetre que la limite de concurrence declare: un autre ecrivain a touche
    le `project.json` pendant que la video s'encodait. Si la capture de
    `cli.encode_command` etait resserree sur `EncodePersistenceError`, deux de
    ces trois cas remonteraient jusqu'a `main()` et ce test leverait au lieu de
    rendre `1`.
    """
    project_dir, _manifest, lot = _projet_scanne(tmp_path)
    chemin = project_dir / "project.json"
    vraie = encode_module.execute_plan

    def encode_puis_sabotage(*args, **kwargs):
        resultat = vraie(*args, **kwargs)
        saboter(chemin)
        return resultat

    monkeypatch.setattr(encode_module, "execute_plan", encode_puis_sabotage)
    code = cli.main(["encode", "--project", str(project_dir), "--lot", lot, "--yes"])

    assert code == 1
    capture = capsys.readouterr()
    assert extrait in capture.err
    assert "conserve pour diagnostic" in capture.err
    assert "--overwrite" in capture.err
    # Le master reste sur le disque: c'est ce qui rend la reprise couteuse, et
    # c'est le prix que la limite de concurrence fait payer.
    assert list((project_dir / project_layout.OUTPUTS_DIRNAME).glob("*.mov"))
    assert extrait in _journal(project_dir)


def test_integration_le_message_de_refus_ne_colle_pas_deux_conseils_contraires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Le conseil herite de la story 3.4 ne doit plus preceder le bon sans
    separateur.

    Mesure de revue sur la fenetre reelle: « [...] Restaurer une copie saine du
    project.json, ou repartir d'un dossier projet vierge Le master est ecrit
    [...] ». Deux phrases collees, et « repartir d'un dossier projet vierge »
    -- qui jetterait le projet -- precedait immediatement la reprise correcte.
    """
    project_dir, _manifest, lot = _projet_scanne(tmp_path)
    chemin = project_dir / "project.json"
    vraie = encode_module.execute_plan

    def encode_puis_tronque(*args, **kwargs):
        resultat = vraie(*args, **kwargs)
        chemin.write_text('{"schema_version": "2.1", "lo', encoding="utf-8")
        return resultat

    monkeypatch.setattr(encode_module, "execute_plan", encode_puis_tronque)
    assert cli.main(
        ["encode", "--project", str(project_dir), "--lot", lot, "--yes"]
    ) == 1

    erreur = capsys.readouterr().err
    assert "vierge Le master" not in erreur
    assert "repartir d'un dossier projet vierge." in erreur
    # La reprise est annoncee comme primant sur le conseil generique qui la
    # precede, et elle vient apres lui.
    assert "elle prime sur tout conseil generique" in erreur
    assert erreur.index("dossier projet vierge") < erreur.index("Reprise")


def test_integration_une_interruption_pendant_la_persistance_rend_130(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """**Le seul point du chemin `encode` qui rendait une trace Python nue.**

    La commande annonce elle-meme un contrat `130` « avec le dossier ou
    chercher »; la fenetre d'ecriture du manifest, elle, n'avait aucun garde-fou
    et le code de sortie ne tombait juste que par le defaut de Python. Ce qui
    est laisse derriere est ce que le message doit dire: `project.json` intact et
    sans temporaire, master ecrit et **non declare**.
    """
    project_dir, _manifest, lot = _projet_scanne(tmp_path)
    avant = (project_dir / "project.json").read_bytes()

    def interrompt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(encode_manifest, "persist_encode", interrompt)
    code = cli.main(["encode", "--project", str(project_dir), "--lot", lot, "--yes"])

    assert code == 130
    sortie = capsys.readouterr().out
    assert encode_module.ENCODE_KEYBOARD_INTERRUPT in sortie
    assert "n'est **pas** declare" in sortie
    assert "--overwrite" in sortie
    assert (project_dir / "project.json").read_bytes() == avant
    assert [
        p.name for p in project_dir.iterdir() if p.name.startswith(".project.json")
    ] == []
    assert list((project_dir / project_layout.OUTPUTS_DIRNAME).glob("*.mov"))


# ---------------------------------------------------------------------------
# AC 9 -- qui refuse un v2.0, et avant quoi
# ---------------------------------------------------------------------------


def _en_v2_0_authentique(chemin: Path) -> None:
    """Retrograder un `project.json` v2.1 en un v2.0 **valide contre son schema**.

    Le schema v2.0 est gele et refuse la moitie des champs que la chaine de scan
    ecrit aujourd'hui: un document v2.1 simplement re-etiquete `"2.0"` n'est donc
    **pas** un v2.0, et c'est toute la difference que ce test mesure.
    """
    champs_de_lot = {
        "lot_id",
        "rush_id",
        "state",
        "expected_frame_count",
        "frames_dir",
    }
    document = json.loads(chemin.read_text(encoding="utf-8"))
    document["schema_version"] = "2.0"
    for lot in document["lots"]:
        for cle in [cle for cle in lot if cle not in champs_de_lot]:
            lot.pop(cle)
    document["rushes"] = [
        {"rush_id": rush["rush_id"], "source_name": rush.get("source_name", "x.mov")}
        for rush in document.get("rushes", [])
    ]
    document["video"] = {}
    document["artifacts"] = {"frames_dir": project_layout.FRAMES_DIRNAME}
    document["reconstruction"] = {}
    chemin.write_text(json.dumps(document, indent=2), encoding="utf-8")


def test_integration_un_v2_0_authentique_traverse_la_validation_et_est_refuse_par_le_plan(
    tmp_path: Path, capsys
) -> None:
    """**L'attribution du refus, corrigee: ce n'est pas `validate_manifest`.**

    Trois documents sur quatre sont bien refuses par le `validate_manifest` de
    tete. Le quatrieme -- un v2.0 **authentique** -- le traverse sans un mot,
    parce que le schema v2.0 le declare valide, ce qui est precisement son role.
    C'est `plan_encode` qui le refuse, faute d'`output_frames_dir` sur le lot: un
    champ que le schema v2.0 ne connait pas.

    Le contrat annonce -- rien d'encode -- tient dans les deux cas; c'est le
    **qui refuse** qui etait faux, dans trois documents a la fois. Le test
    parametre voisin, lui, mesure un v2.1 **re-etiquete** `"2.0"`, qui n'est pas
    le meme objet.
    """
    from test_encode_command import LOT, scanned_project

    project_dir, _ = scanned_project(tmp_path)
    chemin = project_dir / "project.json"
    _en_v2_0_authentique(chemin)

    # Le document est un v2.0 **valide**: la validation de tete l'accepte.
    document = validate_manifest(chemin)
    assert document["schema_version"] == "2.0"

    code = cli.main(["encode", "--project", str(project_dir), "--lot", LOT, "--yes"])
    capture = capsys.readouterr()

    assert code == 1
    # Le refus est nomme par le plan, et il nomme la vraie cause.
    assert extraction_manifest.VERIFY_FRAMES_DIR_NOT_DECLARED in capture.err
    assert "output_frames_dir" in capture.err
    # Rien n'a ete encode: le contrat de l'AC 9 tient, quel que soit le refuseur.
    outputs = project_dir / project_layout.OUTPUTS_DIRNAME
    assert not outputs.exists() or not list(outputs.glob("*.mov"))
    assert "Recapitulatif de l'encodage" not in capture.out


def test_l_attribution_du_refus_d_un_v2_0_est_ecrite_la_ou_elle_etait_fausse() -> None:
    """Trois documents affirmaient que `validate_manifest` refuse un v2.0.

    Un enonce faux dans une docstring et dans une note d'architecture ne coute
    rien tant que personne ne le lit; il coute cher a la story suivante, qui le
    reprend pour argent comptant -- c'est la lecon inscrite en tete de 6.5, et
    elle vient de se verifier sur 6.5 elle-meme. Les deux enonces qui vivent dans
    le code sont donc **testes**, pas seulement corriges.
    """
    for source in (
        encode_manifest.__doc__ or "",
        cli.encode_command.__doc__ or "",
    ):
        assert "authentique" in source
        assert "plan_encode" in source
        assert "re-etiquete" in source

    note = Path(
        REPO_ROOT
        / "docs/guide-developpeur/ARCHITECTURE_DETAILED.md"
    ).read_text(encoding="utf-8")
    assert "Le controle de version a lieu avant l'encodage" not in note


# ---------------------------------------------------------------------------
# AC 14 -- la limite de concurrence est declaree, pas corrigee
# ---------------------------------------------------------------------------


def test_la_limite_de_concurrence_est_declaree_en_tete_de_module() -> None:
    doc = encode_manifest.__doc__ or ""
    assert "aucun verrou" in doc
    assert "une seule commande ecrivant le manifest a la fois par projet" in doc
    assert "cinquieme" in doc


def test_le_prix_de_la_reprise_apres_perte_de_declaration_est_ecrit() -> None:
    """Ce que la revue a mesure et que personne n'avait ecrit.

    La limite de concurrence est deliberement differee -- correctif assigne a une
    story transverse d'apres l'Epic 6 -- mais son **prix** est particulier ici et
    n'apparaissait nulle part: le master etant present, la reprise est refusee et
    la seule issue proposee est `--overwrite`, c'est-a-dire reencoder
    integralement un master deja correct pour reparer une ligne de manifest.
    Aucun chemin de reprise n'est invente: ce serait elargir la story.
    """
    doc = encode_manifest.__doc__ or ""
    assert "MASTER_DEJA_PRESENT" in doc
    assert "--overwrite" in doc
    assert "deja correct" in doc


def test_les_limites_heritees_de_l_ecriture_atomique_sont_declarees() -> None:
    """Deux modes de defaillance mesures par la revue, dont le correctif est dans
    le module de la story 3.4 et non ici: un `project.json` symbolique remplace
    en silence par un fichier ordinaire, et les residus `.project.json.*.tmp`
    jamais balayes -- invisibles a `glob.glob`, qui ignore les noms caches."""
    doc = encode_manifest.__doc__ or ""
    assert "lien symbolique" in doc
    assert ".project.json" in doc


def test_la_regle_du_manifest_qui_declare_le_produit_est_ecrite_en_tete() -> None:
    """Question ouverte 4: rien n'est verifie au MVP, et c'est le regime voulu --
    la premiere personne qui rencontrera le cas doit pouvoir le lire ici."""
    doc = encode_manifest.__doc__ or ""
    assert "ce qui a ete produit" in doc
    assert "pas ce qui est present" in doc
