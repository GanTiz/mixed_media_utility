# -*- coding: utf-8 -*-
"""Demo JETABLE de la vague 3 -- pour juger les stories 11.4 et 11.4b a la main.

**Ce fichier n'est pas un livrable et n'est couvert par aucun test.**

**Ce qui change par rapport a `demo_vague_2.py`, et c'est le point.** La demo de
la vague 2 assemblait la chaine des paliers **a la main**, parce que le point
d'entree du produit ne montait que des ecrans temoins. C'est precisement ce qui
a masque le manque pendant deux vagues : la recette passait par la demo, jamais
par `mmu-tui`. Cette demo-ci n'assemble **rien** -- elle appelle
`construire_l_application()`, le meme point d'entree que `python -m
mixed_media_utility.tui`. Tout ce qu'elle ajoute est un **bac a sable** peuple.

Autrement dit : si un ecran manque ici, il manque aussi dans le produit.

**Ce qui est reel :** tous les ecrans, la grille, les jetons, le clavier, les
refus, les panneaux chiffres et l'ecriture des frames sont le code de
production. Les projets sont crees par le coeur (`depot_projets.creer_projet`),
leurs manifestes par le vrai producteur (`build_extraction_manifest`), et le
rush est une **vraie video** copiee depuis `tests/TEST_FILE.mp4`.

**Ce qui est faux, et le reste assume :**

* le bac a sable est jetable et recree a chaque lancement -- son chemin est
  imprime avant de dessiner, et rien n'est ecrit hors de lui ;
* la liste des recents est lue dans **ce** bac, jamais dans les reglages de ta
  machine ;
* le rush « absent » l'est pour de bon : son `source_path` designe un fichier
  qui n'a jamais existe. C'est ce qui rend le relink jouable ;
* et le bac grave, a cote, **de vraies videos** aux mesures que le manifeste
  declare pour ce rush -- deux aires de recherche, l'une ou la recherche
  reussit, l'autre ou elle refuse sur `candidats-multiples`. Sans elles, la
  recherche automatique ne trouvait jamais rien et le seul refus atteignable
  etait `aucun-candidat` : le plan de test annoncait un ecran que le bac ne
  pouvait pas montrer (meme famille que l'ecart `J4`).

**Et a la fermeture de la TUI, la demo rejoue `mmu extract`** sur les memes
arguments, dans un miroir du projet, et imprime la comparaison des deux cotes :
c'est la section `E.6` du plan de test manuel. Les outils de cette comparaison
sont **empruntes au banc du lot F** (`tests/unit/tui/test_identite_extraction.py`)
plutot que reecrits : deux redactions de la meme mesure divergent tot ou tard.

Lancer, depuis n'importe ou :

    python _bmad-output/planning-artifacts/ux-designs/ux-tui-2026-08-27/demo_vague_3.py

Options : `--ascii`, `--sans-couleur` (ou `NO_COLOR`), `--bac <chemin>`.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_DEPOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_DEPOT / "src"))
sys.path.insert(0, str(_DEPOT / "tests" / "unit"))

from mixed_media_utility import extraction, relink  # noqa: E402
from mixed_media_utility.gui.depot_projets import creer_projet  # noqa: E402
from mixed_media_utility.io.extraction_manifest import (  # noqa: E402
    MANIFEST_FILENAME, build_extraction_manifest)
from mixed_media_utility.tui import projets  # noqa: E402
from mixed_media_utility.tui import (  # noqa: E402
    atelier_extraction_ecriture as ecriture_tui)
from mixed_media_utility.tui.atelier_extraction_ecriture import (  # noqa: E402
    construire_l_application)

from test_extraction_manifest import make_record, make_selection  # noqa: E402

#: La vraie video du depot. Elle est en **Git LFS** : dans un conteneur sans
#: `git-lfs`, elle vaut 132 octets et la previz echouera sur un message de
#: decodage. La demo le dit plutot que de laisser le mystere.
RUSH_SOURCE = _DEPOT / "tests" / "TEST_FILE.mp4"

#: Trois rushes **distinguables**, et l'absent en TROISIEME position -- jamais
#: en premiere. Un ecran qui viserait toujours le premier ne se demasquerait pas
#: autrement, et c'est la quatrieme recidive du depot sur cette famille.
#:
#: **Le sixieme champ est le timecode de depart, et son absence etait un ecart**
#: (`J4`, 2026-08-30). Aucun rush du bac n'en portait, si bien que le troisieme
#: critere d'appariement sortait `TC ·` -- le glyphe « non renseigne » -- sur
#: les captures `13` et `14`. Le coeur disait vrai : il n'y avait pas de
#: timecode. Mais la section B.3 du plan de test manuel annonce **trois**
#: criteres, et le bac ne permettait d'en montrer que deux. Meme famille que
#: l'ecart deja constate sur B.5 : ce n'est pas l'ecran qu'on corrige, c'est ce
#: qu'on lui donne a montrer.
#:
#: Les trois timecodes **different**, comme les cadences et les resolutions : un
#: remplissage uniforme rendrait invisible un appariement decale entre un rush
#: et la reference que le coeur charge pour lui.
RUSHES = (
    ("rush_present", 25.0, 1920, 1080, True, "01:00:00:00"),
    ("zz_rush_lie", 50.0, 1280, 720, True, "02:15:30:12"),
    ("rush_hiver", 24.0, 4096, 2160, False, "10:12:30:04"),
)

#: Le second projet : DEUX absents, la cible en seconde position parmi eux.
#: C'est l'AC 4.4 -- « un seul rush par validation » -- et elle ne se mesure a
#: la main que sur ce cas-la.
#:
#: **Le second absent n'a PAS de timecode, et c'est delibere.** Les deux formes
#: doivent etre jouables a la main : celle ou les trois criteres sont renseignes
#: (`rush_hiver`) et celle ou le troisieme manque et sort le glyphe « neutre »
#: (`rush_perdu_a`). Un bac ou tous les rushes porteraient un timecode ne
#: permettrait plus de voir que la TUI **n'invente pas** un critere absent.
RUSHES_A_DEUX_ABSENTS = (
    ("rush_present", 25.0, 1920, 1080, True, "01:00:00:00"),
    ("rush_perdu_a", 30.0, 3840, 2160, False, None),
    ("rush_hiver", 24.0, 4096, 2160, False, "10:12:30:04"),
)


def peupler(dossier: Path, rushes, videos: Path) -> Path:
    """Un projet dont le manifeste vient du VRAI producteur.

    Un manifeste ecrit a la main serait refuse par `validate_manifest`, donc par
    `diagnostiquer`, donc par l'ecran de projet : la demo montrerait un refus au
    lieu de l'atelier. Piege paye sur la demo de la vague 2.
    """
    manifeste = json.loads((dossier / MANIFEST_FILENAME).read_text("utf-8"))
    identite = manifeste["project_id"]
    for rush_id, cadence, largeur, hauteur, present, timecode in rushes:
        if present:
            chemin = videos / f"{rush_id}.mp4"
            if not chemin.exists():
                shutil.copyfile(RUSH_SOURCE, chemin)
            source = str(chemin)
        else:
            # Un chemin qui n'a jamais existe : `statut_de_liaison` rend
            # `delinke-chemin-absent`, et le relink a de quoi travailler.
            source = str(videos / "jamais_vu" / f"{rush_id}.mov")
        manifeste = build_extraction_manifest(manifeste, make_record(
            # `source_start_timecode` vit dans la SELECTION, et le producteur
            # le rediffuse sur `rushes[]` : c'est de la qu'il remonte a
            # `relink.charger_reference`, donc aux trois criteres de `E2-1b`.
            # L'ecrire directement sur le rush serait une seconde porte.
            make_selection(fps_source=cadence, fps_target=cadence / 2,
                           source_start_timecode=timecode),
            # `fps_source` est passe des DEUX cotes : le producteur refuse un
            # enregistrement dont la cadence typee contredit la selection, et il
            # a raison -- « ecrire les deux produirait un manifest dont la
            # valeur typee et la valeur exacte se contredisent ».
            project_id=identite, rush_id=rush_id,
            fps_source=cadence, fps_target=cadence / 2,
            rush_source_name=f"{rush_id}.mp4", rush_source_path=source,
            source_width=largeur, source_height=hauteur))
    (dossier / MANIFEST_FILENAME).write_text(
        json.dumps(manifeste, indent=2, sort_keys=True), encoding="utf-8")
    return dossier


#: Le rush absent sur lequel les deux recherches de `B.5` se jouent. Il est le
#: TROISIEME de `RUSHES` et le SECOND des deux absents de
#: `RUSHES_A_DEUX_ABSENTS` : les memes fichiers servent donc aux deux projets,
#: parce que les trois criteres d'identite y sont identiques.
RUSH_A_RETROUVER = "rush_hiver"

#: Les deux dossiers de recherche de `B.5`, et ils ne montrent pas la meme
#: chose : le premier fait REUSSIR la recherche (un seul candidat retenu), le
#: second la fait REFUSER (`candidats-multiples`). Les noms sont ceux que
#: l'operateur tape dans l'explorateur, ils sont donc courts et sans accent.
DOSSIER_UN_CANDIDAT = "retrouvailles-1-candidat"
DOSSIER_DEUX_CANDIDATS = "retrouvailles-2-candidats"


def _graver_une_video(destination: Path, *, cadence: float, largeur: int,
                      hauteur: int, cardinal: int, timecode: str) -> None:
    """Graver une VRAIE video aux mesures demandees, par ffmpeg.

    Un fichier bidon ne servirait a rien : `rechercher_candidat` ECARTE
    silencieusement un fichier au bon nom que le probe ne sait pas lire, si
    bien qu'un leurre non decodable ne serait jamais un candidat. Pour que le
    coeur ait deux candidats a departager, il lui faut deux fichiers que
    `probe_reel` lit et dont les trois criteres correspondent.

    `-frames:v` fixe le cardinal EXACT (donc `source_frame_count_is_exact` du
    cote candidat), et `-timecode` pose la piste `tmcd` d'ou sort le troisieme
    critere. La mire est un aplat : la video ne sert qu'a etre mesuree, et un
    `testsrc2` en 4096x2160 pesait mille fois plus lourd pour rien.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi",
         "-i", f"color=c=0x1e2a38:size={largeur}x{hauteur}:rate={cadence}",
         "-frames:v", str(cardinal),
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-timecode", timecode,
         str(destination)],
        check=True, capture_output=True)


