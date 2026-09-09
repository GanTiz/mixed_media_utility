# Le parcours complet, joué de bout en bout

Cette page est un **parcours exécutable**. Toutes les commandes qui y figurent
ont été jouées le 2026-09-07 sur les fixtures du dépôt, et les sorties citées
sont celles qu'elles ont rendues — pas des exemples reconstitués.

Si vous avez installé l'outil [depuis les sources](../installation/from-source.md),
vous pouvez recopier ce parcours ligne par ligne : les fichiers de départ sont
dans le dépôt. Si vous êtes parti d'une installation seule, remplacez
`tests/TEST_FILE.mp4` par votre propre rush — tout le reste est identique.

!!! note "Deux façons de taper la même commande"
    Ce guide écrit `mmu <sous-commande>`. Ce nom vient du raccourci `bin/mmu`,
    posé sur votre `PATH` par `scripts/install-mmu.sh` (voir
    [Ligne de commande](cli.md)). Partout où il n'est
    pas installé, la forme universelle
    `python -m mixed_media_utility.cli <sous-commande>` fait exactement la même
    chose, avec les mêmes options.

---

## Ce que fait l'outil, en une image

```
┌──────────────┐  extract   ┌───────────────────┐  makepdf   ┌──────────────┐
│  Rush vidéo  │ ─────────▶ │  Lot              │ ─────────▶ │  Planche PDF │
│  (mp4, mov…) │            │  frames extraites │            │  (à imprimer)│
└──────────────┘            └───────────────────┘            └──────┬───────┘
                                                                    │ papier
                                                                    ▼
┌──────────────┐  encode    ┌───────────────────┐   scan     ┌──────────────┐
│  Master      │ ◀───────── │  Lot scanné       │ ◀───────── │  Scan        │
│  (ProRes…)   │            │  frames scannées  │            │  (600 dpi)   │
└──────────────┘            └───────────────────┘            └──────────────┘
```

Le vocabulaire — projet, rush, lot, planche, scan, master, profil — est défini
dans [Concepts de base](concepts.md). Vous pouvez suivre ce parcours sans l'avoir
lu ; revenez-y quand un mot vous manque.

---

## Étape 0 — Se placer dans le dépôt

```bash
cd mixed_media_utility
```

Le rush de démonstration est `tests/TEST_FILE.mp4`. Mesuré avec `ffprobe` :
**1920 × 1080, h264, 25 im/s, 26 images, 1,05 s**. Il est volontairement minuscule :
le parcours entier tient en moins d'une minute de calcul.

**Si ce fichier fait 133 octets**

Les médias de test sont suivis par **Git LFS**. Sans `git-lfs` installé au
moment du clone, vous n'avez que des pointeurs, et la panne n'apparaît que
beaucoup plus loin, sur un message de décodage incompréhensible. Le
diagnostic tient en une commande :

```bash
git lfs ls-files -n | while read f; do
  [ -f "$f" ] && [ "$(stat -c%s "$f")" -lt 500 ] && echo "POINTEUR $f"
done
```

S'il sort quelque chose : installez `git-lfs`, puis `git lfs pull`.

---

## Étape 1 — Regarder le rush avant d'extraire (facultatif)

`previz` lit le rush à une ou plusieurs cadences réduites **sans rien écrire**.
C'est le geste qui répond à « est-ce que 12,5 im/s rend bien ? » avant d'engager
une extraction et une rame de papier.

```bash
mmu previz --video tests/TEST_FILE.mp4 --fps 5
```

Il ouvre une fenêtre de lecture. Sur une machine sans affichage, `--no-display`
mesure la cadence sans rien montrer — c'est ce qui a produit la sortie
ci-dessous :

```
Cadence 5 im/s
  frames presentees   : 6 / 6 attendues
  frames omises       : 0
  cadence effective   : 4.999 im/s
  temps reel          : tenu
previz terminee. 26 frame(s) decodee(s) […] Aucun fichier ecrit, aucun lot cree,
aucune extraction declenchee.
```

Plusieurs `--fps` peuvent être empilés pour comparer :
`mmu previz --video … --fps 3 --fps 5 --fps 12.5`.

---

