# -*- coding: utf-8 -*-
"""Frontieres de la documentation UTILISATEUR : elle ne promet que ce qui existe.

**Le defaut que ce banc ferme, et il a ete paye.** Le 2026-09-07, une relecture
de la doc a trouve, sur des pages publiees : une commande `mmu scan calibrate
--scanned <page.tiff> --chain-id <id>` dont NI l'une NI l'autre des deux options
n'existe ; une page d'installation renvoyant a `docs/guide-developpeur/DESIGN.md`,
fichier absent du depot ; une variable d'environnement `MMU_PROJECT_ROOT` qui
n'apparait nulle part dans `src/`. Aucune de ces trois faussetes n'etait
detectable autrement qu'en lisant la doc en entier, une page a la fois.

Une doc juste le jour ou on l'ecrit se perime en silence. Le depot mesure ses
invariants de code par des frontieres ; ces quatre-ci mesurent sa doc.

**Les cinq frontieres, et quatre d'entre elles sont NEGATIVES** -- elles
attrapent la reintroduction d'un defaut, ce qu'aucun test positif ne verrait :

5. :func:`test_toute_url_brute_du_perimetre_nomme_un_fichier_PRESENT` et
   :func:`test_AUCUNE_url_du_perimetre_ne_designe_le_depot_de_TRAVAIL` -- la
   ligne d'installation en une commande, qui est la seule commande de toute la
   doc que le lecteur ne peut PAS verifier avant de l'executer.

1. :func:`test_aucune_invocation_de_commande_inexistante` -- toute ligne de
   commande ecrite dans un bloc de code du perimetre est rejouee contre l'arbre
   argparse REEL. Un executable inconnu, une sous-commande inconnue, une option
   inconnue : rouge ;
2. :func:`test_aucun_chemin_de_depot_inexistant` -- tout chemin du DEPOT cite en
   code inline doit exister ;
3. :func:`test_aucun_lien_interne_casse` -- tout lien Markdown relatif doit
   pointer sur un fichier present ;
4. :func:`test_les_dependances_annoncees_sont_celles_de_pyproject` et
   :func:`test_les_extras_annonces_sont_ceux_de_pyproject` -- **dans les deux
   sens** : rien d'annonce qui manque a `pyproject.toml`, rien dans
   `pyproject.toml` qui ne soit annonce.

**Ce banc s'EXCLUT de son propre balayage, et il faut le dire plutot que le
taire.** Une frontiere qui lit de la prose s'attrape elle-meme, puisqu'elle doit
citer ce qu'elle interdit : le paragraphe ci-dessus contient `--scanned`,
`--chain-id` et `docs/guide-developpeur/DESIGN.md`, qui sont precisement les
trois faussetes mesurees. Le fichier de test n'est pas dans :data:`PERIMETRE`,
et c'est volontaire.

**Chaque frontiere a ete VUE ROUGIR avant d'etre commitee** (2026-09-07). Treize
mutations, chacune restauree depuis une copie prise AVANT -- jamais par un
`git checkout --`, qui a deja detruit une implementation non commitee dans ce
depot :

===========  ==========================================================
mutation     ce qui a ete casse
===========  ==========================================================
M1           `--scanned` / `--chain-id` ajoutes a `configuration.md`
M2           `mixed-media-util extract-frames` ajoute a `cli.md`
M3           un renvoi a `docs/guide-developpeur/DESIGN.md` dans l'accueil
M4           un lien vers `guide-utilisateur/disparue.md`
M5           `workflow.md` retiree du `nav` de `mkdocs.yml`
M6a          une dependance inventee ajoutee au tableau
M6b          `segno` retire du tableau, mais toujours dans `pyproject.toml`
M7a          l'extra `[inexistant]` cite dans `from-source.md`
M7b          un extra `surnumeraire` declare sans etre documente
M8           un point d'entree `mmu` ajoute a `[project.scripts]`
M9           `license` remis a `MIT` dans `pyproject.toml`
M10          `THIRD-PARTY-NOTICES.md`, nomme par `license-files`, retire
M11          `docs/index.md` annoncant `MIT` pendant que le paquet dit GPL
-----------  ----------------------------------------------------------
M12          `name` de la racine remis a autre chose que `mmu-cli`
M13          le point d'entree `mmu` renomme `mmu-tui` dans la racine
M14          `mmu-cli` retire des dependances de `mmu-tui` (l'ARC coupe)
M15          `textual` remis dans les dependances du COEUR
M16          une ligne retiree du tableau de dependances de la TUI
M17          `mmu-tui` ajoute aux dependances du coeur (l'arc INVERSE)
-----------  ----------------------------------------------------------
M18          `scripts/install.sh` renomme dans l'URL de `docs/index.md`
M19          le depot de TRAVAIL glisse dans l'URL de `linux.md`
M20          la ligne d'installation retiree de `macos.md` et `windows.md`
===========  ==========================================================

Les vingt-deux ont rendu au moins un rouge, et la suite est repassee au vert
apres restauration. Une frontiere qu'on n'a pas vue rougir n'est pas mesuree.

**M18 a M20 ont ete jouees le 2026-09-07 sur l'arbre lui-meme**, et non dans
le bac a sable : elles ne touchent que `docs/`, qu'aucun des deux agents alors
en cours n'editait. Chacune a ete restauree depuis une copie prise AVANT, et
`git status docs/` a ete relu vide apres coup. La verification qui compte :
apres restauration, les quatre pages sont identiques au `diff` pres a leur
copie -- une restauration qu'on n'a pas verifiee n'en est pas une.

M18 et M20 tombent sur la meme frontiere par deux chemins opposes : M18 par son
volet negatif (une URL nomme un chemin absent), M20 par son volet positif (le
perimetre a PERDU des URL). Sans ce second volet, supprimer la ligne
d'installation des quatre pages rendrait la frontiere verte -- elle n'aurait
alors plus rien a garder, ce qui n'est pas la meme chose que n'avoir rien a
redire. M19 est la seule des trois a distinguer `mixed_media_utility` de
`mixed_media_utility-dev` : c'est pourquoi la lecture du depot borne le segment
au lieu de tester un prefixe.

**M12 a M17 ont ete jouees le 2026-09-07 dans un BAC A SABLE** -- une copie de
l'arborescence lue par la frontiere, hors de l'arbre de travail -- et non sur
le depot, parce que trois agents y travaillaient en parallele : muter
`pyproject.toml` sous les mains d'un autre agent est le meme geste que le
`git checkout --` que `CLAUDE.md` interdit pendant une campagne, avec le meme
mode de panne. Le bac est reconstruit par copie, jamais par lien, sauf pour
`_bmad/` et `_bmad-output/` qu'aucune mutation ne touche.

Chacune des six est tombee sur le test attendu, et deux d'entre elles sur deux
tests -- M14 et M17 cassent l'arc entre les distributions, que deux frontieres
mesurent par des chemins differents (le tableau annonce, et le sens de la
dependance).

**Ce que ces frontieres NE mesurent PAS**, dit plutot que tu :

* elles ne savent pas si une phrase est VRAIE. « `--dpi` est facultative »
  passerait sans broncher : c'est une affirmation sur le comportement, pas sur
  la surface. Seul le fait de JOUER la commande le dit, et c'est ce que fait
  `docs/guide-utilisateur/workflow.md` ;
* elles ne verifient pas les VALEURS d'option, seulement leur existence :
  `--profile inexistant` passe, `--profil-inexistant` non ;
* elles ne lisent que les blocs de code clotures, pas la prose : une commande
  citee au fil du texte leur echappe. C'est un choix -- la prose emploie des
  fragments (« la sous-commande `detect` ») que rien ne distingue d'une
  invocation, et une frontiere qui crie a tort finit desarmee.
"""
from __future__ import annotations

import argparse
import re
import shlex
import sys
import tomllib
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]

