# -*- coding: utf-8 -*-
"""Dette `CALIB-N1` -- l'ingestion du scan n'est plus MUETTE.

Le grief de terrain d'Egan du 2026-09-06, mot pour mot : « la barre de
progression de la calibration saute de 0 a 100 ». Le diagnostic de la nuit
suivante l'a mesure plutot que suppose :
`scan_calibrate.calibrer_la_chaine` enchaine **trois** phases et n'en observait
qu'**une**.

| phase | duree relative sur un PDF 300 dpi | canal AVANT |
|---|---|---|
| `scan_ingest.ingest_scan_lot` | **la plus longue** (rasterisation) | **muet** |
| `scan_detection.detect_lot_pages` | moyenne | un jalon par page |
| ecriture du profil | negligeable | muet |

Sur une **mire** -- une page --, la seule phase observee ne produisait qu'un
jalon, a la toute fin. Ce banc mesure la moitie coeur du correctif : l'ajout du
canal a `ingest_scan_lot`, et le fait que son absence ne change rien.

**Ce que ce banc ne mesure PAS, dit plutot que tu** : il ne mesure pas ce que
l'ecran en fait. La surface TUI a son propre banc
(`tests/unit/tui/test_progression_des_deux_phases_de_la_calibration.py`), et
les melanger ferait echouer celui-ci pour des motifs qui ne sont pas les siens.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility import scan_calibrate, scan_detection, scan_ingest
from mixed_media_utility.io import project_layout

DPI = 600


def _page(chemin: Path, valeur: int) -> Path:
    """Une page image **distinguable**, jamais un remplissage uniforme.

    La regle des fabriques du depot : une valeur par page, differente d'une
    page a l'autre. Un remplissage uniforme rendrait invisible toute erreur
    d'appariement entre l'ordre de lecture et l'ordre des jalons.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(chemin), np.full((80, 60, 3), valeur, dtype=np.uint8))
    return chemin


#: Le cote, en points PostScript, d'une page qu'aucun rasteriseur ne peut
#: rendre : a 600 dpi elle vaudrait 1,7 million de pixels de cote, et pdfium
#: refuse l'allocation. C'est le levier -- mesure, instantane, sans allouer un
#: octet -- d'un PDF qui **s'ouvre** (donc que `_cardinal_des_pages` compte
#: pour toutes ses pages) mais dont **une** page ne se rasterise pas.
COTE_IRRASTERISABLE = 200_000

#: Les tailles des pages d'un PDF de fabrique, en points. **Toutes
#: DISTINCTES** : la regle des fabriques interdit le remplissage uniforme, et
#: une taille de page voyage jusqu'au rapport (`canvas_size_pt`), donc une
#: permutation des pages d'un PDF s'y verrait.
TAILLES_DE_PAGE = ((200, 100), (210, 120), (220, 140), (230, 160),
                   (240, 180), (250, 200), (260, 220), (270, 240),
                   (280, 260), (290, 280))


def _pdf(chemin: Path, nb_pages: int, *, page_fautive: int | None = None) -> Path:
    """Un PDF de `nb_pages` pages DISTINGUABLES, eventuellement mutile.

    **La regle des fabriques appliquee a la NATURE de la source.** Avant ce
    banc, `_page` ne fabriquait que du `.tiff`/`.png` et **aucun banc de la
    vague n'ingerait un PDF** -- alors que la mire reelle du depot en est un,
    que le tableau du docstring de ce module parle d'un « PDF 300 dpi » et que
    toute la dette `CALIB-N1` porte sur lui. Cinq mutants ont survecu a ce
    trou. Une fabrique qui ne produit qu'une nature de source rend invisible
    tout ce qui distingue les deux, exactement comme une fabrique
    mono-element rend invisible une erreur d'appariement.

    `page_fautive` designe l'index d'une page qu'aucun rasteriseur ne rendra.
    Le PDF **s'ouvre quand meme** : c'est tout l'interet, et c'est le seul
    regime ou la branche `except` de `_ingest_files` est atteinte alors que
    des jalons sont **deja partis**.
    """
    import pypdfium2 as pdfium

    chemin.parent.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument.new()
    for index in range(nb_pages):
        if index == page_fautive:
            document.new_page(COTE_IRRASTERISABLE, COTE_IRRASTERISABLE)
        else:
            document.new_page(*TAILLES_DE_PAGE[index % len(TAILLES_DE_PAGE)])
    document.save(str(chemin))
    return chemin


