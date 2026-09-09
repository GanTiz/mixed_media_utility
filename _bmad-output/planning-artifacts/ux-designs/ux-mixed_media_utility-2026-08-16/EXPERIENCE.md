---
name: mixed_media_utility
status: final
updated: 2026-08-23
sources:
  - DESIGN.md (même dossier) — référence visuelle, vocabulaire des tokens
  - .memlog.md — canon décisionnel ; en cas de contradiction, l'entrée la plus tardive gagne
  - .working/parcours-utilisateurs-epic7-2026-08-17.md (v2.1) — source longue des Key Flows
  - .working/decouverte-epic7-2026-08-16.md
  - imports/extraction-sources-epic7.md — contrats previz-1, vocabulaires de codes
  - _bmad-output/implementation-artifacts/decisions-2026-08-23-epic-7-suite.md — EPIC7-ARB-40 à 54
---

# mixed_media_utility — Experience Spine

> Le comportement. Le visuel est dans `DESIGN.md` et fait autorité : aucune couleur, aucune
> typo, aucune valeur d'espacement n'est redéfinie ici — elles sont appelées par leur nom.

## Foundation

Application de **bureau**, une fenêtre, **macOS 12+ et Windows 10+ natifs**, en Qt piloté depuis
Python (PySide6). La technologie a été tranchée *après* la première rédaction de cette spine
(arbitrage 14), et rien ici n'en dépend. Le repli « vue web fournie par le système » qui figurait
dans ce paragraphe est **écarté** : WebKit convertit toutes les images sans aucun levier de
désactivation, ce qui rendrait le jugement colorimétrique impossible. Local-first : pas de compte,
pas de réseau, pas de synchronisation.

**Un projet = un film = un dossier de travail.** Un projet ouvert à la fois. Le dossier de travail
ne contient **que ce que mmu produit** (frames extraites, scans, frames reconstruites, exports,
calibrations) ; les rushes restent où ils sont, l'outil n'en garde que le chemin et sait les
relinker.

**Le chemin du rush est persisté dans le fichier de projet** (`EPIC7-ARB-41`, verbatim : « Dans le
projet ! Mais remplaçable ! ») — c'est une **exception nommée** à l'invariant « aucun chemin absolu
au manifest », pour ce champ et pour lui seul. Trois exigences, toutes nécessaires :

1. **il est persisté.** Sans lui, tout projet rouvert affiche ses rushes en rouge : le rouge que la
   conception réserve au cas exceptionnel devient le régime nominal, et un signal qui vaut toujours
   ne vaut plus rien ;
2. **il se remplace facilement.** Le relink est un geste de première classe, pas un rattrapage ;
3. **son absence n'empêche rien d'essentiel.** Le mode délinké est **dégradé mais fonctionnel à
   partir d'un scan seul** : on détecte, on répare, on extrait, on exporte sans le rush. Ce qui
   tombe est ce qui exige la source — le son et le balayage — et rien d'autre.

**[À TRANCHER]** — la **règle de comparaison au relink** : à quoi l'outil reconnaît-il que le fichier
retrouvé, ou désigné à la main, est bien *ce* rush, et que fait-il quand la comparaison échoue ?
`EPIC7-ARB-41` la laisse explicitement à écrire. Le cas voisin — deux fichiers satisfaisant les trois
critères de recherche — est déjà, lui, en `deferred-work.md`.

Le fichier de projet et les dossiers de travail sont posés **directement dans le dossier désigné** :
l'outil n'y crée **aucun sous-dossier à son propre nom** (`EPIC7-ARB-28`). Deux demandes d'Egan du
2026-08-23 portent sur ce que le **cœur** écrit et **sortent du périmètre de cette spine** : nommer
le fichier de projet d'après le film, et renommer les dossiers de travail pour la lisibilité
(`lots`, `planches`, `scans`, `lots reconstruits`, `exports`). Elles sont instruites hors Epic 7,
avec leur coût relevé et deux réserves — une **espace** dans un nom de dossier, et `srcs` qui n'est
pas couvert par la proposition.

**La GUI héberge le cœur en processus** (`EPIC7-ARB-46`) : elle appelle ses fonctions directement,
elle ne pilote pas des sous-commandes. La formulation antérieure — « la GUI est une surcouche d'un
cœur CLI : elle expose, elle ne recalcule pas » — est **fausse telle quelle**, et c'est mesuré :
aucun émetteur de document `previz-1` n'existe côté cœur, et la bascule de calibration exige de
rejouer le pipeline couleur sur le même raster, à l'écran, sans rien écrire. Ce qui reste vrai du
principe, et qui est la seule chose qu'il voulait dire : **l'interface ne redéfinit aucune règle du
cœur** — verdicts, codes, géométrie, colorimétrie viennent de lui et de lui seul.

**La CLI est un livrable maintenu, pas un vestige** (`EPIC7-ARB-46`, verbatim : « la CLI indépendante
reste fonctionnelle le temps du chantier »). Le parcours de bout en bout d'aujourd'hui est la
**référence de non-régression** : une story qui le casse est une régression, pas un effet de bord
accepté. Et **la parité fonctionnelle GUI/CLI n'est pas exigée** — « certaines fonctions seront hors
GUI et ce n'est pas grave » : une fonction peut n'exister que d'un côté. C'est une contrainte que le
découpage supposait et que personne n'avait posée.

Les documents `previz-1` (kinds `extraction`, `makepdf`, `scan`, `encode`) sont **consultatifs** —
une previz n'autorise rien, et le consentement se rejoue intégralement au lancement d'une écriture,
quelle que soit la fraîcheur de ce qui est affiché.

**i18n : l'anglais est hors v1** (`EPIC7-ARB-52`). L'interface est **en français** ; les chaînes sont
**extraites dans un catalogue** pour que la bascule reste possible, mais **aucune traduction n'est
livrée**. Conséquence à porter partout : une règle de mise en page calée sur la longueur de l'anglais
n'a plus de référence mesurable (voir *Accessibility Floor*). Personas de référence :
**Camille** (cinéaste, autonome, c'est son film et c'est sa main sur le papier) et **Inès** (monteuse,
sa propre station, prépare le projet pour et avec Camille). Public élargi visé à terme : le reste de
la chaîne de post-production, puis des vidéastes — d'où l'exigence de facilité d'utilisation, portée
sans tutoriel (**hors v1**, arbitrage 6).

## Information Architecture

> **Les maquettes illustrent, cette spine contracte.** **Dix-huit** écrans sont rendus en HTML sous
> `mockups/` (compte vérifié le 2026-08-23), les principaux liés depuis les sections qu'ils servent.
> En cas de contradiction entre une maquette et cette spine, **c'est la spine qui gagne** — une
> maquette est datée, une spine est tenue à jour.
>
> **Aucune maquette ne se lit comme une source de valeurs.** L'énoncé antérieur — « quatre écrans
> porteurs » — ne couvrait que quatre fichiers sur dix-huit, et les quatorze autres n'ont jamais été
> confrontées aux jetons. La garantie implicite qu'il portait est donc **retirée**, et non étendue :
> couleurs, typographies et espacements se lisent dans `DESIGN.md`, jamais dans le HTML d'une
> maquette.

| Surface | Atteinte depuis | Rôle |
|---|---|---|
| Écran de gestion de projet | **Chaque lancement**, toujours | Ouvrir / créer un projet ; dernier projet **en tête** |
| Atelier **Extraction** | Onglet bas 1 | Ouvrir un rush, borner, choisir les cadences, extraire des lots |
| Atelier **Pdf** | Onglet bas 2 | Composer et générer les planches d'un ou plusieurs lots |
| Atelier **Scan** | Onglet bas 3 | Déposer, **détecter**, réparer, puis **extraire** les TIFF |
| Atelier **Exports** | Onglet bas 4 | Visionner un lot reconstruit et encoder un master |
| **Chutier**, à **deux panneaux** (`EPIC7-ARB-40`) | À gauche des 4 ateliers | Un **panneau d'arborescence** rétractable pour se placer, le **chutier** pour lire le contenu de l'objet désigné ; largeur réglable, mode plein écran. Voir *Le chutier — huit rôles* |
| File **« En attente de lecture »** *(la zone tampon)* | **Haut du chutier**, Scan/Exports | Fichiers déposés, pas encore décodés. C'est une **file**, pas un dépotoir (correction A2) ; porte le bouton **Détecter**, qui reste au chutier (`EPIC7-ARB-40`) |
| Section **Calibration** du chutier | Chutier, Pdf et Scan | Planches de calibration générées, profils de scanner produits |
| **Panneau de progression** | Bascule d'en-tête, depuis les **4** ateliers | File des tâches en cours et terminées, toutes fonctions confondues |
| **Scène de previz** | Cœur de chaque atelier | Extraction : vidéo / galerie · Scan : PDF / galerie / **lecteur** · Exports : lecteur + balayage |
| **Bus de transport** | Sous la previz | Lecture, image par image, boucle, in/out en `{typography.data}`, marqueurs |
| **Barre de réglages** | Bas de chaque atelier | Paramètres exposés + action principale de l'atelier, à droite |
| **Vue vignette unique** (`EPIC7-ARB-18`) | Clic sur une vignette de galerie | Une frame seule, plein panneau, **zoom dedans** — troisième vue après galerie et lecteur, pas un agrandissement de la grille. Bouton *éditer* renvoyant à la page PDF correspondante |
| **Formulaire de complétion de QR** | Clic sur un QR non décodé (Scan, mode PDF) | Saisir ce que le code aurait dit, **pointé** sur le scan |
| **Loupe** | Saisie d'une poignée de coin | Réglage au pixel, ouverture automatique |
| **Comparateur de candidats** | Clic sur une frame à plusieurs candidats, en galerie | Comparer et désigner le candidat retenu |
| Modales | Actions ponctuelles | Confirmation d'extraction · écrasement · planche de calibration · calibration scanner · version au dépôt d'un second tirage |
| **Préférences** | Barre de menus | Interface · Fichiers · Performances · Valeurs par défaut. Voir *Préférences utilisateur et réglages projet* |
| **Menu contextuel** | Clic droit sur un objet | Commandes s'appliquant à l'objet désigné. Voir *Menu contextuel* |
| **Barre de menus système** | Toujours, hors fenêtre | Ce que le système exige, l'apprentissage des raccourcis, un second chemin. Voir *Barre de menus système* |

**Règles de navigation.** On travaille *dans* un atelier, on n'y navigue pas : les quatre onglets sont
un ordre de flux, pas une arborescence. **Changer d'atelier ne déplace pas l'image d'un pixel** : le
chrome garde d'un atelier à l'autre les largeurs qu'il a. Ce ne sont plus des largeurs *constantes* —
le chutier et son panneau d'arborescence se règlent à la poignée et se rétractent (`EPIC7-ARB-40`) —,
ce sont des largeurs **stables tant que l'utilisateur ne les change pas** : seul son geste les
déplace, jamais un changement d'atelier. Les jetons (`{spacing.bin-width}`,
`{spacing.side-panel-width}`, `{spacing.tabbar-height}`, `{spacing.header-height}`) portent les
valeurs et leurs bornes, dans `DESIGN.md`. Les modales s'empilent sur **un seul niveau**. Un
**double-clic** sur un lot dans le chutier d'Extraction **ouvre l'atelier Pdf** sur ce lot — le clic
seul désigne (`EPIC7-ARB-2`) ; un clic sur une frame rouge en galerie **ouvre le mode PDF sur la page fautive**,
jamais au début du document. Les tâches tournent **en arrière-plan** : changer d'atelier ne perd
rien.

