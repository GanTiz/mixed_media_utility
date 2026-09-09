"""Socle commun des previz jumelles (jonction ouverte par la story 5.8).

Pourquoi ce module existe
-------------------------
La famille des previz compte trois documents batis sur la meme enveloppe
``previz-1``: ``extraction_previz`` (3.5, ``kind = "extraction"``),
``pdf_previz`` (4.9, ``kind = "makepdf"``) et ``scan_previz`` (5.8,
``kind = "scan"``). La 4.9 avait deja **importe** les trois helpers de
canonicalisation de 3.5 plutot que de les recopier -- deux recettes qui
divergent sont le defaut que 3.5 avait corrige en revue -- mais elle avait
**redeclare** la validation d'horodatage UTC, faute de pouvoir elargir la liste
blanche AST des tests de 3.5 (son AC 7 interdisait de toucher a un test
existant). Cette dette a ete consignee au `deferred-work.md` le 2026-08-06,
avec un mandat explicite: « a ouvrir comme jonction chez 3.5 quand une
troisieme previz jumelle (5.8 ou 6.4) arrive ». La 5.8 est la premiere des deux
a arriver, et une **troisieme** copie de la validation d'horodatage aurait ete
l'echec de la story.

Ce que ce module possede
------------------------
La recette de canonicalisation et d'empreinte, la version de schema de
l'enveloppe, l'etat generique ``planned``, la validation d'horodatage UTC, les
gardes de type partagees par les trois documents, la garde de chemin relatif et
le controle de vocabulaire ferme. Il ne possede **aucune** charge specifique:
ni ``kind``, ni etat specialise, ni vocabulaire d'avertissements, ni champ
d'empreinte. Ceux-la appartiennent a chaque jumelle, et c'est precisement ce
qu'ARB-14 a du resorber une fois: deux vocabulaires homonymes qui divergent
coutent plus cher que deux vocabulaires nommes distinctement.

Purete
------
Meme standard que ses trois consommateurs, et pour la meme raison: si ce module
importait `cv2` ou ouvrait un fichier, les listes blanches AST des trois suites
de tests continueraient de passer tout en ne garantissant plus rien -- elles
n'inspectent que les imports **directs** de leur propre fichier. La purete de ce
module est donc verrouillee par sa propre analyse AST dans
``tests/unit/test_scan_previz.py``.

Erreurs: chacun sa hierarchie
-----------------------------
Aucune fonction de ce module ne leve d'exception qui lui soit propre. Chaque
garde recoit le type d'erreur de son appelant (``error_type``) et leve
celui-la: ``ExtractionPrevizError``, ``PdfPrevizError`` ou ``ScanPrevizError``
selon le module qui appelle. Un appelant qui attrape la hierarchie promise par
la jumelle qu'il consomme continue donc d'attraper exactement ce qu'il
attrapait avant l'extraction -- c'est la condition pour que le refactor soit
observable-neutre.

Convention d'ecriture: messages en francais **sans accents**, comme le reste de
la famille, pour survivre a une console `cp1252`.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Iterable, Sequence

from .codec_profiles import exact_frame_rate
from .numeric_guards import is_strict_int, is_strict_number
from .source_confirmation import normalize_relative_project_path

__all__ = [
    "PREVIZ_SCHEMA_VERSION",
    "PREVIZ_STATE_PLANNED",
    "FINGERPRINT_PREFIX",
    "ENVELOPE_FIELDS",
    "canonical_json",
    "fingerprint_of",
    "is_complete_fingerprint",
    "envelope_head",
    "normalize_generated_at_utc",
    "require_text",
    "optional_text",
    "require_int",
    "require_number",
    "require_relative_path",
    "optional_relative_path",
    "require_known_codes",
    "exact_rate",
]


# --------------------------------------------------------------------------
# Vocabulaire generique de l'enveloppe
# --------------------------------------------------------------------------

#: Version de structure de l'enveloppe partagee par les trois documents.
#: Independante du `schema_version` du manifest **et** de celui du payload QR:
#: la previz n'est pas persistee et evoluera au rythme de la GUI, pas a celui
#: du contrat de portabilite. Les melanger ferait perimer un document pour une
#: raison qui ne le concerne pas.
PREVIZ_SCHEMA_VERSION = "previz-1"

#: Seul etat **generique** de la famille: « rien n'a encore ete produit ». Les
#: etats d'aboutissement sont specifiques au kind (`extracted` pour 3.5,
#: `rendered` pour 4.9, `reconstructed` pour 5.8), precedent pose par 4.9.
PREVIZ_STATE_PLANNED = "planned"

#: Prefixe de recette d'empreinte, porteur de la version d'algorithme -- meme
#: forme que `lots[].frame_timecodes_digest` (story 3.4), et **non comparable**
#: a lui pour autant: deux recettes qui partagent un prefixe ne canonicalisent
#: pas la meme chose.
FINGERPRINT_PREFIX = "sha256-v1:"

#: Les champs de tete de l'enveloppe `previz-1`, dans l'ordre ou les trois
#: documents les rendent. Exportes pour qu'un test puisse verifier qu'une
#: jumelle n'en omet ni n'en invente aucun.
ENVELOPE_FIELDS: tuple[str, ...] = (
    "previz_schema_version",
    "kind",
    "state",
    "generated_at_utc",
)

# Forme **complete** d'une empreinte a la recette de la famille: prefixe suivi
# de 64 hexadecimaux. Le prefixe seul (digest vide ou non hexadecimal) n'est
# comparable a rien et ne perimerait jamais correctement (revue 4.9).
_FINGERPRINT_RE = re.compile(rf"^{re.escape(FINGERPRINT_PREFIX)}[0-9a-f]{{64}}$")

# `generated_at_utc`: ISO 8601 UTC, suffixe `Z` obligatoire. Un horodatage local
# sans fuseau rendrait la fraicheur ininterpretable d'une machine a l'autre. La
# valeur est FOURNIE par l'appelant: l'horloge n'entre pas dans un module dont
# le contrat exige que deux appels sur les memes entrees produisent le meme JSON
# octet pour octet.
_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


# --------------------------------------------------------------------------
# Canonicalisation et empreintes -- point unique de la famille
# --------------------------------------------------------------------------


def canonical_json(obj: Any) -> str:
    """Serialisation canonique, **unique** point de canonicalisation.

    `sort_keys` rend l'ordre d'insertion sans effet, `ensure_ascii` rend la
    sortie insensible a l'encodage du terminal, `separators` retire tout espace
    optionnel: deux processus distincts produisent la meme chaine octet pour
    octet.

    `allow_nan=False` refuse `NaN` et `Infinity`, que `json.dumps` emet par
    defaut et qu'**aucun** parseur JSON strict n'accepte: le document serait
    illisible chez son destinataire, et l'empreinte calculee dessus scellerait
    une chaine invalide. Le chemin est joignable: `json.loads` accepte ces
    litteraux a la lecture d'une sonde ffprobe, et la valeur traverse ensuite le
    rapport source sans jamais etre retypee (revue du 2026-08-05).
    """
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def fingerprint_of(obj: Any) -> str:
    """Empreinte `sha256-v1:` de la serialisation canonique de `obj`."""
    digest = hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
    return f"{FINGERPRINT_PREFIX}{digest}"


def is_complete_fingerprint(value: Any) -> bool:
    """Dire si `value` porte une empreinte de la famille sous forme complete.

    Rend un booleen et ne leve rien: c'est l'appelant qui decide du message et
    de la hierarchie d'erreur, parce que la phrase utile depend de ce que
    l'empreinte transportee est censee designer.
    """
    return isinstance(value, str) and bool(_FINGERPRINT_RE.fullmatch(value))


def envelope_head(
    *,
    kind: str,
    state: str,
    generated_at_utc: str,
    schema_version: str,
) -> dict[str, Any]:
    """Les quatre champs de tete de l'enveloppe `previz-1`, une seule fois.

    Socle d'enveloppe generique reclame par la note differee: les trois
    documents ecrivaient ces quatre paires a l'identique, et un renommage de
    champ d'enveloppe devait etre repercute a trois endroits pour rester
    coherent.

    `schema_version` est un **parametre** et non une constante relue: un
    document se rend tel qu'il a ete construit. Relire la constante ferait
    mentir un document fige sous une version anterieure -- exactement ce que la
    version d'enveloppe existe pour signaler.

    Il est **obligatoire** et sans defaut (revue 5.8, couche 1 F2): la premiere
    version de cette fonction lui donnait `PREVIZ_SCHEMA_VERSION` pour defaut,
    c'est-a-dire qu'un site d'appel qui oubliait l'argument relisait la
    constante -- exactement ce que la docstring ci-dessus interdit, sans rien
    lever ni casser. La regle passe ainsi du commentaire au type: un appel
    incomplet est un `TypeError` a l'import du test, pas un document qui ment.
    """
    return {
        "previz_schema_version": schema_version,
        "kind": kind,
        "state": state,
        "generated_at_utc": generated_at_utc,
    }


# --------------------------------------------------------------------------
# Gardes partagees -- chacune leve la hierarchie de son appelant
# --------------------------------------------------------------------------


def require_text(value: Any, label: str, *, error_type: type[Exception]) -> str:
    """Chaine non vide, ou refus."""
    if not isinstance(value, str) or not value:
        raise error_type(f"{label} doit etre une chaine non vide, recu {value!r}")
    return value


def optional_text(value: Any, label: str, *, error_type: type[Exception]) -> str | None:
    if value is None:
        return None
    return require_text(value, label, error_type=error_type)


def require_int(value: Any, label: str, *, error_type: type[Exception]) -> int:
    """Entier strict, `bool` exclu.

    La garde `bool`-avant-`int` est l'action item 2 de la retrospective de
    l'Epic 4: `isinstance(True, int)` vaut vrai en Python, si bien qu'un `True`
    glisse dans un compteur traversait toutes les gardes et ressortait `true`
    dans le JSON, la ou un cardinal etait attendu. Elle vit **ici**, dans le
    seul domicile que les trois documents partagent, plutot qu'en trois
    exemplaires dont un seul aurait pu etre corrige.
    """
    if not is_strict_int(value):
        raise error_type(f"{label} doit etre un entier, recu {value!r}")
    return value


def require_number(value: Any, label: str, *, error_type: type[Exception]):
    """Nombre transporte verbatim (jamais converti), type controle.

    Sans cette garde, une chaine ou un `Decimal` dans une geometrie traversait
    la construction et n'explosait qu'au `json.dumps` du consommateur, hors de
    la hierarchie d'erreur promise (revue 4.9). Meme garde `bool`-avant-`int`
    que ci-dessus.
    """
    if not is_strict_number(value):
        raise error_type(f"{label} doit etre un nombre, recu {value!r}")
    return value


def require_relative_path(
    value: Any, label: str, *, error_type: type[Exception]
) -> str:
    """Chemin relatif au dossier projet, ou refus.

    Delegue a `source_confirmation.normalize_relative_project_path`, **point
    unique** de cette regle dans le depot: la reimplementer -- ce que faisait la
    premiere version de 3.5, en se contentant d'un « chaine non vide » --
    revient a ne pas la tenir du tout (revue du 2026-08-05). Elle couvre la
    forme Windows (`C:\\...`), invisible a `PurePosixPath`, et la remontee
    `..`, aussi destructrice qu'un chemin absolu.

    La fonction deleguee leve `ValueError`; le message est repris tel quel dans
    la hierarchie de l'appelant, de sorte que le texte du refus ne change pas.
    """
    text = require_text(value, label, error_type=error_type)
    try:
        return normalize_relative_project_path(text, label)
    except ValueError as exc:
        raise error_type(str(exc)) from exc


def optional_relative_path(
    value: Any, label: str, *, error_type: type[Exception]
) -> str | None:
    if value is None:
        return None
    return require_relative_path(value, label, error_type=error_type)


def normalize_generated_at_utc(
    value: Any,
    *,
    error_type: type[Exception],
    example: str,
) -> str:
    """Horodatage UTC ISO 8601 suffixe `Z`, designant un instant reel.

    Regle unique de la famille, extraite de ses deux copies inline
    (`extraction_previz` et `pdf_previz`) par la story 5.8. Deux gardes, et pas
    une:

    * `fullmatch` et non `match`: en mode non multiligne, `$` accepte encore un
      saut de ligne final, donc `"2026-08-04T09:30:00Z\\n"` passait la garde et
      le `\\n` entrait dans le document (revue du 2026-08-05);
    * le motif ne contraint que la **forme**: `2026-02-30T25:61:61Z` la respecte
      et ne designe aucun instant. Un document de fraicheur date d'un jour qui
      n'existe pas ne peut pas etre compare a l'heure courante.

    `example` n'entre que dans le message de refus: les deux jumelles citaient
    chacune une date d'exemple differente, et les conserver garde le texte des
    refus rigoureusement inchange.
    """
    generated = require_text(value, "generated_at_utc", error_type=error_type)
    if not _UTC_TIMESTAMP_RE.fullmatch(generated):
        raise error_type(
            "generated_at_utc doit etre un horodatage UTC ISO 8601 suffixe 'Z' "
            f"(ex. '{example}'), recu {value!r}"
        )
    try:
        datetime.strptime(generated.split(".")[0].rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise error_type(
            f"generated_at_utc ne designe aucun instant reel: {value!r}"
        ) from exc
    return generated


def require_known_codes(
    codes: Sequence[str],
    vocabulary: Iterable[str],
    *,
    label: str,
    error_type: type[Exception],
) -> tuple[str, ...]:
    """Vocabulaire ferme: un code hors du tuple est refuse a la construction.

    `label` porte la phrase d'ouverture du refus, differente d'une jumelle a
    l'autre (« Code d'avertissement de previz inconnu », « ... de previz PDF
    inconnu »): la partager telle quelle aurait fait dire a un module le nom
    d'un autre.
    """
    known = tuple(vocabulary)
    unknown = [code for code in codes if code not in known]
    if unknown:
        raise error_type(
            f"{label}: "
            f"{', '.join(repr(code) for code in unknown)}. Vocabulaire ferme: "
            f"{', '.join(known)}"
        )
    return tuple(codes)


def exact_rate(fps: Any, *, error_type: type[Exception]) -> str:
    """Seule forme canonique de cadence de la famille.

    Chaine `"num/den"` a denominateur toujours explicite (`"30/1"`,
    `"24000/1001"`), rendue par `codec_profiles.exact_frame_rate`. Jamais
    `str(Fraction)` (qui rend `"30"`), jamais un flottant: deux recettes
    produiraient deux empreintes pour la meme cadence, et un consommateur qui
    les compare conclurait a tort a une peremption.
    """
    try:
        return exact_frame_rate(fps)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError) as error:
        raise error_type(f"Cadence inexploitable: {fps!r} ({error})") from error
