# -*- coding: utf-8 -*-
"""Les `.txt` de l'atelier Extraction sont-ils A JOUR de leur GENERATEUR ?

**Le maillon amont, qui n'etait mesure par rien** (2026-09-05).
`test_maquettes_couleur_a_jour.py` mesure que le rendu SVG suit son `.txt`.
Personne ne mesurait que le `.txt` suit `_gen_*.py`, alors que le depot
repete qu'« une maquette se corrige A LA SOURCE, jamais dans le rendu » -- et
que la source, pour ces douze ecrans, est le generateur, pas le `.txt`.

**Ce que ca coutait, et c'est mesure plutot que suppose.** Campagne de
mutation du lot `EPIC11-ARB-227`, trois mutants SURVIVANTS de la meme
famille :

* `M28` -- `RESOLUTION_SANS_CARDINAL = RESOLUTION_CORROBOREE` : la source dit
  l'inverse de l'arbitrage, aucun banc ne rougit ;
* `M29` -- la ligne d'etat de `E2-1i` reprend celle de `E2-1e` ;
* `M30` -- `fiche_de_declaration` ignore son parametre `resolution`.

Les trois passaient parce que le `.txt` commite, lui, ne bougeait pas. La
chaine de production avait donc un maillon mesure et un maillon muet, et le
muet etait celui d'ou tout part.

**Pourquoi le generateur est joue DANS UN DOSSIER TEMPORAIRE.**
`construire_maquette.ecrire` REFUSE de reecrire une maquette qui porte une
annotation manuscrite d'Egan sous sa grille -- garde posee le 2026-08-27 apres
que trois regenerations ont efface ses remarques. **38 des 85 maquettes du
dossier en portent une**, si bien que `python _gen_extraction.py` leve des sa
ligne 132 et n'ecrit plus rien. Le generateur est donc devenu inlancable EN
PLACE. Dans un dossier vide, la garde ne se declenche jamais -- rien n'y
existe a proteger --, et c'est ce qui rend cette frontiere possible du tout.

**Ce que cette frontiere NE mesure PAS, dit plutot que tu.**

* elle ne couvre QUE `_gen_extraction.py`. Les autres generateurs (`_gen_a`,
  `_gen_b`, `_gen_c`, `_gen_selection`, `_gen_explorateur`) sont dans le meme
  etat et ne sont pas mesures ici : les etendre demande de verifier d'abord
  que chacun reproduit bien ses `.txt`, ce qui est un lot a part. L'entree
  correspondante vit dans `deferred-work.md` ;
* elle **ignore les annotations**. Elle compare les 24 lignes de la GRILLE,
  jamais ce qu'Egan ecrit dessous -- le generateur ne peut pas les produire,
  et les exiger ferait rougir toute maquette relue ;
* elle n'a **pas de volet ORPHELIN**. Le dossier `maquettes/` recoit les
  produits de six generateurs ; un `.txt` que celui-ci ne produit pas n'est
  pas un orphelin, c'est le produit d'un autre. Un volet orphelin ici
  rougirait sur 73 fichiers parfaitement sains.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_UX = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
              / "ux-tui-2026-08-27")
SOURCES = DOSSIER_UX / "maquettes"
GENERATEUR = DOSSIER_UX / "_gen_extraction.py"

#: La hauteur de la grille. Ce qui la depasse dans un `.txt` est une
#: annotation manuscrite, jamais du contenu d'ecran.
HAUTEUR_GRILLE = 24

#: Plancher du cardinal, pour qu'un generateur qui n'ecrirait RIEN ne rende pas
#: ce banc vert sans rien mesurer. Meme geste et meme motif que le plancher de
#: `test_maquettes_couleur_a_jour.py`, et meme bande : il se tient contre le
#: cardinal reel plutot que dans l'absolu.
PLANCHER_DE_MAQUETTES = 12
MARGE_DU_PLANCHER = 6


def grille(texte: str) -> list[str]:
    """Les 24 lignes de la grille, sans les annotations qui la suivent."""
    return texte.rstrip("\n").split("\n")[:HAUTEUR_GRILLE]


def _rejouer_le_generateur(cible: Path) -> dict[str, list[str]]:
    """Rejouer `_gen_extraction.py` dans `cible`. Rend `{nom: lignes}`.

    Le reroutage passe par `construire_maquette.ecrire`, que le generateur
    importe : c'est le SEUL point d'ecriture, et le patcher la plutot que de
    recopier la composition garantit qu'on mesure le vrai producteur. Un banc
    qui recomposerait les maquettes lui-meme mesurerait sa propre copie.
    """
    for chemin in (str(DOSSIER_UX), str(RACINE / "src")):
        if chemin not in sys.path:
            sys.path.insert(0, chemin)
    import construire_maquette  # noqa: PLC0415

    vrai_ecrire = construire_maquette.ecrire
    cible.mkdir(parents=True, exist_ok=True)

    def ecrire_ailleurs(nom, contenu, dossier=None, **reste):
        return vrai_ecrire(nom, contenu, dossier=cible, **reste)

    construire_maquette.ecrire = ecrire_ailleurs
    try:
        runpy.run_path(str(GENERATEUR), run_name="__main__")
    finally:
        construire_maquette.ecrire = vrai_ecrire
    return {c.name: grille(c.read_text(encoding="utf-8"))
            for c in sorted(cible.glob("*.txt"))}


def _maquettes_commitees(noms) -> dict[str, list[str]]:
    return {nom: grille((SOURCES / nom).read_text(encoding="utf-8"))
            for nom in noms if (SOURCES / nom).is_file()}


# **Les deux comparaisons vivent ICI et les deux familles de tests les
# APPELLENT** -- assertions comme tests de morsure. Le finding `F3` de la revue
# de la 11.13 dit ce qui arrive sinon : un test de morsure qui recopie la
# comparaison laisse passer une tautologie posee dans l'original.

def perimes(frais: dict[str, list[str]],
            commits: dict[str, list[str]]) -> list[str]:
    """Les `.txt` commites dont la GRILLE ne correspond plus au generateur."""
    return sorted(nom for nom, lignes in frais.items()
                  if commits.get(nom) != lignes)


def manquants(frais: dict[str, list[str]],
              commits: dict[str, list[str]]) -> list[str]:
    """Les maquettes que le generateur ecrit et que le depot n'a pas."""
    return sorted(set(frais) - set(commits))


