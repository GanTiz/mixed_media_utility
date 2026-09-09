"""Story 11.4e -- `EPIC11-ARB-233` : le suffixe d'homonymie est un RANG.

Egan, 2026-09-05, par invite. Le suffixe que la levee d'homonymie pose sur le
`rush_id` valait le **dossier immediat** du fichier ; il vaut desormais un
**rang**, calcule par `io.version_ranks` :

```
avant :  prise01   puis  prise01-hd   puis  BLOCAGE au troisieme
apres :  prise01   puis  prise01-2    puis  prise01-3
```

Les deux defauts que l'arbitrage ferme, tous deux **mesures** sur le terrain
avant d'etre tranches (deux copies du rush reel dans `03_tournage_mai/hd/` et
`04_tournage_juin/hd/`) :

1. **le suffixe ne distinguait rien.** Il valait `hd`, le dossier que les deux
   ont en COMMUN ; ce qui les separe est un cran plus haut ;
2. **le troisieme homonyme n'avait plus d'issue qui ecrit.** Le suffixe de
   dossier etant deterministe et deja pris, il ne restait qu'a « renommer le
   fichier source » -- la corvee manuelle qu'`EPIC11-ARB-104` refuse mot pour
   mot.

**Trois axes de mesure, un par etage**, et ils ne se recouvrent pas :

* `D1` -- la **FORME** du fragment (`io.naming`) : fabrique, inverse, bornes,
  et la borne de longueur, qui est le defaut le moins visible des trois ;
* `D2` -- le **RANG** (`extraction`) : la famille lue au manifeste, la ligne
  d'eau **deleguee** a `io.version_ranks`, l'epuisement ;
* `D3` -- le **comportement** de bout en bout (`declaration_de_rush` et la
  CLI) : le deuxieme homonyme, le TROISIEME -- qui ne bloque plus --, la forme
  tapable de ce que le refus cite, et le volet negatif (aucun `rush_id` ne
  porte un nom de dossier).

**Regle des fabriques de `CLAUDE.md`, ses quatre points, et l'axe qui compte
ici est le RANG.** Un banc ou tous les homonymes seraient au meme rang ne
verrait aucun calcul de rang faux. Les familles fabriquees portent donc au
moins deux rangs **distinguables**, la cible est placee ailleurs qu'en
premiere position de `manifest["rushes"]`, et le point 4 (2026-09-03) est tenu
sur **les deux axes a la fois** : une cible a chaque bord de la LISTE (tete et
queue), et une cible a chaque bord du DOMAINE des rangs (2, le premier rang
possible, et 99, le dernier). Le rang 99 n'est pas une coquetterie : c'est le
seul regime ou le refus d'epuisement se ferme, et un balayage tronque de la
famille ne se demasque pas autrement.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import cli, declaration_de_rush, extraction
from mixed_media_utility.io import naming, version_ranks
from mixed_media_utility.io.extraction_manifest import MANIFEST_FILENAME

requires_ffprobe = pytest.mark.skipif(
    shutil.which("ffprobe") is None, reason="ffprobe absent du PATH"
)

#: Le rush reel du banc : 125 frames a 25 im/s, 236 295 octets une fois
#: materialise.
#:
#: **Corrige le 2026-09-05, finding `F14` de la revue 11.4e.** Cette place
#: affirmait « en git ordinaire (236 ko), donc mesurable dans un conteneur neuf
#: sans `git lfs pull` ». Les deux moities sont fausses, et mesurees telles :
#: ce fichier est un objet LFS -- `HEAD` n'en porte qu'un POINTEUR de 131
#: octets --, simplement ORPHELIN de ses attributs depuis que la revision du
#: 2026-09-03 a scope le LFS par chemin, si bien que `git check-attr filter` y
#: rend `unspecified`. Dans un worktree frais il vaut donc 131 octets et ce
#: banc rend **13 rouges sur 90** : une conclusion tiree d'un pointeur lu comme
#: un fichier. Le regime reel n'est plus affirme ici, il est MESURE --
#: :data:`REGIME_GIT_DES_RUSHES` et les deux tests qui la lisent.
#:
#: La reparation ne coute aucune bande passante quand les objets sont deja dans
#: `.git/lfs/objects`, ce qui est le cas d'un clone fait par un conteneur qui
#: porte `filter.lfs.smudge = --skip` : `git lfs checkout`, jamais
#: `git lfs pull`. Et le verdict se lit sur la TAILLE du fichier apres coup,
#: jamais sur la sortie de la commande, qui ne dit rien quand elle ne fait
#: rien.
RUSH_REEL = REPO_ROOT / "tests/fixtures/rushes/rush_test_16x9_1920x1080_25fps.mp4"


#: La taille sous laquelle un fichier de `tests/fixtures/rushes/` ne peut etre
#: qu'un pointeur LFS. Un pointeur pese 131 octets, le plus leger des cinq
#: medias en pese 7 029 : le seuil separe les deux d'un facteur cinquante, il
#: n'a pas a etre fin.
TAILLE_PLANCHER_D_UN_MEDIA = 500


def exiger_le_media(chemin) -> None:
    """Faire ROUGIR -- jamais sauter -- quand un rush n'est qu'un pointeur LFS.

    **`EPIC11-ARB-241`, tranche par Egan le 2026-09-05.** L'ecart que cet
    arbitrage ferme etait MESURE : dans un conteneur ou les rushes ne sont pas
    materialises, ce banc-ci rendait **13 rouges sur 90** pendant que le banc
    `E2-1f` **SAUTAIT** -- deux bancs, deux regimes, pour la meme cause, et
    rien sur place ne l'expliquait.

    Le cout de la decision est connu et accepte : un conteneur neuf est ROUGE
    tant que `git lfs checkout` n'a pas tourne, et une session pressee peut le
    lire comme une regression -- c'est pour elle que le message nomme la
    commande. Ce qui l'emporte : la reparation coute **zero octet de bande
    passante** quand les objets sont deja dans `.git/lfs/objects` (mesure du
    2026-09-03, deux conteneurs, 38 objets et 350 Mo sans un octet reseau). Un
    defaut reparable a cout nul doit se signaler fort ; un saut le range en
    SILENCE, et ce silence a deja coute ici une course parallele de 56 minutes
    jetee, plus une dette qui n'a jamais ete une dette de code.

    Le verdict se lit sur la TAILLE, jamais sur la sortie de `git lfs`, qui ne
    dit rien quand elle ne fait rien.
    """
    taille = Path(chemin).stat().st_size
    assert taille >= TAILLE_PLANCHER_D_UN_MEDIA, (
        f"{Path(chemin).name} pese {taille} octets : c'est un POINTEUR LFS, "
        "pas un media. `git lfs checkout` le repare a cout reseau nul (les "
        "objets sont deja dans .git/lfs/objects). EPIC11-ARB-241 : un "
        "pointeur ROUGIT, il ne saute jamais."
    )


class JournalMuet:
    def info(self, *_a, **_k) -> None: ...
    def warning(self, *_a, **_k) -> None: ...
    def error(self, *_a, **_k) -> None: ...
    def debug(self, *_a, **_k) -> None: ...


# ---------------------------------------------------------------------------
# fabriques
# ---------------------------------------------------------------------------

#: Deux entrees ETRANGERES a la famille de `prise01`, distinguables entre
#: elles. Elles ne sont pas du decor : un balayage qui compterait tout ce qu'il
#: croise rendrait un rang faux, et un balayage qui ne reconnaitrait pas la
#: famille rendrait toujours 2.
ETRANGERS = (
    {"rush_id": "avant", "source_name": "avant.mov", "source_parent": "Z-CAM",
     "source_path": "/rushes/avril/Z-CAM/avant.mov",
     "fps_source": 24.0, "fps_source_exact": "24/1",
     "source_frame_count": 480, "source_frame_count_is_exact": True},
    {"rush_id": "apres", "source_name": "apres.mov", "source_parent": "B-CAM",
     "source_path": "/rushes/juin/B-CAM/apres.mov",
     "fps_source": 30.0, "fps_source_exact": "30/1",
     "source_frame_count": 900, "source_frame_count_is_exact": True},
)


def entree_de_la_famille(rang: int, tige: str = "prise01") -> dict:
    """Une entree homonyme de `tige`, au rang donne, DISTINGUABLE des autres.

    **Distinguable sur ce qui n'est PAS un critere d'identite**, et la nuance
    a couté deux rouges avant d'etre posee : les quatre criteres
    d'`EPIC11-ARB-230` -- nom, duree, cadence, timecode initial -- doivent
    **coincider** avec le rush reel, sans quoi `EPIC11-ARB-9` separe tout seul
    et `--force-distinct` n'a plus rien a faire. Une famille d'homonymes est
    par construction uniforme sur ces quatre axes ; ce qui la distingue est
    ailleurs, et c'est ce qui varie ici : le rang porte dans le `rush_id`, le
    dossier parent et le chemin complet.

    La duree est donc celle de `RUSH_REEL` -- 125 frames a 25 im/s -- et non
    une valeur qui varierait avec le rang.
    """
    rush_id = tige if rang == 1 else naming.format_rang_de_desambiguisation(tige, rang)
    return {
        "rush_id": rush_id,
        "source_name": f"{tige}.mov",
        "source_parent": f"cam{rang:02d}",
        "source_path": f"/rushes/tournage-{rang:02d}/hd/{tige}.mov",
        "fps_source": 25.0,
        "fps_source_exact": "25/1",
        "source_frame_count": 125,
        "source_frame_count_is_exact": True,
    }


def rushes_de(rangs, position: str = "milieu", tige: str = "prise01") -> list[dict]:
    """La liste `rushes[]` : la famille aux `rangs` donnes, placee dans la liste.

    `position` place la famille en `tete`, au `milieu` ou en `queue` de la
    liste que le code parcourt -- les deux bords compris, point 4 de la regle
    des fabriques.
    """
    famille = [entree_de_la_famille(rang, tige) for rang in rangs]
    if position == "tete":
        return [*famille, *(dict(e) for e in ETRANGERS)]
    if position == "queue":
        return [*(dict(e) for e in ETRANGERS), *famille]
    premier, second = (dict(e) for e in ETRANGERS)
    return [premier, *famille, second]


def manifeste(dossier: Path, rushes: list[dict]) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / MANIFEST_FILENAME
    chemin.write_text(
        json.dumps(
            {
                "schema_version": "2.1",
                "project_id": "projet-arb233",
                "created": "2026-09-05T00:00:00Z",
                "rushes": rushes,
                "lots": [],
                "artifacts": {},
                "color": {},
                "video": {},
                "reconstruction": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return chemin


def copie_du_rush(dossier: Path, nom: str) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / nom
    shutil.copyfile(RUSH_REEL, cible)
    return cible


def rushes_du_manifeste(chemin: Path) -> list[dict]:
    return json.loads(chemin.read_text(encoding="utf-8"))["rushes"]


# ===========================================================================
# D1 -- la FORME du fragment (`io.naming`)
# ===========================================================================


@pytest.mark.parametrize("rang, attendu", [
    (2, "prise01-2"),      # le premier rang possible -- bord bas du domaine
    (7, "prise01-7"),
    (99, "prise01-99"),    # le dernier -- bord haut du domaine
])
def test_D1_la_fabrique_rend_le_fragment_de_RANG(rang, attendu):
    """`EPIC11-ARB-233` : `-<rang>`, et pas le `_v<rang>` des versions.

    La forme n'est pas interchangeable avec celle des lots : deux homonymes ne
    sont pas deux etats d'un meme objet, ce sont deux objets. `prise01_v2`
    dirait « deuxieme version de prise01 », ce qui est faux.
    """
    assert naming.format_rang_de_desambiguisation("prise01", rang) == attendu
    assert not attendu.endswith(naming.format_version_suffix(rang))


@pytest.mark.parametrize("refuse", [1, 0, -3, 100, 999, True, "2", 2.0, None])
def test_D1_la_fabrique_REFUSE_ce_qui_n_est_pas_un_rang(refuse):
    """Les bornes sont celles des rangs, et le rang 1 n'en est pas un.

    Le premier rush d'une famille ne porte **aucun** fragment : son absence dit
    son rang. Ecrire `prise01-1` poserait un second nom pour le meme objet.
    """
    with pytest.raises(naming.NamingError):
        naming.format_rang_de_desambiguisation("prise01", refuse)


@pytest.mark.parametrize("rang", [2, 3, 50, 98, 99])
def test_D1_l_inverse_relit_EXACTEMENT_ce_que_la_fabrique_a_ecrit(rang):
    """Aller-retour, bords du domaine compris.

    La fabrique et son inverse vivent cote a cote (meme geste que
    `format_version_suffix` / `rang_du_fragment_de_version`) precisement pour
    que cet aller-retour soit mesurable a un seul endroit.
    """
    nom = naming.format_rang_de_desambiguisation("prise01", rang)
    assert naming.rang_de_desambiguisation(nom, "prise01") == rang


def test_D1_la_TIGE_seule_est_le_rang_d_ORIGINE():
    """Le rang 1 s'ecrit par omission, comme partout dans ce depot."""
    assert naming.rang_de_desambiguisation("prise01", "prise01") == 1
    assert version_ranks.RANG_ORIGINE == 1


