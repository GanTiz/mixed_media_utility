# Story 7.0, AC 7 -- frontieres dures : PySide6 ne s'importe que sous
# gui/, les pages d'atelier sont vides de widgets metier, la GUI ne lit
# jamais la sortie du coeur (AC 5), le coeur n'importe jamais la GUI.

import ast
import subprocess
from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel, QWidget

import mixed_media_utility
from mixed_media_utility.gui import coquille as coquille_module
from mixed_media_utility.gui.coquille import Coquille

_RACINE_PAQUET = Path(mixed_media_utility.__file__).resolve().parent
_PAQUET_GUI = _RACINE_PAQUET / "gui"
_RACINE_DEPOT = _RACINE_PAQUET.parents[1]  # .../src/mixed_media_utility -> racine du depot

# La regle de regime -- « une reference de perimetre inatteignable est-elle un
# historique tronque, ou un AUTRE depot ? » -- vit dans `tests/_regime_du_depot.py`,
# ecrite une fois pour ses sept appelants.
import sys as _sys
_sys.path.insert(0, str(_RACINE_DEPOT / "tests"))
from _regime_du_depot import echoue_ou_saute  # noqa: E402

# Le motif AST des quatre tests previz existants
# (test_extraction_previz.py:1132), etendu au depot entier hors gui/.
_TOOLKITS_INTERDITS = {"PySide6", "PyQt5", "PyQt6", "shiboken6"}


def _modules_du_coeur():
    """Tous les modules de src/mixed_media_utility HORS gui/."""
    modules = [
        chemin
        for chemin in _RACINE_PAQUET.rglob("*.py")
        if _PAQUET_GUI not in chemin.parents
    ]
    assert len(modules) > 30, "le balayage doit couvrir le coeur entier"
    return modules


