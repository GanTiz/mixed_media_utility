"""Story 5.23, `EPIC5-ARB-92` -- une pile de pages de calibration seules est **acceptee**.

Mandat d'Egan, verbatim: « L'objet de cette story est entre autre de generer une page de
calibration autonome. Donc un lot qui ne possede qu'une page de calibration doit etre
accepte avec la commande de calibration ! Sans la commande de calibration on doit etre
invite (Y/N) a passer en mode calibration. »

Etat du depot avant ce lot, verifie en le lisant plutot qu'en le supposant: `scan ...
calibrate` sur cette pile **fonctionnait deja** -- `check_scan_conflicts`, donc
`_check_pile_homogene`, donc le refus, n'est appele que depuis `scan_command` -- et
`test_pile_mixte_refus.py` le garde. Ce qui manquait est l'autre moitie: `scan` **sans**
`calibrate` levait `REFUS_PILE_SANS_PLANCHE`, avec un message qui nommait pourtant le bon
geste. Ce fichier couvre cette moitie-la, et ses frontieres.

**Ce que ce lot ne change pas, et qui est teste ici comme frontiere negative**: la pile
**mixte** -- page de calibration et planches d'images en une passe -- reste refusee
(`EPIC5-ARB-86`, deux passes separees, question reportee a la story de vrac). Si la
bascule mordait sur elle, la distinction que l'AC 10 a construite serait perdue.

Budget: le fichier ne compose aucun PDF et ne scanne aucun raster reel. Le seul test de
bout en bout ingere un aplat de 400x600 et substitue l'ajustement colorimetrique, exerce
par ses vrais producteurs ailleurs (`test_calibration_page_source`).
"""

from __future__ import annotations

import ast
import pathlib
import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(pathlib.Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from mixed_media_utility import cli  # noqa: E402
from mixed_media_utility import page_roles  # noqa: E402
from mixed_media_utility import scan_chain, scan_detection, scan_ingest  # noqa: E402
from mixed_media_utility import scan_calibrate  # noqa: E402
from mixed_media_utility.io import calibration_profile  # noqa: E402
from mixed_media_utility.io import payload as payload_io  # noqa: E402
from mixed_media_utility.io import project_layout, reconstruction, scan_manifest  # noqa: E402

import test_calibration_page_source as couleur  # noqa: E402
from mixed_media_utility import color_calibration as cc  # noqa: E402

CLI_SOURCE = SRC / "mixed_media_utility" / "cli.py"

#: **Les deux codes de refus, ecrits en litteral** et jamais lus sur la constante que le
#: code utilise. Une assertion qui appellerait `reconstruction.REFUS_PILE_SANS_PLANCHE`
#: resterait vraie apres le mutant qui fond les deux refus en un seul code -- c'est la
#: tautologie nommee au mandat de ce lot.
REFUS_MIXTE_LITTERAL = "pile-mixte-calibration-et-planches"
REFUS_SANS_PLANCHE_LITTERAL = "pile-sans-planche-d-images"


# ---------------------------------------------------------------------------
# Fabriques -- deux elements distinguables, cible jamais en premiere position
# ---------------------------------------------------------------------------

#: Deux libelles de chaine **differents** (regle des fabriques du depot): une pile dont
#: les deux pages de calibration porteraient le meme libelle rendrait invisible une
#: partition qui n'en verrait qu'une, ou qui compterait deux fois la meme.
LIBELLES = (
    "canon lide 400 tiff 600 dpi sans correction",
    "epson perfection v850 tiff 1200 dpi profil scanner",
)

#: Deux lots **differents**, meme motif: une pile de planches uniformes ne dirait rien
#: d'une partition qui ne lirait que `payloads[0]`.
LOTS = ("lot_temoin_0001", "lot_temoin_0002")


def _planche(*, page_index: int, page_count: int, lot_id: str) -> dict:
    """Une planche d'images, par son **vrai** producteur (`build_page_payload`)."""
    return payload_io.build_page_payload(
        project_id="projet_demo",
        rush_id="rush_temoin",
        lot_id=lot_id,
        page_index=page_index,
        page_count=page_count,
        fps_target=24.0,
        timecode_base_fps="25/1",
        template_id="tpl-a4-portrait-4f-v2",
        patch_preset_id="patches-14-v3",
        target_colorspace="rec709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[
            {"slot_index": 2 * page_index + rang,
             "frame_timecode": f"00:00:{page_index:02d}:{rang:02d}"}
            for rang in range(2)
        ],
        page_role=page_roles.PAGE_ROLE_IMAGES,
    )


