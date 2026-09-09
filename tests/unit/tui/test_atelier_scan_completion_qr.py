# -*- coding: utf-8 -*-
"""Story 11.5, lot E -- la completion de QR, `E3-4b` (AC 7).

Ce banc mesure `tui/atelier_scan_completion.py`, et **lui seul**. Les autres
lots du Scan ont chacun le leur : « aucun lot ne partage un fichier de banc avec
un autre » -- ni `git add -N` ni `git commit -- <chemins>` ne protegent a
l'interieur d'un fichier partage, defaut paye trois fois sur ce depot.

**Quatre regles de mesure heritees, et elles commandent la forme des fabriques :**

1. **toute fabrique de collection produit au moins deux elements
   distinguables**, et **trois avec la cible au milieu des qu'une boucle
   compte** (CLAUDE.md, point 2 bis). Les boucles de ce module sont **les lots
   du manifeste**, **les pages deja lues du lot**, **les identites deja posees**
   et **les planches encore a completer** : chacune recoit une fabrique a trois
   elements distinguables, cible au **milieu** ;
2. **la position se verifie sur la liste que le code PARCOURT**, jamais sur
   celle que la fabrique croit ecrire ;
3. **une assertion positive laisse passer toute divergence supplementaire.**
   « Ce fichier a change » ne mesure rien ; « l'ensemble des chemins qui
   changent est **exactement** {X} » mesure l'exception ET son unicite ;
4. **un condensat ne prouve pas qu'un fichier n'a pas ete touche** quand la
   fixture est deterministe : l'AC 7.5 se mesure aux **inodes**, au
   `st_mtime_ns`, et par un **temoin** depose dans le dossier vise.

**Ce que la fixture ne met pas en scene.** Le document de detection vient du
coeur (`tests/fixtures/detection-scan-reelle/detect-ok-et-refus.json`, verse au
depot en 7.4) : `qr_status = no_symbol_detected` y est un constat de terrain,
pas une valeur posee ici. C'est la garde contre le piege d'`EPIC5-ARB-39` --
« une fixture de synthese peut rendre vrai par construction ce que l'on croit
mesurer ».
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import io
import json
import re
import subprocess
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import page_templates, pdf_composition, scan_corrections
from mixed_media_utility.io import payload as payload_io
from mixed_media_utility import scan_previz
from mixed_media_utility.tui import atelier_scan_completion as completion_qr
from mixed_media_utility.tui import execution, jetons
from mixed_media_utility.tui.atelier_scan_rapport import PageMuette
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

from outils_frontiere import chaines_de_code, identifiants

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le paquet mesure, pour les frontieres negatives.
DOSSIER_TUI = Path(_SRC) / "mixed_media_utility" / "tui"

#: Le document de detection **reellement produit par le coeur** : une planche
#: lue et une planche dont le QR n'a rien livre, sur un scan de terrain.
DOCUMENT_REEL = (
    Path(__file__).resolve().parents[2]
    / "fixtures" / "detection-scan-reelle" / "detect-ok-et-refus.json"
)

#: Le lot de ce scan reel. C'est la **cible** de toutes les fabriques de lots,
#: et elle est placee en **seconde position sur trois** : un `find` fautif qui
#: rendrait toujours le premier lot ne se demasque pas autrement (mutant `M25`
#: de la story 5.7).
LOT_CIBLE = "rush-bitch-4-chendj-mat_1-c60b2a76"
LOT_AVANT = "rush-voisin_5"
LOT_APRES = "rush-zenith_2"


# ---------------------------------------------------------------------------
# Fabriques. Aucune ne produit un element unique, aucune ne remplit une
# collection d'une valeur uniforme.
# ---------------------------------------------------------------------------


def manifeste_du_projet() -> dict:
    """Le manifeste, **trois lots distinguables**, la cible au MILIEU.

    Les trois lots different sur **chacun** des sept champs que le modele de
    completion lit -- rush, cadence, base de timecode, gabarit, preset de
    pastilles, compression de gamut, cardinal de frames. Un remplissage uniforme
    laisserait passer n'importe quelle permutation, et c'est precisement
    l'erreur d'appariement que la regle des fabriques existe pour attraper.
    """
    return {
        "schema_version": "2.1",
        "project_id": "chendj-mat",
        "created": "2026-08-29T00:00:00Z",
        "rushes": [
            {"rush_id": "rush-voisin", "source_name": "voisin.mov",
             "fps_source": 25.0, "fps_source_exact": "25/1",
             "resolution_source": {"width": 1920, "height": 1080}},
            {"rush_id": "rush-bitch-4-chendj-mat", "source_name": "bitch-4.mov",
             "fps_source": 25.0, "fps_source_exact": "25/1",
             "resolution_source": {"width": 1920, "height": 1080}},
            {"rush_id": "rush-zenith", "source_name": "zenith.mov",
             "fps_source": 25.0, "fps_source_exact": "25/1",
             "resolution_source": {"width": 1920, "height": 1080}},
        ],
        "lots": [
            # PREMIERE position : le leurre. Tout y differe de la cible.
            {"lot_id": LOT_AVANT, "rush_id": "rush-voisin",
             "state": "extraction", "fps_target": 5.0, "fps_target_exact": "5/1",
             "timecode_base_fps": "24/1",
             "template_id": "tpl-a4-portrait-1f-v2",
             "patch_preset_id": "patches-9-v1",
             "gamut_map_id": "gamut-map-lin-1",
             "expected_frame_count": 10, "frames_dir": "frames/voisin",
             "source_frame_count": 50, "source_frame_count_is_exact": True,
             "rounding_policy": "floor"},
            # SECONDE position sur trois : la CIBLE, celle du scan reel.
            {"lot_id": LOT_CIBLE, "rush_id": "rush-bitch-4-chendj-mat",
             "state": "extraction", "fps_target": 1.0, "fps_target_exact": "1/1",
             "timecode_base_fps": "25/1",
             "template_id": "tpl-a4-paysage-4f-v2",
             "patch_preset_id": "patches-17-v4",
             "gamut_map_id": "gamut-map-none-1",
             "expected_frame_count": 4, "frames_dir": "frames/bitch4",
             "source_frame_count": 100, "source_frame_count_is_exact": True,
             "rounding_policy": "floor"},
            # DERNIERE position : un lot de plusieurs planches.
            {"lot_id": LOT_APRES, "rush_id": "rush-zenith",
             "state": "extraction", "fps_target": 2.0, "fps_target_exact": "2/1",
             "timecode_base_fps": "30000/1001",
             "template_id": "tpl-a4-portrait-4f-v2",
             "patch_preset_id": "patches-12-v1",
             "gamut_map_id": "gamut-map-lin-1",
             "expected_frame_count": 10, "frames_dir": "frames/zenith",
             "source_frame_count": 125, "source_frame_count_is_exact": True,
             "rounding_policy": "floor"},
        ],
        "artifacts": {"frames_dir": "frames"},
        "color": {"target_colorspace": "bt709"},
        "video": {},
        "reconstruction": {},
    }


def document_reel() -> dict:
    """Le document de detection du coeur, relu tel quel."""
    return json.loads(DOCUMENT_REEL.read_text(encoding="utf-8"))


def pile_d_une_seule_planche_muette() -> dict:
    """Le document reel **reduit a sa seule planche refusee**.

    C'est le cas qu'Egan a nomme (AC 7.1) : une pile d'une seule page dont le QR
    echoue. Elle n'a aucune planche soeur a lire, donc aucun modele decode --
    avant `EPIC11-ARB-64`, elle etait incompletable pour cette seule raison.
    Rien n'est mis en scene : on retire l'autre page, on ne fabrique pas un
    refus.
    """
    document = document_reel()
    refusees = [page for page in document["pages"]
                if page.get("qr_status") != "decoded"]
    assert len(refusees) == 1, [p.get("qr_status") for p in document["pages"]]
    document["pages"] = refusees
    # Les compteurs suivent la pile reduite : le lecteur normatif du coeur les
    # confronte au cardinal reel des pages, et un document qui se contredit est
    # refuse (`scan_previz_from_json_dict`, « une valeur alteree est refusee,
    # jamais devinee »). On reduit la pile, on ne fabrique pas un document faux.
    document["counters"]["pages_present"] = len(refusees)
    return document


def planche_muette(read_rank: int = 1,
                   fichier: str = "scans/scans-in/page_02.png") -> PageMuette:
    return PageMuette(read_rank=read_rank, fichier=fichier,
                      code="QR_NON_DECODE", lot_id=LOT_CIBLE)


def trois_pages_lues(total: int = 4, occupee: int = 2, numeros=None,
                     totaux=None) -> tuple:
    """Trois planches lues du meme lot, **la cible au MILIEU**, distinguables.

    Point 2 bis de CLAUDE.md, et il mord ici : `verifier_la_coherence` **boucle**
    sur cette liste pour trouver la page occupee. Une fabrique a deux elements
    dont la cible est en second la placerait aussi en **dernier**, et un
    `break` premature y serait indiscernable d'un `continue`.

    Les trois rangs, les trois fichiers et les trois numeros de page different :
    un remplissage uniforme rendrait invisible toute permutation.

    `totaux` fait diverger le **cardinal annonce page par page**, `None`
    compris. Sans lui, les trois pages portaient toutes le meme `page_count` :
    un remplissage uniforme au sens du point 1, sur la dimension « la page
    annonce-t-elle un total », et c'est ce remplissage qui laissait retirer la
    garde `page_count is not None` de `verifier_la_coherence` sans qu'un test
    bronche. La valeur par defaut reste uniforme parce que c'est le regime
    nominal -- trois planches d'un meme lot annoncent le meme total --, et tout
    test qui mesure une divergence la pose explicitement.
    """
    rangs = (7, 3, 11)
    numeros = numeros or (1, occupee, total)
    totaux = (total,) * 3 if totaux is None else totaux
    return tuple(
        completion_qr.PageLue(read_rank=rang, page_index=numero - 1,
                              page_count=annonce,
                              fichier=f"scans/scans-in/page_{numero:02d}.png")
        for rang, numero, annonce in zip(rangs, numeros, totaux))


def formulaire(pages_lues=(), manifeste=None, planche=None,
               **valeurs) -> completion_qr.FormulaireDeCompletion:
    """La cle `page` de :data:`SAISIE_VALIDE` est un CHAMP du formulaire : la
    planche visee se passe donc par `planche=`, sans quoi les deux se
    disputeraient le meme mot-cle."""
    forme = completion_qr.FormulaireDeCompletion(
        page=planche or planche_muette(),
        manifeste=manifeste if manifeste is not None else manifeste_du_projet(),
        pages_lues=pages_lues)
    forme.valeurs.update(valeurs)
    return forme


#: Une saisie **valide** de la planche muette du scan reel, champ par champ.
#: Les valeurs sont celles que la planche porte imprimees -- le gabarit et le
#: lot sont ceux du manifeste, les timecodes ceux de sa jumelle lue.
SAISIE_VALIDE = {
    completion_qr.CHAMP_LOT: LOT_CIBLE,
    completion_qr.CHAMP_PAGE: "1",
    completion_qr.CHAMP_GABARIT: "tpl-a4-paysage-4f-v2",
    completion_qr.CHAMP_FRAMES: "4",
    completion_qr.CHAMP_TC_PREMIER: "00:00:00:00",
    completion_qr.CHAMP_TC_DERNIER: "00:00:00:03",
}


def formulaire_rempli(**surcharges):
    valeurs = dict(SAISIE_VALIDE)
    valeurs.update(surcharges)
    return formulaire(**valeurs)


def _app(ecran, projet="chendj-mat", **kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                    contexte=Contexte(projet=projet), **kwargs)


def _monte(app, scenario, banc):
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def _texte(ecran) -> str:
    """Le texte **tel qu'il s'affiche**, style retire."""
    return jetons.texte_affiche(str(ecran._corps.content))


def ecran(page=None, manifeste=None, **kwargs):
    """L'ecran monte. `poser` est **requis** cote produit -- l'ecran ne peut pas
    etre monte sans savoir a qui rendre l'identite validee (finding `K3`) --,
    donc ce banc en pose un par defaut, et les tests qui le mesurent en passent
    un qui compte."""
    kwargs.setdefault("poser", lambda _identite: None)
    return completion_qr.EcranCompletionQr(
        page or planche_muette(),
        manifeste if manifeste is not None else manifeste_du_projet(),
        **kwargs)


def _rendu(e, banc, app=None, **kwargs) -> str:
    async def scenario(_pilote):
        return _texte(e)

    return _monte(app or _app(e, **kwargs), scenario, banc)


# ===========================================================================
# E1 / AC 7.1 -- le modele vient du MANIFESTE, et la planche UNIQUE se complete
# ===========================================================================

def test_le_modele_porte_les_HUIT_champs_neutres_et_vient_du_manifeste():
    """AC 7.1 -- `EPIC11-ARB-64` : « DEPUIS LE MANIFESTE, pas d'une planche lue ».

    Ensemble **exact** et non assertion positive : un modele qui porterait un
    neuvieme champ n'aurait plus la meme source, et l'AC 7.2 s'appuie sur le
    fait que ces huit-la, et eux seuls, ne sont pas demandes a l'operateur.
    """
    forme = formulaire(lot=LOT_CIBLE)
    modele = forme.modele
    assert modele is not None, forme.refus_du_modele
    assert set(modele) == set(scan_corrections.CHAMPS_NEUTRES_DU_LOT) | {"lot_id"}


def test_le_modele_est_celui_du_lot_VISE_et_pas_du_PREMIER_de_la_liste():
    """Point 2 de la regle des fabriques, sur la liste que le COEUR parcourt.

    La verification porte sur `manifeste["lots"]` -- la liste reellement iteree
    par `modele_depuis_le_manifeste` --, pas sur l'ordre que cette fabrique croit
    ecrire. Un `find` qui rendrait toujours le premier lot ecrirait les valeurs
    du leurre sur la planche de la cible : c'est le mutant `M25` de la 5.7, dont
    la consequence reelle etait d'ecrire les cardinaux sur le mauvais lot.
    """
    manifeste = manifeste_du_projet()
    ordre = [lot["lot_id"] for lot in manifeste["lots"]]
    assert ordre.index(LOT_CIBLE) == 1, ordre          # ni premier, ni dernier
    modele = formulaire(manifeste=manifeste, lot=LOT_CIBLE).modele
    vise = manifeste["lots"][1]
    assert modele["rush_id"] == vise["rush_id"]
    assert modele["fps_target"] == vise["fps_target"]
    assert modele["timecode_base_fps"] == vise["timecode_base_fps"]
    assert modele["patch_preset_id"] == vise["patch_preset_id"]
    assert modele["gamut_map_id"] == vise["gamut_map_id"]


def test_une_pile_d_UNE_SEULE_planche_muette_est_COMPLETABLE(banc):
    """AC 7.1, le cas qu'Egan a nomme -- et il est mesure de bout en bout.

    Le document est le **reel**, reduit a sa seule planche refusee : elle n'a
    aucune soeur a lire, donc aucun modele decode. Avant `EPIC11-ARB-64` elle
    etait incompletable pour cette seule raison ; ici elle produit un payload.
    """
    document = pile_d_une_seule_planche_muette()
    previz = scan_previz.scan_previz_from_json_dict(document)
    assert [p.qr_status for p in previz.pages] == ["no_symbol_detected"]
    lues = completion_qr.pages_lues_du_lot([previz], LOT_CIBLE)
    assert lues == (), lues            # aucune planche soeur : c'est le cas

    forme = formulaire(pages_lues=lues, **SAISIE_VALIDE)
    payload = forme.payload()
    assert payload["lot_id"] == LOT_CIBLE
    assert len(payload["slots"]) == 4


def test_le_modele_NE_SE_CONSTRUIT_PAS_avant_que_le_lot_soit_saisi():
    """Le modele est celui d'un LOT, et rien n'est prerempli (AC 7.3).

    Une planche du reliquat n'a aucun lot connu -- c'est la definition du
    reliquat --, donc le lot est ce que l'operateur tape en premier. Rendre un
    modele avant serait rendre celui d'un lot que personne n'a nomme.
    """
    forme = formulaire()
    assert forme.modele is None
    assert forme.refus_du_modele == ""


def test_un_lot_INCONNU_du_manifeste_rend_le_motif_du_COEUR_verbatim():
    """AC 7.2 : « le refus est rendu par son motif, jamais par un message local ».

    Le motif du coeur nomme le lot cherche **et** les lots connus du projet :
    c'est ce qui envoie l'operateur au bon endroit quand il a scanne les
    planches d'un autre projet. Le resumer le detruirait (`EPIC11-ARB-30`).
    """
    forme = formulaire(lot="lot-qui-n-existe-pas")
    assert forme.modele is None
    attendu = str(pytest.raises(
        scan_corrections.IdentiteIncompletable,
        lambda: scan_corrections.modele_depuis_le_manifeste(
            manifeste_du_projet(), lot_id="lot-qui-n-existe-pas")).value)
    assert forme.refus_du_modele == attendu


def test_un_GABARIT_de_manifeste_inconnu_rend_un_MESSAGE_et_pas_une_trace():
    """`page_templates.UnknownTemplateError` ne descend PAS d'`IdentiteIncompletable`.

    `modele_depuis_le_manifeste` lit `lots[].template_id` pour deduire le
    cardinal de planches, et `get_template` leve son propre refus quand ce
    gabarit a quitte le registre. Ne pas l'attraper ferait tomber la TUI sur un
    manifeste parfaitement plausible -- c'est le seul chemin de cet ecran ou un
    refus du coeur remonterait en trace.
    """
    manifeste = manifeste_du_projet()
    manifeste["lots"][1]["template_id"] = "tpl-retire-du-registre"
    with pytest.raises(page_templates.UnknownTemplateError):
        scan_corrections.modele_depuis_le_manifeste(manifeste, lot_id=LOT_CIBLE)
    forme = formulaire(manifeste=manifeste, lot=LOT_CIBLE)
    assert forme.modele is None
    assert "tpl-retire-du-registre" in forme.refus_du_modele


def test_le_modele_est_RECONSTRUIT_quand_le_lot_saisi_change():
    """La memoire est indexee par la saisie, et une lettre de plus l'invalide.

    Sans cela, corriger une faute de frappe dans le lot laisserait a l'ecran le
    modele du lot precedent -- c'est-a-dire les valeurs neutres d'un autre lot
    posees sur cette planche, exactement ce que `payload_depuis_l_identite`
    refuse de son cote (« completer l'une par l'autre melangerait deux lots »).
    """
    forme = formulaire(lot=LOT_AVANT)
    assert forme.modele["rush_id"] == "rush-voisin"
    forme.valeurs[completion_qr.CHAMP_LOT] = LOT_CIBLE
    assert forme.modele["rush_id"] == "rush-bitch-4-chendj-mat"
    forme.valeurs[completion_qr.CHAMP_LOT] = "inconnu"
    assert forme.modele is None and forme.refus_du_modele


# ===========================================================================
# E2 / AC 7.2 -- la validation passe par le COEUR, et par lui seul
# ===========================================================================

def test_le_payload_est_EXACTEMENT_celui_que_le_coeur_compose():
    """AC 7.2. L'egalite porte sur le dictionnaire ENTIER, slots compris.

    Une assertion « le payload porte le bon lot » laisserait passer une
    interpolation de timecodes reecrite ici. L'egalite complete ferme la classe.
    """
    forme = formulaire_rempli()
    attendu = scan_corrections.payload_depuis_l_identite(
        forme.identite(), modele=forme.modele)
    assert forme.payload() == attendu


def test_l_identite_composee_porte_les_SIX_champs_du_coeur_et_le_rang_de_la_page():
    """`read_rank` vient de la planche fautive, jamais de la saisie.

    Le faire recopier offrirait a l'operateur l'occasion de poser sa correction
    sur une autre planche -- et cette faute-la produit exactement le meme succes
    apparent (AC 7.9).
    """
    page = planche_muette(read_rank=1)
    forme = formulaire(planche=page, **SAISIE_VALIDE)
    identite = forme.identite()
    assert identite.read_rank == page.read_rank
    assert identite.lot_id == LOT_CIBLE
    assert identite.template_id == "tpl-a4-paysage-4f-v2"
    assert identite.frames_per_page == 4


def test_le_numero_de_page_saisi_est_celui_qui_est_IMPRIME_donc_a_partir_de_UN():
    """La planche imprime `page N/M` a partir de 1, le document numerote a 0.

    C'est le decalage le plus facile a poser a l'envers de tout l'ecran, et il
    ne se voit nulle part : une planche 2 saisie deviendrait la planche 3 du
    lot, et le nom des TIFF suivrait sans un mot.
    """
    forme = formulaire_rempli(**{completion_qr.CHAMP_PAGE: "2"})
    assert forme.page_declaree == 2
    assert forme.identite().page_index == 1


#: Les noms par lesquels une **seconde regle de payload** se reconnaitrait :
#: composer un payload, le valider, le decoder, ou reecrire son numero de
#: schema. Lire la table des cles courtes n'en fait pas partie -- l'ecran s'en
#: sert pour AFFICHER la cle imprimee d'un champ, ce qui est l'inverse d'une
#: seconde regle : c'est une lecture de la table du depot.
NOMS_D_UNE_SECONDE_REGLE = (
    "build_page_payload",
    "validate_payload",
    "parse_payload",
    "encode_payload",
    "PAYLOAD_SCHEMA_VERSION",
    "CHAMPS_NEUTRES_DU_LOT_LOCAUX",
)

#: Les modules du Scan, ceux sur lesquels le comptage a zero porte.
MODULES_DU_SCAN = ("atelier_scan.py", "atelier_scan_detection.py",
                   "atelier_scan_rapport.py", "atelier_scan_completion.py")


def _seconde_regle(dossier: Path, modules=None) -> list[str]:
    """Les references a une composition de payload dans les modules donnes."""
    trouvees = []
    for chemin in sorted(dossier.rglob("*.py")):
        if modules is not None and chemin.name not in modules:
            continue
        noms = identifiants(chemin)
        trouvees += [f"{chemin.name}:{nom}"
                     for nom in NOMS_D_UNE_SECONDE_REGLE if nom in noms]
    return trouvees


def test_AUCUNE_seconde_regle_de_payload_dans_les_modules_du_Scan():
    """AC 7.2, comptage a zero (`EPIC11-ARB-27`).

    A l'AST et non au texte : le docstring du module **explique** qu'il n'ecrit
    pas de seconde regle, donc il en porte le vocabulaire. Un grep de chaine y
    mordrait et se ferait affaiblir -- piege deja paye a l'ecriture de la 11.0.
    """
    assert _seconde_regle(DOSSIER_TUI, MODULES_DU_SCAN) == []


def test_les_QUATRE_modules_du_Scan_existent_bien(paquet_tui):
    """Volet symetrique du comptage ci-dessus : il porte sur quelque chose.

    Une frontiere appliquee a un ensemble vide est verte sans rien mesurer, et
    c'est exactement le mode de panne que les volets symetriques excluent.
    """
    presents = {chemin.name for chemin in paquet_tui.glob("*.py")}
    assert set(MODULES_DU_SCAN) <= presents, sorted(presents)


def test_la_frontiere_de_la_SECONDE_REGLE_de_payload_MORD(tmp_path):
    """Volet symetrique : la mesure SORT sur un module qui compose un payload.

    Elle fait tourner la **meme** fonction de mesure que la frontiere, sur un
    paquet fabrique pour l'occasion -- et non deux chaines ecrites dans le test,
    ce qui etait la tautologie de `test_la_frontiere_de_sobriete_MORD`.
    """
    faux = tmp_path / "faux_paquet"
    faux.mkdir()
    (faux / "atelier_scan.py").write_text("VALEUR = 1\n", encoding="utf-8")
    (faux / "atelier_scan_completion.py").write_text(
        "from ..io.payload import build_page_payload\n\n\n"
        "def payload(**champs):\n"
        "    return build_page_payload(**champs)\n", encoding="utf-8")
    trouvees = _seconde_regle(faux, MODULES_DU_SCAN)
    assert trouvees == ["atelier_scan_completion.py:build_page_payload"], trouvees


def test_le_module_APPELLE_les_trois_points_d_entree_du_coeur():
    """Le pendant positif : les trois fonctions nommees par l'AC 7 sont bien
    celles que le module emprunte, et il ne s'en invente aucune quatrieme."""
    noms = identifiants(Path(completion_qr.__file__))
    assert {"modele_depuis_le_manifeste", "payload_depuis_l_identite",
            "poser_les_identites", "lire_les_identites"} <= noms


