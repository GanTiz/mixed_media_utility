# -*- coding: utf-8 -*-
"""La liste des rushes et le relink, en modele pur (story 11.4, AC 2 et AC 4).

**Aucun `textual` ici**, comme dans `panneau.py`, `noms.py` et
`explorateur.py` : des dataclasses, des methodes qui rendent des donnees, des
invariants leves a la construction. L'ecran `E2-1` pose les lignes que ce
module rend et route les touches ; il ne recalcule rien.

Quatre contrats durs, et chacun repare un defaut deja paye dans ce depot.

* **La presence d'un rush est celle que `relink.statut_de_liaison` rend, et
  elle seule** (AC 2.2). Le verificateur d'existence est un argument : ce
  module ne touche jamais le disque pour ce diagnostic, si bien qu'un banc
  peut le contredire et mesurer qu'aucune seconde source de verite ne s'est
  glissee la.
* **Un rush absent reste selectionnable** (AC 2.3). Le curseur s'y pose ; le
  choisir n'extrait rien, il ouvre le relink (AC 2.4).
* **Le relink traite UN rush par validation** (AC 4.4, `EPIC11-ARB-32`
  verbatim : « le relink en masse n'existe pas »). La cible est celle qui est
  **sous le curseur**, jamais « le premier absent » -- c'est litteralement le
  mutant `M25` de la story 5.7, ou `_find_lot` rendait le premier lot et 257
  tests restaient verts.
* **Rien n'est ecrit tant que le relink n'est pas valide** (AC 4.5).
  :func:`preparer_relink` n'ecrit rien -- `relink.appliquer_relink` est une
  copie pure --, et :func:`ecrire_le_relink` **refuse** d'ecrire un apercu
  porteur d'un refus. L'ordre est tenu par le type, pas par la relecture.

**Ce module appelle `relink` et `io/`, jamais `cli.py`**, exactement comme
`palier_projet.py:9-12` le pose : les fonctions de `cli.py` impriment sur
`stderr` et rendent un code retour ; les appeler depuis une TUI enverrait des
lignes dans le terminal **sous** l'ecran dessine, et rendrait un entier la ou
l'interface a besoin d'un document ou d'un refus nomme. Une garde AST le
mesure, avec son volet symetrique.

**La sequence de relink est celle de `cli.relink_command`** (AC 4.2), refaite
appel par appel dans le meme ordre et avec les memes gardes :
`resoudre_rush_id`, `charger_reference`, puis
`verifier_designation_manuelle` (`--video`) ou `rechercher_candidat`
(`--chercher`), puis `appliquer_relink`, puis `_atomic_write`. La seule
difference est la **coupure** entre l'apercu et l'ecriture, qu'`EPIC11-ARB-4`
exige de toute commande qui ecrit.

**L'appariement d'identite reste dans le coeur** (`EPIC11-ARB-32`) : aucune
chaine de ce module ne nomme l'un des trois criteres
(`relink.CRITERES_IDENTITE_RELINK`). Une TUI qui bouclerait elle-meme sur les
rushes manquants reimplanterait dans l'interface la logique d'appariement que
`relink` porte deja.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .. import relink
from ..io.extraction_manifest import MANIFEST_FILENAME, _atomic_write
from . import jetons, projet_lecture

# ---------------------------------------------------------------------------
# Ce qu'un rush montre de lui-meme (`E2-1`)
# ---------------------------------------------------------------------------

#: Les deux presences que l'ecran connait. **Deux, alors que le coeur rend
#: trois statuts** : `lie` d'un cote, les deux etats delies de l'autre. La
#: distinction entre chemin mort et chemin absent est un diagnostic de coeur,
#: pas une information d'operateur -- dans les deux cas le fichier n'est pas la
#: et le geste est le meme.
LIBELLE_LIE = "lié"
LIBELLE_ABSENT = "absent"

#: Statut du coeur -> nom d'etat de la table de glyphes. Les cles sont **lues**
#: de `relink`, jamais recopiees en litteral : un statut renomme au coeur casse
#: ici a l'import plutot que de rendre silencieusement « absent ».
ETATS_DE_PRESENCE = MappingProxyType({
    relink.LIE: "complete",
    relink.DELINKE_CHEMIN_MORT: "absent",
    relink.DELINKE_CHEMIN_ABSENT: "absent",
})

PRESENCES = MappingProxyType({
    relink.LIE: LIBELLE_LIE,
    relink.DELINKE_CHEMIN_MORT: LIBELLE_ABSENT,
    relink.DELINKE_CHEMIN_ABSENT: LIBELLE_ABSENT,
})

#: Le signe de la resolution. Son repli vit dans `jetons.REPLIS_DE_TEXTE`, avec
#: toutes les autres tables du depot.
#:
#: **Il n'y etait pas, et c'est un defaut que ce module a trouve** (2026-08-29,
#: lot D) : `replier_ascii("1920×1080")` rendait `1920?1080`. La premiere
#: version de ce module repliait le signe LUI-MEME, ce qui marchait et laissait
#: le defaut vivre pour les quatre autres maquettes qui portent ce signe
#: (`E4-1`, `E4-3`, `E5-1`, `E5-6`). Le repli local a donc ete retire au profit
#: de la table : **deux redactions du meme repli divergent**, et celle qui reste
#: est celle que tous les ecrans traversent.
SIGNE_MULTIPLIER = "×"

#: Le separateur des colonnes techniques et des lignes d'etat, celui du
#: `DESIGN.md` et de `projet_lecture.Compteurs.rendu`.
SEPARATEUR = " · "

#: L'entree qui suit les rushes declares dans `E2-1`. Elle n'est **pas** un
#: rush : elle ne vient pas du manifeste, et la faire entrer dans la liste
#: rendrait « le rush sous le curseur » ambigu au moment ou l'AC 4.4 en depend.
#: Son texte vit ici pour que l'ecran ne l'invente pas.
AJOUTER_UN_RUSH = "Ajouter un rush"
PHRASE_AJOUTER_UN_RUSH = "choisir un fichier vidéo dans l'explorateur"

#: Ce que « choisir » declenche (AC 2.4). Deux issues, et le fait qu'elles
#: soient deux est le contenu de l'AC : un rush absent n'extrait pas.
ACTION_EXTRAIRE = "extraire"
ACTION_RELINK = "relink"

# ---------------------------------------------------------------------------
# Geometrie de la liste, MESUREE sur la maquette `E2-1`
# ---------------------------------------------------------------------------
#
# Les quatre colonnes sont relevees au caractere pres sur
# `maquettes/E2-1-extraction-rush.txt`, dont les lignes de contenu font 76
# colonnes (`jetons.largeur_utile()` au plancher) : curseur en 3, nom en 5,
# colonne technique en 26, presence en 60. La presence est calee sur la
# **droite** de la zone utile (76 - 16 = 60), si bien qu'une fenetre plus large
# allonge la colonne technique au lieu d'ouvrir une seconde colonne
# (`EPIC11-ARB-21`).

COLONNE_CURSEUR = 3
COLONNE_NOM = 5

#: **Elle valait 30 jusqu'au 2026-08-30, et c'est un arbitrage d'Egan qui l'a
#: ramenee a 26** (`J2`, question `Q8` de `arbitrages-epic-11-a-trancher.md`,
#: tranchee option `a`).
#:
#: Le defaut : la colonne technique disposait de 28 colonnes, et
#: `23,976 fps · 4096×2160 · 1:02:33` en demande **32** -- un 4K a 23,976 im/s
#: de plus d'une heure, qui n'a rien d'absurde. C'est la **duree** qui etait
#: rognee, et en repli ASCII elle disparaissait entierement. Ce n'etait pas la
#: double deduction de `largeur_utile` corrigee en `I7` : une largeur de
#: colonne insuffisante, purement et simplement.
#:
#: **Les deux chiffres de l'arbitrage, et pourquoi ils ne tombent pas.** Un nom
#: de lot fait jusqu'a `io.naming.CANONICAL_ID_MAX_LENGTH` caracteres ; la
#: mesure complete en demande 32 ; et `E2-1` ne dispose que de
#: `60 - 5 - 2 * CREUX_MINIMAL = 51` colonnes pour les deux. Il en faudrait 80.
#: Aucune repartition ne les fait tenir ensemble, et il faudrait une fenetre de
#: 109 colonnes.
#:
#: **Ce que la comparaison honnete oppose n'est donc pas « nom entier contre
#: nom coupe »** -- un nom de longueur maximale n'etait pas lisible a 23 non
#: plus. Elle oppose trois etats :
#:
#: * avant : nom coupe a 23 **et** mesure coupee -- deux promesses degradees ;
#: * option `a`, retenue : nom coupe a 19, mesure **entiere** -- une promesse
#:   degradee, et **rien de retire de l'ecran** ;
#: * option `b`, ecartee : retirer la resolution rendait la mesure entiere sans
#:   toucher au nom, mais **supprimait une information**.
#:
#: `EPIC11-ARB-41`, verbatim : « **on ne degrade pas une promesse, on la retire
#: quand elle ne peut pas etre tenue** ». La mesure est celle qui etait
#: degradee, et les quatre colonnes rendues sont prises sur une colonne qui
#: **elidait deja** : un nom elide reste reconnaissable, un nombre tronque est
#: faux.
#:
#: **Ce qui rend l'option tenable est l'elision AU MILIEU**, et elle n'est pas
#: negociable ici : `rendu()` passe par `jetons.abreger_nom`, qui garde les
#: **deux bouts**. Les lots de ce depot se distinguent par leur SUFFIXE --
#: `rush_01_25` contre `rush_01_12p5`, et pire avec les cadences
#: d'`EPIC11-ARB-62` (`rush_01_8p333333333333334`). Une elision par la fin
#: rendrait deux lots du meme rush indiscernables a l'ecran, c'est-a-dire le
#: risque R12 remonte au niveau de l'affichage. Un banc le mesure sur deux noms
#: qui ne different QUE par leur suffixe.
COLONNE_TECHNIQUE = 26
LARGEUR_PRESENCE = 16

#: La marge droite de tout l'atelier, celle qu'`atelier_extraction._MARGE_DROITE`
#: applique deja aux blocs que l'ECRAN pose. La ligne de position de la fenetre
#: est le seul element de ce module cale sur la droite, et elle s'y aligne.
_MARGE_DROITE = 2

#: Hauteur FIXE de la fenetre de la liste, `…` compris.
#:
#: **Le defaut qu'elle ferme** (`J1`, 2026-08-30) : la liste n'avait **aucune**
#: fenetre. Elle rendait une ligne par rush declare, et `E2-1` debordait la zone
#: centrale des qu'un projet en portait une douzaine -- ce qu'un projet reel
#: depasse largement. Aucun banc ne le voyait : ils mesuraient trois rushes,
#: c'est-a-dire la seule taille ou le defaut n'existe pas.
#:
#: **Le chiffre est celui du PIRE cas, pas du cas nominal.** La zone centrale
#: vaut `jetons.HAUTEUR_CENTRE_AU_PLANCHER` (17 au plancher), et `E2-1` pose
#: autour de la liste, quand le curseur est sur un rush absent :
#:
#: * **quatre respirations** -- le blanc de tete, celui qui suit le titre, et
#:   les deux qui encadrent le filet du relink ;
#: * le titre, la ligne `Ajouter un rush`, le filet du relink (3 lignes) ;
#: * les **trois** lignes du bloc `r` / `d`, la phrase du mode `r`
#:   s'enveloppant sur deux lignes au plancher.
#:
#: Soit **10** lignes de decor, donc `17 - 10 = 7` exactement. Aucune reserve
#: n'est ajoutee : le chiffre est derive, et un budget « prudent » qui vaudrait
#: 5 laisserait de la place perdue sur tous les projets courts.
#:
#: **Ce que le budget protege n'est PAS seulement le debordement**, et c'est ce
#: qu'un mutant de la campagne du lot J a montre (`M5`) : a `11`, la
#: composition tient encore les 17 lignes -- mais seulement parce que
#: `Composition` **sacrifie ses quatre respirations**. L'ecran cesse alors de
#: ressembler a sa maquette : plus un seul blanc entre le titre, la liste et le
#: bloc `r` / `d`. Le banc mesure donc les respirations RESTANTES, pas
#: seulement la hauteur totale ; sans quoi tout budget jusqu'a 11 passait.
#:
#: Cadrer sur le pire cas et non sur le nominal n'est pas de la prudence : le
#: bloc `r` / `d` apparait **sous le curseur**, donc une fenetre calee sur le
#: cas sans relink deborderait a la premiere fleche vers un rush absent.
HAUTEUR_LISTE = 7


# ---------------------------------------------------------------------------
# Le relink : ses deux modes (`E2-1b`, `E2-1c`)
# ---------------------------------------------------------------------------

#: Les deux modes du groupe mutuellement exclusif de la commande `relink`, et
#: **deux seulement**. `MODE_RETROUVER` sert `--chercher`, `MODE_DESIGNER` sert
#: `--video`. Le relink en masse n'est pas un troisieme mode : il n'existe pas
#: (`EPIC11-ARB-32`, hors v1, verse a `deferred-work.md`).
MODE_RETROUVER = "retrouver"
MODE_DESIGNER = "designer"
MODES = (MODE_RETROUVER, MODE_DESIGNER)

#: `r` retrouver, `d` le designer (AC 4.1). Ces lettres ne sont des raccourcis
#: que **hors champ de saisie** (`EPIC11-ARB-68`) : c'est l'ecran qui tient
#: cette regle, pas ce modele.
TOUCHES_DE_MODE = MappingProxyType({"r": MODE_RETROUVER, "d": MODE_DESIGNER})

#: Ce que l'ecran passe a `explorateur.Explorateur` selon le mode (AC 4.1) :
#: `r` cherche dans un **dossier**, `d` designe un **fichier**.
MONTRER_FICHIERS = MappingProxyType({MODE_RETROUVER: False, MODE_DESIGNER: True})

#: Textes des maquettes, verbatim. Elles font foi sur le texte et les colonnes.
LIBELLES_DE_MODE = MappingProxyType({
    MODE_RETROUVER: "Retrouver le fichier",
    MODE_DESIGNER: "Le désigner à la main",
})
PHRASES_DE_MODE = MappingProxyType({
    MODE_RETROUVER: "chercher dans un dossier, par nom, durée et timecode de départ",
    MODE_DESIGNER: "choisir le fichier, sans recherche",
})

#: Le mot du bandeau. **Distinct de la cle du mode** : les cles, les codes et
#: les identifiants du depot sont en ASCII, les textes d'ecran portent leurs
#: accents. Les confondre rendrait `rush_hiver · designer` a l'ecran.
MOTS_DE_MODE = MappingProxyType({
    MODE_RETROUVER: "retrouver",
    MODE_DESIGNER: "désigner",
})
TITRES_DE_MODE = MappingProxyType({
    MODE_RETROUVER: "Où chercher {rush_id} ?",
    MODE_DESIGNER: "Quel fichier est {rush_id} ?",
})

#: La troisieme issue de `E2-1d`, celle qui ne relance rien.
ISSUE_REVENIR = "revenir"
LIBELLE_REVENIR = "Revenir à la liste des rushes"
LIBELLES_APRES_REFUS = MappingProxyType({
    MODE_DESIGNER: "Le désigner à la main",
    MODE_RETROUVER: "Chercher dans un autre dossier",
    ISSUE_REVENIR: LIBELLE_REVENIR,
})


# ---------------------------------------------------------------------------
# Les refus
# ---------------------------------------------------------------------------

#: Les codes de refus du coeur, **lus** de `relink.__all__` et jamais recopies.
#: Un code ajoute la-bas entre ici tout seul ; un code renomme ne laisse pas
#: derriere lui une copie perimee que l'ecran continuerait d'attendre.
CODES_DE_REFUS_DU_COEUR = tuple(sorted(
    getattr(relink, nom) for nom in relink.__all__ if nom.startswith("REFUS_")))

#: Les deux pannes que `cli.relink_command` traite **avant** d'entrer dans
#: `relink`, et pour lesquelles le coeur n'a donc aucun code : le manifeste
#: absent (`cli.py`, « il n'y a pas de rush a relinker ») et le manifeste
#: illisible (`_load_existing_manifest`, JSON tronque). La CLI y repond par une
#: phrase et un code retour `1` ; une TUI a besoin d'un code, sans quoi l'ecran
#: devrait reconnaitre une phrase francaise -- exactement ce que le gabarit des
#: refus nommes existe pour empecher.
REFUS_MANIFESTE_ABSENT = "manifeste-de-projet-absent"
REFUS_MANIFESTE_ILLISIBLE = "manifeste-de-projet-illisible"

CODES_DE_REFUS = CODES_DE_REFUS_DU_COEUR + (REFUS_MANIFESTE_ABSENT,
                                            REFUS_MANIFESTE_ILLISIBLE)

#: Ce que la ligne d'etat de `E2-1d` dit apres un refus. C'est un **fait**
#: garanti par `_atomic_write` (« le project.json precedent est intact »), pas
#: une formule de politesse.
MANIFESTE_INCHANGE = "le manifest est inchangé"

MESSAGE_MANIFESTE_ABSENT = (
    "Aucun {fichier} dans {dossier} : il n'y a pas de rush a relinker. "
    "Lancez d'abord une extraction sur ce dossier.")
MESSAGE_MANIFESTE_ILLISIBLE = (
    "Le fichier {chemin} n'est pas un JSON valide. Aucune ecriture n'a eu "
    "lieu. Restaurer une copie saine du {fichier}, ou repartir d'un dossier "
    "projet vierge.")


class EcritureRefusee(RuntimeError):
    """Ecrire depuis un apercu qui porte un refus (AC 4.5).

    Ce n'est pas un refus d'operateur, c'est une faute d'appel : l'ecran qui
    persiste un relink refuse ecrirait un manifeste que le coeur n'a jamais
    accepte de produire.
    """


@dataclass(frozen=True)
class Refus:
    """Un refus, **par son code** (AC 4.3).

    `code` est l'un de :data:`CODES_DE_REFUS` ; `message` est celui de
    l'exception du coeur, **mot pour mot**. Une paraphrase divergerait du coeur
    au premier ajustement, et l'operateur perdrait les valeurs en jeu que
    `relink` prend soin de citer.
    """

    code: str
    message: str

    def titre(self, ascii_seul: bool = False) -> str:
        """`✕ candidats-multiples` -- le glyphe d'etat, puis le code."""
        return jetons.marque("absent", self.code, ascii_seul)

    def ligne_d_etat(self, ascii_seul: bool = False) -> str:
        """`✕  candidats-multiples · le manifest est inchangé` (`E2-1d`).

        Deux espaces apres le glyphe : c'est la forme de la ligne d'etat des
        maquettes, distincte du glyphe colle d'un cartouche.
        """
        texte = (f"{jetons.glyphes(ascii_seul)['absent']}  {self.code}"
                 f"{SEPARATEUR}{MANIFESTE_INCHANGE}")
        return jetons.replier_ascii(texte) if ascii_seul else texte

    def etats_des_lignes(self, nombre_de_lignes: int,
                         decalage: int = 0) -> dict[int, str]:
        """Toutes les lignes du refus sont en `absent`, y compris les REPLIEES.

        `EPIC11-ARB-71`, et c'est le troisieme symptome qu'Egan a signale : une
        ligne de continuation ne porte, par construction, aucun glyphe. La
        reconnaissance par motif ne pouvait donc pas la teindre, et un refus sur
        trois lignes n'etait rouge que sur la premiere -- il se lisait comme
        deux messages.

        `decalage` est le rang de la premiere ligne du bloc DANS l'ecran :
        l'ecran seul le connait, puisque c'est lui qui a pose ce qui precede.
        """
        return {decalage + rang: "absent" for rang in range(nombre_de_lignes)}

    def lignes(self, largeur: int = jetons.LARGEUR_PLANCHER,
               ascii_seul: bool = False) -> list[str]:
        """Le contenu du cartouche `Refus` : le code, une ligne vide, le message.

        Le message est **replie**, jamais abrege : un refus tronque perdrait
        precisement les valeurs qui le rendent actionnable. La largeur est celle
        de l'interieur d'un cartouche, pas celle de la fenetre.
        """
        utile = jetons.largeur_de_cartouche(largeur)
        return ([self.titre(ascii_seul), ""]
                + jetons.envelopper(self.message, utile, ascii_seul))


