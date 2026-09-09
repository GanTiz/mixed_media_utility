# Réconciliation d'entrée — `gui-prototype/index.html`

> **Objet.** Chasse aux écarts entre la maquette GUI interactive (1091 lignes,
> commit `8ae88da` du 2026-08-16, « purement indicative ») et l'aval de la
> session UX : le memlog (`.memlog.md`, 122 entrées), les parcours utilisateurs
> v2.1 (`.working/parcours-utilisateurs-epic7-2026-08-17.md`) et la découverte
> (`.working/decouverte-epic7-2026-08-16.md`).
>
> Ce n'est pas un résumé de la maquette. C'est la liste de ce qu'elle porte et
> qui n'a survécu nulle part, de ce qu'elle contredit, et de ce qu'elle décrit
> d'un produit qui n'existe plus.
>
> **Avertissement de lecture, à porter en tête.** Le message de commit de la
> maquette dit lui-même : *« AUCUNE validation de l'utilisateur ; NE PAS servir
> de modèle pour la technologie ni pour l'UX. À n'utiliser que comme support de
> discussion. »* Et elle a été écrite le 2026-08-16 au soir, **avant les sept
> arbitrages du 2026-08-17**. Sa section 4 ci-dessous est donc la plus
> importante du document : plusieurs de ses écrans montrent une conception que
> la session a explicitement abandonnée depuis.
>
> **Bilan : 30 éléments perdus, 7 contradictions, 13 zones périmées.**

---

## 1. Ce que l'input apporte et qui est bien arrivé

Rappelé sans détail — ces points sont dans le memlog, ils n'ont pas besoin
d'être rattrapés.

* Écran de gestion de projet au lancement, projet courant mis en évidence.
* Quatre onglets en bas façon Resolve : Extraction · Pdf · Scan · Exports.
* Chutier à gauche, arbre rush → lots, ouverture d'un lot dans la page Pdf.
* Bandeau d'informations du rush en haut de l'atelier Extraction.
* Previz Extraction à deux modes (vidéo / galerie), avec zoom de galerie,
  toggle des frames écartées, vue agrandie **timecode au-dessus de l'image** et
  bouton retour.
* Bus de transport complet : lecture, pas à pas, boucle, volume, champs de
  timecode in/out, flèches de bascule inter-cadences.
* Panneau latéral de progression ancré à droite, ouvrable/refermable, avec une
  carte par tâche : nom de la fonction, nom du lot, barre, compteur.
* Carte finie : passage au vert, boutons « Ouvrir » et « Montrer ».
* Fenêtre de confirmation d'extraction listant les cadences avec cases à
  cocher, et l'erreur de lot existant levée **au clic**, pas dans la fenêtre.
* Cadence cible par défaut = cadence originale ; profondeur 16 bits par défaut.
* Métadonnées source préremplies, champ en rouge et extraction bloquée si une
  métadonnée essentielle manque.
* Lots nommés automatiquement (nom du rush + cadence + condensat des bornes).
* i18n anglais par défaut, français disponible.

---

## 2. Ce qui a été perdu en route

Trente éléments. Pour chacun : ce que la maquette propose, où, et pourquoi il
ne se retrouve nulle part en aval.

### 2.1 Gestion de projet et cadre de l'application

**G01 — Ouvrir un projet qui n'est pas dans le registre (« Browse… »).**
*Maquette :* deux actions sur l'écran de lancement, `Create new project` et
`Browse…` (l. 266-267, gestionnaire l. 1040).
*Aval :* le memlog décide un registre local de projets et le dernier projet en
tête (entrée 17), jamais le chemin d'ouverture d'un projet **absent du
registre**. Or **P2 étape 1 en dépend entièrement** : Inès « ouvre le projet
qu'on lui a transmis » — un projet qui, par construction, n'a jamais été ouvert
sur sa machine et ne peut pas figurer dans son registre. Le parcours nominal de
P2 passe donc par une surface que personne n'a décidée.

