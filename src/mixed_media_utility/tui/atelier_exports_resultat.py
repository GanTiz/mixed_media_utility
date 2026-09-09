# -*- coding: utf-8 -*-
"""`E4-5` -- le resultat de l'encodage (story 11.8, lot G, AC 10).

**C'est le seul ecran du produit qui affirme ce qui existe sur le disque**, et
c'est ce qui commande tout ce module : un chiffre recalcule ici serait un
mensonge en puissance, parce que rien ne le confronterait jamais au fichier
qu'il pretend decrire.

Ce que le panneau porte, et **d'ou chaque valeur vient** (AC 10.1)
------------------------------------------------------------------

Deux objets du coeur, nommes par l'AC : `codec_profiles.EncodeOutcome` --
transporte verbatim par `encode.EncodeCommandResult.outcome` -- et
`io.encode_manifest.PersistedEncode`. Le point d'entree de coeur les rend tous
les deux dans un seul `encode_master.MasterDuLot`, et :meth:`MasterEcrit.du_master`
les lit sans en recomposer un troisieme :

===========================  =========================================
ce que la ligne montre       ce qui la rend
===========================  =========================================
le nom du master             `outcome.output_path` (son nom de fichier)
les echantillons             `outcome.frame_count`
la cadence                   `outcome.frame_rate`
le timecode de depart        `outcome.timecode`
l'etat du lot                `persisted.state_written`
les constats                 `resultat.findings` + `persisted.findings`
le rapport de verification   `resultat.verification`
===========================  =========================================

**Les trois valeurs que NI l'un NI l'autre ne rend, dites plutot que tues.**

1. **la taille du master.** Aucun des deux objets ne porte un poids reel :
   `EncodeOutcome.encoded_size` est une **geometrie** (largeur, hauteur), et
   l'inventaire du manifest ne porte aucun octet. Le seul poids vrai est celui
   du fichier, et il se **mesure** -- :func:`octets_du_master`, un `stat` garde,
   sur le meme patron que `atelier_extraction_ecriture._octets_du_dossier`.
   Mesurer le disque n'est pas recalculer le coeur : c'est precisement ce que
   cet ecran-ci est le seul a pouvoir faire. **Ce qui serait fautif** serait de
   reafficher `EncodePlan.estimated_bytes`, qui est un **majorant** --
   `execution.EcranResultat` leve d'ailleurs a la construction sur un panneau
   qui en porte un ;
2. **la duree du master.** Le coeur n'en rend aucune -- mesure faite : aucun
   `duration` ni `duree` dans `encode.py`, `codec_profiles.py`,
   `encode_previz.py` ni `video_metadata.py`. Elle est donc **donnee**, par la
   `MesureDuMaster` que l'ecran de reglages a deja affichee (lot D) : deux
   redactions de « combien de temps dure ce master » divergeraient entre les
   reglages et le resultat, sur le meme plan. Personne ne la donne -> la ligne
   **disparait**, elle ne se derive pas de `frame_count / frame_rate` ;
3. **la duree d'encodage.** C'est une mesure de la PASSE, pas du master : le
   parcours la chronometre et la donne, exactement comme le rapport du Scan
   (`atelier_scan_resultat.chronometre`). Absente -> ligne omise.

**Ce que le panneau ne peut PAS porter, et c'est un arbitrage** : la ligne
`Reconstruction  v2 · 8 planches scannées le 02/09` de la maquette. La cle de
famille d'un master **ne gagne pas** la reconstruction (`EPIC11-ARB-193`,
story 6.8), si bien que **rien au manifeste ne dit de quelle passe de
reconstruction un master est issu**. La deviner depuis le nom du dossier de
frames serait exactement le recalcul que l'AC 10.1 interdit. La ligne est donc
**absente**, et le lot le signale plutot que de la fabriquer.

Les quatre suites, au clavier seul (AC 10.2, `EPIC11-ARB-11`)
--------------------------------------------------------------

`EPIC11-ARB-89` : jamais une seule issue. Les quatre sont **servables**, et ca
a ete mesure avant d'etre dessine -- une issue qui ne fait rien est un blocage
sec deguise, et ce depot l'a deja paye (le refus qui conseillait
`--nouvelle-version`, option qui n'existait pas au parser) :

* `Ouvrir le dossier` et `Ouvrir le fichier` passent par
  `execution.ouvrir_dans_l_explorateur_du_systeme` et
  `execution.ouvrir_dans_la_visionneuse_du_systeme` -- les deux existent, elles
  partagent l'**unique** lancement de processus tolere dans `tui/`
  (`EPIC11-ARB-85`), et elles rendent **une phrase dans tous les cas**, y
  compris quand aucun bureau n'est joignable. Ce module n'en ouvre aucun
  second ;
* `Encoder un autre lot` remonte a la page d'ouverture de l'atelier ;
* `Retour aux ateliers` est posee par `execution.EcranResultat` lui-meme
  (`EPIC11-ARB-13`), en dernier -- on ne l'ecrit donc pas ici, sous peine de la
  voir deux fois.

Aucune lettre n'est un raccourci, et **il n'y avait rien a verifier de plus** :
cet ecran ne porte aucun champ de saisie, donc `EPIC11-ARB-68` ne mord pas
ici. Une frontiere negative le mesure plutot que de le supposer.

La ligne d'etat porte une MESURE (AC 10.3, `EPIC11-ARB-56`)
-------------------------------------------------------------

`{taille} écrits · métadonnées vérifiées par ffprobe · aucun refus` : trois
faits, **aucune touche**, aucun motif de conception, aucun conseil d'usage.
C'est la meme regle qui a fait retirer, de l'ecran de conflit, « si ce master a
deja ete livre, ne l'ecrasez pas » (`EPIC11-ARB-188`) -- l'ecran annonce un
fait, il ne conseille pas un usage. Chacun des trois segments **disparait**
quand la mesure qui le fonde manque, plutot que de sortir a zero.

Ce module n'importe jamais `cli` (`EPIC11-ARB-67`) et n'ecrit rien : quand cet
ecran monte, l'ecriture est finie.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import avancement, cadences, explorateur, jetons, projet_lecture
from .atelier_exports_execution import (PassageDeLEncodage,
                                        UNITE_DES_ECHANTILLONS,
                                        dossier_de_sortie)
from .atelier_exports_reglages import SEPARATEUR, texte_de_duree
from .atelier_extraction import _application_montee
from .coque import EcranPasEncore
from .execution import (EcranResultat, ouvrir_dans_l_explorateur_du_systeme,
                        ouvrir_dans_la_visionneuse_du_systeme)
from .panneau import LigneChiffree, Panneau

# ---------------------------------------------------------------------------
# Les libelles -- verbatim de la maquette validee
# ---------------------------------------------------------------------------

#: Le titre du cartouche, verbatim de `E4-5` (l. 5).
TITRE_DU_CARTOUCHE = "Écrit"

#: Les cinq libelles de colonne de gauche que ce lot sert, verbatim de la
#: maquette. **La sixieme, `Reconstruction`, n'est pas ici** : voir la tete de
#: module -- `EPIC11-ARB-193` fait qu'aucun objet du coeur ne la rend.
LIBELLE_TAILLE = "Taille"
LIBELLE_DUREE = "Durée"
LIBELLE_TIMECODE = "Timecode de départ"
LIBELLE_EMPLACEMENT = "Emplacement"
LIBELLE_ETAT_DU_LOT = "État du lot"
LIBELLE_DUREE_D_ENCODAGE = "Durée d'encodage"

#: Ce que la ligne d'etat du lot ajoute a l'etat lui-meme, verbatim de la
#: maquette : un **fait** sur ce que la passe a fait du manifest.
MENTION_DECLARE = "déclaré au manifest"

#: L'unite de cadence, telle que la maquette l'ecrit. Le **nombre**, lui, est
#: rendu par `cadences.texte_de_cadence` -- seule redaction du depot pour
#: l'ecriture decimale d'une cadence.
UNITE_DE_CADENCE = "fps"

# ---------------------------------------------------------------------------
# La ligne d'etat
# ---------------------------------------------------------------------------

#: Le premier segment : ce que le fichier **pese reellement**.
MOTIF_DU_POIDS_ECRIT = "{taille} écrits"

#: Le deuxieme, verbatim de la maquette. Il n'apparait que si un rapport de
#: verification existe : sans champ verifie, l'annoncer serait une promesse.
MENTION_VERIFIEE = "métadonnées vérifiées par ffprobe"

#: Le troisieme, verbatim. **Il est conditionnel** : un constat emis par le
#: coeur le remplace, faute de quoi l'ecran dirait « aucun refus » en taisant
#: ce que la passe a constate. Les codes sortent du coeur **verbatim** --
#: `EPIC11-ARB-30` : la TUI n'ecrit aucun jugement que le coeur ne porte pas.
AUCUN_REFUS = "aucun refus"
MOTIF_DES_CONSTATS = "constats : {codes}"
SEPARATEUR_DES_CONSTATS = ", "

# ---------------------------------------------------------------------------
# Le journal -- ce qu'il y a a lire APRES, la ou il n'y avait rien PENDANT
# ---------------------------------------------------------------------------

#: `EPIC11-ARB-189` : le journal ffmpeg reste **en memoire**, montre puis
#: perdu, et l'ecran ne promet aucun fichier. Ce qu'il montre est le rapport de
#: `video_metadata.verify_technical_metadata`, champ a champ -- c'est ce qui
#: distingue cet ecran de `E4-4`, qui n'annonce pas `Tab journal` parce qu'il
#: n'y a rien a lire PENDANT l'encodage.
MOTIF_DU_CHAMP_VERIFIE = "{champ} : {valeur}"

#: Un constat du coeur, avec son code verbatim. Le mot est celui que la
#: commande emploie deja (`  Constat: <code>`).
MOTIF_DU_CONSTAT = "Constat : {code}"

# ---------------------------------------------------------------------------
# Les suites
# ---------------------------------------------------------------------------

#: Les trois suites que cet ecran pose, verbatim de la maquette (l. 16-18).
#: La quatrieme -- `Retour aux ateliers` -- est posee par `EcranResultat`
#: lui-meme, en dernier : l'ecrire ici la ferait apparaitre deux fois.
SUITE_DOSSIER = "Ouvrir le dossier"
SUITE_FICHIER = "Ouvrir le fichier"
SUITE_AUTRE_LOT = "Encoder un autre lot"

#: L'ensemble EXACT, dans l'ordre de la maquette (AC 10.2).
SUITES = (SUITE_DOSSIER, SUITE_FICHIER, SUITE_AUTRE_LOT)

#: Les deux volets symetriques : ce qu'on dit si une suite d'ouverture etait
#: proposee alors qu'aucun chemin n'est connu. :func:`suites_du_resultat` ne
#: les propose pas dans ce cas ; ces phrases tiennent si un jour elle le
#: faisait -- meme geste que `AUCUN_LOT_A_OUVRIR` cote Extraction.
AUCUN_DOSSIER_A_OUVRIR = "Aucun master écrit : il n'y a aucun dossier à ouvrir."
AUCUN_FICHIER_A_OUVRIR = "Aucun master écrit : il n'y a aucun fichier à ouvrir."


# ---------------------------------------------------------------------------
# La mesure du disque -- le seul chiffre que le coeur ne rend pas
# ---------------------------------------------------------------------------

def octets_du_master(chemin) -> int | None:
    """Le poids **mesure** du master, ou `None` quand il ne se mesure pas.

    **Toute panne de lecture rend `None` plutot que de lever** -- meme garde
    que `atelier_extraction_ecriture._octets_du_dossier`, et pour la meme
    raison : une trace Python nue devant l'operateur au moment ou l'ecriture
    vient de REUSSIR serait la pire des reponses. `is_file()` repond faux sur
    un partage demonte, et `stat()` y leve.

    **`None` et non zero** : un master de zero octet n'existe pas, et
    l'ecrire ferait de l'absence de mesure un chiffre. La ligne disparait
    alors, ce qui est la regle de tout l'atelier.
    """
    if chemin is None:
        return None
    try:
        chemin = Path(chemin)
        if not chemin.is_file():
            return None
        return chemin.stat().st_size
    except OSError:
        return None


def texte_de_cadence_du_master(exacte: str, ascii_seul: bool = False) -> str | None:
    """`25/1` -> `25 fps`, `24000/1001` -> `23,976 fps`. `None` si ca ne se lit pas.

    La cadence que le coeur rend est une fraction **exacte**
    (`codec_profiles.exact_frame_rate`) : c'est ce qu'il faut pour ffmpeg, et
    ce n'est pas ce qu'on lit a l'ecran. L'ecriture decimale est celle du
    depot -- `cadences.texte_de_cadence`, la meme qui ecrit les cadences de
    `E2-2` et de `E4-2` --, jamais une seconde recette locale.

    Une valeur illisible rend `None` : sur un ecran de resultat, une cadence
    fausse serait pire qu'une cadence absente, et lever ferait tomber l'ecran
    apres une ecriture reussie.
    """
    if not exacte:
        return None
    try:
        valeur = Fraction(str(exacte))
    except (ValueError, ZeroDivisionError, TypeError):
        return None
    if valeur <= 0:
        return None
    return f"{cadences.texte_de_cadence(valeur, ascii_seul)} {UNITE_DE_CADENCE}"


def duree_lisible(secondes: float | None) -> str | None:
    """`1 min 04`, la grammaire de la section 8 du `DESIGN.md`.

    **Aucune seconde redaction** : `avancement.duree_lisible` porte deja cette
    grammaire, arrondi compris. `None` traverse en `None` -- la ligne est alors
    **omise**, jamais rendue `0 s`.
    """
    return None if secondes is None else avancement.duree_lisible(secondes)


# ---------------------------------------------------------------------------
# Le modele -- pur, sans `textual`, sans ecriture
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MasterEcrit:
    """Ce que la passe a ecrit et declare, tel que `E4-5` le montre.

    **Modele pur**, comme `panneau.py` et les modeles de `E4-2` et `E4-4` :
    aucune dependance a `textual`, aucune ecriture. C'est ce qui rend mesurable
    sans terminal l'appariement a risque de cet ecran -- la ligne rendue contre
    la valeur du coeur qu'elle decrit.

    **Chaque champ est facultatif, et son absence RETIRE sa ligne** : un
    segment que personne n'a mesure disparait plutot que de sortir a zero.
    C'est la regle de tout l'atelier, et elle vaut ici plus qu'ailleurs -- un
    zero sur cet ecran-ci serait une affirmation sur le disque.
    """

    #: Le nom du fichier master. **Jamais recompose** : c'est
    #: `Path(outcome.output_path).name`, donc ce qu'`io.naming` a decide.
    nom: str
    #: Le chemin complet du master, tel que le coeur l'a rendu. C'est lui que
    #: les deux suites d'ouverture remettent au bureau.
    chemin: Path | None = None
    #: `projet_demo/outputs/`, compose par la seule redaction de l'atelier
    #: (`atelier_exports_execution.dossier_de_sortie`).
    dossier: str = ""
    #: Le poids **reel**, mesure sur le fichier. Jamais un majorant.
    octets: int | None = None
    #: Les echantillons montes -- `outcome.frame_count`, qui compte la sequence
    #: **muxee** (`run_encode` recoit `plan.muxed_frame_paths`), pas les frames
    #: distinctes retenues. Les deux coincident sur un lot 25p et **doublent**
    #: sur un lot 12p5.
    echantillons: int | None = None
    #: La cadence exacte du coeur, `num/den`. Rendue par
    #: :func:`texte_de_cadence_du_master`.
    cadence: str = ""
    #: La duree du master, **donnee** et jamais derivee (voir la tete de
    #: module).
    duree_s: float | None = None
    #: Le timecode de depart emis, ou `None` -- le coeur s'abstient en le
    #: motivant, et une etiquette inventee designerait une autre image.
    timecode: str | None = None
    #: `persisted.state_written` : l'etat que la declaration au manifest a pose.
    etat_du_lot: str = ""
    #: La duree de la passe, **donnee** par le parcours qui l'a chronometree.
    duree_d_encodage_s: float | None = None
    #: Les constats du coeur, codes **verbatim**, dans l'ordre ou il les rend.
    constats: tuple[str, ...] = ()
    #: Le rapport de `verify_technical_metadata`, champ a champ, dans l'ordre
    #: du coeur -- jamais trie : trier serait un jugement sur ce qui compte.
    verification: Mapping[str, Any] | None = None
    #: Les frames **distinctes** retenues, pour la droite du bandeau.
    frames: int | None = None
    lot_id: str = ""

    # -- la lecture du coeur -------------------------------------------------

    @classmethod
    def du_master(cls, master: Any, *, mesure: Any = None,
                  duree_d_encodage_s: float | None = None) -> "MasterEcrit":
        """Depuis l'`encode_master.MasterDuLot` que le point d'entree rend.

        **Rien n'est recompose** : les deux objets que l'AC 10.1 nomme sont lus
        tels quels, et les deux seules valeurs qui n'en sortent pas sont dites
        pour ce qu'elles sont -- un `stat` du fichier pour le poids, et une
        `MesureDuMaster` pour la duree, celle-la meme que l'ecran de reglages a
        affichee.

        Le `lot_id` vient de `persisted`, pas du plan : c'est le lot que la
        declaration au manifest a **effectivement** vise.
        """
        resultat = master.resultat
        persisted = master.persisted
        outcome = resultat.outcome
        chemin = Path(outcome.output_path)
        return cls(
            nom=chemin.name,
            chemin=chemin,
            # Le dossier est **compose** par la redaction de `E4-4`, jamais
            # ecrit ici : deux redactions de « ou vivent les masters »
            # divergeraient entre l'execution et son resultat.
            dossier=dossier_de_sortie(resultat.plan.project_dir),
            octets=octets_du_master(chemin),
            echantillons=outcome.frame_count,
            cadence=outcome.frame_rate,
            duree_s=None if mesure is None else mesure.duree_s,
            timecode=outcome.timecode,
            etat_du_lot=persisted.state_written,
            duree_d_encodage_s=duree_d_encodage_s,
            constats=tuple(resultat.findings) + tuple(persisted.findings),
            verification=resultat.verification,
            # Les frames **distinctes** vivent sur le plan ; les echantillons
            # sur l'issue. Les confondre ferait dire « 63 f » au bandeau d'un
            # master qui porte 125 echantillons.
            frames=resultat.plan.frame_count,
            lot_id=persisted.lot_id,
        )

    # -- ce qui se rend ------------------------------------------------------

    @property
    def taille(self) -> str | None:
        """`1,4 Go`, rendu par la seule redaction du depot, ou `None`."""
        return None if self.octets is None else explorateur.taille_lisible(
            self.octets)

    @property
    def champs_verifies(self) -> tuple[str, ...]:
        """Les champs que `ffprobe` a confrontes, dans l'ordre du coeur."""
        return () if not self.verification else tuple(self.verification)

    def texte_de_la_duree(self, ascii_seul: bool = False) -> str | None:
        """`4 s 96 · 124 échantillons · 25 fps` -- les segments qui existent.

        Les trois sont independants : un master dont personne n'a donne la
        duree porte quand meme ses echantillons et sa cadence, et la ligne ne
        disparait que si les trois manquent.
        """
        segments = [texte_de_duree(self.duree_s)]
        if self.echantillons is not None:
            segments.append(f"{self.echantillons} {UNITE_DES_ECHANTILLONS}")
        segments.append(texte_de_cadence_du_master(self.cadence, ascii_seul))
        presents = [segment for segment in segments if segment]
        return SEPARATEUR.join(presents) if presents else None

    def texte_de_l_etat_du_lot(self) -> str | None:
        """`encode — déclaré au manifest`.

        L'etat est **lu** de `PersistedEncode`, jamais compare a un litteral :
        un vocabulaire d'etat recopie dans `tui/` est exactement ce que la
        frontiere du lot B4 interdit.
        """
        if not self.etat_du_lot:
            return None
        return f"{self.etat_du_lot}{SEPARATEUR}{MENTION_DECLARE}"

    def objet_du_bandeau(self, ascii_seul: bool = False) -> str:
        """`plan-04_25 · 124 f` -- la DROITE du bandeau.

        **Rendue par la redaction de `E4-4`**, et non recopiee : les deux
        ecrans travaillent le meme lot, et deux compositions du meme bandeau
        divergeraient au premier ajustement. Un cardinal inconnu rend le seul
        identifiant plutot qu'un `None f`.
        """
        if not self.lot_id:
            return ""
        if self.frames is None:
            return jetons.replier_ascii(self.lot_id) if ascii_seul else self.lot_id
        return PassageDeLEncodage(
            lot_id=self.lot_id, frames=self.frames).objet_du_bandeau(ascii_seul)


