"""Fabrique une maquette 80x24 conforme au DESIGN.md a partir de son contenu.

On ne dessine pas un cadre a la main: on decrit le CONTENU (bandeau, zone
centrale, etat, raccourcis) et le cadre est pose ici, une seule fois. C'est ce
qui garantit que les quatre ateliers rendent la meme grille -- une maquette
recopiee a la main derive d'une colonne au troisieme ecran.

REGLE DES MAJUSCULES DE RACCOURCI (Egan, 2026-08-30): toute LETTRE de raccourci
s'ecrit en MAJUSCULE dans une ligne de raccourcis -- `Q quitter`, `O revoir`,
`E editer le nom` --, alors que la touche cablee cote produit reste la lettre
NUE en minuscule. La divergence est voulue: elle est ecrite en entier dans
`src/mixed_media_utility/tui/coque.py`. Les touches NOMMEES (`Tab`, `Echap`,
`Espace`, `Suppr`, `Ctrl+R`, `F1`) et les glyphes gardent leur forme.

Usage:

    from construire_maquette import maquette, ecrire

    ecrire("E1-1-menu-ateliers.txt", maquette(
        bandeau_gauche="mmu · projet_demo · Ateliers",
        bandeau_droite="3 rushes · 5 lots",
        centre=["", "   ▸ Extraction", "     Scan"],
        etat="",
        raccourcis="⏎ ouvrir   ↑↓ naviguer   Échap projet   F1 aide   Q quitter",
    ))
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[4] / "src"))

from mixed_media_utility.tui import jetons as _jetons  # noqa: E402

LARGEUR = 80
HAUTEUR_CENTRE = 17
#: Hauteur de la grille complete, bordures comprises. Sert aussi de seuil a la
#: garde d'`ecrire()`: au-dela, c'est une annotation humaine.
HAUTEUR_TOTALE = 24

#: Le glyphe de curseur, LU au module de jetons du produit plutot que recopie :
#: une maquette qui dessinerait un autre glyphe que l'ecran livre ne validerait
#: rien, et c'est exactement la classe de defaut que cette revue a trouvee trois
#: fois ailleurs.
GLYPHE_DE_CURSEUR = _jetons.GLYPHES["curseur"]
#: 80 colonnes moins le bord gauche, une espace de respiration de chaque cote et
#: le bord droit.
UTILE = LARGEUR - 4


def colonnes(texte: str) -> int:
    """Largeur en COLONNES de terminal, les glyphes larges comptant double."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in texte)


def _rembourrer(texte: str) -> str:
    """Une ligne de contenu, bordee, exactement a la largeur de la grille."""
    manque = UTILE - colonnes(texte)
    if manque < 0:
        raise ValueError(
            f"ligne trop large de {-manque} colonnes (max {UTILE}) : {texte!r}"
        )
    return f"│ {texte}{' ' * manque} │"


def _bandeau(gauche: str, droite: str) -> str:
    """Bandeau de contexte: contexte a gauche, objet travaille a droite."""
    manque = UTILE - colonnes(gauche) - colonnes(droite)
    if manque < 1:
        raise ValueError(f"bandeau trop large : {gauche!r} + {droite!r}")
    return f"│ {gauche}{' ' * manque}{droite} │"


def maquette(
    *,
    bandeau_gauche: str,
    bandeau_droite: str = "",
    centre: list[str],
    etat: str = "",
    raccourcis: str,
) -> str:
    """Rend la maquette complete, 24 lignes de 80 colonnes.

    ``centre`` est complete par des lignes vides jusqu'aux 17 lignes de la zone
    centrale; en donner davantage est une erreur et non une troncature, parce
    qu'une maquette tronquee en silence ment sur ce qui tient a l'ecran.
    """
    if len(centre) > HAUTEUR_CENTRE:
        raise ValueError(
            f"{len(centre)} lignes de contenu pour {HAUTEUR_CENTRE} disponibles ; "
            "cet ecran ne tient pas dans la grille plancher"
        )
    regle = "─" * (LARGEUR - 2)
    lignes = [
        f"┌{regle}┐",
        _bandeau(bandeau_gauche, bandeau_droite),
        f"├{regle}┤",
    ]
    lignes += [_rembourrer(l) for l in centre]
    lignes += [_rembourrer("")] * (HAUTEUR_CENTRE - len(centre))
    lignes += [
        f"├{regle}┤",
        _rembourrer(etat),
        _rembourrer(raccourcis),
        f"└{regle}┘",
    ]
    return "\n".join(lignes) + "\n"


