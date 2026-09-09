# -*- coding: utf-8 -*-
"""Maquettes zone A : ecran projet, menu des ateliers, aide, palier Projet.

**Les `E6-*` vivent ICI et non dans un generateur neuf** (story 11.11, lot D).
Le choix est mesure, pas par defaut :

* ce fichier produit deja `E1-1`, le menu des ateliers -- c'est-a-dire l'ecran
  **d'ou l'on entre** dans le palier Projet, et celui que le lot D doit de
  toute facon modifier (la ligne `Projet` gagne sa troisieme entree). Les deux
  moities du meme geste restent donc dans un seul fichier et ne peuvent pas
  diverger ;
* il est **deja dans le cycle de `regenerer.py`**. Un generateur neuf doit y
  etre *ajoute*, et le commentaire de `regenerer.py` enregistre precisement ce
  manquement : « une maquette produite par un generateur que le cycle sur ne
  lance pas est une maquette qu'aucune regeneration ne remet a jour ». Le
  defaut vit encore aujourd'hui pour `_gen_selection.py` ;
* la seule regle que le depot oppose au regroupement est « deux generateurs qui
  ecrivent les memes fichiers font deux sources de verite ». Aucun fichier n'est
  ecrit deux fois ici.

**Aucun identifiant des `E6-*` n'est ecrit a la main** -- meme discipline que
`_gen_c.py` : `lot_id`, nom de PDF de planches et nom de master sortent des
fonctions du produit (`io.naming`), appelees a la generation.
"""
from construire_maquette import (  # noqa: F401
    elider,
    maquette, barre, cartouche, colonnes, regle, ecrire)

from inspect import signature as _signature

from mixed_media_utility import page_templates
from mixed_media_utility.io import naming, project_layout
from mixed_media_utility.tui import jetons

# ===========================================================================
# Le vocabulaire du palier Projet et de son inventaire (story 11.11).
# ===========================================================================

PROJET = "projet_demo"

#: Les trois rushes de demonstration. Le troisieme porte un nom LONG, pour que
#: la colonne des noms de l'arborescence se mesure sur un cas reel et non sur
#: les noms courts de la demonstration -- meme motif que `RUSH_LONG` de
#: `_gen_c.py` (note 1 d'Egan du 2026-09-01).
RUSH = "plan-04"
RUSH_HIVER = "hiver"
RUSH_LONG = "sequence-12-atelier-fonderie-prise-3"

#: Les cinq lots, **construits** et jamais ecrits. `build_lot_id` compose
#: `<rush_id>_<cadence-courte>` : un `lot_hiver` ou un `lot_25fps` est
#: impossible ici parce que personne ne les tape plus.
LOT_25 = naming.build_lot_id(RUSH, 25)
LOT_12P5 = naming.build_lot_id(RUSH, 12.5)
LOT_8 = naming.build_lot_id(RUSH, 8)
LOT_HIVER = naming.build_lot_id(RUSH_HIVER, 24)
LOT_LONG = naming.build_lot_id(RUSH_LONG, 12.5)


#: Le gabarit de la demonstration. `build_sheets_pdf_filename` exige desormais
#: un `template_id` (`EPIC11-ARB-171`, 2026-09-02) : le mot `planches` a quitte
#: le nom et la mise en page a pris sa place, DERIVEE du gabarit par
#: `naming.sheets_layout_fragment`. Ces deux ecrans ne choisissent pas de mise
#: en page -- ils citent un fichier existant --, donc ils prennent celui de la
#: demonstration, construit et jamais ecrit.
GABARIT_DEMO = page_templates.build_template_id("paysage", 6, "0")


def planches(lot: str, rang: int | None = None, rush: str = RUSH,
             gabarit: str = GABARIT_DEMO) -> str:
    """Le nom du PDF de planches, par la fonction du produit."""
    return naming.build_sheets_pdf_filename(
        PROJET, rush, lot, version_rank=rang, template_id=gabarit)


def master(lot: str, profil: str = "prores_hq", conteneur: str = "mov") -> str:
    """Le nom du master video, par la fonction du produit."""
    return naming.build_master_filename(
        lot_id=lot, profile_id=profil, container=conteneur)


def frame(rush: str, cadence: float, timecode: str) -> str:
    """Le nom d'une frame extraite, par la fonction du produit."""
    return naming.build_extracted_frame_filename(rush, cadence, timecode)


#: La phrase de menu du palier `Projet`, **une seule redaction** : `E1-1` la
#: pose sur sa ligne `Projet` et `E6-0` en titre son ecran. Elle nomme les
#: TROIS entrees du palier, la gestion des medias en tete parce que c'est la
#: neuve. Cote produit c'est `projet_lecture.PHRASES[PROJET]` qui la portera.
#:
#: **Redaction d'Egan, `EPIC11-ARB-201`, verbatim** : « Je mettrais "Gestion
#: des médias, Profil par défaut, Reconstruction" ». Elle remplace
#: « Inventorier et supprimer, profil par défaut, reconstruire », qui decrivait
#: des GESTES la ou Egan nomme des DOMAINES -- et qui laissait « inventorier »
#: en tete alors que l'inventaire est le moyen, pas la fin. Les capitales sont
#: les siennes et ne sont pas normalisees : une redaction d'arbitrage se
#: recopie, elle ne se corrige pas.
PHRASE_DU_PALIER_PROJET = (
    "Gestion des médias, Profil par défaut, Reconstruction")

#: Les trois entrees du palier. Les deux premieres cles sont celles que
#: `palier_projet.py` porte deja ; la troisieme est **a arbitrer au lot B** --
#: aucune commande de coeur ne s'appelle ainsi aujourd'hui, `mmu project
#: remove` ne couvrant que la moitie « supprimer » de l'entree.
ENTREE_INVENTAIRE = "project-inventory"
ENTREE_PROFIL = "set-default-profile"
ENTREE_RECONSTRUCTION = "reconstruct-project"

# ---------------------------------------------------------------------------
# L'arborescence : une ligne par noeud, trois colonnes, aucune seconde colonne
# au sens du DESIGN (c'est un tableau aligne, pas deux zones).
# ---------------------------------------------------------------------------

#: 5 colonnes de tete (marge + glyphe de curseur + blanc), puis 47 pour le nom
#: -- ce qui tient le plus long lot de la demonstration, `LOT_LONG` a sa
#: profondeur 1, MARQUE DE PLIAGE COMPRISE --, 14 pour le cardinal de fichiers
#: et 10 pour le poids. 5 + 47 + 14 + 10 = 76, la zone utile au plancher.
#:
#: **Le nom a gagne une colonne sur le cardinal, puis lui en a rendu une**, et
#: les deux mouvements sont mesures. La marque de pliage (`EPIC11-ARB-200`)
#: ajoute 2 colonnes au plus long nom, qui passe de 43 a 45 -- 45 tenaient dans
#: 45, mais tout juste. Puis `E6-1c` a fait deborder le CARDINAL : un projet de
#: trente rushes porte « 2 118 fichiers », 14 colonnes, la ou la demonstration
#: a trois rushes plafonnait a « 491 fichiers », 12.
#:
#: **Puis le nom a repris une colonne au POIDS, et c'est `EPIC11-ARB-210` qui
#: la reclame** (2026-09-04, l'arbre descend jusqu'a l'objet). Le nom le plus
#: long du niveau OBJET est une planche construite par
#: `naming.build_sheets_pdf_filename` -- `projet_demo_plan-04_12p5_6f-pay.pdf`,
#: 35 colonnes --, precedee de son glyphe d'etat (2) et de 9 colonnes de
#: prefixe de profondeur : 46 pile pour 46 disponibles. Une demonstration calee
#: **au caractere pres** sur son plus long nom ne survit pas au premier objet
#: un peu plus long ; la colonne vient du poids, ou « 12,7 Go » (7 colonnes)
#: laissait quatre blancs de separation et n'en garde que trois.
#:
#: La marque ne pouvait pas se poser dans la tete : un `+` colle au bord gauche
#: ne se rattacherait a aucune profondeur, alors que ce qu'il plie est le
#: noeud, pas la ligne.
TETE_ARBRE = 5
NOM_ARBRE = 46
FICHIERS_ARBRE = 17
POIDS_ARBRE = 8

CURSEUR = jetons.GLYPHES["curseur"]
RATTACHEMENT = jetons.GLYPHES["rattachement"]

#: **La marque de pliage, `EPIC11-ARB-200`.** Egan, verbatim : « Ajoute un +
#: a cote d'un element replie qui peut etre deplie. Et un - le remplace quand
#: il a ete deplie pour le reduire. »
#:
#: **Elle n'est PAS encore dans `jetons.GLYPHES`, et c'est deliberement dit
#: plutot que tu.** La table du `DESIGN.md` section 6 est epinglee a
#: l'egalite par `test_jetons_tui.TABLE_ATTENDUE`, et son repli ASCII est
#: mesure INJECTIF. Or `-` est deja le repli ASCII de `barre-vide` (`░`) : y
#: verser la marque de pliage telle quelle ferait rougir
#: `test_chaque_table_est_injective`. La collision est reelle et se tranche --
#: soit les deux dessins cohabitent comme `curseur`/`invite` le font deja pour
#: `>`, soit `barre-vide` change de repli --, mais elle se tranche dans une
#: story, avec sa mesure, pas dans un generateur de maquette. La maquette
#: DESSINE donc l'arbitrage ; le produit ne l'a pas encore.
PLIAGE_REPLIE = "+"
PLIAGE_DEPLIE = "-"

#: **Les cases a cocher de l'arbre, LUES a la table du produit.**
#: `EPIC11-ARB-204` a tranche `Espace coche` sans que la coche soit dessinee
#: nulle part ; Egan le releve le 2026-09-04 : « Peut-on voir a quoi ressemble
#: la coche ? ». Elle se voit desormais sur `E6-1d`. Les deux dessins viennent
#: de `jetons.GLYPHES`, jamais recopies : c'est la meme paire que la liste de
#: cadences et que l'explorateur en mode selection emploient deja.
CASE_COCHEE = jetons.GLYPHES["coche"]
CASE_VIDE = jetons.GLYPHES["decoche"]

#: **La profondeur du niveau OBJET** (`EPIC11-ARB-210`, tranche le 2026-09-04 :
#: « A faire », et redit deux fois -- « il faut bien qu'on aille jusqu'aux
#: objets dans l'arborescence », « on veut voir chaque master, chaque scan,
#: chaque lot, chaque lot reconstruit »).
#:
#: L'arbre compte donc QUATRE niveaux la ou il en avait trois :
#: rush (0) -> lot (1) -> **groupe d'objets** (2) -> **objet** (3).
PROFONDEUR_OBJET = 3



