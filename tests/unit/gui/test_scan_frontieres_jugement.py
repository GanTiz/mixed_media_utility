# -*- coding: utf-8 -*-
"""Story 7.4, AC 9 -- lecture seule : aucune edition, aucune ecriture.

« Elle LIT. » Cette story ne modifie ni le document de detection, ni le
manifeste, ni aucun fichier du projet. Un clic sur une zone **designe** ; il
n'ouvre pas de poignees -- l'edition manuelle est **7.5**, l'ecriture des TIFF
**7.6**.

Ce qu'elle livre en revanche, et qui se mesure : **la prise**. L'adresse
complete ``(read_rank, page_index, slot_index)`` est portee **jusqu'au
widget** ; ce qui manque en 7.4, c'est le geste d'ecriture, pas la prise.
"""

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

import fabriques_detection as fab
from mixed_media_utility.gui import catalogue, jetons
from mixed_media_utility.gui import lecture_detection as lecture
from mixed_media_utility.gui import scan_jugement

_PAQUET_GUI = Path(jetons.__file__).resolve().parent
_RACINE_DEPOT = _PAQUET_GUI.parents[2]

# La regle de regime -- « une reference de perimetre inatteignable est-elle un
# historique tronque, ou un AUTRE depot ? » -- vit dans `tests/_regime_du_depot.py`,
# ecrite une fois pour ses sept appelants.
import sys as _sys
_sys.path.insert(0, str(_RACINE_DEPOT / "tests"))
from _regime_du_depot import echoue_ou_saute  # noqa: E402

#: Les modules de PRODUCTION de cette story.
MODULES_DE_LA_STORY = (
    "scan_jugement.py",
    "surimpressions.py",
    "barre_de_vue.py",
    "lecture_detection.py",
    "raster_de_page.py",
)


# ---------------------------------------------------------------------------
# Grep de frontiere sur le DIFF de la story (mecanisme du socle 7.0)
# ---------------------------------------------------------------------------

#: `baseline_commit` de la fiche 7.4. Un commit RECENT de la branche de
#: travail, donc atteignable dans un clone superficiel -- contrairement aux
#: commits de reference plus anciens (5.19/5.22/5.23) qui font echouer six
#: tests preexistants (`deferred-work.md`).
_BASELINE_7_4 = "3b36163"

#: Prefixe conventionnel des messages de commit de cette story, verifie sur
#: l'historique reel avant d'etre fige ici. Il isole les commits DE CETTE
#: STORY dans un historique partage : la story 7.3 est developpee EN
#: PARALLELE sur la MEME branche, avec la MEME baseline, et ses commits
#: touchent legitimement `cli.py`, `gui/coquille.py` et `gui/atelier_scan.py`.
_PREFIXE_COMMITS_STORY = "story 7.4"


def _commits_de_la_story(baseline=_BASELINE_7_4, prefixe=_PREFIXE_COMMITS_STORY):
    """Hashes des commits de cette story entre `baseline` (exclu) et HEAD.

    L'echec est **dur** (jamais un `skip`) sur un baseline inatteignable : un
    `skip` se lirait comme un vert alors que la frontiere devrait s'evaluer
    et ne le fait pas.
    """
    try:
        sortie = subprocess.run(
            ["git", "log", "--format=%H %s", f"{baseline}..HEAD"],
            cwd=_RACINE_DEPOT, capture_output=True, text=True, check=True,
            timeout=60,
        ).stdout
    except (subprocess.SubprocessError, OSError) as erreur:
        echoue_ou_saute(
            _RACINE_DEPOT, baseline,
            f"commit de reference {baseline} inatteignable ({erreur}) : la "
            "frontiere AC 9 ne s'evalue pas, et un skip se lirait comme un "
            "vert -- clone superficiel ou historique tronque"
        )
    hashes = []
    for ligne in sortie.splitlines():
        hash_commit, _, message = ligne.partition(" ")
        if message.startswith(prefixe):
            hashes.append(hash_commit)
    return hashes