def _page_de_calibration(*, page_index: int, page_count: int, libelle: str) -> dict:
    """Une page de calibration **d'apres l'AC 8bis**, par son vrai producteur.

    C'est le producteur qui retire lui-meme les quatre champs de niveau lot. Un
    dictionnaire ecrit a la main ici pourrait les porter par distraction, et la pile
    cessee silencieusement d'etre celle que ce lot traite.
    """
    return payload_io.build_page_payload(
        project_id=None,
        rush_id=None,
        lot_id=None,
        page_index=page_index,
        page_count=page_count,
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


def _pile_de_calibration_seule() -> list[dict]:
    """Deux pages de calibration distinguables, et **aucune** planche."""
    return [
        _page_de_calibration(page_index=0, page_count=2, libelle=LIBELLES[0]),
        _page_de_calibration(page_index=1, page_count=2, libelle=LIBELLES[1]),
    ]


def _pile_de_planches_seules() -> list[dict]:
    """Le regime nominal du scan: trois planches, deux lots distinguables."""
    return [
        _planche(page_index=0, page_count=3, lot_id=LOTS[0]),
        _planche(page_index=1, page_count=3, lot_id=LOTS[0]),
        _planche(page_index=2, page_count=3, lot_id=LOTS[1]),
    ]


def _pile_mixte() -> list[dict]:
    """Une planche, **puis** deux pages de calibration, **puis** une planche.

    La cible n'est ni en premiere ni en derniere position, et la pile porte deux pages
    de calibration distinguables: une lecture qui s'arreterait a `payloads[0]`, ou a la
    premiere page trouvee, resterait verte sur une fabrique mono-element placee en tete.
    """
    return [
        _planche(page_index=1, page_count=4, lot_id=LOTS[0]),
        _page_de_calibration(page_index=0, page_count=4, libelle=LIBELLES[0]),
        _page_de_calibration(page_index=3, page_count=4, libelle=LIBELLES[1]),
        _planche(page_index=2, page_count=4, lot_id=LOTS[0]),
    ]


class _EntreeInteractive:
    """Une entree standard qui se **declare** terminal, sans en etre un.

    Substituee a `sys.stdin`: c'est le seul moyen d'exercer le regime interactif dans
    une suite qui, elle, ne l'est jamais. Le regime hors terminal est exerce par
    l'entree reelle de pytest, qui n'est pas un tty.
    """

    def isatty(self) -> bool:
        return True


def _interactif(monkeypatch, reponse: str | None) -> list[str]:
    """Rendre l'entree standard « interactive » et scripter la reponse a l'invite.

    `reponse=None` simule une fin de flux (`EOFError`), qui est le regime d'un tube
    ferme. Rend la liste des invites reellement posees: une frontiere negative se
    verifie sur elle, et non sur l'absence d'un effet.
    """
    invites: list[str] = []
    monkeypatch.setattr(sys, "stdin", _EntreeInteractive())

    def _input(*args):
        invites.append("".join(str(a) for a in args))
        if reponse is None:
            raise EOFError
        return reponse

    monkeypatch.setattr("builtins.input", _input)
    return invites


def _logger(tmp_path: pathlib.Path):
    project_layout.ensure_project_layout(tmp_path)
    return cli._configure_scan_logger(tmp_path)


# ---------------------------------------------------------------------------
# Le predicat: quelle pile bascule, et laquelle ne bascule pas
# ---------------------------------------------------------------------------


def test_le_predicat_reconnait_une_pile_de_pages_de_calibration_seules() -> None:
    """Le regime que `EPIC5-ARB-92` fait passer du refus a la bascule."""
    assert reconstruction.pile_sans_planche_d_images(_pile_de_calibration_seule()) is True


def test_le_predicat_ne_reconnait_pas_une_pile_mixte() -> None:
    """Frontiere negative 1: la pile mixte reste refusee (`EPIC5-ARB-86`).

    C'est le mutant le plus dangereux de ce lot: une bascule qui mordrait ici ferait
    consigner un profil de chaine depuis une pile dont les planches d'images seraient
    silencieusement perdues -- et ferait fondre en un seul regime les deux que l'AC 10 a
    separes.
    """
    assert reconstruction.pile_sans_planche_d_images(_pile_mixte()) is False


def test_le_predicat_ne_reconnait_pas_une_pile_de_planches_seules() -> None:
    """Frontiere negative 2: le regime nominal du scan ne bouge pas d'un cran."""
    assert reconstruction.pile_sans_planche_d_images(_pile_de_planches_seules()) is False


def test_le_predicat_rend_faux_sur_une_pile_vide() -> None:
    """Une pile vide n'est pas une pile de calibration.

    `scan` n'atteint le predicat que sur des pages identifiees, mais un `all()` nu sur
    une liste vide rend `True`: la bascule aurait alors lieu sur une passe qui n'a rien
    lu, c'est-a-dire un `calibrate` sans page de calibration -- un echec deguise en
    geste utile.
    """
    assert reconstruction.pile_sans_planche_d_images([]) is False


def test_le_predicat_et_le_refus_lisent_la_meme_partition() -> None:
    """La bascule mord **exactement** la ou le refus tombait, et pas ailleurs.

    C'est la propriete qui interdit la seconde redaction de la partition: si `cli`
    reconnaissait la pile autrement que `_check_pile_homogene`, il existerait des piles
    qui basculent sans que le refus les vise, ou l'inverse -- une bande ou la commande
    n'aurait plus de comportement defini.

    Exercee sur une pile de planches **amputees**, un champ different par page: la
    partition se lit sur les champs et non sur le role (`_check_pile_homogene`), donc
    ces deux planches tronquees sont vues comme des pages sans identite de lot par les
    deux chemins a la fois.
    """
    champs = sorted(payload_io.CALIBRATION_ABSENT_FIELDS)
    assert len(champs) >= 2, champs
    pile = _pile_de_planches_seules()[:2]
    pile = [{cle: valeur for cle, valeur in page.items() if cle != champ}
            for page, champ in zip(pile, champs[:2])]

    assert reconstruction.pile_sans_planche_d_images(pile) is True
    with pytest.raises(reconstruction.ReconstructionError) as capture:
        reconstruction._check_pile_homogene(pile)
    assert capture.value.reason == REFUS_SANS_PLANCHE_LITTERAL


def test_les_deux_codes_de_refus_restent_distincts_au_litteral() -> None:
    """Les deux refus ne se fondent pas en un, et l'assertion ne passe par aucune constante.

    Un test ecrit `REFUS_PILE_MIXTE != REFUS_PILE_SANS_PLANCHE` resterait vrai apres le
    mutant qui donne aux deux la meme valeur **litterale** dans un troisieme nom. Les
    deux valeurs sont donc epinglees telles qu'elles sont ecrites.
    """
    assert reconstruction.REFUS_PILE_MIXTE == REFUS_MIXTE_LITTERAL
    assert reconstruction.REFUS_PILE_SANS_PLANCHE == REFUS_SANS_PLANCHE_LITTERAL
    assert REFUS_MIXTE_LITTERAL != REFUS_SANS_PLANCHE_LITTERAL


# ---------------------------------------------------------------------------
# L'invite -- les trois regimes de l'AC 5, sur ce geste-ci
# ---------------------------------------------------------------------------


def test_hors_terminal_la_bascule_a_lieu_sans_qu_aucune_invite_soit_posee(
    tmp_path, capsys, monkeypatch,
) -> None:
    """Le defaut hors terminal: **on bascule** (`EPIC5-ARB-92`).

    C'est la decision de fond de ce lot. Un refus hors terminal rendrait la commande
    inutilisable en script pour le seul regime qu'elle sert, et l'AC 5 a deja tranche
    dans ce sens: faire la chose utile plutot qu'echouer.

    L'invite est verifiee **absente** et pas seulement inoperante: un `input()` pose
    hors terminal leve `EOFError` sous pytest et bloque sous `cron`, ce que ce depot a
    deja paye deux fois.
    """
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail(
        "une invite a ete posee hors terminal"))
    assert cli._accepter_la_bascule_en_calibration(_logger(tmp_path)) is True
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("reponse", ["Y", "y", "oui", "", "  ", None])
def test_en_terminal_toute_reponse_qui_ne_commence_pas_par_n_bascule(
    tmp_path, monkeypatch, capsys, reponse,
) -> None:
    """Le defaut de l'invite est **basculer**, y compris sur Entree et sur fin de flux.

    Meme politique que l'AC 5 (`EPIC5-ARB-82` decision 6): « le geste par defaut est
    celui qui sert l'utilisateur, le geste explicite est celui qui s'en ecarte ». La
    fin de flux (`None` ci-dessus) compte comme une non-reponse, jamais comme un refus.
    """
    invites = _interactif(monkeypatch, reponse)
    assert cli._accepter_la_bascule_en_calibration(_logger(tmp_path)) is True
    assert len(invites) == 1, invites
    sortie = capsys.readouterr().out
    assert "[Y/n]" in sortie, sortie
    assert cli.SCAN_CALIBRATE_SUBCOMMAND in sortie, sortie


