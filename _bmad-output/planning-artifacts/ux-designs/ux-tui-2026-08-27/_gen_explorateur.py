# -*- coding: utf-8 -*-
"""Maquettes de l'EXPLORATEUR DE DOSSIERS -- version 2 (2026-08-29).

Refonte apres les 17 retours d'Egan sur la v1. Ce qui change, et pourquoi :

* **`Entree` valide le dossier SURLIGNE**, il n'entre plus. C'etait le grief
  central : « long de scroller 150 dossiers pour valider », « c'est mon point :
  c'est lent ». Valider coute desormais UNE frappe depuis n'importe ou, et la
  regle rejoint `EPIC11-ARB-45` a la lettre -- « la validation retient et suit
  l'issue sous le curseur ». On entre par `→` (ou `Tab`, comme Egan le
  proposait au depart) ;
* **les deux « boutons » ne sont plus des cibles**. Ils deviennent deux
  ETIQUETTES VIVES : celle du haut dit ou `←` mene, celle du bas dit ce que `⏎`
  va valider. On ne les atteint jamais, donc on ne les traverse jamais ;
* **un seul curseur a l'ecran**, par construction. La v1 en montrait deux sur
  `X6` -- « il y a deux curseurs sur ton image. Impossible. » C'etait vrai ;
* **« Dossier parent » remonte en haut**, colle a la barre d'adresse, avec `←`
  pour glyphe -- la touche elle-meme, qui est le « glyphe precedent plus
  graphique » demande sans ajouter un signe de plus a la table du `DESIGN.md` ;
* **le compte de rushes et de lots disparait de l'explorateur** (« laisse
  tomber le compteur de rushes et de lots a ce stade, c'est pour les projets de
  la liste »). Il ne reste que `● projet` et le nombre de sous-dossiers.

Lancer :  python _gen_explorateur.py
"""
from __future__ import annotations

# La FORME de l'explorateur (mise en page, etiquettes vives, lignes de
# raccourcis) vit desormais dans `_forme_explorateur.py` : l'atelier Extraction
# ouvre le meme explorateur a son cinquieme site (`EPIC11-ARB-48`, maquettes
# `E2-1b` et `E2-1c`), et deux copies de la meme mise en page auraient derive au
# premier raffinement. Rien n'a change au passage -- les `X*.txt` sont
# identiques au caractere pres avant et apres l'extraction.
from _forme_explorateur import (  # noqa: E402
    RACCOURCIS,
    RACCOURCIS_ADRESSE,
    RACCOURCIS_CACHES,
    RACCOURCIS_SELECTION,
    ecran,
    ligne,
    ligne_cochable,
    points,
    valider,
)
from construire_maquette import ecrire, regle  # noqa: E402


BANDEAU_PROJET = ("mmu \u00b7 \u2014 aucun projet \u2014", "v0.1")


# --------------------------------------------------------------- X1 ---------

ecrire("X1-explorateur-depart.txt", ecran(
    bandeau_gauche=BANDEAU_PROJET[0], bandeau_droite=BANDEAU_PROJET[1],
    titre="Ouvrir un projet",
    parent="\u2026\\Documents\\",
    libelle="Dossier", chemin="D:\\HOKO\\Documents\\mmu", focus_adresse=False,
    entrees=[
        ligne("archives/", "0 sous-dossier"),
        ligne("projects/", "6 sous-dossiers", curseur=True),
        ligne("rushes_2026/", "12 sous-dossiers"),
        ligne("scans/", "3 sous-dossiers"),
    ],
    valide=valider("projects/"),
    etat="4 sous-dossiers \u00b7 aucun projet",
    raccourcis=RACCOURCIS,
))


# --------------------------------------------------------------- X2 ---------

ecrire("X2-explorateur-apres-entree.txt", ecran(
    bandeau_gauche=BANDEAU_PROJET[0], bandeau_droite=BANDEAU_PROJET[1],
    titre="Ouvrir un projet",
    parent="\u2026\\mmu\\",
    libelle="Dossier", chemin="D:\\HOKO\\Documents\\mmu\\projects",
    focus_adresse=False,
    entrees=[
        ligne("chendj_mat/", "\u25cf projet", curseur=True),
        ligne("essais_papier/", "2 sous-dossiers"),
        ligne("planche_hiver_2026/", "0 sous-dossier"),
        ligne("projet_demo/", "\u25cf projet"),
        ligne("rebuts/", "8 sous-dossiers"),
    ],
    valide=valider("chendj_mat/", "\u25cf porte un projet"),
    etat="5 sous-dossiers \u00b7 2 projets",
    raccourcis=RACCOURCIS,
))


# --------------------------------------------------------------- X3 ---------

