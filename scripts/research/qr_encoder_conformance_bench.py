"""Banc de conformite de l'encodeur QR: OpenCV contre un encodeur pur Python.

Motif (2026-08-18, arbitrage techno de l'Epic 7)
------------------------------------------------
Viser macOS 12 Intel fige `opencv-contrib-python` a 4.10.0.84. Sur cette
version, 55 tests unitaires de mmu echouent tous avec la meme signature -- le
QR d'une planche synthetique ne se relit pas. Le reflexe est d'accuser le
**decodeur**. Ce banc montre que c'est l'**encodeur**, et il le montre par
croisement: on fait relire par chaque version les rasters produits par chaque
encodeur.

Ce que le banc mesure, et ce qu'il ne mesure pas
------------------------------------------------
Il mesure la **conformite du symbole** sur un rendu parfait: dix pixels par
module, marge ISO/IEC 18004 de quatre modules, aucune degradation, aucune
optique, aucun tirage papier. Un symbole illisible ici ne se relira jamais sur
papier; l'inverse ne se deduit pas -- la robustesse a l'impression se mesure
ailleurs (story 4.6).

Lecture
-------
Le banc imprime en tete la version d'OpenCV qui l'execute. **C'est la
comparaison de deux executions sur deux versions qui fait la mesure**, pas une
execution seule.

    pip install segno          # dependance de banc, jamais de production
    python scripts/research/qr_encoder_conformance_bench.py

`segno` est absent -> les sections qui en dependent sont annoncees sautees
plutot que silencieusement absentes: un banc qui retire la moitie de sa mesure
sans le dire se lit comme un banc vert.
"""

from __future__ import annotations

import random
import sys

import cv2
import numpy as np

try:
    import segno
except ImportError:  # pragma: no cover - depend de l'environnement de banc
    segno = None

# Marge normative ISO/IEC 18004. L'encodeur d'OpenCV n'en emet pas.
QUIET_ZONE_MODULES = 4
# Facteur d'agrandissement entier: un module = un carre de N x N pixels exacts.
# Un agrandissement entier evite la distorsion de grille d'un redimensionnement
# fractionnaire, qui ferait varier le decodage pour une raison etrangere a la
# conformite du symbole.
UPSCALE = 10
# Alphabet des charges utiles aleatoires: caracteres reellement presents dans
# les payloads de production (identifiants de lot, timecodes, separateurs).
PAYLOAD_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789-_:.|"

#: Capacite normative ISO/IEC 18004 en **mode octet, niveau M**, par version.
#: Sert a dire si une version choisie par un encodeur est seulement sous-optimale
#: ou carrement impossible -- une charge qui n'entre pas dans la version choisie
#: produit forcement un symbole malforme, et c'est un diagnostic, pas une mesure.
BYTE_CAPACITY_LEVEL_M = {
    1: 14, 2: 26, 3: 42, 4: 62, 5: 84, 6: 106, 7: 122, 8: 152, 9: 180,
    10: 213, 11: 251, 12: 287, 13: 331, 14: 362, 15: 412, 16: 450, 17: 504,
    18: 560, 19: 624, 20: 666, 21: 711, 22: 779,
}
# Graine fixe: le banc doit rendre le meme verdict d'une execution a l'autre,
# sinon deux executions sur deux versions d'OpenCV ne sont plus comparables.
SEED = 7


