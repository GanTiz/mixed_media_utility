# -*- coding: utf-8 -*-
"""Le palier 0 : ouvrir un projet, ou en creer un (story 11.2).

Quatre ecrans des maquettes, **deux classes**. `E0-1`, `E0-2` et `E0-3` ne sont
pas trois ecrans mais **trois etats du meme ecran** -- les maquettes montrent la
meme liste de recents et le meme champ de chemin dans les trois, seul le focus
et le bas de la zone centrale changent. En faire trois `Screen` aurait empile
trois paliers la ou `EPIC11-ARB-2` en veut un, et `Echap` aurait remonte trois
fois pour revenir a la liste.

`E0-4` est un ecran a part, et lui aussi pour une raison de fond : c'est le seul
du palier qui **ecrit**.

**Ce module n'ecrit aucun projet lui-meme** : il appelle
:func:`mixed_media_utility.gui.depot_projets.creer_projet`. Voir le docstring de
:mod:`.projets` pour le motif.
"""
from __future__ import annotations

from typing import Callable

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from ..gui.depot_projets import (
    NOM_FICHIER_PROJET,
    NamingError,
    ProjetExistantError,
    creer_projet,
    dossier_cible,
)
from ..io.project_layout import BASE_SUBDIRS
from . import explorateur, jetons, projets
from .coque import Palier
from .panneau import ChoixExclusif, Issue

# ---------------------------------------------------------------------------
# Textes d'ecran. Ils vivent en constantes pour deux raisons mesurables : les
# frontieres negatives de la story les balayent (AC 4.2 et 4.5), et un texte
# ecrit deux fois divergerait au premier ajustement.
# ---------------------------------------------------------------------------

TITRE_OUVRIR = "Ouvrir un projet"
TITRE_CREER = "Creer un projet"

#: Ce que `E0-1` dit sous le filet. **La phrase existe parce que c'est
#: exactement l'ambiguite qu'un operateur redoute devant une touche `Suppr`
#: posee a cote de noms de projets** (`EPIC11-ARB-39`).
PHRASE_SUPPR = "Suppr retire de la liste -- le dossier du projet n'est pas touche"

#: Premier lancement. « Pas de liste vide decorative » : la liste n'est pas
#: montee du tout, et cette phrase prend sa place.
PHRASE_AUCUN_RECENT = ("aucun projet ouvert recemment -- indiquez un dossier "
                       "de projet")

PHRASE_AUTRE_DOSSIER = "Ouvrir un autre dossier..."
LIBELLE_CHEMIN = "Dossier du projet"
LIBELLE_PARENT = "Dossier parent"
LIBELLE_NOM = "Nom du projet"

#: Aide du champ parent, reprise de la maquette `E0-4`. Elle dit ce que le champ
#: attend, pas ce qu'il s'appelle -- « une aide qui paraphrase le libelle est un
#: defaut » (`EPIC11-ARB-14`).
AIDE_PARENT = "le dossier qui CONTIENDRA le projet"

#: Les trois suites de `E0-3` (`EPIC11-ARB-22`). Aucune n'est preselectionnee :
#: c'est `ChoixExclusif` qui le garantit, a la construction.
ISSUE_CREER = "creer-ici"
ISSUE_CORRIGER = "corriger-le-chemin"
ISSUE_RECENTS = "revenir-aux-recents"


def issues_du_refus() -> ChoixExclusif:
    """Les trois suites de `E0-3`, dans l'ordre de la maquette.

    « Creer un projet ici » est en tete parce que c'est la bifurcation
    qu'`EPIC11-ARB-22` a ajoutee pour que l'ecran cesse d'etre un cul-de-sac --
    mais **elle n'est pas retenue pour autant**, et c'est la difference entre
    proposer et decider a la place de l'operateur.
    """
    return ChoixExclusif([
        Issue(ISSUE_CREER, "Creer un projet ici", ecrit=False),
        Issue(ISSUE_CORRIGER, "Corriger le chemin", ecrit=False),
        Issue(ISSUE_RECENTS, "Revenir aux recents", ecrit=False),
    ])


#: Les lignes de raccourcis du palier 0. **Contextuelles** : « elle ne montre
#: que ce qui marche sur l'ecran courant » (`DESIGN.md` section 4). Les trois
#: raccourcis universels -- `Echap`, `F1`, `q` -- gardent leur place relative
#: dans toutes.
#:
#: Elles sont des constantes de MODULE pour etre balayees une par une par la
#: garde d'epic de `test_repli_ascii.py` : une ligne calculee a la volee
#: echapperait a la mesure de largeur et a celle du repli ASCII.
#:
#: **La regle de nommage, posee ici une fois et mesuree** (finding `F-17` de la
#: revue de vague 2 bis, ou la meme touche portait quatre libelles) : *un
#: libelle nomme ce que la touche fait a cet instant, et deux gestes
#: identiques portent le meme mot*. Trois consequences, toutes prises sur les
#: neuf maquettes validees :
#:
#: * **`Tab` nomme sa DESTINATION** -- `Tab explorateur` quand il y entre
#:   (`X9`), `Tab chemin` quand il entre dans la barre d'adresse (`X1`, `X7`),
#:   `Tab liste` quand il en sort (`X5`, `X8`). Le defaut corrige est precis :
#:   `Tab chemin` designait a la fois l'explorateur (depuis les recents) et la
#:   barre d'adresse (depuis la liste) -- un meme mot pour deux destinations ;
#: * **`⏎` dit `valider` dans les trois lignes de l'explorateur**, jamais
#:   `ouvrir` : c'est le verbe d'`EPIC11-ARB-49` (« `⏎` **valide** l'entree
#:   sous le curseur »), celui de l'etiquette du bas rendue par le composant
#:   (`⏎  Valider   <nom>`), et **le seul vrai aux cinq sites** -- sur `E0-4`
#:   la touche ne fait rien ouvrir, elle retient un dossier parent ;
#: * **`Échap` dit `sortir` dans les trois lignes de l'explorateur**, jamais
#:   `récents` : meme motif, `récents` etait la destination d'`E0-2` seulement.
#:   Sur `E0-4` la meme touche revient au formulaire. Libelle verbatim
#:   d'`EPIC11-ARB-51` et des maquettes `X1` a `X8`.
#:
#: **`↑↓ liste` est RENDU ici le 2026-08-31** (`EPIC11-ARB-122`), et le calcul
#: qui l'avait fait tomber vaut d'etre garde parce qu'il dit ce qui a change.
#: Mesure en repli ASCII, ou `⏎` vaut six colonnes : les six jetons font
#: `Entree ouvrir`(13) + `^v liste`(8) + `Suppr retirer`(13) +
#: `Tab explorateur`(15) + `F1 aide`(7) + `Q quitter`(9) = 65. Avec cinq
#: separateurs de TROIS cela faisait 80 pour une zone de 76, et `↑↓ liste`
#: tombait. Avec des separateurs de DEUX cela fait **75**, et il revient.
#:
#: Ce n'etait donc pas le jeton qui etait de trop, c'etait le separateur. Egan
#: le 2026-08-31 : « idealement il faudrait que tous les raccourcis
#: apparaissent. Ou garder ceux qu'on a deja enleves une fois. »
#: **Majuscule d'affichage, touche NUE en minuscule** -- la regle des
#: majuscules de raccourci, ecrite en entier dans `coque.py`. La lettre
#: annoncee ici est en majuscule ; la touche cablee reste la minuscule.
RACCOURCIS_RECENTS = ("⏎ ouvrir  ↑↓ liste  Suppr retirer  Tab explorateur  "
                      "F1 aide  Q quitter")