**G02 — Ce qu'une ligne de projet affiche.**
*Maquette :* icône, nom, **chemin complet**, **nombre de rushes**, et **date de
dernière ouverture** alignée à droite (l. 586-594).
*Aval :* le memlog ne décrit que l'ordre de la liste. Le contenu d'une ligne
n'existe nulle part — et c'est ce qui permet de distinguer deux copies du même
projet sur deux disques, situation nominale d'un projet qui circule.

**G03 — Nom de projet distinct du dossier, avec emplacement par défaut.**
*Maquette :* la modale de création demande deux choses, `Project name` et
`Target folder` prérempli à `~/Movies/mmu-projects` (l. 419-433).
*Aval :* le memlog dit « projet = un film = un dossier cible choisi par
l'utilisateur » (entrée 16) — un seul champ. La maquette suppose un nom
d'affichage indépendant du dossier, et un emplacement de rangement par défaut.
Ni l'un ni l'autre n'est tranché.

**G04 — Fil d'Ariane permanent du chemin du projet ouvert.**
*Maquette :* le chemin du projet est affiché en permanence dans l'en-tête
(l. 276, alimenté l. 601).
*Aval :* rien. Sur un outil dont la promesse est de travailler à deux sur des
machines différentes, savoir en permanence **où on écrit** n'est pas un détail.

**G05 — Commutateur de langue permanent, et repli sur l'anglais.**
*Maquette :* bascule EN/FR dans l'en-tête, active à tout moment (l. 278-281,
1042-1043) ; la fonction de traduction retombe sur l'anglais puis sur la clé
quand une chaîne manque (l. 514).
*Aval :* le memlog tranche la politique de langue (entrée 19) mais jamais **où
l'utilisateur change de langue**, ni ce qui s'affiche quand une traduction
manque. Une interface livrée en deux langues sans surface de bascule est une
interface mono-langue.

**G06 — La phrase qui dit ce qu'est l'application.**
*Maquette :* sous le titre du lanceur, « Workflow supervisor — extract, print,
scan, rebuild », traduit en « **Pupitre de workflow — extraire, imprimer,
scanner, reconstruire** » (l. 260, 443, 478).
*Aval :* aucune formule de présentation nulle part. C'est pourtant la seule
phrase que verra quelqu'un qui ouvre l'outil sans savoir ce qu'il fait — et
elle reprend le mot « pupitre » d'`epics.md`. Idée qualitative typique de
celles qui se perdent.

**G07 — Bouton de progression avec pastille d'état dans l'en-tête.**
*Maquette :* le bouton qui ouvre le panneau latéral porte une **pastille
verte** (l. 282-285).
*Aval :* le memlog décide le panneau (entrée 40) mais pas son point d'entrée.
La pastille dit « quelque chose tourne » **panneau fermé** — c'est ce qui rend
acceptable de le fermer.

**G08 — Le panneau s'ouvre tout seul au lancement d'une tâche.**
*Maquette :* `launchJobs` dé-masque le panneau latéral (l. 802).
*Aval :* rien. Sans cela, l'opératrice clique « Extraire », ne voit rien
bouger, et reclique.

**G09 — Signaler qu'un clic va téléporter.**
*Maquette :* chaque lot du chutier rushes porte un chevron `↗` intitulé
« open in Pdf » (l. 628).
*Aval :* le memlog décide le **comportement** (cliquer un lot ouvre la page
Pdf, entrées 39/41) mais aucun signe visuel ne prévient. Un clic qui change
d'atelier sans le dire est un défaut classique.

### 2.2 Atelier Extraction

**G10 — Le manque de métadonnée rappelé en haut, pas seulement en bas.**
*Maquette :* quand une métadonnée essentielle manque, un badge rouge apparaît
dans le **bandeau du rush** en plus du champ rouge du panneau du bas
(l. 650, 664, 694).
*Aval :* le memlog (entrée 31) ne prévoit que le champ rouge. Le panneau du bas
peut être hors du regard ; le blocage se découvre alors au clic sur Extract
sans qu'on sache où chercher.

