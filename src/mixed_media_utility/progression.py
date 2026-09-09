"""Canal de progression du coeur : emission des jalons, calcul du temps restant.

Deux pieces, sans aucune dependance a Qt, a ``gui/``, au disque ni au binaire
d'encodage -- ce module est du **calcul pur** plus un appel de rappel :

* :class:`EmetteurProgression` -- la surface par laquelle une tache longue du
  coeur *emet* ses jalons ``(faites, total)``. Elle est **observationnelle**
  (`EPIC7-ARB-79`) : aucune de ses defaillances ne peut faire echouer, ralentir
  notablement ni modifier le travail qu'elle observe ;
* :class:`EstimateurTempsRestant` -- le calcul, pur : on lui **note** des
  jalons horodates, il rend le temps par frame ecrite mesure sur une fenetre
  glissante courte, et le temps restant qui s'en deduit.

**L'unite est la seconde par frame ecrite** (`EPIC7-ARB-80`), jamais son
inverse. Dans ce depot, le nombre d'images par seconde designe toujours le
rythme du **rush** -- celui que le projet consigne, celui que le badge de
l'atelier Scan constate -- et l'homonymie porterait sur le concept central du
produit. Le nom porte donc l'unite :
:attr:`EstimateurTempsRestant.secondes_par_frame`.

**Interdit central** (`EPIC7-ARB-67`) : aucun temps n'est rendu tant qu'aucune
mesure reelle n'existe. La reponse est alors ``None`` -- jamais ``0``, qui
s'afficherait « il reste 0 seconde », c'est-a-dire un mensonge et non une
absence, jamais ``inf`` non plus.

**Interdit symetrique** (`EPIC7-ARB-79`) : l'absorption pratiquee par
:class:`EmetteurProgression` ne couvre **que** les defaillances du canal
lui-meme. Les erreurs du travail observe -- echec d'extraction, garde de
comptage, refus durs d'ecriture -- traversent intactes, texte compris. Sans
cette symetrie, on echangerait un mensonge d'affichage contre un faux succes.
"""

from __future__ import annotations

import logging
import math
import time

_JOURNAL = logging.getLogger(__name__)


#: Duree de la fenetre glissante sur laquelle le temps par frame est mesure,
#: en secondes. **Valeur provisoire, faute de mesure terrain** -- meme regime
#: que ``SCALE_WARNING_TOLERANCE`` de ``scan_detection``, a recalibrer au
#: premier pilote reel. Trop courte, le chiffre saute a chaque frame ; trop
#: longue, il met une eternite a suivre un changement de regime (une page
#: lourde apres dix pages legeres).
FENETRE_GLISSANTE_SECONDES = 5.0


class EmetteurProgression:
    """Emettre des jalons ``(faites, total)`` sans jamais casser l'observe.

    Le rappel recoit **deux entiers positionnels**, et rien d'autre : c'est
    l'arite deja gelee par le socle 7.0 (``executeur.soumettre``), et le temps
    restant ne voyage pas avec eux -- il se calcule a cote, par
    :class:`EstimateurTempsRestant`.

    Trois proprietes, toutes exigees par `EPIC7-ARB-79` :

    * **monotone et bornee** : ``faites`` ne decroit jamais et ne depasse jamais
      ``total``. Il n'est **jamais force a ``total``** en fin de course : quand
      le travail observe a produit moins que prevu, le dernier jalon reste sous
      le total, et c'est la garde du travail lui-meme qui leve. Completer
      artificiellement a 100 % masquerait dans l'affichage exactement le defaut
      que cette garde existe pour lever (risque R12) ;
    * **un jalon par avancee constatee**, jamais de doublon : le chemin
      d'extraction scrute un repertoire a intervalle fixe, et un rappel appele a
      chaque scrutation sans que rien n'ait bouge noierait le consommateur ;
    * **toute defaillance est absorbee**, et journalisee **une seule fois** : un
      rappel fautif appele trois cents fois noierait le journal.

    Un emetteur sans rappel, ou dont le total est nul, est **inactif** : il
    n'appelle rien. C'est le repli `AR3`, et c'est le comportement d'aujourd'hui.
    """

    def __init__(self, rappel_progression=None, total=0) -> None:
        self._rappel = rappel_progression if callable(rappel_progression) else None
        try:
            self._total = int(total)
        except (TypeError, ValueError, OverflowError):
            # Un total illisible desactive le canal ; il ne fait jamais echouer
            # la tache qui vient de le construire. `OverflowError` autant que
            # les deux autres : `int(nan)` leve `ValueError` mais `int(inf)`
            # leve `OverflowError`, et une surface publique qui promet de ne
            # jamais lever ne peut pas laisser passer la moitie des flottants
            # non finis (revue de vague 2 bis, EC-6 et BH-2, trouves
            # separement par deux couches aveugles l'une a l'autre).
            self._total = 0
        self._dernier = 0
        self._defaillance_journalisee = False

    @property
    def actif(self) -> bool:
        """Vrai si un jalon peut encore servir a quelque chose."""
        return self._rappel is not None and self._total > 0

    @property
    def total(self) -> int:
        """Cardinal de la selection observee -- exact par construction."""
        return self._total

    @property
    def dernier(self) -> int:
        """Dernier ``faites`` reellement emis ; ``0`` si aucun jalon ne l'a ete."""
        return self._dernier

    def emettre(self, faites) -> bool:
        """Emettre un jalon si -- et seulement si -- le travail a avance.

        Rend ``True`` quand un jalon a effectivement ete transmis. Ne leve
        jamais : c'est la propriete qui rend la progression observationnelle.
        """
        if not self.actif:
            return False
        try:
            faites = int(faites)
        except (TypeError, ValueError, OverflowError):
            # Comptage rendu impossible : moins de jalons, jamais une erreur.
            # `OverflowError` couvre l'infini, que `int()` refuse autrement que
            # `nan` (EC-6 / BH-2).
            return False
        if faites > self._total:
            faites = self._total
        if faites <= self._dernier:
            return False
        self._dernier = faites
        try:
            self._rappel(faites, self._total)
        except Exception:  # noqa: BLE001 -- l'observation ne casse jamais l'observe
            if not self._defaillance_journalisee:
                self._defaillance_journalisee = True
                _JOURNAL.warning(
                    "Le rappel de progression a leve ; la progression est "
                    "abandonnee dans le journal mais la tache continue. Cet "
                    "avertissement n'est emis qu'une fois pour toute la tache.",
                    exc_info=True,
                )
        return True


