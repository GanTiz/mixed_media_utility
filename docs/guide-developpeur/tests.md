# Tests et mutation testing

## Tests unitaires (pytest)

```bash
# Tous les tests hors GUI
pytest tests/unit --ignore=tests/unit/gui -x -q

# TUI uniquement
pytest tests/unit/tui -v

# Avec couverture
pytest tests/unit --cov=src/mixed_media_utility --cov-report=term-missing
```

### Fixtures

`tests/fixtures/` contient les rushes de synthèse et les données de test en git
ordinaire, **plus des médias lourds en Git LFS** : les PDF de scans réels, les
TIFF de terrain et le rush réel. Un clone en tire ~28 Mo ; deux arbres plus
lourds — `tests/fixtures/lots/` (178 Mo) et `tests/fixtures/rushes/reels/`
(64 Mo) — ne descendent **pas** par défaut.

Sans `git-lfs`, ces fichiers valent 133 octets et **ne lèvent aucune erreur** :
la panne apparaît beaucoup plus loin, sur un message de décodage
incompréhensible. Le geste complet — installation, sonde de pointeurs, et le
`--exclude=""` sans lequel rien ne descend — est décrit dans
[l'installation depuis les sources](../installation/from-source.md).

`tests/unit/fixtures_source_confirmation/` : fixtures dédiées à `source_confirmation.py`.

---

## Mutation testing (mutmut)

### Pourquoi
Les tests classiques vérifient le comportement ; la mutation vérifie que les tests **détectent** les bugs. Un mutant survivant = un test qui ne verrouille rien.

### Campagnes par story — **archivées depuis le 2026-09-10**

Jusqu'au 2026-08-12, chaque story avait sa campagne écrite à la main dans
`scripts/mutation/`. **mutmut les a remplacées**, et elles sont désormais
figées sous `scripts/archive/mutation/` :

```bash
python -B -u scripts/archive/mutation/campagne_5_16_geometrie.py A C E G
```

Chacune hardcode les mutants de **sa** story et son bac à sable : elle se
relit, elle ne se transpose pas. Pour une campagne **neuve**, on passe par
mutmut et le harnais courant (ci-dessous), jamais par la copie d'une campagne
archivée.

### Config mutmut (`pyproject.toml`)

```toml
[tool.mutmut]
source_paths = ["src/mixed_media_utility"]
pytest_add_cli_args_test_selection = ["tests/unit"]
```

> **RÈGLE** : cette section est édité **localement** pour chaque campagne et **jamais committée scopée**. Restaurer après usage : `git checkout -- pyproject.toml`.

### Exécution manuelle

```bash
# Campagne complète (long)
mutmut run --paths-to-mutate=src/mixed_media_utility --tests-dir=tests/unit

# Ciblée sur un fichier
mutmut run --paths-to-mutate=src/mixed_media_utility/color_calibration.py --tests-dir=tests/unit

# Voir survivants
mutmut results
mutmut html
```

### Interprétation

| Résultat | Signification |
|----------|--------------|
| **TUE** (killed) | un test échoue → le mutant est détecté |
| **SURVIVANT** | aucun test ne capture → correctif manquant ou test faible |
| **INVALIDE** | erreur d'exécution (config) |
| **MOTIF** | mutant équivalent (pas de bug réel) |

Zéro survivant exigé sur les chemins fragiles (voir politique de revue).

---

## CI (GitHub Actions)

Le workflow suit la politique du dépôt :
- Tests unitaires sur Python 3.11/3.12/3.13
- Mutation testing sur fichiers modifiés (campagne ciblée)
- Build wheel + vérification entry point

---

## Règle des fabriques (rappel)

Une fabrique de collection produit **≥ 2 éléments distinguables** :
- Valeurs différentes (pas uniforme)
- Au moins un test place la cible ailleurs qu'en position 1

*Trois occurrences de défauts M33/M25 trouvées par mutation, invisibles aux tests classiques.*

---

## Tests endormis (interdits)

Aucun test ne doit dormir silencieusement sous décorateur désactivant.
Voir `test_aucun_test_endormi.py` : collecteur pytest qui échoue si un test est désactivé sans motif nommé.

---

## Benchmarks de référence

| Module | Temps typique campagne |
|--------|----------------------|
| `color_calibration` | ~8 min (544 s) sur arbre propre |
| `pdf_composition` | ~12 min |
| `scan_detect` | ~6 min |

> Utiliser `nohup` pour campagnes longues :
> ```bash
> nohup python -B -u scripts/archive/mutation/campagne_5_16_geometrie.py > run.txt 2>&1 &
> ```