@pytest.mark.parametrize("etranger", [
    "prise01-hd",       # le suffixe d'AVANT `EPIC11-ARB-233` : un nom, aucun rang
    "prise01-04_tournage_juin",
    "prise01-0",
    "prise01-1",        # jamais ecrit : l'origine ne porte pas de fragment
    "prise01-02",       # zero de tete
    "prise01-100",      # hors bornes
    "prise01-2x",
    "prise01x-2",       # une AUTRE tige
    "autre-2",
    "prise0-2",
    "-2",
])
def test_D1_l_inverse_rend_None_sur_ce_qui_n_appartient_PAS_a_la_famille(etranger):
    """Volet negatif, et il porte le cas de compatibilite qui compte.

    Un `prise01-hd` ecrit avant cet arbitrage occupe un **nom** et **aucun
    rang** : la famille l'ignore, le prochain forcage rend `prise01-2`, qui est
    libre. C'est ce qui fait qu'un manifeste ancien continue de fonctionner
    sans migration.
    """
    assert naming.rang_de_desambiguisation(etranger, "prise01") is None


def test_D1_la_TIGE_est_raccourcie_AVANT_de_recevoir_le_fragment():
    """La borne de longueur, et c'est le defaut le moins visible des trois.

    `normalize_identifier` raccourcit la chaine **entiere**, fragment compris,
    en recopiant un prefixe verbatim suivi d'un condensat. Sur un `rush_id`
    deja a la borne, le fragment DISPARAIT donc du nom ecrit -- et deux
    forcages successifs, ne reconnaissant plus la famille, recalculent le meme
    rang et rendent le **meme identifiant** pour deux rushes distincts. C'est
    le defaut n.2 de l'arbitrage, reapparu au bord.

    La borne se **lit dans le code**, jamais dans un document : trois fois dans
    ce depot elle a ete citee de memoire et fausse.
    """
    tige = "p" * naming.CANONICAL_ID_MAX_LENGTH
    assert len(tige) == naming.CANONICAL_ID_MAX_LENGTH

    produits = {
        rang: naming.format_rang_de_desambiguisation(tige, rang)
        for rang in (2, 3, 50, 99)
    }
    # Tous conformes a la borne, tous DISTINCTS, tous relisibles.
    for rang, nom in produits.items():
        assert len(nom) <= naming.CANONICAL_ID_MAX_LENGTH, nom
        assert naming.rang_de_desambiguisation(nom, tige) == rang
    assert len(set(produits.values())) == len(produits)


def test_D1_volet_symetrique_la_redaction_NAIVE_perdait_bien_le_fragment():
    """Sans lui, le test precedent serait vert sur un defaut qui n'existe pas.

    On rejoue ici la composition d'avant -- `normalize_identifier` sur la
    chaine entiere -- et on montre qu'elle **perd** le fragment : le nom rendu
    ne se relit pas comme un membre de la famille, et deux rangs differents
    rendent deux noms qu'aucun inverse ne sait distinguer d'une origine.
    """
    tige = "p" * naming.CANONICAL_ID_MAX_LENGTH
    naif = naming.normalize_identifier(f"{tige}-2")
    assert len(naif) == naming.CANONICAL_ID_MAX_LENGTH
    assert not naif.endswith("-2")
    assert naming.rang_de_desambiguisation(naif, tige) is None


def test_D1_la_largeur_du_fragment_SUIT_la_borne_des_rangs():
    """Frontiere negative : aucune largeur ecrite en dur.

    Si `VERSION_RANK_MAX` passait un jour a trois chiffres, la tige devrait se
    raccourcir d'autant. Une constante recopiee ici, ou la-bas, divergerait au
    premier ajustement -- c'est `EPIC5-ARB-78`.

    **La premiere redaction de ce test etait TAUTOLOGIQUE, et un mutant l'a
    dit** (`N10`, campagne du 2026-09-05). Elle comparait la constante a
    `1 + len(str(VERSION_RANK_MAX))`, c'est-a-dire au calcul meme qu'elle est
    censee mesurer : la remplacer par le litteral `3` laissait les deux cotes
    egaux, donc le banc VERT. Aucune assertion de valeur ne peut fermer ce
    defaut -- les deux redactions valent 3 aujourd'hui, et ne divergent que le
    jour ou la borne bouge. Ce qui se mesure, c'est donc la **dependance
    elle-meme**, lue a la source.
    """
    ligne = next(
        ligne for ligne in Path(naming.__file__).read_text(
            encoding="utf-8").splitlines()
        if ligne.startswith("LARGEUR_MAX_FRAGMENT_DESAMBIGUISATION")
    )
    # La largeur du fragment est « un separateur plus le nombre de chiffres du
    # plus grand rang » : le `1` est le tiret, et il est bien un litteral. Ce
    # qui ne doit PAS en etre un est le nombre de chiffres.
    assert "len(str(VERSION_RANK_MAX))" in ligne, ligne

    assert naming.LARGEUR_MAX_FRAGMENT_DESAMBIGUISATION == 1 + len(
        str(naming.VERSION_RANK_MAX))
    tige = "p" * naming.CANONICAL_ID_MAX_LENGTH
    assert len(naming.tige_de_desambiguisation(tige)) == (
        naming.CANONICAL_ID_MAX_LENGTH
        - naming.LARGEUR_MAX_FRAGMENT_DESAMBIGUISATION
    )


#: Des `rush_id` LONGS qui portent un tiret **a chaque place ou la coupe peut
#: tomber**, et non un remplissage uniforme.
#:
#: **Pourquoi ils ne sont pas fabriques avec un seul caractere repete**, et
#: c'est le point 1 de la regle des fabriques paye comptant : les trois tests
#: de borne ci-dessus emploient `"p" * CANONICAL_ID_MAX_LENGTH`, donc une
#: chaine SANS AUCUN TIRET -- et le defaut que la couche 2 de la revue a
#: trouve le 2026-09-05 n'existe QUE quand un tiret tombe a l'indice de coupe.
#: Un remplissage uniforme rendait ce defaut structurellement invisible, ce qui
#: est exactement ce que « des valeurs differentes, jamais un remplissage
#: uniforme » interdit.
#:
#: L'indice de coupe se DERIVE des constantes, il ne se recopie pas : c'est la
#: largeur du prefixe que `derive_short_id` garde verbatim.
_LARGEUR_DE_TIGE = (
    naming.CANONICAL_ID_MAX_LENGTH - naming.LARGEUR_MAX_FRAGMENT_DESAMBIGUISATION
)
#: `derive_short_id` garde `value[:prefix_length]` **verbatim** : le dernier
#: caractere conserve est donc a l'indice `prefix_length - 1`, et c'est LUI
#: qu'un tiret rend fautif. L'ecart d'un cran est le genre de detail qu'un test
#: recopie faux : il se derive.
_LARGEUR_DU_PREFIXE = _LARGEUR_DE_TIGE - naming.SHORT_DERIVE_HASH_LENGTH - 1
_INDICE_DE_COUPE = _LARGEUR_DU_PREFIXE - 1


def _rush_id_long_avec_tiret_en(indice: int) -> str:
    """Un `rush_id` conforme, plus long que la TIGE, tiret pose a `indice`.

    Fabrique **distinguable** : chaque position produit une chaine differente,
    et le tiret y est le seul caractere non alphabetique -- donc ce qui varie
    d'un cas a l'autre est exactement l'axe mesure.

    **Sa longueur est celle de la borne canonique**, pas davantage : en
    production `disambiguated_rush_id` ne recoit que des identifiants deja
    normalises, donc deja sous la borne. Un `rush_id` fabrique plus long
    mesurerait un regime que le produit ne connait pas -- et il ne serait meme
    pas conforme, ce que la garde ci-dessous verifie plutot que de le supposer.
    """
    lettres = list("a" * naming.CANONICAL_ID_MAX_LENGTH)
    lettres[indice] = "-"
    identifiant = "".join(lettres)
    # Conforme (donc representatif) ET plus long que la tige (donc coupe).
    assert naming.normalize_identifier(identifiant) == identifiant, identifiant
    assert len(identifiant) > _LARGEUR_DE_TIGE, identifiant
    return identifiant


#: Les trois poses : **avant** l'indice de coupe, **dessus** -- le seul qui
#: mord --, et **apres**. La pose « dessus » n'est pas la seule jouee parce
#: qu'un test qui ne verrait que le cas fautif ne dirait pas que les autres
#: sont sains ; et les deux bords encadrent l'indice plutot que de le supposer.
_POSES_DE_TIRET = {
    "avant_la_coupe": _INDICE_DE_COUPE - 1,
    "sur_la_coupe": _INDICE_DE_COUPE,
    "apres_la_coupe": _INDICE_DE_COUPE + 1,
}


@pytest.mark.parametrize("pose", sorted(_POSES_DE_TIRET))
def test_D1_la_tige_est_CONFORME_ou_que_tombe_le_tiret(pose):
    """La tige ne porte JAMAIS deux tirets de suite, ou qu'on coupe.

    Le mutant vise : retirer le recollement de `tige_de_desambiguisation`. Il
    ne mord que sur la pose `sur_la_coupe` -- d'ou les trois poses, qui disent
    aussi que les deux voisines etaient saines avant comme apres.
    """
    tige = naming.tige_de_desambiguisation(_rush_id_long_avec_tiret_en(
        _POSES_DE_TIRET[pose]))
    assert "--" not in tige, (pose, tige)
    assert naming.normalize_identifier(tige) == tige, (pose, tige)


def test_D1_les_POSES_encadrent_reellement_l_indice_de_coupe():
    """Garde d'inventaire : sans elle, les trois poses pourraient rater la coupe.

    Un `parametrize` se garde par son CONTENU -- retirer la pose fautive
    jouerait deux cas sains sans faire rougir personne, et derivant l'indice
    des constantes, un ajustement de borne pourrait le deplacer hors des trois.
    """
    poses = set(_POSES_DE_TIRET.values())
    assert _INDICE_DE_COUPE in poses, "aucune pose SUR l'indice de coupe"
    assert min(poses) < _INDICE_DE_COUPE < max(poses), poses
    # Et la coupe tombe bien a l'interieur du `rush_id` fabrique, sans quoi
    # les trois poses mesureraient une chaine que `derive_short_id` ne coupe
    # meme pas.
    assert 0 < _INDICE_DE_COUPE < naming.CANONICAL_ID_MAX_LENGTH


def test_D2_TROIS_homonymes_de_suite_recoivent_TROIS_noms_DISTINCTS():
    """Le defaut de la couche 2, de bout en bout : l'ecrasement silencieux.

    **Ce que ce test ferme, et il vaut d'etre garde ecrit.** Sur un `rush_id`
    dont un tiret tombe a l'indice de coupe, la tige portait un DOUBLE tiret ;
    `disambiguated_rush_id` repassant son resultat par `normalize_identifier`,
    le double tiret etait **recolle** et le nom cessait d'etre `<tige>-<rang>`.
    `rang_de_desambiguisation` rendait alors `None`, aucun rang n'etait compte
    employe, et le troisieme homonyme recevait le rang 2 -- donc le nom du
    second. `build_rush_declaration_manifest` fusionnant en place par
    `rush_id`, la seconde entree DISPARAISSAIT du manifeste sans un mot.

    **Il passe par `disambiguated_rush_id`**, pas par les fonctions de mise en
    forme prises isolement : c'est precisement l'etape de normalisation finale
    qui rouvrait le defaut, et aucune mesure de borne ne l'atteignait.
    """
    rush_id = _rush_id_long_avec_tiret_en(_INDICE_DE_COUPE)
    rushes = [{"rush_id": rush_id}]
    for _ in range(3):
        rushes.append({"rush_id": extraction.disambiguated_rush_id(
            rush_id, rushes)})

    noms = [rush["rush_id"] for rush in rushes]
    assert len(set(noms)) == len(noms), noms
    # Et les rangs se relisent : 2, 3, 4 -- sans quoi le prochain forcage
    # recommencerait a 2.
    tige = naming.tige_de_desambiguisation(rush_id)
    assert [naming.rang_de_desambiguisation(nom, rush_id)
            for nom in noms[1:]] == [2, 3, 4], (noms, tige)


