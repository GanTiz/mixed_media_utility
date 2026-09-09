# Revue de la paire de spines — mixed_media_utility

## Verdict d'ensemble

La paire est exceptionnellement disciplinée sur ce qui se vérifie mécaniquement : les
50 références `{path.to.token}` des deux fichiers se résolvent toutes, chaque couleur
porte un hex, `EXPERIENCE.md` ne redéfinit **aucune** valeur visuelle (zéro hex, zéro px),
`DESIGN.md` suit l'ordre canonique complet, et les cinq parcours sources ont chacun leur
Key Flow avec protagoniste, étapes numérotées, **un** beat de climax et un chemin d'échec.
Elle est en revanche incomplète là où elle avait déjà été prévenue : la réconciliation
`reconcile-extraction-sources.md` a recensé 40 éléments perdus dont ~28 « à réintégrer »,
et deux d'entre eux — la **péremption d'un aperçu** (E04) et la **surface d'affichage des
avertissements** (E05, une vingtaine de codes contractuellement non fusionnables) — sont
absents des deux spines alors qu'ils portent directement l'invariant central du produit
(« juger avant d'écrire »). S'y ajoute une contradiction dure entre les deux spines sur le
nommage du lot composé. Conclusion : contrat exploitable tel quel pour Extraction et Pdf,
insuffisant pour les stories Scan et Exports, et un point décidé à réconcilier avant
d'écrire quoi que ce soit.

## 1. Couverture des flux — strong

Les cinq parcours de `.working/parcours-utilisateurs-epic7-2026-08-17.md` (P1→P5) ont
chacun leur Key Flow, dans l'ordre, avec protagoniste nommé au titre, situation, étapes
numérotées, **exactement un** `**Climax :**` (l. 424, 448, 477, 497, 531) et un bloc
`**Échecs.**` (l. 431, 456, 484, 506, 541). La variante « sans le projet » de P2 est
conservée. Les étapes non livrées sont signalées sur place. Aucun manque de couverture.

### Findings
- **moyen** Le Flow 3 place une **étape 9 après son climax** (l. 480-482), qui est en
  réalité un second micro-parcours (le « deuxième défaut » — sous-section propre dans la
  source, l. 348). Il introduit un comportement qui n'existe **nulle part ailleurs** dans
  la paire : « elle relance la détection **de cette page** avec ce profil » (EXPERIENCE.md
  l. 482 — occurrence unique). Ni *Component Patterns*, ni *State Patterns*, ni les huit
  rôles du chutier ne portent la détection à la page : point d'entrée, sort des ajustements
  de coins déjà faits sur cette page, et effet sur la complétude du lot sont tous
  indéterminés. *Correctif :* soit en faire un Flow 6 court, soit lui donner une ligne de
  *Component Patterns* qui dit d'où il se déclenche et ce qu'il écrase.
- **moyen** Le Flow 5 est cible à partir de l'étape 4, mais le marquage `*(cible)*`
  n'apparaît qu'aux étapes 4 et 1 (l. 513, 519) ; les étapes 5 à 10, dont le climax,
  ne portent aucune marque. Un rédacteur de story 7.x qui lit le flow de haut en bas
  spécifiera des comportements interdits par la section *Cible non livrée*. *Correctif :*
  une mention en tête de flow (« étapes 4-10 : cible ») plutôt qu'un marquage épars.
- **faible** La *Variante* du Flow 2 (l. 453-455) est un sixième chemin sans bloc d'échecs
  propre ; le bloc `**Échecs.**` qui suit porte visiblement sur elle (« projet né du scan
  seul ») mais est attaché au flow principal. *Correctif :* rattacher explicitement.

## 2. Complétude des tokens — adequate

Extraction complète du frontmatter (21 couleurs, 7 rôles typographiques, 7 rayons,
18 espacements, 12 composants) et des références en prose des deux fichiers :
**50 références, 50 résolutions, 0 manque**. Chaque token de couleur porte un hex — le
critère critique est passé. Les cibles de contraste, en revanche, ne sont énoncées nulle
part.

### Findings
- **élevé** **Aucune cible de contraste n'existe dans la paire** — ni ratio, ni niveau WCAG,
  ni mention d'une combinaison porteuse — alors qu'`EXPERIENCE.md` l. 297 délègue
  explicitement : « Le contraste et la couleur sont dans `DESIGN.md` ». Le renvoi pointe
  vers une section qui ne contient pas la chose. Aucune AC d'accessibilité de story 7.x
  n'est rédigeable. *Correctif :* une ligne dans `DESIGN.md.Colors` fixant la cible
  (AA 4.5:1 texte / 3:1 non-textuel) et la liste des combinaisons à vérifier.
- **élevé** Calculées, **trois combinaisons porteuses tombent sous AA** : `accent-on`
  `#FFFFFF` sur `accent` `#4C7EF3` = **3,76** (c'est le texte de
  `{components.button-primary}`, l'action principale des quatre ateliers) ;
  `state-absent` `#E5484D` sur `surface-panel` = **4,35** (c'est
  `bin-row.foreground-delinked`, et l'arbitrage E veut que **la couleur porte seule**
  l'état délinké) ; `state-absent` sur `image-mat` = **3,62** (bordure de vignette absente).
  *Correctif :* soit assombrir `accent` / éclaircir `state-absent`, soit inscrire
  l'exemption au titre du texte large / de l'élément non textuel, mais le dire.
- **élevé** La règle « la couleur ne porte jamais seule » (EXPERIENCE.md l. 324-340,
  ARBITRAGE 10) n'est **pas outillée dans les tokens qui l'implémentent** : le vocabulaire
  de formes (`shapeComplete` / `shapeAbsent` / `shapeSubstitute`) vit uniquement dans
  `components.badge-state`, alors que la règle porte sur les **lignes de chutier** et les
  **vignettes**. Or `components.bin-row` et `components.frame-thumb` n'ont **aucune clé de
  forme** — un consommateur qui génère depuis le frontmatter livre de la couleur seule.
  Et `badge-state` est par ailleurs déclaré « réservé aux verdicts », donc le renvoi croise
  deux règles contraires. *Correctif :* hisser les formes en groupe de tokens propre
  (`shapes-state`), référencé par `bin-row`, `frame-thumb` et `badge-state`.
- **moyen** Deux littéraux non tokenisés dans `DESIGN.md` : l'ombre flottante
  `0 16px 48px rgba(0,0,0,.55)` (l. 280) — il n'existe aucun groupe `shadow` au frontmatter,
  donc rien à référencer — et le fond de champ manquant `rgba(229,72,77,.12)` (l. 311),
  soit `state-absent` à **12 %**, quand `badge-state` (l. 325) pose le même motif à **16 %**.
  Deux alphas pour une seule idée, aucun des deux nommé. *Correctif :* un groupe `shadow`
  et un token d'alpha d'état unique.
- **faible** Cinq tokens définis sans rôle assigné nulle part : `accent-pressed` (aucun état
  pressé n'est décrit), `data-lg` (16 px, la prose l. 232 le liste sans lui donner d'emploi),
  `rounded.DEFAULT` (6 px, doublon exact de `rounded.md`), `border-strong` et `text-disabled`
  (cités par leur hex dans la prose, jamais par leur nom). *Correctif :* leur donner une
  ligne d'emploi ou les retirer.

## 3. Couverture des composants — thin

Extraction de tous les noms de composants employés dans les deux fichiers. Les 12 composants
du frontmatter ont bien une ligne visuelle dans `DESIGN.md.Components` **et** une ligne
comportementale dans `EXPERIENCE.md.Component Patterns`, avec de vraies règles. Le problème
porte sur les composants **non tokenisés** et sur le raccord des noms.

### Findings
- **élevé** Le **comparateur de candidats** n'a de spécification dans aucune des deux
  spines. Il figure comme surface à l'IA (EXPERIENCE.md l. 57), il est l'outil du climax du
  Flow 5 (l. 529) et il est cité en *State Patterns* (l. 208), mais aucune ligne de
  *Component Patterns*, aucun bullet de `DESIGN.md.Components`, aucun token. Rien ne dit
  comment les candidats sont disposés, comment on en désigne un, ce qui se passe à trois
  candidats ou plus, ni comment on annule une désignation. *Correctif :* un token
  `candidate-comparator` + une ligne dans chaque spine.
- **élevé** **Aucun interrupteur / bascule n'est spécifié**, alors que la paire en emploie
  au moins quatre : frames supprimées et calibration couleur (`DESIGN.md` l. 304), bascule
  du panneau de progression, marche/arrêt du balayage. `DESIGN.md` ne les mentionne que
  comme « les bascules », entre parenthèses. Aucune apparence, aucun état actif/inactif,
  aucun rayon. *Correctif :* un composant `toggle` au frontmatter — c'est le contrôle le
  plus répandu de l'application après la ligne de chutier.
- **moyen** Le **sélecteur de mode de previz** (Vidéo/Galerie ; PDF/Galerie/Lecteur) n'est
  spécifié ni visuellement ni comportementalement — il est nommé une fois dans le bullet
  *Scène de previz* (`DESIGN.md` l. 304) et une fois à l'IA. C'est pourtant le contrôle qui
  commute les trois surfaces de jugement du produit. *Correctif :* une ligne dans chaque
  spine (segmenté ou onglets ? mémorise-t-il son mode par atelier ?).
- **moyen** Trois surfaces de l'IA sans aucune spec de composant : la **frame en plein
  écran** (fond, chrome, est-ce une modale ? le bouton *éditer* y vit où ?), la **section
  Calibration** du chutier (que fait un clic sur un profil ? peut-on en supprimer un ?),
  et le **panneau de progression** comme conteneur (ordre des cartes, durée de vie d'une
  carte terminée, défilement, réordonnancement — alors que la file d'exports réordonnable
  est déclarée décidée l. 384). *Correctif :* une ligne par surface.
- **moyen** Les bullets de `DESIGN.md.Components` portent des **noms d'affichage français**
  quand le frontmatter et `EXPERIENCE.md` portent des **noms de tokens kebab anglais**, sans
  table de correspondance. La résolution est devinable pour la plupart, mais **fausse de
  périmètre** dans deux cas : `{components.bin-row}` (le token spécifie une *ligne*) renvoie
  au bullet « Chutier (bin) » (qui décrit l'*arbre entier*), et `{components.params-field}`
  (un *champ*) renvoie au bullet « Barre de réglages (bas) » (la *barre*). *Correctif :*
  titrer chaque bullet par son nom de token.
- **faible** `{components.button-primary}` a une ligne comportementale (EXPERIENCE.md l. 184)
  et un objet au frontmatter, mais **aucun bullet propre** dans `DESIGN.md.Components` — il
  n'est mentionné qu'en fin du bullet *Barre de réglages*. *Correctif :* un bullet propre.

## 4. Couverture des états — thin

Parcours des 18 surfaces de l'IA. **Les cinq états métier hors canon demandés sont tous
présents et bien tenus** : lot complet et lot complet-avec-mires ne sont jamais fondus
(EXPERIENCE.md l. 201-202, `DESIGN.md` l. 220), média délinké (l. 195), fichier déposé non
décodé (l. 197-198), plusieurs candidats par frame (l. 208). C'est la partie la mieux
travaillée de la paire. Les manques sont ailleurs, et deux d'entre eux étaient déjà
signalés par la réconciliation.

### Findings
- **critique** **Aucun état de péremption d'un aperçu** (E04, `reconcile-extraction-sources.md`
  l. 110-121, classé « à réintégrer »). Le mot « périmé » n'apparaît dans la paire que dans
  « périmètres » et dans le rappel du refus actuel (l. 367). Or toute la section *Points de
  jugement avant écriture* repose sur le fait que ce qu'on regarde correspond aux réglages ;
  les empreintes `fingerprints.selection` / `.source_report` / `.source_signature` du contrat
  `previz-1` existent précisément pour fermer ce piège, et l'aperçu vivant de la planche est
  déclaré « sans bouton », donc rien ne signale à l'écran qu'il est en retard. L'invariant
  central du produit n'a pas d'état qui le protège. *Correctif :* un état « aperçu périmé »
  en *State Patterns*, appliqué à `page-preview` et au mode lecteur.
- **critique** **Aucune surface d'avertissement** (E05, ibid. l. 123-137, « à réintégrer »).
  Les contrats produisent une vingtaine de codes en familles fermes (`ingest` / `detection` /
  `output` / `previz` / `encode`), avec interdiction contractuelle de les fusionner. La paire
  n'en expose qu'**un** (`GAMUT_CLIPPING_DETECTED`, l. 206) et le traite en état ad hoc.
  Sans lieu où les poser, ils disparaîtront ou seront fondus en un indicateur unique —
  exactement la faute que la paire s'interdit par ailleurs pour les deux natures de manque.
  *Correctif :* une surface d'avertissements dans l'IA, adressée par famille, et sa ligne
  de *State Patterns*.
- **élevé** **Aucun état de tâche en échec.** *State Patterns* couvre « Tâche en cours » et
  « Tâche terminée » ; `components.job-card` a `border-done` et `bar-done` mais aucune
  variante d'erreur. La ligne générique « Échec d'une écriture | Partout » (l. 212) dit qu'il
  faut un motif et une prise, sans dire à quoi ressemble la carte ni si l'on peut relancer.
  Une détection ou une extraction TIFF qui échoue au milieu d'une file est le cas courant.
  *Correctif :* un état d'échec sur `job-card` (couleur, motif, relance).
- **élevé** **Aucune annulation de tâche en cours.** Le seul « annul- » de la paire porte sur
  la profondeur d'annulation d'édition (l. 239, déjà `[À TRANCHER]`). Sur un outil qui écrit
  des TIFF pour des centaines de pages en arrière-plan, l'impossibilité d'arrêter une file
  lancée par erreur est une décision produit, pas un oubli d'écriture. *Correctif :* trancher
  et l'inscrire sur `job-card`.
- **élevé** **Aucun état de chargement à froid nulle part.** Ni squelette, ni vignette en
  attente, ni progression d'ouverture de projet — alors que la source pose « un projet peut
  totaliser des **centaines de pages** » (parcours l. 84) et que E01 (cache de
  prévisualisation) chiffre un facteur 500. La galerie est la surface la plus sollicitée du
  produit et elle n'a pas d'état d'attente. *Correctif :* un état de chargement par surface
  d'image, et le vocabulaire de vignettes d'E02 (absente / exacte / approximative), dont la
  réintégration était recommandée précisément pour que l'outil ne présente pas une image
  approximative comme exacte.
- **élevé** **Une page dont le QR désigne un autre projet n'a pas d'état.** Le Flow 4
  décrit un vrac « mêlant plusieurs lots et parfois **plusieurs projets** » (l. 501), et la
  seule règle disponible est « ce que la détection ne rattache pas reste dans le tampon ».
  Cela confond deux choses très différentes : *illisible* et *appartient à un autre projet*.
  E11 (rang d'ingestion vs `page_index` décodé) était classé « à réintégrer » comme seul
  diagnostic disponible quand le rangement du vrac tourne mal. *Correctif :* distinguer les
  deux issues dans l'état du tampon.
- **moyen** **États vides quasi absents.** Seul « Chutier vide | Extraction » existe (l. 194).
  Rien pour : Scan sans scan, Exports sans lot reconstruit, panneau de progression sans
  tâche, section Calibration sans profil, galerie d'un lot sans frame détectée, écran de
  gestion de projet au tout premier lancement. *Correctif :* une ligne par surface, même
  brève.
- **moyen** **Aucun état de permission refusée ni de support indisponible**, alors que la
  cible est macOS 11+ (autorisations Bureau/Documents/volumes amovibles au premier
  lancement), que les rushes vivent hors du dossier de travail et que le disque du projet
  « circule » entre deux stations : dossier de travail en lecture seule, volume réseau
  démonté, fichier verrouillé par une autre application, disque plein **pendant** l'écriture
  (l'espace n'est annoncé qu'*avant*, en modale). *Correctif :* une ligne de *State Patterns*
  pour l'accès refusé et une pour l'écriture interrompue faute de place.
- **moyen** Deux états métier de second rang non couverts : la couleur de complétude d'un lot
  **pendant** que sa détection tourne (verdict prématuré ?), et l'affichage d'un **scan
  portant plusieurs lots** (rôle 3 du chutier l'annonce, aucune règle ne dit comment l'arbre
  inversé le représente). *Correctif :* deux lignes.

## 5. Couverture des références visuelles — thin

`imports/` ne contient qu'un fichier, `extraction-sources-epic7.md`, référencé au frontmatter
d'`EXPERIENCE.md` : pas d'orphelin de ce côté. Il n'existe **ni `mockups/` ni `wireframes/`**.
La seule référence visuelle de la paire est la maquette `gui-prototype/index.html`, citée
six fois dans `DESIGN.md`.

### Findings
- **élevé** **La référence `gui-prototype/index.html` ne se résout pas** depuis le workspace :
  la maquette vit à la racine du dépôt, le chemin est écrit en relatif (`DESIGN.md` l. 198),
  et six passages en dépendent — dont cinq **corrections** que le consommateur doit appliquer
  mentalement écran par écran (valeurs teintées, lueur du bouton Extract, dégradé de l'onglet
  actif, vignettes arrondies, dégradé radial du lancement). C'est la seule référence de
  composition de tout le corpus, et elle est simultanément inatteignable et déclarée fausse
  sur ses valeurs. *Correctif :* chemin depuis la racine du dépôt, et une capture corrigée
  déposée dans `imports/` ou `mockups/`.
- **moyen** **Aucune référence n'est appelée en ligne à la section pertinente.**
  `imports/extraction-sources-epic7.md` n'apparaît qu'au frontmatter, jamais là où il sert
  (les vocabulaires de codes en *Voice and Tone*, les contrats `previz-1` en *Foundation*).
  Les exemples canoniques posent au contraire un renvoi à la section concernée
  (`→ Composition reference: mockups/…`). *Correctif :* un renvoi en ligne par section
  consommatrice, nommant ce que la référence illustre.
- **moyen** **La règle « la spine gagne en cas de conflit » n'est énoncée qu'à moitié.**
  `DESIGN.md` l. 198 la pose pour les *valeurs* de la maquette (« ses valeurs ne sont pas
  reprises »), ce qui est plus étroit que la règle attendue, et `EXPERIENCE.md` ne mentionne
  **jamais** l'existence de la maquette — un consommateur qui ouvre la spine comportementale
  et le prototype côte à côte n'a aucune règle d'arbitrage. *Correctif :* une phrase unique,
  générale, dans chaque spine.
- **faible** `.working/parcours-lecture-mobile.html` est le seul HTML du workspace et n'est
  référencé par aucune des deux spines ; c'est un support de lecture, mais un consommateur
  peut le prendre pour une maquette. *Correctif :* une ligne de statut, ou le sortir de la
  zone lisible.

## 6. Gonflement et sur-spécification — adequate

Les deux fichiers sont denses et la quasi-totalité de la prose est rattachée à une décision.
`DESIGN.md` porte une voix éditoriale, ce qui est son droit ; `EXPERIENCE.md` reste
opérationnel, ne redéfinit **aucune** valeur visuelle (vérifié : zéro hex, zéro px) et n'a
pas de narration décorative hors des climax, où elle est attendue. Les tables sont employées
là où elles servent. Peu à couper, mais quelques redites de scope.

### Findings
- **moyen** « **Modale. 460 px** » (`DESIGN.md` l. 314) est une largeur fixe en pixels, sans
  token, et elle **contredit une règle de la même spine** : « aucune boîte n'est calée sur la
  longueur de l'anglais », « +40 % de marge au-delà de l'anglais » (l. 240). C'est la seule
  sur-spécification en pixels de la paire, et elle tombe sur le composant le plus exposé à
  l'i18n. *Correctif :* une largeur min/max tokenisée.
- **moyen** La section **Reprise du travail après interruption** (l. 242-262) reprend pour
  l'essentiel des contenus déjà posés : l'ouverture systématique de l'écran de projet est
  déjà à l'IA (l. 44) *et* en *State Patterns* (l. 193), la forme de l'arbre est déjà le
  rôle 2 du chutier (l. 84) *et* le climax du Flow 4 (l. 497). Ce qu'elle apporte en propre
  tient en deux bullets (rien ne dépend d'un état de session ; aucun horodatage affiché comme
  tri). *Correctif :* la réduire à ce qui n'est dit nulle part ailleurs.
- **moyen** La règle des **deux natures de manque** est énoncée **six fois** avec un périmètre
  légèrement différent à chaque fois (`DESIGN.md` l. 218, 220, 331 ; `EXPERIENCE.md` l. 144,
  201-202, 314, 484). C'est l'invariant central, une répétition est défendable — mais les
  formulations divergent déjà sur ce qu'on compte (« mires » vs « frames synthétiques »,
  voir §7), et c'est ainsi que commence la dérive. *Correctif :* une formulation canonique,
  citée à l'identique.
- **faible** Le diagramme ASCII de `DESIGN.md` (l. 251-262) réinscrit en dur les valeurs
  `44`, `250`, `300`, `54` qui sont des tokens (`header-height`, `bin-width`,
  `side-panel-width`, `tabbar-height`) : il devient faux au premier changement de token.
  *Correctif :* nommer les tokens dans le diagramme.

## 7. Discipline d'héritage — thin

Les renvois de tokens d'`EXPERIENCE.md` vers `DESIGN.md` se résolvent tous (25 références,
0 manque) et la spine comportementale ne réécrit aucune valeur — c'est la meilleure moitié
de cette catégorie. Le frontmatter `sources` d'`EXPERIENCE.md` désigne cinq sources réelles.
Ce qui casse, c'est la fidélité aux décisions et l'unicité du vocabulaire.

### Findings
- **critique** **Les deux spines se contredisent sur le nommage du lot composé, et la spine
  comportementale rouvre une décision close.** `DESIGN.md` l. 320 : « icône (ou mention
  *composite*) + nom du lot + **numéro de passe** + date ». `EXPERIENCE.md` l. 283 : « icône
  **ou** mention *composite* + le nom du lot + une **date** » — le numéro de passe a disparu.
  Pire, `EXPERIENCE.md` l. 290-293 marque `[À TRANCHER]` le fait de savoir « si l'interface
  montre ce numéro, le masque derrière la date, ou le demande », alors que le canon l'a
  tranché : `.memlog.md` l. 131, ARBITRAGE 9 — « on affiche **le numéro et la date** » —
  confirmé par l'entrée de mise à jour des spines elle-même (l. 133 : « le lot composé
  affiche numéro ET date ») et par la source longue (parcours l. 561-566). La règle
  d'arbitrage déclarée au frontmatter (« l'entrée la plus tardive gagne ») désigne
  ARBITRAGE 9. C'est la règle qu'une story 7.x implémenterait, et elle est écrite dans deux
  versions incompatibles. *Correctif :* aligner `EXPERIENCE.md` sur ARBITRAGE 9 et supprimer
  ce `[À TRANCHER]` ; ne garder ouvert que le choix icône/mot.
- **moyen** **La paire viole sa propre règle de vocabulaire** (« Nommer l'objet … | Inventer
  un synonyme par écran », `EXPERIENCE.md` l. 152) sur son objet le plus sensible : la même
  chose s'appelle **mire de remplacement** (5 occurrences), **frame de substitution**
  (`DESIGN.md` l. 218) et **frame synthétique** (`DESIGN.md` l. 220, 322 ; `EXPERIENCE.md`
  l. 315), quand le cœur dit `SYNTHETIC_FRAME_WRITTEN`. La microcopie d'exemple compte des
  « 3 mires de remplacement » (l. 144) pendant que la règle de comptage, elle, compte des
  « frames synthétiques » (`DESIGN.md` l. 220). *Correctif :* un terme d'interface unique,
  et le code du cœur affiché à côté comme le prévoit déjà la règle.
- **moyen** **Deux systèmes de numérotation d'arbitrages coexistent dans les sources
  déclarées, et la spine cite l'un sans le nommer.** `EXPERIENCE.md` renvoie à « arbitrage 6 »
  (l. 38) et « arbitrage 2 » (l. 257) : ces numéros résolvent dans `.memlog.md` (l. 112 et
  l. 96), mais la source longue des Key Flows numérote les **mêmes** décisions en lettres
  A–J (tutoriel = **I**, désignation au manifest = **B**). Le piège est actif : dans le
  parcours, l'élément numéroté **2** est « Dater les passes » (l. 528), donc un lecteur qui
  chasse « arbitrage 2 » dans la source la plus évidente atterrit sur une **autre** décision.
  *Correctif :* citer la source avec le numéro (`memlog ARBITRAGE 2`), ou unifier.
- **moyen** **Les deux documents de réconciliation ne sont pas dans les `sources`** alors
  qu'ils portent le registre E01-E40 qui commande ce que les spines devaient absorber (et
  dont deux éléments « à réintégrer » manquent, voir §4). Un consommateur ne peut pas
  savoir, depuis les spines, ce qui a été écarté sciemment et ce qui a été perdu.
  *Correctif :* les ajouter aux `sources` avec leur rôle.