def regle(titre: str = "", largeur: int = 72, indent: int = 2) -> str:
    """Un filet de section, avec ou sans titre, aligne sur les cartouches."""
    tete = f"── {titre} " if titre else ""
    return " " * indent + tete + "─" * (largeur - colonnes(tete))


def cartouche(
    titre: str, lignes: list[str], largeur: int = 72, indent: int = 2
) -> list[str]:
    """Le panneau chiffre du DESIGN.md section 7.4, borde et aligne au caractere.

    On ne dessine pas ce cadre a la main dans les maquettes: un bord droit
    decale d'une colonne est invisible a la relecture et saute aux yeux dans un
    vrai terminal. Le cadre est donc pose ici, une fois.
    """
    utile = largeur - 4
    marge = " " * indent
    haut = f"┌ {titre} " if titre else "┌"
    dessus = marge + haut + "─" * (largeur - colonnes(haut) - 1) + "┐"
    corps = []
    for ligne in lignes:
        manque = utile - colonnes(ligne)
        if manque < 0:
            raise ValueError(
                f"ligne de cartouche trop large de {-manque} colonnes "
                f"(max {utile}) : {ligne!r}"
            )
        corps.append(f"{marge}│ {ligne}{' ' * manque} │")
    dessous = marge + "└" + "─" * (largeur - 2) + "┘"
    return [dessus, *corps, dessous]


def barre(fait: int, total: int, unite: str, reste: str | None = None) -> str:
    """Ligne d'etat de progression, au format unique du DESIGN.md section 8.

    ``reste`` a ``None`` signifie « aucune mesure reelle encore faite » : rien
    n'est affiche a la place du temps restant. Jamais ``0:00``, qui s'afficherait
    « il reste 0 seconde » -- c'est-a-dire un mensonge et non une absence
    (`EPIC7-ARB-67`).
    """
    pleine = 36
    part = 0 if total == 0 else fait / total
    pleins = round(part * pleine)
    ligne = (
        f"{'▓' * pleins}{'░' * (pleine - pleins)}  {part * 100:.0f} %  "
        f"{fait}/{total} {unite}"
    )
    return f"{ligne}  reste ~ {reste}" if reste else ligne


def barre_double(
    fait: int, total: int, detail: str, reste: str | None = None
) -> str:
    """Progression a deux niveaux (Pdf: lot par lot ET page par page).

    ``detail`` REMPLACE le compte simple au lieu de s'y ajouter: a 80 colonnes
    de plancher, la barre plus le compte plus le detail plus le temps restant
    depassent la ligne. Le detail porte les deux comptes, donc rien n'est perdu
    -- c'est la contrainte de la grille qui choisit la forme, pas l'inverse.
    """
    pleine = 36
    part = 0 if total == 0 else fait / total
    pleins = round(part * pleine)
    ligne = (
        f"{'▓' * pleins}{'░' * (pleine - pleins)}  {part * 100:.0f} %  {detail}"
    )
    return f"{ligne}  reste ~ {reste}" if reste else ligne


class MaquetteAnnotee(RuntimeError):
    """Le fichier cible porte une annotation humaine: on ne l'ecrase pas."""


# **`elider` vit ICI depuis le 2026-09-04, et non plus dans `_gen_c.py`.**
# `_gen_a.py` en a besoin pour l'arbre de `E6-1` : la colonne de coche
# (`EPIC11-ARB-215`) et la colonne de compte d'objets (`EPIC11-ARB-218`)
# prennent ensemble sept colonnes au nom, et le plus long nom d'objet du
# depot -- la planche declaree absente -- en reclamait alors 50 pour 46
# disponibles. Importer `_gen_c` depuis `_gen_a` etait exclu : ce module
# ECRIT ses maquettes a l'import. Le partage passe donc par le module qui
# existe deja pour ca.
def elider(nom: str, largeur: int, queue: int = 20) -> str:
    """Raccourcir un nom de fichier **au milieu**, jamais par la fin.

    La fin porte ce qui IDENTIFIE -- le suffixe `_6f-pay_v3.pdf` qui distingue
    un tirage d'un autre, ou le condensat `-73881cda` de la mire ; la tete
    porte le projet. C'est donc le slug qui cede, et l'ellipse dit ou.
    C'est la regle `P16`, deja payee une fois : une ellipse posee sur le
    condensat rend un nom qui ne designe plus rien.

    `queue` est la longueur de ce qu'on refuse de perdre -- 15 pour un nom de
    tirage (`_6f-pay_vNN.pdf`), 25 pour une mire (`-<8 hexa>_calibration.pdf`).
    """
    if len(nom) <= largeur:
        return nom
    tete = largeur - 1 - queue
    assert tete > 0, (nom, largeur, queue)
    return f"{nom[:tete]}…{nom[-queue:]}"


