# Découverte UX — Epic 7 (Application GUI)

> Notes de discovery du 2026-08-16, session avec Egan. Ce document capture les
> intentions d'Egan telles qu'exprimées, sans interprétation. Le canon décisionnel
> est le memlog (`.memlog.md`); ce fichier est un instantané lisible des pistes.
> À consolider dans les spines DESIGN.md / EXPERIENCE.md à la Finalize.

## Directions posées par Egan (verbatim condensé)

### Structure de l'application

- L'interface se découpe en **4 blocs fonctionnels** → vraisemblablement **4 onglets** :
  1. **Extraction** (Epic 3)
  2. **Pdf** (Epic 4)
  3. **Scan** (Epic 5)
  4. **Exports** (Epic 6)
- Modèle de travail revendiqué : **Resolve** (DaVinci Resolve) — on travaille
  onglet par onglet pour construire la solution.
- **En amont** des 4 onglets (mais en aval dans notre travail UX) : une
  interface dédiée à la **gestion de projet**.

### Philosophie d'expérience

- L'UX **guide l'utilisateur pas à pas**, sans exposer trop de paramètres
  techniques.
- **Choix par défaut** systématiques.
- Le paramétrage avancé vit dans une section **Préférences** (éventuelle).
- À chaque étape, l'utilisateur doit pouvoir :
  - **sélectionner des images**,
  - **corriger des détections**,
  - **prévisualiser les résultats**.
- À chaque étape, l'outil **donne à voir le processus et/ou le résultat**
  (logique "previz", contrats de données déjà écrits en 3.5 / 4.9 / 5.8 / 6.4 —
  pas encore d'interface).

### Contraintes de plateforme

- Compatibilité **macOS** (minimum macOS 11 si possible) et **Windows** natifs.
- **GUI native préférée**.
- Repli acceptable : interface **web livrée par le navigateur système**
  (Chrome / Edge / autre navigateur installé), ou la vue web native d'Apple
  (WKWebView — le "navigateur natif, pas iOS" évoqué).
- **Choix de technologie à trancher APRÈS** l'UX visée (non figé nulle part à ce
  jour dans le dépôt — vérifié par les épics précédents).

## Utilisateur cible (tranché le 2026-08-16)

- **Utilisateur final = l'artiste (cinéaste), autonome.** Pas d'opérateurs
  séparés (impression/scan). L'outil sert un **projet de film précis** : la
  cinéaste travaille avec ses monteuses ; Egan peut assister mais vise
  l'autonomie de la cinéaste sur son travail.
- **Ouverture grand public à terme** (ouverture du dépôt) : l'outil s'adresse à
  toutes celles et ceux qui veulent travailler à partir de rushes imprimés sur
  papier.