Le chutier a **deux périmètres** et une seule identité visuelle : *rush > lots > planches* sur
Extraction et Pdf, *scan > lots reconstruits* sur Scan et Exports, plus la section Calibration et la
file « En attente de lecture » (que ce document appelle aussi *zone tampon*, son nom générique — le
nom **affiché** est « En attente de lecture »).

**L'arborescence n'est pas inversée** (correction A1) : l'ordre affiché reste toujours *rush > lot >
planche > scan*. « Remonter » désigne la **reconstruction de la branche à partir d'un scan seul** —
ce que les QR déclarent permet de recréer les ancêtres manquants —, jamais un affichage retourné. Le
contresens a circulé dans les deux spines ; il est corrigé ici et au rôle 3 ci-dessous.

## Le chutier — huit rôles

> Maquettes : [`mockups/key-chutier-v2.html`](mockups/key-chutier-v2.html) — **le modèle de
> référence**, validé le 2026-08-21 (`EPIC7-ARB-40`) : deux panneaux, poignée de largeur, file en
> haut. [`mockups/key-chutier.html`](mockups/key-chutier.html) la précède : les deux périmètres et
> les huit rôles y sont annotés, mais sa **colonne unique est le modèle remplacé** — c'est la
> maquette v2 qui fait foi sur la disposition, cette spine sur le comportement.

*Section propre au produit.* Le chutier n'est pas un panneau de navigation : c'est la pièce la plus
sollicitée de l'application, et l'endroit où une erreur de conception coûterait le plus cher. Huit
rôles distincts, recensés en fin de parcours, tous portés par la même surface.

| # | Rôle | Ce que ça impose au comportement |
|---|---|---|
| 1 | **Source** | On y ajoute des rushes (dialogue système **ou** glisser-déposer, plusieurs à la fois) ; les rushes ne sont pas copiés |
| 2 | **État d'avancement lisible après trois semaines** | L'arbre montre jusqu'où la chaîne est allée, sans qu'on ait à se souvenir : sous le lot, la planche, et **rien après**. **L'arbre porte ce qui a un état, la galerie ce qui a une image** (`EPIC7-ARB-1`) — c'est ce qui l'empêche de devenir un explorateur de fichiers |
| 3 | **Branche reconstruite depuis un scan seul** | Un scan peut porter plusieurs lots ; la **branche** se reconstruit depuis ce que les QR déclarent, et vient se ranger dans l'ordre habituel *rush > lot > planche > scan*. **L'affichage n'est jamais retourné** (correction A1) |
| 4 | **Lieu d'où l'on déclenche la détection** | Le bouton **Détecter** vit au chutier, jamais dans la previz, et **jamais automatiquement** |
| 5 | **Espace d'organisation** | Dossiers créés par l'utilisatrice (« séquence 3 ») ; ils n'existent **que** dans le chutier, jamais dans le dossier de travail. **Aucun dossier automatique par type** : ce besoin est servi par un **filtre**, pas par une arborescence imposée (`EPIC7-ARB-4`) |
| 6 | **Porteur du code couleur** | Complétude d'un lot et absence d'un média se lisent ici, en `{colors.state-complete}` / `{colors.state-substitute}` / `{colors.state-absent}` |
| 7 | **File « En attente de lecture »** *(la zone tampon)* | Ce qui est déposé mais pas décodé ; ce que la détection ne rattache pas **y reste, visible**. Elle est **en haut** du chutier (correction A2) : une file se vide, un fond de tiroir se remplit |
| 8 | **Lieu des versions et du lot composé** | Un second tirage et ses candidats se posent sous **le même lot** ; **le lot composé est un lot à part entière** — une branche sœur nommée, l'original intact à côté (`EPIC7-ARB-57`) *(cible non livrée)* |

**Six niveaux hiérarchiques doivent rester lisibles** (`EPIC7-ARB-9`), et quatre moyens y concourent
ensemble, aucun ne suffisant seul : la **profondeur lue comme un avancement** dans la chaîne, un
**pictogramme par niveau**, des **branches dessinées** qui s'arrêtent au dernier frère, et le report
du détail **hors de la ligne** plutôt que dans la ligne. L'**expandeur n'apparaît que sur un
nœud qui a des enfants** : son absence est l'information (`EPIC7-ARB-3`).

**[À TRANCHER]** — **où va ce détail, désormais.** Le quatrième moyen visait « un panneau latéral » ;
dans le modèle à deux panneaux (`EPIC7-ARB-40`), le panneau latéral du chutier porte
l'**arborescence** et le chutier porte le **contenu** de l'objet désigné, si bien qu'aucune surface
n'est plus désignée pour le détail d'une ligne. Trois pistes, aucune arbitrée : un inspecteur propre,
une colonne du chutier, ou le panneau latéral d'inspection de l'atelier courant.

**La sélection est à trois états** (`EPIC7-ARB-10`) — vide, partielle, pleine — et sélectionner un
parent vaut sélectionner ses **enfants actionnables**, pas tous ses descendants. L'action porte son
**cardinal** : « Extraire 167 frames », pas « Extraire ».

### Deux panneaux, pas une colonne (`EPIC7-ARB-40`)

Le chutier n'est **pas** une colonne unique ancrée à gauche : c'est un **couple de panneaux**, et le
modèle validé le 2026-08-21 fait référence. Ce qui suit remplace toute description d'une « seule
pièce » à largeur fixe.

- **On désigne à gauche, on lit à droite.** Le **panneau d'arborescence** — un panneau latéral
  rétractable, à ne pas confondre avec le panneau latéral d'inspection des ateliers — sert à *se
  placer* ; le **chutier** montre le **contenu de l'objet désigné** : désigner `séquence 3` met dans
  le chutier tous ses rushes et leurs enfants. Motif : la question « qu'est-ce qui fait qu'on entre
  dans une branche » disparaît, il n'y a plus de mode à activer, et le fil d'Ariane devient inutile —
  le panneau d'arborescence *est* le fil, et il est toujours là.
- **Le chutier reste un arbre.** Le panneau fixe la **portée**, il ne remplace pas la filiation : on
  continue de déplier dans le chutier ce qu'on veut. Modèle assumé : l'explorateur de fichiers et
  Resolve.
- **La largeur se règle**, par une poignée, et **le panneau d'arborescence se rétracte**. Sous une
  certaine largeur de fenêtre il se rétracte **seul** — le chutier passe avant lui — mais il **se
  rappelle d'un geste** : un rail de pictogrammes reste, et rouvre l'arborescence **par-dessus** le
  chutier, le temps de se placer. On a l'un ou l'autre, **jamais rien**.
- **Le chutier a un mode plein écran**, distinct du plein écran de fenêtre : c'est la surface la plus
  sollicitée de l'application, et un arbre à six niveaux se lit parfois seul.
- **La file « En attente de lecture » est en haut** (correction A2), et le bouton **Détecter reste au
  chutier** : il avait disparu de la maquette v2, alors qu'il est le seul déclencheur de la seconde
  moitié de la chaîne — il revient (`EPIC7-ARB-40`).

*La géométrie chiffrée n'est pas ici* : largeurs initiales et bornes, seuil de rétractation
automatique, taille du rail se lisent dans `DESIGN.md`. Cette spine dit le comportement, pas les
tailles.

## Points de jugement avant écriture

