# Sources de la planche de contact de la vague 5


    https://claude.ai/code/artifact/a036322a-8784-46fd-888a-75db94abc2d6
Les trois surfaces demandees par Egan le 23 aout : **Preferences**, **menu
contextuel** et **barre de menus systeme**. Les deux premieres etaient dans
`deferred-work.md` ; elles en sortent.

## AVERTISSEMENT

Meme mecanique que les planches precedentes : la page se republie elle-meme et
**les retours d'Egan vivent dedans**. Avant toute republication, relire la page
en ligne, transcrire les retours dans `retours-v5.json`, et republier.

Une planche publiee a **deux canaux** de retour : les champs de la page ET les
fils d'annotation ancres. **Relire les deux**, systematiquement.

## L'espace de noms CSS, deuxieme fois

La vague 4 avait paye `tete`, deja pris par la tete de lecture. La vague 5 a
paye `app` : la barre de menus nommait `app` son entree applicative, et `.app`
est **a la fois** le cadre applicatif des maquettes **et le selecteur du banc
de capture**. Resultat : une quatrieme capture d'un `<span>` de 40 px.

Avant de nommer une classe :

```
grep -n '\.<nom>' ../planche-vague*/v*-css.css
```

Et ne pas nommer une classe d'apres un mot que `shoot-v5.js` selectionne.

## Ce que le banc ne voit pas, cette fois encore

`verif-v5.js` a rendu vert sur trois defauts que les captures ont montres :

1. les valeurs des Preferences n'etaient pas cadrees -- `.v` n'est stylee que
   sous `.lg2` dans `v3-css.css`, et une ligne `.lg3` la laissait nue. On ne
   retouche pas `v3-css.css` : des maquettes publiees en dependent, on decline ;
2. le menu contextuel du chutier couvrait entierement l'arbre, donc on ne
   voyait plus **sur quoi** on avait clique -- ce que la note 3 de cette meme
   maquette pose en regle ;
3. le caractere Apple `` ne rend qu'en police Apple : ailleurs, un tofu. Le
   menu systeme appartient a macOS, pas a mmu -- un rectangle neutre marque sa
   place sans pretendre le dessiner.

Corollaire : **une maquette doit etre relue contre ses propres notes**. Deux
des trois defauts contredisaient une regle ecrite dans la maquette elle-meme.

## Rebatir

1. `python3 build_prefs.py`, `build_clicdroit.py`, `build_barremenus.py`
   ecrivent les trois maquettes dans `mockups/`. Elles partagent
   `coquille5.py`, qui etend `../planche-vague4/coquille4.py`.
2. `S=<scratchpad> M=<mockups> F=<slug> node shoot-v5.js` capture les etats.
   Selecteur : `.app:not(.mini):not(.deux-os .app), .deux-cotes, .deux-os` --
   une comparaison de deux fenetres est **un** etat.
3. `node verif-v5.js <slugs...>` puis **ouvrir les PNG**.
4. `python3 reduire.py <scratchpad>`.
5. `python3 build_vague5.py` assemble la planche.
6. Publier avec `capabilities: {"artifact": {}}`.
