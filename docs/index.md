# Mixed Media Utility

**Faire passer une séquence vidéo par le papier, et la récupérer.**

Vous partez d'un rush. L'outil en extrait des images, les compose en planches A4
imprimables portant de quoi les relire — un QR par page, des marqueurs de
repérage aux coins, des pastilles de couleur. Vous imprimez, vous travaillez le
papier à la main, vous scannez. L'outil retrouve chaque image, la redresse, la
recale en couleur, et reconstruit une vidéo.

```
rush ──▶ frames ──▶ planches ──▶ [papier] ──▶ scan ──▶ frames ──▶ master
```

---

## Par où commencer

| vous voulez… | allez à |
|---|---|
| **installer l'outil** | [Windows](installation/windows.md) · [macOS](installation/macos.md) · [Linux](installation/linux.md) · [depuis les sources](installation/from-source.md) |
| **le voir marcher de bout en bout** | [Le parcours complet](guide-utilisateur/workflow.md), joué sur les fichiers du dépôt |
| **comprendre le vocabulaire** | [Les mots de l'outil](guide-utilisateur/concepts.md) |
| **le piloter** | [L'interface en terminal](guide-utilisateur/tui.md) · [La ligne de commande](guide-utilisateur/cli.md) |
| **une option précise** | [Référence des commandes](reference/commandes.md) · [Configuration](reference/configuration.md) |

---

## Ce que vous lancez

| commande | ce qu'elle ouvre | posée par |
|---|---|---|
| **`mmu`** | la ligne de commande, scriptable | `pip install mmu-cli` |
| **`mmu-tui`** | l'interface en terminal — le chemin nominal | `pip install mmu-tui` |

Deux paquets, et le second s'appuie sur le premier : **installer `mmu-tui`
donne les deux commandes**, sans rien poser en double. La distribution
s'appelle `mmu-cli` parce que le nom `mmu` est déjà pris sur l'index public ;
la commande, elle, reste `mmu`.

---

## Installation, en bref

```bash
curl -fsSL https://raw.githubusercontent.com/GanTiz/mixed_media_utility/main/scripts/install.sh | bash
```

Le script pose ses questions au clavier — ce que vous voulez installer, quoi
faire si `ffmpeg` manque — et n'exige aucune syntaxe. À la main, si vous
préférez :

```bash
pipx install mmu-cli    # la ligne de commande seule
pipx install mmu-tui    # ... ou les deux (voir la page de votre système)
```

Prérequis : **Python 3.11 ou plus**, et **ffmpeg 5.0 ou plus** — avec `ffprobe`
— accessible depuis le terminal. L'outil appelle ffmpeg comme binaire du
système ; il ne l'embarque pas. Le détail par plateforme est sur sa page
d'installation.

L'interface graphique Qt est optionnelle : `pipx install "mmu-cli[gui]"`.

---

## Trois principes, qui expliquent la plupart des messages

**Rien n'est deviné.** La résolution d'un scan est exigée, jamais déduite. Aucun
profil de calibration n'est choisi à votre place. Aucune cadence source n'est
repliée sur la cadence cible. Quand une information manque, l'outil la déclare
manquante plutôt que de la reconstituer.

**Rien n'est écrasé en silence, et rien n'est bloqué sèchement.** Devant une
sortie qui existe déjà, l'outil propose toujours au moins deux issues : écrire
une version voisine (`_v2`, `_v3`…), ou écraser sciemment après avertissement.
Cinq objets sont versionnables — lots, masters, planches, scans, lots
scannés — et la suppression, qui est la troisième opération, retire du
manifeste **et** du disque.

**Ce qui n'a pas été fait est déclaré non fait.** Un lot scanné sans profil de
calibration sort `not_applied` et le dit. Un lot incomplet reste incomplet :
aucun trou n'est jamais comblé par répétition de l'image précédente.

---

## Liens

* **Dépôt** : [github.com/GanTiz/mixed_media_utility](https://github.com/GanTiz/mixed_media_utility)
* **Signaler un problème** : [les issues](https://github.com/GanTiz/mixed_media_utility/issues)
* **Versions publiées** : [les releases](https://github.com/GanTiz/mixed_media_utility/releases)

---

## Licence

Le projet est distribué sous **GNU General Public License v3.0 ou ultérieure**
(GPL-3.0-or-later) — le texte intégral est dans [LICENSE](../LICENSE).

Concrètement : vous pouvez utiliser, étudier, modifier et redistribuer ce
logiciel librement. La seule contrepartie est la réciprocité — si vous
distribuez une version modifiée, elle doit l'être sous la même licence, code
source compris.

Les composants tiers et leurs licences propres sont recensés dans
[THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md), avec ce que chacun exige à
la distribution.
