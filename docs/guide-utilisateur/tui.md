# L'interface en terminal (TUI)

La TUI est le **chemin nominal** : elle enchaîne les mêmes traitements que la
ligne de commande, mais elle vous montre ce qu'elle va faire avant de le faire,
et elle vous laisse choisir dans des listes plutôt que de vous faire écrire des
identifiants.

```bash
mmu-tui
```

Les écrans reproduits ci-dessous ont été **capturés le 2026-09-07** sur un
projet réel.

---

## Premier lancement : choisir un projet

Il n'y a rien à configurer. La TUI s'ouvre sur un explorateur de dossiers,
positionné dans votre répertoire courant :

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ mmu · - · Projet                                                             │
│──────────────────────────────────────────────────────────────────────────────│
│                                                                              │
│   Ouvrir un projet                                                           │
│                                                                              │
│    ←  …/user/                                                                │
│      Dossier du projet    /home/user/mixed_media_utility                     │
│   ────────────────────────────────────────────────────────────────────────   │
│    ▸ _bmad/                                                8 sous-dossiers   │
│      bin/                                                  0 sous-dossier    │
│      docs/                                                 5 sous-dossiers   │
│      …                                                          1-8 sur 11   │
│   ────────────────────────────────────────────────────────────────────────   │
│    ⏎  Valider   _bmad/                                                       │
│                                                                              │
│──────────────────────────────────────────────────────────────────────────────│
│ 11 sous-dossiers · aucun projet · 7 dossiers cachés                          │
│ ⏎ valider  → entrer  ← parent  ↑↓ liste  Ctrl+H cachés  Échap sortir         │
└──────────────────────────────────────────────────────────────────────────────┘
```

Trois choses à savoir tout de suite :

* **la ligne du bas dit toujours quelles touches marchent ici.** C'est la
  convention de toute l'interface : vous n'avez jamais à deviner ;
* **la ligne juste au-dessus compte ce qu'elle voit** — ici « aucun projet », ce
  qui vous dit que ce dossier n'en est pas un. Quand un dossier contient un
  `project.json`, il est signalé comme tel ;
* **un dossier vide fait un projet neuf.** Validez-le : la première commande qui
  écrira dedans le créera.

Naviguez avec ↑↓, entrez avec →, remontez avec ←, validez avec ⏎.

---

## L'écran des ateliers

Une fois le projet ouvert, la TUI affiche ce qu'on peut y faire — et, en haut à
droite, ce qu'il contient déjà :

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ mmu · demo · Ateliers                             1 rush · 1 lot · 1 master  │
│──────────────────────────────────────────────────────────────────────────────│
│ Que faire dans demo ?                                                        │
│                                                                              │
│ ▸ Extraction  Ouvrir un rush, borner, choisir les cadences, extraire         │
│   Pdf         Composer et generer les planches d'un ou plusieurs lots        │
│   Scan        Deposer des scans, detecter, puis ecrire les TIFF              │
│   Exports     Encoder un master depuis un lot scanné                         │
│                                                                              │
│   Projet      Gestion des médias, Profil par défaut, Reconstruction          │
│                                                                              │
│ ---------------------------------------------------------------------------- │
│                                                                              │
│   Derniere extraction confirmee                                              │
│     07/09 12:16 · TEST_FILE_12p5  ● encode                                   │
│                                                                              │
│──────────────────────────────────────────────────────────────────────────────│
│ ⏎ entrer  ↑↓ naviguer  Échap projet  F1 aide  Q quitter                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

Les quatre premiers ateliers sont le parcours, dans l'ordre : **Extraction →
Pdf → Scan → Exports**. Le cinquième, **Projet**, tient la maintenance. C'est
le même ordre que les onglets de l'interface graphique — celui du flux, et il
ne se renégocie pas d'une interface à l'autre.

Le bloc du bas rappelle où vous en étiez la dernière fois.

### Les trois zones de l'écran

```
┌─────────────────────────────────────────────────────────────┐
│  BARRE D'APPLICATION  (projet actif, raccourcis globaux)    │
├──────────────┬──────────────────────────────────────────────┤
│  MENU DU     │  ZONE DE CONTENU                             │
│  PROJET      │  (l'atelier ouvert : listes, formulaires,    │
│              │   avancement, rapports)                      │
│  • Extraction│                                              │
│  • Pdf       │                                              │
│  • Scan      │                                              │
│  • Exports   │                                              │
│  • Projet    │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

### Ce que chaque atelier produit

