# -*- coding: utf-8 -*-
"""Story 11.4c, **lot V2** -- le code de sortie du scan dit la verite.

AC 9 et AC 10 de `_bmad-output/implementation-artifacts/11-4c-sorties-nommees-du-coeur.md`.

**Le defaut corrige est etroit, et cette phrase est la moitie du banc.** Rien
ne manquait a la tracabilite : au `baseline_commit`, une source illisible
produisait quatre frames de mire sur huit, annoncait `SYNTHETIC_FRAME_WRITTEN`
a l'ecriture, puis `FRAMES_SYNTHETIQUES_PRESENTES` et `LOT_INCOMPLET` a la
persistance, ecrivait `synthetic_frame_count`, la liste des noms de mires et
`reconstruction.status: "partial"` au manifeste -- et rendait **`0`**. Fait F7
de la fiche, verbatim : « La tracabilite de D3 est COMPLETE, et l'elargir
serait le defaut. [...] La correction porte sur **le code de sortie, pas sur la
tracabilite**. »

Ce que ce banc mesure est donc **le pont**, et lui seul : l'inventaire que la
commande produit deja atteint desormais le code qu'elle rend.

Deux pieges de ce depot, payes ailleurs et non repayes ici :

1. **une assertion positive laisse passer toute divergence supplementaire**
   (`CLAUDE.md`, 2026-08-30). « Ce motif degrade » ne mesure rien ;
   l'assertion est celle de l'ensemble, et elle est jouee sur le
   **vocabulaire entier** des dix-neuf codes que la chaine sait produire, pas
   sur les deux qu'on attend ;
2. **un condensat ne prouve pas qu'un fichier n'a pas ete touche** quand la
   fixture est deterministe : une reecriture rend exactement les memes octets.
   Le « rien n'a ete detruit » de l'AC 10.4 se mesure donc aux **inodes**, au
   **`st_mtime_ns`** et par un **temoin** depose dans le dossier vise.

Et la regle des fabriques, point **2 bis** compris : partout ou une boucle
compte -- le filtre des motifs, l'agregation du vrac, la recherche du lot vise
--, la fixture porte **trois** elements et la cible est **au milieu**. Une
fixture a deux elements ne separe pas « rendre le second » de « rendre le
dernier », et c'est litteralement le mutant `continue` -> `break` qui a survecu
sur la story 11.4b.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for chemin in (REPO_ROOT / "src", Path(__file__).resolve().parent):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

from mixed_media_utility import (  # noqa: E402
    cli,
    extraction,
    scan_output_frames,
    scan_write,
)
from mixed_media_utility.io import (  # noqa: E402
    encode_manifest, project_layout, scan_manifest as sm)
from mixed_media_utility.io.extraction_manifest import (  # noqa: E402
    MANIFEST_FILENAME,
    ExtractionPersistenceError,
)

import test_scan_manifest as fixtures  # noqa: E402
import test_scan_write_command as ecriture  # noqa: E402


LOGGER = logging.getLogger("test_sortie_partielle_du_scan")


# ===========================================================================
# AC 9.1 -- le troisieme code, et il ne collisionne avec rien
# ===========================================================================

#: Les cinq codes que la chaine prenait **avant** cette story, recopies du code
#: d'avant (`extraction.py:150-154`, `scan_write.py:109-110`) et non lus des
#: constantes qu'ils mesurent : lire la constante que l'on mesure ferait un test
#: tautologique, le defaut trouve par la campagne de la story 5.9 sur la
#: constante centrale de la calibration.
CODES_DEJA_PRIS = {0, 1, 2, 3, 130}


def test_le_code_de_succes_partiel_ne_COLLISIONNE_avec_aucun_code_deja_pris():
    """AC 9.1 : « distinct de `CODE_SUCCES = 0` et de `CODE_ERREUR = 1`, et
    distinct des valeurs deja prises cote extraction ».

    Le volet symetrique compte autant que le volet direct : les cinq valeurs
    d'avant sont **encore** celles-la. Un test qui n'affirmerait que la
    non-collision serait vert le jour ou l'un des cinq aurait bouge, et le
    contrat CLI aurait alors change deux fois au lieu d'une.
    """
    assert scan_write.CODE_SUCCES_PARTIEL not in CODES_DEJA_PRIS

    # Les cinq valeurs d'avant, la ou elles vivent, sont inchangees.
    assert {
        extraction.CODE_SUCCES,
        extraction.CODE_ERREUR,
        extraction.CODE_PREREQUIS_ABSENT,
        extraction.CODE_REFUS,
        extraction.CODE_INTERRUPTION,
    } == CODES_DEJA_PRIS
    assert {scan_write.CODE_SUCCES, scan_write.CODE_ERREUR} == {0, 1}

    # Et les six sont bien six valeurs, pas cinq : l'egalite d'ensembles ferme
    # la porte a un alias qui ferait passer le succes partiel pour un refus.
    assert len(CODES_DEJA_PRIS | {scan_write.CODE_SUCCES_PARTIEL}) == 6


# ===========================================================================
# AC 9.2 -- l'ensemble ferme des motifs qui degradent
# ===========================================================================

def test_le_VOCABULAIRE_consulte_est_EXACTEMENT_celui_des_deux_producteurs():
    """L'inventaire consulte est celui que la chaine sait produire, pas un autre.

    Sans ce volet, l'egalite d'ensembles ci-dessous porterait sur un
    vocabulaire arbitraire : elle serait verte sur un ensemble de trois codes
    inventes ici. Les deux moities sont **lues** chez leurs producteurs, jamais
    recopiees, et leur reunion n'a aucun homonyme -- deux vocabulaires voisins
    dont un code porterait le meme nom feraient degrader le mauvais fait.
    """
    assert set(scan_write.VOCABULAIRE_DE_L_INVENTAIRE) == (
        set(scan_output_frames.SCAN_OUTPUT_WARNING_CODES)
        | set(sm.SCAN_PERSISTENCE_CODES))
    assert len(scan_write.VOCABULAIRE_DE_L_INVENTAIRE) == len(
        set(scan_write.VOCABULAIRE_DE_L_INVENTAIRE)), (
        "deux codes homonymes entre les deux vocabulaires : le pont degraderait "
        "sur un fait pour un autre")
    # Onze avertissements d'ecriture (5.6) et huit constats de persistance (5.7).
    assert len(scan_write.VOCABULAIRE_DE_L_INVENTAIRE) == 19


def test_l_ENSEMBLE_des_motifs_qui_degradent_le_code_est_EXACTEMENT_le_declare():
    """AC 9.2, sous la seule forme qui vaille : l'egalite d'**ensembles**.

    `CLAUDE.md`, 2026-08-30, verbatim : « une assertion positive laisse passer
    toute divergence supplementaire. [...] « l'ensemble des chemins qui
    divergent est **exactement** {X} » mesure l'exception ET son unicite. »

    L'ensemble mesure n'est pas la constante relue -- ce serait tautologique --
    mais **ce que le code consulte**, obtenu en jouant le pont sur chacun des
    dix-neuf codes du vocabulaire, un par un. Un motif ajoute a l'ensemble, un
    motif retire, un motif remplace : les trois font rougir cette ligne.
    """
    degradent = {code for code in scan_write.VOCABULAIRE_DE_L_INVENTAIRE
                 if scan_write.code_de_sortie_de_l_ecriture((code,))
                 != scan_write.CODE_SUCCES}

    assert degradent == {"LOT_INCOMPLET", "FRAMES_SYNTHETIQUES_PRESENTES"}, (
        f"motifs qui degradent : {sorted(degradent)}")
    # Et ce que la constante declare coincide avec ce que le code fait : les
    # deux moities du meme fait, mesurees separement.
    assert set(scan_write.MOTIFS_QUI_DEGRADENT_LE_CODE) == degradent


def test_un_inventaire_VIDE_rend_le_succes():
    """Le regime nominal, et il ne doit rien couter : aucun avertissement,
    aucun constat, code `0`. Sans cette ligne, un pont qui degraderait
    **toujours** passerait tous les autres tests de degradation."""
    assert scan_write.code_de_sortie_de_l_ecriture(()) == scan_write.CODE_SUCCES
    assert scan_write.motifs_de_degradation(()) == ()


def test_OUTPUT_FRAME_OVERWRITTEN_ne_degrade_PAS_le_code():
    """AC 9.4, et c'est une AC a elle seule.

    L'operateur qui a tape `--overwrite` a **demande** l'ecrasement : le rendre
    non nul casserait tout appelant legitime, a commencer par la seconde passe
    complementaire d'un lot. Le scenario `51b_write_lot_deja_PDF` du dossier
    d'identite mesure la meme chose de bout en bout, sur la vraie CLI ; ici on
    mesure que le code de ce motif est bel et bien **consulte** et bel et bien
    **ecarte**, ce qu'un dossier de scenarios ne distingue pas d'un oubli.
    """
    inventaire = ("OUTPUT_FRAME_OVERWRITTEN",)
    assert "OUTPUT_FRAME_OVERWRITTEN" in scan_write.VOCABULAIRE_DE_L_INVENTAIRE
    assert scan_write.motifs_de_degradation(inventaire) == ()
    assert scan_write.code_de_sortie_de_l_ecriture(inventaire) \
        == scan_write.CODE_SUCCES


#: **Cinq codes, les deux qui degradent ni en premier ni en dernier** (regle des
#: fabriques, points 2 et 2 bis). Un filtre qui rendrait le premier element, le
#: dernier, ou qui s'arreterait au premier motif trouve (`continue` -> `break`)
#: passe une fixture a deux elements ; il ne passe pas celle-ci.
INVENTAIRE_MELE = (
    "PAGE_QR_UNREADABLE",              # avertissement d'ecriture, ne degrade pas
    "FRAMES_SYNTHETIQUES_PRESENTES",   # degrade -- deuxieme position
    "OUTPUT_FRAME_OVERWRITTEN",        # ne degrade pas, ENTRE les deux motifs
    "LOT_INCOMPLET",                   # degrade -- avant-derniere position
    "AUTRES_LOTS_NON_SCANNES",         # ne degrade pas, en dernier
)


def test_les_motifs_sont_rendus_DANS_L_ORDRE_annonce_et_sans_les_autres():
    """Le filtre, sur un inventaire mele -- la fabrique du point 2 bis.

    Trois proprietes en une : les deux motifs sont **tous deux** rendus (un
    arret au premier en rendrait un seul), ils sont rendus **dans l'ordre ou la
    commande les annonce** (c'est cet ordre que la phrase imprime), et rien
    d'autre ne l'est (les trois codes qui n'ont rien a y faire encadrent les
    deux qui y sont).
    """
    assert scan_write.motifs_de_degradation(INVENTAIRE_MELE) == (
        "FRAMES_SYNTHETIQUES_PRESENTES", "LOT_INCOMPLET")
    assert scan_write.code_de_sortie_de_l_ecriture(INVENTAIRE_MELE) \
        == scan_write.CODE_SUCCES_PARTIEL

    # Chacun des deux motifs degrade **seul**: sans cette paire de lignes, un
    # ensemble reduit a un seul des deux resterait vert sur la fixture melee.
    for motif in ("FRAMES_SYNTHETIQUES_PRESENTES", "LOT_INCOMPLET"):
        assert scan_write.code_de_sortie_de_l_ecriture((motif,)) \
            == scan_write.CODE_SUCCES_PARTIEL, motif


class _RapportDeSortie:
    def __init__(self, warnings):
        self.warnings = tuple(warnings)


class _Persistance:
    def __init__(self, findings):
        self.findings = tuple(findings)


def _ecriture(warnings=(), findings=()):
    return scan_write.EcritureDuLot(
        persisted=_Persistance(findings),
        output=_RapportDeSortie(warnings),
        lot_correction=None,
        correction_appliquee=True,
        profil_de_chaine_utilise=False,
    )


def test_l_inventaire_RELAIE_les_deux_moities_dans_l_ordre_ou_elles_sortent():
    """L'inventaire est la **reunion** des deux rapports, pas l'un des deux.

    Les avertissements d'ecriture sortent en premier au journal, les constats
    de persistance ensuite : l'ordre est celui-la, et il compte parce que c'est
    lui que la phrase degradee reprend. Une fabrique a **deux** entrees de
    chaque cote, distinguables : une moitie ignoree ne se voit pas autrement,
    et un inventaire qui ne rendrait qu'un element par rapport non plus.
    """
    ecriture_du_lot = _ecriture(
        warnings=("PAGE_QR_UNREADABLE", "SYNTHETIC_FRAME_WRITTEN"),
        findings=("FRAMES_SYNTHETIQUES_PRESENTES", "LOT_INCOMPLET"),
    )
    assert scan_write.inventaire_de_l_ecriture(ecriture_du_lot) == (
        "PAGE_QR_UNREADABLE", "SYNTHETIC_FRAME_WRITTEN",
        "FRAMES_SYNTHETIQUES_PRESENTES", "LOT_INCOMPLET")
    assert scan_write.code_de_sortie_de_l_ecriture(
        scan_write.inventaire_de_l_ecriture(ecriture_du_lot)) \
        == scan_write.CODE_SUCCES_PARTIEL

    # Et une passe nominale -- aucun avertissement, aucun constat -- reste a
    # zero de bout en bout.
    assert scan_write.inventaire_de_l_ecriture(_ecriture()) == ()


# ===========================================================================
# L'agregation du vrac : plusieurs lots, un seul code
# ===========================================================================

#: **Trois lots, le lot degrade AU MILIEU** (regle des fabriques, 2 bis). Une
#: agregation qui rendrait le premier code, le dernier, ou qui s'arreterait au
#: premier succes ne se demasque pas sur deux elements.
def test_le_vrac_rend_le_succes_PARTIEL_quand_un_seul_lot_est_degrade():
    partiel = scan_write.CODE_SUCCES_PARTIEL
    assert cli._code_agrege_du_vrac((0, partiel, 0)) == partiel
    assert cli._code_agrege_du_vrac((0, 0, 0)) == 0


def test_le_vrac_rend_le_REFUS_des_qu_un_lot_est_refuse_meme_au_milieu():
    """Un refus l'emporte sur un succes partiel : « rien n'est ecrit » est plus
    grave que « ecrit, mais pas ce qui etait promis », et le comportement
    d'avant -- `1` des qu'un code n'est pas `0` -- est preserve pour tout code
    que la table pourrait rendre demain."""
    partiel = scan_write.CODE_SUCCES_PARTIEL
    assert cli._code_agrege_du_vrac((0, 1, partiel)) == 1
    assert cli._code_agrege_du_vrac((partiel, 1, 0)) == 1
    # Un code inattendu tombe du cote du refus, comme avant cette story.
    assert cli._code_agrege_du_vrac((0, 130, 0)) == 1
    # Et une passe sans aucun lot rend le succes, comme avant.
    assert cli._code_agrege_du_vrac(()) == 0


# ===========================================================================
# AC 9.5 et 9.6 -- la commande reelle
# ===========================================================================

def _lot_a_mires(tmp_path: Path, nom: str):
    """Un lot de deux planches dont la seconde a un marqueur de coin efface.

    La planche perdue est la **seconde** et non la premiere : une passe qui
    n'aurait vu que la premiere feuille rendrait le meme verdict sur les deux
    ordres, et le banc ne mesurerait plus quelle planche a produit les mires.
    """
    payloads = fixtures.cli_pages()
    return fixtures.write_cli_folder(
        tmp_path / nom, payloads, broken=(1,)), payloads


def test_un_lot_a_MIRES_rend_le_code_degrade_ET_la_phrase_ne_dit_plus_succes(
        tmp_path, capsys):
    """AC 9.1, 9.3 et 9.5 par la commande reelle, sur de vraies frames.

    C'est le defaut d'origine, dans son regime exact : la moitie du lot est
    une mire, tout est annonce, et le code disait `0`. Les trois moities du
    changement sont mesurees ensemble -- le code, le verbe, et le fait que la
    **mesure** imprimee n'a pas bouge.
    """
    folder, _ = _lot_a_mires(tmp_path, "lot-a")
    project_dir = tmp_path / "projet"
    capsys.readouterr()

    code = fixtures.run_scan(project_dir, folder)

    assert code == scan_write.CODE_SUCCES_PARTIEL
    assert code not in (scan_write.CODE_SUCCES, scan_write.CODE_ERREUR)

    sortie = capsys.readouterr().out
    ligne, = [l for l in sortie.splitlines() if l.startswith("scan termine")]
    assert "succes" not in ligne, ligne
    # La phrase **nomme** les deux motifs : lire le code retour et lire la
    # phrase doivent apprendre la meme chose.
    for motif in ("FRAMES_SYNTHETIQUES_PRESENTES", "LOT_INCOMPLET"):
        assert motif in ligne, ligne
    # Et elle dit toujours la meme mesure qu'avant : les deux cardinaux et le
    # verdict de completude, au meme endroit.
    assert "incomplet" in ligne and "de remplacement" in ligne

    # Le lot est bel et bien ECRIT -- ce n'est pas un refus (AC 9.1).
    lot = fixtures.lot_of(json.loads(
        (project_dir / MANIFEST_FILENAME).read_text(encoding="utf-8")))
    assert lot["synthetic_frame_count"] == 2
    assert list((project_dir / project_layout.SCAN_FRAMES_DIRNAME).rglob("*.tiff"))


def test_un_lot_COMPLET_garde_son_ZERO_et_son_mot_succes(tmp_path, capsys):
    """Le volet symetrique, et sans lui le banc ci-dessus ne mesure rien.

    Un pont qui degraderait **toute** passe serait vert sur le test precedent.
    Le meme montage, les memes planches, aucune de cassee : code `0`, mot
    « succes », aucun motif nomme.
    """
    folder = fixtures.write_cli_folder(tmp_path / "lot-sain", fixtures.cli_pages())
    project_dir = tmp_path / "projet"
    capsys.readouterr()

    assert fixtures.run_scan(project_dir, folder) == scan_write.CODE_SUCCES

    ligne, = [l for l in capsys.readouterr().out.splitlines()
              if l.startswith("scan termine")]
    assert "scan termine avec succes." in ligne, ligne
    assert "LOT_INCOMPLET" not in ligne


def test_scan_et_scan_write_rendent_LE_MEME_code_sur_LE_MEME_etat_de_lot(
        tmp_path):
    """AC 9.6 : les deux commandes, le meme lot, le meme code.

    Elles partagent une seule redaction du verdict (`_ecrire_le_lot_detecte`),
    et c'est ce que ce test protege : deux redactions divergeraient, et l'ecart
    ne se verrait que sur le code retour d'un script.

    Le meme dossier de planches est ecrit **deux fois**, dans deux projets
    distincts : l'un par `mmu scan` d'un bloc, l'autre par `mmu scan detect`
    puis `mmu scan-write`. Le volet symetrique est en bande -- le code obtenu
    n'est ni `0` ni `1`, sans quoi les deux commandes pourraient coincider en
    ne mesurant rien.
    """
    payloads = fixtures.cli_pages()
    folder_scan = fixtures.write_cli_folder(tmp_path / "a", payloads, broken=(1,))
    folder_write = fixtures.write_cli_folder(tmp_path / "b", payloads, broken=(1,))

    projet_scan = tmp_path / "projet-scan"
    projet_write = tmp_path / "projet-write"

    code_scan = fixtures.run_scan(projet_scan, folder_scan)
    document = ecriture._detect_puis_document(projet_write, folder_write, "b")
    code_write = ecriture.run_write(projet_write, document)

    assert code_scan == code_write
    assert code_scan == scan_write.CODE_SUCCES_PARTIEL
    assert code_scan not in (scan_write.CODE_SUCCES, scan_write.CODE_ERREUR)


# ===========================================================================
# AC 10 -- le conflit de contenu, et le pare-arbitrage qui le borne
# ===========================================================================

#: **Trois lots, la cible AU MILIEU, et un lot d'un autre rush** (AC 10.3,
#: regle des fabriques). Un `find` qui rendrait le premier lot -- le mutant
#: `M25` de la story 5.7, dont la consequence reelle etait d'ecrire les
#: cardinaux sur le mauvais lot -- passe une fixture dont la cible est premiere ;
#: une terminaison de boucle fautive passe une fixture dont la cible est
#: derniere. Celle-ci ne laisse passer ni l'un ni l'autre.
LOT_AVANT = "rush-avant_5"
LOT_VISE = "rush-vise_5"
LOT_APRES = "rush-apres_5"

#: **Deux masters, apparies par `path`** (AC 10.3). Un seul ne mesurerait pas
#: que le message les nomme tous ; et `profile_id` ne peut pas etre la cle, la
#: story 6.1 produisant deux masters pour le meme profil.
MASTERS = (
    {"path": "outputs/rush-vise_5_mmu_prores_hq_3307x1860.mov",
     "profile_id": "prores_hq", "frame_count": 8, "incomplete": False},
    {"path": "outputs/rush-vise_5_mmu_prores_hq.mov",
     "profile_id": "prores_hq", "frame_count": 8, "incomplete": False},
)


def _manifeste_a_trois_lots(project_dir: Path, *, etat_du_lot_vise: str,
                            masters=()) -> Path:
    """Un `project.json` a trois lots, celui qui est vise au milieu."""
    project_dir.mkdir(parents=True, exist_ok=True)
    lots = [
        {"lot_id": LOT_AVANT, "state": "scan",
         "encoded_masters": [
             {"path": "outputs/rush-avant_5_mmu_prores_hq.mov",
              "profile_id": "prores_hq", "frame_count": 4, "incomplete": False}]},
        {"lot_id": LOT_VISE, "state": etat_du_lot_vise,
         "output_frames_dir":
             f"{project_layout.SCAN_FRAMES_DIRNAME}/{LOT_VISE}"},
        {"lot_id": LOT_APRES, "state": "encode", "encoded_masters": []},
    ]
    if masters:
        lots[1]["encoded_masters"] = [dict(entree) for entree in masters]
    chemin = project_dir / MANIFEST_FILENAME
    chemin.write_text(json.dumps({"schema_version": "2.1", "lots": lots}),
                      encoding="utf-8")
    return chemin


def _payloads_du_lot_vise():
    """Deux payloads du lot vise -- une pile, jamais une page seule."""
    return [{"lot_id": LOT_VISE, "page_index": 0},
            {"lot_id": LOT_VISE, "page_index": 1}]


def test_les_masters_lus_sont_ceux_DU_LOT_VISE_et_non_ceux_d_un_voisin(tmp_path):
    """L'appariement se fait par `lot_id`, jamais par rang (AC 10.3).

    Le lot vise est **au milieu** de trois, et le premier lot du manifeste
    porte lui aussi un master : une lecture qui rendrait le premier lot
    trouverait donc un master, refuserait, et **passerait** un test dont la
    fixture n'aurait qu'un lot. Le troisieme lot est en etat `encode` avec un
    inventaire vide, ce qui ferme le meme piege par l'autre bout.
    """
    projet = tmp_path / "projet"
    _manifeste_a_trois_lots(projet, etat_du_lot_vise="encode", masters=MASTERS)

    lus = scan_write.masters_declares_du_lot(projet, LOT_VISE)

    assert [entree["path"] for entree in lus] == sorted(
        entree["path"] for entree in MASTERS), (
        "les masters rendus ne sont pas ceux du lot vise, ou ne sont pas "
        "tries par leur cle")
    # Les voisins se lisent chacun pour soi, et ne se contaminent pas.
    assert len(scan_write.masters_declares_du_lot(projet, LOT_AVANT)) == 1
    assert scan_write.masters_declares_du_lot(projet, LOT_APRES) == ()
    # Un lot absent du manifeste n'invente rien.
    assert scan_write.masters_declares_du_lot(projet, "rush-inconnu_5") == ()


def test_un_projet_SANS_manifeste_ne_declare_aucun_master(tmp_path):
    """Le premier scan d'un projet vierge passe par ce chemin et ne doit rien
    couter : pas de `project.json`, donc pas de master, donc pas de refus."""
    assert scan_write.masters_declares_du_lot(tmp_path / "vierge", LOT_VISE) == ()


def test_le_refus_de_conflit_NOMME_le_lot_et_TOUS_ses_masters(tmp_path):
    """AC 10.1 : « nomme, **avant d'ecrire**, ce qui sera detruit et quels
    masters le referencent ».

    Un refus qui dirait « conflit » sans nommer laisserait l'operateur chercher
    lui-meme quel fichier l'empeche d'avancer -- c'est `EPIC11-ARB-25`, « le
    message nomme le motif au lieu de dire invalide ». Les **deux** masters
    sont nommes : n'en nommer qu'un ferait retirer un fichier et rejouer la
    passe pour retomber sur le meme refus.
    """
    projet = tmp_path / "projet"
    _manifeste_a_trois_lots(projet, etat_du_lot_vise="encode", masters=MASTERS)

    with pytest.raises(scan_write.ConflitDeContenuDuLot) as refus:
        scan_write.refuser_le_conflit_de_contenu(
            projet, _payloads_du_lot_vise(), overwrite=True, logger=LOGGER)

    message = str(refus.value)
    assert LOT_VISE in message
    for entree in MASTERS:
        assert entree["path"] in message, message
    assert "Aucune ecriture n'a eu lieu" in message
    # Le master d'un **autre** lot n'a rien a faire dans ce message.
    assert "rush-avant_5_mmu_prores_hq.mov" not in message


def test_le_refus_de_conflit_rend_le_CODE_1_par_la_table_des_codes_de_sortie():
    """Un conflit de contenu est un **refus**, pas un succes partiel.

    La distinction est celle de l'AC 9.1 prise a l'envers : rien n'a ete ecrit,
    donc le code est celui du refus. L'exception derive de la hierarchie de
    persistance de scan, donc la table du coeur repond sans qu'aucune entree
    n'ait ete ajoutee -- et le `1` attendu est ecrit en clair, comme le
    `CODE_DU_BASELINE` du dossier d'identite.
    """
    panne = scan_write.ConflitDeContenuDuLot("panne simulee")
    assert isinstance(panne, ExtractionPersistenceError)
    assert scan_write.code_de_sortie(panne) == 1
    assert scan_write.correspondance_de_sortie(panne)[0] \
        is ExtractionPersistenceError


@pytest.mark.parametrize("etat", ["reconstruction", "encode"])
def test_un_lot_en_etat_encode_SANS_master_declare_reste_ECRIVABLE(
        tmp_path, etat):
    """AC 10.2, et c'est la decision a NE PAS defaire.

    `io/reconstruction._resolve_lot_state` (`reconstruction.py:801-819`) porte,
    verbatim :

        « Un refus **n'est pas une erreur**: reconstruire ou rescanner un lot
        deja passe en `reconstruction` ou en `encode` est le scenario nominal
        « projet recree depuis des payloads, puis planches scannees ». La regle
        qui ferme le sujet: cette fonction **n'abaisse jamais** un etat, elle
        conserve celui en place et laisse l'appelant en informer l'operateur.
        Le seul echec dur reste le conflit de contenu, jamais l'ordre des
        etats. »

    Une garde d'etat posee cote scan rendrait donc erreur ce que cette
    docstring declare nominal. Ce test est le pare-arbitrage : il rougit sur
    tout refus fonde sur l'**ordre des etats** au lieu du **conflit de
    contenu**, et il le fait sur les deux etats que la citation nomme.
    """
    projet = tmp_path / "projet"
    _manifeste_a_trois_lots(projet, etat_du_lot_vise=etat)

    # Aucune exception : le scenario nominal reste ecrivable, `--overwrite`
    # compris.
    scan_write.refuser_le_conflit_de_contenu(
        projet, _payloads_du_lot_vise(), overwrite=True, logger=LOGGER)
    assert scan_write.masters_declares_du_lot(projet, LOT_VISE) == ()


def test_sans_overwrite_la_garde_de_contenu_NE_SE_DECLENCHE_PAS(tmp_path):
    """Un seul refus par fait.

    Sans `--overwrite`, une passe qui retomberait sur des frames existantes est
    **deja** refusee par la garde de reecriture de la story 5.6, et ce refus-la
    nomme le bon geste. Un second refus sur le meme chemin ferait deux messages
    pour une seule situation, et le premier des deux ne serait plus jamais lu.
    """
    projet = tmp_path / "projet"
    _manifeste_a_trois_lots(projet, etat_du_lot_vise="encode", masters=MASTERS)

    scan_write.refuser_le_conflit_de_contenu(
        projet, _payloads_du_lot_vise(), overwrite=False, logger=LOGGER)


def test_une_pile_sans_lot_declare_ne_leve_AUCUNE_KeyError(tmp_path):
    """Story 5.23, AC 10 : **aucun acces indexe nu a un champ de payload**.

    Une page de calibration ne porte ni `lot_id`, ni `rush_id`, ni
    `project_id` : un `payloads[0]["lot_id"]` y mourrait en `KeyError` nue, au
    seul endroit de la chaine ou un refus est encore gratuit et sans rien dire
    a l'operateur. C'est la sixieme occurrence de cette famille en cinq
    corrections, et le balayage AST de `tests/unit/test_pile_mixte_refus.py`
    la ferme au source ; ce test la ferme a l'execution.

    La pile est **mixte a l'envers** : la page sans `lot_id` est **en tete**,
    la ou un acces positionnel la lirait.
    """
    projet = tmp_path / "projet"
    _manifeste_a_trois_lots(projet, etat_du_lot_vise="encode", masters=MASTERS)
    pile = [{"page_index": 0}, {"lot_id": LOT_VISE, "page_index": 1}]

    # Le lot est trouve sur la page qui le declare, et le refus tombe bien.
    with pytest.raises(scan_write.ConflitDeContenuDuLot):
        scan_write.refuser_le_conflit_de_contenu(
            projet, pile, overwrite=True, logger=LOGGER)

    # Et une pile qui n'en declare aucun ne leve rien du tout : elle n'a par
    # definition aucun master a proteger.
    scan_write.refuser_le_conflit_de_contenu(
        projet, [{"page_index": 0}], overwrite=True, logger=LOGGER)


def _empreinte_physique(dossier: Path) -> dict:
    """Inode et `st_mtime_ns` de chaque fichier -- **jamais un condensat**.

    `CLAUDE.md`, 2026-08-30 : « un condensat ne prouve pas qu'un fichier n'a pas
    ete touche quand la fixture est deterministe -- une reecriture rend
    exactement les memes octets. » Les deux fabriques de ce depot le sont : le
    `testsrc` de l'extraction comme les planches synthetiques du scan.
    """
    return {
        chemin.name: (chemin.stat().st_ino, chemin.stat().st_mtime_ns)
        for chemin in sorted(dossier.rglob("*")) if chemin.is_file()
    }


def test_le_refus_de_conflit_ne_TOUCHE_NI_inode_NI_mtime_NI_temoin(
        tmp_path, capsys):
    """AC 10.1 et 10.4, de bout en bout par la commande reelle.

    Le montage est celui du scenario `51b` du dossier d'identite, a un champ
    pres : un lot est scanne, puis le manifeste est edite a la main pour
    declarer que deux masters video ont ete encodes depuis ses frames -- ce que
    `mmu encode` ecrit reellement (`lots[].encoded_masters`, story 6.5). La
    passe suivante demande l'ecrasement, et doit etre **refusee avant d'ecrire**.

    La mesure du « rien n'a ete detruit » porte sur **trois** signaux, et aucun
    n'est un condensat : les inodes, les `st_mtime_ns`, et un **temoin** -- un
    fichier de nom non conforme depose dans le dossier de lot, qu'une passe
    d'ecriture reelle signalerait ou balaierait.
    """
    payloads = fixtures.cli_pages()
    folder = fixtures.write_cli_folder(tmp_path / "lot-a", payloads)
    projet = tmp_path / "projet"
    assert fixtures.run_scan(projet, folder) == scan_write.CODE_SUCCES

    chemin_du_manifeste = projet / MANIFEST_FILENAME
    document = json.loads(chemin_du_manifeste.read_text(encoding="utf-8"))
    lot = fixtures.lot_of(document)
    lot[encode_manifest.MASTER_INVENTORY_FIELD] = [
        {"path": f"outputs/{lot['lot_id']}_mmu_prores_hq.mov",
         "profile_id": "prores_hq", "frame_count": 4, "incomplete": False},
        {"path": f"outputs/{lot['lot_id']}_mmu_prores_hq_3307x1860.mov",
         "profile_id": "prores_hq", "frame_count": 4, "incomplete": False},
    ]
    chemin_du_manifeste.write_text(json.dumps(document), encoding="utf-8")
    octets_du_manifeste = chemin_du_manifeste.read_bytes()

    # Le dossier de lot se **lit** sur le disque et ne se recompose pas depuis
    # le `lot_id` : le slug de dossier a sa propre derivation
    # (`scan_output_frames.derive_lot_dir_slug`), et une seconde redaction ici
    # designerait un dossier voisin le jour ou elle divergerait.
    dossier_du_lot = next(
        d for d in (projet / project_layout.SCAN_FRAMES_DIRNAME).iterdir() if d.is_dir())
    temoin = dossier_du_lot / "temoin-de-non-ecriture.txt"
    temoin.write_text("depose avant le refus", encoding="utf-8")
    avant = _empreinte_physique(dossier_du_lot)
    assert len(avant) >= 5, avant  # les frames du lot, plus le temoin
    capsys.readouterr()

    code = fixtures.run_scan(projet, folder, "--overwrite")

    assert code == scan_write.CODE_ERREUR
    sortie = capsys.readouterr()
    assert "Conflit de contenu" in sortie.err, sortie.err
    for suffixe in ("_mmu_prores_hq.mov", "_mmu_prores_hq_3307x1860.mov"):
        assert suffixe in sortie.err, sortie.err

    # Les trois signaux, et l'assertion porte sur l'**ensemble** : un fichier
    # en plus ou en moins la fait rougir autant qu'une mtime bougee.
    assert _empreinte_physique(dossier_du_lot) == avant
    assert temoin.is_file()
    assert temoin.read_text(encoding="utf-8") == "depose avant le refus"
    assert chemin_du_manifeste.read_bytes() == octets_du_manifeste


def test_le_MEME_lot_SANS_master_declare_se_reecrit_comme_avant(
        tmp_path, capsys):
    """Le volet symetrique du precedent, et il est indispensable.

    Un refus qui tomberait sur **toute** passe `--overwrite` passerait le test
    ci-dessus. Le meme montage, aux masters pres : le lot est laisse en etat
    `encode` -- l'etat que la docstring de `_resolve_lot_state` declare nominal
    -- sans inventaire de master, et la reecriture aboutit.
    """
    payloads = fixtures.cli_pages()
    folder = fixtures.write_cli_folder(tmp_path / "lot-a", payloads)
    projet = tmp_path / "projet"
    assert fixtures.run_scan(projet, folder) == scan_write.CODE_SUCCES

    chemin_du_manifeste = projet / MANIFEST_FILENAME
    document = json.loads(chemin_du_manifeste.read_text(encoding="utf-8"))
    fixtures.lot_of(document)["state"] = "encode"
    chemin_du_manifeste.write_text(json.dumps(document), encoding="utf-8")
    capsys.readouterr()

    assert fixtures.run_scan(projet, folder, "--overwrite") \
        == scan_write.CODE_SUCCES
    assert "Conflit de contenu" not in capsys.readouterr().err
