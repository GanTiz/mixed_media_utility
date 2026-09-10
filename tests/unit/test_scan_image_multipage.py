"""Story 5.31 -- un fichier IMAGE porte N pages, comme un PDF.

Retour de TERRAIN du 2026-09-09, verbatim d'Egan : « sur un tiff de 2 pages,
l'outil ne detecte ainsi qu'une seule page et rend un scan incomplet malgre la
presence de 2 pages ».

Rejoue sur le fichier reel avant correctif -- deux pages `Apple Image Capture`
en 7016 x 5096 -- : `ingest.json` portait `"page_count": 1`, et la commande
rendait **`EXIT=0`**. C'est ce qui fait de ce defaut le plus dangereux des
quatre du jour : il ne rougit pas, il produit un lot **plausible et
incomplet**, et l'ecart ne se voit qu'au montage.

**Ce que ces fabriques NE prouvent pas** : le fichier de terrain n'est pas
verse au depot (consigne d'Egan), donc l'encodage d'ici est celui de Pillow et
non celui d'Apple. Ce que la mesure etablit est STRUCTUREL -- `cv2.imread` rend
une page la ou le fichier en porte N -- et ne depend pas de l'encodeur.
"""

from __future__ import annotations

import ast
import sys
import tokenize
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, TiffImagePlugin

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import scan_ingest  # noqa: E402

MODULE_INGEST = REPO_ROOT / "src" / "mixed_media_utility" / "scan_ingest.py"


def _code_sans_prose(chemin: Path) -> str:
    """Le source d'un module, commentaires et chaines retires.

    Une frontiere negative qui `grep` le fichier entier mesure la PROSE autant
    que le code : le commentaire qui explique pourquoi un appel est interdit la
    ferait rougir, et elle deviendrait une frontiere qu'on desarme en
    reecrivant une phrase.
    """
    with chemin.open("rb") as flux:
        jetons = list(tokenize.tokenize(flux.readline))
    return "\n".join(j.string for j in jetons
                     if j.type not in (tokenize.COMMENT, tokenize.STRING))


# --- fabriques -------------------------------------------------------------
#
# **Trois pages au moins, DISTINGUABLES.** Un remplissage uniforme ne montrerait
# ni une permutation de pages, ni un balayage qui saute la derniere -- deux
# modes de panne differents, et le second ne se demasque qu'avec une cible en
# QUEUE (`CLAUDE.md`, regle des fabriques, point 4).


def couleur_de_page(rang: int) -> tuple[int, int, int]:
    """Un RGB par rang, asymetrique : une permutation de canaux se voit aussi."""
    return (240 - 40 * rang, 120 + 10 * rang, 10 + 25 * rang)


