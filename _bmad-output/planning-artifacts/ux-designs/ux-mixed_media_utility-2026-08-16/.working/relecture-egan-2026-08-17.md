# Relecture d'Egan — parcours Epic 7 (2026-08-17)

> Transcription des notes posées sur la page de lecture mobile. La page ne les
> a **pas** conservées (voir « Incident » en fin de document) : elles sont
> arrivées par captures d'écran et sont recopiées ici pour ne pas les reperdre.
>
> **Réception terminée** — 38 notes sur 38, plus les deux arbitrages.
>
> Le texte des notes est recopié tel quel, y compris les coquilles de saisie.
> Les citations sont le passage auquel la note était accrochée.

---

## 1 — Protagonistes

> « Inès — Monteuse. Elle travaille sur sa propre station. Elle dispose
> généralement des rushes natifs, parce… »

A elles s'ajoutent : les autres membres de la chaine de post-production. Dont
moi. Et le public (videastes) qui pourra utiliser l'appli a terme. La facilité
d'utilisation est un facteur clé. Sinon on pourrait envisager un tuto
dynamique ?

## 2 — P1, situation

> « Situation. Camille a tourné un plan de 4 secondes en 25 fps qu'elle veut
> faire passer par le papier. Le disq… »

Ou bien elle extrait 4 secondes du montage en cours

## 3 — P1, étape 1 (création du projet)

> « Inès lance l'application. L'écran de gestion de projet s'ouvre — il s'ouvre
> toujours au lancement. Le film de… »

Les medias originels (rushes) restent a leur place dans l'arborescence du
disque. On n'y touche pas on se contente de collecter leur chemin d'acces. On
pourra au besoin les relinker plus tard si leur emplacement change. Seuls les
medias *produits* par mmu sont stockés dans le dossier de travail. Frames
extraites, scans, frames reconstruites par scans, exports, calibrations.

*(fin de note complétée par Egan)*

## 4 — P1, étape 2 (ajout du rush)

> « L'atelier Extraction s'ouvre, chutier vide à gauche. Inès ajoute le rush.
> Le rush n'est pas copié dans le… »

Elle peut : ajouter via boite de dialogue systeme. Cliquer-deposer, y compris
plusieurs rushes.
Elle peut : creer des dossiers pour organiser les rushes (sequence x). Ces
dossiers ne concernent que son chutier. Pas le dossier de travail.

## 5 — P1, étape 5 (bornes)

> « Elles posent les bornes. Camille place l'entrée et la sortie dans le bus de
> transport, image par image, pui… »

Il faisait deja 100 frames dans ton exemple.

## 6 — P1, étape 7 (fenêtre de confirmation)

> « Inès clique Extract. Une fenêtre de confirmation liste les cadences
> retenues avec leurs cases à cocher — o… »

On l'informe de l'espace disque requis.

## 7 — P1, étape 11 (réglages de planche)

> « Réglages de planche : 6 frames par page, format A4, marge de travail
> confortable — Camille veut de la pla… »

Par defaut la marge est à 0. C'est eventuellement camille qui en demande

## 8 — P1, étape 12 (aperçu vivant)

> « L'aperçu est vivant : chaque changement de réglage redessine la planche
> sous leurs yeux. Aucun bouton … »

Elles peuvent, je le rappelle, en choisir plusieurs.

## 9 — P1, étape 13 (planche de calibration)

> « Camille clique le bouton planche de calibration en haut à droite. Un
> mini-dialogue lui demande ce dont i… »

Camille est une femme (elle)
Normalement on ne lui demande pas grand chose, juste le nom du scanner cible.
On lui demandera plus de choses au scan

## 10 — P1, étape 14 (génération)

> « Génération. Une carte par planche, progression en pages générées sur le
> total. Neuf planches d'images… »