# ---------------------------------------------------------------------------
# Le cartouche, la ligne d'etat, le journal
# ---------------------------------------------------------------------------

def panneau_du_master(master: MasterEcrit, ascii_seul: bool = False) -> Panneau:
    """Le cartouche de `E4-5` : le master, puis ce qu'on en sait.

    **Aucun majorant** : `EcranResultat` leve a la construction sur un panneau
    qui en porte un (story 11.1, AC 8.2), et c'est juste -- le travail est
    fait, les chiffres sont mesures. C'est aussi ce qui interdit de recycler
    ici le poids attendu de `E4-2` et `E4-3`.

    Chaque ligne dont la valeur manque est **omise**. L'ordre est celui de la
    maquette et il ne se derive pas des donnees : une ligne qui changerait de
    place selon ce qui est connu rendrait deux captures incomparables.
    """
    complet = jetons.glyphes(ascii_seul)["complete"]
    lignes = [LigneChiffree(f"{complet} {master.nom}", ""),
              LigneChiffree("", "")]
    for libelle, valeur in (
            (LIBELLE_TAILLE, master.taille),
            (LIBELLE_DUREE, master.texte_de_la_duree(ascii_seul)),
            (LIBELLE_TIMECODE, master.timecode),
            (LIBELLE_EMPLACEMENT, master.dossier),
            (LIBELLE_ETAT_DU_LOT, master.texte_de_l_etat_du_lot()),
            (LIBELLE_DUREE_D_ENCODAGE,
             duree_lisible(master.duree_d_encodage_s))):
        if valeur:
            lignes.append(LigneChiffree(libelle, valeur))
    return Panneau(TITRE_DU_CARTOUCHE, lignes)


