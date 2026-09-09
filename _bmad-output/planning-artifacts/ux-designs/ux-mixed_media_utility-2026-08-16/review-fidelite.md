# Revue de fidélité aux décisions — `DESIGN.md` / `EXPERIENCE.md`

> Angle **fidélité** de la Reviewer Gate (Epic 7 UX, 2026-08-18). Ce document
> **critique sans modifier** : ni `DESIGN.md` ni `EXPERIENCE.md` n'ont été
> touchés.
>
> Autorité des sources, dans l'ordre : `.memlog.md` (129 entrées, l'entrée la
> plus tardive gagne) · `.working/parcours-utilisateurs-epic7-2026-08-17.md`
> (v2.1) · `.working/relecture-egan-2026-08-17.md` et
> `.working/relecture-egan-v2-2026-08-17.md` · `.working/decouverte-*` /
> `imports/extraction-sources-epic7.md` / `reconcile-*.md`. Le prototype
> `gui-prototype/index.html` a été lu directement (il est marqué périmé, mais
> il est de fait la source d'une partie des valeurs de `DESIGN.md`).

---

## 1. Verdict d'ensemble

**La consigne a été tenue sur le fond : je n'ai trouvé aucune décision produit
inventée de toutes pièces.** Les six arbitrages d'Egan et les arbitrages 7 à 10
sont tous présents, tous dans leur **version tardive** (lecteur bi-format =
confort de développement et non garantie de compatibilité ; date au manifest
voulue ; granularité à la frame avec choix en bloc comme raccourci ; redondance
non chromatique qui nuance et ne défait pas « pas de badge »), et les cinq Key
Flows remontent phrase par phrase au parcours v2.1. La palette neutre, qui
serait le premier endroit où inventer, est au contraire une **déduction
correctement nommée** d'une contrainte métier explicite.

Le risque réel est ailleurs, et il est sérieux : **ce qui a été inventé, c'est
de la certitude, pas du contenu.** Les deux « trous majeurs » que la
réconciliation a trouvés et que le memlog enregistre explicitement comme
*« à trancher avant la rédaction des stories 7.x »* — la **surface d'affichage
des avertissements** et la **détection de péremption d'un aperçu** — ont
disparu des deux spines : ni traités, ni marqués `[À TRANCHER]`. Une décision
structurante encore ouverte (rasteriser le PDF réel *ou* dessiner le plan) est
tranchée en passant, et la tranche entraîne une erreur de fond sur les patchs
de calibration. Enfin, la section `Cible non livrée` **sous-compte ce qui n'est
pas livré** : elle annonce quatre dépendances quand le même document en renvoie
au moins six vers elle.

**Bilan chiffré** — 12 inventions · 8 déformations · 2 périmées · 5 déductions
acceptables non signalées comme telles · **7 `[À TRANCHER]` manquants**, dont
deux critiques.

---

## 2. Inventions

### I-01 — Les patchs de calibration dessinés en encre noire *(élevé)*

> « Les éléments techniques de la planche (marqueurs, QR, **patchs**, blocs de
> texte) se dessinent à leur géométrie réelle, **en `paper-ink`** — ils
> appartiennent au tirage, pas à l'interface, donc ils ne prennent **aucune**
> couleur de l'outil. »
> — `DESIGN.md`, *Components*, « Aperçu de page (atelier Pdf) »

**Ce qui manque.** La règle est juste pour les marqueurs, le QR et les blocs de
texte ; elle est **fausse pour les patchs**, qui sont chromatiques par
définition. Le contrat 4.9 transporte pour chaque patch un `value_id`, une
position, un `size_mm` **et son `rgb`**, avec le motif explicite : *« transporté
— la GUI n'a pas à redupliquer la résolution de table »*
(`imports/extraction-sources-epic7.md` §4). Un aperçu qui imprime les patchs en
`#111111` montre une planche de calibration monochrome, c'est-à-dire l'inverse
de ce que la planche existe pour faire.

Aucune source ne dit de peindre les patchs en encre. La formulation est une
généralisation plausible (« les éléments techniques appartiennent au tirage »)
appliquée à un élément qui n'y rentre pas.

**Recommandation — corriger et sourcer.** Séparer les éléments *monochromes du
tirage* (ArUco, QR, blocs de texte) des **patchs**, dessinés à leur `rgb`
transporté. Poser explicitement que ces valeurs sont **du contenu de page**, au
même titre que le blanc `paper`, et non une chromie de coque — sinon elles
tombent sous l'interdit « aucune chromie à moins de `mat-min` d'une image ».

### I-02 — L'aperçu PDF est « dessiné », décision déléguée tranchée en passant *(élevé)*

> « chaque changement de réglage redessine la planche, sans bouton. Les
> éléments techniques de la planche […] **se dessinent à leur géométrie
> réelle** »
> — `DESIGN.md`, *Components* ; repris dans `EXPERIENCE.md`,
> *Points de jugement avant écriture* et `{components.page-preview}`

**Ce qui manque.** La décision déléguée n°9 est **explicitement ouverte** :
*« la GUI rasterisera le PDF réel (état `rendered`) **ou** dessinera le plan
elle-même depuis les géométries transportées »* (import §4). La réconciliation
la classe **« Non — décision structurante encore ouverte »** et en donne le
motif : *« les deux n'ont ni le même coût, ni la même fidélité, ni le même sens :
dessiner le plan ne peut pas montrer un PDF rendu, rasteriser en direct à chaque
changement de réglage est un tout autre problème de performance »*
(`reconcile-extraction-sources.md` §5, ligne 9). Le memlog n'exige qu'un aperçu
« LIVE en direct », sans dire lequel des deux.

Les spines choisissent la deuxième branche, sans le dire, et I-01 en est le
dommage collatéral.

**Recommandation — marquer `[À TRANCHER]`.** C'est le premier des deux points
de jugement du produit ; le choix décide de ce que l'aperçu peut prouver.

### I-03 — « au moins 40 % de marge au-delà de l'anglais » *(moyen)*

> « Toute boîte de libellé se dimensionne sur son contenu avec au moins
> **40 % de marge au-delà de l'anglais** »
> — `DESIGN.md`, *Typography* ; repris dans *Do's and Don'ts*

**Ce qui manque.** Zéro occurrence de « 40 » dans le memlog, les parcours, les
deux relectures et la découverte. La règle de fond (i18n, anglais par défaut,
extensible) est adossée ; **le chiffre ne l'est pas**. C'est une convention
d'internationalisation défendable (30-40 % est la fourchette usuelle
anglais→langues romanes), mais elle est écrite ici comme un seuil de conformité,
c'est-à-dire exactement la forme qu'un critère d'acceptation prendra.

