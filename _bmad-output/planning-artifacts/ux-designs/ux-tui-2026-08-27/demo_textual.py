# -*- coding: utf-8 -*-
"""Demo JETABLE de la TUI sous `textual` -- a juger dans un vrai terminal.

**Ceci n'est pas le squelette de la story 11.0** (`EPIC11-ARB-15`). C'est une
maquette vivante, qui triche partout ou tricher ne change pas ce qu'Egan doit
juger : donnees en dur, aucun appel au coeur, aucun test. Ce qu'elle montre
fidelement, et qui est la seule chose qu'on lui demande :

* ce que `textual` **rend vraiment** -- bordures, focus, couleurs, animation --
  la ou un rejeu de mes maquettes ASCII ne montrerait que mon ASCII ;
* les **jetons de couleur herites de la GUI** poses sur du texte reel ;
* la **grille 80x24** tenue par de vrais widgets et non par du texte pre-calcule.

Lancer : `python demo_textual.py`   ·   `q` quitte, `←` `→` changent d'ecran.

Si le rendu ne convient pas, c'est le **framework** qu'on rouvre, pas la story.
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static

# --- Jetons, recopies de DESIGN.md section 5. Dans la story 11.0 ils seront
# --- IMPORTES du module de jetons de la GUI, jamais redefinis ici.
COMPLETE = "#4EC57A"
SUBSTITUT = "#F5A623"
ABSENT = "#EE878A"
ACCENT = "#8FAEF7"
DATA = "#E8E8E8"
MUTED = "#9A9A9A"

CSS = f"""
Screen {{ layout: vertical; }}

#bandeau {{
    height: 1; padding: 0 1;
    color: {DATA};
    border-bottom: solid {MUTED};
}}
#centre  {{ height: 1fr; padding: 1 2; }}
#etat    {{ height: 1; padding: 0 1; color: {MUTED}; border-top: solid {MUTED}; }}
#pied    {{ height: 1; padding: 0 1; color: {MUTED}; }}

.titre    {{ color: {DATA}; text-style: bold; margin-bottom: 1; }}
.curseur  {{ color: {ACCENT}; text-style: bold; }}
.ligne    {{ color: {DATA}; }}
.discret  {{ color: {MUTED}; }}
.complet  {{ color: {COMPLETE}; }}
.reserve  {{ color: {SUBSTITUT}; }}
.absent   {{ color: {ABSENT}; }}

#cartouche {{
    border: round {MUTED};
    padding: 0 1;
    margin: 1 0;
    height: auto;
}}
#barre {{ color: {ACCENT}; }}
"""


class Ecran(Vertical):
    """Un ecran de la demo : bandeau, centre, ligne d'etat, raccourcis."""

    def __init__(self, bandeau: str, droite: str, etat: str, pied: str) -> None:
        super().__init__()
        self._bandeau, self._droite = bandeau, droite
        self._etat, self._pied = etat, pied

    def compose(self) -> ComposeResult:
        largeur = 78 - len(self._bandeau) - len(self._droite)
        yield Static(self._bandeau + " " * max(1, largeur) + self._droite, id="bandeau")
        yield Vertical(*self.corps(), id="centre")
        yield Static(self._etat, id="etat")
        yield Static(self._pied, id="pied")

    def corps(self) -> list[Static]:
        return []


class MenuAteliers(Ecran):
    """E1-1 -- le menu des ateliers, avec sa derniere ecriture en pied."""

    def __init__(self) -> None:
        super().__init__(
            "mmu · projet_demo · Ateliers", "3 rushes · 5 lots · 2 masters",
            "",
            "⏎ entrer   ↑↓ naviguer   → écran suivant   q quitter",
        )

    def corps(self) -> list[Static]:
        entrees = [
            ("Extraction", "Ouvrir un rush, borner, choisir les cadences, extraire"),
            ("Scan", "Déposer des scans, détecter, puis écrire les TIFF"),
            ("Pdf", "Composer et générer les planches d'un ou plusieurs lots"),
            ("Exports", "Encoder un master depuis un lot reconstruit"),
        ]
        lignes = [Static("Que faire dans projet_demo ?", classes="titre")]
        for i, (nom, quoi) in enumerate(entrees):
            marque = "▸ " if i == 0 else "  "
            classe = "curseur" if i == 0 else "ligne"
            lignes.append(Static(f"{marque}{nom:<12}", classes=classe))
            lignes[-1].tooltip = quoi
        lignes.append(Static(""))
        lignes.append(Static("  Projet       Profil de calibration par défaut, reconstruction",
                             classes="discret"))
        lignes.append(Static(""))
        lignes.append(Static("  Dernière écriture   26/08 14:32 · lot_25fps · 124 frames  ● ok",
                             classes="discret"))
        return lignes


