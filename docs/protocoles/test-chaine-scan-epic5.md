# Tester la chaîne scan (Epic 5) : de la planche imprimée au manifest

Document manuel : commandes exactes pour reprendre la planche PDF produite
par `makepdf` (voir `test-chaine-extract-makepdf.md`), simuler son scan, et
vérifier ce que `scan` écrit sur le disque et dans `project.json`. Testé et
vérifié ligne par ligne (2026-08-09), **rejoué et corrigé le 2026-09-04** après
le renommage des dossiers de la story 11.14 : les sorties gelées ci-dessous
sont celles réellement relevées ce jour-là, pas des sorties recopiées.

**Depuis la story 5.7, `scan` est une commande unique de bout en bout** :
ingestion (5.1) → détection géométrique et décodage QR (5.2) → recadrage
(5.3) → écriture des frames scannées (5.6) → mise à jour du manifest
(5.7). Aucun script de contournement n'est plus nécessaire — une version
antérieure de ce document en fournissait un parce que 5.7 n'était pas encore
développée ; ce n'est plus le cas.

## 0. Prérequis

Depuis la racine du dépôt :

```bash
export PYTHONPATH="$PWD/src"
```

Pas de script `mixed-media-util` installé — toutes les commandes utilisent
`python -m mixed_media_utility.cli`. Pour éviter de retaper le préfixe à
chaque commande, un wrapper (non versionné, à créer une fois sur ta
machine) :

```bash
cat > ~/.local/bin/mmu << 'EOF'
#!/bin/bash
export PYTHONPATH="${PYTHONPATH:-}:/home/user/mixed_media_utility/src"
python -m mixed_media_utility.cli "$@"
EOF
chmod +x ~/.local/bin/mmu
```

(vérifie que `~/.local/bin` est dans ton `PATH`). Les commandes ci-dessous
restent écrites avec `python -m mixed_media_utility.cli` pour rester
copiables telles quelles ; remplace par `mmu` si le wrapper est installé.

## 1. Reprendre depuis extract → makepdf

Ce document suppose un `mon_projet/` déjà porteur d'un lot extrait et d'une
planche PDF générée. Résumé express (détail et vérifications :
`test-chaine-extract-makepdf.md`) :

```bash
mkdir -p /tmp/mmu-test && cd /tmp/mmu-test
cp /home/user/mixed_media_utility/tests/TEST_FILE.mp4 rush-001.mp4

python -m mixed_media_utility.cli extract \
  --project ./mon_projet --video rush-001.mp4 --fps 5 \
  --yes --accept-unknown-color

python3 -c "
import json
d = json.load(open('mon_projet/project.json'))
d['color']['target_colorspace'] = 'rec709'
json.dump(d, open('mon_projet/project.json', 'w'), indent=2)
"

python -m mixed_media_utility.cli makepdf \
  --project ./mon_projet --rush rush-001 --fps 5
```

À ce stade : `mon_projet/planches/mon_projet_rush-001_5_2f-por.pdf`
existe (3 pages, 2 frames/page, gabarit `tpl-a4-portrait-2f-v2`), et
`lots[0].state == "pdf"` dans `project.json`.

## 2. Simuler le scan (pas d'imprimante ni de scanner ici)

Sans matériel, on ne peut pas exécuter le vrai geste « imprimer puis
scanner ». Ce qu'on peut vérifier, c'est que la chaîne logicielle décode
correctement ce qu'elle a elle-même produit : on réinjecte directement le
PDF de `makepdf` dans `scan`, comme s'il s'agissait d'un fichier scanné.

`poppler-utils` (`pdftoppm`) n'est **pas installé** dans cet environnement —
inutile de rastériser la planche à part : `scan` accepte un PDF multipage
directement en entrée (elle rastérise elle-même via `pypdfium2`).

```bash
python -m mixed_media_utility.cli scan \
  --project ./mon_projet \
  --scan mon_projet/planches/mon_projet_rush-001_5_2f-por.pdf \
  --dpi 600 \
  --lot-slug rush-001_5
```

- `--dpi` : résolution déclarée. `makepdf` demande un scan à 600 dpi minimum
  (message affiché en fin de commande) — c'est la valeur utilisée ici.
- `--lot-slug rush-001_5` : sans cet argument, le slug par défaut vient du
  nom de fichier PDF (`mon_projet_rush-001_5_2f-por`), ce qui
  déclenche un avertissement `INGEST_SLUG_DIFFERS_FROM_LOT_ID` — inoffensif
  mais évitable en connaissant déjà le `lot_id` (`rush-001_5`, visible dans
  `project.json`).
- `--overwrite` (non utilisé ici, à connaître) : réécrit les frames de
  sortie déjà présentes, et assume au manifest la perte d'une frame réelle
  redevenue frame de remplacement — utile pour rejouer `scan` sur un lot
  déjà scanné, sans lever de refus de planche étrangère.

