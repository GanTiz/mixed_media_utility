---
status: draft
date: 2026-08-27
surface: TUI
design: ./DESIGN.md
sources:
  - _bmad-output/planning-artifacts/tui-vision.md
  - _bmad-output/implementation-artifacts/decisions-2026-08-27-epic-11-tui.md
  - _bmad-output/implementation-artifacts/arbitrages-epic-11-a-trancher.md
  - _bmad-output/planning-artifacts/ux-designs/ux-mixed_media_utility-2026-08-16/EXPERIENCE.md
---

# TUI — Parcours utilisateurs

**Ce document dit comment ça marche ; `DESIGN.md` dit à quoi ça ressemble.** Les
deux se lisent ensemble, et chacun gagne sur l'autre dans son domaine.

Écrit pour être **validé écran par écran** avant que la première story de
l'Epic 11 ne soit rédigée. Chaque écran porte : ce que l'opérateur **voit**, ce
qu'il **peut faire**, ce qui **se passe**, et **les cas limites** — parce que
c'est là que se cachent les décisions que personne n'a prises.

Chaque écran renvoie à sa maquette, vérifiée à 80 × 24 par
`verifier_maquettes.py`.

---

## 1. Foundation

**Forme.** Application plein terminal, plancher 80 × 24, pilotée **entièrement au
clavier** (`EPIC11-ARB-11`). Pas de souris en v1 ; quand elle arrivera, aucun
geste ne lui sera réservé.

**Ce que la TUI est.** Un habillage interactif de la CLI (`EPIC11-ARB-1`) : elle
héberge le cœur **en processus**, produit exactement les mêmes artefacts, le même
manifest et les mêmes codes retour que les commandes `mmu` correspondantes, et
consomme nativement le canal de progression de la story 5.28.

**Ce que la TUI n'est pas.** Elle ne remplace pas la GUI. Ce qu'elle ne fait pas
est **arrêté comme périmètre**, pas comme dette (`EPIC11-ARB-12`) :
l'arborescence du chutier, la prévisualisation d'images, **la réparation
géométrique d'un scan** (poignées de coin, loupe), la relecture (lecteur, wipe),
l'aperçu visuel des planches.

> **Amendement du même jour** (`EPIC11-ARB-27`). La **complétion d'un QR non
> décodé** figurait dans cette liste ; elle en sort et entre dans la TUI. Motif :
> la planche imprime un bloc d'identité portant les identifiants canoniques
> **verbatim**, byte pour byte identiques au payload du QR — c'est le mécanisme
> de secours de la story 4.6. L'opérateur recopie du texte imprimé ; le pointage
> de la GUI est un confort, pas la condition. La réparation *géométrique*, elle,
> reste dehors : elle demande de juger une image.
>
> **Corollaire demandé par Egan et retenu** (`EPIC11-ARB-42`) : le formulaire
> **offre d'ouvrir le fichier de scan** de la planche fautive, pour que
> l'opérateur lise le bloc d'identité à l'écran quand il n'a plus le papier.

**La TUI crée un projet** (`EPIC11-ARB-22`), écran `E0-4`, sur la forme tranchée
pour la GUI (`EPIC7-ARB-82`) : dossier parent, nom, aperçu du chemin, et
l'arborescence posée par le cœur.

> *Une version antérieure de ce document disait le contraire*, au motif qu'aucune
> sous-commande CLI ne crée un projet à vide. Le raisonnement confondait le
> périmètre **CLI** et le périmètre du **cœur** : `EPIC11-ARB-1` héberge le cœur
> en processus, donc `ensure_project_layout` est appelable directement. La
> couverture CLI (`EPIC11-ARB-18`) est un **plancher, pas un plafond**.

**La TUI relinke un rush** (`EPIC11-ARB-32`), depuis `E2-1` — l'écran où
l'absence se voit, pas depuis un menu « Projet ». Egan l'a d'abord exclu, puis
rétabli en deux temps : « il faut pouvoir relink directement depuis l'écran où on
voit que le rush est manquant », puis « en fait si, il faut relinker pour pouvoir
générer des lots sur des rushes qui feraient partie d'un projet ».

C'est cette seconde phrase qui donne le **motif** : sans relink, un rush déclaré
mais délié n'est pas seulement mal affiché — **il est inextractible**, et
l'atelier Extraction s'arrête sur lui. Le relink n'est donc pas un confort de
réparation, c'est ce qui rend une branche du parcours praticable.

*(Une version antérieure de ce document le rangeait en non-objectif, sur la
foi d'`EPIC11-ARB-23`, lui-même réécrit.)*

---

## 2. Architecture d'information — trois paliers

`EPIC11-ARB-2`. Ce ne sont pas des onglets et ce n'est pas un panneau latéral :
ce sont **trois paliers empilés**, dont un seul est à l'écran à la fois.

```
   palier 0        palier 1              palier 2
   ┌─────────┐     ┌──────────────┐      ┌──────────────────────────┐
   │ Projet  │ ──▶ │  Ateliers    │ ──▶  │  Extraction · Scan       │
   │         │ ◀── │              │ ◀──  │  Pdf · Exports · Projet  │
   └─────────┘     └──────────────┘      └──────────────────────────┘
        ▲                  ▲                          │
        └──── Échap ───────┴───────── Échap ──────────┘
```

**Règles de circulation, sans exception :**

1. `Échap` remonte **d'un** palier. On ne saute jamais deux paliers d'un coup :
   depuis le milieu d'un formulaire d'atelier, `Échap` rend le menu des ateliers,
   pas l'écran projet.
2. **Un formulaire abandonné n'écrit rien.** `Échap` en cours de saisie perd la
   saisie et le dit en ligne d'état ; il ne demande pas confirmation, parce que
   rien n'a encore été engagé.
3. **Après une exécution, on retombe au palier 1** (`EPIC11-ARB-13`), jamais au
   palier 0. Un opérateur qui enchaîne deux extractions ne rouvre pas son projet.
4. `Échap` pendant une **exécution** ne remonte pas : il ouvre l'écran
   d'interruption (`T6-1`). C'est la seule exception, et elle existe parce qu'une
   exécution a déjà commencé à écrire.

**Un atelier qui a plusieurs entrées commence par son menu** (`EPIC11-ARB-28`) :
Scan (`E3-0` — détecter, calibrer une chaîne, recalibrer un lot écrit) et Pdf
(`E5-0` — composer des planches, planche de calibration). Extraction et Exports
n'en ont pas : une seule entrée chacun, et un menu y serait un écran à franchir
pour rien.

**Ce que le bandeau garantit.** À tout instant, la ligne 2 dit le projet, le
palier et l'objet travaillé. C'est ce qui remplace l'arborescence de la GUI : on
ne voit pas où on est dans un arbre, mais on lit toujours où on est.

---

## 3. Primitives d'interaction

| Touche | Partout | Nuances |
|---|---|---|
| `↑` `↓` | déplacer le curseur | dans une liste, un groupe de choix exclusifs, ou entre champs |
| `Entrée` | valider la ligne ou le formulaire | sur un formulaire incomplet : **ne fait rien** et la ligne d'état nomme le champ manquant |
| `Espace` | cocher / décocher | listes cochables seulement (Pdf) |
| `Tab` | champ suivant · compléter un chemin · ouvrir le journal · **basculer de zone** | **quatre** emplois depuis le 2026-09-02, jamais deux à la fois sur le même écran. La bascule de zone est venue avec `E5-5b` / `E5-5c` (`atelier_pdf_resultat.JETON_DE_LA_BASCULE`), où la liste des écrits et les suites sont deux zones navigables et un seul curseur est visible (`EPIC11-ARB-50`) |
| `Échap` | remonter d'un palier | pendant une exécution : écran d'interruption |
| `F1` | aide du champ courant, ou le manuel | `EPIC11-ARB-14` |
| `e` | éditer les noms produits | sur un panneau de confirmation seulement |
| `q` | quitter | demande confirmation si une tâche tourne |

**Sur la saisie libre.** Un champ de texte accepte la saisie caractère par
caractère, `←` `→` pour se déplacer dedans, `Retour arrière` pour effacer. `Tab`
y complète un chemin — et c'est pour cette raison que `Tab` n'ouvre pas le
journal sur un écran qui porte un champ de chemin.

**Sur les raccourcis de valeur.** Certains champs offrent des touches qui posent
une valeur d'un coup : `s` `2` `3` `4` sur la cadence d'extraction
(`EPIC11-ARB-5`), `r` pour remettre la cadence source aux Exports. Ils sont
**toujours affichés à côté du champ**, jamais seulement dans le manuel.

---

## 4. Motifs d'état

| État | Ce que l'opérateur voit | Ce qu'il peut faire |
|---|---|---|
| **Vide** | la liste dit ce qui manque et comment en avoir : « aucun lot reconstruit — passez d'abord par l'atelier Scan » | remonter, ou aller là où ça se fabrique |
| **Chargement** | la liste s'affiche dès qu'elle est lue ; pas d'écran d'attente pour une lecture de manifest | rien, c'est instantané |
| **Saisie incomplète** | le champ manquant en `state-absent` avec `✕`, le motif en ligne d'état | l'action principale **ne répond pas** tant que ça n'est pas réglé |
| **Prêt à écrire** | le panneau chiffré, et « rien n'a encore été écrit » en ligne d'état | valider, modifier, annuler |
| **En cours** | barre, compte réel, temps restant s'il existe ; le journal défile | voir le journal complet, interrompre |
| **Réussi** | panneau `Écrit`, chiffres réels (pas les majorants), et une liste de suites possibles | ouvrir le dossier, enchaîner, remonter |
| **Refusé** | le **code** de refus, la phrase qui l'explique, et ce qui n'a pas été écrit | reprendre autrement, voir le journal |
| **Partiel** | ce qui est écrit et ce qui ne l'est pas, séparément | reprendre, ou assumer |

**Deux invariants d'état** repris de la GUI et qui valent ici :

* **une frame absente et une mire de remplacement ne sont pas la même chose** et
  ne se fondent jamais en un seul indicateur. `✕ absente` et `▲ mire` sont deux
  lignes, deux glyphes, deux couleurs ;
* **un chiffre estimé n'est jamais présenté comme mesuré.** Avant écriture :
  `~ 3,1 Go (majorant)`. Après : `2,1 Go`, sans tilde et sans mention.

---

## 5. Les écrans, un par un

### Palier 0 — Projet

#### `E0-1` · Ouvrir un projet — les récents

*Maquette : `maquettes/E0-1-projet-recents.txt`*

**Il voit** la liste des projets récemment ouverts, le plus récent en tête
(`EPIC11-ARB-3`), chacun avec sa date d'ouverture et son contenu chiffré (rushes,
lots). Sous un filet, une entrée « Ouvrir un autre dossier… ».

**Il peut** monter et descendre, ouvrir d'un `Entrée`, ou passer à la saisie
d'un chemin par `Tab`.

**Il se passe** : le projet s'ouvre au palier 1, son nom entre au bandeau, et sa
date d'ouverture est mise à jour dans la liste des récents.

**Cas limites.**
* *Aucun récent* (premier lancement) : la liste est absente, le curseur est
  d'emblée sur le champ de chemin, et une phrase dit « aucun projet ouvert
  récemment — indiquez un dossier de projet ». Pas de liste vide décorative.
* *Un récent a disparu du disque* : il reste listé, en `state-absent` avec `✕`,
  et son ouverture propose de le retirer de la liste. On ne l'efface pas
  silencieusement — un disque externe débranché n'est pas un projet supprimé.
* *Un récent est sur un volume lent ou réseau* : la liste ne bloque pas ; le
  contenu chiffré s'affiche à `·` tant qu'il n'est pas lu.