# ---------------------------------------------------------------------------
# Un rush
# ---------------------------------------------------------------------------

def duree_de_rush(frames: int | None, fps: float | None) -> str | None:
    """`6300` frames a `25` fps -> `4:12`. Rend `None` quand ca ne se derive pas.

    **La forme est celle des maquettes** (`M:SS`, `H:MM:SS` au-dela de
    l'heure), et non celle d'`avancement.duree_lisible` (`4 min 12`) : celle-la
    dit une duree **restante** dans la grammaire de la section 8 du `DESIGN.md`,
    celle-ci dit la longueur d'un rush dans une colonne alignee sur trois
    lignes. Deux usages, deux formes, chacune mesuree sur sa maquette.

    **La seconde entamee n'est pas comptee, sauf la premiere.** 3 012 frames a
    24 fps font 125,5 s, et les maquettes ecrivent `2:05` : c'est la convention
    de tout lecteur video, la meme qu'un timecode -- on ne compte pas une
    seconde qui n'est pas ecoulee. Le plancher d'une seconde est la seule
    exception : un rush d'une frame dure 0,04 s, et afficher `0:00` pour un rush
    qui existe serait le mensonge qu'`EPIC7-ARB-67` interdit.

    Rien n'est derive quand une des deux valeurs manque : une duree fausse est
    pire qu'une duree absente.

    **La MISE EN FORME vit dans :func:`duree_lisible_de_secondes`**, extraite
    ici le 2026-09-05 pour que `E2-1i` puisse rendre la meme forme depuis la
    duree du flux quand le cardinal manque. Deux redactions de `M:SS`
    divergeraient au premier cas d'une heure, et ce sont deux lignes du MEME
    cartouche.
    """
    if not frames or not fps or frames <= 0 or fps <= 0:
        return None
    return duree_lisible_de_secondes(frames / fps)


