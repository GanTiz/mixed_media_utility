# -*- coding: utf-8 -*-
"""La chaine de publication a DEUX distributions, mesuree plutot que relue.

**Ce que ces frontieres ferment.** `mmu-tui` epingle `mmu-cli==X`. Trois
defauts en decoulent, et aucun des trois ne se voit a la relecture d'un
workflow :

* **l'ordre**. Publier l'interface avant le coeur produit, pendant tout
  l'intervalle, une release que `pip install mmu-tui` REFUSE d'installer. Le
  workflow ne rougit pas : les deux `upload` reussissent. C'est l'utilisateur
  qui paie ;
* **le desaccord de versions**. Quatre valeurs doivent s'accorder -- la version
  de `mmu-cli`, celle de `mmu-tui`, l'epinglage `mmu-cli==X` porte par les
  metadonnees de `mmu-tui`, et le tag -- et rien ne les compare autrement. Trois
  litteraux qui doivent coincider sans arbitre, c'est la definition d'une
  derive ;
* **le renommage TestPyPI**. Il se faisait par `sed` sur UN nom. Avec deux
  distributions il porte sur cinq lignes, dont l'EPINGLAGE INTERNE : sans lui,
  `mmu-tui-test` dependrait de `mmu-cli` -- le paquet de PRODUCTION --, et une
  installation de bac a sable tirerait de la production. Et un `sed` qui ne
  remplace rien **sort a zero** : la roue se construit sous son nom de
  production, l'upload part, et rien ne l'a dit.

**Pourquoi ce banc EXECUTE le workflow au lieu de le lire.** Un test qui se
contente de chercher `mmu-cli-test` dans le texte de `publish.yml` reste vert
devant un `sed` dont le motif ne mord plus -- il verrait la chaine dans le motif
lui-meme. Les trois scripts qui portent la garantie (renommage, garde de
version, attente) sont donc EXTRAITS du fichier reel et REELLEMENT EXECUTES,
contre des `pyproject.toml` fabriques, des roues fabriquees et un `curl`
d'emprunt. Ce qui est mesure est le comportement, pas la presence d'une chaine.

**Pourquoi aucun `import yaml`.** Un `pytest.importorskip("yaml")` rendrait ces
frontieres SAUTEES en CI, c'est-a-dire inexistantes la ou elles comptent. La
lecture se fait donc par indentation, comme dans
`test_declenchement_des_workflows.py`, et pour le meme motif.

**CE PARAGRAPHE A PREDIT UN DEFAUT REEL, ET IL A FALLU UN AN DE JOURNEE POUR LE
TROUVER AILLEURS.** Il disait aussi « PyYAML n'est pas une dependance du
depot ». C'etait vrai jusqu'au 2026-09-08 -- et pendant tout ce temps
`tests/unit/test_politique_lfs.py` lisait le YAML derriere un
`pytest.importorskip("yaml")`, exactement le geste que cette place declarait
fautif. Mesure du 2026-09-08 : la fermeture transitive de `.[test]` faisait
VINGT-SIX paquets, PyYAML absent -- donc les QUATRE frontieres de la section 1
de ce banc-la, dont celle qui interdit `lfs: true` et que le depot a payee
10 Go de bande passante, SAUTAIENT en CI. Vertes ici, muettes la-bas.

La story 8.10 a ferme le defaut des deux cotes : `pyyaml>=6.0` est declare
(extra `[test]` et `requirements.txt`), et le chargeur de ce banc-la ROUGIT
desormais au lieu de sauter si la roue venait a disparaitre.

Ce qui reste vrai ici, et qui est le vrai motif : **ne rien importer du tout
est ce qui ne peut jamais sauter**, quelle que soit la fermeture des
dependances du jour. Une prediction ecrite dans un fichier ne mesure rien tant
qu'aucune frontiere ne la tient -- c'est la section « Les politiques de ce
fichier se MESURENT » de CLAUDE.md, appliquee a un docstring.

MUTATIONS JOUEES, ET LEUR VERDICT (2026-09-07, chacune injectee dans le fichier
reel puis restauree depuis une copie prise avant -- jamais par `git checkout`).
Le compte se lit dans la table elle-meme -- il etait annonce a QUARANTE-DEUX
devant quarante-huit lignes, et un cardinal recopie se perime a chaque ajout.

UN SURVIVANT ASSUME, `N40`, et il est ecrit comme tel plutot que tu (revue
8.9, couche 3, rejoue au triage : 103 verts sous mutation). La branche
`sdist_non_creux(source_tui, ...)` est INERTE tant que la dispense de sdist
tient : `source_tui` vaut `None` sur les deux distributions en roue seule,
donc l'appel n'a pas lieu. Aucun banc ne peut le tuer -- lui donner un sdist
le fait refuser plus tot, au cardinal.

Ce qui rend cet etat SUR, et c'est ce qui a change au triage : le controle 7
de la garde refuse desormais toute version au-dela de
`BORNE_DE_LA_DISPENSE`. La branche ne peut donc pas rester inerte au-dela de
la 0.1.0 -- la release est bloquee jusqu'a ce que la dispense soit retiree,
et `mmu-tui` retrouve alors un sdist qui rend `N40` a nouveau mortel. Sans ce
controle, la story annoncait `N40` ROUGE et laissait un controle mort
s'installer sans terme.

| la sequence | |
|---|---|
| N01 `release` ne depend plus du passage par TestPyPI | ROUGE |
| N02 `release` n'exige plus un tag | ROUGE |
| N03 `release` n'exige plus le depot de distribution | ROUGE |
| N04 le declenchement manuel peut viser `pypi` | ROUGE |
| N05 le jeu de PRODUCTION se construit apres le renommage | ROUGE |
| N17 la reconnaissance du depot compare de facon relachee (`case` a joker) | ROUGE |
| N18 un slug reste a `TBD` ne bloque plus | ROUGE |
| N50 le job `valider` est retire (l'etat exact rendu par la fusion) | ROUGE |
| N51 la porte reste mais `build` ne l'attend plus | ROUGE |
| N52 la porte appelle un `ci.yml` qui n'existe pas | ROUGE |
| N53 `ci.yml` perd `workflow_call` : l'appel echoue au demarrage | ROUGE |

| l'ordre et les index | |
|---|---|
| N06 l'attente de production lit l'index de TestPyPI | ROUGE |
| N07 l'attente du bac a sable est retiree | ROUGE |
| N08 `mmu-tui`/PyPI televerse le dossier du coeur | ROUGE |
| N09 `mmu-cli-test` perd son `repository-url` (part sur le VRAI PyPI) | ROUGE |
| N34 attente de production : borne remplacee par `while true` | ROUGE (par delai du sous-process) |
| N35 attente du bac a sable : `grep` sur `${PAQUET}` au lieu du couple | ROUGE |

| la porte humaine, et ce qu'elle NOMME | |
|---|---|
| N10 `environment: pypi` retire du job `release` | ROUGE |
| N11 `id-token: write` retire du job `publish` | ROUGE |
| N12 `password: ${{ secrets.PYPI_API_TOKEN }}` reintroduit | ROUGE |
| N13 le diagnostic de `mmu-tui`/PyPI ne nomme plus l'environnement | ROUGE |
| N14 le diagnostic de `mmu-cli-test` ne se declenche plus sur echec | ROUGE |
| N19 la verification d'environnement accepte l'absence de relecteur | ROUGE |
| N20 la verification BLOQUE quand elle ne sait pas | ROUGE |
| N21 la verification ne nomme plus le remede | ROUGE |

| les artefacts | |
|---|---|
| N15 un artefact du bac a sable n'est plus televerse | ROUGE |
| N16 `if-no-files-found: error` retire | ROUGE |
| N30 garde : appel a `poids_admissible` remplace par `pass` | ROUGE |
| N31 garde : plafond releve a 200 Mio | ROUGE |
| N32 garde : plafond rendu exclusif (`>` devient `>=`) | ROUGE |
| N33 garde : poids juge sur le PREMIER artefact seulement | ROUGE |
| N39 garde : le controle du sdist creux est retire | ROUGE |
| N40 garde : le sdist creux n'est cherche que sur le coeur | **SURVIVANT** -- branche inerte sous dispense, voir ci-dessus |
| N41 garde : un sdist sans `.py` est accepte | ROUGE |
| N36 le diagnostic des liens symboliques est retire | ROUGE |
| N42 la panne du `force-include` n'est plus nommee | ROUGE |
| N43 `--wheel` retire de la construction de `mmu-tui` | ROUGE |
| N44 `--wheel` ajoute a la construction de `mmu-cli` | ROUGE |
| N45 garde : comptage assoupli en `len(sources) <= 1` | ROUGE |
| N46 garde : `mmu-cli` entre dans `ROUE_SEULE` | ROUGE |
| N47 garde : un sdist EN TROP est accepte sur une roue seule | ROUGE |
| N48 garde : la borne de la dispense n'est plus ecrite | ROUGE |

| le renommage et la garde de version | |
|---|---|
| N22 substitution 5 (l'epinglage) retiree du renommage | ROUGE |
| N23 temoin de substitution 1 rendu tautologique | ROUGE |
| N24 garde : comparaison du tag supprimee | ROUGE |
| N25 garde : comparaison des deux versions d'un jeu supprimee | ROUGE |
| N26 garde : comparaison de l'epinglage supprimee | ROUGE |
| N27 garde : frontiere negative du bac a sable supprimee | ROUGE |
| N28 garde : les deux jeux ne sont plus compares entre eux | ROUGE |
| N29 garde : le jeu de bac a sable n'est plus lu du tout | ROUGE |
| N37 `MMU_PUBLIC_REPO_SLUG` remis a `TBD` | ROUGE |
| N38 `MMU_PRIVATE_REPO_SLUG` remis au slug public | ROUGE |

DEUX mutants ont d'abord SURVECU, et ce qu'ils ont appris vaut le detour :

* **N28** -- supprimer la comparaison des deux jeux entre eux ne changeait
  rien, parce que le seul cas de desaccord inter-jeux etait AUSSI un
  desaccord INTERNE au bac a sable : une autre comparaison le rattrapait.
  Corrige par un cas ou chaque jeu est internement coherent et ou seule la
  comparaison inter-jeux peut mordre ;
* **N13** -- retirer la ligne `environment pypi` du diagnostic laissait le
  test vert : il cherchait la chaine « pypi », qui figure deja dans l'URL de
  l'index. Corrige en mesurant les CINQ champs du formulaire avec CHACUN sa
  valeur, et non la presence d'un mot quelque part. C'est la tautologie
  classique d'une frontiere qui cherche un fragment trop court.

CE QUE LA MESURE SUR L'ARBRE REEL A TROUVE, ET QUI N'EST PAS DE CETTE STORY
(2026-09-07, `python -m build` joue pour de vrai sur les deux declarations) :

* `mmu_cli-0.1.0.tar.gz` pese **135,9 Mo**, au-dela du plafond de 100 Mio par
  fichier de PyPI. Il embarque `tests/fixtures` (68,8 Mo), `_bmad-output/`
  (47 Mo) et un PDF de `docs/` (26,6 Mo) ;
* `python -m build packaging/mmu-tui` **ne produit pas de roue**, deux fois
  pour deux causes differentes dans la meme heure. D'abord
  `LinkOutsideDestinationError` (trois liens symboliques vers `../../`),
  ferme par la story 8.5 a 16:47 ; puis, une fois les liens remplaces,
  « Forced include not found » -- le sdist ne contient que
  `packaging/mmu-tui/`, six fichiers et pas une ligne de code, et le
  `force-include` qui vise `../../src/` n'a plus rien a inclure. Le sdist
  sort quand meme, a 20 Ko. `python -m build --wheel` seul reussit (921 Ko).

Les deux appartiennent a la declaration (story 8.5). Ce qui appartient a la
chaine, et qui est fait ici, c'est de les REFUSER en les nommant plutot que de
laisser un message de `tarfile`, un 400 de l'index ou un
`pip install --no-binary` casse chez l'utilisateur arriver apres coup -- sur
une sequence a deux index, ces refus tomberaient alors que l'autre paquet est
DEJA publie.

M22, jouee hors du depot sur une COPIE de la declaration reelle, est la seule
que la fabrique ne pouvait pas voir : l'epinglage reecrit `"mmu-cli == 0.1.0"`
-- forme PEP 508 aussi legale que la forme serree -- fait rougir le seul test
de terrain, la fabrique restant verte. Le renommage est donc SENSIBLE a la
forme de l'epinglage, et il le dit plutot que de le taire : il echoue par son
temoin avant toute construction, et la garde de version le rattraperait de
toute facon depuis les metadonnees de la roue.
"""

from __future__ import annotations

import io
import os
import re
import stat
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
PUBLISH = RACINE / ".github" / "workflows" / "publish.yml"
CI = RACINE / ".github" / "workflows" / "ci.yml"
ENV_DEPOT = RACINE / "scripts" / "public-repo.env"

#: Le depot PUBLIC de distribution et le depot de TRAVAIL, depuis le
#: 2026-09-06. Le second porte le suffixe `-dev` ; le premier porte le nom
#: historique, qu'un nouveau depot a repris. Les confondre publierait
#: l'historique de travail.
DEPOT_PUBLIC = "GanTiz/mixed_media_utility"
DEPOT_TRAVAIL = "GanTiz/mixed_media_utility-dev"


# ---------------------------------------------------------------------------
# Lecture du workflow par indentation -- sans PyYAML, voir le docstring.
# ---------------------------------------------------------------------------

def _lignes_du_fichier(fichier: Path = PUBLISH) -> list[str]:
    return fichier.read_text(encoding="utf-8").splitlines()


def _indentation(ligne: str) -> int:
    return len(ligne) - len(ligne.lstrip(" "))


def _bloc_apres(lignes: list[str], indice: int) -> list[str]:
    """Les lignes strictement plus indentees qui suivent `lignes[indice]`."""
    base = _indentation(lignes[indice])
    recueil: list[str] = []
    for ligne in lignes[indice + 1:]:
        if not ligne.strip():
            recueil.append(ligne)
            continue
        if _indentation(ligne) <= base:
            break
        recueil.append(ligne)
    return recueil


def _indentation_minimale(lignes: list[str]) -> int:
    utiles = [l for l in lignes if l.strip()]
    assert utiles, "bloc vide : la lecture du workflow est cassee"
    return min(_indentation(l) for l in utiles)


def _bloc_de_job(nom: str, fichier: Path = PUBLISH) -> list[str]:
    """Les lignes du job `nom`, indentation d'origine conservee."""
    lignes = _lignes_du_fichier(fichier)
    indices = [i for i, l in enumerate(lignes) if l.rstrip() == "jobs:"]
    assert len(indices) == 1, f"{len(indices)} bloc(s) `jobs:` dans {fichier.name}"
    corps = _bloc_apres(lignes, indices[0])
    base = _indentation_minimale(corps)
    for i, ligne in enumerate(corps):
        if _indentation(ligne) == base and ligne.strip() == f"{nom}:":
            return _bloc_apres(corps, i)
    raise AssertionError(f"aucun job `{nom}` dans {fichier.name}")


def _noms_des_jobs() -> list[str]:
    lignes = _lignes_du_fichier()
    (indice,) = [i for i, l in enumerate(lignes) if l.rstrip() == "jobs:"]
    corps = _bloc_apres(lignes, indice)
    base = _indentation_minimale(corps)
    return [l.strip()[:-1] for l in corps
            if l.strip().endswith(":") and _indentation(l) == base
            and " " not in l.strip()[:-1]]


def _etapes(bloc_job: list[str]) -> list[list[str]]:
    """Le bloc `steps:` decoupe en etapes, DANS L'ORDRE du fichier."""
    base_job = _indentation_minimale(bloc_job)
    indices = [i for i, l in enumerate(bloc_job)
               if _indentation(l) == base_job and l.strip() == "steps:"]
    assert len(indices) == 1, "un job doit porter exactement un bloc `steps:`"
    corps = _bloc_apres(bloc_job, indices[0])
    base = _indentation_minimale(corps)
    etapes: list[list[str]] = []
    courante: list[str] | None = None
    for ligne in corps:
        if not ligne.strip():
            if courante is not None:
                courante.append(ligne)
            continue
        if _indentation(ligne) == base and ligne.lstrip().startswith("- "):
            if courante is not None:
                etapes.append(courante)
            coupe = ligne.index("- ")
            courante = [ligne[:coupe] + "  " + ligne[coupe + 2:]]
        elif courante is None:
            # Un bloc de commentaires PRECEDE souvent la premiere etape. Il
            # n'appartient a aucune, et il ne doit pas faire echouer la lecture.
            assert ligne.lstrip().startswith("#"), (
                f"ligne hors etape et non commentee dans `steps:` : {ligne!r}"
            )
        else:
            courante.append(ligne)
    if courante is not None:
        etapes.append(courante)
    assert etapes, "aucune etape lue : la lecture du workflow est cassee"
    return etapes


def _valeur(etape: list[str], cle: str) -> str | None:
    """Valeur scalaire du premier champ `cle:` rencontre dans l'etape."""
    for ligne in etape:
        depouillee = ligne.strip()
        if depouillee.startswith(f"{cle}:"):
            return depouillee[len(cle) + 1:].strip()
    return None


def _valeur_dans_with(etape: list[str], cle: str) -> str | None:
    """Valeur d'un champ du bloc `with:` d'une etape.

    `name:` existe des DEUX cotes -- celui de l'etape et celui de l'artefact --
    et les confondre fait lire le libelle humain la ou un identifiant est
    attendu.
    """
    for i, ligne in enumerate(etape):
        if ligne.strip() == "with:":
            for interne in _bloc_apres(etape, i):
                depouillee = interne.strip()
                if depouillee.startswith(f"{cle}:"):
                    return depouillee[len(cle) + 1:].strip()
    return None


def _nom(etape: list[str]) -> str:
    return _valeur(etape, "name") or _valeur(etape, "uses") or ""


def _script(etape: list[str]) -> str:
    """Le corps litteral du champ `run: |` d'une etape, desindente."""
    for i, ligne in enumerate(etape):
        if ligne.strip() in ("run: |", "run: |-"):
            corps = _bloc_apres(etape, i)
            marge = _indentation_minimale(corps)
            return "\n".join(l[marge:] if l.strip() else "" for l in corps) + "\n"
    raise AssertionError(f"l'etape « {_nom(etape)} » ne porte pas de `run: |`")


def _etape_nommee(bloc_job: list[str], fragment: str) -> list[str]:
    trouvees = [e for e in _etapes(bloc_job) if fragment in _nom(e)]
    assert len(trouvees) == 1, (
        f"{len(trouvees)} etape(s) dont le nom contient « {fragment} », "
        "attendu exactement 1"
    )
    return trouvees[0]


def _etape_exacte(bloc_job: list[str], nom: str) -> list[str]:
    """L'etape dont le nom est EXACTEMENT `nom`.

    Necessaire des qu'un nom est le prefixe d'un autre -- « Publier les
    artefacts du coeur » l'est de « ... du coeur (bac a sable) ». Une
    recherche par fragment en trouverait deux et ne saurait pas laquelle.
    """
    trouvees = [e for e in _etapes(bloc_job) if _nom(e) == nom]
    assert len(trouvees) == 1, (
        f"{len(trouvees)} etape(s) nommee(s) exactement « {nom} »"
    )
    return trouvees[0]


def _rang(noms: list[str], fragment: str) -> int:
    rangs = [i for i, n in enumerate(noms) if fragment in n]
    assert len(rangs) == 1, (
        f"{len(rangs)} etape(s) dont le nom contient « {fragment} » : "
        f"noms lus = {noms}"
    )
    return rangs[0]


# ---------------------------------------------------------------------------
# La SEQUENCE -- construction, TestPyPI, approbation, PyPI
# ---------------------------------------------------------------------------