def ecrire_tiff_multipage(chemin: Path, *, pages: int = 3, tailles=None,
                          rgba: bool = False) -> Path:
    """Un TIFF a N pages, une couleur par page.

    `tailles` permet de melanger deliberement deux formats, pour que
    `MIXED_PAGE_DIMENSIONS` ait de quoi se lever.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tailles = tailles or [(24, 32)] * pages
    mode = "RGBA" if rgba else "RGB"

    def _page(rang: int) -> Image.Image:
        hauteur, largeur = tailles[rang]
        canaux = [np.full((hauteur, largeur), v, np.uint8)
                  for v in couleur_de_page(rang)]
        if rgba:
            canaux.append(np.full((hauteur, largeur), 255, np.uint8))
        tableau = np.dstack(canaux)
        # **Un COIN marque, et une page qui n'est pas uniforme** (finding
        # `C2-5`). Avec un `np.full` plat et des assertions qui ne lisent que
        # `tableau[0, 0]`, une page rendue RETOURNEE haut/bas survit a tous les
        # bancs : la regle des fabriques -- « des valeurs differentes, pas un
        # remplissage uniforme » -- vaut pour les PIXELS d'une page autant que
        # pour les elements d'une collection.
        tableau[-1, -1, :3] = (7, 11, 13)
        return Image.fromarray(tableau, mode=mode)

    premiere = _page(0)
    premiere.save(chemin, save_all=True,
                  append_images=[_page(r) for r in range(1, pages)],
                  compression="tiff_lzw", dpi=(600, 600))
    return chemin


def ecrire_tiff_mono(chemin: Path, *, rang: int = 0, dpi=(600, 600)) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tableau = np.dstack([np.full((24, 32), v, np.uint8)
                         for v in couleur_de_page(rang)])
    Image.fromarray(tableau, mode="RGB").save(chemin, dpi=dpi,
                                              compression="tiff_lzw")
    return chemin


def bgr_attendu(rang: int) -> tuple[int, int, int]:
    return tuple(reversed(couleur_de_page(rang)))


@pytest.fixture
def projet(tmp_path: Path) -> Path:
    dossier = tmp_path / "projet"
    dossier.mkdir()
    return dossier


# --- AC1 : les N pages sont ingerees ----------------------------------------


def test_un_TIFF_a_deux_pages_rend_DEUX_pages(projet: Path, tmp_path: Path) -> None:
    """AC1. Le regime exact du fichier de terrain."""
    ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=2)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan.tiff", dpi=600)
    assert len(rapport.pages) == 2


def test_les_pages_sortent_dans_l_ORDRE_du_document(
    projet: Path, tmp_path: Path
) -> None:
    """AC1, non-vacuite. Trois pages distinguables, relues une a une."""
    ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=3)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan.tiff", dpi=600)
    assert [p.read_rank for p in rapport.pages] == [0, 1, 2]
    for rang, page in enumerate(rapport.pages):
        tableau = scan_ingest.load_page_array(projet, page.locator, dpi=600)
        assert tuple(int(v) for v in tableau[0, 0]) == bgr_attendu(rang), (
            f"la page de rang {rang} n'est pas celle que son localisateur "
            "designe")


def test_les_read_rank_se_suivent_dans_un_dossier_MIXTE(
    projet: Path, tmp_path: Path
) -> None:
    """AC1 et AC2. C'est ce qui fait qu'un dossier melange rend UN lot ordonne
    plutot que deux numerotations juxtaposees (`EPIC11-ARB-157`)."""
    dossier = tmp_path / "scan"
    ecrire_tiff_mono(dossier / "a.tiff", rang=0)
    ecrire_tiff_multipage(dossier / "b.tiff", pages=3)
    ecrire_tiff_mono(dossier / "c.tiff", rang=1)
    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=600)
    assert [p.read_rank for p in rapport.pages] == [0, 1, 2, 3, 4]
    assert len(rapport.pages) == 5


# --- AC2 : les trois points jumeaux -----------------------------------------


def test_le_cardinal_compte_les_PAGES_et_non_les_fichiers(tmp_path: Path) -> None:
    """AC2. `_cardinal_des_pages` est ce que l'ecran de depot annonce.

    Trois fichiers dont un TIFF de trois pages font **cinq** pages. Compter les
    fichiers rendrait `3` : un compte faux presente comme une mesure.
    """
    dossier = tmp_path / "scan"
    ecrire_tiff_mono(dossier / "a.tiff")
    ecrire_tiff_multipage(dossier / "b.tiff", pages=3)
    ecrire_tiff_mono(dossier / "c.tiff")
    chemins = sorted(dossier.iterdir())
    assert scan_ingest._cardinal_des_pages(chemins) == 5


def test_le_cardinal_et_l_ingestion_rendent_le_MEME_nombre(
    projet: Path, tmp_path: Path
) -> None:
    """AC2. Les deux comptes se lisent sur la MEME echelle -- c'est une egalite
    qui se TIENT plutot qu'elle ne se suppose. Le depot a deja paye leur
    divergence : un dossier que le coeur ingerait est devenu indesignable."""
    dossier = tmp_path / "scan"
    ecrire_tiff_mono(dossier / "a.tiff")
    ecrire_tiff_multipage(dossier / "b.tiff", pages=4)
    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=600)
    assert scan_ingest._cardinal_des_pages(
        sorted((projet / rapport.scans_dir).iterdir())) == len(rapport.pages)


def test_le_dpi_d_un_multipage_est_le_PLUS_BAS_de_ses_pages(tmp_path: Path) -> None:
    """AC2 (T4). C'est lui qui borne la finesse reellement disponible.

    Le troisieme point jumeau : sans lui, un multipage passait a
    `_measure_file_dpi`, qui ne lit que sa PREMIERE page -- donc une seconde
    page a 150 ppp disparaissait derriere une premiere a 600.
    """
    chemin = tmp_path / "mixte.tiff"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    haute = tmp_path / "haute.tiff"
    basse = tmp_path / "basse.tiff"
    for source, resolution, rang in ((haute, 600, 0), (basse, 150, 1)):
        Image.fromarray(np.dstack([np.full((24, 32), v, np.uint8)
                                   for v in couleur_de_page(rang)]),
                        mode="RGB").save(source, dpi=(resolution, resolution))
    with Image.open(haute) as premiere, Image.open(basse) as seconde:
        premiere.save(chemin, save_all=True, append_images=[seconde])

    # Ce que le fichier porte VRAIMENT, relu -- une fabrique qui ne verifie pas
    # ce qu'elle a produit mesure son intention, pas son resultat.
    declares = []
    with Image.open(chemin) as relu:
        assert relu.n_frames == 2
        for index in range(2):
            relu.seek(index)
            declares.append(float(relu.info["dpi"][0]))
    assert len(set(declares)) == 2, (
        f"la fabrique n'a pas produit deux resolutions : {declares}")

    assert scan_ingest._measure_page_file_dpi(chemin) == pytest.approx(
        min(declares))


# --- AC3 / AC4 : les pixels de la page N, et son index ----------------------


def test_load_page_array_rend_la_page_N_d_une_IMAGE(
    projet: Path, tmp_path: Path
) -> None:
    """AC3. Le piege le plus couteux de la story.

    `load_page_array` dispatchait sur `locator.page_index is None`. Peupler
    l'index (AC4) sans corriger le dispatch enverrait chaque page de TIFF
    multipage dans `_open_pdf` -- une panne FRANCHE, mais loin de sa cause, et
    seulement a la lecture des pixels, c'est-a-dire apres une ingestion qui a
    l'air reussie.
    """
    ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=3)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan.tiff", dpi=600)
    derniere = rapport.pages[-1]
    tableau = scan_ingest.load_page_array(projet, derniere.locator, dpi=600)
    assert tuple(int(v) for v in tableau[0, 0]) == bgr_attendu(2)


def test_le_locator_porte_un_index_sur_un_MULTIPAGE(
    projet: Path, tmp_path: Path
) -> None:
    """AC4. Il valait `null` : deux pages du meme fichier n'avaient rien pour
    se distinguer, ni au rapport, ni au manifest, ni a la relecture."""
    ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=3)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan.tiff", dpi=600)
    assert [p.locator.page_index for p in rapport.pages] == [0, 1, 2]
    assert len({p.locator.source_path for p in rapport.pages}) == 1


def test_le_locator_d_une_image_a_UNE_page_ne_change_PAS(
    projet: Path, tmp_path: Path
) -> None:
    """AC4, symetrique. Rien de ce qui existe ne change de forme.

    `test_a_pdf_locator_carries_an_index_and_a_file_locator_does_not` (5.1)
    tient deja ce contrat ; on le mesure ici aussi, sur le chemin neuf.
    """
    ecrire_tiff_mono(tmp_path / "scan" / "a.tiff")
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    assert rapport.pages[0].locator.page_index is None


# --- AC5 : compter ne coute pas un decodage ---------------------------------


def test_le_cardinal_ne_DECODE_aucun_pixel(tmp_path: Path, monkeypatch) -> None:
    """AC5. Le cardinal lit les repertoires du fichier, pas ses bandes.

    Sans cette frontiere, la voie evidente -- « lire les pages et compter ce
    qu'on obtient » -- ferait payer un decodage complet a chaque affichage de
    l'ecran de depot, sur un dossier qu'on ne fait que regarder.
    """
    appels: list[str] = []
    for nom in ("imread", "imreadmulti"):
        vrai = getattr(cv2, nom)

        def _trace(*args, _nom=nom, _vrai=vrai, **kwargs):
            appels.append(_nom)
            return _vrai(*args, **kwargs)

        monkeypatch.setattr(cv2, nom, _trace)

    ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=3)
    assert scan_ingest._cardinal_des_pages([tmp_path / "scan.tiff"]) == 3
    assert appels == [], f"le cardinal a decode des pixels : {appels}"


# --- AC6 / AC7 : une page illisible ne fait perdre ni le fichier ni le lot ---


def test_un_fichier_ILLISIBLE_compte_pour_UNE_page_et_jamais_zero(
    tmp_path: Path
) -> None:
    """AC2 et AC6, sur le CARDINAL.

    Meme regle que le PDF : il sera saute a l'ingestion et nomme au rapport, et
    l'annoncer a zero le ferait disparaitre du cardinal **sans un mot** --
    c'est-a-dire le faire compter pour rien dans le total que l'ecran de depot
    annonce, alors qu'il coute du temps et qu'il sera signale.
    """
    faux = tmp_path / "pas-un-tiff.tiff"
    faux.parent.mkdir(parents=True, exist_ok=True)
    faux.write_bytes(b"ceci n'est pas un TIFF")
    assert scan_ingest._pages_d_un_fichier_image(faux) == 1
    assert scan_ingest._cardinal_des_pages([faux]) == 1


def test_un_index_de_page_HORS_BORNES_leve_au_lieu_de_rendre_la_page_zero(
    tmp_path: Path
) -> None:
    """AC3 et AC9. Le verdict se lit sur la LISTE rendue, jamais sur le booleen.

    `cv2.imreadmulti` rend `(False, [])` sur un index hors bornes -- il ne leve
    pas. Se rabattre sur `cv2.imread` en pareil cas rendrait la PAGE ZERO sous
    le nom d'une autre : le lot serait complet en cardinal et faux en contenu,
    ce qui est pire que le defaut que cette story ferme. Meme famille que
    « `git lfs fetch` ne dit rien quand il ne fait rien ».
    """
    chemin = ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=3)
    premiere = scan_ingest.lire_une_page_image(chemin, 0).tableau
    with pytest.raises(scan_ingest.UnsupportedScanInputError):
        scan_ingest.lire_une_page_image(chemin, 99)
    # Non-vacuite : la page 0 EXISTE, donc l'echec ci-dessus vient bien de
    # l'index et non d'un fichier illisible.
    assert tuple(int(v) for v in premiere[0, 0]) == bgr_attendu(0)



def test_une_page_illisible_au_milieu_rend_les_pages_LUES_et_le_DIT(
    projet: Path, tmp_path: Path, monkeypatch
) -> None:
    """AC6 -- **redigee une seconde fois, sur mesure de revue** (finding `C2-1`).

    La premiere politique faisait sauter le FICHIER entier, comme un PDF dont
    une page ne se rasterise pas. La couche 2 a mesure ce que ca coutait, et ce
    n'etait pas theorique : **le compteur et le lecteur ne sont pas le meme
    programme**. Pillow compte les repertoires, OpenCV decode les pixels, et
    ils divergent -- un PNG anime est compte a deux pages et n'en pagine
    qu'une. Sur ces fichiers-la, la politique « fichier entier » detruisait un
    fichier que la version d'AVANT la story ingerait a une page. Une story
    censee rendre les lots plus complets les rendait plus courts.

    Faire l'inverse -- rendre les pages lues sans rien dire -- serait le lot
    plausible et incomplet que cette story existe pour fermer. D'ou la
    TROISIEME issue (`EPIC11-ARB-89`) : les pages lisibles sont ingerees, et
    l'ecart est **nomme**.

    La panne est INJECTEE plutot que fabriquee : un TIFF dont une seule page
    est corrompue ne se construit pas de facon portable. Ce qui est mesure ici
    est la POLITIQUE, pas le decodeur.
    """
    ecrire_tiff_multipage(tmp_path / "scan" / "b.tiff", pages=3)
    ecrire_tiff_mono(tmp_path / "scan" / "a.tiff")

    vrai = scan_ingest.lire_une_page_image

    def _casse(chemin, page_index=None):
        if page_index == 1:
            raise scan_ingest.UnsupportedScanInputError("page 1 illisible")
        return vrai(chemin, page_index)

    monkeypatch.setattr(scan_ingest, "lire_une_page_image", _casse)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    # `a.tiff` (une page) + la seule page lisible de `b.tiff`.
    assert len(rapport.pages) == 2
    assert scan_ingest.IMAGE_PAGES_PARTIALLY_READABLE in rapport.warnings
    assert "b.tiff" not in rapport.skipped_files, (
        "le fichier n'est pas perdu : il a rendu ce qu'il pouvait")


def test_un_multipage_ENTIEREMENT_lisible_ne_declenche_PAS_l_avertissement(
    projet: Path, tmp_path: Path
) -> None:
    """AC6, non-vacuite. Un avertissement pose partout n'avertit de rien -- et
    c'est la moitie qui manque le plus souvent."""
    ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=3)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan.tiff", dpi=600)
    assert len(rapport.pages) == 3
    assert scan_ingest.IMAGE_PAGES_PARTIALLY_READABLE not in rapport.warnings


