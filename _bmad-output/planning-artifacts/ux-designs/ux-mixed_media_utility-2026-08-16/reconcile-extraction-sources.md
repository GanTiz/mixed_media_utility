# Réconciliation d'entrée — `imports/extraction-sources-epic7.md`

> **Objet.** Chasse aux écarts entre l'extraction des sources amont (259 lignes,
> commit `1275f97` du 2026-08-16 : contrats de previz 3.5 / 4.9 / 5.8 / 6.4,
> décisions déléguées par les stories des Epics 3 à 6, prérequis de cache,
> brief produit) et l'aval de la session UX : le memlog (122 entrées), les
> parcours utilisateurs v2.1 et la découverte.
>
> Cet input est la **seule voie** par laquelle les contrats déjà écrits et
> livrés atteignent la conception de l'interface. Ce qui n'en est pas ressorti
> n'a aucune chance d'être retrouvé par une relecture des parcours : ce sont des
> obligations de contrat, pas des idées d'interface.
>
> **Bilan : 40 éléments perdus, 6 contradictions, 5 zones périmées. Sur les 15
> décisions explicitement déléguées à l'Epic 7 par les stories amont, 6 sont
> pleinement arrivées, 3 partiellement, et 6 ne se retrouvent nulle part.**

---

## 1. Ce que l'input apporte et qui est bien arrivé

* Les quatre commandes métier `extract → makepdf → scan → encode` comme
  découpage de l'interface (les quatre ateliers).
* Le principe « donner à voir avant de produire », qui est devenu les points de
  jugement avant écriture de P1.
* Reprise depuis les scans seuls, sans le rush et sans le projet d'origine
  (brief §9, scénario clé) — c'est P2.
* Manifest autoportant, information transmise **dans les fichiers eux-mêmes** —
  renforcé en aval par les arbitrages 2 et 5 (désignation et date au manifest).
* Payload QR **non opaque** — c'est ce qui rend praticable la complétion
  manuelle d'un QR illisible de P3.
* Encode sans rush source autorisé — climax de P2.
* Un encode par lot, pas de concaténation ; refus d'encoder un lot d'extraction
  (`lot_state` en dessous de `scan`) — memlog 64.
* Les **deux états du contrat de previz Scan**, `detected` / `reconstructed` :
  belle convergence, l'aval y est arrivé indépendamment le 2026-08-17 en
  scindant l'atelier Scan en détection puis extraction (memlog 97). À citer
  comme telle dans les stories : le contrat 5.8 portait déjà les deux temps.
* « Montre-moi les trous » : les frames de remplacement (mires) sont arrivées
  et ont même été affinées (memlog 86 : deux natures de manque, deux comptages).
* Édition manuelle des détections rendue possible par le contrat, appliquée par
  l'Epic 7 — c'est P3.
* Choix / comparaison / sélection entre versions d'un même lot — arrivé et
  dépassé par la composition d'un lot hybride (memlog 110).

---

## 2. Ce qui a été perdu en route

Quarante éléments, groupés par origine. Pour chacun : ce que l'input porte,
où, et pourquoi rien en aval ne le reprend.

### 2.1 Le cache de prévisualisation — le trou le plus large

**E01 — Le cache de prévisualisation, « prérequis de la GUI ».**
*Input :* section 8 entière (l. 169-190) et contrainte transverse 3 (l. 248).
Chiffres mesurés : 99 ms par frame en lisant les TIFF du lot contre 0,2 ms par
vignette JPEG — *« une grille de 200 vignettes coûte 20 secondes contre 40
millisecondes, un facteur 500 »* ; *« dès qu'une GUI affiche plus d'une dizaine
de frames, il devient obligatoire »* ; *« le meilleur rapport valeur/coût de
tout ce document »*. Deux résolutions distinctes (vignette ~320 px pour la
grille et la navigation, preview ~1280 px pour le contrôle visuel d'une frame),
quatre invariants de sûreté (nommage distinct de `build_extracted_frame_filename`
sous peine de rendre `verify_extracted_lot` faux ; format lossy assumé **hors
de** `frames/` ; dérivable, jetable, invalidable ; péremption adossée à
`lots[].frame_timecodes_digest`), une troisième valeur d'origine
`preview_cache` à ajouter à une énumération fermée, et un arbitrage recommandé :
*« niveau 0 systématique et non optionnel puisqu'il conditionne la GUI »*.
*Aval :* **zéro occurrence.** Ni « cache », ni « vignette » au sens d'un
artefact, ni aucune mention de coût d'affichage, dans les 122 entrées du memlog
ni dans les 633 lignes de parcours. Or les parcours reposent sur des galeries de
cinquante à plusieurs centaines de frames (P1, P3, P5), et la conclusion du
document désigne le chutier et ses galeries comme la pièce la plus sollicitée.
La conception d'interface la plus soignée s'écroule à l'usage si chaque grille
coûte vingt secondes.

**E02 — Le vocabulaire de vignettes.**
*Input :* §3, l. 53-56. `state ∈ {absent, exact, approximate}`,
`origin ∈ {null, rush_decode, extracted_frame}`, `decoded_source_index`
renseigné **uniquement** si `approximate` ; *« un document sans aucune vignette
est valide et complet — c'est le cas par défaut »* ; *« une vignette
approximative n'est jamais présentée comme exacte »* (refus à la construction).
*Aval :* rien. La galerie d'extraction de P1 est décrite comme si les images
étaient toujours là et toujours justes. Le cas nominal du contrat est pourtant
**aucune vignette**, et le cas dégradé est une vignette qui n'est pas la bonne
image (seek approximatif). C'est mot pour mot la doctrine que la session a
tirée de l'incident de la relecture perdue (memlog 116 : *ne rien affirmer
qu'on n'ait vérifié*), appliquée aux pixels.

