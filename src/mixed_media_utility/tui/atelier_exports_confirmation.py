# -*- coding: utf-8 -*-
"""`E4-3` -- la confirmation de l'atelier Exports (story 11.8, lot E, AC 7).

**C'est le dernier ecran ou rien n'est ecrit sur le disque**, et la ligne
d'etat le dit : elle porte les chiffres de ce qui **va** s'ecrire, suivis de
« rien n'a encore été écrit ». `EPIC11-ARB-4`, verbatim : le panneau chiffre
« est **obligatoire pour toute commande qui ecrit**, et il porte au minimum :
ce qui sera produit (noms de fichiers ou de lots), en quelle quantite (frames,
pages), et ce que cela coute (espace disque, majorant assume comme tel) ».

Le cartouche est DERIVE de `encode.render_summary`, jamais reecrit (AC 7.1)
---------------------------------------------------------------------------
Chaque famille de valeur affichee ici est une famille que le coeur emet dans
son recapitulatif d'avant-ecriture : la sortie, le lot et son etat, le profil
et son conteneur, la resolution et la geometrie source, la cadence source
effective avec ses echantillons, les frames conformes et les mires, le
timecode de depart, le poids majorant. :func:`plan_du_master` les prend sur
l'`encode.EncodePlan` que `render_summary` lit lui-meme -- **le meme objet**,
donc aucune des deux redactions ne peut deriver de l'autre sans que le banc le
voie (`test_atelier_exports_confirmation.py`, famille « AC 7.1 »).

**Deux familles du dessin ne sont PAS dans `render_summary`, et elles sont
dites plutot que tues :**

* la **colorimetrie** (`bt709` sur la maquette) est portee par le PROFIL
  (`codec_profiles.PROFILES[...].colorspace`) : `render_summary` la cite bien,
  mais **noyee dans la prose** de sa note d'approximation sRVB, ou aucun
  decoupage ne la rendrait sans la reecrire. Elle est donc lue a sa source de
  coeur, comme l'ecran de reglages la lit deja -- et le banc verifie qu'elle
  reste **la meme** que celle du recapitulatif ;
* la **reconstruction** (`EPIC11-ARB-190`, « on n'encode pas un lot, on encode
  un lot RECONSTRUIT ») n'a **aucun** producteur de coeur au 2026-09-03 : le
  coeur qui la sert est la story 6.8, lancee en parallele. Elle est donc un
  champ **donne** et **facultatif** : absente, la ligne disparait plutot que
  d'afficher un rang invente. C'est un ecart entre la maquette validee et ce
  que le produit sait dire aujourd'hui, et il est signale, pas comble.

Ce que ce module ne fait pas, et c'est structurel
--------------------------------------------------
* il **n'ecrit rien** et ne touche a aucun fichier : c'est un point de
  jugement, et le banc le mesure aux inodes et au `st_mtime_ns` ;
* il **ne resout, ne calcule et ne consomme aucun rang** (AC 7.4, `EPIC11-ARB-92`
  et `EPIC11-ARB-108`). Le rang, quand il y en a un, a ete tranche par `E4-3b`
  et vit deja dans le nom que le plan porte. Une frontiere negative mesure que
  ce module ne nomme aucune des fonctions de rang du coeur ;
* il **n'ouvre aucun champ de saisie** (`EPIC11-ARB-141`) : le nom du master
  est **derive et montre**, jamais edite -- « On affiche le nom du master. Il
  n'est pas modifiable » (Egan, 2026-09-03). C'est par **absence** de champ,
  pas par une edition qui n'atteindrait pas le coeur : `encode_master.
  encoder_le_master_du_lot` n'a aucun parametre de nom, et l'AC 2.4 le mesure ;
* il **ne se cable pas lui-meme** : le parcours de l'atelier se monte en un
  seul endroit, au lot de cablage (B5).

L'ecart de grille, EPINGLE et non corrige
------------------------------------------
`panneau.LigneChiffree.rendu` cale le chiffre **a DROITE** de la largeur utile,
quand la maquette cale les valeurs **a gauche**, a une colonne fixe. C'est
« l'ecart de tous les `E*-3` du depot » que le lot F de la story 11.7 a deja
epingle sur `E5-3` : le corriger toucherait `panneau.py`, partage par les
quatre ateliers, et cette story ne le modifie pas. Le banc le **constate** au
lieu de le taire.

Ce module ne modifie ni `execution.py` ni `panneau.py`, et il n'importe jamais
`cli` (`EPIC11-ARB-67`).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import codec_profiles, encode
from ..io.project_layout import OUTPUTS_DIRNAME
from . import jetons, projet_lecture
from .atelier_extraction_ecriture import (LIBELLE_DESTINATION,
                                          PREFIXE_APPROCHE, TITRE_A_ECRIRE,
                                          taille_lisible)
from .execution import EcranChiffre
from .noms import ModeleNoms
from .panneau import RIEN_ECRIT, ChoixExclusif, Issue, LigneChiffree, Panneau

# ---------------------------------------------------------------------------
# Les textes de `E4-3`, verbatim de la maquette validee du 2026-09-03
# ---------------------------------------------------------------------------

#: Les libelles de la colonne de gauche du cartouche, dans l'ordre du dessin.
#: Constantes de module et non litteraux au point d'usage : c'est ce qui les
#: fait balayer par les gardes d'epic (repli ASCII, majuscules des raccourcis).
LIBELLE_MASTER = "Master"
LIBELLE_LOT = "Lot"
LIBELLE_RECONSTRUCTION = "Reconstruction"
LIBELLE_PROFIL = "Profil"
LIBELLE_RESOLUTION = "Résolution"
LIBELLE_CADENCE = "Cadence du rushe"
#: **Une seule ligne pour les deux comptes** (Egan, 2026-09-03 : « `Mires` est
#: redondant avec `frames` : si c'est complet on n'a pas de mires, si c'est
#: incomplet on a des mires. Lecture sur la meme ligne »). C'est du dessin,
#: pas un arbitrage -- les deux lignes disaient la meme chose deux fois.
LIBELLE_FRAMES = "Frames · mires"
LIBELLE_TIMECODE = "Timecode de départ"
LIBELLE_POIDS = "Poids attendu"
#: La ligne que le coeur n'ajoute que quand la cadence source declaree diverge
#: de celle du lot. `LIBELLE_DESTINATION` n'est **pas** redige ici : il est
#: importe de `atelier_extraction_ecriture`, ou il vit deja.
LIBELLE_NOTE_DE_CADENCE = "Cadence source"

#: L'unite de la cadence du master, **celle du coeur** : `render_summary`
#: ecrit `im/s`, et c'est le mot que l'operateur relit au journal de la passe.
#: Il differe de `fps`, l'unite du champ de saisie de `E4-2` -- deux ecrans,
#: deux libelles, tous deux verbatim de leur maquette validee.
UNITE_DE_CADENCE_DU_MASTER = "im/s"

#: Le separateur des mesures d'une meme ligne : `25 im/s · 124 échantillons`.
#:
#: **Il est redige ici plutot qu'importe**, et c'est un choix de dependance :
#: `atelier_pdf_confirmation` porte la meme constante, mais les deux modules
#: sont des ecrans de deux ateliers differents et rien ne doit les faire
#: dependre l'un de l'autre. `atelier_scan_confirmation` a tranche pareil.
SEPARATEUR = " · "

#: `prores_hq → .mov` -- le profil et son conteneur, tous deux LUS du coeur.
MOTIF_DU_PROFIL = "{profil} → .{conteneur}"

#: `1920 × 1080` -- la geometrie du master. Le `×` a son repli ASCII dans
#: `jetons.REPLIS_DE_TEXTE` ; sans lui `--ascii` en ferait un `?`.
MOTIF_DE_LA_GEOMETRIE = "{largeur} × {hauteur}"
#: `source 1920 × 1080` -- la geometrie de la matiere, telle que le coeur la
#: sonde. Elle reste affichee meme quand elle egale la geometrie de sortie :
#: c'est ce qui permet de voir qu'aucune mise a l'echelle n'a lieu.
MENTION_DE_LA_SOURCE = "source {geometrie}"

#: Ce que la cadence entraine, tel que le coeur le compte : les echantillons
#: reellement muxes (frames tenues comprises) et les frames distinctes.
MOTIF_DES_ECHANTILLONS = "{echantillons} échantillons"
MOTIF_DES_FRAMES = "{frames} frames"

#: `124 conformes sur 124` -- et sa forme quand le lot ne declare aucun
#: cardinal attendu. `render_summary` ecrit alors « cardinal inconnu » ; ici la
#: comparaison **disparait** plutot que de rendre un « sur 0 » qui serait faux.
MOTIF_DES_CONFORMES = "{frames} conformes sur {attendues}"
MOTIF_DES_CONFORMES_SANS_CARDINAL = "{frames} conformes"

#: Le pluriel des mires. Le pluriel suit le compte, jamais un `+ "s"` au hasard.
PLURIEL_DES_MIRES = {False: "mire", True: "mires"}

#: Les trois etats du jeton de completude (AC 5.2), **dans l'ordre ou l'AC les
#: pose** : `● complet` quand le compte trouve egale le compte attendu,
#: `▲ N mires` quand le lot porte des mires presentes, `✕ incomplet` sinon.
#: Le verdict est celui du coeur (`encode.CompletenessVerdict`), jamais un
#: second calcul ; seuls les mots sont d'ici.
ETAT_COMPLET = "complet"
ETAT_INCOMPLET = "incomplet"

#: Les cles des trois issues. Elles ne sont **jamais** affichees : le libelle
#: l'est. Une cle est ce par quoi un test et un ecran se designent la meme
#: issue sans recopier une chaine francaise.
ISSUE_ENCODER = "encoder"
ISSUE_MODIFIER = "modifier"
ISSUE_ANNULER = "annuler"

#: Les trois libelles, verbatim de la maquette `E4-3` (l. 17 a 19).
LIBELLE_ENCODER = "Encoder"
LIBELLE_MODIFIER = "Modifier les réglages"
LIBELLE_ANNULER = "Annuler"

#: La ligne de raccourcis de `E4-3`, verbatim de la maquette (l. 22).
#:
#: **Elle n'est PAS `execution.RACCOURCIS_CONFIRMATION`** (AC 7.5), et c'est le
#: seul point ou cet ecran s'ecarte de l'ecran partage : la constante commune
#: promet encore une touche `Tab` d'edition de nom, or `EPIC11-ARB-141` a retire
#: ce geste de cet atelier -- `encoder_le_master_du_lot` n'a aucun parametre de
#: nom. L'annoncer promettrait une touche qui ne fait rien.
#:
#: La formulation exacte de cette promesse ne se recopie pas ici : la frontiere
#: negative de l'AC 7.5 est un grep du TEXTE des modules de cet atelier, prose
#: comprise, et un commentaire qui la citerait la ferait rougir. Les deux issues etaient
#: de poser une ligne propre ou de corriger la constante partagee ; corriger la
#: constante toucherait `execution.py`, que cette story ne modifie pas. C'est
#: donc une ligne propre, et l'ecart sur la constante partagee reste ouvert --
#: `atelier_pdf_confirmation` l'a laisse ouvert pour la meme raison.
#:
#: **Le repli ASCII l'ALLONGE de cinq colonnes** (`Entree` pour `⏎`), et c'est
#: le regime qui commande le budget.
#: MESURE: 44/49
RACCOURCIS_EXPORTS_CONFIRMATION = "⏎ valider  ↑↓ choisir  Échap retour  F1 aide"

#: Ce que la ligne d'etat dit en fin de mesure, verbatim de la maquette `E4-3`
#: (l. 21 : « ... — rien n'a encore été écrit »).
#:
#: **Derivee de `panneau.RIEN_ECRIT`, jamais recopiee.** La phrase existe une
#: fois dans le depot ; ce qui change ici est sa place dans la ligne -- elle est
#: en queue d'une mesure, donc sans majuscule ni point final. Une seconde
#: redaction divergerait de la premiere au premier ajustement d'accent, et une
#: phrase desaccentuee a la source rendrait le repli ASCII indistinguable du
#: nominal.
QUEUE_RIEN_ECRIT = RIEN_ECRIT[0].lower() + RIEN_ECRIT[1:].rstrip(".")

#: Le lien entre la mesure et sa queue, verbatim de la maquette.
LIAISON_DE_LA_MESURE = " — "


class PlanDuMasterMalForme(ValueError):
    """Le plan viole un contrat que la revue ne devrait pas avoir a trouver."""


# ---------------------------------------------------------------------------
# Le plan : ce qui SERA ecrit, avant que quoi que ce soit le soit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MasterAEcrire:
    """Ce que `E4-3` montre du master a venir. **Rien n'est recalcule ici.**

    Tous les champs sont **donnes** : :func:`plan_du_master` les prend sur
    l'`encode.EncodePlan`, c'est-a-dire sur l'objet que `render_summary` lit
    lui-meme. Un ecran qui rederiverait l'un d'eux (le poids, les
    echantillons, le verdict) en ferait une seconde verite, et l'ecart ne se
    verrait que sur les masters produits.

    Chaque champ facultatif vaut `None` quand la source qui le porte ne repond
    pas : le segment correspondant **disparait** plutot que de sortir a zero.
    « Un champ que la source ne porte pas est omis » (`DESIGN.md` section 3).
    """

    #: Le nom du fichier, tel que `io.naming` l'a construit **dans le plan**.
    #: Le rang de version, s'il y en a un, y est deja : cet ecran arrive apres
    #: `E4-3b` et n'a plus rien a trancher (AC 7.4).
    nom: str
    lot_id: str
    lot_state: str
    profil: str
    conteneur: str
    #: La colorimetrie du master. Portee par le PROFIL, pas par le manifest --
    #: `render_summary` la cite dans la prose de sa note d'approximation, sans
    #: champ qui l'isole ; elle est donc lue a sa source de coeur.
    colorimetrie: str
    #: La geometrie de sortie, deja resolue par le coeur (`native` comprise :
    #: le plan la settle avant d'arriver ici).
    geometrie: tuple[int, int] | None
    #: La geometrie de la matiere, sondee par le coeur.
    source: tuple[int, int] | None
    #: La cadence source **exacte**, telle que le coeur l'ecrit (`25`, `24000/1001`).
    cadence: str
    #: Les echantillons reellement muxes -- frames tenues comprises.
    echantillons: int | None = None
    #: Les frames distinctes retenues par la selection.
    frames: int | None = None
    #: Le cardinal attendu par le lot, ou `None` quand il n'en declare aucun.
    attendues: int | None = None
    #: Les mires **presentes**, jamais les mires declarees et absentes.
    mires: int = 0
    #: Le verdict de completude du coeur, jamais un second calcul.
    complet: bool = False
    timecode: str | None = None
    #: Le majorant de poids, en octets. Un **ordre de grandeur** assume comme
    #: tel -- la ligne le marque `(majorant)` --, jamais une promesse.
    octets_majorants: int | None = None
    #: Le dossier du projet, dont seul le **nom** est affiche.
    dossier_projet: Path | None = None
    #: `EPIC11-ARB-190`, story 6.8 : la passe de reconstruction encodee. Aucun
    #: producteur de coeur ne la sert au 2026-09-03, donc elle est **donnee**
    #: et facultative -- absente, la ligne disparait.
    reconstruction: str | None = None
    #: L'avertissement structure du coeur quand la cadence source declaree
    #: diverge de celle du lot (`EPIC11-ARB-185`, `plan.source_rate_override_note`).
    #: **Rien n'est reecrit ici** : il se lit la ou le coeur le rend.
    note_de_cadence: str = ""

    @property
    def destination(self) -> str:
        """Le dossier des masters, relatif au projet -- `projet_demo/outputs/`.

        Vide quand aucun projet n'est donne : un chemin devine serait pire
        qu'une ligne absente, puisque c'est la seule chose qui dit ou
        l'operateur ira chercher son fichier.
        """
        if self.dossier_projet is None:
            return ""
        return f"{Path(self.dossier_projet).name}/{OUTPUTS_DIRNAME}/"


def plan_du_master(plan: "encode.EncodePlan", *,
                   reconstruction: str | None = None) -> MasterAEcrire:
    """Le plan de `E4-3`, **derive de ce que `render_summary` lit** (AC 7.1).

    :param plan: l'`encode.EncodePlan` rendu par `encode.plan_encode`, c'est-a-dire
        l'objet exact que `encode.render_summary` met en forme pour le terminal
        et pour `logs/encode.log`.
    :param reconstruction: la passe de reconstruction encodee (`EPIC11-ARB-190`).
        **Donnee**, parce qu'aucune fonction de coeur ne la rend aujourd'hui :
        c'est la story 6.8. `None` fait disparaitre la ligne.

    **Aucune valeur n'est recomposee**, et c'est ce qui rend la derivation
    mesurable : le banc rejoue `render_summary` sur le meme plan et exige que
    chaque valeur affichee ici s'y retrouve. Une seconde redaction -- un
    `len(frame_paths)` refait, un poids reestime -- passerait ce test un jour
    et le raterait le lendemain, ce qui est exactement le but.

    La geometrie suit la meme regle que le recapitulatif : la taille de la
    resolution retenue, ou la taille de la source quand la demande est
    `native` et que le plan l'a deja settlee.
    """
    profil = codec_profiles.PROFILES.get(plan.profile_id)
    if profil is None:
        raise PlanDuMasterMalForme(
            f"Le plan porte le profil {plan.profile_id!r}, absent du catalogue "
            "du coeur. Un ecran qui inventerait sa colorimetrie afficherait "
            "une propriete que le master n'aura pas."
        )
    return MasterAEcrire(
        nom=Path(plan.output_path).name,
        lot_id=plan.lot_id,
        lot_state=plan.lot_state,
        profil=plan.profile_id,
        conteneur=plan.container,
        colorimetrie=profil.colorspace,
        geometrie=plan.resolution.size or plan.source_size,
        source=plan.source_size,
        cadence=plan.exact_frame_rate,
        # `muxed_frame_paths` et `frame_paths` ne se confondent pas : le
        # premier compte les echantillons du master (frames tenues comprises),
        # le second les frames distinctes retenues. `render_summary` affiche
        # les deux sur la meme ligne, et c'est ce que la maquette dessine.
        echantillons=len(plan.muxed_frame_paths) or None,
        frames=plan.frame_count,
        attendues=plan.verdict.expected,
        mires=len(plan.verdict.synthetic_present),
        complet=plan.verdict.complete,
        timecode=plan.timecode.emitted,
        octets_majorants=plan.estimated_bytes,
        dossier_projet=Path(plan.project_dir),
        reconstruction=reconstruction,
        note_de_cadence=plan.source_rate_override_note or "",
    )


# ---------------------------------------------------------------------------
# Le cartouche -- une ligne chiffree par famille de valeur du recapitulatif
# ---------------------------------------------------------------------------


def texte_de_la_geometrie(taille: tuple[int, int] | None) -> str:
    """`1920 × 1080`, ou vide quand personne ne l'a sondee."""
    if not taille:
        return ""
    return MOTIF_DE_LA_GEOMETRIE.format(largeur=taille[0], hauteur=taille[1])


