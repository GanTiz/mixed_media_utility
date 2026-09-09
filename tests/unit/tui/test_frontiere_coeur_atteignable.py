# -*- coding: utf-8 -*-
"""`EPIC11-ARB-159` -- ce que le coeur offre et que la TUI n'atteint pas.

**Ce banc et lui seul mesure la frontiere de la vague Scan.** Aucun autre lot
n'y ecrit : la regle de decoupage du depot est stricte, et le commit `82e64de`
a paye ce qu'il en coute de la relacher.

---

## Le defaut que cette frontiere ferme, et pourquoi la forme compte

Egan ne pouvait pas designer un PDF comme source de scan. Le coeur savait
pourtant l'ingerer, et `atelier_scan.source_acceptable` lisait bien la table du
coeur -- ce qui rendait le defaut invisible a la relecture. Il tenait a un
**ecart entre ce que le coeur accepte et ce que la TUI permet de lui donner**.

Une frontiere ecrite en **appartenance** -- « le `.pdf` est atteignable » --
n'aurait jamais montre ce defaut, et ne montrera pas le prochain : elle ne
rougit que sur le cas qu'elle nomme. Les deux mesures de ce banc sont donc
ecrites en **ensembles EXACTS**, dans les deux sens. « Ce champ diverge » ne
mesure rien ; « l'ensemble des chemins qui divergent est exactement {X} »
mesure l'exception ET son unicite.

## Et la frontiere ne s'arrete pas aux FORMATS

C'est le conseil de la session `oc/epic-11-TUI`, verifie ici plutot que cru :
la meme famille de defaut se joue hors des extensions. `EPIC7-ARB-90` decrit un
geste -- « apres un *Oui* explicite de l'operatrice » -- que l'operatrice n'a
aucun moyen de faire, parce que `remplacer_les_detections` n'est pose par aucun
chemin de `tui/`. Un format injoignable et une capacite injoignable sont le
meme defaut ; ce banc les mesure ensemble.
"""
from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility import (scan_calibrate, scan_detect, scan_detection,
                                 scan_ingest, scan_write)
from mixed_media_utility.tui import atelier_scan

PAQUET_TUI = RACINE / "src" / "mixed_media_utility" / "tui"

def _le_coeur_ingere(extension: str) -> bool:
    """Le coeur sait-il ingerer un fichier de cette extension ? **Mesure.**

    On fabrique un fichier reel de cette extension et on demande a
    `scan_ingest.mesurer_la_source` -- le point d'entree que l'ecran appelle --
    s'il le reconnait. La reponse ne se lit dans aucune table : c'est le
    comportement qui repond.

    **Un refus de CONTENU n'est pas un refus de FORMAT**, et la distinction est
    le coeur de la mesure : un `.png` de zero octet est reconnu comme format et
    refuse comme contenu. On ne retient donc que
    `UnsupportedScanInputError`, qui est le refus de FORME, et l'on traite tout
    autre refus comme « le format est reconnu ».
    """
    import tempfile

    with tempfile.TemporaryDirectory() as bac:
        chemin = Path(bac) / f"sonde{extension}"
        chemin.write_bytes(b"\x00" * 16)
        try:
            scan_ingest.mesurer_la_source(chemin)
        except scan_ingest.UnsupportedScanInputError:
            return False
        except scan_ingest.ScanIngestError:
            return True
        except Exception:
            return True
        return True


#: L'echantillon d'extensions du test des formats. **Ecrit en dur et
#: independant des deux cotes mesures** : c'est la seule facon qu'un ecart
#: entre le coeur et l'ecran se voie. Il porte les six images, le PDF, et cinq
#: intrus plausibles -- dont `.webp`, qui est le format qu'on ajouterait
#: demain, et `.mp4`, que l'atelier voisin manipule.
CANDIDATS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".pdf",
             ".webp", ".mp4", ".txt", ".zip", ".xyz")


#: Les points d'entree du coeur que l'atelier Scan pilote. La liste est
#: **explicite** et non devinee : un `dir(module)` y ferait entrer les helpers
#: prives au premier renommage, et la frontiere se mettrait a mesurer autre
#: chose sans que personne ne s'en apercoive.
POINTS_D_ENTREE = (
    (scan_ingest, "ingest_scan_lot"),
    (scan_detect, "run_scan_detect"),
    (scan_detection, "detect_lot_pages"),
    (scan_calibrate, "calibrer_la_chaine"),
    (scan_write, "ecrire_depuis_le_document"),
)