def _fichiers_touches_par(hashes):
    fichiers = set()
    for hash_commit in hashes:
        try:
            sortie = subprocess.run(
                ["git", "show", "--name-only", "--format=", hash_commit],
                cwd=_RACINE_DEPOT, capture_output=True, text=True, check=True,
                timeout=60,
            ).stdout
        except (subprocess.SubprocessError, OSError) as erreur:
            pytest.fail(f"commit {hash_commit} illisible ({erreur})")
        fichiers.update(ligne for ligne in sortie.splitlines() if ligne)
    return fichiers


def _hors_perimetre(touches):
    """Les chemins hors du perimetre autorise de cette story.

    **Le perimetre, et pourquoi il est ecrit ainsi.** L'AC 9 demande « zero
    hunk hors de `gui/` et de `tests/unit/gui/` ». Prise a la lettre, cette
    formule interdirait aussi les deux livrables que l'AC 7 EXIGE -- une
    capture de reference versionnee et un document de detection de fixture,
    qui vivent l'un et l'autre sous `tests/fixtures/` -- et la mise a jour du
    suivi d'avancement, que le depot impose « dans le meme mouvement ». Ce
    que la frontiere protege reellement est le COEUR : c'est ainsi qu'elle
    est ecrite au socle 7.0 (« zero hunk hors de
    `src/mixed_media_utility/gui/` »). On la garde a cette portee-la, et on
    borne explicitement le reste a `tests/` et aux artefacts BMad.
    """
    autorises = (
        "src/mixed_media_utility/gui/",
        "tests/unit/gui/",
        "tests/fixtures/",
        "_bmad-output/",
    )
    return sorted(
        chemin for chemin in touches
        if not chemin.startswith(autorises)
    )


def test_zero_hunk_hors_de_gui_dans_les_modules_du_coeur():
    hashes = _commits_de_la_story()
    assert hashes, (
        "aucun commit 'story 7.4' trouve depuis le baseline : la frontiere "
        "ne mesurerait rien"
    )
    touches = _fichiers_touches_par(hashes)
    assert touches, "aucun fichier touche : la frontiere ne mesurerait rien"
    coeur = sorted(
        chemin for chemin in touches
        if chemin.startswith("src/mixed_media_utility/")
        and not chemin.startswith("src/mixed_media_utility/gui/")
    )
    assert coeur == [], f"hunk hors de gui/ dans un module du coeur : {coeur}"
    assert _hors_perimetre(touches) == [], _hors_perimetre(touches)


def test_la_frontiere_du_diff_MORD_sur_un_fichier_du_coeur():
    """Le second volet, symetrique, exerce sans toucher au vrai depot git."""
    conforme = {
        "src/mixed_media_utility/gui/scan_jugement.py",
        "tests/unit/gui/test_scan_mode_pdf.py",
        "tests/fixtures/captures-gui/scan-mode-pdf.png",
    }
    assert _hors_perimetre(conforme) == []
    intrus = conforme | {"src/mixed_media_utility/scan_detection.py"}
    assert _hors_perimetre(intrus) == ["src/mixed_media_utility/scan_detection.py"]


# ---------------------------------------------------------------------------
# Aucune ecriture dans les modules de la story
# ---------------------------------------------------------------------------


def _appels_de(nom_de_module):
    arbre = ast.parse((_PAQUET_GUI / nom_de_module).read_text(encoding="utf-8"))
    appels = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call):
            appels.add(
                noeud.func.attr
                if isinstance(noeud.func, ast.Attribute)
                else getattr(noeud.func, "id", "")
            )
    return appels


def test_zero_ecriture_dans_les_modules_de_la_story():
    ecritures = {
        "open", "write_text", "write_bytes", "replace", "mkdir", "dump",
        "dumps", "rename", "unlink", "rmtree", "copy2", "save",
    }
    fautifs = {}
    for nom in MODULES_DE_LA_STORY:
        trouves = sorted(_appels_de(nom) & ecritures)
        if trouves:
            fautifs[nom] = trouves
    assert fautifs == {}, f"ecriture dans un module de la story : {fautifs}"


def test_zero_import_de_module_d_ecriture():
    interdits = {"scan_write", "scan_crop", "scan_manifest", "cli"}
    fautifs = {}
    for nom in MODULES_DE_LA_STORY:
        arbre = ast.parse((_PAQUET_GUI / nom).read_text(encoding="utf-8"))
        importes = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom):
                importes.update(alias.name for alias in noeud.names)
                importes.add((noeud.module or "").split(".")[-1])
            elif isinstance(noeud, ast.Import):
                importes.update(alias.name.split(".")[-1] for alias in noeud.names)
        trouves = sorted(importes & interdits)
        if trouves:
            fautifs[nom] = trouves
    assert fautifs == {}, f"import d'un module d'ecriture : {fautifs}"