def test_la_release_est_une_SEQUENCE_et_non_deux_cibles_exclusives():
    """TestPyPI PRECEDE PyPI ; il n'en est pas une alternative.

    Correction d'Egan du 2026-09-07 : « le workflow de release passe par un
    test, une approbation et la release pypi ». Un workflow qui offrirait les
    deux index comme deux choix d'un menu laisserait la release partir sans
    avoir ete essayee nulle part -- et personne ne le verrait, puisque le run
    serait vert.
    """
    assert _noms_des_jobs() == ["valider", "build", "publish", "garde",
                                "release"], _noms_des_jobs()
    besoins_build = [l.strip() for l in _bloc_de_job("build")
                     if l.strip().startswith("needs:")]
    assert besoins_build == ["needs: valider"], besoins_build
    besoins_publish = [l.strip() for l in _bloc_de_job("publish")
                       if l.strip().startswith("needs:")]
    assert besoins_publish == ["needs: build"], besoins_publish
    # `garde` s'est INTERCALE ici le 2026-09-10, entre TestPyPI et PyPI, et
    # c'est un correctif d'interblocage plutot qu'un rangement. La garde
    # d'installation vivait dans `valider`, donc AVANT `publish` -- alors
    # qu'elle INSTALLE depuis TestPyPI et exige la version qu'on publie. Elle
    # reclamait sur l'index ce que seul `publish` pouvait y mettre : aucune
    # version neuve ne pouvait demarrer. Mesure : release v0.1.1, quatre
    # jambes rouges sur quatre, « attendait 0.1.1, rendu : 0.1.0.post601 ».
    # v0.1.0 n'etait passee que par COINCIDENCE, `0.1.0.dev0` trainant sur
    # l'index -- la garde validait donc la version PRECEDENTE.
    besoins_garde = [l.strip() for l in _bloc_de_job("garde")
                     if l.strip().startswith("needs:")]
    assert besoins_garde == ["needs: publish"], (
        "la garde d'installation ne suit plus TestPyPI : si elle repasse "
        "AVANT, elle exigera de l'index une version que rien n'y a encore "
        f"mise, et aucune release ne demarrera. Lu : {besoins_garde}"
    )
    besoins_release = [l.strip() for l in _bloc_de_job("release")
                       if l.strip().startswith("needs:")]
    assert besoins_release == ["needs: [build, publish, garde]"], (
        "le job de production ne depend pas du passage par TestPyPI ET par la "
        "garde d'installation : la sequence est rompue. Lu : "
        f"{besoins_release}"
    )


def test_la_PORTE_de_validation_precede_toute_construction():
    """Le job `valider` appelle `ci.yml` ENTIER, et tout en depend.

    Defaut ferme le 2026-09-02, et REOUVERT par une fusion le 2026-09-07 : les
    deux workflows partent sur le meme tag `v*`, donc EN PARALLELE. Sans ce
    job, la publication n'attend pas les tests -- et sur le vrai PyPI une
    version publiee est irreversible.

    Ce que cette frontiere mesure et qu'aucune relecture ne donne : la porte a
    disparu d'une reecriture sans qu'un seul test rougisse, parce qu'aucun ne
    la nommait. La chaine `needs:` se verifie de proche en proche -- un job
    qui ne remonte pas jusqu'a `valider` se construit sur un arbre non teste.
    """
    bloc = _bloc_de_job("valider")
    base = _indentation_minimale(bloc)
    appels = [l.strip() for l in bloc
              if l.strip().startswith("uses:") and _indentation(l) == base]
    assert appels == ["uses: ./.github/workflows/ci.yml"], (
        "le job `valider` n'appelle plus `ci.yml` : la porte de release ne "
        f"valide plus rien. Lu : {appels}"
    )
    assert (RACINE / ".github" / "workflows" / "ci.yml").is_file()

    # `ci.yml` doit ACCEPTER d'etre appele : sans `workflow_call`, l'appel
    # ci-dessus echoue au demarrage du run et la porte ne mesure rien.
    lignes_ci = _lignes_du_fichier(RACINE / ".github" / "workflows" / "ci.yml")
    (indice,) = [i for i, l in enumerate(lignes_ci) if l.rstrip() == "on:"]
    declencheurs = [l.strip().rstrip(":") for l in _bloc_apres(lignes_ci, indice)
                    if _indentation(l) == 2 and l.strip().endswith(":")]
    assert "workflow_call" in declencheurs, declencheurs

    # Et la chaine remonte : chaque job non-porte depend, de proche en proche,
    # de `valider`. Un job orphelin partirait en parallele de la validation.
    besoins: dict[str, list[str]] = {}
    for nom in _noms_des_jobs():
        brut = [l.strip()[len("needs:"):].strip() for l in _bloc_de_job(nom)
                if l.strip().startswith("needs:")
                and _indentation(l) == _indentation_minimale(_bloc_de_job(nom))]
        besoins[nom] = [] if not brut else [
            m.strip() for m in brut[0].strip("[]").split(",") if m.strip()
        ]
    for nom in besoins:
        if nom == "valider":
            continue
        vus, a_voir = set(), list(besoins[nom])
        while a_voir:
            courant = a_voir.pop()
            if courant in vus:
                continue
            vus.add(courant)
            a_voir.extend(besoins.get(courant, []))
        assert "valider" in vus, (
            f"le job `{nom}` ne remonte pas a la porte `valider` : il "
            f"partirait sans que les tests soient passes. Chaine lue : {vus}"
        )


def test_la_production_n_est_joignable_que_par_un_TAG_et_depuis_le_depot_public():
    """Deux conditions, et chacune ferme un chemin different.

    Sans la condition de tag, un declenchement manuel atteindrait la
    production. Sans la condition de depot, un tag pose par erreur sur le
    depot de TRAVAIL publierait le vrai paquet -- et le jeton d'Egan a le
    droit d'ecrire sur les deux depots, donc rien ne l'arreterait.
    """
    bloc = _bloc_de_job("release")
    base = _indentation_minimale(bloc)
    conditions = [l.strip() for l in bloc
                  if l.strip().startswith("if:") and _indentation(l) == base]
    assert len(conditions) == 1, conditions
    condition = conditions[0]
    assert "github.event_name == 'push'" in condition, condition
    assert "depot_de_distribution == 'oui'" in condition, condition


def test_un_declenchement_MANUEL_ne_peut_viser_que_le_bac_a_sable():
    """L'entree `target` ne propose plus qu'une option, et c'est la garantie.

    Tant que `pypi` figurait dans les options, une release de production
    tenait a ce que personne ne clique a cote dans un menu deroulant.
    """
    lignes = _lignes_du_fichier()
    (indice,) = [i for i, l in enumerate(lignes) if l.strip() == "options:"]
    options = [l.strip()[2:] for l in _bloc_apres(lignes, indice)
               if l.strip().startswith("- ")]
    assert options == ["testpypi"], (
        f"un declenchement manuel peut viser {options} : la production doit "
        "passer par un tag et par l'approbation qui va avec."
    )


@pytest.mark.parametrize("job,index,paquets", [
    ("publish", "TestPyPI", ("mmu-cli-test", "mmu-tui-test")),
    ("release", "PyPI", ("mmu-cli", "mmu-tui")),
])
def test_le_coeur_est_publie_AVANT_l_interface(job, index, paquets):
    """`mmu-cli` part le premier, sur les deux index.

    L'inversion ne rougit nulle part d'elle-meme : les deux televersements
    reussissent. C'est l'installation qui casse, chez l'utilisateur.
    """
    coeur, interface = paquets
    noms = [_nom(e) for e in _etapes(_bloc_de_job(job))]
    rang_cli = _rang(noms, f"Publier {coeur} sur {index}")
    rang_tui = _rang(noms, f"Publier {interface} sur {index}")
    assert rang_cli < rang_tui, (
        f"sur {index}, {interface} (rang {rang_tui}) est publie avant {coeur} "
        f"(rang {rang_cli}) : pendant l'intervalle, son installation echoue "
        "sur une dependance qui n'existe pas encore."
    )


@pytest.mark.parametrize("job,index,paquets", [
    ("publish", "TestPyPI", ("mmu-cli-test", "mmu-tui-test")),
    ("release", "PyPI", ("mmu-cli", "mmu-tui")),
])
def test_l_attente_se_place_ENTRE_les_deux_publications(job, index, paquets):
    """L'attente ne vaut qu'a sa place : apres le coeur, avant l'interface."""
    coeur, interface = paquets
    noms = [_nom(e) for e in _etapes(_bloc_de_job(job))]
    rang_attente = _rang(noms, f"Attendre que {coeur} soit resolvable")
    assert _rang(noms, f"Publier {coeur} sur {index}") < rang_attente, (
        f"l'attente precede la publication de {coeur} : elle attendrait une "
        "version que personne n'a encore televersee."
    )
    assert rang_attente < _rang(noms, f"Publier {interface} sur {index}"), (
        f"{interface} est publie avant l'attente : l'attente ne protege rien."
    )


def test_chaque_publication_vise_le_DOSSIER_de_sa_propre_distribution():
    """Un `dist/` unique publierait plusieurs paquets d'un coup.

    `gh-action-pypi-publish` televerse un DOSSIER. Deux distributions -- et
    surtout deux JEUX, production et bac a sable -- dans le meme dossier,
    c'est l'ordre perdu et le paquet de test pousse en production.
    """
    attendus = {
        ("publish", "Publier mmu-cli-test sur TestPyPI"): "dist/cli-test",
        ("publish", "Publier mmu-tui-test sur TestPyPI"): "dist/tui-test",
        ("release", "Publier mmu-cli sur PyPI"): "dist/cli",
        ("release", "Publier mmu-tui sur PyPI"): "dist/tui",
    }
    for (job, fragment), dossier in attendus.items():
        etape = _etape_nommee(_bloc_de_job(job), fragment)
        assert _valeur(etape, "uses") == "pypa/gh-action-pypi-publish@release/v1"
        assert _valeur(etape, "packages-dir") == dossier, (
            f"« {fragment} » televerse {_valeur(etape, 'packages-dir')!r} "
            f"au lieu de {dossier!r}."
        )
    for fragment in ("Publier mmu-cli-test sur TestPyPI",
                     "Publier mmu-tui-test sur TestPyPI"):
        etape = _etape_nommee(_bloc_de_job("publish"), fragment)
        assert _valeur(etape, "repository-url") == "https://test.pypi.org/legacy/", (
            f"« {fragment} » ne vise pas TestPyPI : sans `repository-url`, "
            "l'action publie sur le VRAI PyPI."
        )
    for fragment in ("Publier mmu-cli sur PyPI", "Publier mmu-tui sur PyPI"):
        etape = _etape_nommee(_bloc_de_job("release"), fragment)
        assert _valeur(etape, "repository-url") is None


# ---------------------------------------------------------------------------
# Les huit artefacts, inspectables avant d'etre pousses
# ---------------------------------------------------------------------------

def test_le_job_build_construit_les_DEUX_JEUX_de_DEUX_distributions():
    bloc = _bloc_de_job("build")
    production = _script(_etape_nommee(bloc, "distributions de PRODUCTION"))
    assert "python -m build --outdir dist/cli ." in production
    assert ("python -m build --outdir dist/tui packaging/mmu-tui"
            in production)
    assert "packaging/mmu-tui/pyproject.toml" in production, (
        "la construction doit NOMMER la declaration absente plutot que "
        "d'echouer sur un message de hatchling."
    )
    sable = _script(_etape_nommee(bloc, "distributions du BAC A SABLE"))
    assert "python -m build --outdir dist/cli-test ." in sable
    assert ("python -m build --outdir dist/tui-test packaging/mmu-tui"
            in sable)


def test_AUCUNE_distribution_ne_se_construit_en_ROUE_SEULE():
    """Frontiere NEGATIVE, et elle protege desormais les QUATRE.

    `--wheel` retire son archive source a la distribution qui le porte SANS
    QU'AUCUNE AUTRE MESURE NE BOUGE : la garde compterait zero sdist, mais elle
    ne le dirait qu'a l'execution de la CI, apres coup. Ici, c'est lu dans le
    fichier.

    Ce test visait `mmu-cli` SEUL jusqu'au 2026-09-10 : l'interface DEVAIT
    porter `--wheel`, faute d'archive source constructible (`EPIC8-ARB-18`).
    `EPIC8-ARB-21` a ferme ce defaut, et la frontiere s'etend donc a
    l'interface -- c'est ce qui empeche la roue seule de revenir en silence.

    Deux etapes, deux jeux : la frontiere porte sur les DEUX, sinon un
    `--wheel` glisse dans le seul bac a sable passerait -- et c'est le jeu qui
    VALIDE la production.
    """
    bloc = _bloc_de_job("build")
    for fragment, coeur, interface in (
            ("distributions de PRODUCTION", "dist/cli", "dist/tui"),
            ("distributions du BAC A SABLE", "dist/cli-test", "dist/tui-test")):
        script = _script(_etape_nommee(bloc, fragment))
        lignes = [l.strip() for l in script.splitlines()
                  if "python -m build" in l]
        du_coeur = [l for l in lignes if f"--outdir {coeur} ." in l]
        de_l_interface = [l for l in lignes if f"--outdir {interface} " in l]
        assert len(du_coeur) == 1 and len(de_l_interface) == 1, (
            f"[{fragment}] lignes de construction lues : {lignes}")
        for role, ligne in (("le coeur", du_coeur[0]),
                            ("l'interface", de_l_interface[0])):
            assert "--wheel" not in ligne, (
                f"[{fragment}] {role} se construit en `--wheel` : il perdrait "
                f"son archive source, et AUCUNE distribution n'est dispensee "
                f"depuis EPIC8-ARB-21. Ligne : {ligne!r}")


def test_le_jeu_de_PRODUCTION_se_construit_AVANT_le_renommage():
    """Le renommage modifie les deux declarations EN PLACE.

    Construire la production apres lui produirait deux roues nommees
    `mmu-cli-test` / `mmu-tui-test` et televersees sur le VRAI PyPI. Le nom
    serait faux, la publication reussirait, et elle serait irreversible : PyPI
    ne rend pas un nom de fichier deja publie.
    """
    noms = [_nom(e) for e in _etapes(_bloc_de_job("build"))]
    rang_production = _rang(noms, "distributions de PRODUCTION")
    rang_renommage = _rang(noms, "Renommer les deux distributions")
    rang_sable = _rang(noms, "distributions du BAC A SABLE")
    assert rang_production < rang_renommage < rang_sable, (
        f"ordre lu : production={rang_production}, renommage={rang_renommage}, "
        f"bac a sable={rang_sable}"
    )


def test_les_huit_artefacts_sont_televerses_et_leur_absence_ROUGIT():
    """Quatre televersements, quatre dossiers, `if-no-files-found: error`.

    Sans ce dernier, un dossier vide passe en silence et la publication part
    sur rien -- exactement le mode de panne que ce job existe pour empecher.
    """
    bloc = _bloc_de_job("build")
    attendus = {
        "Publier les artefacts du coeur": ("dist-cli", "dist/cli/*"),
        "Publier les artefacts de l'interface": ("dist-tui", "dist/tui/*"),
        "Publier les artefacts du coeur (bac a sable)":
            ("dist-cli-test", "dist/cli-test/*"),
        "Publier les artefacts de l'interface (bac a sable)":
            ("dist-tui-test", "dist/tui-test/*"),
    }
    for fragment, (nom_artefact, chemin) in attendus.items():
        etape = _etape_exacte(bloc, fragment)
        assert _valeur(etape, "uses") == "actions/upload-artifact@v4"
        assert _valeur(etape, "path") == chemin
        assert _valeur(etape, "if-no-files-found") == "error", (
            f"« {fragment} » accepte un dossier vide."
        )
        assert _valeur_dans_with(etape, "name") == nom_artefact, (
            f"l'artefact de « {fragment} » ne s'appelle pas {nom_artefact} : "
            "le job qui publie le telechargerait par un nom inexistant."
        )
    # Et chaque artefact televerse est bien celui que la publication reclame.
    for job, artefacts in (("publish", ("dist-cli-test", "dist-tui-test")),
                           ("release", ("dist-cli", "dist-tui"))):
        recuperes = [_valeur_dans_with(e, "name")
                     for e in _etapes(_bloc_de_job(job))
                     if _valeur(e, "uses") == "actions/download-artifact@v4"]
        assert sorted(recuperes) == sorted(artefacts), (
            f"le job {job} recupere {recuperes} au lieu de {list(artefacts)}"
        )


# ---------------------------------------------------------------------------
# Rien sur le vrai PyPI sans intervention humaine
# ---------------------------------------------------------------------------

def test_chaque_publication_est_gardee_par_un_ENVIRONNEMENT_et_par_OIDC():
    for job, environnement in (("publish", "testpypi"), ("release", "pypi")):
        bloc = _bloc_de_job(job)
        environnements = [l.strip() for l in bloc
                          if l.strip().startswith("environment:")]
        assert environnements == [f"environment: {environnement}"], (
            f"le job {job} ne porte pas l'environnement {environnement} : la "
            "protection « Required reviewers » n'a plus de prise. Lu : "
            f"{environnements}"
        )
        assert any(l.strip() == "id-token: write" for l in bloc), (
            f"sans `id-token: write`, le job {job} ne peut pas publier par "
            "OIDC et la seule issue restante serait un jeton en secret."
        )


def test_aucun_jeton_ni_mot_de_passe_ne_revient_dans_le_workflow():
    """Frontiere NEGATIVE : le Trusted Publishing n'a rien a stocker.

    Aucun test positif ne verrait revenir un `password:` -- c'est pourtant le
    reflexe de tout le monde devant une publication qui echoue.
    """
    texte = PUBLISH.read_text(encoding="utf-8")
    lignes_fautives = [l for l in texte.splitlines()
                       if l.strip().startswith(("password:", "user:"))
                       or "secrets." in l]
    assert not lignes_fautives, (
        "un identifiant est reintroduit dans publish.yml alors que la chaine "
        f"publie par OIDC : {lignes_fautives}"
    )


#: Les six lignes de publicateur de confiance qu'Egan doit creer, et que le
#: workflow doit savoir NOMMER quand l'index refuse. La sequence en exige
#: quatre sur TestPyPI -- deux par depot --, parce que les deux depots y
#: publient : le depot de travail pour la repetition, le depot public parce
#: que l'etape TestPyPI fait partie de la release.
#:
#: DEUX adresses par diagnostic depuis `EPIC8-ARB-20`, et ce n'est pas une
#: redondance : la page de COMPTE ne sert qu'a un projet qui n'existe pas
#: encore, la page du PROJET a tous les autres. Envoyer l'operateur a la
#: premiere quand le projet existe le renvoie dans le mur qu'il vient de
#: prendre -- la page de compte n'accepte qu'UN publicateur en attente par
#: (proprietaire, depot, workflow, environnement), mesure le 2026-09-07.
DIAGNOSTICS = {
    ("publish", "Diagnostic si TestPyPI a refuse mmu-cli-test"):
        ("mmu-cli-test", "testpypi", "test.pypi.org/manage/account/publishing/",
         "https://test.pypi.org/manage/project/mmu-cli-test/settings/publishing/"),
    ("publish", "Diagnostic si TestPyPI a refuse mmu-tui-test"):
        ("mmu-tui-test", "testpypi", "test.pypi.org/manage/account/publishing/",
         "https://test.pypi.org/manage/project/mmu-tui-test/settings/publishing/"),
    ("release", "Diagnostic si PyPI a refuse mmu-cli"):
        ("mmu-cli", "pypi", "pypi.org/manage/account/publishing/",
         "https://pypi.org/manage/project/mmu-cli/settings/publishing/"),
    ("release", "Diagnostic si PyPI a refuse mmu-tui"):
        ("mmu-tui", "pypi", "pypi.org/manage/account/publishing/",
         "https://pypi.org/manage/project/mmu-tui/settings/publishing/"),
}


@pytest.mark.parametrize("cle", sorted(DIAGNOSTICS))
def test_un_refus_de_l_index_NOMME_la_ligne_a_creer(cle):
    """« Echoue en nommant ce qui manque », consigne d'Egan du 2026-09-07.

    Un trusted publisher absent rend un message d'OIDC que personne ne sait
    traduire en formulaire. Le diagnostic dit le projet, le proprietaire, le
    depot, le fichier de workflow et l'environnement -- les cinq champs du
    formulaire, dans l'ordre du formulaire.
    """
    job, fragment = cle
    projet, environnement, adresse, _page_projet = DIAGNOSTICS[cle]
    etape = _etape_nommee(_bloc_de_job(job), fragment)
    assert _valeur(etape, "if") == "failure()", (
        "un diagnostic qui ne se declenche pas sur echec ne sert a rien"
    )
    script = _script(etape)
    assert adresse in script, (
        f"le diagnostic de « {fragment} » ne donne pas l'adresse du formulaire"
    )
    # Les cinq CHAMPS du formulaire, chacun avec SA valeur -- et non la simple
    # presence du mot quelque part. « pypi » figure deja dans l'URL de
    # l'index : chercher la chaine seule laissait passer le retrait de la
    # ligne `environment` (mutant N13, survivant a la premiere campagne).
    lignes = [" ".join(l.split()) for l in script.splitlines()]
    champs = (("projet", projet),
              ("proprietaire", "GanTiz"),
              ("depot", "${DEPOT_COURANT#*/}"),
              ("workflow", "publish.yml"),
              ("environment", environnement))
    for champ, valeur in champs:
        assert any(f"{champ} {valeur}" in ligne for ligne in lignes), (
            f"le diagnostic de « {fragment} » ne donne pas le champ "
            f"« {champ} » avec la valeur « {valeur} » : le formulaire de "
            "publicateur de confiance ne peut pas etre rempli sans deviner."
        )


