# -*- coding: utf-8 -*-
"""Story 11.6, lot F -- `E3-8`, le resultat de l'ecriture du Scan (AC 7).

**Le nom du fichier est verifie globalement unique** : aucun des trois dossiers
de tests n'a d'`__init__.py`, donc deux fichiers homonymes rendent le meme nom
de module et pytest interrompt la collecte de la suite ENTIERE -- une panne
invisible quand on ne lance qu'un sous-dossier. `test_atelier_scan_resultat.py`
n'existe nulle part ailleurs dans `tests/` au moment ou ce banc est ecrit, et
`test_frontiere_gui_tui.py::test_aucun_nom_de_FICHIER_de_test_n_est_en_double`
le mesure en continu.

Cinq choses y sont mesurees, une par tache du lot :

* **F1** la ligne de raccourcis **contextuelle** -- journal present et absent,
  et `Tab` qui fait ce que la ligne annonce dans le premier regime et rien dans
  le second (finding `I8`, quarante fois paye) ;
* **F2** la calibration **telle qu'elle a ete tranchee** -- jamais ce qui avait
  ete demande au depart --, le manifeste et la duree, avec l'omission plutot
  que le `0` quand une mesure manque ;
* **F3** la degradation **lue du coeur**, mesuree en **egalite d'ensembles**
  avec `scan_write.MOTIFS_QUI_DEGRADENT_LE_CODE`, doublee d'une frontiere qui
  refuse qu'un motif soit recopie ici ;
* **F4** les suites, ou chacune mene, et le retour au **menu des ateliers du
  projet ouvert** (`EPIC11-ARB-13`) ;
* **F5** la fabrique a **trois** lots, le degrade **au milieu**.

**Regle des fabriques, appliquee sur la liste que le code PARCOURT** et non sur
celle que la fabrique ecrit :

* :func:`panneau_du_resultat` et :func:`lignes_de_calibration` **bouclent** sur
  `rapport.ecrits` : le rapport porte **trois** lots ecrits, distinguables par
  leur nom, par leur compte de frames et par le poids qu'ils posent sur le
  disque, et celui qui est **degrade** est au rang 1 sur 3. Ni le premier -- ce
  qui masquerait un `find` fautif --, ni le dernier -- ce qui masquerait une
  terminaison de boucle fautive (`CLAUDE.md`, points 2 et 2 bis) ;
* :func:`dossier_a_ouvrir` boucle sur la meme liste, et les trois dossiers sont
  distincts : un parent commun calcule sur un seul lot ne passerait pas ;
* la pile de paliers de `remonter_a_l_ouverture_de_l_atelier` est parcourue par
  depilement : elle porte **quatre** stations d'atelier, et celle qu'on doit
  atteindre est la **premiere** des quatre, ce qui distingue « remonter jusqu'au
  rang de l'atelier » de « remonter jusqu'au premier palier non transitoire »
  -- les deux regles rendent le meme resultat sur l'atelier Extraction, qui n'a
  qu'une station, et des resultats differents ici.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
from textual.widgets import Static

_TESTS_UNIT = Path(__file__).resolve().parents[1]
if str(_TESTS_UNIT) not in sys.path:
    sys.path.insert(0, str(_TESTS_UNIT))

from mixed_media_utility import scan_output_frames, scan_write  # noqa: E402
from mixed_media_utility.io import scan_manifest  # noqa: E402
from mixed_media_utility.io.extraction_manifest import (  # noqa: E402
    MANIFEST_FILENAME,
)
from mixed_media_utility.tui import jetons  # noqa: E402
from mixed_media_utility.tui import atelier_scan_ecriture as ecriture  # noqa: E402
from mixed_media_utility.tui import atelier_scan_resultat as atelier  # noqa: E402
from mixed_media_utility.tui import execution  # noqa: E402
from mixed_media_utility.tui.avancement import Journal  # noqa: E402
from mixed_media_utility.tui.coque import (  # noqa: E402
    Contexte,
    CoqueTui,
    EcranPasEncore,
    PalierTemoin,
)

from outils_frontiere import chaines_de_code, identifiants  # noqa: E402


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

#: **Le rang de la cible dans la liste que le code parcourt.** Ni le premier
#: (ce qui masquerait un `find` fautif) ni le dernier (ce qui masquerait une
#: terminaison de boucle fautive) -- `CLAUDE.md`, points 2 et 2 bis.
RANG_DE_LA_CIBLE = 1

#: **Trois lots distinguables** : par leur nom, par leur compte de frames et
#: par le nombre d'octets qu'ils posent sur le disque. Un remplissage uniforme
#: rendrait toute permutation invisible -- c'est le mutant `M33` de la 5.6.
LOTS = (
    ("lot_a_12p5", 40, 3),
    ("lot_b_25", 62, 11),
    ("lot_c_50", 84, 7),
)

#: Le lot **du milieu** : c'est lui qui est degrade, et lui dont la calibration
#: diverge quand le banc mesure une divergence.
LOT_CIBLE = LOTS[RANG_DE_LA_CIBLE][0]

#: La chaine du profil designe. Le nom vient de la maquette (`E3-8`, l. 9).
CHAINE = "hp-envy-4520-tiff-600"

#: Une seconde chaine, pour que la divergence de calibration se voie.
CHAINE_AUTRE = "epson-v600-tiff-1200"

#: La profondeur de sortie que la maquette porte (l. 6).
PROFONDEUR = 16

#: Les valeurs que `E3-3` et `E3-8` DESSINENT, nommees ici une seule fois.
#: Elles etaient tapees en clair sur sept sites, donc recopiees d'un dessin
#: que ce banc citait sans jamais l'ouvrir. Chacune est confrontee a sa source
#: en fin de fichier, le dessin etant relu sur disque a chaque tour.
RACCOURCI_DU_JOURNAL = "Tab journal"
LIGNE_D_ETAT_DESSINEE = "186 frames écrites sur 186 attendues"
DUREE_DESSINEE = "6 min 12"
SUITE_DU_MASTER = "Encoder un master depuis ces lots"

#: Un code de l'inventaire du coeur qui **ne degrade pas** : il sert de volet
#: symetrique a chaque mesure de degradation -- sans lui, un module qui
#: declarerait « tout degrade » passerait.
CODE_QUI_NE_DEGRADE_PAS = scan_manifest.SCAN_STATE_CONSERVED


def coque(paliers: int = 2, **kwargs) -> CoqueTui:
    """Une coque a `paliers` paliers temoins, nommes par leur rang.

    Deux au minimum -- l'ecran projet et le menu des ateliers --, parce que le
    retour au menu des ateliers (`EPIC11-ARB-13`) ne se distingue d'un retour a
    la racine que si la racine existe a cote. Les suivants montent l'atelier
    Scan, qui empile **quatre** stations la ou l'Extraction n'en a qu'une.
    """
    noms = ["Projet", "Ateliers", "E3-0 menu", "E3-1 depot", "E3-3 rapport",
            "E3-5 calibration"]
    return CoqueTui(
        paliers=[PalierTemoin(nom, "⏎ entrer   Q quitter")
                 for nom in noms[:paliers]],
        contexte=Contexte("projet_demo"), **kwargs)


def rapport_de_sortie(lot_id: str, *, ecrites: int, dossier: str,
                      profondeur: int | None = PROFONDEUR,
                      avertissements: tuple[str, ...] = ()
                      ) -> scan_output_frames.LotOutputReport:
    """Un **vrai** `LotOutputReport`, pas un double a attributs libres.

    Le construire pour de bon est ce qui garantit que la projection de la TUI
    lit des champs qui existent : un double a attributs libres rendrait vert un
    accesseur mal nomme -- et c'est precisement sur `output_bit_depth` et
    `output_dir` que cet ecran se sert.

    **`output_dir` est RELATIF au projet**, comme le coeur le rend
    (`scan_output_frames._project_relative_posix`). C'est ce qui rend la
    resolution de :func:`atelier.chemin_du_lot` mesurable plutot que
    theorique.
    """
    return scan_output_frames.LotOutputReport(
        lot_id=lot_id, rush_id="rush-001", fps_target=25.0,
        project_id="projet_demo", template_id="t", gamut_map_id="g",
        target_colorspace="c", patch_preset_id="p",
        color_calibration_status="applied", output_dir=dossier,
        page_count=1, expected_frame_count=ecrites, written_frame_count=ecrites,
        synthetic_frame_count=0, observed_frame_count=ecrites, complete=True,
        output_bit_depth=profondeur, warnings=avertissements)


def persistance(lot_id: str, constats: tuple[str, ...] = ()
                ) -> scan_manifest.PersistedScan:
    """Un **vrai** `PersistedScan` : c'est lui qui porte `findings`."""
    return scan_manifest.PersistedScan(
        manifest_path=Path(MANIFEST_FILENAME), lot_id=lot_id, manifest={},
        state_written="reconstruction", reconstructed_frame_count=0,
        synthetic_frame_count=0, expected_frame_count=None, lot_complete=True,
        findings=constats)