def test_D2_volet_symetrique_une_tige_SANS_tiret_a_la_coupe_marchait_deja():
    """Sans lui, le test ci-dessus se lirait comme si RIEN ne marchait avant.

    Le defaut etait etroit -- il fallait un tiret exactement a l'indice de
    coupe. Le dire par une mesure evite qu'une reprise future elargisse le
    correctif a un cas qui n'a jamais ete casse.
    """
    rush_id = _rush_id_long_avec_tiret_en(_INDICE_DE_COUPE - 1)
    rushes = [{"rush_id": rush_id}]
    for _ in range(3):
        rushes.append({"rush_id": extraction.disambiguated_rush_id(
            rush_id, rushes)})
    noms = [rush["rush_id"] for rush in rushes]
    assert len(set(noms)) == len(noms), noms


def test_D1_une_tige_COURTE_n_est_pas_touchee():
    """Volet symetrique : le raccourci ne mord que la ou il doit.

    Sans lui, une tige systematiquement condensee passerait la mesure de
    longueur ci-dessus tout en rendant illisible le cas courant.
    """
    assert naming.tige_de_desambiguisation("prise01") == "prise01"


# ---------------------------------------------------------------------------
# F15 -- le rang 1 A LA BORNE DE LONGUEUR (revue 11.4e, `blind` + `edge`)
# ---------------------------------------------------------------------------
#
# Deux mutants survivaient sur `rang_de_desambiguisation` : la reconnaissance
# du rang d'origine y est une DISJONCTION -- `texte == tige or texte == racine`
# -- et le banc ne jouait le rang 1 que sur des tiges COURTES, ou les deux
# termes sont egaux. Chacun couvrait donc l'autre : retirer n'importe lequel
# des deux laissait 279 tests au vert (mesure du 2026-09-05, sur ce banc plus
# `test_identite_rush` et `test_declaration_de_rush`).
#
# **La consequence produit est nulle, et elle est MESUREE plus bas** plutot
# qu'affirmee : `version_ranks.ligne_d_eau` plancher a `RANG_ORIGINE`, donc un
# rang 1 non reconnu ne change aucun nom ecrit. Ce qui n'est pas tenu, c'est le
# CONTRAT d'une fonction exportee, dont la docstring promet « ``1`` quand `nom`
# EST la tige » -- et c'est une porte que le prochain appelant franchira.

#: Deux tiges longues **distinguables**, et il en faut deux : un banc a une
#: seule tige ne dirait pas si la reconnaissance depend de la FORME de la tige
#: ou de sa seule longueur. La seconde porte un tiret exactement a l'indice de
#: coupe -- le regime que `tige_de_desambiguisation` recolle --, donc les deux
#: exercent des racines de formes differentes.
_TIGES_LONGUES = {
    "sans_tiret": "a" * naming.CANONICAL_ID_MAX_LENGTH,
    "tiret_sur_la_coupe": _rush_id_long_avec_tiret_en(_INDICE_DE_COUPE),
}


def _racine(tige: str) -> str:
    return naming.tige_de_desambiguisation(tige)


def test_F15_les_TIGES_LONGUES_sont_reellement_coupees():
    """Garde d'inventaire : sans elle, les tests ci-dessous seraient vacants.

    Une tige que `tige_de_desambiguisation` ne coupe pas rend `racine == tige`,
    et les deux termes de la disjonction redeviennent le meme -- exactement le
    regime aveugle que `F15` ferme. La garde le mesure au lieu de le supposer,
    et elle rougira le jour ou la borne bougera assez pour que ces deux tiges
    passent dessous.
    """
    assert _TIGES_LONGUES, "aucune tige longue : la fabrique est vide"
    for nom, tige in _TIGES_LONGUES.items():
        assert len(tige) > _LARGEUR_DE_TIGE, (nom, tige)
        assert _racine(tige) != tige, (nom, tige)
    # Et elles sont bien DISTINGUABLES -- deux racines differentes, pas deux
    # ecritures de la meme.
    assert len({_racine(t) for t in _TIGES_LONGUES.values()}) == len(_TIGES_LONGUES)


@pytest.mark.parametrize("ecriture", ["le_rush_id_entier", "la_racine_raccourcie"])
@pytest.mark.parametrize("nom_de_tige", sorted(_TIGES_LONGUES))
def test_F15_le_rang_1_se_relit_sur_une_tige_LONGUE(nom_de_tige, ecriture):
    """Le rang d'origine, aux DEUX ecritures qu'une tige longue lui donne.

    C'est ce que la disjonction du produit dit, et chacun de ses deux termes
    est ici le SEUL a repondre :

    * `le_rush_id_entier` -- ce que le produit ecrit reellement pour le premier
      rush d'une famille : son `rush_id` complet, non raccourci, l'omission du
      fragment valant le rang 1 ;
    * `la_racine_raccourcie` -- la tige que tous ses homonymes partagent. Aucun
      chemin du produit ne l'ecrit aujourd'hui, et c'est pourquoi ce terme-la
      survivait : la docstring de `rang_de_desambiguisation` le promet quand
      meme, et un appelant qui relirait la famille par sa racine l'obtiendrait.
    """
    tige = _TIGES_LONGUES[nom_de_tige]
    texte = tige if ecriture == "le_rush_id_entier" else _racine(tige)
    assert naming.rang_de_desambiguisation(texte, tige) == 1, (texte, tige)


@pytest.mark.parametrize("nom_de_tige", sorted(_TIGES_LONGUES))
def test_F15_volet_NEGATIF_une_tige_longue_ETRANGERE_ne_rend_pas_1(nom_de_tige):
    """Sans lui, une fonction qui rendrait 1 sur tout passerait le test ci-dessus.

    Les deux etrangers sont pris au plus pres : la racine d'une AUTRE tige
    longue -- meme longueur, meme forme, autre famille --, et la tige entiere
    amputee d'un caractere. Un `startswith` a la place de l'egalite les
    rendrait tous deux membres.
    """
    tige = _TIGES_LONGUES[nom_de_tige]
    autres = [t for n, t in _TIGES_LONGUES.items() if n != nom_de_tige]
    assert autres, "il faut au moins deux tiges pour que ce volet mesure"
    for etrangere in autres:
        assert naming.rang_de_desambiguisation(_racine(etrangere), tige) is None
        assert naming.rang_de_desambiguisation(etrangere, tige) is None
    assert naming.rang_de_desambiguisation(tige[:-1], tige) is None
    assert naming.rang_de_desambiguisation(_racine(tige)[:-1], tige) is None


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
@pytest.mark.parametrize("nom_de_tige", sorted(_TIGES_LONGUES))
def test_F15_la_famille_d_une_tige_LONGUE_compte_son_rang_1(nom_de_tige, position):
    """Le rang 1 compte comme EMPLOYE, y compris a la borne de longueur.

    La famille porte les rangs 1, 2 et 99 -- les deux bords du domaine plus
    l'origine --, et elle est placee aux deux bords de la liste ainsi qu'au
    milieu : un balayage tronque ne se demasque pas autrement, et un rang 1
    perdu ne se verrait pas sur une famille qui n'en porte pas.
    """
    tige = _TIGES_LONGUES[nom_de_tige]
    rushes = rushes_de((1, 2, 99), position=position, tige=tige)
    employes = extraction.rangs_de_desambiguisation_employes(rushes, tige)
    assert sorted(employes) == [1, 2, 99], (position, employes)


def test_F15_la_CONSEQUENCE_produit_du_rang_1_perdu_est_NULLE_et_mesuree():
    """Pourquoi ces deux mutants etaient une tolerance et non un defaut vivant.

    Le rang 1 ne change aucun nom ecrit : `ligne_d_eau` plancher a
    `RANG_ORIGINE`, donc une famille dont le rang 1 serait ignore rend malgre
    tout le rang 2 au premier forcage. La tolerance est ainsi **mesuree** au
    lieu d'etre affirmee -- et si le plancher tombait un jour, ce test rougirait
    en meme temps que le contrat cesserait d'etre inoffensif.
    """
    assert version_ranks.ligne_d_eau(None, ()) == version_ranks.RANG_ORIGINE
    assert version_ranks.prochain_rang(version_ranks.ligne_d_eau(None, ())) == 2
    tige = _TIGES_LONGUES["sans_tiret"]
    # Une famille reduite a son seul rang 1, et une famille VIDE : le meme
    # rang suivant, ce qui est exactement ce qui rendait les mutants muets.
    assert extraction.disambiguated_rush_id(tige, [{"rush_id": tige}]) == \
        extraction.disambiguated_rush_id(tige, [])
    assert naming.rang_de_desambiguisation(
        extraction.disambiguated_rush_id(tige, []), tige) == 2


# ===========================================================================
# D2 -- le RANG lu de la famille (`extraction`)
# ===========================================================================


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
@pytest.mark.parametrize("rangs, attendus", [
    ((1,), (1,)),
    ((1, 2), (1, 2)),
    ((1, 2, 3), (1, 2, 3)),
    ((1, 3), (1, 3)),            # un trou : le 2 a servi puis a ete retire
    ((2,), (2,)),                # l'origine retiree, le rang reste consomme
    ((1, 2, 99), (1, 2, 99)),    # bord haut du domaine
])
def test_D2_les_rangs_EMPLOYES_se_lisent_de_la_famille(rangs, attendus, position):
    """Deux axes de bord a la fois : bord de la LISTE et bord du DOMAINE.

    Les etrangers de la fabrique doivent rester dehors dans les six cas : un
    balayage qui compterait tout rendrait un rang faux, et un balayage qui ne
    reconnaitrait pas la famille rendrait toujours le meme.
    """
    rushes = rushes_de(rangs, position)
    lus = extraction.rangs_de_desambiguisation_employes(rushes, "prise01")
    assert sorted(lus) == sorted(attendus)


def test_D2_les_entrees_ABIMEES_sont_ignorees_sans_lever():
    """Un manifeste abime ne fait pas tomber la levee d'homonymie.

    Une entree qui n'est pas un objet, un `rush_id` absent ou non textuel : la
    famille les saute. Rendre une trace Python ici transformerait un manifeste
    imparfait en panne d'outil.
    """
    rushes = [
        "pas un objet",
        {"pas_de_rush_id": True},
        {"rush_id": None},
        {"rush_id": 42},
        *rushes_de((1, 2), "queue"),
    ]
    assert sorted(
        extraction.rangs_de_desambiguisation_employes(rushes, "prise01")
    ) == [1, 2]


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
@pytest.mark.parametrize("rangs, attendu", [
    ((1,), "prise01-2"),
    ((1, 2), "prise01-3"),
    ((1, 2, 3), "prise01-4"),
    # Le TROU reste un trou : un rang se CONSOMME (`EPIC11-ARB-92`, point 1).
    ((1, 3), "prise01-4"),
    ((1, 2, 40), "prise01-41"),
    ((2,), "prise01-3"),
])
def test_D2_l_identifiant_leve_est_le_rang_SUIVANT(rangs, attendu, position):
    """Le coeur de l'arbitrage : `prise01`, puis `prise01-2`, puis `prise01-3`.

    Et la regle des rangs joue entiere -- retirer le 2 d'une famille `1, 2, 3`
    ne le rend pas, le suivant est le 4. Ce n'est pas une regle de ce module :
    c'est celle d'`io.version_ranks`, la meme pour les cinq objets versionnables
    du depot (`EPIC11-ARB-108`).
    """
    rushes = rushes_de(rangs, position)
    assert extraction.disambiguated_rush_id("prise01", rushes) == attendu


