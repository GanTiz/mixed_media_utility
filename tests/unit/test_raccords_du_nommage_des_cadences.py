"""Les raccords de la convention de nommage des cadences (`EPIC11-ARB-62`).

Ce banc mesure **l'invariant lui-meme**, pas le cablage : pour une cadence
donnee, l'identifiant du lot et le nom de son dossier doivent etre la MEME
chaine. « Les deux appellent la meme fonction » ne le mesure pas -- un cablage
identique peut produire deux noms differents des qu'un des deux chemins ajoute
ou omet un fragment.

Trois arbitrages sont recopies **verbatim** ici, face aux tests qui les
mesurent, parce que c'est leur confrontation qui donne son sens au banc.

`ARB-3` (`decisions-2026-08-03.md`, decision 2), cite par la docstring de
`naming.build_lot_id` :

    « le nom de dossier de lot et l'identifiant de lot **ne peuvent plus
    diverger** »

`EPIC11-ARB-62`, tranche par Egan :

    « Un lot a cadence fractionnaire s'appelle **`rush-001_25s3`** -- le `s`
    tient la place de la barre. Le nom dit ce que l'operateur a demande, ce
    qu'un nom decimal perdrait. »

`EPIC11-ARB-72`, qui reposait sur une premisse fausse et que le lot P a rendue
vraie :

    « Les cadences fractionnaires **remarquables** restent proposees et
    cochables : [...] leur nom de lot vient de la convention `_25s3`
    (`EPIC11-ARB-62`) »

Ce que ce banc mesure, et dans cet ordre :

1. l'invariant d'`ARB-3` sur les deux chaines produites, avec et sans nom
   court, borne et non borne ;
2. le **troisieme** fragment -- le nom de fichier d'une frame -- qui doit venir
   du meme nom court, sans quoi `extraction.check_fps_form_consistency` refuse
   le lot ;
3. la non-regression, en **egalite d'ensembles** : l'ensemble des cadences dont
   le nom change est EXACTEMENT celles a developpement decimal infini ;
4. la frontiere des quatre consommateurs : ils portent le meme mot-cle, de meme
   defaut, ou aucun ;
5. le raccord TUI qui reste **ferme**, et la mesure qui dit pourquoi.
"""

from __future__ import annotations

import inspect
from fractions import Fraction

import pytest

from mixed_media_utility import extraction, scan_output_frames
from mixed_media_utility.io import project_layout
from mixed_media_utility.io.naming import (
    CANONICAL_ID_MAX_LENGTH,
    NamingError,
    build_extracted_frame_filename,
    build_lot_id,
    format_fps_short,
)
from mixed_media_utility.tui.cadences import nom_court_de_cadence

#: Le rush de reference du banc. Court, pour que `derive_short_id` rende son
#: entree inchangee : au-dela de `CANONICAL_ID_MAX_LENGTH`, `build_lot_id`
#: raccourcit et `rush_dir_slug` non, et c'est une divergence CONNUE et
#: anterieure a `EPIC11-ARB-62` (elle est documentee par la garde de la story
#: 3.7). Elle n'est pas ce que ce banc mesure ; un test nomme la borne plus bas.
RUSH = "rush_01"

#: La cadence source NTSC exacte -- `23,976` de tout materiel americain.
#: `deferred-work.md` mesurait que ses QUATRE remarquables portaient des noms a
#: dix-sept chiffres, ligne « (toutes) » comprise.
FPS_NTSC = Fraction(24000, 1001)


def _a_un_developpement_decimal_infini(valeur: Fraction) -> bool:
    """La definition, reecrite ICI et non importee du module mesure.

    Un rationnel a un developpement decimal fini si et seulement si son
    denominateur reduit ne porte que des facteurs 2 et 5. L'importer de
    `tui.cadences` ferait de l'egalite d'ensembles une tautologie : un mutant
    qui casse le test de finitude casserait les deux cotes de l'egalite et
    resterait vert.
    """
    reste = Fraction(valeur).denominator
    for facteur in (2, 5):
        while reste % facteur == 0:
            reste //= facteur
    return reste != 1


