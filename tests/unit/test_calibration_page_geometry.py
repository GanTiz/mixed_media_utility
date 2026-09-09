"""Story 5.16, moitie geometrie: le role de page, la page de calibration, le temoin.

Ce fichier couvre l'AC 3 (type « page de calibration » et sa declaration au payload),
la part preset de l'AC 6 et l'AC 7 (le preset temoin `patches-14-v3`), et la part
geometrique de l'AC 4 (taille de pastille et plafond derives du role).

Trois consignes du depot gouvernent l'ecriture de ces tests, et elles sont rappelees
ici parce qu'elles ont chacune coute une regression au depot:

* **toute capacite est DERIVEE et confrontee au cardinal reel, jamais comparee a un
  litteral.** La capacite laterale a bouge une fois sur trois passes de geometrie, et
  la marge de la page de calibration n'est que de 5 cellules;
* **toute fabrique de collection produit au moins deux elements distinguables, et au
  moins un test place la cible ailleurs qu'en premiere position.** Ce depot s'est fait
  mordre quatre fois par l'appariement invisible (mutants `M33`, `M25`);
* **les frontieres negatives se verifient sur un diff isole**: aucun identifiant de
  secondaire dans le preset temoin, aucun `mire` ni `synthetic` dans le vocabulaire
  introduit.
"""

from __future__ import annotations

import json
import math
from datetime import date
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# La regle de regime -- « une reference de perimetre inatteignable est-elle un
# historique tronque, ou un AUTRE depot ? » -- vit dans `tests/_regime_du_depot.py`,
# ecrite une fois pour ses sept appelants.
sys.path.insert(0, str(REPO_ROOT / "tests"))
from _regime_du_depot import echoue_ou_saute  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import (  # noqa: E402
    page_roles,
    page_templates,
    patch_presets,
    patch_values,
    scan_sorting,
)
from mixed_media_utility.io import payload as payload_io  # noqa: E402
from mixed_media_utility.io import reconstruction  # noqa: E402

#: Le lot de reference des tests de cette story: un gabarit v2 de chaque orientation,
#: **jamais un seul**. Un couple mono-element rend invisible toute erreur
#: d'appariement, et c'est litteralement la regle des fabriques du depot.
V2_TEMPLATES = ("tpl-a4-portrait-4f-v2", "tpl-a4-paysage-6f-v2")


def _payload(
    *,
    page_index: int,
    page_count: int,
    page_role: str,
    slots: list[dict] | None = None,
    template_id: str = "tpl-a4-portrait-4f-v2",
    preset_id: str = "patches-14-v3",
) -> dict:
    """Un payload de page reel, par son vrai producteur.

    Les emplacements sont **distinguables** -- index croissants et timecodes tous
    differents -- pour la raison de la regle des fabriques: un appariement positionnel
    inverse ne se voit pas sur un remplissage uniforme.
    """
    if slots is None:
        slots = [
            {"slot_index": rank, "frame_timecode": f"00:00:0{rank}:1{rank}"}
            for rank in range(2)
        ]
    return payload_io.build_page_payload(
        project_id="projet_demo",
        rush_id="rush_temoin",
        lot_id="lot_temoin_0001",
        page_index=page_index,
        page_count=page_count,
        fps_target=24.0,
        # Story 2.7 (payload 2.1): meme regime que `scan_chain_label` juste en
        # dessous -- requis sous le role images, absent sous le role calibration.
        timecode_base_fps=(
            "" if page_role == page_roles.PAGE_ROLE_CALIBRATION else "25/1"),
        template_id=template_id,
        patch_preset_id=preset_id,
        target_colorspace="rec709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=slots,
        page_role=page_role,
        # AMENDE PAR 5.23 (2026-08-18): le libelle de chaine est **obligatoire** sous le
        # role `c` et **refuse** ailleurs, donc la fabrique le passe conditionnellement
        # au role plutot que toujours. Le passer toujours ferait echouer toutes les
        # planches d'images de ce fichier, et c'est la garde symetrique qui le dirait.
        scan_chain_label=("hp envy 4520 tiff 600 dpi auto corr off"
                          if page_role == page_roles.PAGE_ROLE_CALIBRATION else None),
    )


def _lot_payloads(*, images_pages: int = 3) -> list[dict]:
    """Un lot complet: la page de calibration a l'index 0, puis les planches d'images.

    ``page_count`` **compte** la page de calibration, et c'est une contrainte demontree
    et non un choix: `page_count` est dans `io.reconstruction._LOT_LEVEL_FIELDS`, au
    meme titre que `template_id` et `patch_preset_id`, donc deux pages du meme lot ne
    peuvent pas en declarer deux valeurs differentes.
    """
    page_count = 1 + images_pages
    pages = [_payload(page_index=0, page_count=page_count,
                      page_role=page_roles.PAGE_ROLE_CALIBRATION, slots=[])]
    slot = 0
    for page_index in range(1, page_count):
        slots = []
        for _ in range(2):
            slots.append({"slot_index": slot,
                          "frame_timecode": f"00:00:{slot // 25:02d}:{slot % 25:02d}"})
            slot += 1
        pages.append(_payload(page_index=page_index, page_count=page_count,
                              page_role=page_roles.PAGE_ROLE_IMAGES, slots=slots))
    return pages


# ---------------------------------------------------------------------------
# AC 3 -- le role se declare par un champ de payload nouveau, de niveau page
# ---------------------------------------------------------------------------


def test_the_role_is_a_page_level_payload_field_next_to_the_index() -> None:
    """Un champ **nouveau**, de niveau page, a cote de `page_index`.

    Et surtout pas un `template_id` ni un `patch_preset_id` divergent: les deux sont de
    niveau lot, et une page qui declarerait les siens serait refusee par l'invariant
    d'identite de lot -- pas par une garde qu'on pourrait assouplir.
    """
    assert "page_role" in payload_io._REQUIRED_SCALAR_FIELDS
    champs = list(payload_io._REQUIRED_SCALAR_FIELDS)
    # Le voisinage n'est pas decoratif: c'est ce qui fait lire le role comme une
    # propriete de la page et non du lot.
    assert champs[champs.index("page_count") + 1] == "page_role"
    assert payload_io.PAYLOAD_SHORT_KEYS["page_role"] == "pr"
    # Il est **emis** par tout payload du contrat -- c'est la ligne du dessus -- mais il
    # n'est **pas exige a la relecture**: il a un defaut, et c'est ce qui garde relisible
    # une planche imprimee avant lui (couche 3, majeur M3, corrige a la passe de
    # correction). Les deux implementations de relecture portent le meme defaut, la
    # seconde **relisant** celui de la premiere au lieu de le recopier.
    assert "page_role" not in reconstruction.REQUIRED_PAGE_FIELDS
    assert payload_io.REREAD_DEFAULTS["page_role"] == page_roles.PAGE_ROLE_IMAGES
    assert reconstruction.PAGE_ROLE_DEFAULT_AT_REREAD == (
        payload_io.REREAD_DEFAULTS["page_role"])
    # Et le defaut est le regime **strict**: c'est ce qui fait qu'un defaut mal applique
    # se fait refuser au lieu de passer. Une planche d'images sans emplacement reste
    # refusee, donc un role devine sur une page de calibration echoue bruyamment.
    assert reconstruction.PAGE_ROLE_DEFAULT_AT_REREAD == page_roles.PAGE_ROLE_IMAGES
    # ... et il n'est **pas** de niveau lot. C'est la frontiere negative de l'AC,
    # verifiee par le comportement et non par un grep de diff: deux pages du meme lot
    # declarent deux roles differents et le lot reste un lot.
    assert "page_role" not in reconstruction._LOT_LEVEL_FIELDS


def test_two_pages_of_one_lot_may_declare_two_roles_and_stay_one_lot() -> None:
    """La moitie **comportementale** de la frontiere ci-dessus, qui manquait.

    Le test precedent affirme dans son commentaire que la frontiere est « verifiee par
    le comportement et non par un grep de diff: deux pages du meme lot declarent deux
    roles differents et le lot reste un lot ». Il ne mesurait pourtant que
    l'**appartenance** (`page_role not in _LOT_LEVEL_FIELDS`) -- une propriete de forme,
    vraie sans que la phrase le soit. Ce test-ci fait ce que la phrase annonce.

    **Pourquoi il est ecrit maintenant** (`EPIC5-ARB-95`, 2026-08-19): jusqu'ici la
    promotion de `page_role` au niveau lot etait tenue par deux gardes de **forme** --
    l'appartenance ci-dessus, et la garde d'egalite au source de 5.16, retiree plus bas
    dans ce fichier. Injection ciblee du mutant `D1` (`page_role` ajoute a
    `_LOT_LEVEL_FIELDS`): aucun test de comportement ne le voyait. C'est exactement ce
    que le docstring de la garde retiree revendiquait proteger -- « le role de page
    aurait alors scinde un tirage en deux lots » --, et cela se mesure.

    **La pile est synthetique, et c'est assume.** Depuis l'AC 8bis de 5.23 une vraie page
    de calibration ne declare plus aucune identite de lot
    (`io.payload.CALIBRATION_ABSENT_FIELDS`), et depuis l'AC 10 une pile mixte est
    refusee en amont par `_check_pile_homogene`. La situation reelle correspondante dort
    donc avec les 35 tests de l'AC 11. Ce qui se mesure ici n'est pas cette pile-la mais
    le contrat propre de `_check_lot_consistency`, appelee directement comme le fait deja
    `test_pile_mixte_refus.py`: « quels champs deux pages d'un meme lot doivent-elles
    partager ? ». Le role n'en est pas, et un tirage ne se scinde pas sur lui.
    """
    pile = [_payload(page_index=rang, page_count=3,
                     page_role=page_roles.PAGE_ROLE_IMAGES) for rang in range(3)]
    # Regle des fabriques: trois pages, et celle qui differe n'est **pas** la premiere --
    # une garde qui ne lirait que `payloads[0]` ne se demasquerait pas autrement.
    divergente = dict(pile[1])
    divergente["page_role"] = page_roles.PAGE_ROLE_CALIBRATION
    pile[1] = divergente
    assert len({page["page_role"] for page in pile}) == 2, "les deux roles sont bien la"

    reference = reconstruction._check_lot_consistency(pile)
    assert reference["lot_id"] == "lot_temoin_0001"
    assert reference["page_count"] == 3
    # Et le role ne ressort pas non plus dans la reference de niveau lot: l'y trouver
    # voudrait dire qu'il a ete confronte, donc qu'il est devenu un identifiant de lot.
    assert "page_role" not in reference

    # Temoin: sur la **meme** pile, un champ qui est vraiment de niveau lot fait refuser.
    # Sans lui, l'absence de levee ci-dessus serait vraie meme d'une fonction qui ne leve
    # jamais -- et c'est precisement la forme de test vide que ce depot a deja payee.
    temoin = dict(pile[1])
    temoin["patch_preset_id"] = "patches-12-v1"
    with pytest.raises(reconstruction.ReconstructionError) as refus:
        reconstruction._check_lot_consistency([pile[0], temoin, pile[2]])
    assert "patch_preset_id" in str(refus.value)


def test_the_role_costs_nine_bytes_and_stays_far_from_the_banned_symbol_version() -> None:
    """Cout **mesure** du champ, et le verdict qui compte: la version du symbole.

    Le budget n'est pas ce qui est en jeu (le pire cas atteignable reste a **226** octets
    du plafond dur); la version de symbole l'est, une seule etant bannie -- la 22, que le
    detecteur de production ne lit a aucune taille imprimee.

    **226 et non 230**, corrige au 2026-08-12 avec le mineur m2: le pire cas de ce regime
    pese 542 octets et non 538. Le 538 est celui d'un **autre** regime -- celui de
    `test_payload_short_keys.py`, qui n'a pas le meme gabarit ni le meme preset -- et sa
    marge de 230 y est juste. Deux regimes, deux chiffres: c'est exactement pourquoi ce
    depot exige qu'un cout en octets soit ecrit avec son regime.
    """
    from mixed_media_utility import qr_codes
    from mixed_media_utility.io import naming

    avec = payload_io.serialize_payload(
        _payload(page_index=0, page_count=2, page_role=page_roles.PAGE_ROLE_IMAGES))
    sans = json.dumps(
        {cle: valeur for cle, valeur in json.loads(avec).items()
         if cle != payload_io.PAYLOAD_SHORT_KEYS["page_role"]},
        separators=(",", ":"), ensure_ascii=True)
    assert len(avec.encode("utf-8")) - len(sans.encode("utf-8")) == 9
    assert '"pr":"i"' in avec

    # Le pire cas **atteignable**: trois identifiants a la borne canonique, 8
    # emplacements, champ present. Le regime est nomme parce qu'un cout en octets sans
    # son regime n'est pas une mesure (lecon de la revue de 5.17).
    borne = "z" * naming.CANONICAL_ID_MAX_LENGTH
    pire = payload_io.build_page_payload(
        project_id=borne, rush_id=borne, lot_id=borne,
        page_index=0, page_count=2, fps_target=24.0, timecode_base_fps="25/1",
        template_id="tpl-a4-portrait-8f-m2-v2", patch_preset_id="patches-14-v3",
        target_colorspace="rec709", gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[{"slot_index": rank,
                "frame_timecode": f"00:00:{rank:02d}:{rank:02d}"}
               for rank in range(8)],
        page_role=page_roles.PAGE_ROLE_IMAGES,
    )
    texte = payload_io.serialize_payload(pire)
    octets = len(texte.encode("utf-8"))
    modules = int(qr_codes.encode_qr_image(texte).shape[0])
    # **555 depuis la story 2.7** (542 + 13 octets du champ de cadence source).
    assert octets == 555, octets
    assert payload_io.ALERT_BUDGET_BYTES - octets == 213, octets
    assert octets < payload_io.ALERT_BUDGET_BYTES, octets
    assert (qr_codes.symbol_version(modules)
            not in qr_codes.QR_BANNED_SYMBOL_VERSIONS), modules


def test_the_worst_case_of_the_role_field_is_bounded_on_both_sides_of_its_domain() -> None:
    """Le pire cas est **borne des deux cotes**, sur le domaine entier qu'il pretend borner.

    Mineur m2 de la couche 1: `page_roles` annoncait **534 octets** pour ce pire cas.
    Balayage des 252 couples (gabarit x preset) livres a ce regime: le minimum est
    **537**. 534 n'etait donc atteint par aucun couple -- il etait **sous le minimum du
    domaine qu'il bornait**, donc faux dans le sens qui **sous-estime** le pire cas, meme
    famille que le majeur M1 de la revue de 5.18.

    Ce test existe parce qu'un pire cas ecrit comme un nombre seul ne se verifie pas: il
    faut son **regime** (les trois identifiants a la borne canonique, 8 emplacements,
    champ present) et son **balayage**. Un seul couple mesure aurait laisse passer le 534
    aussi bien que le 542, puisque rien n'aurait dit de quel ensemble le nombre est le
    maximum -- c'est la forme de faux verrou que la revue de cette story reproche ailleurs.

    Le balayage porte sur les octets seuls, qui sont bon marche; la version du symbole
    n'est encodee que sur les **deux extremes**, parce que c'est la que le verdict se joue
    et qu'un encodage par couple couterait 252 QR pour la meme information.
    """
    from mixed_media_utility import qr_codes, page_templates, patch_presets
    from mixed_media_utility.io import naming

    borne = "z" * naming.CANONICAL_ID_MAX_LENGTH
    mesures: dict[tuple[str, str], int] = {}
    for template_id in page_templates.known_template_ids():
        for preset_id in patch_presets.known_preset_ids():
            paie = payload_io.build_page_payload(
                project_id=borne, rush_id=borne, lot_id=borne,
                page_index=0, page_count=2, fps_target=24.0, timecode_base_fps="25/1",
                template_id=template_id, patch_preset_id=preset_id,
                target_colorspace="rec709",
                gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
                slots=[{"slot_index": rank,
                        "frame_timecode": f"00:00:{rank:02d}:{rank:02d}"}
                       for rank in range(8)],
                page_role=page_roles.PAGE_ROLE_IMAGES,
            )
            mesures[(template_id, preset_id)] = len(
                payload_io.serialize_payload(paie).encode("utf-8"))

    # Le domaine lui-meme, epingle: un balayage dont le cardinal derive ne prouve rien.
    # **315 depuis la story 5.23** (63 gabarits x 5 presets): `patches-17-v4` s'ajoute
    # au registre. Les bornes en octets ne bougent pas -- son identifiant a exactement la
    # meme longueur que `patches-14-v3` --, et c'est la longueur seule qui entre dans le
    # payload, jamais le contenu du preset.
    assert len(mesures) == 315, len(mesures)
    minimum, maximum = min(mesures.values()), max(mesures.values())
    # **550/555 depuis la story 2.7** (payload 2.1, +13 octets du champ de cadence
    # source); 537/542 valait depuis la story 5.16.
    assert (minimum, maximum) == (550, 555), (minimum, maximum)
    # Et le chiffre corrige est bien le **maximum**, jamais un point quelconque du domaine.
    assert maximum == 555
    # 534 est sous le minimum: c'est le volet qui aurait attrape l'enonce d'origine.
    assert 534 < minimum, minimum
    assert payload_io.ALERT_BUDGET_BYTES - maximum == 213

    # La version du symbole est **19 aux deux extremes**, donc sur tout l'intervalle des
    # octets rencontres, et jamais la 22 bannie.
    for cible in (minimum, maximum):
        couple = next(clef for clef, taille in mesures.items() if taille == cible)
        paie = payload_io.build_page_payload(
            project_id=borne, rush_id=borne, lot_id=borne,
            page_index=0, page_count=2, fps_target=24.0, timecode_base_fps="25/1",
            template_id=couple[0], patch_preset_id=couple[1],
            target_colorspace="rec709", gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
            slots=[{"slot_index": rank,
                    "frame_timecode": f"00:00:{rank:02d}:{rank:02d}"}
                   for rank in range(8)],
            page_role=page_roles.PAGE_ROLE_IMAGES,
        )
        texte = payload_io.serialize_payload(paie)
        modules = int(qr_codes.encode_qr_image(texte).shape[0])
        assert qr_codes.symbol_version(modules) == 19, (couple, modules)
        assert (qr_codes.symbol_version(modules)
                not in qr_codes.QR_BANNED_SYMBOL_VERSIONS)