def _timecode_voisin(timecode: str) -> str:
    """Un timecode DIFFERENT de celui du manifeste, derive de lui.

    L'heure avance d'une unite : le leurre reste un timecode plausible -- une
    autre prise du meme tournage -- tout en garantissant que le troisieme
    critere echoue. Rien n'est ecrit en dur ici non plus.
    """
    heures, reste = timecode.split(":", 1)
    return f"{(int(heures) + 1) % 24:02d}:{reste}"


def poser_les_retrouvailles(projet: Path, racine: Path,
                            rush_id: str = RUSH_A_RETROUVER) -> dict:
    """Les deux dossiers ou l'operateur fait chercher le rush absent (`B.5`).

    **Toutes les mesures sont LUES du manifeste reellement ecrit**, par
    `relink.charger_reference` -- la meme fonction que la TUI appelle pour
    apparier. Recopier les chiffres de `RUSHES` a la main rouvrirait la porte
    que `peupler` ferme deja pour le manifeste : c'est le producteur qui fait
    foi, jamais une constante de la demo.

    Arborescence posee, et l'ORDRE compte parce que `rechercher_candidat`
    parcourt les candidats homonymes tries par chemin :

        retrouvailles-1-candidat/
            01-cache-local/rush_hiver.mp4     bon nom, MAUVAIS timecode
            02-disque-atelier/rush_hiver.mp4  <-- la bonne, RETENUE
            03-corbeille/rush_hiver.mp4       bon nom, illisible
        retrouvailles-2-candidats/
            01-cache-local/rush_hiver.mp4     bon nom, MAUVAIS timecode
            02-disque-atelier/rush_hiver.mp4  <-- retenue
            03-disque-secours/rush_hiver.mp4  <-- retenue
            04-corbeille/rush_hiver.mp4       bon nom, illisible

    Regle des fabriques du depot, points 2 et 2 bis : les fichiers retenus ne
    sont **ni les premiers ni les derniers** de leur dossier, et les trois
    familles sont **distinguables** (retenu, ecarte par critere, ecarte par le
    probe). Une aire de recherche qui ne contiendrait que les copies conformes
    ne demasquerait ni un filtre qui prendrait le premier homonyme venu, ni un
    probe en echec compte comme candidat.
    """
    manifeste = json.loads((projet / MANIFEST_FILENAME).read_text("utf-8"))
    reference = relink.charger_reference(manifeste, rush_id)
    if reference.criteres_non_verifiables:
        raise SystemExit(
            f"Bac inutilisable : le manifeste de {projet.name} ne porte pas de "
            f"reference pour {', '.join(reference.criteres_non_verifiables)} sur "
            f"{rush_id!r}. La recherche automatique refuserait en amont, sur "
            "`critere-non-verifiable-en-recherche`, et `B.5` ne montrerait pas "
            "le refus qu'il annonce.")
    rush = next(entree for entree in manifeste["rushes"]
                if entree["rush_id"] == rush_id)
    mesures = dict(cadence=rush["fps_source"],
                   largeur=rush["resolution_source"]["width"],
                   hauteur=rush["resolution_source"]["height"],
                   cardinal=reference.source_frame_count)

    un = racine / DOSSIER_UN_CANDIDAT
    deux = racine / DOSSIER_DEUX_CANDIDATS
    nom = reference.source_name

    # La bonne, gravee UNE fois puis recopiee : trois exemplaires identiques
    # coutent trois encodages pour rien.
    conforme = racine / ".gravure" / nom
    _graver_une_video(conforme, timecode=reference.source_start_timecode,
                      **mesures)
    leurre = racine / ".gravure" / "leurre" / nom
    _graver_une_video(
        leurre, timecode=_timecode_voisin(reference.source_start_timecode),
        **mesures)

    for dossier, sous_dossiers in ((un, ("02-disque-atelier",)),
                                   (deux, ("02-disque-atelier",
                                           "03-disque-secours"))):
        (dossier / "01-cache-local").mkdir(parents=True)
        shutil.copyfile(leurre, dossier / "01-cache-local" / nom)
        for sous in sous_dossiers:
            (dossier / sous).mkdir(parents=True)
            shutil.copyfile(conforme, dossier / sous / nom)
    for dossier, corbeille in ((un, "03-corbeille"), (deux, "04-corbeille")):
        (dossier / corbeille).mkdir(parents=True)
        # Ni video ni conteneur : `probe_reel` leve, et le coeur ECARTE au lieu
        # d'echouer. C'est ce que la demo doit pouvoir montrer aussi.
        (dossier / corbeille / nom).write_text(
            "Ceci n'est pas une video : le probe echoue, le candidat est "
            "ecarte, la recherche continue.\n", encoding="utf-8")

    # **Et on le VERIFIE, bruyamment**, comme `capturer.py` verifie ses
    # projets : une demo qui promet un refus qu'elle ne produit pas est
    # exactement l'ecart que ce correctif repare. On rejoue donc les deux
    # recherches par le coeur lui-meme, avant de laisser l'operateur les jouer
    # au clavier.
    try:
        retenu = relink.rechercher_candidat(un, reference=reference)
    except relink.RelinkError as refus:
        raise SystemExit(
            f"Bac inutilisable : la recherche nominale sous {un.name} refuse sur "
            f"{refus.reason!r}. `B.5a` annonce un relink qui PASSE. Motif du "
            f"coeur : {refus}") from refus
    if retenu.parent.name != "02-disque-atelier":
        raise SystemExit(
            f"Bac inutilisable : la recherche nominale a retenu {retenu}, pas "
            "la copie conforme de `02-disque-atelier`.")
    try:
        relink.rechercher_candidat(deux, reference=reference)
    except relink.RelinkError as refus:
        if refus.reason != relink.REFUS_CANDIDATS_MULTIPLES:
            raise SystemExit(
                f"Bac inutilisable : {deux.name} refuse sur {refus.reason!r} et "
                f"non sur {relink.REFUS_CANDIDATS_MULTIPLES!r}.") from refus
    else:
        raise SystemExit(
            f"Bac inutilisable : {deux.name} n'a pas refuse. `B.5` annonce "
            f"{relink.REFUS_CANDIDATS_MULTIPLES!r} et l'ecran ne le montrerait "
            "pas.")
    return {"un": un, "deux": deux, "rush_id": rush_id}


