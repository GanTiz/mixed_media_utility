"""Frontieres de la licence du projet.

Tranchee par Egan le 2026-09-07 : **GPL-3.0-or-later**. La story 9.3 « socle
open source » etait en backlog et aucune licence n'avait jamais ete choisie ;
le `MIT` qui vivait dans `pyproject.toml` venait du commit d'echafaudage du
packaging (`d8cc7736`), le meme qui portait l'adresse de gabarit
`egan@example.com`. Deux valeurs de generateur, jamais reprises, dont une
declarait une concession de droits.

**Pourquoi un banc et pas une relecture.** Une licence se declare a QUATRE
endroits qui ne se lisent jamais ensemble : le fichier `LICENSE`, le champ
`license` de `pyproject.toml`, le classifieur PyPI, et la documentation. Rien
n'obligeait ces quatre-la a s'accorder -- et de fait, pendant des mois, trois
d'entre eux annoncaient une licence que personne n'avait choisie tandis que le
quatrieme n'existait pas. Le defaut n'etait pas dans le code : il etait dans
l'absence de mesure.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

#: L'expression SPDX qui fait foi. Une seule chaine, citee une seule fois, que
#: les quatre frontieres ci-dessous comparent chacune a sa source.
EXPRESSION = "GPL-3.0-or-later"


def _pyproject() -> dict:
    return tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 1. Le fichier de licence EXISTE et porte le bon texte
# --------------------------------------------------------------------------

def test_le_fichier_LICENSE_porte_le_texte_de_la_GPLv3():
    """Une metadonnee de paquet n'est pas une concession de droits.

    `pyproject.toml` declarait `MIT` depuis toujours sans qu'aucun fichier
    `LICENSE` n'existe : sur un depot prive personne ne le cherche, sur un
    depot public c'est le premier fichier qu'on ouvre.
    """
    licence = RACINE / "LICENSE"
    assert licence.is_file(), "aucun fichier LICENSE a la racine"

    texte = licence.read_text(encoding="utf-8")
    for marqueur in ("GNU GENERAL PUBLIC LICENSE",
                     "Version 3, 29 June 2007",
                     "Free Software Foundation"):
        assert marqueur in texte, f"LICENSE ne porte pas le marqueur « {marqueur} »"

    # Le texte officiel fait 674 lignes. Le seuil attrape le cas qui compte :
    # un resume, un lien, ou une licence tronquee -- aucun des trois n'ayant
    # d'effet juridique.
    assert len(texte.splitlines()) > 600, (
        "LICENSE est trop court pour etre le texte integral de la GPLv3 : "
        "un resume ou un lien ne concede aucun droit")


# --------------------------------------------------------------------------
# 2. La declaration de paquet dit la MEME chose
# --------------------------------------------------------------------------

def test_pyproject_declare_l_expression_SPDX():
    """Forme PEP 639 : `license` est une CHAINE, pas une table `{text = ...}`.

    La forme table survit a cote d'un classifieur, donc elle laisse exister
    deux declarations qui peuvent diverger. L'expression SPDX interdit le
    classifieur, ce qui supprime la divergence a la racine plutot que de la
    surveiller.
    """
    projet = _pyproject()["project"]
    licence = projet.get("license")
    assert isinstance(licence, str), (
        f"`license` doit etre une expression SPDX (chaine), pas {type(licence).__name__}")
    assert licence == EXPRESSION, f"`license` vaut {licence!r}, attendu {EXPRESSION!r}"


def test_les_DEUX_fichiers_de_licence_sont_EMBARQUES_dans_le_paquet():
    """Un texte de licence qui reste au depot ne suit pas la roue.

    `LICENSE` fonde la concession, `THIRD-PARTY-NOTICES.md` porte les trois
    obligations que la LGPL de Qt fait peser sur toute distribution binaire.
    Les deux doivent partir avec le paquet, pas seulement vivre sur GitHub.
    """
    declares = _pyproject()["project"].get("license-files", [])
    for attendu in ("LICENSE", "THIRD-PARTY-NOTICES.md"):
        assert attendu in declares, f"{attendu} n'est pas dans `license-files`"
        assert (RACINE / attendu).is_file(), f"{attendu} est declare mais absent"


def test_le_plancher_de_hatchling_permet_de_LIRE_l_expression():
    """`requires` est resolu a la volee : sans plancher, rien ne garantit la version.

    Une expression SPDX et `license-files` demandent hatchling >= 1.27. Un
    environnement de construction plus ancien echouerait -- et c'est le genre
    de panne qui ne se voit qu'a la release, quand il est le plus couteux de
    la decouvrir.
    """
    requis = _pyproject()["build-system"]["requires"]
    plancher = [r for r in requis if r.startswith("hatchling")]
    assert plancher, "hatchling absent de build-system.requires"
    assert re.search(r">=\s*1\.(2[7-9]|[3-9]\d)", plancher[0]), (
        f"plancher hatchling insuffisant pour PEP 639 : {plancher[0]!r}")


# --------------------------------------------------------------------------
# 3. Frontieres NEGATIVES : ce qui ne doit PAS revenir
# --------------------------------------------------------------------------

def test_AUCUN_classifieur_de_licence_ne_subsiste():
    """PEP 639 l'interdit a cote d'une expression -- et c'est heureux.

    C'est ce classifieur qui, en doublant la declaration, permettait a
    `pyproject.toml` d'annoncer MIT a deux endroits sans qu'aucun banc ne les
    confronte. Frontiere NEGATIVE : aucun test positif ne verrait revenir une
    seconde declaration.
    """
    fautifs = [c for c in _pyproject()["project"].get("classifiers", [])
               if c.startswith("License ::")]
    assert not fautifs, (
        "PEP 639 interdit un classifieur de licence a cote de "
        f"`License-Expression`, et c'est la surface de divergence : {fautifs}")


def test_PLUS_AUCUN_fichier_LIVRE_n_annonce_la_licence_MIT():
    """Le defaut exact du 2026-09-07, mesure pour qu'il ne revienne pas.

    Le perimetre est celui des fichiers LIVRES -- `LICENSE`, `README.md`,
    `docs/`. `_bmad-output/` en est exclu : c'est l'archive de decision, et
    elle DOIT garder trace de l'ancienne declaration, y compris pour expliquer
    pourquoi elle etait fausse.

    `THIRD-PARTY-NOTICES.md` est exclu lui aussi, et pour une raison de fond :
    il recense les licences des DEPENDANCES, dont plusieurs sont MIT
    legitimement. La frontiere porte sur la licence DU PROJET, pas sur le mot.
    """
    a_lire = [RACINE / "LICENSE"]
    readme = RACINE / "README.md"
    if readme.is_file():
        a_lire.append(readme)
    a_lire += sorted((RACINE / "docs").rglob("*.md"))

    fautifs = []
    for chemin in a_lire:
        if chemin.name == "THIRD-PARTY-NOTICES.md" or not chemin.is_file():
            continue
        for numero, ligne in enumerate(
                chemin.read_text(encoding="utf-8").splitlines(), start=1):
            if "MIT License" in ligne or "licence MIT" in ligne.lower():
                fautifs.append(f"{chemin.relative_to(RACINE)}:{numero}: {ligne.strip()}")

    assert not fautifs, (
        "Le projet est sous " + EXPRESSION + " ; ces lignes livrees annoncent "
        "encore MIT :\n  " + "\n  ".join(fautifs))


# --------------------------------------------------------------------------
# 4. Le recensement des tiers suit les dependances REELLES
# --------------------------------------------------------------------------

def test_CHAQUE_dependance_de_distribution_est_RECENSEE_dans_les_notices():
    """L'obligation de mention se perd par AJOUT, jamais par edition.

    Personne n'oublie de mettre a jour un fichier de notices en le lisant : on
    l'oublie en ajoutant une dependance ailleurs, six semaines plus tard. Cette
    frontiere lie les deux fichiers, de sorte que l'ajout non recense rougisse
    au moment ou il est fait.

    Elle porte sur les dependances de DISTRIBUTION (`dependencies` et l'extra
    `gui`), seules a partir chez l'utilisateur ; l'outillage de developpement
    n'est pas redistribue.
    """
    projet = _pyproject()["project"]
    specifications = list(projet["dependencies"])
    specifications += list(projet.get("optional-dependencies", {}).get("gui", []))

    noms = set()
    for specification in specifications:
        nom = re.split(r"[<>=!~;\[\s@]", specification, maxsplit=1)[0].strip()
        if nom:
            noms.add(nom)

    notices = (RACINE / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8").lower()
    manquants = sorted(n for n in noms if n.lower() not in notices)
    assert not manquants, (
        "dependance(s) distribuee(s) absente(s) de THIRD-PARTY-NOTICES.md -- "
        "leur licence n'est donc mentionnee nulle part : " + ", ".join(manquants))
