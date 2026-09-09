# Revue de faisabilité — les spines contre le produit livré

*Reviewer Gate, angle « faisabilité contre le produit livré ». Critique sans
modification : ni `DESIGN.md` ni `EXPERIENCE.md` n'ont été touchés.*

Périmètre confronté : `DESIGN.md`, `EXPERIENCE.md`,
`.working/parcours-utilisateurs-epic7-2026-08-17.md` contre `src/mixed_media_utility/`,
`_bmad-output/specs/project.schema.json`,
`_bmad-output/implementation-artifacts/` (stories, `sprint-status.yaml`,
`deferred-work.md`, `decisions-*.md`) et `_bmad-output/planning-artifacts/epics.md`.

---

## 1. Verdict d'ensemble

Le dispositif de signalement **existe et fonctionne là où il a été appliqué** :
la section *Cible non livrée* nomme quatre comportements, la production d'images
par la détection porte une note de dépendance explicite, et le rôle 8 du chutier
comme le comparateur de candidats sont marqués. Mais il a été appliqué à une
seule famille de manques — celle qu'on avait déjà trouvée — et **vingt-trois
autres endroits supposent du cœur un comportement qu'il n'a pas, sans le dire**.
Cinq d'entre eux ne sont pas des stories à écrire mais des **contradictions de
fond** : la localisation d'un rush n'est pas persistée *par décision*, la section
`reconstruction` est unique par document *par conception*, le manifest est fermé
à la racine *par contrat*, le profil de calibration vit hors du projet *par
arbitrage du 2026-08-16*, et le scan est indivisible *par construction de la
commande*.

La faute de forme dominante n'est pas d'avoir décrit une cible : c'est d'avoir
décrit **comme acquis** ce qui suppose une story d'Epic 5 — et, dans quatre cas,
ce qui suppose de **renverser** une décision produit déjà rendue et écrite.

**Écarts non signalés par sévérité : 5 critiques · 8 élevés · 7 moyens ·
3 faibles.**

---

## 2. Écarts non signalés

### CRITIQUE

---

#### C1 — Le scan est une commande indivisible : « deux temps » n'existe pas, et la détection ne persiste rien

**Ce que la spine promet.**
`EXPERIENCE.md:104-109` : « **Corollaire : l'atelier Scan se déroule en deux
temps, jamais en un.** 1. **Détection** — déclenchée depuis le chutier […]
**complétude annoncée dès la fin de chaque tâche, avant toute écriture**.
2. **Extraction TIFF** — une tâche par planche. » Repris en `EXPERIENCE.md:416`
(P1 étape 11), `:441` (P2 étape 3), `:463` (P3 étape 1), et `DESIGN.md:303`
(le bouton *Détecter* du chutier).

**Ce que le produit sait faire.**
`scan` est une seule commande, dont l'enchaînement est verrouillé par sa propre
docstring : « Quatre etapes […] ingestion (5.1), detection geometrique (5.2),
recadrage (5.3) et ecriture des frames (5.6), puis persistance au manifest
(5.7) » (`src/mixed_media_utility/cli.py:993-1010`). Il n'existe **aucun** point
d'arrêt entre la détection et l'écriture : le seul retour anticipé est le cas
« aucune planche n'a livré son QR » (`cli.py:1058-1073`).

Pire, et c'est ce qui fait le coût : **le rapport de détection n'est jamais écrit
sur le disque.** `scan_detection.report_json` (`scan_detection.py:1052-1058`)
n'a aucun appelant dans `src/`. Le seul artefact persisté par la passe est
`scans/<slug>/ingest.json` (`cli.py:1032-1035`). Tout le reste — homographies,
statuts QR par page, mesures d'échelle, marqueurs étrangers, plans de découpe —
vit en mémoire et meurt avec le processus.

**Nature de l'écart.** Ordre d'opérations et durabilité. La complétude que la
spine veut annoncer « avant toute écriture » est calculée par
`persist_scan` (`io/scan_manifest.py:1828`), c'est-à-dire **après**
`write_lot_output_frames`. Et l'état intermédiaire « détecté, pas encore
extrait » — celui sur lequel reposent le mode lecteur, la galerie, les
surimpressions, l'édition des coins et la reprise après fermeture
(`EXPERIENCE.md:254` : « Rien d'affiché ne dépend d'un état de session ») — n'a
aucun support sur le disque.

**Sévérité : critique.**

**Ce qu'il faudrait.** Une story d'Epic 5 en amont qui (a) scinde `scan` en
`scan detect` / `scan extract`, (b) persiste le document de détection (le
contrat existe déjà : `scan_previz` sait rendre un document en état `detected`,
« aucune frame écrite » — `scan_previz.py:1083`), (c) fasse dériver la
complétude annoncée de ce document et non du rapport d'écriture. Tant qu'elle
n'est pas livrée, la spine doit dire que le premier des deux temps n'existe pas.

---

#### C2 — La section `reconstruction` est unique par document : un projet ne garde le détail que de son **dernier** lot scanné

**Ce que la spine promet.**
`EXPERIENCE.md:80` (rôle 3 du chutier) : « **Arborescence inversée reconstruite
depuis des scans** — Un scan peut porter plusieurs lots ». `EXPERIENCE.md:70` :
le chutier de Scan/Exports est *scan > lots reconstruits*. P4 étape 6
(`EXPERIENCE.md:502`) : « l'outil **range chaque page sous son lot** par les
QR ». Et les états de galerie (`EXPERIENCE.md:198-201`) veulent, **par lot**,
la frame absente à sa place et la mire de remplacement distinguée.

**Ce que le produit sait faire.**
Le manifest porte **une** section `reconstruction`, à la racine, avec **un**
`lot_id` (`_bmad-output/specs/project.schema.json`, `reconstruction.lot_id`), et
elle est réécrite intégralement à chaque passe. C'est écrit dans le code :

> « Story 5.7: la section est unique par document et reecrite en entier a chaque
> appel. » — `src/mixed_media_utility/io/reconstruction.py:623-624`

Le module d'encodage a dû se doter d'un code exprès pour le dire à l'opérateur :

> « La section `reconstruction` decrit un **autre** lot que celui vise. […] la
> section est unique par document et le scan d'un second lot **ecrase le detail
> du premier**. » — `src/mixed_media_utility/encode.py:232-236`
> (`ENCODE_RECONSTRUCTION_OTHER_LOT`)

