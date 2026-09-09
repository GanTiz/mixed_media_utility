# Tester la chaîne complète : extract → makepdf → scan → encode

> **AMENDEMENT DU 2026-08-17 — LIRE AVANT DE SUIVRE CETTE PROCÉDURE.** La story
> 5.22 (`EPIC5-ARB-80`, `EPIC5-ARB-81`) déplace la calibration **du lot vers la
> chaîne de scan**, et trois faits décrits ci-dessous ne sont plus vrais :
>
> 1. **`makepdf` n'insère plus la page de calibration** à l'index 0 du lot. Elle se
>    génère à la demande : `makepdf --project P calibration-page --chaine "<libellé>"`.
>    **Depuis la story 5.23 (2026-08-18) elle ne demande plus ni `--rush`, ni `--fps`,
>    ni `--lot`** : elle se génère *avant* toute extraction, et un projet en porte
>    autant que de chaînes de scan. Le libellé de chaîne, lui, est obligatoire.
>    Le PDF de planches ne compte donc plus « les planches **plus** la page de
>    calibration » mais exactement les planches — tous les cardinaux de pages de ce
>    document sont à diminuer de un.
> 2. **La correction n'est plus ajustée à chaque scan.** Elle est ajustée **une fois
>    par chaîne** — `scan --project P --scan S --dpi D calibrate` — consignée sous
>    `versions/calibration/<chain_id>.json`, puis **réutilisée** par tous les lots de
>    la chaîne. C'est ce qui corrige le motif d'origine de la story : les scans du
>    même scanner étaient refusés par divergence alors que la chaîne était la même.
> 3. **Une planche qui diverge n'est plus refusée.** Elle est livrée **en brut** avec
>    son écart chiffré au manifest (`not_applied`, motif
>    `page_diverges_without_explicit_apply`), et le drapeau
>    `--appliquer-la-correction-de-calibration-telle-quelle` reste le geste explicite
>    qui applique la correction quand même. La section « une planche qui diverge »
>    ci-dessous décrit donc l'ancien régime.
>
> Ce qui reste vrai sans réserve : la lecture d'une page de calibration **présente
> dans un scan** (ancien tirage), le transport de la correction aux pixels, et toute
> la partie `encode`. Cet amendement n'a **pas** été revérifié sur le terrain — les
> commandes de ce document l'ont été le 2026-08-12, avant la story 5.22 : une
> nouvelle passe de terrain reste à faire, et elle est le seul moyen de rendre ce
> document exact plutôt qu'amendé.

Document manuel. Toutes les commandes ci-dessous ont été **exécutées et vérifiées
le 2026-08-12** contre l'état du dépôt après les stories 5.15, 5.17, 5.18, 5.16 et
**5.19**. Elles complètent `test-chaine-extract-makepdf.md` et
`test-chaine-scan-epic5.md`, qu'elles ne remplacent pas : ce document ajoute
**`encode`**, la **page de calibration** de la story 5.16, et répond à la question
« avec et sans retouche colorimétrique ».

## La réponse courte sur la colorimétrie, à lire avant tout le reste

**La chaîne applique désormais la correction couleur**, depuis la story 5.19
(`EPIC5-ARB-65`, qui renverse `EPIC5-ARB-5`). La correction du lot est ajustée
**une seule fois**, sur la page de calibration, puis transportée à chaque planche
d'images ; elle est appliquée aux **pixels** des frames rescannées avant leur
écriture, et le manifest déclare ce qui a été corrigé, page par page.

Le récapitulatif d'`encode` porte donc maintenant **deux** lignes de colorimétrie,
et elles ne disent pas la même chose :

> Colorimetrie        : Approximation assumee: les valeurs viennent d'un scanner,
> donc sRGB de fait, et le master est tague bt709. sRGB et Rec.709 partagent
> primaires et point blanc, seule la courbe de transfert differe.
> Correction couleur  : applied -- correction active appliquee aux pixels, ajustee
> sur la page de calibration du lot; le detail par page vit dans
> reconstruction.page_calibration_results
> Constat : `APPROXIMATION_SRGB_TAGUEE_REC709`

