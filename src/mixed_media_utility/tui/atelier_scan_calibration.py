# -*- coding: utf-8 -*-
"""`E3-5` -- quelle calibration appliquer aux frames (story 11.6, lot C, AC 3).

L'ecran ou l'operateur **valide** la calibration du temps 2. Il est le premier
ecran de la moitie qui ecrit : rien n'est ecrit ici, mais tout ce qui sera
ecrit porte la correction choisie a cet endroit.

**La proposition n'est pas une imposition** (`EPIC11-ARB-6`, et la formulation
d'`epics.md` : « le profil par defaut du projet est propose et modifiable »).
Le curseur part sur le profil par defaut du projet ; il ne retient rien --
l'operateur valide. C'est exactement la forme d'`EPIC11-ARB-45` (« le curseur
*est* la selection ») et d'`EPIC11-ARB-130` : une **liste selectionnable**
(`DESIGN.md` section 7.1), la **fleche seule**, aucune case a cocher. Les cases
sont reservees aux listes ou l'on retient plusieurs elements, et on n'applique
qu'une calibration.

**Trois lectures de coeur, et aucune quatrieme** :

* `io.profile_designation.designated_profiles` enumere les profils que le
  projet a designes, dans l'ordre du registre ;
* `io.profile_designation.default_profile_entry` dit lequel est le defaut ;
* `io.profile_designation.designated_profile_path` resout le fichier d'une
  entree **par le chemin ecrit au manifeste**, jamais en recomposant
  `versions/calibration/<chain_id>.json` (`EPIC5-ARB-83`). Le `chain_id` ne
  choisit rien ici : il **nomme**, il n'apparie pas.

**Ce module ne decide d'aucune correction.** Ce qu'il produit est une
:class:`CalibrationRetenue` -- un chemin de profil, ou « livrer brut » -- que
l'ecriture passe telle quelle a `scan_write.ecrire_le_lot_detecte`
(`profil_designe=`, `livrer_brut=`). L'entree « aucune » appelle donc
`livrer_brut=True`, **jamais un profil vide** (AC 3.3) : un profil vide serait
une correction identite, c'est-a-dire une correction appliquee, et le manifeste
la declarerait comme telle.

**L'explorateur est celui du depot, pas un second** (`EPIC11-ARB-48`) : `E3-5`
est le quatrieme des cinq sites que l'arbitrage nomme, et la story 11.2b l'a
livre sans le cabler ici. Le clavier passe par
:class:`~mixed_media_utility.tui.ecran_projet.CoutureExplorateur` -- cet ecran
ne recable aucune touche a la main.

**Ce que ce module NE fait pas, et c'est structurel :**

* il n'ecrit **aucune frame** et n'appelle **aucun** point d'entree d'ecriture :
  c'est le lot E ;
* il ne se cable pas lui-meme dans `atelier_scan_parcours` : le cablage est le
  lot H. La classe est exposee, elle n'est pas montee.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from .. import scan_chain
from ..io import calibration_profile, profile_designation
from . import jetons
from .atelier_scan import (ENTREES_DU_MENU, INDENT_DU_CURSEUR, INDENT_DU_TEXTE,
                           _cale_a_droite, filet)
from .coque import Palier
from .ecran_projet import CoutureExplorateur, raccourcis_de_l_explorateur
from .explorateur import FAMILLE_PROFILS, Explorateur
from .palier_projet import nom_du_profil

# ===========================================================================
# Le vocabulaire de l'ecran -- une seule redaction, celle-ci
# ===========================================================================

#: La droite du bandeau, verbatim de la maquette (`E3-5`, l. 2). C'est ce qui
#: distingue les ecrans du temps 2 de ceux du temps 1 : le premier detecte, le
#: second ecrit, et `EPIC11-ARB-6` en fait deux commandes de coeur distinctes.
OBJET_DU_BANDEAU = "temps 2 sur 2 · écrire"

#: Le segment de bandeau -- l'atelier, jamais le nom de la classe d'ecran.
PALIER_DE_L_ATELIER = "Scan"

#: Le titre de la question, verbatim de la maquette (l. 5).
TITRE = "Quelle calibration appliquer aux frames ?"

#: Le titre du filet qui separe le choix de sa carte d'identite (l. 12).
TITRE_DE_LA_CARTE = "Le profil retenu"

#: La ligne de raccourcis, verbatim de la maquette (l. 23). **Constante de
#: module**, comme celles des autres ecrans du Scan : c'est ce qui la fait
#: balayer par la garde d'epic du repli ASCII et par celle des majuscules.
#:
#: **Aucune lettre n'y figure** (`EPIC11-ARB-68`), et `Q quitter` n'y est pas :
#: la sortie ne s'annonce pas sur cet ecran, donc la frappe imprimable y est
#: **consommee** plutot que de remonter au binding applicatif -- une meme
#: touche qui quitterait ici et saisirait ailleurs serait pire qu'inerte.
RACCOURCIS_CALIBRATION = "⏎ continuer  ↑↓ choisir  Échap retour  F1 aide"

#: Largeur de la colonne des noms d'entree (mesuree sur la maquette : le nom
#: ouvre a la colonne 5 de la zone utile, la mention a la colonne 38).
LARGEUR_DU_NOM = 33

#: Largeur de la colonne des libelles de la carte d'identite (colonnes 5 et 20
#: de la zone utile, meme mesure).
LARGEUR_DU_LIBELLE = 15

#: Hauteur maximale de la liste des entrees, `…` compris. **Derivee de la place
#: qui reste** et non choisie : la zone centrale porte dix-sept lignes
#: (`DESIGN.md`, 80 x 24 ligne d'etat comprise), dont trois pour le titre et ses
#: blancs, trois pour le filet et ses blancs, et quatre au plus pour la carte.
#: Sept est ce qui tient sans jamais deborder, y compris quand la carte porte sa
#: ligne d'avertissement de dpi.
HAUTEUR_DE_LA_LISTE = 7

#: Les deux zones de l'ecran : la liste, et l'explorateur monte par-dessus
#: l'entree « autre fichier… ».
ZONE_LISTE = "liste"
ZONE_EXPLORATEUR = "explorateur"

# ---------------------------------------------------------------------------
# Les deux entrees qui ne sont pas des profils
# ---------------------------------------------------------------------------

#: Cle de l'entree qui ouvre l'explorateur sur un `.json` (`EPIC11-ARB-48`).
CLE_AUTRE_FICHIER = "autre-fichier"

#: Cle de l'entree qui livre le lot brut (AC 3.3).
CLE_AUCUNE = "aucune"

#: Cle de l'entree que l'explorateur **ajoute** quand un fichier est designe.
#:
#: **Elle existe parce que l'alternative est un cul-de-sac**, mesure en marchant
#: le parcours : si « autre fichier… » devenait elle-meme le choix retenu, `⏎`
#: y retiendrait le fichier et il n'y aurait plus aucune touche pour en
#: designer un autre -- l'operateur qui s'est trompe de fichier n'aurait plus
#: qu'a quitter l'ecran. Le fichier designe prend donc **sa propre ligne**, avec
#: sa carte d'identite (AC 3.6, « juger sans previz »), et « autre fichier… »
#: reste la porte vers l'explorateur.
CLE_FICHIER_DESIGNE = "fichier-designe"

#: Prefixe des cles d'entree de profil. Le rang du registre suit : deux profils
#: de meme `chain_id` ne peuvent pas coexister au registre (`_upsert` les
#: dedoublonne), mais une cle **derivee du chain_id** ferait de l'identite une
#: cle de resolution, et c'est precisement ce que `EPIC5-ARB-83` supprime.
PREFIXE_DE_PROFIL = "profil-"

#: Les libelles des deux entrees fixes, verbatim de la maquette (l. 9 et 10).
LIBELLE_AUTRE_FICHIER = "autre fichier…"
LIBELLE_AUCUNE = "aucune"
MENTION_AUTRE_FICHIER = "un fichier .json, dans l'explorateur"
MENTION_AUCUNE = "livrer le lot brut, non corrigé"
MENTION_FICHIER_DESIGNE = "désigné dans l'explorateur"

#: Ce que porte la mention du profil **par defaut** (l. 7), et celle des autres
#: profils du registre (l. 8). Deux mentions distinctes parce que deux faits
#: distincts : l'un est ce que le projet propose, l'autre une date de pose.
MENTION_PAR_DEFAUT = "profil par défaut du projet"
MENTION_POSE_LE = "posé le {date}"

#: Ce que la mention dit d'un profil dont l'entree ne porte aucune date. **Rien
#: plutot qu'un `--`** : `DESIGN.md` section 3 refuse la valeur devinee, et une
#: entree ecrite avant `EPIC5-ARB-99` n'a pas d'horodate.
MENTION_SANS_DATE = ""

#: Les libelles de la carte d'identite, verbatim de la maquette (l. 14 a 16).
LIBELLE_CHAINE = "Chaîne"
LIBELLE_POSE_LE = "Posé le"
LIBELLE_S_APPLIQUE = "S'applique à"

#: Les deux champs que la ligne « Chaîne » porte, **lus du coeur et jamais
#: recopies** : `calibration_profile` en est la seule redaction, et deux noms de
#: champ ecrits ici divergeraient au premier renommage sans qu'aucun test le voie
#: (la lecture par `.get` rendrait simplement `""`, c'est-a-dire une ligne
#: silencieusement amputee).
CHAMP_DU_NOM = calibration_profile.LABEL_FIELD
CHAMP_DU_COMMENTAIRE = calibration_profile.COMMENT_FIELD

#: Ce que la troisieme ligne de la carte dit, selon le cardinal. Le cas a un
#: element est le seul ou la faute d'accord se voie -- meme geste que
#: `atelier_scan.mention_de_la_mesure`, et une fabrique le porte.
S_APPLIQUE_A_UN_LOT = "le lot de cette détection"
S_APPLIQUE_A_DES_LOTS = "les {lots} lots de cette détection"

#: Les parts de la seconde ligne de la carte. Chacune est **omise** quand le
#: profil ne la porte pas (AC 3.6), jamais rendue `0` ni `--`.
#:
#: **La divergence porte sa VALEUR et aucune legende** (Egan, le 2026-09-01, sur
#: la planche de relecture du temps 2 -- verbatim : « On met la valeur brute sans
#: légende. Seuls les connaisseurs la liront en connaissance de cause. »).
#:
#: Elle en portait une -- « divergence brute {valeur} {unite} » --, et le lot C
#: l'avait signalee comme une **collision de vocabulaire** : le depot emploie deja
#: « divergence brute » pour `color_metrics.raw_divergence_de76`, qui est une
#: comparaison brut-a-brut entre **deux scans** et qu'un profil ne porte pas. Le
#: champ affiche ici est `acceptance.mean_delta_e_before`, c'est-a-dire autre
#: chose. Deux noms pour deux mesures se distinguent ; un seul nom pour deux
#: mesures se confond -- et c'est le lecteur averti, seul concerne, qui aurait ete
#: trompe. La legende tombe donc, la valeur et son unite restent.
PART_PATCHS = "{patchs} patchs"
PART_UN_PATCH = "1 patch"
PART_DIVERGENCE = "{valeur} {unite}"
SEPARATEUR_DE_CARTE = " · "

#: L'unite de la divergence, et son repli ASCII.
#:
#: **Le repli n'est plus local : il est LU de la table partagee** (lot H de la
#: story 11.6). Le lot C avait du l'ecrire ici -- `Δ` manquait a
#: `jetons.REPLIS_DE_TEXTE`, la decomposition Unicode ne le connait pas, et
#: `replier_ascii("ΔE")` rendait `?E` --, en versant l'entree au lot H parce
#: que `jetons.py` est partage par tous les ecrans du depot. L'entree y est
#: desormais, et cette constante la **derive** au lieu d'en tenir une seconde
#: redaction : `dE` ecrit ici et `"Δ": "d"` ecrit la-bas divergeraient au
#: premier ajustement, et l'ecart ne se verrait qu'en `--ascii`.
UNITE_DE_DIVERGENCE = "ΔE"
UNITE_DE_DIVERGENCE_ASCII = jetons.replier_ascii(UNITE_DE_DIVERGENCE)

#: Ce que la ligne d'etat compte (l. 22). **Une mesure de l'ecran courant**,
#: sans touche, sans conseil et sans motif de conception (`EPIC11-ARB-56`).
ETAT_DES_PROFILS = "{profils} profils désignés dans ce projet"
ETAT_UN_PROFIL = "1 profil désigné dans ce projet"
ETAT_SANS_PROFIL = "aucun profil désigné dans ce projet"
#: Ce que la ligne d'etat dit de la portee, **verbatim de la maquette** (l. 22 :
#: « le retenu s'applique aux 2 lots »). Elle est plus courte que la ligne de la
#: carte -- « les 2 lots de cette détection » --, et c'est voulu : la carte
#: designe les lots, la ligne d'etat les compte.
ETAT_PORTEE = "le retenu s'applique aux {lots} lots"
ETAT_PORTEE_UN_LOT = "le retenu s'applique au lot"
SEPARATEUR_D_ETAT = " · "

#: Ce que la carte dit quand le fichier d'un profil du registre a disparu.
#: **Un fait, pas un refus** : « l'entree de manifest reste vraie de ce que le
#: projet a utilise, mais elle ne fabrique pas un profil absent »
#: (`profile_designation.designated_profile_path`).
FICHIER_DISPARU = "le fichier de ce profil a disparu du projet"

#: L'avertissement de dpi (AC 3.7, second cas limite). **Pas un refus** : un
#: profil pose a 600 et un scan declare a 300 restent applicables, et refuser
#: ici retirerait a l'operateur la seule issue qu'il ait.
ECART_DE_DPI = "profil posé à {profil} dpi, scan déclaré à {scan} dpi"

#: Ce que la carte dit sous l'entree « aucune ». Le lot sort brut, et le dire
#: est ce qui distingue « non corrige » de « corrige par rien ».
CARTE_SANS_CALIBRATION = "Aucune correction ne sera appliquée aux frames."

#: Ce que la carte dit sous « autre fichier… » tant qu'aucun fichier n'est
#: designe. **Ligne de corps et non ligne d'etat** : `EPIC11-ARB-56` ne vise
#: que la seconde.
CARTE_SANS_FICHIER = "aucun fichier désigné"

#: La cle de l'entree du menu de l'atelier vers laquelle `E3-5` renvoie quand le
#: projet ne porte aucun profil (AC 3.7, premier cas limite).
CLE_DE_LA_CALIBRATION = "calibrer"


def _nom_de_l_ecran_de_calibration() -> str:
    """Le nom, **lu du menu de l'atelier** et jamais recopie (`EPIC11-ARB-28`).

    L'arbitrage interdit qu'un terme de nos documents de decision s'affiche :
    ce renvoi nomme donc un **ecran** (« Calibrer une chaîne »), jamais une
    commande (`scan calibrate`). Le nom vit dans `atelier_scan.ENTREES_DU_MENU`
    et se lit la : une seconde redaction divergerait au premier renommage, et
    l'ecart enverrait l'operateur chercher une entree qui n'existe plus.

    Leve a l'import si la cle disparait -- bruyamment, plutot que de rendre un
    renvoi vide que personne ne verrait.
    """
    for entree in ENTREES_DU_MENU:
        if entree.cle == CLE_DE_LA_CALIBRATION:
            return entree.nom
    raise RuntimeError(
        f"le menu de l'atelier Scan ne porte plus d'entree {CLE_DE_LA_CALIBRATION!r} : "
        "le renvoi de `E3-5` nommerait un ecran qui n'existe pas")


#: Le nom d'ecran vers lequel renvoie un projet sans profil.
NOM_DE_L_ECRAN_DE_CALIBRATION = _nom_de_l_ecran_de_calibration()

#: La phrase du renvoi. Elle nomme l'ecran, jamais la commande.
RENVOI_SANS_PROFIL = ("Aucun profil dans ce projet — « {ecran} » en produit un.")


def unite_de_divergence(ascii_seul: bool = False) -> str:
    """`ΔE`, ou `dE` en `--ascii`. Voir :data:`UNITE_DE_DIVERGENCE`."""
    return UNITE_DE_DIVERGENCE_ASCII if ascii_seul else UNITE_DE_DIVERGENCE


# ===========================================================================
# Ce que l'ecran lit d'un profil -- et ce qu'il n'en deduit pas
# ===========================================================================

#: Le motif du `chain_id` **tel que `scan_chain.derive_chain_id` le compose** :
#: « un prefixe lisible `<dpi>-<format>` normalise, puis un condensat
#: hexadecimal ». La longueur du condensat est **lue** de
#: `scan_chain.CHAIN_ID_HASH_LENGTH`, jamais ecrite : le jour ou l'encodage
#: change, ce motif cesse de reconnaitre et la ligne de dpi **disparait**, au
#: lieu d'annoncer une resolution fausse.
_MOTIF_DU_CHAIN_ID = re.compile(
    r"^(?P<dpi>\d+)-[A-Za-z0-9_]+-[0-9a-f]{%d}$" % scan_chain.CHAIN_ID_HASH_LENGTH)


def dpi_du_profil(chain_id: object) -> int | None:
    """Le dpi que le `chain_id` porte dans son prefixe, ou `None`.

    **C'est une lecture d'affichage, jamais une resolution** : rien ici ne
    choisit un profil ni ne l'apparie a un scan (`EPIC5-ARB-83`). Elle sert
    l'unique avertissement de l'AC 3.7 -- « ce profil a ete pose a un autre dpi
    que ce scan » --, qui est un fait utile et non un refus.

    Rend `None` des que le `chain_id` ne suit pas exactement la forme que le
    coeur compose : un identifiant ecrit a la main, une chaine d'un encodage
    anterieur, ou n'importe quoi d'autre. `None` fait **omettre** la ligne, ce
    qui est la regle de `DESIGN.md` section 3 -- jamais une valeur devinee.
    """
    if not isinstance(chain_id, str):
        return None
    trouve = _MOTIF_DU_CHAIN_ID.match(chain_id)
    return int(trouve.group("dpi")) if trouve else None


def lire_le_profil_designe(chemin) -> dict:
    """Relire un fichier de profil, **par le point d'entree du coeur**.

    `profile_designation.read_designated_document` valide le document par
    `calibration_profile.validate_profile_document`, c'est-a-dire par la seule
    porte que le depot connaisse. Aucun `json.loads` n'est ecrit ici.

    Ce que cette fonction ajoute, et **rien d'autre** : elle **separe les deux
    refus** que l'AC 3.7 exige de ne pas confondre. `read_designated_document`
    les reunit sous `ProfileDesignationError` ; la separation suit **exactement
    la convention de `calibration_profile.read_profile`**, qui rend depuis 5.22
    `ProfileNotFoundError` sur une `OSError` de lecture et
    `ProfileValidationError` sur un contenu qu'on ne peut pas garantir. Les
    deux ne disent pas la meme chose a l'operateur : l'un designe un fichier
    absent ou inaccessible, l'autre un fichier qui n'est pas un profil.
    """
    try:
        return profile_designation.read_designated_document(chemin)
    except profile_designation.ProfileDesignationError as refus:
        if isinstance(refus.__cause__, OSError):
            raise calibration_profile.ProfileNotFoundError(str(refus)) from refus
        raise calibration_profile.ProfileValidationError(str(refus)) from refus


def date_lisible(horodate: object) -> str:
    """`2026-08-12T09:30:00Z` -> `12/08`, ou `""` quand rien n'est lisible.

    `""` et jamais `--` : un champ que l'entree ne porte pas s'**omet**
    (AC 3.6). Une entree ecrite avant `EPIC5-ARB-99` n'a pas d'horodate, et lui
    en inventer une serait la pire des deux erreurs possibles -- une date qui a
    l'air juste.
    """
    if not isinstance(horodate, str) or not horodate:
        return ""
    try:
        moment = datetime.fromisoformat(horodate.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return f"{moment.day:02d}/{moment.month:02d}"


# ===========================================================================
# Le modele -- PUR, aucune dependance a `textual`
# ===========================================================================


@dataclass(frozen=True)
class EntreeDeCalibration:
    """Une ligne de la liste : ce qu'elle est, et ce qu'elle retiendra.

    `entree` est l'**entree autoportante du registre** telle que
    `profile_designation.designated_profiles` la rend -- jamais un document de
    profil relu, jamais une recomposition. Elle vaut `None` pour les deux
    entrees qui ne sont pas des profils.
    """

    cle: str
    nom: str
    mention: str
    entree: Mapping[str, Any] | None = None
    par_defaut: bool = False

    @property
    def est_un_profil(self) -> bool:
        return self.entree is not None


@dataclass(frozen=True)
class CalibrationRetenue:
    """Ce que l'ecran rend a l'ecriture. **Les deux champs sont exclusifs.**

    `profil_designe` part tel quel a `scan_write.ecrire_le_lot_detecte`
    (`profil_designe=`), `livrer_brut` a son `livrer_brut=`. L'entree « aucune »
    rend donc `livrer_brut=True` **et aucun profil** (AC 3.3) : un profil vide
    serait une correction identite, c'est-a-dire une correction *appliquee*, et
    le manifeste la declarerait comme telle.
    """

    profil_designe: Path | None = None
    livrer_brut: bool = False
    #: L'entree de registre du profil retenu, quand il en a une. Elle sert la
    #: provenance a l'ecran de resultat ; elle ne resout rien.
    entree: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.livrer_brut and self.profil_designe is not None:
            raise ValueError(
                "« livrer brut » et « appliquer ce profil » sont deux choix "
                "exclusifs : les porter ensemble ferait ecrire un lot corrige "
                "que le manifeste declarerait brut")


def entrees_du_projet(dossier, *, profils: Sequence[Mapping] | None = None,
                      defaut: Mapping | None = None
                      ) -> tuple[EntreeDeCalibration, ...]:
    """Les lignes de `E3-5`, **dans l'ordre du registre** puis les deux fixes.

    `profils` et `defaut` sont les **points d'injection du banc** ; leur defaut
    est le vrai chemin de production -- `designated_profiles` et
    `default_profile_entry`, les deux lecteurs du coeur (AC 3.1). Aucune
    seconde lecture n'est ecrite ici, et aucun profil n'est balaye depuis
    `versions/calibration/` : « cette fonction enumere, elle ne choisit pas ».

    **L'ordre du registre n'est jamais retrie** : il est deja trie par
    `chain_id` a l'ecriture, pour que deux projets ayant vu les memes profils
    dans un ordre different rendent le meme document. Le retrier serait une
    seconde redaction de cette regle -- et la liste que ce code parcourt
    cesserait d'etre celle que le registre ecrit.

    Le profil par defaut est reconnu **par le chemin ecrit a son entree**
    (`ENTRY_PATH_KEY`), jamais par comparaison de `chain_id` : c'est la
    propriete meme d'`EPIC5-ARB-83`, et `record_designated_profile` ecrit
    litteralement la meme entree aux deux cles du manifeste.
    """
    if profils is None:
        profils = (profile_designation.designated_profiles(dossier)
                   if dossier is not None else [])
    if defaut is None and dossier is not None:
        defaut = profile_designation.default_profile_entry(dossier)
    chemin_du_defaut = (defaut or {}).get(profile_designation.ENTRY_PATH_KEY)

    lignes: list[EntreeDeCalibration] = []
    for rang, entree in enumerate(profils):
        par_defaut = bool(
            chemin_du_defaut
            and entree.get(profile_designation.ENTRY_PATH_KEY) == chemin_du_defaut)
        lignes.append(EntreeDeCalibration(
            cle=f"{PREFIXE_DE_PROFIL}{rang}",
            # **Une seule redaction de « sous quel nom un profil s'affiche »** :
            # `palier_projet.nom_du_profil`, deja employee par le pied du palier
            # Projet et par celui du menu du Scan. Une troisieme divergerait.
            nom=nom_du_profil(entree),
            mention=(MENTION_PAR_DEFAUT if par_defaut
                     else _mention_de_pose(entree)),
            entree=entree,
            par_defaut=par_defaut))
    lignes.append(EntreeDeCalibration(CLE_AUTRE_FICHIER, LIBELLE_AUTRE_FICHIER,
                                      MENTION_AUTRE_FICHIER))
    lignes.append(EntreeDeCalibration(CLE_AUCUNE, LIBELLE_AUCUNE,
                                      MENTION_AUCUNE))
    return tuple(lignes)


def _mention_de_pose(entree: Mapping[str, Any]) -> str:
    """« posé le 14/08 », ou rien quand l'entree ne porte pas de date."""
    date = date_lisible(entree.get(profile_designation.ENTRY_DESIGNATED_AT_KEY))
    return MENTION_POSE_LE.format(date=date) if date else MENTION_SANS_DATE


