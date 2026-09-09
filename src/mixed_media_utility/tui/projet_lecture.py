# -*- coding: utf-8 -*-
"""Ce qu'un projet ouvert permet de dire (story 11.3).

**Modele pur : aucun `textual`, aucune ecriture.** Trois calculs, et ce sont
exactement ceux qu'une campagne de mutation attaque -- un compteur, une
condition, et un `max` sur une collection.

`EPIC11-ARB-30` gouverne le module entier : **la TUI n'ecrit aucun jugement
metier que le coeur ne porte pas.** Chaque valeur rendue ici se derive du
manifest ou n'est pas rendue.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..gui.depot_projets import NOM_FICHIER_PROJET

if TYPE_CHECKING:  # pragma: no cover - annotation seule, aucun cout au demarrage
    from ..encode import EncodableLot

# ---------------------------------------------------------------------------
# Les cinq entrees du menu (`E1-1`).
# ---------------------------------------------------------------------------

#: **L'ordre est celui de la GUI, et l'ecart d'origine est FERME** (retour
#: terrain d'Egan du 2026-09-06, verbatim : « remonter l'atelier [PDF] dans la
#: liste AVANT scan (ordre logique) »).
#:
#: Cette place portait l'inverse, et il faut dire ce qu'elle disait pour qu'une
#: revue future ne « re-corrige » pas vers l'ancien : « ordre de la chaine de
#: production, et pas celui des onglets de la GUI (qui met Pdf en 2 et Scan en
#: 3) ; c'est un ecart delibere -- la GUI a quatre onglets simultanes ou l'ordre
#: est une disposition, la TUI a une liste qu'on lit de haut en bas, ou l'ordre
#: est une suggestion de parcours ». Le motif etait bon, sa conclusion non : une
#: suggestion de parcours qui contredit l'ordre du meme produit ailleurs
#: n'oriente pas, elle desoriente. Egan a tranche pour la GUI.
#:
#: La coincidence est donc **exacte et voulue** avec
#: `gui/coquille.py:ORDRE_ATELIERS`, dont le commentaire dit deja « l'ordre est
#: l'ordre du flux, il ne se renegocie pas ici ». Les deux listes ne sont pas
#: reliees par le code -- l'une porte des noms d'onglets
#: (`atelier-pdf`), l'autre des libelles d'ecran (`Pdf`) --, et c'est
#: `tests/unit/tui/test_frontiere_ordre_des_ateliers.py` qui les confronte, avec
#: la doc utilisateur, la maquette `E1-1` et `EXPERIENCE.md`.
EXTRACTION = "Extraction"
SCAN = "Scan"
PDF = "Pdf"
EXPORTS = "Exports"
PROJET = "Projet"

#: Les quatre ateliers, dans l'ordre. `PROJET` n'y est pas : ce n'est pas un
#: atelier, et il est separe a l'ecran par une ligne vide.
ATELIERS = (EXTRACTION, PDF, SCAN, EXPORTS)

#: La phrase de chaque entree -- « chacune avec une phrase qui dit ce qu'elle
#: fait ». Un menu qui ne porterait que des noms obligerait a entrer pour
#: savoir, ce qui est exactement ce qu'un menu evite.
PHRASES = {
    EXTRACTION: "Ouvrir un rush, borner, choisir les cadences, extraire",
    PDF: "Composer et generer les planches d'un ou plusieurs lots",
    SCAN: "Deposer des scans, detecter, puis ecrire les TIFF",
    # **« lot scanne », depuis la story 11.14** (`EPIC11-ARB-214`). Le mot
    # d'avant, « reconstruit », etait un NEUVIEME nom pour cet objet -- trouve
    # hors perimetre par le lot D3 et consigne a `deferred-work.md` (`D3-5`)
    # avant d'etre ferme ici. Il disait par surcroit autre chose que le meme
    # mot dit ailleurs dans ce paquet : `palier_projet` compte des « Lots
    # reconstruits » qui sont les lots qu'une RECONSTRUCTION DE PROJET recree
    # au manifeste, un tout autre objet. C'est litteralement l'ambiguite qu'
    # Egan a nommee, sur un mot qu'il n'avait pas nomme.
    EXPORTS: "Encoder un master depuis un lot scanné",
    # **La TROISIEME entree du palier, story 11.11 (`EPIC11-ARB-155`)**, et la
    # phrase du menu la nomme : sans elle, l'entree qui ouvre l'inventaire
    # serait la seule du produit qu'aucun menu n'annonce. Verbatim de `E1-1`.
    PROJET: "Gestion des médias, Profil par défaut, Reconstruction",
}


@dataclass(frozen=True)
class Entree:
    """Une ligne du menu, et **ce qui lui manque** quand il lui manque quelque
    chose.

    ``condition`` est `None` quand l'entree est disponible. Sinon c'est la
    phrase qui dit **ce qui manque et ou l'obtenir** -- jamais un simple
    « indisponible », qui laisserait l'operateur sans geste suivant.
    """

    nom: str
    phrase: str
    condition: str | None = None

    @property
    def disponible(self) -> bool:
        return self.condition is None


#: Pluriel de chaque mot compte. **Une table, pas un `+ "s"`** : « rush » fait
#: « rushes », comme les maquettes `E0-1` et `E1-1` l'ecrivent toutes les deux.
#: Un `s` ajoute mecaniquement rendait « 3 rushs », qui n'est le mot de personne
#: -- trouve par le test d'accord, jamais par relecture.
#:
#: `tirage` est entre ici avec le bandeau de `E5-0` (story 11.7, lot C) : le
#: menu de l'atelier Pdf compte `5 lots · 3 tirages produits`, et ecrire son
#: accord dans l'atelier aurait fait une **seconde** table d'accord a cote de
#: celle-ci -- exactement ce que cette table existe pour fermer.
PLURIELS = {"rush": "rushes", "lot": "lots", "master": "masters",
            "tirage": "tirages"}


def accorder(valeur: int, mot: str) -> str:
    """`3 rushes`, `1 lot`, `0 master`. Le singulier vaut aussi pour zero."""
    return f"{valeur} {PLURIELS[mot] if valeur > 1 else mot}"


@dataclass(frozen=True)
class Compteurs:
    """Ce que le bandeau porte a droite. **Tout est derive, rien n'est lu.**"""

    rushes: int = 0
    lots: int = 0
    masters: int = 0

    def rendu(self) -> str:
        """`3 rushes · 5 lots · 2 masters`, au singulier quand il le faut.

        Un projet vide rend `0 rush · 0 lot · 0 master` -- **pas** une chaine
        vide : « jamais une ligne vide » vaut ici comme au pied.
        """
        return " · ".join((accorder(self.rushes, "rush"),
                           accorder(self.lots, "lot"),
                           accorder(self.masters, "master")))