@pytest.mark.parametrize("reponse", ["n", "N", "non", "no"])
def test_en_terminal_une_reponse_qui_commence_par_n_ne_bascule_pas(
    tmp_path, monkeypatch, reponse,
) -> None:
    """Le `N` explicite est respecte: c'est un geste d'operateur, pas une suggestion."""
    invites = _interactif(monkeypatch, reponse)
    assert cli._accepter_la_bascule_en_calibration(_logger(tmp_path)) is False
    assert len(invites) == 1, invites


def test_un_refus_a_l_invite_laisse_la_pile_sur_son_refus_nomme(tmp_path) -> None:
    """Ce que `N` rend a l'operateur: le refus qui existait, avec son motif.

    La bascule refusee ne court-circuite rien -- la commande poursuit son chemin de scan
    de lot, ou cette pile n'a toujours aucune planche d'images. Le refus qu'elle y
    rencontre est celui d'avant ce lot, code compris.
    """
    project_layout.ensure_project_layout(tmp_path)
    with pytest.raises(reconstruction.ReconstructionError) as capture:
        scan_manifest.check_scan_conflicts(tmp_path, _pile_de_calibration_seule())
    assert capture.value.reason == REFUS_SANS_PLANCHE_LITTERAL
    assert cli.SCAN_CALIBRATE_SUBCOMMAND in str(capture.value)


