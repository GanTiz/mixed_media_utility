# -*- coding: utf-8 -*-
"""Le modele pur de la liste des rushes et du relink (story 11.4, lot D).

**Trois collections a risque, et la regle des fabriques s'y applique
integralement** (`CLAUDE.md`, quatrieme recidive du depot apres 5.6, 5.7 et
5.8) :

* toute fabrique de manifeste produit **au moins deux rushes distinguables** --
  cadences, resolutions et durees toutes differentes, jamais un remplissage
  uniforme : une permutation ne se voit que si les elements different ;
* le rush **absent** est place **ailleurs qu'en premiere position** ;
* un manifeste porte **deux absents**, la cible en **seconde** position : c'est
  l'AC 4.4, et un relink qui traiterait toujours le premier absent ne se
  demasque pas autrement -- c'est litteralement le mutant `M25` de la story 5.7,
  ou `_find_lot` rendait le premier lot et 257 tests restaient verts.

Les lots sont eux aussi multiples et **melanges** : le lot du rush vise n'est
jamais le premier de `lots[]`, sans quoi un appariement positionnel dans la
derivation de duree resterait vert.
"""
import json
import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import relink
from mixed_media_utility.io import extraction_manifest
from mixed_media_utility.tui import jetons, projet_lecture, rushes

from outils_frontiere import chaines_de_code, identifiants


# ---------------------------------------------------------------------------
# Fabriques -- deux rushes distinguables au minimum, valeurs toutes distinctes
# ---------------------------------------------------------------------------

def rush(rush_id: str, *, fps: float = 25.0, largeur: int = 1920,
         hauteur: int = 1080, chemin: str | None = "/rushes/rush.mov",
         nom: str | None = None, timecode: str | None = "00:00:00:00") -> dict:
    """Une entree `rushes[]`. Aucune valeur par defaut n'est partagee entre
    deux appels de la fabrique de manifeste ci-dessous : chaque rush porte sa
    cadence, sa resolution et sa duree.

    `fps_source_exact` est une **fraction**, comme le schema v2 l'exige : un
    manifeste fabrique hors schema passerait la lecture et echouerait a
    l'ecriture, c'est-a-dire exactement la ou ce banc mesure.
    """
    exacte = Fraction(fps).limit_denominator(1000)
    entree = {
        "rush_id": rush_id,
        "source_name": nom if nom is not None else f"{rush_id}.mov",
        "fps_source": fps,
        "fps_source_exact": f"{exacte.numerator}/{exacte.denominator}",
        "resolution_source": {"width": largeur, "height": hauteur},
        "source_metadata_absent_fields": [],
    }
    if chemin is not None:
        entree["source_path"] = chemin
    if timecode is not None:
        entree["source_start_timecode"] = timecode
    return entree


def lot(lot_id: str, rush_id: str, *, frames: int = 6300,
        exact: bool = True) -> dict:
    """Un lot, qui porte le cardinal source du rush ENTIER."""
    return {
        "lot_id": lot_id,
        "rush_id": rush_id,
        "state": "extraction",
        "source_frame_count": frames,
        "source_frame_count_is_exact": exact,
    }


def manifeste(rushes_declares, lots=()) -> dict:
    return {
        "schema_version": "2.1",
        "project_id": "projet_demo",
        "rushes": list(rushes_declares),
        "lots": list(lots),
        "artifacts": {},
        "color": {},
        "video": {},
        "reconstruction": {},
    }


#: Le manifeste de reference des mesures : **trois rushes distinguables**, dont
#: l'absent est le **troisieme** -- jamais le premier. Les trois cadences, les
#: trois resolutions et les trois durees different deux a deux, et l'ordre de
#: `rushes[]` n'est **pas** l'ordre alphabetique : `zz_rush_02` avant
#: `rush_hiver` demasque un tri qui se serait glisse dans la liste.
def manifeste_de_reference() -> dict:
    return manifeste(
        [
            rush("rush_01", fps=25.0, largeur=1920, hauteur=1080,
                 chemin="/rushes/rush_01.mov"),
            rush("zz_rush_02", fps=50.0, largeur=1280, hauteur=720,
                 chemin="/rushes/zz_rush_02.mov"),
            rush("rush_hiver", fps=24.0, largeur=4096, hauteur=2160,
                 chemin="/perdu/rush_hiver.mov"),
        ],
        # Le lot du rush vise n'est **pas** le premier de `lots[]`, et un lot
        # d'un autre rush s'intercale : un appariement positionnel rendrait le
        # mauvais cardinal.
        [
            lot("rush_01_25", "rush_01", frames=6300),
            lot("zz_rush_02_50", "zz_rush_02", frames=37900),
            lot("rush_hiver_24", "rush_hiver", frames=3012),
        ],
    )


def manifeste_a_deux_absents() -> dict:
    """AC 4.4 : **deux** rushes absents, la cible en **seconde** position.

    `rush_perdu_a` est absent AVANT `rush_hiver` : un relink qui prendrait
    « le premier absent » viserait `rush_perdu_a` et ce banc le verrait.
    """
    return manifeste(
        [
            rush("rush_01", fps=25.0, largeur=1920, hauteur=1080,
                 chemin="/rushes/rush_01.mov"),
            rush("rush_perdu_a", fps=30.0, largeur=3840, hauteur=2160,
                 chemin="/perdu/rush_perdu_a.mov"),
            rush("rush_hiver", fps=24.0, largeur=4096, hauteur=2160,
                 chemin="/perdu/rush_hiver.mov"),
        ],
        [
            lot("rush_01_25", "rush_01", frames=6300),
            lot("rush_perdu_a_30", "rush_perdu_a", frames=900),
            lot("rush_hiver_24", "rush_hiver", frames=3012),
        ],
    )


def existe_sauf(*manquants):
    """Un verificateur d'existence PUR : il ne touche pas le disque.

    C'est ce qui permet de mesurer l'AC 2.2 -- « la presence est celle que
    `statut_de_liaison` rend, et elle seule » : si le modele allait voir le
    disque de son cote, il contredirait ce verificateur.
    """
    perdus = set(manquants)

    def _existe(chemin: str) -> bool:
        return chemin not in perdus

    return _existe


EXISTE_SAUF_HIVER = existe_sauf("/perdu/rush_hiver.mov")
EXISTE_SAUF_LES_DEUX = existe_sauf("/perdu/rush_hiver.mov",
                                   "/perdu/rush_perdu_a.mov")


