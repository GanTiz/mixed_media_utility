# Conventions de code

## Langue

- **Commentaires et docstrings** : **français** pour tout nouveau code
- **Identifiants, code, fixtures** : ASCII (sans accents)
- **Stories** : fichiers en ASCII
- **Documents d'arbitrage** : accents autorisés (`.md` décisions)

Modules anglais existants (`patch_values.py`, `color_pipeline.py`, `pdf_render.py`, `detection/aruco.py`) **ne sont pas repris** à retroactivement — le dépôt reste transitoirement bilingue.

---

## Nommage

| Élément | Convention | Exemple |
|---------|------------|---------|
| Fonction | `snake_case` | `build_frame_selection_command` |
| Classe | `PascalCase` | `CoqueTui`, `ScanRecord` |
| Constante | `UPPER_SNAKE` | `MAX_PATCHES_PER_PAGE` |
| Variable privée | `_prefix` | `_build_rush_entry` |
| Test | `test_<sujet>_<cas>` | `test_the_poc_extraction_signature_is_untouched` |
| Fichier test | `test_<module>.py` | `test_color_calibration.py` |

---

## Structure des modules

- Une classe = un fichier si gros
- Fonctions pures pour logique testable
- Imports en tête, groupés : stdlib, third-party, local

---

## Docstrings

Requises sur fonctions publiques et classes. Format :
```python
def analyser(argv: list[str] | None = None) -> argparse.Namespace:
    """Lit la ligne de commande. Les valeurs par defaut lisent l'environnement."""
```

---

## Types

- Type hints partout (PEP 484)
- `from __future__ import annotations` en tête si Python < 3.14
- Éviter `Any` sans garde

---

## Tests

- Un test par comportement
- Fabriques de collection → ≥ 2 éléments distinguables (règle des fabriques)
- Pas de `TODO` dans le code livré
- Chaque correctif a un test qui échoue avant / passe après

---

## Constantes partagées

Source unique de vérité. Exemples à ne **pas** dupliquer :
- `OUTPUT_BIT_DEPTH` → `color_pipeline.MVP_OUTPUT_BIT_DEPTH`
- `ESCDELAY` → `25` (lanceurs)
- `CANONICAL_ID_MAX_LENGTH` → `64` (`scan_ingest`)

---

## argparse

- `allow_abbrev=False` (évite `--o` ambigu entre `--out`/`--overwrite`)
- Aide en français
- `--diagnostic-chemin` pour outils de diagnostic

---

## Gestion d'erreurs

- Exceptions typées (`PocInputError`, `ManifestIncoherent`, …)
- Pas de `except Exception` nu
- Messages d'erreur nomment la cause + l'issue disponible

---

## Logging

- `logger.handlers` fermés proprement (`handler.close()` avant `clear()`)
- Écritures/logger **dans** le bloc `try`
- Pas de fuite de `FileHandler` sous Windows

---

## Commits

- Impératif, français OK : `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- Jamais `git add -A` — chemins explicites
- `git commit -m "..." -- <chemins>`

---

## Linting

```bash
# Avant push
pytest tests/unit --ignore=tests/unit/gui -x -q
mypy src/mixed_media_utility  # si configuré
```

---

## Documentation

- Doc utilisateur : `docs/` (MkDocs Material)
- Référence commandes : `docs/reference/commandes.md`
- Architecture : `docs/guide-developpeur/architecture.md`

---

## Interdits

- ❌ `git add -A`
- ❌ `pyproject.toml [tool.mutmut]` committé scopé
- ❌ `deferred-work.md` entrée supprimée (barrer + annoter)
- ❌ `sprint-status.yaml` édité hors de sa ligne
- ❌ Tests endormis sans motif nommé
- ❌ Fabrique de collection à 1 élément seul