ecrire("X3-explorateur-liste-longue.txt", ecran(
    bandeau_gauche=BANDEAU_PROJET[0], bandeau_droite=BANDEAU_PROJET[1],
    titre="Ouvrir un projet",
    parent="\u2026\\mmu\\",
    libelle="Dossier", chemin="D:\\HOKO\\Documents\\mmu\\rushes_2026",
    focus_adresse=False,
    entrees=[
        ligne("01_reperages/", "4 sous-dossiers", curseur=True),
        ligne("02_tournage_avril/", "17 sous-dossiers"),
        ligne("03_tournage_mai/", "12 sous-dossiers"),
        ligne("04_tournage_juin/", "9 sous-dossiers"),
        ligne("05_plateau_studio/", "2 sous-dossiers"),
        ligne("06_drone/", "0 sous-dossier"),
        ligne("07_interviews/", "23 sous-dossiers"),
        ligne("08_ambiances/", "5 sous-dossiers"),
        points("1-8 sur 27"),
    ],
    valide=valider("01_reperages/"),
    etat="27 sous-dossiers",
    raccourcis=RACCOURCIS,
))


# --------------------------------------------------------------- X4 ---------

ecrire("X4-explorateur-defilement.txt", ecran(
    bandeau_gauche=BANDEAU_PROJET[0], bandeau_droite=BANDEAU_PROJET[1],
    titre="Ouvrir un projet",
    parent="\u2026\\mmu\\",
    libelle="Dossier", chemin="D:\\HOKO\\Documents\\mmu\\rushes_2026",
    focus_adresse=False,
    entrees=[
        points(),
        ligne("11_nuit_ext/", "6 sous-dossiers"),
        ligne("12_nuit_int/", "3 sous-dossiers"),
        ligne("13_plans_de_coupe/", "41 sous-dossiers"),
        ligne("14_raccords/", "0 sous-dossier"),
        ligne("15_sons_seuls/", "2 sous-dossiers"),
        ligne("16_timelapse/", "7 sous-dossiers"),
        ligne("17_essais_pellicule/", "1 sous-dossier", curseur=True),
        points("11-17 sur 27"),
    ],
    valide=valider("17_essais_pellicule/"),
    etat="27 sous-dossiers \u00b7 10 au-dessus, 10 en dessous",
    raccourcis=RACCOURCIS,
))


# --------------------------------------------------------------- X5 ---------

ecrire("X5-explorateur-adresse-collee.txt", ecran(
    bandeau_gauche=BANDEAU_PROJET[0], bandeau_droite=BANDEAU_PROJET[1],
    titre="Ouvrir un projet",
    parent="\u2026\\13_plans_de_coupe\\",
    libelle="Dossier",
    chemin="\u2026\\13_plans_de_coupe\\selection_v3\u2588",
    focus_adresse=True,
    entrees=[
        ligne("brut/", "0 sous-dossier"),
        ligne("etalonne/", "2 sous-dossiers"),
        ligne("proxy/", "0 sous-dossier"),
    ],
    valide=valider("selection_v3", "le dossier de la barre"),
    etat="\u2026\\mmu\\rushes_2026\\13_plans_de_coupe\\selection_v3\\etalonne\\v2",
    raccourcis=RACCOURCIS_ADRESSE,
))


# --------------------------------------------------------------- X6 ---------

