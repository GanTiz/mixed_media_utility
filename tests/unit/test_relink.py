"""Tests du coeur du relink (story 2.8): identite, statut de liaison.

Regle des fabriques du depot (CLAUDE.md, deux occurrences payees en 5.6/5.7):
toute fabrique multi-elements produit des elements DISTINGUABLES, et au moins
un test place la cible hors premiere position. Applique ici a
`_manifest_deux_rushes` (AC 4).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import relink


# --------------------------------------------------------------------------
# Fabriques
# --------------------------------------------------------------------------


def _rush(
    rush_id="rush-001",
    *,
    source_name="rush-001.mov",
    source_start_timecode="__absent__",
    source_path=None,
):
    entry = {"rush_id": rush_id}
    if source_name is not None:
        entry["source_name"] = source_name
    if source_start_timecode != "__absent__":
        entry["source_start_timecode"] = source_start_timecode
    if source_path is not None:
        entry["source_path"] = source_path
    return entry


def _lot(rush_id, *, lot_id=None, source_frame_count=None, is_exact=True):
    entry = {"lot_id": lot_id or f"{rush_id}_4", "rush_id": rush_id}
    if source_frame_count is not None:
        entry["source_frame_count"] = source_frame_count
        entry["source_frame_count_is_exact"] = is_exact
    return entry


def _manifest_un_rush(**kwargs):
    rush_kwargs = {
        key: kwargs.pop(key)
        for key in ("source_name", "source_start_timecode", "source_path")
        if key in kwargs
    }
    cardinal = kwargs.pop("source_frame_count", 120)
    is_exact = kwargs.pop("is_exact", True)
    return {
        "rushes": [_rush("rush-001", **rush_kwargs)],
        "lots": ([_lot("rush-001", source_frame_count=cardinal, is_exact=is_exact)]
                 if cardinal is not None else []),
    }


def _manifest_deux_rushes():
    """Deux rushs DISTINGUABLES (nom, cardinal, timecode differents),
    rush-002 -- la cible de nos tests -- en SECONDE position dans `rushes[]`
    ET dans `lots[]` (AC 4: un `find` fautif qui rendrait le premier element
    ne se demasque pas autrement -- mutants M25/M33)."""
    return {
        "rushes": [
            _rush("rush-001", source_name="rush-001.mov", source_start_timecode="00:00:01:00"),
            _rush("rush-002", source_name="rush-002.mov", source_start_timecode="00:00:02:00"),
        ],
        "lots": [
            _lot("rush-001", source_frame_count=100),
            _lot("rush-002", source_frame_count=240),
        ],
    }


def _candidat(nom="rush-001.mov", cardinal=120, exact=True, timecode=None):
    return relink.ProbeCandidat(
        nom_de_base=nom, cardinal_frames=cardinal, cardinal_est_exact=exact,
        timecode_depart=timecode,
    )


# --------------------------------------------------------------------------
# charger_reference / resoudre_rush_id
# --------------------------------------------------------------------------


def test_charger_reference_lit_les_trois_criteres() -> None:
    manifest = _manifest_un_rush(source_start_timecode="00:00:00:10")

    reference = relink.charger_reference(manifest, "rush-001")

    assert reference.source_name == "rush-001.mov"
    assert reference.source_frame_count == 120
    assert reference.source_frame_count_is_exact is True
    assert reference.source_start_timecode == "00:00:00:10"
    assert reference.criteres_verifiables == relink.CRITERES_IDENTITE_RELINK
    assert reference.criteres_non_verifiables == ()
    assert reference.barren is False


def test_charger_reference_rush_inconnu_leve_refus_nomme() -> None:
    manifest = _manifest_un_rush()

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.charger_reference(manifest, "rush-999")

    assert excinfo.value.reason == relink.REFUS_RUSH_INCONNU


def test_charger_reference_rush_barren_toutes_references_non_verifiables() -> None:
    """Manifest ne du scan seul: entree de rush a rush_id nu."""
    manifest = {"rushes": [{"rush_id": "rush-001"}], "lots": []}

    reference = relink.charger_reference(manifest, "rush-001")

    assert reference.barren is True
    assert reference.criteres_verifiables == ()
    assert reference.criteres_non_verifiables == relink.CRITERES_IDENTITE_RELINK


def test_charger_reference_timecode_absent_mais_rush_extrait_reste_verifiable() -> None:
    """Rush normalement extrait (nom + cardinal presents), source non taguee:
    le timecode reste un critere VERIFIABLE, comparable a l'absence (AC 2,
    point 3) -- distinct du cas barren ci-dessus."""
    manifest = _manifest_un_rush()  # source_start_timecode absent par defaut

    reference = relink.charger_reference(manifest, "rush-001")

    assert reference.barren is False
    assert "source_start_timecode" in reference.criteres_verifiables
    assert reference.source_start_timecode is None


def test_charger_reference_cardinaux_divergents_entre_lots_refuse() -> None:
    manifest = {
        "rushes": [_rush("rush-001")],
        "lots": [
            _lot("rush-001", lot_id="rush-001_4", source_frame_count=120),
            _lot("rush-001", lot_id="rush-001_2", source_frame_count=121),
        ],
    }

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.charger_reference(manifest, "rush-001")

    assert excinfo.value.reason == relink.REFUS_CARDINAUX_DIVERGENTS


def test_reference_duree_ignore_les_lots_des_autres_rushs() -> None:
    """AC 4: le lot d'un AUTRE rush, cardinal different, precede dans
    `lots[]` celui du rush vise -- la reference doit rester celle du BON
    rush."""
    manifest = _manifest_deux_rushes()

    reference = relink.charger_reference(manifest, "rush-002")

    assert reference.source_frame_count == 240  # pas 100 (rush-001)


def test_resoudre_rush_id_omis_sur_un_seul_rush_passe() -> None:
    manifest = _manifest_un_rush()

    assert relink.resoudre_rush_id(manifest, None) == "rush-001"


def test_resoudre_rush_id_omis_sur_deux_rushs_liste_les_deux() -> None:
    manifest = _manifest_deux_rushes()

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.resoudre_rush_id(manifest, None)

    assert excinfo.value.reason == relink.REFUS_RUSH_AMBIGU
    assert "rush-001" in str(excinfo.value)
    assert "rush-002" in str(excinfo.value)


def test_resoudre_rush_id_aucun_rush_distingue_de_l_ambiguite() -> None:
    """Patch 4a (revue de 2.8): manifest sans aucun rush -- ce n'est pas une
    ambiguite (rien a departager), c'est un refus distinct qui le dit."""
    manifest = {"rushes": [], "lots": []}

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.resoudre_rush_id(manifest, None)

    assert excinfo.value.reason == relink.REFUS_AUCUN_RUSH
    assert excinfo.value.reason != relink.REFUS_RUSH_AMBIGU


