# -*- coding: utf-8 -*-
"""Les six ecrans que les quatre ateliers partagent (story 11.1).

Confirmer, avancer, interrompre, ecraser, refuser, conclure. Aucun atelier ne
les possede en propre : ils sont livres une fois et consommes tels quels.

**Le motif n'est pas l'economie, c'est la couture.** La retrospective de
l'Epic 7 instruit la classe « defaut de couture entre deux stories » sur un cas
mesure -- deux cotes corrects, testes isolement, et aucun test capable de
constater l'appel manquant entre eux. Livrer la confirmation dans le premier
atelier puis la redecouvrir dans les trois suivants fabriquerait exactement ce
profil : quatre implementations d'un meme contrat, chacune verte chez elle.
"""
from __future__ import annotations

import subprocess
import sys
import threading

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from ..progression import EmetteurProgression, EstimateurTempsRestant
from . import jetons
from .avancement import Avancement, Journal
from .coque import ObjetTravaille, Palier
from .noms import LIMITE, ModeleNoms
from .panneau import (
    RIEN_ECRIT,
    ChoixExclusif,
    Issue,
    LigneChiffree,
    Panneau,
)

#: Ce que la ligne d'etat dit pendant une edition, quand le nom courant est
#: acceptable : **une mesure du nom en cours**, verbatim de la maquette
#: `E2-3b` (« 31 caracteres sur 48 -- le nom reste valide »).
#:
#: **Elle disait auparavant `Edition des noms. Echap abandonne, Entree
#: valide.`**, c'est-a-dire deux noms de touche et un conseil d'usage dans la
#: zone ou `EPIC11-ARB-56` n'admet qu'une mesure -- verbatim : la ligne d'etat
#: « ne porte **aucune touche** [...] **aucun conseil d'usage** ». Les deux
#: touches sont deja sur la ligne des raccourcis de cet ecran, ou est leur
#: place ; l'ecart etait donc doublement gratuit. Trouve au lot G de la story
#: 11.4, en confrontant les maquettes `E2-*` a leurs ecrans reels : la maquette
#: portait la mesure, l'ecran portait le conseil, et aucun banc ne les
#: comparait.
#:
#: **La limite est LUE de `noms.LIMITE`**, elle-meme lue de
#: `io.naming.CANONICAL_ID_MAX_LENGTH` : un `48` ecrit ici serait la troisieme
#: ecriture d'une regle qui n'en admet qu'une.
PHRASE_NOM_VALIDE = "le nom reste valide"

#: Ce que la ligne d'etat dit quand le nom courant est REFUSE : la consequence,
#: verbatim de la maquette `E2-3c` (« l'action « Extraire » reste
#: inaccessible »). Le nom de l'action est lu du choix de l'ecran, jamais ecrit
#: ici : `E2-3` extrait, `T4-1` ecrase, et les deux autres ateliers nomment
#: encore autre chose.
PHRASE_ACTION_INACCESSIBLE = "reste inaccessible"


def _accord_caracteres(longueur: int) -> str:
    """`1 caractère` / `50 caractères`. Le singulier vaut aussi pour zero."""
    return f"{longueur} caractère{'s' if longueur > 1 else ''}"


def mesure_de_l_edition(longueur: int) -> str:
    """`31 caracteres sur 48 -- le nom reste valide` (ligne d'etat de `E2-3b`).

    Appelee seulement quand le nom courant est acceptable : le cas refuse porte
    :func:`mesure_du_refus`, qui est **aussi** une mesure.
    """
    return f"{_accord_caracteres(longueur)} sur {LIMITE} — {PHRASE_NOM_VALIDE}"


def mesure_du_refus(longueur: int, action: str, ascii_seul: bool = False) -> str:
    """`✕  50 caracteres sur 48 admis — l'action « Extraire » reste inaccessible`.

    **C'est la reconciliation d'`EPIC11-ARB-25` et d'`EPIC11-ARB-56`**, que le
    lot G avait mesuree comme une contradiction sans la trancher. La ligne
    d'etat rendait `noms.MOTIF_TROP_LONG`, c'est-a-dire « deux noms coupes au
    meme prefixe seraient le meme lot » : un **motif de conception**, que
    l'`ARB-56` interdit verbatim -- la ligne d'etat « ne porte **aucune touche**
    [...] **aucun conseil d'usage** [...] **aucun motif de conception** » --
    et que l'`ARB-25` exige par ailleurs de dire -- « le message nomme le motif
    au lieu de dire « invalide » ».

    **La maquette `E2-3c` les reconcilie par la MISE EN PAGE, pas par le
    texte** : le motif descend dans le **corps** (`✕ Le nom est trop long : 50
    caracteres pour 48 admis.`) et la ligne d'etat ne garde qu'une **mesure**
    plus sa consequence. C'est cette mise en page qui est posee ici et dans
    :meth:`EcranChiffre.lignes_du_refus`.

    Le glyphe ouvre la ligne, comme sur toutes les lignes d'etat qui portent un
    etat : `jetons.jeton_d_etat` exige qu'il OUVRE UNE COLONNE pour teinter la
    ligne, et `DESIGN.md` section 5 veut les deux canaux, jamais la couleur
    seule.
    """
    glyphe = jetons.glyphes(ascii_seul)["absent"]
    return (f"{glyphe}  {_accord_caracteres(longueur)} sur {LIMITE} admis"
            f" — l'action « {action} » {PHRASE_ACTION_INACCESSIBLE}")

#: Ce qu'elle dit quand `Entree` est presse sans qu'aucune issue soit retenue.
#: `EPIC11-ARB-7` veut qu'aucune ne soit preselectionnee ; il ne veut pas que la
#: touche reste muette.
#: Conserve pour les ecrans qui refusent une issue **indisponible** -- un nom
#: invalide bloque l'action principale. Depuis `EPIC11-ARB-45`, une validation
#: n'est plus jamais muette faute de retenue : elle suit l'issue sous le
#: curseur. Ce texte ne parle donc plus d'`Espace`.
AUCUNE_ISSUE = "Aucune issue disponible sous le curseur."

#: Ce que le point de jugement annonce **hors edition**, verbatim de la
#: maquette `E2-3` (ligne 23), `F1 aide` mis a part -- voir le docstring de
#: :data:`RACCOURCIS_EDITION_DES_NOMS` pour ce que l'ecran promet et ce qu'il
#: ne promet pas.
#:
#: **Les libelles sont ceux de la maquette et non ceux du code d'avant**, qui
#: disait `↑↓ naviguer   ⏎ choisir`. La regle de nommage est celle que
#: `ecran_projet.py:104` pose deja et que le finding `F-17` a payee : *un
#: libelle nomme ce que la touche fait a cet instant*. Ici `⏎` **valide** une
#: issue et `↑↓` **choisit** parmi elles ; `Tab éditer les noms` **nomme sa
#: destination**, ce que `Tab éditer` ne faisait pas.
#: **Majuscule d'affichage, touche NUE en minuscule** -- la regle des
#: majuscules de raccourci, ecrite en entier dans `coque.py`. La lettre
#: annoncee ici est en majuscule ; la touche cablee reste la minuscule.
RACCOURCIS_CONFIRMATION = ("⏎ valider  ↑↓ choisir  Tab éditer les noms  "
                           "Échap retour")

#: Ce que le meme ecran annonce **pendant l'edition d'un nom** (`E2-3b`,
#: `E2-3c`), et c'est le coeur du finding `I8`.
#:
#: **`EcranChiffre` n'avait PAS de ligne contextuelle** : sa ligne etait un
#: attribut de classe unique, donc elle ne changeait pas en entrant dans les
#: noms. Les trois touches qu'elle annoncait faisaient alors autre chose que ce
#: qu'elle disait -- `⏎` valide le nom, `↑↓` passe d'un nom a l'autre, et
#: `Tab éditer` designait l'entree dans un mode ou l'on etait deja, alors que
#: `Tab` en **sort** (`EPIC11-ARB-68` : « `Tab` **nomme sa DESTINATION** »).
#: Et surtout : **`Ctrl+R`, livre par le lot `A`, n'etait annonce nulle part**
#: -- la classe de defaut que `coque.py:510` documente (« une touche annoncee
#: en ligne de raccourcis devenait **inerte** »), prise ici par l'autre bout.
#:
#: **Ce que la ligne dit, et ce qu'elle ne dit pas.** `⏎` et `Tab` appellent
#: litteralement le meme `ModeleNoms.confirmer()` : les annoncer separement
#: casserait la seconde moitie de la regle `F-17` (« deux gestes identiques
#: portent le meme mot »), donc ils partagent un jeton. `⌫` n'y figure pas,
#: faute de place mesuree, et parce que le retour arriere d'un champ de saisie
#: est la seule touche de cette ligne dont la convention se devine.
#:
#: **Le precedent invoque ici n'existe plus, et le comptage etait faux**
#: (finding `R18`, 2026-08-31). Ce commentaire renvoyait au « `↑↓ liste` tombe
#: de `RACCOURCIS_RECENTS` » -- arbitrage annule par `EPIC11-ARB-122`, qui a
#: rendu le jeton a cette ligne-la. L'argument de place tient toujours pour
#: `⌫`, mais il se tient tout seul : il ne s'adosse plus a un precedent
#: disparu.
#:
#: **Mesure des deux regimes**, parce qu'un repli ASCII peut ALLONGER une
#: ligne : **66** colonnes en UTF-8, **71** repliee (`⏎` rend `Entree`, cinq
#: colonnes de plus), pour une zone utile de 76. Les cinq colonnes rendues par
#: le resserrement sont comptees ici, ce que l'ancienne redaction (69 / 74) ne
#: faisait pas.
#: MESURE: 66/71
RACCOURCIS_EDITION_DES_NOMS = ("↑↓ nom suivant  Ctrl+R remettre  "
                               "⏎ ou Tab les choix  Échap annuler")

#: Ce que `E2-5` annonce, **journal compris** (finding `I8`). La maquette
#: portait `Tab journal` et `EcranResultat.on_key` ne traitait pas `tab` du
#: tout : le journal d'une extraction terminee n'etait relisible de nulle part.
#: La promesse est desormais tenue plutot que retiree -- voir
#: :meth:`EcranResultat.basculer_le_journal`.
RACCOURCIS_RESULTAT_AVEC_JOURNAL = ("⏎ choisir  ↑↓ naviguer  Tab journal  "
                                    "Échap ateliers  F1 aide")

#: Le meme ecran **sans journal a montrer**. La ligne est contextuelle :
#: « elle ne montre que ce qui marche sur l'ecran courant » (`DESIGN.md`
#: section 4), et c'est le motif deja livre pour `Ctrl+H cachés`, qui
#: n'apparait que dans un dossier qui porte des caches.
#:
#: **`Q quitter` -> `F1 aide` (`EPIC11-ARB-140`, 2026-09-02).** Les quatre
#: maquettes de resultat du depot (`E2-5`, `E3-8`, `E5-5`, le rapport du Scan)
#: sont unanimes : elles portent `F1 aide` et **aucune** ne porte `Q quitter`.
#: La redaction n'est pas inventee ici -- elle est **identique** a
#: `atelier_scan_parcours.RACCOURCIS_RAPPORT`, livree bien avant, et
#: `test_arb140_passages_sans_q_quitter.py` l'epingle **par reference** pour
#: que les deux ne divergent pas.
RACCOURCIS_RESULTAT = "⏎ choisir  ↑↓ naviguer  Échap ateliers  F1 aide"

#: Ce que `Tab journal` doit pouvoir montrer pour meriter d'etre annonce.
#: Trois lignes : moins vaudrait la peine de replier le cartouche pour rien.
LIGNES_MINIMALES_DU_JOURNAL = 3


# ---------------------------------------------------------------------------
# `EPIC11-ARB-245` -- le cartouche qui DEFILE
#
# Egan, par invite, le 2026-09-05 : « Faire defiler le cartouche », puis devant
# la maquette `T4-2` : « super je valide ». Le mecanisme est repris de
# `jetons.fenetre_de_liste` / `jetons.recadrer_la_fenetre`, c'est-a-dire de
# l'IDIOME QUE LE DEPOT PORTE DEJA -- celui de la fenetre `11-17 sur 27` de la
# maquette `X4`, employe tel quel par `atelier_pdf_lots.lignes_de_liste` et par
# `atelier_exports_lot`. Il n'est pas reecrit ici : ces deux fonctions
# reservent leur ligne d'indicateur **avant** le decoupage, sans quoi la
# derniere entree se cacherait derriere le `…` qui annonce justement qu'elle
# existe, et c'est exactement le mode de panne qu'un pli doit ne pas avoir.
#
# **Ce que ce pli ajoute a l'idiome, et pourquoi.** Une liste de lots defile
# sous un curseur : l'indicateur y dit des RANGS (`11-17 sur 27`). Un cartouche
# n'a pas de curseur et ses lignes ne sont pas interchangeables : un rang n'y
# apprend rien. La ligne de pli NOMME donc ce qu'elle cache -- « la suite :
# bornes, destination, 3 noms apparies » --, et c'est la seule chose qui
# empeche de valider une ecriture destructive sans savoir ce qu'on n'a pas lu.
# Un nombre de lignes muet aurait rendu le defilement inacceptable ; c'est le
# nommage qui l'a fait accepter.
# ---------------------------------------------------------------------------

#: Ce que la ligne de pli dit du sens ou elle regarde. Deux redactions, une par
#: sens : « la suite » pour ce qui reste a lire, « plus haut » pour ce qui a
#: defile au-dessus. Le pli du bas est celui de la maquette `T4-2` ; celui du
#: haut existe des qu'on a fait defiler, et le taire ferait disparaitre en
#: silence les phrases de consequence si un jour elles cessaient d'etre fixes.
#: Le cadre PROPRE du cartouche : la ligne de titre `┌ À écrire ───┐` en haut,
#: la fermeture `└───┘` en bas. Deux lignes, posees par le `border` du
#: `Vertical#cartouche` que monte :meth:`EcranChiffre.contenu`.
#:
#: **Ce n'est PAS `jetons.BORDURE`**, qui est le cadre de l'ECRAN et que
#: `jetons.hauteur_centrale` deduit deja. Les deux quantites valent un, et
#: c'est une coincidence : rien ne les lie, et le nommer par le jeton de
#: l'ecran reviendrait a refaire ici la soustraction verticale que la
#: frontiere negative de la revue T2 de la 11.9 interdit -- interdiction
#: fondee, quatre modules l'ayant recopiee avant le 2026-09-04.
LIGNES_DU_CADRE_DU_CARTOUCHE = 2

PLI_VERS_LE_BAS = "la suite"
PLI_VERS_LE_HAUT = "plus haut"

#: Le motif de la ligne de pli, verbatim de la maquette `T4-2` :
#: `↓ 8 sur 14 lues — la suite : bornes, destination, 3 noms appariés`.
MOTIF_DU_PLI = "{fleche} {lues} sur {total} lues — {sens} : {noms}"

