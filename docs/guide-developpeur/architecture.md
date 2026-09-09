# Architecture

## Principes de conception

1. **Source unique de vérité** : un invariant par constante, jamais dupliqué
2. **Projection, jamais calcul** : les données transportées sont des mesures, pas des déductions
3. **Contrats fermés** : vocabulaires énumérés, schémas JSON stricts
4. **Tests de mutation** : chaque correctif a un test qui échoue avant et passe après
5. **Règle des fabriques** : une fabrique de collection produit ≥ 2 éléments distinguables

---

## Modules principaux (`src/mixed_media_utility/`)

| Module | Rôle |
|--------|------|
| `cli.py` | Point d'entrée CLI (`python -m mixed_media_utility.cli`) |
| `tui/` | Interface terminal (textual) — `mmu-tui` |
| `gui/` | Interface graphique (PySide6), extra `[gui]` |
| `detection/aruco.py` | Détection marqueurs ArUco, homographie |
| `qr_codes.py` | Encodage/décodage payload QR |
| `scan_detect.py` | Pipeline détection scan |
| `scan_ingest.py` | Ingestion scan (métadonnées) |
| `scan_output_frames.py` | Découpe et écriture des **frames scannées** |
| `extraction.py` | Extraction des **frames extraites** depuis un rush vidéo |
| `frame_selection.py` | Sélection déterministe des frames extraites |
| `project_inventory.py` | L'arbre des objets d'un projet, et **le vocabulaire publié** (les huit natures) |
| `project_maintenance.py` | Suppression par granularité nommée, filiation des objets |
| `color_calibration.py` | Calibration couleur, profils de chaîne |
| `pdf_composition.py` | Composition planche PDF |
| `page_templates.py` | Registre des gabarits de mise en page |
| `patch_presets.py` / `patch_values.py` | Patches calibration, valeurs théoriques |
| `codec_profiles.py` | Profils encodage (ProRes/DNxHR/H.264/HEVC) |
| `encode.py` | Encodage mezzanine (ffmpeg) |
| `io/` | Manifestes, reconstruction, schémas JSON |
| `previz_common.py` | Enveloppe previz partagée (canonicalisation, empreintes) |

---

## Flux de données

```
rush → extract → lot (extract-frames/) → makepdf → planche (planches/)
                                                        ↓ impression
                                                    numérisation
                                                        ↓
                    scan (scans/<slug>/) → détection ArUco/QR → plan de découpe
                                                        ↓
                            lot scanné → frames scannées (frames-scannees/)
                                                        ↓ encode
                                            master (outputs/)
```

Le vocabulaire de ce schéma est celui de
[Concepts de base](../guide-utilisateur/concepts.md), et il est **écrit une
seule fois** dans le code : les huit natures d'objet vivent dans
`project_inventory.py`. Une interface les **lit**, elle ne les rédige pas.

**Deux noms de dossier ont changé et les anciens restent reconnus** : `frames/`
est devenu `extract-frames/`, `output-frames/` est devenu `frames-scannees/`.
Les constantes d'avant survivent sous `LEGACY_FRAMES_DIRNAME` et
`LEGACY_OUTPUT_FRAMES_DIRNAME` dans `io/project_layout.py` — **reconnues en
lecture, jamais écrites**, sur le patron de `LEGACY_SOURCES_DIRNAME`. Les
**clés** du manifeste, elles, ne bougent pas : `output_frames_dir` garde son
nom et sa valeur suit le disque.

---

## Contrats de données

### Schémas JSON (`io/`)

| Schéma | Contenu |
|--------|---------|
| `project.schema.json` | Structure projet (rushs, lots, templates) |
| `extraction_manifest` | Timecodes, cadences, empreintes |
| `scan_manifest` | Détection, crop plan, calibration |
| `pdf_manifest` | État PDF généré, template_id, patch_preset_id |

### Payload QR

Format binaire compact encodé dans le QR. Clés courtes (`pr`, `ti`, `gmi`…) pour budget de taille. Schéma versionné `PAYLOAD_SCHEMA_VERSION`.

---

## Invariants critiques

| Invariant | Module | Raison |
|-----------|--------|--------|
| 16 bits chemin scan | `color_pipeline` | fidélité couleur |
| `OUTPUT_BIT_DEPTH` unique | `color_pipeline` | borne disque correcte |
| `allow_abbrev=False` | `cli.py` | pas d'ambiguïté `--o` |
| `CANONICAL_ID_MAX_LENGTH=48` | `io/naming` | identité de lot tenable dans le QR |
| `NATURES` unique | `project_inventory` | un mot, un objet : aucune seconde rédaction du vocabulaire |
| `ESCDELAY=25` | lanceurs | latence Échap |

---

## Dépendances

### Core (TUI)
`textual`, `numpy>=2`, `Pillow`, `jsonschema`, `ffmpeg-python`

### GUI (optionnel)
`PySide6`, `opencv-contrib-python`, `pypdfium2`, `reportlab`

### Dev
`mutmut`, `pytest`, `pytest-qt`

---

## Tests et qualité

- **Unitaires** : `tests/unit/` (pytest)
- **Mutation** : `scripts/mutation/` (mutmut)
- **Campagnes** : une campagne par story, ciblée sur fichier source + tests

Voir [Tests et mutation testing](tests.md) pour le détail.

---

## Convention de branches

| Type | Nom |
|------|-----|
| Story | `feat/<epic>-<story>` |
| Bug | `fix/<courte-desc>` |
| Chore | `chore/<courte-desc>` |
| Doc | `docs/<sujet>` |
| Packaging | `feat/packaging-*` |

Branches de worktree parallèle : `oc/epic-11-TUI`, `claude/vague-4-epic-7`.

---

## Points de contention connus (CLAUDE.md)

- `sprint-status.yaml` : éditer **sa** ligne uniquement, après `git pull --rebase`
- `pyproject.toml` `[tool.mutmut]` : **jamais** committé scopé
- `deferred-work.md` : entrées barrées annotées, jamais supprimées

---

## Outils externes

| Outil | Usage |
|------|-------|
| `ffmpeg` | décodage/encodage vidéo |
| `pypdfium2` | rasterisation PDF scan |
| `reportlab` | génération PDF planche |
| `opencv` | traitement image, ArUco |