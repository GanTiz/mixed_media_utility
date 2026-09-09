# -*- coding: utf-8 -*-
"""Le palier 1 : que faire dans ce projet (story 11.3, `E1-1`).

Le **carrefour** de la TUI. Les quatre ateliers n'ont pas d'autre porte, et
`EPIC11-ARB-13` y ramene apres chaque execution -- jamais a l'ecran projet.

**Rien n'est masque.** Une entree dont la condition n'est pas remplie reste
visible, porte sa condition, et **mene quelque part** : « un operateur doit
pouvoir voir ce qui existe avant de savoir qu'il n'y a pas acces ».
"""
from __future__ import annotations

from typing import Callable

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from . import jetons, projet_lecture
from .coque import Palier

#: Ligne de raccourcis du menu. Constante de module, comme celles du palier 0 :
#: c'est ce qui la fait balayer par la garde d'epic de `test_repli_ascii.py`.
#: **Majuscule d'affichage, touche NUE en minuscule** -- la regle des
#: majuscules de raccourci, ecrite en entier dans `coque.py`. La lettre
#: annoncee ici est en majuscule ; la touche cablee reste la minuscule.
RACCOURCIS_ATELIERS = ("⏎ entrer  ↑↓ naviguer  Échap projet  "
                       "F1 aide  Q quitter")

#: Libelle du pied. **`EPIC11-ARB-44` : jamais « Derniere ecriture ».**
#: Le `project.json` ne porte aucun signal d'horloge par construction, son
#: `mtime` est reecrit par git puisque `projects/` est versionne, et l'ordre de
#: `lots[]` est celui de premiere creation. La seule date vraie du document est
#: `confirmation.confirmed_at`, qui ne concerne que l'**extraction** : le
#: libelle dit donc ce qu'il mesure, et la difference entre les deux formules
#: est ce qui rend cette ligne honnete.
LIBELLE_PIED = "Derniere extraction confirmee"

#: Ce que le pied dit quand aucun lot ne porte de confirmation. **Jamais une
#: ligne vide** -- c'est l'exigence d'`EXPERIENCE.md` sur ce pied, et elle
#: porte sur le vide, pas sur le libelle.
PIED_VIDE = "aucune extraction confirmee dans ce projet"


