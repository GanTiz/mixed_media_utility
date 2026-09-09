"""Story 11.4, lot B2 -- `PrevizSession` porte `cadence_corroboree`.

`EPIC11-ARB-76`, et le fait F6 de la story : `SourceQualification.cadence_corroboree`
n'est consultee qu'en `extraction.py`, dans `run_extraction`. `prepare_previz`
calcule pourtant la qualification et jette cette information. Sur un conteneur
avare -- Matroska sans duree ni `nb_frames` --, le temps 1 de l'atelier reussit
et le temps 2 refuse : on regarde vingt minutes de previz, puis l'extraction
refuse.

L'ajout est **pur** : la previz ne refuse rien de plus qu'avant, elle rend une
donnee de plus. Les deux regimes sont mesures, jamais un seul -- un champ
cable en dur a `True` (ou a `False`) passerait un banc mono-regime.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import cadence_previz, extraction
from mixed_media_utility.cadence_previz import prepare_previz


def probe_corroborant(**surcharges) -> dict:
    """Un probe qui recoupe sa cadence : duree ET nombre d'images declares."""
    flux = {
        "codec_type": "video",
        "codec_name": "h264",
        "pix_fmt": "yuv420p",
        "width": 320,
        "height": 180,
        "r_frame_rate": "25/1",
        "avg_frame_rate": "25/1",
        "nb_frames": "50",
        "duration": "2.0",
    }
    flux.update(surcharges)
    return {"streams": [flux], "format": {"tags": {}}}


def probe_avare() -> dict:
    """Le conteneur Matroska du fait F6 : ni duree de flux, ni `nb_frames`.

    Les deux garde-fous contre une cadence variable tombent ensemble, pour la
    meme cause, et `SourceQualification.cadence_corroboree` rend `False`.
    """
    flux = probe_corroborant()["streams"][0]
    del flux["nb_frames"]
    del flux["duration"]
    return {"streams": [flux], "format": {"tags": {}}}


#: Les deux regimes, distinguables par leur probe **et** par leur verdict
#: attendu. La cible du test -- le regime non corrobore, celui du defaut -- est
#: en **seconde** position : un champ qui rendrait toujours la valeur du
#: premier cas ne se demasque pas autrement.
REGIMES: tuple[tuple[str, object, bool], ...] = (
    ("conteneur bavard (duree + nb_frames)", probe_corroborant, True),
    ("conteneur avare (ni duree ni nb_frames)", probe_avare, False),
)


@pytest.fixture()
def rush(tmp_path: Path) -> Path:
    chemin = tmp_path / "rush.mp4"
    chemin.write_bytes(b"fake")
    return chemin


@pytest.mark.parametrize("nom, fabrique_probe, attendu", REGIMES,
                         ids=[cas[0] for cas in REGIMES])
def test_la_session_porte_le_verdict_de_corroboration_de_la_source(
    monkeypatch, rush, nom, fabrique_probe, attendu
):
    """AC 5.4b : la session dit ce que la qualification sait, dans les deux sens.

    Sur le conteneur avare, `resolve_source_frame_count` paie un comptage
    exact ; il est ici rendu par un double, pour que la mesure porte sur la
    corroboration et non sur la disponibilite d'ffprobe.
    """
    monkeypatch.setattr(extraction, "count_frames_exact",
                        lambda *a, **k: 50)
    session = prepare_previz(
        video_path=rush, fps_targets=[5.0], probe=fabrique_probe())
    assert session.cadence_corroboree is attendu


@pytest.mark.parametrize("nom, fabrique_probe, attendu", REGIMES,
                         ids=[cas[0] for cas in REGIMES])
def test_la_previz_reussit_dans_les_deux_regimes(
    monkeypatch, rush, nom, fabrique_probe, attendu
):
    """L'ajout est PUR : le temps 1 n'a rien gagne comme motif de refus.

    C'est le volet qui interdit de « combler » le fait F6 en refusant des la
    previz -- ce que `EPIC11-ARB-76` ecarte nommement : la lecture comparee
    n'ecrit rien, elle n'a pas besoin de la garde qui protege une ecriture.
    """
    monkeypatch.setattr(extraction, "count_frames_exact",
                        lambda *a, **k: 50)
    session = prepare_previz(
        video_path=rush, fps_targets=[5.0], probe=fabrique_probe())
    assert session.fps_targets == (5.0,)
    assert len(session.selections) == 1
    assert session.selections[0].expected_frame_count == 10


def test_le_verdict_vient_de_la_qualification_et_pas_d_une_constante(
    monkeypatch, rush
):
    """La valeur est LUE chez `qualify_source`, elle n'est pas recalculee ici.

    Une seconde implementation du critere -- par exemple « `nb_frames` est
    present » -- serait vraie sur les deux regimes ci-dessus et fausse ici :
    la qualification est truquee pour rendre `False` sur un probe qui, lui,
    corrobore. Seule une session qui consulte reellement la qualification
    suit.
    """
    vraie_qualification = extraction.qualify_source

    def qualification_truquee(probe):
        reelle = vraie_qualification(probe)
        # Un conteneur bavard, mais une qualification qui dit non : seule la
        # lecture de `cadence_corroboree` peut rendre `False` ici.
        return extraction.SourceQualification(
            fps_source=reelle.fps_source,
            stream_duration_seconds=None,
            declared_frame_count=None,
            start_timecode=reelle.start_timecode,
            avg_frame_rate=reelle.avg_frame_rate,
        )

    monkeypatch.setattr(extraction, "count_frames_exact", lambda *a, **k: 50)
    monkeypatch.setattr(extraction, "qualify_source", qualification_truquee)
    session = prepare_previz(
        video_path=rush, fps_targets=[5.0], probe=probe_corroborant())
    assert session.cadence_corroboree is False


def test_le_champ_est_bien_un_champ_gele_de_la_dataclass():
    """Frontiere : `PrevizSession` reste une dataclass gelee, champ compris."""
    import dataclasses

    champs = {champ.name: champ for champ in
              dataclasses.fields(cadence_previz.PrevizSession)}
    assert "cadence_corroboree" in champs
    assert champs["cadence_corroboree"].type in ("bool", bool)
    with pytest.raises(dataclasses.FrozenInstanceError):
        session = cadence_previz.PrevizSession(
            video_path=Path("rush.mp4"),
            fps_source=__import__("fractions").Fraction(25, 1),
            source_frame_count=50,
            source_frame_count_is_exact=True,
            start_timecode=None,
            stream_duration_seconds=2.0,
            fps_targets=(5.0,),
            selections=(),
            schedules=(),
            cadence_corroboree=True,
        )
        session.cadence_corroboree = False