def test_un_fichier_dont_la_PREMIERE_page_ne_se_lit_pas_est_saute_en_le_nommant(
    projet: Path, tmp_path: Path, monkeypatch
) -> None:
    """AC7. Pas une seule page lisible : c'est un fichier illisible, et il est
    saute en le nommant -- pas un lot vide, pas un avertissement de lecture
    partielle sur zero page."""
    ecrire_tiff_multipage(tmp_path / "scan" / "b.tiff", pages=3)
    ecrire_tiff_mono(tmp_path / "scan" / "a.tiff")

    vrai = scan_ingest.lire_une_page_image

    def _casse(chemin, page_index=None):
        if Path(chemin).name == "b.tiff":
            raise scan_ingest.UnsupportedScanInputError("fichier illisible")
        return vrai(chemin, page_index)

    monkeypatch.setattr(scan_ingest, "lire_une_page_image", _casse)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    assert len(rapport.pages) == 1
    assert "b.tiff" in rapport.skipped_files
    assert scan_ingest.IMAGE_PAGES_PARTIALLY_READABLE not in rapport.warnings


def test_un_fichier_dont_AUCUNE_page_ne_se_lit_ne_fait_pas_perdre_le_LOT(
    projet: Path, tmp_path: Path, monkeypatch
) -> None:
    """AC7. Dans un dossier de dix planches, un fichier casse n'emporte pas les
    neuf autres."""
    ecrire_tiff_multipage(tmp_path / "scan" / "b.tiff", pages=3)
    ecrire_tiff_mono(tmp_path / "scan" / "a.tiff")
    ecrire_tiff_mono(tmp_path / "scan" / "c.tiff", rang=2)

    vrai = scan_ingest.lire_une_page_image

    def _casse(chemin, page_index=None):
        if Path(chemin).name == "b.tiff":
            raise scan_ingest.UnsupportedScanInputError("fichier illisible")
        return vrai(chemin, page_index)

    monkeypatch.setattr(scan_ingest, "lire_une_page_image", _casse)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    assert len(rapport.pages) == 2
    assert "b.tiff" in rapport.skipped_files


