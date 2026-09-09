# Recadrages QR des quatre scans 300 dpi du 2026-08-17

Ces quatre PNG sont des **recadrages du raster reel**, pas des syntheses. Meme
papier, meme encre, meme capteur, meme bruit : seuls les pixels hors zone du QR
ont ete retires.

## Origine

Quatre planches imprimees puis scannees par Egan le 2026-08-17 sur un HP Envy
(La Seyne), en TIFF **300 dpi**, 2631 x 1912 px, ~15 Mo chacune. C'est le seul
materiel dont il dispose : `EPIC5-ARB-91` en fait une exigence (« Il faut que
300 dpi passe »), pas une observation.

Sur ces quatre scans, **un QR sur quatre** ne se decode pas sans le repli de
re-echantillonnage de `decode_qr_image_resilient` : `main`. Ce n'est pas la
qualite du scan, c'est la densite du symbole — a 300 dpi il ne reste pas assez
de pixels par module. Agrandir le QR imprime est impossible : emprise 38,46 mm
pour 39,62 mm reserves, soit 1,2 mm de marge.

## Ce que chaque fichier vaut

| fichier | verdict sans repli | verdict avec repli |
| --- | --- | --- |
| `main-qr-300dpi.png` | `detected_but_unreadable` | `decoded` (368 octets) |
| `calibration-qr-300dpi.png` | `decoded` (181) | `decoded` (181) |
| `chendj-qr-300dpi.png` | `decoded` (380) | `decoded` (380) |
| `heteroclite-qr-300dpi.png` | `decoded` (338) | `decoded` (338) |

`main` porte la regression ; les trois autres sont le temoin de non-regression
du chemin nominal.

## Pourquoi PNG et pas TIFF

`.gitattributes` versionne `*.tiff` et `*.tif` en **Git LFS**. `tests/fixtures/`
ne contient aujourd'hui aucun TIFF, exactement pour que la suite de tests ne
dependance jamais de `git-lfs` : dans un conteneur neuf sans `git-lfs`, git rend
des **pointeurs de 133 octets sans lever d'erreur**, et le test echouerait sur un
message de decodage d'image incomprehensible.

Le PNG n'est couvert par aucune ligne du `.gitattributes` et il est **sans
perte** : la relecture du PNG rend un tableau `array_equal` au recadrage du TIFF,
verifie a la production. Aucun pixel n'a ete altere.

## Comment ils ont ete produits

Boite du symbole localisee par `cv2.QRCodeDetectorAruco().detect()` sur le TIFF
complet, elargie de **40 px** de marge sur les quatre cotes (bornee au raster),
puis `cv2.imwrite(..., IMWRITE_PNG_COMPRESSION=9)` sur le decoupage 3 canaux.

La marge n'est pas arbitraire. Le docstring de `decode_qr_image_resilient`
avertit qu'un recadrage **ne conserve pas le verdict** ; c'est verifie ici plutot
que suppose. Balayage des marges sur `main`, 300 dpi, detecteur par defaut :

| marge (px) | sans repli | avec repli |
| --- | --- | --- |
| 0 | `no_symbol_detected` | `no_symbol_detected` |
| 10 a 480 | `detected_but_unreadable` | `decoded` |

A marge nulle il n'y a plus de zone de silence et le symbole n'est meme plus
localise : le couple de verdicts serait faux. De 10 a 480 px il est stable, sur
les quatre feuilles. 40 px est pris au milieu de ce plateau, loin des deux bords.

Les TIFF d'origine ne sont pas dans le depot : ils vivaient dans un scratchpad de
session, efface depuis. C'est ce recadrage qui en tient lieu.
