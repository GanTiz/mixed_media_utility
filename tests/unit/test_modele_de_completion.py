# -*- coding: utf-8 -*-
"""Banc du modele de completion depuis le manifeste (story 11.4b, lot S4, AC 5).

**Ce que ce banc mesure, et pourquoi il existe.** Le piege en tete de la fiche
11.4b : les 72 tests de `scan_corrections` etaient verts et **aucun** ne touchait
`payload_depuis_l_identite`, la seule fonction dont la 11.5 a besoin. La regle de
redaction qui en decoule -- « chaque AC mesure ce que la story SUIVANTE
consommera » -- gouverne tout ce fichier : la fonction est appelee **comme la
11.5 l'appellera**, depuis un manifeste reel, sur une pile d'une seule page dont
le QR a echoue.

**Ce que la fixture NE met PAS en scene.** Le refus de QR vient du document de
detection **reellement produit par le coeur** (`detect-ok-et-refus.json`, verse
au depot en 7.4) : `qr_status = no_symbol_detected` y est un constat de terrain,
pas une valeur posee par ce banc. Et le payload de reference contre lequel la
completion est confrontee est celui que le **vrai QR** de la planche soeur a
decode. C'est la garde contre le piege d'`EPIC11-ARB-83` : une fixture de
synthese peut rendre vrai par construction ce que l'on croit mesurer, une
completion confrontee au payload reel ne le peut pas.
"""

from __future__ import annotations

import copy
import inspect
import json
import re
from pathlib import Path

import pytest

from mixed_media_utility import page_templates, pdf_composition, scan_corrections
from mixed_media_utility.io import manifest as manifest_io

#: Le document de detection **reellement produit par le coeur**, deja au depot :
#: une planche lue et une planche refusee, sur un scan de terrain.
DOCUMENT_REEL = (
    Path(__file__).resolve().parents[1]
    / "fixtures" / "detection-scan-reelle" / "detect-ok-et-refus.json"
)

#: Le lot de ce scan reel, et le seul dont le banc connaisse le payload imprime.
LOT_REEL = "rush-bitch-4-chendj-mat_1-c60b2a76"

#: Un second lot, du **meme projet** et distinguable du premier sur les sept
#: champs a la fois : rush, cadence, base de timecode, gabarit, preset de
#: pastilles, compression de gamut. Regle des fabriques du depot : une fabrique
#: mono-element rend invisible toute erreur d'appariement, et le lot vise est
#: place **en seconde position** -- un `find` fautif qui rendrait toujours le
#: premier lot ne se demasque pas autrement (mutant `M25` de la story 5.7, dont
#: la consequence reelle etait d'ecrire les cardinaux sur le mauvais lot).
LOT_VOISIN = "rush-voisin_5"

#: Un troisieme lot, en **derniere** position, pour que la cible ne soit ni la
#: premiere ni la derniere entree de la liste.
LOT_ZENITH = "rush-zenith_2"


def payload_reel() -> dict:
    """Le payload que le **vrai QR** de la planche lue a rendu."""
    document = json.loads(DOCUMENT_REEL.read_text(encoding="utf-8"))
    return document["pages"][0]["payload"]