def test_le_refus_du_coeur_arrive_VERBATIM_en_ligne_d_etat(banc):
    """AC 7.2 : jamais « échec », jamais un resume -- le motif du coeur, entier.

    Le gabarit saisi porte quatre emplacements de moins que la planche : le
    coeur refuse en nommant le gabarit **et** les deux cardinaux, ce qui dit a
    l'operateur quoi corriger. Un « saisie invalide » local ne le dirait pas.
    """
    e = ecran()
    e.formulaire.valeurs.update(SAISIE_VALIDE)
    e.formulaire.valeurs[completion_qr.CHAMP_GABARIT] = "tpl-a4-portrait-1f-v2"

    async def scenario(_pilote):
        e.formulaire.champ = completion_qr.CHAMP_TC_DERNIER
        e.traiter("enter")
        return e.etat()

    etat = _monte(_app(e), scenario, banc)
    assert "tpl-a4-portrait-1f-v2" in etat
    assert "1" in etat and "4" in etat


# ===========================================================================
# E3 / AC 7.3 -- rien n'est prerempli, mesure CHAMP PAR CHAMP
# ===========================================================================

def test_les_champs_du_formulaire_sont_EXACTEMENT_ceux_de_l_identite_du_coeur():
    """AC 7.3 et note 12 d'Egan : le formulaire demande ce qu'il doit demander,
    et **rien de plus**.

    Egalite et non inclusion : la maquette d'origine demandait « Projet » et les
    deux cadences -- des champs **neutres**, que le manifeste donne -- et taisait
    le gabarit, le cardinal d'images et les deux timecodes. Elle demandait donc
    ce qu'elle n'aurait pas du et taisait ce qu'elle devait demander.
    """
    assert (set(completion_qr.CHAMP_DU_COEUR.values())
            == set(scan_corrections.CHAMPS_D_IDENTITE))
    demandes = set(completion_qr.CHAMP_DU_COEUR.values())
    assert demandes & set(scan_corrections.CHAMPS_NEUTRES_DU_LOT) == set()


