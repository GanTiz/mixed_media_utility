"""Le tirage au bord tient-il ? Depouillement du scan de `test_bords_prudent.pdf`.

Cette feuille a ete fabriquee le 2026-08-11 (`build_edge_test_sheet.py`) pour repondre
a UNE question, celle qui bloque l'AC 11 de la story 5.15 : la geometrie resserree place
de l'encre a 5 mm du bord et des marqueurs a 6 mm, la ou la production reste a 15 mm.
Aucune mesure ne couvrait ce regime — la feuille de candidats du 2026-08-11 matin posait
les coins **au milieu de la feuille**, donc elle validait la detection et rien du bord.

Le depouillement ne se contente pas de dire « les marqueurs sont detectes ». Un scan peut
detecter les quatre coins et perdre par ailleurs tout ce qui est a 5 mm : l'imprimante a
une zone non imprimable, le bac a une tolerance de prise, et les deux se cumulent. On
mesure donc, element par element du descripteur, s'il est **la** et s'il est **entier**.

Trois verdicts distincts, a ne pas confondre :

* **detection** — les marqueurs sont-ils lus par le detecteur de production, a leur
  position resserree ? C'est ce qui conditionne le recadrage geometrique ;
* **integrite du tirage** — l'encre posee a 5 mm est-elle sortie de l'imprimante, entiere
  et non rognee ? C'est ce que les quatre reperes de limite d'encre mesurent, et c'est le
  vrai sujet de l'AC 11 ;
* **fidelite geometrique** — les elements sont-ils la ou le descripteur les annonce, une
  fois la page redressee par ses coins ? Un decalage systematique signerait une derive de
  prise papier, qui mangerait la garde sans qu'aucun element manque.

    PYTHONPATH=src:scripts/research python3 scripts/research/analyse_edge_test_scan.py \\
        --scan "projects/projet_demo/srcs/Agressif_TEST_2026-08-11_174937.pdf"
"""

# --- Story 5.17: la planche que ce banc ne relit plus de bout en bout --------
#
# `test_bords_prudent.pdf`, imprime le 2026-08-11, porte un QR au schema de payload
# **1.0** (cles longues). Depuis la story 5.17 (`EPIC5-ARB-60`) le lecteur de production
# ne porte que le `2.0` et il n'existe **aucun lecteur bi-format**.
#
# Ce que ce banc continue de faire, et c'est son sujet: decoder le symbole au bord et
# comparer son texte verbatim au `payload_text` inscrit dans le descripteur de la meme
# fabrication. Le verdict de decodabilite au bord reste donc mesurable sur le tirage
# existant. Ce qu'il ne peut plus faire: en tirer un payload exploitable --
# `io.payload.parse_payload` refuse ce texte en nommant sa version, et aucune
# reconstruction n'en sortira.
#
# Pour retrouver une eprouvette relisible de bout en bout, **reimprimer** la feuille
# avec `build_edge_test_sheet.py`, qui emet desormais du 2.0. Ce n'est pas un bug, c'est
# une decision: ce commentaire existe pour que la prochaine session ne le diagnostique
# pas comme un bug.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, "src")
sys.path.insert(0, "scripts/research")

from mixed_media_utility import color_pipeline, qr_codes  # noqa: E402
from mixed_media_utility.detection import aruco  # noqa: E402
from mixed_media_utility import scan_ingest  # noqa: E402

#: Seuil de presence d'encre. Le papier scanne n'est pas a 255 (voile de numerisation,
#: environ 240-250 sur ce pilote) et un trait de 0,4 mm est **partiellement couvrant** a
#: 600 dpi : il occupe une dizaine de pixels de large mais son minimum ne descend pas au
#: noir d'un aplat. On juge donc sur l'ECART au papier local, pas sur une valeur absolue,
#: et le papier local est mesure a cote de chaque element plutot que suppose.
INK_DROP_MIN = 25.0

