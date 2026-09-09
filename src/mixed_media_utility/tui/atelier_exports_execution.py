# -*- coding: utf-8 -*-
"""`E4-4` / `E4-4b` et `T6-1` -- l'encodage en cours (story 11.8, lot F, AC 9).

**Cet ecran ne compte pas, parce que le coeur ne compte pas.** C'est la mesure
qui commande tout ce module, et elle est refaite ici plutot que citee :
`codec_profiles.run_encode` fait **un seul** `subprocess.run` bloquant, et
l'argv construit par `build_encode_command` ne porte **aucun** `-progress`.
Entre le recapitulatif emis AVANT (`encode.render_summary`) et le rapport
`ffprobe` emis APRES, le chemin d'encodage n'ecrit rien -- ni ligne, ni jalon,
ni cardinal.

La maquette d'origine montrait pourtant « ▓▓▓ 64 % · 79/124 frames · reste
~ 22 s » et cinq lignes de journal par frame : **aucun de ces chiffres
n'existait**, ils etaient fabriques. C'est ce constat qui a fait naitre
`EPIC11-ARB-184`, quatrieme issue ecrite par Egan contre les trois qui lui
etaient proposees, verbatim :

> « Livrer avec un rotor mais preparer une story de progression dans l'epic
> approprie qui pourra etre lancee en parallele et recablee en temps voulu.
> Preparer le terrain pour cette jonction tout en livrant un atelier
> fonctionnel en l'etat. »

Trois consequences, et ce module les porte toutes les trois :

1. **le rotor, et rien qui pretende compter** (AC 9.1). Le glyphe est
   `jetons.ROTOR` / `jetons.rotor()`, jamais un caractere ecrit en dur, et il
   a son repli ASCII dans `jetons.REPLIS_DE_TEXTE` comme les quatre autres
   signes hors table de cet ecran ;
2. **aucun pourcentage, aucun `n/N`, aucune estimation de temps restant**
   (AC 9.2). L'interdit n'est pas une promesse de prose : il est **structurel**
   -- un chiffre d'avancement ne peut apparaitre que si le coeur a emis un
   jalon, et il n'en emet aucun. Le banc le mesure dans les deux sens ;
3. **la jonction se prepare, et c'est le seul cout paye aujourd'hui.**
   :func:`raccord_de_progression` compose le mot-cle de progression **a partir
   de la signature du point d'entree de coeur**, pas d'une liste ecrite ici :
   il rend `{}` tant que `encode_master.encoder_le_master_du_lot` n'accepte
   aucun `rappel_progression`, et le mot-cle **le jour ou il l'acceptera**,
   sans qu'une ligne de `tui/` change. C'est ce que l'AC de frontiere de la
   story 6.7 mesurera de son cote (« son diff de raccordement ne touche aucun
   fichier de `tui/` ») ; ce module la rend vraie d'avance.

**L'AC 9.3 EST TOMBEE**, et il faut le dire plutot que le taire : elle
conditionnait une barre chiffree sur la pre-verification au lot `B3`, et
`EPIC11-ARB-184` a sorti ce lot du perimetre -- il est devenu la story 6.7,
developpee ailleurs et en parallele. Aucune phase de cet ecran ne porte de
barre, y compris la pre-verification, qui est pourtant la seule des quatre a
boucler sur un cardinal connu.

**Le journal part avec les chiffres, et pour la meme mesure** (`EPIC11-ARB-189`).
`run_encode` capture la sortie de ffmpeg puis la **jette en cas de succes** ;
seuls 600 caracteres survivent, dans le message d'erreur d'un echec. Il n'y a
donc rien a montrer PENDANT, et annoncer `Tab journal` ouvrirait une page vide.
C'est aussi pourquoi cet ecran n'est **pas** une sous-classe
d'`execution.EcranExecution` : celui-la porte une barre, un journal et
`Tab journal`, c'est-a-dire les trois choses que la mesure retire d'ici. Le
sous-classer pour en desactiver les trois quarts aurait laisse ses promesses
dans la ligne de raccourcis -- meme raisonnement, et meme geste, que
`atelier_pdf_calibration.EcranMireEnCours`.

**La ligne d'etat a PERDU sa tuyauterie** (`EPIC11-ARB-189`, Egan : « On enleve
cette information de tuyauterie »). Elle disait « aucun compte n'est emis »,
ce qui etait vrai et parlait de la MACHINE la ou cette ligne porte une mesure
du TRAVAIL. Ce qui la remplace est le seul compte reellement disponible -- les
echantillons a monter et le poids attendu --, precede de la mention d'etape.

**Ce que cet ecran ne peut PAS savoir aujourd'hui, dit plutot que tu.** Les
quatre etapes vivent **a l'interieur d'un seul appel opaque** : la
pre-verification et l'encodage sont dans `run_encode`, la verification et la
bascule dans `encode.execute_plan`, et aucune frontiere entre elles n'est
observable depuis la TUI. L'etape courante est donc **donnee** a cet ecran, et
jamais devinee par lui : ce module rend ce qu'on lui dit, il ne se raconte pas
une progression. Le jour ou la story 6.7 emet ses jalons, c'est
:meth:`PassageDeLEncodage.avancer_a` que le raccord appellera -- et elle
existe deja.

Ce module n'importe jamais `cli` (`EPIC11-ARB-67`), et il n'ecrit rien : le
point d'entree de coeur est `encode_master.encoder_le_master_du_lot`, appele
par le parcours de l'atelier.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from .. import encode_master
from ..io import project_layout
from . import explorateur, jetons, projet_lecture
from .atelier_exports_reglages import MesureDuMaster, SEPARATEUR
from .atelier_extraction import (Composition, _application_montee,
                                 ligne_de_titre)
from .coque import EcranPasEncore, ObjetTravaille, Palier
from .execution import EcranInterruption, bloc_peint
from .panneau import Issue, LigneChiffree, Panneau

# ---------------------------------------------------------------------------
# Les quatre etapes -- elles sont celles du COEUR, pas une mise en scene
# ---------------------------------------------------------------------------

#: Les cles des quatre etapes, dans l'ordre ou le coeur les traverse. Chacune
#: designe un geste **mesure** du chemin d'encodage, et non un decoupage
#: d'ecran :
#:
#: * `preverification` -- `codec_profiles.ensure_uniform_frame_shapes` puis
#:   `ensure_frame_order`, appelees par `run_encode` avant tout octet ;
#: * `encodage` -- l'unique `subprocess.run` de `run_encode` ;
#: * `verification` -- `video_metadata.verify_technical_metadata`, appelee par
#:   `encode.execute_plan` sur le fichier d'attente ;
#: * `bascule` -- l'`os.replace` final d'`execute_plan`, qui pose le master a
#:   son emplacement. Egan, sur la planche : « l'etape 4 n'a pas de temps de
#:   chargement ».
ETAPE_PREVERIFICATION = "preverification"
ETAPE_ENCODAGE = "encodage"
ETAPE_VERIFICATION = "verification"
ETAPE_BASCULE = "bascule"


@dataclass(frozen=True)
class EtapeDeLEncodage:
    """Une etape de la passe : son libelle, son titre d'ecran, son constat.

    **Elle ne porte aucun compte, et c'est le point de l'AC 9.2.** Un champ
    d'avancement ici aurait rendu le mensonge exprimable ; son absence le rend
    impossible plutot qu'improbable.
    """

    #: La cle, comparee par le passage. Jamais affichee.
    cle: str
    #: La premiere colonne de la ligne d'etape.
    libelle: str
    #: Le titre de la zone centrale **quand cette etape est en cours**.
    titre: str
    #: Ce que la ligne d'etat dit de cette etape, en une phrase. Les deux
    #: premieres sont verbatim des maquettes validees ; les deux autres suivent
    #: leur forme -- un geste, pas une phrase de commentaire -- parce que
    #: `E4-4` et `E4-4b` ne dessinent que les deux premieres et qu'inventer une
    #: tournure la ou le dessin se tait serait la seule autre issue.
    constat: str


#: Le motif de la deuxieme colonne de la pre-verification, **avant** qu'elle
#: aboutisse : ce qu'il y a a ouvrir.
DETAIL_A_OUVRIR = "{frames} frames à ouvrir"

#: Le meme, **une fois l'etape faite**. Les deux cardinaux sortent du **meme**
#: champ, et c'est deliberement une seule substitution : une etape declaree
#: conforme a ouvert tout ce qu'elle avait a ouvrir, par definition, et deux
#: nombres independants pourraient diverger sans que rien ne le dise.
DETAIL_OUVERTES = "{frames} frames sur {frames}"

#: La deuxieme colonne de la verification, verbatim des maquettes.
DETAIL_DE_LA_VERIFICATION = "ffprobe sur le fichier écrit"

#: Celle de la bascule. Le dossier est **compose** du projet et du nom de
#: dossier que `io.project_layout` porte, jamais ecrit en litteral.
DETAIL_DE_LA_BASCULE = "vers {dossier}"

#: Les trois mentions de la colonne de droite, verbatim des maquettes.
MENTION_EN_ATTENTE = "en attente"
MENTION_EN_COURS = "en cours"
#: **Les maquettes ne fixent que la pre-verification faite.** Employer un
#: second mot pour les trois autres etapes serait inventer la ou le dessin se
#: tait ; celui-ci dit vrai de chacune -- l'etape a rendu ce qu'elle devait
#: rendre -- et il n'y en a qu'un a maintenir.
MENTION_FAITE = "conforme"

#: Les quatre etapes, dans l'ordre. **Le titre et le constat des deux
#: premieres sont verbatim de `E4-4b` et `E4-4`** ; ceux des deux dernieres
#: suivent leur forme, aucune maquette ne les dessinant.
ETAPES: tuple[EtapeDeLEncodage, ...] = (
    EtapeDeLEncodage(ETAPE_PREVERIFICATION, "Pré-vérification",
                     "Pré-vérification des frames",
                     "lecture des {frames} frames"),
    EtapeDeLEncodage(ETAPE_ENCODAGE, "Encodage", "Encodage en cours",
                     "encodage des {echantillons} échantillons"),
    EtapeDeLEncodage(ETAPE_VERIFICATION, "Vérification",
                     "Vérification du master",
                     "vérification des métadonnées écrites"),
    EtapeDeLEncodage(ETAPE_BASCULE, "Bascule", "Bascule du master",
                     "bascule vers {dossier}"),
)

#: Le segment de poids de la ligne d'etat, verbatim de `E4-4`. Il **disparait**
#: quand personne n'a mesure le poids : un majorant inconnu ne s'ecrit pas
#: `0 Go`, meme regle que la ligne d'etat de `E4-2`.
MOTIF_DU_POIDS = "env. {poids} attendus"

#: La mention d'etape, en tete de la ligne d'etat. **Ce n'est pas un compte
#: d'avancement** : c'est un fait sur ou l'on en est, connu exactement, et
#: c'est la place ou la barre de la story 6.7 viendra se poser sans qu'aucune
#: autre ligne bouge (Egan, planche du 2026-09-03 : « pendant la
#: preverification la barre progresse de 0 a 100 avec la mention etape 1
#: au-dessus »).
MOTIF_DE_L_ETAPE = "Étape {rang} sur {total}"

#: La ligne de raccourcis de `E4-4` et `E4-4b`. **Pas de `Tab journal`** : il
#: n'y a rien a lire pendant, et annoncer une touche qui ouvrirait une page
#: vide est la faute que ce module documente en tete. **Pas de `Q quitter`**
#: non plus (`EPIC11-ARB-140`). Elle est identique -- et le banc l'epingle par
#: egalite -- a `atelier_pdf_calibration.RACCOURCIS_MIRE_EN_COURS`, qui porte
#: la meme promesse sur le meme genre d'ecran.
#: MESURE: 26/26
RACCOURCIS_ENCODAGE_EN_COURS = "Échap interrompre  F1 aide"

#: La periode du rotor, en secondes -- la meme que celle des deux autres ecrans
#: a rotor du depot. Quatre dessins : le cycle complet dure quatre fois cette
#: valeur.
PERIODE_DU_ROTOR = 0.25

# ---------------------------------------------------------------------------
# La grille des maquettes
# ---------------------------------------------------------------------------

#: Indentation des lignes d'etape.
_INDENT = 5
#: Colonne du libelle : le glyphe d'etat ouvre la sienne, puis un blanc.
_COLONNE_DU_LIBELLE = _INDENT + 2
#: Colonne du detail, **derivee du libelle le plus long** et jamais ecrite en
#: chiffre -- meme geste que la colonne des valeurs de `E4-2`.
_LARGEUR_DU_LIBELLE = max(jetons.colonnes(etape.libelle)
                          for etape in ETAPES) + 4
_COLONNE_DU_DETAIL = _COLONNE_DU_LIBELLE + _LARGEUR_DU_LIBELLE
#: Largeur du detail, mention d'etat a sa droite.
_LARGEUR_DU_DETAIL = 30


def _replie(texte: str, ascii_seul: bool = False) -> str:
    return jetons.replier_ascii(texte) if ascii_seul else texte


def _a_la_colonne(tete: str, colonne: int) -> str:
    """Completer ``tete`` de blancs jusqu'a ``colonne``, mesuree en COLONNES.

    Jamais `len()` : un ideogramme occupe deux colonnes, et toute la grille
    partirait avec lui.
    """
    return tete + " " * max(1, colonne - jetons.colonnes(tete))


def dossier_de_sortie(project_dir) -> str:
    """`projet_demo/outputs/` -- ou le master bascule, **compose** du coeur.

    Ni le nom du dossier de sorties ni la barre finale ne sont ecrits ici :
    `io.project_layout.OUTPUTS_DIRNAME` est la seule redaction du depot de « ou
    vivent les masters », et un ecran qui la recopierait cesserait de suivre le
    jour ou elle bouge.
    """
    return f"{Path(project_dir).name}/{project_layout.OUTPUTS_DIRNAME}/"


# ---------------------------------------------------------------------------
# Le modele -- pur, sans `textual`, sans ecriture
# ---------------------------------------------------------------------------

@dataclass
class PassageDeLEncodage:
    """Le modele de `E4-4` : quatre etapes, une seule en cours, aucun chiffre.

    **Modele pur**, comme `panneau.py` et le modele de `E4-2` : aucune
    dependance a `textual`, aucune ecriture. C'est ce qui rend mesurable sans
    terminal l'appariement a risque de cet ecran -- la ligne rendue contre
    l'etape qu'elle decrit -- et l'invariant qui le commande : **l'ensemble des
    etapes qui portent un chiffre d'avancement est vide**.

    **Rien de ce qu'il affiche n'est calcule ici** : le nom du master, le
    dossier de bascule, le cardinal de frames et les echantillons a monter
    sortent tous du plan d'encodage, par :meth:`du_plan`.
    """

    #: Le lot travaille : son identifiant et son cardinal de frames.
    lot_id: str
    frames: int
    #: Le nom du fichier master que le plan va ecrire. **Jamais recompose** :
    #: c'est `plan.output_path.name`, donc ce qu'`io.naming` a decide.
    nom_du_master: str = ""
    #: `projet_demo/outputs/`, compose par :func:`dossier_de_sortie`.
    dossier: str = ""
    #: Ce que le coeur a mesure du master a venir. Le **meme** type que celui
    #: de `E4-2` : deux redactions de « ce que le master pesera » divergeraient
    #: entre les reglages et l'execution, sur le meme plan.
    mesure: MesureDuMaster | None = None
    #: La cle de l'etape en cours. **Donnee, jamais devinee** -- voir la tete
    #: de module : les quatre etapes vivent dans un seul appel opaque.
    etape: str = ETAPE_PREVERIFICATION
    #: Le dernier jalon **emis par le coeur**, `(faites, total)`. `None` au
    #: socle du 2026-09-03, et il l'est toujours : rien ne l'emet. C'est la
    #: moitie « terrain prepare » d'`EPIC11-ARB-184` -- voir :meth:`noter`.
    jalon: tuple[int, int] | None = None
    #: Le pas du rotor. Il ne se remet **jamais** a zero : le modulo est fait
    #: par `jetons.rotor`, precisement pour qu'un ecran qui compte ses propres
    #: pas ne rende pas un `IndexError` au quatrieme tour.
    pas: int = 0
    #: L'operateur a-t-il demande l'interruption ? **Un fait d'ecran, pas une
    #: commande au coeur** : la demande est posee par `T6-1`, et cette ligne
    #: existe pour que `E4-4` puisse DIRE ce qui lui arrive au lieu de le taire.
    #: Voir :meth:`demander_l_interruption`.
    interruption_demandee: bool = False

    @classmethod
    def du_plan(cls, plan: Any) -> "PassageDeLEncodage":
        """Depuis l'`encode.EncodePlan` que le coeur a decide.

        **Les deux cardinaux sont DISTINCTS et le restent** : `frame_count`
        compte les frames retenues sur le disque -- ce que la pre-verification
        ouvre --, `muxed_frame_paths` compte les echantillons reellement mux
        -- ce que l'encodage monte. Ils coincident sur un lot 25p et **doublent**
        sur un lot 12p5 ne d'un rushe 25p, ou chaque frame est tenue deux fois.
        Les confondre ferait dire « encodage des 63 echantillons » sur un master
        qui en porte 125.
        """
        return cls(
            lot_id=plan.lot_id,
            frames=plan.frame_count,
            nom_du_master=plan.output_path.name,
            dossier=dossier_de_sortie(plan.project_dir),
            mesure=MesureDuMaster(echantillons=len(plan.muxed_frame_paths),
                                  poids_octets=plan.estimated_bytes),
        )

    # -- l'etape courante ----------------------------------------------------

    @property
    def rang(self) -> int:
        """Le rang **1-fonde** de l'etape en cours.

        Une cle inconnue vaut la premiere etape plutot que de lever : cet ecran
        est monte au-dessus d'une passe qui tourne, et un `ValueError` au
        milieu d'un encodage d'une heure serait la pire des reponses.
        """
        for rang, etape in enumerate(ETAPES, start=1):
            if etape.cle == self.etape:
                return rang
        return 1

    @property
    def etape_courante(self) -> EtapeDeLEncodage:
        return ETAPES[self.rang - 1]

    def avancer_a(self, cle: str) -> bool:
        """Poser l'etape en cours. **C'est la jonction de la story 6.7.**

        Elle est publique et mesurable aujourd'hui, appelee par le raccord
        demain : `EPIC11-ARB-184` demande que la forme du raccord soit payee
        maintenant, pas son contenu.
        """
        if cle == self.etape or all(etape.cle != cle for etape in ETAPES):
            return False
        self.etape = cle
        return True

    def noter(self, faites: int, total: int) -> None:
        """Le rappel de progression du depot, **cable d'avance et muet**.

        C'est la signature exacte qu'`EmetteurProgression` appelle et que cinq
        modules de coeur portent deja (`rappel_progression`). Elle **ne rend
        aucun chiffre a l'ecran**, et c'est l'AC 9.2 : au socle du 2026-09-03
        le coeur n'emet aucun jalon sur ce chemin, et afficher un compte que
        personne n'emet est le mensonge d'interface que cet ecran existe pour
        ne pas commettre.

        Ce qu'elle fait est le seul geste honnete disponible : **retenir** le
        jalon, pour que la story 6.7 n'ait rien a cabler dans `tui/`. Le banc
        mesure les deux moities -- le jalon est retenu, et le rendu reste sans
        chiffre.
        """
        self.jalon = (int(faites), int(total))

    def etapes_chiffrees(self) -> tuple[str, ...]:
        """Les etapes dont le RENDU porterait un compte d'avancement.

        Vide, et il l'est **par construction** : aucune ligne de cet ecran ne
        lit :attr:`jalon`. La methode existe pour que l'invariant se mesure par
        une egalite d'ensemble plutot que par une assertion positive -- « cette
        phase porte un rotor » est faible, « l'ensemble des phases qui portent
        un chiffre est exactement vide » mesure l'invariant ET son unicite.
        """
        return ()

    # -- ce que le coeur a mesure --------------------------------------------

    @property
    def echantillons(self) -> int | None:
        """Les echantillons a monter, ou `None` quand personne ne les a comptes."""
        return None if self.mesure is None else self.mesure.echantillons

    @property
    def poids(self) -> str | None:
        """`1,4 Go`, ou `None`. Rendu par la seule redaction du depot."""
        if self.mesure is None or self.mesure.poids_octets is None:
            return None
        return explorateur.taille_lisible(self.mesure.poids_octets)

    # -- rendu ---------------------------------------------------------------

    def glyphe_du_rotor(self, ascii_seul: bool = False) -> str:
        """Le dessin courant, **lu de `jetons`** et jamais recompose ici."""
        return jetons.rotor(self.pas, ascii_seul)

    def avancer_le_rotor(self) -> None:
        """Un pas de plus. C'est **tout** ce qui bouge sur cet ecran."""
        self.pas += 1

    def glyphe_de(self, etape: EtapeDeLEncodage, ascii_seul: bool = False) -> str:
        """`●` faite, le rotor en cours, `·` en attente."""
        glyphes = jetons.glyphes(ascii_seul)
        rang = ETAPES.index(etape) + 1
        if rang < self.rang:
            return glyphes["complete"]
        if rang == self.rang:
            return self.glyphe_du_rotor(ascii_seul)
        return glyphes["neutre"]

    def mention_de(self, etape: EtapeDeLEncodage) -> str:
        rang = ETAPES.index(etape) + 1
        if rang < self.rang:
            return MENTION_FAITE
        return MENTION_EN_COURS if rang == self.rang else MENTION_EN_ATTENTE

    def detail_de(self, etape: EtapeDeLEncodage) -> str:
        """La deuxieme colonne : ce que cette etape-la travaille.

        La pre-verification est la seule dont le detail **change** une fois
        l'etape faite -- elle passe de ce qu'il y a a ouvrir a ce qui a ete
        ouvert. Les trois autres nomment un objet qui ne bouge pas : le master
        vise, l'outil de verification, le dossier de bascule.
        """
        if etape.cle == ETAPE_PREVERIFICATION:
            motif = (DETAIL_OUVERTES if ETAPES.index(etape) + 1 < self.rang
                     else DETAIL_A_OUVRIR)
            return motif.format(frames=self.frames)
        if etape.cle == ETAPE_ENCODAGE:
            return self.nom_du_master
        if etape.cle == ETAPE_VERIFICATION:
            return DETAIL_DE_LA_VERIFICATION
        return DETAIL_DE_LA_BASCULE.format(dossier=self.dossier)

    def ligne_de_l_etape(self, etape: EtapeDeLEncodage,
                         ascii_seul: bool = False) -> str:
        """`● Pré-vérification    124 frames sur 124            conforme`."""
        tete = _a_la_colonne(
            " " * _INDENT + self.glyphe_de(etape, ascii_seul),
            _COLONNE_DU_LIBELLE)
        avec_libelle = _a_la_colonne(tete + _replie(etape.libelle, ascii_seul),
                                     _COLONNE_DU_DETAIL)
        avec_detail = _a_la_colonne(
            avec_libelle + _replie(self.detail_de(etape), ascii_seul),
            _COLONNE_DU_DETAIL + _LARGEUR_DU_DETAIL)
        return (avec_detail + _replie(self.mention_de(etape), ascii_seul)
                ).rstrip()

    def lignes_des_etapes(self, ascii_seul: bool = False) -> list[str]:
        return [self.ligne_de_l_etape(etape, ascii_seul) for etape in ETAPES]

    def titre(self, ascii_seul: bool = False) -> str:
        """Le titre de la zone centrale : celui de l'etape en cours."""
        return _replie(self.etape_courante.titre, ascii_seul)

    def constat(self, ascii_seul: bool = False) -> str:
        """Ce que la ligne d'etat dit de l'etape en cours, poids compris.

        **Un segment que personne n'a mesure DISPARAIT**, il ne sort pas a
        zero : c'est la meme regle que la ligne d'etat de `E4-2`, et elle vaut
        ici pour la meme raison -- « encodage des None echantillons » serait un
        chiffre invente par l'autre bout.
        """
        valeurs = {"frames": self.frames, "echantillons": self.echantillons,
                   "dossier": self.dossier}
        motif = self.etape_courante.constat
        if any(not valeur and "{" + nom + "}" in motif
               for nom, valeur in valeurs.items()):
            return ""
        segments = [motif.format(**valeurs)]
        if self.etape == ETAPE_ENCODAGE:
            poids = self.poids
            if poids is not None:
                segments.append(MOTIF_DU_POIDS.format(poids=poids))
        return _replie(SEPARATEUR.join(segments), ascii_seul)

    def demander_l_interruption(self) -> None:
        """Retenir que l'operateur a demande l'arret. **Elle n'arrete rien.**

        Le nom dit ce que ca fait : la demande est **retenue**, pas exaucee.
        `encoder_le_master_du_lot` n'offre aucun point de sortie -- en dessous,
        `codec_profiles` appelle `subprocess.run`, qui ne rend la main qu'a la
        fin --, donc une passe engagee va a son terme. Ce que cette ligne
        change est ce que l'ecran DIT, et c'est tout ce qu'il est honnete de
        changer sans toucher au coeur.
        """
        self.interruption_demandee = True

    def ligne_d_etat(self, ascii_seul: bool = False) -> str:
        """`Étape 2 sur 4 · encodage des 124 échantillons · env. 1,4 Go attendus`.

        Une **mesure**, jamais une touche ni un motif de conception
        (`EPIC11-ARB-56`). La tuyauterie qu'elle portait -- « aucun compte n'est
        emis » -- est partie avec `EPIC11-ARB-189` : elle parlait de la machine
        la ou cette ligne parle du travail.

        **Une interruption demandee la REMPLACE**, elle ne s'y ajoute pas
        (2026-09-06). Un operateur qui vient de choisir « Interrompre » n'a
        qu'une question, et ce n'est plus l'etape courante : est-ce que ca
        s'arrete ? La reponse est non, et la taire derriere un `Étape 2 sur 4`
        inchange est exactement ce qui lui a fait ecrire « l'interruption ne
        donne rien ».
        """
        if self.interruption_demandee:
            return _replie(PHRASE_DE_L_INTERRUPTION_DEMANDEE, ascii_seul)
        etape = MOTIF_DE_L_ETAPE.format(rang=self.rang, total=len(ETAPES))
        segments = [etape, self.constat(ascii_seul)]
        return _replie(SEPARATEUR.join(s for s in segments if s), ascii_seul)

    def objet_du_bandeau(self, ascii_seul: bool = False) -> str:
        """`plan-04_25 · 124 f` -- la DROITE du bandeau, composee du lot."""
        return _replie(f"{self.lot_id}{SEPARATEUR}{self.frames} f", ascii_seul)


