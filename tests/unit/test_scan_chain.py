"""Tests de l'identite de chaine de scan (story 5.22, AC 4).

L'identifiant de chaine est derive **des parametres reels** de la chaine, de
facon deterministe et inter-machine. La doctrine est celle du condensat de 5.12
(`io.naming.bounds_suffix`): jamais de `hash()` Python, jamais d'horodate, jamais
de chemin absolu, jamais de slug operateur, jamais de pixels.

**La derive n'est plus surchargeable** depuis la story 5.23 (AC 13,
`EPIC5-ARB-88`): le drapeau qui le permettait a ete retire avec le role
d'appariement du `chain_id` (`EPIC5-ARB-83`). Ce que ce fichier verifie est donc
la seule voie, et non plus « la valeur par defaut ».
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import scan_chain
from mixed_media_utility.io import naming

CHAIN_ID_PATTERN = r"^[A-Za-z0-9_-]+$"


def test_derive_chain_id_est_deterministe_et_conforme() -> None:
    a = scan_chain.derive_chain_id(declared_dpi=600, scan_input_format="tiff")
    b = scan_chain.derive_chain_id(declared_dpi=600, scan_input_format="tiff")
    assert a == b
    assert a.startswith("600-tiff-")
    assert len(a) <= naming.CANONICAL_ID_MAX_LENGTH
    assert __import__("re").match(CHAIN_ID_PATTERN, a)


def test_chaque_parametre_capture_change_le_chain_id() -> None:
    # Frontiere AC 4: un seul parametre varie suffit a changer l'identite.
    base = scan_chain.derive_chain_id(declared_dpi=600, scan_input_format="tiff")
    variations = [
        scan_chain.derive_chain_id(declared_dpi=300, scan_input_format="tiff"),
        scan_chain.derive_chain_id(declared_dpi=600, scan_input_format="pdf"),
        scan_chain.derive_chain_id(declared_dpi=600, scan_input_format="tiff",
                                  make="EPSON"),
        scan_chain.derive_chain_id(declared_dpi=600, scan_input_format="tiff",
                                  model="V850"),
        scan_chain.derive_chain_id(declared_dpi=600, scan_input_format="tiff",
                                  software="EpsonScan"),
    ]
    for variant in variations:
        assert variant != base, f"le parametre varie n'a pas change l'identite: {variant}"


def test_les_captures_reelles_du_depot_se_distinguent_par_le_format() -> None:
    # Mesure du 2026-08-17: scan-WIN est en TIFF, 12p5_test et rush-bitch-4-scan2
    # en PDF, tous declares a 600 dpi. Le format seul suffit donc a separer la
    # chaine TIFF des deux chaines PDF.
    tiff = scan_chain.derive_chain_id(declared_dpi=600, scan_input_format="tiff")
    pdf = scan_chain.derive_chain_id(declared_dpi=600, scan_input_format="pdf")
    assert tiff != pdf


def test_absent_tag_ne_change_pas_la_chaine() -> None:
    # Best effort documente: un tag absent vaut "" et ne compte pas dans le
    # materiel. Les trois captures reelles n'ont aucun tag (mesure du
    # 2026-08-17), donc le materiel se reduit au sous-ensemble possede.
    sans_tag = scan_chain.derive_chain_id(declared_dpi=600, scan_input_format="tiff")
    avec_tag = scan_chain.derive_chain_id(declared_dpi=600, scan_input_format="tiff",
                                          make="", model="", software="")
    assert sans_tag == avec_tag


def test_chain_material_est_deterministe_et_separe_les_champs() -> None:
    materiel = scan_chain.chain_material(
        declared_dpi=600, scan_input_format="pdf", make="HP", model="ScanJet")
    # Valeur attendue mise a jour le 2026-08-17 avec le prefixe de longueur:
    # l'ancienne forme `600|pdf|HP|ScanJet|` n'etait pas injective (cf. le test
    # de collision ci-dessous). L'assertion reste une egalite exacte -- elle
    # continue d'exiger l'ordre des cinq segments et leur presence -- et gagne
    # le cardinal de chaque champ.
    assert materiel == "3:600|3:pdf|2:HP|7:ScanJet|0:"
    # Deux chaines qui ne different que par un champ absent ne se confondent
    # pas: les cinq segments sont toujours presents.
    assert scan_chain.chain_material(
        declared_dpi=600, scan_input_format="pdf") != materiel


def test_un_separateur_dans_un_tag_ne_fusionne_pas_deux_chaines() -> None:
    # Domaine d'activation de la garde: les tags TIFF viennent d'un pilote
    # quelconque, rien ne lui interdit d'y ecrire un `|`. Sans prefixe de
    # longueur, ces deux chaines physiquement differentes partageaient le meme
    # materiel, donc le meme fichier `versions/calibration/<chain_id>.json`.
    gauche = dict(declared_dpi=1200, scan_input_format="tiff",
                  make="X|Y", model="Z", software="drv")
    droite = dict(declared_dpi=1200, scan_input_format="tiff",
                  make="X", model="Y|Z", software="drv")
    assert scan_chain.chain_material(**gauche) != scan_chain.chain_material(**droite)
    assert scan_chain.derive_chain_id(**gauche) != scan_chain.derive_chain_id(**droite)
    # Le delimiteur de longueur est lui aussi un caractere ordinaire d'un tag:
    # il ne doit pas davantage deplacer une frontiere de champ.
    assert (scan_chain.chain_material(declared_dpi=1200, scan_input_format="tiff",
                                      make="12:34", model="")
            != scan_chain.chain_material(declared_dpi=1200, scan_input_format="tiff",
                                         make="12", model="34"))


def test_l_encodage_du_materiel_est_injectif_sur_un_domaine_construit() -> None:
    # L'autre bout de la meme garde: sur un jeu de six chaines couvrant les
    # separateurs, les delimiteurs, les champs vides et les permutations de
    # champs, aucun materiel ne se repete -- et aucun `chain_id` non plus.
    chaines = (
        dict(declared_dpi=600, scan_input_format="tiff", make="A|B", model="C"),
        dict(declared_dpi=600, scan_input_format="tiff", make="A", model="B|C"),
        dict(declared_dpi=600, scan_input_format="tiff", make="A", model="B",
             software="C"),
        dict(declared_dpi=600, scan_input_format="tiff", make="AB", model="C"),
        dict(declared_dpi=600, scan_input_format="tiff", make="2:AB", model=""),
        dict(declared_dpi=600, scan_input_format="tiff", make="", model="2:AB"),
    )
    materiels = {scan_chain.chain_material(**chaine) for chaine in chaines}
    identifiants = {scan_chain.derive_chain_id(**chaine) for chaine in chaines}
    assert len(materiels) == len(chaines), materiels
    assert len(identifiants) == len(chaines), identifiants


def test_la_garde_est_inerte_sur_les_valeurs_livrees() -> None:
    # Premier bout de la garde: sur les valeurs reellement livrees (les trois
    # captures du depot n'ont aucun tag, cf. mesure du 2026-08-17), le prefixe
    # de longueur ne change rien a ce qui doit rester vrai -- determinisme,
    # conformite au pattern, budget de longueur.
    identifiant = scan_chain.derive_chain_id(declared_dpi=600,
                                             scan_input_format="tiff")
    assert identifiant == scan_chain.derive_chain_id(declared_dpi=600,
                                                     scan_input_format="tiff")
    assert identifiant.startswith("600-tiff-")
    assert len(identifiant) <= naming.CANONICAL_ID_MAX_LENGTH
    assert __import__("re").fullmatch(CHAIN_ID_PATTERN, identifiant)


def test_un_dpi_invalide_est_refuse() -> None:
    for bad in (0, -1, True, 1.5, "600", None):
        with pytest.raises(scan_chain.InvalidChainParameterError):
            scan_chain.chain_material(declared_dpi=bad, scan_input_format="tiff")


def test_un_format_vide_est_refuse() -> None:
    with pytest.raises(scan_chain.InvalidChainParameterError):
        scan_chain.chain_material(declared_dpi=600, scan_input_format="")


def _write_tiff_with_tags(path: Path, *, make: str, model: str, software: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    array = np.full((20, 30, 3), 128, dtype=np.uint8)
    Image.fromarray(array, mode="RGB").save(
        path, tiffinfo={scan_chain.TIFF_TAG_MAKE: make,
                        scan_chain.TIFF_TAG_MODEL: model,
                        scan_chain.TIFF_TAG_SOFTWARE: software})


def test_read_scan_tags_retrouve_les_tags_tiff(tmp_path: Path) -> None:
    fichier = tmp_path / "page.tiff"
    _write_tiff_with_tags(fichier, make="EPSON", model="V850", software="EpsonScan")
    assert scan_chain.read_scan_tags(fichier) == ("EPSON", "V850", "EpsonScan")


def test_read_scan_tags_sur_un_png_sans_tags(tmp_path: Path) -> None:
    chemin = tmp_path / "page.png"
    Image.fromarray(np.full((20, 30, 3), 128, dtype=np.uint8), mode="RGB").save(chemin)
    assert scan_chain.read_scan_tags(chemin) == ("", "", "")


def test_read_scan_tags_best_effort_sur_absents_et_dossiers(tmp_path: Path) -> None:
    # Un chemin absent et un dossier vide rendent les trois chaines vides.
    assert scan_chain.read_scan_tags(tmp_path / "absent.tiff") == ("", "", "")
    assert scan_chain.read_scan_tags(tmp_path) == ("", "", "")
    # Un dossier balaie ses fichiers dans l'ordre trie (determinisme inter-machine).
    a = tmp_path / "b.tiff"
    b = tmp_path / "a.tiff"
    _write_tiff_with_tags(a, make="SECOND", model="", software="")
    _write_tiff_with_tags(b, make="PREMIER", model="", software="")
    assert scan_chain.read_scan_tags(tmp_path) == ("PREMIER", "", "")


def test_les_tags_tiff_reels_atteignent_le_chain_id(tmp_path: Path) -> None:
    # `EPIC5-ARB-39`: jusqu'ici aucune fixture ne faisait passer un tag non vide
    # (les trois captures reelles n'en portent pas), si bien que tout le cablage
    # `read_scan_tags` -> `derive_chain_id` pouvait etre supprime sans qu'un
    # test bouge. Ce test part d'un **vrai** raster portant les tags 271/272/305
    # et exige que leurs valeurs arrivent jusqu'a l'identifiant.
    dossier = tmp_path / "scan-epson"
    _write_tiff_with_tags(dossier / "page-01.tiff",
                          make="EPSON", model="V850", software="EpsonScan")
    lus = scan_chain.read_scan_tags(dossier)
    assert lus == ("EPSON", "V850", "EpsonScan")

    make, model, software = lus
    depuis_le_raster = scan_chain.derive_chain_id(
        declared_dpi=600, scan_input_format="tiff",
        make=make, model=model, software=software)
    # (a) les tags lus donnent exactement l'identifiant des memes valeurs
    # ecrites a la main: le chemin de lecture ne les deforme pas;
    assert depuis_le_raster == scan_chain.derive_chain_id(
        declared_dpi=600, scan_input_format="tiff",
        make="EPSON", model="V850", software="EpsonScan")
    # (b) et il differe de l'identifiant sans tags: supprimer le cablage des
    # tags change le resultat, donc le mutant qui l'enleve meurt ici.
    assert depuis_le_raster != scan_chain.derive_chain_id(
        declared_dpi=600, scan_input_format="tiff")

    # (c) deux scanners au meme dpi et au meme format, distingues par le seul
    # tag `model` lu sur le raster, ne partagent pas de profil.
    autre = tmp_path / "scan-canon"
    _write_tiff_with_tags(autre / "page-01.tiff",
                          make="EPSON", model="V600", software="EpsonScan")
    autre_make, autre_model, autre_software = scan_chain.read_scan_tags(autre)
    depuis_l_autre = scan_chain.derive_chain_id(
        declared_dpi=600, scan_input_format="tiff",
        make=autre_make, model=autre_model, software=autre_software)
    assert depuis_l_autre != depuis_le_raster


def test_report_scan_input_format_canonise_les_formats_mesures() -> None:
    from types import SimpleNamespace

    report = SimpleNamespace(pages=(
        SimpleNamespace(scan_input_format="pdf"),
        SimpleNamespace(scan_input_format="pdf"),
    ))
    assert scan_chain.report_scan_input_format(report) == "pdf"

    melange = SimpleNamespace(pages=(
        SimpleNamespace(scan_input_format="png"),
        SimpleNamespace(scan_input_format="tiff"),
        SimpleNamespace(scan_input_format="png"),
    ))
    # Ensemble trie, insensible a l'ordre de lecture, jamais un slug operateur.
    assert scan_chain.report_scan_input_format(melange) == "png+tiff"


#: Graines de hachage balayees par le test d'ordre d'iteration ci-dessous. Huit suffisent
#: **par mesure** et non par principe: sur les quatre formats de la fixture, un ensemble
#: parcouru dans son ordre de hachage n'est trie qu'une fois sur 24 en moyenne, et le
#: mutant qui retire le `sorted()` meurt des la premiere graine qui le derange.
_GRAINES_DE_HACHAGE = tuple(range(8))

#: Les formats de la fixture, **quatre et non deux**, et distinguables deux a deux. Avec
#: deux elements deja ordonnes, l'ordre d'un ensemble coincide avec l'ordre trie pour la
#: majorite des graines: c'est exactement ce qui rendait le `sorted()` invisible (mesure
#: du 2026-08-19, mutant survivant sur 4 graines sur 6).
_FORMATS_MELANGES = ("tiff", "png", "pdf", "jpeg")


def test_le_format_de_chaine_reste_trie_quelle_que_soit_la_graine_de_hachage() -> None:
    """Ordre d'iteration -- classe **critique**, zero survivant tolere.

    Finding de la couche 2 de la revue de 5.22 (checklist des fabriques, `E-F1`):
    `report_scan_input_format` annonce une liste triee et l'etablissait sur **deux**
    elements deja ordonnes (`png`, `tiff`). Mesure du 2026-08-19: le mutant qui remplace
    `sorted({...})` par `list({...})` **survit** sous `PYTHONHASHSEED` 2, 3, 4 et 5, et
    ne meurt que sous 0 et 1. Un test vert quatre fois sur six selon une variable
    d'environnement ne mesure pas l'ordre, il mesure la chance.

    Et ce n'est pas une classe que l'outillage peut couvrir: **mutmut ne genere aucun
    mutant qui retire un `sorted()`** (regle 4.0(c) de la politique de revue). L'ordre
    d'iteration se verifie par injection manuelle, et il faut donc que le test survive
    a la graine.

    La forme retenue est celle deja employee par
    `test_divergence_par_defaut.py::test_le_mutant_de_la_frontiere_stricte_est_
    effectivement_tue`: un sous-processus par graine, plutot qu'une fixture qui
    reglerait `PYTHONHASHSEED` apres le demarrage de l'interpreteur -- ou la variable
    n'a plus aucun effet, l'alea de hachage etant fige au lancement.

    Le cardinal de la fixture est porte a **quatre** formats: c'est ce qui fait tomber a
    1/24 la probabilite qu'un ensemble parcouru dans son ordre de hachage soit trie par
    accident, donc ce qui rend le balayage concluant plutot que chanceux.
    """
    script = textwrap.dedent(
        """
        import sys
        from types import SimpleNamespace
        sys.path.insert(0, sys.argv[1])
        from mixed_media_utility import scan_chain

        formats = sys.argv[2].split(",")
        rapport = SimpleNamespace(pages=tuple(
            SimpleNamespace(scan_input_format=f) for f in formats))
        obtenu = scan_chain.report_scan_input_format(rapport)
        attendu = "+".join(sorted(set(formats)))
        assert obtenu == attendu, f"ordre non trie: {obtenu!r} au lieu de {attendu!r}"
        """
    )
    for graine in _GRAINES_DE_HACHAGE:
        environnement = dict(os.environ, PYTHONHASHSEED=str(graine))
        resultat = subprocess.run(
            [sys.executable, "-c", script, str(REPO_ROOT / "src"),
             ",".join(_FORMATS_MELANGES)],
            capture_output=True, text=True, timeout=120, env=environnement)
        assert resultat.returncode == 0, (
            f"PYTHONHASHSEED={graine}: le format de chaine n'est pas trie -- "
            f"{resultat.stderr}")


def test_report_scan_input_format_refuse_un_scan_vide() -> None:
    from types import SimpleNamespace

    with pytest.raises(scan_chain.InvalidChainParameterError):
        scan_chain.report_scan_input_format(SimpleNamespace(pages=()))