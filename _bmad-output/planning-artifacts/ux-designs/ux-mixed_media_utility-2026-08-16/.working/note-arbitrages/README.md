# Sources de la note d'arbitrages de l'Epic 7

Page ou Egan repond aux huit points et commente les dix corrections adoptees.

    https://claude.ai/code/artifact/66bfa099-755f-44d0-afd6-50f3e2e889a6

Produite avec le skill `note-decision-commentable` : le gabarit de page et la
couche de commentaires viennent de `.claude/skills/note-decision-commentable/templates/`,
seuls les fichiers propres a cette note sont ici.

## AVERTISSEMENT : les reponses d'Egan vivent DANS la page

La page se republie elle-meme (capacite `artifact`). Ses reponses et ses notes
ne sont nulle part ailleurs tant qu'elles n'ont pas ete recopiees dans
`arbitrages-epic-7-a-trancher.md`. **Republier depuis ces sources les ecrase** :
lire la page en ligne d'abord, transcrire, puis seulement reconstruire.

## Rebatir

`build` est inline dans l'historique de la session ; l'assemblage est un simple
concatenat, dans cet ordre :

1. `<title>` et la balise `viewport` (sans elle, un telephone met la page en
   page sur 980 px puis la reduit) ;
2. `<style id="css-page">` = le CSS du gabarit **suivi de** `note-css-extra.css`
   (les boutons de reponse) ;
3. `<style id="css-couche">` = le CSS de la couche de commentaires ;
4. `note-body.html`, qui contient tout le corps dans un `<div id="page">` ;
5. `<script type="application/json" id="etat">{}</script>` ;
6. `<script id="js-memoire">` = `note-memoire.js` ;
7. `<script id="js-couche">` = la couche, avec cinq retouches (voir plus bas) ;
8. `<script id="js-choix">` = `note-choix.js`.

Publier avec `capabilities: {"artifact": {}}`.

## Les cinq retouches de la couche de commentaires

Elles ne sont pas dans le skill : la couche du skill reste generique, ces
retouches branchent la memoire durable et les reponses par bouton.

1. `TITRE` = le titre de la note ;
2. `ecrire()` : la republication compte comme sauvegarde valide au meme titre
   que le stockage du navigateur (`stockageOk = localOk || pageOk`) ;
3. `relire()` : ce que porte la page prime, le navigateur sert de repli ;
4. `construire()` : l'export porte une section « Reponses » et le bloc JSON
   embarque `choix` ;
5. `charger()` : la reprise par collage restaure aussi les reponses.

## Deux pieges payes ici

* **La feuille ouverte porte la classe `open`, pas `on`.** La republication
  attend qu'aucune feuille ne soit ouverte, pour ne pas recharger la vue sous
  les doigts du lecteur ; avec le mauvais selecteur, cette garde ne servait a
  rien. Trouve au banc.
* **Le CSS des boutons de reponse manquait a l'assemblage.** Les tests
  passaient tous — le choix se marquait, se sauvegardait, se rechargeait — et
  la page restait inutilisable. Trouve a l'oeil, sur une capture. Un banc vert
  ne remplace pas un regard.
