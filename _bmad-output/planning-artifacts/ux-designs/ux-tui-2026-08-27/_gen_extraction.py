# -*- coding: utf-8 -*-
"""Maquettes de l'ATELIER EXTRACTION -- version 2 (2026-08-29).

Les neuf ecrans `E2-*` vivaient dans `_gen_a.py:116-320`. Ils en sont **sortis**
(la section y est supprimee dans le meme commit) : deux generateurs qui ecrivent
les memes fichiers font deux sources de verite, et c'est le dernier lance qui
gagne en silence.

Ce qui change par rapport a la version de `_gen_a.py`, et pourquoi. Chaque point
est une decision numerotee, pas un gout :

* **`EPIC11-ARB-56` -- la ligne d'etat porte une MESURE.** Elle « ne porte aucune
  touche [...] aucun conseil d'usage [...] aucun motif de conception ». Quatre
  des neuf ecrans la violaient : `E2-1` (« pas besoin de sortir de l'ecran » --
  conseil), `E2-2` et `E2-2b` (« Previsualiser n'ecrit rien : c'est une lecture,
  pas une extraction » -- motif de conception), `E2-2c` (« **Echap** pour en
  ajouter » -- nom de touche, l'interdit explicite). Les neuf lignes d'etat sont
  reecrites en mesures, ou laissees vides ;

* **`EPIC11-ARB-61` -- la profondeur DISPARAIT de `E2-2c`**, champ et raccourci.
  Mesure : `mmu extract` a huit options et aucune de profondeur, et
  `EXTRACTION_OUTPUT_BIT_DEPTH = 16` est une constante dont le commentaire dit
  que « la valeur ne varie jamais ». Egan : « on n'affiche pas un reglage qu'on
  ne peut pas regler ». Elle reste **affichee comme donnee** au panneau chiffre
  de `E2-3` -- l'operateur doit savoir ce qui sera ecrit, il n'a rien a y
  decider ;

* **`EPIC11-ARB-45` -- les issues de `E2-3` : une par ligne, `▸`, sans radio.**
  La version precedente rendait `( ) Extraire  ( ) Modifier  ( ) Annuler` sur
  UNE ligne, avec des glyphes de radio. Le rendu reel de
  `panneau.ChoixExclusif.rendu()` (`src/mixed_media_utility/tui/panneau.py:217`)
  rend une ligne par issue, prefixee du curseur ou d'une espace. Le curseur part
  sur la premiere issue **qui n'ecrit pas** (`panneau.py:185`, `EPIC11-ARB-7`) ;
  le rang de l'issue principale, lui, ne bouge pas. La **liste cochable** des
  cadences (`E2-2`, `E2-2c`) garde ses `[x]` et son `Espace` : `ARB-45` ne porte
  que sur les ecrans a issue unique, et la frontiere doit rester visible ;

* **`EPIC11-ARB-32` + `-63` -- le relink est DANS la TUI**, et il lui manquait
  ses ecrans. Trois sont ajoutes : `E2-1b` (`r`, explorateur en dossiers seuls),
  `E2-1c` (`d`, explorateur en fichiers visibles) et `E2-1d` (le refus nomme).
  Ils reprennent la forme **deja validee** des maquettes `X1` a `X9`, importee
  de `_forme_explorateur` plutot que recopiee. `EPIC11-ARB-63` : `r` et `d`
  agissent dans la LISTE DES RUSHES ; des que l'explorateur a la main, les
  lettres redeviennent des sauts alphabetiques. La ligne de raccourcis nomme
  donc la zone qui a la main -- `Rushes` ou `Explorateur` ;

* **`EPIC11-ARB-62` -- le nom d'un lot a cadence fractionnaire.** Un lot a `25/3`
  s'appelle `rush-001_25s3`, le `s` tenant la place de la barre oblique que le
  motif `^[A-Za-z0-9_-]+$` du schema v2 interdit. Le second lot de la chaine
  d'ecrans est donc desormais `projet_demo_rush_01_25s3` (cadence source / 3) la
  ou il etait `_12p5` : la convention se voit sur cinq ecrans d'affilee, du
  choix des cadences au resultat. La cadence decimale `12,5 -> _12p5` reste
  visible en temps 1 et en temps 2, decochee : les deux conventions de nommage
  sont a l'ecran en meme temps.

Lancer :  python _gen_extraction.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _forme_explorateur import (  # noqa: E402
    ecran,
    ligne,
    points,
    valider,
)
from construire_maquette import barre, cartouche, ecrire, maquette, regle  # noqa: E402

BANDEAU = "mmu · projet_demo · Extraction"

# ---------------------------------------------------------------------------
# Les deux lignes de raccourcis qui NOMMENT LA ZONE QUI A LA MAIN
# (`EPIC11-ARB-63`).
#
# Egan a propose `alt+r` / `alt+d` pour lever la collision entre les raccourcis
# a lettre et le saut alphabetique de l'explorateur ; la mesure l'ecarte (dans
# un terminal, toute touche tapee dans la fenetre d'`ESCDELAY` arrive prefixee
# `alt+`, et `coque.CoqueTui.normaliser()` retire ce prefixe : un `alt+r`
# arriverait comme un `r` nu). La decision est donc une SEPARATION DE ZONES, et
# une separation de zones ne se voit que si l'ecran dit laquelle a la main.
#
# `← parent` sort de la ligne des deux ecrans d'explorateur, faute de place :
# c'est le seul item que l'ecran redit deja mot pour mot, en etiquette vive et
# avec sa cible (`←  …\rushes_2026\`). `Tab chemin`, lui, n'est ecrit nulle part
# ailleurs -- le retirer rendrait la barre d'adresse indecouvrable.
# ---------------------------------------------------------------------------

# **`Tab` ajoute un rush** (retour d'Egan du 2026-08-29, note
# `q-champ-ajouter-un-rush`) : « si on veut ajouter un rushe d'une touche la
# logique du reste de la TUI est de mettre la touche tab ». Elle est ANNONCEE
# ICI, pas seulement sur l'entree de liste.
#
# `r retrouver` et `d désigner` sortent de la ligne : a 76 colonnes, `Tab` ne
# rentrait pas autrement (90 colonnes demandees). Le sacrifice suit la regle
# deja appliquee a `← parent` sur `E2-1b` -- on retire ce que l'ECRAN redit
# mot pour mot, et l'ecran porte les deux etiquettes vives `r` et `d` avec leur
# touche et leur cible. Reserve a lever : ces etiquettes ne sont la que quand un
# rush est absent.
RACCOURCIS_RUSHES = ("Rushes  Tab ajouter un rush  ⏎ choisir  "
                     "↑↓ naviguer  Échap ateliers")
# **La ligne que le CODE rend, mesuree**, et non celle qu'on souhaiterait :
# `ecran_projet.raccourcis_de_l_explorateur` donne
# `⏎ valider   → entrer   ← parent   Ctrl+H cachés   Échap sortir`, soit 67
# colonnes une fois repliee en ASCII. La version precedente en faisait 78 pour
# une zone de 76 -- elle promettait `↑↓ liste` et `Tab chemin`, que la constante
# a deja sacrifies faute de place. Une maquette qui montre une ligne que le
# terminal plancher ne rend pas est une maquette fausse.
RACCOURCIS_EXPLORATEUR = ("Explorateur  ⏎ valider  → entrer  ← parent  "
                          "Échap rushes")


# --------------------------------------------------------------- E2-1 -------
# **`Ajouter un rush` cesse d'etre bleu** (retour d'Egan : « il ne devrait pas
# etre bleu si le selecteur n'est pas dessus »). Mesure du 2026-08-29 : la ligne
# portait `>` , et `jetons.peindre` traite le glyphe d'invite comme le curseur
# (`jetons.py:654`, `_porte_l_invite`) -- elle sortait donc en `accent` gras,
# c'est-a-dire comme un second curseur. Le defaut etait DANS LA MAQUETTE : elle
# posait une marque de focus sur un champ qui n'a pas le focus. Le `>` est
# retire, et `Ajouter un rush` devient la derniere entree de la liste des
# rushes -- selectionnable au curseur (« l'explorateur s'ouvre ? C'est la bonne
# logique ») et joignable d'une touche par `Tab`.
#
# La ligne d'etat portait « Un rush absent se rebranche depuis ici -- pas besoin
# de sortir de l'ecran. » : un CONSEIL D'USAGE, interdit par `EPIC11-ARB-56`.
# Elle porte maintenant le cardinal des rushes declares et celui des introuvables
# -- la mesure exacte que l'ecran vient de faire par `relink.statut_de_liaison`.

ecrire("E2-1-extraction-rush.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite="",
    centre=[
        "",
        "  Quel rush extraire ?",
        "",
        # **Ces quatre lignes sont mesurees par le CODE, pas seulement par
        # l'oeil.** `test_rushes.py::test_les_lignes_rendues_sont_celles_de_la_
        # MAQUETTE_au_CARACTERE_PRES` confronte les colonnes du module de rushes
        # a CETTE maquette, et `test_atelier_extraction_rushes.py::test_la_
        # phrase_d_AJOUT_suit_la_colonne_technique_D_UNE_colonne` mesure le
        # decalage d'une colonne de la derniere. Le calage ci-dessous est donc
        # celui du code livre, releve sur lui, et il ne se retouche pas a l'oeil.
        #
        # Il a diverge une fois, et le 2026-08-30 la divergence s'est payee : le
        # `.txt` versionne portait le bon calage (celui du code), le generateur
        # l'ancien, et une regeneration de routine a REGRESSE la maquette et
        # casse les deux bancs. La correction est ici, a la source, dans le sens
        # qui rend au generateur ce que la maquette savait deja.
        "     rush_01              25 fps · 1920×1080 · 4:12         ● lié",
        "     rush_02              25 fps · 1920×1080 · 12:38        ● lié",
        "   ▸ rush_hiver           24 fps · 4096×2160 · 2:05         ✕ absent",
        "     Ajouter un rush       choisir un fichier vidéo dans l'explorateur",
        "",
        regle("rush_hiver — déclaré au manifest, introuvable"),
        "",
        "     r   Retrouver le fichier      chercher dans un dossier, par nom,",
        "                                   durée et timecode de départ",
        "     d   Le désigner à la main     choisir le fichier, sans recherche",
    ],
    etat="3 rushes déclarés · 2 liés, 1 introuvable",
    raccourcis=RACCOURCIS_RUSHES,
))


# --------------------------------------------------------------- E2-1b ------
# NEUF. `r` -- l'explorateur de la story 11.2b, variante DOSSIERS SEULS
# (`montrer_fichiers=False`) : on designe un dossier, `relink.rechercher_candidat`
# le parcourt recursivement. Forme reprise telle quelle des maquettes `X1`-`X9`.
#
# La ligne d'etat porte DEUX mesures et rien d'autre : le cardinal du dossier
# courant (ce que `explorateur.etat()` rend deja) et la reference d'identite du
# rush cherche -- les trois criteres que `relink` confronte a chaque candidat.

ecrire("E2-1b-relink-chercher-dossier.txt", ecran(
    bandeau_gauche=BANDEAU,
    bandeau_droite="rush_hiver · retrouver",
    titre="Où chercher rush_hiver ?",
    parent="…\\Documents\\",
    libelle="Dossier", chemin="D:\\HOKO\\Documents\\rushes_2026",
    focus_adresse=False,
    entrees=[
        ligne("01_reperages/", "4 sous-dossiers"),
        ligne("02_tournage_avril/", "17 sous-dossiers"),
        ligne("03_tournage_mai/", "12 sous-dossiers", curseur=True),
        ligne("04_tournage_juin/", "9 sous-dossiers"),
        ligne("05_plateau_studio/", "2 sous-dossiers"),
        ligne("06_drone/", "0 sous-dossier"),
        ligne("07_interviews/", "23 sous-dossiers"),
        points("1-7 sur 27"),
    ],
    valide=valider("03_tournage_mai/", "parcouru récursivement"),
    etat="27 sous-dossiers · rush_hiver : 3 012 frames · TC 00:00:00:00",
    raccourcis=RACCOURCIS_EXPLORATEUR,
))


# --------------------------------------------------------------- E2-1c ------
# NEUF. `d` -- le meme explorateur, variante FICHIERS VISIBLES
# (`montrer_fichiers=True`, `accepte=` sur les extensions video). C'est le
# chemin de `relink.verifier_designation_manuelle` : aucune recherche, un
# fichier designe, les trois criteres verifies sur lui seul.
#
# `· pas une source` reprend le rendu de `X6` pour un fichier non accepte :
# l'entree est VISIBLE mais non validable. Ne pas la montrer ferait croire que
# le dossier est vide.

ecrire("E2-1c-relink-designer-fichier.txt", ecran(
    bandeau_gauche=BANDEAU,
    bandeau_droite="rush_hiver · désigner",
    titre="Quel fichier est rush_hiver ?",
    parent="…\\03_tournage_mai\\",
    libelle="Fichier",
    chemin="D:\\HOKO\\Documents\\rushes_2026\\03_tournage_mai\\hd",
    focus_adresse=False,
    entrees=[
        # **`3 fichiers` et non `2 sous-dossiers`** (`EPIC11-ARB-121`, finding
        # `R11` de la revue du 2026-08-31). Ce site monte l'explorateur avec
        # `montrer_fichiers=True` -- il cherche un FICHIER de rush --, et la
        # colonne d'un dossier compte donc ce que le site cherche. La maquette
        # etait restee sur l'ancienne unite : le produit livre divergeait d'une
        # maquette approuvee, et rien ne rougissait.
        ligne("proxy/", "3 fichiers"),
        ligne("rush_hiver.mov", "12,4 Go"),
        ligne("rush_hiver_v2.mov", "12,4 Go", curseur=True),
        ligne("rush_printemps.mov", "8,1 Go"),
        ligne("derushage.csv", "· pas une source"),
        points("1-5 sur 34"),
    ],
    valide=valider("rush_hiver_v2.mov", "12,4 Go"),
    etat="34 fichiers · 31 vidéos, 3 ignorés",
    raccourcis=RACCOURCIS_EXPLORATEUR,
))


# --------------------------------------------------------------- E2-1d ------
# NEUF. Le refus, rendu PAR SON CODE (`relink.py:131-149` en porte quinze).
# Forme du refus nomme deja validee sur `T5-1` : cartouche `Refus`, le code sur
# sa propre ligne derriere `✕`, puis ce que la mesure a trouve, puis les issues.
#
# Les issues sont un `ChoixExclusif` : une par ligne, `▸` sur celle du curseur,
# aucun glyphe de radio (`EPIC11-ARB-45`). Aucune n'ecrit -- un refus de relink
# ne laisse rien derriere lui, et c'est ce que dit la derniere ligne du
# cartouche.

ecrire("E2-1d-relink-refus-nomme.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite="rush_hiver · retrouver",
    centre=[
        "",
        "  La recherche s'est arrêtée",
        "",
        *cartouche("Refus", [
            "✕ candidats-multiples",
            "",
            "3 fichiers de 03_tournage_mai/ vérifient les trois critères",
            "d'identité de rush_hiver : nom de base, 3 012 frames, timecode.",
            "",
            "   hd\\rush_hiver.mov                       12,4 Go",
            "   hd\\rush_hiver_v2.mov                    12,4 Go",
            "   proxy\\rush_hiver.mov                     1,1 Go",
        ]),
        "",
        "   ▸ Le désigner à la main         choisir lequel des trois",
        "     Chercher dans un autre dossier",
        "     Revenir à la liste des rushes",
    ],
    etat="✕  candidats-multiples · 3 candidats · le manifest est inchangé",
    raccourcis="⏎ choisir  ↑↓ naviguer  Échap rushes  F1 aide",
))


# --------------------------------------------------------------- E2-1e -----
# NEUF (2026-09-01, `EPIC11-ARB-144`). **L'ecran qui manquait entre `E2-1` et
# `X6`.** Depuis la liste des rushes, `Tab` ouvre l'explorateur en mode
# « designer un fichier video » ; l'operateur valide un fichier -- et jusqu'ici
# il ne se passait RIEN, alors qu'`EPIC11-ARB-4` rend un panneau chiffre
# « obligatoire pour toute commande qui ecrit ». C'est cet ecran.
#
# **REDESSINE le 2026-09-01 sur la relecture d'Egan** (treize notes,
# `decisions-2026-09-01-relecture-declaration-de-rush.md`). Cinq notes portent
# sur cet ecran, et chacune retire ou remplace quelque chose :
#
# | note | arbitrage | ce qui change ICI |
# |---|---|---|
# | 2 | `EPIC11-ARB-153` | l'ecran montre `source_name`, pas le `rush_id` |
# | 3, 11 | `EPIC11-ARB-141` | plus aucune edition de nom, ni champ ni raccourci |
# | 4 | -- | le cadre « Ecrit / Non ecrit » est RETIRE (« On enleve ») |
# | 5 | `EPIC11-ARB-151` | le chemin source est COMPLET, sur deux lignes |
# | 6 | `EPIC11-ARB-150` | l'espace couleur tient sur UNE ligne |
#
# **REPRIS le 2026-09-01 sur la relecture v2** (huit notes,
# `retours-egan-2026-09-01-planche-rush-v2.md`). Une seule porte sur cet
# ecran-ci, la **note 6**, et elle AMENDE `EPIC11-ARB-151` plutot qu'elle ne le
# renverse. Verbatim : « 2 lignes puis on coupe au milieu en gardant les 3
# premiers dossiers de l'arborescence et les deux derniers au moins. »
#
# `ARB-151` disait « le chemin complet, quitte a utiliser plusieurs lignes » ;
# il ne disait pas ce qui arrive quand plusieurs lignes ne suffisent pas. La
# note 6 le dit : **deux lignes, puis une coupe au milieu**. Les deux cas se
# dessinent, parce qu'un seul ne montrerait pas la regle :
#
# * **il tient** -- `E2-1e`, ci-dessous : 70 colonnes pour 86 disponibles ;
# * **il ne tient pas** -- `E2-1h`, juste apres : 115 colonnes, coupe au milieu.
#
# **Ce que le panneau porte reste MESURE par le lot A du coeur**
# (`declaration_de_rush.qualifier_pour_declaration`), et rien de plus :
#
# | ligne du panneau     | ce qui la rend                                   |
# |---|---|
# | `Nom du fichier`     | `rushes[].source_name` (accents et espaces)       |
# | `Chemin complet`     | `rushes[].source_path` (`extraction.py:1205`)     |
# | `Codec`, `pixels`    | `source_confirmation` -- criteres d'identite      |
# | `Cadence source`     | `qualification.fps_source` + `fps_source_exact`   |
# | `Resolution`         | `source_confirmation.resolution_du_flux`          |
# | `Timecode de depart` | `qualification.start_timecode`                    |
# | `Espace couleur`     | le triplet, rendu en UNE valeur (`ARB-150`)       |
#
# **`EPIC11-ARB-153` -- le vrai nom, et NON l'identifiant derive.** Note 2
# d'Egan : « garder le nom exact du rush, c'est faisable ? » La mesure a rendu
# un defaut : `tui/atelier_extraction.py` ne lit que `rush_id`, si bien que
# l'ecran montrait `plan-sequence-12` la ou le manifeste garde
# `plan sequence 12.mov`. L'ecran affiche desormais le nom reel, et le bandeau
# aussi.
#
# **Et l'identifiant derive n'apparait PLUS NULLE PART sur cet ecran.** Ce
# n'est pas un oubli, c'est la conjonction de trois arbitrages, aucun ne
# contredisant les autres :
#
# * `EPIC11-ARB-153`, verbatim : le `rush_id` « ne sert qu'aux chemins, aux
#   noms de frames et au payload QR -- **jamais a l'affichage** » ;
# * `EPIC11-ARB-141` retire l'edition de nom : le `rush_id` n'est donc plus
#   corrigible par l'operateur a cet endroit ;
# * `EPIC11-ARB-150`, verbatim : « si cela peut etre source d'erreur on ne doit
#   pas afficher ce qu'on ne peut pas corriger ». Un identifiant translittere
#   pose a cote du vrai nom EST une source d'erreur -- c'est exactement la
#   confusion que la note 2 signale.
#
# La deduction est ecrite ici pour qu'elle se voie et se renverse d'une ligne
# si Egan la refuse : rien d'autre que ces trois arbitrages ne la porte.
#
# **`EPIC11-ARB-151` -- le chemin est COMPLET, sur deux lignes.** Verbatim :
# « sur cet ecran garder le chemin complet quitte a utiliser plusieurs lignes ?
# C'est important. » L'abregement au milieu par `jetons.abreger_chemin` est la
# regle du depot pour un chemin qu'on LIT (`DESIGN.md` section 9) ; il ne vaut
# pas ici, et la reserve portee a la planche du 2026-09-01 disait pourquoi :
# a 43 colonnes de valeur, l'abregement mangeait `03_tournage_mai`, c'est-a-dire
# le seul segment qui distingue deux journees de tournage. Le chemin se replie
# donc sur la ligne suivante, a la colonne de valeur.
#
# **`EPIC11-ARB-150` -- une ligne d'espace couleur, pas trois.** Verbatim :
# « on peut mettre "espace couleur - bt 709" plutot que de le remettre 3 fois
# meme s'il y a 3 parametres distincts derriere ». Les trois parametres
# existent bel et bien (`COLOR_TRIPLET_REPORT_KEYS` :  `color_primaries`,
# `color_transfer`, `color_space`) et le manifeste les garde separement ; ce
# qui tombe est leur AFFICHAGE separe. L'ancienne ligne
# `● complete — bt709 · bt709 · bt709 · tv` montrait quatre valeurs qu'aucune
# issue de cet ecran ne permet de corriger.
#
# **Note 4 -- le cadre « Ecrit / Non ecrit » est RETIRE.** Verbatim : « On
# enleve ». Le commentaire de la version precedente en faisait « le coeur de
# cet ecran » ; Egan tranche l'inverse. Ce que ces deux lignes portaient n'est
# pas perdu pour autant : la ligne d'etat dit deja « rien n'a encore ete
# ecrit », et c'est la seule moitie qui renseigne -- la moitie « Ecrit : 1
# entree rushes[] » enoncait la structure du manifeste, que l'operateur n'a pas
# a connaitre.
#
# **Les trois issues sont un `ChoixExclusif`** : une par ligne, `▸` sur le
# curseur, aucun glyphe de radio (`EPIC11-ARB-126`, verbatim : « Fleche seule !
# C'est uniquement dans les listes a cocher qu'on trouve les deux »). Le
# curseur part sur `Designer un autre fichier` -- la premiere issue qui
# N'ECRIT PAS (`panneau.py:185`) --, et le rang de l'issue principale ne bouge
# pas : c'est exactement la forme de `E2-3`.
#
# **`Tab editer le nom` DISPARAIT de la ligne de raccourcis** (notes 3 et 11,
# `EPIC11-ARB-141`). La version precedente le gardait en argumentant que le
# critere de `ARB-141` est le CABLAGE et qu'il etait tenu ici. Egan tranche
# autrement, et sur les deux ecrans : pas d'edition de nom de source. Ce qu'il
# veut vraiment est ecrit dans la relecture -- « moi j'aimerais pouvoir
# renommer les ecritures » --, et cela porte sur les SORTIES, pas sur les
# sources ; c'est une dette, pas cet ecran.

#: Le chemin source, **entier**, replie a la colonne de valeur du panneau
#: (`EPIC11-ARB-151`). Il est ecrit une fois et sert aux deux etats de la
#: colorimetrie : deux copies divergeraient au premier ajustement, et c'est la
#: classe de defaut que `CLAUDE.md` documente pour les valeurs recopiees.
#:
#: **Le cas « il tient » de la note 6** (relecture v2, 2026-09-01) : 70 colonnes
#: pour 86 disponibles (deux lignes de 43 a la colonne de valeur), donc aucune
#: coupe. Le cas « il ne tient pas » est dessine a part, sur `E2-1h`.
CHEMIN_DECLARE = ("D:\\HOKO\\Documents\\rushes\\2026\\",
                  "03_tournage_mai\\hd\\plan séquence 12.mov")

#: **Le cas COUPE de la note 6**, et il est mesure plutot que suppose.
#:
#: Verbatim d'Egan : « 2 lignes puis on coupe au milieu en gardant les 3
#: premiers dossiers de l'arborescence et les deux derniers au moins ».
#:
#: Le chemin entier de `E2-1h` fait **115 colonnes** :
#: `D:\HOKO\Documents\clients\arte\documentaire-chendj\tournage\`
#: `03_tournage_mai\camera_A\hd\prores\plan séquence 12.mov`. La colonne de
#: valeur en offre **43 par ligne, soit 86** : il faut donc en retirer 29 au
#: moins. La regle rend :
#:
#: * **tete** -- les trois premiers dossiers, `D:\HOKO\Documents\` (18 colonnes) ;
#: * **coupe** -- `…\`, qui remplace `clients\arte\documentaire-chendj\tournage\`
#:   (42 colonnes retirees) ;
#: * **queue** -- QUATRE segments et non deux : la regle dit « les deux derniers
#:   **au moins** », donc on remplit la queue tant que la coupe tient sur deux
#:   lignes brisees a un separateur. Ici `03_tournage_mai\camera_A\hd\prores\`
#:   plus le nom de fichier, 55 colonnes.
#:
#: **Et c'est la queue qui porte le renseignement.** `jetons.abreger_chemin`,
#: la regle du depot pour un chemin qu'on LIT, rend a 43 colonnes
#: `D:\HOKO\Documents\rushe…plan séquence 12.mov` : elle mange
#: `03_tournage_mai`, c'est-a-dire le seul segment qui distingue deux journees
#: de tournage. La regle de la note 6 existe pour ca, et elle n'est donc PAS un
#: reglage d'`abreger_chemin` -- c'est une autre regle.
CHEMIN_DECLARE_COUPE = ("D:\\HOKO\\Documents\\…\\03_tournage_mai\\",
                        "camera_A\\hd\\prores\\plan séquence 12.mov")

#: La colonne de valeur des panneaux de declaration : 25 colonnes d'etiquette.
#: Une continuation de chemin s'y aligne sans que personne ne compte a la main.
RETRAIT_DE_VALEUR = " " * 25


#: La ligne `Résolution` NOMINALE : le cardinal de frames y est CORROBORE.
#:
#: **Elle est une constante et non un litteral recopie** pour la meme raison
#: que `CHEMIN_DECLARE` : le quatrieme etat de l'ecran (`E2-1i`) ne s'en
#: distingue que par le retrait du cardinal, et deux litteraux recopies
#: divergeraient au premier ajustement -- la classe de defaut que `CLAUDE.md`
#: documente pour les valeurs recopiees.
RESOLUTION_CORROBOREE = "Résolution               1920 × 1080 · 6 300 frames · 4:12"

#: La meme ligne quand le moteur n'a PAS corrobore le cardinal
#: (`EPIC11-ARB-227`). Le compte disparait, **sans un mot a sa place** : ni
#: `0`, ni `--`, ni un libelle d'absence. C'est l'application stricte de la
#: regle d'omission que `DESIGN.md` tient depuis `EPIC7-ARB-67` -- « rien a la
#: place du temps -- jamais `0:00`, jamais `--:--` presente comme une duree ».
#:
#: **Le moteur produit deja cet etat, il n'est pas une hypothese de dessin** :
#: `declaration_de_rush._SourceQualifiee.cardinal_de_frames` vaut `None` quand
#: la duree du flux ne corrobore pas le cardinal annonce par le conteneur, et
#: `declarer_un_rush` ecrit alors `source_frame_count=None` --
#: `_build_rush_entry` OMET le champ plutot que d'ecrire une estimation qui
#: divergerait du comptage exact d'une extraction ulterieure.
#:
#: Ce qui RESTE sur la ligne est ce qui est mesure : la resolution du flux et
#: la duree. La duree ne disparait pas avec le cardinal -- c'est elle qui a
#: servi a tenter la corroboration, donc elle existe par construction.
RESOLUTION_SANS_CARDINAL = "Résolution               1920 × 1080 · 4:12"


def fiche_de_declaration(ligne_de_couleur: list[str],
                         chemin: tuple[str, str] = CHEMIN_DECLARE,
                         resolution: str = RESOLUTION_CORROBOREE) -> list[str]:
    """Le corps du panneau « A declarer », commun aux TROIS etats de l'ecran.

    Les deux etats d'`EPIC11-ARB-149` -- colorimetrie reconnue, colorimetrie
    inconnue -- ne different que par leur fin. Tout ce qui precede est identique
    par construction, et non par recopie : deux fiches recopiees divergeraient,
    et l'ecart ne se verrait pas a la relecture.

    `chemin` est le troisieme etat, ne de la note 6 : le chemin coupe de
    `E2-1h`. Il est un PARAMETRE plutot qu'une seconde fiche, pour la meme
    raison -- une fiche recopiee pour n'en changer que deux lignes divergerait
    du reste au premier ajustement.

    `resolution` est le QUATRIEME etat (`EPIC11-ARB-227`, `E2-1i`) : le
    cardinal de frames que le moteur n'a pas corrobore, donc omis. Meme motif
    de parametrage -- et il tient d'autant mieux ici que les deux lignes ne
    different que par onze caracteres au milieu.
    """
    return [
        f"Nom du fichier           plan séquence 12.mov",
        f"Chemin complet           {chemin[0]}",
        f"{RETRAIT_DE_VALEUR}{chemin[1]}",
        "Codec · format de pixel  prores_ks · yuv422p10le",
        "Cadence source           25 fps                        (exacte 25/1)",
        resolution,
        "Timecode de départ       00:00:04:12",
        *ligne_de_couleur,
    ]


#: Les trois issues, identiques aux deux etats. Le curseur est sur la premiere
#: qui n'ecrit pas (`panneau.py:185`, `EPIC11-ARB-7`).
ISSUES_DE_DECLARATION = [
    "     Déclarer le rush",
    "   ▸ Désigner un autre fichier",
    "     Annuler",
]

#: Le bandeau de droite porte desormais le VRAI NOM (`EPIC11-ARB-153`), la ou
#: il portait `plan-sequence-12`. Cadence et duree restent : le `ffprobe` a
#: deja tourne quand cet ecran monte -- et il tourne meme PLUS TOT qu'avant,
#: puisqu'`EPIC11-ARB-148` place desormais la decision d'identite apres lui.
BANDEAU_DE_DECLARATION = "plan séquence 12.mov · 25 fps · 4:12"

#: La ligne d'espace couleur d'une source SIGNALEE, ecrite UNE fois pour les
#: trois etats qui la portent (`E2-1e`, `E2-1h`, `E2-1i`).
#:
#: `EPIC11-ARB-150` : UNE ligne, la ou le triplet en faisait trois plus la
#: plage de valeurs. La valeur est celle qu'un `ffprobe` rend sur une source
#: signalee -- `bt709` pour les trois champs.
#:
#: **Elle valait `bt 709`, avec une espace, et `EPIC11-ARB-235` l'a corrigee
#: le 2026-09-05.** Deux choses se sont payees ensemble ici, et la seconde
#: explique la premiere : la valeur avait derive du commentaire ecrit trois
#: lignes au-dessus d'elle -- qui disait deja `bt709` --, et elle avait derive
#: aux TROIS endroits parce qu'elle y etait RECOPIEE. Une espace au milieu
#: d'une valeur de probe la rend incomparable a ce que l'operateur lit dans
#: `ffprobe` et a ce que le manifeste garde. La constante existe pour que la
#: prochaine correction n'ait qu'un seul endroit ou se poser -- meme motif que
#: `fiche_de_declaration`, parametree plutot que recopiee.
LIGNE_DE_COULEUR_SIGNALEE = "Espace couleur           bt709"

ecrire("E2-1e-declaration-confirmation.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite=BANDEAU_DE_DECLARATION,
    centre=[
        "",
        *cartouche("À déclarer", fiche_de_declaration([
            LIGNE_DE_COULEUR_SIGNALEE,
        ])),
        "",
        *ISSUES_DE_DECLARATION,
    ],
    etat="6 300 frames source · 4e rush du projet — rien n'a encore été écrit",
    # `Tab editer le nom` RETIRE (`EPIC11-ARB-141`, notes 3 et 11).
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
))


# --------------------------------------------------------------- E2-1h -----
# NEUVE (2026-09-01, relecture v2, **note 6**). **Le TROISIEME etat de `E2-1e`**
# -- pas un ecran de plus : meme fiche, memes issues, meme ligne de raccourcis.
# **Une seule chose y change, et c'est celle que la note demande** : le chemin
# source ne tient pas sur ses deux lignes, donc il est coupe.
#
# **Pourquoi les deux cas se dessinent et pas seulement le coupe.** Une regle de
# coupe ne se lit que contre son cas non coupe : sans `E2-1e` a cote, rien ne
# dit ou la coupe commence a mordre, et un lecteur ne peut pas verifier qu'elle
# ne mord pas trop tot. C'est le meme motif qui a fait dessiner `E2-1g` a cote
# de `E2-1e` pour la colorimetrie.
#
# **Ce que la note 6 ajoute a `EPIC11-ARB-151`, et ce qu'elle n'y touche pas.**
# `ARB-151` reste entier : le chemin est COMPLET tant qu'il tient, et il se
# replie plutot que de s'abreger. La note 6 ne dit que ce qui arrive **au-dela
# des deux lignes** -- l'abregement redevient alors necessaire, mais pas celui
# du depot : celui-la garde la tete et le dernier segment seuls, et il mange
# `03_tournage_mai`. La regle d'Egan garde la tete ET la queue. La mesure est
# ecrite au-dessus de `CHEMIN_DECLARE_COUPE`.
#
# **Ce que cette maquette ne mesure PAS, dit plutot que tu** : la coupe est
# dessinee, elle n'est **implementee nulle part**. Aucune fonction du depot ne
# la rend aujourd'hui -- `jetons.abreger_chemin` fait autre chose, et il n'y a
# pas de second abregeur. La regle appartient au lot de coeur / TUI a venir, et
# elle porte un nom qui n'existe pas encore : ne pas la confondre avec un
# comportement livre.
#
# **La ligne d'etat porte la MESURE de la coupe** (`EPIC11-ARB-56`) : le nombre
# de colonnes du chemin entier. C'est ce qui rend la coupe verifiable -- une
# ligne qui dirait seulement « chemin abrege » n'apprendrait rien.

ecrire("E2-1h-declaration-chemin-coupe.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite=BANDEAU_DE_DECLARATION,
    centre=[
        "",
        *cartouche("À déclarer", fiche_de_declaration(
            [LIGNE_DE_COULEUR_SIGNALEE],
            chemin=CHEMIN_DECLARE_COUPE,
        )),
        "",
        *ISSUES_DE_DECLARATION,
    ],
    etat="6 300 frames source · chemin de 115 colonnes, coupé au milieu",
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
))


# --------------------------------------------------------------- E2-1i -----
# NEUVE (2026-09-05, `EPIC11-ARB-227`). **Le QUATRIEME etat de `E2-1e`** -- pas
# un ecran de plus : meme fiche, memes issues, meme ligne de raccourcis, meme
# chemin. **Deux lignes y changent, et elles changent de la meme facon** : le
# cardinal de frames en sort, sans qu'un mot prenne sa place.
#
# **Ce qu'Egan tranche, verbatim, sur l'encart du cardinal absent de la v4 de
# la planche** : « **On n'affiche rien si on ne corrobore pas** ».
#
# Trois issues lui etaient posees -- disparition muette, absence nommee
# (`nombre d'images non corrobore`), ligne d'avertissement sous le cadre. Il
# prend la PREMIERE. La recommandation portee a la planche etait la deuxieme,
# au motif que « c'est le seul chiffre du panneau qui peut manquer, et un
# panneau qui se tait sur ce qu'il ignore se lit comme un panneau complet » :
# elle est ECARTEE, et ce commentaire la garde ecrite pour qu'on ne la
# repropose pas comme neuve.
#
# **Ce n'est donc PAS une exception a la regle d'omission, c'est son
# application stricte.** `DESIGN.md` la tient depuis `EPIC7-ARB-67` -- « rien a
# la place du temps -- jamais `0:00`, jamais `--:--` presente comme une
# duree ». Un libelle d'absence aurait ete une valeur de substitution de plus,
# textuelle au lieu de numerique ; la regle ne distingue pas les deux.
#
# **Le cas existe et il est MESURE dans le moteur, ce n'est pas une hypothese
# de dessin.** `declaration_de_rush._SourceQualifiee.cardinal_de_frames` vaut
# `None` quand la duree du flux ne corrobore pas le cardinal annonce par le
# conteneur ; `declarer_un_rush` ecrit alors `source_frame_count=None` et
# `source_frame_count_is_exact=None`, et `_build_rush_entry` OMET les deux
# champs -- « Omission stricte: jamais `null`, jamais une valeur par defaut »
# (`io/extraction_manifest.py`). L'ecran ne fait ici que refleter ce que le
# manifeste garde : rien.
#
# **LA LIGNE D'ETAT PERD LE CARDINAL ELLE AUSSI, et c'est une deduction, pas
# un arbitrage.** `EPIC11-ARB-227` porte nommement sur la ligne `Résolution`
# du panneau ; il ne dit rien de la ligne 22. Elle porte pourtant le meme
# chiffre -- `6 300 frames source · 4e rush du projet — rien n'a encore été
# écrit` --, et deux regles convergent pour l'en retirer :
#
# * **`EPIC11-ARB-56`** : la ligne d'etat porte une MESURE de l'ecran courant.
#   Un cardinal non corrobore n'est pas une mesure ; l'ecrire quand meme
#   ferait dire a la ligne d'etat ce que le panneau vient de se refuser a dire,
#   et les deux se contrediraient a trois lignes d'ecart ;
# * **`DESIGN.md` section 3** : « elle est **vide quand il n'y a rien a dire**
#   -- elle ne se remplit pas de bavardage pour occuper la place ». Le compte
#   sort donc sans remplacant, exactement comme sur la ligne `Résolution`.
#
# **Ce qui RESTE y est mesure, et c'est pourquoi la ligne ne devient pas
# vide** : `4e rush du projet` est un cardinal que le manifeste rend (les
# entrees de `rushes[]` deja ecrites, plus celle-ci), et `rien n'a encore été
# écrit` est l'etat du disque a cet instant -- la seule moitie du cadre
# « Ecrit / Non ecrit » retire par la note 4 qui renseignait encore.
#
# **Ce que cette maquette ne mesure PAS, dit plutot que tu** : aucun ecran
# livre ne rend cet etat aujourd'hui. `tui/ajout_de_rush.py` calcule ce que les
# ecrans `E2-1e` a `E2-1h` affichent ; la variante du cardinal absent est un
# DESSIN valide, pas un comportement livre, et le lot qui codera l'ecran devra
# porter sa propre frontiere -- une qui rougisse si un `0`, un `--` ou un
# libelle d'absence revenait a la place du compte.

ecrire("E2-1i-declaration-cardinal-absent.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite=BANDEAU_DE_DECLARATION,
    centre=[
        "",
        *cartouche("À déclarer", fiche_de_declaration(
            [LIGNE_DE_COULEUR_SIGNALEE],
            resolution=RESOLUTION_SANS_CARDINAL,
        )),
        "",
        *ISSUES_DE_DECLARATION,
    ],
    # Le cardinal sort de la ligne d'etat comme il sort du panneau. Voir la
    # deduction ci-dessus : `EPIC11-ARB-56` + `DESIGN.md` section 3.
    etat="4e rush du projet — rien n'a encore été écrit",
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
))


# --------------------------------------------------------------- E2-1g -----
# NEUVE (2026-09-01, `EPIC11-ARB-149`, notes 1 et 13). **Le SECOND etat de
# `E2-1e`**, et non un ecran de plus : meme fichier, meme fiche, meme jeu
# d'issues. Une seule ligne du panneau change, et elle est la raison d'etre de
# la maquette.
#
# **Ce qu'Egan tranche, verbatim** : « on force rec709 par defaut partout a ce
# niveau du projet. Pour le moment on ne traite pas de conversion
# colorimetrique en fonction de l'espace couleur reel. J'ai prevu les champs
# pour plus tard. Pour le moment on traite tout ce qui entre comme si c'etait
# du rec 709. [...] **L'outil a besoin de rec 709.** » Et, quand la
# colorimetrie n'est pas reconnue : « **il faut pouvoir corriger** ».
#
# **Le cas existe et il est mesure, ce n'est pas une hypothese de dessin.**
# `source_confirmation` distingue trois etats du triplet -- `complet`,
# `partiel`, `absent` (`COLOR_TRIPLET_STATUS_*`, `source_confirmation.py:125`)
# -- et n'escalade que sur le triplet, jamais sur `color_range` : « ProRes
# n'emet aucune signalisation de plage alors que DNxHR / H264 / HEVC emettent
# `tv` » (mesure de la story 6.3, recopiee ici de son commentaire). Le fichier
# dessine est justement un ProRes.
#
# **REPRISE du 2026-09-01 sur la relecture v2, NOTE 1 -- la liste TOMBE.**
# Verbatim d'Egan : « Pour le moment **pas de raccourci car pas de choix**. Et
# on **annonce** "le rushe sera traite comme Rec709 par defaut" a la place d'un
# choix unique. » Trois retraits et un ajout, et rien d'autre :
#
# * `Tab espace couleur` sort de la ligne de raccourcis -- elle redevient celle
#   de `E2-1e`, au caractere pres. `EPIC11-ARB-68` (« `Tab` nomme sa
#   DESTINATION ») n'a plus de destination a nommer ;
# * la **liste a une entree** (`À traiter comme  (•) Rec. 709`) sort, et sa
#   ligne blanche avec elle ;
# * ce que la version precedente defendait -- « la forme qui accueillera
#   `Rec. 2020` sans redessiner l'ecran » -- reste vrai et **ne suffit pas** :
#   une forme qui n'accueille rien aujourd'hui est un champ que l'operateur
#   peut ouvrir pour n'y rien trouver ;
# * une **assertion de traitement** prend la place, hors du panneau.
#
# **LA DISTINCTION QUE CE DESSIN TIENT, ET ELLE EST CONTRE-INTUITIVE.** Egan
# demandait « le coeur le fait-il ? Sinon, il faut ». Mesure :
# `source_confirmation._normalize_probe_value` (`:338-350`) ne force pas le
# rec709, **il l'interdit** -- verbatim de sa docstring : « Sentinelle ffprobe
# -> `None`, **sans jamais substituer de valeur** [...] Aucune valeur par defaut
# n'est jamais ecrite a la place (**`bt709` interdit, ni affiche ni transmis a
# 3.4**). » Ce n'est pas un oubli : le manifeste ne doit pas affirmer que la
# source **est** en bt709 quand `ffprobe` ne l'a pas dit.
#
# `EPIC11-ARB-149` et cette regle ne se contredisent que si l'on confond deux
# choses, et l'ecran les separe en deux endroits differents :
#
# | ou | ce qui s'y dit | ce que ca engage |
# |---|---|---|
# | **dans** le panneau « À déclarer » | `▲ non signalé — enregistré comme absent` | ce que le manifeste ECRIT |
# | **hors** du panneau, en assertion | `Le rush sera traité comme Rec. 709 par défaut` | ce que la chaine APPLIQUE |
#
# **C'est pour cela que l'assertion est HORS du cartouche.** Le cartouche
# s'appelle « À déclarer » : tout ce qu'il porte se lit comme destine au
# manifeste. Une ligne `À traiter comme  (•) Rec. 709` posee dedans disait donc,
# a la lettre, que `bt709` allait etre ecrit -- l'inverse exact de la regle
# mesuree ci-dessus. Le retrait de la liste ferme ce defaut par surcroit ; il
# n'etait pas dans la note d'Egan.
#
# **L'absence, elle, EST enregistree**, et positivement : le champ est omis et
# son nom entre dans `rushes[].source_metadata_absent_fields`
# (`io/extraction_manifest.py:853-861`, « Omission stricte: jamais `null`,
# jamais une valeur par defaut »). D'ou `enregistré comme absent` plutot que
# `rien n'est enregistré`, qui serait faux.
#
# **Ce que cette maquette ne dit PAS, dit plutot que tu** : l'assertion est un
# dessin, pas un comportement mesure. Aucun ecran livre ne porte cette phrase
# aujourd'hui, et **aucune frontiere ne mesure que la chaine traite bien la
# source comme du rec709** -- le depot n'a simplement pas de conversion
# colorimetrique, donc « traiter comme rec709 » y est un fait par defaut d'autre
# chose, jamais une regle ecrite quelque part. Le jour ou une conversion entre,
# cette phrase devient une promesse a tenir et il lui faudra sa mesure.

ecrire("E2-1g-declaration-colorimetrie-inconnue.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite=BANDEAU_DE_DECLARATION,
    centre=[
        "",
        *cartouche("À déclarer", fiche_de_declaration([
            # Ce que le MANIFESTE garde : l'absence, jamais une valeur.
            "Espace couleur           ▲ non signalé — enregistré comme absent",
        ])),
        "",
        # Ce que la CHAINE applique. Hors du cartouche « À déclarer », parce
        # qu'aucune ligne de cet ecran ne doit laisser croire que `bt709` est
        # ecrit quelque part.
        "  ▲ Le rush sera traité comme Rec. 709 par défaut · aucune valeur écrite.",
        "",
        *ISSUES_DE_DECLARATION,
    ],
    etat="6 300 frames source · espace couleur non signalé — aucune valeur écrite",
    # `Tab espace couleur` RETIRE (note 1) : plus de choix, donc plus de
    # raccourci. La ligne redevient exactement celle de `E2-1e`.
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
))


# --------------------------------------------------------------- E2-1f -----
# NEUF (2026-09-01, `EPIC11-ARB-144`). **Le refus « rush deja declare »**, et
# il est un ecran a part plutot qu'une ligne d'etat sur `E2-1e` : un refus se
# nomme, et il porte ses issues.
#
# **REDESSINE ENTIEREMENT le 2026-09-01. Cet ecran a CHANGE DE RAISON D'ETRE**
# sur les notes 8, 9 et 10 d'Egan, tranchees en `EPIC11-ARB-148` et `-152`.
#
# **Ce que la version precedente montrait, et pourquoi elle tombe.** Elle
# rendait DEUX LIGNES JUMELLES -- « deja declare » et « designe » -- avec la
# meme valeur des deux cotes, et disait au lecteur que « les deux lignes
# ci-dessous sont tout ce qui les separe ». Trois choses la condamnent :
#
# 1. **le critere a change.** `ARB-9` levait une homonymie par le NOM DU
#    DOSSIER PARENT SEUL (`extraction._source_parent_name:346`). Egan l'a mis
#    en echec sur le cas exact que la maquette dessinait -- deux journees de
#    tournage rangees a l'identique (`03_tournage_mai\hd\` et
#    `04_tournage_juin\hd\`) rendent le meme `source_parent`, `hd`. Le critere
#    est desormais **nom de fichier + caracteristiques techniques**, et **le
#    chemin ne compte pas** (`EPIC11-ARB-148`, verbatim d'Egan : « Un fichier
#    identique techniquement, nomme pareil, sur un autre chemin est considere
#    comme un rushe identique. ») ;
# 2. **il n'y a plus rien a comparer a l'oeil.** Le critere est DETERMINISTE :
#    la machine tranche seule, et les trois cas sont exhaustifs -- meme nom +
#    meme technique = meme rush (le seul qui monte cet ecran) ; meme nom + une
#    donnee technique differente = deux rushes, declares sans question ; nom
#    different = deux rushes. Un ecran qui demande a l'operateur de trancher ce
#    que la machine a deja tranche lui fait porter une decision qui n'existe
#    pas ;
# 3. **la phrase du cartouche etait FAUSSE**, et c'est la note 9 qui l'a
#    attrapee. Elle disait « le manifest ne garde ni chemin ni date ». Le
#    manifeste garde bel et bien le chemin absolu resolu
#    (`rushes[].source_path`, `extraction.py:1205`), et le contrat v2 l'exempte
#    NOMMEMENT de l'interdiction des chemins absolus
#    (`io/manifest.py:74`, `CHAMPS_EXEMPTES_CHEMIN_ABSOLU`). L'ecran montre
#    donc, en clair, d'ou le rush deja declare est declare -- c'est ce que
#    l'issue de relink remplacera.
#
# **DEUX issues, pas quatre** (`EPIC11-ARB-152`, verbatim : « on garde le
# premier choix pour relinker vers ce fichier. On garde annuler et c'est
# tout. »). Les deux autres tombent avec le critere qui les portait :
# `Le declarer distinct` proposait `plan-sequence-12-hd`, c'est-a-dire un
# suffixe tire du dossier que les deux fichiers ont EN COMMUN ; et
# `Lui donner un autre identifiant` est une edition de nom de source, retiree
# par `EPIC11-ARB-141`.
#
# **Le `ChoixExclusif` se construit toujours**, et pour la meme raison qu'avant
# : `panneau.ChoixExclusif.__post_init__` (`panneau.py:174-182`) LEVE quand
# TOUTES les issues ecrivent. Ici `Annuler` n'ecrit pas, donc l'invariant est
# tenu par les deux issues d'`ARB-152` telles quelles -- il n'y a plus d'issue
# a ajouter pour que l'ecran se construise. Le curseur s'y pose de lui-meme
# (`panneau.py:185-190`).
#
# **L'ecran peut desormais montrer la TECHNIQUE, et il le doit.** La version
# precedente s'en interdisait le droit : l'ordre des gardes placait
# l'homonymie AVANT le `ffprobe`, donc aucun chiffre n'existait a ce stade.
# `EPIC11-ARB-148` renverse cet ordre -- la decision d'identite a BESOIN des
# caracteristiques techniques, donc elle passe apres le probe (l'AC 1.8 de la
# 11.4e reste tenue : validations bon marche, puis `ffprobe`, puis decision,
# puis ecriture). Les quatre donnees affichees sont exactement celles sur
# lesquelles la machine a juge : les montrer, c'est rendre le verdict
# verifiable au lieu de le rendre opaque.
#
# **Le nom affiche est `source_name`** (`EPIC11-ARB-153`), ici comme sur
# `E2-1e` : `plan séquence 12.mov`, jamais `plan-sequence-12`.
#
# ===========================================================================
# **REPRIS le 2026-09-01 sur la relecture v2 : QUATRE des huit notes portent
# sur cet ecran** (`retours-egan-2026-09-01-planche-rush-v2.md`).
# ===========================================================================
#
# **Note 2 -- le message, et la PREUVE.** Verbatim : « un rushe identique existe
# deja », et il faut « montrer la preuve : le nom **et les infos techniques
# communes** ». Le titre du cartouche porte donc la phrase, et le panneau porte
# les criteres eux-memes. La version precedente affirmait l'identite sans
# montrer sur quoi elle etait jugee.
#
# **Note 5 -- les criteres sont QUATRE, et ils sont nommes.** Verbatim : « pas
# si leurs timecodes ne correspondent pas EXACTEMENT (duree, base, timecode
# initial) ». Avec le nom de fichier, cela fait quatre. Egan corrige au passage
# mon affirmation : deux prises differentes ne seront identiques que si **les
# trois timecodes coincident EXACTEMENT**, ce qui est tres rare -- l'ecran ne
# monte donc quasiment jamais, et c'est voulu.
#
# **Ce que l'ecran montre est EXACTEMENT ce sur quoi la machine a juge, ni plus
# ni moins.** Le codec, le format de pixel et la resolution SORTENT du panneau :
# ils y etaient au titre de « caracteristiques techniques » d'`EPIC11-ARB-148`,
# formule que la note 5 rend precise. Les laisser ferait croire qu'ils comptent
# dans le verdict -- c'est-a-dire exactement le defaut qu'`EPIC11-ARB-150`
# nomme : « si cela peut etre source d'erreur on ne doit pas afficher ce qu'on
# ne peut pas corriger. »
#
# **MESURE A CONNAITRE, et elle change le plan : DEUX des quatre criteres ne
# sont pas atteignables aujourd'hui.** Ce qu'une entree `rushes[]` ecrit
# (`io/extraction_manifest._build_rush_entry:816-874`) :
#
# | critere | stocke sur le RUSH ? | ou il vit aujourd'hui |
# |---|---|---|
# | nom du fichier | **OUI** | `rushes[].source_name` |
# | timecode initial | **OUI** | `rushes[].source_start_timecode` |
# | duree | **NON** | `lots[].source_frame_count` |
# | base de timecode | **NON** | `lots[].timecode_base_fps` |
#
# **Et le manque est structurel, pas un oubli d'ecriture** : les deux champs
# absents vivent sur le **lot**, or un rush declare et pas encore extrait n'a
# **aucun lot** -- c'est toute la raison d'etre de cette story. Les deux
# criteres sont donc inatteignables au moment meme ou la comparaison doit se
# faire. C'est un lot de coeur a venir (`rushes[]` gagne la duree et la base) ;
# **cette maquette dessine l'ecran CIBLE**, pas l'ecran d'aujourd'hui.
#
# **Ecart releve au passage** : le compte rendu de la relecture v2 situe la base
# de timecode dans `lots[].timecode_base`. Mesure : `timecode_base` est l'enum
# `source`/`target` (`encode.py:280`, verbatim : « l'enum `source`/`target` du
# manifest ») ; la **cadence** de la base est `lots[].timecode_base_fps`. Les
# deux vivent sur le lot, donc la conclusion ne bouge pas -- seul le nom du
# champ a corriger dans le lot de coeur.
#
# **Note 3 -- l'issue nomme le rush ET le chemin DESIGNE.** Verbatim : « Mettre
# **relinker [rushe] vers [chemin designe a l'etape precedente]**, comme ca
# c'est clair. » Le chemin de l'issue est donc celui que l'operateur vient de
# designer (`04_tournage_juin`), **jamais** celui du rush deja declare
# (`03_tournage_mai`) -- l'issue dit ou le rush ira, pas d'ou il vient.
#
# **Note 4 -- et cette formulation REGLE l'objection du chemin manquant.**
# Verbatim : le message de sortie « reintroduit le chemin designe ». Il n'y a
# donc **pas** de ligne `Désigné` dans le panneau : ce serait la jumelle de
# `Déclaré depuis`, c'est-a-dire exactement les deux lignes a comparer a l'oeil
# que la relecture v1 avait fait tomber. Le panneau dit **d'ou vient** le rush
# deja declare, l'issue dit **ou il ira** -- deux roles, deux endroits, aucune
# jumelle.
#
# **Le chemin de l'issue est coupe, et c'est MESURE.** Une issue de
# `ChoixExclusif` fait UNE ligne (`panneau.ChoixExclusif.rendu()`, une ligne par
# issue) : 71 colonnes utiles une fois l'indentation et le glyphe poses. Le
# libelle `Relinker plan séquence 12.mov vers ` en prend 35 ; il en reste **36**
# pour le chemin, quand le chemin designe entier en fait **70**. La regle de la
# note 6 (trois premiers dossiers plus les deux derniers segments) demande a
# elle seule 43 colonnes ici : **elle ne tient pas dans une issue.**
#
# Ce que l'issue porte donc, et le choix est explicite : le rush est **nomme une
# fois** (au debut), et le chemin designe est reduit a son **volume et a ses
# deux derniers dossiers** -- `D:\…\04_tournage_juin\hd\`. Le nom du fichier
# n'est pas repete en queue de chemin puisqu'il ouvre la phrase, et c'est ce qui
# libere la place pour `04_tournage_juin`, le seul segment qui distingue deux
# journees de tournage. `jetons.abreger_chemin`, mesure a 36 colonnes sur ce
# chemin, rend `D:\HOKO\Documen…plan séquence 12.mov` : il garde le nom -- deja
# ecrit -- et **mange `04_tournage_juin`**. Il ne convient pas ici.
#
# **Reserve a lever avec Egan** : si nommer le chemin designe en entier compte
# plus que la forme d'une issue, il faut soit une issue sur deux lignes -- que
# `ChoixExclusif` ne sait pas rendre --, soit une ligne de contexte sous le
# panneau. Le dessin ci-dessous fait le choix inverse ; il se renverse d'une
# ligne.
#
# **Note 7 -- le suffixe qui distingue deux homonymes est un CONDENSAT
# TECHNIQUE.** Verbatim d'Egan : « un hash derive des differences techniques ».
# Cela **confirme la recommandation d'`EPIC11-ARB-148`** -- « le condensat
# technique », contre le rang a deux chiffres et contre le dossier parent
# conserve --, et cela ferme la question qui y restait ouverte.
#
# **La forme, mesuree et non inventee** (`io/naming.py`) : le materiau technique
# est condense par `hashlib.sha256`, tronque a `BOUNDS_SUFFIX_LENGTH` (**8**
# caracteres hexadecimaux), exactement comme `bounds_suffix` le fait deja pour
# une fenetre d'extraction bornee. `derive_short_id` ne convient PAS : sa
# docstring le dit elle-meme, « ce n'est pas un hacheur mais un raccourcisseur
# conditionnel » -- elle rend son entree INCHANGEE sous
# `CANONICAL_ID_MAX_LENGTH`, donc elle ne produirait aucun suffixe ici.
#
# Le `rush_id` suffixe fait alors `plan-sequence-12` plus un tiret plus huit
# caracteres, soit **29 caracteres** pour une borne de `CANONICAL_ID_MAX_LENGTH`
# -- la constante, jamais sa valeur recopiee (`CLAUDE.md` : « un document de
# politique ne recopie jamais une valeur qui vit dans le code »). Il tient donc,
# et il tient aussi sous la falaise QR.
#
# **AUCUNE maquette `E2-1*` ne montre ce suffixe, et c'est voulu.**
# `EPIC11-ARB-153` interdit le `rush_id` a l'affichage : les ecrans montrent
# `source_name`. Le suffixe ne se voit donc que dans les chemins, les noms de
# frames et le payload QR. Cette note est enregistree ici pour que le lot de
# coeur la trouve, pas pour qu'un ecran la porte -- et la relecture peut le
# verifier d'un `grep` : aucun `plan-sequence-12` dans les maquettes `E2-1*`.
#
# **Le code de refus ne bouge pas.** `rush-deja-declare` reste, alors que le
# message devient « identique » : la note 2 porte sur le MESSAGE, et un code de
# refus est un identifiant enumere (`rushes.CODES_DE_REFUS`, tous en minuscules
# a tirets) que rien n'autorise a renommer depuis une maquette. Il n'existe
# d'ailleurs pas encore au coeur -- il naitra avec le lot qui livre la
# comparaison --, raison de plus pour ne pas en inventer deux formes.
#
# ===========================================================================
# **TROIS sorties depuis le 2026-09-05** (`EPIC11-ARB-231`, tranche par Egan).
# ===========================================================================
#
# **Ce qui rend la troisieme sortie NECESSAIRE, et ce n'est pas hypothetique.**
# `EPIC11-ARB-230` retire le dossier parent des criteres d'identite : quatre
# criteres coincident, c'est le meme rush, quel que soit le dossier. Le
# contre-exemple qui subsiste est **deux cameras jam-synchronisees**, cartes
# formatees pareil, `prise01.mov` sur les deux -- meme nom, meme duree, meme
# cadence, meme timecode initial, et pourtant deux angles differents.
# `ARB-230` seul en ferait un **faux conflit sans issue**, ce que
# `EPIC11-ARB-89` interdit nommement.
#
# L'ordre des trois PORTE la recommandation, et c'est pourquoi il est mesure
# plutot que relu (`tests/unit/tui/test_maquette_E2_1f_trois_sorties.py`) :
#
#     Relinker plan sequence 12.mov vers D:\…\04_tournage_juin\hd\
#     C'est un autre rush, le declarer separement
#     Annuler
#
# **Le curseur ne bouge pas, et ce n'est pas un oubli.** La sortie neuve
# ECRIT -- elle cree une seconde entree `rushes[]`. Des trois issues, seule
# `Annuler` n'ecrit pas : `panneau.ChoixExclusif` y pose donc le curseur de
# lui-meme (`EPIC11-ARB-7` sous la forme d'`EPIC11-ARB-45`), exactement comme
# a deux issues. L'invariant de `__post_init__` -- lever quand TOUTES les
# issues ecrivent -- reste tenu par la seule `Annuler`.
#
# **La ligne d'etat devient `3 issues, 2 ecrivent`, et c'est une MESURE, pas
# une reformulation.** `EPIC11-ARB-56` (DESIGN.md section 3) veut que cette
# ligne porte ce que l'ecran a compte ; un cardinal qui a cesse d'etre celui
# de l'ecran est pire qu'absent, il se lit comme une verification. Le second
# terme change de nombre AVEC le premier : `2 ecrivent` (relinker, declarer
# separement) contre `1 ecrit` a deux issues.
#
# **Ce que la place a coute, dit plutot que tu.** La zone centrale fait
# `HAUTEUR_CENTRE = 17` lignes et cet ecran les occupait DEJA toutes. Une
# ligne a donc ete prise, et le choix est explicite : c'est la ligne vide qui
# separait `✕ rush-deja-declare` de la phrase qui l'explique. Le code et la
# phrase disent la meme chose a deux grains -- ils font un bloc. Les deux
# autres lignes vides du cartouche ne sont PAS interchangeables avec
# celle-la :
#
# * celle qui precede `Nom du fichier` ouvre le bloc des quatre criteres ;
# * celle qui precede `Déclaré depuis` tient une separation de SENS, et
#   DESIGN.md section 7.4 la prescrit -- « separes du reste par une ligne
#   vide » pour un bloc d'une autre nature. La retirer ferait lire la
#   provenance comme un CINQUIEME critere, c'est-a-dire le defaut exact que
#   nomme `EPIC11-ARB-150` (« si cela peut etre source d'erreur on ne doit pas
#   afficher ce qu'on ne peut pas corriger »).
#
# La premiere ligne vide de la zone centrale n'a pas ete touchee non plus :
# **83 des 86 maquettes du dossier la portent**, c'est une convention de
# grille et non un blanc de confort.
#
# **Ecart assume, a ne pas decouvrir en revue** : `EPIC11-ARB-152` (« on garde
# annuler et c'est tout ») est **supersede sur ce point** par `ARB-231`, du
# choix explicite d'Egan. Le paragraphe « DEUX issues, pas quatre » ci-dessus
# est conserve pour son histoire ; il ne decrit plus l'ecran.
#
# **`Déclaré depuis` est coupe par la regle de la NOTE 6**, et pas par
# `abreger_chemin` : trois premiers dossiers, coupe, puis les deux derniers
# dossiers. Il tient ainsi sur UNE ligne (64 colonnes sur 68) la ou le chemin
# entier en demandait deux -- et `03_tournage_mai` survit, ce qui est le seul
# point qui compte sur un ecran ne d'une confusion entre deux journees.

ecrire("E2-1f-declaration-rush-deja-declare.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite="plan séquence 12.mov · refusé",
    centre=[
        "",
        *cartouche("Un rush identique existe déjà", [
            "✕ rush-deja-declare",
            "Les quatre critères d'identité coïncident avec ceux d'un rush",
            "déjà déclaré. Le chemin ne compte pas.",
            "",
            "Nom du fichier           plan séquence 12.mov",
            "Durée source             6 300 frames · 4:12",
            "Base de timecode         25 fps",
            "Timecode initial         00:00:04:12",
            "",
            "Déclaré depuis           D:\\HOKO\\Documents\\…\\03_tournage_mai\\hd\\",
        ]),
        "",
        "     Relinker plan séquence 12.mov vers D:\\…\\04_tournage_juin\\hd\\",
        "     C'est un autre rush, le déclarer séparément",
        "   ▸ Annuler",
    ],
    etat="✕  rush-deja-declare · 3 issues, 2 écrivent · le manifest est inchangé",
    raccourcis="⏎ choisir  ↑↓ naviguer  Échap rushes  F1 aide",
))


# --------------------------------------------------------------- E2-2 -------
# La ligne d'etat portait « Previsualiser n'ecrit rien : c'est une lecture, pas
# une extraction. » : un MOTIF DE CONCEPTION, interdit par `EPIC11-ARB-56`. Elle
# porte maintenant le cardinal des cochees et le total de frames qu'elles
# representent -- somme que la liste ne fait pas.
#
# `8,333 source / 3` est la cadence qui portera le nom `_25s3` au temps 2
# (`EPIC11-ARB-62`). Elle est cochee ici pour que la convention se voie plus
# loin.
#
# **Les trois questions d'Egan du 2026-08-29** (« Combien de cadences peut-on
# ajouter ? Comment cela s'affiche quand il y en a trop ? Comment on
# supprime ? ») sont repondues A L'ECRAN quand la reponse est une mesure :
#
# * **combien** : le coeur ne pose AUCUNE limite haute --
#   `cadence_previz._validated_targets` (`cadence_previz.py:1422-1442`) valide
#   valeur par valeur et n'en compte jamais le nombre ; il ne dedoublonne pas
#   davantage (deux fois 12,5 fait deux passes). La preparation, elle, est
#   PLATE : `prepare_previz` sonde la source une seule fois
#   (`cadence_previz.py:1489`), quel que soit le nombre de cadences. La vraie
#   limite est donc le TEMPS DE L'OPERATEUR -- chaque cadence est une passe
#   jouee en temps reel --, et c'est ce que la ligne d'etat porte desormais :
#   `15 s de lecture (3 passes de 4,9 s)`. Cinq cadences sur un rush de quatre
#   minutes, ce serait vingt minutes de visionnage ;
# * **quand il y en a trop** : la liste DEFILE, `…` compris, sur l'algorithme
#   de `explorateur.fenetre()` / `lignes_de_liste()` (`explorateur.py:468-849`)
#   avec `HAUTEUR_LISTE` a 5 au lieu de 9. Huit cadences, quatre visibles, une
#   ligne `…` qui porte la position -- c'est la forme deja validee sur `X1`-`X9`;
# * **supprimer** : `Espace` DECOCHE, et une cadence decochee n'est ni lue ni
#   extraite. Rien de plus n'existe au coeur : retirer une cadence ajoutee de
#   la liste elle-meme demanderait une touche qui n'est portee nulle part.

ecrire("E2-2-extraction-cadences.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite="temps 1 sur 2 · prévisualiser",
    centre=[
        "",
        "  Quelles cadences regarder ?",
        "",
        "   ▸ [x] 25        source            124 frames        (toutes)",
        "     [x] 12,5      source / 2         62 frames",
        "     [x] 8,333     source / 3         42 frames",
        "     [ ] 6,25      source / 4         31 frames",
        "     …                                             1-4 sur 8 cadences",
        "",
        "     3 cochées sur 8 · 228 frames",
        "",
        regle("Bornes"),
        "",
        "     Borne d'entrée       00:00:04:12",
        "     Borne de sortie      ·                                   (facultatif)",
    ],
    etat="3 cadences cochées · 228 frames sur 8 cadences proposées",
    # **`Espace cocher` et non `Espace cocher/décocher`** : la ligne complete
    # fait 75 colonnes en UTF-8 mais **80** une fois repliee en ASCII
    # (`⏎` -> `Entree`), pour une zone de 76. Mesure du 2026-08-29, trouvee par
    # une garde du CODE et non par ce generateur -- `verifier_maquettes.py` ne
    # mesurait que l'UTF-8. Il mesure le repli depuis. `E2-2c` ecrit deja
    # `Espace cocher` : les deux ecrans disent maintenant la meme chose.
    raccourcis="Espace cocher  A ajouter  ⏎ prévisualiser  X extraire sans voir",
))


# --------------------------------------------------------------- E2-2b ------
# La ligne d'etat portait « Rien n'est ecrit, ici comme dans la fenetre. » :
# meme motif de conception que `E2-2`, meme interdit. Elle porte maintenant les
# deux cardinaux que le rapport additionne colonne par colonne.
#
# **Trois corrections du 2026-08-29, toutes mesurees.**
#
# 1. **`p` et `r` sont ANNONCEES.** Elles existent deja dans le coeur --
#    `KEY_PREVIOUS = ord("p")` et `KEY_REPLAY = ord("r")`
#    (`cadence_previz.py:231-234`), consommees par la boucle de lecture
#    (`cadence_previz.py:1684-1690`) et testees
#    (`tests/unit/test_cadence_previz.py:823` et `:869`). La maquette les
#    taisait : elle sous-promettait ce qui marche.
# 2. **`L` boucle RESTE ; `Espace pause` et le pas-a-pas `← →` SORTENT.**
#    Deux arbitrages successifs, et le second defait le premier en
#    connaissance de cause :
#
#    * 2026-08-29 au soir, Egan : « J'aimais bien le image par image en pause
#      quand on est sur la previz. » Les trois touches entraient donc dans la
#      legende comme AJOUTS ASSUMES au coeur ;
#    * 2026-08-30, `Q11`, tranchee **option `b`**, Egan : « **on juge un
#      mouvement, pas des frames uniques** ». La previz existe pour juger une
#      cadence de LECTURE ; un pas-a-pas ne montre pas ce qu'on est venu voir.
#      La pause et le pas-a-pas quittent l'ecran ET cette planche.
#
#    Ce qui reste est ce qui aide a juger un mouvement :
#
#    * `n`, `p`, `r` existent depuis toujours et sont testees
#      (`cadence_previz.py:231-234`, `tests/unit/test_cadence_previz.py:823`
#      et `:869`) ;
#    * `L` (bascule de boucle, avec indicateur a l'image) est LIVREE par le lot
#      `K2` : c'est elle qui laisse repasser le mouvement autant qu'il faut,
#      donc elle sert exactement le motif de `Q11`.
#
#    **Le pas-a-pas etait aussi l'ajout le plus lourd, et c'est un argument de
#    plus, pas l'argument** : la lecture est cadencee sur des echeances
#    ABSOLUES depuis une origine (`origin + scheduled.t_theo_s - clock()`), et
#    une pause casse cette horloge. Il n'a jamais ete ecrit ; il n'y a donc
#    rien a retirer du coeur, seulement une promesse a ne plus afficher.
# 3. **La colonne « saccade » et sa phrase causale SORTENT** (Egan : « On
#    enleve la saccade, aucun interet »). Ce qui reste est ce que
#    `PlaybackReport` porte reellement : `frames_attendues` (retenues) et
#    `frames_presentees`.
# 4. **La colonne « temps réel » SORT a son tour** (lot `M`, 2026-08-30). Egan,
#    verbatim : « cette info n'est VRAIMENT pas interessante. Elle est deja en
#    couleur dans le panneau de previz lui-meme. J'aimerais retirer cette
#    notion de temps reel tenu ou pas des ecrans de la tui, TOUS les ecrans. »
#    Partent avec elle les trois verdicts (`● tenu`, `✕ non tenu`,
#    `▲ pause · non mesuré`) et le compte de passes non mesurees de la ligne
#    d'etat. **Le coeur garde sa mesure** : `PlaybackReport.temps_reel_tenu` et
#    `format_report_lines` sont intacts, et `mmu previz` continue de la
#    chiffrer.
# 5. **`o revoir` est ANNONCE** (lot `N1`, 2026-08-30). Egan a tape `o` sur cet
#    ecran-la et rien ne s'est produit : la touche n'etait cablee que sur
#    `E2-2c`. La destination d'`Échap` y est raccourcie parce que la ligne
#    complete fait 80 colonnes une fois repliee en ASCII, pour une zone de 76 :
#    on garde la promesse et on retire le mot de trop.

ecrire("E2-2b-extraction-previz.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite="temps 1 sur 2 · prévisualiser",
    centre=[
        "",
        "  Lecture comparée — une fenêtre s'est ouverte à côté du terminal",
        "",
        "     Dans la fenêtre :  L boucle · N suivante · P précédente · R relire",
        "                        Q fermer et revenir au terminal",
        "",
        regle("Rapport, au fil de la lecture"),
        "",
        "     cadence     retenues   présentées",
        "     25 fps           124          124",
        "     12,5 fps          62           62",
        "     8,333 fps         42           32",
    ],
    etat="3 cadences lues · 228 retenues, 218 présentées",
    raccourcis="⏎ choisir quoi extraire  O revoir  Échap les cadences  F1 aide",
))


# --------------------------------------------------------------- E2-2c ------
# Trois changements sur cet ecran, trois arbitrages :
#
# * `EPIC11-ARB-56` : la ligne d'etat portait « Seules les cadences
#   previsualisees sont ici. **Echap** pour en ajouter. » -- un NOM DE TOUCHE,
#   l'interdit explicite. Elle porte maintenant ce que les cochees pesent ;
# * `EPIC11-ARB-61` : le champ « Profondeur (•) 16 bits ( ) 8 bits » DISPARAIT,
#   et `Tab profondeur` avec lui. La place gagnee sert au troisieme lot ;
# * `EPIC11-ARB-62` : `projet_demo_rush_01_25s3` -- le `s` tient la place de la
#   barre oblique de `25/3`. La ligne dit les deux ecritures, le nom et la
#   cadence, parce que c'est leur rapprochement qui apprend la convention.
#
# **Deux corrections du 2026-08-29.** Egan, verbatim : « On s'en fiche d'avoir
# l'info saccade ou pas ici. Pas pertinent. Le nombre de frames est plus
# pertinent. » La colonne d'etat de lecture (`● fluide` / `▲ saccade`) sort
# donc, et le NOMBRE DE FRAMES passe en avant, juste apres la cadence. La
# phrase didactique sur la convention `s` sort aussi -- question posee, reponse
# d'Egan : « Non ».
#
# **Et la mention `vue · temps réel …` sort a son tour** (lot `M`,
# 2026-08-30) : c'est la meme notion que la colonne `temps réel` de `E2-2b`,
# retiree par le meme arbitrage. Ce qui restait de la colonne de droite --
# `vue` -- ne disait rien : `E2-2c` ne montre QUE des cadences vues, chaque
# ligne l'aurait porte. La colonne disparait donc entierement, et la ligne
# s'arrete au compte de frames.
#
# Le choix des cochees ne dit plus rien d'un ecart de lecture -- il n'y en a
# plus a l'ecran --, mais il reste **panache** (deux sur trois) : c'est ce qui
# montre que le temps 2 se re-choisit.

ecrire("E2-2c-extraction-choix.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite="temps 2 sur 2 · extraire",
    centre=[
        "",
        "  Lesquelles extraire ?",
        "",
        "   ▸ [x] 25 fps          124 frames",
        "     [ ] 12,5 fps         62 frames",
        "     [x] 8,333 fps        42 frames",
        "",
        "     2 cadences cochées → 2 lots",
        "",
        regle("Lots à produire"),
        "",
        "     projet_demo_rush_01_25fps                  124 frames · 25 fps",
        "     projet_demo_rush_01_25s3                    42 frames · 25/3 fps",
    ],
    etat="2 lots · 166 frames · ~ 2,8 Go (majorant)",
    raccourcis="Espace cocher  ⏎ continuer  O revoir  Échap retour  F1 aide",
))


# --------------------------------------------------------------- E2-3 -------
# Les ISSUES, refaites. La version precedente rendait
#
#     ( ) Extraire      ( ) Modifier les réglages      ( ) Annuler
#
# c'est-a-dire trois glyphes de radio sur une seule ligne. `EPIC11-ARB-45` :
# « il n'y a plus de case a cocher. Les glyphes de radio disparaissent du rendu
# de `ChoixExclusif` » -- le curseur EST la selection. Le rendu reel
# (`panneau.py:217-232`) est `f"{curseur ou espace} {libelle}"`, une ligne par
# issue ; c'est lui qui est recopie ici, a l'indentation pres.
#
# Le curseur est sur « Modifier les réglages » et non sur « Extraire » :
# `panneau.__post_init__` (`panneau.py:185`) le pose sur la premiere issue qui
# N'ECRIT PAS, sans reordonner la liste -- « aucune issue qui ecrit n'est
# atteignable par une seule frappe depuis le montage d'un ecran ».
#
# **Deux corrections du 2026-08-29.**
#
# 1. **La PROFONDEUR sort du panneau chiffre** (Egan : « On enleve la
#    profondeur »). Elle y avait ete gardee comme donnee alors qu'`ARB-61` la
#    retirait comme reglage ; l'arbitrage est desormais complet -- une valeur
#    qui ne varie jamais n'apprend rien.
# 2. **Le second curseur DISPARAIT** (Egan : « Il y a deux selecteurs sur cette
#    image »). Mesure : la ligne `Noms produits          > ...` portait le
#    glyphe d'invite, que `jetons.peindre` traite comme le curseur
#    (`jetons.py:654`) -- elle sortait en `accent` gras, en meme temps que
#    `▸ Modifier les réglages`. Le `>` est retire : hors edition, la zone des
#    noms n'a pas le focus. Il revient sur `E2-3b` et `E2-3c`, ou elle l'a.
#
# **Et la ligne de raccourcis dit ce qui MARCHE.** Egan demandait « on passe de
# la selection des choix a la selection des lots avec tab ? ». Mesure sur
# `tui/execution.py:206-234` : `traiter("tab")` rend `False` -- `Tab` ne fait
# RIEN sur cet ecran. Ce qui existe est `e`, qui pose un mode d'edition ou `↑↓`
# change de nom et `Echap` abandonne (`execution.py:226-256`). C'est `e` qui est
# annonce, et c'est deja ce que la ligne porte.

ecrire("E2-3-extraction-confirmation.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite="rush_01 · 25 fps · 4:12",
    centre=[
        "",
        *cartouche("À écrire", [
            "Lots créés               2",
            "Frames écrites           124  +  42        =  166",
            "Bornes                   00:00:04:12 → 00:00:09:08",
            "Espace disque            ~ 2,8 Go                     (majorant)",
            "Destination              projet_demo/frames/",
            "",
            # **La liste PLATE des noms, sans libelle de colonne**
            # (`EPIC11-ARB-141`). Ce n'est pas un choix de mise en page : c'est
            # ce que le produit REND. `Panneau.noms` pose les noms apres une
            # ligne vide, indentes de `INDENT_DES_NOMS`, et rien d'autre -- la
            # colonne « Noms produits » n'a jamais existe dans le code, et une
            # maquette qui la montre fait relire comme valide un rendu qui
            # n'existe pas. La forme est celle d'`E5-3`, livree et validee.
            "  projet_demo_rush_01_25fps",
            "  projet_demo_rush_01_25s3",
        ]),
        "",
        "     Extraire",
        "   ▸ Modifier les réglages",
        "     Annuler",
    ],
    etat="2 lots · 166 frames · ~ 2,8 Go — rien n'a encore été écrit",
    # **`Tab éditer les noms` est RETIRE** (`EPIC11-ARB-141`, story 11.4e lot
    # H). La touche n'a plus de destination : `run_extraction` n'a aucun
    # parametre de nom, le champ est parti, et annoncer une touche inerte est
    # le defaut que `coque.py` documente. La ligne est desormais celle du
    # produit, `atelier_extraction_ecriture.RACCOURCIS_EXTRACTION_CONFIRMATION`,
    # et un banc mesure qu'elles ne peuvent pas diverger.
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
))


# --------------------------------------------------------------- E2-3b ------
# Conforme sur le fond (`EPIC11-ARB-25`), ligne d'etat deja une mesure. Seuls
# le second nom et l'arithmetique suivent le lot `_25s3` d'`EPIC11-ARB-62` --
# `projet_demo_rush_01_25s3` et `projet_demo_rush_01_12p5` font 24 caracteres
# l'un comme l'autre, le compteur de l'ecran ne bouge donc pas.

ecrire("E2-3b-extraction-edition-nom.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite="rush_01 · 25 fps · 4:12",
    centre=[
        "",
        *cartouche("À écrire — édition des noms", [
            "Lots créés               2",
            "Frames écrites           124  +  42        =  166",
            "Espace disque            ~ 2,8 Go                    (majorant)",
            "",
            "Noms produits          > projet_demo_rush_01_25fps_hiver█   31/48",
            "                         projet_demo_rush_01_25s3           24/48",
        ]),
        "",
        "     Lettres, chiffres, tiret et souligné. Accents et espaces refusés.",
        "     Au-delà de 48 caractères le nom est refusé, jamais tronqué.",
        "",
        "     ↑↓ passer d'un nom à l'autre    ←→ déplacer le curseur",
        "     Ctrl+R remet le nom proposé — aucune LETTRE n'est un raccourci ici.",
    ],
    etat="31 caractères sur 48 — le nom reste valide",
    raccourcis="⏎ valider  ↑↓ nom suivant  Tab les choix  Échap annuler l'édition",
))


# --------------------------------------------------------------- E2-3c ------
# Meme remarque. La ligne d'etat gagne le CHIFFRE qui lui manquait : elle disait
# « Nom trop long », qui est un jugement ; elle dit maintenant de combien.
#
# **Le message de refus tient desormais sur UNE ligne**, et c'est deux retours
# d'Egan a la fois :
#
# * « On se contente de dire que le nom est trop long. Pas de justification. »
#   La phrase sur les deux lots tronques au meme prefixe sort : c'est le motif
#   de la regle, pas ce que l'operateur a besoin de lire pour corriger ;
# * « L'erreur est rouge uniquement sur la ligne 1. » Mesure faite en peignant
#   le bloc : le message faisait trois lignes, seule la premiere sortait en
#   `state-absent` (`#EE878A`), les deux suivantes en `data` (`#E8E8E8`). Le
#   defaut n'est PAS dans la maquette : `jetons.peindre` peint ligne a ligne et
#   `jeton_d_etat` exige que le glyphe OUVRE UNE COLONNE sur la ligne
#   examinee (`jetons.py:555-594`) -- une ligne de continuation, qui par
#   construction ne porte pas le glyphe, ne peut donc pas etre teintee. Un
#   message replie perd sa couleur des le premier retour a la ligne, et se lit
#   alors comme deux messages. Le correctif appartient a `jetons.py` et n'est
#   PAS pose ici (perimetre mesure, revue en trois couches recente) : il est
#   decrit dans le rapport. En attendant, la maquette ne montre plus un cas que
#   le code ne sait pas rendre.

ecrire("E2-3c-extraction-nom-refuse.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite="rush_01 · 25 fps · 4:12",
    centre=[
        "",
        *cartouche("À écrire — édition des noms", [
            "Lots créés               2",
            "Frames écrites           124  +  42        =  166",
            "Espace disque            ~ 2,8 Go                    (majorant)",
            "",
            "Noms produits          > projet_demo_rush_01_25fps_hiver_2█  ✕ 50/48",
            "                         projet_demo_rush_01_25s3            24/48",
        ]),
        "",
        "     ✕ Le nom est trop long : 50 caractères pour 48 admis.",
        "",
        "     Retirez 2 caractères, ou Ctrl+R pour remettre le nom proposé.",
    ],
    etat="✕  50 caractères sur 48 admis — l'action « Extraire » reste inaccessible",
    raccourcis="⌫ effacer  Ctrl+R remettre  Tab les choix  Échap annuler",
))


# --------------------------------------------------------------- E2-4 -------
# **Le journal ne montre plus que ce qui EXISTE** (question d'Egan du
# 2026-08-29 : « Le journal a-t-il de quoi etre produit par le coeur ? »).
#
# Mesure faite. `frame 000084 ecrite` n'avait AUCUNE SOURCE : pendant l'ecriture
# des frames le coeur n'emet aucun texte, seulement des entiers -- `_emettre_
# compte` compte les fichiers deja poses et pousse le nombre
# (`ffmpeg_utils.py:358-368`). C'est ce qui alimente la barre, et rien d'autre.
#
# Ce que le coeur emet reellement, ce sont des JALONS, tous par `logger.info` :
# `Source qualifiee: cadence %s im/s, %d frame(s) source (%s), timecode de
# depart %s` (`extraction.py:748`), `%d frame(s) TIFF %d bits ecrite(s) dans %s`
# (`extraction.py:863`) et `Manifest mis a jour: lot %s dans %s`
# (`extraction.py:894`). Il en produit 37 par extraction, dont 32 redisent le
# rapport de confirmation que l'ecran precedent vient de montrer, et dont 18
# depassent 76 colonnes -- jusqu'a 280. Les quatre lignes montrees ici sont donc
# des jalons ABREGES, horodates par la TUI : le coeur n'horodate pas ses
# messages, c'est le format du journal qui le fait.
#
# **L'ecran montre le lot 2 en cours et non le lot 1** : c'est le seul etat ou
# le journal a plus d'une ligne a montrer, puisque entre le jalon d'ouverture
# d'un lot et celui de sa fermeture le coeur se tait. Une ligne par frame
# demanderait un ajout cote coeur -- il est signale, pas suppose.

ecrire("E2-4-extraction-execution.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite="rush_01 · 25 fps · 4:12",
    centre=[
        "",
        "  Extraction en cours — lot 2 sur 2",
        "",
        "     projet_demo_rush_01_25fps                             écrit",
        "     projet_demo_rush_01_25s3                              en cours",
        "",
        regle("Journal"),
        "",
        "     14:31:02  Source qualifiée : 25 im/s, 6 300 frames, TC 00:00:00:00",
        "     14:31:47  124 frame(s) TIFF 16 bits écrite(s) dans …_25fps/",
        "     14:31:47  Manifest mis à jour : lot projet_demo_rush_01_25fps",
        "     14:31:48  Source qualifiée : 25/3 im/s, 6 300 frames, TC 00:00:00:00",
    ],
    etat=barre(28, 42, "frames", "20 s"),
    raccourcis="Tab journal  Échap interrompre  F1 aide",
))


# --------------------------------------------------------------- E2-5 -------
# Ecran approuve tel quel (« parfait aussi surtout le lien avec l'atelier
# suivant !!! »). Sa ligne d'etat est deja une mesure ; elle suit les nouveaux
# cardinaux. Le second lot porte `25/3 fps` en clair a cote de son `_25s3` :
# c'est le dernier ecran ou la convention se lit, donc celui ou elle doit etre
# la moins ambigue.

ecrire("E2-5-extraction-resultat.txt", maquette(
    bandeau_gauche=BANDEAU,
    bandeau_droite="rush_01 · 25 fps · 4:12",
    centre=[
        "",
        *cartouche("Écrit", [
            "● projet_demo_rush_01_25fps     124 frames · 25 fps   · 2,1 Go",
            "● projet_demo_rush_01_25s3       42 frames · 25/3 fps · 0,7 Go",
            "",
            "Manifest mis à jour             projet_demo/manifest.json",
            "Durée                           2 min 41",
        ]),
        "",
        "   ▸ Ouvrir le dossier des lots",
        "     Composer les planches de ces lots          (atelier Pdf)",
        "     Extraire un autre rush",
        "     Retour aux ateliers",
    ],
    etat="●  2 lots écrits, 166 frames, aucun refus",
    raccourcis="⏎ choisir  ↑↓ naviguer  Tab journal  Échap ateliers  F1 aide",
))

print("atelier Extraction : 12 maquettes ecrites dans maquettes/")