**E03 — Les cinq codes dégradés de vignettes.**
*Input :* §3, l. 57. `THUMBNAILS_UNAVAILABLE_NO_FFMPEG`,
`THUMBNAILS_PARTIAL_BUDGET`, `THUMBNAIL_DECODE_FAILED`,
`THUMBNAILS_APPROXIMATE_SEEK`, `SOURCE_UNREADABLE`.
*Aval :* rien. Aucun parcours ne rencontre une galerie qui ne peut pas
s'afficher — et le premier code décrit exactement une machine sans ffmpeg,
c'est-à-dire une installation neuve.

**E17 — La « qualité temporaire » du mode lecteur n'a aucun support.**
*Input :* §5, l. 112 : côté scan, *« aucun mécanisme de vignette : la page
scannée existe déjà sur disque — chemins relatifs seulement, la GUI ouvre le
fichier »* ; et §8, l. 189 : le cache *« n'alimente jamais le chemin scan »*.
*Aval :* memlog 97 crée un **mode lecteur** qui relit un lot reconstruit à sa
cadence cible *« en qualité temporaire »*. Cette qualité temporaire n'existe
nulle part comme artefact : le chemin scan n'a ni vignette, ni preview, ni
cache, et lire des TIFF 16 bits à 12,5 images par seconde est hors d'atteinte
(99 ms par frame mesurés). **Le mode lecteur, qui est devenu le second point de
jugement avant écriture de P1 et la conclusion de P3, n'a pas de source
d'images.** C'est le trou de conception le plus coûteux des deux rapports.

### 2.2 La péremption et les avertissements — deux surfaces entières manquantes

**E04 — Détection de péremption d'un aperçu.**
*Input :* §3 l. 47 (`generated_at_utc`, `rounding_policy`, trois empreintes
`sha256-v1:` : `fingerprints.selection`, `.source_report`, `.source_signature`),
§4 l. 88, §5 l. 110 (`DETECTION_FINGERPRINT_FIELDS`, avec la note que sans
`gamut_map_id` *« une previz périmée devient indétectable — l'angle mort trouvé
côté impression »*), §6 l. 141, contrainte 6 l. 251.
*Aval :* rien. Toute la conception aval repose sur « regarder avant d'écrire » —
et un aperçu périmé qu'on regarde en croyant qu'il est frais est exactement le
piège que ces empreintes existent pour fermer. L'interface n'a aucune façon de
dire « ce que tu regardes ne correspond plus aux réglages ».

**E05 — Où s'affichent les avertissements.**
*Input :* §3 l. 57 (familles `selection` / `confirmation` / `previz`), §4 l. 87
(3 codes), §5 l. 109 (**10 codes**, familles `ingest` / `detection` / `output` /
`previz`), §6 l. 140 (un seul seau `warnings.encode`, vocabulaire
**francophone**), contraintes 7 et 8 (l. 252-253) : vocabulaires fermes,
**noms de constantes distincts, pas d'homonymie**, familles **jamais fusionnées
ni traduites**.
*Aval :* **aucune surface d'avertissement n'existe dans la conception.** Les
parcours affichent des codes couleur, des cartes de tâche et des badges, jamais
un avertissement nommé. Or les contrats en produisent une vingtaine, avec
l'obligation explicite de ne pas les fondre. Sans lieu où les poser, soit ils
disparaissent, soit ils seront fusionnés en un indicateur unique — la faute que
la contrainte 8 interdit et que P3 interdit déjà pour son propre compte
(« deux natures de manque, deux comptages »).

### 2.3 Ce que la planche devrait dire avant d'être imprimée (contrat 4.9)

**E06 — `GEOMETRY_DEGRADED`.**
*Input :* §4, l. 82 et 87 : le QR porte un classement `check_print_geometry`
(`reliable` / `degraded`…), transporté verbatim, et un avertissement se lève
quand il est `degraded`.
*Aval :* rien. C'est pourtant **le prédicteur du QR illisible de P3** —
disponible au moment de la génération, c'est-à-dire **trois semaines avant** que
Camille rapporte ses planches peintes. Une planche imprimée avec une géométrie
dégradée est un aller simple vers la réparation manuelle.

**E07 — `OVER_NOMINAL_BUDGET`.** *Input :* §4, l. 87 (page au-delà du budget
nominal, sous le plafond). *Aval :* rien.

**E08 — `image_rect_mm` et `letterbox_policy`.**
*Input :* §4, l. 80, avec le motif inscrit dans le contrat : *« projetés après
revue — l'aperçu ne ment plus »*.
*Aval :* rien. memlog 46 renvoie les ratios non 16:9 aux versions ultérieures,
ce qui **écarte le cas** mais pas l'exigence : l'aperçu vivant de P1 est un
point de jugement, il doit poser l'image exactement là où le PDF la posera.

**E09 — `slot_labels`, la redondance de secours.**
*Input :* §4, l. 84 : correspondance slot → timecode, doublée des `text_blocks`.
*Aval :* rien. C'est le filet quand un bloc de texte manque à l'impression.

**E10 — `text_blocks` : `role` et `content`, les lignes exactes imprimées.**
*Input :* §4, l. 84.
*Aval :* le raccord n'est **jamais fait** avec P3, qui repose entièrement
dessus : quand l'interface « pointe sur le scan l'endroit où chaque information
est imprimée » (arbitrage 4), les zones qu'elle pointe **sont** les
`text_blocks` du contrat 4.9, avec leurs positions en millimètres. Ce lien est
ce qui rend l'arbitrage 4 implémentable sans reconnaissance de caractères ; il
n'est écrit nulle part.

