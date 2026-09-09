# -*- coding: utf-8 -*-
"""Maquettes zone B : atelier Scan (les deux temps) et ecrans transverses d'execution."""
from construire_maquette import maquette, barre, cartouche, regle, ecrire

# `E3-0` -- le menu de l'atelier, a DEUX entrees depuis le 2026-08-31.
#
# La troisieme, « Recalibrer un lot ecrit », est RETIREE sur arbitrage d'Egan
# (`EPIC11-ARB-101`, note 2), et le motif est une mesure et non un gout :
# `cli.apply_calibration` est un TALON DU POC -- `print("[TODO] Appliquer
# calibration depuis: ...")`, `cli.py:222`. Rien dans le depot n'applique un
# profil a des frames DEJA ECRITES ; `color_pipeline.apply_active_calibration`
# applique un profil a une image PENDANT l'ecriture, ce qui est autre chose.
#
# L'entree promettait donc une capacite que le coeur n'a jamais eue. Ce n'etait
# pas « son ecran arrive avec le temps 2 » : il n'y a pas de commande derriere.
# Egan, qui l'a vu en relisant la planche : « peut-on vraiment recalibrer un lot
# deja ecrit ? Je ne savais pas qu'on pouvait le faire ?! » -- non, en effet.
#
# Elle reviendra le jour ou une story de coeur livrera la commande.
ecrire("E3-0-scan-menu.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan",
    bandeau_droite="1 profil · 2 lots reconstruits",
    centre=[
        "",
        "  Atelier Scan",
        "",
        "   ▸ Détecter des planches      Déposer des scans, lire les QR, puis",
        "                                écrire les TIFF. Le parcours principal.",
        "",
        "     Calibrer une chaîne        Depuis le scan d'une page de calibration,",
        "                                produire le profil couleur du scanner.",
        "",
        regle(),
        "",
        "     Profil par défaut du projet   hp-envy-4520-tiff-600",
    ],
    etat="",
    raccourcis="⏎ entrer  ↑↓ naviguer  Échap ateliers  F1 aide  Q quitter",
),
    # **L'entree du curseur tient sur DEUX lignes, et on le DECLARE**
    # (`EPIC11-ARB-125`). La seconde ne porte aucun glyphe : aucune
    # reconnaissance par motif ne peut la trouver, et elle restait blanche.
    # Egan, sur la planche du 2026-08-31 : « pas la seconde ligne de
    # description ». Le generateur est le seul a le savoir -- il vient
    # d'ecrire les deux lignes, dix lignes plus haut.
    hauteur_du_curseur=2,
)

# `E3-1` -- l'ecran tel qu'on le TROUVE : les deux champs vides et requis.
#
# Trois corrections du 2026-08-30, chacune sur un arbitrage POSTERIEUR au dessin
# du 2026-08-27 :
#
# * `EPIC11-ARB-48` -- la zone de completion `Tab` qui tenait ici trois lignes
#   est RETIREE. La completion n'existe plus nulle part : l'explorateur l'a
#   remplacee sur les cinq sites qui demandent un chemin, et `E3-1` est
#   nommement l'un des cinq. La designation de la source se fait donc sur `X6`,
#   deja dessine et deja valide -- son bandeau porte d'ailleurs
#   « Scan · temps 1 sur 2 », c'est bien cet ecran-ci ;
# * `EPIC11-ARB-38` -- le champ de resolution etait PREREMPLI a 600. Il est
#   vide et marque requis : « elle n'est pas preremplie. Le champ reste requis,
#   et vide ». La mesure du coeur s'offre en `E3-1b`, une fois la source connue
#   -- avant elle, il n'y a rien a mesurer ;
# * `EPIC11-ARB-56` -- la ligne d'etat nommait DEUX touches (`Tab`, `↓`). Elle
#   ne porte plus qu'une mesure ; sans source, il n'y a rien a mesurer, donc
#   elle est VIDE, ce que `DESIGN.md` §3 demande explicitement.
# **`E3-1` montre desormais la QUATRIEME forme de source** (story 11.5, lot E
# bis, 2026-08-31), et l'ecran qu'elle dessinait jusque-la -- les deux champs
# vides, « rien encore » -- n'a plus de maquette. C'est un choix, il se paie, et
# il est dit plutot que tu :
#
# * ce que la maquette GAGNE : la seule forme d'entree du coeur qui n'avait
#   aucun dessin. `EPIC7-ARB-88` en compte quatre -- dossier, PDF, image seule,
#   **sequence de chemins** --, et la quatrieme etait injoignable depuis la TUI
#   jusqu'a ce que la 11.2c livre `selection_multiple` (sa ligne de sprint :
#   « elle debloque la QUATRIEME forme de source de `scan` »). Le rendu est
#   celui d'Egan, note 5 du 2026-08-31 (`EPIC11-ARB-101`), verbatim : « si
#   fichiers multiples on dit **sources multiples**, en dessous la liste
#   navigable » ;
# * ce que la maquette PERD : l'etat d'arrivee, seul porteur de
#   `LIBELLE_RIEN_ENCORE` et de `RACCOURCIS_DEPOT_SANS_SOURCE`. Les trois ecarts
#   corriges le 2026-08-30 restent tous visibles ailleurs -- le champ de dpi
#   VIDE et requis (`EPIC11-ARB-38`) l'est ici comme sur `E3-1b`, la zone de
#   completion `Tab` (`EPIC11-ARB-48`) est absente des deux, et la ligne d'etat
#   ne porte plus de touche (`EPIC11-ARB-56`) mais une mesure. **Si Egan veut
#   garder l'etat d'arrivee, il prend un nom a lui** (`E3-1c`) plutot que de
#   reprendre celui-ci : c'est une maquette de plus, pas un arbitrage.
#
# Trois points du dessin sont des MESURES du produit et non des choix de
# dessinateur -- ils sont recopies de `EcranScanDepot.lignes_du_formulaire`
# rendu a 80 colonnes, pas composes a la main :
#
# * `sources multiples` est ecrit DEUX fois -- au champ et en tete du resume --
#   d'une seule redaction (`LIBELLE_SOURCES_MULTIPLES`) ;
# * la liste ne montre que quatre sources sur huit et le dit : `…  1-4 sur 8`,
#   la ligne de position de l'explorateur, parce que le defilement est le sien
#   (`jetons.fenetre_de_liste`) et non un second ;
# * la ligne de raccourcis annonce `↑↓ sources` **parce que la liste deborde**.
#   Sur trois sources elle ne l'annonce pas : une touche inerte annoncee est
#   indistinguable d'un clavier casse.
ecrire("E3-1-scan-depot.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan",
    bandeau_droite="temps 1 sur 2 · détecter",
    centre=[
        "",
        "  Que faut-il détecter ?",
        "",
        "     Source               sources multiples",
        "",
        "     Résolution de scan > ·                                requis · dpi",
        "",
        regle("Ce qui sera lu"),
        "",
        "     sources multiples · 8 fichiers · 635 Mo",
        "",
        "     planche_01.tiff                                              78 Mo",
        "     planche_03.tiff                                              78 Mo",
        "     planche_04.tiff                                              81 Mo",
        "     planche_07.tiff                                              79 Mo",
        "     …                                                        1-4 sur 8",
    ],
    etat="✕  résolution de scan requise — la détection ne peut pas partir",
    raccourcis="⏎ détecter  ↑↓ sources  Tab champ  Échap ateliers  F1 aide  Q quitter",
))

