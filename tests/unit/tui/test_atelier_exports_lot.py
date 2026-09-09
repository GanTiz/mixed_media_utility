# -*- coding: utf-8 -*-
"""Story 11.8, lot C -- `E4-1`, la designation d'un lot a encoder (AC 5).

Ce banc mesure les six points de l'AC 5, plus les deux etats que
`EPIC11-ARB-186` impose a cet ecran et que la fiche ne dit pas : **pendant le
balayage du disque, et apres**. Le second est ce qui compte le plus -- « aucun
verdict n'est affiche avant d'avoir ete compte », un verdict optimiste affiche
puis corrige etant un mensonge d'interface, meme bref.

**La regle des fabriques s'applique partout ici** (`CLAUDE.md`, points 1, 2 et
3, et l'AC 5.6 l'exige nommement) : les corpus portent **trois** lots au moins,
aux trois etats de completude, aux cardinaux **tous differents**, et la cible
est **au milieu** -- ni en premier, ce qui laisserait vivre un `find` qui rend
toujours le premier element, ni en dernier, ce qui laisserait vivre un
`continue` -> `break` qui arrete la passe au premier ecart. C'est le mutant qui
a survecu a la story 11.4b. La position se verifie sur la liste que le CODE
parcourt, et :func:`test_AC5_6_la_fabrique_tient_ce_que_l_AC_exige` la mesure
plutot que de la promettre.

**Deux frontieres negatives, et elles ne mesurent pas la meme chose que les
frontieres du paquet** (`test_frontiere_vocabulaire_du_coeur.py`) : celles-ci
portent sur le **rendu**, pas sur le source. Un ecran peut n'ecrire aucun
litteral interdit et afficher quand meme un mot faux, parce qu'il l'assemble --
c'est le cas du `lue au QR` de l'AC 5.4, que la maquette d'origine portait et
que la mesure a renverse.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from outils_frontiere import chaines_de_code

from mixed_media_utility import encode
from mixed_media_utility.io import manifest as io_manifest
from mixed_media_utility.io import naming
from mixed_media_utility.tui import atelier_exports_lot as lots_exports
from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

RACINE = Path(__file__).resolve().parents[3]
MODULE = (RACINE / "src" / "mixed_media_utility" / "tui"
          / "atelier_exports_lot.py")
MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")
MAQUETTE = "E4-1-exports-lot.txt"

#: Le rush de la demonstration, et la geometrie que son manifest declare.
RUSH = "plan-04"
LARGEUR, HAUTEUR = 1920, 1080
PROFONDEUR = 16
#: La cadence source du lot, dans l'ecriture exacte du coeur.
CADENCE_EXACTE = "25/1"


# ---------------------------------------------------------------------------
# Fabriques -- trois lots au moins, tous distinguables, la cible AU MILIEU
# ---------------------------------------------------------------------------

def lignes_de_maquette() -> list[str]:
    """Les lignes utiles de `E4-1`, cadre et marges retires."""
    lignes = (MAQUETTES / MAQUETTE).read_text(encoding="utf-8").splitlines()
    return [ligne[2:-2] for ligne in lignes if ligne.startswith("│")]


def document_de_lot(lot_id: str, *, etat: str | None = None,
                    frames: int = 124, dossier: str | None = "",
                    cadence: str | None = CADENCE_EXACTE,
                    passes: list[dict] | None = None,
                    profondeur: int | None = PROFONDEUR) -> dict:
    """Un document de lot du manifest, tel que le coeur le lit.

    ``etat`` vaut par defaut le **minimum admis**, lu du coeur
    (`encode.MINIMUM_LOT_STATE`) et jamais recopie : c'est exactement l'etat
    dont la table retiree de la TUI faisait un lot non encodable, alors que
    `mmu encode` l'encode.
    """
    document: dict = {
        "lot_id": lot_id,
        "rush_id": RUSH,
        "state": encode.MINIMUM_LOT_STATE if etat is None else etat,
        "fps_target": 25,
        "expected_frame_count": frames,
    }
    if cadence is not None:
        document["timecode_base_fps"] = cadence
    if dossier is not None:
        document["output_frames_dir"] = dossier or f"output-frames/{lot_id}"
    if profondeur is not None:
        document["output_bit_depth"] = profondeur
    if passes is not None:
        document[encode.RECONSTRUCTIONS_FIELD] = passes
    return document


def manifeste(*lots: dict, avec_rush: bool = True) -> dict:
    document: dict = {"lots": list(lots)}
    if avec_rush:
        document["rushes"] = [{
            "rush_id": RUSH,
            "resolution_source": {"width": LARGEUR, "height": HAUTEUR},
        }]
    return document


def verdict(*, attendues: int | None, trouvees: int,
            mires: tuple[str, ...] = ()) -> encode.CompletenessVerdict:
    """Un verdict du coeur, construit par son constructeur et non simule."""
    return encode.CompletenessVerdict(
        expected=attendues, found=trouvees, synthetic_present=mires,
        synthetic_missing=(), missing_pages=(),
        complete=attendues is not None and attendues == trouvees)


#: Les trois lots de la fabrique, **tous differents** : trois noms, trois
#: cardinaux, trois verdicts. La cible -- celle que les tests designent -- est
#: `plan-04_12p5`, **au milieu**.
CIBLE = "plan-04_12p5"
TROIS_LOTS = (
    ("plan-04_25", 124, verdict(attendues=124, trouvees=124)),
    (CIBLE, 63, verdict(attendues=63, trouvees=60, mires=("a.tiff", "b.tiff",
                                                          "c.tiff"))),
    ("plan-04_8", 40, verdict(attendues=40, trouvees=31)),
)


def trois_lots(*, comptes: bool = True,
               passes: dict[str, list[dict]] | None = None
               ) -> lots_exports.ListeDesLotsAEncoder:
    """La fabrique du banc : trois lots, trois etats, la cible au milieu.

    ``comptes=False`` rend l'ecran **avant** tout balayage -- l'etat que
    `EPIC11-ARB-186` rend visible par le rotor, et celui ou aucune pastille ne
    doit exister.
    """
    passes = passes or {}
    documents = [document_de_lot(nom, frames=cardinal,
                                 passes=passes.get(nom))
                 for nom, cardinal, _ in TROIS_LOTS]
    liste = lots_exports.ListeDesLotsAEncoder(
        lots=[lots_exports.LotAListe(
            lot=document, dossier=Path("/projet") / f"output-frames/{document['lot_id']}",
            passes=tuple(encode.ReconstructionDeLot(
                rang=entree.get("rang"),
                output_frames_dir=entree["output_frames_dir"],
                ingest_slug=entree["ingest_slug"],
                presente=entree.get("presente", True))
                for entree in passes.get(document["lot_id"], ())))
            for document in documents],
        manifeste=manifeste(*documents),
        project_dir=Path("/projet"))
    if comptes:
        for lot, (_nom, _cardinal, resultat) in zip(liste.lots, TROIS_LOTS):
            liste.balayages[(lot.lot_id, lot.reconstruction_visee)] = \
                lots_exports.Balayage(verdict=resultat)
    return liste


def passe(rang: int | None, *, slug: str, dossier: str | None = None,
          presente: bool = True) -> dict:
    """Une entree d'historique de scan, telle que le manifest la porte."""
    return {"rang": rang, "ingest_slug": slug, "presente": presente,
            "output_frames_dir": (dossier if dossier is not None
                                  else f"output-frames/{CIBLE}"
                                  + ("" if rang in (None, 1)
                                     else naming.format_version_suffix(rang)))}


