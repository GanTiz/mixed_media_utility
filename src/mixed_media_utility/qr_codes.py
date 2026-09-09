"""QR rendering and decoding for the printable patch sheet (story 4.6).

Scope, after the 2026-08-02 review: this module owns **only** the raster side
of the QR code -- encoding a payload string into a symbol, rendering it at a
print size/DPI, and decoding a (possibly degraded) scan. It deliberately owns
neither the payload schema nor the short-id derivation:

- payload schema / validation / budget: ``io.payload`` (story 2.3, Epic 2).
- short ``project_id``/``rush_id`` derivation: ``io.naming.derive_short_id``.

Both used to be duplicated here with a *different* format and a *different*
hash, which made the printed QR and the printed filename disagree -- so the
"fall back on the filename when the QR is unreadable" safety net (AC 4) could
not work by construction. See ``decisions-2026-08-02.md``, decisions 1 and 2.

Everything the OpenCV API lets through silently or fatally is guarded here:
an out-of-range correction level segfaulted the process, a payload holding
surrogates segfaulted the encoder, an oversized payload raised a raw
``cv2.error``, and the decoder reported the same empty string for "no symbol
on this page", "symbol present but unreadable" and "two symbols in frame" --
three situations calling for three different operator actions.

**Depuis le 2026-09-06 (`EPIC11-ARB-250`), les deux roles sont dissocies : on
ENCODE par `segno`, on DETECTE et on DECODE par OpenCV.** Mesure de
`mesure-2026-09-06-plancher-opencv-et-rendu-qr.md` : la ligne 4.10/4.11
d'OpenCV produit un symbole malforme au-dela de la version 7 -- illisible par
tout lecteur, y compris par une version ulterieure d'OpenCV et par
`zxing-cpp`. Le papier est perdu au moment de l'impression, pas au moment du
scan. Son DETECTEUR, lui, est sain sur ces memes versions : les quatre
captures reelles de `tests/fixtures/qr_300dpi/` rendent des verdicts
identiques sous 4.10 et sous 5.0.

Pourquoi `segno` plutot qu'un plancher de version : `4.10.0.84` est la
DERNIERE version d'`opencv-contrib-python` portant une roue
`macosx_12_0_x86_64`, donc tout plancher au-dessus sortait la machine de
reference de la compatibilite. `segno` publie une roue `py3-none-any`, sans
etiquette de plateforme et sans dependance a l'execution : la question du
plancher disparait avec l'encodeur binaire qui la posait.

Et parce que la bascule ferme le defaut CONNU sans rien dire de ceux qui
restent, `encode_qr_image` **relit son propre symbole et avertit** quand il ne
se relit pas (`EPIC11-ARB-251`). Elle n'echoue pas : meme famille
qu'`EPIC11-ARB-89`, un refus qui n'offre aucune issue est aussi fautif qu'une
destruction silencieuse.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np
import segno

from .io.payload import ALERT_BUDGET_BYTES, NOMINAL_BUDGET_BYTES
from .numeric_guards import is_strict_int

#: Le canal d'avertissement du coeur est le journal, comme dans `scan_detect`
#: et `encode_master` : ni `warnings.warn` (que personne n'ecoute ici) ni un
#: champ de resultat (la signature d'`encode_qr_image` rend un raster, et elle
#: ne change pas).
_journal = logging.getLogger(__name__)

# --- Print/scan geometry, re-measured 2026-08-03 --------------------------
#
# The physically meaningful variable is **pixels per module at scan time**,
# not the printed size: size_mm and dpi only ever act through their product,
# so a threshold stated in mm is meaningless without its DPI. Measured on the
# rebuilt bench (`temp/qr_experiment_results.md`, 1620 decodes, both
# detectors, 3 degradation classes) the relationship is monotonic:
#
#   px/module | clean | mild | harsh   (worst of the 2 detectors)
#   ----------|-------|------|------
#   2-3       |  ~20% |   0% |   0%
#   3-4       |  ~30% | ~25% |   0%
#   4-5       |  ~40% | ~48% |   4%
#   6-7       |  ~43% | ~57% |  51%
#   8-9       |  100% | 100% | 100%
#
# Below 5 px/module the code is unusable whatever the ECC level; at >= 8 every
# cell decodes, in every degradation class, with both detectors.
MIN_PIXELS_PER_MODULE_RELIABLE = 8.0
MIN_PIXELS_PER_MODULE_DEGRADED = 6.0

# Consequence for the printed sheet, with the **production** payload schema
# (`io.payload`): a 512-byte payload at ECC M encodes to 93 modules, so
# reaching 8 px/module needs 63 mm at 300 dpi -- not printable next to two
# frame zones on A4 -- or 31.5 mm at 600 dpi. The previous "300 dpi minimum"
# hypothesis is therefore **refuted at the target print size**: 30 mm at
# 300 dpi yields 3.81 px/module and measured 0/5 under `harsh`.
QR_MIN_SCAN_DPI = 600

# 35 mm at 600 dpi = 8.89 px/module for the nominal payload: 5/5 in every
# degradation class with both detectors. 30 mm at the same DPI = 7.62
# px/module, which still measured 5/5 on the nominal payload but sits below
# the reliable threshold, so it is the degraded-margin fallback -- not an
# interchangeable minimum. Prefer `required_print_size_mm()` over these
# constants: it sizes the code from the payload actually being printed.
QR_PRINT_SIZE_TARGET_MM = 35.0
QR_PRINT_SIZE_FALLBACK_RISK_MM = 30.0

# Page capacity at the production schema, measured: the nominal 512-byte
# budget holds **11 slots** per page and the 768-byte ceiling holds 20. The
# previous bench measured a private schema ~2.8x lighter and so overstated
# this (see decisions-2026-08-02.md, decision 1).
#
# The nominal figure dropped from 5 to 4 in story 5.9: `gamut_map_id` costs a
# flat 34 bytes (18 for the JSON fragment + 16 for `gamut-map-none-1`) and a
# 5-slot page went from 493 to 527 bytes -- over the soft budget. That is the
# real price of a field described as "purely additive": nil on content, not
# nil on what gets printed.
#
# **Recalcule par la story 5.17** (cles courtes du payload, `EPIC5-ARB-60`):
# 4 -> 11 au budget nominal et 10 -> 20 au plafond dur.
#
# **Regime nomme, parce qu'un seul caractere le deplace** (revue de 5.17, majeur M4):
# `demo-project-01` / `rush-a1` / `lot-0007`, `tpl-a4-portrait-2f-v1`,
# `patches-12-v1`, `gamut-map-none-1`, `target_colorspace = "rec709"` -- celui de la
# production (`cli.MVP_TARGET_COLORSPACE`) --, `page_index = 0`, `page_count = 1`,
# `fps_target = 24.0`, timecodes `00:00:00:00`, 1 a 21 emplacements. Re-mesure sur un
# payload reellement serialise, cles courtes:
#   10 slots 472 | 11 slots 501 | 12 slots 530 | 20 slots 762 | 21 slots 791
#
# **Recalcule une seconde fois par la story 5.16** (role de page, `EPIC5-ARB-54`), dans
# le meme regime, le payload gagnant le fragment `,"pr":"i"` -- 9 octets, uniformement:
#   10 slots 481 | 11 slots 510 | 12 slots 539 | 20 slots 771 | 21 slots 800
# Le repere du budget nominal ne bouge pas -- 11 emplacements, 510 octets pour 512 --,
# mais sa marge tombe de 11 octets a **2**. Celui du plafond dur tombe de **20 a 19**:
# le vingtieme emplacement passe de 762 a 771 pour un plafond de 768. Les 9 octets d'un
# champ scalaire d'un caractere suffisent donc a deplacer un repere, ce qui est la
# raison pour laquelle ces deux nombres sont recalcules par un test a chaque execution
# et non recopies.
# et, **dans le meme regime**, la forme a cles longues qui precedait, pour que la paire
# soit comparable:
#   10 slots 768 | 11 slots 817 | 12 slots 866 | 20 slots 1258 | 21 slots 1307
#
# Les chiffres « avant » que ce bloc remplacait (4 slots 479 | 5 slots 527 |
# 10 slots 767 | 11 slots 816) sont ceux du meme balayage a
# `target_colorspace = "bt709"`, un caractere plus court -- d'ou l'octet d'ecart. Sous
# `rec709` ils valent 480 | 528 | 768 | 817. C'est tout l'objet de la mention du
# regime: un lecteur qui compare les deux colonnes sans lui croit mesurer l'effet des
# cles courtes et mesure en partie autre chose.
#
# Le cout marginal est de 28 octets par emplacement, 29 des que `slot_index` passe a
# deux chiffres (a partir de l'index 10). Ce n'est **pas** ce qui fixe la frontiere
# 11/12: a 11 emplacements il reste 11 octets sous le budget nominal, et un douzieme le
# depasse quel que soit son cout -- 501 + 28 = 529 comme 501 + 29 = 530, les deux
# au-dela de 512. La frontiere vient du cumul, pas de l'octet du second chiffre
# (majeur M5: la parenthese causale qui figurait ici etait fausse).
#
# **Consequence produit, et elle sort du perimetre de cette story**: le payload
# cesse d'etre ce qui borne le nombre de frames par page (11 emplacements
# atteignables au budget nominal contre 4, la ou les gabarits vont jusqu'a 8).
# La contrainte devient geometrique et non plus informationnelle. Le vocabulaire
# des cardinaux ne change pas ici: c'est `EPIC5-ARB-62`, apres la passe de
# design.
#
# Both remain documentary: the guard is `check_payload_budget`, which measures
# the payload actually being serialised, never these constants.
SLOTS_PER_PAGE_AT_NOMINAL_BUDGET = 11
SLOTS_PER_PAGE_AT_ALERT_BUDGET = 19

GEOMETRY_RELIABLE = "reliable"
GEOMETRY_DEGRADED = "degraded"
GEOMETRY_UNUSABLE = "unusable"

# --- Version du symbole, et la version bannie (story 5.17) -----------------
#
# ISO/IEC 18004: la version `V` d'un symbole a `4V + 17` modules de cote, de la
# version 1 (21 modules) a la version 40 (177). La relation est exacte et sans
# exception, donc le cote de symbole rendu par l'encodeur **est** la version.
QR_SYMBOL_VERSION_MIN = 1
QR_SYMBOL_VERSION_MAX = 40
_MODULES_PER_VERSION = 4
_MODULES_AT_VERSION_ZERO = 17

#: Versions de symbole que la chaine de production refuse d'imprimer, **quelle que
#: soit la taille imprimee**.
#:
#: **La version 22 (105 modules) n'est decodee par `QRCodeDetectorAruco` -- le
#: detecteur par defaut de production -- a AUCUNE taille imprimee, sur un rendu
#: parfait**, et cela sur cinq charges utiles distinctes. Les versions 21 (101
#: modules) et 23 (109) se decodent dans les memes conditions: ce n'est donc ni un
#: plafond de resolution ni un plafond de version, c'est la v22 en propre. Mesure:
#: `analyse-2026-08-11-qr-version-22-indecodable.md`.
#:
#: Avant cette garde, `check_print_geometry` ne regardait que le ratio px/module et
#: classait donc `reliable` un symbole indecodable: une page a 8 frames se composait
#: **sans un mot d'avertissement** et rendait une planche dont le QR ne se relit pas.
#:
#: Les cles courtes de la story 5.17 sortent le vocabulaire des cardinaux de ce
#: regime (le pire cardinal passe de 105 a 85 modules), et **c'est precisement
#: pourquoi cette garde doit exister quand meme**: elles eloignent le domaine du
#: piege, elles ne le suppriment pas. Un champ ajoute au payload y ramenerait le
#: cardinal 8, et sans cette liste le defaut reviendrait a l'identique et sans un mot.
QR_BANNED_SYMBOL_VERSIONS = frozenset({22})

# ISO/IEC 18004 exige >= 4 modules de zone de silence. `render_for_print` les
# ajoute, et toute transformation geometrique appliquee ensuite doit les
# preserver (une rotation dans un canevas fixe l'avait rongee a ~1 module, ce
# qui est une violation de la norme et non une degradation de scan).
#
# **Corrige le 2026-09-06 (`EPIC11-ARB-252`).** Cette place portait « OpenCV's
# encoder does not emit one », et c'etait faux depuis toujours : le raster
# natif de l'encodeur d'OpenCV porte une marge blanche de 2 modules sur les
# quatre bords, mesure invariant a six tailles. C'est cette phrase fausse qui a
# fait ecrire une DEDUCTION (`symbol_version`) la ou il fallait une mesure, et
# le decalage de +1 qu'elle produit est en dette (`ARB252-N1`). Le raster de
# `segno` est nappe de la meme marge -- voir `MARGE_NATIVE_MODULES` -- pour que
# la bascule d'encodeur soit NEUTRE sur toute la geometrie d'impression.
QUIET_ZONE_MODULES = 4

# Ceiling on the intermediate supersampled raster side. A 35 mm / 600 dpi
# nominal page needs ~950 px; anything past this is a unit mix-up (metres for
# millimetres, or a DPI typo), which used to surface as an out-of-memory
# cv2.error naming nothing.
MAX_RENDER_SIDE_PX = 20000

# --- Niveaux de correction d'erreur ---------------------------------------
#
# Le vocabulaire du depot est celui d'OpenCV : un ENTIER, 0=L, 1=M, 2=Q, 3=H.
# Il traverse la ligne de commande et un `patch_preset_id` versionne, donc il
# ne se renomme pas ici -- ce serait casser un contrat externe pour un confort
# interne.
#
# Ces quatre valeurs sont ecrites en clair plutot que lues de l'encodeur
# d'OpenCV, qui n'est plus la (`EPIC11-ARB-250`), et `tests/unit/test_qr_codes.py`
# les CONFRONTE aux constantes reelles d'OpenCV dans les deux sens : ce qui etait
# une dependance devient une mesure, et une inversion L/H se voit au lieu de
# passer.
CORRECTION_LEVEL_L = 0
CORRECTION_LEVEL_M = 1
CORRECTION_LEVEL_Q = 2
CORRECTION_LEVEL_H = 3

# Bornes du niveau. Elles etaient posees parce qu'OpenCV ne rejetait pas les
# valeurs hors bornes -- 99 tuait le process par SIGSEGV, 1000 le faisait
# tourner sans fin. Ce motif-la disparait avec l'encodeur d'OpenCV; la garde,
# elle, reste (voir `check_correction_level`).
CORRECTION_LEVEL_MIN = CORRECTION_LEVEL_L
CORRECTION_LEVEL_MAX = CORRECTION_LEVEL_H

#: Correspondance ENTIER (vocabulaire du depot) -> lettre attendue par `segno`.
#:
#: Nommee et exhaustive plutot que calculee : une table de quatre entrees se
#: mesure entree par entree, alors qu'une indexation dans `"lmqh"` ne se
#: mesure que par ses bords, et une inversion L/H y passe inapercue. Le banc
#: la parcourt dans les quatre sens (entier -> lettre, lettre -> entier,
#: exhaustivite, et le niveau reellement porte par le symbole produit).
_NIVEAU_ECC_VERS_SEGNO: dict[int, str] = {
    CORRECTION_LEVEL_L: "l",
    CORRECTION_LEVEL_M: "m",
    CORRECTION_LEVEL_Q: "q",
    CORRECTION_LEVEL_H: "h",
}

#: Marge blanche, en modules, que le raster NATIF porte sur ses quatre bords.
#:
#: **C'est la condition de surete de la bascule d'encodeur** (`EPIC11-ARB-250`).
#: L'encodeur d'OpenCV emettait cette marge lui-meme, mesuree invariante a six
#: tailles; `segno.make(...).matrix` rend la matrice NUE. Sans ce nappage, le
#: cote du raster perdrait 4 modules, et le cote gouverne `pixels_per_module`,
#: donc `required_print_size_mm`, donc l'emprise du QR sur la planche, donc les
#: gabarits et les seuils de calibration. Un module d'ecart casse la geometrie
#: d'impression du produit entier.
#:
#: Avec ce nappage, les deux encodeurs rendent le MEME cote -- mesure aux huit
#: tailles de reference (150, 170, 181, 256, 320, 380, 452, 560 octets, ECC M ->
#: 53, 57, 61, 69, 73, 81, 89, 93) et sur un balayage des quatre niveaux ECC.
#: `test_qr_codes.py` tient cette egalite cote a cote.
#:
#: Elle n'est PAS la zone de silence ISO : `QUIET_ZONE_MODULES` (4) s'ajoute
#: par-dessus au rendu. Deux modules ne suffiraient pas a la norme.
MARGE_NATIVE_MODULES = 2

# Error-correction default. The "higher ECC is more fragile at a fixed printed
# size" rationale predicts a monotonic M > Q > H robustness ordering, which the
# original bench never showed (Q failed *between* M and H, both succeeding, on
# a perfectly clean render) -- that inversion was the fractional-module
# rendering artifact, not optics. On the rebuilt bench the ordering is
# monotonic and the rationale holds, so the conclusion the story already drew
# is now also the default it ships:
#
#   ECC | classic  | aruco     (same geometry, 512-byte payload -> modules)
#   ----|----------|---------
#   M   | 153/270  | 194/270   (93 modules)
#   Q   |  67/270  | 183/270   (109 modules)
#   H   |  79/270  | 141/270   (121 modules)
#
# The previous default was Q, i.e. the story shipped the opposite of its own
# conclusion.
DEFAULT_CORRECTION_LEVEL = CORRECTION_LEVEL_M

# Decoder is an explicit axis, not a hidden constant: the mm/DPI/ECC limits
# published by story 4.6 were measured with `QRCodeDetector` alone, so they
# described that decoder rather than the paper. Measured over the whole bench
# (270 decodes per cell group), `QRCodeDetectorAruco` wins everywhere:
#
#   printed size | classic | aruco
#   -------------|---------|-------
#   25 mm        |  81/270 | 129/270
#   30 mm        | 103/270 | 181/270
#   35 mm        | 115/270 | 208/270
#
# The gap is not limited to degraded images: on a pristine render of the
# nominal payload at 9.29 px/module, the classic detector *locates* the symbol
# and fails to decode it, while the ArUco-based one decodes it every time. The
# default follows the measurement.
DETECTOR_CLASSIC = "classic"
DETECTOR_ARUCO = "aruco"
DEFAULT_DETECTOR = DETECTOR_ARUCO

# Decode outcomes. The distinction matters operationally: "rescan at a higher
# resolution" and "you scanned the wrong document" are opposite instructions.
DECODE_OK = "decoded"
DECODE_NO_SYMBOL = "no_symbol_detected"
DECODE_UNREADABLE = "detected_but_unreadable"
DECODE_MULTIPLE = "multiple_symbols"

# Known methodology limit: the bench simulates degradation (blur, noise, JPEG
# recompression, rotation) on a synthetic render. It models neither ink
# dot-gain, halftoning, nor a hardware decoder's binarization. Treat every
# mm/DPI/ECC threshold as simulation-backed, not field-proven, and keep the
# margin rather than the bare passing combination.


class QRPayloadTooLarge(ValueError):
    """Raised when a payload cannot be encoded within the QR size guard-rails."""


class QRRenderError(ValueError):
    """Raised when the requested print geometry cannot produce a valid raster."""


@dataclass(frozen=True)
class QRDecodeResult:
    """Outcome of a decode attempt.

    ``text`` is the decoded payload, empty unless ``status`` is ``DECODE_OK``.
    ``status`` is one of the ``DECODE_*`` constants and ``symbol_count`` is how
    many QR symbols the detector located, so a caller can tell a blank page
    from an unreadable code from a two-up sheet.
    """

    text: str
    status: str
    symbol_count: int

    @property
    def ok(self) -> bool:
        return self.status == DECODE_OK


def payload_size_bytes(text: str) -> int:
    """Return the UTF-8 byte size of a payload string.

    Raises ``ValueError`` on a string that cannot be encoded to UTF-8 -- a
    ``str`` holding surrogates, as produced by ``os.fsdecode`` on a non-UTF-8
    filename (a rush copied from a latin-1 volume). Left unguarded this raised
    an undocumented ``UnicodeEncodeError`` here and segfaulted the encoder.
    """
    return len(_encode_utf8(text))


def _encode_utf8(text: str) -> bytes:
    if not isinstance(text, str):
        raise TypeError(f"Payload QR attendu de type str, recu: {type(text).__name__}")
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "Payload QR non encodable en UTF-8 (surrogates issus d'un nom de fichier "
            f"non-UTF-8 ?): {exc}"
        ) from exc


def check_correction_level(correction_level: int) -> int:
    """Tenir la plage ECC valide avant qu'elle n'atteigne l'encodeur.

    **Docstring reecrit le 2026-09-06 : sa justification d'origine est
    perimee.** Elle disait que les valeurs hors bornes tuaient le process
    (SIGSEGV) ou le faisaient tourner sans fin -- vrai de l'encodeur d'OpenCV,
    qui n'encode plus rien ici depuis `EPIC11-ARB-250`. Laisser une raison
    fausse en place est ce que ce depot paie le plus cher : c'est exactement
    ainsi que la phrase « OpenCV's encoder does not emit a quiet zone » a
    survecu des mois et fabrique le decalage d'`EPIC11-ARB-252`.

    Ce qui est vrai maintenant, et qui suffit a garder la garde :

    * `_NIVEAU_ECC_VERS_SEGNO` est une table de QUATRE entrees. Un niveau hors
      bornes y leverait un `KeyError` nu, qui ne nomme ni le parametre, ni la
      plage attendue, ni le fait que le vocabulaire est celui d'OpenCV ;
    * le niveau vient d'une donnee EXTERNE -- un `patch_preset_id` versionne,
      une valeur de ligne de commande --, donc d'une source que ce module ne
      controle pas. Une garde de frontiere se pose ou la donnee entre ;
    * le refus est TYPE : `TypeError` sur ce qui n'est pas un entier strict
      (`True` est un `int` pour Python, pas un niveau ECC), `ValueError` sur un
      entier hors plage. Les appelants sont ecrits contre ces deux-la.
    """
    if not is_strict_int(correction_level):
        raise TypeError(
            f"correction_level doit etre un entier, recu: {type(correction_level).__name__}"
        )
    if not CORRECTION_LEVEL_MIN <= correction_level <= CORRECTION_LEVEL_MAX:
        raise ValueError(
            f"correction_level hors bornes: {correction_level}. "
            f"Attendu entre {CORRECTION_LEVEL_MIN} (L) et {CORRECTION_LEVEL_MAX} (H)."
        )
    return correction_level


#: Regime de la relecture de controle (`EPIC11-ARB-251`), et il est mesure.
#:
#: Zone de silence de 4 modules et agrandissement ENTIER au plus proche voisin
#: -- c'est-a-dire ce que `render_for_print` garantit, en plus simple. Le
#: facteur 4 est le plus petit qui ne fabrique aucune fausse alerte : mesure
#: sur 120 symboles (quatre niveaux ECC x 30 tailles de 20 a 768 octets),
#: `decode_qr_image_resilient` rend 0 fausse alerte a x4, x5 et x6, la lecture
#: directe en rend 1 a x4. Le cout moyen mesure est de 18,5 ms a x4 contre
#: 23,8 ms a x5 : x4 est le regime le moins cher a fausse alerte nulle.
_RELECTURE_ZONE_DE_SILENCE_MODULES = 4
_RELECTURE_FACTEUR = 4


def encode_qr_image(
    payload: str,
    correction_level: int = DEFAULT_CORRECTION_LEVEL,
) -> np.ndarray:
    """Encoder ``payload`` en raster QR a resolution native (1 px/module).

    Rend un tableau ``uint8`` monocanal (0/255) au cote natif du symbole,
    marge de `MARGE_NATIVE_MODULES` comprise et sans zone de silence ISO ;
    passer par :func:`render_for_print` pour obtenir un raster imprimable.

    Gardes, dans l'ordre : le niveau ECC doit etre dans la plage, la charge
    utile doit etre encodable en UTF-8 et non vide, et sa taille doit rester
    sous le plafond d'alerte d'``io.payload`` -- au-dela la planche
    s'imprimait avec un QR hors de toute hypothese de taille/ppp validee.

    **L'encodeur est `segno`** (`EPIC11-ARB-250`), pas celui d'OpenCV, qui rend
    un symbole malforme au-dela de la version 7 sur sa ligne 4.10/4.11. Trois
    reglages sont liants, et chacun se mesure :

    * ``boost_error=False`` -- `segno` remonte le niveau ECC de lui-meme quand
      la place le permet. Ce serait changer le symbole sans qu'on le demande,
      et le niveau demande est celui d'un `patch_preset_id` versionne ;
    * ``micro=False`` -- sans lui, une charge utile de 1 ou 2 octets rend un
      Micro QR (`M2`/`M3`, cote 17 ou 19) la ou l'encodeur d'OpenCV rendait un
      symbole de version 1 (cote 25). C'est une rupture de geometrie que le
      seul balayage des tailles de production n'aurait pas vue ;
    * ``mode`` laisse a l'automatique -- l'encodeur d'OpenCV optimise lui aussi
      le mode. Forcer ``"byte"`` gonflerait une charge utile numerique de
      37 a 49 modules de cote, mesure.

    Puis le symbole est **relu** et un ecart est **journalise** sans bloquer
    (`EPIC11-ARB-251`) : voir :func:`_avertir_si_le_symbole_ne_se_relit_pas`.
    """
    check_correction_level(correction_level)
    size_bytes = payload_size_bytes(payload)
    if size_bytes == 0:
        raise ValueError("Payload QR vide: rien a encoder.")
    if size_bytes > ALERT_BUDGET_BYTES:
        raise QRPayloadTooLarge(
            f"Payload de {size_bytes} octets au-dessus du plafond dur de "
            f"{ALERT_BUDGET_BYTES} octets (budget nominal {NOMINAL_BUDGET_BYTES}). "
            "Reduire le nombre de slots par page."
        )

    try:
        symbole = segno.make(
            payload,
            error=_NIVEAU_ECC_VERS_SEGNO[correction_level],
            boost_error=False,
            micro=False,
        )
    except segno.DataOverflowError as exc:  # capacite depassee pour ce niveau ECC
        raise QRPayloadTooLarge(
            f"Payload de {size_bytes} octets non encodable au niveau ECC "
            f"{correction_level}: {exc}"
        ) from exc

    natif = _raster_natif(symbole)
    _avertir_si_le_symbole_ne_se_relit_pas(natif, payload, correction_level)
    return natif


def _raster_natif(symbole: segno.QRCode) -> np.ndarray:
    """Rendre la matrice de ``symbole`` au format du raster natif du depot.

    Deux conversions, et les deux sont mesurees par des mutants :

    * ``1`` (module sombre chez `segno`) devient ``0`` (noir en niveaux de
      gris), ``0`` devient ``255``. L'inversion produirait un raster en video
      inverse, qu'aucun decodeur du depot ne lit ;
    * la matrice nue est nappee de `MARGE_NATIVE_MODULES` modules de blanc sur
      les quatre bords, pour rendre exactement le cote qu'emettait l'encodeur
      d'OpenCV -- toute la geometrie d'impression en depend.
    """
    modules = np.asarray(symbole.matrix, dtype=np.uint8)
    trame = np.where(modules == 1, 0, 255).astype(np.uint8)
    return np.pad(
        trame,
        MARGE_NATIVE_MODULES,
        mode="constant",
        constant_values=255,
    )


def _avertir_si_le_symbole_ne_se_relit_pas(
    natif: np.ndarray, payload: str, correction_level: int
) -> bool:
    """Relire le symbole qu'on vient d'encoder, et AVERTIR s'il ne se relit pas.

    **Elle ne bloque pas** (`EPIC11-ARB-251`, esprit d'`EPIC11-ARB-89`) : un
    refus qui n'offre aucune issue est aussi fautif qu'une destruction
    silencieuse, et un symbole qui ne se relit pas sur cette machine peut se
    relire ailleurs. Elle rend ``True`` quand la relecture est conforme.

    **Motif.** La bascule d'encodeur ferme le defaut CONNU d'OpenCV 4.10/4.11 ;
    elle ne dit rien de ceux qu'on ne connait pas encore -- une regression de
    `segno`, d'OpenCV, ou du nappage ci-dessus. Ce defaut-la est reste
    invisible des mois precisement parce qu'aucune mesure ne confrontait le
    symbole produit a sa propre relecture.

    **Le message nomme la version d'OpenCV ET l'encodeur**, parce que les deux
    roles sont maintenant tenus par deux bibliotheques distinctes : sans ces
    deux noms, un futur defaut se diagnostique en une session au lieu d'une
    lecture.

    La relecture passe par `decode_qr_image_resilient`, c'est-a-dire par le
    chemin de lecture de la PRODUCTION, et non par un appel nu au decodeur :
    la question posee est « la chaine de lecture du produit relira-t-elle ce
    symbole ? », pas « un detecteur particulier y arrive-t-il ? ».
    """
    try:
        borde = cv2.copyMakeBorder(
            natif,
            _RELECTURE_ZONE_DE_SILENCE_MODULES, _RELECTURE_ZONE_DE_SILENCE_MODULES,
            _RELECTURE_ZONE_DE_SILENCE_MODULES, _RELECTURE_ZONE_DE_SILENCE_MODULES,
            cv2.BORDER_CONSTANT, value=255,
        )
        agrandi = cv2.resize(
            borde, None,
            fx=_RELECTURE_FACTEUR, fy=_RELECTURE_FACTEUR,
            interpolation=cv2.INTER_NEAREST,
        )
        relu = decode_qr_image_resilient(agrandi)
    except Exception as exc:  # noqa: BLE001 -- une garde ne fait jamais echouer son appelant
        # Un raster mal forme (non carre, dimension nulle, dtype inattendu) fait
        # lever le redimensionnement ou la normalisation du decodeur. C'est
        # exactement le cas que la garde existe pour signaler : elle l'avertit
        # au lieu de le propager, sinon un defaut de FORME deviendrait une
        # exception la ou la bascule promet de ne rien casser.
        _journal.warning(
            "QR: la relecture de controle a echoue (%s: %s). Symbole encode par "
            "segno %s, relu par OpenCV %s, niveau ECC %d. La planche est ecrite "
            "quand meme (EPIC11-ARB-251).",
            type(exc).__name__, exc, segno.__version__, cv2.__version__,
            correction_level,
        )
        return False

    if relu.text == payload:
        return True

    _journal.warning(
        "QR: le symbole encode NE SE RELIT PAS (statut %s, %d octets attendus, "
        "%d relus). Encodeur segno %s, decodeur OpenCV %s, niveau ECC %d, cote "
        "natif %d modules. Une planche imprimee avec ce symbole ne se rescannera "
        "pas ; la sortie est ecrite quand meme (EPIC11-ARB-251).",
        relu.status, len(payload), len(relu.text), segno.__version__,
        cv2.__version__, correction_level, int(natif.shape[0]),
    )
    return False


def pixels_per_module(module_side: int, size_mm: float, dpi: int) -> float:
    """Return the scan-time pixels per module for a symbol of ``module_side``
    modules printed at ``size_mm`` and scanned at ``dpi``.

    This is the variable that actually governs decodability; ``size_mm`` and
    ``dpi`` only ever act through their product, so reporting a result against
    one while holding the other fixed conflates the two.
    """
    if module_side <= 0:
        raise QRRenderError(f"module_side invalide: {module_side}")
    if size_mm <= 0 or dpi <= 0:
        raise QRRenderError(f"Geometrie d'impression invalide: size_mm={size_mm}, dpi={dpi}")
    return size_mm / 25.4 * dpi / module_side


def required_print_size_mm(
    module_side: int,
    dpi: int = QR_MIN_SCAN_DPI,
    px_per_module: float = MIN_PIXELS_PER_MODULE_RELIABLE,
) -> float:
    """Return the printed size (mm) needed to reach ``px_per_module`` at ``dpi``.

    Sheet generation should size the QR from the payload actually being
    printed rather than from a constant: a page carrying more slots encodes to
    more modules and needs a physically larger code for the same reliability.
    """
    if module_side <= 0:
        raise QRRenderError(f"module_side invalide: {module_side}")
    if dpi <= 0 or px_per_module <= 0:
        raise QRRenderError(f"Parametres invalides: dpi={dpi}, px_per_module={px_per_module}")
    return px_per_module * module_side * 25.4 / dpi


def symbol_version(module_side: int) -> int:
    """Rendre la version ISO/IEC 18004 d'un symbole de ``module_side`` modules.

    La relation est exacte: version `V` <-> `4V + 17` modules, de 21 a 177. Un cote
    qui ne satisfait pas cette relation n'est pas celui d'un symbole QR, et le
    refuser ici plutot que d'arrondir est delibere: la seule facon d'obtenir un tel
    cote est de lire une dimension ailleurs que sur le raster de l'encodeur -- un
    raster recadre, une hauteur prise pour un cote, ou un nombre de modules **pose a
    la main**, qui est l'erreur d'un facteur trois du 2026-08-11 matin. Un arrondi
    silencieux rendrait une version fausse, donc une garde de version fausse.
    """
    if not is_strict_int(module_side):
        raise QRRenderError(
            f"module_side doit etre un entier, recu: {type(module_side).__name__}"
        )
    if (module_side - _MODULES_AT_VERSION_ZERO) % _MODULES_PER_VERSION != 0:
        raise QRRenderError(
            f"module_side={module_side} n'est pas un cote de symbole QR: la version V "
            f"a 4V+17 modules, donc un cote valide vaut 21, 25, 29, ... 177."
        )
    version = (module_side - _MODULES_AT_VERSION_ZERO) // _MODULES_PER_VERSION
    if not QR_SYMBOL_VERSION_MIN <= version <= QR_SYMBOL_VERSION_MAX:
        raise QRRenderError(
            f"module_side={module_side} donne la version {version}, hors des versions "
            f"ISO/IEC 18004 ({QR_SYMBOL_VERSION_MIN} a {QR_SYMBOL_VERSION_MAX}, soit "
            f"21 a 177 modules)."
        )
    return version


def check_print_geometry(module_side: int, size_mm: float, dpi: int) -> str:
    """Classify a print/scan geometry against the measured thresholds.

    Returns ``GEOMETRY_RELIABLE``, ``GEOMETRY_DEGRADED`` or
    ``GEOMETRY_UNUSABLE``. Callers decide what to do; nothing raises here,
    because printing a known-degraded sheet is a legitimate (documented)
    operator choice while printing an unusable one is not.

    **La garde porte sur deux grandeurs et non sur une seule** (story 5.17). Le ratio
    px/module dit si la trame se relit; il ne dit rien de la version du symbole, et
    une version bannie (`QR_BANNED_SYMBOL_VERSIONS`) est indecodable **quelle que
    soit** la taille imprimee. Agrandir un symbole de version 22 ne le rend pas
    lisible: la seule sortie est de reduire la charge utile. Sans ce test, un tel
    symbole ressortait `reliable` a taille genereuse, et la planche s'imprimait sans
    un mot -- c'est l'action item ouvert du `sprint-status.yaml`, ferme ici.
    """
    version = symbol_version(module_side)
    ratio = pixels_per_module(module_side, size_mm, dpi)
    if version in QR_BANNED_SYMBOL_VERSIONS:
        return GEOMETRY_UNUSABLE
    if ratio >= MIN_PIXELS_PER_MODULE_RELIABLE:
        return GEOMETRY_RELIABLE
    if ratio >= MIN_PIXELS_PER_MODULE_DEGRADED:
        return GEOMETRY_DEGRADED
    return GEOMETRY_UNUSABLE


def render_for_print(
    native_qr: np.ndarray,
    size_mm: float,
    dpi: int,
    *,
    quiet_zone_modules: int = QUIET_ZONE_MODULES,
) -> np.ndarray:
    """Render ``native_qr`` at ``size_mm`` / ``dpi`` with an ISO quiet zone.

    Each module is rendered as a whole number of pixels (nearest-neighbour
    upscale by an integer factor), then the whole raster is resampled once to
    the exact target size with ``INTER_AREA``. Resizing straight to a
    fractional px/module with ``INTER_NEAREST`` made modules alternate between
    n and n+1 pixels, which distorted the grid by an amount depending on the
    fractional part -- decode success then varied non-monotonically with the
    printed size (30 mm decoded, 40 mm did not), independently of any
    degradation.
    """
    if native_qr is None or not isinstance(native_qr, np.ndarray) or native_qr.size == 0:
        raise QRRenderError("Raster QR natif invalide ou vide.")
    if native_qr.ndim < 2 or native_qr.shape[0] != native_qr.shape[1]:
        # A QR symbol is square by construction. Taking shape[0] as *the*
        # module count on a non-square raster silently stretched one axis
        # (50x80 in produced 959x959 out) and made pixels_per_module -- hence
        # check_print_geometry -- wrong on the other axis, without a word.
        raise QRRenderError(
            f"Raster QR natif non carre: {native_qr.shape[:2]}. Un symbole QR est carre; "
            "un raster rectangulaire signale une lecture ou un recadrage errone en amont."
        )
    if not is_strict_int(quiet_zone_modules):
        raise QRRenderError(
            f"quiet_zone_modules doit etre un entier, recu: {type(quiet_zone_modules).__name__}"
        )
    if quiet_zone_modules < QUIET_ZONE_MODULES:
        # A negative value escaped as a raw cv2.error, and 0 silently produced
        # a raster violating the ISO/IEC 18004 minimum this module documents.
        raise QRRenderError(
            f"quiet_zone_modules={quiet_zone_modules} sous le minimum ISO/IEC 18004 "
            f"({QUIET_ZONE_MODULES} modules). Une marge plus large est permise, pas plus etroite."
        )

    module_side = native_qr.shape[0]
    ratio = pixels_per_module(module_side, size_mm, dpi)

    padded = cv2.copyMakeBorder(
        native_qr,
        quiet_zone_modules, quiet_zone_modules, quiet_zone_modules, quiet_zone_modules,
        cv2.BORDER_CONSTANT, value=255,
    )
    padded_side = padded.shape[0]
    target_px = int(round(ratio * padded_side))
    if target_px < padded_side:
        raise QRRenderError(
            f"Rendu impossible: {ratio:.2f} px/module demande, moins de 1 px par module. "
            f"Augmenter size_mm ({size_mm}) ou dpi ({dpi})."
        )

    # Integer supersampling first, single INTER_AREA resample second.
    factor = max(1, int(np.ceil(ratio)))
    if (padded_side * factor) > MAX_RENDER_SIDE_PX:
        # The intermediate raster is (padded_side * ceil(ratio))^2, so an
        # absurd size/DPI blew up in cv2's allocator with a raw error instead
        # of naming the parameter at fault.
        raise QRRenderError(
            f"Geometrie demesuree: size_mm={size_mm}, dpi={dpi} exigent un rendu "
            f"intermediaire de {padded_side * factor} px de cote (max "
            f"{MAX_RENDER_SIDE_PX}). Verifier les unites."
        )
    supersampled = cv2.resize(
        padded, (padded_side * factor, padded_side * factor), interpolation=cv2.INTER_NEAREST
    )
    if supersampled.shape[0] == target_px:
        return supersampled
    return cv2.resize(supersampled, (target_px, target_px), interpolation=cv2.INTER_AREA)


def _as_decodable_uint8(image: np.ndarray) -> np.ndarray:
    """Normalise ``image`` to the single-channel uint8 the detectors accept.

    The detectors raise a raw ``cv2.error`` on float32, uint16, bool, empty
    arrays and ``None`` -- while every caller is written against a documented
    "returns an empty string" contract. uint16 is a real case: the scan path
    produces 16-bit TIFF (story 5.5).
    """
    if image is None:
        raise ValueError("Image absente (None): lecture amont echouee ?")
    if not isinstance(image, np.ndarray):
        raise TypeError(f"Image attendue de type numpy.ndarray, recu: {type(image).__name__}")
    if image.size == 0 or min(image.shape[:2]) == 0:
        raise ValueError("Image vide: rien a decoder.")

    if image.dtype == np.bool_:
        gray = image.astype(np.uint8) * 255
    elif image.dtype.kind == "u" and image.dtype.itemsize == 2:
        gray = (image.astype(np.uint32) >> 8).astype(np.uint8)
    elif image.dtype.kind == "f":
        peak = float(np.nanmax(image)) if image.size else 0.0
        scale = 255.0 if peak <= 1.0 else 1.0
        gray = np.clip(np.nan_to_num(image) * scale, 0, 255).astype(np.uint8)
    elif image.dtype == np.uint8:
        gray = image
    else:
        raise ValueError(f"Type d'image non supporte pour le decodage QR: {image.dtype}")

    if gray.ndim == 3:
        if gray.shape[2] == 4:
            gray = cv2.cvtColor(gray, cv2.COLOR_BGRA2GRAY)
        elif gray.shape[2] == 3:
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
        elif gray.shape[2] == 1:
            gray = gray[:, :, 0]
        else:
            raise ValueError(f"Nombre de canaux non supporte: {gray.shape[2]}")
    elif gray.ndim != 2:
        raise ValueError(f"Image de dimension non supportee: {gray.ndim}")
    return np.ascontiguousarray(gray)


def _make_detector(detector: str):
    if detector == DETECTOR_CLASSIC:
        return cv2.QRCodeDetector()
    if detector == DETECTOR_ARUCO:
        return cv2.QRCodeDetectorAruco()
    raise ValueError(
        f"Detecteur inconnu: {detector!r}. Attendu {DETECTOR_CLASSIC!r} ou {DETECTOR_ARUCO!r}."
    )


def decode_qr_image(image: np.ndarray, *, detector: str = DEFAULT_DETECTOR) -> QRDecodeResult:
    """Decode a (possibly degraded) raster and report *why* it failed.

    ``detectAndDecode`` is mono-symbol and returns an empty string as soon as
    two codes are in frame (a two-up sheet, a double page, the next sheet at
    the edge of the glass), which is indistinguishable from a blank page. This
    uses the multi variant to count symbols first, so the three failure modes
    stay distinguishable.
    """
    gray = _as_decodable_uint8(image)
    engine = _make_detector(detector)

    ok, texts, points, _straight = engine.detectAndDecodeMulti(gray)
    symbol_count = 0 if points is None else len(points)

    decoded = [text for text in (texts or []) if text] if ok else []
    if len(decoded) == 1 and symbol_count <= 1:
        return QRDecodeResult(text=decoded[0], status=DECODE_OK, symbol_count=1)
    if symbol_count > 1:
        return QRDecodeResult(text="", status=DECODE_MULTIPLE, symbol_count=symbol_count)
    if decoded:
        return QRDecodeResult(text=decoded[0], status=DECODE_OK, symbol_count=max(symbol_count, 1))

    # Nothing decoded: was a symbol even located?
    located = False
    try:
        located = bool(engine.detect(gray)[0])
    except cv2.error:
        located = False
    if located or symbol_count:
        return QRDecodeResult(
            text="", status=DECODE_UNREADABLE, symbol_count=max(symbol_count, 1)
        )
    return QRDecodeResult(text="", status=DECODE_NO_SYMBOL, symbol_count=0)


#: L'autre moteur, pour chacun des deux. Fige la paire a exactement deux
#: entrees: un troisieme detecteur qui apparaitrait un jour devrait choisir
#: explicitement son propre repli plutot que d'en heriter un par defaut.
#: Facteurs de reechantillonnage du second repli, dans l'ordre d'essai. Deux suffit
#: sur le materiel mesure; trois est garde parce qu'il ne coute que sur une feuille
#: deja perdue, et qu'aucune mesure ne dit que 5,10 px/module est le pire cas du
#: terrain. Au-dela de trois, l'image grossit sans que le decodeur y gagne: le flou
#: optique, lui, ne se defloute pas.
_RESAMPLE_RESCUE_FACTORS: tuple[int, ...] = (2, 3)

_RESCUE_DETECTOR = {DETECTOR_ARUCO: DETECTOR_CLASSIC, DETECTOR_CLASSIC: DETECTOR_ARUCO}


def decode_qr_image_resilient(
    image: np.ndarray, *, detector: str = DEFAULT_DETECTOR
) -> QRDecodeResult:
    """Comme :func:`decode_qr_image`, avec un second essai quand le premier localise
    le symbole sans le decoder.

    **Origine: un echec de terrain, pas une hypothese.** Sur un vrai lot imprime puis
    scanne (planche a 8 emplacements, QR de 442 octets, version 17, 85 modules --
    9,7 px/module a 35 mm/600 ppp, confortablement au-dessus du seuil `reliable` de
    8,0), le detecteur `aruco` -- celui que `DEFAULT_DETECTOR` choisit -- a localise le
    symbole sans le decoder (`DECODE_UNREADABLE`) alors que `classic` le decodait sans
    detour, payload valide compris. Ce n'etait pas un depassement de budget ni une
    geometrie hors norme: c'est le taux d'echec residuel qu'`aruco` porte deja dans son
    propre commentaire de choix par defaut (208/270 a 35 mm sur le banc, jamais 270/270).

    **Le repli ne coute rien sur le chemin heureux et ne peut pas faire pire.** Il n'est
    tente que si le premier essai rend `DECODE_UNREADABLE` -- un symbole localise mais
    dont le contenu n'a pas ete extrait, jamais sur `DECODE_NO_SYMBOL` (rien a localiser:
    l'autre moteur ne trouvera pas plus une feuille blanche) ni sur `DECODE_MULTIPLE`
    (deux symboles en champ: un changement d'algorithme ne recompte pas la vitre). Si le
    second essai echoue aussi, c'est le diagnostic du **premier** qui est rendu, jamais
    celui du second: l'appelant lit un statut coherent avec le detecteur qu'il a demande,
    et le repli reste invisible quand il ne sauve rien.

    **Piege mesure a ne pas reproduire**: recadrer l'image avant de decoder pour
    « alleger » l'appel ne conserve pas le verdict. Le meme symbole, sur la meme page
    reelle, redonne un verdict **different** selon la marge de contexte gardee autour de
    lui (`aruco` echoue a partir de ~30 mm de marge sur ce cas, mais `classic` alterne
    decode/echec de facon non monotone entre 5 et 180 mm) -- l'un des deux detecteurs
    d'OpenCV lit visiblement plus que la seule zone du symbole. Cette fonction recoit
    donc **la meme image que la production**, jamais un recadrage cense l'approcher.
    """
    primary = decode_qr_image(image, detector=detector)
    if primary.status != DECODE_UNREADABLE:
        return primary
    rescue = decode_qr_image(image, detector=_RESCUE_DETECTOR[detector])
    if rescue.ok:
        return rescue
    # --- Second repli: reechantillonner, mesure sur le terrain d'Egan (2026-08-18) ---
    #
    # Le repli de detecteur ci-dessus change de moteur a resolution constante. Il ne
    # sert a rien quand le probleme n'est pas le moteur mais le nombre de pixels par
    # module: sous ~6 px/module, les deux moteurs localisent le symbole et echouent a
    # poser leur grille de modules dessus.
    #
    # **Mesure, pas hypothese.** Quatre feuilles scannees a 300 dpi par un HP Envy
    # 4520. Le seuil `reliable` vaut 8,0 px/module; les feuilles a 6 emplacements
    # tombent a **5,10** (81 modules sur 35 mm). Deux d'entre elles sont au meme
    # chiffre: l'une decode, l'autre non -- a ce niveau ce n'est plus une propriete de
    # la feuille, c'est le grain du papier qui tranche. Sur celle qui echouait, un
    # simple agrandissement x2 la rend lisible, en cubique comme en Lanczos, et x2 x3
    # x4 reussissent tous. Le seuillage d'Otsu et l'accentuation seuls echouent: ce
    # n'est donc pas un defaut de contraste, c'est bien la resolution d'echantillonnage.
    #
    # L'agrandissement **n'ajoute aucune information** -- il donne au decodeur assez de
    # pixels pour poser sa grille. C'est pour cela qu'il ne peut pas fabriquer un faux
    # positif: un symbole absent ou detruit ne devient pas lisible en grossissant, et le
    # code correcteur du QR refuse un contenu incoherent.
    #
    # Pourquoi ne pas simplement exiger 600 dpi: le materiel d'Egan ne monte pas
    # au-dessus de 300, et agrandir le QR imprime n'est pas possible -- son emprise vaut
    # deja 38,46 mm pour 39,62 mm reserves, soit 1,2 mm de marge. Le porter a 40 mm le
    # ferait mordre sur la bande de frames.
    #
    # Le cout est nul sur le chemin heureux: on n'arrive ici qu'apres deux echecs.
    for facteur in _RESAMPLE_RESCUE_FACTORS:
        agrandie = cv2.resize(image, None, fx=facteur, fy=facteur,
                              interpolation=cv2.INTER_CUBIC)
        for moteur in (detector, _RESCUE_DETECTOR[detector]):
            tentative = decode_qr_image(agrandie, detector=moteur)
            if tentative.ok:
                return tentative
    # Le diagnostic rendu reste celui du **premier** essai: l'appelant lit un statut
    # coherent avec le detecteur qu'il a demande, et les replis restent invisibles
    # quand ils ne sauvent rien.
    return primary
