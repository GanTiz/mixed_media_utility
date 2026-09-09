# -*- coding: utf-8 -*-
"""Story 11.4b, lot S5 -- la liste des profils de calibration se LIT (AC 8).

Le fait F8 de la fiche, mesure et non suppose : `DESIGNATED_PROFILES_KEY`
n'apparaissait qu'a **deux** endroits de tout le depot -- sa definition
(`io/profile_designation.py:61`) et son ecriture (`:285-286`). **Un ecrivain,
zero lecteur.** Les trois lectures publiques du module repondent a d'autres
questions : `read_designated_document` relit un fichier designe,
`default_profile_entry` et `default_profile_path` rendent **le defaut**. Un
ecran qui doit proposer un profil parmi ceux du projet n'avait aucun moyen de
les enumerer.

`designated_profiles` ferme ce trou, et ce banc l'appelle **comme la 11.5
l'appellera** : sur un projet reel dont le registre a ete rempli par le vrai
ecrivain (`record_designated_profile`), jamais par un `project.json` bricole a
la main -- sauf la ou c'est precisement le contenu bricole qui est mesure.

**Le piege central, celui contre lequel la moitie de ce fichier est ecrite** :
un **repli automatique**. `EPIC5-ARB-83`, propriete 2, verbatim : « **Aucun
repli automatique.** Sans profil designe, le lot est livre **brut**, avec un
avertissement. Choisir a la place de l'operateur -- « il n'y a qu'un profil dans
le projet, ce doit etre celui-la » -- reintroduirait exactement le defaut que
`EPIC5-ARB-83` supprime, et le reintroduirait sous une forme plus difficile a
voir. » Une fonction qui **enumere** est exactement l'endroit ou un balayage de
`versions/calibration/` reviendrait sans qu'on le remarque, et deux tests de ce
banc existent pour cela seul.

**Regle des fabriques (AC 8.2)** : **trois** profils distinguables -- trois
presses, donc trois jeux de coefficients deux a deux differents --, et la cible
est celle qui n'est **ni la premiere ni la derniere** du registre. Le registre
etant trie par `chain_id` a l'ecriture, `chaine-mu` y tombe au **milieu** tout
en etant la **derniere ecrite** : un lecteur qui rendrait le premier, comme un
lecteur qui rendrait le dernier, se demasque sur la meme fabrique.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility.io import calibration_profile  # noqa: E402
from mixed_media_utility.io import extraction_manifest  # noqa: E402
from mixed_media_utility.io import profile_designation as designation  # noqa: E402
from mixed_media_utility.io import project_layout  # noqa: E402

import test_profil_designe as designe  # noqa: E402


#: Les trois chaines de la fabrique, **dans leur ordre d'ecriture**. Elles sont
#: reprises de `test_profil_designe` et non redefinies : deux jeux d'identites
#: voisins dans deux bancs seraient deux fabriques a maintenir.
CHAINES = designe._CHAINES

#: La chaine **visee**. Le registre etant trie par `chain_id`, l'ordre lu est
#: alpha, mu, zeta : la cible est donc la **deuxieme des trois** a la lecture,
#: et la **troisieme des trois** a l'ecriture. Ni premiere ni derniere dans
#: l'un comme dans l'autre ordre.
CHAINE_VISEE = "chaine-mu"

#: Rang attendu de la cible dans la liste rendue.
RANG_VISE = 1


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


def _projet_a_trois_profils(tmp_path: Path) -> tuple[Path, dict]:
    """Un projet reel dont les trois profils sont designes par le VRAI ecrivain.

    Trois profils, et ils sont distinguables sur **cinq** familles de valeurs a
    la fois : leur `chain_id`, leurs coefficients (trois presses deux a deux
    differentes), leur nom de fichier d'origine, leur etiquette et leur
    commentaire. Une permutation entre deux entrees se verrait donc sur
    n'importe laquelle -- c'est la lecon d'`EPIC5-ARB-39` : un test qui
    n'asserte que sur une famille de valeurs survit aux mutations des autres.

    Ils sont poses avec des horodates **distinctes** et **decroissantes** avec
    le rang d'ecriture : un lecteur qui retrierait par date rendrait un ordre
    different de celui du registre, et le banc le verrait.

    Rend le couple `(projet, entrees attendues par chain_id)`.
    """
    projet = designe._projet(tmp_path, "projet-de-l-atelier")
    attendues = {}
    for rang, (chaine, presse) in enumerate(zip(CHAINES, designe._PRESSES)):
        document = designe._document(chaine, presse)
        document[calibration_profile.LABEL_FIELD] = f"etiquette-{chaine}"
        document[calibration_profile.COMMENT_FIELD] = f"note de {chaine}"
        source = tmp_path / f"ailleurs-{rang}" / f"fichier-source-{rang}.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(calibration_profile.serialize_profile(document),
                          encoding="utf-8")
        _document_ecrit, chemin = designation.import_designated_profile(
            projet, source, record=False)
        attendues[chaine] = designation.record_designated_profile(
            projet, document, project_path=chemin, source=source,
            designated_at=f"2026-08-{30 - rang:02d}T10:00:00Z")
    return projet, attendues


def _manifeste(projet: Path) -> dict:
    return json.loads(
        (projet / extraction_manifest.MANIFEST_FILENAME).read_text(
            encoding="utf-8"))


def _ecrire_le_manifeste(projet: Path, manifeste: dict) -> None:
    (projet / extraction_manifest.MANIFEST_FILENAME).write_text(
        json.dumps(manifeste, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# AC 8.1 et AC 8.2 -- la liste, et la cible ailleurs qu'en premiere position
# ---------------------------------------------------------------------------


def test_la_fabrique_porte_bien_TROIS_profils_deux_a_deux_DISTINGUABLES(tmp_path):
    """La fabrique tient sa promesse, plutot que de la declarer en commentaire.

    Sans ce garde-fou, tous les tests d'appariement de ce fichier seraient
    verts sur trois entrees identiques -- c'est-a-dire exactement le defaut que
    la regle des fabriques existe pour empecher, et qui a coute quatre stories
    a ce depot (5.6, 5.7, 5.8, puis la vague 2 bis).
    """
    _projet, attendues = _projet_a_trois_profils(tmp_path)
    assert len(attendues) == 3
    for champ in ("chain_id", "path", designation.ENTRY_SOURCE_KEY,
                  designation.ENTRY_DESIGNATED_AT_KEY,
                  calibration_profile.LABEL_FIELD,
                  calibration_profile.COMMENT_FIELD):
        valeurs = [entree[champ] for entree in attendues.values()]
        assert len(set(valeurs)) == 3, (champ, valeurs)


def test_la_liste_rend_LES_TROIS_entrees_dans_l_ordre_du_REGISTRE(tmp_path) -> None:
    """AC 8.1 : le lecteur est symetrique de l'ecrivain, entree pour entree.

    L'egalite porte sur les entrees **entieres**, champ par champ, et pas sur
    leurs seuls `chain_id` : une entree amputee de son chemin, de son etiquette
    ou de son horodate porterait le meme identifiant et ne serait plus
    autoportante -- c'est-a-dire ne repondrait plus a la question pour laquelle
    elle existe.

    L'ordre est celui du registre, deja trie par `chain_id` a l'ecriture pour
    que « deux projets ayant vu les memes profils dans un ordre different
    rendent le meme document ». Le retrier ici serait une seconde redaction de
    cette regle, et le banc mesure donc l'ordre et non un ensemble.
    """
    projet, attendues = _projet_a_trois_profils(tmp_path)

    liste = designation.designated_profiles(projet)

    assert [entree["chain_id"] for entree in liste] == sorted(CHAINES)
    assert liste == [attendues[chaine] for chaine in sorted(CHAINES)]
    # L'ordre du registre n'est **pas** celui de l'ecriture : sans cet ecart,
    # « ordre du registre » et « ordre d'ecriture » seraient indiscernables.
    assert [entree["chain_id"] for entree in liste] != list(CHAINES)


def test_la_liste_vise_le_profil_qui_n_est_PAS_LE_PREMIER(tmp_path) -> None:
    """AC 8.2 : la cible est la deuxieme des trois, et elle est lue comme telle.

    C'est la classe du mutant `M25` (`_find_lot`, story 5.7) : un lecteur qui
    rendrait toujours le premier element restait vert sur 257 tests, et la
    consequence reelle etait d'ecrire les cardinaux **sur le mauvais lot**. Ici
    la consequence serait qu'un ecran propose -- et applique -- un profil que
    l'operatrice n'a pas choisi, c'est-a-dire le defaut meme que
    `EPIC5-ARB-83` supprime.

    La cible est aussi la **derniere ecrite** : le mutant symetrique (« rendre
    la derniere entree ») tombe donc sur la meme fabrique.
    """
    projet, attendues = _projet_a_trois_profils(tmp_path)

    liste = designation.designated_profiles(projet)
    vise = liste[RANG_VISE]

    assert vise["chain_id"] == CHAINE_VISEE
    assert vise == attendues[CHAINE_VISEE]
    # Les quatre familles de valeurs qui distinguent la cible de ses voisines,
    # asserties une par une : un test qui ne comparerait que le `chain_id`
    # survivrait a une entree dont le chemin serait celui d'un autre profil.
    assert vise[designation.ENTRY_PATH_KEY] != \
        attendues[CHAINES[0]][designation.ENTRY_PATH_KEY]
    assert vise[designation.ENTRY_SOURCE_KEY] == "fichier-source-2.json"
    assert vise[calibration_profile.LABEL_FIELD] == f"etiquette-{CHAINE_VISEE}"
    assert vise[calibration_profile.COMMENT_FIELD] == f"note de {CHAINE_VISEE}"
    assert vise[designation.ENTRY_DESIGNATED_AT_KEY] == "2026-08-28T10:00:00Z"


def test_les_entrees_restent_AUTOPORTANTES_quand_les_FICHIERS_ont_disparu(tmp_path):
    """AC 8.1 : « sans ouvrir le fichier, et sans le supposer encore present ».

    C'est la moitie manifest du couple d'Egan (« un profil = un fichier
    autoportant + une entree autoportante au manifest »), et c'est ce qui rend
    la liste affichable : sans elle, il faudrait ouvrir chaque profil pour
    montrer autre chose que des identites de chaine -- « c'est-a-dire
    precisement ce qu'Egan ne veut pas lire ».

    Les trois fichiers sont donc **effaces** avant la lecture. Une
    implementation qui balayerait `versions/calibration/` rendrait ici une
    liste vide ; une implementation qui relirait chaque document leverait.
    """
    projet, attendues = _projet_a_trois_profils(tmp_path)
    for chemin in sorted((projet / "versions" / "calibration").glob("*.json")):
        chemin.unlink()
    # Temoin : il n'y a effectivement plus rien a ouvrir.
    assert not list((projet / "versions" / "calibration").glob("*.json"))

    liste = designation.designated_profiles(projet)

    assert liste == [attendues[chaine] for chaine in sorted(CHAINES)]


# ---------------------------------------------------------------------------
# AC 8.3 -- aucun profil designe rend une liste VIDE, jamais une erreur
# ---------------------------------------------------------------------------


def test_un_projet_SANS_AUCUN_PROFIL_DESIGNE_rend_une_liste_VIDE(tmp_path) -> None:
    """AC 8.3, verbatim : « rend une liste **vide**, jamais une erreur »."""
    projet = designe._projet(tmp_path, "projet-neuf")

    assert designation.designated_profiles(projet) == []


def test_ni_manifest_ni_dossier_de_projet_ne_font_LEVER_la_lecture(tmp_path) -> None:
    """AC 8.3 : les trois formes d'absence rendent la meme chose -- rien.

    Un dossier de projet qui n'a pas encore ete persiste, un `project.json`
    illisible, une section `color` absente : aucune n'est un defaut de
    designation, et faire lever la lecture du registre transformerait un projet
    a demi ecrit en refus d'ouverture d'ecran. C'est le meme repli que
    `default_profile_entry` tient deja pour le defaut du projet.
    """
    assert designation.designated_profiles(tmp_path / "jamais-cree") == []

    sans_manifest = tmp_path / "sans-manifest"
    project_layout.ensure_project_layout(sans_manifest)
    assert designation.designated_profiles(sans_manifest) == []

    casse = tmp_path / "casse"
    project_layout.ensure_project_layout(casse)
    (casse / extraction_manifest.MANIFEST_FILENAME).write_text(
        "{ ceci n'est pas du JSON", encoding="utf-8")
    assert designation.designated_profiles(casse) == []


def test_la_liste_n_INVENTE_aucun_profil_BALAYE_du_disque(tmp_path) -> None:
    """AC 8.3 et `EPIC5-ARB-83`, propriete 2, verbatim :

    « **Aucun repli automatique.** [...] Choisir a la place de l'operateur --
    « il n'y a qu'un profil dans le projet, ce doit etre celui-la » --
    reintroduirait exactement le defaut que `EPIC5-ARB-83` supprime, et le
    reintroduirait sous une forme plus difficile a voir. »

    Trois profils sont **ecrits dans le projet** sans qu'aucun ne soit
    **designe** : `import_designated_profile(record=False)` est litteralement
    ce que le chemin de scan fait. Le registre reste vide, donc la liste aussi.
    Une implementation qui balayerait `versions/calibration/` rendrait trois
    entrees ici -- et c'est le seul test du depot capable de la voir.
    """
    projet = designe._projet(tmp_path, "projet-aux-fichiers-non-designes")
    for rang, (chaine, presse) in enumerate(zip(CHAINES, designe._PRESSES)):
        source, _document = designe._fichier_externe(
            tmp_path / f"externe-{rang}", chaine, presse)
        designation.import_designated_profile(projet, source, record=False)
    # Temoin : les trois fichiers sont bien la, et la liste reste vide malgre
    # eux. Sans ce temoin, le test serait vert sur un projet vide.
    assert len(list((projet / "versions" / "calibration").glob("*.json"))) == 3

    assert designation.designated_profiles(projet) == []


def test_le_DEFAUT_du_projet_n_est_PAS_le_registre(tmp_path) -> None:
    """AC 8.3 : deux cles, deux questions -- et deux reponses independantes.

    `DEFAULT_PROFILE_KEY` et `DESIGNATED_PROFILES_KEY` sont deliberement
    distinctes : « lire le defaut ne demande ni d'ouvrir le fichier de profil,
    ni de parcourir le registre ». Le reciproque doit tenir aussi -- enumerer
    le registre ne doit pas se rabattre sur le defaut --, sans quoi un projet
    dont un seul profil a ete pose par la commande dediee verrait ce profil
    apparaitre dans une liste ou l'operatrice n'a rien designe.
    """
    projet = designe._projet(tmp_path, "projet-au-defaut-seul")
    manifeste = _manifeste(projet)
    manifeste["color"] = {
        designation.DEFAULT_PROFILE_KEY: {
            "chain_id": CHAINE_VISEE, designation.ENTRY_PATH_KEY: "versions/x.json"}
    }
    _ecrire_le_manifeste(projet, manifeste)

    # Le defaut est bien lisible -- sans lui, le test serait vert sur un projet
    # ou il n'y a simplement rien.
    assert designation.default_profile_entry(projet)["chain_id"] == CHAINE_VISEE
    assert designation.designated_profiles(projet) == []


def test_un_registre_MALFORME_est_ECARTE_entree_par_entree(tmp_path) -> None:
    """AC 8.3 : un `project.json` s'edite a la main, et la liste ne casse pas.

    Une chaine nue rendue telle quelle deviendrait un `entree["path"]` en
    `TypeError` chez l'appelant, plusieurs etages plus loin -- hors de toute
    hierarchie nommee et sur un ecran. `_upsert` filtre deja de la meme facon a
    l'ecriture ; le lecteur en est le symetrique.

    La cible reste **la deuxieme des deux entrees valides**, et le bruit est
    place **avant** elle : un filtre qui s'arreterait au premier element
    illisible rendrait une liste vide.
    """
    projet, attendues = _projet_a_trois_profils(tmp_path)
    manifeste = _manifeste(projet)
    registre = manifeste["color"][designation.DESIGNATED_PROFILES_KEY]
    assert len(registre) == 3
    manifeste["color"][designation.DESIGNATED_PROFILES_KEY] = [
        registre[0], "profil-ecrit-a-la-main", registre[1], 42, registre[2]]
    _ecrire_le_manifeste(projet, manifeste)

    liste = designation.designated_profiles(projet)

    assert [entree["chain_id"] for entree in liste] == sorted(CHAINES)
    assert liste[RANG_VISE] == attendues[CHAINE_VISEE]


def test_un_registre_qui_n_est_PAS_une_liste_rend_une_liste_VIDE(tmp_path) -> None:
    """AC 8.3, dernier repli : la cle existe mais ne porte pas une liste."""
    projet = designe._projet(tmp_path, "projet-au-registre-tordu")
    manifeste = _manifeste(projet)
    manifeste["color"] = {designation.DESIGNATED_PROFILES_KEY: {"chain_id": "x"}}
    _ecrire_le_manifeste(projet, manifeste)

    assert designation.designated_profiles(projet) == []


# ---------------------------------------------------------------------------
# La resolution du fichier d'une entree -- par le CHEMIN ECRIT, jamais par le
# `chain_id`
# ---------------------------------------------------------------------------


def test_le_fichier_d_une_entree_se_resout_par_le_CHEMIN_ECRIT(tmp_path) -> None:
    """`EPIC5-ARB-83` : « **jamais** en recomposant
    `versions/calibration/<chain_id>.json` a partir du `chain_id`: recomposer
    ferait de l'identite une cle de resolution ».

    Le piege est nomme dans le module : recomposer marche « tant que les deux
    coincident ». Les trois profils de ce banc portent une **etiquette**, donc
    `write_profile` les nomme par elle et non par leur chaine : le chemin
    recompose n'existe pas, et une resolution fautive rendrait `None` la ou le
    fichier est pourtant present.
    """
    projet, _attendues = _projet_a_trois_profils(tmp_path)
    entree = designation.designated_profiles(projet)[RANG_VISE]

    chemin = designation.designated_profile_path(projet, entree)

    assert chemin is not None and chemin.is_file()
    assert chemin == projet / entree[designation.ENTRY_PATH_KEY]
    # Le chemin recompose depuis l'identite **n'existe pas** : sans cet ecart,
    # une resolution par `chain_id` passerait ce test.
    recompose = projet / "versions" / "calibration" / f"{CHAINE_VISEE}.json"
    assert not recompose.exists()
    assert chemin != recompose
    # Et le document relu est bien celui de la CIBLE, pas d'un voisin : c'est
    # l'assertion de contenu que l'existence d'un fichier ne donne pas.
    assert json.loads(chemin.read_text(encoding="utf-8"))["chain_id"] == \
        CHAINE_VISEE


def test_le_fichier_DISPARU_rend_None_et_ne_fabrique_pas_un_profil(tmp_path):
    """L'entree reste vraie de ce que le projet a utilise ; le fichier, non.

    Meme repli que `default_profile_path`, et c'est le meme corps : « elle ne
    fabrique pas un profil absent. L'appelant avertit, et le lot sort brut. »
    """
    projet, _attendues = _projet_a_trois_profils(tmp_path)
    entree = designation.designated_profiles(projet)[RANG_VISE]
    (projet / entree[designation.ENTRY_PATH_KEY]).unlink()

    assert designation.designated_profile_path(projet, entree) is None
    # L'entree, elle, est intacte : c'est la propriete d'autoportance.
    assert designation.designated_profiles(projet)[RANG_VISE] == entree


@pytest.mark.parametrize("entree", [None, {}, {"path": ""}, {"path": 42}, "x"])
def test_une_entree_sans_chemin_exploitable_rend_None(entree) -> None:
    """Aucune entree malformee ne fait lever la resolution."""
    assert designation.designated_profile_path(Path("/nulle-part"), entree) is None


def test_le_DEFAUT_se_resout_par_LA_MEME_fonction_que_le_registre(tmp_path):
    """Une seule redaction de la resolution, mesuree et non declaree.

    Le defaut du projet est « une entree de la meme forme que celles du
    registre ». Deux resolutions divergeraient, et l'ecart ne se verrait que
    sur un projet ou le defaut et un profil du registre ne pointeraient plus au
    meme endroit -- c'est-a-dire jamais dans un test qui n'exercerait qu'un des
    deux chemins.
    """
    projet, _attendues = _projet_a_trois_profils(tmp_path)
    manifeste = _manifeste(projet)
    entree_visee = next(entree for entree in
                        manifeste["color"][designation.DESIGNATED_PROFILES_KEY]
                        if entree["chain_id"] == CHAINE_VISEE)
    manifeste["color"][designation.DEFAULT_PROFILE_KEY] = dict(entree_visee)
    _ecrire_le_manifeste(projet, manifeste)

    par_le_defaut = designation.default_profile_path(projet)
    par_le_registre = designation.designated_profile_path(
        projet, designation.designated_profiles(projet)[RANG_VISE])

    assert par_le_defaut is not None
    assert par_le_defaut == par_le_registre
