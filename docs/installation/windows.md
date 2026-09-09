# Installation sur Windows

---

## 1. Ce qu'il faut avoir avant

| outil | version | pourquoi |
|---|---|---|
| **Python** | 3.11 ou plus | exigé par le paquet (`requires-python = ">=3.11"`) |
| **ffmpeg** *(avec `ffprobe`)* | 5.0 ou plus | l'outil l'appelle comme **binaire du système** ; il ne l'embarque pas |
| **git** | quelconque | *facultatif* — seulement pour récupérer les sources |
| **git-lfs** | quelconque | *facultatif* — seulement pour les médias de test du dépôt |

Le plus simple, dans un PowerShell :

```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg
winget install Git.Git
winget install GitHub.GitLFS
```

Sinon, à la main : [python.org](https://python.org/downloads/windows/) — **cochez
« Add python.exe to PATH »** —, une build *essentials* ou *full* de
[gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) dont vous ajoutez
le dossier `bin` au `PATH`, et [git-scm.com](https://git-scm.com/download/win).

Ouvrez ensuite un **nouveau** terminal — les fenêtres déjà ouvertes ne voient pas
les changements de `PATH` — et vérifiez :

```powershell
python --version      # doit afficher 3.11 ou plus
ffmpeg -version       # doit afficher 5.0 ou plus
ffprobe -version
```

!!! info "Pourquoi ffmpeg 5.0 et pas moins"
    L'extraction emploie `-fps_mode passthrough`, sans quoi ffmpeg re-cadence la
    sortie et le nombre d'images écrites ne correspond plus à la sélection.
    Cette option n'existe qu'à partir de ffmpeg 5.0. En dessous, l'outil ne
    devine rien : il refuse en nommant la version exigée.

---

## 2. Installer

### En une commande (recommandé)

```powershell
irm https://raw.githubusercontent.com/GanTiz/mixed_media_utility/main/scripts/install.ps1 | iex
```

Le script **pose ses questions au clavier** : ce que vous voulez installer
(la ligne de commande seule, ou avec l'interface en terminal), quoi faire si
`ffmpeg` manque, où ajouter les commandes, s'il faut poser un raccourci dans
le menu Démarrer, et s'il faut vérifier l'installation à la fin. Chaque
question a une réponse par défaut, qu'`Entrée` valide — il n'y a aucune
syntaxe à connaître. Il installe au minimum **`mmu`**, la ligne de commande.

Le raccourci s'écrit dans **votre** menu Démarrer, jamais dans celui de tous
les comptes. `-Desinstaller` le retire.

Sans terminal — dans un script, une image, une intégration continue — il
ne bloque pas : il prend les réponses par défaut et le dit.

### pipx, à la main

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
pipx install mmu-cli                                  # la ligne de commande seule
```

... ou les deux, sans rien installer en double :

```bash
pipx install mmu-tui                                  # pose `mmu-tui`
pipx inject --include-apps --force mmu-tui mmu-cli    # expose aussi `mmu`
```

`pipx` monte l'outil dans son propre environnement isolé et pose ses commandes
sur le `PATH`, sans mêler ses dépendances aux vôtres. Ouvrez un
**nouveau** terminal après `ensurepath`.

### pip, dans un venv

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install mmu-cli        # la ligne de commande seule : `mmu`
pip install mmu-tui        # ... ou les deux : `mmu-tui` s'appuie sur `mmu-cli`
```

Si `Activate.ps1` est bloqué par la politique d'exécution :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

L'interface graphique Qt est **optionnelle** et ne s'installe qu'à la demande :

```powershell
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

    Mesuré sur Linux x86-64 ; l'ordre de grandeur vaut pour Windows. Ces
    chiffres sont ceux d'un `venv` ordinaire ; `pipx` en retire environ
    **28 Mo**, car il n'installe ni `pip` ni `setuptools` dans l'environnement
    de l'application.

    OpenCV et NumPy pèsent **76 des 89 Mo** téléchargés, et ne sont pas
    retirables : c'est le moteur de détection ArUco, de décodage QR et de
    traitement d'image du cœur.

!!! info "La roue OpenCV est la variante `-headless`"
    Elle ne lie aucune bibliothèque graphique du système, ce qui la rend
    importable partout — y compris sous WSL sans serveur X. La seule conséquence
    visible : la **lecture previz** ouvre sa fenêtre par `cv2.imshow`, que cette
    roue ne compile pas. L'outil le détecte et refuse en nommant le paquet, avec
    deux issues plutôt qu'un blocage — lire sans fenêtre, la mesure de cadence
    restant exacte, ou remplacer la roue par
    `pipx inject --force mmu-tui opencv-python`.

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

Pour qui refuse `irm … | iex` — c'est un refus légitime —, ou installe sur un
poste dont il n'a pas choisi la configuration. **L'ordre compte** : `pipx` a
besoin de Python, l'application a besoin de `pipx`, et l'état des lieux vient
avant tout le reste. Tout ce qui suit se lance dans **PowerShell**.

#### 1. Ce qui est déjà là

La plupart des postes portent déjà deux des quatre outils. Installer par-dessus
est la première façon de casser une installation qui marchait. Ce bloc se colle
tel quel et rend un verdict, sur une machine vierge comme sur une machine
complète :

<!-- BLOC-DE-DETECTION -->
```powershell
foreach ($outil in 'python', 'ffmpeg', 'ffprobe', 'pipx') {
    $trouve = Get-Command $outil -ErrorAction SilentlyContinue
    if (-not $trouve) { '{0,-8} ABSENT' -f $outil; continue }
    $drapeau = if ($outil -in 'ffmpeg', 'ffprobe') { '-version' } else { '--version' }
    $version = (& $outil $drapeau 2>&1 | Select-Object -First 1)
    '{0,-8} OK      {1}' -f $outil, $trouve.Source
    '         {0}' -f $version
}
```

Une ligne `ABSENT` désigne une étape ci-dessous à jouer ; une ligne `OK` la
dispense. **`ffmpeg` et `ffprobe` se lisent séparément**, et ce n'est pas un
détail : certains paquets minimalistes ne livrent que le premier, et la panne
survient alors des heures plus tard — à l'encodage, c'est-à-dire après
l'extraction, après l'impression, après le scan.

!!! warning "Un `python` trouvé n'est pas toujours un Python"
    Windows 10 et 11 posent un **alias d'exécution** `python.exe` qui n'ouvre
    que le Microsoft Store. `Get-Command` le trouve, et sa version reste vide
    ou renvoie au Store. Si c'est ce que vous lisez, traitez Python comme
    `ABSENT`. `py --version` est le verdict qui ne ment pas : le lanceur `py`
    n'existe que si un vrai Python est installé.

#### 2. Python, par la voie officielle du système

Python **3.11 ou plus**. Deux voies officielles, et une seule à choisir.

**Par winget**, le gestionnaire de paquets de Windows — c'est le paquet exact
que le script d'installation demande :

```powershell
winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements
```

**Par l'installeur de python.org**, si winget est indisponible — c'est le cas
sur Windows Server, les éditions LTSC et certains postes d'entreprise, et c'est
mot pour mot la voie que le script indique alors :
<https://www.python.org/downloads/windows/>. **Cochez « Add python.exe to
PATH »** à l'installation, sans quoi les étapes suivantes ne trouveront rien.

Ouvrez un **nouveau** terminal, puis vérifiez :

```powershell
py --version          # doit afficher 3.11 ou plus
```

#### 3. ffmpeg **et** ffprobe

**5.0 ou plus.** L'outil les appelle comme binaires du système ; il ne les
embarque pas. Le paquet est celui que le script demande :

```powershell
winget install --id Gyan.FFmpeg -e --source winget --accept-package-agreements
```

Sans winget, la voie que le script indique lui-même :
<https://www.gyan.dev/ffmpeg/builds/>, la construction **« essentials »**, dont
il faut ensuite **ajouter le dossier `bin\` au `PATH`**. Les binaires du projet
sont aussi sur <https://ffmpeg.org/download.html>.

Ouvrez un **nouveau** terminal — winget écrit le `PATH` dans le registre, pas
dans votre session —, puis :

```powershell
ffmpeg  -version | Select-Object -First 1   # doit afficher 5.0 ou plus
ffprobe -version | Select-Object -First 1   # ffprobe vient avec — VÉRIFIEZ-LE
```

!!! warning "Pourquoi `ffprobe` se vérifie séparément"
    `install.ps1` teste les **deux** (`Test-Commande "ffmpeg"` **et**
    `Test-Commande "ffprobe"`) parce qu'un paquet qui ne fournirait que le
    premier laisse l'outil échouer beaucoup plus loin, à la lecture des
    métadonnées du rush. Faites de même à la main.

#### 4. pipx, puis `pipx ensurepath`

`pipx` monte l'application dans son propre environnement isolé et expose ses
commandes sur le `PATH`, sans mêler ses dépendances aux vôtres. Ce sont les
deux lignes que le script joue :

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

`ensurepath` écrit dans le `PATH` **utilisateur**, via le registre. **Fermez et
rouvrez PowerShell** ensuite : une session déjà ouverte ne relit pas le
registre, et c'est la cause la plus fréquente d'un `pipx` « introuvable » juste
après son installation.

#### 5. L'application

Un seul paquet suffit : `mmu-tui` s'appuie sur `mmu-cli`.

```powershell
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

```powershell
pipx install mmu-cli
```

### Pour tous les utilisateurs de la machine { #tous-les-utilisateurs }

`pipx` est **par utilisateur** par construction. Sur Windows, une installation
partagée n'est pas un drapeau : c'est un parcours entièrement différent, qui
exige une **console PowerShell ouverte en administrateur**.

Dans cette console élevée :

```powershell
$env:PIPX_HOME    = 'C:\ProgramData\pipx'
$env:PIPX_BIN_DIR = 'C:\ProgramData\pipx\bin'
pipx install mmu-tui
pipx inject --include-apps --force mmu-tui mmu-cli
```

Puis le `PATH` **machine**, qui est celui que tous les comptes héritent — et
qui ne s'écrit que depuis une console élevée :

```powershell
$machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
[Environment]::SetEnvironmentVariable('Path', "$machine;C:\ProgramData\pipx\bin", 'Machine')
```

**Ce que ça ne dispense pas de faire, et c'est la moitié de l'information.**
« Tous les utilisateurs » ne supprime pas la corvée par compte, il la déplace :
**chaque compte** garde son propre `PATH` utilisateur, son propre profil
PowerShell et son propre raccourci du menu Démarrer — le script écrit toujours
ce raccourci dans **votre** menu, jamais dans celui de tous les comptes. Et
chaque session ouverte avant l'écriture du `PATH` machine devra être fermée et
rouverte.

!!! note "Il n'y a pas de drapeau pour ça"
    Le script d'installation **n'ajoute aucune option** « tous les
    utilisateurs », et c'est délibéré : l'écriture du `PATH` machine exige une
    console élevée, donc un parcours différent et non un drapeau de plus sur le
    chemin nominal. La voie ci-dessus est exacte et se lance à la main, en
    connaissance de cause.

### Les médias de test (facultatif)

Cette section suppose une **copie du dépôt** ; une installation par PyPI
n'en a pas besoin.

Le dépôt porte un rush réel et de vrais scans, qui permettent de jouer
[le parcours complet](../guide-utilisateur/workflow.md) sans avoir rien à
imprimer :

```powershell
git lfs install
git lfs pull
```

**Sans `git-lfs`, ces fichiers ne lèvent aucune erreur** : ils valent 133 octets,
et la panne apparaît beaucoup plus loin, sur un message de décodage
incompréhensible. Pour vérifier :

```powershell
git lfs ls-files -n | ForEach-Object {
  if ((Test-Path $_) -and (Get-Item $_).Length -lt 500) { "POINTEUR $_" }
}
```

Rien en sortie, tout est là.

---

## 3. Vérifier que ça marche

```powershell
mmu-tui --diagnostic-chemin
```

Elle affiche ce que la TUI voit de son environnement — chemins d'import, variables de la console, page de code, police, et **les glyphes à risque imprimés tels quels** — puis sort **sans
rien lancer**. C'est la commande à lire en premier quand l'affichage est
étrange.

**La ligne de commande répond aussi**

```bash
mmu --version
```

Après un `pip install` dans un venv, le paquet est en plus importable :
`python -m mixed_media_utility.cli --version` donne le même résultat.

Puis, pour de bon :

```powershell
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
environnement ne coûte que **28 Mo de plus** que la ligne de commande seule, et
le cœur n'y figure qu'**une fois**.

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
be installed »* et ne réenregistre pas les commandes. L'installation en une
commande le fait pour vous.

!!! warning "N'installez pas les deux par deux `pipx install` séparés"
    `pipx` isole chaque application dans son propre environnement : deux
    installations séparées posent **deux exemplaires du cœur** sur le disque —
    **702 Mo** au lieu de 333, mesuré le 2026-09-07. Le téléchargement, lui,
    n'est pas doublé : `pip` sert le second depuis son cache.

!!! note "Depuis un dépôt cloné"
    `scripts\install-mmu.ps1` ajoute le `bin/` du dépôt au `PATH` et donne, lui aussi,
    une commande `mmu` — celle du dépôt, pas celle du paquet installé. Les deux
    peuvent coexister, et c'est alors l'ordre du `PATH` qui décide laquelle
    répond. Pour travailler sur le code c'est ce qu'on veut ; pour utiliser
    l'outil, préférez le paquet.

---

## 5. Problèmes fréquents

### Des caractères s'affichent en carrés ou en points d'interrogation

**C'est le problème le plus courant sous Windows, et il ne vient ni du terminal
ni du shell.** Le glyphe est dessiné par l'*hôte* — `conhost.exe`, Windows
Terminal, le terminal de VS Code — avec la police qu'il a chargée. Changer de
shell (`cmd` → PowerShell) n'y peut donc rien.

La TUI le devine et bascule d'elle-même en ASCII quand elle ne reconnaît aucun
hôte capable. Les deux échappatoires :

```powershell
mmu-tui --ascii    # forcer le repli ASCII
mmu-tui --utf8     # le refuser, si la détection se trompe
```

Pour trancher en une seconde plutôt que d'essayer : `mmu-tui --diagnostic-chemin`
imprime les caractères à risque tels quels, avec leur repli en regard. Ceux qui
tombent sont visibles à l'œil.

Deux remèdes durables : utiliser **Windows Terminal** plutôt que la console
historique, ou choisir dans les propriétés de la console une police à couverture
large (Cascadia Mono, DejaVu Sans Mono).

### `mmu-tui : terme non reconnu`

Le venv n'est pas activé, ou le dossier `Scripts` de Python n'est pas dans le
`PATH`. Fermez et rouvrez le terminal après toute installation. Repli qui marche
toujours : `python -m mixed_media_utility.tui`.

### `Binaire ffmpeg introuvable dans le PATH`

Ajoutez le dossier `bin` de votre build ffmpeg au `PATH`, puis ouvrez un nouveau
terminal. `winget install Gyan.FFmpeg` le fait pour vous.

### `Cette version de ffmpeg ne connait pas l'option '-fps_mode'`

Votre ffmpeg est antérieur à 5.0. Prenez une build récente.

### Un script `.ps1` refuse de se lancer

C'est la politique d'exécution par défaut de Windows, qui bloque tout script
local non signé. `-ExecutionPolicy Bypass` ne s'applique qu'au processus lancé :
pas de droits administrateur, aucun changement permanent, aucun effet sur les
autres terminaux.

### Pas de couleur

`mmu-tui` respecte la convention `NO_COLOR` : posez la variable, ou passez
`--sans-couleur`.

---

<a id="mettre-a-jour"></a>

## 6. Mettre à jour

Depuis un clone du dépôt :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -MettreAJour
```

Sans le script sous la main : `irm … | iex` **ne sait pas passer
d'argument** — `iex` reçoit le texte et applique les défauts. La forme qui en
passe est celle-ci, et c'est la seule :

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/GanTiz/mixed_media_utility/main/scripts/install.ps1))) -MettreAJour
```

Sans drapeau, sur une machine où l'outil est déjà posé, le script **pose la
question** plutôt que de décider : le mettre à jour, tout réinstaller de zéro,
ou ne rien changer et sortir.

**Ce que la mise à jour touche, et c'est tout :** la distribution `pipx` et le
`mmu-cli` greffé dedans. La greffe n'est pas un détail — sans
`--include-injected`, `pipx` mettrait à jour `mmu-tui` et laisserait `mmu` à
son ancienne version. La voie manuelle équivalente :

```powershell
pipx upgrade mmu-tui --include-injected
```

… ou, si vous n'avez posé que la ligne de commande :

```powershell
pipx upgrade mmu-cli
```

**Ce qu'elle ne touche PAS : ni Python, ni ffmpeg, ni `pipx`.** Ce sont des
dépendances du système, et elles se mettent à jour par le système —
`winget upgrade --id Gyan.FFmpeg -e`, `winget upgrade --id Python.Python.3.12
-e`, ou la voie par laquelle ils sont arrivés chez vous. Ce n'est pas un
détail d'implémentation : « mise à jour » sans précision laisse croire que
**tout** est mis à jour, et l'on conclut alors à un bogue de l'outil le jour
où un `ffmpeg` de 2019 refuse l'option `-fps_mode` — c'est exactement le
symptôme décrit en *Problèmes fréquents* ci-dessus, et sa cause est un
`ffmpeg` que la mise à jour de l'application n'a jamais promis de toucher.

---

<a id="desinstaller"></a>

## 7. Désinstaller

Depuis un clone du dépôt :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Desinstaller
```

… ou, sans le script sous la main — la forme qui passe un argument à travers
`irm` :

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/GanTiz/mixed_media_utility/main/scripts/install.ps1))) -Desinstaller
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

`-NonInteractif` prend ce défaut : une machine muette — un script, une image,
une intégration continue, une entrée redirigée — ne retire **jamais** plus que
l'application. Partent alors les quatre distributions `pipx` (`mmu-tui`,
`mmu-cli`, et leurs versions de bac à sable `mmu-tui-test` et `mmu-cli-test`),
l'entrée `…\bin` que `pipx` a ajoutée à votre `PATH` **utilisateur** — l'ancien
`PATH` est d'abord copié en entier dans
`%USERPROFILE%\mmu-path-utilisateur-avant-desinstallation.txt`, parce qu'éditer
le `PATH` de quelqu'un sans filet est le genre de geste qu'on ne rattrape
pas —, le raccourci du menu Démarrer, et le reçu décrit ci-dessous.

Ni Python, ni ffmpeg, ni `pipx` ne sont touchés.

### L'issue 2 — l'application **et ce que ce script a posé**

Elle ne devine rien, et surtout elle ne balaie pas votre machine : elle relit
un **reçu**, écrit au moment de la pose.

```powershell
Get-Content "$env:LOCALAPPDATA\mmu\pose-par-installeur.txt"
```

Une ligne par objet, trois champs séparés par une tabulation : la nature, le
chemin absolu, la date. **Sur Windows, il n'y enregistre que `pipx`**, et
seulement si c'est ce script qui l'a posé, par `pip --user`. Python et
`ffmpeg` y sont absents *par construction* : ils arrivent par **winget**, donc
ils appartiennent à winget — exactement comme ce qu'`apt` pose appartient à
`apt`. C'est l'issue 3 qui les couvre, et le reçu ne double pas winget. Trois
conséquences, et elles comptent :

* **un binaire présent mais absent du reçu n'est jamais touché.** Un `ffmpeg`
  venu de winget appartient à winget : le retirer par un `Remove-Item`
  laisserait winget avec un paquet fantôme ;
* **un chemin du reçu qui a disparu est dit, puis sauté** — quelqu'un l'a déjà
  retiré à la main, et le lui dire vaut mieux que faire comme si le reçu avait
  raison ;
* **`pipx` n'est jamais retiré par un `Remove-Item`.** Le script repasse par
  la voie qui l'a posé, `pip uninstall`, et il **nomme d'abord les autres
  applications que `pipx` gère**, qui perdraient leurs commandes.
  `pipx uninstall-all` les reprend proprement avant.

**Si le reçu manque** — installation antérieure à ce mécanisme, fichier
effacé —, l'issue 2 **se rabat sur l'issue 1 en le disant**, et vous renvoie à
l'issue 3 pour le reste. Jamais un blocage sec.

**Python n'est jamais retiré, même s'il figure au reçu.** C'est une frontière
du produit et non une prudence — l'issue 3 dit pourquoi.

**Le reçu se retire lui-même**, par l'issue 1 comme par l'issue 2.

### L'issue 3 — elle affiche, et elle ne fait pas

Elle sort **avant le premier retrait** : après elle, rien n'a bougé — ni les
distributions, ni le `PATH`, ni le raccourci, ni le reçu. Elle affiche les
voies officielles de retrait de `ffmpeg`, de `pipx` et de Python :

```
    Pour RETIRER ffmpeg, la voie la plus officielle disponible :
      winget uninstall --id Gyan.FFmpeg -e

    Pour RETIRER pipx, la voie la plus officielle disponible :
      pipx uninstall-all      (les autres applications posees par pipx)
      python -m pip uninstall pipx
```

**Pourquoi elle affiche au lieu de faire.** Ces trois-là n'appartiennent pas à
l'outil. L'interpréteur Python du système n'a pas été posé par cette
installation, et le retirer casse ce qui en dépend ; un `ffmpeg` venu de
winget appartient à winget, et le retirer autrement que par lui le laisse dans
un état faux. Le script ne donne donc **aucune commande de retrait pour
Python** : il renvoie à <https://www.python.org/downloads/> et vous laisse
décider.

### À la main, si vous n'avez plus le script

```powershell
pipx uninstall mmu-tui   # l'interface en terminal
pipx uninstall mmu-cli   # la ligne de commande
# ou, dans un venv : pip uninstall mmu-tui mmu-cli
Remove-Item (Join-Path ([Environment]::GetFolderPath('Programs')) 'mmu-tui.lnk')
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\mmu"
```

Puis retirez l'entrée `…\bin` du `PATH` utilisateur (Paramètres → Système →
Informations système → Paramètres système avancés → Variables
d'environnement).

Vos projets sont des dossiers ordinaires : **rien ne les touche**. Hors
projet, l'outil écrit la liste des projets récents,
`%APPDATA%\mixed_media_utility\recents-v1.json`, et — si vous l'avez accepté —
le raccourci du menu Démarrer nommé juste au-dessus.
