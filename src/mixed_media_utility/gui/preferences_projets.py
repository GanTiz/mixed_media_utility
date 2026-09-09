# -*- coding: utf-8 -*-
"""Preferences utilisateur de l'ecran de gestion de projet (story 7.1, AC 3).

Trois donnees, et elles sont de meme nature : **elles suivent
l'utilisateur, pas le film** (`EPIC7-ARB-33`).

* la liste des projets rencontres (leurs chemins) ;
* les projets epingles ;
* le dernier projet ouvert.

Aucune d'elles ne s'ecrit dans un fichier de projet, ni dans le depot :
ouvrir un projet **lit**, ne modifie pas. Le support est ``QSettings``,
choix par defaut de la plateforme (le socle 7.0 n'en avait etabli aucun --
sa persistance de largeurs etait intra-session ; la fiche 7.1 prevoit
explicitement ce cas et impose de justifier le choix, c'est fait ici).

Les valeurs sont serialisees en JSON dans une **unique** cle de texte plutot
que confiees au type liste de ``QSettings`` : ce dernier rend une chaine nue
quand la liste ne compte qu'un element et une liste au-dela, difference
silencieuse qui ne se voit qu'a l'execution, sur le cas a un seul projet --
c'est-a-dire exactement le premier lancement d'une operatrice.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QSettings

#: Identite de l'application pour ``QSettings``. Ce ne sont pas des libelles
#: affiches : ils ne passent donc pas par le catalogue (ils ne se traduisent
#: jamais -- un reglage retrouve doit l'etre quelle que soit la langue).
ORGANISATION = "mixed_media_utility"
APPLICATION = "mixed_media_utility"

#: Cles de stockage. Le suffixe de version permet de changer la forme
#: stockee sans lire un jour un document d'une forme anterieure.
CLE_CONNUS = "projets/connus-v1"
CLE_EPINGLES = "projets/epingles-v1"
CLE_DERNIER_OUVERT = "projets/dernier-ouvert-v1"


class PreferencesProjets:
    """Lecture et ecriture des trois donnees ci-dessus.

    ``reglages`` est injectable : les tests passent un ``QSettings`` en
    format INI dans un dossier temporaire, de sorte qu'aucun test n'ecrive
    jamais dans les reglages reels de la machine.
    """

    def __init__(self, reglages: QSettings | None = None):
        self._reglages = reglages if reglages is not None else QSettings(
            ORGANISATION, APPLICATION
        )

    # --- helpers de serialisation ---------------------------------------

    def _lire_liste(self, cle: str) -> tuple[str, ...]:
        brut = self._reglages.value(cle)
        if not isinstance(brut, str) or not brut:
            return ()
        try:
            valeurs = json.loads(brut)
        except ValueError:
            # Un reglage corrompu ne fait pas tomber le premier ecran du
            # produit : il se lit comme « rien de memorise ».
            return ()
        if not isinstance(valeurs, list):
            return ()
        return tuple(valeur for valeur in valeurs if isinstance(valeur, str))

    def _ecrire_liste(self, cle: str, valeurs) -> None:
        self._reglages.setValue(cle, json.dumps([str(valeur) for valeur in valeurs]))

    # --- les trois donnees ------------------------------------------------

    def projets_connus(self) -> tuple[str, ...]:
        return self._lire_liste(CLE_CONNUS)

    def definir_projets_connus(self, chemins) -> None:
        self._ecrire_liste(CLE_CONNUS, chemins)

    def epingles(self) -> tuple[str, ...]:
        return self._lire_liste(CLE_EPINGLES)

    def definir_epingles(self, chemins) -> None:
        self._ecrire_liste(CLE_EPINGLES, chemins)

    def dernier_ouvert(self) -> str | None:
        valeur = self._reglages.value(CLE_DERNIER_OUVERT)
        return valeur if isinstance(valeur, str) and valeur else None

    def definir_dernier_ouvert(self, chemin) -> None:
        self._reglages.setValue(CLE_DERNIER_OUVERT, "" if chemin is None else str(chemin))

    def enregistrer(self) -> None:
        """Forcer l'ecriture sur le support (``sync`` de ``QSettings``)."""
        self._reglages.sync()