def noeud(profondeur: int, nom: str, fichiers: str, poids: str,
          curseur: bool = False, pliage: str | None = None,
          case: str | None = None, terminal: bool | None = None) -> str:
    """Un noeud de l'arborescence, a sa profondeur, avec ses deux mesures.

    La profondeur se lit a l'indentation, et les OBJETS -- le niveau le plus
    profond, :data:`PROFONDEUR_OBJET` -- portent le glyphe de **rattachement**
    de la table, le meme que `E3-4` emploie pour ses pages manquantes.

    ``pliage`` porte :data:`PLIAGE_REPLIE`, :data:`PLIAGE_DEPLIE`, ou rien.
    **Rien occupe quand meme les deux colonnes** : sans cela, les noms d'un
    meme niveau ne s'aligneraient plus selon qu'un noeud est pliable ou non, et
    l'indentation cesserait de dire la profondeur -- qui est la seule chose
    qu'elle dit.

    **Un OBJET n'a ni marque de pliage ni colonnes de marque, et c'est mesure
    plutot que choisi.** Un objet est terminal par construction : le coeur
    n'enumere jamais les fichiers d'un objet (`_mesure_du_dossier` additionne
    les 62 frames d'un lot et jette leurs chemins), et Egan interdit lui-meme
    d'aller plus bas -- « on ne peut pas supprimer une unique frame d'un lot
    d'images ». AUCUN noeud de ce niveau ne se plie, donc les deux colonnes y
    seraient mortes sur toutes les lignes a la fois : les retirer ne desaligne
    rien a l'interieur du niveau, et rend les 2 colonnes que le rattachement
    reprend. Le nom d'un objet demarre ainsi en colonne 9 quand celui d'un
    groupe demarre en 6 -- l'indentation reste strictement croissante
    (2, 4, 6, 9), ce qui est la seule promesse qu'elle porte.

    ``case`` porte :data:`CASE_COCHEE` ou :data:`CASE_VIDE` en mode SELECTION,
    rien sinon. Elle se pose **apres** le rattachement et juste avant le nom,
    comme dans `cadences.py` et dans l'explorateur : la case appartient a
    l'objet, pas a la branche qui le porte.
    """
    tete = f"   {CURSEUR} " if curseur else " " * TETE_ARBRE
    indent = "  " * profondeur
    # **La marque precede la decoration de rattachement**, elle ne la suit pas :
    # `└─` dit d'ou la feuille pend, la marque dit si le noeud se plie. Les
    # mettre dans l'autre ordre ecartait le `└─` de trois colonnes de son nom et
    # cassait l'alignement que l'indentation est seule a porter.
    # `terminal` SURCHARGE la regle de profondeur, et elle n'existe que pour un
    # cas mesure : depuis `EPIC11-ARB-244`, un scan vit au niveau 3 -- celui des
    # objets -- tout en portant un enfant, donc en se pliant. La regle de
    # profondeur seule lui refusait sa marque de pliage et lui collait un `└─`
    # de feuille. Elle reste le DEFAUT : aucun appelant qui ne passe pas
    # `terminal` ne change de rendu.
    objet_terminal = (profondeur >= PROFONDEUR_OBJET if terminal is None
                      else terminal)
    deco = f"{RATTACHEMENT} " if objet_terminal else ""
    marque = "" if objet_terminal else (f"{pliage} " if pliage else "  ")
    coche = f"{case} " if case else ""
    corps = f"{indent}{marque}{deco}{coche}{nom}"
    assert colonnes(corps) <= NOM_ARBRE, (corps, colonnes(corps))
    return (tete + corps + " " * (NOM_ARBRE - colonnes(corps))
            + f"{fichiers:>{FICHIERS_ARBRE}}{poids:>{POIDS_ARBRE}}")


def groupe(type_objet: str, cardinal: str, fichiers: str, poids: str,
           pliage: str | None = None, curseur: bool = False,
           case: str | None = None, etat: str = "") -> str:
    """Une ligne de GROUPE d'objets sous un lot : `frames — 62 frames`.

    **Le niveau que reclame `EPIC11-ARB-210`, et sa redaction est d'Egan**, mot
    pour mot dans sa note du 2026-09-03 : « Quand on deplie on voit le detail
    par dossier : - frames - x frames / - planches - x planches / - scans - x
    scans / ... / - masters - x masters ». Un groupe se nomme donc **par le
    type de ce qu'il contient**, jamais « 67 fichiers » -- c'est ce qu'il
    reproche a la version 1 (« reste a les nommer, "frames" ou "scans" au lieu
    de fichiers »).

    Les colonnes de droite ne changent PAS pour autant : le cardinal de
    fichiers et le poids restent ceux de l'arbre, si bien que les sommes se
    verifient toujours a l'oeil d'un niveau a l'autre et d'un ecran a l'autre.
    Le cardinal d'OBJETS, lui, vit dans le nom -- c'est la seule place ou il ne
    coute aucune colonne de mesure.

    **Le cardinal d'un groupe et son cardinal de fichiers ne se lisent pas au
    meme endroit du coeur**, et le piege est reel (mesure du 2026-09-03,
    section 2) : `frames` et le lot scanne sont **un seul noeud** portant N
    fichiers, tandis que masters, planches et scans sont **N noeuds**. « 62
    frames » se lit dans `noeud.fichiers`, « 2 planches » dans
    `len(enfants_de_cette_nature)`. Deux recettes derriere deux lignes qui se
    ressemblent.
    """
    prefixe = f"{etat} " if etat else ""
    return noeud(2, f"{prefixe}{type_objet} — {cardinal}", fichiers, poids,
                 curseur=curseur, pliage=pliage, case=case)


def objet(nom: str, cardinal: str, poids: str, curseur: bool = False,
          case: str | None = None, etat: str = "") -> str:
    """Un OBJET, nomme par le nom que l'outil lui a donne.

    « J'avais aussi parle de nommer les objets par leurs noms et cela n'a pas
    ete pris en compte » (Egan, 2026-09-04) : un objet porte donc ici le nom
    **construit par les fonctions du produit** -- `build_sheets_pdf_filename`,
    `build_master_filename` --, jamais un libelle tape a la main.
    """
    prefixe = f"{etat} " if etat else ""
    return noeud(PROFONDEUR_OBJET, f"{prefixe}{nom}", cardinal, poids,
                 curseur=curseur, case=case)


def elision(fenetre: str = "") -> str:
    """La ligne `…` d'une liste qui deborde, avec sa fenetre a droite.

    **L'idiome est celui de `X4`**, repris et non reinvente : un `…` en tete et
    un `…` en pied, le second portant « 11-17 sur 30 ». Il est ecrit ici plutot
    que ligne a ligne parce que la fenetre se cale sur le BORD DROIT de la zone
    utile, pas sur la colonne des cardinaux -- un `…` n'a ni cardinal ni poids,
    et l'y loger decalait la fenetre de onze colonnes vers l'interieur.
    """
    corps = " " * TETE_ARBRE + "  …"
    utile = TETE_ARBRE + NOM_ARBRE + FICHIERS_ARBRE + POIDS_ARBRE
    return (corps + " " * (utile - colonnes(corps) - colonnes(fenetre))
            + fenetre).rstrip()


#: Libelle a gauche sur 24 colonnes, valeur a droite : le motif du panneau
#: chiffre (`DESIGN.md` 7.4), pose une fois pour les quatre cartouches `E6-*`.
LARGEUR_LIBELLE = 24


def chiffre(libelle: str, valeur: str) -> str:
    """Une ligne de panneau chiffre : libelle a gauche, valeur a droite."""
    return f"{libelle:<{LARGEUR_LIBELLE}}{valeur}"


def issue(libelle: str, note: str = "", curseur: bool = False,
          largeur: int = 35) -> str:
    """Une issue d'un point de decision, avec sa note a droite.

    Meme geometrie que `E5-3b` : six colonnes de tete, le glyphe de curseur
    **seul** (`EPIC11-ARB-126` -- aucune case a cocher a cote d'une fleche hors
    liste cochable).
    """
    tete = f"   {CURSEUR} " if curseur else " " * TETE_ARBRE
    return (tete + libelle + " " * (largeur - colonnes(libelle)) + note).rstrip()


# ---------------------------------------------------------------------------
# Les deux familles d'ECART, chacune avec sa geometrie. Elles sont ecrites ici
# plutot que ligne a ligne pour la meme raison que `cartouche` : un bord droit
# decale d'une colonne est invisible a la relecture et saute aux yeux dans un
# vrai terminal.
#
# **Leur seul appelant, `E6-1b`, a ete retire le 2026-09-04**
# (`EPIC11-ARB-217`). Elles restent parce que les deux familles d'ecart, elles,
# n'ont pas disparu : elles sont dans l'arbre de `E6-1`, et le jour ou un ecran
# les regroupe a nouveau -- un filtre sur le compteur « 4 écarts », par
# exemple -- c'est cette geometrie qui les rendra. Le dire vaut mieux que
# laisser croire a du code vivant.
# ---------------------------------------------------------------------------

#: Zone de texte a l'interieur d'un cartouche de MAQUETTE. Elle est derivee de
#: la signature de `cartouche()` -- 72 colonnes de cadre, moins deux bordures et
#: deux marges -- plutot que recopiee : une largeur ecrite ici divergerait au
#: premier ajustement du bati.
#:
#: **Elle ne vaut PAS `jetons.largeur_de_cartouche()` (72), et l'ecart est
#: reel** : le cartouche du produit occupe toute la zone utile (76), celui des
#: maquettes est retrait de deux colonnes de chaque cote. L'ecart est constate
#: ici, pas corrige -- il touche les cinquante-huit maquettes du depot.
LARGEUR_CARTOUCHE = _signature(cartouche).parameters["largeur"].default
UTILE_CARTOUCHE = LARGEUR_CARTOUCHE - 2 * 1 - 2 * 1
#: La colonne ou commence le nom du fichier dans la famille « declare, absent ».
COLONNE_DU_NOM = 28


def absence(objet: str, nom: str) -> str:
    """Un objet DECLARE au manifeste et ABSENT du disque (AC 1.3).

    Il porte son glyphe d'etat -- celui de la table, jamais un dessin local --
    et il est NOMME : « jamais tu ni confondu avec un objet de poids zero ».
    """
    corps = f"{ABSENT} {objet}"
    return corps + " " * (COLONNE_DU_NOM - colonnes(corps)) + nom


def attendu(chemin: str) -> str:
    """La ligne de rattachement d'une absence : ou l'objet etait attendu."""
    corps = "   attendu ici"
    return corps + " " * (COLONNE_DU_NOM - colonnes(corps)) + chemin


def filiation(nom: str, droite: str, colonne: int = 44) -> str:
    """Une annexe emportee par filiation, avec sa mesure ou son absence.

    Les annexes d'un lot se suppriment **par filiation** (`EPIC11-ARB-90`) : le
    panneau les nomme une par une plutot que d'en donner le seul cardinal, et
    une annexe ABSENTE du disque garde sa ligne -- c'est
    `fichiers_attendus_absents` que ces lignes-la projettent.
    """
    corps = f"  {nom}"
    return corps + " " * (colonne - colonnes(corps)) + droite


def avancement(nom: str, etat: str, profondeur: int = 0,
               colonne: int = 48) -> str:
    """Une ligne de la liste d'avancement d'un ecran d'execution."""
    corps = "  " * profondeur + nom
    return (" " * TETE_ARBRE + corps
            + " " * (colonne - colonnes(corps)) + etat)


def intrus(chemin: str, fichiers: str, poids: str) -> str:
    """Un objet PRESENT sur le disque et declare NULLE PART (AC 1.4).

    « Volet symetrique de 1.3, et c'est lui le vrai livrable » : c'est ce que
    produit un nettoyage manuel interrompu, et rien aujourd'hui ne le montre.
    """
    corps = f"{RESERVE} {chemin}"
    reste = f"{fichiers:>13}{poids:>11}"
    return corps + " " * (UTILE_CARTOUCHE - colonnes(corps)
                          - colonnes(reste)) + reste


