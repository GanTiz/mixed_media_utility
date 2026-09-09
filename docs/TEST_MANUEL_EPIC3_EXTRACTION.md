# Manuel de test — Epic 3: previsualisation et extraction de frames

Ce document decrit un workflow complet **de A a Z**, a executer soi-meme, depuis un rush
brut jusqu'a un lot de frames TIFF verifie, en passant par la previsualisation multi-cadence
qui sert a **choisir** la cadence avant d'extraire.

Il couvre les deux commandes livrees par l'Epic 3:

- `previz` (story 3.6) — lire un rush a une ou plusieurs cadences reduites, sans rien ecrire;
- `extract` (stories 3.1 a 3.4) — produire un lot de frames TIFF deterministe et l'inscrire
  au manifest.

Les autres livrables de l'Epic 3 (story 3.2 selection, 3.3 confirmation, 3.4 manifest,
3.5 contrat de previz d'extraction) n'ont pas de commande propre: ils s'observent a travers
`extract`, aux endroits signales ci-dessous.

---

## 0. Prerequis

- `ffmpeg` et `ffprobe` sur le `PATH` (`ffprobe -version` doit repondre);
- les dependances Python du depot (`pip install -r requirements.txt`);
- pour la fenetre de previsualisation: un affichage disponible (Windows/macOS: rien a faire;
  Linux sans ecran: voir la section 3.5).

Toutes les commandes ci-dessous sont donnees en PowerShell, comme le manuel du POC.
Le prefixe est:

```powershell
.\.venv\Scripts\python.exe -m mixed_media_utility.cli <sous-commande> ...
```

Sous Linux / macOS, depuis la racine du depot:

```bash
PYTHONPATH=src python -m mixed_media_utility.cli <sous-commande> ...
```

Dans la suite, ce prefixe est note `mmu`.

---

## 1. Fabriquer un rush de test (optionnel)

Si vous voulez un rush court et reproductible plutot qu'un vrai rush:

```powershell
ffmpeg -y -f lavfi -i testsrc=size=1280x720:rate=25:duration=8 -c:v libx264 -pix_fmt yuv420p rush_demo.mp4
```

Ce rush fait 8 s a 25 im/s, soit 200 frames source. Un vrai rush convient tout aussi bien:
les commandes sont identiques.

---

## 2. Etape 1 — Arbitrer la cadence avec `previz`

`previz` **ne connait pas la notion de projet**: pas de `--project`, aucune arborescence
creee, aucun journal, aucun manifest, aucune frame ecrite nulle part. C'est un outil de
lecture, pas de production.

### 2.1 Comparer trois cadences en une seule session

```powershell
mmu previz --video rush_demo.mp4 --fps 3 --fps 5 --fps 12.5
```

Ce qui doit se passer:

- une fenetre s'ouvre et le rush est **lu en temps reel** a 3 im/s, en ne montrant que les
  frames que `extract --fps 3` retiendrait — jamais une frame ecartee;
- chaque image porte une incrustation sur une seule ligne:

  ```
  00:00:02:08  idx 58/200   ->   8/24   3/3 im/s
  ```

  - a gauche: le timecode de la frame et sa position dans le **rush source entier**
    (base zero, convention `n` de ffmpeg);
  - a droite de la fleche: le rang de cette image dans le **lot** que `extract` produirait
    (base un, lisible par un humain), puis la cadence de lecture mesuree sur la cadence
    cible;
  - la cadence est **verte** tant que la lecture tient la cible, **rouge** des qu'elle
    decroche de plus de 2 %. C'est la seule information coloree: c'est la seule qui peut se
    degrader.

- a la fin de la passe, la lecture s'arrete sur la derniere image et attend une touche.

### 2.2 Naviguer au clavier

Pendant et entre les passes:

| Touche | Effet |
|---|---|
| `n` | cadence suivante |
| `p` | cadence precedente |
| `r` | rejouer la cadence courante |
| `q` (ou `Echap`) | quitter |

