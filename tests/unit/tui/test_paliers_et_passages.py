# -*- coding: utf-8 -*-
"""Stations et passages : ce que la revue de la vague 2 a trouve (`V2-M1`, `V2-M2`).

**Ce fichier existe parce qu'aucun test ne pouvait attraper ces deux defauts.**
Les mesures d'alors portaient sur `app.rang` -- une hauteur de pile -- et sur
`_running` / `is_attached` / l'identite des enfants, qui sont **justes des deux
cotes** du defaut. Le test d'AC 6.2 etait meme vert *parce que* le defaut etait
la : il assertait que les enfants n'avaient pas ete recomposes, ce qui est la
signature exacte d'un ecran qui ne se redessine pas.

Les mesures ici portent donc sur **le texte reellement peint** et sur
`passages_empiles`, qui distingue « je suis sur le palier 1 » de « je suis sur un
formulaire pose sur le palier 1 » -- ce que `rang` seul confondait par
construction.
"""
import json
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.tui import ecran_ateliers, jetons
from mixed_media_utility.tui.coque import (
    Contexte, CoqueTui, EcranPasEncore, Palier, PalierTemoin)
from mixed_media_utility.tui.ecran_projet import EcranCreation, EcranProjet
from mixed_media_utility.tui.projets import Recents


# ---------------------------------------------------------------------------
# Fabriques. **Deux projets distinguables**, et la cible n'est pas le premier.
# ---------------------------------------------------------------------------

#: Deux projets aux compteurs DIFFERENTS. Un remplissage uniforme rendrait
#: invisible un ecran qui garde le projet precedent -- c'est exactement le
#: defaut `V2-M2`, et la regle des fabriques du depot le dit depuis le mutant
#: `M25` de la story 5.7.
PROJETS = (("projet_alpha", 1), ("projet_omega", 3))


def _projet(tmp_path, nom: str, rushes: int) -> Path:
    chemin = creer_projet(tmp_path, nom).chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": f"{nom}-r{n}"} for n in range(rushes)]
    (chemin / "project.json").write_text(json.dumps(document), encoding="utf-8")
    return chemin


def _texte(ecran) -> str:
    """Le texte REELLEMENT peint, **corps ET bandeau**.

    C'est la seule mesure qui distingue un ecran a jour d'un ecran qui a garde
    le dessin de sa visite precedente. Le bandeau en fait partie : les
    compteurs y vivent, pas dans le corps -- mesurer le corps seul laisserait
    passer un menu dont les chiffres sont perimes.
    """
    from textual.widgets import Static
    bandeau = (str(ecran.query_one("#bandeau", Static).content)
               if ecran.is_mounted else "")
    return str(ecran._corps.content) + "\n" + bandeau


# ---------------------------------------------------------------------------
# `V2-M1` -- un passage n'est pas une station
# ---------------------------------------------------------------------------

def test_un_passage_ne_compte_pas_dans_le_rang():
    """La propriete qui manquait, prise a la racine.

    `rang` comptait `len(screen_stack) - 1`. Trois symptomes en decoulaient ;
    aucun ne se voyait sans cette distinction.
    """
    assert EcranCreation().TRANSITOIRE is True
    assert EcranPasEncore("x", "y").TRANSITOIRE is True
    # Volet symetrique : une station reste une station, sans quoi le predicat
    # serait vrai partout et ne mesurerait rien.
    assert PalierTemoin("Ateliers", "q").TRANSITOIRE is False
    assert ecran_ateliers.EcranAteliers().TRANSITOIRE is False


def test_descendre_depuis_un_FORMULAIRE_ne_saute_pas_de_palier(banc):
    """**Le scenario exact d'Egan** (parcours manuel du 2026-08-28).

    Il cree un projet depuis le palier 0, et atterrit « directement sur
    l'onglet Projet et non pas sur le menu general du projet ». Cause : le
    formulaire occupait le rang 1, donc `descendre()` prenait `_paliers[2]`.
    """
    creation = EcranCreation()
    app = CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                            PalierTemoin("Ateliers", "q quitter"),
                            PalierTemoin("Palier Projet", "q quitter")])

    async def scenario(pilote):
        pilote.app.descendre(creation)      # le formulaire, un passage
        await pilote.pause()
        depuis_le_formulaire = (pilote.app.rang, pilote.app.passages_empiles)
        pilote.app.descendre()              # ce que fait `apres_creation`
        await pilote.pause()
        return depuis_le_formulaire, pilote.app.rang, pilote.app.screen.titre

    depuis, rang, titre = banc(app, scenario)
    assert depuis == (0, 1), "le formulaire est un passage pose sur le palier 0"
    assert (rang, titre) == (1, "Ateliers"), \
        "on descend au palier SUIVANT, pas a celui d'apres"