# `E3-1b` -- la source est designee, la mesure du coeur arrive. Trois
# corrections du 2026-08-30 :
#
# * `EPIC11-ARB-38`, DEUX FOIS sur le meme ecran. Le champ portait `600` ET
#   l'offre de reprendre 600 : l'ecran proposait de reprendre la valeur qu'il
#   avait deja posee. Le champ est VIDE et requis ; la mesure est AFFICHEE a
#   cote, jamais substituee -- « un scanner en auto-fit ecrit une resolution qui
#   ne correspond pas a l'echelle reelle de la page » ;
# * `EPIC11-ARB-68` -- la reprise etait offerte sur la lettre `m`, a cote d'un
#   champ de saisie, ou « aucune lettre n'est un raccourci [...] sans exception
#   et sans ordre de priorite a maintenir ». C'est le defaut du `r` d'`E2-3b`,
#   sous une autre forme. La reprise devient une LIGNE du formulaire, atteinte
#   par `Tab` et prise par `⏎` : zero ressaisie, et un ACTE de l'operateur, ce
#   qu'`ARB-38` demande. Meme forme que « Reprendre a 425 dpi » que l'arbitrage
#   pose deja sur l'ecran de refus. -- A CONFIRMER PAR EGAN (question Q3) ;
# * `EPIC11-ARB-56` -- la ligne d'etat portait un MOTIF DE CONCEPTION (« la
#   detection n'ecrit aucune frame : elle produit un document de detection »).
#   Elle porte la mesure de l'ecran. L'invariant, lui, reste dit -- dans le
#   TITRE de `E3-2`, ou il est vrai au moment ou il compte.
ecrire("E3-1b-scan-depot-fichier-unique.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan",
    bandeau_droite="temps 1 sur 2 · détecter",
    centre=[
        "",
        "  Que faut-il détecter ?",
        "",
        "     Source               D:\\HOKO\\scans\\planches_lot25.pdf",
        "",
        "     Résolution de scan > ·                                requis · dpi",
        "     Reprendre la mesure  600 dpi       les 8 pages déclarent 600 dpi",
        "",
        regle("Ce qui sera lu"),
        "",
        "     1 PDF · 8 pages · 1,2 Go",
        # **Le resume COMPTE, il n'ENUMERE pas** (`EPIC11-ARB-101`, note 6,
        # verbatim d'Egan sur cet ecran-ci -- « Ecran 4 · La source est
        # designee ») : « Pas la peine de lister toutes les pages. Juste de les
        # compter suffit non ? En ligne c'est illisible au dela d'un certain
        # nombre en plus. » La ligne `page 1 ... page 8` etait exactement cette
        # enumeration, et elle ne tenait que parce que la fixture n'a que huit
        # pages : a 24 pages elle depasse les 76 colonnes utiles de la grille.
        #
        # Ce que la note ne retire PAS : le compte lui-meme, ni son vocabulaire.
        # `EPIC11-ARB-26` exige « pages » pour un PDF et « fichiers » pour un
        # dossier -- c'est le VOCABULAIRE qu'il exige, pas l'enumeration, et la
        # ligne de resume ci-dessus le porte deja.
    ],
    etat="✕  résolution de scan requise — la détection ne peut pas partir",
    raccourcis="⏎ détecter  Tab champ  Échap ateliers  F1 aide  Q quitter",
))

ecrire("E3-2-scan-detection-en-cours.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan",
    bandeau_droite="temps 1 sur 2 · détecter",
    centre=[
        "",
        "  Détection en cours — aucune frame n'est écrite",
        "",
        regle("Journal"),
        "",
        "     15:02:11  planche_01.tiff : 4 marqueurs ArUco, QR décodé",
        "     15:02:11    → lot_25fps, page 1/8, 8 emplacements",
        "     15:02:13  planche_02.tiff : 4 marqueurs ArUco, QR décodé",
        "     15:02:13    → lot_25fps, page 2/8, 8 emplacements",
        "     15:02:15  planche_03.tiff : 4 marqueurs ArUco, QR ✕ non décodé",
        "     15:02:15    → non rattaché, reste en attente de lecture",
        "     15:02:17  planche_04.tiff : 4 marqueurs ArUco, QR décodé",
    ],
    etat=barre(14, 24, "pages", "26 s"),
    raccourcis="Tab journal  Échap interrompre  F1 aide",
))

# `E3-3` -- TROIS suites, et non quatre, depuis le 2026-08-31.
#
# « Voir le detail d'un lot » est RETIREE (`EPIC11-ARB-101`, note 9, verbatim
# d'Egan : « Que se passe-t-il quand on regarde le detail d'un lot ? **Si rien
# n'existe on retire cette option.** »). La mesure qui tranche : les maquettes
# du temps 1 sont `E3-0`, `E3-1`, `E3-1b`, `E3-2`, `E3-3`, `E3-4`, `E3-4b` --
# aucun ecran de detail de lot n'existe, ni dessine ni ecrit. Une suite qui ne
# mene nulle part est la meme dette a l'ecran que l'entree « Recalibrer un lot
# ecrit » retiree d'`E3-0` par la note 2, et elle se paie de la meme facon.
#
# **C'est la MAQUETTE qui etait perimee, pas le code** : le lot D de la 11.5 a
# livre TROIS issues conformes a l'arbitrage --
# `atelier_scan_rapport._issues_du_rapport_complet` rend `Écrire les frames de
# ces N lots`, `LIBELLE_REPRENDRE`, `LIBELLE_ANNULER` --, et c'est en les
# confrontant a leur maquette qu'il a trouve l'ecart. Le lot A avait verifie que
# les treize notes etaient absorbees sans verifier laquelle chaque note touchait.
#
# La seconde moitie de la note 9 (« Que fait reprendre la detection avec
# d'autres fichiers ? Retour au depart ? ») est tranchee OUI, retour a `E3-1`
# avec le champ vide ; le code le porte en `A_COTE_REPRENDRE`. La maquette ne
# peut pas montrer ce a-cote : 5 colonnes d'indentation + 45 du libelle + 2 de
# separation + 30 du a-cote font 82 colonnes pour 76 utiles. Ecart signale a la
# fiche plutot que corrige ici -- il se tranche sur le libelle, donc dans `src/`.
ecrire("E3-3-scan-rapport-complet.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan",
    bandeau_droite="détection · 24 pages · 2 lots",
    centre=[
        "",
        "  Ce que la détection a trouvé — rien n'est encore écrit",
        "",
        *cartouche("Lots reconnus", [
            "● lot_25fps          8 pages / 8      124 frames / 124    complet",
            "● lot_12p5           4 pages / 4       62 frames / 62     complet",
        ]),
        "",
        "     En attente de lecture   ·  aucun fichier non rattaché",
        "",
        "   ▸ Écrire les frames de ces 2 lots",
        # Forme COURTE, et c'est une mesure : la longue faisait deborder la
        # ligne complete a 79 colonnes pour 76 utiles, dans les deux rendus.
        # « La detection » est redondant -- on est sur le rapport de detection.
        "     Reprendre avec d'autres fichiers",
        "     Annuler",
    ],
    etat="●  Document de détection écrit : versions/detection/26aout_1502.json",
    raccourcis="⏎ choisir  ↑↓ naviguer  Tab journal  Échap ateliers  F1 aide",
))