@pytest.mark.parametrize("cle", sorted(DIAGNOSTICS))
def test_un_refus_de_l_index_donne_la_page_DU_PROJET_et_pas_seulement_celle_du_COMPTE(cle):
    """`EPIC8-ARB-20` : les quatre projets EXISTENT avant la premiere release.

    La redaction d'avant le 2026-09-07 ne donnait que la page de COMPTE. Elle
    etait juste dans un monde ou aucun des quatre projets n'existait -- et ce
    monde a dure jusqu'a ce que TestPyPI refuse la deuxieme ligne. Une fois les
    projets amorces, la page de compte ne peut RIEN pour eux : elle ne pose que
    des publicateurs EN ATTENTE, et un publicateur en attente ne s'attache pas a
    un projet existant. L'operateur qui la suit tourne en rond.

    La frontiere exige donc l'adresse EXACTE de la page du projet, `https`
    compris : `manage/project/mmu-cli` est un prefixe de
    `manage/project/mmu-cli-test`, et une adresse tronquee d'un segment
    (`/settings/` retire) rend un 404 sans que personne le voie ici.
    """
    job, fragment = cle
    _projet, _environnement, _compte, page_projet = DIAGNOSTICS[cle]
    script = _script(_etape_nommee(_bloc_de_job(job), fragment))
    assert page_projet in script, (
        f"le diagnostic de « {fragment} » n'envoie qu'a la page de COMPTE. "
        f"Attendu aussi : « {page_projet} ». Un projet DEJA CREE ne se regle "
        "pas depuis la page de compte -- elle ne pose que des publicateurs en "
        "attente, et l'operateur y reprend le refus qui l'a amene ici."
    )


@pytest.mark.parametrize("cle", sorted(DIAGNOSTICS))
def test_un_refus_de_l_index_NOMME_la_contrainte_d_unicite_des_publicateurs_EN_ATTENTE(cle):
    """Le mur qu'Egan a pris le 2026-09-07, nomme la ou on le prend.

    Verbatim de TestPyPI : « A pending trusted publisher matching this
    configuration has already been registered for a different project name. »
    L'unicite porte sur (proprietaire, depot, workflow, environnement) et ne
    vaut QUE pour les publicateurs en attente. Nos six lignes forment trois
    paires qui partagent leur tuple : trois des six sont impossibles a poser
    ainsi, et rien dans le message de PyPI ne dit laquelle des deux passe.

    Le diagnostic doit donc nommer DEUX choses : la contrainte, et le nom du
    projet qui entre en collision avec celui-ci -- sans quoi l'operateur ne
    sait pas ce qu'il faut retirer.

    LE MOTIF SE CHERCHE DANS UNE SEULE LIGNE `echo`, jamais dans le script
    recolle : le recollage (`" ".join(...)`) normalise les espaces mais ne
    franchit PAS les guillemets, donc une phrase coupee entre deux `echo`
    echappe a toute frontiere qui la cherche entiere (lecon de la revue 8.9,
    finding sur « ARBRE DE TRAVAIL »).
    """
    job, fragment = cle
    projet, _environnement, _compte, _page = DIAGNOSTICS[cle]
    #: Le projet qui partage le tuple de celui-ci -- c'est la paire qui rend
    #: la contrainte mordante, et le diagnostic doit la nommer.
    collision = {"mmu-cli-test": "mmu-tui-test", "mmu-tui-test": "mmu-cli-test",
                 "mmu-cli": "mmu-tui", "mmu-tui": "mmu-cli"}[projet]
    lignes = [" ".join(l.split()) for l in _script(_etape_nommee(_bloc_de_job(job), fragment)).splitlines()]
    assert any("QU UN publicateur EN ATTENTE par" in l for l in lignes), (
        f"le diagnostic de « {fragment} » ne dit pas que la page de COMPTE "
        "n'accepte qu'UN publicateur en attente par tuple. C'est le refus "
        "qu'Egan a pris le 2026-09-07, et sans cette phrase l'operateur le "
        "reprend sans comprendre."
    )
    assert any("(proprietaire, depot, workflow, environment)" in l for l in lignes), (
        f"le diagnostic de « {fragment} » nomme la contrainte sans dire SUR "
        "QUOI elle porte. « unique » sans son tuple ne se traduit en aucun geste."
    )
    assert any(collision in l for l in lignes), (
        f"le diagnostic de « {fragment} » ne nomme pas « {collision} », le "
        "projet qui partage son tuple. L'operateur ne peut pas savoir quelle "
        "ligne retirer pour poser celle-ci."
    )


#: La procedure d'operateur qu'`EPIC8-ARB-20` a produite. Le recapitulatif de
#: fin de `publish.yml` y renvoie, et un renvoi qui pourrit est pire qu'aucun
#: renvoi : il se lit comme une garantie.
#:
#: **Deplacee sous `docs/reference/` a la liaison du 2026-09-07**, et le motif
#: n'est pas un rangement : `EPIC11-ARB-268` laisse `_bmad-output/` HORS de
#: l'orphelin public a cinq chemins pres, et celui-ci n'en etait pas. Le renvoi
#: aurait donc pourri **exactement sur le depot ou la sequence tourne**, et
#: `tests/unit/test_perimetre_public.py` l'a rendu en nommant ce banc-ci. La
#: seule autre issue etait d'exclure ce banc de la CI publique -- c'est-a-dire
#: de retirer du public la mesure de la chaine de publication elle-meme.
PROCEDURE_D_AMORCAGE = "docs/reference/amorcage-des-projets-pypi.md"


#: Les deux etapes d'attente, une par index. Elles se ressemblent au nom du
#: paquet pres, et c'est justement ce qui fait qu'une correction portee sur
#: l'une seule passe inapercue -- la premiere redaction de la garde ci-dessous
#: n'en mesurait qu'une.
ATTENTES = {
    ("publish", "Attendre que mmu-cli-test soit resolvable"): "mmu-cli-test",
    ("release", "Attendre que mmu-cli soit resolvable"): "mmu-cli",
}


@pytest.mark.parametrize("cle", sorted(ATTENTES))
def test_le_diagnostic_d_attente_NE_CONSEILLE_PLUS_une_relance_qui_ECHOUERA(cle):
    """`EPIC8-ARB-20`, second volet : Egan a tranche « corriger le texte ».

    La redaction d'avant le 2026-09-07 disait, en cas d'expiration : relancer
    le workflow, « le coeur, lui, est deja en ligne et ne sera pas republie ».
    Le second membre etait vrai -- l'index a bien le coeur -- et le premier
    FAUX : une relance repart de la premiere etape de televersement, retente le
    coeur, et recoit un `400 File already exists`. Le conseil envoyait donc
    l'operateur sur une seconde panne, sans rapport avec la premiere, au moment
    ou il en a le moins les moyens.

    Frontiere NEGATIVE d'abord, parce qu'aucun test positif ne verrait revenir
    une phrase : le litteral fautif ne doit plus figurer dans le fichier.
    """
    job, fragment = cle
    script = _script(_etape_nommee(_bloc_de_job(job), fragment))
    assert "ne sera pas republie" not in script, (
        f"« {fragment} » reconseille une relance en affirmant que le coeur ne "
        "sera pas republie. C'est faux sans skip-existing, et c'est exactement "
        "la redaction qu'EPIC8-ARB-20 a fait retirer."
    )
    lignes = [" ".join(l.split()) for l in script.splitlines()]
    assert any("RELANCER CE WORKFLOW TEL QUEL ECHOUERA" in l for l in lignes), (
        f"« {fragment} » ne dit pas que la relance nue echoue. Sans cette "
        "phrase, l'operateur fait le geste evident et prend un 400."
    )
    assert any("400 File already" in l for l in lignes), (
        f"« {fragment} » annonce l'echec sans nommer le message que l'index "
        "rendra. Un operateur qui ne reconnait pas l'erreur la croit nouvelle."
    )


@pytest.mark.parametrize("cle", sorted(ATTENTES))
def test_le_diagnostic_d_attente_donne_DEUX_ISSUES_et_jamais_un_blocage_sec(cle):
    """`EPIC11-ARB-89` applique a un diagnostic plutot qu'a une ecriture.

    « Toujours proposer au moins deux issues, jamais un blocage sec. » Un
    diagnostic qui dit seulement « ca a echoue » est un blocage sec verbal : il
    laisse l'operateur devant un index a moitie publie sans aucun geste nomme.

    Les deux issues sont NOMMEES ici parce qu'elles ne sont pas
    interchangeables : reprendre sous un nouveau numero rejoue la sequence
    entiere, televerser l'interface seule termine celle qui est en cours. Et la
    frontiere exige la RAISON qui exclut la troisieme issue qu'on croit
    voir -- reprendre le meme numero apres avoir supprime la release --, parce
    que c'est le geste que tout le monde tente en premier.
    """
    job, fragment = cle
    lignes = [" ".join(l.split())
              for l in _script(_etape_nommee(_bloc_de_job(job), fragment)).splitlines()]
    assert any("DEUX ISSUES, jamais un blocage sec" in l for l in lignes), (
        f"« {fragment} » ne dit pas qu'il y a deux issues."
    )
    assert any("NOUVEAU numero de version" in l for l in lignes), (
        f"« {fragment} » ne nomme pas la premiere issue -- reprendre sous un "
        "autre numero."
    )
    assert any("televerser mmu-tui SEUL" in l for l in lignes), (
        f"« {fragment} » ne nomme pas la seconde issue -- poser l'interface "
        "seule, le coeur etant deja bon."
    )
    assert any("ne se reprend JAMAIS" in l for l in lignes), (
        f"« {fragment} » ne dit pas qu'un nom de fichier deja televerse ne se "
        "reprend jamais, meme apres suppression. C'est ce qui exclut le geste "
        "que l'operateur tente en premier, et rien d'autre ne le lui dira."
    )


def test_AUCUNE_etape_de_la_chaine_ne_pose_skip_existing():
    """L'autre moitie de l'arbitrage, et elle se mesure en negatif.

    Egan a ecarte `skip-existing` en connaissance de cause : il rendrait la
    relance sans risque, mais il masquerait aussi une VRAIE collision -- une
    version deja sortie republiee par erreur passerait en silence au lieu
    d'etre refusee. Le diagnostic corrige ci-dessus DIT que ce reglage n'existe
    pas ici ; si quelqu'un le posait, le diagnostic deviendrait faux dans
    l'autre sens, et aucune des frontieres ci-dessus ne le verrait.

    C'est donc la frontiere qui tient la coherence entre ce que la chaine FAIT
    et ce qu'elle DIT.
    """
    fautives = [f"{n + 1}: {l.rstrip()}"
                for n, l in enumerate(_lignes_du_fichier(PUBLISH))
                if "skip-existing" in l and not l.lstrip().startswith("#")
                and "echo" not in l]
    assert not fautives, (
        "skip-existing est pose dans la chaine alors que le diagnostic "
        f"d'attente affirme qu'il n'y en a pas : {fautives}. Les deux ne "
        "peuvent pas etre vrais -- soit le reglage part, soit le diagnostic "
        "est reecrit (et EPIC8-ARB-20 avait tranche pour le premier)."
    )


def test_le_recapitulatif_d_operateur_RENVOIE_a_une_procedure_qui_EXISTE():
    """Un module porte sans sa mesure, applique a un renvoi de document.

    Le recapitulatif de fin de `publish.yml` est ce que quelqu'un lit a deux
    heures du matin, une release bloquee sous les yeux. Depuis
    `EPIC8-ARB-20` il ne suffit plus a lui seul -- l'amorcage par jeton se
    joue en cinq etapes, et elles vivent dans un document a part. Ce test
    tient les DEUX bouts, parce que chacun peut se rompre seul : le renvoi
    peut disparaitre du workflow, et le fichier vise peut etre renomme ou
    deplace sans que rien ne le signale.
    """
    texte = PUBLISH.read_text(encoding="utf-8")
    assert PROCEDURE_D_AMORCAGE in texte, (
        "le recapitulatif de publish.yml ne renvoie plus a la procedure "
        f"d'amorcage ({PROCEDURE_D_AMORCAGE}). Sans elle, il annonce six "
        "publicateurs sans dire que trois sont impossibles a poser."
    )
    assert (RACINE / PROCEDURE_D_AMORCAGE).is_file(), (
        f"publish.yml renvoie a {PROCEDURE_D_AMORCAGE}, qui n'existe pas. "
        "Un renvoi mort se lit comme une garantie."
    )


# ---------------------------------------------------------------------------
# L'environnement de production, verifie plutot qu'espere
# ---------------------------------------------------------------------------

def _stub_curl_api(tmp_path: Path, corps: str, code: str) -> dict[str, str]:
    """Un `curl` d'emprunt qui honore `-o` et rend le code demande."""
    faux_bin = tmp_path / "faux-bin"
    faux_bin.mkdir(exist_ok=True)
    fichier_corps = tmp_path / "corps-de-l-api.json"
    fichier_corps.write_text(corps, encoding="utf-8")
    faux_curl = faux_bin / "curl"
    faux_curl.write_text(
        "#!/bin/sh\n"
        "cible=''\n"
        "while [ $# -gt 0 ]; do\n"
        "  if [ \"$1\" = '-o' ]; then cible=\"$2\"; shift 2; else shift; fi\n"
        "done\n"
        f"[ -n \"$cible\" ] && cat '{fichier_corps}' > \"$cible\"\n"
        f"printf '%s' '{code}'\n",
        encoding="utf-8",
    )
    faux_curl.chmod(faux_curl.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    environnement = dict(os.environ)
    environnement["PATH"] = f"{faux_bin}{os.pathsep}{environnement['PATH']}"
    environnement.update({
        "ENVIRONNEMENT": "pypi",
        "GITHUB_TOKEN": "jeton-d-emprunt",
        "GITHUB_API_URL": "https://api.github.d.emprunt",
        "GITHUB_REPOSITORY": DEPOT_PUBLIC,
    })
    return environnement


def _joue_la_verification(tmp_path: Path, corps: str,
                          code: str) -> subprocess.CompletedProcess:
    script = tmp_path / "verifier.sh"
    script.write_text(
        _script(_etape_nommee(_bloc_de_job("release"), "REELLEMENT protege")),
        encoding="utf-8",
    )
    return subprocess.run(["bash", str(script)], cwd=tmp_path,
                          env=_stub_curl_api(tmp_path, corps, code),
                          capture_output=True, text=True, timeout=60)


PROTEGE = ('{"name":"pypi","protection_rules":['
           '{"id":1,"type":"required_reviewers","reviewers":[{"type":"User"}]},'
           '{"id":2,"type":"branch_policy"}]}')
#: Le meme environnement, avec des regles mais AUCUN relecteur. C'est l'etat
#: qu'un environnement AUTO-CREE par GitHub presente, et c'est celui qu'un
#: « deja fait je crois » laisse passer.
SANS_RELECTEUR = ('{"name":"pypi","protection_rules":['
                  '{"id":2,"type":"wait_timer","wait_timer":0},'
                  '{"id":3,"type":"branch_policy"}]}')


def test_l_environnement_de_production_protege_laisse_passer(tmp_path):
    resultat = _joue_la_verification(tmp_path, PROTEGE, "200")
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode == 0, sortie
    assert "la porte tient" in sortie, sortie


def test_un_environnement_SANS_RELECTEUR_arrete_la_release(tmp_path):
    """Le defaut exact qu'Egan risque : « deja fait je crois ».

    Un environnement GitHub reference par un workflow et qui n'existe pas est
    CREE AUTOMATIQUEMENT, sans protection. Son absence ne leve donc aucune
    erreur -- elle supprime la porte, et la seule trace serait une release
    deja publiee sans que personne ait approuve.
    """
    resultat = _joue_la_verification(tmp_path, SANS_RELECTEUR, "200")
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "::error::" in sortie, sortie
    for attendu in ("Required reviewers", "Settings > Environments", "v*"):
        assert attendu in sortie, f"le refus ne nomme pas « {attendu} » :\n{sortie}"


def test_un_environnement_ILLISIBLE_avertit_sans_bloquer(tmp_path):
    """Jamais un blocage sec sur une INCERTITUDE.

    Le jeton d'un run n'a pas, par defaut, le droit de lire les environnements
    du depot. Un 403 ne dit donc rien de la protection -- ni qu'elle existe,
    ni qu'elle manque. Refuser la release sur cette base rendrait la chaine
    inutilisable ; passer en silence perdrait l'avertissement.
    """
    resultat = _joue_la_verification(tmp_path, "{}", "403")
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode == 0, sortie
    assert "::warning::" in sortie, sortie
    assert "403" in sortie and "Required reviewers" in sortie, sortie


# ---------------------------------------------------------------------------
# Le lieu -- une release de production ne part pas de n'importe quel depot
# ---------------------------------------------------------------------------

def _joue_la_reconnaissance(tmp_path: Path, depot: str,
                            slug: str = DEPOT_PUBLIC) -> subprocess.CompletedProcess:
    script = tmp_path / "lieu.sh"
    script.write_text(
        _script(_etape_nommee(_bloc_de_job("build"), "Reconnaitre le depot")),
        encoding="utf-8",
    )
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "scripts" / "public-repo.env").write_text(
        f"MMU_PUBLIC_REPO_SLUG={slug}\n"
        f"MMU_PRIVATE_REPO_SLUG={DEPOT_TRAVAIL}\n", encoding="utf-8")
    environnement = dict(os.environ)
    environnement["DEPOT_COURANT"] = depot
    environnement["GITHUB_OUTPUT"] = str(tmp_path / "sortie.txt")
    return subprocess.run(["bash", str(script)], cwd=tmp_path,
                          env=environnement, capture_output=True, text=True,
                          timeout=60)


@pytest.mark.parametrize("depot,attendu", [
    (DEPOT_PUBLIC, "oui"),
    (DEPOT_TRAVAIL, "non"),
    ("GanTiz/un-fork-quelconque", "non"),
])
def test_seul_le_depot_de_DISTRIBUTION_ouvre_la_production(tmp_path, depot,
                                                           attendu):
    """Trois depots distinguables, dont deux qui se ressemblent beaucoup.

    `mixed_media_utility` et `mixed_media_utility-dev` ne different que par un
    suffixe, et le jeton d'Egan ecrit sur les deux : une comparaison relachee
    (un `case` avec joker, un `grep`) les confondrait sans que rien ne le
    signale avant une publication.
    """
    resultat = _joue_la_reconnaissance(tmp_path, depot)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    sortie = (tmp_path / "sortie.txt").read_text(encoding="utf-8")
    assert f"depot_de_distribution={attendu}" in sortie, (
        f"{depot} est reconnu autrement qu'attendu : {sortie!r}\n"
        + resultat.stdout
    )


def test_un_slug_reste_a_TBD_arrete_tout(tmp_path):
    """Sans slug, la question « suis-je le depot de distribution ? » n'a pas
    de reponse -- et une reponse inventee vaudrait publication."""
    resultat = _joue_la_reconnaissance(tmp_path, DEPOT_PUBLIC, slug="TBD")
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "TBD" in sortie and "::error::" in sortie, sortie


# ---------------------------------------------------------------------------
# Le renommage TestPyPI, EXECUTE
# ---------------------------------------------------------------------------

#: LE RANG DE TENTATIVE QUE CE BANC JOUE. Meme arithmetique que le script --
#: `run_number * 100 + run_attempt` --, recopiee ici a dessein : si le script
#: changeait de formule sans que ce banc le suive, les assertions ci-dessous
#: cesseraient de correspondre et le diraient. C'est une valeur ATTENDUE, pas
#: une source de verite.
RUN_NUMBER_DU_BANC = 7
RUN_ATTEMPT_DU_BANC = 2
SUFFIXE_DU_BAC_A_SABLE = f".post{RUN_NUMBER_DU_BANC * 100 + RUN_ATTEMPT_DU_BANC}"


def _version_du_depot() -> str:
    """La version REELLE du depot, lue a sa source unique.

    `EPIC8-ARB-10` : « UNE seule source de version pour les deux
    distributions ». Un banc qui travaille sur les fichiers reels la lit ici ;
    la recopier en litteral le ferait rougir a chaque release, en accusant le
    code d'un defaut qui serait le sien.
    """
    texte = (RACINE / "src" / "mixed_media_utility" / "__init__.py").read_text(
        encoding="utf-8")
    trouve = re.search(r'__version__\s*=\s*"([^"]+)"', texte)
    assert trouve, "la source unique de version ne porte pas `__version__`"
    return trouve.group(1)

