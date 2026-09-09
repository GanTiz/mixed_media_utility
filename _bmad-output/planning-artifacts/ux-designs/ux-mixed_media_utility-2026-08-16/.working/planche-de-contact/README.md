# Sources de la planche de contact

Page publiee et commentable, ou Egan relit les quatre ecrans-cles et depose ses
retours vignette par vignette.

    https://claude.ai/code/artifact/9108984c-0c24-447e-8100-d620858c4f3d

## AVERTISSEMENT : les retours d'Egan vivent DANS la page

La page se republie elle-meme quand Egan enregistre un retour (capacite
`artifact`, appel `artifact.publish`). Ses retours ne sont donc nulle part
ailleurs tant qu'ils n'ont pas ete recopies dans le depot.

**Republier depuis ces sources ecrase tout ce qu'il a ecrit.** Avant toute
republication : lire la page en ligne (WebFetch sur l'URL), recopier les
retours dans `retours-maquettes-2026-08-19.md`, et les reinjecter dans le
gabarit si la page doit les conserver.

## Rebatir

1. Capturer les huit etats (deux par ecran) depuis `mockups/` :
   `node shoot2.js` puis reduction a 1700 px de large, quantification 256
   couleurs sans tramage (le tramage brouille les aplats neutres R=G=B).
   Les PNG intermediaires ne sont pas versionnes : ils se regenerent.
2. `python3 build_planche.py` assemble `planche.css`, `planche-body.html` et
   `planche.js` avec les images en data-URI. Sortie : un fichier d'environ
   1,7 Mo.
3. Publier avec `capabilities: {"artifact": {}}` -- sans cette declaration, les
   boutons d'enregistrement retombent sur le stockage local du telephone et
   les retours ne remontent plus jusqu'ici.

## Deux pieges deja payes

* **Sans balise `viewport`**, un telephone met la page en page sur un viewport
  virtuel de 980 px puis reduit l'ensemble : illisible, et aucune regle
  `@media` mobile ne s'applique. La balise est dans `build_planche.py`, pas
  dans le gabarit du corps.
* **Le conteneur `.sheet`** porte la largeur, les marges et le rythme vertical.
  Le perdre en decoupant le gabarit donne un texte a fond perdu, colle aux
  bords.