@dataclass
class ChoixDeCalibration:
    """Le modele de `E3-5` : des entrees, un curseur, et un fichier designe.

    **Modele pur**, comme `panneau.py`, `explorateur.py` et
    `atelier_scan_rapport.py` : aucune dependance a `textual`, aucune ecriture.
    C'est ce qui rend mesurables sans terminal les deux appariements a risque
    de cet ecran -- le curseur contre la ligne rendue, et l'entree retenue
    contre le profil qui partira au coeur.
    """

    entrees: tuple[EntreeDeCalibration, ...]
    curseur: int = 0
    premier_visible: int = 0
    #: Le fichier designe par l'explorateur, et le document qu'il porte. Les
    #: deux vont ensemble : un chemin sans document serait un profil qu'on n'a
    #: pas su lire, c'est-a-dire exactement ce que l'AC 3.7 refuse de retenir.
    fichier: Path | None = None
    document: dict | None = None

    def __post_init__(self) -> None:
        self.entrees = tuple(self.entrees)
        if not self.entrees:
            raise ValueError(
                "`E3-5` ne se monte pas sans entree : « aucune » et « autre "
                "fichier… » existent toujours, meme sur un projet sans profil")
        self.curseur = min(max(self.curseur, 0), len(self.entrees) - 1)

    # -- lecture ------------------------------------------------------------

    @property
    def courante(self) -> EntreeDeCalibration:
        return self.entrees[self.curseur]

    @property
    def profils(self) -> tuple[EntreeDeCalibration, ...]:
        """Les seules entrees qui portent un profil du registre."""
        return tuple(e for e in self.entrees if e.est_un_profil)

    def fenetre(self) -> tuple[int, int]:
        return jetons.fenetre_de_liste(len(self.entrees), self.premier_visible,
                                       HAUTEUR_DE_LA_LISTE)

    def retenue(self, dossier=None) -> CalibrationRetenue | None:
        """Ce que `⏎` retient sur l'entree courante, ou `None`.

        `None` veut dire « il n'y a rien a retenir **encore** » : c'est le cas
        de « autre fichier… » tant qu'aucun fichier n'a ete designe, et `⏎` y
        ouvre l'explorateur au lieu de valider. Ce n'est pas un refus.

        Le chemin d'un profil du registre est resolu par
        `designated_profile_path`, **donc par le chemin ecrit au manifeste**.
        Rendre `None` quand le fichier a disparu serait faux : le lot serait
        alors ecrit avec la correction d'un profil absent. On rend donc une
        retenue **sans chemin ni brut** -- et l'ecran, lui, dit que le fichier
        a disparu (voir :func:`carte`). C'est le coeur qui tranche ce qu'il
        fait d'un profil introuvable, pas cet ecran.
        """
        entree = self.courante
        if entree.cle == CLE_AUCUNE:
            return CalibrationRetenue(livrer_brut=True)
        if entree.cle == CLE_FICHIER_DESIGNE and self.fichier is not None:
            return CalibrationRetenue(profil_designe=self.fichier)
        if entree.cle in (CLE_AUTRE_FICHIER, CLE_FICHIER_DESIGNE):
            # **Rien a retenir : `⏎` ouvre l'explorateur.** Ce n'est pas un
            # refus, c'est l'etat ou aucun fichier n'a encore ete designe.
            return None
        return CalibrationRetenue(
            profil_designe=self.chemin_du_profil(entree, dossier),
            entree=entree.entree)

    def chemin_du_profil(self, entree: EntreeDeCalibration,
                         dossier) -> Path | None:
        """Le fichier d'une entree de registre, **resolu par son chemin ecrit**.

        `designated_profile_path` et rien d'autre (`EPIC5-ARB-83`) : recomposer
        `versions/calibration/<chain_id>.json` ferait de l'identite une cle de
        resolution, et de la seule facon qui passe inapercue -- en marchant,
        tant que les deux coincident.
        """
        if entree.entree is None or dossier is None:
            return None
        return profile_designation.designated_profile_path(dossier,
                                                           entree.entree)

    # -- navigation ----------------------------------------------------------

    def deplacer(self, pas: int) -> bool:
        """`↑↓` : le curseur reste dans la liste, il n'en sort jamais."""
        avant = self.curseur
        self.curseur = min(max(self.curseur + pas, 0), len(self.entrees) - 1)
        self.premier_visible = jetons.recadrer_la_fenetre(
            self.premier_visible, self.curseur, len(self.entrees),
            HAUTEUR_DE_LA_LISTE)
        return self.curseur != avant

    def poser_le_fichier(self, chemin, document: dict) -> None:
        """Retenir le fichier designe par l'explorateur, **valide**.

        Le document est passe par l'appelant plutot que relu ici : il vient de
        :func:`lire_le_profil_designe`, donc du coeur, et un profil refuse
        n'arrive jamais jusqu'ici -- c'est ce qui fait que « le choix precedent
        reste actif » (AC 3.7) sans qu'aucune restauration ait a etre ecrite.

        Le fichier prend **sa propre ligne**, juste avant « autre fichier… », et
        le curseur s'y pose : voir :data:`CLE_FICHIER_DESIGNE` pour le
        cul-de-sac que cela evite. Designer un second fichier **remplace** la
        ligne au lieu d'en ajouter une : deux lignes pour un choix unique
        laisseraient l'operateur retenir un fichier qu'il a deja remplace.
        """
        self.fichier = Path(chemin)
        self.document = document
        ligne = EntreeDeCalibration(CLE_FICHIER_DESIGNE, self.fichier.name,
                                    MENTION_FICHIER_DESIGNE)
        restantes = [e for e in self.entrees if e.cle != CLE_FICHIER_DESIGNE]
        rang = [e.cle for e in restantes].index(CLE_AUTRE_FICHIER)
        self.entrees = tuple(restantes[:rang] + [ligne] + restantes[rang:])
        self.curseur = rang
        self.premier_visible = jetons.recadrer_la_fenetre(
            self.premier_visible, self.curseur, len(self.entrees),
            HAUTEUR_DE_LA_LISTE)


