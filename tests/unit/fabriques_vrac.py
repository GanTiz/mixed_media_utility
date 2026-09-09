"""Fabriques de vrac pour la story 5.24 -- **multi-elements par construction**.

Ce module ne contient aucun test : il porte les fabriques que les lots de tests
de la story 5.24 partagent, et il applique nommement la regle des fabriques du
depot (CLAUDE.md, « Ecriture des tests : la regle des fabriques »), qui est ici
une **AC** (AC 3) et non une recommandation :

1. **toute fabrique de collection produit au moins deux elements
   distinguables** -- deux lots aux identifiants differents, deux pages aux index
   differents, deux chaines de scan aux libelles differents. Jamais un
   remplissage uniforme : une permutation ne se voit que si les elements
   different ;
2. **au moins un test place la cible ailleurs qu'en premiere position** -- d'ou
   :func:`vrac_de_reference`, qui ne met en tete ni le lot vise, ni la page
   visee, ni la page de calibration ;
3. la variante multi-elements est ecrite **dans cette story**, jamais renvoyee a
   la revue.

Motif mesure, et il est triple : `M33` (5.6, appariement emplacements/frames
inverse, 165 tests verts), `M25` (5.7, `_find_lot` rendait le **premier** lot,
257 tests verts, cardinaux ecrits sur le mauvais lot) et les cinq survivants de
5.8. Aucun n'a ete trouve par relecture.

Les payloads viennent de leur **vrai producteur** (`io.payload.build_page_payload`) :
un dictionnaire ecrit a la main ici porterait par distraction un champ que le
contrat retire -- et le defaut mesure ne se reproduirait pas.
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mixed_media_utility import page_roles, scan_sorting  # noqa: E402
from mixed_media_utility.io import payload as payload_io  # noqa: E402

#: Le projet courant du vrac. Le tri est **borne a un projet**
#: (`EPIC5-ARB-105`) ; tout le reste est hors perimetre.
PROJET_COURANT = "projet_demo"

#: **Deux** projets etrangers, aux identifiants differents : une seule page
#: etrangere passerait sous un code qui affiche une constante -- exactement la
#: famille de
#: `test_la_provenance_porte_l_identifiant_de_la_page_source_et_non_une_constante`.
PROJETS_ETRANGERS = ("projet_du_voisin", "projet_archives_2019")

#: **Deux** libelles de chaine differents : deux pages de calibration au meme
#: libelle rendraient invisible un profil qui ecrase l'autre.
LIBELLES_DE_CHAINE = (
    "hp envy 4520 tiff 600 dpi auto corr off",
    "epson v600 tiff 1200 dpi profil scanner",
)


def planche(
    *,
    lot_id: str,
    page_index: int,
    page_count: int = 2,
    project_id: str = PROJET_COURANT,
    rush_id: str = "rush_temoin",
    fps_target: float = 24.0,
    timecode_base_fps: str = "25/1",
) -> dict:
    """Une planche d'images, par son vrai producteur.

    Les emplacements sont **distinguables** (rangs et timecodes tous differents),
    parce qu'un appariement positionnel inverse ne se voit pas sur un remplissage
    uniforme.
    """
    return payload_io.build_page_payload(
        project_id=project_id,
        rush_id=rush_id,
        lot_id=lot_id,
        page_index=page_index,
        page_count=page_count,
        fps_target=fps_target,
        timecode_base_fps=timecode_base_fps,
        template_id="tpl-a4-portrait-4f-v2",
        patch_preset_id="patches-14-v3",
        target_colorspace="rec709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[
            {
                "slot_index": 2 * page_index + rang,
                "frame_timecode": f"00:00:{page_index:02d}:{rang:02d}",
            }
            for rang in range(2)
        ],
        page_role=page_roles.PAGE_ROLE_IMAGES,
    )


def page_de_calibration(*, libelle: str) -> dict:
    """Une page de calibration d'apres l'AC 8bis de 5.23, par son vrai producteur.

    Elle ne porte **ni** `project_id`, **ni** `rush_id`, **ni** `lot_id`, **ni**
    cadence (`io.payload.CALIBRATION_ABSENT_FIELDS`) : c'est ce qui rend le
    controle de projet inapplicable a cette feuille, et c'est le point de la
    frontiere negative de l'AC 4.
    """
    return payload_io.build_page_payload(
        project_id=None,
        rush_id=None,
        lot_id=None,
        page_index=0,
        page_count=2,
        fps_target=None,
        timecode_base_fps=None,
        template_id="tpl-a4-portrait-4f-v2",
        patch_preset_id="patches-14-v3",
        target_colorspace="rec709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[],
        page_role=page_roles.PAGE_ROLE_CALIBRATION,
        scan_chain_label=libelle,
    )


def page(
    *,
    read_rank: int,
    source: str,
    page_index_source: int | None = None,
    payload: dict | None = None,
    refusal_reason: str | None = None,
) -> scan_sorting.PageAtrier:
    """Une page a trier. Le localisateur est **unique** par page, comme a l'ingestion."""
    return scan_sorting.PageAtrier(
        read_rank=read_rank,
        locator_source=source,
        locator_page_index=page_index_source,
        payload=payload,
        refusal_reason=refusal_reason,
    )