def test_le_grep_d_ecriture_MORD_sur_un_temoin():
    """Le symetrique : sans lui, le grep pourrait etre vert et vide."""
    temoin = ast.parse('chemin.write_text("x")\nPath("d").mkdir()\n')
    appels = {
        noeud.func.attr for noeud in ast.walk(temoin)
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
    }
    assert {"write_text", "mkdir"} <= appels


# ---------------------------------------------------------------------------
# Un clic DESIGNE, il n'ouvre aucune poignee (7.5)
# ---------------------------------------------------------------------------


def _atelier(qtbot, document):
    atelier = scan_jugement.AtelierScanJugement(catalogue.CHAINES)
    qtbot.addWidget(atelier)
    atelier.resize(1200, 800)
    atelier.show()
    atelier.poser_document(
        document, document.page_par_adresse(*fab.ADRESSE_CIBLE)
    )
    return atelier


def test_un_clic_sur_une_zone_DESIGNE_et_n_instancie_aucune_poignee(qtbot):
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    atelier = _atelier(qtbot, document)
    legendes = sorted(
        atelier.vue_page.legendes.findChildren(scan_jugement.LegendeDeZone),
        key=lambda widget: widget.slot_index,
    )
    assert len(legendes) == 2
    # La SECONDE : un rendu qui prendrait toujours la premiere ne se
    # demasque pas autrement.
    qtbot.mouseClick(legendes[1], Qt.MouseButton.LeftButton)
    rang, index = fab.ADRESSE_CIBLE
    assert atelier.vue_page.designation == (rang, index, 1)

    # ZERO poignee, ZERO loupe dans l'arbre de widgets.
    noms = {
        widget.objectName().lower()
        for widget in atelier.findChildren(QWidget)
    }
    noms |= {type(widget).__name__.lower() for widget in atelier.findChildren(QWidget)}
    for interdit in ("poignee-de-coin", "loupe", "handle-de-zone"):
        assert not any(interdit in nom for nom in noms), interdit
    # Le seul « poignee » admis est celle du panneau lateral, qui n'est pas
    # une poignee d'EDITION : le test la nomme pour que la distinction reste
    # explicite.
    assert "poignee-panneau-lateral" in noms


def test_l_adressage_complet_est_porte_JUSQU_AU_WIDGET(qtbot):
    """La prise de 7.5 existe : ce qui manque, c'est le geste d'ecriture."""
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    atelier = _atelier(qtbot, document)
    rang, index = fab.ADRESSE_CIBLE
    for legende in atelier.vue_page.legendes.findChildren(
        scan_jugement.LegendeDeZone
    ):
        assert legende.adresse == (rang, index, legende.slot_index)
        assert len(legende.adresse) == 3
    # Et sur les cases de galerie aussi.
    for ligne in atelier.vue_galerie.lignes:
        for case in ligne.cases:
            assert case.adresse == (
                ligne.page.page.read_rank,
                ligne.page.page.page_index,
                case.slot_index,
            )
    # Les trois champs sont ceux que `scan_previz` declare stables.
    from mixed_media_utility import scan_previz

    assert scan_previz.FRAME_ZONE_ADDRESS_FIELDS == (
        "read_rank", "page_index", "slot_index"
    )


# ---------------------------------------------------------------------------
# Un parcours complet ne touche a RIEN sur le disque
# ---------------------------------------------------------------------------


