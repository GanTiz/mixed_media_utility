# Sources de la note de revue de l'Epic 7

Note commentable rendue a Egan a l'issue de la revue en trois couches de la
conception GUI (merge `94e1296`).

    https://claude.ai/code/artifact/7e0003c5-11b2-410f-9623-bd22213cfb73

Produite avec le skill `note-decision-commentable`. **Les gabarits ne sont pas
recopies ici** : `build.py` les lit dans
`.claude/skills/note-decision-commentable/templates/` a la construction. Une
correction portee au skill profite donc a cette note comme aux suivantes, au
lieu de mourir dans une copie.

## AVERTISSEMENT : les retours d'Egan vivent DANS la page

La page se republie elle-meme (capacite `artifact`). Ses notes ne sont nulle
part ailleurs tant qu'elles n'ont pas ete recopiees au depot.
**Republier sans reinjecter le bloc durable les efface.**

Le geste, dans cet ordre :

1. relire la page **par les deux canaux** — `WebFetch` ou `Artifact action:"read"`
   pour le bloc durable, `Artifact action:"comments"` pour les fils ancres ;
2. transcrire les retours au depot et **commiter** ;
3. verser le bloc dans `notes-durables.json` ;
4. reconstruire, passer le banc, republier.

`build.py` reinjecte automatiquement `notes-durables.json` dans la page.

*Retours deja transcrits :
`_bmad-output/implementation-artifacts/retours-note-revue-epic7-2026-08-23.md`.*

## Fichiers

| fichier | role |
| --- | --- |
| `corps.html` | le corps de la note, ecrit a la main. Seul fichier de contenu |
| `note-css-extra.css` | deux corrections mesurees au banc et le bloc `.reco` |
| `notes-durables.json` | les retours deja deposes par Egan, reinjectes a la construction |
| `build.py` | assemblage : titre + `viewport` + style du gabarit + complement + style de la couche + corps + bloc durable + script de la couche |
| `note-revue-epic7.html` | la page assemblee, celle qui est publiee |

Il n'y a **pas** de banc ici : il est livre par le skill et il est generique.

## Rebatir

```
python3 build.py
node ../../../../../../.claude/skills/note-decision-commentable/templates/banc-note.js note-revue-epic7.html
```

On ne publie **que** sur un banc vert. Republier le **meme chemin de fichier**
garde la meme URL.

## Ce que le banc a trouve sur cette note

Trois defauts, tous corriges dans le skill plutot qu'ici — c'est le point :

1. **Boucle de republication infinie** (2026-08-23, signalee par Egan). La page
   republiait au demarrage des qu'elle portait des notes ; or publier fait
   **recharger** la page. Mesure : 79 publications et 70 chargements en 6 s,
   l'etat clignotant entre « sauve » et « sur cet appareil seulement », puis
   plantage. Correctif dans `couche-commentaires.html`.
2. **« sauve » affiche sur une note non sauvegardee.** Une fois le bloc durable
   relu, l'etat restait « sauve » meme apres l'ajout d'une note sans capacite.
   L'etat exige desormais **aussi** que ce que la page tient soit ce que le
   serveur porte.
3. **Debordement horizontal de 470 px**, et sa consequence : une page qui defile
   lateralement fait manquer sa cible au pointeur, donc le clic sur un
   paragraphe atterrit sur son voisin. **Le debordement casse le geste central
   de la note.** Corrige ici, dans `note-css-extra.css` : une piste `1fr` de
   grille a `min-width:auto`, qu'une pastille en `white-space:nowrap` pousse
   au-dela de l'ecran.

Regle qui sort du point 3 : **une pastille dit un statut en deux ou trois
mots** ; une phrase entiere prend le bloc `.reco`.
