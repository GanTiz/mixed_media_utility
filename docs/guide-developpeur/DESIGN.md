---
name: mixed_media_utility
description: Instrument de post-production de bureau (macOS 12+ / Windows 10+) pour faire passer des rushes par le papier et les reconstruire. Coque neutre non teintee autour d'images dont on juge la couleur, quatre ateliers en onglets bas, densite d'outil professionnel.
status: final
updated: 2026-08-23
colors:
  # --- Neutres. Invariant absolu : R = G = B sur TOUS les neutres.
  # Une coque teintee fausse le jugement colorimetrique fait dans l'interface.
  surface-canvas: '#141414'
  surface-panel: '#1C1C1C'
  surface-raised: '#242424'
  surface-hover: '#2E2E2E'
  surface-sunken: '#0E0E0E'
  border: '#383838'
  border-strong: '#4A4A4A'
  text-primary: '#E8E8E8'
  text-secondary: '#9A9A9A'
  text-disabled: '#6A6A6A'
  # --- Mat : le neutre pose autour de toute zone d'image jugee.
  image-mat: '#2B2B2B'
  # --- Papier : substrat d'une page (apercu PDF, scan). Blanc vrai, jamais casse.
  paper: '#FFFFFF'
  paper-ink: '#111111'
  # --- Accent. Une seule chromie de coque : selection, focus, activite en cours.
  # Jamais un verdict, jamais a moins de {spacing.mat-min} d'une image.
  accent: '#4C7EF3'
  accent-pressed: '#3A63C4'
  accent-on: '#FFFFFF'
  # --- Semantiques metier. Separees de l'accent, non interchangeables entre elles.
  state-complete: '#3FBF6F'
  state-absent: '#E5484D'
  state-substitute: '#F5A623'
  # --- Variantes de TEXTE des chromies ci-dessus. Meme teinte, clarte relevee.
  # Les valeurs pleines ci-dessus sont des valeurs de TRAIT et d'APLAT (bordure,
  # barre, surimpression, remplissage) : elles tiennent le plancher de 3:1 des
  # elements non textuels. Elles ne tiennent PAS 4,5:1 en texte de 11 ou 13 px
  # (mesure : rouge 3,3:1 en badge sur surface-raised, accent 4,13:1 en label de
  # carte). Tout texte sous 18 px qui porte une de ces chromies prend la variante
  # -text ci-dessous. Voir Colors, "Plancher de contraste".
  state-complete-text: '#4EC57A'
  state-absent-text: '#EE878A'
  state-substitute-text: '#F5A623'   # inchangee : deja au-dessus du plancher
  accent-text: '#8FAEF7'
  # --- Surimpressions de scan. Traits, jamais aplats.
  overlay-halo: '#000000'
  overlay-handle: '#FFFFFF'
typography:
  display:
    fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif'
    fontSize: 28px
    fontWeight: '600'
    lineHeight: '1.2'
  title:
    fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif'
    fontSize: 15px
    fontWeight: '600'
    lineHeight: '1.3'
  body:
    fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif'
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.45'
  label:
    fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif'
    fontSize: 11px
    fontWeight: '600'
    lineHeight: '1.35'
    letterSpacing: 0.08em
  data:
    fontFamily: '"SF Mono", Menlo, Consolas, "Cascadia Mono", monospace'
    fontSize: 12px
    fontWeight: '400'
    lineHeight: '1.4'
    note: 'Chiffres tabulaires obligatoires (font-variant-numeric: tabular-nums).'
  data-lg:
    fontFamily: '"SF Mono", Menlo, Consolas, "Cascadia Mono", monospace'
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.3'
    letterSpacing: 0.04em
  data-sm:
    fontFamily: '"SF Mono", Menlo, Consolas, "Cascadia Mono", monospace'
    fontSize: 11px
    fontWeight: '400'
    lineHeight: '1.35'
rounded:
  none: 0
  sm: 4px
  DEFAULT: 6px
  md: 6px
  lg: 8px
  xl: 10px
  full: 9999px
spacing:
  '1': 2px
  '2': 4px
  '3': 6px
  '4': 8px
  '5': 12px
  '6': 16px
  '7': 24px
  '8': 32px
  gutter: 12px
  panel-pad: 10px
  mat-min: 16px
  row-height: 28px
  hit-min: 24px
  header-height: 44px
  transport-height: 44px
  tabbar-height: 54px
  # --- Largeurs du chrome. Depuis EPIC7-ARB-40 elles ne sont plus toutes
  # constantes : le chutier a deux panneaux et une poignee de largeur entre eux.
  # Ce qui suit donne les DEFAUTS et les PLANCHERS ; le plafond de chaque poignee
  # est derive, jamais constant (voir Layout & Spacing).
  tree-panel-width: 196px       # panneau d'arborescence, defaut
  tree-panel-min-width: 160px   # plancher de la poignee
  tree-panel-rail: 42px         # meme panneau retracte : rail de pictogrammes
  splitter-width: 5px           # poignee de largeur, zone saisissable
  bin-width: 330px              # chutier, defaut
  bin-min-width: 250px          # plancher de la poignee (ancienne valeur constante)
  side-panel-width: 300px       # panneau lateral de reglages (droite)
  queue-width: 320px            # panneau de progression / file des taches
  stage-min-width: 640px        # scene : plancher, jamais franchi par une poignee
  window-min-width: 960px
  window-min-height: 680px
  queue-overlay-threshold: 1500px   # sous ce seuil la file passe en superposition
  tree-collapse-threshold: 1180px   # sous ce seuil le panneau d'arborescence se replie