#: `EPIC11-ARB-49`/`51`/`56` : `⏎ valider` vient EN TETE, c'est l'action
#: principale et sa place la rend decouvrable ; `Tab` n'annonce plus que son
#: seul role ; et **aucune touche ne descend en ligne d'etat**. Ligne
#: identique, jeton pour jeton, a celle de la maquette `X1`.
RACCOURCIS_CHEMIN = ("⏎ valider  → entrer  ← parent  ↑↓ liste  "
                     "Tab chemin  Échap sortir")
#: **La variante de `RACCOURCIS_CHEMIN` quand le dossier courant porte des
#: elements caches** (`EPIC11-ARB-56` : `Ctrl+H` « quitte la ligne d'etat pour
#: celle des raccourcis, ou est sa place »), et c'est ce que la maquette `X7`
#: -- la seule des neuf ou un dossier cache existe -- montre.
#:
#: **Pourquoi une variante et pas un septieme jeton dans la ligne nominale :
#: les sept ne tiennent pas.** Mesure faite, en repli ASCII, ou `⏎` coute six
#: colonnes (`Entree`) : `Entree valider`(14) + `> entrer`(8) + `< parent`(8) +
#: `^v liste`(8) + `Tab chemin`(10) + `Ctrl+H caches`(13) + `Echap sortir`(12)
#: = 73, plus les separateurs. C'est `Tab chemin` qui tombe.
#:
#: **Ce commentaire a raconte le contraire jusqu'au 2026-08-31** (finding `R18`
#: de la revue) : il expliquait la chute de `↑↓ liste` et annoncait « 67
#: colonnes en ASCII, 62 en UTF-8 ». Or `EPIC11-ARB-122` a resserre le
#: separateur a deux blancs, rendu six colonnes, et RENDU `↑↓ liste` a cette
#: ligne -- que la constante porte donc, juste en dessous. Un commentaire qui
#: raconte l'histoire inverse de la ligne qu'il commente est pire qu'aucun
#: commentaire. Mesure du jour : **68 colonnes en UTF-8, 73 en repli**, pour une
#: zone de 76.
#: MESURE: 68/73
RACCOURCIS_CHEMIN_CACHES = ("⏎ valider  → entrer  ← parent  ↑↓ liste  "
                            "Ctrl+H cachés  Échap sortir")
#: **La variante du mode SELECTION** (`EPIC11-ARB-103`), et elle est la ligne
#: que les maquettes `X10`, `X11` et `X11b` portent, jeton pour jeton.
#:
#: Elle existe depuis la story 11.5, lot E bis, parce qu'`E3-1` est le premier
#: site a demander `selection_multiple` : jusque-la, `Espace cocher` etait un
#: geste qui marchait et que **aucune ligne n'annoncait**, ce que la revue de la
#: 11.2c a remonte comme finding et renvoye nommement ici -- « le budget est a
#: refaire au moment ou l'ecran existe ».
#:
#: **C'est `↑↓ liste` qui tombe, et le budget le dit** : `RACCOURCIS_CHEMIN`
#: plus `Espace cocher` pese 85 colonnes en repli ASCII pour une zone de 76. La
#: maquette validee avait deja tranche de la meme facon. MESURE: 70/75.
#:
#: **`Ctrl+H` n'a pas de variante ici, et c'est dit plutot que taire** : la
#: remplacer par `Tab chemin` couterait trois colonnes de plus (78 en repli), et
#: le mode selection n'a donc pas l'annonce des caches que `EPIC11-ARB-56` a
#: rendue au mode simple. La bascule fonctionne, elle n'est pas annoncee : c'est
#: un finding, pas un choix de confort.
RACCOURCIS_CHEMIN_SELECTION = ("⏎ valider  Espace cocher  → entrer  ← parent  "
                               "Tab chemin  Échap sortir")
#: Quand la saisie a le focus : `←→` deplacent le point d'insertion, et le
#: dire est ce qui rend l'etat lisible autant que la surbrillance.
#:
#: **`Ctrl+V coller` a disparu de cette ligne, et ce n'est pas un renoncement :
#: c'etait une promesse qu'aucun terminal ne tient.** Le collage arrive par le
#: `Paste` du *bracketed paste* (`textual` l'active au demarrage, cf.
#: `drivers/linux_driver.py`), c'est-a-dire par le geste de collage du
#: terminal -- `Ctrl+Maj+V` sous GNOME Terminal et Konsole, `Cmd+V` sous macOS,
#: `Ctrl+V` ou clic droit sous Windows Terminal. L'application ne recoit alors
#: **aucune touche** : le texte lui est livre tel quel. Nommer une de ces trois
#: touches serait faux sur les deux autres systemes, d'ou le libelle generique.
#:
#: **`Coller par le terminal`, et plus `Coller : terminal`** (defaut `F4` de la
#: couche 3, 2026-09-03). Le `:` etait un **sous-separateur**, et un
#: sous-separateur ne survit pas au passage en deux colonnes : le manuel des
#: raccourcis decoupe un item sur les blancs et prend le premier mot comme
#: ouvreur, si bien qu'il publiait `Coller       : terminal` -- un deux-points
#: orphelin en tete de colonne, visible par l'operateur. Le libelle reste
#: generique, il cesse seulement d'employer une ponctuation comme grammaire.
#: Mesure : 70 colonnes en UTF-8, 75 en repli, pour 76 utiles.
RACCOURCIS_SAISIE = ("⏎ valider  ←→ curseur  Coller par le terminal  "
                     "Tab liste  Échap sortir")
RACCOURCIS_REFUS = ("⏎ choisir  ↑↓ naviguer  Échap récents  "
                    "F1 aide  Q quitter")
#: `E0-4`, hors explorateur. **`Tab champ` a disparu** : depuis
#: `EPIC11-ARB-48`, le champ « dossier parent » n'est plus une saisie mais
#: l'explorateur, et `Tab` y mene -- c'est le meme geste que depuis les
#: recents, donc le meme mot. Le seul champ qui reste une saisie de texte est
#: le nom du projet, qui n'est pas un chemin a parcourir.
RACCOURCIS_CREATION = ("⏎ créer  Tab explorateur  Échap récents  "
                       "F1 aide  Q quitter")

#: Les trois etats de l'ecran d'ouverture. Ce ne sont pas trois ecrans : voir le
#: docstring du module.
ZONE_RECENTS = "recents"
#: **L'explorateur est a l'ecran.** Nom partage par `E0-2` et `E0-4` : c'est le
#: meme composant, dans le meme etat, et lui donner deux noms aurait fait deux
#: coutures la ou `EPIC11-ARB-48` en veut une.
ZONE_CHEMIN = "chemin"
ZONE_REFUS = "refus"
#: `E0-4` hors explorateur : les deux valeurs et l'apercu de ce qui sera cree.
ZONE_FORMULAIRE = "formulaire"

#: Ce que `⏎` repond quand il n'y a rien sous le curseur (dossier vide,
#: adresse vide). Partagee par les deux ecrans : deux phrases pour le meme
#: refus divergeraient au premier ajustement.
PHRASE_RIEN_A_VALIDER = "Rien a valider ici."


def _porte_un_projet(dossier) -> bool:
    """Un dossier porte-t-il un projet lisible ?

    Passe a l'explorateur pour qu'il marque `● projet` en naviguant. C'est ce
    qui permet de VOIR ses projets au lieu de les deviner -- le seul ajout de
    l'explorateur a ce que la liste des recents dit deja.

    **UN DOSSIER QU'ON N'A PAS LE DROIT DE LIRE N'EST PAS UNE PANNE**, il n'est
    simplement pas marque (pose le 2026-09-08, sur un plantage REEL de la CI
    publique). `diagnostiquer` sonde le disque : `Path.exists()` re-leve
    `EACCES` -- il n'ignore que `ENOENT`, `ENOTDIR`, `EBADF` et `ELOOP` --, et
    `iterdir()` de meme. Un seul sous-dossier interdit dans le dossier ouvert
    faisait donc tomber l'explorateur ENTIER : mesure sur les trois jobs du
    runner GitHub, ou `/tmp` porte un `snap-private-tmp` en root, et le meme
    plantage attend l'operateur qui ouvre un dossier parent quelconque.

    Le reste de l'explorateur garde deja chacun de ses `iterdir()` ; c'est ce
    predicat-ci, passe de l'exterieur, qui etait le seul chemin non garde. Il
    rend donc `False` : « je ne peux pas voir, donc je ne marque pas », ce qui
    est la reponse vraie -- et le balayage continue au lieu de s'arreter.
    """
    try:
        return projets.diagnostiquer(dossier).etat == projets.PROJET_LISIBLE
    except OSError:
        return False