def ligne_d_etat(master: MasterEcrit, ascii_seul: bool = False) -> str:
    """`● 1,4 Go écrits · métadonnées vérifiées par ffprobe · aucun refus`.

    Une **mesure**, jamais une touche, jamais un motif de conception, jamais un
    conseil d'usage (`EPIC11-ARB-56`). Les trois segments sont conditionnels :

    * le poids ne s'ecrit que s'il a ete mesure ;
    * la verification ne s'annonce que si un rapport existe -- annoncer
      `ffprobe` sur zero champ confronte serait une promesse, pas un fait ;
    * `aucun refus` cede la place aux **constats** du coeur des qu'il y en a.
      Les taire ferait de cette ligne une mesure fausse par omission, et les
      traduire serait un jugement que le coeur ne porte pas.
    """
    segments = []
    taille = master.taille
    if taille is not None:
        segments.append(MOTIF_DU_POIDS_ECRIT.format(taille=taille))
    if master.champs_verifies:
        segments.append(MENTION_VERIFIEE)
    if master.constats:
        segments.append(MOTIF_DES_CONSTATS.format(
            codes=SEPARATEUR_DES_CONSTATS.join(master.constats)))
    else:
        segments.append(AUCUN_REFUS)
    return jetons.marque("complete", SEPARATEUR.join(segments), ascii_seul)