def projet(tmp_path, document=None) -> Path:
    """Un dossier projet portant un `project.json` reel."""
    dossier = tmp_path / "projet_demo"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / extraction_manifest.MANIFEST_FILENAME).write_text(
        json.dumps(document if document is not None else manifeste_de_reference(),
                   indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    return dossier


def probe_de(nom: str, frames: int, timecode: str | None,
             exact: bool = True) -> relink.ProbeCandidat:
    return relink.ProbeCandidat(nom_de_base=nom, cardinal_frames=frames,
                                cardinal_est_exact=exact,
                                timecode_depart=timecode)


def probe_conforme(chemin: Path) -> relink.ProbeCandidat:
    """Un probe qui fait correspondre n'importe quel fichier a `rush_hiver`."""
    return probe_de("rush_hiver.mov", 3012, "00:00:00:00")


# ---------------------------------------------------------------------------
# AC 2.1 -- l'ordre du manifeste, et les trois colonnes techniques
# ---------------------------------------------------------------------------

def test_les_rushes_sont_listes_DANS_L_ORDRE_DU_MANIFESTE(tmp_path):
    """AC 2.1. L'ordre du manifeste n'est **pas** l'ordre alphabetique dans la
    fixture : un `sorted` glisse dans la liste rendrait `rush_01`, `rush_hiver`,
    `zz_rush_02`, et ce test le verrait."""
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)

    identites = [r.rush_id for r in liste.rushes]
    assert identites == ["rush_01", "zz_rush_02", "rush_hiver"]
    assert identites != sorted(identites), (
        "la fixture doit porter un ordre non alphabetique, sans quoi elle ne "
        "mesure rien")


def test_chaque_rush_porte_SA_cadence_SA_resolution_et_SA_duree(tmp_path):
    """AC 2.1, et c'est la regle des fabriques : les trois rushes portent trois
    triplets **tous differents**. Un remplissage uniforme rendrait la meme
    colonne technique pour les trois, et toute permutation resterait verte."""
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)
    techniques = [r.technique() for r in liste.rushes]

    assert techniques == [
        "25 fps · 1920×1080 · 4:12",
        "50 fps · 1280×720 · 12:38",
        "24 fps · 4096×2160 · 2:05",
    ]
    assert len(set(techniques)) == 3


def test_la_duree_est_DERIVEE_du_cardinal_source_du_lot_du_rush_VISE(tmp_path):
    """La duree se derive de `lots[].source_frame_count` **du rush vise**.

    Le lot de `rush_hiver` est le **troisieme** de `lots[]`, et les trois
    cardinaux different : un appariement positionnel rendrait `4:12` (le
    cardinal du premier lot) au lieu de `2:05`.
    """
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)

    assert liste.viser("rush_hiver").duree == "2:05"
    assert liste.viser("rush_01").duree == "4:12"


def test_une_duree_INDERIVABLE_ne_ment_pas_et_ne_fait_pas_tomber_l_ecran():
    """Un rush sans lot n'a pas de cardinal source : la colonne le **dit**
    plutot que d'afficher `0:00`, qui serait un chiffre faux."""
    document = manifeste([rush("rush_01", fps=25.0),
                          rush("rush_sans_lot", fps=48.0, largeur=2048,
                               hauteur=858)],
                         [lot("rush_01_25", "rush_01", frames=6300)])
    liste = rushes.ListeDesRushes(rushes.rushes_du_manifeste(
        document, existe=existe_sauf()))

    sans_lot = liste.viser("rush_sans_lot")
    assert sans_lot.duree is None
    assert sans_lot.technique() == f"48 fps · 2048×858 · {jetons.GLYPHES['neutre']}"
    assert "0:00" not in sans_lot.technique()


def test_des_lots_qui_se_CONTREDISENT_sur_le_cardinal_ne_font_pas_tomber_la_liste():
    """`charger_reference` **refuse** de choisir entre deux cardinaux
    divergents (`REFUS_CARDINAUX_DIVERGENTS`). Lister n'est pas relinker : la
    liste doit s'ouvrir quand meme, sans duree, plutot que de refuser tout
    l'ecran sur un manifeste incoherent."""
    document = manifeste(
        [rush("rush_01", fps=25.0), rush("rush_double", fps=24.0)],
        [lot("a", "rush_01", frames=6300),
         lot("b", "rush_double", frames=3012),
         lot("c", "rush_double", frames=9999)])

    liste = rushes.ListeDesRushes(rushes.rushes_du_manifeste(
        document, existe=existe_sauf()))

    assert liste.viser("rush_double").duree is None
    assert liste.viser("rush_01").duree == "4:12"


def test_la_liste_se_lit_par_projet_lecture_et_JAMAIS_par_une_SECONDE_lecture(
        tmp_path, monkeypatch):
    """AC 2.5. La porte unique du disque est `projet_lecture.lire_manifeste` :
    si le module en ouvrait une seconde, neutraliser celle-ci ne suffirait pas
    a vider la liste."""
    dossier = projet(tmp_path)
    monkeypatch.setattr(projet_lecture, "lire_manifeste", lambda _: None)

    assert rushes.lister(dossier, existe=EXISTE_SAUF_HIVER).rushes == []


def test_le_fichier_LU_est_celui_qui_sera_ECRIT():
    """Lire un fichier et en ecrire un autre serait un relink sans effet."""
    from mixed_media_utility.gui.depot_projets import NOM_FICHIER_PROJET

    assert NOM_FICHIER_PROJET == extraction_manifest.MANIFEST_FILENAME


# ---------------------------------------------------------------------------
# AC 2.2 -- la presence vient de `statut_de_liaison`, et d'elle seule
# ---------------------------------------------------------------------------

def test_la_presence_est_celle_de_statut_de_liaison_ET_ELLE_SEULE(tmp_path):
    """AC 2.2. Le fichier de `rush_01` **existe reellement** sur le disque et le
    verificateur pur dit qu'il n'existe pas : si le modele allait voir le disque
    de son cote pour ce diagnostic, il rendrait `lie` et ce test rougirait."""
    reel = tmp_path / "bien_la.mov"
    reel.write_bytes(b"0")
    document = manifeste([rush("rush_01", chemin=str(reel)),
                          rush("rush_02", fps=48.0, largeur=2048, hauteur=858,
                               chemin=str(reel))])

    liste = rushes.ListeDesRushes(rushes.rushes_du_manifeste(
        document, existe=existe_sauf(str(reel))))

    assert [r.presence for r in liste.rushes] == [rushes.LIBELLE_ABSENT,
                                                  rushes.LIBELLE_ABSENT]


