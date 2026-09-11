# -*- coding: utf-8 -*-
"""La matrice du job `garde-installation`, mesuree plutot que rappelee.

**Ce que cette frontiere ferme, et c'est une surface NEUVE.** Avant la story
8.10, *aucun* banc du depot ne mesurait le job `garde-installation` -- ni son
existence, ni ses etapes, ni son `runs-on`. Le job tournait sur
`ubuntu-latest` seul, et ce qu'il mesurait s'arretait a la SYNTAXE :
`bash -n` sur `install.sh`, `[Parser]::ParseFile` sur `install.ps1` -- sous
`pwsh` **sur Linux** --, puis un `--dry-run` qui affiche un PLAN. Autrement
dit, les 935 lignes d'`install.ps1` n'avaient jamais ete EXECUTEES, aucune
branche macOS n'avait jamais ete jouee autrement qu'avec les `uname` /
`sw_vers` / `brew` factices de `test_installateur_interactif.py`, et aucune
installation n'avait jamais eu lieu dans la CI.

La condition posee par Egan le 2026-09-08 pour la release PyPI -- « la release
ne part QUE quand le one-liner d'installation est eprouve sur les trois
environnements » -- devient executoire par `publish.yml:105-107`, dont le job
`valider` fait `uses: ./.github/workflows/ci.yml` et dont tous les autres jobs
dependent par `needs:`. Ce qui se mesure ici est donc sur le chemin
OBLIGATOIRE de la release.

**Pourquoi une frontiere qui rougit dans les DEUX sens.** Un banc qui ne
verifierait que la presence d'`ubuntu-latest` mesurerait l'etat d'AVANT la
story et l'annoncerait vert. Un banc qui ne verifierait que la presence des
quatre laisserait passer un cinquieme environnement ajoute sans arbitrage --
et sur un depot PRIVE, ou les minutes sont facturees (macOS x10, Windows x2),
un environnement de plus est une ligne de facture de plus. L'egalite
d'ENSEMBLES est la seule ecriture qui attrape les deux.

**Pourquoi une analyse par INDENTATION et pas PyYAML.** On n'importe pas
`yaml` : il n'est pas une dependance de production du depot, et il n'est
declare dans l'extra `[test]` que depuis cette meme story. Le precedent est
ecrit : `test_declenchement_des_workflows.py:47-67` et
`test_chaine_de_publication.py:227-238` refusent PyYAML nommement, et
`test_deux_distributions.py:845-863` decoupe deja un job de `ci.yml` a
l'indentation. Une lecture qui ne peut pas SAUTER est la seule qui mesure
quelque chose en CI -- c'est exactement le defaut que l'AC9 de cette story
corrige sur `test_politique_lfs.py`.

**Le piege que ce banc doit eviter lui-meme** : ses propres commentaires, et
ceux du workflow, CITENT `python -m build`, `twine` et `lfs: true` en toutes
lettres pour expliquer ce qui est interdit. Un `grep` sur le texte brut
rougirait sur sa propre explication. Les lignes de commentaire sont donc
retirees avant toute recherche -- meme lecon que `_job_de_construction_de_ci`
dans `test_deux_distributions.py` et que `_commandes_de_ci_sans_commentaires`
dans `test_politique_lfs.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]

#: Le job a QUITTE `ci.yml` le 2026-09-10, et cette constante est le seul
#: endroit ou ce banc le localise -- c'est ce qui a rendu le deplacement
#: possible sans toucher a aucune des vingt-huit frontieres ci-dessous.
#:
#: Motif du deplacement : dans `ci.yml`, le job tournait a l'interieur de
#: `valider`, donc AVANT le job qui publie sur TestPyPI -- alors qu'il INSTALLE
#: depuis TestPyPI et exige la version qu'on publie. Il reclamait sur l'index
#: ce que seul un job plus tard pouvait y mettre : aucune version neuve ne
#: pouvait demarrer (interblocage mesure sur la release v0.1.1, quatre jambes
#: rouges sur quatre). Le fichier separe plutot qu'un `if:`, pour que
#: `test_le_JOB_lui_meme_ne_peut_pas_etre_neutralise_en_silence` garde son sens
#: ENTIER : le job ne porte toujours aucune condition, il est appele plus tard.
CI = RACINE / ".github" / "workflows" / "garde-installation.yml"

#: Le nom du job. Il reste la PORTE de release : `publish.yml` l'appelle par
#: `uses:` apres le job `publish`, et `release` en depend par `needs:`.
JOB = "garde-installation"

#: Les QUATRE environnements, et le motif de chacun.
#:
#:   ubuntu-latest   le systeme du one-liner le plus courant, et le seul ou
#:                   `pwsh` est preinstalle sans etre le systeme cible ;
#:   macos-15-intel        le runner INTEL. Seul a rendre VRAI
#:                   `mac_intel_sans_bouteilles` (install.sh:400-407), donc
#:                   seul a jouer la branche « Homebrew va compiler » ;
#:   macos-14        Apple Silicon. Le chemin nominal, l'autre cote du meme
#:                   drapeau -- une garde qui ne le fait pas varier ne mesure
#:                   qu'une moitie du produit ;
#:   windows-latest  le seul endroit ou `install.ps1` est EXECUTE plutot que
#:                   parse.
ENVIRONNEMENTS_ATTENDUS = {
    "ubuntu-latest",
    "macos-15-intel",
    "macos-14",
    "windows-latest",
}

#: Les INVOCATIONS exactes que l'aller-retour exige, script par script. On
#: cherche l'appel, jamais le token : voir `_lignes_effectives` ci-dessous et
#: le mutant qui l'a impose.
INVOCATIONS_ATTENDUES = (
    # POSIX -- l'installation reelle, puis le retour, puis la simulation qui
    # s'AJOUTE au lieu d'etre transformee : elle mesure le PLAN, et c'est la
    # seule etape qui tourne encore quand le reseau est coupe.
    "scripts/install.sh --non-interactif --testpypi --sans-raccourci",
    "scripts/install.sh --desinstaller",
    "scripts/install.sh --dry-run",
    # Windows -- install.ps1 EXECUTE, plus seulement parse. 935 lignes que la
    # CI n'avait jamais fait tourner.
    "scripts/install.ps1 -NonInteractif -TestPyPI -SansRaccourci",
    "scripts/install.ps1 -Desinstaller",
)

#: Ce qui PUBLIE. La matrice LIT TestPyPI, elle n'y ecrit rien : publier
#: demande la validation explicite d'Egan et un tag `v*` sur le depot PUBLIC.
GESTES_DE_PUBLICATION = (
    "twine",
    "pypa/gh-action-pypi-publish",
    "python -m build",
)


# --------------------------------------------------------------------------
#  Lecture du workflow, par indentation
# --------------------------------------------------------------------------

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


def _bloc_de_job(nom: str, texte: str) -> list[str]:
    """Les lignes du job `nom`, indentation d'origine conservee.

    Le balayage va jusqu'au BOUT du bloc `jobs:` : un job place en queue de
    fichier -- ce qu'est `garde-installation` aujourd'hui -- ne doit pas etre
    invisible, et un balayage qui rendrait toujours le PREMIER job lirait
    `test` a la place. Les deux modes de panne sont mesures plus bas sur des
    fragments de synthese, parce qu'aucun d'eux ne se voit a la relecture.
    """
    lignes = texte.splitlines()
    indices = [i for i, l in enumerate(lignes) if l.rstrip() == "jobs:"]
    assert len(indices) == 1, (
        f"{len(indices)} bloc(s) `jobs:` lus : la lecture du workflow est "
        "cassee, et un banc qui ne parcourt rien passe toujours.")
    corps = _bloc_apres(lignes, indices[0])
    base = _indentation_minimale(corps)
    for i, ligne in enumerate(corps):
        if _indentation(ligne) == base and ligne.strip() == f"{nom}:":
            return _bloc_apres(corps, i)
    raise AssertionError(f"aucun job `{nom}` dans le workflow lu")


def _sans_commentaires(lignes: list[str]) -> list[str]:
    """Les lignes de CODE du bloc, lignes de commentaire retirees.

    Ce n'est pas un detail de confort : le workflow et ce banc CITENT tous
    deux les gestes interdits pour les expliquer. Une frontiere negative qui
    lirait la prose s'accuserait elle-meme.
    """
    return [l for l in lignes if not l.lstrip().startswith("#")]


#: Ce qui ANNONCE plutot que d'agir. Une ligne qui commence par l'un de ces
#: mots ecrit a l'ecran ; elle ne joue rien.
_ANNONCES = ("echo", "printf", "write-host", "write-output", "write-error")

#: Les marqueurs d'annotation de GitHub Actions. Une ligne qui en porte un est
#: un MESSAGE par construction, quelle que soit la syntaxe qui l'entoure --
#: c'est ce qui rend ce critere robuste la ou le premier mot ne l'est pas.
_ANNOTATIONS = ("::error::", "::warning::", "::notice::", "::debug::")


def _lignes_effectives(texte: str) -> str:
    """Les lignes du job qui AGISSENT : ni commentaire, ni annonce a l'ecran.

    **Le piege, et il a ete mesure plutot que suppose** (mutant `M12` de la
    campagne du 2026-09-08). La premiere redaction de ce banc cherchait le
    TOKEN `--desinstaller` dans le job. Or le job ecrit ses messages d'erreur
    en citant l'option qu'il vient de jouer :

        echo "::error::--desinstaller a rendu 0 en laissant :${survivants}"

    Un mutant qui remplacait l'INVOCATION `install.sh --desinstaller` par
    `install.sh --dry-run` -- c'est-a-dire qui supprimait la moitie « retour »
    de l'aller-retour -- laissait donc le banc VERT, satisfait par le message
    d'erreur d'une verification qui ne pouvait plus rien trouver.

    C'est le piege du commentaire d'un cran plus loin, et il est plus retors :
    ce n'est plus la prose du fichier qui s'accuse a la place du code, c'est
    la prose que le fichier IMPRIME. Retirer les commentaires ne suffisait
    pas ; il faut aussi retirer ce que le job dit.

    **Et le PREMIER MOT ne suffit pas non plus** (mutant `M21`, meme
    campagne). La deuxieme redaction ne regardait que le premier mot de la
    ligne, et un motif de `case` le masque :

        *) echo "::error::mmu-test --version attendait 0.1.0, rendu : ..."

    Le premier mot y est `*)`, pas `echo`. Le mutant qui neutralisait les DEUX
    comparaisons de version -- la branche `case` en bash, le `-notlike` en
    PowerShell -- en gardant leurs messages laissait donc le banc VERT.

    Le critere retenu ne depend donc plus de la syntaxe du shell : une ligne
    qui porte une ANNOTATION GitHub (`::error::`, `::warning::`...) est un
    message par construction, ou qu'elle soit dans la ligne et quoi qu'il y
    ait devant. Les deux criteres sont gardes : le premier mot attrape un
    `echo "ok ..."` qui ne porte aucune annotation.

    **Ce que ca ne mesure pas, dit plutot que tu** : ce banc lit le TEXTE du
    workflow. Que `mmu-test --version` rende REELLEMENT 0.1.0 sur quatre
    systemes, seul le run le dit -- c'est precisement ce que la story 8.10
    met sur le chemin de la release, et qu'aucun banc ne peut jouer sans
    modifier la machine qui joue la suite (`test_installateur_interactif.py`
    l. 64-67 le dit de lui-meme).
    """
    gardees = []
    for ligne in texte.splitlines():
        nue = ligne.strip()
        if not nue or nue.startswith("#"):
            continue
        if any(marque in nue for marque in _ANNOTATIONS):
            continue
        premier = nue.split(" ", 1)[0].lower().lstrip("&").lstrip()
        if premier in _ANNONCES:
            continue
        gardees.append(ligne)
    return "\n".join(gardees)


def _valeur_de_cle(lignes: list[str], cle: str) -> str | None:
    """La valeur scalaire de `cle` au premier niveau du bloc, ou None."""
    if not [l for l in lignes if l.strip()]:
        return None
    base = _indentation_minimale(lignes)
    for ligne in _sans_commentaires(lignes):
        if _indentation(ligne) != base:
            continue
        depouillee = ligne.strip()
        if depouillee.startswith(f"{cle}:"):
            return depouillee[len(cle) + 1:].strip()
    return None


def _sous_bloc(lignes: list[str], cle: str) -> list[str]:
    """Le bloc indente sous `cle`, cherche au premier niveau. Vide si absent."""
    if not [l for l in lignes if l.strip()]:
        return []
    base = _indentation_minimale(lignes)
    utiles = _sans_commentaires(lignes)
    for i, ligne in enumerate(utiles):
        if _indentation(ligne) == base and ligne.strip() == f"{cle}:":
            return _bloc_apres(utiles, i)
    return []


def _liste_de_cle(lignes: list[str], cle: str) -> list[str]:
    """Les elements de la liste `cle`, ecrite en ligne `[a, b]` ou en bloc.

    Les deux ecritures sont admises parce que les deux sont valides en YAML :
    une frontiere qui n'en lirait qu'une serait contournee par un
    reformatage, sans qu'une ligne de mesure ne bouge.
    """
    en_ligne = _valeur_de_cle(lignes, cle)
    if en_ligne and en_ligne.startswith("["):
        brut = en_ligne.strip()[1:].rsplit("]", 1)[0]
        return [x.strip().strip("\"'") for x in brut.split(",") if x.strip()]
    elements = []
    for ligne in _sous_bloc(lignes, cle):
        depouillee = ligne.strip()
        if depouillee.startswith("- "):
            elements.append(depouillee[2:].strip().strip("\"'"))
    return elements


def _etapes(bloc_job: list[str]) -> list[list[str]]:
    """Le bloc `steps:` decoupe en etapes, DANS L'ORDRE du fichier."""
    corps = _sous_bloc(bloc_job, "steps")
    assert corps, "le job ne porte aucun bloc `steps:` lisible"
    base = _indentation_minimale(corps)
    etapes: list[list[str]] = []
    courante: list[str] | None = None
    for ligne in corps:
        if _indentation(ligne) == base and ligne.strip().startswith("- "):
            courante = [ligne]
            etapes.append(courante)
        elif courante is not None:
            courante.append(ligne)
    return etapes