def test_le_formulaire_valide_ne_reste_pas_sur_le_chemin_du_RETOUR(banc):
    """Second symptome du meme retour : « quand on fait Echap on revient a la
    page precedente et non pas au menu general. J'ai du faire echap de
    nombreuses fois pour revenir au debut. »"""
    app = CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                            PalierTemoin("Ateliers", "q quitter")])

    async def scenario(pilote):
        pilote.app.descendre(EcranCreation())
        await pilote.pause()
        pilote.app.descendre()
        await pilote.pause()
        pilote.app.action_remonter()        # UN seul Echap
        await pilote.pause()
        return (pilote.app.rang, pilote.app.screen.titre,
                pilote.app.passages_empiles)

    assert banc(app, scenario) == (0, "Projet", 0), \
        "un seul Echap ramene au palier 0, sans repasser par le formulaire"


def test_revenir_aux_ateliers_ne_laisse_JAMAIS_sur_un_formulaire(banc):
    """Troisieme occurrence, **encore latente** quand la revue l'a trouvee.

    `revenir_aux_ateliers()` depilait `while rang > RANG_DES_ATELIERS`. Quand un
    passage occupe *exactement* la hauteur des ateliers -- un formulaire ouvert
    depuis le palier 0 --, la condition est fausse des le premier tour : la
    remontee ne depile rien et **laisse l'operateur sur le formulaire**, la ou
    `EPIC11-ARB-13` promet une station.

    Le scenario de l'AC 6.4 ne pouvait pas le voir : il empile ses passages
    au-dessus du rang vise, donc la boucle depile de toute facon. C'est la regle
    des fabriques du depot, transposee a une pile -- « au moins un test place la
    cible ailleurs qu'en premiere position ».
    """
    racine = PalierTemoin("Projet", "q quitter")
    app = CoqueTui(paliers=[racine, PalierTemoin("Ateliers", "q quitter")])

    async def scenario(pilote):
        pilote.app.descendre(EcranCreation())   # un passage a la hauteur 1
        await pilote.pause()
        avant = (pilote.app.rang, pilote.app.passages_empiles,
                 type(pilote.app.screen).__name__)
        pilote.app.revenir_aux_ateliers()
        await pilote.pause()
        return avant, pilote.app.screen is racine, pilote.app.passages_empiles

    avant, sur_une_station, apres = banc(app, scenario)
    assert avant == (0, 1, "EcranCreation")
    assert sur_une_station, "la remontee a laisse l'operateur sur un formulaire"
    assert apres == 0


def test_revenir_aux_ateliers_depile_aussi_les_passages_du_DESSUS(banc):
    """Volet symetrique : le cas que l'AC 6.4 couvrait deja doit rester couvert.

    Sans lui, on pourrait « corriger » la remontee en ne depilant plus que les
    passages du rang vise, et casser le chemin nominal d'une execution --
    confirmation, execution, resultat empiles sur le menu.
    """
    menu = PalierTemoin("Ateliers", "q quitter")
    app = CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"), menu])

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        pilote.app.descendre(EcranCreation())
        await pilote.pause()
        pilote.app.descendre(EcranPasEncore("Extraction", "vague 3"))
        await pilote.pause()
        avant = pilote.app.passages_empiles
        pilote.app.revenir_aux_ateliers()
        await pilote.pause()
        return avant, pilote.app.screen is menu, pilote.app.passages_empiles

    avant, sur_le_menu, apres = banc(app, scenario)
    assert avant == 2
    assert sur_le_menu and apres == 0


def test_une_STATION_n_est_jamais_depilee_par_le_depilement_des_passages(banc):
    """Volet symetrique du precedent, et il n'est pas decoratif : un
    depilement trop gourmand ramenerait l'operateur au palier 0 a chaque
    descente, ce qui passerait tous les tests ci-dessus."""
    app = CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                            PalierTemoin("Ateliers", "q quitter"),
                            PalierTemoin("Palier Projet", "q quitter")])

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        pilote.app.descendre()
        await pilote.pause()
        return pilote.app.rang, pilote.app.screen.titre

    assert banc(app, scenario) == (2, "Palier Projet")


# ---------------------------------------------------------------------------
# `V2-M2` -- un palier revisite se REPEINT
# ---------------------------------------------------------------------------

def test_le_menu_repeint_ses_compteurs_quand_le_PROJET_a_change(tmp_path, banc):
    """**Le second retour d'Egan** : « j'ai selectionne Projet Demo et meme
    projet tout neuf. A chaque fois j'arrive sur le premier. »

    Mesure sur **le texte peint**, jamais sur `_running` ni sur l'identite des
    enfants : ces trois-la sont vrais des deux cotes du defaut, et c'est
    precisement ce qui a rendu le test d'AC 6.2 vert alors que le defaut etait
    la.

    La cible est le **second** projet, aux compteurs differents du premier.
    """
    premier = _projet(tmp_path, *PROJETS[0])
    second = _projet(tmp_path, *PROJETS[1])
    menu = ecran_ateliers.EcranAteliers(dossier=premier)
    app = CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"), menu],
                   contexte=Contexte(projet=premier.name))

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        avant = _texte(menu)
        pilote.app.action_remonter()
        await pilote.pause()
        # Ce que fait l'ouverture d'un projet : nommer le projet et poser le
        # dossier sur le palier. Les deux, comme le cablage reel.
        menu.dossier = second
        pilote.app.contexte = Contexte(projet=second.name)
        pilote.app.descendre()
        await pilote.pause()
        return avant, _texte(menu)

    avant, apres = banc(app, scenario)
    assert PROJETS[0][0] in avant
    assert PROJETS[1][0] in apres, "le menu a garde le projet precedent"
    assert avant != apres


