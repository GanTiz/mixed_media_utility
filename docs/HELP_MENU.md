# Menu d'aide — Texte à intégrer dans l'application

Aide > À propos
- Nom du logiciel : Mixed Media Utility
- Version : voir `--version`
- Licence : GPL-3.0-or-later — logiciel libre, sans garantie. Texte intégral dans `LICENSE`, composants tiers dans `THIRD-PARTY-NOTICES.md`.

Aide > Guide rapide
- Importer un rush : `File > Import` ou `mixed-media-util extract-frames`
- Générer gabarit imprimable : `File > Générer gabarit` ou `mixed-media-util gen-gabarit`
- Scanner le gabarit et corriger : `File > Import scan` puis `Process > Apply calibration`
- Exporter : `File > Export` (séquence d'images ou encodage vidéo)

Aide > Workflow POC cible story 1.1
- Construire la planche : `mixed-media-util poc build-sheet --project <dir> --video <video> --fps 2 --dpi 300`
- Imprimer puis scanner la planche
- Traiter le scan : `mixed-media-util poc process-scan --project <dir> --scan <scan> --dpi 300`

Aide > Dépannage
- Si la détection des repères échoue, essayer un scan en meilleure résolution et utiliser l'outil manuel pour placer des repères.
- Pour l'encodage, assurez-vous que `ffmpeg` est installé et accessible via le PATH.

Aide > Documentation complète
- Voir le dossier `docs/` dans le dépôt pour les guides d'utilisation et de déploiement.

Contact & retours
- Créez une issue sur GitHub avec l'étiquette `bug` ou `feature`.
