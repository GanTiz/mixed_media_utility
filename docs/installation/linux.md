# Installation sur Linux

---

## 1. Ce qu'il faut avoir avant

| outil | version | pourquoi |
|---|---|---|
| **Python** | 3.11 ou plus | exigé par le paquet (`requires-python = ">=3.11"`) |
| **ffmpeg** *(avec `ffprobe`)* | 5.0 ou plus | l'outil l'appelle comme **binaire du système** ; il ne l'embarque pas |
| **git** | quelconque | *facultatif* — seulement pour récupérer les sources |
| **git-lfs** | quelconque | *facultatif* — seulement pour les médias de test du dépôt |

!!! info "Pourquoi ffmpeg 5.0 et pas moins"
    L'extraction emploie `-fps_mode passthrough`, sans quoi ffmpeg re-cadence la
    sortie et le nombre d'images écrites ne correspond plus à la sélection.
    Cette option n'existe qu'à partir de ffmpeg 5.0. En dessous, l'outil ne
    devine rien : il refuse en nommant la version exigée.

### Debian, Ubuntu, Mint

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv ffmpeg git git-lfs
```

### Fedora, RHEL, CentOS Stream

```bash
sudo dnf install python3 python3-pip ffmpeg git git-lfs
```

### Arch, Manjaro

```bash
sudo pacman -S python python-pip ffmpeg git git-lfs
```

### openSUSE

```bash
sudo zypper install python3 python3-pip ffmpeg git git-lfs
```

Vérifiez avant d'aller plus loin :

```bash
python3 --version     # doit afficher 3.11 ou plus
ffmpeg -version       # doit afficher 5.0 ou plus
ffprobe -version
```

---

## 2. Installer

### En une commande (recommandé)

```bash
curl -fsSL https://raw.githubusercontent.com/GanTiz/mixed_media_utility/main/scripts/install.sh | bash
```

Le script **pose ses questions au clavier** : ce que vous voulez installer
(la ligne de commande seule, ou avec l'interface en terminal), quoi faire si
`ffmpeg` manque, où ajouter les commandes, s'il faut poser un raccourci pour
lancer l'interface hors du terminal, et s'il faut vérifier l'installation à
la fin. Chaque question a une réponse par défaut, qu'`Entrée` valide — il
n'y a aucune syntaxe à connaître. Il installe au minimum **`mmu`**, la ligne
de commande.

Le raccourci n'est proposé que si vous demandez l'interface terminal **et**
qu'une session graphique est détectée. Il s'écrit dans votre dossier
personnel — `~/.local/share/applications/`, ou `$XDG_DATA_HOME/applications/`
si vous avez défini cette variable — et rien n'est posé pour les autres
comptes de la machine. `--desinstaller` le retire.

Sans terminal — dans un script, une image, une intégration continue — il
ne bloque pas : il prend les réponses par défaut et le dit.

### pipx, à la main

```bash
pipx install mmu-cli                                  # la ligne de commande seule
```

... ou les deux, sans rien installer en double :

```bash
pipx install mmu-tui                                  # pose `mmu-tui`
pipx inject --include-apps --force mmu-tui mmu-cli    # expose aussi `mmu`
```

`pipx` monte l'outil dans son propre environnement isolé et pose ses commandes
sur le `PATH`, sans mêler ses dépendances aux vôtres. C'est le mode
qui convient à une application. Si `pipx` manque :
`sudo apt install pipx` (ou `dnf`, `pacman`, `zypper`), puis
`pipx ensurepath`.

### pip, dans un venv

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install mmu-cli        # la ligne de commande seule : `mmu`
pip install mmu-tui        # ... ou les deux : `mmu-tui` s'appuie sur `mmu-cli`
```

L'interface graphique Qt est **optionnelle** et ne s'installe qu'à la demande :

```bash
pipx install "mmu-cli[gui]"
```

