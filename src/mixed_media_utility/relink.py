"""Coeur du relink (story 2.8): identite d'un rush, relink et mode delinke.

Le chemin du rush source vit desormais dans le manifest
(`rushes[].source_path`, AC 1, `EPIC7-ARB-41` -- decision produit d'Egan,
verbatim « Dans le projet ! Mais remplacable ! »). C'est un chemin de
MACHINE: il peut se casser (fichier deplace, renomme, archive, disque
demonte, projet copie sur une autre machine). Ce module porte les deux autres
exigences de l'arbitrage:

* **le relink est un geste de premiere classe** (AC 2): une commande dediee,
  une regle de comparaison d'identite nommee -- nom, duree en frames source,
  timecode de depart (`EPIC7-ARB-34`) -- et une recherche recursive
  (`--chercher`) a cote de la designation manuelle (`--video`);
* **l'absence du rush n'empeche rien d'essentiel** (AC 3): un statut de
  liaison explicite (`statut_de_liaison`) et un refus nomme, reserve aux
  commandes qui ont reellement besoin du fichier source.

Ce que ce module NE fait PAS:

* choisir entre deux candidats qui satisfont tous les trois criteres --
  `EPIC7-ARB-34` l'interdit mot pour mot (« jamais un choix silencieux »);
  la question de departage reste ouverte, consignee dans `deferred-work.md`
  (« Le conflit d'appariement au relink »), et cette story ne la tranche pas;
* offrir un `--force`: un critere d'identite verifiable qui echoue refuse le
  relink sans recours (Decisions d'ecriture de la story, point 3) -- un
  contournement de la verification d'identite serait un arbitrage produit
  qui n'a pas ete pris ici.

Convention d'ecriture: commentaires et docstrings en francais sans accents,
comme `extraction.py` et `io/manifest.py`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from . import extraction, video_metadata

__all__ = [
    "CRITERES_IDENTITE_RELINK",
    "TOLERANCE_DUREE_RELINK_FRAMES",
    "LIE",
    "DELINKE_CHEMIN_MORT",
    "DELINKE_CHEMIN_ABSENT",
    "REFUS_RUSH_INCONNU",
    "REFUS_RUSH_AMBIGU",
    "REFUS_AUCUN_RUSH",
    "REFUS_CARDINAUX_DIVERGENTS",
    "REFUS_CRITERE_NON_VERIFIABLE_RECHERCHE",
    "REFUS_CRITERE_ECHEC",
    "REFUS_VIDEO_ILLISIBLE",
    "REFUS_AUCUN_CANDIDAT",
    "REFUS_CANDIDATS_MULTIPLES",
    "REFUS_DOSSIER_RECHERCHE_INVALIDE",
    "REFUS_RUSH_REQUIS",
    "RelinkError",
    "ProbeCandidat",
    "ReferenceIdentite",
    "EvaluationCritere",
    "probe_reel",
    "evaluer_candidat",
    "charger_reference",
    "resoudre_rush_id",
    "verifier_designation_manuelle",
    "rechercher_candidat",
    "statut_de_liaison",
    "refus_necessite_le_rush",
    "appliquer_relink",
]


# --------------------------------------------------------------------------
# Constantes nommees (AC 2, exigees telles quelles par l'AC d'epics)
# --------------------------------------------------------------------------

#: Les trois criteres d'identite du relink, dans l'ordre normatif de l'AC 2:
#: nom, duree, timecode de depart. Nom de champ = nom du critere: c'est
#: deliberement le meme vocabulaire que `rushes[].source_name`,
#: `lots[].source_frame_count` et `rushes[].source_start_timecode`.
CRITERES_IDENTITE_RELINK: tuple[str, ...] = (
    "source_name",
    "source_frame_count",
    "source_start_timecode",
)

#: Tolerance de duree des qu'un cote (reference du manifest ou probe du
#: candidat) est estime -- meme regle "a une frame pres" que
#: `extraction.resolve_source_frame_count`.
TOLERANCE_DUREE_RELINK_FRAMES = 1


# --------------------------------------------------------------------------
# Statut de liaison (AC 3)
# --------------------------------------------------------------------------

LIE = "lie"
DELINKE_CHEMIN_MORT = "delinke-chemin-mort"
DELINKE_CHEMIN_ABSENT = "delinke-chemin-absent"


# --------------------------------------------------------------------------
# Refus nommes (gabarit io.reconstruction.REFUS_PILE_MIXTE: un CODE sur
# `.reason`, jamais une phrase francaise a reconnaitre dans un test)
# --------------------------------------------------------------------------

REFUS_RUSH_INCONNU = "rush-id-inconnu"
REFUS_RUSH_AMBIGU = "rush-id-omis-ambigu"
#: Manifest sans aucun rush (`rushes[]` vide): distinct de REFUS_RUSH_AMBIGU
#: (revue de 2.8, patch 4a) -- il n'y a rien a departager, ce n'est pas une
#: ambiguite, c'est l'absence totale de rush.
REFUS_AUCUN_RUSH = "aucun-rush-dans-le-manifest"
REFUS_CARDINAUX_DIVERGENTS = "cardinaux-divergents-entre-lots"
REFUS_CRITERE_NON_VERIFIABLE_RECHERCHE = "critere-non-verifiable-en-recherche"
REFUS_CRITERE_ECHEC = "critere-identite-en-echec"
#: Designation manuelle (`--video`) dont le probe echoue: fichier corrompu,
#: illisible, ou pas un flux video exploitable (revue de 2.8, patch 1).
REFUS_VIDEO_ILLISIBLE = "video-designee-illisible"
REFUS_AUCUN_CANDIDAT = "aucun-candidat"
REFUS_CANDIDATS_MULTIPLES = "candidats-multiples"
#: `--chercher` pointant vers un chemin qui n'existe pas ou n'est pas un
#: dossier: distinct de REFUS_AUCUN_CANDIDAT (revue de 2.8, patch 4b) -- ici
#: la recherche n'a meme pas pu commencer, ce n'est pas une recherche
#: infructueuse.
REFUS_DOSSIER_RECHERCHE_INVALIDE = "dossier-recherche-invalide"
REFUS_RUSH_REQUIS = "rush-requis-relink"


class RelinkError(RuntimeError):
    """Toute impossibilite de relink ou d'usage d'un rush delinke.

    Le motif voyage sur `.reason` (un des `REFUS_*` ci-dessus), jamais dans
    le texte du message: un appelant qui veut distinguer les refus n'a pas a
    analyser une phrase francaise (meme gabarit que
    `io.reconstruction._refus_de_pile`).
    """


def _refus(code: str, message: str) -> RelinkError:
    erreur = RelinkError(message)
    erreur.reason = code
    return erreur


# --------------------------------------------------------------------------
# Ce qu'un probe rend sur un fichier candidat
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ProbeCandidat:
    """Ce que `extract` connaitrait d'un fichier s'il l'extrayait: assez pour
    verifier les trois criteres d'identite, jamais plus. Decouple de ffprobe
    pour rester testable sans disque ni binaire externe (la decision pure de
    ce module ne depend que de cette forme, jamais de `video_metadata`
    directement)."""

    nom_de_base: str
    cardinal_frames: int | None
    cardinal_est_exact: bool
    timecode_depart: str | None


def probe_reel(
    video_path: Path,
    *,
    ffprobe_binaire: str = "ffprobe",
    logger: Any = None,
) -> ProbeCandidat:
    """Probe par defaut: LE MEME chemin que `extract`, jamais une
    re-derivation (`qualify_source` puis `resolve_source_frame_count`).

    `extraction.py` l'interdit deja explicitement: « Il ne derive jamais le
    cardinal source d'une duree: il l'exige. » Un second chemin de probe
    ici romprait cette garantie pour le seul usage du relink.
    """
    probe = video_metadata.probe_media(str(video_path), ffprobe_bin=ffprobe_binaire)
    qualification = extraction.qualify_source(probe)
    cardinal, exact = extraction.resolve_source_frame_count(
        video_path, qualification, ffprobe_bin=ffprobe_binaire, logger=logger,
    )
    return ProbeCandidat(
        nom_de_base=Path(video_path).name,
        cardinal_frames=cardinal,
        cardinal_est_exact=exact,
        timecode_depart=qualification.start_timecode,
    )


# --------------------------------------------------------------------------
# Reference d'identite, lue sur le manifest pour le rush vise
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceIdentite:
    """Les trois references d'identite du rush vise, et ce qui est
    effectivement verifiable.

    « Un critere sans reference au manifest est NON VERIFIABLE; il est
    toujours DIT, jamais passe en silence » (AC 2). Le timecode de depart est
    un cas special: son absence AU MANIFEST est en temps normal une valeur
    comparable ("source non taguee", AC 2 point 3) -- sauf dans le cas
    `barren`, ou aucune extraction n'a jamais renseigne ce rush et l'absence
    ne veut donc rien dire (Decisions d'ecriture de la story, point 2:
    manifest ne du scan seul, aucune des trois references).
    """

    rush_id: str
    source_name: str | None
    source_frame_count: int | None
    source_frame_count_is_exact: bool | None
    source_start_timecode: str | None

    @property
    def barren(self) -> bool:
        """Entree de rush a `rush_id` nu: ni nom ni cardinal nulle part.

        C'est le signal qu'aucune extraction n'a jamais tourne sur ce rush
        (manifest issu du scan seul) -- distinct d'un rush normalement
        extrait dont la source, elle, n'etait simplement pas taguee.
        """
        return self.source_name is None and self.source_frame_count is None

    @property
    def criteres_verifiables(self) -> tuple[str, ...]:
        disponibles = set()
        if self.source_name is not None:
            disponibles.add("source_name")
        if self.source_frame_count is not None:
            disponibles.add("source_frame_count")
        if not self.barren:
            disponibles.add("source_start_timecode")
        return tuple(c for c in CRITERES_IDENTITE_RELINK if c in disponibles)

    @property
    def criteres_non_verifiables(self) -> tuple[str, ...]:
        verifiables = set(self.criteres_verifiables)
        return tuple(c for c in CRITERES_IDENTITE_RELINK if c not in verifiables)


def _find_rush(manifest: Mapping[str, Any], rush_id: str) -> dict[str, Any] | None:
    for rush in manifest.get("rushes", []) or []:
        if isinstance(rush, dict) and rush.get("rush_id") == rush_id:
            return rush
    return None


def _reference_duree(
    manifest: Mapping[str, Any], rush_id: str
) -> tuple[int | None, bool | None]:
    """Cardinal de reference: lu sur les lots du rush vise
    (`lots[].source_frame_count`, donnee du fichier ENTIER -- valable meme
    pour un lot borne 3.7, `frame_selection.py`).

    Regle des fabriques (AC 4): appariement par `rush_id`, jamais par
    position -- deux lots d'un AUTRE rush avant celui-ci dans `lots[]` ne
    doivent rien changer.

    Si deux lots du meme rush divergent sur le cardinal: refus (AC 2, point
    2) -- le manifest est incoherent, ce module ne choisit pas.
    """
    valeurs: set[tuple[int, bool]] = set()
    for lot in manifest.get("lots", []) or []:
        if not isinstance(lot, dict) or lot.get("rush_id") != rush_id:
            continue
        cardinal = lot.get("source_frame_count")
        if cardinal is None:
            continue
        valeurs.add((int(cardinal), bool(lot.get("source_frame_count_is_exact", False))))

    if not valeurs:
        return None, None

    cardinaux_distincts = sorted({cardinal for cardinal, _ in valeurs})
    if len(cardinaux_distincts) > 1:
        raise _refus(
            REFUS_CARDINAUX_DIVERGENTS,
            f"Manifest incoherent pour rush_id={rush_id!r}: des lots de ce rush "
            f"declarent des cardinaux source divergents {cardinaux_distincts}. "
            "Le relink refuse de choisir entre eux."
        )
    cardinal = cardinaux_distincts[0]
    # Exact seulement si TOUS les lots d'accord sur ce cardinal le disent
    # exact: une seule estimation quelque part impose la tolerance.
    exact = all(est_exact for valeur, est_exact in valeurs if valeur == cardinal)
    return cardinal, exact


def charger_reference(manifest: Mapping[str, Any], rush_id: str) -> ReferenceIdentite:
    """Assembler la reference d'identite du rush vise depuis le manifest.

    Leve `RelinkError` (`REFUS_RUSH_INCONNU`) si `rush_id` n'y figure pas, et
    (`REFUS_CARDINAUX_DIVERGENTS`) si les lots de ce rush se contredisent sur
    le cardinal source.
    """
    rush = _find_rush(manifest, rush_id)
    if rush is None:
        raise _refus(
            REFUS_RUSH_INCONNU, f"rush_id={rush_id!r} absent du manifest de projet."
        )

    source_name = rush.get("source_name")
    if not isinstance(source_name, str) or not source_name:
        source_name = None

    cardinal, cardinal_exact = _reference_duree(manifest, rush_id)

    timecode = rush.get("source_start_timecode")
    if not isinstance(timecode, str) or not timecode:
        timecode = None

    return ReferenceIdentite(
        rush_id=rush_id,
        source_name=source_name,
        source_frame_count=cardinal,
        source_frame_count_is_exact=cardinal_exact,
        source_start_timecode=timecode,
    )


def resoudre_rush_id(manifest: Mapping[str, Any], rush_id: str | None) -> str:
    """`--rush` est omissible quand le projet ne porte qu'un rush (AC 2).

    Sur plusieurs rushs, l'omission refuse en listant les `rush_id` connus
    plutot que d'en choisir un au hasard.
    """
    rushes = [
        rush for rush in manifest.get("rushes", []) or []
        if isinstance(rush, dict) and rush.get("rush_id")
    ]
    if rush_id is not None:
        if _find_rush(manifest, rush_id) is None:
            connus = ", ".join(sorted(str(rush["rush_id"]) for rush in rushes)) or "aucun"
            raise _refus(
                REFUS_RUSH_INCONNU,
                f"rush_id={rush_id!r} absent du manifest de projet. Rush(s) "
                f"connu(s): {connus}.",
            )
        return rush_id

    if len(rushes) == 1:
        return str(rushes[0]["rush_id"])

    if not rushes:
        # Aucun rush du tout: ce n'est pas une ambiguite (rien a departager),
        # c'est un manifest vide (revue de 2.8, patch 4a).
        raise _refus(
            REFUS_AUCUN_RUSH,
            "--rush omis et le manifest de projet ne porte aucun rush. Il n'y a "
            "rien a relinker: lancez d'abord une extraction sur ce projet.",
        )

    connus = ", ".join(sorted(str(rush["rush_id"]) for rush in rushes))
    raise _refus(
        REFUS_RUSH_AMBIGU,
        f"--rush omis alors que le projet porte {len(rushes)} rush(s): {connus}. "
        "Preciser --rush <rush_id>.",
    )


# --------------------------------------------------------------------------
# Evaluation d'un candidat contre une reference (decision pure)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationCritere:
    """Le verdict d'UN critere pour UN candidat: verifiable ou non, satisfait
    ou non (None quand non verifiable), avec les deux valeurs en jeu pour un
    message de refus actionnable."""

    critere: str
    verifiable: bool
    satisfait: bool | None
    valeur_attendue: Any
    valeur_mesuree: Any


def evaluer_candidat(
    reference: ReferenceIdentite, candidat: ProbeCandidat
) -> tuple[EvaluationCritere, ...]:
    """Confronter un candidat aux trois criteres d'identite (AC 2), decision
    pure -- ni disque ni probe ici, tout est deja dans les deux arguments."""
    verifiables = set(reference.criteres_verifiables)
    resultats: list[EvaluationCritere] = []

    # 1. Nom: comparaison exacte, sensible a la casse.
    verifiable = "source_name" in verifiables
    satisfait = (candidat.nom_de_base == reference.source_name) if verifiable else None
    resultats.append(EvaluationCritere(
        "source_name", verifiable, satisfait, reference.source_name, candidat.nom_de_base,
    ))

    # 2. Duree: egalite stricte si les deux cotes sont exacts, sinon
    # tolerance d'une frame des qu'un cote est estime.
    verifiable = "source_frame_count" in verifiables
    if verifiable:
        if candidat.cardinal_frames is None:
            satisfait = False
        else:
            deux_cotes_exacts = (
                bool(reference.source_frame_count_is_exact) and candidat.cardinal_est_exact
            )
            ecart = abs(candidat.cardinal_frames - reference.source_frame_count)
            satisfait = ecart == 0 if deux_cotes_exacts else ecart <= TOLERANCE_DUREE_RELINK_FRAMES
    else:
        satisfait = None
    resultats.append(EvaluationCritere(
        "source_frame_count", verifiable, satisfait,
        reference.source_frame_count, candidat.cardinal_frames,
    ))

    # 3. Timecode de depart: l'absence se compare a l'absence.
    verifiable = "source_start_timecode" in verifiables
    satisfait = (
        reference.source_start_timecode == candidat.timecode_depart
    ) if verifiable else None
    resultats.append(EvaluationCritere(
        "source_start_timecode", verifiable, satisfait,
        reference.source_start_timecode, candidat.timecode_depart,
    ))

    return tuple(resultats)


def _message_criteres(evaluations: tuple[EvaluationCritere, ...]) -> str:
    return ", ".join(
        f"{evaluation.critere}=attendu {evaluation.valeur_attendue!r}/"
        f"mesure {evaluation.valeur_mesuree!r}"
        for evaluation in evaluations
    )


# --------------------------------------------------------------------------
# Designation manuelle (--video) et recherche (--chercher)
# --------------------------------------------------------------------------


def verifier_designation_manuelle(
    video_path: Path,
    *,
    reference: ReferenceIdentite,
    probe: Callable[[Path], ProbeCandidat] = probe_reel,
) -> tuple[str, ...]:
    """Verifier une designation manuelle (`--video`).

    Rend le tuple des avertissements a afficher (vide s'il n'y a rien a
    signaler). Leve `RelinkError` (`REFUS_CRITERE_ECHEC`) si un critere
    VERIFIABLE echoue -- aucun `--force` dans cette story (Decisions
    d'ecriture, point 3).

    Si AUCUN des trois criteres n'est verifiable, la designation est
    acceptee avec un avertissement nomme: l'operateur est l'autorite de la
    designation manuelle (`EPIC7-ARB-34`: « le relink manuel prend le dessus
    [...] Toujours »), et le manifest n'a rien pour le contredire.

    Leve `RelinkError` (`REFUS_VIDEO_ILLISIBLE`) si le probe echoue --
    fichier corrompu, absent, ou pas un flux video exploitable. Meme trio
    d'exceptions que `rechercher_candidat` (revue de 2.8, patch 1): c'est le
    chemin de designation manuelle, le plus expose a l'erreur de saisie
    humaine, il ne doit jamais laisser une trace Python brute remonter.
    """
    try:
        candidat = probe(video_path)
    except (extraction.ExtractionInputError, video_metadata.FfprobeError, OSError) as exc:
        raise _refus(
            REFUS_VIDEO_ILLISIBLE,
            f"Relink refuse: le fichier designe {str(video_path)!r} n'a pas pu "
            f"etre lu ({exc}). Verifier qu'il existe et qu'il s'agit d'un "
            "flux video exploitable."
        ) from exc
    evaluations = evaluer_candidat(reference, candidat)

    if not reference.criteres_verifiables:
        return (
            "aucun des trois criteres d'identite (" + ", ".join(CRITERES_IDENTITE_RELINK) +
            ") n'est verifiable sur ce manifest (manifest issu du scan seul, "
            "sans reference d'identite pour ce rush): la designation manuelle est "
            "acceptee sans verification, sur l'autorite de l'operateur.",
        )

    for evaluation in evaluations:
        if evaluation.verifiable and not evaluation.satisfait:
            raise _refus(
                REFUS_CRITERE_ECHEC,
                f"Relink refuse: le critere '{evaluation.critere}' ne correspond pas "
                f"(attendu {evaluation.valeur_attendue!r}, mesure "
                f"{evaluation.valeur_mesuree!r})."
            )
    return ()


def rechercher_candidat(
    dossier: Path,
    *,
    reference: ReferenceIdentite,
    probe: Callable[[Path], ProbeCandidat] = probe_reel,
) -> Path:
    """Rechercher recursivement, sous `dossier`, l'unique fichier qui
    satisfait les trois criteres d'identite (`--chercher`, `EPIC7-ARB-34`).

    Exige les trois references (AC 2): une recherche sans critere complet
    devinerait, la machine ne devine pas -- refus nomme si l'une manque.

    Cout maitrise: le nom filtre en premier (comparaison de chaines,
    gratuite); seuls les candidats au nom conforme sont probes (et leur
    eventuel `-count_frames`, jusqu'a 30 minutes, n'est paye que pour eux).

    Deux candidats ou plus qui satisfont les trois criteres: erreur listant
    les chemins, JAMAIS un choix silencieux (`EPIC7-ARB-34`). Zero candidat:
    erreur nommant les criteres et le dossier parcouru.
    """
    non_verifiables = reference.criteres_non_verifiables
    if non_verifiables:
        raise _refus(
            REFUS_CRITERE_NON_VERIFIABLE_RECHERCHE,
            "Recherche automatique refusee: le manifest ne porte pas de reference "
            f"pour {', '.join(non_verifiables)}. Une recherche sans critere complet "
            "devinerait; utiliser --video pour une designation manuelle."
        )

    if not dossier.is_dir():
        # Distinct d'une recherche legitime sans resultat (REFUS_AUCUN_CANDIDAT):
        # ici la recherche n'a meme pas pu commencer -- `rglob` sur un chemin
        # inexistant ou qui n'est pas un dossier ne leve rien et rendrait
        # silencieusement zero candidat (revue de 2.8, patch 4b).
        raise _refus(
            REFUS_DOSSIER_RECHERCHE_INVALIDE,
            f"Recherche automatique refusee: {dossier} n'existe pas ou n'est pas "
            "un dossier. Verifier le chemin passe a --chercher."
        )

    candidats_nommes = sorted(
        chemin for chemin in dossier.rglob("*")
        if chemin.is_file() and chemin.name == reference.source_name
    )

    correspondants: list[Path] = []
    for chemin in candidats_nommes:
        try:
            candidat = probe(chemin)
        except (extraction.ExtractionInputError, video_metadata.FfprobeError, OSError):
            # Un fichier qui porte le bon nom mais qu'aucun probe ne sait lire
            # (corrompu, cadence non fiable, pas un flux video exploitable)
            # n'est pas un candidat: il est ecarte, jamais un motif d'echec de
            # toute la recherche.
            continue
        evaluations = evaluer_candidat(reference, candidat)
        if all(evaluation.satisfait for evaluation in evaluations if evaluation.verifiable):
            correspondants.append(chemin)

    if not correspondants:
        raise _refus(
            REFUS_AUCUN_CANDIDAT,
            f"Aucun candidat trouve sous {dossier} pour rush_id={reference.rush_id!r} "
            f"(criteres: nom={reference.source_name!r}, "
            f"duree={reference.source_frame_count!r} frame(s), "
            f"timecode={reference.source_start_timecode!r})."
        )
    if len(correspondants) > 1:
        raise _refus(
            REFUS_CANDIDATS_MULTIPLES,
            "Plusieurs candidats satisfont les trois criteres d'identite, choix "
            f"impossible sans arbitrage: {[str(chemin) for chemin in correspondants]}."
        )
    return correspondants[0]


# --------------------------------------------------------------------------
# Statut de liaison et refus a l'usage (AC 3)
# --------------------------------------------------------------------------


def statut_de_liaison(
    rush_entry: Mapping[str, Any] | None,
    *,
    existe: Callable[[str], bool] | None = None,
) -> str:
    """Statut de liaison d'un rush: `LIE`, `DELINKE_CHEMIN_MORT` ou
    `DELINKE_CHEMIN_ABSENT` (AC 3).

    Le chemin mort est teste A L'USAGE: c'est CETTE fonction qui touche le
    disque, jamais `validate_manifest` ni la simple lecture du manifest --
    ouvrir un projet ne verifie donc jamais silencieusement l'existence d'un
    fichier que personne n'a demande.
    """
    chemin = (rush_entry or {}).get("source_path") if isinstance(rush_entry, Mapping) else None
    if not chemin:
        return DELINKE_CHEMIN_ABSENT
    verificateur = existe or (lambda chaine: Path(chaine).is_file())
    return LIE if verificateur(chemin) else DELINKE_CHEMIN_MORT


def refus_necessite_le_rush(commande: str, rush_id: str) -> RelinkError:
    """Refus nomme qu'une commande qui a reellement besoin du fichier source
    leve quand le rush est delinke (AC 3): cite `relink` et le `rush_id`.

    Aucune commande CLI du perimetre de cette story n'appelle cette fonction
    (`extract` et `previz` recoivent `--video` explicitement, `scan`,
    `encode` et `makepdf` ne lisent jamais `rushes[].source_path`): c'est la
    GUI (story 7.8, degrisement) qui la consommera.
    """
    return _refus(
        REFUS_RUSH_REQUIS,
        f"{commande} necessite le fichier source du rush {rush_id!r}, qui est "
        f"delinke. Le retrouver avec `relink --project <dossier> --rush {rush_id} "
        "--video <fichier>` (ou --chercher <dossier>), puis relancer la commande."
    )


# --------------------------------------------------------------------------
# Ecriture (pure: la copie profonde, jamais l'I/O -- l'appelant persiste)
# --------------------------------------------------------------------------


def appliquer_relink(
    manifest: Mapping[str, Any], rush_id: str, nouveau_chemin: str
) -> dict[str, Any]:
    """Rendre une COPIE du manifest ou seul `rushes[].source_path` du rush
    vise a change (AC 2: « ne touche a rien d'autre »).

    Copie profonde par serialisation, meme motif que
    `cli._apply_default_target_colorspace`: aucune reference partagee avec
    l'appelant, aucune mutation en place du manifest recu.
    """
    copie = json.loads(json.dumps(manifest))
    for rush in copie.get("rushes", []) or []:
        if isinstance(rush, dict) and rush.get("rush_id") == rush_id:
            rush["source_path"] = nouveau_chemin
            return copie
    raise _refus(REFUS_RUSH_INCONNU, f"rush_id={rush_id!r} absent du manifest de projet.")