## Étape 2 — Extraire un lot de frames

Il n'existe **pas** de commande « créer un projet » : le dossier est créé par la
première commande qui écrit dedans.

```bash
mmu extract --project demo --video tests/TEST_FILE.mp4 --fps 12.5 --yes
```

Avant d'écrire quoi que ce soit, `extract` affiche un récapitulatif complet — ce
que `ffprobe` a lu de la source, la sélection déterministe, la place que ça va
prendre — puis demande votre accord :

```
Selection deterministe (valeurs reprises telles quelles de la selection)
  Frames qui seront extraites (expected_frame_count): 13
  Frames source non retenues en fin de rush         : 1
  Premier timecode de la selection                  : 00:00:00:00 (base source, cadence 25/1)
  Dernier timecode de la selection                  : 00:00:00:24 (base source, cadence 25/1)
Sortie
  Dossier de lot (relatif au projet)                : extract-frames/TEST_FILE_12p5
  Occupation disque, borne haute non compressee     : 154.25 Mio
```

**`--yes` est ce consentement, donné d'avance.** Dans un terminal interactif,
vous pouvez l'omettre et répondre à la question. Hors terminal (script, CI,
session distante), l'omettre fait refuser la commande avec ce message, qui n'est
pas une erreur mais une demande :

> Confirmation non accordee: consentement absent en mode non interactif. Passer
> `--yes` pour donner l'accord sans terminal interactif.

Résultat mesuré :

```
13 frame(s) TIFF 16 bits ecrite(s) dans extract-frames/TEST_FILE_12p5
Manifest mis a jour: lot TEST_FILE_12p5 dans demo/project.json
```

Le rush **n'est pas copié** dans le projet : le manifeste note son chemin. Si
vous déplacez le fichier plus tard, `mmu relink` le raccroche.

Le nom du lot, `TEST_FILE_12p5`, se lit : *nom du rush* + *cadence*, le point
décimal écrit `p`. Il est calculé, jamais saisi.

Options qui servent vraiment :

| option | ce qu'elle fait |
|---|---|
| `--in` / `--out` | bornes en timecode source `hh:mm:ss:ff`, indépendantes l'une de l'autre |
| `--yes` | le consentement d'extraction, pour un usage sans terminal |
| `--accept-unknown-color` | consentement **supplémentaire** quand la colorimétrie de la source est absente ou incomplète |
| `--nouvelle-version` | écrire un lot voisin (`_v2`) au lieu de refuser |
| `--ecrasement-conscient` | écraser le lot en place, sciemment ; exige `--yes` |

---

## Étape 3 — Composer les planches imprimables

```bash
mmu makepdf --project demo --lot TEST_FILE_12p5
```

```
PDF ecrit: demo/planches/demo_TEST_FILE_12p5_2f-por.pdf (7 page(s))
makepdf termine avec succes. 7 page(s) (2 frame(s) par page,
template tpl-a4-portrait-2f-v2, patchs patches-17-v4)
Consigne de numerisation: scanner a 600 dpi minimum.
```

Treize frames à deux par page font sept planches. Chaque page porte :

* **les frames**, dans des emplacements repérés ;
* **un QR de page** — l'identité du lot, les timecodes, la géométrie, le préset
  de patchs. C'est lui qui rendra la page relisible plus tard, seule, sans le
  projet ;
* **des marqueurs ArUco** aux quatre coins, pour redresser la perspective ;
* **des pastilles de calibration** témoins.

Les défauts mesurés : format A4, orientation portrait, 2 frames par page,
géométrie `v2`, patchs `patches-17-v4`, compression de gamut
`gamut-map-none-1` (aucune). Ils se changent par `--format`, `--orientation`,
`--frames-par-page`, `--geometrie`, `--nombre-patchs`, `--gamut-map` et
`--marge` ; le détail des vocabulaires est dans la
[référence des commandes](../reference/commandes.md).

!!! tip "Relancer `makepdf` ne détruit rien"
    Le PDF existe déjà ? La deuxième exécution écrit
    `demo_TEST_FILE_12p5_2f-por_v2.pdf` **à côté** du premier, sans rien
    demander et sans rien écraser. C'est le versionnage
    décrit plus bas.

