"""Frontiere de `tests/conftest.py` -- la selection des tests par dependance.

**Pourquoi ce banc existe.** `tests/conftest.py` decide quels fichiers de test
sont COLLECTES. Il ne peut que RETRANCHER, et jusqu'a cette revue rien ne
mesurait ce qu'il retranchait : les trois couches ont trouve independamment
qu'un mutant plausible (`_est_disponible` lisant `sys.modules`) y faisait
disparaitre 35 fichiers EN SILENCE sur un poste equipe, collecte verte et code
de sortie nul.

Et c'est faute de cette mesure que l'auteur a pu ecrire, dans le module puis
dans `ci.yml`, un motif FAUX : « quatre fichiers hors de `tests/unit/gui/`
importent PySide6 ». Ils n'en citent que le nom en litteral de chaine. Le
dernier test de ce fichier rend ce constat impossible a ecrire faux.

Regle des fabriques : chaque echantillon porte au moins deux fichiers
distinguables, et le fichier FAUTIF n'est jamais en premiere position.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RACINE_DEPOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE_DEPOT / "tests"))
from _chemins_bmad import archives_presentes  # noqa: E402
from _chemins_bmad import porte_l_archive_privee  # noqa: E402


def _charger_conftest():
    """Charge `tests/conftest.py` comme un module ordinaire, pour l'interroger."""
    chemin = RACINE_DEPOT / "tests" / "conftest.py"
    specification = importlib.util.spec_from_file_location("conftest_racine", chemin)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


CONFTEST = _charger_conftest()


class _ConfigFactice:
    """Tient lieu de l'objet `config` de pytest, que le hook ne consulte pas."""


def _ecarte(chemin: Path) -> bool:
    """Vrai si le hook ecarterait ce chemin."""
    return CONFTEST.pytest_ignore_collect(chemin, _ConfigFactice()) is True


@pytest.fixture
def sans_les_dependances_optionnelles(monkeypatch):
    """Le filtre mesure comme si `[gui]` n'etait PAS installe.

    **Ce que cette fixture ferme, et il a coute neuf rouges** (liaison du
    2026-09-01). Huit tests de ce banc posaient `assert _ecarte(fautif)` en
    laissant `_est_disponible` interroger l'environnement REEL. Ils ne tenaient
    donc que sur une machine ou PySide6 est absent -- la CI de `main`. Sur un
    poste portant l'extra `[gui]`, c'est-a-dire **exactement la machine pour
    laquelle ce filtre existe**, ils rougissent tous les huit, et ce qu'ils
    annoncaient mesurer -- la logique du hook -- n'etait pas mesure du tout :
    ils mesuraient l'etat d'installation de l'hote.

    Un banc de frontiere ne peut pas dependre de ce qu'il y a sur la machine.
    La disponibilite est donc **posee**, dans les deux sens, par les tests qui
    en ont besoin : absente ici, presente dans
    `test_le_filtre_n_ecarte_rien_quand_la_dependance_est_installee`. Seul
    `test_disponible_signifie_IMPORTABLE_et_non_deja_importe` interroge encore
    la vraie fonction, et c'est son sujet.
    """
    monkeypatch.setattr(
        CONFTEST, "_est_disponible",
        lambda module: module not in CONFTEST.MODULES_OPTIONNELS)


def _ecrire(dossier: Path, nom: str, contenu: str) -> Path:
    fichier = dossier / nom
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text(contenu, encoding="utf-8")
    return fichier


def test_un_fichier_qui_importe_qt_est_ecarte_et_son_voisin_ne_l_est_pas(tmp_path, sans_les_dependances_optionnelles):
    """Deux fichiers distinguables, le fautif en SECONDE position."""
    sain = _ecrire(tmp_path, "test_a_sain.py", "import json\n\ndef test_x(): pass\n")
    fautif = _ecrire(tmp_path, "test_b_qt.py", "import PySide6\n\ndef test_y(): pass\n")

    assert not _ecarte(sain), "un fichier sans dependance optionnelle ne doit jamais etre ecarte"
    assert _ecarte(fautif)


