# Tester la chaîne extract (Epic 3) → makepdf (Epic 4)

Document manuel : commandes exactes pour extraire un rush et générer la
planche PDF imprimable, et vérifier ce qui est produit à chaque étape.
Testé et vérifié ligne par ligne (2026-08-07) contre l'état actuel du dépôt.

## 0. Prérequis

Depuis la racine du dépôt (`/home/user/mixed_media_utility` ou l'équivalent
sur ta machine) :

```bash
export PYTHONPATH="$PWD/src"
```

Toutes les commandes ci-dessous utilisent `python -m mixed_media_utility.cli`
(il n'y a pas de script `mixed-media-util` installé — pas de
`pyproject.toml`/`setup.py` avec `console_scripts` dans ce dépôt).

Il te faut un fichier vidéo source. Pour un premier essai rapide, le dépôt en
fournit un :

```bash
mkdir -p /tmp/mmu-test && cd /tmp/mmu-test
cp /home/user/mixed_media_utility/tests/TEST_FILE.mp4 rush-001.mp4
```

(Remplace par ta propre vidéo si tu veux tester avec un vrai rush : n'importe
quel fichier lisible par ffprobe/ffmpeg convient.)

## 1. Étape extract (Epic 3)

```bash
python -m mixed_media_utility.cli extract \
  --project ./mon_projet \
  --video rush-001.mp4 \
  --fps 5 \
  --yes \
  --accept-unknown-color
```

- `--project` : dossier projet, créé s'il n'existe pas.
- `--video` : le rush source.
- `--fps` : cadence cible d'extraction (images/seconde).
- `--yes` : consentement d'extraction sans terminal interactif (sinon la
  commande pose des questions).
- `--accept-unknown-color` : nécessaire si ffprobe ne peut pas déterminer
  totalement la colorimétrie source (fréquent avec des fichiers de test
  synthétiques) — sinon `extract` refuse et demande confirmation.

**Ce que ça produit** (affiché en console, à vérifier) :
- Un résumé de confirmation (résolution, codec, cadence, colorimétrie
  source lue par ffprobe).
- Le compte de frames extraites (`expected_frame_count`) et les timecodes
  premier/dernier de la sélection.
- `N frame(s) TIFF 16 bits ecrite(s) dans frames/<rush>_<fps>`.
- `Manifest mis a jour: lot ... dans mon_projet/project.json`.
- Une ligne d'auto-contrôle, généralement
  `METADONNEES_A_RENSEIGNER_AVANT_ENCODE` (réserve informative — normal à ce
  stade, pas une erreur).

**Vérifications sur disque :**

```bash
ls mon_projet/frames/rush-001_5/          # les TIFF 16 bits nommés
cat mon_projet/project.json | python3 -m json.tool | head -60
```

Points à contrôler dans `project.json` :
- `lots[0].state == "extraction"`
- `lots[0].expected_frame_count` == nombre de fichiers dans `frames/rush-001_5/`
- `lots[0].frames_dir == "frames/rush-001_5"`
- `rushes[0].rush_id == "rush-001"`

## 2. Renseigner `target_colorspace` (souvent nécessaire)

Si le rush n'a pas de colorimétrie source complète (cas des fichiers de
test), `color.target_colorspace` reste absent du manifest — `makepdf` le
refusera avec un message explicite (voir étape 3). Dans un usage réel, cette
valeur devrait être confirmée en amont (Epic 2/3) ; pour un test manuel
rapide :

```bash
python3 -c "
import json
p = 'mon_projet/project.json'
d = json.load(open(p))
d['color']['target_colorspace'] = 'rec709'
json.dump(d, open(p, 'w'), indent=2)
"
```

## 3. Étape makepdf (Epic 4)

```bash
python -m mixed_media_utility.cli makepdf \
  --project ./mon_projet \
  --rush rush-001 \
  --fps 5
```

- `--rush` + `--fps` résolvent le `lot_id` (alternative : `--lot <lot_id>`
  directement, si tu le connais déjà — visible dans `project.json`).
- Sans autre option : format A4 portrait, 2 frames/page, marge 0 mm, DPI 600,
  preset de patchs `patches-12-v1` (les défauts du registre 4.1/4.7).

**Si `target_colorspace` est manquant**, tu verras exactement :
```
color.target_colorspace est absent du manifest: le payload QR exige un
espace couleur cible non vide (contrat 2.3). Renseigner
color.target_colorspace dans project.json avant makepdf (constat
METADONNEES_A_RENSEIGNER_AVANT_ENCODE).
```
→ retour à l'étape 2.

**Ce que ça produit en cas de succès :**
```
PDF ecrit: mon_projet/planches/mon_projet_rush-001_rush-001_5_planches.pdf (N page(s))
makepdf termine avec succes. N page(s) (2 frame(s) par page, template
tpl-a4-portrait-2f-v1, patchs patches-12-v1) dans .../planches.pdf.
Consigne de numerisation: scanner a 600 dpi minimum.
```

**Vérifications :**

```bash
ls -la mon_projet/planches/
```

Le PDF contient, par page : les zones de frames (letterboxées/pilarboxées en
16:9, cf. remarque plus bas), 4 marqueurs ArUco aux coins, un QR de page
(payload de reconstruction), une colonne de patchs de calibration de chaque
côté, un bloc d'identité + pied de page technique.

Pour l'ouvrir visuellement sans visionneuse graphique (l'environnement est
headless), convertir une page en image :

```bash
pdftoppm -png -r 150 -f 1 -l 1 \
  mon_projet/planches/mon_projet_rush-001_rush-001_5_planches.pdf \
  /tmp/mmu-test/page
# -> /tmp/mmu-test/page-1.png
```

## 4. Variantes utiles à tester

```bash
# Paysage, 4 frames par page, marge 5 mm, preset de patchs à 9 valeurs
python -m mixed_media_utility.cli makepdf \
  --project ./mon_projet --rush rush-001 --fps 5 \
  --orientation paysage --frames-par-page 4 --marge 5 --nombre-patchs 9

# Refus explicite si le PDF existe déjà (jamais d'écrasement implicite)
python -m mixed_media_utility.cli makepdf --project ./mon_projet --rush rush-001 --fps 5
# -> erreur ; ajouter --overwrite pour forcer

# Lot direct par lot_id (évite --rush/--fps si tu le connais déjà)
python -m mixed_media_utility.cli makepdf --project ./mon_projet --lot rush-001_5
```

## 5. Nettoyage

```bash
rm -rf /tmp/mmu-test
```

## Repères de code si un comportement surprend

- Résolution du lot / manifest : `src/mixed_media_utility/extraction.py`,
  commande `extract_command` dans `cli.py`.
- Composition de la planche (pure, sans I/O) :
  `src/mixed_media_utility/pdf_composition.py::compose_lot_plan`.
- Rendu reportlab (charge les TIFF, écrit le PDF) :
  `src/mixed_media_utility/pdf_render.py::render_lot_pdf`.
- Commande CLI `makepdf` : `makepdf_command` dans
  `src/mixed_media_utility/cli.py`.
