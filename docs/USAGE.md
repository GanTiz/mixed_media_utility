# Guide d'utilisation — Mixed Media Utility

## Description rapide
Outil local pour : extraire des images depuis des rushes, générer un gabarit imprimable (repères ArUco + patchs couleur), rescanner et recalibrer les frames, puis réassembler une séquence ou ré-encoder une vidéo.

## Commandes CLI (squelette actuel et cible 1.1)

`mixed-media-util extract-frames <input> [-o OUTDIR]`
- `input` : fichier vidéo (H.264, HEVC, ProRes, etc.)
- `-o/--outdir` : dossier de sortie (séquence d'images)

`mixed-media-util gen-gabarit <project-meta> [-o OUTPDF]`
- génère un PDF vectoriel avec repères ArUco, patchs couleur et métadonnées

Workflow cible de la story 1.1 rouverte:

`mixed-media-util poc build-sheet --project <dir> --video <video> --fps 2 --dpi <dpi>`
- extrait 2 frames d'une vidéo 16:9 simple et les compose dans une planche PDF imprimable avec repères ArUco

`mixed-media-util poc process-scan --project <dir> --scan <scan> --dpi <dpi>`
- traite le scan de cette planche, redresse la page et réextrait 2 frames rescannées

`mixed-media-util apply-calibration <scanned-image> <profile> [-o OUTDIR]`
- applique correction couleur calculée à partir du scan

`mixed-media-util encode --project <dir> --lot <lot_id> [--profile <profil>] [--resolution <res>] [--overwrite] [--yes]`
- reconstruit le master vidéo d'un lot rescanné dans `outputs/<lot_id>_mmu_<profil>[_<résolution>].<conteneur>`
- prend **un projet et un lot**, jamais un dossier d'images nu (story 6.1, `EPIC6-ARB-2`) : le disque ne
  distingue pas une mire de synthèse d'une vraie frame — même nom par construction, aucun tag — et le verdict
  de complétude, le registre des mires, la cadence du lot et le timecode de départ vivent uniquement dans le
  manifest. Un dossier nu produirait donc un master faux sans le dire.
- profils : identifiants du catalogue `codec_profiles` (`prores_hq` par défaut, puis `prores_422`, `prores_lt`,
  `dnxhr_hq`, `dnxhr_hqx`, `h264_delivery`, `hevc_delivery`). L'ancienne surface POC
  (`encode <frames-dir> -c [prores|h264|hevc] -o output.mov`) est **supprimée** : aucune de ses trois valeurs
  n'était un identifiant valide.
- résolution : `hd1080` par défaut (1920x1080), `native` pour la géométrie des frames rescannées, ou
  `<largeur>x<hauteur>`.

## Menu d'aide (à inclure dans l'application)
Voir `docs/HELP_MENU.md` pour le texte complet du menu d'aide.

## Exemples rapides
Extraire frames :

```bash
mixed-media-util extract-frames "rush.mov" -o project1/frames
```

Générer gabarit :

```bash
mixed-media-util gen-gabarit project1/metadata.json -o project1/gabarit.pdf
```

Workflow cible story 1.1 :

```bash
mixed-media-util poc build-sheet --project project1 --video rush_1920x1080.mp4 --fps 2 --dpi 300
mixed-media-util poc process-scan --project project1 --scan project1/inputs/scan_page.tiff --dpi 300
```

## Fichiers projet
- `project.json` : métadonnées du projet
- `rush-<name>.json` : métadonnées par rush (timecode, fps, provenance)