# `E3-4` -- deux corrections du 2026-08-30 :
#
# * le curseur `▸` etait ABSENT des trois issues. L'ecran montrait un etat que
#   le modele livre ne peut pas produire : `panneau.ChoixExclusif.__post_init__`
#   PLACE le curseur, au montage, sur la premiere issue qui n'ecrit pas -- ici
#   « Completer le QR ». Le rang de l'issue principale ne bouge pas pour
#   autant : c'est le curseur qui se place, pas la liste qui se reordonne ;
# * `EPIC11-ARB-56` -- la ligne d'etat portait « aucune issue n'est
#   preselectionnee », qui est un MOTIF DE CONCEPTION et non une mesure. Elle
#   porte desormais ce que l'ecran a compte. La regle, elle, ne se perd pas :
#   elle est levee a la CONSTRUCTION du modele, pas affichee.
#
# Et une TROISIEME correction, du 2026-08-31 : **les `( )` sont retires des
# trois issues** (`EPIC11-ARB-126`, verbatim d'Egan : « Flèche seule ! C'est
# uniquement dans les listes à cocher qu'on trouve les deux. »). La question Q1
# proposait de garder les deux glyphes et la note 11 d'`EPIC11-ARB-101` l'a
# approuvee (« OK c'est bien ») ; c'est l'arbitrage du meme jour qui tranche la
# forme, et il distingue deux objets que la maquette confondait -- une liste
# d'ISSUES (une seule sortie, `ChoixExclusif`) porte la fleche SEULE, parce que
# « le curseur EST la selection » (`EPIC11-ARB-45`) ; une liste A COCHER
# (explorateur en selection, cadences) porte la fleche ET la case, parce que ce
# sont deux informations distinctes.
#
# **Le code livre etait deja juste** : `panneau.ChoixExclusif.rendu()` ne pose
# que la fleche (`panneau.py`, « Plus de case a cocher »). La maquette montrait
# donc un ecran que le modele livre ne peut pas produire -- exactement l'ecart
# `G8` de 2026-08-30, sur l'autre glyphe de la meme ligne.
ecrire("E3-4-scan-rapport-incomplet.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan",
    bandeau_droite="détection · 24 pages · 2 lots",
    centre=[
        "",
        "  Ce que la détection a trouvé — rien n'est encore écrit",
        "",
        *cartouche("Lots reconnus", [
            "● lot_25fps          8 pages / 8      124 frames / 124    complet",
            "✕ lot_12p5           3 pages / 4       46 frames / 62     incomplet",
            "  └─ page 4 manquante          frames 047 à 062 absentes",
            "  └─ planche_03.tiff           QR_NON_DECODE",
        ]),
        "",
        "     En attente de lecture   ✕  1 fichier non rattaché",
        "",
        "     Écrire quand même     lot_12p5 sera écrit incomplet, 46 frames",
        "   ▸ Compléter le QR        saisir ce que planche_03 n'a pas livré",
        "     Annuler               ne rien écrire",
    ],
    etat="▲  1 lot sur 2 est incomplet · 3 pages sur 4 · 46 frames sur 62",
    raccourcis="⏎ valider  ↑↓ choisir  Tab journal  Échap ateliers  F1 aide",
))

