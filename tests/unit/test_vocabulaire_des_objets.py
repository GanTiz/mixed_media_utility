"""Le RELEVE EXECUTABLE du vocabulaire des objets (story 11.14, lot A).

**Ce banc ne renomme rien.** Il MESURE ce que le depot dit aujourd'hui, et il
pose les frontieres que les lots B a E feront passer au vert. Il existe parce
qu'`EPIC11-ARB-214` demande « qu'on tranche sur les mots une bonne fois pour
toutes » : on ne tranche pas ce qu'on n'a pas compte.

**Le piege que ce banc evite, et il a ete paye trois fois dans ce depot** : une
liste ecrite a la main se perime en silence. Ici, la table
:data:`SYNONYMES_MESURES` est une **hypothese**, pas une verite -- le banc la
confronte au code dans les deux sens :

* chaque synonyme declare doit **exister** dans `src/` (sinon la table porte un
  nom mort) ;
* aucun identifiant portant le radical d'un objet ne doit **echapper** au
  classement (sinon un dixieme nom apparaitrait sans que rien ne rougisse).

C'est ce second volet qui fait le travail. Un banc qui se contenterait du
premier serait tautologique -- exactement le defaut trouve sur la 5.9.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from mixed_media_utility import project_inventory

RACINE = Path(__file__).resolve().parents[2]
SRC = RACINE / "src" / "mixed_media_utility"
# Le schema vit DANS le paquet depuis le 2026-09-07 -- c est ce qui rend
# `pip install mmu-tui` capable de le lire. Ce banc etait reste sur
# l ancien chemin et rendait 6 erreurs de collecte ; trouve par
# `tests/unit/test_perimetre_public.py` a la liaison.
SCHEMA = SRC / "specs" / "project.schema.json"
FIXTURES = RACINE / "tests" / "fixtures"


# ---------------------------------------------------------------------------
# A1 -- les mots que le code emploie AUJOURD'HUI pour chacun des HUIT objets
# ---------------------------------------------------------------------------

#: **Les objets viennent de `project_inventory.NATURES`, jamais recopies.**
#: C'est la table publiee (`project_inventory.py`, « une interface le LIT, elle
#: ne le REDIGE pas ») : si une nature y est ajoutee ou retiree, ce banc la voit
#: sans qu'on ait rien a reporter ici.
NATURES = project_inventory.NATURES

#: Le radical qui rattache un identifiant a un objet. Derive de la nature
#: elle-meme -- `frames_scannees` rend `frames` --, donc pas ecrit a la main :
#: c'est le PREMIER segment de la valeur publiee.
RADICAL_PAR_NATURE = {n: n.split("_")[0] for n in NATURES}

#: **Les RADICAUX de chaque objet, en TOKENS et jamais en sous-chaines.**
#: La distinction n'est pas cosmetique : une recherche par sous-chaine range
#: `slot`, `pilote` et `ballot` sous `lot`, et rend 248 noms la ou il y en a 24.
#: Un token se compare entier.
#:
#: **Deux natures partagent le radical d'une autre, et c'est voulu** (story
#: 11.14) : `frames_scannees` partage `frame` avec `frames_extraites`, et
#: `lot_scanne` partage `lot` avec `lot`. Ce ne sont pas des doublons -- c'est
#: la forme meme de l'ambiguite qu'Egan a nommee. Ce qui les separe est un
#: MARQUEUR, pas un radical, et les deux tables de marqueurs sont juste
#: dessous.
RADICAUX: dict[str, frozenset[str]] = {
    "rush": frozenset({"rush", "rushes"}),
    "lot": frozenset({"lot", "lots"}),
    "lot_scanne": frozenset({"lot", "lots"}),
    "frames_extraites": frozenset({"frame", "frames"}),
    "frames_scannees": frozenset({"frame", "frames"}),
    "master": frozenset({"master", "masters"}),
    "planche": frozenset({"planche", "planches", "tirage", "tirages", "sheet", "sheets"}),
    "scan": frozenset({"scan", "scans"}),
}

#: **Ce qui DESAMBIGUISE une frame.** Le mot `frames` seul ne dit pas de quel
#: objet il parle -- c'est litteralement le defaut qu'Egan nomme : « devant
#: `--frames` ou devant `output-frames/`, deviner s'il s'agit des frames que
#: `extract` a sorties du rush ou de celles qu'un scan a rendues ».
#:
#: Un nom qui porte `frame` SANS aucun de ces marqueurs est **ambigu**, et le
#: cardinal des ambigus est la mesure que la story doit ramener a zero.
#:
#: **`scannee` et `scannees` y sont entres avec la story 11.14** : c'est le mot
#: que le vocabulaire d'Egan retient (`frames_scannees`), et sans lui le nom
#: NEUF de l'objet comptait parmi les AMBIGUS -- la mesure aurait monte au
#: moment meme ou le vocabulaire s'unifiait. Les mots d'avant restent reconnus :
#: le releve doit lire ce que le depot porte, pas ce qu'il devrait porter.
MARQUEURS_SCANNEES = frozenset({
    "output", "scanned", "reconstructed", "rescannees", "rescannee", "scan",
    "scannee", "scannees",
})
#: **`extracted` y est entre le 2026-09-04** (revue 11.14, couche 1). Sa jumelle
#: `MARQUEURS_SCANNEES` connaissait `scanned` depuis le debut ; celle-ci
#: ignorait le participe anglais, alors que les jetons se comparent ENTIERS
#: (c'est la regle du banc) -- si bien que quatre noms parfaitement
#: desambiguises etaient comptes ambigus :
#:
#:     EXTRACTED_FRAME_SUFFIX, THUMBNAIL_ORIGIN_EXTRACTED_FRAME,
#:     build_extracted_frame_filename, read_extracted_frame_timecode
#:
#: Effet direct, et c'est ce qui en fait un defaut et non une coquette : un lot
#: qui renommerait proprement vers `..._extracted_frame_...` aurait vu le
#: releve NE PAS BOUGER, et conclu qu'il n'avait rien gagne. Mesure : 146 ->
#: 142, les quatre noms ci-dessus et eux seuls.
MARQUEURS_EXTRAITES = frozenset({
    "extract", "extracted", "extraites", "extraite", "source"})

#: **Ce qui DESAMBIGUISE un lot** (story 11.14, `EPIC11-ARB-214`). Le lot
#: scanne partage le radical `lot` avec le lot : `NATURE_LOT_SCANNE`,
#: `_famille_du_lot_scanne` et `_slug_du_lot_scanne` tomberaient sous `lot`
#: sans ce filtre, et le cardinal du lot deviendrait faux **en silence** --
#: exactement ce que ce banc existe pour empecher.
#:
#: Le mot `lot` seul, lui, n'est PAS ambigu : il designe le lot, et l'ambiguite
#: qu'Egan a nommee porte sur `frames`, jamais sur `lot`. Un nom de lot sans
#: marqueur va donc sous `lot`, il ne rejoint pas les ambigus -- sans quoi la
#: mesure de la story changerait de sens.
MARQUEURS_LOT_SCANNE = frozenset({
    "scanne", "scannes", "scannee", "scannees", "scanned",
    "reconstruit", "reconstruits", "reconstructed",
})


def _tokens(nom: str) -> frozenset[str]:
    """Decouper un identifiant en tokens : `_`, tirets, et frontieres camelCase."""
    coupe = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", nom)
    return frozenset(m for m in re.split(r"[^a-z0-9]+", coupe.lower()) if m)



#: Ce qui porte un radical du vocabulaire **sans designer l'objet**, avec le
#: motif de chaque exclusion. Une exclusion sans motif est une exclusion qu'on
#: ne peut pas relire : elles sont donc nommees une par une.
FAUX_POSITIFS: dict[str, str] = {
    "slots": "un emplacement de PAGE, pas un objet du vocabulaire d'Egan",
    "slot_index": "idem",
    "output_bit_depth": "la profondeur d'encodage, aucun rapport avec les frames",
}


def _normaliser(nom: str) -> str:
    """Rendre un identifiant comparable : minuscules, separateurs unifies."""
    return re.sub(r"[^a-z0-9]+", "_", nom.lower()).strip("_")


def _noms_de_module(chemin: Path) -> set[str]:
    """Les noms qu'un module PUBLIE : constantes, fonctions et classes de tete.

    Deux choix, et les deux comptent :

    * **l'arbre syntaxique, pas un `grep`** -- un `grep` compterait les mentions
      dans les commentaires et les docstrings, qui ne sont pas des noms ;
    * **le niveau module seulement, jamais les locales d'une fonction.** Une
      variable locale (`frames_ecrites`, `total_frames`) porte une valeur de
      passage ; elle ne DESIGNE pas l'objet. Mesure : le releve de `lot` passe
      de 248 a quelques dizaines de noms une fois les locales exclues.
    """
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except SyntaxError:  # pragma: no cover -- aucun module du depot n'echoue
        return set()
    noms: set[str] = {chemin.stem}
    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            noms.add(noeud.name)
        elif isinstance(noeud, ast.Assign):
            noms.update(c.id for c in noeud.targets if isinstance(c, ast.Name))
        elif isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target, ast.Name):
            noms.add(noeud.target.id)
    return noms


def _tous_les_noms_de_src() -> set[str]:
    """Les noms publies par `src/`, **plus les proprietes du schema**.

    Le schema en fait partie parce que deux des neuf noms de l'objet le plus
    mal nomme n'existent QUE la : `reconstructed_frame_count` et
    `scanned_version_ranks` sont des cles de manifeste, jamais des constantes.
    Un releve qui ne lirait que le code les manquerait tous les deux.
    """
    noms: set[str] = set(_proprietes_du_schema())
    for chemin in sorted(SRC.rglob("*.py")):
        noms |= _noms_de_module(chemin)
    return noms


def _classer(noms: set[str]) -> tuple[dict[str, set[str]], set[str]]:
    """Ranger chaque nom sous son objet, et rendre les noms AMBIGUS.

    Le second element du couple est ce qui fait travailler ce banc : un nom qui
    porte le radical `frame` sans aucun marqueur ne dit pas de quel objet il
    parle. Leur cardinal est la mesure que la story 11.14 doit ramener a zero,
    et c'est la seule facon de voir apparaitre un DIXIEME nom.
    """
    par_objet: dict[str, set[str]] = {n: set() for n in NATURES}
    ambigus: set[str] = set()
    for brut in noms:
        if _normaliser(brut) in FAUX_POSITIFS:
            continue
        jetons = _tokens(brut)
        for nature, radicaux in RADICAUX.items():
            if not (jetons & radicaux):
                continue
            if nature.startswith("frames_"):
                if jetons & MARQUEURS_SCANNEES:
                    par_objet["frames_scannees"].add(brut)
                elif jetons & MARQUEURS_EXTRAITES:
                    par_objet["frames_extraites"].add(brut)
                else:
                    ambigus.add(brut)
            elif nature in ("lot", "lot_scanne"):
                # Meme mecanique que ci-dessus, et pour le meme motif -- mais
                # SANS troisieme issue : un nom de lot sans marqueur designe
                # bien le lot. L'ambiguite d'Egan porte sur `frames`.
                if jetons & MARQUEURS_LOT_SCANNE:
                    par_objet["lot_scanne"].add(brut)
                else:
                    par_objet["lot"].add(brut)
            else:
                par_objet[nature].add(brut)
    return par_objet, ambigus


@pytest.fixture(scope="module")
def releve() -> tuple[dict[str, set[str]], set[str]]:
    return _classer(_tous_les_noms_de_src())


def test_les_HUIT_objets_du_releve_sont_ceux_de_la_table_publiee() -> None:
    """A1 -- le banc lit le vocabulaire ou il est ECRIT, il ne le redige pas.

    **HUIT depuis le lot B de la story 11.14** : `frames_rescannees` est devenu
    `frames_scannees`, et `lot_scanne` est entre. Ce banc n'a rien eu a
    apprendre de ce changement -- `NATURES` est importe -- ; ce qu'il a fallu
    porter, c'est `RADICAUX`, qui est l'ENTREE de la mesure et non sa sortie.
    """
    assert set(RADICAUX) == set(NATURES)
    assert len(NATURES) == 8


#: **L'ENSEMBLE des noms ambigus, gele** -- pas leur cardinal.
#:
#: Pourquoi un ensemble et non un nombre : deux cardinaux egaux peuvent
#: recouvrir deux ensembles differents. C'est la meme doctrine que
#: `CLAUDE.md` applique aux listes de verdicts (« on compare des listes,
#: jamais des compteurs »), et c'est le mode de panne que le lot B a trouve A
#: LA MAIN pendant la story -- le banc, lui, ne pouvait pas le voir.
#:
#: **Cette table ne se met a jour QUE DANS UN SENS sans discussion** : quand
#: des noms en SORTENT, c'est une baisse et on la repercute. Un nom qui y
#: ENTRE est un nom neuf portant `frame` sans marqueur : il se corrige, il ne
#: s'inscrit pas.
#:
#: 147 au `baseline_commit`, 146 apres le lot B, 142 depuis que
#: `MARQUEURS_EXTRAITES` connait `extracted` (2026-09-04).
AMBIGUS_ATTENDUS: frozenset[str] = frozenset({
    "CHAMP_FRAMES", "COUNT_FRAMES_TIMEOUT_SECONDS", "DEFAULT_FRAMES_PER_PAGE",
    "DuplicateFrameTimecodeError", "ENCODE_FRAME_RATE_UNUSABLE",
    "ENCODE_SYNTHETIC_FRAMES_PRESENT", "ENCODE_UNEXPECTED_FRAMES",
    "FRAMES_ATTENDUES_INCONNUES", "FRAMES_DIRNAME",
    "FRAMES_PER_PAGE_VOCABULARY", "FRAMES_SKIPPED",
    "FRAMES_SYNTHETIQUES_PRESENTES", "FRAME_DIGEST_PREFIX",
    "FRAME_GRID_GAP_MM", "FRAME_GRID_GAP_V2_MM", "FRAME_ZONES_MM",
    "FRAME_ZONE_ADDRESS_FIELDS", "FRAME_ZONE_ASPECT_RATIO",
    "FRAME_ZONE_ASPECT_TOLERANCE", "FrameCache", "FrameCropPlan",
    "FrameCropPlanLike", "FrameExtractionError", "FrameObservation",
    "FrameSelection", "FrameSelectionError", "FrameSelectionLike",
    "FrameShapeConflictError", "FrameSlotPlan", "InvalidFrameRateError",
    "LATE_FRAME_RATE_THRESHOLD", "LATE_FRAME_TOLERANCE_S",
    "LEGACY_FRAMES_DIRNAME", "LIBELLE_DES_FRAMES", "LIBELLE_FRAMES",
    "LIBELLE_FRAMES_ATTENDUES", "LIBELLE_FRAMES_OBTENUES",
    "MAX_EXPECTED_FRAME_COUNT", "MISSING_FRAME_TEXT", "MOTIF_DES_FRAMES",
    "MOTIF_DES_FRAMES_EN_BALAYAGE", "MOTIF_DES_FRAMES_SANS_REFERENCE",
    "ONGLET_FRAME", "PATCH_FRAME_MM", "PHRASE_FRAMES_DU_MANQUE",
    "PLURIEL_DES_FRAMES", "PresentedFrame", "PrevizFrame", "PrevizFrameZone",
    "PrevizSequenceFrame", "SEQUENCE_FRAME_DIGEST_FIELDS",
    "SYNTHETIC_FRAME_REASONS", "SYNTHETIC_FRAME_WRITTEN", "ScheduledFrame",
    "SelectedFrame", "SequenceFrameLike", "SequentialFrameReader",
    "TOLERANCE_DUREE_RELINK_FRAMES", "UNITE_FRAMES",
    "VERIFY_FRAMES_DIR_ABSENT", "VERIFY_FRAMES_DIR_NOT_DECLARED",
    "VERIFY_FRAME_COUNT_MISMATCH", "VERIFY_MISSING_FRAMES",
    "VERIFY_UNEXPECTED_FRAMES", "_DigestFrame", "_FRAME_TIMECODE_RE",
    "_FrameSlotLike", "_HISTORICAL_FRAME_BANDS_MM", "_LARGEUR_DES_FRAMES",
    "_PlannedFrame", "_SelectedFrameLike", "_carries_frames",
    "_compute_frame_zones", "_corrected_frame", "_expected_frame_count",
    "_frame_limit", "_frame_zones", "_frames_attendues", "_frames_by_address",
    "_frames_by_slot", "_is_conforming_frame_name", "_ligne_des_frames",
    "_mesures_de_frames", "_normalize_frame_count", "_normalize_frame_paths",
    "_page_frame_shape", "_read_frame_zone",
    "_require_every_written_frame_is_shown", "_resolve_expected_frame_count",
    "_select_sheet_frames", "_sequence_frame_digest_entry",
    "_start_offset_frames", "_timecode_to_frames", "_validated_real_frame",
    "apply_correction_to_frames", "build_frame_filename",
    "build_frame_selection_command", "build_missing_frame_image",
    "compte_de_frames", "compteur_de_frames",
    "compute_frame_timecodes_digest", "count_frames_exact",
    "count_written_temp_frames", "crop_frames", "ensure_frame_order",
    "ensure_uniform_frame_shapes", "exact_frame_rate", "expected_frame_count",
    # ENTRE le 2026-09-07, par INSCRIPTION et non par correction -- c'est
    # l'exception que ce banc documente deja pour `LEGACY_FRAMES_DIRNAME` :
    # « le sortir demanderait un marqueur qui mentirait sur ce qu'il designe ».
    #
    # `PROGRESS_FRAME_KEY` vaut litteralement `"frame"` : c'est la CLE du flux
    # `-progress` de ffmpeg, un nom choisi par ffmpeg et recopie ici pour etre
    # compare a sa sortie. Elle ne designe aucun objet du produit, donc aucun
    # des deux marqueurs ne s'y applique sans mentir : `source` la rangerait
    # sous les frames EXTRAITES et `output` sous les frames SCANNEES, alors que
    # le meme compteur sert aux deux -- un master s'encode aussi bien depuis un
    # lot extrait que depuis un lot rescanne.
    #
    # Elle est entree par la LIAISON du 2026-09-07 : la constante vient de la
    # story 6.7 (`claude/epic6_6-7_6-8`) et ce banc de la story 11.14
    # (`oc/epic-11-TUI`). Aucune des deux branches ne pouvait voir l'autre ;
    # seule la fusion le revele. Verse en dette sous `VOCAB114-N1` pour que le
    # proprietaire de la 11.14 tranche s'il prefere un renommage.
    "PROGRESS_FRAME_KEY",
    "export_frame_tiff16", "first_frame_timecode", "frame_band_mm",
    "frame_count", "frame_image_rect_mm", "frame_index_to_timecode",
    "frame_selection", "frame_timecode", "frame_timecodes",
    "frame_timecodes_digest", "frames_dir", "frames_du_balayage",
    "frames_du_dossier", "frames_per_page_vocabulary",
    "frames_per_timecode_second", "frames_sur_le_disque",
    "last_frame_timecode", "ligne_des_frames", "ligne_des_frames_attendues",
    "ligne_des_frames_obtenues", "load_frame_image_for_print",
    "missing_frame_second_line", "octets_par_frame", "patch_frame_path_mm",
    "probe_frame_size", "requires_printed_frame", "resolve_frame_rate",
    "resolve_frames_per_page", "synthetic_frame_count", "synthetic_frames",
    "temp_frame_path", "timecode_frame_field_width",
    "timecode_to_frame_index", "validate_frame_timecode",
})


def test_le_releve_compte_les_noms_AMBIGUS_du_mot_frames(releve) -> None:
    """A1 -- **la mesure de la story**, et c'est un cardinal, pas une opinion.

    Un nom qui porte `frame` sans marqueur ne dit pas de quel objet il parle.
    C'est litteralement ce qu'Egan decrit. Le cardinal est asserte EXACTEMENT
    et non dans une fourchette : c'est un releve, et un releve qui tolere une
    derive ne releve plus rien. Sa valeur baissera au fil des lots B a E, et
    chaque baisse se constate ici plutot qu'elle ne se raconte.
    """
    _, ambigus = releve
    # **147 au `baseline_commit`, 146 depuis le lot B** (2026-09-04). Un nom
    # neuf portant `frame` sans marqueur fait rougir ce test -- c'est voulu, et
    # c'est ce qui a servi pendant le lot B : la premiere mesure rendait 147 a
    # nouveau, la baisse de deux noms retires (`_famille_de_frames`,
    # `_slug_de_frames`) etant exactement annulee par un nom neuf que le lot
    # venait d'ecrire, `frames_dir_from_slug`. Il a ete renomme
    # `extract_frames_dir_from_slug` dans la foulee -- un releve qui ne bouge
    # pas apres un renommage de fond dit qu'on a remplace une ambiguite par une
    # autre.
    #
    # `LEGACY_FRAMES_DIRNAME`, lui, ENTRE dans le releve et y reste : il NOMME
    # le mot ambigu retire, donc il est ambigu par construction. Le sortir
    # demanderait un marqueur qui mentirait sur ce qu'il designe.
    # **On tient l'ENSEMBLE, plus le cardinal** (revue 11.14, couche 1).
    # Le commentaire ci-dessus RACONTE le mode de panne -- « la baisse de deux
    # noms retires exactement annulee par un nom neuf » -- et le banc ne
    # pouvait pas le voir : 146 noms, DEUX cites. Mutant mesure : un renommage
    # qui desambiguise vraiment (`FrameCache` -> `ExtractFrameCache`) plus un
    # nom neuf ambigu ecrit par le meme changement (`FRAME_TARGET_HINT`)
    # laissaient les 11 tests AU VERT. C'est la tautologie sur la constante
    # centrale que la politique nomme (5.9).
    #
    # La difference symetrique dit LESQUELS ont bouge et dans quel sens : un
    # nom sorti et un nom entre ne s'annulent plus.
    manquants = AMBIGUS_ATTENDUS - ambigus
    surnumeraires = ambigus - AMBIGUS_ATTENDUS
    assert (manquants, surnumeraires) == (set(), set()), (
        "Le releve des noms ambigus a change.\n"
        f"  SORTIS des ambigus ({len(manquants)}) -- une baisse, a repercuter "
        f"dans AMBIGUS_ATTENDUS : {sorted(manquants)}\n"
        f"  ENTRES dans les ambigus ({len(surnumeraires)}) -- un nom NEUF "
        f"portant `frame` sans marqueur, a corriger et non a inscrire : "
        f"{sorted(surnumeraires)}")
    # Garde-fou : un collecteur casse rendrait l'ensemble vide, et deux
    # ensembles vides seraient egaux.
    #
    # 142 -> 143 le 2026-09-07, par l'entree de `PROGRESS_FRAME_KEY` a la
    # liaison de `claude/epic6_6-7_6-8`. Le motif de l'inscription est ecrit sur
    # la ligne elle-meme, dans `AMBIGUS_ATTENDUS`. Cette HAUSSE est la premiere
    # du releve, et il faut la lire pour ce qu'elle est : la mesure de la story
    # 11.14 doit descendre, et un nom entre par une liaison la fait monter d'un.
    # Elle n'annule aucune baisse -- la difference symetrique juste au-dessus le
    # garantit, et c'est precisement ce qu'elle a ete ecrite pour garantir.
    assert len(ambigus) == 143, len(ambigus)


def test_chaque_objet_du_releve_porte_AU_MOINS_un_nom(releve) -> None:
    """A1, sens inverse -- un objet a zero nom signale un classement casse.

    Sans ce volet, la mesure des ambigus serait satisfaite par un classement
    qui ne classe rien et jette tout dans les ambigus.
    """
    par_objet, _ = releve
    vides = [n for n in NATURES if not par_objet[n]]
    assert vides == [], vides


def test_l_objet_FRAMES_SCANNEES_porte_les_NEUF_noms_de_la_fiche(releve) -> None:
    """A1 -- le chiffre qui justifie la story, mesure et non estime.

    Les noms sont assertes **un par un** : un cardinal seul serait vrai avec
    d'autres noms, ce qui est exactement le mode de panne qu'une campagne de
    mutation trouve et qu'une relecture manque.

    **Les noms cites sont ceux qui SURVIVENT au lot B**, et le choix compte :
    `SCAN_FRAMES_DIRNAME` est le nom neuf du dossier ; `output_frames_dir`,
    `reconstructed_frame_count` et `OUTPUT_FRAMES_WATERMARK_FIELD` nomment des
    CLES de manifeste, gelees par `EPIC11-ARB-221` -- elles ne bougeront pas.
    Citer `OUTPUT_FRAMES_DIRNAME`, qui n'est plus qu'un alias de transition,
    ferait rougir ce test le jour ou l'alias partira : ce serait un faux
    signal, pas une mesure.
    """
    par_objet, _ = releve
    for nom in ("SCAN_FRAMES_DIRNAME", "NATURE_FRAMES_SCANNEES",
                "output_frames_dir", "reconstructed_frame_count",
                "OUTPUT_FRAMES_WATERMARK_FIELD"):
        assert nom in par_objet["frames_scannees"], (
            nom, sorted(par_objet["frames_scannees"]))
    assert len(par_objet["frames_scannees"]) >= 6, sorted(
        par_objet["frames_scannees"])


def test_l_objet_LOT_SCANNE_est_SEPARE_du_lot_et_ne_le_POLLUE_pas(
        releve) -> None:
    """**Le piege de jetons du lot B, mesure plutot que suppose.**

    `lot_scanne` partage le radical `lot` avec `lot`. Sans le filtre par
    marqueur, `NATURE_LOT_SCANNE`, `_famille_du_lot_scanne` et
    `_slug_du_lot_scanne` tomberaient sous `lot` : le cardinal du lot serait
    faux **en silence**, et le lot scanne n'aurait aucun nom -- ce que le
    volet « chaque objet porte au moins un nom » attraperait, mais sans dire
    lequel des deux est en cause.

    Les deux sens sont assertes : ces noms-la sont bien sous `lot_scanne`, et
    ils ne sont PAS sous `lot`. Une inclusion seule laisserait passer un
    classement qui les mettrait aux deux endroits, donc qui compterait deux
    fois.
    """
    par_objet, _ = releve
    for nom in ("NATURE_LOT_SCANNE", "_famille_du_lot_scanne",
                "_slug_du_lot_scanne"):
        assert nom in par_objet["lot_scanne"], (
            nom, sorted(par_objet["lot_scanne"]))
        assert nom not in par_objet["lot"], (nom, sorted(par_objet["lot"]))
    # Et le lot ORDINAIRE garde les siens : un filtre trop large les aurait
    # tous emportes vers `lot_scanne`.
    assert "build_lot_id" in par_objet["lot"], sorted(par_objet["lot"])


def test_un_nom_de_l_objet_ECHAPPE_a_tout_radical_et_c_est_le_pire(
        releve) -> None:
    """A1 -- **le nom qu'aucun `grep` du vocabulaire ne trouve.**

    `scanned_version_ranks` designe les frames scannees et ne porte AUCUN
    radical : ni `frame`, ni `frames`. Il n'apparait donc dans aucun releve
    fonde sur le vocabulaire, ni dans celui-ci -- et c'est precisement pourquoi
    il est ecrit ici. C'est le mode de panne le plus couteux d'un renommage :
    le nom qu'on ne trouve pas est celui qu'on oublie.

    Ce test n'echouera pas quand le vocabulaire sera unifie ; il restera vrai
    tant que la cle existe, et il rougira le jour ou elle sera renommee -- ce
    qui est exactement le moment ou quelqu'un doit relire cette note.
    """
    par_objet, ambigus = releve
    assert "scanned_version_ranks" in _proprietes_du_schema()
    assert "scanned_version_ranks" not in par_objet["frames_scannees"]
    assert "scanned_version_ranks" not in ambigus


def test_l_objet_RUSH_ne_porte_AUCUN_nom_ambigu(releve) -> None:
    """A4 -- **le volet symetrique**, sans lequel A1 serait vert sur un vide.

    `rush` est le seul objet dont la fiche dit « un seul mot, rien a faire ».
    Aucun de ses noms n'est ambigu, la ou des dizaines de noms de `frame` le
    sont : c'est la difference que la story existe pour effacer, et elle se
    mesure plutot qu'elle ne se raconte.
    """
    par_objet, ambigus = releve
    assert par_objet["rush"], "le classement ne rend AUCUN nom pour `rush`"
    assert not any("rush" in _tokens(n) for n in ambigus), sorted(ambigus)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "story 11.14, lots B a E : le vocabulaire n'est pas encore unifie. "
        "Ce test PASSERA quand il le sera -- et `strict=True` le fait alors "
        "rougir, ce qui force a retirer ce marqueur plutot qu'a le laisser "
        "vert en silence."
    ),
)
def test_le_vocabulaire_unifie_ne_laisse_AUCUN_nom_ambigu() -> None:
    """AC 1.2 -- la frontiere de la story, posee avant qu'elle puisse passer."""
    _, ambigus = _classer(_tous_les_noms_de_src())
    assert ambigus == set(), sorted(ambigus)


