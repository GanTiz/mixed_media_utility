# -*- coding: utf-8 -*-
"""Les rendus couleur sont-ils A JOUR de leur source `.txt` ?

**Le defaut que cette frontiere ferme, et il a ete paye** (2026-09-05). Cinq
rendus de `maquettes-couleur/` avaient DERIVE de leur `.txt` -- `E6-1` de
32 lignes, `E6-1c` de 22, `E6-1d` de 32, `E6-3` d'une -- et un sixieme,
`E6-1e`, n'avait jamais ete rendu du tout. L'ecart sur `E6-3` est de ceux
qu'une relecture ne voit pas : la source disait
``▸ Réessayer sur les 3 fichiers restés`` la ou le rendu disait
``▸ Réessayer``. Les 71 autres etaient d'accord, ce qui est exactement ce qui
rend la derive invisible -- on ne relit pas 76 images pour en trouver cinq.

**Rien ne le mesurait**, et c'est le point : `coloriser_maquette.py` est un
producteur qu'on lance a la main. Entre deux lancements, une correction portee
au `.txt` -- le seul endroit ou une maquette se corrige, jamais dans le rendu --
laisse le SVG en arriere sans un mot. Un rendu perime est pire qu'absent : il
se lit comme une validation.

**Pourquoi une frontiere et non une consigne.** Une consigne (« penser a
relancer le colorisateur ») est precisement ce qui a echoue : le module
existait, son mode d'emploi aussi. Ce qui se mesure se tient ; ce qui se
rappelle se perd. C'est le meme raisonnement que
`test_politiques_du_depot.py` tient pour les regles de `CLAUDE.md`.

**Ce que cette frontiere ne mesure PAS, dit plutot que tu.** Elle ne juge
aucune couleur : elle compare le rendu COMMIT au rendu que le module produit
AUJOURD'HUI, octet pour octet. Si la palette de `tui/jetons.py` change, les 76
rendus deviennent perimes d'un coup et ce banc rougit en bloc -- c'est voulu,
c'est la divergence que le colorisateur existe pour empecher, et le geste est
de relancer le producteur, jamais de relacher la mesure.

Elle ne mesure pas non plus les maquettes que les motifs du producteur
ECARTENT (`T3-1`, `T4-1`, `T5-1`...). L'ensemble mesure est celui que
`coloriser_maquette.main()` choisit lui-meme : recopier ici une liste
d'exceptions la ferait diverger du producteur au premier motif ajoute.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_UX = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
              / "ux-tui-2026-08-27")
SOURCES = DOSSIER_UX / "maquettes"
RENDUS = DOSSIER_UX / "maquettes-couleur"

#: Plancher du cardinal, pour qu'une selection VIDE ne rende pas ce banc vert
#: sans rien mesurer. Il descend quand une famille de maquettes sort du
#: producteur, et cette descente s'ecrit dans le meme commit ; il ne monte pas
#: tout seul -- un rendu de plus n'a pas besoin qu'on touche a ce banc.
PLANCHER_DE_RENDUS = 70


def _colorisateur():
    """Importer le producteur, qui vit hors du paquet et hors de `tests/`."""
    if str(DOSSIER_UX) not in sys.path:
        sys.path.insert(0, str(DOSSIER_UX))
    import coloriser_maquette  # noqa: PLC0415

    return coloriser_maquette


def _rendre_dans(cible: Path) -> dict[str, bytes]:
    """Rejouer le producteur dans `cible` et rendre `{nom: octets}`.

    On passe par `main()` et non par `peindre_maquette()` : le finding `R10` de
    la revue du 2026-08-31 a mesure que deux mutants du CABLAGE survivaient a un
    test qui appelait la peinture directement. Un test qui ne joue pas le chemin
    fautif ne le mesure pas.
    """
    cible.mkdir(parents=True, exist_ok=True)
    _colorisateur().main(source=SOURCES, cible=cible)
    return {c.name: c.read_bytes() for c in sorted(cible.glob("*.svg"))}


def _rendus_commits() -> dict[str, bytes]:
    return {c.name: c.read_bytes() for c in sorted(RENDUS.glob("*.svg"))}


# **Les trois comparaisons vivent ICI, et les deux familles de tests les
# APPELLENT** -- les assertions ci-dessous comme les tests de morsure. La
# premiere redaction de ce banc les ecrivait deux fois, une par famille, et un
# mutant l'a mesure : remplacer `set(frais) - set(commits)` par
# `set(frais) - set(frais)` -- une tautologie qui rend le volet des manquants
# structurellement incapable de rougir -- laissait les **douze** tests verts,
# parce que le test de morsure recopiait la comparaison au lieu de l'appeler.
# C'est le finding `F3` de la couche 2 de la revue de la 11.13, mot pour mot :
# « le volet est INTEGRALEMENT redondant, on peut l'eteindre sans qu'un seul
# test rougisse ». Une comparaison recopiee n'est pas mesuree.


def perimes(frais: dict[str, bytes], commits: dict[str, bytes]) -> list[str]:
    """Les rendus commites dont le contenu ne correspond plus a leur source."""
    return sorted(nom for nom, octets in frais.items()
                  if commits.get(nom) != octets)


def manquants(frais: dict[str, bytes], commits: dict[str, bytes]) -> list[str]:
    """Les maquettes selectionnees qui n'ont aucun rendu commite."""
    return sorted(set(frais) - set(commits))