@pytest.mark.parametrize("cle", completion_qr.CHAMPS_SAISIS)
def test_AUCUN_champ_n_est_prerempli_au_montage(cle):
    """AC 7.3, **champ par champ** et non « le formulaire est vide ».

    « Un champ devine faux n'appelle pas la verification » : c'est la regle du
    Flow 3 de la GUI, reprise sans amenagement, et c'est celle qu'`EPIC11-ARB-38`
    applique deja au dpi de `E3-1`.
    """
    assert formulaire().valeurs[cle] == ""


def test_le_formulaire_montre_SIX_champs_vides_a_l_ecran(banc):
    """Le pendant a l'ecran : six lignes, six glyphes de « rien ici ».

    Une case vide se lirait comme un defaut de rendu ; `DESIGN.md` section 6
    fait du glyphe neutre le second canal de « rien ici ».
    """
    e = ecran()
    rendu = _rendu(e, banc)
    for cle in completion_qr.CHAMPS_SAISIS:
        assert completion_qr.LIBELLES[cle] in rendu
    assert rendu.count("·") >= len(completion_qr.CHAMPS_SAISIS)
    assert (rendu.count(completion_qr.MENTION_REQUIS)
            == len(completion_qr.CHAMPS_SAISIS))


def test_l_ordre_des_champs_suit_la_PLANCHE_de_haut_en_bas():
    """Note 12 d'Egan : « il faut que le formulaire soit DANS LE MEME ORDRE que
    les infos du pied de page ».

    Applique a la feuille entiere, l'ordre est : l'en-tete (le nom de planche,
    puis la pagination), le pied technique (le gabarit), puis les reperes sous
    les images. Une egalite de liste, jamais une inclusion : une permutation est
    exactement ce que cette AC cherche a empecher.
    """
    assert completion_qr.CHAMPS_SAISIS == (
        completion_qr.CHAMP_LOT, completion_qr.CHAMP_PAGE,
        completion_qr.CHAMP_GABARIT, completion_qr.CHAMP_FRAMES,
        completion_qr.CHAMP_TC_PREMIER, completion_qr.CHAMP_TC_DERNIER)


def test_les_cles_imprimees_sont_LUES_de_la_table_du_depot():
    """Note 12, axe 3 : « en precisant a chaque fois la cle correspondant a
    chaque champ ».

    Les cles sont **derivees** de `io.payload.PAYLOAD_SHORT_KEYS`, jamais
    recopiees : une seconde redaction enverrait l'operateur chercher au pied une
    mention que la planche n'imprime plus. Et les trois champs qui n'en ont
    aucune sont mesures **comme tels** -- ce sont des `slots` du payload, pas des
    scalaires, donc le pied ne les imprime pas.
    """
    assert completion_qr.CLE_IMPRIMEE == {
        completion_qr.CHAMP_LOT: payload_io.PAYLOAD_SHORT_KEYS["lot_id"],
        completion_qr.CHAMP_PAGE: payload_io.PAYLOAD_SHORT_KEYS["page_index"],
        completion_qr.CHAMP_GABARIT: payload_io.PAYLOAD_SHORT_KEYS["template_id"],
    }
    sans_cle = set(completion_qr.CHAMPS_SAISIS) - set(completion_qr.CLE_IMPRIMEE)
    assert sans_cle == {completion_qr.CHAMP_FRAMES,
                        completion_qr.CHAMP_TC_PREMIER,
                        completion_qr.CHAMP_TC_DERNIER}


def test_la_ligne_du_manifeste_porte_les_HUIT_cles_DANS_L_ORDRE_de_la_planche():
    """Note 12, axe 1 : ce que le manifeste donne se **montre** sans se demander.

    L'ordre est celui de la feuille de haut en bas : le bloc d'identite et
    l'entete d'abord, puis le pied technique dans l'ordre de
    `pdf_composition.PIED_CHAMPS`. Il est **derive** des deux tuples du coeur, et
    c'est ce qui le fait bouger tout seul si le contrat change.
    """
    ligne = formulaire(lot=LOT_CIBLE).ligne_du_manifeste()
    cles = ligne.split("  ")[-1].split()
    attendues = [payload_io.PAYLOAD_SHORT_KEYS[champ]
                 for champ in completion_qr.ORDRE_DES_CHAMPS_NEUTRES]
    assert cles == attendues
    assert attendues[:3] == [payload_io.PAYLOAD_SHORT_KEYS[c]
                             for c in ("project_id", "rush_id", "fps_target")]
    assert attendues[3:] == [payload_io.PAYLOAD_SHORT_KEYS[champ]
                             for champ in pdf_composition.PIED_CHAMPS
                             if champ in scan_corrections.CHAMPS_NEUTRES_DU_LOT]


@pytest.mark.parametrize("absent", completion_qr.ORDRE_DES_CHAMPS_NEUTRES)
def test_un_modele_AUQUEL_IL_MANQUE_un_champ_n_annonce_PAS_sa_cle(absent):
    """« Annoncer un champ qu'on n'a pas serait la seule chose que cette ligne
    ne doit jamais faire » -- la docstring de `cles_du_manifeste` nomme le
    defaut que sa garde ferme, et **rien ne le mesurait**.

    Tous les modeles de ce banc viennent de `manifeste_du_projet()`, dont les
    trois lots portent les **huit** champs neutres : c'est un remplissage
    uniforme au sens du point 1, sur la dimension « le modele est-il complet ».
    Retirer `if champ in modele` passait les 3298 tests de `tests/unit/tui/`.

    **Le modele troue est forcement fabrique, et c'est le regime que la
    docstring vise** : mesure faite ici, `modele_depuis_le_manifeste` *refuse*
    un lot sans `patch_preset_id` (« ces valeurs ne se devinent pas ») plutot
    que de rendre un modele troue. La garde protege donc le seul chemin qui
    reste -- un modele construit ailleurs qu'au manifeste --, et c'est celui-la
    qu'il faut monter pour la mesurer : un modele complet ne mesure rien.

    Le champ retire l'est **a chacune des huit positions** plutot qu'a une
    seule. Une garde qui testerait l'appartenance du champ **voisin** ne se
    demasque pas autrement, et les deux bouts de l'ordre imprime sont ceux
    qu'un `[1:]` ou un `[:-1]` emporterait sans bruit.

    L'ensemble rendu est mesure **exactement**, jamais par une appartenance :
    « la cle manquante n'y est pas » laisserait passer toute divergence
    supplementaire.
    """
    complet = formulaire(lot=LOT_CIBLE).modele
    assert complet is not None
    assert absent in complet, sorted(complet)
    troue = {champ: valeur for champ, valeur in complet.items()
             if champ != absent}
    attendues = tuple(payload_io.PAYLOAD_SHORT_KEYS[champ]
                      for champ in completion_qr.ORDRE_DES_CHAMPS_NEUTRES
                      if champ != absent)
    assert len(attendues) == len(completion_qr.ORDRE_DES_CHAMPS_NEUTRES) - 1
    assert completion_qr.cles_du_manifeste(troue) == attendues


def test_la_ligne_du_manifeste_ne_ment_pas_tant_que_le_lot_n_est_pas_saisi():
    """« Le manifeste ne donne aucun champ » y serait FAUX, pas imprecis : il
    n'y a pas encore de lot dont il pourrait donner quoi que ce soit."""
    ligne = formulaire().ligne_du_manifeste()
    assert ligne == completion_qr.MANIFESTE_EN_ATTENTE.format(
        combien=len(scan_corrections.CHAMPS_NEUTRES_DU_LOT))
    assert completion_qr.MANIFESTE_SANS_CHAMP not in ligne


# ---------------------------------------------------------------------------
# AC 7.4 -- la coherence avec les pages deja lues du meme lot
# ---------------------------------------------------------------------------

def test_le_TOTAL_annonce_par_les_pages_lues_contredit_la_saisie():
    """AC 7.4, verbatim : « une "page 4 sur 4" declaree alors que trois pages
    annoncent un total de 6 est une contradiction visible sans aucune image »."""
    lues = trois_pages_lues(total=6, occupee=2)
    constat = completion_qr.verifier_la_coherence(
        4, pages_lues=lues, total_du_modele=4)
    assert constat.contredit
    assert "6" in constat.phrase and "4" in constat.phrase


def test_la_page_DEJA_DECLAREE_est_refusee_et_le_fichier_qui_l_occupe_est_NOMME():
    """« Deux pages 4 dans un lot sont une erreur de saisie, pas un second
    tirage » (`EXPERIENCE.md`).

    **La cible est au MILIEU des trois pages lues** : `verifier_la_coherence`
    boucle sur cette liste, et un `break` premature -- ou une boucle qui ne
    regarderait que le premier element -- passerait inapercu sur une fabrique
    a deux elements, ou « second » et « dernier » sont le meme rang.
    """
    lues = trois_pages_lues(total=4, occupee=2)
    parcourues = [page.page_imprimee for page in lues]
    assert parcourues == [1, 2, 4], parcourues        # la cible est au milieu
    constat = completion_qr.verifier_la_coherence(
        2, pages_lues=lues, total_du_modele=4)
    assert constat.contredit
    assert lues[1].nom_court in constat.phrase
    assert lues[0].nom_court not in constat.phrase
    assert lues[2].nom_court not in constat.phrase


def test_une_page_HORS_du_lot_est_refusee_dans_les_deux_sens():
    """La planche numerote a partir de 1 : `0` n'est pas une page, et `5` sort
    d'un lot de quatre. Les deux bornes, pas seulement la haute."""
    lues = trois_pages_lues(total=4, occupee=2)
    for numero in (0, 5):
        constat = completion_qr.verifier_la_coherence(
            numero, pages_lues=lues, total_du_modele=4)
        assert constat.contredit, numero
        assert str(numero) in constat.phrase


def test_les_DEUX_BORNES_du_lot_sont_ACCEPTEES():
    """La planche 1 et la planche N sont dans le lot, et ce sont exactement les
    deux valeurs qu'un decalage d'une unite fait basculer.

    Trois mutants y vivaient : `2 <= page`, `1 < page`, `page < total`. Aucun
    n'est visible sur un numero du milieu -- c'est pourquoi ce test-ci ne mesure
    QUE les bornes, et sur un lot dont elles sont libres.
    """
    # Les trois pages lues occupent 2, 3 et 4 : les DEUX bornes du lot, 1 et 6,
    # sont donc libres -- sans quoi le test mesurerait l'occupation et non les
    # bornes, et les trois mutants y survivraient encore.
    lues = trois_pages_lues(total=6, numeros=(2, 3, 4))
    for borne in (1, 6):
        constat = completion_qr.verifier_la_coherence(
            borne, pages_lues=lues, total_du_modele=6)
        assert not constat.contredit, (borne, constat)
    for hors in (0, 7):
        assert completion_qr.verifier_la_coherence(
            hors, pages_lues=lues, total_du_modele=6).contredit, hors


def test_les_phrases_de_la_coherence_sont_mesurees_MOT_POUR_MOT():
    """« Ce champ diverge » ne mesure rien : ce sont les valeurs INJECTEES dans
    la phrase qui portent le renseignement.

    Trois mutants y vivaient, chacun remplacant un argument de `format` par
    `None` -- le cardinal des pages lues, le numero de page occupee, le total du
    lot. Une assertion « le nombre est quelque part dans la phrase » les laissait
    tous les trois passer.
    """
    lues = trois_pages_lues(total=4, occupee=2)
    assert completion_qr.verifier_la_coherence(
        4, pages_lues=trois_pages_lues(total=6, occupee=2),
        total_du_modele=4).phrase == completion_qr.COHERENCE_TOTAL.format(
            pages=3, annonce=6, declare=4)
    assert completion_qr.verifier_la_coherence(
        2, pages_lues=lues, total_du_modele=4).phrase == \
        completion_qr.COHERENCE_OCCUPEE.format(page=2, fichier="page_02")
    assert completion_qr.verifier_la_coherence(
        9, pages_lues=lues, total_du_modele=4).phrase == \
        completion_qr.COHERENCE_HORS_LOT.format(page=9, total=4)


def test_DEUX_totaux_annonces_sont_dits_TOUS_LES_DEUX():
    """Deux planches du meme lot qui n'annoncent pas le meme cardinal : la
    contradiction est **entre elles**, et taire l'une des deux enverrait
    l'operateur corriger la mauvaise.

    Le joint « ou » n'est pas decoratif : il dit que les deux valeurs sont des
    annonces concurrentes, pas une plage.
    """
    lues = trois_pages_lues(total=4, occupee=2)
    divergente = dataclasses.replace(lues[1], page_count=6)
    melange = (lues[0], divergente, lues[2])
    constat = completion_qr.verifier_la_coherence(
        3, pages_lues=melange, total_du_modele=4)
    assert constat.phrase == completion_qr.COHERENCE_TOTAL.format(
        pages=3, annonce="4 ou 6", declare=4)