#: Ce que `Ctrl+V` repond dans la saisie. **La touche ne colle pas -- elle dit
#: quoi presser**, et c'est le seul service qu'elle puisse rendre : quand elle
#: parvient jusqu'a l'application, c'est justement que le terminal ne l'a PAS
#: interpretee comme un collage, donc qu'aucun texte n'accompagne la frappe.
#: L'application n'a aucun acces au presse-papier du systeme -- `App.clipboard`
#: est un tampon interne, « only contains text copied in the app, and not text
#: copied from elsewhere in the OS » (`textual` 8.2.8) --, a fortiori a travers
#: une session SSH. Un retour muet serait le mode de panne que la coque nomme
#: elle-meme : « une touche annoncee qui n'agit pas ».
PHRASE_COLLAGE = ("Le collage passe par le terminal : Ctrl+Maj+V, Cmd+V ou "
                  "clic droit.")


def legende_des_cardinaux(ascii_seul: bool = False) -> str:
    """La legende des cinq initiales, **lue** dans `projets`, jamais recopiee.

    L'operateur lit `7R · 4L · 3P · 2S · 1M` sur chaque ligne de recent ; sans
    cette legende, rien a l'ecran ne dit ce que `P` et `M` comptent -- et c'est
    le point precis ou l'ecart assume d'`EPIC11-ARB-55` doit etre visible : ces
    cardinaux comptent des **lots ayant atteint un etat**, pas des objets
    poses sur le disque. La maquette `X9` la porte en ligne d'etat.

    Le repli ASCII est fait **ici**, avant toute mesure de largeur : `…` vaut
    une colonne et `...` en vaut trois, donc mesurer avant de replier mesure
    l'autre mode.
    """
    ligne = " · ".join(f"{lettre} {mot}"
                       for lettre, mot in projets.LEGENDE_DES_CARDINAUX)
    return jetons.replier_ascii(ligne) if ascii_seul else ligne


def raccourcis_de_l_explorateur(exp) -> str:
    """La ligne de raccourcis de l'explorateur, **pour les deux ecrans**.

    `EPIC11-ARB-56` veut `Ctrl+H` dans la ligne des raccourcis ; les sept
    jetons n'y tiennent pas (mesure au docstring de
    `RACCOURCIS_CHEMIN_CACHES`). La ligne etant **contextuelle** -- « elle ne
    montre que ce qui marche sur l'ecran courant », `DESIGN.md` section 4 --,
    `Ctrl+H` s'affiche exactement dans les dossiers ou la bascule change
    quelque chose, c'est-a-dire ceux qui portent des elements caches. C'est
    aussi le moment ou l'operateur en a besoin : la ligne d'etat lui dit alors
    « 3 dossiers caches », et la ligne du dessous lui dit desormais comment les
    voir -- le grief exact du finding `C7`.

    **La condition porte sur les deux etats de la bascule**, pas sur le seul
    compte masque : `caches_masques` retombe a zero des que les caches sont
    montres, et une ligne qui perdrait `Ctrl+H` a la premiere pression
    laisserait l'operateur sans moyen annonce de revenir en arriere.

    **Elle est une fonction de MODULE et non une methode d'ecran** : `E0-2` et
    `E0-4` montrent le meme composant, donc annoncent les memes touches. Deux
    methodes divergeraient au premier ajustement, ce qui est exactement le
    defaut que le finding `F-17` sanctionne.
    """
    if exp.dans_la_saisie:
        return RACCOURCIS_SAISIE
    if exp.selection_multiple:
        # **Le mode passe avant les caches**, faute de place : les sept jetons
        # n'entrent pas (mesure au docstring de `RACCOURCIS_CHEMIN_SELECTION`),
        # et un geste qu'aucune ligne n'annonce est introuvable, la ou `Ctrl+H`
        # reste au moins decouvrable par la ligne d'etat qui compte les caches.
        return RACCOURCIS_CHEMIN_SELECTION
    montre_ou_masque = exp.montrer_caches or exp.caches_masques
    return (RACCOURCIS_CHEMIN_CACHES if montre_ou_masque
            else RACCOURCIS_CHEMIN)