def test_an_unknown_short_key_is_refused_rather_than_slipped_into_a_payload() -> None:
    """Un champ nouveau **s'ajoute a la table**, il ne se glisse pas dans un payload.

    C'est la garde que la story 5.17 a posee, et elle mord: sans elle, un champ hors
    contrat partirait sur le papier, ou la machine tierce ne saurait pas le lire et rien
    ne le signalerait.
    """
    document = _payload(page_index=0, page_count=2,
                        page_role=page_roles.PAGE_ROLE_IMAGES)
    document["page_purpose"] = "c"
    with pytest.raises(payload_io.PayloadValidationError) as refus:
        payload_io.serialize_payload(document)
    assert "page_purpose" in str(refus.value)
    assert "un champ nouveau s'y ajoute" in str(refus.value)


def test_an_unknown_role_is_refused_and_never_falls_back_on_the_images_role() -> None:
    document = _payload(page_index=0, page_count=2,
                        page_role=page_roles.PAGE_ROLE_IMAGES)
    document["page_role"] = "calibration"
    with pytest.raises(payload_io.PayloadValidationError) as refus:
        payload_io.validate_payload(document)
    message = str(refus.value)
    assert "page_role" in message
    # Le refus nomme le vocabulaire **et** ses libelles: un operateur doit lire
    # « page de calibration », pas `'c'`.
    for role in page_roles.PAGE_ROLES:
        assert repr(role) in message
        assert page_roles.PAGE_ROLE_LABELS[role] in message


def test_each_role_label_is_pinned_value_by_value_and_not_merely_present() -> None:
    """**Mutant `A02` de la campagne, survivant a la premiere passe.**

    Le mutant permute les deux libelles de `PAGE_ROLE_LABELS`: le refus dit alors
    « page de calibration » la ou la faute porte sur une planche d'images, et
    reciproquement. Il **survivait**, et pour une raison qui est la signature de cette
    famille dans ce depot -- cinquieme occurrence du mutant `M33` de la story 5.6: les
    assertions existantes verifiaient que les libelles **apparaissent** dans le message,
    ce qu'une permutation satisfait aussi bien qu'un appariement juste. Rien de mesurable
    ne bougeait: ni les octets, ni le vocabulaire, ni le type du refus.

    Ce que ce test ajoute est le seul geste qui le tue: l'appariement **valeur par
    valeur**, et la verification que le libelle porte dans un message est bien celui du
    role dont il est question. Un libelle qui dit le contraire de la verite est pire
    qu'un libelle absent -- c'est la seule phrase que l'operateur lit, et elle
    l'enverrait corriger l'autre page.
    """
    assert page_roles.PAGE_ROLE_LABELS[page_roles.PAGE_ROLE_IMAGES] == "planche d'images"
    assert (page_roles.PAGE_ROLE_LABELS[page_roles.PAGE_ROLE_CALIBRATION]
            == "page de calibration")
    assert page_roles.page_role_label(page_roles.PAGE_ROLE_IMAGES) == "planche d'images"
    assert (page_roles.page_role_label(page_roles.PAGE_ROLE_CALIBRATION)
            == "page de calibration")
    # Les deux libelles sont distincts et la table les couvre tous les deux: sans ces
    # deux verrous, l'appariement ci-dessus resterait vrai avec un libelle unique.
    assert set(page_roles.PAGE_ROLE_LABELS) == set(page_roles.PAGE_ROLES)
    assert len(set(page_roles.PAGE_ROLE_LABELS.values())) == len(page_roles.PAGE_ROLES)

    # Et le libelle **arrive au bon message**. Le refus d'une planche d'images sans
    # emplacement doit nommer la planche d'images, et **pas** la page de calibration: un
    # message permute enverrait rescanner la mauvaise page.
    document = _payload(page_index=0, page_count=2,
                        page_role=page_roles.PAGE_ROLE_IMAGES)
    document["slots"] = []
    with pytest.raises(payload_io.PayloadValidationError) as refus:
        payload_io.validate_payload(document)
    message = str(refus.value)
    attendu = page_roles.PAGE_ROLE_LABELS[page_roles.PAGE_ROLE_IMAGES]
    autre = page_roles.PAGE_ROLE_LABELS[page_roles.PAGE_ROLE_CALIBRATION]
    assert f"{page_roles.PAGE_ROLE_IMAGES!r} ({attendu})" in message, message
    assert f"{page_roles.PAGE_ROLE_IMAGES!r} ({autre})" not in message, message

    # Le symetrique, sur le refus de l'autre role: une page de calibration qui porte des
    # emplacements. Sans ce second volet, une permutation resterait invisible du cote ou
    # elle n'est pas eprouvee -- c'est la lecon de la garde `slots`, testee dans les deux
    # sens pour la meme raison.
    calibration = _payload(page_index=0, page_count=2,
                           page_role=page_roles.PAGE_ROLE_CALIBRATION, slots=[])
    calibration["slots"] = [{"slot_index": 0, "frame_timecode": "00:00:00:00"}]
    with pytest.raises(payload_io.PayloadValidationError) as refus:
        payload_io.validate_payload(calibration)
    message = str(refus.value)
    assert f"{page_roles.PAGE_ROLE_CALIBRATION!r} ({autre})" in message, message
    assert f"{page_roles.PAGE_ROLE_CALIBRATION!r} ({attendu})" not in message, message

    # Enfin, le refus d'un plafond de pastilles nomme le role qu'il borne, et c'est le
    # troisieme point d'usage du libelle dans la production.
    from mixed_media_utility import patch_presets as pp

    assert attendu in pp.page_role_label(page_roles.PAGE_ROLE_IMAGES)


def test_a_payload_round_trip_restores_the_role_identically() -> None:
    for role in page_roles.PAGE_ROLES:
        slots = [] if role == page_roles.PAGE_ROLE_CALIBRATION else None
        document = _payload(page_index=0, page_count=2, page_role=role, slots=slots)
        assert payload_io.parse_payload(
            payload_io.serialize_payload(document)) == document


# ---------------------------------------------------------------------------
# AC 3 -- la garde d'emplacements est conditionnelle au role, DANS LES DEUX SENS
# ---------------------------------------------------------------------------

#: Les deux implementations independantes de la garde, et **les deux mordent**. Elles
#: sont parametrees ensemble parce que c'est leur symetrie qui est la propriete: un
#: assouplissement pose d'un seul cote laisserait passer a l'ecriture ce que la
#: relecture refuse, ou l'inverse.
_GARDES = (
    ("ecriture", payload_io.validate_payload, payload_io.PayloadValidationError),
    ("relecture", reconstruction._validate_page_payload, reconstruction.ReconstructionError),
)


@pytest.mark.parametrize("ou,garde,erreur", _GARDES, ids=[nom for nom, _, _ in _GARDES])
def test_empty_slots_are_accepted_under_the_calibration_role(ou, garde, erreur) -> None:
    garde(_payload(page_index=0, page_count=2,
                   page_role=page_roles.PAGE_ROLE_CALIBRATION, slots=[]))


@pytest.mark.parametrize("ou,garde,erreur", _GARDES, ids=[nom for nom, _, _ in _GARDES])
def test_empty_slots_are_refused_under_the_images_role(ou, garde, erreur) -> None:
    """La garde reste **stricte** pour une planche d'images.

    Un assouplissement inconditionnel ferait passer en silence une planche dont le QR a
    perdu ses emplacements, qui est un mode d'echec reel du chemin de scan. Le motif est
    asserte par sa **chaine** et non par le seul type d'exception: c'est le motif qui
    dit a l'operateur laquelle des deux situations il tient en main.
    """
    document = _payload(page_index=0, page_count=2,
                        page_role=page_roles.PAGE_ROLE_IMAGES)
    document["slots"] = []
    with pytest.raises(erreur) as refus:
        garde(document)
    message = str(refus.value)
    assert "slots" in message
    assert repr(page_roles.PAGE_ROLE_IMAGES) in message
    assert repr(page_roles.PAGE_ROLE_CALIBRATION) in message


@pytest.mark.parametrize("ou,garde,erreur", _GARDES, ids=[nom for nom, _, _ in _GARDES])
def test_a_calibration_page_carrying_slots_is_refused_too(ou, garde, erreur) -> None:
    """La conditionnelle mord dans **l'autre** sens, et c'est ce qui tue la permutation.

    Sans ce volet, une garde dont la comparaison de role serait echangee resterait
    verte du cote de la page de calibration: elle accepterait des emplacements sur une
    page qui n'a aucune frame, et le role cesserait de dire quoi que ce soit.
    """
    document = _payload(page_index=0, page_count=2,
                        page_role=page_roles.PAGE_ROLE_CALIBRATION, slots=[])
    document["slots"] = [{"slot_index": 0, "frame_timecode": "00:00:00:00"}]
    with pytest.raises(erreur) as refus:
        garde(document)
    message = str(refus.value)
    assert repr(page_roles.PAGE_ROLE_CALIBRATION) in message
    assert "aucune frame" in message


# ---------------------------------------------------------------------------
# AC 3 -- l'indexation est DETERMINEE: index 0, et un page_count qui la compte
# ---------------------------------------------------------------------------


def test_le_tri_retire_la_page_de_calibration_avant_la_garde_de_coherence() -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 5).

    L'assertion morte etait « le lot **contenant** sa page de calibration se
    reconstruit `complete` ». Ce qui survit est la propriete de fond -- la garde de
    coherence de lot n'est **jamais sollicitee** sur une page de calibration --, et
    le tri la rend vraie par construction plutot que par tolerance: la feuille est
    retiree du lot **avant** toute lecture d'identite.

    Trois planches et non une: une fabrique mono-page rendrait invisible un `find`
    qui rend toujours la premiere page.
    """
    pages = _lot_payloads(images_pages=3)
    a_trier = [
        scan_sorting.PageAtrier(read_rank=rang, locator_source="vrac.pdf",
                                locator_page_index=rang, payload=payload)
        for rang, payload in enumerate(pages)
    ]
    partition = scan_sorting.trier_les_pages(a_trier, project_id_courant="projet_demo")
    assert len(partition.pages_de_calibration) == 1
    assert len(partition.lots) == 1

    # Et la pile qui atteint la reconstruction est **homogene**: elle passe la garde
    # sans avoir a la desserrer.
    planches = [page.payload for page in partition.lots[0].pages]
    section = reconstruction.reconstruct_project_manifest(planches)["reconstruction"]
    assert section["page_count"] == 4
    assert [slot["slot_index"] for slot in section["slots"]] == [0, 1, 2, 3, 4, 5]
    # La page 0 manque du lot: c'est **vrai**, elle n'en est plus une (`EPIC5-ARB-82`).
    assert section["missing_pages"] == [0]


def test_a_missing_calibration_page_is_reported_in_missing_pages_for_free() -> None:
    """Une page de calibration absente est **signalee**, et gratuitement.

    C'est l'autre moitie du corollaire de l'AC: parce que la page vit dans l'espace
    d'index du lot, son absence est exactement une page manquante. Hors de cet espace,
    elle aurait disparu du document sans un mot.
    """
    pages = _lot_payloads(images_pages=3)
    manifest = reconstruction.reconstruct_project_manifest(pages[1:])
    section = manifest["reconstruction"]
    assert section["status"] == "partial"
    assert section["missing_pages"] == [0]


def test_une_page_de_calibration_n_a_aucune_position_dans_l_espace_d_index_d_un_lot() -> None:
    """REECRIT PAR 5.24 (AC 8, classe B).

    L'assertion morte etait « une page de calibration qui declare `page_count = 1`
    est refusee par l'invariant d'identite de lot »: `page_count` est de niveau lot,
    et une page de calibration n'appartient plus a aucun lot. Ce qui survit est le
    fait que le refus gardait: **le tri ne lui attribue aucune position dans
    l'espace d'index d'un lot**.

    Deux feuilles de calibration aux `page_count` **differents** -- 1 et 4 -- sont
    routees de la meme facon, et aucune n'entre dans le lot: si le `page_count`
    d'une page de calibration decidait quoi que ce soit du routage, ces deux-la
    partiraient differemment.
    """
    pages = _lot_payloads(images_pages=3)
    autonome = dict(pages[0])
    autonome["page_count"] = 1
    a_trier = [
        scan_sorting.PageAtrier(read_rank=0, locator_source="a.tiff",
                                payload=autonome),
        scan_sorting.PageAtrier(read_rank=1, locator_source="b.tiff",
                                payload=pages[1]),
        scan_sorting.PageAtrier(read_rank=2, locator_source="c.tiff",
                                payload=pages[0]),
        scan_sorting.PageAtrier(read_rank=3, locator_source="d.tiff",
                                payload=pages[2]),
    ]
    partition = scan_sorting.trier_les_pages(a_trier, project_id_courant="projet_demo")

    assert {page.locator.source_path for page in partition.pages_de_calibration} == {
        "a.tiff", "c.tiff"}
    assert {page.payload["page_count"] for page in partition.pages_de_calibration} == {
        1, 4}
    # Aucune des deux n'a de position dans le lot, et le lot ne compte que ses planches.
    assert len(partition.lots) == 1
    assert {page.locator.source_path for page in partition.lots[0].pages} == {
        "b.tiff", "d.tiff"}


# ---------------------------------------------------------------------------
# Passe de correction de 5.16 -- une planche imprimee AVANT le champ reste
# relisible (couche 3, majeur M3)
# ---------------------------------------------------------------------------


def test_a_sheet_printed_before_the_role_field_is_still_readable() -> None:
    """Le champ etait **requis** sous une version de schema deja posee.

    `page_role` a ete ajoute a `_REQUIRED_SCALAR_FIELDS` et a `REQUIRED_PAGE_FIELDS` sans
    bouger `PAYLOAD_SCHEMA_VERSION`, restee a `2.0` depuis 5.17: deux contrats de payload
    incompatibles partageaient donc le meme numero, et une planche imprimee sous `2.0`
    avant le champ levait `PayloadValidationError` avec « champ requis manquant » -- un
    message qui envoie diagnostiquer un QR abime la ou la feuille est simplement
    anterieure. C'est exactement la divergence silencieuse que 5.17 avait fermee pour les
    cles.

    Le refus est remplace par un **defaut a la relecture**, et le test le mesure sur les
    **deux** chemins de lecture du depot, plus le chemin d'ecriture qui n'a pas le droit
    d'en profiter.
    """
    complet = _payload(page_index=0, page_count=1,
                       page_role=page_roles.PAGE_ROLE_IMAGES)
    ancien = {champ: valeur for champ, valeur in complet.items()
              if champ != "page_role"}
    assert "page_role" not in ancien

    # 1. Le contrat du QR: la validation passe, et le role lu est celui du defaut.
    payload_io.validate_payload(dict(ancien))
    # 2. Le chemin de production reel -- le texte du QR, comme le scan le lit. Le defaut
    #    est pose **au parseur**, donc aucun consommateur n'a de branche « champ absent ».
    texte = payload_io.serialize_payload(ancien)
    assert '"pr"' not in texte
    relu = payload_io.parse_payload(texte)
    assert relu["page_role"] == page_roles.PAGE_ROLE_IMAGES
    # Et il ne remplace **jamais** une valeur presente: la page de calibration relue
    # garde son role.
    calibration = _payload(page_index=0, page_count=2,
                           page_role=page_roles.PAGE_ROLE_CALIBRATION, slots=[])
    assert payload_io.parse_payload(payload_io.serialize_payload(calibration))[
        "page_role"] == page_roles.PAGE_ROLE_CALIBRATION
    # 3. La reconstruction, seconde implementation independante: meme defaut, et il
    #    persiste au document sous le role d'images.
    #
    #    **Repare le 2026-08-18 (story 5.23, AC 11).** Cette moitie passait la page de
    #    calibration du lot **et** ses planches a la reconstruction; depuis l'AC 10 cette
    #    pile recoit `REFUS_PILE_MIXTE` et le test echouait pour une raison qui n'est pas
    #    la sienne -- il porte sur le **defaut de relecture** de `page_role`, pas sur
    #    l'appartenance d'une feuille a un lot. La pile est donc desormais faite de
    #    planches seules, ce qui exerce exactement la meme branche. Ce que la reparation
    #    laisse tomber -- « la page de calibration traverse la reconstruction en gardant
    #    son role » -- est assere deux paragraphes plus haut au niveau du parseur, et son
    #    volet reconstruction vit dans
    #    `test_the_page_role_reaches_the_document_and_is_never_deduced_from_a_rank`,
    #    desactive avec son motif par cette meme AC.
    planches = _lot_payloads(images_pages=3)[1:]
    anciennes = [{champ: valeur for champ, valeur in page.items()
                  if champ != "page_role"} for page in planches]
    # La cible n'est pas seule et n'est pas mono-element (regle des fabriques): trois
    # planches, dont la premiere garde son champ, les deux autres l'ont perdu.
    section = reconstruction.reconstruct_project_manifest(
        [planches[0], *anciennes[1:]])["reconstruction"]
    assert [entree["page_role"] for entree in section["page_roles"]] == [
        page_roles.PAGE_ROLE_IMAGES,
        page_roles.PAGE_ROLE_IMAGES,
        page_roles.PAGE_ROLE_IMAGES,
    ]

    # Frontiere negative, et c'est elle qui empeche le defaut de devenir une tolerance
    # generale: **l'ecriture** ne beneficie d'aucun defaut de relecture pour les onze
    # autres champs. Un `gamut_map_id` absent reste un refus, parce que son defaut serait
    # juste aujourd'hui et faux demain, en silence (story 5.9).
    for champ in payload_io._REQUIRED_SCALAR_FIELDS:
        if champ in payload_io.REREAD_DEFAULTS:
            continue
        ampute = {nom: valeur for nom, valeur in complet.items() if nom != champ}
        with pytest.raises(payload_io.PayloadValidationError):
            payload_io.validate_payload(ampute)


# ---------------------------------------------------------------------------
# Passe de correction de 5.16 -- le role PERSISTE, et la relecture le garde
# (couche 1 B1 par sa cause structurelle, couche 2 F1 et F2)
# ---------------------------------------------------------------------------


def test_le_role_atteint_la_partition_et_ne_se_deduit_jamais_d_un_rang() -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 3) -- **rejoue en premier**.

    C'est l'un des trois de `deferred-work.md`, et le premier des trois par
    priorite: appariement positionnel, chemin fragile nomme du depot. Il a coute
    cinq regressions (`M25`, `M33`, cinq survivants de 5.8), et aucune n'a ete
    trouvee par relecture.

    L'assertion morte etait « le role est persiste AU DOCUMENT DU LOT »: une page
    de calibration n'appartient plus a aucun lot (`EPIC5-ARB-82`), donc elle n'a
    plus d'entree la. Ce qui survit -- et qui est la propriete de fond -- est que
    **le role se lit dans le payload et ne se deduit jamais du rang d'arrivee**.
    Elle vit desormais dans le tri.

    La cible est **ailleurs qu'en premiere position** de la sequence recue, et la
    partition est comparee sous plusieurs ordres d'arrivee.
    """
    pages = _lot_payloads(images_pages=3)
    # Ordre d'arrivee volontairement melange, page de calibration en **derniere**
    # position de la sequence recue.
    melange = [pages[2], pages[1], pages[3], pages[0]]
    a_trier = [
        scan_sorting.PageAtrier(read_rank=rang, locator_source="vrac.pdf",
                                locator_page_index=rang, payload=payload)
        for rang, payload in enumerate(melange)
    ]
    partition = scan_sorting.trier_les_pages(a_trier, project_id_courant="projet_demo")

    # La page de calibration est routee par son ROLE, quelle que soit sa position.
    assert [page.payload["page_role"] for page in partition.pages_de_calibration] == [
        page_roles.PAGE_ROLE_CALIBRATION]
    assert len(partition.lots) == 1
    assert [page.payload["page_role"] for page in partition.lots[0].pages] == [
        page_roles.PAGE_ROLE_IMAGES] * 3
    # Et les planches gardent **leurs** index, jamais ceux de leur rang d'arrivee.
    assert [page.payload["page_index"] for page in partition.lots[0].pages] == [1, 2, 3]

    # Independance de l'ordre: la meme entree dans l'ordre nominal rend la meme
    # partition, localisateurs compris.
    nominal = [
        scan_sorting.PageAtrier(read_rank=rang, locator_source="vrac.pdf",
                                locator_page_index=melange.index(payload),
                                payload=payload)
        for rang, payload in enumerate(pages)
    ]
    autre = scan_sorting.trier_les_pages(nominal, project_id_courant="projet_demo")
    assert [page.locator for page in autre.lots[0].pages] == [
        page.locator for page in partition.lots[0].pages]
    assert [page.locator for page in autre.pages_de_calibration] == [
        page.locator for page in partition.pages_de_calibration]