def test_resoudre_rush_id_explicite_sur_deux_rushs_passe() -> None:
    manifest = _manifest_deux_rushes()

    assert relink.resoudre_rush_id(manifest, "rush-002") == "rush-002"


def test_resoudre_rush_id_inconnu_refuse() -> None:
    manifest = _manifest_deux_rushes()

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.resoudre_rush_id(manifest, "rush-999")

    assert excinfo.value.reason == relink.REFUS_RUSH_INCONNU


# --------------------------------------------------------------------------
# evaluer_candidat
# --------------------------------------------------------------------------


def test_evaluer_candidat_nom_sensible_a_la_casse() -> None:
    reference = relink.charger_reference(_manifest_un_rush(), "rush-001")
    candidat = _candidat(nom="Rush-001.mov")

    evaluations = relink.evaluer_candidat(reference, candidat)

    nom = next(e for e in evaluations if e.critere == "source_name")
    assert nom.verifiable is True
    assert nom.satisfait is False


def test_evaluer_candidat_duree_egalite_stricte_si_deux_cotes_exacts() -> None:
    reference = relink.charger_reference(_manifest_un_rush(source_frame_count=120), "rush-001")

    assert relink.evaluer_candidat(reference, _candidat(cardinal=120, exact=True))[1].satisfait
    assert not relink.evaluer_candidat(reference, _candidat(cardinal=121, exact=True))[1].satisfait