**G11 — Refuser en disant pourquoi, plutôt qu'un bouton grisé.**
*Maquette :* le bouton Extract reste **actif** ; le clic lève un message
explicite « Métadonnée essentielle manquante (reel). » (l. 770-772).
*Aval :* le memlog dit « extract bloqué tant que non complété ». La forme du
blocage n'est pas décidée. C'est exactement la doctrine que la session a tirée
de l'incident de la relecture perdue (memlog 92, 116 : *un échec doit se voir,
et dire son motif*) — la maquette l'appliquait déjà.

**G12 — Quelles métadonnées source, et laquelle est essentielle.**
*Maquette :* quatre champs nommés — **Reel, Camera, Lens, Timecode base**
(l. 664-667) — et `Reel` désigné comme essentiel (l. 772).
*Aval :* le memlog dit « métadonnées source préremplies, modifiables ; si une
métadonnée **essentielle** manque, champ rouge ». La liste n'existe nulle part,
ni le critère qui rend une métadonnée essentielle. C'est un trou directement
bloquant pour une story 7.x.

**G13 — Le rang de sortie sur la vignette.**
*Maquette :* chaque vignette de galerie porte son **rang** en pastille, en plus
du timecode (l. 150, 726).
*Aval :* le memlog ne parle que du timecode (entrée 22). Or le rang de sortie
(`output_rank` du contrat 3.5) est ce qui identifie une frame **dans le lot** —
le timecode identifie sa position dans le rush. Les deux ne se substituent pas.

**G14 — Une case à cocher par vignette.**
*Maquette :* chaque vignette porte une case, cochée pour les frames retenues
(l. 151-153, 727).
*Aval :* rien — et c'est un écart **structurant**, pas cosmétique. La découverte
pose pourtant « à chaque étape l'utilisateur doit pouvoir **sélectionner des
images** » (memlog 9). Toute la conception aval suppose au contraire une
sélection **calculée** (cadence + bornes) et jamais retouchée à la main. La
maquette suggère qu'on peut décocher une frame ; personne n'a tranché.

**G15 — Le zoom de galerie change le nombre de colonnes.**
*Maquette :* six crans qui pilotent 3, 4, 6 ou 9 colonnes (l. 719).
*Aval :* le memlog dit « zoom sur la taille des miniatures » (entrée 22). Le
zoom comme **densité de grille** (et non comme agrandissement continu) est un
choix qui n'a pas été refait.

**G16 — Le compte de frames par cadence dans la fenêtre de confirmation.**
*Maquette :* chaque ligne de cadence affiche « *n* frames » (l. 777).
*Aval :* P1 étape 7 a gagné à la relecture l'annonce de **l'espace disque
requis**, mais pas le nombre de frames. Les deux se complètent : l'un dit ce que
ça coûte, l'autre dit ce qu'on obtient — et c'est le second qui répond à la
question de Camille (« cinquante images à peindre plutôt que cent »).

**G17 — Notifications transitoires.**
*Maquette :* un système de toasts en bas d'écran, deux variantes (succès /
erreur), effacement automatique à 2,6 s (l. 247-251, 1076-1083).
*Aval :* rien — l'aval ne connaît que les cartes du panneau latéral, qui
persistent. À réintégrer **avec réserve** : un message d'erreur qui s'efface
tout seul en 2,6 s contredit frontalement la leçon du memlog 92/116 (un échec
doit laisser une prise à la main). La bonne forme est probablement : toast pour
les succès, persistance pour les échecs.

### 2.3 Atelier Pdf

**G18 — Dire à l'écran que ce qu'on regarde est un plan, pas le PDF.**
*Maquette :* l'aperçu est coiffé de la mention « **Plan affiché — PDF pas
encore rendu** » (l. 475, 510, 877).
*Aval :* le memlog décide un « aperçu LIVE en direct » (entrée 44) et P1 étape
12 un « aperçu vivant », sans jamais dire à l'utilisatrice **ce qu'elle
regarde**. C'est pourtant la distinction `planned` / `rendered` du contrat 4.9,
et P1 fait de cet aperçu un **point de jugement avant écriture** : juger sur un
dessin en croyant juger sur le produit est précisément le risque.