def test_deux_pages_de_calibration_dans_un_vrac_sont_deux_entrees_de_chaine() -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 7).

    L'assertion morte etait « deux pages de calibration dans un lot sont un
    **refus** ». Elles ne sont plus un conflit **de lot** puisqu'elles
    n'appartiennent a aucun lot: ce sont deux entrees de chaine, et le vrac les
    consigne toutes les deux (`EPIC5-ARB-107`).

    La cible n'est pas en premiere position: c'est la **seconde** page de
    calibration qui doit etre vue, et un routage qui ne regarderait que la premiere
    page passerait.
    """
    pages = _lot_payloads(images_pages=3)
    doublon = dict(pages[2])
    doublon["page_role"] = page_roles.PAGE_ROLE_CALIBRATION
    doublon["slots"] = []
    # Les deux feuilles sont **distinguables**: sans quoi « deux entrees » ne se
    # mesure pas.
    a_trier = [
        scan_sorting.PageAtrier(read_rank=0, locator_source="p0.tiff",
                                payload=pages[0]),
        scan_sorting.PageAtrier(read_rank=1, locator_source="p1.tiff",
                                payload=pages[1]),
        scan_sorting.PageAtrier(read_rank=2, locator_source="p2.tiff",
                                payload=doublon),
        scan_sorting.PageAtrier(read_rank=3, locator_source="p3.tiff",
                                payload=pages[3]),
    ]
    partition = scan_sorting.trier_les_pages(a_trier, project_id_courant="projet_demo")

    assert [page.locator.source_path for page in partition.pages_de_calibration] == [
        "p0.tiff", "p2.tiff"]
    assert len(partition.lots) == 1
    assert [page.locator.source_path for page in partition.lots[0].pages] == [
        "p1.tiff", "p3.tiff"]
    assert partition.cardinal_total == 4


# **Motif corrige le 2026-08-19, apres mesure**: la situation ecrite ici annoncait le
# refus de pile, comme ses cinq voisines de ce fichier. Mesure faite en reveillant le
# test en arbre isole: ce n'est pas ce refus-la qui tombe. Le test permute les roles de
# la page 0 et de la page 2 SANS rendre a la page 0 les quatre champs de niveau lot que
# `build_page_payload` lui avait retires sous le role `c`; `_validate_page_payload`,
# qui passe avant la garde de pile, la refuse donc pour payload incomplet.
def test_la_position_d_arrivee_d_une_page_de_calibration_est_sans_effet() -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 3).

    L'assertion morte etait « une page de calibration ailleurs qu'a l'index 0 est
    **refusee** »: la position dans un lot n'a plus de sens pour une feuille qui
    n'appartient a aucun lot. Ce qui survit est la propriete de fond -- **le
    routage ne depend ni de l'index declare, ni du rang d'arrivee**.

    Le meme vrac est trie deux fois: la feuille de calibration porte l'index 0 puis
    l'index 2, et arrive en premiere puis en troisieme position. La partition doit
    etre la meme, aux localisateurs pres.
    """
    pages = _lot_payloads(images_pages=3)
    routages = []
    for index_declare in (page_roles.CALIBRATION_PAGE_INDEX, 2):
        calibration = dict(pages[0])
        calibration["page_index"] = index_declare
        planches = [pages[1], pages[3]]
        arrivee = ([("c.tiff", calibration)]
                   + [("p1.tiff", planches[0]), ("p3.tiff", planches[1])]
                   if index_declare == page_roles.CALIBRATION_PAGE_INDEX else
                   [("p1.tiff", planches[0]), ("p3.tiff", planches[1])]
                   + [("c.tiff", calibration)])
        a_trier = [
            scan_sorting.PageAtrier(read_rank=rang, locator_source=source,
                                    payload=payload)
            for rang, (source, payload) in enumerate(arrivee)
        ]
        partition = scan_sorting.trier_les_pages(
            a_trier, project_id_courant="projet_demo")
        routages.append((
            [page.locator.source_path for page in partition.pages_de_calibration],
            [[page.locator.source_path for page in lot.pages]
             for lot in partition.lots],
        ))
    assert routages[0] == routages[1], routages
    assert routages[0] == (["c.tiff"], [["p1.tiff", "p3.tiff"]])


def test_un_lot_sans_planche_n_existe_pas_dans_la_partition() -> None:
    """REECRIT PAR 5.24 (AC 8, classe B ; AC 9, entree 2 de `deferred-work.md`).

    L'assertion morte etait « un lot entierement lu sans aucune planche d'images
    est **refuse** ». La question laissee ouverte par `deferred-work.md` -- « un lot
    partiellement scanne dont seule la page de calibration a ete lue doit-il rester
    un refus ou redevenir un `partial` ? » -- est **tranchee par cette story**: ni
    l'un ni l'autre. Apres le tri, une page de calibration n'appartient a aucun
    lot ; un lot dont **aucune planche** n'a ete lue **n'apparait pas** dans la
    partition, et la feuille est routee vers sa chaine.

    Meme forme de reponse qu'`EPIC5-ARB-92`: la question etait posee sur un regime
    qui n'existe plus.

    Le temoin negatif est indispensable et il est ici: un vrac qui porte **aussi**
    une planche fait bien apparaitre son lot. Une partition qui ne rendrait jamais
    de lot passerait la premiere moitie.
    """
    seule = _payload(page_index=0, page_count=1,
                     page_role=page_roles.PAGE_ROLE_CALIBRATION, slots=[])
    partition = scan_sorting.trier_les_pages(
        [scan_sorting.PageAtrier(read_rank=0, locator_source="c.tiff",
                                 payload=seule)],
        project_id_courant="projet_demo")
    assert partition.lots == ()
    assert len(partition.pages_de_calibration) == 1
    assert partition.reliquat == () and partition.hors_perimetre == ()

    # Temoin negatif: la meme feuille **plus** une planche fait apparaitre le lot.
    pages = _lot_payloads(images_pages=3)
    avec_planche = scan_sorting.trier_les_pages(
        [scan_sorting.PageAtrier(read_rank=0, locator_source="c.tiff",
                                 payload=seule),
         scan_sorting.PageAtrier(read_rank=1, locator_source="p1.tiff",
                                 payload=pages[1])],
        project_id_courant="projet_demo")
    assert len(avec_planche.lots) == 1
    assert [page.locator.source_path for page in avec_planche.lots[0].pages] == [
        "p1.tiff"]


@pytest.mark.parametrize("role_inconnu", ["x", "X", "images", "c ", 0, True])
def test_an_unknown_role_is_refused_at_reread_and_never_blamed_on_the_images_role(
    role_inconnu,
) -> None:
    """**F2 de la couche 2**: un role hors vocabulaire etait **accepte** a la relecture.

    Deux mesures de la couche 2, et la seconde est la plus nette: `page_role = 'x'` avec
    des emplacements etait accepte (`status = complete`), et la meme page **sans**
    emplacement recevait un refus qui **attribuait le role `'i'`** -- un message qui
    nomme le mauvais role envoie diagnostiquer la mauvaise chose. C'est litteralement le
    defaut que l'implementation soeur d'`io.payload` a pris soin d'eviter, en validant le
    role **avant** la garde d'emplacements; la seconde implementation ne portait pas ce
    volet.

    Les deux formes sont exercees -- avec et sans emplacement -- parce que ce sont deux
    branches differentes du code fautif, et le refus doit nommer le role **declare**.
    """
    pages = _lot_payloads(images_pages=3)
    for slots in ([{"slot_index": 80, "frame_timecode": "00:00:08:00"}], []):
        fautive = dict(pages[1])
        fautive["page_role"] = role_inconnu
        fautive["slots"] = slots
        with pytest.raises(reconstruction.ReconstructionError) as refus:
            reconstruction.reconstruct_project_manifest(
                [pages[0], fautive, pages[2], pages[3]])
        message = str(refus.value)
        assert "Role de page inconnu" in message, (role_inconnu, slots, message)
        # Frontiere negative: le refus ne parle **pas** des emplacements, et n'attribue
        # aucun role au hasard. Le libelle du role d'images ne doit pas y figurer.
        assert page_roles.PAGE_ROLE_LABELS[page_roles.PAGE_ROLE_IMAGES] not in (
            message.split("Vocabulaire ferme")[0]), message


def test_two_pages_of_the_same_lot_carry_the_same_lot_level_identifiers() -> None:
    """Le role varie, les trois champs de niveau lot ne varient pas.

    C'est la propriete qui a dimensionne l'AC 3 tout entiere, et elle se verifie par le
    comportement: le lot passe, donc aucun des trois champs n'a diverge.
    """
    pages = _lot_payloads(images_pages=3)
    roles = {page["page_role"] for page in pages}
    assert roles == set(page_roles.PAGE_ROLES)
    for champ in ("template_id", "patch_preset_id", "page_count"):
        assert len({page[champ] for page in pages}) == 1, champ


# ---------------------------------------------------------------------------
# AC 3 -- la mise en page se derive du couple (template_id, role de page)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template_id", V2_TEMPLATES)
def test_the_same_template_id_yields_two_different_layouts(template_id) -> None:
    """Deux pages du meme lot, meme `template_id`, mises en page **differentes**.

    C'est la consequence semantique que l'AC demande d'assumer et d'ecrire dans le
    module: `template_id` cesse d'etre une description complete de ce qui est imprime
    sur une page donnee.
    """
    images = patch_presets.resolve_page_layout(
        template_id, page_roles.PAGE_ROLE_IMAGES)
    calibration = patch_presets.resolve_page_layout(
        template_id, page_roles.PAGE_ROLE_CALIBRATION)
    assert images.template_id == calibration.template_id == template_id
    # Les quatre attributs de la mise en page diffe:rent, et chacun pour une raison
    # nommee. Les epingler **un par un** et non par une inegalite globale: une
    # inegalite d'objets serait vraie meme si un seul attribut bougeait, y compris le
    # role lui-meme, ce qui serait une tautologie.
    assert images.frame_zones_mm and calibration.frame_zones_mm == ()
    assert images.patch_size_mm != calibration.patch_size_mm
    assert images.patch_ceiling != calibration.patch_ceiling
    assert images.patch_placement != calibration.patch_placement
    assert calibration.patch_placement == page_templates.WITNESS_PLACEMENT_LATTICE


@pytest.mark.parametrize("template_id", V2_TEMPLATES)
def test_an_images_sheet_prints_six_millimetre_patches_and_the_calibration_page_twelve(
    template_id,
) -> None:
    """Le couple role -> taille de pastille, epingle **valeur par valeur**.

    Une inegalite ne suffirait pas: les deux tailles permutees la satisferaient
    aussi, et c'est exactement le mutant `M33` -- quatre fois rencontre dans ce depot.
    A 12 mm sur une planche d'images, la premiere colonne mord dans la zone de dessin;
    a 6 mm sur la page de calibration, le carre mesure tombe de moitie sur la page dont
    depend toute la correction du lot.
    """
    geometry = page_templates.get_template(template_id).geometry
    assert patch_presets.patch_size_mm_for(
        template_id, page_roles.PAGE_ROLE_IMAGES) == geometry.patch_size_mm == 6.0
    assert patch_presets.patch_size_mm_for(
        template_id, page_roles.PAGE_ROLE_CALIBRATION) == 12.0
    # Et la taille arrive bien jusqu'aux pastilles reellement posees, des deux cotes.
    for patch in patch_presets.resolve_patch_layout(template_id, "patches-14-v3"):
        assert patch.size_mm == 6.0
    for patch in patch_presets.resolve_calibration_page_patches(template_id):
        assert patch.size_mm == 12.0


@pytest.mark.parametrize("template_id", V2_TEMPLATES)
def test_the_patch_ceiling_is_derived_from_the_role_and_the_constant_is_not_raised(
    template_id,
) -> None:
    """Le plafond est **derive du role**, et `MAX_PATCHES_PER_PAGE` n'est pas releve.

    Relever 36 a 141 le rendrait faux pour les planches d'images, qui sont le cas ou il
    protege: son propre commentaire le documente comme mesure « dans les bandes
    laterales libres », donc a cote d'une bande de frames. Une page de calibration n'en
    a pas.
    """
    spec = page_templates.get_template(template_id)
    assert patch_presets.MAX_PATCHES_PER_PAGE == 36
    assert patch_presets.patch_ceiling_for(
        template_id, page_roles.PAGE_ROLE_IMAGES) == patch_presets.MAX_PATCHES_PER_PAGE
    derive = spec.geometry.calibration_grid(
        spec.orientation, patch_presets.CALIBRATION_PATCH_SIZE_MM).capacity
    assert patch_presets.patch_ceiling_for(
        template_id, page_roles.PAGE_ROLE_CALIBRATION) == derive
    assert derive > patch_presets.MAX_PATCHES_PER_PAGE