class CoutureExplorateur:
    """La couture clavier de l'explorateur, **partagee par `E0-2` et `E0-4`**.

    `EPIC11-ARB-48` veut « un composant unique [...] partout ou la TUI demande
    un chemin », et cinq sites. Un composant partage dont chaque site
    reimplemente le routage clavier ne tient que la moitie de la promesse : le
    modele serait commun, le comportement non -- et un defaut se paierait
    quand meme cinq fois. La revue de vague 2 bis (`C18`) a mesure ce que coute
    l'ecart inverse : `E0-4` gardait deux champs texte pendant que la fiche
    declarait le contraire.

    L'ecran qui la reprend fournit `self.explorateur`, `self.zone`,
    `self._etat_a_dire`, et deux gestes qui, eux, lui appartiennent :

    * :meth:`_sortir_de_l_explorateur` -- ou mene `Échap` ;
    * :meth:`_valider_l_explorateur` -- ce que `⏎` fait de la cible.

    Il declare aussi sa :attr:`FAMILLE_D_EXPLORATION`, et c'est **tout** ce
    qu'un site a a faire pour partager la memoire de session de sa famille :
    :meth:`reprendre_la_memoire_de_session` fait le reste.
    """

    #: **La famille d'usage de l'explorateur de cet ecran** -- l'une de
    #: `explorateur.FAMILLES`, ou `None` pour un ecran qui ne veut rien
    #: retenir. C'est le seul reglage qu'un site ait a poser : le partage de la
    #: memoire, sa creation a la demande et son application sont tenus ici.
    #:
    #: `None` par defaut **a dessein** : un ecran qui oublie de la declarer
    #: garde le comportement d'avant (une memoire neuve et vide a lui), il ne
    #: se met pas a partager celle d'une famille au hasard. Une frontiere
    #: balaye les ecrans porteurs d'explorateur et exige qu'ils la declarent,
    #: si bien que l'oubli se paie au banc.
    FAMILLE_D_EXPLORATION: str | None = None

    def memoire_de_session(self) -> "explorateur.MemoireDeSession | None":
        """La memoire de la famille de cet ecran, ou `None` s'il n'y en a pas.

        **Elle se lit sur l'APPLICATION**, pas sur l'ecran : c'est le seul
        objet que les sept sites de l'explorateur ont en commun (voir
        `coque.CoqueTui.memoires`). L'attribut d'instance `memoires`, s'il est
        pose, prime -- c'est ce qui permet a un banc de mesurer le partage sans
        monter d'application.

        Elle rend `None` plutot que de lever quand aucune application n'est
        montee : la plupart des bancs d'ecran instancient l'ecran nu, et un
        explorateur qui refuserait de s'ouvrir hors application serait un
        defaut bien pire que l'absence de memoire.
        """
        famille = self.FAMILLE_D_EXPLORATION
        if famille is None:
            return None
        registre = getattr(self, "memoires", None)
        if registre is None:
            try:
                registre = getattr(self.app, "memoires", None)
            except Exception:      # noqa: BLE001 -- aucune application montee
                registre = None
        if registre is None:
            return None
        return registre.pour(famille)

    def reprendre_la_memoire_de_session(self, exp=None) -> bool:
        """Rebrancher `exp` (par defaut `self.explorateur`) sur la memoire de
        sa famille, et l'y replacer. Rend vrai si le dossier courant a change.

        **A appeler a l'OUVERTURE de la zone explorateur**, jamais seulement a
        la construction de l'ecran : les explorateurs du produit sont montes
        une fois et revisites -- motif complet au docstring de
        `explorateur.Explorateur.reprendre_la_memoire`.
        """
        memoire = self.memoire_de_session()
        if memoire is None:
            return False
        return (exp if exp is not None else self.explorateur
                ).reprendre_la_memoire(memoire)

    def _traiter_l_explorateur(self, touche: str,
                               caractere: str | None) -> bool:
        """Router une touche vers l'explorateur.

        L'ecran **ne decide rien** ici : il traduit un nom de touche en geste,
        et c'est l'explorateur qui sait ce que le geste veut dire. C'est ce qui
        fait que les cinq sites se comportent pareil, sans qu'aucun ne le
        reimplemente.
        """
        exp = self.explorateur
        if touche == "escape":
            # **`Echap` ne remonte JAMAIS d'un dossier** (`EPIC11-ARB-2`) : il
            # sort de l'explorateur, et `←` est la pour remonter. Router cette
            # touche vers `remonter()` donnerait a une meme frappe deux sens
            # selon la profondeur -- et ferait sauter DEUX etats a la fois a
            # qui la presse pour sortir.
            return self._sortir_de_l_explorateur()
        if touche == "tab":
            return exp.basculer_la_saisie()
        if touche == "enter":
            self._valider_l_explorateur()
            return True
        if exp.dans_la_saisie:
            if touche == "left":
                return exp.deplacer_le_caret(-1)
            if touche == "right":
                return exp.deplacer_le_caret(1)
            if touche == "backspace":
                return exp.effacer()
            if touche in ("ctrl+v", "ctrl+V"):
                # **La touche ne colle pas : elle dit quoi presser.** Si elle
                # arrive jusqu'ici, c'est que le terminal ne l'a pas prise pour
                # un collage -- donc qu'il n'y a aucun texte a coller avec
                # elle. Le collage reel arrive par `on_paste`.
                self._etat_a_dire = PHRASE_COLLAGE
                return True
            if caractere and caractere.isprintable():
                return exp.frapper(caractere)
            return False
        if touche in ("up", "down"):
            return exp.deplacer(-1 if touche == "up" else 1)
        if touche == "right":
            return exp.entrer()
        if touche == "left":
            return exp.remonter()
        if touche in ("ctrl+h", "ctrl+H"):
            return exp.basculer_les_caches()
        if caractere == " " and exp.selection_multiple:
            # **La SEULE exception a l'attrape-tout ci-dessous**, et elle est
            # bornee au mode selection (`EPIC11-ARB-103`). `Espace` est un
            # caractere imprimable -- `" ".isprintable()` vaut `True` --, il
            # partait donc au saut alphabetique comme tous les autres. Ce que
            # l'arbitrage retire n'est pas un geste utile : aucun nom de dossier
            # ne commence par un espace, donc le saut y etait deja inoperant.
            #
            # En mode simple, la touche retombe sur l'attrape-tout et saute
            # comme avant : c'est un test qui borne l'exception, pas cette
            # phrase.
            motif = exp.basculer_la_coche()
            if motif:
                self._etat_a_dire = motif
            return True
        if caractere and caractere.isprintable():
            # **Aucune lettre n'est un raccourci d'action** (`EPIC11-ARB-49`) :
            # elles sont toutes prises par le saut, qui est ce qui rend une
            # liste de deux cents dossiers praticable.
            #
            # **La frappe est consommee meme quand aucune entree ne commence
            # par elle**, et c'est la correction d'une perte de travail :
            # `sauter` rend faux sur un dossier sans correspondance,
            # l'evenement remontait alors jusqu'au binding applicatif `q`, et
            # **l'application se fermait**. La meme touche quittait donc ou
            # sautait selon le contenu du dossier -- et `RACCOURCIS_CHEMIN`
            # n'annonce aucune sortie.
            exp.sauter(caractere)
            return True
        return False

    # -- le collage ----------------------------------------------------------

    def coller(self, texte: str) -> bool:
        """Poser un texte colle dans la barre d'adresse. Rend vrai s'il y va.

        Le point d'entree unique du collage, quelle qu'en soit la source : il
        n'existe **qu'un** chemin reel, l'evenement `Paste`, et cette methode
        est ce qu'il atteint. Elle ne colle que dans la saisie -- la liste n'a
        pas de point d'insertion, et y deverser un chemin absolu a la suite du
        dossier courant produirait une adresse composee de deux chemins.
        """
        if self.zone != ZONE_CHEMIN:
            return False
        return self.explorateur.coller(texte)

    def on_paste(self, evenement) -> None:
        """L'evenement de collage du terminal -- **le chemin nominal**.

        `textual` active le *bracketed paste* au demarrage de l'application
        (`drivers/linux_driver.py`), et l'emulateur lui livre alors le texte
        colle dans un evenement `Paste`, sans qu'aucune touche soit vue par
        l'application. C'est vrai du `Ctrl+Maj+V` de GNOME Terminal comme du
        `Cmd+V` de macOS ou du clic droit de Windows Terminal : **le geste
        differe, l'evenement est le meme**. Sans ce gestionnaire, coller une
        adresse dans la barre etait impossible par tous les chemins a la fois.
        """
        if self.coller(getattr(evenement, "text", "")):
            evenement.stop()
            self.rafraichir()