---

## Étape 4 — Imprimer

Imprimez le PDF. La seule consigne qui compte est celle que `makepdf` affiche
lui-même : **scanner à 600 dpi minimum**. Les seuils de détection ArUco et de
décodage QR sont réglés pour cette résolution.

---

## Étape 5 — Scanner, et récupérer les frames

```bash
mmu scan --project demo \
    --scan demo/planches/demo_TEST_FILE_12p5_2f-por.pdf \
    --dpi 600 --lot-slug boucle_01
```

!!! note "Tester la boucle sans imprimante"
    C'est exactement ce que fait la commande ci-dessus : `--scan` accepte un PDF
    multipage, donc on peut réingérer le PDF que `makepdf` vient d'écrire. Cela
    exerce toute la chaîne — géométrie, décodage QR, nommage, écriture — sans
    papier ni encre. Ça ne prouve **rien** sur la robustesse à l'impression, et
    rien non plus sur la couleur : sans encre ni capteur, il n'y a rien à
    corriger.

Sorties mesurées :

```
7 page(s) ingeree(s) dans scans/boucle_01 a 600 dpi (slug d'ingestion: boucle_01)
Avertissement d'ingestion: DPI_DECLARED_DIFFERS_FROM_FILE
Avertissement de detection: INGEST_SLUG_DIFFERS_FROM_LOT_ID
Aucune page de calibration lue dans ce lot: les frames sont ecrites telles
quelles et le manifest le declare (correction non appliquee).
Passe de sortie: 13 frame(s) ecrite(s) dans frames-scannees/TEST_FILE_12p5,
dont 0 de remplacement
Lot TEST_FILE_12p5: etat scan, 13 frame(s) reconstruite(s), […] lot complet
```

Ce qu'il faut retenir des deux paramètres :

* **`--dpi` est obligatoire et n'est jamais devinée.** Sur un PDF, elle pilote
  le rendu ;
* **`--lot-slug` est un nom de dossier d'opérateur**, pas une identité. Le
  `lot_id` réel est porté par le QR et n'est connu qu'au décodage — d'où
  l'avertissement `INGEST_SLUG_DIFFERS_FROM_LOT_ID`, qui est normal.

`scan` enchaîne quatre passes : ingestion (`scans/<slug>/` + `ingest.json`),
détection (ArUco, homographie, QR), découpe et écriture des **frames scannées**
(`frames-scannees/<lot>/`, préfixées `scan_`), puis mise à jour du manifeste.

Pour **juger la détection avant d'écrire un seul TIFF**, arrêtez-vous à la
détection, puis écrivez plus tard depuis le document produit :

```bash
mmu scan --project demo --scan <fichier> --dpi 600 detect
mmu scan-write --project demo --detection scans/<slug>/<document>.json
```

### Les avertissements attendus

| code | ce qu'il dit | faut-il agir ? |
|---|---|---|
| `DPI_DECLARED_DIFFERS_FROM_FILE` | le dpi annoncé n'est pas celui inscrit dans le fichier | non sur un PDF rendu ; vérifiez la valeur sur un scan réel |
| `INGEST_SLUG_DIFFERS_FROM_LOT_ID` | votre nom de dossier diffère du `lot_id` lu au QR | non, c'est la distinction normale |
| `PAGE_SLOT_COUNT_BELOW_TEMPLATE` | une page porte moins d'emplacements que son gabarit | non si c'est une page de calibration |

### Ranger un scan qui mélange plusieurs lots

Le tri en vrac se déclenche par l'**absence** de `--lot-slug` :

```bash
mmu scan --project demo --scan livraison.pdf --dpi 600
```

Chaque page part alors dans le lot que son QR désigne ; les pages étrangères
sont signalées sans être déplacées.

---

## Étape 6 — Encoder le master

```bash
mmu encode --project demo --lot TEST_FILE_12p5 --yes
```

Comme `extract`, `encode` montre d'abord ce qu'il va faire :

