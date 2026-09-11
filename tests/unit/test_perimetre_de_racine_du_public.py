"""Frontieres du perimetre de RACINE du depot public.

**Le defaut que ce banc ferme, et il etait de FORME, pas d'execution.** Jusqu'au
2026-09-10, `scripts/depot_public.py` triait par liste NOIRE : huit prefixes
nommes, et **tout ce qui n'y figurait pas partait par defaut**. Mesure du
2026-09-09 sur l'arbre publie : `temp/`, `.serena/`, `gui-prototype/`,
`.github/agents/`, `scripts/mutation/` (52 campagnes de mutation),
`scripts/research/` (29 scripts) et une capture d'ecran de 3,6 Mo referencee
NULLE PART y etaient. **Rien n'avait fui** -- la simulation du script contre
l'arbre publie rendait UNE ligne d'ecart sur 1 094 fichiers. Le script n'avait
simplement jamais eu de question a poser a ces dossiers.

**La bonne forme existait deja dans ce depot** : la section sdist de
`pyproject.toml` est une liste blanche de six motifs ancres, et c'est pourquoi
les distributions PyPI sont propres -- 149 fichiers, zero interne.

**Pourquoi des frontieres NEGATIVES.** Aucun test positif ne verrait revenir une
liste noire : un script qui trie par liste noire trie, donc il « marche ». Ce
qui se mesure est la FORME, et le fait qu'aucune famille interne connue ne
puisse y rentrer.

Ce banc est le pendant de `test_perimetre_public`, qui garde `_bmad-output/`
sur l'AST. Celui-ci garde la RACINE.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_SCRIPT = _RACINE / "scripts" / "depot_public.py"


def _module():
    if not _SCRIPT.is_file():
        pytest.skip("`scripts/depot_public.py` absent de ce clone.")
    spec = importlib.util.spec_from_file_location("_dp", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: Les familles dont la mesure du 2026-09-09 a etabli qu'elles n'ont rien a
#: faire au public. Chacune y ETAIT publiee avant la bascule.
_INTERNES = (
    "_bmad/", "_bmad-output/", ".agents/", ".claude/", "projects/",
    "temp/", ".serena/", "gui-prototype/",
    "scripts/mutation/", "scripts/research/", "scripts/bac-a-sable/",
    "scripts/planification/", ".github/agents/",
)


def test_FRONTIERE_NEGATIVE_le_script_ne_trie_plus_par_liste_NOIRE():
    """`HORS_DE_L_ORPHELIN` etait la forme fautive : elle publiait par defaut."""
    module = _module()
    assert not hasattr(module, "HORS_DE_L_ORPHELIN"), (
        "`HORS_DE_L_ORPHELIN` est de retour. Une liste noire oubliee PUBLIE "
        "en silence ; une liste blanche oubliee fait manquer un fichier, et "
        "la CI publique rougit. C'est le bon sens de l'erreur."
    )
    texte = _SCRIPT.read_text(encoding="utf-8")
    code = "\n".join(l for l in texte.splitlines()
                     if not l.lstrip().startswith("#"))
    assert "HORS_DE_L_ORPHELIN" not in code


def test_les_trois_listes_blanches_existent_et_ne_sont_pas_vides():
    module = _module()
    for nom in ("PORTES_A_LA_RACINE", "FICHIERS_DE_RACINE", "SCRIPTS_PORTES"):
        valeur = getattr(module, nom, None)
        assert valeur, f"`{nom}` doit exister et nommer au moins un chemin."


@pytest.mark.parametrize("interne", _INTERNES)
def test_FRONTIERE_NEGATIVE_aucune_famille_interne_n_est_portee(interne):
    """Chacune de ces familles ETAIT publiee avant le 2026-09-10."""
    module = _module()
    declares = (tuple(module.PORTES_A_LA_RACINE)
                + tuple(module.FICHIERS_DE_RACINE)
                + tuple(module.SCRIPTS_PORTES))
    fautifs = [d for d in declares
               if d.startswith(interne) or interne.startswith(d)]
    assert not fautifs, (
        f"`{interne}` repasserait au public par {fautifs}."
    )


def test_CLAUDE_md_n_est_pas_publie():
    """Egan, 2026-09-10 : « On ne le publie pas. »

    79 Ko de conduite de travail interne. Les DEUX bancs qui le lisent et qui
    mesurent de l'outillage non publie sont ecartes par `BANCS_NON_PUBLIES` ;
    le troisieme mesure la documentation utilisateur et reste publie.
    """
    module = _module()
    assert "CLAUDE.md" not in module.FICHIERS_DE_RACINE
    for banc in ("tests/unit/test_politiques_du_depot.py",
                 "tests/unit/test_outillage_de_mesure.py"):
        assert banc in module.BANCS_NON_PUBLIES, (
            f"{banc} lit `CLAUDE.md`, qui n'est plus publie : il rougirait "
            "sur la CI publique faute de son sujet."
        )


def test_tout_dossier_de_tete_est_TRANCHE_porte_ou_non():
    """L'invariant qui attrape un dossier NEUF.

    Un dossier de tete qui apparaitrait demain n'est ni porte ni exclu : il
    doit etre TRANCHE explicitement, dans un sens ou dans l'autre. Ce test est
    ce qui force la question au lieu de la laisser se resoudre par defaut.
    """
    module = _module()
    import subprocess
    suivis = subprocess.run(
        ["git", "ls-files"], cwd=_RACINE, capture_output=True, text=True,
        check=True).stdout.split("\n")
    tetes = {c.split("/")[0] + "/" for c in suivis if "/" in c}
    portes = tuple(module.PORTES_A_LA_RACINE)
    connus = set(_INTERNES)
    inconnus = sorted(
        t for t in tetes
        if not any(p.startswith(t) or t.startswith(p) for p in portes)
        and not any(t.startswith(i) or i.startswith(t) for i in connus)
    )
    assert not inconnus, (
        f"dossiers de tete non tranches : {inconnus}. Chacun doit rejoindre "
        "`PORTES_A_LA_RACINE` (il part au public) ou la liste des familles "
        "internes de ce banc (il reste prive). Le silence n'est pas une reponse."
    )


def test_l_arbre_CONSTRUIT_ne_porte_que_ce_qui_est_declare(tmp_path):
    """La mesure de bout en bout : on construit, et on verifie chaque fichier.

    Les deux listes peuvent etre justes et la SELECTION fausse. Seule la
    construction reelle mesure les deux ensemble.
    """
    module = _module()
    dest = module.construit(tmp_path / "orphelin")
    portes = tuple(module.PORTES_A_LA_RACINE)
    racine = tuple(module.FICHIERS_DE_RACINE) + tuple(module.SCRIPTS_PORTES)
    methode = f"{module.DOSSIER_DE_METHODE}/"

    intrus = []
    for chemin in dest.rglob("*"):
        if not chemin.is_file():
            continue
        rel = str(chemin.relative_to(dest))
        if rel.startswith(".git/"):
            continue
        if (any(rel.startswith(p) for p in portes) or rel in racine
                or rel.startswith(methode)):
            continue
        intrus.append(rel)
    assert not intrus, f"l'orphelin porte des chemins non declares : {intrus}"
