# -*- coding: utf-8 -*-
"""Dette `CALIB-N1`, moitie TUI -- la barre ne saute plus de 0 a 100.

Le coeur emet desormais DEUX suites de jalons par le meme rappel : l'ingestion
(`scan_ingest.ingest_scan_lot`, la plus longue sur un PDF 300 dpi) puis la
detection. Il ne peut pas faire autrement -- l'invariant du depot est que le
rappel est **passe, jamais enveloppe** (`EPIC7-ARB-79`), et agreger dans
`calibrer_la_chaine` obligerait a l'envelopper, ce qui casserait l'assertion
d'identite de `test_calibrer_la_chaine_TRANSMET_le_rappel`.

C'est donc a l'ecran de recoller les deux suites, et
:class:`RelaisDesPhasesDeLaCalibration` est ce recollement.

**Ce que ce banc mesure, et pourquoi c'est la SUITE et non un jalon** : un banc
de progression qui n'observe qu'un seul jalon ne mesure rien -- c'est
exactement l'etat d'avant le correctif, ou la seule phase observee n'en
emettait qu'un. On mesure donc la suite entiere de ce que l'ecran affiche, sa
**monotonie** (elle ne recule pas d'une phase a l'autre : c'est le defaut que
le relais existe pour fermer) et ses **bornes** (elle part au-dessus de zero et
finit au total).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility.tui import atelier_scan_calibrate as calib
from mixed_media_utility.tui.execution import SurfaceExecution


def _surface() -> SurfaceExecution:
    return SurfaceExecution(unite=calib.UNITE_DE_LA_PASSE)


def _rejouer(cardinaux: tuple[int, int]) -> tuple[SurfaceExecution, list]:
    """Rejouer les deux suites du coeur et relever ce que la barre affiche.

    `cardinaux` est le couple `(pages ingerees, pages detectees)`. Les deux
    sont **distinguables** quand on le demande : une fabrique qui ne produirait
    que des lots de meme cardinal rendrait invisible une correction de cardinal
    manquante -- `mesurer_le_lot_courant` est precisement ce qui la fait.
    """
    surface = _surface()
    relais = calib.RelaisDesPhasesDeLaCalibration(surface)
    releve = []
    for cardinal in cardinaux:
        for faites in range(1, cardinal + 1):
            relais.noter(faites, cardinal)
            releve.append((surface.avancement.faites,
                           surface.avancement.total))
    return surface, releve


# --- la SUITE affichee : monotone, bornee, et elle ne recule pas ------------


def test_les_deux_phases_font_une_SUITE_MONOTONE_de_1_a_2N() -> None:
    """Quatre pages ingerees puis quatre detectees : la barre va de 1/8 a 8/8.

    Avant le relais, la seconde suite REPASSAIT par 1 : l'operateur voyait la
    barre retomber a 12 % au moment ou la detection commencait. C'est ce recul
    que la monotonie mesure ici.
    """
    _surface, releve = _rejouer((4, 4))
    faites = [f for f, _ in releve]
    totaux = {t for _, t in releve}

    assert faites == [1, 2, 3, 4, 5, 6, 7, 8], (
        f"la passe entiere doit se lire d'un seul tenant ; releve : {releve!r}")
    assert totaux == {8}, (
        f"le total de la passe est la somme des deux lots ; releve : {releve!r}")
    assert faites == sorted(faites), "la barre ne recule jamais"
    assert faites[0] >= 1 and faites[-1] == 8, "bornes de la suite"


def test_LA_MIRE_une_page_par_phase_fait_DEUX_jalons_et_non_un() -> None:
    """Le cas du grief, et la borne basse du relais.

    Une mire fait UNE page. Les deux phases emettent donc `(1, 1)` chacune, et
    le second jalon est **egal** au premier -- pas inferieur. Un relais qui
    lirait la frontiere sur un `<` strict laisserait les deux jalons dans le
    premier lot et rendrait `1/2` puis `1/2` : la barre resterait a 50 % sur un
    travail termine, ce qui est le meme mensonge que celui qu'elle corrige.
    """
    _surface, releve = _rejouer((1, 1))
    assert releve == [(1, 2), (2, 2)], (
        f"une mire doit produire DEUX jalons croissants ; releve : {releve!r}")


def test_le_TOTAL_de_la_seconde_phase_CORRIGE_celui_qui_etait_annonce() -> None:
    """Les cardinaux DIFFERENT, et c'est le mesure qui vaut.

    Le relais annonce le second lot au cardinal du premier, faute de mieux :
    la detection parcourt les pages que l'ingestion a produites. Quand une
    page a ete sautee -- fichier illisible --, la detection en compte une de
    moins, et `PasseEnCours.mesurer_le_lot_courant` doit corriger le total de
    la passe plutot que de le laisser sur la promesse.

    **Deux lots de cardinaux distinguables**, precisement pour cela : avec
    `(4, 4)` des deux cotes, une correction absente serait indiscernable d'une
    correction juste.
    """
    _surface, releve = _rejouer((4, 3))
    faites = [f for f, _ in releve]
    totaux = [t for _, t in releve]

    assert faites == [1, 2, 3, 4, 5, 6, 7]
    assert totaux[:4] == [8, 8, 8, 8], (
        "pendant l'ingestion, le total annonce est 4 + 4 -- rien de mieux n'est "
        f"connu ; releve : {releve!r}")
    assert totaux[4:] == [7, 7, 7], (
        "des que la detection dit son cardinal, le total de la passe se "
        f"corrige ; releve : {releve!r}")
    assert faites[-1] == totaux[-1], (
        "la passe se termine a 100 %, sur un total MESURE")


# --- les deux lots sont NOMMES, et le bon est marque en cours ---------------


@pytest.mark.parametrize("jalons_joues,rang_attendu,ou", [
    (1, 0, "tete"),
    (2, 0, "queue de la premiere phase"),
    (3, 1, "tete de la seconde phase"),
    (4, 1, "queue de la seconde phase"),
])
def test_le_lot_COURANT_est_le_bon_a_CHAQUE_BORD(
    jalons_joues: int, rang_attendu: int, ou: str
) -> None:
    """La cible a chaque bord des deux lots, pas seulement au milieu.

    Regle des fabriques, point 4. Un rang errone d'un cran ne se voit pas au
    milieu d'une phase : il se voit **sur les bords**, et c'est la qu'un
    `commencer_le_lot_suivant` appele une fois de trop -- ou une fois de trop
    peu -- change ce que l'operateur lit. Les quatre bords des deux lots d'une
    passe a deux pages par phase sont donc joues un par un.
    """
    surface = _surface()
    relais = calib.RelaisDesPhasesDeLaCalibration(surface)
    suite = [(1, 2), (2, 2), (1, 2), (2, 2)]
    for faites, total in suite[:jalons_joues]:
        relais.noter(faites, total)

    assert surface.passe is not None, "la passe doit etre declaree au 1er jalon"
    assert surface.passe.rang_du_lot_courant == rang_attendu, (
        f"au bord « {ou} », le lot courant doit etre le rang {rang_attendu}")
    assert [lot.nom for lot in surface.passe.lots] == [
        calib.LOT_DE_L_INGESTION, calib.LOT_DE_LA_DETECTION], (
        "les deux lots sont NOMMES : une barre qui n'annonce pas l'etape en "
        "cours ne dit pas a l'operateur ce qui prend du temps")


def test_AVANT_le_premier_jalon_aucun_total_n_est_INVENTE() -> None:
    """Le drapeau varie dans les deux sens : rien recu, rien affiche.

    Un relais qui declarerait la passe a sa construction poserait un cardinal
    que personne n'a mesure. `DESIGN.md` section 3 : un champ non mesure est
    omis, jamais rendu faux.
    """
    surface = _surface()
    calib.RelaisDesPhasesDeLaCalibration(surface)
    assert surface.passe is None
    assert surface.avancement.faites == 0
    assert surface.avancement.total == 0


def test_une_TROISIEME_suite_de_jalons_ne_DEBORDE_pas_la_passe() -> None:
    """Deborder par la queue est le mode de panne d'une agregation.

    Il n'existe aujourd'hui que deux phases emettrices. Si une troisieme
    apparaissait -- ou si le coeur reemettait -- le relais doit rester dans le
    second lot plutot que d'ecrire hors de la liste. La borne est mesuree ici
    parce qu'aucun test positif ne verrait un `IndexError` qui n'arrive qu'en
    production.
    """
    surface = _surface()
    relais = calib.RelaisDesPhasesDeLaCalibration(surface)
    for faites, total in [(1, 2), (2, 2), (1, 2), (2, 2), (1, 2), (2, 2)]:
        relais.noter(faites, total)
    assert surface.passe.rang_du_lot_courant == 1
    assert len(surface.passe.lots) == 2


# --- le cablage : le parcours passe bien par le relais ----------------------


def test_le_PARCOURS_route_ses_jalons_par_le_relais_et_non_par_la_surface(
) -> None:
    """Frontiere -- le relais est CABLE, pas seulement ecrit.

    Le motif `K3`, paye sept fois dans cet epic : « un mecanisme juste, cable
    nulle part ». La mesure porte sur l'arbre syntaxique de la methode qui
    lance la passe : elle doit construire un `RelaisDesPhasesDeLaCalibration`
    et ne plus poster `surface.noter` directement -- ce dernier ferait reculer
    la barre au changement de phase, ce qui est le defaut d'origine.
    """
    import ast

    source = (RACINE / "src" / "mixed_media_utility" / "tui"
              / "atelier_scan_parcours.py")
    arbre = ast.parse(source.read_text(encoding="utf-8"))
    methodes = [membre
                for classe in ast.walk(arbre)
                if isinstance(classe, ast.ClassDef)
                for membre in classe.body
                if isinstance(membre, ast.FunctionDef)
                and membre.name == "lancer_la_passe_de_calibration"]
    assert len(methodes) == 1, "la methode qui lance la passe a disparu"
    methode = methodes[0]

    construit = [n for n in ast.walk(methode)
                 if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "RelaisDesPhasesDeLaCalibration"]
    assert construit, (
        "la passe de calibration doit router ses jalons par le relais des "
        "deux phases ; sans lui la barre RECULE quand la detection commence")

    direct = [n for n in ast.walk(methode)
              if isinstance(n, ast.Attribute) and n.attr == "noter"
              and isinstance(n.value, ast.Name) and n.value.id == "surface"]
    assert not direct, (
        "plus aucun jalon ne va DIRECTEMENT a `surface.noter` : les deux "
        "suites du coeur s'y annuleraient l'une l'autre")
