# -*- coding: utf-8 -*-
"""`E5-1` -- quels lots mettre en planches (story 11.7, lot D, AC 4).

**La liste a cocher de l'atelier Pdf**, et le second site du motif que la story
11.4 avait ecrit pour un seul usage : `cadences.ListeDeCadences` naissait modele
pur « parce que la story 11.7 (multi-lots Pdf) le reutilisera ». C'est ici que
la promesse se tient -- la forme est reprise (`basculer` sur `Espace`,
`nombre_de_coches`, `frames_cochees`, une fenetre calculee par `jetons`), la
matiere change : des lots lus d'un manifest la ou l'autre porte des cadences
calculees par le coeur.

**Ce module ne juge aucun lot.** `EPIC11-ARB-30` gouverne ici comme partout :
le verdict de conformite vient de `io.extraction_manifest.verify_extracted_lot`,
appele au COEUR, et la TUI ne fait que l'AFFICHER (AC 4.4) -- elle ne rejoue ni
le comptage de frames, ni la verification des noms de fichiers. Un lot que le
coeur declare non conforme **reste cochable** : c'est la confirmation, plus
loin dans le parcours, qui dit ce qui manque.

**Aucune seconde lecture, aucun `glob`** (AC 4.2). Tout ce que l'ecran montre --
le nom, le cardinal de frames, la date d'extraction -- se lit du manifest
**deja charge** par `projet_lecture.lire_manifeste`. Une liste qui irait
compter les TIFF sur le disque mesurerait autre chose que ce que le document
declare, et le ferait a chaque frappe de fleche.

**Ce que le bloc « Le lot survolé » NE porte PAS, et c'est un retour d'Egan du
2026-09-02, verbatim** : « Enlevons-juste geometrie et cadence. La cadence ne
joue pas sur une planche c'est le lot qui la determine. La geometrie n'est pas
reglable on ne l'affiche pas. C'est le nombre de frames (c'est un total ?) qui
nous interesse. » Les deux lignes que la fiche de story annoncait -- `Cadence`
et `Géométrie` -- n'existent donc pas, et la remontee du `rush_id` vers
`rushes[].resolution_source` qu'elles auraient exigee n'est pas ecrite : un
champ qu'aucun ecran ne montre est une surface morte.

**Reponse a sa parenthese, puisqu'elle porte sur un appariement** : le cardinal
du filet est celui du **lot survole**, jamais un total. Le total, lui, est en
ligne d'etat (`2 lots cochés · 164 frames`), et le filet est precisement ce qui
separe les deux. Les deux nombres sont donc calcules par deux chemins
differents -- l'un lit le lot sous le curseur, l'autre somme les coches -- et un
banc les mesure sur une fabrique ou ils ne peuvent pas se confondre.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from ..io.naming import CANONICAL_ID_MAX_LENGTH
from . import jetons, projet_lecture
from .atelier_extraction import (Composition, _application_montee,
                                 filet_titre, ligne_de_titre)
from .coque import EcranPasEncore, ObjetTravaille, Palier
from .projet_lecture import accorder, date_courte

# ---------------------------------------------------------------------------
# Les textes de `E5-1`, verbatim de la maquette validee
# ---------------------------------------------------------------------------

#: La question de l'ecran. Recopiee au caractere pres, accents compris.
TITRE_DES_LOTS = "Quels lots mettre en planches ?"

#: Le titre du filet qui separe la liste des faits du lot sous le curseur.
#: La forme -- un bloc de faits techniques SOUS filet, en bas de l'ecran -- est
#: celle de `E4-1` (« Le lot désigné »), deja approuvee ; elle vient de la
#: note 1 d'Egan du 2026-09-01 : « les infos techniques du lot survole peuvent
#: aller en bas de l'interface ».
FILET_DU_SURVOL = "Le lot survolé"

#: `EPIC11-ARB-45` / `-126`, verbatim : « **Flèche seule !** C'est uniquement
#: dans les listes a cocher qu'on trouve les deux. » Cet ecran EST une liste a
#: cocher : il porte donc les deux, la case **et** la fleche, et sa ligne de
#: raccourcis annonce `Espace` -- ce qu'aucun ecran a issue unique ne fait.
#: MESURE: 64/69
RACCOURCIS_LOTS = ("Espace cocher  ⏎ continuer  ↑↓ naviguer  "
                   "Échap menu Pdf  F1 aide")

#: Le libelle du seul fait que le filet porte.
LIBELLE_DES_FRAMES = "Frames"

#: La mention de droite du filet. `{date}` est un jour et un mois, sans heure :
#: c'est ce que la maquette montre, et la date complete vit deja en ligne de
#: pied du menu de l'atelier.
MENTION_EXTRAITES = "extraites le {date}"

#: Ce que `⏎ continuer` demande, quand l'ecran qui le sert n'existe pas encore.
#: **L'absence NE SE TAIT PAS** : c'est le mode de panne que
#: `tests/unit/tui/test_rappels_cables.py` a paye sept fois -- un rappel
#: optionnel qu'aucun appel n'injecte, et un `if ... is not None` qui
#: transforme le manque en silence. Ici la touche mene a un ecran « pas
#: encore » qui nomme ce qui manque et son echeance.
CE_QUI_MANQUE_APRES_LES_LOTS = "Choisir la mise en page"
QUAND_LES_REGLAGES = "les reglages de planche de l'atelier Pdf"

#: AC 4.3 : une validation a zero coche ne passe **jamais** en silence. C'est
#: `cadences.MOTIF_AUCUNE_COCHEE` transpose -- meme forme, meme absence
#: d'accent que ses voisins de refus, et un geste suivant nomme.
MOTIF_AUCUN_LOT_COCHE = ("Refuse : aucun lot coche, il n'y a rien a mettre "
                         "en planches.")

# ---------------------------------------------------------------------------
# La geometrie, relevee sur la maquette
# ---------------------------------------------------------------------------

#: Hauteur FIXE de la zone de liste, `…` compris.
#:
#: **Elle est DERIVEE de la maquette et non choisie** : `E5-1` pose le filet
#: « Le lot survolé » a la ligne 12 de la fenetre, ce qui laisse exactement
#: cinq lignes a la liste une fois le blanc de tete, le titre et le blanc qui
#: le suit poses. Une hauteur variable ferait danser le filet -- et le fait du
#: lot survole avec lui -- a chaque projet, or « une cible qui se deplace quand
#: la liste change de longueur est une cible qu'on rate ».
HAUTEUR_LISTE = 5

#: Largeur de la colonne des noms de lot.
#:
#: **Elle se lit du coeur, elle ne se recopie pas** : c'est la borne du produit
#: (`io.naming.CANONICAL_ID_MAX_LENGTH`), pas la longueur du plus long nom de
#: la demonstration. C'est la note 1 d'Egan du 2026-09-01, verbatim : « l'espace
#: pour le nom d'un lot est tres limite [...] les noms sont bien plus longs dans
#: mes projets ». Une colonne calee sur la demonstration retrecit des que la
#: demonstration change, ce qui est exactement la panne constatee.
LARGEUR_DU_NOM = CANONICAL_ID_MAX_LENGTH

#: Largeur du libelle du filet : `Frames` cale sa valeur en colonne 26 sur la
#: maquette, l'indentation du bloc valant :data:`_INDENT`.
LARGEUR_DU_LIBELLE = 21

#: Largeur de la valeur du filet : `124` puis la mention en colonne 43.
LARGEUR_DE_LA_VALEUR = 17

#: Colonne ou commence la tete d'une ligne de liste -- trois blancs, le
#: curseur, un blanc, la case, un blanc --, exactement celle de
#: `cadences._INDENT` : les deux listes a cocher du produit s'alignent.
_INDENT = 5
#: Deux colonnes de respiration au bord droit, comme partout ailleurs.
_MARGE_DROITE = 2
#: Largeur de la case a cocher, `[x]` comme `[ ]`.
_LARGEUR_DE_LA_CASE = 3

# ---------------------------------------------------------------------------
# Le verdict du coeur, AFFICHE et jamais rejoue (AC 4.4)
# ---------------------------------------------------------------------------

#: Les deux etats qu'un lot peut porter en colonne de droite, et leur libelle.
#: `complet` est le mot de `E5-1` ; `incomplet` celui de `E4-1`, l'ecran frere
#: qui liste les memes lots pour l'encodage. Deux vocabulaires pour un meme
#: verdict a deux ecrans d'ecart, c'est le defaut que la story 11.4 a paye sur
#: `source / N`.
ETAT_CONFORME = "complete"
MENTION_CONFORME = "complet"
ETAT_NON_CONFORME = "absent"
MENTION_NON_CONFORME = "incomplet"


class LotsMalFormes(ValueError):
    """Un invariant que la revue ne devrait pas avoir a trouver est viole."""


@dataclass(frozen=True)
class Verdict:
    """Ce que le coeur dit d'un lot : un etat, et le mot qui l'accompagne.

    ``etat`` est une **cle** de :data:`jetons.GLYPHES`, jamais un dessin : le
    repli ASCII doit rendre le meme sens, et un `●` ecrit ici serait invisible
    en `--ascii`.
    """

    etat: str = ETAT_CONFORME
    mention: str = MENTION_CONFORME

    def __post_init__(self) -> None:
        if self.etat not in jetons.NOMS_D_ETAT:
            connus = ", ".join(jetons.NOMS_D_ETAT)
            raise LotsMalFormes(
                f"etat de lot inconnu : {self.etat!r}. Connus : {connus}")

    def rendu(self, ascii_seul: bool = False) -> str:
        """`● complet`, ou son repli. Le glyphe et le mot, jamais l'un sans
        l'autre : c'est le second canal de `DESIGN.md` section 6."""
        return jetons.marque(self.etat, _replie(self.mention, ascii_seul),
                             ascii_seul)


VERDICT_CONFORME = Verdict(ETAT_CONFORME, MENTION_CONFORME)
VERDICT_NON_CONFORME = Verdict(ETAT_NON_CONFORME, MENTION_NON_CONFORME)


def verdict_du_coeur(verification) -> Verdict:
    """Le verdict d'un `io.extraction_manifest.LotVerification`, **lu**.

    C'est le seul point de projection entre le vocabulaire du coeur et celui de
    l'ecran, et il tient en une lecture : `LotVerification.ok`, la propriete par
    laquelle le coeur dit lui-meme s'il reste un constat bloquant. La TUI ne
    parcourt pas `findings`, ne connait aucun code de verification et n'a donc
    aucun seuil a elle -- ce serait un second jugement, avec ses propres mots et
    sa propre derive.
    """
    return VERDICT_CONFORME if verification.ok else VERDICT_NON_CONFORME


# ---------------------------------------------------------------------------
# Le modele pur
# ---------------------------------------------------------------------------

def _replie(texte: str, ascii_seul: bool) -> str:
    return jetons.replier_ascii(texte) if ascii_seul else texte


@dataclass
class Lot:
    """Un lot de la liste : son nom, ce qu'il contient, et ce que le coeur en
    dit.

    ``frames`` est `lots[].expected_frame_count` du manifest, et rien d'autre :
    « le noyau ne derive **jamais** le cardinal d'une duree, il l'exige »
    (`EPIC11-ARB-30`). ``extrait_le`` est `lots[].confirmation.confirmed_at`,
    la seule date vraie du document (`EPIC11-ARB-44`) ; elle vaut ``None`` pour
    un lot venu du scan, qui n'en porte pas -- et la mention disparait alors
    plutot que d'etre inventee.
    """

    lot_id: str
    frames: int
    extrait_le: str | None = None
    verdict: Verdict = VERDICT_CONFORME
    coche: bool = False

    def __post_init__(self) -> None:
        if not self.lot_id:
            raise LotsMalFormes(
                "Un lot porte un identifiant : une ligne sans nom ne se coche "
                "pas, elle ne se lit meme pas.")
        if self.frames < 0:
            raise LotsMalFormes(
                f"Le lot {self.lot_id!r} annonce {self.frames} frame(s) : un "
                "cardinal negatif ne vient d'aucun manifest.")

    @property
    def cochable(self) -> bool:
        """AC 4.4 : **toujours**, verdict du coeur compris.

        Un lot non conforme reste cochable, et ce n'est pas un oubli : « la
        confirmation dit ce qui manque ». Retirer la case ici remplacerait un
        avertissement par une impossibilite muette, sur l'ecran qui n'ecrit
        rien.
        """
        return True

    def texte_du_compte(self, ascii_seul: bool = False) -> str:
        """`124` -- le cardinal nu, le libelle etant en colonne de gauche."""
        return str(self.frames)

    def texte_de_la_date(self, ascii_seul: bool = False) -> str:
        """`extraites le 26/08`, ou rien quand le lot n'a pas de date."""
        if not self.extrait_le:
            return ""
        return _replie(MENTION_EXTRAITES.format(
            date=date_courte(self.extrait_le)), ascii_seul)