#: Fraction de la surface d'une pastille qui doit porter de l'encre pour qu'on la declare
#: **entiere**. Une pastille rognee par la zone non imprimable perd une bande sur un
#: cote: elle reste detectee comme « de l'encre est la » tout en etant inutilisable pour
#: une mesure colorimetrique, qui integre toute la surface. 0,90 laisse passer l'erreur de
#: rectification (un demi-millimetre de biais sur 6 mm coute 8 % de surface) et refuse un
#: rognage reel, qui en coute davantage.
PATCH_COVERAGE_MIN = 0.90


def _load_scan(path: Path) -> tuple[np.ndarray, int]:
    """Rasteriser la page unique du scan, au dpi **mesure** et non au dpi souhaite.

    Le piege est celui de l'AC 7 de la story 5.1, et il est verrouille la : demander
    600 dpi a un PDF dont l'image embarquee est a 200 donne une page de 600 dpi nominaux
    et de 200 dpi reels. Ici la consequence serait plus vicieuse encore qu'un manque de
    detail — toutes les conversions mm <-> px de ce banc passent par ce nombre, donc un
    dpi faux deplacerait chaque fenetre de mesure sans qu'aucune ne paraisse absente.
    """
    measured = scan_ingest._measure_pdf_dpi(path)
    if measured is None:
        raise SystemExit(
            f"{path} ne porte aucune image embarquee: ce n'est pas un scan, et le dpi "
            "reel serait indeterminable."
        )
    dpi = int(round(measured))
    document = scan_ingest._open_pdf(path)
    try:
        if len(document) != 1:
            print(f"  NOTE: le PDF porte {len(document)} pages, seule la 1re est lue.")
        page = scan_ingest._render_pdf_page(document, 0, dpi)
    finally:
        document.close()
    return page, dpi


def _homography_mm_to_px(page: np.ndarray, dpi: int, descriptor: dict,
                         corners, ids) -> np.ndarray | None:
    """Passage mm de page -> px de scan, ajuste sur les quatre coins **prudents**.

    On n'utilise pas `compute_page_homography`: elle rend le redressement de production,
    qui projette vers une page normalisee de dimensions choisies. Ici on veut l'inverse
    — aller chercher dans le scan brut la fenetre ou un element est **cense** etre — donc
    la transformation utile est celle du descripteur vers le pixel scanne.

    Les correspondances sont prises sur le centre de chaque marqueur et non sur ses
    quatre sommets. Motif: le sommet d'un marqueur au bord est precisement ce que le
    rognage peut manger, et un point de correspondance fautif deplacerait toutes les
    fenetres de mesure — donc masquerait le rognage qu'on cherche a voir. Le centre est
    la moyenne des quatre sommets, robuste a l'erosion d'un bord.
    """
    wanted = {element["marker_id"]: element
              for element in descriptor["elements"]
              if element["kind"] == "prudent_corner"}
    if ids is None:
        return None
    found = {int(marker_id): quad.reshape(4, 2)
             for marker_id, quad in zip(ids.flatten(), corners)}
    src, dst = [], []
    for marker_id, element in sorted(wanted.items()):
        if marker_id not in found:
            continue
        src.append([element["centre_x_mm"], element["centre_y_mm"]])
        dst.append(found[marker_id].mean(axis=0))
    if len(src) < 4:
        return None
    matrix, _mask = cv2.findHomography(np.array(src, dtype=np.float64),
                                       np.array(dst, dtype=np.float64), 0)
    return matrix


def _project(matrix: np.ndarray, x_mm: float, y_mm: float) -> tuple[float, float]:
    point = matrix @ np.array([x_mm, y_mm, 1.0], dtype=np.float64)
    return float(point[0] / point[2]), float(point[1] / point[2])


