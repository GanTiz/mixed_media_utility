---
status: draft
date: 2026-08-27
surface: TUI
sources:
  - _bmad-output/planning-artifacts/tui-vision.md
  - _bmad-output/implementation-artifacts/decisions-2026-08-27-epic-11-tui.md
  - _bmad-output/planning-artifacts/ux-designs/ux-mixed_media_utility-2026-08-16/DESIGN.md
colors:
  state-complete: "#4EC57A"
  state-substitute: "#F5A623"
  state-absent: "#EE878A"
  accent: "#8FAEF7"
  data: "#E8E8E8"
  muted: "#9A9A9A"
  surface: "#1C1C1C"
grid:
  floor: "80x24"
  rows-header: 2
  rows-central: 17
  rows-status: 1
  rows-footer: 1
---

# TUI — Grammaire visuelle

**Ceci est le DESIGN.md de la TUI.** Il est au TUI ce que le
`DESIGN.md` du 2026-08-16 est à la GUI, en beaucoup plus court : une TUI n'a ni
élévation, ni rayon d'angle, ni échelle typographique. Ce qu'elle a, et qui doit
être tenu de la même main sur les quatre ateliers, c'est **une grille, un jeu de
glyphes, six couleurs et quatre motifs de composant**.

Il **hérite** des jetons de couleur de la GUI plutôt que d'en inventer : les
mêmes trois couleurs d'état disent les mêmes trois choses sur les deux surfaces.
Un opérateur qui passe de la GUI à la TUI ne réapprend pas le code couleur.

**Cette grammaire est la loi ; une maquette qui la contredit est fausse, pas
l'inverse.**

---

## 1. La grille — 80 × 24, et pourquoi

Le plancher est **80 colonnes × 24 lignes** (`Q7`, recommandation `a`). C'est le
terminal hérité d'une session SSH sur matériel ancien, et « déploiement serveur /
SSH sans X11 » plus « opérateur terrain sur machine légère » sont les deux
raisons d'être de cette TUI. Tout écran doit être **lisible et franchissable à
cette taille**.

Répartition verticale, invariante sur **tous** les écrans :

```
ligne  1  ┌───────────────────────────────────────────────────────────────────┐
ligne  2  │ BANDEAU DE CONTEXTE                                               │
ligne  3  ├───────────────────────────────────────────────────────────────────┤
lignes 4-20   ZONE CENTRALE (17 lignes)
ligne 21  ├───────────────────────────────────────────────────────────────────┤
ligne 22  │ LIGNE D'ÉTAT                                                      │
ligne 23  │ RACCOURCIS CONTEXTUELS                                            │
ligne 24  └───────────────────────────────────────────────────────────────────┘
```

**Au-delà de 80 colonnes**, la place gagnée sert à **allonger les lignes de
liste** (un chemin tronqué se déplie, une colonne de chiffres se décolle du
libellé). Elle ne sert **jamais** à ajouter une colonne : une seconde colonne
ferait réapparaître le panneau permanent qu'`EPIC11-ARB-2` vient d'écarter, et
créerait une seconde mise en page à tester.

**Au-delà de 24 lignes**, la place gagnée va **entièrement à la zone centrale** :
plus de lignes de liste visibles, plus de lignes de journal. Le bandeau, l'état
et les raccourcis gardent leur hauteur.

**En dessous du plancher**, la TUI affiche une seule phrase — la taille courante,
la taille exigée — et ne dessine rien d'autre. Elle ne tronque pas.

---

## 2. Le bandeau de contexte (ligne 2)

Il répond en permanence à « où suis-je, et sur quoi ». Trois segments à gauche
séparés par ` · `, une **donnée de contexte** alignée à droite :

```
│ mmu · projet_demo · Extraction                        rush_01 · 25 fps · 4:12 │
```

* segment 1, `mmu` — toujours présent, en `muted`. C'est l'ancre.
* segment 2, **le projet ouvert** — en `data`. Absent (et remplacé par
  `— aucun projet —` en `muted`) tant qu'aucun projet n'est ouvert.
