# Historique des versions

## 0.1.0 (2026-08-28)

### Ajouté
- Packaging PEP 621 (`pyproject.toml` complet)
- Entry point `mmu-tui` (console_scripts)
- Dépendances séparées : `gui`, `dev`, `test`, `full`
- Documentation MkDocs Material (`docs/`, `mkdocs.yml`)
- Installation via `pip install mmu-tui`

### Fonctionnalités existantes (déjà dans le dépôt)
- TUI interactive (textual) : projets, rushs, lots, scan, calibration
- CLI : `makepdf`, `scan`, `extract`, `reconstruct`, `encode`
- Détection ArUco/QR, correction perspective
- Calibration couleur par chaîne de scan
- Extraction frames TIFF 16 bits
- Encodage mezzanine (ProRes/DNxHR/H.264/HEVC)

---

## Roadmap

| Version | Cible |
|---------|-------|
| 0.2.0 | GUI PySide6 packagée (`mmu[gui]`) |
| 0.3.0 | Trusted Publishing PyPI (tokenless) |
| 0.4.0 | Wheels multi-plateforme (macOS arm64, Linux manylinux) |
| 1.0.0 | Release stable, docs complètes |

---

## Notes de migration

### 0.1.0 → 0.2.0 (attendu)
- Ajout extra `[gui]` pour PySide6/OpenCV
- `mmu-gui` console script (si GUI installée)

### Avant 0.1.0 (dépôt privé)
- Lancement via `bin/mmu-tui` et `bin/mmu-tui.cmd` (PYTHONPATH + ESCDELAY)
- Aucun `pip install` — dépôt non packagé