# `E3-4b` -- REDESSINEE le 2026-08-31 (`EPIC11-ARB-101`, note 12 d'Egan). Ce
# n'est plus un ajustement de maquette : les CHAMPS etaient faux, sur deux axes.
#
# Verbatim d'Egan : « Il y a plus de champs que cela a completer. [...] Si le lot
# est au manifeste on peut completer certaines infos automatiquement [...] Si le
# lot n'est pas au manifeste il faut rentrer tous les champs manuellement. [...]
# il faut que le formulaire soit DANS LE MEME ORDRE que les infos du pied de page
# [...] en precisant a chaque fois la cle correspondant a chaque champ. »
#
# * **axe 1 -- les deux familles de champs sont celles du coeur.**
#   `scan_corrections.CHAMPS_D_IDENTITE` (6) est ce que l'operatrice LIT sur la
#   planche, donc ce que le formulaire demande ; `CHAMPS_NEUTRES_DU_LOT` (8) est
#   ce que `modele_depuis_le_manifeste` apporte gratuitement (`EPIC11-ARB-64`),
#   donc ce qu'il MONTRE sans le demander. La maquette d'avant demandait
#   « Projet » et les deux cadences -- trois champs NEUTRES -- et taisait le
#   gabarit, le cardinal d'images et les deux timecodes -- quatre champs
#   d'IDENTITE. Elle demandait ce qu'elle ne devait pas et taisait ce qu'elle
#   devait ;
# * **axe 2 -- l'ordre suit la planche, de haut en bas** : l'entete (le nom de
#   planche, puis la pagination), le pied technique (le gabarit), puis les
#   reperes sous les images (le cardinal, et les deux timecodes) ;
# * **axe 3 -- chaque champ imprime porte sa CLE**, lue de
#   `io.payload.PAYLOAD_SHORT_KEYS` comme le pied technique la lit : `lid`, `pi`,
#   `tid`. Trois champs n'en ont aucune, et l'omission est voulue --
#   `frames_per_page` et les deux timecodes vivent dans les `slots` du payload,
#   pas dans ses scalaires, donc le pied ne les imprime pas ; ils se lisent sous
#   les images, et c'est ce que `F1` dit ;
# * **la ligne du manifeste** (derniere ligne du centre) porte les huit cles que
#   la machine remplit deja. Sans elle, un operateur qui compte huit mentions au
#   pied de sa feuille et six champs a l'ecran conclut qu'il en manque deux.
#
# Les deux corrections du 2026-08-30 sont GARDEES, et elles n'ont pas bouge :
#
# * `EPIC11-ARB-56` -- la ligne d'etat porte la MESURE de l'ecran (« 5 champs sur
#   6 saisis »), jamais le motif de la regle. « Rien n'est prerempli » est
#   MESURE par l'AC 7.3, pas affiche ;
# * l'ecran montre un moment COHERENT -- cinq champs saisis, le sixieme en cours,
#   le focus `>` dessus. Un formulaire ou l'on saisit de haut en bas ne peut pas
#   avoir le focus en tete et les lignes suivantes deja pleines ; et ces cinq
#   valeurs-la, c'est l'operateur qui les a tapees, ce qui rend VISIBLE que rien
#   n'etait prerempli.
#
# **`o` a disparu de cet ecran, et c'est un arbitrage contre un autre.**
# `EPIC11-ARB-42` proposait `o` pour ouvrir le scan de la planche ;
# `EPIC11-ARB-68`, plus recent, interdit **sans exception** qu'une lettre soit un
# raccourci a cote d'un champ de saisie -- et cet ecran est un formulaire de bout
# en bout. L'ouverture est donc une LIGNE du formulaire, atteinte par `Tab` et
# validee par `⏎` : exactement la forme retenue pour la reprise du dpi sur
# `E3-1b` (`EPIC11-ARB-101`, note 7). Le chemin y est en outre rendu en lien
# cliquable OSC 8, qui reste un supplement -- le geste clavier fait foi.
#
# Les seize lignes du centre sont celles que `EcranCompletionQr.lignes()` rend
# reellement, a 80 colonnes : la maquette est le rendu, pas son idee.
ecrire("E3-4b-scan-completion-qr.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan · QR",
    bandeau_droite="planche_03.tiff",
    centre=[
        "",
        "  Compléter ce que le QR aurait dit",
        "",
        "     Recopiez le bloc d'identité imprimé en clair sur la planche.",
        "",
        "   Lot                     lot_12p5                                 lid",
        "   Page                    3                                 sur 4 · pi",
        "   Gabarit                 tpl-a4-paysage-4f-v2                     tid",
        "   Images sur la planche   4",
        "   Timecode première       00:00:08:00",
        "   Timecode dernière     > ·                                     requis",
        "",
        "   Ouvrir le scan          scans/scans-in/planche_03.tiff",
        regle("Vérification"),
        "",
        "     ● Cohérent avec les 3 pages déjà lues de ce lot",
        "     Le manifeste donne  pid rid fps ppi tbf tcs gmi pc",
    ],
    etat="✕  5 champs sur 6 saisis",
    raccourcis="⏎ valider  Tab champ  Échap abandonner  F1 où lire ce champ",
))

# `E3-5` -- le choix du profil de calibration, TROIS corrections du 2026-09-01
# (story 11.6), chacune sur un arbitrage POSTERIEUR au dessin du 2026-08-27.
# L'approbation d'Egan (« NOTE : Très bien, c'est la question suivante donc ? »)
# est du 2026-08-27 : elle precede `EPIC11-ARB-48`, `-56` et `-126`. Ce n'est
# donc pas revenir sur un avis, c'est appliquer des regles qui n'existaient pas
# quand l'avis a ete donne -- meme raisonnement que la 11.5 sur `E3-1` a `E3-4b`.
#
# * ecart `H1`, `EPIC11-ARB-126` -- la liste portait la fleche **ET** la case.
#   Verbatim d'Egan : « **Flèche seule !** C'est uniquement dans les listes à
#   cocher qu'on trouve les deux. » Une liste de profils n'est pas une liste a
#   cocher : on n'en retient qu'un. C'est le motif de la **liste selectionnable**
#   de `DESIGN.md` §7.1, qui ne porte aucune case -- `EPIC11-ARB-130` le tranche
#   nommement pour cet ecran, et **borne** `-126` aux listes d'issues (le
#   `( ) oui / (•) non` de `E3-9` reste, c'est un champ de formulaire, §7.3).
#   Le curseur part sur le profil par defaut : **c'est ca, la proposition**, et
#   elle ne retient rien tant que l'operateur n'a pas valide ;
# * ecart `H2`, `EPIC11-ARB-48` -- « autre fichier… » offrait `Tab, puis un
#   chemin`. Or cet ecran est **nomme** dans la table des cinq sites de
#   l'explorateur (« `E3-5` | Scan, "autre fichier..." | un fichier `.json` »),
#   et l'arbitrage retire « le verbe "completer" des lignes de raccourcis ».
#   Le a-cote dit desormais ce que l'explorateur cherche, pas une touche ;
# * ecart `H3`, `EPIC11-ARB-56` -- la ligne d'etat portait « Le profil par défaut
#   du projet est proposé ; il n'est pas imposé. », c'est-a-dire un **motif de
#   conception**. Elle **echappait au detecteur mecanique** de
#   `ecarts_de_sobriete` (ni touche, ni verbe de conseil, ni « c'est une ») :
#   seule la relecture pouvait la trouver, et c'est pourquoi elle est nommee dans
#   la fiche plutot que laissee au banc. Elle porte desormais une mesure.
#
# L'ecart `H4` tombe avec `H2` : `Tab saisir` designait une saisie de chemin qui
# n'existe plus.
#
# DEUX CORRECTIONS DE PLUS, tranchees par Egan le 2026-09-01 sur la planche de
# relecture du temps 2, et toutes deux sur la carte du profil retenu :
#
# * ecart `E1` -- la ligne « Chaîne » montrait une identite DERIVEE
#   (`hp-envy-4520 · tiff · 600 dpi · auto-corr off`), que le produit rendait par
#   le `chain_id` verbatim faute de mieux : `scan_chain.derive_chain_id` **hache**
#   make/model/software, et rien ne les recompose. Egan : « Ce qui s'affiche ici
#   normalement c'est le nom personnalisé qui a été donné par l'opérateur.ice au
#   moment de créer la page de calibration. Ça suffit très bien. Ce qu'on peut y
#   afficher éventuellement c'est le commentaire qui a été mis au moment de
#   générer la planche s'il est stocké au manifest ? » -- **il l'est** :
#   `calibration_profile.LABEL_FIELD` et `COMMENT_FIELD` sont valides par
#   `_validate_label_and_comment`, et `profile_designation.manifest_entry` les
#   recopie dans l'entree autoportante (`ENTRY_OPTIONAL_DOCUMENT_FIELDS`). La
#   ligne porte donc le **nom** puis le **commentaire**, et le nom dessine ici est
#   celui que `E3-9` fait saisir (« Nom de la chaîne ») ;
# * ecart `E2` -- « divergence brute 2,1 ΔE » portait une legende que le depot
#   emploie DEJA pour autre chose (`color_metrics.raw_divergence_de76`, une
#   comparaison brut-a-brut entre deux scans, qu'un profil ne porte pas ; le champ
#   reellement affiche est `acceptance.mean_delta_e_before`). Egan : « On met la
#   valeur brute sans légende. Seuls les connaisseurs la liront en connaissance de
#   cause. » La legende tombe, la valeur reste.
ecrire("E3-5-scan-calibration.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan",
    bandeau_droite="temps 2 sur 2 · écrire",
    centre=[
        "",
        "  Quelle calibration appliquer aux frames ?",
        "",
        "   ▸ hp-envy-4520-tiff-600            profil par défaut du projet",
        "     epson-v600-tiff-600-2026-08-14   posé le 14/08",
        "     autre fichier…                   un fichier .json, dans l'explorateur",
        "     aucune                           livrer le lot brut, non corrigé",
        "",
        regle("Le profil retenu"),
        "",
        "     Chaîne         hp-envy-4520-tiff-600 · passe du 12/08, vitre nettoyée",
        "     Posé le        12/08 · 24 patchs · 2,1 ΔE",
        "     S'applique à   les 2 lots de cette détection",
    ],
    etat="2 profils désignés dans ce projet · le retenu s'applique aux 2 lots",
    raccourcis="⏎ continuer  ↑↓ choisir  Échap retour  F1 aide",
))