#: Les deux PDF de TERRAIN du depot. Une fabrique mesure la fabrique ; elle ne
#: devient une mesure du produit que confrontee a un artefact reel -- et c'est
#: le premier de ces deux fichiers, la mire, qui a produit le grief d'Egan.
MIRE_REELLE = RACINE / "tests" / "fixtures" / "scans" / \
    "Page calibration HP ENVY La Seyne.pdf"
SCAN_REEL_7_PAGES = RACINE / "tests" / "fixtures" / "lots" / "TEST_FILE_12p5" / \
    "scan_Document_2026-08-10_095415.pdf"


@pytest.fixture
def projet(tmp_path: Path) -> Path:
    dossier = tmp_path / "projet"
    project_layout.ensure_project_layout(dossier)
    return dossier


@pytest.fixture
def lot_de_quatre(tmp_path: Path) -> Path:
    """QUATRE pages distinguables -- assez pour que les deux BORDS existent.

    Quatre et non deux : avec deux elements, la cible de tete est aussi la
    cible d'avant-derniere position, et un balayage tronque par la queue est
    indiscernable d'un balayage correct. Les bancs de bord ci-dessous placent
    leur page fautive en **tete** puis en **queue** de cette meme fabrique.
    """
    dossier = tmp_path / "pile"
    for rang, valeur in enumerate((30, 90, 160, 220)):
        _page(dossier / f"page_{rang:02d}.tiff", valeur)
    return dossier


def _jalons(rapport: list) -> list:
    """Le collecteur, avec la bonne arite -- l'ecrire faux coute un banc vert.

    `EmetteurProgression` **absorbe** le `TypeError` d'un rappel de mauvaise
    arite, par contrat (`EPIC7-ARB-79`) : un `rapport.append` nu rendrait zero
    jalon sans un mot, et le banc accuserait le relais.
    """
    return lambda faites, total: rapport.append((faites, total))


# --- la SUITE des jalons, pas un jalon -------------------------------------


def test_l_ingestion_d_un_dossier_emet_UN_JALON_PAR_PAGE(
    projet: Path, lot_de_quatre: Path
) -> None:
    """La suite entiere, sa monotonie et ses bornes.

    **Un banc qui n'observerait qu'un seul jalon ne mesurerait rien** : c'est
    exactement l'etat d'avant le correctif, ou la phase observee n'en emettait
    qu'un. Ce qui distingue une barre vivante d'une barre qui saute de 0 a 100
    est la SUITE, donc c'est la suite qui est mesuree.
    """
    vus: list = []
    scan_ingest.ingest_scan_lot(projet, lot_de_quatre, dpi=DPI,
                                rappel_progression=_jalons(vus))

    faites = [f for f, _ in vus]
    totaux = {t for _, t in vus}
    assert faites == [1, 2, 3, 4], (
        "l'ingestion doit emettre un jalon par page traversee, dans l'ordre ; "
        f"vus : {vus!r}")
    assert totaux == {4}, f"le total ne varie pas au sein d'un lot : {vus!r}"
    # Monotonie et bornes, dites explicitement plutot que deduites de l'egalite
    # ci-dessus : c'est ce que le prochain lecteur cherchera.
    assert faites == sorted(faites) and len(set(faites)) == len(faites)
    assert faites[0] >= 1 and faites[-1] == 4


def test_l_ingestion_d_une_IMAGE_SEULE_emet_son_unique_jalon(
    projet: Path, tmp_path: Path
) -> None:
    """La borne basse de la fabrique : un lot d'une page en emet un, pas zero.

    C'est le cas de la MIRE, celui du grief. Avant le correctif il n'y avait
    aucun jalon d'ingestion du tout ; en emettre un est ce qui fait que la
    barre bouge avant la detection.
    """
    vus: list = []
    page = _page(tmp_path / "mire.png", 120)
    scan_ingest.ingest_scan_lot(projet, page, dpi=DPI,
                                rappel_progression=_jalons(vus))
    assert vus == [(1, 1)]


# --- les deux BORDS : un saut en tete, un saut en queue ---------------------