@dataclass(frozen=True)
class Validation:
    """Ce que rend une validation : les coches, ou un refus **nomme**.

    Meme forme que `cadences.Validation`, et pour la meme raison : rendre une
    liste vide et rien d'autre laisserait l'appelant continuer sans rien
    remarquer.
    """

    coches: tuple[Lot, ...] = ()
    motif: str | None = None

    @property
    def passe(self) -> bool:
        return self.motif is None


@dataclass
class ListeDeLots:
    """La liste cochable de `E5-1` : des lots, un curseur, une fenetre."""

    lots: list[Lot]
    curseur: int = 0
    premier_visible: int = field(default=0)

    def __post_init__(self) -> None:
        if not self.lots:
            raise LotsMalFormes(
                "Une liste de lots porte au moins un lot ; une liste vide "
                "n'est pas un choix, c'est un ecran sans objet -- le menu de "
                "l'atelier conditionne deja l'entree Pdf a l'existence d'un "
                "lot.")
        noms = [lot.lot_id for lot in self.lots]
        if len(set(noms)) != len(noms):
            # Deux lignes du meme lot doubleraient son cardinal dans la ligne
            # d'etat et feraient generer deux fois les memes planches.
            raise LotsMalFormes(f"Deux lots portent le meme identifiant : {noms}")

    # -- construction --------------------------------------------------------

    @classmethod
    def depuis_le_manifeste(
        cls, manifeste: Mapping | None,
        verdicts: Mapping[str, Verdict] | None = None,
    ) -> "ListeDeLots":
        """Les lots du manifest **deja charge**, dans l'ordre du document.

        ``verdicts`` est indexe **par identifiant de lot, jamais par rang**.
        « Deux listes qui doivent rester en correspondance sont deux occasions
        de les desapparier » : un verdict pris au rang serait juste tant que
        l'ordre des deux collections coincide, c'est-a-dire jusqu'au premier
        lot filtre. C'est litteralement le mutant `M33` de la story 5.6.

        Un lot dont personne n'a demande le verdict est **conforme par
        defaut** : la verification est un travail de coeur qui coute une
        lecture de dossier, et l'ecran doit s'ouvrir avant qu'elle soit faite.
        """
        verdicts = dict(verdicts or {})
        lots = []
        for entree in projet_lecture._lots(
                manifeste if isinstance(manifeste, dict) else None):
            identifiant = entree.get("lot_id")
            if not isinstance(identifiant, str) or not identifiant:
                # Un lot sans nom ne se designe pas : on le saute plutot que
                # de faire tomber l'ecran sur un document abime.
                continue
            confirmation = entree.get("confirmation")
            quand = (confirmation.get("confirmed_at")
                     if isinstance(confirmation, dict) else None)
            lots.append(Lot(
                lot_id=identifiant,
                frames=_cardinal_declare(entree),
                extrait_le=quand if isinstance(quand, str) and quand else None,
                verdict=verdicts.get(identifiant, VERDICT_CONFORME),
            ))
        return cls(lots=lots)

    # -- lecture -------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.lots)

    @property
    def courant(self) -> Lot:
        """Le lot **sous le curseur** -- celui que le filet decrit."""
        return self.lots[self.curseur]

    @property
    def coches(self) -> tuple[Lot, ...]:
        return tuple(lot for lot in self.lots if lot.coche)

    @property
    def nombre_de_coches(self) -> int:
        return len(self.coches)

    @property
    def frames_cochees(self) -> int:
        """La **somme** des cardinaux des coches. Aucun produit, jamais."""
        return sum(lot.frames for lot in self.coches)

    def rang(self, lot_id: str) -> int | None:
        """Le rang du lot de cet identifiant exact, ou ``None``."""
        for rang, lot in enumerate(self.lots):
            if lot.lot_id == lot_id:
                return rang
        return None

    # -- navigation ----------------------------------------------------------

    def deplacer(self, pas: int) -> None:
        """`↑↓` : le curseur reste dans la liste, il n'en sort jamais."""
        self.curseur = min(max(self.curseur + pas, 0), len(self.lots) - 1)
        self._recadrer()

    def viser(self, lot_id: str) -> Lot:
        """Placer le curseur sur un lot **nomme**, comme `cadences.viser`.

        Un `next()` nu remonterait en « StopIteration », qui ne nomme ni le lot
        demande ni ceux qui existent.
        """
        rang = self.rang(lot_id)
        if rang is None:
            raise LotsMalFormes(
                f"Aucun lot ne s'appelle {lot_id!r} ; connus : "
                f"{[lot.lot_id for lot in self.lots]}.")
        self.curseur = rang
        self._recadrer()
        return self.lots[rang]

    # -- ecriture ------------------------------------------------------------

    def basculer(self) -> None:
        """`Espace` coche et decoche le lot **sous le curseur** (AC 4.1).

        Aucun refus n'est possible ici, a la difference de
        `cadences.ListeDeCadences.basculer` : le coeur refuse une cadence dont
        il ne saurait pas compter les frames, il ne refuse pas un lot qui
        existe (AC 4.4).
        """
        lot = self.courant
        lot.coche = not lot.coche

    def valider(self) -> Validation:
        """AC 4.3 : zero coche ne passe **jamais** en silence."""
        coches = self.coches
        if not coches:
            return Validation(motif=MOTIF_AUCUN_LOT_COCHE)
        return Validation(coches=coches)

    # -- ce que la fenetre montre -------------------------------------------

    def fenetre(self) -> tuple[int, int]:
        """`(premier, dernier)` rangs visibles, bornes incluses.

        Le calcul vit dans `jetons`, comme pour les trois listes qui defilent
        deja : une quatrieme redaction divergerait de la premiere retouche.
        """
        return jetons.fenetre_de_liste(len(self.lots), self.premier_visible,
                                       HAUTEUR_LISTE)

    def _recadrer(self) -> None:
        self.premier_visible = jetons.recadrer_la_fenetre(
            self.premier_visible, self.curseur, len(self.lots), HAUTEUR_LISTE)

    # -- rendu ---------------------------------------------------------------

    def lignes_de_liste(self, utile: int = jetons.largeur_utile(),
                        ascii_seul: bool = False) -> list[str]:
        """Les :data:`HAUTEUR_LISTE` lignes de la zone, `…` compris.

        La zone est **completee par des lignes vides** quand les lots sont
        moins nombreux qu'elle : c'est ce qui tient le filet du survol a la
        meme ligne d'un projet a l'autre.
        """
        total = len(self.lots)
        premier, dernier = self.fenetre()
        points = jetons.points_d_abregement(ascii_seul)
        rendues: list[str] = []
        if premier > 0:
            rendues.append(" " * _INDENT + points)
        for rang in range(premier, dernier + 1):
            rendues.append(self.ligne(rang, utile, ascii_seul))
        if dernier < total - 1:
            position = f"{premier + 1}-{dernier + 1} sur {total} lots"
            tete = " " * _INDENT + points
            creux = utile - _MARGE_DROITE - len(tete) - jetons.colonnes(position)
            rendues.append(tete + " " * max(jetons.CREUX_MINIMAL, creux)
                           + position)
        return rendues + [""] * (HAUTEUR_LISTE - len(rendues))

    def ligne(self, rang: int, utile: int = jetons.largeur_utile(),
              ascii_seul: bool = False) -> str:
        """Une ligne de lot, aux colonnes de `E5-1`.

        **Le nom s'abrege AU MILIEU** (`jetons.abreger_nom`), jamais par la
        fin : les lots de ce depot se distinguent par leur SUFFIXE --
        `plan-04_25` contre `plan-04_12p5` --, et une elision par la queue
        rendrait deux lots du meme rush indiscernables a l'ecran,
        c'est-a-dire le risque R12 remonte au niveau de l'affichage.

        **La colonne du nom vaut :data:`LARGEUR_DU_NOM`, le nom vaut deux
        colonnes de moins.** L'ecart est le creux minimal du depot, et il n'est
        pas decoratif : la maquette pose l'etat en colonne 57, c'est-a-dire
        immediatement apres un champ de nom de la longueur maximale du produit.
        Un lot nomme sur exactement `CANONICAL_ID_MAX_LENGTH` caracteres y
        collerait donc son `● complet` -- `..._12p5● complet` --, sur l'ecran
        meme dont la colonne est calee pour ce cas-la. Le creux est pris sur le
        nom plutot que sur la colonne, ce qui garde les colonnes de la maquette
        au caractere pres.
        """
        table = jetons.glyphes(ascii_seul)
        lot = self.lots[rang]
        case = table["coche" if lot.coche else "decoche"]
        curseur = table["curseur"] if rang == self.curseur else " "
        tete = (" " * (_INDENT - 2) + curseur + " "
                + _a_gauche(case, _LARGEUR_DE_LA_CASE, ascii_seul) + " ")
        nom = jetons.abreger_nom(lot.lot_id,
                                 LARGEUR_DU_NOM - jetons.CREUX_MINIMAL,
                                 ascii_seul)
        gauche = tete + _a_gauche(nom, LARGEUR_DU_NOM, ascii_seul)
        place = utile - _MARGE_DROITE - jetons.colonnes(gauche)
        return (gauche + jetons.ajuster(lot.verdict.rendu(ascii_seul), place,
                                        ascii_seul)).rstrip()

    def ligne_du_survol(self, utile: int = jetons.largeur_utile(),
                        ascii_seul: bool = False) -> str:
        """`Frames               124              extraites le 26/08`.

        **Le cardinal est celui du lot SOUS LE CURSEUR**, jamais un total : le
        total des coches vit en ligne d'etat, et le filet est ce qui les
        distingue (retour d'Egan du 2026-09-02).
        """
        lot = self.courant
        gauche = (" " * _INDENT
                  + _a_gauche(_replie(LIBELLE_DES_FRAMES, ascii_seul),
                              LARGEUR_DU_LIBELLE, ascii_seul)
                  + _a_gauche(lot.texte_du_compte(ascii_seul),
                              LARGEUR_DE_LA_VALEUR, ascii_seul))
        place = utile - _MARGE_DROITE - jetons.colonnes(gauche)
        return (gauche + jetons.ajuster(lot.texte_de_la_date(ascii_seul),
                                        place, ascii_seul)).rstrip()

    def ligne_de_compte(self, ascii_seul: bool = False) -> str:
        """`2 lots cochés · 164 frames` -- la LIGNE D'ETAT, et elle seule.

        **Il n'existe aucun second compte dans le corps de l'ecran** (AC 4.6,
        note 4 d'Egan du 2026-09-01 : « Laisse juste la mention du bas [...]
        toujours en double »). La ligne `2 lots cochés sur 4 · 164 frames` qui
        se tenait au-dessus du filet n'existe plus, et aucune methode de ce
        module ne la rend : un grep du corps compose rend zero occurrence du
        mot, dans les deux regimes.

        `EPIC11-ARB-56` tient : la ligne d'etat porte une **mesure**, aucune
        touche, aucun conseil d'usage, aucun motif de conception.

        L'accord du mot `lot` passe par `projet_lecture.accorder`, la table du
        depot -- « un `s` ajoute mecaniquement rendait `3 rushs`, qui n'est le
        mot de personne ».
        """
        nombre = self.nombre_de_coches
        frames = self.frames_cochees
        texte = (f"{accorder(nombre, 'lot')} coché{'s' if nombre > 1 else ''}"
                 f" · {frames} frame{'s' if frames > 1 else ''}")
        return _replie(texte, ascii_seul)

    def rang_du_curseur(self) -> int | None:
        """Le rang, dans :meth:`lignes_de_liste`, de la ligne a accentuer.

        **Passe explicitement a `jetons.peindre`, jamais devine** : ces lignes
        sont indentees de trois blancs, et l'auto-detection teste `startswith`
        sur le glyphe de curseur -- elle ne trouverait rien, en silence.
        """
        premier, dernier = self.fenetre()
        if not premier <= self.curseur <= dernier:
            return None
        return (1 if premier > 0 else 0) + (self.curseur - premier)

    def etats_des_lignes(self) -> dict[int, str]:
        """L'etat de **chaque** ligne de lot, par rang dans la zone de liste.

        A la difference des cadences -- ou seules les lignes refusees sont
        teintees --, toute ligne de lot porte un etat : la maquette couleur
        montre les cinq lots en vert `state-complete`. L'etat est **donne**
        (`EPIC11-ARB-71`) plutot que retrouve dans le texte : la reconnaissance
        par motif marcherait ici par accident, et cesserait de marcher au
        premier lot dont le nom vaudrait `x` en repli ASCII.
        """
        premier, dernier = self.fenetre()
        decalage = 1 if premier > 0 else 0
        return {decalage + (rang - premier): self.lots[rang].verdict.etat
                for rang in range(premier, dernier + 1)}