def correction(chaine: str | None):
    """La `LotCorrection` du coeur, ou `None`.

    Import local : `color_calibration` est lourd et n'est demande que par les
    tests de calibration de ce banc.
    """
    from mixed_media_utility import color_calibration
    return color_calibration.LotCorrection(
        source_page_id="page-002", template_id="t", chain_id=chaine)


def lot_ecrit(nom: str, frames: int, dossier: str, *,
              avertissements: tuple[str, ...] = (),
              constats: tuple[str, ...] = (),
              correction_appliquee: bool = True,
              profil_de_chaine_utilise: bool = True,
              chaine: str | None = CHAINE,
              profondeur: int | None = PROFONDEUR) -> ecriture.LotEcrit:
    """Un `LotEcrit` du lot E, porte par un **vrai** `EcritureDuLot`."""
    return ecriture.LotEcrit(
        lot_id=nom, frames=frames, dossier=Path(dossier),
        correction_appliquee=correction_appliquee,
        profil_de_chaine_utilise=profil_de_chaine_utilise,
        ecriture=scan_write.EcritureDuLot(
            persisted=persistance(nom, constats),
            output=rapport_de_sortie(nom, ecrites=frames, dossier=dossier,
                                     profondeur=profondeur,
                                     avertissements=avertissements),
            lot_correction=correction(chaine),
            correction_appliquee=correction_appliquee,
            profil_de_chaine_utilise=profil_de_chaine_utilise))


def rapport_de_trois_lots(tmp_path: Path, *,
                          degrade_au_milieu: bool = True,
                          calibrations_divergentes: bool = False,
                          refus: tuple = ()) -> ecriture.RapportDEcriture:
    """Trois lots ecrits, **le degrade au milieu**, chacun peuple differemment.

    Les dossiers de sortie sont **relatifs au projet**, comme le coeur les
    rend, et chacun recoit un nombre d'octets **different** : deux poids egaux
    laisseraient passer un comptage qui ne lirait que le premier dossier.
    """
    projet = tmp_path / "projet_demo"
    lots = []
    for rang, (nom, frames, poids) in enumerate(LOTS):
        relatif = f"output-frames/{nom}"
        (projet / relatif).mkdir(parents=True, exist_ok=True)
        (projet / relatif / "f000001.tiff").write_bytes(b"x" * poids)
        cible = rang == RANG_DE_LA_CIBLE
        lots.append(lot_ecrit(
            nom, frames, relatif,
            avertissements=((scan_manifest.SCAN_SYNTHETIC_FRAMES_PRESENT,)
                            if (cible and degrade_au_milieu) else ()),
            constats=(CODE_QUI_NE_DEGRADE_PAS,),
            chaine=(CHAINE_AUTRE if (cible and calibrations_divergentes)
                    else CHAINE)))
    return ecriture.RapportDEcriture(
        ecrits=tuple(lots), refus=tuple(refus),
        manifeste=projet / MANIFEST_FILENAME)


def texte_de_l_etat(ecran) -> str:
    """La ligne d'etat **telle qu'elle est affichee**, sans balisage."""
    return jetons.texte_affiche(str(ecran.query_one("#etat", Static).content))


def valeurs_du_panneau(panneau) -> dict[str, str]:
    """`libelle -> chiffre` des lignes du panneau, sans passer par le rendu."""
    return {ligne.libelle: ligne.chiffre for ligne in panneau.lignes}


# ===========================================================================
# F1 -- la ligne de raccourcis CONTEXTUELLE, journal present et absent
# ===========================================================================

