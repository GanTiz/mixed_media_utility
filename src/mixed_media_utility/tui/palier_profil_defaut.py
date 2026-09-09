# -*- coding: utf-8 -*-
"""« Profil de calibration par defaut » : l'ecran manquant du palier Projet.

**Le manque que ce module ferme, et c'est Egan qui l'a trouve sur le terrain**
(2026-09-06, verbatim de sa note de recette) : « # Profil de calibration par
defaut (projet) -- Cet ecran n'existe pas encore (mauvais cablage ?) ».

Ce n'etait **pas** un mauvais cablage, et la mesure le dit : le coeur est
complet (`io/profile_designation.py`), et `tui/palier_projet.py` porte depuis
la story 11.3 **six fonctions ecrites, exportees et testees** --
:func:`~mixed_media_utility.tui.palier_projet.apercu_de_profil`,
:func:`~mixed_media_utility.tui.palier_projet.panneau_de_profil`,
:func:`~mixed_media_utility.tui.palier_projet.poser_le_profil_par_defaut`,
:func:`~mixed_media_utility.tui.palier_projet.profil_par_defaut`,
:func:`~mixed_media_utility.tui.palier_projet.nom_du_profil` et la garde de
cible `CibleSansProjet`. `atelier_extraction_ecriture.ChaineReelle` le dit
lui-meme : « le coeur des six fonctions de `palier_projet.py` est ecrit, teste
et exporte ; ce qui manque tient en un ecran par commande ». **Ce module est
cet ecran, et rien d'autre** : il n'ecrit pas une ligne de coeur, il n'en
recalcule aucune valeur.

C'est la cinquieme occurrence du mode de panne `E9` de cet epic -- « un
composant livre, teste, et cable nulle part dans l'application est un
composant que le produit n'a pas ». Elle se paie ici comme les quatre autres :
par un banc d'ATTEIGNABILITE qui monte
:func:`~mixed_media_utility.tui.atelier_extraction_ecriture.chaine_du_produit`
et frappe les touches, jamais par une assertion posee sur la classe seule.

Une DECLINAISON, aucun dessin neuf
----------------------------------
`EPIC11-ARB-144` interdit un ecran code sans maquette validee. Egan l'a leve
**pour ce cas precis**, le 2026-09-06, verbatim : « a decliner sans validation
de ma part. Si cela existe : cabler. » Ce qui est decline est
:class:`~mixed_media_utility.tui.atelier_scan_calibration.EcranChoixDeCalibration`
(`E3-5`), qui fait deja presque exactement ce geste -- il choisit un profil
pour **une passe de scan** la ou celui-ci **pose le defaut du projet**. En
sont repris, a l'identique et sans les reecrire :

* les deux zones liste / explorateur, l'explorateur monte par-dessus la ligne
  « autre fichier… » ;
* le fichier designe qui prend **sa propre ligne** plutot que de remplacer
  cette porte -- l'alternative est un cul-de-sac mesure (voir
  :data:`CLE_FICHIER_DESIGNE`) ;
* la couture clavier
  :class:`~mixed_media_utility.tui.ecran_projet.CoutureExplorateur`, posee
  **avant** `Palier` dans les bases : aucune touche n'est recablee ici ;
* la validation d'explorateur qui **reste sur l'explorateur** en cas de refus
  et pose le motif du coeur **verbatim** (`EPIC11-ARB-30`).

Les trois arbitrages que ce module doit tenir
---------------------------------------------
* `EPIC11-ARB-4` -- **l'apercu precede l'ecriture**. Designer un fichier
  n'ecrit rien : il monte :class:`EcranPoseDuProfil`, dont le cartouche est
  celui de `palier_projet.panneau_de_profil`, c'est-a-dire ce qui **sera**
  ecrit. L'ecriture n'arrive qu'a l'issue retenue ;
* `EPIC11-ARB-89` -- **jamais une seule issue, jamais un blocage sec**. Un
  profil par defaut deja pose n'est pas un refus : il est **nomme** dans le
  cartouche, et l'issue qui ecrit s'appelle alors « Remplacer le profil par
  defaut ». Un fichier illisible ne ferme pas l'ecran : on reste sur
  l'explorateur avec le motif du coeur ;
* `EPIC11-ARB-56` -- la ligne d'etat porte une **mesure**, jamais une touche
  ni un conseil.

Et l'ECRAN DE SUCCES, qui est un grief separe
---------------------------------------------
Egan, sur un autre parcours du meme jour : « pas d'ecran de succes et on
revient directement a la page pour lancer une calibration. **Incoherent avec le
reste.** » :class:`EcranProfilPose` est la reponse ici -- un
:class:`~mixed_media_utility.tui.execution.EcranResultat` qui nomme le fichier
ecrit et la chaine posee. Il n'ecrit **pas** « Retour aux ateliers » :
`EcranResultat` l'ajoute de lui-meme, et l'ecrire deux fois donnerait deux
lignes pour une seule sortie.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from ..io import profile_designation
from . import jetons, projet_lecture
from .atelier_extraction import _application_montee
from .coque import EcranPasEncore, ObjetTravaille, Palier
from .ecran_projet import CoutureExplorateur, raccourcis_de_l_explorateur
from .execution import (EcranRefus, EcranResultat, PanneauConfirmation,
                        bloc_peint)
from .explorateur import FAMILLE_PROFILS, Explorateur
from .palier_projet import (CibleSansProjet, ProfilPose, apercu_de_profil,
                            nom_du_profil, panneau_de_profil,
                            poser_le_profil_par_defaut, profil_par_defaut)
from .panneau import ChoixExclusif, Issue, LigneChiffree, Panneau

# ===========================================================================
# Le vocabulaire de l'ecran -- une seule redaction, celle-ci
# ===========================================================================

#: Le segment de bandeau : le PALIER, jamais le nom de la classe d'ecran. Il
#: est lu de `projet_lecture` comme les deux autres ecrans du palier Projet le
#: font deja -- une seconde redaction du mot « Projet » divergerait le jour ou
#: le palier serait renomme, et l'ecart ne se verrait que sur un bandeau.
PALIER_DU_PROFIL = projet_lecture.PROJET

#: La droite du bandeau. Elle nomme **ce sur quoi on travaille**, comme
#: `ObjetTravaille` l'exige : sans elle, les trois ecrans de ce parcours
#: porteraient le meme bandeau que le palier dont ils descendent.
OBJET_DU_BANDEAU = "profil par défaut"

#: Le titre de la question posee par l'ecran de choix.
TITRE = "Quel profil de calibration poser par défaut ?"

#: Le titre du filet qui separe la liste de l'etat courant du projet.
TITRE_DU_PIED = "Le profil par défaut actuel"

#: La ligne de raccourcis de la zone LISTE. **Constante de module**, comme
#: celles des autres ecrans du depot : c'est ce qui la fait balayer par la
#: garde d'epic du repli ASCII et par celle des majuscules de raccourci.
#:
#: **Aucune lettre n'y figure**, et il n'y a donc pas de `Q quitter` : la
#: frappe imprimable est **consommee** par l'ecran plutot que de remonter au
#: binding applicatif `q`, qui fermerait l'application sur une touche que rien
#: n'annonce. Meme geste et meme motif que `E3-5`.
RACCOURCIS_PROFIL = "⏎ continuer  ↑↓ choisir  Échap retour  F1 aide"

#: La ligne de raccourcis du point de jugement. Elle n'annonce **pas** `Tab` :
#: cet ecran ne passe aucun modele de noms, donc `Tab` n'a aucune destination
#: et `EcranChiffre.traiter` le rend inerte -- annoncer une touche inerte est
#: le finding `I8` pris a l'envers.
RACCOURCIS_POSE = "⏎ valider  ↑↓ choisir  Échap retour  F1 aide"

#: Les deux zones de l'ecran de choix : la liste, et l'explorateur monte
#: par-dessus l'entree « autre fichier… ».
ZONE_LISTE = "liste"
ZONE_EXPLORATEUR = "explorateur"

#: Cle de l'entree qui ouvre l'explorateur sur un `.json` (`EPIC11-ARB-48`).
CLE_AUTRE_FICHIER = "autre-fichier"

#: Cle de l'entree que l'explorateur **ajoute** quand un fichier est designe.
#:
#: **Elle existe parce que l'alternative est un cul-de-sac**, et le motif est
#: deja mesure sur `E3-5` : si « autre fichier… » devenait elle-meme le choix
#: retenu, `⏎` y confirmerait le fichier et il n'y aurait plus aucune touche
#: pour en designer un autre -- l'operateur qui s'est trompe de fichier n'aurait
#: plus qu'a quitter l'ecran. Le fichier designe prend donc **sa propre ligne**,
#: et « autre fichier… » reste la porte vers l'explorateur.
CLE_FICHIER_DESIGNE = "fichier-designe"

#: Prefixe des cles d'entree de profil du registre. Le **rang** du registre
#: suit, jamais le `chain_id` : une cle derivee de l'identite ferait de
#: l'identite une cle de resolution, ce qu'`EPIC5-ARB-83` supprime.
PREFIXE_DE_PROFIL = "profil-"

LIBELLE_AUTRE_FICHIER = "autre fichier…"
MENTION_AUTRE_FICHIER = "un fichier .json, dans l'explorateur"
MENTION_FICHIER_DESIGNE = "désigné dans l'explorateur"

#: Ce que porte la mention du profil deja pose par defaut, et celle d'un
#: profil du registre dont le fichier n'est plus la. Le second n'est pas une
#: absence : « l'entree reste vraie de ce que le projet a utilise ».
MENTION_PAR_DEFAUT = "profil par défaut actuel"
MENTION_FICHIER_DISPARU = "son fichier a disparu"

#: Les libelles des deux issues du point de jugement, et la mention qui dit ce
#: que chacune COUTE. `EPIC11-ARB-89` : l'ecriture est possible, elle est
#: **avertie** -- poser un defaut par-dessus un autre ne detruit aucun fichier
#: de profil, il change ce que les scans prendront sans qu'on le repete.
LIBELLE_POSER = "Poser ce profil par défaut"
LIBELLE_REMPLACER = "Remplacer le profil par défaut"
LIBELLE_ANNULER = "Annuler"
#:
#: **Les deux mentions sont TENUES A LA GRILLE**, et c'est mesure : au
#: plancher, la ligne d'issue vaut le curseur, le libelle, le tiret et la
#: mention. La premiere redaction de `MENTION_REMPLACE` -- « l'ancien reste
#: sur le disque, il cesse d'etre propose » -- sortait a 88 colonnes et se
#: faisait couper A LA MENTION, c'est-a-dire sur le seul endroit qui dit ce que
#: l'issue coute. Une issue dont le cout est abrege est une ecriture non
#: avertie, ce qu'`EPIC11-ARB-89` interdit.
MENTION_POSE = "les scans le prendront sans le répéter"
MENTION_REMPLACE = "l'ancien fichier reste sur le disque"
MENTION_RIEN_TOUCHE = "rien n'est touché"
MOTIF_DE_L_ISSUE = "{libelle} — {mention}"

CLE_POSER = "poser"
CLE_ANNULER = "annuler"

#: Le libelle de la ligne qui NOMME le defaut deja pose, dans le cartouche du
#: point de jugement. Sans elle, remplacer un defaut serait indistinguable
#: d'en poser un premier -- c'est-a-dire une ecriture non avertie.
LIBELLE_DEFAUT_ACTUEL = "Remplace"

#: Le titre du cartouche de l'ecran de succes. Il differe de celui du point de
#: jugement (`A ecrire`) et c'est tout ce qui les distingue au premier coup
#: d'oeil : un compte rendu qui garderait « A ecrire » ferait croire qu'il
#: reste quelque chose a faire.
TITRE_ECRIT = "Écrit"

#: Le libelle de la ligne qui situe le fichier ecrit. Le nom seul ne suffit
#: pas : l'operateur veut savoir **ou** il a atterri.
LIBELLE_EMPLACEMENT = "Emplacement"

#: Ce que la ligne d'etat de l'ecran de choix mesure : le cardinal du registre,
#: dans ses trois formes. Le cas a un profil est le seul ou la faute d'accord
#: se voie, et c'est celui qu'une fabrique porte.
ETAT_SANS_PROFIL = "aucun profil au registre du projet"
ETAT_UN_PROFIL = "1 profil au registre du projet"
ETAT_DES_PROFILS = "{profils} profils au registre du projet"
ETAT_SANS_DEFAUT = "aucun profil par défaut"
ETAT_DEFAUT = "défaut : {nom}"
SEPARATEUR_D_ETAT = " · "

#: La ligne d'etat de l'ecran de succes. Un **constat**, jamais une touche.
ETAT_POSE = "profil par défaut posé"

#: Ce qui manque quand aucun projet n'est ouvert, et quand cet ecran l'aura.
#: Meme couple, meme forme et meme motif que `projet_inventaire` : un
#: `EcranPasEncore` sans echeance est indistinguable d'un abandon.
CE_QUI_MANQUE_SANS_PROJET = ("Le profil de calibration par défaut, tant "
                             "qu'aucun projet n'est ouvert")
QUAND_LE_PROFIL_PAR_DEFAUT = "l'ouverture d'un projet sur le palier Projet"

#: Colonne du curseur et colonne du texte courant, comme les autres ecrans a
#: liste du depot. Le titre est **plus a gauche** que ses entrees a dessein :
#: un titre aligne sur elles ne s'en distinguerait plus.
INDENT_DU_CURSEUR = "   "
INDENT_DU_TEXTE = "  "

#: Largeur de la colonne des noms d'entree. La mention ouvre donc toujours a la
#: meme colonne, et l'oeil lit les mentions en colonne plutot qu'en escalier.
LARGEUR_DU_NOM = 33

#: Hauteur maximale de la liste, `…` compris. **Derivee de la place qui
#: reste**, jamais choisie : la zone centrale porte dix-sept lignes
#: (`jetons.hauteur_centrale(24)` au plancher de `EPIC11-ARB-21`), dont trois
#: pour le titre et ses blancs, trois pour le filet et ses blancs, et trois au
#: plus pour le pied. Huit est ce qui tient sans jamais deborder.
HAUTEUR_DE_LA_LISTE = 8


def _replie(texte: str, ascii_seul: bool) -> str:
    """Replier un texte quand le mode l'exige. **Avant toute mesure.**

    Idiome du depot (`atelier_extraction._replie`), repris ici plutot
    qu'importe : ce module ne tire `atelier_extraction` que pour
    `_application_montee`, et lui emprunter en plus une fonction d'une ligne
    l'attacherait a un module que trois agents editent.
    """
    return jetons.replier_ascii(texte) if ascii_seul else texte


def profil_acceptable(chemin: Path) -> bool:
    """Ce que l'explorateur retient : un `.json` (`EPIC11-ARB-48`).

    Un dossier n'a pas a passer par ici : l'explorateur ne soumet au filtre que
    les fichiers. Le filtre est le meme que celui de `E3-5` -- un profil de
    calibration est un JSON, et il l'est aux deux sites.
    """
    return chemin.suffix.lower() == ".json"


# ===========================================================================
# Le modele de la liste
# ===========================================================================

@dataclass(frozen=True)
class EntreeDeProfil:
    """Une ligne de la liste de choix.

    `chemin` est **le fichier que la pose lira**, resolu par le coeur
    (:func:`profile_designation.designated_profile_path`) et jamais recompose
    depuis le `chain_id` -- recomposer ferait de l'identite une cle de
    resolution, ce qu'`EPIC5-ARB-83` supprime, et de la seule facon qui passe
    inapercue : en marchant, tant que les deux coincident.

    Il vaut ``None`` sur la porte « autre fichier… » et sur un profil du
    registre dont le fichier a disparu. Les deux se distinguent par `entree`,
    qui n'est renseignee que pour un profil du registre.
    """

    cle: str
    nom: str
    mention: str
    chemin: Path | None = None
    entree: Mapping[str, Any] | None = None
    par_defaut: bool = False

    @property
    def est_un_profil(self) -> bool:
        """Vrai pour une entree du registre. Faux pour les deux portes."""
        return self.entree is not None

    @property
    def designe_un_fichier(self) -> bool:
        """Vrai quand `⏎` a de quoi construire un apercu."""
        return self.chemin is not None


def _mention_de_l_entree(entree: Mapping[str, Any], chemin: Path | None,
                         par_defaut: bool) -> str:
    """La mention d'un profil du registre, dans ses trois etats.

    L'ordre n'est pas indifferent : **le fichier disparu passe avant tout le
    reste**, y compris avant « profil par defaut actuel ». Un defaut dont le
    fichier n'est plus la est le seul des trois etats sur lequel `⏎` ne peut
    rien faire, et le taire ferait proposer une ligne inerte.

    Le troisieme etat rend le `chain_id` plutot qu'un mot fixe : c'est ce qui
    **distingue** deux profils dont `nom_du_profil` rendrait la meme
    provenance, et une mention uniforme rendrait invisible tout desappariement
    entre une ligne et le fichier qu'elle designe.
    """
    if chemin is None:
        return MENTION_FICHIER_DISPARU
    if par_defaut:
        return MENTION_PAR_DEFAUT
    return str(entree.get("chain_id") or "")


def entrees_du_profil(dossier, *, profils: Sequence[Mapping] | None = None,
                      defaut: Mapping | None = None
                      ) -> tuple[EntreeDeProfil, ...]:
    """Les lignes de l'ecran : le registre **dans son ordre**, puis la porte.

    `profils` et `defaut` sont les **points d'injection du banc** ; leur defaut
    est le vrai chemin de production -- `designated_profiles` et
    `default_profile_entry`, les deux lecteurs du coeur. Aucune seconde lecture
    n'est ecrite ici, et aucun profil n'est balaye depuis
    `versions/calibration/` : cette fonction enumere, elle ne choisit pas.

    **L'ordre du registre n'est jamais retrie** : il est deja trie par
    `chain_id` a l'ecriture, pour que deux projets ayant vu les memes profils
    dans un ordre different rendent le meme document. Le retrier serait une
    seconde redaction de cette regle.

    Le profil par defaut est reconnu **par le chemin ecrit a son entree**
    (`ENTRY_PATH_KEY`), jamais par comparaison de `chain_id` : c'est la
    propriete meme d'`EPIC5-ARB-83`, et `record_designated_profile` ecrit
    litteralement la meme entree aux deux cles du manifeste.

    **La liste n'est jamais vide** : la porte « autre fichier… » y est
    toujours, y compris sur un projet qui n'a designe aucun profil. C'est ce
    qui evite l'« ecran vide (listes) » qu'Egan a nomme le 2026-09-06 -- un
    ecran sans aucune ligne serait un blocage sec deguise en liste.
    """
    if profils is None:
        profils = (profile_designation.designated_profiles(dossier)
                   if dossier is not None else [])
    if defaut is None and dossier is not None:
        defaut = profile_designation.default_profile_entry(dossier)
    chemin_du_defaut = (defaut or {}).get(profile_designation.ENTRY_PATH_KEY)

    lignes: list[EntreeDeProfil] = []
    for rang, entree in enumerate(profils):
        par_defaut = bool(
            chemin_du_defaut
            and entree.get(profile_designation.ENTRY_PATH_KEY)
            == chemin_du_defaut)
        chemin = (profile_designation.designated_profile_path(dossier, entree)
                  if dossier is not None else None)
        lignes.append(EntreeDeProfil(
            cle=f"{PREFIXE_DE_PROFIL}{rang}",
            # **Une seule redaction de « sous quel nom un profil s'affiche »** :
            # `palier_projet.nom_du_profil`, deja employee par le pied du palier
            # Projet, par le menu du Scan et par `E3-5`. Une quatrieme
            # divergerait au premier ajustement.
            nom=nom_du_profil(entree),
            mention=_mention_de_l_entree(entree, chemin, par_defaut),
            chemin=chemin,
            entree=entree,
            par_defaut=par_defaut))
    lignes.append(EntreeDeProfil(CLE_AUTRE_FICHIER, LIBELLE_AUTRE_FICHIER,
                                 MENTION_AUTRE_FICHIER))
    return tuple(lignes)


@dataclass
class ChoixDuProfil:
    """La liste et son curseur. **Aucune entree n'est retenue au depart.**

    `EPIC11-ARB-7` : une entree preselectionnee transforme `⏎` en accident. Le
    curseur part donc en tete, et il ne retient rien -- l'operateur valide.
    """

    entrees: tuple[EntreeDeProfil, ...]
    curseur: int = 0
    premier_visible: int = 0
    #: Le fichier designe dans l'explorateur, quand il y en a un.
    fichier: Path | None = None

    @property
    def courante(self) -> EntreeDeProfil:
        return self.entrees[self.curseur]

    @property
    def profils(self) -> tuple[EntreeDeProfil, ...]:
        """Les seules entrees qui viennent du registre. Sert la ligne d'etat."""
        return tuple(e for e in self.entrees if e.est_un_profil)

    def fenetre(self) -> tuple[int, int]:
        """`(premier, dernier)` rangs visibles, bornes incluses.

        **Le fenetrage est celui du depot, pas un second** :
        `jetons.fenetre_de_liste` reserve la ligne `…` **avant** le decoupage,
        sans quoi la derniere entree se cacherait derriere le `…` qui annonce
        qu'elle existe.
        """
        self.premier_visible = jetons.recadrer_la_fenetre(
            self.premier_visible, self.curseur, len(self.entrees),
            HAUTEUR_DE_LA_LISTE)
        return jetons.fenetre_de_liste(len(self.entrees), self.premier_visible,
                                       HAUTEUR_DE_LA_LISTE)

    def deplacer(self, pas: int) -> bool:
        """Bouger le curseur, borne aux deux bouts. Rend vrai s'il a bouge."""
        cible = min(max(self.curseur + pas, 0), len(self.entrees) - 1)
        bouge = cible != self.curseur
        self.curseur = cible
        return bouge

    def poser_le_fichier(self, chemin) -> None:
        """Retenir le fichier designe par l'explorateur, **deja valide**.

        Il prend sa propre ligne, **juste avant « autre fichier… »**, et le
        curseur s'y pose : voir :data:`CLE_FICHIER_DESIGNE` pour le cul-de-sac
        que cela evite. Designer un second fichier **remplace** la ligne au
        lieu d'en ajouter une : deux lignes pour un choix unique laisseraient
        l'operateur retenir un fichier qu'il a deja remplace.
        """
        self.fichier = Path(chemin)
        ligne = EntreeDeProfil(CLE_FICHIER_DESIGNE, self.fichier.name,
                               MENTION_FICHIER_DESIGNE, chemin=self.fichier)
        restantes = [e for e in self.entrees if e.cle != CLE_FICHIER_DESIGNE]
        rang = [e.cle for e in restantes].index(CLE_AUTRE_FICHIER)
        self.entrees = tuple(restantes[:rang] + [ligne] + restantes[rang:])
        self.curseur = rang
        self.premier_visible = jetons.recadrer_la_fenetre(
            self.premier_visible, self.curseur, len(self.entrees),
            HAUTEUR_DE_LA_LISTE)