#: Les pages de la doc UTILISATEUR, celles que ces frontieres gardent. Le guide
#: developpeur et les protocoles de test manuel n'y sont PAS : ils s'adressent a
#: qui a le depot sous les yeux et peut verifier, la ou une page publiee est lue
#: par quelqu'un qui n'a que ce qu'elle dit.
PERIMETRE: tuple[str, ...] = (
    "README.md",
    "docs/index.md",
    "docs/installation/windows.md",
    "docs/installation/macos.md",
    "docs/installation/linux.md",
    "docs/installation/from-source.md",
    "docs/guide-utilisateur/concepts.md",
    "docs/guide-utilisateur/tui.md",
    "docs/guide-utilisateur/cli.md",
    "docs/guide-utilisateur/workflow.md",
    "docs/reference/commandes.md",
    "docs/reference/configuration.md",
)

#: Les executables du produit, et le parser qu'il faut opposer a chacun. Les
#: quatre formes sont mesurees : `mmu-tui` vient de `[project.scripts]`, `mmu`
#: de `bin/mmu`, et les deux `python -m` sont les points d'entree de module.
EXECUTABLES_TUI = ("mmu-tui", "python -m mixed_media_utility.tui")
EXECUTABLES_CLI = ("mmu", "python -m mixed_media_utility.cli",
                   "mixed-media-util")

#: Les racines du DEPOT. Un chemin cite qui commence par l'une d'elles est
#: verifie ; tout autre est tenu pour un chemin de PROJET (`extract-frames/…`,
#: `scans/…`) ou d'ailleurs, et laisse tranquille. Discriminer par la racine
#: plutot que par la forme evite de crier sur `logs/*.log`, qui n'a jamais
#: pretendu exister dans le depot.
RACINES_DU_DEPOT = ("src/", "tests/", "docs/", "scripts/", "bin/", "_bmad/",
                    "_bmad-output/", ".github/", ".claude/")

#: Les fichiers de la racine qu'une page peut citer nommement.
FICHIERS_DE_RACINE = ("pyproject.toml", "mkdocs.yml", "README.md", "CLAUDE.md",
                      ".lfsconfig", ".gitattributes", ".gitignore",
                      "LICENSE", "THIRD-PARTY-NOTICES.md")


# -- lecture des pages -------------------------------------------------------

def _page(chemin: str) -> str:
    return (RACINE / chemin).read_text(encoding="utf-8")


def _blocs_de_code(texte: str) -> list[str]:
    """Le contenu des blocs clotures par ```. Les tableaux en sont exclus."""
    blocs = []
    dedans = False
    courant: list[str] = []
    for ligne in texte.splitlines():
        if ligne.lstrip().startswith("```"):
            if dedans:
                blocs.append("\n".join(courant))
                courant = []
            dedans = not dedans
            continue
        if dedans:
            courant.append(ligne)
    return blocs


def _lignes_de_commande(texte: str) -> list[str]:
    """Les invocations du produit trouvees dans les blocs de code.

    Les continuations `\\` sont recollees : une commande coupee sur trois lignes
    est UNE commande, et l'analyser par morceaux inventerait des fautes.
    """
    prefixes = EXECUTABLES_TUI + EXECUTABLES_CLI
    trouvees = []
    for bloc in _blocs_de_code(texte):
        recollees: list[str] = []
        tampon = ""
        for ligne in bloc.splitlines():
            ligne = ligne.rstrip()
            if tampon:
                ligne = tampon + " " + ligne.strip()
                tampon = ""
            if ligne.endswith("\\"):
                tampon = ligne[:-1].rstrip()
                continue
            recollees.append(ligne)
        if tampon:
            recollees.append(tampon)
        for ligne in recollees:
            nue = ligne.strip()
            # Un prefixe d'environnement (`NO_COLOR=1 mmu-tui`) se retire : ce
            # n'est pas la commande, c'est ce qui la precede.
            nue = re.sub(r"^(?:[A-Z_][A-Z0-9_]*=\S*\s+)+", "", nue)
            if any(nue == p or nue.startswith(p + " ") for p in prefixes):
                trouvees.append(nue)
    return trouvees


# -- construction des parsers reels ------------------------------------------

def _parser_espionne(fabrique) -> argparse.ArgumentParser:
    """Rend le parser qu'une fabrique construit, sans la laisser parser.

    `cli.main` et `tui.__main__.analyser` construisent leur parser puis
    l'emploient aussitot : on intercepte `parse_args` pour saisir l'objet au
    passage. C'est le seul moyen de mesurer l'arbre REEL plutot que d'en
    recopier une liste, qui se perimerait exactement comme la doc.
    """
    saisi: dict[str, argparse.ArgumentParser] = {}
    original = argparse.ArgumentParser.parse_args

    def espion(self, args=None, namespace=None):
        saisi.setdefault("parser", self)
        raise SystemExit(0)

    argparse.ArgumentParser.parse_args = espion
    try:
        try:
            fabrique()
        except SystemExit:
            pass
    finally:
        argparse.ArgumentParser.parse_args = original
    assert "parser" in saisi, "le parser n'a pas ete construit"
    return saisi["parser"]


@pytest.fixture(scope="module")
def parsers() -> dict[str, argparse.ArgumentParser]:
    """Les deux parsers du produit, construits une fois pour tout le module."""
    sys.path.insert(0, str(RACINE / "src"))
    from mixed_media_utility import cli
    from mixed_media_utility.tui import __main__ as tui_main

    return {
        "cli": _parser_espionne(lambda: cli.main([])),
        "tui": _parser_espionne(lambda: tui_main.analyser([])),
    }