La seconde ligne se lit **sur le lot encodé** et non sur le projet
(`EPIC5-ARB-68`) : `encode` produit un master par lot, et lire un champ de portée
projet lui faisait annoncer « correction active appliquée aux pixels » au master
d'un lot **non corrigé** dès qu'un *autre* lot du même projet l'était — le cas
nominal de la v2.1, deux lots du même rush à deux cadences. Un lot qui ne déclare
rien se lit `not_applied`.

La première **reste vraie** : elle parle de la **courbe de transfert** de l'espace
de sortie, que la correction active ne touche pas. Seule la phrase « le MVP
n'applique aucune correction colorimétrique active » a été retirée, parce qu'elle
est la seule que la story 5.19 rend fausse. Le constat
`APPROXIMATION_SRGB_TAGUEE_REC709`, lui, ne bouge pas.

**Ce qui n'a pas changé** : la décompression de gamut `G^-1` reste post-MVP,
`gamut-map-none-1` reste le défaut, et « ce qui n'a pas été corrigé est déclaré
non corrigé ». Un lot dont la page de calibration **manque** au scan sort
`not_applied` et reste entièrement exploitable.

Quand la page de calibration **est là mais ne sert pas**, le statut dépend de ce que
le code a pu savoir d'elle — et c'est une distinction à connaître avant de lire un
manifest, pas un détail :

* son **QR est lu**, donc le lot sait qu'elle porte le rôle de calibration, mais
  son treillis est illisible ou sa géométrie n'est pas résolue (coin corné) →
  `failed`, avec son motif. Ça dit à l'opérateur qu'un rescan de cette **seule**
  feuille récupérerait la couleur de tout le lot ;
* son **QR lui-même** est illisible → le rôle est inconnaissable, et le lot sort
  `not_applied` comme si la feuille manquait. Le code ne peut pas savoir que la
  feuille perdue *était* la page de calibration ; c'est la seule déclaration
  honnête, mais elle ne signale rien — si tu sais avoir scanné une page de
  calibration et que le lot sort `not_applied`, c'est ce cas-là.

### Le piège de la boucle sans imprimante, à connaître avant de conclure

La boucle « réingérer le PDF que `makepdf` vient d'écrire » (section 5) valide le
**câblage**, pas la **colorimétrie**. Mesuré le 2026-08-12 sur le lot de référence
`TEST_FILE_12p5` : le lot sort bien `applied` sur ses sept planches, mais la
correction ajustée est **exactement l'identité** — matrice unité, écart de
**0,00 code 8 bits** sur un balayage de six couleurs. C'est normal et ce n'est pas
un défaut : sans encre ni papier ni capteur, le treillis rendu est *déjà* égal à
sa référence, donc il n'y a rien à corriger.

Autrement dit : cette boucle prouve que la correction traverse la chaîne, qu'elle
atteint les pixels et que le manifest la déclare. Elle ne prouve **rien** de son
effet visuel. Pour voir l'effet, il faut un tirage réel — ou la suite de tests
`test_scan_calibration_application.py`, qui interpose une presse de synthèse et
mesure l'écart au centre de chaque frame passer de **19,0–28,0 à 0,33–1,06 code
8 bits**, sur les huit frames du lot (la première frame seule tombe de 27,7 à
0,75 ; ce couple, republié isolément par une revue précédente, n'était pas
représentatif des sept autres).

## 0. Prérequis

Depuis la racine du dépôt. Aucun script `mixed-media-util` n'est installé via
`pip` : tout passe par `python -m`, avec `PYTHONPATH` pointant sur `src/`.

```bash
export PYTHONPATH="$PWD/src"
```