> Maquettes : [`mockups/key-atelier-pdf.html`](mockups/key-atelier-pdf.html) pour l'aperçu vivant
> (point 1) et [`mockups/key-mode-lecteur.html`](mockups/key-mode-lecteur.html) pour le mode lecteur
> (point 2, avec l'état dégradé). Chacune rend **deux états**, parce que c'est le mouvement entre
> eux qui porte la règle.

*Section propre au produit.* Le principe qui traverse tout : **ne jamais laisser fabriquer quelque
chose qu'on n'a pas d'abord regardé.** Ce n'est pas une politesse d'interface, c'est ce qui remplace
le tutoriel absent.

| Point de jugement | Avant quoi | Comportement |
|---|---|---|
| **Aperçu vivant de la planche** | Avant de générer le PDF | Chaque changement de réglage redessine la planche, **sans bouton** ; on choisit seulement *quelle* planche regarder parmi celles à générer |
| **Mode lecteur** | Avant d'extraire les TIFF | Le lot se relit **à sa cadence cible**, en qualité temporaire : si c'est raté, à quoi bon écrire les frames |

**Corollaire sur les machines lentes** *(consigne du 2026-08-19)*. Le second point de jugement
suppose que la cadence soit tenue — et sur une machine ancienne elle ne le sera pas toujours. La
previz **dégrade alors l'image, jamais la cadence** : c'est le rythme qu'on juge à cet instant, pas
le grain. Mais elle ne peut pas le faire en silence. Un repli muet ferait juger sur une image
dégradée sans le savoir, dans un outil dont toute la promesse est qu'on juge sur ce qu'on voit :
il ruinerait la règle qu'il sert. D'où la ligne *Previz dégradée* des `State Patterns` : le repli
se voit, se nomme, et **se refuse en un clic**.

**Qui dégrade est tranché : l'utilisateur, sauf en mode *auto*** (`EPIC7-ARB-43`, verbatim). Mais
**[À TRANCHER]** — la **qualité de previz par défaut**, et c'est une ligne qui commande tout le
mécanisme. L'arbitrage dit *qui* dégrade, pas la valeur livrée. **Si le défaut n'est pas *auto*, le
repli automatique ne s'arme jamais** : la previz tiendra la qualité et perdra la cadence — exactement
le comportement que ce point de jugement interdit — et la ligne *Previz dégradée* ne se produira
jamais chez personne.

**Corollaire : l'atelier Scan se déroule en deux temps, jamais en un.**

1. **Détection** — déclenchée depuis le chutier, sur une sélection cochée dans le tampon ; cartes
   « détection » en file d'attente ; **complétude annoncée dès la fin de chaque tâche**, avant toute
   écriture. La détection seule produit déjà la position des frames et un aperçu.
2. **Extraction TIFF** — une tâche par planche. C'est ce qu'on appelait à tort « lancer le scan ».

**Contrat : la détection écrit son propre fichier, un par détection** (`EPIC7-ARB-49`). Ce n'est pas
un détail d'implémentation, c'est ce qui rend les deux temps possibles :

- **un fichier dédié par détection, hors du manifeste** — jamais une section unique du manifeste
  réécrite en entier ;
- **c'est ce qui donne le point d'arrêt avant écriture** : la complétude peut être annoncée à la fin
  de la détection parce qu'elle est *écrite quelque part*, au lieu de vivre en mémoire et de mourir à
  la fermeture ;
- **c'est ce qui supprime l'écrasement du détail par page du lot précédent** : deux détections sur le
  même document ne se marchent plus dessus, donc l'interface peut encore répondre à « quelles pages
  manquent », ouvrir la galerie sur ses trous et renvoyer sur la page fautive ;
- **corollaire d'interface** : ce que la galerie et le mode lecteur montrent d'un lot détecté
  **survit à la fermeture de l'application**, et ne se reconstruit pas à chaque ouverture.

### D'où viennent les images de l'aperçu

Le mode lecteur et la galerie lisent **la même source** : les images légères que
la **détection** écrit en même temps qu'elle établit la géométrie de chaque
frame. Une seule source, et c'est la raison du choix *(tranché le 2026-08-17)* —
deux sources distinctes pourraient montrer deux choses différentes de la même
frame, dans un outil dont toute la promesse est qu'on juge sur ce qu'on voit.

Ces images sont des **artefacts de travail, jetables et régénérables**. Les
écrire ne rompt pas le principe ci-dessus : celui-ci porte sur les **TIFF du
lot**, qui sont le livrable. L'interface ne doit donc jamais les présenter comme
un résultat, ni proposer de les ouvrir dans le système.

> **Dépendance.** Cette production d'images par la détection n'existe pas encore
> — elle a été trouvée manquante à la réconciliation des sources, et c'est la
> pièce sur laquelle repose le second point de jugement. Une story d'Epic 5 la
> porte. Tant qu'elle n'est pas livrée, **le mode lecteur ne peut pas être
> simulé** : voir *Cible non livrée*.

## Voice and Tone

Microcopie. La voix de marque et la posture esthétique sont dans `DESIGN.md`.

**La chaîne de référence est écrite en français** — l'anglais est hors v1 (`EPIC7-ARB-52`) — et elle
vit dans un **catalogue de chaînes**, jamais en dur dans un écran. Aucune mise en page ne suppose la
longueur d'une langue ; aucune ne se cale plus sur celle de l'anglais, qui n'existe pas. Les **codes
du cœur ne se traduisent jamais** : `LOT_INCOMPLETE`, `PAGE_QR_UNREADABLE`, `SYNTHETIC_FRAME_WRITTEN`,
`TIRAGES_MULTIPLES`, `previz-1` s'affichent verbatim en `{typography.data}`, **à côté** de leur phrase
traduite, jamais à sa place.

**Et la GUI ne recopie jamais un code du cœur : elle le lit.** Un code affiché est la **valeur rendue
par le cœur**, jamais une chaîne littérale écrite dans l'interface ou reprise d'une maquette. Le motif
est mesuré, et la divergence a déjà eu lieu : une maquette écrit `LOT_INCOMPLET` là où le cœur écrit
`LOT_INCOMPLETE` — deux orthographes indiscernables à l'œil au milieu d'une phrase française. Un code
recopié à la main perd exactement la propriété qui le justifie : **pouvoir être cherché et comparé**,
au journal, dans la sortie de la CLI, d'une machine à l'autre. La règle vaut partout où cette spine
impose un affichage verbatim — cartes de tâche, refus d'encodage, formulaire de QR, bandeaux d'état.

| Do | Don't |
|---|---|
| « 6 images manquent — page 4. » / *6 frames missing — page 4.* | « Échec du scan » / *Scan failed* |
| « Le QR de la page 4 n'a pas été lu. Complétez ce qui est imprimé dessus. » `PAGE_QR_UNREADABLE` | Un message qui dit qu'il a échoué sans dire quoi faire ensuite |
| « 9 pages, 3 mires de remplacement. Le lot n'est pas complet. » | Fondre pages manquantes et mires en un seul compteur, ou un seul mot |
| « Écraser les 50 frames de ce lot ? Les fichiers actuels seront détruits. » | Écraser sans le dire, ou forcer l'écrasement comme seule issue |
| « Ce projet a été reconstruit à partir de scans : la résolution source et la politique d'arrondi n'y figurent pas. » | Un champ vide accusateur, ou une invitation à « compléter » ce qui est structurellement absent |
| Compter, nommer, et s'arrêter là | Féliciter, encourager, exclamer, célébrer une tâche finie |
| « Ce lot a 2 tirages. » | « Dernière version » — **faux tant que la date n'est pas au manifest** |
| Nommer l'objet : *rush, lot, planche, page, frame, scan, candidat* | Inventer un synonyme par écran |

**Trois règles qui reviennent dans tous les parcours :**

1. **Un échec dit son motif et laisse une prise.** Une action dont le résultat part hors de l'app
   (ouvrir un dossier, écrire un master) ne peut pas échouer en silence ; l'échec nomme sa cause et
   offre au moins un chemin manuel vers le même résultat.
2. **On ne devine pas à la place de l'utilisatrice.** Aucun champ du formulaire de QR n'est
   prérempli : un champ vide appelle la vérification, un champ faux ne l'appelle pas. L'outil
   **propose** une géométrie, il ne la valide jamais lui-même.
3. **On ne propose jamais de compléter ce qui est structurellement absent.** Un projet né du scan
   seul ne porte ni résolution source, ni politique d'arrondi, ni empreinte de sélection : c'est une
   propriété du document, pas un manque à combler.

## Component Patterns

Comportemental. Les specs visuelles sont dans `DESIGN.md.Components`.

> Maquette : [`mockups/key-scan-mode-pdf.html`](mockups/key-scan-mode-pdf.html) — surimpressions,
> poignées, loupe et formulaire de complétion de QR, dans leurs deux états.

| Composant | Où | Règles comportementales |
|---|---|---|
| `{components.workshop-tab}` | Toujours visible | Quatre ateliers dans l'ordre du flux. Changer d'onglet n'interrompt aucune tâche. Aucun compteur, aucune pastille sur l'onglet |
| Onglets de vue | En-tête d'atelier | **`page, galerie, lecteur`** — plus `frame` là où la vue vignette unique a un objet. Ils changent d'un écran à l'autre : un rush n'a pas de page. **Un onglet sans objet est absent**, pas grisé (`EPIC7-ARB-24`) |
| `{components.bin-row}` | Chutier | **Un clic désigne, un double-clic ouvre** (`EPIC7-ARB-2`) — le clic ne déclenche donc plus aucune navigation. Destinations du double-clic, par type (`EPIC7-ARB-11`) : rush → Extraction · lot → Pdf · **planche → Pdf** · scan → Scan · lot reconstruit → Exports · **rush encodé → Exports**. Le principe qui les unifie, écrit dans le même arbitrage et jamais transcrit jusqu'ici : **on atterrit sur l'atelier où l'objet est *en jeu*** — celui qui le consomme s'il en reste un, celui qui l'a produit sinon. La planche et le rush encodé sont les deux objets sans consommateur dans l'outil (l'impression et la diffusion se passent dehors), d'où leur retour vers l'atelier producteur. *(La table est fixée par Egan ; `EPIC7-ARB-11` donne la formulation unifiée comme « à valider ».)* **Sélectionner un parent vaut sélectionner ses enfants actionnables** (`EPIC7-ARB-10`), sélection partielle permise. Le clic droit porte l'inventaire de `## Menu contextuel` |
| `{components.bin-buffer}` — file **« En attente de lecture »** | **Haut du chutier**, Scan | Accepte le dépôt d'un fichier, d'une sélection ou d'un **dossier entier**. Cases à cocher : on choisit ce qui part en détection. Rien n'en sort tout seul ; ce que la détection ne rattache pas **y reste** |
| `{components.viewer-stage}` | Les 4 ateliers | Seule zone souple de la mise en page. Le sélecteur de mode et le zoom de vignettes sont **au-dessus**, le transport **en dessous** ; rien d'autre n'entre dans le cadre. Le bouton d'ajustement s'intitule **« ajuster »**, jamais « largeur » (`EPIC7-ARB-17`). Le lecteur dispose d'un mode qui lui fait **occuper tout l'écran**, distinct du plein écran de fenêtre |
| Panneau latéral | Les 4 ateliers | **Se rétracte**, par la même commande partout (`EPIC7-ARB-25`). Une vue qui n'a rien à y mettre s'ouvre **déjà rétractée** ; une poignée de rappel reste, sinon rien ne dit qu'il revient. L'état est mémorisé **par vue**, pas globalement. Un panneau **ne répète pas ce que l'image montre** — ni timecode, ni numéro de frame, ni position de poignée — et **n'explique pas une fonction en prose** : il porte des contrôles, et un choix y prend la forme d'une liste à cocher (`EPIC7-ARB-22`) |
| Bus de transport | Extraction, Scan (lecteur), Exports | **Une seule ligne sous l'image, icônes seules, aucun libellé.** Les bornes encadrent la barre — l'entrée à gauche, la sortie à droite — et les deux boutons extrêmes du groupe central y conduisent. Recul en vraie lecture arrière, ×2/×4/×8 par appuis successifs. Image par image, boucle, marqueur en bouton unique, volume en haut-parleur dont le curseur vertical s'ouvre au clic. La progression est un **trait**, pas un bandeau : il porte bornes, marqueurs et tête de lecture, rien d'autre. Flèches de cadence = **Extraction seulement**. Le **balayage n'est pas ici** : il s'actionne depuis la barre de vue (`EPIC7-ARB-24`) |
| Balayage (wipe) | Exports | Bouton de la **barre de vue**, en haut de l'affichage (`EPIC7-ARB-24`). Poignée neutre. Marche/arrêt **en un clic**. Inspectable **image par image en pause** — c'est un mode d'inspection, pas un effet de démonstration. **Il n'a aucun panneau latéral** : un balayage se règle en tirant sa poignée. Sans le rush d'origine il reste **grisé**, jamais absent — il redeviendra actionnable au relink |
| `{components.frame-thumb}` | Galeries | Clic = **vue vignette unique** (`EPIC7-ARB-18`) : la frame seule, plein panneau, zoom dedans — c'est une vue à part entière, pas un agrandissement de la grille, et le panneau latéral s'y ouvre **rétracté** (`EPIC7-ARB-25`). Bouton *éditer* = renvoi vers la page PDF correspondante. Une vignette **rouge** renvoie sur la page fautive. Une vignette à **plusieurs candidats** ouvre le comparateur |
| `{components.overlay-zone}` | Scan, mode PDF | Chaque zone est **adressable** (`page_index` + `slot_index`) et **toujours éditable**, y compris quand la détection se déclare satisfaite. Clic = poignées |
| `{components.overlay-handle}` + loupe | Scan, mode PDF | Saisir une poignée ouvre la loupe **automatiquement**. Au relâchement : **rien à relancer**, l'outil actualise la complétude du lot, c'est tout |
| Formulaire de complétion de QR | Scan, mode PDF | Champs : frames par page, numéro de page, identifiant du lot, timecode première/dernière image. Le focus d'un champ **pointe la zone correspondante du scan** ; zoom disponible. Aucun préremplissage. Une fois complété, l'outil peut proposer les zones d'image |
| Bascule de calibration couleur | Scan (mode PDF **et** galerie) | Active/désactive à la volée, change de profil à la volée ; le rendu change à l'écran sans rien écrire. Se bascule autant de fois qu'on veut pour juger |
| Badge de cadence | Scène de previz | Dit la cadence **effective** de la lecture — il **constate**, il ne décide pas (`EPIC7-ARB-15`). La **qualité** est un menu voisin, jamais dans le badge : **c'est l'utilisateur qui dégrade, sauf en *auto*** (`EPIC7-ARB-43`) — la valeur livrée par défaut reste à trancher, voir *Points de jugement avant écriture*. La cadence s'écrit sans unité — `25`, pas `25 fps`. Après **cinq secondes** de rouge continu, un **bandeau unique**, refermable et désactivable pour la session ; en dessous de ce seuil le rouge ne dit rien d'utile |
| `{components.job-card}` | Panneau de progression | **Objet transverse** : toute tâche longue en produit une — extraction, génération, détection, extraction TIFF, encodage (`EPIC7-ARB-23`). Une carte par lot / par planche / par détection. Ordre, qui est un contrat : nom de la fonction, nom du lot, barre, frames/total, temps passé, temps restant. Terminée : boutons *dossier* et *fichier* — **dossier seul** quand le résultat est une collection de frames. Échouée : **motif verbatim** du cœur — lu de lui, jamais recopié (voir *Voice and Tone*). La jauge d'un encodage en cours **est** cette carte, pas un mécanisme séparé |
| Pastille d'activité | En-tête, bascule du panneau | Allumée pendant qu'une tâche tourne. Une activité **n'est pas un verdict** |
| `{components.params-field}` | Barre de réglages | Préremplis d'après la source, initialisés par les valeurs par défaut des Préférences (`EPIC7-ARB-32`). Un champ **essentiel manquant** bloque l'action de l'atelier tant qu'il n'est pas rempli à la main. **La cadence est une valeur saisie, libre** (`EPIC7-ARB-20`) : les valeurs offertes sont des *raccourcis du projet*, pas la liste des possibles, et un `+` ajoute celle qu'on vient de taper |
| Réglages d'export | Exports, panneau latéral | Contenu d'un outil de post-production (`EPIC7-ARB-19`) : **résolution, cadence, codec et variante, débit, profondeur, codec audio, échantillonnage, pistes, nom, destination**. Vocabulaire et groupement alignés sur ceux de DaVinci Resolve — un terme inventé ici coûte une traduction mentale à chaque export. **La cadence d'export** (`EPIC7-ARB-45`) : son défaut est la **cadence source consignée au projet**, et le principe est qu'elle se change. **Repli retenu, et il s'applique tant que le Scan est le chantier prioritaire** : la **v1 fige la cadence à la source**, sans champ modifiable, et **l'écran le dit** au lieu de laisser croire à un choix. Motif : la story 6.6, livrée, a retiré `fps_target` des paramètres d'encodage sur mesure de deux masters réels ; rouvrir le choix est un chantier, et le repli est autorisé par Egan lui-même (« si c'est un gros chantier on bloque ce choix pour le moment »). Le **preset** est un jeu complet de ces valeurs, nommé, modifiable ponctuellement sans être écrasé. Ils tiennent dans le panneau latéral ordinaire, ils n'ont pas de surface propre (`EPIC7-ARB-23`) |
| `{components.page-preview}` | Pdf | **Aperçu vivant** : aucun bouton de rafraîchissement. On sélectionne quelle planche regarder, pas comment la regarder — aucun réglage ne vit dans l'aperçu |
| `{components.button-primary}` | Droite de la barre de réglages | Une action principale par atelier : Extract · Générer · Détecter puis Extraire · Exporter (ou Mettre en file) |
| Modale | Ponctuelle | 1 niveau. Confirmation d'extraction : cadences cochables + **espace disque annoncé**. Écrasement : dit ce qui est détruit, jamais forcé. Calibration scanner : nom du scanner, dpi, format, **commentaire libre** sur les réglages du scanner |
| `{components.badge-state}` | Verdicts uniquement | Jamais pour nommer un type d'objet. **Pas de badge « projet reconstruit »**, et **aucun badge de déduction** (`EPIC7-ARB-14`) : un ancêtre reconstruit depuis un scan peuple l'arbre comme les autres, et s'il manque sur le disque il porte le signe du manquant, déjà défini. **Trois états, trois signes distincts** (`EPIC7-ARB-5`, cas d'usage en `EPIC7-ARB-12`), qui ne se confondent jamais parce qu'ils appellent **trois gestes différents** : **délié** — maillon brisé, *retrouver le fichier* · **non rattaché** — point d'interrogation, *l'identifier* · **incomplet** — ⚠️, *le compléter*. Un glyphe commun dirait « quelque chose ne va pas » sans dire quoi faire. **À ne pas confondre avec la complétude d'un lot** — *complet · complet-avec-mires · incomplet* —, qui est un **autre** triplet : il reste légitime sous son propre nom, il est détaillé aux `State Patterns`, et il **ne relève pas d'`EPIC7-ARB-5`** — la référence lui avait été attribuée par erreur. Troisième famille encore, les **formes** non chromatiques des états de frame (disque plein / anneau creux / disque hachuré), voir *La couleur ne porte jamais seule* |
| Écran de gestion de projet | Lancement | Dernier projet **en tête**, distingué par un liseré mais **non présélectionné**. La liste porte le nom, le chemin, la **date de création** et la **date de modification** ; elle se **trie** et se **cherche**. Elle ne dit **rien du contenu** — ni lots, ni scans, ni rushes manquants : cela se découvre en ouvrant (`EPIC7-ARB-27`). **Deux** actions : *créer* et *ouvrir un dossier* (`EPIC7-ARB-83`, 2026-08-27). L'import d'un projet existant a été retiré de cette passe : `importer_un_projet` et `ouvrir_un_dossier` appelaient tous deux `_designer_et_accueillir`, le même code au caractère près — deux boutons pour un seul comportement. Le geste n'est pas abandonné, il est **reporté à la story 7.14** avec son énoncé complet. Créer = désigner un dossier **parent** et un **nom**, l'outil créant ce dossier (`EPIC7-ARB-82`) ; l'outil n'y crée **aucun sous-dossier** à son propre nom. Ouvrir un projet dont les rushes sont absents reste **toujours** possible |