def test_D2_l_identifiant_leve_n_est_JAMAIS_deja_pris():
    """L'invariant qui remplace la verification d'apres coup.

    Le code d'avant calculait un nom puis verifiait qu'il n'etait pas pris,
    pour retomber sur un refus sans issue quand il l'etait. Le rang etant
    choisi au-dessus de la ligne d'eau, il ne peut pas l'etre : c'est la
    fermeture **par construction** du defaut n.2, et elle se mesure sur une
    famille a trous, avec des etrangers et un `prise01-hd` d'avant l'arbitrage.
    """
    rushes = [
        *rushes_de((1, 3, 7), "milieu"),
        {"rush_id": "prise01-hd", "source_name": "prise01.mov",
         "source_parent": "hd", "source_path": "/vieux/hd/prise01.mov"},
    ]
    pris = {r["rush_id"] for r in rushes if isinstance(r, dict)}
    for _ in range(20):
        leve = extraction.disambiguated_rush_id("prise01", rushes)
        assert leve not in pris, (leve, sorted(pris))
        pris.add(leve)
        rushes.append({"rush_id": leve, "source_name": "prise01.mov"})


def test_D2_la_regle_des_rangs_est_APPELEE_jamais_recopiee():
    """`EPIC11-ARB-108` et la regle `versionnage-mecanisme-unique`.

    Mesure par **substitution** plutot que par egalite : on remplace
    `prochain_rang` par un temoin et l'identifiant rendu doit suivre le temoin.
    Un module qui recopierait le calcul rendrait sa propre valeur et rougirait
    ici -- ce qu'aucune egalite avec une valeur attendue ne verrait.
    """
    vus: list[int] = []

    def temoin(ligne: int) -> int:
        vus.append(ligne)
        return 42

    original = version_ranks.prochain_rang
    version_ranks.prochain_rang = temoin
    try:
        leve = extraction.disambiguated_rush_id("prise01", rushes_de((1, 2, 3)))
    finally:
        version_ranks.prochain_rang = original

    assert leve == "prise01-42"
    assert vus == [3], "la ligne d'eau de la famille n'a pas ete transmise"


def test_D2_volet_symetrique_la_LIGNE_D_EAU_vient_du_module_partage():
    """Meme geste sur l'autre moitie de la regle.

    Sans ce volet, le precedent serait vert sur un module qui recopierait la
    ligne d'eau et n'appellerait que le `+1`.
    """
    vus: list[tuple] = []

    def temoin(declaree, rangs):
        vus.append((declaree, tuple(rangs)))
        return 11

    original = version_ranks.ligne_d_eau
    version_ranks.ligne_d_eau = temoin
    try:
        leve = extraction.disambiguated_rush_id("prise01", rushes_de((1, 2)))
    finally:
        version_ranks.ligne_d_eau = original

    assert leve == "prise01-12"
    assert len(vus) == 1
    assert sorted(vus[0][1]) == [1, 2]


def test_D2_les_98_rangs_CONSOMMES_refusent_avec_DEUX_issues_qui_ecrivent():
    """Le bord haut, et c'est le seul refus qui reste sur ce chemin.

    `EPIC11-ARB-89` : jamais un blocage sec. Les deux issues **ecrivent** l'une
    et l'autre -- retirer un homonyme rend son rang, renommer la source sort de
    la famille --, la ou la redaction d'avant n'offrait qu'une corvee manuelle.

    Le texte est celui de `version_ranks.refus_de_rangs_epuises` : une seule
    redaction pour tous les objets, jamais une seconde ici.
    """
    rushes = rushes_de(tuple(range(1, naming.VERSION_RANK_MAX + 1)), "queue")

    with pytest.raises(extraction.RangsDeDesambiguisationEpuises) as capture:
        extraction.disambiguated_rush_id("prise01", rushes)

    message = str(capture.value)
    assert "CONSOMMES" in message
    assert "prise01" in message

    # **Le refus ANNONCE ses issues, il ne se contente pas de les contenir**
    # (mutant `E10`, campagne du 2026-09-05). La premiere redaction cherchait
    # les gestes -- `mmu project remove`, `renommer` -- sans jamais mesurer que
    # le message les presente COMME des issues : remplacer « Deux issues: » par
    # « Aucune issue: » laissait les trois gestes en place et le banc vert,
    # c'est-a-dire un blocage sec qui recite ses issues en disant qu'il n'y en
    # a pas. `EPIC11-ARB-89` porte sur l'annonce autant que sur le contenu.
    annonce = re.search(r"\b(Deux|Trois|Quatre) issues: (.+)", message)
    assert annonce, message
    gestes = [g.strip() for g in annonce.group(2).split(";") if g.strip()]
    assert len(gestes) >= 2, gestes

    assert any("mmu project remove" in geste for geste in gestes), gestes
    assert any("--rush" in geste for geste in gestes), gestes
    assert any("renommer" in geste.lower() for geste in gestes), gestes
    # Le refus est **nomme**, pas une `ExtractionInputError` nue : l'appelant
    # qui redige un refus a issues doit le reconnaitre sans lire le texte.
    assert isinstance(capture.value, extraction.ExtractionInputError)


def test_D2_volet_symetrique_a_98_rangs_il_reste_UNE_place():
    """Sans lui, le refus ci-dessus serait vert sur une borne posee trop tot.

    Une garde a `>=` plutot qu'a `>` refuserait la derniere place et laisserait
    ce banc parfaitement vert.
    """
    rushes = rushes_de(tuple(range(1, naming.VERSION_RANK_MAX)), "tete")
    assert extraction.disambiguated_rush_id("prise01", rushes) == (
        f"prise01-{naming.VERSION_RANK_MAX}")


def test_D2_le_module_ne_REDIGE_pas_le_refus_d_epuisement():
    """Frontiere negative : le texte vit dans `version_ranks`, pas ici.

    Volet symetrique porte par la mesure de contenu ci-dessus : le message
    existe bel et bien et dit ce qu'il faut.
    """
    source = Path(extraction.__file__).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    appels = {
        noeud.func.attr
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
    }
    assert "refus_de_rangs_epuises" in appels
    assert "sont tous CONSOMMES" not in source


def test_D2_aucun_appelant_ne_passe_le_DOSSIER_a_la_levee_d_homonymie():
    """Frontiere negative : le dossier a quitte la LEVEE, pas seulement un site.

    `disambiguated_rush_id` a deux appelants -- `run_extraction` et
    `declaration_de_rush._trancher_l_identite`. Le premier n'est PAS concerne
    par `EPIC11-ARB-83` : son regime degrade garde le dossier comme **critere**
    de dernier recours, faute de pouvoir mesurer avant la transition d'etat du
    lot. Mais garder le dossier comme critere et le garder comme **nom** sont
    deux choses, et seule la premiere survit : laisser ce chemin nommer par le
    dossier pendant que la declaration nomme par le rang donnerait DEUX
    identifiants au meme rush selon la porte d'entree.

    La mesure est structurelle plutot que comportementale, et c'est delibere :
    exercer `run_extraction` coute ffmpeg et une extraction complete, la ou
    l'ecart cherche -- « ce site-la passe encore le dossier » -- se lit sur
    l'appel. Un `grep` du nom ne suffirait pas : c'est le SECOND argument qui
    est mesure, pas la presence du mot.
    """
    racine = Path(extraction.__file__).resolve().parents[1]
    seconds_arguments: list[tuple[str, str]] = []
    for fichier in sorted(racine.rglob("*.py")):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            cible = noeud.func
            nom = cible.id if isinstance(cible, ast.Name) else getattr(
                cible, "attr", None)
            if nom != "disambiguated_rush_id" or len(noeud.args) < 2:
                continue
            seconds_arguments.append(
                (fichier.name, ast.unparse(noeud.args[1])))

    # Volet symetrique : sans lui la boucle serait verte par vacuite.
    assert len(seconds_arguments) == 2, seconds_arguments
    for fichier, argument in seconds_arguments:
        assert "source_parent" not in argument, (fichier, argument)
        assert "rushes" in argument, (fichier, argument)


# ===========================================================================
# D3 -- le comportement de bout en bout
# ===========================================================================


@requires_ffprobe
@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_D3_le_DEUXIEME_homonyme_recoit_le_rang_2(tmp_path, position):
    """La premiere marche du terrain d'Egan : `prise01`, puis `prise01-2`."""
    projet = tmp_path / "projet"
    chemin = manifeste(projet, rushes_de((1,), position))
    avant = rushes_du_manifeste(chemin)
    video = copie_du_rush(tmp_path / "04_tournage_juin" / "hd", "prise01.mp4")

    issue = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet(),
        force_distinct=True,
    )

    assert issue.rush_id == "prise01-2"
    assert issue.rush_id_derive == "prise01"
    apres = rushes_du_manifeste(chemin)
    assert apres[: len(avant)] == avant, "une entree existante a ete touchee"
    assert apres[-1]["rush_id"] == "prise01-2"


@requires_ffprobe
@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_D3_le_TROISIEME_homonyme_ne_BLOQUE_plus_et_recoit_le_rang_3(
    tmp_path, position
):
    """**Le defaut n.2 de l'arbitrage, et sa fermeture a sa propre frontiere.**

    Terrain du 2026-09-05, verbatim de ce que l'outil rendait au troisieme
    `prise01.mov` pose dans un troisieme `hd/` :

        le suffixe de dossier (prise01-hd) est deja pris, donc
        --force-distinct rendrait ce meme nom: renommer le fichier source pour
        lui donner un identifiant propre

    Des trois issues affichees, l'une etait fausse (relinker : ce n'est pas le
    meme rush), l'autre ne faisait rien, et la troisieme etait une corvee
    manuelle **hors de l'outil**. C'est litteralement ce qu'`EPIC11-ARB-104`
    refuse. Ce test mesure qu'il n'y a plus de refus du tout : l'ecriture
    aboutit.
    """
    projet = tmp_path / "projet"
    chemin = manifeste(projet, rushes_de((1, 2), position))
    avant = rushes_du_manifeste(chemin)
    video = copie_du_rush(tmp_path / "05_tournage_juillet" / "hd", "prise01.mp4")

    issue = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet(),
        force_distinct=True,
    )

    assert issue.rush_id == "prise01-3"
    apres = rushes_du_manifeste(chemin)
    assert len(apres) == len(avant) + 1
    assert apres[: len(avant)] == avant
    assert apres[-1]["source_path"] == str(video.resolve())


@requires_ffprobe
def test_D3_quatre_homonymes_de_SUITE_montent_les_rangs_sans_jamais_bloquer(
    tmp_path,
):
    """Le terrain d'Egan joue en entier, du premier au quatrieme.

    Trois copies du meme rush dans trois dossiers `hd/` differents, plus une
    quatrieme : c'est le montage exact de la mesure du 2026-09-05, celui qui
    bloquait a la troisieme.
    """
    projet = tmp_path / "projet"
    chemin = manifeste(projet, [])
    dossiers = ["03_tournage_mai", "04_tournage_juin", "05_tournage_juillet",
                "06_tournage_aout"]
    obtenus = [
        declaration_de_rush.declarer_un_rush(
            project_dir=projet,
            video_path=copie_du_rush(tmp_path / d / "hd", "prise01.mp4"),
            logger=JournalMuet(),
            force_distinct=True,
        ).rush_id
        for d in dossiers
    ]
    assert obtenus == ["prise01", "prise01-2", "prise01-3", "prise01-4"]
    assert [r["rush_id"] for r in rushes_du_manifeste(chemin)] == obtenus


@requires_ffprobe
def test_D3_volet_NEGATIF_aucun_rush_id_ne_porte_un_nom_de_DOSSIER(tmp_path):
    """Le volet negatif de l'arbitrage : le dossier a quitte le nom.

    Les dossiers de la fabrique sont choisis pour etre reconnaissables --
    `hd`, qui est ce que l'ancien suffixe rendait, et `04_tournage_juin`, qui
    est ce que l'option ecartee aurait rendu. Aucun fragment de chemin ne doit
    figurer dans un `rush_id` produit.

    Un `grep` de `-hd` seul ne suffirait pas : il serait vert sur une
    implementation qui suffixerait par le grand-parent.
    """
    projet = tmp_path / "projet"
    chemin = manifeste(projet, [])
    segments = ["hd", "04_tournage_juin", "05_tournage_juillet", "rushes"]
    for dossier in ("04_tournage_juin", "05_tournage_juillet"):
        declaration_de_rush.declarer_un_rush(
            project_dir=projet,
            video_path=copie_du_rush(tmp_path / "rushes" / dossier / "hd",
                                     "prise01.mp4"),
            logger=JournalMuet(), force_distinct=True,
        )

    produits = [r["rush_id"] for r in rushes_du_manifeste(chemin)]
    assert produits == ["prise01", "prise01-2"]
    for rush_id in produits:
        for segment in segments:
            assert segment not in rush_id, (rush_id, segment)
    # Volet symetrique : le dossier n'a pas DISPARU du manifeste pour autant --
    # il nomme toujours la provenance a l'ecran (`EPIC11-ARB-230`), et c'est
    # son nom dans le `rush_id` qui a ete retire, pas le champ.
    assert {r["source_parent"] for r in rushes_du_manifeste(chemin)} == {"hd"}