#: **Tolerances documentees**, meme statut que les `LANCEURS_TOLERES` de
#: `test_coeur_en_processus.py` : ce n'est pas un affaiblissement silencieux de
#: la garde, c'est un arbitrage ecrit AVEC son motif et son registre.
#:
#: Chacune est au registre de `deferred-work.md`, avec son origine -- et trois
#: des cinq n'y etaient PAS quand cette phrase a ete ecrite pour la premiere
#: fois. Les trois couches de la revue l'ont relevee separement : une liste de
#: tolerances qui revendique un registre qu'elle n'a pas est exactement
#: l'enterrement silencieux qu'elle pretend eviter. Le registre a ete complete,
#: pas la phrase adoucie.
#:
#: Une liste VIDE serait le mensonge inverse -- elle ferait croire la surface
#: complete alors que cinq capacites du coeur n'ont aucun geste dans le produit.
#:
#: **UN FAUX POSITIF CONNU, nomme plutot que tu.**
#: `ecrire_depuis_le_document(confirmer_l_ecrasement=)` est injoignable lui
#: aussi -- le seul site de `tui/` qui pose ce mot-cle vise `calibrer`
#: (`atelier_scan_calibrate.py:1003`), et le site d'ecriture
#: (`atelier_scan_ecriture.py`) ne le pose pas. La mesure large de ce banc le
#: declare pourtant atteint, parce qu'un nom pose QUELQUE PART compte pour
#: tous. C'est la limite documentee ci-dessous, ici a l'etat pur et dans
#: l'arbre courant -- pas sur un mutant hypothetique. Il est au registre avec
#: les cinq autres.
#: **UN SECOND FAUX POSITIF, de la meme famille, apparu le 2026-09-02.**
#: `ingest_scan_lot(manifest=)` figurait ici : le manifeste de projet sert la
#: ligne d'eau des rangs de version, et la TUI n'ouvrait aucun chemin
#: d'ingestion versionnee. **Il en est sorti sans que la dette soit fermee.**
#: Le cablage de l'atelier Pdf pose `manifest=` en appelant
#: `makepdf.etat_des_tirages` -- un tout autre point d'entree --, et la mesure
#: large de ce banc compte un nom pose QUELQUE PART comme atteint pour tous.
#: L'entree a donc ete retiree, sans quoi la table aurait declare hors
#: d'atteinte un mot-cle que la mesure voit desormais pose.
#:
#: **La dette, elle, n'a pas bouge** : aucun ecran n'ouvre d'ingestion
#: versionnee. Elle reste au registre de `deferred-work.md`, avec la mention
#: que cette frontiere ne la mesure plus -- ce qui est exactement la limite
#: que le docstring de `_mots_cles_poses_par_la_tui` annonce, ici a l'etat pur
#: et dans l'arbre courant.
#:
#: **Ce que ce banc ne mesure toujours PAS, et il faut que ce soit ecrit** :
#: les deux points d'entree de `makepdf` ne sont **pas** dans
#: :data:`POINTS_D_ENTREE`, alors que la TUI les pilote depuis le 2026-09-02.
#: Les y verser demande de trancher une dizaine de tolerances -- et deux
#: d'entre elles seraient de faux positifs de plus, `scan_chain_label` et
#: `comment` voyageant par une table de projection
#: (`atelier_pdf_calibration.ARGUMENTS_DU_COEUR`) dont ce banc lit les cles et
#: non les valeurs. C'est un elargissement de la frontiere, pas un cablage :
#: il est **remonte** plutot que fait depuis un lot de cablage.
INJOIGNABLES_TOLERES: dict[str, tuple[str, ...]] = {
    # `EPIC7-ARB-90` : « souhaitez-vous lancer une nouvelle detection sur ce
    # fichier ? + Oui/Non ». L'arbitrage decrit le geste, le coeur le porte, et
    # aucun ecran ne le propose.
    #
    # **`adopter` EST SORTI de cet inventaire le 2026-09-07**, avec le lot
    # d'`EPIC11-ARB-267` : `ParcoursScan.proposer_l_adoption` monte
    # `EcranAdoptionDeLaPlanche`, dont l'issue « adopter » relance la passe
    # avec le drapeau pose. C'est le volet « un mot-cle de MOINS » du docstring
    # ci-dessous qui l'a dit, et il l'a dit dans le sens de la REPARATION --
    # une assertion d'appartenance ne l'aurait pas fait. Il etait au registre
    # depuis le 2026-09-01 ; il n'y a plus sa place.
    "run_scan_detect": ("remplacer_les_detections",),
    # Les deux rappels de l'ecriture : la completude annoncee en cours de passe
    # et la question de l'application de la correction.
    "ecrire_depuis_le_document": ("annoncer_la_completude",
                                  "demander_l_application_de_la_correction"),
}


def _mots_cles_offerts(fonction) -> set[str]:
    """Les parametres que le coeur expose **en mot-cle seul**."""
    return {p.name for p in inspect.signature(fonction).parameters.values()
            if p.kind is p.KEYWORD_ONLY}


