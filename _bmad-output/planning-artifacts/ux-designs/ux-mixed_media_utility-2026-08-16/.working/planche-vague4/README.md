# Sources de la planche de contact de la vague 4

    https://claude.ai/code/artifact/f6721a83-f67e-4ab2-bb9b-dd2a1e8ebf19

Trois surfaces qui n'avaient jamais ete maquettees : les **cartes de taches**
(le `Panneau de progression` de la spine), l'**ecran de gestion de projet** et
les **modales**.

## AVERTISSEMENT

Meme mecanique que les planches precedentes : la page se republie elle-meme et
**les retours d'Egan vivent dedans**. Avant toute republication, relire la page
en ligne, transcrire les retours dans `retours-v4.json`, et republier.

Une planche publiee a **deux canaux** de retour : les champs de la page ET les
fils d'annotation ancres. **Relire les deux**, systematiquement. Les champs se
lisent avec `../extraire-retours.py`, les fils avec l'outil Artifact
(`action: "comments"`).

## La coquille partagee est un espace de noms plat

Defaut paye le 22 aout : la ligne du dernier projet portait la classe `tete`,
**deja prise** par la tete de lecture de la chronologie dans `v2-css.css`
(`position:absolute; width:2px; top:-4px; bottom:-4px`). La ligne se reduisait
a un trait de 26 px de large sur 1108 de haut. Elle etait donc **invisible**,
sans debordement du document ni erreur console -- aucun controle du banc ne la
voyait.

Avant de nommer une classe dans `v4-css.css`, faire `grep -n '\.<nom>' ../planche-vague3/v3-css.css ../planche-vague2/v2-css.css`.

## Le banc, et ce qu'il ne voit pas

`verif-v4.js` porte trois controles, chacun issu d'un defaut reellement passe :

1. **debordement horizontal du document** ;
2. **barre d'atelier debordant sur le panneau** -- signale par Egan sur la
   galerie le 22 aout, reapparu tel quel sur les trois ecrans de la vague 3
   parce qu'il avait ete corrige sur la galerie seule ;
3. **element porteur de texte ecrase** a une largeur derisoire -- le cas de
   `tete` ci-dessus. Les elements volontairement etroits (`rappel`, `replier`,
   `sepv`, `piste`, `curseur`) sont listes nommement : une exception nommee
   reste lisible, un seuil relache attrape moins.

Il ne remplace pas l'ouverture des captures. Deux defauts de cette vague ne se
mesurent pas : l'emphase visuelle du bouton « Ecraser », qui donnait l'accent
plein a l'action destructrice ; et un code de refus **invente**
(`SOURCE_FRAME_MISSING`) la ou le coeur en a de vrais -- `LOT_INCOMPLET`, dans
`encode.ENCODE_REFUSAL_CODES`. Verifier un code cite contre le code source,
pas contre sa vraisemblance.

## Rebatir

1. `python3 build_taches.py`, `build_projet.py`, `build_modales.py` ecrivent
   les trois maquettes dans `mockups/`. Elles partagent `coquille4.py`, qui
   etend `../planche-vague3/coquille.py` sans la recopier.
2. `S=<scratchpad> M=<mockups> F=<slug> node shoot-v4.js` capture les etats.
   Le selecteur est `.app:not(.mini), .deux-cotes` : un etat peut etre une
   comparaison de deux mini-ecrans, et c'est **un** etat, pas deux.
3. `node verif-v4.js <slugs...>` puis **ouvrir les PNG**.
4. `python3 reduire.py <scratchpad>` reduit a 1700 px et quantifie en 256
   couleurs **sans tramage**.
5. `python3 build_vague4.py` assemble la planche.
6. Publier avec `capabilities: {"artifact": {}}`.
