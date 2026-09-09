# -*- coding: utf-8 -*-
"""Story 7.3, AC 5 -- ce qui n'a pas le droit d'exister dans ce diff.

Chaque assertion de ce banc est un **comptage qui doit rendre zero**. Et
chacune a son **symetrique** : `test_la_frontiere_mord_sur_un_module_temoin`
fabrique un module fautif et verifie que **chaque** balayage le voit. « Une
frontiere qui ne mord sur rien n'est pas une frontiere » -- c'est le geste de
`test_la_frontiere_mord_sur_un_fichier_hors_gui` de 7.0, repris ici.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import fabriques_scan as fab
from mixed_media_utility.gui import (
    atelier_scan,
    cartes_taches,
    catalogue,
    chargeur_detections,
    jetons,
    modele_chutier,
    modele_zone_tampon,
    zone_tampon,
)
from mixed_media_utility.gui.coquille import Coquille
from mixed_media_utility.io import project_layout

_PAQUET_GUI = Path(zone_tampon.__file__).resolve().parent

#: Les modules de PRODUCTION que cette story pose ou modifie -- « le chemin de
#: detection de `gui/` ». Les balayages de decoupage (garde 2) portent sur eux
#: et pas sur `gui/` entier, et la raison est mesurable : `coquille.py` et
#: `jetons.py` portent `splitter` (la poignee Qt), et `modele_chutier.py` lit
#: `manifest['lots']` -- une CLE de manifest, pas une partition locale. Un
#: balayage qui les inclurait serait rouge sans qu'aucun decoupage n'existe,
#: donc inapplicable, donc supprime. La garde 8, elle, porte bien sur `gui/`
#: **entier** : aucun module n'a d'excuse pour appeler la CLI.
_MODULES_DE_LA_STORY = (
    "modele_zone_tampon.py",
    "zone_tampon.py",
    "cartes_taches.py",
    "atelier_scan.py",
    "chargeur_detections.py",
)

#: Revue de vague 3, F7 -- les cinq modules de PRODUCTION que 7.4 a ajoutes
#: dans la MEME vague (`EPIC7-ARB-54` : sur l'Epic 7, l'unite de revue est la
#: vague, pas la story). L'interdit de decoupage local (garde 2, ci-dessous)
#: ne vaut pas moins pour eux que pour les modules de 7.3 : le mutant M6b
#: (une fonction `_par_lot(pages)` avec `lots = {}` et `.split(` plantee dans
#: `scan_jugement.py`) laissait les 404 tests GUI verts avant ce correctif.
#:
#: **Peremption, nommee explicitement (politique section 7).** Cette liste
#: est bornee des DEUX cotes : elle couvre la surface reelle de la vague 3
#: (7.3 + 7.4), ni plus ni moins. Elle n'est PAS auto-decouverte -- une story
#: ulterieure qui ajoute un nouveau module `gui/` manipulant des lots (7.5,
#: 7.6, ...) devra l'y ajouter a la main, sans quoi la garde redeviendrait
#: aveugle sur ce module neuf exactement comme elle l'etait ici sur 7.4. Ce
#: n'est pas un oubli silencieux : c'est le meme choix assume que celui de
#: `_MODULES_DE_LA_STORY` juste au-dessus, etendu a la vague plutot qu'a la
#: story.
_MODULES_DE_LA_VAGUE_7_4 = (
    "scan_jugement.py",
    "surimpressions.py",
    "barre_de_vue.py",
    "lecture_detection.py",
    "raster_de_page.py",
)

#: Le decoupage d'une pile en lot n'appartient pas a `gui/` : c'est une
#: fonction du coeur (5.24, AC 1). L'interface MONTRE le resultat du tri, elle
#: ne le refait jamais (`EPIC7-ARB-64`, AC 8c).
_MOTIFS_DE_DECOUPAGE = ("split", "lots", "par_lot")

#: La GUI n'ecrit aucun document elle-meme : ni document de detection, ni
#: ecriture atomique. Le coeur ecrit, l'interface lit.
_MOTIFS_D_ECRITURE = (
    "canonical_json", "build_scan_previz", "os.replace", "NamedTemporaryFile")

#: `EPIC7-ARB-64`, interdit (1) : « Aucune story de l'Epic 7 ne reintroduit un
#: appel de la GUI vers la CLI par sous-processus, ni une lecture de
#: `stdout`/`stderr`. »
_MOTIFS_DE_CLI = ("subprocess", "Popen", "std" + "out", "std" + "err")

#: Une couleur ecrite en dur. Aucune n'existe hors de `gui/jetons.py`.
_HEXADECIMAL = re.compile(r"#[0-9A-Fa-f]{6}\b")


def _sources_de_la_story() -> list[Path]:
    sources = [_PAQUET_GUI / nom for nom in _MODULES_DE_LA_STORY]
    for source in sources:
        assert source.exists(), source
    return sources


def _sources_de_la_vague() -> list[Path]:
    """`_sources_de_la_story()` plus les cinq modules neufs de 7.4 (F7).

    Garde 2 (decoupage) SEULEMENT : les gardes 4/5 (couleur, geometrie hors
    jetons, libelle hors catalogue) restent scopees a 7.3 -- 7.4 a son
    propre catalogue de tokens et sa propre discipline de test, non touchee
    par ce correctif.
    """
    sources = [_PAQUET_GUI / nom for nom in _MODULES_DE_LA_VAGUE_7_4]
    for source in sources:
        assert source.exists(), source
    return _sources_de_la_story() + sources


def _tous_les_modules_gui() -> list[Path]:
    modules = sorted(_PAQUET_GUI.rglob("*.py"))
    assert len(modules) > 10, "le balayage doit couvrir le paquet gui entier"
    return modules


def _balayer(texte: str, motifs) -> list[str]:
    return [motif for motif in motifs if motif in texte]


@pytest.fixture
def module_temoin(tmp_path) -> Path:
    """Un module FAUTIF, fabrique pour que chaque balayage ait de quoi mordre.

    Il porte, en une quinzaine de lignes, exactement ce que les six balayages
    de ce banc interdisent : un decoupage local d'une pile en lot, une
    ecriture de document, un appel a la CLI par sous-processus, une couleur en
    dur, une geometrie en dur, et un libelle visible hors catalogue.
    """
    chemin = tmp_path / "module_temoin_fautif.py"
    chemin.write_text(
        "import subprocess\n"
        "from tempfile import NamedTemporaryFile\n"
        "\n"
        "def decouper(pile):\n"
        "    lots = {}\n"
        "    for page in pile:\n"
        "        lots.setdefault(page.lot_id, []).append(page)\n"
        "    par_lot = dict(lots)\n"
        "    return [p.split('-') for p in par_lot]\n"
        "\n"
        "def ecrire(chemin, document):\n"
        "    from mixed_media_utility.previz_common import canonical_json\n"
        "    from mixed_media_utility.scan_previz import build_scan_previz\n"
        "    with NamedTemporaryFile() as fichier:\n"
        "        fichier.write(canonical_json(build_scan_previz()).encode())\n"
        "    import os\n"
        "    os.replace(fichier.name, chemin)\n"
        "\n"
        "def lancer():\n"
        "    sortie = subprocess.Popen(['mixed-media-util'])\n"
        "    return sortie.std" "out.read(), sortie.std" "err.read()\n"
        "\n"
        "COULEUR = '#4C7EF3'\n"
        "LARGEUR = 320\n"
        "BOUTON = 'Détecter'\n",
        encoding="utf-8")
    return chemin


# ---------------------------------------------------------------------------
# 1 -- zero ecriture de TIFF depuis cet ecran (l'extraction est 7.6)
# ---------------------------------------------------------------------------


def test_zero_ecriture_de_tiff_depuis_cet_ecran(qtbot, tmp_path):
    # (a) aucun module de `gui/` n'importe le module d'ecriture de frames.
    fautifs = {
        module.name for module in _tous_les_modules_gui()
        if "scan_output_frames" in module.read_text(encoding="utf-8")
    }
    assert fautifs == set(), fautifs

    # (b) et apres une detection COMPLETE sur la fixture, le dossier de sortie
    # compte zero fichier -- comptage reel, jamais un drapeau.
    manifest = fab.manifest_des_deux_lot()
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(
        __import__("json").dumps(manifest), encoding="utf-8")
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    fenetre.atelier_scan._detecter = fab.detection_qui_ecrit(
        list(fab.deux_documents_aux_completudes_differentes()))
    fenetre.ouvrir_projet(projet, manifest)
    dossier, _pdf, _image = fab.trois_chemins_distinguables(tmp_path)
    entrees = fenetre.zone_tampon.deposer_des_chemins([dossier])
    fenetre.zone_tampon.modele.poser_le_dpi(entrees[0].identifiant, 600)
    fenetre.zone_tampon.rafraichir()
    fenetre.zone_tampon.bouton_detecter.click()
    qtbot.waitUntil(
        lambda: len(fenetre.atelier_scan.annonces()) == 2, timeout=5000)

    sortie = projet / project_layout.OUTPUT_FRAMES_DIRNAME
    ecrits = [c for c in sortie.rglob("*") if c.is_file()] if sortie.is_dir() else []
    assert ecrits == [], ecrits
    # Temoin : la passe a bien produit quelque chose -- sinon « zero TIFF »
    # serait vrai d'une interface qui ne detecterait rien.
    assert len(chargeur_detections.chemins_de_documents(projet)) == 2


# ---------------------------------------------------------------------------
# 2 -- le decoupage en lot vient du coeur, jamais de gui/
# ---------------------------------------------------------------------------


def test_le_decoupage_en_lots_vient_du_coeur():
    # Revue de vague 3, F7 : la surface de decoupage est celle de la VAGUE
    # (7.3 + 7.4), pas seulement celle de 7.3 -- deux stories ecrites en
    # parallele, l'une pose une frontiere que l'autre traversait sans que ce
    # balayage le voie (M6b, plante dans `scan_jugement.py`, 404 tests verts).
    fautifs = {}
    for source in _sources_de_la_vague():
        trouves = _balayer(source.read_text(encoding="utf-8"),
                           _MOTIFS_DE_DECOUPAGE)
        if trouves:
            fautifs[source.name] = trouves
    assert fautifs == {}, f"decoupage local dans gui/ : {fautifs}"

    # Volet POSITIF, et il n'est pas decoratif : aucun module de `gui/`
    # n'appelle la fonction de tri du coeur non plus. L'interface lit ce que le
    # coeur a ECRIT (documents et rapport de tri), elle ne rejoue pas le tri.
    for module in _tous_les_modules_gui():
        assert "trier_les_pages" not in module.read_text(encoding="utf-8"), module.name


def test_la_garde_du_decoupage_mord_sur_un_decoupage_local(module_temoin):
    """Le volet symetrique EXIGE par la fiche.

    Sans lui, la garde ci-dessus passerait aussi bien sur une interface qui ne
    detecterait rien du tout : un module vide ne contient aucun de ces mots.
    """
    trouves = _balayer(module_temoin.read_text(encoding="utf-8"),
                       _MOTIFS_DE_DECOUPAGE)
    assert set(trouves) == set(_MOTIFS_DE_DECOUPAGE), trouves


def test_le_resultat_du_tri_est_bien_LU_et_non_recompose():
    """Symetrique de fond : la GUI lit le rapport de tri par son lecteur.

    Le grep de mots dit ce qui n'est pas ecrit ; celui-ci dit ce qui EST fait,
    et c'est la moitie qui empeche la garde d'etre satisfaite par le vide.
    """
    source = Path(chargeur_detections.__file__).read_text(encoding="utf-8")
    assert "rapport_from_json_dict" in source
    assert "scan_previz_from_json_dict" in source


# ---------------------------------------------------------------------------
# 3 -- aucun badge de deduction (EPIC7-ARB-14)
# ---------------------------------------------------------------------------


def test_zero_badge_de_deduction():
    # Le vocabulaire de badges du chutier est INCHANGE : trois etats, ceux de
    # la completude, et rien d'autre.
    assert modele_chutier.BADGES_DE_COMPLETUDE == (
        modele_chutier.BADGE_COMPLET,
        modele_chutier.BADGE_COMPLET_AVEC_MIRES,
        modele_chutier.BADGE_INCOMPLET,
    )
    assert modele_chutier.GLYPHES_DE_RATTACHEMENT == (
        modele_chutier.GLYPHE_DELIE,
        modele_chutier.GLYPHE_NON_RATTACHE,
        modele_chutier.GLYPHE_INCOMPLET,
    )
    # Aucune cle de catalogue neuve en `badge-` ni en `glyphe-` : la deduction
    # d'une forme est une PHRASE de ligne, jamais un signe de plus.
    badges = {cle for cle in catalogue.CHAINES if cle.startswith("badge-")}
    glyphes = {cle for cle in catalogue.CHAINES if cle.startswith("glyphe-")}
    assert badges == {"badge-complet", "badge-complet-avec-mires", "badge-incomplet"}
    assert glyphes == {"glyphe-delie", "glyphe-non-rattache", "glyphe-incomplet"}
    # Et le mot « deduite » ne vit que dans une phrase de la file.
    deductions = {
        cle for cle, valeur in catalogue.CHAINES.items()
        if "déduite" in valeur.lower()
    }
    assert deductions == {"zone-tampon-forme-deduite"}, deductions


# ---------------------------------------------------------------------------
# 4 -- zero couleur, zero geometrie hors jetons ; zero libelle hors catalogue
# ---------------------------------------------------------------------------


def test_zero_couleur_et_zero_geometrie_hors_jetons():
    fautifs = {}
    for source in _sources_de_la_story():
        texte = source.read_text(encoding="utf-8")
        couleurs = _HEXADECIMAL.findall(texte)
        if couleurs:
            fautifs[source.name] = couleurs
    assert fautifs == {}, f"couleur en dur : {fautifs}"

    # La geometrie : aucun entier de mise en page ecrit en dur. Les seuls
    # nombres tolerés sont 0 et 1 (marges nulles, facteurs d'etirement, index),
    # tout le reste se LIT dans `jetons`.
    geometries = {}
    for source in _sources_de_la_story():
        arbre = ast.parse(source.read_text(encoding="utf-8"))
        nombres = [
            noeud.value for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Constant)
            and isinstance(noeud.value, int)
            and not isinstance(noeud.value, bool)
            and noeud.value not in (0, 1)
        ]
        if nombres:
            geometries[source.name] = nombres
    assert geometries == {}, f"geometrie en dur : {geometries}"

    # Temoin : les modules LISENT bien des jetons, sans quoi « zero litteral »
    # serait vrai d'un module qui ne mettrait rien en page.
    lecteurs = [
        source.name for source in _sources_de_la_story()
        if "jetons." in source.read_text(encoding="utf-8")
    ]
    assert len(lecteurs) >= 3, lecteurs


def test_zero_libelle_visible_hors_catalogue():
    """Aucune chaine affichable en dur dans les surfaces de la story.

    Le balayage porte sur les appels Qt qui POSENT un texte visible
    (`setText`, `setToolTip`, `setPlaceholderText`, `setAccessibleName`, et les
    constructeurs de `QLabel`/`QPushButton`/`QCheckBox`) : un litteral y est un
    libelle en dur, ou qu'il soit ecrit.
    """
    poseurs = {
        "setText", "setToolTip", "setPlaceholderText", "setAccessibleName",
        "setWindowTitle",
    }
    constructeurs = {"QLabel", "QPushButton", "QCheckBox", "QToolButton"}
    fautifs = {}
    for source in _sources_de_la_story():
        arbre = ast.parse(source.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            nom = getattr(noeud.func, "attr", None) or getattr(
                noeud.func, "id", None)
            if nom not in poseurs | constructeurs:
                continue
            for argument in noeud.args:
                if (isinstance(argument, ast.Constant)
                        and isinstance(argument.value, str)
                        and argument.value != ""):
                    fautifs.setdefault(source.name, []).append(argument.value)
    assert fautifs == {}, f"libelle en dur : {fautifs}"

    # Temoin : ces modules posent bien des textes -- venus du catalogue.
    poseurs_reels = [
        source.name for source in _sources_de_la_story()
        if "setText(" in source.read_text(encoding="utf-8")
    ]
    assert len(poseurs_reels) >= 2, poseurs_reels


# ---------------------------------------------------------------------------
# 5 -- le bouton Detecter n'est pas dans la previz
# ---------------------------------------------------------------------------


def test_le_bouton_detecter_n_est_pas_dans_la_previz():
    libelle = catalogue.CHAINES["zone-tampon-detecter"]
    assert libelle
    # Le libelle ne se lit que dans la file : ni l'atelier, ni les cartes, ni
    # aucune autre surface de `gui/` ne le pose. La cle est cherchee EXACTE --
    # `zone-tampon-detecter-sans-dpi` est une phrase d'inactivite, rendue par
    # le modele pur, et non le libelle du bouton.
    cle_exacte = re.compile(r"zone-tampon-detecter(?!-)")
    fautifs = {
        module.name for module in _tous_les_modules_gui()
        if module.name not in ("catalogue.py", "zone_tampon.py")
        and cle_exacte.search(module.read_text(encoding="utf-8"))
    }
    assert fautifs == set(), fautifs
    # Et une seule cle de catalogue porte ce verbe.
    portant = {
        cle for cle, valeur in catalogue.CHAINES.items()
        if valeur.strip() == libelle
    }
    assert portant == {"zone-tampon-detecter"}, portant


def test_le_bouton_n_est_pas_un_enfant_de_la_scene(qtbot):
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    bouton = fenetre.zone_tampon.bouton_detecter
    parent = bouton
    ancetres = []
    while parent is not None:
        ancetres.append(parent)
        parent = parent.parentWidget()
    assert fenetre.zone_tampon in ancetres
    assert fenetre.scene not in ancetres
    assert fenetre.pile_ateliers not in ancetres


# ---------------------------------------------------------------------------
# 6 -- la GUI n'ecrit aucun document elle-meme
# ---------------------------------------------------------------------------


def test_la_gui_n_ecrit_aucun_document_elle_meme():
    fautifs = {}
    for module in _tous_les_modules_gui():
        trouves = _balayer(module.read_text(encoding="utf-8"),
                           _MOTIFS_D_ECRITURE)
        if trouves:
            fautifs[module.name] = trouves
    assert fautifs == {}, f"ecriture de document dans gui/ : {fautifs}"


# ---------------------------------------------------------------------------
# 8 -- la GUI n'appelle jamais la CLI (EPIC7-ARB-64, interdit 1)
# ---------------------------------------------------------------------------


def test_la_gui_n_appelle_jamais_la_cli():
    fautifs = {}
    for module in _tous_les_modules_gui():
        trouves = _balayer(module.read_text(encoding="utf-8"), _MOTIFS_DE_CLI)
        if trouves:
            fautifs[module.name] = trouves
    assert fautifs == {}, f"appel de la CLI depuis gui/ : {fautifs}"

    # Volet positif : la GUI appelle bien le coeur EN PROCESSUS, par import.
    source = Path(atelier_scan.__file__).read_text(encoding="utf-8")
    assert "from .. import scan_detect" in source
    assert "scan_detect.run_scan_detect" in source


# ---------------------------------------------------------------------------
# 9 -- le banc MORD : chaque balayage voit le module temoin
# ---------------------------------------------------------------------------


def test_la_frontiere_mord_sur_un_module_temoin(module_temoin):
    texte = module_temoin.read_text(encoding="utf-8")

    # (2) decoupage local, (6) ecriture de document, (8) appel de la CLI.
    for famille, motifs in (
        ("decoupage", _MOTIFS_DE_DECOUPAGE),
        ("ecriture", _MOTIFS_D_ECRITURE),
        ("cli", _MOTIFS_DE_CLI),
    ):
        trouves = _balayer(texte, motifs)
        assert set(trouves) == set(motifs), (famille, trouves)

    # (1) ecriture de frames.
    assert "scan_output_frames" not in texte
    temoin_de_frames = texte + "\nfrom mixed_media_utility import scan_output_frames\n"
    assert "scan_output_frames" in temoin_de_frames

    # (4) couleur en dur, geometrie en dur, libelle en dur.
    assert _HEXADECIMAL.findall(texte) == ["#4C7EF3"]
    arbre = ast.parse(texte)
    nombres = [
        noeud.value for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, int)
        and not isinstance(noeud.value, bool) and noeud.value not in (0, 1)
    ]
    assert nombres == [320], nombres
    assert "Détecter" in texte

    # Et la contre-epreuve : les modules de la story, eux, ne portent rien de
    # tout cela. Sans cette moitie, le temoin prouverait que le banc sait
    # trouver, sans dire ce qu'il trouve dans le vrai code.
    for source in _sources_de_la_story():
        vrai = source.read_text(encoding="utf-8")
        assert _balayer(vrai, _MOTIFS_D_ECRITURE) == []
        assert _balayer(vrai, _MOTIFS_DE_CLI) == []


# ---------------------------------------------------------------------------
# AC 2d -- aucun dpi par defaut dans la GUI (revue de vague 3, F12,
# `EPIC7-ARB-44`)
# ---------------------------------------------------------------------------

#: Un litteral de dpi assigne EN DUR (``dpi=300``, ``DPI_X = 300``) --
#: jamais une simple lecture ou transmission (``dpi=entree.dpi``,
#: ``dpi=self.dpi_de_detection``) ni un nom de variable/parametre sans
#: chiffre attache.
_DPI_LITTERAL = re.compile(r"(?i)\bdpi\w*\s*=\s*\d+")

#: **Exception NOMMEE et JUSTIFIEE, a sa ligne precise** (politique section
#: 8) -- la seule que ce balayage tolere.
#:
#: `executeur.py:168 DPI_DEMONSTRATION = 300` alimente uniquement
#: `tache_de_demonstration`, un banc qui prouve l'hebergement in-process de
#: l'executeur (AC 4/AC 5 de la story 7.0, deja close) en appelant une
#: fonction REELLE et bon marche du coeur (`scan_crop.build_page_crop_plan`).
#: Verifie (revue de vague 3, F12) : `tache_de_demonstration` n'est appelee
#: **nulle part** dans `src/` hors sa propre definition -- grep :
#: `grep -rn "tache_de_demonstration" src/` ne rend que sa signature et son
#: unique appel interne. Le chemin nominal de detection, lui, reste
#: gouverne par `modele_zone_tampon.py` (« Le dpi est obligatoire et sans
#: defaut », `EPIC7-ARB-44`) : aucun dpi n'y est jamais invente, le bouton
#: `Detecter` reste inactif tant que l'operatrice n'a pas saisi le sien.
#: `DPI_DEMONSTRATION` n'atteint donc jamais ce chemin -- ce n'est pas le
#: defaut que l'AC 2d interdit.
#:
#: Le retirer proprement demanderait de faire de `dpi` un parametre EXPLICITE
#: de `tache_de_demonstration`, ce qui casserait les appels sans argument de
#: `tests/unit/gui/test_executeur.py` -- hors perimetre de ce lot de revue
#: (fichier d'un autre agent). D'ou le choix : documenter l'exception plutot
#: que la faire disparaitre a l'aveugle.
_EXCEPTIONS_DPI = {
    ("executeur.py", 168): (
        "DPI_DEMONSTRATION -- litteral du seul banc de demonstration de "
        "l'executeur (AC 4/AC 5 de 7.0), jamais appele hors de sa propre "
        "definition et des tests : n'atteint jamais le chemin nominal de "
        "detection ou le dpi reste obligatoire et sans defaut."
    ),
}


def test_aucun_dpi_par_defaut_dans_la_gui():
    """AC 2d de la story 7.3, `EPIC7-ARB-44` -- absent du depot avant ce correctif.

    Trouve par la revue de vague 3 (F12) : ce test, nomme par l'AC, etait
    absent (`grep -rn "aucun_dpi_par_defaut" tests/` -> 0), et un litteral de
    dpi existait bel et bien (`gui/executeur.py:168 DPI_DEMONSTRATION = 300`),
    Task 3 pourtant cochee. Ce balayage tolere une seule exception, NOMMEE et
    JUSTIFIEE a sa ligne precise : voir `_EXCEPTIONS_DPI` ci-dessus.
    """
    fautifs = {}
    for module in _tous_les_modules_gui():
        texte = module.read_text(encoding="utf-8")
        for numero, ligne in enumerate(texte.splitlines(), start=1):
            if not _DPI_LITTERAL.search(ligne):
                continue
            if (module.name, numero) in _EXCEPTIONS_DPI:
                continue
            fautifs.setdefault(module.name, []).append((numero, ligne.strip()))
    assert fautifs == {}, f"litteral de dpi en dur dans gui/ : {fautifs}"

    # Volet de peremption : chaque exception doit encore pointer sur un
    # VRAI litteral de dpi -- sans cette moitie, une exception perimee (le
    # litteral deplace ou supprime par un correctif ulterieur) resterait
    # invisible et couvrirait n'importe quelle ligne par erreur.
    for (nom_fichier, numero), justification in _EXCEPTIONS_DPI.items():
        assert justification
        chemin = _PAQUET_GUI / nom_fichier
        lignes = chemin.read_text(encoding="utf-8").splitlines()
        assert 1 <= numero <= len(lignes), (nom_fichier, numero)
        assert _DPI_LITTERAL.search(lignes[numero - 1]), (
            f"l'exception {nom_fichier}:{numero} ne pointe plus sur un "
            "litteral de dpi -- a retirer ou reancrer"
        )


def test_la_garde_du_dpi_mord_sur_un_litteral_fabrique():
    """Le volet symetrique EXIGE : sans lui, la garde passerait aussi sur le vide."""
    assert _DPI_LITTERAL.search("DPI_PROPOSE_PAR_DEFAUT = 300")
    assert _DPI_LITTERAL.search("    dpi=300,")
    # Une simple LECTURE ou transmission ne mord pas -- sinon la garde
    # interdirait de faire circuler un dpi deja saisi par l'operatrice, ce
    # que l'AC exige au contraire.
    assert not _DPI_LITTERAL.search("dpi=entree.dpi")
    assert not _DPI_LITTERAL.search("self.dpi_de_detection = int(dpi_de_detection)")