ecrire("E0-1-projet-recents.txt", maquette(
    bandeau_gauche="mmu · — aucun projet —",
    bandeau_droite="v0.1",
    centre=[
        "",
        "  Ouvrir un projet",
        "",
        "   ▸ projet_demo                     ouvert le 26/08 · 3 rushes · 5 lots",
        "     film_court_2026                 ouvert le 21/08 · 1 rush  · 2 lots",
        "     tests_calibration               ouvert le 14/08 · 0 rush  · 0 lot",
        "",
        regle(),
        "",
        "     Ouvrir un autre dossier…          Tab, puis le chemin du projet",
        "",
        "     Suppr retire de la liste — le dossier du projet n'est pas touché",
    ],
    etat="",
    raccourcis="⏎ ouvrir  ↑↓ naviguer  Suppr retirer  Tab chemin  Q quitter",
))

ecrire("E0-2-projet-chemin.txt", maquette(
    bandeau_gauche="mmu · — aucun projet —",
    bandeau_droite="v0.1",
    centre=[
        "",
        "  Ouvrir un projet",
        "",
        "     projet_demo                     ouvert le 26/08 · 3 rushes · 5 lots",
        "     film_court_2026                 ouvert le 21/08 · 1 rush  · 2 lots",
        "     tests_calibration               ouvert le 14/08 · 0 rush  · 0 lot",
        "",
        regle(),
        "",
        "   ▸ Dossier du projet  > D:\\HOKO\\Documents\\mmu\\projects\\pr",
        "",
        "      projet_demo/         projet_hiver/         projet_hiver_v2/",
    ],
    etat="3 dossiers correspondent — Tab complète, ↓ descend dans la liste",
    raccourcis="⏎ ouvrir  Tab compléter  Échap récents  F1 aide  Q quitter",
))

ecrire("E0-3-projet-refus.txt", maquette(
    bandeau_gauche="mmu · — aucun projet —",
    bandeau_droite="v0.1",
    centre=[
        "",
        "  Ouvrir un projet",
        "",
        "     projet_demo                     ouvert le 26/08 · 3 rushes · 5 lots",
        "     film_court_2026                 ouvert le 21/08 · 1 rush  · 2 lots",
        "",
        regle(),
        "",
        "     Dossier du projet    > D:\\HOKO\\Documents\\rushes_bruts",
        "                            ✕",
        "",
        "     Ce dossier existe mais ne porte pas de project.json.",
        "",
        "   ▸ Créer un projet ici",
        "     Corriger le chemin",
        "     Revenir aux récents",
    ],
    etat="✕  Aucun project.json dans ce dossier — rien n'a été écrit",
    raccourcis="⏎ choisir  ↑↓ naviguer  Échap récents  F1 aide  Q quitter",
))

ecrire("E0-4-projet-creer.txt", maquette(
    bandeau_gauche="mmu · — aucun projet —",
    bandeau_droite="création",
    centre=[
        "",
        "  Créer un projet",
        "",
        "     Dossier parent     > D:\\HOKO\\Documents\\mmu\\projects",
        "                          le dossier qui CONTIENDRA le projet",
        "",
        "     Nom du projet        planche_hiver_2026",
        "",
        regle("Ce qui sera créé"),
        "",
        "     Dossier du projet    …\\projects\\planche_hiver_2026",
        "     Arborescence         frames/  patches/  scans/  outputs/  versions/",
        "     Fichier de projet    project.json",
    ],
    etat="Le dossier n'existe pas encore : il sera créé avec son arborescence.",
    raccourcis="⏎ créer  Tab champ  Échap récents  F1 aide  Q quitter",
))

ecrire("E1-1-menu-ateliers.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Ateliers",
    bandeau_droite="3 rushes · 5 lots · 2 masters",
    centre=[
        "",
        "  Que faire dans projet_demo ?",
        "",
        "   ▸ Extraction   Ouvrir un rush, borner, choisir les cadences, extraire",
        "     Scan         Déposer des scans, détecter, puis écrire les TIFF",
        "     Pdf          Composer et générer les planches d'un ou plusieurs lots",
        "     Exports      Encoder un master depuis un lot reconstruit",
        "",
        f"     Projet       {PHRASE_DU_PALIER_PROJET}",
        "",
        regle(),
        "",
        "     Dernière écriture   26/08 14:32 · lot_25fps · 124 frames     ● ok",
    ],
    etat="",
    raccourcis="⏎ entrer  ↑↓ naviguer  Échap changer de projet  F1 aide  Q quitter",
))

# Les neuf ecrans `E2-*` de l'atelier Extraction VIVAIENT ICI (lignes 116-321
# jusqu'au 2026-08-29). Ils sont passes dans `_gen_extraction.py`, avec les
# trois ecrans de relink qui leur manquaient : `EPIC11-ARB-56` (ligne d'etat),
# `-61` (la profondeur disparait), `-45` (les issues, une par ligne, sans
# radio), `-62` (le nom d'un lot fractionnaire) et `-32`/`-63` (le relink est
# dans la TUI) les reecrivent tous les neuf. Deux generateurs qui ecrivent les
# memes fichiers font deux sources de verite, et c'est le dernier lance qui
# gagne en silence : la section est donc DEPLACEE, pas dupliquee.

ecrire("T1-1-aide-champ.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Extraction",
    bandeau_droite="temps 1 sur 2 · prévisualiser",
    centre=[
        "",
        "  Quelles cadences regarder ?",
        "",
        "   ▸ [x] 25        source            124 frames        (toutes)",
        "",
        *cartouche("Ajouter une cadence", [
            "",
            "La liste propose la cadence source et ses divisions. Pour une",
            "cadence qui n'y est pas, `a` ouvre une saisie libre :",
            "",
            "   10           un nombre, en images par seconde",
            "   8,333        la virgule ou le point, les deux marchent",
            "   24000/1001   une fraction, pour les cadences NTSC",
            "",
            "La ligne ajoutée porte la mention « ajoutée » et se retire par",
            "Suppr. Cocher n'extrait rien : on choisit ce qu'on regarde.",
        ]),
    ],
    etat="",
    raccourcis="Échap fermer  F1 manuel complet  ↑↓ faire défiler",
))

ecrire("T1-2-manuel-raccourcis.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Manuel",
    bandeau_droite="page 1 sur 3",
    centre=[
        "",
        "  Raccourcis — partout",
        "",
        "     ↑ ↓          déplacer le curseur dans une liste",
        "     Entrée       valider la ligne ou le formulaire courant",
        "     Espace       cocher / décocher (listes à cases)",
        "     Tab          champ suivant · compléter un chemin · voir le journal",
        "     Échap        remonter d'un palier, sans rien écrire",
        "     F1           aide du champ courant, ou ce manuel",
        "     q            quitter (demande confirmation si une tâche tourne)",
        "",
        "  Propres à un écran",
        "",
        "     a            ajouter une cadence          (Extraction)",
        "     r            retrouver un rush absent     (Extraction)",
    ],
    etat="",
    raccourcis="→ page suivante  Échap fermer  Q quitter",
))

# ===========================================================================
# Story 11.11 -- le palier Projet et son inventaire (`E6-*`).
#
# **Les chiffres de la demonstration se somment d'un ecran a l'autre.** Les
# cardinaux et les poids d'un lot font ceux de son rush, les rushes font ceux
# du projet, et la ligne d'etat de `E6-1` porte ces totaux-la. Une
# demonstration dont les sommes ne tombent pas juste apprend a ne pas lire les
# chiffres -- et c'est exactement ce qu'un ecran d'inventaire vend.
#
#   plan-04_25      frames 124 (1,5 Go) + lot scanne 124 (1,5 Go)
#                   + planches 2 (76 Mo) + master 1 (412 Mo)
#                   + scans 4 pages (550 Mo) + un second scan NON DECLARE
#                     4 pages (550 Mo)                    = 259 f. / 4,6 Go
#   plan-04_12p5    frames  62 (770 Mo) + master 1 (206 Mo)
#                   + scans 4 (550 Mo) ; planches DECLAREE ABSENTE
#                                                         =  67 f. / 1,5 Go
#   plan-04_12p5_v2 frames 124 (1,5 Go), PRESENT NON DECLARE
#                                                         = 124 f. / 1,5 Go
#   plan-04_8       frames  40 (496 Mo) + planches 1 (25 Mo)
#                                                         =  41 f. / 521 Mo
#   rush plan-04                                          = 491 f. / 8,1 Go
#
# **Le cardinal d'OBJETS de la ligne d'etat se somme lui aussi**, et il n'a pas
# bouge en gagnant son niveau d'affichage : 7 objets pour `plan-04_25` (frames,
# lot scanne, 2 planches, 1 master, 2 scans), 4 pour `plan-04_12p5`, 2 pour
# `plan-04_8`, 5 pour `hiver_24`, 2 pour le lot long -- soit les **20 objets**
# que `E6-0` et `E6-1` annoncent tous deux. Le lot non declare `plan-04_12p5_v2`
# n'en est pas : il est hors manifeste, et c'est ce que son glyphe dit.
#   hiver_24        frames  96 (1,2 Go) + planches 3 (92 Mo) ;
#                   master DECLARE ABSENT                 =  99 f. / 1,3 Go
#   <RUSH_LONG>_12p5 frames 210 (2,6 Go) + master 1 (690 Mo)
#                                                         = 211 f. / 3,3 Go
#   projet                                                = 801 f. / 12,7 Go
# ===========================================================================

#: Les dossiers de l'arborescence projet, **lus de `project_layout`** et jamais
#: ecrits : un `patches/` en dur ici serait la seconde redaction que ce module
#: existe pour empecher cote produit.
FRAMES = project_layout.FRAMES_DIRNAME
SCANS = project_layout.SCANS_DIRNAME
PATCHES = project_layout.PATCHES_DIRNAME
OUTPUTS = project_layout.OUTPUTS_DIRNAME
OUTPUT_FRAMES = project_layout.OUTPUT_FRAMES_DIRNAME

#: Le lot de rang 2 **non declare** de la demonstration : il est sur le disque
#: et le manifeste l'ignore. C'est le volet de l'AC 1.4, « le vrai livrable ».
LOT_12P5_V2 = naming.build_lot_id(RUSH, 12.5, version_rank=2)

#: Le rang 2 du LOT_25, qui sert de slug au **second scan** de ce lot, et ce
#: second scan est **NON DECLARE** : rescanner une planche corrigee produit une
#: version (`EPIC11-ARB-104`, `EPIC11-ARB-105`), et la filiation d'un scan est
#: DIFFEREE -- elle n'existe qu'apres reconstruction. Un scan ingere et jamais
#: reconstruit est donc exactement l'orphelin que `_orphelins` decrit : « un
#: dossier d'images qui pese sur le disque et qu'aucun ecran ne montre, ce qui
#: est exactement le sujet de la story ». Le slug est construit par la fonction
#: du produit, comme tous les autres.
LOT_25_V2 = naming.build_lot_id(RUSH, 25, version_rank=2)

ABSENT = jetons.GLYPHES["absent"]
RESERVE = jetons.GLYPHES["substitute"]