> **Ce réglage est piégeux, et c'est mesuré** : `PYTHONPATH` posé ainsi ne vaut
> que pour la commande tapée **depuis la racine du dépôt**, dans **ce**
> terminal. Depuis n'importe quel autre répertoire — ou dans un nouveau
> terminal —, `python -m mixed_media_utility.cli` échoue en silence avec
> `No module named mixed_media_utility.cli`, sans dire pourquoi.
>
> Le raccourci `bin/mmu` (ou `bin/mmu.cmd` sous Windows) évite ce piège
> **par construction** : il calcule `PYTHONPATH` depuis sa **propre**
> position sur le disque, jamais depuis le répertoire courant, donc il
> fonctionne d'où qu'on l'appelle. Installation en une fois :
>
> ```bash
> bash scripts/install-mmu.sh              # Linux / macOS / Git Bash
> ```
> ```powershell
> .\scripts\install-mmu.cmd                # Windows, double-clic ou cmd.exe/PowerShell
> ```
>
> Sous Windows, `install-mmu.cmd` est la forme à préférer : la politique
> d'exécution PowerShell par défaut (`Restricted`) bloque tout `.ps1` local
> non signé, et ce `.cmd` contourne ça pour son seul process, sans droits
> admin ni changement permanent. Lancer `install-mmu.ps1` directement échoue
> avec `UnauthorizedAccess` sauf à ajouter la même astuce à la main :
> `powershell -ExecutionPolicy Bypass -File .\scripts\install-mmu.ps1`.
>
> Ouvrir un **nouveau** terminal (le `PATH` mis à jour n'atteint pas les
> fenêtres déjà ouvertes), puis `mmu --help` remplace
> `python -m mixed_media_utility.cli --help` partout dans ce document, depuis
> n'importe quel répertoire.

`ffmpeg` et `ffprobe` doivent être présents (`extract` et `encode` en dépendent).

> **Si tu pars du lot de référence `TEST_FILE_12p5` du dépôt** (et non d'un rush à
> toi), il faut `git-lfs` : les TIFF de `projects/` sont versionnés en LFS, et sans
> lui `git` rend des **pointeurs de 133 octets sans lever d'erreur** — le symptôme
> arrive bien plus loin, sous la forme d'un message de décodage d'image
> incompréhensible.
>
> ```bash
> apt-get install -y git-lfs
> git lfs pull --include="projects/projet_demo/**/*.tiff"
> ```
>
> On tire **par motif de chemin** : tout rematérialiser pèse ~1,4 Go. Rien de tout
> ceci n'est nécessaire si tu extrais tes propres frames à l'étape 2.

## 1. Choisir les bornes, sans rien extraire (facultatif)

```bash
python -m mixed_media_utility.cli previz --video <rush.mp4> --fps 12.5
```

Les timecodes affichés sont ceux du **rush**, pas un décalage depuis son début —
c'est la même base de temps que `--in` / `--out` de l'étape suivante.

## 2. Extraire le lot de frames

```bash
python -m mixed_media_utility.cli extract \
    --project mon_projet \
    --video <rush.mp4> \
    --fps 12.5 \
    --yes --accept-unknown-color
```

* `--project` est **créé s'il est absent** ;
* `--yes` remplace le consentement interactif, `--accept-unknown-color` le
  consentement supplémentaire quand la colorimétrie source est incomplète. Sans
  eux, la commande attend une réponse au terminal ;
* `--in` / `--out` bornent l'extrait, en timecode source, chacune indépendamment.
  Une borne hors du rush est **refusée avec son motif chiffré** — vérifié : « la
  borne de sortie `00:00:02:00` désigne l'index 50, au-delà du dernier index
  valide 25 ».

Sortie : `mon_projet/frames/<rush>_<fps>/`, en TIFF 16 bits. Sur le rush de test
du dépôt (26 images source à 25 im/s), la cible 12,5 rend **13 frames**.

## 3. Renseigner l'espace couleur cible — étape obligatoire, et facile à oublier

`makepdf` **refuse** de composer si `color.target_colorspace` est absent du
manifest, le payload QR l'exigeant non vide (contrat 2.3) :

> `color.target_colorspace` est absent du manifest : le payload QR exige un espace
> couleur cible non vide. Renseigner `color.target_colorspace` dans
> `project.json` avant `makepdf`.