### 2.4 Ce que le scan sait et que personne n'affiche (contrat 5.8)

**E11 — Rang de lecture d'ingestion **et** `page_index` décodé.**
*Input :* §5, l. 106 : *« jamais l'un déduit de l'autre — une interface doit
pouvoir montrer "le 3e fichier du dossier déclare être la page 1", diagnostic
du lot mélangé »*.
*Aval :* rien — alors que **P4 est précisément le parcours du lot mélangé** :
des centaines de pages en vrac, plusieurs lots, parfois plusieurs projets. La
zone tampon range par QR ; rien n'affiche le désaccord entre l'ordre des
fichiers et l'ordre déclaré, qui est le seul diagnostic disponible quand le
rangement tourne mal.

**E12 — Marqueurs étrangers et leur rôle (`FOREIGN_MARKER_DETECTED`).**
*Input :* §5, l. 106 et 109.
*Aval :* rien. Cas réel sur un support où l'artiste colle et découpe : un
marqueur d'une autre planche entre dans le champ.

**E13 — Échelle observée et résidu de reprojection
(`PAGE_SCALE_OUT_OF_TOLERANCE`, `PAGE_ASPECT_OUT_OF_TOLERANCE`).**
*Input :* §5, l. 106 et 109.
*Aval :* rien. C'est le chiffre qui dit si la géométrie tient — une page pliée
(P3) ou numérisée à une échelle différente produit des cadrages faux **sans
rien signaler** si ce résidu n'est pas montré. *(La maquette l'affichait :
voir `reconcile-gui-prototype.md`, G22.)*

**E14 — `DPI_BELOW_QR_MINIMUM`.**
*Input :* §5, l. 109.
*Aval :* rien. Cas de terrain le plus probable de tout P4 : le prestataire
numérise à 300 dpi au lieu de 600, **toutes** les pages ressortent avec un QR
illisible, et sans cet avertissement l'interface envoie Camille réparer
manuellement des centaines de pages au lieu de lui dire de faire renumériser.

**E15 — `GAMUT_CLIPPING_DETECTED` et le verdict d'écrêtage conditionnel.**
*Input :* §5, l. 106 et 109, avec la règle : le verdict est **omis** si la
calibration n'a pas tourné, et *« jamais remplacé par un verdict "pas
d'écrêtage" »* ; le code existe parce que *« un écrêtage doit être **vu** par
l'opérateur »*.
*Aval :* rien. En P3, Camille trouve une image « trop froide » et change de
profil au jugé ; l'outil sait dire qu'il y a écrêtage et ne le dit pas.

**E16 — Les compteurs de lot.**
*Input :* §5, l. 108 : pages présentes/attendues, frames écrites/attendues,
`synthetic_frame_count`, avec la formule du contrat — *« un lot se lit d'abord
par ses compteurs »*.
*Aval :* le code couleur de complétude est arrivé (memlog 97), les mires aussi
(memlog 86), et P3 exige deux comptages distincts — mais **aucune surface ne
porte de compteur**. Le code couleur seul dit « complet / pas complet » ; il ne
dit ni combien, ni de quelle nature.

**E39 — L'adressage stable comme vocabulaire de la story 7.4.**
*Input :* §5, l. 99-103 : *« le document donne à chaque élément modifiable une
adresse stable et explicite (au minimum `page_index` + `slot_index`, et pour un
marqueur son ID) »* ; *« c'est ce qui distingue cette previz de ses deux
jumelles »* ; la story 7.4 doit pouvoir dire « la zone 2 de la page 3 est mal
placée, voici le rectangle corrigé ». Rectangles fournis en **millimètres et en
pixels de page redressée**.
*Aval :* le **geste** est arrivé (P3 : quatre poignées, mode loupe, memlog 120 :
accessible en permanence). Le **vocabulaire d'adressage**, non — et c'est
exactement ce qu'une story 7.4 doit écrire pour que l'édition soit exprimable
et rejouable.

### 2.5 Ce que l'encodage sait et que personne n'affiche (contrat 6.4)

**E18 — `lot_state` et le motif du refus.** *Input :* §6, l. 126 (6.1 refuse en
dessous de `scan`). *Aval :* memlog 64 tranche bien qu'on n'encode pas un lot
d'extraction, mais rien ne dit **comment l'interface l'explique** quand
l'utilisatrice essaie.

**E19 — La fiabilité du timecode par profil.**
*Input :* §6, l. 133 : `reliable` sur `prores_hq`, `prores_422`, `prores_lt`,
`dnxhr_hq`, `dnxhr_hqx` ; `best_effort` sur `h264_delivery`, `hevc_delivery`.
*Aval :* rien. Tout le produit existe pour préserver des timecodes à travers le
papier ; le réglage qui les dégrade se prend sans avertissement.

**E20 — L'origine de la résolution retenue.** *Input :* §6, l. 130 :
`origin ∈ {defaut, registre, native, personnalisee}`, résolution retenue =
`size or source_size`. *Aval :* rien — alors qu'en P2 la résolution source est
structurellement absente du projet reconstruit, et que le parcours prend soin de
dire que ce n'est pas un manque à combler.

**E21 — `missing_pages` : des index de page, jamais des timecodes.**
*Input :* §6, l. 135 (souligné dans le contrat).
*Aval :* la galerie de P3 range **par timecode** et affiche des frames rouges.
Le verdict de complétude, lui, ne parle qu'en index de page. Les deux langues
coexistent sans passerelle décidée — et c'est le libellé qu'on lira au moment
de décider si on encode.

