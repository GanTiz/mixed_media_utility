# -*- coding: utf-8 -*-
"""Story 11.8, **lot B1** -- le releve des observables de `mmu encode`.

**Ce module n'est pas un banc.** C'est l'instrument que le banc et la
**reference** emploient tous les deux : le meme code de releve, joue une fois
sur le depot d'AVANT le deplacement du corps d'`encode_command` et une fois sur
celui d'apres, sur des **entrees octet pour octet identiques** (ecrites par
:func:`fabriquer`).

AC 2.2 de la fiche, verbatim : « **L'artefact produit, les metadonnees
reinjectees et le code retour sont identiques** a ceux d'`mmu encode` avant
deplacement -- mesure par comparaison octet a octet du master et champ a champ
du rapport `ffprobe`. »

**C'est la premiere tache du lot, et elle est jouee AVANT le deplacement.**
Sans elle, « l'identite est preservee » serait une affirmation ; avec elle,
c'est une mesure a ensemble exact, sur vingt-quatre invocations reelles de
`cli.main` qui **encodent pour de vrai**.

Ce que chaque scenario releve, et les deux moities de l'AC 2.2 y sont :

* le socle (:class:`outils_identite_scan.Releve`) donne le code de sortie,
  `stdout` et `stderr` au caractere pres, le **condensat SHA-256 de chaque
  fichier** laisse dans le projet -- c'est la comparaison **octet a octet** du
  master --, chaque document JSON **aplati** -- c'est la comparaison champ a
  champ des metadonnees reinjectees au manifest -- et les lignes de
  `logs/encode.log`, horodate retiree ;
* ce module y ajoute le **rapport `ffprobe` entier** de chaque master produit,
  champ a champ. Un condensat dit seulement que deux fichiers different ; le
  rapport dit **quoi**, et c'est ce que l'AC nomme.

Trois proprietes de conception, chacune payee par un piege connu du depot :

1. **les commandes tournent pour de vrai, ffmpeg compris.** Un releve qui
   verifierait que l'enveloppe appelle le coeur ne mesurerait qu'un cablage, et
   un cablage identique peut produire des artefacts differents -- cadence,
   geometrie, timecode reinjecte, tags de conteneur. Ici c'est `cli.main([...])`
   qui est appele, et les masters sont de vrais fichiers ;
2. **ce module n'importe du `src/` a mesurer que `cli`**, par le socle. Il doit
   tourner sous le `src/` d'un commit ou le point d'entree de coeur de cette
   story n'existe pas encore ;
3. **rien n'est neutralise sans motif ecrit.** La neutralisation est celle,
   deja mesuree, d'`outils_identite_scan` : cles volatiles nommees une a une,
   horodate de journal retiree, chemins absolus masques. Elle est **reprise et
   non recopiee**. Le seul ajout est `format.filename` du rapport `ffprobe`,
   qui porte le dossier temporaire de la course -- et c'est une **mesure** et
   non une precaution : deux releves joues sur l'arbre `bad2f294` intact ont
   diverge sur ce champ **et sur lui seul**, les neuf masters etant identiques
   octet pour octet.

**Aucune horloge n'est figee, et c'est mesure plutot que suppose.** Le master
ne porte aucune date : deux courses completes sur le meme arbre ont rendu neuf
masters au condensat identique. Les seules dates du releve vivent dans les cles
volatiles que le socle neutralise deja (`created`, `updated`).

**Ce que ce dossier NE joue PAS, dit plutot que tu** -- deux familles, et la
seconde est un defaut trouve en ecrivant ce module :

* les codes `130` (interruption clavier) et `143` (`SIGTERM`). Les atteindre
  demanderait de tuer un processus pendant l'encodage, ce qui n'est ni
  deterministe ni rejouable dans une suite ; ils restent mesures par les bancs
  dedies de `tests/unit/test_encode_command.py`, qui les atteignent par un
  signal reel ;
* un `project.json` **syntaxiquement illisible**. `mmu encode` ne le rattrape
  pas : `validate_manifest` leve une `json.JSONDecodeError` nue qui traverse la
  commande et sort en **trace Python**, la ou `mmu makepdf` la rend en `1` avec
  son message (son dossier d'identite joue le scenario `44-manifest-illisible`).
  Le defaut est **anterieur** a cette story et il n'est pas corrige ici : le
  corriger changerait un observable, ce que l'AC 2.2 interdit precisement a ce
  lot. Il est porte en dette dans `deferred-work.md` avec cette origine. Le
  manifest **hors schema**, lui, est joue : c'est l'autre famille du meme refus,
  et elle emprunte un `except` qui existe.

Emploi, et c'est ainsi qu'une reference se regenere (le geste est ecrit ici
parce qu'il devra etre rejoue) :

```
# 1. fabriquer les entrees avec les fabriques D'AUJOURD'HUI, une seule fois
python3 tests/unit/outils_identite_encode.py --fabriquer <entrees>

# 2. les rejouer sous le src d'un commit, dans un worktree detache
GIT_LFS_SKIP_SMUDGE=1 git worktree add --detach <base> <commit>
PYTHONPATH=<base>/src python3 tests/unit/outils_identite_encode.py \\
    --entrees <entrees> --travail <tmp> --sortie <reference.json>
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

_ICI = Path(__file__).resolve().parent
if str(_ICI) not in sys.path:
    sys.path.insert(0, str(_ICI))

import outils_identite_scan as socle   # noqa: E402

#: Le lot du socle, ecrit **en clair** et non lu de `io.naming` : un identifiant
#: de lot qui changerait serait precisement un changement observable, et le
#: deriver du module mesure le rendrait invisible.
LOT = "rush-encode_5"

#: Le registre des passes de scan, au manifest. Nomme ici plutot que recopie,
#: et **jamais renomme** : `EPIC11-ARB-221` gele les cles du document.
RECONSTRUCTIONS = "reconstructions"

#: Les trois projets d'entree, et ce que chacun sert a mesurer. Trois et non un :
#: la regle des fabriques du `CLAUDE.md` veut une collection distinguable, et
#: surtout chacun ouvre une famille de refus que les deux autres ne peuvent pas
#: atteindre.
PROJET_COMPLET = "projet-complet"
PROJET_INCOMPLET = "projet-incomplet"
PROJET_SANS_CADENCE_SOURCE = "projet-sans-cadence-source"

#: Les conteneurs qu'un master peut porter. Nommes plutot que devines par
#: `is_file()` : le dossier `outputs/` porte aussi les fichiers d'attente que la
#: story 6.1 laisse pour diagnostic, et les sonder avec `ffprobe` melangerait
#: deux observables de nature differente.
SUFFIXES_DE_MASTER = (".mov", ".mp4")


# ---------------------------------------------------------------------------
# Les entrees -- produites par les VRAIES chaines, une seule fois
# ---------------------------------------------------------------------------

def fabriquer(destination: Path) -> Path:
    """Ecrire les trois projets d'entree sous `destination`.

    Ils sortent des fabriques de `tests/unit/test_encode_command.py`, donc de
    la chaine de scan **reelle** : payloads de `io.payload`, plans de decoupe de
    `scan_crop`, vrais TIFF ecrits par `scan_output_frames`, manifest fusionne
    par `io.scan_manifest.persist_scan`. Aucun manifest ecrit a la main.

    La fabrique est **deterministe**, et ce n'est pas une hypothese : deux
    courses completes sur le meme arbre ont rendu des masters identiques octet
    pour octet, ce qui n'est possible que si les frames le sont.
    """
    import importlib.util

    chemin = _ICI / "test_encode_command.py"
    specification = importlib.util.spec_from_file_location(
        "_fabriques_d_identite_encode", chemin)
    fabriques = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(fabriques)

    destination.mkdir(parents=True, exist_ok=True)
    fabriques.scanned_project(destination, name=PROJET_COMPLET)
    # Une page **absente**, et c'est la page du MILIEU : un verdict de
    # completude qui ne regarderait qu'un bout de la sequence ne se demasque pas
    # autrement (regle des fabriques, point 2 bis).
    fabriques.scanned_project(destination, name=PROJET_INCOMPLET,
                              absent_pages=(2,))
    projet, manifeste = fabriques.scanned_project(
        destination, name=PROJET_SANS_CADENCE_SOURCE)
    # Le regime d'un lot ne d'un scan de planches **2.0** : le lot ne porte pas
    # `timecode_base_fps`, donc la cadence source du master n'a aucune valeur
    # tant que `--cadence-source` n'est pas passe.
    fabriques.strip_timecode_base_fps(projet, manifeste)
    return destination


def empreinte_des_entrees(entrees: Path) -> dict:
    """Chemin relatif -> condensat, pour **chaque** fichier d'entree.

    Sans elle, la comparaison n'aurait aucun moyen de savoir que les deux cotes
    n'ont pas ete joues sur les memes octets : la fabrique vit dans `tests/`,
    elle peut donc changer entre l'ecriture d'une reference et sa relecture, et
    un ecart de fabrique se lirait alors comme un ecart de produit.

    Un document JSON y entre **aplati**, jamais condense : le `project.json`
    porte `created` et `updated`, poses a l'instant de la fabrique, et deux
    fabriques separees d'une seconde rendraient deux condensats differents pour
    des entrees rigoureusement equivalentes.
    """
    empreinte: dict = {}
    for chemin in sorted(entrees.rglob("*")):
        if not chemin.is_file():
            continue
        relatif = str(chemin.relative_to(entrees))
        if chemin.suffix == ".json":
            empreinte[relatif] = socle._document(chemin, [])
        else:
            empreinte[relatif] = hashlib.sha256(chemin.read_bytes()).hexdigest()
    return empreinte


# ---------------------------------------------------------------------------
# Le releveur -- le socle, plus le rapport `ffprobe` de chaque master
# ---------------------------------------------------------------------------

class ReleveEncode(socle.Releve):
    """Le releveur du scan, augmente du rapport technique de chaque master.

    Le socle condense les octets ; `ffprobe` dit ce qu'ils portent. Les deux
    sont exiges par l'AC 2.2, et ils ne mesurent pas la meme chose : un master
    qui changerait de cadence ou perdrait son timecode se verrait au condensat
    comme « different », sans qu'aucun message ne dise en quoi.
    """

    def jouer(self, nom: str, argv: list[str], *, projet: Path, **reste) -> int:
        code = super().jouer(nom, argv, projet=projet, **reste)
        self.scenarios[nom]["ffprobe"] = self._rapports(projet)
        return code

    def _rapports(self, projet: Path) -> dict:
        """Le rapport `ffprobe` de chaque master, indexe par chemin relatif.

        Le dictionnaire est **vide** quand rien n'a ete ecrit, et c'est un
        observable a part entiere : un refus qui se mettrait a produire un
        fichier se verrait ici avant meme qu'on regarde son contenu.
        """
        from mixed_media_utility import video_metadata

        sorties = projet / "outputs"
        if not sorties.is_dir():
            return {}
        rapports: dict = {}
        for chemin in sorted(sorties.rglob("*")):
            if not chemin.is_file() or chemin.suffix.lower() not in SUFFIXES_DE_MASTER:
                continue
            relatif = str(chemin.relative_to(projet))
            # Le rapport est **aplati** avant d'etre normalise, exactement
            # comme les documents JSON du socle : l'egalite de deux rapports
            # dirait seulement qu'ils different, jamais **quel champ**. Et
            # `_normaliser` ne sait masquer un chemin que dans une chaine :
            # l'appeler sur le dictionnaire entier ne ferait rien du tout --
            # mesure du 2026-09-03, ou `format.filename` a survecu a la
            # normalisation et fait diverger neuf scenarios sur deux courses
            # d'un arbre pourtant intact.
            remplacements = self.remplacements + [
                (variante, "<PROJET>")
                for variante in {str(projet), str(Path(projet).resolve())}]
            rapports[relatif] = {
                cle: socle._normaliser(feuille, remplacements)
                for cle, feuille in socle._aplatir(
                    video_metadata.probe_media(str(chemin))).items()}
        return rapports


def _reecrire_l_etat_du_lot(projet: Path, etat: str) -> None:
    """Poser `lots[].state` sur le lot du socle, dans le manifest sur disque.

    Le seul geste du dossier qui touche un manifest deja ecrit, et il est
    motive : aucune chaine du depot ne sait produire un lot dont le dossier de
    frames est plein et l'etat en deca de `scan`. Le refus d'etat serait sans
    cela **non falsifiable**, ce qui est precisement le defaut qu'il existe
    pour fermer.
    """
    chemin = projet / "project.json"
    document = json.loads(chemin.read_text(encoding="utf-8"))
    for lot in document.get("lots") or []:
        if lot.get("lot_id") == LOT:
            lot["state"] = etat
    chemin.write_text(json.dumps(document, indent=2, sort_keys=True),
                      encoding="utf-8")


def dossiers_de_lots_scannes(projet: Path) -> list[Path]:
    """Les lots scannes qu'un projet DECLARE, lus au manifest (story 11.14).

    **Ce module ne compose aucun nom de dossier, et c'est le defaut que cette
    fonction ferme.** Il ecrivait `projet / "output-frames"` en clair ; le nom
    d'avant est devenu `frames-scannees/` (`EPIC11-ARB-214`, `220`), le glob a
    cesse de mordre, et les scenarios `27-dossier-de-lot-absent` et
    `32-dossier-de-lot-vide` ont continue de passer au VERT tout en vidant un
    dossier qui n'existait plus -- c'est-a-dire en cessant de mesurer ce qu'ils
    annoncent. Un chemin fige est pire qu'un rouge : il rend un banc muet.

    La sortie est lue de `lots[].output_frames_dir` et de
    `lots[].reconstructions[].output_frames_dir`, **les cles de manifeste**, qui
    ne bougent pas (`EPIC11-ARB-221`, regime « surfaces seules »). C'est le seul
    chemin qui marche des deux cotes : un projet d'avant declare
    `output-frames/<slug>`, un projet neuf `frames-scannees/<slug>`, aucun des
    deux n'est converti (`EPIC11-ARB-222`), et le manifest dit lequel.

    Importer `io.project_layout` pour ses constantes serait l'autre issue, et
    elle est ecartee : ce module doit tourner sous le `src/` d'un commit
    ancien, ou ces constantes n'existent pas (propriete 2 en tete de fichier).
    """
    document = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    declares: list[Path] = []
    for lot in document.get("lots") or []:
        if not isinstance(lot, dict):
            continue
        candidats = [lot.get("output_frames_dir")]
        candidats += [
            passe.get("output_frames_dir")
            for passe in (lot.get(RECONSTRUCTIONS) or [])
            if isinstance(passe, dict)
        ]
        for relatif in candidats:
            if isinstance(relatif, str) and relatif:
                chemin = projet / relatif
                if chemin not in declares:
                    declares.append(chemin)
    if not declares:
        raise AssertionError(
            f"aucun lot scanne declare par {projet / 'project.json'} : les "
            "scenarios du dossier de lot ne mesureraient plus rien")
    return declares


def _socle_frais(releve: ReleveEncode, nom: str, source: str = PROJET_COMPLET) -> Path:
    """Une copie fraiche d'un projet d'entree, sous `<travail>/projets/<nom>`."""
    cible = releve.projet(nom)
    cible.parent.mkdir(parents=True, exist_ok=True)
    if cible.exists():
        shutil.rmtree(cible)
    shutil.copytree(releve.entrees / source, cible)
    return cible


# ---------------------------------------------------------------------------
# Le dossier d'identite
# ---------------------------------------------------------------------------

def collecter(entrees: Path, travail: Path) -> dict:
    """Jouer toutes les invocations et rendre le dossier d'observables.

    Cinq blocs, et l'ordre suit ce qu'ils mesurent :

    * **bloc 1** -- la sequence d'ecriture d'un meme lot : nominal, relance qui
      bute sur le master deja la, relance ecrasante. C'est le seul bloc ou deux
      invocations se voient l'une l'autre ;
    * **bloc 2** -- les quatre autres profils et les trois autres resolutions,
      chacun sur son propre exemplaire du socle. Deux conteneurs (`mov`, `mp4`)
      et quatre codecs : une identite qui ne vaudrait que pour ProRes ne vaudrait
      rien ;
    * **bloc 3** -- les refus **anterieurs** a toute ecriture, y compris les
      deux gardes qui precedent l'ouverture du journal ;
    * **bloc 4** -- le consentement, dans ses **trois** regimes (hors terminal,
      refuse en terminal, accorde en terminal). C'est le seul chemin qui rend
      `3`, et le seul ou `stdin` est lu ;
    * **bloc 5** -- la cadence source : l'option qui prime la valeur du lot, le
      lot qui n'en porte aucune, et l'option syntaxiquement fautive (refusee par
      le parseur, code `2`).
    """
    releve = ReleveEncode(entrees, travail)

    def encoder(nom: str, projet: Path, *options: str, reponses=None) -> int:
        return releve.jouer(
            nom, ["encode", "--project", str(projet), *options],
            projet=projet, reponses=reponses)

    # -- bloc 1 : la sequence d'ecriture d'un meme lot ------------------------
    p1 = _socle_frais(releve, "p1-sequence")
    encoder("01-nominal", p1, "--lot", LOT, "--yes")
    encoder("02-relance-master-deja-la", p1, "--lot", LOT, "--yes")
    encoder("03-relance-overwrite", p1, "--lot", LOT, "--yes", "--overwrite")

    # -- bloc 2 : profils et resolutions --------------------------------------
    encoder("10-profil-prores-422", _socle_frais(releve, "p10"),
            "--lot", LOT, "--yes", "--profile", "prores_422")
    encoder("11-profil-prores-lt-en-uhd", _socle_frais(releve, "p11"),
            "--lot", LOT, "--yes", "--profile", "prores_lt",
            "--resolution", "uhd2160")
    encoder("12-profil-dnxhr-hq", _socle_frais(releve, "p12"),
            "--lot", LOT, "--yes", "--profile", "dnxhr_hq")
    encoder("13-profil-h264-en-mp4", _socle_frais(releve, "p13"),
            "--lot", LOT, "--yes", "--profile", "h264_delivery")
    encoder("14-resolution-native", _socle_frais(releve, "p14"),
            "--lot", LOT, "--yes", "--resolution", "native")
    encoder("15-resolution-personnalisee", _socle_frais(releve, "p15"),
            "--lot", LOT, "--yes", "--resolution", "640x360")

    # -- bloc 3 : les refus, un exemplaire du socle chacun --------------------
    p2 = _socle_frais(releve, "p2-refus")
    encoder("20-lot-absent-du-manifest", p2, "--lot", "rush-999_5", "--yes")
    encoder("21-resolution-inconnue", p2, "--lot", LOT, "--yes",
            "--resolution", "1080p")
    encoder("22-profil-inconnu", p2, "--lot", LOT, "--yes",
            "--profile", "profil-qui-n-existe-pas")

    # Les deux gardes qui precedent l'ouverture du journal : ni l'une ni l'autre
    # ne doit creer la moindre arborescence, et c'est l'`arbre` du releve qui le
    # dit -- pas une relecture du code.
    encoder("23-projet-inexistant", travail / "projets" / "p3-inexistant",
            "--lot", LOT, "--yes")
    p4 = travail / "projets" / "p4-sans-manifest"
    p4.mkdir(parents=True, exist_ok=True)
    encoder("24-manifest-absent", p4, "--lot", LOT, "--yes")

    p6 = _socle_frais(releve, "p6-manifest-hors-schema")
    (p6 / "project.json").write_text(
        json.dumps({"schema_version": "2.0", "lots": "pas une liste"}, indent=2),
        encoding="utf-8")
    encoder("26-manifest-hors-schema", p6, "--lot", LOT, "--yes")

    # Le dossier de lot declare mais **absent du disque** : c'est la garde
    # d'admission du lot, distincte des deux precedentes.
    p7 = _socle_frais(releve, "p7-dossier-de-lot-absent")
    for dossier in dossiers_de_lots_scannes(p7):
        if dossier.is_dir():
            shutil.rmtree(dossier)
    encoder("27-dossier-de-lot-absent", p7, "--lot", LOT, "--yes")

    p8 = _socle_frais(releve, "p8-lot-incomplet", PROJET_INCOMPLET)
    encoder("28-lot-incomplet-refuse", p8, "--lot", LOT, "--yes")
    encoder("29-lot-incomplet-consenti", p8, "--lot", LOT, "--yes",
            "--accept-incomplete-lot")

    # L'etat du lot, ramene en deca de `scan` : c'est la garde d'admission qui
    # parle de l'ETAT, distincte de celle qui parle du dossier -- deux codes
    # distincts, et les confondre ferait lire « etat insuffisant » a un
    # operateur dont le lot est au bon etat.
    p31 = _socle_frais(releve, "p31-etat-insuffisant")
    _reecrire_l_etat_du_lot(p31, "extract")
    encoder("31-etat-de-lot-insuffisant", p31, "--lot", LOT, "--yes")

    # Le dossier declare **existe** mais ne porte aucune frame : troisieme code
    # de la meme famille, et le cas nominal d'un projet dont le scan n'a pas
    # encore eu lieu.
    p32 = _socle_frais(releve, "p32-dossier-de-lot-vide")
    for dossier in dossiers_de_lots_scannes(p32):
        for frame in sorted(dossier.rglob("*")):
            if frame.is_file():
                frame.unlink()
    encoder("32-dossier-de-lot-vide", p32, "--lot", LOT, "--yes")

    # -- bloc 4 : le consentement ---------------------------------------------
    #
    # **Un seul regime est atteignable par cet instrument, et le dire vaut
    # mieux que le taire.** `_encode_confirmation` exige un TTY sur `stdin`
    # **et** sur `stdout` (`source_confirmation.detect_interactive`), or le
    # socle capture `stdout` dans un `io.StringIO`, dont `isatty()` est faux.
    # Monter un `stdin` de terminal ne suffit donc pas : la commande retombe
    # dans le regime non interactif, et deux scenarios qui ne differeraient que
    # par leur `stdin` mesureraient la meme chose en laissant croire le
    # contraire. Le regime interactif est mesure a part, par un banc qui appelle
    # le point d'entree avec ses deux flux -- pas par ce dossier.
    encoder("30-consentement-hors-terminal", _socle_frais(releve, "p30"),
            "--lot", LOT)

    # -- bloc 5 : la cadence source -------------------------------------------
    encoder("40-cadence-source-prime-le-lot", _socle_frais(releve, "p40"),
            "--lot", LOT, "--yes", "--cadence-source", "25")
    p41 = _socle_frais(releve, "p41", PROJET_SANS_CADENCE_SOURCE)
    encoder("41-cadence-source-manquante", p41, "--lot", LOT, "--yes")
    p42 = _socle_frais(releve, "p42", PROJET_SANS_CADENCE_SOURCE)
    # La forme `num/den`, transmise **telle quelle** jusqu'a `exact_frame_rate`
    # (story 3.8) : `30/1` est la vraie cadence source de ce lot, donc le
    # scenario ECRIT un master -- une syntaxe fractionnaire qui ne serait
    # mesuree que sur un refus ne dirait rien de ce qu'elle produit.
    encoder("42-cadence-source-fractionnaire", p42, "--lot", LOT, "--yes",
            "--cadence-source", "30/1")
    encoder("43-cadence-source-syntaxe-fautive", _socle_frais(releve, "p43"),
            "--lot", LOT, "--yes", "--cadence-source", "pas-un-nombre")

    return {
        "entrees": empreinte_des_entrees(entrees),
        "scenarios": releve.scenarios,
    }


def main(argv=None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--fabriquer", type=Path,
                         help="ecrire les entrees a ce chemin, puis sortir")
    parseur.add_argument("--entrees", type=Path)
    parseur.add_argument("--travail", type=Path)
    parseur.add_argument("--sortie", type=Path)
    arguments = parseur.parse_args(argv)

    if arguments.fabriquer is not None:
        fabriquer(arguments.fabriquer)
        print(f"entrees fabriquees -> {arguments.fabriquer}")
        return 0

    for nom in ("entrees", "travail", "sortie"):
        if getattr(arguments, nom) is None:
            parseur.error(f"--{nom} est requis hors du mode --fabriquer")

    arguments.travail.mkdir(parents=True, exist_ok=True)
    dossier = collecter(arguments.entrees, arguments.travail)
    arguments.sortie.parent.mkdir(parents=True, exist_ok=True)
    arguments.sortie.write_text(
        json.dumps(dossier, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    print(f"{len(dossier['scenarios'])} invocations relevees -> {arguments.sortie}")
    return 0


if __name__ == "__main__":                                 # pragma: no cover
    raise SystemExit(main())
