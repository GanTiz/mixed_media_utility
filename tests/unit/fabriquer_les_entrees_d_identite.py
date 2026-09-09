# -*- coding: utf-8 -*-
"""Story 11.4b, **lot S6** -- les entrees du releve d'identite, ecrites une fois.

Les planches de ce banc sont fabriquees par les fabriques **d'aujourd'hui**
(`test_scan_calibration_application`), puis **donnees** au releveur
(`outils_identite_scan`) qui, lui, ne connait que `cli`. C'est ce partage qui
rend la mesure d'AC 10.1 possible : le releveur doit tourner sous le `src/` du
`baseline_commit`, ou les fabriques d'aujourd'hui n'existent pas -- et ou un
`sys.path.insert` d'un module de test ferait revenir le `src/` d'aujourd'hui par
la fenetre, mesurant alors deux fois le meme depot.

Les entrees sont donc ecrites **une seule fois**, et les deux passes lisent les
memes octets. Rien d'autre ne garantirait que la difference observee vient du
code et non de la fixture.

Regle des fabriques de `CLAUDE.md`, appliquee ici :

* **deux lots distinguables** (`rush-ident-a` a 5 im/s, `rush-ident-b` a 12 im/s)
  et non un remplissage uniforme : les mesures qui visent un lot en particulier
  visent le **second** ;
* **deux planches par lot**, imprimees sous des presses **differentes** du meme
  tirage, et posees dans l'ordre **inverse** de leur `page_index` -- un
  appariement positionnel page/frame ne se demasque pas autrement (mutant `M33`
  de la story 5.6, `M25` de la 5.7).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RACINE / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_scan_calibration_application as app   # noqa: E402

#: Les deux lots du banc : **le meme rush a deux cadences**. Ce n'est pas un
#: choix de confort -- c'est le cas nominal v2.1 que `CLAUDE.md` nomme au mutant
#: `M25` de la story 5.7 (« deux lots du meme rush a deux cadences »), ou les
#: cardinaux du scan etaient ecrits **sur le mauvais lot**. Deux rushes
#: differents ne cohabitent pas dans un projet : la reconstruction du manifest
#: les refuse, ce que le lot **etranger** ci-dessous mesure exprès.
LOT_A = {"rush_id": "rush-ident", "fps_target": 5.0}
LOT_B = {"rush_id": "rush-ident", "fps_target": 12.0}

#: Le rush du bloc `makepdf`, fabrique **par ffmpeg lui-meme** comme le fait le
#: banc d'identite de l'atelier Extraction (`test_identite_extraction.py`) : le
#: depot reste ainsi sans `.mp4` neuf, et `testsrc` change a chaque frame, donc
#: une duplication ou une permutation d'images se verrait dans les condensats.
#: 30 im/s pendant 1 s = 30 frames source, d'ou **5** frames a 5 im/s et **12**
#: a 12 im/s : deux cadences du meme rush a **comptes differents**, jamais un
#: remplissage uniforme.
RUSH_DU_PDF = "rush_ident"
CADENCES_DU_PDF = (5.0, 12.0)

#: Un lot d'un **autre** rush, qui n'a pas sa place dans le projet du releve :
#: il sert a faire tomber le refus de `check_scan_conflicts` sur le chemin de
#: detection, avec son motif chiffre.
LOT_ETRANGER = {"rush_id": "rush-etranger", "fps_target": 5.0}


def _ecrire_un_lot(dossier: Path, surcharges: dict) -> None:
    """Deux planches du meme lot, presses differentes, **ordre inverse**."""
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False,
                               **surcharges)
    app.write_scan_folder(dossier, [(payloads[1], app.PRESSES_DU_TIRAGE[1]),
                                    (payloads[0], app.PRESSES_DU_TIRAGE[0])])


def fabriquer(racine: Path) -> Path:
    """Ecrire les trois dossiers de scan que le releve consomme."""
    if racine.exists():
        shutil.rmtree(racine)
    racine.mkdir(parents=True)
    app.write_scan_folder(
        racine / "calibration",
        [(app.page_de_calibration_autonome(), app.PRESSE_CALIBRATION)])
    _ecrire_un_lot(racine / "lot-a", LOT_A)
    _ecrire_un_lot(racine / "lot-b", LOT_B)
    _ecrire_un_lot(racine / "lot-etranger", LOT_ETRANGER)
    _fabriquer_le_rush(racine / f"{RUSH_DU_PDF}.mp4")
    return racine


def _fabriquer_le_rush(chemin: Path) -> Path:
    """Le rush du bloc `makepdf`, bit-a-bit reproductible d'une MACHINE a l'autre.

    Le titre disait « d'une session a l'autre » jusqu'au 2026-09-08, et c'etait
    vrai : deux sessions du meme conteneur rendaient bien les memes octets.
    C'est d'une machine a l'autre qu'il ne l'etait pas, et aucun banc ne le
    disait -- le detail est dans le commentaire de `-threads` ci-dessous.

    Il est fabrique ici et non dans le releveur, pour la meme raison que les
    planches : les **deux** passes -- celle du `baseline_commit` et celle
    d'aujourd'hui -- doivent lire les **memes octets**. Un rush regenere entre
    les deux ferait diverger les frames extraites, donc les planches imprimees,
    pour une raison que le banc aurait fabriquee lui-meme.
    """
    resultat = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", "testsrc=size=320x180:rate=30:duration=1",
         "-pix_fmt", "yuv420p",
         # LE NOMBRE DE FILS EST EPINGLE, ET C'EST CE QUI REND LE RUSH
         # REPRODUCTIBLE. Sans lui, x264 prend `1,5 x coeurs` fils, et son
         # multi-threading par FRAMES ne rend pas les memes octets selon leur
         # nombre : le rush depend alors de la MACHINE qui joue le banc.
         # Mesure du 2026-09-08, meme conteneur, meme ffmpeg 6.1.1-3ubuntu5,
         # meme commande a `-threads` pres -- cinq comptes, cinq fichiers :
         #
         #     threads=1  46ca5160...   threads=4  44353f7a...
         #     threads=2  4147ad64...   threads=8  475647b1...
         #     threads=6  487d1d47...  == le DEFAUT sur 4 coeurs (1,5 x 4)
         #
         # C'est ce qui a fait rougir `60_extract_cadence_5` et
         # `61_extract_cadence_12` au run 7 de la CI publique : le runner n'a
         # pas le meme compte de coeurs que la machine de reference, donc pas
         # le meme rush, donc pas les memes frames extraites, donc pas les
         # memes condensats. Rien, dans le produit, n'avait bouge.
         #
         # POURQUOI 6 ET NON 1, qui serait plus naturel : 6 est la valeur sous
         # laquelle le baseline `289f29d` a ete enregistre. La pose a 1
         # changerait les octets du rush, donc ceux des frames, donc ceux des
         # planches imprimees -- et imposerait de regenerer la reference. Le
         # passage a 1 est propose pour la prochaine regeneration du baseline,
         # et il est consigne dans `deferred-work.md` plutot qu'improvise ici.
         "-threads", "6",
         str(chemin)],
        capture_output=True, text=True)
    assert resultat.returncode == 0, resultat.stderr[-2000:]
    return chemin


if __name__ == "__main__":                              # pragma: no cover
    cible = Path(sys.argv[1]).resolve()
    print(fabriquer(cible))
