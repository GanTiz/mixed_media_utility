# Mixed Media Utility

**Faire passer une séquence vidéo par le papier, et la récupérer.**

À partir d'un rush, l'outil extrait des images, les compose en planches A4
imprimables portant de quoi les relire — un QR par page, des marqueurs ArUco aux
coins, des pastilles de calibration. Vous imprimez, vous travaillez le papier —
peinture, découpe, tampon, ce que vous voulez —, vous scannez : l'outil retrouve
chaque image, la redresse, la recale en couleur et reconstruit une vidéo.

```
rush ──▶ frames ──▶ planches ──▶ [papier] ──▶ scan ──▶ frames ──▶ master
```

Rien de ce qui entre ne se perd : chaque objet produit — lot, master, planche,
scan — se **versionne** plutôt que de s'écraser, et rien n'est jamais remplacé
sans que vous l'ayez demandé.

> **v0.1.0 — première publication.** Installation et parcours documentés pour
> Windows, macOS et Linux. Les retours sont les bienvenus.

## Installation

**En une commande.** Le script pose ses questions au clavier et n'exige aucune
syntaxe.

**Linux · macOS**

```bash
curl -fsSL https://raw.githubusercontent.com/GanTiz/mixed_media_utility/main/scripts/install.sh | bash
```

**Windows** (PowerShell)

```powershell
irm https://raw.githubusercontent.com/GanTiz/mixed_media_utility/main/scripts/install.ps1 | iex
```

**Ce que le script installe s'il manque**, et c'est là tout son intérêt :
**Python** (≥ 3.11), **ffmpeg** avec `ffprobe`, et **pipx**. Sur Windows il pose
même `winget` au besoin. Deux réserves, dites plutôt que tues : `ffmpeg` fait
l'objet d'une question — la réponse par défaut est « oui » —, et son
installation demande le mot de passe administrateur. Sur macOS sans Homebrew, le
script s'arrête et vous donne la commande à lancer d'abord.

**À la main**, si vous préférez. Il vous faut alors **Python ≥ 3.11** et
**ffmpeg ≥ 5.0** (avec `ffprobe`) déjà sur le `PATH` — `pipx` ne les pose pas :

```bash
pipx install mmu-tui
```

Un seul paquet suffit : `mmu-tui` s'appuie sur `mmu-cli` et vous donne les deux
commandes. `pipx install mmu-cli` pose la ligne de commande seule. L'interface
graphique Qt est un extra optionnel : `pipx install "mmu-cli[gui]"`.