def projet_sur_disque(tmp_path: Path, lots: list[dict]) -> Path:
    """Un vrai projet : les dossiers declares existent, les autres non.

    Le banc de l'AC 5.1 ne peut pas se passer du disque : deux des trois volets
    du critere du coeur portent sur la **matiere** (un dossier declare, et
    present), et les mesurer sur un document seul mesurerait l'etat, c'est-a-dire
    exactement la table que cette story a retiree.
    """
    for lot in lots:
        dossier = lot.get("output_frames_dir")
        if dossier and not lot.get("_absent_du_disque"):
            (tmp_path / dossier).mkdir(parents=True, exist_ok=True)
        lot.pop("_absent_du_disque", None)
    return tmp_path


# ---------------------------------------------------------------------------
# AC 5.1 -- l'ecran liste ce que le coeur rend, et RIEN D'AUTRE
# ---------------------------------------------------------------------------

def _corpus_de_cinq_lots() -> list[dict]:
    """Cinq lots, deux encodables seulement, et **la cible au milieu**.

    Les trois refuses le sont pour **trois causes differentes** : un etat trop
    tot, un `output_frames_dir` absent du document, un dossier absent du
    disque. Un corpus a une seule cause de refus laisserait vivre une garde qui
    n'en verifierait qu'une.
    """
    trop_tot = document_de_lot("plan-04_8", etat=io_manifest.LOT_STATES[0],
                               frames=40)
    recree = document_de_lot("hiver_24", frames=31, dossier=None)
    disparu = document_de_lot("plan-04_50", frames=12)
    disparu["_absent_du_disque"] = True
    return [trop_tot,
            document_de_lot("plan-04_25", frames=124),
            recree,
            document_de_lot(CIBLE, frames=63),
            disparu]


def test_AC5_1_la_liste_est_EXACTEMENT_celle_du_coeur(tmp_path):
    """AC 5.1 : « les lots rendus par l'AC 3, et **rien d'autre** ».

    C'est une **egalite d'ensemble**, pas une appartenance : « ce lot est
    liste » laisserait passer un sixieme lot que l'ecran aurait ajoute, et
    laisserait passer un ecran qui listerait tout le manifest. Les deux
    ensembles sont confrontes dans les deux sens, et le second est ecrit **en
    dur** -- confronter l'ecran a la seule fonction du coeur mesurerait qu'ils
    sont d'accord, pas qu'ils ont raison.
    """
    lots = _corpus_de_cinq_lots()
    racine = projet_sur_disque(tmp_path, lots)
    document = manifeste(*lots)

    liste = lots_exports.ListeDesLotsAEncoder.depuis_le_coeur(document, racine)

    du_coeur = {str(admis.lot["lot_id"])
                for admis in encode.list_encodable_lots(document, racine)}
    a_l_ecran = {lot.lot_id for lot in liste.lots}
    assert a_l_ecran == du_coeur
    assert a_l_ecran == {"plan-04_25", CIBLE}


def test_AC5_1_un_lot_a_l_etat_MINIMUM_portant_ses_frames_est_LISTE(tmp_path):
    """Le volet « trop strict » du defaut mesure, et il n'est pas theorique.

    `projects/projet_demo` n'a qu'un lot, et il est a cet etat-la. La table
    retiree fermait l'entree `Exports` dessus alors qu'`mmu encode` passe sur
    le meme projet.
    """
    lot = document_de_lot("plan-04_25", etat=encode.MINIMUM_LOT_STATE)
    racine = projet_sur_disque(tmp_path, [lot])
    liste = lots_exports.ListeDesLotsAEncoder.depuis_le_coeur(
        manifeste(lot), racine)
    assert [entree.lot_id for entree in liste.lots] == ["plan-04_25"]


def test_AC5_1_un_lot_recree_depuis_des_payloads_n_est_PAS_liste(tmp_path):
    """Le volet « trop laxiste » : un etat superieur, et pas une frame.

    C'est le motif d'existence de la garde d'admission, cite verbatim par sa
    docstring. L'etat vise est lu du coeur (`io.reconstruction`), jamais
    recopie.
    """
    from mixed_media_utility.io import reconstruction

    recree = document_de_lot("hiver_24", etat=reconstruction.DEFAULT_LOT_STATE,
                             dossier=None)
    admis = document_de_lot("plan-04_25")
    racine = projet_sur_disque(tmp_path, [recree, admis])
    liste = lots_exports.ListeDesLotsAEncoder.depuis_le_coeur(
        manifeste(recree, admis), racine)
    assert [entree.lot_id for entree in liste.lots] == ["plan-04_25"]


def test_AC5_1_l_ordre_est_celui_du_MANIFEST_et_jamais_un_tri(tmp_path):
    """`lots[]` porte l'ordre de premiere creation. Le retrier ferait dire a
    l'ecran une anciennete que le document ne porte pas."""
    ordre = ["zoulou_25", "alpha_25", "mike_25"]
    lots = [document_de_lot(nom) for nom in ordre]
    racine = projet_sur_disque(tmp_path, lots)
    liste = lots_exports.ListeDesLotsAEncoder.depuis_le_coeur(
        manifeste(*lots), racine)
    assert [entree.lot_id for entree in liste.lots] == ordre
    assert [entree.lot_id for entree in liste.lots] != sorted(ordre)


def test_AC5_1_une_liste_VIDE_refuse_plutot_que_de_rendre_un_ecran_sans_objet():
    with pytest.raises(lots_exports.LotsMalFormes):
        lots_exports.ListeDesLotsAEncoder(lots=[])


def test_AC5_1_deux_lots_du_meme_identifiant_REFUSENT():
    """Deux lignes du meme lot feraient compter deux fois le meme balayage."""
    document = document_de_lot("plan-04_25")
    with pytest.raises(lots_exports.LotsMalFormes):
        lots_exports.ListeDesLotsAEncoder(lots=[
            lots_exports.LotAListe(lot=document, dossier=Path("a")),
            lots_exports.LotAListe(lot=dict(document), dossier=Path("b"))])


# ---------------------------------------------------------------------------
# AC 5.2 -- le jeton d'etat vient de `CompletenessVerdict`
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cas,etat,mention", [
    (verdict(attendues=124, trouvees=124), "complete",
     lots_exports.MENTION_COMPLET),
    (verdict(attendues=124, trouvees=121, mires=("a", "b", "c")), "substitute",
     lots_exports.MENTION_MIRES.format(cardinal=3)),
    (verdict(attendues=124, trouvees=121), "absent",
     lots_exports.MENTION_INCOMPLET),
])
def test_AC5_2_les_trois_jetons_viennent_du_verdict(cas, etat, mention):
    """AC 5.2, mot pour mot, et **le glyphe est lu de la table**.

    L'attendu n'est pas `"● complet"` ecrit a la main : c'est
    `jetons.GLYPHES[etat]` suivi de la mention. Un test qui recopierait le
    dessin cesserait de mesurer le jour ou la table change, sans rougir.
    """
    assert lots_exports.jeton_du_verdict(cas) == (
        f"{jetons.GLYPHES[etat]} {mention}")
    assert lots_exports.etat_du_verdict(cas) == etat


def test_AC5_2_le_cardinal_de_mires_est_celui_des_mires_PRESENTES():
    """`synthetic_present`, jamais `synthetic_missing`.

    Le coeur distingue les deux nommement -- « un nom au registre sans fichier
    est un **trou**, pas une mire » --, et les confondre annoncerait des
    substituts qui n'existent pas. Les deux cardinaux sont differents dans ce
    corpus, sans quoi la mesure serait aveugle.
    """
    cas = encode.CompletenessVerdict(
        expected=124, found=121, synthetic_present=("a", "b", "c"),
        synthetic_missing=("d", "e"), missing_pages=(), complete=False)
    assert lots_exports.jeton_du_verdict(cas).endswith("3 mires")


def test_AC5_2_les_trois_jetons_restent_DISTINCTS_en_ascii():
    """Le second canal de `DESIGN.md` section 6 : deux etats, deux chaines.

    Un repli qui rendrait le meme dessin pour deux verdicts detruirait
    exactement le canal qu'il doit servir.
    """
    rendus = {lots_exports.jeton_du_verdict(cas, ascii_seul=True)
              for _nom, _cardinal, cas in TROIS_LOTS}
    assert len(rendus) == 3