#: **Ce qu'un nom d'objet peut occuper quand la ligne porte AUSSI une coche.**
#: Derive de la geometrie, jamais compte a la main : le niveau objet consomme
#: son indentation, son rattachement et sa case, et ce qui reste est ce qu'un
#: nom peut prendre. Une constante litterale serait fausse le jour ou l'une
#: des trois bouge, et personne ne le verrait -- c'est exactement ce que
#: `QUEUE_MIRE` et `QUEUE_PLANCHES` font deja dans `_gen_c.py`.
NOM_OBJET_COCHE = NOM_ARBRE - 2 * PROFONDEUR_OBJET - len(f"{RATTACHEMENT} ") \
                  - len(f"{CASE_VIDE} ") - len(f"{ABSENT} ")

#: Ce qu'un nom de planche ou de master ne perd jamais a l'ellipse : la mise
#: en page et le rang pour l'un, le profil et le conteneur pour l'autre. Les
#: deux tiennent en quinze colonnes, mesure sur les noms que le produit bâtit.
QUEUE_PLANCHE = 15
COMPLET = jetons.GLYPHES["complete"]
NEUTRE = jetons.GLYPHES["neutre"]

# ---------------------------------------------------------------------------
# LE VOCABULAIRE, tranche par Egan le 2026-09-04 (note 13). Verbatim :
#
#   « Un lot est un ensemble de frames extraites depuis le rushe source avec
#     extract. Il s'imprime en une planche, composee de pages mais on ne traite
#     pas ce detail. L'ensemble de ces pages une fois scannees forment un scan.
#     A partir d'un scan on reproduit donc un "lot scanne" (scan-lot) qui est
#     lui meme un ensemble de "frames scannees" (scan-frames). »
#
# **Seules les MAQUETTES le portent aujourd'hui.** Le renommage des dossiers,
# des commandes et de leurs arguments -- `output-frames/`, `--frames`,
# `NATURE_FRAMES_RESCANNEES`, « lot reconstruit » du menu Exports -- est une
# story qu'Egan demande lui-meme « au debut d'une vague », et rien n'en est
# fait ici : une maquette qui renommerait un libelle que le produit mesure
# ailleurs ferait diverger les deux surfaces, ce qui est exactement le defaut
# que la frontiere `R12` a paye entre `X5` et l'explorateur livre.
# ---------------------------------------------------------------------------

#: Les cinq groupes d'objets d'un lot, dans l'ordre ou `_enfants_du_lot` les
#: pose. Le quatrieme est le seul qui change de nom : « frames reconstruites »
#: devient le **lot scanne**, et ce qu'il contient des **frames scannees**.
GROUPE_FRAMES = "frames"
GROUPE_PLANCHES = "planches"
GROUPE_SCANS = "scans"
GROUPE_LOT_SCANNE = "lot scanné"
GROUPE_MASTERS = "masters"

#: L'unite de comptage du lot scanne. Elle ne compte PAS des lots scannes : un
#: lot n'en porte qu'un, `output_frames_dir` etant singulier au manifeste. Ce
#: groupe est donc une feuille, comme `frames`, et son cardinal est celui de
#: ses frames scannees.
UNITE_SCAN_FRAMES = "frames scannées"

# ------------------------------------------------------- E6-0 : le palier ---

ecrire("E6-0-projet-palier.txt", maquette(
    bandeau_gauche=f"mmu · {PROJET} · Projet",
    bandeau_droite="3 rushes · 5 lots · 12,7 Go",
    centre=[
        "",
        f"  Que faire sur {PROJET} lui-même ?",
        "",
        f"   {CURSEUR} Gestion des médias",
        "     Gérer les médias du projet : ajout, relink et suppression",
        "",
        "     Profil de calibration par défaut",
        "     Poser le profil que les scans utiliseront sans le répéter",
        "",
        "     Reconstruire le projet depuis des QR lus",
        "     Rebâtir un project.json depuis les payloads de page",
        "",
        regle(),
        "",
        "     Profil par défaut    mire-hp-envy-4520-26aout.json",
    ],
    etat="3 rushes · 5 lots · 20 objets · 801 fichiers · 12,7 Go · 4 écarts",
    raccourcis="⏎ choisir  ↑↓ naviguer  Échap ateliers  F1 aide  Q quitter",
), hauteur_du_curseur=2)

# -------------------------------------------------- E6-1 : l'arborescence ---

# **`EPIC11-ARB-210` : l'arbre descend jusqu'a l'objet, et il gagne un niveau.**
# Egan, 2026-09-04 : « A faire », puis deux fois plutot qu'une -- « il faut bien
# qu'on aille jusqu'aux objets dans l'arborescence. On veut voir chaque master,
# chaque scan, chaque lot, chaque lot reconstruit ». C'etait deja un des vingt
# retours de la version 1, et il n'avait PAS ete porte : « J'avais aussi parle
# de nommer les objets par leurs noms et cela n'a pas ete pris en compte. »
#
# Quatre niveaux : rush -> lot -> **groupe d'objets** -> **objet**. Le `+` / `-`
# (`EPIC11-ARB-200`) vaut a chacun d'eux, et non plus aux seuls lots.
#
# **Deux groupes ne se plient pas, et c'est une mesure, pas un oubli.**
# `frames` et le lot scanne sont chacun **un seul noeud** portant N fichiers :
# le coeur additionne les 62 frames d'un lot et jette leurs chemins
# (`_mesure_du_dossier`), si bien qu'il n'existe aucun objet a montrer dessous.
# C'est aussi la regle produit qu'Egan a posee lui-meme -- « on ne peut pas
# supprimer une unique frame d'un lot d'images » --, donc un niveau de plus ne
# serait pas seulement invendable, il serait faux. Les trois autres groupes
# (planches, scans, masters) sont N noeuds et se plient.
#
# **Un scan compte pour UN, jamais par page** (exigence explicite d'Egan) : la
# ligne de groupe dit « scans — 1 scan », la ligne d'objet dit « 4 pages », et
# la colonne de cardinal porte les 4 fichiers qui font la somme du lot.
#
# **Les deux ecarts restent dans l'arbre** (note 5 du 2026-09-04, « Les objets
# absents, non declares et avec avertissements restent dans l'arbre ») : la
# planche declaree-absente est desormais NOMMEE par son fichier, au niveau
# objet, et le lot non declare garde sa place au niveau lot. Ce que cette
# maquette ne dessine PAS, et il faut le dire : un troisieme etat
# « avertissement ». `project_inventory` n'en porte que trois -- `present`,
# `declare_absent`, `non_declare` --, dont deux sont des ecarts ; en inventer un
# troisieme ici ferait promettre a la maquette une couleur que le produit ne
# sait pas rendre. La question est remontee a Egan plutot que tranchee.
#
# **L'ecart code / maquette du niveau GROUPE reste ouvert, et il est nomme.**
# `remove_project_element` n'a aucune cible qui vise le dossier `frames/` d'un
# lot, et son `--frames` vise les frames **rescannees** -- c'est-a-dire, dans
# le vocabulaire tranche le 2026-09-04, le lot scanne. Egan repond « Il faut
# corriger le code », et il en fait une story de debut de vague. Cette maquette
# dessine donc un niveau que le coeur sait AFFICHER (les cinq natures sont deja
# des enfants du lot) mais pas encore SUPPRIMER a cette granularite.
#
# **Les deux derniers rushes se replient**, et c'est ce qui paie le niveau neuf :
# le niveau objet coute six lignes sur `plan-04_12p5`, la grille en a dix-sept,
# et un rush replie dit deja ce qu'il cache par son `+`.

