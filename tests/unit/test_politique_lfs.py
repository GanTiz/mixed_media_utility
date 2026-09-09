# -*- coding: utf-8 -*-
"""La politique Git LFS du depot, mesuree plutot que rappelee.

**Ce que cette frontiere ferme, et le prix en est chiffre.** Le quota gratuit
de bande passante LFS de GitHub -- **10 Go par mois**, identique pour un depot
public et un depot prive -- a ete epuise en DEUX JOURS, du 2026-09-01 au
2026-09-03. Deux causes, mesurees :

* **`lfs: true` dans `actions/checkout`**, present sur ONZE branches. Il tire
  tout le LFS de la branche : **718 Mo mesures sur `main`**. Il avait ete pose
  pour obtenir UN fichier de 2,9 Mo (`tests/TEST_FILE.mp4`) -- un facteur 247.
  Quatorze runs suffisent a epuiser 10 Go ; il y en a eu 231 ;
* **`.gitattributes` par EXTENSION**, qui envoyait `*.pdf` et `*.mp4` en LFS ou
  qu'ils soient. Une fixture mp4 de 2,1 Ko et une planche PDF de 70 Ko y
  etaient, et chaque clone les payait.

**Deuxieme passe, le meme jour, sur arbitrage d'Egan** : `projects/` n'est plus
versionne du tout. Il portait **97 % du volume LFS** (2 217 Mo sur 2 291) et
**aucun test ne le lisait**. Verbatim : « c'est un dossier qui a vocation a
rester local, tout fichier qui devra etre partage devra passer par `tests/` ».

**Pourquoi une frontiere et non un commentaire.** Les reglages fautifs sont ceux
que tout le monde pose par defaut : `lfs: true` parce qu'« il faut bien le
LFS », `*.pdf` parce qu'« un PDF c'est lourd ». Ils se reintroduisent en une
ligne, par un agent de bonne foi, et rien ne le signale avant la facture
suivante. Ce qui se mesure se tient ; ce qui se rappelle se perd.

**Le piege que ce banc doit eviter lui-meme** : le commentaire de `ci.yml` CITE
`lfs: true` en toutes lettres pour expliquer son retrait. Un `grep` sur le
texte brut rougirait sur sa propre explication. La lecture se fait donc sur le
YAML ANALYSE, jamais sur le fichier entier -- meme regle que
`test_declenchement_des_workflows.py`, et pour le meme motif.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
WORKFLOWS = RACINE / ".github" / "workflows"

#: Les seuls arbres dont les fichiers ont droit au LFS, depuis le 2026-09-03.
#: Tout ce qui doit etre PARTAGE passe par `tests/` ; ce qui reste local n'est
#: pas versionne du tout.
PREFIXES_LFS_AUTORISES = ("tests/",)

#: L'arbre qui ne doit plus etre versionne DU TOUT, ni en LFS ni en clair.
ARBRE_LOCAL = "projects/"

#: Ce qui DOIT descendre a chaque clone, parce qu'un banc le lit. Le reste du
#: LFS peut rester en pointeur sans qu'aucune mesure en souffre.
AUTO_TELECHARGES = ("tests/TEST_FILE.mp4", "tests/fixtures/scans/")

#: L'arbre lourd : versionne et partageable, mais PAS tire par defaut. C'est la
#: que le « seuil » s'exprime -- git n'apparie que des chemins, jamais des
#: tailles, donc un seuil ne peut vivre que dans le choix de ce qui descend.
ARBRES_LOURDS = ("tests/fixtures/lots/", "tests/fixtures/rushes/reels/")

#: Conserve pour les tests qui n'en visent qu'un ; c'est le plus gros.
ARBRE_LOURD = ARBRES_LOURDS[0]

#: Au-dela, un fichier hors LFS grossit le depot pour toujours -- git ne sait
#: pas oublier un blob. GitHub avertit a 50 Mo et refuse a 100 Mo ; 5 Mo est le
#: seuil ou la question merite d'etre posee, pas celui ou ca casse.
SEUIL_DE_QUESTION_OCTETS = 5 * 1024 * 1024


def _workflows():
    return sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


def _charge(chemin: Path) -> dict:
    """Le workflow ANALYSE, et l'absence de PyYAML fait ROUGIR, jamais sauter.

    **Ce que ce changement ferme, et c'etait un defaut MESURE de ce banc.**
    Cette fonction faisait `pytest.importorskip("yaml")`, et PyYAML n'etait
    declare NULLE PART : ni dans `requirements.txt`, ni dans
    `requirements-dev.txt`, ni dans les extras `[test]` / `[dev]` / `[full]` de
    `pyproject.toml`. Mesure du 2026-09-08, fermeture transitive de `.[test]`
    resolue par `pip install --dry-run --ignore-installed` -- 26 paquets,
    et PyYAML n'en fait pas partie :

        attrs, charset-normalizer, execnet, hatchling, iniconfig, jsonschema,
        jsonschema-specifications, mmu-cli, numpy, opencv-python-headless,
        packaging, pathspec, pillow, pluggy, pygments, pypdfium2, pytest,
        pytest-timeout, pytest-xdist, referencing, reportlab, rpds-py, segno,
        tomlkit, trove-classifiers, typing_extensions

    (`--ignore-installed` est ce qui rend la mesure valable : sans lui, pip ne
    liste que ce qu'il AJOUTERAIT, et PyYAML etant present dans le conteneur
    de session par `conan` et `libcst`, la mesure aurait ete vraie pour une
    mauvaise raison.)

    La CI construit son environnement par `pip install -e .[test]` puis
    `pip install -e ./packaging/mmu-tui` (rich, textual) : `import yaml` y
    echouait, donc les QUATRE frontieres de la section 1 de ce banc --
    **dont celle qui interdit `lfs: true`** -- SAUTAIENT en CI. Vertes ici,
    muettes la-bas : exactement l'ecart que CLAUDE.md decrit, « un test vert
    d'un cote et saute de l'autre ne figure dans aucune des deux listes de
    rouges ». Une politique qui a coute 10 Go de bande passante en deux jours
    n'etait donc gardee, la ou elle mord, par rien.

    Le remede est en deux moities, et la seconde est celle-ci. La premiere est
    la declaration de `pyyaml` dans l'extra `[test]` de `pyproject.toml`. Mais
    une declaration se retire aussi facilement qu'elle s'ajoute, et un
    `importorskip` la laisserait se retirer EN SILENCE -- le banc redeviendrait
    muet sans qu'une seule ligne rougisse. Le saut est donc remplace par un
    echec qui NOMME son remede : jamais un blocage sec, mais jamais un silence
    non plus.

    Pourquoi ce banc lit le YAML analyse la ou les trois autres bancs de
    workflow du depot l'analysent par indentation : le commentaire de
    `ci.yml` CITE `lfs: true` en toutes lettres pour expliquer son retrait, et
    la question posee ici -- « ce `with:` porte-t-il la valeur booleenne
    vraie ? » -- porte sur une VALEUR typee, pas sur la presence d'un texte.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover - mesure par le banc de vivacite
        pytest.fail(
            "PyYAML est absent : les quatre frontieres de la section 1 de ce "
            "banc ne mesurent plus rien, dont celle qui interdit `lfs: true`. "
            "Ce n'est pas un saut admissible -- c'est ce banc-ci qui garde une "
            "politique dont l'oubli a coute 10 Go de bande passante en deux "
            "jours. Remede : `pip install -e .[test]`, ou reintroduire "
            "`pyyaml` dans l'extra [test] de pyproject.toml s'il en a "
            "disparu.")
    return yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}