#: Trois cadences, la CIBLE au milieu (`CLAUDE.md`, regle des fabriques,
#: points 2 et 2 bis). La cible est la cadence a developpement infini : c'est
#: elle seule que `EPIC11-ARB-62` renomme, et une fabrique qui la placerait en
#: premiere ou en derniere position ne separerait pas « la boucle traite la
#: cible » de « la boucle s'arrete a la cible » ou « ne traite que la
#: premiere ».
CADENCES_DE_L_INVARIANT = (
    Fraction(25, 2),   # developpement fini -> `12p5`, le nom des lots livres
    Fraction(25, 3),   # CIBLE, developpement infini -> `25s3`, AU MILIEU
    Fraction(25, 1),   # entiere -> `25`
)

#: Les quatre remarquables d'un rush NTSC : `source`, `source / 2`,
#: `source / 3`, `source / 4`. Les QUATRE ont un developpement infini, donc les
#: quatre changent de nom -- la ligne « (toutes) » comprise, ce qui est
#: exactement ce que le garde-fou ecrit puis RETIRE de cette vague cassait.
REMARQUABLES_NTSC = tuple(FPS_NTSC / n for n in (1, 2, 3, 4))


# --- 1. l'invariant d'ARB-3, sur les DEUX chaines produites -----------------


@pytest.mark.parametrize("valeur", CADENCES_DE_L_INVARIANT + REMARQUABLES_NTSC)
def test_le_lot_id_et_le_nom_de_son_DOSSIER_coincident_avec_le_nom_court(valeur):
    """`ARB-3` verbatim : « le nom de dossier de lot et l'identifiant de lot
    **ne peuvent plus diverger** ».

    La mesure porte sur les deux CHAINES produites, jamais sur le fait que les
    deux fonctions consomment la meme brique.
    """
    nom_court = nom_court_de_cadence(valeur)
    lot_id = build_lot_id(RUSH, float(valeur), fps_short_name=nom_court)
    dossier = project_layout.rush_dir_slug(RUSH, float(valeur),
                                           fps_short_name=nom_court)
    assert lot_id == dossier, (valeur, lot_id, dossier)
    # Et le nom obtenu est bien celui de la convention, pas un artefact : le
    # volet positif, sans lequel deux chaines egales et fausses passeraient.
    assert lot_id == f"{RUSH}_{nom_court}"


@pytest.mark.parametrize("valeur", CADENCES_DE_L_INVARIANT + REMARQUABLES_NTSC)
def test_le_lot_id_et_le_nom_de_son_DOSSIER_coincident_SANS_nom_court(valeur):
    """Le volet symetrique : l'invariant tenait deja avant `EPIC11-ARB-62`, et
    le raccord ne doit pas l'avoir casse sur le chemin d'avant."""
    lot_id = build_lot_id(RUSH, float(valeur))
    dossier = project_layout.rush_dir_slug(RUSH, float(valeur))
    assert lot_id == dossier == f"{RUSH}_{format_fps_short(float(valeur))}"


@pytest.mark.parametrize("valeur", CADENCES_DE_L_INVARIANT)
def test_l_invariant_tient_aussi_sur_une_extraction_BORNEE(valeur):
    """Le condensat de bornes (`bounds_suffix`, story 3.7) est le meme fragment
    des deux cotes : un extrait a cadence fractionnaire ne peut donc pas voir
    son dossier et son identifiant se separer non plus."""
    bornes = {"source_in_timecode": "15:34:30:00",
              "source_out_timecode": "15:34:50:00"}
    nom_court = nom_court_de_cadence(valeur)
    lot_id = build_lot_id(RUSH, float(valeur), fps_short_name=nom_court, **bornes)
    dossier = project_layout.rush_dir_slug(RUSH, float(valeur),
                                           fps_short_name=nom_court, **bornes)
    assert lot_id == dossier
    assert lot_id.startswith(f"{RUSH}_{nom_court}-")