# ---------------------------------------------------------------------------
# La JONCTION de la story 6.7 -- payee aujourd'hui, en forme et pas en contenu
# ---------------------------------------------------------------------------

#: Le nom du mot-cle de progression **du depot**. Cinq points d'entree de coeur
#: le portent deja -- `extraction.run_extraction`, `pdf_render.render_lot_pdf`,
#: `makepdf.generer_les_planches_du_lot`, `scan_detect.run_scan_detect`,
#: `scan_calibrate.calibrer_la_chaine` --, et c'est celui que la story 6.7
#: posera sur le chemin d'encodage. L'ecrire ici une fois est ce qui permet au
#: raccord de le reconnaitre le jour ou il apparait.
NOM_DU_RAPPEL_DE_PROGRESSION = "rappel_progression"


def le_coeur_sait_compter(point_d_entree: Callable[..., Any] | None = None) -> bool:
    """Le point d'entree de coeur accepte-t-il un rappel de progression ?

    **Mesure, jamais declaration.** La reponse est lue sur la signature de
    `encode_master.encoder_le_master_du_lot`, si bien qu'elle bascule toute
    seule le jour ou la story 6.7 y ajoute son mot-cle -- sans qu'une ligne de
    `tui/` change, ce qui est exactement l'AC de frontiere de cette story-la.

    Le parametre existe pour que le banc puisse poser la question a un double
    qui, lui, accepte le mot-cle : une frontiere qui ne saurait mesurer qu'un
    seul des deux etats serait verte sans rien prouver.
    """
    if point_d_entree is None:
        point_d_entree = encode_master.encoder_le_master_du_lot
    parametres = inspect.signature(point_d_entree).parameters
    return NOM_DU_RAPPEL_DE_PROGRESSION in parametres