@requires_ffprobe
def test_D3_la_commande_citee_au_TROISIEME_homonyme_est_TAPABLE_et_ABOUTIT(
    tmp_path, capsys
):
    """Ce que le refus cite, sur la forme tapable, **au rang qui bloquait**.

    La cloture d'`EPIC11-ARB-224` pose qu'une commande nommee dans un refus
    doit etre tapable, doit parser, et doit **changer quelque chose**. Le
    troisieme volet est exactement celui qui tombait : au troisieme homonyme,
    le refus cessait de citer la commande et renvoyait a un renommage manuel.

    La ligne est relue dans la sortie d'erreur et **rejouee telle quelle** --
    une ligne refabriquee par le banc mesurerait le banc.
    """
    projet = tmp_path / "projet"
    chemin = manifeste(projet, rushes_de((1, 2), "milieu"))
    avant = rushes_du_manifeste(chemin)
    video = copie_du_rush(tmp_path / "05_tournage_juillet" / "hd", "prise01.mp4")

    assert cli.main(["project", "add-rush", "--project", str(projet),
                     "--video", str(video)]) == declaration_de_rush.CODE_ERREUR
    erreur = capsys.readouterr().err

    citee = re.search(r"`mmu (project add-rush [^`]*--force-distinct)`", erreur)
    assert citee, erreur
    argv = citee.group(1).split()
    assert cli.main(argv) == declaration_de_rush.CODE_SUCCES

    apres = rushes_du_manifeste(chemin)
    assert apres[: len(avant)] == avant
    assert apres[-1]["rush_id"] == "prise01-3"
    # Et la liste STRUCTUREE dit la meme chose que la prose : les deux sont
    # deux rendus du meme refus, et un seul savait s'adapter avant le
    # 2026-09-05.
    citantes = [ligne for ligne in erreur.splitlines()
                if ligne.strip().startswith("Issue:")
                and "--force-distinct`" in ligne]
    assert len(citantes) == 1, erreur


@requires_ffprobe
def test_D3_a_99_homonymes_le_refus_porte_les_DEUX_issues_qui_ecrivent(tmp_path):
    """Le bord haut, de bout en bout, et la liste structuree suit.

    C'est le seul regime ou `--force-distinct` ne peut plus rien rendre. La
    prose **et** la liste imprimee cessent alors de le citer -- une issue qui
    parse, qu'on peut taper et qui ne change rien est le « blocage sec
    deguise » qu'`EPIC11-ARB-89` interdit.

    **L'ORDRE se mesure en EGALITE EXACTE, jamais en appartenance** (finding
    `F7` de la revue 11.4e, ferme ici). Ce test n'assertait que par `any(...)`,
    `not [...]` et un cardinal : une permutation des rangs 0 et 1 du tuple que
    `_refus_de_rush_deja_declare` compose laissait **318 tests verts**, alors
    que le mutant symetrique sur le rang 2 mourait -- donc c'etait bien l'ordre
    qui echappait, pas le contenu. Or l'ordre PORTE la recommandation : le
    rang 0 est ce que l'operateur doit faire d'abord, et la permutation
    retrograde « relinker » de la premiere issue a la seconde. C'est mot pour
    mot ce que la docstring de `suites_du_rush_deja_declare` interdit deja pour
    les memes trois issues cote ecran.

    **Le texte du milieu n'est pas recopie ici, il est obtenu par l'AUTRE
    chemin** -- celui qui leve l'epuisement. Une constante comparee a sa propre
    recopie est la tautologie de la section 6.2 de la politique de revue, et ce
    banc en a deja paye une (`N10`).
    """
    projet = tmp_path / "projet"
    chemin = manifeste(
        projet, rushes_de(tuple(range(1, naming.VERSION_RANK_MAX + 1)), "queue"))
    avant = rushes_du_manifeste(chemin)
    video = copie_du_rush(tmp_path / "trop_tard" / "hd", "prise01.mp4")

    with pytest.raises(declaration_de_rush.RefusDeDeclaration) as capture:
        declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet(),
            force_distinct=True,
        )
    refus = capture.value

    assert refus.motif == declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE
    assert "CONSOMMES" in str(refus)
    # La citation TAPABLE disparait des deux rendus, pas d'un seul.
    assert "`mmu project add-rush" not in str(refus)
    assert not [issue for issue in refus.issues
                if "`mmu project add-rush" in issue]

    # L'issue du MILIEU, obtenue par le chemin qui la produit et non recopiee :
    # `disambiguated_rush_id` leve l'epuisement sur la meme famille saturee, et
    # c'est son texte que le coeur pose en `issue_de_remplacement`.
    with pytest.raises(extraction.RangsDeDesambiguisationEpuises) as epuise:
        extraction.disambiguated_rush_id("prise01", rushes_du_manifeste(chemin))
    nominales = declaration_de_rush.ISSUES_PAR_MOTIF[
        declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE]
    attendues = (nominales[0], str(epuise.value), nominales[2])

    # La morsure par transposition ne vaut que si les trois issues sont
    # DISTINGUABLES : sur un triplet uniforme, une egalite exacte survivrait a
    # n'importe quelle permutation (point 1 de la regle des fabriques, applique
    # a la mesure elle-meme). On le mesure plutot que de le supposer.
    assert len(set(attendues)) == 3
    assert tuple(refus.issues) == attendues, (
        "l'ordre des trois issues porte la recommandation : le rang 0 est ce "
        "que l'operateur doit faire d'abord")
    # Et les issues qui restent ECRIVENT : retirer un homonyme, renommer.
    assert "mmu project remove" in attendues[1]
    # Rien n'a ete ecrit.
    assert rushes_du_manifeste(chemin) == avant


@requires_ffprobe
def test_D3_volet_symetrique_a_98_homonymes_la_citation_est_LA(tmp_path):
    """Sans lui, le test precedent serait vert sur un refus qui ne cite jamais.

    Un rang de moins, et la commande redevient tapable -- avec la place qui
    reste, la 99e.

    **Le volet d'ORDRE le suit** (`F7`) : hors du regime d'epuisement, la liste
    est celle de la table publiee, dans SON ordre. Sans cette egalite exacte,
    le test precedent mesurerait un ordre que rien ne compare a sa source.
    """
    projet = tmp_path / "projet"
    chemin = manifeste(
        projet, rushes_de(tuple(range(1, naming.VERSION_RANK_MAX)), "tete"))
    video = copie_du_rush(tmp_path / "juste_a_temps" / "hd", "prise01.mp4")

    with pytest.raises(declaration_de_rush.RefusDeDeclaration) as capture:
        declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet(),
        )
    assert "`mmu project add-rush" in str(capture.value)
    assert tuple(capture.value.issues) == declaration_de_rush.ISSUES_PAR_MOTIF[
        declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE]
    assert "--force-distinct`" in capture.value.issues[1]

    issue = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet(),
        force_distinct=True,
    )
    assert issue.rush_id == f"prise01-{naming.VERSION_RANK_MAX}"
    assert rushes_du_manifeste(chemin)[-1]["rush_id"] == issue.rush_id


@requires_ffprobe
def test_D3_le_MEME_fichier_reste_refuse_quel_que_soit_son_identifiant(tmp_path):
    """Le trou que la fermeture du defaut n.2 aurait ouvert sans cette garde.

    La verification « l'identifiant leve est-il deja pris ? » arretait, par
    accident, une redeclaration du **meme fichier** deja enregistre sous un
    identifiant LEVE (`prise01-2`, jamais `prise01`) : la garde bon marche ne
    cherchait le chemin que sous le `rush_id` derive. Le rang etant toujours
    libre, cette verification a disparu -- et sans une garde posee sur le
    CHEMIN, deux entrees auraient pointe le meme chemin absolu, c'est-a-dire un
    doublon et non une distinction.
    """
    projet = tmp_path / "projet"
    chemin = manifeste(projet, rushes_de((1,), "milieu"))
    video = copie_du_rush(tmp_path / "04_tournage_juin" / "hd", "prise01.mp4")

    premier = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet(),
        force_distinct=True,
    )
    assert premier.rush_id == "prise01-2"
    avant = rushes_du_manifeste(chemin)

    with pytest.raises(declaration_de_rush.RefusDeDeclaration) as capture:
        declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet(),
            force_distinct=True,
        )
    assert capture.value.rush_id == "prise01-2"
    assert rushes_du_manifeste(chemin) == avant


def _detour_vers(detour: str, video: Path, tmp_path: Path, monkeypatch) -> Path:
    """Le MEME fichier, redesigne par un chemin qui ne s'ecrit pas pareil.

    Les trois detours sont les trois formes qu'un operateur produit sans le
    vouloir -- un lien pose par un chutier, un chemin tape depuis le dossier
    courant, un chemin recolle a la main avec un `..`. Aucun ne change le
    fichier vise : `Path.resolve()` les ramene tous les trois au meme chemin
    absolu, et c'est exactement ce que le mutant de `F8` retire.
    """
    if detour == "lien_symbolique":
        chutier = tmp_path / "chutier"
        chutier.mkdir()
        lien = chutier / "prise01.mp4"
        lien.symlink_to(video)
        return lien
    if detour == "chemin_relatif":
        # Relatif au dossier courant, et non plus absolu : `str()` n'a alors
        # plus rien de commun avec le `source_path` ecrit au manifeste.
        monkeypatch.chdir(tmp_path)
        return Path(video.relative_to(tmp_path))
    # Absolu, mais non canonique : le `..` se collapse a la resolution seule.
    return video.parent / ".." / video.parent.name / video.name


@requires_ffprobe
@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
@pytest.mark.parametrize(
    "detour", ["lien_symbolique", "chemin_relatif", "segment_parent"])
def test_D3_le_MEME_fichier_DESIGNE_AUTREMENT_reste_refuse(
    tmp_path, monkeypatch, position, detour
):
    """Le `.resolve()` de la garde de chemin, mesure (finding `F8`).

    `_entree_au_chemin` compare le chemin **resolu des deux cotes**, et sa
    docstring en fait un invariant : « un chemin source, une entree ... et
    `--force-distinct` ne la rachete pas ». Rien ne le tenait -- retirer le
    `.resolve()` de `declaration_de_rush.py:656` laissait **318 tests verts**,
    parce que tous les bancs redesignaient le fichier par le chemin absolu
    canonique, celui pour lequel `str(p)` et `str(p.resolve())` coincident.

    Regime exhibe par la sonde de revue, et c'est celui-ci : arbre sain, les
    trois detours rendent `REFUS rush_deja_declare` ; arbre mute, deux entrees
    de plus sont ecrites et le manifeste final porte **trois entrees sur le
    meme chemin absolu**. C'est le doublon qu'`EPIC11-ARB-232` interdit -- le
    drapeau affirme que c'est un AUTRE rush, il ne peut pas separer un fichier
    de lui-meme.

    **Les trois positions ne sont pas du decor** : la garde BALAIE `rushes[]`
    en entier, donc un balayage tronque en tete ou en queue ne se demasque
    qu'avec une cible a chaque bord (point 4 de la regle des fabriques).
    """
    projet = tmp_path / "projet"
    chemin = manifeste(projet, rushes_de((1,), position))
    video = copie_du_rush(tmp_path / "04_tournage_juin" / "hd", "prise01.mp4")

    premier = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet(),
        force_distinct=True,
    )
    assert premier.rush_id == "prise01-2"
    avant = rushes_du_manifeste(chemin)

    autre_ecriture = _detour_vers(detour, video, tmp_path, monkeypatch)
    # Le detour est bien un AUTRE texte, sans quoi le test serait inerte : il
    # mesurerait la garde deja tenue par le banc du chemin canonique.
    assert str(autre_ecriture) != str(video)
    assert autre_ecriture.resolve() == video.resolve()

    with pytest.raises(declaration_de_rush.RefusDeDeclaration) as capture:
        declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=autre_ecriture,
            logger=JournalMuet(), force_distinct=True,
        )
    assert capture.value.motif == declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE
    assert capture.value.rush_id == "prise01-2"
    apres = rushes_du_manifeste(chemin)
    assert apres == avant, "une entree a ete ecrite sur un chemin deja declare"
    # L'invariant lui-meme, et non seulement son symptome : un chemin absolu,
    # une entree. C'est ce que le manifeste mute violait a trois exemplaires.
    chemins = [r["source_path"] for r in apres if r.get("source_path")]
    assert len(chemins) == len(set(chemins))


