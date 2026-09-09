# Retours d'Egan sur les maquettes d'ecrans-cles

**Statut : relu par Egan les 19 et 20 aout 2026 ; ses 18 retours sont transcrits ci-dessous, mot pour mot.** Ce document est le reservoir de retours sur
les quatre maquettes rendues au Finalize du 2026-08-19. Il n'a pas d'autorite
propre : ce qui y est tranche part ensuite dans `.memlog.md` (via
`memlog.py append`) puis, si la decision touche le contrat, dans `DESIGN.md` ou
`EXPERIENCE.md`. Les spines restent le contrat, les maquettes illustrent.

Ecrire sous **Retour** en clair, sans se soucier de la forme. Laisser vide ce qui
va bien : un silence vaut acceptation, c'est la relecture qui compte, pas le
remplissage.

## Ou regarder

| ecran | fichier du depot | page consultable |
|---|---|---|
| planche de contact (les quatre) | - | https://claude.ai/code/artifact/9108984c-0c24-447e-8100-d620858c4f3d |
| chutier | `mockups/key-chutier.html` | https://claude.ai/code/artifact/4a2b4946-4da1-4e69-99d0-c63d94c963ad |
| atelier Scan, mode PDF | `mockups/key-scan-mode-pdf.html` | https://claude.ai/code/artifact/72890f59-9f2f-4d27-a2a2-e0943d671a29 |
| atelier Pdf | `mockups/key-atelier-pdf.html` | https://claude.ai/code/artifact/753ecf67-40d9-440d-854c-f5b050fb3376 |
| mode lecteur | `mockups/key-mode-lecteur.html` | https://claude.ai/code/artifact/79e12912-78c0-42e2-88ba-6ff90e0cba03 |

Les pages consultables sont privees par defaut. Rien ne previent la session d'un
commentaire : le signaler en conversation.

**Le chemin le plus court, y compris sur telephone : la planche de contact
elle-meme.** Sous chaque vignette, un champ de retour ; l'enregistrement inscrit
le texte dans la page, qui se relit depuis une session Claude. C'est de la que
les retours sont recopies dans ce document, et non l'inverse.

Les quatre pages plein format sont des mises en page d'ecran de bureau : elles
ne se lisent bien que sur ordinateur.

**Avant de republier la planche depuis ses sources**
(`.working/planche-de-contact/`), lire la page en ligne et recopier ce qu'elle
porte : une republication ecrase les retours qui n'ont pas ete repris ici.

---

## 1. Le chutier

Deux perimetres, huit roles annotes. `EXPERIENCE.md > Information Architecture`,
`Le chutier - huit roles`, `State Patterns`, `Accessibility Floor`.

**Question posee :** l'inversion de l'arbre du Scan (planches scannees remontant
vers les lots reconstruits) se lit-elle sans explication ?

**Retour :**

> **perimetre 1, Extraction / Pdf — 19/08 23:38**
>
> Ca me semble clair.

> **perimetre 1, Extraction / Pdf — 19/08 23:41**
>
> Ajouter une icone de dossier ? J’aurais quand meme imaginé ensuite une vue en « arbre » et non en deroulables. Avec des lignes et des branches qui tracent clairement les niveaux hierarchiques ici. J’aimerais voir une proposition ainsi. Mais garder cette option ouverte aussi.

> **perimetre 2, Scan / Exports — 19/08 23:42**
>
> C’est ici que j’ai plus de retours :
> Ok pour la pastille rouge creuse sur le delink, mais on peut aussi imaginer un point d’interrogation sur un dossier qui serait peut etre une icone plus claire. Pour un lot incomplet on met un panneau d’information ⚠️

> **perimetre 2, Scan / Exports — 19/08 23:46**
>
> Par ailleurs je ne crois pas qu’il faille inverser l’affichage de l’arborescence. C’est un renversement logique dur a suivre. L’ordre de l’arborescence reste le meme : un scan est « sous » une planche, qui est elle meme sous un lot, qui lui meme est sous un rushe. Ca reste l’ordre « logique ». Quand je dis que l’arborescence remonte c’est que quand on charge un scan dans un projet ou on avait pas le rushe d’origine, on peut deduire du seul scan la planche, le lot et le rushe et donc reconstruire le debut de la branche. Je ne dis pas qu’il faut retourner toute la branche.