# ---------------------------------------------------------------------------
# A2 -- les proprietes de schema candidates, extraites du schema lui-meme
# ---------------------------------------------------------------------------


def _proprietes_du_schema() -> set[str]:
    """Toutes les cles de `properties` du schema, a toute profondeur."""
    document = json.loads(SCHEMA.read_text(encoding="utf-8"))
    trouvees: set[str] = set()

    def descendre(noeud: object) -> None:
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                if cle == "properties" and isinstance(valeur, dict):
                    trouvees.update(valeur)
                descendre(valeur)
        elif isinstance(noeud, list):
            for valeur in noeud:
                descendre(valeur)

    descendre(document)
    return trouvees


def test_les_proprietes_de_schema_candidates_sont_extraites_du_SCHEMA(
) -> None:
    """A2 -- la liste qui instruit `Q7`, lue et non recopiee.

    Elle est **derivee du schema** : un champ ajoute demain y entre seul. Le
    cardinal est asserte pour que l'ajout se voie ; il n'est pas le sujet.
    """
    proprietes = _proprietes_du_schema()
    assert len(proprietes) == 117, len(proprietes)
    # **Par TOKEN, comme le releve A1**, et non par sous-chaine : sinon `slot`
    # tombe sous `lot` et `patch_preset_id` sous `patch`. Les deux mesures de
    # ce banc emploient donc la meme regle, ce qui est la seule facon qu'elles
    # se comparent.
    tous_les_radicaux = frozenset().union(*RADICAUX.values())
    candidates = {
        prop for prop in proprietes
        if (_tokens(prop) & tous_les_radicaux) and prop not in FAUX_POSITIFS
    }
    # **28 au `baseline_commit`**, et non les 31 que la fiche annonce : la
    # fiche comptait par SOUS-CHAINE (`slot` sous `lot`, `patch_preset_id` sous
    # `patch`), ce releve compte par TOKEN. L'ecart est nomme plutot que tu, et
    # le cardinal est asserte EXACTEMENT : un releve qui tolere une derive ne
    # releve plus rien.
    assert len(candidates) == 28, sorted(candidates)
    # Trois des quatre proprietes que l'AC 3.1 nomme doivent en faire partie.
    # La quatrieme, `scanned_version_ranks`, ne porte aucun radical -- voir
    # `test_un_nom_de_l_objet_ECHAPPE_a_tout_radical_et_c_est_le_pire`.
    for attendue in (
        "output_frames_dir",
        "output_frames_version_watermark",
        "reconstructed_frame_count",
    ):
        assert attendue in candidates, (attendue, sorted(candidates))
    assert "scanned_version_ranks" not in candidates