def _etapes(workflow: dict):
    for job in (workflow.get("jobs") or {}).values():
        for etape in (job or {}).get("steps") or []:
            yield etape


def _exclusions() -> list[str]:
    """Les motifs de `fetchexclude`, commentaires exclus."""
    actif = [l.strip() for l in
             (RACINE / ".lfsconfig").read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    motifs = []
    for ligne in (l for l in actif if l.startswith("fetchexclude")):
        motifs += [m.strip() for m in ligne.split("=", 1)[1].split(",")]
    return motifs


def _suivis() -> list[str]:
    """Les chemins suivis par git, ou un saut si l'on n'est pas dans un depot."""
    sortie = subprocess.run(["git", "ls-files", "-z"], cwd=RACINE,
                            capture_output=True, text=True)
    if sortie.returncode != 0:
        pytest.skip("hors depot git : rien a mesurer")
    return [n for n in sortie.stdout.split("\0") if n]


# --------------------------------------------------------------------------
# 1. Aucun checkout ne tire le LFS en entier
# --------------------------------------------------------------------------

#: Ce que GitHub Actions tient pour VRAI dans un `with:`. Toutes les entrees
#: d'une action sont des CHAINES cote runner : `lfs: true` et `lfs: 'true'`
#: arrivent identiques a `actions/checkout`, qui compare a la chaine "true"
#: sans distinguer laquelle des deux a ete ecrite. `yaml.safe_load`, lui, les
#: distingue -- le premier devient le booleen, le second reste une chaine.
_VALEURS_VRAIES_POUR_ACTIONS = {"true", "yes", "on", "1"}


def _active_le_lfs(valeur) -> bool:
    """Ce `with.lfs` fait-il tirer tout le LFS, tel que le runner le lira ?

    DEFAUT MESURE ET FERME le 2026-09-08 (revue 8.10, couche 3). Cette garde
    testait `is True`, c'est-a-dire le BOOLEEN que `yaml.safe_load` construit
    a partir de `lfs: true` sans guillemets. Or **`lfs: 'true'` entre
    guillemets active le LFS a l'identique cote GitHub** -- toutes les entrees
    d'une action y sont des chaines -- pendant que `is True` rend faux. La
    frontiere qui garde une politique payee 10 Go de bande passante se
    contournait donc en ajoutant deux apostrophes.

    L'ecart etait invisible parce que l'AC8 de la story avait recopie
    l'IMPLEMENTATION de la garde (« elle teste `is True` ») au lieu de la
    REGLE qu'elle est censee tenir (« aucun `actions/checkout` ne porte
    `lfs: true` ») -- et une implementation citee comme specification ne se
    relit plus. Meme forme de defaut que sur la story 8.9.

    On lit donc la valeur comme le RUNNER la lira, pas comme le parseur YAML
    la type : `True`, `"true"`, `"True"`, `"yes"`, `"on"`, `"1"` sont tous des
    fautifs. `False`, `"false"`, la clef absente et une expression `${{ ... }}`
    ne le sont pas -- pour la derniere, le verdict appartiendrait au runner et
    ce banc ne peut pas l'evaluer ; elle est traitee a part par la frontiere
    suivante.
    """
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, str):
        return valeur.strip().lower() in _VALEURS_VRAIES_POUR_ACTIONS
    return False


def test_aucun_workflow_ne_tire_TOUT_le_LFS_au_checkout():
    """FRONTIERE NEGATIVE : c'est le reglage qui a coute les 10 Go.

    Lu sur le YAML analyse, jamais sur le texte : le commentaire de `ci.yml`
    cite `lfs: true` pour expliquer son retrait, donc un `grep` rougirait sur
    sa propre explication.

    Mais la valeur se juge comme le RUNNER la lit, pas comme le parseur la
    type -- voir `_active_le_lfs`. Un `lfs: 'true'` entre guillemets passait
    ici jusqu'au 2026-09-08.
    """
    fautifs = []
    for chemin in _workflows():
        for etape in _etapes(_charge(chemin)):
            uses = str(etape.get("uses") or "")
            if not uses.startswith("actions/checkout"):
                continue
            if _active_le_lfs((etape.get("with") or {}).get("lfs")):
                fautifs.append(f"{chemin.name}: {etape.get('name') or uses}")
    assert not fautifs, (
        "`lfs: true` tire tout le LFS de la branche (718 Mo sur main) la ou un "
        "`git lfs pull --include=<chemin>` en tire 2,9 Mo : " + "; ".join(fautifs))