def test_the_images_ceiling_guard_is_active_and_refuses_with_its_own_number(
    monkeypatch,
) -> None:
    """**Mutant `E06`**: la garde de plafond lit le role de calibration au lieu du role
    d'images.

    Sous les presets livres elle est **inerte dans les deux variantes** -- le plus riche
    en pose 36, donc ni les 36 du role d'images ni les 141 du role de calibration ne sont
    franchis --, et le mutant survit: la seule assertion qui existait portait sur le
    **helper** `patch_ceiling_for`, pas sur son emploi dans `resolve_patch_layout`. Or la
    story affirme que « la garde de `patch_presets.py:924` reste active »: une garde qu'on
    affirme active et que rien n'exerce n'est pas une garde, c'est un commentaire.

    Le geste qui la rend mordante est de **franchir** le plafond, ce qu'aucun couple livre
    ne fait: on substitue un preset et son placement, et on exige que le refus nomme le
    plafond **des planches d'images** (36) et non celui de la grille de calibration. C'est
    le nombre qui distingue les deux roles; le type d'exception, lui, serait le meme.

    La substitution porte sur les deux registres prives ensemble, parce que
    `resolve_patch_layout` verifie d'abord la coherence preset / placement: n'en
    substituer qu'un ferait echouer le test sur l'autre garde, celle de la repetition, et
    il passerait alors pour la mauvaise raison.
    """
    template_id = V2_TEMPLATES[0]
    trop = patch_presets.MAX_PATCHES_PER_PAGE + 4
    faux = patch_presets.PatchPreset(
        preset_id="patches-trop-v3",
        values_version="patch-values-3",
        # Autant de valeurs **distinguables** que de pastilles, en repetition 1: la garde
        # de coherence preset / placement passe alors, et c'est bien le plafond qui parle.
        value_ids=tuple(
            patch_presets.get_patch_preset("patches-14-v3").value_ids
        )[:1] * 1,
        repetition=trop,
    )
    placement = tuple(
        (faux.value_ids[0], 5.0 + rang, 40.0) for rang in range(trop)
    )
    monkeypatch.setitem(patch_presets._PRESETS, faux.preset_id, faux)
    monkeypatch.setitem(patch_presets._PLACEMENTS, (template_id, faux.preset_id),
                        placement)
    with pytest.raises(patch_presets.UndefinedPlacementError) as refus:
        patch_presets.resolve_patch_layout(template_id, faux.preset_id)
    message = str(refus.value)
    assert str(trop) in message, message
    # **Le plafond nomme est celui des planches d'images**, et pas celui de la grille de
    # calibration: c'est la seule chose qui distingue les deux roles ici.
    assert str(patch_presets.MAX_PATCHES_PER_PAGE) in message, message
    grille = patch_presets.patch_ceiling_for(
        template_id, page_roles.PAGE_ROLE_CALIBRATION)
    assert str(grille) not in message, (grille, message)
    assert page_roles.PAGE_ROLE_LABELS[page_roles.PAGE_ROLE_IMAGES] in message, message
    # Et le plafond des deux roles differe reellement, sans quoi l'assertion ci-dessus
    # serait vraie par accident.
    assert grille != patch_presets.MAX_PATCHES_PER_PAGE


def test_an_unknown_role_never_resolves_to_a_guessed_layout() -> None:
    for appel in (patch_presets.patch_size_mm_for, patch_presets.patch_ceiling_for,
                  patch_presets.resolve_page_layout):
        with pytest.raises(page_roles.UnknownPageRoleError):
            appel(V2_TEMPLATES[0], "planche")


# ---------------------------------------------------------------------------
# AC 4 (part geometrique) -- la grille du treillis, et ses 5 cellules de marge
# ---------------------------------------------------------------------------


def test_the_lattice_cardinal_is_pinned_on_the_descriptor_not_on_a_copied_number() -> None:
    """**130 pastilles**: 65 valeurs sous le seuil de saturation, en double replicat.

    Le cardinal est epingle sur le **descripteur** du treillis -- ses cinq niveaux et
    son seuil de saturation -- et non sur un chiffre recopie. Le 106 du banc etait un
    compte de **lecture** sur un scan particulier, et il n'est pas re-mesurable: les
    scans ne sont pas dans le depot.
    """
    entier = patch_values.calibration_lattice_values()
    filtre = patch_values.calibration_lattice_adjustment_values()
    assert len(entier) == len(patch_values.CALIBRATION_LATTICE_LEVELS) ** 3 == 125
    assert len(filtre) == 65
    # Le filtre est bien celui du seuil declare, et il porte sur la **reference**.
    for value in filtre:
        assert (patch_values.lattice_saturation_8bit(value.rgb)
                <= patch_values.CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT)
    assert len(filtre) * patch_presets.CALIBRATION_LATTICE_REPETITION == 130


def test_the_furniture_zones_return_the_useful_band_and_never_the_whole_step() -> None:
    """**Mutant `T01`**: la **largeur** de l'entete n'etait asseree nulle part.

    Les deux emprises de furniture rendent la **bande utile** de `n` cellules,
    `n * pas - espacement`, et non `n * pas`: la derniere cellule cede son espacement a la
    pastille suivante, qui doit rester a distance. Seule la **hauteur** de l'entete etait
    confrontee a quelque chose (le message de refus de tenue verticale, qui la nomme); sa
    **largeur** et le cote du bloc de QR ne l'etaient pas, et le mutant qui rend le pas
    entier en largeur survivait.

    **La verification est une derivation independante et non la formule recopiee**, sans quoi
    elle serait la tautologie que cette revue reproche ailleurs: la bande utile de `n`
    cellules doit finir exactement ou finit la **pastille** de la derniere cellule, soit
    `(n - 1) * pas + cote_de_pastille`. Les deux expressions sont egales par
    `pas = cote + espacement`, mais elles ne se deduisent pas l'une de l'autre a la lecture
    -- l'une parle de bande, l'autre de pastilles posees, et c'est la seconde qui dit
    *pourquoi* l'espacement se retire.

    Symptome de production si la largeur rendait le pas entier: l'emprise de l'entete
    mordrait de `espacement` sur ce qui suit a droite, et le texte d'identite -- celui dont
    le mecanisme de secours 4.6 exige l'egalite a l'octet -- serait pose sur une bande plus
    large que celle que la grille laisse libre.
    """
    for template_id in V2_TEMPLATES[:3]:
        spec = page_templates.get_template(template_id)
        grille = spec.geometry.calibration_grid(
            spec.orientation, patch_presets.CALIBRATION_PATCH_SIZE_MM)
        cote = grille.patch_size_mm
        pas = grille.step_mm

        entete = grille.header_zone_mm()
        # Origine: l'entete part du coin de la grille, dans les deux directions.
        assert entete[0] == pytest.approx(grille.origin_x_mm)
        assert entete[1] == pytest.approx(grille.origin_y_mm)
        # Largeur -- le volet que `T01` laissait passer -- et hauteur, chacune derivee des
        # **pastilles posees** et non de la formule de bande.
        assert entete[2] == pytest.approx((grille.columns - 1) * pas + cote), template_id
        assert entete[3] == pytest.approx((grille.header_rows - 1) * pas + cote), template_id
        # Et la bande est **strictement plus courte** que le pas entier, d'exactement
        # l'espacement: c'est la frontiere qui rend les deux assertions ci-dessus
        # non triviales.
        assert entete[2] == pytest.approx(
            grille.columns * pas - grille.spacing_mm)
        assert grille.columns * pas - entete[2] == pytest.approx(grille.spacing_mm)
        assert grille.spacing_mm > 0, "un espacement nul rendrait ce test vide"

        # Le bloc de QR suit la meme regle, et il est **carre**.
        qr = grille.qr_zone_mm()
        assert qr[2] == pytest.approx(qr[3]), "le bloc de QR doit rester carre"
        assert qr[2] == pytest.approx((grille.qr_cells - 1) * pas + cote), template_id
        assert grille.qr_cells * pas - qr[2] == pytest.approx(grille.spacing_mm)
        # Il vit **sous** l'entete et au bord gauche: deux origines distinctes, sans quoi
        # une confusion des deux rectangles passerait.
        assert qr[0] == pytest.approx(grille.origin_x_mm)
        assert qr[1] > entete[1], (qr, entete)
        assert grille.qr_cells >= 1 and grille.header_rows >= 1


def test_the_furniture_zones_read_the_right_axis_when_the_two_origins_differ() -> None:
    """**Mutant `T05`**: les deux origines sont **egales sur toute page livree**.

    Le mutant permute `origin_x_mm` et `origin_y_mm` dans `qr_zone_mm`, et il survit meme au
    test ci-dessus -- non parce que celui-ci n'assert pas les origines, mais parce que
    l'origine de la grille **est le degagement de coin, le meme dans les deux directions**:
    28 mm en v2, sur les 30 gabarits. `origin_x == origin_y` partout, donc la permutation
    est **invisible sur les donnees livrees**.

    C'est la sixieme fois que ce depot rencontre cette forme, et c'est le coeur de la regle
    des fabriques: *une permutation ne se voit que si les elements diffèrent*. La reponse est
    la meme qu'ailleurs -- fabriquer les deux valeurs **distinguables** -- et elle est ici
    directe, `CalibrationGrid` etant construite sans detour.

    Ce que la permutation couterait en production le jour ou une geometrie donnerait deux
    degagements differents: le bloc de QR serait pose a l'abscisse du degagement **vertical**,
    donc decale, et il mordrait sur les pastilles ou sortirait de la marge -- en silence,
    puisqu'aucun cardinal ne bouge. Le test n'attend donc pas cette geometrie pour exister.
    """
    grille = page_templates.CalibrationGrid(
        orientation="portrait",
        patch_size_mm=12.0,
        spacing_mm=2.0,
        # **Les deux origines diffèrent**, et c'est tout l'objet de ce test.
        origin_x_mm=28.0,
        origin_y_mm=41.0,
        columns=9,
        rows=17,
        header_rows=1,
        qr_cells=4,
    )
    assert grille.origin_x_mm != grille.origin_y_mm, (
        "les deux origines doivent differer, sans quoi ce test ne discrimine rien")

    entete = grille.header_zone_mm()
    qr = grille.qr_zone_mm()
    # L'entete part du coin, chaque coordonnee sur **son** axe.
    assert entete[0] == pytest.approx(28.0)
    assert entete[1] == pytest.approx(41.0)
    # Le bloc de QR: abscisse sur l'axe **horizontal**, ordonnee decalee de l'entete sur
    # l'axe **vertical**. Une permutation des deux rend 41,0 et 42,0 au lieu de 28,0 et 55,0.
    assert qr[0] == pytest.approx(28.0), qr
    assert qr[1] == pytest.approx(41.0 + 1 * grille.step_mm), qr
    assert qr[1] == pytest.approx(55.0), qr
    # Et le cote reste celui de la bande utile, carre.
    assert qr[2] == pytest.approx(qr[3])
    assert qr[2] == pytest.approx(4 * grille.step_mm - 2.0)


@pytest.mark.parametrize("cote", [4.0, 6.0, 8.0, 10.0, 11.0, 12.0, 13.0, 14.0, 16.0])
def test_a_furniture_block_always_leaves_room_for_what_it_reserves(cote) -> None:
    """La promesse de `_cells_for_mm`, verifiee sur un domaine et non au seul cote livre.

    **Mutant `D04` de la campagne**: il retire l'espacement du calcul
    (`ceil(besoin / pas)` au lieu de `ceil((besoin + espacement) / pas)`). Au cote livre
    de 12 mm il est **equivalent** -- les deux formes rendent 1 rangee d'entete et 3
    cellules de QR --, donc aucune capacite ne bouge, aucune pastille ne se deplace, et
    aucun test de la story ne peut le voir. Ce n'est pas pour autant un equivalent tout
    court: a 11 mm de pastille il rend **3** cellules de QR pour un bloc utile de
    3 x 14 - 3 = 39 mm, quand l'emprise majorante du symbole en demande 39,624 -- le
    symbole mordrait sur la premiere pastille du treillis.

    Le geste qui le tue est donc de tester la **propriete** que le helper promet, sur un
    domaine de cotes et pas au seul cote que la production compose: `n` cellules doivent
    laisser au moins ce qu'elles reservent, la bande utile de `n` cellules valant
    `n * pas - espacement` et non `n * pas`. C'est la difference entre verifier un
    resultat et verifier un contrat, et c'est la seule facon d'attraper une formule dont
    une seule valeur est exercee.
    """
    geometry = page_templates.get_geometry("v2")
    grid = geometry.calibration_grid(page_templates.ORIENTATION_PAYSAGE, cote)
    espacement = geometry.patch_spacing_mm
    entete_mm = (page_templates.calibration_header_line_count(
        page_templates.ORIENTATION_PAYSAGE)
        * page_templates.body_line_leading_mm())
    emprise_mm = page_templates.qr_footprint_bound_mm()
    # La bande d'entete loge sa pile de texte...
    assert grid.header_rows * grid.step_mm - espacement >= entete_mm - 1e-9, (
        cote, grid.header_rows)
    # ... et le bloc de QR loge l'emprise **majorante** du symbole.
    assert grid.qr_cells * grid.step_mm - espacement >= emprise_mm - 1e-9, (
        cote, grid.qr_cells)
    # Et les deux comptes sont **minimaux**: une cellule de moins ne suffirait pas. Sans
    # ce volet, une formule genereuse -- deux cellules de marge partout -- passerait le
    # test ci-dessus tout en reprenant des cellules au treillis.
    assert (grid.header_rows - 1) * grid.step_mm - espacement < entete_mm
    assert (grid.qr_cells - 1) * grid.step_mm - espacement < emprise_mm


@pytest.mark.parametrize("orientation", page_templates.ORIENTATIONS)
def test_the_grid_capacity_is_derived_and_confronted_to_the_real_cardinal(
    orientation,
) -> None:
    """La capacite est **derivee**, dans les **deux** orientations, jamais un litteral.

    Avec 5 cellules de marge sur l'orientation limitante, la consigne cesse d'etre une
    precaution de style: la prochaine redefinition de geometrie peut faire tomber cette
    marge sans qu'aucun test ne le dise si le chiffre est recopie.
    """
    geometry = page_templates.get_geometry("v2")
    cardinal = (len(patch_values.calibration_lattice_adjustment_values())
                * patch_presets.CALIBRATION_LATTICE_REPETITION)
    grid = geometry.calibration_grid(
        orientation, patch_presets.CALIBRATION_PATCH_SIZE_MM)
    assert grid.capacity >= cardinal, (orientation, grid.capacity, cardinal)
    # La formule et l'enumeration doivent coincider: si elles divergent, l'une des deux
    # place des pastilles la ou l'autre croit qu'il n'y en a pas.
    assert len(grid.usable_cells_mm()) == grid.capacity


def test_the_header_line_budget_is_derived_from_what_each_grid_can_finance() -> None:
    """Le budget de lignes d'entete est **derive**, orientation par orientation.

    Story 5.23. La page porte desormais cinq mentions imprimees la ou elle en portait
    deux, et une rangee d'entete se paie en cellules reprises au treillis. Le budget de
    chaque orientation est donc le maximum de rangees qu'elle peut financer sans passer
    sous le cardinal du treillis, converti en lignes par l'interligne du corps de texte.

    Il est **derive ici et confronte a la constante**, jamais recopie: c'est exactement
    la consigne de l'en-tete de ce fichier, et elle mord ici plus qu'ailleurs -- la
    marge du portrait vaut **une** cellule.
    """
    geometrie = page_templates.get_geometry("v2")
    cardinal = patch_presets.calibration_lattice_patch_count()
    interligne = page_templates.body_line_leading_mm()
    for orientation in page_templates.ORIENTATIONS:
        grille = geometrie.calibration_grid(
            orientation, patch_presets.CALIBRATION_PATCH_SIZE_MM)
        cellules_hors_qr = grille.columns * grille.rows - grille.qr_cells ** 2
        rangees = (cellules_hors_qr - cardinal) // grille.columns
        assert rangees >= 1, (orientation, rangees)
        bande_mm = rangees * grille.step_mm - grille.spacing_mm
        lignes = int(bande_mm / interligne + 1e-9)
        assert page_templates.calibration_header_line_count(orientation) == lignes, (
            orientation, lignes)
        # Et la grille reelle **utilise** ce budget: une rangee de moins ne logerait pas
        # la pile de texte, une de plus repasserait sous le treillis.
        assert grille.header_rows == rangees, (orientation, grille.header_rows)
        assert grille.capacity >= cardinal, (orientation, grille.capacity)

    # Les deux orientations ne financent **pas** le meme budget, et c'est le point: un
    # budget commun couterait l'une ou l'autre -- a 2 lignes le portrait ne peut pas
    # imprimer les mentions, a 5 le paysage ne porte plus son treillis du tout.
    budgets = {orientation: page_templates.calibration_header_line_count(orientation)
               for orientation in page_templates.ORIENTATIONS}
    assert len(set(budgets.values())) == 2, budgets

    # Frontiere negative sur l'idee du **pied de page**: deux rangees contigues portent
    # plus de texte que deux rangees separees, chaque bande perdant l'espacement
    # inter-pastilles a son bord. Un pied couterait donc une ligne au lieu d'en rendre.
    grille = geometrie.calibration_grid(
        page_templates.ORIENTATION_PORTRAIT, patch_presets.CALIBRATION_PATCH_SIZE_MM)
    contigu = int((2 * grille.step_mm - grille.spacing_mm) / interligne + 1e-9)
    separe = 2 * int((grille.step_mm - grille.spacing_mm) / interligne + 1e-9)
    assert contigu > separe, (contigu, separe)


