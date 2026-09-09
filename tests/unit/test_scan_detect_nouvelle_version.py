"""Story 11.4e, lot D -- `mmu scan detect --nouvelle-version` cesse d'etre INERTE.

Le fait mesure qui fonde ce banc, et il n'etait dans aucun audit :

* `--nouvelle-version` est declaree sur le parseur **parent** `scan`
  (`cli.py`), et `detect` en est un sous-parseur qui, par convention explicite
  du fichier, « ne redeclare aucune option du parent ». Le drapeau est donc
  **accepte** par `mmu scan ... --nouvelle-version detect`, sans un mot
  d'argparse ;
* `scan_detect_command` ne lisait **jamais** `args.nouvelle_version` ;
* `run_scan_detect` n'avait **aucun** parametre `nouvelle_version` et appelait
  `scan_ingest.ingest_scan_lot` sans lui, alors que l'ingestion le **porte**
  depuis `EPIC11-ARB-104`.

L'operateur croyait donc demander une nouvelle version et n'obtenait rien, en
silence -- exactement le contraire d'`EPIC11-ARB-104` (« Tout doit etre
versionnable OU ecrase »), sur l'objet que cet arbitrage cite en exemple.

**Le livrable le plus durable de ce banc n'est pas le correctif** : c'est la
frontiere de la section D3, qui mesure qu'AUCUNE option declaree sur un
parseur parent n'est ignoree par la commande qui l'herite. Un correctif ferme
un defaut ; cette frontiere ferme la FAMILLE du defaut, et elle a trouve seize
autres couples (commande, option) inertes que le registre ci-dessous nomme un
par un.

Quatre sections, une par tache du lot :

* **D1** -- `run_scan_detect(nouvelle_version=)` atteint `ingest_scan_lot` ;
* **D2** -- `scan_detect_command` LIT le drapeau, et le bout en bout ecrit a
  cote sans toucher a l'origine (mesure aux **inodes**, au `st_mtime_ns` et
  par un **temoin** -- jamais par un condensat, qu'une reecriture identique
  laisserait vert) ;
* **D3** -- la frontiere des options inertes et son volet symetrique ;
* **D4** -- la ligne d'eau au retrait (`EPIC11-ARB-92`, `EPIC11-ARB-108`).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (  # noqa: E402
    cli,
    project_maintenance,
    scan_detect,
    scan_ingest,
)
from mixed_media_utility.io import project_layout  # noqa: E402


# ---------------------------------------------------------------------------
# Fabriques propres a ce banc.
# ---------------------------------------------------------------------------


def _page(couleur: int = 240) -> "np.ndarray":
    """Une page unie, sans QR : la detection s'arrete proprement apres
    l'ingestion (`ARRET_AUCUNE_PLANCHE_IDENTIFIEE`), qui est la seule moitie
    que ce lot mesure. Un QR reel couterait des minutes pour rien."""
    return np.full((400, 300, 3), couleur, np.uint8)


@pytest.fixture()
def projet_et_source(tmp_path):
    projet = tmp_path / "projet"
    project_layout.ensure_project_layout(projet)
    source = tmp_path / "scan-WIN"
    source.mkdir()
    cv2.imwrite(str(source / "p1.tiff"), _page())
    return projet, source


class _EspionD_ingestion:
    """Un espion qui NOTE puis ARRETE la passe.

    Il leve `ScanIngestError` -- un refus que le coeur connait deja et relaie
    tel quel --, ce qui evite d'avoir a fabriquer un `ScanIngestReport`
    complet pour mesurer ce qui est transmis a l'ingestion.
    """

    def __init__(self):
        self.positionnels = None
        self.mots_cles = None

    def __call__(self, *args, **kwargs):
        self.positionnels = args
        self.mots_cles = dict(kwargs)
        raise scan_ingest.ScanIngestError("arret volontaire du banc")


def _empreinte(chemin: Path) -> tuple:
    """Ce qui dit qu'un fichier n'a PAS ete reecrit.

    **Jamais un condensat** : une fixture deterministe reecrite rend
    exactement les memes octets, et le condensat serait vert a tort
    (`CLAUDE.md`, 2026-08-30). L'inode change des qu'un remplacement atomique
    passe par la, le `st_mtime_ns` des qu'une ecriture en place passe par la :
    les deux ensemble attrapent les deux formes.
    """
    etat = chemin.stat()
    return (etat.st_ino, etat.st_mtime_ns, etat.st_size)


# ===========================================================================
# D1 -- `run_scan_detect(nouvelle_version=)` -> `ingest_scan_lot`  (AC 4.1)
# ===========================================================================


def test_run_scan_detect_TRANSMET_nouvelle_version_a_l_ingestion(
        projet_et_source, monkeypatch):
    projet, source = projet_et_source
    espion = _EspionD_ingestion()
    monkeypatch.setattr(scan_ingest, "ingest_scan_lot", espion)

    with pytest.raises(scan_ingest.ScanIngestError):
        scan_detect.run_scan_detect(projet, source, dpi=600, nouvelle_version=True)

    assert espion.mots_cles["nouvelle_version"] is True


def test_le_DEFAUT_de_run_scan_detect_est_de_ne_PAS_versionner(
        projet_et_source, monkeypatch):
    """Volet symetrique : sans lui, un `nouvelle_version=True` code en dur
    passerait le test precedent."""
    projet, source = projet_et_source
    espion = _EspionD_ingestion()
    monkeypatch.setattr(scan_ingest, "ingest_scan_lot", espion)

    with pytest.raises(scan_ingest.ScanIngestError):
        scan_detect.run_scan_detect(projet, source, dpi=600)

    assert espion.mots_cles["nouvelle_version"] is False


def test_l_ensemble_EXACT_des_mots_cles_transmis_a_l_ingestion(
        projet_et_source, monkeypatch):
    """« Une assertion positive laisse passer toute divergence
    supplementaire » : on mesure l'ensemble, pas l'appartenance."""
    projet, source = projet_et_source
    espion = _EspionD_ingestion()
    monkeypatch.setattr(scan_ingest, "ingest_scan_lot", espion)
    manifeste = {"schema_version": "2.1"}

    with pytest.raises(scan_ingest.ScanIngestError):
        scan_detect.run_scan_detect(
            projet, source, dpi=600, ingest_slug="S",
            nouvelle_version=True, manifest_du_projet=manifeste)

    assert set(espion.mots_cles) == {
        "dpi", "ingest_slug", "nouvelle_version", "manifest"}
    assert espion.positionnels == (Path(projet), source)


def test_le_manifeste_du_projet_est_relaye_TEL_QUEL(projet_et_source, monkeypatch):
    """Il porte la ligne d'eau des rangs. Relaye par IDENTITE : une copie
    intermediaire serait une seconde verite, et un `dict()` de passage
    masquerait un appelant qui ne le lit pas vraiment."""
    projet, source = projet_et_source
    espion = _EspionD_ingestion()
    monkeypatch.setattr(scan_ingest, "ingest_scan_lot", espion)
    manifeste = {"scan_version_watermarks": {"S": 7}}

    with pytest.raises(scan_ingest.ScanIngestError):
        scan_detect.run_scan_detect(
            projet, source, dpi=600, manifest_du_projet=manifeste)

    assert espion.mots_cles["manifest"] is manifeste


def _code_sans_prose(chemin: Path) -> str:
    """Le CODE d'un module, docstrings et commentaires retires.

    La distinction n'est pas une commodite : DIRE ou vit la regle des rangs
    est exactement ce que ce depot demande (« un mecanisme, un lieu »), et une
    frontiere qui compterait la prose punirait la phrase qui nomme le lieu
    unique tout en laissant passer un `if rang > ...` recopie sous un autre
    nom. On mesure donc ce qui S'EXECUTE.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        corps = getattr(noeud, "body", None)
        if not isinstance(corps, list) or not corps:
            continue
        premier = corps[0]
        if (isinstance(premier, ast.Expr) and isinstance(premier.value, ast.Constant)
                and isinstance(premier.value.value, str)):
            del corps[0]
    return ast.unparse(arbre)