# ---------------------------------------------------------------------------
# A3 -- ce que la regeneration des sorties gelees va couter
# ---------------------------------------------------------------------------

#: Les options de la CLI qui portent un mot du vocabulaire. Ecrites ici parce
#: qu'elles sont l'ENTREE de la mesure, pas sa sortie -- et le banc verifie
#: ci-dessous qu'elles existent bien dans `cli.py`, sinon la mesure porterait
#: sur des options imaginaires.
OPTIONS_DU_VOCABULAIRE = (
    # `--frames` est devenue `--frames-scannees` au lot C (`EPIC11-ARB-220`,
    # retrait pur), puis `--lot-scanne` (`EPIC11-ARB-224`, meme doctrine). Le
    # banc verifie plus bas que chaque option de cette liste existe REELLEMENT
    # dans `cli.py` : c'est ce qui a rougi ici, et c'est ce qui rougirait a
    # nouveau si l'un des deux noms repartait.
    "--lot-scanne", "--frames-par-page", "--lot", "--lot-slug",
    "--accept-incomplete-lot", "--confirmer-dernier-lot", "--scan",
    # `--tirage` est devenu `--planche` (`EPIC11-ARB-224`, second temps :
    # « "--tirage" n'est pas un mot de vocabulaire. C'est "planche". »), et
    # `--profile`/`--resolution` entrent parce que `remove` designe desormais
    # un master par les arguments qui l'ont PRODUIT.
    "--avec-scans", "--rush", "--master", "--planche",
    "--profile", "--resolution",
)