def _sous_parsers(parser: argparse.ArgumentParser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return {}


def _option(parser: argparse.ArgumentParser, drapeau: str):
    for action in parser._actions:
        if drapeau in action.option_strings:
            return action
    return None


def _est_un_bouchon(jeton: str) -> bool:
    """Un `<lot_id>`, un `…` ou un `<...>` : un trou a remplir, pas un jeton."""
    return (jeton.startswith("<") and jeton.endswith(">")) or jeton in {"…", "..."}


def _analyser(ligne: str, parsers: dict) -> list[str]:
    """Rend les fautes d'UNE invocation. Liste vide = la ligne est jouable.

    On marche le long des jetons comme argparse le ferait : une option connue
    consomme ses valeurs, un jeton nu descend dans une sous-commande. Ce qui
    reste sans explication est une faute.
    """
    fautes: list[str] = []

    for prefixe in sorted(EXECUTABLES_TUI + EXECUTABLES_CLI, key=len, reverse=True):
        if ligne == prefixe or ligne.startswith(prefixe + " "):
            reste = ligne[len(prefixe):].strip()
            parser = parsers["tui"] if prefixe in EXECUTABLES_TUI else parsers["cli"]
            break
    else:                                   # pragma: no cover -- filtre amont
        return [f"executable inconnu: {ligne!r}"]

    # Un commentaire de fin de ligne, un tube ou un enchainement ne font pas
    # partie de la commande.
    reste = re.split(r"(?:^|\s+)(?:#|\||&&|>|2>)", reste)[0].strip()
    if not reste:
        return fautes

    try:
        jetons = shlex.split(reste)
    except ValueError as erreur:            # guillemet non ferme dans la doc
        return [f"ligne illisible ({erreur})"]

    i = 0
    while i < len(jetons):
        jeton = jetons[i]
        if jeton.startswith("-") and jeton != "-":
            drapeau, _, colle = jeton.partition("=")
            action = _option(parser, drapeau)
            if action is None:
                fautes.append(f"option inconnue {drapeau!r} pour "
                              f"{parser.prog!r}")
                i += 1
                continue
            if colle:
                i += 1
                continue
            arite = action.nargs
            if arite is None:
                a_consommer = 1
            elif isinstance(arite, int):
                a_consommer = arite
            else:                            # '?', '*', '+' : on n'en a aucun
                a_consommer = 0              # dans la CLI, on ne devine pas
            i += 1 + a_consommer
            continue

        choix = _sous_parsers(parser)
        if jeton in choix:
            parser = choix[jeton]
            i += 1
            continue
        if _est_un_bouchon(jeton):
            i += 1
            continue
        fautes.append(f"sous-commande inconnue {jeton!r} pour {parser.prog!r}")
        i += 1

    return fautes


# -- frontiere 1 : les commandes ---------------------------------------------

def test_aucune_invocation_de_commande_inexistante(parsers):
    """NEGATIVE. Aucune ligne de commande du perimetre n'invoque du vide.

    C'est la frontiere qui aurait attrape `mmu scan calibrate --scanned … `
    --chain-id …` : les deux options n'existent pas, et rien d'autre que
    l'execution ne le disait.
    """
    fautes: list[str] = []
    for page in PERIMETRE:
        for ligne in _lignes_de_commande(_page(page)):
            for faute in _analyser(ligne, parsers):
                fautes.append(f"{page}: {faute}\n    dans: {ligne}")
    assert not fautes, ("La doc invoque ce qui n'existe pas :\n"
                        + "\n".join(fautes))


def test_le_banc_attrape_bien_une_option_inventee(parsers):
    """POSITIVE, et c'est la mesure de la frontiere ci-dessus.

    Une frontiere qu'on n'a pas vue rougir n'est pas mesuree. Celle-ci le
    prouve sans toucher au depot, sur une ligne fabriquee ici meme.
    """
    assert _analyser("mmu scan calibrate --scanned p.tiff --chain-id x",
                     parsers), "l'option inventee n'a pas ete vue"
    assert _analyser("mmu extract-frames --project p", parsers), \
        "la sous-commande inventee n'a pas ete vue"
    assert not _analyser("mmu scan --project p --scan s.pdf --dpi 600 "
                         "calibrate --nom x", parsers), \
        "une invocation REELLE a ete refusee a tort"


# -- frontiere 2 : les chemins -----------------------------------------------

def _chemins_cites(texte: str) -> set[str]:
    """Les chemins du depot cites en code inline ou en bloc."""
    cites = set()
    for brut in re.findall(r"`([^`\n]+)`", texte):
        for jeton in re.split(r"[\s,;()\[\]]+", brut.strip()):
            jeton = jeton.strip("`\"'").rstrip(".:,")
            if not jeton:
                continue
            # Les globs se ramenent a leur dossier : `tests/fixtures/lots/**`
            # dit que le DOSSIER existe, pas le motif.
            jeton = re.sub(r"/\*+$", "", jeton)
            jeton = re.sub(r"/[^/]*\*[^/]*$", "", jeton)
            if jeton.startswith(RACINES_DU_DEPOT) or jeton in FICHIERS_DE_RACINE:
                cites.add(jeton.rstrip("/"))
    return cites


def test_aucun_chemin_de_depot_inexistant():
    """NEGATIVE. Aucun chemin du depot cite dans le perimetre n'est absent.

    C'est la frontiere qui aurait attrape le renvoi a
    `docs/guide-developpeur/DESIGN.md`, absent du depot depuis toujours.
    """
    absents: list[str] = []
    for page in PERIMETRE:
        for chemin in sorted(_chemins_cites(_page(page))):
            if not (RACINE / chemin).exists():
                absents.append(f"{page}: {chemin}")
    assert not absents, ("La doc cite des chemins qui n'existent pas :\n"
                         + "\n".join(absents))


# -- frontiere 3 : les liens -------------------------------------------------

def test_aucun_lien_interne_casse():
    """NEGATIVE. Tout lien Markdown relatif du perimetre pointe sur un fichier.

    Une page neuve qui n'entre pas dans `mkdocs.yml` n'est atteignable par
    personne ; un lien vers une page renommee ne l'est pas davantage.
    """
    casses: list[str] = []
    for page in PERIMETRE:
        dossier = (RACINE / page).parent
        for cible in re.findall(r"\]\(([^)\s]+)\)", _page(page)):
            if cible.startswith(("http://", "https://", "#", "mailto:")):
                continue
            fichier = (dossier / cible.split("#", 1)[0]).resolve()
            if not fichier.exists():
                casses.append(f"{page}: -> {cible}")
    assert not casses, ("Liens internes casses :\n" + "\n".join(casses))


#: Les pages de `docs/` qui ne sont **pas** dans le `nav`, avec leur MOTIF.
#:
#: Le lot 4C du 2026-09-10 a retourne la garde qui vivait ici. L'ancienne
#: verifiait que les douze pages de `PERIMETRE` -- une liste ECRITE A LA MAIN --
#: etaient dans le `nav`. Elle ne pouvait donc **structurellement** pas voir un
#: orphelin : une page absente de `PERIMETRE` et absente du `nav` la laissait
#: verte. Mesure du jour : **quinze** des trente-quatre documents de `docs/`
#: n'etaient references par aucune entree de `mkdocs.yml`, et la garde etait
#: verte sur les quinze.
#:
#: Le sens est donc inverse : on part de ce que le DISQUE porte, pas d'une
#: liste. Toute page `.md` de `docs/` est dans le `nav`, ou bien elle est ici
#: avec la raison de n'y pas etre. Une page neuve qui n'est ni l'un ni l'autre
#: fait rougir -- c'est le cas qu'aucune liste ecrite a la main n'attrape.
#:
#: Ce que cette liste COUTE, dit plutot que tu : ce qui y entre part quand meme
#: au depot public, `docs/` etant porte EN ENTIER par `PORTES_A_LA_RACINE` de
#: `scripts/depot_public.py`. Elle dispense du `nav`, jamais de la publication.
HORS_NAV: dict[str, str] = {
    "protocoles/test-atelier-extraction-tui.md":
        "protocole de test MANUEL. Il s'adresse a qui a le depot sous les yeux "
        "et peut verifier, pas a un visiteur du site. Cite `--projet` et "
        "`--rush` la ou `extract` attend `--project` et `--video` : dette "
        "connue, portee par `DETTE_HORS_LOT` de "
        "`test_conformite_de_la_documentation.py`.",
    "protocoles/test-chaine-complete-avec-calibration.md":
        "protocole de test MANUEL de la chaine extract -> makepdf -> scan -> "
        "encode, amende le 2026-08-17. C'est la redaction FAISANT FOI : le "
        "quasi-doublon `testchainecompleteaveccalibration.md` a ete retire le "
        "2026-09-10.",
    "protocoles/test-chaine-extract-makepdf.md":
        "protocole de test MANUEL extract -> makepdf (Epics 3 et 4).",
    "protocoles/test-chaine-scan-epic5.md":
        "protocole de test MANUEL de la commande `scan` (Epic 5), de la "
        "planche imprimee au manifest mis a jour. Tenu par "
        "`DOCUMENTS_TENUS` de `test_conformite_de_la_documentation.py`.",
    "protocoles/test-interface-graphique.md":
        "protocole de test MANUEL de l'interface graphique.",
}


def _pages_de_docs(racine: Path = None) -> list[str]:
    """Toute page `.md` que `docs/` PORTE, en chemin relatif a `docs/`.

    On part du disque, jamais d'une liste : c'est tout le sens du retournement
    du 2026-09-10. Une liste ecrite a la main ne voit que ce qu'on y a mis.
    """
    racine = (RACINE / "docs") if racine is None else racine
    return sorted(chemin.relative_to(racine).as_posix()
                  for chemin in racine.rglob("*.md"))


def test_toute_page_de_docs_est_dans_le_NAV_ou_declaree_HORS_NAV():
    """La garde RETOURNEE. Une page hors du `nav` n'est atteignable par personne.

    L'ancienne redaction partait de `PERIMETRE` et ne pouvait pas voir un
    orphelin. Celle-ci part de `docs/` : ce que le disque porte doit etre
    atteignable, ou bien declare et MOTIVE.
    """
    nav = (RACINE / "mkdocs.yml").read_text(encoding="utf-8")
    orphelines = [page for page in _pages_de_docs()
                  if page not in nav and page not in HORS_NAV]
    assert orphelines == [], (
        "Ces pages de `docs/` ne sont ni dans le `nav` de `mkdocs.yml` ni "
        "declarees dans `HORS_NAV` : elles partent au depot public sans que "
        "personne puisse les atteindre.\n  " + "\n  ".join(orphelines))


def test_FRONTIERE_NEGATIVE_aucune_entree_HORS_NAV_n_est_un_FANTOME():
    """NEGATIVE. Une dispense qui survit a sa page est une tolerance morte.

    Sans elle, `HORS_NAV` grossirait a chaque retrait et ne se viderait
    jamais -- exactement le defaut que `DETTE_HORS_LOT` ferme a cote, et pour
    le meme motif : une liste d'exceptions qui ne se vide pas est une
    tolerance permanente deguisee.
    """
    portees = set(_pages_de_docs())
    fantomes = sorted(page for page in HORS_NAV if page not in portees)
    assert fantomes == [], (
        "Ces entrees de `HORS_NAV` ne designent aucune page existante. La "
        "page a ete retiree ou renommee : retirer aussi sa dispense.\n  "
        + "\n  ".join(fantomes))


def test_FRONTIERE_NEGATIVE_aucune_page_n_est_a_la_fois_au_NAV_et_HORS_NAV():
    """NEGATIVE. Les deux etats sont exclusifs, sinon la dispense ment.

    Une page atteignable qui porte quand meme sa dispense laisserait croire
    qu'elle est hors du site, et la dispense ne rougirait jamais.
    """
    nav = (RACINE / "mkdocs.yml").read_text(encoding="utf-8")
    contradictoires = sorted(page for page in HORS_NAV if page in nav)
    assert contradictoires == [], (
        "Ces pages sont dans le `nav` ET declarees `HORS_NAV` : retirer leur "
        "dispense.\n  " + "\n  ".join(contradictoires))


def test_chaque_dispense_HORS_NAV_porte_un_MOTIF_reel():
    """Une dispense sans motif est un enterrement en silence (`CLAUDE.md`)."""
    muettes = sorted(page for page, motif in HORS_NAV.items()
                     if len(motif.strip()) < 30)
    assert muettes == [], (
        "Ces dispenses ne disent pas POURQUOI la page est hors du `nav` :\n  "
        + "\n  ".join(muettes))


def test_le_releve_des_pages_de_docs_MESURE_encore_quelque_chose():
    """Temoin de VIVACITE : un collecteur qui ne lit rien est vert.

    C'est le mode de panne que `CLAUDE.md` nomme (« un compteur qui court
    n'est pas un producteur vivant »), transpose au balayage d'un dossier :
    un `rglob` casse rendrait zero page et TOUTES les assertions ci-dessus
    deviendraient des tautologies.
    """
    pages = _pages_de_docs()
    assert len(pages) >= 20, (
        f"seulement {len(pages)} pages relevees dans `docs/` : le collecteur "
        "ne lit plus le dossier.")
    assert "index.md" in pages, (
        f"`index.md` est absent du releve : {pages[:5]}...")
    assert "reference/commandes.md" in pages, (
        "le collecteur ne descend plus dans les SOUS-DOSSIERS de `docs/`.")


def test_le_releve_lit_le_PREMIER_et_le_DERNIER_document(tmp_path):
    """Regle des fabriques, point 4 : une cible a CHAQUE BORD.

    Un balayage tronque -- un `[:-1]` ou un `[1:]` -- reste vert tant que
    toutes les cibles sont au milieu. Le corpus temoin est ecrit ICI et
    traverse par le collecteur : le calculer depuis la sortie du collecteur
    lui-meme serait tautologique, un `[:-1]` deplacant simplement le bord.

    Les trois pages sont DISTINGUABLES -- trois noms differents, dont un dans
    un sous-dossier : une troncature ou une permutation ne se voit que si les
    elements different.
    """
    (tmp_path / "a-tete.md").write_text("# tete\n", encoding="utf-8")
    (tmp_path / "m-milieu").mkdir()
    (tmp_path / "m-milieu" / "page.md").write_text("# milieu\n",
                                                   encoding="utf-8")
    (tmp_path / "z-queue.md").write_text("# queue\n", encoding="utf-8")
    (tmp_path / "pas-une-page.txt").write_text("ignore\n", encoding="utf-8")

    assert _pages_de_docs(racine=tmp_path) == [
        "a-tete.md", "m-milieu/page.md", "z-queue.md",
    ], ("Le collecteur ne rend pas le corpus temoin. Une cible perdue en TETE "
        "ou en QUEUE est un balayage tronque, pas un detail.")


# -- frontiere 3 bis : le changelog suit la version DECLAREE -----------------

def _version_declaree() -> str:
    """La version que `src/mixed_media_utility/__init__.py` declare.

    C'est la source UNIQUE des deux distributions (`EPIC8-ARB-10`) : les deux
    `pyproject.toml` la lisent dynamiquement par hatchling. La lire ailleurs
    serait recopier ce que le paquet calcule.
    """
    texte = (RACINE / "src" / "mixed_media_utility" / "__init__.py").read_text(
        encoding="utf-8")
    trouve = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', texte,
                       re.MULTILINE)
    assert trouve, ("`__version__` est introuvable dans `__init__.py` : cette "
                    "frontiere ne mesure plus rien.")
    return trouve.group(1)