def raccord_de_progression(passage: PassageDeLEncodage,
                           point_d_entree: Callable[..., Any] | None = None
                           ) -> dict[str, Callable[[int, int], None]]:
    """Le mot-cle de progression a passer au coeur, ou **rien** (AC 9.2).

    `{}` tant que le coeur n'accepte aucun rappel -- c'est-a-dire aujourd'hui,
    et c'est pour ca que l'atelier se livre au rotor. Le mot-cle **le jour ou
    il l'acceptera**, cable sur :meth:`PassageDeLEncodage.noter`.

    C'est la troisieme consequence d'`EPIC11-ARB-184`, et la seule qui coute
    quelque chose aujourd'hui : « l'atelier appelle le coeur par un point
    d'entree dont la forme accepte un rappel de progression le jour ou il
    existera, sans que le cablage de la TUI ait a changer ».
    """
    if not le_coeur_sait_compter(point_d_entree):
        return {}
    return {NOM_DU_RAPPEL_DE_PROGRESSION: passage.noter}


# ---------------------------------------------------------------------------
# `T6-1` -- interrompre un encodage, et ce qu'il laisse
# ---------------------------------------------------------------------------

#: La cle de l'issue qui arrete la passe.
CLE_INTERROMPRE = "interrompre"

#: Les **deux** issues de l'interruption d'un encodage, et pourquoi il n'y en a
#: pas trois.
#:
#: Les trois issues generiques d'`EcranInterruption` parlent d'ecriture --
#: « garder ce qui est deja ecrit », « effacer ce qui est deja ecrit » -- et
#: **aucune ne s'applique** ici : tant que cet ecran est a l'ecran, aucun master
#: n'est pose. C'est mesure et non suppose (AC 9.6) -- `encode.execute_plan`
#: encode vers un fichier d'attente, ne bascule qu'apres verification, et son
#: `finally` **retire la reservation** quand la bascule n'a pas eu lieu ; la
#: declaration au manifest, elle, vient apres le retour de l'appel. Proposer
#: d'effacer ce qu'on n'a pas ecrit serait un choix qui ment sur l'etat du
#: disque, exactement comme au temps 1 du Scan.
#:
#: Les invariants du choix exclusif l'acceptent : deux issues actionnables,
#: aucune preselectionnee, au moins une qui n'ecrit pas. **Ici aucune des deux
#: n'ecrit**, ce qui est plus fort que l'invariant, pas plus faible.
ISSUES_DE_L_INTERRUPTION = (
    Issue(CLE_INTERROMPRE, "Interrompre, aucun master ne sera écrit"),
    Issue(EcranInterruption.REPRENDRE, "Reprendre l'encodage"),
)