@pytest.fixture(scope="module")
def maquettes_fraiches(tmp_path_factory) -> dict[str, list[str]]:
    """Le generateur rejoue UNE fois, hors du depot.

    Jamais dans `maquettes/` : un banc qui ecrit dans le depot pour se mesurer
    rendrait vert tout ce qu'il touche -- et ici il ecraserait en plus les
    annotations manuscrites que la garde de `ecrire` existe pour proteger.
    """
    return _rejouer_le_generateur(tmp_path_factory.mktemp("maquettes-fraiches"))


def test_aucune_maquette_E2_n_a_DERIVE_de_son_generateur(maquettes_fraiches):
    """Chaque `.txt` commite est la grille que `_gen_extraction.py` produit."""
    ecarts = perimes(maquettes_fraiches, _maquettes_commitees(maquettes_fraiches))
    assert not ecarts, (
        f"{len(ecarts)} maquette(s) ne correspondent plus a leur generateur : "
        f"{ecarts}. Une maquette se corrige DANS `_gen_extraction.py`, jamais "
        "dans le `.txt`. Si le `.txt` porte la correction et pas la source, "
        "c'est la source qu'il faut reprendre -- sans quoi la prochaine "
        "regeneration l'effacera.")


def test_aucune_maquette_PRODUITE_ne_manque_au_depot(maquettes_fraiches):
    """Le volet symetrique : une maquette produite et jamais commitee.

    Le generateur peut ecrire un ecran neuf que personne n'a ajoute au depot.
    Le test precedent ne le verrait pas : il compare ce qui existe des deux
    cotes.
    """
    absentes = manquants(maquettes_fraiches,
                         _maquettes_commitees(maquettes_fraiches))
    assert not absentes, (
        f"{len(absentes)} maquette(s) que le generateur ecrit n'ont aucun "
        f"`.txt` commite : {absentes}.")


