"""Persistance au manifest de ce que `makepdf` vient de produire (story 5.11).

Quatre donnees, et rien d'autre, apres une generation de PDF reussie:
`lots[].state = "pdf"`, `lots[].template_id`, `lots[].patch_preset_id` et
`lots[].gamut_map_id`. La table `PDF_LOT_FIELDS` est l'emplacement unique de
chacune; toute donnee qui n'y figure pas n'est pas ecrite -- ni date-heure de
generation, ni nom du PDF, ni cardinal de pages, ni `artifacts.patches_dir`.

Ce module ferme l'ecart assume par EPIC4-ARB-4: la matrice de responsabilite
2.4 marque `template_id` et `patch_preset_id` « MANIFEST: REQUIRED » alors
qu'aucun producteur ne les ecrivait sur `lots[]`. Le declencheur ecrit dans
l'arbitrage d'origine -- « tant que le scan n'en a pas besoin » -- est atteint:
`gamut_map_id` doit atteindre le manifest des l'impression pour que le scan le
**confronte** au lieu de le decouvrir (EPIC5-ARB-20).

Reprendre, ne pas copier
------------------------
L'ecriture atomique (`_atomic_write`), la serialisation canonique
(`_serialize`) et la relecture typee (`_load_existing_manifest`) sont celles de
la story 3.4, importees telles quelles depuis `io.extraction_manifest`. Il
n'existe pas de seconde version de ces trois fonctions dans le depot, et il ne
doit pas en exister: le contre-exemple a ne pas reproduire est
`reconstruct-project` (`cli.py`), qui ecrit **puis** valide. Corollaire assume:
la hierarchie d'erreurs remontee a la CLI reste `ExtractionPersistenceError`,
dont le nom parle d'extraction alors qu'il couvre desormais l'impression, et
le message d'un temporaire invalide parle de « manifest d'extraction ». Le
renommage appartient a une passe transverse, pas a cette story.

Limite de concurrence, heritee et declaree
------------------------------------------
Le depot n'a **aucun verrou** sur la sequence lecture-modification-ecriture du
manifest. Le defaut est deja consigne deux fois (`deferred-work.md`, revues 3.1
et 3.4): plusieurs `extract` simultanes sur un meme projet perdent des lots
**en rendant tous un succes**, parce que chacun relit le manifest avant que le
precedent n'ait bascule le sien. Ce module ajoute un **troisieme ecrivain** et
donc un cas nouveau: un `makepdf` et un `extract` concurrents sur le meme
projet. Il ne corrige pas -- il faut une politique globale, hors perimetre --
mais il refuse de laisser la limite se redecouvrir une quatrieme fois. Regle
d'usage jusqu'a nouvel ordre: **une seule commande ecrivant le manifest a la
fois par projet**.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema.exceptions import ValidationError

from .extraction_manifest import (
    MANIFEST_FILENAME,
    ExtractionPersistenceError,
    _atomic_write,
    _load_existing_manifest,
)
from .manifest import validate_lot_state_transition

# --------------------------------------------------------------------------
# Table de persistance (normative)
# --------------------------------------------------------------------------

#: Etat pose par cette story, exclusivement via
#: `io.manifest.validate_lot_state_transition`. `"pdf"` est connu de
#: `LOT_STATES` et de l'enum du schema depuis la story 2.2, mais n'avait
#: jusqu'ici **aucun producteur** sur le contrat v2: sa seule occurrence etait
#: `meta.lot.state` du manifest legacy du POC, un document sans
#: `schema_version` et sans `lots[]`.
PDF_LOT_STATE = "pdf"

#: Inventaire des PDF de planches produits pour un lot (`EPIC11-ARB-90/91`).
#:
#: **Pourquoi il existe.** `makepdf` n'ecrivait nulle part OU il avait ecrit.
#: Deux mecanismes en payaient le prix, et par le meme defaut : la suppression
#: retrouvait la planche en RECALCULANT son nom, et le resolveur de rang
#: comptait les tirages en balayant le disque. Un PDF renomme a la main
#: echappait aux deux -- il restait sur le disque, et son rang etait rendu
#: comme libre, donc reattribue a un tirage suivant qui l'aurait ecrase.
#:
#: **Pourquoi un INVENTAIRE et non un champ unique**, meme motif que
#: `encoded_masters` : le versionnage permet 99 tirages du meme lot, et un
#: champ unique effacerait la trace du precedent a chaque reimpression --
#: information non re-derivable des lors qu'un fichier a ete renomme, ce qui
#: est precisement le cas que cet inventaire existe pour couvrir.
SHEETS_INVENTORY_FIELD = "sheets_pdfs"

#: Plus haut rang de tirage JAMAIS employe (`EPIC11-ARB-92`, Egan 2026-08-31).
#: Distinct du plus haut rang encore declare : un rang se consomme.
SHEETS_WATERMARK_FIELD = "sheets_version_watermark"

#: Emplacement unique de chaque donnee ecrite par ce module, sur le motif
#: d'`EXTRACTION_LOT_FIELDS`. **Toute donnee absente de cette table n'est pas
#: ecrite**: la table est le contrat, pas un resume du code.
PDF_LOT_FIELDS: tuple[str, ...] = (
    "state",
    "template_id",
    "patch_preset_id",
    "gamut_map_id",
    SHEETS_INVENTORY_FIELD,
    SHEETS_WATERMARK_FIELD,
)

#: Cle d'appariement de l'inventaire: le chemin, unique par construction.
SHEETS_INVENTORY_KEY = "path"

#: Les trois identifiants d'impression, dans l'ordre de la table. `state` en
#: est exclu: il ne vient pas du plan mais de la garde de transition.
PDF_IDENTIFIER_FIELDS: tuple[str, ...] = (
    "template_id",
    "patch_preset_id",
    "gamut_map_id",
)

#: Equivalent de `NON_IDEMPOTENT_FIELDS` (story 3.4): **le tuple vide**. Deux
#: `makepdf` identiques laissent le manifest identique octet a octet. Aucune
#: horodate, aucun compteur, aucune valeur derivee de l'horloge n'entre au
#: manifest par ce chemin -- en particulier pas `generated_at`, qui rendrait
#: deux executions identiques distinguables alors que la seule chose qu'elle
#: documenterait est deja imprimee sur la planche (EPIC4-ARB-8).
PDF_NON_IDEMPOTENT_FIELDS: tuple[str, ...] = ()

#: Constat informatif: la garde de transition a refuse `-> pdf`, l'etat en
#: place a ete conserve tel quel et la commande reussit. Reimprimer une planche
#: perdue ou dechiree pour un lot deja scanne est le cas **nominal** de l'Epic
#: 5, pas une erreur: contrairement a une re-extraction, regenerer un PDF
#: n'invalide aucun artefact aval.
PDF_STATE_CONSERVED = "ETAT_DE_LOT_CONSERVE"

#: Constat informatif: un identifiant d'impression **deja persiste** differe de
#: celui qu'on vient d'imprimer. Les champs decrivent le dernier PDF reellement
#: produit -- c'est un fait, pas une faute --, mais des planches portant
#: l'ancienne valeur dans leur QR peuvent etre en circulation, et la
#: confrontation que le scan opere comparera leur QR a une valeur qui a change
#: depuis. Le constat vit sur la console de qui reimprime et au journal; il
#: n'est **pas** persiste (AC 6, tuple vide), donc le manifest ne garde aucune
#: trace de la valeur remplacee. Lever cette ambiguite a la source demanderait
#: une politique d'historisation que la story ne possede pas -- consigne au
#: `deferred-work.md`.
PDF_IDENTIFIER_DIVERGES = "IDENTIFIANT_D_IMPRESSION_DIVERGENT"

#: Vocabulaire complet des constats de ce module, tous informatifs.
PDF_PERSISTENCE_CODES: tuple[str, ...] = (
    PDF_STATE_CONSERVED,
    PDF_IDENTIFIER_DIVERGES,
)


# --------------------------------------------------------------------------
# Hierarchie d'exceptions
# --------------------------------------------------------------------------


class PdfPersistenceError(ExtractionPersistenceError):
    """Racine des erreurs de persistance d'impression.

    Sous-classe de la hierarchie de la story 3.4 pour que la CLI n'ait qu'un
    seul `except` a tenir: `ExtractionPersistenceError` est deja importee et
    capturee par `extract`.
    """


class PdfManifestAbsentError(PdfPersistenceError):
    """Aucun `project.json` lisible dans le dossier projet.

    `makepdf` refuse deja un projet sans manifest en amont; ce cas ne se
    produit donc qu'en usage direct du module, ou si le fichier disparait entre
    la validation d'entree et la fin du rendu.
    """


class PdfLotAbsentError(PdfPersistenceError):
    """Le lot vise n'existe pas dans `lots[]`, rien n'est ecrit.

    Cette story ne **cree** aucun lot: `verify_extracted_lot` garantit en amont
    que le lot existe et que ses frames correspondent. Un lot absent ici est
    donc l'indice que le manifest a change sous les pieds de la commande, pas
    un cas nominal a rattraper en fabriquant une entree.
    """


# --------------------------------------------------------------------------
# Objet d'entree, API figee
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PdfRecord:
    """Ce qu'une generation de PDF reussie declare au manifest.

    Les trois identifiants sont **lus** du plan, jamais re-resolus: un
    identifiant persiste qui divergerait de celui imprime rendrait l'expansion
    `G^-1` silencieusement fausse, sans aucun symptome a l'impression.
    """

    lot_id: str
    template_id: str
    patch_preset_id: str
    gamut_map_id: str
    #: Chemin du PDF ECRIT, relatif au projet (`EPIC11-ARB-90`). `None` quand
    #: l'appelant ne le fournit pas -- le champ est additif, et un manifeste
    #: ecrit avant cette story n'en porte aucun.
    pdf_path: str | None = None
    #: Rang de version de CE tirage (`EPIC11-ARB-91`), `None` au rang 1.
    version_rank: int | None = None

    @classmethod
    def from_plan(cls, plan: Any, *, pdf_path: str | None = None,
                  version_rank: int | None = None) -> "PdfRecord":
        """Construire l'objet depuis les attributs deja utilises pour le QR.

        Source unique (AC 7): ce sont **les memes** attributs de
        `LotComposition` qui ont alimente le payload QR et le rendu. Aucun
        appel a `resolve_patch_preset`, `get_template` ou `resolve_gamut_map`
        n'a lieu ici -- deux recettes pour un meme identifiant, c'est
        exactement la divergence que l'invariant interdit.
        """
        return cls(
            lot_id=plan.lot_id,
            template_id=plan.template_id,
            patch_preset_id=plan.patch_preset_id,
            gamut_map_id=plan.gamut_map_id,
            # Le chemin vient de l'APPELANT et non du plan: c'est lui qui
            # decide ou le fichier atterrit (`planches/` + `plan.pdf_filename`),
            # et le plan ne connait que le nom. Le deduire ici recomposerait un
            # chemin a cote de celui qui a servi a ecrire -- deux recettes pour
            # le meme fait, exactement ce que cet inventaire existe pour fermer.
            pdf_path=pdf_path,
            version_rank=version_rank,
        )


@dataclass(frozen=True)
class PdfManifestMerge:
    """Resultat de la fusion pure: le document, l'etat pose, les constats."""

    manifest: dict
    state_written: str | None
    findings: tuple[str, ...]
    diverging_fields: tuple[str, ...]