def _window(gray: np.ndarray, matrix, box_mm, pad_mm: float = 0.0):
    """Decouper la fenetre de scan qui correspond a une emprise en mm.

    La fenetre est **ecretee** au raster plutot que refusee, et c'est un correctif, pas
    une commodite. La premiere version rendait `None` des qu'un pixel de la fenetre
    sortait du raster, et le resultat a ete faux dans le sens le plus trompeur : la
    colonne de temoins de droite a ete rapportee « absente 9 fois sur 9 » alors que
    l'apercu du scan les montre toutes les neuf, imprimees et entieres. Ce qui sortait du
    raster n'etait pas la pastille, c'etait l'anneau de papier de 4 mm demande **autour**
    d'elle, la colonne etant a 5 mm d'un bord.

    On distingue donc deux choses que la premiere version confondait : l'emprise de
    l'element, dont la sortie du raster est une vraie perte, et la garde qu'on ajoute
    autour pour mesurer, dont la sortie n'est qu'un manque de place a mesurer. La
    deuxieme s'ecrete ; la premiere se signale. `clipped` dit ce qui a ete perdu, pour
    qu'un ecretage massif ne passe pas pour une mesure normale.
    """
    x0, y0, x1, y1 = box_mm
    points = [_project(matrix, x, y) for x, y in
              ((x0 - pad_mm, y0 - pad_mm), (x1 + pad_mm, y0 - pad_mm),
               (x1 + pad_mm, y1 + pad_mm), (x0 - pad_mm, y1 + pad_mm))]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    left, right = int(round(min(xs))), int(round(max(xs)))
    top, bottom = int(round(min(ys))), int(round(max(ys)))
    left, top = max(0, left), max(0, top)
    right = min(gray.shape[1], right)
    bottom = min(gray.shape[0], bottom)
    if right - left < 2 or bottom - top < 2:
        return None
    return gray[top:bottom, left:right]


def _box_inside_raster(gray: np.ndarray, matrix, box_mm) -> bool:
    """L'emprise de l'element elle-meme tient-elle dans le raster ?

    Separee de `_window` pour que la question soit posee une fois, explicitement, la ou
    elle est un verdict — un element hors raster est perdu — et non melangee a
    l'ecretage de la garde de mesure, qui n'est qu'un manque de place.
    """
    x0, y0, x1, y1 = box_mm
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        px_x, px_y = _project(matrix, x, y)
        if not (0 <= px_x < gray.shape[1] and 0 <= px_y < gray.shape[0]):
            return False
    return True


def _paper_level(gray: np.ndarray, matrix, box_mm, ring_mm: float = 4.0) -> float:
    """Niveau du papier **au voisinage** de l'element, non suppose.

    Un scan a un voile qui varie d'un bord a l'autre de la feuille (eclairage de barrette,
    ombre de bord de vitre). Comparer un trait du bord bas au blanc du centre melangerait
    donc la question posee — « l'encre est-elle sortie ? » — avec un gradient d'eclairage.
    On lit l'anneau autour de l'element et on en prend le quantile haut: le quantile, et
    non la moyenne, pour que l'encre de l'element voisin qui deborde dans l'anneau ne
    tire pas la reference vers le sombre.
    """
    x0, y0, x1, y1 = box_mm
    # Quatre bandes **adjacentes** a l'element plutot qu'un anneau decoupe par
    # difference de deux fenetres concentriques. Le calcul par difference supposait les
    # deux fenetres centrees l'une sur l'autre, ce que l'ecretage au bord du raster rend
    # faux precisement pour les elements du bord — donc pour ceux qui nous interessent.
    # Ici chaque bande est independante: celles qui tombent hors du raster manquent,
    # les autres suffisent.
    strips = (
        (x0, y0 - ring_mm, x1, y0),
        (x0, y1, x1, y1 + ring_mm),
        (x0 - ring_mm, y0, x0, y1),
        (x1, y0, x1 + ring_mm, y1),
    )
    values = []
    for strip in strips:
        window = _window(gray, matrix, strip)
        if window is not None and window.size:
            values.append(window.reshape(-1))
    if not values:
        return float("nan")
    return float(np.quantile(np.concatenate(values), 0.90))


