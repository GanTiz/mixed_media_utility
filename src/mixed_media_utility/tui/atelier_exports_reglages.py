# -*- coding: utf-8 -*-
"""`E4-2` / `E4-2b` -- les reglages de l'encodage (story 11.8, lot D, AC 6).

**Ce module ne decide rien de ce qu'il affiche.** Les sept profils, leur
conteneur et celui qui est le defaut viennent de `codec_profiles.PROFILES` et
de `codec_profiles.DEFAULT_PROFILE_ID` ; le vocabulaire de resolution vient
d'`encode.known_resolution_ids`, `encode.NATIVE_RESOLUTION_KEYWORD` et
`encode.DEFAULT_RESOLUTION_ID` ; la cadence source du lot vient
d'`encode.resolve_source_rate`, avec son refus nomme
`ENCODE_SOURCE_RATE_MISSING` traite comme un **etat de l'ecran** et non comme
un plantage. Une frontiere negative mesure qu'aucun de ces mots ne vit en
litteral ici (AC 6.1, 6.3, 11.2).

**Le champ s'appelle « Cadence du rushe source »** (`EPIC11-ARB-192`, libelle
d'Egan verbatim, « rushe » compris), et ce nom EST la decision : le champ
**declare** la vraie cadence du rushe d'origine, il ne choisit aucune cadence
de sortie. Trois consequences que ce module tient :

* **aucun avertissement dans le cas nominal.** Un lot 12p5 ne d'un rushe 25p
  porte `timecode_base_fps = 25` : sa cadence source EST 25, rien n'est ecarte,
  et les frames tenues deux fois conservent la duree. La maquette d'avant
  posait un `▲` orange sur ce comportement-la ; c'etait un defaut, trouve par
  Egan ;
* **`fps_target` n'entre jamais ici.** C'est la decimation de l'extraction
  (12,5 sur le lot de demonstration), un parametre de **selection**, et
  `encode.resolve_frame_rate` dit lui-meme qu'elle « ne decide plus de rien qui
  touche a `-r` ». La seule cadence qui mux est `timecode_base_fps`, et c'est
  celle-la que l'ecran montre (AC 6.6) ;
* **`E4-2b` est l'etat du champ quand le lot n'en porte AUCUNE** -- planche en
  payload 2.0, ou manifest reconstruit d'une autre source. Ce n'est plus
  « quand le papier ment ».

**Le champ est REGLABLE** (`EPIC11-ARB-185`), prerempli par la valeur du lot.
Ce qui part au coeur en `cadence_source_override` est **`None` tant que la
valeur saisie ne diverge pas** de celle du lot : `encode.resolve_source_rate`
emet sinon sa note d'ecrasement pour une divergence qui n'existe pas -- defaut
du coeur mesure le 2026-09-03, que cette porte-ci evite de declencher sans le
corriger a sa place.

**Pas de colonne de famille de profil** (`EPIC11-ARB-187`, Egan : « Juste
`defaut` sur le profil par defaut. `secondary` n'apporte aucune
information »). Le profil par defaut porte la mention `défaut`, les six autres
ne portent rien -- ni `primary`/`secondary`, ni traduction. La categorie du
coeur n'est plus **affichee** ; elle n'est pas non plus **lue**, le defaut se
lisant a sa source (`DEFAULT_PROFILE_ID`).

**Aucune lettre n'est un raccourci** (`EPIC11-ARB-68`) : deux des trois champs
sont des champs de saisie, toute lettre frappee y entre, et `Tab` **nomme sa
destination** (« champ suivant »). **Le champ qui nommait le fichier de sortie
est retire**, et sa touche `e` avec lui (`EPIC11-ARB-141` :
`encode_master.encoder_le_master_du_lot` ne porte aucun parametre de ce genre --
mesure, pas supposition ; une frontiere negative le tient dans les deux sens).

**Une seule situation commande quatre surfaces** : le lot declare-t-il sa
cadence source ? Elle decide de la mention de droite du champ, de l'unite
affichee avec la valeur, du cartouche `▲`, de la ligne d'etat et du champ ou
le curseur s'ouvre. Une seule regle plutot que quatre, sans quoi elles
divergeraient au premier ajustement -- et l'ecran ne change pas d'aspect quand
le curseur se deplace, ce qui est exactement ce qu'un formulaire doit eviter.

**Ce module n'importe jamais `cli`** (`EPIC11-ARB-67`), et il n'ecrit rien : le
point d'entree de coeur est `encode_master.encoder_le_master_du_lot`, appele
par le parcours de l'atelier -- pas par un ecran de reglages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Mapping, Sequence

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from .. import codec_profiles, encode
from . import cadences, explorateur, jetons, projet_lecture
from .atelier_extraction import (Composition, _application_montee,
                                 ligne_de_titre)
from .coque import EcranPasEncore, ObjetTravaille, Palier

# ---------------------------------------------------------------------------
# Les textes de `E4-2` / `E4-2b`, verbatim des maquettes validees
# ---------------------------------------------------------------------------

#: Le titre de la zone centrale.
TITRE_DES_REGLAGES = "Réglages d'encodage"

LIBELLE_PROFIL = "Profil"
LIBELLE_RESOLUTION = "Résolution"

#: **Le libelle d'Egan, verbatim** (`EPIC11-ARB-192`), orthographe comprise. Il
#: est le plus long des quatre et c'est lui qui cale la colonne des valeurs :
#: l'abreger pour gagner deux colonnes reviendrait a defaire la decision, le
#: nom etant ce qui dit que le champ DECLARE au lieu de choisir.
LIBELLE_CADENCE = "Cadence du rushe source"

LIBELLE_ESPACE_COULEUR = "Espace couleur"

#: L'unite de la cadence, telle que la maquette l'ecrit.
UNITE_DE_CADENCE = "fps"

#: La mention de droite du champ de cadence, dans ses deux situations. La
#: seconde est celle de `E4-2b` : elle dit un FAIT du lot, jamais un conseil.
MENTION_CADENCE_DU_LOT = "déclarée par le lot"
MENTION_CADENCE_ABSENTE = "le lot n'en déclare aucune"

#: La mention de droite de la ligne de colorimetrie. Elle designe la **bonne**
#: source : la colorimetrie est portee par le profil (`ProfilDeCodec.colorspace`),
#: pas reinjectee depuis le manifest.
MENTION_ESPACE_COULEUR = "porté par le profil"

#: La mention du seul profil que le coeur retient sans qu'on lui demande. Elle
#: se pose sur `DEFAULT_PROFILE_ID` et sur rien d'autre : changer le defaut du
#: coeur deplace la mention toute seule.
MENTION_DU_DEFAUT = " · défaut"

#: La forme personnalisee de resolution, telle que `_parse_custom_resolution`
#: l'accepte. **Le `x` est un ASCII et non un `×`** : un glyphe plus joli ferait
#: saisir une valeur que le coeur refuse.
FORME_PERSONNALISEE = "<l>x<h>"

#: Le marqueur de liste deroulee du champ de profil. Il n'est **pas** un jeton
#: d'etat (`DESIGN.md` §6 n'en porte aucun de cette famille) : c'est un symbole
#: de texte, et son repli ASCII vit dans `jetons.REPLIS_DE_TEXTE` avec les
#: fleches -- sans quoi `--ascii` en ferait un `?`, exactement le defaut que
#: `×` a paye le 2026-08-29.
MARQUE_DEROULANT = "▾"

#: Les deux lignes du cartouche de `E4-2b`. **Un seul objet**, colorise
#: entierement (`EPIC11-ARB-71`) : un avertissement ne se colorise jamais une
#: ligne sur deux.
AVERTISSEMENT_CADENCE_ABSENTE = (
    "Ce lot vient d'une planche 2.0, qui n'imprimait pas la cadence",
    "du rushe. Sans cette déclaration, l'encodage n'a rien à muxer.",
)

#: L'etat qui teinte les deux cartouches d'avertissement de cet ecran. Un nom
#: de la table de `jetons`, jamais un dessin.
ETAT_DE_L_AVERTISSEMENT = "substitute"

#: La ligne de raccourcis quand le champ au focus offre un CHOIX -- le profil
#: (sept valeurs) et la resolution (le vocabulaire du coeur). C'est celle de
#: `E4-2`. `Tab` nomme sa **destination** et non l'objet qu'il quitte
#: (`EPIC11-ARB-68`) : dans un cycle de trois champs, la seule destination
#: vraie est le champ suivant.
#: MESURE: 63/68
RACCOURCIS_CHOIX = ("⏎ retenir  Tab champ suivant  ↑↓ choisir  "
                    "Échap retour  F1 aide")

#: La ligne de raccourcis quand le champ au focus ne se **saisit** que -- la
#: cadence du rushe source. C'est celle de `E4-2b`, et `↑↓ choisir` en tombe
#: parce qu'il n'y a rien a choisir : annoncer une touche qui ne fait rien est
#: la meme faute, en plus petit, que le `--nouvelle-version` d'un refus de
#: coeur qui ne l'offre pas.
#: MESURE: 51/56
RACCOURCIS_SAISIE = "⏎ retenir  Tab champ suivant  Échap retour  F1 aide"

#: Ce que `⏎` demande, quand l'ecran qui le sert n'existe pas encore. **Une
#: touche qui ne fait rien et ne dit rien est indistinguable d'un clavier
#: casse** : la garde structurelle des rappels
#: (`tests/unit/tui/test_rappels_cables.py`) existe pour attraper un
#: `if ... is not None` sans branche `else`.
CE_QUI_MANQUE_APRES_LES_REGLAGES = "Confirmer et encoder le master"
QUAND_LA_CONFIRMATION = "la confirmation de l'atelier Exports"

# ---------------------------------------------------------------------------
# Les deux lignes d'etat, et la SITUATION qui choisit entre elles
# ---------------------------------------------------------------------------

#: La ligne d'etat du cas nominal : **ce qui sera ecrit**. Aucune touche, aucun
#: conseil d'usage, aucun motif de conception (`EPIC11-ARB-56`, AC 6.7).
MOTIF_DE_LA_SORTIE = "{profil} · .{conteneur}"
#: Le segment de geometrie, absent quand la resolution demandee est `native` --
#: sa geometrie n'est connue qu'apres avoir sonde les frames.
MOTIF_DE_LA_GEOMETRIE = "{largeur}×{hauteur} à {cadence} {unite}"
#: Le segment de cadence seule, quand la geometrie n'est pas connue.
MOTIF_DE_LA_CADENCE = "à {cadence} {unite}"
#: Ce que le coeur a mesure du master a venir. Les segments inconnus
#: **disparaissent** : un poids inconnu ne s'ecrit pas `0 Go`.
MOTIF_DU_CONTENU = "{echantillons} échantillons"
MOTIF_DU_POIDS = "~ {poids}"

#: La ligne d'etat quand le lot ne declare aucune cadence : **les consequences
#: de ce qui vient d'etre declare**. C'est la seule verification que
#: l'operateur peut faire d'une valeur qu'aucun papier ne porte.
MOTIF_DES_FRAMES = "{frames} frames"
MOTIF_DES_MAINTIENS = "maintiens de {maintiens}"

#: Les separateurs des deux lignes d'etat, tels que les maquettes les ecrivent.
SEPARATEUR = " · "
SEPARATEUR_DU_CONTENU = " — "
SEPARATEUR_DES_MAINTIENS = " et "
SEPARATEUR_DU_POIDS = ", "

# ---------------------------------------------------------------------------
# La grille des maquettes. Ces colonnes sont celles du DESSIN valide.
# ---------------------------------------------------------------------------

#: Indentation des lignes de formulaire.
_INDENT = 5
#: Colonne des valeurs, **derivee du libelle le plus long** et jamais ecrite en
#: chiffre : c'est ce que le generateur des maquettes fait lui-meme
#: (`LIBELLE = len("Cadence du rushe source") + 4`), et deux redactions de la
#: meme colonne divergeraient a la premiere retouche du libelle.
_COLONNE_DE_LA_VALEUR = _INDENT + len(LIBELLE_CADENCE) + 4
#: Largeur de la valeur des trois champs courts, mention a sa droite.
_LARGEUR_DE_LA_VALEUR = 8
#: Largeur de la valeur du champ de profil, marqueur de deroulant a sa droite.
_LARGEUR_DU_PROFIL = 19
#: Indentation de la liste deroulee. `26 + len("▸ (•) ")` ramene l'identifiant
#: **exactement** a la colonne des valeurs : la liste s'ouvre sous le champ,
#: pas a cote.
_INDENT_DE_LA_LISTE = 26
#: Largeur de l'identifiant de profil dans la liste, conteneur a sa droite.
_LARGEUR_DE_L_IDENTIFIANT = 17
#: Retrait de la seconde ligne d'un cartouche d'avertissement, sous la
#: premiere : le glyphe ouvre une colonne, le texte reste aligne dessous.
_INDENT_DU_CARTOUCHE = 7

# ---------------------------------------------------------------------------
# Les champs, et l'ordre ou `Tab` les parcourt
# ---------------------------------------------------------------------------

CHAMP_PROFIL = "profil"
CHAMP_RESOLUTION = "resolution"
CHAMP_CADENCE = "cadence"

#: **`Espace couleur` n'est PAS un champ.** Les sept profils portent la meme
#: colorimetrie (mesure : `ProfilDeCodec.colorspace`), et un champ dont une
#: seule valeur existe n'est pas un reglage -- c'est l'argument exact par
#: lequel `Format · DPI` est tombe cote Pdf. La ligne reste **affichee**,
#: parce que ce que le master portera se lit ici avant la confirmation.
CHAMPS = (CHAMP_PROFIL, CHAMP_RESOLUTION, CHAMP_CADENCE)

#: Les champs ou `↑↓` retient une valeur voisine, donc ceux qui annoncent
#: `↑↓ choisir`.
CHAMPS_DE_CHOIX = (CHAMP_PROFIL, CHAMP_RESOLUTION)

#: Les champs ou une frappe s'ecrit. **La resolution est dans les deux**
#: (AC 6.3) : le vocabulaire du coeur se parcourt aux fleches, et la forme
#: personnalisee `<l>x<h>` se tape -- la retirer ferait de la TUI une surface
#: MOINS capable que la ligne de commande, ce que rien n'impose.
CHAMPS_DE_SAISIE = (CHAMP_RESOLUTION, CHAMP_CADENCE)


def _replie(texte: str, ascii_seul: bool = False) -> str:
    return jetons.replier_ascii(texte) if ascii_seul else texte


def _a_la_colonne(tete: str, colonne: int) -> str:
    """Completer ``tete`` de blancs jusqu'a ``colonne``, mesuree en COLONNES.

    Jamais `len()` : un ideogramme occupe deux colonnes, et toute la grille
    partirait avec lui.
    """
    return tete + " " * max(1, colonne - jetons.colonnes(tete))


# ---------------------------------------------------------------------------
# Ce que le COEUR dit du lot, lu chez lui
# ---------------------------------------------------------------------------

def cadence_source_du_lot(lot: Mapping[str, Any]) -> str | None:
    """La cadence source **exacte** du lot, ou `None` quand il n'en porte pas.

    **Elle est LUE du coeur** : `encode.resolve_source_rate` est la seule
    redaction du depot de « quelle cadence mux le master », et son refus nomme
    `ENCODE_SOURCE_RATE_MISSING` est ici traite comme un **etat de l'ecran** --
    c'est le cas de `E4-2b` -- plutot que comme un plantage.

    Tout autre refus **remonte** : une cadence source presente mais
    inexploitable (`ENCODE_FRAME_RATE_UNUSABLE`) n'est pas une cadence absente,
    et l'avaler ici ferait afficher « le lot n'en declare aucune » sur un lot
    qui en declare une, fausse. Deux etats differents, deux traitements.
    """
    try:
        _brute, exacte, _note = encode.resolve_source_rate(lot)
    except encode.EncodeDecisionError as refus:
        if refus.code == encode.ENCODE_SOURCE_RATE_MISSING:
            return None
        raise
    return exacte


def note_d_ecrasement(lot: Mapping[str, Any],
                      cadence_source_override: str | None) -> str | None:
    """L'avertissement structure du coeur, **rendu la ou il le rend**.

    `EPIC11-ARB-185`, verbatim : « Rien n'est reecrit cote TUI : l'avertissement
    se lit la ou le coeur le rend. » C'est
    `encode.resolve_source_rate(...)[2]` -- la note qui nomme les **deux**
    valeurs et leur provenance --, jamais une phrase de l'ecran.

    `None` quand rien ne diverge, et `None` aussi quand le coeur refuse : un
    ecran de reglages ne plante pas parce qu'on est en train de taper une
    valeur incomplete.
    """
    if cadence_source_override is None:
        return None
    try:
        return encode.resolve_source_rate(
            lot, cadence_source_override=cadence_source_override)[2]
    except encode.EncodeDecisionError:
        return None


@dataclass(frozen=True)
class LotAEncoder:
    """Le lot designe a `E4-1`, tel que les reglages ont besoin de le connaitre.

    Il porte le **document du lot** en plus de son identite : c'est lui que
    `encode.resolve_source_rate` lit, et le recopier en champs separes ferait
    de cet ecran une seconde redaction de ce que le coeur sait deja tirer d'un
    lot. C'est la meme raison qui fait porter `output_frames_dir` par
    `encode.EncodableLot` plutot que le laisser recalculer.
    """

    lot_id: str
    frames: int
    lot: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def du_manifest(cls, lot: Mapping[str, Any], frames: int) -> "LotAEncoder":
        """Depuis le document de lot que `encode.EncodableLot` transporte."""
        return cls(lot_id=str(lot.get("lot_id") or ""), frames=frames, lot=lot)

    @property
    def cadence_source(self) -> str | None:
        """La cadence source **exacte** du lot, lue du coeur, ou `None`."""
        return cadence_source_du_lot(self.lot)

    @property
    def declare_sa_cadence(self) -> bool:
        """**La situation qui commande quatre surfaces de cet ecran.**"""
        return self.cadence_source is not None


@dataclass(frozen=True)
class MesureDuMaster:
    """Ce que le COEUR a mesure du master a venir. **Rien n'est calcule ici.**

    Les quatre valeurs sortent du plan d'encodage -- la sequence reellement
    muxee, les maintiens de `encode._hold_counts`, la duree qui en decoule et
    le poids majorant d'`EncodePlan.estimated_bytes`. Les recalculer ici serait
    une seconde redaction de la seule chose que cet epic ne redige jamais deux
    fois ; et un ecran de reglages n'a pas de projet ouvert sous la main.

    Chaque champ est **facultatif** : un segment inconnu disparait de la ligne
    d'etat plutot que de sortir a zero.
    """

    echantillons: int | None = None
    #: Les maintiens, **tels que le coeur les rend** -- une valeur par frame
    #: retenue. Constants quand le rapport des cadences est entier, alternants
    #: sinon : l'ecran en rend l'ensemble ordonne, jamais le premier.
    maintiens: tuple[int, ...] = ()
    duree_s: float | None = None
    poids_octets: int | None = None


def texte_saisissable_de_cadence(valeur: Fraction) -> str:
    """L'ecriture d'une cadence qui **se relit sans rien perdre**.

    La valeur exacte du coeur (`25/1`) se lit mal ; c'est son ecriture decimale
    qui entre dans le champ, celle-la meme que l'operateur aurait tapee. Mais
    **une cadence NTSC n'a pas d'ecriture decimale finie** : `24000/1001` se
    rend `23,976`, qui se relit `2997/125`. Preremplir avec le rendu ferait
    alors diverger le champ de la valeur du lot sans que personne n'ait rien
    touche -- et l'ecran annoncerait un ecrasement de cadence sur le seul fait
    d'avoir ouvert un lot NTSC.

    La regle tient en un aller-retour : on rend le decimal quand la grammaire
    du depot le **relit a l'identique**, et la fraction reduite sinon. Aucune
    des deux ecritures n'est inventee ici -- `cadences.texte_de_cadence` rend
    la premiere, `cadences.analyser_la_saisie` accepte les deux.
    """
    decimal = cadences.texte_de_cadence(valeur)
    if cadences.analyser_la_saisie(decimal)[0] == valeur:
        return decimal
    return f"{valeur.numerator}/{valeur.denominator}"


def texte_de_duree(secondes: float | None) -> str | None:
    """`5,000 s` -> `5 s 00` -- la forme des maquettes de cet atelier.

    **C'est une troisieme forme, et elle n'est interchangeable avec aucune des
    deux autres** : `avancement.duree_lisible` dit une duree RESTANTE dans la
    grammaire du `DESIGN.md` §8 (`reste ~ 1 min 10`), `rushes.duree_de_rush`
    dit la longueur d'un rush en `M:SS`. Celle-ci dit la duree d'un master a la
    centieme, parce qu'un master de cinq secondes se compare a la duree du
    rushe dont il vient -- et que la seconde entiere y perd exactement ce qu'on
    veut verifier.

    Elle vit ici parce que `E4-2b` est le premier ecran a en avoir besoin ; les
    ecrans de confirmation et de resultat de cet atelier la **lisent** plutot
    que d'en ecrire une seconde.
    """
    if secondes is None or secondes < 0:
        return None
    entier = int(secondes)
    centiemes = int(round((secondes - entier) * 100))
    if centiemes == 100:            # 4,999 s ne devient pas `4 s 100`
        entier, centiemes = entier + 1, 0
    return f"{entier} s {centiemes:02d}"


# ---------------------------------------------------------------------------
# Le modele -- pur, sans `textual`, sans ecriture
# ---------------------------------------------------------------------------

@dataclass
class ReglagesDeL_encodage:
    """Le modele de `E4-2` : un profil, une resolution, une cadence declaree.

    **Modele pur**, comme `panneau.py` et `explorateur.py` : aucune dependance
    a `textual`, aucune ecriture. C'est ce qui rend mesurables sans terminal
    les deux appariements a risque de cet ecran -- la ligne rendue contre le
    profil qu'elle decrit, et ce qui part au coeur contre ce que l'operateur a
    frappe.

    **L'etat d'ouverture est celui du COEUR, jamais un nom recopie** (AC 6.1,
    6.3) : `codec_profiles.DEFAULT_PROFILE_ID` pour le profil,
    `encode.DEFAULT_RESOLUTION_ID` pour la resolution, et la cadence
    **prereglee par la valeur du lot** (`EPIC11-ARB-185`).
    """

    lot: LotAEncoder
    profil: str = codec_profiles.DEFAULT_PROFILE_ID
    resolution: str = encode.DEFAULT_RESOLUTION_ID
    #: Ce que l'operateur a frappe. Une **chaine** et non un nombre : le champ
    #: doit pouvoir etre vide, ce qu'aucun nombre ne sait dire, et c'est
    #: exactement l'etat de `E4-2b` a l'ouverture.
    cadence: str = ""
    champ: str = ""
    #: Ce que le coeur a mesure, quand quelqu'un l'a mesure. `None` est un
    #: etat normal : cet ecran s'ouvre avant tout plan.
    mesure: MesureDuMaster | None = None

    def __post_init__(self) -> None:
        if not self.cadence and self.lot.cadence_source is not None:
            # **Prerempli par la valeur du lot** (`EPIC11-ARB-185`), sans
            # jamais la degrader (voir :func:`texte_saisissable_de_cadence`).
            self.cadence = texte_saisissable_de_cadence(
                Fraction(self.lot.cadence_source))
        if not self.champ:
            # **Le curseur s'ouvre la ou il y a quelque chose a faire.** Un lot
            # qui ne declare pas sa cadence n'a qu'un champ obligatoire, et
            # ouvrir ailleurs obligerait a chercher lequel.
            self.champ = (CHAMP_PROFIL if self.lot.declare_sa_cadence
                          else CHAMP_CADENCE)

    # -- ce que le coeur porte ----------------------------------------------

    def profils(self) -> tuple[str, ...]:
        """Les sept identifiants, **dans l'ordre du coeur**, jamais tries."""
        return tuple(codec_profiles.PROFILES)

    def conteneur_de(self, profil: str) -> str:
        return codec_profiles.PROFILES[profil].container

    def est_le_defaut(self, profil: str) -> bool:
        """Le seul profil qui porte une mention (`EPIC11-ARB-187`).

        **Il se lit a `DEFAULT_PROFILE_ID` et non a la categorie** : la
        categorie du coeur n'est ni affichee ni lue, et un ecran qui la lirait
        pour deviner le defaut la ferait revenir par la fenetre.
        """
        return profil == codec_profiles.DEFAULT_PROFILE_ID

    def conteneur(self) -> str:
        return self.conteneur_de(self.profil)

    def colorimetrie(self) -> str:
        """La colorimetrie du master : elle est portee par le PROFIL."""
        return codec_profiles.PROFILES[self.profil].colorspace

    def vocabulaire_de_resolution(self) -> tuple[str, ...]:
        """Le vocabulaire du coeur, **plus** le mot-cle natif. Jamais recopie."""
        return (*encode.known_resolution_ids(),
                encode.NATIVE_RESOLUTION_KEYWORD)

    def glose_de_resolution(self) -> str:
        """Ce que le champ de resolution offre, forme personnalisee comprise."""
        return SEPARATEUR.join(
            (*self.vocabulaire_de_resolution(), FORME_PERSONNALISEE))

    def geometrie(self) -> tuple[int, int] | None:
        """La geometrie de sortie, **resolue par le coeur**, ou `None`.

        `None` couvre deux cas qu'il ne faut pas confondre a l'affichage mais
        qui se rendent pareil : `native`, dont la geometrie n'est connue
        qu'apres avoir sonde les frames, et une saisie que le coeur refuse.
        """
        try:
            return encode.resolve_output_resolution(self.resolution).size
        except encode.EncodeDecisionError:
            return None

    # -- la cadence declaree -------------------------------------------------

    def cadence_analysee(self) -> tuple[Fraction | None, str | None]:
        """`(valeur, motif de refus)` de ce qui est frappe dans le champ.

        **La grammaire n'est pas reecrite ici** : `cadences.analyser_la_saisie`
        est la seule redaction du depot de « ce que l'operateur a le droit de
        taper comme cadence », avec sa virgule decimale, ses divisions
        chiffrees et ses refus rediges. En ecrire une seconde accepterait ici
        ce que l'atelier Extraction refuse la.
        """
        return cadences.analyser_la_saisie(self.cadence)[::2]

    @property
    def cadence_retenue(self) -> Fraction | None:
        return self.cadence_analysee()[0]

    @property
    def refus_de_la_cadence(self) -> str | None:
        """Le motif du refus, **seulement quand quelque chose a ete frappe**.

        Un champ vide n'est pas une faute de frappe : c'est l'etat d'ouverture
        de `E4-2b`, et le cartouche le dit deja. Y ajouter un refus ferait deux
        messages pour un seul manque.
        """
        return self.cadence_analysee()[1] if self.cadence.strip() else None

    def cadence_source_transmise(self) -> str | None:
        """Ce qui part au coeur en `cadence_source_override`, ou `None`.

        **`None` tant que la valeur ne diverge pas de celle du lot**, et c'est
        le point qui ferme `EPIC11-ARB-192` point 2 : `resolve_source_rate`
        emet sa note d'ecrasement des que l'option est fournie, **meme
        identique** a la valeur du lot -- il annonce alors une divergence qui
        n'existe pas, sur le cas le plus frequent qui soit. Ne rien transmettre
        quand rien ne diverge evite de declencher ce defaut sans le corriger a
        la place du coeur.

        La comparaison se fait sur la **cadence exacte** du coeur
        (`codec_profiles.exact_frame_rate`), jamais sur le texte : `25`,
        `25,0` et `25/1` sont la meme cadence, et trois textes.
        """
        valeur = self.cadence_retenue
        if valeur is None:
            return None
        exacte = codec_profiles.exact_frame_rate(valeur)
        if exacte == self.lot.cadence_source:
            return None
        return exacte

    def note_du_coeur(self) -> str | None:
        """L'avertissement du coeur quand la valeur declaree diverge du lot."""
        return note_d_ecrasement(self.lot.lot,
                                 self.cadence_source_transmise())

    @property
    def peut_encoder(self) -> bool:
        """L'action principale est **inaccessible** tant qu'un champ requis est
        vide ou invalide (`DESIGN.md` §7.3).

        Les deux conditions sont celles du coeur, et pas une de plus : une
        cadence source que `resolve_source_rate` saurait employer, et une
        resolution que `resolve_output_resolution` sait resoudre. `native` est
        valide et rend `None` en geometrie -- d'ou la mesure sur le refus et
        non sur la taille.
        """
        if self.cadence_retenue is None:
            return False
        try:
            encode.resolve_output_resolution(self.resolution)
        except encode.EncodeDecisionError:
            return False
        return True

    # -- ecriture ------------------------------------------------------------

    def poser_le_profil(self, profil: str) -> bool:
        """Retenir un profil du coeur. Un identifiant inconnu n'entre pas.

        `EPIC11-ARB-17` : l'ecran « ne laisse jamais a l'ecran un couple que le
        coeur refuserait ».
        """
        if profil not in codec_profiles.PROFILES or profil == self.profil:
            return False
        self.profil = profil
        return True

    def poser_la_resolution(self, resolution: str) -> bool:
        if resolution == self.resolution:
            return False
        self.resolution = resolution
        return True

    def choisir(self, pas: int) -> bool:
        """`↑` / `↓` dans le champ au focus : la valeur voisine, **retenue**.

        Bornee et non circulaire : la liste des profils porte sept entrees, et
        un enroulement ferait passer du mezzanine par defaut a un profil de
        diffusion par une seule pression, sans que rien ne l'ait montre.

        Sur un champ de saisie pur -- la cadence -- les fleches ne font rien et
        la ligne de raccourcis ne les annonce pas.
        """
        if self.champ == CHAMP_PROFIL:
            return self._voisin(self.profils(), self.profil, pas,
                                self.poser_le_profil)
        if self.champ == CHAMP_RESOLUTION:
            vocabulaire = self.vocabulaire_de_resolution()
            if self.resolution not in vocabulaire:
                # Une resolution personnalisee est **hors du vocabulaire** : les
                # fleches y entrent par le bord vers lequel elles vont, plutot
                # que de ne rien faire -- une touche annoncee qui reste inerte
                # est indistinguable d'un clavier casse.
                return self.poser_la_resolution(
                    vocabulaire[0] if pas > 0 else vocabulaire[-1])
            return self._voisin(vocabulaire, self.resolution, pas,
                                self.poser_la_resolution)
        return False

    @staticmethod
    def _voisin(valeurs: Sequence, courante, pas: int,
                poser: Callable[..., bool]) -> bool:
        rang = valeurs.index(courante)
        vise = rang + pas
        if not 0 <= vise < len(valeurs):
            return False
        return poser(valeurs[vise])

    def avancer(self, pas: int = 1) -> bool:
        """Le champ suivant, en boucle. C'est `Tab`, et c'est ce qu'il annonce."""
        self.champ = CHAMPS[(CHAMPS.index(self.champ) + pas) % len(CHAMPS)]
        return True

    def frapper(self, caractere: str) -> bool:
        """Un caractere dans le champ de saisie au focus.

        **Toute lettre s'y ecrit** (`EPIC11-ARB-68`) : « aucune lettre n'est un
        raccourci dans un champ de saisie, sans exception et sans ordre de
        priorite a maintenir ». Filtrer les caracteres non numeriques serait
        une facon detournee de rendre une lettre inerte ; le champ les accepte
        et la validation les refuse, ce qui est visible.
        """
        if self.champ not in CHAMPS_DE_SAISIE or not caractere:
            return False
        setattr(self, self.champ, getattr(self, self.champ) + caractere)
        return True

    def effacer(self) -> bool:
        if self.champ not in CHAMPS_DE_SAISIE or not getattr(self, self.champ):
            return False
        setattr(self, self.champ, getattr(self, self.champ)[:-1])
        return True

    def entrer(self) -> bool:
        """`⏎ retenir` : le formulaire est-il complet ?

        Il n'y a **pas de bouton `Valider`** sur cet ecran -- la maquette
        validee n'en dessine aucun --, donc `⏎` est le geste qui retient les
        reglages et ouvre la confirmation. Il ne le fait pas quand le coeur
        refuserait ce qui est a l'ecran (`EPIC11-ARB-17`), auquel cas la ligne
        d'etat porte le motif plutot que de laisser la touche muette.
        """
        return self.peut_encoder

    # -- rendu ---------------------------------------------------------------

    def raccourcis(self) -> str:
        """La ligne de raccourcis, **contextuelle** (`DESIGN.md` §4)."""
        return (RACCOURCIS_CHOIX if self.champ in CHAMPS_DE_CHOIX
                else RACCOURCIS_SAISIE)

    def ligne_du_profil(self, ascii_seul: bool = False) -> str:
        """`Profil   prores_hq   ▾  .mov` -- le champ, deroulant ferme ou non.

        Le champ ne porte **jamais** le glyphe d'invite : quand il a le focus,
        sa liste s'ouvre dessous et c'est le curseur de la liste qui dit ou on
        est. Deux marques pour un seul focus se liraient comme deux focus.
        """
        tete = _a_la_colonne(" " * _INDENT + _replie(LIBELLE_PROFIL, ascii_seul),
                             _COLONNE_DE_LA_VALEUR)
        valeur = _a_la_colonne(tete + self.profil,
                               _COLONNE_DE_LA_VALEUR + _LARGEUR_DU_PROFIL)
        return _replie(f"{valeur}{MARQUE_DEROULANT}  .{self.conteneur()}",
                       ascii_seul)

    def lignes_de_la_liste(self, ascii_seul: bool = False) -> list[str]:
        """Les sept profils, **construits** et jamais ecrits (AC 6.1).

        `EPIC11-ARB-180` commande la forme : un champ exclusif de formulaire
        **qui a le focus** porte les deux glyphes -- la fleche dit ou est le
        curseur, la puce ce qui est retenu. `EPIC11-ARB-126` (« Flèche
        seule ! ») n'est pas renverse : il ne regit que les listes d'ISSUES, et
        celle-ci n'en est pas une.
        """
        glyphes = jetons.glyphes(ascii_seul)
        lignes = []
        for profil in self.profils():
            vise = profil == self.profil
            tete = (f"{glyphes['curseur']} {glyphes['exclusif-retenu']}" if vise
                    else f"  {glyphes['exclusif-libre']}")
            mention = MENTION_DU_DEFAUT if self.est_le_defaut(profil) else ""
            lignes.append(_replie(
                f"{' ' * _INDENT_DE_LA_LISTE}{tete} "
                f"{profil:<{_LARGEUR_DE_L_IDENTIFIANT}}"
                f".{self.conteneur_de(profil)}{mention}", ascii_seul))
        return lignes

    def ligne_de_champ(self, libelle: str, valeur: str, mention: str,
                       au_focus: bool, ascii_seul: bool = False) -> str:
        """Une ligne de formulaire : libelle, glyphe de focus, valeur, mention.

        Le glyphe `>` marque la ligne **au focus** (`DESIGN.md` §7.3), et il
        ouvre sa colonne : les autres lignes portent des blancs a sa place,
        pour que les valeurs restent alignees quand le focus se deplace.
        """
        glyphes = jetons.glyphes(ascii_seul)
        tete = " " * _INDENT + _replie(libelle, ascii_seul)
        if au_focus:
            tete = (_a_la_colonne(tete, _COLONNE_DE_LA_VALEUR - 2)
                    + f"{glyphes['invite']} ")
        else:
            tete = _a_la_colonne(tete, _COLONNE_DE_LA_VALEUR)
        corps = _a_la_colonne(tete + _replie(valeur, ascii_seul),
                              _COLONNE_DE_LA_VALEUR + _LARGEUR_DE_LA_VALEUR)
        return (corps + _replie(mention, ascii_seul)).rstrip()

    def valeur_de_la_cadence(self, ascii_seul: bool = False) -> str:
        """Ce que le champ de cadence affiche.

        **L'unite suit la SITUATION, pas le curseur** : un lot qui declare sa
        cadence porte une valeur retenue, qui se lit avec son unite ; un lot
        qui n'en declare aucune porte ce que l'operateur est en train de
        frapper, et rien d'autre. Un champ dont l'aspect changerait au passage
        du curseur se lirait comme deux champs.

        Le glyphe `neutre` -- et jamais une chaine vide -- marque un champ non
        renseigne : `DESIGN.md` §6 en fait le second canal de « rien ici », et
        une case vide se lit comme un defaut de rendu.
        """
        neutre = jetons.glyphes(ascii_seul)["neutre"]
        saisie = self.cadence.strip()
        if not self.lot.declare_sa_cadence:
            return saisie or neutre
        valeur = self.cadence_retenue
        if valeur is None:
            return saisie or neutre
        return f"{cadences.texte_de_cadence(valeur, ascii_seul)} {UNITE_DE_CADENCE}"

    def mention_de_la_cadence(self) -> str:
        return (MENTION_CADENCE_DU_LOT if self.lot.declare_sa_cadence
                else MENTION_CADENCE_ABSENTE)

    def lignes_des_champs(self, ascii_seul: bool = False) -> list[str]:
        """Les trois lignes courtes, plus la colorimetrie qui n'en est pas un."""
        return [
            self.ligne_de_champ(
                LIBELLE_RESOLUTION, self.resolution,
                self.glose_de_resolution(),
                self.champ == CHAMP_RESOLUTION, ascii_seul),
            self.ligne_de_champ(
                LIBELLE_CADENCE, self.valeur_de_la_cadence(ascii_seul),
                self.mention_de_la_cadence(),
                self.champ == CHAMP_CADENCE, ascii_seul),
            self.ligne_de_champ(
                LIBELLE_ESPACE_COULEUR, self.colorimetrie(),
                MENTION_ESPACE_COULEUR, False, ascii_seul),
        ]

    def lignes_du_cartouche(self, utile: int,
                            ascii_seul: bool = False) -> list[str]:
        """Le cartouche `▲`, ou rien du tout.

        **Trois cas, et le premier est le cas nominal** (`EPIC11-ARB-192`) : un
        lot qui porte sa cadence source et qu'on ne corrige pas n'a **rien** a
        signaler, et l'ecran ne dit rien. Les deux autres sont le lot qui n'en
        porte aucune -- le texte de `E4-2b` -- et la valeur declaree qui
        diverge de celle du lot, ou c'est **le coeur** qui redige.
        """
        if not self.lot.declare_sa_cadence:
            phrases = list(AVERTISSEMENT_CADENCE_ABSENTE)
        else:
            note = self.note_du_coeur()
            if note is None:
                return []
            phrases = jetons.envelopper(
                note, utile - _INDENT_DU_CARTOUCHE, ascii_seul)
        if not phrases:
            # Un cartouche vide n'est pas un cartouche : sur une zone trop
            # etroite, `envelopper` ne rend rien, et poser le glyphe seul
            # afficherait un `▲` qui n'avertit de rien.
            return []
        glyphe = jetons.glyphes(ascii_seul)["substitute"]
        premiere = f"{' ' * _INDENT}{glyphe} {phrases[0]}"
        suivantes = [f"{' ' * _INDENT_DU_CARTOUCHE}{phrase}"
                     for phrase in phrases[1:]]
        return [_replie(ligne, ascii_seul)
                for ligne in [premiere, *suivantes]]

    def etats_du_cartouche(self, depart: int, hauteur: int) -> dict[int, str]:
        """L'etat DONNE de chaque ligne du cartouche (`EPIC11-ARB-71`).

        **Toutes les lignes, jamais la seule qui porte le glyphe** : un
        avertissement se colorise entierement, et la reconnaissance par motif
        de `jetons.peindre` ne verrait que la premiere.
        """
        return {depart + rang: ETAT_DE_L_AVERTISSEMENT
                for rang in range(hauteur)}

    # -- la ligne d'etat -----------------------------------------------------

    def ligne_de_la_sortie(self, ascii_seul: bool = False) -> str:
        """`prores_hq · .mov · 1920×1080 à 25 fps — 124 échantillons, ~ 1,4 Go`.

        Ce qui **sera ecrit**, et rien d'autre. Les segments que personne n'a
        mesures disparaissent : un poids inconnu ne s'ecrit pas `0 Go`, et une
        geometrie native ne s'invente pas avant d'avoir sonde les frames.
        """
        segments = [MOTIF_DE_LA_SORTIE.format(profil=self.profil,
                                              conteneur=self.conteneur())]
        cadence = self.cadence_retenue
        geometrie = self.geometrie()
        if cadence is not None and geometrie is not None:
            segments.append(MOTIF_DE_LA_GEOMETRIE.format(
                largeur=geometrie[0], hauteur=geometrie[1],
                cadence=cadences.texte_de_cadence(cadence, ascii_seul),
                unite=UNITE_DE_CADENCE))
        elif cadence is not None:
            segments.append(MOTIF_DE_LA_CADENCE.format(
                cadence=cadences.texte_de_cadence(cadence, ascii_seul),
                unite=UNITE_DE_CADENCE))
        tete = SEPARATEUR.join(segments)
        contenu = self._contenu_du_master()
        return _replie(tete if not contenu
                       else tete + SEPARATEUR_DU_CONTENU + contenu, ascii_seul)

    def _contenu_du_master(self) -> str:
        """`124 échantillons, ~ 1,4 Go` -- ce que le coeur a mesure, ou rien."""
        if self.mesure is None:
            return ""
        segments = []
        if self.mesure.echantillons is not None:
            segments.append(MOTIF_DU_CONTENU.format(
                echantillons=self.mesure.echantillons))
        if self.mesure.poids_octets is not None:
            segments.append(MOTIF_DU_POIDS.format(
                poids=explorateur.taille_lisible(self.mesure.poids_octets)))
        return SEPARATEUR_DU_POIDS.join(segments)

    def texte_des_maintiens(self) -> str | None:
        """`2`, ou `1 et 2` -- **l'ensemble ordonne**, jamais le premier.

        `encode._hold_counts` rend un maintien par frame retenue : constant
        quand le rapport des cadences est entier, **alternant** entre deux
        valeurs sinon (le module le dit et le verrouille). Afficher le premier
        ferait lire « maintiens de 1 » sur une sequence qui en tient aussi des
        2 -- une mesure fausse sur la moitie des frames.
        """
        if self.mesure is None or not self.mesure.maintiens:
            return None
        return SEPARATEUR_DES_MAINTIENS.join(
            str(valeur) for valeur in sorted(set(self.mesure.maintiens)))

    def ligne_des_consequences(self, ascii_seul: bool = False) -> str:
        """`plan-04_12p5 · 63 frames · maintiens de 2 · 125 échantillons · 5 s 00`.

        La ligne d'etat du lot qui ne declare aucune cadence : **les
        consequences de ce qui vient d'etre declare**. C'est la seule
        verification possible d'une valeur qu'aucun papier ne porte, et c'est
        pour ca qu'elle remplace l'annonce de la sortie plutot que de s'y
        ajouter.
        """
        segments = [self.lot.lot_id,
                    MOTIF_DES_FRAMES.format(frames=self.lot.frames)]
        maintiens = self.texte_des_maintiens()
        if maintiens is not None:
            segments.append(MOTIF_DES_MAINTIENS.format(maintiens=maintiens))
        if self.mesure is not None and self.mesure.echantillons is not None:
            segments.append(MOTIF_DU_CONTENU.format(
                echantillons=self.mesure.echantillons))
        duree = texte_de_duree(None if self.mesure is None
                               else self.mesure.duree_s)
        if duree is not None:
            segments.append(duree)
        return _replie(SEPARATEUR.join(segments), ascii_seul)

    def ligne_d_etat(self, ascii_seul: bool = False) -> str:
        """La ligne d'etat : une **mesure**, jamais une touche (`EPIC11-ARB-56`).

        Un refus de saisie passe devant : il est ce que l'operateur doit lire
        avant tout le reste, et il est redige par la grammaire de cadence du
        depot, jamais ici.
        """
        refus = self.refus_de_la_cadence
        if refus is not None:
            return _replie(refus, ascii_seul)
        if self.lot.declare_sa_cadence:
            return self.ligne_de_la_sortie(ascii_seul)
        return self.ligne_des_consequences(ascii_seul)

    def objet_du_bandeau(self, ascii_seul: bool = False) -> str:
        """`plan-04_25 · 124 f` -- la DROITE du bandeau, composee du lot."""
        return _replie(f"{self.lot.lot_id}{SEPARATEUR}{self.lot.frames} f",
                       ascii_seul)


