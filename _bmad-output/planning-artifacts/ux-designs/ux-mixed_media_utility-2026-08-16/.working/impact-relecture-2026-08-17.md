# Ce que la relecture d'Egan change — Epic 7

> Analyse d'impact des **38 notes** de la relecture, réception close.
> Source : `.working/relecture-egan-2026-08-17.md`.
>
> Trois catégories, dans l'ordre où elles coûtent : **corrections** (mon texte
> était faux, je corrige), **conception** (l'interface change, le memlog du
> 2026-08-16 s'enrichit), **arbitrages** (une décision antérieure est défaite,
> ou une fonction du cœur est demandée — ça ne se corrige pas en silence).

---

## 1. Les deux blocages sont tranchés — et vont tous deux vers l'Epic 5

| blocage | décision | conséquence de planning |
|---|---|---|
| Ingest en masse et en vrac | **(b) une story d'Epic 5 en amont** | le tri par QR devient une fonction du cœur ; la GUI l'expose, la CLI en bénéficie |
| Notion de version désignée | **la désignation vit au manifest** | c'est un contrat, donc une story d'Epic 5 **avant** l'Epic 7 |

**Ce que ça implique.** L'Epic 7 ne peut pas être spécifié complètement sans que
ces deux stories d'Epic 5 existent au moins comme contrat. Ce n'est pas
bloquant pour la Finalize de l'UX — les spines peuvent décrire l'interface
cible — mais ça l'est pour la rédaction des stories 7.x.

---

## 2. Corrections — mon texte était faux

Aucune décision produit là-dedans ; je reprends les parcours.