# --- AC8 : la regle des fabriques -------------------------------------------


@pytest.mark.parametrize("cible", [0, 1, 2])
def test_chaque_page_du_multipage_se_relit_a_sa_place(
    projet: Path, tmp_path: Path, cible: int
) -> None:
    """AC8. En TETE, au MILIEU et en QUEUE.

    La cible au milieu demasque un `find` fautif ; elle ne demasque pas un
    balayage tronque, qui saute la derniere entree et reste vert tant que
    toutes les cibles sont au milieu (mutant mesure sur le lot A de la 11.11).
    """
    ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=3)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan.tiff", dpi=600)
    assert len(rapport.pages) == 3
    page = rapport.pages[cible]
    assert page.locator.page_index == cible
    tableau = scan_ingest.load_page_array(projet, page.locator, dpi=600)
    assert tuple(int(v) for v in tableau[0, 0]) == bgr_attendu(cible)


# --- AC9 : frontieres NEGATIVES ---------------------------------------------


def _appels_cv2(chemin: Path, nom: str) -> list[ast.Call]:
    """Tous les appels a `cv2.<nom>` du module, lus sur l'AST.

    **Pas ligne a ligne, et le depot a deja paye la difference** : le
    recensement au `grep` des chemins publics du 2026-09-07 en avait manque
    quatre sur neuf, parce qu'un appel etale sur trois lignes ne se voit pas
    une ligne a la fois. Ces trois frontieres portent sur des appels qui sont
    justement etales.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    return [noeud for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Attribute)
            and noeud.func.attr == nom
            and isinstance(noeud.func.value, ast.Name)
            and noeud.func.value.id == "cv2"]


def _est_imread_unchanged(noeud: ast.expr) -> bool:
    return (isinstance(noeud, ast.Attribute)
            and noeud.attr == "IMREAD_UNCHANGED"
            and isinstance(noeud.value, ast.Name)
            and noeud.value.id == "cv2")


def test_aucun_cv2_imread_NU_dans_l_ingestion() -> None:
    """AC9. Le depot tient deja cette regle depuis 5.1 : un `imread` nu
    ramenerait un TIFF 16 bits a 8 bits **sans un mot**."""
    appels = _appels_cv2(MODULE_INGEST, "imread")
    assert appels, "la garde n'a plus rien a garder"
    for appel in appels:
        assert len(appel.args) == 2 and _est_imread_unchanged(appel.args[1]), (
            f"cv2.imread nu ligne {appel.lineno}")


def test_aucune_lecture_ne_charge_les_N_pages_D_UN_COUP() -> None:
    """AC9, frontiere NEGATIVE.

    `imreadmulti(chemin, flags=...)` decoderait TOUTES les pages : a 600 ppp en
    RGBA, 143 Mo par page, soit 1,4 Go pour dix pages -- pour en rendre une.
    La surcharge BORNEE `(fichier, start, count)` est la seule admise.
    """
    appels = _appels_cv2(MODULE_INGEST, "imreadmulti")
    assert appels, "la garde n'a plus rien a garder"
    for appel in appels:
        assert len(appel.args) >= 3, (
            f"lecture non bornee ligne {appel.lineno} : la surcharge sans "
            "`start`/`count` lit le fichier ENTIER")
        # **La VALEUR, pas seulement l'arite** (finding `C3-2` de la couche 3).
        # La premiere redaction ne mesurait que la presence d'un troisieme
        # argument : `count=4096` la satisfaisait parfaitement, et la propriete
        # annoncee -- « aucune lecture ne charge les N pages d'un coup » -- ne
        # tenait plus. La lettre de l'AC etait tenue, sa propriete non.
        compte = appel.args[2]
        assert isinstance(compte, ast.Constant) and compte.value == 1, (
            f"lecture non bornee ligne {appel.lineno} : `count` doit valoir 1, "
            "une page a la fois")


def test_le_flag_de_lecture_multipage_est_EXPLICITE() -> None:
    """AC9. Le `flags` par defaut d'`imreadmulti` n'est PAS `IMREAD_UNCHANGED`
    -- c'est `IMREAD_ANYCOLOR` sur la surcharge bornee."""
    appels = _appels_cv2(MODULE_INGEST, "imreadmulti")
    assert appels, "la garde n'a plus rien a garder"
    for appel in appels:
        drapeaux = [mot.value for mot in appel.keywords if mot.arg == "flags"]
        drapeaux += appel.args[3:]
        assert any(_est_imread_unchanged(d) for d in drapeaux), (
            f"lecture multipage sans IMREAD_UNCHANGED ligne {appel.lineno} : "
            "un TIFF 16 bits redescendrait a 8 bits sans un mot")