@pytest.mark.parametrize("statut, libelle, etat", [
    (relink.LIE, rushes.LIBELLE_LIE, "complete"),
    (relink.DELINKE_CHEMIN_MORT, rushes.LIBELLE_ABSENT, "absent"),
    (relink.DELINKE_CHEMIN_ABSENT, rushes.LIBELLE_ABSENT, "absent"),
])
def test_les_TROIS_statuts_du_coeur_se_rendent_en_DEUX_presences(
        statut, libelle, etat):
    """AC 2.2 : `lie` -> « lié » (glyphe `complete`), **les deux** etats delies
    -> « absent » (glyphe `absent`). Les statuts sont lus du coeur, jamais
    recopies en litteral."""
    element = rushes.Rush(rush_id="r", statut=statut, fps_source=25.0,
                          largeur=1920, hauteur=1080, frames_source=6300)

    assert element.presence == libelle
    assert element.etat == etat
    assert element.marque_de_presence() == jetons.marque(etat, libelle)
    assert element.marque_de_presence(ascii_seul=True) == jetons.marque(
        etat, jetons.replier_ascii(libelle), ascii_seul=True)


def test_un_rush_SANS_source_path_est_absent_sans_toucher_au_disque():
    """`DELINKE_CHEMIN_ABSENT` : le manifeste ne porte aucun chemin. Le
    verificateur d'existence n'est **jamais** appele -- il n'y a rien a
    verifier."""
    appels = []

    def _espion(chemin):
        appels.append(chemin)
        return True

    document = manifeste([rush("rush_01", chemin="/rushes/rush_01.mov"),
                          rush("rush_nu", fps=48.0, chemin=None)])
    liste = rushes.ListeDesRushes(rushes.rushes_du_manifeste(
        document, existe=_espion))

    assert liste.viser("rush_nu").statut == relink.DELINKE_CHEMIN_ABSENT
    assert appels == ["/rushes/rush_01.mov"]


def test_le_resume_compte_les_LIES_et_les_INTROUVABLES(tmp_path):
    """La ligne d'etat de `E2-1`, verbatim de la maquette."""
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)

    assert liste.resume() == "3 rushes déclarés · 2 liés, 1 introuvable"


def test_le_resume_s_ACCORDE_au_singulier():
    """« jamais une ligne vide » vaut aussi pour un projet a un seul rush."""
    document = manifeste([rush("rush_01", chemin="/perdu/rush_01.mov")])
    liste = rushes.ListeDesRushes(rushes.rushes_du_manifeste(
        document, existe=existe_sauf("/perdu/rush_01.mov")))

    assert liste.resume() == "1 rush déclaré · 0 lié, 1 introuvable"


# ---------------------------------------------------------------------------
# AC 2.3 et 2.4 -- selectionnable, et le choisir ouvre le relink
# ---------------------------------------------------------------------------

def test_un_rush_ABSENT_est_SELECTIONNABLE_le_curseur_s_y_POSE(tmp_path):
    """AC 2.3 : « le curseur s'y pose, il ne saute pas ». L'absent est le
    **troisieme** : un curseur qui sauterait les absents s'arreterait au
    deuxieme, et rendrait `zz_rush_02`."""
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)

    liste.deplacer(1)
    liste.deplacer(1)

    assert liste.curseur == 2
    assert liste.courant.rush_id == "rush_hiver"
    assert liste.courant.lie is False


def test_le_curseur_se_pose_sur_un_absent_place_AU_MILIEU_de_la_liste(tmp_path):
    """AC 2.3, dans le regime que la fixture precedente ne couvre pas : l'absent
    y est **dernier**, si bien qu'un curseur qui sauterait les absents finirait
    quand meme par s'y arreter faute de suivant. Ici `rush_perdu_a` est au
    **milieu** : un seul `↓` doit s'y poser."""
    liste = rushes.lister(projet(tmp_path, manifeste_a_deux_absents()),
                          existe=EXISTE_SAUF_LES_DEUX)

    liste.deplacer(1)

    assert liste.curseur == 1
    assert liste.courant.rush_id == "rush_perdu_a"
    assert liste.courant.lie is False


def test_TOUS_les_rangs_sont_selectionnables_y_compris_les_absents(tmp_path):
    """Volet exhaustif de l'AC 2.3 : aucun rang n'est refuse."""
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)

    assert [liste.selectionnable(rang) for rang in range(3)] == [True] * 3


def test_viser_un_ABSENT_pose_bien_le_curseur_dessus(tmp_path):
    """`viser` sert le cablage clavier de l'ecran : il place le curseur, il ne
    rend pas seulement l'element."""
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)

    assert liste.viser("rush_hiver").rush_id == "rush_hiver"
    assert liste.curseur == 2


def test_CHOISIR_un_rush_ABSENT_ouvre_le_RELINK_et_n_extrait_RIEN(tmp_path):
    """AC 2.4, verbatim : « le choisir n'extrait rien -- il ouvre le relink »."""
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)
    liste.viser("rush_hiver")

    assert liste.action_du_choix() == rushes.ACTION_RELINK


def test_CHOISIR_un_rush_LIE_ouvre_l_EXTRACTION(tmp_path):
    """Le volet symetrique : sans lui, une action qui rendrait toujours
    `relink` passerait le test precedent sans rien mesurer."""
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)
    liste.viser("zz_rush_02")

    assert liste.action_du_choix() == rushes.ACTION_EXTRAIRE


def test_le_curseur_ne_sort_JAMAIS_de_la_liste(tmp_path):
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)

    liste.deplacer(-5)
    assert liste.curseur == 0
    liste.deplacer(99)
    assert liste.curseur == 2


def test_une_liste_VIDE_ne_rend_ni_courant_ni_action():
    """Un projet sans rush declare : l'ecran doit s'ouvrir, pas tomber."""
    liste = rushes.ListeDesRushes([])

    assert liste.courant is None
    assert liste.action_du_choix() is None
    assert liste.rush_a_relinker() is None
    assert liste.rendu() == []


# ---------------------------------------------------------------------------
# Le rendu -- « au moins un test confronte le TEXTE RENDU, ligne a ligne »
# ---------------------------------------------------------------------------