def test_les_DOSSIERS_frames_et_output_frames_d_un_meme_lot_portent_le_MEME_slug(tmp_path):
    """`frames/` et `output-frames/` sont les deux moities d'un meme lot.

    Un mot-cle offert a l'un et pas a l'autre leur ferait porter deux noms, et
    l'`encode` chercherait les frames rescannees sous un dossier qui n'existe
    pas.
    """
    valeur = CADENCES_DE_L_INVARIANT[1]  # la CIBLE, au milieu de la fabrique
    nom_court = nom_court_de_cadence(valeur)
    frames = project_layout.extract_frames_dir(tmp_path, RUSH, float(valeur),
                                       fps_short_name=nom_court)
    sorties = project_layout.scan_frames_dir(tmp_path, RUSH, float(valeur),
                                               fps_short_name=nom_court)
    assert frames.name == sorties.name == f"{RUSH}_{nom_court}"
    assert frames.parent.name == project_layout.FRAMES_DIRNAME
    assert sorties.parent.name == project_layout.OUTPUT_FRAMES_DIRNAME


# --- 2. le TROISIEME fragment : le nom de fichier d'une frame ---------------


@pytest.mark.parametrize("valeur", CADENCES_DE_L_INVARIANT + REMARQUABLES_NTSC)
def test_le_nom_de_FICHIER_porte_le_meme_fragment_que_le_dossier(valeur):
    """`extraction.check_fps_form_consistency` existe pour refuser un lot dont
    le dossier et les fichiers ne disent pas la meme cadence. Le nom court doit
    donc atteindre les TROIS chemins ou aucun."""
    nom_court = nom_court_de_cadence(valeur)
    dossier = project_layout.rush_dir_slug(RUSH, float(valeur),
                                           fps_short_name=nom_court)
    fichier = build_extracted_frame_filename(RUSH, float(valeur), "00:00:00:00",
                                             fps_short_name=nom_court)
    # Le fragment de cadence du nom de fichier, lu entre les deux `_` finaux.
    fragment_du_fichier = fichier[: -len("_00-00-00-00.tiff")].rpartition("_")[2]
    fragment_du_dossier = dossier.rpartition("_")[2]
    assert fragment_du_fichier == fragment_du_dossier == nom_court
    assert fichier == f"{RUSH}_{nom_court}_00-00-00-00.tiff"


# --- 3. la non-regression, en EGALITE D'ENSEMBLES ---------------------------


def _echantillon_large() -> tuple[Fraction, ...]:
    """Un echantillon large, et les remarquables de plusieurs sources dedans.

    La grille brute couvre les cadences de travail (`1/24` a `60`) ; les
    remarquables des six sources de terrain -- dont les deux NTSC -- y ajoutent
    les cas qu'`EPIC11-ARB-62` nomme explicitement.
    """
    grille = [Fraction(n, d) for n in range(1, 61) for d in range(1, 25)]
    sources = (Fraction(25), Fraction(24), Fraction(30), Fraction(50),
               Fraction(24000, 1001), Fraction(30000, 1001))
    remarquables = [source / n for source in sources for n in (1, 2, 3, 4)]
    return tuple(dict.fromkeys(grille + remarquables))