def test_evaluer_candidat_duree_tolere_un_ecart_d_une_frame_si_estime() -> None:
    reference = relink.charger_reference(
        _manifest_un_rush(source_frame_count=120, is_exact=False), "rush-001"
    )

    assert relink.evaluer_candidat(reference, _candidat(cardinal=121, exact=True))[1].satisfait
    assert not relink.evaluer_candidat(reference, _candidat(cardinal=122, exact=True))[1].satisfait


def test_evaluer_candidat_timecode_absence_compare_a_absence() -> None:
    reference = relink.charger_reference(_manifest_un_rush(), "rush-001")  # timecode absent

    satisfait_absent = relink.evaluer_candidat(reference, _candidat(timecode=None))[2].satisfait
    satisfait_present = relink.evaluer_candidat(reference, _candidat(timecode="00:00:00:05"))[2].satisfait

    assert satisfait_absent is True
    assert satisfait_present is False


def test_evaluer_candidat_criteres_non_verifiables_rendent_none() -> None:
    reference = relink.charger_reference(
        {"rushes": [{"rush_id": "rush-001"}], "lots": []}, "rush-001"
    )

    evaluations = relink.evaluer_candidat(reference, _candidat())

    assert all(e.verifiable is False and e.satisfait is None for e in evaluations)


# --------------------------------------------------------------------------
# verifier_designation_manuelle (--video)
# --------------------------------------------------------------------------


def test_designation_manuelle_nominale_ne_leve_pas_et_rend_aucun_avertissement() -> None:
    reference = relink.charger_reference(
        _manifest_un_rush(source_start_timecode="00:00:00:00"), "rush-001"
    )
    probe = lambda chemin: _candidat(cardinal=120, timecode="00:00:00:00")

    avertissements = relink.verifier_designation_manuelle(
        Path("/n/importe/quoi.mov"), reference=reference, probe=probe
    )

    assert avertissements == ()


def test_designation_manuelle_critere_echec_refuse_avec_valeurs() -> None:
    reference = relink.charger_reference(_manifest_un_rush(source_frame_count=120), "rush-001")
    probe = lambda chemin: _candidat(cardinal=999)

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.verifier_designation_manuelle(
            Path("/x/rush-001.mov"), reference=reference, probe=probe
        )

    assert excinfo.value.reason == relink.REFUS_CRITERE_ECHEC
    assert "120" in str(excinfo.value)
    assert "999" in str(excinfo.value)


def test_designation_manuelle_probe_illisible_refuse_proprement() -> None:
    """Patch 1 (revue de 2.8): un `--video` vers un fichier corrompu/illisible
    doit lever un refus NOMME (REFUS_VIDEO_ILLISIBLE), jamais laisser
    l'exception du probe se propager brute. Meme trio d'exceptions que
    `rechercher_candidat` (extraction.ExtractionInputError,
    video_metadata.FfprobeError, OSError)."""
    from mixed_media_utility import extraction, video_metadata

    reference = relink.charger_reference(_manifest_un_rush(source_frame_count=120), "rush-001")

    for exception_levee in (
        extraction.ExtractionInputError("cadence non fiable"),
        video_metadata.FfprobeError("ffprobe a echoue"),
        OSError("fichier absent"),
    ):
        def probe(chemin, _exc=exception_levee):
            raise _exc

        with pytest.raises(relink.RelinkError) as excinfo:
            relink.verifier_designation_manuelle(
                Path("/x/corrompu.mov"), reference=reference, probe=probe
            )

        assert excinfo.value.reason == relink.REFUS_VIDEO_ILLISIBLE


def test_designation_manuelle_aucun_critere_verifiable_avertit_et_accepte() -> None:
    """Manifest barren: la designation manuelle passe quand meme,
    l'operateur est l'autorite (EPIC7-ARB-34)."""
    reference = relink.charger_reference({"rushes": [{"rush_id": "rush-001"}]}, "rush-001")
    probe = lambda chemin: _candidat(nom="peu-importe.mov")

    avertissements = relink.verifier_designation_manuelle(
        Path("/x/peu-importe.mov"), reference=reference, probe=probe
    )

    assert len(avertissements) == 1
    for critere in relink.CRITERES_IDENTITE_RELINK:
        assert critere in avertissements[0]