def poser_le_bac(racine: Path) -> dict:
    shutil.rmtree(racine, ignore_errors=True)
    racine.mkdir(parents=True)
    videos = racine / "rushes"
    videos.mkdir()

    demo = peupler(creer_projet(racine, "projet_demo").chemin, RUSHES, videos)
    deux = peupler(creer_projet(racine, "projet_deux_absents").chemin,
                   RUSHES_A_DEUX_ABSENTS, videos)
    # Les deux aires de recherche de `B.5`. `rush_hiver` porte les MEMES trois
    # criteres dans les deux projets : un seul jeu de fichiers les sert tous
    # les deux, `B.5` comme `B.6`.
    retrouvailles = (poser_les_retrouvailles(demo, racine)
                     if shutil.which("ffmpeg") else None)

    # Les recents vivent DANS le bac : la demo ne peut pas polluer les tiens.
    recents = projets.Recents(racine / "recents.json")
    # **Les horodatages sont INJECTES, et sans cela l'ordre est faux.** Mesure
    # du 2026-08-30, au parcours `H3` : le bac note ses deux ouvertures dans la
    # MEME seconde, or `ouvert_le` a la seconde pour granularite. Le tri de
    # `Recents.lire` est stable, donc deux entrees a egalite gardent leur ordre
    # d'insertion -- c'est-a-dire l'INVERSE de « le plus recent en tete » : le
    # bac montrait `projet_deux_absents` en tete alors que `projet_demo` avait
    # ete ouvert en dernier, et le guide de test fait taper `Entree` sur
    # `projet_demo` des la premiere touche. Le premier geste du parcours
    # ouvrait donc l'autre projet.
    #
    # Ce n'est PAS un defaut de `Recents` -- a des secondes distinctes, le
    # regime reel, l'ordre est juste, et c'est mesure. C'en est un du bac, qui
    # cadence ses ouvertures plus vite qu'un humain. `noter_ouverture` porte
    # `quand` exactement pour ce cas, et sa docstring le dit : « sans lui, deux
    # ouvertures dans la meme seconde seraient indistinguables ».
    for rang, chemin in enumerate((deux, demo)):   # `demo` ouvert EN DERNIER
        recents.noter_ouverture(chemin, quand=f"2026-08-30T09:0{rang}:00Z")
    return {"racine": racine, "recents": recents, "demo": demo, "deux": deux,
            "retrouvailles": retrouvailles}


