"""Versionnage des PLANCHES -- `EPIC11-ARB-91` (Egan, 2026-08-31).

Ce qui distingue une planche d'un lot ou d'un master, et qui commande tout ce
fichier : **une planche imprimee a quitte le disque**. Versionner le nom du
fichier ne protege rien une fois la feuille posee sur un bureau -- deux tirages
du meme lot y sont visuellement identiques.

D'ou trois porteurs du rang, mesures separement parce qu'ils protegent trois
choses differentes :

* le NOM du fichier      -> le disque ;
* l'ETIQUETTE imprimee   -> l'oeil de l'operateur ;
* le PAYLOAD QR          -> la machine qui scanne.

Un test qui n'en mesurerait qu'un laisserait les deux autres deriver, et la
derive serait invisible jusqu'au jour ou une planche v2 serait scannee comme si
elle etait la v1.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

from mixed_media_utility.io import naming
from mixed_media_utility.io import payload as payload_io
from mixed_media_utility.io import version_ranks
import mixed_media_utility.pdf_composition as pdf_composition


def _fabrique_de_manifeste():
    """Reutilise la fabrique du banc de composition plutot que d'en ecrire une
    seconde : deux fabriques du meme manifeste divergeraient au premier
    ajustement de schema, et c'est le banc existant qui fait foi."""
    spec = importlib.util.spec_from_file_location(
        "_t_pdf", "tests/unit/test_pdf_composition.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.make_manifest


# ---------------------------------------------------------------------------
# Le NOM : rang apres le marqueur, jamais colle a celui du lot.
# ---------------------------------------------------------------------------


#: Un gabarit quelconque, nomme une fois : ces tests-ci mesurent la PLACE du
#: rang, pas la mise en page. Depuis `EPIC11-ARB-171` le nom porte le fragment
#: de forme a l'endroit ou vivait le mot `planches`.
_GABARIT = "tpl-a4-portrait-2f-v2"


def test_le_rang_se_place_APRES_le_marqueur_de_mise_en_page():
    assert naming.build_sheets_pdf_filename(
        "demo", "R", "R_24", version_rank=2,
        template_id=_GABARIT) == "demo_R_24_2f-por_v2.pdf"


def test_le_rang_1_n_ecrit_AUCUN_fragment():
    sans = naming.build_sheets_pdf_filename("demo", "R", "R_24", template_id=_GABARIT)
    avec_none = naming.build_sheets_pdf_filename(
        "demo", "R", "R_24", version_rank=None, template_id=_GABARIT)
    assert sans == avec_none == "demo_R_24_2f-por.pdf"


def test_le_rang_du_LOT_et_celui_de_la_PLANCHE_ne_se_collent_pas():
    """**Le defaut que la premiere redaction avait**, trouve en essayant.

    Le rang etait place avant `planches`, ce qui donnait sur un lot deja
    versionne `demo_R_24_v3_v2_planches.pdf` : DEUX fragments `_vN` colles, ou
    ni l'oeil ni une analyse ne peuvent dire lequel est le rang du lot et
    lequel celui de la planche. Le marqueur doit les separer, exactement comme
    `_mmu_` les separe dans un nom de master -- c'etait `_planches` jusqu'a
    `EPIC11-ARB-171`, c'est le fragment de mise en page depuis.
    """
    nom = naming.build_sheets_pdf_filename(
        "demo", "R", "R_24_v3", version_rank=2, template_id=_GABARIT)
    assert nom == "demo_R_24_v3_2f-por_v2.pdf"
    # La propriete qui compte, et qui ne depend pas de la forme exacte : les
    # deux fragments de rang ne sont jamais adjacents.
    assert "_v3_v2" not in nom and "_v2_v3" not in nom
    # Controle negatif : sur un lot NON versionne, il n'y a qu'un fragment.
    assert naming.build_sheets_pdf_filename(
        "demo", "R", "R_24", version_rank=2,
        template_id=_GABARIT).count("_v") == 1


# ---------------------------------------------------------------------------
# Les TROIS porteurs, mesures ensemble et separement.
# ---------------------------------------------------------------------------


@pytest.fixture
def make_manifest():
    return _fabrique_de_manifeste()


#: Blocs de texte qui portent l'IDENTITE de la feuille. Les blocs techniques
#: sont exclus a dessein: ils citent `tid=tpl-a4-portrait-2f-v2`, ou la
#: sous-chaine `v2` apparait pour une raison qui n'a rien a voir avec le rang
#: de tirage -- un controle naif y trouverait « v2 » sur une planche de rang 1.
_BLOCS_D_IDENTITE = ("header_identity", "footer_block")


def _fragment_imprime(page, fragment: str) -> bool:
    """Le fragment est-il REELLEMENT TYPOGRAPHIE sur cette page ?

    **Ce helper existe parce que le test qui l'a precede etait tautologique**,
    et le defaut qu'il masquait vidait la story de son sens. La premiere
    redaction assertait `page.text.sheet_label.endswith("_v2")` -- c'est-a-dire
    l'attribut Python que le compositeur venait de construire, jamais un bloc
    de texte. Or `sheet_label` n'est PLUS typographie depuis la geometrie v2,
    qui est le DEFAUT : le rang n'etait imprime nulle part dans le regime
    nominal, deux tirages sortis de l'imprimante etaient typographiquement
    identiques, et le test restait vert.

    Il parcourt donc les `TextBlock` reellement composes, la seule chose qui
    finisse sur du papier.
    """
    return any(
        fragment in ligne
        for bloc in page.text.blocks if bloc.name in _BLOCS_D_IDENTITE
        for ligne in bloc.lines
    )


def test_les_TROIS_porteurs_concordent_sur_une_planche_versionnee(make_manifest):
    """Nom, etiquette imprimee et payload disent le MEME rang.

    Les trois sont assertes dans le meme test parce que c'est leur CONCORDANCE
    qui est la propriete -- trois tests separes passeraient encore si deux
    porteurs se mettaient a dire des rangs differents.
    """
    manifest = make_manifest()
    lot_id = manifest["lots"][0]["lot_id"]
    plan = pdf_composition.compose_lot_plan(
        manifest=manifest, lot_id=lot_id, version_rank=2)

    assert plan.pdf_filename.endswith(f"_{plan.frames_per_page}f-"
                                      f"{plan.orientation[:3]}_v2.pdf")
    for page in plan.pages:
        assert _fragment_imprime(page, "_v2"), (
            "l'etiquette IMPRIMEE ne porte pas le rang: une feuille posee sur "
            "un bureau ne se distingue plus d'un autre tirage"
        )
        assert page.qr.payload[payload_io.VERSION_RANK_FIELD] == 2, (
            "le payload QR ne porte pas le rang: une planche v2 scannee se "
            "reconcilierait sur le lot sans dire de quel tirage elle vient"
        )


def test_une_planche_de_rang_1_ne_porte_le_rang_NULLE_PART(make_manifest):
    """Controle negatif des trois porteurs a la fois. Sans lui, un code qui
    ecrirait `_v1` partout satisferait le test ci-dessus."""
    manifest = make_manifest()
    lot_id = manifest["lots"][0]["lot_id"]
    plan = pdf_composition.compose_lot_plan(manifest=manifest, lot_id=lot_id)

    assert plan.pdf_filename.endswith(f"_{plan.frames_per_page}f-"
                                      f"{plan.orientation[:3]}.pdf")
    for page in plan.pages:
        assert not _fragment_imprime(page, "_v")
        assert payload_io.VERSION_RANK_FIELD not in page.qr.payload
        # Et la lecture tolerante rend bien 1 sur cette absence.
        assert payload_io.payload_version_rank(page.qr.payload) == 1


def test_les_pages_d_un_MEME_tirage_portent_TOUTES_le_rang(make_manifest):
    """Regle des fabriques appliquee a la liste que le code PARCOURT : le plan
    boucle sur les pages, et un rang pose sur la seule premiere page
    laisserait les suivantes indiscernables d'un autre tirage. La fixture
    produit plusieurs pages, et l'assertion porte sur toutes."""
    manifest = make_manifest()
    lot_id = manifest["lots"][0]["lot_id"]
    plan = pdf_composition.compose_lot_plan(
        manifest=manifest, lot_id=lot_id, version_rank=3)
    # `>= 2` et non `>= 1` : le jour ou la fabrique redescendrait a une page,
    # un `>= 1` laisserait ce test VERT tout en cessant silencieusement de
    # mesurer sa propriete -- la regle des fabriques appliquee au controle et
    # non a la fabrique (trouve par l'Acceptance Auditor).
    assert len(plan.pages) >= 2, (
        "la fabrique ne produit plus qu'une page: ce test ne mesure plus rien"
    )
    rangs = {payload_io.payload_version_rank(p.qr.payload) for p in plan.pages}
    assert rangs == {3}, f"toutes les pages ne portent pas le rang 3: {rangs}"
    assert all(_fragment_imprime(p, "_v3") for p in plan.pages)


# ---------------------------------------------------------------------------
# Le PAYLOAD : champ facultatif, defaut tolerant, bornes qui mordent.
# ---------------------------------------------------------------------------


def test_absent_vaut_RANG_1_et_c_est_ce_qui_sauve_le_parc_imprime():
    """Verbatim d'Egan : « les anciens payloads qui ne portaient pas de version
    (2.1) sont tout de meme decodes avec v=1 ».

    Ce defaut ROMPT avec le precedent du depot (`EPIC7-ARB-56` : on monte la
    version de schema et on supprime la branche de lecture ancienne). Il faut
    qu'il le rompe -- applique ici, ce precedent aurait rendu illisible toute
    planche deja sur papier, et une feuille imprimee ne se met pas a jour.
    """
    assert payload_io.payload_version_rank({}) == 1
    assert payload_io.payload_version_rank({"lot_id": "L"}) == 1
    assert payload_io.payload_version_rank({payload_io.VERSION_RANK_FIELD: 4}) == 4


@pytest.mark.parametrize("valeur_abimee", [None, "2", 2.0, True, [], {}])
def test_une_valeur_ABIMEE_se_relit_en_rang_1_plutot_qu_en_panne(valeur_abimee):
    """Une planche dont le QR est mal decode ne doit pas faire tomber la
    relecture : elle vaut rang 1, ce que l'absence vaut deja. Le refus, lui,
    appartient a l'ECRITURE (`validate_payload`), ou l'on peut encore corriger
    -- refuser a la relecture rendrait une feuille papier inexploitable pour un
    defaut qu'elle ne peut plus corriger."""
    assert payload_io.payload_version_rank(
        {payload_io.VERSION_RANK_FIELD: valeur_abimee}) == 1


def _charge_valide(**extra):
    """Un payload d'images VALIDE, auquel les tests n'ajoutent que ce qu'ils
    mesurent.

    Ecrit apres un defaut paye : la premiere redaction posait
    `gamut_map_id="identity"`, invalide, si bien que
    `test_l_ECRITURE_refuse_un_rang_hors_bornes` levait bien une
    `PayloadValidationError` -- mais sur le gamut, pas sur le rang. Il serait
    passe au vert avec un rang parfaitement legal. Une tautologie deguisee,
    exactement la famille de defaut que la revue de cette story a payee trois
    fois ailleurs.
    """
    charge = {
        "schema_version": payload_io.PAYLOAD_SCHEMA_VERSION,
        "project_id": "p", "rush_id": "r", "lot_id": "l",
        "page_index": 0, "page_count": 1,
        "page_role": payload_io.PAGE_ROLE_IMAGES,
        "fps_target": 24.0, "timecode_base_fps": "24/1",
        "template_id": "t", "patch_preset_id": "pp",
        "target_colorspace": "bt709",
        "gamut_map_id": payload_io.GAMUT_MAP_IDENTITY,
        "slots": [{"slot_index": 0, "frame_timecode": "00:00:00:00"}],
    }
    charge.update(extra)
    return charge


def test_la_charge_de_reference_du_banc_est_bien_VALIDE():
    """Controle negatif de la fabrique elle-meme. Sans lui, une charge
    invalide ferait passer au vert tous les tests de refus ci-dessous, quelle
    que soit la valeur qu'ils pretendent mesurer."""
    payload_io.validate_payload(_charge_valide())


@pytest.mark.parametrize("rang_refuse", [0, 1, 100, -1, "2", 2.5, True])
def test_l_ECRITURE_refuse_un_rang_hors_bornes(rang_refuse):
    """Asymetrique de la lecture ci-dessus, et delibere : a l'ecriture le
    document n'est pas encore imprime, donc un refus est reparable."""
    with pytest.raises(payload_io.PayloadValidationError) as refus:
        payload_io.validate_payload(
            _charge_valide(**{payload_io.VERSION_RANK_FIELD: rang_refuse}))
    # Le refus porte bien sur LE RANG, et non sur un autre champ de la charge.
    assert payload_io.VERSION_RANK_FIELD in str(refus.value)


@pytest.mark.parametrize("rang_admis", [2, 3, 98, 99])
def test_l_ECRITURE_admet_les_deux_bornes_exactes(rang_admis):
    """Encadrement ferme des deux cotes : sans lui, une validation qui
    refuserait TOUT rang passerait le test ci-dessus."""
    payload_io.validate_payload(
        _charge_valide(**{payload_io.VERSION_RANK_FIELD: rang_admis}))


def test_le_champ_est_FACULTATIF_et_non_requis():
    """Troisieme famille du contrat. Le mettre dans les champs requis aurait
    refuse toute planche deja imprimee ; le reserver a un role n'aurait pas de
    sens, le rang s'appliquant aux planches d'images."""
    assert payload_io.VERSION_RANK_FIELD in payload_io.OPTIONAL_SCALAR_FIELDS
    assert payload_io.VERSION_RANK_FIELD not in payload_io._REQUIRED_SCALAR_FIELDS
    assert payload_io.VERSION_RANK_FIELD not in payload_io.CALIBRATION_ONLY_FIELDS


def test_la_cle_courte_respecte_la_convention_de_LONGUEUR():
    """`vr` et non `v`. Egan avait ecrit « v pour version » en nommant le SENS ;
    la table a une convention de longueur deliberee (2 a 3 caracteres, jamais
    une lettre par champ) dont le motif tient ici : ce payload voyage IMPRIME,
    et le seul outil garanti sur place est un oeil. Cout : un octet.

    Chiffres de budget : voir le commentaire de `PAYLOAD_SHORT_KEYS`, qui
    porte la mesure des TROIS regimes epingles. Ils ne sont pas repetes ici --
    une seconde ecriture des memes chiffres serait une seconde verite, et
    c'est exactement ce qui les a fait deriver une premiere fois."""
    court = payload_io.PAYLOAD_SHORT_KEYS[payload_io.VERSION_RANK_FIELD]
    assert court == "vr"
    assert 2 <= len(court) <= 3


def test_le_rang_fait_un_ALLER_RETOUR_par_la_serialisation():
    """La projection en cles courtes et son inverse rendent le meme rang. Sans
    ce test, une entree manquante dans la table inverse ferait disparaitre le
    champ ENTIER a la relecture, sur un QR deja imprime."""
    charge = _charge_valide(**{payload_io.VERSION_RANK_FIELD: 7})
    texte = payload_io.serialize_payload(charge)
    assert '"vr":7' in texte, "la cle courte n'est pas celle attendue au fil"
    assert payload_io.payload_version_rank(payload_io.parse_payload(texte)) == 7


# ---------------------------------------------------------------------------
# Le RANG LIBRE : lu au DISQUE, faute de declaration au manifeste.
# ---------------------------------------------------------------------------


def _dossier_de_planches(tmp_path):
    dossier = tmp_path / "planches"
    dossier.mkdir()
    return dossier


def test_un_rang_CONSOMME_ne_se_reutilise_JAMAIS(tmp_path):
    """**Ce test mesurait l'inverse, et l'arbitrage l'a retourne**
    (`EPIC11-ARB-92`, Egan 2026-08-31 : « il ne faut pas rendre le rang, la v2
    a ete consommee par la v3 qui se trouve apres »).

    Il verifiait que le resolveur rendait le TROU -- 1, 2 et 4 pris donnant 3
    -- sur le modele des lots. C'est faux pour une planche, et le motif est
    PHYSIQUE : reutiliser le rang 3 ferait porter « v3 » a deux feuilles
    differentes, dont l'une est deja sortie de l'imprimante. Une fois l'encre
    seche, aucun fichier ne rattrape cela.

    Le trou reste donc un trou : le prochain tirage est le 5.
    """
    dossier = _dossier_de_planches(tmp_path)
    for nom in ("demo_R_24_planches.pdf", "demo_R_24_planches_v4.pdf",
                "demo_R_24_planches_v2.pdf"):
        (dossier / nom).write_bytes(b"pdf")
    assert pdf_composition.resolve_sheets_version_rank(
        tmp_path, project_id="demo", rush_id="R", lot_id="R_24") == 5


def test_un_lot_JAMAIS_imprime_rend_le_rang_1(tmp_path):
    _dossier_de_planches(tmp_path)
    assert pdf_composition.resolve_sheets_version_rank(
        tmp_path, project_id="demo", rush_id="R", lot_id="R_24") == 1


def test_un_dossier_de_planches_ABSENT_rend_le_rang_1(tmp_path):
    assert pdf_composition.resolve_sheets_version_rank(
        tmp_path, project_id="demo", rush_id="R", lot_id="R_24") == 1


def test_les_planches_d_un_AUTRE_lot_ne_prennent_aucun_rang(tmp_path):
    """`planches/` est un dossier PARTAGE par tous les lots du projet -- comme
    `outputs/` pour les masters. Un resolveur qui compterait tout ce qu'il y
    trouve ferait deriver le rang d'un lot au rythme des impressions des
    autres."""
    dossier = _dossier_de_planches(tmp_path)
    for nom in ("demo_AUTRE_12_planches.pdf", "demo_AUTRE_12_planches_v2.pdf",
                "demo_ENCORE_5_planches.pdf"):
        (dossier / nom).write_bytes(b"pdf")
    assert pdf_composition.resolve_sheets_version_rank(
        tmp_path, project_id="demo", rush_id="R", lot_id="R_24") == 1


@pytest.mark.parametrize("geometrie", [None, "v1"])
def test_le_rang_est_imprime_sur_LES_DEUX_geometries(make_manifest, geometrie):
    """Le defaut trouve en revue tenait a une SEULE geometrie : le rang etait
    pose sur `sheet_label`, imprime en v1 et **plus du tout** en v2 -- qui est
    le defaut. Mesurer une seule geometrie laisserait le trou se rouvrir de
    l'autre cote."""
    kw = {} if geometrie is None else {"geometry_version": geometrie}
    manifest = make_manifest()
    lot_id = manifest["lots"][0]["lot_id"]

    avec = pdf_composition.compose_lot_plan(
        manifest=manifest, lot_id=lot_id, version_rank=2, **kw)
    sans = pdf_composition.compose_lot_plan(
        manifest=manifest, lot_id=lot_id, **kw)

    assert _fragment_imprime(avec.pages[0], "_v2"), (
        f"geometrie {geometrie or 'par defaut'}: le rang n'est TYPOGRAPHIE nulle part"
    )
    assert not _fragment_imprime(sans.pages[0], "_v"), (
        f"geometrie {geometrie or 'par defaut'}: un rang apparait au tirage d'ORIGINE"
    )


def test_le_lot_id_imprime_reste_VERBATIM_malgre_le_rang(make_manifest):
    """Le mecanisme de secours 4.6 relit les identifiants IMPRIMES quand le QR
    ne se decode pas. Accrocher le rang au `lot_id` ferait relire un lot qui
    n'existe pas -- c'est pourquoi il vit sur la ligne de pagination."""
    manifest = make_manifest()
    lot_id = manifest["lots"][0]["lot_id"]
    plan = pdf_composition.compose_lot_plan(
        manifest=manifest, lot_id=lot_id, version_rank=2)
    entete = [b for b in plan.pages[0].text.blocks if b.name == "header_identity"]
    assert entete and entete[0].lines[0] == lot_id, (
        "le lot_id imprime n'est plus verbatim: le secours 4.6 relirait un "
        "lot inexistant"
    )


@pytest.mark.parametrize("entier_hors_bornes", [0, 1, -5, 100, 10 ** 30])
def test_un_ENTIER_hors_bornes_se_relit_aussi_en_rang_1(entier_hors_bornes):
    """**Le trou de l'asymetrie, trouve en revue.** Le paramétrage voisin
    listait six valeurs, toutes des erreurs de TYPE. Or la corruption reelle
    d'un QR imprime n'est pas un changement de type : c'est un CHIFFRE QUI
    BASCULE -- `2` lu `0`, `12` lu `102`. Ces valeurs traversaient verbatim,
    et la reconciliation attribuait la feuille a un rang qu'aucun nom de
    fichier, aucune etiquette imprimee et aucun tirage ne portent."""
    assert payload_io.payload_version_rank(
        {payload_io.VERSION_RANK_FIELD: entier_hors_bornes}) == 1


@pytest.mark.parametrize("document_abime", [None, "pas un dict", 42, []])
def test_un_DOCUMENT_qui_n_est_pas_un_dictionnaire_ne_fait_pas_tomber_la_lecture(
        document_abime):
    """Toute la raison d'etre de cette fonction est de survivre a une
    relecture abimee ; lever `AttributeError` serait la panne qu'elle existe
    pour eviter."""
    assert payload_io.payload_version_rank(document_abime) == 1


@pytest.mark.parametrize("booleen", [True, False])
def test_un_BOOLEEN_se_relit_en_rang_1_par_les_BORNES(booleen):
    """Et non par une garde de type dediee : celle-ci serait subsumee.

    La premiere redaction posait `isinstance(valeur, bool)` en tete, et un
    test qui pretendait la mesurer. Mesure faite : le mutant qui SUPPRIME
    cette garde ne fait rougir aucun test, et ne le peut pas -- `True` vaut 1
    et `False` vaut 0, tous deux hors de 2..99, donc les bornes les rendent a
    1 de toute facon. C'etait un mutant EQUIVALENT, pas un survivant : la
    garde a ete retiree plutot que le test bricole autour d'elle.

    Ce qui reste mesure ici est la PROPRIETE, qui elle compte : un booleen ne
    devient jamais un rang.
    """
    rendu = payload_io.payload_version_rank(
        {payload_io.VERSION_RANK_FIELD: booleen})
    # **`rendu is not booleen` ne mesurait RIEN** (trouve en revue, couche 3) :
    # `1 is not True` et `1 is not False` sont vrais par construction, quelle
    # que soit la valeur rendue. La propriete qui compte est que le booleen ne
    # traverse PAS, et elle se mesure sur le type autant que sur la valeur.
    assert rendu == version_ranks.RANG_ORIGINE
    assert not isinstance(rendu, bool), (
        f"un booleen a traverse: payload_version_rank a rendu {rendu!r} "
        f"({type(rendu).__name__})"
    )


def test_les_bornes_du_payload_SONT_IMPORTEES_de_naming():
    """Elles etaient recopiees sous un commentaire affirmant qu'elles etaient
    lues -- porter `naming.VERSION_RANK_MAX` a 50 laissait `payload` accepter
    le rang 99 que le NOM refusait, banc entierement vert.

    **La verification est STRUCTURELLE, et une egalite ne suffit pas ici.**
    Premiere redaction : `payload_io.VERSION_RANK_MAX is naming.VERSION_RANK_MAX`.
    Elle passait meme sur deux litteraux recopies, parce que CPython INTERNE
    les petits entiers (plage -5..256) : `2 is 2` et `99 is 99` valent `True`
    quelle que soit leur origine. Le mutant qui remettait les litteraux
    survivait. C'est l'origine du nom qui doit etre mesuree, pas sa valeur.
    """
    import ast

    arbre = ast.parse(pathlib.Path(payload_io.__file__).read_text(encoding="utf-8"))
    importes = {
        alias.name
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.ImportFrom) and (noeud.module or "").endswith("naming")
        for alias in noeud.names
    }
    assert {"VERSION_RANK_MIN", "VERSION_RANK_MAX"} <= importes, (
        "les bornes ne sont pas IMPORTEES de `naming`: deux emplacements pour "
        "le meme fait sont deux verites (EPIC5-ARB-78)"
    )
    # Et aucune affectation locale ne les redefinit derriere l'import.
    affectees = {
        cible.id
        for noeud in ast.walk(arbre) if isinstance(noeud, ast.Assign)
        for cible in noeud.targets if isinstance(cible, ast.Name)
    }
    assert not ({"VERSION_RANK_MIN", "VERSION_RANK_MAX"} & affectees), (
        "une affectation locale masque l'import des bornes"
    )
    # Controle de coherence, qui ne remplace pas le controle structurel.
    assert payload_io.VERSION_RANK_MAX == naming.VERSION_RANK_MAX