def test_une_page_lue_SANS_TOTAL_ANNONCE_n_est_NI_une_annonce_NI_une_trace():
    """Une planche du lot dont l'identite lisible a rendu le `page_index` mais
    **pas** le `page_count`.

    Le regime vient du coeur, il n'est pas invente ici : `scan_detection`
    construit une page refusee a identite **partielle**
    (`page_count=identity.get("page_count")`), `scan_previz` la transporte telle
    quelle (`page_count: int | None`) et `pages_lues_du_lot` l'admet -- elle a
    un `page_index`, c'est sa seule condition d'entree.

    Sans la garde `if page.page_count is not None`, `annonces` vaut
    `{4, None}` : la comparaison a `{total_du_modele}` echoue toujours, et
    `sorted()` leve `TypeError: '<' not supported between instances of
    'NoneType' and 'int'` -- une trace Python par-dessus une TUI plein ecran, la
    ou l'ecran doit rendre une phrase de contradiction.

    **Les deux moities sont mesurees**, parce qu'une seule ne dirait pas ce que
    la garde fait :

    * elle **n'invente pas** d'annonce -- le modele porte le total que les deux
      autres pages annoncent, et le constat reste favorable ;
    * elle **n'en efface pas** une -- le modele diverge, et la phrase nomme `4`
      seul, jamais `4 ou None`.
    """
    lues = trois_pages_lues(total=4, numeros=(1, 2, 4), totaux=(4, None, 4))
    # Point 2 bis, verifie sur la liste que `verifier_la_coherence` PARCOURT :
    # c'est ce tuple-la qu'elle boucle, et la page sans total y est au MILIEU,
    # ni premiere ni derniere.
    assert [page.page_count for page in lues] == [4, None, 4]
    assert [page.page_imprimee for page in lues] == [1, 2, 4]

    accord = completion_qr.verifier_la_coherence(
        3, pages_lues=lues, total_du_modele=4)
    assert accord.phrase == completion_qr.COHERENCE_OK.format(pages=3)
    assert not accord.contredit

    divergence = completion_qr.verifier_la_coherence(
        2, pages_lues=lues, total_du_modele=6)
    assert divergence.phrase == completion_qr.COHERENCE_TOTAL.format(
        pages=3, annonce=4, declare=6)
    assert divergence.contredit


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_coherence_rend_son_GLYPHE_d_etat_dans_les_deux_regimes(ascii_seul):
    """L'etat est une **cle** de la table des glyphes, jamais son dessin : c'est
    ce qui rend le repli ASCII automatique et la couleur posee par `peindre`.

    Six mutants vivaient sur ces trois cles (`complete`, `substitute`,
    `absent`) : aucun test ne les lisait, et aucun n'appelait `Coherence.ligne`,
    qui est pourtant le seul consommateur -- et qui **leve** sur une cle inconnue.
    """
    lues = trois_pages_lues(total=4, occupee=2)
    table = jetons.glyphes(ascii_seul)
    cas = {
        "complete": completion_qr.verifier_la_coherence(
            3, pages_lues=lues, total_du_modele=4),
        "absent": completion_qr.verifier_la_coherence(
            2, pages_lues=lues, total_du_modele=4),
        "substitute": completion_qr.verifier_la_coherence(
            3, pages_lues=(), total_du_modele=4),
        "neutre": completion_qr.verifier_la_coherence(
            None, pages_lues=lues, total_du_modele=4),
    }
    for attendu, constat in cas.items():
        assert constat.etat == attendu, (attendu, constat)
        assert constat.ligne(ascii_seul).startswith(table[attendu]), constat
    # Et la page LUE seule garde bien la cle du complet, pas celle du neutre.
    seule = completion_qr.verifier_la_coherence(
        3, pages_lues=lues[1:2], total_du_modele=4)
    assert seule.etat == "complete" and seule.phrase == \
        completion_qr.COHERENCE_UNE_PAGE


def test_une_page_LIBRE_du_lot_est_coherente():
    """Le cas nominal : la planche 3 manque, les trois autres sont lues."""
    lues = trois_pages_lues(total=4, occupee=2)
    constat = completion_qr.verifier_la_coherence(
        3, pages_lues=lues, total_du_modele=4)
    assert not constat.contredit
    assert "3" in constat.phrase          # trois pages deja lues


def test_la_coherence_ACCORDE_sa_phrase_au_nombre_de_pages_lues():
    """Zero, une, plusieurs : trois phrases, et la premiere n'est pas un
    acquittement.

    « Cohérent avec les 0 pages déjà lues » annoncerait une verification qui n'a
    rien verifie, sur le regime **nominal** de la pile d'une seule planche
    muette. Le cas a un element est le seul ou la faute d'accord se voie.
    """
    seule = trois_pages_lues()[1:2]
    assert completion_qr.verifier_la_coherence(
        3, pages_lues=(), total_du_modele=4).phrase == \
        completion_qr.COHERENCE_SANS_PAGE_LUE
    assert completion_qr.verifier_la_coherence(
        3, pages_lues=seule, total_du_modele=4).phrase == \
        completion_qr.COHERENCE_UNE_PAGE
    assert completion_qr.verifier_la_coherence(
        3, pages_lues=trois_pages_lues(), total_du_modele=4).phrase == \
        completion_qr.COHERENCE_OK.format(pages=3)


def test_la_coherence_ne_juge_RIEN_tant_que_la_page_n_est_pas_saisie():
    """Rendre `oui` avant la saisie vaudrait acquittement d'une verification qui
    n'a rien mesure."""
    constat = completion_qr.verifier_la_coherence(
        None, pages_lues=trois_pages_lues(), total_du_modele=4)
    assert not constat.contredit
    assert constat.phrase == completion_qr.COHERENCE_EN_ATTENTE


def test_les_pages_lues_sont_projetees_DANS_L_ORDRE_du_document():
    """La liste n'est jamais retriee : un banc doit pouvoir verifier le rang
    d'une cible sur la liste que ce code parcourt."""
    previz = scan_previz.scan_previz_from_json_dict(document_reel())
    lues = completion_qr.pages_lues_du_lot([previz], LOT_CIBLE)
    assert [p.read_rank for p in lues] == [
        p.read_rank for p in previz.pages if p.page_index is not None]


class _Document:
    """Un porteur de `pages`, et rien d'autre.

    `pages_lues_du_lot` ne lit que `document.pages` : lui donner un document de
    detection entier pour mesurer une boucle obligerait a fabriquer des
    compteurs et une empreinte coherents, c'est-a-dire a mettre en scene tout ce
    que le test ne mesure pas. Les **pages**, elles, sont de vrais
    `scan_previz.ScanPrevizPage`, derives d'une page reelle par `replace`.
    """

    def __init__(self, pages):
        self.pages = tuple(pages)


def trois_pages_de_document(lot_autre: str = "un-autre-lot"):
    """Trois pages, **la sautee AU MILIEU** : lue, muette, lue.

    C'est le point 2 bis, et il mord exactement ici : `pages_lues_du_lot` saute
    la page muette par un `continue`. Sur la fixture reelle -- deux pages, la
    muette en **derniere** -- un `break` rend le meme resultat qu'un `continue`,
    et le mutant survit. Avec la muette au milieu, un `break` perd la troisieme.

    La quatrieme page appartient a un **autre lot** : sans elle, la garde qui
    ecarte les pages d'un lot etranger n'est mesuree par rien.
    """
    previz = scan_previz.scan_previz_from_json_dict(document_reel())
    lue = next(p for p in previz.pages if p.page_index is not None)
    muette = next(p for p in previz.pages if p.page_index is None)
    # **Les DEUX pages sautees sont au milieu**, et aucune n'est en queue : le
    # `continue` de la page muette comme celui du lot etranger devient
    # observable, la ou une page sautee en derniere position rend `break` et
    # `continue` indiscernables.
    return _Document([
        dataclasses.replace(lue, read_rank=0, page_index=0, page_count=4,
                            source_path_relative="scans/scans-in/page_01.png"),
        dataclasses.replace(lue, read_rank=3, page_index=0, page_count=9,
                            decoded_lot_id=lot_autre,
                            source_path_relative="scans/scans-in/page_09.png"),
        dataclasses.replace(muette, read_rank=1),
        dataclasses.replace(lue, read_rank=2, page_index=2, page_count=4,
                            source_path_relative="scans/scans-in/page_03.png"),
    ])


def test_une_page_muette_AU_MILIEU_est_sautee_SANS_arreter_le_parcours():
    """Le mutant `continue` -> `break` de la vague 3, sur cette boucle-ci.

    Trois planches du lot, la muette au **milieu** : un `break` ferait
    disparaitre la troisieme -- « ni frames, ni mires, ni declaration », et 288
    tests restaient verts sur la 11.4b.
    """
    lues = completion_qr.pages_lues_du_lot([trois_pages_de_document()], LOT_CIBLE)
    assert [p.read_rank for p in lues] == [0, 2], lues


def test_une_page_d_un_AUTRE_lot_n_entre_pas_dans_les_pages_lues():
    """La garde du lot etranger est mesuree, pas supposee.

    Sans elle, une planche d'un autre lot du meme scan ferait annoncer un total
    de planches qui n'est pas celui du lot -- donc une contradiction inventee de
    toutes pieces sur la saisie de l'operateur.
    """
    document = trois_pages_de_document()
    assert [p.decoded_lot_id for p in document.pages][1] == "un-autre-lot"
    lues = completion_qr.pages_lues_du_lot([document], LOT_CIBLE)
    assert 3 not in {p.read_rank for p in lues}, lues


def trois_pages_dont_une_SANS_LOT_DECODE():
    """Trois planches du document de `LOT_CIBLE`, **celle sans lot decode au
    MILIEU**.

    C'est le meme regime de coeur que la page sans total : une planche refusee
    dont l'identite lisible n'a pas livre le `lot_id`. Elle est dans le document
    de son lot parce que le **tri du coeur** l'y a mise, pas parce que son QR
    l'a dite.

    Les trois pages sont distinguables -- trois rangs, trois numeros, trois
    fichiers -- et la cible n'est ni premiere ni derniere : un `break` sur elle
    perdrait la troisieme, un `continue` la laisserait dehors, et les deux
    fautes se voient.
    """
    previz = scan_previz.scan_previz_from_json_dict(document_reel())
    lue = next(p for p in previz.pages if p.page_index is not None)
    return _Document([
        dataclasses.replace(lue, read_rank=0, page_index=0, page_count=4,
                            source_path_relative="scans/scans-in/page_01.png"),
        dataclasses.replace(lue, read_rank=5, page_index=1, page_count=4,
                            decoded_lot_id=None,
                            source_path_relative="scans/scans-in/page_02.png"),
        dataclasses.replace(lue, read_rank=2, page_index=2, page_count=4,
                            source_path_relative="scans/scans-in/page_03.png"),
    ])


def test_une_page_SANS_LOT_DECODE_entre_dans_les_pages_lues_de_SON_document():
    """La moitie de la garde du lot qui **admet**, et rien ne la mesurait.

    `test_une_page_d_un_AUTRE_lot_n_entre_pas_dans_les_pages_lues` mesure la
    moitie qui **exclut**. Retirer `page.decoded_lot_id is not None and`
    laissait les 3298 tests de `tests/unit/tui/` verts : on ne savait donc pas,
    du banc, si l'admission etait voulue ou accidentelle.

    Elle est voulue. Une planche refusee dont le QR n'a pas livre le lot est
    **quand meme** une planche de ce lot -- c'est le tri du coeur qui l'a mise
    dans ce document-la --, et l'ecarter ferait annoncer a l'operateur moins de
    pages lues qu'il n'y en a : une pagination declaree libre alors qu'une
    feuille l'occupe deja, c'est-a-dire le refus qui ne vient pas.

    **Ce test mesure l'admission dans le document du lot vise, et rien
    d'autre.** Que la meme clause admette aussi une page sans lot decode venue
    du document d'un **autre** lot -- les documents sont aplatis avant la boucle
    -- est un defaut distinct, verse a `deferred-work.md` plutot que corrige
    ici : le fermer demanderait de lire le lot du document, donc de changer un
    comportement, ce qui n'est pas une fermeture de mesure.
    """
    document = trois_pages_dont_une_SANS_LOT_DECODE()
    # Point 2 bis, verifie sur la liste que `pages_lues_du_lot` PARCOURT --
    # `document.pages`, jamais l'ordre que la fabrique croit ecrire.
    assert [page.decoded_lot_id for page in document.pages] == [
        LOT_CIBLE, None, LOT_CIBLE]

    lues = completion_qr.pages_lues_du_lot([document], LOT_CIBLE)
    assert [page.read_rank for page in lues] == [0, 5, 2], lues
    assert [page.page_imprimee for page in lues] == [1, 2, 3]
    assert [page.nom_court for page in lues] == [
        "page_01", "page_02", "page_03"]


