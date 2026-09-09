# Banc headless des tests GUI (story 7.0).
#
# Le contrat du banc est OFFSCREEN : la suite tests/unit/gui/ passe verte
# sans Xvfb ni ecran (AC 7, "le banc headless est le contrat"). On pose
# QT_QPA_PLATFORM=offscreen AVANT toute creation de QApplication -- ce
# conftest est importe par pytest avant les modules de test du dossier,
# donc avant le premier import de PySide6 par un test.
#
# **Correctif de la revue de vague 1.** La redaction precedente affirmait que
# "le reglage est scope a ce conftest (donc aux tests GUI) : la suite du coeur
# n'est pas touchee". C'etait FAUX, et mesure : `os.environ` est global au
# PROCESSUS, pas au dossier. La variable posee ici au chargement du conftest
# restait donc en place pour toute la session pytest, et
# `test_cadence_previz.py::test_a_real_window_shows_a_retained_frame_and_never_a_discarded_one`
# -- qui recopie `dict(os.environ)` dans le sous-processus d'une VRAIE fenetre
# lancee sous Xvfb -- voyait `offscreen` : la fenetre ne s'affichait sur aucun
# ecran, la capture ne voyait rien, le test echouait. Reproduit en 3 secondes
# par `pytest tests/unit/gui <ce test>`, alors que le test seul passe.
#
# Le geste correct : poser la variable au chargement (la garantie « avant toute
# QApplication » l'exige), puis la RETIRER des que la QApplication existe --
# Qt a lu la plateforme a sa construction, la variable n'a plus d'utilite ici
# et ne doit plus fuir vers les sous-processus des autres suites. Le retrait
# est fait par une fixture qui depend de `qapp`, donc l'ordre de collection des
# fichiers n'y change rien.

import os
import sys
from pathlib import Path

import pytest

#: Valeur que l'operateur avait posee, AVANT notre reglage -- si xcb a ete
#: choisi a la main (capture manuelle sous Xvfb), on le respecte et on le
#: restaure tel quel. `setdefault` ne l'ecrase jamais.
_PLATEFORME_INITIALE = os.environ.get("QT_QPA_PLATFORM")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Convention du depot (voir les tests existants de tests/unit/) : le paquet
# s'importe depuis src/ par insertion de chemin, pas par installation. Ici
# on le fait UNE fois pour tout le dossier gui/ plutot que dans chaque
# fichier de test.
_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


@pytest.fixture(scope="session", autouse=True)
def _plateforme_offscreen_ne_fuit_pas(qapp):
    """Rendre l'environnement du processus tel qu'il etait, une fois la
    `QApplication` construite sous offscreen.

    La dependance a `qapp` (fixture de pytest-qt) est le coeur du geste : elle
    garantit que la QApplication est **deja construite** -- donc que Qt a deja
    lu la plateforme -- quand on retire la variable. Sans cette dependance, un
    retrait premature ferait retomber le banc sur la plateforme par defaut et
    exigerait un ecran.
    """
    if _PLATEFORME_INITIALE is None:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = _PLATEFORME_INITIALE
    yield
