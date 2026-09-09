# Configuration

**Il n'y a presque rien à configurer**, et c'est délibéré : l'outil ne devine
rien, donc il n'a pas de réglages pour orienter ses devinettes. Tout ce qui
change un résultat se passe en option de ligne de commande, ou se choisit dans
l'interface.

Cette page recense ce qui existe vraiment, relevé dans le code le 2026-09-07.

---

## Variables d'environnement

### Celles que vous pouvez poser

| variable | défaut | effet |
|---|---|---|
| `NO_COLOR` | non posée | sa **seule présence** — quelle que soit sa valeur, y compris vide — éteint la couleur de la TUI. C'est la convention établie ; l'option `--sans-couleur` en est la forme explicite |
| `ESCDELAY` | `25` via les raccourcis `bin/` | délai, en millisecondes, que `textual` attend avant de décider qu'un `Échap` est bien un `Échap` et non le début d'une séquence. Une valeur posée par vous **survit** : sur un terminal distant ou lent, monter à 100 est le bon choix |
| `XDG_CONFIG_HOME` | `~/.config` | où vit la liste des projets récents, sur Linux et macOS |
| `APPDATA` | `%USERPROFILE%\AppData\Roaming` | idem, sur Windows |
| `PYTHONPATH` | — | posé par les raccourcis `bin/mmu` et `bin/mmu-tui`, qui y **ajoutent** `src/` sans jamais écraser ce que vous y aviez mis |

### Celles que l'outil lit sans que vous les posiez

Pour décider s'il doit replier les glyphes en ASCII, `mmu-tui` interroge son
hôte — et **uniquement des variables que l'hôte pose lui-même** :
`WT_SESSION`, `TERM_PROGRAM`, `TERM`, `ConEmuANSI`, `MSYSTEM`.

Aucune variable d'environnement propre à l'outil n'a été inventée. Le repli
ASCII se demande par `--ascii` et se refuse par `--utf8`, pas par une variable.

`mmu-tui --diagnostic-chemin` affiche exactement ce que ces variables valent sur
votre machine, et le motif de la décision qui en découle.

---

## Fichiers

### Dans le projet

| fichier | rôle |
|---|---|
| `project.json` | le **manifeste** : rushes, lots, planches, scans, masters, profils versés. Validé contre un schéma JSON à chaque écriture |
| `versions/calibration/<slug>.json` | un **profil de calibration** de chaîne de scan |
| `scans/<slug>/ingest.json` | le rapport d'ingestion d'un scan |
| `scans/<slug>/detections/*.json` | les documents de détection, consommables par `scan-write` |
| `logs/*.log` | un journal par commande : `extract`, `makepdf`, `scan`, `encode`, `calibration-profile` |

Tout est du JSON lisible. Rien n'est chiffré, rien n'est binaire hormis les
images et les vidéos.

### Hors du projet

L'outil écrit **la liste des projets récents**, et elle ne contient rien
d'autre que cette liste :

| plateforme | emplacement |
|---|---|
| Linux, macOS | `$XDG_CONFIG_HOME/mixed_media_utility/recents-v1.json`, sinon `~/.config/mixed_media_utility/recents-v1.json` |
| Windows | `%APPDATA%\mixed_media_utility\recents-v1.json` |

La supprimer ne perd que l'ordre de la liste d'accueil.

S'y ajoute, **si vous l'avez accepté à l'installation**, le raccourci qui lance
l'interface hors du terminal — et lui seul :

| plateforme | emplacement |
|---|---|
| Linux | `$XDG_DATA_HOME/applications/mmu-tui.desktop`, sinon `~/.local/share/applications/mmu-tui.desktop` |
| Windows | `mmu-tui.lnk`, dans le menu Démarrer de votre compte |
| macOS | aucun : l'installateur n'en pose pas |

`install.sh --desinstaller` et `install.ps1 -Desinstaller` le retirent ; les
pages d'installation donnent aussi la commande pour le faire à la main.

!!! warning "Il n'y a pas de fichier de thème"
    Aucun `tui.css`, aucun fichier de préférences, aucune surcharge de couleurs
    par l'utilisateur. L'apparence de la TUI n'est réglable que par
    `--sans-couleur` et `--ascii` / `--utf8`.