def test_le_changelog_porte_une_entree_pour_la_version_DECLAREE():
    """Une version publiee sans entree de changelog est une version muette.

    Le defaut mesure le 2026-09-10 : l'entree `0.1.0` annoncait UNE
    distribution (« Entry point `mmu-tui` », « `pip install mmu-tui` ») alors
    qu'`EPIC8-ARB-10` en a scinde deux, et ne disait rien de la licence. Une
    entree fausse est pire qu'absente ; celle-ci mesure au moins qu'elle
    EXISTE, et les deux frontieres ci-dessous ce qu'elle NOMME.
    """
    version = _version_declaree()
    changelog = (RACINE / "docs" / "changelog.md").read_text(encoding="utf-8")
    titres = re.findall(r"^##\s+(\S+)", changelog, re.MULTILINE)
    assert version in titres, (
        f"`__init__.py` declare la version {version!r}, et `docs/changelog.md` "
        f"n'en porte aucune entree. Titres trouves : {titres}")


def _corps_de_la_version(version: str) -> str:
    """Le corps de la section `## <version>` du changelog, elle SEULE.

    **Premiere redaction trop faible, tuee par mutation (M11).** Elle cherchait
    les deux distributions dans le fichier ENTIER : une mention egaree dans la
    « Roadmap » ou dans les notes de migration la satisfaisait, alors que
    l'entree de la version publiee, elle, pouvait n'en nommer qu'une. On borne
    donc la lecture a la section de la version DECLAREE.
    """
    changelog = (RACINE / "docs" / "changelog.md").read_text(encoding="utf-8")
    sections = re.split(r"^##\s+", changelog, flags=re.MULTILINE)
    for section in sections[1:]:
        if section.split(maxsplit=1)[0] == version:
            return section
    raise AssertionError(
        f"aucune section `## {version}` dans `docs/changelog.md`.")


def test_l_entree_du_changelog_NOMME_les_DEUX_distributions():
    """`EPIC8-ARB-10` : deux distributions, pas une.

    Un lecteur qui suit un changelog annoncant `pip install mmu-tui` seul
    n'installe jamais la ligne de commande.
    """
    corps = _corps_de_la_version(_version_declaree())
    for distribution in ("mmu-cli", "mmu-tui"):
        assert distribution in corps, (
            f"l'entree de version de `docs/changelog.md` ne nomme pas la "
            f"distribution {distribution!r}. La scission d'`EPIC8-ARB-10` "
            "reste invisible a qui lit l'historique des versions.")