@requires_ffprobe
def test_D3_volet_symetrique_un_AUTRE_fichier_du_meme_nom_passe(tmp_path):
    """Sans lui, la garde precedente serait verte sur un refus de TOUT forcage.

    Deux fichiers distincts portant le meme nom : c'est le cas que
    `--force-distinct` existe pour servir, et il doit continuer de passer.
    """
    projet = tmp_path / "projet"
    chemin = manifeste(projet, rushes_de((1,), "queue"))
    for dossier in ("04_tournage_juin", "05_tournage_juillet"):
        declaration_de_rush.declarer_un_rush(
            project_dir=projet,
            video_path=copie_du_rush(tmp_path / dossier / "hd", "prise01.mp4"),
            logger=JournalMuet(), force_distinct=True,
        )
    assert [r["rush_id"] for r in rushes_du_manifeste(chemin)][-2:] == [
        "prise01-2", "prise01-3"]


# ===========================================================================
# F14 -- ce que git porte VRAIMENT pour les rushes de synthese
# ===========================================================================
#
# Finding `F14` de la revue 11.4e : deux bancs de ce depot ont tire une
# conclusion d'un POINTEUR lu comme un fichier, et l'ont figee en docstring --
# « des tetes de fichier de 131 octets, qui ne passent pas `ffprobe` » ici,
# « en git ordinaire (236 ko), donc mesurable dans un conteneur neuf » la. Les
# deux etaient fausses, et rien ne pouvait les faire rougir : une affirmation
# de prose n'a pas de mutant.
#
# Ce que cette section oppose, c'est la MESURE a la place de l'affirmation. Le
# regime de stockage de chaque rush du dossier est fige dans un inventaire, et
# relu de `HEAD` a chaque course : le jour ou l'un d'eux change de cote --
# migre sous `filter=lfs`, ou en sort --, un banc qui suppose l'autre cote
# rougit ici, avant d'echouer ailleurs sur un message de decodage
# incomprehensible. Ecrite le jour ou la docstring fautive l'a ete, cette
# frontiere l'aurait faite rougir sur-le-champ : `RUSH_REEL` n'a jamais ete en
# git ordinaire.
#
# Ce qu'elle ne mesure PAS, dit plutot que tu : elle ne relit aucune prose. Une
# docstring peut redire demain ce qui est faux ; ce que la frontiere garantit,
# c'est que le FAIT sur lequel elle porte est ecrit quelque part et compare a
# git, plutot que suppose de memoire.

#: Le regime de stockage de chaque rush de `tests/fixtures/rushes/`, mesure le
#: 2026-09-05, REVISE le 2026-09-06, et relu de `HEAD` a chaque course.
#:
#: `True` = `HEAD` porte un POINTEUR LFS (131 ou 133 octets) et non le media :
#: le fichier de l'arbre de travail depend alors de l'etat LFS du conteneur.
#: `False` = `HEAD` porte le media lui-meme, en git ordinaire : il est la, sans
#: reparation, dans n'importe quel clone.
#:
#: **Revise par `EPIC11-ARB-247` (2026-09-06).** Les quatre rushes de synthese
#: etaient des objets LFS ORPHELINS de leurs attributs -- en LFS dans
#: l'historique, plus rattrapes par `.gitattributes` depuis que la revision du
#: 2026-09-03 a scope le LFS par chemin. Ils sont NORMALISES : ~200 Ko piece en
#: git ordinaire, ce que leur taille justifie et ce que `.gitattributes` disait
#: deja en toutes lettres (« ce qui est leger reste en git ordinaire »).
#:
#: Six entrees, dont **cinq d'un cote et une de l'autre** : une fabrique qui
#: n'aurait produit qu'un seul regime rendrait invisible toute erreur
#: d'appariement, et c'est precisement l'erreur que `F14` a payee. La cible
#: minoritaire est en QUEUE ici et un balayage qui la sauterait ne verrait plus
#: qu'un remplissage uniforme. C'est desormais le rush REEL du sous-dossier
#: `reels/` qui la porte -- le seul rush encore en LFS, et il y est par REGLE
#: (`.gitattributes`) plutot que par heritage, ce qui est exactement la
#: difference que cette normalisation ferme.
REGIME_GIT_DES_RUSHES: dict[str, bool] = {
    "rush_test_16x9_1920x1080_25fps.mp4": False,
    "rush_test_235_1920x817_25fps.mp4": False,
    "rush_test_4x3_1080x1436_25fps.mp4": False,
    "rush_test_9x16_1080x1920_25fps.mp4": False,
    "rush_test_16x9_1920x1080_25fps_50img.mp4": False,
    "reels/rush_bitch-4_chendj-mat.mp4": True,
}

#: L'entete d'un pointeur LFS, tel que `git lfs` l'ecrit. Un pointeur pese 131
#: octets et commence par cette ligne ; un media, jamais.
ENTETE_DE_POINTEUR_LFS = b"version https://git-lfs.github.com/spec/v1"

DOSSIER_DES_RUSHES = REPO_ROOT / "tests" / "fixtures" / "rushes"


def _blob_de_HEAD(chemin_relatif: str) -> bytes | None:
    """Le contenu que `HEAD` porte pour ce chemin, ou `None` si git est muet.

    Le saut est **structurel**, jamais un drapeau qu'on oublie de rallumer :
    hors d'un depot git -- archive deroulee, conteneur sans `.git` --, il n'y a
    rien a comparer, et inventer un verdict serait pire que de ne pas en
    rendre.
    """
    try:
        rendu = subprocess.run(
            ["git", "cat-file", "-p", f"HEAD:{chemin_relatif}"],
            cwd=REPO_ROOT, capture_output=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        return None
    return rendu.stdout if rendu.returncode == 0 else None


@pytest.mark.parametrize("nom", sorted(REGIME_GIT_DES_RUSHES))
def test_F14_le_REGIME_git_de_chaque_rush_est_MESURE_et_non_suppose(nom):
    """`HEAD` porte-t-il le media, ou seulement son pointeur ?

    C'est la question que les deux docstrings fautives ont repondue de memoire.
    Elle se lit dans git, et la reponse est ici confrontee a l'inventaire.

    L'inventaire n'est pas du decor : c'est lui qui dit quels rushes un banc
    peut employer sans garde de pointeur -- les cinq de `tests/fixtures/rushes/`
    depuis `EPIC11-ARB-247` -- et lequel oblige encore a en porter une, ou a
    sauter. Un rush qui changerait de cote sans que personne le voie ferait
    echouer un banc plus loin, sur un decodage, ce que `CLAUDE.md` chiffre a
    « une course parallele de 56 minutes jetee ».

    **Le sens de la mesure a change avec la normalisation, pas sa nature.**
    Avant le 2026-09-06 elle attrapait un rush materialise qu'une docstring
    croyait ordinaire ; elle attrape desormais l'inverse -- un rush leger qui
    RETOMBERAIT en LFS, par un motif d'arbre trop large dans `.gitattributes`
    par exemple. C'est le meme appariement, lu dans les deux sens.
    """
    blob = _blob_de_HEAD(f"tests/fixtures/rushes/{nom}")
    if blob is None:
        pytest.skip("git ne rend pas le contenu de HEAD (pas de depot ici)")
    est_un_pointeur = blob.startswith(ENTETE_DE_POINTEUR_LFS)
    assert est_un_pointeur == REGIME_GIT_DES_RUSHES[nom], (
        f"{nom}: HEAD porte "
        f"{'un pointeur LFS' if est_un_pointeur else 'le media'}, "
        f"l'inventaire annonce le contraire -- une docstring qui suppose "
        f"l'ancien regime est a relire")
    if est_un_pointeur:
        # 131 octets, c'est CE contenu-la, et rien d'autre du dossier.
        assert len(blob) < 500
    else:
        assert len(blob) > 5_000


def test_F14_le_rush_en_git_ORDINAIRE_est_la_sans_AUCUNE_reparation():
    """Le volet symetrique, sans lequel l'inventaire ne conclurait rien.

    Un regime lu dans `HEAD` ne dit sa consequence que confronte a l'arbre de
    travail : c'est parce que `..._50img.mp4` est en git ordinaire qu'il est
    materialise partout, et c'est ce que le banc `E2-1f` invoque pour le
    choisir. Sans cette moitie, l'inventaire mesurerait une propriete de git
    sans jamais dire ce qu'elle vaut pour un banc.
    """
    ordinaires = [n for n, pointeur in REGIME_GIT_DES_RUSHES.items()
                  if not pointeur]
    assert ordinaires, "l'inventaire ne porte plus aucun rush en git ordinaire"
    for nom in ordinaires:
        chemin = DOSSIER_DES_RUSHES / nom
        assert chemin.is_file(), nom
        assert chemin.stat().st_size > 5_000, (
            f"{nom} est annonce en git ordinaire et pese "
            f"{chemin.stat().st_size} octets : ce n'est pas un media")
        assert not chemin.read_bytes().startswith(ENTETE_DE_POINTEUR_LFS), nom


#: Le cardinal que `ffprobe` doit rendre sur chaque rush, une fois materialise.
#: Lu ici plutot qu'ecrit en litteral dans le test : deux rushes de cardinaux
#: DIFFERENTS, c'est le point 1 de la regle des fabriques -- un attendu unique
#: rendrait invisible un balayage qui rendrait toujours le meme fichier.
CARDINAL_ATTENDU: dict[str, str] = {
    "rush_test_16x9_1920x1080_25fps.mp4": "25/1,125",
    "rush_test_235_1920x817_25fps.mp4": "25/1,125",
    "rush_test_4x3_1080x1436_25fps.mp4": "25/1,125",
    "rush_test_9x16_1080x1920_25fps.mp4": "25/1,125",
    "rush_test_16x9_1920x1080_25fps_50img.mp4": "25/1,50",
    "reels/rush_bitch-4_chendj-mat.mp4": "25/1,106",
}


@requires_ffprobe
@pytest.mark.parametrize("nom", sorted(REGIME_GIT_DES_RUSHES))
def test_F14_les_rushes_LFS_se_QUALIFIENT_des_qu_ils_sont_materialises(nom):
    """La taille se mesure AVANT de conclure, et jamais l'inverse.

    Le defaut de `F14` en une ligne : un banc a lu 131 octets et en a conclu
    une propriete du RUSH (« il ne passe pas `ffprobe` »), alors que 131 octets
    n'est pas une taille de rush -- c'est une taille de pointeur. Ce test fait
    le geste dans le bon ordre : il sonde d'abord, puis il conclut.

    * pointeur -> le fichier n'est pas mesurable, on le DIT et on ROUGIT, avec
      le geste de reparation nomme (`git lfs checkout`, cout reseau nul quand
      les objets sont deja dans `.git/lfs/objects`). **Ce volet SAUTAIT
      jusqu'au 2026-09-05** ; `EPIC11-ARB-241` l'a converti, parce qu'un saut
      range en silence un defaut reparable a cout nul ;
    * media -> alors `ffprobe` le qualifie, 125 frames a 25/1, et c'est cela
      qui contredit l'affirmation figee.
    """
    chemin = DOSSIER_DES_RUSHES / nom
    assert chemin.is_file(), nom
    # `EPIC11-ARB-241` s'applique ICI AUSSI, y compris au rush de `reels/` que
    # `.lfsconfig` exclut du telechargement : c'est deja ce que fait
    # `test_ecrans_declaration_de_rush` de ce meme fichier, et deux bancs qui
    # traiteraient le meme pointeur de deux facons sont exactement l'ecart que
    # cet arbitrage a ferme. Le message nomme la commande ; le cout du tirage
    # (64 Mo) est celui d'un banc qui veut ce media-la, pas un motif de sauter.
    exiger_le_media(chemin)

    assert chemin.stat().st_size > 5_000, (
        f"{nom} pese {chemin.stat().st_size} octets : ni pointeur ni media")
    sonde = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames,r_frame_rate",
         "-of", "csv=p=0", str(chemin)],
        capture_output=True, text=True, timeout=120,
    )
    assert sonde.returncode == 0, (nom, sonde.stderr)
    assert sonde.stdout.strip() == CARDINAL_ATTENDU[nom], (nom, sonde.stdout)