- **faible** Deux imprécisions de frontmatter : `.memlog.md (118 entrées)` en compte
  aujourd'hui **129** — la référence est déjà périmée ; et les entrées de `sources` sont des
  phrases (« DESIGN.md (même dossier) — référence visuelle… ») plutôt que des chemins,
  donc non résolvables par un consommateur machine, contrairement à la forme canonique.
  `DESIGN.md` ne déclare quant à lui **aucune** `sources`, ce que la spec autorise mais qui
  rend l'héritage asymétrique. *Correctif :* chemin nu + commentaire séparé ; retirer le
  décompte, ou le tenir.

## 8. Conformité de forme — adequate

`DESIGN.md` est dans l'ordre canonique, complet, sans section inventée : Brand & Style →
Colors → Typography → Layout & Spacing → Elevation & Depth → Shapes → Components → Do's and
Don'ts. Rien à redire. `EXPERIENCE.md` porte toutes ses sections obligatoires (Foundation,
Information Architecture, Voice and Tone, Component Patterns, State Patterns, Interaction
Primitives, Accessibility Floor, Responsive & Platform, Key Flows).

**Jugement des six sections inventées.**

| Section | Verdict | Motif |
|---|---|---|
| *Le chutier — huit rôles* | **Gagne sa place** | Une seule surface porte huit responsabilités distinctes ; la ligne unique de l'IA ne peut pas les tenir, et la source désigne le chutier comme « le point où une erreur de conception coûterait le plus cher ». Forme tabulaire, chaque rôle énonce sa conséquence comportementale. |
| *Points de jugement avant écriture* | **Gagne sa place** | Règle transverse qu'aucune section canonique ne peut héberger (ce n'est ni un état, ni un composant, ni une primitive) et qui produit une AC testable. Sa sous-section *D'où viennent les images de l'aperçu* gagne aussi la sienne : source unique, nature jetable, dépendance signalée. |
| *Reprise du travail après interruption* | **Gagne sa place, mais surdimensionnée** | L'écart de trois semaines est le différenciateur du produit ; deux bullets sur six sont propres, le reste redit l'IA, les *State Patterns* et le Flow 4 (voir §6). |
| *Composition d'un lot à partir de candidats* | **Gagne sa place** | Fonction entièrement cible, avec une garde d'invariant (« la garde agit pendant la composition, pas en verdict après coup ») qu'aucune section canonique ne saurait porter. Statut cible annoncé au chapeau. |
| *Cible non livrée* | **Gagne sa place — la plus utile de la paire** | C'est la barrière entre ce qu'une story 7.x peut spécifier et ce qu'elle ne peut pas ; trois colonnes (comportement / état réel / ce qui débloque). |
| *Fermeture de l'architecture d'information* | **Gagne sa place** | Registre d'orphelins explicite ; vérification faite, la fermeture qu'elle revendique tient — les 17 surfaces de l'IA hors Préférences sont bien atteintes par au moins un flow. |