@pytest.mark.parametrize("rang_fautif,position", [(0, "tete"), (3, "queue")])
def test_un_fichier_ILLISIBLE_a_CHAQUE_BORD_ne_fait_ni_caler_ni_reculer(
    projet: Path, lot_de_quatre: Path, rang_fautif: int, position: str
) -> None:
    """Regle des fabriques, point 4 : la cible en TETE **et** en QUEUE.

    Une cible au milieu demasque un appariement fautif ; elle ne demasque pas
    un balayage tronque, qui est un autre mode de panne. Ici la cible est le
    fichier **saute**, et les deux bords mordent differemment :

    * en **tete**, un compteur qui n'avancerait que sur les pages PRODUITES
      partirait a `1` alors que deux fichiers ont ete traverses -- la barre
      accuserait un retard permanent ;
    * en **queue**, ce meme compteur n'atteindrait **jamais** son total : la
      barre resterait a 3/4 sur un travail termine, ce qui est le mensonge
      symetrique de celui qu'`EmetteurProgression` interdit en completant a
      100 %.

    **Les deux bords n'attendent PAS la meme suite, et c'est le finding `A1`
    qui les separe.** Un saut en tete tombe avant qu'aucune page n'existe :
    son jalon est **differe**, pas perdu -- le premier jalon vaut donc `2`,
    les deux fichiers traverses d'un coup, et non `1`. Un saut en queue tombe
    apres, la suite est deja ouverte, il l'avance normalement. Dans les deux
    cas la barre **atteint son total** : c'est ce que le report ne casse pas.
    """
    fautif = sorted(lot_de_quatre.iterdir())[rang_fautif]
    fautif.write_bytes(b"ceci n'est pas une image")

    vus: list = []
    rapport = scan_ingest.ingest_scan_lot(projet, lot_de_quatre, dpi=DPI,
                                          rappel_progression=_jalons(vus))

    assert fautif.name in rapport.skipped_files, (
        f"le banc n'a pas rendu le fichier de {position} illisible")
    faites = [f for f, _ in vus]
    attendu = [2, 3, 4] if position == "tete" else [1, 2, 3, 4]
    assert faites == attendu, (
        f"un saut en {position} ne doit ni faire caler ni faire reculer le "
        f"compte des pages traversees ; vus : {vus!r}")
    assert {t for _, t in vus} == {4}
    assert faites[-1] == 4, (
        "quel que soit le bord, la barre atteint son total sur un travail "
        f"termine ; vus : {vus!r}")


# --- `AR3` : sans rappel, RIEN ne change -----------------------------------


def test_SANS_rappel_l_ingestion_rend_EXACTEMENT_le_meme_rapport(
    projet: Path, lot_de_quatre: Path, tmp_path: Path
) -> None:
    """L'ajout est pur : deux ingestions comparees sur ce qu'elles RENDENT.

    Comparees sur le document du rapport et non sur l'absence d'exception :
    deux passes qui ne levent ni l'une ni l'autre mais rendent des verdicts
    differents seraient un defaut pire, parce que muet.
    """
    second = tmp_path / "projet2"
    project_layout.ensure_project_layout(second)

    sans = scan_ingest.ingest_scan_lot(projet, lot_de_quatre, dpi=DPI)
    vus: list = []
    avec = scan_ingest.ingest_scan_lot(second, lot_de_quatre, dpi=DPI,
                                       rappel_progression=_jalons(vus))

    assert sans.as_document() == avec.as_document()
    assert vus, "le regime AVEC rappel doit, lui, avoir emis quelque chose"


def test_un_rappel_QUI_LEVE_ne_fait_pas_echouer_l_ingestion(
    projet: Path, lot_de_quatre: Path, tmp_path: Path
) -> None:
    """L'observation ne casse jamais l'observe (`EPIC7-ARB-79`).

    **Le drapeau varie pour de vrai** (finding `A5`) : le meme lot, une fois
    avec un rappel sain et une fois avec un rappel fautif, doit rendre le
    **meme document de rapport**. La redaction precedente promettait cette
    variation dans son docstring et ne jouait que le rappel fautif, en
    n'assertant que `len(rapport.pages) == 4` : un rappel fautif qui aurait
    MODIFIE le rapport sans en changer le cardinal -- un avertissement de plus,
    un `scans_dir` different, un `read_rank` decale -- serait passe vert.
    Comparer les documents, et non les cardinaux, est la meme discipline que
    « on compare des listes de verdicts, jamais des compteurs ».
    """
    def _fautif(faites, total):
        raise RuntimeError("le rappel de l'appelant est casse")

    second = tmp_path / "projet_sain"
    project_layout.ensure_project_layout(second)

    vus: list = []
    sain = scan_ingest.ingest_scan_lot(second, lot_de_quatre, dpi=DPI,
                                       rappel_progression=_jalons(vus))
    casse = scan_ingest.ingest_scan_lot(projet, lot_de_quatre, dpi=DPI,
                                        rappel_progression=_fautif)

    assert casse.as_document() == sain.as_document(), (
        "un rappel qui leve doit rendre EXACTEMENT le meme rapport qu'un "
        "rappel sain, pas seulement le meme nombre de pages")
    assert len(casse.pages) == 4
    assert [f for f, _ in vus] == [1, 2, 3, 4], (
        "le regime SAIN doit, lui, avoir emis la suite complete -- sans quoi "
        "les deux branches du drapeau seraient muettes et l'egalite "
        "ci-dessus ne mesurerait rien")