def test_la_lecture_du_drapeau_LFS_juge_comme_le_RUNNER_pas_comme_le_PARSEUR():
    """La frontiere de la frontiere : les six ecritures qui activent le LFS.

    Sans ce test, `_active_le_lfs` pourrait retomber sur `is True` sans qu'une
    ligne rougisse -- et c'est exactement l'etat d'avant le 2026-09-08, ou
    deux apostrophes suffisaient a contourner la garde.

    Les deux sens sont joues, comme l'exige la regle « une garde fait varier
    le drapeau dont elle depend » : six ecritures VRAIES et six FAUSSES.
    """
    vraies = [True, "true", "True", "TRUE", "yes", "on", "1"]
    fausses = [False, "false", "False", "no", "off", "0", None, "", "  "]

    actives = [v for v in vraies if not _active_le_lfs(v)]
    assert not actives, (
        "ces ecritures activent le LFS chez GitHub et la garde ne les voit "
        f"pas : {actives!r}")

    inertes = [v for v in fausses if _active_le_lfs(v)]
    assert not inertes, (
        "ces ecritures n'activent PAS le LFS et la garde les accuse a tort, "
        f"ce qui la rendrait bruyante donc contournee : {inertes!r}")


def test_le_seul_objet_LFS_dont_la_CI_a_besoin_est_tire_PAR_CHEMIN():
    """Le pendant POSITIF du test precedent.

    Sans lui, retirer `lfs: true` et ne rien mettre a la place passerait le banc
    tout en cassant `test_aller_retour_nominal_sur_le_rush_reel` -- une frontiere
    qui n'attraperait qu'une moitie du geste serait pire qu'aucune.
    """
    ci = WORKFLOWS / "ci.yml"
    if not ci.exists():
        # Une branche anterieure a la CI n'a rien a materialiser. Le SAUT est
        # structurel -- il tient a l'absence du fichier, pas a un drapeau qu'on
        # pourrait oublier de rallumer -- et la frontiere precedente reste vraie
        # sans lui : zero workflow porte zero `lfs: true`.
        pytest.skip("pas de .github/workflows/ci.yml sur cette branche")
    commandes = " ".join(str(e.get("run") or "") for e in _etapes(_charge(ci)))
    assert "git lfs pull" in commandes, (
        "ci.yml ne materialise plus aucun objet LFS : "
        "tests/TEST_FILE.mp4 restera un pointeur de 132 octets.")
    assert "--include=" in commandes, (
        "un `git lfs pull` SANS `--include` tire tout : c'est `lfs: true` par "
        "un autre chemin.")
    assert "tests/TEST_FILE.mp4" in commandes


def _commandes_de_ci_sans_commentaires(ci: Path) -> str:
    """Les lignes de commande des etapes de `ci.yml`, COMMENTAIRES RETIRES.

    Ce detail est la frontiere elle-meme, et il a ete paye : la premiere
    redaction joignait le texte brut des `run:`, si bien qu'elle etait
    satisfaite par le COMMENTAIRE qui explique la commande plutot que par la
    commande. Mesure le 2026-09-08 : le mutant `L1` -- remplacer l'`--include`
    par un autre chemin -- laissait le banc VERT, parce que le commentaire
    au-dessus nommait encore les deux arbres.

    C'est la meme famille que `_job_de_construction_de_ci` dans
    `test_deux_distributions.py`, ou un `python -m build` cite en commentaire
    s'etait fait accuser.
    """
    lignes = []
    for etape in _etapes(_charge(ci)):
        for ligne in str(etape.get("run") or "").splitlines():
            nue = ligne.split("#", 1)[0]
            if nue.strip():
                lignes.append(nue)
    return " ".join(lignes)


def test_la_CI_materialise_CHAQUE_arbre_de_tests_que_lfsconfig_EXCLUT():
    """Ce que `fetchexclude` retire au clone humain, la CI doit le reprendre.

    `fetchexclude` est une politique de BANDE PASSANTE, pas une declaration que
    personne n'a besoin de ces objets : `tests/fixtures/lots/**` (178 Mo) et
    `tests/fixtures/rushes/reels/**` (64 Mo) sont lus par trois bancs, et
    `EPIC11-ARB-241` interdit de les faire sauter -- un pointeur ROUGIT. Sur le
    run 34200882803 les trois etaient rouges sur les TROIS jobs, et rien dans
    le depot ne le disait avant que la CI ne le rende.

    La liste n'est pas recopiee : elle est DERIVEE de `.lfsconfig`, si bien
    qu'une exclusion ajoutee demain sans que la CI suive fait rougir ici.
    `projects/**` est hors sujet -- il n'est plus versionne et aucun banc ne le
    lit --, donc seul ce qui est sous `tests/` est exige.
    """
    ci = WORKFLOWS / "ci.yml"
    if not ci.exists():
        pytest.skip("pas de .github/workflows/ci.yml sur cette branche")
    exclus_de_tests = [m for m in _exclusions() if m.startswith("tests/")]

    # Le volet d'anti-vacuite : si `.lfsconfig` cessait d'exclure quoi que ce
    # soit sous `tests/`, la boucle ci-dessous serait vide et le banc vrai pour
    # toujours -- exactement la forme de frontiere morte que ce fichier chasse.
    assert exclus_de_tests, (
        ".lfsconfig n'exclut plus rien sous tests/ : ce banc ne mesure plus "
        "rien, il est a retirer ou a reecrire, pas a laisser vert.")

    commandes = _commandes_de_ci_sans_commentaires(ci)
    for motif in exclus_de_tests:
        assert motif in commandes, (
            f"`{motif}` est exclu du fetch par .lfsconfig et la CI ne le "
            "materialise nulle part : les bancs qui le lisent y verront des "
            "pointeurs, et ils rougiront sans que rien n'en donne la cause.")