# **`X6` porte la colonne de coche depuis le 2026-08-31** (story 11.5, lot E
# bis, note 4 d'Egan). Ce n'est pas un ajout de confort : `E3-1` -- le site que
# cette maquette dessine -- monte desormais l'explorateur avec
# `selection_multiple=True`, parce que c'est le seul chemin par lequel la
# QUATRIEME forme d'entree d'`EPIC7-ARB-88` -- une sequence de chemins qui fait
# UN lot -- soit atteignable depuis la TUI.
#
# Sans cette reprise, `X6` et `X11` dessinaient le MEME site -- meme bandeau,
# meme dossier, memes six entrees -- l'un avec la colonne, l'autre sans : deux
# dessins d'un seul ecran, dont un perime. C'est exactement le defaut que la
# revue de la 11.2c a paye le matin meme sur cette maquette-la (`R11`), et il
# se serait represente le jour ou quelqu'un aurait lu `X6` pour savoir a quoi
# ressemble le depot.
#
# **La redondance qui reste avec `X10` est assumee, et elle est dite** : les
# deux ecrans coincident desormais a deux details pres (le rang du curseur et
# la ligne du bas), parce que `_gen_selection.py` a bati `X10` sur « exactement
# le contenu de `X6`, au caractere pres » pour qu'Egan juge ce que le mode
# AJOUTE. `X10`/`X11`/`X11b` restent le dossier de validation du COMPOSANT
# (11.2c) ; `X6` reste le dessin du SITE. Deux dessins identiques ne peuvent
# pas se contredire -- c'est un dessin perime qui le peut.
#
# Ce qui NE bouge pas : le curseur reste sur `planche_01.tiff`, aucune entree
# n'est cochee, et la ligne d'etat compte le DOSSIER. Une mesure de selection a
# zero ne se dit pas, et c'est ce que `X10` porte deja mot pour mot.
ecrire("X6-explorateur-fichiers.txt", ecran(
    bandeau_gauche="mmu \u00b7 projet_demo \u00b7 Scan",
    bandeau_droite="temps 1 sur 2 \u00b7 d\u00e9tecter",
    titre="Que faut-il d\u00e9tecter ?",
    parent="\u2026\\scans\\",
    libelle="Source", chemin="D:\\HOKO\\scans\\prestataire_26aout",
    focus_adresse=False,
    entrees=[
        # `8 fichiers`, et la maquette avait RAISON contre le code
        # (`EPIC11-ARB-121`, Egan 2026-08-31 : « c'est une bonne feature,
        # j'aimerais bien la conserver »). Aujourd'hui la colonne d'un dossier
        # compte ses SOUS-DOSSIERS partout ; sur un ecran qui cherche des
        # fichiers, ce chiffre ne repond pas a la question qu'on se pose. La
        # story 11.2c fait compter au dossier ce que le SITE cherche.
        ligne_cochable("precedents/", "vide", "8 fichiers"),
        ligne_cochable("planche_01.tiff", "vide", "78 Mo", curseur=True),
        ligne_cochable("planche_02.tiff", "vide", "78 Mo"),
        ligne_cochable("planche_03.tiff", "vide", "81 Mo"),
        ligne_cochable("planches_04_08.pdf", "vide", "312 Mo"),
        # La case porte le REFUS et non un vide : `notes_prestataire.txt` reste
        # visible et ne se coche pas -- `Explorateur._case` pose le glyphe
        # d'absence sur une entree non validable, exactement comme une cadence
        # refusee (`cadences.py:731`).
        ligne_cochable("notes_prestataire.txt", "refusee",
                       "\u00b7 pas une source"),
        points("1-6 sur 142"),
    ],
    valide=valider("planche_01.tiff", "78 Mo"),
    etat="142 fichiers \u00b7 138 images, 3 PDF, 1 ignor\u00e9",
    raccourcis=RACCOURCIS_SELECTION,
))


# --------------------------------------------------------------- X7 ---------

ecrire("X7-explorateur-cas-limites.txt", ecran(
    bandeau_gauche=BANDEAU_PROJET[0], bandeau_droite=BANDEAU_PROJET[1],
    titre="Ouvrir un projet",
    parent="Volumes   C:  D:  E:",
    libelle="Dossier", chemin="D:\\", focus_adresse=False,
    entrees=[
        ligne("HOKO/", "4 sous-dossiers", curseur=True),
        ligne("Temp/", "0 sous-dossier"),
        ligne("Sauvegardes/", "\u2715 illisible"),
    ],
    valide=valider("HOKO/"),
    etat="racine du volume D: \u00b7 3 dossiers cach\u00e9s",
    raccourcis=RACCOURCIS_CACHES,
))


# --------------------------------------------------------------- X8 ---------
# Demande d'Egan : « j'aurais aime voir le dossier inexistant a l'ecran ».
#
# **L'avertissement est NOMME et porte son glyphe** (Egan, 2026-09-04, note 8 :
# « Ca merite un avertissement "ce chemin n'existe pas" »). L'ecran le disait
# deja -- « aucun dossier n'existe a cette adresse » -- mais uniquement sur la
# ligne d'etat, sans glyphe, et cette zone-la est peinte en `muted` quoi qu'elle
# porte. Une phrase grise en bas d'ecran, sous une liste qui propose de creer le
# dossier, se lit comme une note de bas de page et non comme un refus.
#
# Deux corrections. La premiere porte : l'avertissement remonte DANS la zone de
# liste, avec son glyphe et son etat DECLARE, au-dessus des deux issues qu'il
# justifie. C'est la disposition de `E0-3`, ou « Ce dossier existe mais ne porte
# pas de project.json » precede les trois issues ; elle est reprise plutot que
# reinventee. La seconde est de forme : la ligne d'etat prend elle aussi le `✕`
# en tete, comme celle de `E0-3` et celle de `E6-1b`. Elle ne se peint pas pour
# autant -- le colorisateur teinte cette zone en `muted` quoi qu'elle porte --,
# et c'est precisement pourquoi la premiere correction etait necessaire.
#
# **Ce qui ne change pas : les deux issues restent.** Un chemin inexistant
# n'est pas un blocage sec (`EPIC11-ARB-89`) -- on peut le creer, ou revenir.
# L'avertissement rend le geste conscient, il ne l'interdit pas.

