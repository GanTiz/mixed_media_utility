# Installation depuis les sources

C'est le chemin qui fonctionne aujourd'hui, sur les trois plateformes. Il
convient aussi bien pour se servir de l'outil que pour le modifier.

Les prérequis de votre plateforme — Python, ffmpeg, git — sont sur sa page :
[Windows](windows.md), [macOS](macos.md), [Linux](linux.md).

---

## 1. Cloner

```bash
git clone https://github.com/GanTiz/mixed_media_utility.git
cd mixed_media_utility
```

---

## 2. Un environnement virtuel

Recommandé, et pas seulement par principe : l'installation pèse quelques
centaines de mégaoctets de bibliothèques natives (OpenCV, NumPy) qu'on aime
pouvoir jeter d'un `rm -rf`.

### Linux, macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

---

## 3. Installer

```bash
pip install .
```

ou, si vous comptez modifier le code — le paquet pointe alors sur `src/` au lieu
d'être recopié :

```bash
pip install -e .
```

### Les variantes disponibles

| commande | ce qu'elle ajoute |
|---|---|
| `pip install -e .` | `mmu-cli` : le cœur, la CLI, la chaîne de scan et d'encodage |
| `pip install -e packaging/mmu-tui` | `mmu-tui` par-dessus : l'interface en terminal |
| `pip install -e ".[test]"` | de quoi lancer la suite de tests |
| `pip install -e ".[dev]"` | idem, plus `mutmut` pour les campagnes de mutation |
| `pip install -e ".[gui]"` | l'interface graphique Qt (PySide6), qui n'est pas le chemin nominal de cette version |
| `pip install -e ".[full]"` | `gui` + `dev` |

### Ce que chaque paquet tire

D'abord les dépendances de `mmu-cli`, celles du cœur :

<!-- FRONTIERE: dependances-de-base -->

| paquet | rôle |
|---|---|
| `numpy` | le calcul sur les images |
| `Pillow` | la lecture et l'écriture des TIFF |
| `jsonschema` | la validation du manifeste |
| `opencv-python-headless` | la détection ArUco, le décodage QR, le traitement d'image |
| `segno` | l'encodage des QR de page |
| `pypdfium2` | le rendu des PDF au scan |
| `reportlab` | la composition des planches |

Et celles de `mmu-tui`, le second paquet — il n'en ajoute que trois, dont une
qui est le premier paquet lui-même :

<!-- FRONTIERE: dependances-de-la-tui -->

| paquet | rôle |
|---|---|
| `mmu-cli` | le cœur et la ligne de commande, dont la TUI se sert |
| `textual` | le moteur de l'interface en terminal |
| `rich` | le rendu de texte de la console |

Ces deux tableaux sont **mesurés** : `tests/unit/test_documentation_utilisateur.py`
les compare aux `dependencies` des deux `pyproject.toml` **dans les deux sens**,
donc aucun ne peut annoncer un paquet absent ni en oublier un.

!!! note "Deux roues ont été choisies pour ce qu'elles n'exigent pas"
    `opencv-python-headless` plutôt que la roue complète (`EPIC11-ARB-253`) :
    les variantes non-headless lient douze bibliothèques système graphiques
    qu'une machine vierge n'a pas, et `import cv2` y échoue avant la première
    ligne du produit. Les 51 symboles `cv2.*` employés existent tous dans la
    roue non-contrib, `aruco.ArucoDetector` compris.

    `PySide6-Essentials` plutôt que `PySide6` dans l'extra `[gui]`
    (`EPIC11-ARB-254`) : le métapaquet tire aussi `PySide6-Addons`, 401 Mo dont
    186 Mo de Chromium, dont aucun module n'est importé nulle part.

!!! note "Ce que la base contient déjà"
    OpenCV, `reportlab` et `pypdfium2` sont dans les dépendances **de base**, et
    non dans un extra : ce ne sont pas des dépendances d'interface, c'est le
    moteur de détection et de rendu du cœur. Le seul élément réellement
    optionnel est l'interface Qt.

    La liste est mesurée dans les deux sens par
    `tests/unit/test_contrat_de_dependances.py` : rien d'importé qui manque à
    `pyproject.toml`, rien dans `pyproject.toml` que personne n'importe.