def test_AUCUNE_regle_de_rang_n_est_ecrite_dans_le_coeur_de_detect():
    """`EPIC11-ARB-108` : « Il n'y a pas de mecanisme different par objet. »

    Comptage a zero du vocabulaire de rang dans le CODE de `scan_detect.py`,
    avec son volet symetrique -- le vocabulaire existe bel et bien dans le
    module qui porte LA regle, sans quoi ce comptage serait vert sur un depot
    qui aurait simplement perdu la regle.
    """
    vocabulaire = ("ligne_d_eau", "prochain_rang", "rangs_liberables",
                   "est_en_queue", "RANG_ORIGINE", "VERSION_RANK_MAX")
    code = _code_sans_prose(Path(scan_detect.__file__))
    trouves = [mot for mot in vocabulaire if mot in code]
    assert trouves == [], (
        f"`scan_detect` recopie la regle des rangs : {trouves}. Elle vit dans "
        "`io/version_ranks.py`, une seule fois, pour les cinq objets.")

    code_de_la_regle = _code_sans_prose(
        REPO_ROOT / "src" / "mixed_media_utility" / "io" / "version_ranks.py")
    manquants = [mot for mot in vocabulaire if mot not in code_de_la_regle]
    assert manquants == [], manquants


# ===========================================================================
# D2 -- `scan_detect_command` LIT le drapeau  (AC 4.2)
# ===========================================================================


class _EspionDuCoeur:
    """Espion pose sur `scan_detect.run_scan_detect`, vu depuis `cli`."""

    def __init__(self):
        self.mots_cles = None
        self.positionnels = None

    def __call__(self, *args, **kwargs):
        self.positionnels = args
        self.mots_cles = dict(kwargs)
        raise scan_detect.ScanDetectError("arret volontaire du banc")


def _detecter(projet, source, *options) -> int:
    return cli.main([
        "scan", "--project", str(projet), "--scan", str(source),
        "--dpi", "600", *options, cli.SCAN_DETECT_SUBCOMMAND,
    ])


