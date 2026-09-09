# Manuel Temporaire - Test roundtrip Story 1.1

Ce document explique comment tester manuellement le roundtrip de la story 1.1.

Etat important a garder en tete:

- ce document decrit le flux tel qu'implemente par les deux commandes `poc build-sheet` et `poc process-scan`;
- `poc build-sheet` compose desormais effectivement les 2 frames extraites dans le PDF, bord a bord dans leurs zones 16:9.

Il couvre le flux souhaite:

- generation de planche PDF a partir d'une video;
- impression / annotation / scan;
- traitement du scan pour reextraire 2 frames rescannées.

## Ce que la story 1.1 permet

Les deux commandes sont:

```powershell
.\.venv\Scripts\python.exe -m mixed_media_utility.cli poc build-sheet --project <dossier-projet> --video <video> --fps 2 --dpi <dpi>
```

```powershell
.\.venv\Scripts\python.exe -m mixed_media_utility.cli poc process-scan --project <dossier-projet> --scan <scan> --dpi <dpi>
```

Comportement cible:

- `poc build-sheet` extrait des frames depuis la video, retient 2 frames, puis les compose dans `patches/patch_sheet.pdf` avec 4 marqueurs ArUco;
- `poc process-scan` lit un scan ou une photo de la page imprimee, detecte 4 marqueurs ArUco de coin, redresse la page, puis decoupe automatiquement les 2 zones fixes vers `outputs/`.

Contraintes explicites de ce MVP:

- l'utilisateur doit fournir pour l'instant un cas simple 16:9, typiquement une video H.264 1920x1080;
- l'utilisateur doit fournir `--fps 2` pour viser 2 frames placees sur la planche;
- la planche contient exactement 2 cadres image 16:9;
- les images sont placees bord a bord dans le cadre noir, sans marge.

## Prerequis

Depuis PowerShell, placez-vous a la racine du repo:

```powershell
Set-Location D:\EGAN\Documents\mixed_media_utility
```

Activez l'environnement virtuel si necessaire:

```powershell
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& .\.venv\Scripts\Activate.ps1)
```

Verifiez que `ffmpeg` est disponible:

```powershell
ffmpeg -version
```

Si cette commande echoue, le POC ne pourra pas extraire les frames video.

Pour lancer `python -m mixed_media_utility.cli`, definissez aussi `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "src"
```

## Peut-on tester avec un fichier de son choix ?

Oui, avec ces precisions:

- pour `--video`: oui, vous pouvez choisir n'importe quelle video locale lisible par `ffmpeg`, mais le MVP vise d'abord une video 16:9 simple, typiquement 1920x1080 H.264;
- pour `--scan`: oui, vous pouvez choisir n'importe quelle image locale `.png`, `.jpg`, `.jpeg` ou `.tiff` (8 ou 16 bits par canal), mais elle doit montrer la planche imprimee complete avec les 4 marqueurs ArUco visibles.

En pratique:

- si vous voulez preparer le prochain dev, placez votre video ou gardez-la accessible par chemin absolu; la commande la recopiera ensuite dans `inputs/` du projet;
- si vous voulez tester le roundtrip complet une fois la story implemente, utilisez votre propre video et votre propre scan/photo de la page imprimee.

## Parcours A - Test rapide avec votre video et le fixture fourni

Ce parcours est le plus simple pour verifier que le code actuel fonctionne.

### 1. Choisir une video locale

Prenez une video courte 16:9 de votre choix, par exemple:

```text
D:\mes_tests\video_test.mp4
```

Si vous n'avez pas de video sous la main, vous pouvez en generer une synthetique 16:9 (le ratio doit rester proche de 16:9, sinon `poc build-sheet` echoue explicitement):

```powershell
ffmpeg -y -f lavfi -i color=c=blue:s=1920x1080:d=2:r=10 .\tests\fixtures\synthetic_manual_test.mp4
```

### 2. Lancer le POC