#: Ce que la ligne de pli dit des noms qu'elle n'a pas eu la place d'ecrire.
#: **Elle ne les tait jamais : elle les compte.** Une enumeration coupee par
#: `jetons.ajuster` perdrait ses derniers noms sans le dire, ce qui est
#: exactement le defaut que la ligne de pli existe pour ne pas avoir.
MOTIF_DU_RESTE = "+{compte} autres"

#: Ce que la ligne de pli dit quand elle ne cache que des respirations --
#: aucune ligne nommee. Le cas est atteignable : deux lignes vides consecutives
#: en queue de cartouche. Rendre une enumeration vide laisserait
#: `— la suite : ` en l'air.
NOMS_SANS_NOM = "des respirations"


@dataclass(frozen=True)
class LigneDefilante:
    """Une ligne de cartouche qui peut passer sous le pli, et son NOM.

    ``nom`` est ce que la ligne de pli ecrit quand cette ligne est cachee ; il
    vaut ``None`` pour une respiration, qui ne s'annonce pas. ``groupe`` est sa
    forme collective, employee quand plusieurs lignes **consecutives** portent
    le meme nom -- `3 noms appariés` plutot que trois fois `nom apparié`.

    **Le nom voyage AVEC le texte, jamais dans une liste parallele.** Deux
    listes appariees par position sont le mutant `M33` de la story 5.6 : une
    permutation y reste verte tant que les fabriques remplissent uniformement,
    et une ligne de pli qui nommerait la mauvaise ligne est precisement le
    mensonge que ce mecanisme existe pour ne pas produire.
    """

    texte: str
    nom: str | None = None
    groupe: str | None = None


@dataclass(frozen=True)
class Pli:
    """Ce qu'un cartouche replie AFFICHE, et ce qu'il en dit.

    ``lues`` est une **ligne d'eau** : le rang le plus loin atteint depuis
    l'ouverture, jamais le rang courant. Un operateur qui a lu la fin puis est
    remonte a lu la fin ; un compteur qui redescendrait le lui redirait non lu.
    """

    lignes: list[str]
    premier: int
    dernier: int
    lues: int
    total: int

    @property
    def replie(self) -> bool:
        """Vrai quand le cartouche ne tient pas entier, donc quand il defile."""
        return self.lues < self.total or self.premier > 0


def _groupes_de_noms(defilantes) -> list[str]:
    """Les noms d'une tranche de lignes, respirations retirees, groupes.

    Les lignes **consecutives** de meme nom se fondent en une entree : c'est ce
    qui rend `3 noms appariés` la ou trois entrees separees auraient rempli la
    ligne de pli a elles seules. Non consecutives, elles restent distinctes --
    deux blocs de meme nom separes par autre chose sont deux blocs.
    """
    groupes: list[str] = []
    compte = 0
    courante: LigneDefilante | None = None

    def fermer() -> None:
        if courante is None or not compte:
            return
        if compte > 1 and courante.groupe:
            groupes.append(courante.groupe.format(compte=compte))
        else:
            groupes.append(courante.nom)

    for ligne in defilantes:
        if ligne.nom is None:
            continue
        if courante is not None and ligne.nom == courante.nom:
            compte += 1
            continue
        fermer()
        courante, compte = ligne, 1
    fermer()
    return groupes


def enumeration_des_noms(defilantes, budget: int,
                         ascii_seul: bool = False) -> str:
    """Les noms caches, autant qu'il en tient dans `budget` colonnes.

    Ce qui ne tient pas se **compte** (:data:`MOTIF_DU_RESTE`) plutot que de
    disparaitre : une enumeration tronquee par `jetons.ajuster` perdrait ses
    derniers noms en silence, et la promesse de la ligne de pli avec eux.

    **Au moins un nom sort toujours**, meme trop long : il sera abrege par
    `ajuster` comme n'importe quelle ligne, ce qui est visible, la ou une
    enumeration vide ne dirait rien du tout.
    """
    groupes = [_replie(nom, ascii_seul) for nom in _groupes_de_noms(defilantes)]
    if not groupes:
        return _replie(NOMS_SANS_NOM, ascii_seul)
    gardes: list[str] = []
    for nom in groupes:
        candidats = gardes + [nom]
        reste = len(groupes) - len(candidats)
        texte = ", ".join(candidats)
        if reste:
            texte += ", " + MOTIF_DU_RESTE.format(compte=reste)
        if gardes and jetons.colonnes(texte) > budget:
            break
        gardes = candidats
    reste = len(groupes) - len(gardes)
    texte = ", ".join(gardes)
    if reste:
        texte += ", " + MOTIF_DU_RESTE.format(compte=reste)
    return texte


def _replie(texte: str, ascii_seul: bool) -> str:
    """Le repli ASCII, applique **avant** toute mesure de colonnes.

    `…` vaut une colonne et `...` en vaut trois : mesurer puis replier ferait
    deborder de deux colonnes une ligne calee juste. C'est la regle que
    `LigneChiffree.rendu` et `jetons.abreger_nom` appliquent deja.
    """
    return jetons.replier_ascii(texte) if ascii_seul else texte


def ligne_de_pli(sens: str, caches, lues: int, total: int, largeur: int,
                 ascii_seul: bool = False) -> str:
    """`↓ 8 sur 14 lues — la suite : bornes, destination, 3 noms appariés`.

    Le compte **et** les noms, jamais l'un sans l'autre : le compte dit combien
    il reste, les noms disent quoi. La maquette `T4-2` porte les deux, et c'est
    a ce prix que le defilement a ete accepte sur un point de jugement
    destructif.
    """
    fleche = _replie("↓" if sens == PLI_VERS_LE_BAS else "↑", ascii_seul)
    entete = MOTIF_DU_PLI.format(fleche=fleche, lues=lues, total=total,
                                 sens=_replie(sens, ascii_seul), noms="")
    budget = max(largeur - jetons.colonnes(entete), 0)
    return entete + enumeration_des_noms(caches, budget, ascii_seul)


def plier_le_cartouche(fixes, defilantes, hauteur: int,
                       premier_visible: int = 0, deja_lues: int = 0,
                       largeur: int = jetons.largeur_de_cartouche(),
                       ascii_seul: bool = False) -> Pli:
    """Le cartouche replie a `hauteur` lignes : les fixes, une fenetre, ses plis.

    ``fixes`` ne defile **jamais** -- ce sont les phrases de consequence, que
    `EPIC11-ARB-89` exige visibles avant toute ecriture destructive consciente.
    Les faire defiler rendrait l'avertissement atteignable par un geste, donc
    manquable, et le pli n'aurait fait que deplacer le defaut.

    La fenetre elle-meme vient de :func:`jetons.fenetre_de_liste`, sans une
    ligne d'arithmetique de plus : elle reserve ses lignes d'indicateur avant
    de decouper, en haut comme en bas.
    """
    place = max(hauteur - len(fixes), 0)
    premier, dernier = jetons.fenetre_de_liste(len(defilantes),
                                               premier_visible, place)
    lignes = list(fixes)
    lues = max(deja_lues, len(fixes) + dernier + 1)
    total = len(fixes) + len(defilantes)
    if premier > 0:
        lignes.append(ligne_de_pli(PLI_VERS_LE_HAUT, defilantes[:premier],
                                   lues, total, largeur, ascii_seul))
    lignes.extend(ligne.texte for ligne in defilantes[premier:dernier + 1])
    if dernier < len(defilantes) - 1:
        lignes.append(ligne_de_pli(PLI_VERS_LE_BAS, defilantes[dernier + 1:],
                                   lues, total, largeur, ascii_seul))
    return Pli(lignes=lignes, premier=premier, dernier=dernier, lues=lues,
               total=total)


def bloc(lignes, largeur: int, ascii_seul: bool = False) -> str:
    """Assemble des lignes en un bloc qui tient la largeur, ligne par ligne.

    **L'entonnoir unique de tout texte affiche.** Il fait deux choses qu'aucun
    appelant ne doit refaire : il ajuste a la largeur -- `textual` replie une
    ligne trop longue au lieu de la tronquer, et une ligne repliee dans un bloc
    decale tout ce qui suit -- et il replie en ASCII quand `--ascii` est
    demande. Sans lui, le repli ne couvrait que les glyphes d'etat, et la ligne
    de raccourcis restait pleine de `↑↓` et de `⏎` sur un terminal qui ne les
    rend pas (revue de vague 1, couche 2).
    """
    return "\n".join(jetons.ajuster(ligne, largeur, ascii_seul)
                      for ligne in lignes)


def bloc_peint(lignes, largeur: int, app, rang: int | None = None,
               etats=None):
    """Le meme bloc, **peint** (`EPIC11-ARB-47`, portee : aussi la story 11.1).

    Les cinq ecrans de ce module rendaient leur zone centrale en texte nu alors
    que la portee d'`EPIC11-ARB-47` les nomme explicitement -- « les cinq ecrans
    de la vague 2 **et** les quatre ecrans a issues de la story 11.1 ». Le
    defaut a ete trouve le 2026-08-29, sur relecture de la portee.

    ``rang`` force la ligne du curseur, et il n'est pas optionnel partout : la
    detection automatique de :func:`jetons.peindre` teste `startswith` sur le
    glyphe de curseur. Les issues d'un `ChoixExclusif` commencent bien par lui,
    donc la detection les trouve ; les suites d'un ecran de resultat sont
    indentees de deux espaces, donc elle ne les trouverait **pas** -- et ne
    colorerait rien, en silence. C'est la raison pour laquelle ce parametre
    existe plutot que d'etre devine.

    **L'ordre est le meme que partout** : la largeur se mesure sur le texte nu,
    la couleur s'ajoute apres.
    """
    ascii_seul = getattr(app, "ascii_seul", False)
    return jetons.peindre(
        [jetons.ajuster(ligne, largeur, ascii_seul) for ligne in lignes],
        ascii_seul=ascii_seul,
        sans_couleur=getattr(app, "sans_couleur", False),
        ligne_du_curseur=rang,
        etats=etats)