* segment 3, **le palier ou l'atelier courant** — en `accent`. C'est le seul
  segment qui bouge quand on navigue.
* à droite, **l'objet sur lequel on travaille** et ses caractéristiques
  chiffrées, en `data`. Il se remplit au fur et à mesure du parcours : vide au
  premier écran d'un atelier, complet au dernier.

Le bandeau **n'affiche jamais de raccourci** ni d'état d'exécution : ceux-là ont
leurs lignes.

---

## 3. La ligne d'état (ligne 22)

Une ligne, un message, et **elle est vide quand il n'y a rien à dire** — elle ne
se remplit pas de bavardage pour occuper la place.

Elle porte, par ordre de priorité (un seul à la fois) :

| Contenu | Préfixe | Couleur |
|---|---|---|
| Refus / erreur | `✕ ` | `state-absent` |
| Avertissement, réserve, valeur inhabituelle | `▲ ` | `state-substitute` |
| Progression en cours (barre + temps restant) | *(la barre elle-même)* | `accent` |
| Succès d'une écriture | `● ` | `state-complete` |
| Aide brève sur le champ en cours | *(aucun)* | `muted` |

**Le temps restant n'y apparaît que s'il existe.** `EPIC7-ARB-67` interdit de
rendre un temps tant qu'aucune mesure réelle n'a été faite : tant que
`EstimateurTempsRestant` rend `None`, la ligne d'état affiche la barre et le
compte de frames, et **rien** à la place du temps — jamais `0:00`, jamais `--:--`
présenté comme une durée.

---

**La ligne d'état porte une MESURE de l'écran courant** (`EPIC11-ARB-56`,
2026-08-29, sur une remarque explicitement générale d'Egan : « tu es trop bavard
dans les bandeaux en bas […] Sois sobre »). Elle ne porte

* **aucune touche** — une touche va à la ligne des raccourcis ;
* **aucun conseil d'usage** (« tapez une lettre pour sauter ») ;
* **aucun motif de conception** (« un chemin en cours de frappe n'est pas une
  erreur »).

Ce qui reste : ce que l'écran a compté, et le motif d'un refus quand il y en a
un.

---

## 4. La ligne de raccourcis (ligne 23)

**Contextuelle** : elle ne montre que ce qui marche sur l'écran courant. Ordre
constant, de gauche à droite, les entrées absentes laissant leur place aux
suivantes :

```
⏎ valider   ↑↓ naviguer   Tab champ suivant   Échap retour   F1 aide   q quitter
```

Trois raccourcis sont **présents sur tout écran sans exception**, et toujours à
la même place relative :

* `Échap` — **remonter d'un palier** (`EPIC11-ARB-2`). Depuis un formulaire :
  abandonne le formulaire sans rien écrire. Depuis un atelier : retour au menu
  des ateliers. Depuis le menu des ateliers : retour à l'écran projet.
* `F1` — l'aide (`EPIC11-ARB-14`) : contextuelle si le focus est sur un champ, le
  manuel des raccourcis sinon.
* `q` — quitter la TUI. Depuis un écran d'exécution, `q` **demande confirmation**
  au lieu de quitter.

**La ligne de raccourcis n'est pas le manuel.** Elle porte le contextuel ; la
liste complète vit dans le manuel `F1` — c'est la lettre d'`EPIC11-ARB-14`.

---

## 5. Couleurs — six jetons, hérités de la GUI

| Jeton | Valeur | Emploi en TUI |
|---|---|---|
| `state-complete` | `#4EC57A` | lot complet, écriture réussie, case cochée validée |
| `state-substitute` | `#F5A623` | mire de remplacement, avertissement, valeur inhabituelle mais acceptée |
| `state-absent` | `#EE878A` | frame absente, page manquante, refus, champ invalide |
| `accent` | `#8FAEF7` | curseur de sélection, atelier courant au bandeau, barre de progression |
| `data` | `#E8E8E8` | toute **donnée** : chemin, cadence, timecode, taille, nom produit |
| `muted` | `#9A9A9A` | libellés, ancre `mmu`, aide brève, raccourcis |

