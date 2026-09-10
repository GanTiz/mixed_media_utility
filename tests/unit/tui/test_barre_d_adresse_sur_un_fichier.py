# -*- coding: utf-8 -*-
"""La barre d'adresse accepte un chemin de FICHIER -- story 11.15,
`EPIC11-ARB-283`.

Ce que la story ferme, mesure avant d'etre ecrite : coller le chemin d'un
fichier qui existe vidait la liste et faisait dire a la ligne d'etat « aucun
dossier n'existe a cette adresse ». `cible_de_validation()` rendait pourtant
deja ce fichier -- donc `⏎` le validait. **L'ecran decourageait un geste qu'il
savait executer.**

Les quatre points de la regle des fabriques, appliques et non cites
-------------------------------------------------------------------
* **au moins deux elements distinguables** : les douze fichiers de
  :func:`arbo_mixte` portent douze noms et douze TAILLES differentes, et les
  deux dossiers deux cardinaux differents. Un remplissage uniforme rendrait
  invisible tout desappariement entre le chemin colle et la ligne atteinte ;
* **la cible est jouee ailleurs qu'en premiere position** : le cas nominal vise
  un fichier du milieu ;
* **la cible est jouee a CHAQUE BORD**, en tete *et* en queue -- le bord est un
  AUTRE mode de panne que l'aiguillage fautif (un balayage tronque ne se
  demasque que la). La tete vraie du rang 0 demande une liste **sans dossier**,
  puisque `relire()` place toujours les dossiers d'abord : c'est
  :func:`arbo_de_fichiers` ;
* la variante multi-elements est ecrite **ici**, jamais renvoyee a la revue.

**Et l'ordre du DISQUE n'est pas celui de la LISTE** (AC 8) : les fichiers sont
poses dans l'ordre inverse du tri, l'un d'eux porte un accent -- `relire()`
trie sans accent, pas en octets --, si bien qu'une cible en tete du disque se
retrouve en queue de liste. Une fabrique qui poserait ses fichiers deja tries
mesurerait les deux ordres a la fois sans jamais les distinguer.

Les drapeaux qu'on fait VARIER, et pourquoi
-------------------------------------------
« Une garde qui ne fait varier aucun de ses drapeaux ne mesure qu'un seul
chemin » (`CLAUDE.md`, 2026-09-06). Sont joues dans les **deux** sens :
`montrer_fichiers` (les deux regimes des six sites), `montrer_caches`,
`selection_multiple`, `accepte` qui refuse ou non, et `ascii_seul` -- ce
dernier sur un rendu ou le repli change quelque chose, la colonne de droite des
fichiers et le separateur de la ligne d'etat.
"""
from __future__ import annotations

import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[3]
if str(_RACINE / "src") not in sys.path:  # pragma: no cover - amorce du banc
    sys.path.insert(0, str(_RACINE / "src"))

import pytest

from mixed_media_utility.tui import (ecran_projet, explorateur, jetons,
                                     palier_profil_defaut as ppd, projets)
from mixed_media_utility.tui.coque import CoqueTui, PalierTemoin


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

#: Les douze fichiers, dans l'ordre du TRI de `relire()` -- dossiers d'abord,
#: puis fichiers, chacun **sans accent**. `é2_ecran.tiff` commence par un `é` :
#: en OCTETS il se rangerait apres `zz`, ce qui ferait de lui la queue de la
#: liste. Le tri du module -- `_sans_accent`, donc `e2_ecran` -- le place entre
#: `e1` et `e3`. C'est exactement l'ecart que l'AC 8 demande de mesurer :
#: l'ordre de la LISTE n'est ni celui du disque ni celui des octets.
FICHIERS_TRIES = (
    "aa_premier.tiff",
    "bb_second.tiff",
    "cc_troisieme.tiff",
    "dd_quatrieme.tiff",
    "e1_avant_l_accent.tiff",
    "é2_ecran.tiff",
    "e3_apres_l_accent.tiff",
    "ff_sixieme.tiff",
    "gg_septieme.tiff",
    "hh_huitieme.tiff",
    "ii_neuvieme.tiff",
    "zz_dernier.tiff",
)

#: Les deux dossiers, tries. Cardinaux DIFFERENTS : la colonne de droite d'une
#: ligne de dossier doit rester distinguable de celle de sa voisine.
DOSSIERS_TRIES = ("aa_dossier", "zz_dossier")


def _poser_les_fichiers(base: Path) -> None:
    """Poser les douze fichiers **a l'envers du tri**, tailles toutes distinctes.

    L'ordre de creation est celui que `iterdir()` rend le plus souvent sur les
    systemes de fichiers usuels ; le poser inverse est ce qui met le tri de
    `relire()` en tension.
    """
    for rang, nom in enumerate(reversed(FICHIERS_TRIES)):
        (base / nom).write_bytes(b"x" * (1024 + rang * 97))


def arbo_mixte(tmp_path) -> Path:
    """Deux dossiers **et** douze fichiers : quatorze entrees, pour neuf lignes.

    La liste deborde donc la fenetre (`HAUTEUR_LISTE` vaut 9), ce qui est la
    seule facon de mesurer que le recadrage a bien eu lieu : sur une liste plus
    courte que la fenetre, un `_recadrer()` supprime resterait invisible.
    """
    base = tmp_path / "telechargements"
    base.mkdir()
    for rang, nom in enumerate(DOSSIERS_TRIES):
        dossier = base / nom
        dossier.mkdir()
        for n in range(rang * 3):
            (dossier / f"sous_{n}").mkdir()
    _poser_les_fichiers(base)
    return base


def arbo_de_fichiers(tmp_path) -> Path:
    """Douze fichiers et **aucun dossier**.

    C'est la seule disposition ou un fichier peut occuper le rang 0 : `relire()`
    place toujours les dossiers d'abord. Sans elle, « la cible en tete » ne
    serait jamais jouee pour de vrai.
    """
    base = tmp_path / "scans_du_prestataire"
    base.mkdir()
    _poser_les_fichiers(base)
    return base


def coller_dans_l_adresse(exp, chemin) -> None:
    """Le geste d'Egan, verbatim : `Tab`, tout selectionner, `Ctrl+V`."""
    if not exp.dans_la_saisie:
        exp.basculer_la_saisie()
    exp.saisie, exp.caret = "", 0
    exp.coller(str(chemin))


