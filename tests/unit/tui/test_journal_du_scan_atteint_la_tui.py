# -*- coding: utf-8 -*-
"""Findings `C3` et `C2-4` -- ce que le coeur DIT pendant un scan arrive a l'ecran.

Les deux couches de la revue de la calibration du 2026-09-06 ont trouve le meme
defaut par deux chemins, et c'est le grief d'origine d'Egan sous une autre
forme : un operateur qui ne saisit rien, sur une feuille dont le libelle porte
une parenthese -- « hp envy 4520 (bureau) » --, obtient un profil nomme par son
`chain_id` et **aucun mot nulle part**.

Le message existait pourtant, et il etait bon : `scan_calibrate.etiquette_du_profil`
avertit du repli de nommage. Ce qui manquait etait le branchement.
`ParcoursScan` construit son couple `(logger, relais)` des que l'appelant n'impose
pas de journal, passe ce logger au coeur -- deux fois, a la detection et a la
calibration -- et ne visait **jamais** le relais. Or `RelaisDeJournal.emit` jette,
par construction, ce qui arrive avant un `viser` : tout ce que le coeur disait
pendant ces deux passes tombait dans le vide.

Ce banc mesure les deux moities du correctif :

* **le comportement**, de bout en bout et sur le vrai fil de travail : la
  fonction du produit qui avertit, le logger du produit, le relais du produit,
  et le journal de l'ecran reellement monte ;
* **la frontiere**, negative : toute passe de ce parcours qui recoit
  `self._logger` vise aussi le relais dans la meme methode. C'est ce volet-la
  qui attrape une TROISIEME passe ajoutee demain sans branchement -- aucun test
  positif ne verrait ce trou-la se rouvrir, et c'est exactement le motif `K3`,
  paye quatre fois dans cet epic.

**Les deux sens du drapeau sont joues** (regle des gardes de mode du
2026-09-06) : un libelle qui peut nommer un fichier ne doit produire AUCUNE
ligne, sans quoi le banc serait vert sur un relais qui deverse n'importe quoi.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility import scan_calibrate
from mixed_media_utility.tui import atelier_scan_calibrate as calib
from mixed_media_utility.tui import atelier_scan_parcours as parcours
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

#: Le libelle qui FAIT replier le nommage. Ce n'est pas une invention du banc :
#: c'est celui que le docstring d'`etiquette_du_profil` cite comme le cas reel
#: -- `payload.validate_scan_chain_label` accepte la parenthese, `slugify_label`
#: la refuse.
LIBELLE_QUI_REPLIE = "hp envy 4520 (bureau)"

#: Son symetrique, qui doit passer sans un mot. Le couple est ce qui fait varier
#: le drapeau : mesurer le seul cas bruyant laisserait vert un relais qui
#: inscrirait tout, y compris ce que l'operateur n'a pas a lire.
LIBELLE_QUI_PASSE = "hp envy 4520 bureau"

CHAIN_ID = "epson-v600-300dpi"


class _Mesure:
    forme, cardinal, octets, dpi, fichiers = "pdf", 3, 1000, 300.0, 1


class _Source:
    mesure = _Mesure()
    forme, cardinal, dpi, fichiers = "pdf", 3, 300.0, 1
    est_multiple = False

    def __init__(self, chemin):
        self.chemin = chemin


def _formulaire_pret(tmp_path: Path) -> calib.FormulaireDeCalibration:
    formulaire = calib.FormulaireDeCalibration()
    formulaire.poser_le_scan(_Source(tmp_path / "mire.pdf"))
    formulaire.dpi = "300"
    return formulaire


def _app(*ecrans) -> CoqueTui:
    return CoqueTui([PalierTemoin("Ateliers", "Q quitter"), *ecrans],
                    Contexte("projet", "Scan"))


@pytest.mark.parametrize("libelle,attendu_bruyant",
                         [(LIBELLE_QUI_REPLIE, True),
                          (LIBELLE_QUI_PASSE, False)])
def test_C3_l_avertissement_du_repli_de_nommage_ARRIVE_dans_le_journal(
    tmp_path: Path, monkeypatch, libelle: str, attendu_bruyant: bool
) -> None:
    """De la fonction du produit jusqu'au journal de l'ecran monte.

    **Le parcours est construit SANS logger**, et c'est la moitie qui compte :
    un logger injecte rend `self._relais` a `None` -- c'est alors le banc qui
    observe, pas l'ecran --, si bien qu'un banc qui en passerait un mesurerait
    le regime ou le defaut n'existe pas. C'est le regime du produit qui est
    joue ici, celui de `mmu-tui`.

    Le seul double est la LECTURE du libelle sur le QR : la regle de nommage,
    elle, reste celle du produit (`slugify_label`, interrogee par
    `etiquette_du_profil`), et le message est le sien mot pour mot.
    """
    monkeypatch.setattr(scan_calibrate, "libelle_de_chaine_du_scan",
                        lambda detection: libelle)

    ecran_formulaire = calib.EcranCalibrerLaChaine(tmp_path,
                                                   calibrer=lambda f: None)
    app = _app(ecran_formulaire)

    def _calibrer(dossier, scan, *, dpi, logger=None,
                  demander_le_nom_et_le_commentaire=None,
                  confirmer_l_ecrasement=None, rappel_progression=None):
        # **La vraie fonction du produit, avec le vrai logger du parcours.**
        # Recopier ici le `logger.warning` mesurerait le banc et non le coeur.
        scan_calibrate.etiquette_du_profil("", object(), CHAIN_ID,
                                           logger=logger)
        raise scan_calibrate.RefusDeCalibration(
            "arret volontaire du banc", motif="PAS_DE_MIRE")

    p = parcours.ParcoursScan(app, tmp_path, calibration=_calibrer)
    p.ecran_de_calibration = ecran_formulaire

    async def scenario(pilote):
        p.lancer_la_passe_de_calibration(_formulaire_pret(tmp_path))
        # Le fil ne part qu'APRES le dessin : une pause avant l'attente, sans
        # quoi il n'y a encore aucun worker a attendre.
        await pilote.pause()
        await pilote.app.workers.wait_for_complete()
        await pilote.pause()
        return list(p._surface_de_la_passe.journal.dernieres(50))

    lignes = banc_pilote(app, scenario)
    replis = [ligne for ligne in lignes if "ne peut" in ligne]
    if attendu_bruyant:
        assert replis, (
            "l'avertissement du repli de nommage doit ARRIVER dans le journal "
            f"de la passe ; lignes vues : {lignes!r}")
        assert LIBELLE_QUI_REPLIE in replis[0]
        assert CHAIN_ID in replis[0], (
            "l'operateur doit lire SOUS QUEL NOM le profil a ete ecrit")
    else:
        assert not replis, (
            "un libelle qui peut nommer un fichier ne produit aucun "
            f"avertissement ; lignes vues : {lignes!r}")


def test_C3_toute_passe_qui_recoit_le_logger_du_parcours_VISE_aussi_son_relais(
) -> None:
    """Frontiere negative -- le motif `K3` ne se rouvre pas en silence.

    Le defaut d'origine n'etait pas une erreur de calcul : c'etait une **ligne
    absente**. Aucun test positif ne voit une ligne absente dans une methode
    qu'il ne joue pas ; seule une frontiere qui compare les deux gestes
    l'attrape.

    La mesure porte sur l'arbre syntaxique et non sur un `grep` : un `grep` de
    `viser` serait vert sur un `viser` pose dans une AUTRE methode que celle
    qui passe le logger, ce qui est precisement l'etat d'avant le correctif --
    le fichier portait un `viser`, et il ne portait pas les bons.
    """
    source = (RACINE / "src" / "mixed_media_utility" / "tui"
              / "atelier_scan_parcours.py")
    arbre = ast.parse(source.read_text(encoding="utf-8"))

    def _passe_le_logger_du_parcours(methode: ast.AST) -> bool:
        for noeud in ast.walk(methode):
            if not isinstance(noeud, ast.Call):
                continue
            for mot in noeud.keywords:
                if mot.arg != "logger":
                    continue
                valeur = mot.value
                if (isinstance(valeur, ast.Attribute)
                        and valeur.attr == "_logger"
                        and isinstance(valeur.value, ast.Name)
                        and valeur.value.id == "self"):
                    return True
        return False

    def _vise_le_relais(methode: ast.AST) -> bool:
        for noeud in ast.walk(methode):
            if not isinstance(noeud, ast.Call):
                continue
            appelee = noeud.func
            if not (isinstance(appelee, ast.Attribute)
                    and appelee.attr == "viser"):
                continue
            cible = appelee.value
            if (isinstance(cible, ast.Attribute) and cible.attr == "_relais"
                    and isinstance(cible.value, ast.Name)
                    and cible.value.id == "self"):
                return True
        return False

    # **Les methodes de classe, et pas `ast.walk`.** Le fil de travail est une
    # fonction imbriquee dans la methode qui le lance : c'est elle qui porte le
    # `logger=self._logger`, et c'est sa methode englobante qui porte le
    # `viser`. Compter les deux separement rendrait le fil « muet » alors que
    # le branchement est fait -- premiere redaction de ce banc, rouge sur du
    # code correct.
    methodes = [membre
                for classe in ast.walk(arbre)
                if isinstance(classe, ast.ClassDef)
                for membre in classe.body
                if isinstance(membre, (ast.FunctionDef, ast.AsyncFunctionDef))]
    donneuses = [m for m in methodes if _passe_le_logger_du_parcours(m)]
    # Le volet symetrique : une frontiere appliquee a un ensemble vide serait
    # verte sans rien mesurer. Les deux passes connues au 2026-09-07 sont la
    # detection et la calibration.
    assert len(donneuses) >= 2, (
        "aucune passe ne recoit plus `self._logger` : la frontiere ne mesure "
        f"plus rien (trouvees : {[m.name for m in donneuses]})")

    muettes = sorted(m.name for m in donneuses if not _vise_le_relais(m))
    assert not muettes, (
        "ces passes donnent le journal du parcours au coeur sans jamais le "
        f"brancher sur un ecran : {muettes}. Tout ce que le coeur y ecrira "
        "sera JETE par `RelaisDeJournal.emit`.")


# --- le pilote, importe du conftest du dossier ------------------------------

from conftest import piloter as banc_pilote   # noqa: E402