# ---------------------------------------------------------------------------
# `E4-2` / `E4-2b` -- l'ecran
# ---------------------------------------------------------------------------

class EcranReglagesDeL_encodage(ObjetTravaille, Palier):
    """`E4-2` -- les reglages de l'encodage.

    L'ecran ne mesure rien, ne resout rien et ne juge rien : il branche le
    modele ci-dessus sur le clavier et sur la seule issue de l'ecran, `⏎`.
    **Il n'importe jamais `cli.py`** (`EPIC11-ARB-67`).
    """

    titre = projet_lecture.EXPORTS
    #: La ligne de raccourcis d'ouverture. Elle est **reassignee a chaque
    #: dessin** par :meth:`poser_les_raccourcis`, l'idiome du depot pour une
    #: ligne contextuelle. Une `property` aurait fait la meme chose et **casse
    #: le balayage du paquet** : `test_majuscules_des_raccourcis` lit cet
    #: attribut de CLASSE et attend une chaine.
    raccourcis = RACCOURCIS_CHOIX
    #: Une station du parcours : on y revient depuis la confirmation, et
    #: `Échap` ramene a la designation du lot.
    TRANSITOIRE = False
    ID_DU_CORPS = "corps-reglages-exports"

    def __init__(self, reglages: ReglagesDeL_encodage,
                 continuer: Callable[[ReglagesDeL_encodage], None] | None = None
                 ) -> None:
        super().__init__()
        self.reglages = reglages
        self._continuer = continuer

    # -- lecture --------------------------------------------------------------

    def poser_les_raccourcis(self) -> str:
        """Contextuelle : `↑↓ choisir` disparait sur un champ de saisie pur."""
        self.raccourcis = self.reglages.raccourcis()
        return self.raccourcis

    def composer(self, largeur: int, ascii_seul: bool = False
                 ) -> tuple[list[str], int | None, dict[int, str]]:
        """Le corps de `E4-2`, **sous la hauteur de la zone centrale**."""
        utile = jetons.largeur_utile(largeur)
        composition = Composition()
        composition.respirer()
        composition.poser(ligne_de_titre(TITRE_DES_REGLAGES, ascii_seul))
        composition.respirer()
        composition.poser(self.reglages.ligne_du_profil(ascii_seul))
        if self.reglages.champ == CHAMP_PROFIL:
            # **La liste ne s'ouvre que sous le champ qui a le focus.** Elle
            # est ouverte sur `E4-2` (le profil a le focus) et fermee sur
            # `E4-2b` (c'est la cadence qui l'a) : c'est le meme ecran a deux
            # instants, pas deux ecrans.
            composition.poser(*self.reglages.lignes_de_la_liste(ascii_seul))
            composition.respirer()
        composition.poser(*self.reglages.lignes_des_champs(ascii_seul))
        cartouche = self.reglages.lignes_du_cartouche(utile, ascii_seul)
        if cartouche:
            composition.respirer()
            composition.bloc(cartouche,
                             etats=self.reglages.etats_du_cartouche(
                                 0, len(cartouche)))
        return composition.rendu()

    def lignes(self) -> list[str]:
        return self.composer(self.app.size.width, self.app.ascii_seul)[0]

    def etat(self) -> str:
        return self.reglages.ligne_d_etat(self.app.ascii_seul)

    def objet_du_bandeau(self) -> str:
        """Le lot travaille, **rendu au moment de dessiner** et jamais ecrit
        dans la session : l'objet travaille change d'un ecran a l'autre, et
        l'ecrire dans le contexte le ferait survivre au palier qui l'a pose."""
        application = _application_montee(self)
        return self.reglages.objet_du_bandeau(
            bool(getattr(application, "ascii_seul", False)))

    # -- rendu ----------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id=self.ID_DU_CORPS)
        return [Vertical(self._corps, id=f"centre-{self.ID_DU_CORPS}")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur = jetons.largeur_utile(self.app.size.width)
        self.poser_les_raccourcis()
        lignes, rang, etats = self.composer(self.app.size.width,
                                            self.app.ascii_seul)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, largeur, self.app.ascii_seul)
             for ligne in lignes],
            ascii_seul=self.app.ascii_seul,
            sans_couleur=self.app.sans_couleur,
            ligne_du_curseur=rang,
            etats=etats))
        self.poser_etat(self.etat())
        super().rafraichir()

    def on_mount(self) -> None:
        self.rafraichir()

    # -- clavier --------------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier, comme tous les ecrans du depot.

        **L'ordre compte** : les touches nommees d'abord, la frappe ensuite.
        Aucune lettre n'est testee avant d'atteindre le champ de saisie
        (`EPIC11-ARB-68`), et c'est ce qui garantit qu'un `n` de `native`
        s'ecrit au lieu d'ouvrir quoi que ce soit.
        """
        if touche in ("up", "down"):
            self.reglages.choisir(-1 if touche == "up" else 1)
            return True
        if touche in ("tab", "shift+tab"):
            self.reglages.avancer(-1 if touche == "shift+tab" else 1)
            return True
        if touche == "backspace":
            return self.reglages.effacer()
        if touche == "enter":
            if not self.reglages.entrer():
                # Le refus est **dit** par la ligne d'etat, redessinee : une
                # touche annoncee qui ne fait rien et ne dit rien est
                # indistinguable d'un clavier casse.
                return True
            if self._continuer is not None:
                self._continuer(self.reglages)
            else:
                self._pas_encore()
            return True
        if caractere and caractere.isprintable():
            return self.reglages.frapper(caractere)
        return False

    def _pas_encore(self) -> None:
        """`⏎` sans appelant : on le DIT plutot que de rendre la touche muette.

        **En production, cette branche n'est plus atteinte depuis le lot B5**
        (2026-09-03) : `ParcoursExports.designer` injecte `continuer=`, et `⏎`
        mene a la confirmation `E4-3` -- ou a `E4-3b` d'abord quand un master
        existe deja. Elle reste pour l'ecran construit **a nu** par un banc,
        ou l'absence ne doit toujours pas se taire : c'est la consigne d'Egan
        du 2026-08-28, « quitte a ne mener nulle part [...] comme ca on sait
        que c'est temporaire et que ce n'est pas un bug ».
        """
        application = _application_montee(self)
        if application is None:
            # Un ecran construit a nu par un banc n'a pas d'application ou
            # descendre : il n'y a rien a montrer, et rien a taire non plus.
            return
        application.descendre(EcranPasEncore(CE_QUI_MANQUE_APRES_LES_REGLAGES,
                                             QUAND_LA_CONFIRMATION))


__all__ = [
    "AVERTISSEMENT_CADENCE_ABSENTE",
    "CE_QUI_MANQUE_APRES_LES_REGLAGES",
    "CHAMPS",
    "CHAMPS_DE_CHOIX",
    "CHAMPS_DE_SAISIE",
    "CHAMP_CADENCE",
    "CHAMP_PROFIL",
    "CHAMP_RESOLUTION",
    "ETAT_DE_L_AVERTISSEMENT",
    "EcranReglagesDeL_encodage",
    "FORME_PERSONNALISEE",
    "LIBELLE_CADENCE",
    "LIBELLE_ESPACE_COULEUR",
    "LIBELLE_PROFIL",
    "LIBELLE_RESOLUTION",
    "LotAEncoder",
    "MARQUE_DEROULANT",
    "MENTION_CADENCE_ABSENTE",
    "MENTION_CADENCE_DU_LOT",
    "MENTION_DU_DEFAUT",
    "MENTION_ESPACE_COULEUR",
    "MesureDuMaster",
    "QUAND_LA_CONFIRMATION",
    "RACCOURCIS_CHOIX",
    "RACCOURCIS_SAISIE",
    "ReglagesDeL_encodage",
    "TITRE_DES_REGLAGES",
    "UNITE_DE_CADENCE",
    "cadence_source_du_lot",
    "note_d_ecrasement",
    "texte_de_duree",
    "texte_saisissable_de_cadence",
]