Exemple avec votre propre video:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m mixed_media_utility.cli poc build-sheet --project .\projects\manual_test --video "D:\mes_tests\video_test.mp4" --fps 2 --dpi 150
```

Exemple avec la video synthetique generee localement:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m mixed_media_utility.cli poc build-sheet --project .\projects\manual_test --video .\tests\fixtures\synthetic_manual_test.mp4 --fps 2 --dpi 150
```

Puis traitez un scan (le fixture fourni ou votre propre scan) pour completer le roundtrip:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m mixed_media_utility.cli poc process-scan --project .\projects\manual_test --scan .\tests\fixtures\aruco\simple_scan.png --dpi 150
```

### 3. Resultat attendu

Si tout se passe bien, vous devez voir un message de succes dans la console.

Le dossier projet doit contenir:

- `inputs/`
- `frames/`
- `patches/patch_sheet.pdf`
- `detection/markers.json`
- `outputs/scan_frame_0001.tiff`
- `outputs/scan_frame_0002.tiff`
- `logs/poc_run.log`
- `project.json`

### 4. Verifier les fichiers produits

Lister les artefacts:

```powershell
Get-ChildItem .\projects\manual_test
Get-ChildItem .\projects\manual_test\frames
Get-ChildItem .\projects\manual_test\outputs
```

Verifier le manifest:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from mixed_media_utility.io.manifest import validate_manifest; validate_manifest(Path('projects/manual_test/project.json')); print('manifest ok')"
```

Lire le log:

```powershell
Get-Content .\projects\manual_test\logs\poc_run.log
```

## Parcours B - Voir le PDF genere

Oui, vous pouvez deja voir le PDF resultant.

Le fichier genere par le POC est:

```text
projects\manual_test\patches\patch_sheet.pdf
```

Pour l'ouvrir sous Windows:

```powershell
Start-Process .\projects\manual_test\patches\patch_sheet.pdf
```

Ce que vous verrez:

- 4 marqueurs ArUco de coin;
- 2 zones rectangulaires 16:9 contenant chacune une des 2 premieres frames extraites de votre video, bord a bord sans marge;
- un gabarit A4 portrait.

## Parcours C - Tester avec impression, scan, puis reprise de la fin du process

Oui, vous pouvez deja faire un test papier reel de bout en bout: le PDF contient desormais les 2 frames extraites de votre video.

### Idee generale

Le but de ce test est de verifier:

- que le PDF est imprimable;
- qu'un scan ou une photo de cette page peut etre detecte(e);
- que la page peut etre redressee;
- que les 2 zones fixes sont bien decoupees dans `outputs/`.

### 1. Generer un projet de travail

Si vous n'avez pas encore de projet de test, lancez d'abord le parcours A pour creer un dossier projet et obtenir `patch_sheet.pdf`.

### 2. Ouvrir puis imprimer le PDF

Ouvrir le fichier:

```powershell
Start-Process .\projects\manual_test\patches\patch_sheet.pdf
```

Conseils d'impression:

- imprimer en A4 portrait;
- desactiver tout redimensionnement automatique du type "Fit to page" ou "Ajuster a la page";
- imprimer a 100 % si possible;
- garder les 4 marqueurs ArUco bien nets et visibles.

### 3. Verifier le contenu des 2 zones

Les 2 zones contiennent deja les 2 premieres frames extraites de votre video: aucune action manuelle n'est necessaire avant impression.

### 4. Scanner ou photographier la page

Exportez la page sous forme d'image:

- `.tiff` 16 bits recommande: c'est le seul format qui conserve la profondeur du
  scanner, et la profondeur conditionne l'aller-retour de gamut (story 5.0). Un
  `.tiff` 8 bits est accepte et declare comme tel dans `project.json`;
- `.png`, `.jpg` ou `.jpeg` acceptes, tous 8 bits par canal;
- un scan flottant (TIFF 32 bits, `.hdr`, `.pfm`) est refuse explicitement, avec
  un message: convertissez-le en 8 ou 16 bits avant de le passer a la commande.