def journal_de_la_verification(master: MasterEcrit):
    """Ce qu'il y a a lire APRES : le rapport `ffprobe`, champ a champ.

    `EPIC11-ARB-189` -- le journal **reste en memoire**, montre puis perdu :
    l'ecran ne promet aucun fichier de journal, et la ligne de raccourcis ne
    nomme qu'une lecture. C'est ce qui distingue cet ecran de `E4-4`, ou
    annoncer `Tab journal` aurait ouvert une page vide parce que le chemin
    d'encodage n'ecrit rien entre le recapitulatif et le rapport.

    Rend `None` quand il n'y a **rien** a lire : `EcranResultat` n'annonce
    alors pas `Tab journal` et ne le traite pas -- sa ligne de raccourcis est
    contextuelle, et une touche annoncee qui ne fait rien se lit comme une
    panne.
    """
    lignes = [MOTIF_DU_CHAMP_VERIFIE.format(champ=champ,
                                            valeur=_valeur_verifiee(entree))
              for champ, entree in (master.verification or {}).items()]
    lignes += [MOTIF_DU_CONSTAT.format(code=code) for code in master.constats]
    if not lignes:
        return None
    journal = avancement.Journal(plafond=max(len(lignes),
                                            avancement.LIGNES_DE_JOURNAL))
    for ligne in lignes:
        journal.inscrire(ligne)
    return journal