```
  Lot                 : TEST_FILE_12p5 (etat scan)
  Profil              : prores_hq -> conteneur .mov
  Resolution          : 1920x1080 (defaut, hd1080), source 4346x2445
  Cadence             : 25/1 im/s (26 echantillon(s) au master pour 13 frame(s) distincte(s) retenue(s))
  Frames              : 13 conformes pour 13 attendues
  Sortie              : demo/outputs/TEST_FILE_12p5_mmu_prores_hq.mov
  Correction couleur  : not_applied -- aucune correction active […]
  Constat             : APPROXIMATION_SRGB_TAGUEE_REC709
```

puis écrit :

```
Master ecrit: demo/outputs/TEST_FILE_12p5_mmu_prores_hq.mov
  26 frames a 25/1 im/s, 1920x1080, yuv422p10le
```

Le master est reconstruit **depuis les frames scannées**, jamais depuis le rush
d'origine : c'est tout l'objet du dispositif. Sept profils sont disponibles —
`prores_hq` (défaut), `prores_422`, `prores_lt`, `dnxhr_hq`, `dnxhr_hqx`,
`h264_delivery`, `hevc_delivery` — et l'encodeur correspondant doit être compilé
dans votre `ffmpeg` ; l'outil le vérifie et le dit.

Deux lignes du récapitulatif méritent d'être lues :

* **`Correction couleur`** dit si un profil de calibration a touché les pixels.
  Ici `not_applied`, parce que le parcours ci-dessus n'en a désigné aucun. C'est
  une issue légitime, pas un échec ;
* **`Constat : APPROXIMATION_SRGB_TAGUEE_REC709`** est une approximation assumée
  et déclarée : les valeurs viennent d'un scanner, donc sRGB de fait, et le
  master est étiqueté bt709. Les deux espaces partagent primaires et point
  blanc ; seule la courbe de transfert diffère.

---

## La calibration couleur, une fois par chaîne de scan

Un **profil de calibration** appartient à une *chaîne de scan*, pas à un
projet : il se règle une fois, puis resservira à tous les lots passés par elle.

La correction qu'il porte couvre bien toute la boucle — l'imprimante, le papier,
l'encre, le scanner. Mais **l'identité** de la chaîne, celle par laquelle l'outil
reconnaît « la même chaîne », est dérivée du seul côté qu'il peut mesurer sur un
fichier : le **scanner** (marque, modèle, pilote, lus dans les tags quand ils y
sont), le **format d'entrée** et la **résolution déclarée**. C'est
`scan_chain.derive_chain_id`, un condensat déterministe et inter-machine — donc
identique sur deux postes.

!!! warning "Ce que cette identité ne distingue pas, et il faut le savoir"
    Deux imprimantes ou deux papiers différents, scannés sur le même scanner à
    la même résolution, donnent la **même** chaîne. Si vous changez de papier,
    donnez à la nouvelle calibration une étiquette qui le dit.

    **La suite diffère selon l'interface, et c'est mesuré le 2026-09-07 :**

    * dans la **TUI**, recalibrer une chaîne qui porte déjà un profil ouvre un
      écran qui le dit et propose les deux issues — remplacer, ou garder les
      deux (`EPIC11-ARB-261`) ;
    * en **ligne de commande**, `scan … calibrate` écrit le second fichier
      **sans un mot**, et l'ancien reste là sans que rien ne le signale. Le
      balayage qui reconnaît la chaîne existe dans le cœur
      (`io/calibration_profile.profils_de_la_chaine`) mais la CLI ne l'appelle
      pas. Relisez `versions/calibration/` après coup.

```bash
# 1. Générer la page de calibration (--project appartient à makepdf,
#    pas à la sous-commande)
mmu makepdf --project demo calibration-page --chaine "HP ENVY La Seyne"
```

```
page de calibration ecrite: demo/planches/demo_HP-ENVY-La-Seyne-bacfe03b_calibration.pdf
(chaine "HP ENVY La Seyne", template tpl-a4-portrait-2f-v2, a scanner a 600 dpi minimum)
```

Imprimez-la, scannez-la, puis tirez-en le profil. Le dépôt porte le scan réel
d'une telle page, ce qui permet de jouer l'étape sans imprimante :

```bash
# 2. En tirer le profil de la chaîne
mmu scan --project demo \
    --scan "tests/fixtures/scans/Page calibration HP ENVY La Seyne.pdf" \
    --dpi 600 calibrate --nom "HP ENVY La Seyne"
```