---

## Les vocabulaires figés

Ces valeurs ne se configurent pas : elles se **choisissent** parmi une liste
close, et l'identifiant retenu est inscrit dans la planche puis relu au scan.
C'est ce qui permet à une planche imprimée de rester redressable des mois plus
tard, à partir d'elle seule.

### Mise en page — `makepdf`

| réglage | valeurs | défaut |
|---|---|---|
| format | `A4` (210 × 297 mm) | `A4` |
| orientation | `portrait`, `paysage` | `portrait` |
| frames par page | portrait : 1, 2, 3, 4, 8 — paysage : 1, 2, 4, 6, 8 | `2` |
| marge de recadrage | 0, 2 ou 5 mm | `0` |
| géométrie | `v1`, `v2` | `v2` |
| patchs | `patches-9-v1`, `patches-12-v1`, `patches-18-v2`, `patches-14-v3`, `patches-17-v4` | `patches-17-v4` |
| compression de gamut | `gamut-map-none-1`, `gamut-map-lin-1` | `gamut-map-none-1` |

Seuls `patches-18-v2`, `patches-14-v3` et `patches-17-v4` portent des
**sentinelles de gamut**, requises par le verdict d'écrêtage. Les deux presets
`v1` restent résolvables : les planches déjà imprimées sous eux restent
relisibles.

### Encodage — `encode`

| réglage | valeurs | défaut |
|---|---|---|
| profil | `prores_hq`, `prores_422`, `prores_lt`, `dnxhr_hq`, `dnxhr_hqx`, `h264_delivery`, `hevc_delivery` | `prores_hq` |
| résolution | `hd1080` (1920 × 1080), `uhd2160` (3840 × 2160), `native`, ou `<largeur>x<hauteur>` | `hd1080` |

`native` n'est pas une entrée du registre : c'est un mot réservé qui désigne la
géométrie réelle des frames scannées, connue seulement après les avoir sondées.

L'encodeur correspondant au profil doit être **compilé dans votre `ffmpeg`**.
L'outil lit la sortie de `ffmpeg -encoders` et refuse en le nommant si
l'encodeur manque — il ne se contente pas d'un code de retour, qui vaut zéro
même pour un encodeur inexistant.

### Correction couleur — `scan`, `scan-write`

| réglage | valeurs | défaut |
|---|---|---|
| `--cc` | `on`, `off` | `on` |

Deux valeurs et rien d'autre : **on refuse une correction, on ne la dose pas.**
Aucun réglage numérique n'est exposé, et il n'en existera pas.

---

## Quelques valeurs internes, pour lire les messages

Elles ne se configurent pas ; elles sont ici parce qu'elles apparaissent dans
des refus et qu'il est utile de savoir d'où sort le chiffre.

| valeur | mesurée | ce qu'elle borne |
|---|---|---|
| marqueurs ArUco minimum | **4** | en dessous, l'homographie n'est pas résolue et la page est refusée |
| pastilles par page, plafond | **36** | borne de composition d'un préset de patchs |
| longueur d'identifiant canonique | **48** caractères | au-delà, un identifiant est raccourci de façon déterministe |
| emplacements par page au budget nominal du QR | **11** | ce qu'un payload de page peut porter sans déborder |
| consigne de numérisation | **600 dpi** | en dessous, QR et marqueurs cessent d'être lisibles de façon fiable |

---

## Ce qui n'est pas configurable, et pourquoi

* **Le choix d'un profil de calibration.** Aucun appariement automatique : un
  profil s'applique parce que vous l'avez désigné, sinon le lot sort en brut et
  le manifeste le déclare. Un profil deviné serait pire qu'aucun ;
* **La résolution d'un scan.** `--dpi` est exigée, jamais déduite du fichier ;
* **La cadence source d'un rush.** Jamais repliée sur la cadence cible ;
* **Le dosage d'une correction couleur.** `on` ou `off` ;
* **Le comblement d'un trou dans un lot.** Aucune image n'est jamais répétée
  pour masquer une frame manquante : l'incomplétude se déclare
  (`--accept-incomplete-lot`), elle ne se maquille pas.