def _texte_du_job() -> str:
    """Le job `garde-installation` de `ci.yml`, COMMENTAIRES RETIRES."""
    return "\n".join(_sans_commentaires(_bloc_de_job(JOB, _lire_ci())))


def _lire_ci() -> str:
    assert CI.exists(), (
        f"{CI} est absent : ce banc mesure la matrice de la garde "
        "d'installation, il n'a rien a lire sans le workflow.")
    return CI.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
#  1. La matrice declare EXACTEMENT les quatre environnements
# --------------------------------------------------------------------------

def test_la_garde_d_installation_declare_EXACTEMENT_les_quatre_environnements():
    """AC10 -- l'egalite d'ensembles, rouge dans les DEUX sens.

    Vers le BAS : un environnement retire fait rougir. C'est le sens qui
    protege la condition d'Egan -- une release ne doit pas pouvoir partir
    parce que quelqu'un a « juste » retire `macos-15-intel` pour aller plus vite,
    alors que c'est le SEUL runner Intel, donc le seul a jouer la branche ou
    Homebrew compile depuis les sources.

    Vers le HAUT : un environnement ajoute fait rougir aussi. Ce depot est
    PRIVE, les minutes y sont facturees, et macOS coute dix fois Linux.
    """
    bloc = _bloc_de_job(JOB, _lire_ci())
    strategie = _sous_bloc(bloc, "strategy")
    assert strategie, (
        f"le job `{JOB}` ne porte aucun bloc `strategy:` : il n'a pas de "
        "matrice, donc il ne tourne que sur un environnement.")
    matrice = _sous_bloc(strategie, "matrix")
    assert matrice, f"`strategy:` du job `{JOB}` sans `matrix:`."

    declares = _liste_de_cle(matrice, "os")
    assert declares, (
        "`strategy.matrix.os` est vide ou illisible : la lecture est cassee, "
        "et un banc qui ne parcourt rien passe toujours.")
    assert len(declares) == len(set(declares)), (
        f"un environnement est declare DEUX FOIS : {declares}. Le doublon "
        "double la facture sans rien mesurer de plus.")

    assert set(declares) == ENVIRONNEMENTS_ATTENDUS, (
        f"`{JOB}` declare {sorted(declares)} la ou la story 8.10 exige "
        f"{sorted(ENVIRONNEMENTS_ATTENDUS)}.\n"
        "  manquant(s) : "
        f"{sorted(ENVIRONNEMENTS_ATTENDUS - set(declares)) or 'aucun'}\n"
        "  en trop     : "
        f"{sorted(set(declares) - ENVIRONNEMENTS_ATTENDUS) or 'aucun'}\n"
        "Condition d'Egan du 2026-09-08 : la release ne part QUE quand le "
        "one-liner est eprouve sur chaque systeme qu'il vise.")


def test_la_matrice_est_REELLEMENT_BRANCHEE_sur_le_runs_on():
    """Le pendant sans lequel la frontiere precedente serait decorative.

    Une `matrix.os` declaree et un `runs-on: ubuntu-latest` code en dur
    passeraient le banc ci-dessus tout en faisant tourner QUATRE fois le meme
    systeme -- quatre fois la facture, un seul environnement mesure. C'est le
    mode de panne le moins visible de toute la story, parce que le workflow
    est alors parfaitement bien forme, vert, et faux.
    """
    bloc = _bloc_de_job(JOB, _lire_ci())
    runs_on = _valeur_de_cle(bloc, "runs-on")
    assert runs_on == "${{ matrix.os }}", (
        f"`{JOB}` porte `runs-on: {runs_on}` : la matrice est declaree mais "
        "pas branchee. Les quatre courses tourneraient sur le meme systeme.")


def test_un_echec_sur_un_environnement_ne_MASQUE_pas_les_autres():
    """`fail-fast: false` -- AC1, et c'est un choix de mesure.

    Avec le defaut (`fail-fast: true`), le premier echec annule les trois
    autres courses. Or c'est precisement `macos-15-intel` qui a le plus de chances
    d'echouer en premier -- le repli `pip install --user pipx` d'install.sh
    (l. 1022-1025) tourne sans `|| true` sous `set -euo pipefail` --, et son
    echec emporterait l'etat de Windows, qui est la seule mesure jamais faite
    d'`install.ps1` en execution. Un diagnostic partiel vaut mieux qu'aucun.
    """
    strategie = _sous_bloc(_bloc_de_job(JOB, _lire_ci()), "strategy")
    assert _valeur_de_cle(strategie, "fail-fast") == "false", (
        f"`{JOB}` n'a pas `fail-fast: false` : le premier echec annule les "
        "autres environnements et on perd leur verdict.")