def _element_box_mm(element: dict) -> tuple[float, float, float, float]:
    """Emprise **dessinee** d'un element, silence exclu.

    Volontairement different de `build_edge_test_sheet._element_box`, qui dilate les
    marqueurs de leur zone de silence: la-bas il s'agissait de reserver de la place, ici
    de mesurer de l'encre. Dilater ici ferait entrer du papier dans la fenetre et
    diluerait la couverture d'un marqueur sous son seuil.
    """
    if element["kind"] in ("ink_limit_mark", "text_block"):
        w, h = element["width_mm"], element["height_mm"]
    elif element["kind"] == "qr":
        w = h = element["footprint_mm"]
    else:
        w = h = element["size_mm"]
    return (element["x_mm"], element["y_mm"],
            element["x_mm"] + w, element["y_mm"] + h)


def _ink_report(gray, matrix, element) -> dict:
    """Presence, couverture et integrite de l'encre d'un element."""
    box = _element_box_mm(element)
    if not _box_inside_raster(gray, matrix, box):
        return {"present": False, "reason": "emprise hors du raster (element perdu)"}
    patch = _window(gray, matrix, box)
    if patch is None:
        return {"present": False, "reason": "fenetre degeneree"}
    paper = _paper_level(gray, matrix, box)
    if not np.isfinite(paper):
        return {"present": False, "reason": "papier de reference indisponible"}
    drop = paper - patch.astype(np.float64)
    inked = drop > INK_DROP_MIN
    coverage = float(inked.mean())
    # Couverture par quart de bord: c'est la seule statistique qui distingue « rogne sur
    # un cote » de « pale partout ». Une pastille amputee de sa bande gauche garde une
    # couverture globale de 0,8 et une couverture de bord gauche a zero.
    h, w = inked.shape
    band = max(1, int(round(min(h, w) * 0.15)))
    edges = {
        "haut": float(inked[:band, :].mean()),
        "bas": float(inked[-band:, :].mean()),
        "gauche": float(inked[:, :band].mean()),
        "droit": float(inked[:, -band:].mean()),
    }
    return {
        "present": coverage > 0.05,
        "coverage": coverage,
        "paper": paper,
        "min_level": float(patch.min()),
        "max_drop": float(drop.max()),
        "edges": edges,
    }


def _decode_qr(gray, matrix, element, dpi: int) -> dict:
    """Le QR pose a 5 mm du bord se relit-il ?

    On decoupe large (silence compris plus une garde) et on passe par le detecteur de
    **production**, pas par un detecteur de circonstance: un QR qui ne se lit qu'avec un
    autre detecteur ne se lit pas.
    """
    box = _element_box_mm(element)
    crop = _window(gray, matrix, box, pad_mm=3.0)
    if crop is None:
        return {"decoded": False, "reason": "fenetre hors du raster"}
    bgr = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    try:
        result = qr_codes.decode_qr_image(bgr)
    except Exception as error:  # noqa: BLE001 - on veut le motif, quel qu'il soit
        return {"decoded": False, "reason": f"{type(error).__name__}: {error}"}
    if not result.ok:
        return {"decoded": False,
                "reason": f"statut {result.status}, "
                          f"{result.symbol_count} symbole(s) localise(s)"}
    return {"decoded": True, "matches": result.text == element.get("payload_text"),
            "bytes": len(result.text.encode("utf-8"))}