## State Patterns

| État | Surface | Traitement |
|---|---|---|
| Lancement | Gestion de projet | Toujours affiché, même quand un seul projet existe. Aucun saut direct dans un atelier |
| Chutier vide | Extraction | Invite à ajouter un rush (dialogue système ou glisser-déposer). Aucun rush d'exemple |
| Rush absent / délinké | **Tous** les chutiers | Peint en `{colors.state-absent}`, **sans badge ni mention** ; le rush est rouge dans tous les chutiers où il apparaît. Relink possible à tout moment, et **de première classe** (`EPIC7-ARB-41`) ; au relink, le rouge tombe et le son + le balayage reviennent sur Exports. **Le rush absent ne bloque rien d'essentiel** : détection, réparation, extraction et export marchent à partir d'un scan seul — c'est un régime **dégradé mais fonctionnel**, pas une impasse |
| Métadonnée essentielle manquante | Barre de réglages | Champ en `{colors.state-absent}` ; l'action de l'atelier est **bloquée** tant qu'il est rouge |
| Fichier déposé, pas décodé | Zone tampon | Y reste, visible, **sans être rangé**. Aucune détection ne part toute seule |
| **PDF déposé** | Zone tampon | Le type est **ambigu** : une planche à imprimer et le scan d'une planche sont tous deux des PDF (`EPIC7-ARB-13`). L'outil **pose la question** plutôt que de deviner. La détection automatique du type est **reportée** — la question posée suffit, et aucun code ne doit en dépendre |
| Non rattaché après détection | Zone tampon | Y **reste**, nommé, plutôt que de disparaître. C'est le reliquat qu'on ira inspecter |
| **Previz dégradée pour tenir la cadence** | Scène de previz (lecteur, balayage) | Bandeau en `{colors.state-substitute}` **sous** la scène, jamais par-dessus : « Qualité réduite pour tenir la cadence. La cadence est juste, l'image ne l'est pas. » `PREVIEW_QUALITY_REDUCED`. Porte l'échange inverse en un clic (*tenir la qualité, perdre la cadence*) et **disparaît** dès que la machine reprend la main. Ambre et non rouge : c'est un compromis, pas un échec |
| Tâche en cours | Panneau + pastille | `{colors.accent}` — activité, pas verdict. L'atelier reste utilisable. **Deux verbes distincts** (`EPIC7-ARB-6`) : *annuler* une tâche qui n'a pas commencé à écrire, *interrompre* une tâche en cours d'écriture — le second laisse un résultat partiel et le dit |
| Tâche terminée | Carte | `{colors.state-complete}` + boutons d'ouverture système |
| **Lot complet** | Chutier, galerie | `{colors.state-complete}`. Toutes les frames attendues sont là et aucune n'est synthétique |
| **Lot complet-avec-mires** | Chutier, galerie | `{colors.state-substitute}` — **jamais confondu avec complet.** Aucune page ne manque, mais des frames sont des mires |
| **Non rattaché** | Zone tampon | L'objet existe, on ignore de quel lot et de quelle page il relève — un scan dont le QR est illisible, pli ou encre (`EPIC7-ARB-12`). **Résolution** : saisir lot et page dans l'atelier Scan, le scan rejoint sa planche. La zone tampon est **l'endroit** ; *non rattaché* est **l'état** |
| **Délié** | Chutier | Le rush d'origine a été effacé du disque alors que ses planches et ses scans sont là. **Résolution** : retrouver le fichier et le relier |
| **Incomplet** | Chutier, galerie | Un lot de 9 pages dont 7 scans sont présents. **Résolution** : scanner les deux planches manquantes |
| **Frame absente** | Galerie | `{colors.state-absent}`, la case **reste à sa place** dans la grille. « Il n'y a rien ici » |
| **Frame absente, en mode lecteur** | Scène de previz (lecteur) | Le lecteur joue **la mire** à la place de la frame manquante (`EPIC7-ARB-47`). Deux propriétés, et c'est pour elles qu'on la choisit : **la cadence est préservée** — un saut la fausserait, et c'est le rythme qu'on juge à cet instant — et **le trou se voit** — un noir se confondrait avec une image sombre. **Conséquence à porter :** en mode lecteur on est **avant** l'extraction, donc avant qu'une seule mire ne soit écrite sur le disque ; la GUI la **dessine à la volée**, aux dimensions des frames du lot. C'est une story d'interface, pas de cœur |
| **Mire de remplacement** | Galerie | `{colors.state-substitute}`. « Il y a quelque chose ici, mais ce n'est pas ton image » |
| **Frame écartée par la cadence** | Galerie Extraction | Grisée et hachurée, **jamais rouge** — une frame écartée n'est pas une frame manquante. **L'écart est calculé par la cadence demandée, jamais choisi** (`EPIC7-ARB-16`) : aucune case à cocher n'existe sur une frame, et rien ne permet d'outrepasser la sélection. Un **filtre de vue** — toutes / retenues / écartées — affiche ou masque, et n'a aucun effet sur ce qui sera extrait. Le motif est écrit à côté de l'action : changer de cadence est le seul moyen de reprendre une écartée |
| QR non décodé | Scan, mode PDF | Zone du QR en `{colors.state-substitute}` ; **les zones d'image ne sont pas proposées** — sans QR, l'outil ignore quelles frames devraient être là. Clic = formulaire |
| Écrêtage de gamut détecté | Scan | Doit être **vu** : porté à l'écran, pas seulement au journal (`GAMUT_CLIPPING_DETECTED`) |
| Plusieurs candidats pour une frame | Galerie | Marque d'angle en `{colors.accent}` portant leur nombre ; clic = comparateur *(cible non livrée)* |
| Export en cours | Exports | La previz **se bloque** pendant l'encodage, et **l'écran le dit** — bandeau, jauge, temps restant — au lieu de devenir inerte. Visionner un *autre* lot pendant ce temps est **reporté** (Egan, 2026-08-23 : « à voir à l'usage, pas prio ») : la v1 bloque sans exception, et aucun code ne doit dépendre de la levée future de cette contrainte. Ceci **restreint** `EPIC7-ARB-7`, qui posait le principe inverse en attendant l'usage |
| Refus d'encodage | Exports | Motif verbatim depuis `ENCODE_REFUSAL_CODES` — **lu du cœur, jamais recopié** (voir *Voice and Tone*) —, à côté du plan `planned` quand il existe |
| Lot déjà présent au moment d'extraire | Extraction | L'erreur se lève **au clic sur « extraire les lots »**, pas dans la fenêtre de confirmation ; invite explicite d'écrasement |
| Échec d'une écriture | Partout | Interrompt la confiance : il se voit, il dit son motif, il laisse une prise manuelle. Jamais un message fugace comme seul porteur |

## Interaction Primitives

**Souris fine, clavier pour les gestes de précision.** C'est un poste de travail, pas un écran
tactile.

- **Clic** = désigner. **Double-clic** = ouvrir (`EPIC7-ARB-2`). Le clic seul ne navigue jamais.
- **Clic droit** = menu contextuel, inventaire complet en `## Menu contextuel`.
- **Absent ou grisé, ce n'est pas la même chose** (`EPIC7-ARB-24`) : un **onglet sans objet est
  absent** — il n'en aura pas ; un **contrôle temporairement indisponible est grisé** — il
  redeviendra actionnable. Le critère est la **réversibilité**, pas la disponibilité à l'instant t.
- **Glisser-déposer** de fichiers ou d'un dossier entier vers le chutier ou la zone tampon ;
  équivalent complet par la boîte de dialogue système.
- **Cases à cocher** pour toute sélection multiple (lots sur Pdf, fichiers du tampon avant
  détection) — jamais un `ctrl+clic` comme seul chemin.
- **Glisser une poignée** de coin ouvre la loupe ; le réglage se poursuit **au clavier**, flèches =
  un pixel.
- **Curseur de zoom** continu pour la taille des vignettes (pas de paliers).
- **Transport** entièrement pilotable au clavier : lecture/pause, image suivante/précédente,
  boucle, pose des points in/out, saisie directe d'un timecode.
- **Aller à un timecode** existe **aux deux endroits** (`EPIC7-ARB-39`) : dans la barre de menus,
  et à l'écran — le timecode affiché dans le lecteur est **cliquable et saisissable**.
- **Balayage** : glisser la poignée, marche/arrêt d'un clic, pause + image par image.

**Bannis partout :** une détection qui part toute seule au dépôt ; une écriture sans point de
jugement préalable ; un champ prérempli par déduction dans le formulaire de QR ; un tri « dernière
version » ; une action destructive sans avertissement explicite ; l'édition manuelle masquée quand la
détection se déclare satisfaite ; un badge d'état de projet reconstruit ; un message éphémère comme
seul porteur d'un échec.

**Le zoom dans la previz n'est plus à trancher.** Il a été répondu le 2026-08-20 : le zoom fait partie
du **jeu de contrôles de vue commun à toutes les surfaces d'image** — zoom, ajuster, pleine largeur,
pleine hauteur, 100 %, préréglages (correction A10) —, et la vue vignette unique zoome dans la frame
(`EPIC7-ARB-18`). C'est un composant, pas un réglage par écran.

**Profondeur d'annulation : 20 éditions, remise à zéro au changement de lot** (`EPIC7-ARB-6`, option
6a, « sans réserve »). L'annulation porte sur les **éditions réversibles d'état** — zone déplacée ou
redimensionnée, champ de QR saisi, case cochée, lot renommé, rattachement modifié — et **jamais sur un
traitement**, qui s'*interrompt* : le même mot pour les deux ferait croire qu'un encodage se défait.
L'écartement de frame n'en relève pas : ce n'est plus un geste depuis `EPIC7-ARB-16`. Ce qui reste à
spécifier est la **surface** de l'annulation — commande, menu Édition, raccourci —, signalé par la
revue du 2026-08-23 (W3) et versé au report, pas rouvert ici : la **valeur**, elle, est tranchée.