def test_le_nom_du_job_DISTINGUE_les_quatre_courses():
    """Quatre controles homonymes sont illisibles dans l'onglet Actions."""
    nom = _valeur_de_cle(_bloc_de_job(JOB, _lire_ci()), "name") or ""
    assert "matrix.os" in nom, (
        f"le `name` du job vaut {nom!r} : les quatre courses porteraient le "
        "meme intitule, et un rouge ne dirait pas QUEL systeme a echoue.")


#: Ce qu'une minute de runner COUTE, relativement a Linux, sur un depot prive
#: (grille de facturation GitHub). C'est ce qui rend un plafond uniforme faux :
#: quinze minutes de macOS pesent cent cinquante minutes de Linux.
COUT_RELATIF_PAR_OS = {
    "ubuntu-latest": 1,
    "macos-15-intel": 10,
    "macos-14": 10,
    "windows-latest": 2,
}

#: Le pire cas TOLERE pour ce job, en minutes FACTUREES, tous environnements
#: additionnes. Le budget mensuel inclus de ce depot est de 3 000 minutes, et
#: il a deja ete epuise une fois : un seul job ne doit pas pouvoir en prendre
#: plus du huitieme. La valeur posee le 2026-09-08 est de 348 minutes
#: (8x1 + 15x10 + 15x10 + 20x2). La tolerance est posee JUSTE au-dessus, a
#: 360 : douze minutes de marge, assez pour un ajustement mineur, trop peu
#: pour qu'un plafond gonfle passe inapercu.
#:
#: Ce que ce serrage ferme, et il a ete mesure : a 400, le mutant
#: `ubuntu-latest: 8 -> 55` SURVIVAIT (395 minutes, sous la tolerance) alors
#: qu'il donne 55 minutes de plafond a une jambe dont l'aller-retour complet
#: a ete chronometre a 41 SECONDES. Une tolerance qui laisse passer un facteur
#: 80 sur la seule jambe mesuree ne borne rien -- elle enregistre.
PIRE_CAS_FACTURE_TOLERE = 360


def test_le_cout_de_CHAQUE_environnement_est_BORNE():
    """AC12 -- un plafond PAR ENVIRONNEMENT, pondere par ce qu'il coute.

    Sans plafond, une compilation Homebrew partie par accident sur `macos-15-intel`
    tourne jusqu'au defaut de GitHub -- SIX HEURES -- au tarif macOS.

    CE QUE CE TEST MESURAIT AVANT, ET POURQUOI CA NE SUFFISAIT PAS (revue 8.10,
    couche 3, finding sur l'AC12). Il acceptait `0 < n <= 60` sur un plafond
    UNIQUE. Le mutant `timeout-minutes: 59` passait donc, pour un pire cas de
    1 357 minutes facturees -- 45 % du budget mensuel -- et le banc restait
    vert. Il bornait des minutes de MUR alors que son propre docstring
    invoquait les multiplicateurs x10 et x2 comme motif : la grandeur mesuree
    n'etait pas celle qui coute.

    Il lit donc desormais les plafonds PAR OS dans `matrix.include`, exige
    qu'il y en ait exactement un par environnement declare -- egalite
    d'ENSEMBLES, comme la frontiere des environnements eux-memes --, et borne
    la SOMME PONDEREE. Les deux sens rougissent : un plafond qui disparait, et
    un plafond qui gonfle jusqu'a faire deborder le pire cas facture.

    Ce que ce test ne mesure PAS, dit plutot que tu : la duree REELLE des
    quatre jambes. Aucune n'a jamais tourne -- `ci.yml` n'a jamais ete execute
    sur ce depot, mesure sur l'API GitHub le 2026-09-08. Le seul chiffre
    mesure est l'aller-retour Linux en conteneur : 41 secondes. Les plafonds
    sont donc des garde-fous calibres sur cette mesure et sur le tarif, a
    resserrer au premier run reel.
    """
    bloc = _bloc_de_job(JOB, _lire_ci())
    declare = _valeur_de_cle(bloc, "timeout-minutes")
    assert declare is not None, (
        f"`{JOB}` ne declare aucun `timeout-minutes` : le plafond retombe au "
        "defaut de GitHub, six heures, au tarif macOS x10.")
    assert "matrix." in declare, (
        f"`timeout-minutes: {declare}` est un plafond UNIQUE. Il s'applique a "
        "des runners factures 1x, 10x et 2x, donc il est disproportionne dans "
        "les deux sens a la fois. Le plafond se derive de la matrice.")

    plafonds = _plafonds_par_environnement(bloc)
    attendus = set(ENVIRONNEMENTS_ATTENDUS)
    assert set(plafonds) == attendus, (
        "chaque environnement doit porter SON plafond dans `matrix.include`. "
        f"Declares : {sorted(plafonds)!r} ; attendus : {sorted(attendus)!r}. "
        "Un environnement sans plafond retombe aux six heures de GitHub.")

    hors_bornes = {os_: v for os_, v in plafonds.items() if not 0 < v <= 60}
    assert not hors_bornes, (
        f"plafonds hors bornes (entier de minutes, sous l'heure) : {hors_bornes!r}")

    facture = sum(v * COUT_RELATIF_PAR_OS[os_] for os_, v in plafonds.items())
    assert facture <= PIRE_CAS_FACTURE_TOLERE, (
        f"pire cas de ce job : {facture} minutes FACTUREES "
        f"({', '.join(f'{o} {v}x{COUT_RELATIF_PAR_OS[o]}' for o, v in sorted(plafonds.items()))}), "
        f"au-dela des {PIRE_CAS_FACTURE_TOLERE} tolerees. Le budget mensuel "
        "inclus est de 3 000 minutes et il a deja ete epuise une fois.")


def _plafonds_par_environnement(bloc_job: list[str]) -> dict[str, int]:
    """Les `plafond:` de `matrix.include`, apparies a leur `os:`.

    Lecture par indentation, comme tout ce banc : `include:` est une liste de
    tables, chaque entree commencant par `- os: <nom>` et portant `plafond:`
    a l'indentation de son frere. On ne retient que les paires completes --
    une entree qui nommerait un `os:` sans plafond disparait, et l'egalite
    d'ensembles du test appelant la fera rougir plutot que de la tolerer.
    """
    strategie = _sous_bloc(bloc_job, "strategy")
    matrice = _sous_bloc(strategie, "matrix")
    inclusions = _sous_bloc(matrice, "include")

    plafonds: dict[str, int] = {}
    courant: str | None = None
    for ligne in _sans_commentaires(inclusions):
        depouillee = ligne.strip()
        if depouillee.startswith("- os:"):
            courant = depouillee.split(":", 1)[1].strip().strip("\"'")
        elif depouillee.startswith("plafond:") and courant:
            valeur = depouillee.split(":", 1)[1].strip().strip("\"'")
            if valeur.isdigit():
                plafonds[courant] = int(valeur)
            courant = None
    return plafonds


def test_la_lecture_des_plafonds_rougit_dans_les_DEUX_sens():
    """La frontiere de la frontiere : `_plafonds_par_environnement` mesure-t-elle ?

    Sans ce test, le lecteur pourrait rendre un dictionnaire vide et l'egalite
    d'ensembles rougirait pour la mauvaise raison -- ou pire, rendre les bonnes
    clefs a partir d'un fragment qui ne les porte pas. Les deux sens sont donc
    joues sur des fragments FABRIQUES : un complet, un ampute, un gonfle.

    La fabrique porte QUATRE entrees distinguables -- des plafonds tous
    differents, jamais un remplissage uniforme --, et la cible du controle
    d'amputation est en QUEUE, la ou un balayage tronque se demasque.
    """
    def fragment(entrees: list[tuple[str, int]]) -> list[str]:
        lignes = ["    strategy:", "      matrix:",
                  "        os: [" + ", ".join(o for o, _ in entrees) + "]",
                  "        include:"]
        for os_, plafond in entrees:
            lignes += [f"          - os: {os_}", f"            plafond: {plafond}"]
        return lignes

    complet = [("ubuntu-latest", 8), ("macos-15-intel", 15),
               ("macos-14", 12), ("windows-latest", 20)]
    lu = _plafonds_par_environnement(fragment(complet))
    assert lu == dict(complet), (
        f"le lecteur rend {lu!r} sur un fragment qui porte {dict(complet)!r}")

    # AMPUTATION EN QUEUE : c'est le mode de panne qu'une cible au milieu ne
    # demasque pas. `windows-latest` est le dernier ; s'il disparait, le
    # lecteur ne doit pas le rendre.
    ampute = _plafonds_par_environnement(fragment(complet[:-1]))
    assert "windows-latest" not in ampute, (
        "le lecteur rend un environnement que le fragment ne porte pas : un "
        "balayage tronque passerait inapercu.")

    # AMPUTATION EN TETE, le bord symetrique.
    sans_tete = _plafonds_par_environnement(fragment(complet[1:]))
    assert "ubuntu-latest" not in sans_tete, (
        "le lecteur rend la premiere entree alors qu'elle a ete retiree.")

    # UNE ENTREE SANS PLAFOND ne doit pas etre inventee.
    boiteux = fragment(complet)
    boiteux.remove("            plafond: 12")
    assert "macos-14" not in _plafonds_par_environnement(boiteux), (
        "un `os:` sans `plafond:` est rendu avec une valeur inventee : "
        "l'environnement retomberait aux six heures sans qu'on le voie.")