def taper_dans_l_adresse(exp, chemin) -> None:
    """L'AUTRE geste : taper le chemin, caractere par caractere.

    Il n'est pas equivalent au collage, et c'est un mutant survivant qui l'a
    montre : en tapant, **tous les prefixes intermediaires sont inexistants**,
    donc `_refus` porte deja `ADRESSE_INEXISTANTE` quand la derniere lettre
    fait enfin exister le fichier. Un collage part au contraire d'un refus
    vide et ne mesure jamais l'effacement.
    """
    if not exp.dans_la_saisie:
        exp.basculer_la_saisie()
    exp.saisie, exp.caret = "", 0
    for caractere in str(chemin):
        exp.frapper(caractere)


def rangs(exp) -> list[str]:
    return [e.chemin.name for e in exp.entrees]


def _app(ecran) -> CoqueTui:
    return CoqueTui(paliers=[ecran, PalierTemoin("Ateliers", "q quitter")])


# ---------------------------------------------------------------------------
# AC 1 -- le dossier parent, curseur POSE sur le fichier
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nom, place", [
    (FICHIERS_TRIES[0], "tete du bloc des fichiers"),
    (FICHIERS_TRIES[5], "milieu, et c'est le nom accentue"),
    (FICHIERS_TRIES[-1], "queue de la liste, et tete du disque"),
])
def test_AC1_un_chemin_de_FICHIER_montre_son_dossier_curseur_POSE_dessus(
        tmp_path, nom, place):
    """AC 1 et AC 8. Trois places, dont les deux bords du bloc des fichiers.

    Ce que la mesure attrape et qu'une seule place ne verrait pas : un curseur
    pose **avant** `relire()` -- qui remet `curseur` et `premier_visible` a
    zero -- rendrait 0 pour les trois, donc resterait vert sur la premiere.
    """
    base = arbo_mixte(tmp_path)
    cible = base / nom
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)

    coller_dans_l_adresse(exp, cible)

    assert exp.dossier == base, "l'ecran va au dossier PARENT du fichier"
    assert rangs(exp) == list(DOSSIERS_TRIES) + list(FICHIERS_TRIES), (
        "dossiers d'abord, puis fichiers, chacun trie SANS ACCENT -- l'ordre "
        f"du disque est l'inverse. {rangs(exp)}")
    attendu = rangs(exp).index(nom)
    assert exp.curseur == attendu, (
        f"curseur attendu au rang {attendu} ({place}), lu {exp.curseur}")
    assert exp.entree_courante.chemin == cible
    assert exp.cible_de_validation() == cible, "et `⏎` le validerait"
    assert exp.etat(200) == str(base), (
        "aucun refus n'est pose : la cible a ete TROUVEE, elle n'est pas "
        f"seulement la ou le curseur retombe. {exp.etat(200)!r}")


def test_AC1_la_cible_en_QUEUE_fait_DEFILER_la_fenetre(tmp_path):
    """AC 1, second volet : « la fenetre de defilement recadree pour qu'il soit
    visible ».

    Mutant vise : `_recadrer()` retire de la branche fichier. Le curseur serait
    au bon rang et la fenetre resterait sur les neuf premieres lignes -- le
    modele aurait raison, l'operateur ne verrait rien. C'est pourquoi la mesure
    porte sur `fenetre()` **et** sur les lignes rendues, jamais sur le seul
    `curseur`.
    """
    base = arbo_mixte(tmp_path)
    cible = base / FICHIERS_TRIES[-1]
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)

    coller_dans_l_adresse(exp, cible)

    premier, dernier = exp.fenetre()
    assert premier > 0, (
        "quatorze entrees pour neuf lignes : atteindre la queue DOIT faire "
        f"defiler la fenetre, lue ({premier}, {dernier})")
    assert premier <= exp.curseur <= dernier
    table = jetons.glyphes(False)
    portees = [l for l in exp.lignes_de_liste(76, False) if cible.name in l]
    assert len(portees) == 1, portees
    assert portees[0].strip().startswith(table["curseur"]), (
        f"la ligne visible doit porter le curseur : {portees[0]!r}")


def test_AC1_le_chemin_TAPE_efface_le_refus_pose_par_ses_propres_prefixes(
        tmp_path):
    """AC 1 et AC 2, sur l'autre geste. **Mutant survivant, ferme ici.**

    En tapant, la barre traverse une dizaine de prefixes qui n'existent pas :
    `.../z`, `.../zz`, `.../zz_d`... Chacun pose `ADRESSE_INEXISTANTE`. La
    derniere lettre fait exister le fichier -- et si la branche fichier
    n'efface pas le refus, la ligne d'etat continue d'annoncer l'absence d'un
    fichier qui est **sous le curseur**. C'est-a-dire exactement le defaut que
    la story ferme, reapparu par l'autre porte.

    Le collage ne le voyait pas : il part d'un refus vide.
    """
    base = arbo_mixte(tmp_path)
    cible = base / FICHIERS_TRIES[-1]
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)

    exp.basculer_la_saisie()
    exp.saisie, exp.caret = "", 0
    for caractere in str(cible)[:-1]:
        exp.frapper(caractere)
    assert exp.etat() == explorateur.ADRESSE_INEXISTANTE, (
        "il manque une lettre : le refus DOIT etre pose a cet instant, sinon "
        "le test qui suit ne mesure pas son effacement")

    exp.frapper(str(cible)[-1])
    assert exp.entree_courante.chemin == cible
    assert exp.etat(200) == str(base), (
        "le refus n'a pas ete efface : la ligne d'etat annonce encore "
        f"l'absence d'un fichier qui est sous le curseur. {exp.etat(200)!r}")


def test_AC1_le_volet_SYMETRIQUE_un_fichier_en_TETE_de_liste(tmp_path):
    """La tete VRAIE du rang 0, qui n'existe que sans dossier dans la liste.

    Volet symetrique du test de queue : sans lui, un placement qui rendrait
    toujours le dernier rang passerait les deux autres cas.
    """
    base = arbo_de_fichiers(tmp_path)
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)

    coller_dans_l_adresse(exp, base / FICHIERS_TRIES[0])
    assert exp.curseur == 0 and exp.premier_visible == 0
    assert exp.entree_courante.chemin == base / FICHIERS_TRIES[0]
    # **Et la cible a bien ete TROUVEE**, elle n'est pas seulement la ou le
    # curseur retombe par defaut. Mutant mesure : un balayage qui saute la
    # PREMIERE entree rend « pas trouve », donc le curseur reste a zero -- ce
    # qui est ici la bonne reponse par accident. Les trois assertions du dessus
    # restaient vertes ; la ligne d'etat, elle, disait la verite.
    assert exp.etat(200) == str(base), (
        "un refus est pose : la cible n'a pas ete trouvee, le curseur est "
        f"reste a zero par defaut. {exp.etat(200)!r}")

    coller_dans_l_adresse(exp, base / FICHIERS_TRIES[-1])
    assert exp.curseur == len(FICHIERS_TRIES) - 1, (
        "et la queue de la MEME liste, pour que le test ne soit pas vert "
        "parce que le curseur ne bouge jamais")
    assert exp.etat(200) == str(base)