**Deux règles non négociables**, reprises de l'`Accessibility Floor` de la GUI :

1. **la couleur ne porte jamais seule une information.** Chaque état a **aussi**
   son glyphe (§6). Un terminal monochrome, un opérateur daltonien et une capture
   en noir et blanc doivent lire la même chose. C'est *plus* contraignant en TUI
   qu'en GUI : on ne maîtrise pas la palette du terminal de l'opérateur ;
2. **aucune couleur littérale hors du module de jetons** — même AC de frontière
   que la GUI (story 7.0, grep de frontière). Le module de jetons de la TUI
   *importe* ceux de la GUI plutôt que de les recopier, sans quoi les deux
   surfaces divergeront au premier ajustement de contraste.

**Le fond n'est pas imposé, et le contraste n'est donc garanti que sur fond
sombre** (`EPIC11-ARB-43`, tranché le 2026-08-28). La TUI n'impose pas
`surface` : elle hérite du fond du terminal. Les six couleurs de premier plan
sont **réglées pour un fond sombre** — mesurées en WCAG 2.1 contre
`surface-canvas` `#141414`, elles vont de 6,55:1 (`muted`) à 15,04:1 (`data`),
toutes au-dessus du seuil de 4,5:1.

**Sur un fond clair, aucune des six ne tient ce seuil** (2,81:1 au mieux, et
1,23:1 pour `data`) : la palette de la GUI est une palette de thème sombre, et
aucune valeur de cette palette — chromies pleines comprises — ne tient les deux
fonds à la fois. La version antérieure de ce paragraphe affirmait le contraire ;
c'était faux, et un test (`test_aucun_jeton_ne_tient_4_5_sur_un_fond_clair`)
fige désormais la mesure pour que la phrase ne puisse pas redevenir fausse en
silence.

Ce que cela coûte est borné par la **règle 1 ci-dessus, qui n'est pas
négociable** : la couleur ne porte jamais seule une information. Sur un
terminal clair, les couleurs d'état sont pâles, mais chaque état porte aussi
son glyphe, et trois états rendus sans aucune couleur donnent trois chaînes
différentes — en UTF-8 comme en repli ASCII. L'information n'est jamais perdue,
seul le confort l'est.