# --------------------------------------------------------------------------
#  2. La matrice LIT TestPyPI -- elle ne publie RIEN
# --------------------------------------------------------------------------

def test_aucune_etape_de_la_garde_ne_PUBLIE():
    """AC11 -- FRONTIERE NEGATIVE : c'est le geste qu'on surveille.

    Aucun test positif ne verrait revenir un `twine upload`. Publier depuis
    cette garde serait parfaitement bien forme et vert -- ca publierait
    simplement sur PyPI depuis un job dont ce n'est pas le role, sans tag
    `v*` et sans la validation explicite d'Egan.

    Lu sans les commentaires : le job et ce banc citent ces trois gestes pour
    expliquer qu'ils sont interdits.
    """
    job = _texte_du_job()
    fautifs = [geste for geste in GESTES_DE_PUBLICATION if geste in job]
    assert not fautifs, (
        f"le job `{JOB}` porte un geste de publication : {fautifs}. La "
        "matrice LIT TestPyPI (`--testpypi` passe des `--index-url` a pipx), "
        "elle n'y ecrit pas. Publier demande un tag `v*` sur le depot PUBLIC "
        "et la validation explicite d'Egan.")


def test_l_aller_retour_est_REELLEMENT_INVOQUE_sur_les_deux_scripts():
    """Le pendant POSITIF, sans lequel la frontiere negative serait vide.

    Un job qui ne ferait plus rien du tout passerait « aucune publication »
    haut la main. Ce qui est exige ici est l'inverse : l'aller-retour est
    JOUE -- l'installation reelle depuis TestPyPI, le `--desinstaller` qui la
    referme, et la simulation qui s'AJOUTE au lieu d'etre transformee --, et
    il l'est des DEUX cotes : par `install.sh` hors Windows, par `install.ps1`
    sur Windows, ou 935 lignes n'avaient jamais ete executees.

    On cherche l'INVOCATION, jamais le token, et sur les lignes qui AGISSENT :
    voir `_lignes_effectives`, dont le mutant `M12` a impose l'existence.
    """
    effectives = _lignes_effectives(_texte_du_job())
    absentes = [i for i in INVOCATIONS_ATTENDUES if i not in effectives]
    assert not absentes, (
        f"invocation(s) disparue(s) du job `{JOB}` :\n"
        + "\n".join(f"  {i}" for i in absentes)
        + "\nL'aller-retour n'est plus joue en entier, ou la simulation a ete "
          "TRANSFORMEE en installation reelle au lieu d'etre doublee.")


def test_le_verdict_se_lit_sur_l_ETAT_DE_LA_MACHINE_pas_sur_le_code_de_retour():
    """AC3 et AC4 -- et c'est un defaut MESURE de l'existant.

    `install.sh --desinstaller` ne NOMME aucun paquet retire, retire ses
    quatre distributions avec `|| true` (l. 625-629) et rend 0 a l'identique
    qu'il ait tout retire ou rien. Sa verification finale (l. 1249-1267) rend
    ses echecs en `alerte`, jamais en `exit 1`. Un job qui se contenterait du
    code de retour des deux scripts serait donc vert sur une installation qui
    n'a rien pose et une desinstallation qui n'a rien retire.

    Les deux commandes du bac a sable doivent donc etre nommees par les
    etapes elles-memes -- presence apres l'installation, ABSENCE apres le
    retrait.
    """
    effectives = _lignes_effectives(_texte_du_job())
    for commande in ("mmu-test --version", "mmu-tui-test"):
        assert commande in effectives, (
            f"le job `{JOB}` ne nomme jamais `{commande}` : il ne peut donc "
            "mesurer ni sa presence apres installation ni son absence apres "
            "desinstallation, et les deux scripts rendent 0 dans les deux cas.")
    assert _version_du_depot() in effectives, (
        "aucune version attendue n'est nommee : `mmu-test --version` peut "
        "rendre n'importe quoi, y compris la version d'un `mmu` REEL deja "
        "present sur la machine.")


# --------------------------------------------------------------------------
#  3. La LECTURE elle-meme est mesuree, sur des fragments de synthese
# --------------------------------------------------------------------------
#
# La regle des fabriques du depot, appliquee a un balayage plutot qu'a une
# collection de donnees : une fabrique mono-element rend invisible toute
# erreur d'appariement, et une cible toujours placee au MILIEU ne demasque
# pas un balayage tronque. Les trois positions -- tete, milieu, queue -- sont
# donc jouees, et `garde-installation` est aujourd'hui le DERNIER job de
# `ci.yml` : un balayage qui sauterait la derniere entree ne lirait rien du
# tout et ce banc entier deviendrait muet.

def _fragment(position: str) -> str:
    """Un workflow de synthese a TROIS jobs distinguables, cible placee."""
    noms = {"tete": ["cible", "milieu", "queue"],
            "milieu": ["tete", "cible", "queue"],
            "queue": ["tete", "milieu", "cible"]}[position]
    corps = ["name: fragment", "jobs:"]
    for nom in noms:
        corps.append(f"  {nom}:")
        corps.append(f"    name: Job {nom} (${{{{ matrix.os }}}})")
        if nom == "cible":
            corps.append("    runs-on: ${{ matrix.os }}")
            corps.append("    timeout-minutes: 20")
            corps.append("    strategy:")
            corps.append("      fail-fast: false")
            corps.append("      matrix:")
            corps.append("        os: [alpha, beta, gamma]")
        else:
            corps.append("    runs-on: ubuntu-latest")
            corps.append("    strategy:")
            corps.append("      matrix:")
            corps.append("        os: [zeta]")
        corps.append("    steps:")
        corps.append(f"      - run: echo {nom}")
    return "\n".join(corps) + "\n"


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_le_job_est_lu_a_CHAQUE_position_du_fichier(position):
    """Tete ET queue, pas seulement le milieu.

    Un balayage qui rendrait toujours le PREMIER job passerait le cas
    « tete » ; un balayage tronque d'une entree passerait « tete » et
    « milieu ». Les trois positions ensemble sont le seul jeu qui demasque
    les deux modes de panne, et les jobs voisins portent des valeurs
    DIFFERENTES (`os: [zeta]`, `runs-on: ubuntu-latest`) : un remplissage
    uniforme rendrait une permutation invisible.
    """
    bloc = _bloc_de_job("cible", _fragment(position))
    matrice = _sous_bloc(_sous_bloc(bloc, "strategy"), "matrix")
    assert _liste_de_cle(matrice, "os") == ["alpha", "beta", "gamma"], (
        f"le job cible place en {position} n'est pas lu : la lecture rend le "
        "job voisin, ou tronque le balayage.")
    assert _valeur_de_cle(bloc, "runs-on") == "${{ matrix.os }}"
    assert _valeur_de_cle(bloc, "timeout-minutes") == "20"


def test_la_liste_se_lit_EN_LIGNE_comme_EN_BLOC():
    """Les deux ecritures YAML sont valides ; une seule lue serait un trou."""
    en_bloc = """\
name: fragment
jobs:
  cible:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os:
          - alpha
          - beta
          - gamma
    steps:
      - run: echo cible
"""
    matrice = _sous_bloc(_sous_bloc(_bloc_de_job("cible", en_bloc), "strategy"),
                         "matrix")
    assert _liste_de_cle(matrice, "os") == ["alpha", "beta", "gamma"]


def test_un_commentaire_qui_CITE_un_geste_interdit_n_accuse_personne():
    """Le piege paye deux fois dans ce depot, mesure ici plutot que rappele."""
    avec_prose = """\
name: fragment
jobs:
  cible:
    runs-on: ubuntu-latest
    steps:
      # Surtout PAS de `twine upload` ici, ni de `python -m build` :
      # cette garde LIT TestPyPI, elle n'y publie pas.
      - run: echo rien
"""
    texte = "\n".join(_sans_commentaires(_bloc_de_job("cible", avec_prose)))
    assert not [g for g in GESTES_DE_PUBLICATION if g in texte], (
        "la lecture accuse un COMMENTAIRE : la frontiere negative rougirait "
        "sur sa propre explication.")