def manifeste_du_projet() -> dict:
    """Le manifeste du projet reel, **trois lots distinguables**, cible en 2e.

    Les valeurs du lot `LOT_REEL` ne sont pas choisies : elles sont celles que
    le payload imprime declare, si bien qu'un modele construit depuis ce
    manifeste est confrontable au payload que le QR a rendu. Les deux autres
    lots different de lui sur **chacun** des sept champs -- un remplissage
    uniforme laisserait passer n'importe quelle permutation.
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
            {"lot_id": LOT_VOISIN, "rush_id": "rush-voisin",
             "state": "extraction", "fps_target": 5.0, "fps_target_exact": "5/1",
             "timecode_base_fps": "24/1",
             "template_id": "tpl-a4-portrait-1f-v2",
             "patch_preset_id": "patches-9-v1",
             "gamut_map_id": "gamut-map-lin-1",
             "expected_frame_count": 10, "frames_dir": "frames/voisin",
             "source_frame_count": 50, "source_frame_count_is_exact": True,
             "rounding_policy": "floor"},
            # SECONDE position : la cible, celle du scan reel.
            {"lot_id": LOT_REEL, "rush_id": "rush-bitch-4-chendj-mat",
             "state": "extraction", "fps_target": 1.0, "fps_target_exact": "1/1",
             "timecode_base_fps": "25/1",
             "template_id": "tpl-a4-paysage-4f-v2",
             "patch_preset_id": "patches-17-v4",
             "gamut_map_id": "gamut-map-none-1",
             "expected_frame_count": 4, "frames_dir": "frames/bitch4",
             "source_frame_count": 100, "source_frame_count_is_exact": True,
             "rounding_policy": "floor"},
            # DERNIERE position : un lot de plusieurs planches, celui qui rend
            # une pagination non triviale (10 frames pour 4 emplacements).
            {"lot_id": LOT_ZENITH, "rush_id": "rush-zenith",
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


def pile_d_une_seule_planche_muette() -> dict:
    """Le document de detection reel, **reduit a sa seule planche refusee**.

    C'est le cas exact qu'Egan a nomme : une pile d'une seule page dont le QR
    echoue. Elle n'a **aucune** planche soeur a lire, donc aucun modele decode :
    avant cette story, elle etait incompletable pour cette seule raison.

    La planche gardee est celle du **rang 1** du document reel, celle dont le
    coeur a ecrit `qr_status = no_symbol_detected`. Rien n'est mis en scene : on
    retire l'autre page, on ne fabrique pas un refus.
    """
    document = json.loads(DOCUMENT_REEL.read_text(encoding="utf-8"))
    refusee = [page for page in document["pages"]
               if page.get("qr_status") != "decoded"]
    assert len(refusee) == 1, [page.get("qr_status") for page in document["pages"]]
    document["pages"] = refusee
    return document


def identite_de_la_planche_muette(**surcharges) -> scan_corrections.IdentiteManuelle:
    """Ce que l'operatrice lit SUR LE PAPIER de la planche muette, et saisit.

    Les timecodes sont ceux que la planche porte imprimes -- donc ceux du
    payload reel de sa jumelle : la premiere et la derniere image, et elles
    seules (`EXPERIENCE.md:346`).
    """
    champs = {
        "read_rank": 1,
        "lot_id": LOT_REEL,
        "template_id": "tpl-a4-paysage-4f-v2",
        "frames_per_page": 4,
        "page_index": 0,
        "first_frame_timecode": "01:01:39:12",
        "last_frame_timecode": "01:01:42:12",
    }
    champs.update(surcharges)
    return scan_corrections.IdentiteManuelle(**champs)


# ---------------------------------------------------------------------------
# La fixture est-elle reelle ? (garde contre EPIC11-ARB-83)
# ---------------------------------------------------------------------------


def test_le_manifeste_de_la_fabrique_est_un_manifeste_REEL(tmp_path):
    """AC 5.3 : « depuis un manifeste **reel** » -- valide, pas vraisemblable.

    Un dictionnaire qui ressemble a un manifeste et que le schema refuserait
    rendrait vert un banc qui ne mesure alors plus le chemin de production. Le
    schema du depot est le seul juge de « reel ».
    """
    chemin = tmp_path / "project.json"
    chemin.write_text(json.dumps(manifeste_du_projet()), encoding="utf-8")
    valide = manifest_io.validate_manifest(chemin)
    assert valide["project_id"] == "chendj-mat"
    # Volet symetrique : la validation mord vraiment. Sans lui, un schema qui
    # cesserait d'etre applique rendrait le test ci-dessus vert a jamais.
    casse = manifeste_du_projet()
    casse["lots"][1]["fps_target"] = "pas-un-nombre"
    autre = tmp_path / "casse.json"
    autre.write_text(json.dumps(casse), encoding="utf-8")
    with pytest.raises(manifest_io.ValidationError):
        manifest_io.validate_manifest(autre)


def test_la_planche_muette_de_la_fabrique_porte_un_refus_DU_COEUR():
    """Le QR echoue **de terrain**, il n'est pas mis en scene par le banc.

    Piege paye ce matin meme (`EPIC11-ARB-83`) : une fixture de synthese peut
    rendre un defaut invisible par construction. Ici la question est symetrique
    -- est-ce que ce que je crois mesurer (« le QR a echoue ») est un fait ou
    une mise en scene ? Le document vient du coeur, et son constat est nomme.
    """
    document = pile_d_une_seule_planche_muette()
    assert len(document["pages"]) == 1
    planche = document["pages"][0]
    assert planche["qr_status"] == "no_symbol_detected"
    assert "payload" not in planche
    # Et la pile n'a **aucune** planche lue : c'est ce qui rendait le cas
    # incompletable avant cette story.
    assert not [page for page in document["pages"] if page.get("qr_status") == "decoded"]


# ---------------------------------------------------------------------------
# AC 5.3 -- l'appel de la 11.5, sur une pile d'UNE seule planche muette
# ---------------------------------------------------------------------------


def test_une_pile_d_UNE_SEULE_planche_muette_se_complete_DEPUIS_LE_MANIFESTE():
    """AC 5.2 regime 1 et AC 5.3 : le cas exact qu'Egan a nomme.

    C'est la sequence entiere de la 11.5, dans son ordre : le document de
    detection ne porte qu'une planche et son QR a echoue ; l'operatrice saisit
    ce qu'elle lit ; le modele vient du **manifeste** parce que le lot est celui
    du projet ; le payload se compose.

    **La mesure qui compte n'est pas que ca ne leve pas.** C'est que le payload
    reconstitue est egal, champ pour champ, a celui que le **vrai QR** de la
    planche soeur a rendu -- y compris `page_count`, `schema_version` et
    `page_role`, qu'aucune saisie ne porte. Une completion qui inventerait un
    seul de ces champs se verrait ici et nulle part ailleurs.
    """
    document = pile_d_une_seule_planche_muette()
    identites = scan_corrections.lire_les_identites(
        scan_corrections.poser_les_identites(
            document, [identite_de_la_planche_muette()]))
    assert list(identites) == [1]

    modele = scan_corrections.modele_depuis_le_manifeste(
        manifeste_du_projet(), lot_id=LOT_REEL)
    complete = scan_corrections.payload_depuis_l_identite(
        identites[1], modele=modele)

    assert complete == payload_reel()


def test_le_modele_du_manifeste_porte_les_HUIT_champs_neutres_et_le_lot():
    """AC 5.1 : les sept champs presents, plus `page_count` deduit.

    Le contrat de completion est :data:`CHAMPS_NEUTRES_DU_LOT`, et un modele qui
    n'en couvrirait que sept se ferait refuser par `payload_depuis_l_identite`
    -- mais seulement a l'appel suivant, avec un motif qui parle du modele et
    non de sa fabrication. On le mesure ici, ou il se lit.

    `lot_id` en plus des huit : c'est sur lui que le consommateur verifie que le
    modele et l'identite saisie parlent du meme lot.
    """
    modele = scan_corrections.modele_depuis_le_manifeste(
        manifeste_du_projet(), lot_id=LOT_REEL)
    assert set(modele) == set(scan_corrections.CHAMPS_NEUTRES_DU_LOT) | {"lot_id"}
    assert modele["lot_id"] == LOT_REEL
    # Les sept champs presents valent **ce que le payload imprime declare**.
    reel = payload_reel()
    for champ in scan_corrections.CHAMPS_NEUTRES_DU_LOT:
        assert modele[champ] == reel[champ], champ


# ---------------------------------------------------------------------------
# AC 5.1 -- chaque champ vient de SA source, jamais d'un litteral local
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("champ,section,cle,valeur_temoin", [
    ("project_id", "projet", "project_id", "projet-temoin"),
    # Le rush temoin doit **exister** au manifeste : la deduction de
    # `page_count` recalcule la selection, qui lit la cadence source du rush.
    ("rush_id", "lot", "rush_id", "rush-zenith"),
    ("fps_target", "lot", "fps_target", 12.5),
    ("timecode_base_fps", "lot", "timecode_base_fps", "30000/1001"),
    ("patch_preset_id", "lot", "patch_preset_id", "patches-12-v1"),
    ("gamut_map_id", "lot", "gamut_map_id", "gamut-map-lin-1"),
    ("target_colorspace", "color", "target_colorspace", "rec709"),
])
def test_chaque_champ_SUIT_sa_source_de_manifeste(champ, section, cle, valeur_temoin):
    """AC 5.1 : sept champs, sept sources -- et **aucun litteral local**.

    Finding 4.3, deja paye dans ce depot : un litteral recopie diverge en
    silence le jour ou le contrat change. Le seul instrument qui le voie est de
    **bouger la source** et de verifier que le modele bouge avec elle. Un champ
    fige rendrait la valeur d'origine et ce test rougirait.

    Les valeurs temoins sont toutes differentes de celles du lot cible **et**
    de celles des deux autres lots : une valeur temoin qui coinciderait avec
    l'existant rendrait le test vert par construction.
    """
    manifeste = manifeste_du_projet()
    cible = next(lot for lot in manifeste["lots"] if lot["lot_id"] == LOT_REEL)
    avant = scan_corrections.modele_depuis_le_manifeste(
        manifeste, lot_id=LOT_REEL)[champ]
    assert avant != valeur_temoin, "la valeur temoin doit differer de l'existant"
    if section == "projet":
        manifeste[cle] = valeur_temoin
    elif section == "lot":
        cible[cle] = valeur_temoin
    else:
        manifeste["color"][cle] = valeur_temoin
    apres = scan_corrections.modele_depuis_le_manifeste(
        manifeste, lot_id=LOT_REEL)
    assert apres[champ] == valeur_temoin
    # ... et rien d'autre n'a bouge : une source lue au mauvais niveau
    # contaminerait ses voisins.
    for autre in scan_corrections.CHAMPS_NEUTRES_DU_LOT:
        if autre != champ:
            assert apres[autre] == scan_corrections.modele_depuis_le_manifeste(
                manifeste_du_projet(), lot_id=LOT_REEL)[autre], autre


def test_la_completion_vise_le_lot_NOMME_et_jamais_LE_PREMIER_du_manifeste():
    """Regle des fabriques, point 2 : trois lots, la cible en **seconde** place.

    Mutant `M25` de la story 5.7 : `_find_lot` rendait le **premier** lot au
    lieu du lot vise et 257 tests restaient verts, toutes les fixtures placant
    la cible en tete. La consequence reelle etait d'ecrire les cardinaux sur le
    mauvais lot. Ici, la meme faute donnerait a une planche muette la cadence
    et la base de timecode d'un autre rush -- donc des TIFF au mauvais timecode,
    d'apparence valide.
    """
    manifeste = manifeste_du_projet()
    assert [lot["lot_id"] for lot in manifeste["lots"]] == [
        LOT_VOISIN, LOT_REEL, LOT_ZENITH]
    modeles = {lot_id: scan_corrections.modele_depuis_le_manifeste(
        manifeste, lot_id=lot_id)
        for lot_id in (LOT_VOISIN, LOT_REEL, LOT_ZENITH)}
    # La cible se distingue des deux autres sur **chacun** des champs de
    # portee lot : un remplissage uniforme laisserait passer n'importe quelle
    # permutation. (`gamut_map_id` n'a que deux valeurs au registre du depot,
    # donc trois lots ne peuvent pas y etre deux a deux distincts -- ce qui
    # compte est que la CIBLE differe des deux autres, et elle le fait.)
    for champ in ("rush_id", "fps_target", "timecode_base_fps",
                  "patch_preset_id", "gamut_map_id"):
        assert modeles[LOT_REEL][champ] != modeles[LOT_VOISIN][champ], champ
        assert modeles[LOT_REEL][champ] != modeles[LOT_ZENITH][champ], champ
    for champ in ("rush_id", "fps_target", "timecode_base_fps",
                  "patch_preset_id"):
        assert modeles[LOT_VOISIN][champ] != modeles[LOT_ZENITH][champ], champ
    assert modeles[LOT_REEL]["rush_id"] == "rush-bitch-4-chendj-mat"
    assert modeles[LOT_ZENITH]["rush_id"] == "rush-zenith"


# ---------------------------------------------------------------------------
# AC 5.1 -- `page_count` DEDUIT par la formule de l'impression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lot_id,orientation,attendu", [
    # Une seule planche : 4 frames pour 4 emplacements.
    (LOT_REEL, page_templates.ORIENTATION_PAYSAGE, 1),
    # Une pagination qui **ne tombe pas juste** : 10 frames pour 4
    # emplacements font 3 planches, pas 2. Une division par defaut au lieu de
    # la division par exces rendrait 2 ici, et 1 sur le cas ci-dessus : il
    # faut les deux pour que le mutant meure.
    (LOT_ZENITH, page_templates.ORIENTATION_PORTRAIT, 3),
    # Un lot d'un seul emplacement par planche : 10 frames, 10 planches.
    (LOT_VOISIN, page_templates.ORIENTATION_PORTRAIT, 10),
])
def test_page_count_est_CELUI_QUE_L_IMPRESSION_POSE(lot_id, orientation, attendu):
    """AC 5.1 : `page_count` deduit par la formule verbatim de l'impression.

    Le modele n'est pas confronte a un nombre ecrit dans le test mais au
    `page_count` que `compose_lot_plan` -- le **vrai** producteur de planches --
    pose dans le payload qu'il fait imprimer. C'est la seule confrontation qui
    survive a un changement de pagination : un litteral recopie ici, comme dans
    `scan_corrections`, divergerait au meme moment et le banc resterait vert.

    Le nombre attendu est **aussi** epingle, parce qu'un test qui ne comparerait
    que les deux cotes resterait vert si les deux devenaient faux ensemble.
    """
    manifeste = manifeste_du_projet()
    lot = next(entree for entree in manifeste["lots"]
               if entree["lot_id"] == lot_id)
    emplacements = page_templates.get_template(
        lot["template_id"]).frames_per_page
    plan = pdf_composition.compose_lot_plan(
        manifest=manifeste, lot_id=lot_id, orientation=orientation,
        frames_per_page=emplacements,
        patch_preset=lot["patch_preset_id"],
        gamut_map_id=lot["gamut_map_id"],
        geometry_version="v2")
    imprime = {page.qr.payload["page_count"] for page in plan.pages
               if "page_count" in page.qr.payload}
    modele = scan_corrections.modele_depuis_le_manifeste(
        manifeste, lot_id=lot_id)
    assert modele["page_count"] == attendu
    assert imprime == {attendu}, (lot_id, imprime)


def test_page_count_passe_par_LA_SELECTION_recalculee_et_non_par_un_cardinal_declare():
    """`page_count` suit la selection, jamais `expected_frame_count`.

    Deux cardinaux vivent au manifeste : celui que le lot **declare**
    (`expected_frame_count`) et celui que la selection **recalcule** depuis les
    cadences. L'impression n'utilise que le second. Lire le premier donnerait un
    `page_count` qui a l'air juste et qui n'est pas celui du QR imprime -- et le
    test ne le verrait pas tant que les deux coincident, ce qui est le cas
    nominal. On les fait donc diverger.
    """
    manifeste = manifeste_du_projet()
    lot = next(entree for entree in manifeste["lots"]
               if entree["lot_id"] == LOT_ZENITH)
    lot["expected_frame_count"] = 40  # mensonge : la selection en rend 10
    modele = scan_corrections.modele_depuis_le_manifeste(
        manifeste, lot_id=LOT_ZENITH)
    assert modele["page_count"] == 3  # et non 10, que 40 frames donneraient


def test_la_formule_de_pagination_n_est_ecrite_QU_UNE_FOIS():
    """AC 5.1 : « la formule **verbatim** de `pdf_composition.py:1799` ».

    Verbatim ne veut pas dire recopiee : il n'y a qu'une redaction, publiee par
    `pdf_composition.nombre_de_planches`, et les deux chemins l'appellent. Le
    test verrouille la formule elle-meme sur ses bords -- c'est la ou une
    division par defaut, un `+1` de trop ou un `-1` manquant se voient.
    """
    nombre = pdf_composition.nombre_de_planches
    assert nombre(0, 4) == 0
    assert nombre(1, 4) == 1
    assert nombre(4, 4) == 1
    assert nombre(5, 4) == 2
    assert nombre(8, 4) == 2
    assert nombre(9, 4) == 3
    assert nombre(10, 1) == 10
    # Un gabarit a zero emplacement ne pagine rien : le refus est nomme plutot
    # que de rendre 0 planche pour n'importe quel nombre de frames.
    with pytest.raises(pdf_composition.LotContentError):
        nombre(10, 0)
    with pytest.raises(pdf_composition.LotContentError):
        nombre(-1, 4)
    # `True` est un `int` en Python : le laisser passer paginerait a un
    # emplacement par planche, silencieusement.
    with pytest.raises(pdf_composition.LotContentError):
        nombre(10, True)


def test_la_formule_n_est_REDIGEE_QU_UNE_FOIS_dans_tout_le_paquet():
    """La propriete que la comparaison de sorties ne mesure PAS.

    Trouve par injection ciblee : reinliner `(len(frames) + frames_per_page - 1)
    // frames_per_page` dans `compose_lot_plan` **survit** a tous les tests
    ci-dessus. C'est normal et c'est le probleme : deux redactions coincident le
    jour ou on les ecrit, et un test qui ne compare que leurs sorties reste vert
    tant qu'elles coincident. Il ne rougit qu'apres la divergence, c'est-a-dire
    apres le defaut -- alors que le motif de l'extraction etait de la rendre
    impossible.

    Le seul instrument qui la mesure est **structurel**, et c'est le geste que le
    depot fait deja pour le predicat de page de calibration
    (`test_le_predicat_de_page_de_calibration_n_est_redige_qu_une_fois`) : on
    compte les redactions de l'idiome dans le paquet entier, et on verifie
    ensuite que les appelants passent bien par la fonction publiee -- sans quoi
    le compteur serait tenu par un code qui ne paginerait plus du tout.
    """
    idiome = re.compile(r"\+\s*\w+\s*-\s*1\s*\)\s*//")
    paquet = Path(pdf_composition.__file__).resolve().parent
    redactions = {
        str(fichier.relative_to(paquet)): len(
            idiome.findall(fichier.read_text(encoding="utf-8")))
        for fichier in sorted(paquet.rglob("*.py"))
        if idiome.search(fichier.read_text(encoding="utf-8"))
    }
    assert redactions == {"pdf_composition.py": 1}, (
        f"{redactions}: la division par exces d'une pagination vit dans "
        "`pdf_composition.nombre_de_planches`, et nulle part ailleurs. On "
        "l'APPELLE, on ne la recopie pas -- une seconde redaction coinciderait "
        "avec la premiere le jour de son ecriture et divergerait ensuite sans "
        "qu'aucune etape n'echoue.")

    # Volet symetrique : les deux chemins passent bien par la fonction publiee.
    assert "nombre_de_planches(" in inspect.getsource(
        pdf_composition.compose_lot_plan)
    assert "nombre_de_planches(" in inspect.getsource(
        pdf_composition.page_count_du_lot)
    assert "page_count_du_lot(" in inspect.getsource(
        scan_corrections.modele_depuis_le_manifeste)


# ---------------------------------------------------------------------------
# AC 5.2 -- regime 2 : le lot inconnu, et le refus qui reste NOMME
# ---------------------------------------------------------------------------


def test_un_lot_INCONNU_du_projet_REFUSE_nommement_et_n_invente_AUCUN_champ():
    """AC 5.2, regime 2. `EPIC11-ARB-64`, verbatim :

    « il faut une planche lue, ou les champs imprimes »

    Le refus **nomme** le lot cherche et les lots connus : le cas reel est un
    scan de planches d'un AUTRE projet, ou la reponse est « adopte ce lot »
    (AC 3) et non « corrige ta saisie ». Un refus muet enverrait l'operatrice
    verifier au mauvais endroit.
    """
    manifeste = manifeste_du_projet()
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_corrections.modele_depuis_le_manifeste(
            manifeste, lot_id="rush-etranger_25")
    motif = str(refus.value)
    assert "rush-etranger_25" in motif
    # Les trois lots connus sont nommes, pas seulement le premier.
    for connu in (LOT_VOISIN, LOT_REEL, LOT_ZENITH):
        assert connu in motif, (connu, motif)
    assert "planche lue" in motif and "imprimes" in motif


def test_un_projet_SANS_AUCUN_LOT_refuse_aussi_et_le_dit():
    """Le refus tient quand la liste est vide -- pas seulement quand elle est
    pleine d'autres lots. Une boucle qui ne serait jamais entree pourrait rendre
    un modele vide au lieu de lever."""
    manifeste = manifeste_du_projet()
    manifeste["lots"] = []
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_corrections.modele_depuis_le_manifeste(manifeste, lot_id=LOT_REEL)
    assert "(aucun)" in str(refus.value)


@pytest.mark.parametrize("champ,section,cle", [
    ("project_id", "projet", "project_id"),
    ("rush_id", "lot", "rush_id"),
    ("fps_target", "lot", "fps_target"),
    ("timecode_base_fps", "lot", "timecode_base_fps"),
    ("patch_preset_id", "lot", "patch_preset_id"),
    ("gamut_map_id", "lot", "gamut_map_id"),
    ("target_colorspace", "color", "target_colorspace"),
])
def test_un_champ_ABSENT_du_manifeste_est_REFUSE_et_NOMME(champ, section, cle):
    """AC 5.2 : rien ne se devine, meme quand le lot est connu.

    Un lot reconstruit d'un scan anterieur a la story 5.11 peut ne pas porter
    `template_id`, `patch_preset_id` ni `gamut_map_id`. Le repli n'est pas une
    valeur par defaut -- c'est le refus, et il nomme le champ manquant.
    """
    manifeste = manifeste_du_projet()
    cible = next(lot for lot in manifeste["lots"] if lot["lot_id"] == LOT_REEL)
    section_dict = {"projet": manifeste, "lot": cible,
                    "color": manifeste["color"]}[section]
    del section_dict[cle]
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_corrections.modele_depuis_le_manifeste(manifeste, lot_id=LOT_REEL)
    assert champ in str(refus.value)


def test_une_chaine_VIDE_ne_passe_pas_pour_un_identifiant():
    """Le schema borne ces champs a `minLength: 1` ; une chaine vide qui
    traverserait se lirait plus loin comme un identifiant. Le refus est le
    meme que pour l'absence."""
    manifeste = manifeste_du_projet()
    cible = next(lot for lot in manifeste["lots"] if lot["lot_id"] == LOT_REEL)
    cible["patch_preset_id"] = "   "
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_corrections.modele_depuis_le_manifeste(manifeste, lot_id=LOT_REEL)
    assert "patch_preset_id" in str(refus.value)