def test_twelve_millimetres_is_the_largest_side_that_fits_both_orientations() -> None:
    """Le balayage du cote, refait a l'execution. 13 mm ne passe plus.

    La conclusion de l'AC 4 est verifiee et non recopiee: c'est le **paysage** qui
    borne, comme partout ailleurs dans cette geometrie.
    """
    geometry = page_templates.get_geometry("v2")
    cardinal = (len(patch_values.calibration_lattice_adjustment_values())
                * patch_presets.CALIBRATION_LATTICE_REPETITION)

    def tient(cote: float) -> bool:
        return all(
            geometry.calibration_grid(orientation, cote).capacity >= cardinal
            for orientation in page_templates.ORIENTATIONS
        )

    assert tient(patch_presets.CALIBRATION_PATCH_SIZE_MM)
    assert not tient(patch_presets.CALIBRATION_PATCH_SIZE_MM + 1.0)
    # Le plus grand cote entier qui tient **est** celui que le module declare: la borne
    # est derivee du balayage, pas posee a cote de lui.
    plus_grand = max(cote for cote in range(4, 20) if tient(float(cote)))
    assert float(plus_grand) == patch_presets.CALIBRATION_PATCH_SIZE_MM
    # AMENDE PAR 5.23. L'orientation limitante **en capacite residuelle** est desormais
    # le **portrait**, et c'est une consequence voulue: il finance 2 rangees d'entete
    # pour porter les cinq mentions, le paysage une seule (voir
    # `CALIBRATION_HEADER_LINE_COUNT`). La capacite tombe donc a 131 en portrait contre
    # 135 en paysage, pour un treillis qui en demande 130.
    #
    # Ce qui n'a **pas** change, et c'est ce que ce test existe pour dire: c'est bien le
    # **paysage** qui borne la taille de pastille, parce que sa grille est plus courte
    # dans la direction ou les rangees se comptent. Les deux enonces coexistent, et les
    # confondre etait facile: on les separe donc explicitement.
    residuelle = min(
        page_templates.ORIENTATIONS,
        key=lambda orientation: geometry.calibration_grid(
            orientation, patch_presets.CALIBRATION_PATCH_SIZE_MM).capacity,
    )
    assert residuelle == page_templates.ORIENTATION_PORTRAIT
    # A 13 mm, **les deux** orientations tombent sous le cardinal du treillis, et c'est
    # ce que le balayage ci-dessus mesure deja: 12 mm est le plus grand cote entier qui
    # tienne partout. Les deux enonces -- « qui borne la taille de pastille » et « qui a
    # le moins de marge » -- ne designent donc plus la meme orientation depuis que le
    # budget d'entete depend de l'orientation, et c'est exactement le genre de
    # coincidence dont ce fichier demande qu'elle soit re-derivee plutot que recopiee.
    treize = {
        orientation: geometry.calibration_grid(orientation, 13.0).capacity
        for orientation in page_templates.ORIENTATIONS
    }
    assert all(capacite < cardinal for capacite in treize.values()), treize


@pytest.mark.parametrize("template_id", V2_TEMPLATES)
def test_the_lattice_is_placed_in_double_replicate_far_from_itself(template_id) -> None:
    """130 pastilles, 65 valeurs, deux copies **eloignees** de chaque valeur.

    Le double replicat n'est pas du confort: sans deux occurrences,
    `replicate_dispersion` n'a rien a mesurer et la garde de divergence devient aveugle.
    Et l'eloignement est ce qui fait que la moyenne par page capture la non-uniformite
    d'eclairage et de scan -- il est **derive** du pas de grille, pas compare a un
    litteral.
    """
    spec = page_templates.get_template(template_id)
    grid = spec.geometry.calibration_grid(
        spec.orientation, patch_presets.CALIBRATION_PATCH_SIZE_MM)
    placed = patch_presets.resolve_calibration_page_patches(template_id)
    assert len(placed) == 130
    par_valeur: dict[str, list[tuple[float, float]]] = {}
    for patch in placed:
        par_valeur.setdefault(patch.value_id, []).append((patch.x_mm, patch.y_mm))
    assert len(par_valeur) == 65
    assert all(len(positions) == 2 for positions in par_valeur.values())
    ecarts = [math.dist(*positions) for positions in par_valeur.values()]
    assert min(ecarts) >= 6 * grid.step_mm, min(ecarts)
    # Aucune valeur du treillis ne porte de cadre imprime: aucune n'est un extreme pur,
    # le plancher des niveaux etant a 8 et le plafond a 245.
    assert all(patch.frame_mm == 0.0 for patch in placed)


@pytest.mark.parametrize("template_id", V2_TEMPLATES)
def test_the_capacity_guard_counts_physical_patches_and_never_truncates_the_lattice(
    template_id, monkeypatch,
) -> None:
    """**Mutant `F10`**: la garde de capacite compare le cardinal des **valeurs** (65) au
    lieu de celui des **pastilles physiques** (130).

    Sur les deux geometries enregistrees il est **equivalent** -- la v2 a de la place pour
    130, la v1 refuse deja a 65 --, donc aucun test de la production ne peut le voir. Ce
    qu'il ouvre est pourtant un mode d'echec **silencieux**, et c'est le pire de cette
    story: pour une capacite comprise entre 66 et 129, la garde mutee accepte, puis
    `zip(valeurs, cellules)` **tronque** -- la page sort avec moins de pastilles que le
    treillis n'en demande, sans un mot. Une page de calibration amputee ajuste la
    correction du lot entier sur un jeu qu'elle ne declare pas.

    La sonde est le cote de **13 mm**, celui que l'AC 4 mesure comme ne passant plus: sa
    capacite vaut 117 en portrait et 111 en paysage, donc exactement dans la bande ou les
    deux gardes divergent. La production doit y **refuser**, et son motif doit citer le
    cardinal des pastilles physiques.
    """
    # A la taille livree, la pose est **complete**: exactement le cardinal du treillis, et
    # les deux replicats pleins. C'est l'invariant que la garde de non-troncature protege.
    poses = patch_presets.resolve_calibration_page_patches(template_id)
    assert len(poses) == patch_presets.calibration_lattice_patch_count() == 130
    assert patch_presets.calibration_page_refusal(template_id) is None

    # A 13 mm, la capacite tombe dans la bande ou un cardinal de valeurs passerait et un
    # cardinal de pastilles ne passe pas. La production refuse.
    monkeypatch.setattr(patch_presets, "CALIBRATION_PATCH_SIZE_MM", 13.0)
    spec = page_templates.get_template(template_id)
    capacite = spec.geometry.calibration_grid(spec.orientation, 13.0).capacity
    valeurs = len(patch_values.calibration_lattice_adjustment_values())
    # La sonde est bien dans la bande: sinon elle ne distinguerait pas les deux gardes.
    assert valeurs < capacite < patch_presets.calibration_lattice_patch_count(), (
        valeurs, capacite)

    refus = patch_presets.calibration_page_refusal(template_id)
    assert refus is not None, capacite
    # Le motif cite le cardinal des **pastilles physiques**, pas celui des valeurs.
    assert str(patch_presets.calibration_lattice_patch_count()) in refus, refus
    assert f"{patch_presets.CALIBRATION_LATTICE_REPETITION} replicats" in refus, refus
    with pytest.raises(patch_presets.UndefinedPlacementError):
        patch_presets.resolve_calibration_page_patches(template_id)


@pytest.mark.parametrize("template_id", V2_TEMPLATES)
def test_no_lattice_patch_overlaps_the_header_the_qr_or_the_page_margin(
    template_id,
) -> None:
    """Rien ne chevauche rien, sur la page de calibration comme sur une planche.

    Les trois furnitures de cette page sont les marqueurs de coin (qui bornent la
    grille), l'entete d'identite et le bloc du QR. La verification porte sur les
    emprises **reelles** rendues par la mise en page, jamais sur une reservation
    recopiee.
    """
    spec = page_templates.get_template(template_id)
    layout = patch_presets.resolve_page_layout(
        template_id, page_roles.PAGE_ROLE_CALIBRATION)
    placed = patch_presets.resolve_calibration_page_patches(template_id)
    reserves = [(zone["name"], (zone["x"], zone["y"], zone["width"], zone["height"]))
                for zone in layout.reserved_zones_mm]
    pastilles = [(patch.value_id, (patch.x_mm, patch.y_mm, patch.size_mm, patch.size_mm))
                 for patch in placed]

    def chevauche(a, b) -> bool:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        return (ax < bx + bw - 1e-9 and bx < ax + aw - 1e-9
                and ay < by + bh - 1e-9 and by < ay + ah - 1e-9)

    marge = spec.geometry.printer_margin_mm
    for nom, rect in pastilles + reserves:
        x, y, width, height = rect
        assert x >= marge - 1e-9, (nom, rect)
        assert y >= marge - 1e-9, (nom, rect)
        assert x + width <= spec.page_width_mm - marge + 1e-9, (nom, rect)
        assert y + height <= spec.page_height_mm - marge + 1e-9, (nom, rect)
    for index, (nom, rect) in enumerate(pastilles):
        for autre_nom, autre in pastilles[index + 1:] + reserves:
            assert not chevauche(rect, autre), (template_id, nom, autre_nom)
    # Les deux reservations ne se chevauchent pas non plus, et le bloc de QR loge bien
    # l'emprise **majorante** du symbole -- pas l'emprise d'un payload particulier, qui
    # rapetisserait avec la charge utile.
    (_, entete), (_, bloc_qr) = reserves
    assert not chevauche(entete, bloc_qr)
    assert bloc_qr[2] >= page_templates.qr_footprint_bound_mm() - 1e-9
    assert entete[3] >= (page_templates.calibration_header_line_count(
        spec.orientation) * page_templates.body_line_leading_mm()) - 1e-9
    # Et les marqueurs de coin restent hors de la grille: son origine **est** le
    # degagement de coin, dans les deux directions.
    assert entete[0] == pytest.approx(spec.geometry.corner_clearance_mm())
    assert entete[1] == pytest.approx(spec.geometry.corner_clearance_mm())


# ---------------------------------------------------------------------------
# AC 6 (part preset) et AC 7 -- le preset temoin
# ---------------------------------------------------------------------------


def test_the_witness_preset_is_exactly_the_arbitrated_fourteen_values() -> None:
    """14 valeurs, 28 pastilles, 14 par cote. Composition epinglee valeur par valeur."""
    preset = patch_presets.get_patch_preset("patches-14-v3")
    assert preset.values_version == "patch-values-3"
    assert preset.repetition == 2
    assert set(preset.value_ids) == {
        "sentinel-red-1", "sentinel-red-2",
        "sentinel-green-1", "sentinel-green-2",
        "sentinel-blue-1", "sentinel-blue-2",
        "sentinel-black-1", "sentinel-white-1",
        "neutral-020", "neutral-245",
        "primary-red", "primary-green", "primary-blue",
        "neutral-065",
    }
    assert len(preset.value_ids) == 14
    assert len(set(preset.value_ids)) == 14
    # Le jeu est exactement la table v3: le preset temoin la consomme en entier, ce qui
    # est ce qui rend la v3 utile et non decorative.
    table = patch_values.get_patch_values_table("patch-values-3")
    assert set(preset.value_ids) == {value.value_id for value in table.values}


def test_no_secondary_identifier_reaches_the_witness_preset() -> None:
    """Frontiere negative de l'AC 7, verifiee par le **role** et pas par un prefixe.

    Les 3 secondaires ne servaient qu'au re-ajustement d'une page deviante, que
    `EPIC5-ARB-57` supprime. Le test lit le role dans `patch_values`, seul point de
    verite: un test sur le prefixe `secondary-` serait vrai par accident si une
    secondaire etait un jour renommee.
    """
    preset = patch_presets.get_patch_preset("patches-14-v3")
    table = patch_values.get_patch_values_table(preset.values_version)
    for value_id in preset.value_ids:
        assert table.get(value_id).role != patch_values.ROLE_SECONDARY, value_id
        assert not value_id.startswith("secondary-"), value_id
    # ... et le temoin negatif: le role existe, et un preset anterieur en porte. Sans
    # lui, l'assertion ci-dessus serait vraie par vacuite si le role disparaissait.
    douze = patch_presets.get_patch_preset("patches-12-v1")
    table_v1 = patch_values.get_patch_values_table(douze.values_version)
    assert any(table_v1.get(value_id).role == patch_values.ROLE_SECONDARY
               for value_id in douze.value_ids)


@pytest.mark.parametrize("orientation", page_templates.ORIENTATIONS)
def test_the_witness_cardinal_is_confronted_to_the_derived_lateral_capacity(
    orientation,
) -> None:
    """La capacite laterale est **derivee** et confrontee au cardinal par cote.

    Ce chiffre a bouge une fois sur trois passes de geometrie (23/14, puis 26/17, puis
    inchange): un litteral aurait refait passer le paysage sous la limite en silence.
    """
    geometry = page_templates.get_geometry("v2")
    preset = patch_presets.get_patch_preset("patches-14-v3")
    par_cote = len(preset.value_ids)  # une colonne par cote sous la v2
    assert geometry.patch_columns_per_side[orientation] == 1
    capacite = geometry.lateral_row_capacity(orientation)
    assert capacite >= par_cote, (orientation, capacite, par_cote)
    # Le preset le plus riche du depot, lui, ne tient **pas** en paysage: c'est le
    # temoin negatif de cette confrontation, sans quoi elle serait vraie pour tout
    # preset et ne mesurerait rien.
    dix_huit = len(patch_presets.get_patch_preset("patches-18-v2").value_ids)
    if orientation == page_templates.ORIENTATION_PAYSAGE:
        assert capacite < dix_huit, (capacite, dix_huit)


def test_the_witness_preset_makes_the_v2_landscape_composable() -> None:
    """**Le gain que l'AC 7 ne revendiquait pas: une orientation redevient utilisable.**

    Mesure avant / apres sur les gabarits paysage de la v2: `patches-18-v2` y est refuse
    sur **tous** les cardinaux (18 par cote pour une capacite de 17), et le preset temoin
    y tient sur tous. « Refuse » n'est pas « plus petit »: c'est un gain
    qualitativement different, et plus fort.
    """
    paysage_v2 = [
        template_id for template_id in page_templates.known_template_ids()
        if page_templates.get_template(template_id).orientation
        == page_templates.ORIENTATION_PAYSAGE
        and page_templates.get_template(template_id).geometry_version == "v2"
    ]
    assert len(paysage_v2) == 15, len(paysage_v2)  # 5 cardinaux x 3 marges
    cardinaux = {page_templates.get_template(t).frames_per_page for t in paysage_v2}
    assert cardinaux == set(
        page_templates.frames_per_page_vocabulary(
            page_templates.ORIENTATION_PAYSAGE, "v2"))

    refuses = 0
    for template_id in paysage_v2:
        with pytest.raises(patch_presets.UndefinedPlacementError):
            patch_presets.resolve_patch_layout(template_id, "patches-18-v2")
        refuses += 1
        placed = patch_presets.resolve_patch_layout(template_id, "patches-14-v3")
        assert len(placed) == 28, template_id
    assert refuses == 15


def test_the_refusal_of_an_unplaceable_couple_names_its_measured_cause() -> None:
    """Point du `deferred-work.md` **rouvert par cette story**, et ferme.

    `_PLACEMENT_UNPLACEABLE` n'etait lu qu'a la construction du registre: le couple
    retombait dans la branche generique « couvert mais pas pour ce preset », qui se lit
    comme une fonctionnalite manquante alors que c'est une impossibilite geometrique
    assumee. Les chiffres du motif sont **calcules** et non recopies.
    """
    with pytest.raises(patch_presets.UndefinedPlacementError) as refus:
        patch_presets.resolve_patch_layout("tpl-a4-paysage-4f-v2", "patches-18-v2")
    message = str(refus.value)
    assert "infaisable" in message
    # Les quatre grandeurs qui font la cause: le cardinal par cote, le pas, la hauteur
    # exigee et celle du couloir.
    for chiffre in ("18 rangee", "6.0 mm", "9.0 mm", "159.0 mm", "151.0", "17 rangee"):
        assert chiffre in message, chiffre
    # Et le geste disponible, parce qu'un refus qui ne dit pas quoi faire est un refus
    # qu'on relit comme un defaut.
    assert "--geometrie v1" in message
    # Le couple est bien composable sous la v1, ce que le message annonce.
    assert len(patch_presets.resolve_patch_layout(
        "tpl-a4-paysage-4f-v1", "patches-18-v2")) == 36