def test_un_TIFF_16_bits_multipage_reste_16_bits(
    projet: Path, tmp_path: Path
) -> None:
    """AC9, mesuree par EFFET et non par grep -- le grep ci-dessus ne prouve
    que la forme de l'appel."""
    chemin = tmp_path / "scan.tiff"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    pages = [Image.fromarray(np.full((24, 32), 4000 + 500 * r, np.uint16))
             for r in range(2)]
    pages[0].save(chemin, save_all=True, append_images=[pages[1]])
    rapport = scan_ingest.ingest_scan_lot(projet, chemin, dpi=600)
    assert len(rapport.pages) == 2
    assert [p.source_bit_depth for p in rapport.pages] == [16, 16]


# --- AC10 : les avertissements d'homogeneite voient les pages ----------------


def test_MIXED_PAGE_DIMENSIONS_voit_les_pages_d_un_MEME_fichier(
    projet: Path, tmp_path: Path
) -> None:
    """AC10. Ces avertissements se calculent sur la LISTE des pages : ils
    etaient inertes sur un fichier unique, ils redeviennent vrais."""
    ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=2,
                          tailles=[(24, 32), (40, 30)])
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan.tiff", dpi=600)
    assert "MIXED_PAGE_DIMENSIONS" in rapport.warnings


def test_un_multipage_HOMOGENE_ne_declenche_rien(
    projet: Path, tmp_path: Path
) -> None:
    """AC10, non-vacuite : un avertissement pose partout n'avertit de rien."""
    ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=3)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan.tiff", dpi=600)
    assert "MIXED_PAGE_DIMENSIONS" not in rapport.warnings
    assert "MIXED_BIT_DEPTHS" not in rapport.warnings


# --- l'alpha de la 5.30 survit au chemin multipage --------------------------


def test_un_multipage_RGBA_rend_trois_canaux_sur_CHAQUE_page(
    projet: Path, tmp_path: Path
) -> None:
    """Croisement des deux stories de la vague, et c'est le regime EXACT du
    fichier de terrain : deux pages `Apple Image Capture`, RGBA, alpha opaque.

    Les deux correctifs se croisent au point de lecture ; s'ils ne s'y
    croisaient pas, chaque page du multipage reviendrait a quatre canaux.
    """
    ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=2, rgba=True)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan.tiff", dpi=600)
    assert len(rapport.pages) == 2
    for rang, page in enumerate(rapport.pages):
        assert page.channels == 4
        tableau = scan_ingest.load_page_array(projet, page.locator, dpi=600)
        assert tableau.shape[2] == 3
        assert tuple(int(v) for v in tableau[0, 0]) == bgr_attendu(rang)