```
Calibration consignee pour la chaine '600-pdf-19ab02221d95' sous l'etiquette
'HP ENVY La Seyne': forme color-correction-tone-curve-chroma-1,
130 pastille(s) lue(s), 130 retenue(s), 17 temoin(s) mesure(s) brut(s),
source hp-envy-4520-tiff-600-dpi-auto-corr-off-p0.
Fichier: demo/versions/calibration/hp-envy-la-seyne.json
```

Le profil ne s'applique **qu'aux scans qui le désignent**. Deux façons :

```bash
# 3a. pour ce seul scan
mmu scan --project demo --scan <fichier> --dpi 600 \
    --profil demo/versions/calibration/hp-envy-la-seyne.json

# 3b. ou une fois pour toutes, pour ce projet
mmu set-default-profile --project demo \
    --profil demo/versions/calibration/hp-envy-la-seyne.json
```

**Aucun profil n'est choisi à votre place.** Sans profil désigné ni profil par
défaut, le lot est livré **en brut** : les frames sont écrites telles quelles et
le manifeste le déclare `not_applied`. C'est une issue légitime, et le message
qui l'annonce nomme les trois suites possibles.

!!! warning "Un profil de chaîne réelle ne s'applique pas à la boucle sans imprimante"
    Mesuré : en désignant le profil `hp-envy-la-seyne` sur la réingestion du PDF
    généré, chaque page sort avec un écart de **32,05 dE76** aux témoins de la
    page de calibration, très au-delà du seuil de 5,00. L'outil applique quand
    même la correction et le dit, page par page — « une correction imparfaite
    reste plus proche de la source que pas de correction du tout ». C'est
    normal : le PDF réingéré n'est jamais passé par l'encre ni par le capteur
    que ce profil décrit.

---

## Le versionnage : rien n'est jamais écrasé en silence

**Cinq objets sont versionnables** : les lots, les masters, les planches, les
scans, et les **lots scannés** — c'est-à-dire chaque passe de scan d'un même
lot. Tous suivent la même règle de rang (`_v2` … `_v99`).

Face à une sortie qui existe déjà, l'outil ne bloque jamais sèchement et
n'écrase jamais tout seul. Voici ce qu'a rendu un deuxième `scan` sur un lot
déjà scanné :

```
Echec de l'ecriture des frames: 13 fichier(s) de sortie existent deja dans
TEST_FILE_12p5 […]. Rien n'a ete ecrit. Trois issues: relancer avec
--nouvelle-version pour ecrire un jeu VOISIN sans toucher a celui-ci (le rang
entre dans le nom du dossier, ce qui permet de comparer deux profils de
calibration); relancer avec --overwrite pour les reecrire; ou supprimer ce lot
(`mmu project remove --lot <id>`).
```

Avec `--nouvelle-version`, la deuxième passe s'écrit à côté :

```
7 page(s) ingeree(s) dans scans/boucle_02_v2 a 600 dpi (slug d'ingestion: boucle_02)
Passe de sortie: 13 frame(s) ecrite(s) dans frames-scannees/TEST_FILE_12p5_v2,
dont 0 de remplacement
Constat de persistance: ETAT_DE_LOT_CONSERVE
```

Le scénario que cette règle sert : vous avez imprimé une planche, l'avez
scannée, puis vous ajoutez un détail au feutre sur une frame et vous rescannez.
Le contenu a changé, l'identité non — ce n'est ni un doublon, ni une erreur,
c'est une version. Et si vous vouliez vraiment écraser, `--overwrite` le fait,
après avertissement : la rigueur de l'outil n'empêche pas une écriture
destructive **consciente**.

`makepdf` est le seul à verser le rang sans qu'on le demande, parce qu'une
planche n'est jamais qu'un tirage de plus.

---

## Supprimer, la troisième opération

Sans suppression, le versionnage ne fait que remplir le disque : une version de
lot 4K à 12 im/s pèse plus de 2 Go. `project remove` retire du manifeste **et**
du disque.

Il fonctionne en deux temps. Sans `--confirmer`, il n'écrit rien :

