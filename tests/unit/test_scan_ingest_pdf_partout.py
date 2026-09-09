# -*- coding: utf-8 -*-
"""`EPIC11-ARB-157` -- le PDF est une source de pages PARTOUT.

**Ce banc et lui seul mesure le lot du coeur de la vague Scan.** La regle de
decoupage du depot est stricte et payee trois fois : aucun lot ne partage un
fichier de banc avec un autre. `git add -N` et `git commit -- <chemins>`
protegent par FICHIER, jamais a l'interieur d'un fichier.

**Ce que le defaut etait, mesure au produit avant d'etre corrige ici.** Sur le
MEME `ma-planche.pdf`, dans le MEME ecran de depot : le valider au curseur
passait, le **cocher** a l'`Espace` puis valider etait refuse. Egan avait coche
-- c'est le geste que la ligne de raccourcis met en avant. La cause tenait a
l'ordre de deux gestes : `_normaliser_la_selection` refusait les non-images
**avant** que `_reconnaitre_la_source` ne reduise une selection d'un seul
element a son chemin unique.

**Regle des fabriques** (`CLAUDE.md`), appliquee a ses trois points :

1. **trois elements distinguables au moins**, jamais un remplissage uniforme :
   les PDF de ce banc portent des cardinaux de pages DIFFERENTS (1, 3, 2), et
   les images des valeurs de gris differentes -- une permutation ne se voit que
   si les elements different ;
2. **la cible n'est pas en premiere position** ;
3. **trois elements et la cible AU MILIEU des qu'une boucle compte** -- et la
   position se verifie sur la liste que le CODE parcourt (`_discover_folder_pages`
   et `_ordonner_une_selection`, qui **trient** par nom normalise), jamais sur
   celle que la fabrique ecrit. C'est le finding le plus grave de la revue de la
   vague 3, et il se rejoue exactement ici : nommer les fichiers dans l'ordre du
   tri ferait passer une fabrique pour une mesure de position.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdfcanvas

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import scan_ingest
from mixed_media_utility.io import project_layout


# --- fabriques -------------------------------------------------------------


def ecrire_image(chemin: Path, *, valeur: int) -> Path:
    """Une page image, **distinguable** par sa valeur de gris."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(chemin), np.full((40, 60, 3), valeur, dtype=np.uint8))
    return chemin