**E22 — L'estimation de taille est un majorant.**
*Input :* §6, l. 138 : `estimated_bytes`, *« majoration jamais optimiste »*,
constatation hors empreinte ; `encoded_bytes` est le seul champ qui distingue
`encoded` de `planned`.
*Aval :* memlog 66 affiche « la taille estimée » — sans sa nature. Un chiffre
affiché sans dire qu'il majore se lit comme une mesure.

**E23 — Les huit refus survenant après construction du plan.**
*Input :* §6, l. 146 (décision déléguée 12) : `MASTER_DEJA_PRESENT`,
`VERIFICATION_TECHNIQUE_EN_ECHEC`, `INTERRUPTION_CLAVIER`, `ARRET_DEMANDE`,
`DESTINATION_NON_INSCRIPTIBLE`, `MASTER_EST_UN_REPERTOIRE`,
`DOSSIER_DE_SORTIE_EST_UN_FICHIER`, `RESOLUTION_INCONNUE` — montrer « voici ce
qui aurait été produit, et voici pourquoi ça ne l'a pas été ».
*Aval :* rien. **À noter :** l'entrée existe au `deferred-work.md` du dépôt
(l. 2259 et suivantes, revue de 6.4 du 2026-08-11) avec la mention *« à rouvrir
avec la story d'interface qui affiche un encodage refusé »*. Cette session UX
**est** ce moment, et elle est passée à côté.

**E24 — La vérification technique du master.** *Input :* §6, l. 147 (décision
13, `EncodeCommandResult.verification`, non projeté). *Aval :* rien. Même
remarque : `deferred-work.md` dit *« le jour où l'interface doit montrer la
vérification technique du master… »*.

**E25 — `overwrite` est un consentement, jamais un paramètre.**
*Input :* §6, l. 148 et contrainte 2 (l. 247), verrouillé par des tests : les
mots `overwrite` / `yes` / `confirmed` / `granted` sont **interdits** du JSON
canonique.
*Aval :* rien. Aucun parcours ne rencontre un master déjà présent. *(La maquette
posait la question, mais sous la forme d'une case de réglage que cette règle
interdit — voir `reconcile-gui-prototype.md`, C7.)*

**E40 — Un document par encodage prévisualisé, jamais multi-profils.**
*Input :* §6, l. 124 (sinon empreinte ambiguë).
*Aval :* memlog 67/70 conçoit une **file d'attente** d'exports que l'on
paramètre pendant qu'un encodage tourne. La conséquence — chaque entrée de file
porte son propre aperçu, sa propre empreinte, et la previz bloquée ne peut donc
pas être « la » previz — n'est pas tirée.

### 2.6 Versions, tirages et rattachement (stories 5.12 / 5.14)

**E26 — `source_lot_id`, seule voie de rattachement.**
*Input :* §7.1, l. 154 : chaque lot scanné déclare le lot d'extraction dont il
dérive ; *« sans ce lien, rien ne permet de savoir que deux tirages sont deux
versions du **même** contenu, et l'interface ne peut pas offrir le choix qui
motive la story »* (AC 5). Et c'est la **seule** voie : le suffixe
`-<condensat8>` est déjà occupé par le condensat de bornes de 3.7, *« aucune
analyse du nom ne peut distinguer les deux natures »*.
*Aval :* rien. Or c'est le **socle technique du lot hybride** (memlog 110) et de
l'arbitrage 2 (désignation au manifest) : sans `source_lot_id`, il n'y a pas de
notion de « candidats pour la même frame ». La story d'Epic 5 que l'arbitrage 2
appelle doit s'appuyer dessus, et personne ne le lui a dit.

**E27 — Le discriminant de version est **donné par l'opérateur**.**
*Input :* §7.2, l. 160-161 : quand on scanne deux fois **la même planche**
annotée différemment, *« le QR est identique d'une passe à l'autre : le
discriminant **ne peut pas être dérivé**, il est donné par l'opérateur »* —
un numéro de 1 à 99 (`--version <n>`, `EPIC5-ARB-59`), composé sur deux
chiffres zéro de tête compris pour que le tri lexicographique regroupe les
passes d'un même tirage.
*Aval :* P5 étape 5 suppose l'inverse — *« c'est la détection qui le rattachera
au même lot »*. Voir la contradiction **X4** en section 3 : ce n'est pas un
oubli, c'est une impossibilité démontrée en amont et contournée en aval.

**E28 — `EPIC5-ARB-57` : compléter avec un avertissement, jamais refuser.**
*Input :* §7.2, l. 162 : une version déjà présente sur le même tirage
**complète le lot avec un avertissement**, motif consigné — sinon *« l'opérateur
rescannerait une page refusée pour dérive et relancerait `scan` »*.
*Aval :* P5 étape 7 demande « ne pas refuser, proposer de garder une nouvelle
version, écrasement possible mais jamais forcé ». C'est **compatible mais plus
flou** : l'amont dit exactement quel est le comportement par défaut (compléter),
l'aval dit qu'on propose. La formulation amont est meilleure et se perd.