ecrire("E6-1-projet-inventaire.txt", maquette(
    bandeau_gauche=f"mmu · {PROJET} · Projet",
    bandeau_droite="inventaire · 801 fichiers · 12,7 Go",
    centre=[
        "",
        # **Le titre est le NOM DU PROJET, et rien d'autre** (Egan, 2026-09-04,
        # note 1) : « Au lieu de "ce que projet_demo contien" mettre juste le
        # nom du projet ». Sa note porte sur `E6-1a`, l'etat de LECTURE du meme
        # ecran ; les deux etats ne peuvent pas porter deux titres differents
        # sans que le titre change sous les yeux au moment ou la lecture finit.
        f"  {PROJET}",
        "",
        noeud(0, RUSH, "2 lots · 491 f.", "8,1 Go", pliage=PLIAGE_DEPLIE,
              case=CASE_VIDE),
        noeud(1, LOT_25, "5 objets · 259 f.", "4,6 Go", pliage=PLIAGE_REPLIE,
              case=CASE_VIDE),
        noeud(1, LOT_12P5, "3 objets · 67 f.", "1,5 Go",
              pliage=PLIAGE_DEPLIE, case=CASE_VIDE),
        groupe(GROUPE_FRAMES, "62 frames", "62 f.", "770 Mo",
               case=CASE_VIDE),
        groupe(GROUPE_PLANCHES, "1 planche", "0 f.", NEUTRE,
               pliage=PLIAGE_DEPLIE, case=CASE_VIDE),
        objet(elider(planches(LOT_12P5), NOM_OBJET_COCHE, queue=QUEUE_PLANCHE),
              "0 f.", NEUTRE, etat=ABSENT, curseur=True, case=CASE_VIDE),
        groupe(GROUPE_MASTERS, "1 master", "1 f.", "206 Mo",
               pliage=PLIAGE_DEPLIE, case=CASE_VIDE),
        objet(elider(master(LOT_12P5), NOM_OBJET_COCHE, queue=QUEUE_PLANCHE),
              "1 f.", "206 Mo", case=CASE_VIDE),
        noeud(1, f"{LOT_12P5}_scan — 1 lot scanné", "4 pages", "550 Mo",
              pliage=PLIAGE_DEPLIE, case=CASE_VIDE),
        groupe(GROUPE_LOT_SCANNE, "62 frames scannées", "62 f.", "770 Mo",
               case=CASE_VIDE),
        noeud(1, f"{RESERVE} {LOT_12P5_V2} · non déclaré",
              "3 objets · 124 f.", "1,5 Go", pliage=PLIAGE_REPLIE,
              case=CASE_VIDE),
        noeud(1, LOT_8, "3 objets · 41 f.", "521 Mo", pliage=PLIAGE_REPLIE,
              case=CASE_VIDE),
        noeud(0, RUSH_HIVER, "1 lot · 99 f.", "1,3 Go", pliage=PLIAGE_REPLIE,
              case=CASE_VIDE),
        noeud(0, RUSH_LONG, "1 lot · 211 f.", "3,3 Go", pliage=PLIAGE_REPLIE,
              case=CASE_VIDE),
    ],
    # **La ligne d'etat est CONTEXTUELLE quand le curseur porte un ecart, et
    # c'est ce qui remplace `E6-1b`** (`EPIC11-ARB-217`, tranche le
    # 2026-09-04 : « fondre dans E6-1 »). L'ecran des ecarts portait deux
    # familles ; l'une -- les presents non declares -- etait deja dans l'arbre
    # (`▲ … · non déclaré`), l'autre ne l'etait nulle part sinon par sa croix.
    # Le CHEMIN ATTENDU, seule chose que `E6-1b` disait de plus, se lit
    # desormais ici. Les cardinaux globaux ne sont pas perdus pour autant :
    # ils vivent dans le bandeau de droite.
    etat=f"{ABSENT} déclaré au manifeste, absent du disque · attendu dans "
         "patches/ · 4 écarts",
    # **L'HISTOIRE de cette ligne, gardee parce qu'elle est l'argument qui a
    # produit l'arbitrage.** Avec les sept gestes que cet ecran portait, la
    # barre fixe reclamait **89 colonnes** pour une zone utile de 76, et
    # `Tab écarts` avait ete retire provisoirement -- c'est-a-dire que la
    # porte de `E6-1b` n'etait plus annoncee. Ce debordement mesure est ce
    # qui a fait poser `EPIC11-ARB-209` puis `215` : une barre fixe ne peut
    # pas annoncer sept gestes. Les deux arbitrages tranches le 2026-09-04
    # ferment la question des deux bouts -- la barre ne porte plus que ce qui
    # agit, et `E6-1b` n'a plus de porte a annoncer puisqu'il est fondu ici.
    #
    # **`EPIC11-ARB-215`, issue C, tranchee par Egan le 2026-09-04.** La barre
    # ne porte plus que ce qui AGIT sur l'objet sous le curseur ; les gestes de
    # deplacement (`→`, `←`, `Échap`) vivent dans `F1`, ou ils etaient deja
    # decrits. Motif mesure : avec les trois touches contextuelles qu'Egan
    # demande en `Ctrl+`, la barre complete valait **122 colonnes sur 76**, et
    # **105** au pire cas contextuel reel -- le prefixe `Ctrl+` coute cinq
    # colonnes par touche. En issue C elle vaut **70/76**, six de marge.
    #
    # **`Ctrl+D` et `Ctrl+L` sont EXCLUSIFS** : on declare absent ce qui
    # manque, on relinke ce qui est **deja** declare absent. Le curseur est ici
    # sur une planche declaree absente, donc c'est `Ctrl+L relinker` qui
    # s'affiche -- jamais les deux ensemble, ce qui est la mesure qui fait
    # tenir la ligne.
    #
    # **`Ctrl+A` n'est PAS « tout selectionner »** (correction d'Egan du
    # 2026-09-04, verbatim) : « Ajouter au projet depuis le disque : un rushe
    # qui n'est pas deja extrait ne pouvait pas etre ajoute au projet. C'est un
    # des endroits ou le faire, en plus de l'atelier extract. » C'est un second
    # point d'entree d'IMPORT, pas un geste de selection.
    raccourcis=("Espace cocher  Suppr retirer  Ctrl+A ajouter  "
                "Ctrl+L relinker  F1 aide"),
),
# **`EPIC11-ARB-208` -- les deux lignes d'etat de l'arbre sont DECLAREES.**
# Egan, verbatim : « La croix ne donne pas lieu a une colorisation en rouge sur
# la maquette. A corriger. »
#
# Ce n'etait pas un oubli de teinte mais la limite CONNUE du repli par motif :
# `jetons.jeton_d_etat` exige qu'un glyphe **ouvre une colonne** -- debut de
# ligne, ou creux d'au moins deux blancs. Or dans l'arbre le glyphe est precede
# du rattachement (`└─ `) ou de la marque de pliage (`+ `), c'est-a-dire d'UN
# seul blanc. Exactement le defaut qu'Egan avait deja nomme sur `E5-3b` pour le
# glyphe pose dans un cartouche, et que le produit ferme depuis
# `EPIC11-ARB-71` en DONNANT l'etat au lieu de le deviner.
#
# Le mecanisme de declaration existait donc deja ; c'est l'arbre qui ne s'en
# servait pas. Rien n'est relache dans `_etat_structurel` : le relacher ferait
# peindre a la maquette ce que le produit ne peindra pas, ce qui est la
# divergence meme que ce mecanisme existe pour empecher.
    hauteurs_de_message={
        # **Le nom ELIDE, pas le nom entier** : la cle designe la ligne telle
        # qu'elle est RENDUE, et depuis que la coche prend ses quatre colonnes
        # cette ligne porte une ellipse. Le verificateur l'a attrape --
        # « 0 ligne(s) d'etat, il en faut exactement une » --, ce qu'une
        # relecture n'aurait pas fait.
        elider(planches(LOT_12P5), NOM_OBJET_COCHE, queue=QUEUE_PLANCHE): 1,
        f"{LOT_12P5_V2} · non déclaré": 1,
    },
)

# ------------------------- E6-1d : la COCHE, enfin dessinee quelque part ----
#
# **Egan, 2026-09-04, note 3 : « Peut-on voir a quoi ressemble la coche ? »**
# `EPIC11-ARB-204` a tranche `Espace coche` le 2026-09-03, la ligne du bas
# l'annonce depuis, et AUCUNE maquette du palier Projet ne la dessinait : le
# geste etait promis et invisible. Cet ecran est l'etat de SELECTION de `E6-1`,
# pas un ecran de plus -- meme titre, meme arbre, meme ligne de raccourcis.
#
# **Il deplie `plan-04_25` la ou `E6-1` deplie `plan-04_12p5`**, et ce n'est pas
# un choix d'illustration : c'est le seul lot de la demonstration qui porte les
# CINQ groupes, donc le seul ou le **lot scanne** -- le mot qu'Egan vient de
# trancher (note 13) -- puisse se lire. `plan-04_12p5`, lui, est le seul a
# porter l'ecart declare-absent, que `E6-1` doit montrer. Les deux ecrans se
# repartissent les deux demonstrations plutot que de les entasser sur un seul.
#
# **Les sommes tombent juste ici aussi** : 124 + 2 + 8 + 124 + 1 = 259 fichiers
# et 1,5 + 0,076 + 1,1 + 1,5 + 0,412 = 4,6 Go, ce que la ligne de `plan-04_25`
# porte dans `E6-1`. Les deux objets coches font 124 + 8 = 132 fichiers et
# 1,5 + 1,1 = 2,6 Go, ce que la ligne d'etat annonce.
#
# **Deux scans pour deux planches** : `plan-04_25/` et `plan-04_25_v2/`, quatre
# pages chacun. Le rang du second n'est pas un ornement -- un scan est l'un des
# cinq objets versionnables d'`EPIC11-ARB-104`, et rescanner une planche
# corrigee est le scenario meme qui a etabli cet arbitrage.

ecrire("E6-1d-projet-inventaire-selection.txt", maquette(
    bandeau_gauche=f"mmu · {PROJET} · Projet",
    bandeau_droite="sélection · 3 objets cochés",
    centre=[
        "",
        f"  {PROJET}",
        "",
        noeud(0, RUSH, "2 lots · 491 f.", "8,1 Go", pliage=PLIAGE_DEPLIE,
              case=CASE_VIDE),
        noeud(1, LOT_25, "5 objets · 259 f.", "4,6 Go", curseur=True,
              pliage=PLIAGE_DEPLIE, case=CASE_VIDE),
        groupe(GROUPE_FRAMES, "124 frames", "124 f.", "1,5 Go",
               case=CASE_COCHEE),
        groupe(GROUPE_PLANCHES, "2 planches", "2 f.", "76 Mo",
               pliage=PLIAGE_REPLIE, case=CASE_VIDE),
        groupe(GROUPE_MASTERS, "1 master", "1 f.", "412 Mo",
               pliage=PLIAGE_REPLIE, case=CASE_VIDE),
        # **Les deux scans sont des FRERES du lot** (`EPIC11-ARB-219`, valide
        # par Egan le 2026-09-04 : « Le scan est frere du lot et le lot scanne
        # est enfant du scan »), et chacun porte son lot scanne. Cet ecran
        # montre du meme coup ce que la selection en fait : cocher le scan ne
        # coche pas son lot scanne, ce sont deux objets.
        noeud(1, f"{LOT_25}_scan — 1 lot scanné", "4 pages", "550 Mo",
              pliage=PLIAGE_DEPLIE, case=CASE_COCHEE),
        groupe(GROUPE_LOT_SCANNE, f"124 {UNITE_SCAN_FRAMES}",
               "124 f.", "1,5 Go", case=CASE_COCHEE),
        noeud(1, f"{RESERVE} {LOT_25}_scan_v2 · non déclaré", "4 pages",
              "550 Mo", pliage=PLIAGE_REPLIE, case=CASE_VIDE),
        noeud(1, LOT_12P5, "5 objets · 67 f.", "1,5 Go", pliage=PLIAGE_REPLIE,
              case=CASE_VIDE),
        noeud(1, f"{RESERVE} {LOT_12P5_V2} · non déclaré",
              "3 objets · 124 f.", "1,5 Go", pliage=PLIAGE_REPLIE,
              case=CASE_VIDE),
        noeud(1, LOT_8, "3 objets · 41 f.", "521 Mo", pliage=PLIAGE_REPLIE,
              case=CASE_VIDE),
        noeud(0, RUSH_HIVER, "1 lot · 99 f.", "1,3 Go", pliage=PLIAGE_REPLIE,
              case=CASE_VIDE),
        noeud(0, RUSH_LONG, "1 lot · 211 f.", "3,3 Go", pliage=PLIAGE_REPLIE,
              case=CASE_VIDE),
    ],
    # **Aucune TOUCHE sur la ligne d'etat** : elle va a la ligne des
    # raccourcis, jamais ici (regle de sobriete d'Egan du 2026-08-29, tenue par
    # `test_majuscules_des_raccourcis`). La premiere redaction disait « Suppr
    # les retire d'un geste » et la frontiere l'a attrapee -- ce que la
    # relecture n'avait pas fait.
    etat="3 objets cochés · 252 fichiers · 3,5 Go — rien n'est encore retiré",
    raccourcis=("Espace cocher  Suppr retirer  Ctrl+A ajouter  "
                "Ctrl+D déclarer  F1 aide"),
),
    hauteurs_de_message={
        f"{LOT_12P5_V2} · non déclaré": 1,
        # La cle suit la FILIATION validee (`EPIC11-ARB-219`) : l'objet non
        # declare n'est plus une page de scan sous un groupe, c'est un SCAN
        # frere du lot. Le verificateur l'a attrape -- « 0 ligne(s) d'etat ».
        f"{LOT_25}_scan_v2 · non déclaré": 1,
    },
)