def curseur_du_defaut(entrees: Sequence[EntreeDeCalibration]) -> int:
    """Le rang ou le curseur part : **le profil par defaut du projet** (AC 3.2).

    C'est la proposition, et elle ne retient rien -- l'operateur valide
    (`EPIC11-ARB-45` : « le curseur *est* la selection », donc le poser est
    exactement ce que « proposer » veut dire dans cette TUI).

    Sans defaut au projet, le curseur part sur la premiere entree. Il ne part
    **jamais** sur « aucune » par commodite : ce serait proposer de livrer brut,
    ce qui est une decision et non un repli.
    """
    for rang, entree in enumerate(entrees):
        if entree.par_defaut:
            return rang
    return 0


# ===========================================================================
# La carte d'identite du profil retenu (AC 3.6)
# ===========================================================================


@dataclass(frozen=True)
class CarteDuProfil:
    """Ce que la carte dit du profil sous le curseur, ligne par ligne.

    Chaque champ est **omis** quand le profil ne le porte pas -- jamais `0`,
    jamais `--`, jamais une valeur devinee (`DESIGN.md` section 3, meme regle
    que le dpi non mesure du depot). C'est ce qui distingue « ce profil n'a pas
    ete mesure » de « ce profil a mesure zero ».
    """

    #: Ce que la ligne « Chaîne » porte : le **nom personnalise** du profil,
    #: celui que l'operateur a donne en creant sa page de calibration. Ce n'est
    #: plus l'identite de chaine (`chain_id`) -- voir :func:`nom_de_la_chaine`.
    chaine: str = ""
    #: Le commentaire libre pose au meme moment, affiche **a cote** du nom. Vide
    #: quand le profil n'en porte pas : une carte n'invente rien.
    commentaire: str = ""
    #: La seconde ligne, deja assemblee : date, patchs, divergence.
    pose: str = ""
    #: La troisieme ligne : sur quoi le profil retenu s'appliquera.
    portee: str = ""
    #: Les avertissements, chacun avec son etat de glyphe. Une **suite** et non
    #: une chaine : deux avertissements distincts (dpi et fichier disparu)
    #: peuvent coexister, et les concatener ferait perdre lequel est lequel.
    avertissements: tuple[tuple[str, str], ...] = ()
    #: Le texte de remplacement, quand l'entree n'est pas un profil.
    phrase: str = ""


