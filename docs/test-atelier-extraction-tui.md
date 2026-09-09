# Tester l'atelier Extraction en terminal (TUI)

Etat au **2026-08-30**, commit `0fde4ee` sur `oc/epic-11-TUI`. Stories **11.4**
(atelier Extraction) et **11.4b** (socle de coeur du scan) developpees ; la
**revue en trois couches n'est pas encore passee**.

Ce document dit ce que tu peux **taper aujourd'hui**, ce qui est **visible mais
inerte**, et ce qui **n'existe pas encore**. Tout ce qui suit a ete verifie en
lancant reellement les commandes, pas deduit des fiches — c'est cette
verification qui a trouve, en l'ecrivant, que `bin/mmu-tui` n'etait pas
executable.

> **La CLI reste le livrable complet.** `bin/mmu` fait toute la chaine. La TUI
> ne couvre aujourd'hui que le palier Projet, le menu des ateliers et
> **l'atelier Extraction de bout en bout**. Le Scan, les Exports et le Montage
> n'y sont pas.

---

## 1. Avant de commencer : deux prerequis qui font perdre une heure

### Git LFS

`tests/TEST_FILE.mp4` est en **Git LFS**, et c'est le rush que toute la recette
utilise. Sans `git-lfs`, il vaut **132 octets** au lieu de 2 881 478, et la
previz comme l'extraction echouent sur `moov atom not found` — un message qui
ne nomme ni LFS ni le fichier.

```
apt-get install -y git-lfs
git lfs pull --include="tests/TEST_FILE.mp4"
```

Verification, en une commande :

```
ls -l tests/TEST_FILE.mp4        # doit faire ~2,9 Mo, pas 132 octets
```

Le hook de session le fait desormais tout seul, et la demo **te previent** si
le fichier est un pointeur plutot que de te laisser buter dessus.

### ffmpeg

Necessaire pour la previz, pour l'extraction, et pour que le bac a sable grave
les videos de la section B.5. Sans lui, la demo le **dit** au lancement et la
recherche de relink ne pourra refuser que sur `aucun-candidat`.

```
ffmpeg -version | head -1
```

---

## 2. Lancer le produit

```
./bin/mmu-tui
```

Depuis la racine du depot. Rien a installer : comme la CLI, la TUI tourne par
`PYTHONPATH` pointant sur `src/`, et ce chemin se calcule **depuis la position
du script** — donc `bin/` peut etre mis sur le `PATH` et appele d'ou que ce
soit.

Windows :

```
bin\mmu-tui.cmd
```

Trois options, et elles se combinent :