def test_AC1_depuis_la_liste_des_VOLUMES_le_fichier_atteint_son_dossier(
        tmp_path):
    """La saisie **sort de la liste des volumes**. *Mutant survivant, ferme
    ici.*

    La branche dossier le faisait deja, et pour une raison ecrite : sans cela
    `relire()` rejoue les volumes et la liste ne suit pas ce qu'on tape. La
    branche fichier a exactement le meme besoin, et rien ne le disait -- avec
    le mutant, coller un chemin de fichier depuis les volumes rendait la liste
    des VOLUMES avec `self.dossier` pose sur le parent : deux etats qui se
    contredisent, et aucune erreur.

    `lister_volumes` est le point d'injection prevu par le constructeur ; le
    disque, lui, est reel -- c'est le dossier parent qu'on veut voir apparaitre.
    """
    base = arbo_mixte(tmp_path)
    cible = base / FICHIERS_TRIES[5]
    racine = Path(base.anchor)
    exp = explorateur.Explorateur(racine, montrer_fichiers=True,
                                  lister_volumes=lambda: [racine])
    assert exp.remonter() is True, "le montage du banc lui-meme a echoue"
    assert exp.aux_volumes is True

    coller_dans_l_adresse(exp, cible)

    assert exp.aux_volumes is False, (
        "la saisie doit sortir du mode volumes, sinon `relire()` rejoue les "
        "volumes et la liste ne suit pas ce qu'on colle")
    assert exp.dossier == base
    assert rangs(exp) == list(DOSSIERS_TRIES) + list(FICHIERS_TRIES), rangs(exp)
    assert exp.entree_courante.chemin == cible


# ---------------------------------------------------------------------------
# AC 2 -- la frontiere NEGATIVE : aucun chemin existant ne rend le message
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("montrer_fichiers", [False, True])
@pytest.mark.parametrize("montrer_caches", [False, True])
def test_AC2_aucun_chemin_EXISTANT_ne_rend_ADRESSE_INEXISTANTE(
        tmp_path, montrer_fichiers, montrer_caches):
    """AC 2, frontiere directe et negative, balayee sur TOUT l'arbre.

    Les quatre combinaisons des deux drapeaux sont jouees : la phrase ne doit
    dependre d'aucun des deux, et c'est precisement ce qu'un banc a un seul
    regime laisserait passer.
    """
    base = arbo_mixte(tmp_path)
    (base / ".rush_cache.tiff").write_bytes(b"x" * 32)
    chemins = [base, base.parent] + sorted(base.rglob("*"))
    assert len(chemins) >= 17, chemins

    exp = explorateur.Explorateur(base.parent,
                                  montrer_fichiers=montrer_fichiers)
    exp.montrer_caches = montrer_caches
    for chemin in chemins:
        coller_dans_l_adresse(exp, chemin)
        assert exp.etat() != explorateur.ADRESSE_INEXISTANTE, (
            f"{chemin} existe, et l'ecran annonce son absence")


def test_AC2_un_lien_symbolique_CASSE_existe_aussi(tmp_path):
    """`lexists`, et non `exists` -- mutant direct.

    Un lien casse EXISTE comme entree de son dossier, et `relire()` le montre
    (finding `E16` : « un lien casse vers un rush deplace est LE symptome que
    l'operateur cherche »). Lui repondre « rien n'existe a cette adresse »
    serait le meme mensonge que celui que cette story ferme.
    """
    base = arbo_mixte(tmp_path)
    casse = base / "aa_lien_casse.tiff"
    casse.symlink_to(base / "jamais_ecrit.tiff")
    assert not casse.exists() and casse.is_symlink()

    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)
    coller_dans_l_adresse(exp, casse)

    assert exp.dossier == base
    assert exp.etat() != explorateur.ADRESSE_INEXISTANTE, exp.etat()
    assert exp.entree_courante.chemin == casse
    assert exp.entree_courante.illisible is True, (
        "il se voit, et la colonne de droite dit qu'il ne se lit pas")


# ---------------------------------------------------------------------------
# AC 3 -- ce qui n'existe VRAIMENT pas ne bouge pas
# ---------------------------------------------------------------------------

def test_AC3_un_chemin_qui_n_existe_pas_garde_le_comportement_d_aujourd_hui(
        tmp_path):
    """AC 3. Liste vide, le message, aucun `state-absent`, et la bifurcation
    « creer ici » intacte. Le refus qui reste juste ne bouge pas."""
    base = arbo_mixte(tmp_path)
    absent = base / "nexiste" / "pas_du_tout.tiff"
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)

    coller_dans_l_adresse(exp, absent)

    assert exp.entrees == []
    assert exp.curseur == 0 and exp.premier_visible == 0
    assert exp.etat() == explorateur.ADRESSE_INEXISTANTE
    rendu = "\n".join(exp.lignes(80, titre="T"))
    assert jetons.GLYPHES["absent"] not in rendu, rendu
    assert exp.valider() == absent, "la bifurcation « creer ici » reste"


# ---------------------------------------------------------------------------
# AC 4 -- le message cesse de parler de « dossier », la constante garde son nom
# ---------------------------------------------------------------------------