class EcranChiffre(ObjetTravaille, Palier):
    """Base des ecrans qui montrent un cartouche et un choix exclusif.

    Elle porte le rendu et la navigation ; les ecrans concrets ne fournissent
    que leur panneau, leurs issues et ce qu'ils font de l'issue retenue.
    """

    #: Reecrit par chaque ecran concret. **C'est la ligne HORS edition** : en
    #: edition, `_appliquer_les_raccourcis` pose
    #: :data:`RACCOURCIS_EDITION_DES_NOMS` sur l'instance.
    #:
    #: **Elle reste un ATTRIBUT et non une propriete**, et ce n'est pas un
    #: detail de style : la garde d'epic de `test_repli_ascii.py` balaye toutes
    #: les sous-classes de `Palier` et lit `classe.raccourcis` **au niveau de la
    #: CLASSE** -- une propriete y rendrait l'objet `property` et ferait
    #: echapper l'ecran a la mesure. Meme motif, et meme geste, que
    #: `EcranProjet._appliquer_la_zone`.
    raccourcis = "↑↓ parcourir  ⏎ choisir  Échap revenir"

    #: Ce que le titre du cartouche gagne en mode edition, verbatim des
    #: maquettes `E2-3b` et `E2-3c` (`À écrire — édition des noms`).
    #:
    #: **Les trois ecrans etaient le meme a un caret pres** (finding `I5`, vu
    #: sur les captures `20-` a `22-`) : meme titre de cartouche, meme ligne de
    #: raccourcis. Rien ne disait a l'operateur qu'il venait de changer de mode,
    #: et la seule difference visible etait un bloc de six colonnes au milieu du
    #: cartouche.
    SUFFIXE_EDITION = " — édition des noms"

    #: Un passage : le point de jugement chiffre est un passage.
    TRANSITOIRE = True

    def __init__(self, panneau: Panneau, choix: ChoixExclusif,
                 noms: ModeleNoms | None = None,
                 sur_issue: Callable[[Issue], None] | None = None,
                 objet: str = "") -> None:
        super().__init__()
        self.panneau = panneau
        self.choix = choix
        self.noms = noms or ModeleNoms()
        self._sur_issue = sur_issue
        #: La droite du bandeau, **donnee par l'atelier qui monte cet ecran**.
        #: Voir :meth:`objet_du_bandeau`.
        self.objet = objet
        self.issue_declenchee: Issue | None = None
        #: Motif affiche en ligne d'etat quand une validation est refusee.
        #: `None` tant que rien n'a ete refuse.
        self._refus_annonce: str | None = None

    # -- rendu --------------------------------------------------------------

    def lignes_du_panneau(self) -> list[str]:
        """Les lignes CHIFFREES du cartouche. Les noms sont des widgets a part.

        Ils l'etaient au depart : le cartouche etait un seul bloc de texte, donc
        aucun nom ne pouvait porter sa propre couleur, et un nom refuse etait
        rendu comme un nom valide. Un widget par nom rend l'etat `state-absent`
        de l'AC 2.3 exprimable, et le glyphe `✕` le double comme
        `DESIGN.md` section 5 l'exige.
        """
        return Panneau(self.panneau.titre, self.panneau.lignes).rendu(
            self.app.size.width, getattr(self.app, "ascii_seul", False))

    def lignes_du_cartouche(self) -> list[str]:
        """Ce que le cartouche AFFICHE, la ou :meth:`lignes_du_panneau` dit ce
        qu'il CONTIENT.

        Les deux se confondent partout sauf sur un ecran dont le cartouche
        **defile** (`EPIC11-ARB-245`) : la, le contenu vaut quinze lignes et
        l'affichage n'en montre que dix, la derniere nommant ce que les autres
        cachent. Le point de separation vit ici plutot que chez l'ecran
        defilant, parce que c'est `rafraichir` qui dessine, et qu'un ecran qui
        replierait son cartouche en surchargeant `lignes_du_panneau` rendrait
        du meme coup son contenu inaccessible a la mesure -- c'est-a-dire
        qu'aucun banc ne pourrait plus dire ce que le pli cache.
        """
        return self.lignes_du_panneau()

    def contenu(self) -> list[Widget]:
        self._chiffres = Static("\n".join(self.lignes_du_cartouche()),
                                id="chiffres")
        self._lignes_de_noms = [Static("", classes="nom")
                                for _ in range(len(self.noms))]
        enfants: list[Widget] = [self._chiffres]
        if self._lignes_de_noms:
            enfants.append(Static(""))
            enfants.extend(self._lignes_de_noms)
        self._corps = Vertical(*enfants, id="cartouche")
        # Le titre est porte par le CADRE (`┌ A ecrire ───┐`) et non par une
        # ligne de texte : c'est le motif de `DESIGN.md` 7.4, et il rend une
        # ligne de la zone centrale au contenu.
        self._corps.border_title = self.titre_du_cartouche()
        # **Le corps du refus, hors du cartouche**, comme la maquette `E2-3c`
        # le place. Il est masque tant qu'aucun nom n'est refuse : un `Static`
        # vide occuperait quand meme sa ligne et decalerait la geometrie
        # nominale d'un ecran partage par les quatre ateliers.
        self._refus_du_nom = Static("", id="refus-du-nom")
        self._refus_du_nom.display = False
        self._issues = Static("\n".join(self.rendu_des_issues()), id="issues")
        return [self._corps, self._refus_du_nom, Static(""), self._issues]

    def rendu_des_issues(self) -> list[str]:
        return self.choix.rendu(ascii_seul=self.app.ascii_seul)

    def on_mount(self) -> None:
        self.rafraichir()

    # -- ce qui change AVEC LE MODE (finding `I5`) ---------------------------

    def titre_du_cartouche(self, ascii_seul: bool | None = None) -> str:
        """`À écrire`, ou `À écrire — édition des noms` pendant l'edition.

        **Le repli ASCII est applique ICI**, et il manquait : `border_title`
        etait pose depuis `panneau.titre` sans passer par aucune table, si bien
        que la capture `20-E2-3-confirmation-ascii.svg` montre `À écrire`
        accentue au milieu d'un ecran par ailleurs entierement replie. Le
        separateur `—` de l'edition aurait ajoute le meme defaut, en pire :
        `REPLIS_DE_TEXTE` le rend `--`, donc sans repli il serait sorti tel
        quel sur un terminal qui ne le dessine pas.
        """
        if ascii_seul is None:
            ascii_seul = getattr(self.app, "ascii_seul", False)
        titre = self.panneau.titre
        if self.noms.en_edition:
            titre += self.SUFFIXE_EDITION
        return jetons.replier_ascii(titre) if ascii_seul else titre

    def libelle_de_l_action(self) -> str:
        """Le libelle de l'issue qui ecrit **SOUS LE CURSEUR**, lu du choix.

        `Extraire` sur `E2-3`, `Écraser et réextraire` sur `T4-1`, autre chose
        dans les trois ateliers a venir. C'est la seule chose que la ligne
        d'etat d'un refus de nom a besoin de nommer, et la recopier ferait une
        seconde redaction qui divergerait au premier libelle ajuste.

        **Elle lisait `choix.action_qui_ecrit`, c'est-a-dire la PREMIERE issue
        ecrivante de la liste** (story 11.4d, AC 5.1). Tant qu'un panneau n'en
        portait qu'une, les deux se confondaient ; depuis qu'`EPIC11-ARB-89`
        fait de « creer la version » une seconde issue ecrivante, la premiere
        n'est plus forcement celle que l'operateur vise, et la ligne d'etat
        annoncait alors l'inaccessibilite d'une action que personne n'avait
        demandee.

        **Les trois cas, et le troisieme est celui qui refuse de deviner** :

        * l'issue sous le curseur ecrit -- c'est elle, sans ambiguite ;
        * elle n'ecrit pas, et le panneau ne porte qu'**une** issue ecrivante --
          c'est elle : il n'y a rien a confondre, et c'est le regime de presque
          tous les ecrans du produit ;
        * elle n'ecrit pas et le panneau en porte **plusieurs** -- on rend une
          chaine vide plutot que d'en elire une. Nommer la premiere serait
          exactement le `find` fautif que cette methode vient de perdre.
        """
        sous_le_curseur = self.choix.issue_sous_le_curseur
        if sous_le_curseur is not None and sous_le_curseur.ecrit:
            return sous_le_curseur.libelle
        ecrivantes = self.choix.actions_qui_ecrivent
        return ecrivantes[0].libelle if len(ecrivantes) == 1 else ""

    def lignes_du_refus(self) -> list[str]:
        """Le corps de `E2-3c` : le motif du nom refuse, **et rien de plus**.

        Vide quand le nom sous le curseur passe -- c'est ce qui garde la
        geometrie nominale de `E2-3` intacte.

        **Une seule ligne, la ou la maquette en montre deux.** Sa seconde
        (`Retirez 2 caractères, ou Ctrl+R pour remettre le nom proposé.`) dit
        deux choses qui vivent desormais ailleurs : le nombre a retirer se lit
        sur le compteur `50/48` de la ligne du nom, et `Ctrl+R` est annonce par
        :data:`RACCOURCIS_EDITION_DES_NOMS`. Une troisieme ligne de corps sur un
        ecran partage par les quatre ateliers se paierait en hauteur, et la
        hauteur est le budget que `E2-3` a le moins.
        """
        if not len(self.noms) or self.noms.courant.valide:
            return []
        table = jetons.glyphes(getattr(self.app, "ascii_seul", False))
        return [f"{table['absent']} {self.noms.courant.motif}"]

    def _appliquer_les_raccourcis(self) -> None:
        """Poser la ligne de raccourcis du MODE courant (finding `I8`).

        Meme geste que `EcranProjet._appliquer_la_zone` : une constante de
        module posee sur l'instance, jamais une propriete -- les deux lignes
        restent ainsi balayees une par une par la garde d'epic.
        """
        self.raccourcis = (RACCOURCIS_EDITION_DES_NOMS if self.noms.en_edition
                           else type(self).raccourcis)

    # -- rendu ---------------------------------------------------------------

    def rafraichir(self) -> None:
        """Reecrit les blocs et la ligne d'etat. Ne remonte aucun widget."""
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur = self.app.size.width
        cartouche = jetons.largeur_de_cartouche(largeur)
        ascii_seul = self.app.ascii_seul
        self._appliquer_les_raccourcis()
        self._corps.border_title = self.titre_du_cartouche(ascii_seul)
        self._chiffres.update(
            bloc_peint(self.lignes_du_cartouche(), cartouche, self.app))
        for rang, widget in enumerate(self._lignes_de_noms):
            nom = self.noms.noms[rang]
            widget.update(bloc([self.noms.ligne(rang, cartouche,
                                                ascii_seul=ascii_seul)],
                               cartouche, ascii_seul))
            widget.set_class(not nom.valide, "nom-refuse")
            widget.set_class(rang == self.noms.curseur, "nom-courant")
        # **Le rang de la ligne surlignee est PASSE explicitement** (AC 8.5).
        # Il ne s'agit pas d'un second compteur : c'est LE compteur du modele,
        # `ChoixExclusif.curseur`, lu la ou il vit. L'auto-detection de
        # `peindre` le retrouvait par `startswith` sur le glyphe de curseur --
        # ce qui marche tant que le rendu des issues commence par lui, et cesse
        # de marcher sans bruit le jour ou une issue s'indente ou se prefixe.
        # Un surlignage qui disparait ne leve rien : il n'y a plus de ligne
        # accentuee, et c'est tout.
        self._issues.update(bloc_peint(self.rendu_des_issues(),
                                       jetons.largeur_utile(largeur), self.app,
                                       rang=self.choix.curseur))
        lignes_du_refus = self.lignes_du_refus()
        # `display` et non un texte vide : un `Static` vide garde sa ligne.
        self._refus_du_nom.display = bool(lignes_du_refus)
        if lignes_du_refus:
            self._refus_du_nom.update(bloc_peint(
                lignes_du_refus, jetons.largeur_utile(largeur), self.app))
        self.poser_etat(self.etat())
        super().rafraichir()

    def etat(self) -> str:
        """Ce que dit la ligne d'etat. `EPIC11-ARB-35` : un CONSTAT.

        Le compteur `n/48` n'est **pas** ici : il est sur la ligne du nom, dans
        le cartouche, comme les maquettes `E2-3b` et `E2-3c` le montrent. En
        ligne d'etat il ne designait pas lequel des noms il comptait.

        **Le nom refuse rend desormais une MESURE et non son motif**, et c'est
        la tension `EPIC11-ARB-25` / `EPIC11-ARB-56` tranchee -- voir
        :func:`mesure_du_refus`. Le motif, lui, n'est pas perdu : il descend
        dans le corps (:meth:`lignes_du_refus`), ou la maquette `E2-3c` le
        place.
        """
        if self.noms.en_edition:
            courant = self.noms.courant
            if courant.valide:
                return mesure_de_l_edition(courant.longueur)
            return self.mesure_du_nom_refuse(courant.longueur)
        if self._refus_annonce is not None:
            return self._refus_annonce
        return RIEN_ECRIT

    def mesure_du_nom_refuse(self, longueur: int) -> str:
        """La ligne d'etat d'un nom refuse, mode d'affichage compris."""
        return mesure_du_refus(longueur, self.libelle_de_l_action(),
                               getattr(self.app, "ascii_seul", False))

    # -- navigation ---------------------------------------------------------

    def on_key(self, evenement) -> None:
        """Un seul point d'entree clavier, et il ARRETE ce qu'il traite.

        Le dispatch est ecrit ici plutot qu'eclate en `key_<nom>` parce que
        `Echap` doit etre **intercepte** en edition : sans `evenement.stop()`,
        la touche continue de monter jusqu'a l'application, dont le raccourci
        depilerait l'ecran en plus d'abandonner l'edition -- deux effets pour
        une touche.
        """
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Applique une touche. Rend vrai si l'ecran l'a consommee.

        Separee du gestionnaire d'evenement pour etre mesurable sans clavier :
        les tests de la logique n'ont pas a fabriquer d'evenement `textual`.

        **En edition, l'ecran consomme TOUT.** Une touche non reconnue qui
        remonterait a l'application y rencontrerait le raccourci `q`, qui
        quitte : taper « q » dans un nom fermait la TUI et perdait l'edition,
        sans confirmation (revue de vague 1, couche 1). Le mode d'edition est un
        mode : il capture le clavier, sinon ce n'en est pas un.
        """
        if self.noms.en_edition:
            return self._traiter_en_edition(touche, caractere)
        if touche == "down":
            self.choix.deplacer(1)
            return True
        if touche == "up":
            self.choix.deplacer(-1)
            return True
        # **`Tab` nomme sa DESTINATION** (`EPIC11-ARB-68`), et c'est la
        # convention que tout le reste de la TUI pose deja
        # (`ecran_projet.py:104`). Il remplace `e`, qui etait la seule porte
        # vers l'edition : deux portes pour le meme geste, c'est une porte que
        # personne ne documente. Egan l'avait demandee trois fois, sur trois
        # ecrans differents ; la mesure d'avant correctif disait
        # `traiter("tab") -> False`, c'est-a-dire que `Tab` ne faisait RIEN ici.
        if touche == "tab":
            if not len(self.noms):
                return False
            self.noms.entrer_en_edition()
            self._refus_annonce = None
            return True
        if touche == "enter":
            return self.valider()
        # `escape` et `q` ne sont pas notre affaire hors edition : l'application
        # depile ou quitte.
        return False

    def _traiter_en_edition(self, touche: str, caractere: str | None) -> bool:
        """Le clavier du mode edition. Il consomme tout, y compris l'inconnu.

        **La branche du texte passe EN PREMIER, et c'est tout le correctif**
        (`EPIC11-ARB-68`). L'ordre precedent testait `touche == "r"` avant elle :
        la lettre n'entrait donc jamais dans le champ, elle appelait
        `remettre()`. Mesure du 2026-08-29, champ vide, « rush_hiver » tape ->
        la valeur rendue etait le nom d'origine. Nos lots s'appellent
        `projet_demo_rush_01_25fps` : la lettre `r` y est **structurelle**, et
        l'echec etait silencieux -- il rendait une valeur plausible.

        **Pourquoi cette forme plutot qu'un simple echange de deux branches.**
        Une regle d'ordre entre branches se re-casse au prochain raccourci
        ajoute, et le defaut ne se voit pas a la relecture : il faut taper la
        lettre. En sortant le texte AVANT toute touche nommee, la regle
        « aucune lettre n'est un raccourci dans un champ de saisie » devient
        **structurelle** -- un raccourci nomme `z` ajoute demain ne peut plus
        la casser, puisqu'il n'est jamais atteint pour un caractere.

        Le raccourci de remise est donc une **combinaison** (`ctrl+r`) : c'est
        la seule forme qui ne peut pas entrer en collision avec une saisie.
        """
        if caractere is not None and len(caractere) == 1 and caractere.isprintable():
            # Aucun filtrage a la frappe : un caractere refuse doit pouvoir
            # etre tape PUIS vu refuse (`EPIC11-ARB-25`).
            self.noms.taper(caractere)
            return True
        if touche == "down":
            self.noms.descendre()
        elif touche == "up":
            self.noms.monter()
        elif touche == "ctrl+r":
            self.noms.remettre()
        elif touche == "escape":
            self.noms.abandonner()
        elif touche in ("enter", "tab"):
            # **`Tab` SORT en gardant la saisie ; `Echap` sort en l'annulant.**
            # C'est la reponse a « comment on sort de l'edition des noms ? » :
            # trois sorties, et chacune dit ce qu'elle fait du texte tape.
            self.noms.confirmer()
        elif touche == "backspace":
            self.noms.effacer()
        return True

    def valider(self) -> bool:
        """`Entree` : declencher l'issue retenue, ou dire pourquoi c'est refuse."""
        issue = self.choix.valider()
        if issue is None:
            # AC 4.3 : `Entree` sans avoir choisi ne declenche aucune issue.
            self._refus_annonce = AUCUNE_ISSUE
            return True
        if issue.ecrit and not self.noms.valides:
            # AC 2.3 : l'action principale reste inaccessible tant qu'un nom
            # est refuse. On ne corrige pas a sa place, on n'ecrit pas -- mais
            # on DIT pourquoi : une touche qui ne fait rien et ne dit rien est
            # indistinguable d'un clavier casse.
            #
            # **Ce qui est DIT est une mesure, pas le motif** (`EPIC11-ARB-56`)
            # -- et le curseur va sur le nom fautif, ce qui fait apparaitre le
            # motif dans le corps par `lignes_du_refus`. Les deux moities de la
            # reponse arrivent donc ensemble, chacune a sa place.
            rang, _motif = next(iter(sorted(self.noms.motifs.items())))
            self.noms.curseur = rang
            self._refus_annonce = self.mesure_du_nom_refuse(
                self.noms.noms[rang].longueur)
            return True
        self._refus_annonce = None
        self.issue_declenchee = issue
        if self._sur_issue is not None:
            self._sur_issue(issue)
        return True

    # -- lecture, pour les ateliers et pour les tests ------------------------

    @property
    def action_principale_accessible(self) -> bool:
        """Vrai si l'issue qui ecrit peut aboutir en l'etat."""
        return self.noms.valides


class PanneauConfirmation(EcranChiffre):
    """`E2-3` -- le point de jugement. Rien n'a encore ete ecrit."""

    titre = "Confirmation"
    raccourcis = RACCOURCIS_CONFIRMATION