def divergence_brute(document: Mapping[str, Any] | None,
                     ascii_seul: bool = False) -> str:
    """« 2,1 ΔE », ou `""`. **Sans legende** -- voir :data:`PART_DIVERGENCE`.

    **La mesure est `acceptance.mean_delta_e_before`**, c'est-a-dire l'ecart
    moyen des pastilles de la page de calibration **avant** toute correction :
    c'est ce que le profil porte de brut, et le seul champ du document qui
    reponde a la question. Elle est **relue par le coeur**
    (`color_calibration.acceptance_from_document` la publie sous ce nom) et
    jamais recalculee ici.

    `""` -- donc une part **omise** -- des que le document ne porte pas
    d'acceptation : `_acceptance_document(None)` ecrit `{}`, et « aucune mesure »
    ne s'affiche pas comme « une mesure nulle ».
    """
    acceptation = (document or {}).get("acceptance")
    if not isinstance(acceptation, Mapping):
        return ""
    valeur = acceptation.get("mean_delta_e_before")
    if not isinstance(valeur, (int, float)) or isinstance(valeur, bool):
        return ""
    return PART_DIVERGENCE.format(
        valeur=f"{float(valeur):.1f}".replace(".", ","),
        unite=unite_de_divergence(ascii_seul))


def nom_de_la_chaine(source: Mapping[str, Any] | None) -> str:
    """Le **nom personnalise** du profil, ou son `chain_id` a defaut.

    Tranche par Egan le 2026-09-01, verbatim : « Ce qui s'affiche ici normalement
    c'est le nom personnalisé qui a été donné par l'opérateur.ice au moment de
    créer la page de calibration. Ça suffit très bien. »

    **Ce que l'ecran affichait avant, et pourquoi c'etait faute de mieux** : le
    `chain_id` verbatim, `<dpi>-<format>-<condensat de 12 hexa>`. Le lot C l'avait
    signale comme un ecart a trancher -- `scan_chain.derive_chain_id` **hache**
    make, model et software, et rien ne les recompose : la maquette dessinait
    `hp-envy-4520 · tiff · 600 dpi · auto-corr off`, que le produit ne pouvait pas
    rendre. L'etiquette, elle, est ecrite par l'operateur et relue telle quelle.

    **Le repli est NOMME, et il n'invente rien** : un profil ecrit avant l'AC
    8quater ne porte pas d'etiquette, et l'entree de manifest la lui donne vide
    (`ENTRY_OPTIONAL_DOCUMENT_FIELDS` la recopie avec `""` pour defaut). La ligne
    montre alors le `chain_id` -- qui est un **fait** du profil, pas une valeur
    devinee -- plutot que de disparaitre : la carte sert a « juger sans previz »
    (AC 3.6), et une carte dont l'identite s'evapore ne juge plus rien.

    Rend `""` quand il n'y a ni l'un ni l'autre, ce qui **omet** la ligne.
    """
    etiquette = (source or {}).get(CHAMP_DU_NOM)
    if isinstance(etiquette, str) and etiquette.strip():
        return etiquette.strip()
    identite = (source or {}).get("chain_id")
    return identite.strip() if isinstance(identite, str) else ""