def test_AC4_le_message_ne_parle_plus_de_DOSSIER(tmp_path):
    """AC 4, frontiere negative sur le TEXTE.

    Elle est negative parce qu'aucun test positif ne verrait revenir l'ancienne
    formulation : un banc qui compare `etat()` a la constante reste vert quelle
    que soit la phrase qu'elle porte.
    """
    # **En minuscules** (finding de la couche 3) : la frontiere se contournait
    # par une majuscule -- `"aucun Dossier n'existe a cette adresse"` la
    # passait, et AC4 etait cassee sans que rien ne rougisse. Le mutant du
    # developpement n'eprouvait que la direction facile.
    _phrase = explorateur.ADRESSE_INEXISTANTE.lower()
    assert "dossier" not in _phrase, (
        "la phrase couvre desormais les deux natures : elle ne peut plus "
        f"nommer la seule qu'elle sait refuser. {explorateur.ADRESSE_INEXISTANTE!r}")
    assert "fichier" not in _phrase, (
        "et elle ne peut pas davantage nommer l'autre : elle les couvre TOUS")


def test_AC4_la_constante_garde_son_NOM_et_son_EXPORT():
    """Quatre bancs la lisent par son nom : le renommer les casserait en
    silence, et l'export est ce qui autorise `from ... import *`."""
    assert hasattr(explorateur, "ADRESSE_INEXISTANTE")
    assert "ADRESSE_INEXISTANTE" in explorateur.__all__
    for nom in ("FICHIERS_NON_MONTRES", "FICHIER_CACHE",
                "FICHIER_ABSENT_DE_LA_LISTE"):
        assert nom in explorateur.__all__, (
            f"{nom} est lu par les bancs comme la phrase qu'il porte : il "
            "s'exporte comme `ADRESSE_INEXISTANTE`")


def test_AC4_les_QUATRE_phrases_sont_DISTINCTES(tmp_path):
    """Mutant vise : deux motifs interchangeables.

    Quatre phrases qui se vaudraient ne diraient rien de plus qu'un silence --
    c'est le mutant `N6` de la 11.2b, pose sur une autre paire de motifs.
    """
    phrases = [explorateur.ADRESSE_INEXISTANTE,
               explorateur.FICHIERS_NON_MONTRES,
               explorateur.FICHIER_CACHE,
               explorateur.FICHIER_ABSENT_DE_LA_LISTE]
    assert len(set(phrases)) == 4, phrases
    assert all(p and p.strip() == p for p in phrases), phrases


# ---------------------------------------------------------------------------
# AC 5 -- la coche reste un geste de l'operateur
# ---------------------------------------------------------------------------

def test_AC5_en_selection_MULTIPLE_le_fichier_atteint_n_est_PAS_coche(tmp_path):
    """AC 5, `EPIC11-ARB-102`. Le curseur se pose ; la coche ne suit pas.

    Le volet POSITIF est dans le meme test, et il n'est pas decoratif : sans
    lui, une selection qui resterait vide **quoi qu'on fasse** passerait la
    frontiere negative sans rien mesurer.
    """
    base = arbo_mixte(tmp_path)
    cible = base / FICHIERS_TRIES[5]
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True,
                                  selection_multiple=True)

    coller_dans_l_adresse(exp, cible)
    assert exp.entree_courante.chemin == cible
    assert exp.selection == (), (
        "le curseur se pose, la coche reste le geste de l'operateur")
    assert exp.est_cochee(cible) is False

    exp.basculer_la_saisie()               # `Tab` : retour a la liste
    assert exp.entree_courante.chemin == cible, (
        "le curseur pose survit au retour a la liste, sinon la coche "
        "porterait sur une AUTRE entree")
    assert exp.basculer_la_coche() is None
    assert exp.selection == (cible,), "et le geste, lui, coche bien"


# ---------------------------------------------------------------------------
# AC 6 -- quand la liste ne PEUT PAS le montrer, elle le DIT
# ---------------------------------------------------------------------------

def test_AC6_montrer_fichiers_FAUX_va_au_parent_et_NOMME_la_raison(tmp_path):
    """AC 6, premier regime -- le DEFAUT du composant, et deux des six sites.

    Coller un chemin de fichier dans un ecran qui ne montre pas de fichiers est
    un geste **legitime** : l'operateur veut souvent designer le DOSSIER qui
    porte ce fichier. Aller au parent et le dire est la bonne reponse ; rendre
    une liste vide ne l'est pas (`EPIC11-ARB-89`, « jamais un blocage sec »).
    """
    base = arbo_mixte(tmp_path)
    exp = explorateur.Explorateur(base.parent)          # defaut : False
    assert exp.montrer_fichiers is False

    # **TAPE, pas colle** : la raison doit REMPLACER le refus que les prefixes
    # intermediaires ont pose, et non s'y ajouter ni le laisser en place.
    taper_dans_l_adresse(exp, base / FICHIERS_TRIES[5])

    assert exp.dossier == base, "on est bien alle au dossier parent"
    assert rangs(exp) == list(DOSSIERS_TRIES), "et il ne porte aucun fichier"
    assert exp.etat() == explorateur.FICHIERS_NON_MONTRES
    assert exp.curseur == 0
    assert exp.cible_de_validation() == base / FICHIERS_TRIES[5], (
        "la saisie designe toujours ce qu'on y a colle")


def test_AC6_un_fichier_CACHE_est_NOMME_cache(tmp_path):
    """AC 6, deuxieme regime, et le drapeau `montrer_caches` joue dans les DEUX
    sens : la phrase ne doit pas survivre a la revelation des caches."""
    base = arbo_mixte(tmp_path)
    cache = base / ".rush_cache.tiff"
    cache.write_bytes(b"x" * 64)
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)

    coller_dans_l_adresse(exp, cache)
    assert cache.name not in rangs(exp)
    assert exp.etat() == explorateur.FICHIER_CACHE

    exp.basculer_les_caches()
    assert cache.name in rangs(exp)
    assert exp.etat() != explorateur.FICHIER_CACHE, (
        "les caches sont montres : la raison a disparu avec eux")
    coller_dans_l_adresse(exp, cache)
    assert exp.entree_courante.chemin == cache, (
        "et le chemin colle atteint maintenant sa ligne")
    assert exp.etat() != explorateur.FICHIER_CACHE