### Findings
- **élevé** *Cible non livrée* — la section dont le rôle entier est de barrer la route aux
  stories 7.x — **ne nomme qu'une seule des quatre stories d'Epic 5 qui la lèvent** : 5.13
  pour la date au manifest, et pour les trois autres « Story d'Epic 5 », « Stories d'Epic 5
  déjà spécifiées », « Payload 2.1 » (l. 365-369). Les numéros existent au dépôt
  (`5-12-tirages-multiples-du-meme-lot.md`, `5-14-plusieurs-scans-de-la-meme-planche.md`,
  `5-17-payload-qr-cles-courtes.md`…). Sans eux, un rédacteur de story ne peut ni vérifier
  l'état réel d'une dépendance, ni la déclarer en amont. *Correctif :* numéroter les quatre.
- **moyen** **Aucune section *Inspiration & Anti-patterns***, alors que son contenu existe et
  est mal logé : le modèle revendiqué — **DaVinci Resolve**, quatre ateliers en onglets bas,
  « on travaille *dans* un atelier, on n'y navigue pas » — est un héritage **comportemental**
  et il n'est écrit que dans `DESIGN.md.Brand & Style` (l. 194) ; les rejets sont dispersés
  dans « Bannis partout » (l. 232-236) et dans les *Don'ts* visuels. *Correctif :* la section,
  avec ce qui est repris de Resolve et ce qui est rejeté, dans la spine comportementale.
