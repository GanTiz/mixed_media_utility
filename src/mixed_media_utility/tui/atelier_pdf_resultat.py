# -*- coding: utf-8 -*-
"""L'atelier Pdf, LE COMPTE RENDU : `E5-5`, `E5-5b`, `E5-5c` (11.7, AC 10).

**Un seul ecran, trois etats** -- et c'est le point de ce module. `E5-5` est la
passe courte, dont la liste tient entiere ; `E5-5b` est la passe longue a
l'**arrivee**, curseur sur les issues ; `E5-5c` est la meme apres un `Tab`,
curseur dans la liste. Les trois sortent de la meme classe : trois classes
auraient fait diverger trois fois le meme tableau.

La bascule de zone, et l'arbitrage qu'elle NE contredit pas
------------------------------------------------------------

Le retour d'Egan qui l'a fait naitre, verbatim : « si on fait 100 lots d'un
coup on doit tout faire défiler avant d'atteindre les choix ? Non **il faut
basculer d'une zone à l'autre si possible. TAB ?** »

`EPIC11-ARB-50` interdit **deux curseurs simultanes**, pas deux zones
navigables -- et le paragraphe ou il est ecrit est celui de l'explorateur, qui
bascule au `Tab`. `Tab` ne **duplique** donc pas le curseur, il le **deplace** :
les issues restent dessinees et entieres quand la liste prend la main, elles
perdent seulement la fleche. Trois paires du depot le font deja (`X1`/`X5`,
`E2-3`/`E2-3b`, `E6-1`/`E6-1b`).

`Tab journal` est RETIRE, et c'est une correction, pas une perte
-----------------------------------------------------------------

La ligne du produit pour un ecran de compte rendu est
`atelier_scan_parcours.RACCOURCIS_RAPPORT`, et elle n'a **jamais** porte de
`Tab`. Le retrait a une seconde raison, et c'est elle qui l'a declenche : il
**libere** la touche pour la bascule de zone. Sans lui, la meme touche aurait
eu deux sens sur deux etats du meme ecran -- deplier le journal ici, entrer
dans la liste la.

Ce que la ligne du bas montre, et rien d'autre
-----------------------------------------------

`DESIGN.md` section 4 : « elle ne montre que ce qui marche sur l'ecran
courant ». Dans la liste, `⏎` n'a **rien** a valider -- un fichier ecrit n'est
pas une issue --, donc il **part** de la ligne. Annoncer une touche inerte est
le defaut que la story 11.5 a paye quarante fois.

La fenetre de liste ne se reinvente pas
----------------------------------------

`jetons.fenetre_de_liste` et `jetons.recadrer_la_fenetre` existent, cinq
surfaces s'en servent, et la ligne `…` s'y reserve **avant** le decoupage. Les
fleches **ne defilent jamais** : elles deplacent le curseur, et la fenetre
suit, un rang a la fois. Ce module les appelle ; il ne recalcule aucune borne,
et une frontiere AST le mesure.

La liste quitte le cartouche des qu'elle se parcourt, et c'est une contrainte
d'outillage nommee ici pour qu'une revue ne la rouvre pas : le colorisateur ne
reconnait le curseur que si `▸` ouvre la ligne apres `strip()`, et un `▸` pose
dans un cartouche est precede du bord `│`. `E5-5` garde donc son cartouche --
sa liste ne se parcourt pas.

Le rang de tirage est AFFICHE, jamais recalcule
------------------------------------------------

`EPIC11-ARB-92`. Chaque `PlancheEcrite` porte le rang que la passe a
reellement ecrit ; ce module ne resout, ne compte et ne derive rien. Une
frontiere AST mesure qu'il n'appelle aucun resolveur de rang.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

from textual.widget import Widget
from textual.widgets import Static

from . import jetons
from .atelier_extraction import Composition, filet_titre, ligne_de_titre
from .atelier_scan import INDENT_DU_CURSEUR
from .atelier_scan_parcours import RACCOURCIS_RAPPORT
from .execution import (EcranResultat, bloc_peint,
                        ouvrir_dans_l_explorateur_du_systeme)
from .panneau import LigneChiffree, Panneau

# ===========================================================================
# Le bandeau et les lignes de raccourcis
# ===========================================================================

#: Le segment du milieu du bandeau, `mmu · projet_demo · **Pdf**`.
PALIER_DU_RESULTAT = "Pdf"

#: `E5-5` -- **exactement** la ligne du produit pour un compte rendu (AC 10.5).
#: Elle est importee et jamais recopiee : `atelier_scan_parcours` la possede, et
#: une seconde redaction divergerait au premier ajustement de libelle.
#:
#: MESURE: 47/52
RACCOURCIS_LISTE_ENTIERE = RACCOURCIS_RAPPORT

#: Le jeton de la bascule de zone. **`Tab champ`**, sur les deux etats -- le
#: meme libelle pour la meme touche. Deux libelles (« la liste » d'un cote,
#: « les issues » de l'autre) auraient fait deux mots pour un seul geste, ce que
#: la regle de nommage `F-17` interdit ; la maquette validee porte `Tab champ`
#: des deux cotes.
JETON_DE_LA_BASCULE = "Tab champ"

#: Le separateur des jetons d'une ligne de raccourcis : **deux** espaces
#: (`EPIC11-ARB-122`).
SEPARATEUR_DES_JETONS = "  "

#: `E5-5b` -- la ligne d'arrivee : le curseur est sur les issues, donc `⏎` et
#: `↑↓` y marchent, et `Tab` mene a la liste.
#:
#: MESURE: 58/63
RACCOURCIS_CURSEUR_SUR_LES_ISSUES = SEPARATEUR_DES_JETONS.join(
    ("⏎ choisir", "↑↓ naviguer", JETON_DE_LA_BASCULE, "Échap ateliers",
     "F1 aide"))

#: `E5-5c` -- la ligne dans la liste. **`⏎` en est ABSENT**, et c'est mesure
#: plutot que decide : un fichier ecrit n'est pas une issue, il n'y a rien a
#: valider. La touche est inerte dans cette zone, donc elle n'est pas annoncee.
#:
#: MESURE: 47/47
RACCOURCIS_CURSEUR_DANS_LA_LISTE = SEPARATEUR_DES_JETONS.join(
    ("↑↓ naviguer", JETON_DE_LA_BASCULE, "Échap ateliers", "F1 aide"))

# ===========================================================================
# Les deux zones
# ===========================================================================

#: Les deux zones navigables de l'ecran. **Une seule porte le curseur a la
#: fois** : c'est l'invariant reel d'`EPIC11-ARB-50`, et c'est lui qu'un test
#: mesure -- pas l'absence d'une seconde zone.
ZONE_DES_ISSUES = "issues"
ZONE_DE_LA_LISTE = "liste"
ZONES = (ZONE_DES_ISSUES, ZONE_DE_LA_LISTE)

# ===========================================================================
# Le tableau des planches ecrites
# ===========================================================================

#: Les trois en-tetes de colonne, verbatim de la maquette (l. 7 de `E5-5b`).
COLONNE_DU_FICHIER = "fichier"
COLONNE_DES_PAGES = "pages"
COLONNE_DU_RANG = "tirage"

#: Le creux entre les deux colonnes chiffrees, verbatim de la maquette.
CREUX_DES_COLONNES = 3

#: L'indentation d'une ligne de tableau, mesuree sur la maquette : le glyphe
#: d'etat ouvre a la colonne 5 de la zone utile, et l'en-tete de colonnes s'y
#: aligne. Le curseur se pose **dans** cette indentation (colonne 3), ce qui
#: laisse le glyphe et le nom exactement ou ils etaient : une ligne visee et une
#: ligne libre restent alignees.
INDENT_DES_LIGNES = " " * 5

#: La colonne ou la valeur d'une ligne d'information se pose, mesuree sur la
#: maquette (`Gabarit` a 5, `tpl-a4-...` a 39).
COLONNE_DE_LA_VALEUR = 39

#: Le glyphe d'etat d'une planche ecrite. Toutes le sont sur cet ecran : le
#: compte rendu ne montre que ce qui existe.
ETAT_DE_LA_PLANCHE = "complete"

#: Le titre du cartouche de `E5-5`, verbatim de la maquette (l. 5).
TITRE_DU_CARTOUCHE = "Écrit"

#: Le titre du filet de `E5-5b` et `E5-5c`, verbatim (l. 5). Il porte **ses
#: deux mesures** : le cardinal de PDF et celui des frames placees.
FILET_DES_ECRITS = "Écrit — {pdf} {mot_pdf}, {frames} {mot_frames}"

#: Le marqueur de fenetre, verbatim de la maquette (l. 11 de `E5-5b`) : une
#: **position**, jamais une touche. Il disait `↑↓ fait défiler` alors que le
#: pied du meme ecran dit `↑↓ naviguer` -- deux listes ne peuvent pas se
#: disputer les fleches, et la promesse etait fausse.
MARQUEUR_DE_LA_FENETRE = "{premier}-{dernier} sur {total} {mot} écrits"

#: Le pluriel des deux unites de cet ecran. Le singulier vaut aussi pour zero.
PLURIEL_DES_FRAMES = {False: "frame", True: "frames"}
UNITE_DES_PDF = "PDF"

#: Ce que le corps occupe **hors** fenetre, hors informations et hors suites :
#: la respiration de tete, le filet, sa respiration, l'en-tete de colonnes, et
#: les deux respirations qui detachent les informations puis les suites. Six,
#: **compte sur la maquette** et non estime -- au plancher,
#: :func:`hauteur_de_la_fenetre` rend alors 5, ce que `E5-5b` dessine.
LIGNES_HORS_FENETRE = 6


@dataclass(frozen=True)
class PlancheEcrite:
    """Un PDF de la passe, tel que le compte rendu le montre.

    `rang` est **affiche** et jamais recalcule (`EPIC11-ARB-92`) : il vient de
    la passe qui vient de l'ecrire.
    """

    nom: str
    pages: int
    rang: int
    #: Le fragment de mise en page du nom (`6f-pay`), **donne** par
    #: `io.naming.sheets_layout_fragment`. Il ne sert qu'a proteger la queue du
    #: nom a l'abregement ; vide, l'abregement retombe sur le socle.
    fragment: str = ""


def abreger_le_nom_de_planche(nom: str, largeur: int, fragment: str = "",
                              ascii_seul: bool = False) -> str:
    """Le nom d'un tirage tenu dans `largeur`, abrege **AU MILIEU**.

    **Ce que la queue protege, et pourquoi ce n'est pas
    `jetons.abreger_chemin`.** Un nom de tirage ne porte aucun separateur de
    chemin, donc `abreger_chemin` y retombe sur son cas degrade et coupe par le
    DEBUT -- il rend `…12p5_6f-pay.pdf`, ou l'on ne sait plus de quel lot il
    s'agit. Ce que les lignes de cet ecran ont besoin de distinguer est aux
    deux bouts : le lot au debut, la cadence, la mise en page et le rang a la
    fin.

    **Le fragment est DONNE, jamais devine ici** : il vient de
    `io.naming.sheets_layout_fragment(template_id)`, seule redaction de la
    grammaire `<N>f-<ori>` du depot. Re-decouper le nom pour le retrouver
    serait une seconde recette de la meme convention.

    Sans fragment -- ou quand il n'est pas dans le nom --, on retombe sur
    `jetons.abreger_chemin` plutot que d'inventer une queue : mieux vaut le
    comportement du socle qu'une devinette locale.
    """
    if ascii_seul:
        nom = jetons.replier_ascii(nom)
        fragment = jetons.replier_ascii(fragment)
    if jetons.colonnes(nom) <= largeur:
        return nom
    coupe = nom.rfind(fragment) if fragment else -1
    if coupe <= 0:
        return jetons.abreger_chemin(nom, largeur, ascii_seul)
    points = jetons.points_d_abregement(ascii_seul)
    queue = nom[coupe:]
    budget = largeur - jetons.colonnes(points)
    if jetons.colonnes(queue) >= budget:
        return jetons.abreger_chemin(nom, largeur, ascii_seul)
    tete = nom[:coupe]
    place = budget - jetons.colonnes(queue)
    while jetons.colonnes(tete) > place:
        tete = tete[:-1]
    return tete + points + queue


def ligne_d_en_tete(utile: int, ascii_seul: bool = False) -> str:
    """`fichier                       pages   tirage`.

    Elle s'aligne sur l'indentation des lignes, pas sur celle des noms : c'est
    ce que la maquette dessine, et le libelle `fichier` designe la colonne
    entiere -- glyphe compris.
    """
    return _caler_a_droite(INDENT_DES_LIGNES + COLONNE_DU_FICHIER,
                           COLONNE_DES_PAGES, COLONNE_DU_RANG, utile)


def _caler_a_droite(gauche: str, pages: str, rang: str, utile: int) -> str:
    """Les deux colonnes chiffrees, calees a droite de la zone utile.

    Elles sont larges de leur **en-tete**, pas de leur contenu : une colonne
    qui se recalerait sur le plus grand rang present bougerait d'une passe a
    l'autre, et deux captures ne seraient plus comparables.
    """
    droite = (pages.rjust(jetons.colonnes(COLONNE_DES_PAGES))
              + " " * CREUX_DES_COLONNES
              + rang.rjust(jetons.colonnes(COLONNE_DU_RANG)))
    creux = utile - jetons.colonnes(gauche) - jetons.colonnes(droite)
    return gauche + " " * max(creux, jetons.CREUX_MINIMAL) + droite


def _ligne_du_tableau(glyphe: str, planche: "PlancheEcrite", utile: int,
                      ascii_seul: bool = False) -> str:
    """Une ligne de planche : glyphe, nom abrege, pages et rang a droite."""
    largeur_droite = (jetons.colonnes(COLONNE_DES_PAGES) + CREUX_DES_COLONNES
                      + jetons.colonnes(COLONNE_DU_RANG))
    tete = f"{INDENT_DES_LIGNES}{glyphe} "
    place = max(utile - jetons.colonnes(tete) - largeur_droite
                - jetons.CREUX_MINIMAL, 0)
    nom = abreger_le_nom_de_planche(planche.nom, place, planche.fragment,
                                    ascii_seul)
    return _caler_a_droite(tete + nom, str(planche.pages), str(planche.rang),
                           utile)


def hauteur_de_la_fenetre(hauteur_centre: int, suites: int,
                          informations: int) -> int:
    """Combien de rangs de liste tiennent, **derives** de la hauteur courante.

    Ce qui occupe la zone en dehors de la liste : le filet et son en-tete de
    colonnes, les lignes d'information, les suites, et les respirations que
    `Composition` sacrifiera d'abord si la place manque. Au plancher (zone
    centrale de 17 lignes, deux informations, quatre suites), la fonction rend
    **5** -- exactement ce que la maquette `E5-5b` dessine, `…` comprise.
    """
    return max(hauteur_centre - LIGNES_HORS_FENETRE - suites - informations, 0)


@dataclass
class TableDesEcrits:
    """La liste des planches ecrites, sa fenetre et son curseur.

    Modele **pur** : il ne connait ni `textual`, ni largeur d'ecran a la
    construction. C'est ce qui permet de mesurer le recadrage sur des bornes,
    sans monter d'application.
    """

    planches: tuple[PlancheEcrite, ...]
    frames: int = 0
    #: Le rang, 0-fonde, de la planche sous le curseur **quand la liste a la
    #: main**. Il existe meme quand elle ne l'a pas : `Tab` doit retrouver la
    #: ou il etait.
    curseur: int = 0
    #: Le premier rang visible. Deplace **uniquement** par
    #: `jetons.recadrer_la_fenetre`.
    premier_visible: int = 0

    def __post_init__(self) -> None:
        if not self.planches:
            raise ValueError(
                "Un compte rendu de planches porte au moins une planche : un "
                "ecran de resultat sans resultat n'a rien a rendre.")

    # -- la fenetre ----------------------------------------------------------

    def bornes(self, hauteur: int) -> tuple[int, int]:
        """Les rangs visibles, **rendus par `jetons.fenetre_de_liste`**.

        Aucun calcul ici : la reserve de la ligne `…` et son effet sur la place
        disponible vivent dans `jetons`, une seule fois pour la TUI entiere.
        """
        return jetons.fenetre_de_liste(len(self.planches),
                                       self.premier_visible, hauteur)

    def recadrer(self, hauteur: int) -> None:
        """Ramener la fenetre sur le curseur, **un rang a la fois**.

        Les fleches ne defilent pas : elles deplacent le curseur, et c'est ce
        recadrage qui fait suivre la fenetre.
        """
        self.premier_visible = jetons.recadrer_la_fenetre(
            self.premier_visible, self.curseur, len(self.planches), hauteur)

    def se_parcourt(self, hauteur: int) -> bool:
        """Vrai quand la liste **ne tient pas** entiere.

        C'est le seul critere qui ouvre la bascule de zone : une liste qui tient
        n'a rien a parcourir, donc `Tab` n'y est ni offert ni annonce.
        """
        return len(self.planches) > hauteur

    def deplacer(self, pas: int, hauteur: int) -> None:
        """`↑↓` dans la liste : le curseur bouge, la fenetre suit."""
        self.curseur = min(max(self.curseur + pas, 0),
                           len(self.planches) - 1)
        self.recadrer(hauteur)

    # -- le rendu ------------------------------------------------------------

    def titre_du_filet(self) -> str:
        """`Écrit — 7 PDF, 512 frames`."""
        return FILET_DES_ECRITS.format(
            pdf=len(self.planches), mot_pdf=UNITE_DES_PDF,
            frames=self.frames,
            mot_frames=PLURIEL_DES_FRAMES[self.frames > 1])

    def marqueur(self, hauteur: int) -> str:
        """`1-4 sur 7 PDF écrits` -- les bornes rendues, 1-fondees."""
        premier, dernier = self.bornes(hauteur)
        return MARQUEUR_DE_LA_FENETRE.format(
            premier=premier + 1, dernier=dernier + 1,
            total=len(self.planches), mot=UNITE_DES_PDF)

    def lignes(self, hauteur: int, utile: int, ascii_seul: bool = False,
               avec_curseur: bool = False
               ) -> tuple[list[str], int | None, dict[int, str]]:
        """Les lignes de la liste, le rang du curseur, les etats.

        Le rang rendu est celui **dans les lignes composees**, jamais le rang
        absolu de la planche : une fenetre calee ailleurs qu'en tete les rend
        differents, et c'est exactement le defaut qu'une liste indexee sur le
        rang absolu produit sans qu'aucun test cale en tete ne le voie.
        """
        table = jetons.glyphes(ascii_seul)
        premier, dernier = self.bornes(hauteur)
        lignes: list[str] = []
        etats: dict[int, str] = {}
        rang_du_curseur: int | None = None
        if premier > 0:
            lignes.append(INDENT_DES_LIGNES
                          + jetons.points_d_abregement(ascii_seul))
        for absolu in range(premier, dernier + 1):
            planche = self.planches[absolu]
            visee = avec_curseur and absolu == self.curseur
            ligne = _ligne_du_tableau(table[ETAT_DE_LA_PLANCHE], planche,
                                      utile, ascii_seul)
            if visee:
                # **Le curseur se pose DANS l'indentation**, sans decaler le
                # glyphe ni le nom : une ligne visee et une ligne libre restent
                # alignees. Il ouvre bien la ligne apres `strip()`, seule forme
                # que le colorisateur reconnait.
                largeur = len(table["curseur"]) + 1
                ligne = (INDENT_DU_CURSEUR + table["curseur"] + " "
                         + ligne[len(INDENT_DU_CURSEUR) + largeur:])
                rang_du_curseur = len(lignes)
            etats[len(lignes)] = ETAT_DE_LA_PLANCHE
            lignes.append(ligne)
        if dernier < len(self.planches) - 1:
            lignes.append(self._ligne_du_marqueur(hauteur, utile, ascii_seul))
        return lignes, rang_du_curseur, etats

    def _ligne_du_marqueur(self, hauteur: int, utile: int,
                           ascii_seul: bool = False) -> str:
        """`…                                        1-4 sur 7 PDF écrits`."""
        tete = INDENT_DES_LIGNES + jetons.points_d_abregement(ascii_seul)
        marqueur = self.marqueur(hauteur)
        creux = utile - jetons.colonnes(tete) - jetons.colonnes(marqueur)
        return tete + " " * max(creux, jetons.CREUX_MINIMAL) + marqueur


# ===========================================================================
# Les suites, et la ligne d'etat
# ===========================================================================

#: Les quatre suites de `E5-5`, verbatim des maquettes (l. 16-19). Le retour est
#: pose par `EcranResultat` lui-meme s'il manque : on ne l'ecrit donc pas ici,
#: sous peine de le voir deux fois.
SUITE_DOSSIER = "Ouvrir le dossier"
SUITE_CALIBRATION = "Générer une planche de calibration"
SUITE_AUTRES_LOTS = "Mettre d'autres lots en planches"

#: La mention de la colonne de droite de la suite de calibration, verbatim
#: (l. 17). Elle dit **pourquoi elle est proposee ici** : on imprime les deux
#: ensemble.
MENTION_CALIBRATION = "(à imprimer avec)"

#: La colonne ou la mention se pose, mesuree sur la maquette.
COLONNE_DE_LA_MENTION = 49

#: L'ensemble EXACT des suites (AC 10.7), dans l'ordre de la maquette.
SUITES = (SUITE_DOSSIER, SUITE_CALIBRATION, SUITE_AUTRES_LOTS)

#: Les mentions par suite. Une seule en porte une.
MENTIONS_DES_SUITES = {SUITE_CALIBRATION: MENTION_CALIBRATION}

#: Les deux libelles du bloc d'information, verbatim des maquettes.
LIBELLE_GABARIT = "Gabarit"
LIBELLE_EMPLACEMENT = "Emplacement"
LIBELLE_MANIFEST = "Manifest mis à jour"

#: La ligne d'etat, verbatim de la maquette de `E5-5b` (l. 22) : **trois
#: mesures**, et pas un mot de mecanisme (`EPIC11-ARB-56`).
ETAT_DE_LA_PASSE = "{pdf} {mot_pdf} écrits · {frames} {mot_frames} placées"

#: Ce que la ligne d'etat ajoute quand la passe n'a rien refuse. Un **constat**,
#: et il vaut d'etre dit : son absence se lirait comme une information perdue.
AUCUN_REFUS = " · aucun refus"


def ligne_d_etat(table: TableDesEcrits, refus: int = 0) -> str:
    """`7 PDF écrits · 512 frames placées · aucun refus`."""
    mesure = ETAT_DE_LA_PASSE.format(
        pdf=len(table.planches), mot_pdf=UNITE_DES_PDF, frames=table.frames,
        mot_frames=PLURIEL_DES_FRAMES[table.frames > 1])
    return mesure + (AUCUN_REFUS if refus == 0 else "")


def ligne_d_information(libelle: str, valeur: str, utile: int,
                        ascii_seul: bool = False) -> str:
    """`Gabarit                     tpl-a4-paysage-6f-v2`, hors cartouche."""
    tete = INDENT_DES_LIGNES + libelle
    creux = max(COLONNE_DE_LA_VALEUR - jetons.colonnes(tete), 1)
    return tete + " " * creux + jetons.abreger_chemin(
        valeur, max(utile - jetons.colonnes(tete) - creux, 0), ascii_seul)


# ===========================================================================
# La composition -- pure, mesurable sans monter d'application
# ===========================================================================

def hauteur_centrale(hauteur_fenetre: int) -> int:
    """La zone centrale a la hauteur COURANTE de la fenetre.

    **La soustraction n'est plus ecrite ici** (2026-09-04) : elle vit dans
    `jetons.hauteur_centrale`, comme `largeur_utile` vit deja la-bas. Ce nom
    reste parce que le module et son banc l'emploient, mais il ne recopie plus
    la geometrie -- quatre copies de la meme soustraction, c'etait quatre
    endroits a retoucher au premier filet ajoute.
    """
    return jetons.hauteur_centrale(hauteur_fenetre)


def lignes_des_suites(suites: Sequence[str], zone: str, curseur: int,
                      utile: int, ascii_seul: bool = False) -> list[str]:
    """Les suites, **toujours dessinees et entieres**.

    Elles ne portent la fleche que si la zone des issues a la main : c'est la
    difference entre « perdre le curseur » et « disparaitre », et c'est ce
    qu'`EPIC11-ARB-50` demande de montrer.
    """
    table = jetons.glyphes(ascii_seul)
    lignes = []
    for rang, suite in enumerate(suites):
        vise = (zone == ZONE_DES_ISSUES and rang == curseur)
        glyphe = table["curseur"] if vise else " "
        ligne = f"{INDENT_DU_CURSEUR}{glyphe} {suite}"
        mention = MENTIONS_DES_SUITES.get(suite)
        if mention:
            creux = max(COLONNE_DE_LA_MENTION - jetons.colonnes(ligne), 1)
            ligne = ligne + " " * creux + mention
        lignes.append(jetons.ajuster(ligne, utile, ascii_seul))
    return lignes


def corps_du_resultat(table: TableDesEcrits,
                      informations: Sequence[tuple[str, str]],
                      suites: Sequence[str], zone: str, curseur: int,
                      largeur: int, hauteur: int, ascii_seul: bool = False
                      ) -> tuple[list[str], int | None, dict[int, str]]:
    """Le corps de `E5-5b` / `E5-5c`, sous la hauteur de la zone centrale.

    **Un seul rang de curseur est rendu**, celui de la zone qui a la main :
    c'est l'invariant reel d'`EPIC11-ARB-50`, et le mesurer ici plutot que sur
    l'ecran monte le rend verifiable sans terminal.
    """
    utile = jetons.largeur_utile(largeur)
    fenetre = hauteur_de_la_fenetre(hauteur, len(suites), len(informations))
    composition = Composition()
    composition.respirer()
    composition.poser(filet_titre(table.titre_du_filet(), utile, ascii_seul))
    composition.respirer()
    composition.poser(ligne_d_en_tete(utile, ascii_seul))
    lignes, rang, etats = table.lignes(fenetre, utile, ascii_seul,
                                       avec_curseur=zone == ZONE_DE_LA_LISTE)
    composition.bloc(lignes, etats=etats, curseur=rang)
    composition.respirer()
    composition.bloc([ligne_d_information(libelle, valeur, utile, ascii_seul)
                      for libelle, valeur in informations])
    composition.respirer()
    composition.bloc(lignes_des_suites(suites, zone, curseur, utile,
                                       ascii_seul),
                     curseur=(curseur if zone == ZONE_DES_ISSUES else None))
    return composition.rendu(hauteur)


# ===========================================================================
# L'ecran
# ===========================================================================

class EcranResultatDesPlanches(EcranResultat):
    """`E5-5` / `E5-5b` / `E5-5c` -- le compte rendu de la passe.

    **Elle sous-classe `EcranResultat`** pour ses suites : leur ajout du retour
    en dernier, `Échap` qui mene aux ateliers, et le passage par
    `EcranPasEncore` quand un atelier n'existe pas encore. Ce qu'elle redonne
    est le corps -- un tableau a fenetre au lieu d'un panneau -- et le clavier,
    parce que `Tab` change de sens : il ne deplie plus un journal, il change de
    zone.
    """

    titre = PALIER_DU_RESULTAT

    #: Reassignee a chaque dessin par :meth:`poser_les_raccourcis` -- l'idiome
    #: du depot pour une ligne contextuelle. Une `property` casserait le
    #: balayage du paquet, qui lit cet attribut de CLASSE.
    raccourcis = RACCOURCIS_LISTE_ENTIERE

    #: Un passage : le compte rendu d'un travail fini.
    TRANSITOIRE = True

    ID_DU_CORPS = "corps-resultat-pdf"

    def __init__(self, table: TableDesEcrits,
                 informations: Sequence[tuple[str, str]] = (),
                 suites: Sequence[str] | None = None,
                 sur_suite: Callable[[str], None] | None = None,
                 refus: int = 0, objet: str = "") -> None:
        # **Aucun journal n'est passe**, et c'est ce qui retire `Tab journal`
        # de la ligne heritee (AC 10.5). Le panneau est vide : le tableau de cet
        # ecran n'est pas un `Panneau`, il porte trois colonnes.
        super().__init__(Panneau(TITRE_DU_CARTOUCHE),
                         suites=list(suites if suites is not None else SUITES),
                         sur_suite=sur_suite, objet=objet)
        self.table = table
        self.informations = tuple(informations)
        self.refus = refus
        #: La zone qui porte le curseur. **Une seule a la fois**
        #: (`EPIC11-ARB-50`).
        self.zone = ZONE_DES_ISSUES

    # -- la bascule ----------------------------------------------------------

    def liste_parcourable(self, hauteur: int | None = None) -> bool:
        """Vrai quand la liste ne tient pas entiere -- le seul critere."""
        return self.table.se_parcourt(self.hauteur_de_la_fenetre(hauteur))

    def basculer_la_zone(self, hauteur: int | None = None) -> bool:
        """`Tab` : **deplacer** le curseur d'une zone a l'autre.

        Il ne le duplique pas : la zone qu'il quitte reste dessinee, entiere, et
        perd la fleche. Rend faux quand il n'y a pas de seconde zone -- une
        touche annoncee qui ne fait rien se lit comme une panne, et c'est
        pourquoi la ligne ne l'annonce pas dans ce cas.
        """
        if not self.liste_parcourable(hauteur):
            return False
        self.zone = (ZONE_DE_LA_LISTE if self.zone == ZONE_DES_ISSUES
                     else ZONE_DES_ISSUES)
        if self.zone == ZONE_DE_LA_LISTE:
            self.table.recadrer(self.hauteur_de_la_fenetre(hauteur))
        self.rafraichir()
        return True

    def poser_les_raccourcis(self, hauteur: int | None = None) -> str:
        """Contextuelle, et sur les **trois** etats.

        `E5-5` rend **exactement** `RACCOURCIS_RAPPORT` (AC 10.5) ; `E5-5b`
        ajoute la bascule ; `E5-5c` perd `⏎`, qui n'a rien a valider dans la
        liste.
        """
        if not self.liste_parcourable(hauteur):
            self.raccourcis = RACCOURCIS_LISTE_ENTIERE
        elif self.zone == ZONE_DE_LA_LISTE:
            self.raccourcis = RACCOURCIS_CURSEUR_DANS_LA_LISTE
        else:
            self.raccourcis = RACCOURCIS_CURSEUR_SUR_LES_ISSUES
        return self.raccourcis

    # -- la geometrie --------------------------------------------------------

    def hauteur_centrale(self) -> int:
        return hauteur_centrale(self.app.size.height)

    def hauteur_de_la_fenetre(self, hauteur: int | None = None) -> int:
        if hauteur is None:
            hauteur = self.hauteur_centrale()
        return hauteur_de_la_fenetre(hauteur, len(self.suites),
                                     len(self.informations))

    # -- le corps ------------------------------------------------------------

    def lignes_des_suites(self, utile: int, ascii_seul: bool = False
                          ) -> list[str]:
        return lignes_des_suites(tuple(self.suites), self.zone, self.curseur,
                                 utile, ascii_seul)

    def composer(self, largeur: int, ascii_seul: bool = False,
                 hauteur: int | None = None
                 ) -> tuple[list[str], int | None, dict[int, str]]:
        """Le corps. **Pur des le second argument** : `self.app` n'est lu que
        pour les valeurs par defaut, et la composition entiere se mesure sans
        monter d'application."""
        if hauteur is None:
            hauteur = self.hauteur_centrale()
        return corps_du_resultat(self.table, self.informations,
                                 tuple(self.suites), self.zone, self.curseur,
                                 largeur, hauteur, ascii_seul)

    def lignes(self) -> list[str]:
        return self.composer(self.app.size.width,
                             getattr(self.app, "ascii_seul", False))[0]

    def etat(self) -> str:
        return ligne_d_etat(self.table, self.refus)

    # -- rendu ---------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id=self.ID_DU_CORPS)
        return [self._corps]

    def on_mount(self) -> None:
        self.rafraichir()

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        ascii_seul = getattr(self.app, "ascii_seul", False)
        largeur = jetons.largeur_utile(self.app.size.width)
        self.poser_les_raccourcis()
        lignes, rang, etats = self.composer(self.app.size.width, ascii_seul)
        self._corps.update(bloc_peint(lignes, largeur, self.app, rang=rang,
                                       etats=etats))
        self.poser_etat(self.etat())
        # **Deux sauts au-dessus d'`EcranResultat`** : le sien redessine un
        # widget de panneau que cet ecran n'a pas, et pose son propre rang de
        # curseur, qui ignore la zone.
        super(EcranResultat, self).rafraichir()

    def rang_du_curseur(self) -> int | None:
        """Le rang, dans :meth:`lignes`, de la ligne qui porte la fleche."""
        return self.composer(self.app.size.width,
                             getattr(self.app, "ascii_seul", False))[1]

    # -- clavier -------------------------------------------------------------

    def on_key(self, evenement) -> None:
        """`Tab` change de zone, `↑↓` deplace dans la zone qui a la main.

        `⏎` n'est traite que **dans les issues** : dans la liste il n'a rien a
        valider, et le laisser passer ferait exactement ce que la ligne du bas
        s'interdit d'annoncer.
        """
        if evenement.key == "tab":
            if self.basculer_la_zone():
                evenement.stop()
            return
        if evenement.key in ("down", "up"):
            evenement.stop()
            pas = 1 if evenement.key == "down" else -1
            if self.zone == ZONE_DE_LA_LISTE:
                self.table.deplacer(pas, self.hauteur_de_la_fenetre())  # noqa: E501
            else:
                self.curseur = min(max(self.curseur + pas, 0),
                                   len(self.suites) - 1)
            self.rafraichir()
            return
        if evenement.key == "enter":
            if self.zone != ZONE_DES_ISSUES:
                return
            evenement.stop()
            self.choisir()
            return
        if evenement.key == "escape":
            evenement.stop()
            self.app.revenir_aux_ateliers()