```bash
mmu project remove --project demo --lot TEST_FILE_12p5 --planche --version 2
```

```
Apercu: element 'TEST_FILE_12p5 (planche 2)', 1 fichier(s)
    planches/demo_TEST_FILE_12p5_2f-por_v2.pdf
  Ce planche est le DERNIER a date. Son rang reste CONSOMME par defaut: le
  prochain planche sera le v3. Pour rendre le(s) rang(s) 2 […] relancer avec
  --liberer-le-rang.
Aucune ecriture. Relancer avec --confirmer pour supprimer.
```

Puis, avec `--confirmer`, la même ligne supprime réellement.

**On désigne un objet par les arguments qui l'ont produit**, plus son rang — la
même syntaxe pour tous :

```bash
mmu project remove --project demo --lot <lot_id> --confirmer                          # le lot entier
mmu project remove --project demo --lot <lot_id> --planche --version 2 --confirmer    # une planche
mmu project remove --project demo --lot <lot_id> --lot-scanne --confirmer             # une passe de scan
mmu project remove --project demo --lot <lot_id> --scan <slug> --confirmer            # un dossier de scan
mmu project remove --project demo --lot <lot_id> --master --profile prores_422 --confirmer
mmu project remove --project demo --rush <rush_id> --confirmer                        # un rush et sa descendance
```

Un master se retrouve donc par son profil d'encodage, jamais par un chemin : son
emplacement est au manifeste. Sans `--version`, la cible est le rang d'origine,
celui qui ne porte aucun fragment `_vN`.

Par défaut, **le rang d'un objet supprimé reste consommé** : après avoir retiré
la planche `_v2`, la suivante sera `_v3`. `--liberer-le-rang` le rend — sur le
dernier à date seulement.

---

## Reconstruire un projet reçu sans manifeste

Une planche imprimée porte toute son identité dans son QR. Un projet peut donc
être reconstitué à partir des seuls textes décodés :

```bash
mmu reconstruct-project --project demo --payload page-01.txt --payload page-02.txt
```

Chaque `--payload` contient le texte exact du QR d'une page, tel qu'un décodeur
le rend. `--manifest` permet de partir d'un `project.json` partiel existant.

---

## Relire le manifeste

Après chaque étape, `project.json` dit ce que l'outil croit savoir :

```bash
python3 -m json.tool demo/project.json | less
```

Les clés à contrôler sur un lot :

| clé | ce qu'elle porte |
|---|---|
| `state` | `extraction`, `pdf`, `scan`, `reconstruction`, `encode` |
| `frames_dir` | le dossier des **frames extraites** (`extract-frames/<lot>`) |
| `output_frames_dir` | le dossier des **frames scannées** (`frames-scannees/<lot>`) — le nom de la clé est l'ancien vocabulaire, sa valeur suit le disque |
| `reconstructed_frame_count` | le cardinal des frames scannées écrites |
| `synthetic_frame_count` | les frames de remplacement, écrites pour les pages illisibles |

---

## Quand ça ne marche pas

| symptôme | cause probable | geste |
|---|---|---|
| `Confirmation non accordee` | pas de terminal interactif | ajouter `--yes` |
| `Payload sans version: la cle 'sv' est absente` | le document scanné n'est pas une planche du dispositif — ou une planche imprimée sous l'ancien format de QR, qui n'est plus lu | rescanner le bon document ; une planche au format retiré doit être régénérée |
| QR illisible | impression trop basse, page pliée | réimprimer, scanner à 600 dpi |
| ArUco non détecté | contraste faible, coin corné | s'arrêter à `scan … detect` pour juger avant d'écrire |
| `Aucune planche n'a livre son QR` | mauvais document, ou résolution insuffisante | rien n'a été écrit ; l'ingestion, elle, a eu lieu |
| Frames scannées décalées | mauvais gabarit | vérifier `template_id` au manifeste |
| `Binaire ffmpeg introuvable dans le PATH` | `ffmpeg` absent | voir la page d'installation de votre plateforme |
| `frames/` et `output-frames/` sur le disque | projet créé avant le renommage des dossiers | rien à faire, ces noms restent lus |
