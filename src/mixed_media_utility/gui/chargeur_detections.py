# -*- coding: utf-8 -*-
"""Lecture des documents de detection ecrits sur le disque (story 7.3, AC 4).

**Pourquoi ce module existe.** Aucun module de la GUI ne lisait un document
de detection : `modele_chutier.construire_arbre` les **recoit** en parametre.
Or la completude d'un lot detecte doit survivre a la fermeture de
l'application (FR7, `EPIC7-ARB-49`) : elle vit dans le document de 5.25, sur
le disque, et **jamais en session**. Rouvrir le projet, c'est relire ce
dossier -- il n'y a pas d'autre source.

**Ce module LIT, il n'ecrit rien et ne juge rien** : il enumere
`scans/<slug>/detections/*.json` dans un ordre **deterministe**, relit chaque
document par le lecteur normatif de 5.26
(`scan_previz.scan_previz_from_json_dict`) et **nomme** ceux qu'il n'a pas su
relire plutot que de les avaler. Il relit aussi le **rapport de tri** de 5.24
(`scans/<slug>/tri.json`) par son lecteur a lui
(`scan_sorting.rapport_from_json_dict`) : c'est de la, et de nulle part
ailleurs, que vient ce qui n'a ete rattache a aucun lot.

Aucune regle de rattachement n'est rejouee ici. L'interface **montre** ce que
le coeur a range (`EPIC7-ARB-64`, AC 8c).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .. import scan_detect, scan_previz, scan_sorting
from ..io import project_layout


@dataclass(frozen=True)
class DocumentIllisible:
    """Un fichier du dossier de detection que le lecteur normatif a refuse.

    Il est **nomme** -- chemin et motif verbatim du lecteur --, jamais avale :
    un document qui disparait en silence est exactement ce qui fait croire a
    une completude qu'aucune source ne porte.
    """

    chemin: Path
    motif: str


@dataclass(frozen=True)
class ResultatDeChargement:
    """Ce qui a ete relu, et ce qui a resiste."""

    documents: tuple = ()
    illisibles: tuple[DocumentIllisible, ...] = field(default_factory=tuple)

    def __bool__(self) -> bool:
        return bool(self.documents)


def chemins_de_documents(project_dir) -> tuple[Path, ...]:
    """Les documents de detection du projet, dans un ordre DETERMINISTE.

    L'ordre est celui du couple `(slug d'ingestion, nom de fichier)`, et il
    est trie explicitement : `Path.glob` ne promet aucun ordre, et un ordre
    qui depend du systeme de fichiers rend l'arbre du chutier different d'une
    machine a l'autre pour les memes donnees.
    """
    scans = Path(project_dir) / project_layout.SCANS_DIRNAME
    if not scans.is_dir():
        return ()
    trouves = []
    for dossier in sorted(scans.iterdir(), key=lambda chemin: chemin.name):
        detections = dossier / scan_detect.DETECTIONS_DIRNAME
        if not detections.is_dir():
            continue
        trouves.extend(
            sorted(detections.glob("*.json"), key=lambda chemin: chemin.name))
    return tuple(trouves)


def charger_ces_documents(chemins) -> ResultatDeChargement:
    """Relire des documents nommes, dans l'ordre donne."""
    documents = []
    illisibles = []
    for chemin in chemins:
        chemin = Path(chemin)
        try:
            brut = json.loads(chemin.read_text(encoding="utf-8"))
            documents.append(scan_previz.scan_previz_from_json_dict(brut))
        except (OSError, ValueError, scan_previz.ScanPrevizError) as erreur:
            # Le motif est celui du lecteur, VERBATIM (P9) : ni traduit, ni
            # reformule. `json.JSONDecodeError` derive de `ValueError`.
            illisibles.append(DocumentIllisible(chemin=chemin, motif=str(erreur)))
    return ResultatDeChargement(
        documents=tuple(documents), illisibles=tuple(illisibles))


def charger(project_dir) -> ResultatDeChargement:
    """Relire **tous** les documents de detection du projet."""
    return charger_ces_documents(chemins_de_documents(project_dir))


def chemin_du_rapport_de_tri(project_dir, ingest_slug) -> Path:
    """Le chemin du rapport de tri d'une passe : `scans/<slug>/tri.json`."""
    return (Path(project_dir) / project_layout.SCANS_DIRNAME / str(ingest_slug)
            / scan_detect.TRI_DOCUMENT_FILENAME)


def charger_le_rapport_de_tri(project_dir, ingest_slug):
    """Relire le rapport de tri d'une passe, ou `None` s'il n'y en a pas.

    Rendu tel que `scan_sorting.rapport_from_json_dict` le rend : ce module ne
    recompose aucune de ses quatre classes et n'en derive aucune regle. Un
    rapport present mais illisible **leve** -- l'avaler ferait annoncer « rien
    au reliquat » a une passe qui en a produit.
    """
    chemin = chemin_du_rapport_de_tri(project_dir, ingest_slug)
    if not chemin.is_file():
        return None
    return scan_sorting.rapport_from_json_dict(
        json.loads(chemin.read_text(encoding="utf-8")))