def duree_lisible_de_secondes(secondes: float | None) -> str | None:
    """`252.0` -> `4:12`. La forme `M:SS`, `H:MM:SS` au-dela de l'heure.

    C'est la mise en forme que :func:`duree_de_rush` employait en propre
    jusqu'au 2026-09-05 ; elle en est **extraite**, pas recopiee. Le second
    appelant est la ligne `Resolution` de `E2-1i`, ou le cardinal manque et ou
    la duree vient donc du flux plutot que d'une division.

    Les deux conventions de `duree_de_rush` sont ici, puisque c'est ici
    qu'elles s'ecrivent : la seconde entamee n'est pas comptee, et le plancher
    d'une seconde est la seule exception -- afficher `0:00` pour un rush qui
    existe serait le mensonge qu'`EPIC7-ARB-67` interdit.

    Rend `None` sur une duree absente ou non positive : une duree fausse est
    pire qu'une duree absente, et c'est le meme interdit des deux cotes.
    """
    if secondes is None or secondes <= 0:
        return None
    entier = max(int(secondes), 1)
    minutes, reste = divmod(entier, 60)
    if minutes < 60:
        return f"{minutes}:{reste:02d}"
    heures, minutes = divmod(minutes, 60)
    return f"{heures}:{minutes:02d}:{reste:02d}"