Ce qui survit par lot est court et suffisant pour un code couleur, pas pour une
galerie : `lots[].expected_frame_count`, `reconstructed_frame_count`,
`synthetic_frame_count` et `synthetic_frames` (registre durable de noms de
fichiers, volontairement posé sur `lots[]` « et non dans reconstruction, qui est
reecrite en entier a chaque passe » — description du schéma). Tout le reste —
`reconstruction.slots[]` (timecode et nature de chaque frame),
`missing_pages`, `page_roles`, `scan.pages[]` (`read_rank`, `page_index`,
`qr_status`, `homography_status`), `page_calibration_results[]` — appartient au
dernier lot scanné et **à lui seul**.

**Nature de l'écart.** Donnée supposée que rien ne porte — exactement la famille
du « mode lecteur sans images ». Un projet à deux lots scannés affiche un arbre
faux dès le second scan.

**Sévérité : critique.**

**Ce qu'il faudrait.** Une story d'Epic 5 qui fasse passer `reconstruction`
d'objet unique à collection indexée par `lot_id` (changement de schéma,
migration de la règle de comparaison d'idempotence de 5.7 AC 10, et reprise de
`ENCODE_RECONSTRUCTION_OTHER_LOT` qui devient sans objet). À défaut, la spine
doit restreindre le chutier de Scan à un lot reconstruit à la fois, ce qui
détruit P4.

---

#### C3 — Le manifest est fermé : aucun état d'interface ne peut y vivre

**Ce que la spine promet.**
`EXPERIENCE.md:254-256` : « **Rien d'affiché ne dépend d'un état de session.**
Ce que le chutier montre vient du projet sur le disque — donc survit à la
fermeture, au changement de machine, au disque qui change de main. » Et le
chutier porte au moins quatre objets qui ne sont **que** de l'état d'interface :
les **dossiers d'organisation** (`EXPERIENCE.md:88` : « ils n'existent **que**
dans le chutier, jamais dans le dossier de travail »), la **zone tampon**
(`:90`), la **composition d'un lot** (« la composition est inscrite dans le
projet et survit au disque qui change de main », `:534`), et les **presets
d'export** (`:428`).

**Ce que le produit sait faire.**
`project.schema.json` est fermé **aux trois niveaux qui comptent** :
`additionalProperties: false` à la racine (huit clés autorisées, pas une de
plus), sur `lots[].items`, et sur `rushes[].items`. Le dépôt en a fait une règle
de rédaction de story : « tout champ ajoute a `lots[]` est declare au schema dans
la meme story — `lots[].items` est en `additionalProperties: false`, donc un
champ non declare fait echouer la commande **apres** que la video a ete ecrite »
(`_bmad-output/planning-artifacts/epics.md:356`).

**Nature de l'écart.** Champ interdit par le schéma. Aucun des quatre objets
ci-dessus n'a de domicile : ni dans `project.json`, ni dans un fichier annexe que
la spine mentionnerait.

**Sévérité : critique.**

**Ce qu'il faudrait.** Trancher explicitement le domicile de l'état d'interface —
soit une extension du schéma (une story par famille : organisation, composition,
presets), soit un document annexe versionné à côté de `project.json`, nommé dans
la spine. Ce n'est pas une question d'implémentation : la promesse « ça survit au
disque qui change de main » est un choix produit, et elle est aujourd'hui fausse.

---

#### C4 — Le produit **ne garde pas** le chemin d'un rush, et c'est une décision, pas un oubli

**Ce que la spine promet.**
`EXPERIENCE.md:24-27` : « les rushes restent où ils sont, **l'outil n'en garde
que le chemin et sait les relinker** ». `EXPERIENCE.md:194` : « Rush absent /
délinké […] **Relink possible à tout moment** ; au relink, le rouge tombe et le
son + le balayage reviennent sur Exports ». P2 étape 5 en fait un climax
(`:446`).

**Ce que le produit sait faire.**
`extract` écrit sur `rushes[]` exactement trois champs :

```
EXTRACTION_RUSH_FIELDS: tuple[str, ...] = (
    "rush_id", "source_name", "source_parent",
)
```
— `src/mixed_media_utility/io/extraction_manifest.py:264-268`

`source_path` est déclaré au schéma mais **écrit par personne** : la seule
mention dans le code est sa *préservation* à la reconstruction
(`io/reconstruction.py:412-419, 607-616`), et encore, sous condition qu'il ne
soit pas absolu. Et un chemin absolu est refusé **partout**, par une garde
transverse : « absolute paths are not allowed in the v2 contract; use paths
relative to the project directory » (`io/manifest.py:135-147`). Le motif est
écrit dans le schéma lui-même, sur `source_parent` : « Nom seul, jamais un
chemin: il distingue deux rushs homonymes […] sans nommer ni machine ni
utilisateur, **donc sans casser la portabilite du projet**. »

**Nature de l'écart.** Fonction supposée qui n'existe pas, et qui est de plus
**contraire** à un invariant du contrat v2. Conséquences directes :

* le relink n'a aucune cible d'écriture — et en aurait besoin d'une qui viole
  l'invariant, puisqu'un rush « qui reste où il est » est hors du dossier projet ;
* à toute réouverture, **tout** rush est structurellement délinké : l'état rouge
  de `EXPERIENCE.md:194` n'est pas un cas d'exception, c'est le régime nominal ;
* le son et le balayage d'Exports, conditionnés à « le rush original est sur le
  disque » (`:424`, `:445`), ne peuvent jamais être proposés automatiquement.

**Sévérité : critique.**

**Ce qu'il faudrait.** Un arbitrage produit, puis une story : soit un locator de
rush **hors manifest** (bibliothèque par machine, comme le profil de calibration
de `EPIC5-ARB-80`), soit une exception nommée à l'invariant de portabilité pour
`rushes[].source_path`, avec sa règle de comparaison. Les deux ont des
conséquences sur P2, qu'il faut écrire.

---

#### C5 — Le profil de calibration par chaîne de scan (5.22) n'est pas livré, et il vit **hors du projet**

