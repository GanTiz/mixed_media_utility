# -*- coding: utf-8 -*-
"""La coque de la TUI : grille, bandeau, ligne d'etat, raccourcis, paliers.

Story 11.0. Ce module ne porte **aucune fonction metier** : il porte le chrome
que les neuf stories suivantes consomment sans le redefinir.

Quatre pieces :

* :func:`feuille` -- la feuille de style, dont toutes les couleurs viennent de
  :mod:`.jetons` (aucune valeur hexadecimale n'est ecrite ici) ;
* :class:`Contexte` -- ce que le bandeau dit a tout instant ;
* :class:`Palier` -- un etage de navigation, dont **un seul est monte a la
  fois** (`EPIC11-ARB-2`) ;
* :class:`CoqueTui` -- l'application, qui empile les paliers, appelle le coeur
  **en processus** (`EPIC11-ARB-1`) et refuse de dessiner sous le plancher.

**Un palier est un ecran `textual`, et la pile de paliers est la pile
d'ecrans.** Ce n'est pas un detail d'implementation : c'est ce qui rend
« un seul palier monte a la fois » vrai *par construction* plutot que par
discipline -- `textual` ne dessine que le sommet de sa pile -- et ce qui fait de
`Echap` un `pop_screen`, donc une remontee d'exactement un etage, jamais deux.

**Le refus sous le plancher n'est pas un garde-fou d'affichage**
(`EPIC11-ARB-21`) : une mise en page tronquee ment sur ce qui tient a l'ecran,
et c'est exactement ce que la grille verifiee des maquettes cherche a empecher.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Static

from . import jetons

if TYPE_CHECKING:      # pragma: no cover -- annotation seulement
    # Import differe : `explorateur` importe `jetons` comme ce module,
    # et le tirer a l'execution ferait payer un cycle pour une simple
    # annotation. Le registre lui-meme est importe dans `__init__`.
    from .explorateur import MemoiresDeSession


def feuille(sans_couleur: bool = False) -> str:
    """Rend la feuille de style de la coque.

    ``sans_couleur`` produit la **meme** mise en page sans aucune declaration de
    couleur : c'est le mode ou l'AC 3 exige que chaque etat reste distinguable,
    ce que le glyphe -- et lui seul -- garantit alors.

    Les hauteurs comme les couleurs sont **lues** dans :mod:`.jetons` ; ce
    module n'en ecrit aucune.
    """
    def teinte(nom: str) -> str:
        return "" if sans_couleur else f"color: {jetons.couleur(nom)};"

    def trait(cote: str) -> str:
        """Un filet du cadre. Sans couleur, il garde son trait : le cadre est
        de la structure, pas de l'information -- l'eteindre ferait perdre la
        grille a un terminal monochrome au lieu de lui faire perdre une teinte.
        """
        teintee = "" if sans_couleur else f" {jetons.couleur('muted')}"
        return f"{cote}: solid{teintee};"

    marge = f"0 {jetons.MARGE}"
    # `box-sizing: content-box` sur les deux zones qui portent un filet : sans
    # lui, `textual` compte le filet DANS la hauteur declaree, une ligne d'etat
    # de hauteur 1 devient une ligne de zero caractere, et l'ecran affiche un
    # trait a la place du texte. Mesure faite au developpement de la story.
    return f"""
Screen {{ layout: vertical; {trait("border")} }}
#bandeau {{
    height: {jetons.HAUTEUR_BANDEAU}; padding: {marge}; box-sizing: content-box;
    {trait("border-bottom")} {teinte("data")}
}}
#centre {{ height: 1fr; padding: {marge}; }}
#etat {{
    height: {jetons.HAUTEUR_ETAT}; padding: {marge}; box-sizing: content-box;
    {trait("border-top")} {teinte("muted")}
}}
#raccourcis {{
    height: {jetons.HAUTEUR_RACCOURCIS}; padding: {marge}; {teinte("muted")}
}}
#trop-petit {{ height: 1fr; padding: 1 {jetons.MARGE}; {teinte("state-absent")} }}
#cartouche {{
    width: 100%; height: auto; padding: 0 {jetons.MARGE};
    {trait("border")} {teinte("data")}
}}
.nom {{ height: {jetons.HAUTEUR_BANDEAU}; {teinte("data")} }}
.nom-courant {{ {teinte("accent")} }}
/* Un nom refuse porte SA couleur -- et son glyphe `✕`, pose par le modele.
   Les deux ensemble, jamais la couleur seule : c'est la regle 1 non negociable
   de `DESIGN.md` section 5, et un terminal monochrome doit lire la meme chose. */