#: Le titre du cartouche de `T6-1`.
TITRE_DE_L_INTERRUPTION = "Déjà écrit"

#: Ce que `E4-4` dit **apres** que l'operateur a choisi « Interrompre ».
#:
#: **Elle dit non, et c'est le point.** Egan, terrain du 2026-09-06 : « Echap
#: pendant un rendu mene a l'ecran d'interruption mais l'interruption ne donne
#: rien. Oblige de quitter ». Le premier defaut etait le cul-de-sac -- l'ecran
#: d'interruption qui ne se depilait pas --, et il est ferme ailleurs. Celui-ci
#: est l'autre moitie : une fois `T6-1` depile, l'operateur retrouve un rotor
#: qui tourne, et rien ne lui dit pourquoi. Une phrase qui promettrait l'arret
#: serait pire que le silence.
#:
#: Le mot « engage » porte la seule nuance qui compte : une interruption
#: demandee AVANT que le coeur parte, elle, n'encode rien -- `ParcoursExports.
#: lancer` la consulte, c'est l'AC 9.6 --, et l'operateur ne voit alors jamais
#: cette phrase.
PHRASE_DE_L_INTERRUPTION_DEMANDEE = (
    "Interruption demandée : l'encodage engagé va jusqu'à son terme, "
    "il ne peut pas être arrêté en cours de route."
)

