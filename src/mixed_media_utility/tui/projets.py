# -*- coding: utf-8 -*-
"""Le modele du palier 0 : recents, diagnostic d'un dossier, chemins.

Story 11.2. **Ce module ne connait pas `textual`**, et c'est son contrat le plus
important : le banc de la TUI n'a **ni pilote de terminal ni ecran** (deux
lecons payees par cinq defauts a la vague 1), donc tout ce qui peut etre mesure
hors banc doit l'etre hors banc. Les quatre calculs qui vivent ici -- l'ordre
des recents, la classification d'un dossier, la resolution d'un chemin et la
completion -- sont exactement ceux qu'une campagne de mutation attaque.

**Ce module n'ecrit aucun projet.** La creation passe par
:func:`mixed_media_utility.gui.depot_projets.creer_projet`, qui existe deja,
appelle `ensure_project_layout` et l'ecriture atomique validee du coeur. Une
seconde implementation divergerait au premier ajustement -- meme raisonnement
que pour les jetons, ou `tui/jetons.py` **importe** ceux de la GUI plutot que de
les recopier.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from jsonschema.exceptions import ValidationError

from ..gui.depot_projets import NOM_FICHIER_PROJET
from ..io.manifest import LOT_STATES, validate_manifest
from .explorateur import normaliser

#: La machine a etats d'un lot, **importee du coeur** et jamais recopiee : deux
#: listes divergeraient au premier etat ajoute, et la TUI compterait alors des
#: lots dans un vocabulaire que le coeur ne connait plus.
ETATS_DE_LOT = LOT_STATES

# ---------------------------------------------------------------------------
# La liste des recents. `EPIC11-ARB-16` : c'est la SEULE chose que la v1
# memorise -- ni reglages d'atelier, ni historique de commandes.
# ---------------------------------------------------------------------------

#: Dossier de l'outil dans les reglages utilisateur. Le meme nom que la GUI
#: emploie pour `QSettings` (`ORGANISATION`), pour qu'un operateur retrouve ses
#: deux surfaces au meme endroit.
DOSSIER_REGLAGES = "mixed_media_utility"

#: Nom du document. **Le suffixe de version n'est pas decoratif** : c'est celui
#: de la GUI (`projets/connus-v1`), et pour la meme raison -- pouvoir changer la
#: forme stockee sans jamais relire un document d'une forme anterieure.
FICHIER_RECENTS = "recents-v1.json"

#: Les deux seules cles d'une entree. Une frontiere de test mesure l'egalite
#: avec cet ensemble : c'est ce qui rend `EPIC11-ARB-16` opposable, plutot
#: qu'une intention.
CLES_D_ENTREE = ("chemin", "ouvert_le")


def chemin_du_fichier_de_recents(windows: bool | None = None) -> Path:
    """Ou vit la liste des recents (`EPIC11-ARB-16`).

    `%APPDATA%` sous Windows, `~/.config` ailleurs -- en honorant
    `XDG_CONFIG_HOME` quand il est pose, parce que c'est la convention et que
    l'inventer autrement ferait perdre ses reglages a qui l'a configure.

    ``windows`` est **injectable** pour que les deux branches soient mesurables
    depuis n'importe quelle plateforme : une branche qui ne se teste que sur la
    machine ou elle s'execute n'est testee qu'a moitie.
    """
    if windows is None:
        windows = os.name == "nt"
    if windows:
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / DOSSIER_REGLAGES / FICHIER_RECENTS


def _maintenant() -> str:
    """Horodatage RFC3339 UTC, meme forme que celle qu'ecrit le coeur."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class EntreeRecente:
    """Un projet rencontre, et quand il a ete ouvert pour la derniere fois."""

    chemin: Path
    ouvert_le: str


