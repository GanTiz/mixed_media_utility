# -*- coding: utf-8 -*-
"""Creation et lecture d'un dossier de projet, pour l'ecran de gestion
(story 7.1, AC 1 / AC 4 / AC 5).

**L'interface ne redefinit aucune regle du coeur.** Ce module est la seule
couture entre la surface et `io/` : il ecrit ce que le coeur accepte, il
lit ce que le coeur valide, et il refuse exactement ce que le coeur refuse.
Trois consequences directes, chacune portee par une AC :

* la creation **cree elle-meme le dossier de projet** sous le dossier de
  destination designe -- ``<parent>/<nom saisi>`` -- puis y ecrit
  ``project.json`` a la racine (`EPIC7-ARB-82`, essai de terrain du
  2026-08-27 : « l'outil cree lui-meme ce dossier et le peuple »). Ce qui
  nait sous le dossier designe porte le **nom du projet saisi par
  l'operatrice**, jamais le nom de l'outil : `EPIC7-ARB-28` pt 1 tient ;
* l'arborescence de travail qu'il porte est celle du **coeur**, posee par
  ``io.project_layout.ensure_project_layout``. Aucune seconde liste de
  dossiers n'est ecrite ici : ce module ne redefinit aucune regle du coeur,
  et une arborescence est une regle du coeur ;
* l'ecriture passe par l'ecriture atomique du coeur
  (``io.extraction_manifest._atomic_write``), qui VALIDE un temporaire
  avant de le mettre en place : un document que le coeur refuserait ne
  peut donc pas atterrir sur le disque ;
* la lecture rend le **motif verbatim** de l'exception levee par le coeur
  -- fichier absent, JSON corrompu, version de schema inconnue -- sans
  jamais le paraphraser ni le traduire (`EXPERIENCE.md`, Voice and Tone :
  une maquette qui ecrivait ``LOT_INCOMPLET`` la ou le coeur ecrit
  ``LOT_INCOMPLETE`` a deja coute une divergence a ce depot).

Ce module ne fusionne **jamais** deux projets : il n'appelle aucune garde
de conflit de manifeste, et l'identifiant d'un projet importe est lu tel
quel, jamais recalcule (AC 5, `EPIC7-ARB-60`). Un grep de frontiere le
mesure sur tout ``gui/``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jsonschema.exceptions import ValidationError

from ..io.extraction_manifest import (
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
    _atomic_write,
)
from ..io.manifest import validate_manifest
from ..io.naming import NamingError, normalize_identifier
from ..io.project_layout import ensure_project_layout
from .modele_projets import LigneProjet

#: Nom du fichier de projet, lu du coeur -- jamais un litteral de la GUI.
NOM_FICHIER_PROJET = MANIFEST_FILENAME


class ProjetExistantError(Exception):
    """Le dossier designe porte deja un fichier de projet.

    La creation le refuse au lieu de l'ecraser : « aucun ecrasement
    destructeur sans avertissement » (`EXPERIENCE.md`, Interaction
    Primitives). Il n'y a volontairement **aucune modale d'ecrasement**
    ici -- le cas nominal de ce dossier-la, c'est « ouvrir ».
    """


def _horodatage_utc() -> str:
    """Horodatage RFC3339 UTC, meme forme que celle qu'ecrit le coeur."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def manifeste_minimal(identifiant_projet: str, *, cree_le: str | None = None) -> dict:
    """Le document qu'ecrit la creation : un projet valide, et vide.

    Les huit cles requises par le contrat v2.1, les quatre objets dans leur
    forme minimale. Les deux listes sont vides -- ce que le coeur accepte
    depuis la Task 1 de cette meme story (``minItems`` relache de 1 a 0).
    """
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "project_id": identifiant_projet,
        "created": cree_le or _horodatage_utc(),
        "rushes": [],
        "lots": [],
        "artifacts": {},
        "color": {},
        "video": {},
        "reconstruction": {},
    }


def identifiant_depuis_le_dossier(dossier) -> str:
    """Deriver l'identifiant de projet du NOM du dossier designe.

    Passe par le helper generique du coeur (``io.naming``, precedent de la
    story 3.4) : NFKD, restriction au jeu autorise par le schema,
    raccourcissement au-dela de la longueur canonique. Aucune seconde
    normalisation n'est ecrite ici -- une convention, une implementation.
    """
    return normalize_identifier(Path(dossier).name, label="le nom du dossier de projet")


def dossier_cible(dossier_parent, nom) -> Path:
    """Le dossier de projet a creer : ``<dossier_parent>/<nom>``, et rien d'autre.

    C'est aussi ce que l'apercu de la surface de creation affiche : une
    seule fonction calcule le chemin annonce et le chemin cree, sans quoi
    l'apercu pourrait mentir sur ce qui va naitre.

    Le champ de saisie porte un **nom**, pas un chemin. Un nom qui contient
    un separateur, qui se reduit a ``.`` ou ``..``, ou qui est absolu,
    designerait un autre dossier que celui de l'apercu : ces formes sont
    refusees par ``NamingError``, la meme exception que le coeur leve sur un
    nom dont il ne peut tirer aucun identifiant -- donc la meme phrase de
    refus cote surface. Ce n'est **pas** une seconde normalisation de nom :
    c'est le refus d'interpreter un champ de nom comme un chemin.
    """
    # Windows retire les espaces ET les points de fin d'un nom de dossier :
    # `mon_projet.` devient `mon_projet` a la creation. Ne retirer que les
    # espaces faisait donc mentir l'apercu sur le nom exact du dossier qui
    # allait naitre -- le defaut que cette fonction existe pour empecher
    # (mesure du 2026-08-27). Le retrait est fait sur les DEUX plateformes :
    # l'apercu doit annoncer le meme nom partout, et un nom a point final n'a
    # aucun sens de toute facon.
    texte = str(nom).strip().rstrip(". ")
    if (
        not texte
        or texte in (".", "..")
        or "/" in texte
        or "\\" in texte
        or Path(texte).is_absolute()
    ):
        raise NamingError(
            f"Impossible de creer le projet : {nom!r} est un chemin, pas un "
            "nom de projet."
        )
    return Path(dossier_parent) / texte