# `E3-6` -- la confirmation du temps 2, QUATRE corrections du 2026-09-01
# (story 11.6). C'est le seul ecran du temps 2 qu'Egan n'avait PAS approuve tel
# quel : sa note portait sur le mecanisme d'edition des noms, et la reponse
# d'alors (`EPIC11-ARB-25` : « `e` edite ») a depuis ete **remplacee**.
#
# * ecart `H5`, `EPIC11-ARB-126` + `panneau.ChoixExclusif.rendu()` -- les trois
#   issues tenaient sur **une seule ligne**, avec des cases et **sans fleche**.
#   Le modele livre rend **une ligne par issue** avec la fleche sur le curseur
#   (`panneau.py:225-238`), et `ChoixExclusif.__post_init__` **place** ce curseur
#   sur la premiere issue qui n'ecrit pas -- ici « Modifier ». La maquette
#   montrait donc un ecran que le modele livre ne peut pas produire, exactement
#   l'ecart `Ab3` de la 11.5 sur `E3-4`. `E2-3`, livree et validee, porte deja la
#   forme juste : elle est reprise telle quelle ;
# * ecart `H6`, TROIS fautes dans une seule ligne d'etat -- une **touche**
#   (`EPIC11-ARB-56`), une **lettre** offerte a cote d'un champ de saisie
#   (`EPIC11-ARB-68` : « aucune lettre n'est un raccourci [...] **sans
#   exception** »), et le nombre **48 RECOPIE** la ou `tui.noms.LIMITE` **est**
#   `io.naming.CANONICAL_ID_MAX_LENGTH` (`tui/noms.py:30`). Ce dernier point n'est
#   pas theorique : la borne a valu 48, puis 64 sur `main` le 2026-08-28, puis 48
#   de nouveau avec un `LEGACY_ID_MAX_LENGTH = 64` en lecture seule
#   (`EPIC11-ARB-110`, 2026-08-31). Une maquette qui grave le nombre est fausse a
#   la prochaine bascule. La ligne porte desormais une mesure, sur le modele
#   exact de `E2-3`. **`E3-6` sort donc de l'ensemble ferme
#   `MAQUETTES_DONT_LA_LIGNE_D_ETAT_PORTE_ENCORE_UNE_TOUCHE`**
#   (`tests/unit/tui/test_majuscules_des_raccourcis.py:711`), et ce banc rougit
#   dans le sens de l'AMELIORATION -- ce qu'une assertion positive ne ferait pas ;
# * ecart `H7`, `EPIC11-ARB-68` point 2 -- `E éditer les noms` devient `Tab
#   éditer les noms`, et **le produit le dit deja** :
#   `execution.RACCOURCIS_CONFIRMATION` (`execution.py:130`). `Tab` **nomme sa
#   destination** ; `e` etait la porte d'`EPIC11-ARB-25`, remplacee depuis ;
# * ecart `H8` -- le glyphe de focus `>` etait pose sur le premier nom **hors
#   mode edition**. `E2-3` (meme famille d'ecran) ne le porte pas ; `E2-3b`, qui
#   est le mode edition, le porte **avec les compteurs `31/48` qui vont avec**.
#   Un focus sans mode d'edition fait se contredire l'ecran -- meme famille que
#   l'ecart `G12` de la 11.5.
ecrire("E3-6-scan-confirmation.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan",
    bandeau_droite="temps 2 sur 2 · écrire",
    centre=[
        "",
        *cartouche("À écrire", [
            "Lots écrits              2",
            "Frames attendues         124  +  62         =  186",
            "Frames obtenues          124  +  62         =  186        ● toutes",
            "Profondeur               16 bits",
            "Calibration              hp-envy-4520-tiff-600",
            "Espace disque            ~ 5,4 Go                    (majorant)",
            "",
            # **La liste PLATE, et sans libelle de colonne** -- meme correction
            # qu'`E2-3` et pour le meme motif : c'est ce que `Panneau.noms`
            # rend, apres une ligne vide et indente de `INDENT_DES_NOMS`. La
            # colonne « Noms des lots » n'existait que dans la maquette.
            "  projet_demo_lot_25fps_ingest01",
            "  projet_demo_lot_12p5_ingest01",
        ]),
        "",
        "     Écrire les TIFF",
        "   ▸ Modifier",
        "     Annuler",
    ],
    etat="2 lots · 186 frames · ~ 5,4 Go — rien n'a encore été écrit",
    # **`Tab éditer les noms` est RETIRE** (`EPIC11-ARB-141`, story 11.4e lot
    # H), et c'est la CINQUIEME correction de cet ecran. L'ecart `H7` ci-dessus
    # avait remplace le `e` par `Tab` -- la bonne touche pour un geste qui
    # existait. Le geste n'existe plus : `ecrire_depuis_le_document` n'a aucun
    # parametre de slug, et l'ecran editait de surcroit le mauvais objet
    # (`ingest_slug` nomme le seul dossier `scans/<slug>/`, pas un lot). La
    # ligne est desormais celle du produit,
    # `atelier_scan_confirmation.RACCOURCIS_SCAN_CONFIRMATION`.
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
))