def test_chaque_page_lue_est_projetee_CHAMP_PAR_CHAMP():
    """Les quatre champs de `PageLue` viennent de la page, et de la bonne.

    Une assertion sur les seuls rangs laisserait passer un `page_index` pris a
    `None` ou un fichier pris a la page voisine -- la famille d'erreur
    d'appariement que la regle des fabriques existe pour attraper, et qui ne se
    voit jamais a l'oeil.
    """
    lues = completion_qr.pages_lues_du_lot([trois_pages_de_document()], LOT_CIBLE)
    assert lues == (
        completion_qr.PageLue(read_rank=0, page_index=0, page_count=4,
                              fichier="scans/scans-in/page_01.png"),
        completion_qr.PageLue(read_rank=2, page_index=2, page_count=4,
                              fichier="scans/scans-in/page_03.png"),
    )
    assert [p.page_imprimee for p in lues] == [1, 3]
    assert [p.nom_court for p in lues] == ["page_01", "page_03"]


def test_une_page_SANS_page_index_n_entre_pas_dans_les_pages_lues():
    """Elle n'a rien a dire sur la pagination, et l'y compter ferait annoncer
    une planche que personne n'a lue -- c'est justement la planche muette."""
    previz = scan_previz.scan_previz_from_json_dict(document_reel())
    muettes = [p for p in previz.pages if p.page_index is None]
    assert muettes, "la fixture reelle porte bien une planche muette"
    lues = completion_qr.pages_lues_du_lot([previz], LOT_CIBLE)
    assert {p.read_rank for p in lues}.isdisjoint({p.read_rank for p in muettes})


# ---------------------------------------------------------------------------
# AC 7.6 -- `F1` dit OU le champ se lit, il ne paraphrase pas son libelle
# ---------------------------------------------------------------------------

#: Les trois zones de la planche imprimee ou une valeur se lit. Ce ne sont pas
#: des mots choisis pour ce banc : ce sont les trois familles de zones que
#: `pdf_composition` pose sur la page -- l'entete, le pied (bloc d'identite et
#: colonnes techniques), et les etiquettes sous les emplacements de frame.
ZONES_DE_LA_PLANCHE = ("En-tête", "Pied technique", "Sous les", "Sous la")


@pytest.mark.parametrize("cle", completion_qr.CHAMPS_SAISIS)
def test_F1_dit_OU_le_champ_SE_LIT_sur_la_feuille(cle):
    """AC 7.6, `EPIC11-ARB-14` : « une aide qui paraphrase le libelle est un
    defaut ».

    La mesure porte sur ce que l'aide **nomme** : une zone de la planche
    imprimee. Elle ne porte pas sur l'absence du libelle -- l'aide de la
    pagination cite « page N/M » parce que c'est le texte imprime, et le lui
    reprocher rendrait l'aide moins precise, pas plus.
    """
    aide = completion_qr.OU_LIRE_LE_CHAMP[cle]
    assert aide != completion_qr.LIBELLES[cle]
    assert any(aide.startswith(zone) for zone in ZONES_DE_LA_PLANCHE), aide


def test_les_TROIS_zones_de_la_planche_sont_TOUTES_employees():
    """Volet symetrique : si les six aides nommaient la meme zone, le test
    ci-dessus resterait vert en ne mesurant plus rien.

    Les six champs se lisent bien a trois endroits differents -- deux a
    l'entete, un au pied technique, trois sous les images --, et c'est ce qui
    fait de cette aide un renseignement plutot qu'une formule.
    """
    zones = {zone for cle in completion_qr.CHAMPS_SAISIS
             for zone in ZONES_DE_LA_PLANCHE
             if completion_qr.OU_LIRE_LE_CHAMP[cle].startswith(zone)}
    assert zones == set(ZONES_DE_LA_PLANCHE), sorted(zones)


def test_l_aide_de_la_ligne_d_OUVERTURE_existe_aussi():
    """Elle n'est pas un champ, mais `F1` ne doit pas y devenir muette : une
    touche annoncee qui ne fait rien est indistinguable d'un clavier casse."""
    aide = completion_qr.OU_LIRE_LE_CHAMP[completion_qr.ACTION_OUVRIR]
    assert aide and aide != completion_qr.LIBELLES[completion_qr.ACTION_OUVRIR]
    assert set(completion_qr.OU_LIRE_LE_CHAMP) == set(
        completion_qr.LIGNES_DU_FORMULAIRE)


def test_F1_REMPLACE_la_consigne_et_l_ecran_ne_gagne_aucune_ligne(banc):
    """La grille 80 x 24 ne bouge pas : c'est le motif de la forme de `F1`."""
    e = ecran()

    async def scenario(_pilote):
        avant = list(e.lignes())
        e.traiter("f1")
        apres = list(e.lignes())
        return avant, apres

    avant, apres = _monte(_app(e), scenario, banc)
    assert len(avant) == len(apres)
    divergents = [rang for rang, (a, b) in enumerate(zip(avant, apres)) if a != b]
    assert len(divergents) == 1, [avant[r] for r in divergents]
    assert completion_qr.CONSIGNE in avant[divergents[0]]
    assert completion_qr.OU_LIRE_LE_CHAMP[completion_qr.CHAMP_LOT] in \
        apres[divergents[0]]


def test_l_aide_TOMBE_au_changement_de_ligne():
    """Elle porte sur le champ courant : la laisser en place la ferait mentir
    des la ligne suivante."""
    forme = formulaire()
    forme.basculer_l_aide()
    assert forme.aide
    forme.avancer()
    assert not forme.aide
    assert forme.tete() == completion_qr.CONSIGNE


def test_la_cle_imprimee_est_DANS_l_aide_des_champs_qui_en_ont_une():
    """L'aide nomme la mention a chercher au pied, **lue de la table** : c'est ce
    qui evite la table de correspondance de tete que la note 12 reproche."""
    for cle, courte in completion_qr.CLE_IMPRIMEE.items():
        assert courte in completion_qr.OU_LIRE_LE_CHAMP[cle], cle


# ===========================================================================
# E4 / AC 7.5 -- `poser_les_identites`, et RIEN D'AUTRE n'est ecrit
# ===========================================================================

def test_la_correction_ne_change_du_document_QUE_la_couche_manual_corrections():
    """AC 7.5, en **ensemble exact** de chemins divergents.

    « Ce champ diverge » ne mesure rien ; « l'ensemble des chemins qui divergent
    est exactement {X} » mesure l'exception ET son unicite. Et c'est ce qui
    garde `fingerprints.detection` intacte -- la re-signer renommerait tous les
    noeuds du chutier de la GUI a la premiere correction (`EPIC7-ARB-95`).
    """
    avant = document_reel()
    identite = formulaire_rempli().identite()
    apres = completion_qr.poser_la_correction(copy.deepcopy(avant), identite)
    divergents = {cle for cle in set(avant) | set(apres)
                  if avant.get(cle) != apres.get(cle)}
    assert divergents == {scan_corrections.CLE_DOCUMENT}


def test_les_identites_DEJA_POSEES_sont_conservees_la_neuve_au_MILIEU():
    """`poser_les_identites` prend la liste ENTIERE et remplace celle du
    document : lui passer la seule identite qu'on vient de saisir effacerait
    celles des planches corrigees avant, sans un mot.

    **Trois identites, la neuve au milieu** : c'est une boucle qui les
    reconstruit, et une fabrique a deux elements ne separerait pas « second » de
    « dernier ».
    """
    document = document_reel()
    voisines = [
        scan_corrections.IdentiteManuelle(
            read_rank=rang, lot_id=LOT_CIBLE,
            template_id="tpl-a4-paysage-4f-v2", frames_per_page=4,
            page_index=rang, first_frame_timecode="00:00:0%d:00" % rang,
            last_frame_timecode="00:00:0%d:03" % rang)
        for rang in (0, 4)]
    document = scan_corrections.poser_les_identites(document, voisines)

    neuve = formulaire_rempli(**{completion_qr.CHAMP_PAGE: "3"}).identite()
    assert neuve.read_rank == 1                 # entre 0 et 4 : au milieu
    corrige = completion_qr.poser_la_correction(document, neuve)
    posees = scan_corrections.lire_les_identites(corrige)
    assert set(posees) == {0, 1, 4}
    assert posees[1].page_index == 2
    assert posees[0].page_index == 0 and posees[4].page_index == 4


def test_reprendre_la_saisie_d_une_planche_REMPLACE_sa_correction():
    """Cas nominal de cet ecran : on repasse sur une planche pour corriger une
    faute de frappe. `poser_les_identites` refuse deux entrees du meme rang, donc
    la reprise doit remplacer plutot qu'ajouter."""
    document = document_reel()
    premiere = formulaire_rempli(**{completion_qr.CHAMP_PAGE: "1"}).identite()
    document = completion_qr.poser_la_correction(document, premiere)
    seconde = formulaire_rempli(**{completion_qr.CHAMP_PAGE: "3"}).identite()
    corrige = completion_qr.poser_la_correction(document, seconde)
    posees = scan_corrections.lire_les_identites(corrige)
    assert set(posees) == {seconde.read_rank}
    assert posees[seconde.read_rank].page_index == 2


def _empreintes(racine: Path) -> dict[str, tuple]:
    """Inode, taille et `st_mtime_ns` de chaque fichier sous `racine`.

    **Jamais un condensat** : la fixture est deterministe, donc une reecriture
    rend exactement les memes octets et un sha256 declarerait « intact » un
    fichier qui vient d'etre reecrit (CLAUDE.md, vague 3).
    """
    return {
        str(chemin.relative_to(racine)):
            (chemin.stat().st_ino, chemin.stat().st_size,
             chemin.stat().st_mtime_ns)
        for chemin in sorted(racine.rglob("*")) if chemin.is_file()
    }


def _projet_temoin(tmp_path: Path) -> tuple[Path, Path]:
    """Un projet avec son document de detection, son manifeste, et des TEMOINS.

    Les temoins sont deposes **dans le dossier vise** -- `output-frames/` -- et
    ils sont **trois**, pour que la mesure d'un dossier intact ne repose pas sur
    un element unique.
    """
    racine = tmp_path / "projet"
    (racine / "output-frames" / "lot").mkdir(parents=True)
    for rang in range(3):
        (racine / "output-frames" / "lot" / f"temoin_{rang}.tiff").write_bytes(
            b"temoin-" + str(rang).encode())
    (racine / "project.json").write_text(
        json.dumps(manifeste_du_projet()), encoding="utf-8")
    document = racine / "detection.json"
    scan_corrections.ecrire(document, document_reel())
    return racine, document


def test_ecrire_la_correction_ne_touche_EXACTEMENT_qu_UN_fichier(tmp_path):
    """AC 7.5 : « ni frame, ni manifest ».

    Mesure aux **inodes** et au `st_mtime_ns`, plus trois temoins dans
    `output-frames/`. L'ensemble des chemins qui changent est asserte
    **exactement** {le document de detection} : une assertion « le manifeste n'a
    pas change » laisserait passer une frame ecrite a cote.
    """
    racine, document = _projet_temoin(tmp_path)
    avant = _empreintes(racine)
    identite = formulaire_rempli().identite()
    completion_qr.ecrire_la_correction(
        document, json.loads(document.read_text(encoding="utf-8")), identite)
    apres = _empreintes(racine)

    assert set(avant) == set(apres), (set(avant) ^ set(apres))
    divergents = {chemin for chemin in avant if avant[chemin] != apres[chemin]}
    assert divergents == {"detection.json"}, divergents


def test_la_mesure_des_fichiers_INTACTS_mord(tmp_path):
    """Volet symetrique, et il n'est pas decoratif.

    Sans lui, `_empreintes` pourrait ne rien voir bouger et le test ci-dessus
    serait vert en ne mesurant rien. On reecrit un temoin -- **celui du
    milieu** -- avec **exactement les memes octets** : un condensat resterait
    identique, l'inode change.
    """
    racine, _document = _projet_temoin(tmp_path)
    avant = _empreintes(racine)
    temoin = racine / "output-frames" / "lot" / "temoin_1.tiff"
    octets = temoin.read_bytes()
    provisoire = temoin.with_suffix(".tmp")
    provisoire.write_bytes(octets)
    provisoire.replace(temoin)
    assert temoin.read_bytes() == octets      # memes octets, autre inode
    apres = _empreintes(racine)
    divergents = {chemin for chemin in avant if avant[chemin] != apres[chemin]}
    assert divergents == {"output-frames/lot/temoin_1.tiff"}, divergents


def test_le_document_ecrit_se_RELIT_par_le_lecteur_du_coeur(tmp_path):
    """Ecrire par `scan_corrections.ecrire` n'est pas un detail : c'est le
    serialiseur canonique et l'ecrivain atomique du depot. Un document que le
    lecteur du coeur refuserait serait une correction perdue."""
    racine, document = _projet_temoin(tmp_path)
    identite = formulaire_rempli().identite()
    completion_qr.ecrire_la_correction(
        document, json.loads(document.read_text(encoding="utf-8")), identite)
    relu = json.loads(document.read_text(encoding="utf-8"))
    posees = scan_corrections.lire_les_identites(relu)
    assert set(posees) == {identite.read_rank}
    # Et le document reste lisible par le lecteur normatif de la previz.
    assert scan_previz.scan_previz_from_json_dict(relu).subject.lot_id == LOT_CIBLE


# ===========================================================================
# E5 / AC 7.7 et 7.8 -- l'ouverture du scan, et le lien qui n'est qu'un
# supplement
# ===========================================================================

LANCEURS = ("run", "call", "check_call", "check_output", "Popen")