# ------- E6-1e : la FILIATION du scan, arbre deplie, DEUX objets par type ----
#
# **`EPIC11-ARB-244`, tranche par Egan le 2026-09-05**, verbatim : « Je change
# d'avis pour le lot B : le scan est le fils du lot qu'il reproduit. Le lot
# scanne est bien le fils du scan. » Il RENVERSE la moitie de
# `EPIC11-ARB-219`, tranche la veille -- « le scan est frere du lot » --, et
# garde l'autre moitie intacte : le lot scanne reste enfant du scan.
#
# Le scan redevient donc un **enfant du lot d'origine**, comme les planches et
# les masters, et il porte le lot scanne comme enfant. Les quatre niveaux
# d'`EPIC11-ARB-210` suffisent a nouveau, et ils logent la filiation entiere :
# rush (0) -> lot (1) -> scan / groupe (2) -> lot scanne / objet (3).
#
# **Ce que ce renversement REPARE, et qui n'etait pas dans la demande** : la
# table de la demonstration (en tete de ce fichier, l. 565 et suivantes) compte
# depuis toujours les scans et le lot scanne DANS le lot -- « 7 objets pour
# plan-04_25 (frames, lot scanne, 2 planches, 1 master, 2 scans) », et
# 259 f. / 4,6 Go qui ne tombent juste qu'a cette condition. La version
# `ARB-219` sortait les scans du lot sans toucher a ces sommes : l'arbre disait
# une chose et la colonne en disait une autre. La filiation d'Egan les
# raccorde.
#
# **Deux de chaque type, et c'est la regle des fabriques du depot appliquee a
# une maquette** : deux lots, deux scans, deux lots scannes, deux planches,
# deux masters. Un seul element de chaque rendrait invisible toute erreur
# d'appariement -- ce que trois campagnes de mutation ont paye dans ce depot.
# Les valeurs sont volontairement DISTINCTES d'un frere a l'autre (cadences,
# rangs de version, profils de master) : une permutation ne se voit pas sur un
# remplissage uniforme.
#
# **Ce que cette maquette montre, et qu'il faut regarder** : la filiation se
# dessine desormais deux fois, par l'arbre ET par le nom. `plan-04_25_scan` et
# `plan-04_25_scan_v2` pendent du lot `plan-04_25` dont ils portent le nom, et
# chacun porte SON lot scanne -- l'appariement que la version `ARB-219`
# laissait au seul libelle. Deux scans et deux lots scannes ne forment plus
# quatre freres sans appariement lisible.
#
# **Le cout, lui, se deplace sur le NOMMAGE et il faut le voir** : au niveau 2,
# le scan est le seul noeud nomme par son NOM propre au milieu de groupes
# nommes par leur TYPE (`frames`, `planches`, `masters`). `EPIC11-ARB-210`
# faisait de ce niveau celui des groupes ; la filiation d'Egan y loge un objet.
# Un groupe `scans` intercalaire le reparerait, au prix d'un cinquieme niveau
# et d'une ligne -- que les 17 lignes de la zone utile n'ont pas.
#
# **La colonne de compte nomme les objets** (`EPIC11-ARB-218`, meme jour) :
# elle dit « 2 lots · 491 f. » la ou elle disait « 491 fichiers ». Le compte
# de fichiers reste, parce que c'est le seul chiffre qui dit ce qu'une
# suppression toucherait vraiment.
#
# **Les deux derniers rushes se replient**, et le second lot aussi : le niveau
# neuf coute des lignes, et un noeud replie dit deja ce qu'il cache par son `+`.

SCAN_25 = f"{LOT_25}_scan"
SCAN_25_V2 = f"{LOT_25}_scan_v2"

ecrire("E6-1e-projet-inventaire-filiation.txt", maquette(
    bandeau_gauche=f"mmu · {PROJET} · Projet",
    bandeau_droite="inventaire · 2 lots · 2 scans",
    centre=[
        # **Aucune ligne vide sur cet ecran, ni en tete ni sous le nom du
        # projet**, contrairement aux quatre autres etats. L'arbre deplie
        # reclame 18 lignes pour 17 disponibles ; le groupe `scans` que demande
        # `EPIC11-ARB-244` en reclame une dix-neuvieme. Les deux blancs sont les
        # deux seules lignes dont le retrait ne coute AUCUNE information, et il
        # a fallu les deux. Mesure, pas preference -- et la marge est desormais
        # nulle : la prochaine ligne demandee sur cet ecran coutera un repli.
        f"  {PROJET}",
        # **Les chiffres de CET ecran ne sont pas ceux de la table de
        # demonstration**, et c'est mesure plutot que subi (`EPIC11-ARB-244`,
        # seconde passe ; Egan, par invite le 2026-09-05, a choisi de corriger
        # plutot que de laisser la contradiction en dette).
        #
        # La table en tete de ce fichier chiffre un lot a UN master, UN scan,
        # UN lot scanne : 5 objets, 259 f., 4,6 Go, et un rush a 491 f. /
        # 8,1 Go. `E6-1e` DOUBLE deliberement chaque type -- c'est sa raison
        # d'etre --, donc ses sommes ne peuvent pas etre celles-la. Elles se
        # recomptent sur son propre arbre :
        #
        #   frames 124 (1,5 Go) + planches 2 (76 Mo) + masters 2 (1,118 Go)
        #   + scans 8 pages (1,1 Go) + lots scannes 124 + 118 (2,9 Go)
        #                                            = 9 objets / 378 f. / 6,7 Go
        #   + plan-04_12p5 67 f. (1,5 Go)            = 445 f. / 8,2 Go
        #
        # **Ce que ca coute, et il faut le savoir en lisant deux ecrans cote a
        # cote** : `E6-1e` est le seul `E6-*` dont les totaux ne se raccordent
        # plus aux huit autres. Le raccord etait faux ici, pas ailleurs -- les
        # huit autres montrent le jeu canonique, celui-ci en montre une
        # variante doublee.
        noeud(0, RUSH, "2 lots · 445 f.", "8,2 Go", pliage=PLIAGE_DEPLIE),
        noeud(1, LOT_25, "9 objets · 378 f.", "6,7 Go", curseur=True,
              pliage=PLIAGE_DEPLIE),
        groupe(GROUPE_FRAMES, "124 frames", "124 f.", "1,5 Go"),
        groupe(GROUPE_PLANCHES, "2 planches", "2 f.", "76 Mo",
               pliage=PLIAGE_DEPLIE),
        objet(planches(LOT_25), "1 f.", "38 Mo"),
        objet(planches(LOT_25, rang=2), "1 f.", "38 Mo"),
        groupe(GROUPE_MASTERS, "2 masters", "2 f.", "1,1 Go",
               pliage=PLIAGE_DEPLIE),
        objet(master(LOT_25), "1 f.", "412 Mo"),
        objet(master(LOT_25, profil="dnxhr_hqx"), "1 f.", "706 Mo"),
        # **Un groupe `scans` porte les deux scans** (`EPIC11-ARB-244`, seconde
        # passe d'Egan) : le scan cesse d'etre le seul noeud nomme par son NOM
        # propre au milieu de groupes nommes par leur TYPE. Le cout annonce a
        # la premiere passe -- un cinquieme niveau et une ligne -- est paye
        # ici, et il est paye par le blanc sous le nom du projet.
        groupe(GROUPE_SCANS, "2 scans", "8 pages", "1,1 Go",
               pliage=PLIAGE_DEPLIE),
        # **`terminal=False` : un scan se PLIE.** Il est au niveau des objets
        # et porte pourtant un enfant ; sans la surcharge il recevrait le `└─`
        # d'une feuille et perdrait sa marque de pliage.
        #
        # **Et son libelle ne dit plus « — 1 lot scanne »** (Egan, verbatim :
        # « on le lit juste en dessous et il ne peut il y avoir qu'un seul lot
        # scanne par scan en principe »). Le cardinal d'enfants se lit dans le
        # nom sur les lignes de GROUPE, ou il dit ce qu'un repli cache ; sur un
        # scan deplie a un seul enfant, il ne fait que redire la ligne suivante.
        noeud(3, SCAN_25, "4 pages", "550 Mo",
              pliage=PLIAGE_DEPLIE, terminal=False),
        noeud(4, f"{GROUPE_LOT_SCANNE} — 124 frames scannées",
              "124 f.", "1,5 Go"),
        noeud(3, SCAN_25_V2, "4 pages", "550 Mo",
              pliage=PLIAGE_DEPLIE, terminal=False),
        noeud(4, f"{GROUPE_LOT_SCANNE} — 118 frames scannées",
              "118 f.", "1,4 Go"),
        noeud(1, LOT_12P5, "5 objets · 67 f.", "1,5 Go",
              pliage=PLIAGE_REPLIE),
        noeud(0, RUSH_HIVER, "1 lot · 99 f.", "1,3 Go", pliage=PLIAGE_REPLIE),
    ],
    etat="1 rush déplié · 2 lots · 2 scans · 2 lots scannés · 8,2 Go",
    raccourcis=("Espace cocher  Suppr retirer  Ctrl+A ajouter  "
                "Ctrl+D déclarer  F1 aide"),
))


# ------------------- E6-1a : la LECTURE du disque, et son seul signe honnete -
#
# **`EPIC11-ARB-207`.** Egan, verbatim : « Pas génant d'attendre quelques
# secondes si une icone de chargement dynamique (roue en rotation stylisée)
# tourne. C'est une condition importante sur ce type d'interfaces. »
#
# **Le rotor, et pas une barre.** `DESIGN.md` §9 interdit « une animation qui
# tourne a la place d'un compte reel » ; l'interdit ne mord pas ici, parce
# qu'aucun compte reel n'existe : `inventorier_le_projet` bâtit son arbre puis
# rend, sans jalon intermediaire. Le rotor est alors le seul signe honnete que
# la machine travaille -- exactement le cas que `jetons.ROTOR` documente.
#
# **Ce que ca coute, mesure plutot que suppose** (mesure du 2026-09-03,
# section 2) : ~12 µs par fichier, soit 181 ms a 15 000 fichiers sur un disque
# local. Autrement dit cet ecran ne se verra PAS sur la demonstration, et se
# verra sur un volume reseau ou un projet de plusieurs dizaines de milliers de
# fichiers. C'est ce qui le rend necessaire sans le rendre frequent.
#
# **La ligne de raccourcis ne porte pas d'annulation**, pour le meme motif que
# `E6-2c` : aucun point d'interruption n'existe dans ce chemin. Une touche
# annoncee qui n'agit pas est le finding `I8`.
#
# **Le titre est le seul nom du projet** (Egan, 2026-09-04, note 1) : « Au lieu
# de "ce que projet_demo contien" mettre juste le nom du projet ». Sa note est
# posee ICI, sur l'ecran de lecture -- et elle est appliquee aussi a `E6-1`,
# `E6-1c` et `E6-1d`, qui sont le MEME ecran a d'autres moments. Deux titres
# pour un seul ecran feraient changer la ligne sous ses yeux a la seconde ou la
# lecture s'acheve, ce qui est le contraire de ce qu'il demande.

ecrire("E6-1a-projet-inventaire-lecture.txt", maquette(
    bandeau_gauche=f"mmu · {PROJET} · Projet",
    bandeau_droite="inventaire · lecture en cours",
    centre=[
        "",
        f"  {PROJET}",
        "",
        f"     {jetons.ROTOR[0]}  lecture du disque",
        "",
        regle(),
        "",
        "     Le manifeste est lu, puis le disque est parcouru : c'est",
        "     l'écart entre les deux qui fait l'intérêt de cet écran, et il",
        "     ne se mesure pas sans les deux.",
        "",
        "     Sur un projet local la lecture est immédiate. Elle se voit sur",
        "     un volume réseau, ou sur plusieurs dizaines de milliers de",
        "     fichiers.",
    ],
    etat="lecture en cours — aucune écriture, aucun décompte disponible",
    raccourcis="F1 aide",
))

