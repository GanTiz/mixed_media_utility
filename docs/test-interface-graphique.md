# Tester l'interface graphique a la main

Etat au **2026-08-26**, commit `088e6b4` sur `main`. Stories **7.0 a 7.4**
livrees et closes ; **7.5 et au-dela** au backlog.

Ce document dit ce que tu peux **cliquer aujourd'hui**, ce qui est **visible
mais inerte**, et ce qui **n'existe pas encore**. Tout ce qui suit a ete
verifie en lancant reellement l'application, pas deduit des fiches.

> **La CLI reste le livrable complet.** `bin/mmu` fait toute la chaine. L'interface
> ne couvre aujourd'hui qu'une partie du Scan, et rien des trois autres ateliers.

---

## 1. Lancer

```
python -m mixed_media_utility.gui
```

Depuis la racine du depot. Il n'y a **pas** de `bin/mmu-gui` : un lanceur
releve du packaging (Epic 8). Rien a installer -- comme la CLI, la GUI tourne
par `PYTHONPATH` sur `src/`.

```
$env:PYTHONPATH="src"; python -m mixed_media_utility.gui
```

Il faut **PySide6** (mesure ici en 6.8.3).

---

## 2. Le probleme d'abord : aucun scan du depot n'est lisible

C'est le point le plus important de ce document, et il vaut mieux le savoir
avant de perdre une heure.

Le depot contient cinq scans ingeres. **Aucun ne peut produire de document de
detection**, et donc aucun ne peut alimenter l'atelier Scan. Mesure, faite sur
les deux seuls dont le PDF est reellement present (les trois autres sont des
pointeurs Git LFS non materialises) :

| scan | verdict |
| --- | --- |
| `projet_demo/scans/TEST_FILE_12p5` (7 pages) | 7 feuilles refusees -- **payload sans version** (schema 1.0, cles longues) |
| `chendj-mat/scans/rush-bitch-4-scan2` (3 pages) | 3 feuilles refusees -- **payload 2.0**, attendu **2.1** |

Le message du coeur est explicite : « Il n'existe pas de lecteur bi-format
(`EPIC5-ARB-60`) : cette planche doit etre **reimprimee** pour etre
rescannable. » Ce n'est pas un defaut, c'est une decision : la branche de
lecture 1.0 a ete retiree par la story 2.7, et 2.0 n'a jamais eu de lecteur.

**Conclusion pratique** : pour tester l'atelier Scan, il te faut une planche en
**payload 2.1**. La section suivante t'en fabrique une sans imprimante ni
scanner.

---

## 3. Se fabriquer des donnees testables en deux commandes

Le depot porte trois planches en payload 2.1, generees le 2026-08-25 :

```
projects/projet_demo/patches/projet_demo_planche_4f_heteroclite_*_planches.pdf   (13 Mo, 4 frames)
projects/chendj-mat/patches/..._1-c60b2a76_planches.pdf                          (48 Mo, 4 frames paysage)
projects/chendj-mat/patches/..._2-705fa2e2_planches.pdf                          (101 Mo, 8 frames portrait)
```

Un PDF de planches **est** une page imprimable. Le donner directement a
`scan detect` simule un scan parfait : pas de bruit, pas de rotation, pas de
tirage. C'est suffisant pour exercer toute l'interface.

```bash
# ~3 minutes. Produit un document de detection dans projet_demo.
bin/mmu scan \
  --project projects/projet_demo \
  --scan "projects/projet_demo/patches/projet_demo_planche_4f_heteroclite_planche_4f_heteroclite_4_planches.pdf" \
  --dpi 600 \
  --lot-slug demo-synthetique \
  detect
```

Sortie attendue, verifiee :

```
1 page(s) ingeree(s) dans scans/demo-synthetique a 600 dpi
Document de detection ecrit: projects/projet_demo/scans/demo-synthetique/detections/detect-<horodatage>.json
scan detect termine avec succes. 1 page(s), 1 identifiee(s).
```

Le document produit porte : **1 planche, statut `ok`, QR decode, 4 zones
proposees, les quatre marqueurs de coin lus**. C'est le cas nominal parfait --
les deux verrous au vert.

Pour un second jeu de donnees, plus fourni (8 frames) :

```bash
bin/mmu scan \
  --project projects/chendj-mat \
  --scan "projects/chendj-mat/patches/chendj-mat_rush-bitch-4-chendj-mat_rush-bitch-4-chendj-mat_2-705fa2e2_planches.pdf" \
  --dpi 600 \
  --lot-slug chendj-synthetique-8f \
  detect
```

Compte ~110 Mo sur disque pour celui-la (la page rastérisee a 600 dpi).