def test_le_besoin_en_qt_se_voit_aussi_par_la_voie_INDIRECTE(tmp_path, sans_les_dependances_optionnelles):
    """Importer `mixed_media_utility.gui` exige Qt sans nommer PySide6."""
    sain = _ecrire(tmp_path, "test_a_coeur.py", "from mixed_media_utility import cli\n")
    fautif = _ecrire(
        tmp_path, "test_b_indirect.py", "from mixed_media_utility.gui import coquille\n"
    )

    assert not _ecarte(sain)
    assert _ecarte(fautif)


def test_le_besoin_en_qt_se_voit_par_le_NOM_D_UNE_FIXTURE_de_plugin(tmp_path, sans_les_dependances_optionnelles):
    """Une fixture de plugin n'apparait dans AUCUN import.

    C'est le defaut qui a fait tomber neuf tests : `tests/unit/gui/conftest.py`
    n'importe ni PySide6 ni pytest-qt, il nomme `qapp` en parametre.
    """
    sain = _ecrire(tmp_path, "test_a_sain.py", "def test_x(tmp_path): pass\n")
    fautif = _ecrire(tmp_path, "test_b_fixture.py", "def test_y(qtbot): pass\n")
    fautif_cls = _ecrire(tmp_path, "test_c_cls.py", "def test_z(qapp_cls): pass\n")

    assert not _ecarte(sain)
    assert _ecarte(fautif)
    # `qapp_cls` est la sixieme fixture de pytest-qt ; elle manquait a la table.
    assert _ecarte(fautif_cls)


def test_le_besoin_se_HERITE_du_conftest_du_dossier(tmp_path, sans_les_dependances_optionnelles):
    """Un fichier sans aucun import Qt reste inexecutable si SON DOSSIER l'exige."""
    dossier = tmp_path / "avec_conftest"
    _ecrire(dossier, "conftest.py", "import pytest\n\n@pytest.fixture(autouse=True)\ndef _f(qapp): pass\n")
    hérité = _ecrire(dossier, "test_frontiere.py", "def test_x(): pass\n")
    voisin = _ecrire(tmp_path, "test_ailleurs.py", "def test_y(): pass\n")

    assert _ecarte(hérité), "le besoin du dossier doit se transmettre a ses fichiers"
    assert not _ecarte(voisin), "et ne doit PAS deborder sur les dossiers voisins"


def test_un_DOSSIER_dont_le_conftest_importe_qt_est_ecarte_en_bloc(tmp_path, sans_les_dependances_optionnelles):
    """Sinon la collecte ENTIERE tombe, y compris des fichiers sans rapport.

    pytest charge le `conftest.py` d'un dossier AVANT d'appeler le hook sur ses
    fichiers : ecarter le dossier en amont est le seul moment ou l'on peut
    encore l'eviter.
    """
    sain = tmp_path / "coeur"
    _ecrire(sain, "test_x.py", "def test_x(): pass\n")
    fautif = tmp_path / "interface"
    _ecrire(fautif, "conftest.py", "from PySide6.QtWidgets import QApplication\n")
    _ecrire(fautif, "test_y.py", "def test_y(): pass\n")

    assert not _ecarte(sain)
    assert _ecarte(fautif)


def test_la_seconde_convention_de_nommage_de_pytest_est_couverte(tmp_path, sans_les_dependances_optionnelles):
    """`*_test.py` est collecte par defaut au meme titre que `test_*.py`.

    Aucun `python_files` n'est configure dans ce depot. Un fichier de cette
    forme echappait au filtre et, avec le `-x` de la CI, arretait le job.
    """
    sain = _ecrire(tmp_path, "a_sain_test.py", "def test_x(): pass\n")
    fautif = _ecrire(tmp_path, "b_qt_test.py", "import PySide6\n")

    assert not _ecarte(sain)
    assert _ecarte(fautif)