def test_avec_un_journal_la_ligne_ANNONCE_Tab_et_Tab_le_deplie(banc, tmp_path):
    """AC 7.1, premier regime : la touche est annoncee **et** elle fait ce
    qu'elle dit.

    Les deux moities comptent : le finding `I8` etait exactement l'ecart entre
    les deux -- `Tab journal` promis par la maquette, `on_key` qui ne traitait
    pas `tab`, et le journal d'une passe terminee relisible de nulle part.
    """
    rapport = rapport_de_trois_lots(tmp_path)
    journal = Journal()
    journal.inscrire("recadrage de la page 2")

    async def scenario(pilote):
        ecran = atelier.ouvrir_le_resultat(
            pilote.app, rapport, journal=journal, duree=372.0,
            attendues=rapport.frames, sur_suite=lambda _s: None)
        await pilote.pause()
        avant = list(ecran.lignes())
        await pilote.press("tab")
        await pilote.pause()
        return ecran.raccourcis, avant, list(ecran.lignes())

    raccourcis, avant, apres = banc(coque(), scenario)
    assert raccourcis == execution.RACCOURCIS_RESULTAT_AVEC_JOURNAL
    assert RACCOURCI_DU_JOURNAL in raccourcis
    assert not any("recadrage de la page 2" in ligne for ligne in avant), (
        "le journal n'est jamais deplie au montage : le compte rendu chiffre "
        "est ce qu'on vient lire")
    assert any("recadrage de la page 2" in ligne for ligne in apres), (
        "`Tab` doit deplier le journal de l'execution qui vient de finir")


def test_sans_journal_la_ligne_NE_PROMET_RIEN_et_Tab_ne_fait_rien(banc,
                                                                  tmp_path):
    """AC 7.1, second regime -- **le volet symetrique du precedent**.

    « Une touche annoncee qui ne fait rien se lit comme une panne » : la ligne
    ne l'annonce donc pas, et l'ecran ne la consomme pas. Les deux lignes
    doivent en outre **differer** -- une ligne unique passerait les deux
    assertions ci-dessus sans etre contextuelle du tout.
    """
    rapport = rapport_de_trois_lots(tmp_path)

    async def scenario(pilote):
        ecran = atelier.ouvrir_le_resultat(
            pilote.app, rapport, journal=None, duree=None,
            attendues=None, sur_suite=lambda _s: None)
        await pilote.pause()
        return ecran.raccourcis, ecran.basculer_le_journal(), ecran.lignes()

    raccourcis, bascule, lignes = banc(coque(), scenario)
    assert raccourcis == execution.RACCOURCIS_RESULTAT
    assert "journal" not in raccourcis
    assert bascule is False, (
        "sans journal, `Tab` doit rendre faux plutot que basculer a vide")
    assert execution.RACCOURCIS_RESULTAT != (
        execution.RACCOURCIS_RESULTAT_AVEC_JOURNAL), (
        "les deux lignes doivent differer, sans quoi rien n'est contextuel")
    assert lignes, "l'ecran rend son compte rendu meme sans journal"


def test_la_ligne_d_etat_SURVIT_au_redessin(banc, tmp_path):
    """`poser_etat` seul se fait effacer par le dessin suivant.

    C'est l'ajout `EcranCompletionQr.annoncer()` du lot E de la 11.5 : une
    ligne d'etat mesuree **avant** un redessin rend un test vert et creux. Elle
    est donc relue apres un `rafraichir()` complet.
    """
    rapport = rapport_de_trois_lots(tmp_path)

    async def scenario(pilote):
        ecran = atelier.ouvrir_le_resultat(
            pilote.app, rapport, journal=None, duree=None,
            attendues=rapport.frames, sur_suite=lambda _s: None)
        await pilote.pause()
        avant = texte_de_l_etat(ecran)
        ecran.rafraichir()
        await pilote.pause()
        return avant, texte_de_l_etat(ecran)

    avant, apres = banc(coque(), scenario)
    assert LIGNE_D_ETAT_DESSINEE in avant
    assert apres == avant, "la ligne d'etat doit survivre au redessin"


# ===========================================================================
# F2 -- la calibration TRANCHEE, le manifeste, la duree
# ===========================================================================

def test_la_calibration_affichee_est_celle_qui_a_ete_TRANCHEE(tmp_path):
    """AC 7.2 : « jamais ce qui avait ete demande au depart ».

    Le lot porte un profil de chaine **nomme** dans son `lot_correction` -- ce
    qui a ete demande -- et une decision d'application **negative** -- ce qui a
    ete tranche. L'ecran doit dire la seconde. Afficher la chaine ici ferait
    lire « ces TIFF sont calibres » sur des TIFF qui ne le sont pas, et c'est
    la question meme que cette ligne existe pour trancher trois semaines plus
    tard.
    """
    lot = lot_ecrit("lot_b_25", 62, "output-frames/lot_b_25",
                    correction_appliquee=False, profil_de_chaine_utilise=False,
                    chaine=CHAINE)
    valeur = atelier.calibration_du_lot(lot)
    assert valeur == atelier.CALIBRATION_AUCUNE
    assert CHAINE not in valeur


def test_les_TROIS_regimes_de_calibration_ne_se_confondent_pas():
    """Trois faits distincts, trois textes distincts -- en **egalite**.

    Une assertion positive par regime laisserait passer deux regimes rendus
    identiques : c'est la mesure de l'unicite, pas seulement de la presence.
    """
    aucune = atelier.calibration_du_lot(lot_ecrit(
        "l", 1, "d", correction_appliquee=False,
        profil_de_chaine_utilise=False))
    propre = atelier.calibration_du_lot(lot_ecrit(
        "l", 1, "d", profil_de_chaine_utilise=False))
    chaine = atelier.calibration_du_lot(lot_ecrit("l", 1, "d"))
    assert chaine == CHAINE, "le `chain_id` du coeur, verbatim"
    assert propre == atelier.CALIBRATION_PAGE_DU_LOT
    assert aucune == atelier.CALIBRATION_AUCUNE
    assert len({aucune, propre, chaine}) == 3


def test_un_profil_de_chaine_SANS_chaine_nommee_ne_rend_pas_une_ligne_vide():
    """Le repli, et il **dit ce qu'on sait** plutot que rien.

    Une chaine vide dans un cartouche se lit comme un champ casse ; « profil
    designe du projet » se lit comme un fait moins precis.
    """
    lot = lot_ecrit("l", 1, "d", chaine=None)
    assert atelier.calibration_du_lot(lot) == atelier.CALIBRATION_PROFIL_DESIGNE