# ---------------------------------------------------------------------------
# L'INVENTAIRE `lots[].sheets_pdfs` -- `EPIC11-ARB-90`, arbitre par Egan le
# 2026-08-31 (« enregistrer ou le PDF a ete ecrit »).
#
# Ce qu'il ferme, et les deux mecanismes le payaient par le MEME defaut :
# `makepdf` n'ecrivait nulle part ou il avait ecrit, si bien que la
# suppression retrouvait la planche en RECALCULANT son nom et que le resolveur
# de rang comptait les tirages en balayant le disque. Un PDF renomme a la main
# echappait aux deux -- et le second cas etait le plus grave : son rang
# redevenait libre, donc reattribue.
# ---------------------------------------------------------------------------


def _manifeste_avec_inventaire(entrees):
    return {"lots": [
        {"lot_id": "AUTRE_24", "sheets_pdfs": [{"path": "planches/x_AUTRE_24_planches.pdf"}]},
        {"lot_id": "R_24", "sheets_pdfs": list(entrees)},
        {"lot_id": "ENCORE_5", "sheets_pdfs": [{"path": "planches/x_ENCORE_5_planches.pdf"}]},
    ]}


def test_un_tirage_RENOMME_garde_son_rang_pris(tmp_path):
    """**Le defaut que cet inventaire ferme, et le plus grave des deux.**

    Le tirage 2 est declare au manifeste mais absent du disque sous son nom
    (quelqu'un l'a renomme). Sans inventaire, le resolveur ne voit rien sur le
    disque et rend 2 : le tirage suivant reprend un rang deja employe. Avec
    l'inventaire, le rang reste pris et le resolveur rend 3.
    """
    dossier = tmp_path / "planches"
    dossier.mkdir()
    (dossier / "demo_R_24_planches.pdf").write_bytes(b"pdf")
    (dossier / "JE-RENOMME-A-LA-MAIN.pdf").write_bytes(b"pdf")  # c'etait le v2
    manifest = _manifeste_avec_inventaire([
        {"path": "planches/demo_R_24_planches.pdf"},
        {"path": "planches/demo_R_24_planches_v2.pdf", "version_rank": 2},
    ])

    sans = pdf_composition.resolve_sheets_version_rank(
        tmp_path, project_id="demo", rush_id="R", lot_id="R_24")
    avec = pdf_composition.resolve_sheets_version_rank(
        tmp_path, project_id="demo", rush_id="R", lot_id="R_24", manifest=manifest)

    assert sans == 2, "controle: sans l'inventaire, le rang 2 est bien reattribue"
    assert avec == 3, "avec l'inventaire, le rang 2 doit rester pris"