**Ce que la spine promet.**
`EXPERIENCE.md:52` : section **Calibration** du chutier — « Planches de
calibration générées, **profils de scanner produits** ». `EXPERIENCE.md:185`
(modale) : « Calibration scanner : nom du scanner, dpi, format, **commentaire
libre** ». P1 étape 10 (`:414`) : « **calibration scanner** (nom, dpi, format,
commentaire) → profil créé ». `EXPERIENCE.md:180` : « Bascule de calibration
couleur — Active/désactive à la volée, **change de profil à la volée** ».
P3 étape 9 (`:481`) : « bascule de profil de calibration ».

**Ce que le produit sait faire.**
Il n'y a **aucune** notion de profil réutilisable aujourd'hui. La correction est
ajustée à la volée, une fois par lot, sur la page de calibration de **ce** lot
(`cli.py:1095-1108`, `_fit_lot_correction`), et il n'existe qu'un interrupteur
binaire `--cc on|off` (`cli.py:2570-2591`) — dont l'aide interdit jusqu'au
vocabulaire du réglage (frontière négative testée, AC 16 de 5.16).

La fonction décrite par la spine est celle de la story **5.22**
(`EPIC5-ARB-80`, `decisions-2026-08-16-epic-5.md`), qui est
`ready-for-dev` — **pas** `done` (`sprint-status.yaml:5-22-profil-de-calibration-reutilisable-par-chaine`).
Elle n'apparaît **nulle part** dans les deux spines, et **pas** dans la table
*Cible non livrée* (`EXPERIENCE.md:373-381`), qui n'en liste que quatre.

Et l'arbitrage contient une clause que la spine contredit frontalement :

> « **Le profil est stocke dans un fichier**, dans une **bibliotheque par
> machine** (dossier de configuration utilisateur), un fichier par chaine,
> reutilise par tous les projets. Consequence assumee : la reconstruction par un
> tiers depuis les fichiers du projet seul **ne retrouve pas le profil** — il
> faut le transporter ou le re-generer. »
> — `decisions-2026-08-16-epic-5.md`, `EPIC5-ARB-80`, décision 3

**Nature de l'écart.** Double : une fonction non livrée présentée comme acquise
(la plus visible de tout l'atelier Scan), **et** un objet machine-scopé placé
dans le chutier, qui est l'arbre du **projet**. En P2, Inès sur sa station n'a
pas le profil de Camille : la section Calibration de son chutier est vide, et
rien dans la spine ne dit ce qui se passe alors.

**Sévérité : critique.**

**Ce qu'il faudrait.** Ajouter 5.22 à *Cible non livrée* avec ses conséquences
d'interface, et trancher le domicile visuel d'un objet qui n'appartient pas au
projet (le chutier n'est pas le bon endroit, ou alors il faut dire qu'il montre
deux natures d'objets). La décision 3 laisse d'ailleurs explicitement le point de
raccord à la rédaction de la story : c'est un arbitrage que la spine peut
alimenter, pas un détail.

---

### ÉLEVÉ

---

#### E1 — La galerie d'Extraction n'a **aucune** source d'images, et ce n'est pas signalé

**Ce que la spine promet.** P1 étape 3 (`EXPERIENCE.md:396`) : « Camille regarde
en mode vidéo, puis **en galerie**, et active le toggle des frames supprimées
pour voir d'un coup ce qui saute. » C'est **avant** l'extraction (étape 5) :
aucun TIFF n'existe. `DESIGN.md:307` décrit les cinq états de vignette, `:299`
le zoom continu de la grille.

**Ce que le produit sait faire.** Le contrat de vignette existe
(`extraction_previz.py:275-300` : `THUMBNAIL_STATES`, `THUMBNAIL_ORIGINS`,
cinq codes de dégradation) mais **rien ne le produit** : la seule instance
construite dans tout `src/` est `ABSENT_THUMBNAIL = ThumbnailRef()`
(`extraction_previz.py:527`), c'est-à-dire l'absence. Le cas nominal du contrat
est « aucune vignette ».

**Nature de l'écart.** Donnée supposée que rien ne porte. La note de dépendance
de `EXPERIENCE.md:127-134` couvre **le chemin scan uniquement** (« Cette
production d'images par la détection n'existe pas encore ») : le chemin
extraction est laissé sans mention, alors qu'il est dans le même état.

**Sévérité : élevé.** **Ce qu'il faudrait.** Étendre la note de dépendance au
chemin extraction, ou une story d'Epic 5 (le cache de prévisualisation, déjà
identifié en E01 de `reconcile-extraction-sources.md`).

---

#### E2 — Aucune progression n'est mesurable : la carte de tâche n'a pas de source

**Ce que la spine promet.** `DESIGN.md:311` : « Dans l'ordre : le nom de la
fonction […], la **barre** (6 px, accent en cours), puis **frames/total, temps
passé, temps restant**. » `EXPERIENCE.md:183` : « Une carte **par lot / par
planche / par détection** ». `EXPERIENCE.md:76` : « Les tâches tournent **en
arrière-plan** ». `EXPERIENCE.md:196` : « Tâche en cours […] **L'atelier reste
utilisable** ».

**Ce que le produit sait faire.** Toutes les invocations externes sont
**bloquantes et muettes** : `subprocess.run(command, capture_output=True, ...)`
(`ffmpeg_utils.py:77` pour l'extraction, `:285` pour la seconde famille), sans
`-progress`, sans lecture incrémentale de `stderr`. Aucun paramètre de rappel de
progression n'existe dans le dépôt : `extraction.run_extraction`,
`scan_output_frames.write_lot_output_frames`, `encode` n'en prennent aucun. Le
seul mécanisme voisin est celui de `cadence_previz`, qui est un lecteur temps
réel et non un rapporteur de tâche.

**Nature de l'écart.** Donnée supposée que rien ne porte, sur le composant le
plus présent de l'interface (panneau de progression, visible depuis les quatre
ateliers, `EXPERIENCE.md:53`). « Temps restant » suppose en outre un modèle
d'estimation qui n'existe nulle part.

**Sévérité : élevé.** **Ce qu'il faudrait.** Une story d'Epic 5/6 transverse :
canal de progression (au minimum frames écrites / attendues) sur les trois
commandes longues. Sans elle, la carte ne peut afficher que deux états, *en
cours* et *terminée*, ce que la spine doit alors décrire.

---

#### E3 — Le cœur ne sait travailler qu'**au lot** : la tâche par planche et la re-détection d'une page sont impossibles

**Ce que la spine promet.** `EXPERIENCE.md:109` : « **Extraction TIFF** — une
tâche par planche. » P3 étape 9 (`:481-483`) : « elle relance la détection **de
cette page** avec ce profil ». `EXPERIENCE.md:183` : une carte « par planche ».

**Ce que le produit sait faire.** L'unité de travail est le lot, et elle est
indivisible : `detect_lot_pages` balaie toutes les pages du rapport d'ingestion
(`scan_detection.py:855-903`), `write_lot_output_frames` écrit le lot entier en
un appel (`scan_output_frames.py:1657`), et **toutes** les pages d'une passe
doivent déclarer le même lot — `_check_lot_consistency` refuse la moindre
divergence de `lot_id`, `template_id`, `page_count`… (`io/reconstruction.py:301-313`).

Surtout, la re-détection d'une seule page avec un autre profil est **interdite
par arbitrage**, pas seulement absente :

> « **La correction du lot s'ajuste ici, une seule fois** (story 5.19, AC 1),
> avant toute planche […] Un ajustement par planche serait le re-ajustement par
> page qu'`EPIC5-ARB-57` **interdit**. » — `cli.py:1103-1107`

**Nature de l'écart.** Granularité impossible, doublée d'une contrainte du cœur
ignorée. **Sévérité : élevé.** **Ce qu'il faudrait.** Réécrire les étapes
concernées au grain du lot, ou porter la demande à l'arbitrage (5.22 rouvre déjà
le sujet de la calibration : c'est le moment).

---

#### E4 — L'édition des quatre coins n'a **aucun consommateur** : le plan de découpe est dérivé du gabarit

**Ce que la spine promet.** `DESIGN.md:308-309` : chaque zone est « **toujours
éditable**, y compris quand la détection s'est déclarée satisfaite » ; quatre
poignées, loupe automatique, « Après un ajustement, **rien ne se relance** :
l'affichage de complétude du lot se met à jour, c'est tout ». P3 étape 7
(`EXPERIENCE.md:477`). C'est un *droit de reprise en main* revendiqué
(`:487`), et un « Don't » du tableau (`DESIGN.md:341`).

**Ce que le produit sait faire.** Le rectangle de chaque frame **n'est pas un
paramètre** : il est calculé à partir du seul `template_id`.

```
def build_page_crop_plan(*, template_id: str, slots: list[dict], dpi: int) -> PageCropPlan:
    """… Aucune marge en parametre, par contrat (AC 4): elle est resolue depuis le
    `TemplateSpec`, et elle seule. …"""
```
— `src/mixed_media_utility/scan_crop.py:227-241`

L'**adressage** existe bien, lui (`scan_previz.py:26-45` : `PAGE_ADDRESS_FIELDS`,
`FRAME_ZONE_ADDRESS_FIELDS`, `MARKER_ADDRESS_FIELDS`, prévus pour que 7.4 puisse
dire « la zone 2 de la page 3 est mal placée, voici le rectangle corrigé »), mais
le document « **n'autorise rien** […] Il rend l'edition **exprimable**;
l'appliquer appartient a l'Epic 7 » (`scan_previz.py:47-50`). Côté écriture, il
n'y a rien à appliquer *sur*.