def test_un_lot_SANS_template_id_refuse_plutot_que_de_deviner_la_pagination():
    """Sans le gabarit avec lequel le lot a ete imprime, le nombre de planches
    ne se deduit pas. Un gabarit par defaut produirait une pagination fausse
    d'apparence valide -- c'est la faute que `scan_detect` refuse deja de
    commettre sur la geometrie d'une page."""
    manifeste = manifeste_du_projet()
    cible = next(lot for lot in manifeste["lots"] if lot["lot_id"] == LOT_REEL)
    del cible["template_id"]
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_corrections.modele_depuis_le_manifeste(manifeste, lot_id=LOT_REEL)
    assert "template_id" in str(refus.value)


def test_un_champ_du_CONTRAT_sans_source_de_manifeste_est_REFUSE(monkeypatch):
    """La table de sources et le contrat se **confrontent**, ils ne se supposent
    pas egaux.

    Le jour ou `CHAMPS_NEUTRES_DU_LOT` gagne un neuvieme champ, un constructeur
    qui l'ignorerait rendrait un modele silencieusement incomplet -- et le
    symptome n'arriverait qu'a l'appel suivant, sous un motif qui parle du
    modele et non de sa fabrication. C'est la meme discipline que le passage par
    `build_page_payload` dans `payload_depuis_l_identite`.
    """
    monkeypatch.setattr(
        scan_corrections, "CHAMPS_NEUTRES_DU_LOT",
        scan_corrections.CHAMPS_NEUTRES_DU_LOT + ("champ_neuf_du_contrat",))
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_corrections.modele_depuis_le_manifeste(
            manifeste_du_projet(), lot_id=LOT_REEL)
    assert "champ_neuf_du_contrat" in str(refus.value)