class EcranEcrasement(EcranChiffre):
    """`E2-3c` -- une confirmation **en propre**, distincte de la nominale.

    `EPIC11-ARB-4`, corollaire : ce n'est pas le panneau nominal avec une
    phrase de plus. Il dit ce qui existe deja, quand, ce que ca contient, ce
    qui en depend -- et ce qu'ecraser **ne fait pas** : les artefacts derives
    ne sont pas regeneres.
    """

    titre = "Ecrasement"
    raccourcis = RACCOURCIS_CONFIRMATION

    #: Ce qu'ecraser DETRUIT, et ce qu'il ne regenere pas. **Deux phrases
    #: courtes la ou il y en avait une de 96 colonnes** (`EPIC11-ARB-245`).
    #:
    #: L'ancienne redaction -- « Ecraser ne regenere pas ce qui en derive :
    #: planches et masters deja produits restent tels quels. » -- ne tenait pas
    #: dans les 72 colonnes d'un cartouche, et elle ne se repliait pas : tout
    #: texte d'ecran passe par `jetons.ajuster`, qui **abrege**. La phrase
    #: sortait donc coupee a « ... et masters deja pro… » -- c'est-a-dire que
    #: l'avertissement qu'`EPIC11-ARB-89` exige avant une ecriture destructive
    #: consciente etait ampute en plein milieu, dans les deux regimes, et
    #: qu'aucun banc ne le voyait. Deux lignes courtes, verbatim de la maquette
    #: `T4-2`, valent mieux qu'une longue qui compte sur un repli qui n'existe
    #: pas.
    ECRASER_DETRUIT = "Écraser supprime le lot déjà sur le disque, puis réécrit."
    NE_REGENERE_PAS = (
        "Les planches et masters déjà produits ne sont PAS regénérés.")

    #: L'indentation des phrases qui suivent la premiere : elles s'alignent
    #: sous son texte, apres le glyphe d'avertissement et son espace.
    RETRAIT_DES_CONSEQUENCES = "  "

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        #: Le rang de la premiere ligne defilante visible. Il n'est jamais pose
        #: directement : `jetons.recadrer_la_fenetre` le deduit de la ligne
        #: visee, comme pour les trois listes qui defilent deja dans la TUI.
        self._premier_visible = 0
        #: La ligne que `Ctrl+↓` / `Ctrl+↑` cherchent a amener dans la fenetre.
        self._ligne_visee = 0
        #: La ligne d'eau de lecture -- voir :class:`Pli`. Elle ne redescend
        #: jamais : ce qui a ete affiche une fois a ete lu.
        self._lues = 0

    # -- ce qui ne defile JAMAIS ---------------------------------------------

    def phrases_de_consequence(self, ascii_seul: bool = False) -> list[str]:
        """Les phrases qui restent AU-DESSUS DU PLI, quoi qu'il arrive.

        `EPIC11-ARB-89`, verbatim d'Egan : « la rigueur de l'outil ne doit pas
        empecher une ecriture destructive CONSCIENTE (apres avertissement) ».
        L'avertissement est donc ce qui ne peut pas se manquer : le faire
        defiler l'aurait rendu atteignable par un geste, c'est-a-dire
        oubliable, et le pli n'aurait fait que deplacer le defaut qu'il corrige.

        La premiere porte le glyphe d'avertissement du depot (`▲`, `!` en
        repli) ; les suivantes s'alignent sous elle.
        """
        glyphe = jetons.glyphes(ascii_seul)["substitute"]
        phrases = [self.ECRASER_DETRUIT, self.NE_REGENERE_PAS]
        return [f"{glyphe} {phrases[0]}"] + [
            self.RETRAIT_DES_CONSEQUENCES + phrase for phrase in phrases[1:]]

    def lignes_defilantes(self) -> list[LigneDefilante]:
        """Le detail reperable, qui peut passer sous le pli.

        Chaque ligne porte le NOM sous lequel la ligne de pli l'annoncera. La
        base n'en connait aucun -- elle ne sait pas ce que son panneau compte
        --, donc elle rend des lignes anonymes ; l'ecran concret les nomme.
        """
        return [LigneDefilante(texte)
                for texte in super().lignes_du_panneau()]

    # -- le cartouche, entier puis replie ------------------------------------

    def lignes_du_panneau(self) -> list[str]:
        """Le cartouche ENTIER, dans l'ordre qu'`EPIC11-ARB-245` tranche.

        Les phrases de consequence d'abord, une respiration, puis le detail.
        L'ordre precedent les mettait en QUEUE, c'est-a-dire exactement la ou
        un pli les aurait cachees les premieres.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        return (self.phrases_de_consequence(ascii_seul) + [""]
                + [ligne.texte for ligne in self.lignes_defilantes()])

    def hauteur_du_cartouche(self) -> int:
        """Les lignes que la grille laisse a l'INTERIEUR du cartouche.

        Derivee de la fenetre par `jetons.hauteur_centrale`, et de ce que
        :meth:`contenu` monte autour du cartouche : sa bordure (deux lignes),
        le corps du refus quand il est visible, une respiration, les issues.
        Ecrire dix ici serait une seconde source de verite, qui divergerait de
        la grille a la premiere issue ajoutee -- et une quatrieme issue est
        exactement ce que le lot F vient d'ajouter.
        """
        hauteur = getattr(getattr(self.app, "size", None), "height",
                          jetons.HAUTEUR_PLANCHER)
        autour = (LIGNES_DU_CADRE_DU_CARTOUCHE + len(self.lignes_du_refus())
                  + 1 + len(self.rendu_des_issues()))
        return max(jetons.hauteur_centrale(hauteur) - autour, 0)

    def pli(self) -> Pli:
        """Le cartouche replie a la hauteur courante, et ce qu'il en dit."""
        ascii_seul = getattr(self.app, "ascii_seul", False)
        largeur = getattr(getattr(self.app, "size", None), "width",
                          jetons.LARGEUR_PLANCHER)
        defilantes = self.lignes_defilantes()
        self._premier_visible = jetons.recadrer_la_fenetre(
            self._premier_visible, min(self._ligne_visee,
                                       max(len(defilantes) - 1, 0)),
            len(defilantes), self.place_defilante())
        replie = plier_le_cartouche(
            self.phrases_de_consequence(ascii_seul) + [""], defilantes,
            self.hauteur_du_cartouche(), self._premier_visible, self._lues,
            jetons.largeur_de_cartouche(largeur), ascii_seul)
        self._lues = replie.lues
        return replie

    def place_defilante(self) -> int:
        """Les lignes que la fenetre defilante peut occuper, plis compris.

        Elle vaut la hauteur du cartouche moins les lignes fixes -- les memes
        lignes fixes que :meth:`pli` pose, comptees une seule fois ici pour que
        `Ctrl+↓` avance exactement d'une page de ce qu'il montre.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        return max(self.hauteur_du_cartouche()
                   - len(self.phrases_de_consequence(ascii_seul)) - 1, 0)

    def lignes_du_cartouche(self) -> list[str]:
        return self.pli().lignes

    # -- le clavier du pli ---------------------------------------------------

    #: Les deux touches du pli, et **aucune n'est une fleche nue**
    #: (`EPIC11-ARB-245`). `↑↓` choisit une issue, `Ctrl+↑↓` lit le cartouche :
    #: un `↓` qui ferait l'un ou l'autre selon un focus invisible rendrait
    #: indistinguables deux effets dont l'un engage une ecriture destructive.
    #:
    #: `Ctrl+fleche` plutot qu'une touche de pagination : le depot n'en emploie
    #: AUCUNE, nulle part, et il emploie deja `Ctrl+A`, `Ctrl+D` et `Ctrl+R`.
    #: Une famille de touches neuve pour un seul ecran est une regle de plus a
    #: apprendre ; `Ctrl` + la fleche compose celle qui existe.
    TOUCHES_DU_PLI = {"ctrl+down": 1, "ctrl+up": -1}

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """`Ctrl+↓` / `Ctrl+↑` font defiler ; `↑↓` restent aux ISSUES.

        **Les deux gestes ne partagent aucune touche**, et ce n'est pas un
        confort. Un `↑↓` qui ferait defiler le cartouche OU changer d'issue
        selon un focus invisible rendrait indistinguables deux effets dont l'un
        engage une ecriture destructive : l'operateur qui croit lire la suite
        deplacerait son curseur sur `Écraser et réextraire`. La maquette `T4-2`
        porte la touche, et elle fait foi.
        """
        if touche in self.TOUCHES_DU_PLI:
            return self.defiler(self.TOUCHES_DU_PLI[touche])
        return super().traiter(touche, caractere)

    def defiler(self, pages: int) -> bool:
        """Avancer ou reculer d'une page de cartouche. Rend toujours vrai.

        Une **page** est ce que la fenetre montre A CET INSTANT, et non une
        valeur derivee de la place brute -- **et c'est un defaut mesure, pas
        une precaution**. Le premier jet prenait `place_defilante() - 1`, soit
        cinq lignes ; mais la fenetre ne montre cinq lignes que tant qu'il n'y
        a pas de ligne de pli EN HAUT, apres quoi elle n'en montre que quatre.
        Le pas depassait donc d'une ligne ce qui avait ete lu, et le cartouche
        a deux lots **sautait sa ligne 6** -- une ligne que rien n'affichait
        jamais, sur un ecran dont le pli existe justement pour que tout se
        lise. Trouve par le balayage exhaustif du banc, invisible sur un
        releve unique.

        La cible est donc posee depuis le BORD courant de la fenetre, ce qui
        garantit un recouvrement d'au moins une ligne entre deux ecrans.

        Le pas est borne a un minimum de une, sans quoi un cartouche dont la
        fenetre serait vide ne defilerait plus du tout. La touche est consommee
        meme en butee -- un `Ctrl+fleche` en bas de cartouche ne doit pas
        remonter a l'application, qui y verrait une touche libre.
        """
        replie = self.pli()
        visibles = max(replie.dernier - replie.premier + 1, 1)
        pas = max(visibles - 1, 1)
        total = len(self.lignes_defilantes())
        borne = replie.dernier if pages > 0 else replie.premier
        self._ligne_visee = min(max(borne + pages * pas, 0), max(total - 1, 0))
        return True


class EcranRefus(Palier):
    """`T5-1` -- un refus se nomme par son code, et la TUI n'y ajoute rien.

    `EPIC11-ARB-30` : le code **et** la phrase viennent du coeur. La TUI met en
    forme -- elle n'interprete pas, elle ne resume pas, elle ne requalifie pas.
    Le test mesure que le texte affiche est une **sur-chaine exacte** du texte
    leve.
    """

    titre = "Refus"
    #: **`Échap retour` y entre le 2026-09-06** (manque `MQ-7` de l'audit du
    #: parcours), et c'est `EPIC11-ARB-89` pris a la lettre : « toujours
    #: proposer [...] jamais un blocage sec ».
    #:
    #: Les deux issues annoncees etaient `⏎` -- qui depile **jusqu'aux
    #: ateliers**, donc jette le lot choisi et les reglages retenus -- et `Q`,
    #: qui quitte l'application. Mesure de l'audit sur le refus de l'atelier
    #: Exports : les deux sont des abandons, et `Échap`, la seule touche qui
    #: ramene au travail avec les reglages intacts, **marchait deja** sans
    #: etre annoncee. Un refus dont les seules portes visibles perdent le
    #: travail est un blocage sec habille.
    #:
    #: **Un littéral pour HUIT sites de montage** : aucun d'eux ne redefinit
    #: cette ligne ni ne passe de `raccourcis`, et
    #: `test_manques_des_lignes_d_etat.py` recense les huit a l'AST pour que
    #: l'ajout d'un neuvieme ramene un lecteur ici. La limite se dit aussi :
    #: pendant une tache, `action_remonter` arme l'interruption au lieu de
    #: depiler -- aucun des huit ne monte le refus dans ce regime, les deux du
    #: Scan appelant `oublier_la_tache()` juste avant.
    raccourcis = "⏎ revenir aux ateliers  Échap retour  Q quitter"

    #: Un passage : un refus se lit puis se quitte.
    TRANSITOIRE = True

    def __init__(self, code: str, message: str,
                 conserve: list[str] | None = None,
                 non_ecrit: list[str] | None = None,
                 suites: list[str] | None = None) -> None:
        super().__init__()
        self.code = code
        self.message = message
        self.conserve = conserve or []
        self.non_ecrit = non_ecrit or []
        self.suites = suites or []

    def lignes(self) -> list[str]:
        table = jetons.glyphes(getattr(self.app, "ascii_seul", False))
        lignes = [f"{table['absent']} {self.code}", "", self.message]
        for titre, entrees in (("Non ecrit", self.non_ecrit),
                               ("Conserve", self.conserve),
                               ("Suites", self.suites)):
            if entrees:
                lignes.append("")
                lignes.append(f"{titre}")
                lignes.extend(f"  {table['rattachement']} {e}" for e in entrees)
        return lignes

    def contenu(self) -> list[Widget]:
        return [Static(bloc_peint(self.lignes(),
                                  jetons.largeur_utile(self.app.size.width),
                                  self.app),
                       id="refus")]

    def on_key(self, evenement) -> None:
        if evenement.key == "enter":
            evenement.stop()
            self.app.revenir_aux_ateliers()


# ---------------------------------------------------------------------------
# Remettre un dossier a l'explorateur de fichiers du BUREAU
#
# **Le seul lanceur de processus du paquet `tui/`, et il est tolere NOMMEMENT**
# (`EPIC11-ARB-85`, 2026-08-30, en reponse a `Q9`). L'AC 5.2 de la story 11.0
# interdit `subprocess`, `Popen`, `os.system` et `os.exec*` dans tout
# `src/mixed_media_utility/tui/` ; son motif est `EPIC11-ARB-1` -- « le coeur
# est heberge, pas relance » --, c'est-a-dire ne pas re-invoquer `mmu` en
# sous-processus pour faire le travail du coeur. **Remettre un dossier au bureau
# ne fait aucun travail du coeur** : l'interdit garde un invariant que ce geste
# ne menace pas.
#
# La forme de la tolerance n'est pas negociable, et `test_coeur_en_processus.py`
# la mesure point par point :
#
# * **un seul** site d'appel, celui-ci ;
# * son argument est **un chemin de dossier**, jamais un module du depot ni une
#   commande -- c'est precisement ce que la frontiere continue de garder ;
# * il **rend une phrase** quand aucun bureau n'est joignable, il ne leve
#   jamais : un conteneur sans bureau est le regime nominal des bancs.
#
# **Le depot ne savait pas le faire, verifie avant d'ecrire.** La GUI de
# l'Epic 7 *choisit* un dossier (`gui.ecran_projet.ouvrir_un_dossier`, un
# selecteur `QFileDialog`) ; elle n'en ouvre aucun. Ce code vit ici -- avec les
# six ecrans partages -- parce que les quatre ateliers montent le meme
# `EcranResultat` et porteront la meme suite ; l'ecrire dans l'atelier
# Extraction le ferait recopier trois fois, et la tolerance porterait alors sur
# quatre fichiers au lieu d'un.
# ---------------------------------------------------------------------------

#: La commande qui remet un dossier a l'explorateur du bureau, par systeme.
#: **Une seule est tentee** : celle du systeme courant. En essayer plusieurs a
#: la file ferait ouvrir deux fenetres la ou deux commandes cohabitent.
#:
#: **Aucune de ces trois n'est un interpreteur ni une commande du depot**, et un
#: banc de frontiere le mesure : c'est la moitie de la tolerance d'`ARB-85`.
COMMANDES_D_EXPLORATEUR = {
    "darwin": ("open",),
    "win32": ("explorer",),
}

#: Ce qu'on tente partout ailleurs -- Linux et les BSD passent par la
#: specification freedesktop, dont `xdg-open` est l'implementation de reference.
COMMANDE_D_EXPLORATEUR_PAR_DEFAUT = ("xdg-open",)

#: Les systemes dont le code retour ne dit RIEN de la reussite. `explorer.exe`
#: rend 1 alors meme qu'il a ouvert la fenetre : le lire y fabriquerait un
#: message d'echec sur une ouverture reussie. On s'y fie a l'absence
#: d'exception, et a elle seule.
SYSTEMES_SANS_CODE_RETOUR_FIABLE = ("win32",)

#: Combien de temps on attend l'explorateur avant de considerer qu'il ne
#: repondra pas. Les trois commandes rendent la main aussitot apres avoir
#: delegue ; au-dela, c'est qu'il n'y a personne pour prendre le dossier.
DELAI_DE_L_EXPLORATEUR = 10

#: Ce qu'on dit quand le dossier a bien ete remis a l'explorateur. **Un fait**,
#: jamais un conseil (`EPIC11-ARB-56`) : le chemin ouvert, et rien d'autre.
FAIT_DOSSIER_OUVERT = "Dossier ouvert dans l'explorateur de fichiers : {chemin}"

#: Ce qu'on dit quand aucun explorateur ne repond. C'est le cas nominal d'un
#: conteneur sans bureau -- celui des bancs, et celui de la machine ou cette
#: suite a ete jugee decorative. **Le motif est nomme et le chemin reste
#: lisible** : c'est ce qui reste utilisable a la main.
MOTIF_SANS_EXPLORATEUR = (
    "Aucun explorateur de fichiers sur ce système ({commande}) : {chemin}")

#: Ce qu'on dit quand le dossier n'est plus la. Mesure **avant** l'appel : un
#: `xdg-open` sur un chemin absent ouvre le gestionnaire sur une erreur a lui,
#: que la TUI ne verrait jamais passer.
MOTIF_DOSSIER_ABSENT = "Ce dossier n'existe plus : {chemin}"

#: Les trois memes phrases pour un **fichier** remis a la visionneuse du
#: systeme (`EPIC11-ARB-42`, story 11.5 AC 7.7). Ce sont trois phrases et non
#: une reutilisation des precedentes : « Ce dossier n'existe plus » sur un
#: scan de planche enverrait l'operateur chercher un dossier.
FAIT_FICHIER_OUVERT = "Fichier ouvert dans la visionneuse du système : {chemin}"
MOTIF_SANS_VISIONNEUSE = (
    "Aucune visionneuse associée sur ce système ({commande}) : {chemin}")
MOTIF_FICHIER_ABSENT = "Ce fichier n'existe plus : {chemin}"


def ouvrir_dans_l_explorateur_du_systeme(dossier, *, lancer=None,
                                         systeme: str | None = None) -> str:
    """Remettre `dossier` a l'explorateur de fichiers du bureau.

    Rend **un fait a afficher, toujours** : le chemin ouvert, ou le motif qui a
    empeche de l'ouvrir. **Jamais d'exception nue.** Un conteneur sans bureau
    n'a pas d'`xdg-open` et `subprocess.run` y leve `FileNotFoundError` ; la
    laisser remonter ferait tomber la TUI sur une suite dont tout l'objet est
    de ne plus etre muette -- on aurait remplace « ca ne fait rien » par « ca
    plante », ce qui est pire.

    **Ce que cette fonction ne lance jamais** : un interpreteur, un module du
    depot, une commande `mmu`. Elle passe un **chemin de dossier** a l'un des
    trois ouvreurs de bureau, et c'est la forme exacte que la tolerance
    d'`EPIC11-ARB-85` accorde -- un banc de frontiere mesure l'argv reel.

    `lancer` et `systeme` ne sont la que pour les bancs : le produit n'en passe
    aucun et emprunte `subprocess.run` et `sys.platform`.
    """
    chemin = Path(dossier)
    if not chemin.is_dir():
        return MOTIF_DOSSIER_ABSENT.format(chemin=chemin)
    return _remettre_au_bureau(
        chemin, lancer=lancer, systeme=systeme,
        fait=FAIT_DOSSIER_OUVERT, sans_ouvreur=MOTIF_SANS_EXPLORATEUR)


def ouvrir_dans_la_visionneuse_du_systeme(fichier, *, lancer=None,
                                          systeme: str | None = None) -> str:
    """Remettre `fichier` a la visionneuse du systeme (`EPIC11-ARB-42`).

    C'est ce que `E3-4b` fait du scan de la planche muette : « le scan est
    souvent la seule copie lisible, et c'est precisement le fichier que la TUI
    vient d'analyser ».

    **Ce n'est pas un second point d'appel systeme, et c'est tout l'objet de sa
    forme** : elle partage avec l'ouvreur de dossier l'unique
    :func:`_remettre_au_bureau`, donc l'unique `subprocess.run` du paquet
    `tui/`. L'AC 7.7 le demande mot pour mot -- « l'appel systeme est isole en
    un seul point » --, et la frontiere AST de `test_coeur_en_processus.py`
    compte deja ce site : en ecrire un second l'aurait fait rougir, ce qui est
    exactement le service qu'on lui demande.

    Les trois ouvreurs de bureau (`open`, `explorer`, `xdg-open`) ouvrent
    indifferemment un dossier et un fichier -- ils delegent a l'association du
    systeme --, il n'y a donc **aucune seconde table de commandes** a tenir.

    Rend **un fait a afficher, toujours** : jamais une exception, jamais une
    trace. « Son echec (aucune visionneuse associee) doit etre un message,
    jamais une trace » (`EPIC11-ARB-42`, verbatim).
    """
    chemin = Path(fichier)
    if not chemin.is_file():
        # Mesure **avant** l'appel, meme motif que pour un dossier : un
        # `xdg-open` sur un chemin absent ouvre une erreur du systeme que la
        # TUI ne verrait jamais passer, et l'operateur lirait « rien ne s'est
        # passe » la ou le fichier a disparu.
        return MOTIF_FICHIER_ABSENT.format(chemin=chemin)
    return _remettre_au_bureau(
        chemin, lancer=lancer, systeme=systeme,
        fait=FAIT_FICHIER_OUVERT, sans_ouvreur=MOTIF_SANS_VISIONNEUSE)


def _remettre_au_bureau(chemin: Path, *, lancer, systeme: str | None,
                        fait: str, sans_ouvreur: str) -> str:
    """L'**unique** lancement de processus du paquet `tui/`.

    Les deux ouvreurs publics ne different que par ce qu'ils verifient avant
    (un dossier, un fichier) et par les phrases qu'ils rendent. Le lancement,
    lui, est ecrit une seule fois -- sans quoi la tolerance bornee
    d'`EPIC11-ARB-85` (« **un seul** site d'appel ») cesserait d'etre vraie a
    la premiere suite qui ouvre autre chose qu'un dossier.
    """
    systeme = sys.platform if systeme is None else systeme
    commande = COMMANDES_D_EXPLORATEUR.get(systeme,
                                           COMMANDE_D_EXPLORATEUR_PAR_DEFAUT)
    lancer = subprocess.run if lancer is None else lancer
    try:
        issue = lancer([*commande, str(chemin)], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=DELAI_DE_L_EXPLORATEUR)
    except (OSError, subprocess.SubprocessError):
        # `FileNotFoundError` (aucun binaire), `PermissionError`, un delai
        # depasse : les trois disent la meme chose a l'operateur -- il n'y a
        # pas d'explorateur ici -- et aucune ne doit remonter.
        return sans_ouvreur.format(commande=commande[0], chemin=chemin)
    if (systeme not in SYSTEMES_SANS_CODE_RETOUR_FIABLE
            and getattr(issue, "returncode", 0)):
        return sans_ouvreur.format(commande=commande[0], chemin=chemin)
    return fait.format(chemin=chemin)


class EcranResultat(ObjetTravaille, Palier):
    """`E2-5` -- les chiffres REELS, plus aucun majorant, et des suites CHOISIES.

    **Les suites sont navigables, pas decoratives** (Egan, 2026-08-28 : « il
    faudra les cabler vers l'ecran generique qui dit que l'ecran n'existe pas
    tout en laissant l'interaction possible »). Elles etaient rendues comme des
    lignes prefixees d'un glyphe de rattachement, donc l'operateur voyait
    « Composer les planches de ces lots » et rien ne repondait -- ce qu'il a lu
    comme deux invites cassees, et il avait raison de le lire ainsi.

    Une suite dont l'atelier n'existe pas encore mene a
    :class:`~mixed_media_utility.tui.coque.EcranPasEncore`, qui la nomme et dit
    quand elle arrive. C'est ce qui distingue « pas encore construit » de
    « casse », et c'est le seul etat dans lequel une interface a moitie batie
    peut etre jugee.
    """

    titre = "Resultat"
    #: **La ligne HORS journal.** L'ecran la remplace par
    #: :data:`RACCOURCIS_RESULTAT_AVEC_JOURNAL` des qu'un journal lui est
    #: passe : « elle ne montre que ce qui marche sur l'ecran courant »
    #: (`DESIGN.md` section 4).
    raccourcis = RACCOURCIS_RESULTAT

    #: Le titre du filet qui ouvre le journal deplie, comme `E2-4` le porte.
    TITRE_DU_JOURNAL = "Journal"

    #: La suite qui ramene au menu des ateliers. Ajoutee d'office **en
    #: dernier** si l'appelant ne l'a pas mise : `EPIC11-ARB-13` veut qu'on
    #: enchaine dans le meme projet, et un ecran de resultat sans chemin de
    #: retour serait un cul-de-sac -- le defaut que la couche 3 a trouve sur
    #: l'ecran d'interruption.
    RETOUR = "Retour aux ateliers"

    #: Un passage : le compte rendu d'un travail fini.
    TRANSITOIRE = True

    def __init__(self, panneau: Panneau, suites: list[str] | None = None,
                 sur_suite: Callable[[str], None] | None = None,
                 journal: Journal | None = None, objet: str = "") -> None:
        super().__init__()
        self.panneau = panneau
        #: La droite du bandeau, **donnee par l'atelier**. Voir
        #: `coque.ObjetTravaille`.
        self.objet = objet
        #: Le journal de l'execution qui vient de finir, ou ``None``.
        #:
        #: **Il manquait, et c'est le troisieme volet du finding `I8`** : la
        #: maquette `E2-5` annonce `Tab journal` depuis toujours, et
        #: `EcranResultat.on_key` ne traitait pas `tab` du tout (mesure du lot
        #: `G` : `down`, `up`, `enter`, `escape`, et rien d'autre). Le journal
        #: d'une extraction terminee n'etait donc relisible **de nulle part** :
        #: l'ecran `E2-4` qui le portait est depile au moment ou `E2-5` monte.
        #: La promesse est tenue plutot que retiree -- c'est la seule des deux
        #: branches qui rende quelque chose a l'operateur.
        self.journal = journal
        #: Vrai quand le journal est deplie. Il ne l'est jamais au montage : le
        #: compte rendu chiffre est ce qu'on vient lire, le journal est ce
        #: qu'on va chercher.
        self.journal_deplie = False
        if journal is not None:
            self.raccourcis = RACCOURCIS_RESULTAT_AVEC_JOURNAL
        suites = list(suites or [])
        if self.RETOUR not in suites:
            suites.append(self.RETOUR)
        self.suites = suites
        self.curseur = 0
        #: Ce que l'atelier fait d'une suite choisie. Absent, toute suite autre
        #: que le retour mene a l'ecran « pas encore » -- le comportement juste
        #: tant qu'aucun atelier n'existe.
        self._sur_suite = sur_suite
        if panneau.porte_un_majorant:
            raise ValueError(
                "Un ecran de resultat ne porte aucun majorant : le travail est "
                "fait, les chiffres sont mesures (story 11.1, AC 8.2)."
            )

    def lignes(self) -> list[str]:
        """Les chiffres, une ligne vide, puis les suites avec leur curseur."""
        ascii_seul = getattr(self.app, "ascii_seul", False)
        table = jetons.glyphes(ascii_seul)
        # **Le mode traverse jusqu'au panneau.** Sans lui, `Panneau.rendu`
        # abrege avec `…` (une colonne) ce que `bloc_peint` replie ensuite en
        # `...` (trois) : la ligne sort a deux colonnes de trop et se fait
        # couper par la fin, c'est-a-dire sur le chiffre.
        lignes = self.cartouche()
        lignes.append("")
        for rang, suite in enumerate(self.suites):
            curseur = table["curseur"] if rang == self.curseur else " "
            lignes.append(f"  {curseur} {suite}")
        lignes.extend(self.lignes_du_journal())
        return lignes

    def cartouche(self) -> list[str]:
        """Le compte rendu chiffre, **fenetre quand le journal est deplie**.

        **Le defaut que cette methode ferme, et il a ete mesure** (finding
        `C2-1`, revue de la calibration du 2026-09-06) : au plancher 80x24, le
        cartouche d'une passe de calibration occupe **17 des 17 lignes** de la
        zone centrale. `lignes_de_journal_visibles` rendait donc zero, et
        `Tab journal` -- annonce dans le pied depuis le montage -- ne montrait
        rien du tout. Le journal n'apparaissait qu'a partir de **28 lignes de
        terminal**, c'est-a-dire jamais sur le format que le depot tient pour
        plancher. Une touche annoncee qui ne fait rien visiblement se lit comme
        une panne : c'est `EPIC11-ARB-58`, que le docstring de
        :meth:`basculer_le_journal` invoque lui-meme quatre lignes plus bas.

        La sortie est celle qu'`EcranExecution` a deja tranchee pour la meme
        zone et le meme plancher : « deplie, le journal prend la place de la
        liste ». Ici il prend la place de la **queue** du cartouche, et
        l'abregement se DIT -- une ligne de points, comme partout ailleurs
        dans le depot --, sans quoi l'operateur lirait un compte rendu tronque
        en le croyant complet.

        Replie, rien ne change : le cartouche sort entier, et les trois ecrans
        qui avaient la place ne perdent rien.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        entier = self.panneau.rendu(self.app.size.width, ascii_seul)
        if not self.journal_deplie or self.journal is None:
            return entier
        place = self.lignes_de_cartouche_visibles()
        if len(entier) <= place:
            return entier
        # Une ligne est reprise par les points eux-memes.
        garde = max(place - 1, 0)
        return entier[:garde] + [jetons.points_d_abregement(ascii_seul)]

    def lignes_de_cartouche_visibles(self) -> int:
        """Ce que le cartouche garde quand le journal reclame son minimum.

        Le partage est **asymetrique et c'est delibere** : le journal ne prend
        que ce qui lui manque pour atteindre :data:`LIGNES_MINIMALES_DU_JOURNAL`,
        jamais plus. Un ecran qui avait deja la place -- et il y en a trois --
        rend exactement ce qu'il rendait avant.
        """
        hauteur_centre = jetons.hauteur_centrale(self.app.size.height)
        # 1 ligne vide entre le cartouche et les suites, puis les suites ;
        # 3 lignes pour la respiration, le filet et la ligne vide qui suit.
        autour = 1 + len(self.suites) + 3
        return max(hauteur_centre - autour - LIGNES_MINIMALES_DU_JOURNAL, 0)

    def lignes_du_journal(self) -> list[str]:
        """Le journal deplie, sous un filet, comme `E2-4` le montre.

        Vide tant que `Tab` n'a pas ete presse, et vide quand aucun journal
        n'a ete passe : les suites restent alors exactement ou elles etaient,
        donc `rang_du_curseur` n'a pas a en tenir compte.

        Le nombre de lignes est **derive de la hauteur courante**, comme sur
        `E2-4` : au-dela de 24 lignes, la place gagnee va a la zone centrale
        (`DESIGN.md` section 1). Le calculer sur le plancher reviendrait a
        ignorer un terminal plein ecran.
        """
        if not self.journal_deplie or self.journal is None:
            return []
        ascii_seul = getattr(self.app, "ascii_seul", False)
        combien = self.lignes_de_journal_visibles()
        if combien <= 0:
            return []
        trait = "-" if ascii_seul else "─"
        filet = f"{trait * 2} {self.TITRE_DU_JOURNAL} "
        filet += trait * max(
            jetons.largeur_utile(self.app.size.width) - jetons.colonnes(filet),
            0)
        return ["", filet, ""] + [f"  {ligne}"
                                  for ligne in self.journal.dernieres(combien)]

    def lignes_de_journal_visibles(self) -> int:
        """Ce qui reste de hauteur une fois le compte rendu et ses suites poses.

        Le calcul est celui d'`EcranExecution.lignes_de_journal_visibles`, a
        ceci pres que la place deja prise est **mesuree** sur les lignes qu'on
        vient de composer plutot que supposee : ici le cartouche n'a pas une
        hauteur fixe, il depend du nombre de lots ecrits.
        """
        hauteur_centre = jetons.hauteur_centrale(self.app.size.height)
        # **La place prise se mesure sur le cartouche AFFICHE**, qui peut etre
        # fenetre (voir :meth:`cartouche`). La mesurer sur le cartouche entier
        # rendait zero exactement dans le cas ou le fenetrage existe : les deux
        # se seraient annules.
        deja = len(self.cartouche()) + 1 + len(self.suites)
        # 3 lignes pour la respiration, le filet et la ligne vide qui suit.
        return max(hauteur_centre - deja - 3, 0)

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="resultat")
        return [self._corps]

    def on_mount(self) -> None:
        self.rafraichir()

    def rafraichir(self) -> None:
        self._corps.update(bloc_peint(
            self.lignes(), jetons.largeur_utile(self.app.size.width),
            self.app, rang=self.rang_du_curseur()))
        super().rafraichir()

    def rang_du_curseur(self) -> int | None:
        """Le rang, dans :meth:`lignes`, de la suite sous le curseur.

        **Passe explicitement**, parce que les suites sont indentees de deux
        espaces : la detection automatique de `peindre` teste `startswith` et ne
        les trouverait pas. Elle ne planterait pas -- elle ne colorerait rien.
        """
        if not self.suites:
            return None
        # **Le cartouche AFFICHE, jamais l'entier** : quand le journal le
        # fenetre, un rang calcule sur l'entier peindrait le curseur plusieurs
        # lignes sous la suite qu'il designe -- ou hors du bloc.
        return len(self.cartouche()) + 1 + self.curseur

    def basculer_le_journal(self) -> bool:
        """`Tab` : deplier ou replier le journal. Rend faux s'il n'y en a pas.

        **Rendre faux plutot que basculer a vide est le point** : une touche
        annoncee qui ne fait rien visiblement se lit comme une panne
        (`EPIC11-ARB-58`, meme motif). L'ecran n'annonce donc `Tab journal` que
        quand un journal existe, et ne le consomme que dans ce cas.
        """
        if self.journal is None:
            return False
        self.journal_deplie = not self.journal_deplie
        self.rafraichir()
        return True

    def on_key(self, evenement) -> None:
        """`↑↓` deplace, `⏎` choisit, `Tab` deplie le journal, `Échap` sort.

        `Échap` est traite **ici** et mene aux ateliers plutot que de depiler
        d'un cran : un ecran de resultat est empile par-dessus l'execution, donc
        une remontee ordinaire ramenerait l'operateur sur la tache qu'il vient
        de finir (`EPIC11-ARB-13`).
        """
        if evenement.key == "tab":
            if self.basculer_le_journal():
                evenement.stop()
            return
        if evenement.key == "down":
            evenement.stop()
            self.curseur = min(self.curseur + 1, len(self.suites) - 1)
            self.rafraichir()
        elif evenement.key == "up":
            evenement.stop()
            self.curseur = max(self.curseur - 1, 0)
            self.rafraichir()
        elif evenement.key == "enter":
            evenement.stop()
            self.choisir()
        elif evenement.key == "escape":
            evenement.stop()
            self.app.revenir_aux_ateliers()

    def choisir(self) -> str:
        """Declenche la suite sous le curseur, et rend son libelle."""
        suite = self.suites[self.curseur]
        if suite == self.RETOUR:
            self.app.revenir_aux_ateliers()
        elif self._sur_suite is not None:
            self._sur_suite(suite)
        else:
            # Import tardif : `coque` ne connait pas `execution`, et l'inverse
            # ne vaut qu'au moment de l'appel.
            from .coque import EcranPasEncore
            self.app.descendre(EcranPasEncore(
                suite, self.app.QUAND_ARRIVENT_LES_ATELIERS))
        return suite