# --------------------------------------------------------------------------
# rechercher_candidat (--chercher)
# --------------------------------------------------------------------------


def test_recherche_refuse_si_une_reference_manque() -> None:
    reference = relink.charger_reference({"rushes": [{"rush_id": "rush-001"}]}, "rush-001")

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.rechercher_candidat(Path("/dossier"), reference=reference)

    assert excinfo.value.reason == relink.REFUS_CRITERE_NON_VERIFIABLE_RECHERCHE


def test_recherche_dossier_inexistant_refuse_distinct_de_aucun_candidat(tmp_path) -> None:
    """Patch 4b (revue de 2.8): --chercher vers un dossier qui n'existe pas
    doit se distinguer d'une recherche menee a bien mais infructueuse."""
    reference = relink.charger_reference(
        _manifest_un_rush(source_frame_count=120, source_start_timecode="00:00:00:00"),
        "rush-001",
    )
    dossier_inexistant = tmp_path / "n-existe-pas"

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.rechercher_candidat(dossier_inexistant, reference=reference)

    assert excinfo.value.reason == relink.REFUS_DOSSIER_RECHERCHE_INVALIDE
    assert excinfo.value.reason != relink.REFUS_AUCUN_CANDIDAT


def test_recherche_chemin_n_est_pas_un_dossier_refuse(tmp_path) -> None:
    """Meme refus quand le chemin passe existe mais n'est pas un repertoire
    (un fichier, par exemple)."""
    reference = relink.charger_reference(
        _manifest_un_rush(source_frame_count=120, source_start_timecode="00:00:00:00"),
        "rush-001",
    )
    fichier = tmp_path / "pas-un-dossier.txt"
    fichier.write_text("x")

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.rechercher_candidat(fichier, reference=reference)

    assert excinfo.value.reason == relink.REFUS_DOSSIER_RECHERCHE_INVALIDE


def test_recherche_nominale_trouve_un_candidat_en_sous_sous_dossier(tmp_path) -> None:
    reference = relink.charger_reference(
        _manifest_un_rush(source_frame_count=120, source_start_timecode="00:00:00:00"),
        "rush-001",
    )
    cible = tmp_path / "archive" / "2026" / "rush-001.mov"
    cible.parent.mkdir(parents=True)
    cible.write_bytes(b"x")

    def probe(chemin):
        assert chemin == cible
        return _candidat(cardinal=120, timecode="00:00:00:00")

    trouve = relink.rechercher_candidat(tmp_path, reference=reference, probe=probe)

    assert trouve == cible


def test_recherche_zero_candidat_nomme_criteres_et_dossier(tmp_path) -> None:
    reference = relink.charger_reference(
        _manifest_un_rush(source_frame_count=120, source_start_timecode="00:00:00:00"),
        "rush-001",
    )

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.rechercher_candidat(tmp_path, reference=reference, probe=lambda c: _candidat())

    assert excinfo.value.reason == relink.REFUS_AUCUN_CANDIDAT
    assert str(tmp_path) in str(excinfo.value)


def test_recherche_deux_candidats_conformes_refuse_en_listant_les_deux(tmp_path) -> None:
    reference = relink.charger_reference(
        _manifest_un_rush(source_frame_count=120, source_start_timecode="00:00:00:00"),
        "rush-001",
    )
    premier = tmp_path / "a" / "rush-001.mov"
    second = tmp_path / "b" / "rush-001.mov"
    for chemin in (premier, second):
        chemin.parent.mkdir(parents=True)
        chemin.write_bytes(b"x")

    def probe(chemin):
        return _candidat(cardinal=120, timecode="00:00:00:00")

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.rechercher_candidat(tmp_path, reference=reference, probe=probe)

    assert excinfo.value.reason == relink.REFUS_CANDIDATS_MULTIPLES
    assert str(premier) in str(excinfo.value)
    assert str(second) in str(excinfo.value)


