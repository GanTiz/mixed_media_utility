"""Story 11.4c, **lot V1** -- la transition d'etat jugee AVANT ffmpeg.

`EPIC11-ARB-83`, verbatim et in extenso, parce que c'est ce que ce banc mesure
et rien d'autre :

    « Ce n'est pas de deplacer `_clear_existing_lot` : le commentaire qui la
    precede documente qu'elle a deja ete deplacee vers l'aval en revue du
    2026-08-05, pour une raison de correction opposee et toujours valable. La
    transition d'etat doit etre **jugee en amont**, avant ffmpeg, sans toucher
    a l'ordre de l'effacement. »

    « Aucun condensat ne peut voir ce defaut. La fixture est un `testsrc`, donc
    deterministe : les octets qui reviennent apres la reecriture sont
    exactement ceux qui etaient la avant. Il se mesure par les **inodes** et
    par la survie d'un **temoin** depose dans le dossier de lot. »

Le defaut, mesure au `baseline_commit` de la fiche : l'effacement du lot
precedent et le renommage des TIFF sont a l'**etape 5** de `run_extraction`,
et `persist_extraction` -- seul endroit d'ou `LotStateConflictError` pouvait
etre levee -- est a l'**etape 6**. Un lot deja passe a `pdf` ou au-dela voyait
donc ses frames detruites et remplacees **avant** que la transition d'etat ne
soit jugee, et la phrase « Aucune ecriture n'a eu lieu » que porte le refus
n'etait vraie **que du manifeste**. Le defaut est anterieur a l'Epic 11 : il
mord `mmu extract` hors de toute TUI.

Cinq sections, cinq formes de mesure differentes :

* `V1.1` -- **l'ordre**, mesure sans ffmpeg du tout : on passe a
  `run_extraction` des binaires qui n'existent pas. Un refus d'etat prouve
  alors que la garde precede `ensure_ffmpeg_available` ; un
  `FfmpegNotFoundError` prouverait qu'elle ne le precede pas. C'est la mesure
  qui rougit sur les deux mutants « garde retiree » et « garde posee apres
  ffmpeg », et elle ne coute aucun sous-processus ;
* `V1.2` -- **`_clear_existing_lot` n'est pas deplacee**, mesure sur l'arbre
  syntaxique de `run_extraction` : l'effacement reste apres l'appel a ffmpeg et
  dans le meme `try`. Un mutant qui le remonterait rouvrirait le defaut de la
  revue du 2026-08-05 ;
* `V1.3` -- **aucune ecriture**, mesure aux **inodes**, au **`st_mtime_ns`** et
  par un **temoin**, sur un vrai lot extrait par ffmpeg ;
* `V1.4` -- **une seule redaction** du refus : le message rendu par le chemin
  amont est compare, caractere pour caractere, a celui que la persistance
  produit sur le meme lot dans le meme etat ;
* `V1.5` -- **le contrat de la CLI ne bouge pas** : meme exception, meme entree
  de `CODES_DE_SORTIE`, meme code de sortie, et la garde de la TUI est toujours
  la.

Regle des fabriques de `CLAUDE.md`, point **2 bis** compris : le manifeste des
sections `V1.1` et `V1.4` porte **quatre** lots -- un d'un **autre rush** en
tete, le lot vise en **troisieme** position, un autre derriere lui --, et ni le
premier ni le dernier ne portent d'etat conflictuel. Un `find` fautif qui rend
le premier lot, une boucle qui s'arrete au premier tour, une lecture du dernier
lot : les trois se demasquent ici, et aucune ne se demasquerait sur un
manifeste a un seul lot.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

import importlib.util

import pytest
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import extraction, ffmpeg_utils
from mixed_media_utility.frame_selection import select_source_frames
from mixed_media_utility.io import project_layout
from mixed_media_utility.io.extraction_manifest import (
    MANIFEST_FILENAME,
    ExtractionPersistenceError,
    ExtractionRecord,
    LotStateConflictError,
    build_extraction_manifest,
)
from mixed_media_utility.io.manifest import (
    LOT_STATES,
    validate_lot_state_transition,
)
from mixed_media_utility.io.naming import build_lot_id

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="binaires ffmpeg/ffprobe absents du PATH",
)

#: Le rush du banc. Son nom devient le `rush_id` (`video_path.stem`).
RUSH_ID = "rush_amont"

#: La cadence du lot **vise**. Les trois autres cadences du manifeste ne sont
#: la que pour que la cible ne soit ni la premiere ni la derniere entree.
CADENCE_VISEE = 12.0

#: Les etats aval, dans l'ordre de la machine a etats : les quatre qui doivent
#: refuser une re-extraction. `extraction` en est exclu -- `extraction ->
#: extraction` est accepte, et c'est la condition meme de l'idempotence.
ETATS_AVAL = ("pdf", "scan", "reconstruction", "encode")

#: Des binaires qui n'existent pas. Les passer est ce qui rend la section
#: `V1.1` capable de mesurer un **ordre** : si la garde d'etat ne precedait pas
#: `ensure_ffmpeg_available`, l'exception rendue serait `FfmpegNotFoundError`
#: et non `LotStateConflictError`.
FFMPEG_ABSENT = "mmu-ffmpeg-qui-n-existe-pas"
FFPROBE_ABSENT = "mmu-ffprobe-qui-n-existe-pas"


class JournalMuet:
    """Un logger minimal : `run_extraction` en exige un, on n'en lit rien."""

    def info(self, *args, **kwargs) -> None:
        pass

    warning = error = debug = info


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