class Cadences(Ecran):
    """E2-2 -- la liste cochable qui a remplace le champ texte `25 ; 12,5`."""

    def __init__(self) -> None:
        super().__init__(
            "mmu · projet_demo · Extraction", "temps 1 sur 2 · prévisualiser",
            "Prévisualiser n'écrit rien : c'est une lecture, pas une extraction.",
            "Espace cocher   a ajouter   ⏎ prévisualiser   ← → écran   q quitter",
        )

    def corps(self) -> list[Static]:
        lignes = [Static("Quelles cadences regarder ?", classes="titre")]
        rangs = [
            (True, "25", "source", "124 frames", True),
            (True, "12,5", "source / 2", "62 frames", False),
            (False, "8,333", "source / 3", "42 frames", False),
            (False, "6,25", "source / 4", "31 frames", False),
            (True, "10", "ajoutée", "50 frames", False),
        ]
        for coche, cadence, origine, frames, curseur in rangs:
            case = "[x]" if coche else "[ ]"
            marque = "▸ " if curseur else "  "
            lignes.append(Static(
                f"{marque}{case} {cadence:<8} {origine:<14} {frames}",
                classes="curseur" if curseur else ("ligne" if coche else "discret"),
            ))
        lignes.append(Static(""))
        lignes.append(Static("  3 cadences cochées", classes="discret"))
        return lignes


class Confirmation(Ecran):
    """E2-3 -- le point de jugement : le seul ecran chiffre avant ecriture."""

    def __init__(self) -> None:
        super().__init__(
            "mmu · projet_demo · Extraction", "rush_01 · 25 fps · 4:12",
            "Rien n'a encore été écrit. ↑↓ pour choisir, Entrée pour valider.",
            "⏎ valider   e éditer les noms   ← → écran   q quitter",
        )

    def corps(self) -> list[Static]:
        cartouche = Vertical(
            Static("Lots créés               2", classes="ligne"),
            Static("Frames écrites           124  +  62        =  186", classes="ligne"),
            Static("Bornes                   00:00:04:12 → 00:00:09:08", classes="ligne"),
            Static("Espace disque            ~ 3,1 Go            (majorant)", classes="ligne"),
            Static(""),
            Static("Noms produits          > projet_demo_rush_01_25fps", classes="curseur"),
            Static("                         projet_demo_rush_01_12p5", classes="ligne"),
            id="cartouche",
        )
        cartouche.border_title = "À écrire"
        return [
            Static("", classes="titre"),
            cartouche,
            Static("  ( ) Extraire      ( ) Modifier      ( ) Annuler", classes="ligne"),
        ]


class Execution(Ecran):
    """E2-4 -- la seule chose animee de la demo : la barre et son temps restant."""

    faites = reactive(0)

    def __init__(self) -> None:
        super().__init__(
            "mmu · projet_demo · Extraction", "rush_01 · 25 fps · 4:12",
            "",
            "Tab journal   Échap interrompre   ← → écran   q quitter",
        )
        self.total = 124

    def corps(self) -> list[Static]:
        self._journal = Static("", classes="discret")
        return [
            Static("Extraction en cours — lot 1 sur 2", classes="titre"),
            Static("  projet_demo_rush_01_25fps                    en cours", classes="ligne"),
            Static("  projet_demo_rush_01_12p5                     en attente",
                   classes="discret"),
            Static(""),
            Static("  ── Journal " + "─" * 55, classes="discret"),
            self._journal,
        ]

    def on_mount(self) -> None:
        self.set_interval(0.08, self._avancer)

    def _avancer(self) -> None:
        self.faites = (self.faites + 1) % (self.total + 1)

    def watch_faites(self, valeur: int) -> None:
        pleine, part = 36, valeur / self.total
        pleins = round(part * pleine)
        barre = "▓" * pleins + "░" * (pleine - pleins)
        # `EPIC7-ARB-67` : aucun temps restant tant qu'aucune mesure n'existe.
        reste = "" if valeur < 5 else f"  reste ~ {round((self.total - valeur) * 0.6)} s"
        try:
            self.query_one("#etat", Static).update(
                f"{barre}  {part * 100:.0f} %  {valeur}/{self.total} frames{reste}")
            self._journal.update(
                f"  14:31:19  frame {valeur:06d} écrite\n"
                f"  14:31:04  écriture sous frames/projet_demo_rush_01_25fps/")
        except Exception:
            pass


class Demo(App):
    CSS = CSS
    BINDINGS = [("q", "quit", "Quitter"), ("right", "suivant", "Suivant"),
                ("left", "precedent", "Précédent")]

    ECRANS = (MenuAteliers, Cadences, Confirmation, Execution)

    def __init__(self) -> None:
        super().__init__()
        self.rang = 0

    def compose(self) -> ComposeResult:
        yield self.ECRANS[self.rang]()

    def _rejouer(self) -> None:
        self.query("Ecran").remove()
        self.mount(self.ECRANS[self.rang]())

    def action_suivant(self) -> None:
        self.rang = (self.rang + 1) % len(self.ECRANS)
        self._rejouer()

    def action_precedent(self) -> None:
        self.rang = (self.rang - 1) % len(self.ECRANS)
        self._rejouer()


if __name__ == "__main__":
    Demo().run()