**Retirer un projet de la liste** (`EPIC11-ARB-39`, demande d'Egan). `Suppr` sur
une ligne l'ôte des récents, **sans toucher au dossier du projet** — comme le
geste « retirer » de la ligne de projet de la GUI. La ligne d'écran le dit, parce
que c'est exactement l'ambiguïté qu'un opérateur redoute devant une touche
`Suppr` : la liste des récents est une commodité, pas un inventaire des projets.
Aucune confirmation : le geste est réversible en rouvrant le projet par son
chemin.

*Depuis le 2026-08-29 (`EPIC11-ARB-55`), chaque ligne de récent porte **cinq**
cardinaux en initiales — `3R · 5L · 8P · 2S · 1M` — et non plus deux. `P`, `S`
et `M` comptent les **lots ayant atteint** l'état `pdf`, `scan` et `encode` :
le manifeste ne porte aucun cardinal de planches, de scans ni de masters, et
les compter sur le disque ferait écrire à la TUI un jugement que le cœur ne
porte pas (`EPIC11-ARB-30`). `·` là où le manifeste n'a pas été lu, jamais `0`.
Maquette `X9`.*

#### `E0-2` · Ouvrir un projet — par chemin

*Maquette : `maquettes/E0-2-projet-chemin.txt`*

*Réécrit le 2026-08-29 par la story 11.2b (`EPIC11-ARB-48`). La complétion
`Tab` décrite ici jusqu'à cette date **n'existe plus** : elle ne proposait rien
sur un champ vide, tenait sa zone de propositions sur une ligne, et s'arrêtait
au plus long préfixe commun — donc ne complétait rien sur des dossiers
numérotés. Maquettes `X1` à `X8`.*

**Il voit** l'explorateur : le dossier parent en haut, le dossier courant dans
la barre d'adresse, la liste des sous-dossiers, et en bas ce que `Entrée`
validerait.

**Il peut** se déplacer (`↑↓`), entrer (`→`), remonter (`←`), sauter au premier
nom qui commence par un caractère (toute touche imprimable), valider en une
frappe (`Entrée`), passer dans la barre d'adresse et en sortir (`Tab`), y coller
un chemin (`Ctrl+V`), revenir aux récents (`Échap`).

**Il se passe** : la liste suit ce qui est tapé, en direct. Les deux lignes
encadrantes ne se sélectionnent jamais — il n'y a **jamais deux curseurs** à
l'écran.

**Cas limites.**
* *Chemin relatif* : accepté, résolu depuis le dossier courant, et le chemin
  **absolu** résolu est ce que la barre d'adresse montre.
* *Chemin trop long* : la barre d'adresse est **toujours** une fenêtre glissante
  calée sur la fin, avec `…` en tête. Un seul comportement, donc aucune saute
  quand on entre dans la saisie. Le chemin complet vit en ligne d'état, et s'y
  tronque **par le début**.
* *Chemin qui n'existe pas* : la ligne d'état dit « aucun dossier n'existe à
  cette adresse ». Le champ **ne passe pas en refus** — une frappe en cours
  n'est pas une erreur.
* *Dossiers cachés* : masqués, `Ctrl+H` les montre, et la ligne d'état dit
  combien. Rien n'est invisible en silence.
* *Dossier illisible* : listé, marqué `✕`, non entrable. Le masquer ferait
  croire qu'il n'existe pas.
* *Racine d'un volume* : `←` mène à la liste des volumes.

#### `E0-3` · Refus — ce dossier ne porte pas de projet

*Maquette : `maquettes/E0-3-projet-refus.txt`*

**Il voit** le champ marqué `✕`, la phrase qui explique (« ce dossier existe mais
ne porte pas de `project.json` »), et **trois suites** dont la première est
« Créer un projet ici ».

**Il peut** créer le projet sur place, corriger le chemin, ou remonter aux
récents.

**Pourquoi c'est une bifurcation et pas un cul-de-sac** (`EPIC11-ARB-22`). Cet
écran affichait auparavant la ligne de commande que l'opérateur aurait dû taper.
Sur le premier écran, au premier lancement, pour le premier geste : c'est
exactement la découverte que la TUI existe pour supprimer.

**Cas limites.**
* *Le dossier n'existe pas du tout* : ce n'est **plus un refus**
  (`EPIC11-ARB-40`, demande d'Egan) — la TUI propose de le créer, et l'écran de
  création (`E0-4`) le signale (« ce dossier n'existe pas — il sera créé
  aussi »). Un chemin qu'on tape pour un projet qui n'existe pas encore est un
  cas nominal de création, pas une faute de frappe à corriger.
* *Le dossier est vide* : même bifurcation, sans le `✕` — un dossier vide n'est
  pas une anomalie, c'est un point de départ.
* *Le dossier porte un `project.json` illisible ou d'une version inconnue* :
  troisième message, qui nomme le fichier et le problème, et ne propose **pas**
  de le réparer.

#### `E0-4` · Créer un projet

*Maquette : `maquettes/E0-4-projet-creer.txt`*

**Il voit** deux champs — **dossier parent** (celui qui *contiendra* le projet)
et **nom du projet** — puis, sous un filet, l'aperçu de ce qui va être créé : le
chemin résultant, l'arborescence de travail, le fichier de projet.

**Il peut** créer, ou remonter.

**Ce que la forme évite.** Demander « le dossier de projet » obligerait
l'opérateur à créer ce dossier **avant** d'ouvrir l'outil — un geste hors de
l'outil, imposé par l'outil. C'est le défaut que le terrain a trouvé sur la GUI
et qu'`EPIC7-ARB-82` a corrigé ; la TUI n'a pas à le refaire.

**L'arborescence est posée par le cœur** (`project_layout.ensure_project_layout`),
jamais par une seconde liste de dossiers écrite dans la TUI : deux listes
divergeraient au premier ajout.

**Cas limites.**
* *Le dossier cible existe déjà et porte un projet* : la création échoue **avant
  tout écrit**, et le geste proposé devient « ouvrir ».
* *Le dossier cible existe et est vide* : création acceptée.
* *Le dossier parent n'existe pas* : **créé aussi** (`EPIC11-ARB-40`), y compris
  sur plusieurs niveaux, et l'aperçu le dit avant d'écrire. Le refus antérieur
  faisait sortir de l'outil pour un `mkdir` — exactement le renvoi à la ligne de
  commande qu'`EPIC11-ARB-22` a supprimé du premier écran.
* *Nom portant un caractère interdit par le système de fichiers* : refus du champ,
  motif nommé, aperçu non calculé.

---

### Palier 1 — Menu des ateliers

#### `E1-1` · Que faire dans ce projet

*Maquette : `maquettes/E1-1-menu-ateliers.txt`*

**Il voit** cinq entrées, chacune avec une phrase qui dit ce qu'elle fait —
Extraction, Pdf, Scan, Exports, puis Projet, séparé des quatre ateliers par une
ligne vide parce que ce n'est pas un atelier. En bas, sous un filet, **la
dernière écriture du projet** : quand, quoi, avec quel résultat.

**Il peut** entrer dans un atelier, ou remonter à l'écran projet par `Échap`.

**Pourquoi la dernière écriture est là.** C'est la réponse minimale à ce que le
Flow 4 de la GUI obtient par le chutier : « où en étais-je ? ». La TUI n'a pas
d'arborescence ; elle a cette ligne. Elle ne dit pas tout, mais elle dit la seule
chose qu'un opérateur qui revient après trois semaines a besoin de savoir avant
de choisir un atelier.

**Ordre des entrées.** Extraction, Pdf, Scan, Exports — **l'ordre des onglets de
la GUI**, c'est-à-dire l'ordre du flux.

> **Révisé le 2026-09-06, sur retour terrain d'Egan** (verbatim : « remonter
> l'atelier [PDF] dans la liste AVANT scan (ordre logique) »). Ce paragraphe
> posait l'inverse : « Extraction, Scan, Pdf, Exports — l'ordre de la chaîne de
> production, pas l'ordre des onglets de la GUI (qui met Pdf en 2 et Scan en 3).
> C'est un écart délibéré : la GUI a quatre onglets simultanés où l'ordre est une
> disposition ; la TUI a une liste qu'on lit de haut en bas, où l'ordre est une
> suggestion de parcours. » L'écart est **fermé** : une liste qu'on lit de haut en
> bas et qui contredit l'ordre que le même produit affiche ailleurs n'oriente pas,
> elle désoriente. L'ordre du menu coïncide désormais **exactement** avec
> `gui/coquille.py:ORDRE_ATELIERS`, dont le commentaire dit déjà « l'ordre est
> l'ordre du flux, il ne se renégocie pas ici ». La source de vérité reste
> `tui/projet_lecture.ATELIERS` ; ce document, la maquette `E1-1` et la doc
> utilisateur lui sont confrontés par
> `tests/unit/tui/test_frontiere_ordre_des_ateliers.py`.

**Cas limites.**
* *Projet vide* (aucun rush, aucun lot) : les entrées Scan, Pdf et Exports restent
  visibles mais portent leur condition (« aucun lot — passez par Extraction ou
  Scan »). Elles ne sont **pas** masquées : un opérateur doit pouvoir voir ce qui
  existe avant de savoir qu'il n'y a pas accès.
* *Aucune écriture encore faite* : la ligne du bas dit « aucune écriture dans ce
  projet », pas une ligne vide.

---

### Palier 2 — Atelier **Extraction**

Commande de cœur : `mmu extract`.

#### `E2-1` · Quel rush extraire

*Maquette : `maquettes/E2-1-extraction-rush.txt`*

**Il voit** les rushes **déclarés au manifest**, avec cadence, résolution, durée,
et surtout leur **présence sur cette machine** : `● ici` ou `✕ absent`. Sous un
filet, un champ pour ajouter un rush par chemin.

**Il peut** choisir un rush présent, saisir le chemin d'un nouveau, remonter.

**Il se passe** : le rush choisi entre au bandeau avec sa cadence et sa durée, et
ces valeurs alimentent les raccourcis de cadence de l'écran suivant.

**Cas limites.**
* *Rush déclaré mais absent* (`rush_hiver` sur la maquette) : listé, en
  `state-absent`, **sélectionnable**. Le choisir ne lance rien : la ligne d'état
  nomme la commande qui le rebranche (`mmu relink`). Le relink lui-même est
  **hors TUI** (`EPIC11-ARB-23`) — mais l'anomalie reste dite, parce qu'on ne
  masque pas ce qu'on ne traite pas.
* *Fichier vidéo que ffprobe ne lit pas* : refus nommé au moment de la saisie,
  avant même le formulaire.
* *Colorimétrie source absente ou incomplète* : le rush est acceptable, mais le
  panneau de confirmation portera la réserve et exigera un consentement
  supplémentaire — c'est `--accept-unknown-color` de la CLI, rendu visible.

#### `E2-2` · Temps 1 — quelles cadences regarder

*Maquette : `maquettes/E2-2-extraction-cadences.txt`*

**Il voit** une **liste cochable de cadences**, préremplie des cadences
remarquables du rush — la source, puis source/2, /3, /4 — **chacune avec son
compte de frames déjà calculé**. Sous la liste, le compte des cochées. Sous un
filet, les deux bornes.

**Il peut** cocher à l'`Espace`, **ajouter une cadence libre** par `a` (décimale
ou fractionnaire, `24000/1001`, story 3.8), retirer une cadence ajoutée par
`Suppr`, borner en timecode source, puis `Entrée` pour **prévisualiser** — ou `x`
pour **extraire sans regarder**.

**Pourquoi une liste et non un champ de texte** (`EPIC11-ARB-24`). Une saisie
`25 ; 12,5` oblige à deviner le séparateur, ne se retire pas sans réécrire la
chaîne, et ne dit rien de ce que vaut une cadence avant de l'avoir tapée. La
liste cochable est en outre **le motif déjà retenu** pour la sélection multi-lots
du Pdf : un seul motif de sélection multiple dans toute la TUI.

**La prévisualisation est facultative.** `x` extrait directement depuis cet
écran. Un opérateur qui refait tous les jours la même cadence n'a rien à
regarder ; lui imposer une lecture remplacerait une syntaxe obscure par une
cérémonie.

**Cas limites.**
* *Cadence supérieure à la source* : acceptée, mais elle répète des images. Dit à
  la frappe, redit à la confirmation ; jamais interdit — `previz` et `extract`
  appliquent d'ailleurs la même garde, avec les mêmes messages.
* *Cadence en double* : la seconde n'est pas ajoutée, un mot en ligne d'état.
* *Cadence donnant zéro frame dans les bornes* : la ligne passe en
  `state-absent`, et elle ne peut pas être cochée.
* *Borne de sortie avant la borne d'entrée* : refus du champ, motif nommé.

#### `E2-2b` · Temps 1 — la lecture comparée

*Maquette : `maquettes/E2-2b-extraction-previz.txt`*

**Il voit** que **la fenêtre de lecture s'est ouverte à côté du terminal**, les
touches qui la pilotent, et — dans la TUI — **le rapport chiffré qui se remplit au
fil de la lecture** : par cadence, frames retenues, frames réellement présentées,
écart au temps réel.

**Il peut** juger dans la fenêtre, la fermer, puis passer au choix.

**Ce que le rapport dit et que l'œil ne dit pas.** Un écart au temps réel de
+ 21 % signale un **décodage en retard**, pas une cadence mal choisie. Sans cette
distinction, un opérateur rejetterait une cadence à cause de sa machine.

> **Sans affichage, la prévisualisation est refusée** (`EPIC11-ARB-41`, tranché
> par Egan : « on refuse tout simplement la previz. Le cas serveur est un cas
> limite ! »).
>
> `cadence_previz` ouvre sa fenêtre par `cv2.imshow` ; en session SSH sans X11,
> elle ne peut pas s'ouvrir. Le module offre bien un mode mesuré
> (`--no-display`), et **la TUI ne l'expose pas** : une lecture sans image n'est
> pas une prévisualisation, et l'offrir sous ce nom serait un mensonge
> d'affichage.
>
> La TUI **refuse donc la prévisualisation** et le dit en une ligne, sans
> proposer de succédané. Le parcours reste entier : `x` extrait sans regarder
> depuis `E2-2`, et c'est le chemin nominal sur un serveur. **On ne dégrade pas
> une promesse, on la retire quand elle ne peut pas être tenue.**

**Cas limites.**
* *Aucun affichage disponible* : la TUI bascule seule en mode mesuré, le dit en
  ligne d'état, et l'écran ne parle plus de fenêtre.
* *Interruption en cours de lecture* : `previz` rend un rapport **partiel, marqué
  comme tel**, et ne laisse aucune trace — c'est son contrat.
* *Source VFR* : refusée, avec le même message qu'`extract`.

#### `E2-2c` · Temps 2 — lesquelles extraire

*Maquette : `maquettes/E2-2c-extraction-choix.txt`*

**Il voit** les cadences **qu'il vient de regarder**, cochables, chacune portant
**la mesure de la prévisualisation** et non plus une simple promesse. Sous la
liste, les lots à produire avec leurs noms conventionnels. Puis la profondeur.

**Il peut** cocher ce qu'il extrait, choisir 8 ou 16 bits (16 par défaut),
`Échap` pour revenir ajouter des cadences.

**Ce que ce temps 2 change.** On ne coche plus un nombre, on coche **un résultat
observé**. C'est l'idée d'Egan, et c'est ce qui aligne l'Extraction sur le Scan :
les deux ateliers qui produisent des lots explorent d'abord, engagent ensuite.

**Ce dont il n'hérite pas.** Une prévisualisation **n'autorise rien** — le module
le dit en tête : ni lot, ni entrée de manifest, ni consentement réutilisable. Le
temps 2 repasse donc intégralement par le panneau de confirmation
(`EPIC11-ARB-4`).

**Cas limites.**
* *Zéro coché* : `Entrée` ne fait rien, la ligne d'état le dit.
* *Une cadence saccadée cochée quand même* : autorisé — le saccadé venait du
  décodage, pas du lot produit. La confirmation ne le rappelle pas : ce serait
  transformer une mesure de lecture en réserve d'écriture, ce qu'elle n'est pas.


#### `E2-3` · Confirmation — ce qui va être écrit

*Maquette : `maquettes/E2-3-extraction-confirmation.txt`*

Le point de jugement (`EPIC11-ARB-4`).

**Il voit** un panneau chiffré : nombre de lots, frames par lot **et total**,
bornes retenues, profondeur, espace disque en **majorant explicite**,
destination — puis, séparés par une ligne vide, **les noms produits, éditables**
(`EPIC11-ARB-8`). Sous le panneau, trois choix exclusifs dont **aucun n'est
présélectionné**.

**Il peut** valider, revenir aux réglages, annuler, ou presser `e` pour éditer
les noms.

**Il se passe** : à la validation, et **seulement** à la validation, l'écriture
commence.

**Cas limites.**
* *Un lot du même nom existe déjà* : on ne va pas à l'exécution, on va à `T4-1`
  (écrasement). Comme dans la GUI, l'erreur se lève **au moment de lancer**, pas
  pendant la saisie.
* *Espace disque insuffisant* : le majorant est comparé à l'espace libre ; s'il
  ne passe pas, la ligne « Espace disque » est en `state-absent` et l'action
  principale est bloquée. Le majorant sert à ça — c'est pour cela qu'il est
  majorant.
* *Nom édité invalide* (caractère interdit, nom déjà pris par un autre lot du
  même projet) : refus du champ, l'ancien nom reste proposé.
* *Colorimétrie incomplète* : une ligne de réserve `▲` apparaît dans le panneau
  et l'intitulé du premier choix devient explicite (« Extraire malgré la
  colorimétrie incomplète »).