# ===========================================================================
# Le point de jugement et l'ecran de succes -- les DEUX panneaux
# ===========================================================================

def issues_de_la_pose(remplace: bool) -> ChoixExclusif:
    """Les deux issues du point de jugement (`EPIC11-ARB-89`).

    L'issue qui ecrit **change de libelle** selon qu'un defaut existe deja :
    « Poser » quand la place est libre, « Remplacer » quand elle ne l'est pas.
    Le mot n'est pas cosmetique -- c'est l'avertissement qu'`EPIC11-ARB-89`
    exige avant une ecriture consciente, et le seul endroit de l'ecran ou il
    tienne en un mot.

    Elle est en **tete** de liste et l'annulation en queue ; `ChoixExclusif`
    deplace de lui-meme le curseur sur la premiere issue qui n'ecrit pas, si
    bien que l'ecriture n'est jamais atteignable en une frappe.
    """
    return ChoixExclusif([
        Issue(CLE_POSER,
              MOTIF_DE_L_ISSUE.format(
                  libelle=LIBELLE_REMPLACER if remplace else LIBELLE_POSER,
                  mention=MENTION_REMPLACE if remplace else MENTION_POSE),
              ecrit=True),
        Issue(CLE_ANNULER,
              MOTIF_DE_L_ISSUE.format(libelle=LIBELLE_ANNULER,
                                      mention=MENTION_RIEN_TOUCHE)),
    ])