# ---------------------------------------------------------------------------
# La decision complete -- l'invite ne se pose que derriere le predicat
# ---------------------------------------------------------------------------


def test_la_bascule_est_demandee_sur_une_pile_de_calibration_seule(
    tmp_path, monkeypatch,
) -> None:
    """Le regime nominal du livrable: la pile est reconnue, la question est posee."""
    invites = _interactif(monkeypatch, "Y")
    assert cli._bascule_en_calibration_demandee(
        _pile_de_calibration_seule(), _logger(tmp_path)) is True
    assert len(invites) == 1, invites


def test_aucune_invite_n_est_posee_sur_une_pile_mixte(tmp_path, monkeypatch, capsys) -> None:
    """Frontiere negative: la pile mixte ne declenche **pas** l'invite.

    L'entree est declaree interactive et la reponse scriptee serait `Y`: si l'invite se
    posait, la bascule aurait lieu. Elle n'est pas posee, donc la pile mixte suit son
    chemin de refus inchange.
    """
    invites = _interactif(monkeypatch, "Y")
    assert cli._bascule_en_calibration_demandee(_pile_mixte(), _logger(tmp_path)) is False
    assert invites == []
    assert capsys.readouterr().out == ""


def test_aucune_invite_n_est_posee_sur_une_pile_de_planches_seules(
    tmp_path, monkeypatch, capsys,
) -> None:
    """Frontiere negative: le regime nominal du scan ne voit passer aucune question."""
    invites = _interactif(monkeypatch, "Y")
    assert cli._bascule_en_calibration_demandee(
        _pile_de_planches_seules(), _logger(tmp_path)) is False
    assert invites == []
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# De bout en bout -- `scan` sans `calibrate` consigne le profil
# ---------------------------------------------------------------------------


def _dossier_de_scan(tmp_path: pathlib.Path) -> pathlib.Path:
    """Un dossier ingerable, une page synthetique sans QR ni marqueur."""
    dossier = tmp_path / "scan-calibration"
    dossier.mkdir()
    assert cv2.imwrite(str(dossier / "page.tif"),
                       np.full((400, 600, 3), 200, dtype=np.uint8))
    return dossier


def _detection_de(pile: list[dict]):
    """Un rapport de detection **portant** cette pile de payloads.

    Substitue a la detection reelle: exercer le decodage QR demanderait un raster scanne
    complet, ce que le budget de l'AC 9 exclut, et ce n'est pas le sujet -- la detection
    a sa propre suite. Ce que ce substitut laisse reel est tout ce que ce lot decide:
    la partition de la pile, l'invite, la bascule et l'ecriture du profil.
    """
    def _detecter(project_dir, report, *, dpi):
        return scan_detection.LotDetectionReport(
            ingest_slug=report.ingest_slug,
            scan_dpi=dpi,
            pages=tuple(
                scan_detection.DetectedPage(
                    read_rank=rang,
                    status=scan_detection.PAGE_OK,
                    locator_source=report.pages[0].locator.source_path,
                    locator_page_index=None,
                    qr_status="ok",
                    payload=payload,
                )
                for rang, payload in enumerate(pile)
            ),
            ingest_declared_dpi=report.declared_dpi,
        )
    return _detecter


def _moitie_amont(fabrique_de_rapport):
    """Adapter une fabrique de rapport en substitut de `detect_pages` (story 5.24).

    La detection a ete **fendue en deux moities** par 5.24 (`EPIC7-ARB-63`):
    `detect_pages` lit les pages une par une sans reconcilier, `build_lot_report`
    reconcilie **une** pile homogene. Le regime de vrac -- declenche par l'absence
    de `--lot-slug`, ce qui est le cas de tous les scans de ce lot -- appelle la
    moitie amont, et c'est donc elle que le substitut doit remplacer.

    Une **seule** redaction des pages truquees: cet adaptateur reutilise les
    fabriques de rapport ci-dessus au lieu de les recopier, sans quoi les deux
    divergeraient au premier champ ajoute.
    """
    def _detecter(project_dir, report, *, dpi):
        return dpi, fabrique_de_rapport(project_dir, report, dpi=dpi).pages
    return _detecter


