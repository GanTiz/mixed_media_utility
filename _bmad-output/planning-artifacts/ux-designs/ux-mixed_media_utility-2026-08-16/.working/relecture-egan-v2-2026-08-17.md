# Seconde relecture d'Egan — parcours version 2 (2026-08-17)

> Six notes, **reçues par le fichier d'export** — le mécanisme a tenu cette
> fois, aucune capture d'écran n'a été nécessaire.
>
> Texte recopié tel quel, avec le passage auquel chaque note était accrochée.

---

## 1 — P2, encart « Dépendance »

> « L'étape 10 décrit la cible, pas le produit d'aujourd'hui. Elle repose sur
> l'arbitrage du 2026-08-17 : la cadence source entre dans le payload, qui
> passe en version 2.1 avec un lecteur bi-format pour que les… »

Le lecteur bi-format n'est qu'un confort de developpement pour pouvoir utiliser
les anciens scans en test. En production on abandonnera 2.0 au profit de 2.1
uniquement. C'est temporaire.

## 2 — P3, étape 7 (détection des zones après complétion du QR)

> « Le QR complété, l'outil détecte les zones. Cinq des six tombent juste ; la
> sixième est de travers — le pli a déplacé le coin. »

C'est elle qui le constate pas l'outil. L'utilisateur peut volontairement
passer par dessus l'outil.

## 3 — P3, étape 9 (relance de la détection sur une page)

> « Elle relance la détection sur cette page. Pas le lot, pas l'extraction : la
> détection de cette page. »

Est-ce necessaire d'ailleurs ? Pas forcement. On peut juste aller en galerie
non ? Il faut juste actualiser la completude du lot.

## 4 — P5, étape 5 (second tirage rescanné)

> « Elle réimprime la même planche — deuxième tirage — la retravaille
> autrement, et la rescanne. Un deuxième fichier arrive sous le même lot. Elle
> pourrait aussi réimprimer avec une disposition plus grande, 2 frames… »

A la lecture de ce paragraphe je realise que quelque chose manque. Quand on met
un pdf l'outil ne sait pas tout de suite ou le ranger avant le detect. Il y a
donc un emplacement tampon pour les pdf qui n'ont pas encore ete decodés.

## 5 — P5, climax

> « Ce n'est plus « choisir une version », c'est monter les deux. Le lot est
> unique, complet, composite — et l'outil ne l'a laissée composer que parce
> qu'il reste complet : aucune frame n'a disparu en chemin, et aucun… »

Et la granularité est a la frame avec possibilite de choisir en lot

## 6 — Ce qui reste, arbitrage C

> « Cadence source → portée par le QR. Payload 2.1 avec lecteur bi-format, pour
> ne pas rejouer la rupture 1.0 → 2.0. »

Avec la nuance pour le dev uniquement