#: Les trois lignes du cartouche. La derniere est **l'invariant de la passe**,
#: dit a l'ecran plutot que suppose -- meme geste que la ligne « Frames
#: ecrites 0 » de l'interruption d'une detection.
LIBELLE_DE_L_ETAPE = "Étape atteinte"
LIBELLE_DES_ECHANTILLONS = "Échantillons à monter"
UNITE_DES_ECHANTILLONS = "échantillons"
LIBELLE_DES_MASTERS = "Masters écrits"
UNITE_DES_MASTERS = "masters"


class EcranInterruptionDeLEncodage(EcranInterruption):
    """`T6-1` de l'atelier Exports : deux issues, et `execution.py` intact.

    **On reutilise `EcranInterruption`** (AC 9.5) -- son clavier, son rendu,
    son `Echap` qui reprend au lieu de remonter, ses invariants de choix. Ce
    qui est substitue est exactement ce que l'encodage contredit, et rien de
    plus : la liste des issues, et le titre de l'atelier au bandeau. C'est le
    patron livre par `atelier_scan_detection.EcranInterruptionDeDetection` et
    repris par `atelier_scan_ecriture.EcranInterruptionDeLEcriture` ; ce module
    n'en invente pas un troisieme, et il ne touche pas a `execution.py`.
    """

    titre = projet_lecture.EXPORTS
    ISSUES = ISSUES_DE_L_INTERRUPTION