def test_AC5_2_le_module_n_ECRIT_aucun_glyphe_en_dur():
    """Frontiere negative : le dessin vit dans `jetons`, jamais ici.

    Volet symetrique : la table est non vide et les dessins qu'elle porte sont
    bien ceux qu'on cherche -- une frontiere posee sur un ensemble vide serait
    verte pour rien.
    """
    dessins = ((set(jetons.GLYPHES.values()) | set(jetons.ROTOR))
               # `·` est **aussi** le glyphe de l'etat « neutre », et c'est le
               # separateur typographique de toutes les maquettes du depot
               # (`SEPARATEUR = " · "`, ecrit tel quel dans six modules). Il est
               # exclu nommement plutot qu'en silence : la frontiere vise les
               # glyphes qui portent un VERDICT, et une exception tue serait le
               # premier pas vers une liste d'exceptions.
               - {jetons.GLYPHES["neutre"]})
    assert len(dessins) >= 10
    for interdit in (jetons.GLYPHES["complete"], jetons.GLYPHES["substitute"],
                     jetons.GLYPHES["absent"], jetons.ROTOR[0]):
        assert interdit in dessins
    ecrits = [valeur for valeur in chaines_de_code(MODULE)
              if any(dessin in valeur for dessin in dessins)]
    assert ecrits == []


def test_AC5_2_chaque_glyphe_de_l_ecran_a_son_REPLI():
    """Le defaut paye par le signe multiplier le 2026-08-29, et par `▾`.

    Un glyphe hors des deux tables de repli sort en `?` sous `--ascii`, sans
    bruit. On replie donc **tout ce que l'ecran rend**, dans ses deux etats et
    avec ses passes, et on exige qu'il ne reste pas un seul `?`.
    """
    for comptes in (False, True):
        liste = trois_lots(comptes=comptes, passes={CIBLE: [
            passe(1, slug="scan-a"), passe(2, slug="scan-b"),
            passe(3, slug="scan-c", presente=False)]})
        liste.viser(CIBLE)
        liste.focus = lots_exports.FOCUS_VERSIONS
        rendu = (liste.lignes_de_liste() + liste.lignes_de_la_carte()
                 + [liste.ligne_d_etat(), liste.raccourcis()])
        replie = jetons.replier_ascii("\n".join(rendu))
        assert "?" not in replie, replie


# ---------------------------------------------------------------------------
# `EPIC11-ARB-186` -- les DEUX etats de l'ecran, et l'ordre entre eux
# ---------------------------------------------------------------------------

def test_ARB186_aucun_verdict_n_est_affiche_avant_d_avoir_ete_compte():
    """**La mesure qui compte le plus de ce banc.**

    Un verdict optimiste affiche puis corrige est un mensonge d'interface, meme
    bref. Avant le balayage : aucune des trois mentions, aucun etat de ligne
    (donc aucune couleur), et le rotor a leur place.
    """
    liste = trois_lots(comptes=False)
    corps = "\n".join(liste.lignes_de_liste() + liste.lignes_de_la_carte())
    for mention in (lots_exports.MENTION_COMPLET,
                    lots_exports.MENTION_INCOMPLET, "mires"):
        assert mention not in corps, (mention, corps)
    assert liste.etats_des_lignes() == {}
    assert corps.count(lots_exports.MENTION_BALAYAGE) == len(liste.lots)


def test_ARB186_le_glyphe_de_chargement_est_celui_du_PRODUIT():
    """`jetons.rotor`, jamais un caractere en dur, et il **tourne**."""
    liste = trois_lots(comptes=False)
    assert liste.lignes_de_liste()[0].count(jetons.rotor(0)) == 1
    liste.avancer_le_rotor()
    assert liste.lignes_de_liste()[0].count(jetons.rotor(1)) == 1
    assert jetons.rotor(0) != jetons.rotor(1)


def test_ARB186_apres_le_balayage_chaque_ligne_porte_son_verdict():
    """L'autre etat : plus un seul rotor, trois etats poses, trois lignes."""
    liste = trois_lots()
    corps = "\n".join(liste.lignes_de_liste())
    assert lots_exports.MENTION_BALAYAGE not in corps
    assert set(liste.etats_des_lignes().values()) == {"complete", "substitute",
                                                      "absent"}
    assert len(liste.etats_des_lignes()) == len(liste.lots)


def test_ARB186_le_balayage_avance_UN_lot_a_la_fois_dans_l_ordre_de_l_ecran():
    """Un lot par tour, de haut en bas : c'est le seul ordre qui se lise, et
    c'est ce qui rend le rotor honnete -- il tourne pendant qu'un balayage a
    vraiment lieu."""
    liste = trois_lots(comptes=False)
    vus: list[str] = []

    def balayeur(lot, project_dir, document, visee):
        vus.append(str(lot["lot_id"]))
        return lots_exports.Balayage(verdict=verdict(attendues=1, trouvees=1))

    assert liste.balayer_le_prochain(balayeur) is True
    assert liste.comptes == 1
    while liste.balayer_le_prochain(balayeur):
        pass
    assert vus == [nom for nom, _cardinal, _cas in TROIS_LOTS]
    assert liste.balayage_fini is True
    assert liste.balayer_le_prochain(balayeur) is False


def test_ARB186_un_refus_de_balayage_n_est_PAS_un_lot_incomplet():
    """Un dossier disparu n'est pas « incomplet » : il est injoignable.

    Les confondre afficherait `✕ incomplet` sur un lot dont rien ne dit qu'il
    manque une frame. Le code du coeur est **nomme**, et il est lu du coeur.
    """
    liste = trois_lots(comptes=False)
    liste.balayer_le_prochain(
        lambda *_: lots_exports.Balayage(refus=encode.ENCODE_OUTPUT_DIR_ABSENT))
    ligne = liste.lignes_de_liste()[0]
    assert lots_exports.MENTION_REFUS in ligne
    assert lots_exports.MENTION_INCOMPLET not in ligne
    assert liste.balayage(liste.lots[0]).compte is True
    # **Le code entier se lit la ou il tient** : la colonne de la liste en fait
    # vingt et une, `DOSSIER_DE_LOT_ABSENT` en fait vingt et une plus le
    # glyphe. Le nommer a demi serait pire que de le dire court.
    assert encode.ENCODE_OUTPUT_DIR_ABSENT in liste.ligne_des_frames()
    assert encode.ENCODE_OUTPUT_DIR_ABSENT in liste.ligne_d_etat()


def test_ARB186_le_balayage_reel_lit_le_DISQUE_et_pas_le_manifest(tmp_path):
    """Le verdict vient d'un balayage reel (`EPIC11-ARB-186`), pas des
    cardinaux du document.

    La mesure est faite sur un lot dont le manifest annonce **trois** frames et
    dont le dossier n'en porte que **deux** : un verdict lu au manifest dirait
    « complet », le disque dit le contraire. Les deux cardinaux different
    exprès -- egaux, le test serait vert quelle que soit la source.
    """
    lot = document_de_lot("plan-04_25", frames=3)
    racine = projet_sur_disque(tmp_path, [lot])
    dossier = racine / lot["output_frames_dir"]
    for timecode in ("00:00:00:00", "00:00:00:02"):
        (dossier / naming.build_scan_frame_filename(
            RUSH, 25, timecode)).write_bytes(b"x")

    resultat = lots_exports.balayer_le_lot(lot, racine, manifeste(lot))

    assert resultat.refus is None
    assert resultat.verdict.found == 2
    assert resultat.verdict.expected == 3
    assert resultat.verdict.complete is False


