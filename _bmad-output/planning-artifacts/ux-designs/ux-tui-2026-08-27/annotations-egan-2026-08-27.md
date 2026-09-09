# Annotations d'Egan sur les maquettes -- 2026-08-27

**Registre complet de la relecture d'Egan**, ecran par ecran, verbatim.
Il a fait deux passes : une premiere que mes regenerations ont effacee (repechee
dans l'historique local de l'editeur), une seconde apres la pose de la garde.

Les notes vivent aussi **en pied de leur maquette**, ou il les a ecrites, suivies
de la decision qui les traite. Ce fichier-ci est le registre de secours : si les
deux divergent, la maquette fait foi.

Total : **29 maquettes annotees**, 40 lignes.

---

## `E0-3-projet-refus.txt`

> NOTE : non il faut pouvoir créer un projet avec la TUI !

## `E1-1-menu-ateliers.txt`

> NOTE : a ce stade je ne vois pas à quoi sert de relinker un rushe dans la TUI. Je propose d'exclure cela de la TUI si cela te semble correct.

## `E2-1-extraction-rush.txt`

> NOTE : OK cet écran répond à ma question sur l'intérêt du relink je crois. Dans ce cas il faut pouvoir relink directement depuis l'écran ou on voit que le rushe est manquant pas depuis le "projet".
> On peut avoir aussi une option pour relinker en masse en recherchant tous les rushes manquant dans un ensemble de sous-dossiers d'un dossier désigné (est-ce ce que la commande relink permet ?)

## `E2-2-extraction-cadences.txt`

> NOTE (ecrite sur E2-2-extraction-reglages.txt, l'ecran que celui-ci remplace) :
> NOTE : OK mais je ne comprens pas → comment ajouter des cadences ? Comment naviguer dans la liste des cadences à ajouter (1;2;3 etc). Il faut trouver une expérience utilisateur simple avec ajout à la volée et cases à cocher ?
> L'idée serait de faire en 2 temps : on prévisualise (previz) puis on extrait les cadences qu'on choisit dans la liste de celles qu'on a visualisées.
> A developper !

## `E2-3-extraction-confirmation.txt`

> NOTE : peut-on modifier les noms ? Comment ? Il y a des maximums à respecter en nombre de caractères non ?

## `E2-4-extraction-execution.txt`

> NOTE : très chouette.

## `E2-5-extraction-resultat.txt`

> NOTE : parfait aussi surtout le lien avec l'atelier suivant !!!

## `E3-1-scan-depot.txt`

> NOTE : Comment faire pour ne déposer qu'un seul fichier ? Ou un dossier ?
> Très bien sinon.

## `E3-2-scan-detection-en-cours.txt`

> NOTE : OK très bien. Comment faire si le QR n'a pas été décodé ? Formulaire pour completer les infos manquantes ? C'est le travail en cours sur la GUI btw (en dehors de ce worktree !).

## `E3-3-scan-rapport-complet.txt`

> NOTE : ok

## `E3-4-scan-rapport-incomplet.txt`

> NOTE : OK il faut donc ouvrir une page de correction permettant de spécifier ce que le QR n'a pas livré. Pas juste un nouveau scan car cela ne résoudra rien et pas toujours possible de rescanner.

## `E3-5-scan-calibration.txt`

> NOTE : Très bien, c'est la question suivante donc ?

## `E3-6-scan-confirmation.txt`

> NOTE : parfait. Même question sur la modification du nom. quel est le mécanisme ?

## `E3-7-scan-ecriture-en-cours.txt`

> NOTE : parfait.

## `E3-8-scan-resultat.txt`

> NOTE : parfait.

## `E3-9-scan-calibrate.txt`

> NOTE : je n'ai pas compris comment on entre dans ce panneau ? Enlever "parcours à part".
> Pour moi on doit y accéder depuis SCAN.

## `E4-1-exports-lot.txt`

> NOTE : OK

## `E4-2-exports-reglages.txt`

> NOTE : Possible de faire un menu "déroulant" sur les profils ?
> Possible d'enregistrer un profil perso ? Si pas compris dans la CLI on laisse tomber en v1 ...
> Comment renommer le master ?

## `E4-2b-exports-cadence-modifiee.txt`

> NOTE : OK mais ton message est-il déjà livré par la CLI ? Sinon on se contente de dire que ça ne correspond pas et on donne la durée vs la durée initiale.
> Il faut rappeler quelque part aussi que si on génère un lot à 12p5 à partir d'un rushe 25p mais qu'on exporte à 25p comme le rushe natif on "bloque" bien les frames sur 2 images.
> En théorie ce que je décris est le comportement de la CLI non ? tu confirmes ? Et alors comment l'expliciter ici  (préciser la durée source et la durée cible qui sont identiques ?).

## `E5-2-pdf-reglages.txt`

> NOTE : la marge est une marge de travail non ?

## `E5-2b-pdf-cardinal-refiltre.txt`

> NOTE : un peu lourd comme avertissement. Un petit message en bas aurait suffi.

## `E5-3-pdf-confirmation.txt`

> NOTE : OK

## `E5-4-pdf-execution.txt`

> NOTE : OK

## `E5-6-pdf-calibration-page.txt`

> NOTE : le nombre de patches n'est pas un choix je crois. Il dépend de la fonction de calibration non ?

## `T1-1-aide-champ.txt`

> NOTE : Comment distinguer 2 3 4 de 2 fps ? 3 fps ? Il faut taper S/2 S/3 S/4 ? Ce n'est pas clair.
> Une liste à laquelle on peut rajouter un choix à la volée serait pas mal non ?

## `T1-2-manuel-raccourcis.txt`

> NOTE : la précision sur les paliers est de trop non ?

## `T4-1-ecrasement.txt`

> NOTE : parfait.

## `T5-1-refus-nomme.txt`

> NOTE : Si l'outil est capable de lever cette erreur, on ne pourrait pas obtenir le DPI automatiquement ? Ce serait bien.

## `T6-1-interruption.txt`

> NOTE : top.