- **faible** *Fermeture de l'architecture d'information* mélange deux registres sous un
  en-tête qui n'en annonce qu'un : sa colonne s'appelle « Surface orpheline », mais quatre
  de ses six entrées sont des **fonctions** (marqueurs du transport, base de timecode au clic
  droit, file d'exports réordonnable, re-scan partiel), pas des surfaces. Par ailleurs le
  rôle 8 du chutier (versions et lot composé) est cible non livrée, mêlé sans marque aux
  sept rôles livrés. *Correctif :* deux tables, et une colonne « livré / cible » sur les
  huit rôles.

## Notes mécaniques

- **Résolution des tokens : 50 références, 50 résolutions, 0 rupture** (25 dans `DESIGN.md`,
  25 dans `EXPERIENCE.md`). Toutes les couleurs portent un hex. Aucun `{path}` orphelin.
- **Tokens définis et jamais employés :** `colors.accent-pressed`, `colors.border-strong`,
  `colors.text-disabled`, `colors.surface-canvas`, `typography.display`, `typography.title`,
  `typography.body`, `typography.data-lg`, `rounded.DEFAULT`, `spacing.1/2/3/6/7/8`.
  La plupart sont couverts par la prose ; `accent-pressed`, `data-lg` et `rounded.DEFAULT`
  ne le sont pas du tout (voir §2).
- **`EXPERIENCE.md` ne contient aucun littéral visuel** — zéro hex, zéro valeur en px.
  Discipline d'héritage respectée sur les valeurs.
- **Contradiction de placement du bouton *Détecter*.** Trois passages le posent au chutier
  (IA l. 50, rôle 4 l. 87, Flow 1 l. 416, plus `DESIGN.md` l. 303 : la zone tampon « porte le
  bouton **Détecter** ») ; un quatrième le pose ailleurs : `{components.button-primary}` est
  décrit « Droite de la barre de réglages » et sa liste d'actions principales inclut
  « Détecter puis Extraire » (l. 184). C'est le contrôle qui commande tout l'atelier Scan ;
  un rédacteur de story doit deviner. **Sévérité : élevé.**
- **Frontmatter.** `EXPERIENCE.md` : `name`, `status: final`, `sources` (5), `updated`
  — complet, mais `status: final` cohabite avec **18 `[À TRANCHER]`** (8 dans `DESIGN.md`,
  10 dans `EXPERIENCE.md`), dont plusieurs bloquants pour une story (géométrie du panneau de
  progression, taille minimale de fenêtre, iconographie entière, engagement lecteur d'écran).
  `DESIGN.md` : conforme à la spec (`name`, `description`, `colors`, `typography`, `rounded`,
  `spacing`, `components`), pas de `sources` ni de `status`.
- **Décompte de source périmé :** `.memlog.md (118 entrées)` → 129 entrées réelles.
- **Renvoi cassé :** `gui-prototype/index.html` (chemin relatif au dépôt, cité depuis un
  workspace situé cinq niveaux plus bas).
- **Renvoi vide :** `EXPERIENCE.md` l. 297 renvoie le contraste à `DESIGN.md`, qui n'en parle
  pas.
- **Numérotation d'arbitrages ambiguë :** lettres A–J dans les parcours, chiffres 1–10 dans
  le memlog, pour les mêmes décisions ; `EXPERIENCE.md` cite les chiffres sans nommer la
  source.