ecrire("E3-7-scan-ecriture-en-cours.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan",
    bandeau_droite="temps 2 sur 2 · écrire",
    centre=[
        "",
        "  Écriture des TIFF — lot 1 sur 2",
        "",
        "     projet_demo_lot_25fps_ingest01                        en cours",
        "     projet_demo_lot_12p5_ingest01                         en attente",
        "",
        regle("Journal"),
        "",
        "     15:09:40  lot_25fps : correction hp-envy-4520-tiff-600 appliquée",
        "     15:09:41  page 1/8 : 8 frames recadrées sur marge encodée",
        "     15:09:48  page 2/8 : 8 frames recadrées sur marge encodée",
        "     15:10:02  frame 000031 écrite (16 bits)",
    ],
    etat=barre(31, 186, "frames", "3 min 40"),
    raccourcis="Tab journal  Échap interrompre  F1 aide",
))

ecrire("E3-8-scan-resultat.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan",
    bandeau_droite="2 lots · 186 frames",
    centre=[
        "",
        *cartouche("Écrit", [
            "● projet_demo_lot_25fps_ingest01    124 frames · 16 bits · 3,6 Go",
            "● projet_demo_lot_12p5_ingest01      62 frames · 16 bits · 1,8 Go",
            "",
            "Calibration appliquée               hp-envy-4520-tiff-600",
            "Manifest mis à jour                 projet_demo/manifest.json",
            "Durée                               6 min 12",
        ]),
        "",
        "   ▸ Ouvrir le dossier des lots",
        "     Encoder un master depuis ces lots           (atelier Exports)",
        "     Détecter d'autres scans",
        "     Retour aux ateliers",
    ],
    etat="●  186 frames écrites sur 186 attendues, aucun refus",
    raccourcis="⏎ choisir  ↑↓ naviguer  Tab journal  Échap ateliers  F1 aide",
))

# `E3-9` -- calibrer une chaine, QUATRE corrections du 2026-09-01 (story 11.6),
# dont une qui vient d'une MESURE DU COEUR et non d'une regle de charte.
#
# * ecart `H9` + `H10`, et c'est le plus lourd -- l'ecran annoncait
#   `▲ écrasement` et « Un profil de ce nom existe déjà ». **Le coeur dit le
#   contraire**, verbatim de `io/calibration_profile.write_profile`
#   (`io/calibration_profile.py:948-961`) : « il n'y en a **pas** [de collision]
#   quand la chaine est la meme : c'est la recalibration [...] que le module
#   documente depuis 5.22 comme **un remplacement voulu** -- poser la question a
#   chaque recalibration serait une invite qui apprend a repondre « oui » sans
#   lire, donc l'inverse de ce que cette decision cherche » (`EPIC5-ARB-99`).
#   Le cas dessine ici -- meme chaine, meme radical -- est donc une
#   **recalibration**, sans `▲` et sans question. La vraie collision (un AUTRE
#   `chain_id` sous le meme radical) est un autre ecran, a **trois** issues :
#   c'est `EPIC11-ARB-128`, qui reecrit l'AC de `epics.md`. Celle-ci decrivait
#   **une seule issue** la ou `EPIC11-ARB-89` en exige au moins deux -- et, ce
#   que personne n'avait mesure, elle decrivait aussi un mecanisme que le coeur
#   n'a pas. La ligne d'etat porte desormais une **mesure** (`EPIC11-ARB-56`)
#   au lieu du motif « la confirmation le redira » ;
# * ecart `H12`, `EPIC11-ARB-38` -- le champ de resolution etait **prerempli** a
#   600. « elle **n'est pas** preremplie. Le champ reste requis, et **vide** » :
#   l'arbitrage ne connait pas d'exception d'ecran, et c'est l'ecart `G3` que la
#   11.5 a corrige sur `E3-1`. La mesure du coeur est **affichee a cote**, sur
#   une ligne de formulaire reprise telle quelle de `E3-1b` -- ce qui donne aussi
#   la reponse a « quel geste la reprend, si ce n'est une lettre »
#   (`EPIC11-ARB-68`) : `Tab` puis `⏎` sur cette ligne ;
# * ecart `H11`, `EPIC11-ARB-48` -- « un composant unique [...] remplace le
#   champ-chemin **partout ou la TUI demande un chemin** ». `E3-9` demande un
#   chemin et **n'est pas dans la table des cinq sites** (`E0-2`, `E0-4`, `E3-1`,
#   `E3-5`, `E2-1`) : il a ete oublie, c'est un **sixieme site** et non une
#   exception. Le champ est desormais alimente par l'explorateur. Sa seule
#   consequence visible ici est le deplacement du glyphe de focus `>` vers le
#   champ requis -- le chemin affiche est celui que l'explorateur a rendu, et il
#   se dessine pareil ; ce qui change est le mecanisme, et il se mesure au code
#   (AC 8.4) plutot que sur ce dessin.
#
# CINQUIEME correction, tranchee par Egan le 2026-09-01 : l'ecart `E3`. La droite
# du bandeau portait « depuis le menu Scan ». Egan, relisant la planche : « Oui
# mais il y a écrit "depuis le menu scan". On met juste rien à cet endroit... »
# -- **rien**, et non une autre mention : le bandeau n'a pas d'objet travaille a
# dire sur cet ecran. Il n'y a donc plus d'`OBJET_DU_BANDEAU` cote produit non
# plus, et `Palier.bandeau` (la redaction unique) reprend la main : un ecran qui
# n'a rien a poser a droite est exactement le cas que la base traite deja.
#
# La mention datait d'`EPIC11-ARB-28`, qui avait retire « parcours a part » de
# l'interface ; elle repondait a la note d'Egan du 2026-08-27 en pied de cette
# maquette (« je n'ai pas compris comment on entre dans ce panneau ? »). La
# reponse a ete apportee autrement, et pour de bon : `calibrate` est une entree du
# menu d'atelier `E3-0`, et le bandeau porte deja `Scan · Calibrer` a gauche --
# la provenance s'y lit, la redire a droite etait une glose.
ecrire("E3-9-scan-calibrate.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan · Calibrer",
    centre=[
        "",
        "  Calibrer une chaîne de scan",
        "",
        "     Scan de la page        D:\\HOKO\\scans\\calib_hp_26aout.tiff",
        "     Résolution de scan   > ·                          requis · dpi",
        "     Reprendre la mesure    600 dpi       le fichier déclare 600 dpi",
        "",
        "     Nom de la chaîne       hp-envy-4520-tiff-600",
        "     Commentaire            passe du 26/08, vitre nettoyée",
        "",
        regle("Ce qui sera écrit"),
        "",
        "     Profil                 versions/calibration/hp-envy-4520-tiff-600",
        "     Remplace               la passe du 12/08 — même chaîne",
        "     Devient le défaut      ( ) oui    (•) non",
    ],
    etat="✕  résolution de scan requise — la calibration ne peut pas partir",
    raccourcis="⏎ continuer  Tab champ  Échap menu Scan  F1 aide",
))

