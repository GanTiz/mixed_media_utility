# L'explorateur de dossiers — proposition d'ergonomie

*Écrit le 2026-08-29, à la demande d'Egan, **avant** la revue de la vague 2.*

*Maquettes : `maquettes/X1-*` à `maquettes/X7-*`, produites par
`_gen_explorateur.py` sur la même grille 80 × 24 que les 40 autres.*

---

## 1. Ce qui ne va pas dans la complétion `Tab`

La demande d'Egan, verbatim : « On ne connaît pas forcément les chemins de
fichiers, et si les sous-dossiers sont nombreux on ne peut pas tous les voir
dans la disposition actuelle. »

Les deux défauts sont réels et se mesurent sur le code livré
(`tui/projets.py::completer`, `tui/ecran_projet.py`) :

1. **la complétion suppose qu'on sait déjà.** `completer()` ne propose rien tant
   qu'aucun préfixe n'est saisi : sur un champ vide, l'écran ne montre aucun
   dossier. C'est un outil de *raccourci* pour quelqu'un qui connaît le chemin,
   pas un outil de *découverte* ;
2. **la zone de propositions est une ligne.** Elle rend les candidats côte à
   côte sur une seule ligne (`E0-2`), donc trois noms de dossier longs la
   saturent. Il n'y a ni défilement, ni compteur, ni moyen de voir le
   vingt-septième.

Un troisième défaut, non signalé mais du même ordre : `completer()` complète
**jusqu'au plus long préfixe commun**, ce qui veut dire que sur des dossiers
nommés `01_reperages/`, `02_tournage/`, `03_tournage/`, `Tab` ne complète
**rien** et ne dit pas pourquoi.

---

## 2. Ce que l'explorateur remplace — cinq sites, un seul composant

| Site | Écran | Ce qu'il demande |
|---|---|---|
| `E0-2` | Ouvrir un projet | un **dossier** |
| `E0-4` | Créer un projet — champ « Dossier parent » | un **dossier** |
| `E3-1` | Scan — source à détecter | un **dossier, un fichier ou un PDF** (`EPIC11-ARB-26`) |
| `E3-5` | Scan — « autre fichier… » (profil de calibration) | un **fichier** `.json` |
| `E2-1` | Extraction — « Le désigner à la main » (relink) | un **fichier** vidéo |