def test_ARB186_un_fichier_VIDE_n_est_pas_une_frame(tmp_path):
    """C'est le coeur qui le dit (`plan_sequence(empty_names=...)`), et c'est
    lui qui l'ecarte : la lecture du disque ne fait que lui passer la liste.
    Un artefact d'ecriture interrompue faisait passer un lot troue pour
    complet."""
    lot = document_de_lot("plan-04_25", frames=2)
    racine = projet_sur_disque(tmp_path, [lot])
    dossier = racine / lot["output_frames_dir"]
    (dossier / naming.build_scan_frame_filename(
        RUSH, 25, "00:00:00:00")).write_bytes(b"x")
    (dossier / naming.build_scan_frame_filename(
        RUSH, 25, "00:00:00:02")).write_bytes(b"")

    resultat = lots_exports.balayer_le_lot(lot, racine, manifeste(lot))
    assert resultat.verdict.found == 1


def test_ARB186_un_dossier_disparu_ne_fait_PAS_tomber_l_ecran(tmp_path):
    """Un ecran de liste ne plante pas parce qu'un lot sur cinq est abime."""
    lot = document_de_lot("plan-04_25")
    resultat = lots_exports.balayer_le_lot(lot, tmp_path, manifeste(lot))
    assert resultat.verdict is None
    assert resultat.refus == encode.ENCODE_OUTPUT_DIR_ABSENT


# ---------------------------------------------------------------------------
# AC 5.3 -- la cadence source, et le refus qui s'affiche comme un ETAT
# ---------------------------------------------------------------------------

def test_AC5_3_la_carte_porte_la_cadence_rendue_par_le_coeur():
    """La valeur est confrontee a `encode.resolve_source_rate`, pas a `25`."""
    liste = trois_lots()
    _brute, exacte, _note = encode.resolve_source_rate(liste.courant.lot)
    assert exacte == CADENCE_EXACTE
    ligne = liste.ligne_de_la_cadence()
    assert lots_exports.MOTIF_DE_LA_CADENCE.format(cadence="25") in ligne
    assert lots_exports.LIBELLE_CADENCE in ligne


def test_AC5_3_une_cadence_ABSENTE_est_un_etat_de_la_carte_pas_un_plantage():
    """Le refus `ENCODE_SOURCE_RATE_MISSING` s'affiche, il ne tombe pas.

    Le volet symetrique compte autant : le refus **existe bien** sur ce lot-la,
    sans quoi la mesure serait verte sans rien mesurer.
    """
    document = document_de_lot("plan-04_25", cadence=None)
    with pytest.raises(encode.EncodeDecisionError) as refus:
        encode.resolve_source_rate(document)
    assert refus.value.code == encode.ENCODE_SOURCE_RATE_MISSING

    liste = lots_exports.ListeDesLotsAEncoder(
        lots=[lots_exports.LotAListe(lot=document, dossier=Path("x"))],
        manifeste=manifeste(document))
    ligne = liste.ligne_de_la_cadence()
    assert lots_exports.MENTION_CADENCE_ABSENTE in ligne
    assert lots_exports.MENTION_PROVENANCE_DE_LA_CADENCE not in ligne


def test_AC5_3_une_cadence_INEXPLOITABLE_remonte_au_lieu_d_etre_avalee():
    """Deux etats differents, deux traitements.

    Une cadence presente mais inexploitable n'est pas une cadence absente :
    l'avaler ferait dire « le lot n'en declare aucune » d'un lot qui en declare
    une, fausse.
    """
    document = document_de_lot("plan-04_25", cadence="pas-une-cadence")
    liste = lots_exports.ListeDesLotsAEncoder(
        lots=[lots_exports.LotAListe(lot=document, dossier=Path("x"))],
        manifeste=manifeste(document))
    with pytest.raises(encode.EncodeDecisionError) as refus:
        liste.ligne_de_la_cadence()
    assert refus.value.code != encode.ENCODE_SOURCE_RATE_MISSING


def test_AC5_3_une_cadence_NTSC_ne_s_arrondit_pas():
    """`24000/1001` n'a pas d'ecriture decimale finie : on rend l'exacte.

    L'arrondir ici ferait afficher une valeur que le coeur ne connait pas -- et
    seule la cadence a denominateur 1 se lit en entier, comme la maquette.
    """
    document = document_de_lot("plan-04_ntsc", cadence="24000/1001")
    liste = lots_exports.ListeDesLotsAEncoder(
        lots=[lots_exports.LotAListe(lot=document, dossier=Path("x"))],
        manifeste=manifeste(document))
    assert "24000/1001" in liste.ligne_de_la_cadence()


# ---------------------------------------------------------------------------
# AC 5.4 -- la provenance affichee est EXACTE
# ---------------------------------------------------------------------------

def test_AC5_4_la_provenance_affichee_est_le_MANIFEST():
    """Elle est exacte dans tous les regimes : `resolve_source_rate` lit
    `lots[].timecode_base_fps`, c'est-a-dire le manifest, quelle que soit la
    route par laquelle la valeur y est entree."""
    liste = trois_lots()
    assert (lots_exports.MENTION_PROVENANCE_DE_LA_CADENCE
            in liste.ligne_de_la_cadence())


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_AC5_4_le_mot_QR_n_apparait_NULLE_PART_a_l_ecran(ascii_seul):
    """Frontiere negative, dans les deux regimes, et sur le RENDU.

    Le dessin d'origine disait `lue au QR (payload 2.1)`. C'est faux dans le
    cas courant -- un lot ne d'une extraction porte `timecode_base_fps` ecrit
    par `io/extraction_manifest.py` sans qu'aucun QR n'existe --, et **le
    manifest ne garde aucune trace de la route qui a servi** : aucun champ ne
    distingue la valeur ecrite par l'extraction de celle recopiee d'un payload.
    L'ecran ne peut donc pas dire « lue au QR » sans le deviner.
    """
    liste = trois_lots(passes={CIBLE: [passe(1, slug="scan-a"),
                                       passe(2, slug="scan-b")]})
    liste.viser(CIBLE)
    rendu = "\n".join(liste.lignes_de_liste(ascii_seul=ascii_seul)
                      + liste.lignes_de_la_carte(ascii_seul=ascii_seul)
                      + [liste.ligne_d_etat(ascii_seul)])
    assert "QR" not in rendu, rendu


def test_AC5_4_frontiere_le_module_n_ecrit_aucun_QR_en_litteral():
    """Le volet source de la meme frontiere. Docstrings exclus : la prose qui
    explique pourquoi l'ecran ne dit pas « QR » porte forcement le mot."""
    assert [valeur for valeur in chaines_de_code(MODULE)
            if "QR" in valeur] == []


# ---------------------------------------------------------------------------
# AC 5.5 -- la ligne d'etat porte une MESURE (`EPIC11-ARB-56`)
# ---------------------------------------------------------------------------

#: Ce qu'une ligne d'etat ne porte jamais. Les touches nommees et les glyphes
#: de raccourci sont pris **de la ligne de raccourcis du produit**, jamais
#: recopies : une liste ecrite a la main cesserait de mesurer au premier
#: raccourci ajoute.
def _touches_annoncees() -> set[str]:
    mots = set()
    for ligne in (lots_exports.RACCOURCIS_LOTS,
                  lots_exports.RACCOURCIS_LOTS_SANS_PASSES,
                  lots_exports.RACCOURCIS_RECONSTRUCTIONS):
        mots.update(fragment for fragment in ligne.split()
                    if fragment[0].isupper() or not fragment.isalpha())
    return mots


@pytest.mark.parametrize("comptes", [False, True])
def test_AC5_5_la_ligne_d_etat_ne_porte_AUCUNE_touche(comptes):
    """`EPIC11-ARB-56` : une ligne d'etat qui porte une touche est une
    violation de l'arbitrage, dans les deux etats de l'ecran."""
    liste = trois_lots(comptes=comptes)
    etat = liste.ligne_d_etat()
    touches = _touches_annoncees()
    assert len(touches) >= 5, touches
    assert [mot for mot in touches if mot in etat] == []