@dataclass(frozen=True)
class DerniereExtraction:
    """Le pied de `E1-1`, tel qu'`EPIC11-ARB-44` l'a tranche.

    **Ce n'est PAS « la derniere ecriture », et le libelle le dit.** Le
    `project.json` ne porte aucun signal d'horloge par construction -- son
    idempotence est verifiee octet a octet --, son `mtime` est reecrit par git
    puisque `projects/` est versionne, et l'ordre de `lots[]` est celui de
    **premiere creation**. La seule date vraie du document est
    `lots[].confirmation.confirmed_at`, qui n'existe que pour une confirmation
    d'**extraction** (story 3.3).

    Le prix, assume : le pied ne couvre ni les scans, ni les PDF, ni les
    encodages. Il ne dit pas « rien ne s'est passe depuis » ; il dit ce qu'il
    sait.
    """

    quand: str | None = None
    lot: str | None = None
    etape: str | None = None

    @property
    def existe(self) -> bool:
        return self.quand is not None


def lire_manifeste(dossier: Path | str) -> dict | None:
    """Le manifest d'un projet, ou `None` s'il ne se lit pas.

    Ne leve jamais : le menu doit s'ouvrir meme sur un projet dont le document
    est casse, et dire ce qu'il ne sait pas plutot que de tomber.
    """
    try:
        document = json.loads(
            (Path(dossier) / NOM_FICHIER_PROJET).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _lots(manifeste: dict | None) -> list[dict]:
    lots = (manifeste or {}).get("lots")
    return [lot for lot in lots if isinstance(lot, dict)] \
        if isinstance(lots, list) else []


def compter(manifeste: dict | None) -> Compteurs:
    """Rushes, lots et masters. **Les trois sont derives, aucun n'est lu.**

    Les masters sont la **somme** de `lots[].encoded_masters` sur tous les
    lots : un projet peut porter plusieurs lots encodes, et un compte pris sur
    le premier lot serait juste tant qu'un seul en porte -- ce qu'une fixture
    mono-lot ne demasque jamais.
    """
    rushes = (manifeste or {}).get("rushes")
    lots = _lots(manifeste)
    masters = 0
    for lot in lots:
        inventaire = lot.get("encoded_masters")
        if isinstance(inventaire, list):
            masters += len(inventaire)
    return Compteurs(
        rushes=len(rushes) if isinstance(rushes, list) else 0,
        lots=len(lots),
        masters=masters,
    )


def _lots_encodables(manifeste: dict | None,
                     dossier: Path | str | None) -> list["EncodableLot"]:
    """Les lots que **le coeur** admet a l'encodage, et rien d'autre.

    Passe-plat vers `encode.list_encodable_lots` : le critere -- etat au moins
    `MINIMUM_LOT_STATE`, `output_frames_dir` declare, dossier present -- vit
    la-bas et **n'est pas relu ici**. C'est `EPIC11-ARB-30`, et c'est le defaut
    que la story 11.8 ferme : la table `ETATS_RECONSTRUITS` qui vivait ici
    jugeait sur l'etat seul, donc fermait `Exports` sur un lot `scan` que
    `mmu encode` encode, et l'ouvrait sur un lot `reconstruction` recree depuis
    des payloads que le coeur refuse.

    **Sans dossier, aucun lot n'est encodable**, et ce n'est pas un repli
    timide : deux des trois volets du critere portent sur la **matiere** -- un
    dossier declare et present. Juger sans savoir ou regarder, ce serait juger
    sur l'etat, c'est-a-dire reecrire exactement la table qu'on retire. Le cas
    ne se presente d'ailleurs qu'ecran ferme : `EcranAteliers` ne lit un
    manifest que quand il a un dossier.

    **L'import est differe, sur mesure.** Importer `encode` en tete de module
    le ferait entrer dans le graphe du demarrage : `import tui.__main__` coute
    0,19 s aujourd'hui, `import encode` en coute 1,1 a lui seul (il tire
    `scan_output_frames`, donc OpenCV). Le palier 0 n'a aucun lot a juger ; la
    depense se fait quand un projet est ouvert.
    """
    if manifeste is None or dossier is None:
        return []
    from .. import encode

    return encode.list_encodable_lots(manifeste, Path(dossier))


def entrees(manifeste: dict | None,
            dossier: Path | str | None = None) -> list[Entree]:
    """Les cinq entrees, avec leur condition quand elles en ont une.

    **Une seule regle, et elle evite d'inventer un jugement metier** : une
    entree porte sa condition quand **l'atelier n'a rien a lister**.

    * `Extraction` ouvre un rush **depuis un fichier** autant que depuis les
      rushes declares : jamais vide, donc jamais conditionnee ;
    * `Scan` depose un dossier, un fichier ou un PDF, et un projet reconstruit
      **depuis le scan seul** est un cas nominal du depot : jamais conditionnee
      non plus. *(Ecart nomme avec `EXPERIENCE.md`, qui la range parmi les
      trois entrees conditionnees du cas « projet vide » ; la mesure ne le
      soutient pas.)* ;
    * `Pdf` liste les **lots** ;
    * `Exports` liste les lots que le coeur juge **encodables** -- pas ceux
      dont l'etat le laisse croire. `dossier` est ce qui rend ce jugement
      possible : le critere du coeur porte sur la matiere autant que sur
      l'etat, et sans racine de projet il n'y a rien a constater. Voir
      :func:`_lots_encodables` ;
    * `Projet` porte deux commandes : jamais conditionnee.

    Les cinq sont **toujours rendues** : « un operateur doit pouvoir voir ce
    qui existe avant de savoir qu'il n'y a pas acces ».

    La condition d'`Exports` garde son GESTE -- « passez d'abord par l'atelier
    Scan » --, qui reste le bon : c'est bien le scan qui pose
    `output_frames_dir`, et seul le juge avait change a la story 11.8. Ce qui
    a change depuis, c'est le MOT : « aucun lot reconstruit » nommait l'objet
    d'un nom que rien d'autre ne portait, et la story 11.14 a tranche « lot
    scanne » pour tout le depot (`EPIC11-ARB-214`). Le libelle et la condition
    disent donc desormais le meme mot que `E3-8`, qui propose la meme action.
    """
    lots = _lots(manifeste)
    encodables = _lots_encodables(manifeste, dossier)

    conditions = {
        PDF: None if lots else
        "aucun lot -- passez par Extraction ou Scan",
        EXPORTS: None if encodables else
        "aucun lot scanné -- passez d'abord par l'atelier Scan",
    }
    return [Entree(nom, PHRASES[nom], conditions.get(nom))
            for nom in ATELIERS + (PROJET,)]


def derniere_extraction(manifeste: dict | None) -> DerniereExtraction:
    """La derniere extraction **confirmee** du projet (`EPIC11-ARB-44`).

    `max` sur `lots[].confirmation.confirmed_at`. Ni le premier ni le dernier
    element de `lots[]` : cette liste porte l'ordre de **premiere creation**,
    et un `lots[-1]` serait juste tant que la derniere entree se trouve etre la
    plus recente -- c'est-a-dire exactement le mutant `M25` de la story 5.7, ou
    `_find_lot` rendait le premier lot et 257 tests restaient verts.

    Un lot sans `confirmation` est **saute** sans faire tomber l'ecran : le
    champ n'est pas dans le `required` du schema, et les lots venus du scan
    n'en portent pas.
    """
    candidats = []
    for lot in _lots(manifeste):
        confirmation = lot.get("confirmation")
        if not isinstance(confirmation, dict):
            continue
        quand = confirmation.get("confirmed_at")
        if not isinstance(quand, str) or not quand:
            continue
        candidats.append((quand, lot.get("lot_id"), lot.get("state")))
    if not candidats:
        return DerniereExtraction()
    quand, lot, etape = max(candidats, key=lambda triplet: triplet[0])
    return DerniereExtraction(quand=quand, lot=lot, etape=etape)


#: Les ecritures d'horodatage que le coeur produit. **Une seule liste pour les
#: deux rendus ci-dessous** : deux tables divergeraient au premier format
#: ajoute, et l'une des deux surfaces cesserait de lire une date que l'autre
#: lit.
_MOTIFS_D_HORODATAGE = ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
                        "%Y-%m-%dT%H:%M:%S.%fZ")