def test_un_fichier_qui_CITE_le_nom_en_chaine_n_est_JAMAIS_ecarte(tmp_path, sans_les_dependances_optionnelles):
    """La frontiere qui rend le constat faux de l'auteur impossible a ecrire.

    Quatre fichiers du depot (`test_cadence_previz`, `test_encode_previz`,
    `test_extraction_previz`, `test_scan_previz`) CITENT `PySide6` en litteral
    de chaine, dans les listes d'imports interdits de leurs propres frontieres.
    L'auteur les a crus importateurs -- un grep lu la ou il fallait un AST -- et
    a grave ce motif dans `tests/conftest.py` et dans `ci.yml`.

    Les ecarter ferait disparaitre quatre fichiers de tests du COEUR.
    """
    fautif = _ecrire(tmp_path, "test_a_qt.py", "import PySide6\n")
    citant = _ecrire(
        tmp_path,
        "test_b_citant.py",
        'INTERDITS = ["PySide6", "pytestqt", "qtbot"]\n\ndef test_frontiere():\n    assert INTERDITS\n',
    )

    assert _ecarte(fautif)
    assert not _ecarte(citant), (
        "un fichier qui NOMME PySide6 dans une chaine ne l'importe pas : "
        "l'ecarter retirerait des tests du coeur"
    )


def test_les_quatre_fichiers_previz_du_depot_restent_collectes():
    """Le meme invariant, sur les fichiers REELS plutot que sur une synthese.

    Un echantillon peut diverger du depot ; ces quatre-la sont ceux que le
    motif faux accusait, nommement.
    """
    for nom in (
        "test_cadence_previz.py",
        "test_encode_previz.py",
        "test_extraction_previz.py",
        "test_scan_previz.py",
    ):
        chemin = RACINE_DEPOT / "tests" / "unit" / nom
        assert chemin.is_file(), f"{nom} a disparu du depot"
        assert not _ecarte(chemin), (
            f"{nom} ne doit PAS etre ecarte : il cite PySide6 en chaine, il ne l'importe pas"
        )


def test_le_filtre_n_ecarte_rien_quand_la_dependance_est_installee(
        tmp_path, monkeypatch, sans_les_dependances_optionnelles):
    """Sur un poste portant l'extra [gui], la suite entiere tourne.

    Sens INVERSE du filtre, et le plus dangereux : un faux ecart fait
    disparaitre des tests sans bruit, collecte verte et code de sortie nul.
    """
    fautif = _ecrire(tmp_path, "test_qt.py", "import PySide6\n")
    assert _ecarte(fautif)

    monkeypatch.setattr(CONFTEST, "_est_disponible", lambda module: True)
    assert not _ecarte(fautif), (
        "avec la dependance disponible, plus rien ne doit etre ecarte"
    )