def commentaire_du_profil(source: Mapping[str, Any] | None) -> str:
    """Le commentaire libre du profil, ou `""`.

    Reponse mesuree a la question d'Egan (« Ce qu'on peut y afficher
    éventuellement c'est le commentaire qui a été mis au moment de générer la
    planche s'il est stocké au manifest ? ») : **oui**. Il est valide par
    `calibration_profile._validate_label_and_comment`, qui documente que « les
    deux champs sont des etiquettes, jamais des cles », et
    `profile_designation.manifest_entry` le recopie dans l'entree autoportante --
    l'ecran le lit donc sans ouvrir le fichier de profil.

    **Il n'est pas borne ici**, et c'est delibere : `COMMENT_MAX_LENGTH` vaut
    2000, et l'abregement est celui de l'entonnoir unique (`jetons.ajuster` dans
    `rafraichir`), qui pose ses points de suspension apres avoir compte les
    colonnes. Un second abregement ecrit ici serait la seconde redaction que la
    revue de vague 2 bis sanctionne, et il couperait avant le premier.
    """
    commentaire = (source or {}).get(CHAMP_DU_COMMENTAIRE)
    return commentaire.strip() if isinstance(commentaire, str) else ""


def part_des_patchs(source: Mapping[str, Any] | None) -> str:
    """« 24 patchs », ou `""`. Le cardinal **retenu**, pas le cardinal lu.

    `retained_patch_count` est ce qui a servi a l'ajustement ;
    `read_patch_count` compte aussi les pastilles ecartees. Afficher la seconde
    ferait annoncer une finesse que la correction n'a pas.
    """
    valeur = (source or {}).get("retained_patch_count")
    if not isinstance(valeur, int) or isinstance(valeur, bool) or valeur < 0:
        return ""
    return PART_UN_PATCH if valeur == 1 else PART_PATCHS.format(patchs=valeur)