def _mots_cles_poses_par_la_tui() -> set[str]:
    """Tout nom que `tui/` pose en mot-cle, a un appel ou dans un dictionnaire.

    **Les deux formes sont necessaires, et l'oublier rendait la mesure
    fausse.** Les points d'entree du coeur sont **injectes** dans les ecrans
    (`detection: Callable = scan_detect.run_scan_detect`) puis appeles par le
    nom du parametre, si bien qu'aucun site d'appel ne porte le nom de la
    fonction du coeur : chercher les appels a `run_scan_detect` dans `tui/` rend
    **zero**, et une frontiere batie la-dessus aurait declare les huit
    mots-cles injoignables. Et un reglage voyage aussi en dictionnaire
    (`{"detection": ...}`, `**reglages`), d'ou la seconde moitie.

    La mesure est volontairement LARGE : elle compte un mot-cle comme atteint
    des qu'il est pose quelque part dans `tui/`, sans chercher a savoir vers
    QUELLE fonction du coeur il part.

    **Ce que cette frontiere ne mesure donc PAS, et c'est mesure plutot que
    suppose.** Un mot-cle **partage** par deux points d'entree est declare
    atteint pour les deux des qu'un seul le pose. Mutant joue le 2026-09-01 :
    ajouter `rappel_progression` a la signature de `detect_lot_pages` --
    exactement ce que le lot J1 va faire -- **survit** a ce banc, parce que ce
    nom est deja pose pour `run_scan_detect`. Les cinq tolerances ci-dessous
    portent toutes des noms UNIQUES a leur fonction, donc la mesure y est
    exacte ; c'est sur un nom partage qu'elle est approchee.

    **Et la mesure precise a ete essayee avant d'etre ecartee**, sur mesure :
    reconstruire les alias locaux de chaque fonction du coeur (`detection`,
    `_calibrer`, ...) puis ne lire que leurs sites d'appel rend **douze faux
    positifs**, dont `dpi` sur `run_scan_detect` -- que la TUI passe pourtant,
    mais par un objet de requete (`DemandeDeDetection`) que la couche
    d'execution deballe. Un mot-cle qui voyage dans une dataclasse n'est pas un
    mot-cle a un site d'appel, et modeliser ces relais ferait de ce banc une
    seconde implementation de la couche d'execution.

    Le sens de l'erreur est donc assume : cette frontiere peut declarer atteint
    ce qui ne l'est pas, jamais l'inverse. C'est le bon sens ici -- un faux
    rouge sur une frontiere finit par la faire desarmer.
    """
    poses: set[str] = set()
    for chemin in sorted(PAQUET_TUI.rglob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call):
                poses.update(k.arg for k in noeud.keywords if k.arg)
            elif isinstance(noeud, ast.Dict):
                poses.update(
                    cle.value for cle in noeud.keys
                    if isinstance(cle, ast.Constant)
                    and isinstance(cle.value, str)
                )
    return poses


# --- moitie 1 : les FORMATS -------------------------------------------------


def test_la_TUI_accepte_EXACTEMENT_les_formats_que_le_coeur_ingere() -> None:
    """Le defaut d'Egan, mesure dans les DEUX SENS.

    * un format que le coeur ingere et que l'ecran refuse est un blocage --
      c'est ce qui l'a empeche de tester le scan ;
    * un format que l'ecran accepte et que le coeur refuse est un piege -- il
      laisse designer une source puis la refuse plus loin, ce qui est **la
      forme exacte** du defaut du 2026-09-01 : `Espace` cochait un PDF que
      l'ingestion refusait ensuite.

    L'egalite d'ensembles porte les deux sens a la fois. Deux assertions
    d'appartenance n'en porteraient qu'un chacune, et c'est le second qui
    manquait.

    **Les candidats sont INDEPENDANTS des deux tables, et la premiere redaction
    de ce test ne l'etait pas** -- defaut trouve par mutation sur ce banc meme.
    Elle balayait `PAGE_EXTENSIONS | {quelques intrus}` : retirer le `.pdf` de
    la table du coeur le retirait **aussi des candidats**, si bien que la
    question « l'ecran accepte-t-il le `.pdf` ? » n'etait plus posee et que le
    test restait VERT sous le mutant qu'il existe pour attraper. Un banc dont
    l'echantillon derive de l'objet mesure ne mesure que sa propre coherence.
    """
    # **Le cote REFERENCE est mesure par l'INGESTION, pas lu dans la table.**
    # C'est la seconde moitie du couplage, et elle manquait : `du_coeur` valait
    # `set(PAGE_EXTENSIONS)` pendant que `source_acceptable` EST
    # `suffix in PAGE_EXTENSIONS`. Les deux membres de l'egalite derivaient de
    # la meme constante, si bien que le mutant « retirer le .pdf de la table du
    # coeur » SURVIVAIT a ce banc -- le mutant qu'il existe pour attraper.
    # Rendre les candidats independants n'y suffisait pas : ce n'est pas
    # l'echantillon qui derivait de l'objet mesure, c'est le PREDICAT.
    #
    # On demande donc au coeur ce qu'il INGERE reellement, fichier par fichier.
    du_coeur = {extension for extension in CANDIDATS
                if _le_coeur_ingere(extension)}
    de_l_ecran = {
        extension for extension in CANDIDATS
        if atelier_scan.source_acceptable(Path(f"planche{extension}"))
    }
    assert de_l_ecran == du_coeur
    # Volet symetrique : la mesure n'est pas vide des deux cotes. Une egalite
    # entre deux ensembles vides serait verte et ne mesurerait rien.
    assert du_coeur, "le coeur n'ingere plus AUCUN des candidats"