def _cardinal_declare(entree: Mapping) -> int:
    """Le cardinal de frames que le document declare, ou zero.

    **Le repli est UN, et il vaut zero** : un cardinal absent, mal type ou
    negatif ne fait pas tomber l'ecran -- « le menu doit s'ouvrir meme sur un
    projet dont le document est casse [...] il dit ce qu'il sait ». Un negatif
    laisse passer leverait `Lot.__post_init__`, c'est-a-dire perdrait l'ecran
    pour sauver une valeur.

    Le `bool` est exclu **avant** le `max` et ce n'est pas un detail d'ordre :
    `True` est un `int` en Python, et un `"expected_frame_count": true` dans un
    document abime rendrait un lot d'UNE frame -- une valeur plausible, donc
    invisible, ce qui est le pire des cas.
    """
    cardinal = entree.get("expected_frame_count")
    if isinstance(cardinal, bool) or not isinstance(cardinal, int):
        return 0
    return max(cardinal, 0)


def _a_gauche(texte: str, largeur: int, ascii_seul: bool = False) -> str:
    """Un champ cale a gauche, mesure en **COLONNES** et jamais en `len()`.

    Un ideogramme occupe deux colonnes : `str.ljust` calerait un champ de dix
    caracteres sur vingt colonnes, et toutes les colonnes de droite partiraient
    avec.
    """
    texte = jetons.ajuster(texte, largeur, ascii_seul)
    return texte + " " * max(0, largeur - jetons.colonnes(texte))