## Reprise du travail après interruption

*Section propre au produit.* Entre la planche générée et le scan, il se passe **trois semaines** : le
papier part, Camille peint, le prestataire numérise. L'application est fermée pendant tout ce temps.
Le produit doit donc répondre à une question qu'aucun tableau de bord classique ne pose : **où en
étais-je, sans que j'aie à m'en souvenir ?**

- **L'écran de gestion de projet ouvre chaque session**, dernier projet en tête. Il n'y a pas de
  reprise implicite dans le dernier atelier ouvert : on rentre par le projet.
- **L'état d'avancement se lit dans la forme de l'arbre**, pas dans un journal : sous le rush le lot,
  sous le lot la planche, et **rien après** = la chaîne est arrêtée à « planche produite ». Aucune
  question à se poser sur ce qui a été lancé.
- **Rien d'affiché ne dépend d'un état de session.** Ce que le chutier montre vient du projet sur le
  disque — donc survit à la fermeture, au changement de machine, au disque qui change de main.
- **La désignation de ce qui alimente l'encodage vit au manifest**, pas dans un état d'interface :
  elle voyage avec le projet *(cible non livrée — arbitrage 2)*.
- **Un état de conservation implicite est un mensonge.** Ce qui n'est pas écrit ne doit pas être
  présenté comme acquis ; une écriture qui échoue interrompt la confiance au lieu de la laisser
  intacte.
- **Aucun horodatage n'est affiché comme un tri** tant que la date de scan n'est pas au manifest :
  seul l'ordre saisi par l'opératrice est disponible.

## Composition d'un lot à partir de candidats

*Section propre au produit — état cible, non livré.* Plusieurs scans d'un même lot produisent, pour
une même frame, plusieurs **candidats**. Composer, c'est choisir lequel est retenu — jamais
supprimer.

**Priorité** (`EPIC7-ARB-53`, verbatim) : le lot composite est **secondaire pour le MVP de
l'interface**, « mais pas si tard ». Il vient **après** le Scan puis les Exports — reporté, pas
renvoyé à l'infini : ce qui se décide maintenant du chutier ne doit donc pas rendre sa venue
impossible.

- **L'invariant, garde centrale de la fonction :** le lot doit **rester ou devenir complet**.
  L'interface ne doit pas laisser *construire* un choix qui ferait disparaître une frame — la garde
  agit pendant la composition, pas en verdict après coup.
- **La granularité est à la frame.** Le choix en bloc par scan (« les pages que j'ai refaites
  l'emportent partout où elles font doublon ») est un **raccourci vers le même geste**, pas un second
  mécanisme : il reste **défaisable frame par frame**, et l'inverse n'a pas à être vrai.
- **Où ça se passe.** On **compare depuis la galerie** — clic sur une frame à plusieurs candidats,
  candidats affichés côte à côte, l'un désigné. On **vérifie en mode lecteur**, en mouvement, avant
  d'exporter. Comparer deux passes *entières* ne se fait pas côte à côte : on bascule de l'une à
  l'autre **au même timecode**, sans perdre son point de lecture. **Cette bascule ne s'applique
  qu'à une sélection multiple ou à un lot composite** (`EPIC7-ARB-21`, 2026-08-22) — elle n'a pas
  d'objet sur un lot reconstruit unique. Classée non prioritaire.
- **Trancher ne supprime rien.** Les candidats non retenus restent disponibles ; seule la sélection
  change, et un choix se défait.
- **Le lot composé est un lot à part entière** (`EPIC7-ARB-57`, qui **renverse** la version
  antérieure de cette spine — « variante datée du même lot »). Motif d'Egan, structurel : *« pas de
  stockage superflu car on n'a peut-être pas extrait les lots qui composent le lot composé »* — une
  variante supposerait un original pleinement extrait, ce qui n'est pas garanti. Composer crée donc
  une **branche sœur nommée** dans le chutier (icône **ou** mention *composite* + nom + date),
  l'original restant intact à côté. C'est le modèle de `key-lot-hybride`, cohérent avec le cœur
  post-5.12/5.14 qui numérote les passes.
- **Au dépôt d'un scan portant un lot déjà présent**, l'interface **ne refuse pas** : elle propose de
  **garder les deux** — le second lot porte un **suffixe visible dans l'arbre** (date ou numéro de
  version, vocabulaire à aligner sur 5.12 à sa réouverture), jamais un doublon indiscernable
  (`EPIC7-ARB-58`). Écraser reste possible, jamais forcé, et annoncé comme destructeur. Le même
  mécanisme s'applique par cohérence à l'extraction d'un lot déjà présent.

**[À TRANCHER]** — le choix entre l'icône et le mot *composite* (question d'i18n autant que de
graphisme, déjà signalé dans `DESIGN.md`). **[À TRANCHER]** — l'articulation avec le discriminant de
version du cœur (story 5.14 : un numéro à deux chiffres `-01`…`-99` **donné par l'opérateur**) : la
spine nomme les compositions par une date, le cœur numérote les passes ; rien ne dit si l'interface
montre ce numéro, le masque derrière la date, ou le demande.

## Préférences utilisateur et réglages projet

*Section propre au produit.* **La règle qui commande cette section : le réglage projet prime
toujours sur le réglage utilisateur** (`EPIC7-ARB-42`, verbatim : « Le réglage projet prend toujours
le pas sur un réglage utilisateur »).

C'est une **règle de préséance**, et elle est plus forte que le partage ligne par ligne qu'on
cherchait : un même réglage peut exister **aux deux niveaux**, et **le projet gagne**. La question
« où vit la cadence ? le preset d'export ? le profil de scanner ? le dossier de recherche ? » n'a
donc pas à être tranchée réglage par réglage — elle l'est par la règle, et la contradiction entre
cette spine et la maquette des Préférences se résout sans arbitrer sur chaque ligne.

**Ce que l'interface doit faire, et qui devient vérifiable :** *dire laquelle des deux natures
s'applique* au réglage qu'on regarde — et, quand la valeur existe des deux côtés, montrer que c'est
**celle du projet** qui est en vigueur. Une valeur affichée sans sa nature est un piège : elle ne dit
pas si la changer suivra l'utilisateur ou partira avec le film.

Deux natures, donc, que l'interface ne mélange jamais dans une même liste (`EPIC7-ARB-33`) :

- **les préférences utilisateur** valent pour toutes les sessions et tous les projets ; elles
  suivent l'utilisateur, pas le film ;
- **les réglages projet** vivent dans le fichier de projet et **voyagent avec lui** — quand Inès
  reçoit le projet de Camille, elle reçoit ces réglages ;
- une **valeur par défaut** est une préférence utilisateur qui sert à **initialiser** un réglage
  projet. Une fois le projet créé, **le projet fait foi** : changer le défaut ne modifie aucun
  projet existant.

> La frontière d'**affectation** reste volontairement imprécise, et Egan l'assume (2026-08-23) :
> elle se précisera à l'usage. Ce qui ne l'est plus, c'est l'**arbitrage en cas de doublon** — le
> projet l'emporte (`EPIC7-ARB-42`) — ni l'obligation de **dire laquelle des deux natures** porte le
> réglage affiché.

**Règle d'admission** (`EPIC7-ARB-29`) : les Préférences ne contiennent que des **réglages
effectifs**. Une ligne inerte y est du bruit — un invariant du produit se documente dans les spines,
il ne se met pas dans une surface d'action sous forme figée. Les invariants colorimétriques n'y
figurent donc pas.

| Section | Contenu | Origine |
|---|---|---|
| **Interface** | Thème · taille du texte de l'interface. **La langue n'y est pas en v1** (`EPIC7-ARB-52`) : aucune traduction n'étant livrée, un sélecteur de langue serait une ligne inerte — ce que la règle d'admission interdit ; il revient avec la première traduction | Aucune contribution du cœur ; ce sont des réglages de la GUI seule |
| **Fichiers** | Dossier de projets par défaut | Validé par Egan |
| **Performances** | **Budget mémoire du cache d'images décodées** — existe (`--memory-budget-mb`, 128 Mio aujourd'hui). Borne haute portée à **2 Go** ; la valeur par défaut est **à établir par la mesure**, pas par estimation. **Comportement en cas de retard** — deux politiques nommées du cœur, `report` et `skip` | `cadence_previz` |
| **Valeurs par défaut** | résolution d'export · liste des cadences proposées · profil de calibration. **Pas de dpi de scan** (`EPIC7-ARB-44`) | `EPIC7-ARB-32` |