def _detect_without_stray_ink(gray, matrix, element, dpi: int) -> str:
    """Un marqueur non lu l'aurait-il ete sans le trait parasite qui le traverse ?

    Sert un cas precis et non generalisable : la sonde du bord droit de cette feuille est
    traversee par le contour de bande, un trait de 0,3 mm que `build_edge_test_sheet`
    **dessine sans l'enregistrer** aupres de sa garde de non-recouvrement. L'essai brut
    est donc nul — il ne mesure pas le bord, il mesure un defaut de la feuille — et le
    reimprimer couterait un tirage a Egan pour une information deja presente dans le
    raster.

    La reconstruction est explicite sur ce qu'elle vaut : un trait fin et rectiligne se
    retire par filtrage median le long de sa direction, ce qui restitue le motif sous-
    jacent la ou il est **connu par continuite**. Si le marqueur se lit apres retrait, le
    bord est valide sous reserve ; s'il ne se lit toujours pas, la cause est ailleurs et
    l'essai reste nul. Dans aucun des deux cas ce resultat ne vaut un essai propre, et il
    est rapporte comme reconstruit.
    """
    box = _element_box_mm(element)
    quiet = float(element.get("quiet_zone_mm", 5.0))
    crop = _window(gray, matrix, box, pad_mm=quiet + 4.0)
    if crop is None:
        return "impossible (fenetre indisponible)"
    # Noyau vertical: le trait parasite est vertical, donc c'est le long de la verticale
    # que le median voit une majorite de pixels sains. Un noyau carre lisserait aussi les
    # modules du marqueur et detruirait ce qu'on cherche a lire.
    # Largeur du noyau: **juste** plus large que le trait, et surtout plus etroite qu'un
    # module du marqueur. Une premiere version prenait trois fois l'epaisseur du trait,
    # soit 55 px, alors qu'un module de ce marqueur en mesure 30 : la fermeture effacait
    # donc les modules du marqueur avec le trait, et le « toujours non detecte » qu'elle
    # rendait ne disait rien du trait. Le rapport de deux entre le module et le noyau est
    # la seule chose qui rend cette reconstruction interpretable.
    thickness_px = max(3, int(round(0.4 / 25.4 * dpi)))
    module_px = element["size_mm"] / (aruco.marker_modules_per_side()) / 25.4 * dpi
    kernel = 2 * thickness_px + 1
    if kernel >= module_px:
        return (f"impossible: noyau de {kernel} px contre un module de "
                f"{module_px:.0f} px, le retrait effacerait le marqueur")
    repaired = cv2.morphologyEx(
        crop, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (kernel, 1)))
    for label, image in (("brut", crop), ("trait retire", repaired)):
        _corners, ids = aruco.detect_markers(
            cv2.cvtColor(image, cv2.COLOR_GRAY2BGR), dpi=dpi)
        seen = sorted(int(i) for i in ids.flatten()) if ids is not None else []
        if element["marker_id"] in seen:
            return f"DETECTE sur le recadrage ({label})"
    return "toujours non detecte apres retrait du trait"


def _printable_extent(gray: np.ndarray, matrix, descriptor: dict) -> dict:
    """Jusqu'ou l'encre est-elle reellement sortie, mesure sur les quatre reperes.

    Chaque repere de limite d'encre est un trait de 0,4 mm pose **exactement** a
    `PRINTER_MARGIN_MM` du bord. Son sort donne la reponse binaire dont l'AC 11 a besoin,
    et sa couverture donne la nuance: un trait a 0,55 de couverture est sorti mais entre
    dans la zone de degrade de la tete, donc la marge tenue est plus grande que 5 mm.
    """
    verdicts = {}
    for element in descriptor["elements"]:
        if element["kind"] != "ink_limit_mark":
            continue
        report = _ink_report(gray, matrix, element)
        verdicts[element["label"]] = report
    return verdicts


