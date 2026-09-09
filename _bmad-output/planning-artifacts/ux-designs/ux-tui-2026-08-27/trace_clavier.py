# -*- coding: utf-8 -*-
"""Sonde JETABLE : journalise chaque touche recue par la TUI, dans un fichier.

**Pourquoi elle existe.** Egan mesure, dans un vrai terminal, qu'apres un
aller-retour complet (`⏎` `⏎` `Échap` `Échap`) les touches cessent d'agir et que
seul `q` repond encore ; et plus generalement qu'il faut souvent appuyer deux
fois. **Le pilote headless ne reproduit rien** : cinq cycles, avec et sans
franchissement du plancher, avec et sans redimensionnement, tous corrects. Or le
pilote **injecte les evenements de touche directement** et court-circuite le
pilote de terminal -- c'est-a-dire exactement la couche ou le defaut se trouve.

Cette sonde comble l'ecart : elle journalise, sur la TUI reelle et dans un vrai
terminal, **tout** ce que l'application recoit, avec l'horodatage. On saura alors
laquelle des deux hypotheses est la bonne :

* la touche **n'arrive jamais** -- le pilote de terminal l'avale ou la parse
  comme le debut d'une sequence d'echappement (ce que « une suite de touches
  est attendue » decrit exactement) ;
* la touche **arrive et l'ecran ne la traite pas** -- et c'est alors notre code.

Lancer :

    python _bmad-output\\planning-artifacts\\ux-designs\\ux-tui-2026-08-27\\trace_clavier.py

Faire le parcours qui bloque, puis quitter par `q` (ou `Ctrl+C` si `q` ne repond
plus). Le journal est ecrit a cote de ce fichier, dans `trace_clavier.log`.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_DEPOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_DEPOT / "src"))

from mixed_media_utility.tui.coque import CoqueTui  # noqa: E402

JOURNAL = Path(__file__).with_name("trace_clavier.log")


def brancher_le_parseur(tracer) -> None:
    """Journalise les caracteres BRUTS que le terminal envoie au parseur.

    **C'est la reserve d'Egan qui exige ceci.** Il a observe le meme blocage
    en attendant bien plus que la fenetre de 100 ms, ce que le mecanisme de
    collision `Echap` + touche n'explique pas. Journaliser les touches
    *reconnues* ne suffit donc pas : il faut voir ce qui **entre**, pour
    trancher entre trois etats que rien d'autre ne distingue :

    * le caractere n'apparait nulle part -- la touche n'est jamais sortie de
      la console, et ni `textual` ni nous n'y pouvons rien ;
    * il apparait en entree mais aucune touche n'en sort -- le parseur la
      retient ou la fond dans une sequence ;
    * la touche sort et l'ecran ne bouge pas -- le defaut est chez nous.
    """
    from textual import _xterm_parser

    original = _xterm_parser.XTermParser.feed

    def feed_trace(self, donnees):
        if donnees:
            tracer("ENTREE BRUTE", repr(donnees))
        return original(self, donnees)

    _xterm_parser.XTermParser.feed = feed_trace


class CoqueTracee(CoqueTui):
    """La coque reelle, plus un journal de tout evenement d'entree.

    On intercepte au niveau de `on_event`, **avant** tout routage : c'est le
    seul point ou l'on voit ce que l'application recoit vraiment, y compris les
    evenements que le routage jetterait ensuite.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._depart = time.monotonic()
        self._lignes: list[str] = []

    def _tracer(self, categorie: str, detail: str) -> None:
        self._lignes.append("%8.3f s  %-14s %s"
                            % (time.monotonic() - self._depart, categorie, detail))

    async def on_event(self, evenement) -> None:
        nom = type(evenement).__name__
        if nom == "Key":
            self._tracer("TOUCHE", "key=%-12r character=%-8r aliases=%s  "
                                   "ecran=%s rang=%s"
                         % (evenement.key, getattr(evenement, "character", None),
                            getattr(evenement, "aliases", None),
                            type(self.screen).__name__, self.rang))
        elif nom in ("Resize", "Focus", "Blur", "AppFocus", "AppBlur",
                     "ScreenResume", "ScreenSuspend", "Paste"):
            self._tracer(nom.upper(), str(getattr(evenement, "size", "")))
        await super().on_event(evenement)

    def _ecrire(self) -> None:
        entete = [
            "Trace clavier de la TUI -- %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
            "Terminal : %s colonnes x %s lignes" % (self.size.width,
                                                    self.size.height),
            "",
            "Deux niveaux, et c'est leur ECART qui dit ou est le defaut :",
            "",
            "  ENTREE BRUTE   ce que le terminal envoie au parseur, octet pour",
            "                 octet. Absent => la touche n'est jamais sortie de",
            "                 la console.",
            "  TOUCHE         ce que le parseur en a fait, AVANT normalisation.",
            "                 Une entree brute sans touche => le parseur l'a",
            "                 retenue ou fondue dans une sequence.",
            "                 Une touche sans changement de rang => c'est nous.",
            "",
        ]
        JOURNAL.write_text("\n".join(entete + self._lignes), encoding="utf-8")


def main() -> int:
    application = CoqueTracee()
    brancher_le_parseur(application._tracer)
    try:
        application.run()
    finally:
        application._ecrire()
        print("Journal ecrit : %s" % JOURNAL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