ecrire("X8-explorateur-chemin-inexistant.txt", ecran(
    bandeau_gauche=BANDEAU_PROJET[0], bandeau_droite=BANDEAU_PROJET[1],
    titre="Ouvrir un projet",
    parent="\u2026\\mmu\\",
    libelle="Dossier",
    chemin="D:\\HOKO\\Documents\\mmu\\projest\u2588", focus_adresse=True,
    entrees=[
        ligne("\u2715  ce chemin n'existe pas"),
        "",
        ligne("\u23ce  le cr\u00e9er ici, avec son arborescence de projet"),
        ligne("\u2190  revenir \u00e0 mmu"),
    ],
    valide=valider("projest", "\u00b7 \u00e0 cr\u00e9er"),
    etat="\u2715  ce chemin n'existe pas \u2014 aucun dossier \u00e0 cette adresse",
    raccourcis=RACCOURCIS_ADRESSE,
),
# **L'etat est DECLARE, sinon la croix reste grise.** Le colorisateur peint la
# ligne d'ETAT en `muted` quoi qu'elle porte -- c'est sa zone, pas la zone
# centrale --, et dans la liste le `\u2715` est suivi de DEUX blancs pour aligner
# son texte sur celui des etiquettes `\u23ce` et `\u2190`, si bien que le repli par
# motif (`jetons.jeton_d_etat`, qui exige un seul blanc) ne le voit pas. C'est
# exactement le cas qu'`EPIC11-ARB-71` ferme en DONNANT l'etat.
    hauteurs_de_message={"ce chemin n'existe pas": 1},
)

PHRASE_SUPPR = ("Suppr retire de la liste \u2014 le dossier du projet "
                "n'est pas touche")

print("8 maquettes ecrites dans maquettes/")


# ---------------------------------------------------------------------------
# X9 -- la liste des projets recents, avec ses CINQ compteurs.
#
# `QE10`, tranchee `b` par Egan : les compteurs entrent dans cette story, pas
# dans une story ulterieure. Motif de la question : la liste comptait les
# rushes et les lots, et oubliait les planches, les scans et les masters.
# Les initiales sont sa proposition -- « ou des initiales R, L, P, S, M ? ».
#
# Ce n'est PAS un ecran d'explorateur : c'est le premier ecran du palier 0, et
# l'explorateur est ce qu'on atteint depuis lui. Il est ici parce que la
# decision le met dans le meme lot, et parce qu'un compteur se juge a l'oeil.
# ---------------------------------------------------------------------------

def recent(nom: str, date: str, compteurs: str, curseur: bool = False) -> str:
    """Une ligne de recent : nom, date d'ouverture, et les cinq cardinaux.

    `·` la ou le manifeste n'a pas ete lu -- **jamais `0`**, qui serait un
    chiffre faux presente comme une mesure (regle deja tenue par le code).
    """
    return ligne(nom, f"{date}   {compteurs}", curseur=curseur)


from construire_maquette import maquette as _maquette  # noqa: E402

ecrire("X9-recents-cinq-compteurs.txt", _maquette(
    bandeau_gauche=BANDEAU_PROJET[0], bandeau_droite=BANDEAU_PROJET[1],
    centre=[
        "",
        "  Ouvrir un projet",
        "",
        recent("projet_demo", "26/08",
               "3R · 5L · 8P · 2S · 1M", curseur=True),
        recent("chendj_mat", "21/08",
               "1R · 2L · 4P · 1S · ·M"),
        recent("tests_calibration", "14/08",
               "0R · 0L · 0P · 0S · 0M"),
        "",
        regle(),
        "",
        "     Ouvrir un autre dossier…",
        "",
        "     " + PHRASE_SUPPR,
    ],
    etat="R rushes · L lots · P planches · S scans · M masters",
    # `↑↓ liste` sort : la ligne faisait 80 colonnes repliee en ASCII pour une
    # zone de 76, et c'est exactement ce que `ecran_projet.RACCOURCIS_RECENTS`
    # `↑↓ liste` RENDU (finding `R12`). Le jeton avait ete sacrifie faute de
    # place ; `EPIC11-ARB-122` a rendu six colonnes et le PRODUIT
    # (`ecran_projet.RACCOURCIS_RECENTS`) l'a repris. La maquette montrait donc
    # une ligne plus pauvre que l'ecran livre. Mesure : 70 / 75 pour 76.
    raccourcis="⏎ ouvrir  ↑↓ liste  Suppr retirer  "
               "Tab explorateur  F1 aide  Q quitter",
))

print("X9 ecrite")