def jeton_de_completude(master: MasterAEcrire, ascii_seul: bool = False) -> str:
    """`● complet`, `▲ 3 mires` ou `✕ incomplet` -- **le vocabulaire de l'AC 5.2**.

    L'ordre des trois cas est celui que l'AC pose, et il n'est pas
    interchangeable : un lot complet ne porte pas de mire presente (« si c'est
    complet on n'a pas de mires », Egan, 2026-09-03), donc tester la
    completude d'abord ne masque rien -- alors que tester les mires d'abord
    ferait rendre `▲` a un lot complet dont le manifest garderait un registre
    de mires perime.

    Le verdict vient du coeur ; seuls les deux mots sont d'ici.
    """
    table = jetons.glyphes(ascii_seul)
    if master.complet:
        return f"{table['complete']} {ETAT_COMPLET}"
    if master.mires:
        return (f"{table['substitute']} {master.mires} "
                f"{PLURIEL_DES_MIRES[master.mires > 1]}")
    return f"{table['absent']} {ETAT_INCOMPLET}"


def ligne_du_master(master: MasterAEcrire) -> LigneChiffree:
    """`Master   plan-04_25_mmu_prores_hq.mov` -- le nom, **jamais editable**."""
    return LigneChiffree(LIBELLE_MASTER, master.nom)