def test_le_manifeste_et_la_duree_sont_DITS(tmp_path):
    """AC 7.2 : le manifest mis a jour et la duree, aux libelles de la maquette."""
    rapport = rapport_de_trois_lots(tmp_path)
    valeurs = valeurs_du_panneau(atelier.panneau_du_resultat(rapport,
                                                             duree=372.0))
    assert valeurs[atelier.LIBELLE_MANIFESTE] == f"projet_demo/{MANIFEST_FILENAME}"
    assert valeurs[atelier.LIBELLE_DUREE] == DUREE_DESSINEE
    assert valeurs[atelier.LIBELLE_CALIBRATION] == CHAINE


def test_une_duree_INCONNUE_est_omise_jamais_rendue_a_zero(tmp_path):
    """`DESIGN.md` section 3 : ni `0:00`, ni `--:--`, ni chaine vide.

    Le volet symetrique est dans le test precedent : la meme fabrique **avec**
    une duree rend bien la ligne. Sans lui, un panneau qui n'ecrirait jamais de
    duree passerait celui-ci.
    """
    rapport = rapport_de_trois_lots(tmp_path)
    valeurs = valeurs_du_panneau(atelier.panneau_du_resultat(rapport,
                                                             duree=None))
    assert atelier.LIBELLE_DUREE not in valeurs
    assert not any(chiffre in ("0", "--", "0:00", "--:--")
                   for chiffre in valeurs.values())


def test_le_chronometre_mesure_l_ecoule_et_non_l_horloge_murale():
    """La duree vient d'un chronometre monte **avant** l'appel au coeur."""
    tics = iter([100.0, 106.5, 472.0])
    ecoule = atelier.chronometre(horloge=lambda: next(tics))
    assert ecoule() == pytest.approx(6.5)
    assert ecoule() == pytest.approx(372.0)
    assert atelier.duree_lisible(372.0) == DUREE_DESSINEE
    assert atelier.duree_lisible(None) is None
    # **L'arrondi est celui du coeur de la grammaire, vers le HAUT** : une
    # passe de 372,25 s a bien dure plus de 6 min 12, et
    # `avancement.duree_lisible` le dit. Le mesurer ici nomme la propriete au
    # lieu de la decouvrir un jour sur un ecart d'une seconde.
    assert atelier.duree_lisible(372.25) == "6 min 13"


def test_la_calibration_diverge_PAR_LOT_quand_les_lots_divergent(tmp_path):
    """Deux calibrations ne se replient pas sur une seule ligne.

    C'est le mutant `M25` de la story 5.7, transpose : « les cardinaux du scan
    etaient ecrits sur le mauvais lot ». Le test mesure **quel** lot porte
    quelle calibration, et la cible est **au milieu** de la liste que
    `lignes_de_calibration` parcourt.
    """
    rapport = rapport_de_trois_lots(tmp_path, calibrations_divergentes=True)
    lignes = atelier.lignes_de_calibration(rapport)
    assert len(lignes) == len(LOTS), (
        "une ligne par lot des que deux calibrations different")
    par_lot = {ligne.libelle: ligne.chiffre for ligne in lignes}
    assert par_lot[f"{atelier.LIBELLE_CALIBRATION} · {LOT_CIBLE}"] == CHAINE_AUTRE
    autres = [nom for nom, _f, _p in LOTS if nom != LOT_CIBLE]
    assert {par_lot[f"{atelier.LIBELLE_CALIBRATION} · {nom}"]
            for nom in autres} == {CHAINE}


def test_une_calibration_UNIQUE_ne_se_repete_pas_sur_trois_lignes(tmp_path):
    """Le volet symetrique : trois lots d'accord rendent **une** ligne."""
    rapport = rapport_de_trois_lots(tmp_path)
    lignes = atelier.lignes_de_calibration(rapport)
    assert [ligne.libelle for ligne in lignes] == [atelier.LIBELLE_CALIBRATION]


# ===========================================================================
# F3 -- la degradation, LUE du coeur et mesuree en egalite d'ensembles
# ===========================================================================

def test_l_ensemble_qui_degrade_est_EXACTEMENT_celui_du_coeur():
    """AC 7.3 : egalite d'ensembles avec `MOTIFS_QUI_DEGRADENT_LE_CODE`.

    L'inventaire du lot porte **tous** les motifs qui degradent **et** un code
    qui ne degrade pas. Une assertion positive (« ce motif est retenu »)
    laisserait passer un module qui retiendrait aussi le second : ce qui est
    mesure ici est l'exception ET son unicite.
    """
    degradants = tuple(sorted(scan_write.MOTIFS_QUI_DEGRADENT_LE_CODE))
    assert degradants, "l'ensemble du coeur doit etre non vide"
    lot = lot_ecrit("l", 1, "d", avertissements=degradants,
                    constats=(CODE_QUI_NE_DEGRADE_PAS,))
    retenus = atelier.motifs_qui_degradent(lot)
    assert set(retenus) == set(scan_write.MOTIFS_QUI_DEGRADENT_LE_CODE)
    assert CODE_QUI_NE_DEGRADE_PAS not in retenus


def test_un_lot_SANS_motif_degradant_n_en_rend_aucun():
    """Le volet symetrique : un module qui rendrait tout passerait le premier."""
    lot = lot_ecrit("l", 1, "d", constats=(CODE_QUI_NE_DEGRADE_PAS,))
    assert atelier.motifs_qui_degradent(lot) == ()


def test_aucun_motif_du_coeur_n_est_RECOPIE_dans_le_module():
    """« Ensemble ferme **lu** du coeur, jamais recopie » (AC 7.3).

    Mesure sur les chaines litterales du **code**, docstrings exclus : un
    docstring qui cite `SCAN_LOT_INCOMPLETE` explique, il ne decide pas. Le
    volet symetrique verifie que le module reference bien les deux fonctions du
    coeur -- sans lui, un module qui ne mesurerait aucune degradation du tout
    passerait cette frontiere.
    """
    module = (Path(__file__).resolve().parents[3] / "src"
              / "mixed_media_utility" / "tui" / "atelier_scan_resultat.py")
    litterales = set(chaines_de_code(module))
    recopies = litterales & set(scan_write.MOTIFS_QUI_DEGRADENT_LE_CODE)
    assert recopies == set(), (
        f"motifs du coeur recopies dans la TUI : {sorted(recopies)}")
    noms = identifiants(module)
    assert "motifs_de_degradation" in noms
    assert "inventaire_de_l_ecriture" in noms