@pytest.mark.parametrize("template_id", V2_TEMPLATES)
def test_the_witness_preset_places_fourteen_per_side_in_double_replicate(
    template_id,
) -> None:
    placed = patch_presets.resolve_patch_layout(template_id, "patches-14-v3")
    assert len(placed) == 28
    colonnes: dict[float, list[str]] = {}
    for patch in placed:
        colonnes.setdefault(patch.x_mm, []).append(patch.value_id)
    assert len(colonnes) == 2, sorted(colonnes)
    for value_ids in colonnes.values():
        assert len(value_ids) == 14
        assert len(set(value_ids)) == 14
    # Les deux copies d'une valeur sont aux extremites opposees de la feuille: c'est ce
    # qui fait que la moyenne par page capture la non-uniformite d'eclairage.
    gauche, droite = sorted(colonnes)
    assert droite - gauche > 100.0, (gauche, droite)


def test_the_v3_table_stays_a_witness_set_and_never_becomes_the_active_version() -> None:
    """La v3 n'est pas active, et la rendre active serait un contresens.

    Elle est le jeu **temoin** d'une planche d'images, pas un jeu d'ajustement: la
    correction s'ajuste sur le treillis de la page de calibration.
    """
    assert patch_values.ACTIVE_PATCH_VALUES_VERSION != "patch-values-3"
    assert "patch-values-3" in patch_values.known_versions()


# ---------------------------------------------------------------------------
# Frontieres negatives verifiees sur le diff de la story
# ---------------------------------------------------------------------------

#: Les fichiers de **production** que cette moitie de story touche, chacun avec la raison
#: pour laquelle elle y va. Enumeres et non derives d'un `git diff`: c'est l'enumeration
#: qui fait echouer le test si la story s'etend a un fichier qu'elle n'avait pas a
#: toucher, et l'inverse -- deriver la liste du diff -- serait comparer le diff a
#: lui-meme.
_FICHIERS_DE_LA_STORY = {
    # Le vocabulaire des roles, module neuf et pur.
    "src/mixed_media_utility/page_roles.py",
    # Le champ de role au contrat du QR, et la garde d'emplacements a l'ecriture.
    "src/mixed_media_utility/io/payload.py",
    # La meme garde a la relecture, seconde implementation independante.
    "src/mixed_media_utility/io/reconstruction.py",
    # La grille du treillis, derivee des constituants de la geometrie.
    "src/mixed_media_utility/page_templates.py",
    # Les derivations indexees par le role, et le preset temoin.
    "src/mixed_media_utility/patch_presets.py",
    # Le role traverse la jonction payload -> budget -> geometrie sans y etre interprete.
    "src/mixed_media_utility/page_payload.py",
    # La page de calibration composee, et `page_count` qui la compte.
    "src/mixed_media_utility/pdf_composition.py",
    # Le fil de la provenance jusqu'au document, et la confrontation du contournement.
    "src/mixed_media_utility/io/scan_manifest.py",
    # Le drapeau de contournement, et la quatrieme nature de page du chemin de scan.
    "src/mixed_media_utility/cli.py",
    # Les deux reperes documentaires de capacite par page, deplaces par les 9 octets.
    "src/mixed_media_utility/qr_codes.py",
    # --- Inscrits par la PASSE DE CORRECTION, avec leur raison -------------------------
    #
    # Cette enumeration a fonctionne exactement comme son docstring l'annonce: les deux
    # fichiers ci-dessous ont fait echouer ce test, ce qui a transforme leur ajout en
    # decision lisible plutot qu'en accident. Ils ne sont pas un elargissement de scope --
    # ils portent chacun un **bloquant** de la revue de la story, et un bloquant hors des
    # fichiers edites reste un bloquant de la story.
    #
    # Les deux derivations de cardinal attendu de 5.6 -- `_expected_frame_count` et
    # `_underfilled_pages` -- supposaient que toute page non derniere porte
    # `frames_per_page` emplacements. La page de calibration est a l'index 0, n'est jamais
    # la derniere, et n'en porte aucun: elle violait les deux hypotheses, et un lot
    # reconstruit depuis des planches seules ne pouvait plus etre declare complet
    # (bloquant B1 de la couche 1).
    "src/mixed_media_utility/scan_output_frames.py",
    # `UnknownCorrectionFormError` **est** un `ValueError`, donc absorbee par le
    # `except ValueError` d'`assess_divergence`: une page divergente de 33 dE76 ressortait
    # `applied` avec `diverges = None`, et precisement en regime **transporte** -- celui
    # pour lequel la garde existe, ou l'identifiant de forme vient du profil importe et ou
    # la validation prealable etait sautee (bloquant B2 de la couche 1, F3 de la couche 2).
    "src/mixed_media_utility/color_calibration.py",
}


def _exige_git_disponible() -> None:
    """Sauter **seulement** si l'arbre juge n'existe pas, jamais s'il repond mal.

    Mineur m5 de la couche 1: les deux frontieres negatives les plus fortes de la story
    rendaient `skip` des que `git` renvoyait un code non nul, et un `skip` a exactement
    l'apparence d'un test qui n'existe pas. Les deux causes sont separees ici: l'absence
    d'arbre a juger est une propriete de l'**environnement** et un `skip` est alors le bon
    verdict; un commit de reference inaccessible dans un arbre bien present est une
    propriete du **depot juge**, et la frontiere doit alors **echouer** -- c'est elle qui
    ne s'evalue pas.

    **Le premier volet est plus large que « `git` est installe », et c'est la correction
    d'une regression mesuree de la passe de correction.** Poser le seul
    `git --version` a rendu les deux frontieres dures dans tout arbre **copie**: le
    `git` d'un bac a sable de campagne de mutation repond parfaitement, mais le
    repertoire n'est pas un arbre de travail, donc `git diff <baseline>` y sort en code
    non nul et la frontiere echouait. Symptome paye immediatement: le **temoin** de
    `campagne_5_16_blind.py` est sorti `TEMOIN ROUGE (avant), campagne annulee`, et
    aucune des trois campagnes de la story ne pouvait plus mesurer un seul mutant. Une
    frontiere de perimetre qui interdit de mesurer les autres frontieres est un mauvais
    echange.

    La distinction posee ici est donc celle que la docstring d'origine revendiquait
    deja sans la tenir: on exige un arbre de travail **dont la racine est celle que ce
    test juge**. Un `skip` ne peut plus alors masquer un historique tronque ou un clone
    superficiel -- dans les deux cas l'arbre est bien la, et l'echec est dur.
    """
    try:
        subprocess.run(["git", "--version"], cwd=REPO_ROOT, capture_output=True,
                       check=True, timeout=60)
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as error:
        pytest.skip(f"git absent de l'environnement: {error}")
    # L'arbre juge doit etre un arbre de travail, **et sa racine doit etre `REPO_ROOT`**.
    # Comparer les racines et non se contenter de `--is-inside-work-tree` est ce qui
    # distingue une copie posee sous un depot etranger (un bac a sable sous `/tmp` qui
    # serait lui-meme versionne) d'un vrai arbre: la premiere repondrait `true` et ferait
    # juger le diff de quelqu'un d'autre.
    try:
        racine = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=60,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError) as error:
        pytest.skip(
            f"aucun arbre de travail git a la racine jugee {REPO_ROOT} ({error}): "
            "arbre copie ou exporte, la frontiere de perimetre n'a pas d'objet ici"
        )
    if not racine or Path(racine).resolve() != Path(REPO_ROOT).resolve():
        pytest.skip(
            f"la racine jugee {REPO_ROOT} n'est pas la racine de l'arbre git "
            f"{racine!r}: arbre copie, la frontiere de perimetre n'a pas d'objet ici"
        )


#: Borne **haute** du diff de production de la story 5.16, ajoutee par la story 5.19.
#:
#: Motif, et il est structurel: la frontiere comparait `1906211..HEAD`, donc elle mesurait
#: « tout ce que le depot a touche depuis 5.16 » et non « ce que 5.16 a touche ». Toute
#: story ulterieure qui modifie un fichier de production la faisait echouer, et les deux
#: seules issues auraient ete de fausser l'enumeration -- y inscrire des fichiers que 5.16
#: n'a jamais edites -- ou de retirer le test. Borner le diff des deux cotes preserve
#: exactement ce que la frontiere garde: le diff `1906211..9b47f95` est, au caractere pres,
#: celui que l'enumeration decrit.
#:
#: La borne est le commit de fin de la story 5.16 (verdict de revue tranche), reperee par
#: son condensat comme la borne basse l'est deja: les deux ont la meme fragilite -- une
#: reecriture d'historique les invaliderait --, et le depot ne reecrit pas une branche
#: active.
_BORNE_HAUTE_DE_LA_STORY = "9b47f95"

#: Borne **basse** du meme diff -- le `baseline_commit` de la story 5.16.
#:
#: **Elle etait ecrite EN LIGNE aux deux sites d'appel, et c'est ce fichier qui
#: faisait exception** : les onze autres bancs de perimetre du depot declarent
#: leur borne basse en constante de module, comme la borne haute ci-dessus l'est
#: deja ici. L'asymetrie s'est payee le 2026-09-08 : la regle de regime de
#: `tests/_regime_du_depot.py` reconnait les references que les bancs
#: DECLARENT -- un litteral en ligne y est indiscernable d'une sonde fabriquee
#: (`"0" * 40`), et les deux frontieres de ce fichier restaient donc rouges sur
#: le depot public quand les vingt-cinq autres sautaient.
#:
#: La sonde de
#: `test_the_perimeter_gate_separates_a_copied_tree_from_a_truncated_history`,
#: elle, reste EN LIGNE, et c'est exactement ce qui la distingue : elle doit
#: continuer d'echouer dur partout.
_BASELINE_DE_LA_STORY = "1906211"