def test_le_pull_des_arbres_exclus_porte_son_EXCLUSION_VIDE():
    """Le volet symetrique, et il porte sur la seule chose qui puisse etre MUETTE.

    `--include` ne remplace que `fetchinclude` : `fetchexclude` continue de
    s'appliquer par-dessus depuis `.lfsconfig`, si bien qu'un chemin nomme dans
    les deux reste exclu. Mesure du 2026-09-07 (git-lfs 3.4.1) : sans
    `--exclude=""`, 0,04 s et RIEN ; avec, 15,2 s et 243 Mo. Et les deux
    sorties sont IDENTIQUES -- c'est pour ca que ca se mesure ici plutot que de
    se voir au run.
    """
    ci = WORKFLOWS / "ci.yml"
    if not ci.exists():
        pytest.skip("pas de .github/workflows/ci.yml sur cette branche")
    exclus_de_tests = [m for m in _exclusions() if m.startswith("tests/")]
    assert exclus_de_tests, "voir le banc precedent : rien a mesurer"

    for etape in _etapes(_charge(ci)):
        commande = "\n".join(
            nue for ligne in str(etape.get("run") or "").splitlines()
            if (nue := ligne.split("#", 1)[0]).strip())
        if not any(motif in commande for motif in exclus_de_tests):
            continue
        if "git lfs pull" not in commande:
            continue
        assert '--exclude=""' in commande, (
            "un `git lfs pull --include=` qui nomme un arbre EXCLU sans "
            '`--exclude=""` ne tire rien, et ne le dit pas.')


# --------------------------------------------------------------------------
# 2. Le LFS est scope par CHEMIN, et seulement sous tests/
# --------------------------------------------------------------------------

def _regles_lfs() -> list[str]:
    """Les motifs de `.gitattributes` qui envoient en LFS, commentaires exclus."""
    texte = (RACINE / ".gitattributes").read_text(encoding="utf-8")
    return [l.split()[0] for l in (x.strip() for x in texte.splitlines())
            if l and not l.startswith("#") and "filter=lfs" in l]


def test_aucune_regle_LFS_ne_vaut_pour_TOUT_le_depot():
    """FRONTIERE NEGATIVE : `*.pdf` est le motif qui a mis 2,1 Ko en LFS.

    Une extension ne dit rien de la taille. Le depot en portait les deux
    extremes : une fixture mp4 de 2,1 Ko et un rush de 67 Mo, meme extension.
    """
    trop_larges = [m for m in _regles_lfs()
                   if not m.startswith(PREFIXES_LFS_AUTORISES)]
    assert not trop_larges, (
        "ces motifs envoient en LFS hors de `tests/`, donc par extension "
        "seule : " + ", ".join(trop_larges))


def test_les_medias_LOURDS_de_tests_sont_bien_couverts():
    """Le pendant POSITIF : scoper ne doit pas revenir a tout desactiver.

    Sans regle, un TIFF de terrain de 11 Mo entrerait en blob git ordinaire --
    permanent, puisque git ne sait pas oublier. Les trois arbres qui portent du
    lourd doivent chacun avoir la leur.
    """
    motifs = _regles_lfs()
    for attendu in ("tests/fixtures/scans/**",
                    "tests/fixtures/lots/**", "tests/fixtures/rushes/reels/**",
                    "tests/TEST_FILE.mp4"):
        assert attendu in motifs, f"plus aucune regle LFS pour {attendu}"


def test_les_medias_LEGERS_de_tests_restent_hors_LFS():
    """FRONTIERE NEGATIVE symetrique, et c'est la demande explicite d'Egan :
    « eviter d'utiliser lfs sur tous les fichiers assez legers pour s'en
    passer ».

    Les quatre rushes de synthese (~200 Ko) et les QR a 300 dpi n'y gagneraient
    qu'une indirection. Un motif qui les rattraperait -- `tests/fixtures/**` par
    exemple -- passerait les deux tests precedents sans que rien ne le signale.
    """
    motifs = _regles_lfs()
    for leger in ("tests/fixtures/rushes/rush_test_16x9_1920x1080_25fps.mp4",
                  "tests/fixtures/rushes/rush_test_235_1920x817_25fps.mp4",
                  "tests/fixtures/qr_300dpi/main-qr-300dpi.png",
                  "tests/fixtures/aruco/simple_scan.png"):
        for motif in motifs:
            prefixe = motif.rstrip("*").rstrip("/")
            assert not leger.startswith(prefixe + "/"), (
                f"le motif `{motif}` rattraperait `{leger}`, qui pese moins de "
                "300 Ko et n'a rien a faire en LFS")


#: Les rushes de fixture de `tests/fixtures/rushes/`, hors sous-dossier
#: `reels/` : ~200 Ko piece, en git ordinaire, et lus par six bancs.
DOSSIER_DES_RUSHES_DE_FIXTURE = RACINE / "tests" / "fixtures" / "rushes"

#: Les trois champs que `ffprobe` rend pour l'espace couleur, et que le coeur
#: lit sous le nom de « triplet colorimetrique »
#: (`source_confirmation.COLOR_TRIPLET_REPORT_KEYS`). Ce sont TROIS champs et
#: non un : ffmpeg les suit independamment, et `source_confirmation` escalade
#: sur le triplet entier.
CHAMPS_DU_TRIPLET = ("color_primaries", "color_transfer", "color_space")

#: Ce que ces rushes doivent declarer. `EPIC11-ARB-247`, Egan le 2026-09-06,
#: verbatim : « ils ne declarent pas leur espace couleur et provoquent donc
#: des erreurs. Les declarer en rec709 (bt709) si possible ? »
ESPACE_COULEUR_ATTENDU = "bt709"