def test_AC6_la_raison_la_plus_FORTE_prime_sur_l_autre(tmp_path):
    """Mutant vise : l'ORDRE des deux premieres questions de
    `_pourquoi_hors_liste`.

    Un fichier cache dans un ecran qui ne montre pas les fichiers cumule les
    deux raisons. Dire « ce fichier est cache » enverrait l'operateur reveler
    les caches -- geste qu'il PEUT faire, et qui ne le ferait pas apparaitre
    pour autant, puisque l'ecran ne porte aucun fichier. `montrer_fichiers`
    est le reglage du SITE, hors de sa main : c'est la raison qui **borne**
    l'autre, et c'est elle qui se dit.
    """
    base = arbo_mixte(tmp_path)
    cache = base / ".rush_cache.tiff"
    cache.write_bytes(b"x" * 64)
    exp = explorateur.Explorateur(base.parent)          # montrer_fichiers=False

    coller_dans_l_adresse(exp, cache)
    assert exp.etat() == explorateur.FICHIERS_NON_MONTRES, (
        "les deux raisons s'appliquent ; c'est la plus forte qui se dit")

    # Volet symetrique : le meme fichier cache, l'ecran montrant les fichiers.
    montre = explorateur.Explorateur(base.parent, montrer_fichiers=True)
    coller_dans_l_adresse(montre, cache)
    assert montre.etat() == explorateur.FICHIER_CACHE


def test_AC6_un_fichier_REFUSE_par_accepte_recoit_le_CURSEUR(tmp_path):
    """AC 6, troisieme regime. Il est **visible et non validable** : la ligne
    dit deja ce qu'il faut, donc l'ecran pose le curseur dessus et se tait.

    Le drapeau `accepte` est joue dans les deux sens dans le meme test : un
    fichier retenu et un fichier refuse, sur la meme liste.
    """
    base = arbo_mixte(tmp_path)
    refuse = base / "mm_notes.txt"
    refuse.write_bytes(b"x" * 700)
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True,
                                  accepte=lambda c: c.suffix == ".tiff")

    coller_dans_l_adresse(exp, refuse)
    assert exp.entree_courante.chemin == refuse
    assert exp.entree_courante.validable is False
    assert "pas une source" in exp.entree_courante.droite
    assert exp.etat() not in (explorateur.FICHIERS_NON_MONTRES,
                              explorateur.FICHIER_CACHE,
                              explorateur.FICHIER_ABSENT_DE_LA_LISTE), (
        "il figure dans la liste : aucune raison n'a a etre nommee")

    coller_dans_l_adresse(exp, base / FICHIERS_TRIES[5])
    assert exp.entree_courante.validable is True, (
        "et le volet symetrique, sur un fichier que le site accepte")


def test_AC6_le_TROISIEME_motif_n_est_pas_un_fourre_tout(tmp_path):
    """Le dossier parent qui ne se lit pas -- volume debranche, droits retires.

    Mutant vise : le troisieme motif rendu vide. La ligne d'etat retomberait
    alors sur `· sous-dossiers`, c'est-a-dire sur la mesure d'un dossier
    illisible, sans dire un mot du fichier qu'on venait de designer.
    """
    base = arbo_mixte(tmp_path)
    cible = base / FICHIERS_TRIES[5]
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True,
                                  lister=lambda _: None)

    coller_dans_l_adresse(exp, cible)
    assert exp.dossier == base
    assert exp.entrees == []
    assert exp.dossier_lisible is False
    assert exp.etat() == explorateur.FICHIER_ABSENT_DE_LA_LISTE, exp.etat()


# ---------------------------------------------------------------------------
# AC 7 -- la barre d'adresse ne change pas de ROLE
# ---------------------------------------------------------------------------

def test_AC7_Tab_garde_son_UNIQUE_role(tmp_path):
    """`EPIC11-ARB-51`, frontiere negative : « Donner a `Tab` un second role
    [...] rendait la saisie inatteignable au clavier »."""
    base = arbo_mixte(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True)
    depart = exp.dossier

    assert exp.dans_la_saisie is False
    exp.basculer_la_saisie()
    assert exp.dans_la_saisie is True and exp.dossier == depart, (
        "`Tab` entre dans la saisie, et ne change pas de dossier")
    exp.basculer_la_saisie()
    assert exp.dans_la_saisie is False and exp.dossier == depart


def test_AC7_les_fleches_deplacent_le_CARET_et_non_le_dossier(tmp_path):
    """Frontiere negative : `←→` gardent leur role dans la saisie, y compris
    apres qu'un chemin de fichier a fait changer de dossier."""
    base = arbo_mixte(tmp_path)
    cible = base / FICHIERS_TRIES[5]
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)

    coller_dans_l_adresse(exp, cible)
    caret, dossier, curseur = exp.caret, exp.dossier, exp.curseur
    assert exp.deplacer_le_caret(-1) is True
    assert exp.caret == caret - 1
    assert exp.dossier == dossier, "`←` n'a pas remonte d'un dossier"
    assert exp.curseur == curseur, "ni deplace le curseur de la liste"
    assert exp.deplacer_le_caret(1) is True
    assert exp.caret == caret


def test_AC7_sortir_de_la_saisie_RELIT_le_dossier_et_GARDE_le_curseur(tmp_path):
    """Finding `E7` -- la relecture ne bouge pas -- et ce que la story ajoute.

    Les deux moities se tiennent : la relecture est ce qui empeche l'impasse
    (liste vide + message a demeure), et la repose du curseur est ce qui
    empeche la story de livrer un curseur qui s'evapore au premier `Tab` --
    c'est-a-dire de ramener a la premiere des cent cinquante lignes qu'Egan
    cherche justement a ne plus defiler.
    """
    base = arbo_mixte(tmp_path)
    cible = base / FICHIERS_TRIES[-1]
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)

    coller_dans_l_adresse(exp, cible)
    rang = exp.curseur
    assert rang == len(rangs(exp)) - 1

    exp.basculer_la_saisie()
    assert exp.dans_la_saisie is False
    assert rangs(exp) == list(DOSSIERS_TRIES) + list(FICHIERS_TRIES), (
        "la liste a bien ete RELUE -- c'est la frontiere `E7`")
    assert exp.curseur == rang and exp.entree_courante.chemin == cible
    premier, dernier = exp.fenetre()
    assert premier <= exp.curseur <= dernier, (premier, dernier, exp.curseur)
    assert exp.deplacer(-1) is True, "et la liste repond aux fleches"