def panneau_de_la_pose(apercu: ProfilPose, defaut_actuel: str = "") -> Panneau:
    """Le cartouche « A ecrire », **derive de `palier_projet` et non refait**.

    Les trois lignes chiffrees sont celles de
    :func:`~mixed_media_utility.tui.palier_projet.panneau_de_profil`, qui est
    la seule redaction de « ce qu'une pose de profil ecrit ». Les recopier ici
    en ferait une seconde, qui divergerait au premier ajustement -- et l'ecart
    ne se verrait que sur l'ecran, jamais dans le coeur.

    La quatrieme ligne n'apparait **que** quand un defaut existe deja : c'est
    l'avertissement d'`EPIC11-ARB-89`, et l'ecrire a vide ferait annoncer un
    remplacement qui n'a pas lieu.
    """
    panneau = panneau_de_profil(apercu)
    if not defaut_actuel:
        return panneau
    return Panneau(panneau.titre, list(panneau.lignes) + [
        LigneChiffree(LIBELLE_DEFAUT_ACTUEL, defaut_actuel)])


def panneau_du_profil_pose(pose: ProfilPose) -> Panneau:
    """Le cartouche de l'ecran de succes. **Memes valeurs, autre titre.**

    Il se derive lui aussi de `palier_projet.panneau_de_profil` : ce que
    l'apercu annoncait et ce que la pose a ecrit sont les **memes trois
    valeurs**, et un compte rendu qui les recalculerait pourrait annoncer autre
    chose que ce que le point de jugement avait montre.

    L'emplacement s'y ajoute parce que le nom de fichier seul ne situe rien :
    l'operateur veut pouvoir aller le chercher.
    """
    return Panneau(TITRE_ECRIT, list(panneau_de_profil(pose).lignes) + [
        LigneChiffree(LIBELLE_EMPLACEMENT, str(Path(pose.chemin).parent))])


