"""Aucun test de ce depot ne dort en silence.

Ce fichier **remplace** `test_desactivation_regime_vrac.py`, retire par la story
5.24 (AC 8) avec son constructeur de motif `desactivation_regime_vrac.py`. Le
motif du retrait, ecrit ici parce que c'est l'emplacement du retrait :

* **le registre n'avait plus de sujet.** Il comptait les tests endormis au titre
  d'`EPIC5-ARB-84` -- 35, avec leur repartition, leur inventaire nominatif et
  leurs motifs en trois parties. La story 5.24 les a tous statues : 19 rebases
  sur le regime de profil designe (classe A), 15 reecrits contre le tri par QR
  (classe B), 1 supprime avec son motif ecrit a l'emplacement du retrait
  (classe C, `test_chain_profile_scan.py`). Le compteur passe de 35 a 0, donc
  « un compteur de tests endormis n'a plus de sujet quand plus aucun ne dort » ;
* **le constructeur de motif non plus.** Il etait le seul chemin par lequel un
  test de ce depot avait le droit d'etre endormi au titre de ce mandat ; le
  mandat est clos.

**Ce qui NE part pas avec eux, et c'est tout l'objet de ce fichier.** Le registre
portait une garde dont le sujet, lui, survit : « un `skip` muet est un echec
d'AC » (AC 11 de 5.23), trouvee incomplete puis fermee le 2026-08-19
(`EPIC5-ARB-100`). Un `@pytest.mark.skip(reason="instable sur cette machine")`
pose sur n'importe quel test actif du depot doit rester **visible**. La doctrine
du depot est explicite : un test dont le **sujet** a disparu se supprime, un test
dont seule la **forme** est perimee se repare. C'est le second cas, et c'est ce
qui est fait ici.

Le compteur reste **le collecteur de pytest**, interroge dans un sous-processus
sur l'arbre `tests/` entier : c'est le seul organe qui sache ce qui sera
reellement saute -- il deplie les parametrages et applique les marqueurs de
module et de classe. Un inventaire reconstitue a la main serait une seconde
implementation, donc une source de divergence silencieuse. C'est la tautologie
payee trois fois dans ce depot (5.9, puis deux fois le 2026-08-18).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))

#: Les `skip` **inconditionnels** du depot, en litteral. Zero : aucun test de ce
#: depot ne dort, pour aucun motif. Une entree qui apparait ici est soit un
#: endormissement clandestin, soit un endormissement legitime -- et dans le second
#: cas il se declare **ici**, avec son motif, ce qui le rend visible en revue.
#:
#: Les `skipif` n'y sont pas : ce sont des portes d'environnement (ffmpeg, Xvfb)
#: dont le cardinal depend de la machine, donc les epingler mesurerait le PATH et
#: pas le depot. Un endormissement clandestin s'ecrit `skip`, pas `skipif(True)`.
ENDORMIS_DECLARES: tuple[str, ...] = (
    # **Un vide de PARAMETRAGE, pas un test qu'on eteint** (constate le
    # 2026-09-07 par la premiere non-regression large depuis `EPIC11-ARB-248`).
    # `TOLERANCES_D_ABREVIATION` a ete videe le 2026-09-06 -- le drapeau
    # `allow_abbrev=False` a ete porte aux seize sous-parseurs --, et sur une
    # table vide `parametrize` ne rend aucun cas : pytest saute alors le test
    # avec « got empty parameter set ».
    #
    # Le depot le savait deja et l'a couvert **du bon cote** :
    # `test_AUCUNE_tolerance_d_abreviation_ne_SUBSISTE` existe precisement
    # parce que « sur une table vide, le test d'a cote devient un skip, et une
    # frontiere sautee n'affirme rien ». Ce qui manquait est ici : le registre
    # des endormissements ne le connaissait pas.
    "tests/unit/test_suppression_element_de_projet.py"
    "::test_la_TOLERANCE_d_abreviation_est_encore_REELLE[NOTSET]",
    # **La MEME forme, une seconde fois, et pour la meilleure des raisons : la
    # mesure a fait ce qu'elle promettait** (constate le 2026-09-07 sur la
    # course `cloture0907b`). `test_le_TEMOIN_d_une_absence_n_existe_TOUJOURS_PAS`
    # se parametre sur `[f for f in REGISTRE if f.temoin]` ; le SEUL temoin que
    # ce registre ait jamais porte -- `remove_project_element:frames_extraites`
    # -- a RESOLU le 2026-09-07, le filet a ete cable, et son entree a change de
    # famille pour `hors-produit:cle`. La table se vide donc, et sur une table
    # vide `parametrize` ne rend aucun cas : pytest saute avec « got empty
    # parameter set ».
    #
    # **Ce test-la NE PEUT PAS se reveiller aujourd'hui, et ce n'est pas un
    # choix de confort** -- verifie plutot que recopie. Le reveiller demanderait
    # d'inscrire un temoin au registre ; or les trois absences restantes
    # attendent un ECRAN que le depot n'a PAS promis, et la tete de
    # `test_registre_des_filets.py` tranche deja le cas : « poser un temoin sur
    # un nom que le depot n'a pas promis serait decoratif, puisqu'il ne
    # resoudrait pas davantage le jour ou l'ecran arriverait sous un autre
    # nom ». Un temoin invente rendrait ce banc vert sur un nom qui ne designe
    # rien, ce qui est strictement pire que le skip.
    #
    # Et le MECANISME, lui, ne dort pas : il est mesure sur un corpus de
    # SYNTHESE, dans les deux sens, par `test_le_temoin_de_PARAMETRE_mord_dans_
    # les_deux_sens` (un parametre qui existe -> resout ; un nom que le depot
    # n'a jamais promis -> ne resout pas) et par
    # `test_un_temoin_qui_pointe_dans_le_VIDE_se_leve`. Ce qui dort ici est le
    # parcours du registre, pas l'outil.
    #
    # **La sortie de ce skip est mesuree des DEUX cotes**, et c'est ce qui
    # dispense d'y revenir a la main : le jour ou une entree porte a nouveau un
    # temoin, le test se reveille tout seul, cette declaration devient perimee
    # et l'egalite d'ensembles ci-dessous rougit en la nommant
    # (« declares mais plus endormis ») ; et du cote du registre,
    # `test_AUCUNE_entree_du_registre_ne_porte_de_TEMOIN` rougit le meme jour
    # en disant quoi retirer ici. Le zero est une valeur mesuree, pas une
    # phrase de tete de fichier.
    "tests/unit/tui/test_registre_des_filets.py"
    "::test_le_TEMOIN_d_une_absence_n_existe_TOUJOURS_PAS[NOTSET]",
)

#: La sentinelle du mandat clos. Elle reste **nommee** parce qu'un test l'exige a
#: zero : un decorateur d'endormissement `EPIC5-ARB-84` qui reviendrait dans le
#: depot -- copie depuis un ancien commit, par exemple -- doit rendre ce lot
#: rouge, et non passer pour un `skip` declare parmi d'autres.
SENTINELLE_MANDAT_CLOS = "[REGIME-VRAC]"


def _releve_du_collecteur() -> tuple[list, list]:
    """Ce que **pytest** trouve, sur `tests/` entier, en `--collect-only`.

    Rend `(sautes au titre du mandat clos, autres sautes inconditionnels)`.
    L'arbre **entier** et pas quelques fichiers : c'est ce qui rend l'assertion
    « aucun test du depot n'est endormi » vraie plutot que probable.
    """
    with tempfile.TemporaryDirectory() as bac:
        cible = Path(bac) / "collecte.json"
        autres = Path(bac) / "autres.json"
        environnement = dict(os.environ)
        environnement["COLLECTE_VRAC_JSON"] = str(cible)
        environnement["COLLECTE_AUTRES_JSON"] = str(autres)
        environnement["PYTHONPATH"] = os.pathsep.join(
            [str(ICI), environnement.get("PYTHONPATH", "")]).rstrip(os.pathsep)
        acheve = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q",
             "-p", "no:cacheprovider", "-p", "_collecte_desactives_vrac"],
            cwd=RACINE, env=environnement, capture_output=True, text=True,
            timeout=300)
        assert acheve.returncode == 0, acheve.stdout[-3000:] + acheve.stderr[-2000:]
        assert cible.is_file(), (
            "le greffon de collecte n'a rien ecrit: sans lui ce fichier ne "
            "mesure rien\n" + acheve.stdout[-2000:])
        assert autres.is_file(), (
            "le second releve du greffon est absent: le compte des "
            "endormissements ne mesurerait rien\n" + acheve.stdout[-2000:])
        return (
            json.loads(cible.read_text(encoding="utf-8")),
            json.loads(autres.read_text(encoding="utf-8")),
        )


@pytest.fixture(scope="module")
def releves():
    return _releve_du_collecteur()


def test_plus_aucun_test_ne_dort_sous_le_mandat_clos(releves) -> None:
    """AC 8 de la story 5.24 : le compteur passe de 35 a **0**.

    Mesure par le **collecteur de pytest** sur l'arbre `tests/` entier, jamais
    par une relecture du source et jamais recompte a partir de ce que le
    collecteur rend -- c'est la tautologie contre laquelle le registre avait ete
    ecrit, et elle ne revient pas avec son remplacant.

    Le zero est ecrit **en litteral**. Relacher l'egalite en `<=` -- le reflexe
    naturel -- ferait passer toute reapparition du mandat, c'est-a-dire
    exactement le faux succes que l'AC 11 de 5.23 nommait.
    """
    sous_mandat, _ = releves
    assert sous_mandat == [], sorted(nom for nom, _ in sous_mandat)
    assert len(sous_mandat) == 0


def test_aucun_test_du_depot_n_est_endormi_hors_declaration(releves) -> None:
    """« Un `skip` muet est un echec d'AC », et il n'etait mesure par rien.

    Trou trouve par l'injection par AC de l'AC 9 (`EPIC5-ARB-100`, 2026-08-19) :
    un `@pytest.mark.skip(reason="instable sur cette machine")` pose sur un test
    actif survivait au registre entier, dont les assertions ne voyaient que ce
    que la sentinelle leur montrait. La seule forme d'endormissement que l'AC
    nomme explicitement etait la seule que son compteur ne pouvait pas voir.

    Ce test ne juge pas de la **legitimite** d'un endormissement : il exige qu'il
    soit **declare**. Un test qu'on veut vraiment endormir s'ajoute a
    `ENDORMIS_DECLARES`, ce qui le rend visible en revue -- et c'est tout ce que
    l'AC demande.
    """
    _, autres = releves
    trouves = {nom for nom, _ in autres}
    assert trouves == set(ENDORMIS_DECLARES), {
        "clandestins": sorted(trouves - set(ENDORMIS_DECLARES)),
        "declares mais plus endormis": sorted(set(ENDORMIS_DECLARES) - trouves),
    }
    # **Le cardinal, et plus le litteral ZERO** (2026-09-07). La ligne d'avant
    # etait `== len(ENDORMIS_DECLARES) == 0`, ce qui CONTREDISAIT le docstring
    # juste au-dessus : « un test qu'on veut vraiment endormir s'ajoute a
    # `ENDORMIS_DECLARES` ». Avec le zero en dur, l'ajouter ne servait a rien --
    # la porte que ce banc ouvre etait condamnee par son propre verrou, et la
    # contradiction n'a ete payee qu'au premier endormissement legitime.
    #
    # Ce qui tient la frontiere n'est pas le zero, c'est l'EGALITE d'ensembles
    # ci-dessus : elle attrape un clandestin ET une declaration perimee. Le
    # cardinal ne sert qu'a exclure un doublon dans le releve.
    assert len(autres) == len(ENDORMIS_DECLARES)
    # Et le mandat clos, lui, reste a ZERO en litteral : c'est l'autre banc de
    # ce fichier qui le tient, et rien ici ne le relache.


def test_le_constructeur_de_motif_du_mandat_clos_est_retire() -> None:
    """AC 8 : le registre et son constructeur partent **dans le meme mouvement**.

    Le laisser en place laisserait un chemin ouvert pour rendormir un test sous
    un mandat clos, et le motif produit citerait une story livree -- donc une
    promesse deja tenue, ce qui est pire qu'un motif absent.
    """
    for retire in ("desactivation_regime_vrac.py",
                   "test_desactivation_regime_vrac.py"):
        assert not (ICI / retire).exists(), retire
    # Et plus aucun test du depot ne l'importe ni ne pose sa sentinelle.
    for fichier in sorted(Path(RACINE / "tests").rglob("*.py")):
        if fichier.name in {Path(__file__).name, "_collecte_desactives_vrac.py"}:
            continue
        texte = fichier.read_text(encoding="utf-8")
        assert "desactive_jusqu_a_l_ingest_en_vrac" not in texte, fichier
        assert SENTINELLE_MANDAT_CLOS not in texte, fichier