Pour travailler sur le code plutôt que l'utiliser, allez à
[l'installation depuis les sources](from-source.md).

!!! note "Poids, mesuré le 2026-09-07 sur les paquets construits"
    | installation | téléchargé | sur disque | ce qui pèse |
    |---|---|---|---|
    | `mmu-cli` | **89 Mo** | **305 Mo** | OpenCV 59 Mo, NumPy 17 Mo, Pillow 7 Mo |
    | `mmu-tui` | **93 Mo** | **333 Mo** | +28 Mo : `textual`, `rich` et leurs six transitives |
    | `mmu-cli[gui]` | **182 Mo** | **576 Mo** | PySide6-Essentials en plus, **+270 Mo** |

    Ces chiffres sont ceux d'un `venv` ordinaire. `pipx` en retire environ
    **28 Mo** : il n'installe ni `pip` ni `setuptools` dans l'environnement de
    l'application.

    OpenCV et NumPy pèsent **76 des 89 Mo** téléchargés, et ne sont pas
    retirables : c'est le moteur de détection ArUco, de décodage QR et de
    traitement d'image du cœur, employé par la chaîne de scan comme par la TUI.

**La roue OpenCV est la variante `-headless`, et ce n'est pas d'abord pour le poids**

Les roues `opencv-python` et `opencv-contrib-python` lient leur binaire à
**douze bibliothèques système de plus** — `libGL.so.1`, `libX11.so.6`,
`libglib-2.0.so.0`… — absentes d'un serveur nu, d'un conteneur minimal ou
d'un WSL sans serveur X. Sur ces postes, `import cv2` échoue **avant la
première ligne du produit**. La roue headless n'exige que la libc et la
libstdc++ : elle s'importe partout.

Ce que ça coûte, et c'est la seule chose : la **lecture previz** ouvre sa
fenêtre par `cv2.imshow`, que la roue headless ne compile pas. L'outil le
détecte et refuse en nommant le paquet, au lieu de mourir dans le natif.
Deux issues, jamais un blocage sec — lire sans fenêtre, la mesure de cadence
restant exacte, ou remplacer la roue :

```bash
pipx inject --force mmu-tui opencv-python
```

Cette roue-là exige alors `libGL` et `libX11`, à installer par le
gestionnaire de paquets du poste.

**Sauf si vous avez utilisé la ligne d'installation en une commande**

L'installateur en une ligne **détecte un affichage** et pose alors la roue
**avec** fenêtres à la place de la roue headless — c'est le défaut depuis le
7 septembre 2026, sur un outil de studio plutôt que de serveur. Les deux
roues livrent le **même module `cv2`** et ne se connaissent pas l'une
l'autre&nbsp;: `pip` ne voit jamais leur conflit, elles se **remplacent**
donc au lieu de s'empiler.

Ce qui vous concerne selon ce que vous avez tapé&nbsp;:

| ce que vous avez fait | la roue posée |
|---|---|
| la ligne en une commande, sur un poste avec écran | `opencv-python` |
| la ligne en une commande, sans affichage détecté | `opencv-python-headless` |
| `pip install mmu-cli` ou `pipx install mmu-cli` | `opencv-python-headless` |

Pour revenir à la roue sans fenêtres&nbsp;:

```bash
pipx inject --force mmu-tui opencv-python-headless
```

<a id="machine-vierge"></a>

### Depuis une machine vierge, entièrement à la main

Pour qui refuse `curl … | bash` — c'est un refus légitime —, ou installe sur
une machine dont il n'a pas choisi la configuration. **L'ordre compte** :
`pipx` a besoin de Python, l'application a besoin de `pipx`, et l'état des
lieux vient avant tout le reste.

#### 1. Ce qui est déjà là

La plupart des machines portent déjà deux des quatre outils. Installer
par-dessus est la première façon de casser une installation qui marchait. Ce
bloc se colle tel quel et rend un verdict, sur une machine vierge comme sur une
machine complète :

<!-- BLOC-DE-DETECTION -->
```sh
for outil in python3 ffmpeg ffprobe pipx; do
    if chemin=$(command -v "$outil" 2>/dev/null); then
        printf '%-8s OK      %s\n' "$outil" "$chemin"
    else
        printf '%-8s ABSENT\n' "$outil"
    fi
done
python3 --version 2>/dev/null
ffmpeg  -version 2>/dev/null | head -n 1
ffprobe -version 2>/dev/null | head -n 1
pipx    --version 2>/dev/null
```

Une ligne `ABSENT` désigne une étape ci-dessous à jouer ; une ligne `OK` la
dispense. **`ffmpeg` et `ffprobe` se lisent séparément**, et ce n'est pas un
détail : certains paquets minimalistes ne livrent que le premier, et la panne
survient alors des heures plus tard — à l'encodage, c'est-à-dire après
l'extraction, après l'impression, après le scan.

#### 2. Python, par la voie officielle du système

Python **3.11 ou plus**. La ligne de votre distribution, et rien d'autre :

```sh
sudo apt-get install python3 python3-pip python3-venv   # Debian, Ubuntu, Mint
sudo dnf install python3 python3-pip                    # Fedora, RHEL, CentOS Stream
sudo pacman -S python python-pip                        # Arch, Manjaro
sudo zypper install python3 python3-pip                 # openSUSE
sudo apk add python3 py3-pip                            # Alpine
```

Ce sont les paquets que le script d'installation demande lui-même à votre
gestionnaire. Si le dépôt de votre distribution reste sous 3.11 — c'est le cas
de Debian 11 et d'Ubuntu 20.04 —, la voie officielle est
<https://www.python.org/downloads/>, celle-là même que le script nomme quand il
ne peut pas poser Python.

Vérifiez avant de continuer :

```sh
python3 --version     # doit afficher 3.11 ou plus
```

#### 3. ffmpeg **et** ffprobe

**5.0 ou plus.** L'outil les appelle comme binaires du système ; il ne les
embarque pas. Les commandes ci-dessous sont exactement celles que le script
d'installation donne en secours quand son repli échoue — un lecteur de cette
page et un utilisateur dont le repli a échoué reçoivent la même chose :

```sh
sudo apt-get install ffmpeg   # Debian, Ubuntu, Mint
sudo dnf install ffmpeg       # Fedora, RHEL, CentOS Stream : dépôt RPM Fusion requis
sudo pacman -S ffmpeg         # Arch, Manjaro
sudo zypper install ffmpeg    # openSUSE
sudo apk add ffmpeg           # Alpine

ffmpeg  -version | head -n 1  # doit afficher 5.0 ou plus
ffprobe -version | head -n 1  # ffprobe vient avec le paquet — VÉRIFIEZ-LE
```

`pacman`, `zypper` et `apk` n'ont **aucune** commande épinglée dans le script :
ceux-là tombent dans sa branche générique, dont l'issue est la page officielle
du projet, <https://ffmpeg.org/download.html>. C'est aussi la vôtre si votre
distribution ne publie pas ffmpeg 5.0.

!!! warning "Pourquoi `ffprobe` se vérifie séparément"
    `install.ps1` teste les **deux** (`Test-Commande "ffmpeg"` **et**
    `Test-Commande "ffprobe"`) parce qu'un paquet qui ne fournirait que le
    premier laisse l'outil échouer beaucoup plus loin, à la lecture des
    métadonnées du rush. Faites de même à la main.

#### 4. pipx, puis `pipx ensurepath`

`pipx` monte l'application dans son propre environnement isolé et expose ses
commandes sur le `PATH`, sans mêler ses dépendances aux vôtres. Depuis la
PEP 668, c'est aussi la seule voie qu'un Python de distribution accepte sans
protester.

```sh
sudo apt-get install pipx         # Debian, Ubuntu, Mint
sudo dnf install pipx             # Fedora, RHEL, CentOS Stream
sudo pacman -S python-pipx        # Arch, Manjaro
sudo zypper install python3-pipx  # openSUSE
sudo apk add pipx                 # Alpine
```

Si votre distribution ne le publie pas, le repli officiel — c'est celui que le
script emprunte lui aussi :

```sh
python3 -m pip install --user pipx
```

Puis, dans les deux cas :

```sh
pipx ensurepath
```

`ensurepath` ajoute `~/.local/bin` à votre profil. **Ouvrez un nouveau
terminal** ensuite, sans quoi les commandes posées à l'étape suivante ne seront
pas trouvées.

#### 5. L'application

Un seul paquet suffit : `mmu-tui` s'appuie sur `mmu-cli`.

```sh
pipx install mmu-tui
pipx inject --include-apps --force mmu-tui mmu-cli
```

La seconde ligne n'est pas facultative, et c'est mesuré : `pipx install
mmu-tui` installe bien `mmu-cli` dans le venv, mais **pipx n'expose que les
scripts du paquet principal** — sans la greffe, la commande `mmu` n'arrive
jamais sur le `PATH`. `--include-apps` l'y enregistre ; `--force` est
nécessaire parce que sans lui pipx répond « already seems to be installed » et
ne réenregistre rien.

Pour la ligne de commande seule, sans l'interface en terminal :

```sh
pipx install mmu-cli
```

### Pour tous les utilisateurs de la machine { #tous-les-utilisateurs }

`pipx` est **par utilisateur** par construction. Une installation partagée se
fait en le pointant hors du compte courant, sous `sudo` :

```sh
sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install mmu-tui
sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin \
     pipx inject --include-apps --force mmu-tui mmu-cli
```

Les commandes atterrissent alors dans `/usr/local/bin`, qui est sur le `PATH`
de tous les comptes.

**Ce que ça ne dispense pas de faire, et c'est la moitié de l'information.**
« Tous les utilisateurs » ne supprime pas la corvée par compte, il la déplace :
**chaque compte** garde son propre `PATH`, son propre profil de shell et son
propre raccourci de menu. Un compte dont le `PATH` ne contient pas
`/usr/local/bin` ne verra rien, et aucun `pipx ensurepath` lancé en `root` ne
le lui ajoutera.

!!! note "Il n'y a pas de drapeau pour ça"
    Le script d'installation **n'ajoute aucune option** « tous les
    utilisateurs », et c'est délibéré : dans le one-liner, ces deux lignes
    deviennent un `curl … | bash` qui réclame un mot de passe administrateur
    sur le chemin nominal. La voie ci-dessus est exacte et se lance à la main,
    en connaissance de cause.

### Les médias de test (facultatif)

Cette section suppose une **copie du dépôt** ; une installation par PyPI
n'en a pas besoin.

Le dépôt porte un rush réel et de vrais scans, qui permettent de jouer
[le parcours complet](../guide-utilisateur/workflow.md) sans avoir rien à
imprimer. Ils sont suivis par Git LFS :

```bash
git lfs install
git lfs pull
```

**Sans `git-lfs`, ces fichiers ne lèvent aucune erreur** : ils valent 133 octets
et la panne apparaît beaucoup plus loin, sur un message de décodage
incompréhensible. Pour vérifier :

```bash
git lfs ls-files -n | while read f; do
  [ -f "$f" ] && [ "$(stat -c%s "$f")" -lt 500 ] && echo "POINTEUR $f"
done
```

Rien en sortie, tout est là.

---

## 3. Vérifier que ça marche

```bash
mmu-tui --diagnostic-chemin
```

Elle affiche ce que la TUI voit de son environnement — chemins d'import, variables de la console, glyphes à risque — puis sort **sans
rien lancer**. C'est la commande à lire en premier quand l'affichage est
étrange.

**La ligne de commande répond aussi**

```bash
mmu --version
```

Après un `pip install` dans un venv, le paquet est en plus importable :
`python -m mixed_media_utility.cli --version` donne le même résultat.

Puis, pour de bon :

```bash
mmu-tui
```

Vous devez arriver sur un explorateur de dossiers intitulé **« Ouvrir un
projet »**. La suite est dans [l'interface en terminal](../guide-utilisateur/tui.md).

---

## 4. Les deux commandes

Depuis la première version publiée, **`pip` pose bien la commande `mmu`** :
elle vient de `mmu-cli`, le paquet qui porte le cœur et la ligne de commande.
`mmu-tui` est un second paquet, qui s'appuie sur le premier.

| ce que vous installez | ce que vous obtenez |
|---|---|
| `mmu-cli` | `mmu` |
| `mmu-tui` | `mmu` **et** `mmu-tui` — rien n'est installé deux fois |
| `mmu-cli[gui]` | `mmu`, plus l'interface graphique Qt |

Les deux paquets se partagent le cœur : installer les deux dans un même
environnement ne coûte que **28 Mo de plus** que la ligne de commande seule,
et le cœur n'y figure qu'**une fois**.

**Le piège de `pipx`, mesuré le 2026-09-07**

`pipx install mmu-tui` installe bien `mmu-cli` dans l'environnement de
l'application — le binaire `mmu` existe à l'intérieur —, mais **`pipx`
n'expose que les commandes du paquet principal** : `mmu` n'arrive pas sur
le `PATH`. `pipx expose` n'y change rien, il ne relie que les commandes
déjà enregistrées. Un seul geste le corrige :

```bash
pipx inject --include-apps --force mmu-tui mmu-cli
```

Le `--force` est nécessaire : sans lui, `pipx` répond *« already seems to
be installed »* et ne réenregistre pas les commandes. L'installation en
une commande le fait pour vous.

!!! warning "N'installez pas les deux par deux `pipx install` séparés"
    `pipx` isole chaque application dans son propre environnement : deux
    installations séparées mettent **deux exemplaires du cœur** sur le disque —
    **702 Mo** au lieu de 333, mesuré le 2026-09-07. Le téléchargement, lui,
    n'est pas doublé : `pip` sert le second depuis son cache.

!!! note "Depuis un dépôt cloné"
    `bash scripts/install-mmu.sh` ajoute le `bin/` du dépôt au `PATH` et
    donne, lui aussi, une commande `mmu` — celle du dépôt, pas celle du paquet
    installé. Les deux peuvent coexister, et c'est alors l'ordre du `PATH` qui
    décide laquelle répond. Pour travailler sur le code c'est ce qu'on veut ;
    pour utiliser l'outil, préférez le paquet.

---

## 5. Problèmes fréquents

### `mmu-tui: command not found`

Le venv n'est pas activé (`source .venv/bin/activate`), ou vous avez installé
avec `pip install --user` et `~/.local/bin` n'est pas dans le `PATH` :

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Repli qui marche toujours : `python -m mixed_media_utility.tui`.

### `Binaire ffmpeg introuvable dans le PATH`

Installez ffmpeg par votre gestionnaire de paquets, puis ouvrez un nouveau
terminal.

### `Cette version de ffmpeg ne connait pas l'option '-fps_mode'`

Votre ffmpeg est antérieur à 5.0. Les dépôts de certaines distributions
anciennes en livrent encore une version 4.x — prenez une version récente, ou une
build statique.

### Glyphes qui s'affichent en carrés

Rare sous Linux : les polices de console usuelles (DejaVu Sans Mono, Fira Code,
JetBrains Mono) portent les caractères employés. Si cela arrive quand même,
`mmu-tui --ascii` bascule sur un repli intégral.

### Pas de couleur

`mmu-tui` respecte la convention `NO_COLOR` : `NO_COLOR=1 mmu-tui` suffit.
L'option `--sans-couleur` fait la même chose explicitement.

---

<a id="mettre-a-jour"></a>

## 6. Mettre à jour

```bash
bash scripts/install.sh --mettre-a-jour
```

Sans le script sous la main, la même chose en une ligne :

```bash
curl -fsSL https://raw.githubusercontent.com/GanTiz/mixed_media_utility/main/scripts/install.sh | bash -s -- --mettre-a-jour
```

Sans drapeau, sur une machine où l'outil est déjà posé, le script **pose la
question** plutôt que de décider : le mettre à jour, tout réinstaller de zéro,
ou ne rien changer et sortir.

**Ce que la mise à jour touche, et c'est tout :** la distribution `pipx` et le
`mmu-cli` greffé dedans. La greffe n'est pas un détail — sans
`--include-injected`, `pipx` mettrait à jour `mmu-tui` et laisserait `mmu` à
son ancienne version. La voie manuelle équivalente :

```bash
pipx upgrade mmu-tui --include-injected
```

… ou, si vous n'avez posé que la ligne de commande :

```bash
pipx upgrade mmu-cli
```

**Ce qu'elle ne touche PAS : ni Python, ni ffmpeg, ni `pipx`.** Ce sont des
dépendances du système, et elles se mettent à jour par le système —
`sudo apt-get install ffmpeg`, `sudo dnf install ffmpeg`, ou la commande de
votre distribution. Ce n'est pas un détail d'implémentation : « mise à jour »
sans précision laisse croire que **tout** est mis à jour, et l'on conclut
alors à un bogue de l'outil le jour où un `ffmpeg` de 2019 refuse l'option
`-fps_mode` — c'est exactement le symptôme décrit en *Problèmes fréquents*
ci-dessus, et sa cause est un `ffmpeg` que la mise à jour de l'application n'a
jamais promis de toucher.

---

<a id="desinstaller"></a>

## 7. Désinstaller

```bash
bash scripts/install.sh --desinstaller
```

… ou, sans le script sous la main :

```bash
curl -fsSL https://raw.githubusercontent.com/GanTiz/mixed_media_utility/main/scripts/install.sh | bash -s -- --desinstaller
```

**Le script demande d'abord jusqu'où aller, avant de retirer quoi que ce
soit.** « Tout supprimer » et « juste `mmu` » ne sont pas le même acte, et
taper un seul drapeau ne peut pas vouloir dire les deux :

```
Que faut-il retirer ?
      1) l'application seule -- ni Python, ni ffmpeg, ni pipx [defaut]
      2) l'application ET ce que CE SCRIPT a pose (ffmpeg, ffprobe, pipx)
      3) rien pour l'instant -- montre-moi les commandes pour le reste
    Ton choix [1] puis Entree :
```

### L'issue 1 — l'application seule, et c'est le défaut

`--non-interactif` prend ce défaut : une machine muette — un script, une
image, une intégration continue, une entrée fermée — ne retire **jamais** plus
que l'application. Partent alors les quatre distributions `pipx` (`mmu-tui`,
`mmu-cli`, et leurs versions de bac à sable `mmu-tui-test` et `mmu-cli-test`),
la ligne que `pipx` a ajoutée à votre profil — une copie du fichier est gardée
en `.mmu-sauvegarde` avant d'y toucher —, le raccourci du menu des
applications, et le reçu décrit ci-dessous.

Ni Python, ni ffmpeg, ni `pipx` ne sont touchés.

### L'issue 2 — l'application **et ce que ce script a posé**

Elle ne devine rien, et surtout elle ne balaie pas votre machine : elle relit
un **reçu**, écrit au moment de la pose.

```bash
cat "${XDG_STATE_HOME:-$HOME/.local/state}/mmu/pose-par-installeur.txt"
```

Une ligne par objet, trois champs séparés par une tabulation : la nature, le
chemin absolu, la date. Ce qu'il enregistre ici : les `ffmpeg` et `ffprobe`
que le script a déposés **lui-même**, quand votre gestionnaire de paquets ne
pouvait pas les poser, et `pipx` si c'est ce script qui l'a posé. Trois
conséquences, et elles comptent :

* **un binaire présent mais absent du reçu n'est jamais touché.** Un `ffmpeg`
  venu d'`apt` appartient à `apt` : le retirer par un `rm` laisserait votre
  gestionnaire avec un paquet fantôme ;
* **un chemin du reçu qui a disparu est dit, puis sauté** — quelqu'un l'a déjà
  retiré à la main, et le lui dire vaut mieux que faire comme si le reçu avait
  raison ;
* **`pipx` n'est jamais retiré par un `rm`.** Le script repasse par la voie
  qui l'a posé — le paquet de votre distribution, ou `pip --user` —, et il
  **nomme d'abord les autres applications que `pipx` gère**, qui perdraient
  leurs commandes. `pipx uninstall-all` les reprend proprement avant.

**Si le reçu manque** — installation antérieure à ce mécanisme, fichier
effacé —, l'issue 2 **se rabat sur l'issue 1 en le disant**, et vous renvoie à
l'issue 3 pour le reste. Jamais un blocage sec.

**Python n'est jamais retiré, même s'il figure au reçu.** C'est une frontière
du produit et non une prudence — l'issue 3 dit pourquoi.

**Le reçu se retire lui-même**, par l'issue 1 comme par l'issue 2.

### L'issue 3 — elle affiche, et elle ne fait pas

Elle sort **avant le premier retrait** : après elle, rien n'a bougé — ni les
distributions, ni le profil, ni le raccourci, ni le reçu. Elle affiche les
voies officielles de retrait de `ffmpeg`, de `pipx` et de Python, pour la voie
par laquelle chacun est arrivé sur cette machine :

```
    Pour RETIRER ffmpeg, la voie la plus officielle disponible :
      sudo apt-get remove ffmpeg

    Pour RETIRER pipx, la voie la plus officielle disponible :
      pipx uninstall-all      (les autres applications posees par pipx)
      sudo apt-get remove pipx
```

**Pourquoi elle affiche au lieu de faire.** Ces trois-là n'appartiennent pas à
l'outil. Retirer le paquet `python3` de votre distribution en emporte une
partie — le gestionnaire de paquets lui-même en dépend, et l'interpréteur du
système n'a pas été posé par cette installation. La commande n'est
volontairement pas écrite ici : elle se recopie trop bien. De même, un
`ffmpeg` venu d'`apt` ou de `dnf` appartient à `apt` ou à `dnf` ; le retirer
autrement que par eux les laisse dans un état faux. Le script ne donne donc
**aucune commande de retrait pour Python** : il renvoie à
<https://www.python.org/downloads/> et vous laisse décider.

### À la main, si vous n'avez plus le script

```bash
pipx uninstall mmu-tui   # l'interface en terminal
pipx uninstall mmu-cli   # la ligne de commande
# ou, dans un venv : pip uninstall mmu-tui mmu-cli
rm -f "${XDG_DATA_HOME:-$HOME/.local/share}/applications/mmu-tui.desktop"
rm -rf "${XDG_STATE_HOME:-$HOME/.local/state}/mmu"
```

Puis retirez de votre `~/.bashrc` (ou `~/.zshrc`, `~/.profile`) la ligne de
`PATH` qu'a ajoutée `pipx ensurepath` — elle est précédée d'un commentaire
`# Created by pipx on …` qui la nomme.

Vos projets sont des dossiers ordinaires : **rien ne les touche**. Hors
projet, l'outil écrit la liste des projets récents,
`~/.config/mixed_media_utility/recents-v1.json`, et — si vous l'avez accepté —
le raccourci du menu nommé juste au-dessus.