def portee_lisible(lots: int | None) -> str:
    """« les 2 lots de cette détection », ou `""` quand on ne sait pas."""
    if not isinstance(lots, int) or isinstance(lots, bool) or lots <= 0:
        return ""
    return (S_APPLIQUE_A_UN_LOT if lots == 1
            else S_APPLIQUE_A_DES_LOTS.format(lots=lots))


def carte(entree: EntreeDeCalibration, *,
          document: Mapping[str, Any] | None = None,
          chemin: Path | None = None,
          fichier_attendu: bool = True,
          refus: str = "",
          lots: int | None = None,
          dpi_du_scan: int | None = None,
          ascii_seul: bool = False) -> CarteDuProfil:
    """La carte d'identite de l'entree sous le curseur (AC 3.6).

    Elle se **recalcule** a chaque deplacement : c'est une projection pure de
    l'entree et du document, sans etat retenu, donc il n'existe aucun chemin par
    lequel la carte d'un profil resterait affichee sous un autre -- le defaut de
    famille `M33`, qu'aucune relecture n'attrape.

    :param document: le document de profil relu, quand il l'a ete. `None` fait
        **omettre** la divergence : le profil ne la porte pas *ici*, et
        l'inventer serait pire que de la taire.
    :param refus: le motif du coeur quand le fichier n'a pas pu etre relu. Il
        voyage **verbatim** (`EPIC11-ARB-30`).
    """
    if entree.cle == CLE_AUCUNE:
        return CarteDuProfil(phrase=CARTE_SANS_CALIBRATION)
    if entree.cle == CLE_AUTRE_FICHIER or (
            entree.cle == CLE_FICHIER_DESIGNE and document is None):
        return CarteDuProfil(phrase=CARTE_SANS_FICHIER)

    # **L'entree du registre d'abord, le document ensuite** : l'entree est
    # autoportante par construction (`profile_designation.manifest_entry`), donc
    # elle repond seule tant que le fichier n'est pas relu. Le document ne
    # contredit jamais l'entree ; il la complete.
    source: dict[str, Any] = {}
    source.update(dict(entree.entree or {}))
    source.update(dict(document or {}))

    # **Deux valeurs distinctes tirees du meme document, et les confondre serait
    # un defaut silencieux** : `identite` est le `chain_id`, la seule chose dont
    # `dpi_du_profil` sache lire un dpi ; `chaine` est ce que la LIGNE affiche,
    # c'est-a-dire le nom personnalise. Passer le nom a `dpi_du_profil` ferait
    # taire l'avertissement de dpi de l'AC 3.7 sur tout profil etiquete -- sans
    # une erreur, puisque la fonction rend `None` hors de la forme attendue.
    identite = source.get("chain_id")
    chaine = nom_de_la_chaine(source)
    parts = [morceau for morceau in (
        date_lisible(source.get(profile_designation.ENTRY_DESIGNATED_AT_KEY)),
        part_des_patchs(source),
        divergence_brute(document, ascii_seul),
    ) if morceau]

    avertissements: list[tuple[str, str]] = []
    if refus:
        avertissements.append(("absent", refus))
    elif entree.est_un_profil and fichier_attendu and chemin is None:
        avertissements.append(("substitute", FICHIER_DISPARU))
    dpi_pose = dpi_du_profil(identite)
    if (dpi_pose is not None and isinstance(dpi_du_scan, int)
            and not isinstance(dpi_du_scan, bool) and dpi_pose != dpi_du_scan):
        avertissements.append(("substitute", ECART_DE_DPI.format(
            profil=dpi_pose, scan=dpi_du_scan)))

    return CarteDuProfil(
        chaine=chaine,
        commentaire=commentaire_du_profil(source),
        pose=SEPARATEUR_DE_CARTE.join(parts),
        portee=portee_lisible(lots),
        avertissements=tuple(avertissements))


def profil_acceptable(chemin: Path) -> bool:
    """Ce que l'explorateur retient : un `.json` (AC 3.4, `EPIC11-ARB-48`).

    Un dossier n'a pas a passer par ici : l'explorateur ne soumet au filtre que
    les fichiers.
    """
    return chemin.suffix.lower() == ".json"


# ===========================================================================
# `E3-5` -- l'ecran
# ===========================================================================