# ---------------------------------------------------------------------------
# `E4-4` / `E4-4b` -- l'ecran
# ---------------------------------------------------------------------------

#: Ce que l'interruption demande, quand l'ecran qui la sert n'existe pas encore.
#: Une touche annoncee qui ne fait rien et ne dit rien est indistinguable d'un
#: clavier casse : la garde structurelle des rappels
#: (`tests/unit/tui/test_rappels_cables.py`) existe pour attraper un
#: `if ... is not None` sans branche `else`.
CE_QUI_MANQUE_APRES_L_INTERRUPTION = "Interrompre l'encodage"
QUAND_LE_PARCOURS = "le parcours de l'atelier Exports"


#: Ou l'application retient l'ecran de la passe en cours. **Le nom est le meme
#: que celui d'`atelier_pdf_execution`, et deliberement** : les deux ateliers
#: n'ont jamais de passe simultanee -- la coque en heberge une a la fois -- et
#: deux attributs distincts feraient croire le contraire. C'est ce que le
#: demontage lit pour savoir si le drapeau qu'il rendrait est bien le sien.
ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE = "_ecran_de_la_passe"


class EcranEncodageEnCours(ObjetTravaille, Palier):
    """`E4-4` / `E4-4b` -- quatre etapes, un rotor, et aucun chiffre invente.

    **Ce n'est pas `execution.EcranExecution`**, et ce n'est pas un oubli : voir
    la tete de module. C'est **le meme ecran a deux instants**, et non deux
    ecrans : `E4-4b` est l'etat ou la pre-verification tourne, `E4-4` celui ou
    l'encodage tourne.
    """

    titre = projet_lecture.EXPORTS
    raccourcis = RACCOURCIS_ENCODAGE_EN_COURS

    #: Un passage : la duree d'une tache, pas une station.
    TRANSITOIRE = True

    ID_DU_CORPS = "corps-encodage-exports"

    def __init__(self, passage: PassageDeLEncodage,
                 sur_issue: Callable[[Issue], None] | None = None) -> None:
        super().__init__()
        self.passage = passage
        self._sur_issue = sur_issue
        #: Le minuteur du rotor, **retenu** et non oublie. Deux motifs, tous
        #: deux payes ailleurs : un minuteur qu'on ne tient pas continue de
        #: redessiner un arbre de widgets detruit ; et sans poignee, la seule
        #: facon de mesurer le rotor serait d'attendre que l'horloge le fasse
        #: tourner -- un banc qui attend mesure l'attente.
        self.minuteur = None

    # -- lecture --------------------------------------------------------------

    def composer(self, largeur: int, ascii_seul: bool = False
                 ) -> tuple[list[str], int | None, dict[int, str]]:
        """Le corps de `E4-4`, **sous la hauteur de la zone centrale**."""
        composition = Composition()
        composition.respirer()
        composition.poser(ligne_de_titre(self.passage.titre(ascii_seul),
                                         ascii_seul))
        composition.respirer()
        composition.poser(*self.passage.lignes_des_etapes(ascii_seul))
        return composition.rendu()

    def lignes(self) -> list[str]:
        return self.composer(self.app.size.width, self.app.ascii_seul)[0]

    def etat(self) -> str:
        return self.passage.ligne_d_etat(self.app.ascii_seul)

    def objet_du_bandeau(self) -> str:
        """Le lot travaille, **rendu au moment de dessiner**."""
        application = _application_montee(self)
        return self.passage.objet_du_bandeau(
            bool(getattr(application, "ascii_seul", False)))

    # -- rendu ----------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id=self.ID_DU_CORPS)
        return [Vertical(self._corps, id=f"centre-{self.ID_DU_CORPS}")]

    def on_mount(self) -> None:
        self.minuteur = self.set_interval(PERIODE_DU_ROTOR,
                                          self.avancer_le_rotor)
        self.rafraichir()

    def on_unmount(self) -> None:
        """Arreter le minuteur, et **rendre le drapeau de tache** s'il est a soi.

        Le minuteur : un ecran demonte n'a plus rien a faire tourner.

        Le drapeau : c'est le filet des chemins qui **depilent** au lieu de
        conclure. Le `finally` de `ParcoursExports.lancer` couvre la passe qui
        va au bout, refus compris ; il ne couvre pas un ecran retire avant que
        la passe ne parte. Sans ce filet, `Echap` cesserait de depiler et `q`
        de quitter pour la session entiere -- le defaut jumeau, deja paye par
        `atelier_scan_parcours.EcranCollisionDeLaPasse` : un fil de travail qui
        attend derriere un drapeau que plus personne ne rend.

        **L'extinction est CONDITIONNELLE**, et cette condition n'est pas une
        precaution : demonter l'ecran d'une passe FINIE alors que la suivante
        est deja partie ferait tomber le drapeau de la passe **neuve**. C'est
        l'ecart qu'`atelier_scan_calibrate` a impose au second tour, et
        `atelier_pdf_execution` porte la meme garde a `:910`.
        """
        if self.minuteur is not None:
            self.minuteur.stop()
            self.minuteur = None
        if getattr(self.app, ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE, None) is self:
            setattr(self.app, ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE, None)
            self.app.oublier_la_tache()

    def avancer_le_rotor(self) -> None:
        """Un pas, et on redessine. Appelable a la main : c'est ce qui rend le
        mouvement mesurable sans terminal et sans horloge."""
        self.passage.avancer_le_rotor()
        self.rafraichir()

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur = jetons.largeur_utile(self.app.size.width)
        lignes, _rang, _etats = self.composer(self.app.size.width,
                                              self.app.ascii_seul)
        self._corps.update(bloc_peint(lignes, largeur, self.app))
        self.poser_etat(self.etat())
        super().rafraichir()

    # -- clavier --------------------------------------------------------------

    def on_key(self, evenement) -> None:
        """`Echap` ouvre l'interruption ; il ne remonte pas.

        **Arrete ici**, comme sur `EcranExecution` : laisser l'application voir
        la touche depilerait l'encodage en cours, c'est-a-dire ferait
        disparaitre la tache de la vue au lieu de demander quoi en faire.
        """
        if evenement.key == "escape":
            evenement.stop()
            self.ouvrir_l_interruption()

    def ouvrir_l_interruption(self) -> EcranInterruptionDeLEncodage:
        """Monte `T6-1` PAR-DESSUS. **La passe continue derriere.**

        Ouvrir cet ecran n'arrete rien : c'est un empilement, pas une
        substitution. Le rappel n'est pas facultatif -- sans lui, les issues
        poseraient `issue_declenchee` et n'appelleraient personne, c'est-a-dire
        un cul-de-sac clavier.
        """
        ecran = EcranInterruptionDeLEncodage(
            self.panneau_de_ce_qui_est_ecrit(),
            sur_issue=self.issue_d_interruption)
        self.app.descendre(ecran)
        return ecran

    def issue_d_interruption(self, issue: Issue) -> None:
        """Ce que fait chacune des deux issues.

        « Reprendre » est de la **navigation**, entierement interne a l'ecran :
        elle depile ici. L'autre arrete un travail du coeur : elle va au
        parcours, qui seul sait ce qu'il a ouvert -- `ParcoursExports.interrompre`
        depuis le lot B5 (2026-09-03). Le repli reste pour l'ecran construit
        **a nu** par un banc, ou l'absence **ne se tait pas**.
        """
        if issue.cle == EcranInterruption.REPRENDRE:
            self.app.pop_screen()
            return
        if self._sur_issue is not None:
            self._sur_issue(issue)
            return
        self._pas_encore()

    def _pas_encore(self) -> None:
        application = _application_montee(self)
        if application is None:
            return
        application.descendre(
            EcranPasEncore(CE_QUI_MANQUE_APRES_L_INTERRUPTION,
                           QUAND_LE_PARCOURS))

    def panneau_de_ce_qui_est_ecrit(self) -> Panneau:
        """Le cartouche de `T6-1` : ce que la passe a fait, et ce qu'elle n'a
        pas fait.

        Le nom de la methode est celui du patron d'`EcranExecution` -- c'est son
        point d'appel dans les trois ateliers qui l'ont deja sous-classe -- mais
        son contenu ne peut pas l'etre : « Frames ecrites » serait faux sur les
        deux mots a la fois. La derniere ligne est **l'invariant de la passe**,
        dit a l'ecran plutot que suppose (AC 9.6).
        """
        echantillons = self.passage.echantillons
        lignes = [LigneChiffree(
            LIBELLE_DE_L_ETAPE,
            MOTIF_DE_L_ETAPE.format(rang=self.passage.rang,
                                    total=len(ETAPES)))]
        if echantillons is not None:
            lignes.append(LigneChiffree(LIBELLE_DES_ECHANTILLONS,
                                        echantillons, UNITE_DES_ECHANTILLONS))
        lignes.append(LigneChiffree(LIBELLE_DES_MASTERS, 0, UNITE_DES_MASTERS))
        return Panneau(TITRE_DE_L_INTERRUPTION, lignes)