class Recents:
    """Lecture et ecriture de la liste, **le plus recent en tete**.

    Le fichier est **injecte** : aucun test n'ecrit jamais dans les reglages
    reels de la machine. C'est le meme geste que `PreferencesProjets` cote GUI,
    et pour la meme raison.
    """

    def __init__(self, fichier: Path | None = None) -> None:
        self._fichier = Path(fichier) if fichier is not None \
            else chemin_du_fichier_de_recents()

    # -- lecture ------------------------------------------------------------

    def lire(self) -> list[EntreeRecente]:
        """Les entrees, triees, dedoublonnees. **Ne leve jamais.**

        C'est le premier ecran que voit un operateur en panne : un document
        absent, vide, tronque ou d'une forme inattendue rend une liste vide et
        laisse l'ecran s'ouvrir. « Jamais un crash au premier ecran » -- la
        lecon du finding `E20` cote GUI, qui vaut identiquement ici.
        """
        try:
            brut = json.loads(self._fichier.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return []
        if not isinstance(brut, dict):
            return []
        entrees = brut.get("projets")
        if not isinstance(entrees, list):
            return []

        # **La deduplication est faite a la LECTURE, pas seulement a
        # l'ecriture.** Un document edite a la main, ou ecrit par une version
        # anterieure, peut porter deux fois le meme chemin ; le dedoublonner
        # seulement en ecriture laisserait deux lignes identiques a l'ecran.
        par_chemin: dict[str, EntreeRecente] = {}
        for entree in entrees:
            if not isinstance(entree, dict):
                continue
            chemin = entree.get("chemin")
            ouvert_le = entree.get("ouvert_le")
            if not isinstance(chemin, str) or not isinstance(ouvert_le, str):
                continue
            precedente = par_chemin.get(chemin)
            if precedente is None or ouvert_le > precedente.ouvert_le:
                par_chemin[chemin] = EntreeRecente(Path(chemin), ouvert_le)
        return sorted(par_chemin.values(), key=lambda e: e.ouvert_le, reverse=True)

    # -- ecriture -----------------------------------------------------------

    def noter_ouverture(self, dossier: Path | str, quand: str | None = None) -> None:
        """Poser -- ou remonter -- un projet en tete de liste.

        ``quand`` est injectable : sans lui, deux ouvertures dans la meme
        seconde seraient indistinguables, et le test qui verifie qu'un projet
        du **milieu** remonte en tete serait vert par accident.
        """
        entrees = {str(e.chemin): e.ouvert_le for e in self.lire()}
        entrees[str(Path(dossier))] = quand or _maintenant()
        self._ecrire(entrees)

    def retirer(self, dossier: Path | str) -> None:
        """`Suppr` : oter la ligne. **Le dossier du projet n'est pas touche.**

        `EPIC11-ARB-39`. Ce module n'a aucun chemin vers la suppression d'un
        fichier de projet -- ce n'est pas une precaution, c'est une propriete,
        et un test la mesure en comptant les entrees du dossier avant et apres.
        """
        entrees = {str(e.chemin): e.ouvert_le for e in self.lire()
                   if e.chemin != Path(dossier)}
        self._ecrire(entrees)

    def _ecrire(self, entrees: dict[str, str]) -> None:
        document = {"projets": [
            {"chemin": chemin, "ouvert_le": ouvert_le}
            for chemin, ouvert_le in sorted(entrees.items(),
                                            key=lambda paire: paire[1],
                                            reverse=True)
        ]}
        self._fichier.parent.mkdir(parents=True, exist_ok=True)
        self._fichier.write_text(json.dumps(document, indent=2, ensure_ascii=False),
                                 encoding="utf-8")


# ---------------------------------------------------------------------------
# Diagnostic d'un dossier : trois refus, deux situations qui n'en sont pas.
# ---------------------------------------------------------------------------

#: Les cinq etats possibles. Ils ne se resument PAS a « refus / pas refus » :
#: `EPIC11-ARB-40` distingue deux facons de ne pas etre un projet, et une seule
#: porte le glyphe.
PROJET_LISIBLE = "projet-lisible"
SANS_PROJET = "sans-project-json"
PROJET_ILLISIBLE = "project-json-illisible"
DISPARU = "disparu-du-disque"
ABSENT_A_CREER = "absent-a-creer"
VIDE_A_CREER = "vide-a-creer"


@dataclass(frozen=True)
class Diagnostic:
    """Ce qu'un dossier est, et ce que l'ecran doit en dire.

    ``phrase`` est **de la TUI** : c'est une classification qu'elle fait
    elle-meme. ``motif`` est **du coeur, verbatim** : il n'existe que quand le
    coeur a refuse de lire, et il n'est jamais paraphrase -- « une maquette qui
    ecrivait `LOT_INCOMPLET` la ou le coeur ecrit `LOT_INCOMPLETE` a deja coute
    une divergence a ce depot ».
    """

    etat: str
    phrase: str
    motif: str | None = None

    @property
    def est_un_refus(self) -> bool:
        return self.etat in (SANS_PROJET, PROJET_ILLISIBLE, DISPARU)

    @property
    def porte_la_croix(self) -> bool:
        """Le glyphe `absent`. Un dossier vide ne le porte pas.

        « Un dossier vide n'est pas une anomalie, c'est un point de depart. »
        Il se distingue donc du dossier qui porte des fichiers mais pas de
        `project.json`, lequel est bien un refus.
        """
        return self.est_un_refus


def _motif_du_coeur(erreur: BaseException) -> str:
    """Le message de l'exception du coeur, tel quel.

    `ValidationError` porte son message court sur `.message` ; son `str()` y
    ajoute le schema entier, illisible dans une ligne d'ecran. Prendre l'un ou
    l'autre reste une **lecture** de l'objet exception, jamais une reecriture.
    """
    message = getattr(erreur, "message", None)
    if isinstance(message, str) and message:
        return message
    return str(erreur)


def diagnostiquer(dossier: Path | str,
                  depuis_les_recents: bool = False) -> Diagnostic:
    """Classer un dossier, et dire si c'est un refus.

    **Le contexte compte, et c'est mesure.** Un dossier qui n'existe pas rend
    deux diagnostics differents selon d'ou vient le chemin :

    * depuis les **recents** -> `DISPARU`, un refus. « Un disque externe
      debranche n'est pas un projet supprime » : on le montre, on ne l'efface
      pas en silence ;
    * depuis la **saisie** -> `ABSENT_A_CREER`, qui n'est **pas** un refus.
      `EPIC11-ARB-40` : « un chemin qui ne designe rien est traite comme une
      intention de creation, pas comme une faute de frappe ».

    L'etat du disque est le meme dans les deux cas ; c'est le seul endroit du
    module ou l'appelant apporte une information que le systeme de fichiers ne
    porte pas.

    **Pourquoi la classification est faite ici et pas par le coeur.**
    `depot_projets.lire_projet` rend le **meme** motif -- un `[Errno 2]` sur
    `project.json` -- pour « le dossier n'existe pas » et pour « le dossier
    existe sans `project.json` ». Mesure faite a l'ecriture de la story. Le
    coeur n'a aucune raison de les distinguer ; l'ecran, si.
    """
    dossier = Path(dossier)
    if not dossier.exists():
        if depuis_les_recents:
            return Diagnostic(
                DISPARU,
                "Ce dossier est introuvable -- disque debranche, ou projet "
                "deplace.")
        return Diagnostic(
            ABSENT_A_CREER,
            "Ce dossier n'existe pas encore : il sera cree avec son "
            "arborescence.")

    fichier = dossier / NOM_FICHIER_PROJET
    if not fichier.exists():
        if not any(dossier.iterdir()):
            return Diagnostic(
                VIDE_A_CREER,
                "Ce dossier est vide : un projet peut y etre cree.")
        return Diagnostic(
            SANS_PROJET,
            f"Ce dossier existe mais ne porte pas de {NOM_FICHIER_PROJET}.")

    try:
        validate_manifest(fichier)
    except (OSError, json.JSONDecodeError, ValidationError) as erreur:
        return Diagnostic(
            PROJET_ILLISIBLE,
            f"Le {NOM_FICHIER_PROJET} de ce dossier ne peut pas etre lu.",
            _motif_du_coeur(erreur))
    return Diagnostic(PROJET_LISIBLE, "")


# ---------------------------------------------------------------------------
# Chemins : resolution et completion.
# ---------------------------------------------------------------------------

#: Rendre le chemin ABSOLU d'une saisie, relative ou non.
#:
#: `EXPERIENCE.md`, `E0-2` : « chemin relatif : accepte, resolu depuis le
#: dossier courant, et le chemin **absolu** resolu est affiche avant
#: validation ». La resolution a donc lieu **avant** toute validation, et son
#: resultat est ce que l'ecran montre -- montrer la saisie et valider autre
#: chose serait la meme famille de mensonge qu'un apercu de creation faux.
#:
#: **C'est `explorateur.normaliser`, et pas une seconde implementation.** Cette
#: fonction appelait `resolve(strict=False)`, qui reecrit **chaque** maillon du
#: chemin jusqu'a la cible reelle : c'est la resolution recursive que l'AC 6.8
#: interdit, et `strict=False` n'en concerne que l'existence, jamais la
#: recursion. Consequence mesuree sur les cinq appelants d'`ecran_projet` (les
#: champs `dossier_parent` et l'apercu de creation) : un parent saisi via un
#: lien s'affichait comme sa cible REELLE avant validation, c'est-a-dire que
#: l'ecran montrait un chemin que l'operateur n'avait pas donne. `normaliser`
#: rend le meme chemin absolu, `..` compris, sans reecrire un seul lien -- et
#: comme il est purement lexical, un chemin qui n'existe pas encore se resout
#: toujours (`EPIC11-ARB-40`, le cas nominal de la creation).
#:
#: Elles ont ete deux, et elles divergeaient. Une seule survit.
resoudre = normaliser


# ---------------------------------------------------------------------------
# Les compteurs d'une ligne de recent.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Compteurs:
    """Ce qu'un projet contient, ou `None` quand il n'a pas pu etre lu.

    **`None` et `0` ne sont pas la meme information**, et l'ecran ne doit pas
    les confondre : `None` se rend en `·` (« pas encore lu », `E0-1`), `0` se
    rend en `0`. Rendre `0` pour un projet illisible serait un chiffre faux
    presente comme une mesure -- ce que `DESIGN.md` refuse au meme titre qu'un
    majorant presente comme mesure.
    """

    rushes: int | None = None
    lots: int | None = None
    planches: int | None = None
    scans: int | None = None
    masters: int | None = None

    @property
    def lus(self) -> bool:
        return all(valeur is not None for valeur in self.tous)

    @property
    def tous(self) -> tuple[int | None, ...]:
        """Les cinq cardinaux, dans l'ordre de la chaine de production."""
        return (self.rushes, self.lots, self.planches, self.scans,
                self.masters)


def compter(dossier: Path | str) -> Compteurs:
    """Rushes et lots declares par le manifest d'un projet.

    Rend des `None` des que le document ne se lit pas : c'est le cas d'un
    volume lent, debranche, ou d'un projet casse, et `E0-1` demande que la
    liste ne bloque pas et affiche `·` en attendant.
    """
    fichier = Path(dossier) / NOM_FICHIER_PROJET
    try:
        manifeste = json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return Compteurs()
    if not isinstance(manifeste, dict):
        return Compteurs()
    rushes = manifeste.get("rushes")
    lots = manifeste.get("lots")
    if not isinstance(lots, list):
        return Compteurs(rushes=len(rushes) if isinstance(rushes, list) else None)
    return Compteurs(
        rushes=len(rushes) if isinstance(rushes, list) else None,
        lots=len(lots),
        planches=_lots_arrives_a(lots, "pdf"),
        scans=_lots_arrives_a(lots, "scan"),
        masters=_lots_arrives_a(lots, "encode"),
    )


#: Les cinq lettres, et ce qu'elles comptent. La legende de l'ecran les lit ici
#: plutot que de les recopier : deux ecritures divergeraient au premier
#: ajustement.
#: `S` dit « scannés » et non « scans » : le mot nu est un nom de dossier du
#: coeur (`BASE_SUBDIRS`), et une frontiere de la story 11.2 interdit a la TUI
#: d'ecrire ces noms en litteral -- deux listes de dossiers divergeraient au
#: premier ajout cote coeur. Le participe est de toute facon plus juste : ce
#: cardinal compte des LOTS qui ont ete scannes, pas des fichiers de scan.
LEGENDE_DES_CARDINAUX = (
    ("R", "rushes"), ("L", "lots"), ("P", "planches"),
    ("S", "scann\u00e9s"), ("M", "masters"),
)


def _lots_arrives_a(lots: list, etat: str) -> int | None:
    """Combien de lots ont **atteint** cet etat de la chaine de production.

    **Ce n'est pas un comptage d'objets sur le disque, et c'est deliberé.** Le
    manifeste de projet ne porte AUCUN cardinal de planches, de scans ni de
    masters : ses cles de premier niveau sont `artifacts`, `color`, `created`,
    `lots`, `project_id`, `reconstruction`, `rushes`, `schema_version`, `video`,
    et `io/pdf_manifest.py` l'ecrit noir sur blanc -- « ni nom du PDF, ni
    cardinal de pages ».

    Les compter sur le disque violerait `EPIC11-ARB-30` : la TUI n'ecrit aucun
    jugement metier que le coeur ne porte pas. Ce que le coeur porte, c'est
    l'etat de chaque lot sur la machine `extraction -> pdf -> scan ->
    reconstruction -> encode`, et « avoir atteint l'etat `pdf` » est donc la
    seule mesure vraie de « une planche existe pour ce lot ».

    Rend `None` -- qui se rendra `·` et **jamais `0`** -- des qu'un lot porte un
    etat inconnu : un cardinal calcule sur une machine a etats qu'on ne
    reconnait pas serait un chiffre faux presente comme une mesure.
    """
    try:
        rang_cible = ETATS_DE_LOT.index(etat)
    except ValueError:  # pragma: no cover - garde de programmation
        return None
    compte = 0
    for lot in lots:
        if not isinstance(lot, dict):
            return None
        courant = lot.get("state")
        if courant not in ETATS_DE_LOT:
            return None
        if ETATS_DE_LOT.index(courant) >= rang_cible:
            compte += 1
    return compte


__all__ = [
    "CLES_D_ENTREE",
    "ETATS_DE_LOT",
    "LEGENDE_DES_CARDINAUX",
    "DOSSIER_REGLAGES",
    "FICHIER_RECENTS",
    "PROJET_LISIBLE",
    "SANS_PROJET",
    "PROJET_ILLISIBLE",
    "DISPARU",
    "ABSENT_A_CREER",
    "VIDE_A_CREER",
    "Compteurs",
    "Diagnostic",
    "EntreeRecente",
    "Recents",
    "chemin_du_fichier_de_recents",
    "compter",
    "diagnostiquer",
    "resoudre",
]
