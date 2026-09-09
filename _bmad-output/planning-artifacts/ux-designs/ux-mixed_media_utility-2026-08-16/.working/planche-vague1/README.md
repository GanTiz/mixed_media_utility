# Sources de la planche de contact de la vague 1

    https://claude.ai/code/artifact/8be8aac0-ca1f-494c-9d39-59b70e2830d7

Trois ecrans, six etats : chutier v2, reconciliation d'un lot hybride, atelier
Scan v2.

## AVERTISSEMENT : les retours d'Egan vivent DANS la page

Meme mecanique que `../planche-de-contact/` (capacite `artifact`, la page se
republie elle-meme). **Republier depuis ces sources ecrase ses retours** : lire
la page en ligne d'abord, transcrire, puis reconstruire.

**Le 21 aout, la republication les a conserves** : `retours-v1.json` porte les
14 retours releves sur la page, et `build_vague1.py` les reinjecte sous la
vignette qu'ils visaient (`notes_deja`). C'est le geste a refaire a chaque
revision : relire la page en ligne, mettre a jour le JSON, reconstruire. Une
remarque posee a cote de l'image corrigee se verifie ; une remarque effacee se
reperd.

`build_chutier.py` et `picto.py` construisent la maquette du chutier : les
pictogrammes de l'arbre sont generes plutot que copies a la main, pour qu'un
niveau ajoute ne demande pas de redessiner les six autres.

## Rebatir

1. `node shoot-v2.js` avec `S`, `M` (dossier `mockups/`) et `F` (nom de fichier
   sans extension) capture les deux etats d'une maquette ; repeter pour les
   trois. Reduction a 1700 px, quantification 256 couleurs **sans tramage** --
   le tramage brouille les aplats neutres R=G=B.
2. `python3 build_vague1.py` assemble le tout. Il reutilise `planche.css` et
   `planche.js` de `../planche-de-contact/` : la mecanique de retours n'est
   ecrite qu'une fois.
3. Publier avec `capabilities: {"artifact": {}}`.

## Une planche commentable a DEUX canaux

Piege paye le 21 aout. Les retours d'Egan arrivent par deux chemins qui ne se
croisent pas :

1. les **champs de retour** de la page, relus par `WebFetch` puis analyse du
   bloc `#etat` ou des `p.note` ;
2. les **fils d'annotation ancres** de l'artefact, relus par
   `Artifact action:"comments"` avec l'URL.

Lire les premiers ne dit rien des seconds. Le 21 aout, quatre fils sont restes
sans reponse pendant une journee alors qu'Egan avait pose la question dans un
champ (« Retours ponctuels faits. Tu les vois ? ») : la reponse portait sur les
champs seuls, et personne n'a vu le manque.

**Le geste : relire les deux, systematiquement, avant de repondre quoi que ce
soit.** Et repondre dans le fil plutot qu'en conversation quand la remarque y
est nee -- c'est la que l'auteur ira verifier.