def ligne_du_lot(master: MasterAEcrire) -> LigneChiffree:
    """`Lot   plan-04_25 · état reconstruction`.

    L'etat est celui du manifest, **relaye** et jamais compare ici : la garde
    d'admission vit dans `encode.check_lot_admission`, et une seconde redaction
    du critere ferait de la TUI un second juge (`EPIC11-ARB-30`).
    """
    valeur = master.lot_id
    if master.lot_state:
        valeur += f"{SEPARATEUR}état {master.lot_state}"
    return LigneChiffree(LIBELLE_LOT, valeur)


def ligne_de_la_reconstruction(master: MasterAEcrire) -> LigneChiffree | None:
    """`Reconstruction   v2 · 8 planches scannées le 02/09`, ou `None`.

    `EPIC11-ARB-190` : « on n'encode pas un lot, on encode un lot RECONSTRUIT ».
    Le coeur qui rend cette phrase est la story 6.8 ; tant qu'il n'existe pas,
    la ligne **disparait** plutot que d'annoncer une version inventee -- c'est
    le pire mode de panne du versionnage, deux passes differentes portant le
    meme numero.
    """
    if not master.reconstruction:
        return None
    return LigneChiffree(LIBELLE_RECONSTRUCTION, master.reconstruction)


def ligne_du_profil(master: MasterAEcrire) -> LigneChiffree:
    """`Profil   prores_hq → .mov · bt709` -- trois faits, deux sources de coeur."""
    return LigneChiffree(LIBELLE_PROFIL, SEPARATEUR.join([
        MOTIF_DU_PROFIL.format(profil=master.profil,
                               conteneur=master.conteneur),
        master.colorimetrie,
    ]))