La valeur du MVP est `rec709` :

```bash
python - <<'PY'
import json, pathlib
p = pathlib.Path("mon_projet/project.json")
m = json.loads(p.read_text())
m.setdefault("color", {})["target_colorspace"] = "rec709"
p.write_text(json.dumps(m, indent=2, ensure_ascii=False))
PY
```

## 4. Composer les planches imprimables

```bash
python -m mixed_media_utility.cli makepdf \
    --project mon_projet \
    --lot <lot_id> \
    --geometrie v2 \
    --frames-par-page 2 \
    --orientation portrait
```

Ce qu'il faut savoir sur chaque option :

* **`--geometrie v2`** est le défaut depuis la story 5.18. C'est **elle qui ajoute
  la page de calibration** : la v1 ne peut pas en porter une (son dégagement de
  coin de 60 mm ne laisse que 57 à 66 cellules pour les 130 pastilles du
  treillis), et un lot v1 se compose donc exactement comme avant. Vérifié : le
  même lot rend **5 pages en v1 et 6 en v2**, la page ajoutée étant la première ;
* **`--nombre-patchs` n'a plus besoin d'être passée** : `patches-14-v3` est le
  **défaut** depuis `EPIC5-ARB-67`, tranché le 2026-08-12. Ce jeu porte 14 valeurs
  en double réplicat, soit 28 pastilles, 14 par côté, et ses **8 sentinelles de
  gamut**.

  **Pourquoi ce défaut a changé, parce que le savoir évite de reproduire l'erreur.**
  L'ancien défaut `patches-12-v1` est épinglé sur `patch-values-1`, dont
  `sentinel_chains` rend un jeu **vide** : une planche composée sans option ne
  portait **aucune sentinelle de gamut**, donc le verdict d'écrêtage était
  inatteignable sur les cinq axes de ce qui s'imprime réellement. Elle portait en
  outre les trois **secondaires** que l'AC 7 de la story 5.16 interdit sur une
  planche d'images. Le défaut produisait donc la seule configuration où la
  calibration ne peut pas fonctionner. Les deux presets v1 restent résolvables :
  les planches déjà imprimées sous eux restent relisibles ;
* **`--frames-par-page`** : le vocabulaire **dépend de l'orientation** depuis
  `EPIC5-ARB-64` — portrait `1, 2, 3, 4, 8` et paysage `1, 2, 4, 6, 8`. Un
  cardinal retiré est refusé avec son motif chiffré et le cardinal à employer à la
  place ;
* **`--marge`** (0, 2 ou 5 mm) est le préset de recadrage, relu au scan depuis le
  QR ; **`--dpi`** (défaut 600) ne concerne que la rastérisation des éléments
  embarqués, pas la consigne de scan.

Sortie vérifiée sur le lot de test : `8 page(s)` pour 13 frames à 2 par page —
**7 planches d'images plus la page de calibration**. La page 1 porte les
**130 pastilles** du treillis et aucune frame ; les pages 2 à 8 portent 2 frames
et 28 pastilles témoins.

Le fichier atterrit sous `mon_projet/planches/<projet>_<rush>_<lot>_planches.pdf`.

## 5. Imprimer, scanner, et réingérer

Consigne rendue par `makepdf` lui-même : **scanner à 600 dpi minimum**.

```bash
python -m mixed_media_utility.cli scan \
    --project mon_projet \
    --scan <dossier-ou-image-ou-pdf> \
    --dpi 600 \
    --lot-slug essai_01
```

* `--dpi` est **obligatoire** et n'est jamais devinée ; sur un PDF elle pilote le
  rendu ;
* `--lot-slug` est un nom de dossier **opérateur**, pas un `lot_id` : l'identité
  métier du lot est portée par le QR et n'est connue qu'au décodage ;
* `scan` est une commande **unique de bout en bout** depuis la story 5.7 :
  ingestion → détection ArUco et décodage QR → recadrage → écriture des frames
  rescannées → mise à jour du manifest.