Ce qu'il faut verifier: passer de 3 a 5 puis revenir a 3 **ne rouvre pas le fichier** et ne
recalcule rien. Le compteur final indique combien de frames ont ete servies par le cache
memoire.

### 2.3 Restreindre la plage affichee

```powershell
mmu previz --video rush_demo.mp4 --fps 5 --start 2 --duration 3
```

`--start` / `--duration` restreignent **l'affichage**, jamais la selection: le rang affiche
a droite de la fleche reste le rang dans le lot complet, pas dans la plage vue.

Ne pas les confondre avec `--in` / `--out` (sections 2.4 et 3.6), qui changent, eux, **quelles
images sont retenues**. Les deux paires se combinent: on peut previsualiser un extrait
(`--in` / `--out`) et n'en jouer qu'une portion (`--start` / `--duration`).

### 2.4 Previsualiser un extrait, pas le rush entier

```powershell
mmu previz --video rush_demo.mp4 --fps 5 --in 00:00:02:00 --out 00:00:05:24
```

`--in` / `--out` designent ici **exactement** ce qu'ils designent sur `extract`: les images
retenues sont les memes des deux cotes, sur le meme rush avec les memes bornes. C'est ce
qui permet d'arbitrer une cadence sur l'extrait qu'on va reellement extraire.

Le compteur `idx X/Y` en bas a gauche continue de situer l'image dans le **rush entier**
(`idx 100/500`), pas dans l'extrait: on garde son repere dans le rush d'origine. C'est le
groupe de droite qui compte dans le lot.

### 2.5 Regler l'affichage et la memoire

```powershell
mmu previz --video rush_demo.mp4 --fps 5 --height 720 --memory-budget-mb 1024
```

- `--height` (defaut 540) est pose **avant** la lecture: la resolution ne change jamais en
  cours de passe;
- `--memory-budget-mb` (defaut 512) borne le cache de frames decodees. Le cache est une
  optimisation, jamais une condition de justesse: une eviction est signalee par le code
  `CACHE_EVICTED` et n'altere pas la sequence presentee.

### 2.6 Lire sans fenetre (machine sans ecran, integration continue)

```powershell
mmu previz --video rush_demo.mp4 --fps 3 --fps 5 --no-display
```

Rien ne s'affiche, mais la lecture est reellement cadencee et mesuree. C'est le mode qui
permet de verifier les chiffres sans ecran.

Sous Linux sans affichage, la fenetre reste testable via un ecran virtuel:

```bash
Xvfb :99 -screen 0 1280x800x24 &
DISPLAY=:99 PYTHONPATH=src python -m mixed_media_utility.cli previz --video rush_demo.mp4 --fps 3
```

### 2.7 Lire le rapport de fin

Chaque cadence produit un bloc de ce type:

```
Cadence 3 im/s
  frames presentees   : 24 / 24 attendues
  frames omises       : 0
  retard max / median / p95 : 1.7 / 0.2 / 0.2 ms
  derive finale       : 0.2 ms (duree nominale 7.640 s, reelle 7.640 s)
  amorcage            : 17.8 ms (decodage jusqu'a la premiere frame presentee, hors cadencement)
  cadence effective   : 3.010 im/s
  frames en retard    : 0.00 % (seuil 20 ms par frame)
  temps reel          : tenu
```

Points a verifier:

- `frames presentees == frames attendues` en mode par defaut: **aucune frame n'est sautee en
  silence**;
- `temps reel : tenu` si moins de 1 % des frames depassent 20 ms de retard et si la derive
  finale reste sous 2 % de la duree nominale;
- un `temps reel : NON TENU` **n'est pas un echec**: le code de sortie reste `0`. L'ecart est
  mesure et rapporte, pas subi.

### 2.8 Comportement en cas de retard

```powershell
mmu previz --video rush_demo.mp4 --fps 12.5 --height 1080 --on-late skip
```