def ligne_d_etat_de_la_pose(pose: ProfilPose, ascii_seul: bool = False) -> str:
    """`●  profil par défaut posé · <chaîne>`. Un CONSTAT, jamais une touche."""
    glyphe = jetons.glyphes(ascii_seul)["complete"]
    return f"{glyphe}  " + SEPARATEUR_D_ETAT.join((ETAT_POSE, pose.chaine))


class EcranPoseDuProfil(PanneauConfirmation):
    """Le point de jugement : ce qui SERA ecrit, avant que rien ne le soit.

    **Rien n'est ecrit ici** (`EPIC11-ARB-4`). Le cartouche est bati sur
    l'**apercu** -- `palier_projet.apercu_de_profil`, qui lit et valide le
    fichier sans toucher au disque du projet --, jamais sur le resultat de la
    pose : un cartouche construit sur le resultat serait un compte rendu
    portant le titre « A ecrire », et il ne pourrait plus rien empecher.

    **Aucun nom n'est editable** : cet ecran ne passe aucun modele de noms, et
    `EcranChiffre` en pose un vide de lui-meme, si bien que `Tab` n'a aucune
    destination et que `traiter` le rend inerte. Ce n'est pas une garde ajoutee
    ici, c'est la consequence de ne pas donner de noms -- et la ligne de
    raccourcis ne l'annonce pas non plus, les deux allant ensemble.

    `poser` est **injecte et REQUIS**, sans valeur par defaut : c'est le finding
    `K3`, paye quatre fois dans cet epic -- « un `Callable | None = None`
    assorti d'un `if ... is not None` fait de l'oubli de cablage un silence ».
    """

    titre = PALIER_DU_PROFIL
    #: Un ATTRIBUT de classe, jamais une `@property` : la garde d'epic de
    #: `test_repli_ascii.py` lit `classe.raccourcis` au niveau de la CLASSE.
    raccourcis = RACCOURCIS_POSE
    #: Un passage : un point de jugement franchi ne reste pas sur le chemin du
    #: retour.
    TRANSITOIRE = True

    def __init__(self, apercu: ProfilPose, source, *,
                 poser: Callable[[Path], None],
                 defaut_actuel: str = "") -> None:
        super().__init__(panneau_de_la_pose(apercu, defaut_actuel),
                         issues_de_la_pose(bool(defaut_actuel)),
                         objet=OBJET_DU_BANDEAU)
        #: L'apercu montre. Il porte les trois valeurs ; l'ecran n'en
        #: recalcule aucune.
        self.apercu = apercu
        #: Le fichier designe, tel que la pose le relira. C'est **la source**,
        #: jamais le chemin de destination calcule par l'apercu : les confondre
        #: ferait relire le profil a l'endroit ou on s'apprete a l'ecrire.
        self.source = Path(source)
        #: Le nom du defaut que cette pose remplacerait, ou la chaine vide.
        self.defaut_actuel = defaut_actuel
        self._poser = poser
        # Pose APRES `super().__init__`, qui construit l'ecran `textual` : le
        # rappel est une methode liee de cette instance, donc il n'existe pas
        # avant elle.
        self._sur_issue = self._declencher

    def _declencher(self, issue: Issue) -> None:
        """Ce que chaque issue fait, et **les deux font quelque chose**.

        `EPIC11-ARB-89` : une annulation qui ne rendrait pas la main serait un
        blocage sec.

        **L'annulation n'est PAS un rappel injecte, et c'est delibere.** Elle
        depile, ce qui est exactement ce que `Échap` fait deja sur cet ecran :
        un `annuler: Callable | None = None` assorti d'un `if ... is not None`
        serait le finding `K3` pris a l'envers -- un point d'injection que
        personne n'injecte, donc une branche morte qu'aucune garde ne peut
        distinguer d'un oubli. La garde des rappels cables l'a mesuree comme
        telle avant que cette ligne ne soit ecrite.

        `poser`, lui, reste requis et sans defaut : l'ecran ne sait pas ou
        ecrire, et il ne peut pas etre monte sans le savoir.
        """
        if issue.cle == CLE_POSER:
            self._poser(self.source)
            return
        application = _application_montee(self)
        if application is not None:
            application.action_remonter()