def ligne_de_la_resolution(master: MasterAEcrire) -> LigneChiffree | None:
    """`Résolution   1920 × 1080 · source 1920 × 1080`, ou `None`.

    Les deux geometries restent affichees meme lorsqu'elles coincident : c'est
    le seul moyen de voir qu'aucune mise a l'echelle n'a lieu, et le
    recapitulatif du coeur les ecrit toutes les deux pour la meme raison.
    """
    sortie = texte_de_la_geometrie(master.geometrie)
    if not sortie:
        return None
    segments = [sortie]
    source = texte_de_la_geometrie(master.source)
    if source:
        segments.append(MENTION_DE_LA_SOURCE.format(geometrie=source))
    return LigneChiffree(LIBELLE_RESOLUTION, SEPARATEUR.join(segments))


def ligne_de_la_cadence(master: MasterAEcrire) -> LigneChiffree:
    """`Cadence du rushe   25 im/s · 124 échantillons · 124 frames`.

    Les deux comptes sont **ceux du coeur** et ils ne se confondent pas : les
    echantillons du master (frames tenues comprises) et les frames distinctes
    retenues. Les afficher separement est ce qui rend visible qu'un lot decime
    tient chacune de ses frames plusieurs fois -- le nominal d'`EPIC11-ARB-192`.
    """
    segments = [f"{master.cadence} {UNITE_DE_CADENCE_DU_MASTER}"]
    if master.echantillons is not None:
        segments.append(MOTIF_DES_ECHANTILLONS.format(
            echantillons=master.echantillons))
    if master.frames is not None:
        segments.append(MOTIF_DES_FRAMES.format(frames=master.frames))
    return LigneChiffree(LIBELLE_CADENCE, SEPARATEUR.join(segments))