| option | ce qu'elle fait |
| --- | --- |
| `--ascii` | remplace les glyphes UTF-8 par leur repli ASCII, pour une console dont la police n'a pas la table |
| `--sans-couleur` | n'emet aucune couleur ; l'information reste portee par les glyphes (`NO_COLOR` la pose d'office) |
| `--diagnostic-chemin` | affiche les chemins d'import vus par la TUI, puis sort |

**Joue au moins une fois en `--ascii`.** Un repli ASCII peut **allonger** une
ligne, et c'est le regime ou la grille casse en premier — trois defauts de
cette vague n'etaient visibles que la.

```
./bin/mmu-tui --diagnostic-chemin     # la mesure du lancement, avant tout dessin
```

---

## 3. Le chemin recommande : le bac a sable

`./bin/mmu-tui` s'ouvre sur **tes** projets recents. Pour juger l'atelier il
faut un projet avec un rush **present** et un rush **introuvable**, ce qu'un
projet reel n'a pas forcement sous la main. Le bac a sable en fabrique deux :

```
cd _bmad-output/planning-artifacts/ux-designs/ux-tui-2026-08-27
PYTHONPATH=../../../../src python3 demo_vague_3.py
```

**Ce bac n'assemble rien** : il appelle `construire_l_application()`, le meme
point d'entree que `./bin/mmu-tui`. Si un ecran manque ici, il manque aussi
dans le produit. C'est deliberе — la demo de la vague precedente assemblait la
chaine a la main, ce qui a masque pendant **deux vagues** que `mmu-tui`
n'ouvrait que des ecrans temoins.

Il imprime avant de dessiner :

```
Bac a sable jetable : /tmp/demo_mmu_vague_3
  projet_demo            3 rushes, dont rush_hiver INTROUVABLE
  projet_deux_absents    3 rushes, dont DEUX introuvables

  Retrouver rush_hiver (`r`), deux dossiers a taper :
    un candidat, la recherche REUSSIT   /tmp/demo_mmu_vague_3/retrouvailles-1-candidat
    deux candidats, elle REFUSE         /tmp/demo_mmu_vague_3/retrouvailles-2-candidats
```

Le bac est **jetable et recree a chaque lancement**, rien n'est ecrit hors de
lui, et la liste des recents qu'il montre est la sienne — jamais les reglages
de ta machine. Les memes options `--ascii` et `--sans-couleur` marchent, plus
`--bac <chemin>` pour le poser ailleurs.

---

## 4. Le parcours, ecran par ecran

Les touches communes a tout ecran : `Echap` remonte, `q` quitte, `F1` ouvre
l'aide — qui **annonce honnetement qu'elle n'existe pas encore**, plutot que de
ne rien faire.

### 4.1 Choisir le projet, puis l'atelier

`⏎` sur `projet_demo` dans les recents, puis `⏎` sur **Extraction** (en tete du
menu). L'atelier s'ouvre **directement** sur la liste des rushes : il n'a
qu'une entree, un menu intermediaire serait un ecran a franchir pour rien.

### 4.2 `E2-1` — la liste des rushes

Ce que tu dois voir : la question en tete, la liste, `Ajouter un rush` et sa
phrase, un filet, puis le bloc `r` / `d`. Chaque ligne porte le nom du rush,
sa cadence, ses dimensions, sa duree et sa presence.

**A verifier en priorite, ce sont les points corriges aujourd'hui :**

* la **duree est entiere**, jamais `0:…` ni `...` — y compris en `--ascii`, qui
  etait le pire des deux regimes ;
* les noms longs sont **elides au milieu**, jamais par la fin : deux lots du
  meme rush ne se distinguent que par leur suffixe ;
* `rush_hiver` porte `✕ absent` et **reste selectionnable** — c'est de la qu'on
  le repare.

### 4.3 Relink : `r` chercher, `d` designer

Sur `rush_hiver` :

* **`d`** ouvre l'explorateur pour designer un fichier a la main ;
* **`r`** demande un dossier et **cherche** l'unique fichier satisfaisant les
  **trois criteres d'identite** (nom, cardinal de frames, timecode de depart).

Les deux dossiers imprimes par la demo font jouer les deux issues :

| dossier | ce qui arrive |
| --- | --- |
| `retrouvailles-1-candidat` | la recherche **reussit** ; `rush_hiver` passe a `● lie` et sa duree apparait |
| `retrouvailles-2-candidats` | refus **`candidats-multiples`**, les deux chemins nommes |

Chacun contient en plus un leurre au bon nom mais au mauvais timecode, et un
fichier illisible : les deux mecanismes d'ecartement du coeur sont exerces pour
de vrai. **Relance le script entre les deux essais** — le premier ecrit le
manifeste.

> **Une fois relie, n'extrais pas depuis `rush_hiver`.** Il est declare en
> 4096x2160 : un lot a 12 im/s y pese **plus de deux gigaoctets** de TIFF. Le
> panneau chiffre te le dira avant d'ecrire, mais autant le savoir. Les
> sections d'extraction se jouent sur `rush_present`.

Il y a **onze** codes de refus du coeur, plus deux locaux. Chacun s'affiche
avec son code sur sa propre ligne et le message du coeur **verbatim**.

### 4.4 `E2-2` — les cadences

Cocher au moins une cadence, jamais zero. Les cadences remarquables viennent du
coeur ; on peut en ajouter une **decimale** librement.

Point a regarder : **sans affichage** (machine sans serveur X), l'ecran refuse
la previz **avant** de lancer quoi que ce soit et **retire** la promesse au lieu
de la degrader. La ligne `Borne de sortie` doit rester visible — elle
disparaissait en silence il y a quelques heures.

### 4.5 `E2-2b` / `E2-2c` — previz et jugement

**La previz exige un serveur graphique** : elle ouvre une vraie fenetre. Sur une
machine sans affichage, l'ecran precedent l'a deja refusee (4.4) et tu ne
passeras pas ici. C'est le seul point du parcours qui n'a **pas** pu etre
verifie dans le conteneur de developpement.

La previz **n'ecrit rien** : c'est une lecture. `o` la rouvre. L'ecran de choix
ne montre que les cadences reellement previsualisees.

### 4.6 `E2-3` — le panneau chiffre, obligatoire avant toute ecriture

Il porte ce qui sera produit, en quelle quantite, et ce que ca coute.

* `Tab` entre dans l'edition des noms de lot et en ressort ;
* **taper une lettre dans un nom ecrit la lettre** — aucune lettre n'est un
  raccourci dans un champ de saisie. Essaie `r`, `d`, `o` : ils doivent
  s'inscrire ;
* `Ctrl+R` remet le nom propose ;
* un nom trop long refuse avec **le motif dans le corps** et **la mesure en
  ligne d'etat** (`49 caracteres sur 48 admis`).

Les trois etats de cet ecran (`E2-3`, edition, refus) doivent **differer
visiblement** : titre de cartouche et ligne de raccourcis compris.

### 4.7 `E2-4` / `E2-5` — l'execution et le resultat

`Tab` deplie le **journal** — il porte les lignes reelles du coeur (qualification
de la source, frames retenues, manifeste mis a jour). `Echap` ouvre
l'interruption, il ne remonte pas. La fin d'une execution ramene au **menu des
ateliers du projet ouvert**, jamais a l'ecran projet.

---

## 5. La preuve : la TUI ecrit-elle la meme chose que `mmu extract` ?

C'est la question qui compte, et elle est mesuree des deux cotes.

**A la main**, apres une extraction dans le bac a sable :

```
PYTHONPATH=src python3 -m mixed_media_utility.cli extract \
    --projet /tmp/demo_mmu_vague_3/projet_demo \
    --rush rush_present --fps 12.5 --yes
```

puis compare les deux dossiers de frames :

```
find /tmp/demo_mmu_vague_3/projet_demo/frames -name '*.tiff' \
  | sort | xargs sha256sum
```

**Automatiquement**, et c'est le plus simple : **a la fermeture de la TUI**, la
demo rejoue `mmu extract` lot par lot sur les arguments **exacts** du plan que
tu viens d'executer, bornes comprises, dans un miroir du projet. Elle imprime
les commandes en toutes lettres, le compte de TIFF identiques octet a octet et
**le premier chemin qui differe** s'il y en a un, l'ensemble des chemins
divergents du manifeste confronte a l'ensemble **attendu**, et les deux codes
retour. En cas d'ecart : bloc encadre de `!` et code de sortie non nul — elle
crie plutot que d'annoncer « identique » a tort.

Si tu n'as rien extrait, elle le dit (« Aucun lot ecrit dans cette session »)
au lieu de comparer du vide. Et elle ne compare que **la session en cours** :
le bac etant recree a chaque lancement, extraire, quitter, relancer et
comparer ne marche pas.

**Par les bancs**, si tu veux la mesure complete :

```
PYTHONPATH=src QT_QPA_PLATFORM=offscreen xvfb-run -a \
  python3 -m pytest tests/unit/tui/test_identite_extraction.py -q
```

Il fait tourner **les deux chemins reels** sur le meme rush et compare tout
l'arbre `frames/`. La seule divergence admise du manifeste est
`lots[].confirmation.mode`, qui vaut `non_interactif` cote TUI puisqu'elle porte
son propre panneau de confirmation.

---

## 6. La suite complete

```
PYTHONPATH=src QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m pytest tests/unit -q
```

Etat mesure au commit `9260402` : **8 178 passed, 13 skipped, 0 failed**
(~15 min).

---

## 7. Ce qui n'existe pas encore, et qu'il ne faut pas chercher

| ce que tu verras | etat |
| --- | --- |
| `F1 aide` | la touche **repond** et nomme l'absence ; le manuel reste a ecrire |
| ateliers Scan, Exports, Montage | ecran « pas encore », qui nomme l'echeance |
| nom de lot **edite** | il s'edite a l'ecran mais **n'atteint pas le coeur** — identifiant et dossier ne peuvent pas encore diverger (`EPIC11-ARB-82`) |
| cadence `source / 3` | rend `rush_01_8p333333333333334` : la convention `_25s3` d'`EPIC11-ARB-62` **n'est implementee nulle part** |
| liste des rushes > 20 | elle **defile** depuis aujourd'hui ; c'etait un debordement muet avant |

---

## 8. Si quelque chose cloche

Les captures de reference des douze ecrans, dans **les deux regimes**, sont
dans `_bmad-output/planning-artifacts/ux-designs/ux-tui-2026-08-27/captures-reelles/`
(`11-E2-1-*` a `24-E2-5-*`). Elles sont prises **au clavier sur le vrai
produit**, pas montees a la main : ce que tu vois doit y correspondre.

Pour les rejouer apres un changement :

```
cd _bmad-output/planning-artifacts/ux-designs/ux-tui-2026-08-27/captures-reelles
PYTHONPATH=../../../../../src xvfb-run -a python3 capturer.py
```

Le plan de test detaille, section par section avec les touches exactes, est
dans `_bmad-output/implementation-artifacts/plan-de-test-manuel-vague-3.md`.