**E29 — La structure à deux dimensions : *n* tirages × *m* versions.**
*Input :* §7.2, l. 167 : après 5.12 + 5.14, un rush a *n* tirages (impressions
différentes du même lot, par exemple 4 frames/page et 2 frames/page) × *m*
versions (mêmes planches annotées plusieurs fois).
*Aval :* tout est fondu en « deux passes » et « candidats » (memlog 110, P5). La
question que personne n'a posée : **un lot composé peut-il mêler des candidats
issus de tirages différents** — une frame venue d'une planche 4 frames/page et
sa voisine d'une planche 2 frames/page ? P5 étape 5 évoque justement la
réimpression « avec une disposition plus grande ». La réponse change l'invariant
de complétude.

### 2.7 Cadrage, surfaces d'appel et paramètres

**E30 — Modes de sortie `stream` / `keep` / `prune` (axe B).**
*Input :* synthèse par commande, `encode`, l. 221.
*Aval :* rien — un axe entier de comportement (garder ou purger les frames
après encodage) n'est jamais évoqué. Il touche directement l'espace disque, que
P1 étape 7 prend soin d'annoncer à l'extraction.

**E31 — `--lot-slug` au scan.** *Input :* synthèse `scan`, l. 216. *Aval :*
rien. Rien ne dit ce qui nomme un lot reconstruit quand le QR ne le donne pas.

**E32 — « Un lot incomplet se montre en premier ».** *Input :* synthèse
`extract`, l. 205. *Aval :* aucune règle de tri ou de priorité d'affichage
n'existe en aval, alors que le chutier est la pièce la plus chargée.

**E33 — Format maître par défaut : ProRes MOV.** *Input :* §2, l. 33 (décision
fermée de `IMPLEMENTATION_PLAN.md`). *Aval :* memlog 66 expose le profil de
sortie et les presets, sans jamais dire **quel profil est proposé d'emblée**.

**E34 — `--previz` en surface CLI, et l'architecture d'appel laissée ouverte.**
*Input :* décision déléguée 11 (l. 238) et contrainte 10 (l. 255) : *« la GUI
peut être in-process, hors-processus ou distante — le JSON est la forme
normative du contrat de données ; aucune techno d'interface n'est figée nulle
part »* ; exposer `--previz` sur `makepdf` / `scan` appartient à 4.1 / 5.1 ou à
l'Epic 7.
*Aval :* memlog 11 renvoie le choix de **technologie** après l'UX, ce qui est
juste — mais le point amont est différent et plus utile : c'est le contrat JSON
qui **rend** ce report possible, et la question de savoir si la GUI appelle la
CLI ou le cœur en direct reste entière. Elle conditionne l'exécution en
arrière-plan (memlog 38) et la file d'attente (memlog 67).

**E35 — Thème, modèle d'application, packaging.**
*Input :* décision déléguée 6 (l. 233) : grille de vignettes, mise en page,
navigation, **thème**, framework, **modèle d'application**, **packaging**.
*Aval :* la mise en page et la navigation sont abondamment décidées ; le
framework est explicitement renvoyé après l'UX. Le **thème** n'est nulle part
(voir `reconcile-gui-prototype.md`, G30), le **modèle d'application** (une
fenêtre ? plusieurs ? documents multiples ?) non plus, et le **packaging** —
qui est pourtant l'Epic 8 et le seul moyen pour un vidéaste d'installer l'outil
— n'est jamais évoqué.

**E36 — Les stories 7.1-7.4 et leur absence d'AC.**
*Input :* §1, l. 14-22 : quatre stories nommées (7.1 orchestration visuelle, 7.2
paramétrage unifié, 7.3 outils de revue, 7.4 édition manuelle), *« `epics.md` ne
donne aucun critère d'acceptation détaillé »*, aucun fichier de story dans le
dépôt.
*Aval :* les parcours produisent cinq récits et une trentaine de surfaces, et
P3 note bien que certaines sont « à porter comme telles dans les stories » —
mais **rien ne rattache les surfaces aux quatre stories existantes**. Faut-il
remplir 7.1-7.4 ou redécouper l'Epic ? Le travail de Finalize s'arrête au bord
de cette question, qui est celle qui décide si la session est utilisable.

**E37 — « Une previz n'autorise rien ».**
*Input :* §3, l. 59-60 et contrainte 2 : document consultatif, aucun
consentement, aucun déclencheur ; *« le consentement appartient à la story 3.3
et se rejoue intégralement au lancement, quelle que soit la fraîcheur du
document »* ; *« une GUI qui lancerait une extraction sur la foi d'une previz
âgée contournerait la confirmation »*.
*Aval :* partiellement arrivé — la fenêtre de confirmation existe, et l'erreur
de lot existant se lève **au clic** (memlog 35). La règle générale, elle, n'est
pas portée : elle vaut pour les quatre ateliers, et elle est le motif exact de
la forme retenue à l'extraction.

**E38 — Aucune dépendance d'interface dans `requirements.txt`.**
*Input :* contrainte 11, l. 256 : critère de faute — une story de contrat qui en
ajoute une *« a préempté l'Epic 7 »*.
*Aval :* rien. C'est une garde qui protège l'Epic 7 lui-même, et qui devra être
levée explicitement au moment où la technologie sera tranchée.

---

## 3. Ce qui a été contredit