def test_un_parcours_complet_laisse_le_document_inchange_OCTET_POUR_OCTET(
    qtbot, tmp_path
):
    projet = tmp_path / "projet"
    detections = projet / "scans" / "lot" / "detections"
    detections.mkdir(parents=True)
    chemin = detections / "detect-20260825T120000Z.json"
    chemin.write_text(
        json.dumps(fab.deux_pages_cible_seconde()), encoding="utf-8"
    )
    avant_condensat = hashlib.sha256(chemin.read_bytes()).hexdigest()
    avant_arbre = sorted(str(p.relative_to(projet)) for p in projet.rglob("*"))

    document = lecture.charger(chemin)
    atelier = _atelier(qtbot, document)
    rang, index = fab.ADRESSE_CIBLE
    # Parcours complet : ouvrir, zoomer, changer d'onglet, ouvrir une
    # vignette, revenir.
    atelier.vue_page.barre_de_vue.zoom.setValue(180)
    atelier.onglets.activer("galerie")
    atelier.vue_galerie.zoom_vignettes.setValue(140)
    atelier.ouvrir_la_frame((rang, index, 1))
    atelier.vue_frame.barre_de_vue.zoom.setValue(220)
    atelier.onglets.activer("page")
    atelier.vue_page.designer((rang, index, 0))

    assert hashlib.sha256(chemin.read_bytes()).hexdigest() == avant_condensat
    apres_arbre = sorted(str(p.relative_to(projet)) for p in projet.rglob("*"))
    assert apres_arbre == avant_arbre, (
        "le repertoire du projet porte un fichier neuf : cette story LIT"
    )


def test_la_designation_et_le_zoom_sont_des_donnees_de_SESSION(qtbot, tmp_path):
    """Elles ne sont jamais ecrites au projet.

    « La designation d'une zone, l'etat retracte d'un panneau et le facteur
    de zoom sont des donnees de session GUI. » Un nouvel atelier sur le meme
    document repart donc a zero.
    """
    document = lecture.depuis_json(fab.deux_pages_cible_seconde())
    premier = _atelier(qtbot, document)
    rang, index = fab.ADRESSE_CIBLE
    premier.vue_page.designer((rang, index, 1))
    premier.vue_page.barre_de_vue.zoom.setValue(300)

    second = _atelier(qtbot, document)
    assert second.vue_page.designation is None
    assert second.vue_page.barre_de_vue.zoom.value() != 300


# ---------------------------------------------------------------------------
# AC 1 -- aucun ecran ne decide sur la phrase de refus (revue de vague 3, F8)
# ---------------------------------------------------------------------------

#: `EPIC7-ARB-66` : `refusal_reason` est une phrase FRANCAISE destinee a
#: l'oeil, affichee verbatim. Aucun ecran n'a le droit d'en deriver une
#: decision -- ni sous-chaine, ni prefixe, ni suffixe, ni casse, ni regex.
#: Note de contexte (F8) : cette garde porte sur le BRANCHEMENT, pas sur le
#: texte affiche -- elle reste vraie que `EPIC7-ARB-75` (motif neutre
#: `scan-motif-refus-au-scan`, applique en parallele sur ce meme module)
#: choisisse telle ou telle phrase, tant qu'aucun ecran n'inspecte le
#: CONTENU de `refusal_reason` pour en decider.
_METHODES_DE_DERIVATION_DE_TEXTE = {
    "startswith", "endswith", "lower", "upper", "casefold",
    "strip", "lstrip", "rstrip", "split", "find", "index",
    "count", "replace", "match", "search", "fullmatch",
}


def _racine_est_refusal_reason(noeud: ast.AST) -> bool:
    """Vrai si `noeud`, remonte a travers ses appels et attributs, vient de
    `refusal_reason` -- couvre aussi bien `refusal_reason` seul que
    `page.page.refusal_reason` ou un chainage d'appels dessus."""
    if isinstance(noeud, ast.Name):
        return noeud.id == "refusal_reason"
    if isinstance(noeud, ast.Attribute):
        return noeud.attr == "refusal_reason" or _racine_est_refusal_reason(noeud.value)
    if isinstance(noeud, ast.Call):
        return _racine_est_refusal_reason(noeud.func)
    return False