**Recommandation — marquer comme convention** (« convention d'i18n, non
tranchée par le projet ») ou `[À TRANCHER]`, pas retirer : la règle est utile.

### I-04 — « Un projet ouvert à la fois. » *(moyen)*

> — `EXPERIENCE.md`, *Foundation*

**Ce qui manque.** Le memlog dit « projet = un film = un dossier cible » et
« écran de gestion de projet TOUJOURS montré au lancement, dernier projet ouvert
en tête » — aucune de ces deux entrées n'interdit une seconde fenêtre. La
restriction a un coût réel : elle ferme d'avance la comparaison entre deux
projets, et elle frotte avec le mode collaboratif du memlog (« Egan doit pouvoir
ouvrir les projets de la cinéaste »).

**Recommandation — `[À TRANCHER]`.**

### I-05 — Accessibilité clavier, quatre règles fermes *(moyen)*

> « **Ordre de tabulation = ordre de lecture** sur chaque atelier ; `Échap`
> ferme toujours la surface la plus haute » · « déplacement d'**un pixel par
> pression de flèche** » · « Le bus de transport est **intégralement pilotable
> au clavier** »
> — `EXPERIENCE.md`, *Accessibility Floor* et *Interaction Primitives*

**Ce qui manque.** Aucune source ne parle de clavier nulle part (« clavier » :
0 occurrence dans memlog / parcours / relectures / découverte). Le memlog ne
décide qu'une chose voisine : la **loupe** s'active seule pour un réglage
« précis au pixel ». Ces quatre règles sont des conventions de plateforme
raisonnables, et l'une d'elles est même bien argumentée dans le texte
(« contrepartie exacte de l'exigence de pointage au pixel ») — mais elles sont
présentées comme acquises alors que la spine marque `[À TRANCHER]` le point
*voisin* (niveau d'engagement lecteur d'écran).

**Recommandation — marquer comme déduit**, avec le même motif que celui déjà
écrit pour l'édition des coins.

### I-06 — « Les Préférences vivent où la plateforme les met » / « Menu système » *(faible-moyen)*

> — `EXPERIENCE.md`, table d'*Information Architecture* et *Responsive & Platform*

**Ce qui manque.** Le memlog dit seulement : « les préférences sont GLOBALES à
l'app » et « contenu à réfléchir dans un SECOND TEMPS ». L'emplacement est une
convention de plateforme, pas une décision.

**Recommandation — marquer comme déduit.**

### I-07 — « Les modales s'empilent sur un seul niveau » *(faible)*

> — `EXPERIENCE.md`, *Règles de navigation* ; « Modale | Ponctuelle | 1 niveau »

Aucune source. Règle saine, présentée comme décidée. **Marquer comme déduit.**

### I-08 — « Local-first : pas de compte, pas de réseau, pas de synchronisation » *(faible)*

> — `EXPERIENCE.md`, *Foundation*

Le `project-brief` dit « utilitaire local-first » ; les trois négations sont une
extension. Elles sont probablement justes, mais « pas de réseau » est une
contrainte technique forte à énoncer sans source.

**Recommandation — marquer comme déduit.**

### I-09 — Zoom de vignettes « continu, pas de paliers » *(faible)*

> « La **grille de vignettes** est à zoom continu (la taille des miniatures est
> un réglage de la previz, pas un point d'arrêt) »
> — `DESIGN.md`, *Layout & Spacing* ; `EXPERIENCE.md`, *Interaction Primitives*

Le memlog dit « zoom sur la taille des miniatures », sans trancher continu vs
paliers. **Faible** — mais c'est le genre de détail qui devient un AC.

### I-10 — Bascule du panneau de progression « d'en-tête » *(faible)*

> « **Panneau de progression** | Bascule d'en-tête, depuis les **4** ateliers »
> · « **Pastille d'activité** (bascule du panneau, **en-tête**) »
> — `EXPERIENCE.md` / `DESIGN.md`

Le memlog dit « ancré à droite par défaut, activable/désactivable (comme un chat
dans VS Code) ». L'emplacement de la bascule est inventé. **Faible.**

### I-11 — « Barre d'onglets […] largeur égale » ; `display` 28 px « écran de gestion de projet, uniquement » *(faible)*

> — `DESIGN.md`, *Components* et *Typography*

Détails de mise en page sans source ; défendables. **Marquer comme conventions.**

### I-12 — L'autorité normative invoquée pour le mat *(faible, mais à vérifier)*

> « la convention *physique* (**ISO 3664**) est un gris moyen à **18 %**
> (≈ `#767676`) »
> — `DESIGN.md`, *Colors*, dans un `[À TRANCHER]`

**Ce qui manque.** La référence est extérieure au dépôt et n'est vérifiable
nulle part dans le workspace. Le « 18 % » est la convention **photographique**
de la charte grise ; ISO 3664 spécifie l'entourage d'observation en termes de
réflectance neutre (ordre de grandeur 20 % / 60 % selon le régime), ce qui n'est
pas la même affirmation. Le point est logé dans un `[À TRANCHER]`, donc le coût
aval est faible — mais une norme citée par son numéro se relit comme un fait.

**Recommandation — vérifier ou retirer le numéro de norme**, en gardant
l'alternative « neutre sombre de suite d'étalonnage vs gris moyen ».

---

## 3. Déformations

### D-01 — « ses valeurs ne sont pas reprises » — la moitié le sont, verbatim *(moyen)*

| `DESIGN.md` | Le prototype (`gui-prototype/index.html`) |
|---|---|
| « La maquette porte les bonnes structures ; **ses valeurs ne sont pas reprises**. Les neutres de cette spine les remplacent un pour un. » *(Brand & Style)* | l. 50-51 : `--accent:#4c7ef3` · `--accent2:#3a63c4` · `--green:#3fbf6f` · `--red:#e5484d` · `--amber:#f5a623` — soit **exactement** `accent`, `accent-pressed`, `state-complete`, `state-absent`, `state-substitute` de la spine |
| `spacing.bin-width: 250px` · `side-panel-width: 300px` · `tabbar-height: 54px` · `header-height: 44px` · Modale « **460 px** » · `opacity-deselected: 0.32` | l. 125 `.bin{width:250px}` · l. 101 `#sidePanel{width:300px}` · l. 118 `#tabs{height:54px}` · l. 88 `header{height:44px}` · l. 269 `.modal{width:460px}` · l. 181 `opacity:.32` |

**Ce qui cloche.** L'énoncé est faux : seuls les **neutres** ont été remplacés
(dé-teintés : `#e8e8ea`→`#E8E8E8`, `#9a9aa3`→`#9A9A9A`, `#6a6a73`→`#6A6A6A`) ;
les cinq chromies et toutes les dimensions de chrome sont **reprises telles
quelles** d'un fichier que le memlog déclare **périmé**.

C'est une déformation « en mieux » — ces valeurs sont mieux adossées que la
spine ne l'admet — mais elle a deux coûts : un lecteur qui croit ces valeurs
inventées voudra les rejouer, et l'héritage d'un fichier périmé n'est pas tracé.

**Recommandation — sourcer.** Une ligne suffit : « chromies et dimensions de
chrome reprises de la maquette ; seuls les neutres sont remplacés (dé-teintés) ».

### D-02 — « Une story d'Epic 5 la porte » *(élevé)*

| `EXPERIENCE.md`, *D'où viennent les images de l'aperçu* | `.memlog.md`, arbitrage 8 (2026-08-17) |
|---|---|
| « Cette production d'images par la détection n'existe pas encore […]. **Une story d'Epic 5 la porte.** Tant qu'elle n'est pas livrée, le mode lecteur ne peut pas être simulé : voir *Cible non livrée*. » | « Motifs secondaires : […] et **c'est une story au lieu d'une brique générique**. » |

**Ce qui cloche.** L'arbitrage 8 dit que la fonction *sera* une story ; la spine
écrit qu'une story *la porte*, au présent, comme les trois autres lignes de
`Cible non livrée` qui, elles, nomment des stories existantes (5.13 écrite,
5.12/5.14 ready-for-dev). Le renvoi « voir *Cible non livrée* » **pointe vers
une section qui ne la contient pas** (voir D-03). Résultat : la dépendance la
plus structurante du produit — sans elle le second point de jugement n'existe
pas — se lit comme la mieux cadrée des quatre.

**Recommandation — corriger la formulation** (« story à écrire, arbitrage 8 »)
**et l'ajouter à `Cible non livrée`**.

### D-03 — `Cible non livrée` sous-compte : « quatre » pour au moins six *(élevé)*

| `EXPERIENCE.md`, *Cible non livrée* | Ce que le même document renvoie vers elle |
|---|---|
| « **Quatre** comportements décrits dans cette spine ne sont pas dans le produit d'aujourd'hui […] portés par **quatre stories d'Epic 5** » — ingest en vrac · versions multiples · date de scan · cadence source au QR | *Reprise du travail* : « La désignation de ce qui alimente l'encodage vit au manifest […] ***(cible non livrée — arbitrage 2)*** » — **absente de la table** · *D'où viennent les images de l'aperçu* : « voir *Cible non livrée* » — **absente de la table** · *Le chutier — huit rôles*, rôle 8 : « *(cible non livrée)* » · *State Patterns*, plusieurs candidats : « *(cible non livrée)* » |

**Ce qui cloche.** Le memlog énumère les quatre stories d'Epic 5 qui passent
devant l'Epic 7 comme *« tri par QR, désignation au manifest, payload 2.1, date
de scan »* ; la table a **substitué** « versions multiples d'un lot » à
« désignation au manifest ». En ajoutant la production des images d'aperçu, on
est à **six** dépendances, dont deux invisibles dans la seule section censée les
énumérer. C'est précisément la section que le commanditaire lira pour savoir ce
qu'il peut promettre.

**Recommandation — sourcer et compléter** : six lignes, chacune avec son
arbitrage d'origine, et retirer le mot « quatre ».

### D-04 — Le bouton « Détecter » a deux emplacements *(moyen)*

| `EXPERIENCE.md`, *Le chutier — huit rôles*, rôle 4 | `EXPERIENCE.md`, *Component Patterns*, `{components.button-primary}` |
|---|---|
| « Le bouton **Détecter** vit **au chutier**, jamais dans la previz, et **jamais automatiquement** » (repris dans `DESIGN.md` : la zone tampon « porte le bouton **Détecter** ») | « **Droite de la barre de réglages** — Une action principale par atelier : Extract · Générer · **Détecter puis Extraire** · Exporter » |

**Ce qui cloche.** Le memlog est net : « bouton au niveau du CHUTIER (pas dans
la previz) », et la raison est fonctionnelle (on continue à charger des fichiers
pendant la détection). La ligne `button-primary` remet Détecter dans la barre de
réglages, où vit l'action principale d'atelier. L'atelier Scan se retrouve avec
deux actions principales à deux endroits.

**Recommandation — trancher dans le texte** : Détecter au chutier, Extraire à
droite de la barre de réglages, et le dire une seule fois.

### D-05 — « macOS 11+ » là où le memlog dit « si possible » *(faible-moyen)*

| Spines | `.memlog.md` |
|---|---|
| « Instrument de post-production de bureau (**macOS 11+** / Windows) » *(DESIGN, front matter)* · « **macOS 11+ et Windows natifs** » *(EXPERIENCE, Foundation)* | « Prérequis : compatibilité macOS (**min macOS 11 si possible**) et Windows natifs » |

Un prérequis conditionnel devient un contrat de plateforme. Le coût est réel :
c'est le genre de ligne qui décide d'un toolkit.

**Recommandation — restaurer la condition** (« cible macOS 11, à confirmer avec
la technologie »).

### D-06 — « huit rôles […] recensés en fin de parcours » *(faible)*

Le parcours v2.1 en recense **six** (source, état d'avancement, lieu de la
détection, espace d'organisation, code couleur, lieu des versions). Les deux
autres (arborescence inversée, zone tampon) sont bien décidés au memlog, mais
pas « en fin de parcours ». Chaque rôle pris isolément est adossé ; c'est
l'attribution du recensement qui est fausse.

### D-07 — Compteurs de vérification faux dans le front matter *(faible)*

> « `.memlog.md` (**118 entrées**) » — `EXPERIENCE.md`, front matter.
> Le fichier en compte **129**.

Même famille : le memlog s'auto-enregistre à « DESIGN.md distillé (339 lignes) »
et « EXPERIENCE.md distillé (508 lignes) » pour des fichiers de **345** et
**545** lignes. Sans conséquence aval, mais ce sont les seuls chiffres du
document qui servent à vérifier qu'on a tout lu.

### D-08 — Nom de constante `ENCODE_REFUSAL_CODES` *(faible)*

`EXPERIENCE.md` (*State Patterns*, « Refus d'encodage ») affiche le motif
« verbatim depuis `ENCODE_REFUSAL_CODES` ». Côté previz, la constante s'appelle
`ENCODE_PREVIZ_REFUSAL_CODES` (import §6), et la contrainte transverse 7 impose
justement des **noms de constantes distincts, sans homonymie**. Dans un document
qui pose comme règle « les codes du cœur s'affichent verbatim », se tromper de
nom de constante n'est pas neutre.

---

## 4. Périmées

### P-01 — L'accessibilité du délinké rouvre ce que l'arbitrage 10 a tranché *(élevé)*

> « **[À TRANCHER]** : au niveau d'une **ligne de chutier**, l'arbitrage
> "pas de badge, le code couleur suffit" laisse l'état délinké porté par la
> **seule couleur**. C'est un arbitrage produit assumé, pas un oubli — mais il
> n'a **pas de compensation décidée** (mention textuelle sur la ligne,
> inspecteur, réglage de daltonisme). »
> — `EXPERIENCE.md`, *Accessibility Floor*

**Ce qui l'a défait.** L'arbitrage 10 du 2026-08-17 : *« l'état d'une ligne de
chutier porte une MARQUE DISCRÈTE DE FORME en plus de la couleur […]. Cet
arbitrage NUANCE l'arbitrage E ("pas de badge, le code couleur suffit"), qui
portait contre un BADGE TEXTUEL d'origine de projet — pas contre une redondance
non chromatique. »* La compensation **est** décidée, elle est nommée, et le
**même document l'applique deux paragraphes plus bas** (*La couleur ne porte
jamais seule*), comme `DESIGN.md` sur `bin-row` (« doublé de la **forme** de
`{components.badge-state}` »).

Le `[À TRANCHER]` est donc un vestige de la rédaction antérieure aux arbitrages
8-10. Coût : il **rouvre** dans la section accessibilité une question que le
commanditaire a tranchée, et il la rouvre au seul endroit où un développeur ira
la chercher.

**Recommandation — retirer** ce `[À TRANCHER]` et renvoyer à *La couleur ne
porte jamais seule*.

### P-02 — « Rush absent / délinké […] sans badge ni mention » *(moyen)*

> — `EXPERIENCE.md`, *State Patterns*

Formulation antérieure à l'arbitrage 10, incohérente avec `DESIGN.md`
(`foreground-delinked` + forme) et avec la section *La couleur ne porte jamais
seule*. Ce qui reste vrai : pas de **badge textuel**, pas de mention d'origine
de projet. Ce qui ne l'est plus : « la couleur seule ».

**Recommandation — reformuler** : « sans badge textuel ni mention d'origine ;
la couleur est doublée de la forme d'état ».

---

## 5. Déductions acceptables, mais non signalées comme telles

Aucune de ces cinq n'est un défaut de fond ; toutes gagneraient une incise
d'une ligne (« déduit de … »), pour qu'un rédacteur de story sache lesquelles
sont négociables.

1. **La palette de neutres entière** (`#0E0E0E` … `#4A4A4A`, `#E8E8E8` /
   `#9A9A9A` / `#6A6A6A`, `image-mat #2B2B2B`). Déduction **exemplaire** : la
   contrainte est nommée (« l'utilisatrice juge des couleurs dans cette
   interface », R = G = B), la conséquence est explicite, et la valeur la plus
   discutable — la clarté du mat — est la seule marquée `[À TRANCHER]`. C'est
   le modèle à suivre ; il manque seulement de dire que les **paliers** eux-mêmes
   (cinq niveaux, ces écarts-là) sont un choix et non une conséquence.
2. **L'échelle de 4 px, les trois rayons, l'échelle typographique**
   (28/15/13/11 + mono 16/12/11) : conventions d'outil dense, non sourcées, et
   le `[À TRANCHER]` sur la rampe typographique système en couvre déjà une
   partie.
3. **L'accessibilité clavier** (cf. I-05).
4. **« pas de compte, pas de réseau, pas de synchronisation »** (cf. I-08).
5. **L'emplacement système des Préférences** (cf. I-06).

À signaler à l'inverse comme **bien fait** : la spine nomme sa déduction là où
elle compte le plus — « une activité **n'est pas un verdict** : c'est pourquoi
elle porte l'accent et non le vert », « un coin arrondi **rogne la frame** »,
« l'accent ne pénètre jamais le mat ». Ce sont des déductions, elles sont
présentées comme telles, avec leur prémisse.

---

## 6. `[À TRANCHER]` manquants

C'est la section la plus coûteuse de cette revue : **un point non tranché
présenté comme tranché**.

### M-01 — Aucune surface d'affichage des avertissements *(critique)*

Une vingtaine de codes fermes existent au contrat, avec **interdiction
contractuelle de les fondre et de les traduire** : `SCAN_PREVIZ_WARNING_CODES`
(10 codes), `PDF_PREVIZ_WARNING_CODES` (3), les 5 codes dégradés de vignettes,
`ENCODE_PREVIZ_WARNING_CODES`, et quatre familles séparées côté scan
(`ingest` / `detection` / `output` / `previz`).

Les spines n'en surfacent que **deux** : `GAMUT_CLIPPING_DETECTED` (*State
Patterns*) et le motif de refus d'encodage. `GEOMETRY_DEGRADED` — *« le
prédicteur du QR illisible de P3, disponible trois semaines avant que Camille
rapporte ses planches peintes »* — et `DPI_BELOW_QR_MINIMUM` — le cas de terrain
le plus probable de P4, celui qui évite d'envoyer réparer à la main des
centaines de pages qu'il fallait renumériser — n'apparaissent **nulle part**.

Le memlog l'enregistre mot pour mot : *« Deuxième trou : une vingtaine de CODES
D'AVERTISSEMENT fermés […] n'ont AUCUNE surface d'affichage décidée, avec
interdiction contractuelle de les fusionner. »* La réconciliation le classe
E05, « à réintégrer ».

**Il n'y a pas un seul `[À TRANCHER]` là-dessus dans les deux spines.**
Conséquence aval mécanique : sans lieu où les poser, soit les codes
disparaissent, soit une story les fondra en un indicateur unique — la faute que
la contrainte 8 interdit et que P3 interdit déjà pour son propre compte.

**Recommandation — `[À TRANCHER]` explicite**, avec la contrainte de
non-fusion citée.

### M-02 — Rien ne dit qu'un aperçu est périmé *(critique)*

Zéro occurrence de « péremption », « périmé » (au sens d'un aperçu) ou
« empreinte » dans les deux spines, alors que :

* les quatre contrats transportent `generated_at_utc`, `rounding_policy` et des
  empreintes `sha256-v1:` **pour ça** — avec la note du contrat 5.8 que sans
  `gamut_map_id` *« une previz périmée devient indétectable — l'angle mort
  trouvé côté impression »* ;
* `EXPERIENCE.md` **invente une section entière** — *Points de jugement avant
  écriture* — dont le principe est « ne jamais laisser fabriquer quelque chose
  qu'on n'a pas d'abord regardé » ;
* le memlog enregistre le trou : *« rien ne permet de dire qu'un aperçu est
  PÉRIMÉ — alors que toute la conception repose sur "regarder avant d'écrire" »*.

Juger sur un aperçu périmé en croyant qu'il est frais est **exactement** le
piège que ces empreintes existent pour fermer, et c'est le seul mode d'échec qui
défait silencieusement les deux points de jugement.

**Recommandation — `[À TRANCHER]`** dans *Points de jugement avant écriture* :
comment l'interface dit qu'un aperçu ne correspond plus aux réglages.

### M-03 — D'où viennent les vignettes de la galerie d'**Extraction** ? *(élevé)*

L'arbitrage 8 ferme le trou **du côté scan** (« la détection produit les images
d'aperçu »), et `EXPERIENCE.md` le documente bien. Mais la galerie d'Extraction
— P1 étape 4, cent images, avec un zoom continu et un toggle de frames
supprimées — **n'a aucune source d'images nommée**. Le contrat amont mesure
pourtant le régime : *« une grille de 200 vignettes coûte 20 secondes si elle lit
les TIFF du lot, et 40 millisecondes si elle lit un cache de vignettes — un
facteur 500 »*, et le vocabulaire de vignettes de 3.5
(`absent` / `exact` / `approximate`, avec l'interdit « une vignette approximative
n'est jamais présentée comme exacte ») existe déjà pour ça.

« cache », « miniature » et le vocabulaire de vignettes : **0 occurrence** dans
les deux spines. La décision déléguée n°10 reste classée « Non — aucune trace,
l'élément le plus coûteux à ne pas réintégrer ».

**Recommandation — `[À TRANCHER]`**, symétrique de *D'où viennent les images de
l'aperçu*, côté Extraction.

### M-04 — Rasteriser le PDF réel ou dessiner le plan *(élevé)*

Voir I-02. **`[À TRANCHER]`.**

### M-05 — La calibration couleur contredit une décision fermée du plan d'implémentation *(élevé)*

`EXPERIENCE.md` décrit une bascule de calibration qui « change de profil à la
volée ; le rendu change à l'écran sans rien écrire », et P1/P3 en font un geste
de jugement répété. `IMPLEMENTATION_PLAN.md` porte une **décision fermée**
inverse : *« couleur MVP : **pas de correction appliquée** dans cette
itération »* — signalée X1 par la réconciliation, avec la conclusion : *« L'interface
conçue applique une correction couleur que le plan d'implémentation exclut du
MVP »*.

Le memlog est postérieur, donc il gagne au sens de la règle d'autorité. Mais
l'écart n'est **ni signalé, ni porté en `Cible non livrée`**, alors qu'il est de
la même nature exacte que les quatre qui y figurent : un comportement décrit
que le produit d'aujourd'hui ne fait pas.

**Recommandation — porter en `Cible non livrée`** ou marquer `[À TRANCHER]`
(« la correction couleur appliquée sort du périmètre MVP fermé »).

### M-06 — Quatre orphelines sur six sans question posée *(moyen)*

Le memlog exige que chaque surface orpheline soit *« soit à exercer par un
parcours, soit à écarter sciemment »*. La table *Fermeture de l'architecture
d'information* pose la question sur **deux** (marqueurs, re-scan partiel) et la
laisse en suspens sur quatre : **base de timecode au clic droit**, **file
d'exports réordonnable**, **dossiers d'organisation du chutier**, **Préférences**.
Écrire « Décidée, exercée par aucun parcours » sans question, c'est les garder
en v1 par défaut — ce qui est une décision, non prise.

**Recommandation — `[À TRANCHER]` sur les quatre**, au même format que les deux
autres.

### M-07 — Qui fournit le discriminant de passe ? *(moyen-élevé)*

Le `[À TRANCHER]` existe (*Composition d'un lot à partir de candidats* :
« rien ne dit si l'interface montre ce numéro, le masque derrière la date, ou le
demande »), et il est bien posé. Mais le **Flow 5 pose comme acquis deux
mécanismes incompatibles**, à une étape d'intervalle :

> 4. « […] l'outil ne sait pas encore que c'est un second tirage. **C'est la
>    détection qui le rattache au même lot.** »
> 5. « **Au dépôt**, l'interface **propose de garder une nouvelle version** […] »

Si c'est la détection qui rattache, l'interface ne peut rien proposer au dépôt.
Et la story 5.14 démontre que le QR est **identique d'un tirage à l'autre**, donc
que le discriminant *ne peut pas* être dérivé : la réconciliation classe ce
conflit X4 comme *« le conflit le plus dur des deux rapports »*. Le memlog l'a
d'ailleurs corrigé une fois (« la détection rattache au LOT mais ne peut pas
déduire la PASSE ») — la correction est arrivée dans la phrase de l'étape 4,
pas dans l'enchaînement 4→5.

**Recommandation — remonter le `[À TRANCHER]` dans le Flow 5**, ou réécrire
l'étape 5 pour dire qui saisit quoi et quand.

---

## 7. Ce qui est solidement adossé

Le commanditaire peut faire confiance sans relire sur les points suivants —
chacun a été confronté à sa source.

* **Les dix arbitrages, tous dans leur version tardive.** Vérifié un par un :
  ingest en vrac = story d'Epic 5 amont (1) · désignation au manifest (2) ·
  cadence source au QR **avec** la correction de la relecture v2 — « le lecteur
  bi-format est un **confort de développement**, en production 2.0 est abandonné
  et la rupture est assumée » (3, corrigé) · pointage plutôt que lecture
  automatique, avec le report en `deferred-work.md` et son motif (4) · date de
  scan au manifest **voulue**, arbitrage d'origine explicitement défait (5) ·
  tutoriel hors v1, exigence de facilité maintenue (6) · nommage du lot composé
  numéro **et** date (7/9) · la détection produit les images d'aperçu (8) ·
  redondance non chromatique qui **nuance** « pas de badge » sans le défaire
  (10). **Aucune décision périmée reprise comme actuelle** — hors les deux
  vestiges P-01/P-02, qui portent sur le seul arbitrage 10.
* **L'architecture d'information complète** : quatre ateliers en onglets bas,
  écran de projet à chaque lancement avec dernier projet en tête, panneau ancré
  à droite, chutier commun à deux périmètres, arborescence inversée côté scan,
  section Calibration, zone tampon, chrome à largeurs constantes, tâches en
  arrière-plan, clic sur un lot d'Extraction qui ouvre Pdf. Tout est au memlog.
* **Le scan en deux temps** (détection depuis le chutier, jamais automatique,
  puis extraction TIFF), le **mode lecteur** comme troisième mode, la **zone
  tampon** et son rôle de reliquat visible, l'**édition des quatre coins
  accessible en permanence**, le « **rien à relancer** » après ajustement
  manuel : intégralement adossés au memlog et aux deux relectures, y compris
  dans leurs nuances (relecture v2, notes 2, 3, 4).
* **Le lot hybride** : invariant de complétude comme garde centrale, granularité
  à la frame **avec** le choix en bloc comme raccourci défaisable (et non
  l'inverse — relecture v2 note 5), comparaison **côte à côte** des candidats
  d'une frame vs **successive au même timecode** pour deux passes entières,
  « trancher ne supprime rien », « un lot ne change pas d'identité en étant
  composé ».
* **Les trois sémantiques et les deux natures de manque** : rouge « il n'y a
  rien ici », ambre « il y a quelque chose mais ce n'est pas ton image », vert
  « fini/complet » ; l'interdit de fusion ; le comptage séparé ; « un lot à mires
  n'est pas complet ». Acquis de conception de P3, cité comme tel.
* **Les cinq Key Flows.** Sondés au hasard sur une vingtaine de détails
  chiffrés ou nommés — espace disque annoncé à la confirmation, marge de travail
  à 0 par défaut, 6 frames/page et A4, le mini-dialogue de calibration qui ne
  demande que le nom du scanner, les 600 dpi du prestataire, 16 bits non
  discutés, la cadence cible sélectionnée par défaut à l'export, le wipe
  inspectable image par image, le coup de téléphone supprimé, la variante
  « projet vide » de P2 — **tous** remontent au parcours v2.1, souvent mot pour
  mot. C'est la partie la plus fidèle des deux documents.
* **L'invariant colorimétrique et sa justification** : « les neutres sont
  strictement R = G = B **parce que** l'utilisatrice juge des couleurs dans
  l'interface ». Contrainte métier nommée, conséquence explicite, valeur
  discutable isolée en `[À TRANCHER]`. C'est le modèle d'une déduction bien
  faite.
* **La microcopie** : « Ce lot a 2 tirages » contre « Dernière version », faux
  tant que la date n'est pas au manifest ; le refus de proposer de compléter ce
  qui est structurellement absent ; « un champ vide appelle la vérification, un
  champ faux ne l'appelle pas ». Tous adossés, au mot près.
* **Les `[À TRANCHER]` posés le sont à bon droit** — les douze existants portent
  tous sur un point réellement ouvert (mat, thème clair, rampe typographique,
  reflux du panneau, taille minimale de fenêtre, iconographie, icône vs mot,
  apparence de la mire, Préférences, zoom, annulation, lecteur d'écran, previz
  pendant un export). Le défaut n'est pas qu'il y en ait de faux ; c'est qu'il
  en manque sept.