def test_AC5_5_la_ligne_d_etat_ne_porte_aucun_MOTIF_DE_CONCEPTION():
    """Le defaut a ne pas reproduire, nomme par la fiche.

    La ligne dessinee `Seuls les lots reconstruits sont listés — un lot extrait
    ne s'encode pas.` porte une mesure dans sa premiere moitie et un motif de
    conception dans la seconde. La seconde est interdite : la ligne d'etat dit
    ce que la machine a compte, elle n'explique pas pourquoi l'ecran est fait
    comme ca.
    """
    liste = trois_lots()
    etat = liste.ligne_d_etat()
    for motif in ("Seuls les lots", "ne s'encode pas", "sont listés",
                  "passez", "d'abord"):
        assert motif not in etat, (motif, etat)


def test_AC5_5_la_ligne_d_etat_est_une_MESURE_dans_les_deux_etats():
    """Pendant : combien de lots comptes sur combien. Apres : le cardinal seul,
    le `sur N` tombant parce qu'il ne mesure plus rien."""
    liste = trois_lots(comptes=False)
    assert liste.ligne_d_etat().startswith("0 lot compté sur 3")
    liste.balayages[(liste.lots[0].lot_id, None)] = lots_exports.Balayage(
        verdict=TROIS_LOTS[0][2])
    assert liste.ligne_d_etat().startswith("1 lot compté sur 3")

    fini = trois_lots()
    assert fini.ligne_d_etat().startswith("3 lots comptés")
    assert "sur 3" not in fini.ligne_d_etat()


def test_AC5_5_la_ligne_d_etat_decrit_le_lot_DESIGNE_et_pas_le_premier():
    """La cible est **au milieu** : un `find` qui rendrait le premier lot, ou
    une boucle qui s'arreterait au premier ecart, rendraient tous deux la
    mauvaise ligne."""
    liste = trois_lots()
    liste.viser(CIBLE)
    etat = liste.ligne_d_etat()
    assert CIBLE in etat
    assert "60 frames sur 63" in etat
    assert TROIS_LOTS[0][0] not in etat


def test_AC5_5_le_cardinal_du_lot_designe_n_apparait_qu_une_fois_COMPTE():
    """Meme regle que les pastilles : pas de chiffre avant la mesure."""
    liste = trois_lots(comptes=False)
    liste.viser(CIBLE)
    etat = liste.ligne_d_etat()
    assert CIBLE in etat
    assert "63" not in etat


# ---------------------------------------------------------------------------
# AC 5.6 -- la fabrique, et ce qu'elle demasque
# ---------------------------------------------------------------------------

def test_AC5_6_la_fabrique_tient_ce_que_l_AC_exige():
    """Anti-vacuite de tout ce banc : trois lots, trois etats, cible au milieu.

    Une fabrique qui deviendrait mono-element, uniforme, ou qui placerait la
    cible en tete rendrait la moitie des tests ci-dessus verts pour rien --
    c'est le mode de panne que `CLAUDE.md` a paye trois fois d'affilee.
    """
    liste = trois_lots()
    assert len(liste.lots) >= 3
    noms = [lot.lot_id for lot in liste.lots]
    assert len(set(noms)) == len(noms)
    cardinaux = [lot.lot["expected_frame_count"] for lot in liste.lots]
    assert len(set(cardinaux)) == len(cardinaux)
    etats = [liste.etat_de_la_ligne(lot) for lot in liste.lots]
    assert set(etats) == {"complete", "substitute", "absent"}
    rang = noms.index(CIBLE)
    assert 0 < rang < len(noms) - 1


def test_AC5_6_designer_rend_le_lot_SOUS_LE_CURSEUR():
    """La cible est au milieu : un `designer` qui rendrait `lots[0]` passerait
    sur une fabrique a deux elements ou la cible est en seconde position."""
    liste = trois_lots()
    liste.viser(CIBLE)
    designation = liste.designer()
    assert designation.lot_id == CIBLE
    assert designation.balayage.verdict is TROIS_LOTS[1][2]


# ---------------------------------------------------------------------------
# `EPIC11-ARB-190` / story 6.8 -- designer une RECONSTRUCTION
# ---------------------------------------------------------------------------

def test_les_passes_sont_rendues_dans_l_ORDRE_DU_MANIFEST():
    """`encode.enumerer_les_reconstructions` ne trie jamais, et cet ecran non
    plus : l'historique est chronologique et porte « quelle passe a suivi
    laquelle », que le tri detruirait."""
    liste = trois_lots(passes={CIBLE: [passe(1, slug="scan-a"),
                                       passe(2, slug="scan-b"),
                                       passe(3, slug="scan-c")]})
    liste.viser(CIBLE)
    rendues = liste.lignes_des_passes()
    assert [ligne.split()[-1] for ligne in rendues] == ["scan-a", "scan-b",
                                                        "scan-c"]


def test_la_passe_retenue_par_defaut_est_celle_QUE_LE_LOT_DECLARE():
    """Trois passes, et la declaree **au milieu** : un repli sur la premiere ou
    sur la derniere se verrait, ce qu'une fabrique a deux passes ne demasque
    pas."""
    declaree = f"output-frames/{CIBLE}_v2"
    liste = trois_lots(passes={CIBLE: [
        passe(1, slug="scan-a", dossier=f"output-frames/{CIBLE}"),
        passe(2, slug="scan-b", dossier=declaree),
        passe(3, slug="scan-c", dossier=f"output-frames/{CIBLE}_v3")]})
    cible = liste.viser(CIBLE)
    cible.lot["output_frames_dir"] = declaree
    cible.passe = cible._passe_par_defaut()
    assert cible.reconstruction_visee == declaree
    assert liste.designer().reconstruction_visee == declaree


def test_une_passe_ABSENTE_du_disque_est_LISTEE_et_NOMMEE():
    """Le coeur l'enumere plutot que de la sauter, « parce que c'est
    precisement ce que l'operateur doit voir pour comprendre pourquoi une
    version n'est plus joignable ». L'ecran ne la masque pas."""
    liste = trois_lots(passes={CIBLE: [
        passe(1, slug="scan-a"),
        passe(2, slug="scan-b", dossier=f"output-frames/{CIBLE}_v2",
              presente=False)]})
    liste.viser(CIBLE)
    rendues = liste.lignes_des_passes()
    assert len(rendues) == 2
    assert lots_exports.MENTION_PASSE_ABSENTE in rendues[1]
    assert liste.etats_des_passes() == {1: "absent"}


def test_designer_une_passe_absente_REFUSE_et_ne_se_rabat_sur_AUCUNE_autre(
        tmp_path):
    """`EPIC11-ARB-89` : le refus nomme, et il n'y a pas de repli silencieux.

    Encoder la passe d'a cote produirait, sous le nom demande, une matiere que
    l'operateur n'a pas demandee. Le banc mesure les deux moities : le refus
    porte le code du coeur, et **aucun verdict** n'est rendu a la place.
    """
    lot = document_de_lot(CIBLE, passes=[
        {"ingest_slug": "scan-a", "output_frames_dir": f"output-frames/{CIBLE}"},
        {"ingest_slug": "scan-b",
         "output_frames_dir": f"output-frames/{CIBLE}_v2"}])
    racine = projet_sur_disque(tmp_path, [lot])

    resultat = lots_exports.balayer_le_lot(
        lot, racine, manifeste(lot),
        reconstruction_visee=f"output-frames/{CIBLE}_v2")
    assert resultat.verdict is None
    assert resultat.refus == encode.ENCODE_OUTPUT_DIR_ABSENT


def test_un_lot_SANS_historique_ne_vise_aucune_reconstruction():
    """`None` laisse le coeur retomber sur le champ scalaire, c'est-a-dire sur
    le comportement d'avant la story 6.8, messages compris. Lui passer une
    designation ferait dire `RECONSTRUCTION_INCONNUE` a un lot qui n'a jamais
    ete rescanne deux fois."""
    liste = trois_lots()
    assert liste.designer().reconstruction_visee is None