def _diff_de_production(baseline: str, borne_haute: str = _BORNE_HAUTE_DE_LA_STORY
                        ) -> list[str]:
    """Fichiers de production modifies entre `baseline` et `borne_haute`, ou echec nomme.

    L'echec est **dur** et non un `skip`: voir `_exige_git_disponible`.
    """
    try:
        return subprocess.run(
            ["git", "diff", "--name-only", baseline, borne_haute, "--", "src"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=60,
        ).stdout.split()
    except (subprocess.SubprocessError, OSError) as error:
        echoue_ou_saute(
            REPO_ROOT, baseline,
            f"commit de reference {baseline} ou borne haute {borne_haute} inatteignable "
            f"({error}): la frontiere de perimetre ne s'evalue pas, et un skip se lirait "
            "comme un vert. Arbre exporte, historique tronque ou clone superficiel"
        )


def _source_au_baseline(baseline: str, chemin: str) -> str:
    """Source d'un fichier au commit de reference, ou echec nomme. Meme regle que ci-dessus."""
    try:
        return subprocess.run(
            ["git", "show", f"{baseline}:{chemin}"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=60,
        ).stdout
    except (subprocess.SubprocessError, OSError) as error:
        echoue_ou_saute(
            REPO_ROOT, baseline,
            f"commit de reference {baseline} inatteignable pour {chemin} ({error}): la "
            "comparaison au baseline ne s'evalue pas, et un skip se lirait comme un vert"
        )


def test_the_story_touches_no_production_module_outside_its_declared_surface() -> None:
    """Frontiere de perimetre, sur le diff de production isole.

    Ce que ce test protege est ce que les Dev Notes revendiquent: la story ajoute des
    derivations **indexees par le role de page**, dont le comportement pour le role
    « planche d'images » est exactement l'existant. Un module de production qui
    apparaitrait ici sans figurer dans l'enumeration serait un elargissement de scope --
    ce que ce depot interdit explicitement -- et il faudrait alors soit le retirer, soit
    l'inscrire **avec sa raison**, ce qui en fait une decision lisible plutot qu'un
    accident.

    L'enumeration est **exacte** et non une inclusion: un fichier qu'on cesserait de
    toucher doit sortir de la liste, faute de quoi elle deviendrait une liste de souhaits.

    **Le diff est borne des deux cotes depuis la story 5.19** (voir
    `_BORNE_HAUTE_DE_LA_STORY`): borne en bas seulement, il mesurait le depot entier depuis
    5.16 au lieu de la story, et la premiere story suivante qui touchait un module de
    production le faisait echouer sans qu'aucune frontiere de 5.16 ne soit franchie.

    **Le skip est desormais borne** (mineur m5 de la couche 1): il ne couvre plus que
    l'absence de l'outil, jamais un commit de reference inatteignable. Un `skip` se lit
    comme un vert dans un total, et les deux causes ne sont pas de la meme nature -- un
    `git` absent est une propriete de l'environnement, un commit inaccessible (arbre
    exporte, historique tronque, `git clone --depth`) est une propriete du **depot juge**,
    donc une frontiere qui ne s'evalue pas alors qu'elle le devrait.
    """
    _exige_git_disponible()
    touches = _diff_de_production(_BASELINE_DE_LA_STORY)
    assert touches, (
        "aucun fichier de production modifie depuis le commit de reference: la frontiere "
        "ne mesurerait rien")
    assert set(touches) == _FICHIERS_DE_LA_STORY, {
        "en trop": sorted(set(touches) - _FICHIERS_DE_LA_STORY),
        "annonces et non touches": sorted(_FICHIERS_DE_LA_STORY - set(touches)),
    }


def test_the_perimeter_frontier_bites_on_a_file_outside_the_enumeration() -> None:
    """Le second volet, celui qui manquait: la frontiere **echoue** quand elle doit.

    Mineur m5 de la couche 1, dont le geste demande etait « verifier une fois que le test
    echoue sur un fichier volontairement ajoute hors de l'enumeration ». Une comparaison
    d'ensembles qui serait devenue une inclusion, ou dont le membre de gauche serait vide,
    passerait le test precedent sans rien garantir -- c'est le motif « un test peut etre
    vert et vide » que ce depot a paye trois fois.

    La comparaison est exercee **dans les deux directions**, parce qu'une egalite
    d'ensembles remplacee par une inclusion ne se voit que d'un cote a la fois.
    """
    declares = set(_FICHIERS_DE_LA_STORY)
    intrus = declares | {"src/mixed_media_utility/encode.py"}
    assert intrus != declares, "un fichier en trop doit faire echouer la comparaison"
    manquant = declares - {"src/mixed_media_utility/page_roles.py"}
    assert manquant != declares, (
        "un fichier annonce et non touche doit faire echouer la comparaison aussi: "
        "l'enumeration n'est pas une liste de souhaits")
    # Et le diff reel est bien ce qui est confronte a l'enumeration, pas un ensemble vide:
    # `_diff_de_production` rend des chemins, tous sous `src/`.
    _exige_git_disponible()
    touches = _diff_de_production(_BASELINE_DE_LA_STORY)
    assert touches and all(chemin.startswith("src/") for chemin in touches), touches


def test_the_perimeter_gate_separates_a_copied_tree_from_a_truncated_history(
    monkeypatch, tmp_path,
) -> None:
    """Le `skip` est **borne**, et ce test est ce qui le borne (mineur m5, second geste).

    La demande de la revue etait « mieux qu'un `skip` silencieux »: un test qui se tache
    selon l'environnement n'est pas garanti mesure. Le geste de la passe precedente --
    rendre l'echec dur -- allait dans le bon sens et est alle **trop loin**: pose sur le
    seul `git --version`, il a rendu la frontiere dure dans tout arbre copie, et le temoin
    des trois campagnes de mutation de la story est passe rouge, ce qui interdisait de
    mesurer le moindre mutant.

    Les deux causes sont donc separees, et le test les exerce **toutes les deux**, ce qui
    est le seul moyen de garantir qu'aucune ne se degrade en l'autre:

    * pas d'arbre de travail a la racine jugee (copie, export, bac a sable de campagne)
      -> `skip`, parce que la frontiere n'a alors **aucun objet**: il n'y a pas d'histoire
      a juger, et rien de ce que la story a touche n'est observable ici;
    * arbre bien present mais commit de reference inatteignable (historique tronque,
      `clone --depth`) -> **echec dur**, parce que la frontiere devrait s'evaluer et ne
      le fait pas. C'est le volet que le mineur m5 reclamait, et il est conserve.
    """
    # 1. Un repertoire qui n'est pas un arbre de travail: `skip`, jamais d'echec. C'est
    #    exactement la situation d'un bac a sable de campagne de mutation.
    hors_arbre = tmp_path / "copie-sans-histoire"
    hors_arbre.mkdir()
    monkeypatch.setattr(sys.modules[__name__], "REPO_ROOT", hors_arbre)
    with pytest.raises(pytest.skip.Exception) as saute:
        _exige_git_disponible()
    assert "arbre" in str(saute.value).lower(), str(saute.value)

    # 2. Le vrai arbre, avec un commit de reference qui n'existe pas: echec **dur**. Un
    #    `skip` ici se lirait comme un vert alors que la frontiere devrait mordre.
    monkeypatch.setattr(sys.modules[__name__], "REPO_ROOT",
                        Path(__file__).resolve().parents[2])
    _exige_git_disponible()  # l'arbre reel passe la porte, sans skip ni echec
    with pytest.raises(pytest.fail.Exception) as echec:
        _diff_de_production("0" * 40)
    assert "inatteignable" in str(echec.value), str(echec.value)
    with pytest.raises(pytest.fail.Exception):
        _source_au_baseline("0" * 40, "src/mixed_media_utility/page_roles.py")


# ---------------------------------------------------------------------------
# Les trois silences que la story interdit, et qu'aucun test ne regardait
# ---------------------------------------------------------------------------


def test_a_calibration_page_that_cannot_be_composed_says_so_and_says_why() -> None:
    """**Mutant `G07`**: l'impossibilite de composer la page cesse d'etre declaree.

    C'est le silence que ce depot combat partout ailleurs, applique a la page dont
    depend toute la correction. Le mutant survivait parce que le code du motif n'etait
    **asserte nulle part**.

    **Amende par la story 5.22** (`EPIC5-ARB-80`, decision 7), et le motif de l'amendement
    est ce que ce test doit continuer de porter. Avant 5.22, la page etait inseree dans
    chaque lot, donc son impossibilite geometrique ne pouvait etre qu'un **avertissement**
    -- refuser aurait fait perdre l'impression de tout le lot pour une page annexe, et le
    silence a combattre etait celui d'un lot v1 compose sans un mot.

    Depuis 5.22 la page **est** le produit demande par une commande dediee. Un
    avertissement rendrait alors un PDF vide en annoncant un succes: le silence a
    combattre a change de forme, et la garde avec lui -- c'est un **refus**, et il reste
    chiffre. Le code `WARNING_NO_CALIBRATION_PAGE` est conserve dans le message: c'est
    l'identifiant sous lequel ce constat est connu du depot, et le renommer aurait
    debranche ce test de son mutant.

    Le temoin negatif est indispensable, et il a change de nature avec la garde: sous la
    v2 la page se compose (aucun refus), et **aucune** des deux versions ne pose plus de
    page sans frame dans un plan de lot -- c'est la frontiere negative de l'AC 8.
    """
    from mixed_media_utility import pdf_composition

    from test_pdf_composition import (  # noqa: E402
        compose, compose_calibration, images_pages)

    with pytest.raises(pdf_composition.GeometryOverflowError) as refus:
        compose_calibration(geometry_version="v1")
    motif = str(refus.value)
    assert motif.startswith(pdf_composition.WARNING_NO_CALIBRATION_PAGE), motif
    # Le motif est **chiffre**: le cardinal du treillis, la capacite de la grille, et le
    # degagement de coin qui explique l'ecart. Un code sans son motif enverrait chercher
    # une cause ailleurs.
    v1 = compose(geometry_version="v1")
    assert str(patch_presets.calibration_lattice_patch_count()) in motif, motif
    spec = page_templates.get_template(v1.template_id)
    capacite = spec.geometry.calibration_grid(
        spec.orientation, patch_presets.CALIBRATION_PATCH_SIZE_MM).capacity
    assert str(capacite) in motif, motif
    assert f"{spec.geometry.corner_clearance_mm():.0f} mm" in motif, motif

    # Temoin negatif: sous la v2 la page se compose, et elle porte bien son treillis.
    v2_calibration = compose_calibration(geometry_version="v2")
    assert v2_calibration.page_count == pdf_composition.CALIBRATION_ONLY_PAGE_COUNT
    assert v2_calibration.pages[0].patches, "la page composee porte son treillis"

    # **Frontiere negative de l'AC 8, sur les deux versions**: un plan de lot ne porte
    # plus aucune page sans frame. Le tester sur les deux est ce qui distingue « la page
    # n'est plus inseree » de « la v1 ne l'inserait deja pas ».
    v2 = compose(geometry_version="v2")
    for plan in (v1, v2):
        assert len(plan.pages) == len(images_pages(plan)) == plan.page_count


def test_a_scanned_calibration_page_is_never_sent_to_cropping_nor_given_mires() -> None:
    """**Mutants `I09` et `I10`**: la quatrieme nature de page du chemin de scan.

    Sans la branche de role, `build_page_crop_plan` refuse les `slots` vides, le refus est
    rattrape en `frame_crop_failed`, et la page recoit des **mires**: une page
    parfaitement lue declaree en echec et son treillis remplace par des frames de
    synthese. C'est le faux echec symetrique du faux succes que la chaine combat, et il
    portait sur la page dont depend toute la correction du lot.

    Deux pages, et la page de calibration n'est **pas** en premiere position: un
    appariement qui rendrait toujours la premiere entree ne se demasque pas autrement.
    La planche d'images de la fabrique est en echec de detection, ce qui lui fait prendre
    la branche precedente sans aucune I/O -- ce test mesure l'aiguillage, pas le
    recadrage.
    """
    from mixed_media_utility import cli, scan_detection

    def detectee(rang: int, payload: dict, *, ok: bool) -> scan_detection.DetectedPage:
        return scan_detection.DetectedPage(
            read_rank=rang,
            status=scan_detection.PAGE_OK if ok else "page_geometry_failed",
            locator_source=f"scans/p{rang}.tiff",
            locator_page_index=None,
            qr_status="ok",
            page_index=payload["page_index"],
            homography=tuple(range(9)) if ok else None,
            page_size_px=(100, 100),
            payload=payload,
        )

    planche = _payload(page_index=1, page_count=2,
                       page_role=page_roles.PAGE_ROLE_IMAGES)
    calibration = _payload(page_index=0, page_count=2,
                           page_role=page_roles.PAGE_ROLE_CALIBRATION, slots=[])
    rapport = type("Rapport", (), {"pages": (detectee(0, planche, ok=False),
                                             detectee(1, calibration, ok=True))})()

    # Le second membre est la suite des resultats de calibration par page, ajoutee par la
    # story 5.19: elle est vide ici, aucune correction de lot n'etant fournie. Ce que ce
    # test mesure -- l'aiguillage par role -- est inchange.
    pages, calibrations = cli._scanned_pages_for_output(Path("/inexistant"), rapport, 600)
    assert calibrations == ()
    assert len(pages) == 2
    par_index = {page.payload["page_index"]: page for page in pages}
    # La page de calibration: **aucun echec**, donc aucune mire, et aucun plan de decoupe.
    page_zero = par_index[0]
    assert page_zero.failure is None, page_zero.failure
    assert page_zero.crop_plan is None
    assert page_zero.frames == ()
    # La planche d'images, elle, garde son motif d'echec: la branche de role ne l'a pas
    # avalee. Sans ce volet, une branche posee trop haut passerait aussi.
    assert par_index[1].failure == "page_detection_failed"


def test_the_bypass_request_reaches_the_record_from_the_parsed_arguments() -> None:
    """**Mutants `I06` et `I07`**: la demande de contournement n'est plus transportee.

    `scan_command` construit son `ScanRecord` au terme d'une passe de scan complete --
    ingestion, detection, ecriture des frames --, donc l'exercer de bout en bout
    demanderait un lot scanne. Le point d'emission est verifie ici **sur le source**, par
    le meme geste que `test_makepdf_emits_exactly_the_identity_gamut_map` emploie pour la
    compression de gamut, et pour la meme raison: ce qui doit etre garanti est qu'il n'y a
    ni litteral ni valeur devinee a l'endroit ou la demande de l'operateur entre dans la
    couche qui ecrit.

    Ce que l'AST etablit et qu'un test de comportement de la couche d'ecriture n'etablit
    pas: la valeur transportee **vient des arguments analyses** et non d'une constante.
    `I06` (toujours faux) et `I07` (toujours vrai) sont tous deux des constantes.
    """
    import ast

    # **Story 11.4b (lot S1): la mesure est en DEUX temps parce que le chemin
    # l'est.** Le `ScanRecord` se construit desormais dans le module de coeur
    # `scan_write`, qui ne connait aucun `args`; c'est
    # `cli._ecrire_le_lot_detecte` qui lit les arguments analyses une fois et
    # fait descendre la demande en booleen nomme. Les deux hops sont donc lus,
    # et l'invariant en sort plus fort, pas plus faible: ni le point d'emission
    # ni le point de lecture ne peut redevenir une constante.
    coeur = ast.parse(
        (REPO_ROOT / "src" / "mixed_media_utility" / "scan_write.py").read_text(
            encoding="utf-8")
    )
    passages = [
        noeud for noeud in ast.walk(coeur)
        if isinstance(noeud, ast.keyword)
        and noeud.arg == "divergence_bypass_requested"
    ]
    assert len(passages) == 1, "un seul point d'emission, et il est nomme"
    valeur = passages[0].value
    # Pas une constante: ni `True` ni `False` ne disent ce que l'operateur a demande.
    assert not isinstance(valeur, ast.Constant), ast.dump(valeur)
    # Et la valeur lit bien le parametre nomme que l'enveloppeur remplit.
    lu = ast.unparse(valeur)
    assert "divergence_bypass" in lu, lu

    # Second temps: l'enveloppeur remplit ce parametre depuis les arguments
    # analyses, et pas depuis une constante.
    source = ast.parse(
        (REPO_ROOT / "src" / "mixed_media_utility" / "cli.py").read_text(
            encoding="utf-8")
    )
    remplissages = [
        noeud for noeud in ast.walk(source)
        if isinstance(noeud, ast.keyword) and noeud.arg == "divergence_bypass"
    ]
    assert len(remplissages) == 1, "un seul point de lecture, et il est nomme"
    lu_cli = ast.unparse(remplissages[0].value)
    assert not isinstance(remplissages[0].value, ast.Constant), lu_cli
    assert "divergence_bypass" in lu_cli, lu_cli
    assert "args" in lu_cli, lu_cli


def _calibration_plan(**surcharges):
    """Appeler `_calibration_page_plan` **directement**, avec ses arguments explicites.

    En isolation et non a travers `compose_lot_plan`, et le motif est un ordre: la
    composition monte les **planches d'images d'abord**, donc leur propre garde de verbatim
    mordrait avant celle de la page de calibration et le test mesurerait l'autre garde. La
    fonction est l'unite qui porte celle-ci; c'est donc elle qu'on exerce.
    """
    from mixed_media_utility import pdf_composition

    # AMENDE PAR 5.23 (2026-08-18): la feuille ne porte plus ni rush, ni lot, ni
    # cadence, ni pagination -- les quatre etaient faux sur elle. Elle porte a la place
    # le libelle de la chaine de scan, un commentaire libre facultatif et une date.
    arguments = dict(
        spec=page_templates.get_template(V2_TEMPLATES[0]),
        project_id="projet_demo",
        scan_chain_label="hp envy 4520 tiff 600 dpi auto corr off",
        comment=None,
        generated_on=date(2026, 8, 18),
        patch_preset_id="patches-14-v3",
        target_colorspace="rec709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        render_dpi=600,
        markers=(),
    )
    arguments.update(surcharges)
    return pdf_composition._calibration_page_plan(**arguments)


def test_the_calibration_header_is_refused_and_never_truncated(monkeypatch) -> None:
    """**Mutant `G16`**: l'entete de la page de calibration tronque au lieu de refuser.

    AMENDE PAR 5.23, et le **levier** a change avec la feuille. L'enjeu de 5.16 etait le
    `lot_id` imprime, qui rattachait la page a son lot; la feuille ne porte plus de lot.
    Ce qui est desormais irremplacable, c'est le **libelle de la chaine** et le
    **commentaire**: le premier n'existe qu'ici et dans le QR, le second **nulle part
    ailleurs** -- ni QR, ni manifest, ni nom de fichier. Une troncature silencieuse
    l'effacerait definitivement, et sur une feuille imprimee c'est indetectable apres
    coup.

    Trois volets, et le premier est ce qui empeche un mutant « refuser toujours » de
    passer les deux autres.
    """
    from mixed_media_utility import pdf_composition

    libelle = "hp envy 4520 tiff 600 dpi auto corr off"
    commentaire = "vitre nettoyee le 18 aout, lampe froide"
    plan, _avertissements = _calibration_plan(
        scan_chain_label=libelle, comment=commentaire)
    lignes = [ligne for bloc in plan.text.blocks for ligne in bloc.lines]
    texte = " ".join(lignes)
    # 1. Au corps reel, tout s'imprime **verbatim** et rien n'est tronque.
    assert libelle in texte, texte
    assert commentaire in texte, texte
    assert pdf_composition.CALIBRATION_USAGE_MENTION in texte, texte
    assert not any(pdf_composition.TRUNCATION_MARKER in ligne for ligne in lignes)

    # 2. Un texte qui ne tient pas est **refuse**, et le motif ne parle pas de
    # troncature. Le levier est le corps de police, comme en 5.18 et pour la meme
    # raison forcee: les longueurs maximales sont, elles, choisies pour tenir.
    monkeypatch.setattr(pdf_composition, "BODY_FONT_MIN_PT", 16.0)
    with pytest.raises(pdf_composition.GeometryOverflowError) as refus:
        _calibration_plan(scan_chain_label=libelle, comment=commentaire)
    message = str(refus.value)
    assert pdf_composition.TRUNCATION_MARKER not in message, message
    assert "lignes" in message, message
    # Le refus nomme les deux issues reelles, et aucune n'est une troncature.
    assert "raccourcir" in message, message
    assert page_templates.ORIENTATION_PORTRAIT in message, message

    # 3. Et la garde de verbatim **elle-meme** mord encore, alors que le repartiteur ne
    # peut plus la declencher: elle est le contrat 4.2 et non une consequence de lui.
    # Sans ce volet, la retirer ne casserait aucun test -- c'est-a-dire exactement le
    # mutant que ce fichier existe pour tuer.
    monkeypatch.setattr(pdf_composition, "BODY_FONT_MIN_PT", 8.0)
    monkeypatch.setattr(pdf_composition, "_wrap_verbatim",
                        lambda segments, width_mm, font_pt: ["z" * 400])
    with pytest.raises(pdf_composition.GeometryOverflowError) as refus:
        _calibration_plan(scan_chain_label=libelle)
    message = str(refus.value)
    assert "ne tient pas dans le bloc" in message, message
    assert "d'entete de page de calibration" in message, message
    assert pdf_composition.TRUNCATION_MARKER not in message, message
    # La ligne qui deborde est citee **entiere**: un refus qui tronquerait jusque dans
    # son propre motif serait le meme defaut, deplace.
    assert f"'{'z' * 400}'" in message, message


def test_the_calibration_header_band_must_hold_its_lines(monkeypatch) -> None:
    """**Mutant `G15`**: la garde de tenue verticale de l'entete retiree.

    La bande d'entete vaut des **rangees de grille** -- deux en portrait, une en paysage
    depuis 5.23 -- et elle ne s'agrandit qu'en reprenant des cellules au treillis, qui
    n'en a qu'**une** de marge en portrait. Une pile de texte qui deborde la bande
    ecrirait par-dessus la premiere rangee de pastilles, sur la page dont toute la
    correction de la chaine depend.

    AMENDE PAR 5.23: le budget de lignes est desormais verifie **en amont**, par
    `_calibration_header_lines`, qui refuse avant que la pile n'existe. La garde
    verticale est donc dominee -- et c'est precisement pourquoi elle a besoin d'un test
    qui la vise seule: une garde qu'aucun chemin n'atteint plus se retire sans que rien
    ne le dise, et elle est la derniere a mordre si le budget venait a etre relache.

    Le budget est donc ouvert **exprès** le temps du test, ce qui est le seul moyen de
    faire arriver la pile jusqu'a la garde qu'on mesure.
    """
    from mixed_media_utility import pdf_composition

    # La sonde vise la garde **verticale** et rien d'autre: une pile de lignes courtes,
    # donc au-dessus du budget mais sous la garde de verbatim, produite a la place du
    # repartiteur. Ouvrir le budget dans `page_templates` aurait ete plus direct et
    # faux: la meme constante dimensionne la grille, donc la monter la ferait tomber
    # sous le treillis et le refus mesure serait celui du treillis.
    monkeypatch.setattr(pdf_composition, "_calibration_header_lines",
                        lambda **_: ["ligne courte"] * 20)
    with pytest.raises(pdf_composition.GeometryOverflowError) as refus:
        _calibration_plan()
    message = str(refus.value)
    assert "L'entete de la page de calibration" in message, message
    assert "rangee de grille" in message, message
    # Le motif porte les deux grandeurs qui font la cause: ce que la pile exige et ce que
    # la bande offre. Un refus qui ne les nommerait pas laisserait chercher ailleurs.
    spec = page_templates.get_template(V2_TEMPLATES[0])
    bande = spec.geometry.calibration_grid(
        spec.orientation, patch_presets.CALIBRATION_PATCH_SIZE_MM).header_zone_mm()
    assert f"{bande[3]:.1f} mm" in message, (bande, message)


def test_an_undefined_but_placeable_couple_keeps_the_generic_refusal(monkeypatch) -> None:
    """**Mutant `H02`**: le motif d'infaisabilite est rendu pour **tout** couple absent.

    Les deux refus ne disent pas la meme chose et n'appellent pas le meme geste: « couple
    geometriquement infaisable » se lit comme une impossibilite assumee, dont la sortie est
    `--geometrie v1`; « couvert mais pas pour ce preset » se lit comme un trou du registre,
    dont la sortie est de l'y ajouter. Les confondre renverrait l'operateur vers la mauvaise
    sortie -- et c'est precisement le defaut que le point du `deferred-work.md` demandait de
    fermer, dans l'autre sens.

    La sonde retire un couple **placable** du registre: son refus doit rester generique.
    """
    template_id = V2_TEMPLATES[0]
    couple = (template_id, "patches-14-v3")
    assert couple in patch_presets._PLACEMENTS
    monkeypatch.delitem(patch_presets._PLACEMENTS, couple)
    with pytest.raises(patch_presets.UndefinedPlacementError) as refus:
        patch_presets.resolve_patch_layout(*couple)
    message = str(refus.value)
    assert "infaisable" not in message, message
    assert "couvert mais pas pour le preset" in message, message
    # Temoin positif: le couple reellement infaisable, lui, porte bien son motif chiffre.
    with pytest.raises(patch_presets.UndefinedPlacementError) as infaisable:
        patch_presets.resolve_patch_layout("tpl-a4-paysage-4f-v2", "patches-18-v2")
    assert "infaisable" in str(infaisable.value)


def test_the_required_rows_are_divided_by_the_columns_per_side(monkeypatch) -> None:
    """**Mutant `H03`**: les rangees exigees comptees sans division par les colonnes.

    Le mutant est **inobservable sur les donnees livrees**, et c'est le fait a garder
    sous les yeux plutot qu'a masquer: le seul couple enumere infaisable est
    `v2 x paysage x patches-18-v2`, et la v2 ne pose qu'**une** colonne de pastilles par
    cote dans les deux orientations. `ceil(18 / 1)` vaut 18, donc la forme fautive rend
    exactement le meme motif, aux quatre chiffres pres. Aucun resultat ne les separe.

    Ce qui les separe est une **geometrie reelle a plusieurs colonnes**, et le depot en a
    une: la v1 pose 3 colonnes par cote en paysage (2 en portrait) -- c'est justement
    l'asymetrie historique que la v2 a supprimee. La sonde ne fabrique donc aucune
    geometrie: elle ne deplace que l'**enumeration**, qui est une donnee, pour demander
    son motif chiffre a un couple dont la geometrie divise vraiment. Le mutant y annonce
    18 rangees de 8 mm la ou il en faut 6, soit un depassement invente de trois fois la
    hauteur -- et le refus qui en decoulerait renverrait l'operateur vers `--geometrie`
    pour une page qui tient.

    La garde vaut pour la suite et non pour aujourd'hui: le jour ou une version ajoutee
    reprend deux colonnes par cote -- ce que rien n'interdit, la v1 le fait -- la
    division redevient observable, et c'est le moment ou personne ne relit cette ligne.
    """
    paysage = page_templates.ORIENTATION_PAYSAGE
    # Les deux orientations paysage declarees infaisables: `other` reste vide, donc le
    # motif ne promet aucune autre geometrie -- la sonde ne dit rien de faux a personne.
    monkeypatch.setattr(
        patch_presets,
        "_PLACEMENT_UNPLACEABLE",
        (("v1", paysage, "patches-18-v2"), ("v2", paysage, "patches-18-v2")),
    )
    motif = patch_presets._unplaceable_reason("tpl-a4-paysage-4f-v1", "patches-18-v2")
    assert motif is not None
    # Le cardinal par cote et le nombre de rangees sont **deux** grandeurs distinctes ici,
    # et c'est toute la difference: 18 valeurs par cote sur 3 colonnes font 6 rangees.
    spec = page_templates.get_template("tpl-a4-paysage-4f-v1")
    colonnes = spec.geometry.patch_columns_per_side[paysage]
    assert colonnes == 3, "la v1 paysage pose bien plusieurs colonnes par cote"
    assert "18 valeur(s) par cote" in motif, motif
    assert f"{18 // colonnes} rangee(s) de" in motif, motif
    assert "18 rangee(s)" not in motif, motif
    # Et la hauteur exigee suit la division, sinon elle triple: 6 rangees au pas de la v1.
    geometrie = spec.geometry
    attendu = (18 // colonnes) * geometrie.patch_size_mm + (
        18 // colonnes - 1) * geometrie.patch_spacing_mm
    assert f"exigent {attendu:.1f} mm" in motif, (attendu, motif)


def test_the_vocabulary_introduced_never_reuses_mire_or_synthetic() -> None:
    """Le mot `mires` est **deja pris**, et il designe autre chose.

    Dans ce depot, `mires` sont les frames de remplacement de synthese
    (`lots[].synthetic_frames`, `EPIC5-ARB-33`). Aucun identifiant introduit par cette
    story ne porte `mire` ni le prefixe `synthetic`: les confondre rendrait les deux
    registres indiscernables a la lecture.
    """
    introduits = [
        *page_roles.PAGE_ROLES,
        *(nom for nom in dir(page_roles) if not nom.startswith("__")),
        "page_role", payload_io.PAYLOAD_SHORT_KEYS["page_role"],
        page_templates.WITNESS_PLACEMENT_LATTICE,
        "CalibrationGrid", "CALIBRATION_HEADER_LINE_COUNT",
        "CALIBRATION_PATCH_SIZE_MM", "CALIBRATION_LATTICE_REPETITION",
        "patches-14-v3", "patch-values-3",
        *(nom for nom in dir(patch_presets) if "calibration" in nom.lower()),
        *(nom for nom in dir(page_templates) if "calibration" in nom.lower()),
    ]
    assert len(introduits) > 20, "le balayage ne balaye rien"
    for identifiant in introduits:
        assert "mire" not in identifiant.lower(), identifiant
        assert "synthetic" not in identifiant.lower(), identifiant
    # Temoin negatif: le mot **existe** bien dans le depot, avec son autre sens. Sans
    # lui, l'assertion ci-dessus serait vraie meme si le registre des frames de
    # synthese avait disparu, donc ne prouverait aucune distinction.
    from mixed_media_utility.io import scan_manifest

    assert any("synthetic" in nom for nom in dir(scan_manifest))


# --- garde d'egalite au source RETIREE (EPIC5-ARB-95, 2026-08-19) ------------------
#
# Ici vivait `test_the_three_lot_level_guards_are_byte_for_byte_what_they_were`, pose par
# la story 5.16 comme frontiere negative de son AC 3. Il extrayait par AST le segment de
# source de trois definitions -- `_LOT_LEVEL_FIELDS` et `_check_lot_consistency`
# (`io/reconstruction.py`), `_check_printed_identifiers` (`io/scan_manifest.py`) -- et
# exigeait qu'il soit identique **au caractere** a sa forme au commit `1906211`.
#
# Ce n'est pas un oubli, et ce n'est pas non plus le retrait d'une propriete: c'est le
# retrait d'une **contrainte de forme** qui avait survecu a la story qui l'avait posee.
# Le 2026-08-18, le refus nomme de l'AC 10 de la story 5.23 (`EPIC5-ARB-85`) a du vivre
# dans une fonction separee (`_check_pile_homogene`) au lieu d'etre ecrit dans
# `_check_lot_consistency`, la ou l'arbitrage le designait par ses numeros de ligne: un
# garde-fou de 5.16 avait choisi la forme du code de 5.23, deux stories plus tard, sans
# que personne ne l'ait decide. Motif d'Egan: sinon chaque story legue une contrainte
# permanente, et au bout de vingt stories le code n'est plus modifiable. La regle
# generale qui en sort vit dans
# `_bmad-output/implementation-artifacts/politique-revue-et-mutation-testing.md`
# (section 7), la ou les agents de revue la lisent.
#
# **Table de reprise -- ce que la garde couvrait, et ou cela se mesure desormais.** Le
# titre disait « three », et il en gardait bien trois; aucune des trois proprietes de
# fond n'est perdue, chacune etant deja epinglee par un test de **comportement**. Verifie
# par injection ciblee (politique 4.0(b)) le 2026-08-19: 17 mutants reels ecrits dans les
# trois definitions, 17 tues, zero survivant -- le detail est au Dev Agent Record de la
# story 5.23. Le seul mutant qui n'etait tenu par aucun comportement (`page_role` promu au
# niveau lot) a recu son test avant le retrait, plus haut dans ce fichier.
#
# 1. `_LOT_LEVEL_FIELDS` -- « le role de page n'est pas de niveau lot, et l'ensemble ne
#    perd aucun champ ». `test_the_role_is_a_page_level_payload_field_next_to_the_index`
#    (ce fichier) tient la premiere moitie; `test_pile_mixte_refus.py::
#    test_la_garde_couvre_chacun_des_quatre_champs_pris_isolement` tient l'appartenance
#    des quatre champs de `CALIBRATION_ABSENT_FIELDS`, un par un; et le retrait de
#    n'importe lequel des dix champs fait tomber un refus de conflit de
#    `test_reconstruction.py` ou de `test_scan_manifest.py`.
# 2. `_check_lot_consistency` -- « deux pages du meme lot ne peuvent pas declarer deux
#    valeurs de niveau lot differentes ». Dans `test_reconstruction.py`, les trois
#    `test_reconstruct_raises_on_conflicting_<champ>_between_pages` (`project_id`,
#    `target_colorspace`, `page_count`) l'exercent, et `test_pile_mixte_refus.py::
#    test_le_refus_ne_mord_pas_sur_une_pile_de_planches_seules` tient la frontiere
#    positive (la lecture aboutit vraiment jusqu'a la reference de niveau lot).
# 3. `_check_printed_identifiers` -- « les trois identifiants poses a l'impression sont
#    confrontes au QR scanne ». `test_scan_manifest.py::
#    test_a_second_printing_of_a_lot_born_from_plates_alone_is_refused` et
#    `::test_a_plate_from_another_printing_is_refused_against_the_real_producer` sont les
#    deux refus, le second contre le **vrai** producteur `makepdf`.
#
# Ce que la garde couvrait et que personne ne reprend: rien -- sinon l'immobilite du
# texte lui-meme, qui est precisement ce qu'`EPIC5-ARB-95` retire. Le helper
# `_source_au_baseline` reste dans ce fichier: il n'a plus d'appelant de production mais
# `test_the_perimeter_gate_separates_a_copied_tree_from_a_truncated_history` continue de
# mesurer son echec dur, qui est la propriete pour laquelle il a ete ecrit.


def test_the_geometry_v2_declaration_is_unchanged_by_this_story() -> None:
    """Aucune valeur de `GEOMETRY_V2` n'est ecrite par cette story.

    C'est la frontiere que les Dev Notes revendiquent: la story ajoute des derivations
    **indexees par le role de page**, dont le comportement pour le role « planche
    d'images » est exactement l'existant. Un role nouveau n'a pas le droit de bouger
    l'ancien.
    """
    geometry = page_templates.get_geometry("v2")
    assert geometry.patch_size_mm == 6.0
    assert geometry.patch_spacing_mm == 3.0
    # **Amende par la story 5.23** (`EPIC5-ARB-82`, AC 1): le cardinal passe a 34, le jeu
    # temoin gagnant les trois secondaires. Ce que la story 5.16 revendiquait ici -- « un
    # role nouveau n'a pas le droit de bouger l'ancien » -- reste vrai et se verifie
    # desormais sur la **consequence** plutot que sur le litteral: la bande de frames et le
    # placement retenu sont identiques sous 28 et sous 34 pour les 30 gabarits v2, ce
    # qu'epingle `test_the_witness_cardinal_change_prints_the_same_image_sheets` dans
    # `test_page_geometry_v2.py`.
    assert geometry.border_witness_count == page_templates.WITNESS_PATCH_COUNT_V2 == 34
    assert dict(geometry.patch_columns_per_side) == {"portrait": 1, "paysage": 1}
    # Et le cardinal du jeu temoin **est** celui que la v2 declare depuis 5.18: la
    # geometrie etait deja dimensionnee pour ce preset, la story ne redimensionne
    # aucune bande.
    # **Amende par la story 5.23**: le preset temoin du depot est desormais
    # `patches-17-v4` (17 x 2 = 34), et c'est lui que le cardinal de la v2 declare.
    # `patches-14-v3` reste enregistre et inchange -- il n'est simplement plus celui que
    # la geometrie dimensionne.
    preset = patch_presets.get_patch_preset("patches-17-v4")
    assert (len(preset.value_ids) * preset.repetition
            == geometry.border_witness_count == 34)


def test_the_vocabulary_of_the_v2_is_thirty_templates_and_landscape_keeps_six() -> None:
    """Etat du registre au moment de cette story (`EPIC5-ARB-64`): 30 gabarits v2.

    Le cardinal 6 n'est retire que du **portrait**. Ce test est ici parce que la mise en
    page compagne doit couvrir 30 gabarits et non 27, et que le chiffre a change deux
    fois en deux jours.
    """
    v2 = [t for t in page_templates.known_template_ids()
          if page_templates.get_template(t).geometry_version == "v2"]
    assert len(v2) == 30
    assert page_templates.frames_per_page_vocabulary("portrait", "v2") == (1, 2, 3, 4, 8)
    assert page_templates.frames_per_page_vocabulary("paysage", "v2") == (1, 2, 4, 6, 8)
    # La mise en page compagne existe pour **chacun** des 30, et pas pour un
    # representant: un placement par famille d'orientation serait faux des qu'un
    # cardinal deplace une bande.
    for template_id in v2:
        layout = patch_presets.resolve_page_layout(
            template_id, page_roles.PAGE_ROLE_CALIBRATION)
        assert layout.frame_zones_mm == ()
        assert layout.patch_size_mm == patch_presets.CALIBRATION_PATCH_SIZE_MM
        assert len(patch_presets.resolve_calibration_page_patches(template_id)) == 130


def test_this_test_module_runs_against_the_installed_package() -> None:
    """Garde-fou de banc: le module teste est bien celui du depot, pas une copie."""
    assert Path(page_roles.__file__).is_relative_to(REPO_ROOT)
    assert sys.version_info >= (3, 10)


@pytest.mark.parametrize("preset_du_lot", ["patches-9-v1", "patches-12-v1", "patches-18-v2"])
def test_the_calibration_page_carries_the_lots_own_preset_and_never_a_hardcoded_one(
    preset_du_lot,
) -> None:
    """**Mutant `U02`**: la page de calibration declarait son propre preset.

    `patch_preset_id` est un champ de **niveau lot** (`_LOT_LEVEL_FIELDS`): toutes les pages
    d'un lot doivent porter la meme valeur, faute de quoi la relecture voit **deux lots** la
    ou il n'y en a qu'un -- « le tirage se scinde ». La page de calibration n'y echappe pas:
    son QR est relu par la meme chaine que celui des planches.

    **Pourquoi ce mutant survivait, et c'est la meme cause que T05 et R05**: il remplace la
    valeur transmise par le litteral `"patches-14-v3"`, qui est **exactement le preset par
    defaut** depuis `EPIC5-ARB-67`. Toutes les fabriques de page de calibration du depot
    utilisant ce defaut, la substitution etait **invisible** -- une valeur codee en dur
    coincide avec la valeur attendue tant qu'on ne teste que le defaut.

    Le test est donc parametre sur les **trois autres** presets du registre, et jamais sur
    celui du defaut: c'est la seule facon de distinguer « la valeur est transmise » de « la
    valeur se trouve etre la bonne ». Meme regle que la regle des fabriques, appliquee a une
    constante plutot qu'a une collection.
    """
    from mixed_media_utility import pdf_composition

    assert preset_du_lot != pdf_composition.DEFAULT_PATCH_PRESET, (
        "le cas du defaut ne discrimine rien: c'est la valeur que le mutant code en dur")
    plan, _avertissements = _calibration_plan(patch_preset_id=preset_du_lot)
    paie = payload_io.parse_payload(plan.qr.payload_text)
    assert paie["patch_preset_id"] == preset_du_lot, paie["patch_preset_id"]
    # Et les autres champs de niveau lot suivent la meme regle, sinon le test ne verrouille
    # qu'un champ d'une famille qui en compte plusieurs.
    #
    # **Repare le 2026-08-18 (story 5.23, AC 11).** `paie["lot_id"]` levait `KeyError`
    # **dans le corps du test**: depuis l'AC 8bis une page de calibration ne declare ni
    # projet, ni rush, ni lot, ni cadence (`io.payload.CALIBRATION_ABSENT_FIELDS`) --
    # elle sert une chaine de scan entiere et non un lot. Le sujet du test est intact
    # (« la valeur transmise, jamais un litteral code en dur »), seule cette assertion
    # decrivait un champ qui n'existe plus. Elle est remplacee par son contraire, qui
    # est la propriete vraie aujourd'hui **et** une frontiere negative utile: le champ
    # est absent, et son retour se dirait ici.
    assert "lot_id" not in paie, paie
    assert payload_io.CALIBRATION_ABSENT_FIELDS.isdisjoint(paie), paie
    assert paie["target_colorspace"] == "rec709"
    assert paie["gamut_map_id"] == payload_io.GAMUT_MAP_IDENTITY
