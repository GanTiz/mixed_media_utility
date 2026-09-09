"""Ou `ingest.json` s'ecrit -- et la divergence qui le rend NECESSAIRE.

`scan_ingest.chemin_du_rapport` existe parce que reconstruire le chemin du
rapport depuis `report.ingest_slug` donne parfois un dossier **different** de
celui que l'ingestion a reellement employe. Ce banc mesure cette divergence
plutot que de la raconter.

**Ce qui a change, et c'est le motif de ce fichier** (mesure le 2026-09-07). Le
docstring de la fonction justifiait son existence par un cas qui n'existe plus :
« un fichier deja situe sous `<projet>/scans/` [...] `scans_dir` vaut alors
`scans` et le dossier `scans/<slug>/` n'existe jamais ». `EPIC7-ARB-88` a ferme
ce cas en excluant `scans/` lui-meme de `_est_un_dossier_de_lot` : un fichier
pose a la racine de `scans/` recoit desormais son propre dossier de lot, et le
chemin reconstruit **coincide**. La prose est restee sur l'ancien regime.

Le cas qui **diverge encore** est le **rang de version** : une seconde ingestion
du meme lot ecrit sous `scans/<slug>_v2/` pendant que `ingest_slug` garde
`<slug>`. Aucun banc ne le jouait, si bien que la seule divergence vivante
etait la seule non mesuree -- et que la prose pouvait deriver sans rougir.

**Regle des fabriques** (CLAUDE.md) : les pages portent des valeurs toutes
differentes, et les rangs sont joues en **tete**, au **milieu** et en **queue**
de la famille de versions. Un balayage tronque qui sauterait le dernier rang ne
se demasque pas autrement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import scan_ingest
from mixed_media_utility.io import project_layout


# --- fabriques -------------------------------------------------------------


def projet(tmp_path: Path) -> Path:
    """Un dossier de projet, son arborescence posee par le COEUR."""
    dossier = tmp_path / "projet"
    dossier.mkdir()
    project_layout.ensure_project_layout(dossier)
    (dossier / "project.json").write_text(
        json.dumps({"schema_version": "2.1", "project": {"name": "projet"},
                    "rushes": [], "lots": []}),
        encoding="utf-8")
    return dossier


def page(chemin: Path, *, valeur: int) -> Path:
    """Une page-image. `valeur` la rend DISTINGUABLE de ses voisines."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(chemin), np.full((40, 60, 3), valeur, dtype=np.uint8))
    return chemin


def source_de_deux_pages(dossier: Path) -> Path:
    """Un dossier source hors `scans/`, portant deux pages distinguables.

    **Deux**, pas une : une fabrique mono-element rendrait invisible toute
    erreur d'appariement entre les pages et le rapport qui les compte.
    """
    page(dossier / "p1.png", valeur=40)
    page(dossier / "p2.png", valeur=200)
    return dossier


def reconstruit_depuis_le_slug(rapport) -> str:
    """Le chemin que l'ancien appelant composait -- celui qui se trompait."""
    return f"scans/{rapport.ingest_slug}"


# ---------------------------------------------------------------------------
# La divergence VIVANTE : le rang de version
# ---------------------------------------------------------------------------


def test_le_rang_de_version_fait_DIVERGER_le_slug_et_le_dossier(tmp_path) -> None:
    """Trois rangs, et le rapport de chacun sous SON dossier.

    La cible est jouee aux **trois** positions de la famille : le rang 1 en
    tete (ou le slug et le dossier coincident encore), le rang 2 au milieu, le
    rang 3 en queue. Une lecture tronquee qui s'arreterait a l'avant-dernier
    rang resterait verte si seuls les deux premiers etaient verifies.
    """
    dossier = projet(tmp_path)
    source = source_de_deux_pages(tmp_path / "rush")

    rangs = [scan_ingest.ingest_scan_lot(dossier, source, dpi=300)]
    rangs.append(scan_ingest.ingest_scan_lot(
        dossier, source, dpi=300, nouvelle_version=True))
    rangs.append(scan_ingest.ingest_scan_lot(
        dossier, source, dpi=300, nouvelle_version=True))

    dossiers = [rapport.scans_dir for rapport in rangs]
    assert dossiers == ["scans/rush", "scans/rush_v2", "scans/rush_v3"], (
        "les trois rangs doivent ecrire sous trois dossiers distincts ; "
        f"mesure : {dossiers}")

    # Le slug, lui, ne bouge pas d'un rang a l'autre -- c'est CE fait qui rend
    # la reconstruction fausse.
    slugs = {rapport.ingest_slug for rapport in rangs}
    assert slugs == {"rush"}, (
        f"le slug ne porte pas le rang ; mesure : {sorted(slugs)}")

    # Et la divergence se lit aux rangs 2 et 3, en queue comprise.
    diverge = [rapport.scans_dir != reconstruit_depuis_le_slug(rapport)
               for rapport in rangs]
    assert diverge == [False, True, True], (
        "la divergence doit apparaitre des le second rang et TENIR au "
        f"dernier ; mesure : {diverge}")