def cadence_lisible(fps: float | None) -> str | None:
    """`25.0` -> `25 fps`, `12.5` -> `12,5 fps`. Rend `None` si la cadence
    manque -- la TUI ne fabrique aucune cadence par defaut.

    **Publique depuis le lot des ecrans de declaration (2026-09-05)**, et le
    motif est celui de son propre voisin :func:`bandeau_du_rush` -- « deux
    redactions du meme rendu divergeraient, et l'operateur lirait `25 fps` sur
    un ecran et `25.0 fps` sur le suivant pour le meme rush ». Le panneau
    `E2-1e` porte la meme cadence que la colonne technique de `E2-1` ; il
    appelle donc cette fonction-ci plutot que d'en ecrire une troisieme."""
    if fps is None:
        return None
    entier = int(fps)
    if float(fps) == entier:
        return f"{entier} fps"
    return f"{fps} fps".replace(".", ",")


def _replier(texte: str, ascii_seul: bool) -> str:
    """Le repli d'un texte de ce module : les tables de `jetons`, et rien
    d'autre. Le signe de resolution y est entre le 2026-08-29."""
    if not ascii_seul:
        return texte
    return jetons.replier_ascii(texte)


@dataclass(frozen=True)
class Rush:
    """Un rush declare au manifeste, tel que `E2-1` le montre.

    `statut` est **celui que `relink.statut_de_liaison` a rendu**, transporte
    tel quel : ce champ est la trace que le diagnostic vient du coeur et de
    nulle part ailleurs.
    """

    rush_id: str
    statut: str
    fps_source: float | None = None
    largeur: int | None = None
    hauteur: int | None = None
    frames_source: int | None = None

    def __post_init__(self) -> None:
        if self.statut not in ETATS_DE_PRESENCE:
            raise ValueError(
                f"statut de liaison inconnu : {self.statut!r}. Connus : "
                f"{sorted(ETATS_DE_PRESENCE)}. Le statut vient de "
                "relink.statut_de_liaison, il ne s'invente pas.")

    # -- ce que le rush dit de lui-meme ------------------------------------

    @property
    def lie(self) -> bool:
        return self.statut == relink.LIE

    @property
    def presence(self) -> str:
        """`lié` ou `absent` (AC 2.2) -- les deux etats delies se confondent."""
        return PRESENCES[self.statut]

    @property
    def etat(self) -> str:
        """Le nom d'etat de la table de glyphes, pour le glyphe et la couleur."""
        return ETATS_DE_PRESENCE[self.statut]

    @property
    def duree(self) -> str | None:
        return duree_de_rush(self.frames_source, self.fps_source)

    @property
    def resolution(self) -> str | None:
        if self.largeur is None or self.hauteur is None:
            return None
        return f"{self.largeur}{SIGNE_MULTIPLIER}{self.hauteur}"

    def technique(self, ascii_seul: bool = False) -> str:
        """`25 fps · 1920×1080 · 4:12` (AC 2.1).

        Une valeur qui manque prend le glyphe `neutre` -- « non renseigne, sans
        objet » -- plutot que d'etre omise : trois colonnes qui glissent d'un
        rang selon ce qui manque ne se lisent plus l'une sous l'autre.
        """
        inconnu = jetons.glyphes(ascii_seul)["neutre"]
        morceaux = [cadence_lisible(self.fps_source), self.resolution,
                    self.duree]
        return _replier(
            SEPARATEUR.join(morceau or inconnu for morceau in morceaux),
            ascii_seul)

    def marque_de_presence(self, ascii_seul: bool = False) -> str:
        """`● lié` / `✕ absent` : le glyphe **et** le mot.

        Les deux canaux, toujours (`EPIC11-ARB-43`) : la couleur ne porte jamais
        seule une information, et le repli ASCII garde deux chaines distinctes.
        """
        return jetons.marque(self.etat, _replier(self.presence, ascii_seul),
                             ascii_seul)


# ---------------------------------------------------------------------------
# La liste
# ---------------------------------------------------------------------------