class EcranInterruption(EcranChiffre):
    """`E2-4b` -- on dit ce qu'on laisse, et ouvrir cet ecran n'arrete rien.

    L'ecran est **monte par-dessus** l'execution : la tache continue derriere
    lui. C'est ce que l'AC 4.2 mesure -- la progression avance encore pendant
    que l'ecran est a l'ecran.
    """

    titre = "Interruption"
    raccourcis = "↑↓ naviguer  ⏎ choisir  Échap reprendre"

    #: Cle de l'issue de navigation. Nommee, parce que l'ecran d'execution la
    #: traite lui-meme et qu'une chaine ecrite deux fois divergerait.
    REPRENDRE = "reprendre"

    #: Les trois issues, dans l'ordre ou l'operateur les pese : garder ce qui
    #: est ecrit est le cas le plus frequent, effacer le plus destructeur,
    #: reprendre le retour en arriere.
    ISSUES = (
        Issue("garder", "Interrompre et garder ce qui est deja ecrit"),
        Issue("effacer", "Interrompre et effacer ce qui est deja ecrit",
              ecrit=True),
        Issue(REPRENDRE, "Reprendre l'execution"),
    )

    def __init__(self, panneau: Panneau,
                 sur_issue: Callable[[Issue], None] | None = None) -> None:
        super().__init__(panneau, ChoixExclusif(list(self.ISSUES)),
                         sur_issue=sur_issue)

    def etat(self) -> str:
        if self._refus_annonce is not None:
            return self._refus_annonce
        return "L'execution continue tant qu'aucune issue n'est validee."

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """`Echap` reprend l'execution -- il ne remonte pas, il ne quitte pas.

        C'est la sortie que la maquette `T6-1` annonce en toutes lettres
        (« Echap reprendre l'ecriture ») et qui n'existait pas : hors edition,
        `escape` remontait a l'application, qui voyait une tache en cours et ne
        depilait donc pas. L'ecran n'avait aucune sortie clavier.
        """
        if touche == "escape":
            # **Viser puis valider**, jamais `retenir` puis `valider` : depuis
            # `EPIC11-ARB-45` la validation suit le CURSEUR, et une retenue
            # nommee sans deplacement du curseur serait ecrasee -- `Echap`
            # aurait alors declenche l'issue survolee au lieu de la reprise.
            self.choix.viser(self.REPRENDRE)
            return self.valider()
        return super().traiter(touche, caractere)


