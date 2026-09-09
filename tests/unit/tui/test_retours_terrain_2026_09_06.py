# -*- coding: utf-8 -*-
"""Les retours TERRAIN d'Egan du 2026-09-06, mesures un par un.

Ce banc existe parce qu'un retour de terrain n'est pas une story : il n'a ni
critere d'acceptation ni fiche, et le defaut qu'il nomme est souvent DECRIT par
son symptome plutot que par sa cause. Le grouper ici, avec le verbatim en
docstring, garde la trace de ce qui a ete OBSERVE a cote de ce qui a ete
CORRIGE -- les deux ne coincident pas toujours, et le premier retour du lot en
est l'exemple.

Chaque test porte le verbatim du retour qu'il ferme.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility.tui import projets                        # noqa: E402
from mixed_media_utility.tui.atelier_extraction_ecriture import (  # noqa: E402
    chaine_du_produit)
from mixed_media_utility.tui.ecran_projet import EcranCreation     # noqa: E402


# ---------------------------------------------------------------------------
# « Creation d'un projet dans un dossier vide [...] Mais Echap fais un retour
#   a l'ecran precedent au lieu d'ouvrir la liste des projets avec ce projet
#   present. »
#
# Le symptome dit « retour de pile », la cause est ailleurs : la pile etait
# saine (`test_paliers_et_passages` le mesurait deja), mais le projet cree
# n'entrait jamais dans les recents, parce que `apres_creation` court-circuitait
# `EcranProjet.ouvrir` -- seul appelant de `recents.noter_ouverture` de tout
# `src/`. L'operateur retombait donc sur une liste INCHANGEE, ce qu'il a lu
# comme un mauvais retour.
# ---------------------------------------------------------------------------

def _recents_avec_un_projet_deja_la(tmp_path):
    """Une liste de recents qui porte DEJA une entree, distinguable de la neuve.

    La regle des fabriques du depot : une fabrique de collection produit au
    moins deux elements distinguables, et la cible ne se place pas en premiere
    position. Ici les deux elements sont un projet ANCIEN, note a la main, et
    le projet NEUF que le parcours va creer -- le second devant apparaitre
    **sans chasser** le premier.
    """
    ancien = tmp_path / "projet-deja-connu"
    ancien.mkdir()
    recents = projets.Recents(tmp_path / "reglages" / "recents-v1.json")
    recents.noter_ouverture(ancien)
    return recents, ancien


def test_un_projet_CREE_entre_dans_les_recents(tmp_path, banc):
    """Le retour d'Egan, ferme a sa cause et non a son symptome.

    On monte la chaine **du produit** -- pas une chaine degradee de banc --,
    on cree un projet dans un dossier vide par le vrai `EcranCreation`, et on
    relit la liste des recents sur le disque. Elle doit porter les DEUX
    projets.
    """
    recents, ancien = _recents_avec_un_projet_deja_la(tmp_path)
    chaine = chaine_du_produit(recents=recents)
    cible = tmp_path / "dossier-vide" / "projet-neuf"
    cible.parent.mkdir()

    async def scenario(pilote):
        chaine.creer(cible)
        await pilote.pause()
        ecran = pilote.app.screen
        assert isinstance(ecran, EcranCreation), (
            f"le parcours de creation doit monter E0-4, il a monte {ecran!r}")
        ecran.valider()
        await pilote.pause()

    banc(chaine.app, scenario)

    chemins = [Path(entree.chemin).resolve() for entree in recents.lire()]
    assert cible.resolve() in chemins, (
        "le projet fraichement cree doit figurer dans les recents : c'est ce "
        "que l'operateur vient chercher en remontant au palier 0. Trouve "
        f"{chemins!r}")
    assert ancien.resolve() in chemins, (
        "noter le projet neuf ne doit pas chasser celui qui etait deja la")


def test_la_creation_passe_par_EcranProjet_ouvrir_et_PAS_par_celui_de_la_chaine(
        tmp_path, banc):
    """Le volet symetrique : la mesure ci-dessus doit MORDRE.

    Un banc qui verifie seulement « le projet est dans les recents » resterait
    vert si quelqu'un ajoutait un second `noter_ouverture` ailleurs -- par
    exemple dans `ChaineReelle.ouvrir`, la variante ecartee au diagnostic, qui
    doublerait l'appel sur le parcours d'ouverture ORDINAIRE. On mesure donc
    aussi qu'il n'y a **qu'un** appel, en comptant les ouvertures notees.
    """
    recents, _ancien = _recents_avec_un_projet_deja_la(tmp_path)
    appels: list[Path] = []
    vrai_noter = recents.noter_ouverture

    def noter_en_comptant(dossier, quand=None):
        appels.append(Path(dossier))
        return vrai_noter(dossier, quand)

    recents.noter_ouverture = noter_en_comptant  # type: ignore[method-assign]
    chaine = chaine_du_produit(recents=recents)
    cible = tmp_path / "dossier-vide" / "projet-neuf"
    cible.parent.mkdir()

    async def scenario(pilote):
        chaine.creer(cible)
        await pilote.pause()
        pilote.app.screen.valider()
        await pilote.pause()

    banc(chaine.app, scenario)

    notes = [chemin for chemin in appels if chemin.resolve() == cible.resolve()]
    assert len(notes) == 1, (
        "la creation doit noter l'ouverture UNE fois et une seule : zero, et "
        "la liste ment ; deux, et un second appelant a ete ajoute quelque part "
        f"-- trouve {len(notes)} appel(s) sur {appels!r}")