def test_scan_detect_command_LIT_le_drapeau_et_le_passe_au_coeur(
        projet_et_source, monkeypatch):
    projet, source = projet_et_source
    espion = _EspionDuCoeur()
    monkeypatch.setattr(scan_detect, "run_scan_detect", espion)

    assert _detecter(projet, source, "--nouvelle-version") == 1
    assert espion.mots_cles["nouvelle_version"] is True


def test_SANS_le_drapeau_la_commande_passe_False(projet_et_source, monkeypatch):
    """Volet symetrique du precedent."""
    projet, source = projet_et_source
    espion = _EspionDuCoeur()
    monkeypatch.setattr(scan_detect, "run_scan_detect", espion)

    assert _detecter(projet, source) == 1
    assert espion.mots_cles["nouvelle_version"] is False


def test_l_ensemble_EXACT_des_mots_cles_que_la_COMMANDE_passe_au_coeur(
        projet_et_source, monkeypatch):
    projet, source = projet_et_source
    espion = _EspionDuCoeur()
    monkeypatch.setattr(scan_detect, "run_scan_detect", espion)

    _detecter(projet, source, "--nouvelle-version")

    assert set(espion.mots_cles) == {
        "dpi", "ingest_slug", "logger", "nouvelle_version", "manifest_du_projet"}


def test_bout_en_bout_la_nouvelle_version_ECRIT_A_COTE_et_laisse_l_origine_INTACTE(
        projet_et_source):
    """AC 4.2, mesure aux inodes et par temoin -- jamais au condensat."""
    projet, source = projet_et_source
    assert _detecter(projet, source) == 0
    origine = projet / "scans" / "scan-WIN"
    temoin = origine / "temoin-du-banc.txt"
    temoin.write_text("depose avant la seconde passe", encoding="utf-8")
    avant = {chemin.name: _empreinte(chemin)
             for chemin in sorted(origine.iterdir()) if chemin.is_file()}

    assert _detecter(projet, source, "--nouvelle-version") == 0

    voisin = projet / "scans" / "scan-WIN_v2"
    assert voisin.is_dir(), (
        "le drapeau reste inerte : rien n'a ete ecrit dans un dossier voisin. "
        f"Dossiers presents : {sorted(c.name for c in (projet / 'scans').iterdir())}")
    assert (voisin / "p1.tiff").is_file()
    assert temoin.is_file(), "le temoin a disparu : l'origine a ete reecrite"
    apres = {chemin.name: _empreinte(chemin)
             for chemin in sorted(origine.iterdir()) if chemin.is_file()}
    assert apres == avant, (
        "l'origine a ete touchee (inode ou st_mtime_ns changes) alors que la "
        "passe devait ecrire a cote")


def test_bout_en_bout_SANS_le_drapeau_AUCUN_dossier_voisin_n_est_cree(
        projet_et_source):
    """Volet symetrique : le versionnage ne se declenche que sur demande."""
    projet, source = projet_et_source
    assert _detecter(projet, source) == 0
    assert _detecter(projet, source) == 0
    assert sorted(c.name for c in (projet / "scans").iterdir()) == ["scan-WIN"]


# ===========================================================================
# D3 -- LA FRONTIERE DES OPTIONS INERTES  (AC 4.3)
# ===========================================================================
#
# Ce que cette section mesure, et qui vaut au-dela de `--nouvelle-version` :
# `mmu` declare ses options sur des parseurs PARENTS, et ses sous-commandes
# « ne redeclarent aucune option du parent ». Une option du parent qu'une
# sous-commande ne lit jamais est donc **acceptee sans un mot** et sans effet.
# Argparse ne peut pas le voir : pour lui, l'option est parfaitement valide.
#
# La frontiere confronte deux ensembles, par commande :
#
#   * les `dest` que la commande HERITE de ses parseurs ancetres ;
#   * les attributs d'`args` que sa fonction LIT reellement -- transitivement,
#     car `scan_command` passe son `args` a des enveloppes internes.
#
# Le reste doit etre inscrit dans le REGISTRE ci-dessous, avec son motif.
# L'egalite est mesuree dans les DEUX sens : une option ni lue ni inscrite
# rougit (option inerte neuve), et une inscription qui ne designe plus rien --
# option disparue, ou desormais lue -- rougit aussi. C'est ce second sens qui
# empeche le registre de pourrir en liste de suppressions.