- **Collaboratif à terme** : Egan doit pouvoir ouvrir les projets de la cinéaste
  **même sans les rushes natifs** — fonctions éventuellement dégradées, mais avec
  la possibilité de **reconstruire des rushes à partir de simples scans** (cas
  déjà prévu par le brief : scan sur machine B sans le projet d'origine). Les
  labos pourraient à terme effectuer ce travail, mais l'outil vise le travail
  autonome.
- Stakes : **interne → consommateur** — outil de travail pour un projet précis,
  destiné à être ouvert au public ; pas de domaine régulé.

## Ordre de travail (tranché le 2026-08-16)

- Fondations & IA globale d'abord, puis **onglet par onglet dans l'ordre du
  workflow** : Extraction → Pdf → Scan → Exports.

## Questions en attente

- Niveau de granularité des paramètres exposés par défaut vs. préférences ?
- Le registre local de projets (liste stockée sur l'hôte) : format et emplacement
  (fichier de config utilisateur ? base légère ? index dérivé ?).

## IA globale (tranchée le 2026-08-16)

- **Navigation : onglets en bas, à la manière de Resolve.**
- **Panneau latéral actionnable** pour la progression des actions en cours
  (un export, un scan, une génération PDF) — visible/ouvrable depuis les 4
  ateliers.
- **Projet = un film = un dossier cible** choisi par l'utilisateur, dans lequel
  les médias et artefacts sont rangés (modèle du manifest : `project_id`,
  `rushes[]`, `lots[]`).
- **Écran de gestion de projet TOUJOURS montré au lancement**, avec le **dernier
  projet ouvert en tête de liste**.
- **Liste des projets stockée sur l'hôte** (registre local) car les projets
  peuvent être placés dans des dossiers distincts — l'app doit pouvoir les
  retrouver et les lister.

### Atelier Extraction (tranché le 2026-08-16)

- L'atelier commence par **ouvrir un rush** : déjà chargé dans le projet, ou
  **nouveau rush à ajouter**.
- **Chutier à gauche** : liste des rushes du projet, avec possibilité d'en
  ajouter.

### Langue (i18n, tranché le 2026-08-16)

- Interface conçue **multi-langue, extensible**. Priorité : **anglais (défaut)**
  et **français**.
- Terminologie : on garde les termes français évoqués par Egan (Exports pour
  l'onglet encode) mais la langue par défaut de l'UI est l'anglais.

## Atelier Extraction — flux détaillé (tranché le 2026-08-16)

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ [Chutier rushes]  │  ATELIER EXTRACTION                              │
│ ───────────────── │                                                 │
│ ▸ rush_plan_12    │  Infos du rush (en haut) : source, résolution,   │
│   rush_closeup    │    cadence, durée                                │
│ [+ Ajouter]       │  ──────────────────────────────────────────────  │
│                   │  Fenêtre de prévisu (2 modes, boutons au-dessus) │
│                   │  ──────────────────────────────────────────────  │
│                   │  Bus de transport (bas de la prévisu)            │
│                   │  ──────────────────────────────────────────────  │
│                   │  Paramètres (en bas) : cadences, espace couleur, │
│                   │    résolution                 [Extract ⟶]        │
└──────────────────────────────────────────────────────────────────────┘
```

### Détail

- **Infos du rush en haut** : source, résolution, cadence, durée.
- **Prévisualisation — 2 modes** actionnés par deux boutons au-dessus de la
  fenêtre :
  - **Mode vidéo** : lecture à différentes cadences choisies dans les
    paramètres.
  - **Mode galerie** : toutes les images sélectionnées pour une cadence donnée.
    Barre de **zoom** pour ajuster la taille des miniatures. Clic sur une
    miniature = image en grand, **timecode affiché AU-DESSUS** (pas sur
    l'image), bouton retour à la galerie.
- **Bus de transport** (en bas de la prévisu, en fait partie intégrante) :
  lecture, pause, avancer, reculer, avancer d'une frame, reculer d'une frame,
  lecture en boucle, volume/mute, sélection de points **in/out** sur le média
  (champ timecode remplissable précisément), **marqueurs**. **Flèches sur les
  côtés** pour passer d'une cadence à l'autre (équivalent next/previous).
- **Mode galerie — frames supprimées** : un toggle (INACTIF par défaut) affiche
  les frames supprimées en grisé, sélectionnées en normal — on voit tout ce qui
  saute.
- **Paramètres (en bas)** :
  - **Liste des cadences** : défaut = cadence originale ; ajout facile
    cadence/2, /3, /4, /5 (affichés en nombres réels à virgule) ; bouton pour
    fréquences personnalisées.
  - **Espace couleur du rush** : détecté automatiquement, modifiable
    manuellement.
  - **Résolution du rush** : a priori résolution native.
  - **Profondeur** : 16 bits par défaut, 8 bits possible.
  - **Bornes in/out** : exprimées dans la barre de transport (timecode).
- **Bouton Extract en bas à droite, bien visible** :
  - Au lancement, une **fenêtre de confirmation** liste les cadences retenues
    avec **cases à cocher**.
  - On peut lancer **plusieurs extractions en une passe** (même bornes in/out),
    sans relancer plusieurs fois.

### Réponses aux 5 points de cadrage (2026-08-16)

1. **Base de timecode** = celle du rush. Modifiable via **clic droit sur le rush
   dans le chutier** (propriété du rush), pas dans la previz ni les paramètres.
2. **Politique d'arrondi** = partie de la fonction, pas un choix utilisateur.
   Non exposée.
3. **Métadonnées source** dans le panneau de réglage en bas, préremplies par
   défaut d'après le rush, modifiables. Si une métadonnée **essentielle**
   manque : champ en **rouge**, extract bloqué tant que non complété
   manuellement.
4. **Lots nommés automatiquement** : nom du rush + cadence + **hash** dépendant
   des points in/out. Pas de raison de réextraire un lot existant : **invite
   explicite** demandant l'écrasement le cas échéant.
5. **Marqueurs** = repères sur le média : **ponctuels ou plages de durée**, avec
   **couleur, nom, description**. Permettent de préparer plusieurs zones pour
   des in/out à lancer en plusieurs extractions. **Feature future différée :
   les faire apparaître sur les planches PDF** (à consigner au deferred-work).

### Fenêtre de confirmation & exécution (2026-08-16)

- **Fenêtre de confirmation OK** : cases cochées par défaut sur les cadences
  ajoutées. **L'erreur de lot existant s'affiche AU MOMENT de cliquer
  "extraire les lots"**, pas dans la fenêtre.
- **État/progression/résultats** : **carte dédiée + barre de progression PAR
  LOT**. Sur la carte, dans l'ordre : le nom de la fonction ("extract" — même
  logique pour chaque fonction aval), le nom du lot, puis la progression
  (frames/total, temps passé et restant).
- **Lot extrait et validé** : passe en **VERT** + bouton pour l'ouvrir.
- **Destination des lots** : ils ne s'ajoutent PAS au chutier rushes — ils
  s'ajoutent au **chutier "lots" de la page Pdf**.
- **Arborescence automatique** créée par l'appli dans le dossier de travail :
  les **rushes ne sont pas copiés** (chemin source gardé comme référence) ; le
  chutier "lots" est construit à partir du **dossier "frames"** fabriqué par mmu.
- **Exécution en arrière-plan** : les extractions se font toujours en
  arrière-plan ; on peut basculer d'une page à l'autre sans perdre le travail en
  cours. Progression suivie dans le **panneau latéral**.

### Double chutier & navigation (2026-08-16)

- **Chutier rushes** : les lots apparaissent **à titre informatif** sous leur
  rush, comme un arbre (rush → lots par cadence). Cliquer dessus **n'ouvre pas
  ici** — ça ouvre dans la **page Pdf**.
- **Page Pdf** : on travaille **toujours au sein d'un lot donné** (logique
  d'arbre descendant).

### Panneau latéral & navigation entre pages (2026-08-16)

- **Panneau latéral de progression** : ancré à droite par défaut,
  activable/désactivable (comme un chat dans VS Code). Option **détachable**
  (fenêtre flottante, bouton détacher/réancrer) intéressante pour plus tard, à
  juger en œuvre. **Le plus simple en priorité.**
- **Clic sur un lot dans le chutier rushes** → arrive sur la page Pdf avec
  **ce lot ouvert par défaut**. Dans Pdf, **sélection multiple de lots**
  possible.

### RÉVISION — chutier commun & atelier Pdf (2026-08-16)

- **Le chutier est COMMUN aux pages Extract et Pdf** — arborescence :
  **rush → lots → planches pdf**.
- Sur l'atelier Pdf : sélection des lots par **cases à cocher** ; sélectionner
  le rush = sélectionner tous ses lots ; sélection partielle possible.
- **Génération** : une planche **par lot** ; si plusieurs dispositions
  (`frames_par_page`), une planche **par disposition**. Ex : 2 lots × 3
  dispositions = 6 planches.
- **Aperçu PDF : previz LIVE en direct** selon les paramètres — on sélectionne
  simplement quelle planche prévisualiser parmi celles à générer (ex. l'une des
  6). Pas de réglage dans l'aperçu.
- **Réglages exposés** (panneau du bas) :
  - nombre de frames par page ;
  - format (A4, A3…) ;
  - marge de travail autour des images ;
  - **orientation déterminée automatiquement** (disposition optimale, logique
    makepdf CLI).
- **Réglages NON exposés** (logique imposée) :
  - gabarit : choix par défaut imposé (le plus à jour) ;
  - dpi : toujours 600 ;
  - mapping gamut/patches : imposé ;
  - versions ultérieures : ratios non-16:9 à choisir dans cette section.
  - Les paramètres non exposés iront éventuellement dans les **Préférences**.
- **NOUVELLE DEMANDE** : bouton en **haut à droite** pour générer une
  **planche de calibration à la demande** (Egan revoit la logique ; ces planches
  existeront à part). Stockées dans une section **"à part" du chutier :
  CALIBRATION**.
- **Progression planches pdf** : carte par planche générée — progression en
  **nombre de pages générées / total** (ou pourcentage simple).
- **Une planche = un PDF.** Regroupement dans un **dossier par lot** (la
  disposition ne change que la planche). À consigner si c'est une modification
  de la fonction `makepdf` (nommage/organisation).
- **Planches de calibration** : bouton accessible depuis la **page Pdf**, avec
  un **homologue prévu depuis la page Scan**. Le chutier (section Calibration)
  montre une **liste des planches générées**. On demandera un **nom de
  scanner** (story en cours de développement). **Génération via mini dialogue**
  (contenu à déterminer selon les entrées attendues de la **story 5.22**,
  `EPIC5-ARB-80` : profil de calibration réutilisable, sous-fonction
  `calibrate` de `scan`, bibliothèque par machine).

### Cartes de résultat — comportement d'ouverture (2026-08-16)

- Carte finie (extract, pdf, scan, encode) : **deux boutons** — un pour le
  **dossier**, un pour le **fichier**, ouvrant **dans le système**.
- Cas des frames (fichiers multiples dans un dossier) : **bouton dossier seul**.

## Atelier Scan — flux détaillé (2026-08-16)

### Point d'entrée & arborescence

- **Point d'entrée = scans RÉALISÉS** (on "repart de zéro" ; ce n'est pas un
  choix de planches dans le chutier). À partir des scans on **reconstruit des
  lots**.
- **Arborescence INVERSÉE** : sous les scans on trouve les **lots reconstruits**
  (utilisables ensuite pour un export). **Un seul scan peut contenir plusieurs
  lots**.
- Pas de planche à scanner en haut à droite de l'atelier (le choix se fait dans
  le chutier). Éventuellement plus tard : bouton pour scanner directement depuis
  l'app (à voir).
- **Bouton "calibration scanner"** : récupère un scan de page de calibration et
  génère un **profil de calibration**, qui apparaît sous la page de calibration
  dans la section **CALIBRATION** du chutier.

### Prévisualisation — 2 modes (PDF / Galerie)

- **Mode PDF** : la page scannée avec **overlay** —
  - position détectée des **marqueurs ArUco** ;
  - position du **QR** avec **code couleur** (décodé ou non) ;
  - position détectée de chaque **frame** (impossible si QR non décodé).
- **Édition manuelle** :
  - clic sur une zone → modifier la détection en **glissant 4 marqueurs**
    (les 4 coins de la zone extraite) ;
  - réglage d'un marqueur → un mode **LOUPE** s'actionne automatiquement
    (réglage précis au pixel) ;
  - **QR non décodé** → clic → compléter les infos manquantes : frames par
    page, numéro de page, id du lot, timecode première/dernière image (toutes
    affichées sur la page) ;
  - une fois le QR complété, l'outil a toutes les infos pour détecter les
    zones image ;
  - **bouton "rescanner"** une page une fois les infos complétées ;
  - **bouton activer/désactiver la calibration couleur** + choix du fichier de
    calibration par défaut dans le chutier (section calibration). La calibration
    s'applique au scan et on **voit le résultat** ; activable/désactivable dans
    la page scan **et** dans la galerie ; changement de fichier de calibration
    possible.
- **Mode galerie** : images extraites rangées par timecode en grille. **Images
  manquantes mises en évidence en ROUGE**.
  - clic sur une image rouge → renvoi vers la **vue PDF** sur la page
    correspondante pour corriger la détection ;
  - clic sur une image normale → **plein écran avec zoom** ; petit bouton
    "éditer" → renvoi vers la page PDF correspondante pour corriger la zone
    détectée (rare en théorie car tout dépend des marqueurs ArUco).

### Réglages & exécution

- **Réglages en bas** : **DPI** et **choix de la calibration couleur** (rien
  d'autre).
- **Bouton scan** : lance l'extraction effective des frames scannées, avec une
  **tâche par planche** (comme les autres ateliers).
- **Re-scan partiel** : marquer une page en **rescan** et **remplacer** une page
  d'un lot par le scan de cette page seule une fois fait.

## Atelier Exports — flux détaillé (2026-08-16)

### Point d'entrée & arborescence

- **Partage le MÊME chutier que Scan** : on part de **lots reconstruits à
  partir de scans**.
- **Objectif central** : construire un rush à partir d'un scan **sans avoir le
  rush original sur la machine**.
- **NON** : on ne peut pas encoder un lot d'extraction (peut-être y réfléchira).
- **Un encode par lot** — pas de concaténation.

### Structure de l'atelier

- **Écran de préviz** : visionner un lot reconstruit à la **cadence cible
  visée** (logique similaire au previz extract — cadence modifiable après
  coup). **Bus de transport** comme celui d'extract, **sans le son** et **sans
  le basculement inter-cadences**.
- **Réglages** : résolution, cadence (**changent la previz**), puis **profil de
  sortie**. On affiche : **taille estimée**, **nom de fichier prévisionnel**,
  **emplacement de destination prévisionnel**.
- **Profil de sortie EXPOSÉ** + possibilité de créer des **PRESETS**.

### Exécution & file d'attente

- **Lancer directement** ou mettre en **FILE D'ATTENTE** (encode intensif en
  ressources). Pendant qu'un export tourne, on peut paramétrer d'autres exports
  et les mettre en file. La **prévisualisation serait bloquée** pendant un
  export (performances).

### Finalité des exports

- **Montage, post-production, ou diffusion tels quels** — orientera la voix et
  les défauts.
- **Previz Exports (si rush original dispo)** : relecture du **SON** depuis le
  rush original, et **balayage (wipe)** sur le lecteur pour comparer le rush
  original à son résultat.
- **File d'attente Exports : ordre MODIFIABLE** (réordonnable). Previz bloquée
  pendant un export : **à voir** — si on peut encore visionner un autre lot,
  tant mieux.

## Surfaces globales (2026-08-16)

### Gestion de projet (écran de lancement)

- **Résolution et cadence = paramètres rushe par rushe** (pas de défauts projet
  à la création).
- **Ouverture toujours possible** ; si le rush est **absent** de la machine, il
  s'affiche en **ROUGE** dans les chutiers correspondants. Possibilité future de
  **RELINK** après coup (ingest dans les dossiers du projet).

### Préférences

- Contenu **à réfléchir dans un second temps** (indéterminé pour l'instant).
- Les préférences sont **globales à l'app**.

### Position Epic 10 (2026-08-16)

- **Epic 10 (calque, planches vierges) : non anticipé dans les spines UX Epic
  7** — réconciliation à faire ultérieurement. Le chutier reste conçu **structuré
  par types** (rush / lots / planches / calibration) pour que l'ajout futur soit
  naturel.