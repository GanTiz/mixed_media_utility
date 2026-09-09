# -*- coding: utf-8 -*-
"""Interface en terminal de mixed_media_utility (Epic 11).

Elle **heberge le coeur en processus** (`EPIC11-ARB-1`) : aucun sous-processus,
aucun appel a la CLI. La CLI reste par ailleurs un livrable maintenu -- les deux
surfaces appellent les memes fonctions, jamais l'une l'autre.

Contrat visuel et comportemental : `_bmad-output/planning-artifacts/ux-designs/
ux-tui-2026-08-27/` (`DESIGN.md` pour la grammaire, `EXPERIENCE.md` pour les 46
ecrans).
"""
from .coque import Contexte, CoqueTui, Palier, PalierTemoin, paliers_temoins

__all__ = ["Contexte", "CoqueTui", "Palier", "PalierTemoin", "paliers_temoins"]