def test_le_menu_repeint_ses_compteurs_quand_le_MANIFEST_a_change(tmp_path, banc):
    """Second volet, et c'est le cas reel : `reconstruct-project` est la seule
    ecriture du palier Projet, et `EPIC11-ARB-13` ramene precisement ici. Le
    dossier ne change pas -- c'est son contenu qui change."""
    dossier = _projet(tmp_path, "projet_alpha", 1)
    menu = ecran_ateliers.EcranAteliers(dossier=dossier)
    app = CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"), menu])

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        avant = _texte(menu)
        pilote.app.action_remonter()
        await pilote.pause()
        document = json.loads((dossier / "project.json").read_text(encoding="utf-8"))
        document["rushes"] = [{"rush_id": f"r{n}"} for n in range(4)]
        (dossier / "project.json").write_text(json.dumps(document), encoding="utf-8")
        pilote.app.descendre()
        await pilote.pause()
        return avant, _texte(menu), menu.compteurs.rushes

    avant, apres, rushes = banc(app, scenario)
    assert rushes == 4, "le manifest n'a pas ete relu"
    assert "1 rush" in avant and "4 rushes" in apres, (avant, apres)


def test_le_curseur_PEINT_et_la_cible_du_modele_ne_divergent_pas(tmp_path, banc):
    """Meme cause, palier 0, et la consequence y est pire qu'un affichage
    perime : `ouvrir()` reordonne les recents, donc apres un aller-retour la
    ligne montree sous le curseur n'etait plus celle que la validation
    ouvrirait -- ni celle que `Suppr` retirerait.

    Le docstring d'`EcranProjet.ouvrir()` enonce mot pour mot la propriete que
    cette mesure falsifiait.
    """
    premier = _projet(tmp_path, *PROJETS[0])
    second = _projet(tmp_path, *PROJETS[1])
    recents = Recents(tmp_path / "reglages.json")
    recents.noter_ouverture(premier, quand="2026-08-20T10:00:00Z")
    recents.noter_ouverture(second, quand="2026-08-21T10:00:00Z")

    ecran = EcranProjet(recents=recents)
    app = CoqueTui(paliers=[ecran, PalierTemoin("Ateliers", "q quitter")])
    # Ouvrir DESCEND : sans cette couture, on ne quitte jamais le palier 0 et
    # la reprise ne peut pas etre mesuree.
    ecran._ouvrir = lambda chemin: app.descendre()

    async def scenario(pilote):
        await pilote.pause()
        # Ouvrir le SECOND de la liste : la cible n'est pas en premiere
        # position, sans quoi une reordonnance ne se verrait pas.
        ecran.curseur = 1
        vise = ecran.entrees[1].chemin.name
        ecran.ouvrir(ecran.entrees[1].chemin)
        await pilote.pause()
        pilote.app.action_remonter()
        await pilote.pause()
        peint = _texte(ecran).splitlines()
        return vise, peint, ecran.entrees[ecran.curseur].chemin.name

    vise, peint, sous_le_curseur = banc(app, scenario)
    # Le projet qu'on vient d'ouvrir est desormais en tete du MODELE ; il doit
    # l'etre aussi dans ce qui est PEINT.
    lignes_de_projets = [l for l in peint if PROJETS[0][0] in l or PROJETS[1][0] in l]
    assert vise in lignes_de_projets[0], "la liste peinte a garde l'ancien ordre"
    assert sous_le_curseur in {PROJETS[0][0], PROJETS[1][0]}


def test_la_reprise_ne_recompose_PAS_les_enfants(tmp_path, banc):
    """Volet symetrique, et il protege le correctif de la vague 1 bis.

    Repeindre n'est pas recomposer : un palier revisite garde ses widgets --
    c'est ce que la vague 1 bis a gagne apres que `textual` detruisait les
    paliers quittes. Sans cette mesure, « redessiner » pourrait etre implemente
    en reconstruisant l'ecran, et on paierait deux fois la meme regression.
    """
    dossier = _projet(tmp_path, "projet_alpha", 1)
    menu = ecran_ateliers.EcranAteliers(dossier=dossier)
    app = CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"), menu])

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        avant = [id(w) for w in menu.walk_children()]
        pilote.app.action_remonter()
        await pilote.pause()
        pilote.app.descendre()
        await pilote.pause()
        return avant, [id(w) for w in menu.walk_children()], menu._running

    avant, apres, vivant = banc(app, scenario)
    assert avant == apres, "les enfants ont ete recomposes"
    assert vivant is True
