# La ligne de commande

La TUI est le chemin nominal ; la ligne de commande est là pour ce que la TUI ne
fait pas : **scripter**, enchaîner, lancer sur une machine sans terminal
interactif, ou reprendre une étape isolée.

Les deux font exactement les mêmes traitements — la TUI appelle le même cœur.

---

## Comment invoquer la CLI

Il y a **deux formes**, et elles sont strictement équivalentes.

### La forme universelle

Elle marche partout où le paquet est installé, sans rien poser :

```bash
python -m mixed_media_utility.cli --help
```

### Le raccourci `mmu`

C'est le nom que l'outil emploie dans ses propres messages (« relancer avec…
`mmu project remove --lot <id>` »). Il vient du dépôt : `bin/mmu` sous Unix,
`bin\mmu.cmd` sous Windows. Pour l'avoir sur votre `PATH` :

#### Linux, macOS

```bash
bash scripts/install-mmu.sh
```

#### Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-mmu.ps1
```

Le script ajoute `bin/` au `PATH` de façon permanente et idempotente, puis vous
dit d'ouvrir un nouveau terminal. Ensuite :

```bash
mmu --help
```

!!! note "Le chemin le plus court : `pip install mmu-cli`"
    Le dépôt cloné n'est pas nécessaire pour avoir `mmu`. La commande est
    posée par le paquet **`mmu-cli`**, et `mmu-tui` s'appuie dessus — installer
    l'un ou l'autre suffit :

    | vous avez installé… | vous avez |
    |---|---|
    | `pipx install mmu-cli` | `mmu` |
    | `pipx install mmu-tui` | `mmu-tui`, et `mmu` après un `pipx inject --include-apps --force mmu-tui mmu-cli` |
    | `pip install mmu-cli` ou `mmu-tui` dans un venv | `mmu`, et le module importable |
    | le dépôt cloné | `mmu`, après `scripts/install-mmu.sh` — c'est **celui du dépôt** |

    La dernière ligne mérite une nuance : la commande du dépôt et celle du
    paquet peuvent coexister sur une même machine, et c'est alors l'ordre du
    `PATH` qui décide laquelle répond. Pour travailler sur le code, c'est ce
    qu'on veut ; pour utiliser l'outil, préférez le paquet.

---

## La forme des commandes

Une commande s'écrit `mmu`, puis **la sous-commande**, puis ses options.
`--project` désigne le dossier de projet et revient presque partout ; le
reste dépend de la sous-commande.

Onze sous-commandes, dont quatre portent elles-mêmes des sous-commandes. La
liste complète, avec toutes les options, est dans la
[référence des commandes](../reference/commandes.md).

| sous-commande | ce qu'elle fait |
|---|---|
| `previz` | lit un rush à des cadences réduites, sans rien écrire |
| `extract` | tire un lot de frames TIFF depuis un rush |
| `makepdf` | compose les planches imprimables d'un lot |
| `scan` | ingère des pages scannées et en récupère les frames |
| `scan-write` | écrit les frames depuis une détection déjà faite |
| `encode` | reconstruit un master depuis les frames scannées |
| `set-default-profile` | pose le profil de calibration par défaut du projet |
| `relink` | raccroche un rush dont le fichier a bougé |
| `project` | maintenance : `remove`, `add-rush` |
| `reconstruct-project` | reconstitue un projet depuis des QR décodés |
| `poc` | orchestration de bout en bout, pour la mise au point |

`--project` désigne le dossier de projet. Il est exigé partout sauf par
`previz`, qui ne touche à rien.

---

## Trois comportements qui surprennent au début

### 1. Deux commandes demandent votre consentement

`extract` et `encode` affichent un récapitulatif complet **avant** d'écrire, puis
attendent un accord. Dans un terminal interactif, vous répondez. Hors terminal —
script, tâche planifiée, session distante — il faut le donner d'avance :

```bash
mmu extract --project demo --video rush.mp4 --fps 12.5 --yes
```

Sans `--yes`, la commande ne fait rien et le dit :

> Confirmation non accordee: consentement absent en mode non interactif.

`--accept-unknown-color` est un consentement **supplémentaire**, réclamé quand la
colorimétrie de la source est absente ou incomplète. `--accept-incomplete-lot`
joue le même rôle pour `encode` sur un lot incomplet.

### 2. Rien n'est écrasé en silence, et rien n'est bloqué sèchement

Devant une sortie qui existe déjà, l'outil propose **au moins deux issues** :

* `--nouvelle-version` écrit une version voisine (`_v2`, `_v3`…) sans toucher à
  l'existante ;
* `--overwrite` réécrit en place, sciemment, après avertissement.

`makepdf` est le seul à verser le rang de lui-même : une planche n'est jamais
qu'un tirage de plus, donc relancer `makepdf` produit `_v2` sans rien demander.

Voir [le versionnage](workflow.md).

### 3. Rien n'est deviné

`--dpi` est obligatoire au scan. Aucun profil de calibration n'est choisi à
votre place. Le codec est vérifié dans votre `ffmpeg` avant d'écrire. Quand une
information manque, l'outil le déclare au manifeste plutôt que de la
reconstituer.

---

## Reprendre une étape isolée

### Juger la détection avant d'écrire un seul TIFF

`scan` fait tout d'un trait. Pour vous arrêter après la détection :

```bash
mmu scan --project demo --scan planches.pdf --dpi 600 detect
```

puis, quand le résultat vous convient, écrire les frames depuis le document
produit — sans relancer la détection :

```bash
mmu scan-write --project demo --detection scans/<slug>/<document>.json
```

C'est le geste qui évite de refaire vingt minutes de décodage pour changer une
option d'écriture.

### Régler la calibration une fois pour toutes

```bash
mmu makepdf --project demo calibration-page --chaine "mon scanner"
# imprimer, scanner, puis :
mmu scan --project demo --scan page-cal.pdf --dpi 600 calibrate --nom "mon scanner"
mmu set-default-profile --project demo --profil demo/versions/calibration/mon-scanner.json
```

### Raccrocher un rush déplacé

```bash
mmu relink --project demo --rush TEST_FILE --video /nouveau/chemin/TEST_FILE.mp4
mmu relink --project demo --rush TEST_FILE --chercher /un/dossier
```

### Supprimer

```bash
mmu project remove --project demo --lot TEST_FILE_12p5              # aperçu
mmu project remove --project demo --lot TEST_FILE_12p5 --confirmer  # exécution
```

---

## Les journaux

Chaque commande écrit son journal sous `logs/` du projet :
`extract.log`, `makepdf.log`, `scan.log`, `encode.log`,
`calibration-profile.log`. Ils gardent le détail que la sortie du terminal
résume — utile quand une planche sort de travers et que vous cherchez pourquoi.

---

## Un parcours en cinq lignes

```bash
mmu extract --project demo --video tests/TEST_FILE.mp4 --fps 12.5 --yes
mmu makepdf --project demo --lot TEST_FILE_12p5
# … imprimer, puis scanner à 600 dpi …
mmu scan    --project demo --scan mon-scan.pdf --dpi 600 --lot-slug essai_01
mmu encode  --project demo --lot TEST_FILE_12p5 --yes
```

Le détail de chaque étape, avec les sorties réelles, est dans
[Le parcours complet](workflow.md).
