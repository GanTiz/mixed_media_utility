# -*- coding: utf-8 -*-
"""Jetons de la TUI : ils sont IMPORTES de la GUI, jamais redefinis.

Source de verite du comportement : ``_bmad-output/planning-artifacts/
ux-designs/ux-tui-2026-08-27/DESIGN.md``, sections 1 (grille), 5 (couleurs) et
6 (glyphes). Source de verite des VALEURS de couleur :
:mod:`mixed_media_utility.gui.jetons`, que ce module se contente de projeter.

**Pourquoi seules les variantes de texte** (story 11.0, AC 2). ``gui/jetons.py``
distingue deux familles : les chromies pleines (``SEMANTIQUES``, ``ACCENT``) qui
sont des valeurs **de trait et d'aplat** et « ne portent jamais de glyphe », et
les ``VARIANTES_TEXTE``, a clarte relevee, qui portent le texte. Or **dans un
terminal tout est glyphe** : il n'y a ni trait ni aplat. La TUI n'a donc
structurellement acces qu'aux variantes de texte, et importer ``SEMANTIQUES``
serait un defaut de contraste et non un choix de style. C'est ce qu'une AC de
frontiere mesure, imports comptes a zero.

**Aucune valeur hexadecimale n'est ecrite ici.** Elles viennent toutes de la
GUI ; ce module ne fait que leur donner leur nom d'emploi en TUI. Un ecart entre
les deux surfaces devient impossible par construction plutot que par discipline.

**La geometrie vit ici aussi, et seulement ici** -- meme regle que cote GUI, ou
« les composants les LISENT ». Aucun widget n'ecrit 80, 24 ou 36 en dur.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable
from collections.abc import Mapping
from types import MappingProxyType

from ..gui import jetons as _gui

# ---------------------------------------------------------------------------
# Couleurs (DESIGN.md TUI, section 5). Six jetons, tous projetes de la GUI.
# ---------------------------------------------------------------------------

#: Les six couleurs de la TUI. Cle = nom d'emploi en TUI, valeur = la couleur
#: que la GUI porte deja. Le dictionnaire est fige : un appelant qui voudrait
#: « juste corriger une teinte » doit le faire dans la GUI, ou les deux surfaces
#: en beneficient et ou le test de contraste de la story 7.0 le mesure.
COULEURS = MappingProxyType({
    "state-complete": _gui.VARIANTES_TEXTE["state-complete-text"],
    "state-substitute": _gui.VARIANTES_TEXTE["state-substitute-text"],
    "state-absent": _gui.VARIANTES_TEXTE["state-absent-text"],
    "accent": _gui.VARIANTES_TEXTE["accent-text"],
    "data": _gui.NEUTRES["text-primary"],
    "muted": _gui.NEUTRES["text-secondary"],
})

# ---------------------------------------------------------------------------
# Glyphes (DESIGN.md TUI, section 6). Le second canal, obligatoire : aucune
# information n'est portee par la couleur seule.
# ---------------------------------------------------------------------------

#: Table complete. Toute information d'etat prend son glyphe ici; un glyphe hors
#: de cette table est un defaut (il peut manquer dans une police de console).
GLYPHES = MappingProxyType({
    "complete": "●",       # ● complet, reussi, present
    "substitute": "▲",     # ▲ substitut, avertissement, reserve
    "absent": "✕",         # ✕ absent, manquant, refuse, invalide
    "neutre": "·",         # · non renseigne, sans objet
    "curseur": "▸",        # ▸ ligne courante
    "coche": "[x]",
    "decoche": "[ ]",
    "exclusif-retenu": "(•)",
    "exclusif-libre": "( )",
    "barre-pleine": "▓",   # ▓
    "barre-vide": "░",     # ░
    "invite": ">",
    "caret": "█",          # █
    "rattachement": "└─",  # └─
})

#: **Le ROTOR d'attente : quatre dessins d'UN seul signe, jamais un etat.**
#:
#: Il n'entre pas dans :data:`GLYPHES` et ce n'est pas un oubli. Cette table
#: nomme des ETATS -- un jeton, une couleur, un sens -- et chacune de ses
#: entrees rend UN dessin. Un rotor est l'inverse : un seul sens (« ca
#: travaille ») rendu par quatre dessins successifs, et il ne porte aucune
#: couleur d'etat. L'y verser aurait casse les deux proprietes que la table
#: tient -- l'injectivite de son repli ASCII et l'egalite `set(GLYPHES) ==
#: set(GLYPHES_ASCII)` -- pour y loger quelque chose qui n'est pas un etat.
#:
#: **Quand il a le droit de tourner, et c'est la seule condition.**
#: `DESIGN.md` §9 interdit « une animation qui tourne a la place d'un compte
#: reel », et l'interdit tient : un compte qui n'avance pas est une
#: information, un sablier qui tourne n'en est pas une. Ce que la regle ne
#: couvrait pas, c'est le cas ou AUCUN compte reel n'existe -- mesure du
#: 2026-09-02 sur la mire de calibration : `pdf_render.render_lot_pdf` emet un
#: jalon PAR PAGE et une mire tient sur une page, donc le seul compte
#: alimentable a deux etats, 0 % puis 100 %. Le rotor ne remplace alors aucun
#: compte : il est le seul signe honnete que la machine travaille.
ROTOR = ("\u25d0", "\u25d3", "\u25d1", "\u25d2")

#: Le repli du rotor, dans l'ordre de :data:`ROTOR`. Quatre dessins distincts
#: en ASCII aussi : un repli qui rendrait deux fois le meme signe detruirait le
#: mouvement, qui est toute l'information que ce signe porte.
ROTOR_ASCII = ("|", "/", "-", "\\")


def rotor(pas: int, ascii_seul: bool = False) -> str:
    """Le dessin du rotor au `pas` demande, cycle sans fin.

    Le modulo est fait ICI et non chez l'appelant : un ecran qui compterait ses
    propres pas et oublierait le reste rendrait un `IndexError` au quatrieme
    tour, c'est-a-dire apres quelques secondes d'execution reelle.
    """
    table = ROTOR_ASCII if ascii_seul else ROTOR
    return table[pas % len(table)]


#: Repli pour les terminaux qui ne rendent pas l'UTF-8 (`--ascii`). Le SENS ne
#: change pas, seul le dessin change : chaque valeur reste distincte de toutes
#: les autres, sans quoi le repli detruirait le second canal qu'il doit servir.
GLYPHES_ASCII = MappingProxyType({
    "complete": "*",
    "substitute": "!",
    "absent": "x",
    "neutre": ".",
    "curseur": ">",
    "coche": "[x]",
    "decoche": "[ ]",
    "exclusif-retenu": "(o)",
    "exclusif-libre": "( )",
    "barre-pleine": "#",
    "barre-vide": "-",
    "invite": ">",
    "caret": "_",
    "rattachement": "\\_",
})

# ---------------------------------------------------------------------------
# Geometrie (DESIGN.md TUI, section 1).
# ---------------------------------------------------------------------------

#: Plancher absolu. Sous cette taille la TUI ne dessine PAS une version
#: degradee : elle affiche la taille courante et la taille exigee, et rien
#: d'autre (`EPIC11-ARB-21`). Une mise en page tronquee ment sur ce qui tient.
LARGEUR_PLANCHER = 80
HAUTEUR_PLANCHER = 24

#: Repartition verticale, invariante sur TOUS les ecrans (DESIGN.md section 1).
HAUTEUR_BANDEAU = 1
HAUTEUR_ETAT = 1
HAUTEUR_RACCOURCIS = 1

#: Le cadre exterieur : une ligne en haut, une en bas, une colonne de chaque
#: cote. C'est le `+----+` des maquettes, et il consomme de la place -- l'y
#: oublier est exactement l'erreur qui ferait tenir 20 lignes de contenu la ou
#: les maquettes en montrent 17.
BORDURE = 1
#: Les deux filets horizontaux qui separent le bandeau du contenu, puis le
#: contenu de la ligne d'etat.
FILETS = 2
#: La marge laissee a gauche et a droite du texte a l'interieur du cadre.
MARGE = 1

def hauteur_centrale(hauteur_fenetre: int = HAUTEUR_PLANCHER) -> int:
    """Lignes reellement disponibles pour le contenu, cadre et zones deduits.

    Le pendant vertical de :func:`largeur_utile`, et il vit ici pour la meme
    raison : « la geometrie vit ici aussi, et seulement ici ». Au plancher :
    24 - 2 lignes de cadre - 2 filets - bandeau - etat - raccourcis = 17.

    **Derivee de la fenetre et non du plancher** : au-dela de 24 lignes, la
    place gagnee va entierement a la zone centrale (`DESIGN.md` section 1). La
    calculer sur le plancher revient a ignorer un terminal plein ecran -- c'est
    exactement ce que le manuel faisait, sa LARGEUR suivant la fenetre pendant
    que sa HAUTEUR restait au plancher (revue de la 11.9, mutant `M38`).

    **Elle etait ecrite QUATRE fois dans le paquet** avant le 2026-09-04
    (`atelier_pdf_resultat`, `atelier_pdf_execution`, `execution` deux fois),
    chacune avec son propre `max(..., 0)` et son propre commentaire. Une
    frontiere negative mesure desormais qu'aucun autre module ne refait la
    soustraction : un test positif ne verrait pas une cinquieme copie revenir.

    Le plancher a zero n'est pas decoratif : sous 24 lignes la fenetre est hors
    plancher, la coque n'y dessine que le message de `EPIC11-ARB-21`, et une
    hauteur negative rendue a un paginateur serait une valeur qu'aucun appelant
    n'attend.
    """
    return max(hauteur_fenetre - 2 * BORDURE - FILETS
               - HAUTEUR_BANDEAU - HAUTEUR_ETAT - HAUTEUR_RACCOURCIS, 0)


#: Ce qui reste pour le contenu au plancher. Derive, jamais saisi : poser 17 en
#: dur laisserait deux sources de verite diverger a la premiere retouche.
HAUTEUR_CENTRE_AU_PLANCHER = hauteur_centrale(HAUTEUR_PLANCHER)


def largeur_utile(largeur_fenetre: int = LARGEUR_PLANCHER) -> int:
    """Colonnes reellement disponibles pour du texte, cadre et marges deduits.

    Au plancher : 80 - 2 colonnes de cadre - 2 de marge = 76. C'est la largeur
    sur laquelle les maquettes ont ete construites et verifiees ; un widget qui
    calculerait sur 80 deborderait de quatre colonnes.
    """
    return largeur_fenetre - 2 * BORDURE - 2 * MARGE


def largeur_de_cartouche(largeur_fenetre: int = LARGEUR_PLANCHER) -> int:
    """Colonnes de texte a l'INTERIEUR d'un cartouche (`DESIGN.md` 7.4).

    Le cartouche occupe toute la zone centrale et porte son propre cadre : il
    retire donc une seconde fois une bordure et une marge de chaque cote. Au
    plancher : 76 - 2 - 2 = 72, ce que les maquettes verifiees montrent.
    """
    return largeur_utile(largeur_fenetre) - 2 * BORDURE - 2 * MARGE

#: Largeur de la barre de progression (DESIGN.md section 8). Constante, parce
#: qu'une barre qui s'etire rend deux captures incomparables.
LARGEUR_BARRE = 36


def glyphes(ascii_seul: bool = False):
    """Rend la table de glyphes a employer, selon le repli demande."""
    return GLYPHES_ASCII if ascii_seul else GLYPHES


def couleur(nom: str) -> str:
    """Rend la valeur d'un jeton, ou leve si le nom n'existe pas.

    Le refus est deliberement dur : un jeton mal orthographie qui rendrait une
    couleur par defaut produirait une surface silencieusement hors charte, et
    c'est precisement ce que la frontiere « aucune couleur litterale » vise.
    """
    try:
        return COULEURS[nom]
    except KeyError:
        connus = ", ".join(sorted(COULEURS))
        raise KeyError(f"jeton de couleur inconnu: {nom!r}. Connus: {connus}") from None


def marque(nom_etat: str, libelle: str = "", ascii_seul: bool = False) -> str:
    """Rend le TEXTE d'un etat : son glyphe, puis son libelle s'il y en a un.

    C'est le second canal de `DESIGN.md` section 6, rendu executable. Deux
    etats distincts rendent deux chaines distinctes **meme sans couleur** --
    c'est ce que l'AC 3.2 de la story 11.0 mesure, et c'est pourquoi le repli
    ASCII doit lui aussi rester injectif : un repli qui rendrait `*` pour deux
    etats detruirait le canal qu'il est cense servir.
    """
    table = glyphes(ascii_seul)
    try:
        glyphe = table[nom_etat]
    except KeyError:
        connus = ", ".join(sorted(table))
        raise KeyError(
            f"glyphe inconnu: {nom_etat!r}. Connus: {connus}") from None
    return f"{glyphe} {libelle}" if libelle else glyphe


# ---------------------------------------------------------------------------
# Fenetre de defilement. **Une seule redaction pour les trois listes.**
# ---------------------------------------------------------------------------
#
# `explorateur.Explorateur`, `cadences.ListeDeCadences` et
# `rushes.ListeDesRushes` defilent toutes les trois de la meme facon, et le
# calcul etait ecrit DEUX fois avant que la troisieme n'arrive
# (`cadences.py:468` disait deja « Meme calcul que celui de l'explorateur, et
# pour la meme raison »). Une troisieme copie serait la troisieme redaction
# d'une meme regle : le depot en connait le prix -- « deux redactions du meme
# repli divergent » (`rushes.SIGNE_MULTIPLIER`), et c'est le repli local qui a
# ete retire au profit de la table, pas l'inverse.
#
# Les deux fonctions sont **pures** et ne connaissent aucune liste : elles
# prennent un cardinal, un rang et une hauteur. C'est ce qui permet de les
# mesurer sur des bornes, sans monter d'ecran.


def fenetre_de_liste(total: int, premier_visible: int,
                     hauteur: int) -> tuple[int, int]:
    """`(premier, dernier)` rangs visibles d'une liste qui defile, bornes
    **incluses**.

    La ligne `…` se reserve **avant** le decoupage, en haut comme en bas : sans
    cela, la derniere entree se cacherait derriere le `…` qui annonce
    justement qu'elle existe. Une liste qui tient entiere n'en porte aucune, et
    rend donc ses `total` rangs.

    Le couple rendu est **vide** -- `(0, -1)` -- sur une liste vide : c'est un
    resultat, pas un echec, et `range(premier, dernier + 1)` le traverse zero
    fois sans garde a l'appel.
    """
    if total <= hauteur:
        return 0, total - 1
    premier = premier_visible
    haut = 1 if premier > 0 else 0
    place = hauteur - haut
    if premier + place < total:
        place -= 1
    return premier, min(premier + place - 1, total - 1)


def recadrer_la_fenetre(premier_visible: int, curseur: int, total: int,
                        hauteur: int) -> int:
    """Le nouveau `premier_visible` qui ramene `curseur` dans la fenetre.

    Elle avance **d'un rang a la fois** plutot que de sauter au bon
    `premier_visible` : la borne haute depend de la presence du `…` de tete,
    qui depend elle-meme de `premier_visible`. Un calcul direct devrait donc
    resoudre cette dependance croisee, et c'est exactement ce que la boucle
    fait sans l'ecrire.

    La boucle est bornee par `total + 1` : elle termine toujours, et un jour ou
    la borne serait fausse elle rendrait un cadrage faux plutot que de figer
    l'interface.
    """
    for _ in range(total + 1):
        premier, dernier = fenetre_de_liste(total, premier_visible, hauteur)
        if curseur < premier:
            premier_visible = max(premier_visible - 1, 0)
            continue
        if curseur > dernier:
            premier_visible += 1
            continue
        return premier_visible
    return premier_visible


# ---------------------------------------------------------------------------
# Mesure de largeur. **On compte des COLONNES, jamais des caracteres.**
# ---------------------------------------------------------------------------

def colonnes(texte: str) -> int:
    """Largeur d'affichage d'un texte, en colonnes de terminal.

    `len()` compte des caracteres et ment sur deux familles au moins : les
    ideogrammes et le kana en occupent **deux**, les marques combinantes
    **zero**. Un nom de projet en japonais rendait un bandeau de 82 colonnes
    dans une zone de 76, rogne sans bruit -- trouve par la revue de vague 1
    (couche 2). C'est la meme unite que `verifier_maquettes.py` emploie sur les
    46 maquettes : le depot compte en colonnes, ce module aussi.
    """
    largeur = 0
    for caractere in texte:
        if unicodedata.combining(caractere):
            continue
        largeur += 2 if unicodedata.east_asian_width(caractere) in ("W", "F") else 1
    return largeur


def caler_a_gauche(texte: str, largeur: int, ascii_seul: bool = False) -> str:
    """Un champ cale a gauche, mesure en **COLONNES** et jamais en `len()`.

    Un ideogramme occupe deux colonnes : `str.ljust` -- ce que `{x:<33}` est --
    calerait un champ de dix caracteres sur vingt colonnes, et toutes les
    colonnes de droite partiraient avec, jusqu'a se faire amputer par
    :func:`ajuster`. La mention qui suit le champ est alors la premiere a
    disparaitre, c'est-a-dire la seule chose qui dise ce que la ligne EST.

    **Ecrit ICI parce que le depot l'a paye CINQ fois** : `atelier_exports_lot`,
    son jumeau d'`atelier_pdf_lots`, `cadences` et `projet_inventaire` portent
    chacun leur propre `_a_gauche`, quatre redactions du meme calcul ; et
    `palier_profil_defaut` a rouvert le defaut le 2026-09-06 sans les voir --
    ce qu'on ne trouve pas ne se recopie pas, ce qui se recopie diverge. Les
    trois derniers sites fautifs (`atelier_scan_calibration`, `atelier_pdf`,
    `atelier_scan`) appellent celui-ci ; la consolidation des quatre
    redactions existantes est en dette.

    L'abregement passe par :func:`ajuster` **avant** le calage, jamais apres :
    caler puis abreger rendrait un champ deja plein qu'on couperait ensuite.
    """
    texte = ajuster(texte, largeur, ascii_seul)
    return texte + " " * max(0, largeur - colonnes(texte))


#: L'ellipse d'abregement, **ecrite une seule fois pour toute la TUI**. Les
#: quatre fonctions qui abregent la lisent ici : deux litteraux `…`
#: divergeraient au premier ajustement, et le repli ASCII de celui qui aurait
#: ete oublie passerait a travers `REPLIS_DE_TEXTE` sans bruit.
ELLIPSE = "\u2026"

#: Ce que les textes d'ecran portent d'UTF-8 en dehors de la table de glyphes :
#: des fleches de raccourci, le symbole d'entree, les separateurs typographiques.
#: `--ascii` doit les replier aussi -- un terminal qui ne rend pas `▓` ne rend
#: pas davantage `⏎`, et la ligne de raccourcis est ce que l'operateur lit en
#: premier quand il ne sait plus quoi faire (revue de vague 1, couche 2).
REPLIS_DE_TEXTE = MappingProxyType({
    "↑": "^", "↓": "v", "←": "<", "→": ">",
    "⏎": "Entree", "…": "...", "·": ".",
    "—": "--", "–": "-", "«": '"', "»": '"',
    "’": "'", " ": " ",
    # **Le signe multiplier n'est pas decoratif : il porte une resolution.**
    # Defaut trouve au developpement de la story 11.4 (lot D, 2026-08-29) :
    # sans cette entree, `replier_ascii("1920×1080")` rendait `1920?1080` --
    # la decomposition Unicode ne connait pas `×`, et le repli terminal
    # remplace par `?` ce qu'il ne sait pas rendre. Cinq maquettes de TROIS
    # ateliers portent ce signe (`E2-1`, `E4-1`, `E4-3`, `E5-1`, `E5-6`) : le
    # defaut aurait mordu trois fois, et pas une.
    #
    # **`x` et non `*`**, bien que `x` soit aussi le glyphe ASCII de l'etat
    # « absent » : la collision est impossible, `jeton_d_etat` exigeant que le
    # glyphe OUVRE UNE COLONNE, et `1920x1080` le colle entre deux chiffres.
    # C'est la meme frontiere qui empeche deja « resolution 3840 x 2160 » de
    # sortir en rouge, et un test la mesure ici aussi.
    "×": "x",
    # **Le filet titre est le meme piege, trouve au lot G de la story 11.4.**
    # `atelier_extraction._filet` et `explorateur` composent `── Bornes ──…`
    # et choisissent chacun leur trait selon le mode
    # (`trait = "-" if ascii_seul else "─"`), si bien que le defaut ne mord pas
    # aujourd'hui. Mais `replier_ascii("── Bornes ──")` rendait `?? Bornes ??`
    # : tout texte portant un filet qui passerait par le repli GENERAL -- un
    # message venu du coeur, une ligne recopiee d'une maquette -- sortait en
    # points d'interrogation. La table est le bon endroit pour le savoir ; les
    # deux gardes locales restent, elles ne genent pas.
    "─": "-",
    # **`\u0394` porte une unite, et il n'avait pas de repli** -- verse a cette
    # table par le lot H de la story 11.6, sur mesure du lot C. La
    # decomposition Unicode ne connait pas la majuscule grecque : sans cette
    # entree, `replier_ascii("\u0394E")` rendait `?E`, et `--ascii` affichait
    # « divergence brute 2,8 ?E » -- un point d'interrogation la ou l'operateur
    # lit une unite colorimetrique. Le lot C avait pose un repli **local** dans
    # `atelier_scan_calibration`, faute de pouvoir toucher ce module partage ;
    # l'entree appartient ici, ou toute ligne qui porte l'unite en profite, y
    # compris celles que le coeur redige.
    #
    # **`d` et non `D`** : c'est la notation employee par le depot dans ses
    # sorties ASCII (`dE`), et elle est deja celle qu'`atelier_scan_calibration`
    # affichait -- qui lit desormais cette table plutot que sa propre copie.
    "\u0394": "d",
    # **Le marqueur de liste deroulee**, verse a cette table par le lot D de la
    # story 11.8. Il n'est pas dans `GLYPHES` -- ce n'est pas un etat, et
    # `DESIGN.md` section 6 n'en porte aucun de cette famille --, donc la
    # premiere passe ne le voit pas ; et la decomposition Unicode ne connait
    # pas le triangle. Sans cette entree,
    # `replier_ascii("prores_hq ▾ .mov")` rendait `prores_hq ? .mov` :
    # exactement le defaut que `×` a paye le 2026-08-29, cette fois sur le
    # champ de profil des maquettes `E4-2` et `E4-2b`.
    #
    # **`v` et non `V`** : c'est deja le repli de `↓`, et les deux disent
    # la meme chose -- ce qui suit se lit vers le bas. Deux replis differents
    # pour deux dessins descendants se liraient comme deux gestes.
    "▾": "v",
    # **Les quatre dessins du rotor**, sans quoi `replier_ascii` les rendrait
    # `????` : ils ne sont pas dans `GLYPHES` (voir :data:`ROTOR`), donc la
    # premiere passe ne les voit pas, et la decomposition Unicode ne connait pas
    # les quarts de cercle. La table est le seul endroit ou toute ligne d'ecran
    # en profite, y compris celles que le coeur redige.
    "\u25d0": "|", "\u25d3": "/", "\u25d1": "-", "\u25d2": "\\",
})


#: **Les glyphes que la console de Windows est susceptible de ne pas dessiner**,
#: avec le nom de leur point de code. Recensement du 2026-09-06, apres deux
#: plaintes de terrain d'Egan : « le symbole "Enter" [...] devient illisible »
#: et « le glyphe d'attente [...] n'est pas rendu par un terminal windows
#: natif ».
#:
#: **Ce que la table EST** : l'echantillon que `--diagnostic-chemin` imprime
#: tel quel, pour qu'on MESURE sur la machine de l'operateur au lieu de
#: deviner. Les deux premieres entrees sont **confirmees** cassees ; les
#: quatre suivantes sont une **presomption** -- meme famille de blocs
#: Unicode, jamais signalees.
#:
#: **Ce qu'elle n'est PAS** : une liste de ce qui manque a une police. Aucune
#: API ne repond a « cette police contient-elle U+23CE ? » ; on connait le nom
#: de la police, jamais sa couverture. La table dit ou regarder, elle ne dit
#: pas ce qu'on y verra.
#:
#: Les 31 points de code non-ASCII affichables de `tui/*.py` sont **tous dans
#: le BMP**, aucun emoji, aucun hors-BMP, aucun double largeur. Le reste --
#: fleches, `▓░█▲`, filets `─` -- est dans CP437 et Egan les a vus s'afficher.
GLYPHES_A_RISQUE = (
    ("\u23ce", "RETURN SYMBOL -- la touche de validation, 62 litteraux"),
    ("\u25d0", "CIRCLE WITH LEFT HALF BLACK -- le rotor d'attente"),
    ("\u2715", "MULTIPLICATION X -- l'etat « absent / refuse »"),
    ("\u25b8", "BLACK RIGHT-POINTING SMALL TRIANGLE -- le curseur de ligne"),
    ("\u25cf", "BLACK CIRCLE -- l'etat « complet »"),
    ("\u25be", "BLACK DOWN-POINTING SMALL TRIANGLE -- la liste deroulee"),
    # Les temoins : CP437, donc censes passer partout. Ils sont dans
    # l'echantillon **exactement** pour ca -- si eux tombent aussi, le probleme
    # n'est pas la couverture de la police mais l'encodage de la sortie, et le
    # diagnostic doit permettre de trancher entre les deux.
    ("\u2593", "DARK SHADE -- temoin CP437, la barre de progression"),
    ("\u2591", "LIGHT SHADE -- temoin CP437"),
    ("\u2588", "FULL BLOCK -- temoin CP437, le caret"),
    ("\u25b2", "BLACK UP-POINTING TRIANGLE -- temoin CP437"),
    ("\u2500", "BOX DRAWINGS LIGHT HORIZONTAL -- temoin CP437, les filets"),
    ("\u2192", "RIGHTWARDS ARROW -- temoin CP437"),
)


def replier_ascii(texte: str) -> str:
    """Rend un texte d'ecran en ASCII pur, sans en changer le sens.

    Trois passes, dans cet ordre : la table des glyphes (`▓` -> `#`), la table
    des symboles de texte (`⏎` -> `Entree`), puis la decomposition Unicode qui
    retire les accents (`É` -> `E`). Ce qui resterait hors ASCII est remplace
    par `?` plutot que perdu -- un caractere manquant se voit, un caractere
    supprime ne se voit pas.
    """
    for source, cible in GLYPHES.items():
        texte = texte.replace(cible, GLYPHES_ASCII[source])
    for source, cible in REPLIS_DE_TEXTE.items():
        texte = texte.replace(source, cible)
    decompose = unicodedata.normalize("NFKD", texte)
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    return sans_accent.encode("ascii", "replace").decode("ascii")


def points_d_abregement(ascii_seul: bool = False) -> str:
    """Les points d'abregement du mode demande : `…`, ou `...` en `--ascii`.

    **Le repli precede la mesure, et cette fonction est ce qui le rend
    inevitable.** `…` occupe une colonne, `...` en occupe trois : un abregement
    qui choisirait ses points APRES avoir compte ferait deborder de deux
    colonnes toute ligne calee juste. C'est la regression payee sur le bandeau
    le 2026-08-28, puis a nouveau sur la ligne chiffree en revue de vague 2 bis.
    """
    return REPLIS_DE_TEXTE[ELLIPSE] if ascii_seul else ELLIPSE


def envelopper(texte: str, largeur: int, ascii_seul: bool = False) -> list[str]:
    """Replier une PHRASE sur plusieurs lignes, sans jamais rien perdre.

    **La troisieme facon de faire tenir du texte, et elle n'est pas
    interchangeable avec les deux autres.** :func:`ajuster` abrege une ligne
    dont la place est comptee (un bandeau, une ligne d'etat : elles font une
    ligne, par contrat) ; :func:`abreger_chemin` abrege un chemin par le
    milieu ; celle-ci **ne perd rien** et depense de la hauteur a la place.

    Elle sert la ou la hauteur existe et ou le texte est irremplacable : les
    motifs de refus rendus **verbatim** par le coeur. Mesure du developpement de
    la story 11.2 -- `Invalid manifest at 'schema_version': '9.9' is not a
    supported manifest schema_version (known: 2.0, 2.1).` fait 101 colonnes
    pour une zone de 76, et `ajuster` en coupait la moitie actionnable :
    l'operateur lisait qu'il y avait un probleme de `schema_version`, jamais
    **quelles versions** sont acceptees. Un motif tronque n'est plus le motif du
    coeur, c'est un resume -- ce que `EPIC11-ARB-30` refuse.

    La coupure se fait sur les espaces ; un mot plus long que la largeur est
    coupe net plutot que de faire deborder la ligne.

    **La boucle de decoupe progresse toujours d'au moins un caractere**, et ce
    n'est pas une precaution de style : sur `largeur = 1`, `_tete` rend `""`
    des que le premier caractere en coute deux (ideogramme, kana, pleine
    chasse). La boucle apposait alors une ligne vide sans rien consommer, et ne
    se terminait **jamais** -- le processus etait bloque, sans exception ni
    message. Un caractere qui ne rentrera jamais est pose seul et deborde d'une
    colonne, ce qui se voit ; une TUI qui ne rend plus la main ne se voit pas.
    """
    if ascii_seul:
        texte = replier_ascii(texte)
    if largeur <= 0:
        return []
    lignes: list[str] = []
    courante = ""
    for mot in texte.split():
        candidate = f"{courante} {mot}" if courante else mot
        if colonnes(candidate) <= largeur:
            courante = candidate
            continue
        if courante:
            lignes.append(courante)
        # Un mot seul plus large que la zone -- un chemin sans espace, par
        # exemple : on le decoupe plutot que de laisser `textual` le replier
        # lui-meme, ce qui decalerait tout le bloc qui suit.
        while colonnes(mot) > largeur:
            tete = _tete(mot, largeur) or _au_moins_un_caractere(mot)
            lignes.append(tete)
            mot = mot[len(tete):]
        courante = mot
    if courante:
        lignes.append(courante)
    return lignes


#: Les deux separateurs de chemin, traites ensemble. Le depot tourne sous
#: Windows et sous Linux, et un chemin saisi a la main peut porter l'un ou
#: l'autre : deux implementations divergeraient sur la seule plateforme ou
#: personne ne regarde.
SEPARATEURS_DE_CHEMIN = ("\\", "/")


def abreger_chemin(chemin: str, largeur: int, ascii_seul: bool = False) -> str:
    """Rend `chemin` tenu dans `largeur` colonnes, abrege **AU MILIEU**.

    `DESIGN.md` section 9 : « un chemin trop long se tronque **au milieu**, avec
    `…`, en gardant le debut et le nom de fichier ».

    **Pourquoi ce n'est pas :func:`ajuster` avec une option.** Les deux
    abregements repondent a deux questions differentes. Une **phrase** se lit de
    gauche a droite : sa fin est ce qu'il coute le moins cher de perdre, et
    `ajuster` la coupe la. Un **chemin** se lit par ses deux bouts -- la racine
    dit ou l'on est, le dernier segment dit **ce que c'est** -- et c'est son
    milieu qui est le moins couteux.

    La difference n'est pas esthetique, elle est mesurable : abreges par la fin,
    `...\\projects\\projet_demo` et `...\\projects\\projet_hiver` rendent la
    **meme** chaine, et l'operateur choisit entre deux lignes identiques. C'est
    le mode de panne que cette fonction existe pour empecher, et un test le
    fige des deux cotes -- il verifie aussi que `ajuster` le produit bien, sans
    quoi la justification de ce module s'effacerait en silence.

    **Le repli ASCII est fait AVANT toute mesure**, jamais apres : `…` occupe
    une colonne, `...` en occupe trois. Replier ensuite ferait deborder de deux
    colonnes une chaine calee juste -- exactement la regression payee sur le
    bandeau le 2026-08-28, par le seul chemin qui n'etait pas mesure.
    """
    if ascii_seul:
        chemin = replier_ascii(chemin)
    if largeur <= 0:
        return ""
    if colonnes(chemin) <= largeur:
        return chemin
    points = points_d_abregement(ascii_seul)
    cout_points = colonnes(points)
    if largeur <= cout_points:
        # Meme les points ne tiennent pas : on rend ce qui rentre. Une zone
        # aussi etroite est un etat d'ecran, pas une erreur a lever.
        return _tete(points, largeur)

    # Le dernier segment est ce que l'operateur cherchait : il est servi en
    # premier sur le budget, et le debut prend ce qui reste.
    queue = _dernier_segment(chemin)
    budget = largeur - cout_points
    if colonnes(queue) >= budget:
        # A largeur serree, le nom prime sur la racine -- garder la racine et
        # perdre le nom rendrait deux projets identiques a l'ecran.
        return points + _fin(queue, budget)
    return _tete(chemin, budget - colonnes(queue)) + points + queue


def _dernier_segment(chemin: str) -> str:
    """Ce qui suit le dernier separateur, quel qu'il soit.

    Un chemin sans separateur n'a pas de segment terminal distinct : il se rend
    lui-meme, et l'abregement retombe alors sur le comportement de tete.
    """
    coupe = max(chemin.rfind(separateur) for separateur in SEPARATEURS_DE_CHEMIN)
    return chemin if coupe < 0 else chemin[coupe + 1:]


def _au_moins_un_caractere(mot: str) -> str:
    """Le premier caractere de `mot`, avec les marques qui s'y accrochent.

    Le garde-fou de progression de :func:`envelopper`. Les marques combinantes
    valent zero colonne et n'appartiennent pas au caractere suivant : les
    laisser derriere couperait un `e` de son accent et rendrait une ligne
    commencant par un accent orphelin.
    """
    coupe = 1
    while coupe < len(mot) and unicodedata.combining(mot[coupe]):
        coupe += 1
    return mot[:coupe]


def _cout(caractere: str) -> int:
    """Colonnes occupees par un caractere. Zero pour une marque combinante."""
    if unicodedata.combining(caractere):
        return 0
    return 2 if unicodedata.east_asian_width(caractere) in ("W", "F") else 1


def _tete(texte: str, largeur: int) -> str:
    """Le plus long prefixe de `texte` tenant dans `largeur` colonnes."""
    garde: list[str] = []
    reste = largeur
    for caractere in texte:
        cout = _cout(caractere)
        if cout > reste:
            break
        garde.append(caractere)
        reste -= cout
    return "".join(garde)


def _fin(texte: str, largeur: int) -> str:
    """Le plus long suffixe de `texte` tenant dans `largeur` colonnes.

    **Le suffixe ne commence jamais par une marque combinante** (revue de la
    vague 3, couche 2, `C2`). Une marque combinante coute zero colonne, donc la
    boucle la gardait toujours -- y compris quand la lettre qu'elle decore, elle,
    ne tenait pas. Sur un nom en forme **NFD** -- la forme nominale d'un volume
    macOS, ou `e` est suivi de U+0301 --, la queue de l'abrege s'ouvrait alors
    sur un **accent orphelin** : `…́ra_A` au lieu de `…era_A`.

    C'est le symetrique exact de ce que :func:`_au_moins_un_caractere` fait deja
    pour la TETE, et il manquait ici parce que la tete se lit dans le sens de la
    lecture et la queue a l'envers -- le meme defaut ne se voit pas des deux
    cotes de la meme facon.
    """
    garde: list[str] = []
    reste = largeur
    for caractere in reversed(texte):
        cout = _cout(caractere)
        if cout > reste:
            break
        garde.append(caractere)
        reste -= cout
    # Les marques combinantes de tete sont laissees a la partie coupee : sans
    # leur lettre de base, elles ne montrent rien et se collent au symbole
    # d'abregement.
    while garde and unicodedata.combining(garde[-1]):
        garde.pop()
    return "".join(reversed(garde))


def ajuster(texte: str, largeur: int, ascii_seul: bool = False) -> str:
    """Rend `texte` tenu dans `largeur` colonnes, abrege par des points si besoin.

    **Ce n'est pas une commodite d'affichage.** `textual` ne tronque pas une
    ligne trop longue : il la **replie**, et sur une zone de hauteur 1 la fin
    part sur une ligne qui n'est jamais dessinee. Une phrase coupee la est
    indistinguable d'une phrase absente. Abreger visiblement dit au moins qu'il
    manque quelque chose.

    Le garde-fou est le **dernier** recours : un texte qui l'atteint est un
    texte a raccourcir a la source, et les tests mesurent que les textes du
    depot tiennent sans lui.
    """
    if ascii_seul:
        texte = replier_ascii(texte)
    if largeur <= 0:
        return ""
    if colonnes(texte) <= largeur:
        return texte
    points = points_d_abregement(ascii_seul)
    budget = largeur - colonnes(points)
    if budget <= 0:
        return points[:largeur]
    # Le calcul du plus long prefixe est celui de `_tete`, partage avec
    # :func:`abreger_chemin`. Deux copies de cette boucle divergeraient sur les
    # cas ou elle est subtile -- les marques combinantes valent zero colonne,
    # les ideogrammes en valent deux -- et la seconde copie serait la moins
    # testee des deux.
    return _tete(texte, budget) + points


#: Le creux minimal entre un texte de gauche et une colonne de droite -- un nom
#: et ses cardinaux, un libelle et son chiffre, une valeur et son compteur.
#:
#: **Elle vit ICI parce qu'elle etait ecrite QUATRE fois.** `explorateur`,
#: `ecran_projet`, `noms` et `panneau` en portaient chacun une copie, avec un
#: commentaire renvoyant a l'original : quatre ecritures de la meme valeur
#: divergent au premier ajustement, et c'est exactement le motif que
#: `LEGENDE_DES_CARDINAUX` documente dans `projets.py` pour justifier de ne
#: jamais recopier. Sous deux colonnes, les deux textes se touchent ; c'est la
#: borne BASSE que `max(2, creux)` tient, la borne HAUTE etant l'abregement.
CREUX_MINIMAL = 2


def abreger_nom(nom: str, largeur: int, ascii_seul: bool = False) -> str:
    """Un NOM tenu dans `largeur` COLONNES, abrege **AU MILIEU**.

    **Publique, et c'est un contrat.** Quatre lignes de la TUI bornent un nom
    de la meme facon -- la liste de l'explorateur, la ligne des recents, celle
    d'un nom produit, celle d'une ligne chiffree ; elles appellent celle-ci
    plutot que d'en recopier une seconde, parce que deux abregements differents
    sur le meme ecran sont exactement le defaut que la revue de vague 2 bis
    sanctionne.

    **Elle vit dans le module de MESURE, et pas dans l'explorateur.** Elle y a
    ete ecrite d'abord parce que c'est la liste qui en avait besoin la
    premiere ; il en resultait que `panneau.py`, qui se presente comme un
    modele pur, importait `explorateur.py`, c'est-a-dire un ecran. La
    dependance etait a l'envers, et elle disparait ici.

    **Pourquoi au milieu, et pourquoi pas :func:`abreger_chemin`.** Un nom de
    dossier de tournage porte son identite a ses **deux** bouts : la date en
    tete (`2026-08-29_`) et la variante en queue (`_camera_B`, `_v3`, et la
    barre finale qui dit que c'est un dossier). Coupe par la fin,
    `..._camera_A/` et `..._camera_B/` rendent la meme ligne -- le mode de
    panne que :func:`abreger_chemin` existe pour empecher sur les chemins.
    `abreger_chemin`, lui, est pilote par les separateurs : sur un nom qui n'en
    porte qu'un, et en derniere position, il rend une troncature de tete et
    perd la barre finale. Il ne convient donc pas ici.
    """
    if largeur <= 0:
        return ""
    if colonnes(nom) <= largeur:
        return nom
    # Le repli du symbole precede la mesure -- voir :func:`points_d_abregement`.
    points = points_d_abregement(ascii_seul)
    cout = colonnes(points)
    if largeur <= cout:
        return _tete(points, largeur)
    budget = largeur - cout
    # La queue prend la moitie basse : a budget impair, c'est la tete qui gagne
    # la colonne, parce qu'elle porte la date et que deux dossiers d'un meme
    # tournage ne se distinguent qu'a partir d'elle.
    queue = budget // 2
    return _tete(nom, budget - queue) + points + _fin(nom, queue)


# ---------------------------------------------------------------------------
# La couleur, posee au DESSIN (EPIC11-ARB-47)
# ---------------------------------------------------------------------------

#: Les trois etats, **du mode courant seulement**.
#:
#: **Il n'existe volontairement aucune table qui melange les deux modes.** Il en
#: existait une (`ETAT_DE_GLYPHE`, retiree le 2026-08-29) : elle portait les six
#: glyphes -- les trois UTF-8 et leurs trois replis --, et c'est son emploi a la
#: peinture qui faisait sortir « Extraction » en ROUGE, tout `x` ordinaire y
#: repondant. Devenue sans appelant apres la correction, elle restait chargee et
#: exportee sur un chemin fragile : c'est le piege lui-meme qu'on retire ici,
#: pas seulement son dernier usage.
NOMS_D_ETAT = ("complete", "substitute", "absent")


def etats_du_mode(ascii_seul: bool = False) -> dict[str, str]:
    """Les trois glyphes d'etat du mode ACTIF, et leur jeton de couleur.

    Le filtre de mode est la premiere des deux conditions qui rendent la
    peinture sure : chercher les six glyphes des deux tables dans un texte
    UTF-8 revient a teindre toute ligne qui porte un `x`, un `!` ou une `*`
    ordinaires -- et « Extraction » sortait donc en ROUGE au menu des ateliers,
    sur le rendu livre. Defaut trouve par Egan le 2026-08-29, sur une maquette
    coloriee, et reproduit ensuite sur le code. La seconde condition est la
    forme de colonne exigee par :func:`jeton_d_etat` ; le filtre de mode seul
    ne tient pas, puisqu'en repli ASCII les glyphes SONT des lettres.
    """
    table = glyphes(ascii_seul)
    return {table[nom]: f"state-{nom}" for nom in NOMS_D_ETAT}


#: **Ce qui peut preceder un glyphe d'etat** : le debut de la ligne, ses blancs
#: d'indentation compris, ou le creux d'au moins DEUX blancs qui separe deux
#: colonnes. C'est ce que la mise en page produit partout -- `_ligne` de
#: l'explorateur et `ligne_de_recent` de l'ecran projet calent tous deux leur
#: colonne droite sur `" " * max(2, creux)`. Une prose, elle, separe ses mots
#: par UN blanc : c'est exactement ce qui distingue `« resolution 3840 x 2160 »`
#: d'une colonne d'etat, et rien d'autre ne les distingue.
_OUVRE_UNE_COLONNE = r"(?:^[ \t]*|[ \t]{2,})"

#: **Ce qui peut suivre** : un blanc unique puis le libelle -- la forme exacte
#: que :func:`marque` produit --, ou la fin de la ligne. Un glyphe suivi d'un
#: creux de colonne n'est pas un etat mais une valeur : c'est le cas d'une
#: entree de l'explorateur litteralement nommee `x`, dont la taille est calee a
#: droite (`«     x              2 o »`).
_PORTE_UN_LIBELLE = r"(?:[ \t](?=[^ \t])|[ \t]*$)"


def jeton_d_etat(ligne: str, ascii_seul: bool = False) -> str | None:
    """Le jeton de couleur d'une ligne, ou `None` si elle ne porte pas d'etat.

    **Le glyphe doit avoir la forme d'une colonne d'etat**, pas seulement etre
    un mot a lui seul : il ouvre une colonne (debut de ligne ou creux d'au
    moins deux blancs) et porte son libelle a un blanc, ou finit la ligne.

    **Pourquoi la frontiere de mot ne suffisait pas.** Elle rattrape
    « Extraction » et « deux lots », ou le glyphe est colle a des lettres ; elle
    ne rattrape aucun glyphe reellement borde par des blancs. En repli ASCII --
    ou `x`, `!` et `*` SONT les trois glyphes d'etat -- « Rien n'a ete ecrit ! »
    sortait en orange et « resolution 3840 x 2160 » en rouge, sur des lignes
    atteignables : le journal d'execution et l'ecran de refus rendent
    **verbatim** des messages venus du coeur. La correction livree le
    2026-08-29 ne tenait donc qu'en UTF-8, c'est-a-dire dans le seul mode ou le
    defaut ne pouvait de toute facon pas se produire.

    **Ce que cette forme ne prouve pas.** C'est une regle de mise en page, pas
    une preuve : la couleur reste **retrouvee** dans un texte au lieu d'etre
    posee la ou l'on sait qu'on ecrit un etat. Une ligne qui, sans colonne
    droite, ne porterait qu'un nom valant `x` serait encore teintee. La fermeture
    complete demande que l'appelant transmette l'etat au lieu de le laisser
    deviner ; tant qu'elle n'est pas faite, cette forme est ce qui separe le
    mieux les deux familles mesurees.
    """
    for glyphe, jeton in etats_du_mode(ascii_seul).items():
        motif = _OUVRE_UNE_COLONNE + re.escape(glyphe) + _PORTE_UN_LIBELLE
        if re.search(motif, ligne):
            return jeton
    return None


def peindre(lignes, ascii_seul: bool = False, sans_couleur: bool = False,
            ligne_du_curseur: int | None = None,
            etats: Mapping[int, str] | None = None,
            lignes_du_curseur: Iterable[int] | None = None,
            liens: Mapping[int, str] | None = None):
    """Poser la couleur sur des lignes **deja mesurees et ajustees**.

    `EPIC11-ARB-47`. L'ordre compte et il n'est pas negociable : la largeur se
    mesure sur le texte nu, la couleur s'ajoute apres. Peindre d'abord ferait
    compter les balises comme des colonnes, et chaque ligne coloree deborderait.

    Deux regles, et deux seulement :

    * **la ligne du curseur** passe en gras et en couleur d'accentuation --
      c'est la moitie du mecanisme de choix de `EPIC11-ARB-45`, l'autre moitie
      etant la disparition de la case a cocher ;
    * **une ligne qui porte un glyphe d'etat** prend la couleur de cet etat.

    **`etats` DONNE l'etat, ligne par ligne** (`EPIC11-ARB-71`), comme
    `ligne_du_curseur` donne deja le rang du curseur. La reconnaissance par
    motif ci-dessous n'est plus qu'un **repli**, pour les textes venus du coeur
    dont aucun ecran ne connait l'etat.

    **Pourquoi ce parametre existe.** La reconnaissance par motif exige deux
    conditions de *mise en page* -- le glyphe ouvre une colonne, et porte son
    libelle a un blanc. Trois formes courantes ne les remplissent pas, et
    Egan les a trouvees en relisant des maquettes :

    * un glyphe dans un **cartouche** est precede de la bordure et d'**un**
      blanc : il n'ouvre pas de colonne. Consequence generale, et c'est elle
      qui a decide ce correctif -- *aucun glyphe d'etat pose dans un cartouche
      n'etait colore*, or le cartouche est la forme du panneau de confirmation,
      par lequel toute ecriture passe ;
    * un glyphe suivi de **deux** blancs en ligne d'etat ne porte pas son
      libelle a un blanc ;
    * une ligne de **continuation** d'un message replie ne porte, par
      construction, aucun glyphe : un refus sur trois lignes n'etait rouge que
      sur la premiere, et se lisait comme deux messages.

    **Ce qui a ete ecarte, et pourquoi il faut le savoir.** Relacher les deux
    expressions regulieres est la fausse piste evidente et elle casse un cas
    mesure : `_PORTE_UN_LIBELLE` elargi a « un ou plusieurs blancs »
    recolorerait l'entree d'explorateur litteralement nommee `x` dont la taille
    est calee a droite. Le repli n'est donc **pas touche** ; l'etat donne
    s'ajoute au-dessus de lui.

    **Rend un objet stylise, jamais une chaine balisee**, et ce n'est pas un
    detail d'implementation. Le balisage exige d'echapper le texte venu de
    l'exterieur -- un chemin, un motif d'erreur du coeur --, et cet echappement
    n'est pas inversible : `rich` protege une barre oblique inverse finale en la
    doublant, si bien qu'un chemin Windows tres ordinaire s'affichait avec deux
    barres. Le defaut a ete trouve par le test de cette fonction, pas par
    relecture. Construire le style directement supprime la classe entiere.

    `sans_couleur` rend le meme texte sans aucun style : le repli ne change pas
    ce qui est lisible, seulement ce qui est teinte.

    **`liens` DONNE la cible d'un lien cliquable, ligne par ligne**
    (`EPIC11-ARB-42`, story 11.5 AC 7.8). Meme forme que `etats` et
    `lignes_du_curseur`, et pour le meme motif : un lien ne se devine pas dans
    un texte, il se **donne** -- une reconnaissance par motif y prendrait tout
    chemin affiche pour une cible ouvrable, y compris un chemin que le fichier
    n'existe plus.

    **Le lien est un SUPPLEMENT, jamais le chemin principal** : la sequence
    OSC 8 est posee par `rich` a partir du style, donc **hors du texte mesure**
    -- `texte_affiche` rend la meme chaine avec et sans lien, et la grille ne
    bouge pas d'une colonne. Un terminal qui ignore OSC 8 affiche le libelle
    nu, et le geste clavier de l'ecran reste le seul chemin garanti
    (`EPIC11-ARB-11` : « rien n'est atteignable seulement a la souris »).

    `sans_couleur` **retire aussi le lien**, et ce n'est pas un oubli : c'est le
    repli des terminaux qui ne savent rien poser, et c'est le regime exact
    qu'un banc doit pouvoir mesurer pour verifier que rien n'est perdu sans
    OSC 8.
    """
    from rich.text import Text

    lignes = list(lignes)
    etats = dict(etats or {})
    # **Les deux refus sont durs**, du meme motif que celui de :func:`couleur` :
    # un jeton mal orthographie qui rendrait une couleur par defaut produirait
    # une surface silencieusement hors charte, et un rang qui ne designe aucune
    # ligne est une erreur d'appariement -- la famille de defauts que la regle
    # des fabriques existe pour attraper, et qui ne se voit jamais a l'oeil.
    for rang, nom in etats.items():
        if nom not in NOMS_D_ETAT:
            connus = ", ".join(NOMS_D_ETAT)
            raise KeyError(
                f"etat inconnu: {nom!r} au rang {rang}. Connus: {connus}")
        if not 0 <= rang < len(lignes):
            raise IndexError(
                f"rang d'etat hors bornes: {rang} pour {len(lignes)} ligne(s)")
    # **`lignes_du_curseur` DONNE l'entree entiere**, quand une entree tient sur
    # plusieurs lignes (`EPIC11-ARB-101`, note 1 d'Egan du 2026-08-31).
    #
    # C'est le SYMETRIQUE exact de ce qu'`EPIC11-ARB-71` a fait pour les glyphes
    # d'etat : « une ligne de continuation d'un message replie ne porte, par
    # construction, aucun glyphe », donc aucune reconnaissance par motif ne peut
    # la trouver -- il faut la DONNER. Le raisonnement n'avait jamais ete
    # applique au curseur, et la moitie d'une entree restait non teintee.
    #
    # Le parametre d'origine survit intact : huit appelants passent un rang
    # unique, et l'elargir en douce changerait huit ecrans sans que personne ne
    # l'ait demande.
    rangs_du_curseur: set[int] = set()
    if lignes_du_curseur is not None:
        rangs_du_curseur = {int(r) for r in lignes_du_curseur}
        hors_bornes = [r for r in rangs_du_curseur if not 0 <= r < len(lignes)]
        if hors_bornes:
            raise IndexError(
                f"rang de curseur hors bornes: {sorted(hors_bornes)} pour "
                f"{len(lignes)} ligne(s)")
    elif ligne_du_curseur is None:
        # **Auto-detection**, pour que chaque ecran n'ait pas a tenir un second
        # compteur qui divergerait du premier : la ligne du curseur est celle
        # qui porte le glyphe de curseur, pose par le modele. Elle ne peut
        # trouver qu'UN rang, et seulement si le glyphe ouvre la ligne.
        marque_curseur = glyphes(ascii_seul)["curseur"]
        ligne_du_curseur = next(
            (rang for rang, ligne in enumerate(lignes)
             if ligne.startswith(marque_curseur)), None)
    if ligne_du_curseur is not None:
        rangs_du_curseur.add(ligne_du_curseur)

    liens = dict(liens or {})
    hors_bornes = [r for r in liens if not 0 <= r < len(lignes)]
    if hors_bornes:
        # Meme refus dur que pour `etats` et `lignes_du_curseur`, et pour le
        # meme motif : un rang qui ne designe aucune ligne est une erreur
        # d'appariement -- la famille de defauts que la regle des fabriques
        # existe pour attraper, et qui ne se voit jamais a l'oeil.
        raise IndexError(
            f"rang de lien hors bornes: {sorted(hors_bornes)} pour "
            f"{len(lignes)} ligne(s)")

    peint = Text()
    for rang, ligne in enumerate(lignes):
        if rang:
            peint.append(chr(10))
        if sans_couleur:
            peint.append(ligne)
            continue
        if rang in rangs_du_curseur:
            peint.append(ligne, style=_avec_lien("bold " + couleur("accent"),
                                                 liens.get(rang)))
            continue
        # **Troisieme regle** (`EPIC11-ARB-51`) : le champ qui a le focus se rend
        # comme la ligne du curseur, parce qu'il EST le curseur a ce moment-la --
        # quand la saisie a le focus, la liste n'en a plus, et rien d'autre ne le
        # montrerait. Demande d'Egan, verbatim : « il faut que cet etat soit
        # visible. Surbrillance ? Surlignage ? Que proposes-tu ? »
        #
        # Elle vient APRES la regle du curseur, et ce n'est pas indifferent : en
        # repli ASCII le glyphe d'invite et celui du curseur sont le MEME
        # caractere (`>`), et c'est l'ordre qui separe alors les deux cas.
        if _porte_l_invite(ligne, ascii_seul):
            peint.append(ligne, style=_avec_lien("bold " + couleur("accent"),
                                                 liens.get(rang)))
            continue
        # **L'etat DONNE l'emporte sur l'etat devine**, et le repli ne sert que
        # les lignes dont aucun appelant n'a declare l'etat.
        nom = etats.get(rang)
        jeton = f"state-{nom}" if nom else jeton_d_etat(ligne, ascii_seul)
        peint.append(ligne, style=_avec_lien(couleur(jeton) if jeton else "",
                                             liens.get(rang)))
    return peint


#: Le mot que `rich` reconnait dans une chaine de style pour poser un lien
#: cliquable, et qu'il rend en sequence OSC 8. Ecrit une fois : deux redactions
#: divergeraient le jour ou la bibliotheque le renomme, et l'une des deux
#: rendrait alors un style inconnu au lieu d'un lien.
MOT_DE_LIEN = "link"


def _avec_lien(style: str, cible: str | None) -> str:
    """La chaine de style, augmentee du lien quand il y en a un.

    **La cible passe en queue**, apres la couleur : `rich` lit `link` puis
    consomme le reste du mot comme URL, si bien qu'un jeton de couleur pose
    apres serait avale par l'adresse au lieu d'etre applique.

    Une cible vide -- et pas seulement `None` -- ne pose aucun lien : `link `
    suivi de rien serait un style que `rich` refuse, et un ecran qui n'a pas de
    chemin a offrir ne doit pas tomber pour autant.
    """
    if not cible:
        return style
    return f"{style} {MOT_DE_LIEN} {cible}".strip()


def _porte_l_invite(ligne: str, ascii_seul: bool) -> bool:
    """La ligne porte-t-elle le glyphe d'invite, en MOT a lui seul ?

    Meme frontiere de mot que :func:`jeton_d_etat`, et pour le meme motif : sans
    elle, un `>` ordinaire dans un texte d'ecran ferait passer sa ligne entiere
    en accentuation.
    """
    invite = glyphes(ascii_seul)["invite"]
    return re.search(rf"(?:^|\s){re.escape(invite)}(?=\s|$)", ligne) is not None


def texte_affiche(peint) -> str:
    """Le texte **tel qu'il s'affiche**, sans son style.

    C'est la surface sur laquelle une largeur se mesure et sur laquelle un test
    cherche un libelle. Accepte aussi bien l'objet rendu par :func:`peindre`
    qu'une chaine, pour qu'un appelant n'ait pas a savoir lequel il tient.
    """
    from rich.text import Text

    return peint.plain if isinstance(peint, Text) else str(peint)