**G19 — L'aperçu empile toutes les pages de la planche, défilables.**
*Maquette :* toutes les pages sont rendues et le conteneur défile (l. 876-878,
902-920).
*Aval :* le memlog dit « on sélectionne quelle planche prévisualiser parmi
celles à générer » (entrée 44) — le grain est la **planche**. Comment on
navigue **les neuf pages d'une planche** (P1 étape 14) n'est décidé nulle part.

**G20 — La légende de ce qui est posé sur la page.**
*Maquette :* sous la grille de zones, une ligne « ArUco ids 12,13 · patch P1 »
avec ses pastilles de couleur (l. 915-918).
*Aval :* rien. Dire quels marqueurs et quel preset de patchs sont posés, sans
prétendre les dessiner à l'échelle, est une réponse honnête et bon marché à la
question « qu'est-ce qu'il y a sur ma planche à part mes images ».

### 2.4 Atelier Scan

**G21 — La vue en liste des pages du lot.**
*Maquette :* une ligne par fichier de page, portant miniature, **nom de
fichier** (`page_003.tif`), badge **QR ✓/✕**, badge du **gabarit retenu**,
badge de **calibration** (ok / degraded), et le **résidu** (l. 937-958).
*Aval :* les trois modes de previz Scan décidés en aval sont **PDF, galerie et
lecteur** (memlog 57, 97) — aucun ne donne l'état de **chaque page d'un coup**.
On voit une page à la fois (mode PDF), ou des frames (galerie), ou le
mouvement (lecteur). Cette vue tabulaire est la seule qui réponde à « où en
est ce lot, page par page », et elle disparaît intégralement.

**G22 — Le résidu de reprojection, affiché par page.**
*Maquette :* `0.04mm`, `0.05mm`, `0.11mm` en colonne (l. 938-940).
*Aval :* rien. C'est le chiffre qui dit si la géométrie **tient**, avant même
de regarder les images — et il distingue une page correcte d'une page qui va
produire des cadrages faux sans rien signaler.

**G23 — La provenance du gabarit : QR ou manifest.**
*Maquette :* chaque page déclare `src: "QR"` ou `src: "manifest"`, avec la note
« gabarit du QR » / « gabarit du manifest » (l. 938-941, 952).
*Aval :* rien. Un gabarit venu du manifest plutôt que du QR veut dire que
l'outil a **supposé** au lieu de lire — l'information est portée par le contrat
et par un avertissement dédié, et elle n'atteint aucune surface.

**G24 — Le compteur de frames synthétiques dans le bandeau du lot.**
*Maquette :* « pages 4 · frames 14 · **synthetic 1** » (l. 935-936).
*Aval :* la **mire** de remplacement est bien arrivée (memlog 86, P3), et P3
exige explicitement « deux natures de manque, **deux comptages** » — mais
**aucune surface ne porte ces comptages**. La maquette les pose en tête du lot,
là où on les lit avant d'ouvrir quoi que ce soit.

**G25 — Le sélecteur de version au scan.**
*Maquette :* un menu `Version` avec `-01 / -02 / -03` dans les réglages du bas
(l. 962).
*Aval :* absent — voir aussi la contradiction **C4** en section 3, car cet
élément n'est pas seulement perdu : il est incompatible avec ce que P5 suppose.

### 2.5 Atelier Exports

**G26 — Dire pourquoi l'interface n'a rien demandé.**
*Maquette :* la zone des candidats affiche « **Candidat unique —
auto-sélectionné** » quand il n'y a rien à choisir (l. 980-981, clés 473).
*Aval :* rien. Une interface qui choisit en silence et une interface qui dit
« j'ai choisi parce qu'il n'y avait qu'un candidat » ne produisent pas la même
confiance — et la seconde prépare l'utilisatrice au jour où il y en aura deux.