# --- la chaine complete : la calibration branche les DEUX phases -----------


def test_calibrer_la_chaine_PASSE_le_rappel_a_L_INGESTION_AUSSI(
    projet: Path, lot_de_quatre: Path, monkeypatch
) -> None:
    """Le maillon que `CALIB-N1` nommait : la phase la plus longue emet.

    La detection est doublee -- une calibration reelle sur une mire est le
    sujet d'un autre banc -- et elle **leve**, pour que le banc constate ce qui
    a ete emis AVANT elle, c'est-a-dire par la seule ingestion.
    """
    def _detection(project_dir, report, *, dpi=None, rappel_progression=None):
        raise scan_detection.ScanDetectionError("arret volontaire du banc")

    monkeypatch.setattr(scan_detection, "detect_lot_pages", _detection)
    monkeypatch.setattr(scan_calibrate.scan_detection, "detect_lot_pages",
                        _detection)

    vus: list = []
    with pytest.raises(scan_detection.ScanDetectionError):
        scan_calibrate.calibrer_la_chaine(projet, lot_de_quatre, dpi=DPI,
                                          rappel_progression=_jalons(vus))
    assert [f for f, _ in vus] == [1, 2, 3, 4], (
        "avant le correctif, la calibration n'emettait AUCUN jalon tant que la "
        f"detection n'avait pas commence ; vus : {vus!r}")


def test_les_DEUX_phases_emettent_et_la_seconde_REPART_a_un(
    projet: Path, lot_de_quatre: Path
) -> None:
    """La frontiere de phase est **observable**, et c'est ce qui la rend cablable.

    Les deux phases portent le meme cardinal (la detection parcourt les pages
    que l'ingestion a produites), donc la seconde suite repart a `1` sur le
    meme total. Ce jalon non progressif est le seul signal que le relais TUI a
    pour changer de lot -- le mesurer ici, dans le coeur, est ce qui empeche
    d'en faire une supposition cote ecran.
    """
    vus: list = []
    rapport = scan_ingest.ingest_scan_lot(projet, lot_de_quatre, dpi=DPI,
                                          rappel_progression=_jalons(vus))
    coupe = len(vus)
    scan_detection.detect_lot_pages(projet, rapport, dpi=DPI,
                                    rappel_progression=_jalons(vus))

    ingestion, detection = vus[:coupe], vus[coupe:]
    assert [f for f, _ in ingestion] == [1, 2, 3, 4]
    assert [f for f, _ in detection] == [1, 2, 3, 4]
    assert detection[0][0] <= ingestion[-1][0], (
        "le premier jalon de la detection doit etre NON PROGRESSIF par rapport "
        "au dernier de l'ingestion : c'est la frontiere de phase")


# --- la NATURE de la source : des PDF, pas seulement des images ------------
#
# Ce qui suit ferme le trou de fabrique que la revue du canal a nomme : aucun
# banc de la vague n'ingerait un PDF, alors que la mire du depot en est un.
# Cinq mutants y avaient survecu -- deux branches entieres du canal
# (`PDF SEUL`, `SELECTION`), le cardinal des pages, et trois lignes de
# comptage du PDF multipage.


def test_la_MIRE_REELLE_est_un_PDF_et_son_ingestion_EMET(projet: Path) -> None:
    """La branche `PDF SEUL`, mesuree sur le raster de TERRAIN du depot.

    C'est le chemin exact du grief d'Egan : une mire designee seule, un PDF
    d'une page, la phase la plus longue de la calibration. Une fabrique de
    synthese mesure la synthese ; c'est ce fichier-la qui a produit la panne,
    donc c'est lui qui la mesure.

    Le mutant qu'il tue -- `emetteur=_emetteur([copied])` remplace par `None`
    dans la branche PDF de `ingest_scan_lot` -- laissait la barre **immobile
    pendant toute la rasterisation**, la seule progression visible venant
    ensuite de la detection.
    """
    if not MIRE_REELLE.exists():
        pytest.skip(f"raster de terrain absent : {MIRE_REELLE}")

    vus: list = []
    rapport = scan_ingest.ingest_scan_lot(projet, MIRE_REELLE, dpi=300,
                                          rappel_progression=_jalons(vus))
    assert len(rapport.pages) == 1
    assert vus == [(1, 1)], (
        "la branche PDF SEUL doit emettre son jalon ; sans lui la barre reste "
        f"immobile toute la rasterisation ; vus : {vus!r}")


