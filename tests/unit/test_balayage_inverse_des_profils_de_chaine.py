"""Le balayage inverse d'`EPIC11-ARB-261` : quels profils portent CETTE chaine.

`io/calibration_profile.profils_de_la_chaine` est la moitie de coeur de
l'arbitrage du 2026-09-07 : « une chaine deja calibree qui gagne un SECOND
profil ». Depuis que le nom d'un profil suit la precedence *saisie -> libelle
du QR -> identite de chaine*, la collision se juge sur le **chemin** vise et
plus sur la **chaine** -- recalibrer sous un libelle different ecrit donc un
second fichier, et l'ancien devient orphelin sans un mot.

Ce banc mesure le balayage, pas la surface : l'avertissement et les deux issues
(`EPIC11-ARB-89`) restent en dette, entree `ARB261-N1` de `deferred-work.md`.

**La fabrique, et pourquoi elle est ce qu'elle est** (`CLAUDE.md`, regle des
fabriques, quatre points) :

* **quatre** fichiers de profil, jamais un seul ;
* ils sont **distinguables** -- deux chaines differentes, quatre noms
  differents, aucun remplissage uniforme ;
* la chaine visee est posee **en TETE, AU MILIEU et EN QUEUE** du listing trie,
  par trois cas separes. Le point 4 de la regle a ete pose sur un mutant qui
  sautait la DERNIERE entree d'un listing : une cible au milieu demasque un
  `find` fautif, elle ne demasque pas un balayage tronque ;
* le **symetrique est obligatoire** : l'autre chaine ne doit JAMAIS ressortir.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE / "src") not in sys.path:
    sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility.io import calibration_profile as cp  # noqa: E402

#: Les deux chaines. Elles different reellement -- deux dpi, deux scanners --,
#: ce qui est le cas ou deux fichiers sont CORRECTS.
CHAINE_VISEE = "300-pdf-aaaaaaaaaaaa"
CHAINE_VOISINE = "600-tiff-bbbbbbbbbbbb"


def _ecrire(projet: Path, radical: str, chain_id: str, *, scan_dir: str = "") -> Path:
    """Poser un fichier de profil MINIMAL sous `versions/calibration/`.

    Le contenu n'a pas a etre un profil valide : le balayage lit `chain_id` et
    `scan_dir`, jamais les coefficients. L'ecrire par `write_profile` ferait
    dependre ce banc d'un ajustement de couleur qu'il ne mesure pas.
    """
    dossier = projet / cp.VERSIONS_DIRNAME / cp.CALIBRATION_DIRNAME
    dossier.mkdir(parents=True, exist_ok=True)
    document: dict = {"schema_version": cp.PROFILE_SCHEMA_VERSION,
                      "chain_id": chain_id}
    if scan_dir:
        document[cp.SCAN_DIR_FIELD] = scan_dir
    chemin = dossier / f"{radical}.json"
    chemin.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return chemin


#: Les trois positions de la cible dans le listing TRIE, et le radical voisin
#: qui l'y place. `'0'` trie avant `'m'`, qui trie avant `'z'`.
POSITIONS = {
    "tete": ("0-vise", ("m-voisin", "y-voisin", "z-voisin")),
    "milieu": ("m-vise", ("0-voisin", "a-voisin", "z-voisin")),
    "queue": ("z-vise", ("0-voisin", "a-voisin", "m-voisin")),
}


@pytest.fixture
def projet(tmp_path: Path) -> Path:
    return tmp_path / "projet"


@pytest.mark.parametrize("position", sorted(POSITIONS))
def test_la_chaine_visee_est_trouvee_a_CHAQUE_position(projet: Path,
                                                       position: str) -> None:
    """Tete, milieu et queue : un balayage tronque d'un bord perd la cible."""
    radical, voisins = POSITIONS[position]
    attendu = _ecrire(projet, radical, CHAINE_VISEE)
    for voisin in voisins:
        _ecrire(projet, voisin, CHAINE_VOISINE)

    trouves = cp.profils_de_la_chaine(projet, CHAINE_VISEE)
    assert trouves == [attendu], trouves
    # Le symetrique : l'autre chaine rend SES trois fichiers, jamais celui-ci.
    voisins_trouves = cp.profils_de_la_chaine(projet, CHAINE_VOISINE)
    assert len(voisins_trouves) == 3, voisins_trouves
    assert attendu not in voisins_trouves