# --------------------------------------------------------------------------
#  6. Ce que chaque environnement JOUE REELLEMENT
#
#  LE DEFAUT QUE CETTE SECTION FERME, ET LES TROIS COUCHES DE LA REVUE L'ONT
#  TROUVE INDEPENDAMMENT (2026-09-08). Le banc mesurait la DECLARATION de la
#  matrice -- quatre environnements, `runs-on` branche, `fail-fast`, le nom,
#  le plafond -- et jamais son EFFET. Or c'est le `if:` de chaque etape qui
#  decide QUEL environnement joue QUOI, c'est-a-dire le sujet meme de la
#  story. Dix-sept mutants survivaient a ce seul titre. Les plus crus :
#
#    * l'etape PowerShell rebasculee sur `ubuntu-latest` -- c'est-a-dire
#      l'etat exact que la story existe pour clore -- laissait le banc VERT ;
#    * `if: ${{ false }}` sur l'installation reelle : plus aucun aller-retour
#      nulle part, vert ;
#    * `if: false` ou `continue-on-error: true` au NIVEAU DU JOB : les treize
#      frontieres restaient vertes alors que rien ne tournait ;
#    * les deux etapes PERMUTEES : on desinstalle sur une machine vierge, on
#      installe ensuite, et plus rien ne verifie que l'installation se retire.
#
#  L'AGGRAVANT, mesure par la couche 2 : quand l'installation est sautee,
#  l'etape de desinstallation TOURNE QUAND MEME -- son `if` ne depend pas de
#  l'etape precedente, et le `success()` implicite reste vrai apres un pas
#  SAUTE. Elle imprime alors « ok mmu-test et mmu-tui-test ont disparu du
#  PATH » sur une machine ou rien n'a jamais ete pose. Le mutant ne supprime
#  pas une mesure : il en FABRIQUE une fausse.
#
#  La signature mecanique du defaut ne trompait pas : `_etapes()` etait ecrit,
#  documente « DANS L'ORDRE du fichier », porteur de sa propre assertion de
#  non-vacuite -- et appele par AUCUN test. Du code mort dans un banc neuf.
#  Cette section le branche.
# --------------------------------------------------------------------------

def _condition(etape: list[str]) -> str | None:
    """Le `if:` d'une etape, ou None. Lu a l'indentation de l'etape."""
    for ligne in _sans_commentaires(etape):
        depouillee = ligne.strip().lstrip("- ").strip()
        if depouillee.startswith("if:"):
            return depouillee.split(":", 1)[1].strip()
    return None


def _nom(etape: list[str]) -> str:
    for ligne in _sans_commentaires(etape):
        depouillee = ligne.strip().lstrip("- ").strip()
        for cle in ("name:", "uses:"):
            if depouillee.startswith(cle):
                return depouillee.split(":", 1)[1].strip().strip("\"'")
    return "<etape sans nom>"


def _joue_sur(condition: str | None, os_: str) -> bool:
    """Cette etape tourne-t-elle sur `os_` ?

    Evaluateur DELIBEREMENT ETROIT : il ne connait que les formes employees
    par ce job -- `matrix.os == 'x'`, `matrix.os != 'x'`, et leur conjonction
    par `&&` avec un terme qui ne parle pas de `matrix.os`. Une condition
    absente joue partout.

    CE QU'IL NE SAIT PAS FAIRE, dit plutot que tu : `||`, `contains()`,
    `startsWith()`, une comparaison a une autre variable de matrice. Une
    condition qu'il ne sait pas lire fait ROUGIR le test appelant plutot que
    d'etre supposee vraie -- c'est ce que `_conditions_lisibles` verifie. Un
    evaluateur qui devinerait serait pire que pas d'evaluateur : il rendrait
    un verdict sur une question qu'il n'a pas comprise.
    """
    if condition is None:
        return True
    verdict = True
    for terme in _termes(condition):
        if "matrix.os" not in terme:
            continue  # un terme etranger a la matrice : il ne discrimine pas les OS
        prefixe = _prefixe_exige(terme)
        if prefixe is not None:
            verdict = verdict and os_.startswith(prefixe)
            continue
        cible = terme.split("==")[-1].split("!=")[-1].strip().strip("\"'")
        if "==" in terme:
            verdict = verdict and (os_ == cible)
        elif "!=" in terme:
            verdict = verdict and (os_ != cible)
    return verdict


def _prefixe_exige(terme: str) -> str | None:
    """Le prefixe d'un `startsWith(matrix.os, '<x>')`, ou None.

    AJOUTE AU TRIAGE, et par la garde elle-meme : l'etape « ffmpeg et ffprobe
    repondent (macOS) » a besoin de viser les DEUX macOS a la fois, ce qu'une
    egalite ne dit pas. `test_toutes_les_conditions_du_job_sont_LISIBLES` a
    ROUGI a la seconde ou cette etape est entree -- c'est exactement ce qu'une
    anti-vacuite existe pour faire, et c'est la premiere fois qu'elle mord.
    Elle a impose d'etendre l'evaluateur plutot que de laisser une condition
    etre supposee vraie partout.
    """
    import re
    trouve = re.fullmatch(
        r"\s*startsWith\(\s*matrix\.os\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*", terme)
    return trouve.group(1) if trouve else None


def _termes(condition: str) -> list[str]:
    nettoyee = condition.strip()
    if nettoyee.startswith("${{") and nettoyee.endswith("}}"):
        nettoyee = nettoyee[3:-2]
    return [t.strip() for t in nettoyee.split("&&") if t.strip()]


def _lisible(condition: str | None) -> bool:
    """Cet evaluateur sait-il honnetement lire cette condition ?"""
    if condition is None:
        return True
    if "||" in condition:
        return False
    for terme in _termes(condition):
        if "matrix.os" not in terme:
            continue
        if _prefixe_exige(terme) is not None:
            continue  # `startsWith(matrix.os, '<x>')` : lu, et lu exactement
        if terme.count("==") + terme.count("!=") != 1:
            return False
        if "(" in terme:  # contains(), et toute autre fonction non reconnue
            return False
    return True


def _etapes_jouees(os_: str) -> list[str]:
    """Les NOMS des etapes qui tournent sur cet environnement, dans l'ordre."""
    return [_nom(e) for e in _etapes(_bloc_de_job(JOB, _lire_ci()))
            if _joue_sur(_condition(e), os_)]


def test_toutes_les_conditions_du_job_sont_LISIBLES_par_ce_banc():
    """Anti-vacuite de la section : un `if:` non compris ne se suppose pas vrai.

    Sans ce test, une condition ecrite avec `||` ou `contains()` serait lue
    comme « joue partout » par `_joue_sur`, et les frontieres ci-dessous
    deviendraient vertes en ne mesurant plus rien. Le banc prefere rougir et
    demander qu'on etende l'evaluateur.
    """
    illisibles = [(_nom(e), _condition(e))
                  for e in _etapes(_bloc_de_job(JOB, _lire_ci()))
                  if not _lisible(_condition(e))]
    assert not illisibles, (
        "conditions que cet evaluateur ne sait pas lire, donc sur lesquelles "
        f"les frontieres ci-dessous ne mesurent RIEN : {illisibles!r}. "
        "Etendre `_joue_sur` et `_lisible` plutot que de les laisser passer.")


@pytest.mark.parametrize("os_", sorted(ENVIRONNEMENTS_ATTENDUS))
def test_CHAQUE_environnement_joue_REELLEMENT_l_aller_retour(os_):
    """AC2 et AC4 : « sur les quatre » se mesure, il ne se declare pas.

    C'est la frontiere qui tue les mutants `if: matrix.os == 'ubuntu-latest'`
    et `if: ${{ false }}` sur l'installation : trois environnements sur quatre
    cessaient d'installer quoi que ce soit, et le banc restait vert parce que
    la CHAINE d'invocation restait presente quelque part dans le job.
    """
    joues = _etapes_jouees(os_)
    texte = "\n".join(joues).lower()
    assert "installation" in texte or "aller-retour" in texte, (
        f"aucune etape d'installation ne joue sur {os_} : les etapes retenues "
        f"sont {joues!r}. La condition d'Egan porte sur les QUATRE.")
    assert "absence" in texte or "aller-retour" in texte, (
        f"aucune etape de RETOUR ne joue sur {os_} : {joues!r}. Un aller sans "
        "retour ne mesure pas ce que la story promet.")


def test_install_ps1_n_est_EXECUTE_que_sur_WINDOWS():
    """AC5, et son symetrique -- les deux sens, comme l'exige la regle.

    Le mutant que cette frontiere tue est le plus parlant de la revue :
    rebasculer l'etape PowerShell sur `ubuntu-latest`, c'est-a-dire revenir
    EXACTEMENT a l'etat que l'AC5 existe pour clore, laissait le banc vert.

    Le parseur `[Parser]::ParseFile` reste, lui, attache a ubuntu : il analyse
    sans executer, et c'est voulu. On distingue donc l'EXECUTION du script de
    son ANALYSE, sur ce que l'etape invoque.
    """
    etapes = _etapes(_bloc_de_job(JOB, _lire_ci()))
    executantes = [e for e in etapes
                   if "install.ps1 -" in "\n".join(_sans_commentaires(e))]
    assert executantes, (
        "aucune etape n'EXECUTE install.ps1 : 935 lignes que la CI n'a jamais "
        "fait tourner, ce que l'AC5 existe pour clore.")
    for etape in executantes:
        condition = _condition(etape)
        for os_ in sorted(ENVIRONNEMENTS_ATTENDUS):
            attendu = (os_ == "windows-latest")
            assert _joue_sur(condition, os_) is attendu, (
                f"l'etape {_nom(etape)!r} joue sur {os_} = "
                f"{_joue_sur(condition, os_)}, attendu {attendu}. "
                "install.ps1 s'execute sur Windows et nulle part ailleurs.")


@pytest.mark.parametrize("motif", ["slug du depot public",
                                   "URLs d'installation"])