def test_l_entree_du_changelog_NOMME_la_LICENCE_des_paquets():
    """La licence est ce qu'un paquet publie porte de plus contraignant.

    Elle est declaree en expression SPDX dans les DEUX `pyproject.toml` ; la
    frontiere la relit la-bas plutot que de la recopier ici, sinon les deux
    redactions divergeraient -- ce que `CANONICAL_ID_MAX_LENGTH` a paye trois
    fois.
    """
    licence = _pyproject()["project"]["license"]
    assert licence == _pyproject_tui()["project"]["license"], (
        "Les deux distributions ne declarent pas la meme licence : "
        f"{licence!r} contre {_pyproject_tui()['project']['license']!r}.")
    corps = _corps_de_la_version(_version_declaree())
    assert licence in corps, (
        f"l'entree de version de `docs/changelog.md` ne dit pas que les "
        f"paquets sont sous {licence!r}.")


# -- frontiere 4 : les dependances, DANS LES DEUX SENS -----------------------

ANCRE_DEPENDANCES = "<!-- FRONTIERE: dependances-de-base -->"
ANCRE_DEPENDANCES_TUI = "<!-- FRONTIERE: dependances-de-la-tui -->"


def _pyproject() -> dict:
    """Le `pyproject.toml` RACINE, celui de la distribution `mmu-cli`."""
    return tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))


def _pyproject_tui() -> dict:
    """Celui de la SECONDE distribution, `mmu-tui`, depuis la scission 8.5.

    Il vit dans un sous-repertoire parce qu'un repertoire ne porte qu'un seul
    `pyproject.toml` : `packaging/mmu-tui/`. La frontiere lit les deux plutot
    que de supposer qu'il n'y en a qu'un -- c'est exactement la supposition qui
    est devenue fausse le 2026-09-07.
    """
    chemin = RACINE / "packaging" / "mmu-tui" / "pyproject.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8"))


def _nom_de_distribution(specification: str) -> str:
    """`opencv-contrib-python>=4.10,<6` -> `opencv-contrib-python`."""
    return re.split(r"[<>=!~\[; ]", specification.strip(), maxsplit=1)[0].lower()


def _tableau_apres_ancre(texte: str, ancre: str) -> list[str]:
    """La premiere colonne du tableau qui suit l'ancre, en code inline."""
    apres = texte.split(ancre, 1)[1]
    noms = []
    for ligne in apres.splitlines():
        if not ligne.startswith("|"):
            if noms:
                break
            continue
        cellule = ligne.split("|")[1].strip()
        trouve = re.fullmatch(r"`([^`]+)`", cellule)
        if trouve:
            noms.append(trouve.group(1).lower())
    return noms


def test_les_dependances_annoncees_sont_celles_de_pyproject():
    """NEGATIVE dans les deux sens, sur le tableau de `from-source.md`.

    Rien d'annonce qui manque a `pyproject.toml` -- une doc qui promet un paquet
    absent envoie l'utilisateur chercher une panne inexistante. Et rien dans
    `pyproject.toml` qui ne soit annonce -- une dependance ajoutee en silence
    est exactement ce qui rend une page d'installation obsolete.
    """
    page = _page("docs/installation/from-source.md")
    assert ANCRE_DEPENDANCES in page, (
        "l'ancre du tableau de dependances a disparu de from-source.md")
    annoncees = set(_tableau_apres_ancre(page, ANCRE_DEPENDANCES))
    declarees = {_nom_de_distribution(d)
                 for d in _pyproject()["project"]["dependencies"]}
    assert annoncees == declarees, (
        f"annoncees sans etre declarees : {sorted(annoncees - declarees)}\n"
        f"declarees sans etre annoncees : {sorted(declarees - annoncees)}")


def test_les_dependances_de_la_TUI_annoncees_sont_celles_de_son_pyproject():
    """NEGATIVE dans les deux sens, sur le SECOND tableau de `from-source.md`.

    Meme mesure que la precedente, sur l'autre distribution. Elle existe a part
    parce que le defaut qu'elle attrape est different : depuis la scission, une
    dependance peut etre declaree du MAUVAIS COTE -- `textual` reste dans le
    coeur, ou `numpy` migre vers la TUI -- et le tableau du coeur, mesure seul,
    resterait vert. C'est la moitie que la frontiere d'hier ne pouvait pas voir.
    """
    page = _page("docs/installation/from-source.md")
    assert ANCRE_DEPENDANCES_TUI in page, (
        "l'ancre du tableau de dependances de la TUI a disparu de from-source.md")
    annoncees = set(_tableau_apres_ancre(page, ANCRE_DEPENDANCES_TUI))
    declarees = {_nom_de_distribution(d)
                 for d in _pyproject_tui()["project"]["dependencies"]}
    assert annoncees == declarees, (
        f"annoncees sans etre declarees : {sorted(annoncees - declarees)}\n"
        f"declarees sans etre annoncees : {sorted(declarees - annoncees)}")


def test_AUCUNE_dependance_de_la_TUI_ne_reste_declaree_par_le_COEUR():
    """NEGATIVE. `textual` et `rich` ne doivent plus etre dans `mmu-cli`.

    C'est la frontiere qui tient la promesse que la doc fait au lecteur : "la
    ligne de commande seule ne tire pas l'interface en terminal". Les remettre
    dans le coeur ferait mentir les trois pages d'installation ET les 28 Mo
    qu'elles annoncent, sans qu'aucun test positif ne s'en apercoive -- tout
    continuerait de s'installer et de marcher, seulement plus lourd.
    """
    coeur = {_nom_de_distribution(d)
             for d in _pyproject()["project"]["dependencies"]}
    for interdit in ("textual", "rich"):
        assert interdit not in coeur, (
            f"{interdit} est redevenu une dependance de `mmu-cli` : la doc "
            "promet une ligne de commande sans interface en terminal")


def test_les_extras_annonces_sont_ceux_de_pyproject():
    """NEGATIVE dans les deux sens, sur les extras `[gui]`, `[dev]`, ..."""
    extras_declares = set(_pyproject()["project"]["optional-dependencies"])
    corpus = "\n".join(_page(page) for page in PERIMETRE)
    extras_cites = {nom.lower()
                    for nom in re.findall(r"[\"'.\w-]\[([a-z]+)\]", corpus)}
    extras_cites &= extras_declares | {"inexistant"}
    inconnus = extras_cites - extras_declares
    non_documentes = extras_declares - extras_cites
    assert not inconnus, f"extras cites mais non declares : {sorted(inconnus)}"
    assert not non_documentes, (
        f"extras declares mais absents de la doc : {sorted(non_documentes)}")


def test_les_points_d_entree_annonces_sont_ceux_des_DEUX_pyproject():
    """POSITIVE, et elle a change de verite le 2026-09-07.

    Elle affirmait `set(scripts) == {"mmu-tui"}` sur le seul `pyproject.toml`
    de la racine, et toute la doc du perimetre en tirait que `pip` ne posait
    pas `mmu`. La scission en deux distributions rend cet enonce FAUX : la
    racine est desormais `mmu-cli` et pose `mmu` ; `mmu-tui` est pose par
    l'autre. Les pages d'installation, `index.md`, `README.md`,
    `guide-utilisateur/cli.md` et `reference/commandes.md` ont ete reprises
    dans le meme mouvement -- c'est cette frontiere qui les tient.

    Le `bin/mmu` du depot survit et reste mesure : la doc dit maintenant qu'il
    peut COEXISTER avec la commande du paquet, et c'est vrai tant qu'il existe.
    """
    coeur = _pyproject()["project"]
    tui = _pyproject_tui()["project"]

    assert coeur["name"] == "mmu-cli", (
        "la distribution de la ligne de commande s'appelle `mmu-cli` "
        "(EPIC8-ARB-6 : `mmu` est pris sur PyPI) ; "
        f"pyproject.toml declare {coeur['name']!r}")
    assert tui["name"] == "mmu-tui", (
        f"packaging/mmu-tui declare {tui['name']!r}")

    assert set(coeur["scripts"]) == {"mmu"}, (
        "la doc du perimetre annonce que `pip install mmu-cli` pose `mmu` ; "
        f"les points d'entree declares sont {sorted(coeur['scripts'])}")
    assert set(tui["scripts"]) == {"mmu-tui"}, (
        f"les points d'entree de mmu-tui sont {sorted(tui['scripts'])}")

    # L'ARC, et son SENS : c'est lui qui fait que `pip install mmu-tui` donne
    # les deux commandes, et que rien n'est installe deux fois. L'inverser
    # rendrait la doc fausse sans casser aucune installation.
    depend_du_coeur = any(_nom_de_distribution(d) == "mmu-cli"
                          for d in tui["dependencies"])
    assert depend_du_coeur, (
        "`mmu-tui` ne declare plus `mmu-cli` : la doc promet que l'installer "
        "donne les deux commandes sans poser le coeur deux fois")
    assert not any(_nom_de_distribution(d) == "mmu-tui"
                   for d in coeur.get("dependencies", [])), (
        "`mmu-cli` depend de `mmu-tui` : l'arc est inverse, et la ligne de "
        "commande n'est plus installable seule")

    assert (RACINE / "bin" / "mmu").exists(), "bin/mmu a disparu"
    assert (RACINE / "bin" / "mmu.cmd").exists(), "bin/mmu.cmd a disparu"


