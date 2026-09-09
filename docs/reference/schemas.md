# Schémas JSON

Les manifests du projet suivent des schémas stricts (validation `jsonschema`).

## `project.schema.json`

Structure racine du projet.

```json
{
  "project_id": "projet_demo",
  "rushes": [
    {
      "rush_id": "rush_test_16x9_1920x1080_25fps",
      "source_resolution": {"width": 1920, "height": 1080},
      "source_frame_rate": "25/1",
      "timecode_base": 25,
      "lots": [
        {
          "lot_id": "rush_test_..._lot-1",
          "template_id": "tpl-a4-portrait-4f-v1",
          "patch_preset_id": "patches-18-v2",
          "gamut_map_id": "gamut-map-none-1",
          "source_start_timecode": "00:00:00:00",
          "source_in_timecode": "00:00:10:00",
          "source_out_timecode": "00:00:20:00",
          "fps_source_exact": "30000/1001",
          "properties": {
            "pdf_generated": true,
            "template_id": "tpl-a4-portrait-4f-v1",
            "patch_preset_id": "patches-18-v2",
            "gamut_map_id": "gamut-map-none-1"
          }
        }
      ]
    }
  ],
  "templates": {
    "tpl-a4-portrait-4f-v1": {
      "orientation": "portrait",
      "frames_per_page": 4,
      "page_size_mm": [210, 297]
    }
  }
}
```

### Champs requis

| Champ | Type | Description |
|-------|------|-------------|
| `project_id` | string | Identifiant unique |
| `rushes` | array | Liste de rushs |
| `rushes[].rush_id` | string | Identifiant rush |
| `rushes[].lots` | array | Lots du rush |
| `rushes[].lots[].lot_id` | string | Identifiant lot |

### Vocabulaires fermés

| Champ | Valeurs |
|-------|---------|
| `orientation` | `portrait`, `landscape` |
| `page_role` | `i` (images), `c` (calibration) |
| `lot_state` | `extraction`, `reconstruction`, `scan` |
| `timecode_base` | 24, 25, 30, 50, 60, 48, 72, 90, 120 |
| `timecode_format` | `source`, `target` |

---

## `extraction_manifest`

Métadonnées d'extraction (timecodes, cadences, empreintes).

```json
{
  "rush_id": "rush_test_...",
  "fps_source_exact": "30000/1001",
  "resolution_source": {"width": 1920, "height": 1080},
  "frame_timecodes_digest": "a1b2c3...",
  "lots": [
    {
      "lot_id": "...",
      "source_in_timecode": "00:00:10:00",
      "source_out_timecode": "00:00:20:00",
      "fps_target": 5.0,
      "observed_frame_count": 50,
      "rounding_policy_id": "RP-DEFAULT"
    }
  ]
}
```

---

## `scan_manifest`

Détection, crop plan, calibration.

```json
{
  "lot_id": "...",
  "ingest": {
    "dpi": 600,
    "format": "tiff",
    "scanned_at": "2026-08-28T11:00:00Z"
  },
  "detection": {
    "aruco_corners": [[x,y], ...],
    "qr_payload": {
      "pr": "i",
      "ti": "tpl-a4-portrait-4f-v1",
      "gmi": "gamut-map-none-1"
    },
    "homography_ok": true
  },
  "crop_plan": {
    "frames": [
      {"index": 0, "bbox_mm": [x,y,w,h], "slot": 0}
    ]
  },
  "calibration": {
    "status": "applied",
    "profile_id": "scanner-hp-4520",
    "divergence_metric": 0.42
  }
}
```

### Statuts calibration

| Valeur | Signification |
|--------|--------------|
| `not_applied` | aucune correction |
| `applied` | correction active |
| `divergent` | écart > budget, avertissement |

---

## `pdf_manifest`

État PDF généré.

```json
{
  "lot_id": "...",
  "pdf_generated": true,
  "template_id": "tpl-a4-portrait-4f-v1",
  "patch_preset_id": "patches-18-v2",
  "gamut_map_id": "gamut-map-none-1",
  "print_size_mm": [210, 297]
}
```

---

## Validation

```python
import jsonschema
from pathlib import Path

schema = json.loads(Path("src/mixed_media_utility/io/project.schema.json").read_text())
jsonschema.validate(instance=project_dict, schema=schema)
```

Voir `tests/unit/test_project_layout.py` pour les cas de test.

---

## Notes de version

- `PAYLOAD_SCHEMA_VERSION = 2.0` (clés courtes)
- `MVP_OUTPUT_BIT_DEPTH = 16` (TIFF 16 bits)
- `MAX_PATCHES_PER_PAGE = 36`