#: Les cinq substitutions, dans l'ordre du script. La fabrique ci-dessous les
#: produit toutes ; les tests de panne visent chacune a son tour -- donc la
#: PREMIERE et la DERNIERE comprises, et pas seulement une du milieu.
LIGNES_A_SUBSTITUER = {
    "nom-du-coeur": ('pyproject.toml', 'name = "mmu-cli"'),
    "commande-du-coeur": ('pyproject.toml', 'mmu = "mixed_media_utility.cli:main"'),
    "nom-de-l-interface": ('packaging/mmu-tui/pyproject.toml', 'name = "mmu-tui"'),
    "epinglage": ('packaging/mmu-tui/pyproject.toml', '  "mmu-cli==0.1.0",'),
    "commande-de-l-interface": (
        'packaging/mmu-tui/pyproject.toml',
        'mmu-tui = "mixed_media_utility.tui.__main__:main"',
    ),
}


def _fabrique_les_deux_declarations(racine: Path, sans: str | None = None,
                                    *, source_de_version: bool = True) -> None:
    """Ecrit les deux `pyproject.toml` que le renommage attend.

    Les deux fichiers portent des valeurs DISTINGUABLES (deux noms, deux
    commandes, deux listes de dependances) : une substitution qui viserait le
    mauvais fichier, ou qui recopierait une valeur de l'autre, se verrait.
    `sans` retire une ligne, pour mesurer que le script NOMME la substitution
    qui ne mord plus.
    """
    lignes_racine = [
        "[build-system]",
        'requires = ["hatchling>=1.27"]',
        "",
        "[project]",
        'name = "mmu-cli"',
        'description = "le coeur et la ligne de commande"',
        "dependencies = [",
        '  "numpy>=2.0",',
        '  "Pillow",',
        "]",
        "",
        "[project.scripts]",
        'mmu = "mixed_media_utility.cli:main"',
    ]
    lignes_tui = [
        "[build-system]",
        'requires = ["hatchling>=1.27"]',
        "",
        "[project]",
        'name = "mmu-tui"',
        'description = "l interface terminal"',
        "dependencies = [",
        '  "mmu-cli==0.1.0",',
        '  "textual>=8.2,<9",',
        '  "rich>=14.2",',
        "]",
        "",
        "[project.scripts]",
        'mmu-tui = "mixed_media_utility.tui.__main__:main"',
    ]
    if sans is not None:
        fichier, ligne = LIGNES_A_SUBSTITUER[sans]
        cible = lignes_racine if fichier == "pyproject.toml" else lignes_tui
        assert ligne in cible, f"la fabrique ne porte pas « {ligne} »"
        cible.remove(ligne)

    (racine / "pyproject.toml").write_text("\n".join(lignes_racine) + "\n",
                                           encoding="utf-8")
    dossier = racine / "packaging" / "mmu-tui"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "pyproject.toml").write_text("\n".join(lignes_tui) + "\n",
                                            encoding="utf-8")

    # La SOURCE UNIQUE de version (EPIC8-ARB-10). Le renommage la reecrit
    # depuis le 2026-09-09 pour donner au bac a sable son rang de tentative :
    # sans ce fichier, l'etape s'arrete en le nommant.
    if source_de_version:
        module = racine / "src" / "mixed_media_utility"
        module.mkdir(parents=True, exist_ok=True)
        (module / "__init__.py").write_text(
            '__version__ = "0.1.0"\n', encoding="utf-8")


def _joue_le_renommage(racine: Path) -> subprocess.CompletedProcess:
    script = racine / "renommer.sh"
    script.write_text(
        _script(_etape_nommee(_bloc_de_job("build"), "Renommer les deux")),
        encoding="utf-8",
    )
    environnement = dict(os.environ)
    environnement.update({
        "GITHUB_RUN_NUMBER": str(RUN_NUMBER_DU_BANC),
        "GITHUB_RUN_ATTEMPT": str(RUN_ATTEMPT_DU_BANC),
    })
    return subprocess.run(["bash", str(script)], cwd=racine, env=environnement,
                          capture_output=True, text=True, timeout=60)


def test_le_renommage_porte_sur_les_deux_noms_les_deux_commandes_et_l_epinglage(tmp_path):
    _fabrique_les_deux_declarations(tmp_path)
    resultat = _joue_le_renommage(tmp_path)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr

    racine = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    tui = (tmp_path / "packaging" / "mmu-tui" / "pyproject.toml").read_text(
        encoding="utf-8")

    assert 'name = "mmu-cli-test"' in racine
    assert 'mmu-test = "mixed_media_utility.cli:main"' in racine
    assert 'name = "mmu-tui-test"' in tui
    assert 'mmu-tui-test = "mixed_media_utility.tui.__main__:main"' in tui

    # LA VERSION DU BAC A SABLE, et l'epinglage qui la SUIT. Les deux bougent
    # ensemble ou la roue de l'interface exige une version que l'index ne
    # portera jamais -- `mmu-tui` epingle `mmu-cli` a l'unite pres.
    version = (tmp_path / "src" / "mixed_media_utility" / "__init__.py").read_text(
        encoding="utf-8")
    assert f'__version__ = "0.1.0{SUFFIXE_DU_BAC_A_SABLE}"' in version, version
    assert f'"mmu-cli-test==0.1.0{SUFFIXE_DU_BAC_A_SABLE}"' in tui, tui

    # Ce qui n'a PAS a bouger : les dependances tierces gardent leur nom.
    assert '"textual>=8.2,<9"' in tui
    assert '"numpy>=2.0"' in racine


def test_le_paquet_de_test_ne_depend_JAMAIS_du_paquet_de_PRODUCTION(tmp_path):
    """Frontiere NEGATIVE de l'AC3.

    Le defaut qu'elle attrape est muet : `mmu-tui-test` s'installerait
    parfaitement en tirant `mmu-cli` de la production, et la mesure de
    packaging que TestPyPI existe pour faire ne mesurerait plus rien.
    """
    _fabrique_les_deux_declarations(tmp_path)
    assert _joue_le_renommage(tmp_path).returncode == 0
    tui = (tmp_path / "packaging" / "mmu-tui" / "pyproject.toml").read_text(
        encoding="utf-8")
    assert '"mmu-cli==' not in tui, (
        "apres renommage, le paquet de test depend encore du paquet reel :\n" + tui
    )