### Tester la boucle **sans imprimante**

`--scan` accepte un **PDF multipage**. On peut donc réingérer le PDF que
`makepdf` vient d'écrire, ce qui exerce toute la chaîne sans papier — utile pour
valider les commandes avant d'engager un tirage :

```bash
python -m mixed_media_utility.cli scan \
    --project mon_projet \
    --scan mon_projet/planches/<...>_planches.pdf \
    --dpi 600 --lot-slug essai_boucle
```

Vérifié : **8 pages ingérées, 13 frames reconstruites, 0 de remplacement, lot
complet**, et depuis la story 5.19 la ligne de journal

> Correction du lot ajustee sur la page de calibration TEST_FILE_12p5-p0 (forme
> color-correction-affine-matrix-1, 130 pastille(s) lue(s), 130 retenue(s)).

Ce test ne dit évidemment **rien** de la robustesse à l'impression — il n'y a ni
encre, ni papier, ni dérive d'échelle. Il valide la géométrie, le décodage QR, le
nommage, et le **câblage** de la correction. Sur sa colorimétrie, voir l'encadré
« le piège de la boucle sans imprimante » en tête de document : la correction
ajustée y est l'identité exacte, par construction.

### Les avertissements attendus, et ce qu'ils veulent dire

* `DPI_DECLARED_DIFFERS_FROM_FILE` — le dpi déclaré ne correspond pas à celui
  inscrit dans le fichier. Normal sur un PDF rendu ;
* `INGEST_SLUG_DIFFERS_FROM_LOT_ID` — le slug opérateur diffère du `lot_id` lu au
  QR. Normal, et c'est précisément la distinction que `--lot-slug` documente ;
* `PAGE_SLOT_COUNT_BELOW_TEMPLATE` — une page porte moins d'emplacements que son
  gabarit. **Attendu depuis la story 5.16** : c'est la page de calibration, qui
  n'en porte aucun.

### Si une page est refusée pour divergence colorimétrique

> **Levée du 2026-08-12, story 5.19.** Cette section portait un avertissement
> disant qu'elle décrivait un comportement inexistant : la garde de divergence
> n'était atteinte par aucun chemin de production, et le drapeau ci-dessous n'avait
> aucun effet observable alors qu'il était visible dans `--help`. La story 5.19 a
> câblé l'appelant qui manquait, et les deux sont désormais exercés de bout en bout
> par la CLI — refus **et** contournement.

Une page peut s'écarter de la page de calibration du lot au-delà d'un seuil
enregistré. Le refus **nomme la page** et non le lot, et porte trois nombres :
l'excès de résidu mesuré, le seuil, et le résidu que la page obtiendrait sous sa
propre correction — le troisième distingue « cette page dérive » de « ce papier est
bruyant ». Les frames de la page refusée sont **écrites non corrigées**, et le
manifest le déclare : le reste du lot garde sa correction. Deux gestes sont
possibles :

1. **rescanner cette page précisément**, ce que le message demande par défaut ;
2. **passer outre explicitement** :

```bash
python -m mixed_media_utility.cli scan ... \
    --appliquer-la-correction-de-calibration-telle-quelle
```

Ce drapeau applique la correction de la page de calibration **telle quelle**. Rien
ne l'active tout seul, il ne ré-ajuste rien, et le manifest porte la trace du
contournement avec l'écart qui l'a motivé. Vérifiable au manifest : la page
contournée déclare la **même** forme de correction et la **même** page source que
ses voisines, jamais elle-même.

