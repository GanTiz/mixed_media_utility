# Packaging et publication (PyPI / TestPyPI)

> ## ⛔ BLOQUÉ jusqu'au 1er octobre 2026 — les Actions du dépôt privé ne démarrent plus
>
> **Rien de ce qui suit ne peut être exécuté sur
> `GanTiz/mixed_media_utility-dev` tant que ce bandeau est là.** Toute course
> rendue par GitHub y échoue en deux secondes, sans runner et sans log, avec ce
> message :
>
> > *The job was not started because recent account payments have failed or
> > your spending limit needs to be increased.*
>
> **Cause, mesurée le 2026-09-02.** `ci.yml` partait sur
> `push: branches: ["**"]` : cinq jobs à chaque push de chaque branche, dont
> trois suites complètes. Avec plusieurs agents qui commitent en continu, il a
> consommé **3 062 minutes sur 231 runs** — la quasi-totalité des **3 074**
> minutes incluses du compte — en une seule journée, celle du 1er septembre.
> Le déclencheur a été retiré le jour même (`883bd5e`), et une frontière
> (`tests/unit/test_declenchement_des_workflows.py`) empêche sa réintroduction.
>
> **Ce que ça ne dit pas.** Aucun test ne casse. Les centaines de runs rouges
> du dépôt ne mesurent **aucun** défaut de code : ils n'ont jamais démarré
> (0 ms facturée, `runner_id: 0`, logs en 404). Une session qui les lirait
> comme des échecs de tests chasserait un fantôme.
>
> **Les quatre sorties**, de la plus rapide à la plus lourde :
>
> 1. corriger le paiement en échec — rétablit le service immédiatement,
>    indépendamment du quota ;
> 2. relever le *spending limit* : le dépassement se facture ~0,008 $/min
>    sur Linux ;
> 3. **passer au dépôt public** — les minutes ne sont comptées que sur un dépôt
>    **privé**. Sur un dépôt public, les runners standard sont gratuits et sans
>    plafond. **Le 2026-09-06, cette sortie a cessé d'être hypothétique** :
>    `GanTiz/mixed_media_utility` existe, en public et vide, et le dépôt de
>    travail est devenu `-dev`. Le découpage par CONTENU que ce paragraphe
>    réclamait est donc fait — reste à y pousser, et c'est le seul point encore
>    ouvert : l'historique complet porte **4 076 Mo de LFS sur 185 objets, dont
>    148 sous `projects/`**, contre ~86 Mo pour un historique neuf. `.lfsconfig`
>    exclut `projects/` du *fetch*, pas du *push* ;
> 4. un **runner self-hosted**, gratuit et illimité, sur la machine d'Egan.
>
> **UNE SECONDE PANNE, DISTINCTE, ET ELLE NE SE VOIT PAS DANS LES MINUTES**
> (rapportée par Egan le 2026-09-06) : le **quota de STOCKAGE Actions est
> dépassé**, et celui de Git LFS est tendu. Ce n'est pas la même ressource que
> les minutes, et ça ne se répare pas par le même geste. Ce que ça mord
> précisément : `publish.yml` passe ses distributions d'un job à l'autre par
> `actions/upload-artifact` (`dist-test`, puis `dist-prod`) — au-delà du quota
> de stockage, c'est l'**upload** qui échoue, donc la publication, même avec
> des minutes disponibles.
>
> Le remède est gratuit et ne coûte aucun code : les artefacts se **suppriment**
> (Actions → une course → *Artifacts* → corbeille, ou en masse par l'API), et la
> rétention se raccourcit (Settings → Actions → General → *Artifact and log
> retention*, 90 jours par défaut, 1 jour suffit ici). Sur 437 courses, c'est là
> que dort le stockage.
>
> **Sans action, la remise à zéro mensuelle tombe le 1er octobre 2026.** Elle
> vaut pour les MINUTES ; le stockage, lui, ne se remet pas à zéro tout seul —
> il se libère en supprimant.
>
> *Ce bandeau se retire dès que les Actions repartent. S'il est encore là après
> le 1er octobre, c'est qu'un paiement bloque toujours, pas le quota.*


Ce document décrit la chaîne de packaging `mmu-tui` : dépôt privé (tests en
amont) et dépôt public (release), deux index PyPI séparés, et la règle des
**deux commandes distinctes** (`mmu-tui` en prod, `mmu-tui-test` en test) pour
ne jamais écraser une installation de production lors d'un test local.

---

## Principe : deux index, deux commandes

| | Production | Test (bac à sable) |
|---|---|---|
| Index | `pypi.org` | `test.pypi.org` |
| Package | `mmu-tui` | `mmu-tui-test` |
| Commande console | `mmu-tui` | `mmu-tui-test` |
| Déclenchement | tag `v*` sur dépôt **public** | `workflow_dispatch` `target: testpypi` sur dépôt **privé** |
| Visible publiquement | oui | non (sauf `--index-url` explicite) |

**TestPyPI et PyPI sont des index totalement séparés.** Un publish sur
TestPyPI n'apparaît jamais sur le vrai PyPI et n'est installable par personne
sauf si l'on pointe pip explicitement dessus. On peut donc tester sans risque.

**Pourquoi deux noms de commande ?** Si le test publiait aussi `mmu-tui`,
un `pip install` depuis TestPyPI écraserait la commande `mmu-tui` de production
sur la même machine. Le build TestPyPI renomme donc automatiquement le package
**et** la commande console en `mmu-tui-test` (voir `publish.yml`, étape
« Renommer en mmu-tui-test pour TestPyPI »). Les deux coexistents :

```bash
pip install mmu-tui                      # production -> commande mmu-tui
pip install -i https://test.pypi.org/simple/ mmu-tui-test   # test -> commande mmu-tui-test
```

---

## Workflows

| Fichier | Rôle | Déclencheurs |
|---|---|---|
| `.github/workflows/ci.yml` | Tests (3.11/3.12/3.13) + build wheel/sdist + smoke test `mmu-tui --help` + garde d'installation | `workflow_dispatch`, `workflow_call`, tags `v*` |
| `.github/workflows/publish.yml` | Validation, puis TestPyPI, puis **porte humaine**, puis PyPI | tags `v*`, `workflow_dispatch` |
| `.github/workflows/docs.yml` | MkDocs Material -> GitHub Pages | `workflow_dispatch` |

**Aucun ne part sur un push de branche**, depuis le 2026-09-02 et pour le motif
du bandeau ci-dessus. Les lancer à la main :

```bash
gh workflow run ci.yml --ref main
gh workflow run publish.yml -f target=testpypi
```

`ci.yml` et `publish.yml` tournent **identiquement** sur le dépôt privé et le
dépôt public : ils valident le packaging en amont (privé) puis publient
(pubic). Seule l'inscription du trusted publisher diffère.

---

## 1. Environnements GitHub

Créer (Settings → Environments → *New environment*) deux environnements, nommés
**exactement** comme dans le workflow (`testpypi` et `pypi`). Le nom doit
matcher à 3 endroits : le `environment:` du workflow, l'environnement GitHub,
et le champ « Environment name » du trusted publisher PyPI/TestPyPI.

Il en faut **trois**, pas deux — c'est le piège de cette section, corrigé le
2026-09-06 : le dépôt public en veut **deux**, parce qu'une release y publie sur
TestPyPI avant PyPI (`build-prod` porte `needs: publier-testpypi`, cf. §4).

### Dépôt PRIVÉ (`GanTiz/mixed_media_utility-dev`)
- `testpypi` : aucun secret (trusted publishing = OIDC). Protection : vide
  (c'est le sandbox).

### Dépôt PUBLIC (`GanTiz/mixed_media_utility`)
- `testpypi` : aucune protection non plus. Il n'existe que pour porter un nom
  que le trusted publisher reconnaisse — mais sans lui, une release s'arrête à
  sa troisième étape sur un refus OIDC.
- `pypi` :
  - **Required reviewers** : toi-même → chaque vraie release exige ta
    validation manuelle (sécurité « ne publier que si c'est bon »).
  - **Prevent self-review** : laisser **décoché**. Egan est le seul relecteur ;
    le cocher rendrait inapprouvable toute release qu'il déclenche lui-même.
  - **Allow administrators to bypass** : **décoché**, sans quoi la porte ne
    tient pas pour le propriétaire — c'est-à-dire pour la seule personne qui
    l'ouvre.
  - **Deployment branches and tags** : restriction « tags » correspondant à
    `v*` → seuls les tags de version déclenchent le vrai publish. Conséquence
    voulue : un `Run workflow` manuel `target=pypi` lancé depuis une BRANCHE
    est refusé à la porte.

Option `gh` CLI (si `gh auth login`) :
```bash
gh api repos/GanTiz/mixed_media_utility-dev/environments -f name=testpypi  # prive
gh api repos/GanTiz/mixed_media_utility/environments    -f name=testpypi   # public
gh api repos/GanTiz/mixed_media_utility/environments    -f name=pypi       # public
```

---

## 2. Trusted publishers (côté PyPI)

Enregistrer **trois** trusted publishers (PyPI et TestPyPI sont des instances
séparées, avec des comptes séparés). Aucun token : la publication utilise
l'OIDC GitHub.

| Champ | PyPI (vrai) | TestPyPI ① | TestPyPI ② |
|---|---|---|---|
| URL | pypi.org/manage/account/publishing | test.pypi.org/manage/account/publishing | idem |
| PyPI project name | `mmu-tui` | `mmu-tui-test` | `mmu-tui-test` |
| Workflow name | `publish.yml` | `publish.yml` | `publish.yml` |
| Environment name | `pypi` | `testpypi` | `testpypi` |
| Repository owner | `GanTiz` | `GanTiz` | `GanTiz` |
| Repository name | `mixed_media_utility` | `mixed_media_utility-dev` | `mixed_media_utility` |

**Le troisième n'est pas un doublon, et cette section l'omettait** (corrigé le
2026-09-06). Un tag `v*` sur le dépôt **public** joue `publier-testpypi` avant
`publier-pypi` : sans un publisher TestPyPI déclaré pour le dépôt public, la
release meurt à cette étape sur un refus OIDC — alors que la §4 de ce même
document décrit l'enchaînement depuis toujours. Deux moitiés du document se
contredisaient ; c'est celle-ci qui avait tort.

> Le trusted publisher PyPI pointe vers le dépôt **public** uniquement. Le
> dépôt privé n'y est pas autorisé : même un `target: pypi` lancé depuis le
> privé serait rejeté par PyPI (double verrou).

---

## 3. Tester en amont (dépôt privé)

```bash
# GitHub : Actions -> Publish to PyPI -> Run workflow -> target: testpypi
```

Le workflow renomme le package en `mmu-tui-test`, build, et publie sur
test.pypi.org. Vérifier localement :

```bash
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple mmu-tui-test
mmu-tui-test --help
mmu-tui-test --diagnostic-chemin
```

La commande de production `mmu-tui` (si installée) reste intacte.

---

## 4. Release (dépôt public)

```bash
git tag v0.1.0
git push --tags
```

Le tag `v*` déclenche `publish.yml`, qui joue **quatre étapes enchaînées** :

```
valider  ->  build-test  ->  publier-testpypi  ->  [ATTENTE]  ->  publier-pypi
```

`valider` appelle `ci.yml` (`workflow_call`) : rien ne part sur un arbre rouge.
Le candidat est publié sur TestPyPI, **puis la course s'arrête** et attend une
approbation humaine sur l'environnement `pypi`.

**C'est `Settings → Environments → pypi → Required reviewers` qui crée cette
attente**, pas le YAML — celui-ci ne fait que nommer l'environnement. Sans ce
réglage, la publication part toute seule et les deux temps n'existent plus.

Pendant l'attente, valider pour de vrai (c'est le seul moment où le refus est
encore gratuit) :

```bash
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple mmu-tui-test
mmu-tui-test --help
bash scripts/install.sh --testpypi     # sur un conteneur NEUF
```

Puis *Actions → la course → Review deployments → Approve* (ou *Reject*).

**Ce que coûte un refus** : aucune minute pendant l'attente — un job en attente
d'approbation n'alloue aucun runner, et GitHub annule la course au bout de
30 jours. Le vrai PyPI n'a rien reçu. Le seul coût réel est le **numéro de
version brûlé sur TestPyPI** (voir les notes ci-dessous) : reprendre un candidat
rejeté exige une version différente. D'où la convention des pré-releases
(`0.1.0rc1`, `rc2`) pour les candidats.

Installer :

```bash
pip install mmu-tui
mmu-tui --help
```

---

## 5. Notes

- `pyproject.toml` (prod) garde `name = "mmu-tui"` et la commande `mmu-tui`.
  Le renommage en `mmu-tui-test` est fait **uniquement** dans le build
  TestPyPI (`sed` dans `publish.yml`), jamais dans le fichier versionné.
- TestPyPI exige des numéros de version uniques par projet : un `mmu-tui-test`
  0.1.0 ne peut être republié ; utiliser un nouveau numéro pour chaque test.
- `permissions: id-token: write` est requis pour l'OIDC (déjà présent).
- `docs.yml` ne déploie les Pages que depuis `main` (cible = dépôt public).