def _sites_de_lancement(chemin: Path) -> list[str]:
    """Les references a un lanceur de `subprocess`, lues a l'AST.

    Sur les **references** et non sur les appels : `execution.py` passe
    `subprocess.run` par valeur, pour que les bancs puissent l'observer sans
    monkeypatch. Un banc qui chercherait un `Call` y trouverait zero site et
    serait vert sur un module qui en porterait dix.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    return [f"{chemin.name}:{noeud.attr}" for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Attribute)
            and isinstance(noeud.value, ast.Name)
            and noeud.value.id == "subprocess" and noeud.attr in LANCEURS]


def test_le_paquet_TUI_n_a_QU_UN_SEUL_site_d_appel_systeme(paquet_tui):
    """AC 7.7 : « l'appel systeme est isole en un seul point ».

    L'ouverture d'un **fichier** dans la visionneuse ne fabrique pas un second
    site : elle partage le lancement de l'ouverture d'un **dossier**. La
    frontiere est une **egalite** sur le paquet entier -- un second site, ou un
    site dans un autre module, rougit.
    """
    sites = [site for chemin in sorted(paquet_tui.rglob("*.py"))
             for site in _sites_de_lancement(chemin)]
    assert sites == ["execution.py:run"], sites


def test_la_mesure_du_SITE_UNIQUE_mord(tmp_path):
    """Volet symetrique : la lecture AST voit bien un second lanceur."""
    faux = tmp_path / "faux.py"
    faux.write_text("import subprocess\n\n\n"
                    "def a(c):\n    return subprocess.run(c)\n\n\n"
                    "def b(c):\n    return subprocess.Popen(c)\n",
                    encoding="utf-8")
    assert _sites_de_lancement(faux) == ["faux.py:run", "faux.py:Popen"]


def test_l_ecran_de_completion_ne_reference_AUCUN_lanceur():
    """Il **demande** l'ouverture, il ne la lance pas : le module ne connait ni
    `subprocess`, ni `os.system`, ni `os.startfile`."""
    noms = identifiants(Path(completion_qr.__file__))
    assert {"subprocess", "Popen", "system", "startfile", "execv"} & noms == set()
    assert "ouvrir_dans_la_visionneuse_du_systeme" in noms


def test_ce_qui_est_LANCE_est_un_OUVREUR_DE_BUREAU_et_le_CHEMIN_du_scan(tmp_path):
    """AC 7.7 : l'appel systeme « ne sert JAMAIS a appeler le coeur ».

    L'argv reel est mesure : l'ouvreur du systeme, puis le chemin. Rien d'autre
    -- ni interpreteur, ni module du depot, ni commande `mmu`.
    """
    scan = tmp_path / "planche_03.tiff"
    scan.write_bytes(b"tiff")
    vus = []

    def lancer(argv, **_kw):
        vus.append(list(argv))
        return subprocess.CompletedProcess(argv, 0)

    for systeme, attendu in (("darwin", "open"), ("win32", "explorer"),
                             ("linux", "xdg-open")):
        vus.clear()
        execution.ouvrir_dans_la_visionneuse_du_systeme(
            scan, systeme=systeme, lancer=lancer)
        assert vus == [[attendu, str(scan)]], (systeme, vus)


@pytest.mark.parametrize("panne", [FileNotFoundError("aucun binaire"),
                                   PermissionError("interdit"),
                                   subprocess.TimeoutExpired("xdg-open", 10)])
def test_l_echec_de_l_ouverture_est_un_MESSAGE_et_JAMAIS_une_trace(tmp_path, panne):
    """AC 7.7, `EPIC11-ARB-42` verbatim : « son echec (aucune visionneuse
    associee) doit etre un message, jamais une trace ».

    Un conteneur sans bureau est le regime **nominal** des bancs : laisser
    remonter l'exception ferait tomber la TUI sur une suite dont tout l'objet est
    de ne plus etre muette.
    """
    scan = tmp_path / "planche_03.tiff"
    scan.write_bytes(b"tiff")

    def lancer(_argv, **_kw):
        raise panne

    phrase = execution.ouvrir_dans_la_visionneuse_du_systeme(
        scan, systeme="linux", lancer=lancer)
    assert str(scan) in phrase
    assert "Traceback" not in phrase


def test_un_scan_DISPARU_se_dit_AVANT_l_appel(tmp_path):
    """Un `xdg-open` sur un chemin absent ouvre une erreur du systeme que la TUI
    ne verrait jamais passer : l'operateur lirait « rien ne s'est passe »."""
    absent = tmp_path / "parti.tiff"
    appels = []
    phrase = execution.ouvrir_dans_la_visionneuse_du_systeme(
        absent, systeme="linux", lancer=lambda *a, **k: appels.append(a))
    assert appels == []
    assert str(absent) in phrase
    # Et un DOSSIER n'est pas un fichier : la visionneuse ne l'ouvre pas.
    assert str(tmp_path) in execution.ouvrir_dans_la_visionneuse_du_systeme(
        tmp_path, systeme="linux", lancer=lambda *a, **k: appels.append(a))
    assert appels == []


def test_les_deux_ouvreurs_ne_partagent_AUCUNE_phrase(tmp_path):
    """« Ce dossier n'existe plus » sur un scan de planche enverrait l'operateur
    chercher un dossier. Trois phrases par ouvreur, et six en tout."""
    phrases = {execution.FAIT_DOSSIER_OUVERT, execution.MOTIF_SANS_EXPLORATEUR,
               execution.MOTIF_DOSSIER_ABSENT, execution.FAIT_FICHIER_OUVERT,
               execution.MOTIF_SANS_VISIONNEUSE, execution.MOTIF_FICHIER_ABSENT}
    assert len(phrases) == 6, sorted(phrases)


def test_le_GESTE_CLAVIER_ouvre_le_scan_et_il_SUFFIT_SEUL(banc, tmp_path):
    """AC 7.8 : « un test mesure que le geste clavier existe et suffit, terminal
    sans OSC 8 compris ».

    Le parcours est celui de l'operateur : six `Tab` amenent sur la ligne
    d'ouverture, `⏎` la declenche. Aucune lettre n'y est un raccourci
    (`EPIC11-ARB-68`), donc aucune souris n'est requise (`EPIC11-ARB-11`).
    """
    scan = tmp_path / "planche_03.tiff"
    scan.write_bytes(b"tiff")
    ouvertes = []
    e = ecran(chemin_du_scan=scan,
              ouvrir=lambda chemin: ouvertes.append(Path(chemin)) or "ouvert")

    async def scenario(_pilote):
        for _ in range(len(completion_qr.CHAMPS_SAISIS)):
            e.traiter("tab")
        assert e.formulaire.champ == completion_qr.ACTION_OUVRIR
        e.traiter("enter")
        return e.etat()

    etat = _monte(_app(e), scenario, banc, )
    assert ouvertes == [scan], ouvertes
    assert "ouvert" in etat


def test_le_geste_clavier_ouvre_AUSSI_sans_couleur_et_en_ASCII(banc, tmp_path):
    """Le regime **sans OSC 8** : `--sans-couleur` retire le lien, et le geste
    reste le seul chemin -- il n'a jamais dependu du lien."""
    scan = tmp_path / "planche_03.tiff"
    scan.write_bytes(b"tiff")
    ouvertes = []
    e = ecran(chemin_du_scan=scan,
              ouvrir=lambda chemin: ouvertes.append(Path(chemin)) or "ouvert")

    async def scenario(_pilote):
        for _ in range(len(completion_qr.CHAMPS_SAISIS)):
            e.traiter("tab")
        e.traiter("enter")
        return _texte(e)

    texte = _monte(_app(e, sans_couleur=True, ascii_seul=True), scenario, banc)
    assert ouvertes == [scan]
    assert str(scan) in texte or scan.name in texte


def _rendu_terminal(peint) -> str:
    from rich.console import Console

    console = Console(file=io.StringIO(), force_terminal=True, width=200,
                      legacy_windows=False, color_system="truecolor")
    console.print(peint, end="")
    return console.file.getvalue()


def test_le_lien_OSC_8_ne_coute_AUCUNE_COLONNE_et_le_texte_est_le_MEME(tmp_path):
    """AC 7.8 : « le lien est un supplement, jamais le chemin principal ».

    La sequence est posee par le **style**, donc hors du texte mesure : la
    largeur ne bouge pas d'une colonne, et un terminal qui ignore OSC 8 lit
    exactement la meme ligne. C'est ce qui rend la grille 80 x 24 insensible au
    lien.
    """
    lignes = ["  Ouvrir le scan   /tmp/planche_03.tiff", "  autre ligne"]
    sans = jetons.peindre(lignes)
    avec = jetons.peindre(lignes, liens={0: "file:///tmp/planche_03.tiff"})
    assert jetons.texte_affiche(sans) == jetons.texte_affiche(avec)
    assert jetons.colonnes(jetons.texte_affiche(avec)) == \
        jetons.colonnes(jetons.texte_affiche(sans))
    # Et la sequence est bien la, sur la ligne visee et sur elle seule.
    rendu = _rendu_terminal(avec)
    assert "\x1b]8;" in rendu
    assert "file:///tmp/planche_03.tiff" in rendu
    assert "\x1b]8;" not in _rendu_terminal(sans)


def test_le_repli_SANS_COULEUR_retire_le_lien_et_garde_le_texte():
    """C'est le repli des terminaux qui ne savent rien poser, et c'est le regime
    exact qu'un banc doit pouvoir mesurer."""
    lignes = ["  Ouvrir le scan   /tmp/planche_03.tiff"]
    peint = jetons.peindre(lignes, sans_couleur=True,
                           liens={0: "file:///tmp/planche_03.tiff"})
    assert jetons.texte_affiche(peint) == lignes[0]
    assert "\x1b]8;" not in _rendu_terminal(peint)


def test_un_rang_de_lien_HORS_BORNES_est_refuse():
    """Meme refus dur que pour `etats` et `lignes_du_curseur` : un rang qui ne
    designe aucune ligne est une erreur d'appariement, la famille de defauts que
    la regle des fabriques existe pour attraper."""
    with pytest.raises(IndexError):
        jetons.peindre(["une", "deux"], liens={7: "file:///x"})


def test_le_lien_est_pose_sur_LA_LIGNE_D_OUVERTURE_et_sur_elle_seule(banc,
                                                                     tmp_path):
    """Le rang est **derive** du rendu, jamais recompte : deux comptes de lignes
    divergeraient a la premiere ligne ajoutee, et le lien se poserait alors sur
    une autre ligne sans que rien ne le dise."""
    scan = tmp_path / "planche_03.tiff"
    scan.write_bytes(b"tiff")
    e = ecran(chemin_du_scan=scan)

    async def scenario(_pilote):
        return e.rang_du_lien(), list(e.lignes()), e.cible_du_lien()

    rang, lignes, cible = _monte(_app(e), scenario, banc)
    assert completion_qr.LIBELLES[completion_qr.ACTION_OUVRIR] in lignes[rang]
    autres = [r for r, l in enumerate(lignes)
              if completion_qr.LIBELLES[completion_qr.ACTION_OUVRIR] in l]
    assert autres == [rang], autres
    assert cible == scan.absolute().as_uri()


def test_sans_chemin_de_scan_il_n_y_a_NI_lien_NI_rang(banc):
    """Une planche dont on ne connait pas le chemin absolu n'offre pas de lien,
    et n'en offre pas un qui pointerait a cote."""
    e = ecran()

    async def scenario(_pilote):
        return e.rang_du_lien(), e.cible_du_lien()

    assert _monte(_app(e), scenario, banc) == (None, None)


# ===========================================================================
# E6 / AC 7.9 -- QUELLE page a recu la correction
# ===========================================================================

def trois_planches_muettes() -> tuple[PageMuette, ...]:
    """Trois planches muettes du meme lot, **la fautive au MILIEU**.

    Point 2 bis : `page_suivante_a_completer` **boucle** sur cette liste, et une
    fabrique a deux elements dont la cible est en second la placerait aussi en
    dernier -- un `break` premature y serait indiscernable d'un `continue`.
    """
    return tuple(
        PageMuette(read_rank=rang, fichier=f"scans/scans-in/page_{rang:02d}.png",
                   code="QR_NON_DECODE", lot_id=LOT_CIBLE)
        for rang in (0, 1, 4))


def test_la_correction_va_sur_LA_PAGE_VISEE_et_sur_elle_seule():
    """AC 7.9. « Une correction appliquee a la mauvaise page produit exactement
    le meme succes apparent, donc le test mesure QUELLE page a recu la
    correction. »

    La cible est la planche du **milieu** des trois, et l'ensemble des rangs
    corriges est asserte **exactement** : une assertion « la page 1 est
    corrigee » laisserait passer une correction posee en plus sur une autre.
    """
    muettes = trois_planches_muettes()
    assert [p.read_rank for p in muettes] == [0, 1, 4]
    cible = muettes[1]
    identite = formulaire(planche=cible, **SAISIE_VALIDE).identite()
    corrige = completion_qr.poser_la_correction(document_reel(), identite)
    posees = scan_corrections.lire_les_identites(corrige)
    assert set(posees) == {cible.read_rank}
    assert posees[cible.read_rank].lot_id == LOT_CIBLE


