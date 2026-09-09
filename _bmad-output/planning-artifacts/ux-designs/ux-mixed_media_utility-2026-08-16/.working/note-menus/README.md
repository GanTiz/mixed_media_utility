# Note fonctionnelle : d'ou vient chaque entree de menu

    https://claude.ai/code/artifact/43d66580-4348-4e3b-a743-5818b408c277

Premiere application d'**EPIC7-ARB-31** : valider la logique fonctionnelle avant
la surface. Aucune maquette dans cette note -- un decoupage, une liste, et pour
chaque entree sa **provenance**.

## Comment elle a ete construite

Le tri des 35 options de ligne de commande a ete fait **sur le code**, pas de
memoire :

```
python3 - <<'PY'
import re, pathlib
s = pathlib.Path('src/mixed_media_utility/cli.py').read_text()
bornes = [(m.start(), m.group(1)) for m in
          re.finditer(r"add_parser\(\s*\n?\s*['\"]([a-z0-9-]+)['\"]", s)]
bornes.append((len(s), None))
for i in range(len(bornes)-1):
    deb, nom = bornes[i]; fin = bornes[i+1][0]
    opts = sorted(set(re.findall(r"['\"](--[a-z0-9-]+)['\"]", s[deb:fin])))
    if nom: print(f"{nom:22s} {' '.join(opts)}")
PY
```

Resultat du tri, qui est le fond de la note : sur 35 options, **12 sont des
chemins**, **4 des consentements** (qui ne doivent jamais devenir des
preferences, sous peine de desarmer les modales), **14 des parametres de
travail** par lot ou par planche, et **3 seulement sont des reglages de
machine** -- `--memory-budget-mb`, `--on-late`, `--no-display`.

Conclusion portee par la note : **les Preferences sont maigres, et c'est
correct**. Un panneau global bien rempli aurait signale que quelque chose est
mal range.

## Rebatir

Le corps est ici (`corps.html`) ; l'assemblage reprend le gabarit du skill
`note-decision-commentable` :

```
sed 's/var TITRE = "Note de decision";/var TITRE = "D_ou vient chaque entree de menu";/' \
    <script de couche-commentaires.html> > script.js
{ echo '<title>...</title>'; <style de page-modele>; <style de couche>;
  cat corps.html; cat script.js; } > note-menus.html
```

Verifie au navigateur en 390x844 avant publication, selon l'exigence 6 du
skill : pas de debordement, aucune erreur console, pose de note, index, saut au
passage, **alarme en stockage bloque**, et aller-retour export / purge /
reimport par collage (3 notes posees, 3 restaurees).

Piege paye : les identifiants des controles de la couche sont `#c-save`,
`#c-btn-export`, `#c-btn-import`, `#c-im-paste`, `#c-im-load`. Un test qui
cherche un bouton par son libelle tombe sur « Tout effacer ».