@pytest.mark.parametrize("manifeste,lot_id", [
    ("pas un manifeste", LOT_REEL),
    (None, LOT_REEL),
])
def test_un_manifeste_qui_n_en_est_pas_un_est_REFUSE(manifeste, lot_id):
    """Le coeur ne fait jamais confiance a son appelant : un refus nomme, pas un
    `AttributeError` nu -- piege deja paye sur `scan_detect.py:250-260`."""
    with pytest.raises(scan_corrections.IdentiteIncompletable):
        scan_corrections.modele_depuis_le_manifeste(manifeste, lot_id=lot_id)


@pytest.mark.parametrize("lot_id", ["", "   ", None, 12])
def test_un_lot_sans_identifiant_lisible_est_REFUSE(lot_id):
    with pytest.raises(scan_corrections.IdentiteIncompletable):
        scan_corrections.modele_depuis_le_manifeste(
            manifeste_du_projet(), lot_id=lot_id)


def test_le_manifeste_n_est_PAS_MUTE_par_la_construction_du_modele():
    """Le constructeur lit, il n'ecrit pas. Un modele qui muterait le manifeste
    de son appelant ferait diverger la 11.5 de ce qu'elle a charge."""
    manifeste = manifeste_du_projet()
    temoin = copy.deepcopy(manifeste)
    scan_corrections.modele_depuis_le_manifeste(manifeste, lot_id=LOT_REEL)
    assert manifeste == temoin