| # | L'input amont | La décision postérieure |
|---|---|---|
| **X1** | **Couleur MVP : pas de correction appliquée dans cette itération** — décision fermée de `IMPLEMENTATION_PLAN.md` (§2, l. 34) | memlog 59 (2026-08-16) et P1 étape 21 (2026-08-17) : bouton d'activation de la calibration couleur, choix d'un profil, rendu qui change à l'écran, bascule répétée pour juger ; memlog 56 ajoute la génération d'un profil de calibration scanner. L'interface conçue applique une correction couleur que le plan d'implémentation exclut du MVP |
| **X2** | **Réglages `makepdf` à exposer** : `template_id`, `patch_preset_id`, `frames_par_page`, `format`, `orientation`, `dpi`, `marge`, `gamut-map` (synthèse `makepdf`, l. 211) | memlog 45-46 (2026-08-16) : exposés = frames/page, format, **marge** seulement ; gabarit, dpi (toujours 600) et mapping gamut/patchs **imposés** ; orientation **automatique**. Cinq des huit paramètres listés en amont sont désormais interdits d'exposition |
| **X3** | **`timecode_base` exposé comme paramètre d'extraction** (synthèse `extract`, l. 206) | memlog 29 (2026-08-16) : la base de timecode se modifie **au clic droit sur le rush dans le chutier**, propriété du rush — *« pas dans la previz ni les paramètres »* |
| **X4** | **Le discriminant de version ne peut pas être dérivé, il est donné par l'opérateur** (§7.2, l. 160-161) — démonstration : le QR est identique d'une passe à l'autre | P5 étape 5 (2026-08-17) : *« c'est la **détection** qui le rattachera au même lot, comme une version différente de la même planche »*. **C'est le conflit le plus dur des deux rapports** : l'amont ne dit pas « on n'a pas fait », il dit « c'est impossible à partir du QR seul ». Si l'aval a raison, il faut ou bien un discriminant saisi quelque part, ou bien une nouvelle entrée au payload — ce qui relance l'arbitrage 3 (payload 2.1) |
| **X5** | **Le lot scanné ne porte aucune horodate** — le condensat est *« déterministe et inter-machine ; aucun pixel, aucune horodate »* (§7.1, l. 153) | Arbitrage 5 tranché par Egan (memlog 109, 2026-08-17) : *« la date de scan au manifest est voulue, point »*, l'arbitrage d'origine est explicitement défait. **Déjà consigné** en aval (P5, section « Dater les passes ») — rappelé ici pour que l'input ne soit pas relu comme actuel |
| **X6** | **La fusion de deux versions : « personne ne l'a demandée » — hors périmètre** (§7.2, l. 166) ; et **Epic 7 = surcouche optionnelle** qui *« peut avancer sans bloquer le cœur CLI »* (§2, l. 29 ; contrainte 12, l. 257) | memlog 110 (2026-08-17) conçoit la fusion (lot hybride). Et les parcours établissent que **quatre stories d'Epic 5 passent devant l'Epic 7** (tri par QR, désignation au manifest, payload 2.1, date de scan) : *« l'Epic 7 ne peut pas être entièrement spécifié sans que les stories d'Epic 5 correspondantes existent au moins comme contrat »*. L'Epic 7 n'est plus une surcouche optionnelle qui n'engage rien — c'est un arbitrage produit à assumer |

---

## 4. Ce qui est périmé

L'input se date lui-même : *« C'est l'état des sources au 2026-08-16 »* (l. 259).
Il est donc **antérieur aux sept arbitrages du 2026-08-17**. Ce qu'il ne faut
plus relire comme actuel :

* **Y1 — §7.1 et §7.2 dans leur conclusion.** « Aucune horodate » est défait
  (arbitrage 5) ; « la fusion, personne ne l'a demandée » est défait
  (memlog 110) ; « l'interface lui permettra de choisir la version à conserver »
  décrit un geste que P5 a remplacé par un montage à la frame.
* **Y2 — §2, « couleur MVP : pas de correction appliquée ».** Voir X1 : à
  confronter à l'état réel des stories de calibration (5.20, 5.21 existent au
  dépôt ; le memlog 54 renvoie à une story 5.22 « en cours »), dont ce rapport
  ne préjuge pas.
* **Y3 — §1, « Epic 7 : optionnel, backlog avancé », et contrainte 12
  (« orchestration sans blocage du cœur CLI »).** Voir X6 : la session UX a créé
  des dépendances d'Epic 5 vers l'Epic 7 qui rendent la formule caduque.
* **Y4 — Décisions déléguées 12 et 13.** Elles sont annoncées comme
  « consignées au `deferred-work.md`, à trancher ». Elles y sont bien
  (`deferred-work.md`, revue de 6.4 du 2026-08-11), avec la mention *« à rouvrir
  avec la story d'interface »*. Elles ne sont donc pas « à trancher plus tard » :
  **le moment de les rouvrir est maintenant**.
* **Y5 — La synthèse par commande (l. 202-222)** est une projection de ce que la
  GUI « doit exposer » écrite **avant** que la conception d'interface existe.
  Trois de ses lignes sont désormais contredites (X1, X2, X3). Elle reste
  précieuse pour la colonne « **montrer** », pas pour la colonne « exposer comme
  paramètres ».

---

## 5. Les 15 décisions déléguées, vérifiées une par une

C'est le point central de cette réconciliation. Chacune est confrontée au
memlog et aux parcours.