.nom-refuse {{ {teinte("state-absent")} }}
"""


#: Ce que le bandeau affiche quand aucun projet n'est ouvert. C'est une phrase
#: d'ecran : elle ne reprend aucun terme de nos documents de decision
#: (`EPIC11-ARB-28`).
SANS_PROJET = "— aucun projet —"


def assez_grand(largeur: int, hauteur: int) -> bool:
    """Vrai si la fenetre atteint le plancher de `EPIC11-ARB-21`.

    Le predicat est une fonction libre, et pas une methode : il se mesure sans
    monter d'application, et c'est le seul endroit ou la comparaison au plancher
    est ecrite. Les deux bornes sont **inclusives** -- 80x24 est acceptable,
    c'est le plancher et non le premier refus.
    """
    return (largeur >= jetons.LARGEUR_PLANCHER
            and hauteur >= jetons.HAUTEUR_PLANCHER)


def message_trop_petit(largeur: int, hauteur: int) -> str:
    """Le seul contenu affiche sous le plancher : la taille vue, la taille due."""
    return (f"Terminal trop petit : {largeur} colonnes sur {hauteur} lignes.\n"
            f"Il en faut au moins {jetons.LARGEUR_PLANCHER} sur "
            f"{jetons.HAUTEUR_PLANCHER}.")


@dataclass(frozen=True)
class Contexte:
    """Ou l'on est, et sur quoi (``DESIGN.md`` section 2).

    ``palier`` est le SEUL segment qui bouge a la navigation ; ``projet`` et
    ``objet`` traversent les etages sans changer -- c'est ce que l'AC 4.4
    mesure, en comparant deux bandeaux et non un seul.
    """

    projet: str | None = None
    palier: str = ""
    objet: str = ""

    def rendu(self, largeur_fenetre: int = jetons.LARGEUR_PLANCHER,
              ascii_seul: bool = False) -> str:
        """Segments a gauche, objet travaille a droite, sur une seule ligne.

        L'argument est la largeur de la **fenetre** : la largeur ecrivable s'en
        deduit par :func:`jetons.largeur_utile`, qui retire le cadre et les
        marges. Passer directement 80 ici ferait deborder le bandeau de quatre
        colonnes, et la deduction n'est ecrite qu'a un seul endroit.

        **Le bandeau ne deborde jamais, et il ne perd jamais sa droite.** Quand
        les deux cotes ne tiennent pas ensemble, c'est le **nom du projet** qui
        est abrege -- jamais l'objet travaille. Motif : le projet est ecrit
        partout ailleurs (l'operateur vient de l'ouvrir), tandis que l'objet
        porte les chiffres du parcours en cours, qui ne se relisent nulle part.
        Un nom de projet reel du depot -- `projet_demo_planche_4f_heteroclite` --
        faisait dejа 85 colonnes pour 76 et emportait la cadence avec lui
        (revue de vague 1, couche 1).
        """
        utile = jetons.largeur_utile(largeur_fenetre)
        # **Replier AVANT de mesurer, jamais apres.** Le repli ASCII peut
        # ALLONGER le texte -- `—` rend `--`, `·` rend `.`, `…` rend `...` --,
        # si bien qu'une ligne calee a la bonne largeur en UTF-8 la depasse une
        # fois repliee, et l'elision mange alors la DROITE, c'est-a-dire
        # l'objet. Mesure du 2026-08-28, en `--ascii` sans projet ouvert :
        # `TEST_FILE_12p5` devenait `TEST_FILE...`. C'est la regression exacte
        # que `BH-6` / `EC-10` avaient fermee, revenue par le seul chemin qui
        # n'etait pas mesure.
        objet = jetons.ajuster(self.objet, utile, ascii_seul)
        projet = jetons.replier_ascii(self.projet or SANS_PROJET)             if ascii_seul else (self.projet or SANS_PROJET)

        def assembler(nom_du_projet: str) -> str:
            palier = self.palier
            if ascii_seul:
                palier = jetons.replier_ascii(palier)
            segments = ["mmu", nom_du_projet] + ([palier] if palier else [])
            separateur = jetons.replier_ascii(" · ") if ascii_seul else " · "
            return separateur.join(segments)

        gauche = assembler(projet)
        creux = utile - jetons.colonnes(gauche) - jetons.colonnes(objet)
        if creux < 1:
            # Budget du seul segment abregeable : ce qui reste une fois l'ancre,
            # le palier, les separateurs, l'objet et une colonne de creux poses.
            structure = jetons.colonnes(assembler("")) + jetons.colonnes(objet) + 1
            gauche = assembler(jetons.ajuster(projet, max(utile - structure, 0),
                                              ascii_seul))
            creux = utile - jetons.colonnes(gauche) - jetons.colonnes(objet)
        ligne = gauche + " " * max(1, creux) + objet
        # Dernier recours : meme abrege, un palier ou un objet deraisonnable
        # peut encore deborder. On ne replie jamais.
        return jetons.ajuster(ligne, utile, ascii_seul)


class ObjetTravaille:
    """La DROITE du bandeau, posee par l'ecran qui sait sur quoi on travaille.

    **Le defaut qu'elle ferme** (`I3`, 2026-08-30) : `Contexte.objet` existait,
    les maquettes le remplissaient sur onze ecrans sur douze, et **aucun ecran
    de l'atelier ne le posait** -- `rushes.bandeau_de_relink()` etait livre,
    teste, exporte, et appele nulle part. C'est la troisieme occurrence du mode
    de panne du lot `E9` : un composant que rien ne cable est un composant que
    le produit n'a pas.

    **Pourquoi l'ecran substitue au lieu d'ecrire dans la session.**
    `Contexte` est gele et vit sur l'application : ce qu'il porte traverse les
    etages sans changer, ce qui est exactement ce que l'AC 4.4 de la 11.0
    mesure. Or l'objet travaille ici change d'un ecran a l'autre, et meme d'une
    ZONE a l'autre du meme ecran -- la liste des rushes n'en a pas, son
    explorateur de relink en a un. Ecrire dans la session le ferait donc
    survivre au palier qui l'a pose, et le bandeau du voisin porterait le
    rush du precedent. L'ecran rend le sien au moment de dessiner, et rien
    n'est memorise.

    **Pourquoi elle vit ici et non dans `atelier_extraction`** (`J3`,
    2026-08-30) : les cinq ecrans qui manquaient encore leur objet -- `E2-3`,
    `E2-3b`, `E2-3c`, `E2-4` et `E2-5` -- vivent dans `execution.py`, qui est
    importe PAR `atelier_extraction` et ne peut donc pas l'importer en retour.
    Un second mixin ecrit de l'autre cote aurait ete deux redactions du meme
    motif ; la place d'un composant que deux modules partagent est celle ou
    vivent deja `Contexte` et `Palier`, c'est-a-dire ici. `atelier_extraction`
    la reexporte pour que les appelants existants ne bougent pas.
    """

    #: L'objet **donne** par l'atelier qui monte cet ecran, pour les ecrans qui
    #: ne peuvent pas le calculer. `execution.py` porte les cinq ecrans du
    #: jugement, de l'execution et du resultat : ils sont partages par les
    #: quatre ateliers et n'ont donc aucun moyen de savoir qu'on travaille un
    #: *rush* -- ce vocabulaire est celui de l'atelier Extraction, et l'ecrire
    #: dans `execution.py` y ferait entrer un metier qui n'y a pas sa place.
    objet: str = ""

    def objet_du_bandeau(self) -> str:
        """Ce que cet ecran travaille, ou la chaine vide quand il n'y a rien a
        dire -- `E2-1` est dans ce cas, et sa maquette porte un bandeau nu.

        **Deux facons de le savoir, une seule methode.** Un ecran qui connait
        son objet la surcharge et le compose (`EcranRushes` rend
        `rush_hiver · retrouver`) ; un ecran generique le recoit a la
        construction et la reponse par defaut suffit. Ecrire une seconde
        methode pour la seconde facon en ferait deux redactions du meme point
        d'appel, et c'est ce point d'appel unique que :meth:`bandeau` consulte.
        """
        return self.objet

    def bandeau(self, largeur: int | None = None) -> str:
        objet = self.objet_du_bandeau()
        if not objet:
            return super().bandeau(largeur)
        session = getattr(self.app, "contexte", Contexte())
        contexte = Contexte(session.projet, self.titre, objet)
        # Le mode est TRANSMIS, et c'est ce qui manquait : voir la note de
        # :meth:`Palier.bandeau`, dont ce site est le jumeau.
        return contexte.rendu(self.app.size.width if largeur is None
                              else largeur,
                              getattr(self.app, "ascii_seul", False))


# ---------------------------------------------------------------------------
# LA REGLE DES MAJUSCULES DE RACCOURCI (consigne d'Egan du 2026-08-30)
#
# Egan, verbatim : « Il faudrait d'ailleurs ecrire tous les raccourcis partout
# en majuscules pour la lisibilite, meme si on cable directement la touche du
# clavier, pas le raccourci maj+lettre ! »
#
# Elle a DEUX moities, et la seconde est celle qui se relit mal :
#
# 1. **l'affichage** d'une lettre de raccourci est en MAJUSCULE, partout --
#    lignes de raccourcis, legendes de touches, maquettes. `o revoir` s'ecrit
#    `O revoir`, `q quitter` s'ecrit `Q quitter` ;
# 2. **la touche liee ne change pas** : c'est la lettre NUE, minuscule --
#    `ord("o")`, `caractere == "o"`, `("q", "quitter", ...)`. Jamais `"O"`,
#    jamais `maj+o`. Un operateur qui tape `o` doit continuer de marcher, et
#    RIEN ne doit exiger la majuscule.
#
# **C'est donc une divergence VOLONTAIRE entre la ligne d'aide et le code de la
# touche**, et c'est le piege de cette regle : les deux se lisent cote a cote,
# l'un dit `O` et l'autre dit `"o"`, et le reflexe est de « corriger » l'un des
# deux. Les deux sens de la correction sont des regressions :
#
# * mettre la ligne d'aide en minuscule defait la lisibilite qu'Egan demande ;
# * mettre la touche liee en majuscule casse le produit -- taper `o` ne fait
#   plus rien, et il faut decouvrir `Maj+O` pour revoir une previz.
#
# Le precedent est deja au depot : `cadence_previz.KEY_LOOP = ord("l")` sous une
# legende qui affiche `L boucle`, avec le meme motif ecrit en face.
#
# `tests/unit/tui/test_majuscules_des_raccourcis.py` mesure les deux moities a
# la fois -- l'affichage sur toutes les lignes du paquet et des maquettes, la
# frappe sur les touches reellement cablees.
#
# **Ce que la regle ne vise PAS**, et l'exclusion est aussi importante que la
# regle :
#
# * les **touches nommees** gardent leur forme -- `Tab`, `Échap`, `Entrée`,
#   `Espace`, `Suppr`, `Ctrl+R`, `F1`, et les glyphes `⏎ ↑↓ ←→ ⌫`. La regle vise
#   les LETTRES, pas les noms de touche ;
# * une **paire ou la casse est deja porteuse** -- `g debut` / `G fin` du
#   journal `T3-1` -- ne peut pas s'y plier : mettre `g` en majuscule ferait
#   deux entrees `G`. Elle reste telle quelle, et c'est un finding remonte a
#   Egan plutot qu'un oubli ;
# * une **ligne d'etat** ne porte aucune touche du tout (`EPIC11-ARB-56`) :
#   il n'y a donc rien a y mettre en majuscule. Une ligne d'etat qui en porte
#   une est une violation de l'arbitrage, pas un candidat a cette regle.
# ---------------------------------------------------------------------------


class Palier(Screen):
    """Un etage de navigation : le chrome commun, plus son propre contenu.

    Les stories 11.2 et suivantes en derivent leurs ecrans et ne redefinissent
    que :meth:`contenu`, ``titre`` et ``raccourcis``. Elles n'ont donc aucune
    raison de retoucher la grille -- ce qui est le point de la story 11.0.
    """

    titre: str = ""
    raccourcis: str = ""

    #: **Une station, ou un passage.** `DESIGN.md` distingue les deux depuis le
    #: debut ; jusqu'ici rien dans le code ne les separait, et c'est ce qui a
    #: coute les deux defauts de navigation du parcours manuel du 2026-08-28
    #: (`V2-M1`). Un ecran transitoire -- formulaire, confirmation, execution,
    #: resultat, « pas encore » -- occupe la pile **sans etre un palier** : il
    #: ne compte pas dans le rang, et il ne reste pas sur le chemin du retour.
    TRANSITOIRE: bool = False

    def reprendre(self) -> None:
        """Ce qu'un palier fait quand on **revient** dessus.

        Par defaut il se redessine. Un ecran qui lit le disque surcharge cette
        methode pour **relire d'abord** : les paliers sont installes depuis la
        vague 1 bis, donc ils survivent a la visite -- et rien ne les
        redessinait au retour. Un menu gardait ainsi les compteurs du projet
        precedent (`V2-M2`), et la liste des recents peignait un ordre que le
        modele avait deja change, si bien que le curseur designait une ligne et
        la validation en ouvrait une autre.
        """
        self.rafraichir()

    def on_screen_resume(self) -> None:
        """`textual` remonte cet evenement a chaque fois que l'ecran redevient
        le sommet de la pile. C'est le seul endroit ou la reprise est sure :
        `on_mount` ne rejoue pas pour un ecran installe."""
        self.reprendre()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        #: Memoire du dernier dessin, pour ne recomposer qu'au FRANCHISSEMENT
        #: du plancher. Recomposer a chaque evenement de taille detruirait le
        #: contenu -- donc la saisie en cours d'un formulaire des stories
        #: suivantes -- a chaque colonne gagnee par la fenetre.
        self._assez_grand_au_dernier_dessin: bool | None = None
        #: Dernier texte d'etat DEMANDE, avant ajustement a la largeur. Il est
        #: memorise parce que la ligne d'etat doit survivre a deux evenements
        #: qui la detruisaient : un redimensionnement (elle gardait le texte
        #: calcule pour l'ancienne largeur) et un aller-retour sous le plancher
        #: (elle etait perdue **definitivement**, `compose` ne la rejouant pas
        #: et `on_mount` ne se rejouant jamais). Trouve par deux couches de la
        #: revue de vague 1, separement.
        self._etat_courant: str = ""

    def contenu(self) -> list[Widget]:
        """Les widgets de la zone centrale. Redefinie par chaque ecran reel."""
        return []

    def compose(self) -> ComposeResult:
        largeur, hauteur = self.app.size
        self._assez_grand_au_dernier_dessin = assez_grand(largeur, hauteur)
        if not self._assez_grand_au_dernier_dessin:
            # RIEN d'autre : ni bandeau, ni ligne d'etat, ni contenu tronque.
            yield Static(message_trop_petit(largeur, hauteur), id="trop-petit")
            return
        yield Static(jetons.ajuster(
            self.bandeau(largeur), jetons.largeur_utile(largeur),
            getattr(self.app, "ascii_seul", False)), id="bandeau")
        yield Vertical(*self.contenu(), id="centre")
        # La ligne d'etat est SEMEE avec ce qui etait affiche : `compose` est
        # rejoue au retour au-dessus du plancher, et repartir de la chaine vide
        # y perdait l'etat pour toute la duree de vie de l'ecran.
        yield Static(jetons.ajuster(self._etat_courant,
                                    jetons.largeur_utile(largeur),
                                    getattr(self.app, "ascii_seul", False)),
                     id="etat")
        yield Static(jetons.ajuster(self.raccourcis,
                                    jetons.largeur_utile(largeur),
                                    getattr(self.app, "ascii_seul", False)),
                     id="raccourcis")

    def bandeau(self, largeur: int | None = None) -> str:
        """Le texte du bandeau : contexte de session, palier courant substitue.

        **Le mode de repli est TRANSMIS a :meth:`Contexte.rendu`, jamais
        laisse a `compose`** (mesure du 2026-09-06, au plancher de 80x24).
        Sans lui, `rendu` composait en geometrie UTF-8 -- une ligne calee a
        exactement 76 colonnes, l'objet travaille pousse a droite -- et
        `compose` la repliait ENSUITE : `— aucun projet —` rendant
        `-- aucun projet --`, la ligne passait a 78 colonnes et
        :func:`jetons.ajuster` lui coupait la DROITE, c'est-a-dire l'objet.
        Onze des quatorze ecrans montables du produit etaient dans ce cas en
        `--ascii`, et aucun en UTF-8.

        C'est exactement la regression que le docstring de
        :meth:`Contexte.rendu` declare fermee -- « Replier AVANT de mesurer,
        jamais apres », mesure du 2026-08-28 : elle etait fermee DANS le
        module et rouverte par ses deux appelants de ce fichier, les cinq
        surcharges d'atelier (`ecran_ateliers`, `atelier_pdf`, `atelier_scan`,
        `atelier_scan_calibration`, `atelier_scan_completion`) transmettant
        deja le mode, elles. Aucune relecture ne pouvait le voir : les deux
        moities sont justes separement.

        `Palier.compose` replie une seconde fois ce que cette methode rend
        deja replie, et c'est sans effet -- le repli est idempotent, aucun
        remplacant de la table n'etant lui-meme une cle. Le laisser en place
        garde la garde utile pour les surcharges qui, elles, rendraient un
        texte brut.
        """
        session = getattr(self.app, "contexte", Contexte())
        contexte = Contexte(session.projet, self.titre, session.objet)
        return contexte.rendu(self.app.size.width if largeur is None else largeur,
                              getattr(self.app, "ascii_seul", False))

    def poser_etat(self, texte: str = "") -> None:
        """Ecrire la ligne d'etat **de ce palier**. Vide quand il n'y a rien a dire.

        Elle est posee sur l'ecran et non sur l'application, et ce n'est pas un
        detail de style : `push_screen` est differe, donc un ecran qui ecrirait
        via `app.query_one("#etat")` depuis son `on_mount` viserait encore
        l'ecran PRECEDENT -- sa ligne d'etat partirait chez le voisin et la
        sienne resterait vide. Mesure faite au developpement de la story 11.1.

        Le texte demande est **memorise brut** et ajuste a la largeur courante
        au moment d'ecrire : c'est ce qui permet de le redessiner juste apres un
        redimensionnement, sans que l'appelant ait a le recalculer.
        """
        self._etat_courant = texte
        if self._assez_grand_au_dernier_dessin:
            self.query_one("#etat", Static).update(
                jetons.ajuster(texte, jetons.largeur_utile(self.app.size.width),
                               getattr(self.app, "ascii_seul", False)))

    def rafraichir(self) -> None:
        """Redessiner ce qui depend de la largeur. Les ecrans concrets l'etendent.

        Appelee a chaque redimensionnement qui ne franchit pas le plancher.
        Sans elle, la ligne d'etat gardait le texte calcule pour l'ancienne
        largeur : 93 colonnes conservees dans une zone de 76 apres un passage
        de 120 a 80, donc un temps restant qui disparaissait sans bruit.
        """
        if not self._assez_grand_au_dernier_dessin:
            return
        self.query_one("#bandeau", Static).update(jetons.ajuster(
            self.bandeau(), jetons.largeur_utile(self.app.size.width),
            getattr(self.app, "ascii_seul", False)))
        self.query_one("#raccourcis", Static).update(
            jetons.ajuster(self.raccourcis,
                           jetons.largeur_utile(self.app.size.width),
                           getattr(self.app, "ascii_seul", False)))
        self.poser_etat(self._etat_courant)

    def on_resize(self, evenement) -> None:
        largeur, hauteur = evenement.size
        desormais = assez_grand(largeur, hauteur)
        if desormais != self._assez_grand_au_dernier_dessin:
            # Franchissement du plancher : la structure de l'ecran change, il
            # faut la reconstruire. `compose` seme la ligne d'etat memorisee.
            self.refresh(recompose=True)
            return
        if desormais:
            self.rafraichir()


class PalierTemoin(Palier):
    """Palier de remplissage, le temps que les stories d'atelier arrivent.

    Il existe pour que la navigation soit **mesurable des maintenant** : sans
    lui, l'AC 4 n'aurait rien a empiler.
    """

    def __init__(self, titre: str, raccourcis: str, ligne: str = "") -> None:
        super().__init__()
        self.titre, self.raccourcis = titre, raccourcis
        self._ligne = ligne or titre

    def contenu(self) -> list[Widget]:
        return [Static(self._ligne, classes="temoin")]

    def on_key(self, evenement) -> None:
        """`⏎` descend d'un palier -- ce que la ligne de raccourcis promet.

        **Elle le promettait sans que rien ne l'implemente** : `descendre()`
        existait, tous les tests de navigation l'appelaient en Python, et
        **aucune touche ne l'atteignait**. Le lanceur nu montrait donc trois
        paliers dont on ne pouvait sortir que par `Echap` et `q` -- une pile de
        navigation ou l'on ne peut pas descendre. Meme famille que les defauts
        de la revue de vague 1 : le modele etait mesure, le clavier ne l'etait
        pas (trouve le 2026-08-28, en rendant la vague 1 verifiable a la main).

        La liaison est posee **ici et non sur `Palier`** : un atelier des vagues
        suivantes donne a `⏎` le sens de « valider », pas de « descendre ». Ce
        raccourci appartient au palier de remplissage, qui disparaitra avec eux.
        """
        if evenement.key == "enter":
            evenement.stop()
            self.app.descendre()


class EcranPasEncore(Palier):
    """Ce qui est annonce mais pas encore construit -- et qui le DIT.

    **Consigne d'Egan, 2026-08-28** : « ce serait bien que dans les maquettes la
    navigation soit complete quitte a ne mener nulle part (si on fait enter on
    finit sur une page "cette action n'existe pas encore") comme ca on sait que
    c'est temporaire et que ce n'est pas un bug ».

    Le motif est le meme que celui que la revue de vague 1 a ferme trois fois :
    *une touche qui ne fait rien et ne dit rien est indistinguable d'un clavier
    casse*. Il s'etend ici d'un cran -- une touche qui mene a une absence doit
    dire que c'est une absence, et **quand elle sera comblee**. Sans la date, on
    ne distingue pas « pas encore fait » de « abandonne ».

    Cet ecran n'est **pas** un refus : rien n'a echoue, rien n'est invalide. Il
    ne porte donc ni le glyphe ni la couleur de `state-absent`, qui disent une
    frame manquante ou un champ refuse. Il est un **passage**, comme les ecrans
    d'execution, et n'est donc jamais installe : il ne garde aucun etat.
    """

    titre = "Pas encore"
    raccourcis = "Échap revenir  Q quitter"

    #: Ce que la ligne d'etat dit tant que cet ecran est monte. Il precise que
    #: rien n'a ete ecrit, parce que c'est la premiere question qu'un operateur
    #: se pose devant un ecran qu'il n'attendait pas.
    #: **Accentuee depuis le lot I**, meme motif que `panneau.RIEN_ECRIT`
    #: (finding `I6`) : une chaine ecrite sans accents rend le meme texte en
    #: UTF-8 et en repli ASCII. Cet ecran est desormais atteignable depuis
    #: n'importe ou par `F1`, donc son texte se lit partout.
    ETAT = "Rien n'a été écrit : cet écran n'est pas encore construit."

    #: Un passage : il nomme ce qui manque, il n'est pas une station.
    TRANSITOIRE = True

    def __init__(self, ce_qui_manque: str, quand: str = "") -> None:
        super().__init__()
        self.ce_qui_manque = ce_qui_manque
        self.quand = quand

    def lignes(self) -> list[str]:
        """Ce qui a ete demande, puis le constat, puis l'echeance."""
        lignes = [f"« {self.ce_qui_manque} »", "",
                  "Cet ecran n'existe pas encore."]
        if self.quand:
            lignes.append(f"Il arrive avec {self.quand}.")
        return lignes

    def contenu(self) -> list[Widget]:
        utile = jetons.largeur_utile(self.app.size.width)
        ascii_seul = getattr(self.app, "ascii_seul", False)
        corps = Vertical(
            *[Static(jetons.ajuster(ligne, utile - 4, ascii_seul))
              for ligne in self.lignes()],
            id="cartouche")
        corps.border_title = "Pas encore construit"
        return [corps]

    def on_mount(self) -> None:
        self.poser_etat(self.ETAT)

    def on_key(self, evenement) -> None:
        """`⏎` ne descend pas d'ici ; `Echap` DEPILE, d'ou qu'on soit venu.

        **`⏎`** : il n'y a rien en dessous, par definition. On l'**arrete**
        quand meme, pour deux raisons. D'abord parce que le laisser monter
        empilerait un second ecran « pas encore » sur le premier, et l'operateur
        devrait remonter autant de fois qu'il a appuye. Ensuite parce que la
        ligne de raccourcis de cet ecran n'annonce pas `⏎` : une touche non
        annoncee qui agit est aussi trompeuse qu'une touche annoncee qui
        n'agit pas.

        **`Echap` est traite ICI depuis `EPIC11-ARB-140` (2026-09-02), et c'est
        la fermeture d'un cul-de-sac clavier.** Cet ecran est celui que `F1`
        empile de n'importe ou. Le laisser monter jusqu'a
        :meth:`CoqueTui.action_remonter` le rendait **insortable** dans deux
        regimes, pour deux raisons differentes :

        * **pendant une tache** -- `action_remonter` voit `tache_en_cours`,
          arme `interruption_demandee` et rend la main **sans depiler**. L'aide
          restait donc montee, et l'operateur qui l'avait demandee devait
          declencher une interruption pour en sortir. Le defaut n'etait pas
          theorique : `E5-4` et `E5-6c` annoncent `F1 aide` pendant une passe
          depuis leur livraison ;
        * **a la racine** -- `rang` compte les PALIERS, et cet ecran est un
          passage (`TRANSITOIRE`). Un `F1` presse sur l'ecran projet laisse donc
          `rang == 0`, et la garde `if self.rang > 0` ne depile pas davantage,
          sans qu'aucune tache soit en cause.

        **Pourquoi ici et non dans `action_remonter`.** Depiler « un passage
        avant d'armer l'interruption » aurait porte sur TOUS les passages, donc
        aussi sur l'ecran d'interruption lui-meme et sur les ecrans de jugement
        -- exactement la faute symetrique payee le 2026-09-01, ou une fermeture
        a pose `tache_en_cours` et a empeche `action_remonter` de depiler, si
        bien que le filet de demontage ne se declenchait plus jamais. La garde
        d'`EPIC11-ARB-4` (« pendant une execution, `Echap` n'est plus une
        remontee ») reste donc **intacte** pour tout le reste, et un banc
        symetrique le mesure.

        La tache n'est **pas** touchee : ni `tache_en_cours` ni
        `interruption_demandee` ne bougent. Fermer l'aide n'est pas une decision
        sur le travail en cours.
        """
        if evenement.key == "enter":
            evenement.stop()
        elif evenement.key == "escape":
            evenement.stop()
            # `len(...) > 1` et non `rang > 0` : cet ecran est un passage, il
            # ne compte pas comme palier. C'est la hauteur REELLE de la pile
            # qui dit s'il y a quelque chose sous lui.
            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()