def _imports_du_module(chemin):
    """Les racines de modules importes par un fichier (balayage AST)."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    racines = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            racines.update(alias.name.split(".")[0] for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and not noeud.level:
            racines.add((noeud.module or "").split(".")[0])
    return racines


def test_aucun_module_du_coeur_n_importe_un_toolkit_qt():
    fautifs = {}
    for module in _modules_du_coeur():
        importes = _imports_du_module(module) & _TOOLKITS_INTERDITS
        if importes:
            fautifs[str(module.relative_to(_RACINE_PAQUET))] = sorted(importes)
    assert fautifs == {}, f"import Qt hors gui/ : {fautifs}"


#: Le paquet TUI (Epic 11) est un **second client** du coeur, pas le coeur.
#: Il importe `gui.jetons` -- et il le doit : l'AC 2 de la story 11.0 et
#: `DESIGN.md` section 5 de la TUI exigent l'un comme l'autre que les jetons de
#: couleur soient IMPORTES plutot que recopies, « sans quoi les deux surfaces
#: divergeront au premier ajustement de contraste ».
#:
#: L'intention de la frontiere ci-dessous -- « la GUI est un client du coeur,
#: elle n'est jamais importee PAR LUI » -- n'est donc pas violee : elle ne vise
#: pas un autre client. Ce que la frontiere protegeait vraiment, c'est que Qt
#: n'entre pas dans un graphe d'import qui n'en veut pas ; deux tests le
#: mesurent desormais explicitement, ci-dessous et dans
#: `tests/unit/tui/test_frontiere_gui_tui.py`.
_PAQUET_TUI = _RACINE_PAQUET / "tui"


def _modules_du_coeur_hors_tui():
    return [chemin for chemin in _modules_du_coeur()
            if _PAQUET_TUI not in chemin.parents]


def test_le_coeur_n_importe_jamais_le_paquet_gui():
    # gui/ est un CLIENT du coeur, au meme titre que cli.py et que tui/ : il
    # importe, il n'est jamais importe PAR LE COEUR (relatif ou absolu).
    fautifs = []
    for module in _modules_du_coeur_hors_tui():
        arbre = ast.parse(module.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom):
                cible = noeud.module or ""
                if cible == "gui" or cible.startswith("gui.") or ".gui" in cible:
                    fautifs.append(str(module.relative_to(_RACINE_PAQUET)))
            elif isinstance(noeud, ast.Import):
                if any(".gui" in alias.name for alias in noeud.names):
                    fautifs.append(str(module.relative_to(_RACINE_PAQUET)))
    assert fautifs == []


def test_la_gui_n_importe_pas_subprocess_et_ne_lit_aucun_flux_du_coeur():
    # AC 5, frontiere negative : zero parsing de sortie. Aucun module de
    # gui/ n'importe subprocess, ne lit stdout/stderr, ne redirige un flux.
    fautifs = {}
    for module in sorted(_PAQUET_GUI.rglob("*.py")):
        texte = module.read_text(encoding="utf-8")
        importes = _imports_du_module(module)
        motifs = []
        if "subprocess" in importes:
            motifs.append("import subprocess")
        for motif in ("stdout", "stderr", "capsys"):
            if motif in texte:
                motifs.append(motif)
        if motifs:
            fautifs[module.name] = motifs
    assert fautifs == {}, f"lecture ou redirection de flux dans gui/ : {fautifs}"


def test_les_pages_d_atelier_sont_vides_de_widgets_metier(qtbot):
    # Inventaire des enfants des pages ENCORE reservees : des libelles de
    # catalogue et rien d'autre -- pas d'ecran projet (7.1), pas de contenu
    # de chutier (7.2).
    #
    # **Reconciliation de la story 7.3.** La page `atelier-scan` cesse d'etre
    # reservee : la vague 3 la remplit (7.3, premier temps -- detecter et
    # annoncer ; 7.4, second temps -- juger). Le contrat de 7.0 n'est pas
    # affaibli, il est **date** : une page reste vide **jusqu'a la story qui
    # la remplit**, et l'exception est nommee ici plutot que le balayage
    # supprime. Les trois autres pages restent mesurees, et la garde ci-dessous
    # verifie qu'il en reste bien trois -- sans elle, exclure la quatrieme
    # aurait pu vider le balayage entier sans que rien ne le dise.
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    pile = fenetre.pile_ateliers
    assert pile.count() == 4
    indice_du_scan = coquille_module.ORDRE_ATELIERS.index(
        coquille_module.CLE_ATELIER_SCAN)
    reservees = [i for i in range(pile.count()) if i != indice_du_scan]
    assert len(reservees) == 3, reservees
    for indice in reservees:
        page = pile.widget(indice)
        enfants = [
            enfant for enfant in page.findChildren(QWidget)
            if enfant.parent() is not None
        ]
        etrangers = [
            type(enfant).__name__
            for enfant in enfants
            if not isinstance(enfant, QLabel)
        ]
        assert etrangers == [], (
            f"widgets metier dans la page {indice} : {etrangers}"
        )
        assert enfants, "une page reservee porte au moins son libelle"


# ---------------------------------------------------------------------------
# AC 7 -- « Zero hunk dans les modules existants du coeur. » Test de
# frontiere (grep sur le diff) manquant, trouve par la revue de vague 1.
#
# **Piege mesure et evite** : un `git diff <baseline> -- src/mixed_media_utility`
# BRUT contre HEAD n'est PAS robuste ici, pour deux raisons distinctes :
#
# 1. commits de reference ANCIENS (stories 5.19/5.22/5.23) inatteignables
#    dans un clone superficiel -- six tests preexistants du depot en
#    faux rouge permanent pour cette cause (`deferred-work.md`,
#    "clone superficiel") ;
# 2. plus specifique a CETTE story : un autre agent developpe 5.26 EN
#    PARALLELE sur la MEME branche, avec la MEME baseline -- ses commits
#    touchent legitimement `src/mixed_media_utility/cli.py` et
#    `scan_previz.py` (mesure : `6873b3f`, `da630af`, `3250441` sur ce
#    depot). Un diff brut `baseline..HEAD` y verrait donc a tort des hunks
#    hors gui/ qui n'appartiennent pas a 7.0.
#
# Le `baseline_commit` de la fiche (Change Log, 2026-08-24) est RECENT --
# il echappe au risque 1. Le risque 2 est evite en isolant les commits DE
# CETTE STORY par le prefixe conventionnel de leur message ("story 7.0"),
# verifie ci-dessous contre l'historique reel avant d'etre fige ici.
# ---------------------------------------------------------------------------

#: Change Log de la fiche 7.0 (2026-08-24) : « baseline_commit ca8140f ».
#: Un commit RECENT de la branche de travail, donc atteignable dans un
#: clone superficiel -- contrairement aux commits de reference plus
#: anciens (5.19/5.22/5.23) qui font echouer six tests preexistants
#: (deferred-work.md).
_BASELINE_7_0 = "ca8140f"

#: Prefixe conventionnel des messages de commit de cette story, verifie sur
#: l'historique reel de la branche avant d'etre fige ici (`git log
#: --oneline ca8140f..HEAD`) : tous les commits de production de 7.0
#: commencent par "story 7.0", tous ceux de 5.26 par "story 5.26" -- aucun
#: chevauchement mesure. Filtrer sur ce prefixe isole precisement les
#: commits DE CETTE STORY dans un historique partage avec un autre agent.
_PREFIXE_COMMITS_STORY = "story 7.0"


def _commits_de_la_story(baseline=_BASELINE_7_0, prefixe=_PREFIXE_COMMITS_STORY):
    """Hashes des commits de cette story entre `baseline` (exclu) et HEAD.

    L'echec est **dur** (jamais un `skip`) sur un baseline inatteignable :
    un `skip` se lirait comme un vert alors que la frontiere devrait
    s'evaluer et ne le fait pas (meme politique que
    `test_calibration_page_geometry.py::_diff_de_production`).
    """
    try:
        sortie = subprocess.run(
            ["git", "log", "--oneline", "--format=%H %s", f"{baseline}..HEAD"],
            cwd=_RACINE_DEPOT, capture_output=True, text=True, check=True, timeout=60,
        ).stdout
    except (subprocess.SubprocessError, OSError) as erreur:
        echoue_ou_saute(
            _RACINE_DEPOT, baseline,
            f"commit de reference {baseline} inatteignable ({erreur}) : la "
            "frontiere AC 7 ne s'evalue pas, et un skip se lirait comme un "
            "vert -- clone superficiel ou historique tronque"
        )
    hashes = []
    for ligne in sortie.splitlines():
        hash_commit, _, message = ligne.partition(" ")
        if message.startswith(prefixe):
            hashes.append(hash_commit)
    return hashes


def _fichiers_du_coeur_touches_par(hashes):
    """Union des fichiers de `src/mixed_media_utility` touches par `hashes`."""
    fichiers = set()
    for hash_commit in hashes:
        try:
            sortie = subprocess.run(
                ["git", "show", "--name-only", "--format=", hash_commit,
                 "--", "src/mixed_media_utility"],
                cwd=_RACINE_DEPOT, capture_output=True, text=True, check=True,
                timeout=60,
            ).stdout
        except (subprocess.SubprocessError, OSError) as erreur:
            pytest.fail(f"commit {hash_commit} illisible ({erreur})")
        fichiers.update(ligne for ligne in sortie.splitlines() if ligne)
    return fichiers


def test_zero_hunk_hors_de_gui_dans_les_modules_du_coeur():
    """AC 7 : aucun hunk de cette story hors de `src/mixed_media_utility/gui/`.

    Litteralement l'AC : « `git diff <baseline> -- src/mixed_media_utility`
    ne porte AUCUN hunk hors de `src/mixed_media_utility/gui/` -- pas meme
    `__init__.py` ni `cli.py` ». Applique aux commits DE CETTE STORY
    seulement (voir le commentaire de section ci-dessus pour le motif).
    """
    hashes = _commits_de_la_story()
    assert hashes, (
        "aucun commit 'story 7.0' trouve depuis le baseline : la frontiere "
        "ne mesurerait rien"
    )
    touches = _fichiers_du_coeur_touches_par(hashes)
    assert touches, "aucun fichier du coeur touche : la frontiere ne mesurerait rien"
    hors_gui = sorted(
        chemin for chemin in touches
        if not chemin.startswith("src/mixed_media_utility/gui/")
    )
    assert hors_gui == [], f"hunk hors de gui/ dans un module du coeur : {hors_gui}"


def test_la_frontiere_mord_sur_un_fichier_hors_gui():
    # Le second volet, symetrique (le motif « un test peut etre vert et
    # vide » que ce depot a deja paye) : la comparaison echoue vraiment
    # quand un fichier hors gui/ est touche, pas seulement quand rien ne
    # l'est. Meme logique que le test precedent, exercee sans toucher au
    # vrai depot git.
    def _hors_gui(touches):
        return sorted(
            chemin for chemin in touches
            if not chemin.startswith("src/mixed_media_utility/gui/")
        )

    conforme = {"src/mixed_media_utility/gui/coquille.py",
                "src/mixed_media_utility/gui/executeur.py"}
    assert _hors_gui(conforme) == []

    intrus = conforme | {"src/mixed_media_utility/cli.py"}
    assert _hors_gui(intrus) == ["src/mixed_media_utility/cli.py"]