# ===========================================================================
# La passe et ses lots -- le modele que TROIS ecrans d'execution partagent
# ===========================================================================
#
# **Ce modele n'est pas invente ici : il est HISSE.** `atelier_pdf_execution`
# le portait deja en entier (`LotEnGeneration`, `PasseDeGeneration`), et le
# docstring de `EcranGenerationDesPlanches.sur_jalon` nommait d'avance la ligne
# que ce hissage change -- « c'est la seule ligne de ce module que
# `EPIC11-ARB-134` point 2 touchera [...] quand la remise a zero tombera,
# `faites` deviendra le compte de la passe ». L'AC 8.6 de la 11.4e demande le
# comptage a ZERO d'une seconde implementation de la liste des lots dans
# `tui/` : le PDF etant le premier en date, c'est lui qui delegue, et rien
# n'est re-redige de son cote.

#: Les trois etats d'un lot d'une passe. L'ensemble est **ferme** : un
#: quatrieme etat serait un etat que la maquette ne montre pas, et un ecran
#: d'execution n'a que trois choses a dire d'un lot -- il est fait, il se fait,
#: il attend. Verbatim des maquettes `E2-4` (l. 6-7), `E3-7` (l. 6-7) et `E5-4`
#: (l. 6-7) pour les deux qu'elles montrent ; `en attente` ne figure sur aucune
#: des trois -- une passe a deux lots dont l'un ecrit et l'autre en cours ne
#: pouvait pas le montrer -- et il n'est pas invente pour autant : il est ce que
#: `EPIC11-ARB-134` point 3 appelle « ce qui reste en attente ».
MENTION_ECRIT = "écrit"
MENTION_EN_COURS = "en cours"
MENTION_EN_ATTENTE = "en attente"

#: Les mentions dans l'ordre des etats, pour deriver la largeur de leur colonne
#: **du jeu complet** plutot que de ce qui est affiche a cet instant. Une
#: colonne calee sur les seules mentions presentes bougerait d'un rafraichi a
#: l'autre, au moment precis ou un lot change d'etat.
MENTIONS_DES_LOTS = (MENTION_ECRIT, MENTION_EN_COURS, MENTION_EN_ATTENTE)

#: L'etat de peinture d'un lot **ecrit**. Le lot en cours et ceux en attente
#: n'en portent aucun : les maquettes ne posent de marque que sur ce qui est
#: fait.
ETAT_DU_LOT_ECRIT = "complete"

#: L'indentation d'une ligne de lot et d'une ligne de journal, **mesuree** sur
#: les trois maquettes : le nom d'un lot ouvre a la colonne 5 de la zone utile
#: (`E2-4` l. 6, `E3-7` l. 6), et le journal s'y aligne (l. 11). Une seule
#: constante, parce que les maquettes les alignent.
INDENT_DES_LIGNES = " " * 5

#: Le titre d'un ecran d'execution, verbatim des trois maquettes :
#: `Extraction en cours — lot 2 sur 2` (`E2-4` l. 5),
#: `Écriture des TIFF — lot 1 sur 2` (`E3-7` l. 5),
#: `Génération en cours — lot 2 sur 2` (`E5-4` l. 5).
#:
#: **Le libelle vient de l'atelier, le compte vient de l'ecran** (`Q-I-3`,
#: tranche le 2026-09-05). Les trois maquettes ne partagent pas leur verbe --
#: deux disent « en cours », la troisieme nomme ce qu'elle ecrit --, donc
#: composer le verbe ici serait le deviner ; et remplacer le titre de l'atelier
#: serait lui prendre ce qui lui appartient. L'atelier declare son libelle avec
#: ses lots, l'ecran y ajoute le rang.
TITRE_DE_LA_PASSE = "{libelle} — lot {rang} sur {total}"


def mention_du_lot(rang: int, rang_courant: int) -> str:
    """L'etat du lot de `rang` : ecrit, en cours, ou en attente.

    La comparaison porte sur le rang du lot courant, dans les **deux** sens :
    ce qui precede est ecrit, ce qui suit attend. Une comparaison d'un seul
    cote rendrait « en attente » pour tout ce qui n'est pas le lot courant, y
    compris ce qui est deja sur le disque.
    """
    if rang < rang_courant:
        return MENTION_ECRIT
    if rang == rang_courant:
        return MENTION_EN_COURS
    return MENTION_EN_ATTENTE


def largeur_des_mentions(ascii_seul: bool = False) -> int:
    """La largeur de la colonne des mentions, **du jeu complet des trois**.

    Elle se mesure en colonnes et non en caracteres, et sur les mentions
    **repliees** quand `--ascii` est demande : `replier_ascii` peut changer la
    largeur d'un texte accentue, et une colonne calculee sur le texte non
    replie deborderait alors du seul cote ASCII -- le regime exact ou le lot J
    de la 11.7 a mesure une mutilation silencieuse.
    """
    return max(jetons.colonnes(jetons.replier_ascii(texte) if ascii_seul
                               else texte)
               for texte in MENTIONS_DES_LOTS)


def ligne_du_lot(nom: str, mention: str, utile: int,
                 ascii_seul: bool = False, compte: str = "",
                 glyphe: str = "") -> str:
    """`     projet_demo_rush_01_25fps                    écrit`.

    **L'unique redaction d'une ligne de lot dans `tui/`** (AC 8.6). Les trois
    ecrans d'execution l'appellent, chacun avec ce que sa maquette montre :
    `E5-4` pose un glyphe et un compte de pages, `E2-4` et `E3-7` n'en posent
    aucun.

    **Le budget de colonnes, RECALCULE et non repris d'un commentaire** -- le
    lot J de la 11.7 a mesure que cinq des neuf commentaires de budget poses a
    la main dans ce paquet etaient faux. Au plancher, `utile` vaut 76 :

    ==========================  =======================================
    ce qui est pose             colonnes
    ==========================  =======================================
    indentation                 5
    glyphe et son espace        0 (`E2-4`, `E3-7`) ou 2 (`E5-4`)
    nom                         le reste, soit 57 sans glyphe
    creux minimal               2
    compte                      0 (`E2-4`, `E3-7`)
    creux minimal               2
    colonne des mentions        10 (`en attente`, la plus large des trois)
    ==========================  =======================================

    5 + 57 + 2 + 2 + 10 = 76 **exactement**. La ligne la plus longue tient donc
    a la colonne pres, et c'est voulu : la mesure du budget est ce qui garantit
    que la ligne ne passe **jamais** sous l'abreviateur. Une ligne qui y
    passerait serait tronquee sans un mot -- et dans le seul regime ASCII, ou
    aucune capture couleur ne la montre.
    """
    if ascii_seul:
        mention = jetons.replier_ascii(mention)
    largeur_mention = largeur_des_mentions(ascii_seul)
    tete = INDENT_DES_LIGNES + (f"{glyphe} " if glyphe else "")
    # Le budget du nom : ce qui reste une fois la tete, le compte, la colonne
    # des mentions et les deux creux poses. Mesure en COLONNES, jamais en
    # caracteres -- un nom de projet en ideogrammes tiendrait deux fois la
    # place que `len` lui donne.
    place = max(utile - jetons.colonnes(tete) - jetons.colonnes(compte)
                - largeur_mention - 2 * jetons.CREUX_MINIMAL, 0)
    nom = jetons.abreger_chemin(nom, place, ascii_seul)
    gauche = tete + nom
    droite = utile - largeur_mention - jetons.CREUX_MINIMAL
    creux = droite - jetons.colonnes(gauche) - jetons.colonnes(compte)
    return (gauche + " " * max(creux, jetons.CREUX_MINIMAL) + compte
            + " " * jetons.CREUX_MINIMAL + mention)