def ligne_des_frames(master: MasterAEcrire,
                     ascii_seul: bool = False) -> LigneChiffree | None:
    """`Frames · mires   124 conformes sur 124 · 0 mire · ● complet`, ou `None`.

    **Une seule ligne pour les deux comptes** (Egan, 2026-09-03). Le compte de
    mires y reste meme a zero, contrairement a la discipline des lignes
    conditionnelles du depot : ici il n'est pas une ligne, c'est un des deux
    termes de la comparaison qu'Egan a demande de lire ensemble, et « 0 mire »
    est precisement l'information qui rend le verdict lisible.
    """
    if master.frames is None:
        return None
    conformes = (MOTIF_DES_CONFORMES.format(frames=master.frames,
                                            attendues=master.attendues)
                 if master.attendues is not None
                 else MOTIF_DES_CONFORMES_SANS_CARDINAL.format(
                     frames=master.frames))
    return LigneChiffree(LIBELLE_FRAMES, SEPARATEUR.join([
        conformes,
        f"{master.mires} {PLURIEL_DES_MIRES[master.mires > 1]}",
        jeton_de_completude(master, ascii_seul),
    ]))


def ligne_du_timecode(master: MasterAEcrire) -> LigneChiffree | None:
    """`Timecode de départ   00:00:04:12`, ou `None` quand le coeur n'en emet pas.

    Le coeur **n'en devine jamais** : un lot ne d'une planche 2.0 n'a pas de
    base de timecode, et `plan_timecode` rend alors `None`. La ligne disparait
    plutot que d'afficher `00:00:00:00`, qui designerait une autre image.
    """
    if not master.timecode:
        return None
    return LigneChiffree(LIBELLE_TIMECODE, master.timecode)