def test_le_TEXTE_RENDU_apparie_chaque_rush_a_SA_ligne(tmp_path):
    """Le corollaire mesure de la regle des fabriques : un test qui n'interroge
    que le modele ne voit **aucune** permutation du rendu. Les trois lignes sont
    confrontees une a une, curseur pose sur la troisieme."""
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)
    liste.viser("rush_hiver")

    lignes = liste.rendu()

    # Colonnes de `Q8` (`J2`, 2026-08-30) : le nom en 5 sur 19 colonnes, la
    # technique en 26 sur 32, la presence calee a droite en 60. La colonne
    # technique a gagne quatre colonnes sur celle du nom pour que la duree d'un
    # 4K long cesse d'etre rognee -- voir `rushes.COLONNE_TECHNIQUE`.
    assert lignes == [
        "     rush_01              25 fps · 1920×1080 · 4:12         ● lié",
        "     zz_rush_02           50 fps · 1280×720 · 12:38         ● lié",
        "   ▸ rush_hiver           24 fps · 4096×2160 · 2:05         ✕ absent",
    ]


def test_les_lignes_rendues_sont_celles_de_la_MAQUETTE_au_CARACTERE_PRES(
        tmp_path, racine_depot):
    """La maquette `E2-1` fait foi sur le texte **et sur les colonnes**.

    Sans cette confrontation, les quatre colonnes du module ne seraient qu'un
    calage plausible : ici elles sont confrontees a la source. `rush_01` et
    `rush_hiver` de la fixture portent exactement les valeurs de la maquette,
    et leurs deux lignes doivent en ressortir identiques.
    """
    maquette = (racine_depot / "_bmad-output" / "planning-artifacts"
                / "ux-designs" / "ux-tui-2026-08-27" / "maquettes"
                / "E2-1-extraction-rush.txt").read_text(encoding="utf-8")
    # Le contenu utile d'une ligne de maquette : le cadre et la marge otes de
    # chaque cote, il reste les 76 colonnes de `jetons.largeur_utile()`.
    contenu = [ligne[2:-2] for ligne in maquette.splitlines()
               if ligne.startswith("│")]
    attendues = [ligne.rstrip() for ligne in contenu
                 if "fps" in ligne and "●" in ligne or "✕ absent" in ligne]
    assert len(attendues) == 3, attendues

    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)
    liste.viser("rush_hiver")
    rendues = liste.rendu()

    assert rendues[0] == attendues[0]
    assert rendues[2] == attendues[2]


def test_le_rendu_tient_la_GRILLE_et_se_REPLIE_en_ASCII(tmp_path):
    """`EPIC11-ARB-21` : mesure en **colonnes**, jamais en `len()`, dans les
    deux regimes. Le repli ASCII precede la mesure."""
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)

    for ascii_seul in (False, True):
        for ligne in liste.rendu(ascii_seul=ascii_seul):
            assert jetons.colonnes(ligne) <= jetons.largeur_utile()
        if ascii_seul:
            for ligne in liste.rendu(ascii_seul=True):
                assert ligne.isascii(), ligne


def test_un_rush_id_TRES_LONG_est_abrege_AU_MILIEU_et_les_chiffres_survivent():
    """« Borner le nom, jamais les compteurs. » Deux rushes dont les identifiants
    ne different **qu'a la fin** doivent rester distincts a l'ecran."""
    document = manifeste(
        [rush("2026_08_29_tournage_exterieur_nuit_camera_A", fps=25.0),
         rush("2026_08_29_tournage_exterieur_nuit_camera_B", fps=50.0,
              largeur=1280, hauteur=720)],
        [lot("a", "2026_08_29_tournage_exterieur_nuit_camera_A", frames=6300),
         lot("b", "2026_08_29_tournage_exterieur_nuit_camera_B", frames=37900)])
    liste = rushes.ListeDesRushes(rushes.rushes_du_manifeste(
        document, existe=existe_sauf()))

    lignes = liste.rendu()

    assert lignes[0] != lignes[1]
    assert "25 fps · 1920×1080 · 4:12" in lignes[0]
    assert "50 fps · 1280×720 · 12:38" in lignes[1]
    assert jetons.points_d_abregement() in lignes[0]


def test_le_signe_MULTIPLIER_est_replie_par_le_module_et_non_par_replier_ascii():
    """**Le repli du signe de resolution vit dans la TABLE, pas ici.**

    Ce test a d'abord fige le defaut (`replier_ascii("×") == "?"`) pendant que
    le module repliait le signe lui-meme. Le correctif a ete porte a la source
    -- `jetons.REPLIS_DE_TEXTE` -- parce que quatre autres maquettes portent ce
    signe (`E4-1`, `E4-3`, `E5-1`, `E5-6`) : le repli local aurait laisse le
    defaut vivre pour trois ateliers. Le test mesure maintenant que ce module
    n'a **plus** de repli a lui, et que la table suffit.
    """
    assert jetons.replier_ascii(rushes.SIGNE_MULTIPLIER) == "x"
    assert not hasattr(rushes, "REPLI_DU_MULTIPLIER"), (
        "deux redactions du meme repli divergent : celle du module a ete "
        "retiree au profit de la table")

    element = rushes.Rush(rush_id="r", statut=relink.LIE, fps_source=25.0,
                          largeur=1920, hauteur=1080, frames_source=6300)

    assert element.technique(ascii_seul=True) == "25 fps · 1920x1080 · 4:12".replace(
        "·", ".")
    assert "?" not in element.technique(ascii_seul=True)


@pytest.mark.parametrize("frames, fps, attendu", [
    (6300, 25.0, "4:12"),
    (3012, 24.0, "2:05"),
    (37900, 50.0, "12:38"),
    (1, 25.0, "0:01"),          # jamais `0:00` pour un rush qui existe
    (90000, 25.0, "1:00:00"),   # au-dela de l'heure, la forme s'allonge
    (0, 25.0, None),
    (6300, 0, None),
    (6300, None, None),
    (None, 25.0, None),
])
def test_la_duree_LISIBLE_couvre_ses_bornes(frames, fps, attendu):
    assert rushes.duree_de_rush(frames, fps) == attendu