def test_l_ensemble_des_cadences_dont_le_nom_CHANGE_est_EXACTEMENT_celles_a_developpement_infini():
    """L'exigence de non-regression, et elle est dure : **aucun lot deja livre
    ne doit changer de nom**.

    L'assertion est une **egalite d'ensembles**, pas une assertion positive :
    « ces cadences-la changent » laisserait passer toute divergence
    supplementaire, alors que « l'ensemble de celles qui changent est
    EXACTEMENT celui des developpements infinis » mesure la regle ET son
    unicite (`CLAUDE.md`, « deux mesures qui ne prouvent pas ce qu'on croit »).
    """
    echantillon = _echantillon_large()
    changent = {c for c in echantillon
                if nom_court_de_cadence(c) != format_fps_short(float(c))}
    infinies = {c for c in echantillon if _a_un_developpement_decimal_infini(c)}

    assert changent == infinies, {
        "changent sans etre infinies": sorted(changent - infinies, key=float),
        "infinies sans changer": sorted(infinies - changent, key=float),
    }
    # Les deux cotes sont non vides : une egalite d'ensembles VIDES passerait
    # sans rien mesurer.
    assert len(changent) > 100
    assert len(echantillon) - len(changent) > 100
    # Et les cas nommes par l'arbitrage sont bien du bon cote.
    assert Fraction(25, 3) in changent
    assert all(r in changent for r in REMARQUABLES_NTSC)
    assert Fraction(25, 2) not in changent and Fraction(25, 1) not in changent


def test_les_QUATRE_remarquables_d_un_rush_NTSC_perdent_leurs_dix_sept_chiffres():
    """`deferred-work.md`, mesure du 2026-08-30, verbatim dans son tableau :
    `rush_01_23p976023976023978` et ses trois soeurs. Ce que la convention rend
    a leur place est ecrit **en dur** ici, jamais recalcule."""
    avant = [format_fps_short(float(v)) for v in REMARQUABLES_NTSC]
    assert avant == ["23p976023976023978", "11p988011988011989",
                     "7p992007992007992", "5p994005994005994"]
    apres = [nom_court_de_cadence(v) for v in REMARQUABLES_NTSC]
    assert apres == ["24000s1001", "12000s1001", "8000s1001", "6000s1001"]
    # Et c'est bien ce que les trois chemins ecrivent, une fois raccordes.
    assert [build_lot_id(RUSH, float(v), fps_short_name=n)
            for v, n in zip(REMARQUABLES_NTSC, apres)] == [
        f"{RUSH}_{n}" for n in apres]
    assert [project_layout.rush_dir_slug(RUSH, float(v), fps_short_name=n)
            for v, n in zip(REMARQUABLES_NTSC, apres)] == [
        f"{RUSH}_{n}" for n in apres]


def test_sans_le_mot_cle_les_TROIS_chemins_rendent_EXACTEMENT_les_noms_d_avant():
    """Ajout pur, mesure contre une table ECRITE EN DUR.

    Jamais contre `format_fps_short` : un mutant de cette fonction casserait
    les deux cotes de l'egalite et resterait vert (`CLAUDE.md`, le test
    tautologique de la story 5.9).
    """
    attendus = {
        25.0: "25",
        12.5: "12p5",
        6.25: "6p25",
        8.333333333333334: "8p333333333333334",
        23.976023976023978: "23p976023976023978",
        5.0: "5",
        0.5: "0p5",
    }
    for fps, fragment in attendus.items():
        assert build_lot_id(RUSH, fps) == f"{RUSH}_{fragment}"
        assert project_layout.rush_dir_slug(RUSH, fps) == f"{RUSH}_{fragment}"
        assert build_extracted_frame_filename(RUSH, fps, "00:00:00:00") == (
            f"{RUSH}_{fragment}_00-00-00-00.tiff")


# --- 4. la frontiere des quatre consommateurs -------------------------------


#: Les quatre fonctions qui composent un fragment de cadence. `ARB-3` exige
#: qu'elles partent ENSEMBLE : une seule qui resterait sur `format_fps_short`
#: ferait diverger le nom du lot, celui de son dossier ou celui de ses
#: fichiers.
CONSOMMATEURS_DU_NOM_COURT = (
    build_lot_id,
    project_layout.rush_dir_slug,
    project_layout.extract_frames_dir,
    project_layout.scan_frames_dir,
    build_extracted_frame_filename,
)