# ===========================================================================
# D4 -- `EPIC11-ARB-238` : le rang d'homonyme SE REND, et c'est une position
# ===========================================================================
#
# **Ce que cette section fige, et pourquoi elle existe** (finding `F19` de la
# revue 11.4e). `EPIC11-ARB-238` (Egan, 2026-09-05, par invite) tranche que le
# rang d'un rush homonyme **se rend** quand on retire le dernier de la famille
# -- une tolerance assumee, contre le point 3 d'`EPIC11-ARB-92` (« un rang se
# consomme et ne se rend qu'en queue, SUR DEMANDE ») et contre l'unicite de
# mecanisme d'`EPIC11-ARB-108`. L'arbitrage se dit « mesure des deux cotes » :
# c'etait vrai d'un seul. Le SCAN, qui fait l'inverse, a son banc nomme
# (`test_scan_detect_nouvelle_version::
# test_le_rang_de_la_QUEUE_retiree_ne_se_rend_PAS_par_defaut`) ; le rush, dont
# le rang se rend, n'etait fige par rien.
#
# La consequence : poser une ligne d'eau persistee cote rush -- un lot de coeur
# sans migration, explicitement chiffre puis REFUSE par l'arbitrage --
# renverserait la position datee **sans faire rougir personne**. Un
# comportement confirme cesse d'etre un oubli et devient une position ; une
# position qui n'est mesuree nulle part redevient un oubli au premier
# refactoring.


@requires_ffprobe
def test_D4_ARB238_le_rang_du_DERNIER_homonyme_retire_SE_REND(tmp_path):
    """La mesure de l'arbitrage, rejouee : le rang 3 revient a un AUTRE rush.

    C'est le scenario en cinq etapes de
    `decisions-2026-09-05-epic11-arb-237-238-critere-absent-et-rang-rendu.md`,
    joue sur le vrai coeur et le vrai `ffprobe` :

    ```
    1. mai      prise01.mp4                    -> prise01
    2. juin     prise01.mp4 --force-distinct   -> prise01-2
    3. juillet  prise01.mp4 --force-distinct   -> prise01-3
    4. remove --rush prise01-3
    5. aout     prise01.mp4 --force-distinct   -> prise01-3   <- rang RENDU
    ```

    Le fichier d'aout n'a **rien** a voir avec celui de juillet -- il vient
    d'un autre dossier de tournage, et le test le verifie sur `source_path`
    plutot que de le supposer. C'est tout le cout de la tolerance : une
    planche imprimee, un QR scanne, un dossier de frames sauvegarde continuent
    de nommer `prise01-3` alors que `prise01-3` designe desormais autre chose.

    **Ce test rougira si la ligne d'eau est persistee un jour**, ce qui est
    exactement ce qu'on veut : la position est datee, elle se defend, et sa
    revision doit etre un geste conscient plutot qu'un effet de bord.
    """
    projet = tmp_path / "projet"
    chemin = manifeste(projet, [])
    dossiers = ["03_tournage_mai", "04_tournage_juin", "05_tournage_juillet"]
    obtenus = [
        declaration_de_rush.declarer_un_rush(
            project_dir=projet,
            video_path=copie_du_rush(tmp_path / d / "hd", "prise01.mp4"),
            logger=JournalMuet(), force_distinct=True,
        ).rush_id
        for d in dossiers
    ]
    assert obtenus == ["prise01", "prise01-2", "prise01-3"], obtenus

    from mixed_media_utility import project_maintenance

    project_maintenance.remove_project_element(
        projet, rush_id="prise01-3", dry_run=False)
    restants = [r["rush_id"] for r in rushes_du_manifeste(chemin)]
    assert "prise01-3" not in restants, restants
    assert "prise01-2" in restants, (
        "le retrait a emporte plus que sa cible : le reste ne mesure plus rien")

    aout = copie_du_rush(tmp_path / "06_tournage_aout" / "hd", "prise01.mp4")
    rendu = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=aout, logger=JournalMuet(),
        force_distinct=True,
    )

    assert rendu.rush_id == "prise01-3", (
        "le rang 3 n'est plus rendu par defaut : `EPIC11-ARB-238` a ete "
        f"renverse sans etre rouvert (obtenu {rendu.rush_id!r})")
    ecrit = [r for r in rushes_du_manifeste(chemin) if r["rush_id"] == "prise01-3"]
    assert len(ecrit) == 1, ecrit
    assert ecrit[0]["source_path"] == str(aout.resolve()), (
        "le nom est rendu a un rush qui n'est PAS celui de juillet -- c'est "
        "tout le glissement d'identite que la tolerance assume")


@requires_ffprobe
@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_D4_ARB238_le_rang_rendu_ne_depend_pas_de_la_POSITION_dans_la_liste(
    tmp_path, position
):
    """Le meme rendu de rang, la famille placee aux DEUX bords de la liste.

    Point 4 de la regle des fabriques : la cible au milieu demasque un `find`
    fautif, elle ne demasque pas un balayage tronque. Une famille lue en
    QUEUE dont la derniere entree serait sautee ferait remonter le rang 2 au
    lieu du 3 -- ce qui ressemble a s'y meprendre au rang rendu, et n'en est
    pas. Les trois positions le separent.

    La famille est seedee au manifeste plutot que declaree, pour que la
    POSITION soit reellement l'axe qui varie : trois declarations reelles
    empilent toujours la famille en queue, quelle que soit l'intention.
    """
    projet = tmp_path / "projet"
    chemin = manifeste(projet, rushes_de((1, 2, 3), position))
    from mixed_media_utility import project_maintenance

    project_maintenance.remove_project_element(
        projet, rush_id="prise01-3", dry_run=False)
    assert "prise01-3" not in [r["rush_id"] for r in rushes_du_manifeste(chemin)]

    video = copie_du_rush(tmp_path / "06_tournage_aout" / "hd", "prise01.mp4")
    rendu = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet(),
        force_distinct=True,
    )
    assert rendu.rush_id == "prise01-3", (position, rendu.rush_id)


@requires_ffprobe
def test_D4_ARB238_volet_symetrique_le_rang_du_MILIEU_retire_reste_CONSOMME(
    tmp_path,
):
    """Sans lui, le test ci-dessus se lirait comme « tout rang retire se rend ».

    Il ne se rend qu'en QUEUE, et c'est la moitie d'`EPIC11-ARB-92` que la
    tolerance ne touche pas : la ligne d'eau etant deduite du plus HAUT rang
    encore employe, retirer le rang 2 d'une famille `1, 2, 3` ne libere rien
    -- le suivant reste le 4. La cible est ici au milieu du DOMAINE, la ou le
    test precedent la prend en queue.
    """
    projet = tmp_path / "projet"
    chemin = manifeste(projet, rushes_de((1, 2, 3), "milieu"))
    from mixed_media_utility import project_maintenance

    project_maintenance.remove_project_element(
        projet, rush_id="prise01-2", dry_run=False)
    restants = [r["rush_id"] for r in rushes_du_manifeste(chemin)]
    assert "prise01-2" not in restants and "prise01-3" in restants, restants

    video = copie_du_rush(tmp_path / "06_tournage_aout" / "hd", "prise01.mp4")
    rendu = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet(),
        force_distinct=True,
    )
    assert rendu.rush_id == "prise01-4", (
        "un rang du MILIEU a ete rendu : le trou doit rester un trou "
        f"(obtenu {rendu.rush_id!r})")


def test_D4_ARB238_aucune_ligne_d_eau_de_rush_n_est_LUE_le_None_est_le_mecanisme():
    """**Le mecanisme de la tolerance, mesure la ou il vit** : le `None`.

    `disambiguated_rush_id` appelle `version_ranks.ligne_d_eau(None, rangs)`.
    Ce premier argument est la ligne d'eau PERSISTEE, et la passer a `None`
    est litteralement ce qui fait que le rang se rend : la ligne est alors
    deduite des seuls rangs encore employes.

    Mesure par **substitution**, jamais par lecture du code : un temoin
    remplace `ligne_d_eau` et l'on relit ce qu'il a recu. Le jour ou un champ
    de ligne d'eau serait pose cote rush -- ce qu'`EPIC11-ARB-238` a chiffre
    puis refuse --, cet argument cesserait d'etre `None` et ce test rougirait
    **avant** que le comportement ne change pour l'operateur.

    Volet symetrique dans le meme geste : les rangs employes, eux, sont bien
    transmis. Sans lui, un module qui n'appellerait plus rien du tout passerait.
    """
    vus: list[tuple] = []

    def temoin(declaree, rangs):
        vus.append((declaree, tuple(sorted(rangs))))
        return 7

    original = version_ranks.ligne_d_eau
    version_ranks.ligne_d_eau = temoin
    try:
        leve = extraction.disambiguated_rush_id("prise01", rushes_de((1, 2, 3)))
    finally:
        version_ranks.ligne_d_eau = original

    assert leve == "prise01-8"
    assert len(vus) == 1, vus
    assert vus[0][0] is None, (
        "une ligne d'eau PERSISTEE est desormais lue cote rush : le rang ne "
        "se rend plus, et `EPIC11-ARB-238` doit etre rouvert plutot que "
        f"contourne (recu {vus[0][0]!r})")
    assert vus[0][1] == (1, 2, 3), vus


def test_D4_ARB238_l_ASYMETRIE_avec_le_scan_est_MESUREE_et_non_affirmee():
    """L'autre cote de l'asymetrie, nomme ici pour qu'elle cesse d'etre a moitie.

    Le scan LIT un champ persiste (`scan_version_watermarks`) et le lot aussi
    (`lot_version_watermarks`) ; le rush n'en a **aucun**, et c'est la seule
    raison pour laquelle son rang se rend. Ce test mesure l'ecart de structure
    plutot que le comportement -- que le banc du scan tient deja de son cote --
    et il rougira des qu'un champ de rush apparaitra, quel que soit le
    comportement observable a ce moment-la.

    L'inventaire est pris **du code**, jamais recopie : ajouter un troisieme
    champ de ligne d'eau sans y penser fait rougir la garde d'inventaire.
    """
    from mixed_media_utility import project_maintenance, scan_ingest
    from mixed_media_utility.io.extraction_manifest import LOT_WATERMARKS_FIELD

    champs = {LOT_WATERMARKS_FIELD, scan_ingest.SCAN_WATERMARKS_FIELD,
              project_maintenance.SCAN_WATERMARKS_FIELD}
    # Deux objets versionnables portent une ligne d'eau, et deux seulement.
    assert champs == {"lot_version_watermarks", "scan_version_watermarks"}, (
        f"l'inventaire des lignes d'eau a change : {sorted(champs)}")

    # Et aucun de ces champs ne nomme le rush. Le motif est large a dessein :
    # un `rush_version_watermarks` comme un `rush_rank_watermarks` le ferait
    # rougir.
    releve = subprocess.run(
        ["grep", "-rnoE", "[a-z_]*watermark[a-z_]*",
         str(REPO_ROOT / "src" / "mixed_media_utility")],
        capture_output=True, text=True, timeout=120,
    )
    assert releve.returncode == 0, releve.stderr
    noms = {ligne.rsplit(":", 1)[-1] for ligne in releve.stdout.splitlines()}
    assert noms, "le releve est vide : la frontiere ne mesure plus rien"
    coupables = sorted(n for n in noms if "rush" in n)
    assert not coupables, (
        "une ligne d'eau de RUSH est apparue dans le code : `EPIC11-ARB-238` "
        f"tranche que le rang se rend, et ceci le renverse -- {coupables}")