def test_disponible_signifie_IMPORTABLE_et_non_deja_importe():
    """`_est_disponible` doit repondre sur ce qui est INSTALLE, pas sur ce qui
    est deja charge.

    C'est le mutant que la couche 1 a trouve et que rien ne tuait :
    `return module in sys.modules` rend le meme resultat que la vraie
    implementation dans un environnement ou la dependance est ABSENTE -- donc
    en CI, ou il est invisible. Sur un poste portant l'extra `[gui]`, PySide6
    n'est pas encore importe au moment de la collecte : le mutant ecarterait
    alors tout `tests/unit/gui/` EN SILENCE, collecte verte et code de sortie
    nul.

    Le banc l'epingle avec un module de la bibliotheque standard choisi pour
    n'etre importe par personne ici : il est importable, et il n'est pas dans
    `sys.modules`. Les deux formulations y divergent, donc le mutant meurt.
    """
    import sys

    # **Le temoin se CHOISIT a l'execution, il ne se grave plus.** La premiere
    # redaction posait `colorsys` en dur avec, en message d'echec, « choisir un
    # autre temoin » -- ce qui est l'aveu qu'un temoin grave est un pari sur ce
    # que la suite importera un jour. Le pari a ete perdu a la liaison du
    # 2026-09-01 : `colorsys` arrive par la chaine `textual` -> `rich`. La
    # liste est parcourue jusqu'au premier module encore non importe, et son
    # epuisement est un echec NOMME plutot qu'une assertion qui ment.
    candidats = ("colorsys", "cgi", "wave", "sunau", "chunk", "aifc",
                 "imghdr", "sndhdr", "nis", "crypt", "mailcap")
    temoin = next((nom for nom in candidats
                   if nom not in sys.modules
                   and importlib.util.find_spec(nom) is not None), None)
    assert temoin is not None, (
        "aucun temoin de la bibliotheque standard n'est a la fois installe et "
        f"non importe parmi {candidats} : en ajouter un, sans quoi ce banc "
        "cesse de distinguer les deux formulations")
    assert CONFTEST._est_disponible(temoin) is True, (
        "un module installe mais pas encore importe doit etre vu DISPONIBLE"
    )

    # Et l'inverse : un module qui n'existe pas n'est jamais disponible.
    assert CONFTEST._est_disponible("paquet_totalement_absent_xyz") is False


# ---------------------------------------------------------------------------
# L'ecart des bancs dont l'ARCHIVE de travail est absente (`EPIC11-ARB-268`)
# ---------------------------------------------------------------------------
#
# Le regime que ce bloc mesure n'existe QUE sur le depot public : l'orphelin y
# part sans `_bmad-output/`, a trois chemins pres, et quatre bancs de
# tracabilite lisent des documents qui restent prives. Sans l'ecart, le
# `pytest tests/unit -x -q` de `ci.yml` s'arrete au premier -- c'est-a-dire que
# la porte `valider` de la release devient infranchissable pour une raison qui
# n'est pas un defaut du produit.
#
# Il est mesure ici plutot que la-bas parce qu'il n'y a pas de « la-bas » a
# mesurer : le depot public n'a pas encore de CI. Une frontiere qui attend
# l'incident pour exister n'existe pas.

def _bancs_a_archive_privee() -> dict[str, str]:
    """Les bancs qu'`EPIC11-ARB-268` laisse hors de la CI publique, DERIVES.

    **La premiere redaction recopiait ce registre ici, et les trois frontieres
    de perimetre l'ont refuse en choeur** -- recopier les quatre chemins
    faisait de ce banc-ci un LECTEUR de quatre archives privees, donc un
    cinquieme banc a exclure, donc un registre faux. La recopie se punissait
    elle-meme, ce qui est exactement ce qu'on attend d'une frontiere.

    La source unique est `test_perimetre_public.PRIVES_ET_LEUR_BANC_EXCLU` :
    c'est elle qu'`EPIC11-ARB-268` a produite, et c'est elle que la frontiere
    de perimetre tient a jour en rougissant sur un cinquieme document. On la
    retourne (chemin -> banc devient banc -> chemin), on ne la redit pas.
    """
    import importlib
    perimetre = importlib.import_module("test_perimetre_public")
    return {banc: chemin
            for chemin, banc in perimetre.PRIVES_ET_LEUR_BANC_EXCLU.items()}


BANCS_A_ARCHIVE_PRIVEE = _bancs_a_archive_privee()