# --- findings de la revue en trois couches du 2026-09-09 --------------------


def test_une_page_n_est_pas_RETOURNEE_ni_MIROIR(
    projet: Path, tmp_path: Path
) -> None:
    """Finding `C2-5`. Le coin marque de la fabrique est ce qui le mesure.

    Une page rendue retournee haut/bas -- ou en miroir -- laisse `tableau[0, 0]`
    intact quand la page est uniforme. Les deux coins opposes, eux, la
    demasquent.
    """
    ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=2)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan.tiff", dpi=600)
    for rang, page in enumerate(rapport.pages):
        tableau = scan_ingest.load_page_array(projet, page.locator, dpi=600)
        assert tuple(int(v) for v in tableau[0, 0]) == bgr_attendu(rang)
        assert tuple(int(v) for v in tableau[-1, -1]) == (13, 11, 7)


def test_la_LARGEUR_et_la_HAUTEUR_ne_sont_pas_ECHANGEES(
    projet: Path, tmp_path: Path
) -> None:
    """Finding `C2-4`. Classe *critique* de la politique : appariement
    positionnel.

    `test_MIXED_PAGE_DIMENSIONS` ne mesurait que la LEVEE de l'avertissement,
    qui se leve aussi bien avec les deux axes inverses. Il faut des pages non
    carrees ET une assertion sur chaque champ.
    """
    ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=2,
                          tailles=[(24, 32), (40, 30)])
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan.tiff", dpi=600)
    # `tailles` est en (hauteur, largeur), le rapport en px.
    assert [(p.height_px, p.width_px) for p in rapport.pages] == [(24, 32), (40, 30)]
    for page in rapport.pages:
        tableau = scan_ingest.load_page_array(projet, page.locator, dpi=600)
        assert tableau.shape[0] == page.height_px
        assert tableau.shape[1] == page.width_px