def ligne_du_poids(master: MasterAEcrire) -> LigneChiffree | None:
    """`Poids attendu   ~ 1,4 Go   (majorant)`, ou `None` quand il n'est pas su.

    **Un ordre de grandeur, jamais une promesse.** Le prefixe `~` et la mention
    `(majorant)` -- posee par `LigneChiffree` elle-meme, pas ecrite ici -- sont
    les deux canaux qui le disent, et le rendu de taille est celui que
    l'explorateur porte deja : deux formats du meme chiffre dans la meme
    interface divergeraient au premier ajustement.
    """
    lisible = taille_lisible(master.octets_majorants)
    if lisible is None:
        return None
    valeur, _, unite = lisible.partition(" ")
    return LigneChiffree(LIBELLE_POIDS, PREFIXE_APPROCHE + valeur, unite,
                         majorant=True)


def ligne_de_la_destination(master: MasterAEcrire) -> LigneChiffree | None:
    """`Destination   projet_demo/outputs/`, ou `None` sans projet."""
    destination = master.destination
    if not destination:
        return None
    return LigneChiffree(LIBELLE_DESTINATION, destination)


def ligne_de_la_note_de_cadence(master: MasterAEcrire) -> LigneChiffree | None:
    """L'avertissement du coeur sur la cadence source, **rendu tel quel**.

    `EPIC11-ARB-185`, verbatim : « Rien n'est reecrit cote TUI : l'avertissement
    se lit la ou le coeur le rend. » C'est `plan.source_rate_override_note`,
    qui nomme les **deux** valeurs et leur provenance. La paraphraser serait
    exactement ce que l'arbitrage interdit.

    **Deux defauts du coeur traversent donc jusqu'ici, et ils sont signales
    plutot que contournes :** la note se declenche meme quand la valeur fournie
    EGALE celle du lot (mesure du 2026-09-03), et elle nomme `--cadence-source`,
    une option de ligne de commande qui n'a aucun sens dans une TUI. Les
    corriger est un travail de coeur ; les masquer ici ferait de cet ecran le
    seul endroit ou l'avertissement du produit ne se lit pas.
    """
    if not master.note_de_cadence:
        return None
    return LigneChiffree(LIBELLE_NOTE_DE_CADENCE, master.note_de_cadence)


def lignes_du_cartouche(master: MasterAEcrire,
                        ascii_seul: bool = False) -> list[LigneChiffree]:
    """Les lignes chiffrees de `E4-3`, dans l'ordre de la maquette.

    Ce qui sera produit, d'ou ca vient, comment c'est encode, ce que ca
    contient, ce que ca coute, ou ca va. Les lignes conditionnelles
    disparaissent au lieu de rendre un zero.
    """
    lignes = [ligne_du_master(master), ligne_du_lot(master)]
    for ligne in (ligne_de_la_reconstruction(master),
                  ligne_du_profil(master),
                  ligne_de_la_resolution(master),
                  ligne_de_la_cadence(master),
                  ligne_des_frames(master, ascii_seul),
                  ligne_du_timecode(master),
                  ligne_du_poids(master),
                  ligne_de_la_destination(master),
                  ligne_de_la_note_de_cadence(master)):
        if ligne is not None:
            lignes.append(ligne)
    return lignes


def panneau_de_la_confirmation(master: MasterAEcrire,
                               ascii_seul: bool = False) -> Panneau:
    """Le cartouche de `E4-3`. **Aucun nom n'y est editable** (`EPIC11-ARB-141`).

    Le panneau ne porte donc aucun `noms` : le nom du master est une ligne
    chiffree comme les autres, pas un champ. C'est par **absence** que
    l'edition est retiree, ce qui la rend impossible plutot qu'improbable.
    """
    return Panneau(TITRE_A_ECRIRE, lignes_du_cartouche(master, ascii_seul))


# ---------------------------------------------------------------------------
# Les issues -- une seule ecrit, et le curseur ne la vise pas
# ---------------------------------------------------------------------------