#: Les couples (commande, `dest`) herites et deliberement NON lus, avec leur
#: motif. Les entrees prefixees `DETTE` sont des defauts de la MEME famille
#: que celui que ce lot ferme : l'option est acceptee, l'operateur en attend
#: un effet, et il n'y en a aucun. Elles sont nommees plutot que corrigees --
#: les corriger toutes elargirait le perimetre de cette story --, et elles
#: sont portees au rapport du lot D.
REGISTRE_DES_OPTIONS_NON_LUES: dict[tuple[str, str], str] = {
    # --- `mmu scan ... detect` -------------------------------------------
    ("scan detect", "profil"):
        "detect n'applique aucune correction : elle n'ecrit aucune frame. "
        "Le profil est designe au temps 2 (`scan-write`).",
    ("scan detect", "color_correction"):
        "meme motif : la correction s'applique a l'ecriture des frames.",
    ("scan detect", "keep_raw"):
        "meme motif : il n'y a pas de frame a livrer brute.",
    ("scan detect", "divergence_bypass"):
        "meme motif : la divergence se juge au moment d'ecrire.",
    ("scan detect", "overwrite"):
        "DETTE -- detect ecrit bel et bien un document de detection, et le "
        "coeur porte deja `remplacer_les_detections` (`EPIC7-ARB-90`) qu'aucun "
        "drapeau de la CLI n'atteint. `--overwrite` est donc accepte ici sans "
        "effet la ou il aurait un sens.",
    # --- `mmu scan ... calibrate` ----------------------------------------
    ("scan calibrate", "profil"):
        "calibrate PRODUIT un profil ; en designer un a appliquer n'a pas de "
        "sens sur ce chemin.",
    ("scan calibrate", "color_correction"):
        "meme motif : la calibration mesure la correction, elle ne l'applique pas.",
    ("scan calibrate", "keep_raw"):
        "meme motif : aucune frame n'est livree par ce chemin.",
    ("scan calibrate", "divergence_bypass"):
        "meme motif : aucun refus de divergence sur ce chemin.",
    ("scan calibrate", "lot_slug"):
        "DETTE -- calibrate INGERE (`scan_ingest.ingest_scan_lot`) et ne "
        "transmet pas le slug : `mmu scan --lot-slug X ... calibrate` ingere "
        "sous un autre nom que celui demande, sans un mot.",
    ("scan calibrate", "nouvelle_version"):
        "DETTE -- exactement le defaut que ce lot ferme sur `detect`, sur le "
        "chemin voisin : calibrate ingere aussi, et le drapeau n'y descend pas.",
    ("scan calibrate", "overwrite"):
        "DETTE -- le profil de calibration est un objet ecrit, qui peut deja "
        "exister sous le meme nom ; le drapeau est accepte sans effet.",
    # --- `mmu makepdf calibration-page` ----------------------------------
    ("makepdf calibration-page", "lot"):
        "une page de calibration ne porte aucun lot : elle n'a pas d'identite "
        "metier a composer.",
    ("makepdf calibration-page", "rush"):
        "meme motif : aucun rush a designer.",
    ("makepdf calibration-page", "fps"):
        "meme motif : le couple --rush/--fps ne resout un lot que pour une "
        "planche d'images.",
    ("makepdf calibration-page", "nouvelle_version"):
        "DETTE -- la page de calibration est un PDF ecrit, et la commande lit "
        "bien `--overwrite` ; `EPIC11-ARB-104` demande les deux issues, et le "
        "versionnage est ici accepte sans effet.",
}

#: Les couples du registre qui sont des DETTES et non des options sans objet.
#: Mesure en ensemble EXACT plus bas : une dette fermee doit quitter les deux
#: structures, une dette neuve doit entrer dans les deux.
DETTES_D_OPTIONS_ACCEPTEES_SANS_EFFET = frozenset({
    ("scan detect", "overwrite"),
    ("scan calibrate", "lot_slug"),
    ("scan calibrate", "nouvelle_version"),
    ("scan calibrate", "overwrite"),
    ("makepdf calibration-page", "nouvelle_version"),
})


class _Parseur:
    """Un noeud de l'arbre des parseurs, tel que `main` le construit."""

    def __init__(self, libelle, parent):
        self.libelle = libelle
        self.parent = parent
        self.dests: set[str] = set()
        self.fonction: str | None = None

    @property
    def chemin(self) -> str:
        prefixe = f"{self.parent.chemin} " if self.parent is not None else ""
        return (prefixe + (self.libelle or "?")).strip()

    @property
    def herites(self) -> set[str]:
        herites: set[str] = set()
        noeud = self.parent
        while noeud is not None:
            herites |= noeud.dests
            noeud = noeud.parent
        return herites


def _litteral(noeud, module) -> str | None:
    """La valeur d'une chaine ecrite en clair OU portee par une constante.

    Les libelles de sous-commande sont des constantes du module (`detect`
    vient de `scan_detect.SCAN_DETECT_SUBCOMMAND`) : les resoudre sur le
    MODULE plutot que dans le source evite d'en faire une seconde redaction.
    """
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    if isinstance(noeud, ast.Name):
        valeur = getattr(module, noeud.id, None)
        return valeur if isinstance(valeur, str) else None
    return None


def _dest_de(appel, module) -> str | None:
    """Le `dest` d'un `add_argument`, explicite ou derive du drapeau long.

    Rend `None` pour les actions qu'argparse traite lui-meme (`--version`,
    `--help`) : elles ne posent aucun attribut a lire.
    """
    for mot_cle in appel.keywords:
        if mot_cle.arg == "action":
            action = _litteral(mot_cle.value, module)
            if action in ("version", "help"):
                return None
    for mot_cle in appel.keywords:
        if mot_cle.arg == "dest":
            valeur = _litteral(mot_cle.value, module)
            if valeur:
                return valeur
    valeurs = [_litteral(argument, module) for argument in appel.args]
    longs = [v for v in valeurs if v and v.startswith("--")]
    if longs:
        return longs[0].lstrip("-").replace("-", "_")
    for valeur in valeurs:
        if valeur and not valeur.startswith("-"):
            return valeur.replace("-", "_")
    return None