def ecrire_tiff_avec_vignette(chemin: Path) -> Path:
    """Un TIFF dont le SECOND repertoire est une VIGNETTE, pas une page.

    `NewSubfileType` bit 0 -- « image de resolution reduite ». C'est ce qu'un
    scanner ecrit a cote de sa page pleine.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    pleine = Image.fromarray(np.dstack([np.full((40, 60), v, np.uint8)
                                        for v in couleur_de_page(0)]), mode="RGB")
    vignette = Image.fromarray(np.dstack([np.full((8, 12), v, np.uint8)
                                          for v in couleur_de_page(1)]), mode="RGB")
    tags = TiffImagePlugin.ImageFileDirectory_v2()
    tags[254] = 1
    vignette.encoderinfo = {"tiffinfo": tags}
    pleine.save(chemin, save_all=True, append_images=[vignette])
    return chemin


def test_une_VIGNETTE_n_est_pas_comptee_comme_une_page(
    projet: Path, tmp_path: Path
) -> None:
    """Finding `C2-2` de la couche 2.

    Un lot **sur**-complet est l'inverse exact du defaut que la story ferme, et
    il est plus sournois : le cardinal et l'ingestion sont **d'accord**, donc le
    controle d'egalite ne peut pas le voir.

    **Ce que ce banc ne prouve PAS** : aucun des deux fichiers de terrain du
    2026-09-09 ne porte de vignette. La garde est posee sur une fabrique de
    synthese, et le depot sait ce que ca vaut.
    """
    chemin = ecrire_tiff_avec_vignette(tmp_path / "scan.tiff")
    with Image.open(chemin) as relu:
        assert relu.n_frames == 2, "la fabrique doit ecrire DEUX repertoires"
        relu.seek(1)
        assert int(relu.tag_v2[254]) & 1, "le second doit etre marque REDUIT"
    assert scan_ingest._pages_d_un_fichier_image(chemin) == 1
    rapport = scan_ingest.ingest_scan_lot(projet, chemin, dpi=600)
    assert len(rapport.pages) == 1
    assert (rapport.pages[0].height_px, rapport.pages[0].width_px) == (40, 60)


def test_le_canal_de_PROGRESSION_emet_un_jalon_par_page_du_multipage(
    projet: Path, tmp_path: Path
) -> None:
    """Finding `C2-3` de la couche 2 : aucun test ne mesurait la progression du
    chemin multipage.

    Trois regimes fautifs survivaient avec trois consequences visibles -- un
    jalon emis AVANT la lecture (viole `EPIC7-ARB-79`), un decalage d'un cran
    (barre figee a 75 % sur un lot TERMINE, c'est le finding `A2`), un
    rattrapage a `+= 1`.
    """
    jalons: list[tuple[int, int]] = []
    ecrire_tiff_mono(tmp_path / "scan" / "a.tiff")
    ecrire_tiff_multipage(tmp_path / "scan" / "b.tiff", pages=3)
    scan_ingest.ingest_scan_lot(
        projet, tmp_path / "scan", dpi=600,
        rappel_progression=lambda faites, total: jalons.append((faites, total)))
    assert jalons, "aucun jalon emis"
    totaux = {total for _, total in jalons}
    assert totaux == {4}, f"le total doit valoir 4 pages, vu {totaux}"
    faits = [faites for faites, _ in jalons]
    assert faits == sorted(faits), "les jalons doivent etre croissants"
    assert faits[-1] == 4, "la barre doit ATTEINDRE son total"
    assert max(faits) <= 4, "aucun jalon ne depasse le total"


def test_un_PNG_ANIME_n_est_pas_PERDU_par_la_story(
    projet: Path, tmp_path: Path
) -> None:
    """Finding `C1-3` de la couche 1 : une REGRESSION, mesuree des deux cotes.

    `n_frames` n'est la chaine d'IFD que sur un TIFF. Sur un `.png` anime et
    sur un `.jpg` multi-image -- deux extensions qu'`IMAGE_EXTENSIONS`
    accepte -- c'est une bande d'animation, que `cv2.imreadmulti` ne pagine
    pas. La premiere redaction de la story rendait donc **zero page et un
    fichier saute** la ou `cv2.imread` en lisait une avant elle.

    Le fichier rend desormais ce que le lecteur sait lire, et l'ecart est
    nomme.
    """
    dossier = tmp_path / "scan"
    dossier.mkdir(parents=True, exist_ok=True)
    pages = [Image.fromarray(np.dstack([np.full((8, 8), v, np.uint8)
                                        for v in couleur_de_page(r)]), mode="RGB")
             for r in range(2)]
    pages[0].save(dossier / "anim.png", save_all=True,
                  append_images=[pages[1]], duration=100)
    with Image.open(dossier / "anim.png") as relu:
        assert relu.n_frames == 2, "la fabrique doit produire une bande"

    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=600)
    assert len(rapport.pages) == 1, "le fichier ne doit pas etre perdu"
    assert "anim.png" not in rapport.skipped_files
    assert scan_ingest.IMAGE_PAGES_PARTIALLY_READABLE in rapport.warnings


def test_quand_PILLOW_ne_sait_pas_compter_le_LECTEUR_est_interroge(
    projet: Path, tmp_path: Path, monkeypatch
) -> None:
    """Finding `C1-1` de la couche 1, et c'est le plus sournois des trois.

    Pillow et OpenCV n'ont pas les memes plafonds -- un facteur douze sur le
    nombre de pixels. Sur un TIFF de deux pages assez grand, Pillow leve
    `DecompressionBombError` la ou OpenCV lit les deux, et la premiere
    redaction rendait alors `1` : **une page, zero fichier saute, zero
    avertissement**, la seconde perdue en silence. La justification ecrite
    disait « il sera saute a l'ingestion et nomme au rapport » -- elle etait
    fausse dans exactement ce regime.

    Le plafond est ABAISSE ici plutot que le fichier agrandi : fabriquer 180
    Mpx par page couterait des centaines de mega-octets pour mesurer une
    branche de trois lignes.
    """
    chemin = ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=3)
    # Sous ce plafond, Pillow leve sur une image de 24 x 32.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 16)
    with pytest.raises(Exception):
        with Image.open(chemin) as image:
            image.seek(1)
            image.load()

    assert scan_ingest._pages_d_un_fichier_image(chemin) == 3, (
        "le compteur doit se rabattre sur le LECTEUR, pas rendre 1")
    rapport = scan_ingest.ingest_scan_lot(projet, chemin, dpi=600)
    assert len(rapport.pages) == 3


@pytest.mark.parametrize("asymetrie", [(600, 75), (75, 600)])
def test_le_dpi_du_MULTIPAGE_lit_les_DEUX_AXES(tmp_path: Path, asymetrie) -> None:
    """Finding `C1-2` de la couche 1 : le jumeau du defaut de 5.30, dans une
    fonction NEUVE -- donc le correctif de l'autre ne l'atteignait pas.

    **L'asymetrie se joue dans les DEUX SENS.** Avec `(600, 75)` seul, lire le
    PLUS BAS et lire l'axe VERTICAL rendent tous deux `75` : le mutant « axe
    vertical seul » survivait. Regle des fabriques, appliquee aux axes.
    """
    chemin = tmp_path / "mixte.tiff"
    a, b = tmp_path / "a.tiff", tmp_path / "b.tiff"
    for source, resolution, rang in ((a, asymetrie, 0), (b, (300, 300), 1)):
        Image.fromarray(np.dstack([np.full((24, 32), v, np.uint8)
                                   for v in couleur_de_page(rang)]),
                        mode="RGB").save(source, dpi=resolution)
    with Image.open(a) as premiere, Image.open(b) as seconde:
        premiere.save(chemin, save_all=True, append_images=[seconde])
    assert scan_ingest._measure_page_file_dpi(chemin) == pytest.approx(75.0)


def ecrire_tiff_vignette_au_MILIEU(chemin: Path) -> Path:
    """Trois repertoires : page, VIGNETTE, page. L'index et le rang divergent."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    def _page(rang, taille):
        hauteur, largeur = taille
        return Image.fromarray(np.dstack([np.full((hauteur, largeur), v, np.uint8)
                                          for v in couleur_de_page(rang)]),
                               mode="RGB")
    tags = TiffImagePlugin.ImageFileDirectory_v2()
    tags[254] = 1
    vignette = _page(2, (8, 12))
    vignette.encoderinfo = {"tiffinfo": tags}
    _page(0, (40, 60)).save(chemin, save_all=True,
                            append_images=[vignette, _page(1, (40, 60))])
    return chemin


def test_le_RANG_de_lecture_et_l_INDEX_du_repertoire_DIVERGENT(
    projet: Path, tmp_path: Path
) -> None:
    """Le rang suit les pages PRODUITES, l'index designe le REPERTOIRE.

    Les confondre ne se voit que lorsqu'un repertoire est ecarte : avec une
    vignette au MILIEU, les deux vraies pages portent les index `0` et `2`, et
    doivent porter les rangs `0` et `1`. Un rang pris sur l'index ferait un
    TROU dans la numerotation du lot -- mutant qui survivait a tous les bancs
    tant qu'aucune fabrique ne placait de vignette ailleurs qu'en queue.
    """
    chemin = ecrire_tiff_vignette_au_MILIEU(tmp_path / "scan.tiff")
    with Image.open(chemin) as relu:
        assert relu.n_frames == 3, "la fabrique doit ecrire TROIS repertoires"
    assert scan_ingest._indices_de_pages_d_un_fichier_image(chemin) == (0, 2)

    rapport = scan_ingest.ingest_scan_lot(projet, chemin, dpi=600)
    assert [p.read_rank for p in rapport.pages] == [0, 1]
    assert [p.locator.page_index for p in rapport.pages] == [0, 2]
    for rang, page in enumerate(rapport.pages):
        tableau = scan_ingest.load_page_array(projet, page.locator, dpi=600)
        assert tuple(int(v) for v in tableau[0, 0]) == bgr_attendu(rang)


def test_le_RATTRAPAGE_de_compteur_d_un_fichier_saute_atteint_le_TOTAL(
    projet: Path, tmp_path: Path, monkeypatch
) -> None:
    """AC6 (finding `C3-1` de la couche 3), et l'AC nommait elle-meme le
    symptome sans le mesurer.

    Un fichier saute doit faire avancer le compteur de **ce que le cardinal a
    compte pour lui**, pas d'une unite. Le mutant `faites += 1` laissait 42
    bancs verts et rendait une barre a **4/6, soit 67 %, sur un travail
    TERMINE** -- c'est le finding `A2` de la revue du canal de progression,
    reintroduit par la porte du multipage. Le regime 6.1 bis rend le defaut
    invisible autrement : l'emetteur absorbe en silence tout jalon non
    progressif, donc aucune frontiere de CONTENU ne peut le voir.
    """
    ecrire_tiff_multipage(tmp_path / "scan" / "b.tiff", pages=3)
    ecrire_tiff_mono(tmp_path / "scan" / "a.tiff")
    ecrire_tiff_mono(tmp_path / "scan" / "c.tiff", rang=2)

    vrai = scan_ingest.lire_une_page_image

    def _casse(chemin, page_index=None):
        # La PREMIERE page echoue : le fichier entier est saute.
        if Path(chemin).name == "b.tiff":
            raise scan_ingest.UnsupportedScanInputError("fichier illisible")
        return vrai(chemin, page_index)

    monkeypatch.setattr(scan_ingest, "lire_une_page_image", _casse)
    jalons: list[tuple[int, int]] = []
    scan_ingest.ingest_scan_lot(
        projet, tmp_path / "scan", dpi=600,
        rappel_progression=lambda faites, total: jalons.append((faites, total)))
    assert {total for _, total in jalons} == {5}, "a.tiff + b.tiff (3) + c.tiff"
    faits = [faites for faites, _ in jalons]
    assert faits[-1] == 5, (
        f"la barre doit ATTEINDRE son total sur un travail termine, vue a "
        f"{faits[-1]}/5")


def test_un_fichier_MULTIPAGE_designe_SEUL_garde_son_refus_dur(
    projet: Path, tmp_path: Path, monkeypatch
) -> None:
    """AC7, seconde moitie (finding de la couche 3).

    « Le fichier designe SEUL garde son refus dur -- la ou il est la seule
    source, un saut silencieux rendrait un lot vide. » La premiere redaction ne
    mesurait que le cas du DOSSIER.
    """
    chemin = ecrire_tiff_multipage(tmp_path / "scan.tiff", pages=3)

    def _casse(chemin_lu, page_index=None):
        raise scan_ingest.UnsupportedScanInputError("illisible")

    monkeypatch.setattr(scan_ingest, "lire_une_page_image", _casse)
    with pytest.raises(scan_ingest.EmptyScanLotError):
        scan_ingest.ingest_scan_lot(projet, chemin, dpi=600)


def test_MIXED_BIT_DEPTHS_voit_les_pages_d_un_MEME_fichier(
    projet: Path, tmp_path: Path
) -> None:
    """AC10, seconde moitie (finding de la couche 3) : seul
    `MIXED_PAGE_DIMENSIONS` etait mesure, jamais son jumeau."""
    chemin = tmp_path / "scan.tiff"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    huit = Image.fromarray(np.dstack([np.full((24, 32), v, np.uint8)
                                      for v in couleur_de_page(0)]), mode="RGB")
    seize = Image.fromarray(np.full((24, 32), 4000, np.uint16))
    huit.save(chemin, save_all=True, append_images=[seize])
    rapport = scan_ingest.ingest_scan_lot(projet, chemin, dpi=600)
    assert len(rapport.pages) == 2
    assert sorted(p.source_bit_depth for p in rapport.pages) == [8, 16]
    assert "MIXED_BIT_DEPTHS" in rapport.warnings