| # | Décision déléguée (source) | A-t-elle atterri ? | Où / pourquoi non |
|---|---|---|---|
| 1 | Choix de la version à conserver entre tirages (`5-12`) | **Oui**, transformée | memlog 110 + P5 : le choix est devenu une **composition à la frame** ; arbitrage 2 : la désignation vit au manifest |
| 2 | Présentation du choix entre versions (`5-14`) | **Oui** | P5 étapes 7-11 : dialogue au dépôt, choix en bloc, choix frame par frame |
| 3 | Comparaison visuelle de deux versions (`5-14`, story 7.3) | **Oui** | P5 étape 8 : outil « comparer » qui bascule d'une version à l'autre **au même timecode**, wipe évoqué comme équivalent |
| 4 | Sélection du tirage qui alimente `encode` (`5-12`, `6-1`) | **Oui** | Arbitrage 2 (memlog 96) : la désignation vit au manifest, donc une story d'Epic 5 ; P5 étape 14 |
| 5 | Édition manuelle des détections, adressage stable (`5-8` AC 5) | **Partiellement** | Le **geste** est arrivé (P3 ; memlog 120 : accessible en permanence). Le **vocabulaire d'adressage** `page_index` + `slot_index` + ID de marqueur, qui est ce que la story 7.4 doit écrire, n'est nulle part — voir E39 |
| 6 | Grille, mise en page, navigation, **thème**, framework, **modèle d'application**, **packaging** (`3-5`) | **Partiellement** | Mise en page et navigation : abondamment décidées. Framework : renvoyé après l'UX (memlog 11). Grille de vignettes : décidée comme surface mais **sans son producteur** (E01/E02). Thème, modèle d'application, packaging : **nulle part** — voir E35 |
| 7 | Orchestration visuelle (7.1) et **paramétrage unifié** (7.2) | **Partiellement** | L'orchestration est arrivée (panneau latéral, carte par tâche, exécution en arrière-plan). Le **paramétrage unifié** est décidé **à l'inverse** : un panneau de réglages **par atelier** (memlog 27, 45, 61, 66) plus des Préférences globales dont le contenu est explicitement indéterminé (memlog 73). Ce n'est pas un oubli, c'est un écart à assumer par rapport au libellé de la story 7.2 |
| 8 | Outils de revue et previz effective (7.3) | **Oui**, largement | Trois modes par atelier, aperçu vivant du PDF, mode lecteur, wipe inspectable image par image |
| 9 | **Rendu visuel des planches** : rasteriser le PDF réel **ou** dessiner le plan depuis les géométries (`4-9`) | **Non** | memlog 44 exige un aperçu « LIVE en direct » **sans dire lequel des deux**. Or les deux n'ont ni le même coût, ni la même fidélité, ni le même sens : dessiner le plan ne peut pas montrer un PDF rendu, rasteriser en direct à chaque changement de réglage est un tout autre problème de performance. Décision structurante encore ouverte |
| 10 | **Fournisseur de vignettes, politique de cache, budget, format d'image, transport des pixels** (`3-5`, `analyse-2026-08-08`) | **Non** | **Aucune trace.** Voir E01, E02, E17 : c'est l'élément le plus coûteux à ne pas réintégrer — il conditionne toutes les galeries et le mode lecteur |
| 11 | Surface CLI `--previz` sur `makepdf` / `scan` (`4-9`, `5-8`) | **Non** | Voir E34 : la question de savoir si la GUI appelle la CLI ou le cœur n'est jamais posée, alors qu'elle conditionne l'exécution en arrière-plan et la file d'attente |
| 12 | Afficher « voici ce qui aurait été produit, et pourquoi ça ne l'a pas été » pour les 8 refus d'encode (`6-4`) | **Non** | Voir E23 : vit au `deferred-work.md` avec la mention « à rouvrir avec la story d'interface » — cette session **est** cette occasion |
| 13 | Afficher la vérification technique du master (`6-4`) | **Non** | Voir E24 : même statut |
| 14 | Répondre à « montre-moi les trous » : frames de remplacement, drapeau `synthetic` (`5-8` AC 4) | **Oui**, enrichi | memlog 86 et P3 vont plus loin que l'amont : **deux natures de manque, deux comptages, jamais fondus**. Réserve : le compteur `synthetic_frame_count` lui-même n'a pas de surface (E16) |
| 15 | Choix du fournisseur de pixels en mode sans stockage (injection `slot -> PIL.Image`) (`analyse-2026-08-08` L4) | **Non** | Aucune trace. Se rattache à E01/E17 et à la previz multi-cadence de 3.6, dont le principe est que rien ne reste sur disque |

**Verdict : 6 pleinement arrivées (1, 2, 3, 4, 8, 14) · 3 partielles (5, 6, 7) ·
6 absentes (9, 10, 11, 12, 13, 15).**