def test_DEUX_profils_de_la_meme_chaine_sortent_tous_les_deux(projet: Path) -> None:
    """Le regime meme d'`EPIC11-ARB-261` : deux libelles pour une seule chaine.

    C'est ce que la machine d'Egan produira a la prochaine recalibration sous un
    libelle different. Le balayage doit rendre les DEUX, sans quoi l'ecran ne
    peut ni avertir ni proposer de remplacer.
    """
    premier = _ecrire(projet, "a-hp-envy-4520", CHAINE_VISEE)
    _ecrire(projet, "b-autre-chose", CHAINE_VOISINE)
    second = _ecrire(projet, "c-hp-envy-relabellise", CHAINE_VISEE)
    assert cp.profils_de_la_chaine(projet, CHAINE_VISEE) == [premier, second]


def test_l_ordre_est_TRIE_et_donc_stable_entre_deux_lectures(projet: Path) -> None:
    """Deux lectures rendent la meme liste dans le meme ordre.

    Un ecran qui annonce « cette chaine porte deja le profil X » ne doit pas
    nommer un profil different a chaque passage : `iterdir` seul ne garantit
    aucun ordre.
    """
    for radical in ("z-troisieme", "a-premier", "m-deuxieme"):
        _ecrire(projet, radical, CHAINE_VISEE)
    lecture = cp.profils_de_la_chaine(projet, CHAINE_VISEE)
    assert [chemin.stem for chemin in lecture] == [
        "a-premier", "m-deuxieme", "z-troisieme"]
    assert cp.profils_de_la_chaine(projet, CHAINE_VISEE) == lecture


def test_un_projet_SANS_dossier_de_calibration_rend_une_liste_vide(
    projet: Path,
) -> None:
    """Un projet non calibre n'est pas une panne, et ne leve rien."""
    projet.mkdir(parents=True)
    assert cp.profils_de_la_chaine(projet, CHAINE_VISEE) == []
    assert cp.dossiers_de_scan_declares(projet) == set()
    assert cp.documents_de_calibration(projet) == []


def test_un_fichier_ILLISIBLE_est_saute_sans_emporter_les_autres(
    projet: Path,
) -> None:
    """On ne peut rien prouver d'un JSON casse, donc on n'en conclut rien.

    La frontiere est **negative de fait** : sans elle, un fichier tronque
    ferait lever le balayage entier, et l'ecran perdrait les profils sains qui
    l'entourent -- c'est-a-dire l'avertissement qu'`EPIC11-ARB-261` existe pour
    produire.
    """
    sain = _ecrire(projet, "a-sain", CHAINE_VISEE)
    dossier = projet / cp.VERSIONS_DIRNAME / cp.CALIBRATION_DIRNAME
    (dossier / "b-tronque.json").write_text("{ ceci n'est pas", encoding="utf-8")
    (dossier / "c-liste.json").write_text("[1, 2, 3]", encoding="utf-8")
    autre_sain = _ecrire(projet, "d-sain", CHAINE_VISEE)
    assert cp.profils_de_la_chaine(projet, CHAINE_VISEE) == [sain, autre_sain]


def test_les_dossiers_de_scan_declares_se_lisent_du_MEME_balayage(
    projet: Path,
) -> None:
    """La moitie `EPIC11-ARB-262`, sur la meme fabrique multi-elements.

    Deux profils declarent deux dossiers DIFFERENTS, un troisieme n'en declare
    aucun : une valeur uniforme ferait passer un balayage qui ne lit que le
    premier.
    """
    _ecrire(projet, "a-un", CHAINE_VISEE, scan_dir="scans/mire-un")
    _ecrire(projet, "m-sans", CHAINE_VOISINE)
    _ecrire(projet, "z-deux", CHAINE_VOISINE, scan_dir="scans/mire-deux")
    assert cp.dossiers_de_scan_declares(projet) == {
        "scans/mire-un", "scans/mire-deux"}