**Un seul composant, deux réglages** : ce qu'il liste (dossiers seuls, ou
dossiers + fichiers filtrés) et ce que valide le bouton (le dossier courant, ou
l'entrée surlignée). Écrire cinq explorateurs serait la faute que
`DESIGN.md` §7 interdit — « quatre motifs de composant, et rien d'autre ».
L'explorateur devient le **cinquième motif**, et c'est un choix assumé : il
remplace le champ-chemin du motif « formulaire », il ne s'y ajoute pas.

---

## 3. La grammaire de l'écran — trois zones, à hauteur fixe

```
      Dossier              D:\HOKO\Documents\mmu          <- 1. barre d'adresse
   ──────────────────────────────────────────────────
      archives/                          0 sous-dossier
    ▸ projects/                         6 sous-dossiers   <- 2. la liste
      …                                     1-8 sur 27       (9 lignes, fixes)
   ──────────────────────────────────────────────────
      Valider ce dossier                                  <- 3. les deux actions
      Dossier parent
```

**La hauteur des trois zones ne change jamais.** Les deux actions sont
toujours sur les deux dernières lignes de la zone centrale, que le dossier
courant en contienne zéro ou deux cents. Une cible qui se déplace quand la
liste change de longueur est une cible qu'on rate — c'est la même raison qui a
fait figer la grille au `DESIGN.md` §1.

**Les deux « boutons » ne sont pas des boutons, ce sont deux lignes de la même
liste.** Le curseur `▸` circule dans un seul cycle : les entrées, puis
« Valider ce dossier », puis « Dossier parent », puis retour en haut. On garde
ainsi la règle d'`EPIC11-ARB-45` — « le curseur **est** la sélection, et
`Entrée` retient et suit la ligne sous le curseur » — sans inventer un
mécanisme de focus supplémentaire. La ligne du curseur est rendue en gras et
en couleur d'accentuation (`EPIC11-ARB-47`), ce qu'un `.txt` ne peut pas
montrer.

**Le `…` dit qu'il y a du contenu au-delà du bord**, en haut comme en bas
(demande d'Egan). Il porte en plus, à droite, la position mesurée dans la
liste : `1-8 sur 27`. Le `…` seul dit « il y en a d'autres » ; il ne dit pas
« il y en a dix-neuf ». `DESIGN.md` §7.1 exigeait déjà ce compteur sur les
listes qui défilent ; les deux se cumulent sur la même ligne plutôt que d'en
coûter deux.

---

## 4. Le clavier

| Touche | Effet |
|---|---|
| `↑` `↓` | déplacer le curseur — un seul cycle : entrées, puis les deux actions |
| `⏎` | **agit sur la ligne sous le curseur** : entrer dans le dossier, ou déclencher l'action |
| `→` | entrer dans le dossier surligné (raccourci direct) |
| `←` | remonter d'un cran (raccourci direct de « Dossier parent ») |
| une lettre | sauter au premier nom qui commence par elle |
| `Tab` | basculer entre la liste et la barre d'adresse |
| `Ctrl+V` | coller un chemin dans la barre d'adresse |
| `⏎` (barre d'adresse) | valider le chemin saisi |
| `Échap` | **quitter l'explorateur** — remonter d'un palier, jamais d'un dossier |
| `F1` `q` | aide, quitter (universels, `DESIGN.md` §4) |

**Trois points méritent d'être discutés, parce qu'ils touchent à des règles
déjà posées** — ils sont repris en questions au §8 :

* **`Échap` ne remonte pas d'un dossier.** `EPIC11-ARB-2` lui donne un sens
  unique dans toute la TUI : remonter d'un **palier**. Lui donner ici le sens
  de « dossier parent » ferait deux `Échap` différents selon l'écran, et c'est
  exactement la dérive qu'`EPIC11-ARB-45` vient de corriger sur `Espace`. Le
  parent est donc sur `←`, plus la ligne d'action ;
* **`Tab` perd son sens de « compléter »** — il n'y a plus rien à compléter — et
  reprend son sens partout ailleurs dans la TUI : passer d'un champ à l'autre,
  ici de la barre d'adresse à la liste ;
* **aucune lettre n'est un raccourci d'action.** Les lettres sont prises par le
  saut alphabétique, qui est le seul geste qui rende une liste de 200 dossiers
  praticable. C'est pourquoi « Valider » n'a pas de touche unique et se
  déclenche par le curseur, ou par `⏎` depuis la barre d'adresse.

---

## 5. La barre d'adresse — frappe et collage

Maquette `X5`.

* elle est **éditable** : `Tab` y amène le curseur, le caret `█` marque le
  point d'insertion (glyphe déjà à la table du `DESIGN.md` §6) ;
* **`Ctrl+V` colle un chemin.** Techniquement, on branche l'événement de
  collage du terminal (*bracketed paste*, qui est ce que `Cmd+V` et `Ctrl+V`
  produisent dans les terminaux courants) **et** la touche `ctrl+v` elle-même,
  parce que la console Windows historique livre la seconde sans le premier ;
* **la liste suit la frappe, en direct.** Dès que le chemin saisi désigne un
  dossier qui existe, la liste dessous montre son contenu. Coller un chemin
  puis `Tab` `↓` continue donc l'exploration à partir de là — coller puis `⏎`
  valide directement ;
* **un chemin trop long est abrégé au milieu**, avec `…`, début et dernier
  segment conservés — `jetons.abreger_chemin()` existe déjà et fait exactement
  cela. **Sauf pendant l'édition** : un champ en cours de frappe défile
  horizontalement et montre sa fin, parce qu'abréger ce qu'on est en train de
  taper afficherait autre chose que ce qu'on tape.

---

## 6. Le point de départ

Le dossier depuis lequel la commande a été lancée (`Path.cwd()`), comme demandé.

Deux précisions qui ne vont pas de soi :

* si le `cwd` n'est plus lisible (volume débranché, dossier supprimé pendant la
  session), l'explorateur ouvre sur le dossier personnel de l'utilisateur et le
  dit en ligne d'état. Il ne refuse pas de s'ouvrir ;
* sur `E0-2`, la liste des **récents** reste le premier écran, et l'explorateur
  est ce qu'on atteint par `Tab` — l'ordre actuel est conservé. Un opérateur qui
  rouvre son projet de la veille ne traverse pas un explorateur pour cela.

---

## 7. Les cas limites, et ce qu'ils rendent

| Cas | Ce que l'écran fait |
|---|---|
| dossier vide | la zone de liste porte « aucun sous-dossier », « Valider ce dossier » reste actionnable — un dossier vide est un point de départ, pas une anomalie (`E0-3`) |
| dossier illisible (droits, volume lent) | listé, marqué `✕ illisible`, non entrable ; le motif passe en ligne d'état. Il n'est **pas** masqué : un dossier absent de la liste ferait croire qu'il n'existe pas |
| racine de volume (`D:\`) | « Dossier parent » devient « Volumes » et rend la liste des volumes (`C:`, `D:`, `E:`). Sous Unix, le parent de `/` est `/` et la ligne devient inactive |
| dossiers cachés (`.git`, `$RECYCLE.BIN`) | **question `QE4`** ci-dessous |
| chemin collé inexistant | la liste se vide et dit « ce dossier n'existe pas » ; le champ **ne passe pas en refus** — c'est un état de frappe, pas une erreur (règle déjà posée en `E0-2`) |
| 200 sous-dossiers | défilement + `…` + compteur ; le comptage de la colonne de droite n'est fait que pour les **lignes visibles** |
| volume lent / réseau | la colonne de droite rend `·` en attendant, jamais `0` — même règle que `projets.Compteurs` |
| lien symbolique circulaire | suivi une fois, jamais résolu récursivement ; la profondeur n'est pas parcourue |

---

## 8. Ce qui reste à trancher

Réponse par numéro et lettre (« 1a, 2b… »).

### `QE1` — `Entrée` fait deux choses. Est-ce acceptable ?

Sur une ligne de dossier, `⏎` **entre** ; sur la ligne « Valider », il
**valide** ; dans la barre d'adresse, il **valide**. La règle est uniforme
(« `⏎` agit sur la ligne sous le curseur ») mais le mot change.

* **a. (recommandé)** on garde. La règle uniforme est plus facile à apprendre
  que trois touches, et la ligne de raccourcis affiche le verbe **de la ligne
  courante** — elle dit `⏎ entrer` sur un dossier, `⏎ valider` sur l'action
  (c'est la différence entre `X1` et `X6` dans les maquettes) ;
* **b.** `⏎` n'entre jamais et ne fait que valider ; on entre uniquement par
  `→`. Plus strict, mais contredit le réflexe de tout explorateur ;
* **c.** ta proposition d'origine : `Tab` entre aussi dans le dossier. Je la
  déconseille — `Tab` est le passage d'un champ à l'autre partout ailleurs dans
  la TUI, et lui donner un second sens ici rendrait la barre d'adresse
  inatteignable au clavier.

### `QE2` — la colonne de droite de la liste

Elle porte aujourd'hui `6 sous-dossiers`, et `● projet · 3 rushes · 5 lots`
quand le dossier porte un `project.json` (maquette `X2`). C'est ce qui permet
de **voir** ses projets en naviguant, au lieu de les deviner.

* **a. (recommandé)** on garde les deux, comptés seulement pour les lignes
  visibles ;
* **b.** seulement le marqueur `● projet`, pas le nombre de sous-dossiers (un
  `scandir` de moins par ligne visible) ;
* **c.** rien à droite.

### `QE3` — le compteur sur la ligne `…`

* **a. (recommandé)** `…` **et** `1-8 sur 27`, comme aux maquettes ;
* **b.** `…` seul, comme tu l'as décrit ;
* **c.** `…` seul dans la liste, et le compte complet en ligne d'état.

### `QE4` — les dossiers cachés

`.git`, `.venv`, `$RECYCLE.BIN`, `System Volume Information`… Ils encombrent, et
`$RECYCLE.BIN` apparaît à la racine de chaque volume Windows (maquette `X7`).

* **a. (recommandé)** masqués par défaut, `Ctrl+H` les montre, et la ligne
  d'état dit combien sont masqués (« 3 dossiers cachés — Ctrl+H »). Rien n'est
  invisible **en silence** ;
* **b.** toujours affichés ;
* **c.** toujours masqués, sans bascule.

### `QE5` — la mémoire entre deux ouvertures

* **a. (recommandé)** le `cwd` au lancement de la commande, puis **le dernier
  dossier validé** pour les explorateurs suivants **de la même session**. Sur un
  parcours Scan → Pdf, on ne retraverse pas trois fois la même arborescence ;
* **b.** le `cwd` à chaque fois, sans mémoire ;
* **c.** mémoire persistante entre deux lancements (fichier de réglages, à côté
  des récents).

### `QE6` — la souris

`EPIC11-ARB-11` met la souris **hors v1**, tout en la prévoyant, et pose que
« aucun geste ne lui est réservé ». Un explorateur est l'écran où elle sert le
plus (clic pour entrer, molette pour défiler), et `textual` la fournit sans
coût. Répondre `a` **amende** `EPIC11-ARB-11` sur ce seul écran ; le plancher
qu'il pose — rien qui ne soit atteignable au clavier — reste tenu dans les deux
cas.

* **a.** on la câble tout de suite sur ce seul écran : clic = déplacer le
  curseur, double-clic = entrer, molette = défiler ;
* **b. (recommandé)** clavier seul, comme le reste de l'epic — on ne rouvre pas
  un arbitrage tranché pour un confort, et la souris arrivera d'un bloc.

---

## 9. Ce que ça coûte, et comment ça entre dans le sprint

**Nouveau module** : `tui/explorateur.py` — le modèle pur (dossier courant,
entrées, curseur, fenêtre de défilement, filtre) et le widget. Le modèle pur est
testable sans terminal, comme `projets.py` l'est déjà.

**Modules touchés** : `tui/ecran_projet.py` (les deux champs de `E0-2` et
`E0-4`), `tui/projets.py` (`completer()` **disparaît** ; `resoudre()` reste et
sert plus qu'avant).

**Ce que ça retire** : `projets.completer()` et ses tests, la zone de
propositions en ligne, et le verbe « compléter » des trois lignes de
raccourcis. Une AC de frontière négative le mesurera — « un `grep` de
`completer` dans `src/mixed_media_utility/tui/` rend zéro ».

**Où ça entre dans BMad.** C'est un changement produit en cours de sprint sur
des écrans déjà développés : le geste du dépôt est `bmad-correct-course`, qui
produit un *sprint change proposal*, puis une story `11.x` écrite par
`bmad-create-story`, avec son entrée dans `epics.md` **et** dans
`sprint-status.yaml` dans le même mouvement. Les décisions prises ici prendront
des numéros `EPIC11-ARB-<k>` **réservés d'abord** sous `arbitrages_reserves:`,
comme la consigne du 2026-08-27 l'exige.

**Une conséquence sur la revue de la vague 2** : `E0-2` et `E0-4` changent de
forme. Revoir la vague 2 avant ce changement ferait auditer un écran qui n'existe
plus. C'est pourquoi tu as demandé l'implémentation d'abord, et c'est le bon
ordre.
