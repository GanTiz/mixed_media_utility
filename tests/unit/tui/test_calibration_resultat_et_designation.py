# -*- coding: utf-8 -*-
"""`E3-9` : d'ou vient `designated_from`, et ou une passe qui ABOUTIT mene.

Deux retours terrain d'Egan du 2026-09-06, deux defauts sans rapport de cause
mais qui vivent dans la meme fonction et dans son parcours :

> Calibration : sans renseigner de nom le nom de la chaine stocke dans le QR ne
> remplace pas le nom qui est alors celui du pdf (avec .pdf a la fin)
>
> Calibration : pas d'ecran de succes et on revient directement a la page pour
> lancer une calibration. Incoherent avec le reste.

**D1 -- une donnee FAUSSE persistee.** `consigner` passait
`source=formulaire.chemin_du_scan` a `record_designated_profile`, qui en fait
`Path(source).name` et l'ecrit dans `project.json` sous `designated_from`, aux
**deux** cles (`designated_calibration_profiles[]` et le defaut). Le champ veut
dire « le fichier de profil que l'operateur a designe » -- les deux autres
sites du depot y passent un `.json` --, et celui-ci etait le seul a y passer
autre chose. Ce n'est pas cosmetique : `palier_projet.nom_du_profil` met
`designated_from` **en tete** de sa precedence, devant le `chain_id`, et trois
ecrans l'affichent. Mesure sur le scan reel d'Egan : profil affiche
`HP envy Gambetta.pdf`.

**D3 -- un geste qui se termine sans rien dire.** Le court-circuit etait
structurel : `ouvrir_ce_que_le_refus_demande` commence par
`if passe.refus is None: return None`, donc la conclusion d'une passe n'avait
qu'UNE branche de navigation, reservee au refus. Le geste **symetrique** --
produire la mire, `E5-6e` -- a son ecran de resultat depuis la 11.1.

**Regle des drapeaux** (`CLAUDE.md`), et ce banc en fait varier quatre, chacun
dans les deux sens : `devient_le_defaut` (D1), refus / succes (D3),
`recalibration` (les deux regimes de l'AC 8.1), et `ascii_seul` -- « une garde
qui ne fait varier AUCUN de ses drapeaux ne mesure qu'un seul chemin », posee
le 2026-09-06 apres deux bandeaux amputes en `--ascii`.

**Regle des fabriques** : les collections de ce banc sont les **suites** de
l'ecran de resultat et la **pile d'ecrans**. Les suites sont distinguables et
mesurees par ensemble exact ; la cible de navigation est jouee sur chacune des
trois, tete et queue comprises, parce qu'un aiguillage tronque en queue est un
mode de panne que la cible du milieu ne demasque pas.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility import scan_calibrate
from mixed_media_utility.io import (calibration_profile, extraction_manifest,
                                    profile_designation,
                                    project_layout)
from mixed_media_utility.tui import atelier_scan_calibrate as calib
from mixed_media_utility.tui import atelier_scan_parcours as parcours
from mixed_media_utility.tui import execution, jetons
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

#: Le nom du scan designe. **Il porte son extension et sa casse**, comme celui
#: d'Egan : c'est ce qui rend le banc discriminant, un `.stem` pose en
#: rattrapage y serait encore rouge.
NOM_DU_SCAN = "HP envy Gambetta.pdf"

#: L'etiquette que le coeur a retenue, et donc le radical du fichier ecrit.
ETIQUETTE = "hp envy Gambetta"
RADICAL = "hp-envy-gambetta"

CHAINE = "300-pdf-abcdef012345"


# ---------------------------------------------------------------------------
# Les fabriques -- deux profils DISTINGUABLES, jamais un remplissage uniforme
# ---------------------------------------------------------------------------

class _Mesure:
    forme, cardinal, octets, dpi, fichiers = "pdf", 1, 1000, 300.0, 1


class _Source:
    mesure = _Mesure()
    forme, cardinal, dpi, fichiers = "pdf", 1, 300.0, 1
    est_multiple = False

    def __init__(self, chemin):
        self.chemin = chemin


class _Correction:
    """Ce que l'ecran lit d'un `LotCorrection` : deux cardinaux **differents**.

    Differents, et pas un remplissage uniforme : `164 lues · 164 retenues`
    laisserait une inversion des deux champs parfaitement verte.
    """

    read_patch_count = 164
    retained_patch_count = 161


def _document(divergence: float | None = 2.1) -> dict:
    """Un document de profil **complet**, pas un dictionnaire a deux cles.

    `profile_designation.manifest_entry` lit huit champs obligatoires : un
    document maigre leverait `KeyError` et le banc mesurerait sa propre
    fabrique au lieu du chemin de designation.
    """
    document = {
        "schema_version": "1.0",
        "chain_id": CHAINE,
        "correction_form_id": "corr-3x3-v1",
        "source_page_id": "page-de-calibration-1",
        "template_id": "tpl-a4-portrait-2f-v2",
        "read_patch_count": 164,
        "retained_patch_count": 161,
        "ink_floor_excluded": False,
        "label": ETIQUETTE,
    }
    if divergence is not None:
        document["acceptance"] = {"mean_delta_e_before": divergence}
    return document


def _profil(dossier: Path, *, etiquette: str = ETIQUETTE,
            commentaire: str = "posé sur le plateau",
            divergence: float | None = 2.1):
    # Le chemin est demande a son PRODUCTEUR, jamais recompose : un banc qui
    # ecrit `dossier / "versions" / "calibration"` regarde un dossier que
    # `io/calibration_profile` seul decide, et il resterait vert le jour ou
    # celui-ci le deplacerait.
    chemin = calibration_profile.profile_path(dossier, RADICAL)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(_document(divergence)), encoding="utf-8")
    return scan_calibrate.ProfilDeChaineConsigne(
        profile_path=chemin, chain_id=CHAINE, etiquette=etiquette,
        commentaire=commentaire, lot_correction=_Correction(),
        document=_document(divergence))


def _formulaire(tmp_path: Path, *, defaut: bool) -> calib.FormulaireDeCalibration:
    formulaire = calib.FormulaireDeCalibration()
    formulaire.poser_le_scan(_Source(tmp_path / NOM_DU_SCAN))
    formulaire.dpi = "300"
    formulaire.devient_le_defaut = defaut
    return formulaire


def _calibrer_qui_reussit(dossier: Path):
    """Un `calibrer_la_chaine` de banc, **signature du coeur sans `**kwargs`**.

    Un faux permissif laisserait passer un appel dont un mot-cle est mal nomme,
    et le banc mesurerait alors son propre double.
    """
    def _calibrer(project_dir, scan_path, *, dpi, logger=None,
                  demander_le_nom_et_le_commentaire=None,
                  confirmer_l_ecrasement=None, rappel_progression=None):
        if demander_le_nom_et_le_commentaire is not None:
            demander_le_nom_et_le_commentaire(CHAINE)
        return _profil(Path(project_dir))
    return _calibrer


def _passe(dossier: Path, *, recalibration: bool = False,
           divergence: float | None = 2.1,
           commentaire: str = "posé sur le plateau") -> calib.PasseDeCalibration:
    return calib.PasseDeCalibration(
        profil=_profil(dossier, commentaire=commentaire,
                       divergence=divergence),
        chaine=CHAINE, recalibration=recalibration,
        date_precedente="28/08" if recalibration else "",
        date_ecrite="06/09")


def projet_reel(racine: Path, project_id: str) -> Path:
    """Un projet avec un `project.json` **valide au schema**, pas un squelette.

    `profile_designation._rewrite_color_section` rend `False` sans un mot quand
    il n'y a pas de manifest, et l'ecriture atomique **valide** son temporaire
    avant la bascule : un manifest bricole ne serait pas ecrit du tout, et ce
    banc mesurerait le mauvais refus -- un registre vide qui ressemble
    exactement au defaut qu'il cherche.

    **Recopie et non importee**, contre l'usage du depot, et la mesure impose
    l'exception : `tests/unit/test_profil_designe.py` porte deja cette fabrique
    (`_projet`), mais l'importer demande de poser `tests/unit` dans
    `sys.path`, ce qui casse la decouverte des `conftest.py` de
    `tests/unit/tui/` -- mesure du 2026-09-06 : 18 erreurs
    « fixture 'banc' not found » sur un fichier voisin qui n'avait pas change.
    """
    project_dir = racine / project_id
    project_layout.ensure_project_layout(project_dir)
    manifest = {
        "schema_version": "2.1",
        "project_id": project_id,
        "created": "2026-09-06T00:00:00Z",
        "artifacts": {"frames_dir": "frames", "outputs_dir": "outputs"},
        "color": {},
        "video": {},
        "reconstruction": {},
        "rushes": [],
        "lots": [],
    }
    (project_dir / extraction_manifest.MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return project_dir


#: Le pied du palier temoin. `E3-0` le dessine, et ce banc le LIT a sa
#: source -- voir la fin du fichier.
PIED_DU_PALIER = "Q quitter"


def _app(*ecrans) -> CoqueTui:
    return CoqueTui([PalierTemoin("Ateliers", PIED_DU_PALIER), *ecrans],
                    Contexte("projet", "Scan"))


# ===========================================================================
# D1 -- `designated_from` porte le PROFIL, jamais le scan
# ===========================================================================


def test_D1_la_source_designee_est_le_PROFIL_et_pas_le_SCAN(tmp_path: Path):
    """Le defaut, mesure a l'endroit exact ou il se produit.

    L'assertion porte sur ce que `consigner` **passe**, et non sur ce que le
    manifeste finit par contenir : les deux comptent, mais celle-ci nomme la
    ligne fautive. Le volet manifeste est le banc suivant.
    """
    vu = {}

    def _designer(dossier, document, *, project_path, source, as_default):
        vu.update(dossier=dossier, project_path=project_path, source=source,
                  as_default=as_default)

    passe = calib.consigner(
        tmp_path, _formulaire(tmp_path, defaut=True),
        poser_la_collision=lambda c: "annuler",
        calibrer=_calibrer_qui_reussit(tmp_path),
        designer_le_defaut=_designer)

    assert passe.a_ecrit is True
    assert Path(vu["source"]).suffix == ".json", (
        f"la source designee doit etre le fichier de profil ; recu "
        f"{vu['source']!r}")
    assert Path(vu["source"]) == Path(passe.profil.profile_path)
    assert Path(vu["source"]).name != NOM_DU_SCAN


def test_D1_le_MANIFESTE_ne_porte_plus_le_nom_du_pdf(tmp_path: Path):
    """Le volet **persiste**, avec le vrai `record_designated_profile`.

    C'est la seule mesure qui reponde a la phrase d'Egan : ce qu'il lit vient
    de `project.json`, pas d'un argument. Les deux cles sont verifiees --
    `record_designated_profile` ecrit **la meme entree aux deux endroits**, et
    n'en corriger qu'une laisserait le pied du menu Scan mentir pendant que la
    liste des profils dirait vrai.
    """
    projet = projet_reel(tmp_path, "projet-de-banc")

    calib.consigner(projet, _formulaire(tmp_path, defaut=True),
                    poser_la_collision=lambda c: "annuler",
                    calibrer=_calibrer_qui_reussit(projet))

    defaut = profile_designation.default_profile_entry(projet)
    profils = profile_designation.designated_profiles(projet)
    assert len(profils) == 1
    for entree, ou in ((defaut, "default_calibration_profile"),
                       (profils[0], "designated_calibration_profiles[0]")):
        source = entree[profile_designation.ENTRY_SOURCE_KEY]
        assert source == f"{RADICAL}.json", f"{ou} porte {source!r}"
        assert not source.endswith(".pdf"), ou

    # **Et c'est ce que l'operateur LIT** : la redaction unique du nom d'un
    # profil met `designated_from` en tete de sa precedence. Sans ce volet, le
    # banc mesurerait un champ que personne ne regarde.
    from mixed_media_utility.tui.palier_projet import nom_du_profil
    assert nom_du_profil(defaut) == f"{RADICAL}.json"
    assert nom_du_profil(defaut) != NOM_DU_SCAN


def test_D1_le_drapeau_DEVIENT_LE_DEFAUT_a_NON_n_inscrit_RIEN(tmp_path: Path):
    """Le drapeau varie dans les deux sens, et le second sens est une garde.

    « Poser un defaut est une decision, pas un effet de bord » : a `non`, cette
    passe fait exactement ce que `mmu scan ... calibrate` fait -- elle ecrit le
    profil et n'inscrit rien au manifeste. Corriger la source ne doit pas
    transformer un appel conditionnel en appel inconditionnel.
    """
    appels = []
    passe = calib.consigner(
        tmp_path, _formulaire(tmp_path, defaut=False),
        poser_la_collision=lambda c: "annuler",
        calibrer=_calibrer_qui_reussit(tmp_path),
        designer_le_defaut=lambda *a, **k: appels.append(k))
    assert passe.a_ecrit is True
    assert appels == []


# ===========================================================================
# D3 -- l'ecran de succes : le cartouche, la ligne d'etat, les suites
# ===========================================================================


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_D3_le_cartouche_porte_les_FAITS_de_la_passe(tmp_path: Path,
                                                     ascii_seul: bool):
    """Le fichier, la chaine, le nom, le commentaire, les pastilles, l'ecart.

    **`ascii_seul` varie dans les deux sens**, et ce n'est pas du zele : le
    glyphe de tete et l'unite de divergence en dependent tous les deux, et
    « un banc qui ne joue qu'`ascii_seul=False` mesure la moitie du produit et
    l'annonce verte » (`CLAUDE.md`, 2026-09-06).
    """
    panneau = calib.panneau_du_resultat(
        _passe(tmp_path), tmp_path, jetons.LARGEUR_PLANCHER, ascii_seul)
    # **La mesure porte sur les LIGNES du modele, pas sur le rendu a 80
    # colonnes** : `LigneChiffree.rendu` abrege ce qui deborde, et un banc qui
    # chercherait une sous-chaine dans le rendu mesurerait la longueur du
    # `tmp_path` de la machine plutot que le contenu du cartouche.
    par_libelle = {ligne.libelle: str(ligne.valeur) for ligne in panneau.lignes}

    assert f"{RADICAL}.json" in panneau.lignes[0].libelle
    assert par_libelle[calib.LIBELLE_CHAINE] == CHAINE
    assert par_libelle[calib.LIBELLE_ETIQUETTE] == ETIQUETTE
    assert par_libelle[calib.LIBELLE_COMMENTAIRE] == "posé sur le plateau"
    assert par_libelle[calib.LIBELLE_PASTILLES_DU_RESULTAT] == (
        "164 lues · 161 retenues")
    assert "2,1" in par_libelle[calib.LIBELLE_DIVERGENCE_DU_RESULTAT], (
        "l'ecart brut du profil ecrit n'est pas montre")
    assert par_libelle[calib.LIBELLE_DOSSIER_DU_RESULTAT] == str(
        calib.dossier_des_profils(tmp_path))
    # Le glyphe de tete est celui du mode joue, jamais celui de l'autre.
    assert panneau.lignes[0].libelle.startswith(
        jetons.glyphes(ascii_seul)["complete"])
    assert not panneau.lignes[0].libelle.startswith(
        jetons.glyphes(not ascii_seul)["complete"])
    # La prose qui dit a quoi ce profil sert vit dans le CORPS, pas en ligne
    # d'etat -- `EPIC11-ARB-56` interdirait un conseil d'usage la-bas.
    assert list(calib.PROSE_DU_PROFIL) == panneau.noms


def test_D3_une_ligne_NON_MESUREE_est_OMISE_et_jamais_rendue_a_vide(
        tmp_path: Path):
    """`DESIGN.md` section 3, et c'est le volet symetrique du banc precedent.

    Un profil sans commentaire et sans acceptation ne doit pas afficher une
    ligne `Commentaire` vide ni `0,0 ΔE` : « un champ non mesure est omis,
    jamais rendu faux ». Sans ce banc, un cartouche qui remplirait les trous
    de chaines vides resterait vert.
    """
    panneau = calib.panneau_du_resultat(
        _passe(tmp_path, commentaire="", divergence=None), tmp_path)
    libelles = [ligne.libelle for ligne in panneau.lignes]
    assert calib.LIBELLE_COMMENTAIRE not in libelles
    assert calib.LIBELLE_DIVERGENCE_DU_RESULTAT not in libelles
    # Ce qui EST mesure reste la : l'omission est ciblee, pas un panneau vide.
    assert f"{RADICAL}.json" in panneau.lignes[0].libelle
    assert calib.LIBELLE_PASTILLES_DU_RESULTAT in libelles


@pytest.mark.parametrize("recalibration", [False, True])
def test_D3_la_ligne_d_etat_distingue_les_DEUX_regimes_de_l_AC_8_1(
        tmp_path: Path, recalibration: bool):
    """Un profil neuf nomme UNE date ; une recalibration en nomme DEUX.

    Le drapeau varie dans les deux sens parce que c'est lui, et lui seul, qui
    choisit la phrase. Aucun avertissement dans l'un ni dans l'autre : une
    recalibration « se dit sans triangle et sans question ».
    """
    ligne = calib.ligne_d_etat_du_resultat(
        _passe(tmp_path, recalibration=recalibration))
    assert "06/09" in ligne
    assert "161" in ligne
    assert ("28/08" in ligne) is recalibration
    assert jetons.glyphes(False)["absent"] not in ligne
    assert "None" not in ligne


def test_D3_la_ligne_REMPLACE_du_cartouche_fait_VARIER_son_drapeau(
        tmp_path: Path):
    """La ligne `Remplace`, dans les DEUX sens -- mutant `C6` de la couche 1.

    **Elle n'etait lue par aucune assertion.** `test_D3_le_cartouche_porte_les
    FAITS_de_la_passe` lit sept lignes et saute celle-la, et le drapeau
    `recalibration` n'etait varie que pour la ligne d'ETAT. Mesure de la revue
    du 2026-09-06 : inverser la condition (`if not passe.recalibration`)
    laissait **188 tests verts**. Une recalibration aurait alors annonce
    « ce profil est nouveau dans ce projet », et un profil neuf « la passe du  »
    -- avec une date vide, puisqu'il n'y en a pas.

    C'est mot pour mot « une garde qui ne fait varier AUCUN de ses drapeaux »
    (`CLAUDE.md`, 2026-09-06), sur le seul champ du cartouche qui dit a
    l'operateur s'il vient d'ECRASER quelque chose.
    """
    def remplace(recalibration: bool) -> str:
        panneau = calib.panneau_du_resultat(
            _passe(tmp_path, recalibration=recalibration), tmp_path)
        return str({ligne.libelle: ligne.valeur
                    for ligne in panneau.lignes}[calib.LIBELLE_REMPLACE])

    apres_recalibration = remplace(True)
    sur_profil_neuf = remplace(False)

    assert apres_recalibration == calib.PHRASE_RECALIBRATION.format(date="28/08")
    assert sur_profil_neuf == calib.PHRASE_PROFIL_NEUF
    # **Et les deux phrases DIFFERENT** : sans cette ligne, deux gabarits
    # devenus identiques rendraient les deux assertions ci-dessus vraies en
    # meme temps sans que la ligne distingue plus rien.
    assert apres_recalibration != sur_profil_neuf
    # La date de la passe REMPLACEE, et pas celle de la passe ecrite : les
    # deux sont au dossier, et les confondre est le mode de panne suivant.
    assert "28/08" in apres_recalibration
    assert "06/09" not in apres_recalibration


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_D3_la_ligne_d_etat_n_INTERVERTIT_pas_les_deux_dates(
        tmp_path: Path, ascii_seul: bool):
    """L'appariement positionnel des deux dates -- mutant `C5` de la couche 1.

    **Echanger `ancienne` et `nouvelle` laissait 188 tests verts.** Le banc
    voisin n'assertait que `("28/08" in ligne) is recalibration`, et un `in`
    ne distingue pas les deux emplacements : l'ecran aurait annonce
    « profil pose le 06/09 · remplace le 28/08 », c'est-a-dire une chronologie
    a l'envers, sans qu'aucune mesure ne bouge. C'est la famille `M33` / `M25`
    de `CLAUDE.md` -- un appariement positionnel que seule une fabrique aux
    valeurs DISTINGUABLES peut demasquer, et les deux dates le sont.

    **`ascii_seul` varie ici aussi**, et c'est ce qui ferme `C7` : le glyphe de
    tete est le seul terme que le drapeau gouverne dans cette fonction, et il
    n'etait joue que dans un sens. Que `Palier.poser_etat` replie une seconde
    fois derriere ne rend pas la promesse de CETTE fonction moins vraie -- son
    jumeau `atelier_pdf_calibration.ligne_d_etat_du_resultat` est mesure sur
    les deux modes, et l'asymetrie ressemblait a un trou.
    """
    ligne = calib.ligne_d_etat_du_resultat(
        _passe(tmp_path, recalibration=True), ascii_seul)

    # Chaque date avec SON verbe : c'est ce qu'un `in` nu ne mesure pas.
    assert calib.ETAT_RESULTAT_RECALIBRE.format(
        ancienne="28/08", nouvelle="06/09", pastilles=161) in ligne
    # Et l'ordre, dit une seconde fois autrement -- un gabarit qui perdrait
    # ses deux verbes rendrait l'assertion ci-dessus vraie par vacuite.
    assert ligne.index("28/08") < ligne.index("06/09")
    assert ligne.startswith(jetons.glyphes(ascii_seul)["complete"])
    assert not ligne.startswith(jetons.glyphes(not ascii_seul)["complete"])


def test_D3_une_passe_sans_CARDINAL_de_pastilles_ne_dit_pas_None(
        tmp_path: Path):
    """Le repli de la ligne d'etat : la part non mesuree est **retiree**.

    Un `format` nu y ecrirait `None pastilles retenues`, c'est-a-dire un champ
    non mesure **rendu faux** -- exactement ce que `DESIGN.md` section 3
    interdit, et le mode de panne le plus courant d'un gabarit de phrase.
    """
    passe = calib.PasseDeCalibration(
        profil=_profil(tmp_path), chaine=CHAINE, date_ecrite="06/09")
    object.__setattr__(passe.profil, "lot_correction", None)
    ligne = calib.ligne_d_etat_du_resultat(passe)
    assert "None" not in ligne
    assert "06/09" in ligne


def test_D3_les_suites_sont_l_ensemble_EXACT_et_le_retour_n_y_est_qu_UNE_fois(
        tmp_path: Path, banc):
    """Trois suites contextuelles, plus le retour que la BASE ajoute.

    L'ecrire dans la liste le ferait voir deux fois -- `EcranResultat` l'ajoute
    d'office s'il manque (`EPIC11-ARB-13`). L'assertion porte sur l'ensemble
    **exact** et sur le CARDINAL : un `in` laisserait un doublon passer.
    """
    assert calib.suites_du_resultat() == [
        calib.SUITE_DOSSIER_DES_PROFILS,
        calib.SUITE_AUTRE_CHAINE,
        calib.SUITE_DETECTER,
    ]

    async def scenario(pilote):
        return calib.ouvrir_le_resultat(pilote.app, _passe(tmp_path),
                                        tmp_path, sur_suite=lambda s: None)

    ecran = banc(_app(), scenario)
    assert isinstance(ecran, execution.EcranResultat)
    assert ecran.suites == calib.suites_du_resultat() + [
        execution.EcranResultat.RETOUR]
    assert ecran.suites.count(execution.EcranResultat.RETOUR) == 1


# ===========================================================================
# D3 -- l'AIGUILLAGE : c'est lui que le court-circuit fermait
# ===========================================================================


def test_D3_une_passe_qui_a_ECRIT_ouvre_l_ecran_de_succes(tmp_path: Path,
                                                          banc):
    """Le defaut d'origine, mesure : la conclusion n'avait qu'une branche.

    Elle est prise sur `conclure_la_passe`, c'est-a-dire par le chemin que le
    fil de travail emprunte, et pas sur la fonction d'ouverture prise a part :
    « un mecanisme juste, cable nulle part » est le defaut que ce depot a paye
    sept fois.
    """
    ecran_du_formulaire = calib.EcranCalibrerLaChaine(
        tmp_path, calibrer=lambda f: None)
    app = _app(ecran_du_formulaire)
    p = parcours.ParcoursScan(app, tmp_path)
    p.ecran_de_calibration = ecran_du_formulaire
    vu = {}

    async def scenario(pilote):
        # **L'ecran se POUSSE** : `CoqueTui([...])` ne monte que son premier
        # palier, et `conclure_la_passe` depile ce qu'elle trouve au-dessus. Un
        # `E3-9` jamais empile ferait mesurer la pile du banc et non celle du
        # produit.
        pilote.app.descendre(ecran_du_formulaire)
        await pilote.pause()
        app.tache_en_cours = True
        p.conclure_la_passe(ecran_du_formulaire, _passe(tmp_path))
        await pilote.pause()
        vu["sommet"] = type(pilote.app.screen).__name__
        vu["E3-9 dessous"] = ecran_du_formulaire in pilote.app.screen_stack
        vu["etat"] = jetons.texte_affiche(
            str(pilote.app.screen.query_one("#etat").content))
        return vu

    banc(app, scenario)
    assert vu["sommet"] == "EcranCalibrationEcrite"
    # **`E3-9` reste DESSOUS, annote** : l'ecran de succes se pose dessus, il
    # ne le remplace pas. C'est ce qui rend « Calibrer une autre chaine »
    # atteignable d'un seul depilement.
    assert vu["E3-9 dessous"] is True
    assert ecran_du_formulaire.passe is not None
    assert "06/09" in vu["etat"]


def test_D3_un_REFUS_ouvre_toujours_son_impasse_et_PAS_le_succes(
        tmp_path: Path, banc):
    """Le drapeau refus / succes, dans son second sens.

    Ajouter une branche de succes ne doit pas manger celle du refus : les deux
    ecrans sont exclusifs, et un aiguillage ecrit a l'envers serait vert sur le
    seul banc du succes.
    """
    ecran_du_formulaire = calib.EcranCalibrerLaChaine(
        tmp_path, calibrer=lambda f: None)
    app = _app(ecran_du_formulaire)
    p = parcours.ParcoursScan(app, tmp_path)
    p.ecran_de_calibration = ecran_du_formulaire
    refus = calib.PasseDeCalibration(
        refus=scan_calibrate.RefusDeCalibration(
            "aucune page de calibration lue dans ce scan.",
            motif=scan_calibrate.REFUS_AUCUNE_PAGE_DE_CALIBRATION),
        motif=scan_calibrate.REFUS_AUCUNE_PAGE_DE_CALIBRATION)
    vu = {}

    async def scenario(pilote):
        pilote.app.descendre(ecran_du_formulaire)
        await pilote.pause()
        app.tache_en_cours = True
        p.conclure_la_passe(ecran_du_formulaire, refus)
        await pilote.pause()
        vu["sommet"] = type(pilote.app.screen).__name__
        return vu

    banc(app, scenario)
    assert vu["sommet"] == "EcranRefusDeCalibration"


def test_D3_une_ANNULATION_devant_la_collision_ne_monte_RIEN(tmp_path: Path,
                                                             banc):
    """La troisieme issue, et elle n'est ni un succes ni un refus a remontrer.

    L'operateur vient de dire « n'ecris rien » : lui montrer un ecran de succes
    serait faux, lui reposer le refus serait « l'invite qui apprend a repondre
    sans lire » (`EPIC5-ARB-99`). Le formulaire reste sous ses yeux.
    """
    ecran_du_formulaire = calib.EcranCalibrerLaChaine(
        tmp_path, calibrer=lambda f: None)
    app = _app(ecran_du_formulaire)
    p = parcours.ParcoursScan(app, tmp_path)
    p.ecran_de_calibration = ecran_du_formulaire
    annulee = calib.PasseDeCalibration(
        refus=calib.CalibrationAnnulee("calibration annulée"))
    vu = {}

    async def scenario(pilote):
        pilote.app.descendre(ecran_du_formulaire)
        await pilote.pause()
        app.tache_en_cours = True
        p.conclure_la_passe(ecran_du_formulaire, annulee)
        await pilote.pause()
        vu["sommet"] = type(pilote.app.screen).__name__
        return vu

    banc(app, scenario)
    assert vu["sommet"] == "EcranCalibrerLaChaine"


# ===========================================================================
# D3 -- les trois suites MENENT quelque part, et chacune ailleurs
# ===========================================================================


def test_D3_ouvrir_le_dossier_passe_par_le_LANCEUR_UNIQUE_du_paquet(
        tmp_path: Path, monkeypatch):
    """`EPIC11-ARB-85` : un seul lanceur, et le dossier vient du COEUR.

    Le chemin est celui que `calibration_profile` compose (`dossier_des_profils`
    en prend le parent), jamais un `versions/calibration` recompose ici : un
    chemin recompose divergerait au premier deplacement, et l'operateur
    ouvrirait un dossier vide.
    """
    ouverts = []
    monkeypatch.setattr(parcours, "ouvrir_dans_l_explorateur_du_systeme",
                        lambda dossier, **k: ouverts.append(Path(dossier)))
    p = parcours.ParcoursScan(_app(), tmp_path)
    p.suivre_le_resultat_de_la_calibration(
        _passe(tmp_path), calib.SUITE_DOSSIER_DES_PROFILS)
    assert ouverts == [calib.dossier_des_profils(tmp_path)]
    assert ouverts[0].name == "calibration"


def test_D3_calibrer_une_autre_chaine_DEPILE_et_retrouve_E3_9(tmp_path: Path,
                                                              banc):
    """La suite du milieu, et elle depile d'UN cran.

    `pop_screen` et non `action_remonter` : cette derniere est la touche
    `Échap` de l'operateur, **gardee par `tache_en_cours`**. Retenir une issue
    est un geste du parcours ; son effet ne doit pas dependre de l'etat d'une
    tache. Le banc laisse donc le drapeau a VRAI, ce qui est le regime ou le
    defaut mord.
    """
    ecran_du_formulaire = calib.EcranCalibrerLaChaine(
        tmp_path, calibrer=lambda f: None)
    app = _app(ecran_du_formulaire)
    p = parcours.ParcoursScan(app, tmp_path)
    p.ecran_de_calibration = ecran_du_formulaire
    vu = {}

    async def scenario(pilote):
        pilote.app.descendre(ecran_du_formulaire)
        await pilote.pause()
        calib.ouvrir_le_resultat(pilote.app, _passe(tmp_path), tmp_path,
                                 sur_suite=lambda s: None)
        await pilote.pause()
        pilote.app.tache_en_cours = True
        p.suivre_le_resultat_de_la_calibration(_passe(tmp_path),
                                               calib.SUITE_AUTRE_CHAINE)
        await pilote.pause()
        vu["sommet"] = type(pilote.app.screen).__name__
        return vu

    banc(app, scenario)
    assert vu["sommet"] == "EcranCalibrerLaChaine"


def test_D3_detecter_des_planches_remonte_a_E3_0_et_pas_plus_haut(
        tmp_path: Path, monkeypatch):
    """La suite de QUEUE, et c'est elle qu'un aiguillage tronque perdrait.

    Une chaine de `if` a laquelle il manque la derniere branche est verte sur
    les deux premieres suites : c'est le mode de panne que la regle des
    fabriques (point 4, cible a chaque bord) existe pour attraper, applique ici
    a un aiguillage plutot qu'a une collection.
    """
    from mixed_media_utility.tui import atelier_scan_resultat

    remontees = []
    monkeypatch.setattr(atelier_scan_resultat,
                        "remonter_a_l_ouverture_de_l_atelier",
                        lambda app: remontees.append(app))
    app = _app()
    p = parcours.ParcoursScan(app, tmp_path)
    p.suivre_le_resultat_de_la_calibration(_passe(tmp_path),
                                           calib.SUITE_DETECTER)
    assert remontees == [app]


def test_D3_le_RETOUR_aux_ateliers_n_est_PAS_traite_par_le_parcours(
        tmp_path: Path, monkeypatch):
    """La suite de TETE de l'ensemble complet, et le volet negatif de la queue.

    `EcranResultat` ajoute ET traite `Retour aux ateliers` lui-meme. Le doubler
    ici ferait deux redactions d'un retour, et la seconde divergerait le jour
    ou la base changerait la sienne. Un aiguillage qui l'attraperait par erreur
    -- un `else` final au lieu d'un troisieme `if` -- remonterait a `E3-0` sur
    une suite qui doit aller aux ateliers.
    """
    from mixed_media_utility.tui import atelier_scan_resultat

    remontees = []
    ouverts = []
    monkeypatch.setattr(atelier_scan_resultat,
                        "remonter_a_l_ouverture_de_l_atelier",
                        lambda app: remontees.append(app))
    monkeypatch.setattr(parcours, "ouvrir_dans_l_explorateur_du_systeme",
                        lambda dossier, **k: ouverts.append(dossier))
    p = parcours.ParcoursScan(_app(), tmp_path)
    p.suivre_le_resultat_de_la_calibration(
        _passe(tmp_path), execution.EcranResultat.RETOUR)
    assert remontees == []
    assert ouverts == []


# ===========================================================================
# La maquette que ce banc citait sans la LIRE
# ===========================================================================
#
# Frontiere `test_frontiere_des_maquettes_recopiees.py` : un banc qui asserte
# un litteral dessine le confronte a sa SOURCE. Le pied du palier temoin etait
# recopie a la main -- un double dont le pied n'est pas celui du dessin mesure
# un ecran que personne n'a approuve.

#: Le dossier des dessins approuves.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "\u2500\u2502\u250c\u2510\u2514\u2518\u251c\u2524\u252c\u2534\u253c\u2501\u2503\u258f\u2595"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


def test_le_PIED_du_palier_temoin_de_ce_banc_est_DESSINE():
    """`Q quitter` se lit sur le dessin du menu Scan (`E3-0`), il n'est pas invente ici."""
    menu = dessin_de_la_maquette("E3-0-scan-menu.txt")
    assert PIED_DU_PALIER in menu


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe.

    Le volet symetrique de la confrontation ci-dessus. Un `in` sur un dessin
    de plusieurs centaines de caracteres est vrai bien trop souvent pour se
    passer de son contre-exemple.
    """
    dessin = dessin_de_la_maquette("E3-0-scan-menu.txt")
    assert "Q quitter et revenir" not in dessin
    assert "Q fermer" not in dessin