def _exige_le_depot_de_TRAVAIL():
    """Saute quand ce depot n'est PAS celui du travail, et le dit.

    **Les trois tests qui suivent assertent quelque chose du depot de
    TRAVAIL** -- leur nom le dit pour l'un d'eux, leur derniere clause pour les
    deux autres. Sur l'historique orphelin du depot PUBLIC, aucune des quatre
    archives privees n'existe par construction (`EPIC8-ARB-12`) : ils y
    rougissent tous, non pas sur un defaut mais sur le fait de ne pas etre chez
    eux. Mesure du 2026-09-08 sur l'orphelin reel : 9 rouges dans ce seul
    fichier, sur 40 au total.

    **Le saut est STRUCTUREL, jamais un drapeau.** Il se tranche sur la
    presence des archives, pas sur une variable d'environnement -- meme forme
    que `test_politiques_du_depot.py` devant un `origin/main` hors d'atteinte,
    et pour le meme motif : ce qui se rallume a la main ne se rallume pas.

    **Et il ne saute que sur ZERO.** Un registre partiellement perime sur le
    depot de travail -- trois archives sur quatre, le cas d'un document
    renomme -- continue de faire rougir, ce qui est exactement le defaut que
    `test_le_registre_DERIVE...` existe pour attraper. C'est pourquoi l'aide
    partagee rend un CARDINAL et non un booleen.
    """
    if not porte_l_archive_privee(RACINE_DEPOT, BANCS_A_ARCHIVE_PRIVEE.values()):
        pytest.skip(
            "aucune des archives privees declarees n'existe ici : ce depot "
            "n'est pas celui du TRAVAIL (historique orphelin du depot public, "
            "EPIC8-ARB-12). Ce test asserte l'etat du depot de travail et n'a "
            "rien a y mesurer.")


@pytest.mark.parametrize("banc", sorted(BANCS_A_ARCHIVE_PRIVEE))
def test_sur_le_depot_de_TRAVAIL_aucun_banc_prive_n_est_ecarte(banc):
    """Le sens qui compte ici : l'ecart ne doit RIEN faire sur cet arbre.

    Un ecart qui mordrait des deux cotes retirerait quatre bancs de la mesure
    privee sans que personne ne le voie -- une frontiere qui se desarme
    elle-meme, exactement ce que la politique du depot appelle un faux vert.
    """
    _exige_le_depot_de_TRAVAIL()

    assert CONFTEST._archives_absentes(RACINE_DEPOT / banc) == [], (
        f"`{banc}` est ecarte sur le depot de TRAVAIL, ou son archive existe")


@pytest.mark.parametrize("banc", sorted(BANCS_A_ARCHIVE_PRIVEE))
def test_le_meme_banc_EST_ecarte_quand_son_archive_manque(banc, tmp_path):
    """Le volet symetrique, joue sur une copie et jamais sur l'arbre reel.

    Le banc est recopie dans un faux depot ou `_bmad-output/` existe mais ou
    l'archive qu'il lit MANQUE -- c'est-a-dire l'etat exact de l'orphelin
    public. On mesure alors que l'ecart se declenche ET qu'il NOMME le chemin
    manquant : un saut muet vaudrait a peine mieux que l'erreur qu'il remplace.
    """
    archive = BANCS_A_ARCHIVE_PRIVEE[banc]
    faux = tmp_path / "depot"
    (faux / "tests" / "unit" / "tui").mkdir(parents=True)
    # `_bmad-output/` existe et est AMPUTE : c'est le garde-fou de l'ancetre.
    (faux / Path(archive).parent).mkdir(parents=True, exist_ok=True)
    copie = faux / banc
    copie.write_text((RACINE_DEPOT / banc).read_text(encoding="utf-8"),
                     encoding="utf-8")

    ancienne = CONFTEST.RACINE_DU_DEPOT
    try:
        CONFTEST.RACINE_DU_DEPOT = faux
        absentes = CONFTEST._archives_absentes(copie)
    finally:
        CONFTEST.RACINE_DU_DEPOT = ancienne

    assert archive in absentes, (
        f"`{banc}` n'est PAS ecarte alors que `{archive}` manque : il "
        "rougirait a la collecte sur le depot public, et `-x` arreterait la "
        f"porte de release. Lu : {absentes}")