Mmmh non : une seule planche est generee. Par exemple la A4-6f pour le lot
12p5. Elle fait certes 9 pages (dont la derniere avec 2 images) mais c'est une
seule planche, composée de pages. Une seul pdf attendu. + la calibration (2 au
total)

## 11 — P1, étape 16 (calibration scanner)

> « Atelier Scan. Elle dépose d'abord le scan de la planche de calibration et
> clique calibration scanner :… »

On lui demande : le nom du scanner, le dpi, le format (pdf/tiff/jpeg/png ?) et
on l'invite a mettre un commentaire pour identifier les reglages choisis au
scan.

## 12 — P1, étape 17 (dépôt des scans, mode PDF)

> « Elle dépose les scans des planches. En mode PDF, la page s'affiche avec ses
> surimpressions : marqueurs… »

J'imagine qu'elle depose les pdfs puis qu'il y a un premier bouton qui apparait
pour lancer la detection. Ce n'est pas automatique car elle peut continuer a
charger des fichiers pendant ce temps avant de lancer la detection. Ce bouton
est donc au niveau du chutier. On peut selectionner ce qui est lancé ou pas
dans la phase de detection. On a des cartes avec « detection » qui se forment
en file d'attente. A la fin d'une detection on sait tout de suite si le lot est
complet ou pas (code couleur).

Oui c'est un ajout important …

## 13 — P1, étape 19 (réglages du bas, lancement du scan)

> « Réglages du bas : dpi, profil de calibration. Rien d'autre. Elle lance le
> scan — une tâche par planche,… »

Alors quand on dit qu'elle lance le scan c'est en fait l'extraction en tiff qui
est lancée. A partir de la detection seule on a genere la position des frames,
un apercu des frames retrouvees. Et j'ajoute ici : en plus du mode galerie on a
aussi un mode « lecteur » pour relire le rushe extrait (qualité temporaire :
png ?) a sa cadence cible. Si le lot est complet on a directement un apercu
(low res ?) du rendu avant de lancer l'extraction. Si c'est raté : a quoi bon
ecrire les frames ?

## 14 — P1, étape 20 (mode galerie)

> « En mode galerie, les frames extraites se rangent par timecode. Aucune n'est
> en rouge : rien ne manque. »

+ ajout du mode lecteur previz.

## 15 — P1, étape 21 (atelier Exports)

> « Atelier Exports. Le lot reconstruit est là, dans le chutier partagé avec
> Scan. Camille le visionne à la… »

Si le rushe est toujours présent sur le disque : avec le son. Avec un wipe pour
comparer à l'original. Elle peut changer de frequence si elle le souhaite mais
par defaut c'est la cadence cible qui est selectionnee.

---

## 16 — P1, étape 22 (son du rush et balayage)

> « Le rush original est sur le disque : le lecteur lui propose le son du rush
> et le balayage. Elle tire le wip… »

Cf ma remarque precedente

## 17 — P1, climax

> « Climax — Sous le curseur, à gauche l'image tournée, à droite la même image
> passée par la gouache et par le… »

On glisse, on transforme par magie. On pause on rejoue, image par image. On
peut activer ou desactiver le wipe en un clic. On adore !

## 18 — P2, étape 1 (création du projet local)

> « Inès lance l'application, écran de gestion de projet. Elle crée un projet
> local et désigne un dossier sur sa… »

Ou bien on lui a transmis le projet original. Elle le charge et retrouve un
certain nombres d'infos mais pas les rushes.

## 19 — P2, étape 3 (lecture des QR, arborescence inversée)

> « Elle dépose les scans. L'outil lit les QR codes et reconstruit
> l'arborescence à l'envers : sous chaque… »

Oui, mais elle a deja vu les rushes existants si on lui a partagé le projet.

## 20 — P2, étape 7 (passage à Exports)

> « Elle passe à Exports. Le lot reconstruit est là. Elle le visionne. »

Elle a pu le visionner avant sur la page de scan on le rappelle. Mais c'etait
un preview. Et on rappelle qu'elle a d'abord lancé la detection. Puis elle a
lancé l'extraction. (Detect / extract en deux temps ici).