def orphelins(frais: dict[str, bytes], commits: dict[str, bytes]) -> list[str]:
    """Les rendus commites que le producteur ne produit plus."""
    return sorted(set(commits) - set(frais))


@pytest.fixture(scope="module")
def rendus_frais(tmp_path_factory) -> dict[str, bytes]:
    """Le rendu d'aujourd'hui, produit UNE fois hors du depot.

    Jamais dans `maquettes-couleur/` : un banc qui ecrit dans le depot pour se
    mesurer rendrait vert tout ce qu'il touche.
    """
    return _rendre_dans(tmp_path_factory.mktemp("maquettes-couleur-fraiches"))


def test_aucun_rendu_couleur_n_a_DERIVE_de_sa_source(rendus_frais):
    """Chaque SVG commite est celui que son `.txt` produit aujourd'hui."""
    ecarts = perimes(rendus_frais, _rendus_commits())
    assert not ecarts, (
        f"{len(ecarts)} rendu(s) couleur ne correspondent plus a leur source "
        f".txt : {ecarts}. Une maquette se corrige DANS son `.txt`, jamais "
        "dans le rendu ; le rendu se regenere par "
        "`coloriser_maquette.py`. Cinq rendus avaient derive sans que rien ne "
        "le dise, le 2026-09-05.")


def test_aucune_source_SELECTIONNEE_n_est_privee_de_rendu(rendus_frais):
    """Le volet symetrique : un rendu ABSENT est aussi grave qu'un rendu perime.

    `E6-1e` n'avait jamais ete rendu -- neuf `E6` sur dix en avaient un, et le
    dixieme manquait. Le test precedent ne l'aurait pas vu : il compare ce qui
    existe des deux cotes.
    """
    absents = manquants(rendus_frais, _rendus_commits())
    assert not absents, (
        f"{len(absents)} maquette(s) que le producteur SELECTIONNE n'ont "
        f"aucun rendu commite : {absents}. Lancer `coloriser_maquette.py` "
        "et commiter ce qu'il ecrit.")


def test_aucun_rendu_ORPHELIN_ne_survit_a_sa_source(rendus_frais):
    """Le second volet symetrique : un SVG que le producteur ne produit plus.

    Une maquette renommee ou retiree laisse son rendu derriere elle. Il n'est
    ni perime ni manquant -- il est ORPHELIN, et aucun des deux tests ci-dessus
    ne le voit.
    """
    restes = orphelins(rendus_frais, _rendus_commits())
    assert not restes, (
        f"{len(restes)} rendu(s) couleur n'ont plus de source selectionnee "
        f"par le producteur : {restes}. Soit la maquette a ete renommee et "
        "le rendu suit, soit elle a ete retiree et le rendu part avec elle.")