def video_factice(dossier: Path, nom: str = f"{RUSH_ID}.mp4") -> Path:
    """Un fichier qui **existe** et n'est pas une video.

    Il suffit aux sections qui ne vont jamais jusqu'au probe : `run_extraction`
    n'exige a l'etape 1 que `video_path.is_file()`. Le prendre factice est
    volontaire -- si la garde d'etat laissait passer, l'echec suivant serait un
    echec de decodage, donc visible, et non un faux vert.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / nom
    chemin.write_bytes(b"ce fichier n'est pas une video, et c'est voulu")
    return chemin


def manifeste_a_quatre_lots(etat_du_lot_vise: str | None,
                            *, etat_des_voisins: str = "extraction") -> dict:
    """Le manifeste de la regle des fabriques : quatre lots, la cible au milieu.

    `CLAUDE.md`, point 2 bis : « Une fabrique a **deux** elements dont la cible
    est en second la place aussi en **dernier**, et les deux formes y sont
    indiscernables. Il faut **trois** elements et la cible **au milieu**. »

    Ici quatre, parce que le premier sert deja a autre chose : c'est un lot d'un
    **autre rush**, qui demasque un `find` compare sur la seule cadence. La
    cible est en **troisieme** position ; les voisins portent un etat qui, lui,
    **n'est pas conflictuel** -- sans quoi une lecture du premier ou du dernier
    lot refuserait elle aussi, et le banc serait vert sur le defaut qu'il nomme.

    `rushes[]` est deliberement absent : une entree homonyme au `source_parent`
    different ferait desambiguiser le `rush_id` (`ARB-9`), donc changer le
    `lot_id`, donc rater la cible pour une raison qui n'est pas celle mesuree.
    """
    def lot(rush_id: str, fps: float, etat: str | None) -> dict:
        entree = {
            "lot_id": build_lot_id(rush_id, fps),
            "rush_id": rush_id,
            "fps_target": fps,
            "frames_dir": (
                f"frames/{project_layout.rush_dir_slug(rush_id, fps)}"),
            "expected_frame_count": 4,
        }
        if etat is not None:
            entree["state"] = etat
        return entree

    return {
        "schema_version": "2.1",
        "project_id": "projet_du_banc",
        "lots": [
            lot("autre_rush", 5.0, etat_des_voisins),
            lot(RUSH_ID, 5.0, etat_des_voisins),
            lot(RUSH_ID, CADENCE_VISEE, etat_du_lot_vise),   # <- la cible
            lot(RUSH_ID, 25.0, etat_des_voisins),
        ],
    }


def projet_a_la_main(base: Path, document: dict | str | None,
                     *, frames_presentes: bool = True) -> tuple[Path, Path]:
    """Un projet ecrit **a la main** : pas d'extraction, donc pas de ffmpeg.

    Rend `(dossier_projet, chemin_du_rush)`. `document` est ecrit tel quel
    quand c'est une chaine (le cas du manifeste illisible), serialise quand
    c'est un dictionnaire, et rien n'est ecrit du tout quand c'est `None`.
    """
    projet = base / "projet_du_banc"
    projet.mkdir(parents=True, exist_ok=True)
    if document is not None:
        texte = (document if isinstance(document, str)
                 else json.dumps(document, indent=2))
        (projet / MANIFEST_FILENAME).write_text(texte, encoding="utf-8")

    if frames_presentes:
        dossier = project_layout.extract_frames_dir(projet, RUSH_ID, CADENCE_VISEE)
        dossier.mkdir(parents=True, exist_ok=True)
        # Deux frames aux contenus **differents** : un remplissage uniforme
        # rendrait invisible toute permutation lors d'une reecriture.
        for rang, timecode in enumerate(("00-00-00-00", "00-00-01-00")):
            (dossier / f"{RUSH_ID}_12_{timecode}.tiff").write_bytes(
                b"frame-livree-" + str(rang).encode("ascii"))

    return projet, video_factice(base / "rushes")


def extraire_a_blanc(projet: Path, rush: Path, *,
                     fps: float = CADENCE_VISEE,
                     overwrite: bool = True):
    """Appeler `run_extraction` avec des binaires absents du `PATH`.

    Tout ce qui arrive **apres** `ensure_ffmpeg_available` est donc
    inatteignable : ce qui remonte de cet appel ne peut venir que de l'etape 1.
    """
    return extraction.run_extraction(
        project_dir=projet,
        video_path=rush,
        fps_target=fps,
        overwrite=overwrite,
        consent_granted=True,
        unknown_color_accepted=True,
        logger=JournalMuet(),
        ffmpeg_binary=FFMPEG_ABSENT,
        ffprobe_binary=FFPROBE_ABSENT,
    )


def record_de_reference(fps_target: float = CADENCE_VISEE) -> ExtractionRecord:
    """Un `ExtractionRecord` minimal, pour faire parler la **persistance**.

    Il n'existe que pour la section `V1.4` : le message du refus amont s'y
    compare a celui que `build_extraction_manifest` produit sur le meme lot
    dans le meme etat. Deux sites d'appel, deux chemins de code, une seule
    chaine attendue.
    """
    selection = select_source_frames(
        fps_source=30, fps_target=fps_target, source_frame_count=100)
    return ExtractionRecord(
        project_id="projet_du_banc",
        rush_id=RUSH_ID,
        rush_source_name=f"{RUSH_ID}.mp4",
        rush_source_path=f"/videos/{RUSH_ID}.mp4",
        lot_id=build_lot_id(RUSH_ID, fps_target),
        frames_dir_relative=(
            f"frames/{project_layout.rush_dir_slug(RUSH_ID, fps_target)}"),
        selection=selection,
        fps_source=30.0,
        fps_target=fps_target,
        source_width=1920,
        source_height=1080,
        source_fields={},
        confirmation_mode="non_interactif",
        unknown_color_accepted=False,
        confirmed_at="2026-08-30T09:30:00Z",
    )


# ===========================================================================
# V1.1 -- l'ORDRE : la garde precede ffmpeg, mesure sans ffmpeg
# ===========================================================================


@pytest.mark.parametrize("etat_aval", ETATS_AVAL)
def test_un_lot_deja_passe_a_l_aval_est_refuse_AVANT_meme_que_ffmpeg_soit_CHERCHE(
        tmp_path, etat_aval):
    """AC 1.1 -- « juger la transition d'etat **avant** ffmpeg ».

    La mesure d'ordre est portee par les binaires absents : `run_extraction`
    appelle `ffmpeg_utils.ensure_ffmpeg_available(ffmpeg_binary)` a son etape 2,
    donc **avant** toute autre chose couteuse. Avec un binaire qui n'existe pas,
    deux issues seulement sont possibles, et elles disent chacune ou est la
    garde :

    * `LotStateConflictError` -- la garde est en amont, ce que l'AC exige ;
    * `FfmpegNotFoundError` -- la garde n'est pas en amont ; c'est ce que
      rendait le code d'avant, et c'est ce que rend tout mutant qui retire la
      garde ou la repose apres l'appel a ffmpeg.

    Les quatre etats aval sont mesures, pas seulement `pdf` : la fiche parle de
    « `pdf` ou au-dela », et un mutant qui ne refuserait que `pdf` passerait un
    banc mono-etat.
    """
    projet, rush = projet_a_la_main(
        tmp_path, manifeste_a_quatre_lots(etat_aval))

    with pytest.raises(LotStateConflictError) as refus:
        extraire_a_blanc(projet, rush)

    assert etat_aval in str(refus.value)
    assert not isinstance(refus.value, ffmpeg_utils.FfmpegNotFoundError)


def test_le_binaire_absent_rend_bien_FfmpegNotFoundError_quand_l_etat_n_est_PAS_conflictuel(
        tmp_path):
    """Volet **symetrique** de la mesure d'ordre, et il est indispensable.

    Sans lui, le test precedent serait vert meme si `run_extraction` refusait
    tout et n'importe quoi : c'est celui-ci qui prouve que le chemin va bien
    jusqu'a `ensure_ffmpeg_available` quand rien ne s'y oppose, donc que
    l'exception attendue au-dessus mesure une **priorite** et non un refus
    universel.
    """
    projet, rush = projet_a_la_main(
        tmp_path, manifeste_a_quatre_lots("extraction"))

    with pytest.raises(ffmpeg_utils.FfmpegNotFoundError):
        extraire_a_blanc(projet, rush)


def test_l_etat_lu_est_celui_du_lot_VISE_et_pas_celui_d_un_VOISIN(tmp_path):
    """Regle des fabriques : la cible est **au milieu**, les voisins innocents.

    Le manifeste porte quatre lots dont le vise est le **troisieme**. Un
    `find` qui rendrait le premier lot -- mutant `M25` de la story 5.7, dont la
    consequence reelle etait d'ecrire les cardinaux sur le mauvais lot --, une
    boucle qui s'arreterait au premier tour, ou une lecture du dernier lot ne
    verraient ici **aucun** etat conflictuel et laisseraient passer.
    """
    document = manifeste_a_quatre_lots("encode")
    vise = build_lot_id(RUSH_ID, CADENCE_VISEE)
    rangs = [rang for rang, lot in enumerate(document["lots"])
             if lot["lot_id"] == vise]
    assert rangs == [2], (
        "le lot vise doit etre ni le premier ni le dernier des quatre "
        f"(trouve {rangs})")
    assert {lot["state"] for rang, lot in enumerate(document["lots"])
            if rang != 2} == {"extraction"}, (
        "les voisins ne doivent porter AUCUN etat conflictuel, sans quoi une "
        "lecture du mauvais lot refuserait elle aussi")

    projet, rush = projet_a_la_main(tmp_path, document)
    with pytest.raises(LotStateConflictError):
        extraire_a_blanc(projet, rush)


def test_un_etat_conflictuel_sur_un_AUTRE_lot_ne_refuse_PAS_le_lot_vise(tmp_path):
    """Le pendant du precedent : c'est l'etat de la **cible** qui decide.

    Ici les trois voisins sont a `encode` et la cible a `extraction`. Une
    implementation qui balaierait `lots[]` a la recherche d'un etat aval
    quelconque refuserait ; le contrat est qu'elle ne doit pas.
    """
    projet, rush = projet_a_la_main(
        tmp_path,
        manifeste_a_quatre_lots("extraction", etat_des_voisins="encode"))

    with pytest.raises(ffmpeg_utils.FfmpegNotFoundError):
        extraire_a_blanc(projet, rush)


@pytest.mark.parametrize("document, motif", [
    (None, "manifeste absent"),
    ("{ ceci n'est pas du JSON", "manifeste illisible"),
    ({"schema_version": "2.1", "lots": []}, "aucun lot declare"),
    ({"schema_version": "2.1"}, "aucune cle lots"),
    ({"schema_version": "2.1", "lots": "pas une liste"}, "lots non listee"),
])
def test_un_manifeste_qui_ne_declare_AUCUN_etat_ne_refuse_rien(
        tmp_path, document, motif):
    """`None` est un cas **accepte**, pas un conflit.

    `validate_lot_state_transition` documente que `current_state is None` passe
    -- et il le faut : un lot preexistant peut ne pas porter `state`, et le
    premier lot d'un projet n'a pas de manifeste du tout. Un manifeste illisible
    n'est pas davantage un conflit d'etat : la persistance de l'etape 6 a ses
    propres refus pour ce cas, et les doubler ici changerait le message rendu a
    l'operateur pour une panne qui n'est pas celle que cette story corrige.
    """
    projet, rush = projet_a_la_main(tmp_path, document)

    with pytest.raises(ffmpeg_utils.FfmpegNotFoundError):
        extraire_a_blanc(projet, rush), motif


def test_un_lot_sans_cle_state_ne_refuse_rien(tmp_path):
    """Meme regle, sur le porteur reel : le lot existe, il ne porte pas `state`."""
    projet, rush = projet_a_la_main(tmp_path, manifeste_a_quatre_lots(None))

    with pytest.raises(ffmpeg_utils.FfmpegNotFoundError):
        extraire_a_blanc(projet, rush)


@pytest.mark.parametrize("etat_corrompu", ["publie", "PDF", 3, ["pdf"]])
def test_un_etat_CORROMPU_est_refuse_en_amont_COMME_il_le_serait_a_la_persistance(
        tmp_path, etat_corrompu):
    """L'amont et l'aval doivent avoir **le meme avis** sur le meme manifeste.

    `validate_lot_state_transition` refuse un `current_state` qu'elle ne
    connait pas (« Etat de lot courant inconnu »), et la persistance lui passe
    `existing_lot.get("state")` **sans filtre**. Filtrer ici -- ne remonter
    qu'une chaine, traiter le reste comme une absence d'etat -- donnerait a
    l'amont un avis plus permissif que celui de l'aval : l'extraction irait
    jusqu'au bout, puis echouerait a l'etape 6. C'est exactement la forme du
    defaut que cette story corrige.

    Les quatre cas couvrent les deux familles : une chaine hors vocabulaire
    (dont `PDF`, la casse comptant) et un type qui n'est pas une chaine.
    """
    document = manifeste_a_quatre_lots(None)
    document["lots"][2]["state"] = etat_corrompu

    projet, rush = projet_a_la_main(tmp_path, document)
    with pytest.raises(LotStateConflictError) as refus:
        extraire_a_blanc(projet, rush)
    assert "Etat de lot courant inconnu" in str(refus.value)


def test_une_AUTRE_cadence_du_meme_rush_reste_extractible(tmp_path):
    """Le refus porte sur un **lot**, jamais sur un rush.

    C'est litteralement la premiere issue que le message enumere (« extraire
    vers une autre cadence cible, donc un autre lot_id ») : si elle ne marchait
    pas, le refus serait un cul-de-sac.
    """
    projet, rush = projet_a_la_main(
        tmp_path, manifeste_a_quatre_lots("pdf"), frames_presentes=False)

    with pytest.raises(ffmpeg_utils.FfmpegNotFoundError):
        extraire_a_blanc(projet, rush, fps=48.0)


def test_le_refus_arrive_meme_quand_le_dossier_de_lot_est_VIDE(tmp_path):
    """Le regime que la garde de la TUI ne couvre pas, et qui perdait du temps.

    Frames effacees a la main, manifeste toujours a `pdf` : avant cette story,
    `mmu extract` extrayait le lot en entier -- donc payait ffmpeg -- puis
    refusait a la persistance, en laissant les fichiers sur le disque. Le refus
    arrive desormais avant, et **sans `--overwrite`** : le dossier etant vide,
    la garde de l'AC 9 (« un lot deja present n'est jamais efface
    implicitement ») ne mord pas.
    """
    projet, rush = projet_a_la_main(
        tmp_path, manifeste_a_quatre_lots("scan"), frames_presentes=False)

    with pytest.raises(LotStateConflictError):
        extraire_a_blanc(projet, rush, overwrite=False)


def test_le_lot_deja_present_SANS_overwrite_garde_son_refus_d_avant(tmp_path):
    """Ce qui **ne** change **pas** : l'ordre des deux refus d'entree.

    Un lot present sur disque sans `--overwrite` est refuse par
    `ExtractionInputError` (AC 9 de la story 3.1), et ce refus reste **avant**
    la garde d'etat. Le message, le type et le code de sortie sont donc ceux
    d'aujourd'hui pour ce cas, y compris sur un lot passe a `pdf`.
    """
    projet, rush = projet_a_la_main(tmp_path, manifeste_a_quatre_lots("pdf"))

    with pytest.raises(extraction.ExtractionInputError) as refus:
        extraire_a_blanc(projet, rush, overwrite=False)

    assert "ne sera pas efface implicitement" in str(refus.value)


# ===========================================================================
# V1.2 -- `_clear_existing_lot` n'est PAS deplacee
# ===========================================================================


def _corps_de_run_extraction() -> ast.FunctionDef:
    source = Path(extraction.__file__).read_text(encoding="utf-8")
    arbre = ast.parse(source, filename=extraction.__file__)
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.FunctionDef)
                and noeud.name == "run_extraction"):
            return noeud
    raise AssertionError("`run_extraction` introuvable dans extraction.py")


def _lignes_des_appels(fonction: ast.FunctionDef) -> dict[str, list[int]]:
    """Nom appele -> lignes de ses appels, dans `fonction`.

    Le nom retenu est le dernier segment (`a.b.c(...)` -> `c`) : c'est celui
    que l'AC nomme, et il ne change pas si un module est reimporte autrement.
    """
    lignes: dict[str, list[int]] = {}
    for noeud in ast.walk(fonction):
        if not isinstance(noeud, ast.Call):
            continue
        cible = noeud.func
        nom = (cible.attr if isinstance(cible, ast.Attribute)
               else cible.id if isinstance(cible, ast.Name) else None)
        if nom is not None:
            lignes.setdefault(nom, []).append(noeud.lineno)
    return lignes


def test_le_site_d_appel_de__clear_existing_lot_est_INCHANGE(tmp_path):
    """AC 1.2 -- l'effacement reste **apres** ffmpeg, et le grep le dit.

    `EPIC11-ARB-83`, verbatim : « Ce n'est pas de deplacer
    `_clear_existing_lot` [...] La transition d'etat doit etre **jugee en
    amont**, avant ffmpeg, sans toucher a l'ordre de l'effacement. »

    La mesure est un ordre de lignes dans `run_extraction`, et elle rougit sur
    **trois** mutants a la fois : la garde retiree (le nom disparait), la garde
    posee apres ffmpeg, et l'effacement remonte en amont -- ce dernier
    rouvrirait le defaut que la revue du 2026-08-05 avait ferme (« un echec
    d'extraction laissait alors un dossier vide et un manifest qui continuait
    de declarer le lot complet »).
    """
    appels = _lignes_des_appels(_corps_de_run_extraction())
    attendus = ("validate_extraction_state_transition",
                "ensure_ffmpeg_available",
                "extract_selected_frames",
                "_clear_existing_lot",
                "persist_extraction")
    manquants = [nom for nom in attendus if nom not in appels]
    assert manquants == [], (
        f"`run_extraction` n'appelle plus {manquants} : l'ordre mesure ici "
        "n'existe plus")

    ligne = {nom: min(appels[nom]) for nom in attendus}
    assert ligne["validate_extraction_state_transition"] < ligne["ensure_ffmpeg_available"], (
        "la transition d'etat doit etre jugee AVANT ffmpeg (AC 1.1)")
    assert ligne["extract_selected_frames"] < ligne["_clear_existing_lot"], (
        "`_clear_existing_lot` a ete remontee avant l'appel a ffmpeg : c'est "
        "exactement ce que la revue du 2026-08-05 a corrige, et ce que "
        "`EPIC11-ARB-83` interdit de defaire")
    assert ligne["_clear_existing_lot"] < ligne["persist_extraction"], (
        "l'effacement doit rester a l'etape 5, avant la persistance")


def test__clear_existing_lot_reste_dans_le_MEME_try_que_l_appel_a_ffmpeg():
    """Le meme invariant, sur la structure et non sur les numeros de ligne.

    Un ordre de lignes ne dit rien du bloc : remonter l'effacement hors du
    `try` -- donc hors de la protection du `finally` qui nettoie le dossier
    temporaire -- garderait l'ordre et changerait le comportement en cas
    d'echec. Les deux mesures se completent.
    """
    fonction = _corps_de_run_extraction()
    blocs = [noeud for noeud in ast.walk(fonction) if isinstance(noeud, ast.Try)]
    portant_les_deux = [
        bloc for bloc in blocs
        if {"extract_selected_frames", "_clear_existing_lot"}
        <= set(_lignes_des_appels(bloc))  # type: ignore[arg-type]
    ]
    assert len(portant_les_deux) == 1, (
        "l'appel a ffmpeg et l'effacement du lot precedent doivent vivre dans "
        f"le MEME bloc `try` (trouve {len(portant_les_deux)})")


def test_la_justification_de_la_revue_du_2026_08_05_est_TOUJOURS_sur_place():
    """Le commentaire est ce qui empeche le prochain agent de refaire le geste.

    Le retirer ne changerait aucun comportement mesurable, et c'est bien le
    probleme : la raison pour laquelle l'effacement est en aval ne survivrait
    plus qu'a la memoire d'une session.
    """
    source = Path(extraction.__file__).read_text(encoding="utf-8")
    # Marques de commentaire et retours a la ligne aplatis : la phrase est
    # coupee sur quatre lignes, et un simple `in` la manquerait au premier
    # re-enveloppement -- ce qui ferait rougir le banc pour une raison qui
    # n'est pas celle qu'il mesure.
    aplati = " ".join(source.replace("#", " ").split())
    assert "detruisait un lot valide sur la seule intention de le remplacer" in aplati
    assert "revue du 2026-08-05" in aplati


# ===========================================================================
# V1.3 -- aucune ecriture : inodes, `st_mtime_ns`, temoin
# ===========================================================================


def rush_reel(chemin: Path) -> Path:
    """Fabriquer le rush avec ffmpeg lui-meme, comme les bancs d'`extract`.

    Aucun mp4 n'entre dans `tests/fixtures/`, et le rush est reproductible
    d'une session a l'autre. `testsrc` change a chaque frame : une permutation
    d'images se verrait dans les octets -- ce qui, precisement, ne suffit pas
    ici (voir le docstring du test).
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    resultat = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", "testsrc=size=64x36:rate=30:duration=2",
         "-pix_fmt", "yuv420p", str(chemin)],
        capture_output=True, text=True)
    assert resultat.returncode == 0, resultat.stderr
    return chemin