- `--on-late report` (defaut): toutes les frames retenues sont presentees, la lecture
  s'allonge, l'ecart est chiffre et le code `REALTIME_NOT_HELD` apparait;
- `--on-late skip`: les frames dont l'echeance est deja passee sont omises pour preserver le
  tempo percu. Le compte des frames omises est chiffre **dans le rapport final**, avec le
  code `FRAMES_SKIPPED` et la mention explicite que la sequence vue n'etait pas la selection
  complete. L'incrustation a l'ecran, elle, ne change pas: elle garde ses trois zones fixes.

### 2.9 Verifier qu'aucun fichier n'a ete ecrit

Apres n'importe quelle session `previz`, l'arborescence doit etre strictement inchangee:

```powershell
Get-ChildItem -Recurse | Measure-Object
```

La derniere ligne de `previz` le rappelle: *« Aucun fichier ecrit, aucun lot cree, aucune
extraction declenchee. »* Une previsualisation **n'autorise rien**: elle ne vaut pas
confirmation d'extraction, ne cree ni lot ni entree de manifest.

Un `Ctrl+C` en cours de lecture s'arrete proprement, sans trace Python, et le rapport est
alors marque `LECTURE PARTIELLE`.

---

## 3. Etape 2 — Extraire le lot avec `extract`

Une fois la cadence choisie, la meme cadence passee a `extract` produit **exactement** les
frames vues en previsualisation.

### 3.1 Extraction interactive (le chemin nominal)

```powershell
mmu extract --project .\projet_demo --video rush_demo.mp4 --fps 3
```

La commande **s'arrete avant d'ecrire quoi que ce soit** et affiche un rapport de
confirmation (story 3.3). Trois blocs a lire:

1. **Source lue par ffprobe** — resolution de stockage et d'affichage, codec, format de
   pixel, profondeur, rapport de pixel, primaires / gamma / matrice / plage couleur, cadence
   source, timecode de depart. Aucune valeur par defaut n'est substituee: ce qui est absent
   de la source est ecrit `non renseigne (absent de la source)`.
2. **Selection deterministe** — nombre de frames qui seront extraites, frames source non
   retenues en fin de rush, premier et dernier timecode de la selection.
3. **Sortie** — dossier de lot, et une borne haute d'occupation disque (`largeur x hauteur x
   3 canaux x 2 octets x nombre de frames`; la compression n'est pas modelisee, l'occupation
   reelle sera plus faible).

Repondre `o`, `oui`, `y` ou `yes` lance l'extraction; toute autre reponse l'annule, sans rien
ecrire.

**A verifier ici:** le nombre de frames annonce est identique a celui qu'affichait `previz`
pour la meme cadence.

### 3.2 Extraction non interactive

```powershell
mmu extract --project .\projet_demo --video rush_demo.mp4 --fps 3 --yes
```

`--yes` vaut consentement general. Si la colorimetrie source est incomplete (cas frequent
d'un rush non tague), la commande **refuse quand meme** et le dit:

```
Confirmation non accordee: la colorimetrie source est absent et exige un consentement
supplementaire explicite. Passer --accept-unknown-color en plus de --yes.
```

Il faut alors un second consentement, explicite et distinct:

```powershell
mmu extract --project .\projet_demo --video rush_demo.mp4 --fps 3 --yes --accept-unknown-color
```

C'est voulu: le MVP n'applique aucune correction couleur, et ce qui est absent ici le
restera dans le manifest.

### 3.3 Ce qui est produit

```
projet_demo/
  frames/
    rush_demo_3/
      rush_demo_3_00-00-00-00.tiff
      rush_demo_3_00-00-00-16.tiff
      ...                              (24 fichiers pour 8 s a 3 im/s)
  logs/
    extract.log
  project.json
