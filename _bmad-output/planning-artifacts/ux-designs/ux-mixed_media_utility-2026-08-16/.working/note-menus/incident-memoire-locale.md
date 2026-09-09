# La memoire locale n'a rien conserve chez Egan

> « Je note : la memoire locale n'a pas marche ici ! Heureusement j'ai copie le
> tout. » — Egan, 2026-08-23

## Ce que le banc avait teste, et ce qu'il a rate

Avant publication, le banc a verifie le cas du **stockage qui leve** :
`localStorage` et `sessionStorage` remplaces par des accesseurs qui jettent.
Resultat : alarme affichee, etat « non conserve », rappel d'export des la
premiere note. Ce cas-la marche.

**Ce n'est pas celui qui s'est produit.** Une page d'artefact tourne dans une
iframe **inter-site** a l'interieur de `claude.ai`. Dans un navigateur integre
d'application mobile, et sous le cloisonnement de stockage tiers de Safari et
de Chrome, `localStorage` reste **accessible** et `setItem` **reussit** — mais
l'ecriture va dans une partition ephemere, jetee a la fermeture.

Consequence, et c'est le defaut :

| etape | ce qui se passe | ce que la page affiche |
|---|---|---|
| sonde au demarrage | ecrit, relit, reussit | rien |
| enregistrement d'une note | ecrit, relit, reussit | **« sauve 11:06 »** |
| session suivante | la partition a disparu | tout est perdu |

La page a donc **promis une sauvegarde qui n'a pas eu lieu**. C'est exactement
l'exigence 4 du skill — « ne jamais sauvegarder en silence non plus » — mise en
defaut par un cas que sa sonde ne sait pas voir : la sonde detecte une
**erreur**, pas une **non-persistance**.

## Le correctif

Une sonde synchrone ne peut pas prouver la persistance : par construction, elle
teste dans la session en cours. Il faut une **balise inter-session**.

1. au demarrage, lire une balise `__persist__` ecrite lors d'une visite
   anterieure ;
2. si des notes existent en memoire mais qu'aucune balise anterieure n'a
   survecu, le stockage est **ephemere** : basculer en regime degrade ;
3. ecrire une balise horodatee pour la visite suivante ;
4. tant qu'aucune balise n'a **jamais** survecu a un rechargement, ne pas
   afficher « sauve HH:MM ». Afficher **« non verifie »**, et declencher le
   rappel d'export des la premiere note.

Le principe : **une sauvegarde non prouvee ne s'annonce pas comme faite.**
« Non verifie » est honnete au premier chargement et devient « sauve » au
second, quand la preuve existe.

## Ce qui a sauve la relecture

Le bloc exporte. C'est sa raison d'etre, et c'est la deuxieme fois qu'il sert a
ca (la premiere : 2026-08-17, une passe entiere perdue). Egan l'a copie de
lui-meme ; il ne devrait pas avoir a y penser, d'ou le point 4.