def creer_projet(dossier_parent, nom) -> LigneProjet:
    """Creer ``<dossier_parent>/<nom>``, l'arborescence du coeur, et le projet.

    L'operatrice designe le dossier qui **contiendra** le projet et saisit
    son nom ; l'outil fabrique le dossier de projet lui-meme
    (`EPIC7-ARB-82`). Il n'y a plus de dossier a preparer a la main hors de
    l'outil avant de l'ouvrir.

    Trois refus, dans cet ordre, et **aucun** d'eux ne laisse quoi que ce
    soit sur le disque :

    * ``NamingError`` quand ``nom`` est un chemin plutot qu'un nom
      (:func:`dossier_cible`) ;
    * ``ProjetExistantError`` quand le dossier cible existe deja et porte un
      fichier de projet -- « aucun ecrasement destructeur sans avertissement »
      (`EXPERIENCE.md`). Le geste nominal sur ce dossier-la, c'est « ouvrir » ;
    * ``NamingError`` quand le nom ne donne aucun identifiant conforme au
      schema (un nom fait de caracteres tous interdits, ``###``). Ce refus
      est mesure AVANT le premier ``mkdir`` : un nom refuse ne doit pas
      laisser un dossier vide derriere lui.
    """
    dossier = dossier_cible(dossier_parent, nom)
    chemin_projet = dossier / NOM_FICHIER_PROJET
    if chemin_projet.exists():
        raise ProjetExistantError(
            f"{dossier} porte deja un {NOM_FICHIER_PROJET} : la creation ne "
            "l'ecrase pas. Ouvrir ce dossier plutot que le creer."
        )

    # L'identifiant se derive AVANT tout ecrit : voir le troisieme refus
    # ci-dessus. L'ordre de ces deux lignes est le contrat.
    identifiant = identifiant_depuis_le_dossier(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    # L'arborescence de travail est celle du COEUR, jamais une seconde liste
    # de dossiers ecrite dans la GUI.
    ensure_project_layout(dossier)
    _atomic_write(chemin_projet, manifeste_minimal(identifiant))
    return lire_projet(dossier)


def _motif_verbatim(erreur: BaseException) -> str:
    """Le message de l'exception du coeur, tel quel.

    ``ValidationError`` porte son message court sur ``.message`` ; son
    ``str()`` y ajoute le schema entier, illisible dans une ligne de liste.
    On prend donc le message lorsqu'il existe -- ce reste, dans les deux
    cas, une **lecture** de l'objet exception et non une reecriture.
    """
    message = getattr(erreur, "message", None)
    if isinstance(message, str) and message:
        return message
    return str(erreur)


def lire_projet(dossier) -> LigneProjet:
    """Construire la ligne de liste d'un dossier, lisible ou non.

    N'IMPOSE rien de plus que le coeur : un projet dont les sources sont
    introuvables sur le disque se lit et s'ouvre normalement -- l'ecran de
    gestion ne dit rien du contenu (`EPIC7-ARB-27`), et l'etat des sources
    se verra au chutier (story 7.2).

    Ne leve jamais : les trois familles d'echec du coeur deviennent un
    motif porte par la ligne. C'est litteralement l'exigence « jamais un
    crash au premier ecran que voit un utilisateur en panne » (finding
    E20).
    """
    dossier = Path(dossier)
    chemin_projet = dossier / NOM_FICHIER_PROJET

    try:
        date_modification = chemin_projet.stat().st_mtime
    except OSError:
        date_modification = None

    try:
        manifeste = validate_manifest(chemin_projet)
    except (FileNotFoundError, json.JSONDecodeError, ValidationError, OSError) as erreur:
        return LigneProjet(
            nom=dossier.name,
            chemin=dossier,
            date_creation=None,
            date_modification=date_modification,
            motif=_motif_verbatim(erreur),
        )

    cree_le = manifeste.get("created")
    return LigneProjet(
        nom=dossier.name,
        chemin=dossier,
        # « Champ ``created`` quand il existe, sinon vide -- jamais deduite »
        # (AC 2). Aucun repli sur la date de modification : deux dates
        # egales par construction mentiraient sur l'age du projet.
        date_creation=cree_le if isinstance(cree_le, str) else None,
        date_modification=date_modification,
        motif=None,
    )


def identifiant_declare(dossier) -> str | None:
    """L'identifiant que le fichier de projet DECLARE, sans le recalculer.

    Sert a l'import (AC 5) : deux projets peuvent parfaitement declarer le
    meme identifiant, cela ne fabrique aucun conflit ici puisque rien n'est
    fusionne -- les deux lignes coexistent, distinctes par leur chemin.
    Rend ``None`` quand le document ne se lit pas.
    """
    try:
        manifeste = validate_manifest(Path(dossier) / NOM_FICHIER_PROJET)
    except (FileNotFoundError, json.JSONDecodeError, ValidationError, OSError):
        return None
    declare = manifeste.get("project_id")
    return declare if isinstance(declare, str) else None


__all__ = [
    "NOM_FICHIER_PROJET",
    "NamingError",
    "ProjetExistantError",
    "creer_projet",
    "dossier_cible",
    "identifiant_declare",
    "identifiant_depuis_le_dossier",
    "lire_projet",
    "manifeste_minimal",
]