def issues_de_la_confirmation(master: MasterAEcrire) -> ChoixExclusif:
    """Les trois issues de `E4-3`. **Le curseur ne vise aucune ecriture** (AC 7.3).

    La fleche se pose sur « Modifier les réglages », jamais sur « Encoder », et
    cela ne se reecrit pas ici : c'est un invariant leve a la construction par
    :class:`panneau.ChoixExclusif` (`EPIC11-ARB-7` puis `EPIC11-ARB-45`), qui
    **place** le curseur sur la premiere issue qui n'ecrit pas. Depuis que la
    validation retient en un seul geste, un curseur pose au montage sur
    « Encoder » rendrait l'encodage atteignable en **une** frappe.

    Le rendu est **une ligne par issue, la fleche seule** (`EPIC11-ARB-45`,
    `EPIC11-ARB-126` : « Flèche seule ! C'est uniquement dans les listes à
    cocher qu'on trouve les deux »), ce que `ChoixExclusif.rendu` fait deja.

    L'ordre est celui de la deliberation, et il ne se reordonne pas quand le
    curseur se deplace : encoder, revenir aux reglages, renoncer.

    Le master n'entre dans aucun libelle ; l'argument est pris pour que la
    signature ne change pas le jour ou l'un d'eux porterait un chiffre, comme
    `E5-3` et `E3-6` le font deja.
    """
    return ChoixExclusif([
        Issue(ISSUE_ENCODER, LIBELLE_ENCODER, ecrit=True),
        Issue(ISSUE_MODIFIER, LIBELLE_MODIFIER),
        Issue(ISSUE_ANNULER, LIBELLE_ANNULER),
    ])


# ---------------------------------------------------------------------------
# La ligne d'etat et le bandeau -- des MESURES, jamais un conseil
# ---------------------------------------------------------------------------


def mesure_de_la_confirmation(master: MasterAEcrire) -> str:
    """La ligne d'etat de `E4-3` : **une mesure**, verbatim de la maquette.

    `124 frames · ~ 1,4 Go — rien n'a encore été écrit` (l. 21).

    **C'est le dernier ecran ou rien n'est ecrit**, et la queue de cette ligne
    est le seul endroit qui le dit a l'operateur au moment ou il decide. Elle
    n'est jamais omise ; le majorant, lui, disparait quand il n'est pas su --
    le cartouche le dit deja, et la ligne d'etat ne porte que ce qu'elle mesure.

    `EPIC11-ARB-56` : aucune touche, aucun conseil d'usage, aucun motif de
    conception. Un constat, et rien d'autre.
    """
    segments = []
    if master.frames is not None:
        segments.append(MOTIF_DES_FRAMES.format(frames=master.frames))
    lisible = taille_lisible(master.octets_majorants)
    if lisible is not None:
        segments.append(PREFIXE_APPROCHE + lisible)
    mesure = SEPARATEUR.join(segments)
    if not mesure:
        # Aucune mesure connue : la queue reste, seule. Un separateur de tete
        # annoncerait une mesure qui n'existe pas -- meme discipline que
        # `atelier_pdf_versions.ETAT_DU_TIRAGE_PRESENT_SANS_MESURE`.
        return QUEUE_RIEN_ECRIT
    return mesure + LIAISON_DE_LA_MESURE + QUEUE_RIEN_ECRIT


def bandeau_du_master(master: MasterAEcrire) -> str:
    """La DROITE du bandeau : `plan-04_25 · 124 f`, verbatim de la maquette.

    Elle dit ce qu'on **travaille** -- le lot et son cardinal de frames -- la
    ou la ligne d'etat dit ce qu'on va **produire**. Les deux se lisent du meme
    plan. La forme est celle que `E4-2` porte deja, ce qui fait que le bandeau
    ne bouge pas quand on passe des reglages a la confirmation.
    """
    if master.frames is None:
        return master.lot_id
    return f"{master.lot_id}{SEPARATEUR}{master.frames} f"


# ---------------------------------------------------------------------------
# `E4-3` -- l'ecran
# ---------------------------------------------------------------------------