@pytest.mark.parametrize("forme", ["dossier", "selection", "seul"])
def test_les_TROIS_formes_de_designation_acceptent_les_MEMES_formats(
    forme: str, tmp_path: Path
) -> None:
    """Le format ne doit pas dependre du GESTE, et c'est ce qui a mordu.

    Le meme `ma-planche.pdf` passait au curseur et etait refuse a l'`Espace`.
    Aucune des deux voies n'etait fautive prise seule : c'est leur ECART qui
    l'etait, et aucun banc ne regardait les deux ensemble.

    La fabrique porte **trois** fichiers et la cible est au MILIEU de l'ordre
    que le code parcourt -- `_discover_folder_pages` et `_ordonner_une_selection`
    trient par nom normalise, et `b_cible.pdf` y est second sur trois. Une
    fabrique a deux elements placerait la cible en derniere position, ou une
    faute de terminaison de boucle est indiscernable d'une faute d'appariement.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdfcanvas
    import cv2
    import numpy as np

    dossier = tmp_path / "planches"
    dossier.mkdir()
    for nom, valeur in (("a_avant.png", 10), ("c_apres.tif", 200)):
        assert cv2.imwrite(str(dossier / nom),
                           np.full((40, 60, 3), valeur, dtype=np.uint8))
    canevas = pdfcanvas.Canvas(str(dossier / "b_cible.pdf"), pagesize=A4)
    for _ in range(3):
        canevas.showPage()
    canevas.save()

    designations = {
        "dossier": dossier,
        "selection": sorted(dossier.iterdir()),
        "seul": dossier / "b_cible.pdf",
    }
    # Aucune des trois ne leve : c'est la propriete que le defaut violait.
    mesure = scan_ingest.mesurer_la_source(designations[forme])
    assert mesure.cardinal > 0


# --- moitie 2 : les CAPACITES ----------------------------------------------


def test_l_ensemble_des_capacites_du_coeur_HORS_D_ATTEINTE_est_EXACTEMENT_connu(
) -> None:
    """« Une capacite que le coeur porte et que la TUI ne peut pas atteindre. »

    C'est la generalisation du defaut PDF au-dela des formats, et elle attrape
    deja plus que lui. Le rouge se lit dans les deux sens :

    * un mot-cle **de plus** dans l'ecart = une capacite neuve du coeur que
      personne n'a cablee, ou un cablage retire ;
    * un mot-cle **de moins** = une dette fermee dont le registre n'a pas suivi.

    Les deux sont des ecarts a signaler, et c'est pourquoi la table est comparee
    par egalite plutot que par inclusion.
    """
    poses = _mots_cles_poses_par_la_tui()
    hors_d_atteinte = {}
    for module, nom in POINTS_D_ENTREE:
        manquants = tuple(sorted(_mots_cles_offerts(getattr(module, nom)) - poses))
        if manquants:
            hors_d_atteinte[nom] = manquants

    attendu = {nom: tuple(sorted(mots))
               for nom, mots in INJOIGNABLES_TOLERES.items()}
    assert hors_d_atteinte == attendu


def test_la_frontiere_regarde_une_surface_NON_VIDE() -> None:
    """Le volet symetrique, sans lequel les deux mesures seraient vertes a vide.

    Une frontiere posee sur un paquet vide, ou sur une liste de points d'entree
    dont aucun n'existe, est verte et ne mesure rien -- c'est le mode de panne
    que les volets symetriques de ce depot cherchent a exclure, et il a deja
    ete paye.
    """
    assert len(list(PAQUET_TUI.rglob("*.py"))) >= 2
    assert len(_mots_cles_poses_par_la_tui()) >= 10
    for module, nom in POINTS_D_ENTREE:
        assert _mots_cles_offerts(getattr(module, nom)), nom