@dataclass(frozen=True)
class PersistedPdfGeneration:
    """Resultat de la persistance: ce qui a ete ecrit, et ou."""

    manifest_path: Path
    lot_id: str
    manifest: dict
    state_written: str | None
    findings: tuple[str, ...]
    diverging_fields: tuple[str, ...]


# --------------------------------------------------------------------------
# Couche pure de fusion
# --------------------------------------------------------------------------


def _merge_sheets_inventory(lot: dict, record: "PdfRecord") -> None:
    """Ajouter ce tirage a l'inventaire, ou remplacer l'entree de meme chemin.

    Fusion NON DESTRUCTIVE, appariee par `SHEETS_INVENTORY_KEY` : reimprimer
    le tirage 2 met a jour SON entree et laisse celles des tirages 1 et 3 en
    place. Ecraser l'inventaire entier ferait perdre la trace des autres
    tirages -- et cette trace n'est pas re-derivable des lors qu'un fichier a
    ete renomme, ce qui est le cas meme que cet inventaire couvre.

    TRIEE par chemin a l'ecriture : `sort_keys` canonise les mappings et pas
    les tableaux, si bien qu'un ordre d'insertion porterait l'ordre
    chronologique des impressions -- un signal d'horloge dans un document dont
    l'idempotence est verifiee octet a octet (meme motif qu'`encoded_masters`,
    story 6.5).

    Omission stricte du rang 1 : le schema pose `minimum: 2`, et l'absence dit
    deja « tirage d'origine ». Une seule convention pour le meme fait, comme
    `lots[].version_rank` et `encoded_masters[].version_rank`.
    """
    if not record.pdf_path:
        # L'appelant ne fournit pas de chemin: rien n'est ecrit, et surtout
        # rien n'est EFFACE. Un manifeste qui portait deja un inventaire ne
        # doit pas le perdre parce qu'un appelant plus ancien l'ignore.
        return
    entree: dict[str, Any] = {SHEETS_INVENTORY_KEY: record.pdf_path}
    if record.version_rank is not None:
        entree["version_rank"] = record.version_rank
    inventaire = [
        e for e in (lot.get(SHEETS_INVENTORY_FIELD) or [])
        if isinstance(e, Mapping) and e.get(SHEETS_INVENTORY_KEY) != record.pdf_path
    ]
    inventaire.append(entree)
    lot[SHEETS_INVENTORY_FIELD] = sorted(
        inventaire, key=lambda e: str(e.get(SHEETS_INVENTORY_KEY) or ""))

    # LA LIGNE D'EAU MONTE, elle ne redescend jamais ici (`EPIC11-ARB-92`).
    # C'est ce qui fait qu'un rang se CONSOMME : retirer plus tard l'entree du
    # tirage 2 ne rendra pas le rang 2 tant que le 3 existe. Sans cette
    # memoire, deux planches PAPIER differentes porteraient toutes deux « v2 »
    # -- et une fois l'encre seche, aucun fichier ne rattrape cela.
    #
    # Elle ne redescend que par un geste explicite d'`_retirer_un_tirage`, et
    # seulement en queue.
    rang_ecrit = record.version_rank or 1
    ligne = lot.get(SHEETS_WATERMARK_FIELD)
    if not isinstance(ligne, int) or isinstance(ligne, bool):
        ligne = 0
    lot[SHEETS_WATERMARK_FIELD] = max(ligne, rang_ecrit)