components:
  workshop-tab:
    height: '{spacing.tabbar-height}'
    background: '{colors.surface-panel}'
    foreground: '{colors.text-secondary}'
    foreground-active: '{colors.text-primary}'
    indicator-active: '{colors.accent}'
    indicator-width: 2px
    radius: '{rounded.none}'
  bin-row:
    height: '{spacing.row-height}'
    foreground: '{colors.text-primary}'
    foreground-lot: '{colors.text-secondary}'
    background-selected: '{colors.surface-hover}'
    marker-selected: '{colors.accent}'
    # Texte de 13 px : variante -text, jamais la chromie pleine (plancher 4,5:1).
    foreground-delinked: '{colors.state-absent-text}'
    radius: '{rounded.md}'
    indent: '{spacing.5}'
  # --- Panneau d'arborescence : le panneau GAUCHE du chutier a deux panneaux.
  # Il sert a se placer ; le chutier montre le contenu de ce qu'il designe.
  bin-tree-panel:
    width: '{spacing.tree-panel-width}'
    min-width: '{spacing.tree-panel-min-width}'
    width-collapsed: '{spacing.tree-panel-rail}'
    background: '{colors.surface-sunken}'
    border-right: '{colors.border}'
    row-height: 26px
    foreground: '{colors.text-secondary}'
    radius: '{rounded.none}'
  # --- Poignee de largeur entre les deux panneaux (EPIC7-ARB-40).
  bin-splitter:
    width: '{spacing.splitter-width}'
    cursor: 'col-resize'
    grip: '{colors.border-strong}'
    grip-size: '1px x 26px, centre vertical'
    background: 'none'
  # --- Barre de filtres du chutier : filtre par type, jamais seconde hierarchie.
  bin-filters:
    padding: '{spacing.3} {spacing.panel-pad}'
    border-bottom: '{colors.border}'
    chip-radius: '{rounded.full}'
    chip-border: '{colors.border}'
    chip-foreground: '{colors.text-disabled}'
    chip-foreground-active: '{colors.text-primary}'
    typography: '{typography.data-sm}'
  bin-buffer:
    position: 'haut du chutier, au-dessus de l''arbre'
    title: 'En attente de lecture'
    background: '{colors.surface-sunken}'
    border: '{colors.border}'
    border-style: 'dashed'
    foreground: '{colors.text-secondary}'
    radius: '{rounded.md}'
  viewer-stage:
    background: '{colors.image-mat}'
    padding: '{spacing.mat-min}'
    border: '{colors.border}'
    radius: '{rounded.lg}'
    content-radius: '{rounded.none}'
  frame-thumb:
    radius: '{rounded.none}'
    border-default: '{colors.border}'
    border-focus: '{colors.accent}'
    border-absent: '{colors.state-absent}'
    border-substitute: '{colors.state-substitute}'
    opacity-deselected: '0.32'
    caption: '{typography.data-sm}'
    caption-position: 'sous la vignette, hors de l''image'
  overlay-zone:
    stroke: '{colors.accent}'
    stroke-read-ok: '{colors.state-complete}'
    stroke-unreadable: '{colors.state-substitute}'
    stroke-width: 1.5px
    halo: '{colors.overlay-halo}'
    halo-width: 3px
    fill: 'none'
  overlay-handle:
    size: 11px
    fill: '{colors.overlay-handle}'
    halo: '{colors.overlay-halo}'
    radius: '{rounded.none}'
  job-card:
    background: '{colors.surface-raised}'
    width: '{spacing.queue-width}'
    # Nom de fonction en `label` 11 px : variante -text (plancher 4,5:1).
    function-label: '{colors.accent-text}'
    border: '{colors.border}'
    border-done: '{colors.state-complete}'
    bar-running: '{colors.accent}'
    bar-done: '{colors.state-complete}'
    bar-height: 6px
    radius: '{rounded.lg}'
  params-field:
    background: '{colors.surface-raised}'
    border: '{colors.border}'
    border-focus: '{colors.accent}'
    border-required-missing: '{colors.state-absent}'
    radius: '{rounded.sm}'
  page-preview:
    background: '{colors.paper}'
    foreground: '{colors.paper-ink}'
    radius: '{rounded.none}'
    surround: '{colors.image-mat}'
  button-primary:
    background: '{colors.accent}'
    foreground: '{colors.accent-on}'
    radius: '{rounded.md}'
    shadow: 'none'
  # --- FAMILLE 1 : completude d'un lot. Ce badge repond a "que manque-t-il ?".
  badge-state:
    radius: '{rounded.full}'
    typography: '{typography.label}'
    # Fond : 16 % de la chromie pleine, compose sur la surface porteuse.
    fillComplete: '{colors.state-complete} @ 16%'
    fillAbsent: '{colors.state-absent} @ 16%'
    fillSubstitute: '{colors.state-substitute} @ 16%'
    # Texte : variante -text, PAS la chromie pleine (mesure en Colors).
    complete: '{colors.state-complete-text}'
    absent: '{colors.state-absent-text}'
    substitute: '{colors.state-substitute-text}'
    # Redondance non chromatique, exigee : chaque etat porte AUSSI une forme.
    # Rouge et ambre sont la paire la plus confusable, et l'outil s'ouvrira
    # a des videastes dont on ne connait pas la vision des couleurs.
    shapeComplete: 'disque plein'
    shapeAbsent: 'anneau creux'
    shapeSubstitute: 'disque hachure'
  # --- FAMILLE 2 : rattachement d'un objet. Ce signe repond a "que dois-je
  # faire ?" — retrouver le fichier, l'identifier, le completer (EPIC7-ARB-5,
  # cas d'usage en EPIC7-ARB-12). Trois glyphes, jamais les formes ci-dessus.
  state-glyph:
    typography: '{typography.data}'
    size: 14px
    delinked: 'maillon brise (U+2298)'
    delinked-color: '{colors.state-absent-text}'
    unattached: 'point d''interrogation (U+003F)'
    unattached-color: '{colors.text-secondary}'
    incomplete: 'panneau d''avertissement (U+26A0)'
    incomplete-color: '{colors.state-substitute-text}'
    size-incomplete: 15px
    position: 'fin de ligne de chutier, apres le compteur'
---

## Brand & Style

`mixed_media_utility` n'est pas une page, c'est un **instrument de post-production**. Il tourne en natif sur **macOS 12+ et Windows 10+**, en Qt piloté depuis Python (PySide6, LGPL) — arbitrage 14, tranché *après* la première rédaction de cette spine. Rien ici ne dépend pour autant du framework : les valeurs sont des valeurs, pas des surcharges d'une bibliothèque, et elles resteraient vraies si le toolkit changeait.

Le modèle revendiqué est **DaVinci Resolve** : quatre ateliers en onglets bas — Extraction, Pdf, Scan, Exports — un écran de gestion de projet au lancement, un panneau de progression ancré à droite. On travaille *dans* un atelier, on n'y navigue pas.

**Le fait décisif du produit : l'utilisatrice juge des couleurs dans cette interface.** Elle compare un scan calibré à son original, bascule d'un profil de calibration à l'autre, valide un rendu avant qu'un seul TIFF ne s'écrive. Une coque teintée fausse ce jugement — le contexte chromatique déplace la perception de la teinte et de la clarté de ce qu'il entoure. D'où l'invariant du système : **tous les neutres sont strictement neutres, R = G = B**, et une bande de neutre d'au moins `{spacing.mat-min}` sépare toute chromie de coque d'une zone d'image. C'est la norme des outils d'étalonnage, ce n'est pas un parti pris esthétique.

> **Écart signalé.** La maquette `gui-prototype/index.html` est **légèrement teintée** — `#17171a` (bleu-violet), fond de previz `#0d0d0f`, page PDF `#f4f4f2`, dégradé `#232329` au lancement. La maquette porte les bonnes structures ; ses valeurs ne sont pas reprises. Les neutres de cette spine les remplacent un pour un.

Le reste découle de deux tensions. **Densité** : beaucoup d'états simultanés — un arbre de chutier à quatre niveaux, une file de cartes de progression, une page scannée couverte de surimpressions. L'interface se **balaie du regard**, elle ne se lit pas ; c'est un tableau de bord d'atelier, pas un document. **Effacement** : partout où l'image domine — previz vidéo, galerie, page scannée, mode lecteur, balayage — l'habillage recule jusqu'à n'être plus qu'un cadre. Aucun dégradé décoratif, aucune lueur, aucune texture : ce qui n'informe pas n'existe pas.

## Colors

Trois familles, jamais confondues : les **neutres** (la coque), l'**accent** (les marques de l'outil), les **sémantiques** (les verdicts métier).