@pytest.mark.parametrize("fonction", CONSOMMATEURS_DU_NOM_COURT,
                         ids=lambda f: f.__name__)
def test_chaque_consommateur_porte_le_meme_mot_cle_de_meme_defaut(fonction):
    """Meme nom, meme defaut `None`, et **mot-cle uniquement**.

    Positionnel, il se glisserait a la place d'un autre argument au premier
    reordonnancement ; a defaut non nul, il changerait le nom d'extractions
    deja livrees.
    """
    parametre = inspect.signature(fonction).parameters.get("fps_short_name")
    assert parametre is not None, fonction.__name__
    assert parametre.kind is inspect.Parameter.KEYWORD_ONLY
    assert parametre.default is None


@pytest.mark.parametrize("nom_fautif", ["", "25/3", "25.3", "..", "25 3", "../x"])
def test_un_nom_court_hors_du_pattern_canonique_est_refuse_par_les_trois_chemins(nom_fautif):
    """La garde est **load-bearing**, et pas seulement pour le manifeste : le
    slug devient un COMPOSANT DE CHEMIN, donc `25/3` ou `../x` ecrirait le lot
    ailleurs que sous `frames/`. C'est le meme motif que la garde payee a la
    revue du 2026-08-08 sur `derive_lot_dir_slug`, ou un TIFF 16 bits avait ete
    ecrit **hors du dossier projet**.
    """
    with pytest.raises(NamingError):
        build_lot_id(RUSH, 8.333333333333334, fps_short_name=nom_fautif)
    with pytest.raises(NamingError):
        project_layout.rush_dir_slug(RUSH, 8.333333333333334,
                                     fps_short_name=nom_fautif)
    with pytest.raises(NamingError):
        build_extracted_frame_filename(RUSH, 8.333333333333334, "00:00:00:00",
                                       fps_short_name=nom_fautif)


def test_le_volet_symetrique_un_nom_court_CANONIQUE_traverse_les_trois_chemins():
    """Sans lui, une garde qui refuserait TOUT passerait le test precedent."""
    for nom in ("25s3", "24000s1001", "12p5", "25", "6p25"):
        assert build_lot_id(RUSH, 1.0, fps_short_name=nom) == f"{RUSH}_{nom}"
        assert project_layout.rush_dir_slug(RUSH, 1.0, fps_short_name=nom) == (
            f"{RUSH}_{nom}")
        assert build_extracted_frame_filename(RUSH, 1.0, "00:00:00:00",
                                              fps_short_name=nom) == (
            f"{RUSH}_{nom}_00-00-00-00.tiff")


def test_la_divergence_CONNUE_des_noms_de_rush_trop_longs_n_est_pas_ce_banc():
    """Elle preexiste a `EPIC11-ARB-62` et n'est pas rouverte ici.

    Au-dela de `CANONICAL_ID_MAX_LENGTH`, `build_lot_id` raccourcit par
    `derive_short_id` et `rush_dir_slug` non. Le nommer explicitement evite
    qu'un lecteur prenne l'invariant mesure plus haut pour plus large qu'il
    n'est -- et le refus nomme de la story 11.4 mord AVANT sur le chemin du nom
    court.
    """
    rush_long = "A" * CANONICAL_ID_MAX_LENGTH
    assert build_lot_id(rush_long, 25.0) != project_layout.rush_dir_slug(
        rush_long, 25.0)
    # Sur le chemin du nom court, le depassement est REFUSE plutot que tronque :
    # une troncature remplacerait `25s3` par un condensat au moment precis ou il
    # devait dire « une image sur trois ».
    with pytest.raises(NamingError, match="Nom de rush trop long"):
        build_lot_id(rush_long, 8.333333333333334, fps_short_name="25s3")


# --- 5. le raccord TUI, et pourquoi il reste FERME --------------------------