def _print_drift(descriptor: dict, found: dict) -> dict:
    """Echelle et translation reelles du tirage, mesurees sur les marqueurs eux-memes.

    C'est la grandeur que la feuille n'avait pas ete concue pour mesurer et qui est
    ressortie de son depouillement : le contenu imprime n'est pas a l'echelle du PDF. Un
    marqueur de 15,0 mm nominal se mesure a 15,1-15,2 mm, et l'ecart est **coherent sur
    les neuf marqueurs lus**, donc ce n'est ni un artefact de coin ni du bruit de
    detection.

    L'echelle se lit sur le **cote** de chaque marqueur, qui est une longueur connue et
    locale. Elle ne se lit pas sur l'ecart entre deux marqueurs eloignes: cet ecart
    melangerait l'echelle du tirage avec l'erreur de positionnement de chacun, et sur une
    feuille dont on soupconne justement le placement, on ne peut pas se servir du
    placement pour mesurer l'echelle.
    """
    scales = {}
    for element in descriptor["elements"]:
        marker_id = element.get("marker_id")
        if marker_id is None or marker_id not in found:
            continue
        quad = found[marker_id]
        sides = [float(np.hypot(*(quad[(i + 1) % 4] - quad[i]))) for i in range(4)]
        scales[marker_id] = float(np.mean(sides))
    return scales


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", required=True)
    parser.add_argument(
        "--descriptor",
        default="_bmad-output/test-artifacts/cible-de-mesure/test_bords_prudent.json")
    parser.add_argument("--dump-png", default=None,
                        help="ecrire un apercu reduit du scan, pour l'oeil")
    args = parser.parse_args(argv)

    descriptor = json.loads(Path(args.descriptor).read_text(encoding="utf-8"))
    page, dpi = _load_scan(Path(args.scan))
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY)
    page_w_mm, page_h_mm = descriptor["page_size_mm"]
    print(f"scan : {args.scan}")
    print(f"  raster {page.shape[1]} x {page.shape[0]} px a {dpi} dpi "
          f"= {page.shape[1] / dpi * 25.4:.1f} x {page.shape[0] / dpi * 25.4:.1f} mm")
    print(f"  feuille attendue : {page_w_mm:.1f} x {page_h_mm:.1f} mm")

    if args.dump_png:
        scale = 1200.0 / max(page.shape[:2])
        small = cv2.resize(page, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        cv2.imwrite(args.dump_png, small)
        print(f"  apercu ecrit: {args.dump_png}")

    view = aruco.as_detection_view(page)
    corners, ids = aruco.detect_markers(view, dpi=dpi)
    quads = ({int(marker_id): quad.reshape(4, 2)
              for marker_id, quad in zip(ids.flatten(), corners)}
             if ids is not None else {})
    found = sorted(quads)
    expected = sorted(element["marker_id"] for element in descriptor["elements"]
                      if element["kind"] in ("prudent_corner", "registration_probe"))
    print(f"\nDETECTION ArUco au detecteur de production ({dpi} dpi)")
    print(f"  attendus : {expected}")
    print(f"  detectes : {found}")
    missing = [marker_id for marker_id in expected if marker_id not in found]
    extra = [marker_id for marker_id in found if marker_id not in expected]
    print(f"  manquants: {missing or 'aucun'}")
    if extra:
        print(f"  en trop  : {extra} (faux positifs)")

    matrix = _homography_mm_to_px(page, dpi, descriptor, corners, ids)
    if matrix is None:
        print("\nARRET: les quatre coins prudents ne sont pas tous detectes, donc")
        print("aucune fenetre de mesure n'est localisable. C'est en soi le verdict.")
        return 1

    # Echelle reelle mesuree sur la diagonale des coins: elle dit si la feuille a ete
    # scannee a son echelle ou etiree par le bac.
    diag_mm = float(np.hypot(page_w_mm - 2 * 15.5, page_h_mm - 2 * 15.5))
    p0 = _project(matrix, 15.5, 15.5)
    p2 = _project(matrix, page_w_mm - 15.5, page_h_mm - 15.5)
    diag_px = float(np.hypot(p2[0] - p0[0], p2[1] - p0[1]))
    print(f"  echelle mesuree coin a coin : {diag_px / diag_mm * 25.4 / dpi:.4f} "
          f"(1.0000 = feuille a l'echelle)")

    print("\nLIMITE D'ENCRE REELLE (traits de 0,4 mm a 5,0 mm du bord)")
    for label, report in _printable_extent(gray, matrix, descriptor).items():
        if not report.get("present"):
            print(f"  {label:8s} ABSENT  ({report.get('reason', 'aucune encre')})")
            continue
        print(f"  {label:8s} present, couverture {report['coverage']:.2f}, "
              f"papier {report['paper']:.0f}, minimum {report['min_level']:.0f}, "
              f"chute max {report['max_drop']:.0f}")

    print("\nPASTILLES TEMOINS (6 mm, posees a 5,0 mm du bord lateral)")
    clipped, whole = [], 0
    for index, element in enumerate(e for e in descriptor["elements"]
                                    if e["kind"] == "witness_patch"):
        report = _ink_report(gray, matrix, element)
        side = "gauche" if element["x_mm"] < page_w_mm / 2 else "droit"
        if not report.get("present"):
            clipped.append((index, side, element["y_mm"], "absente"))
        elif report["coverage"] < PATCH_COVERAGE_MIN:
            worst = min(report["edges"], key=report["edges"].get)
            clipped.append((index, side, element["y_mm"],
                            f"couverture {report['coverage']:.2f}, "
                            f"bord {worst} a {report['edges'][worst]:.2f}"))
        else:
            whole += 1
    print(f"  entieres : {whole} / 18")
    for index, side, y_mm, why in clipped:
        print(f"  pastille {index:2d} ({side}, y={y_mm:.1f}) : {why}")

    print("\nSONDES DE REPERAGE (marqueurs de 10 mm)")
    for element in descriptor["elements"]:
        if element["kind"] != "registration_probe":
            continue
        marker_id = element["marker_id"]
        seen = marker_id in found
        report = _ink_report(gray, matrix, element)
        state = "DETECTE" if seen else "non detecte"
        if report.get("present"):
            detail = (f"encre presente, couverture {report['coverage']:.2f}, "
                      f"bords " + " ".join(f"{k}={v:.2f}"
                                           for k, v in report["edges"].items()))
        else:
            detail = f"AUCUNE ENCRE ({report.get('reason', '')})"
        print(f"  {marker_id} {element['label']:18s} {state:12s} {detail}")
        if not seen:
            recovered = _detect_without_stray_ink(gray, matrix, element, dpi)
            print(f"     essai reconstruit (trait parasite retire) : {recovered}")

    print("\nDERIVE DU TIRAGE (cote mesure de chaque marqueur lu, nominal -> mesure)")
    nominal = {element["marker_id"]: element["size_mm"]
               for element in descriptor["elements"] if "marker_id" in element}
    ratios = []
    for marker_id, side_px in sorted(_print_drift(descriptor, quads).items()):
        side_mm = side_px / dpi * 25.4
        ratio = side_mm / nominal[marker_id]
        ratios.append(ratio)
        print(f"  {marker_id:2d}  nominal {nominal[marker_id]:5.1f} mm  "
              f"mesure {side_mm:6.2f} mm  echelle {ratio:.4f}")
    if ratios:
        median = float(np.median(ratios))
        print(f"  echelle mediane {median:.4f} -> le contenu est "
              f"{(median - 1) * 100:+.2f} % de sa taille nominale, soit "
              f"{(median - 1) * page_w_mm / 2:+.2f} mm de deplacement au bord lateral "
              f"et {(median - 1) * page_h_mm / 2:+.2f} mm au bord haut/bas.")

    print("\nQR (symbole a 5,0 mm du bord haut)")
    for element in descriptor["elements"]:
        if element["kind"] != "qr":
            continue
        verdict = _decode_qr(gray, matrix, element, dpi)
        ink = _ink_report(gray, matrix, element)
        if verdict["decoded"]:
            print(f"  DECODE, charge utile identique: {verdict['matches']}, "
                  f"{verdict['bytes']} octets")
        else:
            print(f"  NON DECODE: {verdict['reason']}")
        if ink.get("present"):
            print(f"  encre: couverture {ink['coverage']:.2f}, bords " +
                  " ".join(f"{k}={v:.2f}" for k, v in ink["edges"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