ecrire("T5-1-refus-nomme.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan",
    bandeau_droite="détection · 24 pages",
    centre=[
        "",
        "  La détection s'est arrêtée",
        "",
        *cartouche("Refus", [
            "✕ DPI_DECLARE_INCOHERENT",
            "",
            "planche_07.tiff déclare 600 dpi mais mesure 425 dpi sur une A4.",
            "Le recadrage sur marge encodée serait faux de 4,1 mm.",
            "",
            "Les fichiers déclarent 425 dpi — non repris d'office : un",
            "scanner en auto-fit écrit une résolution qui n'est pas la sienne.",
            "Rien n'a été écrit ; les 6 pages détectées sont conservées.",
        ]),
        "",
        "   ▸ Reprendre à 425 dpi      la résolution que les fichiers déclarent",
        "     Reprendre à une autre résolution",
        "     Retirer planche_07.tiff et reprendre",
    ],
    etat="✕  DPI_DECLARE_INCOHERENT — code de refus énuméré (story 5.27)",
    raccourcis="⏎ choisir  ↑↓ naviguer  Tab journal  Échap ateliers  F1 aide",
))

ecrire("T3-1-journal.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Journal",
    bandeau_droite="lignes 812 à 826 sur 826",
    centre=[
        "",
        "     15:10:02  frame 000031 écrite (16 bits)",
        "     15:10:03  frame 000032 écrite (16 bits)",
        "     15:10:04  page 5/8 : 8 frames recadrées sur marge encodée",
        "     15:10:04    zone 3 : ▲ mire de remplacement, pas une frame",
        "     15:10:05  frame 000033 écrite (16 bits)",
        "     15:10:06  frame 000034 écrite (16 bits)",
        "     15:10:07  frame 000035 écrite (16 bits)",
        "     15:10:09  page 6/8 : 8 frames recadrées sur marge encodée",
        "     15:10:10  frame 000036 écrite (16 bits)",
        "     15:10:11  frame 000037 écrite (16 bits)",
        "     15:10:12  frame 000038 écrite (16 bits)",
        "     15:10:13  frame 000039 écrite (16 bits)",
        "     15:10:14  frame 000040 écrite (16 bits)",
    ],
    etat=barre(40, 186, "frames", "3 min 05"),
    # **La seule ligne du depot que la regle des majuscules ne peut pas plier**
    # (lot `O`, 2026-08-30). Ailleurs une lettre de raccourci s'affiche en
    # majuscule et se cable en minuscule ; ici `g` et `G` sont DEUX touches
    # distinctes -- debut et fin du journal, convention de `less` et de `vi` --,
    # et la casse y est donc porteuse. Les mettre toutes deux en majuscule
    # ferait deux entrees `G` dans la meme ligne. `c copier` suit la regle,
    # `g` / `G` restent tels quels, et l'ecart est remonte a Egan comme un
    # arbitrage a trancher plutot que corrige en silence.
    raccourcis="↑↓ défiler  g début  G fin  C copier  Tab revenir  Échap fermer",
))

ecrire("T4-1-ecrasement.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Extraction",
    bandeau_droite="rush_01 · 25 fps · 4:12",
    centre=[
        "",
        *cartouche("Ce lot existe déjà", [
            "▲ projet_demo_rush_01_25fps",
            "",
            "Écrit le          22/08 à 09:14",
            "Contient          124 frames · 16 bits · 2,1 Go",
            "Référencé par     1 planche PDF, 1 master encodé",
            "",
            "Écraser supprime ces 124 fichiers avant d'en écrire 124 autres.",
            "La planche et le master déjà produits ne sont PAS regénérés.",
        ]),
        "",
        "     ( ) Écraser le lot     ( ) Écrire sous un autre nom     ( ) Annuler",
        "",
        "     Autre nom            > projet_demo_rush_01_25fps_v2",
    ],
    etat="▲  Aucune issue présélectionnée — l'écrasement n'est jamais implicite",
    raccourcis="⏎ valider  ↑↓ choisir  E éditer le nom  Échap retour  F1 aide",
))

# ------- T4-2 : l'ecrasement quand le cartouche NE TIENT PAS, et il defile ---
#
# **`EPIC11-ARB-245`, tranche par Egan le 2026-09-05, par invite** : « Faire
# defiler le cartouche ». Il a choisi cette issue en connaissance du cout que
# je lui annoncais NON MESURE -- un defilement dans une confirmation
# destructive laisse valider sans avoir lu ce qu'on detruit.
#
# **Le defaut que cette maquette repare, et il est arithmetique.** Mesure du
# 2026-09-05 sur le code livre (lot F de la 11.4e), avec UN SEUL lot en
# conflit : cartouche **15 lignes** avant repli, plus **4 issues**, pour un
# plafond de `jetons.HAUTEUR_CENTRE_AU_PLANCHER` = **17**. Une ligne du
# cartouche fait 96 colonnes et se replie en deux, ce qui porte le rendu reel a
# 21 lignes ; a deux lots en conflit, 23. Le debordement **preexiste au lot F**
# -- il valait deja 18 pour 17 -- et personne ne l'avait vu parce que
# `test_sobriete_et_grille_extraction.py` **exclut nommement** les ecrans
# d'`execution.py`.
#
# **`T4-1` ne pouvait pas servir de validation.** Elle tient ses 24 lignes,
# mesure refaite -- mais elle dessine ses trois issues sur une SEULE ligne
# horizontale, forme qu'`EPIC11-ARB-45` a remplacee par le rendu vertical, et
# son cartouche porte cinq lignes de fiche la ou le code en rend quinze.
#
# **Ce que je fais du cout qu'Egan a accepte, plutot que de le subir.** Son
# choix porte sur le MECANISME (le cartouche defile) et non sur l'ORDRE de ce
# qu'il contient. Les deux phrases de consequence -- ce qu'ecraser detruit, ce
# qu'il ne regenere pas, ce qu'une version coute -- remontent donc **au-dessus
# du pli**, et ne defilent jamais. Ce qui passe sous le pli est du DETAIL
# reperable : bornes, destination, les noms apparies. La ligne de pli les
# **nomme**, au lieu d'annoncer un nombre de lignes muet : un operateur sait ce
# qu'il n'a pas lu.
#
# L'avertissement qu'`EPIC11-ARB-89` exige avant une ecriture destructive
# consciente reste donc visible a l'ouverture, sans defilement et sans clic.
#
# **La fleche est sur `Modifier les réglages`**, et ce n'est pas un choix de
# maquette : `ChoixExclusif.__post_init__` pose le curseur sur la premiere
# issue **qui n'ecrit pas**, et c'est celle-la. Meme discipline que `T6-1` --
# la maquette montre l'etat du MODELE, jamais un etat plausible.
#
# **Ce que cette maquette NE mesure pas, dit plutot que tu** : le cas a DEUX
# lots en conflit, ou le bloc apparie compte trois lignes de plus. Le pli
# absorbe la difference par construction -- c'est tout l'interet du
# defilement --, mais aucune maquette ne le montre, et une ligne de pli qui
# nommerait mal ce qu'elle cache ne se verrait pas ici.