Enfin, un mode « sans couleur » (`--sans-couleur`, ou `NO_COLOR` dans
l'environnement) rend tout en `data` et ne repose que sur les glyphes.

---

## 6. Glyphes — le second canal, obligatoire

| Glyphe | Sens | Couleur |
|---|---|---|
| `●` | complet, réussi, présent | `state-complete` |
| `▲` | substitut, avertissement, réserve | `state-substitute` |
| `✕` | absent, manquant, refusé, invalide | `state-absent` |
| `·` | neutre, non renseigné, sans objet | `muted` |
| `▸` | curseur de sélection (ligne courante) | `accent` |
| `[x]` / `[ ]` | case cochée / décochée | `accent` / `muted` |
| `( )` / `(•)` | choix exclusif, non retenu / retenu | `muted` / `accent` |
| `▓` / `░` | barre de progression, fait / restant | `accent` / `muted` |
| `>` | invite de saisie libre : ce champ a le focus | `accent` |
| `█` | caret d'édition, à la position d'insertion | `accent` |
| `└─` | rattachement hiérarchique (page sous lot) | `muted` |

**Aucun glyphe hors de cette table.** L'inventaire est court exprès : chaque
glyphe ajouté est un glyphe qui peut manquer dans une police de terminal. Les dix
ci-dessus sont dans le plan multilingue de base et rendus par toutes les polices
de console courantes.

**Repli ASCII pur** (`--ascii`, pour les terminaux qui ne rendent pas l'UTF-8) :
`●`→`*`, `▲`→`!`, `✕`→`x`, `·`→`.`, `▸`→`>`, `▓`→`#`, `░`→`-`, `└─`→`\_`,
`█`→`_`, les cadres en `+`, `-`, `|`. Le sens ne change pas, seul le dessin
change.

**Cette table est verifiable, et elle a deja servi.** Un balayage des maquettes a
trouve deux pictogrammes de dossier et de fichier introduits en cours de route,
hors table : ils sont remplaces par le mot `dossier` / `fichier`. Un emoji ne se
rend pas de la meme facon d'un terminal a l'autre, et il occupe deux colonnes sur
certains — c'est-a-dire qu'il casse la grille en plus du style.

---

## 7. Cinq motifs de composant, et rien d'autre

Toute la TUI se compose de ces cinq-là. Un écran qui a besoin d'un sixième motif
est un écran mal découpé.

**Le cinquième a été ajouté le 2026-08-29** (`EPIC11-ARB-48`), et il **remplace**
le champ-chemin du motif formulaire — il ne s'y ajoute pas. Motif mesuré : la
complétion `Tab` du champ-chemin ne proposait rien sur un champ vide, tenait sa
zone de propositions sur une ligne, et s'arrêtait au plus long préfixe commun,
donc ne complétait rien sur des dossiers numérotés. Voir §7.5.

### 7.1 La **liste sélectionnable**

Un choix parmi N. Curseur `▸`, une ligne par entrée, libellé en `data`, donnée
secondaire alignée à droite en `muted`.

```
   ▸ projet_demo                              ouvert le 2026-08-26 · 3 rushes
     film_court_2026                          ouvert le 2026-08-21 · 1 rush
     tests_calibration                        ouvert le 2026-08-14 · 0 rush
```

`↑↓` déplace, `Entrée` valide. Au-delà de ce que la zone centrale peut montrer,
la liste **défile** et porte un compteur `(3-12 sur 27)` sur sa dernière ligne.

### 7.2 La **liste cochable**

Plusieurs choix parmi N (`EPIC11-ARB-10` : sélection multi-lots au Pdf). Même
navigation, plus `Espace` qui coche.

```
   ▸ [x] lot_25fps                            124 frames · 25 fps      ● complet
     [ ] lot_12p5                              62 frames · 12,5 fps    ● complet
     [x] lot_08fps                             40 frames · 8 fps       ▲ 2 mires
```

Le compte des cochés est **toujours** rappelé sous la liste : `2 lots cochés sur
3`. Une liste cochable ne se valide jamais à zéro coché sans le dire.

### 7.3 Le **formulaire**

Libellé à gauche en `muted` sur 22 colonnes, champ à droite en `data`. Le champ
au focus porte `>` ; les autres, un espace. Une valeur préremplie est une valeur
**réelle**, jamais un exemple grisé — un champ prérempli faux est plus dangereux
qu'un champ vide (`EXPERIENCE.md` de la GUI, Flow 3).

```
     Cadence(s) cible      > 12,5                                  source/2
     Borne d'entrée          00:00:04:12
     Borne de sortie         ·                                     (facultatif)
     Profondeur              (•) 16 bits   ( ) 8 bits
```

Un champ invalide passe en `state-absent` **avec** son glyphe `✕` et le motif du
refus en ligne d'état. **L'action principale reste inaccessible tant qu'un champ
requis est vide ou invalide** — c'est le « parcours interactif qui oblige
l'utilisateur à remplir les paramètres nécessaires » du §1 de la vision.

### 7.4 Le **panneau chiffré** (confirmation, rapport, résultat)

Le point de jugement d'`EPIC11-ARB-4`, et le motif le plus important de cette
TUI : c'est lui qui tient lieu de previz. Un cartouche encadré, deux colonnes,
libellé `muted` à gauche, chiffre `data` à droite, les noms produits en dernier
et **éditables** (`EPIC11-ARB-8`).

```
     ┌ À écrire ─────────────────────────────────────────────────────────┐
     │  Lots créés                2                                      │
     │  Frames écrites            124  +  62                             │
     │  Bornes                    00:00:04:12 → 00:00:09:08              │
     │  Espace disque             ~ 3,1 Go            (majorant)         │
     │                                                                   │
     │  Noms produits           > projet_demo_rush_01_25fps               │
     │                            projet_demo_rush_01_12p5               │
     └───────────────────────────────────────────────────────────────────┘
```

Règles de ce motif :

* **tout chiffre porte son unité**, et un majorant porte le mot `(majorant)` —
  une estimation présentée comme une mesure est un mensonge d'affichage ;
* **rien n'est écrit avant ce panneau**, et il est le dernier écran franchissable
  sans frais ;
* les **noms produits** sont en bas, séparés du reste par une ligne vide, parce
  que ce sont les seules lignes éditables du panneau.

### 7.5 L'**explorateur de dossiers**

Partout où un chemin se désigne. Trois zones à **hauteur fixe** : la ligne du
parent, la barre d'adresse, la liste défilante, et la ligne de validation.

```
    ←  …\Documents\
      Dossier              D:\HOKO\Documents\mmu
   ────────────────────────────────────────────────────────────────────────
      archives/                                              0 sous-dossier
    ▸ projects/                                             6 sous-dossiers
      …                                                          1-8 sur 27
   ────────────────────────────────────────────────────────────────────────
    ⏎  Valider   projects/
```

**Les deux lignes encadrantes sont des étiquettes vives, jamais des cibles**
(`EPIC11-ARB-50`) : le curseur n'y va pas, celle du haut dit où `←` mène, celle
du bas dit ce que `⏎` validerait. Il n'y a donc **jamais deux curseurs** à
l'écran, et rien à « atteindre ».

`⏎` valide l'entrée sous le curseur, `→` y entre, `←` remonte, `Tab` entre dans
la barre d'adresse et en sort — **et rien d'autre** (`EPIC11-ARB-49`, `51`).
Toute lettre est prise par le saut alphabétique : **aucune lettre n'est un
raccourci d'action**.

---

## 8. La progression

Elle occupe la **ligne d'état**, jamais la zone centrale — la zone centrale
continue de montrer ce qui est en train d'être fait (le journal, ou le panneau
chiffré figé). Format unique, sur les quatre ateliers :

```
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░  68 %  84/124 frames  reste ~ 1 min 10
```

* la barre fait **36 colonnes**, toujours, et les trois champs qui la suivent
  sont séparés par **deux** espaces : à 80 colonnes de plancher, la ligne
  complète en fait 75 et il ne reste pas de marge pour en dépenser trois ;
* le pourcentage, puis **le compte réel** (`fait/total` avec son unité) — le
  compte est ce qui est vrai, le pourcentage est ce qui est lisible ;
* **le temps restant n'apparaît que quand il existe** (§3). Il est dérivé de
  `EstimateurTempsRestant.secondes_par_frame` — secondes par frame, jamais son
  inverse (`EPIC7-ARB-80`), parce que dans ce dépôt « images par seconde » désigne
  toujours la cadence d'un rush.

Une progression **par lot et par page** (Pdf, `EPIC11-ARB-10`) porte les deux
comptes, et ils **remplacent** le compte simple au lieu de s'y ajouter :

```
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░  90 %  lot 2/2 · page 3/5  reste ~ 8 s
```

Ce n'est pas un choix de style : à 80 colonnes, la barre **plus** le compte
simple **plus** le détail **plus** le temps restant font 89 colonnes. C'est la
grille qui décide de la forme. Rien n'est perdu — le détail porte les deux
comptes, et `19/21 pages` se relit dans `lot 2/2 · page 3/5`.

---

## 9. Do's and Don'ts

**Deux règles de cette section ont été amendées le 2026-08-29**, après la revue
en trois couches de la vague 2 bis (finding `F-14` de la couche 3) : la section 7
avait reçu l'amendement d'`EPIC11-ARB-48`, celle-ci non, et elle contredisait
donc deux arbitrages postérieurs sur le seul document que les stories lisent
comme la charte. Les deux règles amendées portent leur arbitrage en clair
ci-dessous ; ce qu'elles interdisaient reste interdit, c'est leur **portée** qui
est corrigée.

**À faire**

* écrire le chiffre à côté de l'état : `● complet` plutôt que `●` seul ;
* préremplir depuis la convention du dépôt et laisser éditable (`EPIC11-ARB-8`) ;
* laisser la ligne d'état vide quand il n'y a rien à dire ;
* nommer un refus par son code (les codes énumérés de la story 5.27), pas par
  « échec ».

**À ne pas faire**

* pas de seconde colonne, jamais — voir §1 ;
* pas de couleur sans glyphe — voir §5 ;
* pas de temps restant avant la première mesure — voir §3 ;
* pas d'issue **qui écrit** atteignable par une seule frappe depuis le montage
  d'un écran (`EPIC11-ARB-7`, sous la forme réduite que lui donne
  `EPIC11-ARB-45` le 2026-08-28). **La formulation d'origine — « pas de valeur
  présélectionnée sur un choix qui engage » — est caduque** : depuis `ARB-45` le
  curseur *est* la sélection, il n'y a plus de case à cocher, et un curseur posé
  sur la première entrée au montage est une présélection de fait. Ce qui protège
  n'est donc plus le double geste mais le **panneau chiffré** d'`EPIC11-ARB-4`,
  par lequel passe toute issue qui écrit — c'est cette propriété-là qui se
  mesure ;