@dataclass(frozen=True)
class LotDeLaPasse:
    """Un lot de la passe, tel qu'un ecran d'execution le montre.

    `cardinal` est ce que le lot compte -- des frames, des pages. Il vaut
    `None` tant qu'il n'est pas **mesure** : un lot dont le cardinal n'est pas
    connu ne rend ni `0` ni `--`, il ne rend rien (`DESIGN.md` section 3), et
    c'est cette absence -- et rien d'autre -- qui rend le total de la passe
    inconnu.
    """

    nom: str
    cardinal: int | None = None


@dataclass
class PasseEnCours:
    """L'etat de la passe entiere a un instant : ses lots, et ou l'on en est.

    **L'agregation porte sur la passe, pas sur le lot** (`EPIC11-ARB-134`
    point 2, AC 8.1 de la 11.4e). C'est ce modele qui la tient, parce que c'est
    lui qui connait la liste des lots -- le socle d'execution n'a jamais qu'un
    couple `(faites, total)` a la fois, et un couple ne sait pas ce qu'il y a
    autour.
    """

    #: Le verbe de la passe, **donne par l'atelier** : « Extraction en cours »,
    #: « Écriture des TIFF ». Voir :data:`TITRE_DE_LA_PASSE`.
    libelle: str
    lots: tuple[LotDeLaPasse, ...]
    #: Le rang, 0-fonde, du lot en cours.
    rang_du_lot_courant: int = 0
    #: Ce qui est fait **du lot courant**. C'est le seul champ que le canal du
    #: coeur alimente ; tout le reste se derive.
    faites_du_lot_courant: int = 0
    #: Combien de lots ont ete **commences**. Il n'est pas redondant avec le
    #: rang : c'est lui qui fait avancer le rang a chaque `emetteur()`, et le
    #: rang seul ne saurait pas distinguer « le premier lot commence » de
    #: « aucun lot commence ».
    _commences: int = 0

    def __post_init__(self) -> None:
        if not self.lots:
            raise ValueError(
                "Une passe porte au moins un lot : un ecran d'execution sans "
                "rien a executer n'a pas d'etat a montrer.")

    # -- les cardinaux -------------------------------------------------------

    @property
    def total_connu(self) -> bool:
        """Vrai quand **tous** les lots ont un cardinal mesure.

        « Tous », et non « celui-ci » : la barre agrege la passe entiere, donc
        un seul cardinal manquant suffit a rendre la somme inconnue.
        """
        return all(lot.cardinal is not None for lot in self.lots)

    @property
    def cardinal_de_la_passe(self) -> int:
        """La somme des cardinaux de **tous** les lots, ou `0` si inconnue.

        `0` est ce que `avancement.barre` et `avancement.pourcentage` traitent
        deja comme « le total ne veut rien dire » ; rendre autre chose
        obligerait chaque appelant a refaire la garde.
        """
        if not self.total_connu:
            return 0
        return sum(lot.cardinal or 0 for lot in self.lots)

    @property
    def faites_de_la_passe(self) -> int:
        """Ce qui est fait depuis le debut de la PASSE.

        Les lots **strictement avant** le lot courant, plus ce qui est fait du
        lot courant. Un `sum` sur toute la liste compterait les lots a venir ;
        un `sum` qui inclurait le lot courant le compterait deux fois.
        """
        deja = sum(lot.cardinal or 0
                   for lot in self.lots[:self.rang_du_lot_courant])
        return deja + self.faites_du_lot_courant

    @property
    def lot_courant(self) -> LotDeLaPasse:
        return self.lots[self.rang_du_lot_courant]

    # -- l'avancee d'un lot au suivant ---------------------------------------

    def mesurer_le_lot_courant(self, cardinal: int) -> None:
        """Poser le cardinal MESURE du lot courant, par-dessus le declare.

        Le plan annonce un cardinal, le coeur en mesure un. Quand les deux
        different, c'est le mesure qui vaut : un total de passe compose de
        promesses ferait diverger la barre du compte des jalons, et l'ecart ne
        se verrait qu'a la fin.
        """
        rang = self.rang_du_lot_courant
        if self.lots[rang].cardinal == cardinal:
            return
        self.lots = (self.lots[:rang]
                     + (replace(self.lots[rang], cardinal=cardinal),)
                     + self.lots[rang + 1:])

    def commencer_le_lot_suivant(self, cardinal: int) -> None:
        """Le lot suivant commence : le rang avance, le compte ne recule pas.

        **Le premier appel ouvre le lot 0**, pas le lot 1 : c'est le compte des
        lots commences qui donne le rang, et il vaut zero avant le premier
        appel. Un `rang += 1` inconditionnel sauterait le premier lot -- et le
        rendrait `écrit` alors qu'il est en cours.

        Le rang est **borne a la queue** : un atelier qui appellerait plus
        souvent que sa passe ne compte de lots ecrirait sinon hors de la liste.
        Deborder par la queue est le mode de panne d'une agregation, et il vaut
        mieux le borner que le laisser lever au milieu d'une passe.
        """
        self.rang_du_lot_courant = min(self._commences, len(self.lots) - 1)
        self._commences += 1
        self.faites_du_lot_courant = 0
        self.mesurer_le_lot_courant(cardinal)

    # -- les etats -----------------------------------------------------------

    def mention_du_lot(self, rang: int) -> str:
        return mention_du_lot(rang, self.rang_du_lot_courant)

    def mentions_des_lots(self) -> list[str]:
        """Les mentions de tous les lots, dans l'ordre de la liste."""
        return [self.mention_du_lot(rang) for rang in range(len(self.lots))]

    # -- le rendu ------------------------------------------------------------

    def titre(self) -> str:
        """`Extraction en cours — lot 2 sur 3`. Le rang est rendu 1-fonde.

        **La conversion `+ 1` vit ici et non dans `en_tete_de_lot`**, malgre ce
        que l'AC 8.4 annonce. La mesure la contredit : `en_tete_de_lot` habite
        `atelier_extraction_ecriture`, qui importe ce module -- l'y appeler
        ferait un cycle d'import --, et il rend `-- lot 2/3 : lot_id`, une
        autre ligne pour un autre endroit. `PasseDeGeneration.titre` faisait
        deja son `+ 1` chez elle, pour la meme raison.
        """
        return TITRE_DE_LA_PASSE.format(libelle=self.libelle,
                                        rang=self.rang_du_lot_courant + 1,
                                        total=len(self.lots))

    def ligne_du_lot(self, rang: int, utile: int,
                     ascii_seul: bool = False) -> str:
        return ligne_du_lot(self.lots[rang].nom, self.mention_du_lot(rang),
                            utile, ascii_seul)

    def lignes_des_lots(self, utile: int,
                        ascii_seul: bool = False) -> list[str]:
        return [self.ligne_du_lot(rang, utile, ascii_seul)
                for rang in range(len(self.lots))]


class SurfaceExecution:
    """Le branchement du canal de progression du coeur sur un ecran.

    Elle n'est pas un widget : c'est le **cablage**, isole pour etre mesurable
    sans monter d'application. L'ecran d'execution la possede ; les ateliers la
    reutilisent telle quelle.
    """

    def __init__(self, unite: str, horloge=None,
                 sur_jalon: Callable[[Avancement], None] | None = None) -> None:
        self.avancement = Avancement(unite=unite)
        self.journal = Journal()
        self.estimateur = EstimateurTempsRestant(horloge=horloge)
        #: Les observateurs a prevenir a chaque jalon. Une **liste**, et non un
        #: rappel unique : l'ecran d'execution s'y inscrit a son montage, et un
        #: atelier qui voudrait en plus journaliser ailleurs ne doit pas avoir a
        #: choisir entre les deux.
        self._observateurs: list[Callable[[Avancement], None]] = []
        if sur_jalon is not None:
            self._observateurs.append(sur_jalon)
        #: La passe declaree par l'atelier, ou `None`. **Tant qu'elle est
        #: absente, cette surface se comporte exactement comme avant l'AC 8**
        #: -- un lot, un compte, une remise a zero -- et l'ecran ne montre ni
        #: liste ni rang. Ce n'est pas une prudence : une passe non declaree
        #: est une passe dont on ne connait NI le nombre de lots NI la somme
        #: de leurs cardinaux, et « lot 2 sur 2 » affiche au deuxieme lot d'une
        #: passe qui en compte trois serait une ligne fausse. Un champ non
        #: mesure est omis, jamais rendu faux (`DESIGN.md` section 3).
        self.passe: PasseEnCours | None = None

    def declarer_la_passe(self, libelle: str, lots) -> None:
        """Declarer la passe entiere AVANT son premier lot (AC 8.1).

        `lots` est une suite de :class:`LotDeLaPasse`, ou de couples
        `(nom, cardinal)`. Le libelle est le verbe de l'atelier -- voir
        :data:`TITRE_DE_LA_PASSE`.

        **C'est l'unique porte par laquelle le plan entre dans la surface**, et
        elle existe parce que le canal du coeur ne la porte pas : `emetteur()`
        ne recoit qu'un cardinal a la fois, et un cardinal ne dit ni combien de
        lots suivent ni comment ils s'appellent. Sans cette declaration, le
        total ne pourrait que **grossir** de lot en lot -- « 26/26, 100 % » a la
        fin du premier lot d'une passe qui en compte trois --, ce qui est
        precisement la ligne fausse que `DESIGN.md` section 3 interdit.

        **Declarer une seconde fois ouvre une passe SUIVANTE**, et c'est le
        regime que l'AC 8.2 distingue du lot suivant : ici tout est remis a
        zero, le compte comme l'estimateur ; entre deux lots d'une meme passe,
        le compte, lui, continue. Le journal ne l'est dans **aucun** des deux
        (`EPIC11-ARB-93`) : c'est l'en-tete qui nomme le lot qui rend la
        rupture lisible.
        """
        self.passe = PasseEnCours(
            libelle=libelle,
            lots=tuple(lot if isinstance(lot, LotDeLaPasse)
                       else LotDeLaPasse(*lot) for lot in lots))
        self.avancement.total = self.passe.cardinal_de_la_passe
        self.avancement.faites = 0
        self.avancement.temps_restant = None
        self.avancement.detail = None
        self.estimateur.reinitialiser()

    def abonner(self, rappel: Callable[[Avancement], None]) -> None:
        """Inscrire un observateur des jalons.

        **C'est le cablage qui manquait.** Le rappel existait, `noter()`
        l'appelait, et personne ne le fournissait : l'ecran d'execution
        dessinait sa ligne d'etat une fois au montage puis plus jamais, donc
        affichait `0 %  0/6300 frames` du debut a la fin d'une extraction. Deux
        cotes corrects, aucun test capable de constater l'appel manquant entre
        eux -- exactement le defaut de couture que le docstring de ce module dit
        vouloir eviter (revue de vague 1, couche 1).
        """
        if rappel not in self._observateurs:
            self._observateurs.append(rappel)

    def desabonner(self, rappel: Callable[[Avancement], None]) -> None:
        """Retirer un observateur. Retirer un absent ne leve pas."""
        if rappel in self._observateurs:
            self._observateurs.remove(rappel)

    def emetteur(self, total: int) -> EmetteurProgression:
        """Fabrique l'emetteur que la tache du coeur recevra.

        **Tout ce qui appartient a la tache precedente est efface** -- le
        compte, `temps_restant` et l'estimateur. Motif d'origine : un
        `temps_restant` herite affichait « reste ~ 3 min 14 s » alors que
        l'estimateur du coeur rendait `None`, ce qui est l'interdit
        d'`EPIC7-ARB-67` mot pour mot.

        **Le journal, lui, N'EST PLUS remis a zero** (`EPIC11-ARB-93`, Egan,
        2026-08-30), et ce renversement d'une decision de revue merite son
        motif. Cette methode faisait `self.journal = Journal()` -- elle
        **rebindait** --, et `canal_de_progression` l'appelle **une fois par
        lot**. Or le journal est devenu, a la vague 3, la destination du **log
        du coeur** : le relais (`RelaisDeJournal`) n'est vise qu'**une seule
        fois**, au montage de `E2-4`, si bien qu'il continuait d'ecrire dans un
        objet que plus rien n'affichait des le second lot.

        Mesure du parcours `H3`, sur une extraction reelle de deux lots : les
        **58** lignes emises par le coeur -- relevé `ffprobe`, borne
        d'occupation disque, mise a jour du manifest, et un AVERTISSEMENT
        `[NON_INTEGER_TARGET_RATE]` -- etaient injoignables, et `E2-5`
        n'affichait que les deux derniers jalons du dernier lot.

        **L'objection d'origine ne tombe pas d'elle-meme, elle est fermee
        ailleurs** : « un journal herite montre les jalons de la tache d'avant,
        donc un compte qui recule » etait vrai. C'est
        :func:`~mixed_media_utility.tui.atelier_extraction_ecriture.executer_le_plan`
        qui la ferme, en inscrivant au debut de chaque lot une ligne qui le
        NOMME -- `1/13` precede de « lot 2/2 : ... » ne recule pas, il change
        de lot.
        """
        if self.passe is None:
            self.avancement.total = total
            self.avancement.faites = 0
        else:
            # **Le compte NE REVIENT PAS a zero d'un lot au suivant** (AC 8.1).
            # C'est ici que la remise a zero tombe, et c'est la seule ligne du
            # depot que `EcranGenerationDesPlanches.sur_jalon` annoncait :
            # « quand la remise a zero tombera, `faites` deviendra le compte de
            # la passe ». Le mutant naturel de cette AC est de la remettre.
            self.passe.commencer_le_lot_suivant(total)
            self.avancement.total = self.passe.cardinal_de_la_passe
            self.avancement.faites = self.passe.faites_de_la_passe
        # `temps_restant` et l'estimateur, eux, restent effaces a **chaque**
        # lot : un `temps_restant` herite affichait « reste ~ 3 min 14 s » alors
        # que l'estimateur du coeur rendait `None`, ce qui est l'interdit
        # d'`EPIC7-ARB-67` mot pour mot. L'agregation porte sur le compte, pas
        # sur la vitesse -- deux lots de cadences differentes n'ont pas la meme.
        self.avancement.temps_restant = None
        self.avancement.detail = None
        self.estimateur.reinitialiser()
        return EmetteurProgression(self.noter, total)

    def noter(self, faites: int, total: int) -> None:
        """Le rappel branche sur le coeur. Il **lit** l'estimateur, il ne calcule pas."""
        self.estimateur.noter(faites, total)
        if self.passe is None:
            self.avancement.faites = faites
            self.avancement.total = total
        else:
            self.passe.faites_du_lot_courant = faites
            self.passe.mesurer_le_lot_courant(total)
            self.avancement.faites = self.passe.faites_de_la_passe
            self.avancement.total = self.passe.cardinal_de_la_passe
        self.avancement.temps_restant = self.estimateur.temps_restant
        self.journal.inscrire(f"{faites}/{total} {self.avancement.unite}")
        for observateur in list(self._observateurs):
            observateur(self.avancement)

    def executer(self, tache: Callable[[EmetteurProgression], object],
                 total: int):
        """Lance la tache **en processus**, avec son emetteur.

        Les erreurs de la tache **traversent** : c'est l'interdit symetrique
        d'`EPIC7-ARB-79`. Seules les defaillances du canal sont absorbees, et
        elles le sont par `EmetteurProgression`, pas ici.
        """
        return tache(self.emetteur(total))