# ---------------------------------------------------------------------------
# E.6 -- l'identite avec `mmu extract`, mesuree par le comparateur DU BANC
# ---------------------------------------------------------------------------

#: Le banc du lot F : `tests/unit/tui/test_identite_extraction.py`. La demo lui
#: **emprunte** ses outils de comparaison au lieu d'en ecrire une seconde
#: version. Deux redactions de la meme mesure divergent tot ou tard, et le
#: depot a deja paye ce defaut : le banc porte la LOGIQUE (arbre des frames par
#: condensat, aplatissement du manifeste, neutralisation des volatiles,
#: egalite d'ensembles sur les chemins divergents, canal d'acquittement
#: interactif), la demo porte la MISE EN SCENE -- decouvrir ce que la TUI vient
#: d'ecrire, rejouer la CLI, rendre le verdict lisible a l'oeil.
_BANC = _DEPOT / "tests" / "unit" / "tui" / "test_identite_extraction.py"

_banc_charge = None


def banc():
    """Le module du banc, charge par son CHEMIN et une seule fois.

    Par le chemin plutot que par `import tui.test_identite_extraction` : ce
    dernier poserait dans `sys.modules` un paquet de premier niveau nomme
    `tui`, a un import de distance de `mixed_media_utility.tui`. Le nom
    explicite ferme cette confusion.
    """
    global _banc_charge
    if _banc_charge is None:
        # Le banc importe `outils_frontiere`, son voisin de dossier. Sans
        # pytest pour poser ce dossier sur le chemin (les bancs n'ont pas
        # d'`__init__.py`), c'est a l'appelant de le faire.
        voisinage = str(_BANC.parent)
        if voisinage not in sys.path:
            sys.path.insert(0, voisinage)
        specification = importlib.util.spec_from_file_location(
            "banc_identite_extraction", _BANC)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        _banc_charge = module
    return _banc_charge