**Ce que ce drapeau ne franchit pas, et sa fenêtre utile est étroite.** Il ne lève
que la garde de **divergence** (seuil 1,0 dE76 d'excès de résidu) — jamais le
plafond d'acceptation `color-acceptance-1` (~8,0 dE76). Mesuré par la revue de
5.19 sur un lot déviant réel (excès 10,48 dE76) : la page contournée ressort quand
même `failed / acceptance_metric_failed`, et le drapeau ne change **rien** à ce
verdict. Le contournement n'est donc effectif que sur des pages dont l'excès de
résidu se situe dans la fenêtre `]1,0 ; ~8,0[` dE76 — au-delà, le plafond
d'acceptation refuse la page quel que soit le drapeau, et le geste qui répond
reste le rescan de cette feuille.

### Ce que le manifest déclare, page par page

`reconstruction.page_calibration_results` porte une entrée par page du lot, et
chaque entrée ne porte **que** les champs suivants — jamais de champ de motif en
texte libre :

* la **page de calibration**, quand son ajustement réussit, déclare `not_applied`,
  `correction_source: own_sheet_patches` et son propre identifiant : la
  correction du lot vient de ses pastilles, et aucun de ses pixels n'est
  corrigé — elle ne porte pas de frame. Quand son ajustement **échoue** — QR lu,
  rôle de calibration connu, mais treillis illisible ou implausible —, elle
  déclare `failed` avec son propre motif (vocabulaire fermé) ;

  > **Distinction supplémentaire, tranchée par `EPIC5-ARB-70` et câblée par la
  > passe de correction de 5.19.** Une page de calibration dont le QR est lu — le
  > rôle `c` est donc **connu** — mais dont la géométrie ne se résout pas (coin
  > corné, marqueur d'angle abîmé) déclare `failed`, avec le motif
  > `calibration_page_geometry_unresolved` et un message qui nomme **cette**
  > feuille à rescanner. Elle sortait auparavant `not_applied` sous le message
  > « aucune page de calibration lue », ce qui était trompeur : le rôle n'était
  > pas inconnu, il était perdu, et l'opérateur allait chercher une feuille
  > absente. Quand le **QR lui-même** est illisible, le rôle est inconnaissable :
  > le lot reste `not_applied` et le message « aucune page de calibration lue »
  > est alors vrai à la lettre.

* chaque **planche d'images** corrigée déclare `applied`, `correction_source:
  lot_calibration_page`, l'identifiant de la page source, et son bloc
  `divergence` avec ses trois nombres ;
* une planche **refusée** déclare `failed`, avec le même bloc `divergence` **et
  son motif** : `failure_reason` porte le mot du vocabulaire fermé qui a fait
  refuser la page. Ce champ n'y était pas avant la passe de correction de 5.19 —
  une page refusée disait `failed` sans dire pourquoi, et le motif ne vivait que
  dans la console (« Page N refusee: ... ») et dans `logs/scan.log`. Le **message**
  reste, lui, propre au journal : le manifest porte le motif, pas sa phrase.

### Où lire le statut de la correction, et à quelle échelle

Trois échelles, et elles ne disent pas la même chose. C'est le point qui a coûté
un faux succès à la revue de 5.19 : lire la mauvaise échelle fait croire qu'un
master est corrigé quand il ne l'est pas.

| échelle | où | ce que ça dit |
|---|---|---|
| **page** | `reconstruction.page_calibration_results[]` | ce que **cette feuille** a produit, avec sa provenance et, sur un échec, son motif |
| **lot** | `lots[].color_calibration_status` | ce que la passe a mesuré **sur ce lot**. C'est ce que lit `encode`, et c'est l'échelle du master. **Absent = `not_applied`** : un lot qui n'a jamais eu de page de calibration ne porte pas le champ, ce qui garantit qu'un projet d'avant la calibration reste identique octet à octet |
| **projet** | `color.color_calibration_status` | « au moins un lot de ce projet porte une correction active ». Monotone, informatif, et **jamais** lu pour décider ce qu'un master contient |

```bash
python - <<'PY'
import json, pathlib
m = json.loads(pathlib.Path("mon_projet/project.json").read_text())
print("projet :", m.get("color", {}).get("color_calibration_status"))
for lot in m["lots"]:
    print("lot", lot["lot_id"], ":", lot.get("color_calibration_status", "(absent -> not_applied)"))
for e in m["reconstruction"]["page_calibration_results"]:
    print("  page", e["page_index"], e["status"], e.get("failure_reason", ""))
PY
```

## 6. Comparer plusieurs formes de correction (banc de recherche)

La chaîne applique désormais la correction : la comparaison « avec / sans » se fait
donc en scannant le même lot avec puis sans sa page de calibration. Le banc
ci-dessous garde un autre usage, qu'aucune commande ne couvre — **comparer
plusieurs formes** de correction entre elles et voir un avant/après côte à côte.

```bash
PYTHONPATH=src:scripts/research python3 scripts/research/preview_color_correction.py \
    --scan <scan-des-planches.pdf> --pages 8 \
    --preset patches-14-v3 --images --models
```

* **`--images`** ajuste la correction sur les pastilles **réellement imprimées et
  rescannées** de chaque page, l'applique aux **zones de frames** de la même page,
  et écrit un **avant / après côte à côte**. C'est la comparaison visuelle
  demandée ;
* **`--models`** compare plusieurs formes de correction en **validation
  croisée**. Ne jamais le lancer seul : la croisée ne voit pas
  l'**extrapolation**, et un modèle riche gagne d'un facteur deux en croisé tout
  en rendant une image visiblement fausse — 8,3 % des pixels d'une frame sont hors
  du domaine d'ajustement, les pastilles n'y sont jamais ;
* **`--cross-pages`** mesure le transport d'une correction d'une page à l'autre du
  même tirage (mesuré à +0,02 dE76 pour la forme Lab).

Ce banc est **hors production** : il ne persiste rien et n'écrit aucun manifest.

## 7. Encoder le master

```bash
python -m mixed_media_utility.cli encode \
    --project mon_projet \
    --lot <lot_id> \
    --profile prores_hq \
    --resolution native \
    --yes
```

* `--profile` : `prores_hq` par défaut (master mezzanine acté par
  l'architecture) ; aussi `prores_422`, `prores_lt`, `dnxhr_hq`, `dnxhr_hqx`,
  `h264_delivery`, `hevc_delivery` ;
* `--resolution` : `hd1080` par défaut, `uhd2160`, `native` pour la géométrie des
  frames rescannées, ou `<largeur>x<hauteur>` ;
* `--accept-incomplete-lot` encode un lot définitivement incomplet (planche
  perdue, jamais rescannée). Le récapitulatif déclare alors l'incomplétude —
  **aucun trou n'est jamais comblé par répétition de l'image précédente**.

Sortie vérifiée : `outputs/<lot>_mmu_<profil>_<résolution>.mov`, 13 frames à
25/2 im/s, `yuv422p10le`. Le récapitulatif nomme la cadence, le compte de frames
conformes, le nombre de **mires** (frames de remplacement de synthèse), le
timecode, le poids majorant, et **deux** lignes de colorimétrie — l'approximation
de courbe de transfert, et ce que la correction active a fait. Voir l'encadré de
tête pour leur texte exact et pour ce qui distingue les deux.

## 8. Deux choses à savoir, trouvées en vérifiant ce document

1. **L'aide de `--nombre-patchs` était périmée ; elle a été corrigée.** Elle
   affirmait que « seul `patches-18-v2` porte les sentinelles de gamut ». C'était
   faux depuis la story 5.16 : `patches-14-v3` porte lui aussi ses **8
   sentinelles**. L'aide est désormais **entièrement dérivée du registre** — les
   identifiants, leurs cardinaux, le défaut, les presets à sentinelles, et le
   couple qui n'est pas composable en paysage v2 — donc elle ne peut plus se
   périmer sans que le registre bouge.
2. **Les 10 tests ignorés de la suite sont normaux et documentés.** Ils portent
   tous sur le couple `paysage × patches-18-v2`, arithmétiquement infaisable :
   18 rangées de 6 mm au pas de 9 exigent 159 mm quand le couloir latéral d'une
   page paysage v2 en offre 151. Le refus le dit lui-même, et l'ensemble de ces
   couples est épinglé **exactement** par un test qui échoue si la liste grandit
   *ou* rétrécit en silence.