def ecrire(nom: str, contenu: str, dossier: Path | None = None,
           hauteur_du_curseur: int = 1,
           hauteurs_de_message: dict[str, int] | None = None) -> Path:
    """Ecrit une maquette, SAUF si le fichier existant porte une annotation.

    **Garde ajoutee apres incident** (2026-08-27). Egan relisait les maquettes en
    ecrivant ses remarques a la main SOUS le cadre, dans les `.txt`. Or ces
    fichiers sont des produits de `_gen_*.py`: chaque regeneration les reecrit
    entierement, et trois campagnes de regeneration ont efface ses commentaires
    au fur et a mesure qu'il les posait. Ils n'etaient dans aucun commit -- ils
    n'avaient jamais ete indexes -- donc git ne pouvait rien rendre; ils ont ete
    repeches dans l'historique local de l'editeur, ce qui tenait de la chance.

    La garde est volontairement **grossiere et bloquante**: toute ligne au-dela
    de la grille (24 lignes) est traitee comme une annotation, et l'ecriture
    leve au lieu d'avertir. Un avertissement dans un flot de sortie ne se lit
    pas; une exception arrete la campagne.

    Le geste correct quand elle se declenche: recopier l'annotation dans
    `annotations-egan-*.md` -- qui n'est le produit d'aucun script -- puis
    relancer.

    **`hauteur_du_curseur` DECLARE combien de lignes l'entree du curseur
    occupe** (`EPIC11-ARB-125`, Egan le 2026-08-31). Le generateur est le seul a
    le savoir: il vient de composer ces lignes. Le colorisateur, lui, ne peut que
    deviner, et une ligne de continuation ne porte par construction aucun glyphe
    -- si bien que `E3-0` se peignait sur sa premiere ligne seulement, ce
    qu'Egan a refuse mot pour mot: « pas la seconde ligne de description ».

    Ce que la declaration ne demande PAS au generateur: la position. Il dit une
    HAUTEUR, on retrouve le rang du glyphe dans la grille finale. Un generateur
    qui aurait a compter des rangs se tromperait au premier filet deplace.

    La declaration est ecrite a cote de la maquette, dans `curseurs.json`. Une
    hauteur de 1 -- le cas de toutes les listes, ou les lignes suivantes sont
    d'autres entrees et non des continuations -- n'ecrit rien: le repli par motif
    y rend deja le bon resultat.

    **`hauteurs_de_message` DECLARE la hauteur d'un message d'ETAT**, meme
    geste et meme motif que `hauteur_du_curseur` ci-dessus, applique cette fois
    a la seconde regle de peinture (`EPIC11-ARB-71`, parametre `etats` de
    `jetons.peindre`). Egan, le 2026-09-02, sur trois ecrans differents: « la
    deuxieme ligne de ton avertissement n'est pas colorisee », « l'avertissement
    n'est pas colorise ». Ce n'etaient pas trois retouches mais une REGLE
    absente, et la voici:

    * **un avertissement se colorise ENTIEREMENT**, jamais une ligne sur deux --
      un avertissement multiligne est un seul objet;
    * **la teinte suit ce que le message FAIT**: `substitute` (orange) quand il
      avertit, `absent` (rouge) quand il refuse, `complete` (vert) quand il
      valide -- et jamais du vert sur un interdit.

    La cle est un FRAGMENT du texte de la ligne de tete, la valeur le nombre de
    lignes du message. Un fragment introuvable ou ambigu leve: une declaration
    qui ne designe rien est une erreur d'appariement, exactement la famille que
    la regle des fabriques existe pour attraper.

    **Ce que le generateur n'a PAS a declarer**: les etats d'une seule ligne.
    Ils sont releves tout seuls dans la grille rendue, y compris ceux qu'aucun
    repli par motif ne trouve -- un glyphe pose dans un CARTOUCHE est precede
    de la bordure et d'un seul blanc, donc il n'ouvre pas de colonne et
    `jetons.jeton_d_etat` ne le voit pas. C'est le defaut qu'Egan a nomme sur
    `E5-3b` et il valait pour 27 lignes de 17 maquettes; le produit, lui, le
    ferme depuis `EPIC11-ARB-71` en DONNANT l'etat plutot qu'en le devinant.
    """
    cible = (dossier or Path(__file__).parent / "maquettes") / nom
    cible.parent.mkdir(parents=True, exist_ok=True)
    if cible.exists():
        existant = cible.read_text(encoding="utf-8").rstrip("\n").split("\n")
        surplus = [l for l in existant[HAUTEUR_TOTALE:] if l.strip()]
        if surplus:
            raise MaquetteAnnotee(
                f"{cible.name} porte {len(surplus)} ligne(s) hors grille, "
                f"c'est-a-dire une annotation humaine:\n"
                + "\n".join(f"    {l}" for l in surplus)
                + "\n  Rien n'a ete ecrit. Recopier ces lignes dans "
                "annotations-egan-<date>.md, les retirer du .txt, puis relancer."
            )
    cible.write_text(contenu, encoding="utf-8", newline="\n")
    if hauteur_du_curseur > 1:
        _declarer_le_curseur(cible, contenu, hauteur_du_curseur)
    _declarer_les_etats(cible, contenu, hauteurs_de_message or {})
    return cible


