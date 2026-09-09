# Référence des commandes

Cette page est **dérivée du code** — l'arbre d'options de
`src/mixed_media_utility/cli.py`, relevé le 2026-09-07. Elle liste ce qui
existe ; le guide utilisateur dit quand s'en servir.

Toute commande s'obtient aussi de première main :

```bash
mmu <sous-commande> --help
```

---

## Les deux exécutables

| exécutable | ce qu'il lance | d'où il vient |
|---|---|---|
| `mmu` | la ligne de commande | `[project.scripts]` de **`mmu-cli`** |
| `mmu-tui` | l'interface en terminal | `[project.scripts]` de **`mmu-tui`**, qui dépend de `mmu-cli` |

Deux distributions, un seul cœur : `mmu-tui` déclare `mmu-cli` en dépendance,
donc l'installer donne les deux commandes sans poser le cœur deux fois. La
distribution porte le nom `mmu-cli` parce que `mmu` est déjà pris sur l'index
public ; la commande, elle, est bien `mmu`.

Le dépôt cloné garde son propre `bin/mmu`, mis sur le `PATH` par
`scripts/install-mmu.sh` (ou `.ps1`) — c'est le chemin de développement, pas
celui d'un utilisateur.

Troisième forme, partout où le paquet est **importable** — donc une
installation en venv, pas un `pipx install` qui isole :

```bash
python -m mixed_media_utility.tui      #  ==  mmu-tui
python -m mixed_media_utility.cli      #  ==  mmu
```

### Options de `mmu-tui`

| option | effet |
|---|---|
| `--sans-couleur` | n'émet aucune couleur. Actif d'office si `NO_COLOR` est posée |
| `--ascii` | force le repli ASCII des glyphes |
| `--utf8`, `--pas-d-ascii` | refuse le repli ASCII, même si l'hôte a l'air incapable |
| `--diagnostic-chemin` | imprime l'environnement vu par la TUI, puis sort |

### Options globales de `mmu`

| option | effet |
|---|---|
| `--version` | affiche la version du paquet |
| `-h`, `--help` | l'aide, à tout niveau de l'arbre |

---

## Les onze sous-commandes