def _arbre_des_parseurs(source: str, module) -> list[_Parseur]:
    """L'arbre des parseurs, lu au SOURCE et dans l'ORDRE des instructions.

    Lu au source parce que `main` construit son parseur en LOCAL et ne
    l'expose pas : un test qui tenterait de l'obtenir serait saute, c'est-a-dire
    vert sans rien mesurer (meme motif que
    `test_conformite_sorties_nommees._drapeaux_par_commande`).

    Lu dans l'ORDRE parce que `main` reemploie ses noms de variable -- `p13`
    designe successivement deux commandes. Une lecture par `ast.walk`, qui ne
    garantit aucun ordre, melangeait les options des deux.
    """
    arbre = ast.parse(source)
    main = next(n for n in arbre.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    liaisons: dict[str, object] = {}
    parseurs: list[_Parseur] = []

    def visiter(corps):
        for instruction in corps:
            if (isinstance(instruction, ast.Assign) and len(instruction.targets) == 1
                    and isinstance(instruction.targets[0], ast.Name)
                    and isinstance(instruction.value, ast.Call)):
                cible = instruction.targets[0].id
                appel = instruction.value
                fonction = appel.func
                if isinstance(fonction, ast.Attribute) and isinstance(fonction.value, ast.Name):
                    origine = liaisons.get(fonction.value.id)
                    if fonction.attr == "add_subparsers" and isinstance(origine, _Parseur):
                        # Un groupe de sous-parseurs n'est pas un parseur : il
                        # ne porte que le lien vers son proprietaire.
                        liaisons[cible] = ("sous-parseurs", origine)
                        continue
                    if fonction.attr == "add_parser":
                        proprietaire = (origine[1] if isinstance(origine, tuple) else None)
                        libelle = (_litteral(appel.args[0], module)
                                   if appel.args else None)
                        noeud = _Parseur(libelle, proprietaire)
                        liaisons[cible] = noeud
                        parseurs.append(noeud)
                        continue
                    if fonction.attr in ("add_mutually_exclusive_group",
                                         "add_argument_group") \
                            and isinstance(origine, _Parseur):
                        # **Un groupe est un ALIAS de sa commande.** Sans ce
                        # cas, `--lot` et `--rush` de `project remove` seraient
                        # invisibles.
                        liaisons[cible] = origine
                        continue
                if isinstance(fonction, ast.Attribute) and fonction.attr == "ArgumentParser":
                    racine = _Parseur("mmu", None)
                    liaisons[cible] = racine
                    parseurs.append(racine)
                    continue
            elif (isinstance(instruction, ast.Expr)
                  and isinstance(instruction.value, ast.Call)):
                appel = instruction.value
                fonction = appel.func
                if isinstance(fonction, ast.Attribute) and isinstance(fonction.value, ast.Name):
                    porteur = liaisons.get(fonction.value.id)
                    if isinstance(porteur, _Parseur):
                        if fonction.attr == "add_argument":
                            dest = _dest_de(appel, module)
                            if dest:
                                porteur.dests.add(dest)
                        elif fonction.attr == "set_defaults":
                            for mot_cle in appel.keywords:
                                if mot_cle.arg == "func" \
                                        and isinstance(mot_cle.value, ast.Name):
                                    porteur.fonction = mot_cle.value.id
            for champ in ("body", "orelse", "finalbody"):
                sous_corps = getattr(instruction, champ, None)
                if sous_corps:
                    visiter(sous_corps)

    visiter(main.body)
    return parseurs


def _attributs_lus(source: str, nom_de_fonction: str) -> set[str]:
    """Les attributs de l'objet `args` que la fonction lit, TRANSITIVEMENT.

    La transitivite n'est pas un raffinement : `scan_command` passe son `args`
    a `_ecrire_le_lot_detecte`, et une analyse locale l'aurait declaree
    ignorante de la moitie de ses propres options.
    """
    arbre = ast.parse(source)
    fonctions = {n.name: n for n in arbre.body if isinstance(n, ast.FunctionDef)}
    lus: set[str] = set()
    vus: set[tuple[str, str]] = set()
    a_faire = [(nom_de_fonction, "args")]
    while a_faire:
        nom, parametre = a_faire.pop()
        if (nom, parametre) in vus or nom not in fonctions:
            continue
        vus.add((nom, parametre))
        fonction = fonctions[nom]
        noms_de_parametres = [a.arg for a in fonction.args.args] \
            + [a.arg for a in fonction.args.kwonlyargs]
        if parametre not in noms_de_parametres:
            continue
        for noeud in ast.walk(fonction):
            if (isinstance(noeud, ast.Attribute)
                    and isinstance(noeud.value, ast.Name)
                    and noeud.value.id == parametre
                    and isinstance(noeud.ctx, ast.Load)):
                lus.add(noeud.attr)
            if not (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)):
                continue
            # `getattr(args, "x", defaut)` est une lecture, elle aussi.
            if (noeud.func.id == "getattr" and len(noeud.args) >= 2
                    and isinstance(noeud.args[0], ast.Name)
                    and noeud.args[0].id == parametre
                    and isinstance(noeud.args[1], ast.Constant)):
                lus.add(noeud.args[1].value)
            # ... et `args` passe a une autre fonction du module se suit.
            if noeud.func.id in fonctions:
                appelee = fonctions[noeud.func.id]
                positionnels = [a.arg for a in appelee.args.args]
                for rang, argument in enumerate(noeud.args):
                    if isinstance(argument, ast.Name) and argument.id == parametre \
                            and rang < len(positionnels):
                        a_faire.append((noeud.func.id, positionnels[rang]))
                for mot_cle in noeud.keywords:
                    if isinstance(mot_cle.value, ast.Name) \
                            and mot_cle.value.id == parametre and mot_cle.arg:
                        a_faire.append((noeud.func.id, mot_cle.arg))
    return lus


