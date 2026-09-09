# Composants tiers et leurs licences

`mixed_media_utility` (paquet `mmu-tui`) est distribue sous **GPL-3.0-or-later**
(voir `LICENSE`). Ce fichier recense les composants tiers qu'il utilise, leur
licence, et **ce que leur licence exige de nous a la distribution**.

Les licences ci-dessous ont ete **lues dans les metadonnees des paquets
installes** (`importlib.metadata`), pas recopiees de memoire. La date de la
lecture est le 2026-09-07 ; les versions sont celles de l'environnement de
reference.

## Coeur -- toutes permissives, aucune obligation au-dela de la mention

| composant | version lue | licence declaree |
|---|---|---|
| textual | 8.2.8 | MIT |
| rich | 15.0.0 | MIT |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| Pillow | 12.3.0 | MIT-CMU |
| jsonschema | 4.26.0 | MIT |
| opencv-python-headless | >= 4.10 | Apache-2.0 |
| pypdfium2 | 5.13.0 | BSD-3-Clause, Apache-2.0 (+ licences des dependances embarquees) |
| reportlab | 5.0.1 | BSD |
| segno | 1.6.6 | BSD |

Aucune de ces licences n'est copyleft. Aucune ne contraint la licence de
`mixed_media_utility`, et toutes sont compatibles avec la GPLv3.

## Qt / PySide6 -- LGPL-3.0, et **trois** obligations reelles

`PySide6-Essentials` et `shiboken6` declarent
`LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` (plus une licence commerciale
Qt, que nous n'utilisons pas). **Nous retenons la LGPL-3.0**, compatible avec
la GPLv3 sous laquelle ce logiciel est distribue.

C'est une dependance de l'extra **optionnel** `[gui]` : la TUI et la CLI
fonctionnent sans elle, et une installation qui ne l'inclut pas n'est soumise a
aucune des obligations ci-dessous.

La LGPL **n'oblige pas a ouvrir le code d'une application qui l'utilise** --
c'est la GPL de ce projet qui l'ouvre, par choix, pas Qt. Ce que la LGPL exige,
a la **distribution d'un binaire** :

1. **l'utilisateur doit pouvoir remplacer les bibliotheques Qt** par une version
   modifiee. En pratique : **empaqueter en DOSSIER, jamais en executable
   unique**. C'est deja la contrainte retenue dans la note d'interface
   (`DESIGN.md`), ou elle converge avec la parade aux faux positifs antivirus
   sous Windows ;
2. **joindre le texte de la LGPL-3.0 et de la GPL-3.0** et mentionner que Qt est
   utilise sous LGPL ;
3. **publier nos modifications de Qt** s'il y en avait. Il n'y en a aucune :
   PySide6 est consomme tel que publie sur PyPI.

## ffmpeg -- appele, jamais lie

`ffmpeg` est invoque comme **binaire du systeme** (`shutil.which("ffmpeg")`,
`src/mixed_media_utility/ffmpeg_utils.py`). Il n'est ni lie, ni embarque, ni
redistribue. Un appel de sous-process ne cree pas d'oeuvre derivee : **sa
licence ne se propage pas**.

**Ce que cette section NE couvre pas, dit plutot que tu** : le jour ou un
installateur EMBARQUERAIT ffmpeg -- ce que prevoit l'Epic 8 --, la licence du
build embarque compterait. Un build LGPL passe ; un build GPL (avec x264/x265)
imposerait la GPL a l'ensemble, ce qui est deja le cas ici, mais l'obligation de
fournir la source correspondante deviendrait la notre. A trancher au moment de
construire l'installateur, pas avant.

## Outillage de developpement

`pytest` (MIT), `pytest-qt` (MIT), `pytest-xdist` (MIT), `pytest-timeout` (MIT),
`mutmut` (BSD-3-Clause). Ils ne sont pas distribues avec le logiciel et
n'imposent rien a l'utilisateur.