def test_les_etapes_de_SINGLETON_ne_jouent_QUE_sur_ubuntu(motif):
    """AC6 : ce qui n'a de sens qu'une fois ne se paie pas quatre fois.

    Les trois mutants qui retiraient ces `if:` survivaient tous : la story
    payait donc potentiellement quatre fois une etape inerte, sur des runners
    factures jusqu'a dix fois le tarif Linux.
    """
    etapes = [e for e in _etapes(_bloc_de_job(JOB, _lire_ci()))
              if motif.lower() in _nom(e).lower()]
    assert etapes, f"aucune etape ne porte {motif!r} : le motif a-t-il change ?"
    for etape in etapes:
        condition = _condition(etape)
        assert condition is not None, (
            f"l'etape {_nom(etape)!r} n'a aucune condition : elle jouerait "
            "sur les quatre environnements alors qu'elle est independante du "
            "systeme.")
        joues = [o for o in sorted(ENVIRONNEMENTS_ATTENDUS)
                 if _joue_sur(condition, o)]
        assert joues == ["ubuntu-latest"], (
            f"l'etape {_nom(etape)!r} joue sur {joues!r}, attendu "
            "['ubuntu-latest'] seulement.")


def test_l_ORDRE_de_l_aller_retour_est_mesure():
    """On installe PUIS on desinstalle -- l'inverse mesurerait le vide.

    Mutant tue : permuter les deux invocations. Les deux chaines restaient
    presentes, donc la frontiere d'invocation restait verte, et l'aller-retour
    devenait « desinstaller sur une machine vierge, installer ensuite, puis
    exiger l'absence de ce qu'on vient d'installer ».
    """
    for os_ in sorted(ENVIRONNEMENTS_ATTENDUS):
        etapes = [e for e in _etapes(_bloc_de_job(JOB, _lire_ci()))
                  if _joue_sur(_condition(e), os_)]
        # Les lignes de CODE des etapes jouees, mises bout a bout dans l'ordre
        # du fichier. On raisonne sur la LIGNE et non sur l'ETAPE, parce que
        # les deux gestes ne sont pas toujours dans deux etapes : sur Windows
        # ils vivent dans la MEME (« Aller-retour REEL depuis TestPyPI »).
        # Un premier jet comparait des indices d'etape et rendait `2 < 2` --
        # un vrai positif de la frontiere sur elle-meme, garde ici parce qu'il
        # dit exactement pourquoi la granularite compte.
        lignes: list[str] = []
        for etape in etapes:
            lignes += _sans_commentaires(etape)

        pose = [i for i, l in enumerate(lignes)
                if "--non-interactif --testpypi" in l or "-NonInteractif -TestPyPI" in l]
        retrait = [i for i, l in enumerate(lignes)
                   if "--desinstaller" in l or "-Desinstaller" in l]
        assert pose and retrait, (
            f"sur {os_}, l'aller ({bool(pose)}) ou le retour ({bool(retrait)}) "
            "manque parmi les etapes REELLEMENT jouees.")
        assert min(pose) < min(retrait), (
            f"sur {os_}, la desinstallation precede l'installation : "
            "l'absence mesuree apres coup serait vraie sans que rien ait ete "
            "retire.")


def test_le_JOB_lui_meme_ne_peut_pas_etre_neutralise_en_silence():
    """`if: false` et `continue-on-error: true` au niveau du job.

    Deux mutants survivants de la couche 2 : le job entier cesse de tourner,
    ou cesse de compter, et les treize autres frontieres restent vertes parce
    qu'elles lisent un FICHIER, pas une execution. La porte de release
    (`publish.yml` -> `valider` -> `needs:`) devient alors decorative.
    """
    bloc = _bloc_de_job(JOB, _lire_ci())
    condition = _valeur_de_cle(bloc, "if")
    assert condition is None, (
        f"`{JOB}` porte `if: {condition}` : la porte de release peut etre "
        "eteinte sans qu'une frontiere bouge.")
    tolere = _valeur_de_cle(bloc, "continue-on-error")
    assert tolere in (None, "false"), (
        f"`{JOB}` porte `continue-on-error: {tolere}` : le job tournerait, "
        "pourrait echouer, et le workflow appelant resterait vert.")


def test_la_matrice_n_est_pas_AMPUTEE_ni_ELARGIE_par_une_cle_soeur():
    """`exclude:` retire un environnement ; `include:` peut en ajouter un.

    Deux mutants survivants de la couche 2 : `exclude: - os: macos-15-intel` retire
    le SEUL runner Intel -- donc le seul motif declare de sa presence -- et la
    liste en declare toujours quatre ; `include: - os: windows-2019` ajoute
    une cinquieme combinaison, et une cinquieme ligne de facture.

    NUANCE QUI COMPTE, et elle est arrivee au triage : `include:` est employe
    LEGITIMEMENT par ce job depuis le 2026-09-08 pour porter le `plafond:` de
    chaque OS. Une entree d'`include:` qui nomme un `os:` DEJA declare enrichit
    une combinaison existante ; une entree qui en nomme un autre en CREE une.
    Seule la seconde est fautive, et c'est cette distinction que le test mesure
    -- interdire `include:` tout court aurait casse la correction de cout.
    """
    matrice = _sous_bloc(_sous_bloc(_bloc_de_job(JOB, _lire_ci()), "strategy"),
                         "matrix")
    exclusions = _sous_bloc(matrice, "exclude")
    assert not [l for l in _sans_commentaires(exclusions) if l.strip()], (
        "la matrice porte un `exclude:` : un environnement peut disparaitre de "
        "la course pendant que la liste continue d'en declarer quatre.")

    declares = set(ENVIRONNEMENTS_ATTENDUS)
    inclusions = _sans_commentaires(_sous_bloc(matrice, "include"))
    inconnus = []
    for ligne in inclusions:
        depouillee = ligne.strip()
        if depouillee.startswith("- os:"):
            nom = depouillee.split(":", 1)[1].strip().strip("\"'")
            if nom not in declares:
                inconnus.append(nom)
    assert not inconnus, (
        f"`include:` cree des combinaisons hors de la matrice declaree : "
        f"{inconnus!r}. Chacune est une ligne de facture de plus, sur des "
        "runners factures jusqu'a dix fois le tarif Linux.")


def test_chaque_etape_bash_declare_SON_shell():
    """Sur Windows, le shell par defaut est PowerShell, pas bash.

    Mutant survivant de deux couches : retirer `shell: bash` de la seule etape
    qui joue sur les quatre. Son corps bash (`manquants=""`, `for f in ...`)
    partirait alors en PowerShell. Le commentaire du job revendique
    explicitement cette garde ; rien ne la tenait.
    """
    manquantes = []
    for etape in _etapes(_bloc_de_job(JOB, _lire_ci())):
        lignes = _sans_commentaires(etape)
        texte = "\n".join(lignes)
        if "run:" not in texte:
            continue  # une action `uses:` n'a pas de shell
        if not _joue_sur(_condition(etape), "windows-latest"):
            continue  # une etape qui ne joue jamais sur Windows ne risque rien
        if not any(l.strip().startswith("shell:") for l in lignes):
            manquantes.append(_nom(etape))
    assert not manquantes, (
        f"ces etapes jouent sur Windows sans declarer leur shell : "
        f"{manquantes!r}. Le defaut y est PowerShell.")


# --------------------------------------------------------------------------
#  7. Le VERDICT de l'aller-retour, mesure des DEUX cotes
#
#  Trois findings de deux couches, meme famille : le banc mesurait que le job
#  NOMME les commandes, jamais qu'il ROUGIT quand elles manquent.
#
#    * `exit 1` -> `exit 0` apres chacun des trois `::error::` : trois mutants
#      survivants. Une installation qui ne pose rien devenait verte, et la
#      mesure d'ABSENCE -- la moitie « retour » de l'aller-retour -- devenait
#      decorative ;
#    * la comparaison de version neutralisee d'UN SEUL cote : deux mutants
#      survivants isolement, morts seulement en conjonction. `"0.1.0" in
#      <le job entier>` est un OU faible, satisfait par l'autre plateforme --
#      une tautologie CROISEE, que trois environnements sur quatre payaient ;
#    * l'annonce de SUCCES derriere un motif de `case` echappait au filtre
#      d'annotation, si bien que supprimer la verification des deux cotes en
#      gardant les `printf` laissait le banc vert.
# --------------------------------------------------------------------------

#: Les etapes qui portent le verdict, par le mot de leur nom.
ETAPES_DE_VERDICT = ("Installation REELLE", "ABSENCE", "Aller-retour REEL")

SOURCE_DE_VERSION = RACINE / "src" / "mixed_media_utility" / "__init__.py"


def _etapes_de_verdict() -> list[list[str]]:
    etapes = [e for e in _etapes(_bloc_de_job(JOB, _lire_ci()))
              if any(m.lower() in _nom(e).lower() for m in ETAPES_DE_VERDICT)]
    assert len(etapes) >= 3, (
        f"{len(etapes)} etape(s) de verdict lue(s) sur au moins 3 attendues : "
        "les noms ont-ils change ? Une frontiere qui ne parcourt rien passe "
        "toujours.")
    return etapes


