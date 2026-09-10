# Historique des versions

## 0.1.1 (2026-09-09)

Correctifs de **terrain** : la première monteuse a installé la v0.1.0 et scanné
en TIFF sur macOS avec l'utilitaire système natif. Trois points remontés, un
quatrième trouvé en les mesurant. Chacun a été rejoué de bout en bout sur les
fichiers réels avant et après correctif.

### Corrigé

- **Un scan avec canal alpha n'est plus refusé.** `Apple Image Capture` écrit
  quatre canaux là où le pilote d'imprimante en écrit trois ; l'outil rendait
  `page_not_three_channels` et refusait toute la calibration, alors que le QR
  et la géométrie ArUco se lisaient parfaitement. Le canal est retiré à la
  lecture, et le rapport d'ingestion continue de déclarer ce que le fichier
  portait. Un alpha qui porterait réellement de la transparence est retiré
  aussi, mais en le disant.
- **Un TIFF de plusieurs pages rend toutes ses pages.** Sur un fichier à deux
  pages, l'outil n'en ingérait qu'une, rendait `0`, et le lot était incomplet
  sans le moindre message. Les pages sont désormais lues une par une ; une
  vignette d'aperçu n'est pas comptée comme une page ; et quand le fichier
  porte plus de pages que le lecteur ne sait en rendre, les pages lisibles sont
  ingérées **et l'écart est annoncé**.
- **Le dpi déclaré d'un TIFF est enfin lu.** Il ne l'avait jamais été, sur
  aucun TIFF : la confrontation entre le dpi que vous annoncez et celui que le
  fichier déclare — la garde contre le scanner en *auto-fit* — ne jouait donc
  pas sur le format que l'outil recommande pour scanner. Les deux axes sont
  lus, et c'est le plus bas qui compte.
- **La barre d'adresse de l'explorateur accepte un chemin de fichier.** Coller
  le chemin d'un fichier vous amène désormais à son dossier, curseur posé
  dessus — au lieu d'annoncer « aucun dossier n'existe à cette adresse » d'un
  fichier qui existe. Quand la liste ne peut pas montrer ce fichier, elle dit
  pourquoi.

### Notes

- Un scan en niveaux de gris reste refusé à la calibration : retirer un canal
  alpha opaque ne perd aucune information, convertir du gris en couleur en
  fabriquerait.
- Sur un scanner en auto-fit, l'avertissement « le dpi déclaré diffère de celui
  du fichier » peut désormais apparaître là où il se taisait. C'est l'effet
  voulu.

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

### 0.1.0 → 0.1.1

Aucune action. Aucun format de fichier, aucun nom de commande, aucun manifeste
ne change. Les profils de calibration écrits en 0.1.0 restent valides :
l'identité de chaîne ne dépend ni du nombre de canaux ni du dpi mesuré.

### 0.1.0 → 0.2.0 (attendu)
- Ajout extra `[gui]` pour PySide6/OpenCV
- `mmu-gui` console script (si GUI installée)

### Avant 0.1.0 (dépôt privé)
- Lancement via `bin/mmu-tui` et `bin/mmu-tui.cmd` (PYTHONPATH + ESCDELAY)
- Aucun `pip install` — dépôt non packagé