@contextlib.contextmanager
def observer_les_ecritures(photos: Path):
    """Noter le PLAN et le RAPPORT de chaque ecriture, sans rien changer.

    C'est une **observation**, pas une substitution : `executer_le_plan` est
    appelee avec ses arguments d'origine, et son resultat est rendu tel quel.
    La demo ne peut pas lire ces deux objets autrement -- l'application ne les
    conserve nulle part une fois l'ecran de resultat ferme --, et `E.6` a
    besoin des deux : le plan porte les arguments **exacts** de la commande
    `mmu extract` equivalente (bornes comprises), le rapport porte le code
    retour du cote TUI.

    Chaque projet est en outre **photographie juste avant sa premiere
    ecriture**, et c'est ce point-la qui rend `E.6` honnete : `mmu extract` est
    rejoue sur le **meme etat de depart** que celui ou la TUI a ecrit.

    **Pas avant `.run()`, et c'est mesure.** Une photo prise au lancement rate
    les gestes de la session qui precedent l'extraction -- typiquement le
    relink de `B.5a`, qui reecrit `rushes[].source_path`. Avec une photo prise
    trop tot, `E.6` criait un ecart `rushes[2].source_path` qui n'en est pas
    un : la TUI et la CLI ne divergeaient pas, c'est la demo qui n'avait pas
    rejoue le relink. Une fausse alerte est le mode de panne que `E.6` existe
    pour ne pas avoir.

    A la **premiere** ecriture d'un projet, aucun lot n'a encore ete ecrit par
    la TUI : la copie ne porte donc qu'un manifeste et des dossiers vides. Les
    ecritures suivantes rejouent sur le meme miroir, qui suit le meme chemin.
    """
    ecritures: list[tuple] = []
    photographies: dict[Path, Path] = {}
    vrai = ecriture_tui.executer_le_plan

    def noter(plan, *arguments, **nommes):
        projet = plan.dossier_projet.resolve()
        if projet not in photographies:
            copie = photos / projet.name
            shutil.rmtree(copie, ignore_errors=True)
            copie.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(projet, copie)
            photographies[projet] = copie
        rapport = vrai(plan, *arguments, **nommes)
        ecritures.append((plan, rapport))
        return rapport

    ecriture_tui.executer_le_plan = noter
    try:
        yield ecritures, photographies
    finally:
        ecriture_tui.executer_le_plan = vrai