def test_un_PDF_REEL_de_SEPT_pages_emet_UN_JALON_PAR_PAGE(projet: Path) -> None:
    """Le PDF de terrain multipage : la SUITE, pas un jalon.

    Trois mutants tombent sur cette seule suite :

    * l'emetteur de la branche PDF seul rendu `None` -- plus aucun jalon ;
    * `emettre(deja_faites + page_index + 1)` reduit a `+ page_index` -- le
      premier jalon vaut `0`, il est absorbe, et la suite s'arrete a `6/7` :
      une page sautee en silence, precisement ce que le parametre
      `deja_faites` existe pour fermer ;
    * le cardinal mesure sur le nombre de FICHIERS -- le total vaudrait `1`,
      tous les jalons seraient rabattus a `(1, 1)` et la barre se completerait
      des la premiere page.
    """
    if not SCAN_REEL_7_PAGES.exists():
        pytest.skip(f"raster de terrain absent : {SCAN_REEL_7_PAGES}")

    vus: list = []
    rapport = scan_ingest.ingest_scan_lot(projet, SCAN_REEL_7_PAGES, dpi=300,
                                          rappel_progression=_jalons(vus))
    assert len(rapport.pages) == 7
    assert [f for f, _ in vus] == [1, 2, 3, 4, 5, 6, 7], (
        f"un jalon par page rasterisee, dans l'ordre ; vus : {vus!r}")
    assert {t for _, t in vus} == {7}, (
        "le total est le cardinal des PAGES du PDF, pas celui des fichiers ; "
        f"vus : {vus!r}")


@pytest.mark.parametrize("position", ["tete", "queue"])
def test_un_PDF_MULTIPAGE_a_CHAQUE_BORD_d_un_lot_MIXTE(
    projet: Path, tmp_path: Path, position: str
) -> None:
    """Regle des fabriques, point 4, appliquee a la NATURE de la source.

    Le lot melange deux images et un PDF de trois pages -- cinq pages pour
    trois fichiers, donc un cardinal qui ne peut pas etre confondu avec un
    compte de fichiers. Le PDF est place en **tete** puis en **queue**, et les
    deux bords mordent sur des lignes differentes :

    * en **tete**, le PDF ouvre la suite (`1, 2, 3`) et ce sont les images qui
      la continuent : c'est `faites += len(pages_du_pdf)` qui est mesure. Le
      reduire a `+= 1` fait repartir les images de `2`, sous la ligne d'eau, et
      la barre se **fige a 3/5** sur un travail termine ;
    * en **queue**, les images ouvrent la suite (`1, 2`) et le PDF la
      continue : c'est `deja_faites + page_index + 1` qui est mesure. Le
      reduire a `+ page_index` fait redemarrer le PDF a `2`, deja emis, donc
      une page **disparait** et la barre s'arrete a `4/5`.

    Les deux ensemble tiennent aussi le cardinal : mesure sur les fichiers, il
    vaudrait `3` et la barre se completerait aux deux tiers du travail.
    """
    dossier = tmp_path / f"mixte_{position}"
    if position == "tete":
        _pdf(dossier / "1_doc.pdf", 3)
        _page(dossier / "2_page.tiff", 60)
        _page(dossier / "3_page.tiff", 190)
    else:
        _page(dossier / "1_page.tiff", 60)
        _page(dossier / "2_page.tiff", 190)
        _pdf(dossier / "3_doc.pdf", 3)

    vus: list = []
    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=DPI,
                                          rappel_progression=_jalons(vus))

    assert len(rapport.pages) == 5, (
        "trois fichiers dont un PDF de trois pages font CINQ pages ; "
        f"rendu : {len(rapport.pages)}")
    assert rapport.skipped_files == ()
    assert [f for f, _ in vus] == [1, 2, 3, 4, 5], (
        f"PDF en {position} : la suite doit rester dense et atteindre son "
        f"total ; vus : {vus!r}")
    assert {t for _, t in vus} == {5}, (
        "le total compte les PAGES et non les FICHIERS -- trois fichiers, cinq "
        f"pages ; vus : {vus!r}")