**Nature de l'écart.** Fonction supposée qui n'existe pas. Elle ne se résout pas
côté GUI : c'est le cœur qui doit accepter une géométrie par frame, et le refus
de tout paramètre de marge est un contrat de la story 5.3.

**Sévérité : élevé.** **Ce qu'il faudrait.** Une story d'Epic 5 : `crop_plan`
prenant un tableau de rectangles surchargés, avec sa persistance (voir C1 et C3 —
sans quoi l'ajustement ne survit pas à la fermeture). C'est le vrai contenu de la
story 7.4, et il commence en amont d'Epic 7.

---

#### E5 — Le formulaire de complétion de QR ne peut pas reconstruire un payload valide

**Ce que la spine promet.** `EXPERIENCE.md:178` : « Champs : frames par page,
numéro de page, identifiant du lot, timecode première/dernière image. […] Une
fois complété, **l'outil peut proposer les zones d'image** ». P3 étapes 5-6
(`:468-474`). Le `deferred-work.md:3593-3595` va jusqu'à affirmer : « **Toutes
ces informations sont imprimées en clair sur la planche, et l'outil sait où.** »

**Ce que le produit sait faire.** Un payload de page exige **douze** champs :

```
REQUIRED_PAGE_FIELDS = ("schema_version", "project_id", "rush_id", "lot_id",
  "page_index", "page_count", "fps_target", "template_id", "patch_preset_id",
  "gamut_map_id", "target_colorspace", "slots")
```
— `io/reconstruction.py:50-63`, chaque `slots[]` portant `slot_index` **et**
`frame_timecode` (`:99`).

Confronté à ce qui est réellement **imprimé** (`pdf_composition.py:1229-1237`
pour le pied technique, `:1440-1465` pour l'identité, `:1374` pour l'étiquette de
chaque emplacement `s02 tc 00:00:12:10`), le compte tombe :

| champ requis | imprimé ? |
|---|---|
| `schema_version` | oui (`schema-payload=2.0`) |
| `project_id`, `rush_id` | oui (bloc d'identité du pied) |
| `lot_id`, `page_index`, `page_count`, `fps_target` | oui (en-tête + pied) |
| `template_id`, `patch_preset_id` | oui (`template=`, `patchs=`) |
| `slots[].frame_timecode` | oui, **un par emplacement** |
| **`gamut_map_id`** | **non** |
| **`target_colorspace`** | **non** |

Trois défauts distincts, donc : (a) deux champs obligatoires ne sont imprimés
nulle part — ils ne sont récupérables que **par emprunt aux pages voisines**
(`_LOT_LEVEL_FIELDS`, `io/reconstruction.py:81-92`), ce qui échoue exactement
dans le cas de terrain le plus probable, un lot entier numérisé sous le dpi
minimum ; (b) la spine demande « timecode première/dernière image » alors que le
contrat exige **un timecode par emplacement**, et que la planche les imprime un
par un ; (c) « frames par page » **n'est pas un champ de payload** — c'est une
propriété dérivée de `template_id`.

Et surtout : **il n'existe aucun point d'entrée pour un payload saisi à la
main.** `detect_lot_pages(project_dir, ingest_report, *, dpi)`
(`scan_detection.py:855-860`) décode lui-même et n'accepte aucune surcharge ;
`reconstruct-project` accepte bien des textes de QR (`cli.py:2846-2853`) mais ne
produit **que** du manifest, jamais de frame.

**Nature de l'écart.** Vocabulaire fermé ignoré + fonction supposée inexistante.

**Sévérité : élevé.** **Ce qu'il faudrait.** Une story d'Epic 5 (surcharge de
payload par page, avec la garde qui refuse un payload incohérent avec ses
voisins), **et** soit imprimer `gamut_map_id` / `target_colorspace` au pied —
qui a de la place depuis 5.18 — soit écrire dans la spine que la complétion n'est
possible que si au moins une page du lot a décodé.

---

#### E6 — Deux dispositions du même lot se détruisent l'une l'autre — et c'est la prémisse de P5

**Ce que la spine promet.** P5 étape 2 (`EXPERIENCE.md:514-516`) : « elle coche
les deux lots et demande **deux dispositions** : les planches se génèrent, **une
par lot et par disposition**. Elle imprime, elle peint — les deux traitements ne
se ressemblent pas, **c'est le but**. »

**Ce que le produit sait faire.** Trois obstacles, indépendants :

1. **Le nom du PDF ne porte pas la disposition** :
   `build_sheets_pdf_filename(project_id, rush_id, lot_id)` →
   `<projet>_<rush>_<lot>_planches.pdf` (`io/naming.py:502-519`). Deux
   dispositions du même lot visent le **même fichier**, et le second `makepdf`
   refuse (« existe deja. Relancer avec --overwrite », `cli.py:2070-2077`) — ou
   écrase.
2. **Le manifest ne garde qu'une disposition par lot** :
   `lots[].template_id` / `patch_preset_id` / `gamut_map_id` sont écrasés à
   chaque impression (`io/pdf_manifest.py:325-327`), avec un constat explicite :
   > « Un lot en etat `pdf` est precisement celui dont on **sait** que des
   > planches sont imprimees et pas encore numerisees; les reimprimer avec
   > d'autres parametres met en circulation **deux jeux de planches dont les QR
   > se contredisent**, et le manifest ne garde que le dernier. »
   > — `io/pdf_manifest.py:274-280` (`PDF_IDENTIFIER_DIVERGES`)
3. **Le scan du premier tirage sera ensuite refusé** : `_check_printed_identifiers`
   lève « planche PERIMEE » sur la divergence, et « aucun `--overwrite` ne le
   leve » (`io/scan_manifest.py:687-696, 700-734`).

**Nature de l'écart.** Geste supposé réversible qui ne l'est pas + contrainte du
cœur ignorée. La spine signale bien que la **seconde passe** est refusée
(`EXPERIENCE.md:377`), mais elle rattache ce refus aux *versions d'un même
tirage* ; le cas des **deux dispositions**, qui est la prémisse même de P5, n'est
pas couvert, et il est plus destructeur (il périme rétroactivement des planches
déjà imprimées).

**Sévérité : élevé.** **Ce qu'il faudrait.** Story 5.12 (`ready-for-dev`, qui
transforme la divergence en **routage** vers une autre entrée de `lots[]`,
`epics.md:229`) doit être nommée dans *Cible non livrée* au même titre que les
quatre autres, **et** le nom de fichier du PDF doit gagner son discriminant —
point que 5.12 ne couvre pas, puisqu'elle porte sur le lot scanné.

---

#### E7 — « Une planche = un PDF » est faux, et contredit la spine elle-même

**Ce que la spine promet.** P1 étape 8 (`EXPERIENCE.md:410`) : « Génération :
**une planche = un PDF**. » P4 étape 1 (`:492`) : « carte verte, **un PDF**, un
dossier au nom du lot ».

**Ce que le produit sait faire.** `render_lot_pdf` produit **un seul PDF
multi-pages par lot** — « Rendre le PDF multi-pages du plan, atomiquement »
(`pdf_render.py:334-341`), boucle `for page in plan.pages: … canvas.showPage()`
(`:365-369`) — écrit à plat sous `patches/`
(`cli.py:2069`, `io/project_layout.py:27`), et **non** dans un dossier au nom du
lot.

**Nature de l'écart.** Granularité impossible, et les deux formulations de la
spine sont déjà incompatibles entre elles (« une planche = un PDF » vs « un
PDF » pour tout un lot de neuf planches). Conséquence d'interface concrète : la
carte de tâche terminée annonce « deux boutons — *dossier* et *fichier* »
(`DESIGN.md:311`), et le bouton *dossier* ouvrirait `patches/`, c'est-à-dire tous
les PDF de tous les lots du projet.

**Sévérité : élevé.** **Ce qu'il faudrait.** Choisir : soit corriger la spine
(un PDF par lot, dans `patches/`), soit une story d'Epic 4/5 qui éclate le rendu
par planche et introduit un dossier de sortie par lot.

---

#### E8 — Concurrence : la file de tâches parallèles contre « une seule commande écrivant le manifest à la fois »

**Ce que la spine promet.** `EXPERIENCE.md:76` : « Les tâches tournent **en
arrière-plan** : changer d'atelier ne perd rien. » `:183` : une carte « par lot /
par planche / par détection », donc plusieurs de front. `:416` : « Cartes
« détection » **en file** ». `:184` : « Exporter (ou **Mettre en file**) ».

**Ce que le produit sait faire.** Cinq écrivains du manifest, **aucun verrou** :

> « Le depot n'a **aucun verrou** sur la sequence lecture-modification-ecriture du
> manifest: deux ecritures simultanees et le dernier ecrivain gagne, en rendant
> tous deux un succes. […] Regle d'usage jusqu'a nouvel ordre: **une seule
> commande ecrivant le manifest a la fois par projet**. »
> — `io/scan_manifest.py:46-56`

Le `deferred-work.md` le consigne cinq fois, et nomme précisément le déclencheur
de sa réouverture : « **A rouvrir des qu'une interface lance plusieurs
extractions de front**, ce que la previz multi-cadence rend plausible »
(`deferred-work.md:185-191`) ; « Le correctif est un verrou de fichier par
projet » (`:2196-2209`).

**Nature de l'écart.** Contrainte du cœur ignorée, avec perte de données
silencieuse à la clé (le lot du premier écrivain disparaît du manifest alors que
ses fichiers sont sur le disque).

**Sévérité : élevé.** **Ce qu'il faudrait.** La story de verrou transverse
(`deferred-work.md:1550`) est une **précondition** d'Epic 7, pas un reste : la
spine doit la citer, ou déclarer que les tâches sont sérialisées par projet — ce
qui change la conception du panneau de progression.

---

### MOYEN

---

#### M1 — « Un champ essentiel manquant se remplit à la main » : le cœur n'a aucun champ à remplir

**Spine.** `EXPERIENCE.md:182` : « Préremplis d'après la source. Un champ
**essentiel manquant** bloque l'action de l'atelier tant qu'il n'est pas
**rempli à la main**. » Idem `DESIGN.md:312`, `EXPERIENCE.md:195`.

**Produit.** `extract` n'accepte que huit options — `--project`, `--video`,
`--fps`, `--overwrite`, `--yes`, `--accept-unknown-color`, `--in`, `--out`
(`cli.py:2454-2506`) — et **aucune** surcharge de métadonnée source. Le geste
prévu par le cœur devant une colorimétrie source incomplète est l'inverse exact :
**accepter l'absence explicitement**, `requires_unknown_color_consent` /
`--accept-unknown-color` (`source_confirmation.py:323, 1043, 1141`), avec un
message qui dit ce qui manque sans proposer de le combler
(`source_confirmation.py:906-920`).

**Nature.** Fonction supposée inexistante — et la spine se contredit elle-même
douze lignes plus haut : « **On ne propose jamais de compléter ce qui est
structurellement absent** » (`EXPERIENCE.md:159`). **Sévérité : moyen.**
**Ce qu'il faudrait.** Nommer les deux natures : un paramètre *de commande* non
renseigné (dpi de scan, cadence cible) bloque et se saisit ; une métadonnée
*absente de la source* ne se saisit jamais, elle s'accepte.

---

#### M2 — La frame « volontairement écartée » n'est pas exprimable

**Spine.** `DESIGN.md:307` : état *écartée* (« une frame volontairement écartée
n'est pas une frame manquante ») ; `EXPERIENCE.md:202` : « Frame volontairement
écartée | Galerie Extraction (toggle) ».

**Produit.** La sélection est **déterministe et fermée** : « Ce module possede
**la regle de selection**, et rien d'autre » ; `source_index(n) = floor(n *
fps_source / fps_target)` (`frame_selection.py:1-30`). Les seuls leviers sont
`fps_target` et les bornes in/out (3.7). Une exclusion manuelle briserait de plus
`lots[].frame_timecodes_digest`, qui est l'empreinte de la sélection et sert de
garde à l'encodage (`ENCODE_DIGEST_MISMATCH`, `encode.py:214`).

**Nature.** Granularité impossible. Le toggle est probablement destiné à montrer
les frames *non retenues par la réduction de cadence* — ce qui est calculable —
mais le mot « volontairement » décrit un geste inexistant.
**Sévérité : moyen.** **Ce qu'il faudrait.** Reformuler (« frames non retenues
par la cadence »), ou une story si le geste est voulu.

---

#### M3 — Les réglages d'export promis n'existent pas, et il n'y a pas de magasin de presets

**Spine.** P1 étape 16 (`EXPERIENCE.md:428`) : « Réglages d'export (taille
estimée, **nom et destination prévisionnels**), **enregistrés comme preset**. »

**Produit.** `encode` n'a ni `--output` ni `--dest` : la destination est imposée,
`outputs/<lot>_mmu_<profil>.<conteneur>` (`cli.py:2389-2392`, `io/naming.py:522`).
Le catalogue de sept profils est fermé (`codec_profiles.PROFILES`,
`cli.py:2400-2406`), et aucun magasin de préréglages utilisateur n'existe (voir
aussi C3 : rien ne peut vivre au manifest).

**Nature.** Fonction supposée inexistante + donnée sans domicile.
**Sévérité : moyen.**

---

#### M4 — Extraire « à deux cadences en une passe » n'est pas une passe

**Spine.** P5 étape 1 (`EXPERIENCE.md:512`) : « Elle extrait à **deux cadences en
une passe**, mêmes bornes […] ***(Livré.)*** » ; P1 étape 5 : modale « cadences
**cochables** ».

**Produit.** `extract --fps` est un scalaire requis (`cli.py:2460`). Deux
cadences = deux invocations, donc deux consentements (3.3), deux écritures du
manifest (donc E8), et deux cartes de tâche. Ce qui est réellement livré est
l'**existence** de deux lots du même rush à deux cadences (v2.1,
`io/reconstruction.py:663-668`), pas leur production en un geste.

**Nature.** Granularité + mention « (Livré.) » inexacte. **Sévérité : moyen.**

---

#### M5 — La bascule de calibration « à la volée » impose une GUI qui recalcule

**Spine.** `EXPERIENCE.md:180` : « Active/désactive à la volée, change de profil
à la volée ; **le rendu change à l'écran sans rien écrire**. » `DESIGN.md:196` :
« Elle compare un scan calibré à son original ». Et le principe de cadrage :
« La GUI est une **surcouche d'un cœur CLI** : elle **expose, elle ne recalcule
pas** » (`EXPERIENCE.md:29`).

**Produit.** La correction s'applique au moment d'écrire, sur le raster
**redressé** de la page (`cli.py:657-680` `_rectified_page`,
`scan_output_frames._corrected_frame:1198`), dans un pipeline 16 bits avec
expansion de gamut. Pour que ce que l'écran montre soit ce que le TIFF portera,
la GUI doit rejouer **exactement** `color_pipeline` sur le même raster — donc
embarquer OpenCV et NumPy en processus, et non piloter une CLI.

**Nature.** Contrainte du cœur ignorée, et contradiction avec le principe de
cadrage. **Sévérité : moyen** — mais elle décide de la technologie, que la spine
dit trancher après (`EXPERIENCE.md:21`).

---

#### M6 — Aucune commande n'émet de document `previz-1`

**Spine.** `EXPERIENCE.md:29-32` : « Les documents `previz-1` (kinds
`extraction`, `makepdf`, `scan`, `encode`) sont **consultatifs** ». Ils sont la
source implicite de tout ce que l'interface affiche.

**Produit.** Les quatre constructeurs — `build_extraction_previz`,
`build_pdf_previz`, `build_scan_previz`, `build_encode_previz` — **n'ont aucun
appelant dans `src/`** (vérifié : seules occurrences hors `def`, leurs propres
`__all__`). Aucune sous-commande ne les émet, aucun n'est persisté.

**Nature.** Fonction supposée inexistante *au niveau de la surface*. Les
bibliothèques existent et sont testées ; ce qui manque est le producteur et son
domicile sur le disque. **Sévérité : moyen.**
**Ce qu'il faudrait.** Une story qui expose ces documents (sous-commande
`previz --kind`, ou écriture systématique à côté du rapport), sans quoi la GUI ne
peut être qu'un consommateur in-process — même conclusion que M5.

---

#### M7 — Les frames absentes « rangées à leur place par timecode » : les timecodes manquants sont introuvables

**Spine.** P3 étape 2 (`EXPERIENCE.md:465`) : « Galerie : six images en
`{colors.state-absent}`, **rangées à leur place par timecode**. » `:200` : « la
case **reste à sa place** dans la grille ».

**Produit.** Les timecodes d'une page sont portés par **son** QR
(`slots[].frame_timecode`) ; une page dont le QR n'a rien livré « ne porte ni
frame ni motif — sans timecode il n'y a pas de frame a ecrire, mais un trou a
declarer » (`cli.py:864-868`). Ils sont récupérables **uniquement** depuis le lot
d'extraction (les fichiers de `frames/`, nommés par timecode) —
`lots[].frame_timecodes_digest` étant un condensat, pas une liste. Donc : vrai en
P1/P3 (Camille a tout le projet), **faux** en P2 variante « projet vide » et sur
tout projet né du scan seul, où la galerie ne peut afficher qu'un trou anonyme.

**Nature.** Donnée supposée que rien ne porte, dans un régime précis.
**Sévérité : moyen.** **Ce qu'il faudrait.** Nommer le régime dans la spine.

---

### FAIBLE

---

#### F1 — La page de calibration est aujourd'hui insérée d'office, pas « demandée »

Spine, P1 étape 8 : « Planche de calibration **demandée** en haut à droite ».
Produit : `compose_lot_plan` l'ajoute automatiquement à l'index 0 de tout lot dont
la géométrie peut la porter — `page_count = images_page_count + (0 if
calibration_refusal else 1)` (`pdf_composition.py:1203-1208`). L'inversion est
prévue par `EPIC5-ARB-80` décision 7 (« L'insertion automatique […] est
abandonnée ; la page est generee **a la demande** »), non livrée. Même cause
que C5. **Sévérité : faible** (la cible rejoint la spine).

---

#### F2 — Les cadences NTSC ne sont pas saisissables

`DESIGN.md:230` cite « cadences (`12,5` / `25`) », et `EXPERIENCE.md:170` des
flèches de cadence suivante/précédente. `extract --fps` est un `float`
(`cli.py:2460`) : `24000/1001` n'est pas exprimable. La story **3.8**
(`fps-fractionnaire-en-ligne-de-commande`) est `ready-for-dev`
(`sprint-status.yaml`). **Sévérité : faible.**

---

#### F3 — « Espace disque annoncé » est un **majorant**, et ne le dit pas

Il existe (voir *Faux écarts*, X2), mais c'est une borne haute non compressée :
« borne = largeur x hauteur x 3 canaux x 2 octets x nombre de frames, TIFF
16 bits non compresse; **la compression n'est pas modelisee** »
(`source_confirmation.py:884-891`). Même défaut que `estimated_bytes` côté
encodage (« majoration jamais optimiste »). Un chiffre affiché sans sa nature se
lit comme une mesure. **Sévérité : faible.**

---

## 3. Écarts correctement signalés

Le dispositif marche, et il faut le dire : les six endroits ci-dessous sont
rédigés exactement comme un développeur en a besoin.

* **La table *Cible non livrée*** (`EXPERIENCE.md:369-383`) : quatre lignes, avec
  pour chacune l'état réel *et* ce qui la débloque. Les quatre sont exactes,
  vérifiées au code : ingest en vrac (`_check_lot_consistency` refuse tout lot
  mixte, `io/reconstruction.py:301-313`) ; seconde passe refusée en « planche
  périmée » sans échappatoire (`io/scan_manifest.py:687-696`, et le `--overwrite`
  de `scan` déclare lui-même « Ne leve **aucun** refus de planche etrangere »,
  `cli.py:2543-2551`) ; date de scan absente (story 5.13 `ready-for-dev`) ;
  cadence source réclamée à la main (`--cadence-source`, `cli.py:2438-2447`, et
  `ENCODE_SOURCE_RATE_MISSING`).
* **La note de dépendance sur les images d'aperçu** (`EXPERIENCE.md:127-134`) :
  elle dit que la fonction n'existe pas, qu'une story la porte, et que **le mode
  lecteur ne peut pas être simulé** tant qu'elle n'est pas livrée. C'est le
  modèle à généraliser.
* **Le rôle 8 du chutier** (`:91`) et le **comparateur de candidats**
  (`:205`), tous deux marqués *(cible non livrée)*.
* **La section *Composition d'un lot à partir de candidats*** (`:262`), déclarée
  « état cible, non livré » en tête.
* **L'articulation avec le discriminant de version du cœur** (`:290-293`) : la
  spine nomme la story 5.14, son numéro à deux chiffres, et dit explicitement que
  rien n'est tranché.
* **La désignation de ce qui alimente l'encodage** (`:257`), marquée *(cible non
  livrée — arbitrage 2)*.

---

## 4. Faux écarts

À ne pas transformer en stories : ces points ont l'air non livrés, ils existent.

* **X1 — L'ordre du refus « lot déjà présent ».** La spine exige que l'erreur se
  lève « **au clic sur « extraire les lots », pas dans la fenêtre de
  confirmation** » (`EXPERIENCE.md:432`). C'est exactement l'ordre du cœur : le
  refus est à l'étape 1, avant le probe et avant la confirmation de la story 3.3
  (`extraction.py:694-700`, ordre documenté `:629-640`).
* **X2 — L'espace disque de la modale d'extraction.** Livré :
  `disk_upper_bound_bytes`, ligne « Occupation disque, borne haute non
  compressee » du rapport de confirmation (`source_confirmation.py:882-891`).
  Voir F3 pour la seule réserve.
* **X3 — L'adressage `page_index` + `slot_index` des surimpressions.**
  Livré et nommé : `PAGE_ADDRESS_FIELDS`, `FRAME_ZONE_ADDRESS_FIELDS`,
  `MARKER_ADDRESS_FIELDS` (`scan_previz.py:26-45`), avec `read_rank` toujours
  présent **parce que** `page_index` vaut `None` quand le QR n'a rien livré —
  c'est-à-dire précisément le cas que l'édition doit adresser.
* **X4 — L'état « détecté, rien d'écrit » du contrat de previz.** Il existe :
  `state = "detected"` (« aucune frame ecrite ») contre `reconstructed`
  (`scan_previz.py:1083`, `:1131`). C'est le **producteur** qui manque (C1), pas
  le vocabulaire.
* **X5 — Deux lots du même rush à deux cadences.** Livré en v2.1 : « Un projet
  peut porter plusieurs lots du meme rush a des cadences differentes »
  (`io/reconstruction.py:663-667`).
* **X6 — Les points in/out saisissables au timecode.** Livrés (story 3.7,
  `--in` / `--out`, `cli.py:2492-2506`), et ils entrent dans l'identité du lot
  (`extraction.py:679-690`).
* **X7 — Les codes de refus d'encodage affichés verbatim.** Livrés :
  `ENCODE_REFUSAL_CODES`, trente codes fermés (`encode.py:200-230`), et le plan
  `planned` existe bien à côté (`encode_previz`). La spine a raison de les
  afficher tels quels.
* **X8 — La mire de remplacement.** Produite par le cœur
  (`scan_output_frames.build_missing_frame_image:631`) et son registre est
  **durable par lot** (`lots[].synthetic_frames`, explicitement posé là « et non
  dans reconstruction, qui est reecrite en entier a chaque passe »). Le code
  couleur *complet / complet-avec-mires* du chutier est donc alimentable.
* **X9 — Un lecteur embarquable.** `cadence_previz` expose une abstraction de
  sortie (`NullSink` / `CvWindowSink`, `cli.py:2263-2266`) : une GUI ajoute son
  sink sans réécrire le moteur de cadence. Point d'extension prévu, pas un
  obstacle.

---

## 5. Contraintes du cœur que la spine ignore

Elles ne bloquent pas toutes, mais elles mordront à l'implémentation.

1. **Vocabulaires fermés et schéma fermé.** Racine, `lots[]` et `rushes[]` sont
   en `additionalProperties: false`. Toute donnée d'interface nouvelle est une
   story de schéma, et l'échec arrive **après** l'écriture des fichiers
   (`epics.md:356`). Voir C3.
2. **`page_index` est en base zéro partout, la base un n'existe qu'à
   l'affichage** (`pdf_composition.py:17-18`). La spine parle de « page 4 »
   (P3) ; le document parlera de `page_index: 3`. La règle « les codes du cœur
   s'affichent verbatim » (`DESIGN.md:344`) doit se doubler d'une règle de
   conversion, sans quoi l'écran affichera deux numéros pour la même page.
3. **Idempotence octet à octet du rescan** (story 5.7 AC 10). Tout champ
   horodaté ou dépendant de la session doit être **hors comparaison** — c'est
   toute la raison d'être de la story 5.13. Une interface qui écrirait une date
   d'action au manifest casserait la garde.
4. **`lot_id` n'a aucune contrainte d'unicité au schéma**, et `_find_lot` rend le
   **premier** (`deferred-work.md:2213-2219`). Une interface qui laisse composer
   des identifiants doit garder l'unicité elle-même.
5. **L'identité d'un lot scanné change** après 5.12 / 5.14 :
   `<lot_id>-<condensat>-<version>` (`epics.md:229, 240`). La spine affirme
   l'inverse : « **un lot ne change pas d'identité en étant composé** »
   (`EXPERIENCE.md:285`). Les deux ne peuvent pas être vraies ensemble.
6. **Le budget du QR est saturé.** Le champ `page_role` a coûté 9 octets et fait
   tomber `SLOTS_PER_PAGE_AT_ALERT_BUDGET` de 20 à 19 ; la version 22 de symbole
   est **bannie** parce qu'illisible (`qr_codes.QR_BANNED_SYMBOL_VERSIONS`,
   action item fermé de l'Epic 4, `sprint-status.yaml`). Un payload 2.1 portant
   la cadence source — que la spine appelle de ses vœux (`EXPERIENCE.md:381`) —
   doit être budgété avant d'être promis.
7. **Le dpi de scan n'est jamais deviné** et est obligatoire (`cli.py:2521-2527`,
   « un DPI faux fausse toute la geometrie aval sans erreur visible »). La
   planche imprime la consigne « Scanner a 600 dpi minimum »
   (`pdf_composition.py:1228`). L'interface doit exiger ce champ à chaque dépôt,
   ce que la spine ne dit qu'en passant.
8. **`--overwrite` n'est pas une issue universelle.** Sur `scan`, il ne lève
   **aucun** refus de planche étrangère ou périmée (`cli.py:2543-2551`), et il
   n'existe pas du tout sur `persist_scan` (« la persistance **enregistre le
   reel** et ne refuse jamais », `io/scan_manifest.py:1845-1848`). La modale
   « écraser » de `DESIGN.md:314` ne peut donc pas être proposée devant tous les
   refus.
9. **La zone tampon n'a pas d'équivalent au cœur.** L'ingestion **copie** tout
   sous `scans/<slug>/` (`scan_ingest.py:769-791`) et rattache tout à un lot
   unique ; un fichier « déposé mais pas décodé », ou « non rattaché après
   détection », n'est représentable nulle part — et aujourd'hui un lot mixte fait
   échouer la passe entière plutôt que de laisser un reliquat.
10. **La confirmation de source (3.3) est un dialogue interactif** sur `stdin` /
    `stdout` (`source_confirmation.py:1043-1091`). Une GUI qui passe `--yes`
    court-circuite un consentement à **deux** volets — l'accord général et
    `unknown_color_accepted` — dont le second n'apparaît nulle part dans la
    modale décrite par la spine.

---

*Fin de la revue. Aucun fichier autre que celui-ci n'a été créé ou modifié ;
rien n'a été commité.*