def _lister(chemins, marge: str, combien: int = 12) -> None:
    """Imprimer une liste de chemins, bornee : un ecart massif -- la CLI
    rejouee sur d'autres arguments -- en produit des dizaines, et une liste qui
    defile hors du terminal ne se lit pas."""
    ordonnes = sorted(chemins)
    for chemin in ordonnes[:combien]:
        print(f"{marge}{chemin}")
    if len(ordonnes) > combien:
        print(f"{marge}... et {len(ordonnes) - combien} autre(s)")


def _texte_de_commande(arguments) -> str:
    """La commande telle qu'Egan la retape, depuis la racine du depot."""
    return " ".join(["python", "-m", "mixed_media_utility.cli"]
                    + [f'"{a}"' if " " in str(a) else str(a) for a in arguments])


def commande_equivalente(plan, lot, miroir: Path) -> list[str]:
    """Les arguments `mmu extract` qui correspondent a UN lot du plan.

    Ils sont **lus du plan que la TUI a reellement execute**, jamais
    reconstruits depuis le manifeste : le plan est litteralement ce que
    `run_extraction` a recu, bornes comprises. Une commande reconstruite
    ailleurs serait une seconde redaction de plus.
    """
    arguments = ["extract", "--project", str(miroir),
                 "--video", str(plan.video_path),
                 "--fps", str(lot.fps_target)]
    if plan.source_in_timecode:
        arguments += ["--in", plan.source_in_timecode]
    if plan.source_out_timecode:
        arguments += ["--out", plan.source_out_timecode]
    return arguments


def rejouer_la_cli(arguments) -> tuple[int, str]:
    """Une invocation de `mmu extract`, acquittee **au terminal**.

    Rend le code retour et **tout ce que la commande a dit** -- garde de cote
    plutot que jetee : une invocation qui echoue doit pouvoir montrer son
    motif, et une qui reussit n'a pas a noyer le verdict de `E.6` sous
    quarante lignes de rapport de confirmation.

    Le canal d'acquittement n'est pas un detail : `run_extraction` force
    `interactive=False` des que le consentement vient de `--yes`, si bien qu'un
    `mmu extract --yes` ecrirait `confirmation.mode: non_interactif` comme la
    TUI et la comparaison ne montrerait **aucun** ecart -- elle contournerait
    l'exception de l'AC 7.2 au lieu de la mesurer. C'est le motif que le banc
    porte sur sa classe `FluxTty`, et c'est `FluxTty` **du banc** qui sert ici.
    """
    from mixed_media_utility import cli

    vrais = (sys.stdin, sys.stdout, sys.stderr)
    # Une reponse affirmative par question ; `readline` rend `""` une fois la
    # liste epuisee, ce qui vaudrait refus. On en donne de quoi couvrir la
    # question d'extraction et celle de la colorimetrie incomplete.
    sys.stdin = banc().FluxTty(["o\n"] * 4)
    sortie, erreur = banc().FluxTty(), banc().FluxTty()
    # `sys.stderr` compte autant que `sys.stdout` : le rapport de confirmation
    # passe par le logger de la commande, dont le `StreamHandler` se lie a
    # `sys.stderr` AU MOMENT DE SA CONSTRUCTION, c'est-a-dire dans `cli.main`.
    sys.stdout, sys.stderr = sortie, erreur
    try:
        code = cli.main(list(arguments))
    finally:
        sys.stdin, sys.stdout, sys.stderr = vrais
    return code, "".join(sortie.ecrit + erreur.ecrit)