def test_une_SELECTION_MELANGEE_emet_elle_aussi(
    projet: Path, tmp_path: Path
) -> None:
    """La branche `SELECTION`, que rien ne tenait.

    Une selection multiple d'explorateur -- une liste de chemins -- est *un*
    lot (`EPIC7-ARB-88`), et son canal passe par une ligne distincte de celle
    du dossier. Le mutant qui la rend muette (`emetteur=_emetteur(files)`
    remplace par `None`) survivait a la vague entiere : la branche dossier
    etait la seule tenue.

    Les fichiers sont pris dans **deux dossiers differents**, ce qu'un dossier
    ne peut pas produire -- sinon le banc mesurerait la branche dossier sous
    un autre nom.
    """
    gauche = tmp_path / "gauche"
    droite = tmp_path / "droite"
    selection = [
        _page(gauche / "1_page.tiff", 40),
        _pdf(droite / "2_doc.pdf", 2),
        _page(gauche / "3_page.tiff", 200),
    ]

    vus: list = []
    rapport = scan_ingest.ingest_scan_lot(projet, selection, dpi=DPI,
                                          rappel_progression=_jalons(vus))

    assert len(rapport.pages) == 4
    assert [f for f, _ in vus] == [1, 2, 3, 4], (
        "une selection multiple doit emettre comme un dossier ; "
        f"vus : {vus!r}")
    assert {t for _, t in vus} == {4}, (
        "trois fichiers dont un PDF de deux pages font QUATRE pages ; "
        f"vus : {vus!r}")


# --- le PDF PARTIELLEMENT rasterisable : ni gel, ni saut -------------------


def test_un_PDF_PARTIELLEMENT_rasterisable_ne_FIGE_pas_la_barre(
    projet: Path, tmp_path: Path
) -> None:
    """Finding `A2` : le seul regime ou la branche `except` du PDF est atteinte
    alors que des jalons sont **deja partis**.

    Un PDF qui **s'ouvre** est compte par `_cardinal_des_pages` pour toutes ses
    pages ; si l'une d'elles ne se rasterise pas, `_render_pdf_page` leve et le
    fichier entier est saute. Le compteur retombait alors a `deja_faites + 1`,
    c'est-a-dire **sous** le dernier jalon emis, et tout ce qui suivait
    passait sous la ligne d'eau d'`EmetteurProgression`.

    Mesure du defaut, avant correctif, sur exactement ce lot : cardinal `13`,
    jalons `(1,13)` a `(9,13)` **puis plus rien**, alors que trois images
    etaient encore ingerees derriere. A l'ecran : une barre figee a 69 % sur un
    travail termine.

    Le banc mesure les deux moities que le finding oppose :

    * la barre **atteint son total** -- c'est ce que le comptage sur les pages
      traversees garantit et qu'il ne faut pas casser ;
    * les trois images qui suivent le PDF **emettent chacune leur jalon** --
      c'est ce que le rattrapage au cardinal rend possible.
    """
    dossier = tmp_path / "mixte_mutile"
    _pdf(dossier / "1_doc.pdf", 10, page_fautive=9)
    for rang, valeur in enumerate((50, 130, 210), start=2):
        _page(dossier / f"{rang}_page.tiff", valeur)

    assert scan_ingest._cardinal_des_pages(
        sorted(dossier.iterdir())) == 13, (
        "le PDF s'OUVRE : le cardinal doit le compter pour ses dix pages, "
        "sinon le banc mesure un autre regime que le finding")

    vus: list = []
    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=DPI,
                                          rappel_progression=_jalons(vus))

    assert rapport.skipped_files == ("1_doc.pdf",)
    assert len(rapport.pages) == 3
    faites = [f for f, _ in vus]
    assert faites[-1] == 13 and {t for _, t in vus} == {13}, (
        "la barre doit atteindre son total : un PDF mutile au milieu d'un lot "
        f"ne doit pas la figer ; vus : {vus!r}")
    assert faites == sorted(faites) and len(set(faites)) == len(faites)
    # Les trois images d'apres le PDF : chacune son jalon, aucune absorbee.
    assert [f for f in faites if f > 9] == [11, 12, 13], (
        "les trois images qui suivent le PDF mutile doivent chacune emettre ; "
        f"avant le correctif elles etaient toutes absorbees ; vus : {vus!r}")


def test_un_PDF_ILLISIBLE_ne_compte_QUE_POUR_UNE_page(
    projet: Path, tmp_path: Path
) -> None:
    """Le symetrique du banc precedent, et il tient l'autre moitie du rattrapage.

    Un PDF qui ne s'ouvre **pas** n'a pas de pages a compter : le cardinal lui
    en donne une, le compteur doit lui en donner une aussi. C'est ce qui
    interdit de « corriger » le finding `A2` en rattrapant toujours au
    cardinal du document -- il n'y en a pas -- ou en n'avancant pas du tout.

    Le PDF est en **tete**, donc son jalon est differe (finding `A1`) : la
    suite s'ouvre a `2`, les deux fichiers traverses d'un coup, et atteint son
    total `3`. Un rattrapage a `0` la ferait finir a `2/3` sur un travail
    termine.
    """
    dossier = tmp_path / "pdf_casse"
    dossier.mkdir(parents=True)
    (dossier / "1_doc.pdf").write_bytes(b"%PDF-1.4 ceci n'est pas un PDF")
    _page(dossier / "2_page.tiff", 70)
    _page(dossier / "3_page.tiff", 180)

    vus: list = []
    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=DPI,
                                          rappel_progression=_jalons(vus))

    assert rapport.skipped_files == ("1_doc.pdf",)
    assert len(rapport.pages) == 2
    assert [f for f, _ in vus] == [2, 3], (
        "un PDF illisible en tete compte pour UNE page traversee, differee "
        f"jusqu'a la premiere page produite ; vus : {vus!r}")
    assert {t for _, t in vus} == {3}