def test_le_glyphe_du_lot_DEGRADE_passe_a_substitute_et_lui_seul(tmp_path):
    """AC 7.3, sur la liste que le code parcourt, la cible **au milieu**.

    Trois lots, le degrade au rang 1 : un `find` fautif marquerait le premier,
    une boucle qui ne s'arrete pas marquerait le dernier. Le test mesure la
    suite **complete** des glyphes, pas la seule presence d'un `▲`.
    """
    rapport = rapport_de_trois_lots(tmp_path)
    panneau = atelier.panneau_du_resultat(rapport, duree=None)
    table = jetons.glyphes(False)
    glyphes = [ligne.libelle.split(" ")[0] for ligne in panneau.lignes
               if ligne.libelle.split(" ")[-1] in {nom for nom, _f, _p in LOTS}]
    attendu = [table["substitute"] if rang == RANG_DE_LA_CIBLE
               else table["complete"] for rang in range(len(LOTS))]
    assert glyphes == attendu


def test_le_motif_est_DIT_sous_la_ligne_du_lot_degrade(tmp_path):
    """« Le motif est dit », avec les codes du coeur et sous le bon lot."""
    rapport = rapport_de_trois_lots(tmp_path)
    lignes = atelier.panneau_du_resultat(rapport, duree=None).lignes
    libelles = [ligne.libelle for ligne in lignes]
    rang_du_lot = libelles.index(
        next(l for l in libelles if l.endswith(LOT_CIBLE)))
    motif = lignes[rang_du_lot + 1]
    assert motif.libelle.strip() == atelier.LIBELLE_MOTIF
    assert motif.chiffre == scan_manifest.SCAN_SYNTHETIC_FRAMES_PRESENT
    assert sum(1 for l in libelles if l.strip() == atelier.LIBELLE_MOTIF) == 1, (
        "un seul lot est degrade : une seule ligne de motif")


def test_la_ligne_d_etat_porte_le_glyphe_de_ce_qui_s_est_PASSE(tmp_path):
    """Le second canal du `DESIGN.md` section 6 tenu jusqu'en bas de l'ecran.

    Trois etats mesures **ensemble** : plein, degrade, refuse. Les comparer
    deux a deux est ce qui interdit qu'un seul glyphe serve aux trois.
    """
    table = jetons.glyphes(False)
    plein = atelier.ligne_d_etat_du_resultat(
        rapport_de_trois_lots(tmp_path / "a", degrade_au_milieu=False), 186)
    degrade = atelier.ligne_d_etat_du_resultat(
        rapport_de_trois_lots(tmp_path / "b"), 186)
    refuse = atelier.ligne_d_etat_du_resultat(
        rapport_de_trois_lots(
            tmp_path / "c", degrade_au_milieu=False,
            refus=(ecriture.RefusDEcriture(
                code="RefusDuDocumentDeDetection", message="m",
                code_retour=1),)), 186)
    assert plein.startswith(table["complete"])
    assert degrade.startswith(table["substitute"])
    assert refuse.startswith(table["absent"])
    assert atelier.AUCUN_REFUS in plein
    assert "RefusDuDocumentDeDetection" in refuse
    assert len({plein[0], degrade[0], refuse[0]}) == 3


def test_des_frames_attendues_INCONNUES_ne_se_recopient_pas_sur_les_ecrites(
        tmp_path):
    """Sans compte attendu, le segment DISPARAIT plutot que de mentir.

    Recopier les ecrites a droite du « sur » ferait lire une passe complete a
    coup sur, y compris sur une passe qui a perdu la moitie de ses frames.
    """
    rapport = rapport_de_trois_lots(tmp_path)
    sans = atelier.ligne_d_etat_du_resultat(rapport, None)
    avec = atelier.ligne_d_etat_du_resultat(rapport, 200)
    assert "attendues" not in sans
    assert "sur 200 attendues" in avec


def test_la_ligne_d_etat_se_replie_ENTIEREMENT_en_ascii(tmp_path):
    """Le repli porte sur le libelle autant que sur le glyphe."""
    rapport = rapport_de_trois_lots(tmp_path)
    ligne = atelier.ligne_d_etat_du_resultat(rapport, 186, ascii_seul=True)
    assert ligne.isascii(), f"reste de l'UTF-8 en repli : {ligne!r}"


# ===========================================================================
# F4 -- les suites, et ou chacune mene
# ===========================================================================

def test_les_quatre_suites_sont_celles_de_la_maquette(banc, tmp_path):
    """AC 7.4, en **egalite** : ni une de plus, ni une de moins, dans l'ordre.

    « Retour aux ateliers » n'est pas ecrit par ce module : `EcranResultat`
    l'ajoute en dernier de lui-meme (`EPIC11-ARB-13`), et l'ecrire ici le
    ferait voir deux fois.
    """
    rapport = rapport_de_trois_lots(tmp_path)
    assert atelier.suites_du_resultat(rapport) == [
        atelier.SUITE_DOSSIER, atelier.SUITE_EXPORTS,
        atelier.SUITE_AUTRES_SCANS]

    async def scenario(pilote):
        ecran = atelier.conclure(pilote.app, rapport, journal=None,
                                 duree=None, attendues=None)
        await pilote.pause()
        return list(ecran.suites)

    assert banc(coque(), scenario) == [
        atelier.SUITE_DOSSIER, atelier.SUITE_EXPORTS,
        atelier.SUITE_AUTRES_SCANS, execution.EcranResultat.RETOUR]


def test_sans_lot_ecrit_les_deux_premieres_suites_DISPARAISSENT():
    """Proposer « ouvrir le dossier des lots » sur zero lot designerait un
    dossier qui n'existe pas, et l'atelier Exports une source vide."""
    vide = ecriture.RapportDEcriture()
    assert atelier.suites_du_resultat(vide) == [atelier.SUITE_AUTRES_SCANS]
    assert atelier.dossier_a_ouvrir(vide) is None