def test_une_correction_posee_sur_la_MAUVAISE_page_reussit_AUSSI():
    """Le volet qui prouve que le test ci-dessus mesure quelque chose.

    Poser la correction sur la premiere planche au lieu de celle du milieu
    **reussit** : rien dans le document ne le signale. C'est exactement pourquoi
    l'AC 7.9 exige de mesurer le rang, et pas seulement le succes.
    """
    muettes = trois_planches_muettes()
    identite = formulaire(planche=muettes[0], **SAISIE_VALIDE).identite()
    corrige = completion_qr.poser_la_correction(document_reel(), identite)
    posees = scan_corrections.lire_les_identites(corrige)
    assert set(posees) == {muettes[0].read_rank}   # succes, sur la mauvaise


def test_la_page_SUIVANTE_a_completer_est_celle_du_MILIEU_puis_la_derniere():
    """Note 10 d'Egan (`EPIC11-ARB-101`) : « une page a la fois », puis on revient
    au rapport.

    L'ordre est **celui du rapport**, jamais retrie : le refaire donnerait a
    l'operateur un enchainement different de celui qu'on vient de lui montrer.
    """
    muettes = trois_planches_muettes()
    assert completion_qr.page_suivante_a_completer(muettes) is muettes[0]
    assert completion_qr.page_suivante_a_completer(muettes, {0}) is muettes[1]
    assert completion_qr.page_suivante_a_completer(muettes, {0, 1}) is muettes[2]


def test_quand_TOUTES_les_planches_sont_posees_on_revient_au_rapport():
    """`None` veut dire « reviens au rapport », et le rapport dira lui-meme s'il
    est devenu complet -- ce n'est pas a cette fonction de le decider.

    Retrancher ici une page de la liste ecrirait une seconde regle de completude
    a cote de `scan_detect.completude_des_planches`, sa seule derivation du
    depot : les deux divergeraient au premier lot dont il manque une planche
    JAMAIS SCANNEE, qu'aucune saisie ne rattrape.
    """
    muettes = trois_planches_muettes()
    assert completion_qr.page_suivante_a_completer(
        muettes, {p.read_rank for p in muettes}) is None
    assert completion_qr.page_suivante_a_completer(()) is None


def test_une_planche_deja_posee_est_SAUTEE_sans_arreter_le_parcours():
    """Le mutant `continue` -> `break` de la vague 3, sur cette boucle-ci.

    Avec la seule planche du **milieu** deja posee, un `break` rendrait `None`
    -- « il n'y a plus rien a completer » -- alors que deux planches attendent.
    """
    muettes = trois_planches_muettes()
    assert completion_qr.page_suivante_a_completer(muettes, {0}) is muettes[1]
    suivante = completion_qr.page_suivante_a_completer(muettes, {0, 1})
    assert suivante is muettes[2] and suivante is not None


# ===========================================================================
# Le clavier, la grille, et les deux arbitrages du soir
# ===========================================================================

@pytest.mark.parametrize("caractere", ["q", "o", "m", "d", "r"])
def test_AUCUNE_lettre_n_est_un_raccourci_dans_un_champ_de_saisie(caractere):
    """`EPIC11-ARB-68` : « sans exception et sans ordre de priorite a maintenir ».

    Les cinq lettres mesurees sont celles qui sont des raccourcis **ailleurs**
    dans la TUI : `q` quitte, `o` etait le raccourci que `EPIC11-ARB-42`
    proposait pour cet ecran meme, `m` celui que la maquette de `E3-1b`
    proposait, `r` et `d` ceux d'`EPIC11-ARB-63`. Toutes s'ecrivent ici.
    """
    forme = formulaire()
    assert forme.frapper(caractere) is True
    assert forme.valeurs[completion_qr.CHAMP_LOT] == caractere


def test_la_ligne_d_ouverture_n_absorbe_AUCUNE_frappe():
    """Elle n'est pas un champ : y ecrire des lettres serait un champ fantome."""
    forme = formulaire()
    forme.champ = completion_qr.ACTION_OUVRIR
    assert forme.frapper("x") is False
    assert forme.effacer() is False
    assert all(valeur == "" for valeur in forme.valeurs.values())


def test_Tab_parcourt_les_SEPT_lignes_EN_BOUCLE():
    """Sept lignes, et la boucle : une borne obligerait a une seconde touche pour
    revenir en arriere, ce qui rendrait la ligne d'ouverture atteignable dans un
    sens seulement."""
    forme = formulaire()
    vus = [forme.champ]
    for _ in range(len(completion_qr.LIGNES_DU_FORMULAIRE)):
        forme.avancer()
        vus.append(forme.champ)
    assert vus[:-1] == list(completion_qr.LIGNES_DU_FORMULAIRE)
    assert vus[-1] == completion_qr.LIGNES_DU_FORMULAIRE[0]
    forme.avancer(-1)
    assert forme.champ == completion_qr.LIGNES_DU_FORMULAIRE[-1]


def test_l_action_principale_est_INACCESSIBLE_tant_qu_un_champ_manque(banc):
    """`DESIGN.md` section 7.3, et elle DIT pourquoi : une touche annoncee qui ne
    fait rien et ne dit rien est indistinguable d'un clavier casse."""
    poses = []
    e = ecran(poser=poses.append)
    e.formulaire.valeurs.update(SAISIE_VALIDE)
    e.formulaire.valeurs[completion_qr.CHAMP_TC_DERNIER] = ""

    async def scenario(_pilote):
        e.traiter("enter")
        return e.etat()

    etat = _monte(_app(e), scenario, banc)
    assert poses == []
    assert "5" in etat and "6" in etat        # 5 champs sur 6 saisis


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_mention_SUR_LE_TOTAL_ne_vit_que_sur_la_ligne_PAGE(banc, ascii_seul):
    """« Page 3 sur 4 » : le cardinal est **lu du modele**, et il ne s'affiche
    que la, et que quand un numero est saisi.

    Quatre mutants y vivaient -- la condition passee en `or`, en `!=`, en `is
    None`, et le total remplace par `None`. Aucun test ne lisait cette colonne.
    """
    e = ecran()
    e.formulaire.valeurs.update(SAISIE_VALIDE)

    async def scenario(_pilote):
        return {cle: e.mention_du_champ(cle)
                for cle in completion_qr.LIGNES_DU_FORMULAIRE}

    mentions = _monte(_app(e, ascii_seul=ascii_seul), scenario, banc)
    total = e.formulaire.total_du_lot
    assert isinstance(total, int) and total >= 1, total
    assert mentions[completion_qr.CHAMP_PAGE] == (
        completion_qr.MENTION_SUR_LE_TOTAL.format(total=total)
        + completion_qr.SEPARATEUR_DE_MENTION
        + completion_qr.CLE_IMPRIMEE[completion_qr.CHAMP_PAGE])
    # Aucune autre ligne ne porte « sur N », et l'ouverture n'a pas de mention.
    autres = {cle: valeur for cle, valeur in mentions.items()
              if cle != completion_qr.CHAMP_PAGE}
    assert all("sur " not in valeur for valeur in autres.values()), autres
    assert mentions[completion_qr.ACTION_OUVRIR] == ""


def test_sans_lot_connu_la_ligne_PAGE_ne_montre_AUCUN_total(banc):
    """Jamais `0`, jamais `--`, jamais une valeur devinee (`DESIGN.md` 3) : un
    total invente ferait declarer une page hors du lot a tort."""
    e = ecran()
    e.formulaire.valeurs.update(SAISIE_VALIDE)
    e.formulaire.valeurs[completion_qr.CHAMP_LOT] = "lot-inconnu"

    async def scenario(_pilote):
        return e.mention_du_champ(completion_qr.CHAMP_PAGE)

    mention = _monte(_app(e), scenario, banc)
    assert e.formulaire.total_du_lot is None
    assert mention == completion_qr.CLE_IMPRIMEE[completion_qr.CHAMP_PAGE]


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_clavier_rend_TRAITE_sur_ce_qu_il_traite_et_NON_sur_le_reste(
        banc, ascii_seul):
    """La valeur de retour de `traiter` commande `evenement.stop()` **et** le
    redessin : la rendre a l'envers rend l'ecran inerte ou vole la touche a
    l'application.

    Onze mutants vivaient sur ce chemin -- `backspace` compare a l'envers ou en
    majuscules, le `and` de la frappe passe en `or` (qui leve sur une touche sans
    caractere), le caractere remplace par `None`, et les deux retours inverses.
    """
    e = ecran()

    async def scenario(_pilote):
        vus = {}
        vus["frappe"] = e.traiter("l", "l")
        vus["apres_frappe"] = e.formulaire.valeurs[completion_qr.CHAMP_LOT]
        vus["backspace"] = e.traiter("backspace")
        vus["apres_backspace"] = e.formulaire.valeurs[completion_qr.CHAMP_LOT]
        # Une touche SANS caractere : `and` la laisse passer, `or` y leve.
        vus["inconnue"] = e.traiter("ctrl+underscore", None)
        vus["tab"] = e.traiter("tab")
        vus["f1"] = e.traiter("f1")
        return vus

    vus = _monte(_app(e, ascii_seul=ascii_seul), scenario, banc)
    assert vus["frappe"] is True and vus["apres_frappe"] == "l"
    assert vus["backspace"] is True and vus["apres_backspace"] == ""
    assert vus["inconnue"] is False
    assert vus["tab"] is True and vus["f1"] is True


def test_une_frappe_EFFACE_le_dernier_message_de_la_ligne_d_etat(banc):
    """La ligne d'etat porte une mesure de l'ecran COURANT : un motif de refus
    laisse en place apres une correction dirait l'etat d'avant la frappe."""
    e = ecran()
    e.formulaire.valeurs.update(SAISIE_VALIDE)
    e.formulaire.valeurs[completion_qr.CHAMP_GABARIT] = "tpl-inconnu"

    async def scenario(_pilote):
        e.formulaire.champ = completion_qr.CHAMP_TC_DERNIER
        e.traiter("enter")
        refus = e.etat()
        e.formulaire.champ = completion_qr.CHAMP_GABARIT
        e.traiter("backspace")
        return refus, e.etat()

    refus, apres = _monte(_app(e), scenario, banc)
    assert "tpl-inconnu" in refus
    assert "tpl-inconnu" not in apres
    assert completion_qr.ETAT_PRET.format(total=6) in apres


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_ligne_d_etat_se_replie_en_ASCII_comme_le_reste(banc, ascii_seul):
    """Le glyphe de la ligne d'etat passe par la table, dans les deux regimes.

    Quatre mutants vivaient sur le seul argument `ascii_seul` de `jetons.marque`
    -- omis ou passe a `None`, il rend le glyphe UTF-8 en repli ASCII, ce qui est
    exactement ce que `--ascii` existe pour eviter.
    """
    e = ecran()
    table = jetons.glyphes(ascii_seul)

    async def scenario(_pilote):
        vide = e.etat()
        e.formulaire.valeurs.update(SAISIE_VALIDE)
        return vide, e.etat()

    vide, plein = _monte(_app(e, ascii_seul=ascii_seul), scenario, banc)
    assert vide.startswith(table["absent"]), vide
    assert plein.startswith(table["complete"]), plein


def test_ouvrir_le_scan_SANS_chemin_absolu_retombe_sur_le_fichier_de_la_page(
        banc):
    """Un appelant qui ne connait pas le chemin absolu ne doit pas faire tomber
    l'ecran : la page porte toujours son chemin **relatif au projet**, et c'est
    lui qu'on remet au bureau faute de mieux.

    Le mutant qui y vivait passait `None` a `Path()` -- une trace nue, sur le
    seul chemin de cet ecran qui n'a pas de chemin.
    """
    ouvertes = []
    e = ecran(ouvrir=lambda chemin: ouvertes.append(Path(chemin)) or "vu")

    async def scenario(_pilote):
        e.formulaire.champ = completion_qr.ACTION_OUVRIR
        return e.traiter("enter"), e.etat()

    traite, etat = _monte(_app(e), scenario, banc)
    assert traite is True
    assert ouvertes == [Path(planche_muette().fichier)]
    assert "vu" in etat