Le vocabulaire des objets est celui des [mots de l'outil](concepts.md).

| Entrée | Ce qu'elle fait | Objets |
|---|---|---|
| **Extraction** | Ouvrir un rush, borner, choisir les cadences, extraire | un **rush** → un **lot** et ses **frames extraites** |
| **Pdf** | Composer et générer les planches d'un ou plusieurs lots | un **lot** → une **planche** (un tirage) |
| **Scan** | Déposer des scans, détecter, puis écrire les TIFF | un **scan** → un **lot scanné** et ses **frames scannées** |
| **Exports** | Encoder un master depuis un lot scanné | des **frames scannées** → un **master** |
| **Projet** | Gestion des médias, profil de calibration par défaut, reconstruction | le **projet** |

L'atelier **Scan** enchaîne les mêmes étapes que la commande `scan` :
ingestion (source, dpi), détection ArUco et décodage QR, puis écriture des
**frames scannées** en TIFF 16 bits. La calibration de chaîne s'y traite à
part, sur une page de calibration scannée.

Les raccourcis propres à chaque écran sont rappelés en bas de l'écran actif, et
`F1` ouvre le manuel : ils font foi sur ce document.

---

## Atelier Extraction

Il commence par la liste des rushes déjà déclarés, avec ce que l'outil sait
d'eux et s'il les retrouve encore :

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ mmu · demo · Extraction                                                      │
│──────────────────────────────────────────────────────────────────────────────│
│                                                                              │
│   Quel rush extraire ?                                                       │
│                                                                              │
│    ▸ TEST_FILE            25 fps · 1920×1080 · 0:01              ● lié       │
│      Ajouter un rush       choisir un fichier vidéo dans l'explorateur       │
│                                                                              │
│──────────────────────────────────────────────────────────────────────────────│
│ 1 rush déclaré · 1 lié, 0 introuvable                                        │
│ ⏎ choisir  ↑↓ naviguer  Tab ajouter un rush  Échap ateliers  F1 aide         │
└──────────────────────────────────────────────────────────────────────────────┘
```

**`● lié` veut dire que le fichier est encore là où le manifeste l'attend.** Un
rush déplacé s'affiche `introuvable`, et l'atelier Projet le raccroche.

La suite : borner l'extrait (timecodes d'entrée et de sortie), choisir une ou
plusieurs cadences, voir le récapitulatif — nombre d'images, place sur le
disque —, puis confirmer. C'est le même récapitulatif que celui de
`mmu extract` en ligne de commande.

---

## Atelier Scan

Deux entrées, et l'atelier dit laquelle est le parcours principal :

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ mmu · demo · Scan                                                            │
│──────────────────────────────────────────────────────────────────────────────│
│   Atelier Scan                                                               │
│                                                                              │
│    ▸ Détecter des planches   Déposer des scans, lire les QR, puis écrire     │
│                              les TIFF. Le parcours principal.                │
│                                                                              │
│      Calibrer une chaîne     Depuis le scan d'une page de calibration,       │
│                              produire le profil couleur du scanner.          │
│                                                                              │
│   ────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│      Profil par défaut du projet   hp-envy-la-seyne.json                     │
│                                                                              │
│──────────────────────────────────────────────────────────────────────────────│
│ ⏎ entrer  ↑↓ naviguer  Échap ateliers  F1 aide  Q quitter                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

La ligne du bas rappelle en permanence **quel profil de calibration s'appliquera**
— ou qu'il n'y en a aucun, auquel cas les frames sortiront en brut.

---

## L'aide, sur F1

`F1` ouvre le manuel des raccourcis, construit à partir des touches réellement
liées dans l'application. Il tient sur deux pages : d'abord ce qui marche
**partout**, puis ce qui est propre à un écran.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ mmu · demo · Manuel                                             page 1 sur 2 │
│──────────────────────────────────────────────────────────────────────────────│
│   Raccourcis — partout                                                       │
│      Espace       Oui/non · cocher                                           │
│      F1           aide · où lire ce champ                                    │
│      Q            quitter                                                    │
│      Tab          ajouter un rush · champ · chemin · explorateur · journal…  │
│      Échap        abandonner · annuler · ateliers · interrompre · retour…    │
│      ↑↓           champ · choisir · liste · naviguer · parcourir · sources   │
│      ⏎            calibrer · choisir · continuer · créer · détecter…         │
│                                                                              │
│   Propres à un écran                                                         │
│      A            ajouter                      (Extraction)                  │
│      Ctrl+L       relinker                     (Projet)                      │
│      Ctrl+R       remettre                     (Execution)                   │
│──────────────────────────────────────────────────────────────────────────────│
│ 15 raccourcis sur 21                                                         │
│ → page suivante  ← page précédente  Échap fermer                             │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Les options de lancement

`mmu-tui` en prend quatre, et rien d'autre :

| option | effet |
|---|---|
| `--sans-couleur` | n'émet aucune couleur ; l'information reste portée par les glyphes. Actif d'office si la variable d'environnement `NO_COLOR` est posée |
| `--ascii` | remplace les glyphes UTF-8 par un repli ASCII |
| `--utf8` *(alias `--pas-d-ascii`)* | garde les glyphes UTF-8 même si la console a l'air de ne pas les rendre |
| `--diagnostic-chemin` | affiche ce que la TUI voit de son environnement, puis sort |

### Si des caractères s'affichent en carrés

C'est un problème de **police de la console**, pas de terminal ni de shell : le
glyphe est dessiné par l'hôte (`conhost.exe`, Windows Terminal, le terminal de
VS Code) avec la police qu'il a chargée. Deux glyphes posent problème en
pratique sous Windows, dont le symbole « Entrée ».

La TUI **déduit** le repli de son hôte, sans lire aucune variable qui lui soit
propre, et le choix est débrayable dans les deux sens : `--ascii` force le
repli, `--utf8` le refuse.

Pour voir ce qu'elle a décidé et pourquoi :

```bash
mmu-tui --diagnostic-chemin
```

La sortie donne la plateforme, les variables posées par l'hôte, ce que `rich`
sait de la console, le motif de la décision, et surtout **un échantillon des
glyphes à risque imprimés tels quels** avec leur repli en regard. Aucune API ne
sait dire si une police contient un caractère donné : regarder l'échantillon
tranche en une seconde ce qu'aucune détection ne peut prouver.

---

## Ce que la TUI retient d'une session à l'autre

Uniquement la **liste des projets récents**, dans un fichier hors du projet :

| plateforme | emplacement |
|---|---|
| Linux, macOS | `~/.config/mixed_media_utility/recents-v1.json` (ou sous `$XDG_CONFIG_HOME`) |
| Windows | `%APPDATA%\mixed_media_utility\recents-v1.json` |

Rien d'autre n'est stocké en dehors du dossier de projet. Supprimer ce fichier
ne perd que l'ordre de la liste d'accueil.