def test_le_chemin_d_un_lot_est_RESOLU_depuis_le_projet(tmp_path):
    """Le coeur rend un chemin **relatif** ; le prendre pour absolu est muet.

    `scan_output_frames` ecrit `output_dir` par `_project_relative_posix`, et
    `LotEcrit.dossier` le recopie tel quel. Sans resolution, le poids mesure
    serait zero et le dossier remis au bureau n'existerait pas -- deux pannes
    silencieuses sur les deux seules choses que cet ecran promet d'un lot.
    Le volet symetrique : un chemin **deja absolu** traverse tel quel.
    """
    rapport = rapport_de_trois_lots(tmp_path)
    projet = tmp_path / "projet_demo"
    for rang, (nom, _frames, poids) in enumerate(LOTS):
        chemin = atelier.chemin_du_lot(rapport, rapport.ecrits[rang])
        assert chemin == projet / "output-frames" / nom
        assert chemin.is_absolute()
        assert atelier.octets_du_dossier(chemin) == poids, (
            "chaque lot doit porter SON poids, jamais celui d'un voisin")
    absolu = ecriture.LotEcrit(
        lot_id="x", frames=1, dossier=tmp_path / "ailleurs",
        correction_appliquee=False, profil_de_chaine_utilise=False)
    assert atelier.chemin_du_lot(rapport, absolu) == tmp_path / "ailleurs"


def test_dossier_a_ouvrir_est_le_parent_COMMUN_des_lots_ecrits(tmp_path):
    """Ouvrir un lot parmi trois cacherait les deux autres derriere un libelle
    qui les annonce au pluriel."""
    rapport = rapport_de_trois_lots(tmp_path)
    assert atelier.dossier_a_ouvrir(rapport) == (
        tmp_path / "projet_demo" / "output-frames")


def test_ouvrir_le_dossier_passe_par_L_UNIQUE_point_et_ne_quitte_PAS_la_TUI(
        banc, tmp_path, monkeypatch):
    """AC 7.5 : le dossier part a l'unique ouvreur, et l'ecran ne bouge pas.

    Le fait rendu est **pose en ligne d'etat**, et il l'est dans les deux
    regimes : un echec silencieux serait indistinguable de la suite decorative
    que le finding `K3` a payee.
    """
    rapport = rapport_de_trois_lots(tmp_path)
    vus: list = []
    monkeypatch.setattr(atelier, "ouvrir_dans_l_explorateur_du_systeme",
                        lambda dossier: vus.append(dossier) or f"ouvert {dossier}")

    async def scenario(pilote):
        ecran = atelier.conclure(pilote.app, rapport, journal=None,
                                 duree=None, attendues=None)
        await pilote.pause()
        ecran.curseur = ecran.suites.index(atelier.SUITE_DOSSIER)
        ecran.choisir()
        await pilote.pause()
        return pilote.app.screen is ecran, texte_de_l_etat(ecran)

    memes, etat = banc(coque(), scenario)
    assert vus == [tmp_path / "projet_demo" / "output-frames"]
    assert memes, "on reste sur `E3-8` : le compte rendu reste lisible"
    assert "ouvert" in etat


def test_l_ouvreur_reel_rend_une_PHRASE_et_ne_leve_jamais(banc, tmp_path):
    """Le regime nominal d'un conteneur sans bureau, mesure sans double.

    L'ouvreur du produit rend un **fait a afficher, toujours** : le chemin
    ouvert, ou le motif qui a empeche de l'ouvrir. Une trace Python nue au
    moment ou l'ecriture vient de REUSSIR serait pire que la suite muette
    qu'on corrige.
    """
    rapport = rapport_de_trois_lots(tmp_path)

    async def scenario(pilote):
        atelier.conclure(pilote.app, rapport, journal=None, duree=None,
                         attendues=None)
        await pilote.pause()
        return atelier.ouvrir_le_dossier_des_lots(pilote.app, rapport)

    fait = banc(coque(), scenario)
    assert isinstance(fait, str) and fait
    assert str(tmp_path / "projet_demo" / "output-frames") in fait


def test_aucun_SECOND_site_d_appel_systeme_dans_ce_module():
    """AC 7.5, frontiere : l'appel systeme reste **unique** dans `tui/`.

    Mesure a l'AST sur les noms reellement references : un docstring qui parle
    de `subprocess` explique, il ne lance rien -- c'est la lecon du finding
    `I3`. Le volet symetrique verifie que le module reference bien l'ouvreur
    isole : sans lui, un module qui n'ouvrirait **rien** passerait la moitie
    negative.
    """
    module = (Path(__file__).resolve().parents[3] / "src"
              / "mixed_media_utility" / "tui" / "atelier_scan_resultat.py")
    noms = identifiants(module)
    interdits = {"subprocess", "Popen", "system", "startfile", "execv", "spawn",
                 "run"} & noms
    assert interdits == set(), f"lanceur de processus dans la TUI : {interdits}"
    assert "ouvrir_dans_l_explorateur_du_systeme" in noms


def test_Detecter_d_autres_scans_remonte_a_L_OUVERTURE_de_l_atelier(banc,
                                                                    tmp_path):
    """AC 7.4 : la page d'ouverture de l'atelier, pas le choix de calibration.

    L'atelier Scan empile **quatre** stations non transitoires (`E3-0`, `E3-1`,
    `E3-3`, `E3-5`) la ou l'Extraction n'en a qu'une. Un depilement « jusqu'au
    premier palier non transitoire » -- la regle de
    `atelier_extraction_ecriture` -- s'arreterait donc sur `E3-5`, c'est-a-dire
    devant un profil a valider pour un lot deja ecrit. Le test mesure le palier
    **atteint**, pas le nombre de depilements.
    """
    rapport = rapport_de_trois_lots(tmp_path)

    async def scenario(pilote):
        app = pilote.app
        for _ in range(5):
            app.descendre()
            await pilote.pause()
        depart = app.rang
        ecran = atelier.conclure(app, rapport, journal=None, duree=None,
                                 attendues=None)
        await pilote.pause()
        ecran.curseur = ecran.suites.index(atelier.SUITE_AUTRES_SCANS)
        ecran.choisir()
        await pilote.pause()
        return depart, app.rang, app.screen.titre, app.passages_empiles

    depart, rang, titre, passages = banc(coque(paliers=6), scenario)
    assert depart == 5, "la fabrique doit empiler les quatre stations du Scan"
    assert rang == CoqueTui.RANG_DES_ATELIERS + 1
    assert titre == "E3-0 menu"
    assert passages == 0, "aucun passage ne reste sur le chemin du retour"