#: La zone utile d'un cartouche de 72 colonnes : le helper en retire 4.
_UTILE_T4 = 68


def _chiffre_t4(libelle: str, valeur: str) -> str:
    """Libelle a gauche, valeur calee a DROITE du cartouche.

    Ecrit ici plutot que compte a la main comme dans `T4-1` : un bord droit
    decale d'une colonne est invisible a la relecture et saute aux yeux dans
    un vrai terminal.
    """
    return f"{libelle}{' ' * (_UTILE_T4 - len(libelle) - len(valeur))}{valeur}"


ecrire("T4-2-ecrasement-cartouche-defilant.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Extraction",
    bandeau_droite="rush_01 · 3 cadences · conflit",
    centre=[
        "",
        *cartouche("Ce lot existe déjà", [
            "▲ Écraser supprime le lot déjà sur le disque, puis réécrit.",
            "  Les planches et masters déjà produits ne sont PAS regénérés.",
            "  Créer la v2 n'efface rien : ces ~ 2,1 Go s'ajoutent au disque.",
            "",
            _chiffre_t4("Déjà sur le disque", "rush_01_12p5 · 1 fichier"),
            _chiffre_t4("Lots créés", "3 lots"),
            _chiffre_t4("Frames écrites", "124 + 42 + 17 = 183 frames"),
            _chiffre_t4("Espace disque", "~ 2,1 Go (majorant)"),
            "↓ 8 sur 14 lues — la suite : bornes, destination, 3 noms appariés",
        ]),
        "",
        "     Écraser et réextraire",
        "     Créer la v2",
        "   ▸ Modifier les réglages",
        "     Annuler, ne rien écrire",
    ],
    etat="▲  8 lignes sur 14 lues · 4 issues, 2 écrivent · rien n'est écrit",
    # **`Ctrl+↓` et non `PgSuiv`, et c'est une frontiere du depot qui l'a
    # tranche.** La premiere redaction de cette maquette annoncait `PgSuiv` ;
    # `test_majuscules_des_raccourcis.py` l'a refusee, et elle a eu raison :
    # son inventaire `_TOUCHES_NOMMEES` est un ensemble FERME, et un grep du
    # depot entier confirme qu'AUCUNE touche de pagination n'existe nulle part
    # -- ni dans une maquette, ni dans un `on_key`. `PgSuiv` aurait donc
    # introduit une famille de touches neuve dans tout le produit pour un seul
    # ecran.
    #
    # `Ctrl+↓` entre sans rien ouvrir : il suit `Ctrl+A`, `Ctrl+D` et `Ctrl+R`
    # que le depot emploie deja, et il compose une regle qui s'apprend d'un
    # coup -- **les fleches choisissent une issue, Ctrl + fleche lit le
    # cartouche**. C'est aussi ce qui garantit qu'un defilement ne vole jamais
    # les fleches aux issues, l'exigence que l'arbitrage pose.
    raccourcis=("⏎ valider  ↑↓ choisir  Ctrl+↓ lire la suite  "
                "Échap retour  F1 aide"),
))


# `T6-1` -- l'interruption d'une ECRITURE, seule maquette d'interruption du
# depot. Une correction du 2026-09-01 (story 11.6), et un soupcon leve.
#
# * ecart `H13`, `EPIC11-ARB-126` -- les trois issues portaient `( )`. C'est
#   **exactement** l'ecart `Ab3` que la 11.5 a corrige sur `E3-4`, laisse ouvert
#   par elle avec la mention « la seule [maquette d'interruption] du depot,
#   `T6-1`, est le TEMPS 2 -- et elle porte le meme ecart qu'Ab3. A traiter avec
#   la 11.6 ». Le modele livre (`execution.EcranInterruption.ISSUES`,
#   `execution.py:1069-1076`) porte ces trois issues **verbatim** ; seul le
#   glyphe etait faux. La fleche est posee sur « garder », parce que c'est ce que
#   `ChoixExclusif.__post_init__` produit : la premiere issue **qui n'ecrit pas**
#   (« effacer » est la seule marquee `ecrit=True`). La maquette montre donc
#   l'etat exact du modele, et non un etat plausible ;
# * soupcon `H15`, LEVE et garde ici pour qu'on ne le repaie pas -- la ligne
#   d'etat « L'écriture continue tant que rien n'est choisi ici » **ressemble** a
#   un motif de conception, c'en est **une mesure de l'etat de la passe** :
#   l'ecriture tourne derriere l'ecran. Le produit dit deja la meme chose,
#   `EcranInterruption.etat()` (`execution.py:1091`). Rien a corriger ;
# * ce que cette maquette a de MIEUX que le code, et qui part au produit plutot
#   qu'ici (ecart `H14`) : elle **chiffre** ses issues (« les 40 frames »), la ou
#   `ISSUES` les laisse generiques (« ce qui est deja ecrit »). C'est l'AC 6.5 de
#   la 11.5 -- « chaque issue porte, a cote d'elle, ce qu'elle fait avec son
#   chiffre reel » --, et c'est le produit qui doit rattraper la maquette.
ecrire("T6-1-interruption.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Scan",
    bandeau_droite="temps 2 sur 2 · écrire",
    centre=[
        "",
        *cartouche("Interrompre l'écriture ?", [
            "▲ 40 frames sur 186 sont déjà écrites sur le disque.",
            "",
            "Interrompre les laisse en place : le lot sera sur le disque mais",
            "INCOMPLET, et le manifest ne le déclarera pas terminé.",
            "",
            "Le document de détection reste valide : reprendre l'écriture plus",
            "tard ne redemande pas de détecter.",
        ]),
        "",
        "   ▸ Interrompre et garder les 40 frames",
        "     Interrompre et effacer les 40 frames",
        "     Reprendre l'écriture",
    ],
    etat="▲  L'écriture continue tant que rien n'est choisi ici",
    raccourcis="⏎ valider  ↑↓ choisir  Échap reprendre l'écriture  F1 aide",
))
print("zone B : ok")