**G27 — La fiabilité du timecode, à côté du profil.**
*Maquette :* un badge `reliable` / `best effort` accolé au profil de sortie
(l. 990, clés 474).
*Aval :* rien. Or tout le produit existe pour préserver des timecodes, et le
choix d'un profil de livraison (`h264_delivery`, `hevc_delivery`) les dégrade.
Sans ce badge, le réglage le plus lourd de conséquence de l'atelier Exports se
prend à l'aveugle.

**G28 — L'origine de la résolution retenue.**
*Maquette :* « 4096×2160 — *origin: native* » (l. 992).
*Aval :* rien. Le memlog expose la résolution comme réglage (entrée 66) sans
jamais dire **d'où vient la valeur proposée** — défaut, registre, native, ou
saisie. Sur un lot reconstruit depuis des scans, où la résolution source est
structurellement absente (P2), c'est l'information qui évite un contresens.

**G29 — Le consentement d'écrasement du master.**
*Maquette :* une case « overwrite (consent) » dans les réglages d'export
(l. 1006).
*Aval :* **rien du tout**. Aucun parcours ne rencontre un master déjà présent.
La maquette pose au moins la question ; sa **forme** est en revanche contestable
(voir C7).

### 2.6 Vocabulaire visuel

**G30 — La grammaire d'états, et la typographie des identifiants.**
*Maquette :* quatre états de badge — `ok` vert, `warn` ambre, `err` rouge,
`off` gris « non applicable » (l. 218-222) ; **police à chasse fixe** pour tout
ce qui est identifiant (noms de lots, timecodes, chemins, l. 34 et emplois) ;
thème sombre dense de station de travail.
*Aval :* le code couleur est **la** pièce la plus sollicitée de la conception —
rouge du média absent (memlog 72, 100), rouge de la frame manquante (60), vert
du lot complet, « code couleur de complétude » (97), et la conclusion des
parcours dit que le chutier « est le point où une erreur de conception coûterait
le plus cher ». Il n'est pourtant **défini nulle part** : ni la liste des états,
ni ce qu'est l'ambre, ni l'existence d'un état « non applicable ». La maquette
propose quatre états ; la conception aval en utilise implicitement au moins
cinq (absent, incomplet, complet, dégradé, non décodé) sans les nommer.

---

## 3. Ce qui a été contredit

L'input dit A, une décision postérieure dit B. Les deux sont donnés ; aucun
n'est tranché ici.

| # | La maquette (2026-08-16, soir) | La décision postérieure |
|---|---|---|
| **C1** | Les frames écartées par la cadence s'affichent en **rouge, pointillé, avec une croix** (l. 148-149) | memlog 24 (2026-08-16) : « frames SUPPRIMÉES en **grisé** ». Et surtout memlog 60 + P3 (2026-08-17) réservent le **rouge** à « il n'y a rien ici » — une frame écartée n'est pas une frame manquante, la collision sémantique est frontale |
| **C2** | Le bandeau du haut porte la **base de timecode** et l'**espace couleur** du rush (l. 648-649) | memlog 21 (2026-08-16) limite le bandeau à source / résolution / cadence / durée ; memlog 29 place la base TC **au clic droit sur le rush dans le chutier** et memlog 27 l'espace couleur **au panneau du bas**. La maquette les duplique en haut |
| **C3** | Les réglages Pdf exposés sont **gabarit, preset de patchs, frames/page, format, orientation, dpi** (l. 883-891) ; la **marge de travail** est absente | memlog 45-46 (2026-08-16) : exposés = frames/page, format, **marge** ; **non exposés** = gabarit (imposé), dpi (toujours 600), mapping gamut/patchs ; orientation **déterminée automatiquement**. Quatre des six réglages de la maquette sont désormais interdits d'exposition |
| **C4** | Le discriminant de version est **choisi par l'opératrice** dans les réglages (`-01/-02/-03`, l. 962) | P5 étape 5 (2026-08-17) : « c'est la **détection** qui le rattachera au même lot ». memlog 110 remplace la version par des **candidats**. Rien ne dit plus qui numérote une seconde passe — voir aussi le rapport `reconcile-extraction-sources.md`, élément **E27**, où la source amont démontre que ce discriminant **ne peut pas être dérivé** |
| **C5** | Un candidat se nomme `rush_plan_12@12-<c8a2>` — nom du lot + **condensat d'impression** (l. 982) | memlog 114 / arbitrage 7 (2026-08-17) : icône (ou mention **composite**) + **nom du lot commun aux deux scans** + une **date**. Deux conventions de nommage incompatibles pour la même chose |
| **C6** | Le chutier de l'atelier Pdf est **séparé**, à plat, liste de lots, **sélection unique** (l. 348-350, 859-864) | memlog 42 (2026-08-16, RÉVISION) : chutier **commun** Extract/Pdf, arbre rush → lots → planches, sélection par **cases à cocher**, multi-lots, sélectionner le rush = sélectionner tous ses lots |
| **C7** | `overwrite` est une **case à cocher dans le panneau de réglages** (l. 1006) | Contrat 6.4 (source amont, section 6) : *« `overwrite` n'entre pas au document : c'est un **consentement**, et la GUI le demande comme consentement, jamais comme paramètre »*. Une case persistante dans un panneau de réglages est exactement ce que la règle interdit |

