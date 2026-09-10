# Essayer l'outil sur une machine jetable, qui n'a rien

**Pourquoi cette voie existe.** L'installation en une commande promet de poser
ce qui manque — Python, ffmpeg, pipx, et sous Windows `winget` lui-même. Cette
promesse n'a jamais été vérifiée sur une vraie machine vierge : ce qui a été
mesuré jusqu'ici, c'est un venv neuf dans un conteneur Linux, ce qui ne dit rien
de l'amorçage de `winget` ni de Homebrew.

Un bac à sable jetable est le seul endroit où l'essayer sans salir sa machine,
et le seul où un échec d'amorçage se voit **avant** un utilisateur.

---

## Windows — `Windows Sandbox`, intégré au système

Deux fichiers de ce dossier se double-cliquent :

| fichier | ce qu'il fait |
|---|---|
| `windows-vierge.wsb` | ouvre un Windows jetable et lance l'installation **interactive** depuis le vrai PyPI — le chemin exact d'un inconnu |
| `windows-vierge-testpypi.wsb` | même chose, mais **sans aucune question** et depuis **TestPyPI** — la forme à employer pour valider un candidat de release |

**À faire une seule fois**, dans un PowerShell **administrateur** — un
redémarrage est demandé à la fin :

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName "Containers-DisposableClientVM" -All
```

**Ce que ça vaut.** Tout ce qui se passe dans la fenêtre est détruit à sa
fermeture ; la machine hôte n'est pas touchée. Le bac à sable n'a **ni Python,
ni ffmpeg, ni pipx, ni Microsoft Store, ni winget** — c'est-à-dire exactement la
machine que l'installeur prétend savoir amorcer.

**Ce que ça ne couvre pas, dit plutôt que tu :**

* **l'édition Familiale (Home) n'a pas Windows Sandbox.** Il faut Pro,
  Enterprise ou Education, et la virtualisation active dans le BIOS/UEFI. Sur
  une Home, la voie de remplacement est une machine virtuelle ordinaire
  (Hyper-V, VirtualBox, VMware) créée depuis une ISO Windows d'évaluation ;
* **l'amorçage de `winget` dans ce bac à sable n'est pas mesuré.** L'installeur
  y répond par `Install-Module Microsoft.WinGet.Client` puis
  `Repair-WinGetPackageManager` ; sans Microsoft Store, ce chemin est
  plausible mais **non vérifié**. C'est précisément ce que le premier essai
  répondra, et le résultat vaut d'être noté ici, quel qu'il soit ;
* **`Install-Module` peut demander d'installer le fournisseur NuGet** et de
  faire confiance à PSGallery, au premier lancement. Répondre oui.

---

## macOS — pas d'équivalent intégré, trois voies

macOS n'a rien qui ressemble à Windows Sandbox. Ce qui suit est **documenté,
non mesuré depuis ce dépôt** : aucune de ces trois voies n'a été jouée ici.

**1. `tart`, sur Mac Apple Silicon — le plus proche du double-clic.**

```bash
brew install cirruslabs/cli/tart
tart clone ghcr.io/cirruslabs/macos-sequoia-vanilla:latest vierge
tart run vierge
```

Puis, **dans la machine virtuelle** :

```bash
curl -fsSL https://raw.githubusercontent.com/GanTiz/mixed_media_utility/main/scripts/install.sh | bash
```

Prendre l'image `vanilla` et non `base` : la seconde porte déjà des outils de
développement, ce qui n'est plus une machine vierge. `tart` est gratuit pour un
usage personnel. Il se supprime avec `tart delete vierge`.

**2. UTM + un `.ipsw` d'Apple**, sur Apple Silicon. Plus long, mais l'image
vient d'Apple et de personne d'autre : c'est la voie à prendre si la
provenance d'une image tierce gêne.

**3. Un Mac Intel** ne peut pas utiliser les deux premières. VMware Fusion
(gratuit pour un usage personnel) sait faire tourner un macOS invité.

**Ce qui n'est PAS un substitut, et l'erreur est facile :** créer un nouveau
**compte utilisateur** macOS ne donne pas une machine vierge. Homebrew
(`/opt/homebrew`), Python et ffmpeg sont installés à l'échelle du système et
restent visibles depuis le compte neuf. L'essai serait vert sans rien prouver.

---

## Les runners de la CI — gratuits, mais ils ne mesurent pas la même chose

`windows-latest` et `macos-latest` sont jetables et gratuits sur un dépôt
public. Ils portent en revanche **Python déjà installé**, et le runner macOS
porte Homebrew : ils valident donc `pipx install`, jamais l'amorçage que cette
page existe pour éprouver. Utiles, et pour autre chose.