# ---------------------------------------------------------------------------
# AC 5.4 -- les trois refus de `_slots_interpoles` restent INTACTS
# ---------------------------------------------------------------------------
#
# Ils sont mesures **a travers le nouveau chemin** -- modele du manifeste, puis
# `payload_depuis_l_identite` -- et non sur la fonction privee : c'est cette
# composition-la que la 11.5 exercera, et c'est elle qui doit refuser.


def test_une_planche_a_UNE_SEULE_frame_dont_les_TIMECODES_DIFFERENT_est_REFUSEE():
    """AC 5.4, premier refus : « on ne sait pas lequel des deux est celui de la
    frame ». En choisir un arbitrairement nommerait le TIFF au hasard."""
    modele = scan_corrections.modele_depuis_le_manifeste(
        manifeste_du_projet(), lot_id=LOT_VOISIN)
    identite = identite_de_la_planche_muette(
        lot_id=LOT_VOISIN, template_id="tpl-a4-portrait-1f-v2",
        frames_per_page=1,
        first_frame_timecode="01:01:39:12",
        last_frame_timecode="01:01:42:12")
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_corrections.payload_depuis_l_identite(identite, modele=modele)
    assert "une seule frame" in str(refus.value)
    # Volet symetrique : la meme planche avec **le meme** timecode des deux
    # cotes passe, et rend son unique emplacement. Sans lui, un refus pose sur
    # toute planche a une frame serait indiscernable de celui-ci.
    passante = identite_de_la_planche_muette(
        lot_id=LOT_VOISIN, template_id="tpl-a4-portrait-1f-v2",
        frames_per_page=1,
        first_frame_timecode="01:01:39:12",
        last_frame_timecode="01:01:39:12")
    payload = scan_corrections.payload_depuis_l_identite(passante, modele=modele)
    assert payload["slots"] == [
        {"slot_index": 0, "frame_timecode": "01:01:39:12"}]