def _valeur_verifiee(entree: Any) -> Any:
    """Ce que le rapport dit avoir **trouve** sur le fichier.

    Le rapport de `verify_technical_metadata` est un dictionnaire par champ
    (`ok`, `expected`, `actual`) ; c'est `actual` qui decrit le fichier ecrit,
    donc ce que cet ecran-ci a le droit d'affirmer. Un rapport d'une autre
    forme traverse tel quel plutot que de faire lever un ecran de resultat.
    """
    if isinstance(entree, Mapping) and "actual" in entree:
        return entree["actual"]
    return entree


# ---------------------------------------------------------------------------
# Les suites, et ce que chacune fait REELLEMENT
# ---------------------------------------------------------------------------

def suites_du_resultat(master: MasterEcrit) -> list[str]:
    """Les suites de `E4-5`, et **chacune mene quelque part**.

    Les deux ouvertures ne sont proposees que si un chemin de master est connu :
    offrir « Ouvrir le fichier » sans fichier serait l'invite muette
    qu'`EPIC11-ARB-89` interdit. `Retour aux ateliers` est ajoutee d'office par
    `EcranResultat`, en dernier.
    """
    suites = [SUITE_DOSSIER, SUITE_FICHIER] if master.chemin is not None else []
    suites.append(SUITE_AUTRE_LOT)
    return suites