def _options_inertes(source: str, module) -> dict[tuple[str, str], str]:
    """Les couples (commande, option heritee) que la commande ne lit pas."""
    inertes: dict[tuple[str, str], str] = {}
    for parseur in _arbre_des_parseurs(source, module):
        if parseur.fonction is None:
            continue
        commande = parseur.chemin.removeprefix("mmu ").strip()
        lus = _attributs_lus(source, parseur.fonction)
        for dest in sorted(parseur.herites - lus):
            inertes[(commande, dest)] = parseur.fonction
    return inertes


@pytest.fixture(scope="module")
def source_de_la_cli() -> str:
    return Path(cli.__file__).read_text(encoding="utf-8")


def test_AUCUNE_option_d_un_parseur_parent_n_est_ignoree_par_sa_sous_commande(
        source_de_la_cli):
    """La frontiere du lot D, et son livrable le plus durable.

    Une option heritee qu'une commande ne lit jamais est acceptee **sans un
    mot** par argparse et sans effet par le produit : l'operateur croit
    demander quelque chose et n'obtient rien. C'est ce que
    `--nouvelle-version` faisait sur `scan detect`.
    """
    inertes = _options_inertes(source_de_la_cli, cli)
    non_inscrites = sorted(
        f"`mmu {commande}` accepte --{dest.replace('_', '-')} et ne le lit "
        f"jamais ({fonction})"
        for (commande, dest), fonction in inertes.items()
        if (commande, dest) not in REGISTRE_DES_OPTIONS_NON_LUES
    )
    assert non_inscrites == [], (
        "Option(s) INERTE(s) : acceptees par argparse, jamais lues par la "
        "commande. Les lire, ou les inscrire au registre avec leur motif :\n  "
        + "\n  ".join(non_inscrites))


def test_nouvelle_version_est_desormais_LUE_par_scan_detect(source_de_la_cli):
    """Le defaut nomme, mesure a l'endroit exact ou il vivait."""
    lus = _attributs_lus(source_de_la_cli, "scan_detect_command")
    assert "nouvelle_version" in lus, (
        "`scan_detect_command` ne lit toujours pas `args.nouvelle_version`")


def test_le_REGISTRE_ne_designe_que_des_options_reellement_INERTES(
        source_de_la_cli):
    """L'egalite dans l'autre sens : une inscription perimee rougit.

    Sans elle, le registre deviendrait la liste des options qu'on a un jour
    renonce a lire, et il grandirait sans jamais retrecir -- une frontiere qui
    ne fait que s'assouplir n'en est plus une.
    """
    inertes = _options_inertes(source_de_la_cli, cli)
    perimees = sorted(
        f"{commande} / {dest}"
        for (commande, dest) in REGISTRE_DES_OPTIONS_NON_LUES
        if (commande, dest) not in inertes
    )
    assert perimees == [], (
        "Inscription(s) perimee(s) au registre : l'option a disparu, ou elle "
        "est desormais LUE. Retirer la ligne :\n  " + "\n  ".join(perimees))


def test_les_DETTES_sont_exactement_celles_du_registre():
    """Les deux structures ne peuvent pas diverger en silence."""
    assert DETTES_D_OPTIONS_ACCEPTEES_SANS_EFFET <= set(REGISTRE_DES_OPTIONS_NON_LUES)
    for couple in DETTES_D_OPTIONS_ACCEPTEES_SANS_EFFET:
        assert REGISTRE_DES_OPTIONS_NON_LUES[couple].startswith("DETTE"), couple
    declarees = {couple for couple, motif in REGISTRE_DES_OPTIONS_NON_LUES.items()
                 if motif.startswith("DETTE")}
    assert declarees == DETTES_D_OPTIONS_ACCEPTEES_SANS_EFFET