def test_la_mesure_porte_sur_un_ENSEMBLE_REEL_et_non_sur_le_vide(rendus_frais):
    """Sans ce plancher, un producteur qui ne selectionne RIEN rend tout vert.

    Les trois tests ci-dessus sont des comparaisons d'ensembles : sur deux
    ensembles vides, ils passent tous les trois sans rien mesurer. C'est le
    mode de panne que ce depot appelle une assertion tautologique.
    """
    assert len(rendus_frais) >= PLANCHER_DE_RENDUS, (
        f"le producteur n'a rendu que {len(rendus_frais)} maquettes pour un "
        f"plancher de {PLANCHER_DE_RENDUS} : ses motifs de selection se sont "
        "refermes, et les trois frontieres ci-dessus ne mesurent plus rien.")


#: Ecart maximum tolere entre le plancher et le cardinal reel. Une bande, et
#: non une egalite : une egalite forcerait a editer ce banc a chaque maquette
#: ajoutee, ce qui est le meilleur moyen de faire relever un seuil par reflexe.
MARGE_DU_PLANCHER = 10


def test_le_plancher_n_est_pas_DEGENERE(rendus_frais):
    """Un plancher a zero laisserait la garde en place sans sa mesure.

    Mesure : `PLANCHER_DE_RENDUS = 0` **survivait** a la premiere campagne. La
    garde du cardinal existait, et rien ne mesurait qu'elle gardait quelque
    chose -- c'est la version « seuil » du drapeau sans effet. Le plancher se
    tient donc contre le cardinal REEL, dans une bande.
    """
    reel = len(rendus_frais)
    assert 0 < PLANCHER_DE_RENDUS <= reel, (
        f"plancher {PLANCHER_DE_RENDUS} pour {reel} rendus reels : un "
        "plancher nul ou superieur au reel ne garde rien.")
    assert reel - PLANCHER_DE_RENDUS <= MARGE_DU_PLANCHER, (
        f"plancher {PLANCHER_DE_RENDUS} pour {reel} rendus reels, soit "
        f"{reel - PLANCHER_DE_RENDUS} d'ecart pour une marge de "
        f"{MARGE_DU_PLANCHER} : le plancher a decroche du cardinal et ne "
        "detecterait plus qu'un effondrement total de la selection.")


@pytest.mark.parametrize("bord", ["tete", "queue"])
def test_la_frontiere_MORD_sur_un_rendu_altere_a_CHAQUE_BORD(
        tmp_path, rendus_frais, bord):
    """La frontiere attrape-t-elle vraiment une derive ? Mesure aux DEUX bords.

    **La regle des fabriques de `CLAUDE.md`, point 4** : une cible au milieu
    demasque une comparaison fautive, elle ne demasque **pas** un balayage
    tronque -- un `for` qui saute la derniere entree resterait vert avec une
    cible mediane. Les deux bords sont donc mesures, et le point 1 est tenu par
    construction : les 76 rendus different tous les uns des autres.

    Sans ces deux tests, les trois frontieres ci-dessus seraient vertes le jour
    ou la comparaison cesserait de comparer -- et c'est exactement le defaut
    qu'aucun test positif ne voit.
    """
    faux_depot = tmp_path / "rendus"
    faux_depot.mkdir()
    for nom, octets in rendus_frais.items():
        (faux_depot / nom).write_bytes(octets)

    noms = sorted(rendus_frais)
    vise = noms[0] if bord == "tete" else noms[-1]
    altere = rendus_frais[vise].replace(b"</svg>", b"<!-- derive --></svg>")
    assert altere != rendus_frais[vise], "l'alteration n'a rien change"
    (faux_depot / vise).write_bytes(altere)

    commits = {c.name: c.read_bytes() for c in sorted(faux_depot.glob("*.svg"))}
    vus = perimes(rendus_frais, commits)
    assert vus == [vise], (
        f"une derive posee en {bord} ({vise}) n'est pas attrapee : la "
        f"comparaison rend {vus}. Une frontiere qui ne mord pas sur le "
        "defaut qu'elle nomme ne mesure rien.")


