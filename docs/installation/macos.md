# Installation sur macOS

---

## 1. Ce qu'il faut avoir avant

| outil | version | pourquoi |
|---|---|---|
| **Python** | 3.11 ou plus | exigé par le paquet (`requires-python = ">=3.11"`) |
| **ffmpeg** *(avec `ffprobe`)* | 5.0 ou plus | l'outil l'appelle comme **binaire du système** ; il ne l'embarque pas |
| **git** | quelconque | *facultatif* — seulement pour récupérer les sources |
| **git-lfs** | quelconque | *facultatif* — seulement pour les médias de test du dépôt |

Le plus simple passe par [Homebrew](https://brew.sh) :

```bash
brew install python@3.12 ffmpeg git git-lfs
```

!!! warning "Sur un Mac Intel, cette ligne COMPILE — et ça se compte en heures"
    Mesuré sur l'API de Homebrew le 8 septembre 2026 : `python@3.12`,
    `openssl@3` et `mpdecimal` n'ont **aucune** bouteille (binaire précompilé)
    macOS Intel ; `ffmpeg` n'en a qu'une, pour Sonoma. Sur un Mac Intel — quelle
    que soit la version de macOS, y compris Sequoia — Homebrew n'a donc
    pratiquement plus rien à servir dans cet arbre et **compile tout depuis les
    sources**. Ce n'est ni un défaut de votre installation, ni un Homebrew
    périmé, et la tendance ne s'inversera pas : `arm64_tahoe` (macOS 26) existe
    déjà sans `tahoe` correspondant.

    Le même constat vaut pour **macOS 12 et en dessous**, sur les deux
    architectures.

    Dans ces deux cas, préférez [la ligne d'installation en une
    commande](#repli-precompile) : elle détecte la situation, vous
    prévient, et **pose les binaires précompilés elle-même** plutôt que de vous
    renvoyer au terminal.

Vérifiez avant d'aller plus loin :

```bash
python3 --version     # doit afficher 3.11 ou plus
ffmpeg -version       # doit afficher 5.0 ou plus
ffprobe -version
```

!!! info "Pourquoi ffmpeg 5.0 et pas moins"
    L'extraction emploie `-fps_mode passthrough`, sans quoi ffmpeg re-cadence la
    sortie et le nombre d'images écrites ne correspond plus à la sélection.
    Cette option n'existe qu'à partir de ffmpeg 5.0. En dessous, l'outil ne
    devine rien : il refuse en nommant la version exigée.

!!! tip "Python de Homebrew plutôt que celui du système"
    Le Python livré avec macOS est réservé au système et ses permissions
    d'installation sont contraignantes. Préférez celui de Homebrew —
    `/opt/homebrew/bin/python3` sur Apple Silicon, `/usr/local/bin/python3` sur
    Intel — ou un installeur de [python.org](https://python.org/downloads/macos/).

---

## 2. Installer

### En une commande (recommandé)

```bash
curl -fsSL https://raw.githubusercontent.com/GanTiz/mixed_media_utility/main/scripts/install.sh | bash
```

Le script **pose ses questions au clavier** : ce que vous voulez installer
(la ligne de commande seule, ou avec l'interface en terminal), quoi faire si
`ffmpeg` manque, où ajouter les commandes, et s'il faut vérifier
l'installation à la fin. Chaque question a une réponse par défaut,
qu'`Entrée` valide — il n'y a aucune syntaxe à connaître. Il installe au
minimum **`mmu`**, la ligne de commande.

Sans terminal — dans un script, une image, une intégration continue — il
ne bloque pas : il prend les réponses par défaut et le dit.

#### Quand Homebrew compilerait : le script pose le binaire lui-même { #repli-precompile }

Sur un **Mac Intel**, ou sur **macOS 12 et en dessous**, poser `python@3.12` ou
`ffmpeg` par Homebrew passerait par une compilation depuis les sources. Le
script le détecte, nomme la cause — « votre Mac est un Intel » et « votre macOS
est ancien » ne se réparent pas de la même façon — et vous laisse **trois**
issues :

| issue | ce qu'elle coûte |
|---|---|
| compiler avec Homebrew | de l'ordre de l'heure sur les gros paquets, mais c'est la voie Homebrew |
| **poser le binaire précompilé** *(défaut)* | quelques dizaines de secondes ; aucun mot de passe pour `ffmpeg` |
| ne rien poser | rien — le script vous donne la commande officielle et continue |

Ce que le script fait quand vous le laissez faire :

* **`ffmpeg` et `ffprobe`** — il télécharge les deux archives, **vérifie leur
  condensat SHA-256** contre une valeur épinglée dans le script, les dézippe, et
  les dépose dans **le répertoire binaire que `pipx` expose réellement** —
  demandé à `pipx` (`pipx environment --value PIPX_BIN_DIR`), à défaut lu
  dans la variable `PIPX_BIN_DIR` que `pipx` honore, et en dernier recours
  `~/.local/bin`, qui est son défaut. Un chemin **relatif** est refusé : il
  ferait écrire dans le répertoire courant de qui a lancé la commande, et
  mettrait ensuite une entrée relative dans le `PATH`. Aucun
  `sudo`, aucune écriture hors de votre compte. Il retire ensuite l'attribut de
  quarantaine si le système en a posé un, puis **lance le binaire** pour
  vérifier qu'il démarre — un attribut retiré ne prouve pas qu'un binaire
  fonctionne ;
* **Python** — il télécharge l'installeur officiel de python.org, vérifie son
  condensat, puis **vous prévient que le geste demande votre mot de passe
  administrateur** avant de lancer quoi que ce soit. `installer -pkg … -target /`
  est la seule voie officielle sur macOS et elle exige `sudo` ; le défaut de
  cette question-là est donc de **refuser**, et un refus vous rend la commande.

**Tout échec de ce repli vous donne la commande de secours la plus officielle**
de la dépendance concernée : URL morte, réseau coupé, condensat qui ne
correspond pas, archive illisible, refus de mot de passe, binaire qui ne démarre
pas. Jamais un blocage sec, jamais un échec muet — et un condensat qui ne
correspond pas fait **abandonner** le repli, il ne fait jamais poser le binaire
« quand même ».

**Et « abandonner » veut dire ne rien laisser derrière.** Un `ffmpeg` posé sans
son `ffprobe`, ou un binaire que le script vient de déclarer « ne démarre pas »,
est **retiré**. Ce n'est pas de la propreté : `~/.local/bin` est en tête de
votre `PATH`, donc un orphelin qui resterait là **masquerait** le
`brew install ffmpeg` que la commande de secours vient de vous donner. Le script
ne retire jamais un binaire qui était là avant lui.

**Un binaire qui ne rend pas la main est traité comme un binaire en panne.** Le
lancement de vérification est plafonné à 30 secondes, et les téléchargements à
15 minutes. Le cas n'est pas théorique : le premier lancement d'un binaire non
notarisé fait partir Gatekeeper au réseau, et un pare-feu qui *jette* les
paquets au lieu de les refuser suspend l'appel indéfiniment.

!!! note "D'où viennent ces binaires, et pourquoi un condensat épinglé"
    Les binaires `ffmpeg`/`ffprobe` viennent d'[evermeet.cx](https://evermeet.cx/ffmpeg/),
    le build macOS de référence de la communauté FFmpeg — ancien, très utilisé,
    signé GPG. **Ce n'est pas le projet FFmpeg lui-même**, et c'est dit plutôt
    que tu. L'installeur Python vient de python.org, qui l'est.

    Aucune des deux sources ne **sert** de condensat SHA-256 : l'API d'evermeet
    rend `url`, `size` et `sig`, et le `.sha256` du paquet python.org répond
    404. Les trois condensats ont donc été relevés une fois, archives en main,
    et vivent **en constantes dans `scripts/install.sh`**. C'est ce qui les rend
    forts : une source compromise ne peut pas changer à la fois l'archive et une
    valeur qui vit dans notre dépôt.

    La voie GPG a été écartée : elle exigerait `gpg` sur la machine, qu'un Mac
    vierge n'a pas — ce qui rouvrirait le problème que ce repli ferme.

!!! info "Mettre ces versions à jour (pour qui maintient le dépôt)"
    Trois URL et trois condensats vieilliront. **Deux fichiers les portent, et
    il faut les reprendre ensemble** :

    1. `scripts/install.sh`, en tête du bloc « repli précompilé » — les six
       constantes `FFMPEG_VERSION_EPINGLEE`, `FFMPEG_ZIP_SHA256`,
       `FFPROBE_ZIP_SHA256`, `PYTHON_PKG_VERSION_EPINGLEE`, `PYTHON_PKG_SHA256`
       et les URL qui les emploient ;
    2. `tests/unit/test_installateur_interactif.py`, dans le **seul** test qui
       recopie les trois condensats — `test_les_TROIS_condensats_epingles_sont_ceux_qui_ont_ete_MESURES`.
       Il les recopie **exprès** : tout le reste du banc *lit* la constante dans
       `install.sh`, si bien qu'y mettre trois zéros laisserait le lot vert.
       C'est ce test-là, et lui seul, qui dit qu'une valeur a été relevée
       archive en main plutôt que de mémoire.

    Le geste : relever la version courante
    (`https://evermeet.cx/ffmpeg/info/ffmpeg/release` pour ffmpeg, la page des
    téléchargements macOS de python.org pour Python), télécharger, calculer
    `shasum -a 256`, puis remplacer **la version et le condensat ensemble**,
    dans les deux fichiers.

    !!! warning "Cette page a menti jusqu'au 8 septembre 2026, et ça se mesure"
        Elle affirmait que les constantes vivaient « **uniquement** » dans
        `install.sh` et nulle part ailleurs. La couche 3 de la revue a suivi
        cette procédure **à la lettre** et a obtenu **17 tests rouges** que la
        procédure n'annonçait pas. Le second fichier était omis. C'est
        exactement ce qu'un engagement de maintenance écrit est censé éviter.

    **Ce qui rougit quand une version épinglée disparaît de la source**, et
    c'est une réponse qui a changé le 8 septembre 2026 : la jambe `macos-15-intel`
    de la CI (`EPIC11-ARB-272`). Elle joue une installation réelle, donc elle
    emprunte réellement ce repli, et une étape exige que `ffmpeg` et `ffprobe`
    **démarrent** après coup — quelle que soit la voie par laquelle ils sont
    arrivés. Une archive injoignable ou un condensat changé à la source la fait
    **rougir**, ce qui était le but : jusque-là, rien dans le dépôt ne l'aurait
    dit.

    Aucune garde n'interroge le réseau **en dehors de cette jambe-là** : sur un
    poste de développement, la suite reste verte, et c'est voulu — ce serait une
    panne de plus sur le chemin d'installation. Chez l'utilisateur, le repli
    dégrade proprement : il nomme l'échec du téléchargement et donne
    `brew install ffmpeg`. La mesure du 8 septembre 2026 dit par ailleurs que
    les deux sources gardent leur historique (ffmpeg 6.1.1 et Python 3.11.0
    répondent encore `200`) : une URL épinglée ne pourrit pas, elle vieillit.

### pipx, à la main

Si `pipx` manque, Homebrew le pose — et `ensurepath` met ses applications sur
votre `PATH` :

```bash
brew install pipx
pipx ensurepath
```

Puis l'application elle-même :

```bash
pipx install mmu-cli                                  # la ligne de commande seule
```

... ou les deux, sans rien installer en double :

```bash
pipx install mmu-tui                                  # pose `mmu-tui`
pipx inject --include-apps --force mmu-tui mmu-cli    # expose aussi `mmu`
```

`pipx` monte l'outil dans son propre environnement isolé et pose ses commandes
sur le `PATH`, sans mêler ses dépendances aux vôtres.

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

!!! info "La roue OpenCV est la variante `-headless`"
    Elle ne lie aucune bibliothèque graphique du système, ce qui la rend
    importable partout. La seule conséquence visible : la **lecture previz**
    ouvre sa fenêtre par `cv2.imshow`, que cette roue ne compile pas. L'outil le
    détecte et refuse en nommant le paquet, avec deux issues plutôt qu'un
    blocage — lire sans fenêtre, la mesure de cadence restant exacte, ou
    remplacer la roue par `pipx inject --force mmu-tui opencv-python`.

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

Pour qui refuse `curl … | bash` — c'est un refus légitime —, ou installe sur un
Mac dont il n'a pas choisi la configuration. **L'ordre compte** : `pipx` a
besoin de Python, l'application a besoin de `pipx`, et l'état des lieux vient
avant tout le reste.

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

Python **3.11 ou plus**. Deux voies officielles, et une seule à choisir.

**Par Homebrew**, si vous l'avez déjà — c'est le paquet que le script
d'installation demande lui-même :

```sh
brew install python@3.12
```

Si Homebrew manque, sa commande d'installation officielle est affichée en
première page de <https://brew.sh> — c'est celle-là, et pas une variante, que
le script d'installation vous donne quand il ne trouve pas Homebrew. Elle
demande le mot de passe administrateur.

!!! note "Pourquoi cette page ne recopie pas la commande de Homebrew"
    Une frontière de ce dépôt interdit à la documentation publiée de porter une
    URL de téléchargement brute vers un dépôt qui n'est pas le sien — elle
    existe pour attraper un renommage de `scripts/install.sh` qui laisserait
    une commande grammaticalement juste rendre un 404. La recopier ici la
    figerait de surcroît : Homebrew la fait évoluer, `brew.sh` non.

**Par python.org**, si vous préférez ne rien installer d'autre : l'installeur
officiel de <https://www.python.org/downloads/macos/>.

Dans les deux cas, **pas le Python livré avec macOS** : il est réservé au
système et ses permissions d'installation sont contraignantes. Vérifiez avant
de continuer :

```sh
python3 --version     # doit afficher 3.11 ou plus
```

!!! warning "Sur un Mac Intel, `brew install python@3.12` COMPILE"
    Mesuré sur l'API de Homebrew le 8 septembre 2026 : `python@3.12`,
    `openssl@3` et `mpdecimal` n'ont aucune bouteille macOS Intel. Comptez des
    heures. C'est le régime où [la ligne d'installation en une
    commande](#repli-precompile) vaut mieux que la voie manuelle : elle pose le
    binaire précompilé officiel elle-même.

#### 3. ffmpeg **et** ffprobe

**5.0 ou plus.** L'outil les appelle comme binaires du système ; il ne les
embarque pas. Ce sont exactement les deux issues que le script donne en secours
quand son repli échoue — un lecteur de cette page et un utilisateur dont le
repli a échoué reçoivent la même chose :

```sh
brew install ffmpeg

ffmpeg  -version | head -n 1  # doit afficher 5.0 ou plus
ffprobe -version | head -n 1  # ffprobe vient avec le paquet — VÉRIFIEZ-LE
```

Sans Homebrew, ou pour éviter la compilation sur un Mac Intel, les binaires du
projet : <https://ffmpeg.org/download.html>. Les archives macOS y sont celles
d'evermeet, qui ciblent macOS 10.15 et au-delà — ce sont les mêmes que le repli
précompilé du script télécharge.

!!! warning "Pourquoi `ffprobe` se vérifie séparément"
    `install.ps1` teste les **deux** (`Test-Commande "ffmpeg"` **et**
    `Test-Commande "ffprobe"`) parce qu'un paquet qui ne fournirait que le
    premier laisse l'outil échouer beaucoup plus loin, à la lecture des
    métadonnées du rush. Faites de même à la main.

#### 4. pipx, puis `pipx ensurepath`

`pipx` monte l'application dans son propre environnement isolé et expose ses
commandes sur le `PATH`, sans mêler ses dépendances aux vôtres.

```sh
brew install pipx
```

Sans Homebrew, le repli officiel — c'est celui que le script emprunte lui
aussi :

```sh
python3 -m pip install --user pipx
```

Puis, dans les deux cas :

```sh
pipx ensurepath
```

`ensurepath` ajoute le répertoire binaire de pipx à votre profil (`~/.zprofile`
sous zsh, qui est le shell par défaut depuis Catalina). **Ouvrez un nouveau
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
propre raccourci. Un compte dont le `PATH` ne contient pas `/usr/local/bin` ne
verra rien, et aucun `pipx ensurepath` lancé en `root` ne le lui ajoutera.

!!! note "Il n'y a pas de drapeau pour ça"
    Le script d'installation **n'ajoute aucune option** « tous les
    utilisateurs », et c'est délibéré : dans le one-liner, ces deux lignes
    deviennent un `curl … | bash` qui réclame un mot de passe administrateur
    sur le chemin nominal. La voie ci-dessus est exacte et se lance à la main,
    en connaissance de cause.

### macOS 12 sur Intel

C'est le plancher visé par la conception. Une réserve à connaître : la dernière
roue `macosx_12_0_x86_64` d'OpenCV est la **4.10.0.84**. Le paquet accepte
explicitement cette version — son plancher déclaré est `>=4.10` —, donc `pip` la
retiendra d'elle-même sur ces machines. Aucun geste à faire, mais ne forcez pas
une version plus récente : elle n'a pas de roue pour vous.

**Ce que ce paragraphe ne dit pas, et qui compte davantage sur ces machines :**
les roues Python ne sont pas ce qui coince ici — elles existent pour les deux
architectures. C'est le **chemin d'installation** qui coince, `brew install`
compilant tout depuis les sources faute de bouteilles Intel. La réponse est
[le repli précompilé](#repli-precompile)
de la ligne d'installation en une commande, et elle vaut pour **tous** les Mac
Intel — pas seulement pour macOS 12.

Sur Apple Silicon et sur macOS 13 et au-delà, `pip` prend la version courante.

### Le périmètre du support macOS : ce qui est éprouvé, et ce qui est raisonné { #perimetre-du-support }

**macOS 12 est supporté, et aucun runner ne le joue.** Les deux moitiés de
cette phrase comptent, et la seconde se dit plutôt qu'elle ne se tait.

GitHub ne propose plus de runner `macos-12`. La matrice d'intégration continue
de ce dépôt offre `macos-15-intel` (Intel) et `macos-14` (Apple Silicon), et c'est
tout ce qui existe. **Aucune installation réelle ne peut donc être jouée sur
macOS 12** : le support y est **raisonné, pas éprouvé**.

Ce qui le fonde, et qui n'est pas rien — trois choses mesurées :

| ce qui est mesuré | où |
|---|---|
| **les branches du script**, avec un `sw_vers` factice rendant `12` | `tests/unit/test_installateur_interactif.py`, machine macOS majeur `12`, arm64 — c'est le régime « Homebrew ne publie plus de bouteilles », celui qui déclenche le repli précompilé |
| **le plancher des roues** : `opencv-python-headless 4.10.0.84` est la dernière version portant une roue `macosx_12_0_x86_64` | le paquet déclare `>=4.10`, donc `pip` la retient d'elle-même sur ces machines. Un plancher au-dessus sortirait macOS 12 Intel du support |
| **le binaire précompilé** que pose le repli | les archives d'evermeet ciblent macOS 10.15 et au-delà |

Ce qui ne l'est pas : l'installation de bout en bout sur une machine réelle en
macOS 12.

**Pourquoi ne pas simplement retirer la promesse.** Parce qu'elle est
probablement vraie, que la retirer priverait des machines qui marchent, et
qu'une promesse bornée vaut mieux qu'un silence : si vous êtes en macOS 12 et
que l'installation échoue, **remontez-le** — c'est exactement ce qui
transformerait ce raisonnement en mesure. Un silence, lui, vous ferait croire
que vous êtes seul.

### Les médias de test (facultatif)

Cette section suppose une **copie du dépôt** ; une installation par PyPI
n'en a pas besoin.

Le dépôt porte un rush réel et de vrais scans, qui permettent de jouer
[le parcours complet](../guide-utilisateur/workflow.md) sans avoir rien à
imprimer :

```bash
git lfs install
git lfs pull
```

**Sans `git-lfs`, ces fichiers ne lèvent aucune erreur** : ils valent 133 octets
et la panne apparaît beaucoup plus loin, sur un message de décodage
incompréhensible. Pour vérifier :

```bash
git lfs ls-files -n | while read f; do
  [ -f "$f" ] && [ "$(stat -f%z "$f")" -lt 500 ] && echo "POINTEUR $f"
done
```

Rien en sortie, tout est là.

---

## 3. Vérifier que ça marche

```bash
mmu-tui --diagnostic-chemin
```

Elle affiche ce que la TUI voit de son environnement puis sort **sans
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

### `zsh: command not found: mmu-tui`

Le venv n'est pas activé (`source .venv/bin/activate`), ou vous avez installé
avec `pip install --user` et le dossier des scripts n'est pas dans le `PATH` :

```bash
echo 'export PATH="$(python3 -m site --user-base)/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Repli qui marche toujours : `python -m mixed_media_utility.tui`.

### `Binaire ffmpeg introuvable dans le PATH`

`brew install ffmpeg`, puis ouvrez un nouveau terminal. Sur Apple Silicon,
vérifiez que `/opt/homebrew/bin` est bien dans votre `PATH`.

### `Cette version de ffmpeg ne connait pas l'option '-fps_mode'`

Votre ffmpeg est antérieur à 5.0 — `brew upgrade ffmpeg`.

### Glyphes qui s'affichent en carrés

Peu probable : les polices de console d'Apple (SF Mono, Menlo) portent les
caractères employés. Si cela arrive quand même, `mmu-tui --ascii` bascule sur un
repli intégral, et `mmu-tui --diagnostic-chemin` imprime les glyphes à risque
tels quels pour que vous voyiez lesquels tombent.

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
`brew upgrade ffmpeg`, ou la voie par laquelle `ffmpeg` est arrivé chez vous.
Ce n'est pas un détail d'implémentation : « mise à jour » sans précision
laisse croire que **tout** est mis à jour, et l'on conclut alors à un bogue de
l'outil le jour où un `ffmpeg` de 2019 refuse l'option `-fps_mode` — c'est
exactement le symptôme décrit en *Problèmes fréquents* ci-dessus, et sa cause
est un `ffmpeg` que la mise à jour de l'application n'a jamais promis de
toucher.

**Le binaire posé par le repli précompilé ne se met pas à jour tout seul non
plus.** Si le script a déposé `ffmpeg` et `ffprobe` lui-même (voir *Quand
Homebrew compilerait* plus haut), ils restent à la version téléchargée ce
jour-là : les remplacer, c'est relancer le script, ou poser `ffmpeg` par
Homebrew et retirer les deux binaires du reçu.

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
la ligne que `pipx` a ajoutée au profil de votre shell — `~/.zshrc` sous
zsh, qui est le défaut de macOS ; `~/.bashrc` sous bash. Une copie du fichier
est gardée en `.mmu-sauvegarde` avant d'y toucher. Et le reçu décrit
ci-dessous.

Ni Python, ni ffmpeg, ni `pipx` ne sont touchés.

### L'issue 2 — l'application **et ce que ce script a posé**

Elle ne devine rien, et surtout elle ne balaie pas votre machine : elle relit
un **reçu**, écrit au moment de la pose.

```bash
cat "${XDG_STATE_HOME:-$HOME/.local/state}/mmu/pose-par-installeur.txt"
```

Une ligne par objet, trois champs séparés par une tabulation : la nature, le
chemin absolu, la date. Ce qu'il enregistre ici : les `ffmpeg` et `ffprobe`
du repli précompilé, quand Homebrew aurait compilé ou qu'il était absent ;
`pipx` si c'est ce script qui l'a posé ; et, sur un Mac où le script a dû
poser Python par l'installeur officiel python.org,
`/Library/Frameworks/Python.framework` — **noté pour que vous sachiez où, pas
pour être retiré**. Trois conséquences, et elles comptent :

* **un binaire présent mais absent du reçu n'est jamais touché.** Un `ffmpeg`
  venu de Homebrew appartient à Homebrew : le retirer par un `rm` laisserait
  `brew` avec une formule fantôme ;
* **un chemin du reçu qui a disparu est dit, puis sauté** — quelqu'un l'a déjà
  retiré à la main, et le lui dire vaut mieux que faire comme si le reçu avait
  raison ;
* **`pipx` n'est jamais retiré par un `rm`.** Le script repasse par la voie
  qui l'a posé — la formule Homebrew, ou `pip --user` —, et il **nomme d'abord
  les autres applications que `pipx` gère**, qui perdraient leurs commandes.
  `pipx uninstall-all` les reprend proprement avant.

**Si le reçu manque** — installation antérieure à ce mécanisme, fichier
effacé —, l'issue 2 **se rabat sur l'issue 1 en le disant**, et vous renvoie à
l'issue 3 pour le reste. Jamais un blocage sec.

**Python n'est jamais retiré, même s'il figure au reçu.** C'est une frontière
du produit et non une prudence — l'issue 3 dit pourquoi.

**Le reçu se retire lui-même**, par l'issue 1 comme par l'issue 2.

### L'issue 3 — elle affiche, et elle ne fait pas

Elle sort **avant le premier retrait** : après elle, rien n'a bougé — ni les
distributions, ni le profil, ni le reçu. Elle affiche les voies officielles de
retrait de `ffmpeg`, de `pipx` et de Python, pour la voie par laquelle chacun
est arrivé sur cette machine :

```
    Pour RETIRER ffmpeg, la voie la plus officielle disponible :
      brew uninstall ffmpeg

    Pour RETIRER pipx, la voie la plus officielle disponible :
      pipx uninstall-all      (les autres applications posees par pipx)
      brew uninstall pipx
```

**Pourquoi elle affiche au lieu de faire.** Ces trois-là n'appartiennent pas à
l'outil. `/usr/bin/python3` appartient aux outils d'Apple, et l'interpréteur
du système n'a pas été posé par cette installation — le retirer casse ce qui
en dépend. De même, un `ffmpeg` venu de Homebrew appartient à Homebrew ; le
retirer autrement que par `brew` le laisse dans un état faux. Le script ne
donne donc **aucune commande de retrait pour Python** : il renvoie à
<https://www.python.org/downloads/> et vous laisse décider.

### À la main, si vous n'avez plus le script

```bash
pipx uninstall mmu-tui   # l'interface en terminal
pipx uninstall mmu-cli   # la ligne de commande
# ou, dans un venv : pip uninstall mmu-tui mmu-cli
rm -rf "${XDG_STATE_HOME:-$HOME/.local/state}/mmu"
```

Puis retirez du profil de votre shell — `~/.zshrc` sous zsh, `~/.bashrc`
sous bash — la ligne de `PATH` qu'a ajoutée `pipx ensurepath` : elle est
précédée d'un commentaire `# Created by pipx on …` qui la nomme.

Vos projets sont des dossiers ordinaires : **rien ne les touche**. Le seul
fichier écrit hors projet est la liste des projets récents,
`~/.config/mixed_media_utility/recents-v1.json`.
