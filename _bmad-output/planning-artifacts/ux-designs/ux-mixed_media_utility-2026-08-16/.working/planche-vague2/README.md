# Sources de la planche de contact de la vague 2

    https://claude.ai/code/artifact/62692920-64be-42c6-9d19-7017bb3f1ad1

Deux ecrans, cinq etats : atelier Extraction (modes Mouvement et Images) et le
badge de cadence dans ses trois regimes.

## AVERTISSEMENT

Meme mecanique que les planches precedentes : la page se republie elle-meme et
**les retours d'Egan vivent dedans**. Avant toute republication depuis ces
sources, relire la page en ligne, transcrire les retours, et les reinjecter --
`build_vague2.py` sait le faire, il suffit de lui donner un `retours-v2.json`
au format produit par l'analyse de la page (voir `../planche-vague1/`).

Rappel du piege du 21 aout : une planche publiee a **deux canaux** de retour,
les champs de la page et les fils d'annotation ancres. Relire les deux.

## Rebatir

1. `python3 build_extraction.py` et `python3 build_cadence.py` ecrivent les deux
   maquettes dans `mockups/`. Elles partagent `v2-css.css` -- la coquille
   commune est aussi commune dans le code, sinon elle derive.
2. `node shoot-v2.js` avec `S`, `M` et `F` capture les etats ; reduction a
   1700 px, quantification 256 couleurs **sans tramage**.
3. `python3 build_vague2.py` assemble la planche.
4. Publier avec `capabilities: {"artifact": {}}`.