## 21 — P2, étape 8 (rush absent, ni son ni balayage)

> « Le lecteur ne lui propose ni le son, ni le balayage : le rush original
> n'est pas sur cette machine. Dans les… »

Elle peut le relinker si on lui a envoyé par ailleurs.

## 22 — P2, étape 10 (cadence source demandée)

> « L'outil s'arrête et lui demande une information qu'aucun fichier ne porte.
> Un lot né du scan seul ne… »

Alors le QR doit la porter … c'est un manque. Peu couteux.

## 23 — P2, étape 11 (appel à Camille)

> « Inès appelle Camille, obtient la cadence source, la saisit. »

A eviter

## 24 — P2, étape 13 (master, timecodes)

> « Elle ouvre le fichier depuis la carte. Le master est livré à la cadence
> source. Aucun timecode n'y est… »

Si ! Les timecodes lus sur les planches ! Ils y sont pour le coup. Et on
connaitra la cadence source. Faux !

## 25 — P2, encart « Ce que ce projet ne portera jamais »

> « Ce que ce projet ne portera jamais — Un manifest né du scan ne peut pas
> porter la cadence source, la… »

Si il le peut. A quel coût ? La resolution n'est pas tant le sujet mais la
candence source oui. Tout est possible. D'autant que camille a pu envoyer le
projet a Ines !

## 26 — P2, encart « Question ouverte · à trancher »

> « Question ouverte · à trancher — Comment nommer cet état dans l'interface ?
> Le manifest distingue déjà… »

Je ne comprends absolument pas a quoi cela correspond ?!

## 27 — P3, étape 4 (surimpression, QR non décodé)

> « La surimpression dit tout : les quatre marqueurs sont détectés, la page est
> bien géométriquement lue. Mai… »

On peut lui proposer de zoomer sur l'image si ca aide ou pas ? Mais sinon on
lui fait remplir les infos.

## 28 — P3, étape 5 (formulaire de complétion du QR)

> « Elle clique sur le QR. Un formulaire s'ouvre, demandant ce que le code
> aurait dit : nombre de… »

On sait meme ou c'est sur la page on peut les pointer ? On pourrait meme les
lire …

## 29 — P3, étape 8 (rescanner cette page)

> « Elle clique rescanner cette page. Pas le lot : cette page. Une tâche part,
> comme les autres. »

Dans notre nouvelle distinction elle relance plutot la detection. Pas le scan a
ec exteaction. Elle voit sur la galerie que c'est complet
Elle verifie a la relecture que le resultat est conforme avant de passer a
l'export.

## 30 — P5, situation

> « Situation. Camille ne sait pas encore comment elle veut traiter ce plan.
> Elle veut essayer, comparer,… »

Ou plutot elle imprime, essaie, detecte et visionne l'apercu. Elle n'aime pas
le travail fait. Elle n'extrait pas. Elle reimprime la meme planche (deuxieme
tirage) et rescane (deuxieme fichier sous le meme lot, meme planche mais
version differente). Ou bien meme une planche avec une disposition plus grande
(2f au lieu de 4).

*(fin de note complétée par Egan)* Elle peut donc generer plusieurs planches
differentes. Faire plusieurs essais sur la meme planche reimprimee — il y aura
alors deux scans de la meme planche originale.

De plus, dans ton exemple elle ne refait QUE 3 frames. Il faudrait donc
inventer un scenario ou elle integre ces 3 frames aux autres frames deja
validees pour fabriquer un nouveau lot hybride complet et composite. Tout est
donc a inventer a ce niveau.

## 31 — P5, étape 5 (visionnage des deux séries)

> « Elle numérise les deux séries. Deux lots reconstruits apparaissent sous
> leurs scans. Elle les visionne l'un… »

Dans scan avec la previz native.