def ouvrir_le_dossier_du_master(app, master: MasterEcrit) -> str:
    """Remettre le dossier du master a l'explorateur du systeme (AC 10.2).

    **Le resultat est DIT, dans les deux cas** -- un echec silencieux serait
    indistinguable de la suite decorative que le finding `K3` a payee -- et
    **l'ecran ne change pas** : le compte rendu reste lisible au moment ou
    l'operateur va le comparer au contenu du dossier.
    """
    fait = (AUCUN_DOSSIER_A_OUVRIR if master.chemin is None
            else ouvrir_dans_l_explorateur_du_systeme(master.chemin.parent))
    return _dire(app, fait)


def ouvrir_le_fichier_du_master(app, master: MasterEcrit) -> str:
    """Remettre le master a la visionneuse du systeme (`EPIC11-ARB-42`).

    C'est le **meme** unique lancement de processus que l'ouverture du dossier
    (`execution._remettre_au_bureau`) : ce module n'en ouvre pas un second, et
    la frontiere de `test_coeur_en_processus.py` compte ce site-la.
    """
    fait = (AUCUN_FICHIER_A_OUVRIR if master.chemin is None
            else ouvrir_dans_la_visionneuse_du_systeme(master.chemin))
    return _dire(app, fait)


def _dire(app, fait: str) -> str:
    """Poser le fait en ligne d'etat, replie si l'application l'est."""
    if getattr(app, "ascii_seul", False):
        fait = jetons.replier_ascii(fait)
    app.palier_courant.poser_etat(fait)
    return fait