def ecrire_pdf(chemin: Path, *, pages: int) -> Path:
    """Un PDF de `pages` pages, **distinguable** par son cardinal."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    canevas = pdfcanvas.Canvas(str(chemin), pagesize=A4)
    for rang in range(pages):
        canevas.setFillColorRGB(1, 0, 0)
        canevas.rect(100, 400 + rang, 300, 300, stroke=0, fill=1)
        canevas.showPage()
    canevas.save()
    return chemin


@pytest.fixture
def projet(tmp_path: Path) -> Path:
    dossier = tmp_path / "projet"
    project_layout.ensure_project_layout(dossier)
    return dossier


@pytest.fixture
def vrac(tmp_path: Path) -> Path:
    """Un dossier « en vrac » : trois PDF et deux images, la CIBLE au milieu.

    Les noms sont choisis pour que l'ordre du TRI (nom normalise) differe de
    l'ordre de creation : le PDF de trois pages s'appelle `b_...` et se
    retrouve donc **au milieu** de la liste que le code parcourt, alors qu'il
    est ecrit en dernier ici.
    """
    dossier = tmp_path / "vrac"
    ecrire_pdf(dossier / "c_une_page.pdf", pages=1)      # 3e au tri, 1 page
    ecrire_image(dossier / "a_image.png", valeur=10)     # 1er au tri
    ecrire_image(dossier / "d_image.tif", valeur=200)    # 4e au tri
    ecrire_pdf(dossier / "b_cible.pdf", pages=3)         # 2e au tri : LA CIBLE
    ecrire_pdf(dossier / "e_deux_pages.pdf", pages=2)    # 5e au tri
    return dossier


# --- la table unique des fichiers porteurs de pages ------------------------


def test_la_table_des_pages_est_l_union_EXACTE_des_deux_tables() -> None:
    """`PAGE_EXTENSIONS` n'est pas une troisieme redaction, c'est l'union.

    **Ensemble EXACT et non appartenance** : « le `.pdf` est dedans » ne
    mesurerait pas qu'un format n'y a pas ete ajoute en douce, et c'est
    exactement la moitie qui manquait.
    """
    assert set(scan_ingest.PAGE_EXTENSIONS) == (
        set(scan_ingest.IMAGE_EXTENSIONS) | set(scan_ingest.PDF_EXTENSIONS)
    )
    # Et l'union ne perd rien : autant d'entrees que les deux tables reunies,
    # donc aucune collision silencieuse entre elles.
    assert len(scan_ingest.PAGE_EXTENSIONS) == (
        len(scan_ingest.IMAGE_EXTENSIONS) + len(scan_ingest.PDF_EXTENSIONS)
    )


# --- 1. un PDF COCHE SEUL : le defaut d'Egan, a la racine -------------------


def test_un_PDF_coche_SEUL_est_la_meme_chose_que_le_meme_PDF_au_curseur(
    projet: Path, tmp_path: Path
) -> None:
    """Le defaut exact d'Egan : « J'avais selectionne un seul pdf pourtant ».

    Une selection d'un element et le chemin nu sont **la meme intention**. Le
    banc mesure qu'elles rendent la meme mesure, pas seulement qu'aucune ne
    leve : deux formes qui ne levent pas mais divergent sur le cardinal
    seraient un defaut pire, parce que muet.
    """
    pdf = ecrire_pdf(tmp_path / "source" / "ma-planche.pdf", pages=3)

    au_curseur = scan_ingest.mesurer_la_source(pdf)
    coche_seul = scan_ingest.mesurer_la_source([pdf])

    assert coche_seul == au_curseur
    assert coche_seul.forme == scan_ingest.FORME_PDF
    assert coche_seul.cardinal == 3


# --- 2. un dossier de PDF --------------------------------------------------


def test_un_dossier_de_PDF_s_ingere_et_ses_PAGES_comptent(
    projet: Path, tmp_path: Path
) -> None:
    """Un dossier de trois PDF de 1, 3 et 2 pages fait **six** pages.

    Le cardinal d'un dossier melange compte des PAGES et non des fichiers :
    trois fichiers, six pages. Compter les fichiers rendrait `3`, ce qui est
    exactement le « compte faux presente comme une mesure » que le depot
    interdit ailleurs.
    """
    dossier = tmp_path / "que_des_pdf"
    ecrire_pdf(dossier / "c_une.pdf", pages=1)
    ecrire_pdf(dossier / "b_trois.pdf", pages=3)
    ecrire_pdf(dossier / "a_deux.pdf", pages=2)

    mesure = scan_ingest.mesurer_la_source(dossier)
    assert mesure.cardinal == 6

    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=300)
    assert len(rapport.pages) == 6


def test_le_PDF_du_MILIEU_du_tri_contribue_ses_pages_a_sa_place(
    projet: Path, vrac: Path
) -> None:
    """La CIBLE est au milieu de la liste que le CODE parcourt.

    `b_cible.pdf` est le **second** des cinq au tri par nom normalise, et il
    porte trois pages. Ses trois pages doivent donc occuper les rangs 1, 2 et 3
    -- apres l'unique page de `a_image.png`, avant celle de `c_trois_pages.pdf`.

    **Ce test mesure la terminaison de boucle autant que l'appariement.** Un
    `break` a la place d'un `continue` sur la premiere page-fichier, ou un
    `find` qui rendrait toujours le premier element, laisserait la cible en
    place s'il n'y avait que deux elements ou si elle etait en tete. Elle est au
    milieu, et l'ordre du tri differe de l'ordre de creation.
    """
    pages, _ignores = scan_ingest._discover_folder_pages(vrac)
    assert [c.name for c in pages] == [
        "a_image.png", "b_cible.pdf", "c_une_page.pdf",
        "d_image.tif", "e_deux_pages.pdf",
    ]

    rapport = scan_ingest.ingest_scan_lot(projet, vrac, dpi=300)
    # 1 + 3 + 1 + 1 + 2 = 8 pages
    assert len(rapport.pages) == 8
    formats = [p.scan_input_format for p in rapport.pages]
    assert formats == ["png", "pdf", "pdf", "pdf", "pdf", "tif", "pdf", "pdf"]
    # Les rangs de lecture sont GLOBAUX et contigus : un PDF au milieu ne
    # redemarre pas la numerotation a zero.
    assert [p.read_rank for p in rapport.pages] == list(range(8))


def test_un_dossier_MELANGE_n_ignore_plus_AUCUN_PDF(vrac: Path) -> None:
    """L'ensemble des fichiers ignores est EXACTEMENT vide.

    C'est le cas le plus couteux des cinq, et celui que personne n'aurait
    signale : un dossier de dix planches dont deux sont des PDF s'ingerait
    **sans erreur** en annoncant huit pages. Une assertion d'appartenance
    (« le PDF n'est pas dans les ignores ») laisserait passer toute divergence
    supplementaire ; l'ensemble exact mesure l'absence ET son unicite.
    """
    _pages, ignores = scan_ingest._discover_folder_pages(vrac)
    assert set(ignores) == set()


# --- 3. une selection en vrac ----------------------------------------------


def test_une_SELECTION_melangee_de_PDF_et_d_images_est_UN_lot(
    projet: Path, vrac: Path
) -> None:
    """« tout en vrac » (Egan) : trois PDF et deux images coches ensemble.

    La selection est passee dans un ordre DELIBEREMENT faux -- l'ordre d'un
    glisser-deposer -- et le lot doit sortir dans l'ordre du tri, pas dans
    celui-la.
    """
    desordre = [
        vrac / "e_deux_pages.pdf",
        vrac / "b_cible.pdf",
        vrac / "a_image.png",
        vrac / "d_image.tif",
        vrac / "c_une_page.pdf",
    ]
    mesure = scan_ingest.mesurer_la_source(desordre)
    assert mesure.forme == scan_ingest.FORME_SELECTION
    assert mesure.cardinal == 8

    rapport = scan_ingest.ingest_scan_lot(projet, desordre, dpi=300)
    assert len(rapport.pages) == 8
    assert [p.scan_input_format for p in rapport.pages] == [
        "png", "pdf", "pdf", "pdf", "pdf", "tif", "pdf", "pdf",
    ]


def test_une_selection_refuse_TOUJOURS_un_dossier_et_l_ensemble_est_EXACT(
    tmp_path: Path
) -> None:
    """Ce que l'elargissement ne doit PAS emporter avec lui.

    Un dossier dans une selection reste refuse -- il est deja une forme
    d'entree a lui seul --, et le refus doit nommer **exactement** ce qu'il
    refuse : ni le PDF ni l'image qui l'accompagnent, seulement le dossier.
    """
    ecrire_image(tmp_path / "vrac" / "a.png", valeur=10)
    ecrire_pdf(tmp_path / "vrac" / "b.pdf", pages=2)
    (tmp_path / "vrac" / "c_dossier").mkdir()

    with pytest.raises(scan_ingest.UnsupportedScanInputError) as refus:
        scan_ingest.mesurer_la_source([
            tmp_path / "vrac" / "a.png",
            tmp_path / "vrac" / "c_dossier",
            tmp_path / "vrac" / "b.pdf",
        ])
    motif = str(refus.value)
    assert "c_dossier" in motif
    assert "a.png" not in motif and "b.pdf" not in motif


def test_un_dossier_SANS_aucune_page_refuse_en_nommant_les_DEUX_familles(
    tmp_path: Path
) -> None:
    """Le refus d'un dossier vide doit citer les PDF, pas seulement les images.

    Le message disait « extensions reconnues: .png, .jpg, ... » et n'y mettait
    pas le `.pdf` : un operateur dont le dossier ne portait que des PDF y
    lisait, litteralement, que le PDF n'etait pas reconnu.
    """
    dossier = tmp_path / "rien"
    dossier.mkdir()
    (dossier / "notes.txt").write_text("rien a ingerer", encoding="utf-8")

    with pytest.raises(scan_ingest.EmptyScanLotError) as refus:
        scan_ingest.mesurer_la_source(dossier)
    for extension in scan_ingest.PAGE_EXTENSIONS:
        assert extension in str(refus.value)


# --- les deux proprietes que la CAMPAGNE a trouvees non mesurees -----------


def test_le_dpi_d_un_dossier_MELANGE_retient_le_PLUS_BAS_des_deux_natures(
    projet: Path, tmp_path: Path
) -> None:
    """Mutant `M6` : `_measure_page_file_dpi` cesse de dispatcher vers le PDF.

    **Il a SURVECU a la premiere campagne**, et c'est le survivant qui coutait
    le plus cher : sans le dispatch, un PDF passe a `_measure_file_dpi`, qui ne
    sait lire que des images, rend `None`, et **disparait du `min`**. Un dossier
    melangeant un PDF a basse resolution et des TIFF a haute annonce alors la
    HAUTE -- le « faux succes » que l'AC 7 nomme, revenu par la porte du
    melange. La propriete etait ecrite au source, et rien ne la mesurait.

    La fabrique porte les deux natures a des resolutions DIFFERENTES, ce qui
    est la seule facon de voir laquelle est retenue : deux natures a la meme
    resolution rendraient le meme dpi avec ou sans dispatch.
    """
    dossier = tmp_path / "melange_de_dpi"
    # Une image a 600 dpi : le dpi se pose dans les metadonnees PNG.
    from PIL import Image
    dossier.mkdir(parents=True, exist_ok=True)
    haute = Image.fromarray(np.full((80, 60, 3), 180, dtype=np.uint8))
    haute.save(dossier / "a_image.png", dpi=(600, 600))

    # Un PDF dont l'image embarquee est a ~72 dpi : une grande page, une
    # petite image.
    from reportlab.lib.utils import ImageReader
    petite = tmp_path / "petite.png"
    Image.fromarray(np.full((60, 60, 3), 90, dtype=np.uint8)).save(petite)
    canevas = pdfcanvas.Canvas(str(dossier / "b_basse.pdf"), pagesize=A4)
    canevas.drawImage(ImageReader(str(petite)), 0, 0, width=A4[0], height=A4[1])
    canevas.showPage()
    canevas.save()

    dpi_du_pdf = scan_ingest.mesurer_la_source(dossier / "b_basse.pdf").dpi
    dpi_de_l_image = scan_ingest.mesurer_la_source(dossier / "a_image.png").dpi
    assert dpi_du_pdf is not None and dpi_de_l_image is not None
    assert dpi_du_pdf < dpi_de_l_image, (
        "la fabrique doit porter DEUX resolutions distinguables")

    # Le dossier retient la plus basse des deux natures reunies.
    assert scan_ingest.mesurer_la_source(dossier).dpi == min(
        dpi_du_pdf, dpi_de_l_image)


def test_un_PDF_ILLISIBLE_dans_un_dossier_est_SAUTE_et_n_emporte_pas_les_autres(
    projet: Path, tmp_path: Path
) -> None:
    """Mutant `M8` : le PDF illisible fait tomber le lot au lieu d'etre saute.

    **Il a SURVECU a la premiere campagne.** La politique est ecrite dans le
    docstring d'`_ingest_files` -- « dans un dossier de dix planches, un PDF
    chiffre ne doit pas emporter les neuf autres » -- et rien ne la mesurait.

    Trois fichiers et **le fautif AU MILIEU** de l'ordre que le code parcourt :
    en tete, un `raise` non rattrape serait indiscernable d'un lot vide ; en
    queue, il serait indiscernable d'un `break` apres le dernier bon fichier.

    L'ensemble des sautes est mesure EXACTEMENT : « le PDF fautif est dans les
    sautes » laisserait passer une image saute au passage.
    """
    dossier = tmp_path / "un_pdf_casse"
    ecrire_image(dossier / "a_bonne.png", valeur=40)
    (dossier / "b_cassee.pdf").write_bytes(b"%PDF-1.4\nceci n'est pas un PDF")
    ecrire_image(dossier / "c_bonne.tif", valeur=210)

    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=300)

    assert set(rapport.skipped_files) == {"b_cassee.pdf"}
    assert len(rapport.pages) == 2
    assert [p.scan_input_format for p in rapport.pages] == ["png", "tif"]
    # Les rangs de lecture restent CONTIGUS : un saut ne doit pas laisser un
    # trou, sans quoi le rang cesse d'etre un rang de lecture.
    assert [p.read_rank for p in rapport.pages] == [0, 1]
    assert "UNREADABLE_FILE_SKIPPED" in rapport.warnings


# --- ce que la REVUE EN TROIS COUCHES a trouve, et les trois l'ont trouve ---


def test_la_MESURE_accepte_EXACTEMENT_ce_que_l_INGESTION_accepte(
    projet: Path, tmp_path: Path
) -> None:
    """Le defaut le plus grave de la vague, trouve par les TROIS couches.

    `_cardinal_des_pages` rattrapait `(UnsupportedScanInputError, ValueError)`.
    Or `_open_pdf` ne leve **que** `PdfIngestError` (chiffre, corrompu) ou
    `EmptyScanLotError` (zero page), et **aucune des deux n'est sous-classe
    d'`UnsupportedScanInputError`** : les trois descendent directement de
    `ScanIngestError`. La branche de secours documentee -- « un PDF qu'on ne
    sait pas ouvrir compte pour une page plutot que zero » -- n'etait donc
    atteinte par rien.

    **C'est le defaut d'Egan REINTRODUIT par le correctif d'Egan**, et c'est ce
    qui le rend grave. Mesure au produit avant correction, sur le meme dossier :

        ingest_scan_lot   -> OK, 2 pages, saute b_cassee.pdf
        mesurer_le_dpi    -> OK
        mesurer_la_source -> LEVE PdfIngestError
        designer (ECRAN)  -> LEVE PdfIngestError

    `atelier_scan._valider_l_explorateur` rend ce refus **verbatim** et ne pose
    pas la source : un dossier de dix planches dont une seule est un PDF
    illisible devenait indesignable a l'ecran, alors que le coeur en ingere
    neuf. C'est mot pour mot « un format que le coeur ingere et que l'ecran
    refuse est un blocage » -- l'AC que la frontiere de cette vague existe pour
    tenir, et qu'elle ne voyait pas parce qu'elle n'exerce que des EXTENSIONS,
    jamais un CONTENU.

    Le banc mesure donc l'accord des DEUX chemins sur la meme entree, ce qui
    est plus fort que « la mesure ne leve plus » : deux chemins qui ne levent
    ni l'un ni l'autre mais comptent differemment seraient un defaut pire,
    parce que muet.
    """
    dossier = tmp_path / "un_pdf_casse"
    ecrire_image(dossier / "a_bonne.png", valeur=40)
    (dossier / "b_cassee.pdf").write_bytes(b"%PDF-1.4\nceci n'est pas un PDF")
    ecrire_image(dossier / "c_bonne.tif", valeur=210)

    # La mesure ne leve plus...
    mesure = scan_ingest.mesurer_la_source(dossier)
    # ...et elle COMPTE le PDF illisible pour une page, comme son docstring le
    # promet : deux images plus une page de secours.
    assert mesure.cardinal == 3
    assert mesure.fichiers == 3

    # Et l'ingestion, elle, en saute une : les deux chemins ne mentent pas,
    # ils disent deux choses vraies. Le cardinal annonce ce qui sera TENTE, le
    # rapport dit ce qui a ete LU.
    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=300)
    assert len(rapport.pages) == 2
    assert set(rapport.skipped_files) == {"b_cassee.pdf"}

    # Le volet qui compte pour l'ecran : la designation ne leve pas.
    from mixed_media_utility.tui import atelier_scan
    source = atelier_scan.designer(dossier)
    assert source.cardinal == 3


def test_la_MESURE_d_une_SELECTION_accepte_aussi_le_PDF_illisible(
    tmp_path: Path
) -> None:
    """Le volet symetrique sur la quatrieme forme, mesure a part.

    La selection passe par le meme `_cardinal_des_pages`, mais par un autre
    chemin d'entree : un correctif pose sur la seule branche du dossier
    laisserait la selection lever. C'est exactement l'asymetrie qui a produit
    le defaut d'origine -- `_ingest_files` avait recu la garde, son jumeau
    `_cardinal_des_pages` ne l'avait pas.
    """
    dossier = tmp_path / "vrac_casse"
    a = ecrire_image(dossier / "a_bonne.png", valeur=40)
    casse = dossier / "b_cassee.pdf"
    casse.write_bytes(b"%PDF-1.4\nceci n'est pas un PDF")
    c = ecrire_image(dossier / "c_bonne.tif", valeur=210)

    mesure = scan_ingest.mesurer_la_source([a, casse, c])
    assert mesure.forme == scan_ingest.FORME_SELECTION
    assert mesure.cardinal == 3


def test_un_PDF_HORS_DU_PROJET_n_est_pas_declare_ILLISIBLE(
    projet: Path, tmp_path: Path, monkeypatch
) -> None:
    """Un defaut de CHEMIN presente comme un defaut de CONTENU.

    `path.relative_to(base_dir)` etait **dans** le `try` de la branche PDF,
    alors que la branche image le fait **hors** du `try`. `ValueError` etant
    dans le tuple rattrape, un PDF parfaitement lisible dont le chemin ne se
    relativise pas partait dans `skipped_files` avec `UNREADABLE_FILE_SKIPPED`.

    Le depot exige qu'un saut soit **nomme** ; celui-la etait nomme FAUX. Et il
    est atteignable : la CLI ne resout pas `project_dir` (`cli.py`), tandis
    qu'un chemin colle depuis un gestionnaire de fichiers est absolu.

    Le banc mesure que la panne de chemin **remonte** au lieu d'etre deguisee,
    et que le message nomme le CHEMIN. Une panne franche vaut mieux qu'un saut
    silencieux mal attribue -- c'est la regle du depot, et c'est ce que la
    branche image fait deja.
    """
    dossier = tmp_path / "hors_projet"
    ecrire_pdf(dossier / "a_lisible.pdf", pages=2)

    # `base_dir` qui ne contient pas le fichier : la relativisation echoue.
    with pytest.raises(ValueError) as refus:
        scan_ingest._ingest_files([dossier / "a_lisible.pdf"],
                                  base_dir=tmp_path / "ailleurs", dpi=300)
    assert "subpath" in str(refus.value) or "relative" in str(refus.value)


def test_les_pages_d_un_PDF_gardent_leur_index_DANS_LEUR_document(
    projet: Path, vrac: Path
) -> None:
    """L'appariement positionnel -- la classe de defaut la plus payee du depot.

    `_ingest_pdf` affirme : « L'index de page n'est pas perdu : il reste dans
    le `PageLocator`, qui est le seul endroit ou il veut dire quelque chose. »
    **Rien ne le mesurait.** Mutant joue par la couche 1 :
    `PageLocator(source, page_index)` -> `PageLocator(source, rang_initial +
    page_index)`. Verdict : 71 tests verts, **survivant**.

    Ce que le mutant produit : les pages du PDF pointent vers les mauvais index
    de leur document, les premieres rendent SILENCIEUSEMENT les mauvais pixels,
    et la derniere leve « Echec du rendu de la page N » a la detection -- bien
    apres un rapport d'ingestion vert.

    Les deux bancs voisins ne pouvaient pas le voir : `read_rank` reste
    contigu, et `scan_input_format` vaut `"pdf"` pour toutes les pages d'un
    PDF. Le seul champ discriminant est le LOCATOR, et c'est lui qu'on mesure
    ici -- en ensemble EXACT, source et index ensemble, sur le vrac dont la
    cible est au milieu du tri.
    """
    rapport = scan_ingest.ingest_scan_lot(projet, vrac, dpi=300)
    locators = [(Path(p.locator.source_path).name, p.locator.page_index)
                for p in rapport.pages]
    assert locators == [
        ("a_image.png", None),
        ("b_cible.pdf", 0), ("b_cible.pdf", 1), ("b_cible.pdf", 2),
        ("c_une_page.pdf", 0),
        ("d_image.tif", None),
        ("e_deux_pages.pdf", 0), ("e_deux_pages.pdf", 1),
    ]