def test_la_mesure_porte_sur_un_ENSEMBLE_REEL_et_non_sur_le_vide(
        maquettes_fraiches):
    """Sans ce plancher, un generateur qui n'ecrirait RIEN rendrait tout vert.

    Les deux comparaisons ci-dessus sont des comparaisons d'ensembles : sur
    deux ensembles vides elles passent sans rien mesurer. C'est exactement le
    regime dans lequel `python _gen_extraction.py` se trouve aujourd'hui quand
    on le lance EN PLACE -- il leve avant d'ecrire quoi que ce soit.
    """
    assert len(maquettes_fraiches) >= PLANCHER_DE_MAQUETTES, (
        f"le generateur n'a ecrit que {len(maquettes_fraiches)} maquettes pour "
        f"un plancher de {PLANCHER_DE_MAQUETTES} : il s'est arrete en chemin, "
        "et les deux frontieres ci-dessus ne mesurent plus rien.")


def test_le_plancher_n_est_pas_DEGENERE(maquettes_fraiches):
    """Un plancher a zero laisserait la garde en place sans sa mesure."""
    reel = len(maquettes_fraiches)
    assert 0 < PLANCHER_DE_MAQUETTES <= reel, (
        f"plancher {PLANCHER_DE_MAQUETTES} pour {reel} maquettes reelles : un "
        "plancher nul ou superieur au reel ne garde rien.")
    assert reel - PLANCHER_DE_MAQUETTES <= MARGE_DU_PLANCHER, (
        f"plancher {PLANCHER_DE_MAQUETTES} pour {reel} maquettes reelles, soit "
        f"{reel - PLANCHER_DE_MAQUETTES} d'ecart pour une marge de "
        f"{MARGE_DU_PLANCHER} : le plancher a decroche du cardinal.")


def test_la_VARIANTE_du_cardinal_absent_est_bien_PRODUITE(maquettes_fraiches):
    """`E2-1i` sort du generateur, et non d'une ecriture a la main.

    C'est la maquette d'`EPIC11-ARB-227`, et c'est celle dont les trois
    mutants ont survecu. Nommer le fichier ici empeche que la frontiere reste
    verte le jour ou il cesserait d'etre produit -- le volet des manquants ne
    verrait rien, puisqu'il compare le produit au commite et que les deux
    disparaitraient ensemble.
    """
    assert "E2-1i-declaration-cardinal-absent.txt" in maquettes_fraiches, (
        f"produites : {sorted(maquettes_fraiches)}")


#: Les trois rangs OU l'on altere une ligne, DANS la grille. Deux collections
#: sont imbriquees ici -- l'ensemble des maquettes et les 24 lignes de
#: chacune --, et la regle des fabriques vaut pour les DEUX.
#:
#: **Mesure, mutant `M36` du second tour** : avec la seule alteration en
#: premiere ligne, remplacer la comparaison de grilles par une comparaison de
#: leur PREMIERE LIGNE SEULEMENT laissait les douze tests VERTS. La cible
#: etait toujours a l'endroit exact que la comparaison mutilee regardait
#: encore. C'est le point 4 applique a la mauvaise collection : les bords
#: etaient tenus sur les maquettes, pas sur les lignes.
RANGS_ALTERES = {"premiere_ligne": 0, "ligne_mediane": 12, "derniere_ligne": -1}


@pytest.mark.parametrize("rang", sorted(RANGS_ALTERES))
@pytest.mark.parametrize("bord", ["tete", "queue"])
def test_la_frontiere_MORD_sur_une_grille_alteree_a_CHAQUE_BORD(
        maquettes_fraiches, bord, rang):
    """La frontiere attrape-t-elle vraiment une derive ? Aux deux bords, et
    sur les deux collections imbriquees.

    Point 4 de la regle des fabriques, applique deux fois : la maquette visee
    est en tete puis en queue de l'ensemble, et la ligne alteree est en tete,
    au milieu puis en queue de la grille. Le point 1 est tenu par
    construction -- les douze maquettes different toutes, et les 24 lignes
    d'une grille aussi.
    """
    noms = sorted(maquettes_fraiches)
    vise = noms[0] if bord == "tete" else noms[-1]
    faux_depot = {nom: list(lignes)
                  for nom, lignes in maquettes_fraiches.items()}
    indice = RANGS_ALTERES[rang]
    altere = list(faux_depot[vise])
    assert altere[indice] != "derive", "l'alteration n'alterait rien"
    altere[indice] = "derive"
    faux_depot[vise] = altere
    assert perimes(maquettes_fraiches, faux_depot) == [vise], (
        f"une derive posee en {bord} ({vise}), {rang}, n'est pas attrapee : "
        f"la comparaison rend {perimes(maquettes_fraiches, faux_depot)}")