def _chaine_derivee(dossier: pathlib.Path, tmp_path: pathlib.Path) -> str:
    """L'identite que la commande derive de ce scan, par le **vrai** producteur.

    L'ingestion temoin se fait dans un projet jetable, pour ne pas semer un `logs/` dans
    le projet que le test observe.
    """
    rapport = scan_ingest.ingest_scan_lot(tmp_path / "derive-a-part", dossier, dpi=600)
    return scan_chain.derive_chain_id(
        declared_dpi=rapport.declared_dpi,
        scan_input_format=scan_chain.report_scan_input_format(rapport))


def _correction_ajustee():
    """Une correction ajustee par le vrai producteur, sur un raster synthetique."""
    profil = couleur._calibration_profile()
    return cc.LotCorrection(
        source_page_id="calibration-0",
        template_id=couleur.TEMPLATE,
        profile=profil,
        correction_form_id=profil.correction_id,
    )


def test_scan_sans_calibrate_consigne_le_profil_de_la_chaine(
    tmp_path, monkeypatch, capsys,
) -> None:
    """Le livrable de `EPIC5-ARB-92`, de bout en bout et sans la sous-commande.

    `scan --project P --scan S --dpi D`, **sans** `calibrate`, sur une pile qui ne porte
    que des pages de calibration: la commande rend `0` et le profil de la chaine existe
    sur le disque, sous l'identite que le vrai deriveur donne a ce scan.

    Hors terminal (l'entree de pytest n'est pas un tty), donc aucune invite: c'est le
    regime du script, celui que le refus rendait inutilisable.
    """
    project_dir = tmp_path / "projet"
    dossier = _dossier_de_scan(tmp_path)
    monkeypatch.setattr(scan_detection, "detect_pages",
                        _moitie_amont(_detection_de(_pile_de_calibration_seule())))
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction", lambda *a, **k: _correction_ajustee())

    assert cli.main(["scan", "--project", str(project_dir), "--scan", str(dossier),
                     "--dpi", "600"]) == 0

    chaine = _chaine_derivee(dossier, tmp_path)
    assert calibration_profile.profile_exists(project_dir, chaine)
    assert calibration_profile.read_profile(project_dir, chaine)["chain_id"] == chaine
    sortie = capsys.readouterr().out
    assert "calibration ecrite pour la chaine" in sortie, sortie


def test_scan_sans_calibrate_n_ecrit_aucun_profil_quand_l_operateur_refuse(
    tmp_path, monkeypatch, capsys,
) -> None:
    """Le symetrique du precedent: `N` ne consigne rien, et la commande refuse.

    Sans lui, le test ci-dessus serait vrai d'une bascule inconditionnelle -- une
    commande qui consignerait le profil quelle que soit la reponse, c'est-a-dire une
    invite decorative.
    """
    project_dir = tmp_path / "projet"
    dossier = _dossier_de_scan(tmp_path)
    monkeypatch.setattr(scan_detection, "detect_pages",
                        _moitie_amont(_detection_de(_pile_de_calibration_seule())))
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction", lambda *a, **k: _correction_ajustee())
    _interactif(monkeypatch, "n")

    assert cli.main(["scan", "--project", str(project_dir), "--scan", str(dossier),
                     "--dpi", "600"]) == 1

    assert not calibration_profile.profile_exists(
        project_dir, _chaine_derivee(dossier, tmp_path))
    assert "pile ne porte aucune planche d'images" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Non-divergence: la bascule **appelle** la calibration, elle ne la reecrit pas
# ---------------------------------------------------------------------------


def _appels_de(nom_de_fonction: str) -> set[str]:
    """Les expressions appelees dans le corps de cette fonction du chemin de scan.

    **Story 11.6 (lot B) : le balayage porte sur les DEUX fichiers.** La
    consignation d'un profil de chaine a suivi l'ingestion et la detection dans
    le module de coeur `scan_calibrate` (`EPIC11-ARB-129`), comme la moitie aval
    du scan avait suivi `scan_write` en 11.4b ; la chercher dans `cli.py` seul
    ferait echouer la garde sans qu'une seule redaction n'ait disparu. La
    fonction reste **unique sur les deux fichiers reunis**, et c'est l'assertion
    de cardinal ci-dessous qui le mesure.
    """
    corps = []
    for fichier in (CLI_SOURCE, SRC / "mixed_media_utility" / "scan_calibrate.py"):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        corps += [n for n in ast.walk(arbre)
                  if isinstance(n, ast.FunctionDef) and n.name == nom_de_fonction]
    assert len(corps) == 1, (nom_de_fonction, len(corps))
    return {ast.unparse(n.func) for n in ast.walk(corps[0]) if isinstance(n, ast.Call)}