#### `E2-3b` · Éditer un nom produit · `E2-3c` · Le nom est refusé

*Maquettes : `maquettes/E2-3b-extraction-edition-nom.txt`,
`maquettes/E2-3c-extraction-nom-refuse.txt`*

**Il voit**, après `e`, le bloc des noms en édition — caret `█` à la position
d'insertion, et **un compteur par nom** (`31/48`). Sous le cartouche, la règle en
une phrase et ce que fait chaque touche.

**Il peut** taper, passer d'un nom à l'autre par `↑↓`, remettre le nom
conventionnel par `r`, valider par `Entrée`, abandonner l'édition par `Échap`
sans toucher aux valeurs.

**La limite est 48 caractères** (`EPIC11-ARB-25`), motif `^[A-Za-z0-9_-]+$`
(`io.naming.CANONICAL_ID_MAX_LENGTH`, imposé aux `project_id`, `rush_id` et
`lot_id` par `project.schema.json`). Accents et espaces sont hors motif.

**Et au-delà, le cœur refuse — il ne tronque pas.** C'est écrit tel quel dans
`calibration_profile` (« refusée plutôt que tronquée »), et la raison est
structurelle : **deux noms tronqués au même préfixe seraient le même lot**. La
TUI refuse donc de la même façon (`E2-3c`) : compteur en `state-absent`, motif
nommé, et **l'action principale reste inaccessible**. Tronquer en douce
fabriquerait une collision d'identifiants.

**Cas limites.**
* *Nom vide* : refusé — `r` remet le nom conventionnel.
* *Nom déjà porté par un autre lot du projet* : refusé, avec le nom du lot qui
  l'occupe.
* *Accent ou espace saisi* : le caractère n'est pas inséré, la ligne d'état
  nomme le motif accepté plutôt que de dire « invalide ».

#### `E2-4` · Exécution

*Maquette : `maquettes/E2-4-extraction-execution.txt`*

**Il voit** la liste des lots avec leur état (`en cours`, `en attente`, `● écrit`),
un journal qui défile, et en ligne d'état la barre, le compte réel et le temps
restant.

**Il peut** ouvrir le journal complet (`Tab`, écran `T3-1`), ou interrompre
(`Échap`, écran `T6-1`).

**Cas limites.**
* *Aucune mesure encore faite* : la barre est à 0, le compte à `0/124`, et **rien
  n'est affiché à la place du temps restant** (`EPIC7-ARB-67`).
* *Un lot échoue au milieu d'une série* : les lots déjà écrits le restent, le lot
  fautif porte son code de refus, les suivants ne sont pas lancés. L'écran de
  résultat sera **partiel**, pas « échoué ».
* *Le terminal est redimensionné pendant l'exécution* : la mise en page se
  recalcule, la tâche continue. Sous le plancher, l'écran passe au message de
  taille — la tâche continue quand même, et rien n'est perdu.

#### `E2-5` · Résultat

*Maquette : `maquettes/E2-5-extraction-resultat.txt`*

**Il voit** un panneau `Écrit` avec les **chiffres réels** (plus de majorant),
le manifest mis à jour, la durée. Puis une liste de suites : ouvrir le dossier,
enchaîner vers l'atelier suivant de la chaîne, refaire, remonter.

**Il peut** choisir une suite. `Échap` remonte au palier 1 (`EPIC11-ARB-13`).

**Pourquoi la suite « atelier Pdf » est là.** C'est le seul endroit où la TUI
propose la chaîne de production : après avoir extrait, la chose suivante est
généralement de composer les planches. La proposition **ne pré-sélectionne rien**
au-delà des lots qui viennent d'être écrits.

---

### Palier 2 — Atelier **Scan**

Commandes de cœur : `mmu scan detect` puis `mmu scan-write`, plus
`mmu scan calibrate` en parcours à part. Le découpage en deux temps est celui du
cœur, pas une invention de la TUI (`EPIC11-ARB-6`).

#### `E3-0` · Le menu de l'atelier Scan

*Maquette : `maquettes/E3-0-scan-menu.txt`*

**Il voit** trois entrées, chacune avec deux lignes qui disent ce qu'elle fait :
**Détecter des planches** (nommé « le parcours principal »), **Calibrer une
chaîne**, **Recalibrer un lot écrit**. En pied, le profil de calibration par
défaut du projet.

**Pourquoi ce menu existe** (`EPIC11-ARB-28`). `scan calibrate` et
`apply-calibration` n'avaient aucune porte d'entrée : leurs écrans portaient la
mention « parcours à part », qui est du vocabulaire de document de décision et ne
dit à personne où aller. Un atelier à plusieurs entrées commence par son menu.

**Le profil par défaut est affiché ici**, et pas ailleurs, parce que c'est
l'information qui décide si l'on va calibrer avant de détecter.

#### `E3-1` · Temps 1 — que faut-il détecter

*Maquette : `maquettes/E3-1-scan-depot.txt`*

**Il voit** deux champs (source, résolution de scan déclarée), et sous un filet
**ce qui a été trouvé** à la source : les premiers noms de fichiers, le compte
total, le poids, le type.

**Il peut** désigner un dossier d'images, une image seule ou un PDF multipage —
les trois formes que `scan` accepte —, déclarer le dpi, et lancer la détection.

**Un seul champ, et c'est l'explorateur qui montre les trois formes**
(`EPIC11-ARB-26`, dans la forme que lui donne `EPIC11-ARB-48` le 2026-08-29).
Le champ ne se complète plus au `Tab` : il **ouvre l'explorateur**, réglé sur
`montrer_fichiers`, qui liste **dossiers et fichiers ensemble**, chaque ligne
portant sa nature et sa mesure (`8 fichiers`, `78 Mo`), et marque `· pas une
source` ce qu'il ne sait pas lire. C'est l'écran `X6`, déjà dessiné et déjà
validé — son bandeau porte « Scan · temps 1 sur 2 », c'est bien celui-ci.
L'affordance n'est donc pas dans une ligne d'aide qu'on ne lit pas : elle est
dans ce que l'explorateur affiche. Pas de sélecteur de mode — un mode à choisir
avant de savoir ce qu'on a est un écran de plus pour rien.

**Ce que la TUI n'atteint pas, et il vaut mieux le dire.** `scan` accepte une
**quatrième** forme (`EPIC7-ARB-88`) : une *sélection de plusieurs fichiers*
qui fait **un** lot. L'explorateur valide **une** entrée sous le curseur et n'a
aucune sélection multiple. Cette quatrième forme reste donc à la ligne de
commande, et l'écran le dit plutôt que de la taire.

**Et le résumé parle dans le vocabulaire de la forme retenue** (`E3-1b`) :
« 1 PDF · 8 pages » pour un PDF (maquette `maquettes/E3-1b-scan-depot-fichier-unique.txt`), « 24 fichiers · 1,9 Go » pour un dossier.
Confondre pages et fichiers est précisément ce qui ferait déclarer un lot
incomplet à tort.

**Ce que la ligne d'état martèle** : « la détection n'écrit aucune frame ». C'est
l'invariant d'`EPIC11-ARB-6`, et il doit être lisible avant le premier lancement,
pas découvert après.

**Cas limites.**
* *Le dpi est obligatoire* et n'a pas de valeur par défaut dans le cœur : le champ
  est vide, marqué requis, et l'action est bloquée tant qu'il l'est. La maquette
  du 2026-08-27 le montrait pourtant **prérempli à 600**, sur les deux écrans, et
  `E3-1b` proposait même de « reprendre » la valeur qu'elle avait déjà posée :
  corrigé le 2026-08-30, à la source.

> **La mesure est offerte, jamais posée d'office** (`EPIC11-ARB-38`, question
> d'Egan : « si l'outil est capable de lever cette erreur, on ne pourrait pas
> obtenir le DPI automatiquement ? »). Le cœur **mesure déjà** le dpi déclaré par
> les fichiers (`scan_ingest._measure_file_dpi`, et `_measure_pages_dpi` sur
> **toutes** les pages) — c'est ce qui lui permet de lever
> `DPI_DECLARE_INCOHERENT`. Mais il refuse de le substituer, motif écrit : « un
> scanner en auto-fit écrit une résolution qui ne correspond pas à l'échelle
> réelle de la page ».
>
> La TUI **affiche** donc la valeur mesurée à côté du champ (« les 8 pages
> déclarent 600 dpi ») et la reprend d'un geste, **sans préremplir**. Zéro
> ressaisie, mais un acte de l'opérateur — parce qu'un champ prérempli faux
> n'appelle pas la vérification, et l'auto-fit est exactement ce cas.
>
> **Ce geste n'est pas une lettre.** La maquette d'origine l'offrait sur `m`, à
> côté d'un champ de saisie, ce qu'`EPIC11-ARB-68` interdit « sans exception et
> sans ordre de priorité à maintenir » — c'est le défaut du `r` d'`E2-3b` sous
> une autre forme. La reprise est une **ligne du formulaire**, atteinte par
> `Tab` et prise par `⏎`. Même forme que le « Reprendre à 425 dpi » que
> l'arbitrage pose déjà sur l'écran de refus.
* *Vrac de plusieurs lots, voire de plusieurs projets* : c'est le cas nominal du
  Flow 4 de la GUI, et il est **supporté** — la détection trie par QR
  (story 5.24). L'écran ne demande pas à quel lot ça appartient.
* *PDF multipage* : compté en pages, pas en fichiers ; la ligne de résumé le dit
  (« 1 PDF · 24 pages »).
* *Source vide ou illisible* : refus avant lancement.

#### `E3-2` · Temps 1 — détection en cours

*Maquette : `maquettes/E3-2-scan-detection-en-cours.txt`*

**Il voit** le journal page par page : marqueurs ArUco trouvés, QR décodé ou non,
et **le rattachement** de chaque page à son lot. La progression est en **pages**,
pas en frames.

**Ce que le journal montre volontairement** : une page dont le QR n'est pas décodé
apparaît **au fil de l'eau**, avec « non rattaché, reste en attente de lecture ».
L'opérateur n'attend pas la fin pour savoir qu'il y a un problème.

**Cas limites.**
* *Aucun QR décodé du tout* : la détection va au bout, le rapport dira zéro lot
  reconnu et tout en attente de lecture. Ce n'est pas un plantage.
* *Page appartenant à un projet différent* : rattachée à rien, listée en attente
  de lecture, nommée. Elle n'est jamais rangée de force dans un lot du projet
  courant.

#### `E3-3` · Temps 1 — rapport, cas complet

*Maquette : `maquettes/E3-3-scan-rapport-complet.txt`*

**Il voit** un panneau par lot reconnu : pages trouvées **sur** pages attendues,
frames **sur** frames attendues, et l'état. Puis la file « en attente de
lecture », et une liste de suites.