def remonter_a_l_ouverture_de_l_atelier(app) -> None:
    """Depiler jusqu'a la page d'ouverture de l'atelier Exports.

    **On depile les PASSAGES**, comme cote Extraction : `EPIC11-ARB-28` dit
    que « Extraction et Exports n'ont pas » de menu d'atelier. Le premier
    palier non transitoire rencontre est rendu sans que cette fonction ait a
    connaitre sa classe : elle ne l'importe pas.

    **CORRIGE le 2026-09-03, par la mesure du lot de cablage (B5).** Ces
    lignes affirmaient que cet atelier « n'a qu'une seule station sous ses
    passages -- `E4-1` ». C'est faux : `EcranReglagesDeL_encodage` (`E4-2`)
    est **lui aussi** `TRANSITOIRE = False`, et c'est voulu -- « une station
    du parcours : on y revient depuis la confirmation ». Un depilement par
    passages s'arrete donc sur les **reglages** du lot qu'on vient d'encoder,
    pas sur la liste des lots. `ParcoursExports` cable donc `Encoder un autre
    lot` sur une remontee visant la **classe** `EcranDesLotsAEncoder`, comme
    `atelier_pdf_parcours` le fait pour son menu, et n'appelle pas cette
    fonction-ci. Elle reste employee par son propre banc.

    **On ne remonte pas plus haut** (`EPIC11-ARB-13`, verbatim : « la fin d'une
    execution ramene au menu des ateliers du projet ouvert [...], jamais a
    l'ecran projet ») : cette suite-ci s'arrete un cran EN DESSOUS du menu,
    dans l'atelier ou l'operateur travaille -- c'est le retour, et lui seul,
    qui remonte au menu.
    """
    while app.passages_empiles and len(app.screen_stack) > 1:
        app.pop_screen()


def suivre(app, master: MasterEcrit, suite: str) -> None:
    """Ce que `E4-5` fait d'une suite choisie. **Aucune n'est muette.**

    Quatre destinations, et la derniere est le filet :

    * :data:`SUITE_DOSSIER` et :data:`SUITE_FICHIER` remettent l'un et l'autre
      au bureau, et **disent** ce qui s'est passe -- y compris qu'aucun bureau
      n'est joignable ici, ce qui est le cas d'un conteneur sans affichage
      (tolerance nommee d'`EPIC11-ARB-85`). **La TUI ne se quitte pas** ;
    * :data:`SUITE_AUTRE_LOT` remonte a la page d'ouverture de l'atelier ;
    * tout libelle inconnu mene a l'ecran qui **NOMME** l'absence. C'est la
      cinquieme consigne du lot `K3` : « une suite sans destination doit le
      DIRE, pas ne rien faire », et le filet est ce qui empeche qu'une suite
      ajoutee demain redevienne decorative en silence.

    **Ce que cette fonction ne fait jamais** : rien ecrire, rien effacer, rien
    reencoder. Une suite est une navigation ; l'ecriture est finie quand `E4-5`
    monte.
    """
    if suite == SUITE_DOSSIER:
        ouvrir_le_dossier_du_master(app, master)
        return
    if suite == SUITE_FICHIER:
        ouvrir_le_fichier_du_master(app, master)
        return
    if suite == SUITE_AUTRE_LOT:
        remonter_a_l_ouverture_de_l_atelier(app)
        return
    app.descendre(EcranPasEncore(suite, app.QUAND_ARRIVENT_LES_ATELIERS))


# ---------------------------------------------------------------------------
# `E4-5` -- l'ecran
# ---------------------------------------------------------------------------