def _scenarios_d_identite() -> list[tuple[str, list[str]]]:
    """Les scenarios geles, avec leur `argv`, lus des quatre fixtures."""
    scenarios: list[tuple[str, list[str]]] = []
    for chemin in sorted(FIXTURES.glob("identite-*.json")):
        document = json.loads(chemin.read_text(encoding="utf-8"))
        # **La forme reelle des fixtures** : un objet a deux cles, `entrees`
        # (les condensats de fichiers) et `scenarios` (un DICT d'invocations).
        # Prendre `document.values()` melangeait les deux et rendait huit
        # scenarios sur 141 -- une mesure fausse qui n'aurait rien dit.
        for entree in document.get("scenarios", {}).values():
            if isinstance(entree, dict):
                argv = [str(a) for a in entree.get("argv", [])]
                scenarios.append((chemin.name, argv))
    return scenarios


def test_les_options_du_vocabulaire_existent_TOUTES_dans_la_CLI() -> None:
    """A3, prealable -- mesurer sur des options imaginaires ne mesure rien."""
    # **Les deux formes de guillemets, et l'option sur sa propre ligne.**
    # `cli.py` declare `'--frames',` seul sur une ligne quand l'aide est longue
    # (`cli.py:4213`) et `add_argument('--lot', ...)` quand elle tient. Chercher
    # `add_argument("--x")` ne trouvait aucune des onze : la mesure aurait ete
    # vraie sur rien.
    source = (SRC / "cli.py").read_text(encoding="utf-8")
    absentes = [
        o for o in OPTIONS_DU_VOCABULAIRE
        if f"'{o}'" not in source and f'"{o}"' not in source
    ]
    assert absentes == [], absentes