**Il peut** écrire, reprendre la détection avec d'autres fichiers, annuler —
**trois** suites, et non quatre. « Voir le détail d'un lot » est retirée
(`EPIC11-ARB-101`, note 9 : « si rien n'existe on retire cette option ») : aucun
écran de détail de lot n'existe dans le temps 1. *Reprendre* ramène à `E3-1`, le
dépôt, avec le champ vide — la seconde moitié de la même note.

**Il se passe** : le document de détection est **déjà écrit** à ce stade — c'est
le livrable de `scan detect` — et la ligne d'état en donne le chemin. C'est ce qui
permet de quitter ici et de reprendre plus tard sans redétecter.

**Cas limites.**
* *Un lot déjà scanné une fois* (second tirage) : listé comme un lot distinct,
  avec sa date de scan. La composition d'un lot depuis plusieurs scans est **hors
  TUI** (`EPIC11-ARB-12`).
* *Un lot complet en pages mais portant des mires* : `▲` et non `●`, et le compte
  de mires est dit. Une mire n'est pas une frame.

#### `E3-4` · Temps 1 — rapport, cas incomplet

*Maquette : `maquettes/E3-4-scan-rapport-incomplet.txt`*

L'écran le plus important de l'atelier.

**Il voit** le même panneau, mais le lot incomplet porte `✕` et **deux lignes de
détail rattachées** (`└─`) : quelle page manque et quelles frames elle portait,
et quel fichier a été refusé avec **son code** (`QR_NON_DECODE` — les codes
énumérés de la story 5.27, `EPIC11-ARB-7`). Puis les trois issues.

**Il peut** choisir l'une des trois. **Aucune n'est présélectionnée**
(`EPIC11-ARB-7`) : un `Entrée` réflexe ne franchit pas un lot incomplet.

**Ce que chaque issue fait, écrit à côté d'elle :**
* *Écrire quand même* — le lot est écrit **incomplet**, avec son compte réel
  (46 frames, pas 62). Aucun trou n'est comblé par répétition.
* *Compléter le QR* (`EPIC11-ARB-29`) — ouvre `E3-4b` sur la page fautive,
  nommée. **Ce n'est plus « rescanner »**, et le motif est d'Egan : si le QR est
  illisible parce que le pli le traverse, le rescanner produit le même QR
  illisible ; et la planche n'est pas toujours disponible pour un second passage.
  Renvoyer au dépôt était une impasse, pas une v1 minimale.
* *Annuler* — rien n'est écrit ; le document de détection reste sur le disque.

**Cas limites.**
* *Tous les lots incomplets* : même écran, l'intitulé de la première issue dit
  « écrire les 2 lots incomplets ».
* *Un lot complet et un incomplet* (la maquette) : « écrire quand même » écrit
  **les deux**, et le dit. Il n'y a pas de sélection par lot en v1 — c'est une
  simplification assumée, à signaler si elle gêne.

#### `E3-4b` · Compléter ce que le QR aurait dit

*Maquette : `maquettes/E3-4b-scan-completion-qr.txt`*

Atteignable depuis le rapport de détection, sur une page dont le QR n'a pas été
décodé (`EPIC11-ARB-27`).

**Il voit** **six** champs — lot, page, gabarit, images sur la planche,
timecode première, timecode dernière — et, en tête, **où lire ces valeurs** : le
bloc d'identité imprimé en clair sur la planche. Chaque ligne porte en outre
**la clé imprimée** de son champ, quand la planche en imprime une, pour que
l'opérateur voie sur la même ligne le mot qu'il doit chercher sur sa feuille.
Sous un filet, la vérification de cohérence avec les pages déjà lues du même
lot.

> **Corrigé le 2026-08-31, sur mesure** (lot F de la story 11.5). Cette page
> annonçait *cinq* champs — « projet, lot, page, cadence source, cadence du
> lot » —, et ils étaient faux sur **deux axes** : trois d'entre eux sont des
> valeurs **neutres** que le manifeste donne déjà (projet, cadences), donc que
> l'opérateur ne lit pas sur la planche ; et quatre champs d'**identité** que
> le cœur exige y manquaient. Le formulaire livré demande exactement
> `scan_corrections.CHAMPS_D_IDENTITE`, dans l'ordre où la planche les imprime.
> La maquette `E3-4b` a été redessinée en conséquence (note 12 d'Egan).

**Il peut** saisir, champ par champ, et valider. `F1` sur un champ dit **où ce
champ se lit sur la feuille**. Et **une ligne du formulaire ouvre le scan de la
planche** dans la visionneuse du système (`EPIC11-ARB-42`) : on l'atteint par
`Tab`, on la déclenche par `Entrée`.

> **Corrigé le 2026-08-31, et c'est un arbitrage et non une coquille.** Cette
> page offrait la touche `o`. `EPIC11-ARB-68` interdit **sans exception** qu'une
> lettre soit un raccourci à côté d'un champ de saisie — et cet écran est un
> formulaire de bout en bout, donc `o` y serait entré dans le champ au lieu
> d'ouvrir quoi que ce soit. La forme retenue est celle de la **note 7** d'Egan :
> l'ouverture devient une ligne du formulaire, atteinte comme les autres.

**Pourquoi cette touche n'est pas un détail.** Le formulaire demande de recopier
ce qui est imprimé sur la planche — encore faut-il pouvoir la lire. Le papier est
souvent parti (chez le prestataire, découpé, collé) : **le scan est la seule
copie disponible**, et c'est justement le fichier que la TUI vient d'analyser.
Le chemin est aussi rendu en **lien cliquable** dans les terminaux qui le
supportent (séquence OSC 8) — un confort en plus du raccourci, jamais à sa
place : `EPIC11-ARB-11` interdit qu'un geste soit réservé à la souris.

**Pourquoi c'est possible sans image.** La planche imprime les identifiants
canoniques **verbatim** (`pdf_composition.PageTextPlan`), et l'égalité à l'octet
près avec le payload du QR **est** le mécanisme de secours de la story 4.6. La
TUI ne demande donc pas de déchiffrer un QR : elle demande de recopier un texte
imprimé, ce que l'opérateur a sous les yeux.

**Où l'on revient après avoir validé** (note 10 d'Egan, 2026-08-31, verbatim de
la disposition) : « le formulaire `E3-4b` s'ouvre pour la page non rattachée,
**une page à la fois**, puis on **revient au rapport** (`E3-4`), qui se
**recalcule**. Si la page rattachée était la dernière manquante, le rapport
devient complet (`E3-3`) et l'écriture s'ouvre. Sinon la page suivante est
proposée. »

**Le rapport se recalcule, il ne se rapièce pas**, et ce n'est pas un détail
d'implémentation : `E3-3` et `E3-4` sont deux rendus du **même** rapport, et
lequel s'affiche se lit sur sa complétude. Retrancher ici une page de la liste
des complétables écrirait une seconde règle de complétude à côté de celle du
cœur — et les deux divergeraient au premier lot dont il manque une planche
**jamais scannée**, qu'aucune saisie ne rattrape.

**Rien n'est prérempli**, et c'est délibéré : un champ deviné faux n'appelle pas
la vérification. C'est la règle du Flow 3 de la GUI, reprise sans changement.

**Ce que la TUI vérifie quand même.** La cohérence avec les pages déjà lues du
lot : une « page 4 sur 4 » déclarée alors que trois pages annoncent un total de 6
est une contradiction visible sans aucune image.

**Cas limites.**
* *Lot inconnu du projet* : accepté avec réserve `▲` — c'est peut-être la
  première page lue de ce lot. Refuser ici casserait la reconstruction depuis un
  scan seul.
* *Page déjà déclarée par une autre feuille* : refus, avec le nom du fichier qui
  l'occupe. Deux pages 4 dans un lot sont une erreur de saisie, pas un second
  tirage.
* *Opérateur qui abandonne* : la page reste en attente de lecture, nommée. Rien
  n'est écrit.

> **Coordination.** Le formulaire équivalent est en cours de développement sur la
> **GUI** (story 7.5), hors de ce worktree — Egan l'a signalé. La story TUI
> **consomme le même point d'entrée de cœur**, elle n'écrit pas une seconde règle
> de validation de payload. S'il n'existe pas encore, c'est la story GUI qui le
> pose et la TUI attend. C'est exactement la « couture entre deux stories » que
> la rétrospective de l'Epic 7 instruit.

#### `E3-5` · Temps 2 — quelle calibration

*Maquette : `maquettes/E3-5-scan-calibration.txt`*

**Il voit** les profils disponibles en liste sélectionnable (`DESIGN.md` §7.1 —
la flèche seule, aucune case : `EPIC11-ARB-126`, borné à cet écran par
`EPIC11-ARB-130`), **le curseur posé sur le profil par défaut du projet**
(`EPIC11-ARB-6`) — c'est ça, la proposition, et elle ne retient rien tant que
l'opérateur n'a pas validé —, une entrée pour désigner un autre fichier, et une
entrée « aucune » qui livre le lot brut. Sous un filet, **la
carte d'identité du profil retenu** : chaîne, date, nombre de patchs, divergence
brute mesurée.

**Il peut** changer de profil et voir la carte se mettre à jour, ou désigner un
fichier **dans l'explorateur** — `E3-5` est nommément l'un des cinq sites
d'`EPIC11-ARB-48`, et il ne saisit donc plus de chemin à la main.

**Pourquoi la carte d'identité est là.** Un nom de profil ne dit pas si le profil
est le bon. La chaîne (`hp-envy-4520 · tiff · 600 dpi · auto-corr off`) et le dpi
du scan en cours sont comparables **à l'œil**, et c'est la seule vérification que
la TUI peut offrir sans previz.

**Cas limites.**
* *Aucun profil dans le projet* : « aucune » est la seule option active, et une
  phrase renvoie à l'entrée **Calibrer une chaîne** du menu du Scan (`E3-9`) —
  par son nom d'écran, jamais par un nom de commande (`EPIC11-ARB-28`).
* *Le profil retenu a été fait à un autre dpi que le scan* : ligne `▲` sur la
  carte, nommant les deux dpi. Pas un refus — c'est un jugement d'opérateur.
* *Le fichier de profil désigné est illisible* : refus nommé, le choix précédent
  reste actif.

#### `E3-6` · Temps 2 — confirmation

*Maquette : `maquettes/E3-6-scan-confirmation.txt`*

**Il voit** frames **attendues** et frames **obtenues** sur deux lignes
distinctes — c'est la demande littérale d'Egan —, la profondeur, la calibration
retenue, le majorant disque, et les **noms de lots éditables** dont le segment
`ingest01` est le slug opérateur (`EPIC11-ARB-8`).

**Il peut** valider, modifier, annuler, éditer les noms par **`Tab`** —
`EPIC11-ARB-25` proposait `e`, qu'`EPIC11-ARB-68` a remplacé (« aucune lettre
n'est un raccourci dans un champ de saisie »). C'est ce que le produit livre
déjà : `execution.RACCOURCIS_CONFIRMATION`.

**Cas limites.**
* *Attendues ≠ obtenues* : la ligne « obtenues » passe en `state-absent`, le
  glyphe `●  toutes` devient `✕  16 manquantes`, et l'intitulé de la première
  action devient « Écrire les 170 frames obtenues ».
* *Un slug déjà utilisé dans ce projet* : refus du champ, motif nommé.
* *Slug vide* : refusé — le slug est ce qui distingue deux ingests du même lot.

#### `E3-7` · Temps 2 — écriture

*Maquette : `maquettes/E3-7-scan-ecriture-en-cours.txt`*

Même grammaire que `E2-4`. Le journal montre la correction appliquée, le recadrage
page par page, puis les frames écrites une à une. Progression en **frames**, cette
fois — c'est ce qui s'écrit.

#### `E3-8` · Temps 2 — résultat

*Maquette : `maquettes/E3-8-scan-resultat.txt`*

Même grammaire que `E2-5`, avec en plus la calibration appliquée nommée dans le
panneau : trois semaines plus tard, c'est l'information qu'on cherche.

#### `E3-9` · Calibrer une chaîne de scan

*Maquette : `maquettes/E3-9-scan-calibrate.txt`*

**Il voit** un formulaire court : le scan de la page de calibration, le dpi, le
nom de chaîne, un commentaire. Sous un filet, ce qui sera écrit, **et si ça
remplace quelque chose**.

**Il peut** générer le profil, et décider s'il devient le profil par défaut du
projet (`(•) non` par défaut — poser un défaut est une décision, pas un effet de
bord).

**Cas limites.**
* *Le même nom, la même chaîne* : ce n'est **pas** un écrasement, c'est une
  **recalibration**, et le cœur la traite comme un remplacement voulu depuis
  5.22 — « poser la question à chaque recalibration serait une invite qui apprend
  à répondre « oui » sans lire » (`EPIC5-ARB-99`). L'écran le dit, sans `▲` et
  sans question.
* *Le même nom, une **autre** chaîne* : là il y a collision, et elle ouvre
  **trois** issues — écrire sous un nom différencié (le défaut du cœur, celui
  qui n'écrase rien), écraser sciemment, annuler. Aucune n'est présélectionnée.
  Jamais une seule sortie, jamais un blocage sec (`EPIC11-ARB-89`,
  `EPIC11-ARB-128`).
* *La page scannée n'est pas une page de calibration* (patchs non trouvés) : refus
  nommé, aucun profil écrit.

---

### Palier 2 — Atelier **Pdf**

> **Section remise d'accord le 2026-09-02** avec l'atelier tel qu'il est livré :
> neuf modules `src/mixed_media_utility/tui/atelier_pdf*.py`, seize maquettes
> `E5-*`, onze arbitrages tranchés les 2026-09-01 et 2026-09-02, et une revue en
> trois couches qui a corrigé le produit. Elle avait été écrite **avant** que
> l'atelier n'existe.
>
> **Ce qui a changé se lit plutôt que se devine**, et c'est le motif de la table
> ci-dessous : un document qui décrit un produit **périme aussi vite qu'un
> arbitrage se tranche**. La fiche de la story 11.7 en porte vingt-neuf
> exemples datés, dont sept qui étaient vrais le matin et faux le soir du
> 2026-09-02. Remplacer une prose périmée par une autre sans dire laquelle
> tombe, c'est reconduire le défaut.

#### Ce que cette section disait de faux, et la mesure qui le contredit

| # | ce que cette section disait | ce qui est mesuré |
| --- | --- | --- |
| 1 | « Commandes de cœur : `mmu makepdf`, et `mmu makepdf calibration-page` » | la TUI **n'appelle pas la ligne de commande** : elle héberge `makepdf.generer_les_planches_du_lot` et `makepdf.generer_la_page_de_calibration` (`EPIC11-ARB-1`), et une frontière compte à zéro tout import de `cli` dans `tui/`. Les deux **feuilles CLI** couvertes, elles, restent bien celles-là |
| 2 | `E5-0` : « en pied, la dernière planche produite avec son gabarit » | le pied porte aussi la **date**, les **pages** et le **rang**, tous trois *dérivés* — l'inventaire (`io.pdf_manifest.SHEETS_INVENTORY_FIELD`) ne porte que le chemin et le rang. Sans rang déclaré, le pied dit `tirage d'origine` et n'en invente aucun (`EPIC11-ARB-92`) |
| 3 | `E5-1` : « chacun avec frames, cadence, géométrie et état » | **cadence et géométrie sont retirées** (Egan, 2026-09-02 : « La cadence ne joue pas sur une planche c'est le lot qui la détermine. La géométrie n'est pas réglable on ne l'affiche pas. »). La ligne porte le nom et le verdict ; les frames et la date d'extraction vivent sous le filet `Le lot survolé` |
| 4 | `E5-1` : « Sous la liste, le compte des cochés, le total de frames et les géométries concernées » | le double compte est **fermé** (note 4 du 2026-09-01) : la ligne du haut est retirée, seule la ligne d'état porte `N lots cochés · M frames`. Aucune géométrie n'est affichée nulle part |
| 5 | `E5-1` : « *Lots de géométries différentes cochés ensemble* […] l'écran de réglages le rappellera » | aucun des deux écrans ne montre de géométrie, et `atelier_pdf_reglages` **ne compare aucune géométrie** — la seule comparaison de l'atelier est la domination, calculée au cœur par `page_templates.bilan_de_domination` |
| 6 | `E5-2` : « **six** réglages — orientation, frames par page, format, marge de travail, dpi, compression de gamut » | **trois champs et un bouton** (`atelier_pdf_reglages.CHAMPS`). Le gamut est retiré (retour v5 n°1 d'Egan) ; `Format · DPI` est **affiché sans être réglable**, `page_templates.PAGE_FORMATS` n'en portant qu'un |
| 7 | `E5-2` : « sous un filet, ce qui en découle : le gabarit et le nombre de pages par lot » ; « le `template_id` reste affiché » | le bloc « Ce qui en découle » **n'existe plus** (`EPIC11-ARB-173`) : la surface de dessin et les pages vivent **sur chaque entrée** de la liste unique. Le `template_id` se lit au journal de `E5-4` et au cartouche de `E5-5`, pas ici |
| 8 | `E5-2` : « la TUI le dit et ramène **au plus proche** offert » | `EPIC11-ARB-179` (« On économise le papier ») : le repli **MONTE** vers le cardinal offert immédiatement supérieur, et il vit au cœur — `page_templates.replier_le_cardinal`. Sans cardinal supérieur offert, la fonction **refuse** au lieu de deviner |
| 9 | `E5-2` : « La ligne « Gabarit » porte le préset (`…-marge2`) » ; « une ligne `▲` sous le filet nomme les deux géométries » | il n'y a plus de ligne `Gabarit` sur cet écran, et la ligne `▲` est le **conseil inter-orientations** (`MOTIF_DU_CONSEIL`), pas un rappel de géométrie |
| 10 | `E5-2b` : ligne d'état « `▲ 6 f/page n'existe pas en portrait (surface < 8 f) — ramené à 4` » | `MOTIF_DU_REPLI` ne porte **aucune parenthèse**, et la maquette lit `ramené à 8` : la clause « même surface qu'à 8 f » est tombée avec `EPIC11-ARB-179`, qui nommait déjà `8` |
| 11 | `E5-2b` : « Le cœur porte déjà cette explication (`page_templates._retired_cardinal_reason`) : la TUI l'affiche plutôt que d'inventer sa propre phrase » | **faux, et c'est l'inverse** : `retired_cardinal_reason` n'a aucun site d'appel dans `tui/` (seul `pdf_composition` l'appelle). La TUI rédige `MOTIF_DU_REPLI`, et cet écart est *déclaré*, fondé sur un verbatim d'Egan (planche v8, note 2) |
| 12 | `E5-3` : « un nom de fichier par planche, **éditable**, avec son nombre de pages » | `EPIC11-ARB-141` a **retiré l'édition des noms** là où elle ne peut pas être effective ; les noms sont listés seuls, sans compte de pages |
| 13 | `E5-3` : « *Un PDF du même nom existe* : `E5-3b` […] et ses **trois** sorties » | deux erreurs : le conflit passe **AVANT** la confirmation (`EPIC11-ARB-172`), et `E5-3b` porte **quatre** issues (créer, remplacer, masse, annuler), `E5-3c` **trois** |
| 14 | `E5-4` : « la progression à deux niveaux — `lot 2/2 · page 3/5` » | la maquette validée lit `lot 2/2 · page 3/7`, et surtout la section ne disait pas que **l'interruption n'est constatée qu'ENTRE deux lots** — le canal du cœur est observationnel par contrat (`EPIC7-ARB-79`) |
| 15 | `E5-5` : « Panneau `Écrit`, puis les suites » | deux états de plus, `E5-5b` et `E5-5c`, avec une **bascule de zone** (`Tab champ`) entre la liste des écrits et les suites |
| 16 | `E5-6` : « sous un filet […] ce qui n'est **pas** réglable : jeu de patchs, **répétitions**, format, dpi » | le filet porte `Pastilles`, `Jeu de patchs` et `Format · DPI` — pas de « répétitions » —, et un **second filet** `Ce qui sera écrit` nomme le fichier et sa destination |
| 17 | `E5-6` : « *Nombre de patchs hors vocabulaire* : refus, vocabulaire rappelé » | **cas mort** : aucun champ de patchs n'existe. Le refus qui existe porte sur le **nom de chaîne** que le cœur ne sait pas nommer, et il se présente sur le champ, avec une issue |
| 18 | `E5-6` : « **un** parcours » à un écran | **cinq** écrans : `E5-6` → `E5-6d` (la mire existe) → `E5-6b` (confirmation) → `E5-6c` (écriture) → `E5-6e` (résultat) |
| 19 | `E5-6` : « `CALIBRATION_PAGE_BAND_PRESETS` ne contient qu'un jeu, `patches-17-v4`, **répété deux fois** » | un document **ne recopie pas** une valeur qui vit dans le code — il nomme la constante. Le jeu se lit dans `patch_presets.CALIBRATION_PAGE_BAND_PRESETS`, et les deux cardinaux affichés viennent de `patch_presets.calibration_page_patch_count` et `calibration_lattice_patch_count` |

**Ce que la TUI appelle, et ce n'est pas la ligne de commande.** L'atelier couvre
les deux feuilles `mmu makepdf` et `mmu makepdf calibration-page`
(`EPIC11-ARB-10`), mais il ne les **relance** pas : il **héberge** les deux
points d'entrée de cœur, `makepdf.generer_les_planches_du_lot` et
`makepdf.generer_la_page_de_calibration`, par `CoqueTui.executer_en_processus`
(`EPIC11-ARB-1`). Aucun module `tui/atelier_pdf*` n'importe `cli`, et une
frontière le mesure.

#### Le parcours, d'un bout à l'autre

```
E5-0 ─┬─ E5-1 ─ E5-2 ─ [E5-3b / E5-3c, un par lot] ─ E5-3 ─ E5-4 ─ E5-5
      │         (E5-2b)                                            (E5-5b, E5-5c)
      └─ E5-6 ─ [E5-6d] ─ E5-6b ─ E5-6c ─ E5-6e
```

Les crochets marquent ce qui **ne se monte que s'il y a lieu** : aucun écran de
conflit quand rien n'existe encore, pas de `E5-6d` quand la mire est neuve.
L'inversion coûte donc zéro écran dans le cas nominal.

#### Les cinq faits qui changent ce que l'opérateur vit

Ils ne sont pas des détails d'écran : ce sont les propriétés que l'atelier tient,
et sans lesquelles les écrans ci-dessous ne se lisent pas.

1. **Une planche est un objet VERSIONNABLE** (`EPIC11-ARB-104`, verbatim d'Egan :
   « Tout doit être versionnable OU écrasé. »). Relancer un lot ne détruit rien :
   ça **consomme un rang**, et le rang entre dans le nom du fichier
   (`io.naming.build_sheets_pdf_filename`), dans l'en-tête imprimé et dans le QR
   (`EPIC11-ARB-91`). Le rang d'origine, lui, n'écrit aucun fragment de nom
   (`EPIC11-ARB-88`) : `v` absent vaut 1. Et **le nom porte la mise en page**
   (`EPIC11-ARB-171`, forme `…_<Nf-ori>[_vN].pdf`), si bien que deux géométries
   du même lot ne se disputent jamais un rang — le rang se compte **par lot**
   (`EPIC11-ARB-175`), la mise en page les sépare dans le nom.

2. **Un tirage SCANNÉ ne peut plus être écrasé du tout**, et c'est le **seul
   interdit dur** de l'atelier (`EPIC11-ARB-174`, fermé par Egan le 2026-09-02 :
   « S'il est scanné on ne peut de fait pas l'écraser. »). Le motif est physique
   plutôt qu'informatique : la feuille est sortie de l'outil, elle porte son rang
   dans son QR, et deux feuilles ne peuvent pas dire le même numéro. La
   reconnaissance se fait **AU RANG**, jamais au lot (`EPIC11-ARB-176`) : c'est
   `lots[].scanned_version_ranks`, écrit par `io/scan_manifest.py`. Refuser au
   niveau du lot bloquerait un `v4` jamais imprimé au motif que le `v3` a été
   scanné — un blocage sec sur un objet innocent, ce qu'`EPIC11-ARB-89`
   proscrit.

3. **Le conflit passe AVANT la confirmation** (`EPIC11-ARB-172`, question d'Egan :
   « comment sait-on déjà que cela va être le lot 4 si on n'a pas tranché pour
   l'écrasement ou le versionnage ? »). Un écran de confirmation ne peut annoncer
   que des **faits déjà tranchés** : quand `E5-3` écrit « tirage 4 », le numéro
   est vrai, et il le sera encore sur la feuille imprimée.

4. **Le repli de cardinal MONTE** (`EPIC11-ARB-179`, verbatim : « On économise le
   papier »). Basculer d'orientation ne fait donc **jamais perdre de papier** :
   un cardinal indisponible est remplacé par le cardinal offert immédiatement
   **supérieur**, jamais par le plus proche. Ce que ça coûte est mesuré et
   assumé — la surface de dessin par frame baisse.

5. **L'exécution ne s'interrompt qu'ENTRE deux lots.** Le canal de progression du
   cœur est **observationnel par contrat** (`EPIC7-ARB-79`) : il ne peut rien
   arrêter, et promettre un arrêt à la page serait promettre ce que le cœur
   n'offre pas. `Échap` **demande** l'interruption ; elle est constatée au lot
   suivant. Ce que ça garantit en revanche est fort : le manifeste est écrit
   **par lot**, donc une passe interrompue laisse un manifeste cohérent avec ce
   qui est sur le disque, et un lot refusé n'annule pas les suivants — deux lots
   sont deux documents indépendants.

#### `E5-0` · Le menu de l'atelier Pdf

*Maquette : `maquettes/E5-0-pdf-menu.txt`*

**Il voit** deux entrées — **Composer des planches** et **Planche de
calibration** — et, sous un filet, le **dernier tirage produit** : son nom, sa
date, ses pages, son rang et son gabarit.

**Pourquoi il y a un menu.** `EPIC11-ARB-28`, verbatim : « Tout atelier qui a
plus d'une entrée commence par un menu d'atelier ». Le Pdf en a deux, comme le
Scan, et `E5-0` est la même colonne que `E3-0` à la colonne près.

**Pourquoi la planche de calibration est ici et pas dans le formulaire.** Ses
paramètres n'ont rien en commun avec ceux d'une planche de lot, et elle ne dépend
d'aucun lot. Une case à cocher dans le formulaire Pdf aurait fait apparaître des
champs sans rapport avec les autres.

**Ce que le pied ne fait pas.** Il ne **calcule** aucun rang (`EPIC11-ARB-92`) :
il le lit de l'inventaire du manifeste, et quand le manifeste n'en déclare aucun
il dit `tirage d'origine` plutôt que d'en déduire un. Les deux valeurs que
l'inventaire ne porte pas — la date et le cardinal de pages — sont dérivées,
chacune de la seule source qui les possède : les pages par
`pdf_composition.page_count_du_lot`, c'est-à-dire par le même chemin que
l'impression, la date par le fichier sur le disque. Quand aucun fichier ne
répond, le segment de date **disparaît** plutôt que de mentir.

#### `E5-1` · Quels lots mettre en planches

*Maquette : `maquettes/E5-1-pdf-lots.txt`*

**Il voit** une **liste cochable** de lots (`EPIC11-ARB-10`), chacun avec son
verdict de conformité en colonne de droite. Sous un filet, **le lot survolé** :
son cardinal de frames et sa date d'extraction, et rien d'autre.

**Il peut** cocher/décocher à l'`Espace`, valider à l'`Entrée`. C'est une liste à
cocher, donc elle porte **la case ET la flèche** — le seul endroit où les deux
coexistent (`EPIC11-ARB-45` / `-126`, verbatim : « Flèche seule ! C'est uniquement
dans les listes à cocher qu'on trouve les deux. »).

**Ce que le bloc du survol ne porte pas, et c'est un retour d'Egan du
2026-09-02** : ni cadence — « elle ne joue pas sur une planche, c'est le lot qui
la détermine » —, ni géométrie — « elle n'est pas réglable, on ne l'affiche
pas ». La remontée du lot vers `rushes[].resolution_source` qu'elles auraient
exigée n'est pas écrite : un champ qu'aucun écran ne montre est une surface
morte.

**Deux comptes, deux chemins, et le filet les sépare.** Le cardinal du filet est
celui du **lot survolé** ; le total (`N lots cochés · M frames`) est en ligne
d'état, et il somme les cochés. Le double compte de la ligne du haut a été retiré
le 2026-09-01.

**Cet écran ne juge aucun lot** (`EPIC11-ARB-30`) : le verdict vient de
`io.extraction_manifest.verify_extracted_lot`, appelé au cœur, et la TUI ne fait
que l'afficher. Elle ne rejoue ni le comptage de frames, ni la vérification des
noms de fichiers, et ne va rien compter sur le disque — tout se lit du manifeste
**déjà chargé**.

**Cas limites.**
* *Zéro coché* : `Entrée` ne fait rien, la ligne d'état le dit. Une liste
  cochable ne se valide jamais à vide en silence (`DESIGN.md` §7.2).
* *Un projet sans aucun lot* : la liste ne s'ouvre pas vide — « une liste vide
  n'est pas un choix, c'est un écran sans objet ». Le parcours **le dit** par un
  écran de refus nommé, avec la phrase du modèle et non une seconde rédaction.
* *Un lot incomplet* : **cochable**, avec le glyphe d'absence (`✕`) et la mention
  `incomplet`. C'est la confirmation, plus loin, qui dira ce qui manque.
* *Lots de géométries différentes cochés ensemble* : autorisé — chaque lot a sa
  planche, et chacune est paginée **séparément** : le papier ne se partage pas
  entre deux lots.

#### `E5-2` · Réglages des planches

*Maquette : `maquettes/E5-2-pdf-reglages.txt`*

**Il voit trois champs** — **orientation**, **marge de travail**, et la liste des
**frames par page** — plus une ligne `Format · DPI` **affichée sans être
réglable**, et un bouton `Valider`. Chaque entrée de la liste porte sa **surface
de dessin** en millimètres et en centimètres carrés, **et** son nombre de pages.

**Il peut** changer l'orientation, la marge et le cardinal, et voir la liste et
la ligne d'état se recalculer.

**UNE seule liste verticale** (`EPIC11-ARB-173`, retour v5 d'Egan). Les deux
rangées « proposés d'office » / « et aussi » n'existent plus, ni le bloc « Ce qui
en découle ». Le motif est mesuré plutôt que décoratif : `jetons.peindre` peint
**par ligne**, jamais par fragment de ligne, et son paramètre `etats` est un
jeton par rang. Du vert sur quelques puces d'une même rangée n'était donc pas
exprimable sans changer le contrat de peinture du produit ; une entrée par ligne
le rend exprimable par la règle qui existe déjà.

**Le glyphe de choix optimal et sa couleur ne font qu'UN jeton** (`DESIGN.md`
§6) : `●` vaut l'état complet — le vert — et son repli ASCII est `*`, l'astérisque
qu'Egan demande. Écrire un `*` littéral aurait fait deux fautes d'un coup : un
glyphe hors table, et une collision avec le repli de `●`. La légende dit trois
mots, `choix optimal`, et pas la définition de la mesure.

**Aucun cardinal n'est retiré de la liste** (`EPIC11-ARB-154`) : on guide, on
n'interdit pas. La liste est le vocabulaire **entier** de l'orientation, tel que
`page_templates.frames_per_page_vocabulary` le rend, dans son ordre.

**Ce module ne compare aucune géométrie.** La domination — « surface ≥ ET
pages ≤, avec au moins une inégalité stricte » — est calculée au cœur par
`page_templates.bilan_de_domination`, sur le **produit des deux orientations**, et
jamais rejouée côté TUI. C'est pourquoi la ligne `▲` du conseil survit à la liste
unique : une entrée peut être sans glyphe à cause d'une combinaison de l'**autre**
orientation, que la liste ne montre pas, et ce conseil est le seul endroit qui la
nomme.

**`⏎` sélectionne puis saute sur `Valider`** (Egan, 2026-09-02 : « appuyer sur
Entrée "saute" ensuite en dehors du choix pour valider »). La ligne de raccourcis
est contextuelle par charte (`DESIGN.md` §4) : dans un champ elle annonce
`⏎ sélectionner et Valider`, sur le bouton `⏎ valider`. La règle se **lit** à
l'écran, elle n'est pas seulement respectée.

**Ce que cet écran tranche, et ce qu'il ne tranche pas.** L'orientation **est un
champ** (`EPIC11-ARB-17`, réponse d'Egan à `Q3`) — divergence assumée avec la GUI,
où `EPIC7-ARB-48` l'a supprimée : la GUI a un aperçu vivant où l'orientation se
découvre sur l'image, la TUI n'en a pas. Le `template_id`, lui, n'est toujours
**pas** un champ, et il n'est même plus affiché ici : il se lit au journal de
`E5-4` et au cartouche de `E5-5`.

**L'ordre des champs n'est pas décoratif.** Le vocabulaire des cardinaux **dépend
de l'orientation** — le cardinal 6 est retiré en portrait, et 3 en paysage : ce
sont des mesures de géométrie (`EPIC5-ARB-62` / `-64`), pas des choix d'écran.
L'orientation se saisit donc **avant** le cardinal, et en changer refiltre la
liste offerte.

> **Le libellé est « marge de travail », pas « marge de recadrage »**
> (`EPIC11-ARB-34`, corrigé par Egan). Le second décrit ce que le logiciel en
> fait — le recadrage a lieu au scan, à l'autre bout de la chaîne ; le premier
> décrit ce que l'opérateur y met : la place qu'il se laisse pour peindre, plier,
> découper. C'est sur celle-là qu'il décide. Le mot proscrit est compté à **zéro**
> sur tout `tui/`, prose comprise.

**L'état d'ouverture est celui du cœur, jamais un nombre recopié** :
`pdf_composition.resolve_orientation(None)`,
`page_templates.DEFAULT_FRAMES_PER_PAGE`, `page_templates.DEFAULT_MARGIN_PRESET`.
Les deux maquettes dessinent un état **après réglage**, pas l'état d'ouverture :
une maquette montre un instant.

**Cas limites.**
* *Le cardinal courant n'existe pas dans la nouvelle orientation* : la TUI le
  **dit** et retient le cardinal offert immédiatement **supérieur** — écran
  `E5-2b`. Elle ne laisse jamais à l'écran un couple que le cœur refuserait, et
  elle ne change pas un réglage en silence.
* *Marge non nulle* : le nombre de frames par page ne change pas, la surface par
  frame si — et elle se lit sur chaque entrée de la liste, qui se recalcule.
* *Cardinal élevé et QR trop dense* : le cœur refuse au moment de composer
  (versions de symbole bannies, story 5.17). La TUI ne recopie pas cette règle —
  elle affiche le refus du cœur, avec son motif.

#### `E5-2b` · Le cardinal est refiltré par l'orientation

*Maquette : `maquettes/E5-2b-pdf-cardinal-refiltre.txt`*

**Il voit** le formulaire avec la valeur **déjà retenue** et le vocabulaire
**déjà refiltré**, et une seule ligne d'état qui porte le constat :
`▲ 6 f/page n'existe pas en portrait — ramené à 8`.

> **Un constat va en ligne d'état, pas en cartouche** (`EPIC11-ARB-35`, « un peu
> lourd comme avertissement. Un petit message en bas aurait suffi »). Le
> cartouche **interrompt** : il est réservé aux points où l'opérateur doit
> **décider** — le conflit de tirage, l'écrasement, l'interruption. Ici il n'y a
> rien à décider, la valeur est déjà retenue.

**Il peut** continuer avec la valeur retenue, ou repasser à l'autre orientation
pour retrouver la sienne.

**Le repli MONTE, et c'est le cœur qui le décide** (`EPIC11-ARB-179`) :
`page_templates.replier_le_cardinal` rend le cardinal offert immédiatement
supérieur. Il **refuse** plutôt que de deviner quand aucun n'est offert au-dessus
— un repli vers le bas serait un `max()` silencieux qui renverserait « on
économise le papier » sans qu'aucune décision ne l'ait dit. Ce cas est
injoignable sur les géométries livrées, et une frontière rougirait le jour où une
géométrie ferait tomber cette propriété.

> **Écart déclaré, et il est dans ce sens-là.** La phrase du repli est **rédigée
> par la TUI** (`MOTIF_DU_REPLI`), pas relayée du cœur : `retired_cardinal_reason`
> existe et explique le retrait d'un cardinal, mais elle n'a aucun site d'appel
> dans `tui/`. Ce n'est pas une dérive silencieuse — c'est un choix fondé sur la
> forme validée de la maquette (Egan, 2026-09-02 : « on laisse la ligne du bas
> avec les infos »), la ligne d'état voulant des **constats** et non des
> explications de mécanisme (`EPIC11-ARB-56`).

#### `E5-3b` / `E5-3c` · Ce tirage existe déjà — et le conflit passe AVANT

*Maquettes : `maquettes/E5-3b-pdf-tirage-existe.txt`,
`maquettes/E5-3c-pdf-tirage-scanne.txt`*

**Quand cet écran se monte.** Juste après `E5-2`, **avant** la confirmation
(`EPIC11-ARB-172`), et **un par lot en conflit** (`EPIC11-ARB-177`, réponse
d'Egan : « Par lot »), dans l'ordre par lot — l'ordre de `lots[]` serait celui de
la première création, qui ne veut rien dire pour qui tranche des conflits. Quand
aucun tirage n'existe, **aucun écran ne se monte** : l'inversion coûte zéro écran.

**Il voit** une fiche du tirage présent : son nom de fichier, son rang et son
rang relatif, sa date d'écriture, ce qu'il contient en pages, frames et
mégaoctets, sa mise en page, et la ligne **`Scanné`**.

**Un seul écran, deux états.** `E5-3b` et `E5-3c` sont le même conflit rendu par
la même classe : seule la ligne `Scanné` change, et avec elle la liste des issues.
Deux écrans séparés auraient laissé la frontière négative — « l'écrasement n'est
pas offert » — mesurer un chemin de code différent de celui qui l'offre,
c'est-à-dire ne rien mesurer du tout.

**Il peut**, quand le tirage **n'est pas** scanné (`E5-3b`) :
* **Créer la v*N*** — la sortie non destructive, et c'est elle que le curseur
  vise au montage : `ChoixExclusif` déplace le curseur hors de toute issue qui
  écrit (`EPIC11-ARB-7` / `-45`) ;
* **Remplacer ce tirage** — l'écriture destructive **consciente**
  (`EPIC11-ARB-89`), qui annonce sous elle les mégaoctets effacés ;
* **Appliquer ce choix aux *N* conflits restants** — l'issue de masse ;
* **Annuler**, qui remonte d'un palier — on revient sur ce qu'on vient de
  quitter, pas au menu.

Quand le tirage **est** scanné (`E5-3c`), `Remplacer ce tirage` **n'est pas
offert**, et la ligne d'état dit pourquoi. Le cartouche porte la phrase d'Egan,
verbatim : « Ce tirage a déjà été imprimé. Vous ne pouvez pas l'écraser car cela
pourrait causer des conflits de version. » Elle **remplace** une rédaction qui
expliquait le mécanisme du QR — trop longue, et « le mécanisme n'est pas la
raison qu'un opérateur a besoin de lire ». Le mécanisme vit dans les documents de
décision, pas à l'écran.

**L'issue de masse et ses trois contraintes** (`EPIC11-ARB-177`, « Excellente
proposition : le choix 3 ») :
1. elle **n'est jamais la première issue atteinte** ;
2. elle **nomme ce qu'elle emporte** en cardinal *et* en poids — un « appliquer
   aux 4 restants » muet sur les mégaoctets serait moins informatif que l'écran
   qu'il remplace ;
3. elle **reste une issue parmi d'autres** : les issues unitaires demeurent.

**Et elle SAUTE les tirages scannés en le disant** : le compte sauté est
**affiché** sous l'issue, jamais seulement journalisé — « un lot écarté sans que
l'écran le nomme serait une décision cachée ». Le choix appliqué est celui que
l'écran offrait : destructif quand le tirage courant est écrasable, non
destructif sinon, si bien que le chiffre annoncé sous l'issue et ce qui se produit
ne peuvent pas diverger.

**Cas limites.**
* *Les rangs sont épuisés pour ce lot* : un écran de refus prend la place, avec
  le texte du cœur relayé **tel quel**, et il offre **au moins deux** issues —
  retirer **ce lot-là** de la passe (les autres restent : perdre les *N*−1 autres
  pour un seul serait le blocage sec qu'`EPIC11-ARB-89` proscrit), annuler, plus
  l'écrasement conscient quand le tirage n'est pas scanné. La suppression d'un
  tirage pour libérer son rang — la troisième opération d'`EPIC11-ARB-89` —
  n'est **pas** offerte ici : elle n'est pas livrée, et une issue qui ne ferait
  rien serait pire qu'absente. Le texte du cœur, lui, la nomme.
* *L'issue de masse rencontre un lot aux rangs épuisés* : elle ne l'emporte pas.
  Le lot garde son conflit **non tranché**, et la file s'arrêtera dessus pour
  montrer son refus — même principe que le tirage scanné : ce qu'une masse ne
  peut pas emporter, elle le saute **en le disant**.
* *La passe est vidée de tous ses lots* : elle ne va pas confirmer une passe sans
  objet, elle ramène aux ateliers.
* *Revenir en arrière sur un conflit déjà tranché* : légitime, et c'est ce
  qu'`Annuler` promet. La file **suit l'écran** — l'écran qui parle redevient le
  courant, avec ses restants à lui.

#### `E5-3` · Confirmation

*Maquette : `maquettes/E5-3-pdf-confirmation.txt`*

**Il voit** le nombre de PDF **et** de pages, la mise en page (cardinal,
orientation, format, dpi, marge), la taille majorée, la destination, puis **un
nom de fichier par planche**.

**Le numéro de tirage y est un FAIT.** C'est tout l'objet d'`EPIC11-ARB-172` : le
conflit vient d'être tranché, donc « tirage 4 » est déjà vrai au moment où l'écran
l'écrit, et il le sera encore sur la feuille imprimée. Le nom, lui, est
**construit** par `io.naming.build_sheets_pdf_filename` et jamais rédigé ici : il
porte la mise en page (`EPIC11-ARB-171`) et le rang quand il y en a un.

**Il peut** générer, modifier les réglages, ou annuler. Les deux dernières
ramènent **aux réglages** — et pas « d'un palier » : l'inversion d'`ARB-172` a
glissé les écrans de conflit entre `E5-2` et `E5-3`, et un `remonter` d'un cran y
atterrirait sur le dernier conflit, c'est-à-dire ailleurs que là où le libellé
l'annonce, et seulement quand un conflit existait.

**Les noms ne sont plus éditables** (`EPIC11-ARB-141`) : l'édition d'un nom **se
retire là où elle ne peut pas être effective**. La ligne de raccourcis de cet
écran est donc propre à l'atelier Pdf plutôt que reprise de la constante
partagée, qui promet encore une édition retirée.

**Cas limites.**
* *Une dernière page n'est que partiellement remplie* : une ligne
  `Emplacements` le dit, avec la **répartition** — quatre vides tombant deux par
  deux dans deux PDF n'est pas la même chose que quatre vides dans un seul. Elle
  n'est posée **que s'il y a des vides** : « 0 vide » sur une passe qui remplit
  exactement ses pages serait du bruit.
* *Un lot a quitté la passe entre-temps* (refus des rangs épuisés) : la mise en
  page est **remesurée ici**, sur les lots qui restent. Elle ne se recopie pas de
  `E5-2` : la pagination s'apparie **positionnellement** aux lots, et une liste
  plus courte d'un côté écrirait les pages d'un lot sur un autre.

#### `E5-4` · Génération

*Maquette : `maquettes/E5-4-pdf-execution.txt`*

**Il voit** les planches — celle qui est écrite portant `●`, celle en cours son
état —, le journal page par page avec la version de QR effectivement produite, et
en ligne d'état la **progression à deux niveaux** (`lot 2/2 · page 3/7`) qui
remplace le compte simple (`DESIGN.md` §8).

**Le journal n'est PAS remis à zéro entre deux lots** (`EPIC11-ARB-93`), et c'est
ce qui rend nécessaire l'en-tête qui **nomme** chaque lot : sans elle, `21/21`
suivi de `1/7` se lirait comme un compte qui recule. Nommée, la rupture se lit
pour ce qu'elle est.

**Un lot refusé laisse une trace et n'arrête pas la passe.** Le refus du cœur est
inscrit au journal, nommé sur son lot, et l'écriture **continue** : deux lots sont
deux documents indépendants. Le message est celui du cœur et voyage **verbatim**
(`EPIC11-ARB-30`) — la TUI n'ajoute rien à un refus et n'en reformule aucun.

**Cas limites.**
* *`Échap` pendant la passe* : l'interruption est **demandée**, et constatée
  **entre deux lots** — voir le point 5 plus haut. Ce qui est déjà écrit reste
  écrit, et le manifeste, écrit par lot, reste cohérent avec le disque.
* *Une panne hors de la table des refus nommés* : elle **traverse**. Déguiser une
  panne inconnue en refus métier ferait lire un motif rassurant sur un bug.

#### `E5-5` · Résultat

*Maquettes : `maquettes/E5-5-pdf-resultat.txt`,
`maquettes/E5-5b-pdf-resultat-nombreux.txt`,
`maquettes/E5-5c-pdf-resultat-liste-parcourue.txt`*

**Il voit** le panneau `Écrit` — un fichier par ligne, avec ses pages et son
rang —, puis le gabarit, l'emplacement et le manifeste mis à jour. Les deux
derniers sont **dérivés des constantes du produit**
(`io.project_layout.PATCHES_DIRNAME`, `io.extraction_manifest.MANIFEST_FILENAME`)
et non recopiés : un dossier renommé au cœur renommerait la ligne avec lui.

**Il peut** ouvrir le dossier, **générer une planche de calibration** — proposée
ici parce que c'est le moment où elle sert : on imprime les deux ensemble —,
mettre d'autres lots en planches, ou revenir aux ateliers.

**Quand les écrits sont nombreux** (`E5-5b`, `E5-5c`), la liste devient une
**seconde zone navigable**, et `Tab champ` bascule de l'une à l'autre. Un seul
curseur est visible à la fois — c'est l'invariant réel d'`EPIC11-ARB-50`, qui
interdit deux curseurs simultanés et non deux zones. Dans la liste, `⏎` est
**absent de la ligne de raccourcis**, et c'est mesuré plutôt que décidé : un
fichier écrit n'est pas une issue, il n'y a rien à valider.

**Trois conclusions, trois destinations.** Rien d'écrit et un refus : l'écran de
refus, avec le message du cœur et rien d'ajouté. Rien d'écrit et une
interruption : retour au menu des ateliers (`EPIC11-ARB-13`). Au moins une
planche écrite : ce compte rendu — y compris quand un autre lot a été refusé ou
que la passe a été interrompue. **Ce qui est écrit se montre.**

#### `E5-6` à `E5-6e` · La planche de calibration

*Maquettes : `maquettes/E5-6-pdf-calibration-page.txt`, `-6b`, `-6c`, `-6d`,
`-6e`*

**C'est un parcours de cinq écrans**, pas un formulaire : régler, trancher un
conflit s'il y a lieu, confirmer, écrire, conclure. C'est une demande d'Egan,
verbatim : « conformément à la logique de tous les autres écrans qui écrivent
quelque chose ». `E5-6b` est donc **le même écran** que `E5-3` — même cadre
`À écrire`, même ordre, mêmes trois issues, même flèche posée sur celle qui
n'écrit pas — et non une seconde rédaction.

**Il voit**, à `E5-6`, **deux champs** — nom de chaîne, commentaire — puis, sous
un filet « Imposé par la fonction de calibration », ce qui n'est **pas** réglable :
le cardinal de pastilles avec sa décomposition, le jeu de patchs, le format et le
dpi. Un second filet, « Ce qui sera écrit », nomme le fichier et sa destination.

> **Le jeu de patchs n'est pas un choix** (`EPIC11-ARB-36`, trouvé par Egan : « le
> nombre de patches n'est pas un choix je crois, il dépend de la fonction de
> calibration non ? »). Vérifié : `makepdf calibration-page` n'a que `--chaine` et
> `--commentaire`. Le jeu vit dans `patch_presets.CALIBRATION_PAGE_BAND_PRESETS`,
> et les deux cardinaux affichés sont **substitués** depuis
> `patch_presets.calibration_page_patch_count` et
> `calibration_lattice_patch_count` — ce document ne les recopie pas. Une version
> antérieure de cet écran affichait `--nombre-patchs`, `--format` et `--dpi`,
> recopiés depuis `makepdf` où ils existent : **trois champs sans commande
> derrière**. `EPIC11-ARB-36` pose la règle générale — **tout champ d'un
> formulaire TUI nomme l'argument de cœur qu'il alimente** ; un champ sans
> argument est un défaut.

**Ce que la mire N'A PAS, et qui se mesure comme une absence :**
* **aucun rang de version** (`EPIC5-ARB-82`). La mire ne déclare ni rush, ni lot,
  ni cadence — elle sert **toute une chaîne de scan** —, donc elle n'a pas de lot
  dont numéroter les tirages. `E5-6d` n'offre par conséquent aucune issue « créer
  la version suivante » : sa sortie non destructive est le **changement de nom de
  chaîne**, qui entre dans le nom du fichier et écrit à côté. La ligne d'état le
  dit — `aucun rang pour cet objet` ;
* **aucun poids annoncé.** `E5-3` porte un majorant parce qu'un majorant de
  planches se calcule ; personne n'a pesé une mire, et l'inventer serait la
  valeur qui a l'air juste — la pire des deux erreurs (`DESIGN.md` §3) ;
* **aucune durée, aucun « reste ~ 3 s »** (`EPIC7-ARB-67` : pas de temps rendu
  tant qu'aucune mesure n'existe) ;
* **aucune barre, et aucun journal**, à `E5-6c`. Egan l'a demandé puis validé :
  « je crois qu'il n'y aura rien à voir côté journal, non ? ». Il avait raison, et
  c'est mesuré sur le chemin de production — entre le démarrage et la ligne
  d'écriture, **aucun appel de journalisation n'existe**. Le canal du cœur émet un
  jalon **par page**, et une mire tient sur une page : la seule barre alimentable
  aurait deux états, 0 % puis 100 %. Ce qui reste est une attente honnête — un
  rotor, la ligne du fichier, et une ligne d'état qui ne dit que ce qui est su.

**Pourquoi c'est un parcours et pas une case.** C'est la lettre d'Egan (« c'est un
parcours à part ! ») et c'est vrai dans le cœur : `makepdf calibration-page` est
une sous-commande distincte, avec ses propres arguments. Une case à cocher dans
le formulaire Pdf aurait fait apparaître des champs sans rapport avec les autres.

**Cas limites.**
* *Une mire du même nom existe* : `E5-6d`, et **jamais une seule issue, jamais
  zéro** — changer le nom de la chaîne (la sortie non destructive, sous le
  curseur au montage), remplacer cette mire (l'écriture destructive consciente
  d'`EPIC11-ARB-89`), annuler. `Remplacer` passe **par la confirmation** comme
  l'autre : une écriture qui sauterait le point de jugement parce qu'elle a déjà
  traversé un avertissement en ferait deux, pas un.
* *Le nom du fichier est trop long pour 80 colonnes* (le cas réel : les noms de
  chaîne sont longs) : tronqué **au milieu** avec `…`.
* *Le libellé de chaîne est innommable par le cœur* : le refus se présente **sur
  le champ**, avec une issue, et le message est celui du cœur. Un appelant qui
  monterait l'écran d'écriture sans passer par le formulaire trouve le même refus
  relayé tel quel, plutôt qu'une chute hors de la boucle d'événements.
* *Aucun profil encore produit pour cette chaîne* : sans objet ici — cette planche
  se génère **avant** tout scan, c'est elle qui rend la calibration possible.

---

### Palier 2 — Atelier **Exports**

Commande de cœur : `mmu encode`.

#### `E4-1` · Quel lot encoder

*Maquette : `maquettes/E4-1-exports-lot.txt`*

**Il voit** **les lots reconstruits seulement** — un lot extrait ne s'encode pas —
avec frames, cadence, profondeur, état. Sous un filet, la carte du lot désigné :
depuis combien de planches il a été reconstruit, **sa cadence source lue au QR**,
sa géométrie.

**Pourquoi la cadence source est mise en avant.** C'est le climax du Flow 2 de la
GUI : le master s'écrit à la bonne cadence *sans que l'outil ne demande rien*,
parce que le payload 2.1 la porte. La TUI ne peut pas montrer ce climax, mais elle
peut **montrer qu'elle la connaît**.

**Cas limites.**
* *Le lot ne porte pas sa cadence source* (planche imprimée en payload 2.0) : la
  carte affiche `✕ cadence source inconnue`, et l'écran de réglages exposera un
  champ obligatoire — c'est `--cadence-source` de la CLI. **C'est exactement le
  coup de téléphone que 2.7 supprime**, et la TUI doit le dire comme tel.
* *Lot incomplet* : sélectionnable avec `✕`. La confirmation exigera le
  consentement (`--accept-incomplete-lot`), et rappellera qu'aucun trou n'est
  comblé par répétition de l'image précédente.
* *Aucun lot reconstruit* : liste vide explicite, renvoyant à l'atelier Scan.

#### `E4-2` · Réglages d'encodage

*Maquette : `maquettes/E4-2-exports-reglages.txt`*

**Il voit** trois lignes communes — profil, résolution, et **la cadence du
master en lecture seule** (`EPIC11-ARB-31`) — puis,
**sous un filet titré du nom du profil**, les réglages propres à ce profil, et le
nom du master.

**Les sept profils s'ouvrent en liste déroulée** sous le champ (`EPIC11-ARB-33`),
chacun avec sa catégorie (`mezzanine` / `diffusion`) et son conteneur ; le champ
fermé n'affiche que le retenu, marqué `▾`. Ce n'est pas un motif de plus : c'est
la liste sélectionnable du `DESIGN.md` §7.1, posée sur un champ.

**Le nom du master s'édite par `e`**, depuis cette ligne — la touche y est
désormais visible, alors qu'elle n'existait qu'au panneau de confirmation, deux
écrans plus loin.

> **Pas de profil personnalisé en v1** (`EPIC11-ARB-33`, condition posée par Egan
> lui-même : « si pas compris dans la CLI on laisse tomber en v1 »).
> `codec_profiles.PROFILES` est un dictionnaire **figé dans le code**, et
> `--profile` a pour `choices` la liste triée de ce dictionnaire : aucune commande
> n'enregistre un profil. Il n'y a donc rien à exposer, et un registre de profils
> utilisateur serait une story de cœur.

**Il peut** changer de profil et voir **le bloc du bas se remplacer entièrement**
(`EPIC11-ARB-9`) : un profil ProRes ne montre pas un débit cible, un profil h264
ne montre pas de variante ProRes. Aucun champ inerte à l'écran.

**Les 7 profils** sont ceux du registre (`codec_profiles.PROFILES`) et rien
d'autre : `prores_hq` (défaut), `prores_422`, `prores_lt`, `dnxhr_hq`,
`dnxhr_hqx`, `h264_delivery`, `hevc_delivery`. **Les résolutions** sont
`hd1080` (défaut), `uhd2160`, `native`, ou une saisie `<largeur>x<hauteur>`.

**Cas limites.**
* *Résolution personnalisée* : acceptée en saisie libre ; les règles de parité de
  dimension du codec s'appliquent et un refus nomme la contrainte.
* *`native` sur un lot reconstruit* : prend la géométrie des frames rescannées,
  affichée à côté pour que l'opérateur sache ce que ça vaut.
* *Nom de master trop long* : tronqué au milieu à l'affichage, jamais à l'écriture.

> **La cadence n'est pas un champ en v1** (`EPIC11-ARB-31`). `encode` n'a
> **aucune** option de cadence cible : le master prend le `fps_target` du lot, et
> `build_encode_command` pose délibérément la même valeur en entrée et en sortie
> d'ffmpeg (« le contrôle de cardinal ne vaut que si elles sont égales »).
> `EPIC11-ARB-9` promettait une cadence « modifiable » — c'était ma faute de
> l'avoir consignée sans vérifier qu'une commande la servait.

#### `E4-2b` · **Écran cible** — la cadence est modifiée *(dépend de 10.9)*

*Maquette : `maquettes/E4-2b-exports-cadence-modifiee.txt`*

**Il voit**, dès que la cadence du master s'écarte de la cadence source, un
cartouche `▲` qui **constate** le fait et donne **les deux durées côte à côte** —
cadence source et durée correspondante, cadence demandée et durée correspondante,
à nombre de frames égal.

**Il peut** continuer, ou remettre la cadence du lot d'une touche (`r`).

> **Cet écran n'est pas livrable en v1** et son bandeau le dit. Il documente ce
> que l'écran devra montrer le jour où la capacité existera : les deux cadences,
> **les frames écrites de part et d'autre** (62 contre 124) et la durée
> **conservée** — car c'est la durée, et non la cadence, que la duplication
> préserve. Le comportement qu'Egan décrit est réel : ffmpeg duplique bien les
> frames quand les cadences diffèrent (mesure citée dans
> `build_encode_command` : « `-r 25` en entrée et `-r 50` en sortie donnent
> `nb_frames=8` pour une liste de 4 »). C'est le dépôt qui l'interdit
> aujourd'hui, pas ffmpeg. La capacité est une **story de cœur** (10.9), pas une
> story de TUI — l'écrire dans l'interface serait ce qu'`EPIC11-ARB-30`
> interdit.

**Pourquoi cet écran existe.** `EPIC11-ARB-9` : la cadence est préremplie mais
**modifiable**, et le préréglage ne doit pas devenir un verrouillage silencieux.

**Ce qu'il ne dit pas, et c'est délibéré** (`EPIC11-ARB-30`). Une version
antérieure écrivait « le mouvement est ralenti d'un facteur 2 : c'est un choix
d'animation, pas une correction technique ». **Le cœur ne dit pas cela** — la
seule mise en garde structurée d'`encode` est `source_rate_override_note`, qui
concerne `--cadence-source`, pas l'écart entre cadence cible et cadence source.
L'avertissement sur la durée des animations est attendu de la story **10.9**,
qui est au backlog. La TUI **constate** donc ce qu'elle sait calculer — deux
cadences, deux durées, un nombre de frames — et **n'invente pas** une règle
métier que le cœur ne porte pas encore. Quand 10.9 arrivera, c'est son message
qui s'affichera ici.

**Cas limites.**
* *Cadence accélérée* : même cartouche, avec « accéléré » et la durée raccourcie.
* *Le lot ne portait pas de cadence source* : pas d'avertissement possible — il
  n'y a rien à comparer. Le champ `Cadence source` est alors requis, et c'est lui
  qui porte l'attention.

#### `E4-3` · Confirmation

*Maquette : `maquettes/E4-3-exports-confirmation.txt`*

**Il voit** le profil déplié en clair (`prores_hq · ProRes 422 HQ · bt709`), la
résolution en pixels, le compte de frames avec l'état du lot, la cadence **avec la
mention `= cadence source du lot`** quand elles coïncident, la durée calculée, la
taille majorée, le nom éditable et la destination.

**Cas limites.**
* *Cadence ≠ source* : la ligne devient `▲ source du lot : 25 fps` et la durée
  porte la comparaison.
* *Lot incomplet* : ligne `✕`, et l'intitulé de la première action devient
  « Encoder le lot incomplet (124 frames sur 140) ».
* *Master du même nom* : `T4-1`.

#### `E4-4` · Encodage · `E4-5` · Résultat

*Maquettes : `maquettes/E4-4-exports-execution.txt`,
`maquettes/E4-5-exports-resultat.txt`*

Même grammaire que les autres ateliers. Le journal montre la réinjection des
métadonnées et la cadence source lue au manifest — les deux choses qui, si elles
manquaient, produiraient un master silencieusement faux. Le résultat propose
**ouvrir le dossier** et **ouvrir le fichier**, les deux actions qu'Egan a
demandées (`EPIC11-ARB-13`), sans quitter la TUI.

---

### Écrans transverses

#### `T1-1` · Aide d'un champ

*Maquette : `maquettes/T1-1-aide-champ.txt`*

`F1` sur un champ ouvre un cartouche **au-dessus du formulaire**, sans le quitter.
Il dit : ce que le champ attend, les formes acceptées, les raccourcis, et **une
valeur du contexte courant** (« la cadence source du rush est 25 fps »). C'est ce
dernier point qui distingue une aide utile d'une paraphrase du libellé.

#### `T1-2` · Manuel

*Maquette : `maquettes/T1-2-manuel-raccourcis.txt`*

`F1` hors champ ouvre le manuel : **tous** les raccourcis, ceux qui valent
partout puis ceux qui sont propres à un écran (`a` ajouter une cadence, `e`
éditer les noms, `r` retrouver un rush). Paginé, `Échap` referme, on revient où
on était (`EPIC11-ARB-14`).

> **Le schéma des trois paliers en sort** (`EPIC11-ARB-37`, « la précision sur les
> paliers est de trop non ? »). L'architecture **se pratique** : `Échap` remonte,
> et on l'apprend en le faisant. La décrire occupait, avec une abstraction, la
> place des raccourcis qui ne s'apprennent pas seuls. `EPIC11-ARB-2` reste vrai ;
> il n'a pas à être **affiché**.

#### `T3-1` · Journal complet

*Maquette : `maquettes/T3-1-journal.txt`*

`Tab` pendant une exécution. Le journal occupe la zone centrale entière ; **la
ligne d'état continue de porter la progression**. On peut défiler, sauter au début
ou à la fin, copier. `Tab` revient à l'écran d'exécution.

Le journal est le **canal brut** : il porte ce que le cœur émet, y compris les
lignes que l'écran d'exécution résume. C'est là qu'on va quand le résumé ne suffit
pas.

#### `T4-1` · Écrasement

*Maquette : `maquettes/T4-1-ecrasement.txt`*

**Il voit** ce qui existe déjà : quand ça a été écrit, ce que ça contient, **et ce
qui en dépend** (« référencé par 1 planche PDF, 1 master encodé »). Puis la phrase
qui dit ce qu'écraser fait vraiment, et ce que ça ne fait **pas** (les artefacts
dérivés ne sont pas regénérés).

**Il peut** écraser, écrire sous un autre nom (champ prérempli avec un suffixe),
ou annuler. **Aucune issue présélectionnée.**

C'est la confirmation « en propre » qu'`EPIC11-ARB-4` exige en plus de la
confirmation nominale : elle n'est pas absorbée par le panneau chiffré.

> **Cet écran n'est PAS celui de l'atelier Pdf** (précision du 2026-09-02, pour
> fermer une lecture que sa mention « 1 planche PDF » invite). Un tirage qui
> existe déjà se tranche à `E5-3b` / `E5-3c`, et les deux écrans ne proposent pas
> la même chose : ici on écrit **sous un autre nom**, là-bas on **consomme un
> rang** — le versionnage est le même mécanisme partout, écrit une fois dans
> `io/version_ranks.py` (`EPIC11-ARB-104`, `-108`). Et là-bas une issue peut
> **disparaître** : l'écrasement n'est pas offert sur un tirage scanné
> (`EPIC11-ARB-174` / `-176`), ce que `T4-1` ne connaît pas. `T4-1` reste l'écran
> de l'Extraction, hors du périmètre de la story 11.7.

#### `T5-1` · Refus nommé

*Maquette : `maquettes/T5-1-refus-nomme.txt`*

**Il voit** le **code** en clair (`DPI_DECLARE_INCOHERENT`), puis la phrase qui
l'explique avec les chiffres réels, puis **ce qui n'a pas été écrit et ce qui est
conservé**. Puis des suites concrètes, pas un « OK ».

**Le code est affiché, pas seulement la phrase.** C'est ce que la story 5.27
énumère, c'est ce qu'un opérateur peut chercher dans la documentation, et c'est ce
qu'il peut recopier dans un message. Une TUI qui traduit tout en prose rend son
diagnostic incommunicable.

#### `T6-1` · Interruption

*Maquette : `maquettes/T6-1-interruption.txt`*

`Échap` pendant une exécution.

**Il voit** combien est déjà écrit, ce qu'interrompre laisse sur le disque, et
**ce qui reste valide** (le document de détection, pour le Scan — reprendre ne
redemande pas de détecter).

**Il peut** interrompre en gardant, interrompre en effaçant, ou reprendre.
**L'exécution continue tant que rien n'est choisi** : ouvrir cet écran n'arrête
rien.

---

## 6. Parcours de bout en bout

Les quatre parcours d'Egan, joués sur les écrans ci-dessus. Ils servent à vérifier
que l'enchaînement tient, pas à redécrire les écrans.

### Parcours A — Opérateur Extraction, tâche quotidienne

`E0-1` (projet_demo est en tête, `Entrée`) → `E1-1` (Extraction) → `E2-1`
(`rush_01`) → `E2-2` (`s` puis `; ` puis `2` → deux cadences ; borne d'entrée au
timecode) → `E2-3` (186 frames, 3,1 Go, deux noms de lot — il en raccourcit un par
`e`) → `E2-4` (2 min 41) → `E2-5` (`Échap`) → `E1-1`.

**Ce qu'il n'a pas eu à savoir :** le nom des options `--fps`, `--in`, `--project`,
ni que deux cadences se passent en deux invocations de la CLI.

### Parcours B — Opérateur Scan, terrain, hors ligne

`E0-1` → `E1-1` (Scan) → `E3-1` (dossier du prestataire, 600 dpi) → `E3-2`
(24 pages ; il voit passer un QR non décodé) → `E3-4` (un lot incomplet ; il
choisit **Corriger**) → `E3-1` (il ajoute la page rescannée) → `E3-2` → `E3-3`
(complet) → `E3-5` (profil par défaut, il vérifie que le dpi de la chaîne est bien
600) → `E3-6` (186 attendues, 186 obtenues ; il change `ingest01` en `ingest_hiver`)
→ `E3-7` → `E3-8`.

**Le point dur, et il est tenu :** entre `E3-2` et `E3-4`, **rien n'a été écrit**.
La détection est un livrable en soi, et le retour à `E3-1` ne perd pas les 23
pages déjà détectées.

### Parcours C — Fin de chaîne, encodage

`E0-1` → `E1-1` (Exports) → `E4-1` (lot reconstruit ; il lit que la cadence source
est connue) → `E4-2` (`prores_hq`, `hd1080`, cadence laissée à 25) → `E4-3` →
`E4-4` → `E4-5` (ouvrir le fichier).

**Variante qui compte :** s'il passe la cadence à 12,5, `E4-2b` s'interpose et lui
dit que la durée double. Il peut continuer — mais pas sans l'avoir lu.

### Parcours D — Planches

> **Remis d'accord le 2026-09-02**, comme la section de l'atelier Pdf. Trois
> passages étaient devenus faux : les noms de `E5-3` n'y sont plus éditables
> (`EPIC11-ARB-141`), la progression lit `page 3/7` sur la maquette validée, et
> surtout **l'écran de conflit manquait au parcours** alors qu'il en est
> l'étape la plus lourde depuis `EPIC11-ARB-172`.

`E0-1` → `E1-1` (Pdf) → `E5-1` (il coche deux lots) → `E5-2` (il pose une
orientation et un cardinal, et lit sur chaque entrée ce que ça donne en surface
de dessin et en pages) → **`E5-3b`** (le premier lot a déjà un tirage ; il crée
la version suivante plutôt que d'écraser) → `E5-3` (deux PDF, et le numéro de
tirage y est déjà un fait) → `E5-4` (`lot 2/2 · page 3/7`) → `E5-5` →
**« générer une planche de calibration »** → `E5-6` → `E5-6b` → `E5-6c` →
`E5-6e`.

**L'enchaînement qui a du sens :** la planche de calibration est proposée **au
résultat**, parce que c'est au moment d'imprimer qu'on en a besoin — pas comme une
case cochée vingt minutes plus tôt.

**Le point dur, et il est tenu :** l'opérateur ne découvre pas au dernier écran
qu'il va écraser quelque chose. Le conflit se tranche **avant** la confirmation,
un lot à la fois, et ce que la confirmation annonce — le numéro de tirage, donc
le nom du fichier, donc ce qui sera imprimé sur la feuille — est déjà vrai quand
il le lit.

**Variante qui compte :** si le tirage présent a déjà été **scanné**, c'est
`E5-3c` qui s'interpose, et `Remplacer` n'y est **pas offert**. C'est le seul
endroit de toute la TUI où une issue destructive disparaît au lieu d'être
avertie — parce que la feuille est sortie de l'outil et que deux feuilles ne
peuvent pas dire le même numéro.

---

## 7. Plancher d'accessibilité

Repris de la GUI, adapté à ce que la TUI peut garantir.

* **Aucune information portée par la couleur seule.** Chaque état a son glyphe
  (`DESIGN.md` §6). Vérifiable : un rendu `--sans-couleur` doit rester
  interprétable écran par écran.
* **Aucun geste réservé à la souris**, en v1 comme après (`EPIC11-ARB-11`).
* **Repli ASCII** pour les terminaux sans UTF-8 (`--ascii`) : le sens ne change
  pas, seul le dessin change.
* **Le focus est toujours visible** — `▸` sur une ligne, `>` sur un champ. Un
  écran sans marque de focus est un défaut.
* **Rien ne clignote, rien ne tourne.** Pas de *spinner* : un compte qui n'avance
  pas est une information, un sablier qui tourne n'en est pas une
  (`DESIGN.md` §9).
* **Le contraste** hérite des jetons GUI, qui tiennent le plancher 4,5:1 mesuré.
  La TUI n'impose pas le fond du terminal : c'est la limite honnête de cette
  garantie, et c'est pourquoi les glyphes sont obligatoires.

---

## 8. État des arbitrages — tous tranchés

Les sept questions de `arbitrages-epic-11-a-trancher.md` ont reçu la réponse
d'Egan le 2026-08-27, consignées en `EPIC11-ARB-15` à `21`. Ses deux annotations
manuscrites sur les maquettes ont donné `EPIC11-ARB-22` et `23`.

| Question | Réponse | Ce que ça a changé ici |
|---|---|---|
| `Q1` framework | `b` — `textual`, après une démo jetable | rien sur ces écrans |
| `Q2` persistance | `c` — la liste des récents, rien d'autre | l'historique sort de la v1 |
| `Q3` orientation | **`c`** — l'orientation redevient un champ | **`E5-2` redessiné**, `E5-2b` ajouté |
| `Q4` périmètre | `b` — + un palier « Projet » | le palier existe, à **deux** commandes (voir `ARB-23`) |
| `Q5` parité CLI | `a` + `c` optionnel | reformulé en contrat d'artefact, mesurable |
| `Q6` métrique | jugement humain + couverture CLI | aucune AC d'ergonomie ; la couverture est le chiffre |
| `Q7` grille | `a` — 80 × 24, « si c'est réaliste » | **vérifié** : 38 maquettes, 0 défaut |
| note `E0-3` | la TUI crée un projet | **`E0-4` ajouté**, `E0-3` devient une bifurcation |
| note `E1-1` | `relink` hors TUI | palier Projet à 2 commandes ; `E2-1` nomme la commande |
| note `E2-2` | cadences en liste cochable, previz puis extraction | **`E2-2` refait**, `E2-2b` et `E2-2c` ajoutés |
| note `E2-3` | comment édite-t-on, et quelle limite | **`E2-3b` et `E2-3c` ajoutés** ; la limite est 48, refus et non troncature |
| note `E3-1` | fichier seul ou dossier ? | complétion mixte ; **`E3-1b` ajouté** |
| note `E3-2` | et si le QR n'est pas décodé ? | **`E3-4b` ajouté** — la complétion entre dans la TUI |
| note `E3-9` | comment entre-t-on ici ? | **`E3-0` et `E5-0` ajoutés** ; « parcours à part » retiré de l'interface |
| note `E3-4` | « corriger » doit compléter le QR | 2ᵉ issue refaite ; `E3-4b` entre au parcours nominal |
| note `E3-6` | mécanisme d'édition du nom | ligne d'état explicite, même règle qu'`E2-3b` |
| note `E4-2b` | ce message vient-il de la CLI ? | **non** — cartouche réécrit sur des faits calculables, et `EPIC11-ARB-31` |
| approbations | `E2-4`, `E2-5`, `E3-3`, `E3-5`, `E3-7`, `E3-8`, `E4-1` | rien à changer |

**La réserve la plus lourde de cette passe n'est pas dans le tableau** : la
prévisualisation d'`E2-2b` ouvre une fenêtre `cv2.imshow`, qui **ne peut pas
s'ouvrir en SSH sans X11**. Le mode mesuré (`--no-display`) existe et le parcours
tient, mais **le jugement visuel n'est disponible qu'en local**. C'est la seule
promesse du document de vision qui se dégrade selon le contexte de déploiement,
et elle se dégrade précisément dans celui qui justifiait la TUI.

**Reste un point, qui ne bloque rien** : `scan` seul (l'ingestion en une passe de
la story 5.1) n'est **pas exposé**, parce que deux chemins de scan dans la même
TUI contrediraient `EPIC11-ARB-6`. Couverture : **11 feuilles CLI sur 13**, plus
la création de projet qui n'en est pas une.