def test_la_licence_annoncee_est_celle_que_le_PAQUET_declare():
    """NEGATIVE, et c'est la divergence exacte qui a ete payee le 2026-09-07.

    Ce jour-la, `pyproject.toml` de cette branche declarait encore
    `license = {text = "MIT"}` -- le gabarit d'echafaudage -- pendant que la
    doc utilisateur ecrite la veille annoncait la GPL, et que `main` avait
    tranche GPL-3.0-or-later sans que personne ne le porte ici. Deux textes,
    deux licences, aucune mesure entre les deux : c'est exactement la famille
    de defaut que `CLAUDE.md` decrit sous « ce qui se mesure se tient, ce qui
    se rappelle se perd ».

    La mesure porte dans les DEUX sens, parce que chacun est un defaut reel :

    * une page qui nomme une licence que le paquet ne declare pas trompe le
      lecteur sur ses droits -- c'est la moitie qui a mordu ;
    * un `license-files` qui nomme un fichier absent casse la construction de
      la roue, et la casse au moment du `twine upload`, pas ici.

    Ce qu'elle NE mesure pas, dit plutot que tu : elle ne lit pas le CONTENU de
    `LICENSE`, donc elle ne verrait pas un texte de licence qui contredirait
    l'expression SPDX declaree. Comparer 674 lignes de prose juridique
    demanderait un condensat de reference, c'est-a-dire une seconde source de
    verite -- exactement ce que cette frontiere existe pour supprimer.
    """
    projet = _pyproject()["project"]
    declaree = projet["license"]
    assert declaree == "GPL-3.0-or-later", (
        "la doc du perimetre annonce GPL-3.0-or-later en toutes lettres "
        f"(docs/index.md, README.md) ; le paquet declare {declaree!r}")

    # Les deux fichiers que la doc met en lien, et que la roue embarque.
    for nom in _pyproject()["project"]["license-files"]:
        assert (RACINE / nom).exists(), (
            f"`license-files` nomme {nom}, qui n'existe pas : la construction "
            "de la roue echouerait, et le lien de la doc pointerait dans le "
            "vide")

    # Le volet symetrique : aucune page ne doit nommer une AUTRE licence. Sans
    # lui, remplacer « GPL-3.0-or-later » par « MIT » dans les pages laisserait
    # la mesure ci-dessus verte -- elle ne lit que `pyproject.toml`.
    autres = ("MIT", "Apache-2.0", "BSD-3-Clause", "proprietaire", "propriétaire")
    for page in PERIMETRE:
        texte = _page(page)
        for licence in autres:
            assert f"licence {licence}" not in texte and \
                   f"sous **{licence}**" not in texte, (
                f"{page} nomme la licence {licence} ; le paquet est sous "
                f"{declaree}")


# -- frontiere 6 : les URL GitHub de la doc ----------------------------------
#
# La ligne d'installation en une commande est la PREMIERE chose qu'un lecteur
# tape, et la seule qu'il ne peut pas verifier : elle telecharge un script et
# le passe a un interpreteur. Elle n'etait mesuree par rien -- ni le chemin
# qu'elle nomme, ni le depot qu'elle vise.
#
# Les deux modes de panne, et ils ne se voient ni l'un ni l'autre a la lecture :
#
#   * le CHEMIN se perime. `test_aucun_chemin_de_depot_inexistant` ne l'attrape
#     pas : il ne lit que les chemins cites en code inline, jamais l'interieur
#     d'une URL. Renommer `scripts/install.sh` laisserait les quatre pages
#     vertes et la commande morte ;
#   * le DEPOT se trompe. `mixed_media_utility` et `mixed_media_utility-dev` ne
#     different que par un suffixe -- c'est le motif exact que `CLAUDE.md`
#     nomme depuis le 2026-09-06, et que la chaine de publication verifie de
#     son cote. Une URL du depot de TRAVAIL sur une page publiee envoie le
#     lecteur sur un 404 et nomme un depot prive dans la meme ligne.

#: Le depot de DISTRIBUTION, seul autorise dans une page publiee.
DEPOT_PUBLIC = "GanTiz/mixed_media_utility"

#: Le depot de TRAVAIL. Aucune page du perimetre ne doit le nommer.
DEPOT_DE_TRAVAIL = "GanTiz/mixed_media_utility-dev"

#: Une URL brute : `raw.githubusercontent.com/<proprietaire>/<depot>/<ref>/<chemin>`.
#: Le `[^/\s)`"]+` sur le depot est ce qui distingue `mixed_media_utility` de
#: `mixed_media_utility-dev` : un prefixe suffirait a confondre les deux.
_URL_BRUTE = re.compile(
    r"https://raw\.githubusercontent\.com/"
    r"(?P<depot>[^/\s)`\"]+/[^/\s)`\"]+)/"
    r"(?P<ref>[^/\s)`\"]+)/"
    r"(?P<chemin>[^\s)`\"]+)")

#: Une URL de page : `github.com/<proprietaire>/<depot>[/...]`.
_URL_PAGE = re.compile(
    r"https://github\.com/(?P<depot>[^/\s)`\"]+/[^/\s)`\"#]+)")


def _depots_nommes(texte: str) -> set[str]:
    """Rend tous les `<proprietaire>/<depot>` que ce texte nomme, les deux formes."""
    trouves = {m.group("depot") for m in _URL_BRUTE.finditer(texte)}
    for m in _URL_PAGE.finditer(texte):
        # `…/mixed_media_utility.git` designe le meme depot que sans suffixe.
        trouves.add(m.group("depot").removesuffix(".git"))
    return trouves


def test_toute_url_brute_du_perimetre_nomme_un_fichier_PRESENT():
    """NEGATIVE. Une URL brute qui telecharge un script nomme un chemin reel.

    C'est la frontiere qui attraperait un renommage de `scripts/install.sh` :
    les quatre pages qui portent la ligne d'installation resteraient
    grammaticalement justes et la commande rendrait un 404.
    """
    absents: list[str] = []
    vus: list[str] = []
    for page in PERIMETRE:
        for m in _URL_BRUTE.finditer(_page(page)):
            chemin = m.group("chemin")
            vus.append(f"{page}: {chemin}")
            if not (RACINE / chemin).exists():
                absents.append(f"{page}: {chemin}")
    assert not absents, (
        "Des URL de la doc telechargent un fichier qui n'existe pas :\n"
        + "\n".join(absents))
    # Le volet positif, sans lequel la frontiere serait verte sur une doc qui
    # aurait PERDU sa ligne d'installation : elle n'a alors plus rien a garder.
    assert len(vus) >= 4, (
        "Le perimetre ne porte plus que "
        f"{len(vus)} URL brute(s) : la ligne d'installation en une commande a "
        "disparu de pages qui la portaient, ou la lecture est cassee")