class EstimateurTempsRestant:
    """Mesurer le temps par frame ecrite, et en deduire le temps restant.

    Calcul **pur** : on lui note des jalons ``(faites, total)``, il les
    horodate avec son horloge et ne retient que ceux qui tombent dans une
    fenetre glissante courte. Le temps par frame est la duree reelle de la
    fenetre divisee par l'accroissement de ``faites`` sur cette meme fenetre ;
    le temps restant en est le produit par le nombre de frames restantes.

    L'horloge est **injectable** et vaut ``time.monotonic`` par defaut, jamais
    ``time.time`` : l'horloge murale recule quand l'horloge systeme est ajustee
    (synchronisation reseau, changement d'heure), ce qui produirait une duree
    negative au milieu d'une extraction longue.

    **La fenetre borne la moyenne, elle n'eteint pas la mesure.** Quand les
    jalons sont plus espaces que la fenetre -- une unite de travail lente, une
    frame de scan 16 bits --, l'elagage conserve les **deux** derniers jalons
    plutot que de retomber a un seul : voir :meth:`_vue_elaguee`. Le seul cas ou
    plus rien n'est retenu est celui ou le jalon le plus recent est lui-meme
    sorti de la fenetre, c'est-a-dire la tache qui a cale.

    **Les lectures ne mutent rien.** :attr:`secondes_par_frame` et
    :attr:`temps_restant` evaluent la fenetre sur une vue ; seul :meth:`noter`
    elague. C'est ce qui rend :attr:`faites` monotone, et donc une jauge qui lit
    ce couple incapable de reculer.
    """

    def __init__(self, *, fenetre_secondes=FENETRE_GLISSANTE_SECONDES, horloge=None) -> None:
        fenetre = float(fenetre_secondes)
        if not (fenetre > 0.0) or not math.isfinite(fenetre):
            raise ValueError(
                f"La fenetre glissante doit etre une duree strictement positive, "
                f"recu {fenetre_secondes!r}."
            )
        self._fenetre = fenetre
        self._horloge = time.monotonic if horloge is None else horloge
        self._jalons: list[tuple[float, int]] = []
        self._total: int | None = None

    # -- lecture ---------------------------------------------------------

    @property
    def horloge(self):
        """L'horloge reellement utilisee -- lisible pour que le banc la verifie."""
        return self._horloge

    @property
    def fenetre_secondes(self) -> float:
        return self._fenetre

    @property
    def total(self) -> int | None:
        """Cardinal de la tache courante, ``None`` tant qu'aucun jalon n'est note."""
        return self._total

    @property
    def faites(self) -> int:
        """Dernier ``faites`` note, ``0`` en l'absence de jalon.

        **Ne recule jamais** tant que la tache est la meme : c'est le dernier
        jalon *note*, pas le dernier jalon *retenu par la fenetre*. Une jauge
        qui lit ce couple ne peut donc pas retomber de 50 % a 0 % au seul motif
        que la tache a cale trente secondes -- ce que faisait l'elagage pratique
        depuis la lecture (BH-1).
        """
        return self._jalons[-1][1] if self._jalons else 0

    # -- ecriture --------------------------------------------------------

    def reinitialiser(self) -> None:
        """Oublier toute mesure -- une nouvelle tache commence."""
        self._jalons = []
        self._total = None

    def noter(self, faites, total) -> bool:
        """Noter un jalon horodate ; rend ``True`` s'il a ete retenu.

        Les jalons hors bornes sont **ignores**, jamais refuses par une
        exception : cet estimateur est alimente par un canal observationnel, et
        il ne peut pas se permettre d'etre la piece qui casse.
        """
        try:
            faites = int(faites)
            total = int(total)
        except (TypeError, ValueError, OverflowError):
            # `OverflowError` couvre l'infini : `int(inf)` ne leve pas la meme
            # exception que `int(nan)`, et le contrat ecrit ici est « les jalons
            # hors bornes sont ignores, jamais refuses par une exception »
            # (EC-6 / BH-2).
            return False
        if total <= 0:
            return False
        if faites < 0 or faites > total:
            return False
        if total != self._total:
            # Un total different, c'est une autre tache : la mesure precedente
            # ne dit rien de celle-ci. Un denominateur fige au premier lot est
            # precisement le defaut que la regle des fabriques traque.
            self._jalons = []
            self._total = total
        elif self._jalons and faites < self._jalons[-1][1]:
            # `faites` ne recule pas. L'egalite, elle, est legitime : c'est le
            # regime « la tache a cale », qui doit rendre `None` et non un
            # chiffre herite.
            return False
        instant = float(self._horloge())
        self._jalons.append((instant, faites))
        # L'elagage a lieu **ici**, a l'ecriture, et nulle part ailleurs : une
        # propriete de lecture qui mute l'etat faisait reculer `faites` de 50 a
        # 0 parce qu'on avait simplement lu `secondes_par_frame` apres un calage
        # (revue de vague 2 bis, BH-1).
        self._jalons = self._vue_elaguee(instant)
        return True

    # -- mesure ----------------------------------------------------------

    def _vue_elaguee(self, reference: float) -> list[tuple[float, int]]:
        """Les jalons retenus contre `reference` -- **sans muter** l'estimateur.

        Fonction pure : c'est ce qui permet a :attr:`secondes_par_frame` d'etre
        une lecture, et non une lecture qui deplace ce qu'elle lit (revue de
        vague 2 bis, BH-1).

        Regle en trois temps :

        1. on ne retient que les jalons **strictement** plus recents que la
           fenetre -- la borne est stricte, et c'est elle qui borne la moyenne
           en regime rapide (EC-4) ;
        2. si le jalon le plus recent est lui-meme sorti de la fenetre, la tache
           a **cale** : plus rien n'est retenu, et :attr:`secondes_par_frame`
           rend ``None``. C'est l'interdit d'`EPIC7-ARB-67` -- pas de chiffre
           herite qui continuerait de descendre pendant que rien n'avance ;
        3. sinon, on **conserve toujours au moins deux jalons** : le plus
           recent, plus le dernier anterieur a la fenetre. Sans ce troisieme
           temps, deux jalons consecutifs espaces d'au moins la fenetre
           (5,0 s par defaut) faisaient retomber la liste a un element et
           :attr:`temps_restant` rendait ``None`` **definitivement** -- or une
           unite de travail plus lente que la fenetre, comme une frame de scan
           16 bits, est precisement le regime ou l'estimation sert le plus
           (EC-5 et BH-3, trouves separement par deux couches).
        """
        limite = reference - self._fenetre
        recents = [jalon for jalon in self._jalons if jalon[0] > limite]
        if len(recents) >= 2:
            return recents
        if not self._jalons or self._jalons[-1][0] <= limite:
            return recents
        return self._jalons[-2:]

    @property
    def secondes_par_frame(self) -> float | None:
        """Temps mesure par frame **ecrite**, ou ``None`` faute de mesure.

        La fenetre est evaluee contre l'instant **courant**, et non contre le
        dernier jalon note : une tache qui cale doit voir ses jalons sortir de
        la fenetre et cesser de rendre un chiffre, plutot que geler
        indefiniment le dernier connu.

        Cette evaluation se fait sur une **vue**, sans rien deplacer : lire deux
        fois de suite rend la meme chose, et :attr:`faites` ne bouge pas parce
        qu'on a lu (BH-1).
        """
        vue = self._vue_elaguee(float(self._horloge()))
        if len(vue) < 2:
            return None
        debut_instant, debut_faites = vue[0]
        fin_instant, fin_faites = vue[-1]
        ecrites = fin_faites - debut_faites
        if ecrites <= 0:
            # Couvre a la fois « la tache a cale » et « aucune frame faite » :
            # un accroissement nul n'autorise aucune extrapolation.
            return None
        duree = fin_instant - debut_instant
        if duree <= 0.0:
            return None
        valeur = duree / ecrites
        if not math.isfinite(valeur):
            return None
        return valeur

    @property
    def temps_restant(self) -> float | None:
        """Secondes restantes estimees, ou ``None`` tant qu'aucune mesure n'existe."""
        par_frame = self.secondes_par_frame
        if par_frame is None or self._total is None:
            return None
        restantes = self._total - self._jalons[-1][1]
        if restantes <= 0:
            # La mesure existe et le travail est fini : zero n'est pas une
            # absence de mesure, c'est le resultat.
            return 0.0
        return par_frame * restantes


__all__ = [
    "FENETRE_GLISSANTE_SECONDES",
    "EmetteurProgression",
    "EstimateurTempsRestant",
]