def test_le_champ_des_passes_ne_s_ouvre_PAS_sur_une_passe_unique():
    """« des qu'il en porte plusieurs ». Un champ a une seule valeur n'est pas
    un choix, et sa touche ne serait annoncee pour rien."""
    liste = trois_lots(passes={CIBLE: [passe(1, slug="scan-a")]})
    liste.viser(CIBLE)
    assert liste.lignes_des_passes() == []
    assert liste.basculer_le_focus() is False
    assert liste.focus == lots_exports.FOCUS_LOTS
    assert liste.raccourcis() == lots_exports.RACCOURCIS_LOTS_SANS_PASSES


def test_TAB_n_est_annonce_que_quand_il_mene_quelque_part():
    """`EPIC11-ARB-68` : `Tab` nomme sa **destination**, et il n'est annonce
    que s'il en a une. Les trois lignes sont mesurees, et elles sont
    distinctes -- deux lignes identiques ne mesureraient rien."""
    liste = trois_lots(passes={CIBLE: [passe(1, slug="scan-a"),
                                       passe(2, slug="scan-b")]})
    assert liste.raccourcis() == lots_exports.RACCOURCIS_LOTS_SANS_PASSES
    liste.viser(CIBLE)
    assert liste.raccourcis() == lots_exports.RACCOURCIS_LOTS
    assert liste.basculer_le_focus() is True
    assert liste.raccourcis() == lots_exports.RACCOURCIS_RECONSTRUCTIONS
    assert liste.basculer_le_focus() is True
    assert liste.focus == lots_exports.FOCUS_LOTS
    assert len({lots_exports.RACCOURCIS_LOTS,
                lots_exports.RACCOURCIS_LOTS_SANS_PASSES,
                lots_exports.RACCOURCIS_RECONSTRUCTIONS}) == 3


def test_les_fleches_bougent_le_curseur_OU_la_passe_selon_le_focus():
    """Le meme geste sur deux objets : c'est le focus qui tranche, et rien
    d'autre. Une fleche qui bougerait les deux ferait sauter le lot designe en
    changeant de version."""
    liste = trois_lots(passes={CIBLE: [passe(1, slug="scan-a"),
                                       passe(2, slug="scan-b")]})
    liste.viser(CIBLE)
    liste.basculer_le_focus()
    rang = liste.curseur
    liste.deplacer(-1)
    assert liste.curseur == rang
    assert liste.courant.passe == 0
    liste.focus = lots_exports.FOCUS_LOTS
    liste.deplacer(-1)
    assert liste.curseur == rang - 1


def test_changer_de_passe_change_le_DOSSIER_qui_part_au_coeur():
    """C'est l'appariement a risque de cet ecran : la passe designee et ce qui
    part au coeur. Les deux dossiers sont differents, sans quoi la mesure
    serait aveugle."""
    premier = f"output-frames/{CIBLE}"
    second = f"output-frames/{CIBLE}_v2"
    liste = trois_lots(passes={CIBLE: [
        passe(1, slug="scan-a", dossier=premier),
        passe(2, slug="scan-b", dossier=second)]})
    cible = liste.viser(CIBLE)
    cible.passe = 0
    assert liste.designer().reconstruction_visee == premier
    cible.deplacer_la_passe(1)
    assert liste.designer().reconstruction_visee == second


def test_le_verdict_est_indexe_par_PASSE_et_pas_seulement_par_lot():
    """Deux passes du meme lot ne portent pas la meme matiere : un verdict
    indexe par le seul `lot_id` afficherait celui de la passe precedente apres
    un changement de version -- exactement le mutant `M33`, par une autre
    porte."""
    liste = trois_lots(comptes=False, passes={CIBLE: [
        passe(1, slug="scan-a", dossier=f"output-frames/{CIBLE}"),
        passe(2, slug="scan-b", dossier=f"output-frames/{CIBLE}_v2")]})
    cible = liste.viser(CIBLE)
    cible.passe = 0
    liste.balayages[(CIBLE, f"output-frames/{CIBLE}")] = lots_exports.Balayage(
        verdict=verdict(attendues=63, trouvees=63))
    assert liste.balayage(cible) is not None
    cible.deplacer_la_passe(1)
    assert liste.balayage(cible) is None


def test_EPIC11_ARB_193_aucune_provenance_de_MASTER_n_est_affichee():
    """La dette est assumee et **dite** : rien au manifest ne dit de quelle
    reconstruction un master est issu, la cle de famille ne la gagnant pas.
    L'ecran ne l'affiche donc pas -- il ne la devine pas non plus."""
    lot = document_de_lot(CIBLE, passes=[
        {"ingest_slug": "scan-a", "output_frames_dir": f"output-frames/{CIBLE}"},
        {"ingest_slug": "scan-b",
         "output_frames_dir": f"output-frames/{CIBLE}_v2"}])
    lot["encoded_masters"] = [{"path": "masters/un_master.mov"}]
    liste = lots_exports.ListeDesLotsAEncoder(
        lots=[lots_exports.LotAListe(
            lot=lot, dossier=Path("x"),
            passes=tuple(encode.enumerer_les_reconstructions(lot, Path("/x"))))],
        manifeste=manifeste(lot))
    rendu = "\n".join(liste.lignes_de_la_carte() + [liste.ligne_d_etat()])
    assert "master" not in rendu.lower()


# ---------------------------------------------------------------------------
# La maquette validee -- les colonnes, et l'ecart SIGNALE
# ---------------------------------------------------------------------------

#: Les cinq lots de `E4-1`, dans l'ordre du dessin, avec le cardinal que la
#: maquette leur donne. **Les deux premiers sont comptes, les trois autres
#: non** : c'est l'etat que la maquette montre, celui du balayage en cours.
LOTS_DE_LA_MAQUETTE = (
    ("plan-04_25", 124, True),
    ("plan-04_12p5", 63, True),
    ("plan-04_8", 40, False),
    ("hiver_24", 31, False),
    ("sequence-12-atelier-fonderie-prise-3_12p5", 18, False),
)

#: Les deux passes de scan que la carte de `E4-1` dessine.
PASSES_DE_LA_MAQUETTE = (
    {"ingest_slug": "scan-2026-08-26",
     "output_frames_dir": "output-frames/plan-04_25"},
    {"ingest_slug": "scan-2026-09-02",
     "output_frames_dir": "output-frames/plan-04_25_v2"},
)


def _liste_de_la_maquette() -> lots_exports.ListeDesLotsAEncoder:
    """L'ecran que `E4-1` dessine : cinq lots, deux comptes, deux passes.

    Les passes sont enumerees **par le coeur**
    (`encode.enumerer_les_reconstructions`) plutot que construites a la main :
    un banc qui fabriquerait ses propres `ReconstructionDeLot` mesurerait sa
    propre lecture du manifest, pas celle du produit.
    """
    documents = [document_de_lot(
        nom, frames=cardinal,
        passes=list(PASSES_DE_LA_MAQUETTE) if nom == "plan-04_25" else None)
        for nom, cardinal, _compte in LOTS_DE_LA_MAQUETTE]
    racine = Path("/projet")
    liste = lots_exports.ListeDesLotsAEncoder(
        lots=[lots_exports.LotAListe(
            lot=document, dossier=racine / str(document["output_frames_dir"]),
            passes=tuple(encode.enumerer_les_reconstructions(document, racine)))
            for document in documents],
        manifeste=manifeste(*documents), project_dir=racine)
    for lot, (_nom, cardinal, compte) in zip(liste.lots, LOTS_DE_LA_MAQUETTE):
        if compte:
            liste.balayages[(lot.lot_id, lot.reconstruction_visee)] = \
                lots_exports.Balayage(
                    verdict=verdict(attendues=cardinal, trouvees=cardinal))
    liste.lots[0].passe = 0
    return liste


