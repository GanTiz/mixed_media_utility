# Premiers pas

1. Créer un environnement Python :

```bash
python -m venv .venv
source .venv/bin/activate    # macOS / Linux
.\.venv\Scripts\Activate   # Windows
pip install -r requirements.txt
```

2. Vérifier que `ffmpeg` est installé et accessible (`ffmpeg -version`).

3. Lancer la commande d'aide :

```bash
python -m src.mixed_media_utility.cli -h
```

4. Exemples : voir `docs/USAGE.md`.
