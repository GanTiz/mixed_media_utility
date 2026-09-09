# -*- coding: utf-8 -*-
"""Le panneau chiffre et le choix exclusif (story 11.1, AC 1 et AC 7).

`EPIC11-ARB-4` : **l'ecran de confirmation est le point de jugement de la
TUI**. C'est la seule chose qu'Egan ait ecrite dans les quatre parcours, et
c'est pourquoi le motif vit ici, une fois, plutot que quatre fois dans les
ateliers.

Deux contrats durs, tenus par le type plutot que par la relecture :

* **tout chiffre porte son unite** -- une ligne chiffree sans unite est
  refusee a la construction, pas signalee en revue ;
* **tout majorant porte le mot `(majorant)`** -- l'operateur doit pouvoir
  distinguer d'un coup d'oeil ce qui est mesure de ce qui est estime, sans
  quoi le panneau chiffre ment sur sa propre precision.

Et un troisieme, porte par :class:`ChoixExclusif` : **aucune issue n'est
preselectionnee** (`EPIC11-ARB-7`), et **un cartouche porte au moins deux
issues actionnables** (AC 7.2) -- un cartouche sans issue est un defaut, parce
qu'un point de decision sans decision possible est un constat, et un constat va
en ligne d'etat (`EPIC11-ARB-35`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import jetons

#: Le mot qui marque une valeur estimee. Un seul, ecrit une fois : deux
#: formulations differentes d'un ecran a l'autre rendraient la distinction
#: illisible exactement la ou elle compte.
MENTION_MAJORANT = "(majorant)"

#: Ce que la ligne d'etat dit tant que le panneau est a l'ecran (AC 1.3).
#:
#: **Accentuee depuis le lot I** (finding `I6`, vu sur la capture reelle
#: `20-E2-3-confirmation.svg`) : elle etait ecrite sans accents dans une source
#: rendue en UTF-8, donc elle rendait `Rien n'a encore ete ecrit.` **dans les
#: deux regimes**. Le repli ASCII a sa table (`jetons.REPLIS_DE_TEXTE`, puis la
#: decomposition Unicode) ; une chaine desaccentuee a la source court-circuite
#: ce mecanisme et rend le repli indistinguable du nominal -- c'est-a-dire
#: exactement ce que la table existe pour eviter.
RIEN_ECRIT = "Rien n'a encore été écrit."


class PanneauMalForme(ValueError):
    """Le panneau viole un contrat que la revue ne devrait pas avoir a trouver."""


@dataclass(frozen=True)
class LigneChiffree:
    """Un libelle a gauche, un chiffre a droite, et son unite.

    ``valeur`` peut etre un texte (un timecode, un intervalle de bornes) : dans
    ce cas l'unite n'a pas lieu d'etre et vaut ``None``. Mais un **nombre**
    sans unite est refuse : c'est le defaut que l'AC 1.2 vise, et le refuser a
    la construction le rend impossible plutot qu'improbable.
    """

    libelle: str
    valeur: object
    unite: str | None = None
    majorant: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.valeur, bool) or not isinstance(self.valeur, (int, float)):
            return
        if not self.unite:
            raise PanneauMalForme(
                f"La ligne {self.libelle!r} porte le chiffre {self.valeur!r} "
                "sans unite. Tout chiffre d'un panneau porte son unite "
                "(story 11.1, AC 1.2)."
            )

    @property
    def chiffre(self) -> str:
        """La partie droite : la valeur, son unite, sa mention de majorant."""
        morceaux = [f"{self.valeur}"]
        if self.unite:
            morceaux.append(self.unite)
        if self.majorant:
            morceaux.append(MENTION_MAJORANT)
        return " ".join(morceaux)

    def rendu(self, largeur: int = jetons.LARGEUR_PLANCHER,
              ascii_seul: bool = False) -> str:
        """Libelle a gauche, chiffre a droite, un creux d'au moins deux espaces.

        L'argument est la largeur de la **fenetre** ; la largeur ecrivable s'en
        deduit par :func:`jetons.largeur_de_cartouche`, le cartouche portant son
        propre cadre en plus de celui de l'ecran. Le creux minimal de deux
        espaces vaut aussi quand tout deborde : coller le chiffre au libelle
        rendrait la ligne illisible en plus d'etre trop longue.

        **Deux defauts mesures par la revue de vague 2 bis**, et ils
        expliquent la forme de cette fonction.

        * Le creux n'avait **aucune borne haute**, et une valeur de ligne
          chiffree n'est pas toujours un nombre : `palier_projet` en pose deux
          qui portent un **nom de fichier** (`Fichier de projet`, `Fichier du
          profil`). Mesure au plancher (cartouche de 72 colonnes) :
          `2026-08-29_tournage_exterieur_nuit_camera_B_prise_02.json` rendait
          une ligne de **76 colonnes**, et de **80** avec un suffixe `_bis`.
          `jetons.ajuster` la rattrapait en coupant par la fin -- c'est-a-dire
          en mangeant le chiffre, la seule chose que le panneau existe pour
          montrer.
        * La mesure se faisait en **`len()`**. Un nom de fichier en
          ideogrammes rendait `len(ligne) == 72`, donc une ligne que le code
          croyait calee juste, pour **92 colonnes reelles** ; a 34 ideogrammes,
          106 colonnes pour 72. Le defaut ne se voit que sur de la double
          chasse, et aucune fixture n'en portait.

        `ascii_seul` **precede la mesure** : `…` vaut une colonne, `...` en
        vaut trois, et choisir les points apres avoir compte ferait deborder de
        deux colonnes une ligne calee juste.
        """
        libelle, chiffre = self.libelle, self.chiffre
        if ascii_seul:
            libelle = jetons.replier_ascii(libelle)
            chiffre = jetons.replier_ascii(chiffre)
        utile = jetons.largeur_de_cartouche(largeur)
        place = utile - jetons.CREUX_MINIMAL
        # **Le chiffre passe en premier sur le budget** : c'est la mesure, et un
        # chiffre ampute serait un panneau qui ment sur ce qu'il annonce. Mais
        # le libelle garde au moins la moitie de la place -- un chiffre sans son
        # libelle ne designe plus rien, et c'est un point de jugement.
        part_du_libelle = min(jetons.colonnes(libelle), max(place // 2, 0))
        chiffre = jetons.abreger_nom(
            chiffre, max(place - part_du_libelle, 0), ascii_seul)
        libelle = jetons.abreger_nom(
            libelle, max(place - jetons.colonnes(chiffre), 0), ascii_seul)
        creux = utile - jetons.colonnes(libelle) - jetons.colonnes(chiffre)
        return libelle + " " * max(jetons.CREUX_MINIMAL, creux) + chiffre


@dataclass(frozen=True)
class Issue:
    """Une sortie possible d'un point de decision.

    ``ecrit`` dit si retenir cette issue provoque une ecriture. Ce n'est pas
    decoratif : c'est ce qui permet de verifier qu'un panneau propose toujours
    une sortie qui **n'ecrit pas** -- sans quoi le point de jugement ne serait
    plus un jugement.
    """

    cle: str
    libelle: str
    ecrit: bool = False


@dataclass
class ChoixExclusif:
    """Des issues, dont **aucune** n'est retenue au depart.

    `EPIC11-ARB-7`. Une issue preselectionnee transforme `Entree` en accident :
    l'operateur qui valide par reflexe declenche le choix de quelqu'un d'autre.
    """

    issues: list[Issue]
    retenue: str | None = None
    curseur: int = 0

    def __post_init__(self) -> None:
        if len(self.issues) < 2:
            raise PanneauMalForme(
                "Un point de decision porte au moins deux issues actionnables "
                f"(story 11.1, AC 7.2) ; recu {len(self.issues)}."
            )
        cles = [issue.cle for issue in self.issues]
        if len(set(cles)) != len(cles):
            raise PanneauMalForme(f"Deux issues portent la meme cle : {cles}")
        if self.retenue is not None:
            raise PanneauMalForme(
                "Aucune issue n'est preselectionnee (EPIC11-ARB-7).")
        if all(issue.ecrit for issue in self.issues):
            # Le docstring de `sortie_sans_ecriture` promettait cette
            # verification depuis le premier jour et personne ne la posait : les
            # trois autres invariants etaient rendus impossibles plutot
            # qu'improbables, celui-la restait une declaration. Un point de
            # jugement dont toutes les issues ecrivent n'est plus un jugement,
            # c'est un couloir.
            raise PanneauMalForme(
                "Un point de decision offre au moins une issue qui n'ecrit "
                f"pas : {[i.cle for i in self.issues]} ecrivent toutes.")

        # **Le curseur part sur une issue qui n'ecrit pas.** C'est ce que
        # `EPIC11-ARB-7` garde apres `EPIC11-ARB-45` : la validation retient
        # desormais en un geste, donc un curseur pose au montage sur l'issue qui
        # ecrit rendrait l'ecriture atteignable en UNE frappe -- exactement
        # l'accident que `ARB-7` existait pour empecher. Le rang de l'issue
        # principale ne bouge pas pour autant : c'est le curseur qui se place,
        # pas la liste qui se reordonne.
        if self.issues[self.curseur].ecrit:
            self.curseur = next(rang for rang, issue in enumerate(self.issues)
                                if not issue.ecrit)

    # -- lecture ----------------------------------------------------------

    @property
    def action_qui_ecrit(self) -> "Issue | None":
        """La **PREMIERE** issue qui ecrit, s'il y en a une. Il peut y en avoir
        plusieurs.

        Symetrique de :attr:`sortie_sans_ecriture`, qui existait seule. C'est
        une issue que le curseur ne doit **jamais** viser au montage
        (`EPIC11-ARB-45`), et c'est donc elle qu'un test doit savoir nommer sans
        recopier une cle litterale.

        **Son docstring disait « l'issue qui ecrit », au singulier defini, et
        c'etait faux depuis qu'un ecran en porte deux** (story 11.4d, AC 5.3 :
        « elle ne reste pas en place en mentant »). `EPIC11-ARB-89` fait de la
        seconde issue ecrivante -- creer une version a cote plutot qu'ecraser --
        la forme normale de tout conflit d'ecriture du produit : un panneau a
        deux issues ecrivantes n'est plus l'exception, et un `find` qui rend la
        premiere nomme silencieusement la mauvaise des que le curseur est sur
        l'autre. C'est litteralement le mutant `M25` de la story 5.7.

        **Ce qu'elle reste bonne a faire, et c'est pour cela qu'elle survit** :
        repondre « y a-t-il une ecriture possible ici ? » (`is None` ou non), et
        nommer l'action d'un panneau qui n'en porte qu'une -- ce qui est le cas
        de la grande majorite des ecrans du produit. **Ce qu'elle ne sait pas
        faire** : designer laquelle des deux l'operateur vise. Pour cela,
        :attr:`actions_qui_ecrivent` et :attr:`issue_sous_le_curseur`.
        """
        return next((issue for issue in self.issues if issue.ecrit), None)

    @property
    def actions_qui_ecrivent(self) -> list["Issue"]:
        """**TOUTES** les issues qui ecrivent, dans l'ordre du panneau.

        La forme plurielle qu'`EPIC11-ARB-89` rend necessaire (story 11.4d,
        AC 5.1). Elle est ce qu'une frontiere interroge pour mesurer qu'un point
        de jugement offre bien **deux** issues ecrivantes -- creer la version, ou
        ecraser sciemment -- la ou :attr:`action_qui_ecrit` ne pouvait rendre
        qu'un cardinal de zero ou un.

        Une **liste** et non un iterateur : une frontiere en prend le cardinal,
        et un generateur epuise rendrait zero a la seconde lecture.
        """
        return [issue for issue in self.issues if issue.ecrit]

    @property
    def issue_sous_le_curseur(self) -> "Issue | None":
        """L'issue que le curseur designe, ou ``None`` si le panneau est vide.

        Depuis `EPIC11-ARB-45` « le curseur EST la selection » : c'est donc
        cette issue-la, et non la premiere d'une liste, que tout affichage qui
        parle de « l'action » doit nommer. La lire ici plutot que d'indexer
        `issues[curseur]` chez l'appelant garde l'indexation a un seul endroit.
        """
        if not self.issues:
            return None
        return self.issues[self.curseur]

    @property
    def sortie_sans_ecriture(self) -> Issue | None:
        """L'issue qui n'ecrit rien. Il en faut une, et le panneau le verifie."""
        for issue in self.issues:
            if not issue.ecrit:
                return issue
        return None

    def issue(self, cle: str) -> Issue:
        for candidate in self.issues:
            if candidate.cle == cle:
                return candidate
        connues = ", ".join(i.cle for i in self.issues)
        raise KeyError(f"issue inconnue : {cle!r}. Connues : {connues}")

    def rendu(self, ascii_seul: bool = False) -> list[str]:
        """Une ligne par issue. **Le curseur EST la selection** (`EPIC11-ARB-45`).

        Plus de case a cocher : Egan a lu la sequence en deux gestes comme un
        blocage -- « je n'ai pas vu de panneau chiffre, comment y acceder ? » --,
        et elle n'etait decouvrable nulle part, sauf apres une validation
        infructueuse. Le rendu ne porte donc plus que la fleche ; la couleur
        d'accentuation et le gras de la ligne courante sont poses au dessin, la
        ou la largeur a deja ete mesuree.
        """
        table = jetons.glyphes(ascii_seul)
        return [f"{table['curseur'] if rang == self.curseur else ' '} "
                f"{issue.libelle}"
                for rang, issue in enumerate(self.issues)]

    # -- ecriture ---------------------------------------------------------

    def deplacer(self, pas: int) -> None:
        """`↑↓` : deplacer le curseur **ne retient rien**.

        La distinction est le coeur de `EPIC11-ARB-7` : parcourir n'est pas
        choisir. Un curseur qui retiendrait au passage rendrait la derniere
        issue survolee equivalente a une preselection.
        """
        self.curseur = min(max(self.curseur + pas, 0), len(self.issues) - 1)

    def viser(self, cle: str) -> Issue:
        """Placer le **curseur** sur une issue nommee, sans rien retenir.

        Depuis `EPIC11-ARB-45` le curseur est la selection : viser puis valider
        est le chemin qu'un operateur parcourt avec les fleches, et c'est donc
        le chemin qu'un test doit emprunter. `retenir(cle)` ecrivait le modele
        sans bouger le curseur -- la validation, qui suit desormais le curseur,
        aurait rendu une autre issue.
        """
        for rang, issue in enumerate(self.issues):
            if issue.cle == cle:
                self.curseur = rang
                return issue
        # Un `next()` nu remontait ici en « coroutine raised StopIteration »,
        # message qui ne nomme ni la cle demandee ni celles qui existent.
        raise PanneauMalForme(
            f"Aucune issue ne porte la cle {cle!r} ; connues : "
            f"{[i.cle for i in self.issues]}.")

    def retenir(self, cle: str | None = None) -> Issue:
        """Retenir l'issue sous le curseur, ou celle qu'on nomme.

        Depuis `EPIC11-ARB-45`, aucune touche ne l'appelle seule : la validation
        retient et suit en un geste. La methode reste le point d'ecriture du
        modele -- c'est par elle que `valider()` a quelque chose a rendre --, et
        les ecrans qui nomment une issue (une reprise, une annulation) s'en
        servent toujours.
        """
        issue = self.issue(cle) if cle is not None else self.issues[self.curseur]
        self.retenue = issue.cle
        return issue

    def valider(self) -> Issue | None:
        """La validation **retient l'issue sous le curseur, puis la rend**.

        `EPIC11-ARB-45` : un seul geste. Ce que `EPIC11-ARB-7` interdisait --
        qu'une issue soit preselectionnee -- garde ici sa forme reduite et
        mesurable : **aucune issue qui ecrit n'est atteignable en une frappe
        depuis le montage d'un ecran**, parce que toute issue qui ecrit debouche
        sur un point de jugement portant « Annuler, ne rien ecrire ».

        Rend ``None`` quand il n'y a aucune issue -- un resultat, pas un echec.
        """
        if not self.issues:
            return None
        return self.retenir()


@dataclass
class Panneau:
    """Le motif chiffre de `DESIGN.md` 7.4, en modele pur.

    Ordre impose : les lignes chiffrees, une ligne vide, puis les noms
    produits. Les noms sont **en dernier** parce qu'ils sont ce que
    l'operateur edite, et qu'un bloc editable au milieu d'un tableau de
    chiffres se cherche.
    """

    titre: str
    lignes: list[LigneChiffree] = field(default_factory=list)
    noms: list[str] = field(default_factory=list)

    #: Le libelle sous lequel :meth:`rendu_nomme` designe le bloc de noms. Ce
    #: n'est pas un libelle de ligne chiffree -- les noms n'en portent pas --,
    #: mais un nom de BLOC, et il existe pour qu'un cartouche qui defile puisse
    #: dire « 3 noms » plutot que d'enumerer trois lignes anonymes
    #: (`EPIC11-ARB-245`). Un appelant qui a mieux a dire le remplace ; celui-ci
    #: est le mot que le panneau connait de lui-meme.
    LIBELLE_DES_NOMS = "noms"

    def rendu_nomme(self, largeur: int = jetons.LARGEUR_PLANCHER,
                    ascii_seul: bool = False) -> list[tuple[str, str | None]]:
        """Le rendu, **chaque ligne appariee au libelle qui l'a produite**.

        La seule composition du panneau : :meth:`rendu` en derive plutot que de
        la refaire. Deux compositions divergeraient a la premiere retouche, et
        surtout : un cartouche qui defile a besoin de savoir CE QUE chaque
        ligne dit pour pouvoir nommer celles qu'il cache. Reconstituer ce lien
        chez l'appelant, par une seconde liste appariee par position, serait le
        mutant `M33` de la story 5.6 -- une permutation y reste verte.

        Le libelle vaut ``None`` sur une respiration, qui ne nomme rien.
        """
        couples: list[tuple[str, str | None]] = [
            (ligne.rendu(largeur, ascii_seul), ligne.libelle)
            for ligne in self.lignes]
        if self.noms:
            couples.append(("", None))
            couples.extend((nom, self.LIBELLE_DES_NOMS) for nom in self.noms)
        return couples

    def rendu(self, largeur: int = jetons.LARGEUR_PLANCHER,
              ascii_seul: bool = False) -> list[str]:
        return [texte for texte, _ in self.rendu_nomme(largeur, ascii_seul)]

    @property
    def porte_un_majorant(self) -> bool:
        return any(ligne.majorant for ligne in self.lignes)