def test_les_rushes_de_FIXTURE_declarent_leur_espace_couleur():
    """`EPIC11-ARB-247` : un rush muet sur sa colorimetrie fait REFUSER l'extraction.

    **L'erreur, mesuree avant d'agir.** Les cinq rushes rendaient `unknown` sur
    tout ou partie du triplet. `source_confirmation` en tire
    `color_triplet_status` a `absent` (ou `partiel`), donc
    `requires_unknown_color_consent`, et toute extraction non interactive est
    refusee : « la colorimetrie source est absent et exige un consentement
    supplementaire explicite. Passer --accept-unknown-color en plus de --yes ».
    Cinq sur cinq. Le rush REEL du depot, lui, declare `bt709` sur les trois
    champs : c'etait un defaut de la FABRIQUE, jamais du terrain.

    **Pourquoi une frontiere et non un fichier corrige.** Ces rushes n'ont pas
    de generateur -- ce sont des `testsrc` produits a la main. Rien, en amont,
    ne rejouerait le geste : le prochain rush ajoute ici arriverait muet, et
    personne ne le verrait avant qu'un `extract` ne refuse. Ce qui se mesure se
    tient ; ce qui se rappelle se perd.

    **Le geste, pour un rush neuf** -- un remux, jamais un reencodage, sans quoi
    les pixels changent sous les bancs qui les lisent :

        ffmpeg -i entree.mp4 -c copy \
          -bsf:v h264_metadata=colour_primaries=1\
:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0 \
          -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
          -color_range tv sortie.mp4

    Les DEUX moities comptent, et c'est mesure : sans le `bsf`, la declaration
    ne vit que dans l'atome `colr` du conteneur et disparait des qu'on extrait
    le flux elementaire ; le rush reel du terrain, lui, la porte dans la VUI de
    son SPS. Un rush qui ne la porterait qu'au conteneur passerait ce test et
    redeviendrait muet au premier demux -- c'est pourquoi le volet symetrique
    ci-dessous lit le FLUX, pas le fichier.

    Elle SAUTE sans `ffprobe` : un banc ne rougit jamais pour une raison
    d'environnement.
    """
    if shutil.which("ffprobe") is None:
        pytest.skip("ffprobe absent du PATH : le verdict serait faux")
    rushes = sorted(DOSSIER_DES_RUSHES_DE_FIXTURE.glob("*.mp4"))
    assert len(rushes) >= 2, (
        "moins de deux rushes de fixture : la mesure serait vide, et un "
        "balayage casse la rendrait verte")

    muets = []
    for rush in rushes:
        sonde = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=" + ",".join(CHAMPS_DU_TRIPLET),
             "-of", "default=nw=1:nk=0", str(rush)],
            capture_output=True, text=True, timeout=120)
        if sonde.returncode != 0:  # pragma: no cover - fixture illisible
            muets.append(f"{rush.name} (ffprobe echoue : {sonde.stderr.strip()})")
            continue
        lus = dict(l.split("=", 1) for l in sonde.stdout.splitlines() if "=" in l)
        ecarts = [f"{champ}={lus.get(champ, 'absent')}"
                  for champ in CHAMPS_DU_TRIPLET
                  if lus.get(champ) != ESPACE_COULEUR_ATTENDU]
        if ecarts:
            muets.append(f"{rush.name} : " + ", ".join(ecarts))
    assert not muets, (
        "ces rushes de fixture ne declarent pas `bt709` sur les trois champs "
        "du triplet : `extract` les REFUSERA sans `--accept-unknown-color` "
        f"(`EPIC11-ARB-247`). {'; '.join(muets)}")


def test_la_declaration_couleur_survit_au_RETRAIT_du_conteneur():
    """FRONTIERE NEGATIVE : la declaration vit dans le FLUX, pas seulement dans le mp4.

    Le piege que ce volet ferme est mesure, et il est silencieux. Poser les
    seuls `-color_primaries/-color_trc/-colorspace` sur un `-c copy` remplit
    l'atome `colr` du conteneur et RIEN d'autre : `ffprobe` du fichier rend
    `bt709`, le test precedent passe au vert, et le meme flux demuxe rend
    `unknown` sur les trois champs. Mesure le 2026-09-06 sur
    `rush_test_16x9_1920x1080_25fps.mp4`, avant et apres le `bsf`.

    Aucun test positif ne verrait la difference : des deux cotes le fichier
    declare `bt709`.
    """
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe absents du PATH : le verdict serait faux")
    rushes = sorted(DOSSIER_DES_RUSHES_DE_FIXTURE.glob("*.mp4"))
    assert rushes, "aucun rush de fixture : la mesure serait vide"

    superficiels = []
    for rush in rushes:
        demux = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(rush), "-c", "copy",
             "-f", "h264", "-"],
            capture_output=True, timeout=120)
        if demux.returncode != 0:  # pragma: no cover - flux non h264
            continue
        sonde = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=" + ",".join(CHAMPS_DU_TRIPLET),
             "-of", "default=nw=1:nk=0", "-f", "h264", "-"],
            input=demux.stdout, capture_output=True, timeout=120)
        lus = dict(l.split("=", 1)
                   for l in sonde.stdout.decode("utf-8", "replace").splitlines()
                   if "=" in l)
        ecarts = [f"{champ}={lus.get(champ, 'absent')}"
                  for champ in CHAMPS_DU_TRIPLET
                  if lus.get(champ) != ESPACE_COULEUR_ATTENDU]
        if ecarts:
            superficiels.append(f"{rush.name} : " + ", ".join(ecarts))
    assert not superficiels, (
        "ces rushes ne declarent `bt709` QUE dans leur conteneur : la VUI de "
        "leur SPS est muette, donc la declaration se perd au premier demux. "
        "Ajouter `-bsf:v h264_metadata=...` au remux. "
        + "; ".join(superficiels))


def test_les_rushes_de_FIXTURE_ne_sont_plus_des_objets_LFS():
    """FRONTIERE NEGATIVE d'`EPIC11-ARB-247` : ni par regle, ni par heritage.

    Les deux moities sont necessaires et aucune ne suffit.
    :func:`test_les_medias_LEGERS_de_tests_restent_hors_LFS` mesure la REGLE --
    qu'aucun motif de `.gitattributes` ne les rattrape --, et elle etait DEJA
    verte quand ces quatre fichiers etaient des pointeurs dans `HEAD` : un
    objet LFS orphelin de ses attributs echappe par construction a une mesure
    qui lit les attributs. C'est le blob de `HEAD` qui tranche.

    Ce que la normalisation ferme : ces fichiers pesent ~200 Ko, leur mettre
    une indirection LFS n'economise rien, et `git add` sur un orphelin indexe
    le binaire BRUT sans qu'aucun message ne le dise -- le meme piege qui a
    failli mettre 350 Mo de PDF nu dans git ordinaire le 2026-09-03.

    Le saut est STRUCTUREL : hors depot git, il n'y a rien a comparer.
    """
    rushes = sorted(DOSSIER_DES_RUSHES_DE_FIXTURE.glob("*.mp4"))
    assert rushes, "aucun rush de fixture : la mesure serait vide"
    pointeurs = []
    for rush in rushes:
        relatif = rush.relative_to(RACINE).as_posix()
        rendu = subprocess.run(["git", "cat-file", "-p", f"HEAD:{relatif}"],
                               cwd=RACINE, capture_output=True, timeout=60)
        if rendu.returncode != 0:
            pytest.skip("git ne rend pas le contenu de HEAD (pas de depot ici)")
        if rendu.stdout.startswith(b"version https://git-lfs.github.com/spec/v1"):
            pointeurs.append(relatif)
    assert not pointeurs, (
        "ces rushes legers sont encore des objets LFS dans `HEAD`, alors "
        "qu'aucune regle ne les y envoie : ce sont des orphelins, et un "
        "`git add` y indexerait le binaire brut sans le dire "
        f"(`EPIC11-ARB-247`). {', '.join(pointeurs)}")