> **Le `--lot-slug` n'est pas decoratif.** Sans lui, `scan detect` derive le slug
> du **nom du fichier**, ce qui donne un dossier different de celui ou vit le
> PDF -- et la commande echoue sur un message trompeur (« Erreur d'acces disque
> [...] Verifier l'espace disponible »). Defaut reel, trouve en ecrivant ce
> document, consigne a `deferred-work.md`. Passe toujours `--lot-slug`.

---

## 4. Le parcours, du lancement au jugement

### 4.1 L'ecran de gestion de projet

C'est **toujours** la premiere surface. Aucune reprise automatique dans le
dernier atelier ouvert, meme quand un seul projet est connu.

* **un clic** sur une ligne la designe et active le bouton **Ouvrir** en bas ;
* **un double-clic** ouvre directement ;
* **Creer un projet** / **Ouvrir un dossier** / **Importer un projet existant**
  ouvrent une boite systeme de choix de dossier ;
* la fleche a droite d'une ligne **epingle** le projet -- un projet epingle
  resiste au tri par date ;
* la **croix** a droite de la fleche **retire le projet de la liste**. Elle ne
  touche **aucun fichier** : le dossier et son `project.json` restent ou ils
  sont, et redesigner le dossier fait revenir la ligne a l'identique. Aucune
  confirmation n'est demandee, pour cette raison exactement. La croix est
  presente sur **toutes** les lignes, y compris celles qui affichent une erreur
  -- c'est meme le cas qui l'exige, puisqu'une ligne en erreur ne se designe
  pas ;
* tri (nom / creation / modification) et recherche libre au-dessus de la liste.

La ligne **designee** porte une **bordure d'accent bleu** sur ses quatre cotes.
Le **dernier projet ouvert** porte, lui, un lisere d'accent sur son bord gauche
et un libelle qui le nomme, mais il **n'est pas preselectionne** : il faut
cliquer dessus comme les autres.

> **Repartir d'un ecran vide.** La liste des projets connus, les epingles et le
> dernier ouvert vivent dans les reglages de l'utilisateur, pas dans le depot
> (`QSettings`, soit `HKCU\Software\mixed_media_utility` sous Windows). Les
> retirer un par un avec la croix suffit. Pour tout effacer d'un coup :
>
> ```
> python -c "from PySide6.QtCore import QSettings, QCoreApplication; QCoreApplication([]); s=QSettings('mixed_media_utility','mixed_media_utility'); [s.remove(c) for c in s.allKeys()]; s.sync()"
> ```

### 4.2 La coquille

Une fois un projet ouvert : en-tete, puis une bande **arborescence | chutier |
scene**, et **quatre onglets en bas** -- Extraction, Pdf, **Scan**, Exports.

* **un clic** sur un noeud (arborescence ou chutier) **designe** l'objet, sans
  changer d'atelier ;
* **un double-clic** **ouvre** l'objet -- ce qui active l'onglet ou cet objet est
  en jeu : rush -> Extraction, lot ou planche -> Pdf, **scan -> Scan**, lot
  reconstruit ou rush encode -> Exports ;
* la poignee entre arborescence et chutier se deplace ; sous **1180 px** de
  largeur de fenetre, l'arborescence se replie **seule**. Un repli que tu as
  choisi explicitement survit au franchissement du seuil ;
* le bouton en tete du chutier le passe en **plein ecran** ; un second clic
  restaure exactement la geometrie d'avant ;
* la fenetre refuse de descendre sous **960x680**.

### 4.3 Atelier Scan, premier temps : deposer et detecter

* **glisser-deposer** dans la zone « En attente de lecture », en haut du
  chutier. **N chemins deposes = N entrees** ; **un dossier = une seule
  entree** ;
* chaque entree porte une case a cocher (cochee par defaut), un champ **dpi
  vide**, et un bouton **Retirer de la file** -- le seul geste qui sort une
  entree de la file. Une detection terminee ou echouee n'en retire aucune ;
* le bouton **Detecter** est au **chutier**, jamais dans la page Scan.

**Ce qui active « Detecter »** : au moins une entree cochee, **et toutes** les
entrees cochees portent un dpi. Ce n'est pas « au moins une a un dpi ». Une
phrase a cote dit laquelle des deux conditions manque.

**Au clic** : une carte de tache par entree, deux etats honnetes -- « En cours »
puis « Terminee », ou « Echouee » avec le motif du coeur affiche **verbatim**.
**Aucune jauge, aucun temps restant** : ce n'est pas un oubli, c'est interdit
tant qu'aucune mesure reelle de cadence n'existe (`EPIC7-ARB-67`).

Une entree qui contient **plusieurs lots** donne **une carte par lot trouve**.
Ce que la detection ne rattache a rien reste **visible et nomme** dans la file,
avec son motif ; une page appartenant a un **autre projet** apparait a part,
avec le nom du projet a utiliser quand le document le porte.

### 4.4 Atelier Scan, second temps : juger

**Le geste qui y mene, et le seul** : **double-clic sur un noeud de type
scan**. Aucun autre type d'objet n'y mene.

La page Scan est une pile de deux surfaces ; **il n'y a pas de bouton
« retour »**. Ce qui ramene au premier temps :

| geste | effet |
| --- | --- |
| double-clic sur un noeud **scan** | va au **second temps**, sur cette planche |
| document de detection introuvable ou illisible | **reste au premier temps** -- pas de surface vide |
| clic sur **Detecter** | ramene au premier temps |
| ouvrir un **autre** projet | ramene au premier temps |
| ouvrir un rush ou un lot | change d'**onglet**, mais ne referme pas le jugement -- en revenant sur Scan tu le retrouves |

Le second temps porte deux onglets, **Page** et **Galerie** (un troisieme,
**Frame**, n'apparait qu'apres un clic sur une case de la galerie).

**Onglet Page (mode PDF)** -- c'est la surface la plus aboutie. Verifie sur le
jeu de donnees de la section 3 :

* la page scannee en entier, avec les **zones proposees** surimprimees et les
  marqueurs ArUco ;
* sous l'image, la legende par emplacement : `Emplacement 0 / 2675 x 1504 px /
  00:00:00:00`, une colonne par frame ;
* **deux verrous independants**, chacun son indicateur : **Identite (QR)** --
  « quel lot, quelle planche » -- et **Geometrie (ArUco)** -- « ou se trouvent
  les zones ». La proposition de zones exige **les deux** au vert ;
* la phrase d'etat en clair : « Les quatre marqueurs de coin sont lus. » ;
* les controles de vue : **Ajuster**, Pleine largeur, Pleine hauteur, 100 %, et
  un curseur de zoom.

**Onglet Galerie** : le badge de completude du lot, l'apercu de la page entiere,
et une case par emplacement portant sa taille et son timecode. **Un clic simple**
(pas un double) sur une case ouvre l'onglet Frame.

---

## 5. Les pieges

Dans l'ordre ou tu risques de les rencontrer. Aucun n'est un bug.

1. **Un projet neuf n'a aucun noeud « scan » dans l'arbre**, meme si tu as mis
   des fichiers dans son dossier a la main. Les noeuds scan viennent
   **exclusivement** des documents de detection ecrits par `scan detect`, jamais
   d'un listing de dossier.
2. **`Detecter` reste grise** des qu'**une seule** entree cochee n'a pas de dpi.
3. **La bascule brut / corrige de l'en-tete est grisee**, sur tous les projets,
   et le restera. Il n'existe **aucune** image corrigee : la calibration active
   est post-MVP (`EPIC5-ARB-5`). Le bouton reste **visible et grise** plutot
   qu'absent, parce que le critere retenu est la reversibilite et non la
   disponibilite du moment (`EPIC7-ARB-24`).
4. **Dans la Galerie, chaque emplacement dit « Aucune image ici »** -- meme
   apres un `scan-write` qui a bel et bien ecrit les TIFF. **Verifie ici** : les
   quatre frames existaient sur disque et la galerie affichait toujours
   « Aucune image ici ». C'est le comportement prevu : aucune vignette recadree
   n'est fabriquee avant l'extraction (story **7.6**). Ce que tu vois d'image
   reelle, c'est la **page entiere** -- en apercu dans la galerie, et zoomee
   dans l'onglet Frame.
5. **Un lot fraichement detecte peut s'afficher « Incomplet »** alors qu'aucune
   planche ne manque : a l'etape `detected`, la completude porte sur les
   **planches**, pas sur les frames. Depuis `EPIC7-ARB-73` elle est lue d'une
   **source unique au coeur**, donc l'arbre et l'annonce ne se contredisent plus
   entre eux -- c'etait le cas avant le 2026-08-25.
6. **Un panneau lateral s'ouvre a droite des vues Page et Galerie, avec une
   poignee qui marche, et il est vide.** Rien n'y est encore pousse.
7. **Un refus de planche affiche la phrase du coeur, jamais un code.** Le champ
   de code existe cote interface mais **aucun producteur ne l'ecrit** : la story
   de coeur qui devait le livrer (5.27) a ete abandonnee le 2026-08-25.
8. **Quand le document ne dit pas quel verrou a lache**, l'ecran affiche
   « Aucune zone proposee : cette planche a ete refusee au scan », **sans nommer
   de verrou**. C'est deliberе (`EPIC7-ARB-75`, 2026-08-26) : la version d'avant
   accusait le QR sur une planche dont le QR avait tout livre, ce qui envoyait
   verifier le mauvais element.
9. **Les trois autres onglets -- Extraction, Pdf, Exports -- sont litteralement
   vides**, avec la mention « Zone reservee ». Ce n'est pas une erreur de
   chargement.
10. **Les projets d'avant le schema v2.1 sont des lignes en erreur, avec leur
    motif.** Au depot, `projects/example`, `projects/demo_review` et
    `projects/manual_test` portent un manifest d'ancienne forme (une cle `id`,
    aucun `schema_version`) : ils sont **reellement** illisibles, et l'ecran le
    dit plutot que de les masquer. Seuls `projet_demo` et `chendj-mat` sont en
    v2.1. La croix de retrait est la pour les faire sortir de la liste.
11. **Le dossier `projects/` n'est pas un projet, c'est le conteneur des
    projets.** Le designer dans « Creer un projet » y ecrit un `project.json`
    a la racine et fabrique un projet nomme « projects », qui contient tous les
    autres. Il n'y a **aucun champ de nom** dans le geste de creation : le nom
    du projet EST le nom du dossier designe, et aucun sous-dossier au nom de
    l'outil n'est cree (`EPIC7-ARB-28`). Creer le dossier depuis la boite
    systeme (« Nouveau dossier ») puis le designer est le geste attendu.

> **Trois defauts rapportes au premier essai du 2026-08-26 sont corriges** et
> ne se rencontrent plus : la coquille s'ouvrait sans son projet (arbre vide
> partout, et « argument should be a str or an os.PathLike object [...] not
> NoneType » au clic sur Detecter), la ligne designee n'etait pas distinguable,
> et rien ne retirait un projet de la liste. Detail :
> `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-26.md`.

---

## 5 bis. Regarder l'interface sans la lancer

```
python scripts/gui/capturer_ecrans.py
```

Onze PNG dans `captures-gui/` (ignore par git, se regenere en une commande) :
l'ecran de projet vide, peuple et avec une ligne designee ; la coquille sur ses
quatre ateliers et sur un noeud designe ; l'atelier Scan **peuple sur un vrai
document de detection du depot**, en vue page, galerie et frame.

Aucun ecran n'est requis, aucun serveur graphique non plus : `QWidget.grab()`
rend le widget dans une image sans passer par la capture d'ecran du systeme.
Tes reglages ne sont pas touches -- les captures utilisent un `QSettings` INI
jetable.

C'est ce harnais qui a trouve, le 2026-08-26, ce qu'aucun des 450 tests d'alors
ne pouvait voir : les poignees de `QSplitter` en bandes claires au milieu de la
coquille, le gris de Windows sur 66 % de la vue galerie, et des icones d'arbre
entierement vides parce qu'un `QColor` etait interpole dans un document SVG. La
non-regression est desormais tenue par `tests/unit/gui/test_palette_peinte.py`,
qui compte les couleurs peintes.

---

## 6. Ce qui n'existe pas encore, et quelle story le livrera

| ce que tu ne pourras pas faire | story |
| --- | --- |
| corriger un QR non decode, poignees de coin, loupe, annulation | **7.5** |
| ecrire les TIFF depuis l'interface, mode lecteur, vignettes recadrees | **7.6** |
| atelier Exports (encoder un master) | **7.7** |
| retrouver un rush deplace depuis l'interface (relink) | **7.8** |
| menu contextuel sur l'arbre | **7.11** |
| comparer deux candidats de frame | **7.12** (backlog, attend le coeur) |
| lanceur `bin/mmu-gui`, installation | **Epic 8** |

Tout cela existe **deja en CLI** pour la plupart : `bin/mmu --help`.

---

## 7. Si l'interface ne demarre pas

**`Could not load the Qt platform plugin "xcb"`** -- sous Linux, il manque
`libxcb-cursor0` (`apt-get install -y libxcb-cursor0`). Sous macOS et Windows,
Qt n'a pas cette dependance.

**Pour verifier que l'interface se construit sans ecran** (utile en conteneur
ou par SSH) :

```
QT_QPA_PLATFORM=offscreen python -m mixed_media_utility.gui
```

Elle se construit, ne s'affiche pas, et sort. Si ca marche, le probleme est
l'affichage, pas l'application.

**La suite de tests de l'interface**, si tu veux verifier que rien n'est casse
avant de cliquer :

```
python -m pytest tests/unit/gui -q
```

426 tests, ~13 secondes.