def test_la_bascule_et_la_sous_commande_consignent_par_le_meme_chemin() -> None:
    """Les deux voies **appellent** le meme consignateur, aucune ne le reecrit.

    C'est ce qui interdit qu'un profil ecrit par la bascule differe d'un profil ecrit
    par `scan ... calibrate`: il n'existe qu'une redaction du geste. Une seconde,
    copiee dans `scan_command`, divergerait au premier champ ajoute au document -- et le
    symptome serait un profil que la relecture ne comprend qu'a moitie.

    Le temoin positif (le consignateur ecrit bien le profil) est ce qui rend l'assertion
    d'absence concluante: sans lui, un consignateur devenu muet passerait ce test.
    """
    assert "_consigner_le_profil_de_chaine" in _appels_de("scan_command")
    # **Story 11.6 (lot B): un etage de plus, et une seule redaction quand
    # meme.** `scan_calibrate_command` n'appelle plus le consignateur
    # directement: elle appelle le point d'entree de coeur de `calibrate`, qui
    # l'appelle. La chaine entiere est donc mesuree, maillon par maillon.
    assert "scan_calibrate.calibrer_la_chaine" in _appels_de(
        "scan_calibrate_command")
    assert "consigner_le_profil_de_chaine" in _appels_de("calibrer_la_chaine")
    # `scan_command` ne redige aucune ecriture de profil a lui.
    ecritures = {appel for appel in _appels_de("scan_command")
                 if "write_profile" in appel or "profile_to_document" in appel}
    assert ecritures == set(), sorted(ecritures)
    # Temoin positif: c'est bien le consignateur qui ecrit. Il porte le meme nom
    # sans son tiret bas, dans `scan_calibrate` : `cli._consigner_le_profil_de_chaine`
    # n'en est plus que l'enveloppeur.
    consignateur = _appels_de("consigner_le_profil_de_chaine")
    assert any("write_profile" in appel for appel in consignateur), sorted(consignateur)
    assert any("profile_to_document" in appel for appel in consignateur), sorted(consignateur)


def test_la_sous_commande_calibrate_reste_hors_de_la_garde_de_pile() -> None:
    """Ce que ce lot ne devait pas casser: `scan ... calibrate` ne passe par aucun refus.

    Il fonctionnait deja sur cette pile avant `EPIC5-ARB-92` -- c'est la moitie du
    mandat qui etait tenue --, et l'extraction du consignateur ne devait pas l'y faire
    entrer. Verifie sur les **deux** fonctions, la sous-commande et le consignateur
    qu'elle appelle desormais: la garde ne s'est pas glissee dans l'extraction.
    """
    # **Story 11.6 (lot B): les deux fonctions sont devenues quatre**, l'etage
    # de terminal et l'etage de coeur pour chacune. La garde se verifie sur les
    # quatre: elle ne doit s'etre glissee dans aucun des deux deplacements.
    for nom in ("scan_calibrate_command", "_consigner_le_profil_de_chaine",
                "calibrer_la_chaine", "consigner_le_profil_de_chaine"):
        appels = _appels_de(nom)
        assert not any("check_scan_conflicts" in appel for appel in appels), (nom, appels)
    # Temoin positif: le balayage voit bien des appels dans ces deux corps.
    assert any("ingest_scan_lot" in appel for appel in _appels_de("calibrer_la_chaine"))
    assert any("_fit_lot_correction" in appel
               for appel in _appels_de("consigner_le_profil_de_chaine"))


# ---------------------------------------------------------------------------
# Correctif de revue (lot B, couche 2, C5): les feuilles muettes sont des planches
# ---------------------------------------------------------------------------

#: Le regime ferme ici, en une ligne: **N planches dont le QR n'a rien livre, plus une
#: page de calibration lue**. Avant le correctif, `pile_sans_planche_d_images` ne voyait
#: que les pages identifiees, donc rendait `True`, donc la commande basculait -- hors
#: terminal **sans invite**, sans ecrire une seule frame, et en rendant `0`.
#:
#: Le cardinal est **deux et non un**: une pile a une seule feuille muette laisserait
#: passer une garde ecrite `planches_muettes == 1`, et la regle des fabriques du depot
#: veut plus d'un element partout ou un compte est en jeu.
MUETTES = 2


def test_aucune_bascule_quand_des_feuilles_n_ont_pas_livre_leur_qr(
    tmp_path, monkeypatch, capsys,
) -> None:
    """Le defaut mesure: une feuille muette est une planche, jamais une feuille absente.

    L'entree est declaree interactive et la reponse scriptee serait `Y`: si l'invite se
    posait, la bascule aurait lieu. Elle n'est pas posee -- le predicat court-circuite
    avant --, donc la pile repart sur le chemin de scan de lot, ou elle rencontre son
    refus nomme. Un scan qui n'ecrit rien et rend un succes etait le pire des deux
    mondes.
    """
    invites = _interactif(monkeypatch, "Y")
    assert cli._bascule_en_calibration_demandee(
        _pile_de_calibration_seule(), _logger(tmp_path),
        planches_muettes=MUETTES) is False
    assert invites == []
    assert capsys.readouterr().out == ""