| note | correction |
|---|---|
| 5 | Le plan **faisait déjà** 100 frames ; les bornes ne l'y ramènent pas. |
| 7 | La marge par défaut est **0**, pas « confortable ». C'est éventuellement Camille qui en demande. |
| 9 | Reformuler « un mini-dialogue lui demande de quoi **il** a besoin » : le « il » désigne le dialogue, la phrase est illisible. Et le mini-dialogue ne demande **que le nom du scanner cible** — le reste est demandé au scan. |
| 10 | **Une seule planche est générée**, pas neuf. La planche A4-6f du lot 12p5 fait neuf pages (la dernière avec deux images) mais reste **une planche composée de pages**, donc **un seul PDF**. Deux PDF au total avec la calibration. *(Le memlog du 2026-08-16 disait déjà « une planche = un PDF » — l'erreur est la mienne, pas la sienne.)* |
| 8 | Rappeler qu'elles peuvent choisir **plusieurs** dispositions. |
| 15 | Dans Exports, elle **peut** changer de cadence, mais **par défaut c'est la cadence cible qui est sélectionnée**. |

---

## 3. Conception — ce que l'interface doit faire en plus

### 3.1 La distinction détection / extraction *(notes 12, 13, 20, 29, 31)*

**C'est le changement le plus structurant de toute la relecture.** Egan le
qualifie lui-même d'« ajout important ». Il traverse P1, P2, P3 et P5, et il
n'était **pas** dans le memlog du 2026-08-16 — qui ne connaissait qu'un
« bouton scan pour lancer l'extraction effective, une tâche par planche ».

L'atelier Scan se déroule désormais en **deux temps** :

1. **Détection.** Elle dépose des fichiers. Un bouton apparaît **au niveau du
   chutier** — pas dans la previz — pour lancer la détection. Ce n'est **pas**
   automatique : elle continue à charger des fichiers pendant ce temps. Elle
   **sélectionne ce qui part** en détection. Des cartes « détection » se
   forment en file d'attente. À la fin de chaque détection, on sait tout de
   suite si le lot est complet (code couleur).
2. **Extraction.** Ce que j'appelais « lancer le scan » est en fait
   l'**extraction en TIFF**. La détection seule a déjà produit la position des
   frames et un aperçu des frames retrouvées.

**Le mode lecteur.** En plus des modes PDF et galerie, un troisième mode
**lecteur** relit le rush reconstruit à sa cadence cible, en qualité temporaire
(PNG ?). Si le lot est complet, **on a un aperçu du rendu avant d'écrire quoi
que ce soit**. La raison d'Egan est décisive : *« si c'est raté, à quoi bon
écrire les frames ? »*

**Conséquence sur les autres parcours** — la répercussion est plus large que
les endroits où la note est posée :

* **P2** : Inès a déjà visionné le lot dans Scan (un aperçu) avant d'arriver à
  Exports ; le parcours doit le rappeler.
* **P3** : après avoir corrigé une page, elle relance la **détection**, pas
  l'extraction. Elle voit en galerie que c'est complet, **puis vérifie à la
  relecture que le résultat est conforme** avant de passer à l'export.
* **P5** : la comparaison entre deux traitements se fait **dans Scan avec la
  previz native**, pas dans Exports.

### 3.2 Le chutier et le dossier de travail *(notes 3, 4)*

* **Ce que mmu range dans le dossier de travail** : frames extraites, scans,
  frames reconstruites par scans, exports, calibrations. **Rien d'autre.**
* Les **rushes restent à leur place** dans l'arborescence du disque — on ne
  collecte que leur chemin d'accès, et on pourra les **relinker** si leur
  emplacement change.
* Ajout d'un rush : **boîte de dialogue système** *ou* **glisser-déposer**, y
  compris **plusieurs rushes à la fois**.
* Elle peut **créer des dossiers pour organiser ses rushes** (« séquence x »).
  Ces dossiers **ne concernent que le chutier**, jamais le dossier de travail.

### 3.3 Extraction *(notes 2, 6)*

* La source n'est pas forcément un rush entier : elle peut **extraire quatre
  secondes du montage en cours**.
* La fenêtre de confirmation **annonce l'espace disque requis**.

### 3.4 Calibration *(notes 9, 11)*

* Génération de la planche : **le nom du scanner cible**, rien de plus.
* Au scan de la planche de calibration : **nom du scanner, dpi, format**
  (pdf/tiff/jpeg/png) **et une invitation à commenter** pour identifier les
  réglages choisis au scan.

### 3.5 Réparation d'un scan *(notes 27, 28)*

* Avant de faire remplir le formulaire : **proposer de zoomer** sur l'image —
  à évaluer, ça aide ou pas.
* **On sait où les informations sont imprimées sur la page**, donc on peut les
  **pointer**. Egan va plus loin : *« on pourrait même les lire »* — c'est-à-dire
  les reconnaître automatiquement plutôt que les faire recopier.
  **[À CLARIFIER]** lecture automatique = une fonction à part entière, pas un
  détail d'interface. À confirmer avant de l'écrire dans un parcours.

### 3.6 P2 à remanier *(notes 18, 19, 21, 23)*

Le cas nominal que j'ai écrit — Inès crée un projet vide — **n'est pas le cas
nominal**. Le plus souvent **on lui a transmis le projet original** : elle le
charge, retrouve un certain nombre d'informations, mais **pas les rushes**.
Elle a donc **déjà vu les lots existants** avant de déposer le moindre scan.

* Le rush absent peut être **relinké** si on le lui a envoyé par ailleurs.
* **« Inès appelle Camille » : à éviter.** Un parcours dont le dénouement est
  un coup de téléphone est un parcours raté — voir §4.1.

### 3.7 Comparaison entre versions *(note 32)*

Pas de côte à côte : **l'un après l'autre**, plus un **outil « compare »** pour
passer de l'un à l'autre **au même timecode**. Ou un wipe — Egan laisse les
deux ouverts.

### 3.8 Écart 07, tranché *(note 37)*

**Pas de badge « projet reconstruit ».** On affiche simplement **ce qui est
délinké, en rouge**. Et on va plus loin que je ne l'imaginais : *on connaît le
nom du rush, donc on peuple les chutiers des autres pages et on l'affiche en
rouge*. Le code couleur suffit ; ma question était mal posée (voir §5).

### 3.9 Le public *(note 1)*

Aux deux protagonistes s'ajoutent : **les autres membres de la chaîne de
post-production** (dont Egan lui-même), et **à terme le public — des vidéastes**.

> « La facilité d'utilisation est un facteur clé. Sinon on pourrait envisager
> un tuto dynamique ? »

**Nouvelle préoccupation à porter dans les spines** : l'apprentissage. Un
tutoriel dynamique est une surface, pas une note de bas de page — il faudra
décider s'il entre dans le périmètre.

---

## 4. Arbitrages — ce qui défait une décision ou demande une fonction du cœur

Ces quatre points **ne se corrigent pas en silence**. Chacun contredit soit une
décision motivée déjà prise, soit ce que le produit livré sait faire.

### 4.1 La cadence source doit être portée par le QR *(notes 22, 24, 25)*

> « Alors le QR doit la porter … c'est un manque. Peu coûteux. »
> « Si ! Les timecodes lus sur les planches ! Ils y sont pour le coup. Et on
> connaîtra la cadence source. »

**Ce que ça défait.** Le schéma du manifest déclare aujourd'hui que la cadence
source, la base de timecode et la politique d'arrondi sont **irrécupérables**
depuis un scan — « leur absence est une propriété du document, pas un manque à
combler ». Toute la fin de P2 repose là-dessus, et l'encodage **exige** une
saisie manuelle de la cadence source.

**Ce que ça coûte.** Ajouter un champ au payload, c'est une nouvelle version de
son schéma. Le passage de la version 1.0 à la 2.0 a rendu **non scannables les
planches imprimées avant** — il n'existe pas de lecteur bi-format. Le même
risque se repose ici. « Peu coûteux » est vrai pour l'écriture, pas pour la
compatibilité des tirages déjà faits.

**Question ouverte** : la cadence source suffit-elle, ou faut-il aussi la base
de timecode ? Egan dit que la résolution « n'est pas tant le sujet ».

### 4.2 Une date de scan au manifest *(note 36 — « À corriger ! »)*

**Ce que ça défait.** Le schéma **interdit** aujourd'hui toute date dans la
section de scan, pour une raison assumée : une horodate rendrait deux passes
identiques distinguables et casserait la reproductibilité octet à octet. La
story qui rouvre la question existe (`5.13`, prête à développer, jamais faite).

**« À corriger » vaut donc décision de la développer** — mais l'arbitrage
d'origine mérite d'être défait explicitement, pas contourné.

### 4.3 Le lot hybride *(notes 30, 35)*

C'est le point le plus neuf de toute la relecture, et Egan le dit lui-même :
**« tout est à inventer à ce niveau. »**

Le scénario réel n'est pas « deux passes, on en choisit une » :

1. Camille imprime, essaie, **détecte et visionne l'aperçu**. Elle n'aime pas.
   **Elle n'extrait pas** — rien n'est écrit.
2. Elle **réimprime la même planche** (deuxième tirage) et rescanne : deuxième
   fichier sous le même lot, **même planche, version différente**. Ou bien une
   planche avec une **disposition différente** (2f au lieu de 4).
3. Et surtout : elle **n'a refait que trois frames**. Elle voudrait **intégrer
   ces trois frames aux frames déjà validées** pour fabriquer **un lot hybride,
   complet et composite**, et c'est celui-là qui part à l'export.

**Ce que ça défait.** Les stories amont disent explicitement qu'**aucune fusion
n'a été demandée**. Elle l'est maintenant. Et le grain n'est plus la passe : la
sélection se fait **à la frame**.

**Conséquence sur P5** : le parcours que j'ai écrit est trop simple. Son climax
— « elle en désigne une, l'autre reste » — n'est plus le bon. Le climax devient
la **fabrication du lot hybride**.

### 4.4 Écraser plutôt que refuser *(notes 33, 34)*

Aujourd'hui une seconde passe est **refusée** (« planche périmée »), et aucune
option ne lève le refus. Egan : *« gros problème en effet »*.

Le comportement voulu : on **garde une nouvelle version** — on invite Camille à
le faire. On peut **aussi proposer d'écraser** les frames actuelles, **sans
jamais le forcer, et en avertissant que c'est destructeur**.

---

## 5. Mes réponses à tes deux questions

**Note 26 — « Question ouverte : comment nommer cet état dans l'interface ? Je
ne comprends absolument pas à quoi cela correspond ?! »**

Le manifest porte un champ qui dit **d'où vient le projet** : né d'un scan, né
des seuls payloads QR, ou né d'une extraction d'origine. Ma question était :
faut-il que l'interface montre cette différence à l'utilisatrice. **Ta note 37 y
répond** — non, pas de badge, juste le code couleur de ce qui est délinké. La
question est close, je la retire.

**Note 38 — « Reconstruction depuis les seuls payloads QR, sans planche. Je ne
comprends pas ça ?! »**

Il existe une commande qui recrée un manifest de projet à partir des **seuls
payloads JSON** extraits des QR, **sans aucune image scannée** — on retrouve la
structure (rushes, lots, pages, timecodes) mais aucun pixel. Elle est livrée et
testée en CLI (story 2.6).

Je la signalais parce qu'aucune décision UX ne la couvre. **À mon avis elle n'a
pas sa place dans la GUI** : le cas d'usage réel — reprendre un projet à partir
de ce qu'on a reçu — est déjà couvert par le dépôt des scans, et par le chargement
du projet transmis (ta note 18). **Sauf objection, je l'écarte du périmètre.**

---

## 6. Ce que la relecture valide

Le **climax de P1 tient** — c'est la seule note franchement enthousiaste de
toute la relecture *(note 17)* :

> « On glisse, on transforme par magie. On pause on rejoue, image par image. On
> peut activer ou désactiver le wipe en un clic. On adore ! »

Trois précisions de comportement en découlent, à écrire dans le parcours : le
lecteur se **met en pause et rejoue image par image** pendant le balayage, et
le wipe **s'active et se désactive en un clic**. Ce n'est pas un détail : ça
fait du balayage un mode d'inspection, pas un effet de démonstration.

---

## 7. Ce qui reste à trancher

* **§4.1** — la cadence source dans le QR : à décider en connaissance du coût
  de compatibilité (les tirages déjà imprimés ne se rescanneraient plus).
* **§3.5** — « on pourrait même les lire » : pointage à l'écran, ou
  reconnaissance automatique des informations imprimées ?