class EcranChoixDeCalibration(CoutureExplorateur, Palier):
    """`E3-5` -- le profil est propose, jamais impose.

    **Une liste selectionnable, pas une liste a cocher** (`EPIC11-ARB-126`,
    borne par `EPIC11-ARB-130`) : la fleche seule, une ligne par entree, aucune
    case. On n'applique qu'une calibration ; une case a cocher promettrait qu'on
    puisse en retenir deux.

    `retenir` est **injecte et REQUIS**, sans defaut : c'est le finding `K3`,
    paye quatre fois dans cet epic -- « un `Callable | None = None` assorti d'un
    `if ... is not None` fait de l'oubli de cablage un silence ». L'ecran ne
    sait pas ce qui suit le choix ; il ne peut simplement pas etre monte sans
    savoir a qui le rendre.

    **Cet ecran n'est pas cable dans le parcours du Scan** : le cablage est le
    lot H de la story 11.6. La classe est exposee, elle n'est pas montee.
    """

    titre = PALIER_DE_L_ATELIER
    raccourcis = RACCOURCIS_CALIBRATION

    #: **La famille de memoire de session de cet explorateur.** Sans elle, cet
    #: ecran repartait de `Path.cwd()` a chaque ouverture, la ou les sites
    #: voisins reprennent l'operateur ou il en etait. Les deux derniers sites
    #: de `A_POSER` sont fermes ici, le meme jour que les six autres.
    FAMILLE_D_EXPLORATION = FAMILLE_PROFILS

    def __init__(self, dossier=None, *,
                 retenir: Callable[[CalibrationRetenue], None],
                 lots: int | None = None,
                 dpi_du_scan: int | None = None,
                 profils: Sequence[Mapping] | None = None,
                 defaut: Mapping | None = None) -> None:
        super().__init__()
        self.dossier = Path(dossier) if dossier is not None else None
        self._retenir = retenir
        self.lots = lots
        self.dpi_du_scan = dpi_du_scan
        entrees = entrees_du_projet(self.dossier, profils=profils,
                                    defaut=defaut)
        self.choix = ChoixDeCalibration(entrees,
                                        curseur=curseur_du_defaut(entrees))
        self.zone = ZONE_LISTE
        # **Monte a la construction et non a l'ouverture**, comme `E3-1` :
        # l'explorateur lit `Path.cwd()`, et le lire plus tard ferait dependre
        # le dossier de depart du moment ou l'on appuie.
        self.explorateur = Explorateur(montrer_fichiers=True,
                                       accepte=profil_acceptable)
        self._etat_a_dire = ""
        #: La carte coute une lecture de fichier ; la rebatir a chaque dessin la
        #: paierait a chaque frappe. La cle est le **chemin relu**, si bien
        #: qu'un deplacement de curseur invalide la memoire tout seul.
        self._profil_memorise: tuple[Path | None, dict | None, str] = (
            None, None, "")

    # -- lecture ------------------------------------------------------------

    def _appliquer_la_zone(self) -> None:
        """Poser la ligne de raccourcis de la zone courante.

        **`raccourcis` reste un ATTRIBUT, jamais une propriete** : la garde
        d'epic de `test_repli_ascii.py` lit `classe.raccourcis` au niveau de la
        CLASSE, et une propriete ferait echapper cet ecran a la mesure.
        """
        self.raccourcis = (raccourcis_de_l_explorateur(self.explorateur)
                           if self.zone == ZONE_EXPLORATEUR
                           else RACCOURCIS_CALIBRATION)

    def bandeau(self, largeur: int | None = None) -> str:
        """Le bandeau, avec « temps 2 sur 2 · écrire » a droite."""
        from .coque import Contexte

        session = getattr(self.app, "contexte", Contexte())
        contexte = Contexte(session.projet, self.titre, OBJET_DU_BANDEAU)
        return contexte.rendu(
            self.app.size.width if largeur is None else largeur,
            getattr(self.app, "ascii_seul", False))

    def _document_courant(self) -> tuple[Path | None, dict | None, str]:
        """`(chemin, document, refus)` du profil sous le curseur, memorise.

        Le fichier du registre est relu **par le coeur**
        (:func:`lire_le_profil_designe`), et son refus voyage verbatim. Un
        profil dont le fichier a disparu rend `(None, None, "")` : ce n'est pas
        un refus, c'est une entree qui reste vraie de ce que le projet a
        utilise.
        """
        entree = self.choix.courante
        if entree.cle == CLE_FICHIER_DESIGNE:
            return self.choix.fichier, self.choix.document, ""
        if not entree.est_un_profil:
            return None, None, ""
        chemin = self.choix.chemin_du_profil(entree, self.dossier)
        if chemin is None:
            return None, None, ""
        if self._profil_memorise[0] != chemin:
            try:
                self._profil_memorise = (chemin,
                                         lire_le_profil_designe(chemin), "")
            except calibration_profile.ProfileReadError as refus:
                self._profil_memorise = (chemin, None, str(refus))
        return self._profil_memorise

    def carte_courante(self) -> CarteDuProfil:
        """La carte d'identite du profil sous le curseur. **Recalculee.**"""
        chemin, document, refus = self._document_courant()
        return carte(self.choix.courante, document=document, chemin=chemin,
                     fichier_attendu=self.dossier is not None, refus=refus,
                     lots=self.lots, dpi_du_scan=self.dpi_du_scan,
                     ascii_seul=self.app.ascii_seul)

    def ligne_d_entree(self, rang: int, utile: int) -> str:
        """Une entree : la **fleche seule**, le nom en colonne, sa mention.

        Aucune case a cocher, ni retenue ni libre (`EPIC11-ARB-126`, verbatim
        d'Egan : « **Flèche seule !** C'est uniquement dans les listes à cocher
        qu'on trouve les deux. »). La colonne du nom est la meme qu'une entree
        porte le curseur ou non : sans quoi les noms danseraient d'une colonne
        a chaque `↑`.
        """
        entree = self.choix.entrees[rang]
        marque = (self.app.glyphes["curseur"]
                  if rang == self.choix.curseur else " ")
        nom = jetons.abreger_nom(entree.nom, LARGEUR_DU_NOM,
                                 self.app.ascii_seul)
        # **La mention ouvre une colonne FIXE, elle n'est pas calee a droite**,
        # et c'est ce que la maquette dessine : les quatre mentions commencent a
        # la meme colonne (38 de la zone utile), donc l'oeil les lit en colonne.
        # Les caler a droite comme les mentions du formulaire du depot les
        # ferait danser d'une entree a l'autre au gre de leur longueur.
        gauche = (f"{INDENT_DU_CURSEUR}{marque} "
                  + jetons.caler_a_gauche(nom, LARGEUR_DU_NOM,
                                          self.app.ascii_seul))
        return jetons.ajuster(gauche + entree.mention, utile,
                              self.app.ascii_seul).rstrip()

    def lignes_de_la_liste(self, utile: int) -> list[str]:
        """La liste, avec ses `…` quand elle deborde.

        **Le fenetrage est celui du depot et de l'explorateur, pas un second** :
        `jetons.fenetre_de_liste` reserve la ligne `…` **avant** le decoupage,
        sans quoi la derniere entree se cacherait derriere le `…` qui annonce
        qu'elle existe.
        """
        total = len(self.choix.entrees)
        premier, dernier = self.choix.fenetre()
        points = jetons.points_d_abregement(self.app.ascii_seul)
        rendues: list[str] = []
        if premier > 0:
            rendues.append(INDENT_DU_CURSEUR + points)
        rendues += [self.ligne_d_entree(rang, utile)
                    for rang in range(premier, dernier + 1)]
        if dernier < total - 1:
            rendues.append(_cale_a_droite(
                INDENT_DU_CURSEUR + points,
                f"{premier + 1}-{dernier + 1} sur {total}", utile))
        return rendues

    def ligne_de_carte(self, libelle: str, valeur: str) -> str:
        return f"{INDENT_DU_CURSEUR}  {libelle:<{LARGEUR_DU_LIBELLE}}{valeur}"

    def lignes_de_la_carte(self) -> list[str]:
        """Le corps de la carte, **champs omis compris**."""
        courante = self.carte_courante()
        ascii_seul = self.app.ascii_seul
        if courante.phrase:
            return [INDENT_DU_CURSEUR + "  " + courante.phrase]
        lignes: list[str] = []
        if courante.chaine:
            # Le nom, puis le commentaire **quand il y en a un** : le separateur
            # ne s'ecrit pas devant du vide, sinon la ligne se terminerait par un
            # ` · ` orphelin qui annonce une valeur absente.
            lignes.append(self.ligne_de_carte(
                LIBELLE_CHAINE,
                SEPARATEUR_DE_CARTE.join(
                    part for part in (courante.chaine, courante.commentaire)
                    if part)))
        if courante.pose:
            lignes.append(self.ligne_de_carte(LIBELLE_POSE_LE, courante.pose))
        if courante.portee:
            lignes.append(self.ligne_de_carte(LIBELLE_S_APPLIQUE,
                                              courante.portee))
        lignes += [INDENT_DU_CURSEUR + "  " + jetons.marque(etat, phrase,
                                                            ascii_seul)
                   for etat, phrase in courante.avertissements]
        return lignes

    def lignes(self) -> list[str]:
        if self.zone == ZONE_EXPLORATEUR:
            # **Par mots-cles, et la largeur BRUTE** : `Explorateur.lignes`
            # prend `(largeur, titre, libelle, ascii_seul)`, et l'appeler
            # positionnellement poserait `ascii_seul` dans `titre`.
            return self.explorateur.lignes(
                self.app.size.width, titre=TITRE,
                libelle=LIBELLE_AUTRE_FICHIER,
                ascii_seul=self.app.ascii_seul)
        utile = jetons.largeur_utile(self.app.size.width)
        corps = ["", INDENT_DU_TEXTE + TITRE, ""]
        corps += self.lignes_de_la_liste(utile)
        corps += ["", filet(utile, TITRE_DE_LA_CARTE, self.app.ascii_seul), ""]
        corps += self.lignes_de_la_carte()
        if not self.choix.profils:
            # **Le renvoi nomme un ECRAN, jamais une commande**
            # (`EPIC11-ARB-28`), et il est en zone centrale : la ligne d'etat
            # ne porte que des mesures (`EPIC11-ARB-56`).
            corps += ["", INDENT_DU_CURSEUR + "  " + RENVOI_SANS_PROFIL.format(
                ecran=NOM_DE_L_ECRAN_DE_CALIBRATION)]
        return corps

    def rang_du_curseur(self) -> int | None:
        """Le rang **rendu** de la ligne du curseur, ou `None`.

        Il est **derive** de la fenetre et non compte a la main : deux comptes
        de lignes divergeraient a la premiere ligne inseree au-dessus de la
        liste, et le curseur se peindrait alors sur une autre entree sans que
        rien ne le dise.
        """
        if self.zone == ZONE_EXPLORATEUR:
            return self.explorateur.rang_du_curseur()
        premier, dernier = self.choix.fenetre()
        if not premier <= self.choix.curseur <= dernier:
            return None
        tete = 3 + (1 if premier > 0 else 0)
        return tete + (self.choix.curseur - premier)

    def etat(self) -> str:
        """La ligne d'etat : une **mesure**, jamais une touche ni un conseil.

        `EPIC11-ARB-56`. Elle compte les profils du projet et dit sur quoi le
        retenu s'appliquera -- deux faits, verbatim de la maquette (l. 22).
        """
        if self._etat_a_dire:
            return self._etat_a_dire
        if self.zone == ZONE_EXPLORATEUR:
            return self.explorateur.etat(
                jetons.largeur_utile(self.app.size.width),
                self.app.ascii_seul)
        combien = len(self.choix.profils)
        if combien == 0:
            parts = [ETAT_SANS_PROFIL]
        elif combien == 1:
            parts = [ETAT_UN_PROFIL]
        else:
            parts = [ETAT_DES_PROFILS.format(profils=combien)]
        lots = self.lots
        if isinstance(lots, int) and not isinstance(lots, bool) and lots > 0:
            # Le cas a un lot est le seul ou la faute d'accord se voie, et
            # c'est celui qu'une fabrique porte -- meme geste que
            # `atelier_scan.mention_de_la_mesure`.
            parts.append(ETAT_PORTEE_UN_LOT if lots == 1
                         else ETAT_PORTEE.format(lots=lots))
        return SEPARATEUR_D_ETAT.join(parts)

    # -- rendu ---------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="corps-scan-calibration")
        return [Vertical(self._corps, id="centre-scan-calibration")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        utile = jetons.largeur_utile(self.app.size.width)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, utile, self.app.ascii_seul)
             for ligne in self.lignes()],
            ascii_seul=self.app.ascii_seul, sans_couleur=self.app.sans_couleur,
            ligne_du_curseur=self.rang_du_curseur()))
        self.poser_etat(self.etat())
        super().rafraichir()

    def on_mount(self) -> None:
        self._appliquer_la_zone()
        self.rafraichir()

    # -- navigation ----------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier, comme tous les ecrans du depot."""
        if self.zone == ZONE_EXPLORATEUR:
            traite = self._traiter_l_explorateur(touche, caractere)
            self._appliquer_la_zone()
            return traite
        self._etat_a_dire = ""
        if touche in ("up", "down"):
            return self.choix.deplacer(-1 if touche == "up" else 1)
        if touche == "enter":
            return self._valider()
        if caractere and caractere.isprintable():
            # **La frappe est CONSOMMEE**, et ce n'est pas un oubli : la ligne
            # de raccourcis de cet ecran n'annonce aucune sortie, donc laisser
            # remonter la frappe jusqu'au binding applicatif `q` fermerait
            # l'application sur une touche que rien n'annonce. `F1` et `Échap`,
            # eux, sont **annonces** : ils traversent jusqu'a l'application, qui
            # les cable.
            return True
        return False

    def _valider(self) -> bool:
        """Ce que `⏎` fait, entree par entree.

        Sur « autre fichier… » sans fichier designe, il **ouvre l'explorateur**
        au lieu de retenir : il n'y a rien a retenir, et consommer la touche sur
        rien serait indistinguable d'un clavier casse.
        """
        retenue = self.choix.retenue(self.dossier)
        if retenue is None:
            return self._ouvrir_l_explorateur()
        self._retenir(retenue)
        return True

    def _ouvrir_l_explorateur(self) -> bool:
        # `reprendre_la_memoire_de_session` relit elle-meme quand elle deplace ;
        # le `relire` qui suit reste pour le cas ou elle ne deplace rien -- le
        # dossier a pu changer sous nos pieds depuis la derniere visite.
        self.reprendre_la_memoire_de_session()
        self.explorateur.relire()
        self.zone = ZONE_EXPLORATEUR
        self._appliquer_la_zone()
        return True

    # -- les deux gestes que la couture laisse a l'ecran ----------------------

    def _sortir_de_l_explorateur(self) -> bool:
        """Ou mene `Échap` : a la liste, jamais d'un dossier vers son parent
        (`EPIC11-ARB-2`)."""
        self.zone = ZONE_LISTE
        self._appliquer_la_zone()
        return True

    def _valider_l_explorateur(self) -> None:
        """Ce que `⏎` fait de la cible : **il la relit, il ne retient rien
        d'illisible**.

        AC 3.7, troisieme cas limite. Les deux refus du coeur ne se confondent
        pas -- `ProfileNotFoundError` designe un fichier absent,
        `ProfileValidationError` un fichier qui n'est pas un profil -- et le
        motif voyage **verbatim** (`EPIC11-ARB-30`). L'ecran reste sur
        l'explorateur : la cible est fautive, pas le geste, et refermer ferait
        recommencer la navigation. **Le choix precedent reste actif**, sans
        qu'aucune restauration ait a etre ecrite : rien n'a ete pose.
        """
        cible = self.explorateur.valider()
        if cible is None:
            self._etat_a_dire = jetons.marque(
                "substitute", "rien a valider", self.app.ascii_seul)
            return
        try:
            document = lire_le_profil_designe(cible)
        except calibration_profile.ProfileReadError as refus:
            self._etat_a_dire = jetons.marque("absent", str(refus),
                                              self.app.ascii_seul)
            return
        self.choix.poser_le_fichier(cible, document)
        self.zone = ZONE_LISTE
        self._appliquer_la_zone()