def test_un_banc_qui_NOMME_un_chemin_pour_l_INTERDIRE_n_est_JAMAIS_ecarte():
    """La regression payee le 2026-09-07, et elle allait dans le pire sens.

    La premiere redaction de l'ecart lisait TOUT litteral portant
    `_bmad-output/`. Elle ecartait donc `test_politiques_du_depot.py`, dont la
    frontiere NOMME l'ancien chemin d'`ARCHITECTURE_DETAILED.md` **pour le
    refuser** -- retirant du public la garde qui empeche un chemin perime de
    revenir, c'est-a-dire l'inverse exact de son but.

    Le tri se fait desormais sur la FORME : un lecteur bati un chemin par une
    chaine de `/`, un interdicteur porte un litteral nu. Mesure sur les cinq
    bancs concernes -- 0 joint contre 2 nus d'un cote, 3 a 8 joints et 0 nu de
    l'autre -- et c'est cette separation-la que ce test epingle, sur le cas qui
    l'a payee.
    """
    import sys
    sys.path.insert(0, str(RACINE_DEPOT / "tests"))
    from _chemins_bmad import chemins_construits, chemins_joints

    interdicteur = RACINE_DEPOT / "tests" / "unit" / "test_politiques_du_depot.py"
    source = interdicteur.read_text(encoding="utf-8")

    # **La propriete se mesure sur la FORME, jamais en recopiant le chemin.**
    # Le nommer ici ferait de ce banc-ci un lecteur de l'archive -- c'est ce
    # que les frontieres de perimetre ont refuse a la premiere redaction, et
    # elles avaient raison. On mesure donc ce qui definit un interdicteur :
    # des litteraux nus, et AUCUNE chaine de `/`.
    nus = chemins_construits(source) - chemins_joints(source)
    assert nus, (
        "ce banc ne nomme plus aucun chemin interdit : le cas de regression a "
        "disparu, et ce test ne mesure plus rien")
    assert not chemins_joints(source), (
        "ce banc CONSTRUIT desormais un chemin sous `_bmad-output/` : il n'est "
        f"plus un interdicteur, et l'ecart doit le traiter comme un lecteur "
        f"({sorted(chemins_joints(source))})")
    for interdit in nus:
        assert not (RACINE_DEPOT / interdit).exists(), (
            f"`{interdit}` est revenu sous `_bmad-output/` : la prohibition "
            "n'a plus d'objet, et ce test mesure autre chose qu'il annonce")

    assert CONFTEST._archives_absentes(interdicteur) == [], (
        "le banc qui INTERDIT un chemin est ecarte comme s'il le LISAIT : "
        "la garde disparaitrait du depot public, ou elle compte le plus")


def test_le_registre_DERIVE_n_est_pas_vide_et_nomme_des_bancs_REELS():
    """Une derivation muette vaut une liste fausse : on mesure qu'elle rend.

    Si `PRIVES_ET_LEUR_BANC_EXCLU` se vidait -- ou si l'import silencieux
    rendait un dictionnaire vide --, tous les tests parametres ci-dessus
    seraient SAUTES sans un mot, et l'ecart de la CI publique ne serait plus
    mesure nulle part. Le cas se ferme ici plutot qu'il ne s'espere.
    """
    _exige_le_depot_de_TRAVAIL()

    assert BANCS_A_ARCHIVE_PRIVEE, (
        "le registre derive est vide : les tests parametres qui en dependent "
        "ne mesurent plus rien")
    for banc, archive in sorted(BANCS_A_ARCHIVE_PRIVEE.items()):
        assert (RACINE_DEPOT / banc).is_file(), f"banc inconnu : {banc}"
        assert (RACINE_DEPOT / archive).is_file(), (
            f"`{archive}` est declaree privee et n'existe pas sur le depot de "
            "TRAVAIL : le registre est perime")


