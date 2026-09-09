# -*- coding: utf-8 -*-
"""Frontieres negatives de l'ecran de gestion de projet (story 7.1).

Trois AC portent une frontiere qui ne se mesure pas par un scenario mais
par un grep, parce que ce qu'elles interdisent est une *tentation* et non
un chemin d'execution :

* **AC 2** -- le modele de la liste ne connait rien du contenu d'un projet :
  zero occurrence de ``rush``, ``lot``, ``absent`` dans son module
  (`EPIC7-ARB-27`, `EPIC7-ARB-14`). Le corollaire, c'est que les motifs
  d'erreur de l'AC 4 sont **lus** des exceptions du coeur : un seul message
  recopie en litteral y ferait entrer le vocabulaire du contenu ;
* **AC 5** -- l'import ne fusionne jamais deux projets : aucune fonction de
  fusion de manifeste du coeur n'est importee ni appelee depuis ``gui/`` ;
* **AC 4** -- la GUI n'introduit aucun code d'erreur nouveau : elle affiche
  ceux du coeur.

**Chaque grep porte son volet symetrique** : un test qui ne verifie que
« zero occurrence » peut etre vert parce qu'il ne mesure rien (mauvais
chemin, mauvaise casse, motif qui ne compile pas). Le second volet prouve
que la comparaison MORD sur une entree fautive fabriquee pour l'occasion --
c'est le motif « un test peut etre vert et vide » que ce depot a deja paye.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import mixed_media_utility

_PAQUET_GUI = Path(mixed_media_utility.__file__).resolve().parent / "gui"
_MODULE_DU_MODELE = _PAQUET_GUI / "modele_projets.py"


# ---------------------------------------------------------------------------
# AC 2 -- le modele de la liste ignore le vocabulaire du contenu
# ---------------------------------------------------------------------------

#: Les trois mots nommes par l'AC. Recherches sans egard a la casse, et sur
#: le fichier ENTIER (commentaires et docstrings compris) : une note de
#: developpement qui parlerait deja de contenu est le premier pas vers un
#: champ qui le porte.
_MOTS_DU_CONTENU = ("rush", "lot", "absent")


def _occurrences_du_contenu(texte):
    """Les mots du contenu presents dans ``texte``, sans egard a la casse."""
    minuscule = texte.lower()
    return sorted(mot for mot in _MOTS_DU_CONTENU if mot in minuscule)


def test_le_module_du_modele_de_liste_existe_bien_la_ou_le_grep_le_cherche():
    """Sans ce garde-fou, un renommage rendrait les deux tests suivants
    verts en ne lisant plus rien du tout."""
    assert _MODULE_DU_MODELE.is_file(), _MODULE_DU_MODELE


def test_zero_vocabulaire_de_contenu_dans_le_modele_de_la_liste():
    texte = _MODULE_DU_MODELE.read_text(encoding="utf-8")

    assert _occurrences_du_contenu(texte) == [], (
        "le modele de la liste parle du CONTENU d'un projet : "
        f"{_occurrences_du_contenu(texte)}"
    )


def test_le_grep_de_contenu_mord_sur_un_texte_fautif():
    """Volet symetrique : la comparaison echoue vraiment sur une entree
    fautive, pas seulement sur une entree conforme."""
    assert _occurrences_du_contenu("nombre de LOTS du projet") == ["lot"]
    assert _occurrences_du_contenu("rushes absents") == ["absent", "rush"]
    assert _occurrences_du_contenu("nom, chemin, dates") == []


def test_le_modele_de_la_liste_n_importe_aucun_toolkit_graphique():
    """Contrat enonce par le module lui-meme : Python pur, donc mesurable
    sans banc graphique. Un import de Qt le rendrait dependant d'une
    ``QApplication`` et ferait glisser la logique dans les widgets."""
    arbre = ast.parse(_MODULE_DU_MODELE.read_text(encoding="utf-8"))
    racines = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            racines.update(alias.name.split(".")[0] for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and not noeud.level:
            racines.add((noeud.module or "").split(".")[0])

    assert "PySide6" not in racines
    assert racines <= {"__future__", "dataclasses", "pathlib"}, racines


# ---------------------------------------------------------------------------
# AC 5 -- aucune fusion de manifeste : ni import, ni appel
# ---------------------------------------------------------------------------

#: Les gardes de conflit du coeur. Elles restent le porte-etendard exclusif
#: du chemin Scan (story 7.3) : l'import de l'ecran de projet OUVRE, il ne
#: fusionne pas -- le conflit du finding E24 ne se pose donc pas ici.
_FONCTIONS_DE_FUSION = (
    "_check_manifest_conflicts",
    "check_scan_conflicts",
    "_merge_entries",
)


def _modules_gui():
    modules = sorted(_PAQUET_GUI.rglob("*.py"))
    assert len(modules) >= 6, "le balayage doit couvrir tout le paquet GUI"
    return modules


def _appels_de_fusion(texte):
    return sorted(nom for nom in _FONCTIONS_DE_FUSION if nom in texte)


def test_aucun_module_gui_ne_touche_a_une_fonction_de_fusion_de_manifeste():
    fautifs = {}
    for module in _modules_gui():
        # Ce fichier de test n'est pas dans gui/ ; aucun module de
        # production n'a de raison de nommer ces fonctions.
        trouves = _appels_de_fusion(module.read_text(encoding="utf-8"))
        if trouves:
            fautifs[module.name] = trouves
    assert fautifs == {}, f"fonction de fusion de manifeste dans gui/ : {fautifs}"


def test_le_grep_de_fusion_mord_sur_un_texte_fautif():
    assert _appels_de_fusion("from ..io.reconstruction import _check_manifest_conflicts") == [
        "_check_manifest_conflicts"
    ]
    assert _appels_de_fusion("check_scan_conflicts(existant, decode)") == [
        "check_scan_conflicts"
    ]
    assert _appels_de_fusion("depot_projets.lire_projet(dossier)") == []


def test_le_depot_de_projets_n_importe_que_ce_qu_il_lui_faut_du_coeur():
    """L'inventaire EXPLICITE de la couture avec le coeur.

    Un import supplementaire n'est pas interdit en soi -- il est interdit
    d'en ajouter un sans que ce test le dise, parce que c'est par la qu'une
    surface de gestion se mettrait a fusionner, migrer ou reecrire.
    """
    module = _PAQUET_GUI / "depot_projets.py"
    arbre = ast.parse(module.read_text(encoding="utf-8"))
    importes = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            for alias in noeud.names:
                importes.add(alias.name)

    assert importes == {
        "MANIFEST_FILENAME",
        "MANIFEST_SCHEMA_VERSION",
        "_atomic_write",
        "validate_manifest",
        "NamingError",
        "normalize_identifier",
        # Ajout DELIBERE du 2026-08-27 (`EPIC7-ARB-82`) : la creation « peuple
        # le dossier avec l'arborescence », et cette arborescence est une
        # regle du COEUR. L'alternative -- une liste de dossiers ecrite dans
        # `gui/` -- serait precisement la divergence que ce fichier de
        # frontieres existe pour empecher. L'import est donc le bon geste, et
        # c'est son absence d'inventaire qui aurait ete la faute.
        "ensure_project_layout",
        "LigneProjet",
        "ValidationError",
        "datetime",
        "timezone",
        "Path",
        "annotations",
    }, sorted(importes)


# ---------------------------------------------------------------------------
# AC 4 -- la GUI n'introduit aucun code d'erreur nouveau
# ---------------------------------------------------------------------------

#: Forme d'un code d'erreur du coeur : capitales et souligne
#: (``LOT_INCOMPLETE``, ``VERIFY_MISSING_FRAMES``...). La GUI ne doit en
#: ecrire aucun -- elle affiche ceux qu'elle lit.
_MOTIF_CODE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")


def _noms_exportes(arbre):
    """Les chaines d'un ``__all__`` : des NOMS de symboles, pas des codes.

    Sans cette exemption, tout module qui declare son interface publique
    serait signale -- et l'exemption est sure parce qu'un ``__all__`` ne
    contient que des noms deja definis dans le module.
    """
    exportes = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Assign):
            continue
        vise = any(
            isinstance(cible, ast.Name) and cible.id == "__all__"
            for cible in noeud.targets
        )
        if vise and isinstance(noeud.value, (ast.List, ast.Tuple)):
            exportes.update(
                element.value
                for element in noeud.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            )
    return exportes


def _codes_litteraux(source):
    """Les chaines litterales en forme de code d'erreur dans un module."""
    arbre = ast.parse(source)
    exportes = _noms_exportes(arbre)
    return sorted(
        {
            noeud.value
            for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Constant)
            and isinstance(noeud.value, str)
            and _MOTIF_CODE.match(noeud.value)
            and noeud.value not in exportes
        }
    )


def test_aucun_code_d_erreur_litteral_dans_le_paquet_gui():
    fautifs = {}
    for module in _modules_gui():
        codes = _codes_litteraux(module.read_text(encoding="utf-8"))
        if codes:
            fautifs[module.name] = codes
    assert fautifs == {}, f"code d'erreur ecrit en dur dans gui/ : {fautifs}"


def test_le_grep_de_code_d_erreur_mord_sur_un_texte_fautif():
    """La divergence est deja arrivee dans ce depot : une maquette ecrivait
    ``LOT_INCOMPLET`` la ou le coeur ecrit ``LOT_INCOMPLETE``. C'est
    exactement ce que ce grep interdit d'ecrire a nouveau."""
    assert _codes_litteraux('motif = "LOT_INCOMPLET"') == ["LOT_INCOMPLET"]
    assert _codes_litteraux('cle = "ecran-projet-illisible"') == []
