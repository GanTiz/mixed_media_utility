# mmu-tui — l'interface en terminal de Mixed Media Utility

`mmu-tui` est **l'une des deux distributions** de Mixed Media Utility. Elle ne
porte que l'interface en terminal ; tout le reste — le coeur d'extraction, de
calibration et d'encodage, la ligne de commande `mmu`, la GUI optionnelle —
vit dans `mmu-cli`, dont elle depend.

```
pip install mmu-tui      # la TUI, et la CLI avec elle (mmu-cli est tiree)
pip install mmu-cli      # la CLI seule, sans les ~28 Mo de la TUI
```

Les deux paquets ne partagent **aucun fichier** : installer les deux dans un
meme environnement n'installe qu'un seul exemplaire du coeur.

Documentation, licence (GPL-3.0-or-later) et sources :
<https://github.com/GanTiz/mixed_media_utility>.