def test_les_RANGS_ALTERES_couvrent_les_deux_bords_de_la_GRILLE():
    """La garde de l'inventaire ci-dessus, pour le meme motif que sur `POSES`.

    Un inventaire de poses se garde par son CONTENU : retirer une entree d'un
    `parametrize` joue une pose de moins sans faire rougir personne.
    """
    indices = set(RANGS_ALTERES.values())
    assert 0 in indices, "aucune alteration en PREMIERE ligne de grille"
    assert -1 in indices, "aucune alteration en DERNIERE ligne de grille"
    assert indices - {0, -1}, "aucune alteration au MILIEU de la grille"


@pytest.mark.parametrize("bord", ["tete", "queue"])
def test_le_volet_des_MANQUANTS_mord_a_chaque_bord(maquettes_fraiches, bord):
    """Meme mesure pour l'absence, et aux deux bords pour le meme motif."""
    noms = sorted(maquettes_fraiches)
    vise = noms[0] if bord == "tete" else noms[-1]
    faux_depot = {nom: lignes for nom, lignes in maquettes_fraiches.items()
                  if nom != vise}
    assert manquants(maquettes_fraiches, faux_depot) == [vise], (
        f"une maquette absente en {bord} ({vise}) n'est pas attrapee.")


def test_la_comparaison_IGNORE_les_annotations_manuscrites(maquettes_fraiches):
    """Volet negatif : une remarque d'Egan sous la grille ne fait PAS rougir.

    Sans lui, la frontiere rougirait sur les 38 maquettes annotees du dossier
    et serait desarmee dans la semaine. C'est aussi la garantie qu'aucun agent
    n'ira « reparer » un rouge en supprimant une remarque d'Egan -- ce que la
    garde de `ecrire` existe precisement pour empecher.
    """
    nom = sorted(maquettes_fraiches)[0]
    annotee = {nom: list(maquettes_fraiches[nom])}
    assert perimes({nom: maquettes_fraiches[nom]}, annotee) == []
    # La grille est identique ; l'annotation vit HORS des 24 lignes, donc
    # `grille()` ne la voit pas -- mesure sur le vrai decoupage.
    avec_note = "\n".join(maquettes_fraiches[nom]) + "\nNOTE : remarque d'Egan"
    assert grille(avec_note) == maquettes_fraiches[nom]


def test_le_generateur_n_ECRIT_JAMAIS_dans_le_depot_pendant_la_mesure(tmp_path):
    """Volet negatif : la mesure ne doit pas rendre vert ce qu'elle touche.

    Si le reroutage cessait de fonctionner, ce banc regenererait `maquettes/`
    a chaque course -- il se rendrait vert lui-meme, et il ecraserait au
    passage les annotations manuscrites.
    """
    empreinte_avant = {c.name: c.stat().st_mtime_ns
                       for c in sorted(SOURCES.glob("*.txt"))}
    _rejouer_le_generateur(tmp_path / "ailleurs")
    empreinte_apres = {c.name: c.stat().st_mtime_ns
                       for c in sorted(SOURCES.glob("*.txt"))}
    assert empreinte_avant == empreinte_apres, (
        "le generateur a ecrit dans `maquettes/` alors qu'on le reroutait")


def test_le_generateur_est_DETERMINISTE_et_la_mesure_a_donc_un_sens(tmp_path):
    """Deux passes du meme arbre produisent les memes grilles.

    Sans cette propriete, une frontiere par comparaison exacte rougirait au
    hasard et finirait desarmee. Elle est mesuree plutot que supposee : ce banc
    entier repose dessus.
    """
    premier = _rejouer_le_generateur(tmp_path / "a")
    second = _rejouer_le_generateur(tmp_path / "b")
    assert set(premier) == set(second)
    assert perimes(premier, second) == []