@pytest.mark.parametrize("substitution", sorted(LIGNES_A_SUBSTITUER))
def test_le_renommage_NOMME_la_substitution_qui_ne_mord_plus(tmp_path, substitution):
    """Un `sed` qui ne remplace rien sort a ZERO. C'est le temoin qui parle.

    Joue sur les CINQ substitutions, donc sur la premiere et sur la derniere du
    script -- un temoin manquant en tete ou en queue ne se demasque pas
    autrement (CLAUDE.md, regle des fabriques, point 4).
    """
    _fabrique_les_deux_declarations(tmp_path, sans=substitution)
    resultat = _joue_le_renommage(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, (
        f"la substitution « {substitution} » n'a rien remplace et le script "
        f"sort quand meme a zero :\n{sortie}"
    )
    assert "::error::Renommage TestPyPI sans effet" in sortie, sortie


def test_le_renommage_mord_sur_les_DECLARATIONS_REELLES_du_depot(tmp_path):
    """La fabrique mesure la fabrique ; le terrain mesure le produit.

    CLAUDE.md, 2026-09-02 : « une fixture de synthese peut fabriquer une panne
    que le terrain n'a PAS », et son symetrique -- une fixture peut aussi
    fabriquer un SUCCES que le terrain n'a pas. Les motifs de `sed` sont
    ancres (`^name = `, `^mmu = `) : une fabrique qui ecrit ces lignes en
    colonne zero les satisfait par construction, alors que les fichiers reels
    portent des commentaires, des tables et une ligne de prose ou `mmu-cli==X`
    apparait sans guillemet.

    Les deux `pyproject.toml` REELS sont donc copies et renommes pour de vrai.
    """
    reels = {
        "pyproject.toml": RACINE / "pyproject.toml",
        "packaging/mmu-tui/pyproject.toml":
            RACINE / "packaging" / "mmu-tui" / "pyproject.toml",
        # La source unique de version, reelle elle aussi : c'est sur ELLE que
        # le rang de tentative se pose, et son format (`__version__ = "..."`)
        # est ce que le `sed` du script attend.
        "src/mixed_media_utility/__init__.py":
            RACINE / "src" / "mixed_media_utility" / "__init__.py",
    }
    for relatif, source in reels.items():
        assert source.is_file(), (
            f"{relatif} est absent du depot : la scission en deux "
            "distributions (story 8.5) est le contrat sur lequel cette chaine "
            "de publication est batie."
        )
        cible = tmp_path / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    resultat = _joue_le_renommage(tmp_path)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr

    racine = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    tui = (tmp_path / "packaging" / "mmu-tui" / "pyproject.toml").read_text(
        encoding="utf-8")

    assert 'name = "mmu-cli-test"' in racine
    assert '\nmmu-test = ' in racine
    assert 'name = "mmu-tui-test"' in tui
    assert '\nmmu-tui-test = ' in tui
    # **La version se LIT a sa source, elle ne se recopie pas ici** (corrige le
    # 2026-09-09, a la release v0.1.1). Ce banc portait `0.1.0` en dur alors
    # qu'il travaille sur les fichiers REELS : il rougissait donc a la premiere
    # version suivante, en accusant le renommage d'un defaut qui etait le sien.
    # C'est le defaut exact que `CLAUDE.md` releve deja sur `depot_public.py`
    # -- « le second etait perime des `v0.2.0`, et un recapitulatif perime
    # dicte un tag faux ». Les fabriques de SYNTHESE de ce fichier gardent
    # leur version litterale, et c'est juste : elles choisissent la leur.
    version_reelle = _version_du_depot()
    assert f'"mmu-cli-test=={version_reelle}{SUFFIXE_DU_BAC_A_SABLE}"' in tui, (
        "sur les fichiers REELS, l'epinglage ne porte pas le rang de "
        "tentative : la roue de l'interface exigerait une version du coeur "
        f"que TestPyPI ne portera pas (version du depot : {version_reelle}).\n"
        + tui)
    # Frontiere NEGATIVE, sur le terrain : plus aucune dependance vers le
    # paquet de PRODUCTION dans la declaration de l'interface.
    assert '"mmu-cli==' not in tui, (
        "sur les fichiers REELS, l'epinglage vers le paquet de production "
        "survit au renommage."
    )
    # Et ce qui ne doit PAS bouger : la racine ne declare pas de commande
    # `mmu-tui`, et les dependances tierces gardent leur nom.
    assert '"textual>=' in tui
    assert "mmu-tui-test = " not in racine


def test_le_renommage_NOMME_la_declaration_ABSENTE(tmp_path):
    """`packaging/mmu-tui/` absent : la cause est nommee, pas devinee."""
    (tmp_path / "pyproject.toml").write_text('name = "mmu-cli"\nmmu = "x"\n',
                                             encoding="utf-8")
    resultat = _joue_le_renommage(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0
    assert "packaging/mmu-tui/pyproject.toml est absent" in sortie, sortie


# ---------------------------------------------------------------------------
# La garde de version, EXECUTEE contre des roues fabriquees
# ---------------------------------------------------------------------------

def _roue(dossier: Path, nom: str, version: str, exigences=(), *,
          sdist_creux: bool = False, sans_sdist: bool = False,
          roue_creuse: bool = False) -> None:
    """Une roue et, sauf `sans_sdist`, son archive source.

    Le sdist est une VRAIE archive : la garde l'ouvre pour verifier qu'il
    porte au moins un module. `sdist_creux` fabrique la coquille que la
    declaration reelle de `mmu-tui` produisait le 2026-09-07 -- metadonnees
    seules, pas une ligne de code.

    `sans_sdist` reproduit ce que `python -m build --wheel` rend depuis
    `EPIC8-ARB-18` : une roue, et rien d'autre dans le dossier.

    LA ROUE PORTE UN MODULE, et ce n'est pas un detail de fabrication. Jusqu'au
    2026-09-07 elle ne portait que `METADATA` -- la couche 1 de la revue 8.9 a
    mesure que les quatre roues du banc etaient CREUSES et que la garde les
    acceptait. Une fabrique qui ne produit pas un artefact realiste ne mesure
    pas ce qu'elle croit mesurer. `roue_creuse` fabrique la coquille
    DELIBEREMENT, pour la frontiere qui la refuse.
    """
    # DEUX PARAMETRES QUI SE CONTREDISENT NE SE DEPARTAGENT PAS EN SILENCE.
    # `sdist_creux` demande une archive source en coquille ; `sans_sdist`
    # demande qu'il n'y en ait aucune. La redaction precedente laissait le
    # second gagner sans un mot : un test qui passait `sdist_creux=("tui",)`
    # ne fabriquait RIEN et mesurait le cas nominal en croyant mesurer la
    # coquille. Mesure par la couche 2 de la revue 8.9 -- le seul vrai chemin
    # silencieux du diff.
    assert not (sdist_creux and sans_sdist), (
        f"{nom} : `sdist_creux` et `sans_sdist` sont demandes ensemble. Une "
        "distribution en ROUE SEULE n'a pas d'archive source, creuse ou non : "
        "le test qui demande les deux ne mesure pas ce qu'il croit")
    assert not (roue_creuse and sdist_creux), (
        f"{nom} : `roue_creuse` et `sdist_creux` ensemble fabriquent une "
        "distribution entierement vide, dont le refus ne designerait aucune "
        "cause en particulier")

    dossier.mkdir(parents=True, exist_ok=True)
    base = nom.replace("-", "_")
    metadata = ["Metadata-Version: 2.1", f"Name: {nom}", f"Version: {version}"]
    metadata += [f"Requires-Dist: {e}" for e in exigences]
    with zipfile.ZipFile(dossier / f"{base}-{version}-py3-none-any.whl", "w") as roue:
        roue.writestr(f"{base}-{version}.dist-info/METADATA",
                      "\n".join(metadata) + "\n")
        if not roue_creuse:
            # Deux modules, pas un : une fabrique de collection produit au
            # moins deux elements distinguables (regle des fabriques).
            roue.writestr(f"{base}/__init__.py", f'__version__ = "{version}"\n')
            roue.writestr(f"{base}/__main__.py", "def main():\n    return 0\n")

    if sans_sdist:
        return

    racine = f"{base}-{version}"
    membres = {f"{racine}/PKG-INFO": "\n".join(metadata) + "\n",
               f"{racine}/pyproject.toml": f'name = "{nom}"\n'}
    if not sdist_creux:
        membres[f"{racine}/src/{base}/__init__.py"] = f'__version__ = "{version}"\n'
    with tarfile.open(dossier / f"{base}-{version}.tar.gz", "w:gz") as source:
        for nom_du_membre, contenu in membres.items():
            octets = contenu.encode("utf-8")
            info = tarfile.TarInfo(nom_du_membre)
            info.size = len(octets)
            source.addfile(info, io.BytesIO(octets))


def _fabrique_les_deux_jeux(tmp_path: Path, *, version="0.1.0",
                            version_tui=None, epinglage="mmu-cli==0.1.0",
                            nom_cli="mmu-cli",
                            version_test=None,
                            epinglage_test=None,
                            exigences_test_en_plus=(),
                            sdist_creux=(),
                            sdist_manquant=(),
                            roues_creuses=()) -> None:
    """Les QUATRE distributions : production et bac a sable, distinguables.

    LES QUATRE PORTENT UN SDIST depuis `EPIC8-ARB-21`. La fabrique produisait
    l'ABSENCE d'archive source pour l'interface, la dispense d'`EPIC8-ARB-18`
    l'exigeant ; `packaging/mmu-tui/hatch_build.py` a rendu cette archive
    constructible, et le registre de dispense est vide.

    `sdist_creux` nomme les distributions dont le sdist doit sortir en
    coquille -- il vaut desormais pour les quatre.

    `sdist_manquant` nomme celles auxquelles on n'en fabrique aucun : c'est le
    mutant qui verifie que la garde EXIGE l'archive source partout. Il remplace
    `sdist_en_trop`, dont la mesure -- « la dispense porte sur l'absence, pas
    sur une tolerance » -- n'a plus de sujet, aucune distribution n'etant
    dispensee. Cette mesure-la n'est pas perdue : elle est rejouee sur une
    dispense REARMEE par
    `test_la_garde_REFUSE_un_sdist_EN_TROP_sur_une_dispense_REARMEE`.
    """
    _roue(tmp_path / "dist" / "cli", nom_cli, version,
          sdist_creux="cli" in sdist_creux,
          sans_sdist="cli" in sdist_manquant,
          roue_creuse="cli" in roues_creuses)
    _roue(tmp_path / "dist" / "tui", "mmu-tui", version_tui or version,
          ([epinglage] if epinglage else []) + ["textual>=8.2,<9"],
          sdist_creux="tui" in sdist_creux,
          sans_sdist="tui" in sdist_manquant,
          roue_creuse="tui" in roues_creuses)
    # LE BAC A SABLE PORTE SON RANG DE TENTATIVE PAR DEFAUT, comme le
    # renommage le pose depuis le 2026-09-09 : c'est ce qui rend son nom de
    # fichier neuf a chaque course, et donc republiable. Fabriquer les deux
    # jeux a la MEME version reproduirait l'etat qui a fait echouer la release
    # -- et la garde le refuse desormais.
    version_bac = version_test or f"{version}{SUFFIXE_DU_BAC_A_SABLE}"
    if epinglage_test is None:
        epinglage_test = f"mmu-cli-test=={version_bac}"
    _roue(tmp_path / "dist" / "cli-test", "mmu-cli-test", version_bac,
          sdist_creux="cli-test" in sdist_creux,
          sans_sdist="cli-test" in sdist_manquant,
          roue_creuse="cli-test" in roues_creuses)
    _roue(tmp_path / "dist" / "tui-test", "mmu-tui-test", version_bac,
          ([epinglage_test] if epinglage_test else [])
          + list(exigences_test_en_plus) + ["textual>=8.2,<9"],
          sdist_creux="tui-test" in sdist_creux,
          sans_sdist="tui-test" in sdist_manquant,
          roue_creuse="tui-test" in roues_creuses)


def _joue_la_garde(tmp_path: Path, *, evenement="push", ref="v0.1.0",
                   source=None, nom="garde.sh"
                   ) -> subprocess.CompletedProcess:
    """Joue la garde de version. `source` permet d'en jouer une version MUTEE.

    Le mutant est toujours applique au SCRIPT joue, jamais au fichier du depot
    -- et il passe par ici plutot que par un `subprocess.run` recopie : c'est
    l'environnement (les quatre `DOSSIER_*`) qu'une recopie oublie, et une
    garde privee de ses dossiers refuse pour la mauvaise raison, ce qui rend le
    test vert ou rouge sans rapport avec ce qu'il croit mesurer.
    """
    script = tmp_path / nom
    script.write_text(
        source if source is not None
        else _script(_etape_nommee(_bloc_de_job("build"), "Garde de version")),
        encoding="utf-8",
    )
    environnement = dict(os.environ)
    environnement.update({
        "EVENEMENT": evenement, "REF_NAME": ref,
        "DOSSIER_CLI": str(tmp_path / "dist" / "cli"),
        "DOSSIER_TUI": str(tmp_path / "dist" / "tui"),
        "DOSSIER_CLI_TEST": str(tmp_path / "dist" / "cli-test"),
        "DOSSIER_TUI_TEST": str(tmp_path / "dist" / "tui-test"),
        "GITHUB_OUTPUT": str(tmp_path / "sortie.txt"),
    })
    return subprocess.run(["bash", str(script)], cwd=tmp_path, env=environnement,
                          capture_output=True, text=True, timeout=120)


def test_la_garde_laisse_passer_les_QUATRE_valeurs_accordees(tmp_path):
    _fabrique_les_deux_jeux(tmp_path)
    resultat = _joue_la_garde(tmp_path)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    assert "version=0.1.0" in (tmp_path / "sortie.txt").read_text(encoding="utf-8"), (
        "la garde ne publie pas la version : l'attente qui suit n'aurait rien "
        "a chercher sur l'index."
    )


#: Les desaccords, un par valeur confrontee. L'ordre suit celui de la garde :
#: le nom de roue est verifie en premier, le tag en dernier. La cible n'est
#: donc ni toujours en tete ni toujours au milieu -- une comparaison sautee en
#: bout de garde se demasque.
DESACCORDS = {
    "nom-de-roue-inattendu": dict(nom_cli="mmu-cli-inattendu"),
    "deux-versions-differentes": dict(version_tui="0.2.0"),
    "epinglage-en-retard": dict(epinglage="mmu-cli==0.0.9"),
    "epinglage-absent": dict(epinglage=None),
    "epinglage-de-test-en-retard": dict(epinglage_test="mmu-cli-test==0.0.9"),
    # Chaque jeu est INTERNEMENT coherent -- meme version des deux cotes,
    # epinglage juste -- et le tag s'accorde a la production. SEULE la
    # comparaison des deux jeux entre eux peut voir l'ecart. Sans ce cas, la
    # supprimer restait sans effet mesurable : c'est le mutant N28, survivant
    # a la premiere campagne et tue par cette ligne.
    "les-deux-jeux-desaccordes": dict(version_test="0.3.0",
                                      epinglage_test="mmu-cli-test==0.3.0"),
    "tag-desaccorde": dict(),
}


@pytest.mark.parametrize("cas", sorted(DESACCORDS))
def test_la_garde_REFUSE_de_publier_sur_un_desaccord(tmp_path, cas):
    _fabrique_les_deux_jeux(tmp_path, **DESACCORDS[cas])
    tag = "v9.9.9" if cas == "tag-desaccorde" else "v0.1.0"
    resultat = _joue_la_garde(tmp_path, ref=tag)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, (
        f"le desaccord « {cas} » passe la garde :\n{sortie}"
    )
    assert "::error::" in sortie, sortie


def test_la_garde_REFUSE_un_paquet_de_test_qui_depend_de_la_PRODUCTION(tmp_path):
    """Frontiere NEGATIVE, prise du cote des artefacts et non des sources.

    Le renommage peut etre juste et la roue fausse -- un `force-include` mal
    place, une dependance calculee. Ce qui compte est ce qui part sur l'index.
    """
    _fabrique_les_deux_jeux(tmp_path,
                            exigences_test_en_plus=("mmu-cli==0.1.0",))
    resultat = _joue_la_garde(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "PRODUCTION" in sortie, sortie


def test_la_garde_exige_UNE_roue_de_la_DERNIERE_distribution(tmp_path):
    """Le cardinal de la ROUE, mesure la ou il compte : sur les huit artefacts.

    **Ce test visait `tui-test` et son SDIST jusqu'au 2026-09-07.** La dispense
    d'`EPIC8-ARB-18` avait fait disparaitre cette archive, et le test serait
    devenu vert en ne mesurant rien : il supprimait un fichier absent, puis
    constatait que la garde passe. Il a donc ete reporte sur la ROUE.

    `EPIC8-ARB-21` rend le sdist de l'interface a nouveau constructible, mais
    on ne remet pas ce test sur lui : le volet sdist est desormais mesure sur
    les QUATRE distributions par
    `test_la_garde_REFUSE_une_distribution_SANS_sdist`, et celui-ci garde la
    ROUE -- deux cardinaux distincts, deux frontieres distinctes. La cible
    reste en QUEUE de ce que la garde parcourt.
    """
    _fabrique_les_deux_jeux(tmp_path)
    for roue in (tmp_path / "dist" / "tui-test").glob("*.whl"):
        roue.unlink()
    resultat = _joue_la_garde(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "trouve 0 roue(s)" in sortie, sortie


def test_la_garde_compare_les_valeurs_internes_hors_tag(tmp_path):
    """Un declenchement manuel n'a pas de tag -- elle le DIT et mesure quand meme."""
    _fabrique_les_deux_jeux(tmp_path, version="0.3.0",
                            epinglage="mmu-cli==0.2.0",
                            epinglage_test="mmu-cli-test==0.3.0")
    resultat = _joue_la_garde(tmp_path, evenement="workflow_dispatch", ref="")
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, (
        "sans tag, la garde a laisse passer un epinglage en retard :\n" + sortie
    )
    assert "aucun tag a confronter" in sortie, sortie


#: Le plafond PAR FICHIER de PyPI et de TestPyPI, en octets.
PLAFOND_DE_L_INDEX = 100 * 1024 * 1024

#: Les SIX artefacts -- quatre roues et deux sdists depuis `EPIC8-ARB-18` --,
#: pour placer le fichier trop lourd en TETE, au milieu et
#: en QUEUE de ce que la garde parcourt. Un balayage tronque ne se demasque pas
#: autrement (CLAUDE.md, regle des fabriques, point 4).
ARTEFACTS = {
    "roue-du-coeur": ("cli", "*.whl"),
    "sdist-du-coeur": ("cli", "*.tar.gz"),
    "roue-de-l-interface": ("tui", "*.whl"),
    "sdist-de-l-interface": ("tui", "*.tar.gz"),
    "roue-du-coeur-de-test": ("cli-test", "*.whl"),
    "sdist-du-coeur-de-test": ("cli-test", "*.tar.gz"),
    "roue-de-l-interface-de-test": ("tui-test", "*.whl"),
    # La QUEUE de ce que la garde parcourt. Elle avait ete reportee sur la ROUE
    # de l'interface de test, dont le sdist n'existait plus (`EPIC8-ARB-18`) ;
    # `EPIC8-ARB-21` le rend, et le bord reprend sa place d'origine -- les deux
    # restent listes, un artefact hors plafond pouvant etre l'un ou l'autre.
    "sdist-de-l-interface-de-test": ("tui-test", "*.tar.gz"),
}


@pytest.mark.parametrize("trop_lourd", sorted(ARTEFACTS))
def test_la_garde_REFUSE_un_artefact_au_dela_du_plafond_de_l_index(tmp_path,
                                                                  trop_lourd):
    """PyPI refuse tout fichier de plus de 100 Mio, par un 400 apres coup.

    Le refuser ICI vaut mieux : sur une sequence a deux distributions et deux
    index, le 400 arriverait apres que l'autre paquet a DEJA ete accepte --
    une release a moitie publiee, exactement ce que la story ferme.

    Ce n'est PAS hypothetique. Mesure du 2026-09-07, `python -m build` joue sur
    l'arbre reel : `mmu_cli-0.1.0.tar.gz` pese **135,9 Mo**, dont 68,8 Mo de
    `tests/fixtures`, 47 Mo de `_bmad-output/` et un PDF de `docs/` a 26,6 Mo.
    Il serait refuse par l'index. La correction appartient a la declaration
    (story 8.5) ; ce qui appartient a la chaine, c'est de le NOMMER avant le
    televersement plutot qu'apres.
    """
    _fabrique_les_deux_jeux(tmp_path)
    dossier, motif = ARTEFACTS[trop_lourd]
    (cible,) = (tmp_path / "dist" / dossier).glob(motif)
    # Fichier CREUX : `stat` annonce la taille, le disque ne la paie pas.
    os.truncate(cible, PLAFOND_DE_L_INDEX + 1)

    resultat = _joue_la_garde(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, (
        f"« {trop_lourd} » depasse le plafond et la garde laisse passer :\n{sortie}"
    )
    assert cible.name in sortie and "100 Mio" in sortie, sortie


def test_la_borne_du_plafond_est_INCLUSIVE(tmp_path):
    """100 Mio pile n'est pas « au-dela » : la borne est une borne.

    Sans ce symetrique, une garde qui refuserait TOUT serait verte au test
    ci-dessus -- c'est la tautologie classique d'une frontiere de seuil.

    Ce qui est mesure ici est le MESSAGE, pas le code de sortie : allonger un
    fichier a la taille voulue le rend illisible comme archive, et la garde le
    dira -- a juste titre. Ce que la borne doit garantir, c'est qu'elle ne
    parle pas de plafond a 100 Mio pile.
    """
    _fabrique_les_deux_jeux(tmp_path)
    (cible,) = (tmp_path / "dist" / "cli").glob("*.tar.gz")
    os.truncate(cible, PLAFOND_DE_L_INDEX)
    sortie = _joue_la_garde(tmp_path).stdout
    assert "plafond" not in sortie, (
        "a 100 Mio pile, la garde parle deja de plafond : la borne est "
        f"exclusive alors qu'elle doit etre inclusive.\n{sortie}"
    )


#: Les distributions qui portent une archive source : LES QUATRE depuis
#: `EPIC8-ARB-21`. Elles etaient deux -- l'interface partait en ROUE SEULE, sa
#: sdist n'etant pas constructible --, et le bord de QUEUE de la regle des
#: fabriques devait alors etre emprunte a une autre famille. Il revient ici :
#: `tui-test` est le dernier des quatre dossiers que la garde parcourt, `cli`
#: le premier, et cette seule liste couvre desormais la tete, le milieu et la
#: queue (CLAUDE.md, regle des fabriques, point 4).
SDISTS = ["cli", "tui", "cli-test", "tui-test"]


@pytest.mark.parametrize("creux", SDISTS)
def test_la_garde_REFUSE_un_sdist_CREUX(tmp_path, creux):
    """Un sdist sans une ligne de code se televerse tres bien.

    Il ne se construit pas -- et ca ne se voit qu'a l'installation, chez
    l'utilisateur, longtemps apres la release. Mesure du 2026-09-07 sur
    l'arbre reel : le sdist de `mmu-tui` sortait a 20 Ko et SIX fichiers
    (pyproject, LICENSE, README, notices, .gitignore, PKG-INFO), parce que son
    `force-include` vise `../../src/`, qui n'entre pas dans le sdist. La roue
    n'etait meme pas construite : « Forced include not found ».
    """
    _fabrique_les_deux_jeux(tmp_path, sdist_creux=(creux,))
    resultat = _joue_la_garde(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, (
        f"le sdist creux de « {creux} » passe la garde :\n{sortie}"
    )
    assert "AUCUN fichier .py" in sortie, sortie
    assert "force-include" in sortie, sortie


#: Les distributions en roue seule : PLUS AUCUNE depuis `EPIC8-ARB-21`.
#:
#: La liste reste, VIDE, parce que la machinerie de dispense reste elle aussi :
#: `test_les_listes_de_PARAMETRISATION_couvrent_les_QUATRE_distributions` la
#: lit pour verifier que les deux listes partitionnent bien les quatre. Une
#: dispense future se pose en nommant ici la distribution ET dans le registre
#: du workflow -- la partition rougira tant que les deux ne s'accordent pas.
#:
#: AUCUN TEST N'EST PARAMETRE DESSUS, et c'est deliberé : une parametrisation
#: vide ne collecte rien et se tait, ce qui est la pire des issues -- une
#: mesure qui disparait sans rougir. Les deux familles qui l'employaient sont
#: rejouees sur une dispense REARMEE dans le script, pas sur cette liste.
ROUE_SEULE = []


def test_la_garde_REFUSE_un_sdist_EN_TROP_sur_une_dispense_REARMEE(tmp_path):
    """La dispense porte sur l'ABSENCE, jamais sur une tolerance.

    Cette mesure n'a plus de sujet dans l'arbre -- `EPIC8-ARB-21` a vide le
    registre --, et la SUPPRIMER laisserait la machinerie de dispense sans
    aucune garde : le jour ou quelqu'un renomme une distribution ici, un
    comptage tolerant (`len(sources) <= 1`) publierait `mmu-cli` sans archive
    source et la CI resterait VERTE.

    Elle se rejoue donc sur une dispense REARMEE dans le script joue, comme
    `test_le_REFUS_au_dela_de_la_borne_TOMBE_si_la_dispense_est_VIDE` le fait
    en sens inverse. Le mutant est applique au SCRIPT, jamais au fichier du
    depot.
    """
    garde = _script(_etape_nommee(_bloc_de_job("build"), "Garde de version"))
    assert "ROUE_SEULE = set()" in garde, (
        "le registre n'a plus la forme attendue : ce test ne sait plus "
        "l'armer")
    rearme = garde.replace("ROUE_SEULE = set()",
                           'ROUE_SEULE = {"mmu-tui"}', 1)

    # La fabrique produit les quatre sdists : celui de `tui` est donc EN TROP
    # au regard de la dispense qu'on vient d'armer.
    _fabrique_les_deux_jeux(tmp_path)
    resultat = _joue_la_garde(tmp_path, source=rearme,
                              nom="garde-dispense-rearmee.sh")
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, (
        f"un sdist en trop sur une distribution dispensee passe la garde :"
        f"\n{sortie}")
    assert "ROUE SEULE" in sortie, sortie
    assert "attendu UNE roue et 0 sdist" in sortie, sortie


@pytest.mark.parametrize("privee", SDISTS)
def test_la_garde_REFUSE_une_distribution_SANS_sdist(tmp_path, privee):
    """La frontiere qui empeche la roue seule de revenir en silence.

    C'est le remede evident et faux qu'`EPIC8-ARB-18` interdisait nommement :
    assouplir le comptage en `len(sources) <= 1` rendrait n'importe laquelle
    des quatre publiable sans archive source, et la CI resterait VERTE.
    Personne ne le verrait avant qu'un `pip install --no-binary` ne le
    decouvre chez l'utilisateur, longtemps apres la release.

    Il visait les deux distributions du COEUR jusqu'au 2026-09-10, l'interface
    etant alors dispensee. `EPIC8-ARB-21` l'etend aux quatre, donc a la TETE
    (`cli`) comme a la QUEUE (`tui-test`) de ce que la garde parcourt.
    """
    _fabrique_les_deux_jeux(tmp_path, sdist_manquant=(privee,))
    resultat = _joue_la_garde(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, (
        f"« {privee} » passe la garde sans archive source :\n{sortie}")
    assert "attendu UNE roue et 1 sdist" in sortie, sortie
    assert "n'est PAS dispensee" in sortie, sortie


@pytest.mark.parametrize("distribution", ["tui", "tui-test"])
def test_la_garde_REFUSE_DEUX_roues_sur_une_distribution(tmp_path,
                                                        distribution):
    """Le cardinal de la ROUE reste exige, dispense ou non.

    Sans lui, un dossier dont on a assoupli le comptage du sdist pourrait etre
    lu comme « plus compte du tout ». Deux roues, c'est deux versions du meme
    paquet dans le meme dossier : `gh-action-pypi-publish` televerse un
    DOSSIER, il les enverrait toutes les deux.

    Les cibles sont le MILIEU (`tui`) et la QUEUE (`tui-test`) de ce que la
    garde parcourt.
    """
    _fabrique_les_deux_jeux(tmp_path)
    dossier = tmp_path / "dist" / distribution
    (roue,) = dossier.glob("*.whl")
    (dossier / (roue.stem + "-doublon.whl")).write_bytes(roue.read_bytes())
    resultat = _joue_la_garde(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, (
        f"deux roues dans « {distribution} » passent la garde :\n{sortie}")
    assert "trouve 2 roue(s)" in sortie, sortie


#: Les quatre distributions, pour le cardinal de la ROUE. `ROUE_SEULE` seul ne
#: couvrait que les deux dispensees : le mutant `A` de la couche 1 --
#: `if (dispensee and len(roues) != 1) or ...` -- restait VERT sur 78/78,
#: parce qu'aucun banc ne fabriquait deux roues dans une distribution NON
#: dispensee. Le docstring du test voisin affirmait pourtant « exigee des
#: quatre distributions » : la mesure ne portait que sur la quatrieme.
TOUTES_LES_DISTRIBUTIONS = ["cli", "tui", "cli-test", "tui-test"]


@pytest.mark.parametrize("distribution", TOUTES_LES_DISTRIBUTIONS)
def test_le_cardinal_de_la_ROUE_est_exige_des_QUATRE_distributions(
        tmp_path, distribution):
    """AC3, le volet que `ROUE_SEULE` seul ne mesurait pas.

    Deux roues dans un dossier, c'est deux versions du meme paquet :
    `gh-action-pypi-publish` televerse le DOSSIER, il les enverrait toutes
    les deux. Le cas est aussi grave sur `mmu-cli` que sur `mmu-tui` -- et
    c'est precisement sur `mmu-cli` que rien ne le mesurait.
    """
    _fabrique_les_deux_jeux(tmp_path)
    dossier = tmp_path / "dist" / distribution
    (roue,) = dossier.glob("*.whl")
    (dossier / (roue.stem + "-doublon.whl")).write_bytes(roue.read_bytes())
    resultat = _joue_la_garde(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, (
        f"deux roues dans « {distribution} » passent la garde : "
        "les deux partiraient sur l'index.\n" + sortie)
    assert "trouve 2 roue(s)" in sortie, sortie


def test_le_registre_de_dispense_est_VIDE_et_sa_MACHINERIE_reste():
    """La dispense se lit dans le fichier, avec sa borne et son motif.

    Elle est VIDE depuis `EPIC8-ARB-21` : plus aucune distribution ne part en
    roue seule. Ce test mesure les deux moities de cet etat, et la seconde est
    la moins evidente.

    1. LE REGISTRE EST VIDE. Une distribution qui y reviendrait sans qu'on
       l'ait voulu -- un copier-coller, une reversion -- publierait sans
       archive source, et rien d'autre ne rougirait.
    2. LA MACHINERIE RESTE ECRITE : la borne, et les motifs qui expliquent
       pourquoi une dispense se pose. La retirer parce qu'elle ne sert plus
       ferait de la prochaine dispense un etat permanent -- exactement ce
       qu'`EPIC8-ARB-18` interdisait, et ce que la revue 8.9 avait deja
       trouve une fois sur cette meme borne.

    Ce test lit le SCRIPT DE GARDE, donc ce qui tourne, pas un commentaire pose
    a cote.
    """
    garde = _script(_etape_nommee(_bloc_de_job("build"), "Garde de version"))
    trouve = re.search(r"ROUE_SEULE\s*=\s*(set\(\)|\{([^}]*)\})", garde)
    assert trouve, ("le registre `ROUE_SEULE` n'est plus dans le script de "
                    "garde : la machinerie de dispense a disparu")
    nommees = set(re.findall(r'"([^"]+)"', trouve.group(2) or ""))
    assert not nommees, (
        f"le registre de dispense nomme a nouveau {sorted(nommees)}. Il est "
        "VIDE depuis EPIC8-ARB-21 : une distribution qui y revient est "
        "publiee SANS archive source, et aucune autre frontiere ne le dirait. "
        "Si la dispense est voulue, elle se pose avec sa borne et son "
        "arbitrage, et ce test se reprend dans le meme commit")

    assert re.search(r'BORNE_DE_LA_DISPENSE\s*=\s*"0\.1\.0"', garde), (
        "la borne de la dispense n'est plus ecrite : sans elle, la prochaine "
        "dispense cesse d'etre une dette et devient un etat")
    recolle = " ".join(garde.split())
    for motif in ("EPIC8-ARB-18", "EPIC8-ARB-21", "len(sources)"):
        assert motif in recolle, (
            f"le registre de dispense n'explique plus « {motif} » -- une "
            "dispense sans motif se perennise")


def test_la_construction_NOMME_la_panne_du_FORCE_INCLUDE():
    """La seconde panne mesuree le 2026-09-07, une fois les liens remplaces.

    Elle ne se lit pas dans son message brut : « Forced include not found:
    /tmp/src/mixed_media_utility/tui » designe un chemin de repertoire
    temporaire, pas la declaration fautive.
    """
    script = _script(_etape_nommee(_bloc_de_job("build"),
                                   "distributions de PRODUCTION"))
    # Le message tient sur plusieurs `echo` : on lit le texte RECOLLE, sinon
    # une phrase coupee en deux echapperait a la frontiere.
    recolle = " ".join(script.split())
    for attendu in ("Forced include not found", "hatch_build.py",
                    "src/mixed_media_utility/tui", "EMPLACEMENTS",
                    "Deux issues"):
        assert attendu in recolle, (
            f"l'echec de construction ne nomme pas « {attendu} »"
        )
    # LE VOLET NEGATIF A CHANGE DE SUJET, et le dire vaut mieux que le taire.
    # Il mesurait, depuis le finding `C1-4` / `C3-2` de la revue 8.9, que le
    # diagnostic ne proposait pas une manoeuvre sur le SDIST -- geste alors
    # sans effet, la commande passant par `--wheel` et n'en construisant aucun.
    # `EPIC8-ARB-21` rend le sdist a la construction : la manoeuvre est
    # redevenue un remede legitime, et l'interdire serait desormais faux.
    #
    # Le nouveau sujet TIENT, la ou une simple interdiction du chemin
    # `../../src` ne tiendrait pas : le diagnostic le NOMME legitimement, comme
    # l'un des deux emplacements que le crochet essaie. Ce qu'il ne doit pas
    # faire, c'est proposer `--wheel` -- le remede d'`EPIC8-ARB-18`, qui
    # retablirait la roue seule SANS arbitrage et sans qu'aucune autre
    # frontiere ne le dise, la garde de version se taisant sur un registre
    # qu'on n'a pas touche.
    assert "--wheel" not in recolle, (
        "le diagnostic propose `--wheel` : c'est le remede d'EPIC8-ARB-18, "
        "qui retablit la ROUE SEULE en silence. EPIC8-ARB-21 l'a ferme -- si "
        "la dispense doit revenir, elle se pose dans le registre avec sa "
        "borne, pas dans un message d'erreur")


def test_la_construction_NOMME_le_piege_des_LIENS_SYMBOLIQUES():
    """La panne des liens est HISTORIQUE, et le diagnostic doit le DIRE.

    Mesure du 2026-09-07 : `packaging/mmu-tui/` porte `LICENSE`, `README.md` et
    `THIRD-PARTY-NOTICES.md` en liens symboliques vers `../../`. `build`
    fabrique le sdist PUIS la roue DEPUIS ce sdist, et le filtre `data` de
    `tarfile` (PEP 706, Python 3.12+) refuse un lien qui sort de l'archive :
    `LinkOutsideDestinationError`. Le sdist sort (7 Ko), la ROUE n'est jamais
    construite -- et le message brut ne nomme ni la cause ni le remede.

    La correction appartient a la declaration (story 8.5). Ce qui appartient
    ici, c'est que l'echec soit LISIBLE : la frontiere mesure que le job dit
    quoi faire, pas seulement que quelque chose a casse.
    """
    script = _script(_etape_nommee(_bloc_de_job("build"),
                                   "distributions de PRODUCTION"))
    recolle = " ".join(script.split())
    for attendu in ("LinkOutsideDestinationError", "PANNES HISTORIQUES",
                    "atteignables ICI"):
        assert attendu in recolle, (
            f"l'echec de construction de mmu-tui ne nomme pas « {attendu} » : "
            "il rendrait un message de tarfile que personne ne sait lire."
        )
    # ET LE POINT QUE LA REVUE 8.9 A FAIT VALOIR : cette panne n'est plus
    # ATTEIGNABLE, ET ELLE L'EST A NOUVEAU. La revue 8.9 avait fait valoir
    # l'inverse : la panne passait par la construction du SDIST, que `--wheel`
    # ne faisait plus, et un diagnostic pour une panne impossible egare
    # l'operateur. `EPIC8-ARB-21` a retire `--wheel` -- le sdist se construit,
    # donc le filtre `data` de `tarfile` est a nouveau sur le chemin.
    #
    # La condition de retour du diagnostic s'inverse donc avec lui : la panne
    # est atteignable TANT QUE la construction ne passe PAS par `--wheel`.
    ligne = [l for l in script.splitlines()
             if "python -m build" in l and "packaging/mmu-tui" in l]
    assert ligne and "--wheel" not in ligne[0], (
        "la construction de mmu-tui est repassee par `--wheel` : le sdist "
        "n'est plus produit, la roue seule est de retour sans arbitrage, et ce "
        f"diagnostic annonce atteignable une panne qui ne l'est plus. Ligne "
        f"lue : {ligne}")
    # PIEGE REFERME par la story 8.5 le 2026-09-07 : les trois liens sont
    # devenus des fichiers reels, et le sdist du 2026-09-10 n'en porte AUCUN
    # (mesure : 65 entrees, zero lien). Cette frontiere ne mesure donc pas une
    # panne actuelle -- elle mesure que le job saura la NOMMER si elle revient,
    # ce qu'un lien repose en une commande. On ne retire pas un diagnostic
    # parce que la panne du jour est fermee : c'est le role d'une frontiere
    # negative.


# ---------------------------------------------------------------------------
# L'attente, EXECUTEE contre un index d'emprunt
# ---------------------------------------------------------------------------

#: Les deux attentes du workflow : une par index. Elles portent le meme
#: mecanisme et se mesurent toutes les deux -- une seule mesuree laisserait
#: l'autre libre de deriver.
ATTENTES = {
    "bac-a-sable": ("publish", "Attendre que mmu-cli-test", "mmu-cli-test",
                    "mmu_cli_test"),
    "production": ("release", "Attendre que mmu-cli soit", "mmu-cli", "mmu_cli"),
}


def _index_d_emprunt(tmp_path: Path, entrees: list[str]) -> dict[str, str]:
    """Un `curl` qui rend une page d'index fabriquee, et le PATH qui va avec."""
    faux_bin = tmp_path / "faux-bin"
    faux_bin.mkdir(exist_ok=True)
    page = tmp_path / "page-de-l-index.html"
    page.write_text(
        "<html><body>\n"
        + "\n".join(f'<a href="../../packages/{e}">{e}</a><br/>' for e in entrees)
        + "\n</body></html>\n",
        encoding="utf-8",
    )
    faux_curl = faux_bin / "curl"
    faux_curl.write_text(f'#!/bin/sh\ncat "{page}"\n', encoding="utf-8")
    faux_curl.chmod(faux_curl.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    environnement = dict(os.environ)
    environnement["PATH"] = f"{faux_bin}{os.pathsep}{environnement['PATH']}"
    return environnement


def _joue_l_attente(tmp_path: Path, attente: str, entrees: list[str], *,
                    version="0.1.0",
                    tentatives="3") -> subprocess.CompletedProcess:
    job, fragment, paquet, _ = ATTENTES[attente]
    script = tmp_path / "attendre.sh"
    script.write_text(_script(_etape_nommee(_bloc_de_job(job), fragment)),
                      encoding="utf-8")
    environnement = _index_d_emprunt(tmp_path, entrees)
    environnement.update({
        "PAQUET": paquet, "VERSION": version,
        "INDEX_SIMPLE": "https://index.d.emprunt/simple",
        "TENTATIVES": tentatives, "DELAI": "0",
    })
    return subprocess.run(["bash", str(script)], cwd=tmp_path, env=environnement,
                          capture_output=True, text=True, timeout=60)


def _page(prefixe: str, position: str) -> list[str]:
    """Quatre entrees DISTINGUABLES, la version visee placee ou l'on veut.

    Une lecture d'index tronquee -- qui ne regarderait que la premiere ou que
    la derniere ligne -- ne se demasque pas autrement (CLAUDE.md, regle des
    fabriques, points 2 et 4).
    """
    autres = [f"{prefixe}-0.0.7.tar.gz", f"{prefixe}-0.0.8.tar.gz",
              f"{prefixe}-0.0.9.tar.gz"]
    visee = f"{prefixe}-0.1.0.tar.gz"
    return {"en-tete": [visee] + autres,
            "au-milieu": autres[:1] + [visee] + autres[1:],
            "en-queue": autres + [visee]}[position]


@pytest.mark.parametrize("attente", sorted(ATTENTES))
@pytest.mark.parametrize("position", ["en-tete", "au-milieu", "en-queue"])
def test_l_attente_rend_la_main_des_que_la_version_VISEE_est_sur_l_index(
        tmp_path, attente, position):
    prefixe = ATTENTES[attente][3]
    resultat = _joue_l_attente(tmp_path, attente, _page(prefixe, position))
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode == 0, (
        f"version presente en {position} et l'attente ne la voit pas :\n{sortie}"
    )
    assert "resolvable" in sortie, sortie


@pytest.mark.parametrize("attente", sorted(ATTENTES))
def test_l_attente_ne_confond_pas_une_AUTRE_version_du_meme_paquet(tmp_path,
                                                                   attente):
    """Le paquet est la, la version non : c'est un echec, pas un succes.

    Trois autres versions du MEME paquet sont en ligne. Une lecture qui
    chercherait le nom du paquet plutot que le couple nom+version rendrait la
    main aussitot, et l'interface partirait sur un epinglage introuvable.
    """
    prefixe = ATTENTES[attente][3]
    resultat = _joue_l_attente(tmp_path, attente,
                               [f"{prefixe}-0.0.7.tar.gz",
                                f"{prefixe}-0.0.9.tar.gz",
                                f"{prefixe}-0.2.0.tar.gz"])
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "0.1.0" in sortie and ATTENTES[attente][2] in sortie, sortie


@pytest.mark.parametrize("attente", sorted(ATTENTES))
def test_l_attente_est_BORNEE_et_NOMME_son_echec(tmp_path, attente):
    """Bornee : elle finit. Nommee : on sait quoi relancer, et pourquoi.

    Le delai du `subprocess.run` est ce qui mesure la borne -- une boucle sans
    borne ne rend jamais la main et fait rougir ce test par delai depasse.
    """
    resultat = _joue_l_attente(tmp_path, attente, ["autre_paquet-9.9.9.tar.gz"],
                               tentatives="4")
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "::error::" in sortie, sortie
    for attendu in (ATTENTES[attente][2], "0.1.0", "index.d.emprunt",
                    "4 lectures", "ININSTALLABLE"):
        assert attendu in sortie, f"l'echec ne nomme pas « {attendu} » :\n{sortie}"
    assert sortie.count("lecture 1/4") == 1 and "lecture 4/4" in sortie, (
        "les lectures ne sont pas toutes jouees, ou la borne n'est pas celle "
        f"demandee :\n{sortie}"
    )


@pytest.mark.parametrize("attente", sorted(ATTENTES))
def test_l_attente_n_est_pas_un_sleep_a_l_aveugle(attente):
    """Frontiere NEGATIVE : un `sleep` sans lecture d'index reviendrait vite.

    Le `sleep` du corps de boucle est legitime -- c'est le pas entre deux
    lectures. Ce qui ne l'est pas, c'est un `sleep` qui remplacerait la lecture.
    """
    job, fragment, _, _ = ATTENTES[attente]
    script = _script(_etape_nommee(_bloc_de_job(job), fragment))
    assert "curl" in script, "l'attente n'interroge aucun index"
    assert "${INDEX_SIMPLE}" in script
    lignes_sleep = [l.strip() for l in script.splitlines()
                    if l.strip().startswith("sleep ")]
    assert len(lignes_sleep) == 1, (
        f"un seul `sleep` est admis, celui du pas de boucle : {lignes_sleep}"
    )
    assert "while" in script and "tentatives" in script


def test_chaque_attente_interroge_l_index_de_SA_PROPRE_cible():
    """Attendre sur le mauvais index, c'est ne rien attendre du tout.

    Une attente de production qui lirait TestPyPI rendrait la main tout de
    suite -- le paquet y est deja -- et publierait `mmu-tui` avant que
    `mmu-cli` soit resolvable sur PyPI.
    """
    attendus = {
        "bac-a-sable": ("https://test.pypi.org/simple", "mmu-cli-test"),
        "production": ("https://pypi.org/simple", "mmu-cli"),
    }
    for attente, (index, paquet) in attendus.items():
        job, fragment, _, _ = ATTENTES[attente]
        etape = _etape_nommee(_bloc_de_job(job), fragment)
        assert _valeur(etape, "INDEX_SIMPLE") == index, (
            f"l'attente « {attente} » lit {_valeur(etape, 'INDEX_SIMPLE')!r} "
            f"au lieu de {index!r}"
        )
        assert _valeur(etape, "PAQUET") == paquet


# ---------------------------------------------------------------------------
# Le slug du depot public
# ---------------------------------------------------------------------------

def _cles_du_fichier_env() -> dict[str, str]:
    cles = {}
    for ligne in ENV_DEPOT.read_text(encoding="utf-8").splitlines():
        depouillee = ligne.strip()
        if not depouillee or depouillee.startswith("#") or "=" not in depouillee:
            continue
        cle, valeur = depouillee.split("=", 1)
        cles[cle.strip()] = valeur.strip()
    return cles


def test_le_slug_public_est_RENSEIGNE_et_designe_le_depot_de_distribution():
    cles = _cles_du_fichier_env()
    assert cles.get("MMU_PUBLIC_REPO_SLUG") == DEPOT_PUBLIC, (
        "le slug public ne designe pas le depot de distribution : les URLs "
        "d'installation de la documentation pointeraient a cote, et le job "
        "`release` ne partirait jamais. Lu : "
        f"{cles.get('MMU_PUBLIC_REPO_SLUG')!r}"
    )


def test_les_deux_slugs_designent_DEUX_depots_differents():
    """Frontiere NEGATIVE, et le defaut qu'elle ferme etait en place.

    `MMU_PRIVATE_REPO_SLUG` valait `GanTiz/mixed_media_utility`, c'est-a-dire le
    nom que le depot PUBLIC porte depuis le 2026-09-06. Les deux cles auraient
    annonce le meme depot ; la garde de coherence de `ci.yml` aurait alors
    compare une valeur a elle-meme -- verte par construction --, et le job
    `release` serait parti depuis le depot de travail.
    """
    cles = _cles_du_fichier_env()
    assert cles.get("MMU_PRIVATE_REPO_SLUG") == DEPOT_TRAVAIL
    assert cles["MMU_PUBLIC_REPO_SLUG"] != cles["MMU_PRIVATE_REPO_SLUG"]
    assert "TBD" not in cles.values()


# -- `ci.yml` : le smoke test ne lance QUE ce que le job construit ------------
#
# Ce que cette frontiere ferme, et il a ete MESURE. La couche 1 de la revue 8.9
# a trouve, hors du diff mais adjacent, que le job `build` de `ci.yml`
# installait la roue `mmu-cli` puis lancait `mmu-tui --help` -- commande que
# cette distribution ne declare pas. Reproduit de bout en bout le 2026-09-07 :
# `python -m build` a la racine rend `mmu_cli-0.1.0-py3-none-any.whl`, dont
# l'`entry_points.txt` porte le seul `mmu = mixed_media_utility.cli:main` et
# qui contient ZERO module `tui/` ; installee dans un venv jetable,
# `mmu-tui --help` rend **127 command not found**.
#
# Le job se declenche sur `push: tags: ["v*"]`, LE MEME tag que `publish.yml` :
# il rougissait donc a coup sur sur la release. Le bloc datait de `d8cc7736`,
# ou il n'y avait qu'UNE distribution ; la scission d'`EPIC8-ARB-6` ne l'a pas
# porte. C'est le defaut « un module porte sans sa mesure », celui de
# `5635d70a`, et aucune frontiere ne le voyait.

#: L'argument que `python -m build` recoit, et le `pyproject.toml` qu'il lit.
#: Sans argument, `build` construit la RACINE.
PYPROJECT_PAR_CIBLE: dict[str, Path] = {
    "": RACINE / "pyproject.toml",
    ".": RACINE / "pyproject.toml",
    "packaging/mmu-tui": RACINE / "packaging" / "mmu-tui" / "pyproject.toml",
}


def _commandes_declarees(pyproject: Path) -> set[str]:
    """Les commandes que cette distribution POSE, lues dans son `pyproject`."""
    donnees = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return set(donnees.get("project", {}).get("scripts", {}))


def _cibles_construites(script: str) -> set[str]:
    """Les distributions qu'un script `run:` construit, par ses `python -m build`."""
    cibles: set[str] = set()
    for ligne in script.splitlines():
        nu = ligne.split("#", 1)[0].strip()
        if not re.match(r"^python(3)? -m build\b", nu):
            continue
        # Ce qui reste apres les options est le chemin ; rien = la racine.
        #
        # La VALEUR d'une option qui en prend une n'est pas un chemin, et le
        # confondre avec la cible a fait rougir cette frontiere le 2026-09-08,
        # quand `ci.yml` a gagne `--outdir dist .` : `dist` etait lu comme la
        # distribution construite. Seul `--outdir` est concerne aujourd'hui ;
        # la liste est nommee pour qu'une option a valeur ajoutee demain se
        # declare ici plutot que de decaler silencieusement la lecture.
        OPTIONS_A_VALEUR = {"-o", "--outdir"}
        mots = nu.split()[3:]
        arguments: list[str] = []
        saute = False
        for mot in mots:
            if saute:
                saute = False
                continue
            if mot in OPTIONS_A_VALEUR:
                saute = True
                continue
            if mot.startswith("-"):
                continue
            arguments.append(mot)
        cibles.add(arguments[0].rstrip("/") if arguments else "")
    return cibles


def test_toute_commande_SMOKE_TESTEE_par_ci_est_POSEE_par_une_roue_CONSTRUITE():
    """NEGATIVE. Le job ne lance pas une commande qu'il n'a pas installee.

    Les deux bouts sont LUS, jamais recopies ici : les commandes du produit
    viennent des `[project.scripts]` des deux `pyproject.toml`, et ce que le
    job construit vient de ses propres lignes `python -m build`. Declarer
    `mmu-tui` dans la mauvaise distribution, ou retirer la construction de
    `mmu-tui` en laissant le smoke test, fait rougir cette frontiere -- ce
    qu'une liste de commandes ecrite en dur dans le banc ne ferait pas.

    **Ce qu'elle NE couvre PAS, dit plutot que tu.** La reconnaissance par
    prefixe commun a une limite mesuree : renommer la commande de la RACINE
    (`mmu` -> autre chose) porte le prefixe commun a `mmu-`, et l'invocation
    `mmu` restee dans `ci.yml` cesse d'etre reconnue -- mutant `N5`, que
    cette frontiere laisse passer. Il est tue par
    :func:`test_le_renommage_mord_sur_les_DECLARATIONS_REELLES_du_depot`,
    donc le BANC le mesure, mais pas celle-ci. Le cas symetrique (`N4`, la
    TUI renommee) est bien attrape ici depuis le renforcement.
    """
    bloc = _bloc_de_job("build", CI)
    scripts = []
    for etape in _etapes(bloc):
        try:
            scripts.append(_script(etape))
        except AssertionError:
            continue  # une etape `uses:` ne porte pas de `run:`
    assert scripts, "le job `build` de ci.yml ne porte plus aucun `run:`"

    construites: set[str] = set()
    for script in scripts:
        construites |= _cibles_construites(script)
    assert construites, (
        "le job `build` ne lance plus aucun `python -m build` : la lecture "
        "est cassee, ou le job ne construit plus rien")

    inconnues = construites - set(PYPROJECT_PAR_CIBLE)
    assert not inconnues, (
        f"le job construit une cible que le banc ne sait pas lire : {inconnues}")

    posees: set[str] = set()
    for cible in construites:
        posees |= _commandes_declarees(PYPROJECT_PAR_CIBLE[cible])
    assert posees, "aucune commande posee : la lecture des pyproject est cassee"

    # Ce qui compte comme une invocation du produit. Reconnaitre les seules
    # commandes ACTUELLEMENT declarees serait une frontiere qui se desarme
    # toute seule : renommer `mmu-tui` dans son `pyproject` sortirait
    # l'invocation restee dans `ci.yml` du champ de la mesure, et le test
    # passerait au vert sur un job qui rend 127. Mesure du mutant `N4`, qui a
    # SURVECU a la premiere redaction de cette frontiere -- c'est le defaut
    # « vert en ne mesurant rien » que la revue 8.9 a trouve ailleurs, et il
    # etait ici aussi.
    #
    # On reconnait donc par le PREFIXE commun des commandes du produit, lui
    # aussi derive des `pyproject.toml` plutot qu'ecrit en dur.
    du_produit: set[str] = set()
    for pyproject in set(PYPROJECT_PAR_CIBLE.values()):
        du_produit |= _commandes_declarees(pyproject)

    prefixe = os.path.commonprefix(sorted(du_produit))
    assert len(prefixe) >= 3, (
        f"les commandes du produit {sorted(du_produit)} ne partagent plus de "
        f"prefixe utilisable ({prefixe!r}) : la reconnaissance des invocations "
        "attraperait `pip` ou `echo`, et cette frontiere crierait a tort")

    lancees: list[str] = []
    for script in scripts:
        for ligne in script.splitlines():
            jetons = ligne.split("#", 1)[0].strip().split()
            if jetons and jetons[0].startswith(prefixe):
                lancees.append(jetons[0])
    assert lancees, (
        "le job `build` ne lance AUCUNE commande du produit : le smoke test a "
        "disparu, et cette frontiere n'aurait plus rien a garder")

    absentes = sorted(set(lancees) - posees)
    assert not absentes, (
        "Le job `build` de `ci.yml` lance des commandes qu'aucune roue "
        f"construite ne pose : {absentes}\n"
        f"  construit : {sorted(construites) or ['(la racine seule)']}\n"
        f"  pose      : {sorted(posees)}\n"
        f"  lance     : {sorted(set(lancees))}\n"
        "Mesure du 2026-09-07 : `mmu-tui` lance contre la seule roue "
        "`mmu-cli` rend 127 command not found, sur le tag `v*` de la release.")


def test_le_banc_attrape_les_DEUX_sens_de_la_derive_du_smoke_test():
    """Le banc se prouve sur des scripts fabriques ici, sans toucher au depot.

    Les deux sens, parce que la derive va dans les deux : le job perd une
    construction en gardant l'invocation (ce qui est arrive), ou il gagne une
    invocation sans la construction. Une cible est placee a chaque BORD du
    script, la regle des fabriques de `CLAUDE.md` (point 4) voulant les deux.
    """
    racine_seule = _commandes_declarees(RACINE / "pyproject.toml")
    tui_seule = _commandes_declarees(
        RACINE / "packaging" / "mmu-tui" / "pyproject.toml")
    assert racine_seule and tui_seule and racine_seule != tui_seule, (
        "les deux distributions ne posent plus des commandes distinctes : la "
        "frontiere ne discriminerait plus rien")

    # La lecture des cibles, aux deux bords et au milieu.
    script = (
        "python -m build\n"                            # tete : la racine
        "pip install dist/*.whl\n"                     # milieu : sans effet
        "python -m build --wheel packaging/mmu-tui\n"  # queue : la TUI
    )
    assert _cibles_construites(script) == {"", "packaging/mmu-tui"}, (
        f"lecture des cibles cassee : {_cibles_construites(script)}")

    # Le sens REELLEMENT paye : construire la racine seule et lancer la TUI.
    construites = _cibles_construites("python -m build\n")
    posees: set[str] = set()
    for cible in construites:
        posees |= _commandes_declarees(PYPROJECT_PAR_CIBLE[cible])
    assert tui_seule - posees, (
        "la roue de la racine poserait les commandes de la TUI : la panne "
        "mesuree le 2026-09-07 serait devenue impossible, ce qui rendrait "
        "cette frontiere vide -- a verifier plutot qu'a supposer")


# -- la dispense EXPIRE, et c'est mesure sur le COMPORTEMENT ------------------
#
# Ce que ces frontieres ferment. Les TROIS couches de la revue 8.9 ont trouve,
# independamment et par trois sondes differentes, que `BORNE_DE_LA_DISPENSE`
# ne bornait RIEN : elle n'etait citee que dans le message d'ECHEC de la garde.
# Mesures des couches : jeu complet en 0.2.0 puis en 9.9.9, garde jouee,
# `returncode 0` et « Les quatre valeurs s'accordent » -- la dispense ne
# cessait jamais.
#
# Et la seule frontiere qui existait etait un `re.search` de la CHAINE
# « 0.1.0 » dans le script. Mutant mesure par la couche 1 : remplacer le
# litteral par « 99.0.0 » tuait ce test-la et AUCUN autre, parce qu'aucun
# comportement n'en dependait. C'est le test tautologique sur la constante
# centrale que la regle 5 de CLAUDE.md cite du precedent 5.9.
#
# Les frontieres ci-dessous mesurent le COMPORTEMENT : la garde est jouee, et
# c'est son verdict qui est lu. Le litteral peut encore etre lu ailleurs -- il
# n'est plus le seul temoin.

#: Les versions confrontees a la borne, et le verdict attendu de la garde.
#: Les trois positions comptent : SOUS la borne, A la borne exacte, et
#: AU-DELA -- juste au-dessus autant que tres au-dessus. Un `>=` fautif se
#: demasque sur « 0.1.0 », qu'il refuserait.
#:
#: Ce que cette table NE discrimine PAS, dit plutot que tu : l'ordre
#: LEXICOGRAPHIQUE rend ici les memes verdicts que l'ordre numerique. Avec une
#: borne en « 0.1.0 », « 0.0.9 » lui est inferieure et « 0.1.1 », « 0.2.0 »,
#: « 0.10.0 », « 9.9.9 » lui sont superieures dans les DEUX ordres -- verifie
#: caractere a caractere, et non suppose. Un remplacement de
#: `rang_de_version` par une comparaison de chaines SURVIVRAIT donc a cette
#: table. Il faudrait pour l'attraper une borne a deux chiffres (« 0.10.0 »
#: face a « 0.9.0 »), qui n'est pas la borne du depot : on ne fabrique pas un
#: cas que la garde ne connait pas pour se donner une couverture.
VERSIONS_FACE_A_LA_BORNE = [
    ("0.0.9", 0, "sous la borne"),
    ("0.1.0", 0, "la borne exacte -- un `>=` fautif la refuserait"),
    ("0.1.1", 1, "juste au-dela : le plus petit depassement possible"),
    ("0.2.0", 1, "le depassement mesure par la couche 2"),
    ("0.10.0", 1, "au-dela, et lexicographiquement INFERIEURE a 0.2.0"),
    ("9.9.9", 1, "le depassement mesure par la couche 1"),
]


@pytest.mark.parametrize("version,attendu,motif", VERSIONS_FACE_A_LA_BORNE,
                         ids=[v for v, _, _ in VERSIONS_FACE_A_LA_BORNE])
def test_la_dispense_de_sdist_EXPIRE_a_sa_borne(tmp_path, version, attendu, motif):
    """La garde REFUSE la roue seule au-dela de la borne. Comportement, pas chaine.

    `EPIC8-ARB-18` n'accorde pas la dispense seulement « nommee » : il
    l'accorde « bornee, ET elle se retire, elle ne se perennise pas ». L'AC4
    de la story n'avait retenu que la moitie nommante -- c'est le finding
    `C3-9` de la couche 3, qui a vu que le defaut etait dans l'AC et non dans
    le code livre.
    """
    # LA DISPENSE EST REARMEE DANS LE SCRIPT JOUE. Le registre du depot est
    # vide depuis `EPIC8-ARB-21`, donc la borne ne borne plus rien : jouee
    # telle quelle, cette famille passerait sur les six versions et ne
    # mesurerait plus l'expiration -- une frontiere verte qui ne mesure rien,
    # exactement ce que la revue 8.9 avait deja trouve sur cette borne.
    #
    # C'est la frontiere qui a REFUSE la release 0.1.1 le 2026-09-10 : elle se
    # garde armee, pour la prochaine dispense.
    garde = _script(_etape_nommee(_bloc_de_job("build"), "Garde de version"))
    assert "ROUE_SEULE = set()" in garde, (
        "le registre n'a plus la forme attendue : ce test ne sait plus l'armer")
    rearme = garde.replace("ROUE_SEULE = set()",
                           'ROUE_SEULE = {"mmu-tui", "mmu-tui-test"}', 1)
    _fabrique_les_deux_jeux(
        tmp_path, version=version,
        epinglage=f"mmu-cli=={version}",
        epinglage_test=f"mmu-cli-test=={version}{SUFFIXE_DU_BAC_A_SABLE}",
        sdist_manquant=("tui", "tui-test"))
    resultat = _joue_la_garde(tmp_path, ref=f"v{version}", source=rearme,
                              nom=f"garde-borne-{version}.sh")
    sortie = resultat.stdout + resultat.stderr

    assert (resultat.returncode != 0) == bool(attendu), (
        f"version {version} ({motif}) : la garde rend "
        f"{resultat.returncode}, attendu "
        f"{'un refus' if attendu else 'un passage'}.\n{sortie}")

    if attendu:
        # Le refus doit venir de LA BORNE, pas d'un desaccord fabrique par
        # megarde : sans ce volet, le test serait vert sur n'importe quelle
        # autre panne de la garde.
        assert "borne" in sortie, (
            f"version {version} : la garde refuse, mais pas au titre de la "
            f"borne de la dispense -- le refus vient d'ailleurs.\n{sortie}")
        assert "ROUE SEULE" in sortie or "roue seule" in sortie.lower(), (
            f"version {version} : le refus ne nomme pas la roue seule.\n{sortie}")


def _version_du_depot() -> str:
    """La version que CE depot publierait, lue a sa source unique."""
    fichier = RACINE / "src" / "mixed_media_utility" / "__init__.py"
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("__version__"):
            return ligne.split("=", 1)[1].strip().strip("\"'")
    raise AssertionError(f"aucun `__version__` en colonne zero dans {fichier}")


def test_la_version_DU_DEPOT_passe_la_garde_de_publication(tmp_path):
    """LA FRONTIERE QUI MANQUAIT, et son absence a coute la release 0.1.1.

    Ce que le 2026-09-10 a mesure. `test_la_dispense_de_sdist_EXPIRE_a_sa_borne`
    portait deja, en toutes lettres, le cas « 0.1.1 -> refus », et il etait
    VERT. Le tag `v0.1.1` a ete pose, `publish.yml` a joue 38 minutes de tests
    verts, et le job `build` a refuse -- exactement ce que ce banc annoncait.
    Personne n'avait rapproche « on publie 0.1.1 » de « le banc dit que 0.1.1
    est refusee ».

    Le defaut n'etait donc PAS dans la garde, ni dans le banc : il etait dans
    le fait qu'aucune mesure ne confrontait la garde a la version que le depot
    s'apprete reellement a publier. Une table de versions parametree mesure un
    COMPORTEMENT ; elle ne dit rien de l'ETAT du depot. Les deux sont
    necessaires, et c'est le second qui manquait.

    CE QU'IL MESURE, dit precisement : que la garde de version laisse passer un
    jeu d'artefacts nominal construit a la version du depot, tag compris. Il
    tourne du cote PRIVE, sur une branche, avant tout tag -- la ou une release
    n'a encore rien coute.

    CE QU'IL NE MESURE PAS, dit plutot que tu, et le temoin de vivacite l'a
    rendu visible. Il ne joue pas la chaine, ne construit aucune vraie roue et
    ne touche aucun index : un refus venu d'un autre job -- TestPyPI qui
    connait deja la version, la garde d'installation, l'approbation -- lui
    reste invisible. Il ferme la classe de defaut qui a mordu ici, pas toutes
    celles d'une release.

    Et la FABRIQUE MODELISE les artefacts, elle ne les OBSERVE pas. Rejoue sur
    l'arbre du 2026-09-10, ce banc rougit bien -- mais par le comptage des
    artefacts, pas par la borne, parce que la fabrique produit desormais un
    sdist la ou la construction d'alors n'en produisait aucun. Le verdict est
    bon, le chemin differe. Ce qui tient les deux ensemble n'est pas ce
    banc-ci : ce sont `test_AUCUNE_distribution_ne_se_construit_en_ROUE_SEULE`
    et `test_le_registre_de_dispense_est_VIDE_et_sa_MACHINERIE_reste`, qui
    rougissent des que la construction reelle et le registre divergent du
    modele.
    """
    version = _version_du_depot()
    _fabrique_les_deux_jeux(
        tmp_path, version=version,
        epinglage=f"mmu-cli=={version}",
        epinglage_test=f"mmu-cli-test=={version}{SUFFIXE_DU_BAC_A_SABLE}")
    resultat = _joue_la_garde(tmp_path, ref=f"v{version}")
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode == 0, (
        f"LA VERSION {version} DE CE DEPOT NE PASSERAIT PAS la garde de "
        f"publication : poser le tag `v{version}` ferait echouer la release "
        f"apres les tests, comme le 2026-09-10. Le motif est ci-dessous, et il "
        f"se corrige ICI, avant tout tag.\n{sortie}")
    assert f"s'accordent sur {version}" in sortie, (
        "la garde passe, mais sans se prononcer sur la version du depot : "
        f"ce banc serait vert sans rien mesurer.\n{sortie}")


def test_le_REFUS_au_dela_de_la_borne_TOMBE_si_la_dispense_est_VIDE(tmp_path):
    """NEGATIVE. Sans dispense, la borne n'a rien a borner -- et se tait.

    C'est ce qui fait de la borne une DETTE et non un plafond de version. Le
    jour redoute par la premiere redaction de ce test est ARRIVE le
    2026-09-10 : `mmu-tui` produit un sdist exploitable (`EPIC8-ARB-21`) et est
    sorti de `ROUE_SEULE`. Une garde qui refuserait encore aurait transforme la
    dispense en interdit permanent -- l'inverse exact de ce qu'`EPIC8-ARB-18`
    demandait.

    IL NE MUTE DONC PLUS RIEN : le registre du depot EST vide, et ce test joue
    la garde telle quelle. Il mesure l'etat nominal, pas une hypothese -- ce
    qui le rend plus fort qu'avant, pas moins. Son symetrique, celui qui garde
    la machinerie armee, est
    `test_la_dispense_de_sdist_EXPIRE_a_sa_borne`.
    """
    garde = _script(_etape_nommee(_bloc_de_job("build"), "Garde de version"))
    assert "ROUE_SEULE = set()" in garde, (
        "le registre de dispense n'est plus vide : une distribution y est "
        "revenue, et ce test ne mesure plus l'etat nominal du depot")

    # Registre vide => les quatre distributions gardent leur sdist, et une
    # version tres au-dela de la borne doit passer.
    _fabrique_les_deux_jeux(
        tmp_path, version="0.2.0",
        epinglage="mmu-cli==0.2.0",
        epinglage_test=f"mmu-cli-test==0.2.0{SUFFIXE_DU_BAC_A_SABLE}")
    resultat = _joue_la_garde(tmp_path, ref="v0.2.0")
    assert resultat.returncode == 0, (
        "sans dispense, une 0.2.0 doit passer : la borne s'est transformee en "
        "plafond de version permanent.\n" + resultat.stdout + resultat.stderr)


# -- la ROUE se lit, comme le sdist ------------------------------------------

#: Les quatre distributions, DANS L'ORDRE ou la garde les parcourt. La
#: parametrisation couvre donc les deux BORDS -- `cli` en tete, `tui-test` en
#: queue -- ce que la regle des fabriques de `CLAUDE.md` (point 4) exige : une
#: cible au milieu demasque un `find` fautif, pas un balayage tronque.
ROUES_A_CREUSER = ["cli", "tui", "cli-test", "tui-test"]


@pytest.mark.parametrize("distribution", ROUES_A_CREUSER)
def test_la_garde_REFUSE_une_roue_SANS_UN_SEUL_MODULE(tmp_path, distribution):
    """Le symetrique de `sdist_non_creux`, et il MANQUAIT.

    Tant que `mmu-tui` produisait un sdist, une coquille se voyait la. Depuis
    qu'`EPIC8-ARB-18` la publie en ROUE SEULE, la roue est le SEUL artefact de
    l'interface, et plus rien n'en lisait le contenu : la couche 1 de la revue
    8.9 a mesure que les quatre roues du banc ne portaient que `METADATA` et
    que la garde rendait 0.

    C'est la distribution dont le contenu est le plus fragile -- il vient d'un
    `force-include` qui vise hors de la racine du paquet, et qui ne crie pas
    quand il ne trouve rien : il produit une roue valide et vide.
    """
    _fabrique_les_deux_jeux(tmp_path, roues_creuses=(distribution,))
    resultat = _joue_la_garde(tmp_path)
    sortie = resultat.stdout + resultat.stderr

    assert resultat.returncode != 0, (
        f"une roue creuse dans `dist/{distribution}` passe la garde : elle "
        "s'installerait sans erreur et ne poserait aucune commande.\n" + sortie)
    assert "AUCUN module" in sortie, (
        f"la garde refuse `dist/{distribution}`, mais pas au titre de la roue "
        f"creuse -- le refus vient d'ailleurs.\n{sortie}")


def test_le_controle_de_roue_creuse_IGNORE_les_py_des_METADONNEES(tmp_path):
    """NEGATIVE. Un `.py` dans `.dist-info/` ne sauve pas une coquille.

    Sans cette exclusion, il suffirait qu'un outil de construction depose un
    fichier `.py` dans les metadonnees pour que toute roue vide passe. Le
    controle serait alors vert sur exactement ce qu'il existe pour refuser.
    """
    _fabrique_les_deux_jeux(tmp_path, roues_creuses=("tui",))
    roue = next((tmp_path / "dist" / "tui").glob("*.whl"))
    # On AJOUTE un `.py`, mais dans les metadonnees : la roue reste creuse.
    with zipfile.ZipFile(roue, "a") as archive:
        archive.writestr("mmu_tui-0.1.0.dist-info/faux_module.py", "x = 1\n")

    resultat = _joue_la_garde(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, (
        "un `.py` depose dans `.dist-info/` a suffi a faire passer une roue "
        "creuse : le controle compte les mauvais fichiers.\n" + sortie)
    assert "AUCUN module" in sortie, sortie


def test_les_roues_PLEINES_du_banc_passent_la_garde(tmp_path):
    """Le volet POSITIF : sans lui, les trois frontieres ci-dessus seraient
    vertes sur une garde qui refuserait TOUTE roue.

    C'est le meme piege que la couche 3 a trouve sur un test reecrit de cette
    story : une frontiere peut passer au vert en ne mesurant plus rien.
    """
    _fabrique_les_deux_jeux(tmp_path)
    resultat = _joue_la_garde(tmp_path)
    assert resultat.returncode == 0, (
        "les roues PLEINES du banc sont refusees : le controle de coquille "
        "mord sur des artefacts corrects.\n" + resultat.stdout + resultat.stderr)
    # Et la fabrique produit bien ce qu'elle annonce, verifie plutot que suppose.
    for distribution in ROUES_A_CREUSER:
        roue = next((tmp_path / "dist" / distribution).glob("*.whl"))
        with zipfile.ZipFile(roue) as archive:
            modules = [n for n in archive.namelist()
                       if n.endswith(".py") and ".dist-info/" not in n]
        assert len(modules) >= 2, (
            f"la roue de `{distribution}` ne porte que {modules} : une fabrique "
            "de collection produit au moins DEUX elements distinguables")


# -- les listes de parametrisation couvrent tout, et c'est MESURE -------------

#: Les quatre distributions que la chaine publie, en un seul endroit.
DISTRIBUTIONS_DU_DEPOT = {"cli", "tui", "cli-test", "tui-test"}


def test_les_listes_de_PARAMETRISATION_couvrent_les_QUATRE_distributions():
    """Ce banc mesure ses propres bords, parce que rien d'autre ne le fait.

    Ce que cette frontiere ferme, et c'est la couche 2 qui l'a mesure. Le bord
    de QUEUE de la regle des fabriques a ete DEPLACE par cette story : il etait
    tenu par le sdist de l'interface de test, qui n'existe plus, et c'est sa
    ROUE qui a pris la place. Le deplacement est bon -- verifie. Mais rien ne
    le tenait : le mutant `M-QUEUE` retirait `tui-test` des TROIS listes a la
    fois (`ROUE_SEULE`, `SDISTS`, `ARTEFACTS`) et rendait **74 passed, 0
    failed**. La derniere des quatre distributions sortait de toute mesure sans
    un rouge, alors que la garde INVITE nommement a retirer la dispense un jour.

    Les cardinaux sont DERIVES, jamais ecrits en dur : le nombre d'artefacts
    parcourus est « une roue par distribution, plus un sdist par distribution
    non dispensee ». Un compteur recopie se perime -- l'en-tete de ce banc
    annoncait « huit artefacts » devant six.
    """
    couvertes = set(SDISTS) | set(ROUE_SEULE)
    assert couvertes == DISTRIBUTIONS_DU_DEPOT, (
        "les deux listes de parametrisation ne couvrent plus les quatre "
        f"distributions : {sorted(couvertes)} au lieu de "
        f"{sorted(DISTRIBUTIONS_DU_DEPOT)}. Une distribution absente des deux "
        "sort de toute mesure sans faire rougir quoi que ce soit")

    chevauchement = set(SDISTS) & set(ROUE_SEULE)
    assert not chevauchement, (
        f"{sorted(chevauchement)} figure a la fois parmi les distributions qui "
        "gardent leur sdist et parmi les dispensees : les deux listes se "
        "contredisent, et les tests qui les lisent mesurent des choses opposees")

    dossiers = {dossier for dossier, _ in ARTEFACTS.values()}
    assert dossiers == DISTRIBUTIONS_DU_DEPOT, (
        f"le balayage du poids ne visite plus que {sorted(dossiers)} : une "
        "distribution absente peut porter un artefact hors plafond sans que "
        "rien ne le voie")

    # Le cardinal, DERIVE : une roue par distribution, plus un sdist par
    # distribution non dispensee.
    attendu = len(DISTRIBUTIONS_DU_DEPOT) + len(SDISTS)
    assert len(ARTEFACTS) == attendu, (
        f"`ARTEFACTS` porte {len(ARTEFACTS)} entrees pour {attendu} artefacts "
        f"reellement parcourus ({len(DISTRIBUTIONS_DU_DEPOT)} roues + "
        f"{len(SDISTS)} sdists) : le balayage du poids en laisse passer, ou "
        "en cherche qui n'existent pas")

    # Et les deux BORDS sont bien occupes, sans quoi « tete » et « queue »
    # seraient des mots plutot que des positions.
    ordre = sorted(ARTEFACTS)
    assert ARTEFACTS[ordre[0]][0] in DISTRIBUTIONS_DU_DEPOT
    assert ARTEFACTS[ordre[-1]][0] in DISTRIBUTIONS_DU_DEPOT


# -- le message de la garde designe LA BONNE panne ---------------------------

@pytest.mark.parametrize("distribution", ["cli", "tui", "cli-test", "tui-test"])
def test_quand_la_ROUE_manque_le_message_ne_parle_PAS_du_sdist(tmp_path,
                                                               distribution):
    """La panne du `force-include` est une roue ABSENTE. Le message doit le dire.

    Ce que cette frontiere ferme, mesure par la couche 2 : le message branchait
    sur `dispensee`, pas sur le cardinal fautif. Retirer la roue de `dist/tui`
    -- c'est-a-dire reproduire la panne meme pour laquelle `--wheel` existe --
    imprimait « trouve 0 roue(s) et 0 sdist(s) » suivi de trois lignes sur la
    declaration du sdist. L'operateur part sur la mauvaise piste, de nuit, un
    soir de release.
    """
    _fabrique_les_deux_jeux(tmp_path)
    roue = next((tmp_path / "dist" / distribution).glob("*.whl"))
    roue.unlink()

    resultat = _joue_la_garde(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, (
        f"une distribution SANS roue passe la garde :\n{sortie}")
    assert "C'est la ROUE qui manque" in sortie, (
        f"la roue de `{distribution}` manque et le message ne le dit pas :\n"
        + sortie)
    # Le volet NEGATIF, qui est le finding lui-meme : le message ne doit pas
    # expliquer une panne de sdist quand c'est la roue qui manque.
    assert "ne produit pas\nd'archive source" not in sortie, sortie
    assert "Un sdist trouve ici" not in sortie, (
        f"la roue de `{distribution}` manque, et le message explique quand "
        f"meme la declaration du sdist :\n{sortie}")


def test_quand_le_SDIST_est_en_trop_le_message_parle_BIEN_du_sdist(tmp_path):
    """Le volet symetrique : la bonne explication reste servie quand elle vaut.

    Sans lui, la frontiere ci-dessus serait verte sur une garde qui aurait
    perdu l'explication du sdist -- verte en ne mesurant plus rien, exactement
    le piege que la couche 3 a trouve ailleurs dans cette story.
    """
    # Comme `test_la_garde_REFUSE_un_sdist_EN_TROP_sur_une_dispense_REARMEE`,
    # cette explication n'a plus de sujet dans l'arbre : elle se mesure sur une
    # dispense armee dans le SCRIPT joue. La retirer laisserait la frontiere
    # ci-dessus verte sur une garde qui aurait perdu l'explication du sdist.
    garde = _script(_etape_nommee(_bloc_de_job("build"), "Garde de version"))
    assert "ROUE_SEULE = set()" in garde, (
        "le registre n'a plus la forme attendue : ce test ne sait plus l'armer")
    rearme = garde.replace("ROUE_SEULE = set()", 'ROUE_SEULE = {"mmu-tui"}', 1)

    _fabrique_les_deux_jeux(tmp_path)
    resultat = _joue_la_garde(tmp_path, source=rearme,
                              nom="garde-message-sdist.sh")
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "Un sdist trouve ici" in sortie, (
        "un sdist EN TROP sur une distribution dispensee, et le message ne "
        f"l'explique plus :\n{sortie}")
    assert "C'est la ROUE qui manque" not in sortie, sortie


# ==========================================================================
#  LA PORTE NE SE FRANCHIT PAS EN SAUTANT -- un job SAUTE n'est pas un job VERT
# ==========================================================================
# Ce que ce bloc ferme, et il a ete trouve sur une question d'Egan du
# 2026-09-09 (« rien ne bloque la publication sur PyPI, et meme sur TestPyPI,
# si les tests echouent -- c'est un peu bete non ? »).
#
# La chaine `valider -> build -> publish -> release` existait et etait juste :
# `needs:` bloque sur un echec. Mais elle ne dit rien d'un job **SAUTE**, et
# c'est par la que ca passait :
#
#   * `workflow_call:` de `ci.yml` ne declare AUCUNE entree, donc `inputs.lot`
#     y vaut la chaine VIDE ;
#   * `github.event_name`, lui, est celui de l'APPELANT.
#
# Sur un tag `v*` l'appelant est un `push`, la premiere clause suffit, les
# tests jouent. Sur un `workflow_dispatch` de `publish.yml` -- la repetition
# TestPyPI depuis `-dev` -- `event_name` vaut `workflow_dispatch` et
# `inputs.lot` est vide : `test` et `build` etaient SAUTES, `valider` rendait
# vert sans avoir joue un test, et `publish` televersait derriere.
#
# Un `needs:` ne rattrape pas ca : GitHub considere un job saute comme
# satisfait. C'est pourquoi la mesure porte sur la CONDITION, pas sur le
# graphe -- le graphe etait deja bon.

CI = RACINE / ".github" / "workflows" / "ci.yml"

#: Les deux regimes sous lesquels `publish.yml` appelle `ci.yml`, et sous
#: lesquels AUCUN job ne doit etre saute. Le second est celui qui mordait.
APPELS_DE_LA_PORTE = (
    ("push", ""),                # un tag `v*` : release de production
    ("workflow_dispatch", ""),   # la repetition TestPyPI depuis `-dev`
)


def _conditions_des_jobs_de_ci() -> dict[str, str]:
    """Le `if:` de chaque job de `ci.yml`, lu a plat.

    Volontairement textuel plutot que par `yaml.safe_load` : c'est
    l'EXPRESSION qu'on veut evaluer, et un chargeur YAML la rendrait
    identique -- mais ce banc doit rester lisible par un agent qui n'a pas
    PyYAML sous la main.
    """
    conditions: dict[str, str] = {}
    lignes = CI.read_text(encoding="utf-8").splitlines()
    job_courant = None
    for indice, ligne in enumerate(lignes):
        if re.fullmatch(r"  [a-z][a-z0-9-]*:", ligne):
            job_courant = ligne.strip().rstrip(":")
        elif job_courant and re.fullmatch(r"    if: >-", ligne):
            corps = []
            for suite in lignes[indice + 1:]:
                if suite.strip() and _indentation(suite) <= 4:
                    break
                corps.append(suite.strip())
            conditions[job_courant] = " ".join(corps)
    return conditions


def _evalue(expression: str, event_name: str, lot: str) -> bool:
    """Evalue une expression GitHub de la forme `${{ A || B || ... }}`.

    Elle ne connait que ce que ces conditions-la emploient : `||`, `==`, `!=`,
    les litteraux `'...'` et `null`, et les deux contextes `github.event_name`
    et `inputs.lot`. Une forme inconnue leve plutot que de rendre un verdict
    faux -- une frontiere qui devine est pire qu'une frontiere absente.
    """
    corps = expression.strip()
    if not (corps.startswith("${{") and corps.endswith("}}")):
        raise AssertionError(f"expression non reconnue : {expression}")
    corps = corps[3:-2].strip()

    contextes = {"github.event_name": event_name, "inputs.lot": lot}
    for terme in corps.split("||"):
        terme = terme.strip().strip("()").strip()
        trouve = re.fullmatch(
            r"(github\.event_name|inputs\.lot)\s*(==|!=)\s*('([^']*)'|null)",
            terme)
        if not trouve:
            raise AssertionError(f"terme non reconnu : {terme!r}")
        gauche = contextes[trouve.group(1)]
        droite = "" if trouve.group(3) == "null" else trouve.group(4)
        if (gauche == droite) if trouve.group(2) == "==" else (gauche != droite):
            return True
    return False


def test_l_evaluateur_du_banc_est_LUI_MEME_mesure():
    """Une frontiere batie sur un evaluateur faux ne mesure rien.

    Les deux sens, sur une expression ecrite ici -- jamais celle du produit,
    qui est ce qu'on cherche a juger.
    """
    forme = "${{ (github.event_name != 'workflow_dispatch') || (inputs.lot == 'tout') }}"
    assert _evalue(forme, "push", "") is True
    assert _evalue(forme, "workflow_dispatch", "tout") is True
    assert _evalue(forme, "workflow_dispatch", "") is False
    with pytest.raises(AssertionError):
        _evalue("${{ github.actor == 'x' }}", "push", "")


@pytest.mark.parametrize("job", sorted(_conditions_des_jobs_de_ci()))
@pytest.mark.parametrize("event_name,lot", APPELS_DE_LA_PORTE)
def test_AUCUN_job_de_ci_n_est_SAUTE_quand_la_PORTE_de_release_l_appelle(
        job, event_name, lot):
    condition = _conditions_des_jobs_de_ci()[job]
    assert _evalue(condition, event_name, lot), (
        f"le job `{job}` de ci.yml est SAUTE quand publish.yml l'appelle "
        f"(event_name={event_name!r}, inputs.lot={lot!r}). Un job saute ne "
        f"fait pas echouer son appelant : la porte de release rendrait vert "
        f"sans l'avoir joue.\n  condition : {condition}")


@pytest.mark.parametrize("lot,doit_jouer", [
    ("tout", True),
    ("tests", True),
    ("garde-installation", False),
])
def test_le_CHOIX_DE_LOT_continue_de_jouer_sur_un_declenchement_MANUEL(
        lot, doit_jouer):
    """La symetrie POSITIVE du test precedent, et elle n'est pas decorative.

    Sans elle, la frontiere ci-dessus serait vraie d'un `ci.yml` dont on
    aurait simplement RETIRE tout `if:` -- c'est-a-dire d'un produit qui aurait
    perdu le choix de lot, celui qui evite de repayer trois matrices de tests
    pour verifier une correction d'une ligne dans la garde d'installation.
    """
    condition = _conditions_des_jobs_de_ci()["test"]
    assert _evalue(condition, "workflow_dispatch", lot) is doit_jouer


# ==========================================================================
#  LE RANG DE TENTATIVE DU BAC A SABLE -- ce qui rend une republication possible
# ==========================================================================
# CE QUE CE BLOC FERME, ET IL A ETE PAYE SUR UNE RELEASE REELLE (2026-09-09).
#
# TestPyPI a refuse `mmu_cli_test-0.1.0` avec un 400 : « This filename was
# previously used by a file that has since been deleted. Use a different
# version. » Deux faits s'y combinent, et aucun des deux n'etait dans le
# depot :
#
#   * un index REFUSE un nom de fichier deja employe ;
#   * SUPPRIMER la release ne libere pas ce nom -- ca le BRULE.
#
# Republier une meme version y etait donc impossible A JAMAIS, et la chaine de
# release entiere avec elle. L'exigence d'egalite stricte entre les deux jeux,
# juste sur le fond, rendait cet etat irrattrapable.
#
# Le remede n'est pas un menage a refaire a chaque fois : c'est un suffixe
# `.postN` propre a la TENTATIVE, qui rend le nom de fichier neuf par
# construction. Ce bloc mesure les deux moities -- que le renommage le POSE, et
# que la garde ne tolere QUE lui.


def _version_du_bac_a_sable(racine: Path, run: int, tentative: int) -> str:
    """Joue le renommage avec un couple (run, tentative) donne, rend la version."""
    racine.mkdir(parents=True, exist_ok=True)
    _fabrique_les_deux_declarations(racine)
    script = racine / "renommer.sh"
    script.write_text(
        _script(_etape_nommee(_bloc_de_job("build"), "Renommer les deux")),
        encoding="utf-8")
    environnement = dict(os.environ)
    environnement.update({"GITHUB_RUN_NUMBER": str(run),
                          "GITHUB_RUN_ATTEMPT": str(tentative)})
    rendu = subprocess.run(["bash", str(script)], cwd=racine, env=environnement,
                           capture_output=True, text=True, timeout=60)
    assert rendu.returncode == 0, rendu.stdout + rendu.stderr
    texte = (racine / "src" / "mixed_media_utility" / "__init__.py").read_text(
        encoding="utf-8")
    trouve = re.search(r'__version__ = "([^"]+)"', texte)
    assert trouve, texte
    return trouve.group(1)


def test_un_REJEU_ne_rend_PAS_le_meme_nom_de_fichier(tmp_path):
    """LA frontiere du bloc, et celle qui a failli manquer.

    Un rejeu garde le MEME numero de run et n'incremente que la tentative. Un
    rang derive du seul numero rendrait donc deux fois le meme nom -- et le
    deuxieme rejeu se ferait refuser exactement comme la release du
    2026-09-09. Le defaut serait invisible tant qu'on ne rejoue pas.
    """
    premiere = _version_du_bac_a_sable(tmp_path / "a", 12, 1)
    seconde = _version_du_bac_a_sable(tmp_path / "b", 12, 2)
    assert premiere != seconde, (
        f"deux tentatives du MEME run rendent {premiere!r} : le nom de fichier "
        "serait rejoue, et l'index le refuserait.")


def test_le_rang_est_une_MULTIPLICATION_et_pas_une_concatenation(tmp_path):
    """« run 5, tentative 11 » et « run 51, tentative 1 » ne se confondent pas.

    Une concatenation rendrait `511` des deux cotes. C'est le seul cas ou les
    deux formules divergent, donc le seul qui les distingue -- et il n'est pas
    theorique : onze tentatives sur un run de release, c'est une journee comme
    celle du 2026-09-09.
    """
    assert (_version_du_bac_a_sable(tmp_path / "a", 5, 11)
            != _version_du_bac_a_sable(tmp_path / "b", 51, 1))


def test_le_jeu_de_PRODUCTION_ne_recoit_PAS_le_rang(tmp_path):
    """Frontiere NEGATIVE : le suffixe est au bac a sable, et a lui seul.

    Si le rang atteignait la production, PyPI recevrait `mmu-cli 0.1.0.postN`
    au lieu de `0.1.0` -- une version que le tag ne designe pas, et que
    personne n'a demandee. Le jeu de production est construit AVANT le
    renommage : ce test mesure que cet ordre est bien ce qui protege.
    """
    bloc = _bloc_de_job("build")
    noms = [_nom(e) for e in _etapes(bloc)]
    rang_production = _rang(noms, "distributions de PRODUCTION")
    rang_renommage = _rang(noms, "Renommer les deux")
    assert rang_production < rang_renommage, (
        f"le renommage (etape {rang_renommage}) precede la construction de "
        f"production (etape {rang_production}) : le rang de tentative "
        "atteindrait les artefacts publies sur PyPI.\n" + "\n".join(noms))


def test_la_garde_ACCEPTE_le_bac_a_sable_qui_porte_son_rang(tmp_path):
    """La symetrie positive -- sans elle, les negatives seraient vraies d'une
    garde qui refuserait TOUT bac a sable, donc de la chaine cassee."""
    _fabrique_les_deux_jeux(tmp_path)
    resultat = _joue_la_garde(tmp_path)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr


@pytest.mark.parametrize("version_test,quoi", [
    ("0.1.0", "l'EGALITE STRICTE -- c'est le nom de fichier qui a brule"),
    ("0.1.0.dev1", "un pre-release : pip l'ecarterait de la garde d'install"),
    ("0.1.0.post", "un suffixe sans rang"),
    ("0.1.0.post1a", "des caracteres apres le rang"),
    ("0.1.0+local", "une etiquette locale"),
    ("0.2.0", "un jeu qui validerait autre chose que la release"),
])
def test_la_garde_REFUSE_toute_autre_derive_que_le_rang(tmp_path, version_test,
                                                        quoi):
    """La tolerance est NOMMEE, pas ouverte.

    Six formes, dont l'egalite stricte : elle etait exigee avant le
    2026-09-09, elle est desormais un ecart -- parce qu'un bac a sable qui
    rejoue la version de production rejoue son nom de fichier, et que l'index
    le refuse pour toujours.
    """
    _fabrique_les_deux_jeux(tmp_path, version_test=version_test)
    resultat = _joue_la_garde(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, (
        f"la garde laisse passer {version_test!r} ({quoi}) :\n{sortie}")


def test_la_garde_NOMME_la_forme_attendue_plutot_que_de_refuser_sec(tmp_path):
    """Un refus qui n'offre aucune issue est aussi fautif qu'une destruction
    silencieuse (`EPIC11-ARB-89`). Le message doit dire la forme attendue."""
    _fabrique_les_deux_jeux(tmp_path, version_test="0.1.0")
    sortie = _joue_la_garde(tmp_path).stdout
    assert "0.1.0.post<chiffres>" in sortie, sortie


def test_l_epinglage_du_bac_a_sable_SUIT_le_rang(tmp_path):
    """Les deux surfaces bougent ensemble, ou la roue de l'interface exige une
    version du coeur que l'index ne porte pas -- `mmu-tui` epingle a l'unite
    pres, et une release desaccordee est ININSTALLABLE."""
    _fabrique_les_deux_jeux(tmp_path, epinglage_test="mmu-cli-test==0.1.0")
    resultat = _joue_la_garde(tmp_path)
    assert resultat.returncode != 0, (
        "un epinglage reste sur la version SANS rang passe la garde :\n"
        + resultat.stdout + resultat.stderr)


def test_le_renommage_NOMME_l_absence_de_SOURCE_DE_VERSION(tmp_path):
    """Sans `__version__`, le bac a sable n'a pas de rang -- et le script le
    dit, plutot que de construire un jeu sans suffixe qui se ferait refuser
    par l'index trois etapes plus loin."""
    _fabrique_les_deux_declarations(tmp_path, source_de_version=False)
    resultat = _joue_le_renommage(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "__init__.py est absent" in sortie, (
        "le fichier absent sort sur un message de `sed` au lieu d'etre "
        "nomme :\n" + sortie)


def test_le_renommage_NOMME_une_source_de_version_MUETTE(tmp_path):
    """L'autre cause, et elle ne rend pas le meme message.

    Le fichier existe mais ne porte pas `__version__` -- un renommage de
    module, une ligne indentee. Sans ce cas, la frontiere precedente serait
    vraie d'un script qui ne distinguerait pas « absent » de « muet ».
    """
    _fabrique_les_deux_declarations(tmp_path, source_de_version=False)
    module = tmp_path / "src" / "mixed_media_utility"
    module.mkdir(parents=True, exist_ok=True)
    (module / "__init__.py").write_text('"""sans version."""\n', encoding="utf-8")
    resultat = _joue_le_renommage(tmp_path)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "Aucun __version__" in sortie, sortie


def test_l_attente_sur_TESTPYPI_guette_la_version_du_BAC_A_SABLE():
    """Le defaut que cette frontiere ferme n'aurait pas rougi : il aurait ATTENDU.

    L'etape construit un nom de fichier et lit l'index simple jusqu'a le
    trouver. Avec la version de PRODUCTION, elle guetterait
    `mmu_cli_test-0.1.0.tar.gz` -- un fichier que le rang de tentative fait
    qu'on ne televerse plus jamais. Soixante lectures, dix minutes, puis un
    echec dont la cause serait a chercher du cote de l'index.
    """
    etape = _etape_nommee(_bloc_de_job("publish"), "Attendre que mmu-cli-test")
    texte = "\n".join(etape)
    assert "needs.build.outputs.version_bac_a_sable" in texte, texte
    assert "needs.build.outputs.version }}" not in texte, (
        "l'attente TestPyPI guette la version de PRODUCTION :\n" + texte)


def test_l_attente_sur_PYPI_guette_bien_la_version_de_PRODUCTION():
    """La symetrie, et elle n'est pas decorative : c'est elle qui empeche de
    « corriger » la precedente en branchant les DEUX attentes sur le bac a
    sable, ce qui ferait guetter sur PyPI une version qu'il ne portera jamais."""
    etape = _etape_nommee(_bloc_de_job("release"), "Attendre que mmu-cli soit")
    texte = "\n".join(etape)
    assert "needs.build.outputs.version }}" in texte, texte
    assert "version_bac_a_sable" not in texte, (
        "l'attente PyPI guette la version du bac a sable :\n" + texte)


def test_le_job_build_PUBLIE_les_deux_versions():
    """Une sortie non declaree vaut la chaine VIDE dans `needs.*`, en silence.

    L'attente aurait alors un `VERSION` vide, que son propre `: "${VERSION:?}"`
    attrape -- mais deux etapes plus loin, et sur un message qui parle d'une
    variable, pas d'une sortie manquante.
    """
    bloc = _bloc_de_job("build")
    debut = next(i for i, l in enumerate(bloc) if l.strip() == "outputs:")
    plat = "\n".join(_bloc_apres(bloc, debut))
    for attendue in ("version:", "version_bac_a_sable:"):
        assert attendue in plat, (attendue, plat)


def test_la_garde_ECRIT_les_deux_versions_dans_sa_sortie(tmp_path):
    """Mesure sur l'EXECUTION, pas sur le texte : la declaration de sortie peut
    etre juste et le script ne rien y ecrire."""
    _fabrique_les_deux_jeux(tmp_path)
    assert _joue_la_garde(tmp_path).returncode == 0
    sortie = (tmp_path / "sortie.txt").read_text(encoding="utf-8")
    assert "version=0.1.0\n" in sortie, sortie
    assert f"version_bac_a_sable=0.1.0{SUFFIXE_DU_BAC_A_SABLE}\n" in sortie, sortie