@dataclass
class ListeDesRushes:
    """Les rushes declares, **dans l'ordre du manifeste** (AC 2.1).

    Aucun tri, aucun filtre : ni par presence, ni par nom. L'ordre du document
    est une information -- c'est l'ordre de premiere extraction --, et le
    reordonner ferait mentir la position que l'operateur a memorisee.
    """

    rushes: list[Rush] = field(default_factory=list)
    curseur: int = 0
    #: Le premier rang que la fenetre montre. Meme champ, meme nom et meme role
    #: que dans `cadences.ListeDeCadences` et `explorateur.Explorateur`.
    premier_visible: int = 0

    # -- lecture ----------------------------------------------------------

    @property
    def courant(self) -> Rush | None:
        if not self.rushes:
            return None
        return self.rushes[min(max(self.curseur, 0), len(self.rushes) - 1)]

    @property
    def absents(self) -> list[Rush]:
        """Les rushes delies, dans l'ordre du manifeste.

        **Aucune methode de ce module ne relinke depuis cette liste.** Elle sert
        le compte de la ligne d'etat ; s'en servir pour choisir une cible serait
        le relink en masse qu'`EPIC11-ARB-32` interdit, et sa premiere entree
        est precisement le mauvais rush du mutant `M25`.
        """
        return [rush for rush in self.rushes if not rush.lie]

    @property
    def lies(self) -> list[Rush]:
        return [rush for rush in self.rushes if rush.lie]

    def selectionnable(self, rang: int) -> bool:
        """AC 2.3 : **tout** rang est selectionnable, absent compris.

        Cette methode existe pour que la regle soit un point unique et mesure :
        une liste ou l'absent serait saute rendrait `False` ici, et le banc le
        verrait sur le rang exact.
        """
        return 0 <= rang < len(self.rushes)

    def action_du_choix(self) -> str | None:
        """AC 2.4 : choisir un rush **absent** n'extrait rien, il ouvre le
        relink. Rend `None` sur une liste vide -- un resultat, pas un echec."""
        courant = self.courant
        if courant is None:
            return None
        return ACTION_EXTRAIRE if courant.lie else ACTION_RELINK

    def rush_a_relinker(self) -> Rush | None:
        """Le rush **sous le curseur** s'il est absent (AC 4.4).

        Jamais `self.absents[0]` : avec deux rushes manquants, « le premier
        absent » relinkerait l'autre, silencieusement et avec un manifeste
        valide a l'arrivee. C'est le mode de panne de `_find_lot` en 5.7.
        """
        courant = self.courant
        if courant is None or courant.lie:
            return None
        return courant

    def titre_du_relink(self) -> str | None:
        """Le filet de `E2-1` sous un rush absent, verbatim de la maquette."""
        vise = self.rush_a_relinker()
        if vise is None:
            return None
        return f"{vise.rush_id} — déclaré au manifest, introuvable"

    # -- ecriture ---------------------------------------------------------

    def deplacer(self, pas: int) -> None:
        """`↑↓`. **Aucun rang n'est saute** (AC 2.3) : le curseur se borne aux
        extremites, il ne cherche pas le prochain rush lie."""
        if not self.rushes:
            self.curseur = 0
            self.premier_visible = 0
            return
        self.curseur = min(max(self.curseur + pas, 0), len(self.rushes) - 1)
        self._recadrer()

    def viser(self, rush_id: str) -> Rush:
        """Poser le curseur sur un rush nomme, et le rendre."""
        for rang, rush in enumerate(self.rushes):
            if rush.rush_id == rush_id:
                self.curseur = rang
                self._recadrer()
                return rush
        connus = [rush.rush_id for rush in self.rushes]
        raise KeyError(f"rush inconnu : {rush_id!r} ; connus : {connus}")

    def poser_le_curseur(self, rang: int) -> None:
        """Poser le curseur a un rang donne, borne, **et recadrer la fenetre**.

        Elle existe pour que rien n'ecrive `liste.curseur` de l'exterieur :
        `EcranRushes.relire()` le faisait, et un curseur pose sans recadrage
        laisse la fenetre la ou elle etait -- apres l'ajout d'un rush a une
        liste deja longue, la ligne surlignee ne serait plus a l'ecran.
        """
        if not self.rushes:
            self.curseur = 0
            self.premier_visible = 0
            return
        self.curseur = min(max(rang, 0), len(self.rushes) - 1)
        self._recadrer()

    # -- ce que la fenetre montre -----------------------------------------

    def fenetre(self) -> tuple[int, int]:
        """`(premier, dernier)` rangs visibles, bornes incluses.

        Le calcul est celui de `jetons.fenetre_de_liste`, partage avec la liste
        des cadences et l'explorateur : la ligne `…` se reserve **avant** le
        decoupage, sans quoi le dernier rush se cacherait derriere le `…` qui
        annonce qu'il existe.
        """
        return jetons.fenetre_de_liste(len(self.rushes), self.premier_visible,
                                       HAUTEUR_LISTE)

    def _recadrer(self) -> None:
        """Faire suivre la fenetre au curseur, d'un rang a la fois.

        Appelee par tout ce qui **bouge le curseur** -- `deplacer` et `viser`.
        Un curseur pose sans recadrage sortirait de la fenetre en silence :
        `rang_du_curseur()` rendrait `None`, et l'ecran dessinerait une liste
        sans aucune ligne surlignee, c'est-a-dire un ecran ou l'on ne sait plus
        ou l'on est.
        """
        self.premier_visible = jetons.recadrer_la_fenetre(
            self.premier_visible, self.curseur, len(self.rushes),
            HAUTEUR_LISTE)

    # -- rendu ------------------------------------------------------------

    def resume(self, ascii_seul: bool = False) -> str:
        """`3 rushes déclarés · 2 liés, 1 introuvable` (ligne d'etat de `E2-1`).

        Le pluriel de « rush » vient de `projet_lecture.accorder` : le depot
        ecrit « rushes », et un `+ "s"` mecanique rendait « 3 rushs », qui n'est
        le mot de personne.
        """
        total = len(self.rushes)
        lies = len(self.lies)
        absents = total - lies
        texte = (f"{projet_lecture.accorder(total, 'rush')} "
                 f"{_accord(total, 'déclaré')}{SEPARATEUR}"
                 f"{lies} {_accord(lies, 'lié')}, "
                 f"{absents} {_accord(absents, 'introuvable')}")
        return _replier(texte, ascii_seul)

    def rang_du_curseur(self) -> int | None:
        """Le rang de la ligne surlignee dans :meth:`rendu`, ou `None`.

        **Ce n'est plus l'index du rush** depuis que la liste defile (`J1`) :
        `rendu` ne commence pas au rang 0 de la liste, et il pose une ligne `…`
        de tete des que la fenetre a du contenu au-dessus d'elle. Le jour ou
        l'ecran supposerait a nouveau « une ligne par rush », il surlignerait la
        mauvaise -- c'est exactement le decalage que `_decalage_de_tete`
        absorbe, et il n'est ecrit qu'ici.

        `EPIC11-ARB-47` exige que le rang soit PASSE a `jetons.peindre`, jamais
        devine : l'auto-detection teste `startswith` sur le glyphe de curseur,
        et ces lignes sont indentees -- elle ne trouverait rien, en silence.
        """
        if not self.rushes:
            return None
        premier, dernier = self.fenetre()
        if not premier <= self.curseur <= dernier:
            return None
        return self._decalage_de_tete() + (self.curseur - premier)

    def etats_des_lignes(self) -> dict[int, str]:
        """L'etat de chaque ligne de :meth:`rendu`, a DONNER a `jetons.peindre`.

        `EPIC11-ARB-71` : la couleur se donne, elle ne se devine plus. Ce modele
        a compose les lignes, il sait donc lesquelles portent un rush lie et
        lesquelles portent un absent -- alors que la reconnaissance par motif,
        elle, devrait le relire dans le texte.

        **Seuls les rangs VISIBLES y figurent**, et decales comme ceux du
        curseur : une table indexee sur la liste entiere peindrait la couleur
        d'un rush qui n'est pas a l'ecran sur la ligne d'un autre qui y est.
        """
        premier, dernier = self.fenetre()
        decalage = self._decalage_de_tete()
        return {decalage + (rang - premier): self.rushes[rang].etat
                for rang in range(premier, dernier + 1)}

    def _decalage_de_tete(self) -> int:
        """Le nombre de lignes que :meth:`rendu` pose **avant** le premier rush
        visible : la ligne `…` de tete, ou rien."""
        premier, _dernier = self.fenetre()
        return 1 if premier > 0 else 0

    def rendu(self, largeur: int = jetons.LARGEUR_PLANCHER,
              ascii_seul: bool = False) -> list[str]:
        """Une ligne par rush, aux colonnes de la maquette `E2-1`.

        **Mesure en colonnes, jamais en `len()`**, et le repli precede la
        mesure : un identifiant en ideogrammes rendrait sinon une ligne que le
        code croit calee juste pour le double de sa largeur reelle.

        Le nom est abrege **au milieu** (`jetons.abreger_nom`) : deux rushes
        d'un meme tournage ne different souvent qu'a leur derniere lettre, et
        une coupe par la fin les rendrait identiques a l'ecran.

        **`largeur` est celle de la FENETRE**, jamais la largeur utile : cadre
        et marges sont retires ici, une fois. C'est le contrat de
        `cadences.ListeDeCadences.lignes` et de :meth:`Refus.lignes`, et le
        tenir a un seul endroit est ce qui empeche la double deduction --
        `E2-1` a vecu avec (`I7`, 2026-08-30) : 80 -> 76 -> 72, la colonne
        technique tombait de 28 a 24 colonnes, et la **duree** -- une mesure --
        etait abregee au lieu du nom. Un banc mesure aujourd'hui la duree
        RENDUE, pas la largeur passee.
        """
        utile = jetons.largeur_utile(largeur)
        curseur = jetons.glyphes(ascii_seul)["curseur"]
        colonne_presence = max(utile - LARGEUR_PRESENCE, COLONNE_TECHNIQUE)
        place_du_nom = max(COLONNE_TECHNIQUE - COLONNE_NOM - jetons.CREUX_MINIMAL, 0)
        place_technique = max(
            colonne_presence - COLONNE_TECHNIQUE - jetons.CREUX_MINIMAL, 0)

        total = len(self.rushes)
        premier, dernier = self.fenetre()
        points = jetons.points_d_abregement(ascii_seul)
        lignes = []
        if premier > 0:
            lignes.append(" " * COLONNE_NOM + points)
        for rang in range(premier, dernier + 1):
            rush = self.rushes[rang]
            ligne = " " * COLONNE_CURSEUR
            ligne += (curseur if rang == self.curseur else " ")
            ligne = _caler(ligne, COLONNE_NOM)
            ligne += jetons.abreger_nom(
                _replier(rush.rush_id, ascii_seul), place_du_nom, ascii_seul)
            ligne = _caler(ligne, COLONNE_TECHNIQUE)
            ligne += jetons.ajuster(rush.technique(ascii_seul), place_technique,
                                    ascii_seul)
            ligne = _caler(ligne, colonne_presence)
            ligne += rush.marque_de_presence(ascii_seul)
            lignes.append(ligne.rstrip())
        if dernier < total - 1:
            lignes.append(self._ligne_de_position(premier, dernier, total,
                                                  utile, ascii_seul, points))
        return lignes

    def _ligne_de_position(self, premier: int, dernier: int, total: int,
                           utile: int, ascii_seul: bool, points: str) -> str:
        """`…                                     1-7 sur 20 rushes`.

        Meme forme que celle de l'explorateur et de la liste des cadences : le
        `…` a gauche dit qu'il reste du contenu, la position a droite dit
        **combien**. Sans elle, `…` annonce un ailleurs sans taille -- et c'est
        la taille qui dit a l'operateur s'il lui reste trois rushes ou quarante.

        Le pluriel vient de `projet_lecture.accorder`, comme celui de
        :meth:`resume` : le depot ecrit « rushes », et un `+ "s"` mecanique
        rendrait « 20 rushs », qui n'est le mot de personne.
        """
        position = _replier(
            f"{premier + 1}-{dernier + 1} sur "
            f"{projet_lecture.accorder(total, 'rush')}", ascii_seul)
        tete = " " * COLONNE_NOM + points
        # **Le creux se mesure en COLONNES, jamais en `len()`**, et le repli
        # ASCII est deja applique aux deux morceaux : `…` rend `...`, donc la
        # tete s'ALLONGE de deux colonnes en repli et un creux calcule avant le
        # repli pousserait la position hors de la marge droite.
        creux = (utile - _MARGE_DROITE - jetons.colonnes(tete)
                 - jetons.colonnes(position))
        return tete + " " * max(jetons.CREUX_MINIMAL, creux) + position