# --------------------------------------------------------------------------
# 3. `projects/` n'est plus versionne du tout
# --------------------------------------------------------------------------

def test_aucun_fichier_de_projects_n_est_versionne():
    """FRONTIERE NEGATIVE sur l'arbitrage d'Egan du 2026-09-03.

    `projects/` portait 2 217 Mo -- 97 % du volume LFS -- et aucun test ne le
    lisait. Il revient en une commande (`git add projects/`), et le seul signal
    serait la facture du mois suivant.
    """
    revenus = [n for n in _suivis() if n.startswith(ARBRE_LOCAL)]
    assert not revenus, (
        f"{len(revenus)} fichier(s) de `{ARBRE_LOCAL}` sont a nouveau suivis, "
        "alors que ce dossier a vocation a rester local : "
        + ", ".join(sorted(revenus)[:5]))


def test_projects_est_bien_ignore():
    """Le pendant POSITIF : desuivre sans ignorer laisserait le dossier
    reapparaitre au premier `git add` un peu large."""
    sortie = subprocess.run(["git", "check-ignore", "-q", "projects/"],
                            cwd=RACINE)
    assert sortie.returncode == 0, (
        "`projects/` n'est pas dans .gitignore : il reviendra tout seul.")


# --------------------------------------------------------------------------
# 4. Aucun clone ne retelecharge l'heritage
# --------------------------------------------------------------------------