def test_le_rapport_de_CHAQUE_rang_s_ecrit_sous_SON_dossier(tmp_path) -> None:
    """Le regime que la fonction existe pour tenir, joue jusqu'a l'ecriture.

    Ce n'est pas le meme test que le precedent : celui-la mesure la divergence
    des valeurs, celui-ci mesure que `chemin_du_rapport` la **suit**. Un
    `chemin_du_rapport` qui recomposerait depuis le slug passerait le premier
    et echouerait ici -- ce qui est exactement la panne d'origine
    (`[Errno 2] ... ingest.json`, essai de terrain du 2026-08-27).
    """
    dossier = projet(tmp_path)
    source = source_de_deux_pages(tmp_path / "rush")

    attendus = ["scans/rush/ingest.json", "scans/rush_v2/ingest.json",
                "scans/rush_v3/ingest.json"]
    ecrits: list[str] = []
    for indice in range(3):
        rapport = scan_ingest.ingest_scan_lot(
            dossier, source, dpi=300, nouvelle_version=indice > 0)
        chemin = scan_ingest.ecrire_le_rapport(dossier, rapport)
        ecrits.append(chemin.relative_to(dossier).as_posix())
        assert chemin.is_file(), f"rang {indice + 1} : {chemin} n'existe pas"

    assert ecrits == attendus, f"mesure : {ecrits}"

    # **Les trois rapports coexistent** : aucun rang n'ecrase le precedent.
    # C'est la moitie que le cardinal seul ne dirait pas.
    survivants = sorted(
        chemin.relative_to(dossier).as_posix()
        for chemin in (dossier / project_layout.SCANS_DIRNAME).glob("*/ingest.json"))
    assert survivants == attendus, f"mesure : {survivants}"


# ---------------------------------------------------------------------------
# Le cas que `EPIC7-ARB-88` a FERME -- il ne diverge plus, et c'est mesure
# ---------------------------------------------------------------------------


def test_un_fichier_a_la_racine_de_scans_ne_diverge_PLUS(tmp_path) -> None:
    """L'ancienne justification du docstring, mesuree comme fermee.

    Avant `EPIC7-ARB-88`, un fichier pose a la racine de `scans/` etait ingere
    en place avec `scans/` pour dossier de lot, et son rapport partait a la
    racine des lots -- un rapport de lot pose sur l'arborescence entiere, que
    le lot suivant ecrasait. Depuis, `scans/` lui-meme n'est plus un dossier de
    lot : le fichier recoit le sien.

    Ce test n'est donc pas la pour empecher une regression de valeur, mais pour
    tenir la PROSE : tant qu'il est vert, le docstring ne peut pas continuer a
    citer ce cas comme la divergence vivante.
    """
    dossier = projet(tmp_path)
    page(dossier / project_layout.SCANS_DIRNAME / "Ma Mire.png", valeur=90)

    rapport = scan_ingest.ingest_scan_lot(
        dossier, dossier / project_layout.SCANS_DIRNAME / "Ma Mire.png", dpi=300)

    assert rapport.scans_dir == "scans/Ma Mire", (
        "le fichier doit recevoir SON dossier de lot, pas la racine ; "
        f"mesure : {rapport.scans_dir!r}")
    assert rapport.scans_dir == reconstruit_depuis_le_slug(rapport), (
        "ce cas ne doit PLUS diverger ; mesure : "
        f"{rapport.scans_dir!r} contre {reconstruit_depuis_le_slug(rapport)!r}")


# ---------------------------------------------------------------------------
# Frontiere NEGATIVE sur la prose -- ce qu'aucun test positif ne verrait
# ---------------------------------------------------------------------------


PHRASE_PERIMEE = "vaut alors `scans`"
#: Ce qui autorise la phrase a figurer : le paragraphe qui la cite doit dire
#: qu'elle est fausse. Sans ce marqueur, une citation et une affirmation sont
#: le meme texte -- et c'est litteralement ce qui est arrive : la premiere
#: redaction de cette frontiere a rougi sur la retractation qui la corrigeait.
MARQUEUR_DE_RETRACTATION = "qui n'est plus vrai"