def test_les_feuilles_muettes_sont_nommees_au_journal_avant_le_refus(tmp_path) -> None:
    """Ne pas basculer ne suffit pas: l'operateur doit savoir **pourquoi**.

    Sans cette phrase, la pile repartirait sur le refus « la pile ne porte aucune
    planche d'images », qui serait faux de N feuilles posees sur la vitre -- le
    symetrique exact du message que le correctif supprime.

    Le cardinal est cherche **en litteral** dans la ligne, jamais lu sur la constante
    passee: un message qui ecrirait toujours « 0 feuille(s) » passerait autrement.
    """
    logger = _logger(tmp_path)
    assert cli._bascule_en_calibration_demandee(
        _pile_de_calibration_seule(), logger, planches_muettes=MUETTES) is False
    journal = (tmp_path / "logs" / "scan.log").read_text(encoding="utf-8")
    lignes = [ligne for ligne in journal.splitlines() if "n'ont pas livre leur QR" in ligne]
    assert len(lignes) == 1, journal
    assert "2 feuille(s)" in lignes[0], lignes[0]
    assert cli.SCAN_CALIBRATE_SUBCOMMAND in lignes[0], lignes[0]


def test_le_regime_nominal_ne_bouge_pas_quand_aucune_feuille_n_est_muette(
    tmp_path, monkeypatch,
) -> None:
    """Frontiere negative du correctif: sans feuille muette, la bascule a lieu comme avant.

    Sans ce test, le precedent serait vrai d'une garde qui aurait tue la bascule tout
    entiere -- c'est-a-dire du regime nominal du livrable de `EPIC5-ARB-92`.
    """
    invites = _interactif(monkeypatch, "Y")
    assert cli._bascule_en_calibration_demandee(
        _pile_de_calibration_seule(), _logger(tmp_path), planches_muettes=0) is True
    assert len(invites) == 1, invites


def test_le_defaut_du_cardinal_de_feuilles_muettes_est_zero(tmp_path, monkeypatch) -> None:
    """Le parametre est **optionnel**, et son defaut est celui d'avant le correctif.

    Les frontieres negatives deja ecrites plus haut appellent le predicat sans lui, et
    elles doivent continuer de mesurer ce qu'elles mesuraient.
    """
    _interactif(monkeypatch, "Y")
    assert cli._bascule_en_calibration_demandee(
        _pile_de_calibration_seule(), _logger(tmp_path)) is True


def _detection_avec_muettes(pile: list[dict], muettes: int):
    """Un rapport de detection ou `muettes` pages n'ont livre aucun payload.

    C'est l'ecart que le predicat ne voyait pas: `report.pages` depasse `identified`.
    Les pages muettes sont posees **avant** les pages lues, pour qu'un comptage qui
    s'arreterait a la premiere page identifiee ne passe pas.
    """
    def _detecter(project_dir, report, *, dpi):
        pages = tuple(
            scan_detection.DetectedPage(
                read_rank=rang,
                status=scan_detection.PAGE_REFUSED,
                locator_source=report.pages[0].locator.source_path,
                locator_page_index=None,
                qr_status="detected_but_unreadable",
                payload=None,
                refusal_reason="QR inexploitable: la feuille est posee a l'envers.",
            )
            for rang in range(muettes)
        ) + tuple(
            scan_detection.DetectedPage(
                read_rank=muettes + rang,
                status=scan_detection.PAGE_OK,
                locator_source=report.pages[0].locator.source_path,
                locator_page_index=None,
                qr_status="ok",
                payload=payload,
            )
            for rang, payload in enumerate(pile)
        )
        return scan_detection.LotDetectionReport(
            ingest_slug=report.ingest_slug, scan_dpi=dpi, pages=pages,
            ingest_declared_dpi=report.declared_dpi)
    return _detecter