def _find_lot(manifest: Mapping[str, Any], lot_id: str) -> dict:
    """Rendre l'entree de `lots[]` du lot vise, ou echouer sans rien ecrire."""
    lots = manifest.get("lots")
    if not isinstance(lots, list):
        raise PdfLotAbsentError(
            "Le manifest ne porte aucune liste `lots`: impossible d'y declarer "
            f"le lot '{lot_id}'. Aucune ecriture n'a eu lieu"
        )
    for lot in lots:
        if isinstance(lot, dict) and lot.get("lot_id") == lot_id:
            return lot
    raise PdfLotAbsentError(
        f"Le lot '{lot_id}' est absent de `lots[]`: la generation de PDF ne "
        "cree aucun lot, elle met a jour une entree existante. Aucune ecriture "
        "n'a eu lieu"
    )


def _resolve_state(lot: Mapping[str, Any]) -> tuple[str, tuple[str, ...]]:
    """Poser `pdf` si la garde l'accepte, conserver l'etat en place sinon.

    La garde de `io.manifest` est le **seul** juge de l'ordre des etats: aucune
    comparaison d'index n'est reecrite ici. Sont acceptes `None -> pdf`,
    `extraction -> pdf` et `pdf -> pdf` (comparaison stricte, condition meme de
    l'idempotence); sont refuses `scan -> pdf`, `reconstruction -> pdf` et
    `encode -> pdf`.

    Un refus n'est **pas** une erreur ici, contrairement a l'extraction: une
    re-extraction reecrit les frames sous les artefacts deja produits, une
    reimpression ne touche a rien en aval. Confondre les deux rendrait
    impossible de reimprimer une planche perdue pour un lot deja scanne, le cas
    d'usage le plus banal de tout l'Epic 5.
    """
    current = lot.get("state")
    try:
        validate_lot_state_transition(current, PDF_LOT_STATE)
    except ValidationError:
        # `current` ne peut pas valoir `None` sur cette branche: la garde
        # accepte `None -> pdf` sans condition. Un refus implique donc un etat
        # reellement pose, et l'etat rendu est toujours une chaine -- d'ou le
        # type de retour, et l'absence de garde `is not None` chez l'appelant.
        return current, (PDF_STATE_CONSERVED,)
    return PDF_LOT_STATE, ()