def test_la_validation_d_un_champ_MANQUANT_rend_TRAITE_et_ne_pose_rien(banc):
    """Deux mutants y vivaient : le retour inverse (la touche remonte alors a
    l'application, qui remonterait d'un palier) et l'etat pose a `None` (la
    ligne d'etat redevient muette, donc la touche annoncee ne fait rien et ne
    dit rien)."""
    poses = []
    e = ecran(poser=poses.append)
    e.formulaire.valeurs.update(SAISIE_VALIDE)
    e.formulaire.valeurs[completion_qr.CHAMP_LOT] = ""

    async def scenario(_pilote):
        e.formulaire.champ = completion_qr.CHAMP_TC_DERNIER
        return e.traiter("enter"), e.etat()

    traite, etat = _monte(_app(e), scenario, banc)
    assert traite is True
    assert poses == []
    assert etat == jetons.marque(
        "absent", completion_qr.COMPTE_DES_CHAMPS.format(saisis=5, total=6))


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_glyphe_de_FOCUS_est_sur_la_ligne_COURANTE_et_sur_ELLE_SEULE(
        banc, ascii_seul):
    """`DESIGN.md` section 7.3 : le glyphe d'invite marque le champ au focus.

    Un mutant y vivait, et il inversait la comparaison : le glyphe se posait sur
    les six autres lignes et pas sur la courante. Personne ne mesurait **quelle**
    ligne le portait -- or c'est tout ce qu'un formulaire dit de l'endroit ou la
    frappe ira.

    La ligne visee est celle du **milieu** du parcours, jamais la premiere : un
    focus fige au rang zero rendrait le meme resultat sur elle.
    """
    e = ecran()

    async def scenario(_pilote):
        e.formulaire.champ = completion_qr.CHAMP_FRAMES
        utile = jetons.largeur_utile(80)
        return {cle: e.ligne_de_champ(cle, utile)
                for cle in completion_qr.LIGNES_DU_FORMULAIRE}

    lignes = _monte(_app(e, ascii_seul=ascii_seul), scenario, banc)
    invite = jetons.glyphes(ascii_seul)["invite"]
    portent = {cle for cle, ligne in lignes.items()
               if re.search(rf"(?:^|\s){re.escape(invite)}(?=\s|$)", ligne)}
    assert portent == {completion_qr.CHAMP_FRAMES}, portent
    assert completion_qr.CHAMPS_SAISIS.index(completion_qr.CHAMP_FRAMES) not in (
        0, len(completion_qr.LIGNES_DU_FORMULAIRE) - 1)


def test_les_pages_LUES_passees_a_l_ecran_arrivent_bien_au_formulaire(banc):
    """Le cablage, pas le calcul : un mutant retirait `pages_lues` de la
    construction du formulaire, et la verification de coherence se faisait alors
    sur une liste vide -- « aucune autre page de ce lot n'a ete lue » sur un lot
    dont trois pages venaient d'etre lues."""
    lues = trois_pages_lues(total=4, occupee=2)
    e = ecran(pages_lues=lues)
    e.formulaire.valeurs.update(SAISIE_VALIDE)
    e.formulaire.valeurs[completion_qr.CHAMP_PAGE] = "2"

    async def scenario(_pilote):
        return e.formulaire.pages_lues, e.formulaire.coherence()

    portees, constat = _monte(_app(e), scenario, banc)
    assert portees == lues
    # Le constat est **celui que les pages portees produisent**, et il differe de
    # celui d'une liste vide : c'est ce qui distingue « cable » de « accepte puis
    # jete », la famille de panne que la garde des rappels cables mesure ailleurs.
    total = e.formulaire.total_du_lot
    assert constat == completion_qr.verifier_la_coherence(
        2, pages_lues=lues, total_du_modele=total)
    assert constat != completion_qr.verifier_la_coherence(
        2, pages_lues=(), total_du_modele=total)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_refus_du_coeur_et_l_ouverture_se_REPLIENT_en_ASCII(banc, ascii_seul,
                                                               tmp_path):
    """Quatre mutants vivaient sur le seul argument `ascii_seul` de
    `jetons.marque`, dans les deux messages que cet ecran pose lui-meme.

    Omis ou passe a `None`, il rend le glyphe UTF-8 en repli ASCII -- ce que
    `--ascii` existe precisement pour eviter, sur les deux seules lignes d'etat
    que cet ecran fabrique.
    """
    scan = tmp_path / "planche_03.tiff"
    scan.write_bytes(b"tiff")
    table = jetons.glyphes(ascii_seul)
    e = ecran(chemin_du_scan=scan, ouvrir=lambda _c: "vu")
    e.formulaire.valeurs.update(SAISIE_VALIDE)
    e.formulaire.valeurs[completion_qr.CHAMP_GABARIT] = "tpl-inconnu"

    async def scenario(_pilote):
        e.formulaire.champ = completion_qr.CHAMP_TC_DERNIER
        rendu_refus = e.traiter("enter")
        refus = e.etat()
        e.formulaire.champ = completion_qr.ACTION_OUVRIR
        rendu_ouvre = e.traiter("enter")
        return refus, e.etat(), rendu_refus, rendu_ouvre

    refus, ouverture, rendu_refus, rendu_ouvre = _monte(
        _app(e, ascii_seul=ascii_seul), scenario, banc)
    assert refus.startswith(table["absent"]), refus
    assert ouverture.startswith(table["substitute"]), ouverture
    # Et les deux chemins **consomment** la touche : la rendre a l'application
    # ferait remonter d'un palier au lieu de valider.
    assert rendu_refus is True and rendu_ouvre is True


def test_une_POSE_reussie_consomme_aussi_la_touche(banc):
    """Le dernier des quatre retours de ce chemin : un `⏎` qui pose la correction
    doit etre consomme, sinon `Échap`-comme-`⏎` remonterait d'un palier pendant
    que l'identite part."""
    poses = []
    e = ecran(poser=poses.append)
    e.formulaire.valeurs.update(SAISIE_VALIDE)

    async def scenario(_pilote):
        e.formulaire.champ = completion_qr.CHAMP_TC_DERNIER
        return e.traiter("enter")

    assert _monte(_app(e), scenario, banc) is True
    assert len(poses) == 1


def test_AUCUNE_touche_de_navigation_ne_laisse_un_message_derriere(banc):
    """La ligne d'etat porte une mesure de l'ecran COURANT.

    Trois mutants y vivaient, chacun posant une chaine parasite sur une branche
    de `traiter` -- `Tab`, `F1`, et la frappe. Ils n'etaient mesures nulle part
    parce qu'aucun test ne lisait la ligne d'etat APRES une touche.
    """
    e = ecran()

    async def scenario(_pilote):
        etats = {}
        e.traiter("tab")
        etats["tab"] = e.etat()
        e.traiter("f1")
        etats["f1"] = e.etat()
        e.traiter("x", "x")
        etats["frappe"] = e.etat()
        return etats

    etats = _monte(_app(e), scenario, banc)
    assert etats["tab"] == jetons.marque(
        "absent", completion_qr.COMPTE_DES_CHAMPS.format(saisis=0, total=6))
    assert etats["f1"] == etats["tab"]
    assert etats["frappe"] == jetons.marque(
        "absent", completion_qr.COMPTE_DES_CHAMPS.format(saisis=1, total=6))


def test_le_rappel_de_POSE_est_REQUIS_et_non_optionnel():
    """Finding `K3` de la vague 3, applique ici : « un `Callable | None = None`
    fait de l'oubli de cablage un silence ».

    Sept pannes de cet epic sont de cette famille -- un rappel accepte que rien
    n'injecte, et tous les bancs verts parce que le banc l'injecte lui-meme. Un
    ecran qu'on ne peut pas monter sans son rappel ne peut pas etre monte sans
    l'avoir cable.
    """
    with pytest.raises(TypeError):
        completion_qr.EcranCompletionQr(planche_muette(), manifeste_du_projet())


def test_une_saisie_VALIDE_rend_l_identite_a_qui_a_ouvert_l_ecran(banc):
    """L'ecran ne pose rien lui-meme : il rend l'identite validee par le coeur.

    C'est ce qui garde ce lot separable du branchement du rapport -- et c'est
    aussi ce qui permet a la note 10 d'Egan (« une page a la fois, puis retour au
    rapport RECALCULE ») d'etre decidee par qui tient le rapport.
    """
    poses = []
    e = ecran(poser=poses.append)
    e.formulaire.valeurs.update(SAISIE_VALIDE)

    async def scenario(_pilote):
        e.formulaire.champ = completion_qr.CHAMP_TC_DERNIER
        e.traiter("enter")
        return e.etat()

    _monte(_app(e), scenario, banc)
    assert [identite.read_rank for identite in poses] == [1]
    assert poses[0].lot_id == LOT_CIBLE


def test_la_ligne_d_etat_COMPTE_et_ne_porte_ni_touche_ni_conseil(banc):
    """`EPIC11-ARB-56` : la ligne d'etat porte une **mesure**.

    Le comptage porte sur les touches nommees par la ligne de raccourcis : aucune
    ne doit apparaitre en ligne d'etat, dans aucun des deux regimes.
    """
    e = ecran()

    async def scenario(_pilote):
        vide = e.etat()
        e.formulaire.valeurs.update(SAISIE_VALIDE)
        return vide, e.etat()

    vide, plein = _monte(_app(e), scenario, banc)
    for etat in (vide, plein):
        for touche in ("Tab", "F1", "Échap", "⏎"):
            assert touche not in etat, (touche, etat)
    assert "0" in vide and "6" in vide
    assert completion_qr.ETAT_PRET.format(total=6) in plein


@pytest.mark.parametrize("ascii_seul", MODES)
def test_l_ecran_tient_la_grille_80x24_dans_les_deux_regimes(banc, ascii_seul,
                                                             tmp_path):
    """AC 8.3 vue du lot E : dix-sept lignes de corps, aucune plus large que la
    largeur utile. Une ligne de plus pousserait la verification hors de l'ecran,
    c'est-a-dire le renseignement que ce formulaire existe pour rendre."""
    scan = tmp_path / "planche_03.tiff"
    scan.write_bytes(b"tiff")
    e = ecran(chemin_du_scan=scan, pages_lues=trois_pages_lues())
    e.formulaire.valeurs.update(SAISIE_VALIDE)

    async def scenario(_pilote):
        return list(e.lignes())

    lignes = _monte(_app(e, ascii_seul=ascii_seul), scenario, banc)
    assert len(lignes) == 17, lignes
    utile = jetons.largeur_utile(80)
    trop_larges = [l for l in lignes if jetons.colonnes(l) > utile]
    assert trop_larges == [], trop_larges


def test_le_formulaire_ne_porte_AUCUNE_case_a_cocher(banc):
    """`EPIC11-ARB-126` (Egan, 2026-08-31) : la case appartient aux listes A
    COCHER. Cet ecran est un formulaire -- le glyphe de focus `>` marque la ligne
    courante, et rien d'autre ne s'y coche."""
    e = ecran()
    rendu = _rendu(e, banc)
    assert "( )" not in rendu and "(•)" not in rendu and "[ ]" not in rendu


def test_le_bandeau_NOMME_la_planche_fautive(banc):
    """Un formulaire qui ne nomme pas sa planche est un formulaire qu'on remplit
    a l'aveugle des qu'un lot en porte deux."""
    e = ecran(page=planche_muette(fichier="scans/scans-in/page_07.png"))

    async def scenario(_pilote):
        return e.bandeau(80)

    assert "page_07.png" in _monte(_app(e), scenario, banc)


def test_le_mot_COMPLETER_est_ECRIT_dans_cet_ecran():
    """`EPIC11-ARB-127` (Egan, 2026-08-31) : la frontiere d'`EPIC11-ARB-48` vise
    la completion de **CHEMIN**, pas celle du QR.

    Ce test est le pendant positif du resserrement porte a
    `test_projets.py::test_la_frontiere_de_COMPLETER_rend_zero_sur_le_paquet_TUI` :
    si quelqu'un re-elargissait la frontiere au mot, il rougirait ici -- et le
    contournement d'hier (`ISSUE_COMPLETER = "saisir-le-qr"`) reviendrait en
    silence. La chose se resserre, la chose ne se renomme pas.
    """
    source = Path(completion_qr.__file__).read_text(encoding="utf-8")
    assert "completion" in source.lower()
    assert completion_qr.TITRE.startswith("Compléter")


def test_le_titre_et_les_raccourcis_sont_ceux_de_la_maquette():
    """Les deux sont des constantes de module : c'est ce qui les fait balayer par
    la garde d'epic du repli ASCII et par celle des majuscules."""
    maquette = (Path(_SRC).parents[0] / "_bmad-output" / "planning-artifacts"
                / "ux-designs" / "ux-tui-2026-08-27" / "maquettes"
                / "E3-4b-scan-completion-qr.txt")
    texte = maquette.read_text(encoding="utf-8")
    assert completion_qr.TITRE in texte
    assert completion_qr.RACCOURCIS_COMPLETION in texte
    assert completion_qr.CONSIGNE in texte


def test_aucune_TOUCHE_n_est_promise_par_la_ligne_d_etat_de_la_maquette():
    """`EPIC11-ARB-56` mesure sur la maquette elle-meme : la ligne d'etat porte
    une mesure de l'ecran, jamais un motif de conception -- ce que la version
    d'avant faisait (« rien n'est prerempli : un champ devine faux n'appelle pas
    la verification »)."""
    maquette = (Path(_SRC).parents[0] / "_bmad-output" / "planning-artifacts"
                / "ux-designs" / "ux-tui-2026-08-27" / "maquettes"
                / "E3-4b-scan-completion-qr.txt")
    lignes = maquette.read_text(encoding="utf-8").splitlines()
    etat = lignes[-3]
    for interdit in ("Tab", "F1", "Échap", "prérempli"):
        assert interdit not in etat, etat


def test_les_chaines_de_code_du_module_ne_portent_AUCUN_terme_de_DECISION():
    """Meme frontiere de vocabulaire que `E3-0` (AC 2.3) : aucun terme de nos
    documents de decision n'apparait a l'ecran."""
    textes = chaines_de_code(Path(completion_qr.__file__))
    interdits = ("palier", "parcours a part", "feuille cli", "rescanner")
    fautives = [t for t in textes
                for mot in interdits if mot in t.lower()]
    assert fautives == [], fautives