def test_le_curseur_pose_ne_SURVIT_PAS_a_une_saisie_redevenue_un_DOSSIER(
        tmp_path):
    """Mutant vise : la memoire du fichier pointe non remise a zero.

    Elle ne doit vivre que le temps d'un `Tab`. Coller un fichier, puis
    corriger l'adresse pour designer un DOSSIER, doit rendre la liste de ce
    dossier avec le curseur au depart -- et non celui du fichier qu'on vient
    d'abandonner.
    """
    base = arbo_mixte(tmp_path)
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)

    coller_dans_l_adresse(exp, base / FICHIERS_TRIES[-1])
    assert exp.curseur > 0
    coller_dans_l_adresse(exp, base)               # l'adresse redevient un dossier
    assert exp.curseur == 0

    exp.basculer_la_saisie()
    assert exp.curseur == 0, (
        "le fichier a ete abandonne : rien ne doit reposer son curseur")
    assert exp.dossier == base


def test_la_memoire_du_pointe_se_CONSOMME_au_premier_Tab(tmp_path):
    """Second volet du meme mutant : elle ne se repose pas deux fois.

    `Tab` pour revenir, puis `↓`, puis `Tab` aller et `Tab` retour : le second
    aller-retour part du dossier courant, pas du fichier d'il y a trois gestes.
    """
    base = arbo_mixte(tmp_path)
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)

    coller_dans_l_adresse(exp, base / FICHIERS_TRIES[-1])
    exp.basculer_la_saisie()
    exp.deplacer(-1)
    ailleurs = exp.curseur

    exp.basculer_la_saisie()               # `Tab` aller, saisie = le dossier
    exp.basculer_la_saisie()               # `Tab` retour
    assert exp.curseur == 0, (
        "la relecture `E7` remet le curseur a zero, et plus rien ne le "
        f"repose : lu {exp.curseur}, il etait a {ailleurs}")


# ---------------------------------------------------------------------------
# AC 8 -- l'appariement se fait par IDENTITE de `Path`
# ---------------------------------------------------------------------------

def test_AC8_l_appariement_se_fait_par_IDENTITE_et_non_par_NOM(tmp_path):
    """T2 : « chercher le chemin dans `self.entrees` par identite de `Path`,
    pas par nom : deux dossiers peuvent porter le meme nom de fichier ».

    La condition est **fabriquee** par le point d'injection `lister` -- le meme
    que les bancs de dossier illisible emploient --, parce que c'est le seul
    regime ou les deux comparaisons different : apres `relire()`, toutes les
    entrees partagent d'ordinaire le meme parent. Une liste qui porte
    l'homonyme d'un AUTRE dossier **en premiere position** est exactement ce
    qu'un `find` par nom rendrait a tort.
    """
    base = arbo_mixte(tmp_path)
    voisin = tmp_path / "un_autre_dossier"
    voisin.mkdir()
    homonyme = voisin / FICHIERS_TRIES[5]
    homonyme.write_bytes(b"x" * 11)
    cible = base / FICHIERS_TRIES[5]

    exp = explorateur.Explorateur(
        base.parent, montrer_fichiers=True,
        lister=lambda _: [homonyme, cible, base / FICHIERS_TRIES[0]])

    coller_dans_l_adresse(exp, cible)
    assert exp.entree_courante.chemin == cible, (
        "l'homonyme est en TETE de la liste : un appariement par nom "
        f"l'aurait rendu. Lu {exp.entree_courante.chemin}")
    assert exp.entree_courante.chemin != homonyme
    assert exp.curseur == 2, (
        "les deux homonymes portent la MEME cle de tri ; l'injecte passe "
        f"donc devant, au rang 1, et la cible est au rang 2. Lu {exp.curseur}")


def test_AC8_un_homonyme_dans_un_dossier_VOISIN_n_est_pas_atteint(tmp_path):
    """Le volet reel du precedent, sans injection : deux dossiers portant le
    meme nom de fichier, colles l'un apres l'autre."""
    base = arbo_mixte(tmp_path)
    voisin = tmp_path / "un_autre_dossier"
    voisin.mkdir()
    for nom in ("aa_premier.tiff", FICHIERS_TRIES[5]):
        (voisin / nom).write_bytes(b"x" * 11)

    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)
    coller_dans_l_adresse(exp, voisin / FICHIERS_TRIES[5])
    assert exp.dossier == voisin
    assert exp.entree_courante.chemin == voisin / FICHIERS_TRIES[5]

    coller_dans_l_adresse(exp, base / FICHIERS_TRIES[5])
    assert exp.dossier == base
    assert exp.entree_courante.chemin == base / FICHIERS_TRIES[5]


# ---------------------------------------------------------------------------
# AC 9 -- les drapeaux jouent dans les DEUX sens
# ---------------------------------------------------------------------------

#: Une fabrique aux noms ASCII PURS, pour la seule mesure qui balaye le rendu
#: entier. `arbo_mixte` ne convient pas ici, et la raison est un point de
#: produit plutot qu'une commodite : le nom d'un fichier est une DONNEE, jamais
#: du chrome -- l'ecran ne le replie pas, et il a raison, un `é2_ecran.tiff`
#: rendu `e2_ecran.tiff` designerait un fichier qui n'existe pas. Balayer un
#: rendu qui porte ce nom mesurerait donc la donnee au lieu du chrome.
FICHIERS_ASCII = ("aa_source.tiff", "mm_source.tiff", "zz_source.tiff")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_AC9_le_fichier_atteint_se_rend_dans_les_DEUX_modes(tmp_path,
                                                            ascii_seul):
    """AC 9. Le repli change quelque chose sur ce rendu-la -- le curseur, les
    filets, la colonne de droite et le separateur `·` de la ligne d'etat --, et
    c'est ce qui fait de ce cas une mesure plutot qu'une repetition."""
    base = tmp_path / "sources"
    base.mkdir()
    for rang, nom in enumerate(reversed(FICHIERS_ASCII)):
        (base / nom).write_bytes(b"x" * (2048 + rang * 13))
    cible = base / FICHIERS_ASCII[-1]
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)

    coller_dans_l_adresse(exp, cible)
    assert exp.curseur == len(FICHIERS_ASCII) - 1, exp.curseur
    exp.basculer_la_saisie()               # la ligne d'etat porte ses mesures
    rendu = "\n".join(exp.lignes(80, titre="Scanner", ascii_seul=ascii_seul))
    assert cible.name in rendu, rendu
    if ascii_seul:
        assert rendu.isascii(), (
            "un seul caractere hors ASCII suffit a casser un terminal en "
            f"`--ascii` : {[c for c in rendu if not c.isascii()][:5]}")
    else:
        assert not rendu.isascii(), (
            "le mode UTF-8 doit porter au moins un glyphe : sans cela les "
            "deux sens du drapeau mesureraient la meme chose")


