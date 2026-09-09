# -*- coding: utf-8 -*-
"""Demo JETABLE de la vague 1 -- pour juger la story 11.1 a la main.

**Ce fichier n'est pas un livrable et n'est couvert par aucun test.** Il existe
parce que `bin/mmu-tui` nu ne montre que les trois paliers temoins de la story
11.0 : les ecrans de la story 11.1 -- confirmation, execution, interruption,
resultat -- sont ecrits, testes, et **inatteignables au clavier** tant qu'aucun
atelier ne les empile. Les ateliers arrivent en vague 3. Sans ce script, la
moitie de la vague 1 ne se verifie que par la suite de tests.

**Ce qui est reel ici, et c'est l'essentiel :** les ecrans, la grille, les
jetons de couleur, le clavier, le cablage de progression, la ligne d'etat, les
glyphes et tous les refus sont le **code de production**, importe tel quel de
`mixed_media_utility.tui`. Rien n'est reimplemente pour la demo.

**Ce qui est faux, et le reste assume :** les chiffres du panneau sont en dur,
et la tache n'est pas le coeur mais une boucle qui compte des frames
imaginaires (:class:`TacheFactice`). C'est la seule triche, et elle ne porte
sur rien de ce qu'on demande de juger -- le canal de progression traverse, lui,
le vrai `SurfaceExecution` et le vrai `EmetteurProgression` du coeur.

Lancer, depuis n'importe ou :

    python _bmad-output/planning-artifacts/ux-designs/ux-tui-2026-08-27/demo_vague_1.py

Options : `--ascii` (repli sans Unicode), `--sans-couleur` (ou `NO_COLOR` dans
l'environnement).
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path

# `src/` sur le chemin d'import sans rien installer -- meme geste que
# `bin/mmu-tui`, calcule depuis la position de CE fichier et jamais depuis le
# repertoire courant.
_DEPOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_DEPOT / "src"))

from textual.widgets import Static  # noqa: E402

from mixed_media_utility.tui.coque import (  # noqa: E402
    Contexte, CoqueTui, EcranPasEncore, Palier, PalierTemoin)
from mixed_media_utility.tui.execution import (  # noqa: E402
    EcranExecution, EcranResultat, PanneauConfirmation, SurfaceExecution)
from mixed_media_utility.tui.noms import ModeleNoms, NomEditable  # noqa: E402
from mixed_media_utility.tui.panneau import (  # noqa: E402
    ChoixExclusif, Issue, LigneChiffree, Panneau)

#: Assez de frames pour que la barre bouge lisiblement, assez peu pour que la
#: demo tienne une minute. C'est l'ordre de grandeur d'un rush reel du depot.
TOTAL = 6300


def panneau_de_confirmation() -> Panneau:
    """Le motif chiffre de `DESIGN.md` 7.4, avec des chiffres plausibles.

    **Deux lignes portent la mention `(majorant)`** : c'est ce que l'ecran de
    resultat n'a plus le droit de porter, et le contraste entre les deux ecrans
    est une des choses a regarder.
    """
    return Panneau(
        "A ecrire",
        [
            LigneChiffree("Rush", "TEST_FILE_12p5"),
            LigneChiffree("Frames a extraire", TOTAL, "frames", majorant=True),
            LigneChiffree("Cadence de lecture", "12,5", "i/s"),
            LigneChiffree("Espace disque requis", "4,2", "Go", majorant=True),
            LigneChiffree("Fenetre", "00:00:00:00 -> 00:08:24:00"),
        ],
    )


def modele_de_noms() -> ModeleNoms:
    """Deux noms DISTINCTS, dont un deja invalide.

    Deux, parce qu'un modele a un seul nom rendrait `↑↓` et la validation
    d'ensemble inobservables (regle des fabriques de `CLAUDE.md`). Et le second
    est **deja refuse des le depart**, pour que le refus soit visible sans rien
    taper : son glyphe, sa couleur `state-absent`, et l'action principale qui
    reste bloquee tant qu'il l'est.

    Le nom refuse porte des espaces et une barre oblique -- ce qu'un operateur
    ecrit spontanement (« lot b 25 i/s ») et que le schema du manifeste refuse.
    Une valeur **vide** n'aurait rien montre : `NomEditable` remplace une valeur
    vide par le nom conventionnel a la construction, ce qui est le bon
    comportement et rend le nom valide.
    """
    return ModeleNoms(noms=[
        NomEditable("test_file_12p5_lot_a_12i5", "test_file_12p5_lot_a_12i5"),
        NomEditable("test_file_12p5_lot_b_25i0", "lot b 25 i/s"),
    ])


class TacheFactice:
    """La SEULE triche : une boucle qui compte, a la place du coeur.

    Elle recoit le vrai `EmetteurProgression` et lui emet ses jalons, donc tout
    ce qui est en aval -- estimateur de temps restant, journal, ligne d'etat,
    barre -- est exerce exactement comme il le sera par une extraction reelle.
    """

    def __init__(self, surface: SurfaceExecution, ecran: EcranExecution) -> None:
        self.surface = surface
        self.ecran = ecran
        self.arretee = threading.Event()

    def lancer(self) -> None:
        threading.Thread(target=self._boucler, daemon=True).start()

    def _boucler(self) -> None:
        emetteur = self.surface.emetteur(TOTAL)
        faites = 0
        while faites < TOTAL and not self.arretee.is_set():
            time.sleep(0.05)
            faites = min(faites + 90, TOTAL)
            # `call_from_thread` : textual n'est pas thread-safe, et le coeur
            # reel emettra depuis le thread de la tache lui aussi.
            self.ecran.app.call_from_thread(emetteur.emettre, faites)
        if not self.arretee.is_set():
            self.ecran.app.call_from_thread(self._finir)

    def _finir(self) -> None:
        """Fin nominale : le resultat s'empile, et les drapeaux s'eteignent."""
        self.ecran.app.oublier_la_tache()
        self.ecran.app.descendre(EcranResultat(
            Panneau("Ecrit", [
                LigneChiffree("Frames extraites", TOTAL, "frames"),
                LigneChiffree("Lots ecrits", 2, "lots"),
                LigneChiffree("Espace occupe", "4,1", "Go"),
            ]),
            suites=["Scanner les planches de ce rush",
                    "Encoder un master depuis ces frames"]))


class PalierDemo(Palier):
    """Le point de depart : une ligne qui dit quoi faire, et `⏎` qui y va."""

    titre = "Extraction"
    raccourcis = "⏎ preparer l'extraction   Échap ateliers   q quitter"

    def contenu(self) -> list[Static]:
        return [Static(
            "Demo de la vague 1 : les ecrans sont le code de production,\n"
            "seuls les chiffres et la tache sont factices.\n\n"
            "  ⏎   ouvrir l'ecran de confirmation", classes="temoin")]

    def on_mount(self) -> None:
        # Pas de `super()` : `Palier` ne definit pas `on_mount`.
        self.poser_etat("Rien n'a encore ete ecrit.")

    def on_key(self, evenement) -> None:
        if evenement.key == "enter":
            evenement.stop()
            self.app.descendre(ecran_de_confirmation())


def ecran_de_confirmation() -> PanneauConfirmation:
    """`E2-3` -- trois issues, aucune preselectionnee, une seule qui ecrit."""
    ecran = PanneauConfirmation(
        panneau_de_confirmation(),
        ChoixExclusif([
            Issue("extraire", "Extraire les 2 lots", ecrit=True),
            Issue("cadence", "Corriger la cadence de lecture"),
            Issue("annuler", "Annuler, ne rien ecrire"),
        ]),
        noms=modele_de_noms(),
    )
    ecran._sur_issue = lambda issue: _suite_de_la_confirmation(ecran, issue)
    return ecran


def _suite_de_la_confirmation(ecran: PanneauConfirmation, issue: Issue) -> None:
    """Ce qu'un atelier de la vague 3 fera : router l'issue retenue.

    « Annuler » revient aux ateliers -- c'est son sens. Mais « Corriger la
    cadence » **mene a l'ecran « pas encore »** plutot que de ramener aux
    ateliers : Egan l'a lue comme inerte le 2026-08-28, et il avait raison de le
    faire -- une issue qui ramene en arriere sans rien dire est indistinguable
    d'une issue qui ne marche pas.
    """
    if issue.cle == "cadence":
        ecran.app.descendre(EcranPasEncore(
            "Corriger la cadence de lecture",
            ecran.app.QUAND_ARRIVENT_LES_ATELIERS))
        return
    if issue.cle != "extraire":
        ecran.app.revenir_aux_ateliers()
        return
    surface = SurfaceExecution(unite="frames")
    execution = EcranExecution(
        surface, titre_tache="Extraction de TEST_FILE_12p5 -- 2 lots",
        sur_issue=lambda _issue: ecran.app.revenir_aux_ateliers())
    ecran.app.descendre(execution)
    # `call_later` : la tache ne demarre qu'une fois l'ecran reellement monte,
    # `push_screen` etant differe.
    ecran.app.call_later(lambda: TacheFactice(surface, execution).lancer())


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(prog="demo_vague_1")
    analyseur.add_argument("--ascii", dest="ascii_seul", action="store_true")
    analyseur.add_argument("--sans-couleur", dest="sans_couleur",
                           action="store_true",
                           default="NO_COLOR" in os.environ)
    options = analyseur.parse_args(argv)
    CoqueTui(
        paliers=[
            PalierTemoin("Projet", "⏎ ouvrir   q quitter", "Projet"),
            PalierTemoin("Ateliers", "⏎ entrer   Échap projet   q quitter",
                         "Ateliers"),
            PalierDemo(),
        ],
        contexte=Contexte(projet="projet_demo", objet="TEST_FILE_12p5"),
        sans_couleur=options.sans_couleur,
        ascii_seul=options.ascii_seul,
    ).run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
