# -*- coding: utf-8 -*-
"""`E4-3b` -- un master qui existe deja (story 11.8, lot E, AC 8).

Un master porte deja le nom que la passe s'apprete a ecrire : l'operateur
tranche ici, **et il tranche toujours entre plusieurs issues**
(`EPIC11-ARB-89`, verbatim d'Egan : « au lieu d'un overwrite destructif,
toujours proposer un versionnage [...] Mais toujours permettre une reecriture
plutot qu'un blocage sec »).

Cet ecran arrive AVANT la confirmation, et ce n'est pas un detail
------------------------------------------------------------------
Meme ordre que l'atelier Pdf depuis `EPIC11-ARB-172` : le conflit se tranche
avant `E4-3`, sans quoi la confirmation annoncerait un nom de fichier que le
choix suivant peut encore changer.

```
E4-2 reglages -> E4-3b (SI un master existe) -> E4-3 -> E4-4
```

`EPIC11-ARB-188` commande cet ecran en entier
----------------------------------------------
Tranche par Egan le 2026-09-03, et il **retire** quelque chose :

* **trois issues, comme dessine** : creer la version suivante, remplacer
  sciemment (poids efface annonce), annuler. **Pas de quatrieme issue de
  suppression** -- le menu Projet la sert, avec sa propre confirmation ;
* **curseur sur `Annuler`** (« Ok sur annuler », verbatim) : la seule issue qui
  n'ecrit rien, lecture stricte d'`EPIC11-ARB-7`. Voir
  :func:`issues_du_conflit`, qui dit **comment** cet invariant est obtenu sans
  reecrire `panneau.ChoixExclusif` ;
* **le message « si ce master a deja ete livre, ne l'ecrasez pas » est
  RETIRE.** Egan : « On propose juste d'ecraser avec l'avertissement de ce qui
  sera supprime ou de versionner. » L'ecran annonce donc **ce qui sera
  detruit** -- un fait, verifiable a l'octet pres -- et cesse de conseiller un
  usage qu'il ne peut pas connaitre. C'est aussi ce qu'`EPIC11-ARB-56` exige de
  toute ligne d'etat : aucun conseil d'usage, aucun motif de conception.

Ce que ce module NE fait PAS, et c'est structurel
--------------------------------------------------
* il **ne calcule aucun rang** (AC 8.4). `EPIC11-ARB-92`, verbatim d'Egan :
  « **il ne faut pas rendre le rang** ». Le rang du prochain master est
  **donne**, deja resolu par `encode.resolve_master_version_rank` ; ce module
  l'affiche et le passe verbatim a `io.naming.build_master_filename`. Une
  frontiere negative mesure qu'aucune fonction de rang du coeur n'est nommee
  ici, et **afficher un rang ne le consomme pas** : monter cet ecran trois
  fois et annuler trois fois ne touche a aucun fichier ni a aucune ligne
  d'eau -- le banc le mesure aux inodes, et le banc de coeur
  (`tests/unit/test_versions_de_master.py::test_afficher_un_rang_ne_le_CONSOMME_pas`)
  le mesure au manifest ;
* il **n'offre pas la suppression**. `mmu project remove --master` existe deja,
  et `EPIC11-ARB-188` a tranche que le menu Projet la sert avec sa propre
  confirmation. **Une issue qui ne ferait rien serait pire qu'absente** ;
* il **n'ecrit rien**, ne supprime rien et ne renomme rien : il rend une issue
  a son appelant, qui la porte au coeur ;
* il **n'importe jamais `cli`** (`EPIC11-ARB-67`).

Deux ecarts avec la maquette validee, EPINGLES et non combles
--------------------------------------------------------------
* **le poids se rend par le format de taille du depot** (`explorateur.
  taille_lisible`, via `atelier_extraction_ecriture`), donc `1,4 Go` la ou la
  maquette a ecrit `1,38 Go` a la main. Une seconde ecriture du meme chiffre
  dans la meme interface divergerait au premier ajustement, et le depot a deja
  paye trois fois ce defaut ;
* **le repli de l'avertissement suit la largeur reelle du cartouche**, donc il
  ne coupe pas ou la maquette coupe. C'est deja le cas de `E5-3b`, dont la
  mention est repliee par `jetons.envelopper` : aucun mot n'est change, seule
  la coupure differe.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from ..io import naming
from . import jetons, projet_lecture
from .atelier_extraction_ecriture import taille_lisible
from .atelier_exports_reglages import UNITE_DE_CADENCE, texte_de_duree
from .atelier_scan import LARGEUR_DU_LIBELLE
from .coque import ObjetTravaille, Palier
from .panneau import ChoixExclusif, Issue

# ===========================================================================
# La grille du cartouche -- trois colonnes, comme la maquette les dessine
# ===========================================================================

#: Largeur de la colonne de la **valeur** du cartouche. La colonne du libelle,
#: elle, est celle du formulaire de l'atelier Scan (`LARGEUR_DU_LIBELLE`) et
#: n'est pas redigee ici : deux redactions du meme calage divergeraient au
#: premier reglage.
LARGEUR_DE_LA_VALEUR = 21

#: Le creux minimal entre une valeur et sa glose. Il est de **cinq** colonnes
#: et non de deux : une valeur plus large que sa colonne pousse sa glose, et a
#: deux colonnes les deux se toucheraient assez pour se lire comme un seul
#: champ. C'est la mesure de la maquette validee, ou `prores_hq · 1920×1080`
#: deborde de la colonne et garde cinq blancs avant sa glose.
CREUX_DE_LA_GLOSE = 5

#: L'indentation des issues sous le cartouche, et celle de leur ligne de
#: consequence. La seconde est **derivee** de la premiere plutot que tapee :
#: les deux se decalent ensemble le jour ou la maquette bouge.
INDENT_DU_CURSEUR = " " * 4
INDENT_DE_LA_CONSEQUENCE = INDENT_DU_CURSEUR + " " * 4

#: Le retrait d'une ligne de continuation sous un glyphe : la largeur du
#: glyphe et de son blanc, si bien que le message se lit comme un seul bloc.
INDENT_SOUS_LE_GLYPHE = " " * 2

#: Les libelles de la colonne de gauche, dans l'ordre de la maquette.
LIBELLE_DU_LOT = "Lot"
LIBELLE_DE_LA_DATE = "Écrit le"
LIBELLE_DU_CONTENU = "Contient"
LIBELLE_DU_PROFIL = "Profil · cible"

#: La glose de la ligne `Lot` quand le master present est celui d'ORIGINE :
#: `EPIC11-ARB-88`, le rang 1 ne s'ecrit dans aucun nom, donc rien ne le
#: designe sur le disque. Au-dela du rang d'origine la glose **disparait** :
#: le rang est alors dans le nom du fichier, affiche juste au-dessus, et le
#: redire en toutes lettres serait une seconde redaction du meme fait.
GLOSE_SANS_RANG = "aucun rang encore posé"

#: La glose de la ligne `Profil · cible`. C'est la raison d'etre de l'ecran :
#: deux masters qui different par le profil ou par la resolution ne sont pas
#: deux versions l'un de l'autre (`encode.cle_de_famille_de_master`), et le
#: conflit n'aurait pas lieu. Elle disparait si l'appelant dit le contraire --
#: un ecran qui l'affirmerait toujours n'affirmerait rien.
GLOSE_MEME_CLE = "la même clé qu'ici"

#: Le separateur des mesures d'une meme ligne : `124 échantillons · 25 fps`.
#: **Redige ici plutot qu'importe**, comme dans les autres ecrans du depot :
#: deux ecrans voisins ne doivent pas dependre l'un de l'autre, c'est le
#: parcours qui les enchaine.
SEPARATEUR = " · "

#: `prores_hq · 1920×1080` -- la cle de famille, rendue en clair. Le `×` porte
#: son repli ASCII dans `jetons.REPLIS_DE_TEXTE` ; sans lui `--ascii` en ferait
#: un `?`. **Pas d'espaces autour**, verbatim de la maquette : la valeur tient
#: alors dans la colonne du cartouche, ce qui n'est pas le cas de `E4-3`.
MOTIF_DE_LA_CIBLE = "{largeur}×{hauteur}"

#: Le format de la date d'ecriture d'un master : jour, mois, heure, comme la
#: maquette. Ce n'est **pas** `projet_lecture.date_courte`, et le motif n'est
#: pas la forme mais la SOURCE : celle-la traduit un horodatage ISO du
#: manifeste, alors qu'un master n'en porte aucun et que sa date vient du
#: systeme de fichiers.
FORMAT_DE_LA_DATE = "%d/%m à %H:%M"
#: La forme courte, pour la ligne d'etat : `26/08`.
FORMAT_DE_LA_DATE_COURTE = "%d/%m"

#: Le titre du cartouche. Il nomme un FAIT, jamais un echec (`DESIGN.md` §9).
TITRE_DU_CONFLIT = "Ce master existe déjà"


# ===========================================================================
# Le modele -- ce que l'ecran montre d'un master deja present
# ===========================================================================

@dataclass(frozen=True)
class MasterEnConflit:
    """Un master deja present, et ce que l'ecran en dit.

    **Les DEUX rangs sont donnes, aucun n'est calcule ici** (`EPIC11-ARB-92`,
    verbatim d'Egan : « il ne faut pas rendre le rang »). Ils arrivent **deja
    resolus du coeur** : celui du master present, et celui que la passe
    ecrirait. `rang_propose` n'a **aucune valeur par defaut** -- un defaut
    ferait de l'oubli de cablage un silence, et un ecran qui inventerait un
    numero de version est le pire mode de panne du versionnage : deux fichiers
    differents portant le meme nom, et une fois le master livre au client aucun
    manifeste ne rattrape cela.

    `echantillons`, `cadence`, `duree_s`, `poids_octets` et `quand` valent
    `None` quand la source qui les porte ne repond pas -- un fichier disparu du
    disque, un rapport `ffprobe` absent. Le segment correspondant **disparait**
    de la ligne : il vaut mieux une ligne plus courte qu'un chiffre invente.
    """

    #: Le master present, tel qu'il s'appelle sur le disque.
    nom: str
    #: Ce que « Créer la vN » ecrirait, **derive par `io.naming`** depuis le
    #: rang donne : le nom montre est celui qui sera ecrit, jamais un voisin.
    nom_propose: str
    lot_id: str
    #: Le rang du master present, `None` au rang d'origine -- valeur que
    #: `io.naming` emploie deja pour dire « aucun fragment `_vN` ».
    rang: int | None
    #: Le rang que `encode.resolve_master_version_rank` a rendu. **Requis.**
    rang_propose: int
    profil: str
    #: La geometrie de la cible, deja resolue par le coeur.
    geometrie: tuple[int, int] | None = None
    echantillons: int | None = None
    #: La cadence du master present, telle que le coeur l'ecrit.
    cadence: str | None = None
    duree_s: float | None = None
    poids_octets: int | None = None
    quand: str | None = None
    quand_court: str | None = None
    #: Vrai quand le master present partage la cle de famille de la passe.
    #: **Un fait donne**, jamais deduit ici : la cle vit au coeur.
    meme_cle: bool = True

    @property
    def poids(self) -> str | None:
        """Le poids du master present, **au format de taille du depot**.

        Aucune seconde redaction : c'est celui de l'explorateur, avec sa
        virgule decimale. La maquette a ecrit `1,38 Go` a la main ; le produit
        rend `1,4 Go`, et l'ecart est epingle plutot que comble par un
        quatrieme format de taille.
        """
        return taille_lisible(self.poids_octets)

    @property
    def annonce_la_destruction(self) -> bool:
        """Vrai quand l'ecran peut dire **ce qui sera detruit** (`EPIC11-ARB-188`).

        Il faut pour cela le poids **et** la date : c'est ce que l'arbitrage
        demande d'annoncer. Sans eux l'avertissement disparait -- l'issue, elle,
        reste offerte : « un refus qui n'offre aucune issue est aussi fautif
        qu'une destruction silencieuse ».
        """
        return self.poids is not None and bool(self.quand)


def _quand_du_fichier(chemin: Path, format_: str) -> str | None:
    try:
        horodate = chemin.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(horodate).strftime(format_)


def _octets_du_fichier(chemin: Path) -> int | None:
    try:
        return chemin.stat().st_size
    except OSError:
        return None


def conflit_du_master(chemin_present: Path | str, *,
                      lot_id: str,
                      profile_id: str,
                      container: str,
                      resolution_segment: str | None = None,
                      rang: int | None,
                      rang_propose: int,
                      geometrie: tuple[int, int] | None = None,
                      echantillons: int | None = None,
                      cadence: str | None = None,
                      duree_s: float | None = None,
                      meme_cle: bool = True) -> MasterEnConflit:
    """Le conflit d'un master present, lu du DISQUE pour ce que le disque sait.

    **`rang` et `rang_propose` sont requis et sans defaut** : ce sont les deux
    nombres que le coeur resout (`encode.resolve_master_version_rank`), et ce
    module ne sait produire ni l'un ni l'autre.

    Le poids et la date se lisent sur le **fichier** et non au manifeste :
    l'inventaire des masters ne porte ni l'un ni l'autre. Les deux valent
    `None` quand le fichier ne repond plus -- un master declare qui a quitte le
    disque est un etat que l'ecran dit au lieu de l'inventer.

    Le nom propose est derive par `io.naming.build_master_filename`, **la seule
    redaction de la convention**, et le rang y traverse **verbatim** : ni
    comparaison, ni repli, ni calcul. C'est le meme geste que
    `atelier_pdf_confirmation.preparer_le_plan` fait pour un tirage.
    """
    chemin = Path(chemin_present)
    return MasterEnConflit(
        nom=chemin.name,
        nom_propose=naming.build_master_filename(
            lot_id=lot_id, profile_id=profile_id, container=container,
            resolution_segment=resolution_segment,
            version_rank=rang_propose),
        lot_id=lot_id,
        rang=rang,
        rang_propose=rang_propose,
        profil=profile_id,
        geometrie=geometrie,
        echantillons=echantillons,
        cadence=cadence,
        duree_s=duree_s,
        poids_octets=_octets_du_fichier(chemin),
        quand=_quand_du_fichier(chemin, FORMAT_DE_LA_DATE),
        quand_court=_quand_du_fichier(chemin, FORMAT_DE_LA_DATE_COURTE),
        meme_cle=meme_cle,
    )


# ===========================================================================
# Les issues -- trois, jamais une seule, jamais un blocage sec
# ===========================================================================

CLE_CREER = "creer"
CLE_REMPLACER = "remplacer"
CLE_ANNULER = "annuler"

#: `Créer la v2` -- la version voisine, qui n'efface rien. Le rang y est
#: **affiche**, jamais derive ici.
LIBELLE_CREER = "Créer la v{rang}"

#: `Remplacer ce master` -- l'ecriture destructive **consciente**
#: d'`EPIC11-ARB-89`. Elle est toujours offerte : contrairement a un tirage
#: scanne, rien ne rend un master inecrasable -- il n'a pas de jumeau papier
#: qui porterait son rang.
LIBELLE_REMPLACER = "Remplacer ce master"

#: `Annuler` -- la sortie qui n'ecrit rien, et **celle que le curseur vise**.
LIBELLE_ANNULER = "Annuler"

#: La consequence de la creation : `écrit <nom>, sans rien effacer`. Elle porte
#: le glyphe **neutre** et non l'avertisseur : creer une version n'est ni une
#: reserve ni un interdit, c'est le cas courant.
CONSEQUENCE_DE_LA_CREATION = "écrit {nom}, sans rien effacer"

#: La consequence de l'ecrasement : `efface les 1,4 Go écrits le 26/08`. Une
#: issue qui ecrase **dit ce qu'elle ecrase**, sans quoi le consentement
#: d'`EPIC11-ARB-89` (« une ecriture destructive CONSCIENTE ») porte sur rien.
CONSEQUENCE_DE_L_ECRASEMENT = "efface les {poids} écrits le {quand}"

#: L'avertissement du cartouche, `EPIC11-ARB-188`. Il annonce **ce qui sera
#: detruit** -- le master et le rapport `ffprobe` que la story 6.4 ecrit a
#: cote --, et **rien d'autre** : plus un mot sur ce qu'il faudrait faire.
#: Le sujet de la phrase est le **verbe de l'issue**, lu de
#: :data:`LIBELLE_REMPLACER` : une phrase qui nommerait une issue disparue
#: serait pire qu'absente, et la lire ici garantit qu'elles bougent ensemble.
AVERTISSEMENT_DE_L_ECRASEMENT = (
    "{issue} efface les {poids} écrits le {quand}, et le rapport ffprobe "
    "qui les accompagne. Rien d'autre n'est touché.")

#: L'etat qui teinte l'avertissement du cartouche et la consequence de
#: l'ecrasement. Un nom de la table de `jetons`, jamais un dessin.
ETAT_DE_L_AVERTISSEMENT = "substitute"


def libelle_de_la_creation(rang_propose: int) -> str:
    """`Créer la v2`. Le rang est **affiche**, jamais derive ici."""
    return LIBELLE_CREER.format(rang=rang_propose)


def verbe_de_l_ecrasement() -> str:
    """`Remplacer` -- le premier mot de l'issue, lu de son libelle.

    La maquette ouvre l'avertissement par le verbe seul, la ou l'issue porte
    son complement (`Remplacer ce master`). Le lire ici plutot que de le
    retaper est ce qui empeche l'avertissement de nommer un jour une issue qui
    ne s'appelle plus ainsi -- meme geste que
    `atelier_pdf_versions.ligne_d_etat`, qui lit `LIBELLE_REMPLACER` entier.
    """
    return LIBELLE_REMPLACER.split(" ", 1)[0]


def issues_du_conflit(conflit: MasterEnConflit) -> list[Issue]:
    """Les **trois** issues de `E4-3b`, dans l'ordre de la maquette.

    **L'ensemble est EXACT et il se lit ici**, pas dans la maquette :

    * `Créer la vN` -- la version voisine, qui n'efface rien ;
    * `Remplacer ce master` -- l'ecrasement conscient d'`EPIC11-ARB-89` ;
    * `Annuler` -- la seule qui n'ecrit **rien**.

    **Pas de quatrieme issue de suppression** (`EPIC11-ARB-188`) : le menu
    Projet la sert, avec sa propre confirmation. Une issue inerte serait pire
    qu'absente.

    **Les DEUX premieres portent `ecrit=True`, et c'est ce qui pose le curseur
    sur `Annuler`.** `panneau.Issue.ecrit` dit, a sa propre definition, « si
    retenir cette issue provoque une **ecriture** » : creer la version voisine
    ecrit un master de plusieurs gigaoctets, donc elle ecrit. C'est la lecture
    litterale du champ, et c'est elle qui rend l'invariant d'`EPIC11-ARB-188`
    (« Ok sur annuler ») **structurel** plutot que pose a la main :
    `ChoixExclusif.__post_init__` place le curseur sur la premiere issue qui
    n'ecrit pas, et il n'y en a qu'une.

    **Cette lecture DIVERGE de celle des deux autres ecrans de conflit du
    produit**, et l'ecart est signale plutot que tu :
    `atelier_pdf_versions.LIBELLE_CREER` et
    `atelier_scan_calibrate.issues_de_la_collision` documentent tous deux
    qu'ils lisent `ecrit` comme « **detruit** quelque chose », ce qui pose leur
    curseur sur l'issue non destructive. `EPIC11-ARB-188` tranche l'autre sens
    pour cet ecran-ci ; l'harmonisation des trois n'appartient pas a ce lot.
    """
    return [
        Issue(CLE_CREER, libelle_de_la_creation(conflit.rang_propose),
              ecrit=True),
        Issue(CLE_REMPLACER, LIBELLE_REMPLACER, ecrit=True),
        Issue(CLE_ANNULER, LIBELLE_ANNULER),
    ]


def choix_du_conflit(conflit: MasterEnConflit) -> ChoixExclusif:
    """Le point de jugement. **Le curseur part sur `Annuler`** (`EPIC11-ARB-188`).

    Il n'est pas pose ici : c'est `ChoixExclusif.__post_init__` qui le place, et
    cet invariant n'est pas reecrit (`EPIC11-ARB-7`). Ce module se contente de
    lui donner des issues dont **une seule** n'ecrit pas -- ce qui est aussi ce
    qui rend l'invariant verifiable plutot que suppose.
    """
    return ChoixExclusif(issues_du_conflit(conflit))


def consequences_des_issues(conflit: MasterEnConflit) -> dict[str, str]:
    """La ligne de consequence de chaque issue qui en porte une.

    Deux issues seulement en portent -- la creation dit le nom qu'elle ecrit,
    l'ecrasement dit ce qu'il efface. `Annuler` n'emporte rien qui doive etre
    chiffre, et une ligne de consequence vide occuperait une ligne de la grille
    pour ne rien dire.

    L'ecrasement perd la sienne quand le disque n'a pas repondu : un poids
    inconnu ne s'ecrit **pas** `0 Go` -- ce serait annoncer qu'on n'efface rien
    alors qu'on efface un fichier dont on n'a pas su lire la taille.
    """
    consequences = {
        CLE_CREER: CONSEQUENCE_DE_LA_CREATION.format(nom=conflit.nom_propose),
    }
    if conflit.poids is not None and conflit.quand_court:
        consequences[CLE_REMPLACER] = CONSEQUENCE_DE_L_ECRASEMENT.format(
            poids=conflit.poids, quand=conflit.quand_court)
    return consequences


#: Le GLYPHE de chaque ligne de consequence : neutre pour la creation,
#: avertisseur pour l'ecrasement. **Une table et non un `if`** : c'est le seul
#: endroit qui marque une consequence, et deux redactions divergeraient.
#:
#: **`neutre` est un nom de GLYPHE, pas un nom d'etat**, et la distinction est
#: ce que le banc a paye : `jetons.peindre` n'accepte que les trois noms de
#: `jetons.NOMS_D_ETAT` (`complete`, `substitute`, `absent`) et **leve** sur
#: tout autre. Une premiere redaction donnait `neutre` comme etat de la ligne
#: de creation ; l'ecran montait, puis mourait au premier dessin d'un
#: `KeyError` -- une panne que seul le montage voit, jamais la composition.
#: Une consequence neutre ne se **teinte** donc pas : elle porte son glyphe et
#: rien d'autre, ce qui est aussi ce que la maquette dessine.
GLYPHE_DES_CONSEQUENCES: Mapping[str, str] = {
    CLE_CREER: "neutre",
    CLE_REMPLACER: ETAT_DE_L_AVERTISSEMENT,
}


# ===========================================================================
# Le cartouche
# ===========================================================================

def _ligne_de_fiche(libelle: str, valeur: str, glose: str = "") -> str:
    """Une ligne du cartouche : libelle, valeur, glose, en trois colonnes.

    La valeur est **calee** sur :data:`LARGEUR_DE_LA_VALEUR` pour que les
    gloses s'alignent ; une valeur plus large que sa colonne pousse sa glose
    plutot que de la tronquer -- il vaut mieux une glose decalee qu'une valeur
    amputee, puisque c'est la valeur qui porte le fait.

    Les deux calages sont mesures en **colonnes** et jamais en `len()` : un
    ideogramme en occupe deux, et toute la grille partirait avec lui.
    """
    tete = libelle + " " * max(1, LARGEUR_DU_LIBELLE - jetons.colonnes(libelle))
    if not glose:
        return (tete + valeur).rstrip()
    creux = max(LARGEUR_DE_LA_VALEUR - jetons.colonnes(valeur),
                CREUX_DE_LA_GLOSE)
    return tete + valeur + " " * creux + glose


def texte_de_la_cible(conflit: MasterEnConflit) -> str:
    """`prores_hq · 1920×1080` -- la cle de famille, rendue en clair.

    La geometrie disparait quand personne ne l'a resolue : `native` n'a de
    taille qu'apres avoir sonde les frames, et l'inventer ici ferait annoncer
    une cible que le master n'aura pas.
    """
    if not conflit.geometrie:
        return conflit.profil
    return conflit.profil + SEPARATEUR + MOTIF_DE_LA_CIBLE.format(
        largeur=conflit.geometrie[0], hauteur=conflit.geometrie[1])


def texte_du_contenu(conflit: MasterEnConflit) -> str:
    """`124 échantillons · 25 fps · 4 s 96 · 1,4 Go` -- les inconnus disparaissent.

    La duree se rend par `atelier_exports_reglages.texte_de_duree`, **ecrite
    une fois pour cet atelier** : `E4-2b` en avait besoin le premier, et les
    ecrans suivants la lisent plutot que d'en ecrire une seconde. L'unite de
    cadence vient du meme module, pour la meme raison.
    """
    mesures = []
    if conflit.echantillons is not None:
        mesures.append(f"{conflit.echantillons} échantillons")
    if conflit.cadence:
        mesures.append(f"{conflit.cadence} {UNITE_DE_CADENCE}")
    duree = texte_de_duree(conflit.duree_s)
    if duree is not None:
        mesures.append(duree)
    if conflit.poids is not None:
        mesures.append(conflit.poids)
    return SEPARATEUR.join(mesures)


def texte_de_l_avertissement(conflit: MasterEnConflit) -> str:
    """L'avertissement d'`EPIC11-ARB-188`, ou rien du tout.

    Il annonce **ce qui sera detruit** et cesse de conseiller un usage. Sans
    poids ni date il n'a rien a annoncer, et il disparait : un avertissement
    qui ne nomme pas ce qu'il efface est le contraire de ce que l'arbitrage
    demande.
    """
    if not conflit.annonce_la_destruction:
        return ""
    return AVERTISSEMENT_DE_L_ECRASEMENT.format(
        issue=verbe_de_l_ecrasement(), poids=conflit.poids,
        quand=conflit.quand_court or conflit.quand)


def lignes_de_la_fiche(conflit: MasterEnConflit,
                       ascii_seul: bool = False) -> list[str]:
    """Les lignes de fiche du cartouche, dans l'ordre de la maquette.

    La premiere porte le **nom du master present** sous le glyphe
    d'avertissement : c'est l'objet du conflit, et il se lit avant tout le
    reste. Les lignes dont la source ne repond pas disparaissent.
    """
    table = jetons.glyphes(ascii_seul)
    lignes = [f"{table[ETAT_DE_L_AVERTISSEMENT]} {conflit.nom}"]
    lignes.append(_ligne_de_fiche(
        LIBELLE_DU_LOT, conflit.lot_id,
        GLOSE_SANS_RANG if conflit.rang is None else ""))
    if conflit.quand:
        lignes.append(_ligne_de_fiche(LIBELLE_DE_LA_DATE, conflit.quand))
    contenu = texte_du_contenu(conflit)
    if contenu:
        lignes.append(_ligne_de_fiche(LIBELLE_DU_CONTENU, contenu))
    lignes.append(_ligne_de_fiche(
        LIBELLE_DU_PROFIL, texte_de_la_cible(conflit),
        GLOSE_MEME_CLE if conflit.meme_cle else ""))
    return [jetons.replier_ascii(ligne) if ascii_seul else ligne
            for ligne in lignes]


def lignes_de_l_avertissement(conflit: MasterEnConflit, largeur: int,
                              ascii_seul: bool = False) -> list[str]:
    """L'avertissement replie, son glyphe en tete, ses continuations alignees.

    `EPIC11-ARB-71` exige qu'un avertissement multiligne soit peint
    **entierement** : les continuations sont indentees de la largeur du glyphe,
    si bien que le message se lit comme un seul bloc -- et qu'aucune d'elles ne
    porte de glyphe a reconnaitre, ce que :meth:`EcranMasterExistant.etats_du_cartouche`
    compense en donnant l'etat de **toutes** les lignes.
    """
    texte = texte_de_l_avertissement(conflit)
    if not texte:
        return []
    repliees = jetons.envelopper(
        texte, max(largeur - len(INDENT_SOUS_LE_GLYPHE), 1), ascii_seul)
    if not repliees:
        # Un cartouche trop etroit ne rend rien : poser le glyphe seul
        # afficherait un `▲` qui n'avertit de rien.
        return []
    table = jetons.glyphes(ascii_seul)
    lignes = [f"{table[ETAT_DE_L_AVERTISSEMENT]} {repliees[0]}"]
    lignes += [f"{INDENT_SOUS_LE_GLYPHE}{ligne}" for ligne in repliees[1:]]
    return [jetons.replier_ascii(ligne) if ascii_seul else ligne
            for ligne in lignes]


def lignes_du_cartouche(conflit: MasterEnConflit, largeur: int,
                        ascii_seul: bool = False) -> list[str]:
    """La fiche, une ligne vide, puis l'avertissement -- comme la maquette.

    La ligne vide **ne parait pas** quand l'avertissement disparait : une
    ligne vide en queue de cartouche est un blanc que rien ne justifie.
    """
    fiche = lignes_de_la_fiche(conflit, ascii_seul)
    avertissement = lignes_de_l_avertissement(conflit, largeur, ascii_seul)
    if not avertissement:
        return fiche
    return fiche + [""] + avertissement


# ===========================================================================
# La ligne d'etat et le bandeau -- des CONSTATS, jamais un conseil
# ===========================================================================

#: Ce que la ligne d'etat dit du master present : ce qui est ecrit, et depuis
#: quand. Les deux viennent du **fichier**.
ECRITURE_DU_MASTER = "{poids} écrits le {quand}"
#: Le rang libre, **donne** par le coeur et affiche tel quel.
ETAT_DU_RANG_LIBRE = "le prochain rang est {rang}"
#: Ce que l'ecran n'a pas encore fait. `EPIC11-ARB-56` : un constat, pas une
#: promesse rassurante -- rien n'est efface **parce que** rien n'a ete retenu.
RIEN_N_EST_EFFACE = "rien n'est effacé"

#: La droite du bandeau : `master présent · rang 2 libre`.
OBJET_DU_BANDEAU = "master présent"
MENTION_DU_RANG_LIBRE = "rang {rang} libre"


def ligne_d_etat(conflit: MasterEnConflit, ascii_seul: bool = False) -> str:
    """`▲  1,4 Go écrits le 26/08 · le prochain rang est 2 · rien n'est effacé`.

    Trois constats, dans l'ordre de la maquette : ce qui est la, ce qui est
    libre, ce qui n'a pas eu lieu. Aucune touche, aucun conseil d'usage, aucun
    motif de conception (`EPIC11-ARB-56`).

    Le premier segment **disparait** quand le disque n'a pas repondu : le
    module retire partout ailleurs les segments qu'il ne sait pas remplir, et
    un separateur de tete annoncerait une mesure qui n'existe pas.
    """
    table = jetons.glyphes(ascii_seul)
    segments = []
    if conflit.poids is not None and conflit.quand_court:
        segments.append(ECRITURE_DU_MASTER.format(
            poids=conflit.poids, quand=conflit.quand_court))
    segments.append(ETAT_DU_RANG_LIBRE.format(rang=conflit.rang_propose))
    segments.append(RIEN_N_EST_EFFACE)
    ligne = f"{table[ETAT_DE_L_AVERTISSEMENT]}  " + SEPARATEUR.join(segments)
    return jetons.replier_ascii(ligne) if ascii_seul else ligne


def bandeau_du_conflit(conflit: MasterEnConflit) -> str:
    """`master présent · rang 2 libre` -- compose du conflit, jamais recu."""
    return (OBJET_DU_BANDEAU + SEPARATEUR
            + MENTION_DU_RANG_LIBRE.format(rang=conflit.rang_propose))


# ===========================================================================
# `E4-3b` -- l'ecran
# ===========================================================================

#: La ligne de raccourcis, verbatim de la maquette (l. 22). Constante de
#: module, comme celles des autres ateliers : c'est ce qui la fait balayer par
#: la garde d'epic du repli ASCII et par celle des majuscules.
#: MESURE: 44/49
RACCOURCIS_DU_CONFLIT = "⏎ valider  ↑↓ choisir  Échap retour  F1 aide"


class EcranMasterExistant(ObjetTravaille, Palier):
    """`E4-3b` -- un master existe deja, et l'operateur tranche (AC 8).

    Un cartouche, un avertissement, un `ChoixExclusif` dont deux issues portent
    une ligne de consequence. **Il n'existe pas d'instance a zero issue** :
    `ChoixExclusif.__post_init__` en exige deux, et cet invariant n'est pas
    reecrit ici.

    `retenir` est **injecte et REQUIS** (finding `K3`) : un point de jugement
    qui ne sait pas a qui rendre son issue est un cul-de-sac.
    """

    titre = projet_lecture.EXPORTS
    raccourcis = RACCOURCIS_DU_CONFLIT

    #: Un passage : on y decide, puis on en sort.
    TRANSITOIRE = True
    ID_DU_CARTOUCHE = "cartouche-master-existant"
    ID_DES_ISSUES = "issues-master-existant"

    def __init__(self, conflit: MasterEnConflit, *,
                 retenir: Callable[[Issue], None]) -> None:
        super().__init__()
        self.conflit = conflit
        self.choix = choix_du_conflit(conflit)
        self._retenir = retenir

    # -- rendu ------------------------------------------------------------

    def largeur_du_cartouche(self) -> int:
        """La largeur ecrivable du cartouche, **lue de la fenetre courante**.

        Elle retombe sur le plancher d'`EPIC11-ARB-21` tant qu'aucune
        application ne porte l'ecran : le repli d'un message se calcule aussi
        hors montage -- c'est ainsi qu'un banc mesure l'avertissement sans
        piloter la boucle d'evenements. `Screen.app` **leve** quand aucune
        application n'est active, donc un `getattr(..., None)` ne rattrape rien.
        """
        try:
            largeur = self.app.size.width
        except Exception:                                  # noqa: BLE001
            largeur = jetons.LARGEUR_PLANCHER
        return jetons.largeur_de_cartouche(largeur)

    def titre_du_cartouche(self, ascii_seul: bool = False) -> str:
        return (jetons.replier_ascii(TITRE_DU_CONFLIT) if ascii_seul
                else TITRE_DU_CONFLIT)

    def lignes_du_corps(self, ascii_seul: bool = False) -> list[str]:
        return lignes_du_cartouche(self.conflit, self.largeur_du_cartouche(),
                                   ascii_seul)

    def etats_du_cartouche(self, ascii_seul: bool = False) -> dict[int, str]:
        """L'etat DONNE de chaque ligne : le nom, et **toute** la mention.

        « Un avertissement se colorise ENTIEREMENT, jamais une ligne sur deux --
        un avertissement multiligne est un seul objet » (`EPIC11-ARB-71`). Une
        ligne de continuation ne porte, par construction, aucun glyphe : la
        reconnaissance par motif de `jetons.peindre` ne verrait que la premiere.
        """
        lignes = self.lignes_du_corps(ascii_seul)
        mention = len(lignes_de_l_avertissement(
            self.conflit, self.largeur_du_cartouche(), ascii_seul))
        etats = {0: ETAT_DE_L_AVERTISSEMENT}
        for rang in range(len(lignes) - mention, len(lignes)):
            etats[rang] = ETAT_DE_L_AVERTISSEMENT
        return etats

    def lignes_des_issues(self,
                          ascii_seul: bool = False) -> tuple[list[str], int]:
        """Les lignes des issues **et** le rang de celle du curseur, en UN passage.

        Deux reperages tenus separement -- une methode qui rendrait les lignes,
        une autre qui compterait les rangs -- divergent des la premiere ligne de
        consequence ajoutee, et le curseur se peindrait alors sur une autre
        issue sans que rien ne le dise.
        """
        table = jetons.glyphes(ascii_seul)
        consequences = consequences_des_issues(self.conflit)
        lignes: list[str] = []
        rang = 0
        for position, issue in enumerate(self.choix.issues):
            if position == self.choix.curseur:
                rang = len(lignes)
            marque = (table["curseur"] if position == self.choix.curseur
                      else " ")
            lignes.append(f"{INDENT_DU_CURSEUR}{marque} {issue.libelle}")
            consequence = consequences.get(issue.cle)
            if consequence:
                glyphe = table[GLYPHE_DES_CONSEQUENCES[issue.cle]]
                lignes.append(f"{INDENT_DE_LA_CONSEQUENCE}"
                              f"{glyphe} {consequence}")
        if ascii_seul:
            lignes = [jetons.replier_ascii(ligne) for ligne in lignes]
        return lignes, rang

    def etats_des_issues(self, ascii_seul: bool = False) -> dict[int, str]:
        """L'etat DONNE de chaque ligne de consequence.

        Meme motif que le cartouche : un glyphe pose derriere une indentation
        n'ouvre pas de colonne au sens de `jetons.jeton_d_etat`, donc la
        reconnaissance par motif ne le voit pas. L'etat est donc **donne**,
        ligne par ligne, et une consequence qui disparait emporte le sien.

        **Seuls les noms d'etat de `jetons.NOMS_D_ETAT` sortent d'ici** : le
        glyphe neutre de la creation n'en est pas un, et le donner faisait
        lever `jetons.peindre` au premier dessin. Le filtre se lit a la source
        plutot que d'exclure `neutre` a la main -- un quatrieme glyphe non
        colorisable retomberait alors du bon cote de lui-meme.
        """
        consequences = consequences_des_issues(self.conflit)
        etats: dict[int, str] = {}
        rang = 0
        for issue in self.choix.issues:
            rang += 1
            if consequences.get(issue.cle):
                glyphe = GLYPHE_DES_CONSEQUENCES[issue.cle]
                if glyphe in jetons.NOMS_D_ETAT:
                    etats[rang] = glyphe
                rang += 1
        return etats

    def etat(self, ascii_seul: bool = False) -> str:
        return ligne_d_etat(self.conflit, ascii_seul)

    def objet_du_bandeau(self) -> str:
        """La DROITE du bandeau, **rendue au moment de dessiner**.

        L'objet travaille change d'un ecran a l'autre, et l'ecrire dans le
        contexte le ferait survivre au palier qui l'a pose.
        """
        return bandeau_du_conflit(self.conflit)

    def contenu(self) -> list[Widget]:
        ascii_seul = getattr(self.app, "ascii_seul", False)
        self._cartouche = Static("", id=self.ID_DU_CARTOUCHE)
        self._corps = Vertical(self._cartouche,
                               id=f"corps-{self.ID_DU_CARTOUCHE}")
        self._corps.border_title = self.titre_du_cartouche(ascii_seul)
        self._issues = Static("", id=self.ID_DES_ISSUES)
        return [self._corps, Static(""), self._issues]

    def on_mount(self) -> None:
        self.rafraichir()

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        ascii_seul = self.app.ascii_seul
        largeur = self.app.size.width
        cartouche = jetons.largeur_de_cartouche(largeur)
        utile = jetons.largeur_utile(largeur)
        self._corps.border_title = self.titre_du_cartouche(ascii_seul)
        self._cartouche.update(jetons.peindre(
            [jetons.ajuster(ligne, cartouche, ascii_seul)
             for ligne in self.lignes_du_corps(ascii_seul)],
            ascii_seul=ascii_seul, sans_couleur=self.app.sans_couleur,
            etats=self.etats_du_cartouche(ascii_seul)))
        lignes, rang = self.lignes_des_issues(ascii_seul)
        self._issues.update(jetons.peindre(
            [jetons.ajuster(ligne, utile, ascii_seul) for ligne in lignes],
            ascii_seul=ascii_seul, sans_couleur=self.app.sans_couleur,
            ligne_du_curseur=rang,
            etats=self.etats_des_issues(ascii_seul)))
        self.poser_etat(self.etat(ascii_seul))
        super().rafraichir()

    # -- clavier ----------------------------------------------------------

    def rang_du_curseur(self, ascii_seul: bool = False) -> int:
        """Le rang **rendu** de la ligne du curseur, dans le bloc des issues.

        Le regime est **passe** plutot que lu de l'application : un test qui
        interroge le rang apres avoir referme le banc n'a plus d'application
        active, et `Screen.app` **leve** alors.
        """
        return self.lignes_des_issues(ascii_seul)[1]

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """`↑↓` deplacent, `⏎` retient. **Aucune lettre n'est un raccourci.**

        `EPIC11-ARB-45` / `-126` : fleche seule hors des listes a cocher. La
        frappe imprimable est **consommee** -- la ligne de raccourcis n'annonce
        aucune sortie par lettre, et laisser remonter une lettre fermerait
        l'application sur une touche que rien n'annonce.
        """
        if touche in ("up", "down"):
            self.choix.deplacer(-1 if touche == "up" else 1)
            return True
        if touche == "enter":
            issue = self.choix.valider()
            if issue is not None:
                self._retenir(issue)
            return True
        if caractere and caractere.isprintable():
            return True
        return False


__all__ = [
    "AVERTISSEMENT_DE_L_ECRASEMENT",
    "CLE_ANNULER",
    "CLE_CREER",
    "CLE_REMPLACER",
    "CONSEQUENCE_DE_LA_CREATION",
    "CONSEQUENCE_DE_L_ECRASEMENT",
    "CREUX_DE_LA_GLOSE",
    "ECRITURE_DU_MASTER",
    "ETAT_DE_L_AVERTISSEMENT",
    "ETAT_DU_RANG_LIBRE",
    "EcranMasterExistant",
    "GLYPHE_DES_CONSEQUENCES",
    "GLOSE_MEME_CLE",
    "GLOSE_SANS_RANG",
    "INDENT_DE_LA_CONSEQUENCE",
    "INDENT_DU_CURSEUR",
    "LARGEUR_DE_LA_VALEUR",
    "LIBELLE_ANNULER",
    "LIBELLE_CREER",
    "LIBELLE_DE_LA_DATE",
    "LIBELLE_DU_CONTENU",
    "LIBELLE_DU_LOT",
    "LIBELLE_DU_PROFIL",
    "LIBELLE_REMPLACER",
    "MENTION_DU_RANG_LIBRE",
    "MOTIF_DE_LA_CIBLE",
    "MasterEnConflit",
    "OBJET_DU_BANDEAU",
    "RACCOURCIS_DU_CONFLIT",
    "RIEN_N_EST_EFFACE",
    "SEPARATEUR",
    "TITRE_DU_CONFLIT",
    "bandeau_du_conflit",
    "choix_du_conflit",
    "conflit_du_master",
    "consequences_des_issues",
    "issues_du_conflit",
    "libelle_de_la_creation",
    "ligne_d_etat",
    "lignes_de_l_avertissement",
    "lignes_de_la_fiche",
    "lignes_du_cartouche",
    "texte_de_la_cible",
    "texte_de_l_avertissement",
    "texte_du_contenu",
    "verbe_de_l_ecrasement",
]