class EcranExecution(ObjetTravaille, Palier):
    """`E2-4` -- la barre, le journal, et `Echap` qui n'est plus une remontee."""

    titre = "Execution"
    #: **UN littéral pour QUATRE ecrans** : `EcranDetectionEnCours` (`E3-2`),
    #: `EcranEcritureDuScan` (`E3-7`) et l'ecran de la passe de `calibrate` ne
    #: redefinissent pas cette ligne, ils en **heritent**. C'est mesure par
    #: identite (`is`) dans `test_arb140_passages_sans_q_quitter.py`, pas
    #: suppose.
    #:
    #: **`Q quitter` -> `F1 aide` (`EPIC11-ARB-140`, 2026-09-02).** Les sept
    #: maquettes d'execution du depot sont unanimes sur `F1 aide` et aucune ne
    #: porte `Q quitter`. Le retrait ferme au passage une **promesse sans
    #: observable** : sur un ecran d'execution, `q` ne quittait pas -- il posait
    #: `app.confirmation_de_sortie_demandee`, un drapeau qu'**aucun module de
    #: `src/` ne lit** (le docstring d'`oublier_la_tache` le dit lui-meme).
    #: Annoncer la touche etait donc le defaut `I8` par l'autre bout.
    #:
    #: **L'ecart avec les maquettes est FERME** (`EPIC11-ARB-246`, Egan le
    #: 2026-09-06, par invite, verbatim : « Tab journal partout »). Cette place
    #: portait « ce qui n'est PAS corrige ici » : les quatre maquettes
    #: d'execution dessinaient `Tab journal complet` la ou ce littéral rend
    #: `Tab journal`. Ce sont les **maquettes** qui se sont alignees -- `E2-4`,
    #: `E3-2`, `E3-7` et `E5-4`, corrigees a la source dans leurs generateurs --
    #: et `atelier_pdf_execution.RACCOURCIS_GENERATION`, seul site du code a
    #: porter la forme longue, a perdu son mot. L'epingle n'est pas retiree,
    #: elle est **retournee** : le jeton est desormais UNIQUE dans le produit,
    #: et `test_vocabulaire_de_la_tui.py` le tient par une frontiere
    #: **negative** -- un grep de `Tab journal complet` dans `src/` et dans les
    #: maquettes doit rendre zero. Une frontiere supprimee ne rougirait plus
    #: jamais ; celle-ci rougit a la reintroduction.
    raccourcis = "Tab journal  Échap interrompre  F1 aide"

    #: Un passage : la duree d'une tache, pas une station.
    TRANSITOIRE = True

    def __init__(self, surface: SurfaceExecution, titre_tache: str = "",
                 sur_issue: Callable[[Issue], None] | None = None,
                 objet: str = "") -> None:
        super().__init__()
        self.surface = surface
        self.titre_tache = titre_tache
        #: La droite du bandeau, **donnee par l'atelier**. Voir
        #: `coque.ObjetTravaille`.
        self.objet = objet
        self.journal_deplie = False
        #: Ce que l'atelier fait des DEUX issues qui interrompent. « Reprendre »
        #: n'y va jamais : c'est de la navigation, elle appartient a la surface
        #: partagee et se traite ici.
        self._sur_issue = sur_issue

    #: Ce que le bloc de tete occupe **hors** liste des lots, et ce que la
    #: liste doit donc laisser libre : le titre (1), la respiration qui le
    #: separe des lots (1), la ligne vide qui separe le bloc du journal (1) et
    #: la respiration de bas de zone (1).
    #:
    #: **Recalcule, jamais repris d'un commentaire** (lot J de la 11.7 : cinq
    #: des neuf commentaires de budget du paquet etaient faux). Au plancher, la
    #: zone centrale vaut 17 lignes et le journal replie en prend 2 : la liste
    #: dispose donc de 17 - 4 - 2 = **11** lignes, ligne `…` comprise. Le total
    #: dessine vaut alors 1 + 1 + 11 + 1 + 2 + 1 = 17, la zone exactement.
    LIGNES_HORS_LOTS = 4

    def contenu(self) -> list[Widget]:
        utile = jetons.largeur_utile(self.app.size.width)
        lignes, _etats = self.lignes_de_l_entete(
            utile, self.app.ascii_seul, self.lignes_de_lots_visibles())
        self._entete = Static(bloc(lignes, utile, self.app.ascii_seul),
                              id="tache")
        self._journal = Static("", id="journal")
        return [self._entete, Static(""), self._journal]

    def lignes_de_lots_visibles(self) -> int:
        """Combien de lignes la liste des lots peut prendre, ligne `…` comprise.

        **Deplie, le journal prend la place de la liste** : c'est ce que
        `Tab journal` promet, et le seul moyen de tenir la promesse dans une
        zone centrale de 17 lignes. Le budget du journal, lui, ne bouge dans
        **aucun** des deux regimes -- une liste des lots qui rognerait le
        journal serait une regression sur les trois ecrans qui n'ont rien
        demande.
        """
        if self.journal_deplie:
            return 0
        return max(jetons.hauteur_centrale(self.app.size.height)
                   - self.LIGNES_HORS_LOTS
                   - self.lignes_de_journal_visibles(), 0)

    def lignes_de_l_entete(self, utile: int, ascii_seul: bool,
                           hauteur_des_lots: int
                           ) -> tuple[list[str], dict[int, str]]:
        """Le bloc de tete : le titre, et la liste des lots quand il y en a une.

        Rend aussi les etats de peinture, en rangs **relatifs au bloc** : seuls
        les lots ecrits en portent un, comme les maquettes ne posent de marque
        que sur ce qui est fait.

        **Sans passe declaree, rien ne change** : le titre de tache de
        l'atelier, seul, exactement comme avant l'AC 8. C'est le volet
        symetrique de la declaration -- un ecran qui inventerait un rang
        qu'aucun plan ne lui a donne dirait un chiffre faux.
        """
        passe = self.surface.passe
        if passe is None:
            return [self.titre_tache], {}
        lignes = [passe.titre()]
        etats: dict[int, str] = {}
        if hauteur_des_lots <= 0:
            return lignes, etats
        lignes.append("")
        total = len(passe.lots)
        # La fenetre se **derive** du lot courant a chaque dessin plutot que de
        # se retenir : cet ecran n'a pas de curseur qu'on deplace, il suit une
        # passe qui avance toute seule. Un `premier_visible` retenu serait un
        # etat de plus a remettre a zero entre deux passes.
        premier_visible = jetons.recadrer_la_fenetre(
            0, passe.rang_du_lot_courant, total, hauteur_des_lots)
        premier, dernier = jetons.fenetre_de_liste(
            total, premier_visible, hauteur_des_lots)
        if premier > 0:
            lignes.append(INDENT_DES_LIGNES
                          + jetons.points_d_abregement(ascii_seul))
        for absolu in range(premier, dernier + 1):
            if passe.mention_du_lot(absolu) == MENTION_ECRIT:
                etats[len(lignes)] = ETAT_DU_LOT_ECRIT
            lignes.append(passe.ligne_du_lot(absolu, utile, ascii_seul))
        if dernier < total - 1:
            lignes.append(INDENT_DES_LIGNES
                          + jetons.points_d_abregement(ascii_seul))
        return lignes, etats

    def on_mount(self) -> None:
        self.app.tache_en_cours = True
        # LE cablage : sans cette inscription, la ligne d'etat et le journal
        # sont dessines une fois au montage et plus jamais.
        self.surface.abonner(self.sur_jalon)
        self.rafraichir()

    def on_unmount(self) -> None:
        """Se desabonner : un ecran demonte qui recevrait encore des jalons
        ecrirait dans un arbre de widgets detruit."""
        self.surface.desabonner(self.sur_jalon)

    def sur_jalon(self, _avancement: Avancement) -> None:
        """Appele par le coeur a chaque jalon, et **repasse par la boucle**.

        **Le defaut que cette garde ferme, mesure le 2026-09-06.** Tant que les
        passes tournaient sur la boucle d'evenements, ce rappel y tournait
        aussi et `rafraichir` mutait l'arbre de widgets au bon endroit par
        accident de structure. Des qu'une passe part au fil de travail -- ce
        que `scan-calibrate` faisait deja et ce que les ateliers Scan puis PDF
        font depuis ce jour --, le coeur ecrit ses jalons DEPUIS LE FIL, et
        `rafraichir` mute alors l'arbre hors de la boucle. Mesure : trois
        jalons sur trois emis depuis un fil distinct de `App._thread_id`.

        `atelier_scan_parcours.lancer_la_passe_de_calibration` reglait le cas
        chez lui, par un `noter_le_jalon` qui rappelait `call_from_thread` --
        et son docstring notait deja que « le fil de travail n'appelle
        **jamais** un ecran directement ». La garde est ici plutot que chez
        chaque appelant pour une raison simple : un atelier qui partirait au
        fil demain **oublierait** de la reposer, et le defaut est invisible --
        `textual` ne signale rien, l'ecran se met a jour la plupart du temps,
        et ce qui casse casse au hasard.

        **Le cout est celui d'`EPIC7-ARB-79` et il est tenu** : le canal
        d'observation ne doit « ni faire echouer, ni ralentir notablement, ni
        modifier le travail qu'il observe ». Un aller-retour par jalon sur un
        chemin dont chaque jalon vaut une page decodee ne se mesure pas ; et
        appeler `call_from_thread` DEPUIS la boucle leverait, d'ou le test de
        fil plutot qu'un appel inconditionnel.
        """
        app = self.app
        if (getattr(app, "_loop", None) is not None
                and getattr(app, "_thread_id", None) != threading.get_ident()):
            app.call_from_thread(self.rafraichir)
            return
        self.rafraichir()

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        utile = jetons.largeur_utile(self.app.size.width)
        self.poser_etat(self.surface.avancement.ligne_d_etat(
            utile, ascii_seul=self.app.ascii_seul))
        # Le bloc de tete se **redessine a chaque jalon** : c'est ce qui fait
        # que « lot 1 sur 3 » devient « lot 2 sur 3 » et qu'un lot passe de
        # `en cours` a `écrit`. `contenu` ne le rend qu'une fois, au montage --
        # c'est l'ecart que `atelier_scan_ecriture.titre_de_la_tache` assumait
        # faute de pouvoir ouvrir ce fichier.
        lignes, etats = self.lignes_de_l_entete(
            utile, self.app.ascii_seul, self.lignes_de_lots_visibles())
        self._entete.update(bloc_peint(lignes, utile, self.app, etats=etats))
        combien = self.lignes_de_journal_visibles()
        # Le journal n'a pas de curseur, mais ses lignes portent des glyphes
        # d'etat : un jalon en echec doit se voir de loin, pas seulement se
        # lire. Aucun rang force -- il n'y a rien a surligner ici.
        self._journal.update(bloc_peint(
            [f"  {ligne}" for ligne in self.surface.journal.dernieres(combien)],
            utile, self.app))
        super().rafraichir()

    def lignes_de_journal_visibles(self) -> int:
        """Combien de lignes de journal tiennent, a la hauteur COURANTE.

        Derive de la fenetre et non du plancher : au-dela de 24 lignes, la place
        gagnee va entierement a la zone centrale (`DESIGN.md` section 1), donc
        au journal deplie. La calculer sur le plancher revenait a ignorer un
        terminal plein ecran.
        """
        hauteur_centre = jetons.hauteur_centrale(self.app.size.height)
        #: 3 lignes prises par l'entete de tache et sa ligne vide, plus une de
        #: respiration ; 2 lignes seulement quand le journal est replie.
        return max(hauteur_centre - 3, 0) if self.journal_deplie else 2

    def on_key(self, evenement) -> None:
        """`Tab` deplie le journal ; `Echap` ouvre l'interruption, il ne remonte pas.

        AC 4.1 : pendant une execution, `Echap` cesse d'etre une remontee. Il
        est donc **arrete ici** -- laisser l'application le voir depilerait
        l'ecran d'execution, c'est-a-dire ferait disparaitre la tache de la vue
        au lieu de demander quoi en faire.
        """
        if evenement.key == "tab":
            evenement.stop()
            self.journal_deplie = not self.journal_deplie
            self.rafraichir()
            return
        if evenement.key == "escape":
            evenement.stop()
            self.ouvrir_l_interruption()

    def ouvrir_l_interruption(self) -> "EcranInterruption":
        """Monte l'ecran d'interruption PAR-DESSUS. La tache continue derriere.

        AC 4.2 : ouvrir cet ecran n'arrete rien. C'est un empilement, pas une
        substitution -- l'ecran d'execution reste dans la pile, et l'emetteur
        du coeur continue de noter ses jalons dans la meme surface.

        **Le rappel est fourni ici, et il n'est pas facultatif.** Sans lui,
        l'ecran d'interruption etait un cul-de-sac clavier : les trois issues
        posaient `issue_declenchee` et n'appelaient personne, `Echap` ne
        depilait pas (une tache tourne), `q` posait un drapeau que rien
        n'affichait. Aucune sortie (revue de vague 1, couche 3).
        """
        ecran = EcranInterruption(self.panneau_de_ce_qui_est_ecrit(),
                                  sur_issue=self.issue_d_interruption)
        self.app.descendre(ecran)
        return ecran

    def issue_d_interruption(self, issue: Issue) -> None:
        """Ce qui se passe quand une des trois issues est validee.

        « Reprendre » est de la **navigation**, entierement interne a la surface
        partagee : elle depile ici, sans que l'atelier ait rien a faire. Les
        deux autres arretent un travail du coeur : elles vont a l'atelier, qui
        seul sait ce qu'il a ouvert.
        """
        if issue.cle == EcranInterruption.REPRENDRE:
            self.app.pop_screen()
            return
        if self._sur_issue is not None:
            self._sur_issue(issue)

    def panneau_de_ce_qui_est_ecrit(self) -> Panneau:
        """AC 4.4 : combien est deja ecrit, et ce qui reste valide.

        Les deux chiffres sont **mesures** -- ils viennent des jalons du coeur,
        pas d'une estimation -- donc aucun ne porte la mention de majorant.
        """
        avancement = self.surface.avancement
        unite = avancement.unite
        return Panneau(
            "Deja ecrit",
            [LigneChiffree(f"{unite.capitalize()} ecrites",
                           avancement.faites, unite),
             LigneChiffree(f"{unite.capitalize()} restantes",
                           max(avancement.total - avancement.faites, 0), unite)],
        )