@pytest.mark.parametrize("secondes, attendu", [
    (252.0, "4:12"),
    (125.5, "2:05"),          # la seconde entamee n'est pas comptee
    (758.9, "12:38"),
    (0.04, "0:01"),           # jamais `0:00` pour un rush qui existe
    (3600.0, "1:00:00"),      # au-dela de l'heure, la forme s'allonge
    (0.0, None),
    (-3.0, None),             # une duree negative est une donnee fausse
    (None, None),
])
def test_la_duree_DE_SECONDES_couvre_les_MEMES_bornes(secondes, attendu):
    """Le second appelant de la mise en forme, mesure a part.

    `duree_lisible_de_secondes` est **extraite** de `duree_de_rush` le
    2026-09-05 pour que `E2-1i` rende `4:12` quand le cardinal manque. Les deux
    bornes qui portent une convention -- la seconde entamee non comptee et le
    plancher d'une seconde -- sont donc mesurees des DEUX cotes : la
    parametrisation voisine passe par une division, celle-ci par la duree que
    le conteneur declare, et un plancher retire ne se verrait pas dans l'une
    si l'autre ne le tenait pas.

    La duree **negative** n'a pas d'equivalent chez la voisine (un cardinal
    negatif est filtre plus tot) : elle est ici parce que ce chemin-ci recoit
    une valeur de probe brute, et qu'un conteneur peut declarer n'importe quoi.
    """
    assert rushes.duree_lisible_de_secondes(secondes) == attendu


# ---------------------------------------------------------------------------
# AC 4.1 -- les deux modes, et ce que l'ecran cablera sur l'explorateur
# ---------------------------------------------------------------------------

def test_les_DEUX_modes_de_relink_et_leur_touche():
    """AC 4.1 : `r` retrouver, `d` designer. Les deux modes, et **deux
    seulement** -- le relink en masse n'existe pas (`EPIC11-ARB-32`)."""
    assert rushes.MODES == (rushes.MODE_RETROUVER, rushes.MODE_DESIGNER)
    assert rushes.TOUCHES_DE_MODE == {"r": rushes.MODE_RETROUVER,
                                      "d": rushes.MODE_DESIGNER}


def test_chercher_montre_les_DOSSIERS_designer_montre_les_FICHIERS():
    """AC 4.1 : `montrer_fichiers=False` pour `r`, `True` pour `d`. Les deux
    valeurs different -- une table uniforme ne mesurerait rien."""
    assert rushes.MONTRER_FICHIERS[rushes.MODE_RETROUVER] is False
    assert rushes.MONTRER_FICHIERS[rushes.MODE_DESIGNER] is True


def test_les_titres_et_le_bandeau_des_deux_modes_sont_ceux_des_MAQUETTES():
    """`E2-1b` et `E2-1c` font foi sur le texte."""
    assert rushes.titre_de_relink("rush_hiver", rushes.MODE_RETROUVER) == \
        "Où chercher rush_hiver ?"
    assert rushes.titre_de_relink("rush_hiver", rushes.MODE_DESIGNER) == \
        "Quel fichier est rush_hiver ?"
    assert rushes.bandeau_de_relink("rush_hiver", rushes.MODE_RETROUVER) == \
        "rush_hiver · retrouver"
    assert rushes.bandeau_de_relink("rush_hiver", rushes.MODE_DESIGNER) == \
        "rush_hiver · désigner"


def test_un_mode_INCONNU_est_refuse_a_l_appel():
    """Un mode invente est une faute de cablage, pas un refus d'operateur : il
    leve, il ne rend pas un refus nomme."""
    with pytest.raises(ValueError):
        rushes.titre_de_relink("rush_hiver", "relink-en-masse")


def test_le_bloc_de_relink_de_E2_1_porte_les_DEUX_modes_et_leur_phrase(tmp_path):
    """Le bloc que `E2-1` ouvre sous un rush absent, verbatim de la maquette."""
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)
    liste.viser("rush_hiver")

    assert liste.titre_du_relink() == \
        "rush_hiver — déclaré au manifest, introuvable"
    assert rushes.lignes_des_modes() == [
        ("r", "Retrouver le fichier",
         "chercher dans un dossier, par nom, durée et timecode de départ"),
        ("d", "Le désigner à la main", "choisir le fichier, sans recherche"),
    ]


def test_un_rush_LIE_n_ouvre_AUCUN_bloc_de_relink(tmp_path):
    """Volet symetrique du precedent : le bloc n'apparait que sur un absent."""
    liste = rushes.lister(projet(tmp_path), existe=EXISTE_SAUF_HIVER)
    liste.viser("rush_01")

    assert liste.titre_du_relink() is None


# ---------------------------------------------------------------------------
# AC 4.2 -- la sequence de `cli.relink_command`, refaite sans importer `cli`
# ---------------------------------------------------------------------------

def test_le_relink_par_DESIGNATION_ecrit_le_chemin_RESOLU_du_rush_vise(tmp_path):
    """La sequence de `cli.relink_command`, mode `--video` : verifier la
    designation, resoudre le chemin, appliquer, puis persister."""
    dossier = projet(tmp_path)
    video = tmp_path / "retrouve" / "rush_hiver.mov"
    video.parent.mkdir()
    video.write_bytes(b"0")

    apercu = rushes.preparer_relink(dossier, rush_id="rush_hiver",
                                    mode=rushes.MODE_DESIGNER, cible=video,
                                    probe=probe_conforme)
    assert apercu.valide
    rushes.ecrire_le_relink(dossier, apercu)

    ecrit = json.loads(
        (dossier / extraction_manifest.MANIFEST_FILENAME).read_text("utf-8"))
    chemins = {r["rush_id"]: r.get("source_path") for r in ecrit["rushes"]}
    assert chemins["rush_hiver"] == str(video.resolve())
    assert chemins["rush_01"] == "/rushes/rush_01.mov"
    assert chemins["zz_rush_02"] == "/rushes/zz_rush_02.mov"


def test_le_relink_par_RECHERCHE_passe_par_rechercher_candidat(tmp_path):
    """Mode `--chercher` : la recherche recursive du coeur, jamais une
    reimplantation cote TUI."""
    dossier = projet(tmp_path)
    arbre = tmp_path / "rushes_2026" / "03_tournage_mai" / "hd"
    arbre.mkdir(parents=True)
    (arbre / "rush_hiver.mov").write_bytes(b"0")
    (arbre / "rush_printemps.mov").write_bytes(b"0")

    apercu = rushes.preparer_relink(dossier, rush_id="rush_hiver",
                                    mode=rushes.MODE_RETROUVER,
                                    cible=tmp_path / "rushes_2026",
                                    probe=probe_conforme)
    rushes.ecrire_le_relink(dossier, apercu)

    ecrit = json.loads(
        (dossier / extraction_manifest.MANIFEST_FILENAME).read_text("utf-8"))
    trouve = {r["rush_id"]: r.get("source_path") for r in ecrit["rushes"]}
    assert trouve["rush_hiver"] == str((arbre / "rush_hiver.mov").resolve())