@pytest.mark.parametrize("banc", sorted(BANCS_A_ARCHIVE_PRIVEE))
def test_le_HOOK_lui_meme_ecarte_le_banc_et_pas_seulement_son_aide(banc, tmp_path):
    """`N71` : retirer l'appel du hook survivait a tous les tests ci-dessus.

    Ils mesuraient `_archives_absentes`, c'est-a-dire l'AIDE, jamais le geste
    qui compte -- `pytest_ignore_collect` rendant `True`. Un mutant qui
    remplacait son appel par une liste vide restait donc vert pendant que les
    quatre bancs redevenaient collectes, et rougissaient sur le public.

    C'est le motif que la politique du depot nomme depuis la revue 8.8 : « N
    mutants, 0 survivant » mesure la SOLIDITE de ce qui est asserte, jamais
    l'ETENDUE de ce qui ne l'est pas. Ce test-ci mesure l'etendue manquante.
    """
    archive = BANCS_A_ARCHIVE_PRIVEE[banc]
    faux = tmp_path / "depot"
    (faux / "tests" / "unit" / "tui").mkdir(parents=True)
    (faux / Path(archive).parent).mkdir(parents=True, exist_ok=True)
    copie = faux / banc
    copie.write_text((RACINE_DEPOT / banc).read_text(encoding="utf-8"),
                     encoding="utf-8")

    ancienne = CONFTEST.RACINE_DU_DEPOT
    try:
        CONFTEST.RACINE_DU_DEPOT = faux
        verdict = CONFTEST.pytest_ignore_collect(copie, config=None)
    finally:
        CONFTEST.RACINE_DU_DEPOT = ancienne

    assert verdict is True, (
        f"`pytest_ignore_collect` ne rend pas `True` sur `{banc}` alors que "
        f"`{archive}` manque : le banc serait COLLECTE sur le depot public et "
        f"tomberait a l'import. Rendu : {verdict!r}")

    # Et le sens inverse, sur l'arbre REEL : le hook ne doit rien ecarter ici.
    #
    # **La garde porte sur cette CLAUSE seule, et pas sur le test.** Tout ce
    # qui precede se joue dans un faux depot monte sur `tmp_path` : c'est vrai
    # partout, et c'est la moitie qui ferme le mutant `N71`. Elle continue
    # donc de se mesurer sur le depot public. Seule cette derniere ligne
    # asserte l'etat du depot de TRAVAIL, et c'est elle qu'on saute -- sauter
    # le test entier aurait desarme `N71` la ou il vaut le plus cher.
    if porte_l_archive_privee(RACINE_DEPOT, BANCS_A_ARCHIVE_PRIVEE.values()):
        assert CONFTEST.pytest_ignore_collect(RACINE_DEPOT / banc, config=None) in (
            None, False), (
            f"`{banc}` est ecarte sur le depot de TRAVAIL par le hook lui-meme")