# --- `A1` : un refus d'ingestion ne produit AUCUNE progression -------------


def test_un_dossier_ENTIEREMENT_ILLISIBLE_n_emet_AUCUN_jalon(
    projet: Path, tmp_path: Path
) -> None:
    """AC 9.3 de la story 11.4e (`EPIC7-ARB-79`), au regime qui la mettait en
    defaut.

    Le banc qui tenait cet AC jouait un dossier **sans aucune page** : le refus
    y tombe avant l'emetteur, donc il ne mesurait pas l'emetteur. Le regime
    « fichiers presents mais TOUS illisibles » n'etait mesure nulle part, et
    c'est celui-la qui produisait de la progression avant un refus.

    Mesure du defaut, avant correctif, sur exactement ce dossier :
    `(1, 2)` puis `(2, 2)` -- une barre a **100 %**, un lot annonce a deux
    pages qui ne seront jamais detectees -- **puis** `EmptyScanLotError`.
    """
    dossier = tmp_path / "illisibles"
    dossier.mkdir(parents=True)
    (dossier / "1_page.tiff").write_bytes(b"ceci n'est pas une image")
    (dossier / "2_page.tiff").write_bytes(b"celle-la non plus")

    vus: list = []
    with pytest.raises(scan_ingest.EmptyScanLotError):
        scan_ingest.ingest_scan_lot(projet, dossier, dpi=DPI,
                                    rappel_progression=_jalons(vus))
    assert vus == [], (
        "un refus d'ingestion ne produit AUCUNE progression (AC 9.3) ; "
        f"vus : {vus!r}")


def test_un_dossier_PARTIELLEMENT_lisible_atteint_QUAND_MEME_son_total(
    projet: Path, tmp_path: Path
) -> None:
    """L'autre moitie du drapeau, et elle est ce qui interdit la correction
    facile du finding `A1`.

    Differer les jalons **n'est pas** revenir au comptage des pages produites,
    que le commit `f41a22a79` a explicitement ecarte : « un compte sur les
    seules pages produites n'atteindrait jamais son total quand la derniere
    planche est illisible ». Ce banc joue ce cas-la -- la derniere planche est
    illisible -- et exige `4/4`.

    Les deux bancs se lisent ensemble : entierement illisible n'emet rien,
    partiellement lisible atteint son total. Un banc qui ne jouerait que l'un
    des deux laisserait passer la correction qui casse l'autre.
    """
    dossier = tmp_path / "partiel"
    for rang, valeur in enumerate((40, 120, 200), start=1):
        _page(dossier / f"{rang}_page.tiff", valeur)
    (dossier / "4_page.tiff").write_bytes(b"la derniere planche est illisible")

    vus: list = []
    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=DPI,
                                          rappel_progression=_jalons(vus))

    assert rapport.skipped_files == ("4_page.tiff",)
    assert [f for f, _ in vus] == [1, 2, 3, 4], (
        "un dossier dont la derniere planche est illisible doit quand meme "
        f"atteindre son total ; vus : {vus!r}")


def test_un_PDF_partiellement_rasterisable_SEUL_emet_encore_avant_son_refus(
    projet: Path, tmp_path: Path
) -> None:
    """**Tolerance documentee**, mesuree plutot que tue.

    `_ingest_pdf` emet un jalon apres chaque page **reellement rasterisee** :
    ces jalons partent donc avant que l'echec de la page suivante ne soit
    connu. Un dossier ne portant qu'un PDF partiellement rasterisable emet
    ainsi de la progression avant son `EmptyScanLotError`, ce qu'AC 9.3
    interdit a la lettre.

    Ce qui n'est **pas** tolere, et que la garde ferme : que le jalon de
    **rattrapage** complete la barre a `3/3` juste avant le refus. La suite
    s'arrete a `2/3`.

    La fermer entierement demanderait de differer TOUS les jalons d'un PDF
    jusqu'a sa derniere page -- c'est-a-dire de rendre muette la phase la plus
    longue de la calibration, la dette `CALIB-N1` exactement. Le banc fixe donc
    le regime au lieu de le taire : s'il rougit, c'est que quelqu'un a change
    l'arbitrage sans le dire.
    """
    dossier = tmp_path / "pdf_mutile_seul"
    _pdf(dossier / "doc.pdf", 3, page_fautive=2)

    vus: list = []
    with pytest.raises(scan_ingest.EmptyScanLotError):
        scan_ingest.ingest_scan_lot(projet, dossier, dpi=DPI,
                                    rappel_progression=_jalons(vus))
    assert vus == [(1, 3), (2, 3)], (
        "tolerance documentee : les deux pages reellement rasterisees ont "
        "emis, mais le rattrapage ne complete PAS la barre avant le refus ; "
        f"vus : {vus!r}")