**Depuis une machine vierge, entièrement à la main.** Si Python, ffmpeg ou pipx
manquent et que vous ne voulez pas d'un script, chaque page porte le chemin
complet — un bloc de détection à copier-coller d'abord, puis Python, ffmpeg
*et* `ffprobe`, pipx, l'application, dans cet ordre :
[Windows](docs/installation/windows.md#machine-vierge) ·
[macOS](docs/installation/macos.md#machine-vierge) ·
[Linux](docs/installation/linux.md#machine-vierge). La voie **pour tous les
utilisateurs de la machine** y est écrite aussi, avec ce qu'elle ne dispense
pas de faire.

**L'essayer sans rien installer.** Sur un Windows Pro, Enterprise ou Education,
`Windows Sandbox` ouvre une machine jetable qui n'a ni Python, ni ffmpeg, ni
pipx — c'est-à-dire exactement ce que le script prétend savoir poser. Deux
fichiers se double-cliquent : `scripts/bac-a-sable/windows-vierge.wsb` pour le
chemin nominal, `scripts/bac-a-sable/windows-vierge-testpypi.wsb` pour essayer
un candidat de release. Tout est détruit à la fermeture de la fenêtre. Les
voies équivalentes sur macOS, et ce qui n'en est pas une, sont dans
[la note du dossier](scripts/bac-a-sable/README.md).

**Mettre à jour.** Relancer le script avec `--mettre-a-jour`
(`-MettreAJour` sous Windows), ou, à la main,
`pipx upgrade mmu-tui --include-injected` — la greffe compte, sans elle `mmu`
resterait à son ancienne version. **Ce qu'il ne met à jour ni ne prétend
mettre à jour : ni Python, ni ffmpeg, ni `pipx`**, qui restent à la charge du
système. Le dire évite de conclure à un bogue le jour où un `ffmpeg` de 2019
refuse une option :
[Windows](docs/installation/windows.md#mettre-a-jour) ·
[macOS](docs/installation/macos.md#mettre-a-jour) ·
[Linux](docs/installation/linux.md#mettre-a-jour).

**Désinstaller.** Avec `--desinstaller` (`-Desinstaller` sous Windows), le
script **demande d'abord jusqu'où aller** — l'application seule, ce qui est le
défaut ; ou aussi ce que *ce script* a posé, et lui seul, d'après un reçu ; ou
rien du tout, auquel cas il affiche les commandes officielles et n'exécute
rien. Python n'est jamais retiré, même s'il figure au reçu. Le détail des
trois issues :
[Windows](docs/installation/windows.md#desinstaller) ·
[macOS](docs/installation/macos.md#desinstaller) ·
[Linux](docs/installation/linux.md#desinstaller).

Le détail par plateforme — [Windows](docs/installation/windows.md),
[macOS](docs/installation/macos.md), [Linux](docs/installation/linux.md) — et
[l'installation depuis les sources](docs/installation/from-source.md).

## Premier lancement

```
mmu-tui
```

C'est le chemin nominal : un projet se crée, un rush s'y ajoute et le parcours
se déroule d'écran en écran. Tout est aussi scriptable :

```
mmu --help
```

| commande | ce qu'elle ouvre | posée par |
|---|---|---|
| `mmu` | la ligne de commande, scriptable | `pip install mmu-cli` |
| `mmu-tui` | l'interface en terminal, chemin nominal | `pip install mmu-tui` |

Deux paquets, et `mmu-tui` s'appuie sur `mmu-cli` : l'installer donne les deux
commandes sans rien poser en double. La distribution s'appelle `mmu-cli` parce
que le nom `mmu` est déjà pris sur l'index public ; la commande reste `mmu`.

## Documentation

* [Le parcours complet](docs/guide-utilisateur/workflow.md) — d'un rush au
  master, joué sur les fichiers du dépôt
* [Les mots de l'outil](docs/guide-utilisateur/concepts.md) — projet, rush, lot,
  planche, scan, master, profil, version
* [L'interface en terminal](docs/guide-utilisateur/tui.md) et
  [la ligne de commande](docs/guide-utilisateur/cli.md)
* [Référence des commandes](docs/reference/commandes.md) et
  [configuration](docs/reference/configuration.md)
* [Guide développeur](docs/guide-developpeur/architecture.md) — architecture,
  tests, conventions, contribution
* [Packaging et publication](docs/reference/packaging.md) — TestPyPI puis PyPI,
  avec une porte humaine entre les deux

## S'orienter dans le dépôt

| où | quoi |
|---|---|
| `src/mixed_media_utility` | le produit. `cli.py` et le cœur à la racine du paquet, `tui/` l'interface en terminal, `io/` la lecture-écriture des projets, `detection/` les marqueurs, `specs/` le schéma des manifestes |
| `tests/` | les bancs, et `tests/fixtures/` les artefacts de terrain — scans réels, captures ArUco, QR à 300 dpi |
| `docs/` | la documentation publiée, telle que `mkdocs.yml` la compose |
| `scripts/` | `install.sh` et `install.ps1`, plus l'outillage de mesure et de mutation |
| `bin/` | des raccourcis `mmu` et `mmu-tui` utilisables sans rien installer, depuis un clone |
| `packaging/` | le second `pyproject.toml`, celui de la distribution `mmu-tui` |
| `.github/` | la construction des roues, TestPyPI puis PyPI |

Pour contribuer, [le guide développeur](docs/guide-developpeur/contribuer.md)
dit comment lancer la suite et ce que le dépôt attend d'un test. Les fixtures de
terrain y sont en **Git LFS** (~28 Mo) : `git-lfs` est nécessaire pour jouer la
suite, et pour elle seule — installer l'outil depuis PyPI n'en demande rien.

## Licence

**GPL-3.0-or-later** — texte intégral dans [LICENSE](LICENSE). Les composants
tiers et ce que leurs licences exigent à la distribution sont recensés dans
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