def test_AUCUNE_url_du_perimetre_ne_designe_le_depot_de_TRAVAIL():
    """NEGATIVE. Une page publiee ne nomme que le depot de DISTRIBUTION.

    Les deux noms ne different que par un suffixe. Une confusion envoie le
    lecteur sur un depot qu'il ne peut pas lire, et nomme un depot prive dans
    une page publique.
    """
    fautives: list[str] = []
    for page in PERIMETRE:
        for depot in sorted(_depots_nommes(_page(page))):
            if depot != DEPOT_PUBLIC:
                fautives.append(f"{page}: {depot}")
    assert not fautives, (
        f"La doc publiee nomme un depot autre que {DEPOT_PUBLIC} "
        f"(le depot de travail est {DEPOT_DE_TRAVAIL}) :\n"
        + "\n".join(fautives))


def test_le_banc_attrape_une_url_FABRIQUEE_a_chaque_BORD():
    """Le banc se prouve sur des lignes fabriquees ici, sans toucher au depot.

    Trois defauts, places en TETE, au MILIEU et en QUEUE : un balayage tronque
    d'un cote ou de l'autre laisserait passer l'un des trois, et la regle des
    fabriques de `CLAUDE.md` (point 4) veut precisement ces deux bords.
    """
    lignes = [
        # tete : le depot de TRAVAIL, en URL brute
        f"curl -fsSL https://raw.githubusercontent.com/{DEPOT_DE_TRAVAIL}"
        "/main/scripts/install.sh | bash",
        # une ligne juste, pour que le banc ne soit pas vert par vacuite
        f"curl -fsSL https://raw.githubusercontent.com/{DEPOT_PUBLIC}"
        "/main/scripts/install.sh | bash",
        # milieu : un chemin qui n'existe pas
        f"curl -fsSL https://raw.githubusercontent.com/{DEPOT_PUBLIC}"
        "/main/scripts/install-inexistant.sh | bash",
        # une seconde ligne juste, distinguable de la premiere
        f"irm https://raw.githubusercontent.com/{DEPOT_PUBLIC}"
        "/main/scripts/install.ps1 | iex",
        # queue : le depot de travail, en URL de page cette fois
        f"Le code vit sur https://github.com/{DEPOT_DE_TRAVAIL}",
    ]
    texte = "\n".join(lignes)

    chemins = [m.group("chemin") for m in _URL_BRUTE.finditer(texte)]
    assert len(chemins) == 4, (
        f"la lecture des URL brutes est cassee : {chemins}")
    absents = [c for c in chemins if not (RACINE / c).exists()]
    assert absents == ["scripts/install-inexistant.sh"], (
        f"le chemin fabrique du MILIEU n'est pas attrape : {absents}")

    depots = _depots_nommes(texte)
    assert DEPOT_DE_TRAVAIL in depots, (
        "les deux depots de travail fabriques -- en TETE en URL brute, en "
        f"QUEUE en URL de page -- ne sont pas vus : {sorted(depots)}")
    assert depots == {DEPOT_PUBLIC, DEPOT_DE_TRAVAIL}, (
        f"la lecture des depots est cassee : {sorted(depots)}")


# -- les AFFIRMATIONS DE COMPORTEMENT des pages d'installation ----------------
#
# Ce que ces quatre frontieres ferment, et il a ete paye. Le finding `C1-9` de
# la revue 8.8 a trouve QUATRE affirmations fausses ou incompletes dans
# `docs/installation/`, toutes rendues fausses par la story 8.8 elle-meme, et
# aucune detectable par les frontieres ci-dessus : elles mesurent la SURFACE
# (une commande existe-t-elle, un chemin existe-t-il), jamais ce qu'une page
# AFFIRME du comportement.
#
# Les quatre ont ete reprises en prose au commit de triage. Ce qui manquait,
# c'est la mesure : une prose corrigee a la main se reperime au prochain
# changement du script, exactement comme elle venait de le faire. Et la preuve
# que ce n'etait pas theorique est tombee en ecrivant ces lignes -- une
# CINQUIEME occurrence, que `C1-9` n'avait pas vue parce qu'il ne lisait que
# `docs/installation/` : `docs/reference/configuration.md`, section « Hors du
# projet », annoncait encore « Un seul fichier ».
#
# Le principe des quatre : l'invariant se LIT DANS LE SCRIPT, il n'est pas
# recopie ici. Renommer `mmu-tui.desktop` dans `install.sh` fait rougir la
# frontiere de la page, ce qu'un litteral copie dans le banc ne ferait pas --
# c'est le defaut « un module porte sans sa mesure » que ce depot a deja paye.

INSTALLATEUR_SH = "scripts/install.sh"
INSTALLATEUR_PS1 = "scripts/install.ps1"

#: La plateforme que chaque page decrit. Une page absente de ce tableau est
#: tenue pour TRANSVERSE : elle parle de toutes les plateformes a la fois, donc
#: une affirmation qui n'est vraie que sur l'une d'elles y est fausse.
PLATEFORME_DE_LA_PAGE: dict[str, str] = {
    "docs/installation/linux.md": "linux",
    "docs/installation/macos.md": "macos",
    "docs/installation/windows.md": "windows",
}


def _script(chemin: str) -> str:
    return (RACINE / chemin).read_text(encoding="utf-8")


def _section(texte: str, titre: str) -> str:
    """Rend la section `## <titre>` d'une page, jusqu'au prochain `## `.

    Assert bruyamment si le titre est introuvable : une frontiere qui ne
    trouve plus son perimetre doit crier, pas mesurer une chaine vide et
    passer au vert. C'est la panne exacte que `C3-6` a evitee sur le banc de
    l'installateur, et elle se rejoue a l'identique ici.
    """
    debut = re.search(rf"^##\s+\d*\.?\s*{re.escape(titre)}\s*$", texte,
                      re.MULTILINE)
    assert debut, (
        f"section « {titre} » introuvable : le perimetre de la frontiere est "
        "perdu, elle ne mesure plus rien")
    reste = texte[debut.end():]
    suite = re.search(r"^##\s+", reste, re.MULTILINE)
    return reste[: suite.start()] if suite else reste


def _raccourci_ecrit_par_le_shell() -> str:
    """Le nom de fichier que `install.sh` pose, LU dans le script."""
    m = re.search(r'^RACCOURCI_FICHIER="\$\{RACCOURCI_DOSSIER\}/([^"]+)"',
                  _script(INSTALLATEUR_SH), re.MULTILINE)
    assert m, ("`install.sh` ne definit plus `RACCOURCI_FICHIER` sous la forme "
               "attendue : la frontiere ne sait plus quel nom la page doit "
               "citer")
    return m.group(1)


def _raccourci_ecrit_par_powershell() -> str:
    """Le nom de fichier que `install.ps1` pose, LU dans le script."""
    m = re.search(r'Join-Path \$RaccourciDossier "([^"]+)"',
                  _script(INSTALLATEUR_PS1))
    assert m, ("`install.ps1` ne compose plus `$RaccourciFichier` sous la "
               "forme attendue : la frontiere ne sait plus quel nom la page "
               "doit citer")
    return m.group(1)


def _garde_du_raccourci_shell() -> str:
    """Le bloc `if` qui decide si un raccourci est POSSIBLE, dans `install.sh`."""
    texte = _script(INSTALLATEUR_SH)
    debut = texte.index("RACCOURCI_POSSIBLE=0")
    fin = texte.index("RACCOURCI_POSSIBLE=1", debut)
    return texte[debut:fin]


def _plateformes_qui_posent_un_raccourci() -> set[str]:
    """Rend les plateformes ou un raccourci est ECRIT, lu dans les deux scripts.

    Le point de la frontiere `_le_SEUL_fichier` : c'est ce qui autorise
    `macos.md` a dire ce que `linux.md` n'a pas le droit de dire. La reponse
    n'est pas une opinion, elle est dans le garde.
    """
    avec: set[str] = set()
    garde = _garde_du_raccourci_shell()
    if re.search(r'"\$\{SYSTEME\}"\s*=\s*"linux"', garde):
        avec.add("linux")
    if re.search(r'"\$\{SYSTEME\}"\s*=\s*"macos"', garde):
        avec.add("macos")
    if "Test-SurWindows" in _script(INSTALLATEUR_PS1):
        avec.add("windows")
    return avec