# ===========================================================================
# F20 -- le `normalize_identifier` final de `disambiguated_rush_id`
# ===========================================================================
#
# **Il est MORT aujourd'hui, et il ne doit pas etre retire pour autant.**
# `format_rang_de_desambiguisation` rend `<tige>-<rang>` ou la tige est
# raccourcie a `CANONICAL_ID_MAX_LENGTH - LARGEUR_MAX_FRAGMENT_DESAMBIGUISATION`
# et le fragment tient dans cette largeur : le nom compose est deja conforme et
# deja sous la borne, donc l'appel de normalisation qui l'enveloppe ne change
# rien.
#
# **Ce que la revue a dit, et pourquoi la conclusion n'est PAS de le
# supprimer** (finding `F20`, a relire a la lumiere de `F2`). C'est cet appel
# meme qui RECOLLAIT le double tiret -- le defaut n.2 d'`EPIC11-ARB-233`, deux
# rushes distincts sous le meme identifiant --, et le correctif de `F2` a
# deplace le recollement dans `tige_de_desambiguisation`, en amont. L'appel est
# donc devenu inerte par le haut, pas par nature : il reste la porte par
# laquelle le defaut rentrerait si la composition changeait.
#
# Trois tests : qu'il est inerte AUJOURD'HUI (mesure, sur des tiges
# adversariales et aux deux bords du domaine des rangs), que l'inertie vient
# bien du recollement en amont, et qu'il est TOUJOURS LA.


#: Les tiges adversariales : celle qui n'a rien de special, celle dont un tiret
#: tombe sur la coupe -- le regime de `F2` --, et ses deux voisines. Quatre
#: valeurs DISTINGUABLES, pas quatre ecritures de la meme.
_TIGES_ADVERSARIALES = {
    "ordinaire": "prise01",
    "longue_sans_tiret": "a" * naming.CANONICAL_ID_MAX_LENGTH,
    **{f"tiret_{pose}": _rush_id_long_avec_tiret_en(indice)
       for pose, indice in _POSES_DE_TIRET.items()},
}

#: Les deux bords du domaine des rangs, et un rang du milieu.
_RANGS_AUX_BORDS = (version_ranks.VERSION_RANK_MIN, 50, naming.VERSION_RANK_MAX)


@pytest.mark.parametrize("rang", _RANGS_AUX_BORDS)
@pytest.mark.parametrize("nom_de_tige", sorted(_TIGES_ADVERSARIALES))
def test_F20_le_nom_COMPOSE_est_deja_normalise_l_appel_final_est_inerte(
    nom_de_tige, rang
):
    """Le nom rendu par la composition est un POINT FIXE de la normalisation.

    C'est la mesure exacte de « l'appel est mort » : si
    `normalize_identifier(x) == x` pour tout ce que la composition produit,
    alors l'enveloppe du produit ne change rien. Elle est prise sur les
    constantes du code -- la borne se lit dans `CANONICAL_ID_MAX_LENGTH`,
    jamais dans un document -- donc elle se refait toute seule le jour ou la
    borne bouge.
    """
    tige = _TIGES_ADVERSARIALES[nom_de_tige]
    compose = naming.format_rang_de_desambiguisation(tige, rang)
    assert len(compose) <= naming.CANONICAL_ID_MAX_LENGTH, compose
    assert naming.normalize_identifier(compose) == compose, (nom_de_tige, compose)
    # Et le rang s'y relit : un point fixe qui aurait perdu son fragment
    # serait inerte lui aussi, et faux.
    assert naming.rang_de_desambiguisation(compose, tige) == rang, compose


@pytest.mark.parametrize("nom_de_tige", sorted(_TIGES_ADVERSARIALES))
def test_F20_l_inertie_vient_du_RECOLLEMENT_en_amont_pas_de_la_nature(nom_de_tige):
    """Pourquoi cet appel ne se supprime pas : c'est LUI qui recollait.

    La tige est rendue deja conforme par `tige_de_desambiguisation` -- c'est le
    correctif de `F2`. Ce test le mesure sur la tige SEULE, en amont de toute
    composition : le double tiret n'existe plus a l'entree, donc il n'y a plus
    rien a recoller a la sortie. Le jour ou le recollement amont disparaitrait,
    l'appel final redeviendrait vivant, et le defaut n.2 d'`EPIC11-ARB-233`
    rentrerait par cette porte-la.
    """
    tige = _TIGES_ADVERSARIALES[nom_de_tige]
    racine = naming.tige_de_desambiguisation(tige)
    assert "--" not in racine, (nom_de_tige, racine)
    assert naming.normalize_identifier(racine) == racine, (nom_de_tige, racine)
    assert len(racine) <= (naming.CANONICAL_ID_MAX_LENGTH
                           - naming.LARGEUR_MAX_FRAGMENT_DESAMBIGUISATION)


def test_F20_l_appel_final_de_disambiguated_rush_id_est_TOUJOURS_LA():
    """**Frontiere negative : la porte reste gardee.**

    Un appel qu'aucune mesure n'atteint est exactement ce qu'une relecture
    supprime en le croyant mort -- et celui-la a deja ferme un defaut reel.
    La frontiere le lit a l'AST plutot qu'au texte : un `grep` serait vert sur
    un appel commente, ou sur une occurrence dans la docstring.

    Elle ne dit pas que l'appel SERT ; les deux tests ci-dessus mesurent qu'il
    ne sert pas. Elle dit qu'on ne le retire pas sans decider de le retirer.
    """
    source = (REPO_ROOT / "src" / "mixed_media_utility" / "extraction.py"
              ).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    fonctions = [n for n in ast.walk(arbre)
                 if isinstance(n, ast.FunctionDef)
                 and n.name == "disambiguated_rush_id"]
    assert len(fonctions) == 1, "`disambiguated_rush_id` a change de forme"

    retours = [n for n in ast.walk(fonctions[0]) if isinstance(n, ast.Return)]
    assert len(retours) == 1, retours
    appel = retours[0].value
    assert isinstance(appel, ast.Call), ast.dump(retours[0])
    assert getattr(appel.func, "id", None) == "normalize_identifier", (
        "l'enveloppe de normalisation a ete retiree de `disambiguated_rush_id` "
        "-- c'est elle qui recollait le double tiret avant `F2`, et elle reste "
        "la porte par laquelle le defaut n.2 d'`EPIC11-ARB-233` rentrerait")
    interieur = appel.args[0]
    assert isinstance(interieur, ast.Call), ast.dump(appel)
    assert getattr(interieur.func, "id", None) == "format_rang_de_desambiguisation"


# ---------------------------------------------------------------------------
# `EPIC11-ARB-241` -- un pointeur LFS ROUGIT, il ne saute nulle part
# ---------------------------------------------------------------------------

#: Les mots par lesquels un saut avoue qu'il porte sur un POINTEUR. Deux
#: entrees et non une : l'orthographe varie d'un banc a l'autre, et une
#: fabrique mono-element laisserait passer la moitie des redactions.
#:
#: **`lfs` seul n'en est PAS un**, et c'est la frontiere elle-meme qui l'a
#: appris : avec `lfs` dans la liste, elle rougissait sur
#: `test_politique_lfs.py`, dont le saut porte sur `git-lfs` INDISPONIBLE --
#: un outil absent, pas un media non materialise. Ce saut-la est structurel et
#: legitime : sans l'outil il n'y a rien a comparer, alors qu'avec un pointeur
#: il y a un defaut reparable a cout nul. `EPIC11-ARB-241` vise le second, pas
#: le premier.
_AVEUX_DE_POINTEUR = ("pointeur", "pointer")


def _sauts_de_pointeur_du_depot() -> list[str]:
    """Tous les `pytest.skip(...)` de `tests/` dont le message avoue un pointeur.

    Lu a l'AST plutot qu'au `grep` : un `grep` rougirait sur une docstring qui
    RACONTE le defaut -- et cette section en contient plusieurs, a commencer par
    celle d'`exiger_le_media`.
    """
    trouves: list[str] = []
    for chemin in sorted((REPO_ROOT / "tests").rglob("test_*.py")):
        try:
            arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - un banc casse se voit ailleurs
            continue
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            cible = noeud.func
            nomme_skip = (
                (isinstance(cible, ast.Attribute) and cible.attr == "skip")
                or (isinstance(cible, ast.Name) and cible.id == "skip")
            )
            if not nomme_skip:
                continue
            # Le message se lit sur les litteraux de l'appel, f-strings
            # comprises : `pytest.skip(f"{x.name} est un pointeur LFS")`.
            textes = [n.value.lower() for n in ast.walk(noeud)
                      if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            message = " ".join(textes)
            if any(aveu in message for aveu in _AVEUX_DE_POINTEUR):
                trouves.append(
                    f"{chemin.relative_to(REPO_ROOT)}:{noeud.lineno}")
    return trouves


def test_ARB241_AUCUN_banc_ne_SAUTE_sur_un_pointeur_LFS():
    """**Frontiere negative.** Un pointeur rougit ; il ne se range pas en silence.

    `EPIC11-ARB-241`, tranche par Egan le 2026-09-05 sur un ecart MESURE : ce
    banc-ci rendait 13 rouges sur 90 dans un conteneur non materialise pendant
    que le banc `E2-1f` sautait. Deux bancs, deux regimes, meme cause.

    **Pourquoi une frontiere negative et pas une consigne** : aucun test
    positif ne verrait revenir un `pytest.skip` sur un pointeur. Le saut est
    precisement ce qui ne se signale pas -- c'est tout son defaut, et c'est
    aussi ce qui le rend indetectable a la relecture d'un diff vert.
    """
    sauts = _sauts_de_pointeur_du_depot()
    assert not sauts, (
        "ces bancs SAUTENT sur un pointeur LFS au lieu de rougir "
        f"({', '.join(sauts)}) : `EPIC11-ARB-241` l'interdit. La reparation "
        "coute zero octet reseau (`git lfs checkout`), donc le defaut doit se "
        "signaler fort -- voir `exiger_le_media`.")


def test_ARB241_la_frontiere_ci_dessus_MORD_reellement():
    """Le volet anti-vacuite, sans lequel la frontiere pourrait ne rien lire.

    Une frontiere qui balaie une arborescence peut devenir verte pour la
    mauvaise raison -- un motif qui ne reconnait plus rien, un `rglob` qui ne
    trouve plus les bancs. On lui donne donc a manger un saut FABRIQUE, dans
    les deux redactions que le depot a portees, et on exige qu'elle le voie.
    """
    for redaction in (
        'import pytest\ndef test_x():\n    pytest.skip("x est un pointeur LFS")\n',
        'from pytest import skip\ndef test_x():\n'
        '    skip(f"{n} est un POINTEUR (git lfs checkout)")\n',
    ):
        arbre = ast.parse(redaction)
        vus = [n for n in ast.walk(arbre)
               if isinstance(n, ast.Call)
               and ((isinstance(n.func, ast.Attribute) and n.func.attr == "skip")
                    or (isinstance(n.func, ast.Name) and n.func.id == "skip"))
               and any(aveu in " ".join(
                   c.value.lower() for c in ast.walk(n)
                   if isinstance(c, ast.Constant) and isinstance(c.value, str))
                   for aveu in _AVEUX_DE_POINTEUR)]
        assert len(vus) == 1, redaction

    # Et le balayage lit bien une arborescence PEUPLEE : sans ce cardinal, un
    # `rglob` casse rendrait la frontiere verte en ne lisant aucun fichier.
    assert len(list((REPO_ROOT / "tests").rglob("test_*.py"))) > 100


def test_ARB241_exiger_le_media_ROUGIT_sur_un_pointeur_et_se_TAIT_sur_un_media(
        tmp_path):
    """Les deux volets de la sonde, et le second n'est pas decoratif.

    Sans le volet symetrique, une sonde qui rougirait sur TOUT passerait le
    volet positif -- et rendrait la suite entiere rouge.
    """
    pointeur = tmp_path / "faux_rush.mp4"
    pointeur.write_bytes(b"version https://git-lfs.github.com/spec/v1\n" + b"x" * 88)
    assert pointeur.stat().st_size < TAILLE_PLANCHER_D_UN_MEDIA
    with pytest.raises(AssertionError, match="POINTEUR LFS"):
        exiger_le_media(pointeur)

    media = tmp_path / "vrai_rush.mp4"
    media.write_bytes(b"\x00" * TAILLE_PLANCHER_D_UN_MEDIA)
    exiger_le_media(media)  # ne leve pas