def test_le_relink_ne_touche_a_RIEN_D_AUTRE_dans_le_manifeste(tmp_path):
    """`appliquer_relink` est une copie **pure** qui « ne touche a rien
    d'autre » : tout le reste du document doit etre identique octet a octet."""
    dossier = projet(tmp_path)
    avant = json.loads(
        (dossier / extraction_manifest.MANIFEST_FILENAME).read_text("utf-8"))
    video = tmp_path / "rush_hiver.mov"
    video.write_bytes(b"0")

    apercu = rushes.preparer_relink(dossier, rush_id="rush_hiver",
                                    mode=rushes.MODE_DESIGNER, cible=video,
                                    probe=probe_conforme)
    rushes.ecrire_le_relink(dossier, apercu)
    apres = json.loads(
        (dossier / extraction_manifest.MANIFEST_FILENAME).read_text("utf-8"))

    for document in (avant, apres):
        for entree in document["rushes"]:
            entree.pop("source_path", None)
    assert avant == apres


def test_les_AVERTISSEMENTS_du_coeur_traversent_sans_etre_reecrits(tmp_path):
    """Un manifeste sans aucune reference d'identite : le coeur accepte la
    designation « sur l'autorite de l'operateur » et rend un avertissement.
    Il est **transporte**, pas paraphrase."""
    document = manifeste([rush("rush_01", chemin="/rushes/rush_01.mov"),
                          rush("rush_nu", nom="", timecode=None,
                               chemin="/perdu/rush_nu.mov")])
    document["rushes"][1].pop("source_name")
    dossier = projet(tmp_path, document)
    video = tmp_path / "quelconque.mov"
    video.write_bytes(b"0")

    apercu = rushes.preparer_relink(dossier, rush_id="rush_nu",
                                    mode=rushes.MODE_DESIGNER, cible=video,
                                    probe=probe_conforme)

    assert apercu.valide
    assert len(apercu.avertissements) == 1
    assert "autorite de l'operateur" in apercu.avertissements[0]


def test_le_module_n_appelle_JAMAIS_cli_py():
    """AC 4.2, interdit dur (`palier_projet.py:9-12`). Mesure a l'**AST**, pas
    au texte : le docstring du module explique justement pourquoi il ne le fait
    pas, et un grep y mordrait."""
    noms = identifiants(Path(rushes.__file__))
    fautifs = [n for n in noms if n == "cli" or n.endswith(".cli")]

    assert fautifs == [], fautifs


def test_la_garde_de_frontiere_cli_MORD(tmp_path):
    """Volet symetrique : la meme mesure appliquee a un module qui **viole** la
    regle doit rougir. Sans lui, la garde pourrait ne rien regarder."""
    fautif = tmp_path / "module_fautif.py"
    fautif.write_text(
        "from mixed_media_utility import cli\n"
        "def relink(args):\n"
        "    return cli.relink_command(args)\n", encoding="utf-8")

    noms = identifiants(fautif)

    assert [n for n in noms if n == "cli" or n.endswith(".cli")] != []


def test_l_APPARIEMENT_reste_dans_le_COEUR_et_la_TUI_n_en_porte_AUCUNE_moitie():
    """`EPIC11-ARB-32`, verbatim : « la TUI qui bouclerait elle-meme sur les
    rushes manquants reimplanterait dans l'interface la logique d'appariement
    (nom, duree, timecode) que `relink` porte deja ».

    Mesure : **aucune** chaine litterale du module n'est l'un des trois criteres
    d'identite. Les criteres sont lus du coeur, jamais recopies ici.
    """
    textes = set(chaines_de_code(Path(rushes.__file__)))
    fautifs = sorted(textes & set(relink.CRITERES_IDENTITE_RELINK))

    assert fautifs == [], fautifs


def test_la_garde_d_APPARIEMENT_MORD(tmp_path):
    """Volet symetrique de la frontiere precedente."""
    fautif = tmp_path / "apparieur_fautif.py"
    fautif.write_text(
        "def apparier(rush, probe):\n"
        "    return rush['source_frame_count'] == probe.cardinal_frames\n",
        encoding="utf-8")

    textes = set(chaines_de_code(fautif))

    assert sorted(textes & set(relink.CRITERES_IDENTITE_RELINK)) == [
        "source_frame_count"]


# ---------------------------------------------------------------------------
# AC 4.3 -- les codes de refus, rendus PAR LEUR CODE
# ---------------------------------------------------------------------------

def test_TOUS_les_codes_de_refus_du_COEUR_sont_connus_du_module():
    """AC 4.3. La table est **lue** de `relink.__all__`, jamais recopiee : un
    code ajoute au coeur entre automatiquement, un code renomme ne diverge
    pas."""
    du_coeur = {getattr(relink, nom) for nom in relink.__all__
                if nom.startswith("REFUS_")}

    assert du_coeur, "la lecture du coeur doit trouver des codes"
    assert set(rushes.CODES_DE_REFUS_DU_COEUR) == du_coeur
    assert du_coeur <= set(rushes.CODES_DE_REFUS)


@pytest.mark.parametrize("code", sorted(
    {getattr(relink, nom) for nom in relink.__all__ if nom.startswith("REFUS_")}))
def test_chaque_code_de_refus_est_rendu_PAR_SON_CODE(code):
    """AC 4.3, verbatim : « rendus **par leur code**, jamais par une phrase
    inventee ». Le code apparait tel quel dans le titre du cartouche **et** dans
    la ligne d'etat."""
    refus = rushes.Refus(code=code, message="peu importe le message du coeur")

    assert refus.titre() == f"{jetons.GLYPHES['absent']} {code}"
    assert refus.ligne_d_etat().startswith(
        f"{jetons.GLYPHES['absent']}  {code} · ")
    assert refus.ligne_d_etat().endswith(rushes.MANIFESTE_INCHANGE)