def test_la_desinstallation_MANUELLE_nomme_le_FICHIER_de_raccourci_pose():
    """Le nom vient du SCRIPT, pas d'un litteral recopie ici.

    Un lecteur qui suit la desinstallation manuelle sans y trouver le
    raccourci laisse derriere lui exactement le fichier mort que
    `EPIC11-ARB-89` dit de ne pas laisser. La frontiere mord des DEUX cotes :
    retirer la ligne de la page la fait rougir, et renommer le fichier dans le
    script aussi -- ce qu'un nom copie dans le banc ne ferait pas.
    """
    attendus = {
        "docs/installation/linux.md": _raccourci_ecrit_par_le_shell(),
        "docs/installation/windows.md": _raccourci_ecrit_par_powershell(),
    }
    muettes: list[str] = []
    for page, fichier in attendus.items():
        if fichier not in _section(_page(page), "Désinstaller"):
            muettes.append(f"{page}: n'y nomme pas {fichier}")
    assert not muettes, (
        "La desinstallation MANUELLE laisse un raccourci derriere elle :\n"
        + "\n".join(muettes))


_SEUL_FICHIER = re.compile(r"(?i)\b(?:le|un)\s+seul\s+fichier\b")


def test_AUCUNE_page_dont_la_plateforme_pose_un_raccourci_ne_dit_le_SEUL_FICHIER():
    """NEGATIVE. « le seul fichier ecrit hors projet » n'est vrai que sans raccourci.

    Depuis la story 8.8, Linux et Windows ecrivent AUSSI un raccourci hors du
    projet. La phrase reste vraie sur `macos.md`, et la frontiere le sait
    parce qu'elle LIT le garde : `install.sh` epingle `SYSTEME = linux`. Le
    jour ou macOS gagnerait un raccourci, cette page rougirait d'elle-meme.

    Une page TRANSVERSE (absente de :data:`PLATEFORME_DE_LA_PAGE`) parle de
    toutes les plateformes, donc de Linux : elle n'a pas le droit a la phrase
    non plus. C'est par ce volet que la frontiere a trouve l'occurrence que
    `C1-9` avait manquee, hors de `docs/installation/`.
    """
    avec_raccourci = _plateformes_qui_posent_un_raccourci()
    assert avec_raccourci, (
        "aucune plateforme ne pose de raccourci d'apres les scripts : la "
        "lecture du garde est cassee, la frontiere serait verte par vacuite")

    fautives: list[str] = []
    for page in PERIMETRE:
        texte = _page(page)
        plateforme = PLATEFORME_DE_LA_PAGE.get(page)
        # Une page transverse couvre toutes les plateformes, donc les fautives.
        couvre_une_plateforme_a_raccourci = (
            plateforme in avec_raccourci if plateforme else True)
        if not couvre_une_plateforme_a_raccourci:
            continue
        for m in _SEUL_FICHIER.finditer(texte):
            # La phrase n'est fautive que si elle parle bien de ce qui est
            # ecrit HORS du projet -- « un seul fichier de calibration » ne
            # regarde pas cette frontiere.
            fenetre = texte[max(0, m.start() - 500): m.end() + 500]
            if re.search(r"(?i)hors\s+(?:du\s+)?projet", fenetre):
                fautives.append(f"{page}: « {m.group(0)} »")
    assert not fautives, (
        "Ces pages annoncent un SEUL fichier ecrit hors projet, alors que "
        f"leur plateforme pose aussi un raccourci ({', '.join(sorted(avec_raccourci))}) :\n"
        + "\n".join(fautives))


def test_la_page_qui_nomme_le_DOSSIER_du_raccourci_nomme_aussi_XDG_DATA_HOME():
    """`install.sh` respecte XDG ; une page qui l'ignore ment sur un chemin.

    La frontiere est CONDITIONNEE au script : si `install.sh` cessait un jour
    d'honorer `XDG_DATA_HOME`, elle cesserait d'elle-meme de l'exiger de la
    page, au lieu de reclamer une mention devenue fausse.
    """
    honore_xdg = "XDG_DATA_HOME" in _script(INSTALLATEUR_SH)
    if not honore_xdg:
        pytest.skip("`install.sh` n'honore plus XDG_DATA_HOME : rien a exiger")

    page = "docs/installation/linux.md"
    texte = _page(page)
    lignes = texte.splitlines()
    fautives: list[str] = []
    for n, ligne in enumerate(lignes):
        if ".local/share/applications" not in ligne:
            continue
        # Le voisinage, parce qu'une phrase se coupe sur plusieurs lignes.
        voisinage = "\n".join(lignes[max(0, n - 3): n + 4])
        if "XDG_DATA_HOME" not in voisinage:
            fautives.append(f"{page}:{n + 1}: {ligne.strip()}")
    assert not fautives, (
        "Ces passages annoncent le dossier du raccourci sans dire que "
        "`XDG_DATA_HOME` le deplace, alors que `install.sh` le respecte :\n"
        + "\n".join(fautives))


def test_le_GARDE_du_raccourci_n_a_pas_change_sans_que_la_page_soit_relue():
    """Le garde pose TROIS conditions ; la page les dit en prose.

    **Ce que cette frontiere fait**, et il faut le dire exactement : elle
    epingle le nombre de conditions du garde de `install.sh`. Elle ne LIT PAS
    le francais de la page -- aucune frontiere ne sait qu'« il faut aussi la
    TUI » est la traduction de `CHOIX_COMPOSANTS -ne 1`.

    Ce qu'elle attrape est donc l'AJOUT d'une condition au garde sans relecture
    de la page, qui est le defaut exact de `C1-9` : la page annoncait une seule
    condition la ou le garde en posait trois. Elle rougit alors avec le chemin
    et la ligne a relire, ce qu'aucun test positif ne ferait.

    Elle n'attrape PAS le cas symetrique -- une page qui perdrait une condition
    sans que le garde bouge. Dit plutot que tu.
    """
    garde = _garde_du_raccourci_shell()
    conditions = re.findall(r"\[\s*\"?\$\{[A-Z_]+\}", garde)
    assert len(conditions) == 3, (
        f"Le garde du raccourci de `{INSTALLATEUR_SH}` pose maintenant "
        f"{len(conditions)} condition(s) et non 3 : "
        f"{conditions}\n"
        "Relire le passage de `docs/installation/linux.md` qui annonce QUAND "
        "le raccourci est propose (« Le raccourci n'est proposé que si… ») : "
        "il enonce ces conditions en prose et se perime en silence.\n"
        "Puis reporter le compte ici.")


def test_le_banc_attrape_les_QUATRE_affirmations_a_chaque_BORD():
    """Le banc se prouve sur des pages fabriquees ici, sans toucher au depot.

    Trois defauts en TETE, au MILIEU et en QUEUE (regle des fabriques,
    point 4), et une page juste entre chaque pour que la lecture ne soit pas
    verte par vacuite.
    """
    # tete : la phrase fautive, sur une page transverse
    tete = "Hors du projet, un seul fichier est ecrit."
    assert _SEUL_FICHIER.search(tete), "la lecture de tete est cassee"
    # milieu : la meme phrase sous une autre tournure
    milieu = "Rien ne les touche. Le seul fichier écrit hors projet est X."
    assert _SEUL_FICHIER.search(milieu), "la lecture du milieu est cassee"
    # queue : une phrase INNOCENTE, qui ne doit PAS etre attrapee comme fautive
    queue = "Chaque chaine de scan a un seul fichier de calibration."
    assert _SEUL_FICHIER.search(queue), "la lecture de queue est cassee"
    assert not re.search(r"(?i)hors\s+(?:du\s+)?projet", queue), (
        "la phrase innocente de QUEUE serait signalee : la frontiere crierait "
        "a tort, et une frontiere qui crie a tort finit desarmee")

    # Et les deux noms de fichier viennent bien des scripts, pas d'ici.
    assert _raccourci_ecrit_par_le_shell().endswith(".desktop")
    assert _raccourci_ecrit_par_powershell().endswith(".lnk")