def realistic_payload(size: int) -> str:
    """Une charge utile de la forme reellement imprimee, calibree a `size` octets.

    **Le mode d'encodage doit etre le meme des deux cotes, sinon la comparaison
    ne mesure rien.** Une premiere version de ce banc utilisait `"A" * n`:
    OpenCV y voyait de l'alphanumerique (5,5 bits par caractere) quand `segno`,
    force en mode octet, y voyait 8 bits par caractere. Les deux encodeurs
    choisissaient alors des versions differentes pour une raison etrangere a ce
    qu'on mesure, et l'un des deux paraissait gonfler ses symboles.

    Un payload de production est du JSON compact (`io.payload.serialize_payload`):
    accolades, guillemets, minuscules -- aucun n'appartient a l'alphabet du mode
    alphanumerique, donc les deux encodeurs sont en mode octet, sans le forcer.
    """
    import json

    body = json.dumps(
        {
            "s": 1,
            "l": "LOT-demo-1",
            "p": 3,
            "f": ["00:00:1%d:14" % (index % 10) for index in range(size // 14)],
        },
        separators=(",", ":"),
    )
    return body[:size].ljust(size, "0")


def minimum_normative_version(payload: str) -> int:
    """Plus petite version ISO capable de porter `payload` en mode octet, niveau M."""
    needed = len(payload.encode("utf-8"))
    return min(v for v, cap in BYTE_CAPACITY_LEVEL_M.items() if cap >= needed)


def _module_side(matrix: np.ndarray) -> int:
    return int(matrix.shape[0])


def _symbol_version(matrix: np.ndarray) -> int:
    """Version ISO du symbole, deduite de son cote en modules (17 + 4 x v)."""
    return (_module_side(matrix) - 17) // 4


def _render(matrix: np.ndarray) -> np.ndarray:
    """Rendu parfait: marge normative, puis agrandissement entier."""
    padded = np.pad(matrix, QUIET_ZONE_MODULES, constant_values=255)
    return cv2.resize(
        padded, None, fx=UPSCALE, fy=UPSCALE, interpolation=cv2.INTER_NEAREST
    )


def encode_opencv(payload: str) -> np.ndarray:
    params = cv2.QRCodeEncoder_Params()
    params.correction_level = cv2.QRCodeEncoder_CORRECT_LEVEL_M
    return cv2.QRCodeEncoder_create(params).encode(payload)


def encode_segno(payload: str, version: int | None = None) -> np.ndarray:
    """Meme niveau de correction que `encode_opencv`, pour que seul l'encodeur differe."""
    symbol = segno.make(payload, error="m", mode="byte", version=version)
    return np.array(
        [[0 if module else 255 for module in row] for row in symbol.matrix],
        dtype=np.uint8,
    )


def decodes(raster: np.ndarray, payload: str, detector: str) -> bool:
    """Vrai si le raster rend **exactement** la charge utile attendue.

    Comparer au payload plutot que tester « une chaine non vide »: un decodage
    partiel ou errone se lirait sinon comme un succes.
    """
    engine = cv2.QRCodeDetectorAruco() if detector == "aruco" else cv2.QRCodeDetector()
    return engine.detectAndDecode(raster)[0] == payload


def _mark(ok: bool) -> str:
    return "OK" if ok else "KO"


def section_threshold() -> None:
    """A partir de quelle version l'encodeur d'OpenCV cesse d'etre conforme ?

    On fait relire ses symboles par **son propre decodeur**: un encodeur dont la
    sortie n'est pas relue par le decodeur du meme paquet est en faute, sans
    qu'aucune comparaison entre versions ne soit encore necessaire.

    Le verdict se lit sur le detecteur **aruco**, celui de production. Le
    detecteur classique est imprime a titre indicatif mais ne decide pas: il
    echoue sporadiquement sur des symboles par ailleurs conformes (mesure sur
    OpenCV 5.0: un echec isole a 232 octets, entoure de succes a la meme
    version), et un seuil calcule sur lui designerait cette sporadicite comme
    une frontiere de conformite.
    """
    print("\n[1] Seuil de conformite de l'encodeur OpenCV (relu par OpenCV)")
    print("    charges JSON de production; verdict sur aruco, classique indicatif")
    print("    octets  version  modules  minimum ISO  aruco  classique")
    last_ok_version = None
    first_ko_version = None
    for size in range(60, 260, 10):
        payload = realistic_payload(size)
        native = encode_opencv(payload)
        raster = _render(native)
        ok_classic = decodes(raster, payload, "classic")
        ok_aruco = decodes(raster, payload, "aruco")
        version = _symbol_version(native)
        floor = minimum_normative_version(payload)
        if ok_aruco and first_ko_version is None:
            last_ok_version = version
        elif not ok_aruco and first_ko_version is None:
            first_ko_version = version
        verdict = "impossible" if version < floor else f"v{floor}"
        print(
            f"    {size:6d}  v{version:<6d} {_module_side(native):7d}  "
            f"{verdict:>11s}  {_mark(ok_aruco):5s}  {_mark(ok_classic)}"
        )
    if first_ko_version is None:
        print("    -> aucun seuil: l'encodeur est conforme sur tout le domaine balaye")
    else:
        print(
            f"    -> conforme jusqu'a la version {last_ok_version}, "
            f"non conforme des la version {first_ko_version}"
        )


def section_crossover() -> None:
    """Le croisement qui designe le coupable.

    Si le decodeur etait en cause, il echouerait sur les deux encodeurs. S'il
    lit sans faute les symboles conformes d'un encodeur tiers aux memes
    versions, il est hors de cause -- et c'est l'encodeur qui produit des
    symboles malformes.
    """
    print("\n[2] Croisement des encodeurs, relus par CETTE version d'OpenCV")
    if segno is None:
        print("    saute: segno absent (pip install segno)")
        return
    print("    octets  encodeur  version  modules  minimum ISO  aruco  classique")
    for size in (60, 120, 160, 200, 300, 400, 512, 700):
        payload = realistic_payload(size)
        floor = minimum_normative_version(payload)
        for label, native in (
            ("opencv", encode_opencv(payload)),
            ("segno ", encode_segno(payload)),
        ):
            raster = _render(native)
            version = _symbol_version(native)
            gap = "impossible" if version < floor else f"v{floor} {version - floor:+d}"
            print(
                f"    {size:6d}  {label}    v{version:<6d} "
                f"{_module_side(native):7d}  {gap:>11s}  "
                f"{_mark(decodes(raster, payload, 'aruco')):5s}  "
                f"{_mark(decodes(raster, payload, 'classic'))}"
            )


def section_version_22() -> None:
    """La version 22 est-elle indecodable, ou seulement mal encodee ?

    `qr_codes.QR_BANNED_SYMBOL_VERSIONS` bannit la version 22 en production, au
    motif qu'elle ne se decode a aucune taille imprimee sur cinq charges utiles
    distinctes. Cette mesure d'origine n'a jamais teste qu'un seul encodeur.
    On force donc la meme version chez les deux, sur cinq charges utiles
    **reellement distinctes** (aleatoires a graine fixe, pas un caractere
    repete: une charge utile uniforme se comprime et change de version).
    """
    print("\n[3] Version 22: defaut de version, ou defaut d'encodeur ?")
    if segno is None:
        print("    saute: segno absent (pip install segno)")
        return
    rnd = random.Random(SEED)
    print("    charge  encodeur  version  modules  classique  aruco")
    for index in range(5):
        payload = "".join(rnd.choice(PAYLOAD_ALPHABET) for _ in range(600))
        natives = [("segno ", encode_segno(payload, version=22))]
        # L'encodeur d'OpenCV ne se pilote pas en version: on ne le fait figurer
        # que s'il tombe spontanement sur 105 modules pour cette charge utile.
        opencv_native = encode_opencv(payload)
        if _module_side(opencv_native) == 105:
            natives.append(("opencv", opencv_native))
        for label, native in natives:
            raster = _render(native)
            print(
                f"    {index:6d}  {label}    v{_symbol_version(native):<6d} "
                f"{_module_side(native):7d}  "
                f"{_mark(decodes(raster, payload, 'classic')):9s}  "
                f"{_mark(decodes(raster, payload, 'aruco'))}"
            )


def main() -> int:
    print(f"OpenCV {cv2.__version__} | numpy {np.__version__}", end="")
    print(f" | segno {segno.__version__}" if segno else " | segno absent")
    section_threshold()
    section_crossover()
    section_version_22()
    print(
        "\nRappel: une execution seule ne mesure rien. Comparer deux executions "
        "sur deux versions d'OpenCV."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