def _empreinte_du_dossier(dossier: Path) -> dict[str, tuple[int, int, int]]:
    """Nom -> (inode, `st_mtime_ns`, taille), pour **tout** le dossier de lot.

    Les trois ensemble, et pas le contenu : `EPIC11-ARB-83`, verbatim, « La
    fixture est un `testsrc`, donc deterministe : les octets qui reviennent
    apres la reecriture sont exactement ceux qui etaient la avant. » Un
    condensat ne peut donc pas distinguer « rien n'a ete touche » de « tout a
    ete refait a l'identique ». L'inode, lui, ne survit pas a un `unlink` suivi
    d'un `replace`, et la mtime en nanosecondes ne survit pas a une reecriture.
    """
    return {chemin.name: (chemin.stat().st_ino,
                          chemin.stat().st_mtime_ns,
                          chemin.stat().st_size)
            for chemin in sorted(dossier.iterdir()) if chemin.is_file()}


@requires_ffmpeg
def test_le_refus_d_etat_ne_TOUCHE_NI_inode_NI_mtime_NI_temoin(tmp_path):
    """AC 1.4 et 1.5 -- « Le refus arrive sans qu'aucune ecriture ait eu lieu ».

    Le scenario est celui qui perdait des donnees, joue sur le **vrai** coeur et
    sur de **vrais** TIFF : un lot est extrait, il passe a `pdf` (ses frames sont
    desormais referencees par une planche imprimee), et l'operateur relance
    `extract --overwrite`. Avant cette story, l'etape 5 effacait le lot puis le
    reecrivait, et l'etape 6 refusait en affirmant « Aucune ecriture n'a eu
    lieu ».

    **Ce que le condensat ne mesure pas**, et c'est le piege qui a fait echouer
    la premiere mesure : le lot efface puis reecrit rend exactement les memes
    octets, `testsrc` etant deterministe. Ce banc mesure donc ce qu'une
    reecriture change **quoi qu'elle rende** :

    * l'**inode** de chaque TIFF, detruit par le `unlink` de
      `_clear_existing_lot` puis le `replace` du renommage ;
    * le **`st_mtime_ns`** de chaque TIFF ;
    * la survie d'un **temoin** de nom non conforme, que `_clear_existing_lot`
      emporterait avec le reste ;
    * et, en negatif, l'absence du dossier temporaire d'extraction, que
      l'etape 5 cree avant meme d'appeler ffmpeg.
    """
    rush = rush_reel(tmp_path / "rushes" / f"{RUSH_ID}.mp4")
    projet = tmp_path / "projet_du_banc"

    issue = extraction.run_extraction(
        project_dir=projet, video_path=rush, fps_target=CADENCE_VISEE,
        consent_granted=True, unknown_color_accepted=True,
        logger=JournalMuet())
    assert issue.granted and issue.written_frame_count > 1

    dossier = issue.frames_dir
    temoin = dossier / "temoin-de-non-ecriture.txt"
    temoin.write_text("rien ne doit toucher ce dossier", encoding="utf-8")
    avant = _empreinte_du_dossier(dossier)
    assert len(avant) == issue.written_frame_count + 1

    document = json.loads(
        (projet / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    rangs = [rang for rang, lot in enumerate(document["lots"])
             if lot["lot_id"] == issue.lot_id]
    assert rangs == [0], rangs
    document["lots"][0]["state"] = "pdf"
    (projet / MANIFEST_FILENAME).write_text(json.dumps(document, indent=2),
                                            encoding="utf-8")

    with pytest.raises(LotStateConflictError):
        extraction.run_extraction(
            project_dir=projet, video_path=rush, fps_target=CADENCE_VISEE,
            overwrite=True, consent_granted=True, unknown_color_accepted=True,
            logger=JournalMuet())

    apres = _empreinte_du_dossier(dossier)
    assert temoin.is_file(), (
        "le dossier du lot passe a `pdf` a ete vide : le refus est arrive "
        "APRES une ecriture, ce que l'AC 1.4 interdit")
    assert apres == avant, (
        "inodes ou mtimes modifies : les frames ont ete effacees puis "
        "reecrites. Le contenu revient identique -- la fixture est "
        "deterministe -- mais l'ecriture a bien eu lieu")
    assert not (dossier / ffmpeg_utils.EXTRACT_TEMP_DIRNAME).exists(), (
        "le dossier temporaire d'extraction a ete cree : l'etape 5 a demarre")


@requires_ffmpeg
def test_le_manifeste_lui_meme_n_est_pas_TOUCHE_par_le_refus(tmp_path):
    """Le pendant de la mesure precedente sur l'autre artefact.

    La phrase « Aucune ecriture n'a eu lieu » etait deja vraie du manifeste
    avant cette story ; elle doit le rester. Mesure au meme etalon -- inode,
    `st_mtime_ns`, octets -- et non par une simple relecture.
    """
    rush = rush_reel(tmp_path / "rushes" / f"{RUSH_ID}.mp4")
    projet = tmp_path / "projet_du_banc"
    extraction.run_extraction(
        project_dir=projet, video_path=rush, fps_target=CADENCE_VISEE,
        consent_granted=True, unknown_color_accepted=True,
        logger=JournalMuet())

    chemin = projet / MANIFEST_FILENAME
    document = json.loads(chemin.read_text(encoding="utf-8"))
    document["lots"][0]["state"] = "encode"
    chemin.write_text(json.dumps(document, indent=2), encoding="utf-8")
    avant = (chemin.stat().st_ino, chemin.stat().st_mtime_ns,
             chemin.read_bytes())

    with pytest.raises(LotStateConflictError):
        extraction.run_extraction(
            project_dir=projet, video_path=rush, fps_target=CADENCE_VISEE,
            overwrite=True, consent_granted=True, unknown_color_accepted=True,
            logger=JournalMuet())

    assert (chemin.stat().st_ino, chemin.stat().st_mtime_ns,
            chemin.read_bytes()) == avant
    assert not list(projet.glob(f".{MANIFEST_FILENAME}.*")), (
        "un fichier temporaire de reecriture atomique traine")


# ===========================================================================
# V1.4 -- une seule redaction du refus
# ===========================================================================


def test_le_message_du_refus_EN_AMONT_est_EXACTEMENT_celui_de_la_persistance(
        tmp_path):
    """AC 1.3 -- « la **meme** exception, avec le **meme message de base** ».

    Les deux chaines viennent de deux chemins de code differents : celle de
    gauche de `run_extraction` (etape 1, sans ffmpeg), celle de droite de
    `build_extraction_manifest` (le corps de l'etape 6). L'egalite mesure qu'il
    n'y a **qu'une** redaction -- `EPIC5-ARB-78`, « deux emplacements pour le
    meme fait, ce sont deux verites ».

    Elle mesure aussi, au passage, que le refus **nomme l'etat atteint** : un
    mutant qui retirerait `{current_state!r}` du message ferait diverger les
    deux cotes seulement si l'un des deux etait recopie -- d'ou les assertions
    de contenu qui suivent, qui mordent meme quand la redaction est unique.
    """
    projet, rush = projet_a_la_main(tmp_path, manifeste_a_quatre_lots("scan"))

    with pytest.raises(LotStateConflictError) as amont:
        extraire_a_blanc(projet, rush)

    record = record_de_reference()
    existant = build_extraction_manifest(None, record)
    existant["lots"][0]["state"] = "scan"
    with pytest.raises(LotStateConflictError) as persistance:
        build_extraction_manifest(existant, record)

    assert str(amont.value) == str(persistance.value)


@pytest.mark.parametrize("etat_aval", ETATS_AVAL)
def test_le_refus_NOMME_le_lot_l_etat_atteint_et_les_issues(tmp_path, etat_aval):
    """AC 2 -- le refus nomme, il ne se contente pas de dire « invalide ».

    Quatre exigences, mesurees une par une parce qu'un mutant peut n'en casser
    qu'une : le `lot_id` vise, l'**etat atteint**, l'etat demande, et **les deux
    issues, mot pour mot** (AC 2.1 : elles sont conservees telles quelles, et
    c'est V3 qui en ajoutera une troisieme). La derniere phrase, « Aucune
    ecriture n'a eu lieu », est ici adossee a la mesure de l'AC 1.4 plutot qu'a
    sa seule presence dans la chaine.

    **Le piege mesure, et il a fait survivre un mutant** : le message recopie
    entre parentheses le motif que rend la machine a etats, lequel nomme deja
    l'etat courant (« Transition d'etat de lot invalide: 'pdf' -> ... »). Un
    `assert etat in message` est donc vert **meme si le refus lui-meme cesse de
    nommer l'etat**. La mesure porte donc sur le message **prive de ce motif** :
    ce qui reste est la redaction propre du refus, et c'est elle qui doit nommer
    l'etat atteint.
    """
    projet, rush = projet_a_la_main(
        tmp_path, manifeste_a_quatre_lots(etat_aval))

    with pytest.raises(LotStateConflictError) as refus:
        extraire_a_blanc(projet, rush)

    message = str(refus.value)
    assert build_lot_id(RUSH_ID, CADENCE_VISEE) in message
    assert "extraction" in message
    assert "Aucune ecriture n'a eu lieu" in message
    assert ", ".join(LOT_STATES) in message

    # Les deux issues, mot pour mot (AC 2.1).
    assert "extraire vers une autre cadence cible" in message
    assert "nettoyer ce lot a la main" in message

    # **Deux** citations sont retirees du message avant la mesure, et il faut
    # les deux : le motif rendu par la machine a etats (qui nomme deja l'etat
    # courant) **et** la liste des etats connus (qui les nomme tous). Sans la
    # seconde, un refus qui cesserait de nommer l'etat atteint resterait vert
    # -- c'est litteralement le mutant qui a survecu a la premiere campagne.
    # Les deux citations sont obtenues de leur source, jamais recopiees ici :
    # une chaine ecrite en dur casserait des deux cotes de la soustraction et
    # ne mesurerait rien.
    with pytest.raises(ValidationError) as machine:
        validate_lot_state_transition(etat_aval, "extraction")
    assert machine.value.message in message, (
        "le refus doit citer le motif rendu par la machine a etats")
    propre = message.replace(machine.value.message, "").replace(
        ", ".join(LOT_STATES), "")
    assert etat_aval in propre, (
        "le refus doit nommer l'ETAT ATTEINT DE LUI-MEME, pas seulement en "
        "citant le motif de la machine a etats -- sans quoi il se contente de "
        "dire que la transition est invalide (`EPIC11-ARB-25`)")


def test_la_phrase_du_refus_n_a_qu_UN_SEUL_site_de_redaction_dans_src():
    """AC 2.4, forme frontiere : « une seule redaction ».

    Un grep de la phrase distinctive du message sur tout `src/` doit rendre
    **exactement un** fichier. Le jour ou le lot V3 y ajoutera la troisieme
    issue -- la nouvelle version --, il n'aura donc qu'un endroit a toucher.
    """
    racine = Path(extraction.__file__).resolve().parent
    porteurs = sorted(
        chemin.relative_to(racine).as_posix()
        for chemin in racine.rglob("*.py")
        if "invaliderait les artefacts aval deja produits"
        in chemin.read_text(encoding="utf-8"))
    assert porteurs == ["io/extraction_manifest.py"], porteurs


def test_une_seule_fonction_du_chemin_extraction_appelle_la_machine_a_etats():
    """AC 1.1 -- « aucune machine a etats n'est reecrite ».

    Mesure sur l'arbre syntaxique des **deux** modules du lot : une seule
    fonction y appelle `validate_lot_state_transition`, et c'est celle qui
    porte le message. Un mutant qui reimplementerait la comparaison d'index
    dans `extraction.py` -- ou qui y recopierait l'appel avec sa propre
    redaction -- ferait rougir ce test.
    """
    from mixed_media_utility.io import extraction_manifest

    appelantes: list[str] = []
    for module in (extraction, extraction_manifest):
        chemin = Path(module.__file__)
        arbre = ast.parse(chemin.read_text(encoding="utf-8"),
                          filename=str(chemin))
        for fonction in [n for n in ast.walk(arbre)
                         if isinstance(n, ast.FunctionDef)]:
            for noeud in ast.walk(fonction):
                if (isinstance(noeud, ast.Call)
                        and isinstance(noeud.func, ast.Name)
                        and noeud.func.id == "validate_lot_state_transition"):
                    appelantes.append(f"{chemin.name}::{fonction.name}")

    assert appelantes == [
        "extraction_manifest.py::validate_extraction_state_transition"], appelantes


# ===========================================================================
# V1.5 -- le contrat de sortie et la garde de la TUI
# ===========================================================================


def test_le_code_de_sortie_du_refus_est_INCHANGE(tmp_path):
    """AC 1.3 -- la table `CODES_DE_SORTIE` repond sans avoir ete touchee.

    `LotStateConflictError` n'a pas d'entree a elle : elle est attrapee par
    `ExtractionPersistenceError`, et le code reste `1`. Le refus arrive plus
    tot, il ne rend pas autre chose -- c'est ce qui permet a `mmu extract` et a
    la TUI de continuer de repondre sans etre modifies.
    """
    projet, rush = projet_a_la_main(tmp_path, manifeste_a_quatre_lots("pdf"))

    with pytest.raises(LotStateConflictError) as refus:
        extraire_a_blanc(projet, rush)

    classe, code = extraction.correspondance_de_sortie(refus.value)
    assert classe is ExtractionPersistenceError
    assert code == extraction.CODE_ERREUR


@pytest.mark.parametrize("etat_aval", ETATS_AVAL)
def test_mmu_extract_rend_le_MEME_code_qu_avant_et_dit_le_refus_sur_stderr(
        tmp_path, capsys, etat_aval):
    """Le contrat de la CLI, mesure **par `cli.main`** et non deduit du coeur.

    C'est le seul risque de ce lot : un refus qui remonte change l'ordre des
    pannes possibles, donc potentiellement ce que la commande rend. La mesure
    dit trois choses :

    * le code de sortie est `1`, celui de `ExtractionPersistenceError` dans
      `CODES_DE_SORTIE`, exactement comme quand le refus arrivait a l'etape 6 ;
    * le refus est ecrit sur `stderr`, prefixe `Erreur:` comme les autres ;
    * il nomme le lot et l'etat atteint.

    Le rush est un fichier **factice** : sans la garde, la commande irait au
    probe et echouerait sur un decodage. Les deux issues rendent `1`, donc le
    code seul ne separe pas les deux mondes -- c'est le message qui le fait, et
    c'est pourquoi il est asserte ici.
    """
    from mixed_media_utility import cli   # le BANC peut l'importer, pas la TUI

    projet, rush = projet_a_la_main(
        tmp_path, manifeste_a_quatre_lots(etat_aval), frames_presentes=False)

    code = cli.main(["extract", "--project", str(projet),
                     "--video", str(rush), "--fps", str(CADENCE_VISEE),
                     "--yes", "--accept-unknown-color"])

    assert code == extraction.CODE_ERREUR
    erreurs = capsys.readouterr().err
    assert "Erreur:" in erreurs
    assert build_lot_id(RUSH_ID, CADENCE_VISEE) in erreurs
    assert etat_aval in erreurs
    assert "Aucune ecriture n'a eu lieu" in erreurs


@pytest.mark.skipif(
    importlib.util.find_spec("mixed_media_utility.tui") is None,
    reason="le paquet `tui/` n'est pas sur cette branche : la liaison de la "
           "vague 3 porte le COEUR SEUL (Egan, 2026-08-30). La garde vit avec "
           "la TUI et sera mesuree quand elle arrivera.")
def test_la_garde_d_etat_de_la_TUI_EXISTE_TOUJOURS():
    """AC 12.1 -- `EPIC11-ARB-86`, verbatim : « **Cette garde ne se retire pas** ».

    Elle cesse d'etre *load-bearing* avec cette story -- le coeur refuse
    desormais de lui-meme, avant ffmpeg -- et devient une defense en
    profondeur : elle refuse **sans lancer le coeur du tout**, ce que le coeur
    ne fera jamais gratuitement. Son retrait est explicitement hors du perimetre
    de la story (`AC 12.1`), et ce test est ce qui l'empeche de partir par
    inadvertance.

    **Le `skipif` n'est pas un relachement, c'est le contraire.** Sur la branche
    de travail, ou la TUI vit, il ne saute pas et la garde est mesuree. Sur une
    branche qui n'a que le coeur, le test ne peut pas mesurer ce qui n'y est
    pas -- et le SAUTER en le disant vaut mieux que le retirer, qui ferait
    perdre la mesure au retour de la TUI. Le motif du saut est **structurel**
    (l'absence du paquet), jamais un drapeau qu'on oublie de rallumer.
    """
    from mixed_media_utility.tui import atelier_extraction_ecriture

    assert callable(atelier_extraction_ecriture.refus_d_etat_de_lot)
