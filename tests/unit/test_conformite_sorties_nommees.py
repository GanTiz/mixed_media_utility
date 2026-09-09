# -*- coding: utf-8 -*-
"""La frontiere qui mesure la conformite a `EPIC11-ARB-89`, dans le CODE.

**Ce que cette frontiere ferme, et pourquoi elle existe.** La regle « jamais
une seule sortie face a un conflit d'ecriture » est entree dans `CLAUDE.md` le
2026-08-30 (marqueur `sortie-nommee-jamais-une-seule`). Le mecanisme des
politiques, pose le meme jour, garantit qu'elle ATTEINT toutes les branches --
il ne dit rien de sa conformite dans le code. La revue Opus de la story 5.29 a
mesure l'ecart : la regle etait deja violee a quatre endroits du depot, a
trois ecrans de la ou elle venait d'etre ecrite.

Une regle qu'on se rappelle se perd ; une regle qu'on mesure se tient. C'est
la doctrine de la section « Les politiques de ce fichier se MESURENT » de
`CLAUDE.md`, appliquee ici a la conformite du code plutot qu'a la propagation
de la prose.

## Ce que la frontiere mesure, exactement

Elle recense les sites qui **refusent d'ecrire par-dessus une sortie
existante**, et compare ce releve a un registre de dettes **connues et
datees**. Un site NEUF hors du registre fait rougir : on ne peut plus en
ajouter sans le decider.

Elle ne mesure PAS la qualite de chaque issue -- juger « ce message propose-t-il
vraiment un versionnage » demanderait de lire du francais. Elle mesure ce qui
se compte : le nombre de sites, et leur identite.

## Ce que la frontiere NE fait PAS, dit plutot que tu

Elle ne rougit pas sur les quatre dettes connues : les corriger est un travail
arbitre separement (Egan, 2026-08-30 : « mesurer + consigner la dette »), et
faire rougir le banc pour un travail deja decide et date ne dirait rien de
neuf a personne. Leur entree vit dans `deferred-work.md`.

Elle est fondee sur le CODE SOURCE, jamais sur un intervalle de commits :
c'est deliberement l'inverse du piege `BH-9` de la story 5.27, ou une
frontiere assise sur `git log` devenait vacante au premier squash-merge.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import io
import json
import re
import tokenize
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
SOURCES = RACINE / "src" / "mixed_media_utility"

#: Le motif d'un refus d'ecraser une sortie existante. Volontairement etroit :
#: il attrape la forme idiomatique du depot (`<chemin>.exists() and not
#: <drapeau d'ecrasement>`), pas toute occurrence de `exists()`. Un site qui
#: emploierait une autre forme echapperait -- c'est assume et dit : cette
#: frontiere borne la derive par la forme la plus courante, elle ne pretend
#: pas a l'exhaustivite semantique.
#: **La premiere redaction ratait la forme INVERSEE**, et deux sites du depot
#: l'employaient deja -- dont un dans un fichier que le registre nomme (revue
#: Opus finale). Elle promettait « on ne peut plus en ajouter sans le
#: decider » alors qu'il suffisait d'intervertir les deux termes de la
#: conjonction. Les deux ordres sont desormais reconnus.
MOTIF_REFUS = re.compile(
    r"\.exists\(\)\s+and\s+not\s+(?:args\.)?overwrite\b"
    r"|not\s+(?:args\.)?overwrite\s+and\s+.*\.exists\(\)"
)

#: **Le SECOND motif : la garde de course par `O_EXCL`.** Le premier motif
#: cherche `.exists() and not overwrite`, une forme qui se lit sur UNE ligne.
#: Deux refus du depot n'ont pas cette forme : ils tentent
#: `os.open(..., O_CREAT | O_EXCL)` et refusent sur `FileExistsError`. La
#: couche 3 de la revue du 2026-08-31 les a trouves HORS du registre, alors
#: que ce sont exactement la meme famille que les deux garde-fous de course
#: deja arbitres (`EPIC11-ARB-107`). Les ajouter au registre sans elargir le
#: motif aurait fait rougir le comptage ; les ignorer aurait laisse la
#: frontiere aveugle sur la moitie de sa propre famille.
#: **Ancre sur `os.open(`**, sinon le motif ramasse la PROSE : la premiere
#: redaction attrapait une docstring de `scan_detect` qui explique la
#: technique, et comptait donc un site de plus qu'il n'en existe. Une
#: frontiere qui compte des commentaires ne mesure pas le code.
MOTIF_COURSE = re.compile(
    r"os\.open\(.*(?:O_CREAT\s*\|\s*os\.O_EXCL|O_EXCL\s*\|\s*os\.O_CREAT)")

#: Les SITES DE REFUS recenses, avec leur etat de conformite.
#:
#: **Cette table ne mesure pas la conformite, elle recense les sites** -- la
#: nuance a ete payee : les cinq entrees etaient toutes libellees « dette »
#: quand elles ont ete posees le 2026-08-30, et elles le sont restees apres
#: que trois d'entre elles ont ete mises en conformite le 2026-08-31. Le banc
#: restait vert (il ne compte que les sites), donc la frontiere mentait sur
#: son propre releve sans rien faire rougir. Trouve par DEUX couches de la
#: revue.
#:
#: Un site de refus n'est pas un defaut en soi : `EPIC11-ARB-89` demande qu'un
#: conflit d'ecriture propose AU MOINS DEUX issues, pas qu'il n'y ait aucun
#: refus. Un refus par defaut, assorti de ses issues, est la forme correcte.
#: Ce que cette frontiere garantit est plus modeste et suffisant : **aucun
#: site de refus NEUF n'apparait sans etre inscrit ici**, donc aucun ne se
#: glisse sans qu'on ait regarde ses issues.
DETTES_CONNUES = {
    # --- Mis en conformite le 2026-08-31 (`EPIC11-ARB-91`) ---------------
    # Trois issues, mesurees de bout en bout par `test_makepdf_command.py`.
    # **Le fichier a change le 2026-09-02, pas le site** (story 11.7, lot B) :
    # le corps de `makepdf_command` a ete DEPLACE dans le module de coeur
    # `makepdf.py`, et le refus l'a suivi verbatim. Le registre nomme le
    # fichier ou le refus vit, donc il suit lui aussi -- le laisser sur
    # `cli.py` aurait fait rougir le comptage sur un site qui n'a pas bouge.
    ("makepdf.py", "makepdf : le PDF de planches -- CONFORME depuis 2026-08-31 "
                   "(--nouvelle-version, --overwrite, project remove) ; "
                   "DEPLACE de cli.py au coeur le 2026-09-02 (story 11.7)"),
    # Trois issues, dont UNE NON DESTRUCTIVE (changer --chaine, qui entre dans
    # le nom). Les deux d'origine detruisaient toutes deux le fichier, au motif
    # -- mesure comme faux -- que deux tirages de la meme chaine seraient le
    # meme document : huit parametres de geometrie font varier la page sans
    # entrer dans son nom.
    ("makepdf.py", "makepdf calibration-page -- CONFORME depuis 2026-08-31 "
                   "(--chaine, --overwrite, suppression) ; DEPLACE de cli.py "
                   "au coeur le 2026-09-02 (story 11.7)"),
    # Trois issues, mesurees par `test_versions_de_master.py`.
    ("encode.py", "encode : le master, decision d'encodage -- CONFORME depuis "
                  "2026-08-31 (--nouvelle-version, --overwrite, project remove)"),
    # --- Une issue unique, ARBITREE ET ASSUMEE (Egan, 2026-08-31) ---------
    # Ces deux refus ne sont PAS un dialogue avec l'operateur: la commande a
    # deja verifie la destination a son entree et lui a propose trois issues.
    # Ceux-ci ne se declenchent que si le fichier est apparu DEPUIS, donc si un
    # autre encodage s'est glisse dans l'intervalle. La bonne reponse y est
    # « recommencez » et non un menu: le rang resolu au debut de la commande
    # n'est plus fiable, puisque quelqu'un vient de le consommer, et proposer
    # un rang qui pourrait etre pris a son tour serait pire que de se taire.
    #
    # Ce ne sont donc pas des dettes mais des garde-fous internes, et le motif
    # est nomme ici POUR qu'une revue future ne les rouvre pas comme un oubli.
    ("codec_profiles.py", "encode : garde-fou de course, refus courtois avant "
                          "la sonde -- une issue ARBITREE (Egan 2026-08-31)"),
    ("codec_profiles.py", "encode : garde-fou de course, forme inversee -- "
                          "une issue ARBITREE (Egan 2026-08-31)"),
    # --- Meme famille, vue par le SECOND motif (revue du 2026-08-31) -------
    # Ces deux-ci reservent le chemin par `O_CREAT | O_EXCL` et refusent sur
    # `FileExistsError`. Le motif d'origine ne les voyait pas, et le registre
    # se croyait complet -- il declarait meme ne connaitre qu'UN seul angle
    # mort. Le motif de leur issue unique est celui d'`EPIC11-ARB-107`, mot
    # pour mot : la commande a deja propose ses issues a son entree, et ce
    # refus-ci ne se declenche que si le fichier est apparu DEPUIS.
    ("codec_profiles.py", "encode : reservation atomique du chemin de sortie "
                          "-- une issue, meme motif qu'EPIC11-ARB-107"),
    # **Mis en conformite le 2026-09-03** (story 11.8, AC 4.7). Ce site etait
    # RECENSE ici et non conforme : une issue unique, et destructive. Le motif
    # d'`EPIC11-ARB-107` tient toujours -- proposer un RANG calcule dans ce
    # refus serait proposer un rang qui peut etre pris a son tour -- mais il
    # n'interdisait pas de nommer la RELANCE, qui resout le rang a nouveau
    # contre le manifeste et ne detruit rien. Son jumeau de `codec_profiles.py`
    # reste en l'etat : il ne resout aucun rang, donc la relance n'y change
    # rien, et son issue unique reste celle qu'Egan a arbitree.
    ("encode.py", "encode : reservation atomique du master -- CONFORME depuis "
                  "2026-09-03 (relance qui reresout le rang, --overwrite) ; "
                  "recense au titre d'EPIC11-ARB-107"),
    # --- CONFORME, et trouve par l'elargissement du motif -----------------
    # Ni une dette ni un garde-fou : c'est un VERSIONNAGE. Sur collision, ce
    # site prend un suffixe `-2`, `-3`, ... au lieu d'ecraser, ce qui est
    # exactement la forme qu'`EPIC11-ARB-89` demande -- jamais un blocage sec,
    # jamais un ecrasement silencieux. Il est inscrit parce que le registre
    # RECENSE les sites (il ne mesure pas la conformite), et parce qu'un site
    # non inscrit ferait rougir le comptage.
    ("scan_detect.py", "detection : reservation atomique du nom de document -- "
                       "CONFORME, versionne par suffixe au lieu d'ecraser"),
}

#: **Un site que ce motif ne peut PAS voir, nomme plutot que tu.**
#: `scan_output_frames.py` refuse d'ecraser une frame de sortie par
#: `if existing and not overwrite:` -- ou `existing` est un booleen calcule
#: plus haut, sans `.exists()` sur la ligne. Aucune expression reguliere
#: raisonnable ne l'attrape sans ramasser tout le depot. Il est donc consigne
#: ICI, en clair, plutot que compte parmi les dettes que la frontiere mesure :
#: une frontiere qui pretendrait le voir mentirait sur sa propre portee.
SITE_HORS_PORTEE_DU_MOTIF = (
    "scan_output_frames.py",
    "scan : frame de sortie deja presente -- `if existing and not overwrite:`, "
    "le booleen est calcule plus haut, la ligne ne porte pas `.exists()`",
)


def _sites_de_refus() -> list[tuple[str, int]]:
    """(nom de fichier, numero de ligne) de chaque refus d'ecrasement."""
    releve: list[tuple[str, int]] = []
    for chemin in sorted(SOURCES.rglob("*.py")):
        for numero, ligne in enumerate(
            chemin.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if MOTIF_REFUS.search(ligne) or MOTIF_COURSE.search(ligne):
                releve.append((chemin.name, numero))
    return releve


def test_aucun_site_de_refus_NEUF_hors_du_registre_des_dettes():
    """Le volet qui mord : on ne peut plus ajouter une sortie non conforme
    sans le decider explicitement.

    Si ce test rougit sur du code que vous venez d'ecrire, c'est que votre
    nouvelle sortie ne propose qu'une seule issue. Deux gestes possibles :
    lui donner sa seconde issue (un versionnage, sur le modele de
    `extraction.run_extraction(nouvelle_version=...)`), ou -- si c'est un
    choix -- l'inscrire dans `DETTES_CONNUES` avec son motif ET dans
    `deferred-work.md`. Le second geste est un arbitrage, pas une formalite.
    """
    releve = _sites_de_refus()
    fichiers = sorted({nom for nom, _ in releve})
    attendus = sorted({nom for nom, _ in DETTES_CONNUES})
    assert fichiers == attendus, (
        f"Sites de refus d'ecrasement releves dans {fichiers}, attendus dans "
        f"{attendus}. Un site NEUF ne propose qu'une seule issue -- "
        "`EPIC11-ARB-89` en exige au moins deux. Voir la docstring de ce test."
    )
    assert len(releve) == len(DETTES_CONNUES), (
        f"{len(releve)} site(s) de refus releve(s) pour {len(DETTES_CONNUES)} "
        f"dette(s) connue(s) : {releve}. Un site a ete ajoute ou retire sans "
        "que le registre suive."
    )


def test_la_frontiere_MORD_vraiment(tmp_path):
    """Controle negatif, sans lequel le test ci-dessus pourrait etre vert et
    vide : le motif doit reellement reconnaitre la forme qu'il cherche.

    Le piege `F3` de la premiere passe de revue de cette story etait
    exactement celui-la -- un test d'atomicite vert pour une ecriture NON
    atomique, parce qu'il ne mesurait rien.
    """
    assert MOTIF_REFUS.search("if output_path.exists() and not args.overwrite:")
    assert MOTIF_REFUS.search("        if output_path.exists() and not overwrite:")
    # La forme INVERSEE, que la premiere redaction ratait alors que deux sites
    # du depot l'employaient deja.
    assert MOTIF_REFUS.search("if not overwrite and Path(output_path).exists():")
    # La forme sans `.exists()` sur la ligne reste HORS de portee, et c'est
    # dit : voir `SITE_HORS_PORTEE_DU_MOTIF`.
    assert MOTIF_REFUS.search("        if existing and not overwrite:") is None
    assert MOTIF_REFUS.search("if not args.overwrite and chemin.exists():")
    assert not MOTIF_REFUS.search("if output_path.exists():")
    assert not MOTIF_REFUS.search("if not output_path.exists():")

    # Le SECOND motif, celui des gardes de course.
    assert MOTIF_COURSE.search(
        "handle = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)")
    assert MOTIF_COURSE.search("os.open(p, os.O_EXCL | os.O_CREAT)")
    # Et il ne ramasse pas une ouverture ordinaire.
    assert not MOTIF_COURSE.search("handle = os.open(p, os.O_WRONLY)")
    # Ni la PROSE qui explique la technique -- le defaut de sa premiere
    # redaction, qui comptait une docstring comme un site.
    assert not MOTIF_COURSE.search(
        "    Le nom est reserve par creation exclusive (`os.O_CREAT | os.O_EXCL`,")


def test_le_site_HORS_PORTEE_est_reellement_hors_de_portee():
    """La constante etait DECORATIVE : definie, commentee, jamais assertee.

    Trouve en revue (couche 3). Une note qui dit « ce site echappe au motif »
    sans le mesurer devient fausse en silence le jour ou le code change de
    forme -- et c'est alors la frontiere qui ment sur sa propre portee, ce que
    sa docstring promet justement de ne pas faire.
    """
    fichier, description = SITE_HORS_PORTEE_DU_MOTIF
    assert fichier not in {nom for nom, _ in DETTES_CONNUES}, (
        f"{fichier} figure au registre : il n'est plus hors de portee, la note "
        "doit etre retiree."
    )
    # La forme exacte que la note decrit reste invisible aux DEUX motifs.
    ligne = "        if existing and not overwrite:"
    assert MOTIF_REFUS.search(ligne) is None
    assert MOTIF_COURSE.search(ligne) is None
    assert "existing" in description


def test_le_mecanisme_de_la_story_529_est_CONFORME_lui():
    """Le chemin d'extraction, lui, offre bien DEUX issues.

    Sans ce test, la frontiere ne mesurerait que des dettes : elle dirait ce
    qui n'est pas conforme sans jamais verifier que quelque chose l'est. Le
    refus de transition d'etat doit nommer ses issues, et le mecanisme doit
    les exposer.
    """
    import inspect

    from mixed_media_utility import extraction
    from mixed_media_utility.io import extraction_manifest

    parametres = inspect.signature(extraction.run_extraction).parameters
    assert "nouvelle_version" in parametres, "l'issue de versionnage a disparu"
    assert "ecrasement_conscient" in parametres, "l'issue d'ecrasement a disparu"

    source = inspect.getsource(extraction_manifest.validate_extraction_state_transition)
    assert "nouvelle version" in source, "le refus ne nomme plus l'issue de versionnage"
    assert "SCIEMMENT" in source, "le refus ne nomme plus l'issue d'ecrasement conscient"


# ---------------------------------------------------------------------------
# La frontiere qui ferme la classe de defaut « le refus nomme une sortie qui
# n'existe pas » (`EPIC11-ARB-89`, trouve en revue les couches 2 et 3).
#
# Quatre refus d'epuisement de rang proposaient en PREMIERE issue un geste sans
# commande -- « supprimer le DERNIER scan de ce slug en liberant son rang »
# alors qu'aucune commande ne supprime un scan seul. Un operateur y va et ne
# trouve rien : c'est un blocage sec deguise, aussi fautif qu'un refus sans
# issue.
# ---------------------------------------------------------------------------

#: **Le tiret ne peut plus ouvrir un MOT de commande** (mutant survivant,
#: revue 11.14 couche 1). Le tiret appartient a la classe de caracteres des
#: deux mots -- il le faut, `scan-write` et `set-default-profile` en portent
#: un --, mais rien n'empechait le SECOND mot d'avaler le premier drapeau :
#: sur une commande d'UN SEUL mot, `mmu encode --drapeau-fantome` se lisait
#: comme la commande « encode --drapeau-fantome » sans aucun drapeau, et
#: `if options:` jetait la citation **en silence**. Mesure du mutant : deux
#: refus citant `mmu encode --drapeau-fantome <x>` et
#: `mmu extract --option-qui-nexiste-pas` laissaient les 7 tests AU VERT.
#: Le seul cas jamais exerce etait celui a deux mots (`project remove`),
#: c'est-a-dire le seul qui marchait -- voila pourquoi le trou n'a jamais ete vu.
#: Le `(?!-)` s'ecrit en tete des DEUX mots : sur le premier il interdit
#: `mmu --version` de passer pour une commande, sur le second il rend au
#: groupe des drapeaux ce qui lui appartient.
#: **Une valeur citee peut etre LITTERALE, pas seulement un gabarit**
#: (revue `EPIC11-ARB-224`, fermeture de `C1-02`/`C2-10`/`F1`). La redaction
#: d'avant n'acceptait qu'un `<gabarit>` apres un drapeau : un refus qui
#: nomme le profil reel -- `--profile prores_422` -- voyait la citation
#: TRONQUEE a cet endroit, et tout ce qui suivait (`--version`,
#: `--liberer-le-rang`, `--confirmer`) sortait de la portee de la frontiere
#: sans un mot. La classe de valeur exclut le tiret en tete, sans quoi elle
#: avalerait le drapeau suivant.
_MOTIF_VALEUR = r"(?:<[^>]*>|[A-Za-z0-9][A-Za-z0-9_.:/@=+-]*)"
_MOTIF_COMMANDE = re.compile(
    r"`mmu ((?!-)[a-z-]+(?: (?!-)[a-z-]+)?)"
    r"((?: --?[a-z-]+(?: " + _MOTIF_VALEUR + r")?)*)")

#: Le decoupage d'un releve de drapeaux en couples (drapeau, valeur ou None).
#: C'est l'ARITE citee, celle que la frontiere de rejeu confronte au parseur.
_MOTIF_JETON = re.compile(r"(--[a-z-]+)(?: (" + _MOTIF_VALEUR + r"))?")


def _rendu_d_un_f_string(noeud: ast.JoinedStr) -> str:
    """Un `f"..."` rendu en texte, ses interpolations vues comme des gabarits.

    **Troisieme angle mort de la meme famille**, ferme avec `C1-02`. La note
    de `_textes_des_sources` raconte deja les deux premiers : le balayage de
    texte, puis les litteraux adjacents. Un message construit par f-string est
    le suivant -- `ast.walk` n'y voit que les MORCEAUX constants, si bien
    qu'une citation qui enjambe une interpolation est coupee en deux et que
    chaque moitie devient illisible. Rendre l'interpolation comme un `<...>`
    recolle le message tel que l'operateur le lira, et donne au rejeu une
    valeur a substituer.
    """
    return "".join(
        valeur.value if isinstance(valeur, ast.Constant)
        and isinstance(valeur.value, str) else "<...>"
        for valeur in noeud.values
    )


def _textes_des_sources():
    """(fichier, ligne, texte) pour chaque chaine du code source.

    **Les chaines sont lues par AST, pas par balayage de texte** (trouve en
    mutation, apres la revue). Un message de refus tient rarement sur une
    ligne : Python recolle les litteraux adjacents, mais le TEXTE source les
    separe par un guillemet et un saut de ligne. Le motif appliqué au texte ne
    voyait donc que le debut de chaque message -- mesure : citer `--overwrite`
    sur `mmu project remove` passait, parce que le drapeau tombait apres la
    coupure. La frontiere ne mesurait qu'une PARTIE de chaque message, et rien
    ne le disait.

    Un `ast.JoinedStr` est rendu ENTIER et l'on ne descend pas dedans : sans
    cette borne, ses morceaux constants seraient comptes une seconde fois,
    tronques.
    """
    racine = Path(__file__).resolve().parents[2] / "src" / "mixed_media_utility"
    for fichier in sorted(racine.rglob("*.py")):
        nom = fichier.relative_to(racine).as_posix()
        pile = [ast.parse(fichier.read_text(encoding="utf-8"))]
        while pile:
            noeud = pile.pop()
            if isinstance(noeud, ast.JoinedStr):
                yield (nom, noeud.lineno, _rendu_d_un_f_string(noeud))
                continue
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
                yield (nom, noeud.lineno, noeud.value)
            pile.extend(ast.iter_child_nodes(noeud))


def _citations_des_sources():
    """(fichier, ligne, commande, jetons) pour chaque `mmu ...` cite.

    `jetons` porte l'ARITE telle qu'elle est ecrite : une suite de couples
    `(drapeau, valeur citee ou None)`. C'est ce que la frontiere de rejeu
    confronte au parseur, et c'est exactement ce que la frontiere d'EXISTENCE
    jetait.
    """
    for fichier, ligne, texte in _textes_des_sources():
        for commande, drapeaux in _MOTIF_COMMANDE.findall(texte):
            jetons = tuple(_MOTIF_JETON.findall(drapeaux))
            if jetons:
                yield (fichier, ligne, commande,
                       tuple((option, valeur or None) for option, valeur in jetons))


def _commandes_citees_dans_les_sources():
    """Chaque `mmu ... --drapeau` cite dans une chaine du code source.

    Adaptateur de `_citations_des_sources` : il JETTE la valeur et ne garde
    que les noms. C'est ce que mesure la frontiere d'EXISTENCE -- et c'est
    precisement pourquoi elle ne pouvait pas voir `C1-02`.
    """
    for fichier, _ligne, commande, jetons in _citations_des_sources():
        yield (fichier, commande, tuple(option for option, _ in jetons))


def _drapeaux_par_commande() -> dict[str, set[str]]:
    """Les `--drapeau` de chaque commande, lus du PARSEUR REELLEMENT CONSTRUIT.

    **Ce lecteur n'est pas ecrit ici : il est emprunte au banc voisin**
    (`test_conformite_de_la_documentation._drapeaux_par_commande`, ecrit par
    le lot D3 de la story 11.14). Deux redactions du meme lecteur dans une
    meme story, c'est deux verites -- et la story avait deja **mesure** que
    celle-ci etait la fausse sans la debrancher (`D3-3` de
    `deferred-work.md`).

    Ce qui a ete mesure, et qui a decide de la bascule (revue 11.14, couche 1) :

    ========================  ====================================
    lecteur AST (ici, avant)  11 entrees, dont une vide -- 10 commandes
    lecteur PARSEUR (voisin)  17 commandes
    invisibles a l'AST        poc, project, relink, scan calibrate,
                              scan detect, scan-write,
                              set-default-profile
    ========================  ====================================

    Sur `scan`, l'AST ne voyait ni `--profil`, ni `--cc`, ni
    `--garder-le-scan-brut`, ni
    `--appliquer-la-correction-de-calibration-telle-quelle` : un refus JUSTE
    citant `mmu scan --profil <id>` etait donc hors de portee de la
    frontiere, et un refus FAUX sur ces sept commandes-la aussi.

    **Le motif ecrit de l'ancien lecteur est tombe.** Il disait : « lu au
    SOURCE et non sur un parseur construit : `main` batit le sien en local et
    ne l'expose pas, donc un test qui l'appellerait serait saute ». Le lot D3
    a montre que non -- on intercepte le premier `parse_args`, ou le parseur
    est complet et rien n'a encore ete execute. Un lecteur AST de la CLI
    reconstitue la construction d'argparse a la main ; il perd tout ce qu'un
    auxiliaire pose.
    """
    from test_conformite_de_la_documentation import (
        _drapeaux_par_commande as _du_parseur)

    return _du_parseur()


def test_tout_drapeau_cite_dans_un_message_EXISTE_sur_SA_commande():
    """Un message qui cite `mmu project remove --x` doit trouver `--x` SUR
    `project remove`, pas ailleurs dans la CLI."""
    par_commande = _drapeaux_par_commande()
    # Garde-fou : si la lecture cassait, tout passerait pour vert.
    assert "--liberer-le-rang" in par_commande.get("project remove", set()), (
        f"la lecture des drapeaux par commande a rendu {par_commande!r} : la "
        "frontiere ne mesure plus rien."
    )

    inconnus = []
    for fichier, commande, options in _commandes_citees_dans_les_sources():
        connus = par_commande.get(commande)
        if connus is None:
            inconnus.append(f"{fichier}: `mmu {commande}` n'est pas une commande")
            continue
        for option in options:
            if option not in connus:
                inconnus.append(
                    f"{fichier}: `mmu {commande}` n'accepte pas {option}")
    assert inconnus == [], (
        "Ces messages citent une commande ou un drapeau qui n'existe pas sur "
        "elle. Un refus qui nomme une sortie inexistante est un blocage sec "
        "deguise (EPIC11-ARB-89):\n  " + "\n  ".join(inconnus)
    )


def test_la_frontiere_par_COMMANDE_mord_la_ou_la_plate_ne_mordait_pas():
    """Le controle negatif qui manquait : un drapeau REEL mais d'une AUTRE commande.

    C'est le trou exact de la premiere redaction. Il ne se voit pas en testant
    un drapeau invente -- celui-la, meme une frontiere plate l'attrape.
    """
    par_commande = _drapeaux_par_commande()
    remove = par_commande.get("project remove", set())
    assert "--overwrite" not in remove, (
        "`--overwrite` est devenu un drapeau de `project remove` : ce controle "
        "negatif doit etre reecrit sur un autre drapeau."
    )
    # Il existe pourtant ailleurs dans la CLI : c'est ce qui rendait la
    # frontiere plate aveugle.
    assert any("--overwrite" in d for d in par_commande.values())


def test_le_motif_lit_les_drapeaux_d_une_commande_d_UN_SEUL_MOT():
    """Le controle negatif qui manquait, et c'est un mutant qui l'a exige.

    La frontiere n'exercait que des commandes a DEUX mots (`project remove`),
    c'est-a-dire le seul cas ou l'ancien motif marchait. Sur un seul mot, le
    second mot optionnel avalait le premier drapeau et la citation etait
    jetee sans un mot : deux refus inventes -- `mmu encode --drapeau-fantome`
    et `mmu extract --option-qui-nexiste-pas` -- laissaient les 7 tests au
    vert (revue 11.14, couche 1).

    Les trois formes sont exercees ENSEMBLE, aux deux bords de la grammaire :
    un mot, deux mots, et un mot dont le nom PORTE un tiret (`scan-write`),
    qui est la raison pour laquelle le tiret doit rester dans la classe.
    """
    cas = {
        "`mmu encode --drapeau-fantome <x>`": ("encode", ["--drapeau-fantome"]),
        "`mmu scan --profil <id>`": ("scan", ["--profil"]),
        "`mmu scan-write --overwrite`": ("scan-write", ["--overwrite"]),
        "`mmu project remove --lot <id> --lot-scanne --version <r>`":
            ("project remove", ["--lot", "--lot-scanne", "--version"]),
    }
    for texte, (commande_attendue, drapeaux_attendus) in cas.items():
        trouves = _MOTIF_COMMANDE.findall(texte)
        assert trouves, f"le motif ne reconnait meme pas {texte!r}"
        commande, drapeaux = trouves[0]
        assert commande == commande_attendue, (texte, commande)
        assert re.findall(r"--[a-z-]+", drapeaux) == drapeaux_attendus, (
            texte, drapeaux)


def test_le_lecteur_de_drapeaux_est_bien_celui_du_PARSEUR_construit():
    """Volet symetrique : la bascule de lecteur se mesure, elle ne se raconte pas.

    Sept commandes etaient invisibles a l'ancien lecteur AST -- dont `scan`,
    `project` et `scan-write`, qui portent l'essentiel des refus du depot. Une
    frontiere qui ne voit pas la commande ne peut refuser aucun de ses
    drapeaux : elle passe, muette.
    """
    table = _drapeaux_par_commande()
    for commande in ("poc", "project", "relink", "scan calibrate",
                     "scan detect", "scan-write", "set-default-profile"):
        assert commande in table, (
            f"`{commande}` a disparu du lecteur : la frontiere redevient "
            "aveugle sur cette commande, comme l'etait le lecteur AST.")
    assert {"--profil", "--cc", "--garder-le-scan-brut"} <= table["scan"], (
        "les drapeaux de `scan` ne sont plus lus : c'est exactement ce que "
        "l'ancien lecteur AST manquait.")


def test_la_frontiere_precedente_MORD(tmp_path):
    """Controle negatif : un drapeau invente doit bien etre attrape.

    Sans lui, un motif de recherche trop etroit -- ou un parseur qui rendrait
    tout -- ferait passer la frontiere pour verte sans qu'elle mesure rien.
    """
    faux = tmp_path / "faux.py"
    faux.write_text(
        'MESSAGE = "Issue: `mmu project remove --lot <id> --drapeau-invente`"\n',
        encoding="utf-8")
    trouves = list(_MOTIF_COMMANDE.findall(faux.read_text(encoding="utf-8")))
    assert trouves, "le motif ne reconnait meme pas une commande citee"
    options = re.findall(r"--[a-z-]+", trouves[0][1])
    assert "--drapeau-invente" in options


# ---------------------------------------------------------------------------
# LA FRONTIERE D'ARITE, ET LE REJEU CONTRE LE VRAI PARSEUR
#
# **Ce qu'elle ferme, et pourquoi la frontiere d'a cote ne pouvait pas le
# voir.** `test_tout_drapeau_cite_dans_un_message_EXISTE_sur_SA_commande`
# mesure le NOM d'un drapeau et JETTE sa valeur : elle est donc
# structurellement aveugle a l'ARITE. Un drapeau qui passe de « prend un
# argument » a « drapeau nu » lui reste invisible -- et `EPIC11-ARB-224` a
# fait exactement cela a quatre drapeaux le meme jour (`--planche`,
# `--master`, `--lot-scanne` devenus nus ; `--profile` et `--resolution`
# apparus).
#
# Le defaut paye : le refus d'epuisement des rangs de master d'`encode`
# proposait en PREMIERE issue `mmu project remove ... --master <chemin de
# famille> ...`. `argparse` rendait `unrecognized arguments` (code 2), et meme
# sans le jeton parasite le coeur refusait, `--profile` etant desormais exige.
# Des deux issues annoncees il ne restait que `--overwrite`, la destructrice :
# le « blocage sec deguise » qu'`EPIC11-ARB-89` interdit. Trois couches de
# revue l'ont trouve independamment (`C1-02`, `C2-10`, `F1`), deux d'entre
# elles sans lire le contrat -- et les 391 tests du perimetre restaient verts.
#
# LA REGLE QUE CETTE FRONTIERE POSE : une issue nommee dans un refus doit etre
# une commande qu'on peut TAPER, qui PARSE, et qui CHANGE quelque chose. Les
# trois se mesurent ci-dessous, et aucune ne se mesure par comparaison de
# chaines -- une frontiere qui comparerait des chaines refabriquerait le
# defaut du jour a un cran de plus.
# ---------------------------------------------------------------------------


def _parseur_reel():
    """Le parseur que `cli.main` construit, emprunte au banc voisin.

    Meme motif que `_drapeaux_par_commande` : deux redactions du meme lecteur
    dans un meme depot, c'est deux verites.
    """
    from test_conformite_de_la_documentation import _parseur_reel as _emprunte

    return _emprunte()


def _sous_parseur(parseur, mots):
    """Le (sous-)parseur qui porte la commande `mots`, ou `None`."""
    for mot in mots:
        for action in parseur._actions:
            if (isinstance(action, argparse._SubParsersAction)
                    and mot in action.choices):
                parseur = action.choices[mot]
                break
        else:
            return None
    return parseur


def _prend_une_valeur(action) -> bool:
    """L'ARITE declaree du drapeau, lue de l'action et non de son nom."""
    return action.nargs != 0 and not isinstance(action, (
        argparse._StoreTrueAction, argparse._StoreFalseAction,
        argparse._StoreConstAction, argparse._CountAction,
        argparse._AppendConstAction, argparse._HelpAction,
        argparse._VersionAction))


#: Les valeurs d'essai, dans l'ordre. **Elles sont ESSAYEES contre le `type=`
#: de l'action, jamais devinees d'apres son nom** : une frontiere qui rendrait
#: `"X"` a un drapeau `type=float` ferait rougir sur `invalid float value`,
#: c'est-a-dire sur sa propre substitution et non sur la citation. Le defaut a
#: ete mesure en balayant `docs/` avec une premiere redaction : douze faux
#: fautifs, tous sur `--fps`.
_VALEURS_D_ESSAI = ("1", "X", "1.0")


def _valeur_plausible(action) -> str:
    """Une valeur que le parseur ACCEPTE pour ce drapeau-la.

    Lue de l'action : ses `choices` d'abord (sinon `--profile` serait refuse
    pour la mauvaise raison), puis la premiere valeur d'essai que son `type=`
    convertit sans broncher. La frontiere mesure l'arite, pas la validite
    semantique d'une valeur inventee -- et une valeur refusee pour son TYPE
    dirait autre chose que ce qu'elle mesure.
    """
    if action.choices:
        return str(sorted(map(str, action.choices))[0])
    if action.type is None:
        return "X"
    for essai in _VALEURS_D_ESSAI:
        try:
            action.type(essai)
        except Exception:
            continue
        return essai
    return "X"


def _argv_de_la_citation(sous_parseur, commande: str, jetons,
                         valeurs=None) -> list[str]:
    """La ligne de commande que la citation dit de TAPER, prete pour argparse.

    Deux completions, et elles sont dites plutot que tues :

    * un `<gabarit>` cite est remplace par une valeur que le parseur accepte --
      substituer un gabarit est ce que l'operateur fait de toute facon ;
    * les options REQUISES que la citation ne porte pas sont ajoutees (ainsi
      `--project`, qu'aucun des quatre refus jumeaux ne cite). Un message de
      refus est un patron, pas une ligne complete : le penaliser pour son
      contexte implicite ferait rougir les quatre a la fois et la frontiere ne
      dirait plus rien de l'arite, qui est ce qu'elle mesure.

    `valeurs` impose la valeur de certains drapeaux -- le volet « qui CHANGE
    quelque chose » y met le projet et le lot REELS, sans quoi la cible serait
    inconnue du manifeste et la question posee serait masquee par une autre.
    """
    valeurs = valeurs or {}
    argv = commande.split()
    cites: set[str] = set()

    def _valeur(action, option):
        if option in valeurs:
            return valeurs[option]
        return _valeur_plausible(action) if action is not None else "X"

    for option, valeur_citee in jetons:
        argv.append(option)
        cites.add(option)
        if valeur_citee is not None:
            action = next((a for a in sous_parseur._actions
                           if option in a.option_strings), None)
            argv.append(_valeur(action, option))

    def _completer(action):
        option = action.option_strings[-1]
        argv.append(option)
        cites.add(option)
        if _prend_une_valeur(action):
            argv.append(_valeur(action, option))

    for action in sous_parseur._actions:
        if (getattr(action, "required", False) and action.option_strings
                and not (cites & set(action.option_strings))):
            _completer(action)
    # Un groupe mutuellement exclusif REQUIS ne marque aucune de ses actions
    # `required` : sans ce second passage, `--lot`/`--rush` manquerait et la
    # frontiere rougirait sur toutes les citations de `project remove`.
    for groupe in sous_parseur._mutually_exclusive_groups:
        if groupe.required and not any(
                set(a.option_strings) & cites for a in groupe._group_actions):
            _completer(groupe._group_actions[0])
    return argv


def _rejouer(parseur, argv):
    """(namespace, code de sortie, message) -- le VRAI `parse_args`.

    Jamais une reconstitution de la grammaire : c'est l'objet `argparse` que
    `cli.main` construit qui rend le verdict, comme il le rendrait a
    l'operateur.
    """
    erreur = io.StringIO()
    try:
        with contextlib.redirect_stderr(erreur), \
                contextlib.redirect_stdout(io.StringIO()):
            return parseur.parse_args(argv), 0, ""
    except SystemExit as sortie:
        lignes = erreur.getvalue().strip().splitlines()
        return None, sortie.code, lignes[-1] if lignes else ""


def test_toute_commande_citee_dans_un_message_SE_PARSE_pour_de_vrai():
    """Volet « qu'on peut TAPER » : la citation passe le parseur reel.

    C'est la frontiere d'ARITE. Elle mord dans les DEUX sens sans avoir a les
    distinguer, parce que c'est `argparse` qui tranche : une valeur donnee a
    un drapeau nu rend `unrecognized arguments`, un drapeau a valeur cite nu
    rend `expected one argument`. Les deux sont le code 2.
    """
    parseur = _parseur_reel()
    relevees = list(_citations_des_sources())
    # **Garde-fou de CABLAGE, et il est load-bearing.** L'issue d'`encode` est
    # construite par f-string : si `_textes_des_sources` cessait de recoller
    # les f-strings, la citation serait coupee AVANT `--profile` et la
    # frontiere deviendrait muette sur la ligne meme qu'elle vient de
    # corriger -- muette, donc VERTE. Mesurer que le releve la voit ENTIERE
    # est le seul moyen de tuer ce mutant-la.
    assert any(
        fichier == "encode.py" and commande == "project remove"
        and [option for option, _ in jetons] == [
            "--lot", "--master", "--profile", "--version",
            "--liberer-le-rang", "--confirmer"]
        for fichier, _ligne, commande, jetons in relevees), (
        "l'issue du refus de rangs epuises d'`encode.py` n'est plus relevee "
        "ENTIERE : le lecteur ne recolle plus les f-strings, ou le motif "
        "tronque sur la valeur litterale. La frontiere est aveugle la ou elle "
        "doit mordre.\n  " + "\n  ".join(
            f"{f}:{l}: mmu {c} {[o for o, _ in j]}"
            for f, l, c, j in relevees if f == "encode.py"))
    fautifs = []
    for fichier, ligne, commande, jetons in relevees:
        sous = _sous_parseur(parseur, commande.split())
        if sous is None:
            # L'existence de la commande est la frontiere d'a cote ; ici on ne
            # peut rien rejouer.
            continue
        argv = _argv_de_la_citation(sous, commande, jetons)
        _, code, message = _rejouer(parseur, argv)
        if code:
            cite = " ".join(
                option + (f" {valeur}" if valeur else "")
                for option, valeur in jetons)
            fautifs.append(
                f"{fichier}:{ligne}: `mmu {commande} {cite}` -- code {code} : "
                f"{message}")
    assert fautifs == [], (
        "Ces messages nomment une issue qu'argparse REFUSE. Une issue qu'on "
        "ne peut pas taper n'est pas une issue : c'est un blocage sec deguise "
        "(EPIC11-ARB-89), et le refus n'en laisse alors qu'une, la "
        "destructrice.\n  " + "\n  ".join(fautifs))


#: **Les QUATRE drapeaux dont `EPIC11-ARB-224` a change l'arite le meme jour**
#: -- trois devenus nus, deux apparus a valeur. Le controle negatif les exerce
#: TOUS : n'en exercer qu'un laisserait la frontiere aveugle sur les autres,
#: et c'est litteralement ce qui vient d'arriver a la frontiere d'existence.
_DRAPEAUX_NUS = ("--planche", "--master", "--lot-scanne")
_DRAPEAUX_A_VALEUR = ("--profile", "--resolution", "--version")


@pytest.mark.parametrize("drapeau", _DRAPEAUX_NUS)
def test_la_frontiere_de_REJEU_mord_sur_une_VALEUR_donnee_a_un_DRAPEAU_NU(drapeau):
    """Volet de morsure, sens 1 -- exactement le defaut `C1-02`/`C2-10`/`F1`.

    Sans ce controle, la frontiere pourrait ne rien mesurer et rester verte :
    c'est ce qui est arrive a la frontiere d'existence pendant tout le diff
    d'`EPIC11-ARB-224`. Les trois drapeaux nus sont exerces, pas seulement
    `--master` : c'est le SITE qui a ete manque, pas la classe, et rien ne dit
    que le prochain sera celui-la.
    """
    parseur = _parseur_reel()
    sous = _sous_parseur(parseur, ["project", "remove"])
    action = next(a for a in sous._actions if drapeau in a.option_strings)
    assert not _prend_une_valeur(action), (
        f"`{drapeau}` a repris une valeur : ce controle negatif doit etre "
        "reecrit, ou le contrat a change.")
    jetons = (("--lot", "<id>"), (drapeau, "<chemin de famille>"),
              ("--version", "<rang>"), ("--liberer-le-rang", None),
              ("--confirmer", None))
    argv = _argv_de_la_citation(sous, "project remove", jetons)
    _, code, message = _rejouer(parseur, argv)
    assert code == 2, (
        f"la forme fautive passe sur {drapeau} : la frontiere est morte")
    assert "unrecognized" in message, message


@pytest.mark.parametrize("drapeau", _DRAPEAUX_A_VALEUR)
def test_la_frontiere_de_REJEU_mord_sur_un_drapeau_a_VALEUR_cite_NU(drapeau):
    """Volet de morsure, sens 2 -- l'arite peut aussi se perdre a l'envers.

    Le diff d'`EPIC11-ARB-224` a fait les deux mouvements le meme jour : trois
    drapeaux devenus nus, deux drapeaux a valeur apparus. Une frontiere qui ne
    mordrait que dans un sens laisserait passer la moitie du risque.
    """
    parseur = _parseur_reel()
    sous = _sous_parseur(parseur, ["project", "remove"])
    action = next(a for a in sous._actions if drapeau in a.option_strings)
    assert _prend_une_valeur(action), drapeau
    # Le drapeau cite NU, suivi d'un autre drapeau : argparse n'a rien a
    # consommer. C'est la forme qu'un message prend quand son auteur croit le
    # drapeau nu.
    jetons = (("--lot", "<id>"), ("--master", None), (drapeau, None),
              ("--confirmer", None))
    argv = _argv_de_la_citation(sous, "project remove", jetons)
    _, code, message = _rejouer(parseur, argv)
    assert code == 2, (
        f"{drapeau} cite NU passe : la frontiere est morte de ce cote-la")
    assert "expected one argument" in message, message


def test_la_valeur_substituee_est_ACCEPTEE_par_le_type_du_drapeau():
    """Volet de morsure de la substitution : elle ne doit pas rougir a la
    place de la citation.

    Une frontiere qui rendrait `"X"` a un drapeau `type=float` verrait
    `invalid float value` et accuserait un message parfaitement juste. Mesure
    de la premiere redaction, en balayant `docs/` : douze faux fautifs, tous
    sur `--fps`. Le depot porte les trois familles -- des `choices`
    (`--profile`), un entier (`--version`) et un flottant (`--fps`) --, et les
    trois sont exercees ici, aux deux bords de la ladder de valeurs d'essai.
    """
    parseur = _parseur_reel()
    cas = [
        (["project", "remove"], "--profile"),
        (["project", "remove"], "--version"),
        (["extract"], "--fps"),
    ]
    vus = set()
    for chemin, option in cas:
        sous = _sous_parseur(parseur, chemin)
        action = next(a for a in sous._actions if option in a.option_strings)
        assert _prend_une_valeur(action), option
        valeur = _valeur_plausible(action)
        if action.type is not None:
            # Elle passe le convertisseur declare : c'est la seule chose que
            # cette substitution doit garantir.
            action.type(valeur)
        if action.choices:
            assert valeur in {str(c) for c in action.choices}, (option, valeur)
        vus.add(valeur)
    assert len(vus) >= 2, (
        f"les trois familles rendent toutes {vus}: la ladder ne discrimine "
        "plus rien, ce controle ne mesure plus la substitution.")


def test_le_motif_lit_une_valeur_LITTERALE_et_ne_TRONQUE_plus_la_citation():
    """Volet de morsure du motif elargi, et il est load-bearing.

    Le correctif de `C1-02` nomme le profil REEL (`--profile prores_422` apres
    interpolation). Avec l'ancien motif -- qui n'acceptait qu'un `<gabarit>`
    apres un drapeau -- la citation etait coupee net a cet endroit :
    `--version`, `--liberer-le-rang` et `--confirmer` sortaient de la portee
    de la frontiere, qui aurait donc ferme le finding en se rendant aveugle a
    la moitie de la ligne qu'elle venait de corriger.
    """
    texte = ("`mmu project remove --lot <id> --master --profile prores_422 "
             "--version <rang> --liberer-le-rang --confirmer`")
    trouves = _MOTIF_COMMANDE.findall(texte)
    assert trouves, texte
    commande, drapeaux = trouves[0]
    assert commande == "project remove"
    assert re.findall(r"--[a-z-]+", drapeaux) == [
        "--lot", "--master", "--profile", "--version", "--liberer-le-rang",
        "--confirmer"], drapeaux
    couples = _MOTIF_JETON.findall(drapeaux)
    assert ("--profile", "prores_422") in couples, couples
    assert ("--master", "") in couples, "l'arite NUE de --master s'est perdue"


def test_le_lecteur_recolle_un_message_construit_par_F_STRING(tmp_path):
    """Volet de morsure du lecteur de f-strings.

    Une citation qui enjambe une interpolation etait coupee en deux morceaux
    illisibles, et la frontiere ne voyait ni la commande ni ses drapeaux. Le
    correctif de `C1-02` est precisement un f-string : sans ce lecteur, la
    fermeture aurait rendu la frontiere muette sur sa propre ligne.
    """
    import ast as _ast

    source = (
        'def refus(profil):\n'
        '    raise ValueError(\n'
        '        f"Issue: `mmu project remove --lot <id> --master "\n'
        '        f"--profile {profil} --version <rang> --confirmer`")\n')
    arbre = _ast.parse(source)
    joints = [n for n in _ast.walk(arbre) if isinstance(n, _ast.JoinedStr)]
    assert len(joints) == 1, joints
    rendu = _rendu_d_un_f_string(joints[0])
    commande, drapeaux = _MOTIF_COMMANDE.findall(rendu)[0]
    assert commande == "project remove"
    assert re.findall(r"--[a-z-]+", drapeaux) == [
        "--lot", "--master", "--profile", "--version", "--confirmer"], rendu
    # Le lecteur reel ne compte pas deux fois : un seul releve pour ce f-string.
    morceaux = [t for t in (m.value for m in _ast.walk(arbre)
                            if isinstance(m, _ast.Constant)
                            and isinstance(m.value, str))
                if "`mmu" in t]
    assert morceaux, "le f-string ne porte plus de morceau citant `mmu`"
    assert "--version" not in morceaux[0], (
        "le morceau constant porte deja toute la citation : ce controle "
        "negatif ne mesure plus le recollage.")


# ---------------------------------------------------------------------------
# Volet « qui CHANGE quelque chose » : l'issue atteint le COEUR
# ---------------------------------------------------------------------------

#: Le manifeste minimal d'un projet reel. TROIS lots distinguables et la cible
#: au MILIEU : le coeur balaie `manifest["lots"]`, une fabrique mono-lot
#: rendrait invisible un appariement fautif, et une fabrique a deux lots dont
#: la cible est en second la placerait aussi en DERNIERE -- les deux formes y
#: sont indiscernables (regle des fabriques, point 2 bis).
_MANIFESTE_MINIMAL = {
    "schema_version": "2.1",
    "project_id": "projet-de-mesure",
    "created": "2026-09-05T00:00:00Z",
    "rushes": [{"rush_id": "R"}],
    "lots": [
        {"lot_id": "AUTRE_24", "rush_id": "R"},
        {"lot_id": "CIBLE_12", "rush_id": "R"},
        {"lot_id": "ENCORE_5", "rush_id": "R"},
    ],
}


def _projet_de_mesure(tmp_path, nom: str = "projet") -> Path:
    """Un projet NEUF a chaque appel.

    Les issues relevees ne sont pas toutes inoffensives -- celle
    d'`extraction_manifest` porte `--confirmer` et retire vraiment le lot. Un
    projet partage rendrait le verdict de la Nieme citation dependant de la
    N-1eme, c'est-a-dire de l'ORDRE du releve.
    """
    dossier = tmp_path / nom
    dossier.mkdir()
    (dossier / "project.json").write_text(
        json.dumps(_MANIFESTE_MINIMAL), encoding="utf-8")
    return dossier


def _l_issue_atteint_le_manifeste(argv):
    """Le coeur a-t-il seulement LU le manifeste ?

    **Le discriminant est une mesure, pas une chaine.** Toutes les gardes de
    designation de `remove_project_element` -- « --master exige --profile »,
    « --version sans cible fine », « une seule cible fine » -- refusent AVANT
    que `load_manifest` soit appele. Un espion sur ce seul appel separe donc
    « la designation a ete comprise » de « la designation a ete refusee pour
    argument manquant », sans lire un mot de francais.

    Le rejeu passe par `cli.project_remove_command`, jamais par un appel
    direct au coeur : c'est le cablage reel, et une designation peut aussi se
    perdre entre le namespace et les mots-cles.
    """
    from mixed_media_utility import cli, project_maintenance

    parseur = _parseur_reel()
    namespace, code, message = _rejouer(parseur, argv)
    assert code == 0, f"la citation ne parse meme pas : {message}"

    # **L'espion se retire dans un `finally`, jamais par la fixture de
    # remplacement de pytest.** Cette fonction est appelee plusieurs fois dans
    # un meme test, et un remplacement qui n'est defait qu'a la FIN du test
    # ferait espionner le premier espion par le second. Ca resterait juste ici
    # -- chaque appel a sa propre liste -- mais l'empilement est une surface
    # morte, et une surface morte finit par mentir.
    lectures = []
    vraie = project_maintenance.load_manifest

    def _espion(*args, **kwargs):
        lectures.append(1)
        return vraie(*args, **kwargs)

    project_maintenance.load_manifest = _espion
    try:
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            cli.project_remove_command(namespace)
    finally:
        project_maintenance.load_manifest = vraie
    return bool(lectures)


def _citations_de_refus():
    """Les citations portees par un `raise` : les ISSUES, pas les mentions.

    Meme perimetre que `_citations_de_refus` de `test_versions_de_master.py`,
    et pour le meme motif : un operateur ne lit une docstring ni un
    commentaire au moment ou une commande echoue.
    """
    racine = Path(__file__).resolve().parents[2] / "src" / "mixed_media_utility"
    for fichier in sorted(racine.rglob("*.py")):
        nom = fichier.relative_to(racine).as_posix()
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for leve in (n for n in ast.walk(arbre) if isinstance(n, ast.Raise)):
            pile = [leve]
            while pile:
                noeud = pile.pop()
                if isinstance(noeud, ast.JoinedStr):
                    textes = [(noeud.lineno, _rendu_d_un_f_string(noeud))]
                elif (isinstance(noeud, ast.Constant)
                      and isinstance(noeud.value, str)):
                    textes = [(noeud.lineno, noeud.value)]
                    pile.extend(ast.iter_child_nodes(noeud))
                else:
                    textes = []
                    pile.extend(ast.iter_child_nodes(noeud))
                for ligne, texte in textes:
                    for commande, drapeaux in _MOTIF_COMMANDE.findall(texte):
                        jetons = tuple(
                            (option, valeur or None)
                            for option, valeur in _MOTIF_JETON.findall(drapeaux))
                        if jetons:
                            yield (nom, ligne, commande, jetons)


def test_toute_issue_de_refus_ATTEINT_le_coeur_et_pas_seulement_le_parseur(
        tmp_path):
    """Volet « qui CHANGE quelque chose », sur les citations portees par un
    `raise` -- c'est-a-dire sur les ISSUES, pas sur les mentions en prose.

    Une commande peut parser et ne rien pouvoir faire : c'est le second etage
    du defaut `C1-02`, ou `--master` sans `--profile` passait argparse pour se
    faire refuser par le coeur. Le perimetre est celui de la promesse : une
    issue est ce qu'un refus propose a un operateur bloque. Une docstring qui
    MENTIONNE une commande (`tui/atelier_exports_versions.py`) n'est pas une
    issue, et la frontiere ne la juge pas.
    """
    parseur = _parseur_reel()
    sous = _sous_parseur(parseur, ["project", "remove"])
    muets, vues = [], 0
    for fichier, ligne, commande, jetons in _citations_de_refus():
        if commande != "project remove":
            continue
        vues += 1
        projet = _projet_de_mesure(tmp_path, f"projet-{vues}")
        argv = _argv_de_la_citation(
            sous, commande, jetons,
            valeurs={"--project": str(projet), "--lot": "CIBLE_12"})
        if not _l_issue_atteint_le_manifeste(argv):
            cite = " ".join(o + (f" {v}" if v else "") for o, v in jetons)
            muets.append(f"{fichier}:{ligne}: `mmu {commande} {cite}`")
    # Garde-fou : si le releve rendait zero citation, tout passerait pour vert.
    assert vues >= 4, (
        f"seules {vues} issues de `project remove` ont ete relevees : les "
        "quatre refus jumeaux d'`EPIC11-ARB-111` en portent au moins autant, "
        "la frontiere ne mesure plus rien.")
    assert muets == [], (
        "Ces issues parsent mais le coeur les refuse AVANT de lire le "
        "manifeste : la designation est incomplete, donc l'issue ne change "
        "rien. Un refus qui n'en laisse qu'une, destructrice, est un blocage "
        "sec deguise (EPIC11-ARB-89):\n  " + "\n  ".join(muets))


def test_la_frontiere_de_COEUR_mord_sur_une_designation_INCOMPLETE(tmp_path):
    """Volet de morsure du second etage, et c'est le defaut `C1-02` MOINS son
    jeton parasite -- la moitie que la seule correction de syntaxe laissait
    passer.

    `--master` sans `--profile` parse parfaitement : seule une mesure du coeur
    peut voir qu'il ne change rien.
    """
    projet = _projet_de_mesure(tmp_path)
    prefixe = ["project", "remove", "--project", str(projet)]
    assert not _l_issue_atteint_le_manifeste(
        prefixe + ["--lot", "CIBLE_12", "--master", "--version", "2",
                   "--liberer-le-rang", "--confirmer"]), (
        "`--master` sans `--profile` atteint le manifeste : le coeur n'exige "
        "plus le profil, ce controle negatif doit etre reecrit.")
    # Le symetrique : la meme ligne AVEC `--profile` va jusqu'au manifeste.
    assert _l_issue_atteint_le_manifeste(
        prefixe + ["--lot", "CIBLE_12", "--master", "--profile", "prores_422",
                   "--version", "2", "--liberer-le-rang", "--confirmer"]), (
        "meme complete, la designation n'atteint pas le manifeste : l'espion "
        "ne mesure plus rien.")


# ---------------------------------------------------------------------------
# `F4` -- une clause vraie que RIEN ne mesurait
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("argv, code_attendu, dans_la_sortie", [
    (["--version"], 0, "."),
    (["project", "--version"], 2, "required"),
    (["project", "remove", "--version", "2"], 2, "--project"),
])
def test_le_VERSION_racine_ne_se_dispute_pas_avec_celui_de_project_remove(
        argv, code_attendu, dans_la_sortie):
    """Le commentaire de `cli.py:4343-4348` affirme que ce comportement est
    « mesure plutot que suppose » (`EPIC11-ARB-224`). Il ne l'etait par RIEN
    (`F4`, couche 3) : aucun banc du depot n'exercait le `--version` racine, et
    la table de cinq formes du contrat avait ete relevee sur une REPRODUCTION
    de la hierarchie d'argparse -- ce que le contrat rétracte lui-meme.

    Le fait est vrai ; c'est la mesure qui manquait. La voici, sur le VRAI
    parseur. Le risque n'etait pas theorique : la ligne racine
    `parser.add_argument('--version', action='version', ...)` est a un `dest=`
    de distance d'un sous-parseur qui la masquerait, et rien ne rougirait.

    Les trois formes sont celles de la table du contrat, aux deux bords de la
    grammaire : la racine seule, le noeud intermediaire, et la feuille ou
    `--version` prend un RANG.
    """
    parseur = _parseur_reel()
    sortie, erreur = io.StringIO(), io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(sortie), \
                contextlib.redirect_stderr(erreur):
            parseur.parse_args(argv)
    except SystemExit as fin:
        code = fin.code or 0
    assert code == code_attendu, (
        f"`mmu {' '.join(argv)}` rend {code}, pas {code_attendu} : "
        f"{sortie.getvalue()!r} / {erreur.getvalue()!r}")
    assert dans_la_sortie in (sortie.getvalue() + erreur.getvalue()), (
        sortie.getvalue(), erreur.getvalue())


def test_le_VERSION_racine_rend_la_VERSION_DE_L_OUTIL_et_pas_un_rang():
    """Volet de morsure de la mesure ci-dessus : le code 0 ne suffit pas.

    Un `--version` racine masque par un sous-parseur rendrait lui aussi une
    sortie ; ce qui distingue les deux est CE QU'IL DIT. On le compare a la
    version declaree du paquet, jamais a une chaine ecrite ici.
    """
    from mixed_media_utility import __version__

    parseur = _parseur_reel()
    sortie = io.StringIO()
    with contextlib.suppress(SystemExit):
        with contextlib.redirect_stdout(sortie), \
                contextlib.redirect_stderr(io.StringIO()):
            parseur.parse_args(["--version"])
    assert sortie.getvalue().strip() == __version__, sortie.getvalue()


# ---------------------------------------------------------------------------
# La PROSE du code se mesure aussi (finding `F17` de la revue 11.4e).
#
# **Le defaut que cette section ferme, et il a ete paye deux fois le meme
# jour.** `EPIC11-ARB-233` a fait du suffixe d'homonymie un RANG ; le lot
# `E2-1f` avait ete fusionne AVANT, et l'arbitrage n'est pas repasse sur sa
# prose. Deux docstrings de la TUI et un commentaire du coeur ont continue
# d'invoquer « le suffixe de dossier » comme MECANISME courant -- la conclusion
# de chaque phrase restait vraie, sa RAISON etait fausse. Meme famille : le
# journal du lot citait `_refus_de_rush_deja_declare(suffixe_epuise=True)`, un
# parametre que le meme arbitrage avait supprime.
#
# Une prose fausse ne fait rien tomber, et c'est exactement pourquoi elle
# survit : elle est la seule partie du code qu'aucun test ne lit. La prochaine
# session la lit, elle, et en tire une conclusion perimee -- ce que ce depot a
# deja paye trois fois sur la seule borne `CANONICAL_ID_MAX_LENGTH`.
#
# Deux frontieres, et elles ne se recouvrent pas :
#
# * l'une recense les mentions du DOSSIER comme mecanisme d'homonymie, et les
#   compare a un registre de mentions HISTORIQUES assumees. Une mention neuve
#   fait rougir ;
# * l'autre relit toute prose qui cite un appel `f(cle=...)` et exige que
#   `cle` existe reellement sur `f`. C'est la classe du `suffixe_epuise=True`.
#
# **Ce qu'elles ne mesurent PAS, dit plutot que tu.** Elles ne lisent que
# `src/` -- commentaires et chaines, par `tokenize`, donc docstrings comprises.
# La prose de `_bmad-output/` leur echappe entierement, et c'est deliberé : un
# journal de lot RACONTE des regimes perimes, c'est son travail. Le
# `suffixe_epuise=True` du journal de `E2-1f` n'aurait donc pas ete attrape
# ici ; il a ete corrige a la main, et c'est la moitie de `F17` qui reste
# documentaire.

#: Le motif d'une prose qui rattache le suffixe d'homonymie au DOSSIER.
#: Volontairement large des deux cotes -- « suffixe de dossier », « suffixe
#: derive du dossier parent », « le dossier donne son suffixe » --, et borne a
#: la PHRASE (`[^.]`) pour ne pas enjamber deux idees voisines.
#:
#: **Il s'applique a la prose APLATIE, jamais aux lignes brutes**, et ce detail
#: a ete paye a l'ecriture : une docstring se replie a 79 colonnes, si bien que
#: « Le suffixe / valait le dossier immediat » d'`extraction.py` tombait de part
#: et d'autre d'un retour a la ligne et echappait entierement a la premiere
#: redaction. Une frontiere de prose qui lit des LIGNES ne mesure que les
#: phrases courtes.
MOTIF_SUFFIXE_DE_DOSSIER = re.compile(
    r"suffixe[^.]{0,40}dossier|dossier[^.]{0,40}suffixe", re.IGNORECASE)


def _prose_aplatie(texte: str) -> str:
    """La prose sur une seule ligne, sans ses marques de mise en forme.

    Les etoiles et les guillemets obliques sont retires plutot que tolerees
    dans le motif : sans cela, le fragment releve pour `**dossier immediat**`
    et pour `dossier immediat` seraient deux entrees differentes du registre,
    et un simple gras suffirait a faire rougir.
    """
    return " ".join(texte.replace("*", "").replace("`", "").split())

#: Les mentions HISTORIQUES assumees, par (fichier, fragment releve).
#:
#: Toutes disent le regime d'AVANT `EPIC11-ARB-233`, et elles se rangent en
#: deux familles :
#:
#: * le MOTIF de l'arbitrage -- « le suffixe valait le dossier immediat »,
#:   suivi des deux defauts qui l'ont fait tomber. Une regle sans son motif se
#:   refait defaire au premier refactoring ;
#: * les NOTES DE CORRECTION de `F17`, qui citent verbatim la phrase fausse
#:   qu'elles remplacent. C'est la forme que ce depot emploie partout ailleurs
#:   (« Corrige le ..., cette place disait ... »), et elle vaut mieux qu'une
#:   correction muette : sans le verbatim, une reprise future rétablit la
#:   phrase d'avant sans savoir qu'elle a deja ete jugee.
#:
#: Ce qui est interdit, c'est de donner le dossier pour le mecanisme COURANT.
#: La comparaison est faite sur la LISTE et non sur un ensemble : une seconde
#: occurrence du meme fragment dans le meme fichier fait rougir elle aussi.
MENTIONS_HISTORIQUES_DU_SUFFIXE = [
    # Le motif de l'arbitrage, aux deux endroits qui l'expliquent.
    ("declaration_de_rush.py", "suffixe valait le dossier"),
    ("extraction.py", "suffixe valait le dossier"),
    # Le regime DISPARU, cite entre guillemets par la docstring du refus :
    # « le suffixe de dossier est deja pris » n'arrive plus, le rang etant
    # toujours libre. Trouvee par l'aplatissement, invisible ligne a ligne.
    ("declaration_de_rush.py", "suffixe de dossier"),
    # Les notes de correction de `F17`, verbatim de ce qu'elles remplacent.
    ("ajout_de_rush.py", "suffixe de dossier"),
    ("extraction.py", "suffixe derive du dossier"),
]


def _prose_des_sources():
    """(fichier, ligne, texte) pour chaque COMMENTAIRE et chaine de `src/`.

    Par `tokenize` et non par AST : un `#:` de Sphinx n'est pas un noeud, et
    c'est precisement la forme qu'`ajout_de_rush.py` employait pour la prose
    perimee de `F17`. Un balayage de lignes brutes, lui, ramasserait le CODE
    -- un nom de variable `suffixe_de_dossier` ferait rougir une frontiere de
    prose, ce qui n'est pas ce qu'elle mesure.
    """
    for chemin in sorted(SOURCES.rglob("*.py")):
        with tokenize.open(chemin) as fichier:
            for jeton in tokenize.generate_tokens(fichier.readline):
                if jeton.type in (tokenize.COMMENT, tokenize.STRING):
                    yield (chemin.name, jeton.start[0], jeton.string)


#: Les prose ou « suffixe » ne veut PAS dire ce que la frontiere cherche.
#:
#: Le motif attrape « suffixe » et « dossier » a moins de 40 caracteres l'un de
#: l'autre. C'est ce qu'il faut pour trouver le mecanisme d'homonymie, et ca
#: ramasse au passage l'autre sens du mot -- **l'extension d'un fichier** --
#: quand un dossier est nomme dans la meme phrase. Ces deux-la sont de ce
#: second sens, verifiees une par une :
#:
#: * `codec_profiles.py` parle du suffixe `.m.<pid>-<hex>.mov` d'un fichier
#:   temporaire et du dossier `<dossier>/frames` que vise le second appelant.
#:   Rien n'y leve d'homonymie de rush ;
#: * `modele_zone_tampon.py` parle du suffixe d'un chemin depose -- `.pdf`,
#:   `.tiff` -- et dit qu'un chemin d'un autre suffixe « fait entree a part,
#:   exactement comme un dossier ». Le mot « dossier » y est une COMPARAISON.
#:
#: **Elles ne vont pas dans `MENTIONS_HISTORIQUES_DU_SUFFIXE`**, et la nuance
#: porte : ce registre-la nomme des phrases qui racontent DELIBEREMENT le
#: regime d'avant `EPIC11-ARB-233`. Y ranger un faux positif du motif ferait
#: croire, au prochain lecteur, que le depot porte deux mentions historiques de
#: plus qu'il n'en a. Deux categories, deux registres.
HOMONYMES_DU_MOT_SUFFIXE = [
    # `codec_profiles.py` l. 1310 : « ce suffixe-la » designe l'EXTENSION d'un
    # nom de fichier temporaire (`.m.mov.<hash>.mov`), et le `<dossier>` qui
    # suit deux lignes plus bas est la racine d'un appelant. C'est
    # l'aplatissement de la prose qui les met cote a cote ; la phrase ne dit
    # rien du mecanisme d'homonymie des rushes, et `EPIC11-ARB-233` ne la
    # concerne pas.
    ("codec_profiles.py", "suffixe-la : le second appelant vise <dossier"),
]


def _mentions_du_suffixe_de_dossier() -> list[tuple[str, str]]:
    """(fichier, fragment) de chaque prose qui rattache le suffixe au dossier.

    Les homonymes du mot -- l'extension d'un fichier -- sont ecartes
    **nommement** par :data:`HOMONYMES_DU_MOT_SUFFIXE`, jamais par un
    relachement du motif : elargir la regex pour les eviter la rendrait aveugle
    a une prose neuve qui, elle, parlerait bien du mecanisme.
    """
    ecartes = {(f, m.lower()) for f, m in HOMONYMES_DU_MOT_SUFFIXE}
    releve: list[tuple[str, str]] = []
    for fichier, _ligne, texte in _prose_des_sources():
        for trouve in MOTIF_SUFFIXE_DE_DOSSIER.findall(_prose_aplatie(texte)):
            if (fichier, trouve.lower()) in ecartes:
                continue
            releve.append((fichier, trouve.lower()))
    return sorted(releve)


def test_les_HOMONYMES_du_mot_suffixe_sont_tous_VIVANTS():
    """Volet symetrique : un ecart perime rendrait la frontiere tautologique.

    Une entree qui ne correspond plus a rien laisserait
    `..._ne_donne_le_DOSSIER_pour_mecanisme_d_homonymie` vert en n'ecartant
    plus rien -- et, pire, elle masquerait une prose NEUVE qui reprendrait le
    meme fragment dans le meme fichier, cette fois pour de mauvaises raisons.
    """
    brut: list[tuple[str, str]] = []
    for fichier, _ligne, texte in _prose_des_sources():
        for trouve in MOTIF_SUFFIXE_DE_DOSSIER.findall(_prose_aplatie(texte)):
            brut.append((fichier, trouve.lower()))
    for fichier, fragment in HOMONYMES_DU_MOT_SUFFIXE:
        assert (fichier, fragment.lower()) in brut, (
            f"ecart PERIME, a retirer : {fichier} / {fragment}")


def test_aucune_prose_NEUVE_ne_donne_le_DOSSIER_pour_mecanisme_d_homonymie():
    """`EPIC11-ARB-233` : le suffixe est un RANG, et la prose doit suivre.

    Si ce test rougit sur une prose que vous venez d'ecrire : le dossier ne
    leve plus l'homonymie, c'est `io/version_ranks` qui le fait
    (`disambiguated_rush_id`). `EPIC11-ARB-9` **tient** -- c'est lui qui decide
    qu'il FAUT lever --, seule la FORME de la levee a change. Si votre phrase
    raconte deliberement le regime d'avant, inscrivez-la dans
    `MENTIONS_HISTORIQUES_DU_SUFFIXE` : c'est un geste conscient, pas une
    formalite.
    """
    releve = _mentions_du_suffixe_de_dossier()
    assert releve == sorted(MENTIONS_HISTORIQUES_DU_SUFFIXE), (
        f"Mentions relevees : {releve}\n"
        f"Mentions attendues : {sorted(MENTIONS_HISTORIQUES_DU_SUFFIXE)}\n"
        "Une prose neuve donne le DOSSIER pour mecanisme d'homonymie, ou une "
        "mention historique a disparu sans que le registre suive."
    )


def test_la_frontiere_de_PROSE_MORD_vraiment():
    """Controle negatif : le motif reconnait bien les trois formes payees.

    Les trois sont prises **verbatim** de la prose que `F17` a trouvee, et la
    quatrieme ligne est celle qui l'a remplacee : une frontiere qui ferait
    rougir le correctif ne serait pas utilisable.
    """
    assert MOTIF_SUFFIXE_DE_DOSSIER.search(
        "et le coeur peut refuser une seconde fois (le suffixe de dossier est")
    assert MOTIF_SUFFIXE_DE_DOSSIER.search(
        "#: l'identifiant leve par le suffixe de dossier d'`EPIC11-ARB-9`.")
    assert MOTIF_SUFFIXE_DE_DOSSIER.search(
        "    # ecrit, et leve par un suffixe derive du dossier parent plutot")
    # La redaction de remplacement, qui ne parle plus de dossier du tout.
    assert not MOTIF_SUFFIXE_DE_DOSSIER.search(
        "    # ecrit, et leve par un RANG (`EPIC11-ARB-233`) plutot que par un")
    # Et la prose voisine qui parle d'un dossier SANS suffixe reste hors de
    # portee : la frontiere ne mesure pas le mot « dossier ».
    assert not MOTIF_SUFFIXE_DE_DOSSIER.search(
        "    Le dossier parent : separateur de dernier recours, jamais critere")


#: Une prose qui cite un appel avec au moins un argument NOMME.
#: Les deux bornes comptent : `[^)`]` interdit d'enjamber la parenthese
#: fermante ou le guillemet oblique, faute de quoi une phrase entiere passerait
#: pour un appel.
MOTIF_APPEL_CITE = re.compile(r"`(_?[a-z][a-z0-9_]*)\(([^)`]*=[^)`]*)\)`")

#: Les cles nommees d'un appel cite. Le `\b` evite de prendre `==` pour une
#: affectation.
MOTIF_CLE_CITEE = re.compile(r"\b([a-z_][a-z0-9_]*)\s*=")


def _signatures_du_depot() -> dict[str, list[tuple[set[str], bool]]]:
    """Nom de fonction -> ses signatures (cles admises, accepte-t-il `**`).

    Une LISTE par nom, et non une signature : deux modules peuvent definir
    `_preparer`. La frontiere se contente alors qu'une seule des homonymes
    accepte la cle -- elle est faite pour attraper un parametre SUPPRIME
    partout, pas pour desambiguiser un appel.
    """
    par_nom: dict[str, list[tuple[set[str], bool]]] = {}
    for chemin in sorted(SOURCES.rglob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = noeud.args
            cles = {a.arg for a in [*args.posonlyargs, *args.args,
                                    *args.kwonlyargs]}
            par_nom.setdefault(noeud.name, []).append(
                (cles, args.kwarg is not None))
    return par_nom


def _cles_citees_hors_signature() -> list[str]:
    """Chaque `f(cle=...)` cite dans la prose dont `cle` n'existe pas sur `f`.

    Les fonctions que le depot ne definit pas -- `resolve(strict=False)`,
    `mkdir(parents=True)` -- sont **ignorees** : leur signature n'est pas la
    notre, et les recenser ferait de cette frontiere un doublon fragile de la
    bibliotheque standard.
    """
    signatures = _signatures_du_depot()
    fautes: list[str] = []
    for fichier, ligne, texte in _prose_des_sources():
        for fonction, arguments in MOTIF_APPEL_CITE.findall(texte):
            connues = signatures.get(fonction)
            if connues is None:
                continue
            for cle in MOTIF_CLE_CITEE.findall(arguments):
                if not any(cle in cles or libre for cles, libre in connues):
                    fautes.append(
                        f"{fichier}:{ligne} cite `{fonction}({cle}=...)`, "
                        f"parametre inexistant sur `{fonction}`")
    return fautes


def test_toute_prose_qui_cite_un_APPEL_nomme_un_parametre_qui_EXISTE():
    """La classe de defaut du `suffixe_epuise=True` de `F17`.

    Un parametre supprime par un arbitrage laisse derriere lui des phrases qui
    le citent, et rien ne les relit. Le lecteur suivant, lui, le fait.

    **Garde d'inventaire d'abord** : une frontiere qui ne trouverait plus aucun
    appel cite serait verte et vide, ce qui est le piege `F3` de la story 5.29.
    """
    signatures = _signatures_du_depot()
    cites = [(f, a) for _fi, _li, t in _prose_des_sources()
             for f, a in MOTIF_APPEL_CITE.findall(t) if f in signatures]
    assert len(cites) >= 5, (
        f"la lecture des appels cites n'en rend que {len(cites)} : la "
        "frontiere ne mesure plus rien")

    fautes = _cles_citees_hors_signature()
    assert not fautes, "\n".join(fautes)


def test_la_frontiere_des_APPELS_cites_MORD_vraiment():
    """Controle negatif, sur la forme exacte que `F17` a payee.

    `_refus_de_rush_deja_declare` existe toujours ; `suffixe_epuise` a ete
    remplace par `issue_de_remplacement` (`EPIC11-ARB-233`). Le premier volet
    mesure que la citation perimee serait vue, le second que la citation juste
    passe -- sans lui, une frontiere qui rougirait sur TOUT serait verte ici.
    """
    signatures = _signatures_du_depot()
    assert "_refus_de_rush_deja_declare" in signatures, (
        "la fonction temoin a disparu : ce controle ne mesure plus rien")
    cles, _libre = signatures["_refus_de_rush_deja_declare"][0]
    assert "suffixe_epuise" not in cles
    assert "issue_de_remplacement" in cles

    fonction, arguments = MOTIF_APPEL_CITE.findall(
        "sait ce cas (`_refus_de_rush_deja_declare(suffixe_epuise=True)`) et")[0]
    assert fonction == "_refus_de_rush_deja_declare"
    assert MOTIF_CLE_CITEE.findall(arguments) == ["suffixe_epuise"]
    # Et la prose qui n'est PAS un appel ne passe pas pour un appel.
    assert not MOTIF_APPEL_CITE.findall("`CRITERES_IDENTITE_RUSH` (dossier=x)")
