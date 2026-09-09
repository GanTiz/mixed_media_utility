# -*- coding: utf-8 -*-
"""Story 11.7, **lot B1** -- le releve des observables de `mmu makepdf`.

**Ce module n'est pas un banc.** C'est l'instrument que le banc et les
**references** emploient tous les deux : le meme code de releve, joue une fois
sur le depot d'aujourd'hui et une fois sur le depot d'un commit anterieur, sur
des **entrees octet pour octet identiques** (ecrites par
`fabriquer_les_entrees_makepdf.py`).

AC 2.5 de la fiche, verbatim : « **Aucun comportement observable de
`mmu makepdf` ne change, HORS les trois changements que les lots B0 / B0 bis /
B0 ter portent explicitement** -- memes messages sur `stderr`, memes codes
(`0`, `1`, `130`), meme `logs/makepdf.log`, meme manifest. »

**C'est la PREMIERE tache du lot et elle ne se saute pas.** Sans ce releve,
« l'identite est preservee » apres le deplacement du corps de `makepdf_command`
serait une affirmation ; avec lui, c'est une mesure a ensemble exact.

Trois proprietes de conception, chacune payee par un piege connu du depot :

1. **les commandes tournent pour de vrai.** Un releve qui verifierait que
   l'enveloppe appelle le coeur ne mesurerait qu'un cablage, et un cablage
   identique peut produire des artefacts differents -- nom, rang, octets du PDF,
   ordre des lignes de journal. Ici c'est `cli.main([...])` qui est appele ;
2. **ce module n'importe rien du `src/` a mesurer, hors `cli`.** Il doit tourner
   sous le `src/` d'un commit anterieur, ou le module de coeur de cette story
   n'existe pas encore. Il ne connait que `mixed_media_utility.cli` et les
   outils de releve du dossier d'identite du scan, qui vivent dans `tests/` et
   ne dependent d'aucune version du produit ;
3. **rien n'est neutralise sans motif ecrit.** La neutralisation est celle,
   deja mesuree, d'`outils_identite_scan` : cles volatiles nommees une a une,
   horodate de journal retiree, chemins absolus masques. Elle est **reprise et
   non recopiee** -- une seconde redaction divergerait au premier champ
   volatil ajoute.

**Le gel de l'horloge porte sur TOUS les modules qui la lisent, pas sur `cli`
seul.** C'est le seul endroit ou ce releve s'ecarte de celui du scan, et le
motif est structurel : la tache B5 deplace `datetime.now()` de `cli` vers le
module de coeur. Un gel pose sur `cli.datetime` uniquement cesserait
silencieusement d'agir apres le deplacement, et la comparaison rougirait sur la
date imprimee **de chaque planche** -- un faux ecart, qui masquerait les vrais.
Le gel est donc pose sur l'ensemble des modules de :data:`MODULES_A_HORLOGE`
qui existent sous le `src/` courant, et ce qui n'existe pas encore est saute.

Emploi, et c'est ainsi qu'une reference se regenere (le geste est ecrit ici
parce qu'il devra etre rejoue) :

```
# 1. fabriquer les entrees avec les fabriques D'AUJOURD'HUI, une seule fois
python3 tests/unit/fabriquer_les_entrees_makepdf.py <entrees>

# 2. les rejouer sous le src d'un commit, dans un worktree detache
GIT_LFS_SKIP_SMUDGE=1 git worktree add --detach <base> <commit>
PYTHONPATH=<base>/src python3 tests/unit/outils_identite_makepdf.py \\
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

#: Les modules dont l'attribut `datetime` doit voir l'horloge figee. `cli` le lit
#: aujourd'hui (`generated_at` d'une planche, `generated_on` d'une mire) ; le
#: module de coeur de la tache B2/B3 le lira demain. Les deux y figurent, et
#: celui qui n'existe pas encore est saute -- c'est ce qui rend le meme releve
#: jouable des deux cotes du deplacement.
MODULES_A_HORLOGE = (
    "mixed_media_utility.cli",
    "mixed_media_utility.makepdf",
)

#: Le lot du socle, ecrit en clair. Il n'est pas relu de `io.naming` : un
#: identifiant de lot qui changerait serait precisement un changement
#: observable, et le deriver du module mesure le rendrait invisible.
LOT = "rush-001_5"

#: Les deux noms du dossier de frames extraites (story 11.14) : le NEUF, que le
#: `src/` d'aujourd'hui ecrit, et l'ANCIEN, que celui du `baseline_commit`
#: ecrivait -- et qu'`EPIC11-ARB-222` fait RECONNAITRE indefiniment, puisqu'un
#: projet deja sur disque ne se convertit pas.
#:
#: **Ecrits ici plutot que lus de `io.project_layout`**, et ce n'est pas une
#: entorse a la regle du nom unique mais la propriete 2 du docstring de ce
#: module : il doit tourner sous le `src/` d'un commit anterieur, ou
#: `EXTRACT_FRAMES_DIRNAME` n'existe pas encore. Un import de ce module ferait
#: exploser la regeneration d'une reference a l'`ImportError`, c'est-a-dire au
#: moment ou l'instrument sert. Porter les deux noms rend au contraire le meme
#: releve jouable des DEUX cotes du renommage -- ce qu'une regeneration
#: demande, et ce que le releve d'aujourd'hui demande aussi.
DOSSIERS_DE_FRAMES_EXTRAITES = ("extract-frames", "frames")


def frames_extraites_du_projet(projet: Path) -> list[Path]:
    """Les frames extraites de `projet`, quel que soit le nom de leur dossier.

    **Elle leve plutot que de rendre une liste vide**, et c'est le seul point
    qui compte ici. Ce qu'elle remplace composait `projet / "frames"` en dur :
    apres le renommage, le `rglob` rendait `[]` et l'appelant levait un
    `IndexError` nu -- un accident, pas une mesure. Le lot D2 a trouve le cas
    symetrique et plus cher : deux scenarios d'`encode` qui vidaient un dossier
    absent **en restant verts**, c'est-a-dire un collecteur qui avait cesse de
    mesurer sans que rien ne rougisse.

    Un collecteur de banc qui ne trouve rien doit donc le DIRE. Le message
    nomme les deux dossiers cherches, sans quoi le lecteur du rouge chercherait
    la panne dans le produit plutot que dans le nom.
    """
    for nom in DOSSIERS_DE_FRAMES_EXTRAITES:
        trouvees = sorted((projet / nom).rglob("*.tiff"))
        if trouvees:
            return trouvees
    cherches = ", ".join(f"{nom}/" for nom in DOSSIERS_DE_FRAMES_EXTRAITES)
    raise AssertionError(
        f"aucune frame extraite sous {projet} : ni {cherches} ne porte de "
        "`.tiff`. Le socle n'a pas ecrit son lot, ou le dossier a ete renomme "
        "sans que ce releve le sache."
    )

#: Le libelle de chaine de la mire nominale, et son voisin. Deux libelles et non
#: un : le nom d'une page de calibration porte le libelle, donc c'est la seule
#: issue **non destructive** qu'`EPIC11-ARB-89` exige de la commande, et la
#: mesurer demande d'en jouer deux.
CHAINE = "banc identite 600 dpi"
CHAINE_VOISINE = "banc identite 1200 dpi"


def _modules_a_horloge():
    """Les modules de :data:`MODULES_A_HORLOGE` presents sous le `src/` courant."""
    import importlib

    presents = []
    for nom in MODULES_A_HORLOGE:
        try:
            module = importlib.import_module(nom)
        except ImportError:
            continue
        if hasattr(module, "datetime"):
            presents.append(module)
    return presents


class ReleveMakepdf(socle.Releve):
    """Le releveur du scan, dont le gel d'horloge porte sur plusieurs modules.

    Toutes les invocations de ce dossier ecrivent -- ou refusent d'ecrire -- un
    document date : la planche porte « genere le ... » et la mire porte la date
    du geste. L'horloge est donc figee sur **chaque** scenario, et non sur un
    bloc comme dans le dossier du scan.
    """

    def jouer(self, nom: str, argv: list[str], *, projet: Path, **reste) -> int:
        modules = _modules_a_horloge()
        anciennes = [(module, module.datetime) for module in modules]
        for module in modules:
            module.datetime = socle.HorlogeFigee
        try:
            return super().jouer(nom, argv, projet=projet, **reste)
        finally:
            for module, horloge in anciennes:
                module.datetime = horloge


def empreinte_des_entrees(entrees: Path) -> dict:
    """Chemin relatif -> condensat, pour **chaque** fichier d'entree.

    Sans elle, la comparaison n'aurait aucun moyen de savoir que les deux cotes
    n'ont pas ete joues sur les memes octets : la fabrique des entrees vit dans
    `tests/`, elle peut donc changer entre l'ecriture d'une reference et sa
    relecture, et un ecart de fabrique se lirait alors comme un ecart de
    produit. C'est le pendant de l'exigence « des entrees octet pour octet
    identiques » du docstring de tete -- exigee, et desormais **mesuree**.

    **Un document JSON y entre aplati, jamais condense**, et c'est une mesure et
    non un choix de forme : le `project.json` du socle porte `created` et
    `updated`, poses par `project_layout` a l'instant de la fabrique. Deux
    fabriques separees d'une seconde rendent donc deux condensats differents
    pour des entrees rigoureusement equivalentes -- l'empreinte aurait rougi a
    chaque relecture, en nommant un ecart qui n'existe pas. Les memes cles
    volatiles que le releve sont donc retirees ici, et par le meme code.
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


