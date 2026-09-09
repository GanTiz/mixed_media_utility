# Sources de la planche de contact de la vague 3

    https://claude.ai/code/artifact/5ebb3c65-9b30-4833-979f-f02c0c832820

Trois ecrans, neuf etats : l'atelier Exports (lecture, balayage, encodage),
la comparaison (vignette unique, deux candidats, deux passes) et l'atelier
Extraction corrige (selecteur de cadence, galerie sans case a cocher).

## AVERTISSEMENT

Meme mecanique que les planches precedentes : la page se republie elle-meme et
**les retours d'Egan vivent dedans**. Avant toute republication, relire la page
en ligne, transcrire les retours dans `retours-v3.json`, et republier --
`build_vague3.py` les reinjecte tout seul a partir de ce fichier.

Une planche publiee a **deux canaux** de retour : les champs de la page ET les
fils d'annotation ancres. **Relire les deux**, systematiquement. Le champ se lit
avec `../extraire-retours.py`, les fils avec l'outil Artifact (`action:
"comments"`).

## Ce que la vague 3 ajoute au dispositif

`coquille.py` est le seul endroit ou vivent la barre de vue, les onglets, le
rail et le chutier. Motif mesure : la vague 2 a paye deux fois le prix d'une
correction appliquee dans un seul ecran -- le debordement du compteur sur le
panneau, signale par Egan sur la galerie, est reapparu tel quel sur les trois
maquettes de la vague 3 parce qu'il avait ete corrige sur la galerie seule.

Corollaire : ne pas recopier un fragment de barre dans un builder. Si un ecran
a besoin d'une variante, on ajoute un parametre a `barre_vue()`.

## Rebatir

1. `python3 build_exports.py`, `build_comparaison.py`, `build_extraction_v3.py`
   ecrivent les trois maquettes dans `mockups/`. Elles partagent `coquille.py`
   et `v3-css.css`.
2. `S=<scratchpad> M=<mockups> F=<slug> node shoot-v3.js` capture les etats
   (un `.app` = un etat), puis `python3 reduire.py <scratchpad>` reduit a
   1700 px et quantifie en 256 couleurs **sans tramage**.
3. `python3 build_vague3.py` assemble la planche.
4. Publier avec `capabilities: {"artifact": {}}`.

## Regarder les captures, pas seulement le banc

Le banc de `shoot-v3.js` ne detecte que le debordement horizontal du document.
Il a rendu « aucune erreur » sur trois defauts visibles a l'oeil : le compteur
passant sous le panneau, le lisere de designation etire sur toute la hauteur de
la colonne, et le menu de cadence decapite par un `overflow:hidden`. Ouvrir les
PNG reste obligatoire.