def _diverging_identifiers(lot: Mapping[str, Any], record: PdfRecord) -> tuple[str, ...]:
    """Nommer les identifiants deja persistes que cette impression remplace.

    Seuls comptent les champs qui portaient **deja** une valeur differente. Un
    champ absent est le cas nominal de la premiere impression, pas une
    divergence.

    Amendement de l'AC 5, pose par la revue en trois couches du 2026-08-08 et
    trouve **independamment par les trois**: la story restreignait ce constat
    aux lots « au-dela de `pdf` ». C'etait exclure le cas qui le justifie le
    plus. Un lot en etat `pdf` est precisement celui dont on **sait** que des
    planches sont imprimees et pas encore numerisees; les reimprimer avec
    d'autres parametres met en circulation deux jeux de planches dont les QR se
    contredisent, et le manifest ne garde que le dernier. Le constat est donc
    emis quel que soit l'etat. Il reste sans objet a la premiere impression,
    ou aucun champ n'est encore pose.
    """
    return tuple(
        field
        for field in PDF_IDENTIFIER_FIELDS
        if field in lot and lot[field] != getattr(record, field)
    )


def build_pdf_manifest(
    existing: Mapping[str, Any], record: PdfRecord
) -> PdfManifestMerge:
    """Fusion **pure**: aucune I/O, aucune horloge, aucun acces disque.

    Le decoupage est celui de `build_extraction_manifest`, et pour la meme
    raison: l'idempotence octet a octet se teste sans toucher au disque. La
    mise a jour est faite **en place** sur l'entree de `lots[]` trouvee par
    `lot_id`; aucun autre lot, aucun rush, aucune section de tete n'est
    touche, et `created` est preserve parce que rien ne le relit ni ne le
    reecrit. Les sections `rushes`, `artifacts`, `color`, `video` et
    `reconstruction` sont recopiees telles quelles.
    """
    if not isinstance(existing, Mapping):
        # Un `project.json` qui contient `42` ou `"x"` est un JSON valide et un
        # manifest absurde. Sans cette garde, `dict(existing)` levait une
        # `TypeError` **nue**, hors de la hierarchie que la CLI capture: trace
        # Python devant l'operateur, sur le mode de panne que
        # `_load_existing_manifest` revendique justement avoir ferme pour le
        # JSON tronque (revue 5.11, couche 2).
        raise PdfManifestAbsentError(
            "Le manifest lu n'est pas un objet JSON "
            f"({type(existing).__name__}): il ne peut pas porter de `lots`. "
            "Aucune ecriture n'a eu lieu. Restaurer une copie saine du "
            "project.json"
        )

    manifest = copy.deepcopy(dict(existing))
    lot = _find_lot(manifest, record.lot_id)

    state, findings = _resolve_state(lot)
    diverging = _diverging_identifiers(lot, record)
    if diverging:
        findings = findings + (PDF_IDENTIFIER_DIVERGES,)

    lot["state"] = state
    for field in PDF_IDENTIFIER_FIELDS:
        lot[field] = getattr(record, field)
    _merge_sheets_inventory(lot, record)

    return PdfManifestMerge(
        manifest=manifest,
        state_written=state,
        findings=findings,
        diverging_fields=diverging,
    )