def test_les_ensembles_MESURES_ne_sont_pas_VIDES(source_de_la_cli):
    """Volet symetrique de l'AC 4.3 : « le test rougit si la liste des `dest`
    du parent devient vide ».

    Une frontiere qui ne mesure plus rien est verte pour la mauvaise raison.
    Les deux ensembles sont donc gardes : celui des options heritees, et celui
    des attributs lus.
    """
    parseurs = {p.chemin: p for p in _arbre_des_parseurs(source_de_la_cli, cli)}
    detect = parseurs.get(f"mmu scan {cli.SCAN_DETECT_SUBCOMMAND}")
    assert detect is not None, sorted(parseurs)
    assert detect.fonction == "scan_detect_command"
    assert {"project", "scan", "dpi", "nouvelle_version", "lot_slug"} \
        <= detect.herites, sorted(detect.herites)
    assert detect.dests == set(), (
        "`detect` redeclare une option du parent, contre la convention du "
        "fichier -- la frontiere ci-dessus ne mesurerait plus le bon arbre")
    lus = _attributs_lus(source_de_la_cli, "scan_detect_command")
    assert {"project", "scan", "dpi", "lot_slug"} <= lus, sorted(lus)


_CLI_TEMOIN_INERTE = '''
def commande_temoin(args):
    return faire(args.project, dpi=args.dpi)

def main(argv=None):
    parser = argparse.ArgumentParser(prog="temoin")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("pere")
    p.add_argument("--project", required=True)
    p.add_argument("--dpi", type=int)
    p.add_argument("--nouvelle-version", action="store_true", dest="nouvelle_version")
    p_sub = p.add_subparsers(dest="sous")
    p_fils = p_sub.add_parser("fils")
    p_fils.set_defaults(func=commande_temoin)
'''

_CLI_TEMOIN_SAINE = _CLI_TEMOIN_INERTE.replace(
    "return faire(args.project, dpi=args.dpi)",
    "return faire(args.project, dpi=args.dpi, v=args.nouvelle_version)")


def test_la_frontiere_MORD_sur_une_cli_temoin_fautive():
    """« Une frontiere qui ne mord sur rien n'est pas une frontiere. »

    Le temoin est une CLI miniature qui reproduit exactement la forme du
    defaut : une option sur le pere, une sous-commande qui ne la lit pas. Il
    ne depend pas du source reel, donc il reste probant meme le jour ou
    `cli.py` sera corrige de bout en bout.
    """
    inertes = _options_inertes(_CLI_TEMOIN_INERTE, cli)
    assert ("pere fils", "nouvelle_version") in inertes, inertes


def test_la_frontiere_ne_mord_PAS_quand_le_temoin_LIT_son_option():
    """Volet symetrique : sans lui, une frontiere qui accuse tout le monde
    passerait le test precedent."""
    inertes = _options_inertes(_CLI_TEMOIN_SAINE, cli)
    assert ("pere fils", "nouvelle_version") not in inertes, inertes
    # ... et elle voit toujours les autres options du meme temoin.
    assert ("pere fils", "project") not in inertes


# ===========================================================================
# D4 -- la LIGNE D'EAU au retrait  (AC 4.4)
# ===========================================================================
#
# `EPIC11-ARB-92`, point 3 : un rang se CONSOMME, il ne se rend qu'en queue et
# **sur demande**. `EPIC11-ARB-108` : la ligne d'eau se pose au RETRAIT, pas
# seulement a la consommation -- sans quoi le rang est rendu par defaut des
# que le dossier disparait du disque.
#
# **LA GRAMMAIRE DU RETRAIT, et elle n'est pas negociable ici**
# (`EPIC11-ARB-234`, Egan le 2026-09-05, apres `EPIC11-ARB-224`) : `scan=`
# nomme la FAMILLE -- le nom du dossier PRIVE de son fragment `_vN` -- et
# `version=` porte le rang. `scan="S_v3"` est REFUSE par
# `project_maintenance._refuser_un_designateur_versionne`, et ce refus a son
# propre banc (`test_ARB224_un_designateur_qui_porte_un_fragment_est_refuse`,
# dans `test_suppression_element_de_projet.py`) : il ne se remesure pas ici.
# Les trois tests ci-dessous ont parle l'ancienne grammaire jusqu'au
# 2026-09-05 ; ce que la substitution devait etablir, et qui l'a ete par
# reinjection, c'est qu'ils visent toujours le MEME objet -- un `version=`
# devenu inerte les fait rougir tous les trois, chacun par une assertion
# differente.


