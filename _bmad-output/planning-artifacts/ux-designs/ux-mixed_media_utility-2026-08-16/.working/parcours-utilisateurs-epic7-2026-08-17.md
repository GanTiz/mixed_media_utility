# Parcours utilisateurs — Epic 7 (application GUI)

> **Version 2.1** — 2026-08-17, révisée après les deux relectures d'Egan : la
> première (38 notes, `.working/relecture-egan-2026-08-17.md`, triée dans
> `.working/impact-relecture-2026-08-17.md`) et la seconde, sur cette version
> même (6 notes, `.working/relecture-egan-v2-2026-08-17.md`).
>
> Ces parcours seront distillés en section **Key Flows** d'`EXPERIENCE.md` à la
> Finalize. Ils ne décrivent pas seulement un chemin heureux : ils servent à
> **fermer l'architecture d'information** — chaque besoin énoncé doit atterrir
> sur une surface, chaque surface doit être atteinte par un parcours.
>
> Ce qui n'existe pas encore dans le produit est signalé comme tel, jamais
> comblé par invention. Les arbitrages tranchés sont rappelés en fin de
> document avec ce qu'ils engagent.
>
> ---
>
> **Corrigé le 2026-08-23**, sur quatre points et rien d'autre. Le corps du
> document date toujours du 2026-08-17 ; les corrections portent leur référence
> sur place.
>
> 1. **Le cardinal de composition du parcours de référence était inatteignable**
>    (`EPIC7-ARB-48`). P1 demandait **6 frames par page** en laissant l'outil
>    choisir l'orientation ; le cœur n'offre `6` **qu'en paysage** —
>    portrait `(1, 2, 3, 4, 8)`, paysage `(1, 2, 4, 6, 8)`, défaut `2`. Egan a
>    tranché : *« je n'ai jamais demandé 6 images par page comme référence. C'est
>    une erreur mais on garde les cardinaux existants. »* P1 passe donc à
>    **8 frames par page**, atteignable dans les deux orientations, et
>    **l'exigence d'orientation automatique tombe** : elle n'existait que pour
>    rendre atteignable un cardinal qui n'avait jamais été demandé. Conséquence
>    arithmétique portée partout : 50 frames à 8 par page font **sept pages**,
>    la dernière n'en portant que deux — et non neuf. P5 corrige la même erreur
>    (`12` n'existe dans aucune orientation).
> 2. **L'arborescence n'est pas inversée** (correction A1). L'ordre reste
>    rush > lot > planche > scan, y compris dans un projet né des seuls scans ;
>    « remonter » y désigne la **reconstruction d'une branche à partir d'un scan
>    seul**, pas un arbre à l'envers.
> 3. **Le panneau latéral et le panneau de progression sont deux surfaces
>    distinctes**, à deux bascules indépendantes (`EPIC7-ARB-25`,
>    `EPIC7-ARB-26`). Le document les confondait en trois endroits ; les cartes
>    de tâche vivent dans le **panneau de progression**, jamais dans le panneau
>    latéral de réglages.
> 4. **Le double-clic sur une planche mène à la page Pdf**, pas à Scan
>    (`EPIC7-ARB-11`). Aucun parcours ne portait de carte de destinations à
>    corriger ; la règle est rappelée ici pour que la distillation en *Key
>    Flows* ne la réinvente pas.

---

## Qui travaille

**Camille** — cinéaste. C'est son film. Elle pilote les arbitrages de rendu et
elle porte le geste : c'est elle qui peint, plie, découpe les planches
imprimées. Elle sait que les **lectures techniques de la planche doivent rester
intactes** (marqueurs ArUco aux angles, QR code, patchs de calibration) et elle
se limite à l'espace réservé de chaque frame. Cette contrainte, elle l'a
intégrée comme un cadre de travail ; ce n'est pas l'interface qui la lui impose.
Elle vise l'autonomie technique — Egan peut assister, mais l'outil doit tenir
sans lui.

**Inès** — monteuse. Elle travaille sur **sa propre station**. Elle dispose
généralement des rushes natifs, parce qu'elle travaille avec Camille et que le
disque du projet circule entre elles. Mais à certains moments du workflow elle
n'a pas le disque : elle reçoit alors seulement le projet et les scans, et doit
pouvoir travailler quand même. C'est souvent elle qui **prépare le projet pour
et avec Camille** : ingest des rushes, réglages d'extraction, génération des
planches.

**Et autour d'elles.** Les autres membres de la chaîne de post-production, Egan
compris. Puis, à terme, **le public — des vidéastes**, quand le dépôt s'ouvrira.

> **Ce que cet élargissement impose.** « La facilité d'utilisation est un
> facteur clé. » Un outil qui tient parce qu'Egan est joignable n'est pas le
> même produit qu'un outil que des vidéastes prennent en main seuls.
>
> Le **tutoriel dynamique** évoqué par Egan est **hors v1** (tranché le
> 2026-08-17, consigné dans `deferred-work.md`) : l'apprentissage se conçoit
> sur une interface arrêtée, pas sur une interface en cours de définition. Mais
> **l'exigence, elle, reste dans la v1** et pèse sur toutes les décisions de ces
> parcours : choix par défaut partout, paramétrage avancé regroupé dans les
> Préférences, et un point de jugement avant chaque écriture. Ce n'est pas un
> tutoriel qui rendra l'outil prenable en main — c'est de ne jamais laisser
> quelqu'un fabriquer quelque chose qu'il n'a pas d'abord regardé.

### Ce que le projet contient, et ce qu'il ne contient pas

**Les rushes ne bougent pas.** Ils restent à leur place dans l'arborescence du
disque ; l'outil ne collecte que leur **chemin d'accès**, et sait les
**relinker** si cet emplacement change.

**Le dossier de travail ne contient que ce que mmu produit** : frames
extraites, scans, frames reconstruites à partir des scans, exports,
calibrations. Rien d'autre.

Le chutier, lui, est un espace de travail : Camille et Inès peuvent y **créer
des dossiers** pour organiser leurs rushes (« séquence 3 »). Ces dossiers
n'existent que dans le chutier et ne se reflètent **jamais** dans le dossier de
travail.

**Et le chutier a une zone tampon.** Un fichier scanné qu'on vient de déposer
n'a encore sa place nulle part dans l'arbre : **tant qu'il n'est pas décodé,
l'outil ne sait pas à quel lot il appartient**. Il vit donc dans une zone
d'attente — les fichiers déposés, pas encore décodés — d'où la détection les
tirera pour les ranger. Ce qu'elle ne parvient pas à rattacher **y reste**,
visible, plutôt que de disparaître.

### Contexte matériel

Le plus souvent elles travaillent sur le **disque du projet**, qui circule. En
mode dégradé, elles s'envoient le projet, les PDF, puis les scans.

Un lot compte un nombre de planches limité, mais un projet peut totaliser des
**centaines de pages**. Le scan est parfois fait **chez un prestataire** qui
numérise vite en 600 dpi. Ce qui revient est alors en masse et en vrac : c'est
aux QR codes de permettre à l'outil de retrouver ses petits.

---

## P1 — La chaîne complète, d'extract à encode

**Situation.** Camille veut faire passer par le papier un plan de 4 secondes
tourné en 25 fps — cent images. Ce n'est pas forcément un rush entier : elle
peut tout aussi bien **extraire quatre secondes du montage en cours**. Le
disque du projet est chez Inès, qui prépare la session ; Camille est à côté
d'elle.

### Déroulé

1. Inès lance l'application. L'**écran de gestion de projet** s'ouvre — il
   s'ouvre toujours au lancement. Le film de Camille n'y figure pas encore.
   Elle crée un projet et désigne le dossier de travail sur le disque.
2. L'atelier **Extraction** s'ouvre, chutier vide à gauche. Inès ajoute le
   rush — par la boîte de dialogue du système ou en le glissant dans le
   chutier, plusieurs à la fois si besoin. Le rush n'est **pas copié** : seul
   son chemin est retenu.
3. Le bandeau du haut affiche ce qu'il a lu du rush : source, résolution,
   cadence, durée. Le panneau de réglages du bas est **prérempli** des
   métadonnées du rush. Rien n'est en rouge : aucune métadonnée essentielle ne
   manque, l'extraction n'est pas bloquée.
4. Camille veut voir. Inès bascule en **mode vidéo** et lit le plan. Puis en
   **mode galerie** : la grille montre toutes les frames retenues pour la
   cadence courante. Camille active le toggle des **frames supprimées** — elles
   apparaissent en grisé au milieu des retenues, et elle voit d'un coup ce qui
   saute.
5. Elles posent les bornes sur les cent images du plan. Camille place l'entrée
   et la sortie dans le **bus de transport**, image par image, puis ajuste au
   timecode exact dans les champs prévus.
6. Cadence cible : la cadence originale est proposée par défaut. Camille veut
   la moitié — 12,5 fps, cinquante images à peindre plutôt que cent. Inès
   ajoute la cadence /2 d'un clic. Profondeur : 16 bits, la valeur par défaut,
   non discutée.
7. Inès clique **Extract**. Une fenêtre de confirmation liste les cadences
   retenues avec leurs cases à cocher — on peut lancer plusieurs extractions en
   une passe, sur les mêmes bornes — et **annonce l'espace disque requis**. Ici
   une seule cadence est cochée. Elle valide.
8. Une **carte de progression** apparaît dans le **panneau de progression** —
   la file des tâches, à droite, distincte du panneau latéral de réglages et
   dotée de sa propre bascule : le nom de la fonction, puis le nom du lot, puis
   la progression en frames/total avec temps passé et temps restant.
   L'extraction tourne **en arrière-plan**. *(Corrigé le 2026-08-23 : le
   parcours écrivait « panneau latéral ». Les deux surfaces sont distinctes —
   `EPIC7-ARB-25` pour la rétraction du panneau latéral, `EPIC7-ARB-26` pour la
   bascule ancré/superposé de la file — et fermer l'une n'a aucun effet sur
   l'autre.)*
9. La carte passe au **vert**. Le lot apparaît **sous son rush**, comme une
   branche de l'arbre. Un bouton ouvre le dossier des frames dans le système —
   un bouton dossier seul, puisqu'il s'agit de fichiers multiples.
10. Inès clique sur le lot. Elle arrive sur l'atelier **Pdf**, ce lot déjà
    ouvert. Le chutier est le même qu'à l'extraction : rush > lots > planches.
11. Réglages de planche : **8 frames par page**, format A4. La **marge de
    travail est à 0 par défaut** ; c'est éventuellement Camille qui en demande,
    pour déborder à la gouache. Le gabarit et le dpi ne sont pas exposés.
    *(Corrigé le 2026-08-23, `EPIC7-ARB-48` : le parcours demandait 6 frames par
    page, cardinal que le cœur n'offre qu'en paysage — portrait `(1, 2, 3, 4, 8)`,
    paysage `(1, 2, 4, 6, 8)`, défaut `2`. `8` est atteignable dans les deux
    orientations. L'**orientation automatique n'est plus exigée** : elle
    n'existait que pour rendre atteignable un cardinal qui n'avait pas été
    demandé, et le choix d'orientation appartient à l'opératrice.)*
12. L'**aperçu est vivant** : chaque changement de réglage redessine la planche
    sous leurs yeux. Aucun bouton à presser. Elles peuvent demander
    **plusieurs dispositions** — et choisissent simplement laquelle des
    planches à générer elles veulent regarder.
13. Camille clique le bouton **planche de calibration** en haut à droite. Un
    mini-dialogue s'ouvre et lui demande **le nom du scanner cible**, rien de
    plus — le reste sera demandé au moment du scan. La planche produite va dans
    la section **Calibration** du chutier, à part des planches d'images.
14. Génération. **Une planche est générée** pour ce lot dans cette disposition
    — la A4-8f du lot 12,5 fps. Elle fait **sept pages**, la dernière n'en
    portant que deux, mais c'est **une planche composée de pages**, donc **un
    seul PDF**. *(Corrigé le 2026-08-23, `EPIC7-ARB-48` : 50 frames à 8 par page
    font 7 pages et non 9 ; le reliquat de deux images sur la dernière page,
    lui, ne change pas.)* Deux PDF au total avec la calibration. La carte de progression
    compte les pages générées. Camille imprime.
15. **Trois semaines passent.** Camille peint, plie, découpe — dans les cadres,
    sans jamais toucher les angles ni le QR. Elle rapporte les planches. Le
    prestataire les numérise à 600 dpi.
16. Atelier **Scan**. Elle dépose d'abord le scan de la planche de calibration
    et clique **calibration scanner**. On lui demande le **nom du scanner**, le
    **dpi**, le **format** du fichier, et on l'invite à **laisser un
    commentaire** pour identifier les réglages qu'elle a choisis au scanner. Un
    profil est créé ; il apparaît sous la page de calibration dans la section
    Calibration.
17. Elle dépose les scans des planches. **Où atterrissent-ils ?** Nulle part
    dans l'arbre : tant qu'un fichier n'a pas été décodé, **l'outil ne sait pas
    à quel lot il appartient**. Il tombe donc dans une **zone tampon du
    chutier** — les fichiers déposés, en attente de décodage. C'est là qu'ils
    vivent jusqu'à la détection, et c'est ce qui permet de continuer à en
    charger sans rien décider.
18. **Rien ne se lance tout seul** : un bouton **Détecter** apparaît au niveau
    du **chutier**, et elle continue à charger des fichiers pendant ce temps.
    Elle **coche dans le tampon ce qu'elle veut envoyer** en détection.
19. La détection part. Des **cartes « détection »** se forment en file
    d'attente, comme les autres tâches. À la fin de chacune, **on sait tout de
    suite si le lot est complet** — code couleur sur le lot dans le chutier.
20. En **mode PDF**, la page s'affiche avec ses surimpressions : marqueurs
    détectés, position du QR — décodé, au vert — et position détectée de chaque
    frame. La peinture est là, la géométrie tient dessous. **Rien n'a encore
    été écrit sur le disque.**
21. Elle active la calibration couleur et choisit le profil qu'elle vient de
    créer. Le rendu change à l'écran ; elle bascule le réglage plusieurs fois
    pour juger.
22. En **mode galerie**, les frames retrouvées se rangent par timecode. Aucune
    n'est en rouge : rien ne manque.
23. Elle passe en **mode lecteur** — le troisième mode de l'atelier Scan. Le
    lot se relit **à sa cadence cible**, sur les images légères que la détection
    a produites en même temps que la géométrie — les mêmes que celles de la
    galerie, jamais une seconde source qui pourrait diverger. Le lot étant
    complet, elle a **l'aperçu du rendu final avant qu'une seule frame du lot
    n'ait été écrite**. Elle regarde. C'est bon.
24. Alors seulement elle lance l'**extraction** : les TIFF s'écrivent, une
    tâche par planche, suivie dans le **panneau de progression**. Les réglages
    du bas se limitent au dpi et au profil de calibration. *(Corrigé le
    2026-08-23 : « panneau latéral » dans la version du 17.)*
25. Atelier **Exports**. Le lot reconstruit est là, dans le chutier partagé
    avec Scan. Elle le visionne : **la cadence cible est sélectionnée par
    défaut**, elle peut en changer si elle le souhaite.
26. Le rush original est sur le disque : le lecteur lui propose le **son du
    rush** et le **balayage**. Elle tire le wipe.
27. **Climax :** on glisse, et l'image se transforme sous le curseur — à gauche
    l'image tournée, à droite la même image passée par la gouache et par le
    scanner. Même cadrage, même timecode, même mouvement. Elle met en pause,
    rejoue **image par image**, coupe et remet le wipe **d'un clic**. Le geste
    de la main est entré dans le plan, et elle peut l'inspecter frame à frame.
28. Réglages d'export : résolution, cadence, profil de sortie. Taille estimée,
    nom de fichier prévisionnel, destination prévisionnelle s'affichent. Elle
    enregistre ses réglages comme **preset** — il y aura d'autres plans.
29. Elle lance l'export. La prévisualisation se bloque pendant l'encodage.
    Carte de progression, passage au vert, deux boutons : ouvrir le dossier,
    ouvrir le fichier.

**Échec à mi-parcours.** Si le lot existe déjà au moment du clic « extraire les
lots », l'erreur se lève **là**, pas dans la fenêtre de confirmation : une
invite explicite demande s'il faut écraser.

**Ce que le parcours a gagné à la relecture.** La chaîne compte désormais
**deux points de jugement avant écriture** : l'aperçu vivant de la planche
avant de générer le PDF, et le mode lecteur avant d'extraire les TIFF. L'outil
ne fabrique rien qu'on n'ait d'abord regardé.

**Surfaces exercées.** Gestion de projet · Extraction (chutier, ajout par
dialogue ou glisser-déposer, previz vidéo + galerie, transport, réglages,
confirmation avec espace disque) · Pdf (sélection de lot, dispositions
multiples, aperçu vivant, calibration) · Scan (détection déclenchée depuis le
chutier, previz PDF + galerie + **lecteur**, profil de calibration, extraction)
· Exports (previz, wipe inspectable, presets) · **Panneau de progression**
(file des tâches) — surface distincte du **panneau latéral** de réglages, que P1
exerce aussi à chaque atelier. *(Corrigé le 2026-08-23 : la version du 17 les
fondait en un « panneau latéral de progression », qui n'existe pas.)*

---

## P2 — Reprendre sans les rushes

**Situation.** Inès est chez elle, sur sa station. Le disque des rushes est
resté chez Camille. Mais **on lui a transmis le projet** : elle le charge et
retrouve la structure — les rushes déclarés, les lots, les planches — sans les
médias eux-mêmes. Puis les scans arrivent.

C'est la promesse centrale du produit : travailler sans le dossier d'origine.

> **Ce qui a changé à la relecture.** J'avais écrit ce parcours en supposant
> un projet vide reconstruit de zéro depuis les scans. **Ce n'est pas le cas
> nominal.** Le cas nominal, c'est le projet transmis. La reconstruction depuis
> les seuls scans reste possible et reste le filet — mais elle n'est plus
> l'histoire principale.

### Déroulé

1. Inès lance l'application et **ouvre le projet qu'on lui a transmis**. Il se
   charge : les rushes déclarés, les lots extraits, les planches générées.
2. Dans les chutiers, les rushes apparaissent **en rouge** : ils sont déclarés,
   mais absents de cette machine. Rien n'est perdu, rien n'est masqué — le code
   couleur suffit à le dire, sans badge ni mention particulière.
3. Elle va à l'atelier **Scan** et dépose les scans reçus. Elle coche ce qui
   part et lance la **détection** depuis le chutier.
4. Les QR sont lus. Les lots qu'elle voyait déjà se peuplent de leurs pages ;
   la géométrie est bonne. Les cartes « détection » passent au vert, le lot est
   annoncé complet.
5. Elle regarde en **mode galerie**, puis en **mode lecteur** : le lot se relit
   à sa cadence cible. C'est un aperçu, pas le rendu final — mais c'est assez
   pour juger.
6. Elle lance l'**extraction**. Les TIFF s'écrivent.
7. Elle passe à **Exports**. Le lot reconstruit est là. Elle le visionne à la
   cadence cible.
8. Le lecteur ne lui propose **ni le son, ni le balayage** : le rush original
   n'est pas sur cette machine. **Si Camille le lui envoie par ailleurs**, elle
   peut le **relinker** — et le rouge du chutier devient noir, le son et le
   wipe reviennent.
9. Elle règle résolution, cadence, profil de sortie, et lance l'encodage.
10. **L'outil ne lui demande rien.** La cadence source, le QR la porte
    désormais ; les timecodes de chaque frame y étaient déjà. Elle n'a personne
    à appeler.
11. **Climax :** le master s'écrit, à la cadence source, timecodes réinjectés.
    Un film reconstruit à partir de feuilles de papier numérisées, sur une
    machine qui n'a jamais vu le rush — **et sans qu'aucun coup de téléphone
    n'ait été nécessaire.**

> **Dépendance.** L'étape 10 décrit la cible, pas le produit d'aujourd'hui.
> Elle repose sur l'arbitrage du 2026-08-17 : la cadence source entre dans le
> payload, qui passe en **version 2.1**. Tant que cette story n'est pas livrée,
> l'encodage exige une saisie manuelle de la cadence source — c'est exactement
> le coup de téléphone qu'Egan veut supprimer.
>
> **Le lecteur bi-format n'est pas une garantie de compatibilité.** Précision
> d'Egan : c'est un **confort de développement**, pour continuer à utiliser les
> anciens scans comme fixtures de test. **En production, 2.0 est abandonné au
> profit de 2.1 seul.** La rupture pour les tirages déjà imprimés est donc
> **assumée**, comme elle l'avait été au passage 1.0 → 2.0 — le bi-format ne la
> repousse pas, il évite seulement de perdre le banc d'essai.

**Variante — reconstruire sans le projet.** Si elle n'a reçu que les scans,
elle crée un projet vide et le dépôt des scans suffit : chaque QR dit à quelle
planche et à quel lot sa page appartient, et l'outil **remonte** de là jusqu'au
rush pour rebâtir la branche. *(Corrigé le 2026-08-23, correction A1 : le
parcours écrivait « les QR reconstruisent l'arborescence à l'envers, chaque scan
portant les lots qu'il contient ». **L'arborescence n'est pas inversée** —
l'ordre affiché reste rush > lot > planche > scan, ici comme ailleurs. Ce qui se
fait à l'envers est le **sens de la reconstruction**, pas la forme de l'arbre :
on part d'une feuille pour retrouver sa branche, et l'arbre obtenu se lit
comme les autres. Un rush qu'aucun fichier ne matérialise y figure **délié**,
à sa place de racine.)* Le déroulé est le même à partir de l'étape 3.

**Ce que le projet ne portera toujours pas.** Même avec la cadence source au
QR, un projet né du scan seul ne porte ni la résolution source, ni la politique
d'arrondi, ni l'empreinte de sélection. **Ce n'est pas un manque à combler,
c'est une propriété du document** — et Egan le dit lui-même : la résolution
« n'est pas tant le sujet ». L'interface ne doit ni afficher de champs vides
accusateurs, ni proposer de compléter ce qui est structurellement absent.

**Surfaces exercées.** Gestion de projet (ouverture d'un projet transmis) ·
Chutiers (rushes déclarés absents, en rouge ; relink) · Scan (dépôt, détection
depuis le chutier, galerie, lecteur, extraction) · Exports (previz sans son ni
wipe, puis avec après relink).

---

## P3 — Un scan qui ne passe pas

**Situation.** Suite de P1. Camille a récupéré ses planches numérisées et lance
la détection. Sur les **sept pages** (`EPIC7-ARB-48`), une résiste : elle a
plié la page 4 pour travailler un raccord, et le pli passe en travers du QR.

C'est le parcours de réparation. Il n'est pas exceptionnel — c'est la
contrepartie assumée d'un outil qui laisse l'artiste maltraiter le support.

### Déroulé

1. La détection tourne. Le lot ressort **incomplet** : le code couleur le dit
   dès la fin de la tâche, avant toute écriture.
2. Camille ouvre le **mode galerie**. La grille se range par timecode et **six
   images sont en rouge** — elles manquent. Elles correspondent à une page.
3. Elle clique sur une image rouge. L'outil la renvoie à la **vue PDF, sur la
   page concernée** — pas au début du document, sur la page fautive.
4. La surimpression dit tout : les quatre marqueurs sont détectés, la page est
   bien lue géométriquement. Mais la **position du QR est marquée comme non
   décodée**. Sans QR décodé, l'outil ne peut pas savoir quelles frames sont
   censées être là : les positions des images ne sont pas proposées.
5. Elle clique sur le QR. Un formulaire s'ouvre, demandant ce que le code
   aurait dit : nombre de frames par page, numéro de page, identifiant du lot,
   timecode de la première et de la dernière image.
6. **L'interface ne la laisse pas chercher.** Toutes ces informations sont
   imprimées en clair sur la planche, et l'outil **sait où** : à mesure qu'elle
   passe d'un champ à l'autre, la zone correspondante du scan est **pointée à
   l'écran**. Elle lit, elle recopie. Un **zoom** est proposé si la peinture
   gêne la lecture.
7. Le QR complété, l'outil détecte les zones d'image et les propose. **C'est
   Camille qui juge**, pas l'outil : elle regarde, et voit que la sixième est
   de travers — le pli a déplacé le coin. L'outil n'a rien signalé, il n'a
   aucun moyen de savoir qu'il a mal placé une zone.
8. Elle clique dans cette zone. Quatre poignées apparaissent aux coins de la
   zone extraite. Elle attrape le coin fautif et le tire — le **mode loupe**
   s'active tout seul, elle règle au pixel.
9. **Rien à relancer.** La position, c'est elle qui vient de la poser : il n'y
   a pas de détection à refaire. L'outil **actualise la complétude du lot**,
   et c'est tout.
10. Retour en galerie : le rouge a disparu, le lot est annoncé complet.
11. **Climax :** elle passe en **mode lecteur** et relit le lot entier à sa
    cadence. Les cinquante frames défilent, dans l'ordre, et **la peinture
    d'une page pliée passe comme les autres**. C'est là qu'elle sait que la
    réparation a tenu — pas sur une pastille verte, sur le mouvement.
12. Elle lance l'extraction, puis part vers Exports.

### Deuxième défaut, d'une autre nature

13. En parcourant la galerie, Camille trouve une image dont les couleurs
    partent — trop froide par rapport à ses voisines. Ce n'est pas une frame
    manquante : elle est là, elle est mal calibrée.
14. Elle clique dessus, plein écran, zoom. Le petit bouton **éditer** la renvoie
    vers la page PDF correspondante.
15. Elle bascule le profil de calibration : le rendu de la page change à
    l'écran. Elle en essaie un autre. Le bon rendu revient.
16. Elle relance la détection de **cette page**, avec ce profil.

**Ce qui doit rester distinct dans l'interface.** Une image absente et une
image de remplacement ne sont pas la même chose. Quand une page est là mais que
sa géométrie a échoué, le produit ne laisse pas un trou : il pose une **mire de
remplacement**. Le lot n'est alors pas complet, même si aucune page ne manque.
Deux natures de manque, deux comptages, et l'interface ne doit pas les fondre
en un seul indicateur. Le rouge de la galerie dit « il n'y a rien ici » ; la
mire dit « il y a quelque chose ici, mais ce n'est pas ton image ».

**L'édition manuelle n'est pas une roue de secours.** L'outil ne détecte jamais
qu'il s'est trompé — il propose une géométrie, et c'est l'œil de Camille qui
tranche. Corollaire : **l'ajustement des quatre coins doit être accessible en
permanence**, sur n'importe quelle zone, y compris quand la détection s'est
déclarée satisfaite. *L'utilisatrice peut délibérément passer par-dessus
l'outil* — ce n'est pas un contournement, c'est un droit de reprise en main, et
sur un support peint à la gouache il servira souvent.

**Ce que l'Epic 7 crée ici, plutôt qu'il n'expose.** La complétion manuelle
d'un QR illisible, le pointage des informations sur le scan et l'ajustement des
quatre coins n'ont **aucun équivalent en CLI**. Ce sont des surfaces GUI
natives, à porter comme telles dans les stories.

**Reporté.** La **lecture automatique** des informations imprimées — champs
préremplis par reconnaissance de caractères sur les zones connues, à confirmer
par Camille — part en `deferred-work.md`. Motif : c'est une brique à fiabiliser
sur du papier peint, pas un détail d'interface ; le pointage suffit à rendre la
réparation praticable.

**Surfaces exercées.** Scan mode PDF (surimpression, formulaire QR avec
pointage et zoom, édition des quatre coins, loupe, relance de détection sur une
page) · Scan mode galerie (rouge, plein écran, renvoi vers la page) · Scan mode
lecteur (vérification par la relecture) · Bascule de profil de calibration.

---

## P4 — S'arrêter à la planche, et revenir

**Situation.** Inès a préparé un lot et généré la planche. À partir de là, plus
rien ne dépend de l'ordinateur : c'est Camille qui prend, avec ses mains, pour
trois semaines. Puis les planches partent chez le prestataire.

Ce parcours ne produit rien de neuf. Il teste autre chose : **est-ce que l'outil
sait attendre, et sait-il dire où on en est quand on revient ?**

### Déroulé

1. Inès finit la génération. Une carte verte, un PDF, dans un dossier au nom du
   lot.
2. Elle clique le bouton **dossier** de la carte : le dossier s'ouvre dans le
   système. Elle envoie le PDF à l'imprimeur.
3. **Elle ferme l'application.** C'est ici que le parcours devient intéressant.
4. Trois semaines plus tard, Camille rapporte les planches peintes. Elles
   partent chez le prestataire, qui les numérise.
5. Inès rouvre l'application. L'écran de gestion de projet s'affiche, **le
   dernier projet ouvert en tête**. Elle l'ouvre.
6. **Climax :** le chutier lui dit exactement où elle en était **sans qu'elle
   ait à se souvenir**. Sous le rush, le lot ; sous le lot, la planche générée,
   et rien après. La chaîne est visiblement arrêtée à l'étape « planche
   produite ». Elle n'a pas besoin de se demander si elle avait lancé le scan.
7. Elle passe à l'atelier Scan et dépose les scans. La chaîne repart.

### Le prestataire renvoie tout en vrac

8. Ce que le prestataire renvoie n'est pas rangé : plusieurs centaines de
   pages, à plat, mêlant plusieurs lots et parfois plusieurs projets. Il n'a
   pas trié — ce n'est pas son métier, et Camille ne veut pas le lui demander.
9. Inès désigne le dossier entier. Les centaines de pages atterrissent dans la
   **zone tampon** — c'est là que la zone tampon prend tout son sens : elle
   absorbe un vrac que personne ne peut trier à la main.
10. Elle lance la détection sur tout. L'outil lit les QR et **range chaque page
    sous le lot auquel elle appartient**. Ce qu'il n'a pas su rattacher **reste
    dans le tampon**, visible, au lieu de disparaître : c'est là qu'elle ira
    voir ce qui a résisté. Le vrac est devenu une arborescence, et le reliquat
    est nommé.

> **Dépendance.** Les étapes 9 et 10 décrivent la cible. Le produit
> d'aujourd'hui ingère **un document à la fois**, sans tri automatique par QR —
> l'information est dans les QR, la fonction n'existe pas. Arbitrage du
> 2026-08-17 : **c'est une story d'Epic 5 en amont**, pas une boucle dans la
> GUI. Le tri par QR devient une fonction du cœur, la GUI ne fait que
> l'exposer, et la CLI en bénéficie aussi.

**Surfaces exercées.** Pdf (cartes finies, bouton dossier) · Gestion de projet
(dernier projet en tête, reprise) · Chutier comme **état d'avancement lisible**,
un rôle qu'aucun autre parcours ne sollicite aussi directement · Scan (ingest
d'un dossier en vrac, rattachement par QR, panier des non-rattachés).

---

## P5 — Essayer, refaire, composer

**Situation.** Camille ne sait pas encore comment elle veut traiter ce plan.
Elle veut essayer, voir, refaire. Le papier coûte du temps mais ne coûte
presque rien à réimprimer — et rien ne l'oblige à écrire des frames tant qu'elle
n'est pas contente.

> **Ce qui a changé à la relecture.** J'avais écrit « deux passes, elle en
> choisit une ». C'est trop simple. Le vrai scénario est un cycle d'essais où
> **rien ne s'écrit tant que l'aperçu ne convainc pas**, et il se termine sur
> un besoin que personne n'avait formulé : **fabriquer un lot hybride** en
> mêlant les frames réussies de deux passes. Egan : *« tout est à inventer à
> ce niveau. »*

### Déroulé

1. Camille extrait son plan à **deux cadences** en une passe — 12,5 et 25 —
   sur les mêmes bornes. Deux lots apparaissent sous le même rush, distingués
   par leur cadence. *(Livré : c'est ce que le modèle de données a été refait
   pour permettre.)*
2. Sur l'atelier Pdf elle coche les deux lots et demande deux dispositions
   différentes : **8 frames par page** pour l'un, **2** pour l'autre. Les
   planches se génèrent — une par lot et par disposition. *(Livré.)*
   *(Corrigé le 2026-08-23, `EPIC7-ARB-48` : le parcours demandait 6 et 12 ;
   `12` n'existe dans aucune orientation et `6` n'existe qu'en paysage. `8` et
   `2` sont atteignables dans les deux, et l'écart entre les deux dispositions —
   qui est le point de l'étape — est plus grand qu'avant.)*
3. Elle imprime, elle peint. Les deux traitements ne se ressemblent pas —
   c'est le but.
4. Elle scanne, elle lance la **détection**, elle **visionne l'aperçu** en mode
   lecteur. **Elle n'aime pas ce qu'elle a fait sur le premier lot.** Elle
   n'extrait pas. Rien n'a été écrit.
5. Elle **réimprime la même planche** — deuxième tirage — la retravaille
   autrement, et la rescanne. Le fichier tombe dans la **zone tampon** : à ce
   stade l'outil ne sait rien du tout. La **détection** lit le QR et le rattache
   **au même lot** — le QR porte l'identifiant du lot. Mais elle **ne peut pas
   savoir que c'est une seconde passe** : le QR est identique d'un tirage à
   l'autre, c'est démontré en amont. C'est donc à Camille de dire quelle passe
   c'est, au moment où le fichier sort du tampon (étape 7). Elle pourrait aussi bien
   réimprimer avec une **disposition plus grande**, 2 frames par page au lieu
   de 8, pour travailler plus finement. *(Corrigé le 2026-08-23,
   `EPIC7-ARB-48` : le lot de l'étape 2 est désormais à 8 par page.)*
6. **Ici le produit bloque.** Une seconde passe sur le même lot est
   **refusée**, avec un message qui dit que la planche est périmée — et aucune
   option ne lève ce refus. *(Non livré.)*
7. **Ce que le parcours demande.** Au dépôt d'un scan portant un lot déjà
   présent, l'interface **ne refuse pas** : elle propose de **garder une
   nouvelle version**, et Camille est invitée à le faire. Elle peut aussi
   choisir d'**écraser** les frames existantes — mais l'outil **ne le force
   jamais** et **avertit que c'est destructeur**.
8. Elle compare. Pas de côte à côte : elle visionne **l'un après l'autre**, et
   un outil **comparer** la fait basculer d'une version à l'autre **au même
   timecode**, sans perdre son point de lecture. Un wipe entre les deux
   versions ferait le même travail — les deux restent ouverts.
9. Sur les **sept pages** du lot (`EPIC7-ARB-48`), elle n'en a refait que
   trois. Le deuxième scan
   n'apporte donc pas un lot entier : il apporte **des candidats** pour les
   frames de ces trois pages. Partout ailleurs, il n'y a qu'un candidat et
   rien à décider.
10. Elle tranche **en bloc**, d'un geste : *les frames du second scan
    l'emportent partout où elles font doublon.* Les six autres pages restent
    telles quelles. C'est le cas courant, et c'est une seule décision.
11. Mais sur deux frames, elle hésite. Elle clique dessus **dans la galerie** :
    les candidats s'affichent côte à côte, celui du premier scan et celui du
    second. Elle garde le premier sur l'une, le second sur l'autre. Le reste de
    son choix en bloc ne bouge pas.
12. Elle repasse en **mode lecteur**. Le lot composé se relit à sa cadence, avec
    exactement les frames qu'elle vient de désigner — elle voit le montage de
    ses deux passes **en mouvement**, pas en vignettes.
13. **Climax :** ce n'est plus « choisir une version », c'est **monter les
    deux**. Le lot est unique, complet, composite. La granularité est **à la
    frame** — le choix en bloc n'était qu'un raccourci vers le même geste — et
    l'outil ne l'a laissée composer que parce que le lot **reste complet** :
    aucune frame n'a disparu en chemin, et aucun choix ne pouvait en faire
    disparaître une.
14. Elle exporte. Le master porte le lot composé, et la composition est
    inscrite dans le projet : elle survit au disque qui change de main. Les
    candidats non retenus **restent là** — trancher n'a rien supprimé.

### Ce que ce parcours demande au produit

Trois choses, dans l'ordre de ce qu'elles coûtent.

**1. Autoriser la seconde passe.** Aujourd'hui refusée. La story existe,
spécifiée et prête à développer. Le comportement voulu est celui de l'étape 7 :
nouvelle version proposée, écrasement possible mais jamais forcé, avertissement
explicite.

**2. Dater les passes.** Le manifest **interdit** aujourd'hui toute date dans
la section de scan — pour une raison assumée : une horodate rendrait deux
passes identiques distinguables et casserait la reproductibilité octet à octet.
**Cet arbitrage est défait** (2026-08-17) : la date est voulue. La story qui la
porte existe déjà, prête à développer et jamais développée — il s'agit de la
développer, pas d'en écrire une nouvelle. **Tant qu'elle ne l'est pas,
l'interface ne peut pas trier deux passes par ancienneté, et tout affichage du
type « dernière version » serait faux.**

**3. Composer un lot hybride.** C'est le point neuf. Rien n'existe : aucune
notion de variante, aucune sélection entre deux passes, aucune fusion — les
stories amont disaient explicitement qu'**aucune fusion n'avait été demandée**.
Elle l'est maintenant, et sa conception est arrêtée (2026-08-17).

Le modèle tient en un mot : **candidat**. Plusieurs scans d'un même lot
produisent, pour une même frame, plusieurs candidats. Composer, c'est choisir
lequel est retenu — jamais supprimer.

* **L'invariant, qui est la garde centrale de la fonction :** le lot doit
  **rester ou devenir complet**. Une composition ne doit jamais faire perdre
  une frame, et l'interface ne doit pas laisser construire un choix qui en
  ferait disparaître une.
* **La granularité est à la frame**, avec la possibilité de choisir en bloc.
  L'ordre compte : le modèle est *frame par frame*, et le choix par scan — « les
  pages que j'ai refaites l'emportent partout où elles font doublon » — est une
  **commodité posée par-dessus**, qui applique d'un geste ce que l'on pourrait
  faire une frame à la fois. Ce n'est pas deux mécanismes, c'en est un seul avec
  un raccourci. Un choix en bloc reste donc défaisable frame par frame, et
  l'inverse n'a pas à être vrai.
* **Où ça se passe.** On clique sur une frame **dans la galerie** pour voir ses
  candidats et les comparer ; on vérifie le résultat **en mode lecteur**, en
  mouvement, avant d'exporter.
* **Trancher ne supprime rien.** Les candidats non retenus restent disponibles ;
  seule la sélection change. Un choix se défait.

* **Comment il se nomme.** Une **icône** — ou la mention **composite** — puis
  **le nom du lot**, qui reste **commun aux deux scans**, puis le **numéro de
  passe** et une **date**. Les deux : le numéro distingue à l'œil deux
  compositions du même jour, la date permet de trier.
  Ce choix dit quelque chose de fort : **le lot ne change pas d'identité en
  étant composé.** Une composition est une *variante datée d'un lot*, pas un
  nouveau lot. C'est ce qui permet au chutier de garder son arborescence — rush
  > lot > scans — sans qu'une branche parallèle apparaisse à chaque essai.

La désignation, elle, **vit au manifest** — c'est un contrat, donc une story
d'Epic 5 avant l'Epic 7.

> **Les deux stories se tiennent.** Le nommage repose sur la date, donc sur la
> story qui ouvre une date au manifest. Sans elle, un lot composé n'a pas de
> nom — et deux compositions successives du même lot seraient
> indistinguables.

**Surfaces exercées.** Extraction (cadences multiples) · Pdf (sélection
multi-lots, dispositions multiples, réimpression d'un second tirage) · Scan
(dialogue de version au dépôt, previz native, mode lecteur, comparaison au même
timecode) · Chutier (deux lots sous un rush : livré ; deux passes sous un lot,
et un lot composé : à créer) · Exports (le lot composé part à l'encodage).

---

## Ce qui reste ouvert

Les blocages de la version 1 sont tranchés ; ce tableau est celui de la version
2, après relecture.

### Tranché le 2026-08-17

| # | sujet | décision |
|---|---|---|
| A | Ingest en masse et en vrac | **Story d'Epic 5 en amont.** Le tri par QR devient une fonction du cœur ; la GUI l'expose, la CLI en bénéficie. |
| B | Désignation de la version | **Elle vit au manifest.** Elle survit au changement de machine — donc un contrat, donc Epic 5 avant Epic 7. |
| C | Cadence source | **Portée par le QR**, payload en **2.1**. Le lecteur bi-format est un **confort de développement** (garder les anciens scans comme fixtures) : en production, 2.0 est abandonné au profit de 2.1 seul, et la rupture pour les tirages antérieurs est assumée. |
| D | Complétion d'un QR illisible | **Pointage** des informations sur le scan. La lecture automatique part en `deferred-work.md`. |
| E | État « projet reconstruit » | **Pas de badge.** On affiche en rouge ce qui est délinké ; le code couleur suffit. |
| F | Reconstruction depuis les seuls payloads QR | **Hors périmètre GUI** (sauf objection). Le cas réel est couvert par le projet transmis et par le dépôt des scans. |
| G | Date de scan au manifest | **Voulue.** L'arbitrage d'origine (idempotence octet à octet) est explicitement défait ; la story existe déjà, il s'agit de la développer. |
| H | Composition d'un lot hybride | **Conçue** : des *candidats* par frame, l'invariant de complétude, deux grains de décision (par scan / par frame), comparaison depuis la galerie, vérification en mode lecteur, et rien n'est supprimé. |
| I | Tutoriel dynamique | **Hors v1** — reporté dans `deferred-work.md`. L'exigence de facilité d'utilisation reste, la surface d'apprentissage attend une interface arrêtée. |
| J | Nommage du lot composé | Icône (ou mention **composite**) + **le nom du lot, commun aux deux scans** + une **date**. Le lot ne change pas d'identité : une composition est une variante datée. |

**Les sept arbitrages sont tranchés. Plus rien ne bloque la Finalize de l'UX.**

Restent des **dépendances de développement**, toutes signalées sur place dans
les parcours : quatre stories d'Epic 5 passent devant l'Epic 7 — tri par QR à
l'ingest, désignation au manifest, payload 2.1 avec lecteur bi-format, et date
de scan. Les spines peuvent décrire l'interface cible sans elles ; les stories
7.x, non.

### Dépendances de développement

Trois parcours décrivent des étapes qui ne sont pas livrées : **P2** étape 10
(cadence source au QR), **P4** étapes 9-10 (ingest en vrac), **P5** étapes 6-11
(versions, dates, composition). Chacune est signalée sur place. **L'Epic 7 ne
peut pas être entièrement spécifié sans que les stories d'Epic 5 correspondantes
existent au moins comme contrat.**

### Ce que les parcours confirment

L'architecture d'information à quatre ateliers tient, et la relecture l'a
renforcée plutôt que déplacée. Deux surfaces décidées le 2026-08-16 ne sont
toujours atteintes par aucun parcours : les **Préférences**, dont le contenu
était déjà renvoyé à plus tard, et rien d'autre — le **relink**, qui n'existait
qu'en creux dans la version 1, est maintenant déroulé dans P2.

Le **chutier commun** ressort comme la pièce la plus sollicitée, et la relecture
l'a encore chargé : il est une source (P1), un état d'avancement lisible après
trois semaines d'absence (P4), le lieu d'où l'on **déclenche la détection**
(P1, P2, P3), un espace d'organisation avec ses propres dossiers, l'endroit où
se lit le **code couleur de complétude** d'un lot et le **rouge** d'un média
absent, et le lieu où se poseraient les versions et le lot composé (P5).
**C'est le point où une erreur de conception coûterait le plus cher.**
