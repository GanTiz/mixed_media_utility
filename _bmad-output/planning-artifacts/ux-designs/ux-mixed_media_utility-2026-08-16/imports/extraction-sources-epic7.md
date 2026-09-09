# Extraction des sources — EPIC 7 (Application GUI de supervision)

Document préparatoire à l'élaboration UX de l'Epic 7. Extraction factuelle des artefacts du dépôt, orientée « ce que la GUI doit savoir / montrer / piloter ». Aucune invention ; chaque élément est sourcé par fichier.

## 1. `epics.md` — Epic 7 et dépendances inter-EPICs

**Source :** `_bmad-output/planning-artifacts/epics.md` (lignes 346-357 et 489-505)

### Positionnement
- Statut : **optionnel, backlog avancé** (ligne 348). Pas encore de story développée ni de fichier de story 7.x dans le dépôt (vérifié : aucun artefact `*7-1*` … `*7-4*`).
- **Dépendance inter-EPICs** (ligne 496) : *« Epic 7 dépend des contrats des EPICs 2 à 6 mais peut avancer en parallèle sur la couche d'orchestration et de previz. »*
- Epic 10 est prioritaire au **même rang que l'Epic 7** (`EPIC10-ARB-12`), tous deux après le MVP strict (Epics 1-6) et avant les epics de diffusion (8-9).

### Feature 7.A — Orchestration visuelle du workflow
- **Story 7.1** : *« visualiser les étapes `extract`, `makepdf`, `scan`, `encode` et leurs artefacts »* — la GUI est un **pupitre de workflow** qui montre l'état des quatre commandes et leurs productions (frames, PDF, scans, médias encodés).
- **Story 7.2** : *« exposer les paramètres critiques de chaque commande dans une interface unifiée »* — une surface unique de paramétrage, par commande.

### Feature 7.B — Outils de revue
- **Story 7.3** : *« permettre la previz des frames, PDF, zones détectées et sorties encodées »* — la revue visuelle de chaque type d'artefact.
- **Story 7.4** : *« prévoir les points d'édition manuelle minimaux lorsque la détection automatique échoue »* — correction ponctuelle des détections de scan.

> **Note :** `epics.md` ne donne **aucun critère d'acceptation détaillé** pour 7.1-7.4 (les stories ne sont décrites que par ces phrases). Les AC de la GUI se reconstruisent à partir des contrats previz (sections 3-6) et des décisions déléguées (section 8).

## 2. `IMPLEMENTATION_PLAN.md` — cadrage de l'Epic 7

**Source :** `_bmad-output/implementation-artifacts/IMPLEMENTATION_PLAN.md` (lignes 119-125, 157-161, 163-169)

- **Rôle de l'Epic 7** : *« surcouche optionnelle de supervision et de paramétrage »*.
- **Décision structurante** (ligne 124) : *« la GUI peut avancer en maquettes, previz et orchestration de commandes sans bloquer le coeur CLI »* — la GUI se construit **par-dessus** la CLI, jamais contre elle.
- **Phase C — Surcouches** (lignes 157-161) : 1. Epic 7 GUI, 2. Epic 8 packaging, 3. Epic 9 documentation. L'Epic 7 ne démarre qu'après le cœur CLI (Phase B : extract → makepdf → scan → encode).
- **Décisions fermées pertinentes pour l'affichage** (lignes 163-169) :
  - format maître par défaut : **ProRes MOV** ;
  - scans d'entrée : formats multiples acceptés si lisibles, sortie reconstruite normalisée en **TIFF 16 bits** ;
  - couleur MVP : **pas de correction appliquée** dans cette itération ;
  - encode sans rush source : autorisé ;
  - **un QR par page**, payload non opaque.

## 3. Contrat de prévisualisation d'extraction (`3-5-gui-previz-extraction.md`)

**Source :** `_bmad-output/implementation-artifacts/3-5-gui-previz-extraction.md` — kind `extraction`, contrat `previz-1`. Statut : done.