def _projet_a_trois_versions(tmp_path, ligne_d_eau=None, famille_voisine=True):
    """Trois versions de scan de la famille `S`, plus une famille voisine.

    Regle des fabriques : **trois** elements distinguables (`S`, `S_v2`,
    `S_v3`), contenus differents, et une seconde famille (`T`) qui n'a rien a
    voir -- un resolveur qui melangerait les familles rendrait le meme rang
    des deux cotes, et une fabrique mono-famille ne le verrait jamais.
    """
    projet = tmp_path / "projet"
    project_layout.ensure_project_layout(projet)
    manifeste = {
        "schema_version": "2.1",
        "project_id": "projet",
        "rushes": [{"rush_id": "R"}],
        "lots": [{
            "lot_id": "L", "rush_id": "R", "fps_target": 12.5,
            "reconstructions": [
                {"ingest_slug": "S"}, {"ingest_slug": "S_v2"},
                {"ingest_slug": "S_v3"},
            ],
        }],
    }
    if ligne_d_eau is not None:
        manifeste["scan_version_watermarks"] = dict(ligne_d_eau)
    (projet / "project.json").write_text(
        json.dumps(manifeste, indent=2), encoding="utf-8")
    for rang, nom in enumerate(("S", "S_v2", "S_v3"), start=1):
        dossier = projet / "scans" / nom
        dossier.mkdir(parents=True)
        (dossier / "p.tiff").write_bytes(f"page du rang {rang}".encode())
    if famille_voisine:
        for nom in ("T", "T_v2"):
            (projet / "scans" / nom).mkdir(parents=True)
            (projet / "scans" / nom / "p.tiff").write_bytes(f"page {nom}".encode())
    source = tmp_path / "S"
    source.mkdir()
    cv2.imwrite(str(source / "p1.tiff"), _page())
    return projet, source


def _dossiers_de_scan(projet) -> list[str]:
    return sorted(c.name for c in (projet / "scans").iterdir() if c.is_dir())


def test_le_rang_de_la_QUEUE_retiree_ne_se_rend_PAS_par_defaut(tmp_path):
    """Le rang 3 a ete consomme : la prochaine version est la 4, pas la 3.

    C'est la mesure qui distingue une ligne d'eau LUE d'une ligne d'eau
    seulement ecrite : le dossier `S_v3` n'existe plus sur le disque, et seul
    le manifeste sait encore que le rang a servi.
    """
    projet, source = _projet_a_trois_versions(tmp_path)
    project_maintenance.remove_project_element(
        projet, lot_id="L", dry_run=False, scan="S", version=3)
    manifeste = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    assert manifeste["scan_version_watermarks"] == {"S": 3}, (
        "la ligne d'eau n'est pas posee au retrait : le reste du test ne "
        "mesurerait plus rien")

    assert _detecter(projet, source, "--lot-slug", "S", "--nouvelle-version") == 0

    assert "S_v4" in _dossiers_de_scan(projet), (
        "le rang 3 a ete RENDU par defaut, contre le point 3 d'EPIC11-ARB-92 : "
        f"dossiers presents {_dossiers_de_scan(projet)}")
    assert "S_v3" not in _dossiers_de_scan(projet)


def test_le_rang_du_MILIEU_retire_reste_lui_aussi_consomme(tmp_path):
    """Fabrique a trois versions, cible **au milieu** -- ni premiere ni
    derniere (`CLAUDE.md`, points 2 et 2 bis).

    La ligne d'eau declaree (5) est plus haute que tout ce que le disque
    montre : c'est ce qui rend la mesure discriminante. Un resolveur qui ne
    lirait que le disque rendrait 4.
    """
    projet, source = _projet_a_trois_versions(tmp_path, ligne_d_eau={"S": 5, "T": 9})
    project_maintenance.remove_project_element(
        projet, lot_id="L", dry_run=False, scan="S", version=2)
    assert not (projet / "scans" / "S_v2").exists()

    assert _detecter(projet, source, "--lot-slug", "S", "--nouvelle-version") == 0

    assert "S_v6" in _dossiers_de_scan(projet), (
        "la ligne d'eau du manifeste n'a pas ete lue : "
        f"dossiers presents {_dossiers_de_scan(projet)}")


def test_la_famille_VOISINE_n_est_ni_lue_ni_touchee(tmp_path):
    """Un resolveur qui melangerait les familles rendrait 10 pour `S` aussi."""
    projet, source = _projet_a_trois_versions(tmp_path, ligne_d_eau={"S": 5, "T": 9})
    avant = _empreinte(projet / "scans" / "T_v2" / "p.tiff")

    assert _detecter(projet, source, "--lot-slug", "S", "--nouvelle-version") == 0

    assert "S_v6" in _dossiers_de_scan(projet), _dossiers_de_scan(projet)
    assert "S_v10" not in _dossiers_de_scan(projet)
    assert _empreinte(projet / "scans" / "T_v2" / "p.tiff") == avant


def test_le_rang_se_rend_QUAND_on_le_demande(tmp_path):
    """Volet symetrique : « il ne se rend qu'en queue, **sur demande** ».

    Sans lui, une ligne d'eau posee trop haut passerait les trois tests
    ci-dessus, et la moitie liberatrice d'`EPIC11-ARB-92` serait perdue.
    """
    projet, source = _projet_a_trois_versions(tmp_path)
    rapport = project_maintenance.remove_project_element(
        projet, lot_id="L", dry_run=False, scan="S", version=3,
        liberer_le_rang=True)
    assert rapport.rangs_liberables == (3,)

    assert _detecter(projet, source, "--lot-slug", "S", "--nouvelle-version") == 0

    assert "S_v3" in _dossiers_de_scan(projet), (
        "le rang rendu n'a pas ete repris : "
        f"dossiers presents {_dossiers_de_scan(projet)}")