def _caler(ligne: str, colonne: int) -> str:
    """Completer une ligne jusqu'a une colonne donnee, en gardant au moins un
    creux d'une colonne : deux textes colles se lisent comme un seul."""
    return ligne + " " * max(colonne - jetons.colonnes(ligne), 1)


def _accord(valeur: int, mot: str) -> str:
    """Le pluriel des adjectifs de la ligne d'etat. Le singulier vaut pour zero
    -- « 0 lié », comme `projet_lecture.accorder` le fait pour les noms."""
    return f"{mot}s" if valeur > 1 else mot


# ---------------------------------------------------------------------------
# Lecture du projet (AC 2.5)
# ---------------------------------------------------------------------------

def rushes_du_manifeste(manifeste: Mapping[str, Any] | None, *,
                        existe: Callable[[str], bool] | None = None
                        ) -> list[Rush]:
    """Les rushes d'un manifeste **deja lu**, dans son ordre.

    `existe` est passe tel quel a `relink.statut_de_liaison` : c'est la seule
    chose de ce module qui puisse toucher un disque, et elle est du coeur. AC
    2.2 : « la TUI ne fait aucun autre acces disque pour ce diagnostic ».

    Un rush dont la duree ne se derive pas -- pas de lot, ou des lots qui se
    contredisent sur le cardinal -- est rendu **sans duree** plutot que de faire
    tomber l'ecran : `charger_reference` refuse de choisir entre deux cardinaux
    divergents, ce qui est juste pour un relink et trop dur pour une liste.
    """
    document = manifeste or {}
    entrees = document.get("rushes")
    if not isinstance(entrees, list):
        return []

    liste = []
    for entree in entrees:
        if not isinstance(entree, Mapping):
            continue
        rush_id = entree.get("rush_id")
        if not isinstance(rush_id, str) or not rush_id:
            continue
        resolution = entree.get("resolution_source")
        resolution = resolution if isinstance(resolution, Mapping) else {}
        liste.append(Rush(
            rush_id=rush_id,
            statut=relink.statut_de_liaison(entree, existe=existe),
            fps_source=_nombre(entree.get("fps_source")),
            largeur=_entier(resolution.get("width")),
            hauteur=_entier(resolution.get("height")),
            frames_source=_cardinal_source(document, rush_id),
        ))
    return liste