### Périmètre du document (ce qu'il transporte)
- Document **JSON serialisable et versionné** (`PREVIZ_SCHEMA_VERSION = "previz-1"`), **dérivé sans recalcul** des sorties des stories 3.1/3.2/3.3 (projection stricte, jamais un calcul). Aucun octet d'image.
- **Enveloppe générique** (réutilisée telle quelle par les trois autres previz avec un autre `kind`) : `previz_schema_version`, `kind`, `state`, `generated_at_utc` (ISO 8601 avec `Z`), `subject`, `warnings`, `fingerprints`.
- **Charge spécifique `kind = "extraction"`** : `source_report` (métadonnées source, champs `source_*`, verbatim) et `frames` (liste ordonnée des frames retenues : `output_rank`, `source_index`, `frame_timecode`, `frame_path_relative`).
- **`subject`** porte : `project_id`, `rush_id`, `lot_id` (nullable en `planned`), `fps_source_exact`, `fps_target_exact`, `timecode_base`, `timecode_base_fps_exact`, `rounding_policy`, `batch_dir_relative`, `expected_frame_count`, `source_tail_frames`, `frames_present_count`.
- **Détection de péremption** : `generated_at_utc`, `rounding_policy`, et trois empreintes `sha256-v1:` — `fingerprints.selection` (les seules entrées de décision de la sélection : `fps_source_exact`, `fps_target_exact`, `source_frame_count`, `source_start_timecode`, `rounding_policy`, `timecode_base`), `fingerprints.source_report` (forme JSON du rapport 3.3), `fingerprints.source_signature` (optionnel, fourni par l'appelant, jamais calculé).

### Les deux régimes `planned` / `extracted`
- **`state = "planned"`** : avant extraction, `frame_path_relative` absent (les TIFF n'existent pas encore).
- **`state = "extracted"`** : après extraction, `frame_path_relative` renseigné. `frames_present_count` est **fourni par l'appelant** (jamais compté par le module) ; `expected_frame_count` vient de la sélection, jamais d'un comptage de fichiers.

### Vocabulaire de vignettes
- Bloc `thumbnail` par frame : `state` ∈ `{"absent", "exact", "approximate"}`, `origin` ∈ `{null, "rush_decode", "extracted_frame"}`, `path_relative`, `decoded_source_index` (renseigné **uniquement** si `state == "approximate"`).
- **Un document sans aucune vignette est valide et complet** — c'est le cas par défaut.
- Une vignette approximative **n'est jamais présentée comme exacte** (une entrée `approximate` sans `decoded_source_index` est refusée à la construction).
- Cas dégradés (codes fermes stables ASCII, portés par `warnings.previz`, émis par l'appelant) : `THUMBNAILS_UNAVAILABLE_NO_FFMPEG`, `THUMBNAILS_PARTIAL_BUDGET`, `THUMBNAIL_DECODE_FAILED`, `THUMBNAILS_APPROXIMATE_SEEK`, `SOURCE_UNREADABLE` — plus `LOT_INCOMPLETE` (ARB-13 : compteurs attendus/présents confrontés à la construction, refus si `present > attendu`). Trois familles d'avertissements **jamais fusionnées** : `warnings.selection`, `warnings.confirmation`, `warnings.previz`.

### La règle « une previz n'autorise rien »
- Le document est **consultatif** : aucun consentement, aucun état de confirmation exploitable comme accord, aucun déclencheur, aucune fonction qui lance ou confirme. **Le consentement appartient à la story 3.3 et se rejoue intégralement au lancement**, quelle que soit la fraîcheur du document. Une GUI qui lancerait une extraction sur la foi d'une previz âgée contournerait la confirmation (qui s'intercale après le probe et la sélection, avant l'appel ffmpeg).

### Ce qui est EXPLICITEMENT délégué à l'Epic 7 (frontière 3.5, section « Frontiere Epic 3 / Epic 7 »)
- le choix du **framework**, du **modèle d'application**, du **packaging** ;
- la **mise en page, la navigation, la grille de vignettes, le thème** ;
- l'**orchestration visuelle (7.1)** et le **paramétrage unifié (7.2)** ;
- les **outils de revue et la previz effective des frames (7.3)** ;
- l'**édition manuelle (7.4)** ;
- le **protocole de fournisseur de vignettes, la politique de cache, le budget, la taille, le format d'image, le mode de transport des pixels** (côté `ffmpeg_utils` Epic 3 ou côté Epic 7 — non tranché) ;
- critère de faute : **si une story de contrat fige un choix de techno GUI (dépendance ajoutée à `requirements.txt`, champ typé par un toolkit, format d'image imposé, écran décrit, protocole d'appel, politique de cache), elle est fausse**.
- Le **JSON est la forme normative** du contrat (pas un objet Python) pour ne préjuger d'aucune architecture : in-process (Qt/Tk), hors-processus (front lisant un fichier ou la sortie d'une commande), ou distante.

## 4. Contrat de prévisualisation PDF (`4-9-gui-previz-pdf.md`)

**Source :** `_bmad-output/implementation-artifacts/4-9-gui-previz-pdf.md` — kind `makepdf`, contrat `previz-1`. Statut : done.

### Ce que le document transporte
- **États** : `planned` (plan calculé, PDF non rendu) / `rendered` (PDF rendu, chemin relatif renseigné). En `rendered`, toute donnée constatée est fournie par l'appelant, jamais mesurée.
- **Pages** : `page_index` (base zéro), `page_count`.
- **Par page, les éléments posés** :
  - `frame_zones` : `slot_index`, `frame_timecode`, `frame_path_relative`, position `x_mm`/`y_mm`/`w_mm`/`h_mm`, plus `image_rect_mm` et `letterbox_policy` (projetés après revue — « l'aperçu ne ment plus ») ;
  - `qr` : position, `size_mm`, `geometry` (classement `check_print_geometry` : `reliable`/`degraded`…, transporté verbatim), `payload_bytes` ;
  - `aruco_markers` : `marker_id`, `center_x_mm`, `center_y_mm`, `size_mm` ;
  - `patches` : `value_id`, position, `size_mm`, et `rgb` (transporté — la GUI n'a pas à redupliquer la résolution de table) ;
  - `text_blocks` : `role` (= nom de zone 4.2), `content` (lignes exactes) ; `slot_labels` (redondance de secours slot → timecode) ;
- **Paramètres de composition** (`parameters`) : `template_id`, `patch_preset_id`, `frames_par_page`, `format`, `orientation`, `dpi`, `marge`.
- **`output_pdf_path_relative`** / `pdf_filename` : chemin *prévu* du PDF (`null` en `planned`).
- **Avertissements** : vocabulaire ferme `PDF_PREVIZ_WARNING_CODES` = `GEOMETRY_DEGRADED` (QR classé `degraded`), `LOT_INCOMPLETE` (déduit de la confrontation des compteurs, seule exception à la pureté d'émission ; `present > attendu` refuse à la construction), `OVER_NOMINAL_BUDGET` (page au-delà du budget nominal, sous le plafond).
- **Empreintes** : `fingerprints.composition` (les seules entrées de décision de la composition, `COMPOSITION_FINGERPRINT_FIELDS`) et `fingerprints.selection` (transportée verbatim, recette 3.5 ; jamais comparée au `frame_timecodes_digest` de 3.4).

### Ce qui revient à l'Epic 7
- **Aucun pixel dans le document** : la GUI **rasterisera le PDF réel** (état `rendered`) **ou dessinera le plan elle-même depuis les géométries transportées** — c'est explicitement un travail de rendu appartenant à l'Epic 7.
- Framework, mise en page d'écran, navigation, protocole d'appel, politique de cache (frontière identique à 3.5).
- Exposer une option `--previz` sur `makepdf` appartient à 4.1 ou à l'Epic 7.

## 5. Contrat de prévisualisation de scan (`5-8-gui-previz-scan.md`)

**Source :** `_bmad-output/implementation-artifacts/5-8-gui-previz-scan.md` — kind `scan`, contrat `previz-1`. Statut : ready-for-dev (jonction `previz_common` faite ici).

### Point 5 — l'adressage stable de chaque élément éditable (clé pour la story 7.4)
> *« Le document donne donc à chaque élément modifiable une **adresse stable et explicite** (au minimum `page_index` + `slot_index`, et pour un marqueur son ID), documentée comme telle. »*

- C'est **ce qui distingue cette previz de ses deux jumelles** : la story 7.4 doit pouvoir dire « la zone 2 de la page 3 est mal placée, voici le rectangle corrigé ».
- Le document rend l'édition **exprimable** ; **l'appliquer appartient à l'Epic 7** (story 7.4). Le document **n'autorise rien** pour autant : pas de champ de consentement, pas de déclencheur, aucune fonction qui relance une détection ou écrit un fichier.

### Ce que le document transporte (par page et au niveau lot)
- **Par page** : rang de lecture d'ingestion **et** `page_index` décodé (jamais l'un déduit de l'autre — une interface doit pouvoir montrer « le 3e fichier du dossier déclare être la page 1 », diagnostic du lot mélangé) ; statut de décodage QR ; identité décodée ; `template_id` retenu **et sa provenance** (QR ou manifest) ; marqueurs de coin détectés et marqueurs étrangers avec leur rôle ; échelle observée et résidu de reprojection ; pour chaque zone : `slot_index`, `frame_timecode`, rectangle de zone et rectangle de découpe (en mm **et** en pixels de page redressée) ; chemin relatif de la frame produite si elle l'a été ; statut de calibration et résultats de page ; `gamut_map_id` (toujours présent, jamais interprété) ; verdict d'écrêtage (conditionnel, omis si la calibration n'a pas tourné, **jamais remplacé** par un verdict « pas d'écrêtage »).
- **Drapeau `synthetic`** : dès qu'un chemin de frame est présent, `synthetic` l'est aussi (`false` compris) ; `synthetic_reason` (vocabulaire ferme `SYNTHETIC_FRAME_REASONS`) n'est transporté que si `synthetic == true`. Une page dont la détection a échoué reçoit une **frame de remplacement** (« FRAME MANQUANTE », mire) — **l'interface doit pouvoir répondre à « montre-moi les trous »** sans inspecter image par image.
- **Au niveau lot** : compteurs pages présentes/attendues, frames écrites/attendues, **`synthetic_frame_count`** — *« un lot se lit d'abord par ses compteurs »*.
- **Avertissements** : vocabulaire ferme `SCAN_PREVIZ_WARNING_CODES` (10 codes) = `LOT_INCOMPLETE`, `PAGE_QR_UNREADABLE`, `TEMPLATE_FROM_MANIFEST_NOT_QR`, `FOREIGN_MARKER_DETECTED`, `PAGE_SCALE_OUT_OF_TOLERANCE`, `PAGE_ASPECT_OUT_OF_TOLERANCE`, `CALIBRATION_FAILED`, `DPI_BELOW_QR_MINIMUM`, `GAMUT_CLIPPING_DETECTED` (un écrêtage doit être **vu** par l'opérateur), `SYNTHETIC_FRAME_WRITTEN`. Quatre familles d'avertissements séparées : `ingest`, `detection`, `output`, `previz`.
- **Empreintes** : `DETECTION_FINGERPRINT_FIELDS` — identité du lot, `template_id`, DPI de scan déclaré, `gamut_map_id` (obligatoire, sinon une previz périmée devient indétectable — l'angle mort trouvé côté impression), et empreinte de l'ensemble des pages ingérées via un **sous-condensat** `ingested_pages_digest` (sensible à l'ordre).
- **États** : `detected` (détection faite, aucune frame écrite) / `reconstructed` (frames écrites, chemins relatifs renseignés).
- **Aucun mécanisme de vignette** : la page scannée existe déjà sur disque — chemins relatifs seulement, la GUI ouvre le fichier.

### Ce qui revient à l'Epic 7
- framework, mise en page d'écran, navigation, **rendu visuel des pages scannées**, protocole d'appel, politique de cache — et surtout **l'édition elle-même (story 7.4)**, rendue possible par l'adressage stable.
- Exposer une option `--previz` sur `scan` appartient à 5.1 ou à l'Epic 7.

## 6. Contrat de prévisualisation d'encodage (`6-4-gui-previz-encodage.md`)

**Source :** `_bmad-output/implementation-artifacts/6-4-gui-previz-encodage.md` — kind `encode`, contrat `previz-1`. Statut : done. Quatrième jumelle, sur le socle commun `previz_common`.

### Ce que le document transporte
- **États** : **`planned` / `encoded` / `refused`** (trois états — la revue a imposé un état pour un encodage qui n'aura pas lieu). Un document `refused` ne porte **aucun plan** (champs de décision omis), et porte son motif verbatim depuis `ENCODE_REFUSAL_CODES` ; son empreinte n'est comparable à aucune autre. L'interface peut montrer le refus à côté du `planned`.
- **Un document par encodage prévisualisé** (jamais multi-profils, sinon empreinte ambiguë).
- **Le plan projeté** :
  - **lot retenu** : `lot_id`, `lot_state` (entrée de décision — 6.1 refuse en dessous de `scan`) ;
  - **candidats écartés** (en cas de `TIRAGES_MULTIPLES`, 6.1 liste les candidats) : constatation ;
  - **séquence ordonnée des frames** : `frame_paths` (chemins relatifs) + `sequence_timecodes` ;
  - **profil et conteneur** : `profile_id`, `container` ;
  - **résolution retenue** : `TargetResolution(requested, origin, resolution_id, size)` avec `origin` ∈ `{defaut, registre, native, personnalisee}` ; la résolution retenue est `size or source_size` ;
  - **cadence** : forme `"num/den"` (`exact_frame_rate`), jamais un flottant — c'est la seule exception nommée à la pureté de transport ;
  - **timecode de départ et sa base** : `TimecodePlan.emitted` (nullable), `.manifest_value`, `.base_rate` ;
  - **fiabilité du timecode pour le profil** : `plan.timecode.reliability` (constatation ; `reliable` sur `prores_hq`, `prores_422`, `prores_lt`, `dnxhr_hq`, `dnxhr_hqx` ; `best_effort` sur `h264_delivery`, `hevc_delivery`) ;
  - **mires** : `verdict.synthetic_present` / `.synthetic_missing` (constatation — le disque fait foi pour la présence, le manifest pour la nature) ;
  - **verdict de complétude** : `verdict.expected`, `.found`, `.missing_pages` (tuple d'**index de page**, jamais de timecodes), `.complete` ;
  - **chemin du master à produire** : `output_path` (constatation, dérivée de valeurs déjà dans l'empreinte) ;
  - **estimation de taille** : `estimated_bytes` (majoration « jamais optimiste », constatation, hors empreinte) ;
  - **poids réel** : `encoded_bytes` (obligatoire en `encoded`, interdit ailleurs — c'est le seul champ qui distingue `encoded` de `planned`) ;
  - **fichiers écartés** : `nonconforming`, `empty_files` ; **bornes déclarées** : `declared_bounds` ; **tags du conteneur** : `container_tags`.
- **Avertissements** : un **seul** seau `warnings.encode` (vocabulaire ferme `ENCODE_PREVIZ_WARNING_CODES`, **francophone** — orthographe du producteur : `LOT_INCOMPLET`, `TIRAGES_MULTIPLES`, `CARDINAL_ATTENDU_INDETERMINABLE`, `FRAMES_SYNTHETIQUES_PRESENTES`…). Le seau `previz` **n'existe pas** (aucun émetteur). Le motif de refus vit dans une section `refusal` de premier niveau avec `ENCODE_PREVIZ_REFUSAL_CODES`.
- **Empreinte** : `DECISION_FINGERPRINT_FIELDS` (9 entrées) — lot retenu, `lot_state`, profil, résolution retenue, cadence `"num/den"`, **sous-condensat de la séquence ordonnée** (une frame ajoutée, retirée ou **réordonnée** change l'empreinte), timecode de départ et sa base de validation. Hors empreinte : chemin du master, fiabilité du timecode, verdict de complétude, mires, estimation de taille, fichiers écartés, bornes, avertissements, tags.

### Ce qui revient à l'Epic 7
- Interface d'affichage (framework, mise en page, etc. — frontière identique aux jumelles).
- **Deux extensions identifiées** (consignées au `deferred-work.md`, à trancher) :
  - montrer « voici ce qui aurait été produit, et voici pourquoi ça ne l'a pas été » pour les **8 refus survenant après construction du plan** (`MASTER_DEJA_PRESENT`, `VERIFICATION_TECHNIQUE_EN_ECHEC`, `INTERRUPTION_CLAVIER`, `ARRET_DEMANDE`, `DESTINATION_NON_INSCRIPTIBLE`, `MASTER_EST_UN_REPERTOIRE`, `DOSSIER_DE_SORTIE_EST_UN_FICHIER`, `RESOLUTION_INCONNUE`) — demanderait de rouvrir la règle « un document `refused` ne porte aucun plan » ;
  - montrer la **vérification technique du master** (`EncodeCommandResult.verification`, non projeté — la forme appartient à `video_metadata`).
- `overwrite` n'entre **pas** au document : c'est un consentement, et « overwrite » est un mot interdit du JSON canonique — la GUI le demande comme consentement, jamais comme paramètre de previz.

## 7. Choix de version entre tirages/scans (`5-12` et `5-14`)

### 7.1 `5-12-tirages-multiples-du-meme-lot.md`
- **Cas** : imprimer deux planches pour le même lot (ex. 4 frames/page et 2 frames/page), les scanner toutes les deux. Un lot scanné porte un **condensat** : `<lot_id>-<condensat>` dérivé de `template_id`, `patch_preset_id` et `gamut_map_id` lus au payload (déterministe et inter-machine ; aucun pixel, aucune horodate).
- **Ce que la GUI devra présenter** : en cas de doublons, *« l'interface lui permettra de choisir la version à conserver, y compris entre deux versions d'annotation »* (contexte). Le rattachement est porté par le champ **`source_lot_id`** (chaque lot scanné déclare le lot d'extraction dont il dérive) — *« sans ce lien, rien ne permet de savoir que deux tirages sont deux versions du **même** contenu, et l'interface ne peut pas offrir le choix qui motive la story »* (AC 5). `source_lot_id` est la **seule voie de rattachement** (le suffixe `-<condensat8>` est déjà occupé par le condensat de bornes de 3.7 ; aucune analyse du nom ne peut distinguer les deux natures).
- **Ce qui est explicitement renvoyé à l'interface** (section « Ce qui n'est pas dans cette story ») :
  - *« **Le choix de la version à conserver.** Il appartient à l'interface (Epic 7, story 7.3 ou 7.4). Cette story rend le choix **possible** en cessant de faire entrer les tirages en collision ; elle ne le présente pas et n'en persiste aucun. »*
  - *« **La sélection du tirage qui alimente `encode`** (Epic 6). Même motif. »*

### 7.2 `5-14-plusieurs-scans-de-la-meme-planche.md`
- **Cas** : scanner plusieurs fois la **même planche**, annotée différemment → plusieurs versions du même rush. Le QR est identique d'une passe à l'autre : **le discriminant ne peut pas être dérivé**, il est **donné par l'opérateur**.
- **Discriminant** : un **numéro de 1 à 99** (`--version <n>` sur `scan`, `EPIC5-ARB-59`), composé sur **deux chiffres, zéro de tête compris** (`-01` à `-99`) pour que le tri lexicographique regroupe les passes d'un même tirage. Nom composé : `<lot_id>-<condensat-d-impression>-<version>` (ordre fixe).
- **Flux opérateur imposé** (`EPIC5-ARB-57`) : une version déjà présente sur le même tirage **complète le lot avec un avertissement — jamais un refus** (l'opérateur rescannerait une page refusée pour dérive et relancerait `scan`).
- **Ce qui est renvoyé à l'Epic 7** (section « Ce qui n'est pas dans cette story ») :
  - *« **La présentation du choix entre versions. Interface, Epic 7. »*
  - *« **La comparaison visuelle de deux versions. Story 7.3. »*
  - la fusion de deux versions : *« Personne ne l'a demandée »* — hors périmètre.
- **Conséquence pour la GUI** : après 5.12 + 5.14, un rush a *n* tirages × *m* versions. L'interface doit pouvoir lister les candidats d'un même contenu (via `source_lot_id`) et faire choisir celui qui alimente `encode` (6.1 refuse et énumère les candidats en cas de `TIRAGES_MULTIPLES`).

## 8. Prérequis GUI — cache de prévisualisation (`analyse-2026-08-08-empreinte-disque-et-templates.md`)

**Source :** `_bmad-output/implementation-artifacts/analyse-2026-08-08-empreinte-disque-et-templates.md` (A.6 et synthèse)

- **A.6** : le cache de prévisualisation est le *« niveau 0 »* du mode hors ligne (consulter, naviguer, comparer, décider sans jamais produire) et *« c'est un **prérequis de la GUI** », « le meilleur rapport valeur/coût de tout ce document »*.
- **Coûts de lecture mesurés** (disque local, OpenCV) :

  | artefact | taille | temps de lecture |
  |---|---|---|
  | TIFF 16 bits (lot actuel) | 48,6 Mo | **99 ms/frame** |
  | preview JPEG 1280 px | ~0,4 Mo | ~6,8 ms |
  | vignette JPEG 320 px | 6,5 Ko | **0,2 ms** |

- **Le chiffre décisif** : *« une grille de 200 vignettes coûte **20 secondes** si elle lit les TIFF du lot, et **40 millisecondes** si elle lit un cache de vignettes — un facteur 500 »*. Conclusion : *« dès qu'une GUI affiche plus d'une dizaine de frames, il devient obligatoire »*.
- **Deux résolutions, pas une** :
  - **vignette ~320 px** (10-25 Ko) : grille de contact, navigation, choix de cadence, sélection de plages — *« c'est elle qui rend la GUI vivante »* ;
  - **preview ~1280 px** (150-400 Ko) : contrôle visuel d'une frame, jugement de mise en page, arbitrage de gabarit.
  - Les deux : **< 0,5 Go pour 1000 frames UHD** (contre 49,8 Go).
- **Le contrat existe déjà** : le vocabulaire de vignettes d'`extraction_previz` (3.5) a été *« écrit pour ça »* ; le cache ajoute une **troisième valeur d'origine** `preview_cache` à une énumération fermée (extension additive prévue).
- **Invariants du cache** (le rendre structurellement incapable d'être pris pour un lot) : (1) **nommage distinct** — jamais `build_extracted_frame_filename`, sinon `verify_extracted_lot` deviendrait faux ; (2) **format lossy assumé, hors de `frames/`** (JPEG auto-évidemment non livrable dans un projet TIFF 16 bits — propriété de sûreté) ; (3) **dérivable, jetable, invalidable** — péremption adossée à `lots[].frame_timecodes_digest` (existe déjà).
- **Portée** : le cache ne remplace ni le niveau 1 (régénérer un PDF identique) ni le niveau 2 (régénérer avec d'autres paramètres), ne produit **aucun PDF valide** et n'alimente **jamais le chemin scan**. Distinct de la prévisu multi-cadence de 3.6 (qui porte sur un rush **non encore extrait** — rien ne doit rester sur disque) : le cache porte sur un **lot déjà extrait et déjà persisté**.
- **Arbitrage 2 recommandé** : niveau 0 (cache de prévisu) **systématique et non optionnel** puisqu'il conditionne la GUI.

## 9. Flux de travail produit (`project-brief.md`)

**Source :** `_bmad-output/design-artifacts/A-Product-Brief/project-brief.md`

- **Pitch** : utilitaire local-first qui extrait des frames d'un rush vidéo, les prépare pour impression dans un support auto-descriptif, permet leur transformation physique, puis reconstruit frames et média final à partir des scans.
- **Flux standardisé** : **`extract -> makepdf -> scan -> encode`** (objectif produit).
- **Scénario clé** : (1) rush sélectionné sur machine A ; (2) `extract` produit un lot de frames + manifest ; (3) `makepdf` produit des PDF imprimables (frames, marqueurs, QR codes, patchs, informations lisibles) ; (4) PDF transmis ou imprimés par un tiers ; (5) pages annotées ou transformées physiquement ; (6) un tiers scanne sur machine B **sans disposer du projet d'origine** ; (7) `scan` détecte, recadre, calibre et recrée/enrichit le projet local ; (8) `encode` reconstruit le média final avec les métadonnées adéquates.
- **Utilisateurs** : primaire = porteur du projet artistique (pilote le workflow et les arbitrages de rendu) ; secondaires = personne chargée de l'impression, personne chargée du scan, collaborateurs aval. **Travail asynchrone sur machines distinctes** : l'information doit être transmise dans les fichiers eux-mêmes (manifest autoportant, noms de fichiers/QR/marqueurs/métadonnées comme éléments de contrat).
- **Mentions d'interface** : *« CLI est la colonne vertébrale du coeur technique », « GUI est un stade avancé et optionnel »* (Epic 7 = *« supervision et paramétrage du workflow, stade avancé et optionnel »*).

## Synthèse par commande métier — ce que la GUI doit montrer / exposer

### `extract`
- **Montrer** : sélection des frames (mapping ordonné `output_rank` → `frame_timecode`), métadonnées source (champs `source_*`, champs absents), état des vignettes (`absent`/`exact`/`approximate` + `origin`), compteurs `expected_frame_count` vs `frames_present_count` (un lot incomplet se montre **en premier**), cadences source/cible en `"num/den"`, `timecode_base`, `rounding_policy`, avertissements (familles séparées), détection de péremption (empreintes).
- **Exposer comme paramètres** : chemin du rush, fps cible, bornes éventuelles (timecodes in/out), timecode_base, profondeur de sortie (8/16), confirmation des métadonnées — **consentement rejoué au lancement**, jamais accordé par une previz.
- **Prévisualisation** : contrat `previz-1` kind `extraction` (3.5), états `planned`/`extracted`. Cache de vignettes requis dès la grille (facteur 500).

### `makepdf`
- **Montrer** : « voici les planches que `makepdf` produira » — pages, zones de frames (position/tailles mm, `image_rect_mm`, `letterbox_policy`), QR (position, taille, `geometry`, `payload_bytes`), marqueurs ArUco (ID, centre), patchs (preset, `rgb`), blocs de texte, paramètres de composition, avertissements (`GEOMETRY_DEGRADED`, `LOT_INCOMPLETE`, `OVER_NOMINAL_BUDGET`).
- **Exposer comme paramètres** : `template_id`, `patch_preset_id`, `frames_par_page`, `format`, `orientation`, `dpi`, `marge`, `gamut-map`.
- **Prévisualisation** : contrat `previz-1` kind `makepdf` (4.9), états `planned`/`rendered`. Rendu visuel = rasteriser le PDF réel ou dessiner le plan depuis les géométries (décision Epic 7).

### `scan`
- **Montrer** : « voici ce que le scan a détecté et ce qu'il produira » — rang de lecture vs `page_index` décodé (lot mélangé), statut QR + identité décodée, `template_id` + provenance (QR/manifest), marqueurs (coins + étrangers), échelle observée/résidu, rectangles de zone et de découpe (mm et px), frames produites avec drapeau `synthetic`/`synthetic_reason` (les **trous** visibles), statut calibration, verdict d'écrêtage, `gamut_map_id`, compteurs lot (pages, frames, `synthetic_frame_count`), **adresses stables** `page_index` + `slot_index` (+ ID de marqueur) pour l'édition.
- **Exposer comme paramètres** : DPI de scan déclaré, `--lot-slug`, `--version <1-99>` (5.14), et **le choix du tirage/version à conserver** (renvoyé par 5.12/5.14).
- **Prévisualisation** : contrat `previz-1` kind `scan` (5.8), états `detected`/`reconstructed`. Pas de vignettes (chemins relatifs). **Édition manuelle** (7.4) rendue possible par l'adressage stable.

### `encode`
- **Montrer** : « voici ce qui va sortir » — lot retenu (+ `lot_state`), candidats écartés (tirages multiples), séquence ordonnée, profil/conteneur, résolution retenue (+ `origin`), cadence `"num/den"`, timecode + fiabilité, mires présentes/manquantes, verdict de complétude (`missing_pages` = index de page), chemin du master, `estimated_bytes` (majorant) et `encoded_bytes`, refus avec motif (`refused`).
- **Exposer comme paramètres** : `lot_id` (sélection parmi les candidats), `profile_id`, conteneur, résolution (défaut/registre/native/personnalisée), **`overwrite` comme consentement** (hors document de previz), modes de sortie stream/keep/prune (axe B).
- **Prévisualisation** : contrat `previz-1` kind `encode` (6.4), états `planned`/`encoded`/`refused`. Un document par encodage prévisualisé.

## Liste des décisions déléguées à l'Epic 7 (avec source)

| # | Décision déléguée | Source |
|---|---|---|
| 1 | **Choix de la version à conserver** entre plusieurs tirages d'un même lot (y compris entre versions d'annotation) — à présenter à l'utilisateur, jamais persistant côté 5.12 | `5-12`, « Ce qui n'est pas dans cette story » : « Le choix de la version à conserver. Il appartient à l'interface (Epic 7, story 7.3 ou 7.4) » |
| 2 | **Présentation du choix entre versions** de scans de la même planche | `5-14`, « Ce qui n'est pas dans cette story » : « Interface, Epic 7 » |
| 3 | **Comparaison visuelle de deux versions** | `5-14` : « La comparaison visuelle de deux versions. Story 7.3 » |
| 4 | **Sélection du tirage/version qui alimente `encode`** | `5-12` (motif même, « Epic 6 » renvoyé hors story) ; `6-1` refuse et énumère les candidats (`TIRAGES_MULTIPLES`) |
| 5 | **Édition manuelle des détections** de scan (7.4) — l'adressage stable `page_index` + `slot_index` + ID de marqueur rend l'édition *exprimable*, l'appliquer appartient à l'Epic 7 | `5-8` AC 5 et Dev Notes « Frontiere Epic 5 / Epic 7 » |
| 6 | **Grille de vignettes, mise en page, navigation, thème, framework, modèle d'application, packaging** | `3-5`, « N'appartient pas à cette story (Epic 7, différé) » |
| 7 | **Orchestration visuelle du workflow (7.1)** et **paramétrage unifié (7.2)** | `3-5`, frontière ; `epics.md` Feature 7.A |
| 8 | **Outils de revue et previz effective des frames, PDF, zones détectées, sorties encodées (7.3)** | `3-5`, frontière ; `epics.md` Feature 7.B ; `5-14` (comparaison) |
| 9 | **Rendu visuel des planches** : rasteriser le PDF réel (`rendered`) ou dessiner le plan depuis les géométries transportées | `4-9`, Dev Notes et question ouverte 1 |
| 10 | **Fournisseur de vignettes, politique de cache, budget, format d'image, mode de transport des pixels** (producteur côté `ffmpeg_utils` ou côté Epic 7 — non tranché) | `3-5`, Dev Notes « Vignettes » et question ouverte 4 ; `analyse-2026-08-08` A.6 (cache comme producteur attendu) |
| 11 | **Surface CLI `--previz`** sur `makepdf` / `scan` (appartient à 4.1 / 5.1 ou à l'Epic 7) | `4-9` et `5-8`, Project Structure Notes |
| 12 | **Affichage « voici ce qui aurait été produit, et pourquoi ça ne l'a pas été »** pour les 8 refus d'encode survenant après construction du plan (extension à trancher : rouvrir « un document `refused` ne porte aucun plan ») | `6-4`, « À consigner au deferred-work » point 5 et Décision 4 |
| 13 | **Affichage de la vérification technique du master** (`EncodeCommandResult.verification`, non projeté) | `6-4`, « À consigner au deferred-work » point 6 |
| 14 | **Réponse à « montre-moi les trous »** : visualisation des frames de remplacement « FRAME MANQUANTE » (drapeau `synthetic`) sans inspection image par image | `5-8`, AC 4 et Dev Notes (EPIC5-ARB-8) |
| 15 | **Choix du fournisseur de pixels en mode sans stockage** (injection `slot -> PIL.Image` au lieu de `Path`) si un mode éphémère est retenu | `analyse-2026-08-08` A.2/A.4 (levier L4) |

## Contraintes transverses relevées

1. **Pas de pixel dans les documents previz** : chemins **relatifs** au dossier projet uniquement (vérifié par le détecteur unique `io/manifest._iter_absolute_path_violations`), aucune image, aucun base64. Le **chemin du rush source n'est jamais un champ du contrat** (le rush n'a aucune obligation de vivre dans le projet). La GUI ouvre les fichiers. *(3-5, 4-9, 5-8, 6-4)*
2. **Une previz n'autorise rien** : document consultatif, sans consentement ni déclencheur ; le consentement (3.3), le `--yes`/`overwrite` d'encode se **rejouent au lancement**, jamais accordés par un document. Verrouillé par des tests (préfixes `run/launch/confirm/approve/authorize/trigger/persist/save/write/apply/validate_/encode_…` interdits, mots `overwrite`/`yes`/`confirmed`/`granted` interdits du JSON canonique). *(3-5 AC 11, 5-8 AC 5, 6-4 AC 5)*
3. **Cache de prévisualisation obligatoire au-delà d'une dizaine de frames** : 99 ms/frame en lisant les TIFF du lot contre 0,2 ms par vignette JPEG — facteur 500 sur une grille de 200 vignettes. Deux tailles : vignette ~320 px (navigation/grille) et preview ~1280 px (contrôle visuel). Contrat de vignette déjà en place (3.5) ; 3e origine `preview_cache` à ajouter. *(analyse-2026-08-08 A.6)*
4. **Enveloppe `previz-1` commune et partagée** : `previz_schema_version`, `kind`, `state`, `generated_at_utc`, `subject`, `warnings`, `fingerprints` — versionnée indépendamment du manifest. États spécifiques par kind : `extraction` → `planned`/`extracted` ; `makepdf` → `planned`/`rendered` ; `scan` → `detected`/`reconstructed` ; `encode` → `planned`/`encoded`/`refused`. *(3-5, 4-9, 5-8, 6-4)*
5. **Cadences en forme unique `"num/den"`** (`codec_profiles.exact_frame_rate`, dénominateur toujours explicite) — dans le document **et** dans les empreintes. *(3-5 AC 4, 6-4 AC 4)*
6. **Empreintes `sha256-v1:`** : une recette de canonicalisation unique, jamais comparable entre portées (ex. `fingerprints.selection` ≠ `frame_timecodes_digest` de 3.4). *(3-5, 5-8)*
7. **Vocabulaire d'avertissements ferme par kind**, noms de constantes distincts (`PREVIZ_WARNING_CODES` vs `PDF_PREVIZ_WARNING_CODES` vs `SCAN_PREVIZ_WARNING_CODES` vs `ENCODE_PREVIZ_WARNING_CODES`) — pas de homonymie. *(ARB-14 ; 4-9, 5-8, 6-4)*
8. **Familles d'avertissements jamais fusionnées ni traduites** : `selection`/`confirmation`/`previz` (3.5), `ingest`/`detection`/`output`/`previz` (5.8), `encode` seul (6.4). *(3-5, 5-8, 6-4)*
9. **`LOT_INCOMPLETE` déduit à la construction** (compteurs confrontés, `present > attendu` refusé) — seule exception à la pureté d'émission (fermée dans 6.4, qui suit l'orthographe francophone `LOT_INCOMPLET` de son producteur). *(ARB-13 ; 3-5, 4-9, 5-8, 6-4)*
10. **La GUI peut être in-process, hors-processus ou distante** — le JSON est la forme normative du contrat de données ; aucune techno d'interface n'est figée nulle part. *(3-5 Dev Notes)*
11. **Aucune dépendance d'interface dans `requirements.txt`** au 2026-08-08 — toute story de contrat qui en ajoute une « a préempté l'Epic 7 » (critère de faute). *(3-5, 3-6, 4-9, 5-8, 6-4)*
12. **Orchestration sans blocage du cœur CLI** : la GUI avance en maquettes/previz pendant les Epics 2-6 ; Epic 7 dépend des contrats des EPICs 2 à 6. *(IMPLEMENTATION_PLAN.md, epics.md)*

**Note de méthode :** les stories 7.1-7.4 n'ont ni AC détaillés dans `epics.md` ni fichiers de story dédiés dans le dépôt. Ce document reconstitue donc les besoins de l'interface à partir des contrats previz (3.5, 4.9, 5.8, 6.4), des renvois explicites à l'Epic 7 (frontières) et des décisions déléguées (5.12, 5.14, analyse-2026-08-08, IMPLEMENTATION_PLAN). C'est l'état des sources au 2026-08-16.