def test_le_lfsconfig_exclut_l_heritage_de_projects():
    """FRONTIERE NEGATIVE sur le fichier qui rend la politique PORTABLE.

    Les objets de `projects/` ne sont plus dans `HEAD`, mais ils restent dans
    l'HISTORIQUE : un `git checkout` d'un commit d'avant le 2026-09-03 les
    retelechargerait -- 2 217 Mo, un cinquieme du quota mensuel, pour un dossier
    que personne ne lit. Cette ligne est la seule chose qui l'empeche.

    Et un `git config` LOCAL n'aurait pas suffi : il serait a reposer dans
    chaque conteneur neuf, et un conteneur neuf est exactement ce qui coutait.
    """
    chemin = RACINE / ".lfsconfig"
    assert chemin.exists(), (
        ".lfsconfig manque : un checkout d'un vieux commit retirera 2,2 Go.")
    actif = [l.strip() for l in chemin.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    exclusions = [l for l in actif if l.startswith("fetchexclude")]
    assert exclusions, "`fetchexclude` absent de .lfsconfig"
    assert any(ARBRE_LOCAL in l for l in exclusions), (
        f"`{ARBRE_LOCAL}` n'est pas exclu : " + " ; ".join(exclusions))


def test_le_lfsconfig_n_exclut_PAS_les_medias_de_tests():
    """FRONTIERE NEGATIVE, et elle ferme une erreur DEJA COMMISE.

    La premiere redaction portait `fetchexclude = *`. C'etait la bonne reponse
    tant que `projects/` etait versionne, et c'est devenu la mauvaise des lors
    qu'il ne l'etait plus : elle bloquait aussi les medias de `tests/`, que la
    CI et les bancs doivent au contraire recevoir automatiquement. Egan l'a
    demande mot pour mot : « que tous les fichiers medias dans tests/ soient
    bien synchronises ».
    """
    motifs = _exclusions()
    assert "*" not in motifs, (
        "`fetchexclude = *` bloque AUSSI les medias de tests/ : "
        "les bancs recevraient des pointeurs de 133 octets.")
    for indispensable in AUTO_TELECHARGES:
        for motif in motifs:
            prefixe = motif.rstrip("*").rstrip("/")
            assert not indispensable.startswith(prefixe), (
                f"`{motif}` empeche `{indispensable}` de descendre, alors que "
                "les bancs le lisent a chaque course.")


def test_le_lfsconfig_dit_COMMENT_materialiser_ce_qui_est_exclu():
    """Une interdiction sans issue est une corvee, pas une politique.

    Meme famille qu'`EPIC11-ARB-89` : jamais un blocage sec, toujours une issue
    nommee. L'issue doit figurer dans le fichier que lira celui qui butera
    dessus.
    """
    texte = (RACINE / ".lfsconfig").read_text(encoding="utf-8")
    assert "git lfs pull --include=" in texte


def test_l_issue_documentee_MARCHE_et_pas_seulement_existe():
    """Frontiere NEGATIVE : la forme inerte ne doit pas revenir.

    Le 2026-09-07, les trois commandes de `.lfsconfig` portaient
    `--include=` SEUL. Elles ne tiraient rien : `--include` remplace
    `lfs.fetchinclude` pour la commande, il ne desarme pas
    `lfs.fetchexclude`, qui reste applique par-dessus depuis ce meme
    fichier. Un chemin nomme dans les deux reste donc exclu -- et c'est le
    cas de TOUT ce que ces commandes sont censees obtenir.

    Mesure (git-lfs 3.4.1), trois appels de suite, seule la troisieme ligne
    differe de la deuxieme par `-X ""` :

        -I "tests/**"                            -> 0,22 s, RIEN
        -I "tests/fixtures/lots/**,.../reels/**" -> 0,04 s, RIEN
        ... le meme, plus -X ""                  -> 15,2 s, 243 Mo

    Le test qui gardait ce paragraphe -- celui juste au-dessus -- mesurait la
    PRESENCE d'une issue et non son EFFET : la forme inerte satisfaisait son
    `assert` mot pour mot. C'est exactement le defaut qu'une frontiere
    negative attrape et qu'aucun test positif ne verrait revenir.
    """
    texte = (RACINE / ".lfsconfig").read_text(encoding="utf-8")

    # Seules les lignes de COMMANDE, c'est-a-dire les blocs indentes de quatre
    # espaces sous le `#`. Sans cette restriction le test attrape sa propre
    # justification en prose, qui cite forcement la forme fautive pour dire
    # qu'elle est fautive -- ce qui est arrive a sa premiere redaction.
    commandes = [
        m.group(1).strip()
        for m in re.finditer(
            r"^#\s{4,}(git lfs pull .*)$", texte, flags=re.MULTILINE
        )
    ]
    assert commandes, "aucune commande de materialisation documentee"

    inertes = [
        c for c in commandes
        if "--exclude=" not in c and not re.search(r"(^|\s)-X(\s|=)", c)
    ]
    assert not inertes, (
        "Commande(s) documentee(s) SANS exclusion vide -- elles ne tirent "
        "rien, silencieusement, puisque `fetchexclude` de ce meme fichier "
        "les recouvre :\n  " + "\n  ".join(inertes)
    )


# --------------------------------------------------------------------------
# 5. Le risque que la politique CREE
# --------------------------------------------------------------------------

def test_aucun_gros_fichier_SUIVI_ne_dort_hors_LFS():
    """Le symetrique, et il mesure le risque de la politique NEUVE.

    Scoper le LFS ouvre la porte inverse : un raster de 128 Mo depose dans
    `docs/` entrerait en blob git, que git ne sait pas oublier et que GitHub
    refuse au-dela de 100 Mo. Une politique qui n'aurait que la frontiere « pas
    trop de LFS » pousserait le probleme de l'autre cote -- c'est ce test qui a
    trouve `tests/20260714.png`, 9,5 Mo references par aucun fichier.

    Il ecarte les fichiers DEJA SUIVIS PAR LFS en interrogeant
    `git lfs ls-files`, pas en devinant sur la taille : un pointeur pese 133
    octets tant qu'il n'est pas materialise et 12 Mo une fois tire, donc un
    seuil aurait rendu le verdict dependant de ce que le conteneur avait
    telecharge -- c'est-a-dire non reproductible.
    """
    suivis = subprocess.run(["git", "lfs", "ls-files", "-n"], cwd=RACINE,
                            capture_output=True, text=True)
    if suivis.returncode != 0:
        pytest.skip("git-lfs indisponible : le verdict serait faux")
    en_lfs = set(suivis.stdout.splitlines())

    # DEUX sources de verite, et il faut les deux. `git lfs ls-files` lit le
    # COMMIT : un fichier fraichement indexe n'y figure pas encore, et le test
    # rougissait donc sur un lot correctement route. `git check-attr` lit la
    # REGLE : elle ignore les objets HERITES dont l'attribut ne parle plus --
    # entres en LFS avant la revision du 2026-09-03 et plus rattrapes par aucun
    # motif depuis. Sous `tests/` il n'en reste AUCUN : `EPIC11-ARB-247` a
    # normalise les quatre rushes de synthese le 2026-09-06, et
    # `synthetic_review_video.mp4` -- le dernier, lu par aucun banc -- a ete
    # retire le 2026-09-09. Les douze qui subsistent vivent sous
    # `_bmad-output/test-artifacts/**` et `docs/tuto_*.pdf`, et `.lfsconfig`
    # les exclut desormais du fetch. L'union des deux repond a la vraie
    # question :
    # « ce fichier est-il en LFS ? »
    regles = subprocess.run(["git", "check-attr", "--stdin", "filter"],
                            cwd=RACINE, capture_output=True, text=True,
                            input="\n".join(_suivis()))
    for ligne in regles.stdout.splitlines():
        if ligne.endswith(": filter: lfs"):
            en_lfs.add(ligne[: -len(": filter: lfs")])

    lourds = []
    for nom in _suivis():
        if nom in en_lfs:
            continue
        try:
            taille = (RACINE / nom).stat().st_size
        except OSError:
            continue
        if taille >= SEUIL_DE_QUESTION_OCTETS:
            lourds.append(f"{nom} ({taille / 1048576:.1f} Mo)")
    assert not lourds, (
        "ces fichiers de 5 Mo ou plus sont suivis en clair ; git ne sait pas "
        "les oublier. Les mettre sous un arbre LFS de `tests/`, les publier en "
        "asset de Release, ou trancher explicitement : "
        + ", ".join(sorted(lourds)))


def test_l_arbre_LOURD_ne_descend_PAS_automatiquement():
    """FRONTIERE NEGATIVE : c'est le seuil, et il ne peut vivre qu'ici.

    `tests/fixtures/lots/` porte un lot complet de terrain -- 13 frames et le
    PDF de son scan, **178 Mo**. Il est versionne, donc partageable et
    reproductible. Le tirer a chaque clone couterait 178 Mo par conteneur neuf,
    c'est-a-dire la saturation du quota en trois jours -- exactement le defaut
    qu'on vient de fermer, par une autre porte.

    **Git ne sait pas apparier une TAILLE**, seulement un chemin : un seuil ne
    peut donc pas vivre dans `.gitattributes`. Il vit dans le choix de ce qui
    descend, et cette ligne est ce choix.
    """
    motifs = _exclusions()
    for arbre in ARBRES_LOURDS:
        assert any(arbre.rstrip("/").startswith(m.rstrip("*").rstrip("/"))
                   or m.startswith(arbre.rstrip("/")) for m in motifs), (
            f"`{arbre}` n'est pas exclu du telechargement automatique. "
            f"Exclusions declarees : {motifs}")


def test_l_arbre_lourd_reste_STOCKE_en_LFS():
    """Le pendant POSITIF : exclure du fetch n'est pas exclure du depot.

    Sans regle `filter=lfs`, ces 178 Mo entreraient en blobs git ordinaires --
    et GitHub refuse au-dela de 100 Mo par fichier, ce qui aurait au moins
    rougi ; en dessous, ils grossiraient le depot pour toujours, en silence.
    """
    regles = _regles_lfs()
    for arbre in ARBRES_LOURDS:
        assert f"{arbre}**" in regles, f"`{arbre}` n'est pas stocke en LFS"


def test_le_TEXTE_d_un_arbre_LFS_reste_en_git_ordinaire():
    """FRONTIERE NEGATIVE : un motif d'ARBRE rattrape tout ce qui s'y trouve.

    `tests/fixtures/lots/**` envoyait son propre README et les manifestes JSON
    du lot en LFS. C'est arrive DEUX FOIS le meme jour, a une heure
    d'intervalle : la regle etroite posee la premiere fois, qui listait chaque
    dossier, a echoue des la famille suivante (`rushes/reels/`).

    Le test balaie donc TOUS les fichiers texte suivis, pas une liste ecrite a
    la main -- une liste aurait manque la famille suivante exactement comme la
    regle etroite l'avait fait.

    Rien ne rougit quand un README part en pointeur : il devient juste
    illisible sur la page GitHub.
    """
    textes = [n for n in _suivis()
              if n.endswith((".md", ".json", ".txt", ".yaml", ".yml"))]
    assert textes, "aucun fichier texte suivi : la mesure serait vide"
    rendu = subprocess.run(["git", "check-attr", "--stdin", "filter"],
                           cwd=RACINE, capture_output=True, text=True,
                           input="\n".join(textes))
    fautifs = [l[: -len(": filter: lfs")] for l in rendu.stdout.splitlines()
               if l.endswith(": filter: lfs")]
    assert not fautifs, (
        "ces fichiers TEXTE partent en LFS -- une indirection pour quelques "
        "kilo-octets, et un README en pointeur devient illisible sur la page "
        "GitHub : " + ", ".join(fautifs[:5]))


def test_le_garde_fou_de_taille_existe_et_est_EXECUTABLE():
    """Le seuil que `.gitattributes` ne sait pas exprimer, applique au moment
    ou il compte -- avant que le blob n'entre dans l'historique.

    Ce test verifie les deux choses qui le rendent inerte en silence : un hook
    absent, et un hook present mais **non executable** -- git le saute alors
    sans un mot, et rien ne distingue ce cas d'un depot sain.
    """
    import os
    hook = RACINE / ".githooks" / "pre-commit"
    assert hook.exists(), (
        ".githooks/pre-commit manque : plus rien n'arrete un gros fichier "
        "avant qu'il entre dans l'historique.")
    assert os.access(hook, os.X_OK), (
        ".githooks/pre-commit n'est pas executable : git le saute EN SILENCE.")
    texte = hook.read_text(encoding="utf-8")
    assert "SEUIL_MO" in texte
    # Jamais un blocage sec : le refus doit nommer ses issues (EPIC11-ARB-89).
    assert "--no-verify" in texte, (
        "le refus n'offre aucune issue deliberee : c'est un blocage sec.")


#: Les hooks que git-lfs installe, et dont il a besoin. `pre-push` est le seul
#: qui EXPEDIE : sans lui, un push envoie des pointeurs dont le contenu n'a
#: jamais quitte la machine.
HOOKS_DE_LFS = ("pre-push", "post-checkout", "post-merge", "post-commit")


def test_le_dossier_de_hooks_porte_AUSSI_ceux_de_git_lfs():
    """FRONTIERE NEGATIVE sur un defaut introduit par le garde-fou lui-meme.

    `core.hooksPath` **remplace** `.git/hooks`, il ne s'y ajoute pas. En posant
    `.githooks` pour le seuil de taille, on a donc debranche les quatre hooks
    de git-lfs -- et le plus grave est `pre-push` : sans lui, un `git push`
    envoie les POINTEURS sans televerser les objets. Le depot devient alors
    illisible pour tout le monde sauf celui qui a poussé, et **rien ne le
    signale** : le push reussit.

    git-lfs les a reinstalles tout seul dans `.githooks/` a la premiere
    occasion, ce qui a masque le probleme ici. Sur un clone neuf qui pose
    `core.hooksPath` avant que git-lfs n'y touche, il ne serait pas masque.
    """
    import os
    for nom in HOOKS_DE_LFS:
        hook = RACINE / ".githooks" / nom
        assert hook.exists(), (
            f".githooks/{nom} manque : `core.hooksPath` ayant remplace "
            ".git/hooks, git-lfs n'est plus branche. Pour `pre-push`, cela "
            "veut dire des objets jamais televerses, sans un mot d'erreur.")
        assert os.access(hook, os.X_OK), (
            f".githooks/{nom} n'est pas executable : git le saute EN SILENCE.")
        assert "git lfs" in hook.read_text(encoding="utf-8")


def test_le_TEXTE_reste_DIFFABLE_et_FUSIONNABLE():
    """FRONTIERE NEGATIVE sur une regression introduite le meme jour.

    Sortir un fichier du LFS demande de defaire l'attribut `filter`. Ecrit avec
    un TIRET (`-diff -merge`), on ne le defait pas : on le met a UNSET, ce qui
    fait traiter le fichier comme BINAIRE. `git diff` rend alors « Binary files
    differ » et une fusion ne peut plus se resoudre autrement qu'en prenant un
    cote entier.

    Sur un depot dont les stories, les arbitrages et CLAUDE.md sont en markdown
    et edites par plusieurs agents en parallele, c'est une regression grave --
    et elle a mordu : un `git cherry-pick` de CLAUDE.md a conflicte sans diff
    lisible. Le bon signe est `!`, qui rend l'attribut NON SPECIFIE, donc au
    defaut de git.

    Un test positif ne verrait pas la difference : dans les deux cas le fichier
    est hors LFS.
    """
    textes = [n for n in _suivis() if n.endswith((".md", ".json", ".txt",
                                                  ".yaml", ".yml"))][:200]
    assert textes, "aucun fichier texte suivi : la mesure serait vide"
    rendu = subprocess.run(["git", "check-attr", "--stdin", "diff", "merge"],
                           cwd=RACINE, capture_output=True, text=True,
                           input="\n".join(textes))
    binaires = [l for l in rendu.stdout.splitlines() if l.endswith(": unset")]
    assert not binaires, (
        "ces fichiers texte sont traites comme BINAIRES (`-diff` / `-merge` au "
        "lieu de `!diff` / `!merge`) : plus de diff lisible, plus de fusion "
        "possible. " + "; ".join(binaires[:4]))
