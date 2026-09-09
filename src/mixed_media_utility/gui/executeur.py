# -*- coding: utf-8 -*-
"""Executeur de taches de fond (story 7.0, AC 4 et AC 5).

La GUI heberge le coeur Python EN PROCESSUS (FR1, ``EPIC7-ARB-46``) : une
tache est une fonction Python du coeur plus ses arguments nommes, executee
dans un thread de travail du processus de la GUI -- JAMAIS un sous-processus
CLI, jamais un parsing de sortie.

Modele d'etats d'une tache (FR4, v1) :

* ``EN_COURS`` des la soumission ;
* ``TERMINEE`` avec son resultat, ou
* ``ECHOUEE`` portant le MOTIF : le message verbatim de l'exception typee
  du coeur (``str(exc)``), jamais recopie ni reformule -- le coeur ecrit,
  la GUI lit.

Les transitions sont observables par signaux Qt (les cartes visibles sont
la story 7.3 ; ici l'objet tache et ses signaux suffisent). Aucun widget
n'est touche depuis le thread de travail : les signaux traversent les
threads par connexion en file, c'est le modele Qt.

Canal de progression (AR3) : l'executeur ACCEPTE un rappel optionnel et le
transmet tel quel aux taches qui savent le consommer (parametre nomme
``rappel_progression`` dans leur signature). Aucune fonction du coeur
n'exige de rappel ; 7.0 n'en ajoute aucun au coeur.
"""

import inspect

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

# Etats d'une tache -- le modele de FR4, rien de plus.
EN_COURS = "en-cours"
TERMINEE = "terminee"
ECHOUEE = "echouee"


class Tache(QObject):
    """Une tache de fond : etat courant, resultat ou motif, signaux."""

    # Emis a la transition finale ; l'argument est le resultat verbatim de
    # la fonction du coeur, ou le motif verbatim de son exception.
    terminee = Signal(object)
    echouee = Signal(str)

    def __init__(self, fonction, arguments, parent=None):
        super().__init__(parent)
        self._fonction = fonction
        self._arguments = dict(arguments)
        # En cours des la soumission : du point de vue de l'operatrice la
        # tache est lancee, la file d'attente du pool est un detail.
        self._etat = EN_COURS
        self._resultat = None
        self._motif = None

    @property
    def etat(self):
        """L'etat courant : EN_COURS, TERMINEE ou ECHOUEE."""
        return self._etat

    @property
    def resultat(self):
        """Le resultat rendu par la fonction du coeur (TERMINEE seulement)."""
        return self._resultat

    @property
    def motif(self):
        """Le motif d'echec, verbatim ``str(exc)`` (ECHOUEE seulement)."""
        return self._motif

    # Les mutations sont internes a l'executeur (appelees du thread de
    # travail, AVANT l'emission du signal correspondant).

    def _terminer(self, resultat):
        self._resultat = resultat
        self._etat = TERMINEE
        self.terminee.emit(resultat)

    def _echouer(self, motif):
        self._motif = motif
        self._etat = ECHOUEE
        self.echouee.emit(motif)


class _Execution(QRunnable):
    """L'enveloppe QRunnable qui execute une tache dans le pool."""

    def __init__(self, tache):
        super().__init__(self)
        self._tache = tache

    def run(self):
        tache = self._tache
        try:
            resultat = tache._fonction(**tache._arguments)
        except BaseException as exc:
            # BaseException et non Exception : une KeyboardInterrupt ou une
            # SystemExit levee dans ce thread de travail (revue de vague 1)
            # ne doit PAS traverser sans etat final -- sinon la tache reste
            # EN_COURS pour toujours, aucun signal n'est emis, et tout
            # attendeur (qtbot.waitUntil, un futur consommateur GUI) reste
            # suspendu indefiniment. Le motif reste le message VERBATIM de
            # l'exception : str(exc), octet pour octet, jamais recopie ni
            # reformule (FR4). L'application ne crashe jamais sur un echec
            # de tache -- pas plus une exception typee du coeur qu'une
            # exception de controle du thread.
            tache._echouer(str(exc))
        else:
            tache._terminer(resultat)


class Executeur(QObject):
    """File de taches de fond, un seul thread de travail (file serielle).

    Un thread suffit au contrat de 7.0 : les taches longues du produit
    (detection, extraction) sont sequencees, et une file serielle rend les
    positions observables -- la parallelisation, si elle vient, viendra
    avec les cartes de 7.3.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)

    def soumettre(self, fonction, arguments=None, rappel_progression=None):
        """Soumettre une fonction du coeur ; rend la :class:`Tache`.

        ``rappel_progression`` est OPTIONNEL de bout en bout (AR3) : il
        n'est transmis -- tel quel -- qu'aux fonctions dont la signature
        declare un parametre de ce nom. Une fonction du coeur sans rappel
        s'execute a l'identique.
        """
        if not callable(fonction):
            raise TypeError(f"la tache doit etre appelable, recu {fonction!r}")
        arguments = dict(arguments or {})
        if rappel_progression is not None and self._accepte_progression(fonction):
            arguments["rappel_progression"] = rappel_progression
        tache = Tache(fonction, arguments, parent=self)
        self._pool.start(_Execution(tache))
        return tache

    def attendre(self, delai_ms=-1):
        """Attendre la fin des taches soumises (banc de test)."""
        return self._pool.waitForDone(delai_ms)

    @staticmethod
    def _accepte_progression(fonction):
        """Vrai si la signature declare ``rappel_progression`` (ou **kwargs)."""
        try:
            parametres = inspect.signature(fonction).parameters
        except (TypeError, ValueError):
            return False
        if "rappel_progression" in parametres:
            return True
        return any(
            p.kind is inspect.Parameter.VAR_KEYWORD for p in parametres.values()
        )


# ---------------------------------------------------------------------------
# Tache de demonstration : une VRAIE fonction du coeur, pure et bon marche.
# ---------------------------------------------------------------------------

# Gabarit du depot, deux frames par page, sans marqueurs -- un identifiant
# du coeur, verbatim (les codes du coeur ne se traduisent pas).
GABARIT_DEMONSTRATION = "tpl-a4-portrait-2f-v1"
DPI_DEMONSTRATION = 300


def tache_de_demonstration(rappel_progression=None):
    """Construire un plan de decoupe de page -- calcul pur du coeur.

    Appelle ``scan_crop.build_page_crop_plan`` (« calcul pur, aucun pixel,
    aucune ecriture », fiche 5.25) dans le processus courant : c'est la
    preuve d'hebergement in-process de l'AC 4, et la consommatrice du
    rappel optionnel de l'AC 5 (un jalon avant l'appel, un apres).
    """
    from .. import page_templates, scan_crop  # le coeur, importe par la GUI

    if rappel_progression is not None:
        rappel_progression(0, 1)
    spec = page_templates.get_template(GABARIT_DEMONSTRATION)
    slots = [
        {"slot_index": indice + 1, "frame_timecode": f"00:00:{indice:02d}:00"}
        for indice in range(spec.frames_per_page)
    ]
    plan = scan_crop.build_page_crop_plan(
        template_id=GABARIT_DEMONSTRATION, slots=slots, dpi=DPI_DEMONSTRATION
    )
    if rappel_progression is not None:
        rappel_progression(1, 1)
    return plan