class EcranProjet(CoutureExplorateur, Palier):
    """`E0-1`, `E0-2`, `E0-3` -- la liste, le champ, et la bifurcation.

    `ouvrir` est injecte : l'ecran ne sait pas ce que « descendre dans un
    projet » veut dire, et c'est l'application qui le lui dit. Sans cette
    couture, l'ecran devrait connaitre le palier 1, ce qui ferait dependre le
    palier 0 de la story 11.3.
    """

    titre = "Projet"
    raccourcis = RACCOURCIS_RECENTS

    #: Famille « projets » : on cherche ici un DOSSIER DE PROJET, pas de la
    #: matiere. Cet ecran vit au palier 0, avant qu'un projet soit ouvert -- sa
    #: memoire ne peut donc pas etre rangee par projet.
    FAMILLE_D_EXPLORATION = explorateur.FAMILLE_PROJETS

    def __init__(self, recents: projets.Recents | None = None,
                 ouvrir: Callable[[object], None] | None = None,
                 creer: Callable[[object], None] | None = None) -> None:
        super().__init__()
        self.recents = recents if recents is not None else projets.Recents()
        self._ouvrir = ouvrir
        self._creer = creer
        self.zone = ZONE_RECENTS
        self.curseur = 0
        self.saisie = ""
        # `EPIC11-ARB-48` : l'explorateur remplace le champ-chemin. Il est monte
        # ICI et pas au premier `Tab` -- il lit `Path.cwd()`, et le lire plus
        # tard ferait dependre le dossier de depart du moment ou l'on appuie.
        # `montrer_fichiers=False` est PASSE, alors que c'est le defaut : les
        # deux sites de la story le disent a la construction, et c'est ce qui
        # rend le reglage lisible -- ici on choisit un dossier, pas un fichier.
        self.explorateur = explorateur.Explorateur(
            montrer_fichiers=False, porte_un_projet=_porte_un_projet)
        self.diagnostic: projets.Diagnostic | None = None
        self.choix: ChoixExclusif | None = None
        self.entrees: list[projets.EntreeRecente] = []
        self._etat_a_dire = ""

    # -- lecture ------------------------------------------------------------

    def charger(self) -> None:
        """Relire les recents. **Le curseur part sur le champ s'il n'y en a
        aucun** : « la liste est absente, le curseur est d'emblee sur le champ
        de chemin » (`E0-1`, premier lancement)."""
        self.entrees = self.recents.lire()
        if not self.entrees:
            self.zone = ZONE_CHEMIN
            # La liste est absente : l'explorateur est ce que l'operateur voit
            # d'emblee, il doit donc partir du dernier dossier valide de la
            # famille comme s'il y etait entre par `Tab`.
            self.reprendre_la_memoire_de_session()
        self.curseur = min(self.curseur, max(len(self.entrees) - 1, 0))
        self._appliquer_la_zone()

    def _appliquer_la_zone(self) -> None:
        """Poser la ligne de raccourcis de la zone courante.

        **`raccourcis` reste un ATTRIBUT, pas une propriete**, et ce n'est pas
        un detail de style : la garde d'epic de `test_repli_ascii.py` balaye
        toutes les sous-classes de `Palier` et lit `classe.raccourcis` **au
        niveau de la classe**. Une propriete y rend l'objet `property` et fait
        echapper l'ecran a la mesure -- ce qui reviendrait a affaiblir une garde
        commune pour faire tenir un ecran. Les trois lignes sont donc des
        constantes de module, balayees une par une par cette meme garde.
        """
        self.raccourcis = {
            ZONE_REFUS: RACCOURCIS_REFUS,
            ZONE_CHEMIN: raccourcis_de_l_explorateur(self.explorateur),
        }.get(self.zone, RACCOURCIS_RECENTS)

    def ligne_de_recent(self, rang: int, largeur: int) -> str:
        """Une ligne de la liste : curseur, nom, et son contenu chiffre a droite.

        Un recent **disparu du disque** porte son glyphe `✕` et sa couleur --
        les deux, jamais la couleur seule (`DESIGN.md` section 5, regle 1).
        """
        table = self.app.glyphes
        entree = self.entrees[rang]
        marque = table["curseur"] if (rang == self.curseur
                                      and self.zone == ZONE_RECENTS) else " "
        diag = projets.diagnostiquer(entree.chemin, depuis_les_recents=True)
        compteurs = projets.compter(entree.chemin)

        def chiffre_nu(valeur) -> str:
            """Le cardinal seul. `·` quand il n'a pas pu etre lu, JAMAIS `0`."""
            return table["neutre"] if valeur is None else str(valeur)

        # `EPIC11-ARB-55` : CINQ cardinaux, en initiales. Ils se lisent dans
        # `projets.LEGENDE_DES_CARDINAUX` plutot que d'etre recopies ici : deux
        # ecritures divergeraient au premier ajustement, et la legende de la
        # ligne d'etat lit la meme source.
        droite = " · ".join(
            f"{chiffre_nu(valeur)}{lettre}"
            for (lettre, _), valeur in zip(projets.LEGENDE_DES_CARDINAUX,
                                           compteurs.tous))
        if diag.etat == projets.DISPARU:
            droite = jetons.marque("absent", "introuvable",
                                   self.app.ascii_seul)
        entete = f"{marque} "
        # **Ce qui se partage la ligne**, une fois l'entete pose. `max(2, ...)`
        # seul n'avait aucune borne HAUTE : des 51 colonnes de nom -- un nom de
        # rush ordinaire, ou 26 ideogrammes, chacun valant deux colonnes -- la
        # ligne faisait 77 colonnes pour 76, et `jetons.ajuster` la rattrapait
        # en coupant PAR LA FIN. Le premier cardinal perdu etait donc le `M`,
        # le plus tardif de la chaine de production, c'est-a-dire precisement
        # la mesure qu'`EPIC11-ARB-55` venait d'ajouter. On borne le NOM, pas
        # les compteurs (finding `E11`).
        place = largeur - jetons.colonnes(entete)
        # Les cardinaux passent en premier sur le budget -- ils sont la mesure
        # --, mais bornes eux aussi : sans cela un nom pathologique ne laisserait
        # aucune place et le creux minimal ferait deborder la ligne malgre tout.
        droite = jetons.abreger_nom(
            droite, max(place - jetons.CREUX_MINIMAL, 0), self.app.ascii_seul)
        # Le nom s'abrege AU MILIEU : `..._camera_A` et `..._camera_B` coupes
        # par la fin rendraient la meme ligne.
        nom = jetons.abreger_nom(
            entree.chemin.name,
            place - jetons.colonnes(droite) - jetons.CREUX_MINIMAL,
            self.app.ascii_seul)
        creux = place - jetons.colonnes(nom) - jetons.colonnes(droite)
        return f"{entete}{nom}{' ' * max(jetons.CREUX_MINIMAL, creux)}{droite}"

    def lignes(self) -> list[str]:
        """La zone centrale, dans l'ordre des maquettes."""
        largeur = jetons.largeur_utile(self.app.size.width)
        table = self.app.glyphes
        corps = [TITRE_OUVRIR, ""]
        if self.entrees:
            corps += [self.ligne_de_recent(rang, largeur)
                      for rang in range(len(self.entrees))]
        else:
            corps.append(PHRASE_AUCUN_RECENT)
        corps += ["", "-" * largeur, ""]

        if self.zone == ZONE_RECENTS:
            corps += [f"  {PHRASE_AUTRE_DOSSIER}", "", f"  {PHRASE_SUPPR}"]
            return corps

        if self.zone == ZONE_CHEMIN:
            # `EPIC11-ARB-48` : l'explorateur rend sa propre zone centrale, en
            # entier. L'ecran ne recompose rien -- c'est ce qui garantit que les
            # cinq sites qui le consommeront montrent la MEME chose.
            return self.explorateur.lignes(
                self.app.size.width, titre=TITRE_OUVRIR,
                libelle=LIBELLE_CHEMIN, ascii_seul=self.app.ascii_seul)
        if self.zone == ZONE_REFUS and self.diagnostic is not None:
            # **Le glyphe suit le diagnostic, pas la zone.** La bifurcation est
            # la meme pour un refus et pour une intention de creation
            # (`EPIC11-ARB-40`) ; ce qui les separe est justement ce `✕`. Le
            # poser des qu'on entre en `ZONE_REFUS` mettrait un dossier vide --
            # « un point de depart » -- au meme rang qu'un `project.json`
            # casse. Trouve par les deux tests symetriques sur `porte_la_croix`.
            if self.diagnostic.porte_la_croix:
                corps.append(f"{' ' * (len(LIBELLE_CHEMIN) + 5)}{table['absent']}")
            corps += ["", f"  {self.diagnostic.phrase}"]
            if self.diagnostic.motif:
                # **Le motif du coeur se replie, il ne s'abrege pas.** Il fait
                # jusqu'a 101 colonnes pour une zone de 76, et l'abreger en
                # coupait la partie actionnable -- « quelles versions sont
                # acceptees ». Un motif tronque n'est plus le motif du coeur.
                corps += [f"  {ligne}" for ligne in jetons.envelopper(
                    self.diagnostic.motif, largeur - 2, self.app.ascii_seul)]
            corps.append("")
            corps += self.choix.rendu(ascii_seul=self.app.ascii_seul)
        return corps

    def chemin_affiche(self) -> str:
        """Le chemin **absolu resolu**, affiche avant validation (`E0-2`).

        Montrer la saisie et valider autre chose serait la meme famille de
        mensonge qu'un apercu de creation faux.
        """
        if not self.saisie:
            return ""
        return str(projets.resoudre(self.saisie))

    # -- rendu ---------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self.charger()
        self._corps = Static("", id="corps-projet")
        return [Vertical(self._corps, id="centre-projet")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur = jetons.largeur_utile(self.app.size.width)
        ascii_seul = self.app.ascii_seul
        # **Le rang du curseur est passe EXPLICITEMENT quand l'explorateur est
        # a l'ecran.** L'auto-detection de `peindre` teste `startswith` sur le
        # glyphe de curseur ; les lignes de l'explorateur sont indentees, donc
        # elle ne les trouverait pas -- et ne colorerait rien, en silence.
        rang = (self.explorateur.rang_du_curseur()
                if self.zone == ZONE_CHEMIN else None)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, largeur, ascii_seul)
             for ligne in self.lignes()],
            ascii_seul=ascii_seul, sans_couleur=self.app.sans_couleur,
            ligne_du_curseur=rang))
        self.poser_etat(self.etat())
        super().rafraichir()

    def etat(self) -> str:
        """La ligne d'etat. **Vide quand il n'y a rien a dire.**"""
        if self._etat_a_dire:
            return self._etat_a_dire
        if self.zone == ZONE_REFUS and self.diagnostic is not None:
            # Meme regle qu'au corps : le prefixe `✕` de la ligne d'etat est
            # celui d'un REFUS (`DESIGN.md` section 3). Une intention de
            # creation n'en porte pas -- elle n'est pas une erreur.
            if not self.diagnostic.porte_la_croix:
                return self.diagnostic.phrase
            return jetons.marque("absent", self.diagnostic.phrase,
                                 self.app.ascii_seul)
        if self.zone == ZONE_CHEMIN:
            return self.explorateur.etat(
                jetons.largeur_utile(self.app.size.width),
                self.app.ascii_seul)
        if self.entrees:
            # AC 7.5 / maquette `X9` : la legende des cinq cardinaux se lit
            # **sous** la liste qui les affiche. Elle n'apparait qu'avec la
            # liste : expliquer des initiales que personne ne voit serait le
            # bavardage qu'`EPIC11-ARB-56` interdit a cette ligne.
            return legende_des_cardinaux(self.app.ascii_seul)
        return ""

    def reprendre(self) -> None:
        """Revenir au palier 0 **relit la liste** avant de la redessiner.

        `ouvrir()` reordonne les recents en notant la date d'ouverture ; sans
        cette relecture, la liste peinte gardait l'ancien ordre pendant que le
        modele avait le nouveau. Le curseur designait alors une ligne et la
        validation en ouvrait une autre -- et `Suppr` retirait la mauvaise.
        """
        self.charger()
        self.curseur = min(self.curseur, max(len(self.entrees) - 1, 0))
        self._appliquer_la_zone()
        self.rafraichir()

    def on_mount(self) -> None:
        self.rafraichir()

    # -- navigation ----------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Applique une touche. Rend vrai si l'ecran l'a consommee.

        Separee du gestionnaire d'evenement pour etre mesurable **sans
        clavier** : le banc n'a pas de pilote de terminal, et un test de cette
        famille doit pouvoir injecter le nom de touche tel que le parseur le
        produit -- `alt+q` aussi bien que `q`.
        """
        self._etat_a_dire = ""
        if self.zone == ZONE_REFUS:
            consommee = self._traiter_refus(touche)
            self._appliquer_la_zone()
            return consommee
        if self.zone == ZONE_CHEMIN:
            consommee = self._traiter_l_explorateur(touche, caractere)
        else:
            consommee = self._traiter_recents(touche)
        self._appliquer_la_zone()
        return consommee

    def _traiter_recents(self, touche: str) -> bool:
        if touche in ("up", "down") and self.entrees:
            pas = -1 if touche == "up" else 1
            self.curseur = min(max(self.curseur + pas, 0), len(self.entrees) - 1)
            return True
        if touche == "tab":
            self.zone = ZONE_CHEMIN
            # **A l'OUVERTURE de la zone, pas a la construction de l'ecran**
            # (2026-09-06) : ce palier est monte une fois pour toute la
            # session, et son explorateur avec lui. Sans cette reprise, la
            # memoire de session ne serait lue qu'au tout premier montage --
            # c'est-a-dire jamais utilement.
            self.reprendre_la_memoire_de_session()
            return True
        if touche == "delete" and self.entrees:
            # `EPIC11-ARB-39` : **aucune confirmation**, et le dossier n'est pas
            # touche. Le geste se defait en rouvrant le projet par son chemin.
            retire = self.entrees[self.curseur].chemin
            self.recents.retirer(retire)
            self.charger()
            self._etat_a_dire = (f"{retire.name} retire de la liste -- son "
                                 "dossier n'est pas touche.")
            return True
        if touche == "enter" and self.entrees:
            self._ouvrir_le_recent()
            return True
        return False

    def _ouvrir_le_recent(self) -> None:
        """`⏎` sur un recent. **Un recent disparu ne s'ouvre pas en silence.**"""
        entree = self.entrees[self.curseur]
        diag = projets.diagnostiquer(entree.chemin, depuis_les_recents=True)
        if diag.est_un_refus:
            self.saisie = str(entree.chemin)
            self._entrer_en_refus(diag)
            return
        self.ouvrir(entree.chemin)

    def _sortir_de_l_explorateur(self) -> bool:
        """`Échap` depuis l'explorateur : revenir a la liste des recents.

        **Il ne remonte JAMAIS d'un dossier** (`EPIC11-ARB-2`) : `←` est la
        pour ca. Et il ne remonte pas non plus d'un palier -- c'est une
        navigation interne a l'ecran, les trois etats d'`E0-1`/`E0-2`/`E0-3`
        etant un seul `Screen` (docstring du module).

        Sans recent a montrer, la touche n'est **pas** consommee : la liste est
        absente, il n'y a rien ou revenir, et la laisser filer rend a la coque
        son « remonte d'un palier ». La consommer poserait une touche annoncee
        qui n'agit pas.
        """
        if self.entrees:
            self.zone = ZONE_RECENTS
            return True
        return False

    def _valider_l_explorateur(self) -> None:
        """`⏎` : ouvrir ce que l'explorateur designe, ou bifurquer.

        Une frappe, quelle que soit la position dans la liste
        (`EPIC11-ARB-49`) -- c'est ce qui remplace les vingt-sept frappes qu'il
        fallait pour atteindre un bouton.
        """
        cible = self.explorateur.valider()
        if cible is None:
            self._etat_a_dire = PHRASE_RIEN_A_VALIDER
            return
        self.saisie = str(cible)
        diag = projets.diagnostiquer(cible)
        if diag.etat == projets.PROJET_LISIBLE:
            self.ouvrir(cible)
            return
        self._entrer_en_refus(diag)

    def _entrer_en_refus(self, diagnostic: projets.Diagnostic) -> None:
        """Passer en `E0-3`. **Y compris quand ce n'est pas un refus.**

        Un dossier absent ou vide n'est pas un refus (`EPIC11-ARB-40`), mais il
        mene a la **meme bifurcation** : « creer ici » y est le geste nominal.
        Ce qui change est ce que l'ecran montre -- le glyphe `✕` n'est pose que
        si `diagnostic.porte_la_croix`, et la ligne d'etat suit.
        """
        self.diagnostic = diagnostic
        self.choix = issues_du_refus()
        self.zone = ZONE_REFUS

    def _traiter_refus(self, touche: str) -> bool:
        if touche in ("up", "down"):
            self.choix.deplacer(-1 if touche == "up" else 1)
            return True
        if touche == "escape":
            self.zone = ZONE_RECENTS if self.entrees else ZONE_CHEMIN
            self.diagnostic, self.choix = None, None
            return True
        if touche == "enter":
            # `EPIC11-ARB-45` : la validation retient l'issue sous le curseur
            # et la suit, en un seul geste. Elle ne peut plus etre muette --
            # c'est ce qu'Egan avait lu comme un blocage.
            issue = self.choix.valider()
            if issue is None:
                return True
            self._suivre(issue)
            return True
        return False

    def _suivre(self, issue: Issue) -> None:
        if issue.cle == ISSUE_RECENTS:
            self.zone = ZONE_RECENTS if self.entrees else ZONE_CHEMIN
            self.diagnostic, self.choix = None, None
            return
        if issue.cle == ISSUE_CORRIGER:
            self.zone = ZONE_CHEMIN
            self.diagnostic, self.choix = None, None
            return
        self.creer(projets.resoudre(self.saisie) if self.saisie else None)

    # -- couture avec l'application -----------------------------------------

    def ouvrir(self, dossier) -> None:
        """Noter l'ouverture, puis descendre. **Dans cet ordre.**

        La date d'ouverture est mise a jour avant la descente : si l'appelant
        remonte plus tard, il retrouve la liste a jour. L'inverse laisserait la
        liste mentir jusqu'au prochain passage.
        """
        self.recents.noter_ouverture(dossier)
        self.charger()
        if self._ouvrir is not None:
            self._ouvrir(dossier)

    def creer(self, cible) -> None:
        if self._creer is not None:
            self._creer(cible)