# ---------------------------------------------------------------------------
# `E5-1` -- l'ecran
# ---------------------------------------------------------------------------

class EcranLotsAPlanches(ObjetTravaille, Palier):
    """`E5-1` -- quels lots mettre en planches.

    L'ecran ne compte rien, ne nomme rien et ne juge rien : il branche le
    modele pur ci-dessus sur le clavier et sur la seule issue de l'ecran,
    `⏎ continuer`. **Il n'importe jamais `cli.py`** (`EPIC11-ARB-67`) : le
    point d'entree de coeur de cet atelier est `mixed_media_utility.makepdf`,
    et c'est l'appelant qui le tient.
    """

    titre = projet_lecture.PDF
    raccourcis = RACCOURCIS_LOTS
    #: Une station du parcours, pas un passage : on revient dessus depuis les
    #: reglages, et `Échap` y ramene au menu de l'atelier.
    TRANSITOIRE = False
    ID_DU_CORPS = "corps-lots-pdf"

    def __init__(self, liste: ListeDeLots,
                 continuer: Callable[[Validation], None] | None = None) -> None:
        super().__init__()
        self.liste = liste
        self._continuer = continuer
        #: Ce que la ligne d'etat dit **a la place** de sa mesure, le temps
        #: d'un refus : `(nom d'etat, texte)`. Le couple est garde brut pour
        #: que la ligne se redise dans les deux regimes.
        self._a_dire: tuple[str, str] | None = None

    # -- lecture --------------------------------------------------------------

    def composer(self, largeur: int, ascii_seul: bool = False
                 ) -> tuple[list[str], int | None, dict[int, str]]:
        """Le corps de `E5-1`, **sous la hauteur de la zone centrale**.

        Les respirations sont sacrifiables et tombent de haut en bas : c'est le
        budget de `Composition`, qui existe parce que `textual` coupe par le
        bas, en silence.
        """
        utile = jetons.largeur_utile(largeur)
        composition = Composition()
        composition.respirer()
        composition.poser(ligne_de_titre(TITRE_DES_LOTS, ascii_seul))
        composition.respirer()
        composition.bloc(self.liste.lignes_de_liste(utile, ascii_seul),
                         etats=self.liste.etats_des_lignes(),
                         curseur=self.liste.rang_du_curseur())
        composition.respirer()
        composition.poser(filet_titre(FILET_DU_SURVOL, utile, ascii_seul))
        composition.respirer()
        composition.poser(self.liste.ligne_du_survol(utile, ascii_seul))
        return composition.rendu()

    def mesure(self, ascii_seul: bool = False) -> str:
        """Ce que la ligne d'etat dit quand il n'y a pas de refus a dire."""
        return self.liste.ligne_de_compte(ascii_seul)

    def ligne_d_etat(self, ascii_seul: bool = False) -> str:
        if self._a_dire is not None:
            glyphe = jetons.glyphes(ascii_seul)[self._a_dire[0]]
            return _replie(f"{glyphe}  {self._a_dire[1]}", ascii_seul)
        return self.mesure(ascii_seul)

    def lignes(self) -> list[str]:
        return self.composer(self.app.size.width, self.app.ascii_seul)[0]

    def etat(self) -> str:
        return self.ligne_d_etat(self.app.ascii_seul)

    def objet_du_bandeau(self) -> str:
        """`E5-1` porte un bandeau NU : on n'y travaille pas encore un lot en
        particulier, on choisit lesquels."""
        return ""

    # -- rendu ----------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id=self.ID_DU_CORPS)
        return [Vertical(self._corps, id=f"centre-{self.ID_DU_CORPS}")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur = jetons.largeur_utile(self.app.size.width)
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

        **Une validation a zero coche ne demonte rien** (AC 4.3) : le refus
        s'ecrit en ligne d'etat, l'ecran reste monte, et `_continuer` n'est pas
        appele. C'est le point ou une liste vide passerait « en silence ».
        """
        self._a_dire = None
        if touche in ("up", "down"):
            self.liste.deplacer(-1 if touche == "up" else 1)
            return True
        if touche == "space" or caractere == " ":
            self.liste.basculer()
            return True
        if touche == "enter":
            validation = self.liste.valider()
            if not validation.passe:
                self._a_dire = (ETAT_NON_CONFORME, validation.motif or "")
                return True
            if self._continuer is not None:
                self._continuer(validation)
            else:
                self._pas_encore()
            return True
        return False

    def _pas_encore(self) -> None:
        """`⏎` sans appelant : l'ecran suivant n'existe pas encore, et on le DIT.

        Un `if ... is not None` sans branche `else` rendrait la touche
        indistinguable d'un clavier casse -- c'est litteralement le finding
        `K1.1a`, et la garde structurelle des rappels existe pour l'attraper.
        """
        application = _application_montee(self)
        if application is None:
            # Un ecran construit a nu par un banc n'a pas d'application ou
            # descendre : il n'y a rien a montrer, et rien a taire non plus.
            return
        application.descendre(EcranPasEncore(CE_QUI_MANQUE_APRES_LES_LOTS,
                                             QUAND_LES_REGLAGES))


__all__ = [
    "CE_QUI_MANQUE_APRES_LES_LOTS",
    "ETAT_CONFORME",
    "ETAT_NON_CONFORME",
    "FILET_DU_SURVOL",
    "HAUTEUR_LISTE",
    "LARGEUR_DU_NOM",
    "LIBELLE_DES_FRAMES",
    "MENTION_CONFORME",
    "MENTION_EXTRAITES",
    "MENTION_NON_CONFORME",
    "MOTIF_AUCUN_LOT_COCHE",
    "QUAND_LES_REGLAGES",
    "RACCOURCIS_LOTS",
    "TITRE_DES_LOTS",
    "VERDICT_CONFORME",
    "VERDICT_NON_CONFORME",
    "EcranLotsAPlanches",
    "ListeDeLots",
    "Lot",
    "LotsMalFormes",
    "Validation",
    "Verdict",
    "verdict_du_coeur",
]
