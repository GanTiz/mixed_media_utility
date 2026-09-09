"""Jonction payload de page -> budget QR -> geometrie d'impression (story 4.5).

Ce module cable ensemble trois contrats existants sans en posseder aucun:

- ``io.payload`` (story 2.3, clos): schema du payload, validation, budgets;
- ``io.naming`` (story 2.3, clos): forme canonique des identifiants;
- ``qr_codes`` (story 4.6, close): geometrie d'impression mesuree.

Il ne serialise rien lui-meme, ne derive aucun identifiant et ne duplique
aucune constante de budget: le depot a deja paye deux fois le prix d'un
contrat duplique (schema prive de 4.6 supprime le 2026-08-02, double base
d'indexation 2.3/2.6). Un test AST verrouille cette regle (AC 7).

Tracabilite epic -> contrat 2.3 (AC 1)
--------------------------------------
L'AC de l'epic demande "projet, rush, timecode, fps cible, nombre de patchs,
version du schema". Couverture par le contrat de production:

    projet            -> ``project_id``
    rush              -> ``rush_id``
    timecode          -> ``slots[].frame_timecode``
    fps cible         -> ``fps_target``
    nombre de patchs  -> ``patch_preset_id`` (le cardinal est une propriete du
                         preset, resolue par le registre de la story 4.7 --
                         jamais un champ redondant, piege 1 de la story 4.4)
    version du schema -> ``schema_version``

Les champs supplementaires du contrat 2.3 (``lot_id``, ``page_index``,
``page_count``, ``template_id``, ``target_colorspace``,
``slots[].slot_index``) sont necessaires au contrat minimal de reconstruction
sur machine tierce (ARCHITECTURE_DETAILED.md section 3). Aucun champ n'est
ajoute ni retire ici: toute evolution passe par un arbitrage explicite.

Un QR par page (AC 2)
---------------------
Le choix "par frame ou par groupe" est ferme: **un QR par page** (strategie
MVP, ARCHITECTURE_DETAILED.md section 6, hypothese de tout le dimensionnement
4.6). Un QR par frame est ecarte: chaque symbole coute ~35 mm de cote plus sa
zone de silence ISO (4 modules), soit une surface impossible a caser a cote
des zones de frames; et ``qr_codes.decode_qr_image`` traite le multi-symbole
comme un cas a compter (``DECODE_MULTIPLE``), pas comme un mode nominal.
Rouvrir ce choix exigerait de re-mesurer: capacite par symbole reduit,
geometrie de placement multi-QR, et comportement des deux detecteurs en
presence de N symboles voisins.

Semantique de ``template_id`` (AC 3)
------------------------------------
Identifiant **canonique** au sens de ``io.naming`` (pattern
``^[A-Za-z0-9_-]+$``, longueur <= 48), versionne par suffixe explicite
(``-v1``, ``-v2``...): toute modification de geometrie est un **nouvel**
identifiant, jamais une redefinition silencieuse. Ce que l'identifiant engage
(decision 4.4 sur la marge discrete): format de page, orientation, nombre et
positions des zones de frames, preset de marge. Contrat du registre que la
story 4.1 implemente: resolution ``template_id -> geometrie complete``; un
``template_id`` inconnu au scan est un **echec explicite**, jamais une
geometrie devinee.

Semantique de ``patch_preset_id`` (AC 4)
----------------------------------------
Meme forme canonique et meme regle de versionnement. Le payload ne porte
jamais les valeurs des patchs ni leur cardinal: uniquement l'identifiant du
preset, que le registre de la story 4.7 est seul a resoudre (matrice de
responsabilite 2.4, ARCHITECTURE_DETAILED.md section 5).

Timecode (AC 5)
---------------
``slots[].frame_timecode`` porte la forme canonique ``hh:mm:ss:ff`` rendue
par la selection 3.2 (base source, ARB-2) -- jamais la forme assainie
``hh-mm-ss-ff`` des noms de fichiers. La conversion vit dans ``io.naming`` au
moment du nommage, nulle part ailleurs: un payload portant la forme fichier
casserait le recoupement QR <-> nom de fichier (filet de securite de l'AC 4
de 4.6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import qr_codes
from .io import naming
from .numeric_guards import is_strict_int
from .page_roles import PAGE_ROLE_IMAGES
from .io.payload import (
    PayloadBudgetReport,
    build_page_payload,
    check_payload_budget,
    serialize_payload,
)

#: Code stable de l'avertissement "page imprimable mais hors budget nominal"
#: (EPIC4-ARB-2: avertissement structure sans consentement, QR agrandi si
#: necessaire).
WARNING_OVER_NOMINAL_BUDGET = "HORS_BUDGET_NOMINAL"

#: Code stable de l'avertissement "QR agrandi au-dela de la cible 4.6 par le
#: dpi de scan demande" (revue 4.5): a budget nominal, un scan_dpi bas
#: triplait la surface du QR sans un mot.
WARNING_QR_ENLARGED_FOR_SCAN_DPI = "QR_AGRANDI_POUR_DPI_SCAN"


class NonCanonicalIdentifierError(ValueError):
    """Raised when an identifier is not in its canonical manifest form.

    Les identifiants entrent **deja canoniques** dans la jonction (piege 6 de
    la story 4.5): un appelant qui passerait un nom humain brut produirait un
    QR portant une autre forme que les noms de fichiers, cassant le
    recoupement QR <-> nom sans aucune erreur. Le refus est donc explicite.
    """


class NonCanonicalTimecodeError(ValueError):
    """Raised when a slot timecode is not in the canonical selection form.

    Le payload porte ``hh:mm:ss:ff`` (selection 3.2); la forme assainie
    ``hh-mm-ss-ff`` des noms de fichiers casserait le recoupement QR <-> nom
    (filet de securite 4.6). Garde ajoutee en revue 4.5: le docstring
    revendiquait ce filet sans qu'aucune verification n'existe.
    """


@dataclass(frozen=True)
class PagePayloadPlan:
    """Resultat du cablage payload reel -> budget -> geometrie d'impression.

    ``payload`` est le dict valide par le contrat 2.3, ``payload_text`` sa
    serialisation exacte (celle qui sera encodee dans le QR), ``budget`` le
    rapport de ``io.payload.check_payload_budget``. ``module_side`` est le
    cote du symbole reellement encode; ``required_print_size_mm`` la taille
    minimale fiable a ``dpi`` de scan; ``print_size_mm`` la taille a imprimer
    (jamais sous la cible 4.6, agrandie automatiquement au-dela si le payload
    l'exige -- EPIC4-ARB-2); ``geometry_status`` le classement de
    ``qr_codes.check_print_geometry`` pour cette taille.
    """

    payload: dict[str, Any]
    payload_text: str
    budget: PayloadBudgetReport
    module_side: int
    required_print_size_mm: float
    print_size_mm: float
    geometry_status: str
    scan_dpi: int
    warnings: tuple[str, ...]


def _require_canonical_identifier(value: Any, field: str) -> None:
    """Refuse une valeur qui n'est pas deja sous forme canonique.

    Delegue a l'implementation unique ``io.naming.validate_manifest_identifier``
    (pattern du schema v2 + longueur maximale). La premiere version de cette
    garde verifiait le point fixe de ``normalize_identifier`` — plus severe
    que le contrat: elle refusait des ``lot_id`` produits par
    ``naming.build_lot_id`` lui-meme (``derive_short_id`` recopie son prefixe
    verbatim, un rush long a tiret pres de la borne rend ``...--<hash>``) et
    des identifiants schema-valides comme ``a--b`` (revue 4.5). Aucune valeur
    derivee n'est jamais utilisee ni retournee -- ce module controle, il ne
    transforme pas (AC 7). Les valeurs vides ou non-str sont laissees au
    contrat 2.3, qui possede leur message d'erreur.
    """
    if not isinstance(value, str) or not value:
        return
    try:
        # **La borne de CREATION, pas la tolerante.** `plan_page_payload`
        # COMPOSE une planche a imprimer : c'est de l'ecriture. Assouplir ici
        # rouvrirait la falaise QR qu'`EPIC11-ARB-110` vient de fermer -- la
        # tolerance de `LEGACY_ID_MAX_LENGTH` n'appartient qu'aux chemins qui
        # RELISENT un identifiant deja imprime (`derive_lot_dir_slug`).
        naming.validate_manifest_identifier(value, label=field)
    except naming.NamingError as exc:
        raise NonCanonicalIdentifierError(
            f"Identifiant '{field}' non canonique: {exc}"
        ) from exc


def plan_page_payload(
    *,
    project_id: str,
    rush_id: str,
    lot_id: str,
    page_index: int,
    page_count: int,
    fps_target: float,
    timecode_base_fps: str,
    template_id: str,
    patch_preset_id: str,
    gamut_map_id: str,
    target_colorspace: str,
    slots: list[dict[str, Any]],
    scan_dpi: int = qr_codes.QR_MIN_SCAN_DPI,
    page_role: str = PAGE_ROLE_IMAGES,
    scan_chain_label: str | None = None,
    #: Rang de version de la PLANCHE (`EPIC11-ARB-91`). `None` au rang 1,
    #: qui n'ecrit aucun champ -- son absence le dit, et l'ecrire couterait
    #: 7 octets sur chaque planche du parc pour ne rien ajouter (le detail du
    #: budget vit au commentaire de `PAYLOAD_SHORT_KEYS`, seul endroit du depot
    #: ou une cle courte s'ecrit -- frontiere mesuree par
    #: `test_the_table_is_the_only_place_where_a_short_key_is_written`, que
    #: citer la cle ici faisait rougir).
    version_rank: int | None = None,
) -> PagePayloadPlan:
    """Construire le payload reel d'une page et rendre budget + geometrie QR.

    Trois regimes contractuels (EPIC4-ARB-2):

    - budget nominal respecte: aucun avertissement, taille cible 4.6;
    - budget nominal depasse mais plafond respecte: la page reste imprimable,
      avertissement ``WARNING_OVER_NOMINAL_BUDGET`` et QR agrandi a la taille
      minimale fiable rendue par ``qr_codes.required_print_size_mm``;
    - plafond depasse: ``io.payload.PayloadBudgetExceeded`` est **transportee**
      telle quelle, jamais avalee ni maquillee (piege 1).

    ``page_role`` declare le **role de page** (story 5.16, `EPIC5-ARB-54`): il ne
    change rien au cablage de cette fonction, mais il change ce que la validation du
    contrat 2.3 exige des emplacements -- une page de calibration n'en porte aucun, une
    planche d'images doit en porter.

    Les erreurs de validation du contrat 2.3 (``PayloadValidationError``, par
    exemple un ``target_colorspace`` absent du manifest au moment de makepdf,
    piege 5) traversent egalement sans maquillage. La capacite n'est jamais
    lue dans une constante: elle est mesuree sur le payload reellement
    serialise -- les ``SLOTS_PER_PAGE_AT_*`` de ``qr_codes`` sont des reperes
    documentaires, pas des gardes.
    """
    # scan_dpi garde a l'entree (revue 4.5): un dpi nul/negatif/booleen
    # n'echouait qu'apres l'encodage complet du QR, en QRRenderError au
    # message ne nommant pas le parametre.
    if not is_strict_int(scan_dpi) or scan_dpi <= 0:
        raise qr_codes.QRRenderError(
            f"scan_dpi invalide: {scan_dpi!r}. Attendu: un entier strictement "
            f"positif (defaut {qr_codes.QR_MIN_SCAN_DPI}, contrat 4.6)."
        )

    for field, value in (
        ("project_id", project_id),
        ("rush_id", rush_id),
        ("lot_id", lot_id),
        ("template_id", template_id),
        ("patch_preset_id", patch_preset_id),
        ("gamut_map_id", gamut_map_id),
    ):
        _require_canonical_identifier(value, field)

    # Copie des dicts de slots (revue 4.5): io.payload ne copie que la liste,
    # pas les dicts — un appelant qui reutilise ses dicts entre pages aurait
    # fait diverger `payload` de `payload_text` apres coup. Et la forme du
    # timecode est controlee ici (filet 4.6 revendique par le docstring):
    # la forme fichier hh-mm-ss-ff casserait le recoupement QR <-> nom.
    copied_slots: list[dict[str, Any]] = []
    for index, slot in enumerate(slots or []):
        if isinstance(slot, dict):
            timecode = slot.get("frame_timecode")
            if isinstance(timecode, str) and timecode:
                try:
                    naming.validate_frame_timecode(
                        timecode, label=f"slots[{index}].frame_timecode"
                    )
                except naming.NamingError as exc:
                    raise NonCanonicalTimecodeError(str(exc)) from exc
            copied_slots.append(dict(slot))
        else:
            copied_slots.append(slot)  # le contrat 2.3 possede le refus

    payload = build_page_payload(
        project_id=project_id,
        rush_id=rush_id,
        lot_id=lot_id,
        page_index=page_index,
        page_count=page_count,
        fps_target=fps_target,
        # Story 2.7 (payload 2.1): traverse sans etre interprete, comme
        # `fps_target` juste au-dessus -- ce module cable, il ne decide pas
        # de la cadence source, il la transporte verbatim jusqu'au contrat.
        timecode_base_fps=timecode_base_fps,
        template_id=template_id,
        patch_preset_id=patch_preset_id,
        gamut_map_id=gamut_map_id,
        target_colorspace=target_colorspace,
        slots=copied_slots,
        # Story 5.23: le libelle de chaine traverse lui aussi sans etre interprete.
        # Il n'est **pas** passe a `_require_canonical_identifier` juste au-dessus, et
        # c'est le point: ce n'est pas un identifiant mais de la prose saisie par
        # l'operateur (« hp envy 4520 tiff 600 dpi auto corr off »). Lui imposer la
        # forme canonique le ferait refuser sur sa premiere espace, donc obligerait a
        # ressaisir autre chose que ce qui est lu sur la machine. Son contrat -- non
        # vide, borne en longueur -- appartient a `io.payload.validate_scan_chain_label`.
        scan_chain_label=scan_chain_label,
        version_rank=version_rank,
        # Story 5.16: le role de page traverse la jonction sans y etre interprete --
        # ce module cable, il ne decide pas. Le defaut est le role d'images, donc le
        # regime **strict** de la garde d'emplacements: un appelant qui l'oublie sur
        # une page de calibration se fait refuser, il ne se fait pas mal etiqueter.
        page_role=page_role,
    )
    budget = check_payload_budget(payload)
    payload_text = serialize_payload(payload)

    native = qr_codes.encode_qr_image(payload_text)
    module_side = int(native.shape[0])
    required_mm = qr_codes.required_print_size_mm(module_side, scan_dpi)
    print_size_mm = max(qr_codes.QR_PRINT_SIZE_TARGET_MM, required_mm)
    geometry_status = qr_codes.check_print_geometry(module_side, print_size_mm, scan_dpi)
    if (
        geometry_status != qr_codes.GEOMETRY_RELIABLE
        and print_size_mm <= required_mm + 1e-9
    ):
        # Arrondi flottant au seuil exact (revue 4.5): required_print_size_mm
        # et pixels_per_module n'enchainent pas les operations dans le meme
        # ordre, et 8.0 px/module peut se recalculer 7.999999999999999 --
        # une taille dimensionnee pour etre fiable etait classee degradee.
        # 0.01 mm de marge retablit la classe calculee.
        bumped = print_size_mm + 0.01
        if qr_codes.check_print_geometry(module_side, bumped, scan_dpi) == qr_codes.GEOMETRY_RELIABLE:
            print_size_mm = bumped
            geometry_status = qr_codes.GEOMETRY_RELIABLE

    warnings: list[str] = []
    if not budget.within_nominal:
        # Message honnete (revue 4.5): n'annoncer un agrandissement que
        # lorsqu'il a reellement lieu.
        if print_size_mm > qr_codes.QR_PRINT_SIZE_TARGET_MM:
            size_note = (
                f"QR agrandi a {print_size_mm:.1f} mm pour rester fiable a "
                f"{scan_dpi} dpi de scan"
            )
        else:
            size_note = (
                f"taille cible de {print_size_mm:.1f} mm conservee (suffisante "
                f"a {scan_dpi} dpi de scan)"
            )
        warnings.append(
            f"{WARNING_OVER_NOMINAL_BUDGET}: payload de {budget.size_bytes} octets "
            f"au-dessus du budget nominal de {budget.nominal_budget} octets "
            f"(plafond {budget.alert_budget}). Page imprimable hors budget "
            f"nominal; {size_note} (EPIC4-ARB-2)."
        )
    elif print_size_mm > qr_codes.QR_PRINT_SIZE_TARGET_MM:
        # Agrandissement pilote par le dpi de scan (revue 4.5): un scan prevu
        # sous 600 dpi grossit le QR bien au-dela de la cible 4.6 -- sans ce
        # signal, le plan etait "nominal, sans avertissement" alors que la
        # geometrie ne tient plus forcement sur le gabarit.
        warnings.append(
            f"{WARNING_QR_ENLARGED_FOR_SCAN_DPI}: QR agrandi a "
            f"{print_size_mm:.1f} mm (cible 4.6: "
            f"{qr_codes.QR_PRINT_SIZE_TARGET_MM:.0f} mm) pour rester fiable a "
            f"{scan_dpi} dpi de scan. Verifier que cette emprise tient sur le "
            "gabarit de page."
        )

    return PagePayloadPlan(
        payload=payload,
        payload_text=payload_text,
        budget=budget,
        module_side=module_side,
        required_print_size_mm=required_mm,
        print_size_mm=print_size_mm,
        geometry_status=geometry_status,
        scan_dpi=scan_dpi,
        warnings=tuple(warnings),
    )
