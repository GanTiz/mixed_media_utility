# -*- coding: utf-8 -*-
"""Maquettes de l'explorateur en MODE SELECTION (story 11.2c, 2026-08-31).

**Ce ne sont pas des captures.** Le mode selection n'existe pas encore dans le
code : ces maquettes existent precisement pour le faire valider avant qu'il soit
ecrit.

Elles sont bati sur `X6`, l'explorateur de la source du Scan, valide par Egan le
2026-08-29 -- et sur **exactement son contenu**, au caractere pres. C'est
deliberé : ce qu'il doit juger est ce que le mode AJOUTE, et rien d'autre. Une
liste de fichiers differente l'obligerait a demeler ce qui change de ce qui
bouge.

La mise en page de la case vient de `_forme_explorateur.ligne_cochable`, qui
copie celle de la liste de cadences (`cadences.py:735`) plutot que d'en inventer
une seconde -- `EPIC11-ARB-103`.

**La regle des fabriques vaut aussi pour ce qu'on MONTRE.** Le curseur est pose
sur la quatrieme entree de sept -- ni la premiere, ni la derniere -- et les
entrees cochees sont dispersees. Une maquette qui coche les trois premieres ne
montrerait pas si la case suit bien sa ligne.

Lancer :  python _gen_selection.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _forme_explorateur import (  # noqa: E402
    RACCOURCIS_SELECTION,
    ecran,
    etiquette,
    ligne_cochable,
    points,
    valider,
)
from construire_maquette import ecrire  # noqa: E402

BANDEAU = ("mmu \u00b7 projet_demo \u00b7 Scan", "temps 1 sur 2 \u00b7 d\u00e9tecter")
TITRE = "Que faut-il d\u00e9tecter ?"
PARENT = "\u2026\\scans\\"
CHEMIN = "D:\\HOKO\\scans\\prestataire_26aout"

# **`RACCOURCIS_SELECTION` a demenage dans `_forme_explorateur.py`** le
# 2026-08-31, avec le lot E bis de la 11.5 : `X6` la porte desormais aussi, et
# une seconde redaction dans ce fichier aurait diverge de la sienne. Son budget
# mesure et le motif de la chute de `↑↓ liste` sont partis avec elle.

def _entrees(cochees: set[str], curseur: str) -> list[str]:
    """Les sept entrees de `X6`, avec leur case.

    `notes_prestataire.txt` n'est pas une source : sa case porte le refus, comme
    une cadence refusee porte le sien (`cadences.py:731`). Elle reste VISIBLE --
    la masquer ferait croire qu'elle n'est pas la, ce que l'explorateur s'interdit
    depuis la 11.2b.
    """
    lignes = [
        ("precedents/", "8 fichiers", "vide"),
        ("planche_01.tiff", "78 Mo", "vide"),
        ("planche_02.tiff", "78 Mo", "vide"),
        ("planche_03.tiff", "81 Mo", "vide"),
        ("planches_04_08.pdf", "312 Mo", "vide"),
        ("notes_prestataire.txt", "\u00b7 pas une source", "refusee"),
    ]
    rendu = []
    for nom, droite, case in lignes:
        if case != "refusee" and nom in cochees:
            case = "cochee"
        rendu.append(ligne_cochable(nom, case, droite, curseur=(nom == curseur)))
    rendu.append(points("1-6 sur 142"))
    return rendu


ETAT_NU = "142 fichiers \u00b7 138 images, 3 PDF, 1 ignor\u00e9"

# --------------------------------------------------------------- X10 --------
# Ce qu'on trouve en arrivant : le mode est ouvert, rien n'est coche. La ligne
# d'etat est celle de `X6`, mot pour mot -- une mesure de selection a zero ne se
# dit pas (AC 5.4).

ecrire("X10-selection-rien-coche.txt", ecran(
    bandeau_gauche=BANDEAU[0], bandeau_droite=BANDEAU[1],
    titre=TITRE, parent=PARENT,
    libelle="Source", chemin=CHEMIN, focus_adresse=False,
    entrees=_entrees(set(), "planche_03.tiff"),
    valide=valider("planche_03.tiff", "81 Mo"),
    etat=ETAT_NU,
    raccourcis=RACCOURCIS_SELECTION,
))

# --------------------------------------------------------------- X11 --------
# Trois cochees, dispersees, et le curseur sur l'une d'elles au MILIEU de la
# liste. Le compte rejoint les mesures existantes en ligne d'etat.
#
# La ligne du bas dit ce que `⏎` ferait : elle valide la SELECTION, pas l'entree
# sous le curseur. C'est le seul point que cette planche laisse ouvert -- voir
# `X11b` pour l'autre redaction.

COCHEES = {"planche_01.tiff", "planche_03.tiff", "planches_04_08.pdf"}
ETAT_AVEC_COMPTE = ETAT_NU + " \u00b7 3 s\u00e9lectionn\u00e9s"

ecrire("X11-selection-trois-cochees.txt", ecran(
    bandeau_gauche=BANDEAU[0], bandeau_droite=BANDEAU[1],
    titre=TITRE, parent=PARENT,
    libelle="Source", chemin=CHEMIN, focus_adresse=False,
    entrees=_entrees(COCHEES, "planche_03.tiff"),
    valide=etiquette("\u23ce", "3 fichiers s\u00e9lectionn\u00e9s   471 Mo",
                     libelle="Valider"),
    etat=ETAT_AVEC_COMPTE,
    raccourcis=RACCOURCIS_SELECTION,
))

# --------------------------------------------------------------- X11b -------
# La meme, avec l'autre redaction du bas : le compte ET le nom sous le curseur.
# Elle coute des colonnes et rend les deux informations d'un coup.

ecrire("X11b-selection-bas-avec-nom.txt", ecran(
    bandeau_gauche=BANDEAU[0], bandeau_droite=BANDEAU[1],
    titre=TITRE, parent=PARENT,
    libelle="Source", chemin=CHEMIN, focus_adresse=False,
    entrees=_entrees(COCHEES, "planche_03.tiff"),
    valide=etiquette("\u23ce", "3 s\u00e9lectionn\u00e9s   \u2022 planche_03.tiff",
                     libelle="Valider"),
    etat=ETAT_AVEC_COMPTE,
    raccourcis=RACCOURCIS_SELECTION,
))