def test_chaque_annonce_d_ERREUR_est_suivie_d_une_SORTIE_en_erreur():
    """Un `::error::` sans `exit 1` annonce une panne et rend zero.

    C'est la difference entre un job qui MESURE et un job qui COMMENTE. Les
    trois mutants tues ici -- `exit 1` -> `exit 0` apres chacune des trois
    familles d'annotation -- laissaient passer, respectivement : une
    installation qui ne pose rien, une desinstallation qui ne retire rien, et
    l'equivalent PowerShell des deux.

    On lit la sortie dans les CINQ lignes qui suivent l'annonce : les messages
    de ce job ajoutent jusqu'a deux lignes de contexte (le PATH cherche, le
    motif) avant de sortir.
    """
    fautives = []
    for etape in _etapes_de_verdict():
        lignes = _sans_commentaires(etape)
        for i, ligne in enumerate(lignes):
            if "::error::" not in ligne:
                continue
            suite = " ".join(lignes[i + 1:i + 6])
            if "exit 1" not in suite:
                fautives.append(f"{_nom(etape)} : {ligne.strip()[:70]}")
    assert not fautives, (
        "ces annonces d'erreur ne sont suivies d'aucune sortie en erreur : le "
        "job annoncerait la panne et rendrait zero.\n  " + "\n  ".join(fautives))


@pytest.mark.parametrize("shell,motif", [
    ("bash", "*{v}*)"),
    ("pwsh", "-notlike '*{v}*'"),
])
def test_la_version_est_verifiee_de_CHAQUE_cote(shell, motif):
    """Un cote suffisait a satisfaire le banc -- c'est une tautologie croisee.

    `assert "0.1.0" in <job>` est un OU faible : neutraliser la comparaison
    bash laissait le banc vert parce que la branche PowerShell portait la meme
    chaine, et reciproquement. Trois environnements sur quatre cessaient donc
    d'exiger la version, sans un rouge.

    Chaque cote est desormais mesure SEPAREMENT, sur la forme qui lui est
    propre : le motif de `case` en bash, le `-notlike` en PowerShell.
    """
    # **Le motif porte `{v}` et non la version en dur** : ce banc mesure que
    # `ci.yml` SUIT la source unique, il ne doit pas la recopier lui-meme.
    motif = motif.format(v=_version_du_depot())
    texte = "\n".join("\n".join(_sans_commentaires(e))
                      for e in _etapes_de_verdict())
    assert motif in texte, (
        f"la verification de version manque du cote {shell} (motif attendu : "
        f"{motif!r}). L'autre cote ne la remplace pas : ils tournent sur des "
        "environnements differents.")


def _version_du_depot() -> str:
    """La version REELLE, lue a sa source unique (`EPIC8-ARB-10`).

    **Ajoutee le 2026-09-09, a la release v0.1.1.** Trois bancs de ce fichier
    codaient `0.1.0` en dur pour mesurer que `ci.yml` ne le codait pas en dur
    ailleurs -- ils rougissaient donc a la premiere release, en accusant le
    workflow d'un defaut qui etait le leur. C'est la troisieme occurrence de
    cette famille dans la meme soiree, apres `depot_public.py` (relevee par
    `CLAUDE.md`) et `test_chaine_de_publication.py`.
    """
    import re as _re
    trouve = _re.search(r'__version__\s*=\s*["\']([^"\']+)["\']',
                        SOURCE_DE_VERSION.read_text(encoding="utf-8"))
    assert trouve, f"{SOURCE_DE_VERSION} ne porte plus `__version__`"
    return trouve.group(1)


def test_le_litteral_de_version_du_job_SUIT_la_source_unique():
    """`0.1.0` etait ecrit EN DUR, hors de la source unique de version.

    `EPIC8-ARB-10` fait de `src/mixed_media_utility/__init__.py` la source
    UNIQUE, et `test_deux_distributions.py` compare deja « les quatre
    expressions d'une seule et meme version ». La story 8.10 en a ajoute DEUX
    -- une par shell -- qu'aucune de ces frontieres ne voyait.

    Consequence, et les deux regimes sont mauvais : monter `__version__` sans
    toucher `ci.yml` laisse la garde eprouver le one-liner sur un artefact qui
    n'est pas celui qu'on publie ; et si TestPyPI porte deja la version
    suivante, la garde bloque les QUATRE jambes sur une release qu'elle existe
    pour valider.

    Ce que ce test NE ferme PAS, dit plutot que tu : `install.sh` n'epingle
    aucune version en mode `--testpypi` (`--index-url` seul), donc pipx y
    installe la DERNIERE publiee. Faire coincider le litteral et la source ne
    garantit pas que l'index serve celle-la. La divergence reste possible ;
    elle est desormais VISIBLE plutot que silencieuse.
    """
    import re
    source = SOURCE_DE_VERSION.read_text(encoding="utf-8")
    trouve = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', source)
    assert trouve, (
        f"{SOURCE_DE_VERSION} ne porte plus `__version__` : la source unique "
        "de version a bouge, ce banc ne sait plus a quoi comparer.")
    attendue = trouve.group(1)

    texte = "\n".join("\n".join(_sans_commentaires(e))
                      for e in _etapes_de_verdict())
    litteraux = set(re.findall(r"\b\d+\.\d+\.\d+\b", texte))
    assert litteraux, (
        "aucun litteral de version dans les etapes de verdict : la garde "
        "n'exige plus rien de ce qu'elle installe.")
    etrangers = litteraux - {attendue}
    assert not etrangers, (
        f"les etapes de verdict exigent {sorted(etrangers)!r} alors que la "
        f"source unique porte {attendue!r} "
        f"({SOURCE_DE_VERSION.relative_to(RACINE)}). La garde eprouverait le "
        "one-liner sur un artefact qui n'est pas celui qu'on publie.")


def test_l_echec_du_repli_PRECOMPILE_est_VISIBLE_sur_macOS():
    """Arbitrage d'Egan du 2026-09-08, par invite : « l'echec devient VISIBLE ».

    LE DEFAUT QUE CETTE FRONTIERE FERME, et il traverse les deux stories du
    lot. La story 8.11 (`EPIC11-ARB-271`) a rendu `install.sh` capable de POSER
    ffmpeg et ffprobe depuis evermeet.cx quand Homebrew compilerait -- donc,
    en `--non-interactif`, sur `macos-15-intel`. Le script degrade PROPREMENT si ce
    repli echoue (`|| alerte`), ce qu'`EPIC11-ARB-89` exige d'un installateur :
    un utilisateur ne doit pas etre bloque parce qu'un tiers est tombe.

    Mais ce qui est bon pour l'utilisateur est mauvais pour la GARDE : la
    jambe resterait verte en n'ayant rien eprouve, et `install.sh` declare
    lui-meme que ce qui rougit quand la version epinglee disparait est « RIEN
    dans ce depot ». La porte de release depend desormais d'un tiers, et sans
    cette etape elle ne le saurait pas.

    Ce que la frontiere exige : une etape macOS-SEULEMENT qui verifie ffmpeg
    ET ffprobe, apres l'installation et AVANT la desinstallation -- apres,
    l'un comme l'autre auraient disparu pour une raison legitime.
    """
    etapes = _etapes(_bloc_de_job(JOB, _lire_ci()))
    index = {id(e): i for i, e in enumerate(etapes)}

    gardes = [e for e in etapes
              if "ffmpeg" in "\n".join(_sans_commentaires(e)).lower()
              and "ffprobe" in "\n".join(_sans_commentaires(e)).lower()]
    assert gardes, (
        "aucune etape ne verifie ffmpeg ET ffprobe : le repli precompile de la "
        "story 8.11 degraderait en silence sur le seul environnement qui "
        "l'exerce, et la jambe resterait verte.")

    for garde in gardes:
        joues = [o for o in sorted(ENVIRONNEMENTS_ATTENDUS)
                 if _joue_sur(_condition(garde), o)]
        assert joues == ["macos-14", "macos-15-intel"], (
            f"l'etape {_nom(garde)!r} joue sur {joues!r}. Le repli precompile "
            "n'existe que sur macOS : sur Linux les gestionnaires de paquets "
            "ne compilent pas, et install.ps1 n'a recu AUCUN repli (AC8 de la "
            "8.11). L'etendre ferait rougir des jambes pour un chemin qu'elles "
            "ne parcourent pas.")

        texte = "\n".join(_sans_commentaires(garde))
        assert "exit 1" in texte, (
            f"l'etape {_nom(garde)!r} n'a aucune sortie en erreur : elle "
            "annoncerait l'absence de ffmpeg et rendrait zero.")

        # L'ORDRE : apres la pose, avant le retrait. Une verification placee
        # apres `--desinstaller` serait vraie pour la mauvaise raison.
        pose = [i for i, e in enumerate(etapes)
                if "--non-interactif --testpypi" in "\n".join(_sans_commentaires(e))]
        retrait = [i for i, e in enumerate(etapes)
                   if "--desinstaller" in "\n".join(_sans_commentaires(e))]
        assert pose and retrait, "l'aller-retour bash a disparu du job"
        assert min(pose) < index[id(garde)] < min(retrait), (
            f"l'etape {_nom(garde)!r} n'est pas ENTRE la pose et le retrait : "
            "avant, elle mesurerait l'image du runner ; apres, elle mesurerait "
            "une absence legitime.")