**N'y figurent pas, et c'est décidé :**

- **ffmpeg** — fourni par l'application ou par l'installateur, jamais un champ de chemin
  (`EPIC7-ARB-35`). Un tel champ transforme un défaut d'installation en question posée à
  l'utilisateur, qui n'y répondra pas mieux ;
- **les consentements** — écraser, accepter une colorimétrie inconnue, accepter un lot incomplet.
  En faire un réglage permettrait de cocher « oui toujours » et **désarmerait les modales** ;
- **le mode de la file des tâches** — la bascule est dans la file elle-même (`EPIC7-ARB-26`) ;
- **le seuil de largeur** de bascule de la file — un nombre en pixels que personne ne sait régler
  sans l'avoir vécu, et que le geste règle déjà (Egan, 2026-08-23) ;
- **l'optimisation matérielle** — n'existe pas encore, et n'apparaîtra pas tant qu'elle n'existe
  pas (`EPIC7-ARB-30`) ;
- **un dpi de scan par défaut** (`EPIC7-ARB-44`) — `--dpi` est sans défaut **délibérément** (garde du
  cœur, risque R8) : un dpi faux fausse toute la géométrie sans lever d'erreur. Une préférence le
  réintroduirait **en le rendant invisible**, ce qui est exactement l'argument que cette spine oppose
  au préremplissage du formulaire de QR.

**Le dossier de recherche** est un **réglage projet** (`EPIC7-ARB-34`), pas une préférence. Tous les
sous-dossiers de la cible sont parcourus pour retrouver un média délinké, sur **trois** critères —
**nom, durée, timecode**. **Le relink manuel prend toujours le dessus** : la recherche automatique
est une commodité, jamais une autorité, et un fichier désigné à la main ne se fait pas remplacer au
chargement suivant. **[À TRANCHER]** — que faire quand deux fichiers satisfont les trois critères.

**Le cache disque** n'existe pas encore. Direction prise (`EPIC7-ARB-36`) : emplacement dans le
dossier applicatif du système par défaut mais **configurable**, purge **par projet et pour tous les
projets**, taille maximale à définir. Explicitement **à concevoir** avant toute maquette.

## Menu contextuel

*Section propre au produit.* Le clic droit n'a d'objet que lorsqu'une commande s'applique à **un
objet précis qu'on vient de désigner** — c'est ce qui le distingue d'un bouton de barre, qui agit
sur la sélection, et d'un menu système, qui agit sur l'écran.

**Règle** (`EPIC7-ARB-37`) : **sauf « rattacher à », aucune commande n'existe uniquement au clic
droit.** Une commande qu'on ne peut atteindre qu'en essayant le clic droit est introuvable pour qui
n'y pense pas. Corollaire : **une entrée grisée dit pourquoi**, dans le menu et non dans une aide,
et **le titre du menu nomme l'objet** — dans un chutier à six niveaux, savoir sur quoi on a cliqué
n'est pas un détail.

| Objet | Entrées |
|---|---|
| **Rush** | Relinker · **Rattacher à** *(seule commande sans autre chemin, voulue ainsi)* · Révéler dans le système · Retirer du projet |
| **Lot / extraction** | Révéler le dossier · **Supprimer le lot** — l'outil peut donc effacer ce qu'il a produit, ce qui n'était pas vrai avant `EPIC7-ARB-37` ; encadré par la modale d'écrasement |
| **Marqueur** | Éditer *(aussi au double-clic)* · Supprimer · **Convertir une durée entrée/sortie en marqueur de durée** |
| **Vignette de galerie** | Ouvrir en vue unique · Comparer les candidats · Voir la page de planche · Révéler le fichier |
| **Tâche** | Annuler / interrompre · **Ouvrir le dossier** · **Ouvrir le fichier** *(selon ce que la tâche a produit)* |
| **Projet, dans la liste** | Ouvrir · Révéler le dossier · **Épingler** *(résiste au tri par date)* · Retirer de la liste *(les fichiers ne sont pas touchés)* |

> **Le marqueur de durée n'existe pas encore.** Les marqueurs sont ponctuels. Un marqueur de durée
> touche la chronologie, le bus de transport et le format de projet : il est **à concevoir** avant
> d'être dessiné.

## Barre de menus système

*Section propre au produit.* Elle apporte trois choses, et une seule est indispensable : ce que le
système **exige** (À propos, Préférences, Quitter — sans quoi les Préférences sont inatteignables
avant l'ouverture d'un projet) ; l'**apprentissage des raccourcis clavier**, qui ne s'obtient nulle
part ailleurs sans les chercher ; et un **second chemin** vers ce qui existe déjà.

**Décidé** (`EPIC7-ARB-38`) : la barre est **relativement complète** — le second chemin est accepté,
avec son coût de maintenance connu — et **identique sur macOS et Windows**, sauf là où le système
l'interdit absolument. Egan donne le précédent : *DaVinci Resolve garde son menu applicatif sur
Windows*. Ceci **annule** la divergence qui avait été proposée sur la place des Préférences.

| Menu | Contenu |
|---|---|
| **mmu** | À propos · **Préférences** · Quitter |
| **Fichier** | Nouveau projet · Ouvrir · Importer · Récents · Fermer · **Exporter**, et l'export de fichiers spécifiques — un lot, un scan, un fichier de projet, un fichier de calibration |
| **Édition** | Les **opérations de création**, comme second chemin : créer un lot, créer une planche, lancer une extraction |
| **Affichage** | Ateliers · vues · ajuster et zoom · panneaux, **avec leur état coché** — c'est ce qui fait de ce menu autre chose qu'une liste de raccourcis · plein écran |
| **Aller** | Image précédente / suivante · entrée / sortie · marqueur précédent / suivant · **aller au timecode** |
| **Aide** | Exigé par les deux systèmes |

> **L'export de fichiers spécifiques n'existe nulle part ailleurs** — ni dans les maquettes, ni dans
> cette spine avant aujourd'hui. À instruire.

## Accessibility Floor

Comportemental. Le contraste et la couleur sont dans `DESIGN.md`.

- **Cibles tactiles : sans objet.** C'est du desktop à la souris ; la cible minimale de clic est
  `{spacing.hit-min}` et le produit exige au contraire un **pointage fin au pixel** (poignées de
  coin, points in/out). Aucun geste tactile n'est requis nulle part.
- **Le bus de transport est intégralement pilotable au clavier** — lecture, image par image, boucle,
  pose et saisie des points in/out. C'est le contrôle le plus utilisé de l'application ; il ne peut
  pas dépendre d'un geste fin.
- **L'édition des quatre coins est pilotable au clavier**, en mode loupe : sélection d'une poignée,
  déplacement d'un pixel par pression de flèche, validation. C'est la contrepartie exacte de
  l'exigence de pointage au pixel : ce qui demande de la précision à la souris doit être atteignable
  autrement.
- **Ordre de tabulation = ordre de lecture** sur chaque atelier ; `Échap` ferme toujours la surface
  la plus haute (modale, loupe, plein écran).
- **Les libellés ne se tronquent jamais**, et aucune boîte n'est calée sur la longueur d'**un**
  libellé : c'est la contrainte d'accessibilité, et elle tient seule. La règle de marge qui se calait
  sur l'anglais **tombe** (`EPIC7-ARB-52`) : l'anglais est hors v1, aucune chaîne anglaise n'existe,
  donc rien ne peut se mesurer contre elle. Ce qui la remplace est plus simple et vérifiable en
  français : une boîte accepte un libellé plus long que celui qu'elle affiche, sans le tronquer.