```

- le dossier de lot suit `frames/<rush>_<fps-cible>/`;
- les fichiers suivent `<rush>_<fps-cible>_<timecode>.tiff`, timecode en `HH-MM-SS-FF`;
- les TIFF sont en **16 bits**;
- **aucun doublon, aucune interpolation**: chaque fichier est une frame reellement presente
  dans la source.

### 3.4 Verifier le lot et le manifest (story 3.4)

Le manifest `project.json` doit permettre a un tiers de verifier que le lot est complet et
conforme, sans ouvrir une seule image:

```powershell
Get-Content .\projet_demo\project.json | ConvertFrom-Json | Select-Object -ExpandProperty lots
```

Champs a controler:

| Champ | Ce qu'il doit dire |
|---|---|
| `lot_id`, `frames_dir` | `rush_demo_3`, `frames/rush_demo_3` |
| `expected_frame_count` | 24 — a comparer au nombre reel de `.tiff` du dossier |
| `fps_target` / `fps_target_exact` | `3.0` et `3/1` (valeur typee **et** valeur exacte) |
| `first_frame_timecode` / `last_frame_timecode` | bornes de la selection |
| `source_in_timecode` / `source_out_timecode` | bornes **demandees** (section 3.6). Absents des lots non bornes: ils disent l'intention, la ou les deux champs ci-dessus disent la consequence |
| `timecode_base` / `timecode_base_fps` | `source` et `25/1` — les timecodes sont dans la base **source**, jamais dans la base cible |
| `source_frame_count` / `source_frame_count_is_exact` | 200, `true` (comptage exact, pas une estimation) |
| `source_tail_frames` | frames de fin de rush non retenues |
| `rounding_policy` | `floor-index-ceil-count-v1` — la politique d'arrondi est nommee, pas implicite |
| `selection_warnings` | ex. `NON_DIVISIBLE_RATES` pour 25 -> 3 |
| `frame_timecodes_digest` | empreinte `sha256-v1:...` de la liste des timecodes |
| `confirmation` | `mode`, `unknown_color_accepted`, `confirmed_at` |
| `state` | `extraction` |

Cote rush, le bloc `rushes` porte `fps_source`, `resolution_source`, `source_codec`,
`source_pix_fmt`, `source_bit_depth`, et surtout `source_metadata_absent_fields`: la liste
de ce que la source **ne disait pas**, conservee telle quelle.

Verification croisee rapide:

```powershell
(Get-ChildItem .\projet_demo\frames\rush_demo_3\*.tiff).Count
```

Ce nombre doit etre egal a `expected_frame_count`.

### 3.5 Un lot par cadence

```powershell
mmu extract --project .\projet_demo --video rush_demo.mp4 --fps 5 --yes --accept-unknown-color
```

Produit `frames/rush_demo_5/` **a cote** du precedent, et une seconde entree dans `lots`.
Les deux lots coexistent: la cadence fait partie de l'identite du lot.

### 3.6 N'extraire qu'un extrait, borne par timecodes (story 3.7)

Un rush trop long pour tenir sous le plafond de 1000 images n'oblige pas a baisser la
cadence: on peut n'extraire qu'une portion, a cadence intacte.

```powershell
mmu extract --project .\projet_demo --video rush_demo.mp4 --fps 5 --in 00:00:02:00 --out 00:00:05:24 --yes --accept-unknown-color
```

Trois points a controler:

1. **Le timecode est celui du rush, pas un decalage depuis son debut.** Un rush qui
   demarre a `01:00:00:00` se borne avec des timecodes en `01:00:...`, et un rush tourne
   en heure du jour (`15:34:17:20`) avec ses timecodes d'horloge. C'est le meme timecode
   que celui affiche par `previz` et que celui des noms de fichiers.
2. **Le rapport de confirmation annonce l'extrait avant son compte.** Deux lignes
   apparaissent au-dessus de `expected_frame_count`:

   ```
   Borne d'entree demandee (--in)      : 00:00:02:00 (base source, cadence 25/1)
   Borne de sortie demandee (--out)    : 00:00:05:24 (base source, cadence 25/1)
   ```

   Sur une extraction complete, ces deux lignes n'apparaissent pas du tout.
3. **L'extrait ne touche pas l'extraction complete.** Le dossier porte un condensat de
   bornes (`frames/rush_demo_5-a1b2c3d4/`) et le lot une entree distincte dans `lots`.
   Les deux coexistent, comme deux cadences coexistent.

Les deux bornes sont independantes: `--in` seul va jusqu'a la fin du rush, `--out` seul
part de sa premiere image.

A essayer aussi:

| Ce qu'on tente | Ce qui doit se passer |
|---|---|
| `--in` posterieur a `--out` | refus nommant les deux bornes et la plage reelle du rush |
| `--out` au-dela de la fin du rush | refus nommant le dernier timecode valide |
| une borne malformee (`--in 12:34`) | refus nommant `source_in_timecode` |
| un nom de fichier source de plus de 37 caracteres | refus invitant a renommer le fichier: au-dela, l'identifiant du lot et le nom de son dossier divergeraient |

### 3.7 Ne jamais ecraser un lot par accident

Relancer la meme cadence sur un lot deja present echoue:

```
Un lot est deja present dans frames/rush_demo_3 et ne sera pas efface implicitement.
Relancer avec --overwrite pour le remplacer, ou choisir une autre cadence cible.
```

Le remplacement est toujours explicite:

```powershell
mmu extract --project .\projet_demo --video rush_demo.mp4 --fps 3 --yes --accept-unknown-color --overwrite
```

---

## 4. Cas d'erreur a essayer

| Ce qu'on tente | Ce qui doit se passer | Code |
|---|---|---|
| `--fps 50` sur un rush a 25 im/s | refus de sur-echantillonnage, avec la cadence maximale admissible | 1 |
| Fichier video inexistant | erreur d'entree lisible, aucune trace Python | 1 |
| Lot deja present sans `--overwrite` | refus explicite | 1 |
| Repondre autre chose que `o` a la confirmation | annulation, aucun fichier ecrit, **aucun prefixe `Erreur:`** | 3 |
| `--yes` sans `--accept-unknown-color` sur un rush non tague | refus de consentement | 3 |
| `ffprobe` retire du `PATH` | prerequis externe absent | 2 |
| `previz` sans affichage disponible et sans `--no-display` | prerequis externe absent, avec la suggestion `--no-display` | 2 |

Codes de sortie, communs aux deux commandes:

- `0` succes (y compris `previz` avec un temps reel non tenu);
- `1` erreur d'entree ou de traitement;
- `2` prerequis externe absent (`ffmpeg`, `ffprobe`, affichage);
- `3` refus de confirmation — propre a `extract`. Rien n'a echoue: l'operateur a dit non.

---

## 5. Verification de bout en bout, en une passe

Le scenario complet, tel qu'il devrait s'enchainer en usage reel:

```powershell
# 1. arbitrer la cadence, sans rien ecrire
mmu previz --video rush_demo.mp4 --fps 3 --fps 5 --fps 12.5

# 2. extraire la cadence retenue, apres confirmation a l'ecran
mmu extract --project .\projet_demo --video rush_demo.mp4 --fps 5

# 3. verifier que le lot est complet
(Get-ChildItem .\projet_demo\frames\rush_demo_5\*.tiff).Count
Get-Content .\projet_demo\project.json | ConvertFrom-Json | Select-Object -ExpandProperty lots

# 4. verifier que la previsualisation n'a laisse aucune trace
#    (aucun dossier cree par l'etape 1, seul le projet de l'etape 2 existe)
```

Le point de jonction a controler: **le nombre de frames annonce par `previz` a une cadence
donnee doit etre exactement celui que `extract` produit a cette meme cadence.** C'est la
promesse centrale de l'Epic 3; si les deux nombres different, c'est un defaut a signaler.

---

## 6. Lancer la suite de tests automatises

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

L'environnement doit avoir `ffmpeg`, `ffprobe` et (sous Linux) `Xvfb` pour que les tests
d'integration reels ne soient pas ignores. La suite ne doit afficher **aucun test ignore**.
