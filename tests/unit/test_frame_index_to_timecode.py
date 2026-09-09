# -*- coding: utf-8 -*-
"""Le banc de `codec_profiles.frame_index_to_timecode`.

**Pourquoi ce fichier existe.** La fonction a ete portee depuis la branche de
l'Epic 7 le 2026-08-29, ou elle vivait **sans aucun test**. C'est cette absence
qui a laisse recuperer `scan_corrections.py` sans elle : le banc de ce module
est vert a 72 sur 72 **et ne touche jamais** `payload_depuis_l_identite`, la
seule fonction qui l'appelle. Un module « verifie fonctionnel » l'etait donc sur
tout sauf sur ce dont la story avait besoin.

La mesure qui compte ici est l'**aller-retour** avec `timecode_to_frame_index`,
qui existait deja : deux arithmetiques de timecode qui divergent ne se voient
que sur le nom des TIFF produits, des mois plus tard.
"""
from __future__ import annotations

from fractions import Fraction

import pytest

from mixed_media_utility import codec_profiles


#: Des cadences deux a deux distinguables, entiere, decimale, et NTSC -- une
#: fabrique uniforme ne demasquerait pas un plafond calcule sur la mauvaise.
CADENCES = (24, 25, Fraction(30000, 1001), 12.5, 50)


@pytest.mark.parametrize("cadence", CADENCES)
@pytest.mark.parametrize("index", [0, 1, 12, 24, 25, 1000, 86399, 123456])
def test_l_ALLER_RETOUR_est_l_IDENTITE(cadence, index):
    """L'index -> timecode -> index rend le rang de depart."""
    tc = codec_profiles.frame_index_to_timecode(index, cadence)
    assert codec_profiles.timecode_to_frame_index(tc, cadence) == index


@pytest.mark.parametrize("cadence,index,attendu", [
    (25, 0, "00:00:00:00"),
    (25, 24, "00:00:00:24"),
    (25, 25, "00:00:01:00"),
    (25, 1525, "00:01:01:00"),
    # 12,5 im/s : le champ `ff` est borne par le PLAFOND, donc 13 valeurs
    # (0 a 12) -- c'est la convention d'ffmpeg, mesuree par `_frame_limit`.
    (12.5, 12, "00:00:00:12"),
    (12.5, 13, "00:00:01:00"),
    # NTSC : le plafond de 29,97 est 30, la partie fractionnaire n'entre
    # jamais dans la notation hh:mm:ss:ff.
    (Fraction(30000, 1001), 30, "00:00:01:00"),
])
def test_des_valeurs_NOMMEES_tombent_juste(cadence, index, attendu):
    assert codec_profiles.frame_index_to_timecode(index, cadence) == attendu


def test_le_compteur_REBOUCLE_a_24_heures():
    """`validate_timecode` refuse `hh > 23` : le rebouclage n'est pas optionnel.

    Un rush de vingt minutes demarrant a 23:50:00:00 deborde -- sans
    rebouclage, la fonction rendrait un timecode que le depot refuse.
    """
    une_journee = 24 * 3600 * 25
    assert codec_profiles.frame_index_to_timecode(une_journee, 25) == "00:00:00:00"
    assert codec_profiles.frame_index_to_timecode(une_journee + 25, 25) == "00:00:01:00"
    # La derniere frame avant le rebouclage existe et se valide.
    dernier = codec_profiles.frame_index_to_timecode(une_journee - 1, 25)
    assert dernier == "23:59:59:24"
    assert codec_profiles.validate_timecode(dernier, 25) == dernier


@pytest.mark.parametrize("cadence", CADENCES)
def test_tout_timecode_produit_est_ACCEPTE_par_la_validation(cadence):
    """Volet symetrique : ce que la fonction ecrit, le depot le relit.

    Sans lui, la fonction pourrait rendre une forme coherente avec elle-meme et
    refusee partout ailleurs -- c'est le defaut que trois arithmetiques
    separees produisent.
    """
    for index in (0, 1, 599, 3600, 86399):
        tc = codec_profiles.frame_index_to_timecode(index, cadence)
        assert codec_profiles.validate_timecode(tc, cadence) == tc


def test_deux_INDEX_distincts_ne_rendent_pas_le_MEME_timecode():
    """Une collision serait deux frames au meme nom de fichier.

    La cible est en SECONDE position dans chaque couple : un defaut qui rendrait
    toujours le premier element ne se demasque pas autrement.
    """
    for cadence in CADENCES:
        rendus = [codec_profiles.frame_index_to_timecode(i, cadence)
                  for i in range(0, 200)]
        assert len(set(rendus)) == 200, f"collision a {cadence}"