def test_Retour_aux_ateliers_ramene_au_MENU_jamais_a_l_ecran_projet(banc,
                                                                    tmp_path):
    """`EPIC11-ARB-13`, verbatim : « jamais a l'ecran projet »."""
    rapport = rapport_de_trois_lots(tmp_path)

    async def scenario(pilote):
        app = pilote.app
        for _ in range(5):
            app.descendre()
            await pilote.pause()
        ecran = atelier.conclure(app, rapport, journal=None, duree=None,
                                 attendues=None)
        await pilote.pause()
        ecran.curseur = ecran.suites.index(execution.EcranResultat.RETOUR)
        ecran.choisir()
        await pilote.pause()
        return app.rang, app.screen.titre

    rang, titre = banc(coque(paliers=6), scenario)
    assert rang == CoqueTui.RANG_DES_ATELIERS
    assert titre == "Ateliers"


@pytest.mark.parametrize("suite", [SUITE_DU_MASTER,
                                   "une suite ajoutée demain"])
def test_une_suite_sans_destination_NOMME_l_absence(banc, tmp_path, suite):
    """« Une suite sans destination doit le DIRE, pas ne rien faire » (`K3`).

    Le second cas -- un libelle inconnu -- est le **filet** : sans lui, une
    suite ajoutee demain redeviendrait decorative en silence.
    """
    rapport = rapport_de_trois_lots(tmp_path)

    async def scenario(pilote):
        atelier.suivre(pilote.app, rapport, suite)
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(coque(), scenario)
    assert isinstance(ecran, EcranPasEncore)
    # L'ecran NOMME la suite demandee : « pas encore construit » sans dire quoi
    # se lit comme une panne generique, pas comme une echeance.
    assert ecran.ce_qui_manque == suite
    assert any(suite in ligne for ligne in ecran.lignes())
    assert ecran.quand == CoqueTui.QUAND_ARRIVENT_LES_ATELIERS


def test_le_point_d_appel_du_PRODUIT_passe_le_rappel_des_suites(banc, tmp_path):
    """La garde du finding `K3`, prise par le bout qui a manque.

    `EcranResultat` savait se servir de `sur_suite`, `ouvrir_le_resultat`
    savait le transmettre, et **le point d'appel ne le passait pas** : les
    quatre suites etaient navigables au clavier et decoratives. La mesure
    porte donc sur :func:`atelier.conclure`, le chemin du produit, et sur une
    suite dont la destination **n'est pas** l'ecran « pas encore » -- sans
    quoi le defaut serait indistinguable du repli.
    """
    rapport = rapport_de_trois_lots(tmp_path)

    async def scenario(pilote):
        app = pilote.app
        for _ in range(5):
            app.descendre()
            await pilote.pause()
        ecran = atelier.conclure(app, rapport, journal=None, duree=None,
                                 attendues=None)
        await pilote.pause()
        ecran.curseur = ecran.suites.index(atelier.SUITE_AUTRES_SCANS)
        ecran.choisir()
        await pilote.pause()
        return app.screen

    ecran = banc(coque(paliers=6), scenario)
    assert not isinstance(ecran, EcranPasEncore), (
        "un `sur_suite` non passe replierait TOUTE suite sur « pas encore »")


# ===========================================================================
# F5 -- la fabrique : trois lots, le degrade AU MILIEU
# ===========================================================================

def test_la_fabrique_place_la_cible_AU_MILIEU_de_trois():
    """La regle des fabriques, mesuree sur la fabrique elle-meme.

    Un banc dont la cible glisserait en premiere ou en derniere position
    cesserait de mesurer ce qu'il croit, **sans rougir** : c'est la panne
    instrumentee de la 11.4b, ou une fixture croyait respecter le point 2 bis.
    """
    assert len(LOTS) == 3
    assert 0 < RANG_DE_LA_CIBLE < len(LOTS) - 1
    assert LOTS[RANG_DE_LA_CIBLE][0] == LOT_CIBLE
    assert len({nom for nom, _f, _p in LOTS}) == 3
    assert len({frames for _n, frames, _p in LOTS}) == 3
    assert len({poids for _n, _f, poids in LOTS}) == 3


def test_chaque_lot_porte_SON_compte_SA_profondeur_et_SON_poids(tmp_path):
    """Une permutation ne se voit que si les trois lots different partout.

    Le test confronte les trois lignes **deux a deux** : un rendu qui
    recopierait les cardinaux du premier lot sur les trois passerait toute
    assertion posee sur un seul.
    """
    rapport = rapport_de_trois_lots(tmp_path)
    lignes = {ligne.libelle.split(" ", 1)[1]: ligne.chiffre
              for ligne in atelier.panneau_du_resultat(rapport, duree=None
                                                       ).lignes
              if ligne.libelle.split(" ", 1)[-1] in {n for n, _f, _p in LOTS}}
    assert set(lignes) == {nom for nom, _f, _p in LOTS}
    for nom, frames, poids in LOTS:
        assert lignes[nom] == f"{frames} frames · {PROFONDEUR} bits · {poids} o"
    assert len(set(lignes.values())) == 3


def test_une_profondeur_INCONNUE_traverse_et_la_ligne_ne_l_invente_pas():
    """`None` traverse : le morceau disparait plutot que d'annoncer `0 bits`.

    Le volet symetrique est le test precedent, ou la profondeur est bien dite.
    """
    lot = lot_ecrit("l", 12, "d", profondeur=None)
    assert atelier.profondeur_du_lot(lot) is None
    assert atelier.profondeur_du_lot(lot_ecrit("l", 12, "d")) == "16 bits"


def test_le_bandeau_porte_la_MESURE_de_la_passe(tmp_path):
    """La droite du bandeau de `E3-8` (maquette, l. 2) : ce qui est sorti."""
    rapport = rapport_de_trois_lots(tmp_path)
    assert atelier.objet_du_bandeau(rapport) == "3 lots · 186 frames"
    un_seul = ecriture.RapportDEcriture(ecrits=rapport.ecrits[:1])
    assert atelier.objet_du_bandeau(un_seul) == "1 lot · 40 frames"


