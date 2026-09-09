# -*- coding: utf-8 -*-
"""Story 11.7, **lot B1** -- fabriquer les entrees du dossier d'identite de `makepdf`.

**Ce fichier n'est pas un banc.** C'est l'etape 1 de la mesure d'identite :
il ecrit **une seule fois**, avec le `src/` d'AUJOURD'HUI, le projet sur lequel
les deux releves seront joues -- celui du `baseline_commit` et celui de la
branche apres deplacement du corps de `makepdf_command`.

**Pourquoi les entrees sont fabriquees a part, et une seule fois.** Le releve
tourne deux fois, sous deux `src/` differents. S'il fabriquait son projet
lui-meme, il le fabriquerait avec `build_extraction_manifest` et `io.naming` du
`src/` sous lequel il tourne : deux entrees differentes, donc une comparaison
qui ne mesure plus le deplacement mais la somme du deplacement et de la
fabrique. Les entrees sont donc des **octets figes**, recopies tels quels avant
chaque scenario.

Emploi :

```
python3 tests/unit/fabriquer_les_entrees_makepdf.py <dossier d'entrees>
```
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

_RACINE = Path(__file__).resolve().parents[2]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

from mixed_media_utility.frame_selection import select_source_frames  # noqa: E402
from mixed_media_utility.io import naming, project_layout             # noqa: E402
from mixed_media_utility.io.extraction_manifest import (              # noqa: E402
    ExtractionRecord,
    build_extraction_manifest,
)

#: Identite du projet mesure. Verbeuse a dessein : elle se relit dans les
#: messages de refus, ou un identifiant court se confondrait avec un lot.
PROJECT_ID = "proj-identite-makepdf"
RUSH_ID = "rush-001"
FPS_SOURCE = 25.0
FPS_TARGET = 5.0

#: 20 images source a 25 im/s vers 5 im/s -> **quatre** frames extraites. Quatre
#: et non deux : le vocabulaire portrait porte `(1, 2, 3, 4, 8)`, donc quatre
#: frames donnent **trois** mises en page distinguables sur le meme lot
#: (`1f` -> 4 planches, `2f` -> 2, `4f` -> 1). Une seule mise en page rendrait
#: le scenario « changer de forme ne declenche plus de conflit » (`ARB-175`)
#: inexprimable.
SOURCE_FRAME_COUNT = 20

#: L'espace couleur cible que l'operateur renseigne avant d'imprimer. `makepdf`
#: l'exige ; il est pose ici pour que le nominal ne parte pas sur le chemin du
#: defaut applique, qui reecrit le manifest et brouillerait la mesure.
TARGET_COLORSPACE = "rec709"

#: Le nom du dossier d'entree que le releve recopie avant chaque scenario.
SOCLE = "projet-avec-lot"


def fabriquer(entrees: Path) -> Path:
    """Ecrire le socle sous `<entrees>/projet-avec-lot` et rendre son chemin."""
    projet = entrees / SOCLE
    projet.mkdir(parents=True, exist_ok=True)
    project_layout.ensure_project_layout(projet)

    selection = select_source_frames(
        fps_source=FPS_SOURCE,
        fps_target=FPS_TARGET,
        source_frame_count=SOURCE_FRAME_COUNT,
    )
    lot_id = naming.build_lot_id(RUSH_ID, FPS_TARGET)
    frames_dir_relative = (
        f"{project_layout.FRAMES_DIRNAME}/"
        f"{project_layout.rush_dir_slug(RUSH_ID, FPS_TARGET)}"
    )
    record = ExtractionRecord(
        project_id=PROJECT_ID,
        rush_id=RUSH_ID,
        rush_source_name=f"{RUSH_ID}.mov",
        lot_id=lot_id,
        frames_dir_relative=frames_dir_relative,
        selection=selection,
        fps_source=FPS_SOURCE,
        fps_target=FPS_TARGET,
        source_width=1920,
        source_height=1080,
        source_fields={},
        confirmation_mode="non_interactif",
        unknown_color_accepted=True,
        # Fige : cet instant entre dans le manifest et serait sinon un
        # troisieme champ volatil a neutraliser pour rien.
        confirmed_at="2026-08-06T00:00:00Z",
    )
    manifest = build_extraction_manifest(None, record)
    manifest["color"]["target_colorspace"] = TARGET_COLORSPACE
    (projet / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    frames_path = projet / Path(frames_dir_relative)
    frames_path.mkdir(parents=True, exist_ok=True)
    generateur = np.random.default_rng(42)
    for frame in selection.frames:
        nom = naming.build_extracted_frame_filename(
            RUSH_ID, FPS_TARGET, frame.frame_timecode
        )
        # Un bruit **different par frame** -- le generateur avance a chaque
        # tirage. Des frames uniformes rendraient invisible toute permutation
        # de l'appariement page/emplacement (regle des fabriques).
        image = generateur.integers(0, 65535, size=(108, 192, 3), dtype=np.uint16)
        if not cv2.imwrite(str(frames_path / nom), image):   # pragma: no cover
            raise RuntimeError(f"ecriture TIFF impossible: {nom}")

    # Garde de la fabrique elle-meme : sans quatre frames, les trois mises en
    # page annoncees plus haut n'existent pas et le releve mesurerait moins que
    # ce qu'il annonce.
    ecrites = sorted(p.name for p in frames_path.glob("*.tiff"))
    if len(ecrites) != len(selection.frames):               # pragma: no cover
        raise RuntimeError(f"{len(ecrites)} frames ecrites")
    return projet


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:                                # pragma: no cover
        print(__doc__, file=sys.stderr)
        return 2
    projet = fabriquer(Path(arguments[0]))
    print(f"socle ecrit: {projet}")
    return 0


if __name__ == "__main__":                                 # pragma: no cover
    raise SystemExit(main())