# ---------------------- E6-1c : l'arbre qui DEFILE, sur un projet reel ------
#
# **`EPIC11-ARB-205`.** Egan, verbatim : « Oui ! » -- a « Ce qui se passe quand
# l'arbre ne tient plus dans l'écran. Le projet de démonstration a trois
# rushes ; le tien en aura trente. »
#
# **La demonstration change donc de taille, et c'est deliberé** : trois rushes
# ne debordent pas, et un etat de defilement dessine sur une liste qui tient ne
# mesure rien. Ce projet-ci en porte trente.
#
# **L'idiome est celui de `X4`, repris et non reinvente** : un `…` en tete et un
# `…` en pied, le second portant la fenetre (« 11-17 sur 30 »), et la ligne
# d'etat qui dit ce qui reste des deux cotes. Un second dessin du meme etat
# divergerait du premier au premier ajustement -- c'est la meme raison qui fait
# que `noeud()` vit ici et pas dans chaque ecran.
#
# **Le rush deplie est au MILIEU de la fenetre, pas a son bord**, et ce n'est
# pas un hasard de mise en page : un defilement qui recadrerait toujours sur le
# premier ou le dernier element visible se demasque exactement la (regle des
# fabriques, point 2). La marque de pliage est donc lisible dans ses deux etats
# sur le meme ecran.

#: Les trente rushes du projet qui DEBORDE. Les noms sont numerotes pour que la
#: fenetre visible se lise d'un coup d'oeil -- « 11-17 sur 30 » se verifie sur
#: le dessin -- et ils portent des cardinaux differents, jamais un remplissage
#: uniforme : une fenetre qui glisserait d'un rang ne se verrait pas sur trente
#: lignes identiques.
RUSHES_DU_GROS_PROJET = 30

ecrire("E6-1c-projet-inventaire-defilement.txt", maquette(
    bandeau_gauche="mmu · tournage_2026 · Projet",
    bandeau_droite="inventaire · 14 812 fichiers · 214 Go",
    centre=[
        "",
        "  tournage_2026",
        "",
        elision(),
        noeud(0, "plan-11_nuit_ext", "1 lot · 412 f.", "6,8 Go",
              pliage=PLIAGE_REPLIE, case=CASE_VIDE),
        noeud(0, "plan-12_nuit_int", "1 lot · 198 f.", "3,1 Go",
              pliage=PLIAGE_REPLIE, case=CASE_VIDE),
        noeud(0, "plan-13_coupe", "3 lots · 1 204 f.", "18,7 Go",
              pliage=PLIAGE_DEPLIE, case=CASE_VIDE),
        noeud(1, "plan-13_coupe_25", "5 objets · 702 f.", "11,2 Go",
              pliage=PLIAGE_REPLIE, case=CASE_VIDE),
        noeud(1, "plan-13_coupe_12p5", "5 objets · 502 f.", "7,5 Go",
              curseur=True, pliage=PLIAGE_REPLIE, case=CASE_VIDE),
        noeud(1, f"{RESERVE} plan-13_coupe_12p5_v2 · non déclaré",
              "3 objets · 348 f.", "5,2 Go", pliage=PLIAGE_REPLIE,
              case=CASE_VIDE),
        noeud(0, "plan-14_raccords", "1 lot · 96 f.", "1,4 Go",
              pliage=PLIAGE_REPLIE, case=CASE_VIDE),
        noeud(0, "plan-15_sons_seuls", "0 lot", NEUTRE, case=CASE_VIDE),
        noeud(0, "plan-16_timelapse", "4 lots · 2 118 f.", "31,4 Go",
              pliage=PLIAGE_REPLIE, case=CASE_VIDE),
        noeud(0, "plan-17_essais_pellicule", "1 lot · 84 f.", "1,2 Go",
              pliage=PLIAGE_REPLIE, case=CASE_VIDE),
        elision("11-17 sur 30"),
    ],
    etat=(f"{RUSHES_DU_GROS_PROJET} rushes · 10 au-dessus, 13 en dessous · "
          "14 812 fichiers · 214 Go"),
    raccourcis=("Espace cocher  Suppr retirer  Ctrl+A ajouter  "
                "Ctrl+D déclarer  F1 aide"),
),
    hauteurs_de_message={"plan-13_coupe_12p5_v2 · non déclaré": 1},
)

# ---- E6-1b : RETIREE le 2026-09-04, fondue dans E6-1 (EPIC11-ARB-217) -----
#
# Egan, note 6 de la planche v3, verbatim : « Il n'est pas tres utile au
# demeurant », puis l'arbitrage : fondre dans `E6-1`. L'ecran portait deux
# familles d'ecarts, et elles ne sont pas symetriques :
#
# * les PRESENTS NON DECLARES etaient deja dans l'arbre (`▲ … · non déclaré`),
#   donc cette famille ne perd rien ;
# * les DECLARES ABSENTS n'y etaient que par leur croix. Ce que `E6-1b` disait
#   de plus -- le CHEMIN ATTENDU -- vit desormais dans la ligne d'etat de
#   `E6-1` quand le curseur porte l'objet, et c'est ce que `E6-1` dessine.
#
# Sans ce report, `Ctrl+D declarer` (`EPIC11-ARB-215`) n'aurait plus de cible
# visible : on declarerait absent un objet qu'aucun ecran ne nomme.

# ------------------------------------ E6-2 : la confirmation chiffree -------

# **Trois arbitrages d'Egan du 2026-09-03 refont cet ecran, et le refont dans
# le meme sens : la filiation cesse d'etre un CHOIX pour devenir une
# CONSEQUENCE du niveau ou `Suppr` a ete lance.**
#
# * `EPIC11-ARB-199` -- la ligne « aucun suivi par git · IRRÉCUPÉRABLES » part
#   avec la logique qui la nourrissait. Verbatim : « Le suivi par git n'est pas
#   un sujet [...] Il faut supprimer cette ligne ET cette logique du coeur. »
#   Le mot lui-meme survit **sur l'issue**, la ou une decision se prend, et
#   nulle part ailleurs : une suppression reste definitive, elle ne l'est
#   simplement plus PARCE QUE git ne suit pas ;
# * `EPIC11-ARB-203` -- « On retire "reste en place" et "scans liés" car ils
#   seraient emportés par défaut selon le niveau où Suppr est lancé. » Les
#   issues deviennent : Supprimer / Supprimer et libérer les rangs / Annuler ;
# * consequence chiffree, et elle FERME un ecart que personne n'avait releve :
#   avec les scans emportes par defaut, le panneau annonce **67 fichiers et
#   1,5 Go** -- exactement ce que la ligne du lot porte dans `E6-1`. L'ancienne
#   redaction en annoncait 63 et 976 Mo, c'est-a-dire que l'ecran de
#   confirmation et l'ecran d'inventaire ne disaient pas la meme chose du meme
#   lot. Les sommes de la demonstration retombent desormais juste d'un ecran a
#   l'autre, ce que la note de tete de cette section exige.
#
# Le RANG s'affiche en colonne, comme Egan le suggere : « il n'y a pas que le
# lot qui en porte un, les planches, les scans etc peuvent porter un rang et il
# faudrait peut-être qu'un affichage en colonnes le rappelle ? »

ecrire("E6-2-projet-suppression-confirmation.txt", maquette(
    bandeau_gauche=f"mmu · {PROJET} · Projet",
    bandeau_droite=f"suppression · {LOT_12P5}",
    centre=[
        "",
        *cartouche(f"À supprimer — tout le lot {LOT_12P5}", [
            chiffre("Élément", f"lot {LOT_12P5}"),
            chiffre("Fichiers", "67"),
            chiffre("Poids libéré", "1,5 Go"),
            "",
            chiffre("Emportés avec le lot", "4 groupes d'objets"),
            filiation(f"{FRAMES}/{LOT_12P5}/", "62 fichiers · 770 Mo"),
            filiation(master(LOT_12P5), "1 fichier · 206 Mo"),
            filiation(f"{SCANS}/{LOT_12P5}/", "4 fichiers · 550 Mo"),
            filiation(f"{ABSENT} {planches(LOT_12P5)}", "déclarée, absente"),
            chiffre("Rangs portés", "lot v2 · scans v1 · planches v1"),
        ]),
        "",
        issue("Supprimer", f"{RESERVE} 67 fichiers, définitif"),
        issue("Supprimer et libérer les rangs",
              f"{RESERVE} le prochain lot reprendrait le v2"),
        issue("Annuler", "rien n'est touché", curseur=True),
    ],
    etat="67 fichiers · 1,5 Go · 4 groupes — rien n'a encore été écrit",
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
))

# ------------------- E6-2b : le dernier lot, et le panneau DIT pourquoi -----

# **`EPIC11-ARB-202` desamorce cet ecran, et c'est Egan qui le desamorce.**
# A la question « Le dernier lot d'un rush merite-t-il vraiment un second
# accord ? » il repond « Non », puis : « La logique est plus simple pour moi :
# supprimer le dernier lot d'un rush ne pose pas de difficulte particuliere.
# Puisqu'on peut maintenant declarer un rushe seul on aura qu'a generer un lot
# avec l'extraction. On peut simplement proposer au passage de supprimer le
# rushe en meme temps car c'est plus pratique. Pas la peine de sonner 1000
# alarmes. Quand on supprime on sait ce qu'on fait. »
#
# Ce qui part : le « second consentement, distinct », le paragraphe de trois
# lignes qui expliquait la cascade, et le `▲` de la ligne d'etat. Ce qui reste
# : le FAIT, en une ligne -- le rush restera sans lot --, parce qu'il reste
# vrai et qu'il informe le choix, et la commodite qu'Egan demande, qui est de
# pouvoir emporter le rush du meme geste.
#
# **Ce n'est pas une simplification de confort.** Un ecran qui sonne l'alarme
# sur un cas ordinaire apprend a passer outre les alarmes -- c'est le meme
# defaut que « une demonstration dont les sommes ne tombent pas juste apprend a
# ne pas lire les chiffres », en haut de cette section.

ecrire("E6-2b-projet-suppression-dernier-lot.txt", maquette(
    bandeau_gauche=f"mmu · {PROJET} · Projet",
    bandeau_droite=f"suppression · {LOT_HIVER}",
    centre=[
        "",
        *cartouche(f"À supprimer — tout le lot {LOT_HIVER}", [
            chiffre("Élément", f"lot {LOT_HIVER}"),
            chiffre("Fichiers", "99"),
            chiffre("Poids libéré", "1,3 Go"),
            "",
            chiffre("Emportés avec le lot", "2 groupes d'objets"),
            filiation(f"{FRAMES}/{LOT_HIVER}/", "96 fichiers · 1,2 Go"),
            filiation(f"{PATCHES}/ · 3 planches", "3 fichiers · 92 Mo"),
            filiation(f"{ABSENT} {master(LOT_HIVER)}", "déclaré, absent"),
            "",
            f"Dernier lot du rush {RUSH_HIVER} : le rush restera déclaré "
            "sans lot.",
        ]),
        "",
        issue("Supprimer le lot", f"{RESERVE} 99 fichiers, 1,3 Go",
              largeur=38),
        issue(f"Supprimer le lot et le rush {RUSH_HIVER}",
              f"{RESERVE} + l'entrée du rush", largeur=38),
        issue("Annuler", "rien n'est touché", curseur=True, largeur=38),
    ],
    etat=("dernier lot du rush hiver · 99 fichiers · 1,3 Go — "
          "rien n'a été écrit"),
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
))