def test_le_cout_de_regeneration_des_sorties_gelees_est_CHIFFRE() -> None:
    """A3 -- le poste de cout dominant de la story, compte avant de l'engager."""
    scenarios = _scenarios_d_identite()
    assert len(scenarios) == 141, len(scenarios)
    cites = [
        (fichier, argv) for fichier, argv in scenarios
        if any(o in argv for o in OPTIONS_DU_VOCABULAIRE)
    ]
    assert len(cites) == 84, len(cites)
    occurrences = sum(
        chemin.read_text(encoding="utf-8").count("output-frames")
        for chemin in sorted(FIXTURES.glob("identite-*.json"))
    )
    assert occurrences == 524, occurrences


def test_la_mesure_du_cout_MORD_sur_une_option_qui_n_est_pas_du_vocabulaire(
) -> None:
    """A3, volet symetrique -- sans lui, le compte serait vrai par hasard.

    Une option qui n'appartient pas au vocabulaire ne doit citer AUCUN
    scenario ; si elle en citait, c'est que l'appariement compte des sous-
    chaines plutot que des arguments.
    """
    scenarios = _scenarios_d_identite()
    tous_lots = [a for _, a in scenarios if "--lot" in a]
    assert tous_lots, "aucun scenario ne cite --lot : le classement est casse"
    inconnue = [a for _, a in scenarios if "--frmes" in a]
    assert inconnue == [], inconnue
