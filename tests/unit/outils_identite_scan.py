# -*- coding: utf-8 -*-
"""Story 11.4b, **lot S6** -- le releve des observables de `mmu scan`.

**Ce module n'est pas un banc.** C'est l'instrument que le banc et la
**reference** emploient tous les deux, et c'est la seule facon d'obtenir une
mesure d'identite qui vaille quelque chose : le meme code de releve, joue une
fois sur le depot d'aujourd'hui et une fois sur le depot du `baseline_commit`,
sur des **entrees octet pour octet identiques**.

AC 10.1 de la fiche, verbatim : « `mmu scan` et `mmu scan write` rendent, a
arguments equivalents, **les memes codes de sortie**, **les memes messages** et
**les memes artefacts** qu'au `baseline_commit`. »

Trois proprietes de conception, chacune payee par un piege connu du depot :

1. **les commandes tournent pour de vrai.** Un releve qui se contenterait de
   verifier que l'enveloppe appelle le coeur ne mesurerait qu'un cablage, et un
   cablage identique peut produire des artefacts differents. Ici c'est
   `cli.main([...])` qui est appele, et ce sont les octets ecrits, les lignes
   imprimees et l'entier rendu qui sont releves ;
2. **ce module n'importe rien du paquet de tests.** Il doit tourner sous le
   `src/` du `baseline_commit`, ou les fabriques d'aujourd'hui n'existent pas et
   ou un `sys.path.insert` d'un module de test ferait revenir le `src/`
   d'aujourd'hui par la fenetre. Il ne connait que `mixed_media_utility.cli` et
   la bibliotheque standard ; **les entrees lui sont donnees**, deja ecrites ;
3. **rien n'est neutralise sans motif ecrit.** Chaque champ volatil est nomme
   un a un ci-dessous avec la raison de sa volatilite. Un motif large -- « tout
   ce qui ressemble a une date » -- rendrait la comparaison verte en cessant
   d'observer.

Emploi, et c'est ainsi que la reference se regenere (le geste est ecrit ici
plutot que dans un compte rendu, parce qu'il devra etre rejoue) :

```
# 1. fabriquer les entrees avec les fabriques D'AUJOURD'HUI, une seule fois
python3 tests/unit/fabriquer_les_entrees_d_identite.py <entrees>

# 2. les rejouer sous le src du baseline, dans un worktree detache
GIT_LFS_SKIP_SMUDGE=1 git worktree add --detach <base> <baseline_commit>
PYTHONPATH=<base>/src python3 tests/unit/outils_identite_scan.py \
    --entrees <entrees> --travail <tmp> --sortie <reference.json>
```

Le releve produit par l'etape 2 est la **reference** ; le banc
`test_identite_du_scan.py` rejoue l'etape 2 sous le `src/` d'aujourd'hui et
compare les deux dossiers **chemin par chemin**.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

# ---------------------------------------------------------------------------
# Ce que le releve neutralise, et **pourquoi** -- un motif par ligne
# ---------------------------------------------------------------------------

#: Les cles de document JSON dont la valeur ne peut pas coincider d'une passe a
#: l'autre. Chacune est nommee **entierement** (aucun motif ouvert) et porte son
#: motif : un motif large rendrait la comparaison verte en cessant d'observer.
#:
#: * `created` / `updated` -- l'instant de creation et de derniere ecriture de
#:   l'arborescence projet, poses par `project_layout` et par le manifest ;
#: * `generated_at_utc` -- l'instant d'ecriture d'un document de detection ;
#: * `created_at` / `measured_at` -- les horodates d'un document de profil ;
#: * `designated_at` -- l'instant ou un profil a ete verse au projet, pose par
#:   `io/profile_designation` sur chaque entree de `color.calibration_profiles` ;
#: * `confirmed_at` -- l'instant de la confirmation d'un lot d'extraction, pose
#:   par `io/extraction_manifest` (bloc `makepdf`, qui commence par deux
#:   `mmu extract`).
#:
#: Les deux dernieres sont **mesurees et non supposees** : ce sont les seules
#: que la comparaison de deux passes du **meme** commit a fait diverger.
#:
#: Rien d'autre. En particulier **aucun chemin n'est neutralise** : ils sont
#: normalises (voir `_normaliser`), donc ils doivent coincider, et leur
#: divergence serait un vrai defaut.
CLES_VOLATILES = ("created", "updated", "generated_at_utc", "created_at",
                  "measured_at", "designated_at", "confirmed_at")

#: Le prefixe d'horodatage que `_configure_scan_logger` pose sur chaque ligne du
#: journal (`%(asctime)s [%(levelname)s] `). Il est retire, le **niveau et le
#: message** sont gardes : c'est le message qui est l'observable.
_HORODATE_DE_JOURNAL = re.compile(
    r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} (\[[A-Z]+\] )")

#: Le **nom de fichier** d'un document de detection porte l'instant de son
#: ecriture (`detect-20260830T031901Z.json`). C'est le seul nom volatil du
#: releve : il est masque, jamais le dossier ni le prefixe -- un document ecrit
#: ailleurs, ou nomme autrement, resterait donc visible.
_NOM_DE_DETECTION = re.compile(r"detect-\d{8}T\d{6}Z")

#: Un instant ISO-8601 UTC **ecrit dans un message**. Il n'y en a qu'un dans
#: tout le releve -- le `confirmed_at=...` que `mmu extract` imprime et
#: journalise --, et c'est le meme fait que la cle de manifest neutralisee
#: ci-dessus : deux emplacements pour le meme instant. La forme reconnue est
#: **complete** (date, heure, `Z`) : un motif plus large avalerait des
#: cardinaux, des dpi ou des identifiants de lot, et la comparaison cesserait
#: d'observer la ligne au lieu d'en neutraliser l'horodate.
_INSTANT_ISO = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")

#: Le fragment `(choose from ...)` qu'`argparse` ecrit sur un `invalid choice`.
#: C'est le SEUL observable du releve dont la forme appartient a la
#: bibliotheque standard plutot qu'au produit, et CPython l'a change EN COURS
#: de serie -- pas d'une version majeure a l'autre, ce que la matrice de CI
#: aurait vu, mais d'un correctif a l'autre :
#:
#:     3.11.15  ... (choose from 'dnxhr_hq', 'dnxhr_hqx', ...)
#:     3.12.3   ... (choose from 'dnxhr_hq', 'dnxhr_hqx', ...)
#:     3.12.11  ... (choose from dnxhr_hq, dnxhr_hqx, ...)
#:     3.13.7   ... (choose from dnxhr_hq, dnxhr_hqx, ...)
#:     3.13.12  ... (choose from dnxhr_hq, dnxhr_hqx, ...)
#:
#: Mesure du 2026-09-08, cinq interpreteurs, meme parseur reconstruit a
#: l'identique. Le depot classe 3.11, 3.12 et 3.13 : une reference figee sur
#: l'une des deux formes rend le scenario `22-profil-inconnu` rouge sur l'autre,
#: ce qui est exactement ce qu'un job 3.12 de la CI publique a rendu alors que
#: le meme arbre etait vert ici -- le conteneur porte 3.12.3, le runner un
#: correctif plus recent.
#:
#: La canonisation ramene a la forme QUOTEE, celle que porte la reference, pour
#: qu'aucun fichier de reference n'ait a etre regenere. Elle porte sur la seule
#: PONCTUATION : la liste des choix, elle, reste comparee element par element,
#: donc un profil qui disparaitrait du produit ferait toujours rougir. Les deux
#: sens sont mesures dans `test_encode_noyau.py`.
_CHOIX_ARGPARSE = re.compile(r"\(choose from ([^)]*)\)")


def _choix_canonises(ligne: str) -> str:
    """Ramener `(choose from ...)` a la forme quotee, quel que soit CPython."""
    def _quoter(trouve: "re.Match[str]") -> str:
        choix = [mot.strip().strip("'\"")
                 for mot in trouve.group(1).split(",")]
        return "(choose from " + ", ".join(f"'{mot}'" for mot in choix) + ")"

    return _CHOIX_ARGPARSE.sub(_quoter, ligne)


def _sans_horodate(ligne: str) -> str:
    return _HORODATE_DE_JOURNAL.sub(r"\1", ligne)


#: L'instant que le bloc `makepdf` fait lire a `cli.datetime.now`. Il est fige
#: parce que **le PDF porte sa date imprimee sur chaque planche**
#: (`pdf_render.render_lot_pdf`, `genere le %Y-%m-%d %H:%M %Z`) : sans ce gel,
#: deux passes separees par une minute rendent deux documents differents, et la
#: reference versionnee serait perimee des le lendemain de son ecriture.
#:
#: Le gel est **nomme et applique des deux cotes a l'identique** : `cli.py`
#: importe `datetime` de la meme facon au `baseline_commit` et aujourd'hui
#: (`from datetime import datetime, timezone`, ligne 16 des deux cotes), donc
#: la substitution atteint exactement le meme site.
#:
#: **ET IL PORTE DESORMAIS SUR DEUX MODULES, parce qu'un seul ne suffit plus**
#: (mesure du 2026-09-02). Le deplacement du corps de `makepdf` au coeur
#: (commit `f9cc6623`) a emporte avec lui les trois `datetime.now(timezone.utc)`
#: qui datent la planche : ils vivent maintenant dans
#: `mixed_media_utility.makepdf`, ou la substitution de `cli.datetime`
#: n'atteignait plus rien. La consequence n'est pas theorique et elle a ete
#: mesuree : trois passes du bloc `makepdf` ont rendu **trois** condensats
#: differents pour le meme PDF -- egaux entre elles dans la meme minute,
#: differentes d'une minute a l'autre --, parce que la ligne « genere le
#: %Y-%m-%d %H:%M %Z » imprimee sur chaque planche a la **minute** pour
#: granularite. Le seul banc qui l'a vu est l'egalite directe de l'AC 6.4
#: (« la v1 revient au condensat du baseline ») : partout ailleurs le PDF
#: tombe sous la tolerance du renommage d'`EPIC11-ARB-171`, qui excuse tout
#: chemin de tirage.
#:
#: **La liste des modules est donc la mesure**, et elle est nommee plutot que
#: devinee : un quatrieme deplacement de ce corps ailleurs redonnerait le meme
#: defaut, et c'est `MODULES_A_HORLOGE_FIGEE` qu'il faudra alors completer.
INSTANT_FIGE = (2026, 1, 2, 3, 4, 5)

#: Les modules dont l'attribut `datetime` est substitue le temps d'une
#: invocation a horloge figee. **`cli` ne suffit plus** : voir ci-dessus.
MODULES_A_HORLOGE_FIGEE = ("cli", "makepdf")


class HorlogeFigee:
    """Le `datetime` que `cli` voit pendant le bloc `makepdf`.

    Seul `now(tz)` est employe par le chemin mesure ; le reste de la classe
    reste celui de la bibliotheque standard, `HorlogeFigee` n'etant substituee
    qu'a l'attribut de module et jamais au type.
    """

    @staticmethod
    def now(tz=None):
        import datetime as _datetime
        return _datetime.datetime(*INSTANT_FIGE, tzinfo=tz)


def geler_le_rendu_pdf() -> bool:
    """Rendre le PDF de `reportlab` **reproductible**, et dire si on y arrive.

    **Mesure, pas suppose** (2026-08-30, quatre passes de `makepdf` sur le meme
    lot et le meme commit) :

    | regime | deux passes rendent-elles les memes octets ? |
    | --- | --- |
    | aucun gel | **non** |
    | horloge figee seule | **non** -- `reportlab` pose son propre `/ID` et son `/CreationDate` |
    | `rl_config.invariant` seul | **oui**, mais seulement **dans la meme minute** : la ligne « genere le ... » imprimee sur la planche a la minute pour granularite |
    | horloge figee **et** `invariant` | **oui**, et stable dans le temps |

    Les deux gels sont donc necessaires **ensemble**, et c'est le second qui
    rend une reference versionnee valable au-dela de la minute ou elle a ete
    ecrite. Aucun des deux ne touche le code mesure : `invariant` est un
    reglage de la dependance, l'horloge est une substitution d'attribut faite
    par l'appelant -- exactement ce qu'une interface ferait.

    Rend `False` si la version de `reportlab` installee n'expose pas le
    reglage ; le banc a alors une mesure qui le lui dit, plutot qu'une
    comparaison qui echoue sans motif.
    """
    try:
        from reportlab import rl_config
    except ImportError:                                  # pragma: no cover
        return False
    if not hasattr(rl_config, "invariant"):              # pragma: no cover
        return False
    rl_config.invariant = 1
    return True


class FluxTty:
    """Un flux que `cli._stdin_is_interactive` reconnait comme un terminal.

    Il existe pour l'unique raison qui rend les invites `Y/N` mesurables : le
    regime 3 (« en terminal interactif ») ne se distingue du regime 2 que par ce
    predicat, et un banc qui ne le franchirait pas ne verrait **jamais** de
    question -- il mesurerait le regime 2 en croyant mesurer le regime 3.
    """

    def __init__(self, reponses=()) -> None:
        self._reponses = list(reponses)

    def isatty(self) -> bool:
        return True

    def readline(self) -> str:
        return self._reponses.pop(0) if self._reponses else ""

    def read(self, *args) -> str:
        return ""


# ---------------------------------------------------------------------------
# Normalisation : ce qui change d'une machine a l'autre sans rien dire
# ---------------------------------------------------------------------------

def _remplacements(travail: Path, entrees: Path) -> list[tuple[str, str]]:
    """Les chemins absolus a masquer, **du plus long au plus court**.

    L'ordre compte : `<travail>/projets` est un prefixe de rien, mais le
    resolu et le non-resolu d'un meme dossier peuvent l'etre l'un de l'autre.
    """
    couples = []
    for jeton, chemin in (("<TRAVAIL>", travail), ("<ENTREES>", entrees)):
        for variante in {str(chemin), str(chemin.resolve())}:
            couples.append((variante, jeton))
    return sorted(couples, key=lambda couple: -len(couple[0]))


def _normaliser(valeur, remplacements):
    """Masquer chemins absolus, horodates, et canoniser la ponctuation d'argparse.

    Trois neutralisations, et **trois seulement** : les chemins de la machine,
    les instants (nom de document et instant ecrit dans un message), et le
    fragment `(choose from ...)` dont CPython a change la ponctuation en cours
    de serie (voir `_CHOIX_ARGPARSE`). Tout le reste est compare tel quel.
    """
    if not isinstance(valeur, str):
        return valeur
    for brut, jeton in remplacements:
        valeur = valeur.replace(brut, jeton)
    return _choix_canonises(
        _INSTANT_ISO.sub("<INSTANT>",
                         _NOM_DE_DETECTION.sub("detect-<HORODATE>", valeur)))


def _aplatir(valeur, prefixe: str = "") -> dict:
    """Un document JSON -> `chemin pointe -> feuille`.

    Aplatir plutot que comparer deux `dict` : l'egalite de deux documents dit
    seulement qu'ils different, jamais **ou**. Le banc doit pouvoir nommer
    l'ensemble exact des chemins divergents, donc il lui faut des chemins.
    """
    if isinstance(valeur, dict):
        aplati: dict = {}
        for cle, sous in valeur.items():
            aplati.update(_aplatir(sous, f"{prefixe}.{cle}" if prefixe else cle))
        return aplati or {prefixe: "<objet vide>"}
    if isinstance(valeur, list):
        aplati = {}
        for rang, sous in enumerate(valeur):
            aplati.update(_aplatir(sous, f"{prefixe}[{rang}]"))
        return aplati or {prefixe: "<liste vide>"}
    return {prefixe: valeur}


def _document(chemin: Path, remplacements) -> dict:
    """Un document JSON du projet, aplati, normalise et prive des volatiles."""
    try:
        brut = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:      # pragma: no cover
        return {"<illisible>": f"{type(exc).__name__}"}
    return {
        cle: _normaliser(feuille, remplacements)
        for cle, feuille in _aplatir(brut).items()
        if cle.rsplit(".", 1)[-1] not in CLES_VOLATILES
    }


def _empreinte_du_projet(projet: Path, remplacements) -> dict:
    """Tout ce que la commande a laisse sur le disque, en trois familles.

    * `arbre` -- chemin **relatif** -> condensat, pour tout ce qui n'est ni un
      document JSON ni un journal : les TIFF de sortie, les copies ingerees du
      scan. Relatif et non le seul nom : le dossier de lot fait partie de
      l'artefact, et deux lots intervertis ne se voient nulle part ailleurs ;
    * `documents` -- chaque JSON du projet, **aplati** : le manifest, les
      documents de detection, les profils. Un condensat de manifest dirait
      seulement qu'il diverge ; un aplatissement dit **ou** ;
    * `journaux` -- les lignes de `logs/`, horodate retiree. La sequence
      d'ecriture a change de module au lot S1 : c'est ici que se verrait une
      ligne de journal perdue en chemin.
    """
    arbre: dict = {}
    documents: dict = {}
    journaux: dict = {}
    if not projet.is_dir():
        return {"arbre": arbre, "documents": documents, "journaux": journaux,
                "existe": False}
    for chemin in sorted(projet.rglob("*")):
        if not chemin.is_file():
            continue
        relatif = _normaliser(str(chemin.relative_to(projet)),
                              remplacements)
        if chemin.suffix == ".json":
            documents[relatif] = _document(chemin, remplacements)
        elif chemin.suffix == ".log":
            journaux[relatif] = [
                _normaliser(_sans_horodate(ligne), remplacements)
                for ligne in chemin.read_text(encoding="utf-8").splitlines()]
        else:
            arbre[relatif] = hashlib.sha256(chemin.read_bytes()).hexdigest()
    return {"arbre": arbre, "documents": documents, "journaux": journaux,
            "existe": True}


# ---------------------------------------------------------------------------
# Le releveur
# ---------------------------------------------------------------------------

class Releve:
    """Le dossier d'observables en construction.

    Un scenario = **une invocation de la CLI**, relevee entierement : le code de
    sortie, `stdout` et `stderr` au caractere pres, et l'etat du projet apres.
    """

    def __init__(self, entrees: Path, travail: Path) -> None:
        self.entrees = entrees
        self.travail = travail
        self.remplacements = _remplacements(travail, entrees)
        self.scenarios: dict = {}

    # -- les entrees, recopiees fraiches pour chaque projet ------------------
    def copier(self, nom: str, source: str) -> Path:
        cible = self.travail / "entrees" / nom
        if cible.exists():
            shutil.rmtree(cible)
        shutil.copytree(self.entrees / source, cible)
        return cible

    def projet(self, nom: str) -> Path:
        return self.travail / "projets" / nom

    # -- l'invocation --------------------------------------------------------
    def jouer(self, nom: str, argv: list[str], *, projet: Path,
              reponses=None, origines=(), horloge_figee: bool = False) -> int:
        """Jouer une invocation de `cli.main` et relever tout ce qui en sort.

        `reponses` non `None` monte un `stdin` que le predicat d'interactivite
        reconnait : c'est le seul commutateur entre les trois regimes des deux
        invites `Y/N`, et il est passe par le scenario plutot que devine.

        `horloge_figee` substitue `HorlogeFigee` a l'attribut `datetime` de
        **chacun** des `MODULES_A_HORLOGE_FIGEE` -- `cli` et `makepdf` --, **le
        temps de cette invocation seulement**. Les deux sont necessaires
        ensemble depuis que le corps de `makepdf` a quitte `cli.py` : le
        motif est ecrit au long avec `INSTANT_FIGE`. Il n'est pose que sur le
        bloc `makepdf`, seul chemin dont l'artefact porte une date : le poser
        partout changerait des observables que la reference du
        `baseline_commit` porte deja.

        `origines` nomme les projets dont celui-ci est une **copie**. Les uns et
        les autres se lisent alors `<PROJET>`, si bien que six regimes joues sur
        six copies du meme socle restent comparables entre eux : sans cette
        equivalence, chaque regime divergerait par le seul nom de son dossier et
        la mesure ne dirait plus rien.
        """
        from mixed_media_utility import cli

        remplacements = sorted(
            self.remplacements
            + [(variante, "<PROJET>")
               for chemin in (projet, *origines)
               for variante in {str(chemin), str(Path(chemin).resolve())}],
            key=lambda couple: -len(couple[0]))

        # Les modules sont importes ICI plutot qu'en tete : `outils_identite_scan`
        # est un instrument rejoue sous le `src/` d'une AUTRE branche, ou
        # `makepdf` peut ne pas exister encore -- il est neuf du commit
        # `f9cc6623`. L'absence se lit alors comme « rien a geler la-bas »,
        # jamais comme un plantage de l'instrument.
        from importlib import import_module
        horloges: list[tuple[object, object]] = []
        for nom_de_module in MODULES_A_HORLOGE_FIGEE:
            try:
                module = import_module(f"mixed_media_utility.{nom_de_module}")
            except ImportError:                          # pragma: no cover
                continue
            horloges.append((module, getattr(module, "datetime", None)))

        sortie, erreur = io.StringIO(), io.StringIO()
        vrai_stdin = sys.stdin
        if reponses is not None:
            sys.stdin = FluxTty(reponses)
        if horloge_figee:
            for module, _ in horloges:
                module.datetime = HorlogeFigee
        try:
            with redirect_stdout(sortie), redirect_stderr(erreur):
                code = cli.main(argv)
        except SystemExit as exc:                        # argparse
            code = exc.code
        finally:
            sys.stdin = vrai_stdin
            for module, vraie_horloge in horloges:
                if vraie_horloge is not None:
                    module.datetime = vraie_horloge

        self.scenarios[nom] = {
            "argv": [_normaliser(mot, remplacements) for mot in argv],
            "regime_stdin": ("terminal" if reponses is not None
                             else "hors terminal"),
            "horloge_figee": bool(horloge_figee),
            "reponses": list(reponses or ()),
            "code": code,
            "stdout": [_normaliser(ligne, remplacements)
                       for ligne in sortie.getvalue().splitlines()],
            "stderr": [_normaliser(ligne, remplacements)
                       for ligne in erreur.getvalue().splitlines()],
            "projet": _empreinte_du_projet(projet, remplacements),
        }
        return code


# ---------------------------------------------------------------------------
# Les entrees nommees, et les deux fichiers que le releve doit retrouver
# ---------------------------------------------------------------------------

#: Le dpi de tout le releve. Il est celui des entrees, et il est nomme une fois :
#: deux redactions divergeraient, et l'ecart se verrait sur la geometrie.
DPI = "300"

#: Le nom de la commande de second temps. Il est ecrit **en clair** et non lu de
#: `cli.SCAN_WRITE_COMMAND` : un nom de commande qui changerait serait
#: precisement un changement observable, et le lire du module a mesurer le
#: rendrait invisible.
COMMANDE_ECRITURE = "scan-write"


def _profil_unique(projet: Path) -> Path:
    """Le profil consigne par `scan ... calibrate`, dont le cardinal est verifie.

    Un projet qui en porterait deux rendrait le raccourci ambigu, et un scenario
    qui en designerait « un » ne prouverait plus lequel.
    """
    (profil,) = sorted((projet / "versions" / "calibration").glob("*.json"))
    return profil


def _detection_unique(projet: Path) -> Path:
    """Le document de detection ecrit par `scan ... detect`, cardinal verifie."""
    (document,) = sorted((projet / "scans").rglob("detections/*.json"))
    return document


def _source_ingeree(projet: Path, document: Path) -> Path:
    """Le fichier source de la **seconde** page du document.

    La seconde et non la premiere (regle des fabriques) : un refus qui ne
    regarderait que la premiere page de la pile ne se demasque pas autrement.
    """
    pages = json.loads(document.read_text(encoding="utf-8"))["pages"]
    return projet / pages[1]["source"]["path_relative"]


# ---------------------------------------------------------------------------
# Le releve lui-meme : un scenario = une invocation
# ---------------------------------------------------------------------------

def collecter(entrees: Path, travail: Path) -> dict:
    """Jouer toutes les commandes de scan et rendre le dossier d'observables.

    L'ordre des blocs suit ce qu'ils mesurent, pas la commodite :

    * **bloc 1** -- les deux voies sur un projet a **deux lots**, la cible en
      seconde position, jusqu'au refus de reecriture et a son contournement ;
    * **bloc 2** -- l'invite de correction dans ses **trois** regimes, plus les
      deux drapeaux qui la court-circuitent ;
    * **bloc 3** -- les **huit** refus nommes de `scan write`, chacun sur son
      propre exemplaire du socle ;
    * **bloc 4** -- l'invite d'ecrasement de profil dans ses **trois** regimes.

    Les blocs 2 a 4 rejouent tous le **meme socle** (calibration + detection du
    lot B), recopie a l'identique avant chaque regime : c'est ce qui rend les
    regimes comparables **entre eux** autant qu'au `baseline_commit`.
    """
    travail.mkdir(parents=True, exist_ok=True)
    rendu_pdf_gele = geler_le_rendu_pdf()
    releve = Releve(entrees, travail)
    calibration = entrees / "calibration"
    lot_a, lot_b = entrees / "lot-a", entrees / "lot-b"
    lot_etranger = entrees / "lot-etranger"

    def calibrer(nom: str, projet: Path):
        return releve.jouer(nom, ["scan", "--project", str(projet), "--scan",
                                  str(calibration), "--dpi", DPI, "calibrate"],
                            projet=projet)

    def detecter(nom: str, projet: Path, source: Path):
        return releve.jouer(nom, ["scan", "--project", str(projet), "--scan",
                                  str(source), "--dpi", DPI, "detect"],
                            projet=projet)

    # -- bloc 1 : les deux voies, deux lots, la cible en second ---------------
    p1 = releve.projet("p1")
    calibrer("01_calibrate", p1)
    profil_p1 = _profil_unique(p1)
    releve.jouer("02_scan_dun_bloc_lot_a",
                 ["scan", "--project", str(p1), "--scan", str(lot_a),
                  "--dpi", DPI, "--profil", str(profil_p1)], projet=p1)
    detecter("03_detect_lot_b", p1, lot_b)
    document_p1 = _detection_unique(p1)
    ecriture_p1 = [COMMANDE_ECRITURE, "--project", str(p1),
                   "--detection", str(document_p1), "--profil", str(profil_p1)]
    releve.jouer("04_write_lot_b", list(ecriture_p1), projet=p1)
    releve.jouer("05_write_rejoue_REFUS", list(ecriture_p1), projet=p1)
    releve.jouer("06_write_overwrite", ecriture_p1 + ["--overwrite"], projet=p1)
    # Le refus de `check_scan_conflicts` sur le chemin de detection : une pile
    # d'un **autre** rush, posee dans un projet qui en porte deja un. Le motif
    # est chiffre et nomme les deux rushes -- c'est un message que le lot S1 a
    # fait voyager avec le corps, et le seul endroit du releve ou il tombe.
    detecter("07_detect_lot_ETRANGER_REFUS", p1, lot_etranger)

    # -- le socle des blocs 2 a 4 --------------------------------------------
    socle = releve.projet("socle")
    calibrer("10_socle_calibrate", socle)
    detecter("11_socle_detect_lot_b", socle, lot_b)
    intact = travail / "socle-intact"
    if intact.exists():
        shutil.rmtree(intact)
    shutil.copytree(socle, intact)

    def depuis_le_socle(nom: str) -> Path:
        cible = releve.projet(nom)
        if cible.exists():
            shutil.rmtree(cible)
        shutil.copytree(intact, cible)
        return cible

    def ecrire(nom: str, *options: str, reponses=None, projet=None,
               document=None, profil=None, origines=()):
        cible = projet if projet is not None else depuis_le_socle(nom)
        argv = [COMMANDE_ECRITURE, "--project", str(cible), "--detection",
                str(document if document is not None
                    else _detection_unique(cible)),
                "--profil", str(profil if profil is not None
                                else _profil_unique(cible)),
                *options]
        return releve.jouer(nom, argv, projet=cible, reponses=reponses,
                            origines=(socle, intact, *origines))

    # -- bloc 2 : l'invite de correction, trois regimes + deux drapeaux ------
    #
    # Regime 2 (hors terminal) : aucune invite, defaut appliquer.
    ecrire("20_invite_HORS_TERMINAL")
    # Regime 3 (terminal) : l'invite est posee. Trois reponses, dont l'entree
    # vide -- « l'operateur qui frappe Entree », dont le defaut est appliquer.
    ecrire("21_invite_TERMINAL_entree_vide", reponses=["\n"])
    ecrire("22_invite_TERMINAL_oui", reponses=["o\n"])
    ecrire("23_invite_TERMINAL_non", reponses=["n\n"])
    # Regime 1 (drapeau explicite) : la decision est deja prise, **et le
    # terminal est la** -- c'est le seul montage ou « aucune invite » mesure le
    # drapeau plutot que l'absence de terminal.
    ecrire("24_drapeau_cc_off_EN_TERMINAL", "--cc", "off", reponses=["n\n"])
    ecrire("25_drapeau_brut_EN_TERMINAL", "--garder-le-scan-brut",
           reponses=["n\n"])

    # -- bloc 3 : les huit refus nommes de `scan write` -----------------------
    cible = depuis_le_socle("30_document_INTROUVABLE")
    ecrire("30_document_INTROUVABLE", projet=cible,
           document=cible / "scans" / "aucun-document.json")

    cible = depuis_le_socle("31_json_INVALIDE")
    casse = cible / "scans" / "casse.json"
    casse.write_text("{ ceci n'est pas du JSON", encoding="utf-8")
    ecrire("31_json_INVALIDE", projet=cible, document=casse)

    cible = depuis_le_socle("32_PAS_une_previz")
    etranger = cible / "scans" / "etranger.json"
    etranger.write_text(json.dumps({"schema": "autre-chose", "pages": []}),
                        encoding="utf-8")
    ecrire("32_PAS_une_previz", projet=cible, document=etranger)

    cible = depuis_le_socle("33_ETAT_inattendu")
    document = _detection_unique(cible)
    brut = json.loads(document.read_text(encoding="utf-8"))
    brut["state"] = "written"
    document.write_text(json.dumps(brut), encoding="utf-8")
    ecrire("33_ETAT_inattendu", projet=cible, document=document)

    cible = depuis_le_socle("34_document_ANTERIEUR")
    document = _detection_unique(cible)
    brut = json.loads(document.read_text(encoding="utf-8"))
    # La **seconde** page perd son condensat : un refus qui ne balaierait que la
    # premiere page passerait sur une pile ou la premiere est fautive.
    brut["pages"][1]["source_digest"] = None
    document.write_text(json.dumps(brut), encoding="utf-8")
    ecrire("34_document_ANTERIEUR", projet=cible, document=document)

    cible = depuis_le_socle("35_source_MANQUANTE")
    _source_ingeree(cible, _detection_unique(cible)).unlink()
    ecrire("35_source_MANQUANTE", projet=cible)

    cible = depuis_le_socle("36_source_REMPLACEE")
    source = _source_ingeree(cible, _detection_unique(cible))
    source.write_bytes(source.read_bytes() + b"\x00")
    ecrire("36_source_REMPLACEE", projet=cible)

    cible = depuis_le_socle("37_AUCUNE_page_identifiee")
    document = _detection_unique(cible)
    brut = json.loads(document.read_text(encoding="utf-8"))
    for page in brut["pages"]:
        page["payload"] = None
        page["page_index"] = None
    document.write_text(json.dumps(brut), encoding="utf-8")
    ecrire("37_AUCUNE_page_identifiee", projet=cible, document=document)

    # -- bloc 4 : l'invite d'ecrasement de profil, trois regimes --------------
    #
    # Deux profils qui portent la **meme etiquette** et deux chaines
    # differentes : c'est la seule forme de collision que
    # `calibration_profile.write_profile` connaisse, et le seul chemin du depot
    # par lequel un profil mesure est perdu.
    profils = travail / "profils"
    profils.mkdir(exist_ok=True)
    modele = json.loads(_profil_unique(socle).read_text(encoding="utf-8"))
    alpha = dict(modele, label="chaine du banc")
    beta = dict(modele, label="chaine du banc",
                chain_id="300-tiff-000000000042")
    (profils / "alpha.json").write_text(json.dumps(alpha), encoding="utf-8")
    (profils / "beta.json").write_text(json.dumps(beta), encoding="utf-8")

    pose = depuis_le_socle("40_profil_ALPHA_pose")
    ecrire("40_profil_ALPHA_pose", projet=pose,
           profil=profils / "alpha.json")
    occupe = travail / "socle-a-profil-occupe"
    if occupe.exists():
        shutil.rmtree(occupe)
    shutil.copytree(pose, occupe)

    def ecraser(nom: str, reponses):
        cible = releve.projet(nom)
        if cible.exists():
            shutil.rmtree(cible)
        shutil.copytree(occupe, cible)
        return ecrire(nom, "--overwrite", projet=cible, reponses=reponses,
                      profil=profils / "beta.json",
                      origines=(pose, occupe))

    # **Deux** reponses par regime, et ce n'est pas de la prudence : en
    # terminal, la passe pose les DEUX invites -- l'ecrasement d'abord, la
    # correction ensuite. Une seule reponse laisserait la seconde tomber sur une
    # fin de flux, et le regime de la seconde ne serait plus choisi par le
    # scenario mais subi.
    ecraser("41_ecrasement_HORS_TERMINAL", None)
    ecraser("42_ecrasement_TERMINAL_oui", ["o\n", "\n"])
    ecraser("43_ecrasement_TERMINAL_non", ["n\n", "\n"])

    # -- bloc 5 : les autres familles de la table des codes de sortie ---------
    #
    # Le bloc 3 ci-dessus ne touche que les gardes de LECTURE du document, qui
    # rendent toutes leur refus sans jamais entrer dans le coeur. La campagne
    # d'injection du lot S6 l'a mesure : un code de sortie change sur
    # `ReconstructionError` **survivait**, aucun scenario ne faisant lever cette
    # famille-la a travers `scan write`. Les quatre scenarios qui suivent
    # existent pour ca, et chacun fait tomber une famille differente.

    # `ReconstructionError` -- « la garantie que detect a donnee hier ne dit
    # rien du manifest d'aujourd'hui », verbatim du docstring de la commande.
    # Le document du lot etranger est produit dans un projet NEUF, ou aucun
    # manifest ne s'y oppose, puis consomme dans un projet qui porte deja un
    # autre rush : c'est le seul montage qui atteigne cette garde par la CLI.
    jumeau = releve.projet("50a_detect_lot_etranger_en_projet_NEUF")
    detecter("50a_detect_lot_etranger_en_projet_NEUF", jumeau, lot_etranger)
    document_etranger = _detection_unique(jumeau)

    cible = depuis_le_socle("50b_write_document_ETRANGER_au_manifest")
    ecrire("50b_write_le_lot_du_projet_d_abord", projet=cible)
    shutil.copytree(jumeau / "scans" / "lot-etranger",
                    cible / "scans" / "lot-etranger")
    importe = (cible / "scans" / "lot-etranger" / "detections"
               / document_etranger.name)
    ecrire("50b_write_document_ETRANGER_au_manifest", projet=cible,
           document=importe, origines=(jumeau,))

    # `ExtractionPersistenceError` -- le lot est passe a `pdf` : ses frames sont
    # referencees par une planche imprimee, et la garde d'etat refuse **avant**
    # toute ecriture, `--overwrite` compris.
    cible = depuis_le_socle("51_lot_deja_PDF")
    ecrire("51a_write_avant_le_passage_a_pdf", projet=cible)
    manifeste = cible / "project.json"
    document = json.loads(manifeste.read_text(encoding="utf-8"))
    for lot in document["lots"]:
        lot["state"] = "pdf"
    manifeste.write_text(json.dumps(document), encoding="utf-8")
    ecrire("51b_write_lot_deja_PDF", "--overwrite", projet=cible)

    # `ScanIngestError` -- la copie ingeree n'est plus une image lisible, et le
    # condensat du document a ete **refait dessus** : la garde du bloc 3 est
    # donc franchie, et c'est la lecture du pixel qui tombe.
    cible = depuis_le_socle("52_source_ILLISIBLE")
    document = _detection_unique(cible)
    source = _source_ingeree(cible, document)
    source.write_bytes(b"ceci n'est pas une image")
    brut = json.loads(document.read_text(encoding="utf-8"))
    condensat = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    for page in brut["pages"]:
        if page["source"]["path_relative"].endswith(source.name):
            page["source_digest"] = condensat
    document.write_text(json.dumps(brut), encoding="utf-8")
    ecrire("52_source_ILLISIBLE", projet=cible, document=document)

    # **Le seul changement de comportement de la vague**, et il est mesure ici
    # plutot que declare (story 11.4b, lot S3, ligne L18 du document de
    # liaison) : une couche `manual-corrections-v1` -- le levier des rectangles
    # retire par `EPIC7-ARB-102` -- etait **ignoree en silence** avant le lot
    # S3, `scan_corrections` n'ayant aucun consommateur ; elle est desormais un
    # refus nomme. Aucune commande de la CLI ne sait POSER cette couche : seul
    # un document edite a la main ou produit par une interface en porte une.
    cible = depuis_le_socle("53_couche_manual_corrections_v1")
    document = _detection_unique(cible)
    brut = json.loads(document.read_text(encoding="utf-8"))
    brut["manual_corrections"] = {"schema": "manual-corrections-v1"}
    document.write_text(json.dumps(brut), encoding="utf-8")
    ecrire("53_couche_manual_corrections_v1", projet=cible, document=document)

    # -- bloc 6 : `makepdf`, l'artefact PHYSIQUE dont le scan depend ensuite ---
    #
    # `pdf_composition.py` est le seul fichier de coeur touche par la vague
    # (lot S4 : `nombre_de_planches` et `page_count_du_lot` extraites de
    # `compose_lot_plan`) qu'aucune invocation de scan ne traverse -- le scan
    # **relit** des planches, il n'en imprime aucune. Les 678 tests de
    # `test_pdf_composition.py` mesurent le module ; ce bloc mesure **ce qui
    # sort de la commande**, c'est-a-dire le PDF lui-meme, compare octet a
    # octet dans `arbre` comme n'importe quel autre artefact.
    #
    # Le lot est imprime en **v2 portrait**, la famille ou `EPIC11-ARB-84` a
    # mesure que les colonnes techniques sont les plus contraintes (55,188 mm
    # bornants, une seule part de marge avant debordement) : c'est la que la
    # moindre regression de mise en page se verrait en premier. La **v1
    # portrait** suit, seconde configuration serree de la meme mesure
    # (45,6 mm exiges pour 45,0 disponibles avec dix parts).
    pdf_projet = travail / "projets" / "projet_demo"
    rush = entrees / "rush_ident.mp4"
    for cadence, nom in ((5, "60_extract_cadence_5"),
                         (12, "61_extract_cadence_12")):
        releve.jouer(nom, ["extract", "--project", str(pdf_projet),
                           "--video", str(rush), "--fps", str(cadence),
                           "--yes", "--accept-unknown-color"],
                     projet=pdf_projet)
    lots = [lot["lot_id"] for lot in json.loads(
        (pdf_projet / "project.json").read_text(encoding="utf-8"))["lots"]]

    def imprimer(nom: str, lot: str, *options: str):
        return releve.jouer(
            nom, ["makepdf", "--project", str(pdf_projet), "--lot", lot,
                  "--orientation", "portrait", "--frames-par-page", "4",
                  *options],
            projet=pdf_projet, horloge_figee=True)

    # Le **second** lot d'abord (regle des fabriques : la cible ailleurs qu'en
    # premiere position), puis le premier. Les deux cadences ne portent pas le
    # meme compte de frames -- 5 et 12 --, donc pas le meme nombre de planches :
    # une pagination qui rendrait toujours celle du premier lot se demasque ici
    # et nulle part ailleurs, et c'est exactement ce que le lot S4 a touche.
    imprimer("62_makepdf_SECOND_lot_v2_portrait", lots[1], "--geometrie", "v2")
    imprimer("63_makepdf_premier_lot_v2_portrait", lots[0], "--geometrie", "v2")
    # Le meme, rejoue a l'identique : c'est le **temoin de reproductibilite**
    # du PDF, en bande. Sans lui, une comparaison octet a octet qui cesserait
    # d'etre possible passerait pour une divergence de code.
    imprimer("64_makepdf_SECOND_lot_REJOUE_a_l_identique", lots[1],
             "--geometrie", "v2", "--overwrite")
    imprimer("65_makepdf_v1_portrait", lots[1], "--geometrie", "v1",
             "--overwrite")
    # Deux refus nommes de la commande : le PDF deja present sans `--overwrite`,
    # et un dpi de rasterisation qui mettrait le QR sous son seuil de lecture --
    # refus **chiffre**, et c'est la moitie du sujet : une planche dont le QR ne
    # se relit pas n'est pas une planche.
    imprimer("66_makepdf_deja_present_REFUS", lots[1], "--geometrie", "v2")
    imprimer("67_makepdf_dpi_INSUFFISANT_REFUS", lots[0], "--geometrie", "v2",
             "--dpi", "150", "--overwrite")

    return {"provenance": provenance(rendu_pdf_gele),
            "scenarios": releve.scenarios}


def provenance(rendu_pdf_gele: bool = False) -> dict:
    """De quel arbre ce releve sort, **mesure dans l'arbre lui-meme**.

    Ce bloc ne participe **pas** a la comparaison -- il en est la garde. Une
    reference regeneree par megarde depuis le depot d'aujourd'hui serait
    identique a la passe d'aujourd'hui pour la plus mauvaise des raisons, et
    aucune comparaison de scenarios ne pourrait le voir. Deux faits suffisent a
    le trahir, et ils sont exactement ce que le lot S1 a change : le module de
    coeur `scan_write` **n'existe pas** avant lui, et `cli.py` y est **plus
    long** de la sequence entiere.
    """
    import importlib.util
    import inspect

    from mixed_media_utility import cli

    return {
        "scan_write_present":
            importlib.util.find_spec("mixed_media_utility.scan_write")
            is not None,
        "lignes_de_cli": len(inspect.getsource(cli).splitlines()),
        "rendu_pdf_gele": bool(rendu_pdf_gele),
    }


def main(argv=None) -> int:                              # pragma: no cover
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--entrees", required=True, type=Path)
    analyseur.add_argument("--travail", required=True, type=Path)
    analyseur.add_argument("--sortie", required=True, type=Path)
    options = analyseur.parse_args(argv)
    dossier = collecter(options.entrees.resolve(), options.travail.resolve())
    options.sortie.write_text(
        json.dumps(dossier, indent=1, sort_keys=True, ensure_ascii=False),
        encoding="utf-8")
    print(f"{len(dossier['scenarios'])} scenario(s) releve(s) -> "
          f"{options.sortie}", file=sys.stderr)
    return 0


if __name__ == "__main__":                               # pragma: no cover
    raise SystemExit(main())
