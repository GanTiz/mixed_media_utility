# Tester la chaîne complète : extract → makepdf → scan → encode

Document manuel. Toutes les commandes ci-dessous ont été **exécutées et vérifiées
le 2026-08-12** contre l'état du dépôt après les stories 5.15, 5.17, 5.18 et 5.16
(cette dernière encore en `review`). Elles complètent
`test-chaine-extract-makepdf.md` et `test-chaine-scan-epic5.md`, qu'elles ne
remplacent pas : ce document ajoute **`encode`**, la **page de calibration** de la
story 5.16, et répond à la question « avec et sans retouche colorimétrique ».

## La réponse courte sur la colorimétrie, à lire avant tout le reste

**La chaîne ne sait aujourd'hui produire que la branche « sans retouche ».** Ce
n'est pas un réglage à trouver : la calibration active est post-MVP
(`EPIC5-ARB-5`), `color_calibration_status` vaut **invariablement `not_applied`**,
et `encode` l'écrit dans son propre récapitulatif :

> Approximation assumée : les valeurs viennent d'un scanner, donc sRGB de fait, et
> le master est tagué bt709. […] **le MVP n'applique aucune correction
> colorimétrique active.**
> Constat : `APPROXIMATION_SRGB_TAGUEE_REC709`

Ce que la story 5.16 a livré, c'est **tout ce qui précède l'application** : la
seconde forme de correction et ses gardes, la page de calibration imprimée, le
rôle de page au payload QR, le seuil de divergence, le contournement explicite et
le champ de provenance au manifest. Ce qui manque est **un seul branchement** :
aucun appelant ne construit encore de `PageCalibration` dans `scan_command`, donc
la correction calculable n'est pas appliquée aux frames. C'est la réserve nommée
de l'AC 10, consignée au `deferred-work.md`.

**La comparaison avec / sans est donc mesurable aujourd'hui, mais pas par la
chaîne** : elle se fait par le banc de recherche de la section 6, qui ajuste sur
les pastilles réellement imprimées et écrit un avant/après côte à côte.

## 0. Prérequis

Depuis la racine du dépôt. Aucun script `mixed-media-util` n'est installé : tout
passe par `python -m`.

```bash
export PYTHONPATH="$PWD/src"
```

`ffmpeg` et `ffprobe` doivent être présents (`extract` et `encode` en dépendent).

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
    --nombre-patchs 14 \
    --frames-par-page 2 \
    --orientation portrait
```

Ce qu'il faut savoir sur chaque option :

* **`--geometrie v2`** est le défaut depuis la story 5.18. C'est **elle qui ajoute
  la page de calibration** : la v1 ne peut pas en porter une (son dégagement de
  coin de 60 mm ne laisse que 57 à 66 cellules pour les 130 pastilles du
  treillis), et un lot v1 se compose donc exactement comme avant. Vérifié : le
  même lot rend **5 pages en v1 et 6 en v2**, la page ajoutée étant la première ;
* **`--nombre-patchs 14`** sélectionne `patches-14-v3`, le jeu témoin de la story
  5.16 : 14 valeurs en double réplicat, soit 28 pastilles, 14 par côté. **Ce
  n'est pas le défaut** — le défaut reste `patches-12-v1`. Sans cette option, les
  planches portent 24 pastilles et non 28 ;
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
complet**. Ce test ne dit évidemment **rien** de la colorimétrie ni de la
robustesse à l'impression — il n'y a ni encre, ni papier, ni dérive d'échelle. Il
valide la géométrie, le décodage QR et le nommage.

### Les avertissements attendus, et ce qu'ils veulent dire

* `DPI_DECLARED_DIFFERS_FROM_FILE` — le dpi déclaré ne correspond pas à celui
  inscrit dans le fichier. Normal sur un PDF rendu ;
* `INGEST_SLUG_DIFFERS_FROM_LOT_ID` — le slug opérateur diffère du `lot_id` lu au
  QR. Normal, et c'est précisément la distinction que `--lot-slug` documente ;
* `PAGE_SLOT_COUNT_BELOW_TEMPLATE` — une page porte moins d'emplacements que son
  gabarit. **Attendu depuis la story 5.16** : c'est la page de calibration, qui
  n'en porte aucun.

### Si une page est refusée pour divergence colorimétrique

La story 5.16 ajoute un refus quand une page s'écarte de la page de calibration du
lot, au-delà d'un seuil enregistré. Le refus **nomme la page** et non le lot, et
porte trois nombres : l'excès de résidu mesuré, le seuil, et le résidu que la page
obtiendrait sous sa propre correction — le troisième distingue « cette page
dérive » de « ce papier est bruyant ». Deux gestes possibles :

1. **rescanner cette page précisément**, ce que le message demande par défaut ;
2. **passer outre explicitement** :

```bash
python -m mixed_media_utility.cli scan ... \
    --appliquer-la-correction-de-calibration-telle-quelle
```

Ce drapeau applique la correction de la page de calibration **telle quelle**. Rien
ne l'active tout seul, il ne ré-ajuste rien, et le manifest porte la trace du
contournement avec l'écart qui l'a motivé.

## 6. Comparer avec et sans retouche colorimétrique

C'est ici que passe la comparaison, puisque la chaîne n'applique pas encore la
correction (voir l'encadré du début).

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
timecode, le poids majorant, et le constat colorimétrique.

## 8. Deux choses à savoir, trouvées en vérifiant ce document

1. **L'aide de `--nombre-patchs` est périmée.** Elle affirme que « seul
   `patches-18-v2` porte les sentinelles de gamut, requises par le verdict
   d'écrêtage ». C'est faux depuis la story 5.16 : `patches-14-v3` porte lui aussi
   ses **8 sentinelles** (vérifié à l'exécution). Suivre l'aide conduirait à
   choisir le mauvais préset — et `patches-18-v2` n'a **aucun placement en
   paysage** sous la v2.
2. **Les 10 tests ignorés de la suite sont normaux et documentés.** Ils portent
   tous sur le couple `paysage × patches-18-v2`, arithmétiquement infaisable :
   18 rangées de 6 mm au pas de 9 exigent 159 mm quand le couloir latéral d'une
   page paysage v2 en offre 151. Le refus le dit lui-même, et l'ensemble de ces
   couples est épinglé **exactement** par un test qui échoue si la liste grandit
   *ou* rétrécit en silence.