def test_un_ecart_de_timecodes_NEGATIF_est_REFUSE():
    """AC 5.4, deuxieme refus : « la derniere image precederait la premiere »."""
    modele = scan_corrections.modele_depuis_le_manifeste(
        manifeste_du_projet(), lot_id=LOT_REEL)
    identite = identite_de_la_planche_muette(
        first_frame_timecode="01:01:42:12",
        last_frame_timecode="01:01:39:12")
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_corrections.payload_depuis_l_identite(identite, modele=modele)
    assert "precede" in str(refus.value)


def test_un_ecart_de_timecodes_qui_ne_TOMBE_PAS_JUSTE_est_REFUSE():
    """AC 5.4, troisieme refus. `EPIC11-ARB-64` / `_slots_interpoles`, verbatim :

    « Un ecart qui ne tombe pas juste est **refuse** plutot qu'arrondi --
    arrondir decalerait un nom de TIFF d'une frame sans un mot. »

    Quatre emplacements, donc trois intervalles : un ecart de 74 frames ne se
    repartit pas. Le refus nomme l'ecart et le nombre d'intervalles, pour que
    l'operatrice sache lequel des deux timecodes elle a mal lu.
    """
    modele = scan_corrections.modele_depuis_le_manifeste(
        manifeste_du_projet(), lot_id=LOT_REEL)
    identite = identite_de_la_planche_muette(
        first_frame_timecode="01:01:39:12",
        last_frame_timecode="01:01:42:11")  # 74 frames pour 3 intervalles
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_corrections.payload_depuis_l_identite(identite, modele=modele)
    motif = str(refus.value)
    assert "74" in motif and "3 intervalles" in motif
    assert "arrondis" in motif
    # Volet symetrique, et c'est lui qui rend le refus mesurable : **75** frames
    # tombent juste et donnent les quatre timecodes du payload reel. Sans ce
    # volet, un refus pose sur tout ecart serait vert de la meme facon.
    juste = identite_de_la_planche_muette(
        last_frame_timecode="01:01:42:12")
    payload = scan_corrections.payload_depuis_l_identite(juste, modele=modele)
    assert payload["slots"] == payload_reel()["slots"]