> **perimetre 2, Scan / Exports — 19/08 23:51**
>
> Ce qu’il faut avant tout fixer c’est la facon dont cette arborescence interragit avec la navigation de page. Que se passe-t-il visuellement en passant d’une page a l’autre ? Est-ce que l’arborescence se deploie automatiquement ? Si je clique sur un niveau « inferieur » de la branche (par exemple sur une planche alors que je suis sur la page extract (en supposant que je voie les planches sur cette page ce qui n’est pas arrêté) : est-ce que je bascule sur la page pdf ?
> J’aimerais tes conseils et tes propossitions (pour/contre ?) sur ces comportements. Cela doit rester lisible.
>
> Et surtout faut il aller jusqu’aux rushes reconstruits dans cette aborescence ou s’arreter aux frames extraites d’une planche pdf ? C’est un enjeu de lisibilité que je ne sais pas encore trancher.
>
> Une solution alternative : des dossiers par type comme on l’a fait pour le reste ? Mais bon … moins convaincant peut-etre ? Moins a l’image de la logique du projet ?

> **perimetre 2, Scan / Exports — 19/08 23:53**
>
> Remonter la zone tampon en haut : en attente de lecture plutot que zone tampon.

---

## 2. Atelier Scan, mode PDF

Etat A, QR non lu, aucune zone proposee, action bloquee, aucun champ prerempli.
Etat B, QR complete, zones proposees, poignee saisie, loupe dans le passe-partout.
`State Patterns (PAGE_QR_UNREADABLE)`, `Interaction Primitives`, `Key Flows`.

**Question posee :** le blocage de l'etat A est-il vecu comme une protection ou
comme un mur ?

**Retour :**

> **etat A, QR non lu — 19/08 23:55**
>
> Oui mais il manque des couleurs. Et puis on doit voir le qr dans une couleur (ici orange car non lu) et les marqueurs aruco aussi (ici en vert car decodés). Dans le cas ou les marqueurs aruco ne sont pas vus ils sont soit manquants (a ajouter) soit en orange (il en manque par exemple un ?). Une fois qu’on complete ca passe au vert et le reste des zones a detecter se debloque.

> **etat A, QR non lu — 19/08 23:56**
>
> Il manque a voir de la maquette la vue galerie avec des frames detectees, manquantes, l’apercu etc. Et le mode lecteur. Qui devrait ressembler au reste.

> **etat B, QR complete — 19/08 23:57**
>
> meme remarque sur les codes couleur diffenciant les statuts. Manque les aruco.

> **etat B, QR complete — 19/08 23:58**
>
> trop de vide sur cet ecran. Controle de zoom pour le pdf ? Mode pleine largeur ? Autre disposition ?

> **etat B, QR complete — 19/08 23:59**
>
> afficher la taille en pixel des zones d’ilage. Afficher les timecodes detectés en dessous de chaque zone (ca bient du qr)

---

## 3. L'atelier Pdf

Etat A, marge de travail a 0. Etat B, marge a 8 mm. Apercu vivant, sans bouton de
rafraichissement. `Component Patterns`, `Interaction Primitives`,
`DESIGN.md > Layout & Spacing`.

**Question posee :** les reglages sont-ils dans l'ordre ou tu les prends, ou dans
l'ordre ou ils ont ete ranges ?

**Retour :**

> **etat A, marge 0 — 20/08 00:00**
>
> Ca me semble bien. Meme remarque sur le cote vide de l’interface. Controle de zoom, controle de largeur pleine page et hauteur pleine page etc

> **etat B, marge 8 mm — 20/08 00:01**
>
> Ok l’ordre des reglages ne me choque pas. Mais pourquoi mettre l’orientation qui n’est pas un choix ?

---

## 4. Le mode lecteur

Etat A, la machine tient la cadence. Etat B, elle ne la tient pas : bandeau ambre
`PREVIEW_QUALITY_REDUCED` sous la scene, refus en un clic. Applique la consigne du
2026-08-19 sur le materiel moins performant. `State Patterns`,
`Responsive & Platform`, `Voice and Tone`.

**Question posee :** le repli doit-il se souvenir du choix pour les lots suivants,
ou se reposer a chaque fois ?

**Retour :**

> **etat A, cadence tenue — 20/08 00:07**
>
> Ok mais manque un certain nombre de controles : frame par frame, boucle, in/out, marqueurs, volume … j’avais fait la liste complete que tu peux reprendre.
>
> Sur la question de la cadence : pas de bandeau c’est lourd. Juste un badge au dessus du levteur qui affiche la cadence effectivement affichée. Si c’est celle attentdue (avec marge d’erreur comme dans le previz existant en cli) c’est vert. Sinon c’est rouge. On peut alors manuellement degrader la qualité : full, half, quarter ou Auto (resolution). En cas de lecture « rouge » prolongee j’accepte un unique bandeau « la lecture ne se fait pas en temps reel, reduisez la qualité de visionnage ». On peut ferme ce bandeau manuellement. On peut demander a ne plus le voir (de toute la session). Mais c’est l’utilisateur qui degrade la qualité sauf en mode « auto » ou elle s’ajuste seule pour le temps reel

---

## 5. Les surfaces non maquettees

Sept surfaces se construiront sur les seules tables des spines : ecran de gestion
de projet, atelier Extraction, atelier Exports, frame en plein ecran, modales,
preferences, comparateur de candidats.

Pari assume et contestable : **Extraction herite de l'ossature de Pdf, Exports de
celle du lecteur.** Si l'un des deux s'ecarte de son modele, la maquette manque a
cet endroit.

**Retour :**

> **surfaces non maquettees — 20/08 00:08**
>
> moi je voudrais tout voir. La logique n’est
> Pas identique du tout. Il faut valider aussi ces ecrans.

> **surfaces non maquettees — 20/08 00:11**
>
> En plus je ne vois absolument pas en quoi extraction herite de pdf ? Rien a voir.
>
> Il faut aussi qu’on voie les modes galerie et lecteur sur toutes les pages.
>
> Et aussi l’interface en cas de reconciliation d’un lot hybride a partir de olusieurs scans d’une meme page ! Important. Il yab de la comparaison etc.
>
> Il faut aussi voir le wipe, la navigation entre les cadences, etc. Bref toutes le fonctions evoquées …

---

## 6. Les [A TRANCHER] restants

Questions produit ouvertes, conservees volontairement dans les spines.

| # | question | reponse |
|---|---|---|
| 1 | profondeur d'annulation : combien de gestes en arriere ? | |
| 2 | geste de zoom en previsualisation | |
| 3 | taille minimale de fenetre | |
| 4 | panneau de progression : superposition ou retrecissement de la scene ? | |
| 5 | consulter un autre lot pendant un encodage : permis ou bloque ? | bloque, par contrainte de calcul |

Reponses d'Egan, verbatim (20/08 00:14) :

> Annuler quoi ?
> On doit pouvoir zoomer en previz : manuellement, presets de valeur, fit etc
> Panneau de progression en retrecissement de la scene. Mais je rapelle qu’un toggle doit exister pour on off.
>
> Pourrait-on avoir un double toggle ? On off et superposition vs ancrage avec retrecissement de scene ?
>
> Consulter un autre lot pendant encodage : je serais pour mais je pense que c’est un probleme de ressource de calcul. A mon avis on va le bloquer par besoin technique.

---

## 7. Divers

Ce qui ne rentre dans aucune case ci-dessus.

**Retour :**

> **divers — 20/08 00:16**
>
> Tu as reussi a faire une vraie memoire fonctionnelle pour mes commentaires ! Ce n’etait pas le cas avant, donc je pense que tu peux consigner cela dans le skill des notes commentables et le pousser sur main. C’est tres utile.