@pytest.mark.parametrize("bord", ["tete", "queue"])
def test_le_volet_des_MANQUANTS_mord_a_chaque_bord(tmp_path, rendus_frais,
                                                   bord):
    """Meme mesure pour l'absence, et aux deux bords pour le meme motif."""
    faux_depot = tmp_path / "rendus"
    faux_depot.mkdir()
    for nom, octets in rendus_frais.items():
        (faux_depot / nom).write_bytes(octets)

    noms = sorted(rendus_frais)
    vise = noms[0] if bord == "tete" else noms[-1]
    (faux_depot / vise).unlink()

    commits = {c.name: c.read_bytes() for c in sorted(faux_depot.glob("*.svg"))}
    assert manquants(rendus_frais, commits) == [vise], (
        f"un rendu absent en {bord} ({vise}) n'est pas attrape.")


@pytest.mark.parametrize("bord", ["tete", "queue"])
def test_le_volet_des_ORPHELINS_mord_a_chaque_bord(rendus_frais, bord):
    """Le troisieme volet a sa morsure lui aussi, et aux deux bords.

    Il ne l'avait pas a la premiere redaction, ce qui le laissait dans l'etat
    exact que les deux autres ont quitte : une comparaison qu'aucun test ne
    fait echouer.
    """
    noms = sorted(rendus_frais)
    vise = noms[0] if bord == "tete" else noms[-1]
    # Un rendu commite que le producteur ne produit plus : on le laisse cote
    # « commits » et on le retire cote « frais ».
    frais = {nom: octets for nom, octets in rendus_frais.items() if nom != vise}
    assert orphelins(frais, dict(rendus_frais)) == [vise], (
        f"un rendu orphelin en {bord} ({vise}) n'est pas attrape.")


def test_le_producteur_est_DETERMINISTE_et_la_mesure_a_donc_un_sens(tmp_path):
    """Deux rendus successifs du meme arbre sont identiques.

    Sans cette propriete, une frontiere par comparaison d'octets rougirait au
    hasard et finirait desarmee. Elle est mesuree ici plutot que supposee : ce
    banc entier repose dessus.
    """
    premier = _rendre_dans(tmp_path / "a")
    second = _rendre_dans(tmp_path / "b")
    differents = sorted(nom for nom in premier if premier[nom] != second.get(nom))
    memes_noms = set(premier) == set(second)
    assert not differents and memes_noms, (
        "le producteur n'est pas deterministe : "
        f"contenus divergents {differents}, memes noms {memes_noms}")


def test_les_deux_dossiers_de_maquettes_EXISTENT():
    """Un chemin faux rendrait les frontieres vertes sur deux ensembles vides.

    Le plancher ci-dessus l'attrape deja par le cardinal ; celui-ci le nomme
    pour que le message dise « le dossier a bouge » et non « le producteur ne
    selectionne plus rien ».
    """
    assert SOURCES.is_dir(), f"{SOURCES} n'existe pas : le dossier a bouge"
    assert RENDUS.is_dir(), f"{RENDUS} n'existe pas : le dossier a bouge"


def test_le_producteur_n_ECRIT_JAMAIS_dans_le_depot_pendant_la_mesure(tmp_path):
    """Volet negatif : la mesure ne doit pas rendre vert ce qu'elle touche.

    `main()` prend ses deux dossiers en parametre depuis le finding `R10`.
    Si un jour il reprenait ses defauts en dur, ce banc regenererait le depot
    a chaque course et ne mesurerait plus jamais rien -- il se rendrait vert
    lui-meme.
    """
    empreinte_avant = {c.name: c.stat().st_mtime_ns
                       for c in sorted(RENDUS.glob("*.svg"))}
    _rendre_dans(tmp_path / "ailleurs")
    empreinte_apres = {c.name: c.stat().st_mtime_ns
                       for c in sorted(RENDUS.glob("*.svg"))}
    assert empreinte_avant == empreinte_apres, (
        "le producteur a ecrit dans `maquettes-couleur/` alors qu'on lui "
        "donnait un autre dossier : la frontiere se rendrait verte elle-meme")


def test_le_dossier_de_travail_du_banc_n_est_pas_le_depot(tmp_path):
    """Garde de forme : `shutil` n'est importe que pour une copie hors depot."""
    assert RACINE not in tmp_path.parents and tmp_path != RACINE
    copie = tmp_path / "copie"
    shutil.copytree(RENDUS, copie)
    assert len(list(copie.glob("*.svg"))) >= PLANCHER_DE_RENDUS