def test_le_bandeau_nomme_l_ATELIER_et_pas_le_nom_de_l_ecran(banc, tmp_path):
    """`mmu · projet_demo · Scan` (maquette, l. 2), et non `· Resultat`.

    C'est tout ce que la sous-classe redonne, et le test le mesure comme tel :
    la surface propre a `EcranResultatDuScan` est **exactement** son titre.
    Toute methode ajoutee ici serait une seconde redaction de ce que
    `execution.py` porte deja pour les quatre ateliers.
    """
    rapport = rapport_de_trois_lots(tmp_path)
    # **Mesure sur la SOURCE, pas sur `vars()`** : la metaclasse de `textual`
    # depose une douzaine d'attributs sur toute sous-classe d'ecran, si bien
    # qu'un `vars()` ne distingue pas ce que l'auteur a ecrit de ce que le
    # cadre a ajoute. L'arbre syntaxique, lui, dit exactement ce qui est
    # redonne ici.
    module = (Path(__file__).resolve().parents[3] / "src"
              / "mixed_media_utility" / "tui" / "atelier_scan_resultat.py")
    arbre = ast.parse(module.read_text(encoding="utf-8"))
    classe = next(n for n in ast.walk(arbre)
                  if isinstance(n, ast.ClassDef)
                  and n.name == "EcranResultatDuScan")
    assert [base.id for base in classe.bases] == ["EcranResultat"]
    corps = [n for n in classe.body
             if not (isinstance(n, ast.Expr)
                     and isinstance(n.value, ast.Constant))]
    assert len(corps) == 1 and isinstance(corps[0], ast.Assign)
    assert [c.id for c in corps[0].targets] == ["titre"]
    assert atelier.EcranResultatDuScan.titre == ecriture.PALIER_DE_L_ATELIER
    assert atelier.EcranResultatDuScan.titre != execution.EcranResultat.titre

    async def scenario(pilote):
        ecran = atelier.conclure(pilote.app, rapport, journal=None,
                                 duree=None, attendues=None)
        await pilote.pause()
        return ecran.bandeau()

    bandeau = banc(coque(), scenario)
    assert "Scan" in bandeau
    assert "3 lots · 186 frames" in bandeau


def test_le_panneau_du_resultat_ne_porte_AUCUN_majorant(tmp_path):
    """« Le travail est fait, les chiffres sont mesures » (story 11.1, AC 8.2).

    `EcranResultat` leve a la construction sur un panneau qui en porte un : le
    mesurer ici nomme la propriete au lieu de la laisser a une exception.
    """
    rapport = rapport_de_trois_lots(tmp_path)
    panneau = atelier.panneau_du_resultat(rapport, duree=372.0)
    assert panneau.porte_un_majorant is False


# ===========================================================================
# Les deux maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E3-0`, `E3-1`, `E3-3`,
# `E3-5` et `E3-8` et n'ouvrait aucun dessin : sept de ses valeurs en etaient
# recopiees. La confrontation des CONSTANTES DU MODULE `atelier_scan_resultat`
# est posee ailleurs (`test_confrontation_maquettes_scan_profond.py`, table
# `E3-8`) ; ce qui manquait ici, ce sont les valeurs que le BANC tape
# lui-meme -- la ligne d'etat, la duree, la suite, le raccourci -- et qu'aucune
# constante de module ne porte.
#
# La ligne du lot (`124 frames · 16 bits · 3,6 Go`) n'est pas recopiee : elle
# est ASSEMBLEE par le banc a partir de `LOTS` et de `PROFONDEUR`. Ce sont ses
# deux separateurs (`" frames · "`, `" bits · "`) que la mesure voyait, et ils
# sont dessines. La confrontation porte donc sur la ligne assemblee, pas sur
# ses morceaux : c'est la forme du dessin qu'elle epingle, pas une coincidence
# de sous-chaine.

#: Les maquettes, a leur source.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


def test_les_valeurs_du_RESULTAT_sont_VERBATIM_de_la_maquette_E3_8():
    """Quatre valeurs tapees par le banc, confrontees au dessin lu a sa source.

    Ce n'est pas une ressemblance, c'est une appartenance : le jour ou `E3-8`
    change, ce test rouge NOMME l'ecart (`EPIC11-ARB-144`) plutot que de
    laisser l'ecran et le dessin approuve diverger en silence.
    """
    dessin = dessin_de_la_maquette("E3-8-scan-resultat.txt")
    for attendu in (LIGNE_D_ETAT_DESSINEE, DUREE_DESSINEE, SUITE_DU_MASTER,
                    RACCOURCI_DU_JOURNAL):
        assert attendu in dessin, attendu


def test_la_LIGNE_DE_LOT_assemblee_a_la_FORME_que_le_dessin_montre():
    """`124 frames · 16 bits · 3,6 Go`, assemblee et non recopiee.

    Le banc compose cette ligne a partir de `LOTS` et de `PROFONDEUR` ; le
    dessin en montre deux exemplaires, aux deux premieres lignes du cartouche.
    Confronter la ligne ASSEMBLEE plutot que ses separateurs est ce qui
    distingue une forme d'une coincidence de sous-chaine.
    """
    dessin = dessin_de_la_maquette("E3-8-scan-resultat.txt")
    assert f"124 frames · {PROFONDEUR} bits · 3,6 Go" in dessin
    assert f"62 frames · {PROFONDEUR} bits · 1,8 Go" in dessin


def test_le_raccourci_du_journal_est_dessine_par_les_DEUX_ecrans():
    """`E3-3` et `E3-8` l'annoncent tous les deux, et c'est mesure.

    Le banc l'asserte sur les deux ecrans ; une seule des deux maquettes
    suffirait a rendre la confrontation verte sans dire que les deux le
    portent.
    """
    for nom in ("E3-3-scan-rapport-complet.txt", "E3-8-scan-resultat.txt"):
        assert RACCOURCI_DU_JOURNAL in dessin_de_la_maquette(nom), nom


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : le pli absorbe la mise en page, PAS un ecart.

    Quatre contre-exemples, dont trois a un chiffre ou un mot pres.
    """
    dessin = dessin_de_la_maquette("E3-8-scan-resultat.txt")
    assert "186 frames écrites sur 187 attendues" not in dessin
    assert "6 min 13" not in dessin
    assert "Encoder un master depuis ce lot" + "," not in dessin
    assert f"124 frames · {PROFONDEUR + 1} bits · 3,6 Go" not in dessin