def test_AC9_les_QUATRE_phrases_d_etat_survivent_au_repli_ASCII(tmp_path):
    """Frontiere negative. `etat()` rend `self._refus` **avant** de construire
    sa table de glyphes et sans passer par `_replie` : un accent pose dans
    l'une de ces phrases fuirait tel quel en `--ascii`, et aucun banc de rendu
    ne le verrait puisque la ligne d'etat n'est pas une ligne de liste.

    Les quatre regimes sont atteints par le PRODUIT, pas ecrits a la main :
    c'est ce qui fait que la mesure suit la phrase si elle change.
    """
    base = arbo_mixte(tmp_path)
    cache = base / ".rush_cache.tiff"
    cache.write_bytes(b"x" * 64)

    montre = explorateur.Explorateur(base.parent, montrer_fichiers=True)
    dossiers_seuls = explorateur.Explorateur(base.parent)
    aveugle = explorateur.Explorateur(base.parent, montrer_fichiers=True,
                                      lister=lambda _: None)
    regimes = [
        (montre, base / "jamais_ecrit.tiff", explorateur.ADRESSE_INEXISTANTE),
        (dossiers_seuls, base / FICHIERS_TRIES[5],
         explorateur.FICHIERS_NON_MONTRES),
        (montre, cache, explorateur.FICHIER_CACHE),
        (aveugle, base / FICHIERS_TRIES[5],
         explorateur.FICHIER_ABSENT_DE_LA_LISTE),
    ]
    for exp, chemin, attendue in regimes:
        coller_dans_l_adresse(exp, chemin)
        assert exp.etat() == attendue, (chemin, exp.etat())
        for mode in (False, True):
            lue = exp.etat(76, ascii_seul=mode)
            assert lue == attendue, (mode, lue)
            assert lue.isascii(), (
                f"la phrase doit tenir en ASCII pur : {lue!r}")


# ---------------------------------------------------------------------------
# AC 10 -- les DEUX regimes, mesures sur des ecrans montes
# ---------------------------------------------------------------------------

def test_AC10_regime_montrer_fichiers_FAUX_sur_l_ecran_Projet(tmp_path, banc):
    """`ecran_projet.py` prend le defaut. Le collage passe par le point
    d'entree reel de l'ecran -- `coller`, ce que l'evenement `Paste` atteint --
    et non par le modele : c'est la couture qui est mesuree ici."""
    base = arbo_mixte(tmp_path)
    cible = base / FICHIERS_TRIES[5]
    ecran = ecran_projet.EcranProjet(
        recents=projets.Recents(tmp_path / "reglages" / "recents-v1.json"))

    async def scenario(pilote):
        cible_ecran = pilote.app.screen
        cible_ecran.traiter("tab")             # des recents vers l'explorateur
        cible_ecran.traiter("tab")             # de la liste vers la saisie
        cible_ecran.explorateur.saisie = ""
        cible_ecran.explorateur.caret = 0
        cible_ecran.coller(str(cible))
        cible_ecran.rafraichir()
        return (cible_ecran.explorateur.dossier, cible_ecran.etat(),
                cible_ecran.explorateur.montrer_fichiers)

    dossier, etat, montrer = banc(_app(ecran), scenario)
    assert montrer is False, "c'est bien le regime par defaut qui est mesure"
    assert dossier == base, "l'ecran est alle au dossier PARENT"
    assert etat == explorateur.FICHIERS_NON_MONTRES, etat
    assert etat != explorateur.ADRESSE_INEXISTANTE


def test_AC10_regime_montrer_fichiers_VRAI_sur_le_Profil_par_defaut(tmp_path,
                                                                    banc):
    """`palier_profil_defaut.py` emploie `montrer_fichiers=True`, comme les
    trois ecrans de Scan. Le fichier colle atteint sa ligne, et il est validable
    parce que le site l'accepte -- `profil_acceptable` retient les `.json`."""
    base = tmp_path / "valise"
    base.mkdir()
    for nom in ("aa_autre.json", "mm_profil.json", "zz_dernier.json"):
        (base / nom).write_text("{}", encoding="utf-8")
    cible = base / "zz_dernier.json"
    ecran, prises = ppd.EcranProfilParDefaut(None, confirmer=[].append,
                                             profils=[]), []

    async def scenario(pilote):
        ecran.zone = ppd.ZONE_EXPLORATEUR
        exp = ecran.explorateur
        exp.basculer_la_saisie()
        exp.saisie, exp.caret = "", 0
        exp.coller(str(cible))
        await pilote.pause()
        return (exp.montrer_fichiers, exp.dossier, exp.curseur,
                [e.chemin.name for e in exp.entrees],
                exp.entree_courante.chemin, exp.entree_courante.validable,
                exp.etat())

    montrer, dossier, curseur, noms, courant, validable, etat = banc(
        _app(ecran), scenario)
    assert montrer is True, "c'est bien l'autre regime qui est mesure"
    assert dossier == base
    assert noms == ["aa_autre.json", "mm_profil.json", "zz_dernier.json"]
    assert curseur == 2 and courant == cible, (curseur, courant)
    assert validable is True, "le site accepte les `.json`"
    assert etat != explorateur.ADRESSE_INEXISTANTE, etat
    assert prises == [], "designer n'est pas confirmer"


# ---------------------------------------------------------------------------
# Findings de la revue en trois couches du 2026-09-09
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("montrer_fichiers", [False, True])
def test_REVUE_le_TAB_qui_suit_un_fichier_non_montrable_GARDE_la_raison(
    tmp_path, montrer_fichiers
):
    """`C2` de la couche 1 et `C2-1` de la couche 2, trouves INDEPENDAMMENT.

    `basculer_la_saisie` ignorait le retour de `_poser_le_curseur_sur`, la ou
    `_suivre_la_saisie` le garde. Or `Tab` vient d'appeler
    `_oublier_le_refus()` : la phrase mourait, le curseur restait au rang 0, et
    le geste d'Egan -- **coller, `Tab`, `Entree`** -- rendait un AUTRE fichier,
    sans un mot. C'est mot pour mot l'etat que le module declare inacceptable
    trente lignes plus haut.

    Le drapeau est joue dans les deux sens : a `True` la cible est cachee, a
    `False` c'est l'ecran qui ne montre pas les fichiers -- deux raisons
    differentes, un seul invariant.
    """
    base = arbo_mixte(tmp_path)
    cible = base / (".invisible.tiff" if montrer_fichiers else FICHIERS_TRIES[5])
    if montrer_fichiers:
        cible.write_bytes(b"x" * 4242)

    exp = explorateur.Explorateur(base.parent, montrer_fichiers=montrer_fichiers)
    coller_dans_l_adresse(exp, cible)
    raison_dans_la_saisie = exp.etat()
    assert raison_dans_la_saisie != explorateur.ADRESSE_INEXISTANTE

    exp.basculer_la_saisie()          # `Tab` : retour a la liste

    assert exp.etat() == raison_dans_la_saisie, (
        "la raison doit survivre au `Tab` : l'effacer laisse un curseur sur "
        "une autre entree, en silence")
    assert exp.cible_de_validation() != cible, (
        "hors saisie, la validation suit le CURSEUR -- et il n'a pas pu se "
        "poser : c'est precisement ce que la phrase doit dire")


