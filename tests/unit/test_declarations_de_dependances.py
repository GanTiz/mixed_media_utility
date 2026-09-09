"""Les deux declarations de dependances du depot ne decrivent AUCUN environnement commun.

**La frontiere qui manquait, et ce qu'elle a deja coute.** `EPIC8-ARB-4` a
releve le plafond d'OpenCV dans `pyproject.toml` le 2026-08-31, en commentant la
mesure qui le justifiait, et **n'a jamais ete porte dans `requirements.txt`**.
Rien ne comparait les deux fichiers, donc rien ne l'a dit. Sept mois de
divergence plus tard -- mesure du 2026-09-06 -- l'ecart n'est plus un plafond
perime : les deux epingles sont **contradictoires entre elles**, et l'addition
se paie en 40 rouges environnementaux que deux sessions au moins ont pris pour
des defauts de code.

    ERROR: Cannot install numpy<2 and >=1.24 and opencv-contrib-python==5.0.0.93
    The conflict is caused by:
        The user requested numpy<2 and >=1.24
        opencv-contrib-python 5.0.0.93 depends on numpy>=2

**Ce que ce banc fait, et ce qu'il ne fait PAS.** Il ne tranche pas : le couple
`(opencv, numpy)` que le depot exige est un arbitrage PRODUIT -- il decide quel
poste peut faire tourner le depot --, il appartient a Egan, et il est pose au
registre sous `Q15`. Le banc **epingle** l'inventaire complet des divergences,
motif par motif. Il est donc VERT aujourd'hui, et il rougit le jour ou une
divergence de plus apparait, ou ou l'une des presentes se referme -- dans les
deux cas l'arbitrage se pose au lieu de se perdre, ce qui est exactement ce qui
a manque en aout.

**Et il a deja servi dans le sens de la FERMETURE, le 2026-09-06.** La moitie
`opencv` de `Q15` s'est refermee sans que personne ne l'ait posee comme telle :
`EPIC11-ARB-250` a fait passer l'encodage QR a `segno`, ce qui a retire au
plafond `<4.11` la seule chose qu'il protegeait. Le banc a rougi sur
`fermees`, l'inventaire est passe de SEPT a SIX, et la ligne correspondante de
`Q15` se ferme avec lui. C'est le second `assert` du test d'inventaire -- celui
qu'on ecrit rarement -- qui a rendu ce mouvement visible.

C'est le meme instrument que la section « Les politiques de ce fichier se
MESURENT » de `CLAUDE.md` applique aux regles de travail, porte cette fois sur
une declaration de dependance : **ce qui se mesure se tient ; ce qui se rappelle
se perd.**

**Et il a servi dans le sens de l'OUVERTURE le 2026-09-07, story 8.5.**
L'inventaire passe de SIX a ONZE, et c'est un bon usage de l'instrument plutot
qu'une degradation : la story porte depuis `main` deux renommages de roue
(`opencv-contrib-python` -> `opencv-python-headless`, `PySide6` ->
`PySide6-Essentials`) et n'a pas `requirements.txt` dans son perimetre. Le banc
refuse que ces quatre entrees passent en silence : elles sont au registre, avec
leur motif, appariees deux a deux, et `test_les_DEUX_renommages_de_roue_sont_a_
MOITIE_portes` mesure que chacune est bien un renommage -- memes bornes, deux
noms de roue -- et non une divergence de plafond. Se ferme en deux lignes de
`requirements.txt`, le jour ou une story l'aura dans son perimetre.

**Le depot a par ailleurs DEUX `pyproject.toml` depuis cette meme story** :
la racine (`mmu-cli`) et `packaging/mmu-tui/` (`mmu-tui`). Les deux se lisent,
faute de quoi le deplacement de `textual` et `rich` de l'un vers l'autre
inventerait des divergences que la scission ne cree pas.

--------------------------------------------------------------------------
MUTATIONS JOUEES sur les volets touches par la story 8.5 (2026-09-07 ; arbre
restaure depuis une copie prise avant, jamais par `git checkout`) :

  P1  `declarations_de_pyproject` ne lit que la racine  -> ROUGE (3 tests)
  P2  `DISTRIBUTIONS_DU_DEPOT` videe                    -> ROUGE
  P3  entree `opencv-python-headless` retiree           -> ROUGE (2)
  P4  plafond fautif `<4.11` reepingle                  -> ROUGE
  P5  bornes de `textual` desaccordees cote mmu-tui     -> ROUGE (2)
  P6  `hatchling` retire de l'extra [dev]               -> SURVIVANT ICI, et
      c'est correct : ce banc lit les extras CONFONDUS, donc `[test]` et
      `[full]` suffisent a le voir. Le mutant est tue par
      `test_deux_distributions.py`, qui exige les trois extras nommement
      (mesure rejouee le meme jour : 1 rouge).
  P7  ordre du registre : `rich` remonte en tete        -> ROUGE (2)
  P8  `PySide6-Essentials` remis en `PySide6`           -> ROUGE (2)
--------------------------------------------------------------------------
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE / "src") not in sys.path:
    sys.path.insert(0, str(RACINE / "src"))

REQUIREMENTS = RACINE / "requirements.txt"
PYPROJECT = RACINE / "pyproject.toml"
#: La SECONDE declaration de paquet, depuis la story 8.5 : `mmu-tui`. Le depot
#: en a deux, et les lire toutes les deux n'est pas un raffinement -- ne lire
#: que la racine ferait disparaitre `textual` et `rich` du cote pyproject, donc
#: inventerait deux divergences la ou la scission n'en cree aucune.
PYPROJECT_TUI = RACINE / "packaging" / "mmu-tui" / "pyproject.toml"

#: Les distributions du depot lui-meme : `mmu-tui` depend de `mmu-cli`, et cet
#: arc INTERNE n'a rien a faire dans un inventaire de dependances tierces. Il a
#: son propre banc (`tests/unit/test_deux_distributions.py`).
DISTRIBUTIONS_DU_DEPOT = frozenset({"mmu-cli", "mmu-tui"})

#: Un nom de paquet suivi de ses bornes. Les noms se comparent en minuscules et
#: `-`/`_` confondus : PyPI les normalise ainsi, et un banc qui ne le ferait pas
#: verrait une fausse divergence entre `pytest-qt` et `pytest_qt`.
_NOM_ET_BORNES = re.compile(r"([A-Za-z0-9_.\-]+)(.*)")


def _normalise(nom: str) -> str:
    return nom.lower().replace("_", "-")


def _decoupe(ligne: str) -> tuple[str, str]:
    trouve = _NOM_ET_BORNES.match(ligne.strip())
    assert trouve, f"ligne de dependance illisible: {ligne!r}"
    return _normalise(trouve.group(1)), trouve.group(2).strip()


def declarations_de_requirements() -> dict[str, str]:
    """`requirements.txt`, commentaires et lignes vides retires."""
    trouvees = {}
    for ligne in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        nu = ligne.strip()
        if nu and not nu.startswith("#"):
            nom, bornes = _decoupe(nu)
            trouvees[nom] = bornes
    return trouvees


def declarations_de_pyproject() -> dict[str, str]:
    """Les DEUX `pyproject.toml`, base **et** extras confondus.

    Les extras comptent : `requirements.txt` porte `pytest`, `pytest-qt` et
    Qt, donc il ne se veut pas « runtime seul » -- le comparer a la seule liste
    de base inventerait des divergences qui n'en sont pas.

    Les deux fichiers comptent depuis la story 8.5, et pour la meme raison :
    `textual` et `rich` ont quitte la racine pour `packaging/mmu-tui/`. Ne lire
    que la racine ferait apparaitre `textual` comme « requirements seul » et
    ferait DISPARAITRE l'entree `rich` du registre -- deux mouvements que la
    scission ne produit pas.

    L'arc interne `mmu-cli` est ecarte : ce n'est pas une dependance tierce.
    """
    trouvees: dict[str, str] = {}
    for fichier in (PYPROJECT, PYPROJECT_TUI):
        if not fichier.is_file():
            raise AssertionError(
                f"{fichier} est absent : le depot a DEUX declarations de paquet "
                "depuis la story 8.5, et ce banc n'en lit plus qu'une")
        projet = tomllib.loads(fichier.read_text(encoding="utf-8"))["project"]
        listes = [projet.get("dependencies", [])]
        listes += list(projet.get("optional-dependencies", {}).values())
        for liste in listes:
            for ligne in liste:
                nom, bornes = _decoupe(ligne)
                if nom in DISTRIBUTIONS_DU_DEPOT:
                    continue
                trouvees.setdefault(nom, bornes)
    return trouvees


#: **L'inventaire mesure des divergences, au 2026-09-07 (SIX -> ONZE).** Chaque
#: entree porte son motif, et le motif est une mesure -- pas une supposition.
#:
#: **`opencv-contrib-python` a quitte cette liste le 2026-09-06.** Elle est
#: alignee des deux cotes sur `>=4.10,<6` par `EPIC11-ARB-250` : l'encodage QR
#: etant passe a `segno`, la ligne 4.10 n'est plus fautive dans le seul role
#: qu'OpenCV garde -- detecter et decoder --, donc le plafond `<4.11` n'avait
#: plus rien a proteger et beaucoup a couter. La fermeture se CONSTATE ici,
#: ce qui est exactement ce que le second `assert` du test d'inventaire force.
#:
#: **L'ordre garde une cible a chaque bord**, et les deux bords n'ont PAS bouge
#: le 2026-09-07 : `numpy` -- la seule divergence de BORNES, et la seule qui
#: bloque l'installation -- tient la TETE, `rich` -- la seule dont le paquet est
#: reellement IMPORTE par le code -- tient la queue. Les cinq entrees de la
#: story 8.5 entrent au MILIEU, deliberement : un balayage tronque d'un cote ou
#: de l'autre doit continuer de faire tomber une entree qui compte.
DIVERGENCES = [
    (
        "rich", "pyproject seul",
        "IMPORTE par `tui/jetons.py` (deux fois). Ne pas le declarer ici le "
        "fait dependre de la transitivite de textual -- exactement le "
        "couplage qu'EPIC8-ARB-2 a refuse pour pyproject. C'est la SEULE "
        "entree restante dont le paquet est employe a l'execution, et elle "
        "tient la TETE pour cette raison.",
    ),
    (
        "mutmut", "pyproject seul",
        "Outil de campagne de mutation, extra [dev]. Son absence ici n'empeche "
        "aucun banc de tourner: c'est la divergence la plus benigne du "
        "registre, et elle y est gardee pour que l'inventaire soit COMPLET.",
    ),
    (
        "pytest-xdist", "pyproject seul",
        "Greffon de parallelisme, exige par `scripts/mesure/mesure.py` des "
        "qu'on demande `--parallele`, qui est le DEFAUT depuis le 2026-09-01.",
    ),
    (
        "pytest-timeout", "pyproject seul",
        "`scripts/mesure/mesure.py` REFUSE de lancer sans lui (il teste "
        "`find_spec(\"pytest_timeout\")`). Un conteneur monte depuis ce "
        "fichier-ci ne peut donc pas jouer l'outil de mesure du depot.",
    ),
    (
        "hatchling", "pyproject seul",
        "Backend de construction, deja `[build-system].requires`. Il entre "
        "dans les extras [dev]/[test]/[full] par la story 8.5 : sans lui, la "
        "moitie \u00ab roue \u00bb de `test_deux_distributions.py` -- celle qui mesure "
        "\u00ab zero fichier livre par les deux \u00bb -- sauterait sur un poste "
        "ordinaire, et un banc qui saute partout s'annonce vert.",
    ),
    (
        "ffmpeg-python", "requirements seul",
        "Declare ici et importe NULLE PART: `ffmpeg_utils.py` appelle ffmpeg "
        "par `subprocess`, pas par ce paquet. C'est pyproject qui a raison de "
        "l'omettre -- sa liste se verifie \u00ab DANS LES DEUX SENS \u00bb. Seule "
        "entree de sa FORME, elle tient la QUEUE pour cette raison.",
    ),
]

#: Les trois formes que prend une divergence. Nommees plutot que libres : une
#: quatrieme forme signalerait un mode d'ecart que ce banc ne sait pas lire.
FORMES = {"bornes", "requirements seul", "pyproject seul"}


def test_les_noms_se_comparent_a_la_NORMALISATION_PyPI() -> None:
    """Le repli `_` -> `-` se mesure, sinon il n'existe pas.

    Aujourd'hui aucun nom des deux fichiers ne porte de `_`, donc retirer ce
    repli laisse les neuf cas verts -- mutant `Q8`, mesure SURVIVANT le
    2026-09-06. Il ne se tolere pas : PyPI tient `pytest_qt` et `pytest-qt`
    pour le MEME paquet, et le jour ou l'un des deux fichiers l'ecrirait avec
    un souligne, l'inventaire inventerait deux divergences la ou il n'y en a
    aucune -- puis quelqu'un irait chercher la cause dans les bornes.
    """
    assert _normalise("pytest_qt") == _normalise("pytest-qt") == "pytest-qt"
    assert _normalise("PySide6") == "pyside6"
    assert _normalise("opencv_contrib_python") == "opencv-contrib-python"
    # Et le repli ne va pas trop loin : le point est significatif chez PyPI,
    # il ne se replie pas.
    assert _normalise("ruamel.yaml") == "ruamel.yaml"


def test_l_inventaire_des_divergences_est_EXACT_ni_plus_ni_moins() -> None:
    """Le coeur du banc : exactement celles de `DIVERGENCES`, ni plus ni moins.

    Une divergence de plus fait rougir -- c'est ce qui aurait attrape
    `EPIC8-ARB-4` en aout. Une divergence refermee fait rougir aussi, pour que
    la fermeture se constate au registre au lieu de s'y perimer en silence, et
    c'est ce volet-la qui a joue le 2026-09-06 sur `opencv-contrib-python`.

    Le cardinal n'est deliberement pas ecrit ici : il se lit de `DIVERGENCES`,
    qui porte les motifs. Un nombre recopie dans un docstring est exactement le
    genre de valeur que ce depot retrouve fausse trois revisions plus tard.
    """
    req, pyp = declarations_de_requirements(), declarations_de_pyproject()
    mesurees = set()
    for nom in set(req) - set(pyp):
        mesurees.add((nom, "requirements seul"))
    for nom in set(pyp) - set(req):
        mesurees.add((nom, "pyproject seul"))
    for nom in set(req) & set(pyp):
        if req[nom] != pyp[nom]:
            mesurees.add((nom, "bornes"))

    attendues = {(nom, forme) for nom, forme, _ in DIVERGENCES}
    neuves = mesurees - attendues
    fermees = attendues - mesurees
    assert not neuves, (
        f"divergence NEUVE entre requirements.txt et pyproject.toml: "
        f"{sorted(neuves)}. Elle se porte au registre avec son motif MESURE, "
        "ou elle se referme -- elle ne se laisse pas passer.")
    assert not fermees, (
        f"divergence REFERMEE: {sorted(fermees)}. Retirer son entree de "
        "DIVERGENCES, et fermer la ligne correspondante de Q15.")


def test_les_DEUX_renommages_de_roue_sont_PORTES_des_deux_cotes() -> None:
    """Ce test s'appelait `..._sont_a_MOITIE_portes`, et il l'a ete deux fois.

    Il a d'abord mesure l'alignement d'OpenCV obtenu le 2026-09-06 ; la story
    8.5 l'a ROUVERT en portant depuis `main` deux renommages de ROUE que
    `requirements.txt`, hors de son perimetre, n'a pas suivis ; il mesure
    maintenant leur fermeture, faite le 2026-09-07 dans le meme mouvement que
    l'alignement de `numpy`.

    **Ce qu'il continue d'interdire, et qui est le fond de l'affaire** : le
    retour du plafond `<4.11`, c'est-a-dire de la ligne dont l'ENCODEUR rendait
    un symbole malforme au-dela de la version 7
    (`mesure-2026-09-06-plancher-opencv-et-rendu-qr.md`). C'est la seule chose
    que la fermeture du 2026-09-06 protegeait vraiment, et elle reste protegee
    a travers les deux changements de nom.

    **Et ce qu'il interdit desormais en plus** : le retour des ANCIENS noms.
    Une frontiere negative, parce qu'aucun test positif ne verrait revenir
    `opencv-contrib-python` -- tout continuerait de s'installer et de marcher,
    seulement plus lourd, et illisible sur une machine sans affichage.
    """
    req, pyp = declarations_de_requirements(), declarations_de_pyproject()

    # Renommage 1 -- la roue d'OpenCV. Meme paquet, memes bornes, des deux cotes.
    assert req["opencv-python-headless"] == pyp["opencv-python-headless"] == ">=4.10,<6"
    assert "opencv-contrib-python" not in req
    assert "opencv-contrib-python" not in pyp
    assert "opencv-python" not in req and "opencv-python" not in pyp, (
        "la roue AVEC fenetres n'est declaree par aucun des deux fichiers : "
        "elle est posee a l'installation, quand un affichage est detecte "
        "(EPIC8-ARB-15), jamais comme dependance")

    # Renommage 2 -- Qt. Meme paquet, memes bornes, des deux cotes.
    assert req["pyside6-essentials"] == pyp["pyside6-essentials"] == ">=6.8,<6.9"
    assert "pyside6" not in req
    assert "pyside6" not in pyp

    # Le plafond fautif ne revient par aucun des deux chemins.
    for nom, table in (("requirements.txt", req), ("pyproject", pyp)):
        for paquet, bornes in table.items():
            if paquet.startswith("opencv"):
                assert "<4.11" not in bornes, (
                    f"{nom} reepingle `{paquet}{bornes}` : c'est la ligne dont "
                    "l'encodeur QR rend un symbole malforme au-dela de la "
                    "version 7, donc chaque planche imprimee est perdue")


def test_l_epingle_de_NUMPY_est_ALIGNEE_et_ne_se_rouvre_pas() -> None:
    """La seconde moitie de Q15 est fermee le 2026-09-07, et voici pourquoi.

    Ce banc affirmait `req["numpy"] == ">=1.24,<2"` et `pyp["numpy"] == ">=2.0"`,
    et documentait patiemment que les deux declarations ne decrivaient AUCUN
    environnement commun. C'est precisement ce qui la separe des autres entrees
    du registre : une divergence de perimetre (`mutmut` absent d'un cote) decrit
    deux environnements differents ; celle-la n'en decrivait aucun. Un
    `pip install -r requirements.txt` suivi d'un `pip install -e .` se
    contredisait, dans les deux ordres.

    Ce n'etait donc pas un arbitrage produit en attente -- c'etait un defaut, et
    il se corrige plutot qu'il ne se tranche. La borne de `pyproject.toml` fait
    foi : c'est elle que les roues publiees portent.

    NEGATIVE : elle rougit si l'une des deux reprend une borne que l'autre
    exclut. Le premier `assert` seul laisserait passer un futur `<3` pose d'un
    seul cote.
    """
    req, pyp = declarations_de_requirements(), declarations_de_pyproject()
    assert req["numpy"] == pyp["numpy"] == ">=2.0", (
        f"numpy diverge de nouveau : requirements {req['numpy']!r} contre "
        f"pyproject {pyp['numpy']!r}")

    from packaging.specifiers import SpecifierSet
    ici, la_bas = SpecifierSet(req["numpy"]), SpecifierSet(pyp["numpy"])
    communes = [v for v in ("1.24.0", "1.26.4", "2.0.0", "2.4.6")
                if v in ici and v in la_bas]
    assert communes, (
        "les deux declarations ne decrivent aucun environnement commun -- "
        "c'est le defaut exact que le 2026-09-07 a ferme")


def test_segno_est_ALIGNE_des_deux_cotes_des_son_entree() -> None:
    """La dependance neuve entre ALIGNEE, et c'est un geste, pas une chance.

    `EPIC8-ARB-4` est entre dans `pyproject.toml` sans etre porte ici, et c'est
    ce qui a fabrique la divergence que ce banc existe pour mesurer. `segno`
    entre le 2026-09-06 dans les DEUX fichiers, avec la MEME borne, dans le
    meme commit -- meme discipline qu'un identifiant de regle pose avec sa
    regle. Sans ce test, une huitieme divergence pourrait naitre du geste meme
    qui referme la premiere.
    """
    req, pyp = declarations_de_requirements(), declarations_de_pyproject()
    assert "segno" in req, "segno absent de requirements.txt: plus rien n'encode de QR"
    assert "segno" in pyp, "segno absent de pyproject.toml: `pip install mmu-tui` casse"
    assert req["segno"] == pyp["segno"] == ">=1.6,<2"


def test_rich_est_IMPORTE_et_absent_de_requirements() -> None:
    """La divergence qui n'est pas qu'une question de plafond.

    `pyproject` declare `rich` explicitement plutot que de le tenir de textual
    (`EPIC8-ARB-2`). `requirements.txt`, lui, le tient de textual sans le dire
    -- et la borne `textual<9` ne protege en rien des dependances que textual
    choisit, ce que l'arbitrage dit deja mot pour mot.
    """
    jetons = (RACINE / "src" / "mixed_media_utility" / "tui" / "jetons.py")
    source = jetons.read_text(encoding="utf-8")
    assert "from rich" in source, (
        "rich n'est plus importe: la divergence change de nature, le registre "
        "est a relire")
    assert "rich" in declarations_de_pyproject()
    assert "rich" not in declarations_de_requirements()


def test_ffmpeg_python_n_est_importe_NULLE_PART() -> None:
    """La divergence en sens INVERSE, et c'est ce qui rend l'inventaire honnete.

    Six des sept divergences sont des manques de `requirements.txt`. Celle-ci
    est un EXCES : il declare un paquet que le code n'importe pas. Sans elle,
    on lirait l'inventaire comme « pyproject a raison partout », ce qui est
    faux dans le detail meme si c'est vrai sur le couple bloquant.
    """
    paquet = RACINE / "src" / "mixed_media_utility"
    fautifs = [
        chemin.relative_to(RACINE)
        for chemin in paquet.rglob("*.py")
        if re.search(r"^\s*(import ffmpeg\b|from ffmpeg\b)",
                     chemin.read_text(encoding="utf-8"), re.MULTILINE)
    ]
    assert not fautifs, (
        f"ffmpeg-python est desormais importe ({fautifs}): il doit alors "
        "entrer dans pyproject, et cette entree du registre change de motif")
    assert "ffmpeg-python" in declarations_de_requirements()
    assert "ffmpeg-python" not in declarations_de_pyproject()


def test_mesure_py_REFUSE_de_partir_sans_un_greffon_absent_d_ici() -> None:
    """La divergence qui casse l'outil que `CLAUDE.md` rend obligatoire.

    « Toute suite de tests longue se lance par `scripts/mesure/mesure.py` ».
    Or il teste la presence de `pytest_timeout` et refuse sans lui, et ce
    greffon n'est pas dans `requirements.txt`. Un conteneur monte depuis ce
    seul fichier ne peut donc pas jouer la mesure que la politique exige.
    """
    outil = (RACINE / "scripts" / "mesure" / "mesure.py").read_text(encoding="utf-8")
    assert "pytest_timeout" in outil, (
        "mesure.py ne verifie plus le greffon: le motif de cette entree change")
    assert "pytest-timeout" not in declarations_de_requirements()
    assert "pytest-timeout" in declarations_de_pyproject()


def test_le_registre_est_bien_FORME_et_ses_deux_bords_portent_une_cible() -> None:
    """La regle des fabriques, appliquee au registre lui-meme.

    Des entrees DISTINGUABLES -- nom, forme et motif differents --, et une cible
    a CHAQUE BORD. Un balayage tronque d'un cote ou de l'autre doit faire tomber
    precisement ce qu'on surveille, jamais une entree benigne.

    **Les bords ont change deux fois.** Ils portaient d'abord les deux
    divergences de BORNES ; la fermeture d'`opencv` le 2026-09-06 en a laisse
    une, `numpy`, qui a pris la tete. La fermeture de `numpy` le 2026-09-07 la
    retire a son tour, avec les quatre moities de renommage. Les bords sont
    donc desormais `rich` en TETE -- la seule entree dont le paquet est
    reellement IMPORTE par le code, donc la seule dont l'oubli se paierait a
    l'execution -- et `ffmpeg-python` en QUEUE -- la seule de sa FORME, donc
    celle dont la disparition ferait perdre au registre un mode d'ecart
    entier. Deux cibles qui comptent, pour deux raisons differentes.

    Le cardinal n'est pas ecrit en dur : c'est le test d'inventaire qui le tient
    contre la mesure. L'ecrire deux fois ferait de ce test-ci un second endroit
    a corriger a chaque mouvement, donc un endroit qu'on oublie.
    """
    noms = [nom for nom, _, _ in DIVERGENCES]
    assert len(set(noms)) == len(noms), noms
    assert len(noms) >= 3, "un registre a moins de trois entrees n'a plus de bords"
    assert DIVERGENCES[0][0] == "rich", noms
    assert DIVERGENCES[-1][0] == "ffmpeg-python", noms
    assert DIVERGENCES[-1][1] == "requirements seul", (
        "la queue doit porter la seule entree de sa forme : c'est elle dont la "
        "disparition ferait perdre au registre un mode d'ecart entier")
    # **L'assertion qui vivait ici disait `"opencv-contrib-python" not in noms`**,
    # et son motif etait juste : le retour d'opencv au registre aurait signale
    # que `requirements.txt` reepinglait la ligne fautive `<4.11`. Le 2026-09-07
    # opencv EST revenu au registre sans que rien de fautif ne revienne -- c'est
    # un renommage de roue, memes bornes des deux cotes. Un nom ne mesure donc
    # pas ce que cette assertion croyait mesurer ; le PLAFOND, si. Il est
    # desormais mesure sur les bornes, dans
    # `test_les_DEUX_renommages_de_roue_sont_a_MOITIE_portes`, des deux cotes et
    # sur tout paquet dont le nom commence par `opencv`.
    #
    # Ce qui reste ici est la forme du registre : les renommages entrent PAR
    # PAIRE, une moitie de chaque cote. Une paire depareillee voudrait dire
    # qu'un renommage s'est referme a moitie, ce qui est pire que l'ecart
    # complet -- les deux fichiers installeraient alors le meme paquet sous
    # deux noms.
    formes_par_nom = {nom: forme for nom, forme, _ in DIVERGENCES}
    for ancienne, neuve in (("opencv-contrib-python", "opencv-python-headless"),
                            ("pyside6", "pyside6-essentials")):
        presentes = [n for n in (ancienne, neuve) if n in formes_par_nom]
        assert len(presentes) in (0, 2), (
            f"renommage a moitie referme : {presentes} seul(e) au registre")
        if presentes:
            assert formes_par_nom[ancienne] == "requirements seul"
            assert formes_par_nom[neuve] == "pyproject seul"
    # Toute forme employee doit etre une forme CONNUE -- une quatrieme
    # signalerait un mode d'ecart que ce banc ne sait pas lire.
    #
    # **L'assertion vivait ici en `== FORMES`**, et son motif etait bon : un
    # registre qui ne porterait qu'une forme ne mesurerait qu'un mode d'ecart.
    # Elle est devenue fausse le 2026-09-07, quand `numpy` -- derniere
    # divergence de BORNES -- s'est refermee. Exiger qu'une forme reste
    # representee, c'est exiger qu'un defaut reste ouvert : le registre aurait
    # empeche sa propre fermeture. On mesure donc l'inclusion, et le nombre de
    # formes VIVANTES est dit plutot que contraint.
    formes = {forme for _, forme, _ in DIVERGENCES}
    assert formes <= FORMES, f"forme inconnue au registre : {formes - FORMES}"
    assert len(formes) >= 2, (
        "il ne reste qu'un seul mode d'ecart au registre : verifier que c'est "
        f"bien ce que la mesure dit, et non un balayage tronque. Formes : {formes}")
    # Et chaque motif dit quelque chose : une entree sans motif serait une
    # tolerance muette, ce que ce depot appelle un finding enterre.
    for nom, _, motif in DIVERGENCES:
        assert len(motif) >= 60, nom


#: **`pyside6` a quitte cette liste le 2026-09-07** : il n'est plus declare des
#: deux cotes, `pyproject.toml` portant `PySide6-Essentials`. Il est remplace
#: par `segno`, temoin d'un accord POSE volontairement dans le meme commit
#: (2026-09-06) plutot que subi -- ce qui en fait un meilleur temoin.
#:
#: `textual` reste, et il vaut la peine d'etre dit : il a change de FICHIER
#: (racine -> `packaging/mmu-tui/`) sans changer de borne. C'est la preuve que
#: la scission en deux distributions n'a fabrique aucune divergence.
@pytest.mark.parametrize("nom, bornes", [
    pytest.param("textual", ">=8.2,<9", id="textual"),
    pytest.param("segno", ">=1.6,<2", id="segno"),
    pytest.param("pytest-qt", ">=4.4", id="pytest-qt"),
])
def test_ce_qui_est_declare_DES_DEUX_COTES_porte_les_MEMES_bornes(
    nom: str, bornes: str
) -> None:
    """Le volet symetrique, sans lequel l'inventaire ne dirait rien.

    Un banc qui ne mesurerait que les divergences serait vert sur deux
    fichiers integralement divergents. Ces trois-la sont declares des deux
    cotes avec la meme borne, et doivent le rester : ce sont les temoins que
    l'accord EST possible et qu'il tient ailleurs.
    """
    req, pyp = declarations_de_requirements(), declarations_de_pyproject()
    assert req[nom] == bornes, nom
    assert pyp[nom] == bornes, nom