def test_un_refus_REEL_du_coeur_traverse_avec_SON_code_et_SON_message(tmp_path):
    """Bout en bout : trois fichiers satisfont les trois criteres, le coeur
    refuse de choisir, et c'est **son** code qui remonte."""
    dossier = projet(tmp_path)
    arbre = tmp_path / "rushes_2026"
    for sous in ("hd", "proxy", "archive"):
        (arbre / sous).mkdir(parents=True)
        (arbre / sous / "rush_hiver.mov").write_bytes(b"0")

    apercu = rushes.preparer_relink(dossier, rush_id="rush_hiver",
                                    mode=rushes.MODE_RETROUVER, cible=arbre,
                                    probe=probe_conforme)

    assert apercu.valide is False
    assert apercu.refus.code == relink.REFUS_CANDIDATS_MULTIPLES
    assert "rush_hiver.mov" in apercu.refus.message
    assert relink.REFUS_CANDIDATS_MULTIPLES in apercu.refus.titre()


def test_le_message_du_coeur_n_est_JAMAIS_reecrit(tmp_path):
    """Le message qui accompagne le code est celui de l'exception du coeur, mot
    pour mot -- une paraphrase divergerait au premier ajustement du coeur."""
    dossier = projet(tmp_path)

    apercu = rushes.preparer_relink(dossier, rush_id="rush_inexistant",
                                    mode=rushes.MODE_RETROUVER,
                                    cible=tmp_path, probe=probe_conforme)

    attendu = None
    try:
        relink.resoudre_rush_id(manifeste_de_reference(), "rush_inexistant")
    except relink.RelinkError as exc:
        attendu = str(exc)
    assert apercu.refus.code == relink.REFUS_RUSH_INCONNU
    assert apercu.refus.message == attendu


def test_les_deux_refus_PROPRES_a_la_TUI_sont_nommes_et_distincts(tmp_path):
    """`cli.relink_command` traite deux pannes **avant** d'entrer dans
    `relink` -- manifeste absent, manifeste illisible -- et le coeur n'a pas de
    code pour elles. La TUI les nomme plutot que de rendre une phrase."""
    vide = tmp_path / "sans_projet"
    vide.mkdir()
    absent = rushes.preparer_relink(vide, rush_id="rush_hiver",
                                    mode=rushes.MODE_RETROUVER, cible=tmp_path,
                                    probe=probe_conforme)

    casse = tmp_path / "projet_casse"
    casse.mkdir()
    (casse / extraction_manifest.MANIFEST_FILENAME).write_text("{ pas du json",
                                                               encoding="utf-8")
    illisible = rushes.preparer_relink(casse, rush_id="rush_hiver",
                                       mode=rushes.MODE_RETROUVER,
                                       cible=tmp_path, probe=probe_conforme)

    assert absent.refus.code == rushes.REFUS_MANIFESTE_ABSENT
    assert illisible.refus.code == rushes.REFUS_MANIFESTE_ILLISIBLE
    assert absent.refus.code != illisible.refus.code
    assert rushes.REFUS_MANIFESTE_ABSENT not in rushes.CODES_DE_REFUS_DU_COEUR


def test_les_issues_du_refus_de_E2_1d_sont_TROIS_et_aucune_n_ECRIT():
    """`E2-1d` : trois sorties, aucune preselectionnee (`EPIC11-ARB-7`), aucune
    qui ecrive -- un refus est un point de jugement, pas un couloir."""
    choix = rushes.issues_apres_refus()

    assert [issue.cle for issue in choix.issues] == [
        rushes.MODE_DESIGNER, rushes.MODE_RETROUVER, rushes.ISSUE_REVENIR]
    assert choix.retenue is None
    assert [issue.ecrit for issue in choix.issues] == [False, False, False]


def test_le_cartouche_de_refus_REPLIE_le_message_sans_rien_perdre():
    """Un message long du coeur tient dans le cartouche, et **rien** n'en est
    perdu : c'est ce que `E2-1d` montre sur trois lignes."""
    message = ("Plusieurs candidats satisfont les trois criteres d'identite, "
               "choix impossible sans arbitrage: ['a.mov', 'b.mov', 'c.mov'].")
    refus = rushes.Refus(code=relink.REFUS_CANDIDATS_MULTIPLES, message=message)

    lignes = refus.lignes()

    assert lignes[0] == refus.titre()
    assert len(lignes) > 2
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= jetons.largeur_de_cartouche()
    recolle = " ".join(lignes[2:]).split()
    assert recolle == message.split()


# ---------------------------------------------------------------------------
# AC 4.4 -- UN SEUL rush par validation
# ---------------------------------------------------------------------------

def test_le_relink_ne_traite_QU_UN_rush_par_validation_MEME_avec_DEUX_absents(
        tmp_path):
    """`EPIC11-ARB-32`, verbatim : « **le relink en masse n'existe pas** ».

    **Deux** rushes absents, et la cible est le **second** (`rush_hiver`,
    troisieme de la liste). Un relink qui traiterait « le premier absent »
    viserait `rush_perdu_a` : c'est le mutant `M25` de la story 5.7, ou
    `_find_lot` rendait le premier lot et 257 tests restaient verts.
    """
    dossier = projet(tmp_path, manifeste_a_deux_absents())
    liste = rushes.lister(dossier, existe=EXISTE_SAUF_LES_DEUX)
    liste.viser("rush_hiver")
    assert [r.rush_id for r in liste.absents] == ["rush_perdu_a", "rush_hiver"]

    vise = liste.rush_a_relinker()
    video = tmp_path / "rush_hiver.mov"
    video.write_bytes(b"0")
    apercu = rushes.preparer_relink(dossier, rush_id=vise.rush_id,
                                    mode=rushes.MODE_DESIGNER, cible=video,
                                    probe=probe_conforme)
    rushes.ecrire_le_relink(dossier, apercu)

    ecrit = json.loads(
        (dossier / extraction_manifest.MANIFEST_FILENAME).read_text("utf-8"))
    chemins = {r["rush_id"]: r.get("source_path") for r in ecrit["rushes"]}
    assert vise.rush_id == "rush_hiver"
    assert apercu.rush_id == "rush_hiver"
    assert chemins["rush_hiver"] == str(video.resolve())
    # L'AUTRE absent n'a pas bouge : une passe en masse l'aurait relinke aussi.
    assert chemins["rush_perdu_a"] == "/perdu/rush_perdu_a.mov"
    assert chemins["rush_01"] == "/rushes/rush_01.mov"


