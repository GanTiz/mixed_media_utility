# Rushes RÉELS — versionnés, mais PAS téléchargés par défaut

Sans le geste ci-dessous, les fichiers d'ici valent **133 octets** — ce sont des
pointeurs, et **aucune erreur ne le signale** :

```
git lfs pull --include="tests/fixtures/rushes/reels/**"
```

## Ce qu'il y a dedans

| fichier | |
|---|---|
| `rush_bitch-4_chendj-mat.mp4` | **64 Mo** — H.264, **3840×2160**, 25 im/s, 4,24 s |

C'est le **seul rush 4K réel** du dépôt. Il sert à reproduire des frames depuis
une vraie source de terrain, là où les quatre rushes du dossier parent sont des
fabriques de synthèse (~200 Ko pièce, 1080p et moins) qui, elles, descendent à
chaque clone.

## Pourquoi il ne descend pas tout seul

64 Mo par démarrage de conteneur, multipliés par les agents et les vérifications
automatiques, c'est ce qui a vidé le quota de bande passante le 2026-09-03. Le
fichier reste **dans le dépôt** — partageable, reproductible — mais il attend
qu'on le demande.

Même régime que `tests/fixtures/lots/`, et pour la même raison. Le détail est
dans `.lfsconfig`, et `tests/unit/test_politique_lfs.py` vérifie que ce dossier
est bien stocké en LFS **et** bien exclu du téléchargement automatique.