## 32 — P5, étape 6 (première décision, comparaison)

> « Première décision : lequel des deux traitements tient à l'écran ? Elle veut
> les voir côte à côte, ou l'un après… »

L'un apres l'autre. On peut ajouter un outil compare pour passer de l'un a
l'autre au meme tc. Ou bien un wipe ?

## 33 — P5, étape 8 (seconde passe refusée)

> « Ici le produit bloque. Une seconde passe sur le même lot est refusée, avec
> un message qui dit que la… »

Gros probleme en effet. On garde juste une nouvelle version ! (On invite
camille a le faire. On peut aussi proposer d'evraser les frames actuelles en
previsant bien que c'est destructeur.

## 34 — P5, étape 9 (dialogue de passe)

> « Ce que le parcours demande, une fois la story livrée : au moment de déposer
> un scan portant un lot déjà… »

Elle propose d'ecraser sans le forcer jamais et en avertissant !

## 35 — P5, climax (deux passes sous un lot)

> « Climax — Dans le chutier, sous le lot 12,5 fps, deux passes. Camille en
> désigne une comme celle qui part… »

Ton cas est pljs complexe elle n'a refait que 3 frames. Elle pourrait donc
vouloir meler la page unique de la passe 2 (ou les 3 frames seulement) a la
passe 1 - les « merger » en quelque sorte pour produire un lot hybride unique
oret a exporter. Tout est a construire ici.

## 36 — P5, encart « 2 · L'ordre entre deux passes »

> « 2 · L'ordre entre deux passes — Le manifest interdit aujourd'hui toute date
> dans la section de scan — pou… »

A corriger !

## 37 — Écart 07 (nommer l'état « projet reconstruit »)

> « 07 Nommer l'état « projet reconstruit ». Le modèle distingue l'origine ;
> l'architecture d'information doit-… »

Non on affiche ce qui est delinké dans le cas ou ca l'est (on connait le nom du
rushe donc on peut tout a fait peupler les chutiers des autres page et
l'afficher en rouge !)
Pas de badge spécial juste le code couleur.

## 38 — Écart 08 (reconstruction depuis les seuls payloads QR)

> « 08 Reconstruction depuis les seuls payloads QR, sans planche. Livrée en
> CLI, aucune décision UX.… »

Je e comprends pas ça ?!

---

## Les deux arbitrages, tranchés

| blocage | décision d'Egan |
|---|---|
| **1 — Ingest en masse et en vrac** | **(b) Une story d'Epic 5 le fait en amont.** Le tri par QR devient une fonction du cœur ; la GUI ne fait que l'exposer, et la CLI en bénéficie aussi. |
| **2 — Notion de version désignée** | **La désignation vit au manifest.** Elle survit au changement de machine et se transmet avec le projet — donc une story d'Epic 5 avant l'Epic 7. |

---

## Incident — les notes n'ont pas été conservées

La page de lecture mobile enregistrait les notes dans le stockage local du
navigateur. **Ce stockage n'a rien retenu** dans la vue où Egan a travaillé :
toute une passe de relecture aurait été perdue s'il n'avait pas fait des
captures d'écran au fur et à mesure.

Deux conséquences à traiter, dans cet ordre :

1. **La page ne doit plus supposer que le stockage local fonctionne.** Il faut
   soit vérifier l'écriture et le dire franchement quand elle échoue, soit ne
   pas en dépendre du tout — et dans tous les cas rendre la sauvegarde
   explicite et visible plutôt qu'implicite.
2. **L'export était le seul filet, et il ne rendait rien non plus** (corrigé le
   2026-08-17, commit `d84fb62` : le texte est désormais toujours affiché et
   récupérable à la main). Un filet qui dépend d'un mécanisme silencieux n'est
   pas un filet.

C'est exactement le défaut que les parcours reprochent à l'application : une
action dont le résultat part hors de l'outil doit toujours laisser une prise à
la main, et un échec doit se voir.
