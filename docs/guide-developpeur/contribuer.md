# Contribuer

## Prérequis

- Python ≥ 3.11
- Git
- ffmpeg dans le PATH
- (GUI) PySide6, opencv-contrib-python

---

## Mise en place

```bash
git clone https://github.com/GanTiz/mixed_media_utility.git
cd mixed_media_utility
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Git LFS — nécessaire pour jouer la suite, et pour elle seule

Les fixtures de terrain (scans réels, TIFF, rush réel) sont stockées en **Git
LFS**, ~28 Mo par clone. Sans `git-lfs` installé elles valent 133 octets et
**aucune erreur ne le dit** : la suite échoue bien plus loin, sur un message de
décodage incompréhensible.

```bash
git lfs install
git lfs pull
```

Le diagnostic, et les deux arbres lourds qui ne descendent pas par défaut :
[installation depuis les sources](../installation/from-source.md).

---

## Cycle de développement

Ce dépôt suit la méthode **BMad** (stories, epics, sprints). Chaque changement de code part d'une story :

1. **Rédiger** la story (`bmad-create-story` ou template manuel)
2. **Développer** (`bmad-dev-story`)
3. **Revoir** en 3 couches (blind hunter, edge case hunter, acceptance auditor)
4. **Mutation testing** (`mutmut run`)
5. **Commit** par chemin, jamais `git add -A`

---

## Règles de commit

### Jamais `git add -A`
Ajoutez explicitement vos chemins :
```bash
git add -N src/mixed_media_utility/mon_module.py tests/unit/test_mon_module.py
git commit -m "feat: ..." -- src/mixed_media_utility/mon_module.py tests/unit/test_mon_module.py
```

### Commit atomique
Un commit = une logique. Message explicite (impératif, français ok).

### Sauvegarde intermédiaire
À chaque rendu d'agent, commit + push sur la branche de travail.

---

## Règle des fabriques (CRITIQUE)

Toute fabrique de collection produit **≥ 2 éléments distinguables** :
- Valeurs différentes, pas un remplissage uniforme
- Au moins un test place la cible ailleurs qu'en première position

*Sinon un `find` fautif qui rend toujours le premier élément reste invisible.*

---

## Tests de mutation

Chaque correctif doit avoir un test qui **échoue avant** le correctif et **passe après** (jamais un grep du code source).

```bash
mutmut run --paths-to-mutate=src/mixed_media_utility/mon_module.py --tests-dir=tests/unit
mutmut results
```

Zéro survivant exigé sur les chemins fragiles (liste dans la politique de revue).

---

## Linting / typage

```bash
# Tests
pytest tests/unit --ignore=tests/unit/gui -x -q

# Type hints (si mypy configuré)
mypy src/mixed_media_utility
```

---

## Code review (3 couches)

1. **Blind Hunter** : relit le diff sans la story, cherche bugs
2. **Edge Case Hunter** : parcourt toutes les frontières (sans lire la story)
3. **Acceptance Auditor** : confronte AC par AC (seul lit la story)

Trois agents, jamais plus de trois en parallèle.

---

## Conventions de code

- **Commentaires en français** pour le nouveau code (modules anglais existants non repris)
- **Stories en ASCII** (identifiants, fixtures)
- **Docstrings** requises sur fonctions publiques
- **Pas de `TODO`** dans le code livré (voir `cli.py:215,218` corrigés)

Voir [Conventions de code](conventions.md) pour le détail.

---

## Documentation

- Doc utilisateur : `docs/` (MkDocs Material)
- Doc développeur : `docs/guide-developpeur/`
- Manuels : voir [Installation](../installation/windows.md)

Pour builder la doc localement :
```bash
pip install mkdocs mkdocs-material mkdocs-git-revision-date-localized-plugin
mkdocs serve
```

---

## Pull Request

1. Branche depuis `main` ou `oc/epic-11-TUI`
2. PR vers `main`
3. Titre : `[epic-X] <courte desc>` ou `fix: ...` / `feat: ...` / `docs: ...`
4. Description : lien vers la story, résumé des changements, preuve tests/mutation

---

## Points de contention (à éviter)

| Fichier | Règle |
|---------|-------|
| `sprint-status.yaml` | éditer **sa** ligne, après `pull --rebase` |
| `pyproject.toml` `[tool.mutmut]` | jamais scopé en commit |
| `deferred-work.md` | barrer + annoter, jamais supprimer |
| `CLAUDE.md` | lire avant tout commit sur branche partagée |