def _decisions_sur_refusal_reason(source: str) -> list[str]:
    """Les branchements sur le CONTENU de `refusal_reason` trouves dans `source`.

    Deux familles, celles que le mutant M23b et sa famille exploitent :

    1. un appel de methode de derivation de texte CHAINE sur `refusal_reason`
       (``refusal_reason.lower().startswith("...")`` aussi bien qu'un appel
       simple) ;
    2. une comparaison litterale (``==``, ``!=``, ``in``, ``not in`` contre
       une chaine) ou l'un des operandes vient de `refusal_reason`.

    Une lecture simple (``phrase = page.page.refusal_reason``, un `f"..."`,
    un test de nullite ``is None``/``is not None``) ne mord PAS : ce n'est
    pas une decision sur le CONTENU, seulement sur la presence ou l'affichage.
    """
    trouvailles = []
    arbre = ast.parse(source)
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
                and noeud.func.attr in _METHODES_DE_DERIVATION_DE_TEXTE
                and _racine_est_refusal_reason(noeud.func.value)):
            trouvailles.append(f".{noeud.func.attr}(...)")
        elif (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
                and noeud.func.attr in {"match", "search", "fullmatch"}
                and isinstance(noeud.func.value, ast.Name)
                and noeud.func.value.id == "re"
                and any(_racine_est_refusal_reason(a) for a in noeud.args)):
            trouvailles.append(f"re.{noeud.func.attr}(...)")
        elif isinstance(noeud, ast.Compare):
            operandes = [noeud.left, *noeud.comparators]
            racines = any(_racine_est_refusal_reason(o) for o in operandes)
            litteraux = any(
                isinstance(o, ast.Constant) and isinstance(o.value, str)
                for o in operandes)
            textuel = any(
                isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn))
                for op in noeud.ops)
            if racines and litteraux and textuel:
                trouvailles.append("comparaison litterale")
    return trouvailles


def test_aucun_ecran_ne_decide_sur_la_phrase_de_refus():
    """AC 1 de la story 7.4, `EPIC7-ARB-66` -- absent du depot avant ce correctif.

    Trouve par la revue de vague 3 (F8) : la note de completion de la fiche
    affirmait que cette garde etait « portee par le grep d'anti-derivation
    de `test_scan_valeurs_de_zone.py` », qui ne contient AUCUNE occurrence de
    `refusal_reason` -- l'interdit d'`EPIC7-ARB-66` n'etait mesure par rien.
    Mutant M23b (``if refusal_reason.lower().startswith("qr illisible en
    zone"): return VERROU_INDETERMINE``) : SURVIVANT avant ce test.
    """
    fautifs = {}
    for module in sorted(_PAQUET_GUI.rglob("*.py")):
        trouvailles = _decisions_sur_refusal_reason(
            module.read_text(encoding="utf-8"))
        if trouvailles:
            fautifs[module.name] = trouvailles
    assert fautifs == {}, f"decision sur le contenu de refusal_reason : {fautifs}"


def test_la_garde_anti_derivation_mord_sur_M23b_reinjecte():
    """Le volet symetrique EXIGE : le mutant M23b, verbatim, doit mordre.

    Sans lui, la garde ci-dessus pourrait etre verte sur un module vide tout
    autant que sur un module honnete -- « une frontiere qui ne mord sur rien
    n'est pas une frontiere ».
    """
    temoin_chaine = (
        "def motif(page):\n"
        "    refusal_reason = page.page.refusal_reason\n"
        "    if refusal_reason.lower().startswith(\"qr illisible en zone\"):\n"
        "        return VERROU_INDETERMINE\n"
        "    return VERROU_TENU\n"
    )
    # L'ORDRE de decouverte de `ast.walk` n'est pas garanti stable entre
    # versions de Python -- on compare un ensemble, pas une liste.
    assert set(_decisions_sur_refusal_reason(temoin_chaine)) == {
        ".lower(...)", ".startswith(...)"}

    # Contre-epreuve : une comparaison litterale simple mord aussi.
    temoin_egalite = (
        "def motif(refusal_reason):\n"
        "    if refusal_reason == \"QR illisible en zone.\":\n"
        "        return VERROU_INDETERMINE\n"
    )
    assert _decisions_sur_refusal_reason(temoin_egalite) == ["comparaison litterale"]

    # Et la contre-epreuve symetrique : une lecture verbatim ne mord PAS --
    # sans cette moitie, la garde interdirait l'affichage lui-meme, ce que
    # l'AC exige au contraire.
    temoin_lecture = (
        "def bandeau(page):\n"
        "    phrase = page.page.refusal_reason\n"
        "    if phrase is not None:\n"
        "        self.label.setText(phrase)\n"
    )
    assert _decisions_sur_refusal_reason(temoin_lecture) == []