#: Le nom du fichier de declarations, a cote des maquettes. Un seul fichier
#: plutot qu'un satellite par maquette: on le relit d'un coup d'oeil, et une
#: entree perimee s'y voit.
DECLARATIONS = "curseurs.json"


def _declarer_le_curseur(cible: Path, contenu: str, hauteur: int) -> None:
    """Ecrit les rangs de l'entree du curseur dans `curseurs.json`.

    Le rang du glyphe se RETROUVE dans la grille rendue ; seule la hauteur est
    declaree. Une maquette sans glyphe de curseur ne declare rien plutot que de
    lever: certaines n'en portent pas, et une campagne ne doit pas s'arreter
    dessus.
    """
    import json

    lignes = contenu.rstrip("\n").split("\n")[:HAUTEUR_TOTALE]
    rangs = [i for i, l in enumerate(lignes)
             if len(l) > 2 and l[1:-1].strip().startswith(GLYPHE_DE_CURSEUR)]
    registre = cible.parent / DECLARATIONS
    connu = {}
    if registre.exists():
        connu = json.loads(registre.read_text(encoding="utf-8"))
    if not rangs:
        connu.pop(cible.stem, None)
    else:
        depart = rangs[0]
        connu[cible.stem] = list(range(depart, depart + hauteur))
    registre.write_text(
        json.dumps(dict(sorted(connu.items())), indent=2, ensure_ascii=False)
        + "\n", encoding="utf-8", newline="\n")


#: Le fichier des etats declares, a cote de `curseurs.json` et pour le meme
#: motif: un seul registre se relit d'un coup d'oeil, et une entree perimee s'y
#: voit.
ETATS_DECLARES = "etats.json"

#: Les trois glyphes d'etat, LUS au module du produit plutot que recopies --
#: meme regle que `GLYPHE_DE_CURSEUR` ci-dessus. `·` (neutre) n'en est pas un:
#: un lot non scanne n'est ni un manque ni un refus, et le teinter sonnerait
#: l'alarme sur le cas courant.
GLYPHES_D_ETAT = {_jetons.GLYPHES[nom]: nom for nom in _jetons.NOMS_D_ETAT}


#: **Ce qui peut preceder un glyphe d'etat.** Les deux premieres alternatives
#: sont `jetons._OUVRE_UNE_COLONNE`, verbatim ; la troisieme -- la bordure d'un
#: CARTOUCHE suivie d'un seul blanc -- est l'elargissement, et il est le coeur
#: de la correction du 2026-09-02. `jetons.peindre` documente lui-meme le cas :
#: « un glyphe dans un cartouche est precede de la bordure et d'UN blanc : il
#: n'ouvre pas de colonne [...] aucun glyphe d'etat pose dans un cartouche
#: n'etait colore ». Le produit le ferme en DONNANT l'etat ; c'est ce que la
#: declaration fait ici.
_OUVRE_UNE_COLONNE = r"(?:^[ \t]*|[ \t]{2,}|\u2502[ \t])"

