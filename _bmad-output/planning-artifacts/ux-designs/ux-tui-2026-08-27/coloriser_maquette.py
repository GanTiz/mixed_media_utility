# -*- coding: utf-8 -*-
"""Colorier une maquette 80x24 avec les VRAIES regles de peinture de la TUI.

Ce module n'invente aucune couleur : il lit `jetons` et rejoue les regles qui
existent deja dans le code livre --

* la coque (`coque.feuille`) : cadre et filets en `muted`, bandeau en `data`,
  ligne d'etat et ligne de raccourcis en `muted` ;
* `jetons.peindre` (`EPIC11-ARB-47`) : dans la zone centrale, **la ligne du
  curseur** passe en gras et en `accent` ; **une ligne qui porte un glyphe
  d'etat** prend la couleur de cet etat, ligne entiere ;
* `jetons.peindre(etats=...)` (`EPIC11-ARB-71`) : **l'etat DONNE** l'emporte
  sur l'etat devine, et le repli ne sert que les lignes dont aucun generateur
  n'a declare l'etat. C'est le troisieme mecanisme, ajoute le 2026-09-02 : sans
  lui la maquette ne pouvait colorier ni un glyphe pose dans un CARTOUCHE -- il
  n'y ouvre pas de colonne -- ni la ligne de CONTINUATION d'un message, qui ne
  porte par construction aucun glyphe. Egan a vu les deux, sur trois ecrans
  differents, et le produit fermait deja les deux depuis `EPIC11-ARB-71` : la
  maquette peignait donc moins que ce que le produit sait peindre, ce qui est
  la divergence exacte que ce module existe pour empecher.

Une seule chose est ajoutee, et elle est signalee comme telle : `TOUCHES_EN_ACCENT`
peint les touches (`←`, `⏎`) des deux etiquettes vives. C'est une **troisieme
regle proposee**, pas une regle en vigueur -- elle attend l'arbitrage d'Egan.

Rend du SVG (pour le depot) et des fragments HTML (pour la note commentable).
Les deux sortent des memes segments : deux rendus qui divergeraient feraient
valider autre chose que ce qui sera livre.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).parents[4] / "src"))

from mixed_media_utility.tui import jetons  # noqa: E402

#: Le fond. `DESIGN.md` `EPIC11-ARB-43` : la palette est reglee pour un fond
#: sombre, et c'est contre `surface-canvas` que ses contrastes sont mesures.
FOND = "#141414"

#: Regle proposee, hors des deux regles en vigueur. Voir le docstring.
TOUCHES_EN_ACCENT = True
TOUCHES = ("←", "⏎")

CADRE = set("┌┐└┘├┤│─")

#: Hauteur de la grille. Tout ce qui la depasse dans un `.txt` est une
#: annotation manuscrite d'Egan, jamais du contenu d'ecran.
HAUTEUR_GRILLE = 24


def _couleur(nom: str) -> str:
    return jetons.couleur(nom)


def segments_de_ligne(ligne: str, zone: str, du_curseur: bool = False,
                      repli: bool = True, etat: str | None = None,
                      ) -> list[tuple[str, str, bool]]:
    """Decoupe une ligne en `(texte, couleur, gras)`, selon sa zone.

    Les deux caracteres de cadre d'une ligne de contenu sont toujours servis
    a part et en `muted` : le cadre est de la structure, pas de l'information.

    `du_curseur` dit que cette ligne appartient a l'entree du curseur. C'est
    l'equivalent exact de `lignes_du_curseur` cote produit (`jetons.peindre`,
    `EPIC11-ARB-71`) : le rang est **donne**, il ne se devine pas.

    `repli` autorise la reconnaissance par motif. Elle est **eteinte des que des
    rangs sont donnes**, exactement comme `jetons.peindre` le fait par son
    `elif ligne_du_curseur is None` : sans cela, une maquette qui donne ses
    rangs verrait quand meme le glyphe teinter une ligne de plus, et les deux
    rendus divergeraient sur la seule chose que ce module existe pour tenir
    identique.
    """
    if zone == "cadre":
        return [(ligne, _couleur("muted"), False)]

    bord_g, corps, bord_d = ligne[0], ligne[1:-1], ligne[-1]
    peints = [(bord_g, _couleur("muted"), False)]

    if zone in ("etat", "raccourcis"):
        peints.append((corps, _couleur("muted"), False))
    elif zone == "bandeau":
        peints.append((corps, _couleur("data"), False))
    elif zone == "filet":
        # Une ligne de filet dans la zone centrale : c'est du cadre dessine
        # par le contenu, il prend donc la couleur du cadre.
        peints.append((corps, _couleur("muted"), False))
    else:
        peints.extend(_segments_du_centre(corps, du_curseur, repli, etat))

    peints.append((bord_d, _couleur("muted"), False))
    return peints


def _segments_du_centre(corps: str, du_curseur: bool = False,
                        repli: bool = True, etat: str | None = None,
                        ) -> list[tuple[str, str, bool]]:
    """La zone centrale, par les deux regles de `jetons.peindre`.

    `etat` DONNE l'etat de la ligne, exactement comme le parametre `etats` de
    `jetons.peindre` (`EPIC11-ARB-71`) : il l'emporte sur le repli par motif et
    ne l'emporte pas sur le curseur -- **le meme ordre que le produit**, et il
    n'est pas negociable. Deux ordres qui divergeraient feraient valider une
    maquette contre autre chose que ce qui sera livre, ce que ce module existe
    pour empecher.
    """
    # Regle 1, forme DONNEE : le rang appartient a l'entree du curseur. Elle
    # passe avant le vide, parce qu'une entree multi-lignes peut porter une
    # ligne de continuation qui, elle, ne dit rien -- et elle est teintee
    # quand meme, sans quoi on retrouve le blanc au milieu de l'entree
    # qu'Egan a vu le 2026-08-31.
    if du_curseur:
        return [(corps, _couleur("accent"), True)]

    nu = corps.strip()
    if not nu:
        return [(corps, _couleur("data"), False)]

    # Regle 1, forme DEVINEE : le repli par motif. Il ne trouve qu'UN rang, et
    # seulement si le glyphe ouvre la ligne une fois `strip()` faite -- deux
    # limites epinglees par le banc, et le motif pour lequel un ecran a
    # entrees multi-lignes DOIT donner ses rangs plutot que les laisser
    # deviner.
    if repli and nu.startswith(jetons.GLYPHES["curseur"]):
        return [(corps, _couleur("accent"), True)]

    # Regle 1 bis, PROPOSEE : le champ qui a le focus. Le glyphe `>` dit deja
    # « ce champ a le focus » au `DESIGN.md` section 6 ; ce qui est propose ici,
    # c'est de traiter la ligne comme celle du curseur -- parce qu'elle l'EST :
    # quand la saisie a le focus, la liste n'a plus de curseur, et rien d'autre
    # ne le montrerait. Demande d'Egan (note `k-tab`) : « il faut que cet etat
    # soit visible. Surbrillance ? Surlignage ? Que proposes-tu ? »
    if re.search(rf"(?:^|\s){re.escape(jetons.GLYPHES['invite'])}(?=\s|$)",
                 corps):
        return [(corps, _couleur("accent"), True)]

    # Regle proposee : la touche d'une etiquette vive, en accentuation.
    if TOUCHES_EN_ACCENT and nu[0] in TOUCHES:
        rang = corps.index(nu[0])
        reste = corps[rang + 1:]
        jeton = f"state-{etat}" if etat else _jeton_d_etat(reste)
        return [
            (corps[:rang], _couleur("muted"), False),
            (nu[0], _couleur("accent"), True),
            (reste, _couleur(jeton) if jeton else _couleur("data"), False),
        ]

    # Regle 2 : un glyphe d'etat teinte SA LIGNE, entiere. **L'etat DONNE
    # l'emporte sur l'etat devine**, et le repli ne sert que les lignes dont
    # aucun generateur n'a declare l'etat -- copie conforme de la ligne
    # `nom = etats.get(rang)` de `jetons.peindre`.
    jeton = f"state-{etat}" if etat else _jeton_d_etat(corps)
    return [(corps, _couleur(jeton) if jeton else _couleur("data"), False)]


def _jeton_d_etat(texte: str) -> str | None:
    """Delegue a `jetons.jeton_d_etat` : la maquette ne redit pas la regle.

    La version precedente de cette fonction rejouait a la main la recherche
    dans `ETAT_DE_GLYPHE`, replis ASCII compris -- donc elle teintait en rouge
    toute ligne portant un `x`. Egan l'a vu sur `X8` (« pourquoi la deuxieme
    ligne est rouge ? »), et le meme defaut etait dans le produit.
    """
    return jetons.jeton_d_etat(texte)


def zones(lignes: list[str]) -> list[str]:
    """Nomme la zone de chacune des 24 lignes de la grille."""
    noms = []
    for rang, ligne in enumerate(lignes):
        if rang in (0, 2, len(lignes) - 3, len(lignes) - 1):
            noms.append("cadre")
        elif rang == 1:
            noms.append("bandeau")
        elif rang == len(lignes) - 3 + 1:
            noms.append("etat")
        elif rang == len(lignes) - 2:
            noms.append("raccourcis")
        elif set(ligne[1:-1].strip()) <= {"─"} and ligne[1:-1].strip():
            noms.append("filet")
        else:
            noms.append("centre")
    return noms


def peindre_maquette(texte: str, lignes_du_curseur: "Iterable[int] | None" = None,
                     etats: "dict[int, str] | None" = None,
                     ) -> list[list[tuple[str, str, bool]]]:
    """Peint la grille, et accepte les rangs de l'entree du curseur.

    Meme nom de parametre que `jetons.peindre` : deux contrats qui divergeraient
    par leur vocabulaire feraient valider une maquette contre autre chose que ce
    qui sera livre, ce que ce module existe precisement pour empecher.

    **`[]` n'est pas `None`, et c'est delibere** (finding `R15`). Une liste vide
    DONNEE dit « aucun rang n'est sous le curseur » -- l'entree est hors fenetre,
    le menu est vide -- et elle eteint donc le repli comme n'importe quelle
    declaration. `None` dit « je ne declare rien », et le repli reprend la main.
    Les deux comportements etaient plausibles et aucun n'etait mesure des deux
    cotes ; celui-ci est celui de `jetons.peindre`, dont le `is not None` fait
    la meme distinction.
    """
    lignes = texte.rstrip("\n").split("\n")
    donnes = lignes_du_curseur is not None
    rangs = {int(r) for r in lignes_du_curseur} if donnes else set()
    # **Les memes bornes que `jetons.peindre`, et pour le meme motif**
    # (finding `R16`). Un rang hors grille etait avale ici et levait la-bas :
    # une maquette validee sur de mauvais rangs passait pour validee, ce qui est
    # exactement ce que ce module existe pour empecher. Les deux contrats
    # divergeaient sur l'entree fautive -- le seul cas ou la divergence compte.
    hors_bornes = sorted(r for r in rangs if not 0 <= r < len(lignes))
    if hors_bornes:
        raise IndexError(
            f"rang de curseur hors bornes: {hors_bornes} pour "
            f"{len(lignes)} ligne(s)")
    # **Les memes deux refus durs que `jetons.peindre`**, et pour le meme motif :
    # un jeton mal orthographie qui rendrait une couleur par defaut produirait
    # une maquette silencieusement hors charte, et un rang qui ne designe aucune
    # ligne est une erreur d'appariement -- celle que la regle des fabriques
    # existe pour attraper, et qui ne se voit jamais a l'oeil.
    donnes_d_etat = {int(r): n for r, n in (etats or {}).items()}
    for rang, nom in donnes_d_etat.items():
        if nom not in jetons.NOMS_D_ETAT:
            connus = ", ".join(jetons.NOMS_D_ETAT)
            raise KeyError(
                f"etat inconnu: {nom!r} au rang {rang}. Connus: {connus}")
        if not 0 <= rang < len(lignes):
            raise IndexError(
                f"rang d'etat hors bornes: {rang} pour {len(lignes)} ligne(s)")
    return [segments_de_ligne(l, z, rang in rangs, not donnes,
                              donnes_d_etat.get(rang))
            for rang, (l, z) in enumerate(zip(lignes, zones(lignes)))]


# ---------------------------------------------------------------- SVG -------

LARGEUR_CAR = 8.4
HAUTEUR_LIGNE = 17.0
POLICE = ("ui-monospace, 'DejaVu Sans Mono', 'SF Mono', Menlo, Consolas, "
          "'Liberation Mono', monospace")


def en_svg(texte: str, titre: str,
           lignes_du_curseur: "Iterable[int] | None" = None,
           etats: "dict[int, str] | None" = None) -> str:
    peint = peindre_maquette(texte, lignes_du_curseur, etats)
    largeur = 80 * LARGEUR_CAR + 24
    hauteur = len(peint) * HAUTEUR_LIGNE + 24
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largeur:.0f}" '
        f'height="{hauteur:.0f}" viewBox="0 0 {largeur:.0f} {hauteur:.0f}" '
        f'role="img" aria-label="{html.escape(titre)}">',
        f'<title>{html.escape(titre)}</title>',
        f'<rect width="100%" height="100%" rx="6" fill="{FOND}"/>',
        f'<g font-family="{POLICE}" font-size="14" '
        # `xml:space` ne suffit PAS, et c'est le second volet du defaut du
        # 2026-08-29 : il n'est honore que dans un document XML. **Inline dans
        # une page HTML**, c'est la regle CSS des blancs qui s'applique, les
        # espaces de remplissage des lignes de 80 colonnes sont ecrases, et le
        # moteur etale les glyphes restants sur toute la largeur imposee par
        # `textLength`. Mesure : une ligne de titre de 78 caracteres rendait
        # 252,8 px de glyphes pour 655,2 px demandes. `style="white-space:pre"`
        # porte la meme intention en CSS, donc dans les deux mondes. Les deux
        # sont poses : un moteur qui honore l'un ou l'autre rend juste.
        'xml:space="preserve" style="white-space:pre" '
        'dominant-baseline="middle">',
    ]
    for rang, segments in enumerate(peint):
        y = 12 + (rang + 0.5) * HAUTEUR_LIGNE
        colonne = 0
        for morceau, couleur, gras in segments:
            if morceau:
                x = 12 + colonne * LARGEUR_CAR
                poids = ' font-weight="700"' if gras else ""
                # `textLength` force la largeur exacte du segment : sans lui,
                # l'ecart entre l'avance reelle de la police et LARGEUR_CAR
                # decale le bord droit du cadre de deux ou trois pixels.
                #
                # **`spacing` et surtout pas `spacingAndGlyphs`** (corrige le
                # 2026-08-29, defaut trouve par Egan : « les textes sont
                # affreusement deformes »). `spacingAndGlyphs` etire les
                # GLYPHES eux-memes pour atteindre la largeur cible : des que
                # la police de rendu n'a pas exactement l'avance supposee --
                # c'est-a-dire des qu'on sort de la machine qui a genere le
                # SVG --, chaque caractere est ecrase ou allonge. `spacing`
                # n'ajuste que les ECARTS entre glyphes : la grille tombe
                # juste a la colonne pres, et les lettres gardent leur forme.
                large = len(morceau) * LARGEUR_CAR
                out.append(
                    f'<text x="{x:.1f}" y="{y:.1f}" fill="{couleur}"{poids} '
                    f'textLength="{large:.1f}" lengthAdjust="spacing">'
                    f'{html.escape(morceau)}</text>')
            colonne += len(morceau)
    out += ["</g>", "</svg>"]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- HTML ------

def en_html(texte: str,
            lignes_du_curseur: "Iterable[int] | None" = None,
            etats: "dict[int, str] | None" = None) -> str:
    """Le meme rendu, en `<span>`, pour la note commentable."""
    lignes = []
    for segments in peindre_maquette(texte, lignes_du_curseur, etats):
        morceaux = []
        for morceau, couleur, gras in segments:
            if not morceau:
                continue
            poids = "font-weight:700;" if gras else ""
            morceaux.append(f'<span style="color:{couleur};{poids}">'
                            f'{html.escape(morceau)}</span>')
        lignes.append("".join(morceaux))
    return "\n".join(lignes)


def rangs_declares(source: Path) -> dict[str, list[int]]:
    """Les rangs de curseur DECLARES par les generateurs (`EPIC11-ARB-125`).

    Le fichier peut ne pas exister : une maquette non declaree retombe sur le
    repli par motif, avec ses deux limites connues -- un seul rang, et seulement
    si le glyphe ouvre la ligne.
    """
    registre = source / "curseurs.json"
    if not registre.exists():
        return {}
    return json.loads(registre.read_text(encoding="utf-8"))


def etats_declares(source: Path) -> dict[str, dict[int, str]]:
    """Les etats DECLARES par les generateurs (regle de colorisation du
    2026-09-02).

    Symetrique exact de :func:`rangs_declares` : le generateur sait ce qu'il
    vient d'ecrire, le colorisateur ne peut que le deviner -- et le repli par
    motif echoue par construction sur deux formes, la ligne de continuation
    d'un message replie et le glyphe pose dans un cartouche. Le produit ferme
    les deux depuis `EPIC11-ARB-71` en DONNANT l'etat ; les maquettes le
    faisaient encore deviner, et c'est ce qu'Egan a vu trois fois de suite.
    """
    registre = source / "etats.json"
    if not registre.exists():
        return {}
    brut = json.loads(registre.read_text(encoding="utf-8"))
    return {nom: {int(r): etat for r, etat in table.items()}
            for nom, table in brut.items()}


def main(source: Path | None = None, cible: Path | None = None) -> int:
    """Colorise les maquettes relues. Rend le nombre de SVG ecrits.

    Les deux dossiers sont **des parametres**, avec les vrais par defaut : sans
    cela, la seule facon de mesurer ce chemin serait d'ecrire dans le depot. La
    premiere version du test de `R10` s'en est passee -- elle appelait
    `peindre_maquette` directement -- et les deux mutants qui comptaient y ont
    SURVECU : le finding portait precisement sur le cablage de `main()`, pas sur
    la peinture. Un test qui ne joue pas le chemin fautif ne le mesure pas.
    """
    source = source or Path(__file__).parent / "maquettes"
    cible = cible or Path(__file__).parent / "maquettes-couleur"
    cible.mkdir(parents=True, exist_ok=True)
    # **Sans cette lecture, le parametre neuf n'a AUCUN appelant de production**
    # (finding `R10` de la revue du 2026-08-31). `main()` est le seul producteur
    # de `maquettes-couleur/` : la story 11.2c avait livre a `peindre_maquette`
    # la capacite de recevoir des rangs, et personne ne les lui donnait --
    # regenerer reproduisait a l'identique le rendu qu'Egan avait refuse.
    declares = rangs_declares(source)
    etats = etats_declares(source)
    ecrits = 0
    # `X*` etait le seul motif : les neuf ecrans d'Extraction n'avaient donc
    # aucune version couleur, alors que l'AC 1.1 de la story 11.4 les veut
    # colorises AVANT la premiere ligne de code. Les deux motifs sont nommes
    # plutot que reunis en `*.txt` : les zones B et C portent des ecrans que
    # personne n'a encore relus a la couleur, et les colorier ici les ferait
    # passer pour valides.
    # `E3-*` rejoint les deux motifs le 2026-08-30, pour la story 11.5 : les
    # SEPT ecrans du temps 1 du Scan (`E3-0` a `E3-4b`) se relisent a la
    # couleur avant leur premiere ligne de code, exactement comme les `E2-*`
    # l'ont fait pour la 11.4.
    #
    # **Le filtre qui ecartait le temps 2 est RETIRE le 2026-09-01**, et son
    # propre motif disait quand il tomberait : « les CINQ ecrans du temps 2
    # (`E3-5` a `E3-9`) sont ecartes NOMMEMENT : ils relevent de la 11.6, **dont
    # la fiche n'est pas ecrite**, et les colorier les ferait passer pour
    # relus. » La fiche est ecrite
    # (`11-6-atelier-scan-temps-2-ecriture.md`), donc la condition tombe.
    #
    # Il est **retire** et non vide : un ensemble vide laisserait la mecanique
    # d'exclusion en place sans son motif, et la prochaine relecture ne saurait
    # pas si elle est morte ou si elle attend quelque chose. Le motif `E3-*`
    # suffit desormais seul.
    #
    # **`T6-1` entre par un motif A LUI, et c'est deliberement etroit.** Aucune
    # maquette `T*` n'entrait dans le colorisateur jusqu'ici, et il n'est pas
    # question d'ouvrir `T*.txt` en bloc : `T3-1`, `T4-1` et `T5-1` sont des
    # ecrans que personne n'a relus a la couleur, et les colorier les ferait
    # passer pour valides -- c'est exactement le raisonnement qui a fait nommer
    # les deux premiers motifs plutot que de prendre `*.txt`. `T6-1` est le seul
    # `T*` que la 11.6 dessine : c'est son ecran d'interruption.
    #
    # **`T4-2` entre le 2026-09-05, et `T4-1` reste dehors** -- ce qui est
    # exactement la distinction que le paragraphe precedent pose. `T4-2` est
    # l'ecran d'ecrasement redessine par `EPIC11-ARB-245` : il est soumis a
    # Egan MAINTENANT, et la couleur est ce avec quoi il le relit. `T4-1`, lui,
    # reste un ecran que personne n'a relu a la couleur, et il est de surcroit
    # perime sur sa forme (issues horizontales, `EPIC11-ARB-45` les a rendues
    # verticales). Un motif `T4-*` les ferait entrer tous les deux et
    # donnerait a `T4-1` une apparence de validite qu'elle n'a pas.
    #
    # **`E5-*` rejoint les motifs le 2026-09-01, pour la story 11.7.** Les huit
    # ecrans de l'atelier Pdf n'etaient ecartes par AUCUN ensemble nomme -- ils
    # etaient simplement hors des motifs, ce qui est le regime normal d'une
    # maquette que personne n'a encore relue a la couleur. Il n'y avait donc
    # rien a « retirer » ici comme `TEMPS_2_DU_SCAN` l'a ete la veille : il y
    # avait un motif a AJOUTER. La condition est la meme que celle qui a fait
    # entrer `E2-*` puis `E3-*` : les ecrans se relisent a la couleur AVANT
    # leur premiere ligne de code.
    #
    # **`E4-*` rejoint les motifs le 2026-09-02, pour la story 11.8** (lot A).
    # Il en etait ecarte NOMMEMENT, et son motif disait quand il tomberait :
    # « personne ne l'a relu, et le coloriser le ferait passer pour valide ».
    # La condition est desormais remplie, et c'est exactement celle qui a fait
    # entrer `E2-*`, `E3-*`, `E5-*` puis `E6-*` : **les ecrans se relisent a la
    # couleur AVANT leur premiere ligne de code**, et l'AC 1.2 de la story 11.8
    # l'exige mot pour mot (« c'est le SVG qu'Egan relit, et un `.txt` corrige
    # sans recolorisation laisse une image perimee »).
    #
    # Les huit ecrans entrent **apres la passe de correction** du meme jour :
    # les six d'origine dataient du 2026-08-27 et portaient trente-deux
    # passages perimes, dont vingt de comportement. Les coloriser AVANT cette
    # passe aurait fait exactement ce que le motif d'exclusion redoutait.
    #
    # La couleur y porte de l'INFORMATION et non du style, et deux ecrans le
    # montrent mieux que les autres : `E4-3b` peint son avertissement
    # d'ecrasement **entierement** en orange (`state-substitute`, deux lignes
    # declarees) parce que la teinte suit ce que le message FAIT ; `E4-4`
    # n'affiche aucun vert, l'encodage n'ayant rien de valide a montrer tant
    # qu'il tourne. Deux maquettes sont NEUVES et n'existaient dans aucune
    # version relue : `E4-3b` (le conflit de master, qu'`EPIC11-ARB-89` exige)
    # et `E4-4b` (la pre-verification, seule phase comptable).
    #
    # **`E6-*` rejoint les motifs le 2026-09-01, pour la story 11.11** (lot D).
    # Meme condition que `E2-*`, `E3-*` puis `E5-*` : les sept ecrans du palier
    # Projet se relisent a la couleur AVANT leur premiere ligne de code -- c'est
    # litteralement ce que le lot D exige, « a soumettre a Egan AVANT le lot B ».
    # Les couleurs y portent de l'information et non du style : `state-absent`
    # sur un objet declare-et-absent, `state-substitute` sur un objet
    # present-et-non-declare, et ce sont ces deux vocabulaires que l'AC 2.4
    # demande de lire du coeur.
    #
    # **`E1-1` entre par un motif A LUI, et c'est deliberement etroit** -- meme
    # geste que `T6-1` ci-dessus. Aucune maquette `E0-*`/`E1-*` n'entrait ici,
    # et il n'est pas question d'ouvrir `E1-*.txt` en bloc. `E1-1` est le menu
    # des ateliers, et la story 11.11 en change la ligne `Projet` : Egan doit
    # voir la ligne qu'il valide, pas la lire recopiee dans une note.
    fichiers = sorted(set(source.glob("X*.txt"))
                      | set(source.glob("E1-1-*.txt"))
                      | set(source.glob("E2-*.txt"))
                      | set(source.glob("E3-*.txt"))
                      | set(source.glob("E4-*.txt"))
                      | set(source.glob("E5-*.txt"))
                      | set(source.glob("E6-*.txt"))
                      | set(source.glob("T4-2-*.txt"))
                      | set(source.glob("T6-1-*.txt")),
                      key=lambda c: c.name)
    for fichier in fichiers:
        # **La grille SEULE, jamais les annotations.** Les `.txt` d'Egan portent
        # ses remarques manuscrites SOUS le cadre ; `zones()` compte les zones a
        # partir de `len(lignes)`, donc une maquette annotee ferait prendre la
        # ligne d'etat pour du contenu et une ligne de note pour le bas du
        # cadre. Les `X*` n'en portaient aucune, les `E2-*` en portent cinq :
        # le defaut n'existait pas tant que le motif etait `X*`.
        grille = "\n".join(
            fichier.read_text(encoding="utf-8").split("\n")[:HAUTEUR_GRILLE])
        svg = en_svg(grille, fichier.stem, declares.get(fichier.stem),
                     etats.get(fichier.stem))
        (cible / f"{fichier.stem}.svg").write_text(svg, encoding="utf-8",
                                                   newline="\n")
        ecrits += 1
    print(f"{ecrits} maquettes coloriees dans {cible.name}/")
    return ecrits


if __name__ == "__main__":
    main()
