"""Story 5.17 -- payload QR a cles courtes, et la version 22 fermee (`EPIC5-ARB-60`).

Ce fichier verrouille cinq choses distinctes, et l'ordre suit celui des AC:

1. la **table de correspondance** est unique, bijective, exhaustive et epinglee valeur
   par valeur -- c'est un contrat aussi dur que les noms longs qu'elle remplace, et il
   voyage imprime sur du papier;
2. le passage a `PAYLOAD_SCHEMA_VERSION = "2.0"` et les **deux refus** qu'il exige;
3. le **gain**, re-mesure par cardinal sur le chemin de production et non modelise;
4. la **version du symbole**: aucun cardinal du vocabulaire ne l'atteint plus, et la
   garde d'impression la refuse quelle que soit la taille imprimee;
5. le **budget** et le **domaine de modules** recalcules, non recopies.

Regle des fabriques du depot, qui mord ici deux fois: une table de correspondance
appliquee dans le mauvais ordre est exactement le mutant `M33` de la story 5.6, et il
ne se voit que si les valeurs diffèrent. Toutes les fabriques d'emplacements de ce
fichier produisent donc au moins **deux** elements **distinguables** (index et
timecodes tous differents), et plusieurs tests placent la cible **ailleurs qu'en
premiere position**.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (  # noqa: E402
    gamut_map,
    page_payload,
    page_templates,
    patch_presets,
    qr_codes,
)
from mixed_media_utility.io import payload as payload_io  # noqa: E402


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

#: Regime d'identifiants **de reference de la story**: c'est celui sur lequel les
#: colonnes de l'AC 4 ont ete mesurees, et le seul qui les reproduise. Un autre regime
#: donne d'autres octets pour les memes cardinaux (c'est tout l'objet de la reserve du
#: 2026-08-11 sur `QR_MIN_MODULE_SIDE`), donc il est nomme ici plutot que devine.
REFERENCE_IDS = ("projet_demo", "planche_4f_heteroclite", "planche_4f_heteroclite_4")
REFERENCE_TEMPLATE = "tpl-a4-portrait-2f-v1"
REFERENCE_PRESET = "patches-12-v1"

#: Regime des identifiants **longs**, celui des balayages du depot (40 caracteres par
#: identifiant, cf. `test_page_geometry_v2`). C'est lui que l'AC 8 designe.
LONG_IDS = ("p" * 40, "r" * 40, "l" * 40)

#: Regime **maximal**: les trois identifiants a la borne canonique de 48 caracteres.
#: Il n'est pas celui de l'AC 8 et il est mesure a part, parce que c'est le seul ou un
#: cardinal du vocabulaire repasse au-dessus du budget nominal (voir
#: `test_the_absolute_identifier_ceiling_is_the_one_regime_still_over_nominal`).
MAX_IDS = ("p" * 48, "r" * 48, "l" * 48)


def distinguishable_slots(count: int, *, first_index: int = 0) -> list[dict]:
    """``count`` emplacements dont **aucun** ne ressemble a un autre.

    Index croissants et timecodes tous differents: une table appliquee a l'envers, un
    appariement positionnel inverse ou un `find` qui rend toujours le premier element
    ne se demasquent pas autrement. Un remplissage uniforme les aurait rendus
    invisibles -- c'est litteralement le mutant `M33` de la story 5.6.
    """
    return [
        {"slot_index": first_index + rank,
         "frame_timecode": f"{rank + 1:02d}:{rank * 2 + 3:02d}:{rank * 3 + 7:02d}:{rank:02d}"}
        for rank in range(count)
    ]


def payload_for(
    cardinal: int,
    *,
    ids: tuple[str, str, str] = REFERENCE_IDS,
    first_index: int = 0,
) -> dict:
    """Le vrai payload de production, par son vrai producteur."""
    return payload_io.build_page_payload(
        project_id=ids[0], rush_id=ids[1], lot_id=ids[2],
        page_index=0, page_count=1, fps_target=24.0,
        timecode_base_fps="25/1",
        template_id=REFERENCE_TEMPLATE, patch_preset_id=REFERENCE_PRESET,
        target_colorspace="bt709", gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=distinguishable_slots(cardinal, first_index=first_index),
    )


def plan_for(cardinal: int, *, ids: tuple[str, str, str] = REFERENCE_IDS):
    """Le chemin de **production** de bout en bout: payload -> budget -> symbole.

    Jamais un modele: la lecon de methode du 2026-08-11 (trois erreurs de banc dans la
    meme journee) est qu'une grandeur mesuree ailleurs que sur `plan_page_payload` ne
    vaut rien.
    """
    return page_payload.plan_page_payload(
        project_id=ids[0], rush_id=ids[1], lot_id=ids[2],
        page_index=0, page_count=1, fps_target=24.0,
        timecode_base_fps="25/1",
        template_id=REFERENCE_TEMPLATE, patch_preset_id=REFERENCE_PRESET,
        target_colorspace="bt709", gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=distinguishable_slots(cardinal),
    )


#: Le vocabulaire des cardinaux livres par les gabarits.
CARDINALS = (1, 2, 3, 4, 6, 8)


# ---------------------------------------------------------------------------
# AC 1 -- la table est une constante nommee, unique et testee
# ---------------------------------------------------------------------------


def test_the_table_is_bijective() -> None:
    """Aucune cle courte en double, dans les deux sens.

    Une cle courte dupliquee ne serait pas une erreur d'ecriture visible: elle ferait
    disparaitre une entree de la table inverse, donc un champ **entier** du payload a
    la relecture, et le QR imprime serait deja sur du papier.
    """
    short_keys = list(payload_io.PAYLOAD_SHORT_KEYS.values())
    assert len(set(short_keys)) == len(short_keys), sorted(short_keys)
    assert len(payload_io.PAYLOAD_LONG_KEYS) == len(payload_io.PAYLOAD_SHORT_KEYS)
    for long, short in payload_io.PAYLOAD_SHORT_KEYS.items():
        assert payload_io.PAYLOAD_LONG_KEYS[short] == long


def test_the_table_covers_exactly_the_contract_no_more_no_less() -> None:
    """Les onze scalaires, les deux champs d'emplacement, et le conteneur. Rien d'autre.

    Un champ du contrat absent de la table serait refuse a la serialisation (donc
    bruyamment); une **entree en trop** serait l'inverse et c'est le cas dangereux:
    elle ferait passer sur le papier un champ hors contrat, que la machine tierce ne
    saurait pas lire et que rien ne signalerait.
    """
    # AMENDE PAR 5.23: la table couvre desormais **trois** familles et non deux --
    # les champs de toute page, les champs d'emplacement, et les champs du **seul
    # role `c`** (`CALIBRATION_ONLY_FIELDS`). Le contrat n'est plus « les scalaires
    # requis », il est « ce que le document peut porter »: `scan_chain_label` est
    # obligatoire sur une page de calibration et refuse ailleurs, donc l'ajouter a
    # `_REQUIRED_SCALAR_FIELDS` aurait rendu toute planche d'images invalide.
    expected = (set(payload_io._REQUIRED_SCALAR_FIELDS)
                | set(payload_io.CALIBRATION_ONLY_FIELDS)
                | set(payload_io.OPTIONAL_SCALAR_FIELDS)
                | set(payload_io._REQUIRED_SLOT_FIELDS) | {"slots"})
    assert set(payload_io.PAYLOAD_SHORT_KEYS) == expected
    # Et les deux familles conditionnelles sont **disjointes**: un champ ne peut pas
    # etre a la fois absent par contrat et exige par contrat sous le meme role.
    assert not (payload_io.CALIBRATION_ONLY_FIELDS
                & payload_io.CALIBRATION_ABSENT_FIELDS)
    # **Treize scalaires depuis la story 2.7** (`timecode_base_fps`, EPIC7-ARB-56),
    # douze depuis la story 5.16 (role de page, `EPIC5-ARB-54`) et onze avant elle.
    # Les trois cardinaux sont conserves en litteral plutot que derives les uns des
    # autres: c'est leur redondance qui fait que ce test **dit** qu'un champ est
    # arrive, au lieu de suivre en silence.
    assert len(payload_io._REQUIRED_SCALAR_FIELDS) == 13
    assert len(payload_io.CALIBRATION_ONLY_FIELDS) == 1
    # **Troisieme famille depuis `EPIC11-ARB-91`**: les champs FACULTATIFS. Le
    # contrat n'est plus « ce que toute page porte, plus ce que le role `c` est
    # seul a porter »: `version_rank` est absent de toute planche deja imprimee
    # et present sur les versions a partir de la deuxieme, si bien que le
    # ranger dans l'une des deux autres familles aurait soit refuse tout le
    # parc, soit reserve le rang a un role qui n'est pas le sien.
    assert len(payload_io.OPTIONAL_SCALAR_FIELDS) == 1
    assert len(payload_io._REQUIRED_SLOT_FIELDS) == 2
    assert len(payload_io.PAYLOAD_SHORT_KEYS) == 18


#: Les modules de production qui manipulent le payload QR, recenses par l'AC 9. Ce
#: sont eux, et eux seuls, ou un litteral de cle courte serait une seconde table en
#: puissance -- ailleurs dans `src/`, une chaine de trois lettres est une coincidence
#: (`"fps"` est une cle de previz d'encodage, sans rapport avec ce contrat).
_MODULES_QUI_TOUCHENT_LE_PAYLOAD = (
    "io/payload.py",
    "page_payload.py",
    "pdf_composition.py",
    "pdf_render.py",
    "scan_detection.py",
    "io/reconstruction.py",
)


def test_the_table_is_the_only_place_where_a_short_key_is_written() -> None:
    """Interdiction de litteraux courts disperses (defaut ferme en revue de 3.5).

    Deux tables qui divergent produiraient un QR ecrit dans une forme et relu dans une
    autre -- silencieux a l'ecriture, fatal a la relecture, et le support est du papier.
    Le test compte les litteraux dans les six modules de production qui touchent au
    payload: chacune des quatorze cles courtes n'y est ecrite **qu'une fois**, dans la
    table.
    """
    base = REPO_ROOT / "src" / "mixed_media_utility"
    sources = {
        relative: (base / relative).read_text(encoding="utf-8")
        for relative in _MODULES_QUI_TOUCHENT_LE_PAYLOAD
    }
    for short in payload_io.PAYLOAD_SHORT_KEYS.values():
        literal = f'"{short}"'
        occurrences = {
            relative: text.count(literal)
            for relative, text in sources.items() if literal in text
        }
        assert occurrences == {"io/payload.py": 1}, (short, occurrences)


@pytest.mark.parametrize("cardinal", CARDINALS)
def test_the_roundtrip_returns_the_original_dict_identically(cardinal: int) -> None:
    """`serialize_payload` puis `parse_payload` rend le dictionnaire d'origine.

    Les emplacements sont **distinguables**: sur un remplissage uniforme, une table
    appliquee a l'envers ou un appariement inverse passerait ce test sans broncher.
    """
    payload = payload_for(cardinal)
    text = payload_io.serialize_payload(payload)
    assert payload_io.parse_payload(text) == payload
    # Et la boucle est stable: relire puis reecrire rend le meme texte.
    assert payload_io.serialize_payload(payload_io.parse_payload(text)) == text


def test_the_roundtrip_preserves_the_order_of_slots_and_not_only_their_set() -> None:
    """La cible n'est **pas** en premiere position, et les emplacements ne sont pas tries.

    Un appariement positionnel inverse (le mutant `M33` de 5.6) rendrait le meme
    ensemble d'emplacements dans l'ordre inverse. Un test qui compare des ensembles, ou
    qui place la valeur cherchee en tete, ne le voit pas.
    """
    payload = payload_for(4)
    payload["slots"] = list(reversed(payload["slots"]))
    cible = payload["slots"][2]
    assert cible is not payload["slots"][0]

    relu = payload_io.parse_payload(payload_io.serialize_payload(payload))

    assert relu["slots"] == payload["slots"]
    assert relu["slots"][2] == cible
    assert [slot["slot_index"] for slot in relu["slots"]] == [3, 2, 1, 0]
    assert [slot["frame_timecode"] for slot in relu["slots"]] == [
        slot["frame_timecode"] for slot in payload["slots"]]


def test_the_printed_field_order_is_the_builders_order_and_the_version_comes_first() -> None:
    """L'ordre des champs **imprimes** est celui du producteur, jamais un tri.

    Survivant `B07` de la campagne de mutation, et il est instructif: trier les cles a
    la serialisation ne change ni le nombre d'octets, ni le nombre de modules, ni la
    boucle -- deux dictionnaires sont egaux quel que soit leur ordre. **Rien** ne le
    voyait donc, alors que l'ordre est une propriete que ce module revendique depuis la
    story 2.3 (« field order mirrors the *Payload recommande* list, kept stable for
    readability/debugging ») et dont un diagnostic depend: ce payload se lit **a l'oeil**
    sur du papier, et la version doit etre le premier champ qu'on y trouve.
    """
    payload = payload_for(3)
    document = json.loads(payload_io.serialize_payload(payload))

    ordre = list(document)
    assert ordre == [payload_io.PAYLOAD_SHORT_KEYS[long] for long in payload]
    assert ordre[0] == payload_io.PAYLOAD_SHORT_KEYS["schema_version"]
    # Et ce n'est pas l'ordre alphabetique: sans cette assertion, un tri passerait le
    # test le jour ou la table serait rangee par hasard dans cet ordre.
    assert ordre != sorted(ordre), ordre
    # Dans chaque emplacement aussi: l'index avant le timecode.
    for slot in document[payload_io.PAYLOAD_SHORT_KEYS["slots"]]:
        assert list(slot) == [payload_io.PAYLOAD_SHORT_KEYS["slot_index"],
                              payload_io.PAYLOAD_SHORT_KEYS["frame_timecode"]]


def test_serialization_and_parsing_read_the_same_table(monkeypatch) -> None:
    """Le contrat de l'AC 1: **une** table, consommee par les deux sens.

    La table est renommee a chaud et les deux cotes doivent suivre ensemble. Deux
    tables, ou un litteral cable dans l'un des deux sens, laisseraient ce cote-la
    inchange -- et c'est exactement la divergence fermee en revue de 3.5, silencieuse a
    l'ecriture et fatale a la relecture.
    """
    from types import MappingProxyType

    table = dict(payload_io.PAYLOAD_SHORT_KEYS)
    table["rush_id"] = "zzz"
    monkeypatch.setattr(payload_io, "PAYLOAD_SHORT_KEYS", MappingProxyType(table))
    monkeypatch.setattr(payload_io, "PAYLOAD_LONG_KEYS", MappingProxyType(
        {short: long for long, short in table.items()}))

    payload = payload_for(2)
    text = payload_io.serialize_payload(payload)

    assert '"zzz"' in text
    assert '"rid"' not in text
    assert payload_io.parse_payload(text) == payload


def test_a_key_outside_the_table_is_refused_in_both_directions() -> None:
    """Ni a l'ecriture ni a la lecture un champ hors contrat ne passe.

    Recopier verbatim une cle inconnue aurait fait imprimer un champ que la machine
    tierce ne connait pas -- et, a la relecture, l'aurait conserve dans le
    dictionnaire rendu comme s'il faisait partie du contrat.
    """
    payload = payload_for(2)
    payload["camera_serial"] = "A1234"
    with pytest.raises(payload_io.PayloadValidationError, match="camera_serial"):
        payload_io.serialize_payload(payload)

    payload = payload_for(2)
    payload["slots"][1]["exposure"] = 2
    with pytest.raises(payload_io.PayloadValidationError, match="exposure"):
        payload_io.serialize_payload(payload)

    text = payload_io.serialize_payload(payload_for(2))
    intrus = json.loads(text)
    intrus["xyz"] = 1
    with pytest.raises(payload_io.PayloadValidationError, match="xyz"):
        payload_io.parse_payload(json.dumps(intrus, separators=(",", ":")))


def test_a_contract_key_used_at_the_wrong_level_is_also_refused() -> None:
    """Une cle **du** contrat placee au mauvais niveau est un champ hors contrat.

    Majeur M2 de la revue: la table est plate -- les deux jeux de noms etant disjoints,
    une seule suffit a projeter le document entier -- et elle etait passee **telle
    quelle** aux deux niveaux, si bien que les trois formes de confusion etaient
    acceptees dans les deux sens (mesure a l'execution: `{'slot_index': 99}` a la
    racine, `{'project_id': 'intrus'}` dans un emplacement, et le symetrique a
    l'ecriture, qui aurait fait passer le champ **sur le papier**). Le test qui existait
    n'employait que des cles etrangeres a la table (`camera_serial`, `exposure`,
    `xyz`): il ne pouvait pas voir un probleme de niveau.

    Les quatre sondes sont donc croisees: les deux niveaux, dans les deux sens. La
    cible est placee dans le **second** emplacement et non le premier -- regle des
    fabriques du depot: une erreur de niveau qui ne porterait que sur le premier
    element ne se demasquerait pas autrement.
    """
    # 1. cle d'emplacement a la racine, a l'ecriture: elle serait imprimee.
    a_ecrire = dict(payload_for(3))
    a_ecrire["slot_index"] = 7
    with pytest.raises(payload_io.PayloadValidationError) as excinfo:
        payload_io.serialize_payload(a_ecrire)
    assert "slot_index" in str(excinfo.value)
    assert "racine" in str(excinfo.value)
    # Le message ne propose que les cles du **niveau** en faute: proposer les quatorze
    # aggravait la confusion qu'il est censee lever.
    assert "frame_timecode" not in str(excinfo.value), str(excinfo.value)

    # 2. cle de racine dans un emplacement, a l'ecriture, et pas dans le premier.
    a_ecrire = dict(payload_for(3))
    a_ecrire["slots"] = [dict(slot) for slot in a_ecrire["slots"]]
    a_ecrire["slots"][2]["project_id"] = "intrus"
    with pytest.raises(payload_io.PayloadValidationError) as excinfo:
        payload_io.serialize_payload(a_ecrire)
    assert "project_id" in str(excinfo.value)
    assert "emplacement" in str(excinfo.value)
    assert "template_id" not in str(excinfo.value), str(excinfo.value)

    # 3. cle courte d'emplacement a la racine, a la relecture.
    a_relire = json.loads(payload_io.serialize_payload(payload_for(3)))
    a_relire[payload_io.PAYLOAD_SHORT_KEYS["slot_index"]] = 99
    with pytest.raises(payload_io.PayloadValidationError) as excinfo:
        payload_io.parse_payload(json.dumps(a_relire, separators=(",", ":")))
    assert "racine" in str(excinfo.value)

    # 4. cle courte de racine dans un emplacement, a la relecture, le second.
    a_relire = json.loads(payload_io.serialize_payload(payload_for(3)))
    a_relire[payload_io.PAYLOAD_SHORT_KEYS["slots"]][1][
        payload_io.PAYLOAD_SHORT_KEYS["project_id"]] = "intrus"
    with pytest.raises(payload_io.PayloadValidationError) as excinfo:
        payload_io.parse_payload(json.dumps(a_relire, separators=(",", ":")))
    assert "emplacement" in str(excinfo.value)


def test_the_two_level_views_are_derived_from_the_single_table() -> None:
    """Les vues de niveau sont **derivees**, jamais une seconde table (AC 1).

    Deux tables qui divergent est le defaut ferme en revue de 3.5, et c'est
    precisement ce qu'un correctif de niveau pouvait reintroduire. La partition doit
    donc etre exhaustive et disjointe: chaque entree de la table unique appartient a un
    niveau et a un seul.
    """
    racine, emplacement = payload_io._level_tables(payload_io.PAYLOAD_SHORT_KEYS)
    assert set(racine) | set(emplacement) == set(payload_io.PAYLOAD_SHORT_KEYS)
    assert not set(racine) & set(emplacement)
    assert set(emplacement) == set(payload_io._REQUIRED_SLOT_FIELDS)
    # AMENDE PAR 5.23: la racine porte aussi les champs du seul role `c`.
    assert set(racine) == {*payload_io._REQUIRED_SCALAR_FIELDS,
                           *payload_io.CALIBRATION_ONLY_FIELDS,
                           *payload_io.OPTIONAL_SCALAR_FIELDS, "slots"}
    # Et la meme partition tient dans l'autre sens, sur la table inverse.
    racine_courte, emplacement_courte = payload_io._level_tables(
        payload_io.PAYLOAD_LONG_KEYS)
    assert set(racine_courte) == {payload_io.PAYLOAD_SHORT_KEYS[long] for long in racine}
    assert set(emplacement_courte) == {
        payload_io.PAYLOAD_SHORT_KEYS[long] for long in emplacement}


# ---------------------------------------------------------------------------
# AC 2 -- les cles font 2 a 3 caracteres, pas une lettre
# ---------------------------------------------------------------------------

#: La table **entiere**, epinglee valeur par valeur. C'est un contrat au meme titre
#: que les noms longs qu'elle remplace: elle voyage imprimee, et un QR deja sur du
#: papier ne se corrige pas. Toute modification de cette table oblige a re-mesurer les
#: octets de l'AC 4 dans le meme mouvement -- une autre table donne d'autres octets.
_PINNED_TABLE = {
    "schema_version": "sv",
    "project_id": "pid",
    "rush_id": "rid",
    "lot_id": "lid",
    "page_index": "pi",
    "page_count": "pc",
    # Story 5.16 (`EPIC5-ARB-54`): le role de page. Epingle **valeur par valeur** comme
    # les quatorze autres, et pas seulement compte -- c'est cette table figee dans le
    # fichier de test qui empeche qu'une cle courte soit renommee en silence, ce qui
    # rendrait un QR deja imprime indecodable.
    "page_role": "pr",
    "fps_target": "fps",
    # Story 2.7 (`EPIC7-ARB-56`): la cadence SOURCE du rush, meme recette que
    # ses voisins.
    "timecode_base_fps": "tbf",
    "template_id": "tid",
    "patch_preset_id": "ppi",
    "target_colorspace": "tcs",
    "gamut_map_id": "gmi",
    # Story 5.23 (correction d'Egan du 2026-08-18): le libelle de la chaine de scan,
    # porte par le **seul** role `c`. Meme recette que ses voisins -- initiales,
    # trois caracteres -- et epingle ici pour la meme raison que les autres.
    "scan_chain_label": "scl",
    # `EPIC11-ARB-91` (Egan, 2026-08-31): le rang de version de la planche,
    # premier champ **facultatif** de la table. `vr` et non `v`: Egan nommait
    # le sens (« v pour version »), la convention de longueur ci-dessous est
    # celle du depot, et elle coute ici UN octet sur 41 de marge mesuree.
    "version_rank": "vr",
    "slots": "s",
    "slot_index": "si",
    "frame_timecode": "ft",
}

def test_the_table_is_pinned_value_by_value() -> None:
    assert dict(payload_io.PAYLOAD_SHORT_KEYS) == _PINNED_TABLE


def test_the_keys_are_two_or_three_characters_and_never_one_letter_per_field() -> None:
    """Choix assume: 2 a 3 caracteres, pas une lettre par champ.

    Descendre a une lettre gagne environ 15 octets de plus et rend illisible un payload
    decode a la main lors d'un diagnostic. Mauvais echange: ce payload voyage imprime,
    et le seul outil garanti sur place est un oeil.

    **Une exception, nommee**: le conteneur `slots` est raccourci en `s`, un caractere.
    Ce n'est pas un champ mais l'enveloppe des emplacements, il n'y a rien a lire
    dedans, et c'est la table qu'`EPIC5-ARB-60` tranche et sur laquelle les octets de
    l'AC 4 sont mesures -- `sl` couterait un octet de plus a chaque page et rendrait
    faux chacun des six cardinaux epingles.
    """
    champs = (set(payload_io._REQUIRED_SCALAR_FIELDS)
              | set(payload_io.CALIBRATION_ONLY_FIELDS)
              | set(payload_io.OPTIONAL_SCALAR_FIELDS)
              | set(payload_io._REQUIRED_SLOT_FIELDS))
    for long, short in payload_io.PAYLOAD_SHORT_KEYS.items():
        if long == "slots":
            assert short == "s"
            continue
        assert long in champs, long
        assert 2 <= len(short) <= 3, (long, short)
        assert short.isascii() and short.islower(), (long, short)
    # Et le raccourci est bien un raccourci: chaque cle courte est plus courte que la
    # longue qu'elle remplace. Une table « courte » qui rallongerait un champ ne
    # gagnerait rien et ce test le dirait.
    for long, short in payload_io.PAYLOAD_SHORT_KEYS.items():
        assert len(short) < len(long), (long, short)


# ---------------------------------------------------------------------------
# AC 3 -- la version passe a 2.1, et la branche de lecture 1.0 est supprimee
# (story 2.7, EPIC7-ARB-56 -- ce bloc portait les tests de la branche 1.0
# retiree par cette story; chaque test est repris selon son SUJET, jamais
# recopie: voir le motif ecrit sur chacun ci-dessous)
# ---------------------------------------------------------------------------


def test_the_schema_version_is_the_current_one() -> None:
    # Suit la constante plutot que de l'epingler (lecon de la tautologie 5.9,
    # `politique-revue-et-mutation-testing.md` section 6): la valeur elle-meme a
    # bouge deux fois depuis la redaction initiale de ce test (5.17: "2.0";
    # 2.7: "2.1", EPIC7-ARB-56) et bougera encore.
    assert payload_for(2)["schema_version"] == payload_io.PAYLOAD_SCHEMA_VERSION
    # La version circule dans le payload **imprime**, sous sa cle courte.
    assert (f'"sv":"{payload_io.PAYLOAD_SCHEMA_VERSION}"'
            in payload_io.serialize_payload(payload_for(2)))


def test_a_long_key_document_is_refused_as_a_foreign_qr_not_a_stale_sheet() -> None:
    """**Retiree et remplacee par la story 2.7** (AC 4, `EPIC7-ARB-56`): le sujet change.

    Les deux tests que ce test remplace --
    `test_a_complete_and_valid_1_0_payload_is_refused_by_name` et
    `test_a_long_key_document_is_refused_on_its_format_without_being_misdated` --
    avaient pour sujet « un document a cles longues (format 1.0) est refuse comme
    planche PERIMEE, distinctement d'un QR etranger, avec un motif de reimpression ».
    Ce sujet n'existe plus: `EPIC7-ARB-56` retire dans le meme geste la branche de
    lecture 1.0 -- « la branche de lecture 1.0 est supprimee ». Un document a cles
    longues ne porte jamais la cle courte `sv` que ce lecteur exige desormais seule,
    donc il tombe dans le meme refus qu'un QR etranger (`PayloadVersionMissing`),
    plus dans le refus de planche perimee (`PayloadSchemaVersionRefused`) -- ce qui
    est exact au regard du parc: aucune planche `1.0` n'a jamais ete imprimee hors
    materiel de test (voir `io/payload.py`, module docstring et `_refuse_unreadable_schema`).

    Ce test mesure donc le nouveau fait, exige par l'AC 4 de la story 2.7: « un
    payload a cles longues rend `PayloadVersionMissing` ».
    """
    longues = dict(payload_for(2))  # le dictionnaire en memoire, cles longues
    assert longues["schema_version"] == payload_io.PAYLOAD_SCHEMA_VERSION
    with pytest.raises(payload_io.PayloadVersionMissing) as excinfo:
        payload_io.parse_payload(json.dumps(longues, separators=(",", ":")))
    message = str(excinfo.value)
    assert "sv" in message, message
    assert "etranger" in message.lower(), message
    # Et il n'est **pas** confondu avec une planche perimee: l'ancien refus, dedie,
    # ne se declenche plus jamais sur cette forme.
    assert not isinstance(excinfo.value, payload_io.PayloadSchemaVersionRefused)


@pytest.mark.parametrize("version", ["1.0", "1.1", "2.0", "3.0", "9.9", ""])
def test_any_other_declared_version_is_refused_the_same_way(version: str) -> None:
    """La garde est une egalite, pas une liste de versions connues.

    Un lecteur qui n'accepterait que « pas 1.0 » laisserait passer un format futur en
    le lisant avec les regles du present -- le pire des trois cas possibles, parce
    qu'il ne dit rien.
    """
    court = json.loads(payload_io.serialize_payload(payload_for(2)))
    court["sv"] = version
    with pytest.raises(payload_io.PayloadSchemaVersionRefused) as excinfo:
        payload_io.parse_payload(json.dumps(court, separators=(",", ":")))
    assert repr(version) in str(excinfo.value) or version in str(excinfo.value)
    assert payload_io.PAYLOAD_SCHEMA_VERSION in str(excinfo.value)


def test_a_payload_without_either_version_key_is_refused_distinctly() -> None:
    """Un QR etranger n'est pas une planche perimee, et les deux refus le disent.

    Confondre les deux enverrait l'operateur reimprimer une planche qui n'a jamais
    existe -- ou jeter une planche qu'il suffisait de reimprimer.
    """
    court = json.loads(payload_io.serialize_payload(payload_for(2)))
    del court["sv"]
    with pytest.raises(payload_io.PayloadVersionMissing) as excinfo:
        payload_io.parse_payload(json.dumps(court, separators=(",", ":")))
    message = str(excinfo.value)
    # **Depuis la story 2.7**, le controle ne porte plus que sur la cle courte `sv`
    # (la lecture de la cle longue `schema_version`, propre a la branche 1.0, est
    # retiree avec elle, AC 4): le message ne nomme donc plus que celle-la.
    assert "sv" in message, message
    assert "reimprim" not in message.lower(), message
    # **Le contenu operateur est exige positivement**, et c'est la lecon des deux
    # survivants de la campagne du blind hunter (`N04`, `N04b`): le message pouvait
    # etre reduit a une chaine minimale sans qu'aucun des sept fichiers de tests ne
    # bronche. La moitie « planche perimee -> reimprimer » etait gardee positivement,
    # la moitie « QR etranger -> a la poubelle » ne l'etait que negativement. Quand un
    # refus existe pour dire une phrase a un operateur, la phrase **est** le livrable.
    assert "etranger" in message.lower(), message
    assert "aucun tirage n'est en cause" in message, message
    assert "c'est le document scanne qui n'est pas le bon" in message, message
    # Les deux refus sont **distincts** et aucun n'est un cas particulier de l'autre.
    assert not isinstance(excinfo.value, payload_io.PayloadSchemaVersionRefused)
    assert isinstance(excinfo.value, payload_io.PayloadValidationError)
    with pytest.raises(payload_io.PayloadVersionMissing):
        payload_io.parse_payload("{}")


def test_the_version_refusal_comes_before_any_field_complaint() -> None:
    """Une planche future **amputee** est refusee pour sa version, pas pour son champ.

    L'ordre n'est pas cosmetique: un payload de version future auquel il manque un
    champ est d'abord une planche que ce lecteur ne sait pas lire. Diagnostiquer le
    champ absent ferait chercher un defaut de fabrication sur une planche dont le seul
    tort est sa version.

    **Le sujet ne change pas avec la story 2.7, seule la forme change**: la planche
    « d'un autre temps » etait `1.0` a cles longues (branche de lecture retiree,
    `EPIC7-ARB-56`); elle est ici une version future a cles **courtes** (`sv` present
    mais non reconnu), qui exerce la meme propriete d'ordre par le seul chemin qui la
    produit encore.
    """
    court = json.loads(payload_io.serialize_payload(payload_for(4)))
    court["sv"] = "9.9"
    del court["rid"]
    del court["s"]
    with pytest.raises(payload_io.PayloadSchemaVersionRefused):
        payload_io.parse_payload(json.dumps(court, separators=(",", ":")))


def test_every_refusal_carries_the_identity_still_readable() -> None:
    """L'identite voyage **avec** le refus, quand ce refus la porte encore.

    C'est le mecanisme du correctif de B1, teste ici a son niveau: `parse_payload` pose
    `error.readable_identity` sur tous les refus posterieurs au decodage JSON, une
    valeur qui ne tient pas le contrat etant **omise** plutot que publiee -- ce qui sort
    d'ici entre dans le document de scan et dans la reconciliation.

    **Depuis la story 2.7** (AC 4, `EPIC7-ARB-56`), une seule forme la porte: la lecture
    cle longue de `readable_identity` est retiree dans le meme geste que la branche de
    lecture 1.0 qui en etait l'unique consommatrice. Un document a cles longues ne rend
    donc plus d'identite du tout (scenario 1 ci-dessous, **nouveau fait** exige par
    l'AC 4) -- seul un document a cles courtes de version refusee (future, scenario 1b)
    la conserve encore.
    """
    # 1. document a cles longues: **aucune** identite recuperable depuis la story 2.7,
    #    quand bien meme le document est par ailleurs complet et valide sous ses noms.
    longues = dict(payload_for(2))
    with pytest.raises(payload_io.PayloadVersionMissing) as excinfo:
        payload_io.parse_payload(json.dumps(longues, separators=(",", ":")))
    assert dict(excinfo.value.readable_identity) == {}

    # 1b. document a cles courtes, version future: l'identite, elle, reste lisible --
    #     c'est la forme qui remplace la planche `1.0` pour cette propriete.
    future = json.loads(payload_io.serialize_payload(payload_for(2)))
    future["sv"] = "9.9"
    with pytest.raises(payload_io.PayloadValidationError) as excinfo:
        payload_io.parse_payload(json.dumps(future, separators=(",", ":")))
    assert dict(excinfo.value.readable_identity) == {
        "project_id": REFERENCE_IDS[0], "rush_id": REFERENCE_IDS[1],
        "lot_id": REFERENCE_IDS[2], "page_index": 0, "page_count": 1}

    # 2. document du dispositif dont un champ est abime: cles courtes.
    court = json.loads(payload_io.serialize_payload(payload_for(2)))
    court[payload_io.PAYLOAD_SHORT_KEYS["fps_target"]] = 0
    with pytest.raises(payload_io.PayloadValidationError) as excinfo:
        payload_io.parse_payload(json.dumps(court, separators=(",", ":")))
    assert dict(excinfo.value.readable_identity)["lot_id"] == REFERENCE_IDS[2]
    assert dict(excinfo.value.readable_identity)["page_count"] == 1

    # 3. valeurs hors contrat: omises, jamais recopiees. Un `page_count` valant
    #    `"beaucoup"` leverait un `TypeError` a des kilometres de sa cause.
    abime = json.loads(payload_io.serialize_payload(payload_for(2)))
    abime["sv"] = "9.9"
    abime.update({"lid": 1234, "rid": "", "pc": "beaucoup", "pi": True})
    with pytest.raises(payload_io.PayloadValidationError) as excinfo:
        payload_io.parse_payload(json.dumps(abime, separators=(",", ":")))
    identite = dict(excinfo.value.readable_identity)
    assert identite == {"project_id": REFERENCE_IDS[0]}, identite

    # 4. QR etranger: rien a nommer, et l'attribut existe quand meme.
    with pytest.raises(payload_io.PayloadVersionMissing) as excinfo:
        payload_io.parse_payload('{"colis":"AB12"}')
    assert dict(excinfo.value.readable_identity) == {}
    # Et le defaut de classe est vide, pour un refus leve hors de `parse_payload`.
    assert dict(payload_io.PayloadValidationError("x").readable_identity) == {}


def _future_version_sheet(tmp_path: Path, **champs):
    """Une planche **complete** de version future, scannee et detectee par les vrais
    chemins. Marqueurs de coin reels, QR reel, ingestion reelle (5.1), detection
    reelle (5.2). Rend `(banc, texte)`.

    **Remplace `_planche_1_0`** (story 2.7, `EPIC7-ARB-56`): le format `1.0` a cles
    longues qu'elle fabriquait ne peut plus faire traverser d'identite a travers son
    refus (voir `test_every_refusal_carries_the_identity_still_readable`), donc ne peut
    plus exercer les proprietes de bout en bout de ce fichier -- lecture du statut
    observe (AC 11 de 5.17), risque R12 en reconciliation. Cette fabrique les exerce
    par le seul chemin qui les produit encore: une planche a cles **courtes**, complete
    et valide, dont la version (`sv`) est simplement future.
    """
    import test_scan_detection as banc  # les fabriques de planches vivent la-bas

    payload = payload_io.build_page_payload(
        project_id=champs.pop("project_id", "demo-project-01"),
        rush_id="rush-a1",
        lot_id=champs.pop("lot_id", "lot-0007"),
        page_index=0,
        page_count=champs.pop("page_count", 1),
        fps_target=24.0,
        timecode_base_fps="25/1",
        template_id=banc.PORTRAIT_2F,
        patch_preset_id=REFERENCE_PRESET,
        target_colorspace="bt709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=distinguishable_slots(2),
    )
    assert not champs, f"champs non consommes: {champs}"
    court = json.loads(payload_io.serialize_payload(payload))
    court["sv"] = "9.9"  # version future: meme refus nomme qu'une planche perimee
    return banc, json.dumps(court, separators=(",", ":"))


def test_a_stale_sheet_refused_on_the_scan_path_publishes_what_it_really_saw(
    tmp_path: Path,
) -> None:
    """Comportement, pas source: le refus arrive a l'operateur **et** dit vrai (AC 11).

    Ce test remplace un `grep` de `inspect.getsource` -- deux assertions de presence de
    chaine dans le texte de `_detect_one_page` -- et c'est le point de methode de la
    revue: un test qui lit le code au lieu de l'exercer ne peut pas voir un **ordre
    d'operations** faux. Il ne l'a pas vu. Le refus de version etant leve *dans*
    `resolve_page_identity`, il sortait avant que le statut observe n'ait ete pose, et
    la planche se publiait `not_attempted` alors que son QR avait parfaitement decode
    -- le contraire de la definition de ce statut, et le symetrique exact du defaut
    ferme par 5.2 (bloquant B1 de la revue de 5.17).

    Les quatre choses que la page publie sont donc exigees une par une, et la premiere
    est celle que le grep ne pouvait pas voir. **Planche de version future depuis la
    story 2.7** (voir `_future_version_sheet`): la propriete mesuree -- ordre
    statut/refus, identite conservee -- ne depend pas de la raison du refus de version.
    """
    from mixed_media_utility import qr_codes as qr
    from mixed_media_utility import scan_detection

    banc, texte = _future_version_sheet(tmp_path, page_count=2)
    image = banc._render_page(banc.PORTRAIT_2F, None, qr_text=texte)
    # Le symbole va parfaitement bien: c'est ce qui rend `not_attempted` faux.
    assert qr.decode_qr_image(image).status == qr.DECODE_OK

    project_dir, ingested = banc._ingest(tmp_path, [image], slug="lot-0007")
    rapport = scan_detection.detect_lot_pages(project_dir, ingested)
    page = rapport.pages[0]

    assert page.status == scan_detection.PAGE_REFUSED
    # 1. le statut **observe**, pas celui d'une page dont le QR n'a pas ete tente.
    assert page.qr_status == qr.DECODE_OK, page.qr_status
    assert page.qr_status != scan_detection.QR_NOT_ATTEMPTED
    assert page.as_document()["qr_status"] == qr.DECODE_OK
    # 2. le motif nomme la version rencontree et la version attendue.
    motif = page.refusal_reason or ""
    assert "9.9" in motif, motif
    assert payload_io.PAYLOAD_SCHEMA_VERSION in motif, motif
    # 3. l'identite est conservee: la feuille est la, elle est nommee, elle est
    #    seulement inexploitable.
    assert (page.project_id, page.rush_id, page.lot_id) == (
        "demo-project-01", "rush-a1", "lot-0007")
    assert (page.page_index, page.page_count) == (0, 2)
    # 4. mais rien de ce qui servirait a l'**exploiter** n'est publie: le payload
    #    n'est pas relisible, et nommer n'est pas exploiter.
    assert page.payload is None
    assert page.template_id is None
    # Et la reconciliation de lot **parle**: la planche declare 2 pages, une seule a
    # ete ingeree. C'est la seule detection du risque R12 de la chaine, et une page
    # sans `lot_id` en sortait silencieusement.
    assert "PAGE_COUNT_DIFFERS_FROM_INGESTED" in rapport.warnings, rapport.warnings
    assert "PAGE_INDEX_MISSING" in rapport.warnings, rapport.warnings


def test_a_foreign_stale_sheet_still_triggers_the_lot_reconciliation(
    tmp_path: Path,
) -> None:
    """Deux planches perimees de **lots differents**: le risque R12 en propre (AC 11).

    C'est le cas que le bloquant B1 rendait muet: les deux pages perdant leur `lot_id`,
    le filtre `identified` de `_reconcile_lot` rendait une liste vide et la
    reconciliation sortait sans un controle. Une planche etrangere sur la vitre ne
    declenchait plus rien du tout, et son diagnostic devenait indistinguable de celui
    d'une planche illisible. **Planches de version future depuis la story 2.7**, meme
    motif que le test precedent.
    """
    from mixed_media_utility import scan_detection

    banc, mienne = _future_version_sheet(tmp_path)
    _, etrangere = _future_version_sheet(
        tmp_path, project_id="autre-projet", lot_id="lot-9999")
    pages = [banc._render_page(banc.PORTRAIT_2F, None, qr_text=texte)
             for texte in (mienne, etrangere)]
    project_dir, ingested = banc._ingest(tmp_path, pages, slug="lot-0007")

    with pytest.raises(scan_detection.LotIdentityError) as excinfo:
        scan_detection.detect_lot_pages(project_dir, ingested)
    # Les deux identites sont nommees, par rang de lecture: c'est ce dont l'operateur
    # a besoin pour trier les feuilles sur la vitre.
    lots = {identite[3] for identite in excinfo.value.identities_by_read_rank}
    assert lots == {"lot-0007", "lot-9999"}, lots


def test_both_refusals_stay_catchable_as_the_contract_error() -> None:
    """La parente par laquelle le motif arrive au `refusal_reason` de la page.

    Complement du test de comportement ci-dessus, et pas son substitut: la parente est
    ce qui fait que `_detect_one_page` rattrape le refus au lieu de laisser une trace
    d'exception emporter tout le lot.
    """
    assert issubclass(payload_io.PayloadSchemaVersionRefused,
                      payload_io.PayloadValidationError)
    assert issubclass(payload_io.PayloadVersionMissing,
                      payload_io.PayloadValidationError)


# ---------------------------------------------------------------------------
# AC 4 -- le gain est mesure et epingle, par cardinal
# ---------------------------------------------------------------------------

#: Mesures de la story, re-mesurees ici sur le chemin de production, regime
#: d'identifiants `REFERENCE_IDS` (gabarit `tpl-a4-portrait-2f-v1`, preset
#: `patches-12-v1`, `bt709`, `fps_target = 24.0`): (cardinal, octets avant, octets
#: apres, modules avant, modules apres).
#:
#: Les colonnes « avant » sont **mesurees**, pas recopiees: `_forme_a_cles_longues`
#: reserialise le meme payload sous ses noms longs -- la forme exacte que le papier
#: portait avant la story -- et l'encodeur en rend le cote de symbole. La
#: reconstitution par le surcout de la table (96 + 20n) les verifie une seconde fois,
#: par un chemin independant.
#: **Colonnes « apres » re-mesurees par la story 5.16** (role de page), et elles
#: montent toutes de **9 octets**: c'est le cout du fragment `,"pr":"i"`, uniforme sur
#: les six cardinaux parce que la cle fait deux caracteres et la valeur un seul. Les
#: colonnes « avant » ne bougent pas d'un octet, et c'est voulu -- voir
#: `_forme_a_cles_longues`, qui retire le champ de role du document d'avant parce que
#: ce champ n'existait pas quand ce document etait imprime.
#:
#: **Colonnes « apres » re-mesurees par la story 2.7** (payload 2.1, champ
#: `timecode_base_fps`, valeur `"25/1"`): elles montent de 13 octets, uniformement --
#: le cout du champ ne depend pas du cardinal, meme motif que les 9 octets de la story
#: 5.16. Les colonnes « avant » restent inchangees: `_forme_a_cles_longues` retire
#: desormais aussi `timecode_base_fps`, qui n'existait pas davantage quand le papier
#: portait la forme a cles longues (story 5.17, largement anterieure a 2.7).
#: `modules_apres` du cardinal 2 seul en est affecte (69 -> 73): un octet de plus ne
#: fait pas systematiquement changer la version de symbole.
#:
#: Trois des six cardinaux (avant re-mesure) montaient d'une version de symbole (13,
#: 15, 18 au lieu de 12, 14, 17) et **aucun** n'atteint la version bannie 22. C'est le
#: seul verdict qui compte ici: le budget n'est pas en jeu au regime de reference (464
#: pour 768 de plafond dur), la version l'est.
_GAIN_PAR_CARDINAL = (
    (1, 362, 268, 77, 69),
    (2, 410, 296, 81, 73),
    (3, 458, 324, 89, 73),
    (4, 506, 352, 93, 77),
    (6, 602, 408, 97, 81),
    (8, 698, 464, 105, 89),
)

#: Surcout des noms longs, par construction de la table: **117** octets sur les champs
#: scalaires (`slots` -> `s` compris) et 20 par emplacement (`slot_index` -> `si`,
#: `frame_timecode` -> `ft`). Le passage de 96 a 103 etait l'ecart de longueur du champ
#: ajoute par la story 5.16 (`page_role` -> `pr`, soit 7); celui de 103 a **117** est
#: celui du champ ajoute par la story 2.7 (`timecode_base_fps` -> `tbf`, soit 14). Il
#: est **derive** de la table par
#: `test_the_long_key_overhead_is_the_sum_of_the_table_length_differences`.
_SURCOUT_SCALAIRES = 117
_SURCOUT_PAR_EMPLACEMENT = 20


def _fragment_octets(cle: str, valeur: str) -> int:
    """Octets qu'un champ scalaire de chaine pese dans le JSON compact, virgule comprise.

    Derive et non pose: c'est ce qui rend le **9 octets** de la story 5.16 verifiable
    au lieu d'etre recopie, et c'est ce qui permet de reconstituer le document d'avant
    en retirant exactement le fragment que la story ajoute.
    """
    return len(f',"{cle}":"{valeur}"')


#: Le fragment de role sous ses deux formes de cles. Le court est le **9 octets** que
#: la story 5.16 mesure et publie; le long est ce qu'il aurait coute si la story 5.17
#: n'avait pas raccourci les cles, et c'est ce que le document d'avant ne porte pas.
_FRAGMENT_ROLE_COURT = _fragment_octets(
    payload_io.PAYLOAD_SHORT_KEYS["page_role"], payload_io.PAGE_ROLE_IMAGES)
_FRAGMENT_ROLE_LONG = _fragment_octets("page_role", payload_io.PAGE_ROLE_IMAGES)

#: Meme paire, pour le fragment de cadence source (story 2.7): le document d'avant ne
#: le porte pas non plus -- il n'existait pas encore quand le papier portait la forme a
#: cles longues (story 5.17, largement anterieure a 2.7).
_TIMECODE_BASE_FPS_VALEUR = "25/1"
_FRAGMENT_TIMECODE_BASE_FPS_COURT = _fragment_octets(
    payload_io.PAYLOAD_SHORT_KEYS["timecode_base_fps"], _TIMECODE_BASE_FPS_VALEUR)
_FRAGMENT_TIMECODE_BASE_FPS_LONG = _fragment_octets(
    "timecode_base_fps", _TIMECODE_BASE_FPS_VALEUR)


def _forme_a_cles_longues(payload: dict) -> str:
    """Le texte que le papier portait **avant** la story 5.17: cles longues, JSON compact.

    C'est la serialisation que `serialize_payload` faisait au `baseline_commit` de
    5.17, avant que la projection ne s'y insere -- memes separateurs, meme ASCII, meme
    ordre de champs. La version n'y est pas figee: elle suit celle du payload passe en
    argument (`PAYLOAD_SCHEMA_VERSION` courante), et toutes les versions successives du
    contrat sont de la forme `X.Y`, de meme longueur -- aucun octet n'en depend.
    """
    #: **Le champ de role et la cadence source sont retires** (stories 5.16 et 2.7,
    #: cette derniere posterieure a 5.17 dont ce document simule le baseline). Ce
    #: document est celui que le papier portait avant la story 5.17, et ni l'un ni
    #: l'autre champ n'existait alors: les y laisser fabriquerait un document qui n'a
    #: jamais ete imprime. Ce n'est pas une precaution de style, c'est une mesure: avec
    #: le champ de role seul, le pire cardinal encode sur 109 modules, soit la version
    #: **23** et non la version bannie **22**, et l'assertion qui porte toute la these
    #: de la story 5.17 passerait alors par vacuite. C'est la non-monotonie de la
    #: version de symbole en octets, exactement le piege que l'AC 3 de 5.16 nomme --
    #: ici du cote qui *desarme* un test au lieu de debloquer une page.
    ancien = {cle: valeur for cle, valeur in payload.items()
              if cle not in ("page_role", "timecode_base_fps")}
    return json.dumps(ancien, separators=(",", ":"), ensure_ascii=True)


@pytest.mark.parametrize(
    "cardinal,octets_avant,octets_apres,modules_avant,modules_apres", _GAIN_PAR_CARDINAL
)
def test_the_gain_is_measured_per_cardinal(
    cardinal: int, octets_avant: int, octets_apres: int,
    modules_avant: int, modules_apres: int,
) -> None:
    """Octets **et** modules, des deux cotes: `avant` est mesure comme `apres`.

    Mesure sur `plan_page_payload`, qui serialise le vrai payload et **encode
    reellement** le symbole. Aucun de ces quatre nombres n'est calculable de tete.

    La colonne `modules_avant` n'entrait auparavant que dans une comparaison de
    versions, si bien qu'elle passait avec des valeurs **falsifiees** -- verifie a
    l'execution par la revue, `modules_avant = 89` ou `101` au lieu de 105 passaient
    tous les deux (majeur M8). Elle est donc confrontee a un encodage reel de la forme
    a cles longues, et le cardinal 8 doit tomber sur la version bannie: c'est le
    chiffre qui porte toute la these de la story, et rien ne l'exigeait.
    """
    plan = plan_for(cardinal)
    assert plan.budget.size_bytes == octets_apres, cardinal
    assert plan.module_side == modules_apres, cardinal

    # La colonne « avant », **mesuree** sur la forme que le papier portait.
    ancien = _forme_a_cles_longues(payload_for(cardinal))
    assert len(ancien.encode("utf-8")) == octets_avant, cardinal
    assert int(qr_codes.encode_qr_image(ancien).shape[0]) == modules_avant, cardinal
    # Et reconstituee une seconde fois par un chemin independant: le surcout des noms
    # longs est la somme des ecarts de longueur de la table.
    # Le document d'avant ne porte **ni** le champ de role (story 5.16) **ni** la
    # cadence source (story 2.7): on retire donc leurs deux fragments sous leur forme a
    # cles longues, celle que ce document aurait portee. Les 117 octets de surcout
    # comptent les deux champs, le document ni l'un ni l'autre: les termes retires sont
    # les deux a la fois, d'ou les fragments **longs** et non les courts.
    attendu_avant = (octets_apres + _SURCOUT_SCALAIRES
                     + _SURCOUT_PAR_EMPLACEMENT * cardinal
                     - _FRAGMENT_ROLE_LONG - _FRAGMENT_TIMECODE_BASE_FPS_LONG)
    assert attendu_avant == octets_avant, (cardinal, attendu_avant)
    # Et le cout du champ de role lui-meme, mesure sur le document reellement
    # serialise: les **9 octets** que la story 5.16 publie, identiques sur les six
    # cardinaux -- et celui du champ de cadence source, **13 octets** a `"25/1"`.
    assert _FRAGMENT_ROLE_COURT == 9
    assert _FRAGMENT_TIMECODE_BASE_FPS_COURT == 13

    assert qr_codes.symbol_version(modules_avant) > qr_codes.symbol_version(modules_apres)
    if cardinal == max(CARDINALS):
        # La these de la story, asseree et non racontee: le pire cardinal encodait sur
        # la version que le detecteur de production ne decode a aucune taille.
        assert qr_codes.symbol_version(modules_avant) in qr_codes.QR_BANNED_SYMBOL_VERSIONS
        assert (qr_codes.symbol_version(modules_apres)
                not in qr_codes.QR_BANNED_SYMBOL_VERSIONS)


def test_the_long_key_overhead_is_the_sum_of_the_table_length_differences() -> None:
    """Les deux constantes de surcout sont **derivees** de la table, pas posees.

    Sans cette derivation, l'AC 4 pourrait etre tenue par deux nombres qui s'annulent:
    un octet de trop dans la colonne « apres » et un de moins dans le surcout.
    """
    scalaires = sum(
        len(long) - len(payload_io.PAYLOAD_SHORT_KEYS[long])
        for long in (*payload_io._REQUIRED_SCALAR_FIELDS, "slots")
    )
    par_emplacement = sum(
        len(long) - len(payload_io.PAYLOAD_SHORT_KEYS[long])
        for long in payload_io._REQUIRED_SLOT_FIELDS
    )
    assert scalaires == _SURCOUT_SCALAIRES
    assert par_emplacement == _SURCOUT_PAR_EMPLACEMENT


def test_the_marginal_cost_per_slot_is_measured_and_not_assumed() -> None:
    """~28 octets par emplacement: c'est ce chiffre qui sort le payload du role de borne.

    Il se lit sur les cardinaux mesures et non sur une division approchee: (442 - 246)
    / 7 = 28 exactement sur le regime de reference.
    """
    par_cardinal = {cardinal: plan_for(cardinal).budget.size_bytes
                    for cardinal in CARDINALS}
    assert (par_cardinal[8] - par_cardinal[1]) / 7 == 28.0
    for petit, grand in zip(CARDINALS, CARDINALS[1:]):
        ecart = par_cardinal[grand] - par_cardinal[petit]
        assert ecart == 28 * (grand - petit), (petit, grand, ecart)


# ---------------------------------------------------------------------------
# AC 5 -- aucun cardinal du vocabulaire n'encode plus sur la version 22
# ---------------------------------------------------------------------------


def test_the_banned_version_list_is_not_empty_and_names_twenty_two() -> None:
    """Frontiere negative: sans cette assertion, l'AC 5 serait vraie par vacuite.

    Une liste d'exclusion vide ferait passer tous les tests d'appartenance ci-dessous
    en ne protegeant de rien. C'est le motif de la famille `O` des campagnes du depot.
    """
    assert 22 in qr_codes.QR_BANNED_SYMBOL_VERSIONS
    assert qr_codes.QR_BANNED_SYMBOL_VERSIONS


@pytest.mark.parametrize("cardinal", CARDINALS)
@pytest.mark.parametrize("ids", [REFERENCE_IDS, LONG_IDS], ids=["reference", "longs"])
def test_no_cardinal_of_the_vocabulary_encodes_on_a_banned_version(
    cardinal: int, ids: tuple[str, str, str]
) -> None:
    """Sur les six cardinaux **et** sur le regime des identifiants longs.

    Le regime long est celui qui produisait 109 modules avant la story: c'est lui, et
    non le cardinal 8, qui borne le domaine par le haut. Le tester est ce qui empeche
    de conclure « aucun cardinal n'atteint la 22 » sur le seul regime nominal.
    """
    plan = plan_for(cardinal, ids=ids)
    version = qr_codes.symbol_version(plan.module_side)
    assert version not in qr_codes.QR_BANNED_SYMBOL_VERSIONS, (cardinal, ids[0][:4], version)
    # Et la geometrie planifiee est utilisable, ce que la version bannie interdirait.
    assert plan.geometry_status == qr_codes.GEOMETRY_RELIABLE, (cardinal, ids[0][:4])


def test_the_whole_template_registry_stays_out_of_the_banned_regime() -> None:
    """Balayage large: tous les gabarits, tous les presets, tous les gamut, trois regimes.

    Le vocabulaire des cardinaux ne dit pas tout: `template_id` et `patch_preset_id`
    entrent dans le payload, et le plus long `template_id` du registre coute
    des octets que le cardinal ne porte pas. Mesure: les versions atteignables vont de
    11 a 19, la 22 n'en fait pas partie.
    """
    versions = set()
    gamut_ids = sorted(gamut_map.known_gamut_map_ids())
    template_ids = sorted(page_templates.known_template_ids())
    # Les deux extremites de longueur suffisent a borner le domaine, et gardent ce
    # test sous la seconde: le poids d'un `template_id` est sa longueur, rien d'autre.
    extremes = (min(template_ids, key=len), max(template_ids, key=len))
    for ids in (("a", "b", "c"), REFERENCE_IDS, LONG_IDS):
        for template_id in extremes:
            for preset_id in patch_presets.known_preset_ids():
                for gamut_id in gamut_ids:
                    for cardinal in CARDINALS:
                        payload = payload_io.build_page_payload(
                            project_id=ids[0], rush_id=ids[1], lot_id=ids[2],
                            page_index=0, page_count=999, fps_target=23.976,
                            timecode_base_fps="30000/1001",
                            template_id=template_id, patch_preset_id=preset_id,
                            target_colorspace="bt2020-pq", gamut_map_id=gamut_id,
                            slots=distinguishable_slots(cardinal),
                        )
                        native = qr_codes.encode_qr_image(
                            payload_io.serialize_payload(payload))
                        versions.add(qr_codes.symbol_version(int(native.shape[0])))
    assert versions, "le balayage n'a rien mesure"
    assert not versions & qr_codes.QR_BANNED_SYMBOL_VERSIONS, sorted(versions)
    assert max(versions) < 22, sorted(versions)


# ---------------------------------------------------------------------------
# AC 6 -- la garde porte sur la version du symbole, et plus seulement sur le ratio
# ---------------------------------------------------------------------------


def test_the_symbol_version_follows_the_iso_relation() -> None:
    """Version `V` <-> `4V + 17` modules, de 21 a 177 modules. Exact, sans exception."""
    for version in range(qr_codes.QR_SYMBOL_VERSION_MIN,
                         qr_codes.QR_SYMBOL_VERSION_MAX + 1):
        assert qr_codes.symbol_version(4 * version + 17) == version
    assert qr_codes.symbol_version(21) == 1
    assert qr_codes.symbol_version(105) == 22
    assert qr_codes.symbol_version(177) == 40


@pytest.mark.parametrize("module_side", [0, -1, 17, 20, 22, 50, 104, 106, 181, True])
def test_a_side_that_is_not_a_qr_side_is_refused_not_rounded(module_side) -> None:
    """Un arrondi silencieux rendrait une version fausse, donc une garde fausse.

    La seule facon d'obtenir un tel cote est de lire une dimension ailleurs que sur le
    raster de l'encodeur -- ou de la **poser a la main**, qui est l'erreur d'un
    facteur trois du 2026-08-11 matin.
    """
    with pytest.raises(qr_codes.QRRenderError):
        qr_codes.symbol_version(module_side)


@pytest.mark.parametrize("size_mm", [36.0, 50.0, 80.0, 120.0, 200.0])
def test_a_banned_version_is_never_reliable_however_generous_the_print_size(
    size_mm: float,
) -> None:
    """105 modules a taille genereuse: **pas** `reliable`, quel que soit le ratio.

    Avant cette garde, `check_print_geometry` ne regardait que les px/module et
    classait donc `reliable` un symbole que le detecteur de production ne decode a
    aucune taille: un gabarit 8 frames se composait sans un mot d'avertissement et
    rendait une planche dont le QR ne se relit pas. C'est l'action item ouvert du
    `sprint-status.yaml`.
    """
    ratio = qr_codes.pixels_per_module(105, size_mm, qr_codes.QR_MIN_SCAN_DPI)
    assert ratio >= qr_codes.MIN_PIXELS_PER_MODULE_RELIABLE, ratio
    verdict = qr_codes.check_print_geometry(105, size_mm, qr_codes.QR_MIN_SCAN_DPI)
    assert verdict == qr_codes.GEOMETRY_UNUSABLE, (size_mm, ratio, verdict)


def test_the_ban_is_targeted_and_its_neighbours_stay_reliable() -> None:
    """Les versions 21 (101 modules) et 23 (109) se decodent: la garde ne les touche pas.

    Une garde qui refuserait « tout ce qui est gros » aurait le meme effet sur cette
    page-la et interdirait les lots aux identifiants longs, que la v1 composait sans
    broncher. Ce n'est ni un plafond de resolution ni un plafond de version: c'est la
    v22 en propre.
    """
    for module_side in (101, 109):
        taille = max(qr_codes.QR_PRINT_SIZE_TARGET_MM,
                     qr_codes.required_print_size_mm(module_side))
        assert qr_codes.check_print_geometry(
            module_side, taille, qr_codes.QR_MIN_SCAN_DPI
        ) == qr_codes.GEOMETRY_RELIABLE, module_side


def test_the_ratio_still_governs_outside_the_banned_versions() -> None:
    """La garde de version **s'ajoute** au ratio, elle ne le remplace pas.

    Sans cette verification, une garde qui aurait rendu `unusable` partout, ou qui
    aurait court-circuite le ratio, passerait le test precedent.
    """
    assert qr_codes.check_print_geometry(93, 35.0, 600) == qr_codes.GEOMETRY_RELIABLE
    assert qr_codes.check_print_geometry(93, 27.0, 600) == qr_codes.GEOMETRY_DEGRADED
    assert qr_codes.check_print_geometry(93, 15.0, 600) == qr_codes.GEOMETRY_UNUSABLE


def test_a_page_landing_on_the_banned_version_is_classed_unusable_end_to_end() -> None:
    """Le chemin de production, pas la fonction seule.

    Le regime fautif n'est plus atteignable par un cardinal du vocabulaire -- c'est
    l'objet de l'AC 5 -- mais il reste atteignable par un payload lourd, et c'est
    exactement le cas que la garde existe pour attraper: un champ ajoute au payload
    ramenerait le cardinal 8 ici. La page est donc construite par
    `plan_page_payload`, avec le nombre d'emplacements qui l'y amene.
    """
    fautif = []
    for cardinal in range(1, 30):
        try:
            candidat = plan_for(cardinal)
        except payload_io.PayloadBudgetExceeded:
            break  # au-dela du plafond dur la page est refusee en amont
        if qr_codes.symbol_version(candidat.module_side) == 22:
            fautif.append(cardinal)
    assert fautif, "aucun cardinal n'atteint la version bannie: le test ne mesure rien"
    plan = plan_for(fautif[0])
    assert plan.module_side == 105
    assert plan.geometry_status == qr_codes.GEOMETRY_UNUSABLE
    # Et la taille imprimee est **genereuse**: ce n'est pas le ratio qui la condamne.
    assert qr_codes.pixels_per_module(
        plan.module_side, plan.print_size_mm, plan.scan_dpi
    ) >= qr_codes.MIN_PIXELS_PER_MODULE_RELIABLE
    # Un cardinal voisin, hors du regime banni, reste utilisable: la garde ne refuse
    # pas « les pages lourdes ».
    voisin = plan_for(fautif[0] - 1)
    assert qr_codes.symbol_version(voisin.module_side) != 22
    assert voisin.geometry_status == qr_codes.GEOMETRY_RELIABLE


# ---------------------------------------------------------------------------
# AC 7 -- le majorant d'emprise est recalcule sur le nouveau domaine
# ---------------------------------------------------------------------------


def _payload_minimal(template_id: str, preset_id: str, gamut_id: str) -> dict:
    """Le payload le plus court que le schema permette, pour ce triple de registre.

    Identifiants d'une lettre, un seul emplacement, `target_colorspace` d'un
    caractere: tout ce qui reste variable est la longueur des trois identifiants de
    registre, et c'est precisement ce que le balayage fait varier.
    """
    return payload_io.build_page_payload(
        project_id="a", rush_id="b", lot_id="c",
        page_index=0, page_count=1, fps_target=24.0,
        # Story 2.7: valeur la plus courte que le contrat admette (un chiffre de
        # part et d'autre de la barre), coherente avec le reste de la fabrique.
        timecode_base_fps="1/1",
        template_id=template_id, patch_preset_id=preset_id,
        target_colorspace="b", gamut_map_id=gamut_id,
        slots=[{"slot_index": 0, "frame_timecode": "00:00:00:00"}],
    )


def _payload_calibration(template_id: str, preset_id: str, gamut_id: str) -> dict:
    """Le payload le plus **leger** de la chaine: page de calibration, cardinal **zero**.

    Bloquant B3 de la revue de 5.16: les deux balayages de production partaient du cardinal
    1 et ne posaient jamais le cardinal 0, donc le domaine de modules du payload le plus
    leger de la chaine n'etait mesure nulle part. `slots=[]` n'est licite **que** sous ce
    role -- la garde d'emplacements refuse une planche d'images vide --, ce qui rend cette
    fabrique impossible a confondre avec la precedente.
    """
    return payload_io.build_page_payload(
        project_id="a", rush_id="b", lot_id="c",
        page_index=0, page_count=1, fps_target=24.0,
        # Story 2.7: absente sous ce role (CALIBRATION_ABSENT_FIELDS), sentinelle
        # jamais ecrite -- meme motif que `fps_target` juste au-dessus.
        timecode_base_fps="",
        template_id=template_id, patch_preset_id=preset_id,
        target_colorspace="b", gamut_map_id=gamut_id,
        slots=[],
        page_role=payload_io.PAGE_ROLE_CALIBRATION,
        # AMENDE PAR 5.23: le libelle de chaine est **obligatoire** sous le role `c`,
        # donc le payload le plus leger de la chaine est celui d'un libelle d'**un**
        # caractere -- pas celui d'un libelle absent, qui n'est plus recevable. C'est
        # bien le plancher du domaine reel: rien n'interdit a un operateur de nommer
        # sa chaine `a`.
        scan_chain_label="x",
    )


def test_the_calibration_page_module_domain_is_measured_on_the_production_path() -> None:
    """**Bloquant B3**: le plancher de la page de calibration, mesure et non deduit.

    Le cardinal **0** manquait aux deux balayages du depot, et c'est le seul cardinal du
    payload le plus **leger** de la chaine: une page de calibration ne porte aucun
    emplacement. Consequence mesuree avant correctif: **57** modules contre un plancher
    declare a 61, et une emprise de **39,912 mm** contre un majorant annonce a **39,624** --
    sur 30 des 90 configurations livrees.

    Le piege qui rend ce cas contre-intuitif, et qui est la raison pour laquelle il n'a pas
    ete cherche: l'emprise est en **U**, donc le payload le plus **leger** produit l'emprise
    la plus **grande** sous le regime plafonne a 35 mm. « Plus leger donc plus sur » est un
    raisonnement faux ici, et le docstring de `qr_footprint_bound_mm` l'avait deja ecrit
    pour la version de symbole.
    """
    template_ids = sorted(page_templates.known_template_ids())
    extremes = (min(template_ids, key=len), max(template_ids, key=len))
    cotes: set[int] = set()
    emprises: list[float] = []
    bound = page_templates.calibration_qr_footprint_bound_mm()
    for template_id in extremes:
        for preset_id in sorted(patch_presets.known_preset_ids()):
            for gamut_id in sorted(gamut_map.known_gamut_map_ids()):
                texte = payload_io.serialize_payload(
                    _payload_calibration(template_id, preset_id, gamut_id))
                cote = int(qr_codes.encode_qr_image(texte).shape[0])
                cotes.add(cote)
                taille = max(qr_codes.QR_PRINT_SIZE_TARGET_MM,
                             qr_codes.required_print_size_mm(cote))
                emprises.append(
                    taille * (cote + 2 * qr_codes.QUIET_ZONE_MODULES) / cote)
    assert cotes, "le balayage n'a pas balaye"
    # Le plancher declare est **atteint**, et il est bien **sous** celui des planches: c'est
    # la mesure qui a manque, et c'est elle qui justifie une seconde constante.
    # RE-MESURE PAR 5.23 (AC 8bis): le payload du role `c` perd rush_id, lot_id
    # et fps_target, donc le symbole maigrit et le plancher descend de 57 a **53**.
    # Le litteral est conserve -- c'est lui qui rend la constante falsifiable --
    # mais il est re-mesure sur le chemin de production, jamais recopie.
    assert min(cotes) == page_templates.QR_CALIBRATION_MIN_MODULE_SIDE == 53
    assert min(cotes) < page_templates.QR_MIN_MODULE_SIDE
    # Et le majorant borne **toutes** ces emprises, ce qui n'etait pas le cas avant.
    assert max(emprises) <= bound + 1e-9, (max(emprises), bound)
    # RE-MESURE PAR 5.23: l'emprise maximale suit le **plancher** du domaine, et le
    # plancher est passe de 57 a 53 modules. Elle grandit de 39,912 a 40,283 mm --
    # et c'est bien la propriete en **U** que ce test existe pour epingler: un
    # payload plus LEGER produit une emprise plus GRANDE sous le regime plafonne.
    # La constante est relue, jamais recopiee: si le plancher rebouge, l'assertion
    # suit sans qu'on ait a la reecrire.
    assert max(emprises) == pytest.approx(
        page_templates.qr_footprint_mm(
            page_templates.QR_CALIBRATION_MIN_MODULE_SIDE), abs=1e-6)
    # Frontiere qui mord: le majorant des **planches** ne borne pas cette page. Sans cette
    # assertion, un majorant qui reviendrait a celui des planches passerait le test.
    assert max(emprises) > page_templates.qr_footprint_bound_mm() + 1e-9, (
        "si la page de calibration cessait de sortir du majorant des planches, la seconde "
        "constante n'aurait plus de raison d'etre -- et il faudrait le mesurer, pas le "
        "supposer")


def test_the_module_domain_is_remeasured_on_the_production_path() -> None:
    """Le plancher est le payload **minimal** du schema, **balaye** et non pose.

    Le commentaire de `page_templates` annonce « un test rebalaye les deux » : il n'y
    avait pas de balayage, et le temoin nomme n'etait pas le minimum du domaine
    (`tpl-a4-paysage-1f-m2-v1`, 188 octets, contre 185 pour le plus court
    `template_id` -- majeur M7 de la revue). Le balayage est donc reel ici.

    Il porte sur les **deux extremites de longueur** du registre plutot que sur tous les
    gabarits: la longueur de l'identifiant est tout ce qui pese dans le payload, donc
    ces deux-la bornent le domaine, et 12 encodages tiennent sous la seconde la ou le
    balayage complet coute une demi-minute. (Les cardinaux -- 66 gabarits, 792 encodages
    -- sont retires de ces trois docstrings le 2026-08-12, revue de 5.18, m12: ils ont
    change trois fois en deux jours, et c'est le test qui les compte.) Ce qui est exige n'est pas le cardinal d'octets -- il
    depend des identifiants du projet -- mais le fait que le cote de symbole vaille
    **exactement** le plancher declare sur toute l'etendue du balayage: min = max.
    """
    template_ids = sorted(page_templates.known_template_ids())
    extremes = (min(template_ids, key=len), max(template_ids, key=len))
    cotes, octets = set(), {}
    for template_id in extremes:
        for preset_id in sorted(patch_presets.known_preset_ids()):
            for gamut_id in sorted(gamut_map.known_gamut_map_ids()):
                texte = payload_io.serialize_payload(
                    _payload_minimal(template_id, preset_id, gamut_id))
                cotes.add(int(qr_codes.encode_qr_image(texte).shape[0]))
                octets[(template_id, preset_id, gamut_id)] = len(texte.encode("utf-8"))
    assert len(octets) == 2 * len(patch_presets.known_preset_ids()) * len(
        gamut_map.known_gamut_map_ids()), "le balayage n'a pas balaye"
    # Le plancher est **atteint**, et il l'est partout: min = max = le plancher declare.
    assert cotes == {page_templates.QR_MIN_MODULE_SIDE}, sorted(cotes)

    # Le temoin du minimum d'octets, corrige: le plus **court** `template_id` du
    # registre avec les deux autres identifiants les plus courts.
    plus_court = (min(template_ids, key=len),
                  min(patch_presets.known_preset_ids(), key=len),
                  min(gamut_map.known_gamut_map_ids(), key=len))
    # **206 depuis la story 2.7** (194 + 12 octets du champ de cadence source a sa
    # valeur la plus courte "1/1"; 194 valait depuis la story 5.16, 185 + les 9 octets
    # du champ de role). Le cote de symbole, lui, est **inchange a 61 modules sur la
    # totalite du balayage** -- et c'est cette invariance-la qui borne le domaine, pas
    # le cardinal d'octets: la version 1 du symbole a de la capacite de reste a ce
    # regime.
    assert octets[plus_court] == min(octets.values()) == 206, octets[plus_court]
    # Et le temoin qui figurait dans le commentaire n'est pas ce minimum: 23 caracteres
    # de `template_id` contre 20. C'est l'assertion qui empeche de le recopier a
    # nouveau.
    assert len("tpl-a4-paysage-1f-m2-v1") > len(min(template_ids, key=len))

    # Le plafond est celui du plafond dur de payload, et il est atteint: un texte de
    # exactement `ALERT_BUDGET_BYTES` octets encode sur le cote maximal declare.
    plafond = qr_codes.encode_qr_image("x" * payload_io.ALERT_BUDGET_BYTES)
    assert int(plafond.shape[0]) == page_templates.QR_MAX_MODULE_SIDE


def test_the_footprint_bound_is_recomputed_at_both_extremities() -> None:
    """L'emprise est en U: son majorant est a une **extremite**, jamais au milieu.

    Erreur deja commise une fois sur cette meme grandeur (`SIZING_CARDINAL = 8`,
    « c'est le payload le plus lourd qui commande »). Sous le domaine de la story 5.17
    les deux extremites sont a **0,034 mm** l'une de l'autre, donc le `max` est a un
    demi-module de changer de branche -- raison de plus pour qu'il porte sur les deux.
    """
    bas = page_templates.qr_footprint_mm(page_templates.QR_MIN_MODULE_SIDE)
    haut = page_templates.qr_footprint_mm(page_templates.QR_MAX_MODULE_SIDE)
    bound = page_templates.qr_footprint_bound_mm()
    assert bound == max(bas, haut)
    assert bound == pytest.approx(39.624, abs=1e-3)
    assert bas == pytest.approx(39.590, abs=1e-3)
    # Le milieu du domaine est **sous** les deux extremites: c'est le U.
    milieu = page_templates.qr_footprint_mm(85)
    assert milieu < bas and milieu < haut, (milieu, bas, haut)
    # Le point de bascule se calcule: sous 61 modules le plancher passe devant.
    assert page_templates.qr_footprint_mm(57) > haut


def test_the_bound_follows_the_low_extremity_when_the_domain_moves(monkeypatch) -> None:
    """La **seconde branche** du `max` est exercee, et c'est le seul moyen de la voir.

    Sous le domaine livre c'est le plafond qui gagne, de 0,034 mm: un majorant ecrit
    « l'emprise du plafond » passerait donc tous les autres tests de ce fichier sans
    rien garantir -- il serait un equivalent, jusqu'au jour ou le plancher descend d'une
    version de symbole et ou il deviendrait faux **dans le sens rassurant**.

    C'est exactement le motif de la regle des fabriques du depot, transpose a une
    comparaison: une fabrique qui ne produit qu'un seul cas rend invisible toute erreur
    de selection. Le test descend donc le plancher a 57 modules -- la version de symbole
    immediatement en dessous -- et exige que le majorant change de branche.
    """
    monkeypatch.setattr(page_templates, "QR_MIN_MODULE_SIDE", 57)
    bas = page_templates.qr_footprint_mm(57)
    haut = page_templates.qr_footprint_mm(page_templates.QR_MAX_MODULE_SIDE)
    assert bas > haut, (bas, haut)
    assert page_templates.qr_footprint_bound_mm() == bas


def test_the_footprint_bound_binds_every_real_payload_and_is_attained() -> None:
    """Balayage de **vrais** payloads contre le majorant reserve (AC 7).

    Un majorant trois fois trop grand bornerait tout sans rien garantir: il doit etre
    atteint a moins de 1,5 mm. Le balayage passe par `plan_page_payload`, donc par le
    `max(cible, plancher)` de production -- pas par une formule recopiee.
    """
    bound = page_templates.qr_footprint_bound_mm()
    pire = 0.0
    vus = set()
    for ids in (("a", "b", "c"), REFERENCE_IDS, LONG_IDS):
        for cardinal in (1, 2, 3, 4, 6, 8, 10, 14, 18):
            try:
                plan = plan_for(cardinal, ids=ids)
            except Exception:  # budget depasse: la page est refusee ailleurs
                continue
            emprise = plan.print_size_mm * (
                plan.module_side + 2 * qr_codes.QUIET_ZONE_MODULES) / plan.module_side
            vus.add(plan.module_side)
            pire = max(pire, emprise)
            assert emprise <= bound + 1e-9, (ids[0][:4], cardinal, emprise)
    assert vus, "aucun payload planifie: le balayage ne mesure rien"
    assert min(vus) >= page_templates.QR_MIN_MODULE_SIDE
    assert max(vus) <= page_templates.QR_MAX_MODULE_SIDE
    assert bound - pire < 1.5, (bound, pire)
    # **Le cardinal 0 n'est pas dans ce balayage, et c'est voulu**: ce majorant-ci est celui
    # des **planches d'images**, et une page de calibration en sort de 0,288 mm (bloquant
    # B3). Le domaine de la page sans emplacement est mesure par
    # `test_the_calibration_page_module_domain_is_measured_on_the_production_path`, contre
    # son propre majorant. Confondre les deux ferait remonter le plancher des planches a 57
    # et reprendrait 0,288 mm de bande de dessin a toutes, pour un symbole qu'elles ne
    # portent jamais et un gain en cellules nul.
    assert page_templates.QR_CALIBRATION_MIN_MODULE_SIDE < page_templates.QR_MIN_MODULE_SIDE
    assert page_templates.calibration_qr_footprint_bound_mm() > bound


# ---------------------------------------------------------------------------
# AC 8 -- le budget est reevalue, et le seuil d'alerte cesse d'etre atteint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cardinal", CARDINALS)
@pytest.mark.parametrize("ids", [REFERENCE_IDS, LONG_IDS], ids=["reference", "longs"])
def test_every_cardinal_is_back_under_the_nominal_budget(
    cardinal: int, ids: tuple[str, str, str]
) -> None:
    """Le pire cardinal passe de 698 a 442 octets, sous les 512 du budget nominal.

    Avant la story, 6f (602) et 8f (698) vivaient au-dessus du nominal, sur le plafond
    d'alerte -- c'est-a-dire que la chaine imprimait en permanence des pages
    accompagnees d'un avertissement de budget.
    """
    plan = plan_for(cardinal, ids=ids)
    # **Un cas sort du budget NOMINAL depuis la story 5.16, et il est nomme plutot que
    # relache**: au regime d'identifiants longs (40 caracteres) et au cardinal 8, le
    # payload passait 505 octets, 514 apres la story 5.16 (les 9 octets du champ de
    # role consommant exactement les 7 qui restaient a ce regime), et **527** depuis la
    # story 2.7 (+ 13 octets du champ de cadence source, valeur "25/1").
    #
    # Ce que cela change et ce que cela ne change pas: le budget nominal est un budget
    # **souple** -- la page reste imprimable, avec `HORS_BUDGET_NOMINAL` et un QR
    # eventuellement agrandi (`EPIC4-ARB-2`). Le plafond **dur** de 768 octets, lui,
    # reste tres loin (514), et la version de symbole reste hors de la version bannie:
    # ce sont les deux verdicts que la story 5.16 confronte, et ils tiennent tous les
    # deux. L'AC 8 de la story 5.17 -- « aucun cardinal du vocabulaire au-dessus du
    # nominal » -- cesse en revanche d'etre vraie a ce regime, et c'est le cout a
    # publier, pas a masquer.
    marge_consommee = (cardinal == max(CARDINALS) and ids is LONG_IDS)
    if marge_consommee:
        assert plan.budget.within_nominal is False, plan.budget.size_bytes
        assert plan.budget.size_bytes == 527, plan.budget.size_bytes
        assert plan.budget.size_bytes <= payload_io.ALERT_BUDGET_BYTES
        assert plan.budget.within_alert is True
        assert any(page_payload.WARNING_OVER_NOMINAL_BUDGET in avertissement
                   for avertissement in plan.warnings), plan.warnings
        # Et le depassement est **exactement** la somme des deux fragments ajoutes
        # (role, story 5.16; cadence source, story 2.7): sans eux, ce regime tenait
        # sous le nominal. C'est ce qui distingue « les deux stories ont consomme la
        # marge » de « ce regime etait deja hors budget ».
        assert plan.budget.size_bytes - _FRAGMENT_ROLE_COURT - (
            _FRAGMENT_TIMECODE_BASE_FPS_COURT) <= payload_io.NOMINAL_BUDGET_BYTES
        return
    assert plan.budget.within_nominal is True, (cardinal, ids[0][:4], plan.budget.size_bytes)
    assert plan.budget.size_bytes <= payload_io.NOMINAL_BUDGET_BYTES
    assert plan.warnings == (), plan.warnings


def test_the_absolute_identifier_ceiling_is_the_one_regime_still_over_nominal() -> None:
    """**Ecart mesure avec l'enonce de l'AC 8**, epingle plutot que passe sous silence.

    « Tous les cardinaux du vocabulaire passent sous 512 octets » est vrai au regime de
    reference (pire cas 442) et au regime long des balayages du depot (505). Il est
    **faux** au regime maximal, les trois identifiants a la borne canonique de 48
    caracteres: le cardinal 8 y vaut 529 octets, 17 de trop.

    Ce que la story promet vraiment reste tenu, et c'est le point: le **seuil d'alerte**
    cesse d'etre atteint -- 529 contre un plafond de 768, la ou le meme regime valait
    785 avant la story, c'est-a-dire au-dessus du plafond dur, donc **refuse a
    l'encodage**. Le regime maximal est passe d'impossible a « imprimable avec
    avertissement de budget ».

    Un regime maximal a trois identifiants de 48 caracteres est d'ailleurs theorique:
    `derive_short_id` rend toujours exactement 48 pour un `lot_id`, mais un
    `project_id` et un `rush_id` tous deux a la borne supposent des noms de rush de 48
    caracteres.
    """
    from mixed_media_utility.io import naming

    assert all(len(identifiant) == naming.CANONICAL_ID_MAX_LENGTH
               for identifiant in MAX_IDS)
    tailles = {cardinal: len(payload_io.serialize_payload(
        payload_for(cardinal, ids=MAX_IDS)).encode("utf-8")) for cardinal in CARDINALS}
    # **551 depuis la story 2.7** (538 + 13 octets du champ de cadence source; 538
    # valait depuis la story 5.16, 529 + les 9 octets du champ de role). Le verdict de
    # l'AC 3 de 5.16 se lit ici: ce pire regime atteignable reste a la version **19** du
    # symbole -- (93 - 17) / 4 -- loin du plafond dur. Ni le budget ni la version
    # bannie ne sont en jeu.
    assert tailles[8] == 551, tailles
    assert tailles[8] > payload_io.NOMINAL_BUDGET_BYTES
    assert tailles[8] < payload_io.ALERT_BUDGET_BYTES
    modules_pire = int(qr_codes.encode_qr_image(payload_io.serialize_payload(
        payload_for(8, ids=MAX_IDS))).shape[0])
    assert qr_codes.symbol_version(modules_pire) == 19, modules_pire
    assert (qr_codes.symbol_version(modules_pire)
            not in qr_codes.QR_BANNED_SYMBOL_VERSIONS)
    # Le surcout par rapport au regime de reference est exactement l'ecart de longueur
    # des trois identifiants: rien d'autre ne change.
    ecart = sum(len(long) - len(court) for long, court in zip(MAX_IDS, REFERENCE_IDS))
    assert tailles[8] == 464 + ecart
    # Avant la story, le meme regime depassait le plafond dur: 698 + 87 = 785 > 768.
    assert 698 + ecart > payload_io.ALERT_BUDGET_BYTES
    # Et tous les cardinaux plus petits, eux, tiennent sous le nominal.
    assert all(tailles[cardinal] <= payload_io.NOMINAL_BUDGET_BYTES
               for cardinal in CARDINALS if cardinal < 8), tailles


def test_the_worst_cardinal_of_the_vocabulary_is_pinned_at_442_bytes() -> None:
    # **464 depuis la story 2.7** au regime de reference (451 + 13 octets du champ de
    # cadence source; 451 valait depuis la story 5.16, 442 + 9), et le regime des
    # identifiants longs franchit le budget **nominal** de 15 octets (527, contre 514
    # depuis 5.16, 2 de trop) -- voir `test_every_cardinal_is_back_under_the_nominal_budget`,
    # qui le mesure et le nomme. Ce qui reste vrai des deux cotes, et c'est ce que la
    # story 5.17 protegeait: le plafond **dur** n'est pas approche.
    pires = {ids[0][:4]: max(plan_for(c, ids=ids).budget.size_bytes for c in CARDINALS)
             for ids in (REFERENCE_IDS, LONG_IDS)}
    assert pires["proj"] == 464
    assert pires["pppp"] == 527
    assert max(pires.values()) <= payload_io.ALERT_BUDGET_BYTES, pires


def test_the_slots_per_page_landmarks_are_recomputed_not_copied() -> None:
    """`SLOTS_PER_PAGE_AT_*` re-mesures sur le regime d'identifiants qu'ils documentent.

    4 -> 11 au budget nominal, 10 -> 20 au plafond dur. Ces deux nombres restent
    **documentaires** (la garde est `check_payload_budget`, qui mesure le payload
    reellement serialise), mais un repere faux se recopie: c'est ce qui a produit le
    facteur 2,8 de la story 4.6.

    **Re-mesure par la story 2.7** (payload 2.1, champ `timecode_base_fps`, valeur
    `"25/1"`, 13 octets): le predicteur ecrit par la revue de 5.16 se realise --
    « un treizieme champ scalaire de payload deplacerait ce repere » -- et c'est
    exactement ce treizieme champ. Le repere du budget nominal **cesse de coincider**
    avec son propre regime (11, mesure au payload 2.0): la marge de 2 octets que 5.16
    avait laissee est absorbee, et la vraie frontiere de ce regime descend a 10.
    Celui du plafond dur, lui, **reste 19**: sa marge (768 - 755 = 13 octets avant
    cette story) l'absorbe sans en changer.
    """
    def octets(count: int) -> int:
        payload = payload_io.build_page_payload(
            project_id="demo-project-01", rush_id="rush-a1", lot_id="lot-0007",
            page_index=0, page_count=1, fps_target=24.0, timecode_base_fps="25/1",
            template_id="tpl-a4-portrait-2f-v1", patch_preset_id="patches-12-v1",
            target_colorspace="rec709", gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
            slots=[{"slot_index": index, "frame_timecode": "00:00:00:00"}
                   for index in range(count)],
        )
        return len(payload_io.serialize_payload(payload).encode("utf-8"))

    nominal = max(count for count in range(1, 40)
                  if octets(count) <= payload_io.NOMINAL_BUDGET_BYTES)
    alerte = max(count for count in range(1, 40)
                 if octets(count) <= payload_io.ALERT_BUDGET_BYTES)
    # **Le repere du budget nominal a cesse de coincider avec ce regime, story 2.7**:
    # il vaut 11 dans `qr_codes.py` (mesure au payload 2.0, fichier non modifie par
    # cette story), et la frontiere reelle de ce regime, au payload 2.1, est
    # descendue a 10. Celui du plafond dur, lui, **reste 19** -- coincidence
    # distincte de celle, deja documentee, de la story 5.16.
    assert qr_codes.SLOTS_PER_PAGE_AT_NOMINAL_BUDGET == 11
    assert nominal == 10
    assert nominal != qr_codes.SLOTS_PER_PAGE_AT_NOMINAL_BUDGET
    assert alerte == qr_codes.SLOTS_PER_PAGE_AT_ALERT_BUDGET == 19
    # Le cardinal juste au-dessus depasse: ce sont des frontieres, pas des minorants.
    assert octets(nominal + 1) > payload_io.NOMINAL_BUDGET_BYTES
    assert octets(alerte + 1) > payload_io.ALERT_BUDGET_BYTES

    # Les cinq figures que le commentaire de `qr_codes` publie, epinglees **dans le
    # regime qu'il nomme** (`rec709`, celui de la production), re-mesurees avec le
    # treizieme champ. Elles montent de 13 octets par rapport a leurs valeurs
    # post-5.16 (481 / 510 / 539 / 771 / 800), uniformement: le cout du champ de
    # cadence source ne depend pas du cardinal.
    assert {n: octets(n) for n in (10, 11, 12, 20, 21)} == {
        10: 494, 11: 523, 12: 552, 20: 784, 21: 813}

    # Et la frontiere n'est plus 11/12 mais **10/11**: a 10 emplacements il reste 18
    # octets sous le budget, et un onzieme le depasse quel que soit son cout marginal
    # (28 avant le second chiffre de `slot_index`, 29 apres -- majeur M5 de 5.17,
    # toujours vrai).
    marge = payload_io.NOMINAL_BUDGET_BYTES - octets(nominal)
    assert marge == 18, marge
    for cout_marginal in (28, 29):
        assert octets(nominal) + cout_marginal > payload_io.NOMINAL_BUDGET_BYTES
    # Consequence produit: le payload cesse de borner le cardinal des gabarits, qui
    # s'arretent a 8. La contrainte devient geometrique (`EPIC5-ARB-62`).
    assert qr_codes.SLOTS_PER_PAGE_AT_NOMINAL_BUDGET > max(CARDINALS)


# ---------------------------------------------------------------------------
# AC 10 -- les manifests ne sont pas touches
# ---------------------------------------------------------------------------


def test_no_short_key_ever_reaches_a_persisted_document() -> None:
    """Le payload est ce qui est **imprime**, pas ce qui est persiste.

    Enonce a ne pas croire sur parole: la story 5.9 s'etait declaree « purement
    additive » et son AC 12 a mesure ce que la phrase coutait. Le test compose un vrai
    lot, fabrique le manifest de PDF, et cherche les quatorze cles courtes **comme
    cles** a toute profondeur du document persiste. Le seul endroit du monde ou elles
    ont le droit d'apparaitre est la charge utile serialisee du QR.
    """
    from mixed_media_utility import pdf_composition
    from mixed_media_utility.io import naming, pdf_manifest

    lot_id = naming.build_lot_id("rush-001", 5.0)
    existing = {
        "schema_version": "2.1",
        "project_id": "proj-cles-courtes",
        "created": "2026-08-11T00:00:00Z",
        "rushes": [{
            "rush_id": "rush-001", "source_name": "rush-001.mov",
            "fps_source": 25.0, "fps_source_exact": "25/1",
            "resolution_source": {"width": 1920, "height": 1080},
        }],
        "lots": [{
            "lot_id": lot_id, "rush_id": "rush-001", "state": "extraction",
            "fps_target": 5.0, "fps_target_exact": "5/1",
            # Story 2.7 (payload 2.1): requis par `_lot_identity` pour composer.
            "timecode_base_fps": "25/1",
            "expected_frame_count": 10,
            "frames_dir": f"frames/{naming.derive_short_id('rush-001')}_"
                          f"{naming.format_fps_short(5.0)}",
            "source_frame_count": 50, "source_frame_count_is_exact": True,
            "rounding_policy": "floor",
        }],
        "artifacts": {"frames_dir": "frames"},
        "color": {"target_colorspace": "rec709"},
        "video": {}, "reconstruction": {},
    }
    plan = pdf_composition.compose_lot_plan(
        manifest=existing, lot_id=lot_id, geometry_version="v1")
    merge = pdf_manifest.build_pdf_manifest(
        existing, pdf_manifest.PdfRecord.from_plan(plan))

    courtes = set(payload_io.PAYLOAD_SHORT_KEYS.values())

    def cles(noeud) -> set:
        if isinstance(noeud, dict):
            trouvees = set(noeud) & courtes
            for valeur in noeud.values():
                trouvees |= cles(valeur)
            return trouvees
        if isinstance(noeud, list):
            return set().union(*(cles(item) for item in noeud)) if noeud else set()
        return set()

    assert cles(merge.manifest) == set(), cles(merge.manifest)
    # Et la charge utile imprimee, elle, les porte toutes: sans cette moitie, le test
    # serait vrai sur un lot dont le QR n'aurait pas change.
    imprime = set(json.loads(plan.pages[0].qr.payload_text))
    assert imprime == {payload_io.PAYLOAD_SHORT_KEYS[long]
                       for long in plan.pages[0].qr.payload}
    assert imprime <= courtes


# ---------------------------------------------------------------------------
# AC 9 -- les bancs qui decodent une planche existante sont recenses et traites
# ---------------------------------------------------------------------------

#: Les bancs de recherche qui **decodent** un QR d'une planche deja imprimee. Chacun
#: doit porter la note disant quelle planche il ne peut plus relire et qu'il faut la
#: reimprimer -- sans quoi la prochaine session diagnostiquera un bug la ou il y a une
#: decision (`EPIC5-ARB-60`).
_BANCS_QUI_DECODENT = (
    "analyse_edge_test_scan.py",
    "analyse_measurement_target.py",
    "compare_acquisition_paths.py",
)

#: Les bancs qui **fabriquent** un payload: ils suivent la nouvelle table sans rien
#: perdre, et disent lequel de leurs tirages est perime.
_BANCS_QUI_FABRIQUENT = (
    "build_edge_test_sheet.py",
    "build_measurement_target.py",
    "qr_feasibility_experiment.py",
)


@pytest.mark.parametrize("nom", _BANCS_QUI_DECODENT + _BANCS_QUI_FABRIQUENT)
def test_every_listed_bench_carries_its_note(nom: str) -> None:
    """La note est verrouillee, pas seulement ecrite une fois.

    Un commentaire qu'aucun test ne regarde se perd a la premiere reecriture du banc,
    et c'est precisement la session suivante qui en paie le prix.
    """
    texte = (REPO_ROOT / "scripts" / "research" / nom).read_text(encoding="utf-8")
    assert "5.17" in texte, nom
    assert "EPIC5-ARB-60" in texte, nom
    if nom in _BANCS_QUI_DECODENT:
        assert "reimprim" in texte.lower(), nom