- **Redondance non chromatique des états — partiellement acquise, partiellement ouverte.** Les deux
  natures de manque sont déjà comptées séparément en `{typography.data}` (pages manquantes d'un côté,
  frames synthétiques de l'autre) : ce comptage est la redondance textuelle du couple
  `{colors.state-absent}` / `{colors.state-substitute}`, qui est précisément la paire la plus
  confusable en vision des couleurs déficiente. **[À TRANCHER]** : au niveau d'une **ligne de
  chutier**, l'arbitrage « pas de badge, le code couleur suffit » laisse l'état délinké porté par la
  seule couleur. C'est un arbitrage produit assumé, pas un oubli — mais il n'a pas de compensation
  décidée (mention textuelle sur la ligne, inspecteur, réglage de daltonisme).
- **[À TRANCHER]** — niveau d'engagement lecteur d'écran (VoiceOver / Narrateur / NVDA) : aucune
  décision nulle part. À trancher avec la technologie, dont il dépend directement.

### La couleur ne porte jamais seule

Un état de ligne de chutier ou de vignette est signalé par sa couleur **et par
une forme** : disque plein pour *complet*, anneau creux pour *absent*, disque
hachuré pour *mire de remplacement* (voir `{components.badge-state}`). La
couleur reste le signal premier — c'est elle qu'on balaie du regard — la forme
ne fait que la doubler.

Motif *(tranché le 2026-08-17)* : `{colors.state-absent}` et
`{colors.state-substitute}` sont la paire la plus confusable pour une vision
des couleurs atypique, et ce sont précisément les deux états que l'interface a
l'obligation de ne pas fondre. L'outil s'ouvrira à des vidéastes dont on ne
connaît pas la vision.

Cette exigence **nuance** la décision « pas de badge, le code couleur suffit » :
celle-ci portait contre un **badge textuel d'origine de projet**, pas contre une
redondance non chromatique. Rien ne revient sur l'absence de badge.

## Responsive & Platform

Pas de responsive au sens web : **une seule classe de surface**, le poste de travail. Ce qui varie,
c'est la taille de fenêtre et la plateforme.

| Sujet | Comportement |
|---|---|
| Redimensionnement | Le chrome garde **les largeurs qu'on lui a données** — réglables à la poignée pour le chutier et son panneau d'arborescence (`EPIC7-ARB-40`), constantes ailleurs ; la scène de previz absorbe le reste. Aucune recomposition qui déplacerait l'image. Sous une certaine largeur de fenêtre, le panneau d'arborescence **se rétracte seul**, le chutier passant avant lui, et son rail de rappel reste |
| Panneau de progression | Activable/désactivable depuis les 4 ateliers. **Les deux, par bascule** (`EPIC7-ARB-26`) : *ancrée*, elle rétrécit la scène ; *superposée*, elle flotte et l'image ne bouge pas. Superposée par défaut sous un seuil de largeur de fenêtre ; un choix explicite survit au franchissement du seuil. Le passage sous le seuil se fait **sans message** (`EPIC7-ARB-8`) : le lecteur voit que le panneau a changé de place, le lui dire est du bruit |
| Panneau détaché (fenêtre flottante) | Souhaité « pour plus tard, à juger en œuvre » — **hors v1** ; le plus simple d'abord |
| Taille minimale de fenêtre | **[À TRANCHER]** — en dessous de quoi chutier + scène + panneau ne tiennent plus |
| macOS 12+ / Windows 10+ | Boîtes de dialogue de fichiers **du système** ; glisser-déposer natif ; boutons *dossier* / *fichier* des cartes ouvrant le **Finder / l'Explorateur** ; les Préférences vivent où la plateforme les met |
| Matériel ancien | **Le repli de qualité est un comportement, pas un accident** : quand la machine ne tient pas la cadence, la previz dégrade l'image plutôt que la cadence, **et le dit**. Voir *État dégradé de la previz* |
| Machine de développement de référence | iMac Intel sous macOS 12. Ce n'est pas le pire cas toléré, c'est le **cas nominal** : l'outil doit être agréable dessus, pas seulement fonctionnel |
| Langue | **Français en v1, anglais hors v1** (`EPIC7-ARB-52`) : chaînes extraites dans un catalogue, aucune traduction livrée. Aucune mise en page ne dépend d'un libellé tenant sur une ligne |
| Scanner piloté depuis l'app | Évoqué, **non retenu en v1** : on part de scans réalisés |

## Cible non livrée

Quatre comportements décrits dans cette spine **ne sont pas dans le produit d'aujourd'hui**. Ils sont
tranchés côté produit et portés par **quatre stories d'Epic 5 qui passent devant l'Epic 7** : les
spines peuvent décrire l'interface cible, les stories 7.x non.

| Comportement | État réel aujourd'hui | Ce qui le débloque |
|---|---|---|
| **Ingest en vrac avec tri par QR** (P4) | La CLI ingère **un document à la fois**, sans tri automatique | Story d'Epic 5 : le tri par QR devient une fonction du cœur, la GUI l'expose, la CLI en bénéficie |
| **Versions multiples d'un lot** (P5) | Une seconde passe est **refusée** (« planche périmée ») ; aucune option ne lève le refus | Stories d'Epic 5 déjà spécifiées, prêtes à développer |
| **Date de scan au manifest** (P5) | Interdite par le schéma ; **aucun tri chronologique possible**, donc aucun nom de lot composé | Story 5.13, écrite, jamais développée |
| **Cadence source portée par le QR** (P2) | Absente : l'encodage exige une saisie manuelle de la cadence source | Payload **2.1**. Le lecteur bi-format est un **confort de développement** (garder les anciens scans comme fixtures) ; en production, 2.0 est abandonné et la rupture pour les tirages déjà imprimés est assumée — **mais seulement jusqu'au jalon ci-dessous** |

Tant que ces stories ne sont pas livrées, l'interface **ne doit pas simuler** le comportement cible :
pas de « dernière version », pas de tri chronologique, pas de dépôt en vrac silencieusement partiel.

> **Une échéance matérielle, et c'est la seule du plan** (`EPIC7-ARB-51`, ~2026-09-02). L'abandon de
> la rétrocompatibilité **reste acquis** pour les formats de projet et de manifeste. Il ne vaut pas
> pour le **payload imprimé** : à partir de ce jalon, **une planche sortie de l'imprimante doit rester
> décodable par toute version ultérieure**. Motif, et il est physique : le papier ne se met pas à
> jour, et ce qui compte est la relecture possible des planches. **Conséquence directe :** le passage
> au **payload 2.1**, qui casse la relecture des tirages déjà imprimés, se fait **avant** ce jalon —
> ou ne se fait plus.

> **Recommandation en cours d'instruction** (`EPIC7-ARB-49`) : les stories de versions multiples
> (5.12 / 5.13 / 5.14) **restent `deferred`** — le fichier propre à chaque détection peut absorber le
> besoin, et elles ne se rouvrent que si le modèle de candidats les redemande. Egan a posé la question
> sans la trancher ; rien de ce qui est décrit ci-dessus ne change tant qu'elle ne l'est pas.

## Fermeture de l'architecture d'information

Chaque besoin énoncé atterrit sur une surface, et chaque surface listée plus haut est atteinte par au
moins un flow — **sauf celles-ci**, à traiter comme dette de conception connue :

| Surface orpheline | Statut |
|---|---|
| **Préférences** | Décidée, **contenu explicitement renvoyé à un second temps**. Aucun flow ne l'ouvre, aucune spécification visuelle dans `DESIGN.md`. C'est l'orpheline assumée |
| **Marqueurs du bus de transport** | Décidés en détail (ponctuels ou plages, couleur, nom, description ; servent à préparer plusieurs zones d'in/out) et exercés par **aucun** parcours. **[À TRANCHER]** : gardés en v1 ou reportés ? |
| **Base de timecode par clic droit sur le rush** | Décidée, exercée par aucun parcours |
| **File d'attente d'exports réordonnable** | Décidée ; aucun parcours ne met deux exports en file ni n'en change l'ordre |
| **Dossiers d'organisation du chutier** | Décidés ; présents dans le préambule des parcours, dans aucune étape |
| **Re-scan partiel** (« marquer une page en rescan, remplacer cette page dans le lot ») | Décidé le 2026-08-16 ; **largement absorbé** depuis par le modèle de candidats (composition), qui remplace au grain de la frame. **[À TRANCHER]** : subsiste-t-il comme geste propre ? |

## Couverture des maquettes

Chaque surface de l'architecture d'information est ici classée. **Toutes sont rendues** — dix-huit
maquettes sous `mockups/` — **à trois exceptions assumées** et nommées plus bas. « Rendue » veut dire
dessinée, jamais « conforme aux jetons » : cette confrontation n'a eu lieu que sur quatre fichiers
(voir *Information Architecture*).

| Surface | Couverture |
|---|---|
| Chutier · zone tampon · section Calibration | `key-chutier.html`, puis `key-chutier-v2.html` |
| Atelier Pdf · aperçu vivant · barre de réglages · panneau de progression | `key-atelier-pdf.html` |
| Atelier Scan mode PDF · surimpressions · loupe · formulaire de QR | `key-scan-mode-pdf.html`, puis `key-scan-v2.html` |
| Scène de previz · mode lecteur · bus de transport · état dégradé | `key-mode-lecteur.html` |
| Atelier Extraction · sélecteur de cadence · galerie filtrée | `key-extraction.html`, puis `key-extraction-v3.html` |
| Badge de cadence, trois régimes | `key-cadence.html` |
| Lot hybride, extraction composite | `key-lot-hybride.html` |
| Atelier Exports · balayage · encodage | `key-exports.html` |
| Vue vignette unique · comparateur de candidats | `key-comparaison.html` |
| Cartes de tâches · panneau de progression, deux modes | `key-taches.html` |
| Écran de gestion de projet, trois états | `key-projet.html` |
| Modales — extraction, écrasement, calibration | `key-modales.html` |
| Préférences · menu contextuel · barre de menus | `key-preferences.html`, `key-clic-droit.html`, `key-barre-menus.html` — **rendues, puis leur logique reprise** (voir ci-dessous) |

**Trois surfaces restent hors maquettes, par décision :** le **mode vignette du chutier** et la
**lecture d'un autre lot pendant un encodage**, tous deux reportés par Egan ; et le **comparateur de
candidats** dans sa forme aboutie, *cible non livrée*.

> **La logique fonctionnelle se valide avant la surface** (`EPIC7-ARB-31`, 2026-08-23). Les trois
> maquettes de menus ont été remplies par convention plutôt que dérivées de ce que l'outil sait
> faire : le cœur expose 35 options de ligne de commande, dont **aucune** n'apparaissait dans la
> maquette de Préférences, alors que deux y avaient leur place. Depuis, toute surface dont le
> contenu n'est pas déjà contraint par cette spine passe par un **document fonctionnel validé** —
> découpage, liste, apport de chaque entrée — avant qu'une maquette soit produite. La règle vaut
> jusqu'à ce qu'Egan la lève ; la forme visuelle, elle, est validée.

## Key Flows

Ossature comportementale des cinq parcours. La source longue reste
`.working/parcours-utilisateurs-epic7-2026-08-17.md` (v2.1).

### Flow 1 — La chaîne complète (Inès prépare, Camille juge ; puis trois semaines)

1. Inès lance l'application ; l'écran de gestion de projet s'ouvre, elle crée le projet et désigne le
   dossier de travail.
2. Extraction : elle ajoute le rush (glisser-déposer), l'en-tête affiche source, résolution, cadence,
   durée ; les réglages sont préremplis, **rien n'est rouge**, l'extraction n'est pas bloquée.
3. Camille regarde en mode vidéo, puis en galerie, et active le toggle des frames supprimées pour
   voir d'un coup ce qui saute.
4. Bornes posées au transport puis affinées au timecode ; cadence /2 ajoutée d'un clic ; 16 bits par
   défaut, non discuté.
5. **Extract** → modale de confirmation : cadences cochables, **espace disque annoncé**. Carte de
   progression, exécution en arrière-plan, carte verte, lot posé **sous son rush**.
6. Double-clic sur le lot → atelier Pdf, ce lot ouvert. Réglages : **8 frames par page**, A4, marge
   de travail à 0 par défaut. **Les cardinaux offerts sont ceux qui existent** (`EPIC7-ARB-48`) :
   portrait 1, 2, 3, 4, 8 · paysage 1, 2, 4, 6, 8, **défaut 2**. « Six images par page » était une
   **erreur de ce parcours**, jamais une demande, et elle est corrigée ici. **L'orientation
   automatique n'est plus exigée** : elle n'existait que pour rendre atteignable un cardinal qui
   n'avait pas été demandé — l'orientation se lit au résumé de planche, elle ne se règle pas
   (correction A6).

   > *Pourquoi **8** et non le défaut du cœur.* Les deux corrections de ce jour ont d'abord posé
   > deux valeurs différentes ici — `2` dans cette spine, `8` dans la source longue — en citant le
   > même arbitrage. C'est exactement le défaut que la revue reprochait au corpus, et il est tranché
   > au lieu d'être laissé : **8**, parce que c'est le seul cardinal offert **dans les deux
   > orientations**. Le parcours de référence n'a donc pas à supposer une orientation, et ne
   > redevient pas dépendant du réglage qu'`EPIC7-ARB-48` vient de supprimer. Le défaut du cœur
   > reste `2` : ce parcours change donc un réglage, ce qui est aussi ce qu'il doit montrer.
7. **Premier point de jugement :** l'aperçu est vivant, chaque réglage redessine la planche. Elles
   choisissent quelle planche regarder parmi celles à générer.
8. Planche de calibration demandée en haut à droite (un mini-dialogue, le nom du scanner et rien de
   plus) ; elle se range dans la section Calibration. Génération : **une planche = un PDF**. Camille
   imprime.
9. Trois semaines. Peinture, pliage, découpe — jamais sur les angles ni le QR. Le prestataire
   numérise à 600 dpi.
10. Scan : dépôt du scan de calibration, **calibration scanner** (nom, dpi, format, commentaire) →
    profil créé. Dépôt des scans de planches : ils tombent dans la **zone tampon**.
11. Elle coche ce qui part et clique **Détecter** depuis le chutier. Cartes « détection » en file ;
    à la fin, **la complétude est annoncée** — rien n'est encore écrit.
12. Mode PDF : surimpressions, QR décodé, géométrie tenue sous la peinture. Elle bascule la
    calibration plusieurs fois pour juger. Mode galerie : aucun rouge.
13. **Second point de jugement :** mode lecteur, le lot se relit à sa cadence cible en qualité
    temporaire. C'est bon. **Alors seulement** elle lance l'extraction TIFF.
14. Exports : le lot reconstruit est là, cadence cible **sélectionnée par défaut**. Le rush original
    est sur le disque : son et balayage disponibles.
15. **Climax :** elle tire le wipe et l'image se transforme sous le curseur — à gauche l'image
    tournée, à droite la même passée par la gouache et le scanner. Même cadrage, même timecode, même
    mouvement. Elle met en pause, rejoue **image par image**, coupe et remet le wipe d'un clic. Le
    geste de la main est entré dans le plan, et il s'inspecte frame à frame.
16. Réglages d'export (taille estimée, nom et destination prévisionnels), enregistrés comme
    **preset**. Encodage ; la previz se bloque ; carte verte, deux boutons.

**Échecs.** Lot déjà existant → l'erreur se lève **au clic sur « extraire les lots »**, pas dans la
modale de confirmation ; invite explicite d'écrasement, jamais forcée. Métadonnée essentielle
manquante → champ rouge et action bloquée avant même la modale.

### Flow 2 — Reprendre sans les rushes (Inès, sa station, le disque est resté chez Camille)

1. Elle **ouvre le projet qu'on lui a transmis** : rushes déclarés, lots, planches — sans les médias.
   *(Cas nominal : le projet transmis, pas un projet vide.)*
2. Les rushes sont **en rouge** dans tous les chutiers : déclarés, absents de cette machine. Aucun
   badge, aucune mention — le code couleur suffit.
3. Scan : dépôt des scans reçus, cases cochées, **détection** lancée depuis le chutier. Les lots
   qu'elle voyait déjà se peuplent de leurs pages ; complétude annoncée.
4. Galerie, puis **mode lecteur** : le lot se relit à sa cadence cible. Assez pour juger. Elle lance
   l'extraction.
5. Exports : le lot reconstruit est là. Le lecteur ne propose **ni son ni balayage** — le rush n'est
   pas sur cette machine. Si Camille le lui envoie, elle **relinke** : le rouge tombe, le son et le
   wipe reviennent.
6. **Climax :** le master s'écrit à la cadence source, timecodes réinjectés, **sans que l'outil ne
   lui ait rien demandé** — la cadence source est portée par le QR. Un film reconstruit depuis des
   feuilles de papier, sur une machine qui n'a jamais vu le rush, et **sans un seul coup de
   téléphone**. *(Étape cible : dépend du payload 2.1.)*

**Variante.** Sans le projet : elle crée un projet vide, le dépôt des scans suffit, les QR
reconstruisent l'arborescence à l'envers. Identique à partir de l'étape 3.

**Échecs.** Un projet né du scan seul ne porte ni résolution source, ni politique d'arrondi, ni
empreinte de sélection : l'interface le **dit**, sans champ vide accusateur ni proposition de
compléter. Tant que 2.1 n'est pas livré, l'encodage réclame la cadence source à la main — c'est
exactement le coup de téléphone qu'on veut supprimer.

### Flow 3 — Un scan qui ne passe pas (Camille ; elle a plié la page 4, le pli traverse le QR)

1. La détection finit : le lot ressort **incomplet**, dit par le code couleur, **avant toute
   écriture**.
2. Galerie : six images en `{colors.state-absent}`, rangées à leur place par timecode. Elles font une
   page.
3. Clic sur une image rouge → mode PDF **sur la page fautive**, pas au début du document.
4. La surimpression dit tout : les quatre marqueurs sont détectés, la page est lue géométriquement,
   mais le **QR est marqué non décodé** — donc **aucune zone d'image n'est proposée**.
5. Clic sur le QR → formulaire. **L'interface ne la laisse pas chercher :** à chaque champ pris, la
   zone correspondante du scan est **pointée à l'écran**, avec zoom si la peinture gêne. Elle lit,
   elle recopie. Rien n'est prérempli.
6. QR complété, l'outil propose les zones. **C'est Camille qui juge** : la sixième est de travers, le
   pli a déplacé un coin — l'outil n'a rien signalé, il n'a aucun moyen de le savoir.
7. Elle attrape le coin, la **loupe s'ouvre seule**, elle règle au pixel. **Rien à relancer** : la
   position vient d'être posée à la main, l'outil **actualise la complétude**, c'est tout.
8. **Climax :** mode lecteur, le lot entier relu à sa cadence. Les frames défilent dans l'ordre et
   **la peinture d'une page pliée passe comme les autres**. La réparation se prouve sur le mouvement,
   pas sur une pastille verte.
9. Second défaut, d'une autre nature : une frame trop froide. Elle est là, elle est mal calibrée.
   Plein écran, bouton *éditer* → page PDF, bascule de profil de calibration, le rendu revient, elle
   relance la détection **de cette page** avec ce profil.

**Échecs et invariants.** Une frame **absente** et une **mire de remplacement** ne sont pas la même
chose et ne se fondent jamais en un seul indicateur : un lot à mires n'est pas complet même si aucune
page ne manque. L'ajustement des quatre coins est accessible **en permanence**, y compris quand la
détection se déclare satisfaite : passer par-dessus l'outil est un **droit de reprise en main**. La
lecture automatique des informations imprimées est **reportée** (`deferred-work.md`) — un champ
prérempli faux est plus dangereux qu'un champ vide, parce qu'il n'appelle pas la vérification.

### Flow 4 — S'arrêter à la planche, et revenir (Inès, trois semaines plus tard)

1. Génération finie : carte verte, un PDF, un dossier au nom du lot. Elle clique le bouton
   **dossier**, envoie à l'imprimeur, **ferme l'application**.
2. Trois semaines. Camille peint ; les planches partent chez le prestataire.
3. Inès rouvre : écran de gestion de projet, **dernier projet en tête**, elle l'ouvre.
4. **Climax :** le chutier lui dit exactement où elle en était **sans qu'elle ait à se souvenir**.
   Sous le rush le lot, sous le lot la planche, et **rien après** : la chaîne est visiblement arrêtée
   à « planche produite ». Elle n'a pas à se demander si elle avait lancé le scan.
5. Le prestataire renvoie **des centaines de pages en vrac**, mêlant plusieurs lots et parfois
   plusieurs projets. Elle désigne le dossier entier : tout atterrit dans la **zone tampon** — c'est
   là qu'elle prend tout son sens, elle absorbe un vrac que personne ne peut trier à la main.
6. Détection sur tout : l'outil **range chaque page sous son lot** par les QR. Le vrac est devenu une
   arborescence. *(Étapes 5-6 : cible — l'ingest en vrac est une story d'Epic 5 en amont.)*

**Échecs.** Ce que la détection **ne rattache pas reste dans le tampon**, visible et nommé, plutôt
que de disparaître : c'est là qu'on va voir ce qui a résisté. Un vrac partiellement rattaché n'est
jamais annoncé comme un rattachement complet.

### Flow 5 — Essayer, refaire, composer (Camille ; elle ne sait pas encore comment traiter ce plan)

1. Elle extrait à **deux cadences** en une passe, mêmes bornes : deux lots sous le même rush,
   distingués par leur cadence. *(Livré.)*
2. Sur Pdf, elle coche les deux lots et demande deux dispositions : les planches se génèrent, une par
   lot et par disposition. Elle imprime, elle peint — les deux traitements ne se ressemblent pas,
   c'est le but.
3. Scan, détection, **mode lecteur**. Elle n'aime pas ce qu'elle a fait sur le premier lot. **Elle
   n'extrait pas. Rien n'a été écrit.**
4. Elle réimprime la même planche, la retravaille autrement, la rescanne. Le fichier tombe dans la
   **zone tampon** : l'outil ne sait pas encore que c'est un second tirage. C'est la **détection**
   qui le rattache **au même lot**. *(Aujourd'hui le produit refuse la seconde passe — cible.)*
5. Au dépôt, l'interface **propose de garder une nouvelle version** ; écraser reste possible, jamais
   forcé, et annoncé comme destructeur.
6. Elle compare les deux passes **l'une après l'autre**, au même timecode, sans perdre son point de
   lecture.
7. Sur neuf pages, elle n'en a refait que trois : le second scan n'apporte pas un lot entier, il
   apporte des **candidats** pour ces frames-là. Ailleurs il n'y a qu'un candidat, rien à décider.
8. Elle tranche **en bloc** — les frames du second scan l'emportent partout où elles font doublon —
   puis, sur deux frames, elle hésite : clic dans la **galerie**, candidats côte à côte, elle garde
   l'un pour l'une, l'autre pour l'autre. Le reste du choix en bloc ne bouge pas.
9. **Climax :** ce n'est plus « choisir une version », c'est **monter les deux**. Mode lecteur : le
   lot composé se relit à sa cadence, avec exactement les frames désignées — le montage de ses deux
   passes **en mouvement**, pas en vignettes. Le lot est unique, complet, composite ; la granularité
   est **à la frame**, le choix en bloc n'était qu'un raccourci vers le même geste ; et l'outil ne
   l'a laissée composer que parce que le lot **reste complet** — aucune frame n'a disparu, et aucun
   choix ne pouvait en faire disparaître une.
10. Elle exporte. Le master porte le lot composé ; la composition est inscrite dans le projet et
    survit au disque qui change de main. Les candidats non retenus **restent là** — trancher n'a rien
    supprimé.

**Échecs.** Un choix qui viderait une frame de tout candidat n'est **pas constructible** : la garde
agit pendant la composition. Un choix en bloc reste **défaisable frame par frame**. Sans date au
manifest, un lot composé **n'a pas de nom** et deux compositions successives seraient
indistinguables : tant que la story n'est pas livrée, l'interface ne peut trier les passes que dans
l'ordre saisi par l'opératrice.