# --------------------------------------------------------------------------
# Couche de persistance
# --------------------------------------------------------------------------


def persist_pdf_generation(
    project_dir: str | Path, record: PdfRecord
) -> PersistedPdfGeneration:
    """Ecrire la declaration d'impression dans `<project_dir>/project.json`.

    Point d'entree unique. Appele par `makepdf` **apres** l'ecriture reussie du
    PDF, exactement comme `persist_extraction` est appelee apres l'ecriture
    reussie des TIFF: rien n'est ecrit au manifest tant que le PDF n'existe
    pas. L'ordre inverse ouvrirait un piege -- un manifest qui declare
    `state: "pdf"` pour une planche que le rendu n'a pas produite.

    Sequence: relecture (`_load_existing_manifest`), fusion pure
    (`build_pdf_manifest`), ecriture atomique validee (`_atomic_write`). Toute
    erreur laisse le `project.json` precedent **strictement intact** et ne
    laisse aucun temporaire.
    """
    project_dir = Path(project_dir)
    manifest_path = project_dir / MANIFEST_FILENAME

    existing = _load_existing_manifest(manifest_path)
    if existing is None:
        raise PdfManifestAbsentError(
            f"Aucun {MANIFEST_FILENAME} dans {project_dir}: la generation de "
            "PDF declare un lot existant, elle ne cree pas de projet. Aucune "
            "ecriture n'a eu lieu"
        )

    merge = build_pdf_manifest(existing, record)
    try:
        _atomic_write(manifest_path, merge.manifest)
    except OSError as error:
        # `_atomic_write` ouvre son temporaire **avant** son propre `try`: un
        # dossier projet non inscriptible ou un quota atteint -- le mode de
        # panne le plus probable de tout ce chemin -- remonte donc en `OSError`
        # nue, hors de la hierarchie que la CLI capture pour dire « le PDF est
        # ecrit, le project.json precedent est intact » (revue 5.11, couche 2).
        # Le defaut appartient au module de la story 3.4 et son correctif est
        # transverse (consigne au `deferred-work.md`); ici on se contente de
        # ramener l'erreur dans la bonne famille, sans la maquiller.
        raise PdfPersistenceError(
            f"Ecriture du manifest impossible: {error}. Le "
            f"{MANIFEST_FILENAME} precedent est intact"
        ) from error

    return PersistedPdfGeneration(
        manifest_path=manifest_path,
        lot_id=record.lot_id,
        manifest=merge.manifest,
        state_written=merge.state_written,
        findings=merge.findings,
        diverging_fields=merge.diverging_fields,
    )