**Ce que ça produit** (vérifié) :
```
Demarrage de scan pour le projet mon_projet
3 page(s) ingeree(s) dans scans/rush-001_5 a 600 dpi (slug d'ingestion: rush-001_5)
Avertissement d'ingestion: DPI_DECLARED_DIFFERS_FROM_FILE
Rapport d'ingestion ecrit: mon_projet/scans/rush-001_5/ingest.json
Passe de sortie: 6 frame(s) ecrite(s) dans frames-scannees/rush-001_5, dont 0 de remplacement
Manifest ecrit et valide: mon_projet/project.json
Lot rush-001_5: etat scan, 6 frame(s) reconstruite(s), 0 de remplacement, attendu 6 -- lot complet
scan termine avec succes. 3 page(s) dans scans/rush-001_5; lot rush-001_5 complet (6 frame(s) reconstruite(s), 0 de remplacement). Manifest: mon_projet/project.json
```

`DPI_DECLARED_DIFFERS_FROM_FILE` est attendu ici et pas inquiétant : la
mesure de DPI du PDF (page A4 réelle) diverge du DPI **déclaré** (600, celui
qu'on affirme avoir utilisé pour le scan) — c'est exactement le rôle de cet
avertissement sur un vrai scan aussi : dire que le DPI annoncé par
l'opérateur n'est pas corroboré par le fichier, pas une erreur en soi.

**Un lot dont aucune planche n'a livré son QR** (mauvais gabarit, page
illisible…) s'arrête après la détection : la commande le dit explicitement
(« Aucune planche n'a livre son QR : ni frame ni manifest ne sont ecrits »)
et rend `0` — l'ingestion, elle, a bien eu lieu et son rapport est écrit. Pas
testé ici (le cas nominal n'y passe pas), mais à connaître si un lot réel
échoue silencieusement à ce stade.

## 3. Vérifications sur disque et dans le manifest

```bash
ls mon_projet/frames-scannees/rush-001_5/
# scan_rush-001_5_00-00-00-00.tiff ... scan_rush-001_5_00-00-01-00.tiff
# (6 fichiers, memes timecodes que les 6 frames extraites a l'etape extract)
```

Les noms de fichiers scannés doivent correspondre exactement aux timecodes
des frames extraites au départ — c'est la garantie que la chaîne
impression → scan n'a perdu aucune identité de frame en route (le risque que
les mutants `M33` de 5.6 et `M25` de 5.7, tous deux trouvés en revue, visaient
précisément : un mauvais appariement page/frame ou lot/lot, silencieux).

```bash
python3 -c "
import json
lot = json.load(open('mon_projet/project.json'))['lots'][0]
print('state:', lot['state'])
print('output_frames_dir:', lot['output_frames_dir'])
print('reconstructed_frame_count:', lot['reconstructed_frame_count'])
print('synthetic_frame_count:', lot['synthetic_frame_count'])
"
```

Points à contrôler dans `project.json` :
- `lots[0].state == "scan"` (progression depuis `"pdf"`, écrit par `makepdf`).
- `lots[0].output_frames_dir == "frames-scannees/rush-001_5"`. **Le nom de la
  cle ne change pas** (`EPIC11-ARB-221`) : le manifeste garde `output_frames_dir`
  la ou l'interface dit « frames scannees ». Seule la VALEUR suit le disque.
- `lots[0].reconstructed_frame_count == 6` (== `expected_frame_count`, posé
  par `extract` — le lot est déclaré **complet**).
- `lots[0].synthetic_frame_count == 0` (aucune frame de remplacement : les
  six pages ont toutes livré leur QR et leur géométrie).
- Un bloc `reconstruction` au niveau racine du document, qui trace la
  provenance scan par page (`qr_status`, `homography_status`, `status`) —
  c'est ce que 5.7 ajoute par rapport à ce que `makepdf` écrivait déjà.

## 4. Ce que cette chaîne ne fait pas encore

- **Pas de prévisualisation GUI du scan.** La story 5.8 livre le contrat de
  données `scan_previz` (comme `extraction_previz`/`pdf_previz` pour les
  étapes précédentes), consommé par une future interface graphique — ce
  n'est pas une commande CLI, rien à tester en ligne de commande ici.
- **Aucun round-trip physique réel n'est exercé.** En réinjectant le PDF de
  `makepdf` directement dans `scan`, on saute l'impression et la
  numérisation matérielles. Ce que ce document vérifie, c'est que le
  logiciel décode correctement ce qu'il a lui-même produit — pas la
  robustesse à un vrai scan bruité (déformation papier, bave d'encre,
  éclairage). C'est un test de câblage, pas un test de terrain.

## 5. Nettoyage

```bash
rm -rf /tmp/mmu-test
```

## Repères de code si un comportement surprend

- Commande unique : `scan_command` dans `cli.py` — enchaîne les quatre
  étapes ci-dessous, chacune appelée et jamais réécrite (voir sa docstring).
- Ingestion (5.1) : `scan_ingest.ingest_scan_lot`.
- Détection géométrique + décodage QR (5.2) : `scan_detection.detect_lot_pages`.
- Recadrage (5.3) : `scan_crop.build_page_crop_plan`, `scan_crop.crop_frames`.
- Écriture des frames scannées (5.6) : `scan_output_frames.write_lot_output_frames`.
- Persistance au manifest (5.7) : `scan_manifest.persist_scan`,
  `scan_manifest.check_scan_conflicts` (refus **avant** écriture,
  EPIC5-ARB-34).