class EcranProfilPose(EcranResultat):
    """L'ecran de succes : le profil est pose, et on le DIT.

    **C'est un grief separe d'Egan**, releve le 2026-09-06 sur un autre
    parcours : « pas d'ecran de succes et on revient directement a la page pour
    lancer une calibration. Incoherent avec le reste. » Un geste qui ecrit et
    rend la main sans compte rendu est indistinguable d'un geste qui n'a rien
    fait.

    Une sous-classe et **rien d'autre**, exactement comme `EcranMireEcrite` et
    `EcranResultatDuScan` : elle ne redonne que le **titre**, segment du milieu
    du bandeau. « Retour aux ateliers » n'est pas ecrit ici -- `EcranResultat`
    l'ajoute d'office en queue de ses suites, et l'ecrire une seconde fois
    donnerait deux lignes pour une seule sortie.
    """

    titre = PALIER_DU_PROFIL


# ===========================================================================
# L'ecran de choix
# ===========================================================================

class EcranProfilParDefaut(CoutureExplorateur, ObjetTravaille, Palier):
    """La liste des profils du projet, plus la porte vers un fichier.

    **La couture clavier est le mixin du depot, pas un second routage** :
    `CoutureExplorateur` est pose **avant** `Palier` dans les bases, et il
    route toutes les touches de la zone explorateur (`EPIC11-ARB-48` : « un
    composant unique [...] partout ou la TUI demande un chemin »). Cet ecran ne
    recable aucune touche a la main ; il ne fournit que les deux gestes que la
    couture lui laisse -- ou mene `Échap`, et ce que `⏎` fait de la cible.

    `confirmer` est **injecte et REQUIS**, sans valeur par defaut (finding
    `K3`) : l'ecran ne sait pas ce qui suit le choix, et il ne peut simplement
    pas etre monte sans savoir a qui le rendre.
    """

    titre = PALIER_DU_PROFIL
    raccourcis = RACCOURCIS_PROFIL

    #: **La famille de memoire de session de cet explorateur.** Les profils
    #: sont une famille a part (`explorateur.FAMILLE_PROFILS`) : on va les
    #: chercher dans un dossier d'outillage -- une valise de calibration, un
    #: dossier partage --, pas dans le dossier des rushes ni dans celui des
    #: projets. Partager la memoire des rushes ferait rouvrir l'explorateur sur
    #: un volume de tournage a chaque designation de profil.
    FAMILLE_D_EXPLORATION = FAMILLE_PROFILS

    def __init__(self, dossier=None, *,
                 confirmer: Callable[[Path], None],
                 profils: Sequence[Mapping] | None = None,
                 defaut: Mapping | None = None) -> None:
        super().__init__()
        self.dossier = Path(dossier) if dossier is not None else None
        self._confirmer = confirmer
        #: Ce que l'appelant a INJECTE, retenu pour que :meth:`relire` le
        #: rejoue. Sans ces deux champs, l'injection ne survivait pas au
        #: premier `reprendre()` : un banc qui injectait puis montait mesurait
        #: le DISQUE en croyant mesurer son injection, et il le faisait en
        #: silence -- l'ecran se recomposait simplement sans elle. C'est la
        #: forme inverse du motif `K3` (un point d'injection sans injecteur),
        #: trouvee par la couche 2 de la revue du 2026-09-07.
        self._profils_injectes = profils
        self._defaut_injecte = defaut
        self.choix = ChoixDuProfil(self._entrees())
        self.zone = ZONE_LISTE
        #: La droite du bandeau, portee par `ObjetTravaille`.
        self.objet = OBJET_DU_BANDEAU
        # **Monte a la CONSTRUCTION et non a l'ouverture**, comme `E3-1` et
        # `E3-5` : l'explorateur lit `Path.cwd()`, et le lire plus tard ferait
        # dependre le dossier de depart du moment ou l'on appuie.
        self.explorateur = Explorateur(montrer_fichiers=True,
                                       accepte=profil_acceptable)
        self._etat_a_dire = ""

    # -- lecture -------------------------------------------------------------

    def _appliquer_la_zone(self) -> None:
        """Poser la ligne de raccourcis de la zone courante.

        **`raccourcis` reste un ATTRIBUT, jamais une propriete** : la garde
        d'epic de `test_repli_ascii.py` lit `classe.raccourcis` au niveau de la
        CLASSE, et une propriete ferait echapper cet ecran a la mesure.
        """
        self.raccourcis = (raccourcis_de_l_explorateur(self.explorateur)
                           if self.zone == ZONE_EXPLORATEUR
                           else RACCOURCIS_PROFIL)

    def relire(self) -> None:
        """Recomposer la liste depuis le disque, en gardant le fichier designe.

        Appelee au retour sur cet ecran : un profil pose entre-temps doit
        apparaitre, et l'ancien defaut doit cesser de porter sa mention. Le
        fichier designe dans l'explorateur, lui, **survit** -- il ne vient pas
        du registre, donc rien de ce qu'on relit ne le concerne.
        """
        designe = self.choix.fichier
        self.choix = ChoixDuProfil(self._entrees())
        if designe is not None:
            self.choix.poser_le_fichier(designe)

    def _entrees(self) -> tuple[EntreeDeProfil, ...]:
        """La composition de la liste, **en un seul endroit**.

        La construction et :meth:`relire` passaient par deux appels distincts
        a `entrees_du_profil`, et le second oubliait `profils=` et `defaut=`.
        Deux compositions divergent a la premiere retouche ; celle-ci diverge
        des le premier `reprendre()`.
        """
        return entrees_du_profil(self.dossier,
                                 profils=self._profils_injectes,
                                 defaut=self._defaut_injecte)

    def reprendre(self) -> None:
        """Ce que cet ecran fait quand on **revient** dessus : il relit d'abord.

        Sans elle, revenir de l'ecran de succes montrerait encore l'ancien
        defaut -- le palier au-dessus a le meme geste, et pour la meme raison
        (`Palier.reprendre`, defaut `V2-M2`).
        """
        self.relire()
        self.zone = ZONE_LISTE
        self._appliquer_la_zone()
        super().reprendre()

    def ligne_d_entree(self, rang: int, utile: int) -> str:
        """Une entree : la **fleche seule**, le nom en colonne, sa mention.

        Aucune case a cocher (`EPIC11-ARB-126`, verbatim d'Egan : « Flèche
        seule ! C'est uniquement dans les listes à cocher qu'on trouve les
        deux. »). On ne pose qu'un profil par defaut ; une case promettrait
        qu'on puisse en retenir deux.

        La colonne du nom est la meme qu'une entree porte le curseur ou non :
        sans quoi les noms danseraient d'une colonne a chaque `↑`.
        """
        ascii_seul = self.app.ascii_seul
        entree = self.choix.entrees[rang]
        marque = (self.app.glyphes["curseur"]
                  if rang == self.choix.curseur else " ")
        # **Le repli precede le CALAGE, et c'est un defaut mesure** : le nom de
        # la porte est `autre fichier…`, `abreger_nom` ne replie **que** ce
        # qu'il abrege -- un nom qui tient en ressort intact --, et
        # `jetons.ajuster` replie ensuite, une fois la colonne posee.
        # `…` vaut une colonne, `...` en vaut trois : la mention de cette
        # ligne-la partait donc DEUX colonnes plus a droite que les autres en
        # `--ascii`, et l'oeil perdait la colonne que ce calage existe pour
        # tenir. Mesure au plancher, sur cet ecran, avant que la ligne ne soit
        # ecrite. **Le meme defaut vit dans `E3-5`**, d'ou ce rendu est
        # decline : il est remonte au rapport plutot que corrige ici, le
        # fichier appartenant a un autre lot.
        nom = jetons.abreger_nom(_replie(entree.nom, ascii_seul),
                                 LARGEUR_DU_NOM, ascii_seul)
        # **Le calage se compte en COLONNES, jamais en caracteres** (couche 2
        # de la revue, 2026-09-07). `str.ljust` -- que `{nom:<33}` est --
        # compte des caracteres ; un ideogramme en occupe deux. Mesure exacte :
        # un nom de 16 ideogrammes plus `.json` fait 37 colonnes,
        # `abreger_nom` le rend a 32 colonnes mais **19 caracteres**, et le
        # calage ajoute alors 14 espaces au lieu d'un. La mention -- la seule
        # chose qui dise ce que la ligne EST -- part 13 colonnes trop a droite
        # et se fait amputer a droite par `ajuster`.
        #
        # Le mode `--ascii` PASSE (`日` y vaut `?`, une colonne) : c'est le mode
        # nominal qui casse, et c'est pourquoi une garde qui ne jouerait que
        # l'ASCII ne verrait rien. Le nom vient de `designated_from`, donc d'un
        # fichier que l'operateur a nomme : le regime est atteignable.
        #
        # **Cinquieme occurrence dans le depot**, apres `atelier_exports_lot`,
        # `atelier_pdf_lots`, `cadences` et `projet_inventaire`, qui portent
        # tous la meme correction sous le nom `_a_gauche`. Les trois jumeaux
        # encore fautifs -- `atelier_scan_calibration.py`, `atelier_pdf.py`,
        # `atelier_scan.py` -- sont verses en dette : ils appartiennent a
        # d'autres lots.
        gauche = (f"{INDENT_DU_CURSEUR}{marque} "
                  + jetons.caler_a_gauche(nom, LARGEUR_DU_NOM, ascii_seul))
        return jetons.ajuster(gauche + _replie(entree.mention, ascii_seul),
                              utile, ascii_seul).rstrip()

    def lignes_de_la_liste(self, utile: int) -> list[str]:
        """La liste, avec ses `…` quand elle deborde."""
        total = len(self.choix.entrees)
        premier, dernier = self.choix.fenetre()
        points = jetons.points_d_abregement(self.app.ascii_seul)
        rendues: list[str] = []
        if premier > 0:
            rendues.append(INDENT_DU_CURSEUR + points)
        rendues += [self.ligne_d_entree(rang, utile)
                    for rang in range(premier, dernier + 1)]
        if dernier < total - 1:
            rendues.append(INDENT_DU_CURSEUR + points)
        return rendues

    def lignes_du_pied(self) -> list[str]:
        """L'etat du profil par defaut. **Trois etats, pas deux.**

        Aucun profil pose ; un profil pose et present ; un profil pose dont le
        fichier a disparu. Le troisieme n'est pas le premier : le projet a
        travaille avec ce profil, et le taire ferait croire qu'il n'y en a
        jamais eu. C'est exactement la distinction que
        `palier_projet.lignes_du_profil` tient un cran au-dessus, et les deux
        lisent le **meme** couple `(entree, chemin)` -- `profil_par_defaut`
        rend les deux separement parce qu'ils ne disent pas la meme chose.
        """
        if self.dossier is None:
            return [INDENT_DU_CURSEUR + ETAT_SANS_DEFAUT]
        entree, chemin = profil_par_defaut(self.dossier)
        if entree is None:
            return [INDENT_DU_CURSEUR + ETAT_SANS_DEFAUT]
        ascii_seul = self.app.ascii_seul
        nom = nom_du_profil(entree)
        etat = "substitute" if chemin is None else "complete"
        # Meme geste que `ligne_d_entree` : le repli passe AVANT la
        # composition. Le tiret cadratin de la phrase vaut une colonne et son
        # repli en vaut deux.
        phrase = nom if chemin is not None else (
            f"{nom} \u2014 {MENTION_FICHIER_DISPARU}")
        return [INDENT_DU_CURSEUR
                + jetons.marque(etat, _replie(phrase, ascii_seul), ascii_seul)]

    def _filet(self, utile: int) -> str:
        """Le filet du pied, avec son titre a gauche.

        **Le repli precede la mesure**, jamais l'inverse : `jetons.ajuster`
        replierait bien le titre au dessin, mais la longueur du trait serait
        alors calculee sur la geometrie de l'AUTRE mode. Les deux traits font
        une colonne, donc l'ecart serait ici de zero -- ce qui est exactement
        ce qui rend le defaut invisible le jour ou le titre gagne un caractere
        a repli large. Meme geste que `EcranResultat.lignes_du_journal`.
        """
        ascii_seul = self.app.ascii_seul
        trait = "-" if ascii_seul else "\u2500"
        titre = jetons.replier_ascii(TITRE_DU_PIED) if ascii_seul else TITRE_DU_PIED
        tete = f"{trait * 2} {titre} "
        return tete + trait * max(utile - jetons.colonnes(tete), 0)

    def lignes(self) -> list[str]:
        if self.zone == ZONE_EXPLORATEUR:
            # **Par mots-cles, et la largeur BRUTE** : `Explorateur.lignes`
            # prend `(largeur, titre, libelle, ascii_seul)` et retire lui-meme
            # ses marges. Un appel positionnel poserait `ascii_seul` dans
            # `titre`, et il a deja coute un `TypeError` en production.
            return self.explorateur.lignes(
                self.app.size.width, titre=TITRE,
                libelle=LIBELLE_AUTRE_FICHIER,
                ascii_seul=self.app.ascii_seul)
        utile = jetons.largeur_utile(self.app.size.width)
        corps = ["", INDENT_DU_TEXTE + TITRE, ""]
        corps += self.lignes_de_la_liste(utile)
        corps += ["", self._filet(utile), ""]
        corps += self.lignes_du_pied()
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

        `EPIC11-ARB-56`. Elle compte les profils du registre et dit lequel est
        le defaut -- deux faits. Un refus verbatim, quand il y en a un, prend
        toute la place : c'est ce que l'operateur a besoin de lire.
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
        entree = None if self.dossier is None else profil_par_defaut(
            self.dossier)[0]
        parts.append(ETAT_SANS_DEFAUT if entree is None
                     else ETAT_DEFAUT.format(nom=nom_du_profil(entree)))
        return SEPARATEUR_D_ETAT.join(parts)

    # -- rendu ---------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="corps-profil-par-defaut")
        return [Vertical(self._corps, id="centre-profil-par-defaut")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        self._corps.update(bloc_peint(
            self.lignes(), jetons.largeur_utile(self.app.size.width),
            self.app, rang=self.rang_du_curseur()))
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
        """Mesurable sans clavier, comme tous les ecrans du depot.

        **Le motif de la frappe PRECEDENTE s'efface D'ABORD, et dans LES DEUX
        zones.** Il ne l'etait que dans la liste : la remise a zero vivait
        **apres** l'aiguillage vers l'explorateur, si bien qu'un refus pose par
        :meth:`_valider_l_explorateur` survivait a tout ce qui suivait -- le
        curseur bougeait dans l'explorateur et la ligne d'etat continuait
        d'accuser le fichier precedent, et surtout une designation **reussie**
        rendait la main a la liste en portant encore le refus de celle d'avant.
        Une ligne d'etat qui accuse un fichier accepte est un chemin d'erreur
        qui ment, et `EPIC11-ARB-56` -- « la ligne d'etat porte une mesure » --
        l'interdit a la lettre.

        Elle est ici plutot que dans chaque branche parce que la couture
        elle-meme ecrit dans `_etat_a_dire` (`CoutureExplorateur` y pose la
        phrase du collage) : effacer avant d'aiguiller est le seul point ou
        aucune ecriture de la frappe COURANTE n'est encore faite.
        """
        self._etat_a_dire = ""
        if self.zone == ZONE_EXPLORATEUR:
            traite = self._traiter_l_explorateur(touche, caractere)
            self._appliquer_la_zone()
            return traite
        if touche in ("up", "down"):
            return self.choix.deplacer(-1 if touche == "up" else 1)
        if touche == "enter":
            return self._valider()
        if caractere and caractere.isprintable():
            # **La frappe est CONSOMMEE**, et ce n'est pas un oubli : la ligne
            # de raccourcis de cet ecran n'annonce aucune sortie par lettre,
            # donc laisser remonter la frappe jusqu'au binding applicatif `q`
            # fermerait l'application sur une touche que rien n'annonce. `F1`
            # et `Échap`, eux, sont annonces : ils traversent jusqu'a
            # l'application, qui les cable.
            return True
        return False

    def _valider(self) -> bool:
        """Ce que `⏎` fait, entree par entree. **Aucune ne reste muette.**

        Sur « autre fichier… », il ouvre l'explorateur : il n'y a rien a
        confirmer, et consommer la touche sur rien serait indistinguable d'un
        clavier casse.

        Sur un profil du registre dont le **fichier a disparu**, il ne bloque
        pas (`EPIC11-ARB-89`) : il pose le motif en ligne d'etat et laisse la
        porte « autre fichier… » ouverte a un rang de la. L'entree reste
        affichee -- elle est vraie de ce que le projet a utilise -- mais elle
        ne peut rien poser.
        """
        entree = self.choix.courante
        if entree.designe_un_fichier:
            self._confirmer(entree.chemin)
            return True
        if entree.est_un_profil:
            self._etat_a_dire = jetons.marque(
                "substitute", f"{entree.nom} — {MENTION_FICHIER_DISPARU}",
                self.app.ascii_seul)
            return True
        return self._ouvrir_l_explorateur()

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

        Le refus vient du coeur (`read_designated_document`) et voyage
        **verbatim** (`EPIC11-ARB-30`) : la TUI met en forme, elle n'interprete
        pas, elle ne resume pas, elle ne requalifie pas. L'ecran **reste sur
        l'explorateur** : la cible est fautive, pas le geste, et refermer ferait
        recommencer la navigation. Le choix precedent reste actif sans qu'aucune
        restauration ait a etre ecrite -- rien n'a ete pose.
        """
        cible = self.explorateur.valider()
        if cible is None:
            self._etat_a_dire = jetons.marque(
                "substitute", "rien a valider", self.app.ascii_seul)
            return
        try:
            profile_designation.read_designated_document(cible)
        except profile_designation.ProfileDesignationError as refus:
            self._etat_a_dire = jetons.marque("absent", str(refus),
                                              self.app.ascii_seul)
            return
        self.choix.poser_le_fichier(cible)
        self.zone = ZONE_LISTE
        self._appliquer_la_zone()


# ===========================================================================
# Le PARCOURS -- un `if` et un appel a poser dans `ChaineReelle`
# ===========================================================================

#: Ce qui separe deux mots dans un nom de classe en casse chameau. Pose une
#: fois : la derivation du code de refus est la seule a s'en servir.
_AVANT_UNE_MAJUSCULE = re.compile(r"(?<!^)(?=[A-Z])")


def code_du_refus(refus: BaseException) -> str:
    """Le code d'un refus, **derive de son nom de classe**.

    `CibleSansProjet` rend `CIBLE_SANS_PROJET`, `ProfileDesignationError` rend
    `PROFILE_DESIGNATION_ERROR`. **Une derivation plutot qu'une table**, et
    c'est le meme choix mesure que `projet_inventaire.code_du_refus` : une
    table serait une seconde redaction du coeur, qui perimerait **en silence**
    le jour ou un refus de plus serait publie -- l'ecran afficherait alors un
    code vide ou celui d'un autre refus.
    """
    return _AVANT_UNE_MAJUSCULE.sub("_", type(refus).__name__).upper()


def refus_de_la_pose(refus: BaseException) -> EcranRefus:
    """L'ecran d'un refus. Le message y voyage **verbatim** (`EPIC11-ARB-30`).

    Un refus du coeur n'est pas un « pas encore » : `EcranPasEncore` annonce une
    absence a venir, la ou un profil illisible ou une cible qui n'est pas un
    projet annoncent un **fait**. `EcranRefus` porte trois sorties dont aucune
    n'est un blocage sec -- `⏎ revenir aux ateliers`, `Échap retour`, `Q
    quitter`.
    """
    return EcranRefus(code_du_refus(refus), str(refus))


@dataclass
class _CablageDeLaPose:
    """Ce qui relie les trois ecrans, **hors de `ChaineReelle`**.

    Cette classe existe pour une raison de DECOUPAGE, pas de confort : le seul
    endroit du depot qui monte le palier Projet est
    `atelier_extraction_ecriture.ChaineReelle`, qu'un autre agent tient. Sans
    elle, cabler cet ecran demanderait d'y ecrire une vingtaine de lignes qui
    savent lire un profil, batir un apercu et monter un compte rendu. Avec
    elle, il y reste **un `if` et un appel** -- la meme forme exactement que
    `ouvrir_l_inventaire_du_projet` et que les trois `ouvrir_l_atelier_*`.

    Les deux points d'entree du coeur sont **injectes** : c'est ce qui rend le
    parcours mesurable sans disque, et c'est aussi ce qui permet a un banc de
    verifier que la pose appelle bien `poser_le_profil_par_defaut` et non une
    seconde ecriture ecrite ici.
    """

    application: Any
    dossier: Any
    apercevoir: Callable[..., ProfilPose] = apercu_de_profil
    poser_au_coeur: Callable[..., ProfilPose] = poser_le_profil_par_defaut

    def confirmer(self, source) -> None:
        """Temps 1 : l'apercu. **Rien n'est ecrit** (`EPIC11-ARB-4`).

        Les deux refus possibles -- une cible qui n'est pas un projet, un
        profil que le coeur refuse -- montent un `EcranRefus` avec leur phrase
        **verbatim**, jamais une trace de pile. Le second ne devrait pas
        arriver depuis l'explorateur, qui relit deja la cible ; il peut arriver
        depuis une entree du registre dont le fichier a change sous nos pieds,
        et c'est exactement le regime ou une trace de pile serait peinte
        par-dessus l'interface.
        """
        try:
            apercu = self.apercevoir(self.dossier, source)
        except (CibleSansProjet,
                profile_designation.ProfileDesignationError) as refus:
            self.application.descendre(refus_de_la_pose(refus))
            return
        entree, _chemin = profil_par_defaut(self.dossier)
        self.application.descendre(EcranPoseDuProfil(
            apercu, source, poser=self.poser,
            defaut_actuel=nom_du_profil(entree)))

    def poser(self, source) -> None:
        """Temps 2 : l'ecriture, **par le coeur**, puis le compte rendu.

        `poser_le_profil_par_defaut` appelle
        `profile_designation.import_designated_profile(..., as_default=True)` :
        ce parcours n'ecrit ni le fichier ni l'entree de manifest, si bien que
        l'artefact produit est identique a celui de `mmu set-default-profile`
        **par construction** plutot que par verification.
        """
        try:
            pose = self.poser_au_coeur(self.dossier, source)
        except (CibleSansProjet,
                profile_designation.ProfileDesignationError) as refus:
            self.application.descendre(refus_de_la_pose(refus))
            return
        ascii_seul = getattr(self.application, "ascii_seul", False)
        ecran = EcranProfilPose(panneau_du_profil_pose(pose),
                                objet=OBJET_DU_BANDEAU)
        self.application.descendre(ecran)
        # **`poser_etat` APRES le montage**, jamais avant : la ligne d'etat est
        # posee sur l'ecran monte, et un ecran pas encore empile la perdrait au
        # premier dessin.
        ecran.poser_etat(ligne_d_etat_de_la_pose(pose, ascii_seul))


def ouvrir_le_profil_par_defaut(app, dossier_projet, *,
                                apercevoir=apercu_de_profil,
                                poser=poser_le_profil_par_defaut) -> bool:
    """Ce que l'entree *Profil de calibration par defaut* du palier ouvre.

    **Trois sorties, aucune n'est un blocage sec** (`EPIC11-ARB-89`) :

    * aucune application montee -> faux, et l'appelant sait que rien n'a bouge ;
    * aucun projet ouvert -> `EcranPasEncore` qui NOMME ce qui manque **et
      quand** il arrive : un `EcranPasEncore` sans echeance est indistinguable
      d'un abandon (`MQ-8`, meme correctif) ;
    * tout va bien -> l'ecran de choix, sa confirmation et son compte rendu
      cables les uns aux autres.

    Les deux points d'entree du coeur sont **injectes** pour la mesure ; le
    produit, lui, n'a pas de version degradee -- leurs valeurs par defaut sont
    le vrai chemin.
    """
    application = _application_montee(app)
    if application is None:
        return False
    if not dossier_projet:
        application.descendre(EcranPasEncore(CE_QUI_MANQUE_SANS_PROJET,
                                             QUAND_LE_PROFIL_PAR_DEFAUT))
        return True
    cablage = _CablageDeLaPose(application, Path(dossier_projet),
                               apercevoir=apercevoir, poser_au_coeur=poser)
    # Le rappel est passe EN MOT-CLE DE CONSTRUCTION, par une methode liee du
    # porteur : c'est la seule route que la garde des rappels cables voit.
    ecran = EcranProfilParDefaut(Path(dossier_projet),
                                 confirmer=cablage.confirmer)
    application.descendre(ecran)
    return True


__all__ = [
    "CE_QUI_MANQUE_SANS_PROJET",
    "CLE_ANNULER",
    "CLE_AUTRE_FICHIER",
    "CLE_FICHIER_DESIGNE",
    "CLE_POSER",
    "ChoixDuProfil",
    "EcranPoseDuProfil",
    "EcranProfilParDefaut",
    "EcranProfilPose",
    "EntreeDeProfil",
    "ETAT_DEFAUT",
    "ETAT_DES_PROFILS",
    "ETAT_POSE",
    "ETAT_SANS_DEFAUT",
    "ETAT_SANS_PROFIL",
    "ETAT_UN_PROFIL",
    "HAUTEUR_DE_LA_LISTE",
    "LIBELLE_ANNULER",
    "LIBELLE_AUTRE_FICHIER",
    "LIBELLE_DEFAUT_ACTUEL",
    "LIBELLE_EMPLACEMENT",
    "LIBELLE_POSER",
    "LIBELLE_REMPLACER",
    "MENTION_FICHIER_DESIGNE",
    "MENTION_FICHIER_DISPARU",
    "MENTION_PAR_DEFAUT",
    "OBJET_DU_BANDEAU",
    "PALIER_DU_PROFIL",
    "PREFIXE_DE_PROFIL",
    "QUAND_LE_PROFIL_PAR_DEFAUT",
    "RACCOURCIS_POSE",
    "RACCOURCIS_PROFIL",
    "TITRE",
    "TITRE_DU_PIED",
    "TITRE_ECRIT",
    "ZONE_EXPLORATEUR",
    "ZONE_LISTE",
    "code_du_refus",
    "entrees_du_profil",
    "issues_de_la_pose",
    "ligne_d_etat_de_la_pose",
    "ouvrir_le_profil_par_defaut",
    "panneau_de_la_pose",
    "panneau_du_profil_pose",
    "profil_acceptable",
    "refus_de_la_pose",
]
