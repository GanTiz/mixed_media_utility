# Déploiement & Packaging

Objectif : fournir un binaire facile à installer pour la cinéaste macOS.

Options proposées :

- PyInstaller → générer un exécutable macOS (.app ou DMG). Simple et offline.
- Tauri (si interface Web) → plus moderne mais nécessite toolchain Rust/JS.
- Homebrew tap (avancé) → distribuer via Homebrew.

Étapes pour PyInstaller (macOS) :

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pyinstaller --onefile -n mixed-media-util src/mixed_media_utility/cli.py
```

Générer un DMG : utiliser `create-dmg` ou `hdiutil` pour empaqueter l'app créée.

Dépendances externes requises :
- `ffmpeg` (installé système, recommandé via Homebrew on macOS)

Fichiers à commiter :
- `requirements.txt` (ou `pyproject.toml` si vous utilisez Poetry)
- `README.md`, `docs/` et exemples