class EcranExportsConfirmation(EcranChiffre):
    """`E4-3` -- le point de jugement de l'atelier Exports. **Rien n'est ecrit.**

    Elle herite d'`EcranChiffre` et n'ecrit **pas** un second point de jugement :
    le cartouche, le `ChoixExclusif`, la navigation et la ligne d'etat y sont
    deja, livres par la story 11.1. Ce module **alimente** cet ecran, et
    `execution.py` -- partage par les quatre ateliers -- n'est pas modifie.

    **Aucun nom n'est editable** : le `ModeleNoms` est **vide**, donc `Tab` n'a
    aucune destination et `EcranChiffre.traiter` le rend inerte de lui-meme --
    ce n'est pas une garde ajoutee ici, c'est la consequence de ne pas donner
    de noms editables. La ligne de raccourcis ne l'annonce pas non plus, et les
    deux vont ensemble : une touche annoncee et inerte est le defaut que
    `coque.py` documente.

    `sur_issue` est **requis et sans defaut** (finding `K3`, paye quatre fois
    dans cet epic) : un point de jugement qui ne sait pas a qui rendre son
    issue est un cul-de-sac, et un `Callable | None = None` assorti d'un
    `if ... is not None` fait de l'oubli de cablage un silence.
    """

    titre = projet_lecture.EXPORTS

    #: **Un ATTRIBUT de classe, jamais une `@property`.** La garde de paquet de
    #: `test_repli_ascii.py` balaye les sous-classes de `Palier` et lit
    #: `classe.raccourcis` **au niveau de la classe** : une propriete y rendrait
    #: l'objet `property` et ferait echapper l'ecran a la mesure.
    raccourcis = RACCOURCIS_EXPORTS_CONFIRMATION

    #: **Un passage, pas une station** : un point de jugement franchi ne doit
    #: pas rester sur le chemin du retour. C'est deja la valeur qu'`EcranChiffre`
    #: pose ; elle est redite parce que c'est une propriete du parcours et non
    #: un detail d'implementation.
    TRANSITOIRE = True

    def __init__(self, master: MasterAEcrire, *,
                 sur_issue: Callable[[Issue], None]) -> None:
        super().__init__(panneau_de_la_confirmation(master),
                         issues_de_la_confirmation(master),
                         # **Vide, et c'est le sujet d'`EPIC11-ARB-141`** : le
                         # nom du master n'est pas un champ.
                         noms=ModeleNoms(),
                         sur_issue=sur_issue)
        #: Le master montre. C'est lui qui porte les chiffres ; l'ecran n'en
        #: recalcule aucun.
        self.master = master

    # -- rendu ---------------------------------------------------------------

    def lignes_du_panneau(self) -> list[str]:
        """Le cartouche a la largeur courante, dans le regime courant.

        Le panneau est **recompose** plutot que garde tel quel : `ascii_seul`
        commande le jeton de completude, et il n'est connu qu'une fois l'ecran
        monte. `ascii_seul` **precede la mesure** -- `…` vaut une colonne,
        `...` en vaut trois, et choisir les points apres avoir compte ferait
        deborder de deux colonnes une ligne calee juste.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        largeur = self.app.size.width
        return panneau_de_la_confirmation(self.master, ascii_seul).rendu(
            largeur, ascii_seul)

    def objet_du_bandeau(self) -> str:
        """`plan-04_25 · 124 f` -- compose du plan, jamais recu.

        Cet ecran **est** celui de l'atelier Exports et son objet varie avec le
        lot : le recevoir a la construction ferait recopier la composition au
        cablage, donc diverger de la maquette au premier ajustement.
        """
        return bandeau_du_master(self.master)

    def etat(self) -> str:
        """La ligne d'etat : la mesure de la passe, et « rien n'a encore été écrit ».

        Le regime de refus de la classe de base passe en premier -- c'est le
        moment ou l'operateur a besoin d'autre chose que le total. Le regime
        d'edition, lui, ne peut pas se presenter : il n'y a aucun nom a editer.
        """
        if self._refus_annonce is not None:
            return super().etat()
        return mesure_de_la_confirmation(self.master)


__all__ = [
    "ETAT_COMPLET",
    "ETAT_INCOMPLET",
    "EcranExportsConfirmation",
    "ISSUE_ANNULER",
    "ISSUE_ENCODER",
    "ISSUE_MODIFIER",
    "LIAISON_DE_LA_MESURE",
    "LIBELLE_ANNULER",
    "LIBELLE_CADENCE",
    "LIBELLE_ENCODER",
    "LIBELLE_FRAMES",
    "LIBELLE_LOT",
    "LIBELLE_MASTER",
    "LIBELLE_MODIFIER",
    "LIBELLE_NOTE_DE_CADENCE",
    "LIBELLE_POIDS",
    "LIBELLE_PROFIL",
    "LIBELLE_RECONSTRUCTION",
    "LIBELLE_RESOLUTION",
    "LIBELLE_TIMECODE",
    "MasterAEcrire",
    "MOTIF_DES_CONFORMES",
    "MOTIF_DES_ECHANTILLONS",
    "MOTIF_DES_FRAMES",
    "PLURIEL_DES_MIRES",
    "PlanDuMasterMalForme",
    "QUEUE_RIEN_ECRIT",
    "RACCOURCIS_EXPORTS_CONFIRMATION",
    "SEPARATEUR",
    "UNITE_DE_CADENCE_DU_MASTER",
    "bandeau_du_master",
    "issues_de_la_confirmation",
    "jeton_de_completude",
    "ligne_de_la_cadence",
    "ligne_de_la_destination",
    "ligne_de_la_note_de_cadence",
    "ligne_de_la_reconstruction",
    "ligne_de_la_resolution",
    "ligne_des_frames",
    "ligne_du_lot",
    "ligne_du_master",
    "ligne_du_poids",
    "ligne_du_profil",
    "ligne_du_timecode",
    "lignes_du_cartouche",
    "mesure_de_la_confirmation",
    "panneau_de_la_confirmation",
    "plan_du_master",
    "texte_de_la_geometrie",
]