class EcranResultatDuMaster(EcranResultat):
    """`E4-5` -- ce qui a ete ecrit, et les quatre suites.

    **Elle sous-classe `EcranResultat` et ne lui reprend rien** : son clavier
    (`↑↓`, `⏎`, `Tab`, `Échap`), l'ajout du retour en dernier, sa ligne de
    raccourcis contextuelle et le passage par `EcranPasEncore` sont exactement
    ce que cet ecran demande, et la maquette porte **mot pour mot** la ligne
    que cet ecran-la annonce quand un journal lui est passe
    (`RACCOURCIS_RESULTAT_AVEC_JOURNAL`). Ce qui est substitue est donc le
    strict minimum : le titre de l'atelier au bandeau, et l'objet travaille.

    Le sous-classement est aussi ce qui garde `execution.py` **intact** -- la
    story ne le modifie pas, ce module est partage par les quatre ateliers.
    """

    titre = projet_lecture.EXPORTS

    def __init__(self, master: MasterEcrit, suites: Sequence[str] | None = None,
                 sur_suite: Callable[[str], None] | None = None,
                 journal=None) -> None:
        super().__init__(
            panneau_du_master(master),
            list(suites if suites is not None else suites_du_resultat(master)),
            sur_suite=sur_suite,
            journal=journal_de_la_verification(master) if journal is None
            else journal)
        self.master = master

    def objet_du_bandeau(self) -> str:
        """Le lot travaille, **rendu au moment de dessiner**.

        Le mode ASCII est celui de l'application a cet instant : le composer a
        la construction figerait le bandeau dans le mode d'alors.

        `_application_montee` et non `self.app` : `textual` fait de `app` une
        propriete qui **leve** hors montage, et les bancs construisent les
        ecrans a nu.
        """
        application = _application_montee(self)
        return self.master.objet_du_bandeau(
            bool(getattr(application, "ascii_seul", False)))

    def etat(self) -> str:
        application = _application_montee(self)
        return ligne_d_etat(self.master,
                            bool(getattr(application, "ascii_seul", False)))


def ouvrir_le_resultat(app, master: MasterEcrit, *,
                       sur_suite: Callable[[str], None]
                       ) -> EcranResultatDuMaster:
    """Monter `E4-5`. `sur_suite` est **requis**.

    Requis, et non `None` par defaut : c'est le finding `K3`, ou quatre suites
    d'un ecran de resultat etaient navigables et **decoratives** parce qu'un
    point d'appel avait oublie de les passer, sans que rien ne le dise. Un
    defaut a `None` rendrait le meme oubli silencieux ici.
    """
    ecran = EcranResultatDuMaster(master, sur_suite=sur_suite)
    app.descendre(ecran)
    # Le mode est lu sur l'application **passee**, pas sur `ecran.app` :
    # `push_screen` est differe, donc l'ecran n'est pas encore monte ici. C'est
    # le geste des trois autres ateliers, et il vaut pour le meme motif.
    ecran.poser_etat(ligne_d_etat(master, getattr(app, "ascii_seul", False)))
    return ecran


__all__ = [
    "AUCUN_DOSSIER_A_OUVRIR",
    "AUCUN_FICHIER_A_OUVRIR",
    "AUCUN_REFUS",
    "EcranResultatDuMaster",
    "LIBELLE_DUREE",
    "LIBELLE_DUREE_D_ENCODAGE",
    "LIBELLE_EMPLACEMENT",
    "LIBELLE_ETAT_DU_LOT",
    "LIBELLE_TAILLE",
    "LIBELLE_TIMECODE",
    "MENTION_DECLARE",
    "MENTION_VERIFIEE",
    "MOTIF_DES_CONSTATS",
    "MOTIF_DU_CHAMP_VERIFIE",
    "MOTIF_DU_CONSTAT",
    "MOTIF_DU_POIDS_ECRIT",
    "MasterEcrit",
    "SUITES",
    "SUITE_AUTRE_LOT",
    "SUITE_DOSSIER",
    "SUITE_FICHIER",
    "TITRE_DU_CARTOUCHE",
    "UNITE_DE_CADENCE",
    "duree_lisible",
    "journal_de_la_verification",
    "ligne_d_etat",
    "octets_du_master",
    "ouvrir_le_dossier_du_master",
    "ouvrir_le_fichier_du_master",
    "ouvrir_le_resultat",
    "panneau_du_master",
    "remonter_a_l_ouverture_de_l_atelier",
    "suites_du_resultat",
    "suivre",
    "texte_de_cadence_du_master",
]