#: Ce qu'on dit quand aucune planche n'a de dossier a ouvrir. Le volet
#: symetrique de la suite : elle n'est proposee que s'il y a un dossier, et ce
#: texte tient si un jour elle l'etait quand meme.
AUCUN_DOSSIER_A_OUVRIR = "Aucune planche écrite : il n'y a aucun dossier à ouvrir."


def ouvrir_le_dossier_des_planches(app, dossier) -> str:
    """Remettre le dossier des planches a l'explorateur du systeme (AC 10.3).

    **Elle passe par `execution.ouvrir_dans_l_explorateur_du_systeme`**, seul
    site du depot ou un `subprocess` est tolere : `tui/` n'en porte aucun, et
    une frontiere negative le mesure sur ce module.

    **Le resultat est DIT, dans les deux cas** -- un echec silencieux serait
    indistinguable de la suite decorative que le finding `K3` a payee -- et
    **l'ecran ne change pas** : le compte rendu reste lisible au moment ou
    l'operateur va le comparer au contenu du dossier.

    Rend le fait affiche, pour qu'un banc le mesure sans relire l'ecran.
    """
    fait = (AUCUN_DOSSIER_A_OUVRIR if dossier is None
            else ouvrir_dans_l_explorateur_du_systeme(dossier))
    if getattr(app, "ascii_seul", False):
        fait = jetons.replier_ascii(fait)
    app.palier_courant.poser_etat(fait)
    return fait


def ouvrir_le_resultat(app, table: TableDesEcrits, *,
                       sur_suite: Callable[[str], None],
                       informations: Sequence[tuple[str, str]] = (),
                       refus: int = 0,
                       objet: str = "") -> EcranResultatDesPlanches:
    """Monter `E5-5`. `sur_suite` est **requis**.

    Requis, et non `None` par defaut : c'est le finding `K3`, ou quatre suites
    d'un ecran de resultat etaient navigables et decoratives parce qu'un point
    d'appel avait oublie de les passer, sans que rien ne le dise.
    """
    ecran = EcranResultatDesPlanches(table, informations=informations,
                                     sur_suite=sur_suite, refus=refus,
                                     objet=objet)
    app.descendre(ecran)
    return ecran