def test_les_COLONNES_sont_celles_de_la_maquette_validee():
    """La maquette est la seule source de verite du dessin, et elle se compare
    au caractere pres -- pas « a peu pres a la meme colonne ».

    **Les cinq lignes de liste ensemble**, et non la premiere seule : c'est
    l'etat a deux temps de `EPIC11-ARB-186` que le dessin porte -- deux
    pastilles comptees, trois rotors --, et une comparaison ligne a ligne le
    mesure au caractere pres, glyphe de chargement compris.
    """
    maquette = lignes_de_maquette()
    liste = _liste_de_la_maquette()
    assert liste.lignes_de_liste() == [ligne.rstrip()
                                       for ligne in maquette[4:9]]
    frames, cadence, geometrie = liste.lignes_de_la_carte()[2:]
    assert frames == maquette[14].rstrip()
    assert cadence == maquette[15].rstrip()
    assert geometrie == maquette[16].rstrip()


def test_le_CORPS_de_E4_1_est_celui_de_la_maquette_SAUF_les_deux_lignes_signalees():
    """Le corps entier, ligne a ligne, et l'ecart borne a **deux** lignes.

    C'est plus fort qu'une comparaison colonne par colonne : les seize lignes
    -- blanc de tete, titre, cinq lots, filet, carte -- sont confrontees
    ensemble, et les deux seules qui divergent sont celles du detail des
    passes, dont :func:`test_le_detail_des_passes_DIVERGE_de_la_maquette_et_c_est_SIGNALE`
    dit pourquoi. **Borner l'ecart est ce qui l'empeche de grandir** : une
    troisieme ligne qui divergerait ferait rougir ce test, pas une revue.
    """
    ecran = lots_exports.EcranDesLotsAEncoder(_liste_de_la_maquette())
    corps = [ligne.rstrip() for ligne in ecran.composer(80)[0]]
    maquette = [ligne.rstrip() for ligne in lignes_de_maquette()[1:17]]
    assert len(corps) == len(maquette)
    divergentes = [rang for rang, (rendu, dessin)
                   in enumerate(zip(corps, maquette)) if rendu != dessin]
    assert divergentes == [11, 12]
    assert all(lots_exports.LIBELLE_RECONSTRUCTION in maquette[11]
               for _ in (0,))


def test_l_ecran_se_MONTE_et_se_peint_sans_terminal(banc):
    """Le contrat du banc headless : la suite passe sans terminal.

    Un ecran qui compose bien mais ne monte pas est un ecran qui n'existe
    pas -- et `textual` coupe par le bas en silence, si bien qu'un corps trop
    haut ne se voit qu'ici.
    """
    ecran = lots_exports.EcranDesLotsAEncoder(_liste_de_la_maquette())
    application = CoqueTui(
        paliers=[PalierTemoin("Projet", "F1 aide"),
                 PalierTemoin("Ateliers", "F1 aide"), ecran],
        contexte=Contexte("projet_demo"))

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return (pilote.app.screen.query_one(
                    f"#{lots_exports.EcranDesLotsAEncoder.ID_DU_CORPS}").content,
                ecran.minuteur is not None)

    peint, tourne = banc(application, scenario)
    assert lots_exports.TITRE_DES_LOTS in str(peint)
    assert "plan-04_25" in str(peint)
    # **Le minuteur est mesure PENDANT le montage, jamais apres** : `run_test`
    # demonte l'application en refermant son gestionnaire de contexte, et
    # `on_unmount` arrete le minuteur -- une assertion posee apres coup
    # mesurerait le demontage. C'est la meme lecon que la poignee de minuteur
    # d'`EcranMireEnCours`.
    assert tourne is True
    assert ecran.minuteur is None


def test_la_LIGNE_D_ETAT_est_celle_de_la_maquette_validee():
    """`2 lots comptés sur 5 · plan-04_25 : 124 frames sur 124, 2 …`.

    Elle porte les trois mesures du dessin -- l'avancement du balayage, le
    cardinal du lot designe, le cardinal de ses passes -- et rien d'autre.
    """
    liste = _liste_de_la_maquette()
    assert liste.ligne_d_etat() == lignes_de_maquette()[18].rstrip()


def test_la_ligne_de_raccourcis_de_la_maquette_est_celle_du_produit():
    assert lots_exports.RACCOURCIS_LOTS == lignes_de_maquette()[19].rstrip()


def test_le_titre_et_le_filet_sont_ceux_de_la_maquette():
    maquette = lignes_de_maquette()
    assert lots_exports.TITRE_DES_LOTS in maquette[2]
    assert lots_exports.FILET_DU_LOT in maquette[10]


def test_le_detail_des_passes_DIVERGE_de_la_maquette_et_c_est_SIGNALE(
        tmp_path):
    """**Un ecart assume, mesure ici pour qu'il ne se perde pas.**

    La maquette dessine `v2  02/09 · 8 planches · 124 frames`. **Aucun de ces
    trois faits n'existe au manifest** : une entree de
    `lots[].reconstructions` porte `ingest_slug`, `output_frames_dir`,
    `origin` et `status`, et **aucune horodate** -- deliberement, l'idempotence
    octet a octet du document l'interdisant (`EPIC4-ARB-8`). Les afficher
    demanderait de les inventer.

    Et l'**ordre** diverge aussi : la maquette montre `v2` puis `v1`,
    c'est-a-dire l'inverse de l'ordre du manifest, que le coeur rend et que ce
    module ne retrie pas. Les deux ecarts appartiennent a la maquette : ils
    sont signales, pas corriges d'autorite.
    """
    lot = document_de_lot("plan-04_25", passes=list(PASSES_DE_LA_MAQUETTE))
    racine = tmp_path
    for entree in PASSES_DE_LA_MAQUETTE:
        (racine / entree["output_frames_dir"]).mkdir(parents=True)
    liste = lots_exports.ListeDesLotsAEncoder(
        lots=[lots_exports.LotAListe(
            lot=lot, dossier=racine / str(lot["output_frames_dir"]),
            passes=tuple(encode.enumerer_les_reconstructions(lot, racine)))],
        manifeste=manifeste(lot), project_dir=racine)
    rendues = liste.lignes_des_passes()

    # Ni date, ni cardinal de planches, ni cardinal de frames : aucun des trois
    # n'existe au manifest, et les afficher demanderait de les inventer.
    assert "planches" not in "\n".join(rendues)
    assert "02/09" not in "\n".join(rendues)
    # L'ordre rendu est celui du coeur, pas celui du dessin.
    assert rendues[0].endswith("scan-2026-08-26")
    assert rendues[1].endswith("scan-2026-09-02")
    assert lignes_de_maquette()[12].strip().startswith("Reconstruction")
    assert "v2" in lignes_de_maquette()[12]


# ---------------------------------------------------------------------------
# La grille -- rien ne deborde, dans les deux regimes
# ---------------------------------------------------------------------------

#: Le refus le plus LONG que le coeur puisse rendre a cet ecran. Il est
#: **cherche** parmi les codes du coeur plutot qu'ecrit : le code ajoute demain
#: entre dans la mesure le jour ou il est ecrit, sans qu'aucune story ait a le
#: nommer.
def _refus_le_plus_long() -> str:
    codes = [valeur for nom, valeur in vars(encode).items()
             if nom.startswith("ENCODE_") and isinstance(valeur, str)]
    assert len(codes) >= 20, codes
    return max(codes, key=len)