---

## 4. Ce qui est périmé

**La maquette décrit un produit qui n'existe plus.** Cette section est celle à
lire avant de rouvrir le fichier : plusieurs de ses écrans, pris pour argent
comptant, feraient ré-implémenter une conception abandonnée.

**Les quatre décisions lourdes postérieures, une par une :**

**Z1 — Le déroulé en deux temps de l'atelier Scan (memlog 97, 2026-08-17).**
La maquette a **un seul bouton**, « Scanner + détecter » (l. 964), qui fait tout
d'un coup et écrit les frames. La conception actuelle sépare (1) la
**détection**, déclenchée **depuis le chutier**, non automatique, qui produit
déjà la position des frames et un aperçu sans rien écrire, de (2)
l'**extraction** en TIFF. Le point le plus visible : dans la maquette, **rien
ne permet de juger avant d'écrire**. *Trace amusante et significative :* la
maquette porte déjà une clé de traduction inutilisée, `scan.reconstruct` =
« Reconstruire les frames » (l. 467, 502) — l'intuition du deux-temps était là,
sans surface.

**Z2 — Le mode lecteur (memlog 97).** Il n'existe pas dans la maquette, et rien
n'en tient lieu. C'est pourtant devenu le **second point de jugement avant
écriture** de P1, la conclusion de P3, et le lieu où l'on vérifie un lot composé
en P5. Un lecteur de rush reconstruit « en qualité temporaire » est aujourd'hui
une pièce centrale de l'atelier Scan ; la maquette n'a même pas de galerie Scan.

**Z3 — La zone tampon du chutier (memlog 119, 2026-08-17).** Le chutier Scan de
la maquette liste directement des **lots** (`SCAN_LOTS`, l. 925). Il n'y a
aucun endroit où vit un fichier déposé **pas encore décodé** — donc aucun
endroit où déposer un scan, aucun endroit où absorber le vrac du prestataire
(P4), aucun endroit où atterrit un second tirage avant qu'on sache que c'en est
un (P5), et aucun endroit où **reste visible** ce que la détection n'a pas su
rattacher. C'est le manque trouvé par Egan lui-même à la seconde relecture.