def test_le_rush_a_relinker_est_celui_SOUS_LE_CURSEUR_pas_le_premier_absent(
        tmp_path):
    """Le meme piege, mesure sur le modele seul : le curseur est sur le
    **second** absent."""
    liste = rushes.lister(projet(tmp_path, manifeste_a_deux_absents()),
                          existe=EXISTE_SAUF_LES_DEUX)
    liste.viser("rush_hiver")

    assert liste.rush_a_relinker().rush_id == "rush_hiver"
    assert liste.absents[0].rush_id == "rush_perdu_a"


def test_un_rush_LIE_sous_le_curseur_n_a_RIEN_a_relinker(tmp_path):
    """Volet symetrique : sans lui, une methode qui rendrait toujours le rush
    courant passerait le test precedent."""
    liste = rushes.lister(projet(tmp_path, manifeste_a_deux_absents()),
                          existe=EXISTE_SAUF_LES_DEUX)
    liste.viser("rush_01")

    assert liste.rush_a_relinker() is None


def test_preparer_le_relink_ne_prend_QU_UN_rush_id():
    """La signature elle-meme interdit le relink en masse : `rush_id` est un
    scalaire, et il n'y a **aucun** parametre de liste, de lot ou de selection.
    Un `rush_ids=` ajoute ici serait le relink en masse d'`EPIC11-ARB-32`."""
    import inspect

    parametres = list(inspect.signature(rushes.preparer_relink).parameters)

    assert parametres == ["dossier_projet", "rush_id", "mode", "cible", "probe"]


# ---------------------------------------------------------------------------
# AC 4.5 -- rien n'est ecrit tant que le relink n'est pas valide
# ---------------------------------------------------------------------------

def test_preparer_le_relink_N_ECRIT_RIEN_sur_le_disque(tmp_path):
    """AC 4.5, et `EPIC11-ARB-4` : « le panneau chiffre precede toute
    ecriture ». Le `project.json` est compare **octet a octet** avant et apres
    la preparation, et le dossier ne porte aucun temporaire."""
    dossier = projet(tmp_path)
    chemin = dossier / extraction_manifest.MANIFEST_FILENAME
    avant = chemin.read_bytes()
    video = tmp_path / "rush_hiver.mov"
    video.write_bytes(b"0")

    apercu = rushes.preparer_relink(dossier, rush_id="rush_hiver",
                                    mode=rushes.MODE_DESIGNER, cible=video,
                                    probe=probe_conforme)

    assert apercu.valide
    assert apercu.manifeste is not None
    assert chemin.read_bytes() == avant
    assert sorted(p.name for p in dossier.iterdir()) == [chemin.name]


def test_l_apercu_porte_DEJA_le_chemin_qui_sera_ecrit(tmp_path):
    """L'apercu et l'ecriture derivent de la **meme** valeur : un apercu
    recalcule au moment d'ecrire pourrait mentir."""
    dossier = projet(tmp_path)
    video = tmp_path / "rush_hiver.mov"
    video.write_bytes(b"0")

    apercu = rushes.preparer_relink(dossier, rush_id="rush_hiver",
                                    mode=rushes.MODE_DESIGNER, cible=video,
                                    probe=probe_conforme)
    rushes.ecrire_le_relink(dossier, apercu)

    ecrit = json.loads(
        (dossier / extraction_manifest.MANIFEST_FILENAME).read_text("utf-8"))
    vise = [r for r in ecrit["rushes"] if r["rush_id"] == "rush_hiver"][0]
    assert apercu.chemin == vise["source_path"]


def test_un_apercu_REFUSE_ne_peut_PAS_etre_ecrit(tmp_path):
    """AC 4.5 par le type : ecrire depuis un apercu refuse est **impossible**,
    pas seulement improbable. Et le manifeste reste intact."""
    dossier = projet(tmp_path)
    chemin = dossier / extraction_manifest.MANIFEST_FILENAME
    avant = chemin.read_bytes()

    apercu = rushes.preparer_relink(dossier, rush_id="rush_inexistant",
                                    mode=rushes.MODE_RETROUVER, cible=tmp_path,
                                    probe=probe_conforme)

    with pytest.raises(rushes.EcritureRefusee):
        rushes.ecrire_le_relink(dossier, apercu)
    assert chemin.read_bytes() == avant


def test_le_manifeste_ECRIT_est_VALIDE_par_le_coeur(tmp_path):
    """`_atomic_write` valide avant de remplacer : un manifeste invalide laisse
    le precedent **strictement intact** et ne laisse aucun temporaire."""
    dossier = projet(tmp_path)
    chemin = dossier / extraction_manifest.MANIFEST_FILENAME
    avant = chemin.read_bytes()
    video = tmp_path / "rush_hiver.mov"
    video.write_bytes(b"0")

    apercu = rushes.preparer_relink(dossier, rush_id="rush_hiver",
                                    mode=rushes.MODE_DESIGNER, cible=video,
                                    probe=probe_conforme)
    apercu.manifeste.pop("schema_version")

    with pytest.raises(Exception):
        rushes.ecrire_le_relink(dossier, apercu)
    assert chemin.read_bytes() == avant
    assert sorted(p.name for p in dossier.iterdir()) == [chemin.name]


def test_le_resume_de_REFERENCE_de_E2_1b_vient_du_coeur(tmp_path):
    """La ligne d'etat de `E2-1b` : « rush_hiver : 3 012 frames · TC
    00:00:00:00 ». Les deux chiffres sont ceux de `charger_reference`."""
    reference = relink.charger_reference(manifeste_de_reference(), "rush_hiver")

    assert rushes.resume_de_reference(reference) == \
        "rush_hiver : 3 012 frames · TC 00:00:00:00"


def test_le_resume_de_REFERENCE_dit_ce_qu_il_ne_SAIT_PAS():
    """Un manifeste sans reference d'identite : le resume le dit plutot que
    d'afficher un zero qui serait faux."""
    document = manifeste([rush("rush_01"), rush("rush_nu", timecode=None)])
    document["rushes"][1].pop("source_name")
    reference = relink.charger_reference(document, "rush_nu")

    inconnu = jetons.GLYPHES["neutre"]

    assert rushes.resume_de_reference(reference) == \
        f"rush_nu : {inconnu} frames · TC {inconnu}"