@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("resultat", [
    lots_exports.Balayage(verdict=verdict(attendues=124, trouvees=124)),
    lots_exports.Balayage(refus=_refus_le_plus_long()),
    None,
])
def test_aucune_ligne_ne_DEBORDE_la_largeur_utile(ascii_seul, resultat):
    """Y compris sur un identifiant de la **longueur maximale du produit** :
    c'est le cas pour lequel la colonne est calee, et c'est celui ou une
    colonne trop juste colle la pastille au nom.

    **Et y compris quand le coeur refuse** : le code le plus long du
    vocabulaire de refus, pose en colonne des pastilles, sortirait de la
    fenetre de cinq colonnes -- defaut trouve en ecrivant ce banc, corrige en
    le posant en colonne des valeurs. Les trois etats d'une ligne sont
    mesures : comptee, refusee, pas encore comptee.
    """
    long = "z" * naming.CANONICAL_ID_MAX_LENGTH
    lot = document_de_lot(long, frames=124)
    liste = lots_exports.ListeDesLotsAEncoder(
        lots=[lots_exports.LotAListe(lot=lot, dossier=Path("x"))],
        manifeste=manifeste(lot))
    if resultat is not None:
        liste.balayages[(long, None)] = resultat
    utile = jetons.largeur_utile()
    lignes = (liste.lignes_de_liste(utile, ascii_seul)
              + liste.lignes_de_la_carte(ascii_seul)
              + [liste.ligne_d_etat(ascii_seul), liste.raccourcis()])
    for ligne in lignes:
        rendu = jetons.replier_ascii(ligne) if ascii_seul else ligne
        assert jetons.colonnes(rendu) <= utile, ligne


def test_la_pastille_ne_COLLE_pas_a_un_nom_de_longueur_maximale():
    """Le creux est pris sur le nom, pas sur la colonne : la maquette pose la
    pastille immediatement apres un champ de la longueur maximale du produit."""
    long = "z" * naming.CANONICAL_ID_MAX_LENGTH
    lot = document_de_lot(long)
    liste = lots_exports.ListeDesLotsAEncoder(
        lots=[lots_exports.LotAListe(lot=lot, dossier=Path("x"))],
        manifeste=manifeste(lot))
    liste.balayages[(long, None)] = lots_exports.Balayage(
        verdict=verdict(attendues=1, trouvees=1))
    ligne = liste.lignes_de_liste()[0]
    glyphe = jetons.GLYPHES["complete"]
    assert f" {glyphe}" in ligne
    assert f"z{glyphe}" not in ligne


def test_la_zone_de_liste_garde_sa_HAUTEUR_quel_que_soit_le_projet():
    """C'est ce qui tient le filet -- et la carte avec lui -- a la meme ligne
    d'un projet a l'autre : « une cible qui se deplace quand la liste change de
    longueur est une cible qu'on rate »."""
    for cardinal in (1, 3, 9):
        lots = [document_de_lot(f"plan-04_{rang}") for rang in range(cardinal)]
        liste = lots_exports.ListeDesLotsAEncoder(
            lots=[lots_exports.LotAListe(lot=lot, dossier=Path("x"))
                  for lot in lots],
            manifeste=manifeste(*lots))
        assert len(liste.lignes_de_liste()) == lots_exports.HAUTEUR_LISTE


def test_la_geometrie_DISPARAIT_quand_le_manifest_ne_la_porte_pas():
    """Un manifest reconstruit depuis le scan seul ne porte ni
    `resolution_source` ni `output_bit_depth` : « leur absence est une
    propriete attendue, pas un defaut ». La ligne disparait plutot que de
    sortir a zero."""
    lot = document_de_lot("plan-04_25", profondeur=None)
    liste = lots_exports.ListeDesLotsAEncoder(
        lots=[lots_exports.LotAListe(lot=lot, dossier=Path("x"))],
        manifeste=manifeste(lot, avec_rush=False))
    assert liste.ligne_de_la_geometrie() == ""
    assert len(liste.lignes_de_la_carte()) == 2


def test_la_geometrie_est_celle_du_rush_DE_CE_LOT_et_pas_du_premier():
    """L'appariement se fait par `rush_id`, jamais par rang : un `rushes[0]`
    serait juste jusqu'au premier projet a deux rushes, ou l'ecran afficherait
    la geometrie de l'autre."""
    lot = document_de_lot("plan-04_25")
    document = manifeste(lot)
    document["rushes"].insert(0, {"rush_id": "un-autre-rush",
                                  "resolution_source": {"width": 4096,
                                                        "height": 2160}})
    liste = lots_exports.ListeDesLotsAEncoder(
        lots=[lots_exports.LotAListe(lot=lot, dossier=Path("x"))],
        manifeste=document)
    ligne = liste.ligne_de_la_geometrie()
    assert f"{LARGEUR}×{HAUTEUR}" in ligne
    assert "4096" not in ligne


def test_un_output_bit_depth_BOOLEEN_ne_rend_pas_UN_bits():
    """`True` est un `int` en Python : un document abime rendrait « 1 bits »,
    une valeur plausible donc invisible, ce qui est le pire des cas."""
    lot = document_de_lot("plan-04_25")
    lot["output_bit_depth"] = True
    liste = lots_exports.ListeDesLotsAEncoder(
        lots=[lots_exports.LotAListe(lot=lot, dossier=Path("x"))],
        manifeste=manifeste(lot))
    assert "1 bits" not in liste.ligne_de_la_geometrie()


# ---------------------------------------------------------------------------
# L'ecran -- le clavier et le rappel
# ---------------------------------------------------------------------------

def test_l_ecran_rend_sa_DESIGNATION_a_l_appelant():
    """Ce que `⏎` rend est ce qu'un parcours consomme : le lot, son dossier, la
    passe visee. Aucune valeur n'est recomposee par l'appelant."""
    liste = trois_lots()
    liste.viser(CIBLE)
    recues: list[lots_exports.Designation] = []
    ecran = lots_exports.EcranDesLotsAEncoder(liste, continuer=recues.append)
    assert ecran.traiter("enter") is True
    assert [designation.lot_id for designation in recues] == [CIBLE]
    assert recues[0].dossier == liste.courant.dossier


def test_l_ecran_arrete_son_minuteur_quand_TOUT_est_compte():
    """Un rotor qui continuerait de tourner sur un ecran fini dirait qu'il
    travaille encore."""
    class Minuteur:
        arrete = False

        def stop(self):
            self.arrete = True

    liste = trois_lots(comptes=False)
    ecran = lots_exports.EcranDesLotsAEncoder(
        liste, balayeur=lambda *_: lots_exports.Balayage(
            verdict=verdict(attendues=1, trouvees=1)))
    ecran.minuteur = Minuteur()
    ecran.rafraichir = lambda: None
    for _tour in range(len(liste.lots)):
        ecran.tourner()
    assert liste.balayage_fini is True
    assert ecran.minuteur is None


def test_le_balayeur_par_DEFAUT_est_le_vrai_balayage_du_disque():
    """« C'est le double qui est l'exception, pas le defaut. » Un
    `Callable | None = None` aurait fait de l'absence un silence, ce que la
    garde structurelle des rappels existe pour attraper."""
    ecran = lots_exports.EcranDesLotsAEncoder(trois_lots())
    assert ecran.balayeur is lots_exports.balayer_le_lot


def test_une_touche_inconnue_ne_pretend_RIEN_avoir_fait():
    liste = trois_lots()
    ecran = lots_exports.EcranDesLotsAEncoder(liste)
    assert ecran.traiter("f9") is False


def test_les_MESURES_annoncees_des_raccourcis_sont_les_MESURES_REELLES():
    """La convention `#: MESURE: <utf8>/<ascii>` du depot, appliquee aux trois
    lignes de cet ecran. Un chiffre se mesure, une prose ne se mesure pas."""
    import re

    source = MODULE.read_text(encoding="utf-8")
    motif = re.compile(r"#: MESURE: (\d+)/(\d+)\n(RACCOURCIS[A-Z_]*) = ",
                       re.MULTILINE)
    vues = motif.findall(source)
    assert len(vues) == 3, vues
    for utf8, ascii_, nom in vues:
        ligne = getattr(lots_exports, nom)
        assert (jetons.colonnes(ligne),
                jetons.colonnes(jetons.replier_ascii(ligne))) == (int(utf8),
                                                                  int(ascii_))