def _cardinal_source(manifeste: Mapping[str, Any], rush_id: str) -> int | None:
    """Le cardinal source du rush vise, **par le coeur**.

    `charger_reference` apparie les lots **par `rush_id`**, jamais par
    position : deux lots d'un autre rush avant celui-ci dans `lots[]` ne
    changent rien. C'est exactement la garantie que la story 5.7 a payee.
    """
    try:
        return relink.charger_reference(manifeste, rush_id).source_frame_count
    except relink.RelinkError:
        return None


def _nombre(valeur: Any) -> float | None:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return float(valeur)


def _entier(valeur: Any) -> int | None:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return int(valeur)


def lister(dossier_projet: Path | str, *,
           existe: Callable[[str], bool] | None = None) -> ListeDesRushes:
    """La liste des rushes d'un projet ouvert (AC 2.5).

    **La lecture passe par `projet_lecture.lire_manifeste`, jamais par une
    seconde lecture de manifeste.** Ce module ne connait ni `json` ni le nom du
    fichier de projet pour lire : une seconde porte divergerait de la premiere
    sur les pannes qu'elle sait absorber -- `lire_manifeste` ne leve jamais,
    parce que l'ecran doit s'ouvrir meme sur un document casse.
    """
    return ListeDesRushes(rushes_du_manifeste(
        projet_lecture.lire_manifeste(Path(dossier_projet)), existe=existe))


# ---------------------------------------------------------------------------
# Le relink (AC 4)
# ---------------------------------------------------------------------------

def _mode_connu(mode: str) -> str:
    if mode not in MODES:
        raise ValueError(
            f"mode de relink inconnu : {mode!r}. Connus : {list(MODES)}. Le "
            "relink en masse n'est pas un mode (EPIC11-ARB-32).")
    return mode


def titre_de_relink(rush_id: str, mode: str) -> str:
    """`Où chercher rush_hiver ?` / `Quel fichier est rush_hiver ?`."""
    return TITRES_DE_MODE[_mode_connu(mode)].format(rush_id=rush_id)


def bandeau_de_relink(rush_id: str, mode: str) -> str:
    """La droite du bandeau : `rush_hiver · retrouver`."""
    return f"{rush_id}{SEPARATEUR}{MOTS_DE_MODE[_mode_connu(mode)]}"


def bandeau_du_rush(rush_id: str, fps_source: float | None,
                    frames_source: int | None,
                    ascii_seul: bool = False) -> str:
    """La droite du bandeau du rush travaille : `rush_01 · 25 fps · 4:12`.

    C'est le texte que les maquettes `E2-3`, `E2-3b`, `E2-3c`, `E2-4` et `E2-5`
    portent, verbatim -- et qu'aucun de ces cinq ecrans ne posait (`J3`,
    2026-08-30). Trois valeurs : l'identifiant, la cadence **source** et la
    duree. Pas la resolution : le bandeau est une ligne partagee avec le chemin
    de navigation, la colonne technique de `E2-1` est l'endroit ou les trois
    chiffres tiennent ensemble.

    **Les deux mesures passent par les memes fonctions que la colonne technique
    de `E2-1`** (:func:`cadence_lisible`, :func:`duree_de_rush`) : deux redactions du
    meme rendu divergeraient, et l'operateur lirait `25 fps` sur un ecran et
    `25.0 fps` sur le suivant pour le meme rush.

    Une valeur qui manque prend le glyphe `neutre`, comme
    :meth:`Rush.technique` : « non renseigne, sans objet ». Rien n'est derive
    d'une seule des deux -- une duree fausse est pire qu'une duree absente.
    """
    inconnu = jetons.glyphes(ascii_seul)["neutre"]
    morceaux = [rush_id, cadence_lisible(fps_source),
                duree_de_rush(frames_source, fps_source)]
    return _replier(
        SEPARATEUR.join(morceau or inconnu for morceau in morceaux),
        ascii_seul)


def reference_de_rush(dossier_projet: Path | str,
                      rush_id: str) -> relink.ReferenceIdentite | None:
    """Les trois references d'identite du rush vise, ou `None`.

    C'est **le meme appel que `preparer_relink` fait deja** dans la sequence de
    `cli.relink_command` -- `resoudre_rush_id` puis `charger_reference` --,
    isole pour que `E2-1b` et `E2-1c` puissent MONTRER sur quoi le coeur va
    apparier **avant** de chercher. Rien n'est recalcule ici : l'appariement
    reste dans le coeur (`EPIC11-ARB-32`), et cette fonction n'en rend que les
    trois references, pas un verdict.

    **Rend `None` plutot que de lever.** Un manifeste absent, illisible ou un
    `rush_id` inconnu ne doit pas empecher l'explorateur de s'ouvrir : le point
    de jugement se tient a la validation, ou `preparer_relink` rend un refus
    **par son code**. Une ligne d'etat qui perd ses criteres est un manque ;
    une pile d'appel dans un ecran est une panne.
    """
    manifeste = projet_lecture.lire_manifeste(Path(dossier_projet))
    if manifeste is None:
        return None
    try:
        return relink.charger_reference(
            manifeste, relink.resoudre_rush_id(manifeste, rush_id))
    except relink.RelinkError:
        return None


def lignes_des_modes() -> list[tuple[str, str, str]]:
    """Le bloc `r` / `d` de `E2-1`, dans l'ordre de la maquette.

    Rendu en donnees et non en texte cale : c'est l'ecran qui connait sa
    largeur, et deux calages du meme bloc divergeraient.
    """
    return [(touche, LIBELLES_DE_MODE[mode], PHRASES_DE_MODE[mode])
            for touche, mode in TOUCHES_DE_MODE.items()]


def issues_apres_refus():
    """Les trois sorties de `E2-1d`, en `panneau.ChoixExclusif`.

    **Aucune n'ecrit** : un refus est un point de jugement, et `ChoixExclusif`
    refuse a la construction qu'une issue soit preselectionnee
    (`EPIC11-ARB-7`). Les cles nomment le mode de coeur qu'elles relancent
    (`EPIC11-ARB-36`).
    """
    from .panneau import ChoixExclusif, Issue

    return ChoixExclusif([
        Issue(MODE_DESIGNER, LIBELLES_APRES_REFUS[MODE_DESIGNER], ecrit=False),
        Issue(MODE_RETROUVER, LIBELLES_APRES_REFUS[MODE_RETROUVER], ecrit=False),
        Issue(ISSUE_REVENIR, LIBELLES_APRES_REFUS[ISSUE_REVENIR], ecrit=False),
    ])


def resume_de_reference(reference: relink.ReferenceIdentite,
                        ascii_seul: bool = False) -> str:
    """`rush_hiver : 3 012 frames · TC 00:00:00:00` (ligne d'etat de `E2-1b`).

    Les deux chiffres sont ceux de `charger_reference` : ce sont les criteres
    sur lesquels le coeur va chercher, et les montrer avant la recherche est ce
    qui rend un refus comprehensible. Une reference qui manque prend le glyphe
    `neutre` : annoncer `0 frames` serait un chiffre faux.
    """
    inconnu = jetons.glyphes(ascii_seul)["neutre"]
    cardinal = reference.source_frame_count
    frames = f"{_grouper(cardinal)} {_accord(cardinal, 'frame')}" \
        if cardinal else f"{inconnu} frames"
    timecode = reference.source_start_timecode or inconnu
    texte = f"{reference.rush_id} : {frames}{SEPARATEUR}TC {timecode}"
    return _replier(texte, ascii_seul)