def comparer_avec_la_cli(ecritures, photos: dict, miroirs: Path) -> int:
    """`E.6` : rejouer `mmu extract` et confronter les deux cotes.

    Rend `0` si tout coincide, `1` sinon -- et **le dit fort** dans ce cas.
    Une sortie qui annoncerait « identique » sans l'avoir mesure serait pire
    que pas de sortie du tout : c'est exactement le mode de panne que cette
    vague a passe la journee a chasser.
    """
    outils = banc()
    print()
    print("=" * 72)
    print("E.6 -- identite de la TUI avec `mmu extract`")
    print("=" * 72)

    if not ecritures:
        # **Ne jamais comparer du vide et annoncer un succes.** Si l'operateur
        # n'a rien extrait, la sortie le dit et s'arrete la.
        print("Aucun lot ecrit dans cette session : il n'y a rien a comparer.")
        print("Rejoue les sections D et E jusqu'a « Extraire » pour que E.6 ait")
        print("de la matiere.")
        return 0

    # Un miroir par projet touche, ne dans l'etat d'AVANT l'ecriture.
    miroirs.mkdir(parents=True, exist_ok=True)
    ecarts = 0
    for projet in dict.fromkeys(plan.dossier_projet.resolve()
                                for plan, _ in ecritures):
        siennes = [(plan, rapport) for plan, rapport in ecritures
                   if plan.dossier_projet.resolve() == projet]
        ecarts += _comparer_un_projet(outils, projet, siennes,
                                      photos[projet], miroirs / projet.name)

    print()
    if ecarts:
        print("!" * 72)
        print(f"!! {ecarts} ECART(S) : la TUI et `mmu extract` ne produisent PAS")
        print("!! la meme chose. C'est un BLOCAGE -- remonte-le tel quel.")
        print("!" * 72)
        return 1
    print(">>> IDENTIQUE des deux cotes. AC 7.1, 7.2 et 7.3 tenues sous tes yeux.")
    return 0


def _comparer_un_projet(outils, projet: Path, siennes, photo: Path,
                        miroir: Path) -> int:
    """Le corps de `E.6` pour UN projet. Rend le nombre d'ecarts trouves."""
    shutil.rmtree(miroir, ignore_errors=True)
    shutil.copytree(photo, miroir)

    print()
    print(f"Projet          : {projet}")
    print(f"Miroir CLI      : {miroir}")
    print("Commandes rejouees -- tu peux les retaper telles quelles depuis la")
    print("racine du depot (la demo repond `o` a la question du terminal : ce")
    print("canal d'acquittement, et lui seul, fait diverger `confirmation.mode`) :")

    code_cli = extraction.CODE_SUCCES
    for plan, _rapport in siennes:
        for lot in plan.lots:
            arguments = commande_equivalente(plan, lot, miroir)
            print(f"    {_texte_de_commande(arguments)}")
            code_cli, dit = rejouer_la_cli(arguments)
            if code_cli != extraction.CODE_SUCCES:
                # Comme `executer_le_plan`, la serie s'arrete au premier refus
                # -- et le motif de la commande est rendu, jamais avale.
                print(f"    -> code {code_cli}. Ce que la commande a dit :")
                for ligne in dit.splitlines()[-12:]:
                    print(f"       {ligne}")
                break
        if code_cli != extraction.CODE_SUCCES:
            break

    ecarts = 0

    # -- les TIFF, chemin relatif -> condensat, par l'outil du banc ----------
    cote_tui = outils.arbre_des_frames(projet)
    cote_cli = outils.arbre_des_frames(miroir)
    communs = sorted(set(cote_tui) & set(cote_cli))
    identiques = [c for c in communs if cote_tui[c] == cote_cli[c]]
    divergents = sorted(set(cote_tui) ^ set(cote_cli)) + [
        c for c in communs if cote_tui[c] != cote_cli[c]]
    print()
    print(f"TIFF            : {len(cote_tui)} cote TUI, {len(cote_cli)} cote CLI, "
          f"{len(identiques)} identiques octet a octet")
    if divergents:
        ecarts += 1
        print(f"                  PREMIER CHEMIN QUI DIFFERE : {divergents[0]}")
        print(f"                  ({len(divergents)} au total)")

    # -- le manifeste, egalite d'ENSEMBLES sur les chemins divergents --------
    lots_ecrits = {lot.lot_id for _plan, rapport in siennes
                   for lot in rapport.lots_ecrits}
    apres = outils.manifeste(projet)
    attendus = {f"lots[{rang}].confirmation.mode"
                for rang, lot in enumerate(apres.get("lots") or [])
                if lot.get("lot_id") in lots_ecrits}
    trouves = outils.chemins_divergents(apres, outils.manifeste(miroir))
    print(f"Manifeste       : {len(trouves)} chemin(s) divergent(s)")
    _lister(trouves, " " * 18)
    print("                  attendu, et rien d'autre :")
    _lister(attendus or ["aucun"], " " * 18)
    print("                  (`lots[].confirmation.mode` est l'exception NOMMEE")
    print("                   de l'AC 7.2 : la TUI porte son propre panneau)")
    if trouves != attendus:
        ecarts += 1
        print(f"                  ECART. En trop ({len(trouves - attendus)}) :")
        _lister(trouves - attendus, " " * 20)
        print(f"                  Manquants ({len(attendus - trouves)}) :")
        _lister(attendus - trouves, " " * 20)

    # -- le code retour, des deux cotes -------------------------------------
    code_tui = siennes[-1][1].code_retour
    print(f"Code retour     : TUI {code_tui} · mmu extract {code_cli}")
    if code_tui != code_cli:
        ecarts += 1
        print("                  ECART : les deux cotes ne rendent pas le meme "
              "code de sortie")
    return ecarts


