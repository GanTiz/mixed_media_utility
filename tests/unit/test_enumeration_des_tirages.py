"""L'enumeration des tirages presents balaie TOUTES les mises en page.

Lot B0 ter, AC 2.11 -- `EPIC11-ARB-175`, consequence 2. **Correction de defaut.**

`pdf_composition._rangs_sur_le_disque` liste le dossier `planches/`, puis
**reconstruit** les 99 noms attendus et teste l'appartenance exacte. Le test
etant une egalite de chaine, un nom portant une autre mise en page devient
**invisible** des qu'`EPIC11-ARB-171` fait entrer la forme dans le nom.

Le mode de panne est la **sous-estimation** de la ligne d'eau, donc un rang
**re-attribue** : deux feuilles de mises en page differentes portant le meme
« tirage N ». C'est precisement ce qu'`EPIC11-ARB-92` interdit, et le choix
d'Egan de compter le rang PAR LOT ferme le risque a condition que
l'enumeration, elle, connaisse toutes les formes.

**La route est ecrite, et l'autre est ecartee** (AC 2.11c) : les tirages
DECLARES se lisent a `lots[].sheets_pdfs[].path` (`EPIC11-ARB-90`), qui porte le
chemin reellement ecrit et ne demande aucune reconstruction ; le balayage ne
paie que le cas que lui seul couvre -- un fichier present que le manifeste
ignore. Parser les noms presents est ecarte : ce serait re-deriver une
convention dont `io/naming.py` est proprietaire.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mixed_media_utility import page_templates, pdf_composition
from mixed_media_utility.io import naming, pdf_manifest, project_layout


PROJET = "proj-enum"
RUSH = "rush-enum"
LOT = "rush-enum_24"


def _gabarit(orientation: str, cardinal: int) -> str:
    return page_templates.build_template_id(
        orientation, cardinal, page_templates.DEFAULT_MARGIN_PRESET)


#: **TROIS formes, la cible AU MILIEU de la liste que le CODE parcourt.**
#:
#: La liste parcourue n'est pas celle-ci : c'est `known_template_ids()`, dans
#: son ordre de registre. La cible du balayage est donc placee au milieu **de
#: cet ordre-la**, ce que `_position_dans_le_registre` mesure plutot que de le
#: supposer -- « la position se verifie sur la liste que le CODE parcourt,
#: jamais sur celle que la fabrique ecrit » (regle des fabriques, point 4).
FORMES = (
    (page_templates.ORIENTATION_PORTRAIT, 1),
    (page_templates.ORIENTATION_PAYSAGE, 4),
    (page_templates.ORIENTATION_PORTRAIT, 8),
)


def _position_dans_le_registre(orientation: str, cardinal: int) -> int:
    return page_templates.known_template_ids().index(_gabarit(orientation, cardinal))


@pytest.fixture()
def planches_a_trois_formes(tmp_path: Path) -> Path:
    """Trois tirages du MEME lot, trois mises en page, rangs 1 / 2 / 3.

    Aucun n'est declare au manifeste : c'est le cas que le balayage est seul a
    couvrir, et le seul ou son absence se voit.
    """
    projet = tmp_path / "projet"
    dossier = projet / project_layout.PLANCHES_DIRNAME
    dossier.mkdir(parents=True)
    for rang, (orientation, cardinal) in enumerate(FORMES, start=1):
        nom = naming.build_sheets_pdf_filename(
            PROJET, RUSH, LOT, version_rank=None if rang == 1 else rang,
            template_id=_gabarit(orientation, cardinal))
        (dossier / nom).write_bytes(f"tirage-{rang}".encode())
    return projet


# ---------------------------------------------------------------------------
# B0t.3 -- la fabrique, et la position de la cible sur la liste PARCOURUE
# ---------------------------------------------------------------------------


def test_la_cible_du_balayage_est_bien_AU_MILIEU_du_registre_parcouru():
    """Le temoin de la fabrique elle-meme (regle des fabriques, points 1 et 4).

    Sans lui, la fabrique pourrait glisser vers un jeu de formes toutes en tete
    du registre -- ou toutes en queue -- et les tests ci-dessous resteraient
    verts en cessant de mesurer la terminaison de la boucle. La cible est le
    rang **3**, porte par la troisieme forme ; ce qui compte est sa place dans
    `known_template_ids()`, ni premiere ni derniere.
    """
    registre = page_templates.known_template_ids()
    positions = [_position_dans_le_registre(*forme) for forme in FORMES]
    assert len(set(positions)) == 3, positions
    cible = _position_dans_le_registre(*FORMES[-1])
    assert 0 < cible < len(registre) - 1, (cible, len(registre))
    # Et la cible est STRICTEMENT encadree par les deux autres formes : une
    # fabrique dont la cible serait la premiere ou la derniere du registre
    # laisserait un `break` premature invisible, et l'`or` qui figurait ici
    # rendait l'assertion vraie par construction -- une tautologie, corrigee
    # avant qu'elle ne serve.
    assert min(positions) < cible < max(positions), (positions, cible)


# ---------------------------------------------------------------------------
# B0t.4 -- la sous-estimation, mesuree comme mode de panne, en ensemble EXACT
# ---------------------------------------------------------------------------


def test_les_rangs_vus_sur_le_disque_sont_EXACTEMENT_1_2_3(planches_a_trois_formes):
    """AC 2.11b, et c'est une egalite d'ensembles, jamais une appartenance.

    « Le rang 3 est vu » serait vrai d'un balayage qui verrait 3 et raterait 2.
    Ce qui est mesure est l'ensemble entier -- c'est lui qui alimente la ligne
    d'eau, donc lui qui decide du rang suivant.
    """
    rangs = pdf_composition._rangs_sur_le_disque(
        planches_a_trois_formes, PROJET, RUSH, LOT)
    assert rangs == {1, 2, 3}, rangs


def test_la_ligne_d_eau_et_le_PROCHAIN_rang_sur_trois_formes(planches_a_trois_formes):
    """La consequence qui compte : le prochain tirage est le **4**.

    C'est la formulation que la panne rendait fausse. Un balayage qui ne
    connaitrait qu'une forme verrait un seul tirage, poserait la ligne d'eau a
    1 et rendrait **2** -- un rang deja consomme, donc deux feuilles papier
    portant « tirage 2 ».
    """
    assert pdf_composition.sheets_version_watermark(
        None, LOT, planches_a_trois_formes,
        project_id=PROJET, rush_id=RUSH) == 3
    assert pdf_composition.resolve_sheets_version_rank(
        planches_a_trois_formes, project_id=PROJET, rush_id=RUSH, lot_id=LOT,
        manifest=None) == 4


def test_un_tirage_d_une_AUTRE_forme_ne_peut_pas_faire_RE_ATTRIBUER_un_rang(
        planches_a_trois_formes):
    """Le mode de panne, joue a l'endroit : la **sous-estimation**.

    Le volet symetrique du test precedent. On retire du disque les deux tirages
    des formes 1 et 2 : la ligne d'eau doit alors descendre a 3 -- le rang du
    seul tirage restant --, ce qui montre que les rangs comptes viennent bien
    des FICHIERS et non d'un compteur. Puis on les remet, et l'ensemble
    redevient exact. Un balayage mono-forme rendrait `set()` a la premiere
    etape, ou `{1}` a la seconde.
    """
    dossier = planches_a_trois_formes / project_layout.PLANCHES_DIRNAME
    fichiers = {chemin.name: chemin.read_bytes()
                for chemin in sorted(dossier.iterdir())}
    assert len(fichiers) == 3

    cible = naming.build_sheets_pdf_filename(
        PROJET, RUSH, LOT, version_rank=3,
        template_id=_gabarit(*FORMES[-1]))
    for nom in fichiers:
        if nom != cible:
            (dossier / nom).unlink()
    assert pdf_composition._rangs_sur_le_disque(
        planches_a_trois_formes, PROJET, RUSH, LOT) == {3}

    for nom, octets in fichiers.items():
        (dossier / nom).write_bytes(octets)
    assert pdf_composition._rangs_sur_le_disque(
        planches_a_trois_formes, PROJET, RUSH, LOT) == {1, 2, 3}


def test_le_balayage_ne_voit_PAS_les_tirages_d_un_AUTRE_lot(planches_a_trois_formes):
    """Frontiere negative : le balayage est large en formes, pas en lots.

    Sans ce volet, un balayage qui aurait cesse de comparer le `lot_id`
    passerait tous les tests ci-dessus -- en gonflant la ligne d'eau de chaque
    lot avec les tirages de ses voisins.
    """
    dossier = planches_a_trois_formes / project_layout.PLANCHES_DIRNAME
    intrus = naming.build_sheets_pdf_filename(
        PROJET, "autre-rush", "autre-rush_12", version_rank=9,
        template_id=_gabarit(*FORMES[0]))
    (dossier / intrus).write_bytes(b"intrus")
    assert pdf_composition._rangs_sur_le_disque(
        planches_a_trois_formes, PROJET, RUSH, LOT) == {1, 2, 3}


# ---------------------------------------------------------------------------
# La forme HERITEE reste reconnue -- un rang pose avant ARB-171 est consomme
# ---------------------------------------------------------------------------


def test_un_tirage_ecrit_AVANT_ARB_171_consomme_toujours_son_rang(tmp_path):
    """Aucun fichier deja ecrit n'est renomme (portee tranchee par Egan).

    Un tirage pose sous `..._planches_v2.pdf` a bel et bien consomme le rang 2.
    L'oublier ferait re-attribuer ce rang a une planche neuve -- exactement la
    panne que ce lot ferme, par une autre porte. Le balayage reconnait donc
    l'ancienne forme **en plus** des 63 gabarits ; il ne l'ECRIT jamais.
    """
    projet = tmp_path / "ancien"
    dossier = projet / project_layout.PLANCHES_DIRNAME
    dossier.mkdir(parents=True)
    for rang in (None, 2):
        (dossier / naming.legacy_sheets_pdf_filename(
            PROJET, RUSH, LOT, version_rank=rang)).write_bytes(b"ancien")

    assert pdf_composition._rangs_sur_le_disque(
        projet, PROJET, RUSH, LOT) == {1, 2}
    assert pdf_composition.resolve_sheets_version_rank(
        projet, project_id=PROJET, rush_id=RUSH, lot_id=LOT, manifest=None) == 3


def test_les_deux_formes_se_COMPTENT_ensemble_sans_se_doubler(tmp_path):
    """Le rang se compte PAR LOT (`EPIC11-ARB-175`), toutes formes confondues.

    Ancienne forme au rang 1, forme neuve au rang 2 : l'ensemble est `{1, 2}` et
    le prochain vaut 3. Un balayage qui compterait les deux familles separement
    -- ou qui laisserait l'une masquer l'autre -- ne rendrait pas cet ensemble.
    """
    projet = tmp_path / "mixte"
    dossier = projet / project_layout.PLANCHES_DIRNAME
    dossier.mkdir(parents=True)
    (dossier / naming.legacy_sheets_pdf_filename(
        PROJET, RUSH, LOT)).write_bytes(b"ancien")
    (dossier / naming.build_sheets_pdf_filename(
        PROJET, RUSH, LOT, version_rank=2,
        template_id=_gabarit(*FORMES[1]))).write_bytes(b"neuf")

    assert pdf_composition._rangs_sur_le_disque(
        projet, PROJET, RUSH, LOT) == {1, 2}


# ---------------------------------------------------------------------------
# B0t.2 -- le `break` est TRANCHE : il coupe la FORME, jamais le balayage
# ---------------------------------------------------------------------------


def test_un_gabarit_IRRECEVABLE_ne_fait_pas_disparaitre_les_AUTRES(
        planches_a_trois_formes, monkeypatch):
    """AC 2.11d, et c'est la moitie du lot qui ne se devine pas.

    Le `except naming.NamingError: break` d'origine sortait d'une boucle
    **unique**. Imbrique sous une boucle de gabarits, il change de sens, et il
    fallait choisir : couper la forme courante, ou tout le balayage. Couper
    tout ferait disparaitre les tirages des 63 autres formes des qu'un seul
    gabarit deviendrait irrecevable -- c'est-a-dire produirait la
    sous-estimation que ce lot ferme.

    Le gabarit fautif est glisse **en tete** du registre : c'est la position ou
    un `break` trop large fait le plus de degats, et la seule ou un mutant qui
    le remonterait d'un cran se voit.
    """
    registre = page_templates.known_template_ids()
    monkeypatch.setattr(page_templates, "known_template_ids",
                        lambda: ("tpl-a4-portrait-7f-v2", *registre))
    assert pdf_composition._rangs_sur_le_disque(
        planches_a_trois_formes, PROJET, RUSH, LOT) == {1, 2, 3}


def test_un_gabarit_irrecevable_AU_MILIEU_ne_coupe_pas_la_suite(
        planches_a_trois_formes, monkeypatch):
    """Le meme, la cible **au milieu** : c'est la forme qui tue le `break` large.

    En tete, un `break` qui couperait tout rendrait `set()`, ce que le test
    precedent attrape. Au milieu, il rendrait les rangs des formes qui
    PRECEDENT le fautif -- un ensemble non vide, donc un resultat qui a l'air
    plausible. Seule cette position-la distingue « coupe la forme » de « coupe
    la suite ».
    """
    registre = page_templates.known_template_ids()
    milieu = len(registre) // 2
    truque = (*registre[:milieu], "tpl-a4-portrait-7f-v2", *registre[milieu:])
    monkeypatch.setattr(page_templates, "known_template_ids", lambda: truque)
    # La forme du rang 3 est-elle bien APRES le fautif ? Sinon le test serait
    # vert sans rien mesurer.
    assert truque.index(_gabarit(*FORMES[-1])) > milieu
    assert pdf_composition._rangs_sur_le_disque(
        planches_a_trois_formes, PROJET, RUSH, LOT) == {1, 2, 3}


# ---------------------------------------------------------------------------
# B0t.1 -- la route : les DECLARES ne passent pas par le balayage
# ---------------------------------------------------------------------------


def test_un_tirage_DECLARE_est_vu_par_son_CHEMIN_et_non_par_reconstruction():
    """AC 2.11c : `sheets_pdfs[].path` porte le chemin reellement ecrit.

    Le chemin declare est ici volontairement **hors convention** : aucune
    reconstruction ne le produirait. S'il est compte quand meme, c'est qu'il a
    ete lu et non recalcule -- ce qui est le point d'`EPIC11-ARB-90`, et ce qui
    rattrape le seul cas que le balayage ne peut pas voir : un PDF renomme a la
    main.
    """
    manifest = {
        "lots": [
            {"lot_id": "AVANT_12", "rush_id": "avant"},
            {"lot_id": LOT, "rush_id": RUSH,
             pdf_manifest.SHEETS_INVENTORY_FIELD: [
                 {pdf_manifest.SHEETS_INVENTORY_KEY: "planches/a.pdf"},
                 {pdf_manifest.SHEETS_INVENTORY_KEY: "planches/b-renomme-a-la-main.pdf",
                  "version_rank": 2},
                 {pdf_manifest.SHEETS_INVENTORY_KEY: "planches/c.pdf",
                  "version_rank": 3},
             ]},
            {"lot_id": "APRES_25", "rush_id": "apres"},
        ]
    }
    rangs = {rang for rang, _ in pdf_composition._rangs_declares(manifest, LOT)}
    assert rangs == {1, 2, 3}, rangs


def test_le_balayage_ne_fait_AUCUNE_lecture_de_disque_supplementaire(
        planches_a_trois_formes, monkeypatch):
    """Le cout annonce (AC 2.11c) : `(1 + 63) x 99` chaines, **zero I/O de plus**.

    Le dossier n'est liste qu'une fois, quel que soit le nombre de formes
    balayees. Sans cette mesure, une redaction qui relisterait le dossier par
    gabarit passerait tous les tests ci-dessus en multipliant le cout par 64 --
    et personne ne le verrait avant un projet reel.
    """
    dossier = planches_a_trois_formes / project_layout.PLANCHES_DIRNAME
    listages = []
    vrai = Path.iterdir

    def espion(self):
        if self == dossier:
            listages.append(self)
        return vrai(self)

    monkeypatch.setattr(Path, "iterdir", espion)
    pdf_composition._rangs_sur_le_disque(planches_a_trois_formes, PROJET, RUSH, LOT)
    assert len(listages) == 1, listages


def test_le_parsing_des_noms_presents_est_ECARTE():
    """La troisieme route, ecartee et **mesuree comme absente** (AC 2.11c).

    Parser les noms poses dans `planches/` re-deriverait une convention dont
    `io/naming.py` est proprietaire -- le meme defaut, dans l'autre sens, que
    celui qu'`EPIC11-ARB-171` corrige. La frontiere est negative : aucun lecteur
    de nom de tirage n'existe, et le module d'enumeration n'en appelle aucun.
    """
    import inspect

    source = inspect.getsource(pdf_composition._rangs_sur_le_disque)
    for lecture in ("re.match", "re.search", "rpartition", "split(", "removesuffix"):
        assert lecture not in source, lecture
    # Volet symetrique : `naming` n'expose aucun lecteur de nom de tirage, la ou
    # il en expose bien un pour les frames rescannees.
    assert hasattr(naming, "read_scan_frame_timecode")
    assert not [nom for nom in dir(naming)
                if nom.startswith("read_") and "sheets" in nom]


# ---------------------------------------------------------------------------
# `EPIC11-ARB-225` -- le balayage lit LES DEUX racines
#
# « Une garde de repli fait VARIER le drapeau dont elle depend » (`CLAUDE.md`,
# 2026-09-06). Le drapeau est ici l'arborescence du projet, et il a TROIS
# etats : ANCIEN (`patches/` seul), NEUF (`planches/` seul) et MIXTE. Un banc
# qui ne jouerait que le neuf mesurerait la moitie du produit.
#
# Le mode de panne est nomme et il est cher : sous une racine unique, les
# tirages d'un projet ancien deviennent INVISIBLES, la ligne d'eau est
# sous-estimee, et un rang deja imprime est RE-ATTRIBUE -- deux feuilles papier
# portant le meme « tirage N », ce qu'`EPIC11-ARB-92` interdit et qu'aucun
# fichier ne rattrape une fois l'encre seche.
# ---------------------------------------------------------------------------


def _poser_les_trois_formes(projet: Path, dossiers: tuple[str, ...]) -> None:
    """Les trois tirages des `FORMES`, repartis a tour de role sur `dossiers`.

    A tour de role, et non tous au meme endroit : un remplissage uniforme ne
    distinguerait pas « la bonne racine a ete lue » de « une racine a ete lue
    et l'autre est vide ». Avec deux dossiers, la cible du rang 1 est en tete
    de l'un et celle du rang 3 en queue de l'autre.
    """
    for nom in dossiers:
        (projet / nom).mkdir(parents=True, exist_ok=True)
    for rang, (orientation, cardinal) in enumerate(FORMES, start=1):
        nom_de_fichier = naming.build_sheets_pdf_filename(
            PROJET, RUSH, LOT, version_rank=None if rang == 1 else rang,
            template_id=_gabarit(orientation, cardinal))
        dossier = projet / dossiers[(rang - 1) % len(dossiers)]
        (dossier / nom_de_fichier).write_bytes(f"tirage-{rang}".encode())


@pytest.mark.parametrize("dossiers,etat", (
    (("patches",), "projet ANCIEN"),
    (("planches",), "projet NEUF"),
    (("planches", "patches"), "projet MIXTE"),
    (("patches", "planches"), "projet MIXTE, l'autre repartition"),
))
def test_les_rangs_sont_vus_dans_les_DEUX_racines(
    tmp_path: Path, dossiers: tuple[str, ...], etat: str
) -> None:
    """Les trois rangs sortent, quel que soit l'etat de l'arborescence.

    Les deux repartitions du cas MIXTE ne sont pas une redondance : elles
    posent la cible du rang 1 tantot dans la racine neuve, tantot dans celle
    d'avant, donc a CHAQUE BORD de l'ordre dans lequel le code parcourt ses
    racines (regle des fabriques, point 4).
    """
    projet = tmp_path / "projet"
    _poser_les_trois_formes(projet, dossiers)

    assert pdf_composition._rangs_sur_le_disque(
        projet, PROJET, RUSH, LOT) == {1, 2, 3}, etat


def test_la_ligne_d_eau_d_un_projet_ANCIEN_ne_RE_ATTRIBUE_pas_un_rang(
    tmp_path: Path,
) -> None:
    """Le volet qui dit ce que la racine unique COUTAIT, et il est chiffre.

    Sans la seconde racine, les trois tirages d'un projet ancien sont
    invisibles : la ligne d'eau retombe a 0 et le prochain rang vaut 2 -- le
    rang 2 est deja imprime. Le banc mesure les deux nombres plutot que la
    seule presence de la correction.
    """
    projet = tmp_path / "projet"
    _poser_les_trois_formes(projet, ("patches",))

    ligne_d_eau = pdf_composition.sheets_version_watermark(
        None, LOT, projet, project_id=PROJET, rush_id=RUSH)

    assert ligne_d_eau == 3
    assert pdf_composition.resolve_sheets_version_rank(
        projet, project_id=PROJET, rush_id=RUSH, lot_id=LOT,
        manifest=None) == 4