def test_recherche_filtre_par_nom_avant_de_prober(tmp_path) -> None:
    """Cout maitrise (AC 2): un fichier au mauvais nom n'est jamais probe."""
    reference = relink.charger_reference(
        _manifest_un_rush(source_frame_count=120, source_start_timecode="00:00:00:00"),
        "rush-001",
    )
    mauvais_nom = tmp_path / "autre-fichier.mov"
    mauvais_nom.write_bytes(b"x")

    appels = []

    def probe(chemin):
        appels.append(chemin)
        return _candidat(cardinal=120, timecode="00:00:00:00")

    with pytest.raises(relink.RelinkError):
        relink.rechercher_candidat(tmp_path, reference=reference, probe=probe)

    assert appels == []


def test_recherche_candidat_illisible_est_ecarte_pas_fatal(tmp_path) -> None:
    from mixed_media_utility import extraction

    reference = relink.charger_reference(
        _manifest_un_rush(source_frame_count=120, source_start_timecode="00:00:00:00"),
        "rush-001",
    )
    illisible = tmp_path / "rush-001.mov"
    illisible.write_bytes(b"x")

    def probe(chemin):
        raise extraction.ExtractionInputError("cadence non fiable")

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.rechercher_candidat(tmp_path, reference=reference, probe=probe)

    assert excinfo.value.reason == relink.REFUS_AUCUN_CANDIDAT


# --------------------------------------------------------------------------
# statut_de_liaison / refus_necessite_le_rush (AC 3)
# --------------------------------------------------------------------------


def test_statut_de_liaison_chemin_absent() -> None:
    assert relink.statut_de_liaison({"rush_id": "rush-001"}) == relink.DELINKE_CHEMIN_ABSENT


def test_statut_de_liaison_chemin_existant_est_lie(tmp_path) -> None:
    fichier = tmp_path / "rush-001.mov"
    fichier.write_bytes(b"x")

    statut = relink.statut_de_liaison({"rush_id": "rush-001", "source_path": str(fichier)})

    assert statut == relink.LIE


def test_statut_de_liaison_chemin_mort() -> None:
    statut = relink.statut_de_liaison(
        {"rush_id": "rush-001", "source_path": "/n/existe/pas/rush-001.mov"}
    )

    assert statut == relink.DELINKE_CHEMIN_MORT


def test_statut_de_liaison_accepte_un_verificateur_injecte() -> None:
    statut = relink.statut_de_liaison(
        {"rush_id": "rush-001", "source_path": "/peu/importe.mov"},
        existe=lambda chemin: True,
    )

    assert statut == relink.LIE


def test_refus_necessite_le_rush_nomme_relink_et_le_rush_id() -> None:
    erreur = relink.refus_necessite_le_rush("encode", "rush-002")

    assert erreur.reason == relink.REFUS_RUSH_REQUIS
    assert "relink" in str(erreur)
    assert "rush-002" in str(erreur)


# --------------------------------------------------------------------------
# appliquer_relink -- frontiere structurelle (AC 2)
# --------------------------------------------------------------------------


def test_appliquer_relink_ne_touche_que_le_bon_rush() -> None:
    """AC 4: relink du rush en SECONDE position -- le champ mis a jour est
    celui du BON rush, l'autre entree est intacte."""
    manifest = _manifest_deux_rushes()

    resultat = relink.appliquer_relink(manifest, "rush-002", "/mnt/nouveau/rush-002.mov")

    rushes = {rush["rush_id"]: rush for rush in resultat["rushes"]}
    assert rushes["rush-002"]["source_path"] == "/mnt/nouveau/rush-002.mov"
    assert "source_path" not in rushes["rush-001"]
    # Rien d'autre n'a bouge (comparaison structurelle avant/apres).
    assert rushes["rush-001"] == manifest["rushes"][0]
    assert resultat["lots"] == manifest["lots"]


def test_appliquer_relink_ne_mute_pas_le_manifest_recu() -> None:
    manifest = _manifest_un_rush()

    relink.appliquer_relink(manifest, "rush-001", "/x/rush-001.mov")

    assert "source_path" not in manifest["rushes"][0]


def test_appliquer_relink_rush_inconnu_refuse() -> None:
    manifest = _manifest_un_rush()

    with pytest.raises(relink.RelinkError) as excinfo:
        relink.appliquer_relink(manifest, "rush-999", "/x.mov")

    assert excinfo.value.reason == relink.REFUS_RUSH_INCONNU