| sous-commande | rôle | sous-commandes propres |
|---|---|---|
| [`previz`](#previz) | prévisualiser un rush à des cadences réduites | — |
| [`extract`](#extract) | extraire un lot de frames TIFF | — |
| [`makepdf`](#makepdf) | composer les planches imprimables | `calibration-page` |
| [`scan`](#scan) | ingérer des pages scannées et écrire les frames | `detect`, `calibrate` |
| [`scan-write`](#scan-write) | écrire les frames depuis une détection déjà faite | — |
| [`encode`](#encode) | reconstruire un master | — |
| [`set-default-profile`](#set-default-profile) | poser le profil de calibration par défaut | — |
| [`relink`](#relink) | raccrocher un rush déplacé | — |
| [`project`](#project) | maintenance du projet | `remove`, `add-rush` |
| [`reconstruct-project`](#reconstruct-project) | reconstituer un projet depuis des QR | — |
| [`poc`](#poc) | orchestration de bout en bout | `build-sheet`, `process-scan` |

`--project` désigne le dossier de projet. Il est **exigé partout sauf par
`previz`**, qui n'écrit rien.

---

## `previz`

Lit un rush à une ou plusieurs cadences réduites. **N'écrit aucun fichier, ne
crée aucun lot, ne déclenche aucune extraction.**

```bash
mmu previz --video <rush> --fps <cadence>
mmu previz --video <rush> --fps 3 --fps 5 --fps 12.5
```

| option | défaut | effet |
|---|---|---|
| `--video` | *(exigé)* | fichier vidéo source |
| `--fps` | *(exigé)* | cadence à prévisualiser ; **répétable** pour comparer |
| `--height` | `540` | hauteur d'affichage, en pixels |
| `--in`, `--out` | — | bornes en timecode source `hh:mm:ss:ff`. Changent **quelles images sont retenues**, comme pour `extract` |
| `--start`, `--duration` | — | plage jouée dans cette session, en secondes. Ne change **pas** la sélection |
| `--on-late` | `report` | `report` présente tout et chiffre l'écart ; `skip` omet les frames en retard pour préserver le tempo perçu |
| `--memory-budget-mb` | `128` | budget du cache de frames décodées |
| `--no-display` | — | cadencer et mesurer sans ouvrir de fenêtre |

---

## `extract`

Tire un lot de frames TIFF 16 bits déterministe depuis un rush, sous
`extract-frames/<lot>/`.

```bash
mmu extract --project <dossier> --video <rush> --fps <cadence> --yes
```

| option | effet |
|---|---|
| `--project` | dossier projet, **créé s'il est absent** |
| `--video` | fichier vidéo source |
| `--fps` | cadence cible, en images par seconde |
| `--in`, `--out` | bornes en timecode source `hh:mm:ss:ff`, incluses, indépendantes l'une de l'autre |
| `--yes`, `-y` | consentement d'extraction, pour un usage sans terminal interactif |
| `--accept-unknown-color` | consentement **supplémentaire** quand la colorimétrie source est absente ou incomplète |
| `--nouvelle-version` | sur un lot déjà passé au-delà de l'état `extraction` : en créer une version voisine (`_v2`…) plutôt que refuser |
| `--ecrasement-conscient` | l'écraser **sciemment** en place. Exige `--yes`, incompatible avec `--nouvelle-version` |
| `--overwrite` | remplacer un lot déjà présent dans le dossier de lot |

---

## `makepdf`

Compose le PDF de planches imprimables d'un lot, sous `planches/`.

```bash
mmu makepdf --project <dossier> --lot <lot_id>
mmu makepdf --project <dossier> --rush <rush_id> --fps <cadence>
```

| option | défaut | effet |
|---|---|---|
| `--lot` | — | `lot_id` direct |
| `--rush` + `--fps` | — | l'autre façon de désigner le même lot |
| `--format` | `A4` | format de page (vocabulaire : `A4`) |
| `--orientation` | `portrait` | `portrait` ou `paysage` |
| `--frames-par-page` | `2` | portrait : 1, 2, 3, 4, 8 — paysage : 1, 2, 4, 6, 8. Un cardinal retiré est refusé en nommant celui à employer |
| `--marge` | `0` | préset de marge de recadrage, en mm : 0, 2 ou 5. Relu au scan depuis le QR |
| `--geometrie` | `v2` | `v1` ou `v2`. Portée par le `template_id` et relue au scan : une planche imprimée reste redressable |
| `--dpi` | `600` | rastérisation des éléments embarqués. **Distinct de la consigne de scan**, qui reste 600 dpi |
| `--nombre-patchs` | `patches-17-v4` | `patches-9-v1`, `patches-12-v1`, `patches-18-v2`, `patches-14-v3`, `patches-17-v4` — ou leur cardinal. Sentinelles de gamut : seuls `18-v2`, `14-v3` et `17-v4` en portent |
| `--gamut-map` | `gamut-map-none-1` | `gamut-map-none-1` (aucune) ou `gamut-map-lin-1` |
| `--nouvelle-version` | — | écrire une version voisine plutôt que refuser |
| `--overwrite` | — | remplacer le PDF présent |

!!! note
    Sans option de version, une deuxième exécution écrit **d'elle-même** un
    `_v2` à côté du premier PDF : une planche n'est jamais qu'un tirage de plus.

### `makepdf calibration-page`

Génère la page de calibration d'une chaîne de scan. Elle **n'est plus insérée
automatiquement** dans un lot, et ne demande ni rush, ni lot, ni cadence : elle
se génère avant toute extraction.

```bash
mmu makepdf --project <dossier> calibration-page --chaine "<libellé>"
```

| option | effet |
|---|---|
| `--chaine` | libellé de la chaîne de scan. **Obligatoire** |
| `--commentaire` | texte libre attaché à la page |

---

## `scan`

Ingère un lot de pages scannées — dossier d'images, image unique ou PDF
multipage — puis détecte, découpe et écrit les frames.

```bash
mmu scan --project <dossier> --scan <source> --dpi <valeur> --lot-slug <slug>
```

| option | effet |
|---|---|
| `--scan` | dossier d'images, image unique (png/jpg/tiff) ou PDF multipage |
| `--dpi` | résolution déclarée. **Obligatoire, jamais devinée** ; sur un PDF elle pilote le rendu |
| `--lot-slug` | nom du dossier sous `scans/`. C'est un slug **opérateur**, pas un `lot_id`. Son absence déclenche le tri en vrac |
| `--profil` | profil de calibration à appliquer à ce scan. Peut vivre hors du projet ; il y est versé à l'usage |
| `--cc` | `on` *(défaut)* ou `off`. À `off`, la correction est quand même **ajustée et mesurée** au manifeste, mais posée sur aucun pixel |
| `--garder-le-scan-brut` | livrer le lot brut, sans correction et sans invite |
| `--appliquer-la-correction-de-calibration-telle-quelle` | conservé pour compatibilité : la correction s'applique de toute façon depuis la story 5.23, ce drapeau n'inscrit plus qu'une trace au manifeste |
| `--nouvelle-version` | ingérer un scan voisin (`scans/<slug>_v2/`) quand le slug porte déjà un contenu différent |
| `--overwrite` | réécrire les frames de sortie déjà présentes |

### `scan detect`

Détecte et écrit un **document de détection** — géométries, zones, payloads
décodés, statuts, provenance — sous `scans/<slug>/detections/`. **N'écrit aucune
frame et ne touche pas au manifeste** : c'est le point d'arrêt pour juger avant
d'écrire un seul TIFF.

```bash
mmu scan --project <dossier> --scan <source> --dpi 600 detect
```

### `scan calibrate`

Ajuste la correction sur une page de calibration scannée et la consigne sous
`versions/calibration/<slug>.json`.

```bash
mmu scan --project <dossier> --scan <page> --dpi 600 calibrate --nom "<libellé>"
```

| option | effet |
|---|---|
| `--nom` | nom sous lequel relire ce profil. Sans lui, la question est posée sur un terminal |
| `--commentaire` | commentaire libre attaché au profil |

Le profil ne s'applique ensuite **que par désignation** — `--profil` ou
`set-default-profile` —, jamais par appariement automatique.

---

## `scan-write`

Écrit les frames d'un lot depuis un document produit par `scan detect`, **sans
relancer la détection**.

```bash
mmu scan-write --project <dossier> --detection scans/<slug>/detections/<fichier>.json
```

Porte les mêmes options d'écriture que `scan` : `--profil`, `--cc`,
`--garder-le-scan-brut`, `--appliquer-la-correction-de-calibration-telle-quelle`,
`--overwrite`.

---

## `encode`

Reconstruit un master vidéo **depuis les frames scannées** du lot, sous
`outputs/<lot>_mmu_<profil>.<conteneur>`.

```bash
mmu encode --project <dossier> --lot <lot_id> --yes
```

| option | défaut | effet |
|---|---|---|
| `--lot` | *(exigé)* | `lot_id` du lot scanné à encoder |
| `--profile` | `prores_hq` | `prores_hq`, `prores_422`, `prores_lt`, `dnxhr_hq`, `dnxhr_hqx`, `h264_delivery`, `hevc_delivery` |
| `--resolution` | `hd1080` | `hd1080`, `uhd2160`, `native` (géométrie des frames scannées), ou `<largeur>x<hauteur>` |
| `--yes`, `-y` | — | consentement d'encodage, pour un usage sans terminal |
| `--accept-incomplete-lot` | — | encoder un lot définitivement incomplet. **Aucun trou n'est jamais comblé par répétition de l'image précédente** |
| `--nouvelle-version` | — | écrire une version voisine du master. Incompatible avec `--overwrite` |
| `--overwrite` | — | remplacer le master présent |
| `--cadence-source` | — | cadence source du rush, exigée seulement si le lot ne la porte pas. **Prime** sur celle du lot quand les deux existent : le papier ne se met pas à jour |

---

## `set-default-profile`

Pose le profil de calibration par défaut du projet, utilisé par les scans qui ne
passent pas `--profil`.

```bash
mmu set-default-profile --project <dossier> --profil <fichier.json>
```

Le profil peut vivre hors du projet : il y est versé, fichier et entrée de
manifeste, sans refus lié à sa provenance.

---

## `relink`

Remplace le chemin du rush source d'un projet — fichier déplacé, renommé,
archivé.

```bash
mmu relink --project <dossier> --rush <rush_id> --video <nouveau-chemin>
mmu relink --project <dossier> --rush <rush_id> --chercher <dossier>
```

| option | effet |
|---|---|
| `--rush` | `rush_id` canonique. **Omissible** si le projet ne porte qu'un seul rush |
| `--video` | désignation manuelle. L'opérateur fait autorité : un critère d'identité vérifiable qui échoue refuse le relink, mais aucun ne le contourne en silence |
| `--chercher` | dossier parcouru récursivement, par les trois critères d'identité — nom, durée, timecode de départ. Refuse si l'un des trois manque au manifeste : **la recherche ne devine jamais** |

---

## `project`

### `project add-rush`

Déclare un rush au projet, sans rien extraire.

```bash
mmu project add-rush --project <dossier> --video <fichier>
```

`--force-distinct` déclare un second rush malgré une identité proche d'un rush
déjà présent.

### `project remove`

Retire un élément **du manifeste et du disque**. Sans `--confirmer`, n'écrit
rien et affiche ce qui partirait.

```bash
mmu project remove --project <dossier> --lot <lot_id> --confirmer
mmu project remove --project <dossier> --rush <rush_id> --confirmer
```

| option | effet |
|---|---|
| `--lot` / `--rush` | l'objet visé. `--rush` refuse s'il porte encore des lots : **aucune suppression en cascade** |
| `--confirmer` | effectuer réellement la suppression |

Sans cible fine, c'est le lot entier. Avec, une seule cible à la fois :

| cible fine | ce qu'elle retire |
|---|---|
| `--planche` | une planche produite par `makepdf` |
| `--master --profile <id>` | un master produit par `encode`. `--resolution` n'est exigée que si elle lève une ambiguïté |
| `--scan <slug>` | un dossier de scan seul, le lot restant en place. Le slug est la **famille**, privée de son fragment de version |
| `--lot-scanne` | une passe de scan, c'est-à-dire un jeu de frames scannées |
| `--frames-extraites` | le jeu de frames extraites. N'accepte ni `--version` ni `--liberer-le-rang`, et les refuse en le disant |

| option de rang | effet |
|---|---|
| `--version <rang>` | le rang de la version visée. **Exige une cible fine** ; sans elle il est refusé, le rang d'un lot vivant dans son `lot_id`. Sans `--version`, la cible est le rang d'origine |
| `--liberer-le-rang` | rendre le rang au lieu de le laisser consommé. **Uniquement sur le dernier à date** ; refusé nommément sur un `--rush`, qui n'a pas de rang |
| `--avec-scans` | inclure le dossier de scan lié. Consentement **séparé** de `--confirmer` |
| `--confirmer-dernier-lot` | consentement **supplémentaire**, exigé pour vider un projet de son dernier lot ou de son dernier rush |

**On désigne un objet par les arguments qui l'ont produit**, plus son rang. Un
master se retrouve donc par son profil d'encodage, jamais par un chemin : son
emplacement est au manifeste.

---

## `reconstruct-project`

Reconstruit un projet local depuis des payloads de page décodés, et un manifeste
partiel optionnel.

```bash
mmu reconstruct-project --project <dossier> --payload <page-01> --payload <page-02>
```

| option | effet |
|---|---|
| `--payload` | fichier contenant le texte **exact** du QR d'une page, tel qu'un décodeur le rend. Répétable, un par page disponible |
| `--manifest` | `project.json` partiel existant, facultatif |

---

## `poc`

Orchestration de bout en bout, destinée à la mise au point plutôt qu'à l'usage
courant.

```bash
mmu poc build-sheet   --project <dossier> --video <rush> --fps <cadence> --dpi 600
mmu poc process-scan  --project <dossier> --scan <source> --dpi 600
```

---

## Ce que la CLI ne fait pas

* **il n'y a pas de commande « créer un projet »** : le dossier naît de la
  première commande qui écrit dedans ;
* **il n'y a pas de commande de listing** : l'inventaire d'un projet se lit dans
  `project.json`, ou dans l'atelier *Projet* de la TUI ;
* **aucune commande ne devine** : `--dpi` est exigée, aucun profil de
  calibration n'est choisi automatiquement, aucune cadence source n'est déduite
  de la cadence cible.