__all__ = [
    "CARTE_SANS_CALIBRATION",
    "CARTE_SANS_FICHIER",
    "CLE_AUCUNE",
    "CLE_AUTRE_FICHIER",
    "CLE_FICHIER_DESIGNE",
    "CLE_DE_LA_CALIBRATION",
    "CalibrationRetenue",
    "CarteDuProfil",
    "ChoixDeCalibration",
    "ECART_DE_DPI",
    "ETAT_DES_PROFILS",
    "ETAT_PORTEE",
    "ETAT_PORTEE_UN_LOT",
    "ETAT_SANS_PROFIL",
    "ETAT_UN_PROFIL",
    "EcranChoixDeCalibration",
    "EntreeDeCalibration",
    "FICHIER_DISPARU",
    "HAUTEUR_DE_LA_LISTE",
    "LARGEUR_DU_LIBELLE",
    "LARGEUR_DU_NOM",
    "LIBELLE_AUCUNE",
    "LIBELLE_AUTRE_FICHIER",
    "CHAMP_DU_COMMENTAIRE",
    "CHAMP_DU_NOM",
    "LIBELLE_CHAINE",
    "LIBELLE_POSE_LE",
    "LIBELLE_S_APPLIQUE",
    "MENTION_AUCUNE",
    "MENTION_AUTRE_FICHIER",
    "MENTION_FICHIER_DESIGNE",
    "MENTION_PAR_DEFAUT",
    "MENTION_POSE_LE",
    "NOM_DE_L_ECRAN_DE_CALIBRATION",
    "OBJET_DU_BANDEAU",
    "PALIER_DE_L_ATELIER",
    "PART_DIVERGENCE",
    "PART_PATCHS",
    "PART_UN_PATCH",
    "PREFIXE_DE_PROFIL",
    "RACCOURCIS_CALIBRATION",
    "RENVOI_SANS_PROFIL",
    "S_APPLIQUE_A_DES_LOTS",
    "S_APPLIQUE_A_UN_LOT",
    "TITRE",
    "TITRE_DE_LA_CARTE",
    "UNITE_DE_DIVERGENCE",
    "UNITE_DE_DIVERGENCE_ASCII",
    "ZONE_EXPLORATEUR",
    "ZONE_LISTE",
    "carte",
    "commentaire_du_profil",
    "curseur_du_defaut",
    "date_lisible",
    "divergence_brute",
    "dpi_du_profil",
    "entrees_du_projet",
    "lire_le_profil_designe",
    "nom_de_la_chaine",
    "part_des_patchs",
    "portee_lisible",
    "profil_acceptable",
    "unite_de_divergence",
]
