# Amorcer les quatre projets par jeton API — `EPIC8-ARB-20`

**Tranché par Egan le 2026-09-07, par invite**, après le refus de TestPyPI.
Ce document est une **procédure d'opérateur** : elle s'exécute sur la machine
d'Egan, avec ses comptes. Rien ici n'est faisable depuis un commit.

---

## 1. Ce qui bloquait, mesuré et non supposé

Le message rendu par TestPyPI, verbatim :

> A pending trusted publisher matching this configuration has already been
> registered for a different project name. Please contact PyPI's admins if
> this wasn't intentional.

**L'unicité porte sur le tuple `(propriétaire, dépôt, workflow, environnement)`,
et elle ne s'applique QU'AUX publicateurs EN ATTENTE** — ceux qu'on pose depuis
la page de compte (`/manage/account/publishing/`) pour un projet qui n'existe
pas encore. Une fois le projet créé, les publicateurs se posent depuis la page
**du projet**, où plusieurs projets peuvent partager la même configuration :
la relation est alors plusieurs-à-plusieurs.

C'est donc un problème **d'amorçage**, pas un problème permanent. La discussion
canonique est [pypi/warehouse#16920](https://github.com/pypi/warehouse/issues/16920)
(« suboptimal UX with pending publishers and monorepos ») ; le message vit dans
`warehouse/accounts/views.py:1931`.

Nos six lignes forment **trois paires** qui partagent chacune leur tuple :

| # | projet | dépôt | environnement | collision |
|---|---|---|---|---|
| 1 | `mmu-cli-test` | `mixed_media_utility-dev` | `testpypi` | — |
| 2 | `mmu-tui-test` | `mixed_media_utility-dev` | `testpypi` | **avec 1** |
| 3 | `mmu-cli-test` | `mixed_media_utility` | `testpypi` | — |
| 4 | `mmu-tui-test` | `mixed_media_utility` | `testpypi` | **avec 3** |
| 5 | `mmu-cli` | `mixed_media_utility` | `pypi` | — |
| 6 | `mmu-tui` | `mixed_media_utility` | `pypi` | **avec 5** |

**Trois des six sont structurellement impossibles à poser en attente.** Aucun
réglage ne les débloque : c'est la contrainte de PyPI, pas une erreur de saisie.

Les quatre noms étaient **libres** au 2026-09-07 (les quatre index rendent 404).

---

## 2. Pourquoi l'amorçage par jeton, et ce qu'il coûte

PyPI lui-même liste trois contournements, et met l'amorçage par jeton **en
premier**. Les deux autres ont été écartés par Egan :

* **publier en deux passes** (poser un publicateur, lancer, le tuple se libère,
  poser le second, relancer) exige `skip-existing` sur les téléversements, donc
  une modification du workflow — et `skip-existing` masque aussi les vraies
  collisions ;
* **un environnement GitHub par paquet** dédouble les tuples, mais dédouble
  aussi les portes d'approbation et sort de la forme séquence d'`EPIC8-ARB-13`.

Ce que l'amorçage par jeton coûte, dit plutôt que tu :

* **deux jetons de portée « compte entier » existent le temps de la manœuvre.**
  Un jeton de portée projet ne peut pas être créé avant le projet ; c'est donc
  le seul type qui amorce. Ils se **révoquent** à l'étape 5, et c'est une
  étape de la procédure, pas une bonne intention ;
* **une version est brûlée sur chaque index.** PyPI n'autorise jamais le
  re-téléversement d'un nom de fichier, même après suppression de la release.
  D'où le choix de version ci-dessous.

---

## 3. Le choix de version : `0.1.0.dev0`, et pas `0.1.0`

**Amorcer en `0.1.0` publierait la release** — et la ferait échouer ensuite,
puisque le workflow retenterait les mêmes fichiers et recevrait un `400 File
already exists`. La répétition TestPyPI, qui est ce qui valide la chaîne,
échouerait pour la même raison.

`0.1.0.dev0` est une **version de développement** au sens de la PEP 440 :

* elle trie **avant** `0.1.0`, donc elle ne masque jamais la vraie release ;
* `pip` **refuse les pré-versions par défaut** : entre l'amorçage et la
  publication, un `pip install mmu-cli` ne trouve rien à installer plutôt que
  d'installer une version d'amorçage. C'est ce que `0.0.0` ne donnerait pas —
  `0.0.0` est une version finale, donc installable ;
* elle laisse `0.1.0` **entièrement libre** pour la vraie séquence.

Il n'y a **rien à supprimer ensuite**. On peut la marquer *yanked* par confort
(page du projet → Releases → Yank), mais ce n'est pas nécessaire.

---

## 4. La manœuvre

### 4.1 Construire les six artefacts d'amorçage

```
git clone https://github.com/GanTiz/mixed_media_utility-dev.git amorcage-mmu
cd amorcage-mmu
git checkout claude/epic-8-packaging
python -m pip install --upgrade build twine
python scripts/amorcage_pypi.py
```

> **La première rédaction de cette section était une suite de `sed`, et elle a
> échoué chez Egan dès la première ligne** (2026-09-07). Il travaille sous
> **PowerShell**, où `sed` n'existe pas ; et le `cd` ne s'était pas appliqué, si
> bien que `build` a cherché un `pyproject.toml` dans un dossier quelconque et
> rendu « Source . does not appear to be a Python project » — message qui ne
> nomme ni le dossier attendu ni celui qui a été lu. Rien n'avait été
> téléversé : les quatre `twine upload` ont échoué faute de fichiers, donc
> aucun projet créé et aucun numéro consommé.
>
> `scripts/amorcage_pypi.py` ferme les deux pannes **par construction** : la
> racine se déduit de l'emplacement du script — il peut donc être lancé depuis
> n'importe où — et les substitutions sont faites par Python, qui est de toute
> façon requis. Sur Windows la commande est `python` ; sur macOS et Linux,
> souvent `python3`.

Le script **ne téléverse rien**. Il vérifie qu'il est dans le bon arbre, pose
la version d'amorçage, construit le jeu de production, applique les **cinq**
substitutions du renommage TestPyPI — chacune avec son **témoin**, parce qu'une
substitution qui ne mord pas ne lève rien et laisse construire sous le mauvais
nom —, construit le jeu du bac à sable, passe `twine check`, puis affiche les
six artefacts avec leurs métadonnées et les deux commandes d'envoi.

Ce qu'il doit rendre, mesuré le 2026-09-07 en le lançant **depuis `/tmp`** —
six artefacts, quatre roues et deux archives source, `mmu-tui` partant en roue
seule (`EPIC8-ARB-18`) :

```
dist/cli/       mmu_cli-0.1.0.dev0-py3-none-any.whl        mmu-cli        mmu
                mmu_cli-0.1.0.dev0.tar.gz
dist/tui/       mmu_tui-0.1.0.dev0-py3-none-any.whl        mmu-tui        mmu-tui
                                                           depend de mmu-cli==0.1.0.dev0
dist/cli-test/  mmu_cli_test-0.1.0.dev0-py3-none-any.whl   mmu-cli-test   mmu-test
                mmu_cli_test-0.1.0.dev0.tar.gz
dist/tui-test/  mmu_tui_test-0.1.0.dev0-py3-none-any.whl   mmu-tui-test   mmu-tui-test
                                                           depend de mmu-cli-test==0.1.0.dev0
```

Les six passent `twine check`. **Si l'épinglage de `mmu-tui-test` nommait
`mmu-cli` et non `mmu-cli-test`, s'arrêter** : le paquet de test dépendrait du
paquet de production. Le script le vérifie, mais la lecture reste due.

**Ses deux gardes ont été vues rougir**, pas seulement écrites : lancé hors
d'un clone, il nomme le fichier manquant et le dépôt attendu (code 1) ; sur un
arbre dont la version a déjà bougé, le témoin nomme le motif et ce qu'il
attendait (code 1).

**Ne pas se servir des artefacts du job `build` de la CI** pour cette étape :
ils sont en `0.1.0`, c'est-à-dire exactement la version qu'il faut préserver.
Et **ne pas commiter cet arbre** : il porte la version d'amorçage et le
renommage. Il est jetable.

### 4.2 Créer les deux projets sur TestPyPI

Jeton : <https://test.pypi.org/manage/account/token/>, portée « Entire account ».

```
python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/cli-test/* dist/tui-test/*
```

`twine` demande alors `username` — répondre **`__token__`** — puis `password`,
où l'on colle la clé. Les variables d'environnement `TWINE_USERNAME` /
`TWINE_PASSWORD` marchent aussi, mais elles ne s'écrivent pas pareil sous
PowerShell (`$env:TWINE_USERNAME = "__token__"`) et sous un shell Unix
(`export`) : la saisie interactive évite la question.

### 4.3 Créer les deux projets sur PyPI

Jeton : <https://pypi.org/manage/account/token/>, portée « Entire account ».
**C'est un autre compte et un autre jeton** — TestPyPI et PyPI ne partagent rien.

```
python -m twine upload dist/cli/* dist/tui/*
```

L'ordre n'importe pas ici : PyPI ne résout aucune dépendance au téléversement.
`mmu-tui` peut donc monter avant que `mmu-cli` existe.

### 4.4 Attacher les six publicateurs, depuis la page DU PROJET

C'est ici que la contrainte disparaît. **Ne plus passer par la page de compte** :
les projets existent, et la page de compte ne sert qu'aux projets qui n'existent
pas. Le champ « Workflow name » attend le **nom de fichier** `publish.yml`, pas
le `name:` du workflow.

| page | propriétaire | dépôt | workflow | environnement |
|---|---|---|---|---|
| `test.pypi.org/manage/project/mmu-cli-test/settings/publishing/` | GanTiz | `mixed_media_utility-dev` | `publish.yml` | `testpypi` |
| ″ | GanTiz | `mixed_media_utility` | `publish.yml` | `testpypi` |
| `test.pypi.org/manage/project/mmu-tui-test/settings/publishing/` | GanTiz | `mixed_media_utility-dev` | `publish.yml` | `testpypi` |
| ″ | GanTiz | `mixed_media_utility` | `publish.yml` | `testpypi` |
| `pypi.org/manage/project/mmu-cli/settings/publishing/` | GanTiz | `mixed_media_utility` | `publish.yml` | `pypi` |
| `pypi.org/manage/project/mmu-tui/settings/publishing/` | GanTiz | `mixed_media_utility` | `publish.yml` | `pypi` |

Les **deux** dépôts publient sur TestPyPI, et ce ne sont pas les mêmes lignes :
le dépôt de travail pour la **répétition** (déclenchement manuel), le dépôt
public parce que l'étape TestPyPI fait partie de la séquence de release.

### 4.5 Révoquer les deux jetons

<https://pypi.org/manage/account/> et <https://test.pypi.org/manage/account/>,
section « API tokens » → Remove.

Un jeton de portée compte est le plus fort des identifiants ; une fois les
publicateurs de confiance en place, il ne sert plus à rien et ne porte plus que
du risque. **La chaîne n'en a jamais besoin** : `publish.yml` ne contient ni
`password:` ni `PYPI_API_TOKEN`, et le banc rougit si l'un des deux revenait.

---

## 5. Ce que la procédure NE ferme PAS

* **Les trois environnements GitHub et le ruleset du tag `v*`** restent à poser :
  la liste exacte est en fin de `publish.yml`. Un environnement référencé par un
  workflow et qui n'existe pas est **créé automatiquement, sans protection** —
  son absence ne lève donc aucune erreur, elle supprime la porte.

* **L'étape d'attente donnait un conseil faux ; il est corrigé.** Elle disait de
  relancer le workflow et que « le cœur, lui, est déjà en ligne et ne sera pas
  republié ». Le second membre est vrai, le premier ne l'était pas : sans
  `skip-existing`, une relance **retente** le téléversement du cœur et échoue en
  `400 File already exists`. Egan a tranché **A — corriger le texte** (et non
  poser `skip-existing`, qui masquerait aussi une vraie collision). Le
  diagnostic nomme désormais l'échec de la relance nue et donne deux issues,
  dont l'une est le geste de téléversement manuel décrit en 4.2/4.3 ci-dessus,
  appliqué à `dist/tui` seul.