#: `jetons._PORTE_UN_LIBELLE`, verbatim et NON relache. Le relacher recolorerait
#: l'entree d'explorateur litteralement nommee `x` dont la taille est calee a
#: droite -- le cas mesure que `jetons.peindre` nomme comme la fausse piste.
_PORTE_UN_LIBELLE = r"(?:[ \t](?=[^ \t])|[ \t]*$)"


def _etat_structurel(ligne: str) -> str | None:
    """L'etat qu'une ligne porte **en position de colonne d'etat**.

    C'est la regle du produit, elargie a la seule bordure de cartouche. Elle
    reste etroite a dessein : une prose separe ses mots par UN blanc, si bien
    qu'un `✕` au milieu d'une ligne de journal -- texte venu du COEUR, dont
    aucun ecran ne connait l'etat -- n'est pas un etat. Le relacher ferait
    peindre a la maquette ce que le produit ne peindra pas, ce qui est
    exactement la divergence que ce mecanisme existe pour empecher.
    """
    interne = ligne[1:-1] if ligne.startswith("\u2502") else ligne
    for glyphe, nom in GLYPHES_D_ETAT.items():
        if re.search(_OUVRE_UNE_COLONNE + re.escape(glyphe) + _PORTE_UN_LIBELLE,
                     interne):
            return nom
    return None


def _etat_de_la_ligne(ligne: str) -> str | None:
    """L'etat porte par une ligne, glyphe pris OU QU'IL SOIT.

    Sert uniquement aux lignes que le generateur DESIGNE nommement : lui seul
    sait qu'un glyphe colle a un chiffre (`( ) 4●`, la demande d'Egan du
    2026-09-02) est un etat et non un caractere de prose.
    """
    interne = ligne[1:-1] if ligne.startswith("\u2502") else ligne
    for glyphe, nom in GLYPHES_D_ETAT.items():
        rang = interne.find(glyphe)
        if rang < 0:
            continue
        suite = interne[rang + len(glyphe):]
        if not suite.strip() or suite.startswith(" "):
            return nom
    return None


def _declarer_les_etats(cible: Path, contenu: str,
                        hauteurs: dict[str, int]) -> None:
    """Ecrit `<maquette> -> {rang: etat}` dans `etats.json`.

    Deux passes. La premiere releve tout glyphe d'etat de la ZONE CENTRALE --
    le bandeau, la ligne d'etat et la ligne de raccourcis ont leur propre regle
    de peinture, qui ne les regarde pas. La seconde etend chaque message
    declare a ses lignes de continuation, qui ne portent par construction aucun
    glyphe.
    """
    import json

    lignes = contenu.rstrip("\n").split("\n")[:HAUTEUR_TOTALE]
    premiere, derniere = 3, HAUTEUR_TOTALE - 3   # bornes de la zone centrale
    declares: dict[int, str] = {}
    for rang in range(premiere, derniere):
        etat = _etat_structurel(lignes[rang])
        if etat:
            declares[rang] = etat

    for fragment, hauteur in hauteurs.items():
        tetes = [rang for rang in range(premiere, derniere)
                 if fragment in lignes[rang] and _etat_de_la_ligne(lignes[rang])]
        if len(tetes) != 1:
            raise ValueError(
                f"{cible.name}: le fragment {fragment!r} designe {len(tetes)} "
                "ligne(s) d'etat, il en faut exactement une")
        depart = tetes[0]
        declares[depart] = _etat_de_la_ligne(lignes[depart])
        for rang in range(depart + 1, depart + hauteur):
            if rang >= derniere or not lignes[rang][1:-1].strip():
                raise ValueError(
                    f"{cible.name}: le message {fragment!r} declare {hauteur} "
                    f"lignes, mais la ligne {rang} est vide ou hors zone")
            declares[rang] = declares[depart]

    registre = cible.parent / ETATS_DECLARES
    connu = {}
    if registre.exists():
        connu = json.loads(registre.read_text(encoding="utf-8"))
    if declares:
        connu[cible.stem] = {str(r): declares[r] for r in sorted(declares)}
    else:
        connu.pop(cible.stem, None)
    if not declares and not registre.exists():
        # Rien a dire et rien a corriger : on n'ecrit pas un registre vide, pour
        # la meme raison que `hauteur_du_curseur=1` n'ecrit rien -- un fichier
        # qu'on relit d'un coup d'oeil ne se remplit pas de vide.
        return
    registre.write_text(
        json.dumps(dict(sorted(connu.items())), indent=2, ensure_ascii=False)
        + "\n", encoding="utf-8", newline="\n")