def test_de_bout_en_bout_un_scan_a_planches_muettes_ne_consigne_aucun_profil(
    tmp_path, monkeypatch, capsys,
) -> None:
    """Le defaut complet, tel que l'operateur le subissait: succes muet, disque vide.

    Hors terminal (l'entree de pytest n'est pas un tty), sur une pile de deux feuilles
    muettes et deux pages de calibration lues. Avant le correctif: bascule silencieuse,
    profil ecrit, **aucune frame**, code `0`. Apres: aucun profil, code non nul, et le
    journal porte les deux faits.

    Le code attendu est ecrit **en litteral** (`1`), jamais compare a un autre appel.
    """
    project_dir = tmp_path / "projet"
    dossier = _dossier_de_scan(tmp_path)
    monkeypatch.setattr(scan_detection, "detect_pages",
                        _moitie_amont(_detection_avec_muettes(
                            _pile_de_calibration_seule(), MUETTES)))
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction", lambda *a, **k: _correction_ajustee())

    assert cli.main(["scan", "--project", str(project_dir), "--scan", str(dossier),
                     "--dpi", "600"]) == 1

    assert not calibration_profile.profile_exists(
        project_dir, _chaine_derivee(dossier, tmp_path))
    journal = (project_dir / "logs" / "scan.log").read_text(encoding="utf-8")
    assert "n'ont pas livre leur QR" in journal, journal
    # Et le motif de chaque feuille refusee est sorti, une fois par feuille: il etait
    # ecrit au rapport de detection et journalise nulle part.
    assert journal.count("Feuille refusee") == MUETTES, journal


def test_de_bout_en_bout_la_bascule_a_toujours_lieu_sans_feuille_muette(
    tmp_path, monkeypatch, capsys,
) -> None:
    """Temoin positif du precedent, sur le **meme** chemin de detection.

    Sans lui, le test ci-dessus serait vrai d'un scan qui aurait cesse de basculer pour
    n'importe quelle raison -- une fabrique de detection cassee, par exemple.
    """
    project_dir = tmp_path / "projet"
    dossier = _dossier_de_scan(tmp_path)
    monkeypatch.setattr(scan_detection, "detect_pages",
                        _moitie_amont(_detection_avec_muettes(
                            _pile_de_calibration_seule(), 0)))
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction", lambda *a, **k: _correction_ajustee())

    assert cli.main(["scan", "--project", str(project_dir), "--scan", str(dossier),
                     "--dpi", "600"]) == 0
    assert calibration_profile.profile_exists(
        project_dir, _chaine_derivee(dossier, tmp_path))


# ---------------------------------------------------------------------------
# Correctif de revue (lot B, couche 1, C5): le repli d'identite garde le libelle
# ---------------------------------------------------------------------------


def test_le_repli_d_identite_de_page_distingue_deux_chaines(tmp_path) -> None:
    """Deux pages de calibration de deux chaines rendent deux identifiants **differents**.

    Ce nom n'est pas cosmetique: il devient `source_page_id` au document de profil, puis
    `correction_source_page_id` au manifest, puis la valeur recopiee dans l'entree
    autoportante du registre. Deux chaines qui rendraient la meme chaine de caracteres
    feraient perdre a l'entree la seule question qu'elle existe pour trancher --
    « qu'est-ce qui a corrige ce lot ».

    Le mutant tue: le repli reduit a la constante `"chaine-inconnue"`. Il survivait a
    tous les lots parce qu'aucune fabrique ne portait **deux** libelles distinguables
    (regle des fabriques, point 1).

    La cible n'est **pas en premiere position**: c'est la seconde page qui porte le
    second libelle, et c'est elle dont le nom est confronte au litteral.
    """
    pile = _pile_de_calibration_seule()
    noms = [cli._page_identifier(payload) for payload in pile]
    assert noms[0] != noms[1], noms
    # Et chaque nom porte reellement le libelle de **sa** chaine, ecrit en litteral:
    # deux noms distincts pourraient l'etre par le seul `page_index`.
    assert "canon" in noms[0] and "lide" in noms[0], noms
    assert "epson" in noms[1] and "perfection" in noms[1], noms
    assert "canon" not in noms[1], noms


def test_le_repli_d_identite_de_page_nomme_l_inconnu_sans_libelle(tmp_path) -> None:
    """Frontiere: sans libelle, le repli reste lisible et ne leve pas.

    Une page de calibration ne porte pas de `lot_id`; si son libelle manquait aussi,
    un acces nu aurait rendu ce chemin fatal. C'est le pendant negatif du test
    precedent: sans lui, la seule facon de le passer serait d'exiger un libelle,
    c'est-a-dire de rouvrir le `KeyError` que ce repli a ferme.
    """
    page = dict(_pile_de_calibration_seule()[1])
    page.pop(payload_io.SCAN_CHAIN_LABEL_FIELD)
    assert cli._page_identifier(page) == "chaine-inconnue-p1"


def test_l_identifiant_de_page_d_une_planche_reste_celui_du_lot(tmp_path) -> None:
    """Temoin positif: le repli ne mord pas sur une planche d'images.

    Le nom d'une planche reste `<lot_id>-p<index>`, et la cible est prise **hors de la
    premiere position** parmi trois planches de deux lots distinguables.
    """
    planches = _pile_de_planches_seules()
    noms = [cli._page_identifier(payload) for payload in planches]
    assert noms == [f"{LOTS[0]}-p0", f"{LOTS[0]}-p1", f"{LOTS[1]}-p2"], noms