**Les neutres.** Cinq niveaux, du plus enfoncé au plus levé — `surface-sunken` `#0E0E0E` (zone tampon, fosses), `surface-canvas` `#141414` (fond d'atelier), `surface-panel` `#1C1C1C` (chutier, panneau latéral, barres), `surface-raised` `#242424` (cartes, champs, boutons), `surface-hover` `#2E2E2E`. Les bordures `#383838` / `#4A4A4A` et les trois valeurs de texte `#E8E8E8` / `#9A9A9A` / `#6A6A6A` sont sur le même axe. Aucune de ces valeurs ne porte de teinte, et ce n'est pas négociable : elles occupent la totalité du champ visuel périphérique pendant qu'on juge une image.

**`image-mat` `#2B2B2B`** est le seul neutre qui a un rôle plutôt qu'un niveau : c'est le **mat**, le fond posé directement autour d'une image — derrière la previz, derrière la grille de vignettes, autour d'une page scannée, derrière la page de l'aperçu PDF. Il est plus clair que le canvas pour que le bord d'une image sombre reste visible, et assez sombre pour ne pas éclaircir par contraste ce qu'on regarde.

**`paper` `#FFFFFF`.** L'aperçu PDF montre ce qui sera **imprimé** : le substrat de la page est un blanc vrai. Un blanc « de confort » légèrement cassé mentirait sur le tirage et sur la calibration, exactement comme une coque teintée mentirait sur un scan.

**`accent` `#4C7EF3`.** L'unique chromie de la coque. Elle dit trois choses et rien d'autre : *ceci est sélectionné* (ligne de chutier, onglet actif, case cochée), *ceci a le focus*, *ceci tourne en ce moment* (barre de progression en cours, pastille d'activité du panneau latéral). Une activité **n'est pas un verdict** : c'est pourquoi elle porte l'accent et non le vert. L'accent ne pénètre jamais le mat.

**Les sémantiques.** Elles sont imposées par le métier et ne se renégocient pas.

- **`state-absent` `#E5484D` — le rouge dit « il n'y a rien ici ».** Rush absent ou délinké dans les chutiers ; frame manquante dans la galerie ; métadonnée essentielle non renseignée dans le panneau de réglages, où elle **bloque** l'extraction. Un seul sens : une absence, et souvent une absence qui empêche d'avancer.
- **`state-complete` `#3FBF6F` — le vert dit « c'est fini, c'est complet ».** Carte de tâche terminée, lot complet dans le chutier, QR décodé et marqueurs lus dans les surimpressions. Le vert est un aboutissement ; il ne signale jamais une simple disponibilité.
- **`state-substitute` `#F5A623` — l'ambre dit « il y a quelque chose ici, mais ce n'est pas ton image ».** C'est la **mire de remplacement** : la page est là, sa géométrie a échoué, le produit a écrit une frame de substitution. C'est aussi le QR présent mais non décodé. Un lot qui contient des mires **n'est pas complet** même si aucune page ne manque.

Le rouge et l'ambre nomment **deux natures de manque** et l'interface ne doit jamais les fondre en un seul indicateur — c'est un acquis de conception explicite, pas une nuance graphique. Ils se comptent séparément : *pages manquantes* d'un côté, *frames synthétiques* de l'autre.

**Les surimpressions de scan** n'ajoutent aucune couleur : elles réutilisent l'accent (les rectangles proposés par l'outil), le vert (ce qui a été lu avec succès), l'ambre (ce qui n'a pas pu l'être). Elles sont dessinées **en trait, jamais en aplat**, avec un halo noir `overlay-halo` sous le trait — c'est ce qui les rend lisibles aussi bien sur une marge de papier blanc que sur une zone peinte à la gouache. Les **poignées** des quatre coins sont blanches à halo noir, jamais colorées : une poignée colorée sur une planche peinte se confond avec la peinture.

### Plancher de contraste

**Tout texte affiché sous 18 px tient au moins 4,5:1 contre la surface sur laquelle il est réellement posé** (WCAG 2.1 AA, seuil du petit texte). L'échelle typographique de cet outil n'a **aucune** taille au-dessus de 18 px hors `display` : le seuil de 4,5:1 est donc le plancher **de tout le texte du produit**, sans exception à négocier. Les éléments **non textuels** — bordure de vignette, barre de progression, trait de surimpression, filet de sélection — tiennent 3:1, seuil des composants graphiques.

Ce plancher n'existait pas, et son absence avait un coût mesuré. Les trois chromies sémantiques et l'accent étaient employés **à la fois** comme trait et comme texte, et deux de ces emplois échouaient :

| emploi | avant | après |
|---|---|---|
| badge `absent` — texte plein sur fond composé à 16 %, sur `surface-raised` | `#E5484D` sur `#432A2B` = **3,34:1** | `#EE878A` sur `#432A2B` = **5,28:1** |
| le même sur `surface-panel` / `surface-hover` | **3,68:1** / **2,98:1** | **5,81:1** / **4,70:1** |
| nom de fonction en `label` accent sur carte `surface-raised` | `#4C7EF3` sur `#242424` = **4,13:1** | `#8FAEF7` sur `#242424` = **7,07:1** |
| ligne de chutier d'un rush **délié**, `body` 13 px sur `surface-panel` | `#E5484D` sur `#1C1C1C` = **4,35:1** | `#EE878A` sur `#1C1C1C` = **6,87:1** |
| badge `complete` sur ligne survolée `surface-hover` | `#3FBF6F` sur `#314538` = **4,36:1** | `#4EC57A` sur `#314538` = **4,70:1** |
| badge `substitute`, pire cas (`surface-hover`) | `#F5A623` sur `#4E412C` = **4,90:1** | inchangé — **4,90:1**, déjà au-dessus |

**Le correctif porte sur les jetons, pas sur la recette du badge**, et c'est le choix qui casse le moins : la recette « fond à 16 %, texte à la couleur d'état, forme redondante » est un acquis de conception cité partout ; baisser l'opacité du fond aurait éclairci le badge de moins d'un point de ratio et abîmé la lisibilité de la forme. Quatre jetons de **texte** sont donc ajoutés — `state-complete-text`, `state-absent-text`, `state-substitute-text`, `accent-text` — de **même teinte** que leur chromie pleine, à clarté relevée. La chromie pleine reste la valeur de trait et d'aplat ; elle ne porte plus jamais de glyphe.

Trois conséquences à tenir :

- **le pire fond est `surface-hover`**, pas `surface-raised` : une ligne de chutier survolée porte son badge, et c'est ce cas-là qui a servi de calcul. Les valeurs ci-dessus sont les minima sur les cinq neutres, pas des moyennes ;
- `state-substitute-text` **vaut exactement** `state-substitute` : l'ambre passait déjà. Le jeton existe pour que la règle d'emploi soit uniforme — un développeur n'a pas à savoir laquelle des trois chromies avait un problème ;
- ce plancher **ne remplace pas** la redondance non chromatique. Forme et couleur traitent deux publics différents : le daltonisme d'un côté, la basse vision de l'autre. Les deux sont dus.


> **[À TRANCHER]** La clarté exacte du mat. `#2B2B2B` est un neutre sombre, cohérent avec la convention des suites d'étalonnage ; la convention *physique* (ISO 3664) est un gris moyen à 18 % (≈ `#767676`). Aucune décision du memlog ne tranche, et le choix ne se tranche pas sur le papier : il se teste à l'écran, sur un scan réel, avec Camille. Corollaire non tranché : le mat doit-il être **réglable** par l'utilisatrice, comme dans les outils d'étalonnage ?

> **Tranché — le thème clair est hors v1**, et pour une raison de fond : élever la luminance du pourtour déplace le contraste et la clarté perçus de l'image jugée, ce qui est exactement ce que le produit essaie d'éviter. Les surfaces claires existent déjà là où elles sont *vraies* (papier, scan), à l'intérieur de la coque sombre — ce n'est pas un thème, c'est un contenu. La question se rouvrira à l'**ouverture du dépôt (Epic 9)** : des vidéastes ne travaillent pas forcément dans une pièce sombre.
>
> **Conséquence sur les Préférences, et elle est visuelle :** il n'y a **pas de ligne « Thème »** dans les Préférences de la v1. Un sélecteur qui n'offre que « Sombre » est une ligne figée, et `EPIC7-ARB-29` les interdit — les Préférences « ne contiennent que des réglages effectifs ». La maquette `key-preferences.html` en porte encore une : écart à corriger côté maquette, la spine gagne.

## Typography

Deux voix, et la seconde compte autant que la première.

**L'interface** est en police système — SF Pro sur macOS, Segoe UI sur Windows. Deux raisons, aucune n'étant une préférence. L'interface est **multilingue et extensible** (anglais par défaut, français ensuite), donc la couverture de jeu de caractères du système est un acquis qu'on ne rachète pas. Et la licence LGPL impose déjà une distribution en dossier : n'embarquer aucune fonte, c'est autant de moins à redistribuer. Ni l'une ni l'autre ne dépendait du choix de toolkit, et le choix de Qt ne les a donc pas déplacées.

**Les données** sont en **monospace à chiffres tabulaires** : `data` 12 px, `data-sm` 11 px, `data-lg` 16 px. C'est obligatoire, pas décoratif — timecodes, cadences (`12,5` / `25`), compteurs de frames (`38/50`), identifiants de lot, tailles estimées, condensats. Ces valeurs se **comparent en colonne** : une frame qui manque se voit à un timecode qui ne s'aligne pas. `font-variant-numeric: tabular-nums` partout où un chiffre peut changer sans que sa boîte change.

L'échelle est courte, parce qu'un outil dense n'a pas de hiérarchie éditoriale : `display` 28 px (écran de gestion de projet, uniquement), `title` 15 px (titre d'atelier, en-tête de modale), `body` 13 px (tout le reste), `label` 11 px capitales espacées (en-têtes de section : chutier, panneau latéral, colonnes de réglages).

Règles fermes :

- **Le timecode d'une image s'affiche au-dessus d'elle, jamais dessus.** Une valeur posée sur l'image en abîme la lecture et lui ajoute une couleur.
- **i18n :** aucun composant ne suppose la longueur d'une langue. Toute boîte de libellé se dimensionne sur son contenu avec au moins **40 % de marge au-delà de l'anglais** ; aucun libellé interactif n'est tronqué ; aucune mise en page ne dépend d'un libellé tenant sur une ligne. Les capitales espacées sont réservées aux en-têtes courts, qui ont le droit de passer sur deux lignes.
- **Les codes du cœur ne se traduisent pas.** `LOT_INCOMPLETE`, `PAGE_QR_UNREADABLE`, `previz-1`, `sha256-v1:` s'affichent en `data`, verbatim, à côté de leur phrase traduite — jamais à sa place.

> **Tranché (2026-08-19).** Qt est retenu, et sa rampe typographique système **ne fait pas foi** à la place des tailles ci-dessus : l'échelle courte est un choix de densité propre à cet outil, pas un défaut de plateforme dont on hériterait. Les **rôles** et l'obligation de chiffres tabulaires restent dus quel que soit le toolkit.

## Layout & Spacing

Échelle de base **4 px** : 2 · 4 · 6 · 8 · 12 · 16 · 24 · 32. En dessous de 8 px on est dans le détail d'un composant ; au-dessus de 16 px on sépare des blocs. Il n'y a pas de valeur au-delà de 32 px : rien dans cet outil ne respire, tout se voit d'un coup.

**Le chrome n'est plus à largeurs constantes** (`EPIC7-ARB-40`). Le chutier a **deux panneaux** : à gauche une **arborescence rétractable**, qui sert à se placer ; à droite le **chutier**, qui montre le contenu de l'objet désigné. Une **poignée de largeur** les sépare. Ce qui reste vrai de l'ancienne clause — *passer d'Extraction à Pdf ne déplace pas l'image d'un pixel* — est conservé sous une forme exacte : ce ne sont plus les largeurs qui sont constantes, c'est le **changement d'atelier** qui ne les touche pas.

```
┌──────────────────────────────────────────────────────────────────────┐
│ en-tête (44)                                                         │
├──────┬─┬──────────┬──────────────────────────┬──────────────────────┤
│ arbo │║│ chutier  │ SCÈNE                    │ panneau de           │
│ 196  │║│ 330      │  infos (haut)            │ progression          │
│ ↔    │║│ ↔        │  previz ← seule zone     │ 320                  │
│      │║│  ┌───────┤    vraiment souple       │  (ancré ou superposé)│
│ rail │║│  │tampon │  transport (44)          │                      │
│ 42   │║│  └───────┤  réglages (bas)          │ panneau latéral 300  │
├──────┴─┴──────────┴──────────────────────────┴──────────────────────┤
│ onglets d'ateliers (54)                                              │
└──────────────────────────────────────────────────────────────────────┘
   ║ = poignée de largeur (5)      ↔ = réglable      rail = panneau replié
```

**Ce qui est fixe, ce qui se règle.**

| élément | jeton | régime |
|---|---|---|
| en-tête | `{spacing.header-height}` 44 | **fixe** |
| onglets d'ateliers | `{spacing.tabbar-height}` 54 | **fixe** |
| bus de transport | `{spacing.transport-height}` 44 | **fixe** |
| panneau d'arborescence | `{spacing.tree-panel-width}` 196 | **réglable**, plancher `{spacing.tree-panel-min-width}` 160 ; replié il vaut `{spacing.tree-panel-rail}` 42 |
| poignée | `{spacing.splitter-width}` 5 | **fixe** |
| chutier | `{spacing.bin-width}` 330 | **réglable**, plancher `{spacing.bin-min-width}` 250 |
| panneau de progression | `{spacing.queue-width}` 320 | **fixe** en largeur ; ancré ou superposé (`EPIC7-ARB-26`) |
| panneau latéral de réglages | `{spacing.side-panel-width}` 300 | **fixe** en largeur ; rétractable (`EPIC7-ARB-25`) |
| scène | — | prend tout le reste, plancher `{spacing.stage-min-width}` 640 |

- **Le plafond de chaque poignée est dérivé, jamais constant.** Aucune poignée ne peut faire descendre la scène sous `{spacing.stage-min-width}` : la largeur maximale d'un panneau vaut `largeur de fenêtre − chrome restant − 640`. C'est ce qui rend inutile un plafond écrit en dur, et ce qui garantit qu'un geste de poignée ne produit jamais un état où l'image n'est plus jugeable. Le plancher, lui, est bien une constante : 160 px pour l'arborescence (elle sert à *se placer*, un nom peut y être tronqué), 250 px pour le chutier (l'ancienne valeur constante de `bin-width`, en dessous de laquelle un nom à quatre niveaux d'indentation ne tient plus).
- **Deux seuils de largeur de fenêtre, et ils sont ordonnés.** En dessous de `{spacing.queue-overlay-threshold}` (1500) la file des tâches passe en **superposition** par défaut (`EPIC7-ARB-26`) ; en dessous de `{spacing.tree-collapse-threshold}` (1180) le panneau d'arborescence se **replie seul sur son rail** de 42 px — le chutier passe avant lui, et le rail reste touchable pour rouvrir l'arborescence *par-dessus* le chutier, le temps de se placer. Dans les deux cas le passage se fait **sans message** (`EPIC7-ARB-8`), et un mode choisi explicitement survit au franchissement du seuil : le seuil fixe le défaut, il ne reprend pas la main sur un choix.
- **Chutier en plein écran.** Le chutier occupe alors toute la bande entre l'en-tête et la barre d'onglets : la scène est masquée, la file passe en superposition. **L'arborescence, elle, garde l'état qu'elle avait avant le clic** — repliée comme ouverte (`EPIC7-ARB-86`, 2026-08-27, second essai de terrain d'Egan : « il faut qu'il reste dans l'état où il était avant le clic »). Le mécanisme qui la repliait puis la restituait était correct ; c'est son principe qui a été refusé. Corollaire de géométrie : la bande libérée par la scène revient **au chutier**, jamais au panneau — sans quoi le panneau prend la moitié de la fenêtre au moment précis où l'on demande le chutier en grand. C'est une géométrie, pas une fenêtre : rien ne se détache, rien ne flotte, et la barre d'onglets reste là.
- **La zone tampon est en haut du chutier**, au-dessus de l'arbre, et se nomme **« En attente de lecture »** (correction A2). Elle est en `{colors.surface-sunken}` à bordure pointillée.
- **Le chutier est commun** à Extraction et Pdf (rush > lots > planches) et commun à Scan et Exports (scan > lots reconstruits, plus une section Calibration et la zone tampon). C'est la pièce la plus sollicitée du produit — source, état d'avancement, arborescence, code couleur de complétude — donc celle qui a droit à la plus grande stabilité visuelle. **Sa largeur est mémorisée et vaut pour les quatre ateliers** : c'est ce qui remplace la constante et préserve la comparaison d'un atelier à l'autre.
- **Densité :** ligne de chutier `{spacing.row-height}` (28 px), ligne d'arborescence 26 px, cible de clic minimale `{spacing.hit-min}` (24 px), gouttière `{spacing.gutter}` (12 px), remplissage de panneau `{spacing.panel-pad}` (10 px). C'est serré, et ça doit l'être : un arbre profond et une file de tâches doivent tenir ensemble à l'écran.
- **`{spacing.mat-min}` (16 px) est un minimum, pas un padding.** Aucune couleur chromatique — accent, sémantique, badge — n'entre dans cette bande autour d'une image. Une surimpression posée *sur* l'image est la seule exception, et elle est en trait à halo.
- **La grille de vignettes** est à zoom continu (la taille des miniatures est un réglage de la previz, pas un point d'arrêt) ; gouttière `{spacing.4}`, alignement en grille régulière pour que l'œil compte les lignes.

### Taille minimale de fenêtre

**`{spacing.window-min-width}` × `{spacing.window-min-height}` — 960 × 680 px.** La valeur est une addition, pas un usage :

```
largeur    42  rail de l'arborescence     (repliée : sous 1180 px c'est le régime)
          + 5  poignée
        + 250  chutier à son plancher
        + 640  scène à son plancher
        -----
          937  →  960 px  (arrondi au multiple de 8 supérieur, 23 px de marge)

hauteur    44  en-tête
          +54  onglets d'ateliers
         +374  previz : image 608 × 342 (16:9) + 2 × 16 de mat
          +28  bandeau d'infos (une ligne de {spacing.row-height})
          +44  bus de transport
         +120  barre de réglages : un `label` de colonne + deux rangs de champs
         -----
          664  →  680 px
```

Trois choses que cette addition dit, et qui ne l'étaient nulle part :

1. **le budget de chrome dépend du régime.** Tout ancré, il vaut 196 + 5 + 330 + 320 = **851 px**, pas une colonne à droite comme l'écrivait l'ancien schéma. C'est ce total qui rendait le seuil de superposition de 1100 px proposé par `key-preferences.html` **faux** : à 1101 px avec tout ancré, la scène tombe à 250 px. Le seuil vaut donc 851 + 640 = 1491 → **1500 px**, et la maquette est à corriger, pas la règle ;
2. le seuil de repli de l'arborescence obéit à la même addition, en régime file superposée : 196 + 5 + 330 + 640 = 1171 → **1180 px** ;
3. **les trois valeurs sont monotones** — 960 < 1180 < 1500 — et chacune laisse la scène à 640 px au moins : 960 − 42 − 5 − 250 = 663 ; 1180 − 196 − 5 − 330 = 649 ; 1500 − 196 − 5 − 330 − 320 = 649. Aucun régime intermédiaire ne produit une scène plus étroite que son plancher.

**Les deux termes posés, et leur motif.** `stage-min-width` 640 et la hauteur de la barre de réglages (120) ne viennent d'aucune décision : ce sont des valeurs **posées ici**, parce qu'une taille minimale sans elles n'est pas calculable. 640 est la largeur qui laisse une previz 16:9 de 608 × 342 — au-dessus du quart de 1080p — une fois retiré le mat obligatoire des deux côtés ; c'est aussi la largeur en dessous de laquelle la galerie ne tient plus quatre vignettes de 128 px avec leurs gouttières. Elles se révisent à la première mesure sur écran réel, et ce sont les seules deux valeurs de cette section à ne pas descendre d'un jeton ou d'un arbitrage.

## Elevation & Depth

La profondeur se fait par **niveau de gris et par filet de 1 px**, pas par ombre. Deux régimes seulement :

- **Surfaces ancrées** — chutier, panneau, barres, cartes, réglages : aucune ombre. Elles se distinguent par leur niveau de neutre et par une bordure `{colors.border}`. C'est ce qui permet d'empiler beaucoup d'états sans que l'écran se salisse.
- **Surfaces flottantes** — modales, loupe, menus contextuels, panneau détaché : ombre noire diffuse, `0 16px 48px rgba(0,0,0,.55)`, sans teinte.

Règles :

- **Aucune ombre ne déborde sur une image.** Une ombre projetée sur un bord de frame en modifie la luminance locale : c'est un mensonge colorimétrique, au même titre qu'un fond teinté.
- **Aucune lueur.** La maquette pose une lueur accent sous le bouton Extract (`box-shadow` bleu) — elle ne fait pas partie du système. L'importance d'un bouton se dit par sa taille, sa position et son remplissage.
- **Aucune ombre colorée, aucun dégradé de surface.** Y compris sur l'onglet actif, que la maquette dégrade en bleu : l'onglet actif se marque par un filet de 2 px `{colors.accent}` et un texte plein, rien d'autre.
- La **loupe** de réglage au pixel est une surface flottante : elle a une ombre, mais son intérieur est du contenu d'image — donc bordure neutre, coins droits, aucun habillage.

## Shapes

Trois rayons et une exception qui compte plus que les trois.

- `{rounded.sm}` (4 px) : champs, cases, petits contrôles.
- `{rounded.md}` (6 px) : boutons, lignes de chutier, puces de cadence.
- `{rounded.lg}` (8 px) : cartes, panneaux, cadre de previz, modales (`{rounded.xl}` 10 px pour la modale et l'écran de lancement).
- `{rounded.full}` : **uniquement** les badges d'état et les puces de cadence supprimables.

**L'exception : `{rounded.none}` sur tout contenu d'image.** Vignette, previz, page rastérisée, candidat comparé, mire, poignée. Un coin arrondi **rogne la frame** — et sur un outil dont le métier est de recadrer au pixel, il fait douter de ce qu'on regarde : est-ce mon cadrage, ou est-ce l'habillage ? Le cadre autour de l'image peut être arrondi ; l'image, jamais. La maquette arrondit ses vignettes à 6 px : écart à corriger.

## Components

> **Rendus — et ce que la confrontation aux jetons couvre réellement.** `mockups/` compte
> **18 maquettes**. **Quatre** ont été confrontées à ces jetons, une par une, et les appliquent
> tels quels : `bin-row` et `badge-state` dans [`key-chutier.html`](mockups/key-chutier.html),
> `overlay-*` et `params-field` dans
> [`key-scan-mode-pdf.html`](mockups/key-scan-mode-pdf.html), `page-preview` et `job-card` dans
> [`key-atelier-pdf.html`](mockups/key-atelier-pdf.html), `viewer-stage` dans
> [`key-mode-lecteur.html`](mockups/key-mode-lecteur.html). **Les quatorze autres ne l'ont
> jamais été** : leurs valeurs n'ont aucune autorité et ne se recopient pas — y compris
> `key-chutier-v2.html`, dont c'est la *structure* qui fait référence (`EPIC7-ARB-40`), pas les
> nombres, réécrits ici en jetons. **La spine gagne sur toute maquette**, et une maquette non
> confrontée n'est pas une source de valeurs : c'est le seul énoncé du corpus qui pouvait
> laisser croire l'inverse.

- **Barre d'onglets (bas).** Quatre ateliers dans l'ordre du flux, largeur égale, `{spacing.tabbar-height}`. Actif : filet 2 px `{colors.accent}` en haut + `{colors.text-primary}`. Inactif : `{colors.text-secondary}`. Pas de dégradé, pas de compteur. Elle ne bouge jamais.
- **Chutier (bin) — deux panneaux** (`EPIC7-ARB-40`). À gauche le **panneau d'arborescence**, `bin-tree-panel` : fond `{colors.surface-sunken}`, lignes de 26 px, texte `{colors.text-secondary}`, un pictogramme par nœud, aucune puce de sélection, aucun compteur — il sert à **se placer**, pas à lire. Il se rétracte sur un **rail de `{spacing.tree-panel-rail}`** qui ne garde que les pictogrammes et reste touchable. Entre les deux, la **poignée** `bin-splitter` : 5 px saisissables, curseur `col-resize`, un filet de 1 × 26 px en `{colors.border-strong}` centré verticalement pour toute affordance — pas de cartouche, pas de flèche. À droite le **chutier** proprement dit, qui montre le **contenu de l'objet désigné** à gauche : un en-tête `label` portant sa **portée** (« Contenu de *sequence 3* · 2 rushes ») et le bouton **plein écran** ; puis la **barre de filtres** `bin-filters` (chips `{rounded.full}` par type : Tout, Scans, Planches, Exports) — un **filtre**, jamais une seconde hiérarchie, sans quoi on ne saurait plus laquelle fait foi ; puis la **zone tampon**, puis l'arbre. Indentation `{spacing.5}`, ligne `{spacing.row-height}`, filets de filiation en `{colors.border}` s'arrêtant au dernier nœud d'un niveau.
- **Deux familles de signes, à ne jamais confondre.** Le corpus a fait circuler trois triplets différents sous la même référence `EPIC7-ARB-5` ; ils décrivent deux questions distinctes, et c'est la confusion qui était le défaut, pas les triplets.
  - **Complétude — « que manque-t-il dans ce lot ? »** C'est `{components.badge-state}` : `complete` / `absent` / `substitute`, en **disque plein / anneau creux / disque hachuré**. Un badge, posé sur un lot, qui compte. Ce triplet reste, **sous son propre nom** — il ne répond pas à la question d'`EPIC7-ARB-5` et ne porte plus sa référence.
  - **Rattachement — « que dois-je faire de cet objet ? »** C'est `{components.state-glyph}`, et c'est le triplet réellement décidé par `EPIC7-ARB-5` (cas d'usage en `EPIC7-ARB-12`) : **délié** = *maillon brisé* ⊘ en `{colors.state-absent-text}`, le fichier a disparu du disque, il faut le **retrouver** ; **non rattaché** = *point d'interrogation* ? en `{colors.text-secondary}`, l'objet existe mais on ignore à quoi il appartient, il faut l'**identifier** ; **incomplet** = *panneau d'avertissement* ⚠ en `{colors.state-substitute-text}`, le rattachement est connu mais il manque des pièces, il faut le **compléter**. Un glyphe en fin de ligne, `data` 14 px (15 px pour ⚠, dont l'œil est plus petit), avec une bulle au survol qui dit le geste — jamais un badge, jamais une pastille.
  - **Trois glyphes et non deux**, parce que les trois appellent trois gestes différents : fondre *délié* et *non rattaché* ferait dire à l'interface « quelque chose ne va pas » sans dire quoi faire.
- **Chutier — la ligne.** Arbre à quatre niveaux, indentation `{spacing.5}`, ligne `{spacing.row-height}`. Un rush **délié** est en `{colors.state-absent-text}` — la variante de texte, pas la chromie pleine (voir *Plancher de contraste*) — **doublé du glyphe de délié** de `{components.state-glyph}` : pas de badge textuel ni de mention d'origine, mais la couleur ne porte jamais seule. Le rush est peint en rouge dans **tous** les chutiers où il apparaît. Un lot porte son **code couleur de complétude** (`complete` / `substitute` / `absent`) et, s'il y a lieu, **un** signe de rattachement — jamais les deux familles dans le même signe (bullet suivant). Sélection multiple par cases à cocher sur l'atelier Pdf ; cocher un rush coche ses lots. Les **dossiers d'organisation** créés par l'utilisatrice ne se distinguent pas des autres nœuds sinon par leur icône : ils n'existent que dans le chutier.
- **Zone tampon du chutier.** Section propre, **en haut du chutier**, au-dessus de l'arbre, titrée **« En attente de lecture »** en `label` avec son compteur à droite (correction A2). Sur `{colors.surface-sunken}` à bordure **pointillée** : les fichiers déposés, pas encore décodés. Elle est en haut parce que c'est ce qui **appelle un geste** : une pile en bas de liste, sous un arbre qu'on déplie, ne se voit pas. C'est un état visuel à part entière, pas une liste d'attente technique — elle absorbe le vrac d'un prestataire, elle **garde visible** ce que la détection n'a pas su rattacher, et elle porte le bouton **Détecter** avec les cases de ce qui part en détection.
- **Scène de previz.** Cadre `{rounded.lg}` bordé, fond `{colors.image-mat}`, remplissage `{spacing.mat-min}`. Au-dessus : le sélecteur de mode (Vidéo / Galerie sur Extraction ; PDF / Galerie / **Lecteur** sur Scan), le zoom de vignettes, les bascules (frames supprimées, calibration couleur). En dessous : le bus de transport. Rien d'autre n'entre dans ce cadre.
- **Bus de transport.** `{spacing.transport-height}`, `{colors.surface-panel}`. Lecture/pause, image par image, boucle, volume, points in/out en champs `data` saisissables, marqueurs, flèches latérales de changement de cadence. Sur Exports : ni son, ni changement de cadence — mais le **balayage**, avec une poignée de wipe neutre (trait blanc à halo noir) et une bascule marche/arrêt en un clic, le wipe restant inspectable **image par image** en pause.
- **Vignette de frame.** Coins droits, légende `data-sm` **sous** l'image. Cinq états, jamais fondus : *retenue* (bordure `{colors.border}`) ; *écartée* (opacité 0.32, bordure neutre et hachure — **pas de rouge** : une frame écartée n'est pas une frame manquante ; l'écart est **calculé par la cadence**, jamais choisi, `EPIC7-ARB-16`, donc la vignette n'est pas actionnable) ; *absente* (bordure `{colors.state-absent}`, la case reste à sa place dans la grille) ; *mire de remplacement* (bordure `{colors.state-substitute}`) ; *plusieurs candidats* (marque d'angle en `{colors.accent}` portant leur nombre, cliquable pour comparer).
- **Surimpressions de scan (mode PDF).** Traits 1,5 px à halo noir 3 px, sans remplissage. Marqueurs ArUco lus et QR décodé en `{colors.state-complete}` ; QR non décodé en `{colors.state-substitute}` ; zones de frames proposées par l'outil en `{colors.accent}`. Chaque zone est **adressable** (page + slot) et **toujours éditable**, y compris quand la détection s'est déclarée satisfaite : l'outil ne sait jamais qu'il s'est trompé, c'est l'œil qui tranche.
- **Poignées de coin + loupe.** Quatre carrés blancs de 11 px à halo noir, coins droits. Les saisir ouvre la loupe automatiquement. Après un ajustement, **rien ne se relance** : l'affichage de complétude du lot se met à jour, c'est tout.
- **Formulaire de complétion de QR.** Champs `data` ; à mesure qu'un champ prend le focus, **la zone correspondante du scan est pointée** dans la previz (encadré `{colors.accent}` + zoom disponible). Aucun champ n'est prérempli : un champ vide appelle la vérification, un champ faux ne l'appelle pas.
- **Carte de tâche (panneau de progression).** `{colors.surface-raised}`, `{rounded.lg}`. Largeur `{spacing.queue-width}` (320). Dans l'ordre : le **nom de la fonction** en `label` `{colors.accent-text}` — la variante de texte, l'accent plein n'atteignant que 4,13:1 en 11 px sur cette surface —, le **nom du lot** en `data`, la barre (6 px, accent en cours), puis frames/total, temps passé, temps restant. Terminée : bordure et barre en `{colors.state-complete}`, plus deux boutons — *dossier* et *fichier* — ou le **bouton dossier seul** quand le résultat est une collection de frames.
- **Pastille d'activité** (bascule du panneau, en-tête) : `{colors.accent}` quand une tâche tourne, éteinte sinon. **Jamais verte** — le vert est un verdict, pas une disponibilité.
- **Panneau latéral.** `{spacing.side-panel-width}` (300). **Ce n'est pas le panneau de progression** : deux surfaces distinctes, deux largeurs distinctes (300 contre `{spacing.queue-width}` 320), deux bascules indépendantes — le panneau latéral porte les réglages de l'atelier courant, la file des tâches porte l'avancement, et fermer l'un n'a aucun effet sur l'autre. Elles peuvent être visibles en même temps. Il porte des **contrôles**, pas de la prose (`EPIC7-ARB-22`) : il ne répète ni le timecode, ni le numéro de frame, ni la position d'une poignée — tout cela est dans l'image. Une ligne de texte n'y est légitime que pour un **motif** qu'aucun contrôle ne peut porter. Un choix y prend la forme d'une **liste à cocher**, jamais d'un paragraphe suivi d'un bouton à long libellé. Il se **rétracte** partout, poignée de rappel conservée (`EPIC7-ARB-25`).
- **Barre de réglages (bas).** Colonnes titrées en `label`, champs `{rounded.sm}`. Un champ **essentiel manquant** prend une bordure `{colors.state-absent}` et un fond `rgba(229,72,77,.12)` ; tant qu'il est rouge, l'action de l'atelier est bloquée. L'action principale de l'atelier vit **à droite de cette barre**, en `button-primary`, sans ombre.
- **Aperçu de page (atelier Pdf).** Page sur `{colors.paper}`, coins droits, posée sur le mat. L'aperçu est **vivant** : chaque changement de réglage redessine la planche, sans bouton. Les éléments techniques de la planche (marqueurs, QR, patchs, blocs de texte) se dessinent à leur géométrie réelle, en `paper-ink` — ils appartiennent au tirage, pas à l'interface, donc ils ne prennent **aucune** couleur de l'outil.
- **Réglages d'export (panneau latéral, Exports).** Groupés et nommés comme dans **DaVinci Resolve** (`EPIC7-ARB-19`) : *Preset*, *Vidéo* (format, codec, variante, résolution, cadence, débit, profondeur), *Audio* (codec, échantillonnage, pistes), *Fichier* (nom, destination). Un terme inventé ici coûterait une traduction mentale à chaque export. Une ligne = libellé à gauche, valeur cadrée à droite en `data`.
- **Modale.** 460 px, `{rounded.xl}`, ombre flottante. Titre `title`, corps défilant, actions en bas à droite. Usages : confirmation d'extraction (cadences cochables + espace disque annoncé), écrasement (avertissement explicite de destruction, jamais forcé), dialogue de planche de calibration, dialogue de version au dépôt d'un second tirage.
- **Écran de gestion de projet.** Ouvert à chaque lancement, dernier projet en tête. `display` pour le nom du produit, lignes de projet en `body` + chemin en `data-sm` `{colors.text-secondary}`. Fond neutre plat — la maquette y pose un dégradé radial, écart à corriger.
- **Badge d'état.** `{rounded.full}`, `label`, fond à 16 % de la couleur d'état **composé sur la surface porteuse**, texte à la **variante `-text`** de cette couleur — pas à la chromie pleine, qui ne tient pas 4,5:1 en 11 px (voir *Plancher de contraste*). Réservé aux verdicts de **complétude** ; jamais utilisé pour nommer un type d'objet, jamais pour dire un rattachement (c'est `{components.state-glyph}`).

> **Dépendance nommée — l'iconographie, et ce qu'elle bloque.** Ce n'est pas une case vide : c'est une décision qui n'a pas de titulaire, et il faut dire lequel. Aucun jeu d'icônes n'est arrêté — style, graisse, taille, et surtout les **glyphes des quatre ateliers** et le **pictogramme par type de nœud** du chutier. Or le pictogramme par niveau est **l'un des quatre moyens** par lesquels `EPIC7-ARB-9` propose de rendre lisible une arborescence profonde (avec l'indentation, les filets de filiation et la puce de sélection) ; `key-chutier-v2.html` en dessine déjà un par type — dossier, rush, extraction, planche, scan, lot reconstruit —, et ces dessins n'ont jamais été confrontés à un système.
>
> **Ce qui est bloqué tant qu'elle n'est pas tranchée :** la maquette du chutier ne peut pas être déclarée finie (trois des quatre moyens de lisibilité sont spécifiés, le quatrième ne l'est pas) ; la **barre d'ateliers** ne peut pas être dessinée autrement qu'en texte seul ; le rail de 42 px du panneau d'arborescence replié **n'a aucun contenu spécifié** — il ne porte que des pictogrammes, par construction ; et le choix « icône *ou* mention *composite* » ci-dessous ne peut pas se trancher, puisqu'il compare un mot à un dessin qui n'existe pas.
>
> **Ce qui ne l'est pas :** les jetons, les géométries et les couleurs de cette spine sont indépendants du jeu d'icônes. Une story de chutier peut être écrite et développée avec des pictogrammes provisoires, à condition que **la substitution reste un remplacement d'assets** et non une reprise de mise en page — donc que la boîte du pictogramme soit fixée dès maintenant : **15 × 15 px**, en trait de 1,2 px, à la couleur du texte de la ligne (`currentColor`), jamais en aplat coloré.
>
> Le **lot composé** se nomme « icône (ou mention *composite*) + nom du lot + **numéro de passe** + date » — les deux repères, tranché le 2026-08-17 : le numéro distingue à l'œil deux compositions du même jour, la date permet de trier. **[À TRANCHER]** Le choix entre l'icône et le mot reste ouvert, et il est aussi une question d'i18n. Dépend de la date au manifest (story 5.13) : **tant qu'elle n'est pas livrée, aucun affichage du type « dernière version » n'est vrai**, et l'interface ne peut trier deux passes que dans l'ordre saisi par l'opératrice.
>
> **[À TRANCHER]** L'apparence de la **mire de remplacement** elle-même est produite par le cœur (frame synthétique « FRAME MANQUANTE »). La spine fixe son cadre ambre côté interface ; reste à décider si la GUI y superpose une marque propre ou si le graphisme de la mire suffit.
>
> **Les Préférences** ont désormais un contenu arrêté — voir `EXPERIENCE.md`, *Préférences utilisateur et réglages projet*. Visuellement elles reprennent l'ossature d'un atelier : rail de sections à gauche, réglages à droite, une ligne par réglage sur le modèle du panneau latéral. **Elles ne contiennent que des réglages effectifs** (`EPIC7-ARB-29`) : aucune ligne figée, aucun invariant affiché pour mémoire. Les **options de couleur avancées** sont ouvertes, non tranchées, et rien n'est à dessiner pour elles aujourd'hui.
>
> **[À TRANCHER]** L'iconographie du **menu contextuel** et de la **barre de menus** — cases à cocher d'état, marques de sous-menu, rendu des raccourcis clavier.

## Do's and Don'ts

| Do | Don't |
|---|---|
| Tous les neutres strictement R = G = B, de la barre d'onglets au texte | Reprendre les valeurs teintées de la maquette (`#17171a`, `#0d0d0f`, `#f4f4f2`, dégradé `#232329`) |
| Une bande de `{spacing.mat-min}` de neutre pur entre toute chromie et une image | Poser un accent, un badge ou une bordure colorée au contact d'une zone d'image |
| ROUGE = « il n'y a rien ici » · AMBRE = « il y a quelque chose, mais pas ton image » · VERT = fini/complet | Fondre les deux natures de manque en un seul indicateur, ou compter les mires avec les pages manquantes |
| Doubler chaque état d'une forme : disque plein, anneau creux, disque hachuré | Laisser rouge et ambre se distinguer par la seule couleur — c'est la paire la plus confusable, et l'outil s'ouvrira à des vidéastes |
| Complétude = **badge** (disque plein / anneau creux / disque hachuré) · Rattachement = **glyphe** (⊘ délié, ? non rattaché, ⚠ incomplet, `EPIC7-ARB-5`) | Fondre les deux familles dans un seul signe, ou rattacher le triplet de complétude à la référence `EPIC7-ARB-5` |
| Tout texte sous 18 px à **4,5:1** minimum contre la surface où il est **réellement** posé, `surface-hover` comprise | Poser une chromie sémantique ou l'accent en texte : ce sont des valeurs de trait, elles tombent à 3,3:1 en badge et 4,13:1 en `label` |
| Retirer un **onglet** qui n'a pas d'objet ; **griser** un contrôle qui en retrouvera un | Griser un onglet sans objet, ou faire disparaître un contrôle qui reviendra — le critère est la réversibilité (`EPIC7-ARB-24`) |
| Donner le bouton plein au chemin qui **ne détruit rien** | Mettre l'accent plein sur l'action destructrice d'une modale (`EPIC7-ARB-22`) |
| Écarter une frame par l'opacité, une hachure et une bordure neutre | Peindre en rouge une frame écartée, ou lui donner une case à cocher : l'écart est calculé, pas choisi |
| Accent pour la sélection, le focus, l'activité en cours | Accent comme verdict, ou vert pour dire « disponible » |
| Coins droits sur tout contenu d'image, cadre arrondi autour | Arrondir vignettes, previz, pages rastérisées, mires |
| Mono à chiffres tabulaires pour timecodes, cadences, compteurs, identifiants | Chiffres proportionnels dans une colonne qu'on lit pour repérer un trou |
| Timecode et libellés **au-dessus ou sous** l'image | Incruster une valeur sur l'image |
| Papier au blanc vrai dans l'aperçu PDF | Un blanc « de confort » cassé ou réchauffé |
| Ombres uniquement sur les surfaces flottantes, noires et sans teinte | Lueurs accent, ombres colorées, dégradés de surface, ombre débordant sur une image |
| Largeurs réglées par la poignée, **mémorisées et identiques dans les quatre ateliers** ; en-tête, onglets et transport constants (`EPIC7-ARB-40`) | Écrire que le chrome est « à largeurs constantes » — une poignée de largeur le contredit —, ou laisser un changement d'atelier redimensionner un panneau |
| Une poignée bornée par le plancher de la scène : 640 px, jamais franchis | Un plafond de poignée écrit en dur, ou un geste de largeur qui rend l'image trop petite pour être jugée |
| Libellés dimensionnés sur le contenu, +40 % de marge au-delà de l'anglais | Boîtes de largeur fixe calées sur l'anglais, ou libellé interactif tronqué |
| Poignées d'édition blanches à halo noir, disponibles en permanence | Poignées colorées, ou édition manuelle masquée quand la détection se déclare satisfaite |
| Codes du cœur affichés verbatim en `data`, à côté de leur phrase traduite | Traduire ou reformuler `LOT_INCOMPLETE`, `PAGE_QR_UNREADABLE`, `previz-1` |
| Un point de jugement visible avant chaque écriture (aperçu vivant, mode lecteur) | Une action qui écrit sans que l'écran ait montré ce qui sera écrit |