def _grouper(valeur: int) -> str:
    """`3012` -> `3 012`. Groupement par espace, comme les maquettes l'ecrivent
    -- un cardinal a cinq chiffres non groupe se relit deux fois."""
    return f"{valeur:,}".replace(",", " ")


@dataclass(frozen=True)
class Apercu:
    """Ce qu'un relink **ecrira**, sans que rien n'ait ete ecrit (AC 4.5).

    `manifeste` est la copie que `relink.appliquer_relink` a rendue -- pure, non
    persistee. `refus` est `None` quand le relink peut aboutir ; sinon c'est le
    code du coeur, et :func:`ecrire_le_relink` refusera d'ecrire.

    `EPIC11-ARB-4` : le point de jugement precede toute ecriture. Un apercu
    calcule apres l'ecriture serait un panneau de resultat portant le titre « a
    ecrire » -- il ne pourrait plus rien empecher.
    """

    rush_id: str | None
    chemin: str | None = None
    manifeste: dict[str, Any] | None = None
    avertissements: tuple[str, ...] = ()
    refus: Refus | None = None

    @property
    def valide(self) -> bool:
        return self.refus is None


def preparer_relink(dossier_projet: Path | str, *, rush_id: str | None,
                    mode: str, cible: Path | str,
                    probe: Callable[[Path], relink.ProbeCandidat] =
                    relink.probe_reel) -> Apercu:
    """La sequence de `cli.relink_command`, **sans la derniere etape** (AC 4.2).

    Meme ordre, memes gardes, memes appels : le manifeste existe, il se lit,
    `resoudre_rush_id`, `charger_reference`, puis selon le mode
    `verifier_designation_manuelle` (et le chemin **resolu** de la cible) ou
    `rechercher_candidat`, puis `appliquer_relink`. Ce que la CLI fait ensuite
    -- `_atomic_write` -- est ici un appel **separe**, et c'est toute la
    difference : `EPIC11-ARB-4` exige le point de jugement avant l'ecriture.

    **Un seul `rush_id`, jamais une liste** (AC 4.4). Boucler ici sur les
    rushes manquants reimplanterait dans l'interface la logique d'appariement
    que `relink` porte deja (`EPIC11-ARB-32`).

    Ne leve jamais sur un refus du coeur : le refus voyage dans l'apercu, avec
    son **code**. Un ecran n'a pas a reconnaitre une phrase francaise pour
    savoir ce qui s'est passe.
    """
    _mode_connu(mode)
    dossier = Path(dossier_projet)
    chemin_manifeste = dossier / MANIFEST_FILENAME
    if not chemin_manifeste.is_file():
        return Apercu(rush_id=rush_id, refus=Refus(
            REFUS_MANIFESTE_ABSENT,
            MESSAGE_MANIFESTE_ABSENT.format(fichier=MANIFEST_FILENAME,
                                            dossier=dossier)))

    manifeste = projet_lecture.lire_manifeste(dossier)
    if manifeste is None:
        return Apercu(rush_id=rush_id, refus=Refus(
            REFUS_MANIFESTE_ILLISIBLE,
            MESSAGE_MANIFESTE_ILLISIBLE.format(chemin=chemin_manifeste,
                                               fichier=MANIFEST_FILENAME)))

    try:
        vise = relink.resoudre_rush_id(manifeste, rush_id)
        reference = relink.charger_reference(manifeste, vise)
        avertissements: tuple[str, ...] = ()
        if mode == MODE_DESIGNER:
            avertissements = tuple(relink.verifier_designation_manuelle(
                Path(cible), reference=reference, probe=probe))
            resolu = str(Path(cible).resolve())
        else:
            trouve = relink.rechercher_candidat(Path(cible),
                                                reference=reference, probe=probe)
            resolu = str(trouve.resolve())
        nouveau = relink.appliquer_relink(manifeste, vise, resolu)
    except relink.RelinkError as erreur:
        return Apercu(rush_id=rush_id,
                      refus=Refus(erreur.reason, str(erreur)))

    return Apercu(rush_id=vise, chemin=resolu, manifeste=nouveau,
                  avertissements=avertissements)


def ecrire_le_relink(dossier_projet: Path | str, apercu: Apercu) -> Path:
    """Persister l'apercu **valide**, et lui seul (AC 4.5).

    `_atomic_write` ecrit un temporaire dans le dossier projet, **valide**,
    puis remplace : un manifeste invalide laisse le `project.json` precedent
    strictement intact et ne laisse aucun temporaire.

    Un apercu porteur d'un refus leve :class:`EcritureRefusee` : « rien n'est
    ecrit tant que le relink n'est pas valide » est ici tenu par le type, pas
    par la discipline de l'appelant.
    """
    if not apercu.valide or apercu.manifeste is None:
        raise EcritureRefusee(
            "Rien n'est ecrit tant que le relink n'est pas valide (AC 4.5) ; "
            f"refus en cours : {apercu.refus.code if apercu.refus else 'aucun'}.")
    chemin = Path(dossier_projet) / MANIFEST_FILENAME
    _atomic_write(chemin, apercu.manifeste)
    return chemin


__all__ = [
    "ACTION_EXTRAIRE",
    "ACTION_RELINK",
    "AJOUTER_UN_RUSH",
    "CODES_DE_REFUS",
    "CODES_DE_REFUS_DU_COEUR",
    "ETATS_DE_PRESENCE",
    "HAUTEUR_LISTE",
    "ISSUE_REVENIR",
    "LIBELLES_APRES_REFUS",
    "LIBELLES_DE_MODE",
    "LIBELLE_ABSENT",
    "LIBELLE_LIE",
    "MANIFESTE_INCHANGE",
    "MODES",
    "MODE_DESIGNER",
    "MODE_RETROUVER",
    "MONTRER_FICHIERS",
    "MOTS_DE_MODE",
    "PHRASES_DE_MODE",
    "PHRASE_AJOUTER_UN_RUSH",
    "PRESENCES",
    "REFUS_MANIFESTE_ABSENT",
    "REFUS_MANIFESTE_ILLISIBLE",
    "SEPARATEUR",
    "SIGNE_MULTIPLIER",
    "TOUCHES_DE_MODE",
    "Apercu",
    "EcritureRefusee",
    "ListeDesRushes",
    "Refus",
    "Rush",
    "bandeau_de_relink",
    "bandeau_du_rush",
    "cadence_lisible",
    "duree_de_rush",
    "duree_lisible_de_secondes",
    "ecrire_le_relink",
    "issues_apres_refus",
    "lignes_des_modes",
    "lister",
    "preparer_relink",
    "reference_de_rush",
    "resume_de_reference",
    "rushes_du_manifeste",
    "titre_de_relink",
]