---

## 4. Les médias de test

Le dépôt porte un rush réel et de vrais scans, qui permettent de jouer
[le parcours complet](../guide-utilisateur/workflow.md) sans imprimante :

```bash
git lfs install
git lfs pull
```

**Sans `git-lfs`, ces fichiers ne lèvent aucune erreur** : ils valent 133 octets
et la panne apparaît beaucoup plus loin, sur un message de décodage
incompréhensible. Le diagnostic :

```bash
git lfs ls-files -n | while read f; do
  [ -f "$f" ] && [ "$(stat -c%s "$f")" -lt 500 ] && echo "POINTEUR $f"
done
```

Deux arbres lourds sont **exclus du téléchargement par défaut**, parce qu'ils
pèsent 178 Mo et 64 Mo et que personne n'en a besoin pour démarrer. Pour les
obtenir, il faut désarmer l'exclusion explicitement — `--include` seul ne suffit
pas :

```bash
git lfs pull --include="tests/fixtures/lots/**" --exclude=""
git lfs pull --include="tests/fixtures/rushes/reels/**" --exclude=""
```

Le verdict se lit sur la **taille du fichier** après coup : `git lfs pull`
affiche la même chose qu'il tire 178 Mo ou rien du tout.

---

## 5. Vérifier

```bash
mmu-tui --diagnostic-chemin
python -m mixed_media_utility.cli --version
```

Puis, pour de bon : `mmu-tui`. Vous devez arriver sur un explorateur de dossiers
intitulé « Ouvrir un projet ».

---

## 6. La commande `mmu`

`pip` ne pose qu'un point d'entrée, `mmu-tui`. Le raccourci `mmu` de la ligne de
commande vit dans `bin/` du dépôt et s'ajoute au `PATH` par un script :

### Linux, macOS

```bash
bash scripts/install-mmu.sh
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-mmu.ps1
```

Ouvrez un **nouveau** terminal, puis `mmu --help`. Sans ce raccourci, tout passe
par `python -m mixed_media_utility.cli`, à l'identique.

---

## Ce que contient le dépôt

```
mixed_media_utility/
├── src/mixed_media_utility/   le paquet
│   ├── cli.py                 la ligne de commande
│   ├── tui/                   l'interface en terminal (textual)
│   ├── gui/                   l'interface graphique (PySide6, optionnelle)
│   ├── io/                    manifeste, nommage, schémas JSON
│   ├── detection/             ArUco et QR
│   └── …                      extraction, planches, scan, encodage
├── bin/                       les deux raccourcis de lancement, POSIX et Windows
├── scripts/                   installation, mesure, campagnes de mutation
├── tests/                     la suite de tests et ses fixtures
├── docs/                      cette documentation (MkDocs Material)
├── pyproject.toml             packaging et dépendances
└── mkdocs.yml                 configuration de la documentation
```

!!! warning "`projects/` n'est plus versionné"
    Depuis le 2026-09-03, le dossier `projects/` est ignoré par git : il portait
    97 % du volume Git LFS du dépôt et aucun test ne le lisait. Ne vous étonnez
    pas de ne pas le trouver dans un clone neuf, et ne faites jamais
    `git add projects/`. Tout ce qu'un banc doit lire vit sous `tests/`.

---

## Construire une distribution

```bash
pip install build
python -m build --wheel
```

Produit `dist/mmu_tui-0.1.0-py3-none-any.whl` — une roue universelle, sans
étiquette de plateforme.

---

## Prévisualiser la documentation

```bash
pip install mkdocs mkdocs-material \
    mkdocs-git-revision-date-localized-plugin mkdocs-git-authors-plugin
mkdocs serve
```

La documentation est alors servie sur `http://127.0.0.1:8000`.

---

## Aller plus loin

Lancer la suite de tests, mener une campagne de mutation, contribuer : voir le
[guide développeur](../guide-developpeur/tests.md).