Conseils pour que la detection marche:

- toute la page doit etre visible;
- les 4 marqueurs ArUco doivent etre entiers et lisibles;
- eviter les reflets trop forts;
- eviter un flou important;
- garder une perspective raisonnable si vous utilisez un smartphone.

Exemple de chemin:

```text
D:\mes_tests\scan_page_01.png
```

### 5. Traiter votre vrai scan

Sur un nouveau projet (executez d'abord `poc build-sheet` sur ce dossier si ce n'est pas deja fait):

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m mixed_media_utility.cli poc build-sheet --project .\projects\paper_test --video "D:\mes_tests\video_test.mp4" --fps 2 --dpi 150
.\.venv\Scripts\python.exe -m mixed_media_utility.cli poc process-scan --project .\projects\paper_test --scan "D:\mes_tests\scan_page_01.png" --dpi 150
```

Ou sur le projet existant du parcours A, si vous acceptez d'ecraser les sorties precedentes:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m mixed_media_utility.cli poc process-scan --project .\projects\manual_test --scan "D:\mes_tests\scan_page_01.png" --dpi 150
```

### 6. Examiner la fin du process

Ouvrir le dossier des sorties:

```powershell
Start-Process .\projects\paper_test\outputs
```

Vous devriez y trouver:

- `scan_frame_0001.tiff`
- `scan_frame_0002.tiff`

Ces deux images correspondent aux deux zones fixes decoupees apres deskew de la page.
Elles sont ecrites en TIFF 16 bits depuis la story 5.0 (et non plus en PNG 8 bits):
`project.json` porte, sous `meta.color`, la profondeur reellement lue en entree
(`source_bit_depth`) a cote de celle ecrite en sortie (`output_bit_depth`).

Ouvrir aussi le JSON de detection si vous voulez verifier les marqueurs trouves:

```powershell
Get-Content .\projects\paper_test\detection\markers.json
```

Lire le log du pipeline:

```powershell
Get-Content .\projects\paper_test\logs\poc_run.log
```

## Que tester concretement aujourd'hui

Voici le flux complet realiste a tester maintenant:

1. Utiliser votre propre video 16:9 pour verifier l'extraction de frames et leur composition dans le PDF.
2. Voir le PDF produit par `poc build-sheet`, avec les 2 frames deja placees dans leurs zones.
3. Imprimer ce PDF.
4. Scanner ou photographier la page imprimee.
5. Rejouer `poc process-scan` avec votre scan pour verifier la detection, le redressement et la decoupe finale.

Ce flux couvre desormais le roundtrip complet:

`video -> frames inserees dans le PDF -> impression -> scan -> re-extraction des memes frames`

Le test physique valide:

- la generation du gabarit avec les frames composees;
- la detectabilite des marqueurs;
- le redressement de page;
- la decoupe des zones rescannees.

## Depannage rapide

### Erreur: `Fichier video introuvable`

Le chemin passe a `--video` n'existe pas ou est mal quote.

### Erreur: `Fichier scan introuvable`

Le chemin passe a `--scan` n'existe pas ou est mal quote.

### Erreur liee a `ffmpeg`

`ffmpeg` n'est pas disponible dans le `PATH`.

Test rapide:

```powershell
ffmpeg -version
```

### Erreur: marqueurs manquants

Le scan ne montre pas correctement les 4 marqueurs de coin.

Verifier:

- page complete visible;
- marqueurs non coupes;
- image nette;
- contraste suffisant.

### Erreur sur `--fps` ou `--dpi`

Le POC exige des valeurs strictement positives.

Exemple correct:

```powershell
--fps 2 --dpi 150
```

## Commande de verification automatique

Si vous voulez verifier l'etat actuel du code sans test papier:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit -q
```

Au moment de rediger ce document, la suite passe avec succes.