def vrac_de_reference() -> list[scan_sorting.PageAtrier]:
    """Un vrac qui porte **les quatre classes**, aucune cible en tete.

    Composition, et chaque ligne est un choix :

    * **trois** lots, aux `lot_id` differents. Deux d'entre eux sont **du meme
      rush a deux cadences** -- le cas nominal v2.1, et le regime exact ou `M25`
      avait mord : deux lots, jamais un lot fusionne ;
    * le lot « vise » par les tests d'appariement (`lot_beta_0002`) n'est **ni le
      premier arrive, ni le premier en identite** ;
    * **deux** pages de calibration, aux libelles differents ;
    * **deux** entrees de reliquat, aux motifs **differents** (QR muet, payload
      refuse) ;
    * **deux** pages hors perimetre, declarant **deux** projets differents.

    Douze pages au total. L'ordre d'arrivee est deliberement melange : le premier
    element est une planche du dernier lot en identite.
    """
    return [
        # rang 0 : une planche du lot qui vient en DERNIER dans l'ordre d'identite
        page(read_rank=0, source="vrac.pdf", page_index_source=0,
             payload=planche(lot_id="lot_gamma_0003", page_index=1,
                             timecode_base_fps="24/1")),
        page(read_rank=1, source="vrac.pdf", page_index_source=1,
             payload=planche(lot_id="lot_beta_0002", page_index=1)),
        page(read_rank=2, source="vrac.pdf", page_index_source=2,
             payload=page_de_calibration(libelle=LIBELLES_DE_CHAINE[0])),
        page(read_rank=3, source="vrac.pdf", page_index_source=3,
             payload=planche(lot_id="lot_alpha_0001", page_index=0)),
        page(read_rank=4, source="page_muette.tiff",
             payload=None),
        page(read_rank=5, source="vrac.pdf", page_index_source=4,
             payload=planche(lot_id="lot_beta_0002", page_index=0)),
        page(read_rank=6, source="etrangere_b.tiff",
             payload=planche(lot_id="lot_du_voisin_0001", page_index=0,
                             project_id=PROJETS_ETRANGERS[1])),
        page(read_rank=7, source="vrac.pdf", page_index_source=5,
             payload=planche(lot_id="lot_gamma_0003", page_index=0,
                             timecode_base_fps="24/1")),
        page(read_rank=8, source="page_perimee.tiff",
             payload=None,
             refusal_reason="Payload schema version '1.0' is unreadable"),
        page(read_rank=9, source="etrangere_a.tiff",
             payload=planche(lot_id="lot_du_voisin_0002", page_index=0,
                             project_id=PROJETS_ETRANGERS[0])),
        page(read_rank=10, source="vrac.pdf", page_index_source=6,
             payload=page_de_calibration(libelle=LIBELLES_DE_CHAINE[1])),
        page(read_rank=11, source="vrac.pdf", page_index_source=7,
             payload=planche(lot_id="lot_alpha_0001", page_index=1)),
    ]


def vue_canonique(partition: scan_sorting.PartitionDeVrac) -> dict:
    """La partition **sans les rangs de lecture**, pour comparer deux permutations.

    Permuter le vrac, c'est poser les memes feuilles sur la vitre dans un autre
    ordre : chaque page recoit alors un autre `read_rank`, ce qui est legitime.
    Ce qui doit etre **identique**, c'est le rangement : quels lots existent,
    quelles pages sont dans chacun, et dans quel ordre. La vue les compare par
    localisateur -- l'identifiant qui, lui, voyage avec la feuille.
    """
    return {
        "lots": [
            (lot.identite, [page.locator for page in lot.pages])
            for lot in partition.lots
        ],
        "calibration": [
            (page.locator, page.scan_chain_label)
            for page in partition.pages_de_calibration
        ],
        "reliquat": [
            (entree.locator, entree.motif) for entree in partition.reliquat
        ],
        "hors_perimetre": [
            (entree.locator, entree.motif, entree.projet_a_utiliser)
            for entree in partition.hors_perimetre
        ],
    }
