# Lots complets de terrain — versionnés, mais PAS téléchargés par défaut

Ce dossier porte des **lots réels et complets**, versionnés en Git LFS. Ils
pèsent lourd et **ne descendent pas avec le clone** : sans le geste ci-dessous,
les fichiers d'ici valent **133 octets** — ce sont des pointeurs, et
**aucune erreur ne le signale**.

```
git lfs pull --include="tests/fixtures/lots/**"
```

## Pourquoi ils ne descendent pas tout seuls

Parce que 178 Mo par conteneur neuf, c'est la saturation du quota de bande
passante (10 Go/mois) en trois jours. C'est exactement le défaut fermé le
2026-09-03 — `lfs: true` dans la CI tirait 718 Mo par run — et le rouvrir par
une autre porte n'aurait rien réglé.

**Git ne sait pas apparier une taille**, seulement un chemin : un « seuil au-delà
duquel on passe en LFS » ne peut donc pas s'écrire dans `.gitattributes`. Il
s'écrit dans le choix de **ce qui descend**, c'est-à-dire dans le `fetchexclude`
de `.lfsconfig`. `tests/unit/test_politique_lfs.py` tient les deux bouts : cet
arbre doit être **stocké** en LFS, et il ne doit **pas** descendre seul.

## Ce qu'il y a dedans

### `TEST_FILE_12p5/` — 178 Mo

Le lot complet du projet de démonstration, un aller-retour entier de la chaîne :

| | |
|---|---|
| `frames/` | **13 frames** TIFF 1920×1080 RGB extraites du rush, timecodes `00-00-00-00` à `00-00-00-24` |
| `scan_Document_2026-08-10_095415.pdf` | le **scan réel** de la planche imprimée à partir de ces frames — 36 Mo |
| `project.json`, `scan_ingest.json` | les manifestes réels du lot |

Le rush d'origine est déjà là et **descend, lui** : `tests/TEST_FILE.mp4`
(2,75 Mo). La chaîne complète est donc : rush → 13 frames → planche → scan.

Deux de ces frames étaient aussi, jusqu'au 2026-09-09, dans
`tests/fixtures/rasters/`, qui **descendait automatiquement** — « les témoins
toujours disponibles ». Elles en ont été retirées (arbitrage d'Egan, par
invite) : c'était le même contenu, donc le même objet LFS et zéro octet de
stockage en plus, mais **21,7 Mio tirés à chaque clone** pour deux fichiers
qu'aucun banc ne lisait.

Un raster réel reste à une commande, et c'est celle-ci — `--exclude=""` est
indispensable, `--include` seul ne désarme pas `fetchexclude` :

```bash
git lfs pull --include="tests/fixtures/lots/**" --exclude=""
```

## À quoi ça sert, et pourquoi ça vaut la peine

`CLAUDE.md` porte une règle payée cher : *« une fixture de synthèse peut
fabriquer une panne que le terrain n'a PAS »*. Le 2026-09-02, une conclusion
produit fausse sur le décodage QR a été publiée puis rétractée le jour même,
parce qu'elle avait été tirée d'un banc de synthèse. Le dépôt portait déjà des
rasters réels du côté **lecture** (`qr_300dpi/`, `aruco/`, `scans/`) ; il n'en
avait aucun du côté **production**. Ce lot ferme les deux bouts.

## Le piège, dit plutôt que tu

Un pointeur non matérialisé ne lève **aucune erreur** : il vaut 133 octets, et
le banc échoue plus loin sur un message de décodage incompréhensible. Avant
toute mesure qui lit ce dossier :

```
git lfs ls-files -n | while read f; do
  [ -f "$f" ] && [ $(stat -c%s "$f") -lt 500 ] && echo "POINTEUR $f"
done
```

Et tant que le quota de bande passante du mois est épuisé, **le `git lfs pull`
échoue lui aussi en silence** — il affiche `Fetching reference …` et rien
d'autre. Vérifier la taille après, jamais avant.