* pas d'animation qui tourne (`spinner`) **à la place d'un compte réel** : un
  compte qui n'avance pas est une information, un sablier qui tourne n'en est pas
  une. **L'interdit porte sur le remplacement, pas sur le rotor**, et la nuance a
  été payée : quand aucun compte réel n'existe, il n'y a rien à remplacer et le
  rotor devient le seul signe honnête que la machine travaille. Le cas est
  mesuré, pas supposé — `pdf_render.render_lot_pdf` émet un jalon **par page**
  et une mire de calibration tient sur **une** page, donc le seul compte
  alimentable y aurait deux états, 0 % puis 100 %. Le rotor vit alors dans
  `jetons.ROTOR` / `jetons.rotor()`, avec son repli ASCII à quatre dessins
  distincts ; il n'entre pas dans la table des glyphes d'état, qui nomme des
  états et non des attentes ;
* pas de troncature silencieuse d'un chemin. **Trois abrègements, et le milieu
  n'est que le premier des trois** — la règle d'origine ne connaissait que
  celui-là et `EPIC11-ARB-52` la contredit deux fois :
  * **au milieu**, avec `…`, en gardant le début et le nom de fichier
    (`jetons.abreger_chemin`) : c'est le cas par défaut, celui d'un chemin qu'on
    **lit** par ses deux bouts — la racine dit où l'on est, le dernier segment
    dit ce que c'est ;
  * **par le début**, avec `…` en tête : la barre d'adresse de l'explorateur est
    *toujours* une fenêtre glissante calée sur la **fin** du chemin, et le chemin
    complet rendu en ligne d'état l'est de même. Motif d'`EPIC11-ARB-52` : ici la
    fin est ce que l'opérateur **vient de taper**, et une barre qui changerait de
    comportement selon qu'on tape ou non ferait la « saute » qu'Egan refuse ;
  * **par la fin**, avec `…` : une **phrase** (`jetons.ajuster`), qui se lit de
    gauche à droite et dont la fin coûte le moins cher à perdre. Jamais un chemin
    — abrégés par la fin, `…\projects\projet_demo` et `…\projects\projet_hiver`
    rendent la même chaîne.