class EcranAteliers(Palier):
    """`E1-1` -- cinq entrees, et le pied du projet.

    `entrer` est injecte, comme `ouvrir` l'est au palier 0 : l'ecran ne sait pas
    ce qu'un atelier est, et c'est l'application qui le lui dit. Sans cette
    couture, le palier 1 dependrait des stories d'atelier de la vague 3.
    """

    titre = "Ateliers"
    raccourcis = RACCOURCIS_ATELIERS

    def __init__(self, dossier=None,
                 entrer: Callable[[projet_lecture.Entree], None] | None = None
                 ) -> None:
        super().__init__()
        self.dossier = dossier
        self._entrer = entrer
        self.curseur = 0
        self.manifeste: dict | None = None
        self.entrees: list[projet_lecture.Entree] = []
        self._etat_a_dire = ""

    # -- lecture ------------------------------------------------------------

    def charger(self) -> None:
        """Relire le manifest. **Une seule lecture pour les trois calculs.**

        Les compteurs, les conditions et le pied se derivent tous du meme
        document : le relire trois fois donnerait trois etats potentiellement
        differents d'un projet qu'un autre processus peut ecrire pendant ce
        temps -- et l'ecran afficherait alors un bandeau qui contredit son pied.

        **Le dossier part avec le document** depuis la story 11.8 : la
        condition d'`Exports` est desormais le verdict du coeur
        (`encode.list_encodable_lots`), et ce verdict porte sur la matiere --
        un `output_frames_dir` declare **et present** -- autant que sur l'etat.
        Un manifest sans sa racine ne suffit pas a le rendre.
        """
        self.manifeste = (projet_lecture.lire_manifeste(self.dossier)
                          if self.dossier is not None else None)
        self.entrees = projet_lecture.entrees(self.manifeste,
                                              self.dossier)
        self.curseur = min(self.curseur, len(self.entrees) - 1)

    @property
    def compteurs(self) -> projet_lecture.Compteurs:
        return projet_lecture.compter(self.manifeste)

    def bandeau(self, largeur: int | None = None) -> str:
        """Le bandeau, avec les compteurs a droite.

        Ils sont poses sur l'**objet** du contexte, ce qui les fait passer par
        l'elision de `Contexte.rendu` : quand les deux cotes ne tiennent pas
        ensemble, c'est le nom du projet qui est abrege et **jamais** les
        compteurs -- « le projet est ecrit partout ailleurs, tandis que l'objet
        porte les chiffres du parcours, qui ne se relisent nulle part ».
        """
        from .coque import Contexte

        session = getattr(self.app, "contexte", Contexte())
        contexte = Contexte(session.projet, self.titre, self.compteurs.rendu())
        return contexte.rendu(self.app.size.width if largeur is None else largeur,
                              getattr(self.app, "ascii_seul", False))

    def ligne_d_entree(self, rang: int, largeur: int) -> str:
        """Une entree : curseur, nom sur une colonne fixe, puis sa phrase.

        Une entree **conditionnee** montre sa condition **a la place** de sa
        phrase, et porte le glyphe `▲` -- un avertissement, pas un refus : rien
        n'a echoue, l'atelier n'a simplement rien a lister.
        """
        table = self.app.glyphes
        entree = self.entrees[rang]
        marque = table["curseur"] if rang == self.curseur else " "
        if entree.disponible:
            droite = entree.phrase
        else:
            droite = jetons.marque("substitute", entree.condition,
                                   self.app.ascii_seul)
        return jetons.ajuster(f"{marque} {entree.nom:<12}{droite}", largeur,
                              self.app.ascii_seul)

    def lignes_du_pied(self) -> list[str]:
        """Le pied, sur deux lignes -- `EPIC11-ARB-44`.

        **Le glyphe d'etape OUVRE une colonne, il n'est pas dans la prose.**
        Le dernier separateur n'est donc pas un `·` mais un creux de DEUX
        blancs, comme `ligne_de_recent` de l'ecran projet et `_ligne` de
        l'explorateur calent leur colonne droite sur `" " * max(2, creux)`.

        Ce n'est pas une preference de mise en page : c'est la condition que
        :func:`jetons.jeton_d_etat` exige pour teindre. Ecrit
        `« ... · lot_a · ● extraction »`, le `●` n'est precede que d'UN blanc
        -- la forme d'une prose --, et la ligne perdait sa teinte **dans les
        deux modes**, sans qu'aucun test ne s'en apercoive :

            '  12/08 14:03 · lot_a · ● extraction'  -> None
            '  12/08 14:03 · lot_a  ● extraction'   -> state-complete

        Regression mesuree le 2026-08-29, effet de bord du resserrement de
        `jetons.jeton_d_etat` -- lequel ferme un vrai defaut (« Extraction »
        sortait en rouge) et n'est pas ce qu'on corrige ici. C'est la mise en
        page de cette ligne qui devait se conformer a la regle de colonne, pas
        la regle qui devait se relacher pour elle.
        """
        derniere = projet_lecture.derniere_extraction(self.manifeste)
        if not derniere.existe:
            return [PIED_VIDE]
        quand = projet_lecture.date_lisible(derniere.quand)
        etape = jetons.marque("complete", derniere.etape or "",
                              self.app.ascii_seul)
        return [LIBELLE_PIED, f"  {quand} · {derniere.lot}  {etape}"]

    def lignes(self) -> list[str]:
        largeur = jetons.largeur_utile(self.app.size.width)
        nom = getattr(getattr(self.app, "contexte", None), "projet", None)
        corps = [f"Que faire dans {nom} ?" if nom else "Que faire ici ?", ""]
        for rang, entree in enumerate(self.entrees):
            # La ligne vide separe `Projet` des quatre ateliers : « ce n'est pas
            # un atelier ». Elle est posee AVANT l'entree, pas apres la
            # quatrieme, pour qu'ajouter un cinquieme atelier un jour ne la
            # laisse pas au mauvais endroit.
            if entree.nom == projet_lecture.PROJET:
                corps.append("")
            corps.append(self.ligne_d_entree(rang, largeur))
        corps += ["", "-" * largeur, ""]
        corps += [f"  {ligne}" for ligne in self.lignes_du_pied()]
        return corps

    # -- rendu ---------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self.charger()
        self._corps = Static("", id="corps-ateliers")
        return [Vertical(self._corps, id="centre-ateliers")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur = jetons.largeur_utile(self.app.size.width)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, largeur, self.app.ascii_seul)
             for ligne in self.lignes()],
            ascii_seul=self.app.ascii_seul, sans_couleur=self.app.sans_couleur))
        self.poser_etat(self.etat())
        super().rafraichir()

    def etat(self) -> str:
        """Vide quand il n'y a rien a dire. La condition d'une entree est **sur
        sa ligne**, pas ici : la ligne d'etat ne designerait pas laquelle."""
        return self._etat_a_dire

    def reprendre(self) -> None:
        """Revenir au menu **relit le manifest** avant de le redessiner.

        Deux raisons, mesurees toutes les deux : le palier peut avoir change de
        projet entre deux visites (`V2-M2`), et la seule ecriture du palier
        Projet -- `reconstruct-project` -- ramene precisement ici, ou les
        compteurs restaient a zero.
        """
        self.charger()
        self.rafraichir()

    def on_mount(self) -> None:
        self.rafraichir()

    # -- navigation ----------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier : voir le meme choix au palier 0."""
        self._etat_a_dire = ""
        if touche in ("up", "down") and self.entrees:
            pas = -1 if touche == "up" else 1
            self.curseur = min(max(self.curseur + pas, 0), len(self.entrees) - 1)
            return True
        if touche == "enter" and self.entrees:
            self.entrer(self.entrees[self.curseur])
            return True
        return False

    def entrer(self, entree: projet_lecture.Entree) -> None:
        """`⏎` sur une entree. **Une entree conditionnee mene quand meme
        quelque part** (consigne d'Egan, 2026-08-28) : elle nomme ce qui manque
        et ou l'obtenir, en ligne d'etat, plutot que de rester muette. Une
        touche qui ne fait rien et ne dit rien est indistinguable d'un clavier
        casse.

        **Ce que le rappel `entrer` a le droit de faire d'une entree
        disponible.** `EPIC11-ARB-28` tranche atelier par atelier, verbatim :
        « **Tout atelier qui a plus d'une entree commence par un menu
        d'atelier** [...] **Extraction et Exports n'en ont pas** : une seule
        entree chacun, donc le menu serait un ecran a franchir pour rien. La
        regle est « plus d'une entree », pas « un menu partout » --
        l'uniformite se paierait ici en frappes. »

        Ce palier ne connait donc **aucun** des ateliers : il transmet
        l'entree, et c'est le cablage de l'application
        (`atelier_extraction_ecriture.ChaineReelle.entrer`) qui sait lequel
        s'ouvre directement et lequel commence par son menu. La regle est citee
        ici parce que c'est ici qu'on est tente de l'enfreindre -- en glissant
        un ecran intermediaire commun aux quatre pour uniformiser."""
        if not entree.disponible:
            self._etat_a_dire = jetons.marque("substitute", entree.condition,
                                              self.app.ascii_seul)
            return
        if self._entrer is not None:
            self._entrer(entree)


__all__ = [
    "LIBELLE_PIED",
    "PIED_VIDE",
    "RACCOURCIS_ATELIERS",
    "EcranAteliers",
]