def test_REVUE_le_TAB_qui_suit_un_fichier_MONTRABLE_efface_la_raison(tmp_path):
    """Volet symetrique du precedent : sans lui, garder la raison
    INCONDITIONNELLEMENT passerait le banc ci-dessus."""
    base = arbo_mixte(tmp_path)
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)
    coller_dans_l_adresse(exp, base / FICHIERS_TRIES[5])
    exp.basculer_la_saisie()
    assert exp.etat() != explorateur.FICHIERS_NON_MONTRES
    assert exp.etat() != explorateur.FICHIER_ABSENT_DE_LA_LISTE
    assert exp.cible_de_validation() == base / FICHIERS_TRIES[5]


def test_REVUE_un_dossier_ILLISIBLE_ne_repond_pas_le_reglage_de_l_ecran(tmp_path):
    """`C1` de la couche 1 et `C2-2` de la couche 2, trouves INDEPENDAMMENT.

    `_pourquoi_hors_liste` repondait depuis les drapeaux de l'ECRAN sans avoir
    etabli le moindre fait. Sur un dossier parent qui ne se lit pas, elle
    disait « cet ecran ne montre pas les fichiers » -- alors que **rien** n'a
    ete lu, dossiers compris, et que la phrase etait identique quand le dossier
    se lisait. Elle designait un obstacle qui n'etait pas le bon.
    """
    base = arbo_mixte(tmp_path)
    cible = base / FICHIERS_TRIES[5]
    exp = explorateur.Explorateur(
        base.parent, lister=lambda dossier: None if dossier == base else [])
    coller_dans_l_adresse(exp, cible)
    assert exp.dossier_lisible is False
    assert exp.etat() == explorateur.FICHIER_ABSENT_DE_LA_LISTE, (
        "un dossier qui ne se lit pas n'est pas un reglage d'ecran")


def test_REVUE_un_LIEN_CASSE_n_est_pas_masque_par_montrer_fichiers(tmp_path):
    """`C1` de la couche 1, second symptome.

    `relire()` range un lien symbolique casse parmi les **dossiers** (finding
    `E16`) : il figure donc dans la liste meme quand les fichiers n'y sont pas.
    Repondre « cet ecran ne montre pas les fichiers » designait un obstacle
    inexistant -- et ici, c'est `Ctrl+H` qui le ferait apparaitre.
    """
    base = arbo_mixte(tmp_path)
    casse = base / ".lien_casse"
    casse.symlink_to(base / "cible_absente")
    exp = explorateur.Explorateur(base.parent)          # montrer_fichiers False
    coller_dans_l_adresse(exp, casse)
    assert exp.etat() == explorateur.FICHIER_CACHE, (
        "un lien casse est porte par la liste des dossiers : ce qui le masque "
        "est le drapeau des CACHES, pas celui des fichiers")

    exp.basculer_les_caches()
    coller_dans_l_adresse(exp, casse)
    assert exp.etat() != explorateur.FICHIER_CACHE
    assert exp.entree_courante is not None
    assert exp.entree_courante.chemin == casse


def test_REVUE_un_fichier_CACHE_MONTRE_est_trouve_et_non_nomme_cache(tmp_path):
    """`C2-3` de la couche 2 : le drapeau etait joue dans les deux sens, jamais
    **la ou il change quelque chose**.

    Des que les caches sont montres, la cible entre dans la liste : le mutant
    qui retirait `and not self.montrer_caches` survivait aux 236 bancs.
    """
    base = arbo_mixte(tmp_path)
    cache = base / ".cache.tiff"
    cache.write_bytes(b"x" * 777)
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)
    exp.basculer_les_caches()
    coller_dans_l_adresse(exp, cache)
    assert exp.etat() != explorateur.FICHIER_CACHE
    assert exp.entree_courante is not None
    assert exp.entree_courante.chemin == cache


def test_REVUE_la_POINTE_ne_survit_pas_a_une_adresse_inexistante(tmp_path):
    """`C3` de la couche 1 : des trois branches qui ecrivent `_pointe`, deux
    avaient leur volet symetrique, la troisieme non."""
    base = arbo_mixte(tmp_path)
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)
    coller_dans_l_adresse(exp, base / FICHIERS_TRIES[5])
    coller_dans_l_adresse(exp, base / "ce_fichier_n_existe_pas.tiff")
    assert exp.etat() == explorateur.ADRESSE_INEXISTANTE
    exp.basculer_la_saisie()
    assert exp.curseur == 0, (
        "aucune pointe ne doit survivre a une adresse inexistante")


def test_REVUE_la_POINTE_ne_survit_pas_a_une_REPRISE_DE_MEMOIRE(tmp_path):
    """Couche 3 : `reprendre_la_memoire` est une TROISIEME sortie de la saisie,
    et elle arrive de l'exterieur.

    Sans la remise a zero, le curseur se reposait sur un fichier designe deux
    changements de dossier plus tot -- l'invariant que la story declare mesure
    etait faux du produit.
    """
    base = arbo_mixte(tmp_path)
    autre = base / "aa_dossier"
    exp = explorateur.Explorateur(base.parent, montrer_fichiers=True)
    coller_dans_l_adresse(exp, base / FICHIERS_TRIES[-1])
    assert exp._pointe is not None

    memoire = explorateur.MemoireDeSession()
    memoire.dernier_valide = autre
    assert exp.reprendre_la_memoire(memoire)
    assert exp._pointe is None
    assert exp.dossier == autre
    assert exp.curseur == 0