def test_le_raccord_de_L_ECRITURE_reste_ferme_tant_que_le_COEUR_ignore_le_nom_court():
    """La mesure qui gouverne la fin du lot P, et le tripwire qui l'ouvrira.

    `tui.atelier_extraction_ecriture` ne compose aucun nom : il appelle
    `build_lot_id` et `project_layout.extract_frames_dir` avec **les memes arguments**
    que ceux qu'il passera a `extraction.run_extraction`, et c'est ce qui rend
    vrai `EPIC11-ARB-46` (verbatim : « l'apercu ne peut jamais mentir »).

    Or `run_extraction` **derive le nom lui-meme** (`extraction.py`, etape 1 :
    `build_lot_id(rush_id, fps_target, **bornes)`) et n'a aucun argument de nom
    de lot. Lui passer le nom court cote apercu SANS qu'il puisse le recevoir
    ferait annoncer `rush_01_25s3` a l'ecran et ecrire
    `rush_01_8p333333333333334` sur le disque -- mesure, pas suppose. Trois
    consequences en decoulent, toutes reelles :

    * l'apercu ment (`EPIC11-ARB-46`) ;
    * l'appariement `etats.get(lot_id)` ne trouve plus l'etat du lot, donc la
      garde `refus_d_etat_de_lot` (AC 7.5) devient aveugle -- or elle est
      load-bearing, le coeur detruisant les frames avant de refuser
      (`EPIC11-ARB-83`) ;
    * `deja_present` regarde un dossier qui n'existe pas, donc `overwrite=False`
      et le coeur refuse « un lot est deja present ».

    Ce test devient rouge le jour ou `run_extraction` gagne le mot-cle. C'est
    le bon moment, et le geste est alors de DEUX lignes :
    `atelier_extraction_ecriture:414` et `:1583` passent
    `fps_short_name=cadences.nom_court_de_cadence(valeur)` (resp.
    `cadence.nom_court()`), et `preparer_le_plan` le passe aussi a
    `frames_dir`.
    """
    parametres = inspect.signature(extraction.run_extraction).parameters
    assert "fps_short_name" not in parametres, (
        "`run_extraction` sait desormais recevoir le nom court : le raccord de "
        "`tui/atelier_extraction_ecriture.py` (lignes 414 et 1583) doit etre "
        "pose DANS LE MEME MOUVEMENT, sans quoi l'apercu et le disque "
        "divergent. Voir la fiche 11.4, lot P.")


def test_la_reconstruction_depuis_le_QR_ne_sait_pas_ENCORE_lire_un_nom_court():
    """Le second verrou, et il est plus profond que le premier.

    Le payload QR ne porte que `fps_target`, **un nombre**
    (`io/payload.py`) : `scan_output_frames.derive_lot_dir_slug` recompose donc
    le slug par `format_fps_short(fps_target)`. Un lot nomme `rush_01_25s3`
    serait introuvable depuis sa propre planche imprimee -- mesure ici, et
    c'est ce qui fait de la fin d'`EPIC11-ARB-62` une story de coeur et non un
    cablage : le nom court doit etre PERSISTE (manifeste et payload), pas
    seulement calcule.
    """
    valeur = CADENCES_DE_L_INVARIANT[1]  # la CIBLE, au milieu
    nom_court = nom_court_de_cadence(valeur)
    lot_id = build_lot_id(RUSH, float(valeur), fps_short_name=nom_court)
    with pytest.raises(scan_output_frames.LotInconsistencyError):
        scan_output_frames.derive_lot_dir_slug(
            rush_id=RUSH, fps_target=float(valeur), lot_id=lot_id)
    # Volet symetrique : le meme lot nomme SANS nom court se retrouve, lui.
    ancien = build_lot_id(RUSH, float(valeur))
    assert scan_output_frames.derive_lot_dir_slug(
        rush_id=RUSH, fps_target=float(valeur), lot_id=ancien) == ancien
