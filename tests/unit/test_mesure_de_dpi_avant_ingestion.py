# -*- coding: utf-8 -*-
"""Story 11.4b, lot S5 -- la mesure de dpi AVANT ingestion (AC 7).

Ce que ce banc mesure, et ce qu'aucun autre ne mesurait. `_measure_pages_dpi`
existe depuis la story 5.1 et elle est **privee** : ses trois appelants exigent
deja un dpi **et** ont deja copie les fichiers dans le projet (fait F5 de la
11.4b). Rien ne pouvait donc afficher la mesure **avant** la saisie, et
`EPIC11-ARB-38` -- « la valeur mesuree est affichee a cote du champ, **des le
depot** » -- etait intenable.

`scan_ingest.mesurer_le_dpi` ferme ce trou, et ce banc l'appelle **comme la 11.5
l'appellera** : sur une selection que l'operatrice vient de deposer, dans un
projet qui n'a encore rien vu.

**Les trois pieges nommes de l'AC, chacun avec son test.**

1. **AC 7.3, verbatim du coeur** : la mesure « est confrontee au DPI declare,
   **jamais substituee** ». Le banc le mesure aux deux etages : sur le
   comportement (le rapport d'ingestion garde le dpi declare) et surtout en
   **frontiere de source** -- aucun chemin d'ingestion ne fait circuler une
   mesure vers un parametre de dpi. La frontiere ne depend d'aucun chemin
   exerce, c'est ce qui la rend capable de voir une substitution posee sur une
   branche qu'aucun test ne deroule ;
2. **AC 7.4** : les **quatre** formes d'entree de l'ingestion (`EPIC7-ARB-88`)
   ou un refus **nomme** -- jamais un `TypeError` nu. Piege deja paye a
   `scan_detect.py:250-260`, ou coercer `scan_path` en `Path` detruisait la
   quatrieme forme et remplacait un motif lisible par un message Python
   affiche sur une carte de tache ;
3. **AC 7.5, regle des fabriques** : **trois** fichiers, deux dpi differents,
   et le divergent **au milieu** -- ni en premiere position (mutant « rendre le
   premier »), ni en derniere (mutant `continue` -> `break`, mesure du lot S2
   le 2026-08-30 : sur une fabrique de deux ou la cible est seconde, seconde
   **est** derniere et les deux formes sont indiscernables).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import scan_ingest  # noqa: E402
from mixed_media_utility.io import project_layout  # noqa: E402

MODULE_INGESTION = REPO_ROOT / "src" / "mixed_media_utility" / "scan_ingest.py"

#: Le dpi que declarent les pages **saines** de la fabrique.
DPI_SAIN = 600

#: Le dpi **divergent**, celui qu'un scanner en auto-fit ecrirait. Il est plus
#: bas que le sain a dessein : c'est la plus basse qui borne la finesse
#: reellement disponible, et c'est elle que `_measure_pages_dpi` retient.
DPI_DIVERGENT = 72

#: Le rang du fichier divergent dans le lot : **le deuxieme des trois**. Ni le
#: premier, ni le dernier -- voir le point 3 du docstring de module.
RANG_DIVERGENT = 1


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


def _page(chemin: Path, *, dpi: int | None, teinte: int) -> Path:
    """Une page PNG qui **declare** son dpi, ou qui n'en declare aucun.

    PNG et non TIFF : `_measure_file_dpi` lit `Image.info["dpi"]`, que Pillow ne
    rend pas d'un TIFF ecrit par `cv2.imwrite` puis resauve. Le PNG stocke sa
    resolution en pixels par **metre** et en entier, donc 72 dpi ressort a
    72,009 -- d'ou les comparaisons approchees plus bas, exactement comme le
    fait deja `test_scan_ingest.py`.

    La teinte differe d'une page a l'autre : deux pages identiques rendraient
    toute permutation invisible, et c'est le premier point de la regle des
    fabriques.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(chemin), np.full((40, 60, 3), teinte, dtype=np.uint8))
    if dpi is not None:
        Image.open(chemin).save(chemin, dpi=(dpi, dpi))
    return chemin