def test_les_emplacements_d_une_planche_qui_n_est_PAS_LA_PREMIERE_sont_decales():
    """`slot_index` est un rang dans le **LOT**, pas dans la planche.

    Regle des fabriques, point 2, appliquee aux **pages** : la planche visee est
    la troisieme du lot (`page_index = 2`), jamais la premiere. Un rang qui
    repartirait de zero a chaque planche declarerait deux fois le meme
    emplacement au manifest, et la reconstruction refuserait -- « Conflit de
    reconstruction: slot_index 0 declare plusieurs fois ». Une planche unique en
    premiere position ne le montre pas.
    """
    modele = scan_corrections.modele_depuis_le_manifeste(
        manifeste_du_projet(), lot_id=LOT_ZENITH)
    identite = identite_de_la_planche_muette(
        lot_id=LOT_ZENITH, template_id="tpl-a4-portrait-4f-v2",
        frames_per_page=4, page_index=2,
        first_frame_timecode="00:00:10:00",
        last_frame_timecode="00:00:11:00")
    payload = scan_corrections.payload_depuis_l_identite(identite, modele=modele)
    assert [slot["slot_index"] for slot in payload["slots"]] == [8, 9, 10, 11]
    # Les quatre timecodes sont **distincts et croissants** : une interpolation
    # qui rendrait quatre fois le premier passerait un test qui ne regarde que
    # les rangs.
    timecodes = [slot["frame_timecode"] for slot in payload["slots"]]
    assert len(set(timecodes)) == 4
    assert timecodes == sorted(timecodes)
    assert timecodes[0] == "00:00:10:00" and timecodes[-1] == "00:00:11:00"
    assert payload["page_index"] == 2
    assert payload["page_count"] == 3


def test_un_modele_d_UN_AUTRE_LOT_est_refuse_par_son_consommateur():
    """Le modele du manifeste n'echappe pas a la garde d'appariement : completer
    une identite avec le modele d'un autre lot melangerait deux lots, et c'est
    exactement ce que la fabrique a trois lots rend possible par erreur."""
    modele = scan_corrections.modele_depuis_le_manifeste(
        manifeste_du_projet(), lot_id=LOT_VOISIN)
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_corrections.payload_depuis_l_identite(
            identite_de_la_planche_muette(), modele=modele)
    assert LOT_VOISIN in str(refus.value) and LOT_REEL in str(refus.value)