def test_le_DISQUE_est_consulte_EN_PLUS_du_manifeste_jamais_a_sa_place(tmp_path):
    """Un fichier present que le manifeste ignore -- ecrit avant cette story,
    ou copie a la main -- doit occuper son rang, sans quoi le tirage suivant
    l'ecraserait. L'inventaire s'AJOUTE au balayage, il ne le remplace pas."""
    dossier = tmp_path / "planches"
    dossier.mkdir()
    (dossier / "demo_R_24_planches.pdf").write_bytes(b"pdf")
    (dossier / "demo_R_24_planches_v3.pdf").write_bytes(b"pdf")  # absent du manifeste
    manifest = _manifeste_avec_inventaire([
        {"path": "planches/demo_R_24_planches_v2.pdf", "version_rank": 2},
    ])
    # 1 (disque), 2 (manifeste) et 3 (disque) employes -> la ligne d'eau est
    # a 3, le prochain tirage est le 4.
    assert pdf_composition.resolve_sheets_version_rank(
        tmp_path, project_id="demo", rush_id="R", lot_id="R_24",
        manifest=manifest) == 4


def test_l_inventaire_d_un_AUTRE_lot_ne_prend_aucun_rang(tmp_path):
    """Regle des fabriques : trois lots, la cible AU MILIEU. `planches/` est un
    dossier partage, et l'inventaire l'est tout autant -- un resolveur qui
    lirait `lots[0]` ferait deriver le rang au rythme des autres lots."""
    (tmp_path / "planches").mkdir()
    manifest = _manifeste_avec_inventaire([])
    assert pdf_composition.resolve_sheets_version_rank(
        tmp_path, project_id="demo", rush_id="R", lot_id="R_24",
        manifest=manifest) == 1


def test_un_manifeste_SANS_inventaire_retombe_sur_le_recalcul(tmp_path):
    """Le champ est ADDITIF. Refuser un manifeste qui ne le porte pas
    priverait de versionnage tous les projets existants -- pire que la
    fragilite qu'on ferme."""
    dossier = tmp_path / "planches"
    dossier.mkdir()
    (dossier / "demo_R_24_planches.pdf").write_bytes(b"pdf")
    assert pdf_composition.resolve_sheets_version_rank(
        tmp_path, project_id="demo", rush_id="R", lot_id="R_24",
        manifest={"lots": [{"lot_id": "R_24"}]}) == 2