def _paragraphes(texte: str) -> list[str]:
    """Le texte decoupe en blocs separes par une ligne vide.

    Un paragraphe est la plus petite unite ou une phrase et sa retractation se
    lisent ensemble : plus large, la frontiere laisserait passer une phrase
    affirmee a l'autre bout du fichier sous couvert d'une retractation lointaine.
    """
    blocs, courant = [], []
    for ligne in texte.splitlines():
        if ligne.strip():
            courant.append(ligne)
        elif courant:
            blocs.append("\n".join(courant))
            courant = []
    if courant:
        blocs.append("\n".join(courant))
    return blocs


def _paragraphes_fautifs(texte: str) -> list[str]:
    """Les blocs qui portent la phrase SANS dire qu'elle est fausse."""
    return [bloc for bloc in _paragraphes(texte)
            if PHRASE_PERIMEE in bloc and MARQUEUR_DE_RETRACTATION not in bloc]


def test_le_docstring_ne_cite_PLUS_le_cas_ferme_comme_vivant() -> None:
    """La derive de prose se mesure, elle ne se relit pas.

    Elle a ete trouvee par une mesure, pas par une lecture : trois sessions
    avaient lu ce docstring sans voir qu'il decrivait un regime ferme depuis
    `EPIC7-ARB-88`. Une frontiere **negative** est le seul geste qui attrape la
    reintroduction -- aucun test positif ne verrait revenir la phrase.

    **Ce qu'elle mesure exactement**, et la nuance porte : non pas l'absence de
    la phrase, mais l'absence d'une phrase **affirmee**. Le docstring corrige
    la cite pour dire qu'elle est fausse, et une frontiere qui refuserait la
    citation forcerait a effacer la retractation -- c'est-a-dire a perdre
    l'information qui empeche la prochaine session de refaire la correction a
    l'envers.
    """
    source = (REPO_ROOT / "src" / "mixed_media_utility"
              / "scan_ingest.py").read_text(encoding="utf-8")
    fautifs = _paragraphes_fautifs(source)
    assert not fautifs, (
        f"la phrase {PHRASE_PERIMEE!r} est affirmee sans retractation dans "
        f"{len(fautifs)} paragraphe(s) de scan_ingest.py. Elle decrit le "
        "regime d'avant EPIC7-ARB-88, mesure comme ferme par "
        "test_un_fichier_a_la_racine_de_scans_ne_diverge_PLUS. "
        f"Premier fautif :\n{fautifs[0][:400]}")


def test_la_phrase_est_bien_PRESENTE_et_retractee() -> None:
    """Le pendant POSITIF, sans lequel la frontiere ci-dessus est tautologique.

    Effacer purement la phrase rendrait la frontiere negative verte pour la
    mauvaise raison -- et ferait perdre la retractation. Ce test exige donc que
    la phrase **soit la**, et qu'elle y soit sous sa forme retractee.
    """
    source = (REPO_ROOT / "src" / "mixed_media_utility"
              / "scan_ingest.py").read_text(encoding="utf-8")
    assert PHRASE_PERIMEE in source, (
        "la retractation a disparu de scan_ingest.py : la prochaine session "
        "n'aura plus rien qui l'empeche de reecrire l'ancien regime.")


def test_la_frontiere_elle_meme_est_CONFRONTEE() -> None:
    """Une frontiere de prose non confrontee mesure sa propre redaction.

    Trois formes acceptees et trois refusees, toutes construites a la main pour
    faire varier ce qui compte : la presence de la phrase, la presence du
    marqueur, et le fait qu'ils soient ou non dans le MEME paragraphe. C'est ce
    dernier point que la premiere redaction ratait.
    """
    accepte = [
        "un texte qui ne parle pas du tout de ce sujet",
        f"Ce que ce docstring disait et {MARQUEUR_DE_RETRACTATION} : "
        f"`scans_dir` « {PHRASE_PERIMEE} ».",
        f"prose neutre\n\nbloc ou la phrase {PHRASE_PERIMEE} figure et "
        f"{MARQUEUR_DE_RETRACTATION}\n\nautre prose",
    ]
    refuse = [
        f"`scans_dir` {PHRASE_PERIMEE} et le dossier n'existe jamais.",
        # Le marqueur existe, mais DANS UN AUTRE paragraphe : c'est le cas que
        # la premiere redaction laissait passer a l'envers.
        f"un paragraphe qui affirme : {PHRASE_PERIMEE}\n\n"
        f"un autre paragraphe, plus loin, {MARQUEUR_DE_RETRACTATION}",
        f"deux affirmations : {PHRASE_PERIMEE}\n\net encore {PHRASE_PERIMEE}",
    ]
    for texte in accepte:
        assert not _paragraphes_fautifs(texte), (
            f"forme acceptee refusee a tort : {texte!r}")
    for texte in refuse:
        assert _paragraphes_fautifs(texte), (
            f"forme fautive acceptee a tort : {texte!r}")