**Z4 — La composition d'un lot hybride (memlog 110, arbitrage H).** La maquette
ne connaît que « choisir **un** lot candidat » dans Exports (l. 980-987) —
exactement le modèle que P5 v2 a démoli (*« j'avais écrit deux passes, elle en
choisit une. C'est trop simple. »*). La conception actuelle est un **montage à
la frame** : plusieurs **candidats** par frame, invariant de complétude, choix
en bloc comme simple raccourci du choix frame par frame, comparaison **depuis
la galerie**, vérification **en mode lecteur**, et rien n'est jamais supprimé.
Aucune de ces cinq pièces n'a d'équivalent dans la maquette.

**Les autres zones périmées :**

* **Z5 — Atelier Scan, previz.** Pas de mode PDF avec surimpression (marqueurs,
  QR, zones), pas d'édition des quatre coins, pas de mode loupe, pas de
  complétion manuelle d'un QR illisible, pas de galerie rangée par timecode.
  Tout cela était **déjà décidé le 2026-08-16** (memlog 57-60), donc la maquette
  était en retrait dès sa naissance ; et memlog 120 (2026-08-17) a depuis rendu
  l'ajustement des quatre coins **accessible en permanence**.
* **Z6 — Atelier Exports.** Ni chutier partagé avec Scan (memlog 63), ni écran
  de previz, ni bus de transport, ni son du rush original, ni **balayage
  (wipe)** — qui est le climax de P1 —, ni file d'attente réordonnable, ni
  presets, ni nom de fichier prévisionnel, ni destination prévisionnelle
  (memlog 65-70, 103). L'atelier de la maquette est une fiche et un bouton.
* **Z7 — Planches de calibration.** Aucun bouton en haut à droite de l'atelier
  Pdf, aucune section **Calibration** du chutier, aucun bouton « calibration
  scanner », aucun profil de calibration, aucun choix de profil dans les
  réglages Scan (memlog 47, 51, 56, 59, 61).
* **Z8 — Média absent et relink.** Aucun rush en rouge, aucun relink
  (memlog 72, 100) — donc rien de ce qui fait P2.
* **Z9 — Le chutier comme espace de travail.** Pas de dossiers d'organisation
  (« séquence 3 »), pas de glisser-déposer, pas d'ajout multiple (memlog 98).
* **Z10 — Marqueurs.** Réduits à une pastille qui bascule (l. 1064), alors que
  memlog 33 les définit **ponctuels ou plages de durée, avec couleur, nom et
  description**, servant à préparer plusieurs extractions.
* **Z11 — Cartes de progression.** La maquette affiche `n/total` et un
  pourcentage, mais **jamais le temps passé et le temps restant** exigés par
  memlog 36 — le champ `eta` est déclaré (l. 799) et jamais affiché.
* **Z12 — Cadences.** Les raccourcis **/2, /3, /4, /5** de memlog 25 n'existent
  pas : la maquette n'offre que la fréquence personnalisée par invite
  (l. 697-700). C'est justement le geste de P1 étape 6.
* **Z13 — Fenêtre de confirmation.** Sans annonce de l'**espace disque requis**,
  ajout de la relecture (P1 étape 7).

---

## 5. Recommandation par élément perdu

| # | Élément | Recommandation | Motif |
|---|---|---|---|
| G01 | Ouvrir un projet hors registre | **À réintégrer** | P2 étape 1 en dépend : un projet transmis n'est jamais dans le registre local |
| G02 | Contenu d'une ligne de projet (chemin, rushes, date) | **À réintégrer** | Seul moyen de distinguer deux copies du même projet sur deux disques |
| G03 | Nom de projet ≠ dossier + emplacement par défaut | **À trancher par Egan** | Décide si un projet a une identité indépendante de son chemin |
| G04 | Fil d'Ariane du projet ouvert | **À réintégrer** | Sur un outil à deux machines, savoir où l'on écrit se lit en permanence |
| G05 | Bascule de langue + repli sur l'anglais | **À réintégrer** | Sans surface de bascule, la politique i18n décidée reste inapplicable |
| G06 | Baseline « pupitre de workflow » | **À réintégrer** | Seule phrase que lit un nouvel arrivant ; l'ouverture au public est un objectif déclaré |
| G07 | Pastille d'état sur le bouton du panneau | **À réintégrer** | Rend acceptable de fermer le panneau sans perdre de vue les tâches |
| G08 | Ouverture auto du panneau au lancement | **À réintégrer** | Sans retour immédiat, l'opératrice reclique le bouton d'action |
| G09 | Affordance « ce clic ouvre l'atelier Pdf » | **À réintégrer** | Un clic qui change d'atelier sans prévenir est une désorientation gratuite |
| G10 | Rappel du manque en haut de l'atelier | **À réintégrer** | Le blocage doit être trouvable depuis là où il se manifeste |
| G11 | Refus explicite au clic plutôt que bouton grisé | **À réintégrer** | Applique déjà la doctrine memlog 92/116 : un échec dit son motif |
| G12 | Liste des métadonnées source + critère d'essentialité | **À trancher par Egan** | Bloquant pour écrire une story 7.x ; la liste doit venir du contrat 3.5 (`source_*`) |
| G13 | Rang de sortie sur la vignette | **À réintégrer** | Le rang identifie la frame dans le lot, le timecode dans le rush : pas substituables |
| G14 | Case à cocher par vignette (sélection manuelle) | **À trancher par Egan** | Décide si la sélection reste calculée ou devient retouchable ; conséquence directe sur l'empreinte de sélection |
| G15 | Zoom = densité de grille | **À réintégrer** | Précise une décision qui existe déjà sans forme |
| G16 | Compte de frames par cadence à la confirmation | **À réintégrer** | Répond à la question réelle de Camille (combien d'images à peindre) |
| G17 | Toasts transitoires | **À réintégrer avec réserve** | Utile pour les succès ; un échec ne doit pas s'effacer seul (memlog 92/116) |
| G18 | « Plan affiché — PDF pas encore rendu » | **À réintégrer** | P1 fait de cet aperçu un point de jugement : il doit dire ce qu'il montre |
| G19 | Navigation dans les pages d'une planche | **À trancher par Egan** | Neuf pages par planche en P1 ; le grain de navigation n'est pas décidé |
| G20 | Légende ArUco / preset de patchs | **À réintégrer** | Dit ce qui est posé sans prétendre le dessiner à l'échelle |
| G21 | Vue en liste des pages du lot | **À réintégrer** | Seule surface qui donne l'état page par page d'un coup ; aucun des trois modes ne le fait |
| G22 | Résidu de reprojection par page | **À réintégrer** | Distingue une page correcte d'une page qui produira des cadrages faux en silence |
| G23 | Provenance du gabarit (QR / manifest) | **À réintégrer** | Distingue « lu » de « supposé » ; le contrat porte déjà l'avertissement |
| G24 | Compteurs de lot, dont les frames synthétiques | **À réintégrer** | P3 exige deux comptages distincts et aucune surface ne les porte |
| G25 | Sélecteur de version au scan | **À trancher par Egan** | Voir C4/E27 : conflit ouvert entre discriminant saisi et rattachement automatique |
| G26 | « Candidat unique — auto-sélectionné » | **À réintégrer** | Une décision silencieuse et une décision expliquée n'engagent pas la même confiance |
| G27 | Fiabilité du timecode par profil | **À réintégrer** | Le réglage le plus lourd d'Exports se prend sinon à l'aveugle, sur un produit fait pour préserver les timecodes |
| G28 | Origine de la résolution retenue | **À réintégrer** | Évite un contresens sur un lot reconstruit, où la résolution source est absente par construction |
| G29 | Consentement d'écrasement du master | **À réintégrer** | Aucun parcours ne rencontre un master déjà présent ; la forme doit suivre le contrat 6.4, pas la case de la maquette |
| G30 | Grammaire d'états et typographie des identifiants | **À réintégrer** | Le code couleur est la pièce la plus sollicitée de la conception et n'est défini nulle part |

**Aucun élément « à écarter sciemment ».** La seule chose que la maquette porte
et qu'il faut refuser est son *implémentation* (technologie, structure du
fichier), ce que le commit dit lui-même — pas ses idées d'interface.