class EcranCreation(CoutureExplorateur, Palier):
    """`E0-4` -- dossier parent, nom, et l'apercu de ce qui sera cree.

    **L'apercu est derive du coeur.** L'arborescence annoncee vient de
    `project_layout.BASE_SUBDIRS`, jamais d'une liste ecrite ici : la maquette
    du 2026-08-27 en annonce cinq dont deux que le coeur ne cree pas -- le
    dossier des frames extraites et `outputs/` -- et en omet une qu'il cree
    (`logs/`). Mesure faite a l'ecriture de la story. Un apercu qui ment sur
    ce qui va naitre est le defaut que `dossier_cible` existe deja pour
    empecher, cote chemin.

    **Et c'est cette derivation qui a evite a l'ecran de mentir a la story
    11.14** : le dossier des frames extraites a change de nom
    (`EPIC11-ARB-220`) sans qu'une ligne bouge ici, parce qu'aucun nom de
    dossier n'est ecrit dans ce module. Un apercu recopie a la main aurait
    annonce, apres le renommage, un dossier qui n'existe plus.

    **Le champ « dossier parent » est l'explorateur** (`EPIC11-ARB-48`, second
    des cinq sites, finding `C18` de la revue de vague 2 bis). Il ne s'agit pas
    d'un explorateur *de plus* : c'est la classe
    :class:`~mixed_media_utility.tui.explorateur.Explorateur`, montee comme sur
    `E0-2`, peinte par le meme rendu, pilotee par la meme couture clavier
    (:class:`CoutureExplorateur`) et annoncee par les memes lignes de
    raccourcis. Un site qui recopierait l'un de ces quatre morceaux paierait
    deux fois chaque defaut, ce que l'arbitrage existe pour empecher.

    **Deux etats, donc, et non deux champs texte.**

    * :data:`ZONE_FORMULAIRE` -- les deux valeurs et l'apercu. Le seul champ
      qui s'y tape est le **nom** : ce n'est pas un chemin a parcourir, et
      c'est la raison pour laquelle il reste une saisie ;
    * :data:`ZONE_CHEMIN` -- l'explorateur occupe toute la zone centrale,
      exactement comme sur `E0-2`.

    **Ce que `Tab` y fait, et pourquoi c'est le meme geste qu'ailleurs.**
    Depuis le formulaire, `Tab` entre dans l'explorateur -- le geste exact de
    `Tab` depuis la liste des recents, d'ou le meme libelle
    (`Tab explorateur`). Dans l'explorateur, il entre dans la barre d'adresse
    et en sort, « rien d'autre » (`EPIC11-ARB-51`). On revient au formulaire
    par `Échap` (sortir) ou par `⏎` (valider), c'est-a-dire par les deux
    memes touches que sur `E0-2` -- et non par un troisieme role de `Tab`, qui
    reintroduirait la contradiction qu'`EPIC11-ARB-51` a tranchee.
    """

    titre = "Création"
    raccourcis = RACCOURCIS_CREATION

    #: Meme famille que `EcranProjet` : on y designe le dossier PARENT d'un
    #: projet, pas de la matiere. Les deux ecrans du palier 0 se partagent donc
    #: le meme souvenir, ce qui est le comportement voulu -- on cree un projet
    #: la ou on vient d'en chercher.
    FAMILLE_D_EXPLORATION = explorateur.FAMILLE_PROJETS

    #: Un passage : un formulaire valide ne reste pas sur le chemin du retour.
    TRANSITOIRE = True

    def __init__(self, dossier_parent: str = "", nom: str = "",
                 apres_creation: Callable[[object], None] | None = None) -> None:
        super().__init__()
        self.dossier_parent = dossier_parent
        self.nom = nom
        self.zone = ZONE_FORMULAIRE
        # **L'explorateur s'ouvre la ou le champ pointe deja**, quand ce chemin
        # existe. Le monter systematiquement sur `Path.cwd()` obligerait a
        # retraverser l'arborescence pour corriger une valeur deja bonne --
        # exactement le grief d'`EPIC11-ARB-54` sur les explorateurs
        # successifs, en plus petit.
        depart = None
        if dossier_parent:
            candidat = projets.resoudre(dossier_parent)
            if candidat.is_dir():
                depart = candidat
        self.explorateur = explorateur.Explorateur(
            depart, montrer_fichiers=False, porte_un_projet=_porte_un_projet)
        #: **Un depart IMPOSE prime sur la memoire de session**, et c'est le
        #: sens du commentaire ci-dessus : le champ pointe deja quelque part,
        #: le deplacer d'office obligerait a revenir a la main. La memoire ne
        #: sert donc ici que lorsque rien n'est impose -- l'ecart entre les
        #: deux se mesure, un banc joue les deux cas.
        self._depart_impose = depart is not None
        self._apres = apres_creation
        self._refus: str | None = None
        self._etat_a_dire = ""
        self._appliquer_la_zone()

    def _appliquer_la_zone(self) -> None:
        """Poser la ligne de raccourcis de l'etat courant.

        **`raccourcis` reste un ATTRIBUT, pas une propriete** : la garde d'epic
        de `test_repli_ascii.py` balaye les sous-classes de `Palier` et lit
        `classe.raccourcis` au niveau de la CLASSE. Meme motif que sur
        `EcranProjet`, et meme consequence -- les lignes sont des constantes de
        module, balayees une par une.
        """
        self.raccourcis = (raccourcis_de_l_explorateur(self.explorateur)
                           if self.zone == ZONE_CHEMIN else RACCOURCIS_CREATION)

    # -- apercu --------------------------------------------------------------

    @property
    def cible(self):
        """Le dossier qui naitra, calcule par **la meme fonction** que la
        creation (`dossier_cible`). Une seconde formule ferait mentir l'apercu.

        Rend `None` quand le nom n'en est pas un -- un chemin, `..`, ou vide :
        « aperçu non calcule », comme `EXPERIENCE.md` le demande.
        """
        if not self.dossier_parent or not self.nom:
            return None
        try:
            return dossier_cible(projets.resoudre(self.dossier_parent), self.nom)
        except NamingError:
            return None

    @property
    def parent_manquant(self) -> bool:
        if not self.dossier_parent:
            return False
        return not projets.resoudre(self.dossier_parent).exists()

    def lignes(self) -> list[str]:
        if self.zone == ZONE_CHEMIN:
            # `EPIC11-ARB-48` : l'explorateur rend sa propre zone centrale, en
            # entier -- **le meme appel que sur `E0-2`**, au titre et au
            # libelle pres. L'ecran ne recompose rien : c'est ce qui garantit
            # que les deux sites cables par cette story montrent la MEME chose,
            # et que les trois qui viendront la montreront aussi.
            return self.explorateur.lignes(
                self.app.size.width, titre=TITRE_CREER,
                libelle=LIBELLE_PARENT, ascii_seul=self.app.ascii_seul)
        largeur = jetons.largeur_utile(self.app.size.width)
        table = self.app.glyphes
        corps = [TITRE_CREER, ""]
        # **L'invite `>` est sur le NOM, et sur lui seul.** Le dossier parent
        # n'est plus une saisie : il se choisit dans l'explorateur, et poser un
        # glyphe de focus sur une valeur qu'on ne tape pas dirait le contraire
        # de ce que `Tab` fait. La maquette `E0-4` porte encore l'invite sur le
        # parent : elle date du champ-chemin qu'`EPIC11-ARB-48` a retire.
        corps.append(f"  {LIBELLE_PARENT:<18}  {self.dossier_parent}")
        corps.append(f"  {'':<18}  {AIDE_PARENT}")
        corps.append(f"  {LIBELLE_NOM:<18}{table['invite']} {self.nom}")
        corps += ["", f"-- Ce qui sera cree {'-' * max(0, largeur - 21)}", ""]

        cible = self.cible
        if cible is None:
            corps.append("  Renseignez les deux champs pour voir le chemin.")
            return corps
        corps.append(f"  {'Dossier du projet':<18}"
                     f"{jetons.abreger_chemin(str(cible), largeur - 22, self.app.ascii_seul)}")
        # **Derive de `BASE_SUBDIRS`**, jamais recopie : deux listes
        # divergeraient au premier dossier ajoute au coeur.
        corps.append(f"  {'Arborescence':<18}"
                     + "  ".join(f"{nom}/" for nom in BASE_SUBDIRS))
        corps.append(f"  {'Fichier de projet':<18}{NOM_FICHIER_PROJET}")
        if self.parent_manquant:
            corps += ["", "  " + jetons.marque(
                "substitute", "ce dossier n'existe pas -- il sera cree aussi",
                self.app.ascii_seul)]
        return corps

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="corps-creation")
        return [Vertical(self._corps, id="centre-creation")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur = jetons.largeur_utile(self.app.size.width)
        # **Le rang du curseur est passe EXPLICITEMENT quand l'explorateur est
        # a l'ecran** -- meme geste que sur `E0-2`, et pour le meme motif :
        # l'auto-detection de `peindre` teste `startswith` sur le glyphe de
        # curseur, les lignes de l'explorateur sont indentees, donc elle ne les
        # trouverait pas et ne colorerait rien, **en silence**. C'etait l'un
        # des trois defauts du developpement de cette story.
        rang = (self.explorateur.rang_du_curseur()
                if self.zone == ZONE_CHEMIN else None)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, largeur, self.app.ascii_seul)
             for ligne in self.lignes()],
            ascii_seul=self.app.ascii_seul, sans_couleur=self.app.sans_couleur,
            ligne_du_curseur=rang))
        self.poser_etat(self.etat())
        super().rafraichir()

    def etat(self) -> str:
        if self._refus:
            return jetons.marque("absent", self._refus, self.app.ascii_seul)
        if self._etat_a_dire:
            return self._etat_a_dire
        if self.zone == ZONE_CHEMIN:
            # La ligne d'etat de l'explorateur est la SIENNE : le compte des
            # sous-dossiers, le chemin complet, les caches. La recomposer ici
            # ferait deux mesures d'une seule.
            return self.explorateur.etat(
                jetons.largeur_utile(self.app.size.width), self.app.ascii_seul)
        if self.parent_manquant:
            return "Le dossier n'existe pas encore : il sera cree avec son arborescence."
        return ""

    def on_mount(self) -> None:
        self.rafraichir()

    # -- navigation ----------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Applique une touche. Rend vrai si l'ecran l'a consommee.

        Separee du gestionnaire d'evenement pour etre mesurable **sans
        clavier**, comme sur `EcranProjet` : le banc n'a pas de pilote de
        terminal.
        """
        self._refus = None
        self._etat_a_dire = ""
        if self.zone == ZONE_CHEMIN:
            consommee = self._traiter_l_explorateur(touche, caractere)
        else:
            consommee = self._traiter_le_formulaire(touche, caractere)
        self._appliquer_la_zone()
        return consommee

    def _traiter_le_formulaire(self, touche: str,
                               caractere: str | None) -> bool:
        """Le formulaire : un seul champ se tape, et c'est le **nom**.

        Le dossier parent est un chemin ; depuis `EPIC11-ARB-48` un chemin ne
        se tape plus dans un champ, il se parcourt -- et l'explorateur porte sa
        propre barre d'adresse pour qui prefere le taper.
        """
        if touche == "tab":
            self.zone = ZONE_CHEMIN
            if not self._depart_impose:
                self.reprendre_la_memoire_de_session()
            return True
        if touche == "backspace":
            self.nom = self.nom[:-1]
            return True
        if touche == "enter":
            self.valider()
            return True
        if caractere and caractere.isprintable():
            self.nom += caractere
            return True
        return False

    def _sortir_de_l_explorateur(self) -> bool:
        """`Échap` depuis l'explorateur : revenir au formulaire.

        **Il ne remonte JAMAIS d'un dossier** (`EPIC11-ARB-2`) -- `←` est la
        pour ca --, et il ne remonte pas d'un palier non plus : la sortie de
        `E0-4` se fait depuis le formulaire, ou `Échap` n'est pas consommee et
        rend a la coque son « remonte d'un palier ». Deux etats, deux
        pressions, jamais deux sauts d'un coup.
        """
        self.zone = ZONE_FORMULAIRE
        return True

    def _valider_l_explorateur(self) -> None:
        """`⏎` : retenir le dossier sous le curseur comme dossier parent.

        Une frappe, quelle que soit la position dans la liste
        (`EPIC11-ARB-49`), et la valeur retenue est **celle que l'etiquette du
        bas annonce** -- `valider()` rend la cible que `ligne_de_validation`
        affiche, donc l'ecran ne peut pas retenir autre chose que ce qui etait
        promis.
        """
        cible = self.explorateur.valider()
        if cible is None:
            self._etat_a_dire = PHRASE_RIEN_A_VALIDER
            return
        self.dossier_parent = str(cible)
        self.zone = ZONE_FORMULAIRE

    def valider(self) -> None:
        """Creer -- **par le coeur**, et sans rien ecrire si un refus tombe.

        Les trois refus sont ceux de `depot_projets.creer_projet`, et leurs
        motifs sont rendus **verbatim**. Aucun d'eux ne laisse quoi que ce soit
        sur le disque : `creer_projet` derive l'identifiant AVANT le premier
        `mkdir`, et refuse une cible portant deja un projet avant tout ecrit.
        """
        if not self.dossier_parent or not self.nom:
            self._refus = "Renseignez le dossier parent et le nom du projet."
            return
        try:
            ligne = creer_projet(projets.resoudre(self.dossier_parent), self.nom)
        except ProjetExistantError as erreur:
            self._refus = str(erreur)
            return
        except (NamingError, OSError) as erreur:
            self._refus = str(erreur)
            return
        if self._apres is not None:
            self._apres(ligne.chemin)


__all__ = [
    "AIDE_PARENT",
    "PHRASE_COLLAGE",
    "PHRASE_RIEN_A_VALIDER",
    "CoutureExplorateur",
    "EcranCreation",
    "EcranProjet",
    "ISSUE_CORRIGER",
    "ISSUE_CREER",
    "ISSUE_RECENTS",
    "PHRASE_AUCUN_RECENT",
    "PHRASE_SUPPR",
    "TITRE_CREER",
    "TITRE_OUVRIR",
    "RACCOURCIS_CHEMIN",
    "RACCOURCIS_CHEMIN_CACHES",
    "RACCOURCIS_CHEMIN_SELECTION",
    "RACCOURCIS_CREATION",
    "RACCOURCIS_RECENTS",
    "RACCOURCIS_SAISIE",
    "RACCOURCIS_REFUS",
    "ZONE_CHEMIN",
    "ZONE_FORMULAIRE",
    "ZONE_RECENTS",
    "ZONE_REFUS",
    "issues_du_refus",
    "legende_des_cardinaux",
    "raccourcis_de_l_explorateur",
]