# ------------------- E6-2c : ce que l'outil sait VRAIMENT rendre en cours ---
#
# **Cet ecran est redessine a la baisse, sur une mesure, et sur la demande
# d'Egan.** Verbatim : « L'outil sait faire ça ? Se contenter des lignes qui
# existent vraiment en sortie. » La reponse est NON, et elle est chiffree dans
# `mesure-2026-09-03-reponses-aux-questions-d-egan-ecran-projet.md`, section 4.
#
# `remove_project_element` est un appel BLOQUANT : il rend un seul objet, une
# fois tout termine. Le module ne porte ni `rappel_progression` -- ses cinq
# voisins du coeur l'ont, lui non --, ni `logging`, ni aucun point de controle.
# L'ancien dessin promettait SIX choses dont aucune n'existe : « objet 2 sur
# 3 », les trois etats fait / en cours / en attente, le journal horodate, la
# barre a 33 %, le « reste ~ 9 s », et `Échap interrompre`.
#
# **Ce qui reste est le seul signe honnete**, et c'est Egan lui-meme qui l'a
# autorise ailleurs (`EPIC11-ARB-207`, sur le parcours du disque) : « une icône
# de chargement dynamique (roue en rotation stylisée) [...] C'est une condition
# importante sur ce type d'interfaces. » Le rotor de `jetons.ROTOR` est fait
# pour exactement ce cas -- `DESIGN.md` §9 interdit « une animation qui tourne a
# la place d'un compte reel », et il n'y a ici AUCUN compte reel a remplacer.
#
# **Ce qu'il faudrait pour rendre l'ancien dessin**, chiffre plutot que tu : les
# deux chemins construisent leur liste de `Path` AVANT de supprimer, puis
# bouclent dessus. Un jalon `(faites, total)` pose dans cette boucle est un
# ajout local -- mais son unite serait le FICHIER, pas l'« objet », granularite
# que le coeur ne connait pas. C'est une story, pas une retouche de maquette.
#
# **`Échap interrompre` part avec le reste**, et c'est le retrait le plus dur :
# il n'y a aucun point d'interruption entre le debut et la fin. Une touche
# annoncee qui n'agit pas est le finding `I8` a l'etat pur -- mieux vaut ne rien
# promettre que promettre une sortie qui n'existe pas.

# **Et le pied de cet ecran part a son tour** (Egan, 2026-09-04, note 6) :
# « Enlever les informations de justification en bas. C'est de la tuyauterie ! »
# Les six lignes retirees expliquaient POURQUOI le manifeste part avant les
# fichiers et pourquoi aucun decompte n'existe. Elles disaient vrai, et c'est
# precisement ce qui les condamne : elles expliquaient a l'operateur une
# contrainte d'implementation dont il n'a rien a faire pendant qu'il attend.
# Le motif reste ecrit -- ici, dans ce commentaire, qui est sa place.
#
# Le filet part avec elles : un filet de section qui ne separe plus rien est un
# trait qui promet un contenu absent.

ecrire("E6-2c-projet-suppression-execution.txt", maquette(
    bandeau_gauche=f"mmu · {PROJET} · Projet",
    bandeau_droite=f"suppression · {LOT_12P5}",
    centre=[
        "",
        "  Suppression en cours",
        "",
        f"     {jetons.ROTOR[0]}  tout le lot {LOT_12P5} — 67 fichiers, 1,5 Go",
    ],
    etat="67 fichiers · 1,5 Go — écriture en cours",
    raccourcis="F1 aide",
))

# ---------------- E6-3 : le resultat, et le cas qui n'est PAS un succes -----

ecrire("E6-3-projet-suppression-resultat.txt", maquette(
    bandeau_gauche=f"mmu · {PROJET} · Projet",
    bandeau_droite=f"suppression · {LOT_12P5}",
    centre=[
        "",
        *cartouche("Suppression INCOMPLÈTE", [
            f"{ABSENT} 3 fichiers occupent toujours le disque",
            "",
            chiffre("Manifeste", "à jour · l'entrée du lot est retirée"),
            # **Les cardinaux suivent `EPIC11-ARB-203`** : le lot emporte ses
            # scans par defaut, donc le total est 67 et non 63. 64 + 3 = 67, et
            # 1,3 Go + 231 Mo = 1,5 Go -- les memes chiffres que `E6-1` et
            # `E6-2` portent pour ce lot. Une demonstration dont les sommes ne
            # tombent pas juste apprend a ne pas lire les chiffres.
            chiffre("Supprimés", "64 fichiers · 1,3 Go"),
            chiffre("Restés", "3 fichiers · 231 Mo"),
            "",
            f"  {master(LOT_12P5)}",
            f"  {FRAMES}/{LOT_12P5}/{frame(RUSH, 12.5, '00:00:04:12')}",
            f"  {FRAMES}/{LOT_12P5}/{frame(RUSH, 12.5, '00:00:04:14')}",
            chiffre("Motif", "droits refusés ou fichier verrouillé"),
        ]),
        "",
        # **« Juste "Réessayer" »** (Egan, note 7 de la planche v3, verbatim).
        # Le cardinal et l'objet du reessai sont deja dits DEUX fois
        # au-dessus -- « ✕ 3 fichiers occupent toujours le disque » en tete du
        # cartouche, et la ligne « Restés  3 fichiers · 231 Mo ». Une issue
        # les redisait une troisieme fois.
        issue("Réessayer", "", curseur=True,
              largeur=40),
        issue("Ouvrir le dossier", "", largeur=40),
        issue("Retour à l'inventaire", "", largeur=40),
    ],
    etat=("✕  3 fichiers n'ont pas pu être supprimés · manifeste à jour · "
          "64 retirés"),
    raccourcis="⏎ choisir  ↑↓ naviguer  Échap inventaire  F1 aide",
))

# ------------- E6-3b : le resultat quand la suppression a ABOUTI ------------

# **Dessine le 2026-09-05, sur demande d'Egan** (« Maquette a dessiner depuis le
# meme modele que les autres ecrans de reussite », puis « Il faut qu'elle soit
# conforme aux autres maquettes d'ecrans de reussite »).
#
# Elle FERME l'ecart que la story 11.11 portait a son registre : `E6-3` ne
# dessine que l'incomplete, si bien que le chemin nominal -- celui que
# l'operateur verra presque toujours -- n'avait aucune maquette, et
# `EPIC11-ARB-144` interdit de coder un ecran qui n'en a pas. Le parcours
# remontait donc a l'inventaire sans rien dire, et **le poids libere n'etait
# annonce nulle part** : c'est le seul endroit du produit qui puisse le
# confirmer APRES l'ecriture, la confirmation ne pouvant que le promettre.
#
# **Ce qu'elle reprend du modele commun** (`E2-5`, `E3-8`, `E4-5`, `E5-5`) :
# cartouche a titre d'action accomplie, la ligne de l'objet en tete avec le
# glyphe PLEIN, les lignes chiffrees ensuite, les suites en dessous dont la
# derniere est un retour, et une ligne d'etat a glyphe plein qui resume. Le
# titre dit `Supprimé` la ou les autres disent `Écrit` : c'est le meme role --
# nommer ce qui vient d'avoir lieu --, et `Écrit` serait faux ici, seul le
# manifeste ayant ete ecrit.
#
# **Les chiffres sont ceux de `E6-2`, groupe pour groupe**, et c'est
# volontairement la demonstration la plus forte : la confirmation promettait
# 67 fichiers, 1,5 Go et quatre groupes ; le resultat rend les memes. Une
# demonstration dont les sommes ne tombent pas juste apprend a ne pas lire les
# chiffres -- 62 + 1 + 4 = 67, et 770 + 206 + 550 = 1 526 Mo.
#
# **La ligne « Rang libere » n'est pas inconditionnelle** : elle ne parait que
# si l'operateur a retenu l'issue « Supprimer et liberer les rangs »
# (`EPIC11-ARB-92`, point 3 -- un rang se consomme et ne se rend que sur
# demande). La maquette montre ce cas parce que c'est le plus riche ; sans lui
# la ligne tombe, et rien d'autre ne bouge.
#
# **La quatrieme filiation porte le glyphe d'ABSENCE dans un ecran de
# reussite**, et ce n'est pas une contradiction : la planche etait declaree et
# deja absente du disque avant la suppression. Rien n'a donc ete efface pour
# elle -- seule son entree de manifeste l'a ete --, et le taire ferait croire
# qu'un fichier de plus est parti.

ecrire("E6-3b-projet-suppression-reussie.txt", maquette(
    bandeau_gauche=f"mmu · {PROJET} · Projet",
    bandeau_droite=f"suppression · {LOT_12P5}",
    centre=[
        "",
        *cartouche("Supprimé", [
            f"{COMPLET} tout le lot {LOT_12P5}",
            "",
            chiffre("Supprimés", "67 fichiers · 1,5 Go libérés"),
            chiffre("Manifeste", "à jour · l'entrée du lot est retirée"),
            chiffre("Rang libéré", "lot v2 · le prochain lot le reprendra"),
            "",
            filiation(f"{FRAMES}/{LOT_12P5}/", "62 fichiers · 770 Mo"),
            filiation(master(LOT_12P5), "1 fichier · 206 Mo"),
            filiation(f"{SCANS}/{LOT_12P5}/", "4 fichiers · 550 Mo"),
            filiation(f"{ABSENT} {planches(LOT_12P5)}",
                      "absente · entrée retirée"),
        ]),
        "",
        # **DEUX suites, et c'est un choix mesure contre le modele.** `E2-5`,
        # `E3-8` et `E5-5` en portent quatre parce qu'ils ont un atelier
        # SUIVANT a proposer -- « le lien avec l'atelier suivant », qu'Egan a
        # nomme comme ce qu'il aimait de `E2-5`. Une suppression n'en a aucun.
        #
        # Et « Supprimer un autre element » a ete ECRIT puis RETIRE : dans
        # cette TUI, revenir a l'inventaire EST la facon d'en supprimer un
        # autre, si bien que les deux entrees auraient declenche exactement le
        # meme geste. Deux suites qui font la meme chose sont pires qu'une
        # seule : elles font croire qu'elles different.
        #
        # « Reessayer » n'a pas sa place ici non plus -- il n'y a rien a
        # reprendre --, et c'est ce qui distingue cet ecran de `E6-3`.
        issue("Ouvrir le dossier du projet", "", curseur=True, largeur=40),
        issue("Retour à l'inventaire", "", largeur=40),
    ],
    etat=(f"{COMPLET}  67 fichiers supprimés · 1,5 Go libérés · "
          "manifeste à jour · rang v2 rendu"),
    raccourcis="⏎ choisir  ↑↓ naviguer  Échap inventaire  F1 aide",
),
    # **Le glyphe de tete du cartouche est DECLARE** (`EPIC11-ARB-71`). Pose
    # dans un cartouche, il est precede de la bordure et d'UN seul blanc : il
    # n'ouvre donc pas de colonne, et `jetons.jeton_d_etat` ne le voit pas. Le
    # verificateur l'a attrape -- « glyphe d'etat "complete" qu'AUCUN repli par
    # motif ne peut voir » --, ce qu'une relecture n'aurait pas fait. Le laisser
    # deviner rendrait un `Supprime` en vert sur la maquette et en gris dans le
    # produit, ce qui est la divergence meme que ce mecanisme ferme.
    hauteurs_de_message={f"tout le lot {LOT_12P5}": 1},
)


print("zone A : ok")