def paliers_temoins() -> list[Palier]:
    """Les trois etages de `EPIC11-ARB-2`, montes avec des contenus temoins.

    **Trois elements distincts, deliberement** (regle des fabriques de
    `CLAUDE.md`) : une pile a un seul palier rendrait la remontee inobservable,
    et une pile a deux ne distinguerait pas « remonter d'un » de « remonter
    jusqu'a la racine » -- ce que l'AC 4.2 separe justement.
    """
    return [
        PalierTemoin("Projet", "⏎ ouvrir  Q quitter", "Projet"),
        PalierTemoin("Ateliers", "⏎ entrer  Échap projet  Q quitter",
                     "Ateliers"),
        PalierTemoin("Extraction",
                     "⏎ entrer  Échap ateliers  Q quitter", "Extraction"),
    ]


class CoqueTui(App):
    """L'application : la pile de paliers, le plancher, l'appel du coeur."""

    BINDINGS = [("escape", "remonter", "Remonter"),
                ("f1", "aide", "Aide"),
                ("q", "quitter", "Quitter")]

    #: L'echeance annoncee par les ecrans « pas encore », ecrite UNE fois :
    #: deux formulations differentes d'un ecran a l'autre feraient croire a
    #: deux echeances differentes.
    QUAND_ARRIVENT_LES_ATELIERS = "les ateliers de la vague 3"

    # **Ce que `F1` ouvre, et l'histoire de la liaison** (finding `I8` du lot I,
    # mesure le 2026-08-30) : « `F1 aide` etait promis par trente-neuf maquettes
    # et par sept lignes de raccourcis du produit, et n'etait implemente NULLE
    # PART ». La promesse a d'abord ete tenue par un ecran « pas encore », qui
    # nommait l'absence et son echeance -- le motif qu'Egan a pose le
    # 2026-08-28 : « quitte a ne mener nulle part [...] comme ca on sait que
    # c'est temporaire et que ce n'est pas un bug ».
    #
    # **Depuis la story 11.9, elle est tenue pour de bon** : `action_aide`
    # empile `tui/ecran_manuel.EcranManuel`, derive du paquet par
    # `tui/manuel.py`. Les deux constantes qui tenaient la place --
    # `CE_QU_OUVRE_F1` et `QUAND_ARRIVE_L_AIDE` -- sont retirees dans le meme
    # mouvement : elles nommaient une absence qui n'existe plus, et une
    # constante que plus rien ne lit est exactement le « composant que rien ne
    # cable » que le docstring d'`ObjetTravaille` donne comme mode de panne.

    def __init__(self, paliers: list[Palier] | None = None,
                 contexte: Contexte | None = None,
                 sans_couleur: bool = False,
                 ascii_seul: bool = False,
                 memoires: MemoiresDeSession | None = None) -> None:
        super().__init__()
        self.sans_couleur = sans_couleur
        self.ascii_seul = ascii_seul
        #: **Le registre des memoires de session de l'explorateur** (2026-09-06,
        #: retour d'Egan « l'explorateur de fichiers ne retient pas le dernier
        #: chemin explore »). Une memoire par famille d'usage ; voir
        #: `explorateur.FAMILLES` pour le motif de la granularite.
        #:
        #: **Il vit sur l'APPLICATION et non sur un module**, pour la meme
        #: raison que `CSS` est pose sur l'instance juste en dessous : deux
        #: coques d'un meme processus -- ce que le banc monte a chaque fichier
        #: -- doivent avoir des memoires distinctes. Un registre de module en
        #: ferait fuir une d'un test a l'autre.
        #:
        #: C'est aussi le SEUL endroit ou les ecrans peuvent se le partager :
        #: `EcranProjet` est construit avant l'application (`ChaineReelle`) et
        #: les ecrans d'atelier sont montes bien plus tard, si bien qu'aucun
        #: point de construction commun n'existe. Les ecrans le lisent donc par
        #: `self.app`, au moment ou ils ouvrent leur explorateur --
        #: `ecran_projet.CoutureExplorateur.reprendre_la_memoire_de_session`.
        from .explorateur import MemoiresDeSession
        self.memoires = memoires if memoires is not None else MemoiresDeSession()
        # `CSS` est un attribut de CLASSE cote textual ; on le pose sur
        # l'INSTANCE pour que deux coques aux modes differents coexistent dans
        # un meme processus -- ce que le banc de test fait a chaque fichier.
        self.CSS = feuille(sans_couleur)
        self._paliers = list(paliers) if paliers else paliers_temoins()
        self.contexte = contexte or Contexte()
        #: Vrai des qu'une tache tourne. `q` demande alors confirmation au lieu
        #: de quitter, et `Echap` cesse d'etre une remontee (`DESIGN.md`
        #: section 4). La story 11.1 pilote ces trois drapeaux.
        self.tache_en_cours = False
        self.confirmation_de_sortie_demandee = False
        self.interruption_demandee = False

    # -- clavier ---------------------------------------------------------------

    #: Le prefixe qu'un terminal colle a une touche tapee juste apres `Echap`.
    #: Il ne vient pas d'un vrai `Alt` : voir :meth:`on_event`.
    PREFIXE_ECHAPPEMENT = "alt+"

    @classmethod
    def normaliser(cls, touche: str) -> str:
        """Rend le nom de touche debarrasse du prefixe d'echappement.

        Fonction pure, exposee pour etre mesurable sans monter d'application --
        le defaut qu'elle repare ne se voit qu'a travers un pilote de terminal,
        que le banc n'a pas.
        """
        if touche.startswith(cls.PREFIXE_ECHAPPEMENT):
            return touche[len(cls.PREFIXE_ECHAPPEMENT):]
        return touche

    async def on_event(self, evenement) -> None:
        """Point d'entree unique du clavier, **avant** l'ecran.

        `App.on_event` est ce qui transmet l'evenement a l'ecran monte : le
        normaliser ici, et non dans chaque `on_key`, fait que les liaisons de
        l'application **et** les ecrans voient tous la meme touche. Une
        normalisation par ecran aurait produit autant d'implementations que
        d'ecrans, chacune verte chez elle -- le defaut de couture que la story
        11.1 invoque comme sa raison d'etre.

        **Pourquoi normaliser.** `Echap` emet ``, qui est aussi le prefixe
        de **toute** sequence d'echappement (fleches, F1, focus du terminal).
        Le parseur de `textual` ne peut pas distinguer les deux autrement qu'en
        attendant `ESCDELAY` ; toute touche tapee dans cette fenetre est collee
        a l'echappement et rendue **prefixee**. Mesure faite sur le parseur :
        `Echap` puis `q` rend `alt+q`, que rien ne reconnaissait -- donc une
        touche annoncee en ligne de raccourcis devenait **inerte**. C'est le
        defaut que la revue de vague 1 a ferme trois fois (« une touche qui ne
        fait rien et ne dit rien est indistinguable d'un clavier casse »),
        revenu par la seule couche que le banc ne traverse pas.

        **Ce que ca coute, et pourquoi c'est acceptable.** Un vrai `Alt+X` et un
        `Echap` suivi de `X` sont **indistinguables** a ce niveau : c'est ainsi
        que les terminaux fonctionnent, pas une approximation de notre part.
        Normaliser revient donc a decider que `Alt` n'est pas un modificateur de
        cette interface -- ce que `DESIGN.md` tient deja : aucune maquette,
        aucune ligne de raccourcis n'emploie `Alt`. Un test de frontiere le
        mesure, pour que lier une touche `alt+` un jour fasse rougir plutot que
        de disparaitre en silence.

        **Reserve d'Egan, 2026-08-28** : il a observe le meme blocage en
        attendant *bien plus* de 100 ms entre deux touches, ce que ce mecanisme
        seul n'explique pas. La normalisation reste juste et necessaire, mais
        **elle n'est pas presumee suffisante** : `trace_clavier.py` journalise
        desormais les caracteres bruts recus, pour que la prochaine observation
        tranche entre « la touche n'arrive pas » et « elle arrive et n'est pas
        traitee ».
        """
        touche = getattr(evenement, "key", None)
        if touche is not None and not evenement.is_forwarded:
            normalisee = self.normaliser(touche)
            if normalisee != touche:
                from textual import events as _evenements
                evenement = _evenements.Key(normalisee,
                                            getattr(evenement, "character", None))
        await super().on_event(evenement)

    # -- etat -----------------------------------------------------------------

    def get_default_screen(self) -> Screen:
        """Le palier 0 est l'ecran par defaut : la racine de la pile."""
        return self._paliers[0]

    def on_mount(self) -> None:
        """Declarer les paliers PERSISTANTS, sans quoi `textual` les detruit.

        `App._replace_screen` fait `await screen.remove()` sur tout ecran depile
        qui n'est ni installe ni present dans une autre pile. Or les paliers sont
        construits **une fois** et `descendre()` reempile ces memes instances :
        sans cette declaration, remonter d'un palier **detruit** celui qu'on
        quitte, et y redescendre reempile un ecran mort, qui se recompose avec de
        nouveaux widgets.

        La pile restait juste -- c'est pourquoi trois mesures successives sur
        `rang` et `screen.titre` n'ont rien vu --, mais le chemin de peinture,
        lui, differait : deux mises a jour au lieu de quatre au re-push, et une
        peinture vide visant l'ecran precedent a l'evenement suivant. **Egan a
        decrit exactement cela dans son terminal le 2026-08-28** : « les
        commandes sont bien enregistrees mais il y a un delai d'affichage, on
        saute une commande a l'affichage ».

        **Un palier revisite retrouve son etat la ou on l'a laisse**, tranche par
        Egan le 2026-08-28. C'est ce que cette declaration donne, et c'est
        pourquoi elle est preferee a l'autre issue -- empiler un palier neuf a
        chaque descente, qui aurait donne l'inverse.

        Les ecrans que les ateliers empilent par `descendre(ecran)` ne sont
        **pas** installes, et c'est voulu : un ecran de confirmation ou
        d'execution est ouvert pour un travail precis et n'a aucun etat a
        retrouver. La distinction est celle du `DESIGN.md` : les paliers sont des
        stations, les ecrans sont des passages.
        """
        for rang, palier in enumerate(self._paliers):
            if not self.is_screen_installed(palier):
                self.install_screen(palier, name=f"palier-{rang}")

    @property
    def rang(self) -> int:
        """Rang du palier monte. 0 = la racine.

        **Il compte les PALIERS, pas la hauteur de la pile.** La difference
        n'est pas theorique : un formulaire de creation ou un panneau de
        confirmation occupe une hauteur sans etre une station, et le rang le
        comptait. `descendre()` sautait alors un palier entier, `Echap`
        redescendait dans le formulaire qu'on venait de quitter, et
        `revenir_aux_ateliers()` atterrissait sur un formulaire abandonne la
        ou `EPIC11-ARB-13` promet le menu. Trois symptomes, une seule ligne.
        """
        return sum(1 for ecran in self.screen_stack
                   if isinstance(ecran, Palier) and not ecran.TRANSITOIRE) - 1

    @property
    def passages_empiles(self) -> int:
        """Combien d'ecrans transitoires sont poses au-dessus du palier monte.

        Mesurable de l'exterieur : c'est ce qui permet a un test de distinguer
        « je suis sur le palier 1 » de « je suis sur un formulaire pose sur le
        palier 1 », que `rang` seul confond par construction.
        """
        combien = 0
        for ecran in reversed(self.screen_stack):
            if not (isinstance(ecran, Palier) and ecran.TRANSITOIRE):
                break
            combien += 1
        return combien

    def _oublier_les_passages(self) -> None:
        """Depiler les ecrans transitoires poses au-dessus du palier courant.

        **Un passage ne reste pas sur le chemin du retour.** Sans ce
        depilement, valider un formulaire puis descendre laissait le formulaire
        enterre sous le palier atteint, et `Echap` y redescendait -- ce
        qu'Egan a decrit comme « Echap agit comme precedent plutot que comme
        remonter », en devant appuyer de nombreuses fois pour revenir.
        """
        while self.passages_empiles and len(self.screen_stack) > 1:
            self.pop_screen()

    @property
    def palier_courant(self) -> Palier:
        return self.screen

    @property
    def glyphes(self):
        """La table de glyphes du mode courant (UTF-8 ou repli ASCII)."""
        return jetons.glyphes(self.ascii_seul)

    @property
    def assez_grand(self) -> bool:
        largeur, hauteur = self.size
        return assez_grand(largeur, hauteur)

    def poser_etat(self, texte: str = "") -> None:
        """Ecrit la ligne d'etat du palier monte, par delegation a ce palier."""
        self.palier_courant.poser_etat(texte)

    # -- navigation -----------------------------------------------------------

    def descendre(self, palier: Palier | None = None) -> None:
        """Entrer d'un palier.

        Sans argument, on descend d'un cran dans les paliers connus de la
        session ; un palier fourni est empile tel quel -- c'est par la que les
        ateliers des stories suivantes entrent, sans que la coque ait a les
        connaitre.
        """
        if palier is None:
            if isinstance(self.screen, EcranPasEncore):
                # **La garde est ici, et pas seulement sur la touche.** Un
                # `on_key` qui arrete `⏎` protege le clavier ; il ne protege pas
                # un appelant qui passe par l'API -- ce que fera chaque atelier
                # des la vague 3. Sans cette ligne, cinq appels empilaient cinq
                # ecrans « pas encore », et l'operateur devait remonter cinq
                # fois. Trouve par le volet a cinq descentes, jamais par celui a
                # une seule.
                return
            if self.rang + 1 >= len(self._paliers):
                # **Jamais un retour muet.** Le dernier palier annonce `⏎` comme
                # les autres ; sans cet ecran, la touche ne faisait rien et ne
                # disait rien, ce qu'Egan a lu comme un blocage plutot que comme
                # une absence (2026-08-28). On nomme ce qui manque et quand il
                # arrive, sans quoi « pas encore fait » et « abandonne » se
                # ressemblent.
                # Sans guillemets ici : c'est `EcranPasEncore.lignes()` qui les
                # pose, une fois. Les mettre aux deux endroits donnait
                # « La suite de « Extraction » ».
                self.push_screen(EcranPasEncore(
                    f"La suite de {self.screen.titre}",
                    self.QUAND_ARRIVENT_LES_ATELIERS))
                return
            palier = self._paliers[self.rang + 1]
            # **Les passages tombent AVANT d'empiler la station suivante.** Un
            # formulaire valide n'est pas une etape du retour ; le garder
            # enterre est ce qui faisait redescendre `Echap` dedans.
            self._oublier_les_passages()
        self.push_screen(palier)

    def action_aide(self) -> None:
        """`F1` : ouvrir le MANUEL des raccourcis (story 11.9, lot C).

        **Elle ne s'empile pas sur elle-meme** : `descendre` porte deja la garde
        pour les ecrans « pas encore », mais elle ne vaut que pour l'appel sans
        argument. Ici l'ecran est fourni, donc la garde est reprise -- sans
        quoi cinq `F1` empileraient cinq ecrans identiques, et l'operateur
        devrait remonter cinq fois. C'est le defaut mesure le 2026-08-28 sur
        `descendre`, repris par l'autre bout. **Elle vise desormais le manuel**
        (AC 5.3) : la garder sur `EcranPasEncore` l'aurait laissee proteger un
        ecran que `F1` n'ouvre plus.

        **L'import est fait DANS LE CORPS, et c'en est la raison d'etre**
        (AC 3.5). `tui/manuel.py` balaie tout le paquet a l'appel, et
        `tui/ecran_manuel.py` importe `coque` comme le font vingt-cinq autres
        modules : un import au niveau de ce module-ci rendrait le cycle, et la
        TUI ne demarrerait plus. Le cout est nul -- le module n'est charge que
        le jour ou quelqu'un demande l'aide.
        """
        from .ecran_manuel import EcranManuel

        if isinstance(self.screen, EcranManuel):
            return
        self.push_screen(EcranManuel())

    def action_remonter(self) -> None:
        """`Echap` : remonte d'UN palier, jamais deux (`EPIC11-ARB-2`).

        Rien n'est ecrit au passage. Ce n'est pas une precaution mais une
        propriete : la coque **depile un ecran**, elle n'a aucun chemin vers le
        disque, et l'AC 4.3 le mesure en comptant les fichiers d'un repertoire
        temoin.
        """
        if self.tache_en_cours:
            # Pendant une execution, `Echap` n'est plus une remontee : la story
            # 11.1 monte ici l'ecran d'interruption.
            self.interruption_demandee = True
            return
        if self.rang > 0:
            self.pop_screen()

    #: Rang du menu des ateliers dans la pile : palier 0 = ecran projet,
    #: palier 1 = menu des ateliers. `EPIC11-ARB-13` renvoie la, jamais a
    #: l'ecran projet -- l'operateur qui vient d'ecrire enchaine dans le meme
    #: projet, il ne recommence pas par en choisir un.
    RANG_DES_ATELIERS = 1

    def revenir_aux_ateliers(self) -> None:
        """Depiler jusqu'au menu des ateliers du projet ouvert.

        Depiler **jusqu'a un rang** et non « d'un cran » : une execution peut
        avoir empile confirmation, execution puis resultat, et remonter d'un
        seul palier laisserait l'operateur sur l'ecran d'execution d'une tache
        finie.
        """
        # Deux conditions, et la seconde est celle qui manquait : on depile tant
        # qu'on est trop bas, **et** tant que le sommet est un passage. Sans
        # elle, une remontee s'arretait sur un formulaire pose au rang des
        # ateliers au lieu du menu -- troisieme occurrence de `V2-M1`, encore
        # latente quand la revue l'a trouvee.
        while len(self.screen_stack) > 1 and (
                self.rang > self.RANG_DES_ATELIERS or self.passages_empiles):
            self.pop_screen()
        self.oublier_la_tache()

    def retirer_l_ecran(self, ecran) -> bool:
        """Retirer `ecran` de la pile **ou qu'il soit**, avec ce qui le couvre.

        Rend vrai si l'ecran etait la, faux s'il n'y etait pas.

        **Le defaut que cette aide ferme, et il avait deja ete repare une fois.**
        Le 2026-09-07, la couche 2 de la revue a mesure que le cul-de-sac
        d'encode -- « Oblige de quitter », remonte du terrain la veille --
        **rouvrait entier** apres son correctif. Celui-ci depilait l'ecran de la
        passe *seulement s'il etait au sommet* :

        ``if self.screen is ecran: self.pop_screen()``

        Or il ne l'est plus des que l'operateur a ouvert quoi que ce soit
        pendant la passe -- et les **deux seules touches** que l'ecran
        d'encodage annonce, `Echap` (interruption) et `F1` (aide), font
        exactement cela. La condition etait donc fausse precisement dans le
        regime qu'elle devait couvrir : le geste litteral d'Egan.

        **La garde par identite reste, elle change seulement de role.** Elle
        etait employee comme *condition de depilement*, ou elle est
        insuffisante ; elle est ici *condition d'arret*, ou elle est juste --
        on depile jusqu'a l'ecran vise inclus, et on ne touche a rien si cet
        ecran n'est pas dans la pile. Un `pop_screen` inconditionnel, lui,
        retirerait l'ecran de quelqu'un d'autre.

        **Ce que cette aide NE fait pas, dit plutot que tu** : elle depile ce
        qui couvre l'ecran vise, donc un formulaire que l'operateur aurait
        ouvert par-dessus disparait sans etre valide. C'est voulu -- ces ecrans
        sont les transitoires d'une passe terminee, et les laisser flotter
        au-dessus d'un ecran mort est exactement le cul-de-sac qu'on ferme --
        mais ca reste une perte de contexte, pas un depilement neutre.
        """
        if ecran is None or ecran not in self.screen_stack:
            return False
        # Le plancher `> 1` est ce qui empeche de vider la pile : un
        # depilement de trop rendrait l'application a rien, et c'est le bord que
        # la garde precedente tenait bien. Il est conserve tel quel.
        while len(self.screen_stack) > 1 and ecran in self.screen_stack:
            self.pop_screen()
        return True

    def oublier_la_tache(self) -> None:
        """Eteindre les TROIS drapeaux d'une execution finie, pas seulement un.

        `interruption_demandee` et `confirmation_de_sortie_demandee` etaient
        poses a vrai et **aucun chemin ne les remettait a faux** : ils ne sont
        lus que par les tests aujourd'hui, mais un atelier qui les consulterait
        verrait une interruption demandee bien apres la fin de la tache. C'est
        la classe « defaut de couture entre deux stories » que le docstring de
        `execution.py` cite comme motif de la story (revue de vague 1, couche 2).
        """
        self.tache_en_cours = False
        self.interruption_demandee = False
        self.confirmation_de_sortie_demandee = False

    def action_quitter(self) -> None:
        """`q` quitte, sauf si une tache tourne : il demande confirmation."""
        if self.tache_en_cours:
            self.confirmation_de_sortie_demandee = True
            return
        self.exit()

    # -- appel du coeur -------------------------------------------------------

    def executer_en_processus(self, fonction: Callable[..., Any],
                              *args: Any, **kwargs: Any) -> Any:
        """Appelle une fonction du coeur **dans le processus courant**.

        `EPIC11-ARB-1` : le coeur est heberge, pas relance. L'appel direct est
        donc l'implementation entiere, et cette methode existe pour **nommer**
        la frontiere -- un futur `subprocess` se verrait ici, et la frontiere
        negative de l'AC 5.2 (aucun `subprocess`, `Popen`, `os.system`,
        `os.exec*` dans le paquet) la mesure a zero.

        L'ecran reste monte pendant l'appel : la fonction recoit une TUI
        vivante, ce que l'AC 5.1 verifie en assertant sur l'arbre de widgets
        **pendant** l'appel et non apres.
        """
        return fonction(*args, **kwargs)