def _lot_de_trois_pages(racine: Path, *, divergent: bool = True) -> list[Path]:
    """Trois pages distinguables, la divergente **au milieu**.

    Regle des fabriques, ses trois points a la fois : trois elements, des
    valeurs differentes (teintes et dpi), et la cible ailleurs qu'en premiere
    **et** qu'en derniere position.

    `divergent=False` est le **volet symetrique** : les trois pages declarent
    alors le meme dpi, et la mesure doit rendre celui-la. Sans lui, une
    implementation qui rendrait toujours `DPI_DIVERGENT` serait verte.
    """
    dpis = [DPI_SAIN, DPI_SAIN, DPI_SAIN]
    if divergent:
        dpis[RANG_DIVERGENT] = DPI_DIVERGENT
    return [
        _page(racine / f"page_{rang + 1:02d}.png", dpi=dpi, teinte=10 + 40 * rang)
        for rang, dpi in enumerate(dpis)
    ]


def _pdf_avec_image_embarquee(chemin: Path) -> Path:
    """Un PDF portant une image embarquee, donc une resolution mesurable.

    C'est la troisieme forme d'entree de l'ingestion, et la seule dont la
    mesure ne passe pas par `_measure_pages_dpi` : un PDF ne declare pas un dpi
    par page comme un TIFF, il porte des images dont chacune a la sienne.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    photo = chemin.parent / "photo.jpg"
    Image.fromarray(
        np.random.default_rng(0).integers(0, 255, (400, 600, 3), dtype=np.uint8)
    ).save(photo, quality=80)
    canvas = pdfcanvas.Canvas(str(chemin), pagesize=A4)
    canvas.drawImage(ImageReader(str(photo)), 50, 400, width=300, height=200)
    canvas.showPage()
    canvas.save()
    return chemin


def _empreinte_de_l_arborescence(racine: Path) -> set:
    """Chemin, taille et date de chaque fichier sous `racine`.

    Ni un cardinal ni une liste de noms : une mesure qui reecrirait un fichier
    en place ne changerait ni l'un ni l'autre.

    Elle est prise sur le **bac a sable entier** et non sur le seul dossier
    designe -- voir le motif mesure dans
    :func:`test_le_point_d_entree_de_dpi_n_ECRIT_RIEN`.
    """
    if not racine.exists():
        return set()
    return {
        (chemin.relative_to(racine).as_posix(),
         chemin.stat().st_size, chemin.stat().st_mtime_ns)
        for chemin in sorted(racine.rglob("*")) if chemin.is_file()
    }


# ---------------------------------------------------------------------------
# AC 7.1 -- le point d'entree n'ecrit rien, ne copie rien, n'exige aucun dpi
# ---------------------------------------------------------------------------


def test_le_point_d_entree_de_dpi_n_ECRIT_RIEN(tmp_path: Path) -> None:
    """AC 7.1 : sans rien copier, sans rien ingerer, sans exiger un dpi.

    `EPIC11-ARB-38` pose que la valeur mesuree s'affiche « des le depot » et
    que « elle **n'est pas preremplie**. Le champ reste requis, et vide ». La
    moitie qui appartient a cette story est celle-ci : le point d'entree
    **rend** la mesure et n'ecrit nulle part. Le champ est de la 11.5.

    La mesure porte sur **tout** le bac a sable, et pas sur le seul dossier
    source ni sur le seul dossier projet. La difference n'est pas de la
    prudence : elle a ete **mesuree** pendant la campagne d'injection du lot
    S5. Le mutant « le point d'entree ingere au lieu de lire » a d'abord
    **SURVECU** a une version de ce test qui ne regardait que ces deux
    dossiers -- une materialisation posee **a cote** de la source (le regime
    exact de `_materialise_folder`, qui ecrit dans un dossier de lot qu'il cree
    lui-meme) n'y laissait aucune trace. Une copie posee n'importe ou est une
    copie posee, et c'est le contrat entier qui tombe : la fonction existe pour
    montrer une valeur **avant** que l'operatrice n'ait decide d'ingerer quoi
    que ce soit.
    """
    source = tmp_path / "depot-de-l-operatrice"
    _lot_de_trois_pages(source)
    projet = tmp_path / "projet"
    project_layout.ensure_project_layout(projet)

    avant = _empreinte_de_l_arborescence(tmp_path)
    # Temoin : l'empreinte porte de la matiere, et elle couvre bien les deux
    # dossiers. Sans lui, deux ensembles vides seraient egaux et ce test serait
    # vert et creux.
    assert len(avant) >= 3, sorted(avant)
    assert sum(1 for chemin, _taille, _date in avant
               if chemin.startswith("depot-de-l-operatrice/")) == 3

    # **Aucun dpi n'est passe** : c'est la signature meme du point d'entree.
    mesure = scan_ingest.mesurer_le_dpi(source)

    assert mesure == pytest.approx(DPI_DIVERGENT, abs=0.1)
    assert _empreinte_de_l_arborescence(tmp_path) == avant
    # Et aucun dossier neuf n'est apparu : une empreinte de fichiers ne verrait
    # pas un dossier de lot cree puis laisse vide.
    assert sorted(chemin.name for chemin in tmp_path.iterdir()) == [
        "depot-de-l-operatrice", "projet"]


def test_la_mesure_n_exige_AUCUN_dpi_la_ou_l_ingestion_en_exige_un(tmp_path) -> None:
    """AC 7.1, volet symetrique : l'ingestion, elle, refuse toujours sans dpi.

    Sans ce volet, « la mesure n'exige aucun dpi » ne se distingue pas de « le
    dpi n'a jamais ete obligatoire nulle part ». C'est `InvalidScanDpiError` qui
    porte la difference, et le contrat de la 5.1 est explicite : « Le DPI n'a
    pas de defaut ici, contrairement au chemin POC ».
    """
    source = tmp_path / "depot"
    _lot_de_trois_pages(source)
    projet = tmp_path / "projet"
    project_layout.ensure_project_layout(projet)

    assert scan_ingest.mesurer_le_dpi(source) is not None
    with pytest.raises(scan_ingest.InvalidScanDpiError):
        scan_ingest.ingest_scan_lot(projet, source, dpi=None)


# ---------------------------------------------------------------------------
# AC 7.2 et AC 7.5 -- toutes les pages, la divergente au milieu
# ---------------------------------------------------------------------------


def test_la_mesure_porte_sur_TOUTES_les_pages_et_la_divergente_est_AU_MILIEU(
        tmp_path: Path) -> None:
    """AC 7.2 et AC 7.5 : « sur **toutes** les pages, pas la premiere ».

    Trois mutants tombent sur cette seule fabrique, et c'est pourquoi la
    divergente est au milieu :

    * `paths[0]` ou « le premier qui declare quelque chose » -- la premiere
      page declare `DPI_SAIN` ;
    * `max` au lieu de `min` -- le maximum vaut `DPI_SAIN` ;
    * une boucle qui s'arrete au premier ecart (`break`) -- il y a une page
      saine **apres** la divergente, donc l'arret se voit.
    """
    source = tmp_path / "depot"
    pages = _lot_de_trois_pages(source)
    # La fabrique dit bien ce qu'elle pretend dire : la divergente n'est ni
    # premiere ni derniere, et deux dpi differents coexistent.
    assert RANG_DIVERGENT not in (0, len(pages) - 1)

    assert scan_ingest.mesurer_le_dpi(source) == pytest.approx(
        DPI_DIVERGENT, abs=0.1)


def test_un_lot_HOMOGENE_rend_le_dpi_qu_il_declare(tmp_path: Path) -> None:
    """AC 7.2, volet symetrique du test precedent.

    Sans lui, une fonction qui rendrait toujours la plus basse valeur possible
    -- ou une constante -- passerait le test ci-dessus.
    """
    source = tmp_path / "depot"
    _lot_de_trois_pages(source, divergent=False)

    assert scan_ingest.mesurer_le_dpi(source) == pytest.approx(DPI_SAIN, abs=0.1)


def test_aucune_page_ne_declarant_de_dpi_rend_None_et_jamais_une_valeur_devinee(
        tmp_path: Path) -> None:
    """AC 7.2 : « rend `None` quand aucune mesure n'est possible ».

    Jamais une valeur devinee, jamais celle d'un voisin, jamais zero -- qui
    s'afficherait « 0 ppp », c'est-a-dire un mensonge et non une absence. C'est
    le meme interdit que celui d'`EPIC7-ARB-67` sur le temps restant.
    """
    source = tmp_path / "depot"
    for rang in range(3):
        _page(source / f"page_{rang + 1:02d}.png", dpi=None, teinte=10 + 40 * rang)

    assert scan_ingest.mesurer_le_dpi(source) is None


def test_une_SEULE_page_declarant_un_dpi_suffit_a_le_rendre(tmp_path: Path) -> None:
    """AC 7.2 : le lot mixte -- deux pages muettes, une qui parle, au milieu.

    Une implementation qui exigerait que **toutes** les pages declarent leur
    resolution rendrait `None` ici, et l'operatrice ne verrait rien alors que
    la mesure existe. Le contrat de `_measure_pages_dpi` est « les valeurs
    lues », pas « toutes les valeurs ».
    """
    source = tmp_path / "depot"
    for rang in range(3):
        _page(source / f"page_{rang + 1:02d}.png",
              dpi=DPI_DIVERGENT if rang == RANG_DIVERGENT else None,
              teinte=10 + 40 * rang)

    assert scan_ingest.mesurer_le_dpi(source) == pytest.approx(
        DPI_DIVERGENT, abs=0.1)


# ---------------------------------------------------------------------------
# AC 7.4 -- les quatre formes d'entree, ou un refus NOMME
# ---------------------------------------------------------------------------


def test_les_QUATRE_formes_d_entree_de_l_ingestion_sont_mesurees(tmp_path) -> None:
    """AC 7.4 : dossier, image seule, PDF, **et** sequence de chemins.

    La quatrieme est celle qui casse (`EPIC7-ARB-88`) : c'est le geste reel
    d'Egan -- glisser plusieurs TIFF depuis un explorateur --, et `Path(tuple)`
    y leve un `TypeError` nu. Les quatre sont donc mesurees dans le meme test,
    pour qu'aucune ne puisse etre oubliee en silence.

    La selection porte les **trois** pages, la divergente au milieu : une
    selection qui ne mesurerait que son premier element rendrait `DPI_SAIN`.
    """
    dossier = tmp_path / "depot"
    pages = _lot_de_trois_pages(dossier)
    pdf = _pdf_avec_image_embarquee(tmp_path / "documents" / "planches.pdf")

    par_dossier = scan_ingest.mesurer_le_dpi(dossier)
    par_selection = scan_ingest.mesurer_le_dpi(list(pages))
    par_selection_tuple = scan_ingest.mesurer_le_dpi(tuple(pages))
    par_image = scan_ingest.mesurer_le_dpi(pages[0])
    par_pdf = scan_ingest.mesurer_le_dpi(pdf)

    # Dossier et selection des memes fichiers disent la **meme** chose : c'est
    # l'invariant de la 5.1 (« les quatre produisent la meme sequence ordonnee
    # de pages »), porte jusqu'a la mesure.
    assert par_dossier == pytest.approx(DPI_DIVERGENT, abs=0.1)
    assert par_selection == par_dossier
    assert par_selection_tuple == par_dossier
    # L'image seule est la premiere page, qui est SAINE : la selection ne
    # rendrait pas cette valeur-la, et c'est ce qui prouve que la mesure d'une
    # selection porte bien sur ses trois elements.
    assert par_image == pytest.approx(DPI_SAIN, abs=0.1)
    assert par_image != par_selection
    # Le PDF est mesure et non ecarte : `_measure_pdf_dpi` lit le dpi des
    # images **embarquees**, jamais une valeur derivee d'une taille de media
    # box. Voir le docstring de `mesurer_le_dpi` pour l'ecart assume a Q2.
    assert par_pdf is not None and par_pdf > 0


def test_une_liste_d_UN_SEUL_chemin_mesure_comme_le_meme_chemin_seul(tmp_path):
    """AC 7.4 : la reduction de selection est celle de l'ingestion, pas une autre.

    `ingest_scan_lot` reduit une selection d'un element au cas a un chemin,
    parce qu'« un seul chemin dans une liste est exactement le cas a un
    chemin ». La mesure suit **la meme** regle, appelee et non recopiee : une
    seconde redaction de la reduction ferait diverger la mesure affichee avant
    le depot de celle que le rapport inscrira apres.

    **Le second volet disait l'inverse jusqu'au 2026-09-01, et il mesurait un
    DEFAUT en le prenant pour une limite.** Il asserait qu'« un PDF dans une
    liste d'un element est refuse -- par la mesure comme par l'ingestion » :
    c'etait vrai, `_normaliser_la_selection` refusant tout non-image **avant**
    la reduction, et c'est precisement ce qui a bloque Egan. Il avait coche un
    seul PDF a l'`Espace` ; le meme PDF valide au curseur passait.
    `EPIC11-ARB-157` renverse la regle -- « on doit tout accepter : pdf seul,
    dans un dossier, avec des images ... tout en vrac ».

    Ce que le volet mesure desormais est la MEME propriete que le premier, sur
    l'autre nature de page : une liste d'un element et le chemin nu sont la
    meme intention, pour un PDF comme pour une image. C'est plus fort que « ca
    ne leve plus » -- deux formes qui ne levent pas mais divergent sur le dpi
    seraient un defaut pire, parce que muet.
    """
    dossier = tmp_path / "depot"
    pages = _lot_de_trois_pages(dossier)
    projet = tmp_path / "projet"
    project_layout.ensure_project_layout(projet)

    assert scan_ingest.mesurer_le_dpi([pages[0]]) == scan_ingest.mesurer_le_dpi(
        pages[0])

    pdf = _pdf_avec_image_embarquee(tmp_path / "documents" / "planches.pdf")
    assert scan_ingest.mesurer_le_dpi([pdf]) == scan_ingest.mesurer_le_dpi(pdf)

    # **La comparaison porte sur les LOCATORS, pas sur un cardinal.** La
    # premiere redaction comparait `len(pages) == len(pages)` sur un PDF d'UNE
    # page, donc `1 == 1` : un mutant qui n'ingererait que la premiere page
    # d'un PDF dans la forme selection y survivait. Releve par deux couches de
    # la revue, sur la propriete centrale d'`EPIC11-ARB-157`.
    #
    # Les locators portent la source ET l'index de page : c'est le seul couple
    # qui distingue « le meme PDF lu deux fois » de « deux lectures qui se
    # ressemblent ». La fabrique reste celle de ce banc, mono-page ; ce qui la
    # rend suffisante ici est que la propriete mesuree est l'IDENTITE des deux
    # formes, pas le cardinal -- et deux bancs voisins portent deja des PDF de
    # deux et trois pages pour le cardinal.
    def _lus(source, ou):
        rapport = scan_ingest.ingest_scan_lot(ou, source, dpi=DPI_SAIN)
        return [(Path(p.locator.source_path).name, p.locator.page_index,
                 p.scan_input_format) for p in rapport.pages]

    assert _lus([pdf], projet) == _lus(pdf, tmp_path / "temoin")


@pytest.mark.parametrize("entree", [42, None, {"chemin": "a.png"}, object()])
def test_une_forme_NON_MESURABLE_est_refusee_NOMMEMENT_jamais_en_TypeError(
        entree) -> None:
    """AC 7.4 : « jamais un `TypeError` nu ».

    Le piege est deja paye (`scan_detect.py:250-260`) : un `TypeError` remonte
    hors de toute hierarchie nommee, s'affiche tel quel sur une carte de tache,
    et ne dit pas a l'operatrice ce qu'elle doit corriger. Le refus doit
    appartenir a `ScanIngestError` -- la base que tout appelant rattrape deja --
    et **nommer** ce qu'il attendait.
    """
    with pytest.raises(scan_ingest.ScanIngestError) as refus:
        scan_ingest.mesurer_le_dpi(entree)
    assert not isinstance(refus.value, TypeError)
    assert "Forme d'entree non mesurable" in str(refus.value)


def test_une_SEQUENCE_de_non_chemins_est_refusee_NOMMEMENT(tmp_path) -> None:
    """AC 7.4 : la sequence est reconnue comme telle, puis refusee sur son contenu.

    `bytes` et un tuple d'entiers sont des `Sequence` : ils traversent le test
    de forme et vont mourir dans `Path(entree)`. C'est la moitie du piege que
    le test precedent ne couvre pas -- la forme est bonne, le contenu ne l'est
    pas.
    """
    for entree in ((1, 2, 3), b"pas-des-chemins"):
        with pytest.raises(scan_ingest.ScanIngestError) as refus:
            scan_ingest.mesurer_le_dpi(entree)
        assert not isinstance(refus.value, TypeError)


def test_les_refus_de_chemin_sont_ceux_de_l_INGESTION_et_pas_d_autres(tmp_path):
    """AC 7.4 : chemin absent, extension inconnue, dossier sans page image.

    Les trois refus sont ceux que l'ingestion leverait sur la meme entree, avec
    le meme type. C'est ce qui permet a la 11.5 de n'ecrire qu'une seule
    traduction de refus : deux vocabulaires voisins seraient deux contrats
    melanges.

    Le dossier sans page image rend un **refus** et non `None`. Les deux ne
    disent pas la meme chose : `None` veut dire « des pages, aucune resolution
    declaree », et les confondre ferait afficher « dpi non mesurable » sur un
    dossier qui ne sera de toute facon jamais ingere.
    """
    with pytest.raises(scan_ingest.UnsupportedScanInputError):
        scan_ingest.mesurer_le_dpi(tmp_path / "nulle-part")

    texte = tmp_path / "notes.txt"
    texte.write_text("pas une planche", encoding="utf-8")
    with pytest.raises(scan_ingest.UnsupportedScanInputError):
        scan_ingest.mesurer_le_dpi(texte)

    vide = tmp_path / "sans-image"
    vide.mkdir()
    (vide / "notes.txt").write_text("rien a mesurer", encoding="utf-8")
    with pytest.raises(scan_ingest.EmptyScanLotError):
        scan_ingest.mesurer_le_dpi(vide)


# ---------------------------------------------------------------------------
# AC 7.3 -- la mesure est informative, JAMAIS substituee
# ---------------------------------------------------------------------------


def test_la_mesure_de_dpi_n_est_JAMAIS_substituee_au_dpi_declare(tmp_path) -> None:
    """AC 7.3, verbatim du coeur (`_measure_file_dpi`, `EPIC11-ARB-38`) :

    « Mesure **informative** : elle est confrontee au DPI declare, **jamais
    substituee**. »

    Moitie comportementale de l'AC. L'ingestion voit une divergence franche --
    600 declares, 72 mesures -- et doit garder 600 de bout en bout : dans le
    rapport, dans l'avertissement, et dans ce que le point d'entree de mesure
    rend **a cote** sans jamais s'y substituer.

    Un scanner en auto-fit ecrit une resolution qui ne correspond pas a
    l'echelle reelle de la page : substituer la mesure au dpi declare
    fausserait toute la geometrie aval **sans erreur visible**, c'est-a-dire le
    risque R8.
    """
    source = tmp_path / "depot"
    _lot_de_trois_pages(source, divergent=False)
    for chemin in sorted(source.glob("*.png")):
        Image.open(chemin).save(chemin, dpi=(DPI_DIVERGENT, DPI_DIVERGENT))
    projet = tmp_path / "projet"
    project_layout.ensure_project_layout(projet)

    mesure = scan_ingest.mesurer_le_dpi(source)
    rapport = scan_ingest.ingest_scan_lot(projet, source, dpi=DPI_SAIN)

    assert mesure == pytest.approx(DPI_DIVERGENT, abs=0.1)
    assert rapport.declared_dpi == DPI_SAIN
    assert rapport.measured_dpi == pytest.approx(DPI_DIVERGENT, abs=0.1)
    # La divergence est **dite**, pas resolue en silence.
    assert "DPI_DECLARED_DIFFERS_FROM_FILE" in rapport.warnings
    # Et le rapport ecrit sur le disque dit la meme chose que l'objet : un
    # document qui porterait 72 la ou l'objet porte 600 serait deux verites.
    ecrit = scan_ingest.report_document(rapport)
    assert ecrit["declared_dpi"] == DPI_SAIN
    assert ecrit["measured_dpi"] == pytest.approx(DPI_DIVERGENT, abs=0.1)


def _noms_portes(noeud: ast.AST) -> set:
    """Tous les identifiants et attributs cites dans un sous-arbre."""
    portes = set()
    for enfant in ast.walk(noeud):
        if isinstance(enfant, ast.Name):
            portes.add(enfant.id)
        elif isinstance(enfant, ast.Attribute):
            portes.add(enfant.attr)
    return portes


#: Tout ce qui, dans `scan_ingest.py`, **produit** une mesure. Un flux de l'un
#: d'eux vers un parametre de dpi est la substitution que l'AC 7.3 interdit.
PRODUCTEURS_DE_MESURE = frozenset(
    {"measured", "_measure_pages_dpi", "_measure_pdf_dpi", "_measure_file_dpi",
     "mesurer_le_dpi", "measured_dpi"})

#: Tout ce qui, dans ce module, **consomme** un dpi et decide de la geometrie.
CONSOMMATEURS_DE_DPI = frozenset({"dpi", "scan_dpi", "declared_dpi"})


def test_aucun_chemin_d_INGESTION_ne_se_met_a_UTILISER_la_mesure_comme_dpi():
    """AC 7.3, moitie structurelle -- et c'est elle qui mord.

    Le test comportemental ci-dessus ne voit que le chemin qu'il deroule. Une
    substitution posee sur une **autre** branche -- le PDF, la selection
    multiple, un repli -- lui resterait invisible : c'est litteralement le
    piege de tete de la fiche (« un banc vert ne dit rien de ce qu'il ne
    mesure pas »), et c'est la meme forme de trou que la 11.4b a deja ferme
    par une frontiere AST au lot S1 (le coeur qui imprimait sur `stderr`
    survivait au banc d'execution parce qu'il ne deroulait que le nominal).

    La frontiere balaie **tout** le module et refuse deux gestes :

    1. affecter un consommateur de dpi depuis une mesure
       (`dpi = measured`, `scan_dpi = _measure_pages_dpi(...)`) ;
    2. passer une mesure a un mot-cle de dpi (`dpi=measured`,
       `declared_dpi=mesurer_le_dpi(...)`).

    Elle ne depend d'aucun chemin exerce, donc elle vaut aussi pour les
    branches qu'aucun test ne deroule.
    """
    arbre = ast.parse(MODULE_INGESTION.read_text(encoding="utf-8"))
    fautes = []
    affectations_de_dpi = 0
    mots_cles_de_dpi = 0

    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Assign, ast.AnnAssign)):
            cibles = ([noeud.target] if isinstance(noeud, ast.AnnAssign)
                      else list(noeud.targets))
            vises = {cible.id for cible in cibles if isinstance(cible, ast.Name)}
            if not vises & CONSOMMATEURS_DE_DPI:
                continue
            affectations_de_dpi += 1
            if noeud.value is not None and (
                    _noms_portes(noeud.value) & PRODUCTEURS_DE_MESURE):
                fautes.append(
                    f"ligne {noeud.lineno}: {sorted(vises)} affecte depuis une "
                    "mesure")
        elif isinstance(noeud, ast.Call):
            for mot_cle in noeud.keywords:
                if mot_cle.arg not in CONSOMMATEURS_DE_DPI:
                    continue
                mots_cles_de_dpi += 1
                if _noms_portes(mot_cle.value) & PRODUCTEURS_DE_MESURE:
                    fautes.append(
                        f"ligne {noeud.lineno}: `{mot_cle.arg}=` recoit une mesure")

    assert fautes == [], (
        "la mesure de dpi est INFORMATIVE : elle est confrontee au DPI "
        f"declare, JAMAIS substituee (AC 7.3, `EPIC11-ARB-38`). Vu : {fautes}")
    # **Volet symetrique** : la frontiere doit avoir eu de la matiere a
    # regarder. Sans ces temoins, un module renomme -- ou une lecture qui ne
    # rendrait plus rien -- laisserait la garde verte sans rien mesurer.
    assert affectations_de_dpi >= 2, affectations_de_dpi
    assert mots_cles_de_dpi >= 5, mots_cles_de_dpi


def test_la_frontiere_de_substitution_ROUGIT_sur_une_substitution_posee():
    """AC 7.3, volet symetrique : la garde ci-dessus sait dire non.

    Une frontiere qui ne rougit jamais ne mesure rien. Celle-ci est rejouee sur
    une source ou la substitution est **effectivement** posee -- le mutant
    exact de la campagne d'injection --, et elle doit la voir.
    """
    source = (
        "def ingest_scan_lot(project_dir, scan_path, *, dpi):\n"
        "    measured = _measure_pages_dpi([scan_path])\n"
        "    dpi = measured\n"
        "    return ScanIngestReport(declared_dpi=measured)\n"
    )
    arbre = ast.parse(source)
    fautes = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assign):
            vises = {c.id for c in noeud.targets if isinstance(c, ast.Name)}
            if vises & CONSOMMATEURS_DE_DPI and (
                    _noms_portes(noeud.value) & PRODUCTEURS_DE_MESURE):
                fautes.append(noeud.lineno)
        elif isinstance(noeud, ast.Call):
            for mot_cle in noeud.keywords:
                if mot_cle.arg in CONSOMMATEURS_DE_DPI and (
                        _noms_portes(mot_cle.value) & PRODUCTEURS_DE_MESURE):
                    fautes.append(noeud.lineno)
    assert len(fautes) == 2, fautes