def _relire(horodatage: str):
    """L'horodatage du coeur en `datetime`, ou `None` s'il ne se lit pas."""
    from datetime import datetime

    for motif in _MOTIFS_D_HORODATAGE:
        try:
            return datetime.strptime(horodatage, motif)
        except ValueError:
            continue
    return None


def date_lisible(horodatage: str) -> str:
    """`2026-08-25T16:46:05Z` -> `25/08 16:46`, la forme des maquettes.

    Rend l'horodatage **tel quel** s'il ne se lit pas : un format inattendu se
    montre plutot que de disparaitre, et il vient du coeur -- le reecrire
    serait le paraphraser.
    """
    lu = _relire(horodatage)
    return horodatage if lu is None else lu.strftime("%d/%m %H:%M")


def date_courte(horodatage: str) -> str:
    """`2026-08-26T09:12:00Z` -> `26/08`, la forme de `E5-1`.

    Le jour et le mois, sans l'heure : c'est ce que le filet « Le lot survolé »
    montre, la ou le pied du menu de projet porte la date complete. Meme repli
    que :func:`date_lisible` -- un format inattendu se montre tel quel -- et
    **la meme table de motifs**, pour que les deux surfaces lisent exactement
    les memes horodatages.
    """
    lu = _relire(horodatage)
    return horodatage if lu is None else lu.strftime("%d/%m")


__all__ = [
    "ATELIERS",
    "EXPORTS",
    "EXTRACTION",
    "PDF",
    "PHRASES",
    "PROJET",
    "SCAN",
    "Compteurs",
    "DerniereExtraction",
    "Entree",
    "accorder",
    "compter",
    "date_courte",
    "date_lisible",
    "derniere_extraction",
    "entrees",
    "lire_manifeste",
]