def _socle(releve: ReleveMakepdf, nom: str) -> Path:
    """Une copie fraiche du projet d'entree, sous `<travail>/projets/<nom>`."""
    cible = releve.projet(nom)
    cible.parent.mkdir(parents=True, exist_ok=True)
    if cible.exists():
        shutil.rmtree(cible)
    shutil.copytree(releve.entrees / "projet-avec-lot", cible)
    return cible


def collecter(entrees: Path, travail: Path) -> dict:
    """Jouer toutes les invocations et rendre le dossier d'observables.

    Quatre blocs, et l'ordre suit ce qu'ils mesurent :

    * **bloc 1** -- la sequence d'ecriture d'un meme lot : nominal, relance,
      relance ecrasante, deux autres mises en page. C'est le seul bloc que les
      trois ecarts nommes (AC 2.9 / 2.10 / 2.11) traversent ;
    * **bloc 2** -- les refus de `makepdf` **anterieurs** a toute ecriture,
      chacun sur son propre exemplaire du socle ;
    * **bloc 3** -- la mire de calibration : nominal, ses trois issues de
      conflit, et ses refus ;
    * **bloc 4** -- les refus **communs** aux deux commandes, joues sur les
      deux, pour que la comparaison voie une divergence de l'une sans l'autre.

    Deux refus de l'AC 2.3 ne sont **pas** joues, et le dire vaut mieux que le
    taire (aucune troncature silencieuse) : les **rangs epuises**
    (`VERSION_RANK_MAX`) demanderaient une centaine de tirages reels, et
    l'**echec de declaration au manifest** (`PdfPersistenceError`) n'a aucun
    chemin d'operateur -- `verify_extracted_lot` refuse plus haut tout lot que
    la persistance retrouverait absent. Le **conflit de sortie** de `makepdf`
    n'en a plus non plus depuis le lot B0 bis (le rang avance a chaque passe,
    donc le nom est toujours neuf) : il reste joue ici parce qu'il **en avait
    un** au commit de reference, et c'est precisement l'ecart que le dossier
    doit montrer.
    """
    rendu_pdf_gele = socle.geler_le_rendu_pdf()
    releve = ReleveMakepdf(entrees, travail)

    def makepdf(nom: str, projet: Path, *options: str) -> int:
        return releve.jouer(nom, ["makepdf", "--project", str(projet),
                                  *options], projet=projet)

    def mire(nom: str, projet: Path, *options: str, amont: tuple = ()) -> int:
        """Jouer `makepdf calibration-page`.

        `amont` porte les options declarees sur le parseur **parent** --
        geometrie, marge, patchs, `--overwrite`. Elles ne sont pas une commodite
        de redaction : argparse les refuse apres le nom de la sous-commande
        (code `2`, `usage:`), et les y placer mesurerait le parseur au lieu de
        la commande. La sous-commande ne declare que `--chaine` et
        `--commentaire` (voir `cli._build_parser`).
        """
        return releve.jouer(nom, ["makepdf", "--project", str(projet), *amont,
                                  "calibration-page", *options], projet=projet)

    # -- bloc 1 : la sequence d'ecriture d'un meme lot ------------------------
    p1 = _socle(releve, "p1-sequence")
    makepdf("01-nominal", p1, "--lot", LOT)
    makepdf("02-relance-identique", p1, "--lot", LOT)
    makepdf("03-relance-nouvelle-version", p1, "--lot", LOT, "--nouvelle-version")
    makepdf("04-relance-overwrite", p1, "--lot", LOT, "--overwrite")
    # Une autre mise en page du **meme** lot : `EPIC11-ARB-175` veut qu'elle
    # n'entre plus en conflit, et que son rang continue la serie du lot.
    makepdf("05-autre-mise-en-page-4f", p1, "--lot", LOT, "--frames-par-page", "4")
    makepdf("06-autre-mise-en-page-1f", p1, "--lot", LOT, "--frames-par-page", "1")
    # Le couple `--rush/--fps`, qui resout le meme lot par l'autre porte.
    makepdf("07-par-rush-et-fps", p1, "--rush", "rush-001", "--fps", "5")

    # -- bloc 2 : les refus de `makepdf`, un exemplaire du socle chacun -------
    p2 = _socle(releve, "p2-refus")
    makepdf("10-designation-ambigue", p2, "--lot", LOT, "--rush", "rush-001")
    makepdf("11-designation-absente", p2)
    makepdf("12-lot-absent-du-manifest", p2, "--lot", "rush-999_5")
    makepdf("13-vocabulaire-refuse", p2, "--lot", LOT, "--frames-par-page", "7")
    makepdf("14-preset-de-patchs-inconnu", p2, "--lot", LOT,
            "--nombre-patchs", "patches-000-v0")
    makepdf("15-gamut-map-inconnu", p2, "--lot", LOT, "--gamut-map", "compression-000")
    makepdf("16-format-inconnu", p2, "--lot", LOT, "--format", "A9")
    makepdf("17-marge-inconnue", p2, "--lot", LOT, "--marge", "7")
    makepdf("18-geometrie-inconnue", p2, "--lot", LOT, "--geometrie", "v0")
    # `paysage x patches-18-v2` n'a aucun placement sous la v2 : c'est le refus
    # geometrique nomme de l'AC 2.3, et il est atteint par le vocabulaire du
    # coeur plutot que par un chiffre invente.
    makepdf("19-geometrie-impossible", p2, "--lot", LOT,
            "--orientation", "paysage", "--nombre-patchs", "patches-18-v2")
    # Une compression non triviale : elle passe, et elle porte son
    # avertissement `COMPRESSION_SANS_EXPANSION` au journal.
    makepdf("20-compression-non-triviale", p2, "--lot", LOT,
            "--gamut-map", "gamut-map-lin-1")

    # Un lot que le disque contredit : une frame retiree, `verify_extracted_lot`
    # refuse avec ses constats bloquants.
    p3 = _socle(releve, "p3-lot-non-conforme")
    frames = frames_extraites_du_projet(p3)
    # La frame retiree est celle du **MILIEU** : ni la premiere, ni la
    # derniere. Un controle qui ne regarderait qu'un bout de la liste ne se
    # demasque pas autrement (regle des fabriques, point 2 bis).
    frames[len(frames) // 2].unlink()
    makepdf("21-lot-non-conforme", p3, "--lot", LOT)

    # -- bloc 3 : la mire de calibration --------------------------------------
    p4 = _socle(releve, "p4-mire")
    mire("30-mire-nominale", p4, "--chaine", CHAINE)
    mire("31-mire-relance-identique", p4, "--chaine", CHAINE)
    mire("32-mire-autre-chaine", p4, "--chaine", CHAINE_VOISINE)
    mire("33-mire-overwrite", p4, "--chaine", CHAINE, amont=("--overwrite",))
    mire("34-mire-avec-commentaire", p4, "--chaine", "banc identite commentee",
         "--commentaire", "chaine de banc, jamais imprimee")

    p5 = _socle(releve, "p5-mire-refus")
    mire("35-mire-chaine-trop-longue", p5, "--chaine", "x" * 120)
    mire("36-mire-commentaire-trop-long", p5, "--chaine", CHAINE,
         "--commentaire", "y" * 400)
    # `patches-14-v3` est ACCEPTE : il ne porte simplement pas le bandeau de
    # temoins (`CALIBRATION_PAGE_BAND_PRESETS`). Le scenario mesure donc une
    # mire VALIDE d'une autre forme, pas un refus -- le nommer « refuse »
    # aurait fait croire a une couverture qui n'existe pas.
    mire("37-mire-preset-sans-bandeau", p5, "--chaine", CHAINE,
         amont=("--nombre-patchs", "patches-14-v3"))
    mire("38-mire-vocabulaire-refuse", p5, "--chaine", CHAINE,
         amont=("--frames-par-page", "7"))
    mire("39-mire-geometrie-impossible", p5, "--chaine", CHAINE,
         amont=("--orientation", "paysage", "--nombre-patchs", "patches-18-v2"))

    # -- bloc 4 : les refus communs, joues sur les DEUX commandes -------------
    absent = travail / "projets" / "p6-inexistant"
    makepdf("40-projet-inexistant", absent, "--lot", LOT)
    mire("41-mire-projet-inexistant", absent, "--chaine", CHAINE)

    p7 = travail / "projets" / "p7-sans-manifest"
    p7.mkdir(parents=True, exist_ok=True)
    makepdf("42-manifest-absent", p7, "--lot", LOT)
    mire("43-mire-manifest-absent", p7, "--chaine", CHAINE)

    p8 = _socle(releve, "p8-manifest-corrompu")
    (p8 / "project.json").write_text("{ ceci n'est pas du JSON", encoding="utf-8")
    makepdf("44-manifest-illisible", p8, "--lot", LOT)
    p9 = _socle(releve, "p9-manifest-corrompu-mire")
    (p9 / "project.json").write_text("{ ceci n'est pas du JSON", encoding="utf-8")
    mire("45-mire-manifest-illisible", p9, "--chaine", CHAINE)

    # Un manifest **valide en JSON** mais refuse par le schema : c'est l'autre
    # famille du refus « manifest invalide », et elle n'emprunte pas le meme
    # `except` que la precedente.
    pa = _socle(releve, "pa-manifest-hors-schema")
    (pa / "project.json").write_text(
        json.dumps({"schema_version": "2.0", "lots": "pas une liste"}, indent=2),
        encoding="utf-8")
    makepdf("46-manifest-hors-schema", pa, "--lot", LOT)
    pb = _socle(releve, "pb-manifest-hors-schema-mire")
    (pb / "project.json").write_text(
        json.dumps({"schema_version": "2.0", "lots": "pas une liste"}, indent=2),
        encoding="utf-8")
    mire("47-mire-manifest-hors-schema", pb, "--chaine", CHAINE)

    return {
        "rendu_pdf_gele": rendu_pdf_gele,
        "entrees": empreinte_des_entrees(entrees),
        "scenarios": releve.scenarios,
    }


def main(argv=None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--entrees", required=True, type=Path)
    parseur.add_argument("--travail", required=True, type=Path)
    parseur.add_argument("--sortie", required=True, type=Path)
    arguments = parseur.parse_args(argv)

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