def test_l_evaluateur_de_condition_lit_startsWith_DANS_LES_DEUX_SENS():
    """La frontiere de l'evaluateur, sur la forme qu'il vient d'apprendre.

    `startsWith(matrix.os, 'macos')` doit rendre VRAI sur les deux macOS et
    FAUX sur les deux autres. Sans ce test, `_prefixe_exige` pourrait rendre
    None -- et la condition retomberait sur la lecture par egalite, qui n'y
    trouve ni `==` ni `!=` et conclurait « joue partout ».
    """
    vrais = [o for o in sorted(ENVIRONNEMENTS_ATTENDUS)
             if _joue_sur("startsWith(matrix.os, 'macos')", o)]
    assert vrais == ["macos-14", "macos-15-intel"], (
        f"`startsWith(matrix.os, 'macos')` rend vrai sur {vrais!r}")

    faux = [o for o in sorted(ENVIRONNEMENTS_ATTENDUS)
            if _joue_sur("startsWith(matrix.os, 'windows')", o)]
    assert faux == ["windows-latest"], (
        f"`startsWith(matrix.os, 'windows')` rend vrai sur {faux!r}")

    # Et la forme NON reconnue reste refusee plutot que devinee.
    assert not _lisible("contains(matrix.os, 'macos')"), (
        "`contains(...)` est declare lisible alors que l'evaluateur ne le lit "
        "pas : les frontieres qui s'appuient dessus deviendraient vertes en ne "
        "mesurant rien.")


# --------------------------------------------- les runners RETIRES (2026-09-09)

#: Les libelles d'image que GitHub a RETIRES, avec leur date. Un job qui en
#: nomme un n'echoue pas : il est ACCEPTE a la soumission, puis attend
#: indefiniment un runner qui n'existe plus, jusqu'au delai de file de 24 h.
#:
#: Ce qui a ete paye le 2026-09-09 : la premiere CI publique de la v0.1.0 est
#: restee `queued` sur `macos-13`, RETIRE DEPUIS NEUF MOIS, pendant que ses
#: sept freres recevaient un runner en 2 a 7 secondes. Aucune mesure ne le
#: disait -- ni ici, ni ailleurs -- parce que toutes les frontieres de ce banc
#: verifient que la matrice porte les BONS environnements, jamais qu'ils
#: EXISTENT encore. Un libelle mort passe donc toutes les gardes.
RUNNERS_RETIRES = {
    "macos-13": "retire le 2026-12-04 (annonce le 2025-09-22)",
    "macos-13-arm64": "retire le 2026-12-04",
    "macos-12": "retire le 2024-12-03",
    "macos-11": "retire le 2024-06-28",
    "ubuntu-18.04": "retire le 2023-04-01",
    "ubuntu-20.04": "retire le 2025-04-15",
    "windows-2019": "retire le 2025-06-30",
}

#: L'echeance de la DERNIERE image x86_64 de macOS, et c'est une date qu'il
#: vaut mieux lire ici que decouvrir dans une file d'attente.
FIN_DU_X86_64_MACOS = "aout 2027 (macos-15-intel, derniere image Intel)"

#: ET ROSETTA N'EST PAS LE REPLI, CONTRAIREMENT A CE QUE J'AI D'ABORD ECRIT
#: (corrige le 2026-09-09, sur verification, quelques heures apres l'avoir
#: avance). Le premier jet de ce banc annoncait « apres aout 2027 la jambe
#: passera par Rosetta 2 sur un runner arm64 ». Mesure : Rosetta expire au
#: MEME MOMENT.
#:
#:   macOS 27 (WWDC 2026, automne 2026)  derniere version a la supporter
#:                                       pleinement -- elle est meme
#:                                       desinstallee a la mise a jour,
#:                                       reinstallable sur demande ;
#:   macOS 28 (automne 2027)             plus de Rosetta 2 pour la quasi
#:                                       totalite des applications.
#:
#: Ce n'est donc pas un repli, c'est un pont de quelques mois. Ce qui reste
#: apres : un Mac Intel AUTO-HEBERGE -- qui n'a pas besoin de Rosetta puisqu'il
#: EST Intel, mais que macOS 27 laisse sans mises a jour, le materiel Intel
#: n'etant plus supporte.
#:
#: ET LA VRAIE QUESTION N'EST PAS TECHNIQUE : apres 2027, les utilisateurs sur
#: Mac Intel sont eux aussi figes sur macOS 26. Si le produit veut les servir,
#: la jambe garde son sens et demande une machine ; sinon elle se retire et la
#: matrice tombe a trois. C'est un ARBITRAGE PRODUIT, il appartient a Egan, et
#: il n'est pas tranche ici -- il est ecrit pour ne pas se decouvrir dans une
#: file d'attente.
ROSETTA_EXPIRE_AUSSI = "macOS 28, automne 2027 -- Rosetta n'est pas un repli durable"


def test_AUCUN_environnement_de_la_matrice_n_est_un_runner_RETIRE():
    """La frontiere qui manquait, et son absence a coute une porte de release.

    Elle est NEGATIVE, et c'est le seul type qui puisse attraper ce defaut :
    aucun test positif ne verrait revenir un libelle mort, puisqu'un libelle
    mort est syntaxiquement correct et que GitHub l'ACCEPTE. Le job part en
    file d'attente et n'en sort jamais -- ni rouge, ni vert, juste `queued`.

    C'est la meme famille que le `timeout 5400` de `mesure.py` : ce qui ne se
    mesure pas ne se voit qu'au prix d'une course perdue.
    """
    morts = sorted(ENVIRONNEMENTS_ATTENDUS & set(RUNNERS_RETIRES))
    assert morts == [], (
        "la matrice nomme %d runner(s) RETIRE(S) par GitHub : %s. Le job sera "
        "accepte puis attendra 24 h un runner qui n'existe plus -- ni rouge, "
        "ni vert. Remplacer le libelle, jamais retirer la jambe."
        % (len(morts), ", ".join("%s (%s)" % (o, RUNNERS_RETIRES[o])
                                 for o in morts)))

    # ... ET LE FICHIER LUI-MEME, pas seulement la liste attendue de ce banc.
    # Les deux peuvent diverger, et c'est le fichier qui part en CI.
    declares = _liste_de_cle(
        _sous_bloc(_sous_bloc(_bloc_de_job(JOB, _lire_ci()), "strategy"),
                   "matrix"), "os")
    assert declares, "la lecture de `strategy.matrix.os` est cassee"
    dans_le_fichier = sorted(set(declares) & set(RUNNERS_RETIRES))
    assert dans_le_fichier == [], (
        "`ci.yml` nomme %r, retire(s) par GitHub" % dans_le_fichier)


def test_la_jambe_INTEL_de_macOS_existe_toujours():
    """Le volet POSITIF du precedent, et il vaut autant.

    Retirer `macos-13` faisait passer la frontiere ci-dessus ; ca aurait aussi
    supprime la SEULE jambe Intel, c'est-a-dire la seule qui rende vrai
    `mac_intel_sans_bouteilles` et qui exerce le repli precompile
    d'`EPIC11-ARB-272`. `macos-14` et `macos-15` sont arm64 : les nommer a la
    place aurait rendu la matrice verte en ne mesurant plus rien.

    Une frontiere negative seule se satisfait toujours d'un retrait. Il lui
    faut son symetrique, sinon « corriger » veut dire « supprimer ».

    **Ce qu'elle ne mesure PAS, dit plutot que tu** : elle lit le NOM du
    libelle, pas l'architecture du runner. Ca ne marche que parce que GitHub
    nomme desormais son image Intel explicitement (`macos-15-intel`) -- et
    c'est justement un changement de convention : `macos-13`, qui etait la
    jambe Intel jusqu'ici, ne le disait pas dans son nom et aurait echappe a
    ce critere. Un futur runner Intel qui ne l'annoncerait pas y echapperait
    aussi. La propriete vraie -- « la matrice porte un runner x86_64 » -- n'est
    pas lisible depuis le fichier ; seule une execution la rendrait
    (`uname -m`), et ce banc ne s'execute pas dans la CI.
    """
    intel = [o for o in ENVIRONNEMENTS_ATTENDUS if "intel" in o]
    assert len(intel) == 1, (
        "la matrice porte %d jambe(s) Intel au lieu d'une : %r. Sans elle, le "
        "repli precompile d'`EPIC11-ARB-272` n'est exerce NULLE PART, et la "
        "porte de release reste verte en n'ayant rien eprouve." % (len(intel),
                                                                   intel))
    assert intel[0].startswith("macos-"), (
        "la jambe Intel n'est pas un macOS : %r" % intel[0])

    declares = _liste_de_cle(
        _sous_bloc(_sous_bloc(_bloc_de_job(JOB, _lire_ci()), "strategy"),
                   "matrix"), "os")
    assert intel[0] in declares, (
        "`ci.yml` ne porte pas la jambe Intel %r que ce banc attend" % intel[0])

    # L'ECHEANCE EST ECRITE, parce qu'elle arrivera -- et le remede aussi,
    # avec ce qu'il vaut. Apres aout 2027 il n'y a plus d'image Intel chez
    # GitHub, et Rosetta 2 n'est PAS le repli : elle expire a l'automne 2027
    # elle aussi. Les deux dates vivent ici pour se lire ensemble.
    assert "2027" in FIN_DU_X86_64_MACOS
    assert "2027" in ROSETTA_EXPIRE_AUSSI