__all__ = [
    "CE_QUI_MANQUE_APRES_L_INTERRUPTION",
    "CLE_INTERROMPRE",
    "DETAIL_A_OUVRIR",
    "DETAIL_DE_LA_BASCULE",
    "DETAIL_DE_LA_VERIFICATION",
    "DETAIL_OUVERTES",
    "ETAPES",
    "ETAPE_BASCULE",
    "ETAPE_ENCODAGE",
    "ETAPE_PREVERIFICATION",
    "ETAPE_VERIFICATION",
    "EcranEncodageEnCours",
    "EcranInterruptionDeLEncodage",
    "EtapeDeLEncodage",
    "ISSUES_DE_L_INTERRUPTION",
    "MENTION_EN_ATTENTE",
    "MENTION_EN_COURS",
    "MENTION_FAITE",
    "MOTIF_DE_L_ETAPE",
    "MOTIF_DU_POIDS",
    "NOM_DU_RAPPEL_DE_PROGRESSION",
    "PERIODE_DU_ROTOR",
    "PassageDeLEncodage",
    "QUAND_LE_PARCOURS",
    "RACCOURCIS_ENCODAGE_EN_COURS",
    "TITRE_DE_L_INTERRUPTION",
    "dossier_de_sortie",
    "le_coeur_sait_compter",
    "raccord_de_progression",
]