def test_calibrer_la_chaine_qui_REFUSE_a_l_ingestion_n_emet_AUCUN_jalon(
    projet: Path, tmp_path: Path
) -> None:
    """L'AC 9.3 sur sa vraie surface : la CHAINE, pas seulement l'ingestion.

    `calibrer_la_chaine` passe le meme rappel a ses deux phases et laisse
    remonter le refus de la premiere. Le banc mesure donc ce que l'operateur
    voit : une calibration lancee sur une pile entierement illisible ne doit
    faire bouger la barre **d'aucun cran** avant son message d'erreur.

    Il complete `test_calibrer_la_chaine_PASSE_le_rappel_a_L_INGESTION_AUSSI`,
    qui mesure le sens inverse -- que le rappel atteint bien l'ingestion. Les
    deux ensemble font varier le drapeau : un canal qui emettrait toujours et
    un canal qui n'emettrait jamais rougissent chacun sur l'un des deux.
    """
    dossier = tmp_path / "pile_illisible"
    dossier.mkdir(parents=True)
    (dossier / "1_page.tiff").write_bytes(b"ceci n'est pas une image")
    (dossier / "2_page.tiff").write_bytes(b"celle-la non plus")

    vus: list = []
    with pytest.raises(scan_ingest.ScanIngestError):
        scan_calibrate.calibrer_la_chaine(projet, dossier, dpi=DPI,
                                          rappel_progression=_jalons(vus))
    assert vus == [], (
        "une calibration refusee a l'ingestion ne produit AUCUNE progression "
        f"(AC 9.3) ; vus : {vus!r}")


def test_DEUX_PDF_dont_le_premier_est_mutile_la_barre_ATTEINT_son_total(
    projet: Path, tmp_path: Path
) -> None:
    """Le regime que la revue decrivait comme un « saut » : il n'y en a pas.

    La revue annoncait, sur un PDF partiellement rasterise, « une barre figee,
    puis un saut de 35 % a 87 % ». La moitie « figee » est reproduite et
    fermee ; le **saut**, lui, n'existe pas dans ce regime, et la mesure le
    dit. Deux PDF, le premier mutile (huit pages, la sixieme irrasterisable),
    le second sain (quinze pages), cardinal `23` :

    | regime | jalons | fin |
    |---|---|---|
    | avant correctif | `1..16`, denses | **70 %** sur un travail termine |
    | apres correctif | `1..5`, puis `9..23` | **100 %** |

    Avant le correctif la barre ne saute pas : elle **avance normalement et
    s'arrete a 70 %**, parce que les jalons du second PDF repartent sous la
    ligne d'eau et sont absorbes jusqu'a la rattraper. Ce qui se voit a
    l'ecran est un plafond, pas un bond.

    **Apres le correctif il y a bien un bond, et il est LEGITIME** : `5 -> 9`,
    soit les trois pages du PDF mutile que personne n'a rasterisees mais que le
    cardinal a comptees. C'est le prix, assume, de lire les deux comptes sur la
    meme echelle -- le meme prix qu'une image illisible fait payer pour une
    page. Le banc le fixe pour qu'il ne soit pas pris un jour pour le defaut
    qu'il remplace.
    """
    dossier = tmp_path / "deux_pdf"
    _pdf(dossier / "1_mutile.pdf", 8, page_fautive=5)
    _pdf(dossier / "2_sain.pdf", 15)

    vus: list = []
    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=DPI,
                                          rappel_progression=_jalons(vus))

    assert rapport.skipped_files == ("1_mutile.pdf",)
    assert len(rapport.pages) == 15
    faites = [f for f, _ in vus]
    assert {t for _, t in vus} == {23}
    assert faites == [1, 2, 3, 4, 5] + list(range(9, 24)), (
        "cinq pages rasterisees, un rattrapage de trois pages jamais "
        "atteintes, puis le second PDF jusqu'au total ; avant le correctif la "
        f"suite s'arretait a 16/23 ; vus : {vus!r}")