def test_le_PREDICAT_de_regime_distingue_DEUX_arbres_fabriques(tmp_path):
    """Le volet symetrique du saut lui-meme, et il ferme le pire des mutants.

    `_exige_le_depot_de_TRAVAIL` protege trois tests. Un garde-fou qui rendrait
    TOUJOURS « ce n'est pas le depot de travail » les ferait tous sauter --
    verts, sautes, et plus rien de mesure --, et **aucun d'eux ne pourrait le
    signaler puisqu'ils sauteraient**. C'est la definition meme du faux vert
    que la politique du depot poursuit, et la circularite est ce qui le rend
    invisible : on ne mesure pas un garde par les tests qu'il garde.

    On le mesure donc sur DEUX arbres FABRIQUES, ou la reponse attendue est
    connue d'avance et ne depend pas du depot ou ce test tourne. Il rougit donc
    des deux cotes -- sur le depot de travail comme sur l'orphelin public.

    Regle des fabriques : deux archives DISTINGUABLES, et le faux depot porte
    la SECONDE seulement, jamais la premiere -- un predicat qui ne regarderait
    que le premier element rendrait faux et passerait pour juste.

    **Les noms fabriques ne portent PAS le prefixe `_bmad-output/`, et ce n'est
    pas un detail de confort.** Premiere redaction : ils le portaient, et
    `test_perimetre_public::test_aucun_banc_ne_lit_un_SIXIEME_chemin_de_bmad_output`
    a rougi sur-le-champ -- son detecteur AST ne distingue pas un chemin
    FABRIQUE sous `tmp_path` d'une vraie lecture d'archive, et il a raison de
    ne pas essayer : c'est le meme noeud. Le predicat mesure ici ne connait
    aucun prefixe, donc la fabrique n'en a pas besoin. C'est la meme lecon que
    le docstring de `_bancs_a_archive_privee` tire d'une recopie : la frontiere
    a puni le raccourci avant qu'il coute quelque chose.
    """
    complet = tmp_path / "travail"
    partiel = tmp_path / "partiel"
    public = tmp_path / "public"
    archives = ("archives-privees/a/premiere.md", "archives-privees/b/seconde.md")

    for racine, portees in ((complet, archives),
                            (partiel, archives[1:]),
                            (public, ())):
        for chemin in portees:
            cible = racine / chemin
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text("archive", encoding="utf-8")
        racine.mkdir(parents=True, exist_ok=True)

    assert porte_l_archive_privee(complet, archives) is True
    assert porte_l_archive_privee(public, archives) is False, (
        "un arbre SANS aucune archive privee doit se reconnaitre comme le "
        "depot public : sinon les trois tests gardes y rougiraient encore")

    # Le cas qui distingue un CARDINAL d'un booleen, et c'est celui qui compte :
    # un registre PARTIELLEMENT perime -- une archive renommee sur le depot de
    # travail -- ne doit PAS sauter, sans quoi le seul test qui l'attrape
    # (`test_le_registre_DERIVE...`) se tairait exactement quand il sert.
    assert porte_l_archive_privee(partiel, archives) is True, (
        "un depot qui porte UNE archive sur deux reste le depot de travail : "
        "l'archive manquante y est un registre perime, pas un autre regime")

    # Et l'aide sous-jacente rend bien LESQUELLES, pas seulement combien.
    assert archives_presentes(partiel, archives) == [archives[1]]


def test_un_depot_SANS_bmad_output_du_tout_n_ecarte_RIEN(tmp_path):
    """`N72` : le garde-fou de l'ancetre survivait, faute d'etre exerce.

    Deux situations que rien ne distinguait sans lui, et elles appellent des
    conduites opposees :

    * `_bmad-output/` existe et l'archive precise MANQUE -- c'est l'orphelin
      public, et le banc doit etre ecarte ;
    * `_bmad-output/` n'existe PAS DU TOUT -- c'est un arbre casse, une sdist,
      un clone partiel. Le banc a d'autres raisons de tomber, et un ecart
      silencieux les masquerait toutes.

    Sans le garde-fou, le second cas ecarte les bancs comme le premier : la
    suite devient verte en ne jouant rien, sur un arbre ou tout manque. C'est
    le pire des faux verts, et aucun test ne le voyait.
    """
    banc = "tests/unit/test_liaison_coeur_vague_3.py"
    faux = tmp_path / "depot"
    (faux / "tests" / "unit").mkdir(parents=True)
    copie = faux / banc
    copie.write_text((RACINE_DEPOT / banc).read_text(encoding="utf-8"),
                     encoding="utf-8")
    assert not (faux / "_bmad-output").exists(), "la fixture doit etre nue"

    ancienne = CONFTEST.RACINE_DU_DEPOT
    try:
        CONFTEST.RACINE_DU_DEPOT = faux
        absentes = CONFTEST._archives_absentes(copie)
        verdict = CONFTEST.pytest_ignore_collect(copie, config=None)
    finally:
        CONFTEST.RACINE_DU_DEPOT = ancienne

    assert absentes == [], (
        "sur un arbre ou `_bmad-output/` n'existe pas DU TOUT, l'ecart se "
        f"declenche et masque un arbre casse : {absentes}")
    assert verdict in (None, False), (
        f"le hook ecarte le banc sur un arbre nu : {verdict!r}")