def main(argv: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(prog="demo_vague_3")
    lecteur.add_argument("--ascii", action="store_true", dest="ascii_seul")
    lecteur.add_argument("--sans-couleur", action="store_true",
                         default="NO_COLOR" in os.environ)
    lecteur.add_argument("--bac", type=Path, default=None)
    options = lecteur.parse_args(argv)

    racine = options.bac or Path(tempfile.gettempdir()) / "demo_mmu_vague_3"
    bac = poser_le_bac(racine)

    taille = RUSH_SOURCE.stat().st_size if RUSH_SOURCE.exists() else 0
    print(f"Bac a sable jetable : {racine}")
    print("  projet_demo            3 rushes, dont rush_hiver INTROUVABLE")
    print("  projet_deux_absents    3 rushes, dont DEUX introuvables")
    print()
    # Les deux chemins que `B.5` fait taper : ils sont imprimes plutot que
    # decrits, parce que c'est au clavier qu'ils servent.
    if bac["retrouvailles"] is None:
        print("  ATTENTION : ffmpeg est introuvable dans le PATH, donc les deux")
        print("  dossiers de recherche de B.5 n'ont PAS ete graves. Le relink")
        print("  par `r` refusera sur `aucun-candidat`, jamais sur")
        print("  `candidats-multiples`. Installer ffmpeg pour jouer B.5.")
    else:
        print("  Retrouver rush_hiver (`r`), deux dossiers a taper :")
        for quoi, chemin in (("un candidat, la recherche REUSSIT",
                              bac["retrouvailles"]["un"]),
                             ("deux candidats, elle REFUSE",
                              bac["retrouvailles"]["deux"])):
            print(f"    {quoi:<34} {chemin}")
    if taille < 1000:
        print()
        print("  ATTENTION : tests/TEST_FILE.mp4 fait "
              f"{taille} octets -- c'est un POINTEUR Git LFS, pas une video.")
        print("  La previz et l'extraction echoueront sur un message de "
              "decodage.")
        print("  Corriger par :  git lfs pull --include=\"tests/TEST_FILE.mp4\"")
    print()
    print("A la sortie de la TUI, E.6 rejoue `mmu extract` sur les memes")
    print("arguments et compare les deux cotes. Rien n'est ecrit hors de ce")
    print("dossier. Entree pour dessiner.")
    input()

    # **Aucun cablage ici.** C'est le point d'entree du PRODUIT, le meme que
    # `python -m mixed_media_utility.tui` : si un ecran manque a la demo, il
    # manque aussi a l'operateur. `observer_les_ecritures` n'en change rien :
    # elle NOTE le plan et le rapport au passage, sans toucher aux arguments
    # ni au resultat.
    with observer_les_ecritures(racine / ".avant") as (ecritures, photos):
        construire_l_application(sans_couleur=options.sans_couleur,
                                 ascii_seul=options.ascii_seul,
                                 recents=bac["recents"]).run()
    return comparer_avec_la_cli(ecritures, photos, racine / ".miroir")


if __name__ == "__main__":
    sys.exit(main())