Les six absentes ne sont pas de même nature : **10 et 15** sont des questions de
**production d'images** (sans elles, aucune galerie ni aucun lecteur ne
fonctionne) ; **9 et 11** sont des questions d'**architecture d'appel** (elles
décident ce que l'interface peut afficher et à quel coût) ; **12 et 13** sont
des **surfaces d'affichage** identifiées, déjà motivées, qui attendent
précisément cette session.

---

## 6. Recommandation par élément perdu

| # | Élément | Recommandation | Motif |
|---|---|---|---|
| E01 | Cache de prévisualisation (niveau 0) | **À réintégrer** | Facteur 500 mesuré ; sans lui toutes les galeries des parcours sont inutilisables |
| E02 | Vocabulaire de vignettes (absent / exact / approximate) | **À réintégrer** | Le cas nominal du contrat est « aucune vignette » ; l'interface ne doit pas présenter une image approximative comme exacte |
| E03 | Cinq codes dégradés de vignettes | **À réintégrer** | Le premier décrit une installation sans ffmpeg, c'est-à-dire une machine neuve |
| E04 | Détection de péremption d'un aperçu | **À réintégrer** | Les parcours jugent avant d'écrire ; juger sur un aperçu périmé est le piège que ces empreintes ferment |
| E05 | Surface d'affichage des avertissements | **À réintégrer** | Une vingtaine de codes fermes, avec interdiction contractuelle de les fusionner, et aucun endroit où les poser |
| E06 | `GEOMETRY_DEGRADED` à l'impression | **À réintégrer** | Prédit trois semaines à l'avance le QR illisible de P3 |
| E07 | `OVER_NOMINAL_BUDGET` | **À réintégrer** | Même famille, coût nul une fois la surface d'avertissement posée |
| E08 | `image_rect_mm` / `letterbox_policy` | **À réintégrer** | L'aperçu vivant est un point de jugement : il doit poser l'image là où le PDF la posera |
| E09 | `slot_labels` (redondance de secours) | **À écarter sciemment** | Filet interne au document ; aucune conséquence d'interface tant que les blocs de texte sont présents |
| E10 | `text_blocks` comme cible du pointage | **À réintégrer** | C'est ce qui rend l'arbitrage 4 implémentable sans reconnaissance de caractères |
| E11 | Rang d'ingestion vs `page_index` décodé | **À réintégrer** | Seul diagnostic disponible quand le rangement du vrac de P4 tourne mal |
| E12 | Marqueurs étrangers | **À réintégrer** | Cas réel sur un support qu'on colle et découpe |
| E13 | Échelle observée et résidu de reprojection | **À réintégrer** | Distingue une géométrie qui tient d'une géométrie fausse et silencieuse |
| E14 | `DPI_BELOW_QR_MINIMUM` | **À réintégrer** | Évite d'envoyer réparer à la main des centaines de pages qu'il fallait renumériser |
| E15 | `GAMUT_CLIPPING_DETECTED` et verdict conditionnel | **À réintégrer** | En P3 Camille juge la couleur à l'œil alors que l'outil sait |
| E16 | Compteurs de lot (dont `synthetic_frame_count`) | **À réintégrer** | « Un lot se lit d'abord par ses compteurs » ; P3 en exige deux, aucune surface ne les porte |
| E17 | Source d'images du mode lecteur | **À trancher par Egan** | Le mode lecteur est un point de jugement central et n'a aujourd'hui aucune source d'images praticable |
| E18 | `lot_state` et motif de refus | **À réintégrer** | La règle « pas d'encode d'un lot d'extraction » existe ; son explication à l'écran, non |
| E19 | Fiabilité du timecode par profil | **À réintégrer** | Le produit existe pour préserver les timecodes ; le réglage qui les dégrade est muet |
| E20 | Origine de la résolution retenue | **À réintégrer** | Évite un contresens sur un lot reconstruit, où la résolution source est absente par construction |
| E21 | `missing_pages` en index de page | **À trancher par Egan** | Deux langues coexistent (timecodes en galerie, index de page au verdict) sans passerelle |
| E22 | L'estimation de taille est un majorant | **À réintégrer** | Un chiffre sans sa nature se lit comme une mesure |
| E23 | Les 8 refus d'encode avec leur plan | **À trancher par Egan** | Rouvrir « un document `refused` ne porte aucun plan » a un coût côté contrat ; le `deferred-work.md` attend cette décision |
| E24 | Vérification technique du master | **À trancher par Egan** | Même dossier ; la forme appartient à `video_metadata`, pas à la previz |
| E25 | `overwrite` comme consentement | **À réintégrer** | Aucun parcours ne rencontre un master déjà présent ; la règle contractuelle dicte la forme |
| E26 | `source_lot_id` | **À réintégrer** | Socle technique du lot hybride ; la story d'Epic 5 de l'arbitrage 2 doit s'y adosser |
| E27 | Discriminant de version saisi par l'opérateur | **À trancher par Egan** | Conflit ouvert avec P5 (X4) ; touche l'arbitrage 3 et le payload |
| E28 | « Compléter avec un avertissement, jamais refuser » | **À réintégrer** | Formulation amont plus précise que celle de P5, avec son motif de terrain |
| E29 | *n* tirages × *m* versions | **À trancher par Egan** | Décide si un lot composé peut mêler des dispositions différentes — change l'invariant de complétude |
| E30 | Modes `stream` / `keep` / `prune` | **À trancher par Egan** | Axe de comportement entier, à conséquence directe sur l'espace disque annoncé en P1 |
| E31 | `--lot-slug` | **À réintégrer** | Rien ne nomme un lot reconstruit quand le QR ne le donne pas |
| E32 | « Un lot incomplet se montre en premier » | **À réintégrer** | Règle de priorité gratuite sur la pièce la plus chargée de l'interface |
| E33 | ProRes MOV par défaut | **À réintégrer** | Le profil exposé n'a aucune valeur proposée d'emblée |
| E34 | `--previz` et architecture d'appel | **À trancher par Egan** | Conditionne l'exécution en arrière-plan et la file d'attente, déjà décidées |
| E35 | Thème, modèle d'application, packaging | **À trancher par Egan** | Le thème pilote le code couleur, le packaging est la condition de l'ouverture au public |
| E36 | Rattachement des surfaces aux stories 7.1-7.4 | **À trancher par Egan** | Décide si la Finalize remplit quatre stories existantes ou redécoupe l'Epic |
| E37 | « Une previz n'autorise rien » | **À réintégrer** | Règle générale des quatre ateliers ; elle est le motif de la forme déjà retenue à l'extraction |
| E38 | Aucune dépendance d'interface dans `requirements.txt` | **À écarter sciemment** | Garde interne au dépôt, à lever explicitement le jour du choix de technologie — pas une décision d'interface |
| E39 | Vocabulaire d'adressage stable | **À réintégrer** | C'est ce qu'une story 7.4 doit écrire pour rendre l'édition exprimable |
| E40 | Un document de previz par encodage | **À réintégrer** | Chaque entrée de la file d'attente porte son propre aperçu — conséquence non tirée |
