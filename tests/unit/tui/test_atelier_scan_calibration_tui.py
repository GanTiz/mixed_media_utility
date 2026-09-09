# -*- coding: utf-8 -*-
"""Story 11.6, lot C -- `E3-5`, le choix du profil (AC 3).

**Ce banc et lui seul mesure le lot C.** La regle de decoupage de la fiche est
stricte, et elle a ete payee trois fois sur ce depot : « aucun lot ne partage un
fichier de banc avec un autre ». `git add -N` et `git commit -- <chemins>`
protegent par FICHIER, jamais a l'interieur d'un fichier -- le commit `82e64de`
du 2026-08-30 a embarque ~200 lignes du lot voisin sous un message qui parlait
d'autre chose, alors que les deux agents appliquaient la regle a la lettre.

**Regle des fabriques** (`CLAUDE.md`), appliquee ici a ses trois points :

1. **au moins deux elements DISTINGUABLES** -- les trois profils de
   :func:`_projet` different par leur `chain_id`, leur nom de fichier designe,
   leur date de pose, leur cardinal de pastilles **et** leur divergence. Un
   remplissage uniforme rendrait toute permutation invisible, et c'est le mutant
   `M33` de la story 5.6 ;
2. **la cible n'est pas en premiere position** -- un `find` fautif qui rend le
   premier profil se demasque (mutant `M25`, story 5.7) ;
3. **trois elements et la cible AU MILIEU des qu'une boucle compte** -- la liste
   des profils est parcourue par `entrees_du_projet`, et un `continue` devenu
   `break` y ferait disparaitre les suivants sans un mot (mutant de la 11.4b,
   paye trois fois).

**Et la position se verifie sur la liste que le CODE parcourt.** Ce piege a ete
paye deux fois : la liste ecrite par la fabrique n'est PAS celle que le code
lit. `profile_designation._upsert` **trie le registre par `chain_id`** a
l'ecriture, donc l'ordre d'appel de la fabrique ne decide de rien. Les trois
`chain_id` sont choisis pour que la cible -- `600-tiff-…` -- soit au milieu de
`designated_profiles()`, et :func:`test_C5_la_cible_est_au_MILIEU_de_la_liste_que_le_code_parcourt`
le **mesure sur cette liste-la** plutot que sur la fabrique.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io import calibration_profile, profile_designation
from mixed_media_utility.tui import atelier_scan, jetons
from mixed_media_utility.tui import atelier_scan_calibration as calib
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.ecran_projet import CoutureExplorateur

#: Les deux regimes, portes par tout test qui touche au rendu. « Ne jamais
#: ajuster un test au code : tout test parametre porte les deux regimes. »
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Les trois profils de la fabrique, **distinguables sur sept axes** et ranges
#: ici dans l'ordre ou `_upsert` les triera. La cible est le second des trois.
#:
#: Le `chain_id` suit la forme que `scan_chain.derive_chain_id` compose --
#: `<dpi>-<format>-<condensat de 12 hexa>` -- parce que c'est la seule dont
#: `atelier_scan_calibration.dpi_du_profil` lit le dpi. Un identifiant hors
#: forme est mesure a part (voir le test du dpi).
#:
#: **`label` et `comment` sont les deux axes ajoutes le 2026-09-01** (correction
#: d'Egan sur la ligne « Chaîne »). Trois exigences les gouvernent, et chacune
#: ferme un mutant :
#:
#: 1. **aucune etiquette ne ressemble a son `chain_id`** -- une carte qui
#:    afficherait encore l'identite derivee passerait inapercue si les deux se
#:    ressemblaient, et c'est precisement la valeur que la correction retire ;
#: 2. **les trois etiquettes sont distinctes, et leurs slugs aussi** -- deux
#:    etiquettes de meme slug feraient un seul fichier (`EPIC5-ARB-99`), donc une
#:    fabrique qui mesurerait autre chose que ce qu'elle croit ;
#: 3. **le premier profil n'a AUCUN commentaire** -- c'est le volet d'omission :
#:    la ligne ne doit pas se terminer par un ` · ` orphelin. Un remplissage
#:    uniforme des trois commentaires ne l'aurait jamais montre.
PROFILS = (
    {"chain_id": "300-tiff-aaaaaaaaaaaa", "source": "profil-alpha.json",
     "patchs": 12, "avant": 3.4, "date": "2026-08-04T08:00:00Z",
     "label": "HP Envy 4520 salon", "comment": ""},
    {"chain_id": "600-tiff-bbbbbbbbbbbb", "source": "profil-beta.json",
     "patchs": 24, "avant": 2.1, "date": "2026-08-12T09:30:00Z",
     "label": "HP Envy 4520 atelier",
     "comment": "passe du 12/08, vitre nettoyée"},
    {"chain_id": "900-png-cccccccccccc", "source": "profil-gamma.json",
     "patchs": 18, "avant": 1.2, "date": "2026-08-14T17:45:00Z",
     "label": "Epson V600 archives", "comment": "après changement de lampe"},
)

#: Le rang de la cible : **le second des trois**. Ni le premier (mutant « rendre
#: le premier »), ni le dernier (mutant `continue` -> `break`).
RANG_DE_LA_CIBLE = 1

#: Le dpi que le scan declare dans les tests d'ecart. Il differe de celui de la
#: cible (600), et c'est ce que l'AC 3.7 mesure.
DPI_DU_SCAN_DIVERGENT = 300


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def _document(chain_id: str, *, patchs: int, avant: float | None,
              label: str = "", comment: str = "") -> dict:
    """Un document de profil **valide au sens du coeur**, jamais un mock.

    Il passe par `calibration_profile.validate_profile_document` a l'ecriture :
    un document fabrique a la main qui ne passerait pas cette porte mesurerait
    un ecran qui ne verra jamais ce document en production.

    ``avant`` a `None` produit un profil **sans acceptation** -- c'est ce
    qu'ecrit `_acceptance_document(None)`, et c'est le regime ou la divergence
    doit etre **omise** (AC 3.6).
    """
    document = {
        "schema_version": calibration_profile.PROFILE_SCHEMA_VERSION,
        "chain_id": chain_id,
        "correction_form_id": calibration_profile.CORRECTION_FORM_AFFINE_ID,
        "coefficients": {
            "stage_a": [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]],
            "stage_m": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        },
        "read_patch_count": patchs + 2,
        "retained_patch_count": patchs,
        "ink_floor_excluded": True,
        "source_page_id": f"page-{chain_id}",
        "template_id": "tpl-de-banc",
        "acceptance": {},
        # **Les deux champs sont poses meme vides**, parce que c'est ce que
        # `validate_profile_document` en fait (« `label` et `comment` y figurent
        # avec la chaine vide pour defaut »). Un profil ANCIEN, qui ne les porte
        # pas du tout, est mesure a part -- c'est le repli nomme de la ligne.
        calibration_profile.LABEL_FIELD: label,
        calibration_profile.COMMENT_FIELD: comment,
    }
    if avant is not None:
        document["acceptance"] = {
            "status": "accepted", "acceptance_id": "color-acceptance-1",
            "mean_delta_e": 1.0, "max_delta_e": 2.0,
            "mean_delta_e_before": avant,
            "distortion_budget_id": "distortion-budget-1",
            "mean_degradation_de76": 0.1,
            "max_neutral_degradation_de76": None,
            "max_degradation_de76": None, "distortion_budget_met": True,
            "neutral_axis_channel_spread_8bit": None,
        }
    return document


def _projet(tmp_path, *, profils=PROFILS, rang_du_defaut: int | None = None,
            nom="projet_demo") -> Path:
    """Un projet reel, avec ses profils ecrits **par le coeur** et inscrits.

    `write_profile` puis `record_designated_profile` plutot que
    `import_designated_profile` : le second n'accepte pas `designated_at`, et
    trois profils poses a la meme seconde ne seraient pas distinguables par leur
    date -- ce qui est exactement le remplissage uniforme que la regle des
    fabriques interdit.
    """
    chemin = creer_projet(tmp_path, nom).chemin
    for rang, profil in enumerate(profils):
        document = _document(profil["chain_id"], patchs=profil["patchs"],
                             avant=profil.get("avant"),
                             label=profil.get("label", ""),
                             comment=profil.get("comment", ""))
        fichier = calibration_profile.write_profile(chemin, document)
        profile_designation.record_designated_profile(
            chemin, document, project_path=fichier, source=profil["source"],
            as_default=(rang == rang_du_defaut),
            designated_at=profil["date"])
    return chemin


def _app(ecran, projet="projet_demo", **kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                    contexte=Contexte(projet=projet), **kwargs)


def _monte(app, scenario, banc):
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def _texte(ecran) -> str:
    """Le texte **tel qu'il s'affiche**, balises de couleur retirees."""
    return jetons.texte_affiche(str(ecran._corps.content))


def _ecran(tmp_path, banc, *, retenues=None, **kwargs):
    """Monter `E3-5` sur un projet, et rendre `(ecran, rappel)`.

    `retenir` est **requis** : l'oubli du cablage est une erreur d'appel, pas un
    silence (finding `K3`). Le banc lui donne une liste qui collecte.
    """
    prises = [] if retenues is None else retenues
    ecran = calib.EcranChoixDeCalibration(retenir=prises.append, **kwargs)
    return ecran, prises


def _rendu(ecran, banc, app=None, **kwargs) -> str:
    async def scenario(_pilote):
        return _texte(ecran)

    return _monte(app or _app(ecran, **kwargs), scenario, banc)


def _lignes_utiles(rendu: str) -> list[str]:
    return rendu.splitlines()


# ===========================================================================
# C1 -- la liste LUE du projet, la fleche seule, le curseur sur le defaut
# ===========================================================================

def test_C1_la_liste_est_LUE_du_registre_et_dans_SON_ordre(tmp_path):
    """AC 3.1 : `designated_profiles` et rien d'autre, **sans retri**.

    L'ensemble est mesure **exactement** : « une assertion positive laisse
    passer toute divergence supplementaire ». Une quatrieme entree qui
    entrerait -- un profil balaye depuis `versions/calibration/`, par exemple --
    ferait rougir ici, ce qu'un `in` n'aurait pas fait.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    entrees = calib.entrees_du_projet(projet)

    assert [e.cle for e in entrees] == [
        f"{calib.PREFIXE_DE_PROFIL}0", f"{calib.PREFIXE_DE_PROFIL}1",
        f"{calib.PREFIXE_DE_PROFIL}2",
        calib.CLE_AUTRE_FICHIER, calib.CLE_AUCUNE]
    # L'ordre est celui du registre, que `_upsert` trie par `chain_id`.
    lus = profile_designation.designated_profiles(projet)
    assert [e.entree["chain_id"] for e in entrees if e.est_un_profil] == [
        entree["chain_id"] for entree in lus]
    assert [e.nom for e in entrees] == [
        "profil-alpha.json", "profil-beta.json", "profil-gamma.json",
        calib.LIBELLE_AUTRE_FICHIER, calib.LIBELLE_AUCUNE]


def test_C1_le_curseur_part_sur_le_profil_par_DEFAUT_du_projet(tmp_path):
    """AC 3.2 : « le curseur part sur le profil par defaut du projet ».

    Le defaut est **le second des trois** : un curseur qui partirait sur zero
    par commodite rendrait vert un ecran qui ne propose rien.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    entrees = calib.entrees_du_projet(projet)
    rang = calib.curseur_du_defaut(entrees)

    assert rang == RANG_DE_LA_CIBLE, [e.nom for e in entrees]
    assert entrees[rang].entree["chain_id"] == PROFILS[RANG_DE_LA_CIBLE]["chain_id"]
    # Volet symetrique : sans defaut au projet, le curseur part sur la premiere
    # entree -- **jamais** sur « aucune », qui serait proposer de livrer brut.
    sans_defaut = calib.entrees_du_projet(_projet(tmp_path, nom="autre"))
    assert calib.curseur_du_defaut(sans_defaut) == 0
    assert sans_defaut[0].cle != calib.CLE_AUCUNE


def test_C1_le_DEFAUT_se_reconnait_par_le_CHEMIN_ecrit_jamais_par_le_chain_id(
        tmp_path):
    """AC 3.1, `EPIC5-ARB-83` : « jamais par recomposition depuis une identite ».

    Le manifeste porte deux entrees du **meme** profil, a deux cles differentes
    (`calibration_profiles` et `default_calibration_profile`). Ici on retire le
    `chain_id` de l'entree de defaut : la reconnaissance doit tenir, parce
    qu'elle porte sur `path`. Un appariement par `chain_id` rougirait.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    defaut = dict(profile_designation.default_profile_entry(projet))
    defaut.pop("chain_id")
    entrees = calib.entrees_du_projet(projet, defaut=defaut)

    par_defaut = [rang for rang, e in enumerate(entrees) if e.par_defaut]
    assert par_defaut == [RANG_DE_LA_CIBLE], [
        (e.nom, e.par_defaut) for e in entrees]


def test_C1_aucune_SECONDE_LECTURE_ni_recomposition_dans_le_module():
    """AC 3.1, comptage a zero **a l'AST**, avec son volet symetrique.

    Trois portes fermees, et chacune est un chemin par lequel l'identite de
    chaine redeviendrait une cle de resolution (`EPIC5-ARB-83`) :
    `calibration_profile.read_profile`, `profile_path` et `profile_exists`
    resolvent tous les trois par le **radical de nom de fichier**. Le module
    lit `designated_profile_path`, et lui seul.
    """
    arbre = ast.parse(Path(calib.__file__).read_text(encoding="utf-8"))
    appeles = {noeud.func.attr for noeud in ast.walk(arbre)
               if isinstance(noeud, ast.Call)
               and isinstance(noeud.func, ast.Attribute)}

    interdits = {"read_profile", "profile_path", "profile_exists",
                 "profile_path_for_document", "profile_file_stem", "loads"}
    assert appeles & interdits == set(), sorted(appeles & interdits)
    # **Volet symetrique** : la mesure regarde bien quelque chose, et les deux
    # lecteurs legitimes du coeur sont bien appeles.
    assert {"designated_profiles", "default_profile_entry",
            "designated_profile_path", "read_designated_document"} <= appeles, (
                sorted(appeles))


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C1_la_liste_porte_la_FLECHE_SEULE_et_AUCUNE_case(tmp_path, banc,
                                                          ascii_seul):
    """AC 3.2, `EPIC11-ARB-126` : « **Flèche seule !** »

    L'ecart `H1` de la fiche : la maquette d'origine portait `▸ (•)` sur la meme
    ligne. Une liste de profils n'est pas une liste a cocher -- on n'en retient
    qu'un --, donc **aucun** des quatre glyphes de retenue n'a sa place ici.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet)
    rendu = _rendu(ecran, banc, app=_app(ecran, ascii_seul=ascii_seul))

    table = jetons.glyphes(ascii_seul)
    assert rendu.count(table["curseur"]) == 1, rendu
    for retenue in ("coche", "decoche", "exclusif-retenu", "exclusif-libre"):
        assert table[retenue] not in rendu, (retenue, rendu)


def test_C1_le_rendu_pose_les_DEUX_COLONNES_de_la_maquette(tmp_path, banc):
    """AC 3.2, la maquette `E3-5` fait foi sur le dessin.

    Le nom ouvre a la colonne 5 de la zone utile, la mention a la colonne 38 --
    **la meme pour les quatre entrees**. Une mention calee a droite (la forme du
    formulaire du depot) les ferait danser d'une entree a l'autre, et c'est ce
    que la maquette ne montre pas.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet)

    async def scenario(_pilote):
        return [ecran.ligne_d_entree(rang, 76)
                for rang in range(len(ecran.choix.entrees))]

    lignes = _monte(_app(ecran), scenario, banc)
    for ligne, entree in zip(lignes, ecran.choix.entrees):
        assert ligne.index(entree.nom[:4]) == 5, (ligne,)
        if entree.mention:
            assert ligne.index(entree.mention) == 38, (ligne,)


def test_C1_la_ligne_de_raccourcis_est_EXACTEMENT_celle_de_la_maquette():
    """AC 3, `EPIC11-ARB-56` et `EPIC11-ARB-68`.

    La ligne est lue **dans la maquette regeneree par le lot A**, jamais
    recopiee ici : la recopier ferait passer ce banc pour vert le jour ou l'une
    des deux bougerait sans l'autre. Et elle ne porte **aucune lettre** : la
    sortie ne s'annonce pas sur cet ecran.
    """
    maquette = (_RACINE / "_bmad-output/planning-artifacts/ux-designs"
                / "ux-tui-2026-08-27/maquettes/E3-5-scan-calibration.txt")
    ligne = maquette.read_text(encoding="utf-8").splitlines()[22][2:78].rstrip()

    assert calib.RACCOURCIS_CALIBRATION == ligne
    # **L'ensemble EXACT des ouvreurs**, et non « Q n'y est pas » : une
    # assertion positive laisserait entrer un cinquieme jeton sans un mot.
    ouvreurs = [jeton.split(" ")[0]
                for jeton in calib.RACCOURCIS_CALIBRATION.split("  ") if jeton]
    assert ouvreurs == ["⏎", "↑↓", "Échap", "F1"], ouvreurs


# ===========================================================================
# C2 -- « autre fichier… » ouvre l'EXPLORATEUR (AC 3.4, AC 3.5)
# ===========================================================================

def test_C2_l_entree_AUTRE_FICHIER_ouvre_l_explorateur(tmp_path, banc):
    """AC 3.4 : `⏎` sur « autre fichier… » **ouvre l'explorateur**.

    Il n'y a rien a retenir tant qu'aucun fichier n'est designe : consommer la
    touche sur rien serait indistinguable d'un clavier casse.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, prises = _ecran(tmp_path, banc, dossier=projet)

    async def scenario(_pilote):
        rang = [e.cle for e in ecran.choix.entrees].index(
            calib.CLE_AUTRE_FICHIER)
        ecran.choix.curseur = rang
        ecran.traiter("enter")
        return ecran.zone, ecran.raccourcis

    zone, raccourcis = _monte(_app(ecran), scenario, banc)
    assert zone == calib.ZONE_EXPLORATEUR
    assert prises == [], "rien n'est retenu tant qu'aucun fichier n'est designe"
    assert raccourcis != calib.RACCOURCIS_CALIBRATION, (
        "la ligne de raccourcis suit la zone : `DESIGN.md` section 4 veut "
        "qu'elle ne montre que ce qui marche sur l'ecran courant")


def test_C2_l_explorateur_est_monte_avec_les_reglages_de_l_AC(tmp_path, banc):
    """AC 3.4 : `montrer_fichiers=True` et un `accepte=` qui retient les `.json`.

    Et il **herite de `CoutureExplorateur`** : l'identite de fonction est
    mesuree, pas la ressemblance -- « un composant partage dont chaque site
    reimplemente le routage ne tient que la moitie de sa promesse » (finding
    `C18`).
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet)

    assert ecran.explorateur.montrer_fichiers is True
    assert ecran.explorateur.selection_multiple is False, (
        "on n'applique qu'une calibration : le mode selection promettrait "
        "qu'on puisse en cocher deux")
    assert calib.profil_acceptable(Path("p.json")) is True
    assert calib.profil_acceptable(Path("P.JSON")) is True
    assert calib.profil_acceptable(Path("p.tiff")) is False
    assert (calib.EcranChoixDeCalibration._traiter_l_explorateur
            is CoutureExplorateur._traiter_l_explorateur)


def test_C2_un_fichier_designe_VALIDE_devient_le_profil_retenu(tmp_path, banc):
    """AC 3.4 : le fichier designe est celui qui partira au coeur."""
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    externe = tmp_path / "ailleurs" / "profil-externe.json"
    externe.parent.mkdir()
    externe.write_text(json.dumps(_document("600-tiff-dddddddddddd",
                                            patchs=30, avant=0.9)),
                       encoding="utf-8")
    ecran, prises = _ecran(tmp_path, banc, dossier=projet)

    async def scenario(_pilote):
        rang = [e.cle for e in ecran.choix.entrees].index(
            calib.CLE_AUTRE_FICHIER)
        ecran.choix.curseur = rang
        ecran.traiter("enter")
        ecran.explorateur.dossier = externe.parent
        ecran.explorateur.relire()
        ecran.explorateur.curseur = [
            e.chemin.name for e in ecran.explorateur.entrees].index(
                externe.name)
        ecran.traiter("enter")
        pose = (ecran.zone, ecran.choix.courante.cle, ecran.carte_courante())
        ecran.traiter("enter")
        return pose

    (zone, cle, carte) = _monte(_app(ecran), scenario, banc)
    assert zone == calib.ZONE_LISTE
    assert cle == calib.CLE_FICHIER_DESIGNE, (
        "le fichier designe prend SA ligne, et le curseur s'y pose : sinon "
        "`⏎` retiendrait sur « autre fichier… », qui n'aurait plus aucune "
        "touche pour en designer un second")
    # **Sa carte d'identite est la** (AC 3.6, « juger sans previz ») : un
    # fichier designe qui ne montrerait rien obligerait a une previz.
    assert carte.chaine == "600-tiff-dddddddddddd", carte
    assert "30 patchs" in carte.pose and "0,9" in carte.pose, carte
    assert ecran.choix.fichier == externe
    assert prises == [calib.CalibrationRetenue(profil_designe=externe)], prises


def test_C2_designer_un_SECOND_fichier_REMPLACE_la_ligne_du_premier(
        tmp_path, banc):
    """Deux lignes pour un choix unique laisseraient l'operateur retenir un
    fichier qu'il a deja remplace.

    **Et « autre fichier… » reste la porte** : c'est ce qui rend la
    re-designation possible, et c'est le cul-de-sac que
    `CLE_FICHIER_DESIGNE` existe pour eviter.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    dossier = tmp_path / "ailleurs"
    dossier.mkdir()
    premier = dossier / "aa-premier.json"
    premier.write_text(json.dumps(_document("600-tiff-dddddddddddd",
                                            patchs=30, avant=0.9)),
                       encoding="utf-8")
    second = dossier / "zz-second.json"
    second.write_text(json.dumps(_document("300-tiff-eeeeeeeeeeee",
                                           patchs=11, avant=4.2)),
                      encoding="utf-8")
    ecran, prises = _ecran(tmp_path, banc, dossier=projet)

    def _designer(nom):
        rang = [e.cle for e in ecran.choix.entrees].index(
            calib.CLE_AUTRE_FICHIER)
        ecran.choix.curseur = rang
        ecran.traiter("enter")
        ecran.explorateur.dossier = dossier
        ecran.explorateur.relire()
        ecran.explorateur.curseur = [
            e.chemin.name for e in ecran.explorateur.entrees].index(nom)
        ecran.traiter("enter")

    async def scenario(_pilote):
        _designer(premier.name)
        _designer(second.name)
        ecran.traiter("enter")
        return [e.cle for e in ecran.choix.entrees]

    cles = _monte(_app(ecran), scenario, banc)
    assert cles.count(calib.CLE_FICHIER_DESIGNE) == 1, cles
    assert calib.CLE_AUTRE_FICHIER in cles, cles
    assert ecran.choix.fichier == second
    assert prises == [calib.CalibrationRetenue(profil_designe=second)], prises


# ===========================================================================
# C3 -- la carte qui se recalcule, et les champs OMIS
# ===========================================================================

def test_C3_la_carte_se_RECALCULE_au_deplacement_du_curseur(tmp_path, banc):
    """AC 3.6 : « elle se recalcule au deplacement du curseur ».

    Les trois profils portent trois dates, trois cardinaux et trois divergences
    **distincts** : une carte qui resterait celle du profil precedent est le
    defaut de famille `M33`, et une fabrique uniforme le rendrait invisible.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet)

    async def scenario(_pilote):
        cartes = []
        for rang in range(len(PROFILS)):
            ecran.choix.curseur = rang
            cartes.append(ecran.carte_courante())
        return cartes

    cartes = _monte(_app(ecran), scenario, banc)
    # **Le NOM personnalise, jamais l'identite derivee** (Egan, 2026-09-01) :
    # l'ensemble est mesure EXACTEMENT, et aucune etiquette de la fabrique ne
    # ressemble a son `chain_id` -- une carte restee sur l'identite rougit donc,
    # ce qu'un `in` n'aurait pas fait.
    assert [c.chaine for c in cartes] == [p["label"] for p in PROFILS]
    assert [c.commentaire for c in cartes] == [p["comment"] for p in PROFILS]
    for carte, profil in zip(cartes, PROFILS):
        assert profil["chain_id"] not in carte.chaine, carte
        assert f"{profil['patchs']} patchs" in carte.pose, carte
        attendu = f"{profil['avant']:.1f}".replace(".", ",")
        assert attendu in carte.pose, carte
        assert calib.date_lisible(profil["date"]) in carte.pose, carte
    assert len({c.pose for c in cartes}) == 3, (
        "trois profils distinguables doivent rendre trois cartes distinctes ; "
        "sinon la fabrique ne mesure aucune permutation")


def test_C3_un_champ_que_le_profil_ne_porte_pas_est_OMIS(tmp_path, banc):
    """AC 3.6 : « omis, jamais rendu `0` ni `--` » (`DESIGN.md` section 3).

    Deux omissions distinctes, et leur volet symetrique dans le meme test :
    un profil **sans acceptation** n'affiche aucune divergence, une entree
    **sans horodate** n'affiche aucune date.
    """
    profils = ({"chain_id": "600-tiff-eeeeeeeeeeee", "source": "muet.json",
                "patchs": 7, "avant": None, "date": ""},)
    projet = _projet(tmp_path, profils=profils)
    entree = dict(profile_designation.designated_profiles(projet)[0])
    entree.pop(profile_designation.ENTRY_DESIGNATED_AT_KEY, None)
    ligne = calib.EntreeDeCalibration("profil-0", "muet.json", "",
                                      entree=entree)
    document = calibration_profile.read_profile(projet, "600-tiff-eeeeeeeeeeee")

    carte = calib.carte(ligne, document=document,
                        chemin=Path(projet) / "x.json")
    assert carte.pose == "7 patchs", carte
    assert "0" not in carte.pose.replace("7 patchs", "")
    assert "--" not in carte.pose
    # **Volet symetrique** : avec l'acceptation et la date, les deux parts
    # apparaissent -- sans lui, une carte toujours vide serait verte.
    riche = calib.carte(
        calib.EntreeDeCalibration(
            "profil-0", "riche.json", "",
            entree=profile_designation.designated_profiles(
                _projet(tmp_path, nom="riche"))[RANG_DE_LA_CIBLE]),
        document=_document("600-tiff-bbbbbbbbbbbb", patchs=24, avant=2.1),
        chemin=Path(projet) / "x.json")
    assert "24 patchs" in riche.pose and "2,1" in riche.pose, riche


def test_C3_la_divergence_est_LUE_de_l_acceptation_du_coeur(tmp_path):
    """AC 3.6 : la mesure est `acceptance.mean_delta_e_before`, jamais un calcul.

    Le nom du champ est celui que `color_calibration.acceptance_from_document`
    relit : la carte ne recalcule rien, elle **lit** ce que le profil porte.
    """
    document = _document("600-tiff-bbbbbbbbbbbb", patchs=24, avant=2.14)
    # **La valeur BRUTE, sans legende** (Egan, 2026-09-01 : « On met la valeur
    # brute sans légende. Seuls les connaisseurs la liront en connaissance de
    # cause. »). L'egalite est EXACTE : « divergence brute » collisionnait avec
    # `color_metrics.raw_divergence_de76`, qui designe une comparaison
    # brut-a-brut entre deux SCANS et qu'un profil ne porte pas.
    assert calib.divergence_brute(document) == "2,1 ΔE"
    assert "divergence" not in calib.divergence_brute(document)
    assert calib.divergence_brute(document, ascii_seul=True).endswith("dE"), (
        "`Δ` n'est pas dans `jetons.REPLIS_DE_TEXTE` : sans repli local, le "
        "mode `--ascii` rendrait un `?`")
    # Aucune acceptation : la part est **omise**, jamais `0,0`.
    assert calib.divergence_brute(_document("600-tiff-bbbbbbbbbbbb",
                                            patchs=24, avant=None)) == ""
    assert calib.divergence_brute(None) == ""


def test_C3_le_cardinal_affiche_est_le_RETENU_et_non_le_LU(tmp_path):
    """AC 3.6 : `retained_patch_count`, pas `read_patch_count`.

    Les deux different de deux dans la fabrique -- une fabrique qui les
    egaliserait rendrait la permutation invisible, ce qui est le premier point
    de la regle des fabriques applique a un axe qu'on ne pense pas (lecon des
    deux dpi egaux du lot B).
    """
    document = _document("600-tiff-bbbbbbbbbbbb", patchs=24, avant=2.1)
    assert document["read_patch_count"] != document["retained_patch_count"]
    assert calib.part_des_patchs(document) == "24 patchs"
    assert calib.part_des_patchs({"retained_patch_count": 1}) == "1 patch"
    assert calib.part_des_patchs({}) == ""


def test_C3_la_carte_d_un_profil_dont_le_FICHIER_a_disparu_le_DIT(tmp_path,
                                                                 banc):
    """AC 3.6 : « l'entree reste vraie de ce que le projet a utilise, mais elle
    ne fabrique pas un profil absent » (`designated_profile_path`).

    Ce n'est **pas un refus** : le glyphe est celui de la substitution, et la
    carte garde ce que l'entree autoportante porte deja.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    entree = profile_designation.designated_profiles(projet)[RANG_DE_LA_CIBLE]
    (Path(projet) / entree[profile_designation.ENTRY_PATH_KEY]).unlink()
    ecran, _ = _ecran(tmp_path, banc, dossier=projet)

    async def scenario(_pilote):
        ecran.choix.curseur = RANG_DE_LA_CIBLE
        return ecran.carte_courante(), _texte(ecran)

    carte, _rendu_ = _monte(_app(ecran), scenario, banc)
    assert ("substitute", calib.FICHIER_DISPARU) in carte.avertissements, carte
    # **L'entree autoportante suffit** : le nom et le commentaire y sont recopies
    # (`ENTRY_OPTIONAL_DOCUMENT_FIELDS`), donc la carte reste lisible sans le
    # fichier -- c'est ce que « l'entree reste vraie de ce que le projet a
    # utilise » veut dire, et ce qu'un repli sur le `chain_id` aurait masque.
    assert carte.chaine == PROFILS[RANG_DE_LA_CIBLE]["label"]
    assert carte.commentaire == PROFILS[RANG_DE_LA_CIBLE]["comment"]
    assert "24 patchs" in carte.pose, carte


def test_C3_la_carte_de_AUCUNE_dit_que_rien_ne_sera_corrige(tmp_path, banc):
    """AC 3.3 : « aucune » livre le lot brut, et l'ecran le **dit**."""
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet)

    async def scenario(_pilote):
        ecran.choix.curseur = len(ecran.choix.entrees) - 1
        return ecran.carte_courante(), ecran.choix.retenue(projet)

    carte, retenue = _monte(_app(ecran), scenario, banc)
    assert carte.phrase == calib.CARTE_SANS_CALIBRATION
    assert retenue == calib.CalibrationRetenue(livrer_brut=True)


def test_C3_AUCUNE_appelle_livrer_brut_et_JAMAIS_un_profil_vide():
    """AC 3.3, verbatim : « Elle appelle `livrer_brut=True` sur le coeur, jamais
    un profil vide. »

    Le couple est **exclusif par construction** : les porter ensemble ferait
    ecrire un lot corrige que le manifeste declarerait brut.
    """
    brut = calib.CalibrationRetenue(livrer_brut=True)
    assert brut.profil_designe is None and brut.livrer_brut is True
    with pytest.raises(ValueError):
        calib.CalibrationRetenue(profil_designe=Path("p.json"),
                                 livrer_brut=True)


def test_C3_le_profil_retenu_est_resolu_par_le_CHEMIN_ECRIT(tmp_path, banc):
    """AC 3.1 et `EPIC5-ARB-83` : `designated_profile_path`, jamais recompose.

    Le chemin rendu est **exactement** celui que le coeur resout : une seconde
    resolution divergerait le jour ou l'etiquette d'un profil change son
    radical de fichier, et l'ecart ne se verrait que sur les TIFF produits.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, prises = _ecran(tmp_path, banc, dossier=projet)

    async def scenario(_pilote):
        ecran.choix.curseur = RANG_DE_LA_CIBLE
        ecran.traiter("enter")
        return None

    _monte(_app(ecran), scenario, banc)
    attendu = profile_designation.designated_profile_path(
        projet, profile_designation.designated_profiles(projet)[RANG_DE_LA_CIBLE])
    assert len(prises) == 1
    assert prises[0].profil_designe == attendu
    assert prises[0].livrer_brut is False
    assert attendu.is_file()
    # **Le radical vient de l'ETIQUETTE, pas de l'identite**, et les deux volets
    # sont poses : depuis que la fabrique etiquette ses profils, le fichier
    # s'appelle `hp-envy-4520-atelier.json`. Une resolution qui recomposerait le
    # chemin depuis le `chain_id` -- exactement ce qu'`EPIC5-ARB-83` interdit --
    # viserait un fichier qui n'existe pas, et le volet negatif est le seul a le
    # mesurer : le volet positif seul resterait vert sur un profil non etiquete.
    assert attendu.name.startswith(calibration_profile.slugify_label(
        PROFILS[RANG_DE_LA_CIBLE]["label"]))
    assert not attendu.name.startswith(PROFILS[RANG_DE_LA_CIBLE]["chain_id"])


# ===========================================================================
# C3 bis -- la ligne « Chaîne » porte le NOM PERSONNALISE (Egan, 2026-09-01)
# ===========================================================================
#
# Correction tranchee sur la planche de relecture du temps 2. Verbatim d'Egan :
# « Ce qui s'affiche ici normalement c'est le nom personnalisé qui a été donné
# par l'opérateur.ice au moment de créer la page de calibration. Ça suffit très
# bien. Ce qu'on peut y afficher éventuellement c'est le commentaire qui a été
# mis au moment de générer la planche s'il est stocké au manifest ? »
#
# L'ecran affichait le `chain_id` verbatim -- `<dpi>-<format>-<sha256[:12]>` --
# faute de mieux : `scan_chain.derive_chain_id` **hache** make/model/software, et
# la maquette d'origine dessinait une identite decomposee que le produit ne
# pouvait pas rendre.


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C3bis_la_ligne_CHAINE_porte_le_NOM_puis_le_COMMENTAIRE(tmp_path, banc,
                                                                ascii_seul):
    """La ligne rendue porte l'etiquette et le commentaire, **et pas l'identite**.

    Mesure sur le RENDU et non sur la carte : `carte_courante()` pourrait porter
    les deux champs sans que `lignes_de_la_carte` les pose -- c'est le mode de
    panne du lot `E9` (« un composant que rien ne cable est un composant que le
    produit n'a pas »), paye trois fois sur ce depot.

    Le volet negatif est ce qui donne sa valeur au test : sans lui, une ligne qui
    porterait le nom **et** le `chain_id` resterait verte.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet, lots=2)

    async def scenario(_pilote):
        ecran.choix.curseur = RANG_DE_LA_CIBLE
        ecran.rafraichir()
        return _texte(ecran)

    rendu = _monte(_app(ecran, ascii_seul=ascii_seul), scenario, banc)
    cible = PROFILS[RANG_DE_LA_CIBLE]
    attendus = [cible["label"], cible["comment"]]
    if ascii_seul:
        attendus = [jetons.replier_ascii(part) for part in attendus]
    ligne = [l for l in _lignes_utiles(rendu)
             if jetons.replier_ascii(calib.LIBELLE_CHAINE) in
             jetons.replier_ascii(l)]
    assert len(ligne) == 1, rendu
    for part in attendus:
        assert part in ligne[0], (part, ligne[0])
    # **Jamais l'identite de chaine**, et sur le rendu ENTIER : elle ne doit
    # revenir ni sur la carte, ni ailleurs a l'ecran.
    assert cible["chain_id"] not in rendu, rendu
    # **Et la divergence n'a plus de legende, sur le rendu lui-meme** (seconde
    # correction d'Egan du meme jour). Elle est mesuree ici en plus de son test
    # de fonction, parce que c'est cette ligne-la qu'il relit : la valeur passe
    # par l'entonnoir, la legende pourrait y revenir par une seule redaction.
    assert "divergence" not in rendu.lower(), rendu
    attendue = f"{cible['avant']:.1f}".replace(".", ",")
    assert attendue in rendu, (attendue, rendu)


def test_C3bis_un_profil_SANS_ETIQUETTE_replie_sur_son_chain_id(tmp_path):
    """Le repli **nomme** : un profil ancien n'a pas d'etiquette.

    `ENTRY_OPTIONAL_DOCUMENT_FIELDS` la recopie a `""`, et `validate_profile_
    document` la pose vide. Montrer le `chain_id` est alors un **fait** du profil
    -- pas une valeur devinee --, et la ligne reste : une carte dont l'identite
    s'evapore ne permet plus de « juger sans previz » (AC 3.6).

    Les trois regimes de repli sont mesures ensemble, parce qu'ils se
    distinguent : etiquette absente, etiquette vide, etiquette d'espaces.
    """
    for etiquette in ({}, {"label": ""}, {"label": "   "}):
        source = {"chain_id": "600-tiff-bbbbbbbbbbbb", **etiquette}
        assert calib.nom_de_la_chaine(source) == "600-tiff-bbbbbbbbbbbb", source
    # Et **rien** quand il n'y a ni l'un ni l'autre : la ligne est alors omise.
    assert calib.nom_de_la_chaine({}) == ""
    assert calib.nom_de_la_chaine(None) == ""
    # Le volet symetrique, sans lequel un repli permanent serait vert.
    assert calib.nom_de_la_chaine(
        {"chain_id": "600-tiff-bbbbbbbbbbbb",
         "label": "HP Envy 4520 atelier"}) == "HP Envy 4520 atelier"


def test_C3bis_un_profil_SANS_COMMENTAIRE_ne_pose_AUCUN_separateur(tmp_path,
                                                                   banc):
    """Le volet d'omission : pas de ` · ` orphelin en fin de ligne.

    Le premier profil de la fabrique n'a aucun commentaire, et c'est pour cela
    qu'il n'en a pas : un remplissage uniforme des trois n'aurait jamais montre
    la difference.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet, lots=2)

    async def scenario(_pilote):
        ecran.choix.curseur = 0
        return ecran.carte_courante(), ecran.lignes_de_la_carte()

    carte, lignes = _monte(_app(ecran), scenario, banc)
    assert carte.commentaire == "", carte
    ligne = [l for l in lignes if calib.LIBELLE_CHAINE in l][0]
    assert ligne.rstrip().endswith(PROFILS[0]["label"]), ligne
    assert calib.SEPARATEUR_DE_CARTE not in ligne, ligne


def test_C3bis_l_ecart_de_DPI_se_lit_encore_sur_un_profil_ETIQUETE(tmp_path,
                                                                   banc):
    """Le piege que la correction pouvait ouvrir, ferme par une mesure.

    `dpi_du_profil` lit le dpi du **prefixe du `chain_id`** et rend `None` hors de
    cette forme, **sans erreur**. Passer le nom personnalise a sa place aurait
    donc fait taire l'avertissement de l'AC 3.7 sur tout profil etiquete -- en
    silence, et sur le seul regime que la fabrique exerce desormais.

    La cible est posee a 600, le scan declare 300, et son etiquette
    (`HP Envy 4520 atelier`) ne porte aucun dpi lisible.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet,
                      dpi_du_scan=DPI_DU_SCAN_DIVERGENT)

    async def scenario(_pilote):
        ecran.choix.curseur = RANG_DE_LA_CIBLE
        return ecran.carte_courante()

    carte = _monte(_app(ecran), scenario, banc)
    assert calib.dpi_du_profil(PROFILS[RANG_DE_LA_CIBLE]["label"]) is None, (
        "si l'etiquette portait un dpi lisible, ce test ne mesurerait rien")
    assert ("substitute", calib.ECART_DE_DPI.format(
        profil=600, scan=DPI_DU_SCAN_DIVERGENT)) in carte.avertissements, carte


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C3bis_un_commentaire_de_2000_CARACTERES_ne_deborde_pas(tmp_path, banc,
                                                                ascii_seul):
    """`COMMENT_MAX_LENGTH` vaut 2000, et la grille fait 80 colonnes.

    L'abregement n'est **pas** ecrit sur la ligne : c'est l'entonnoir unique
    (`jetons.ajuster` dans `rafraichir`) qui le pose, apres avoir compte les
    colonnes. Un second abregement local couperait avant lui et divergerait.

    Le commentaire porte des accents, pour que le regime `--ascii` mesure aussi
    le repli -- `…` y vaut trois colonnes contre une, et c'est la regression
    payee deux fois sur le bandeau.
    """
    # **Le plafond est LU du coeur, jamais recopie** : `COMMENT_MAX_LENGTH` a
    # deja bouge une fois ailleurs (la borne des identifiants canoniques), et un
    # nombre grave ici mesurerait autre chose au premier ajustement.
    bavard = ("vitre nettoyée à l'alcool, "
              * 80)[:calibration_profile.COMMENT_MAX_LENGTH]
    assert len(bavard) == calibration_profile.COMMENT_MAX_LENGTH
    profils = (dict(PROFILS[RANG_DE_LA_CIBLE], comment=bavard),)
    projet = _projet(tmp_path, profils=profils, nom="bavard")
    ecran, _ = _ecran(tmp_path, banc, dossier=projet, lots=2)
    rendu = _rendu(ecran, banc,
                   app=_app(ecran, projet="bavard", ascii_seul=ascii_seul))

    lignes = _lignes_utiles(rendu)
    assert len(lignes) <= 17, (len(lignes), rendu)
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= 76, (jetons.colonnes(ligne), ligne)
    if ascii_seul:
        assert rendu.isascii(), [l for l in lignes if not l.isascii()]
    # **L'abregement se VOIT** : une ligne coupee net serait indistinguable
    # d'une ligne complete, et c'est ce que `jetons.ajuster` existe pour dire.
    ligne = [l for l in lignes
             if jetons.replier_ascii(calib.LIBELLE_CHAINE) in
             jetons.replier_ascii(l)][0]
    assert ligne.rstrip().endswith(jetons.points_d_abregement(ascii_seul)), ligne


# ===========================================================================
# C4 -- les trois cas limites de l'AC 3.7, chacun mesure SEPAREMENT
# ===========================================================================

def test_C4_aucun_profil_dans_le_projet_renvoie_a_l_ECRAN_de_calibration(
        tmp_path, banc):
    """AC 3.7, premier cas : « aucune » reste seule, et l'ecran renvoie a
    `Calibrer une chaîne` **par son nom d'ecran** (`EPIC11-ARB-28`).

    Le nom est **lu** de `atelier_scan.ENTREES_DU_MENU`, jamais recopie : une
    seconde redaction enverrait l'operateur chercher une entree renommee.
    """
    projet = _projet(tmp_path, profils=())
    ecran, _ = _ecran(tmp_path, banc, dossier=projet)
    rendu = _rendu(ecran, banc)

    assert [e.cle for e in ecran.choix.entrees] == [
        calib.CLE_AUTRE_FICHIER, calib.CLE_AUCUNE]
    nom = [e.nom for e in atelier_scan.ENTREES_DU_MENU
           if e.cle == calib.CLE_DE_LA_CALIBRATION][0]
    assert calib.NOM_DE_L_ECRAN_DE_CALIBRATION == nom
    assert nom in rendu, rendu
    # **Jamais un nom de commande** : le comptage porte sur le rendu ET sur les
    # chaines du module.
    for commande in ("scan calibrate", "scan-calibrate", "mmu scan"):
        assert commande not in rendu, (commande, rendu)


def test_C4_le_renvoi_ne_se_montre_QUE_quand_le_projet_n_a_aucun_profil(
        tmp_path, banc):
    """Le volet symetrique du precedent : sans lui, un renvoi permanent
    passerait pour conforme -- et il occuperait deux lignes sur les dix-sept."""
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet)
    rendu = _rendu(ecran, banc)
    assert calib.NOM_DE_L_ECRAN_DE_CALIBRATION not in rendu, rendu


def test_C4_un_profil_pose_a_un_AUTRE_DPI_porte_une_ligne_et_PAS_un_refus(
        tmp_path, banc):
    """AC 3.7, second cas : « ligne `▲` sur la carte, **nommant les deux dpi**,
    et **pas un refus** ».

    La cible est posee a 600, le scan declare 300. Un refus retirerait a
    l'operateur la seule issue qu'il ait -- un profil pose a un autre dpi reste
    applicable, et c'est a lui de juger.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, prises = _ecran(tmp_path, banc, dossier=projet,
                           dpi_du_scan=DPI_DU_SCAN_DIVERGENT)

    async def scenario(_pilote):
        ecran.choix.curseur = RANG_DE_LA_CIBLE
        carte = ecran.carte_courante()
        ecran.traiter("enter")
        return carte, _texte(ecran)

    carte, rendu = _monte(_app(ecran), scenario, banc)
    avertissement = [phrase for etat, phrase in carte.avertissements
                     if etat == "substitute"]
    assert avertissement == [
        calib.ECART_DE_DPI.format(profil=600, scan=DPI_DU_SCAN_DIVERGENT)]
    assert "600" in avertissement[0] and "300" in avertissement[0]
    # **Pas un refus** : le choix passe quand meme.
    assert len(prises) == 1 and prises[0].profil_designe is not None


def test_C4_aucune_ligne_de_dpi_quand_les_deux_COINCIDENT_ou_sont_INCONNUS(
        tmp_path, banc):
    """Le volet symetrique du precedent, et il porte **deux** regimes.

    Une ligne d'ecart posee sans condition serait verte au test ci-dessus. Et
    un `chain_id` hors de la forme que le coeur compose ne rend **aucun** dpi :
    `dpi_du_profil` omet plutot que de deviner.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet, dpi_du_scan=600)

    async def scenario(_pilote):
        ecran.choix.curseur = RANG_DE_LA_CIBLE
        return ecran.carte_courante()

    carte = _monte(_app(ecran), scenario, banc)
    assert carte.avertissements == (), carte
    assert calib.dpi_du_profil("hp-envy-4520-tiff-600") is None
    assert calib.dpi_du_profil("600-tiff-trop-court") is None
    assert calib.dpi_du_profil(None) is None
    assert calib.dpi_du_profil("600-tiff-bbbbbbbbbbbb") == 600


def test_C4_les_deux_refus_du_coeur_ne_se_CONFONDENT_pas(tmp_path):
    """AC 3.7, troisieme cas : « `ProfileValidationError` **ou**
    `ProfileNotFoundError`, qui ne se confondent pas ».

    Les deux ne disent pas la meme chose a l'operateur : l'un designe un
    fichier absent, l'autre un fichier qui n'est pas un profil. Et le motif du
    coeur voyage **verbatim** (`EPIC11-ARB-30`).
    """
    absent = tmp_path / "nulle-part.json"
    invalide = tmp_path / "invalide.json"
    invalide.write_text("{\"schema_version\": 1}", encoding="utf-8")
    pas_du_json = tmp_path / "pas-du-json.json"
    pas_du_json.write_text("ceci n'est pas du JSON", encoding="utf-8")

    with pytest.raises(calibration_profile.ProfileNotFoundError):
        calib.lire_le_profil_designe(absent)
    with pytest.raises(calibration_profile.ProfileValidationError):
        calib.lire_le_profil_designe(invalide)
    with pytest.raises(calibration_profile.ProfileValidationError):
        calib.lire_le_profil_designe(pas_du_json)
    # Les deux classes sont **distinctes** et non l'une l'alias de l'autre.
    assert not issubclass(calibration_profile.ProfileNotFoundError,
                          calibration_profile.ProfileValidationError)
    assert not issubclass(calibration_profile.ProfileValidationError,
                          calibration_profile.ProfileNotFoundError)
    # Volet symetrique : un vrai profil traverse.
    bon = tmp_path / "bon.json"
    bon.write_text(json.dumps(_document("600-tiff-ffffffffffff", patchs=9,
                                        avant=1.0)), encoding="utf-8")
    assert calib.lire_le_profil_designe(bon)["chain_id"] == "600-tiff-ffffffffffff"


def test_C4_un_fichier_designe_ILLISIBLE_laisse_le_choix_precedent_ACTIF(
        tmp_path, banc):
    """AC 3.7, troisieme cas, cote ecran : « le choix precedent reste actif ».

    On designe d'abord un profil valide, puis un fichier refuse. Rien n'est
    pose : ni le fichier, ni le document. L'ecran **reste** sur l'explorateur --
    la cible est fautive, pas le geste -- et le motif du coeur va en ligne
    d'etat, verbatim.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    dossier = tmp_path / "ailleurs"
    dossier.mkdir()
    bon = dossier / "aa-bon.json"
    bon.write_text(json.dumps(_document("600-tiff-dddddddddddd", patchs=30,
                                        avant=0.9)), encoding="utf-8")
    casse = dossier / "zz-casse.json"
    casse.write_text("{}", encoding="utf-8")
    ecran, prises = _ecran(tmp_path, banc, dossier=projet)

    def _designer(nom):
        ecran.explorateur.dossier = dossier
        ecran.explorateur.relire()
        ecran.explorateur.curseur = [
            e.chemin.name for e in ecran.explorateur.entrees].index(nom)
        ecran.traiter("enter")

    def _ouvrir():
        rang = [e.cle for e in ecran.choix.entrees].index(
            calib.CLE_AUTRE_FICHIER)
        ecran.choix.curseur = rang
        ecran.traiter("enter")

    async def scenario(_pilote):
        _ouvrir()
        _designer(bon.name)
        avant = (ecran.choix.fichier, ecran.choix.document)
        _ouvrir()
        _designer(casse.name)
        return avant, ecran.choix.fichier, ecran.choix.document, ecran.zone, \
            ecran.etat()

    avant, fichier, document, zone, etat = _monte(_app(ecran), scenario, banc)
    assert avant[0] == bon
    assert fichier == bon, "le choix precedent doit rester actif"
    assert document == avant[1]
    assert zone == calib.ZONE_EXPLORATEUR
    assert str(casse) in etat, etat
    assert prises == []


# ===========================================================================
# C5 -- la fabrique a trois profils, la cible AU MILIEU
# ===========================================================================

def test_C5_la_cible_est_au_MILIEU_de_la_liste_que_le_code_parcourt(tmp_path):
    """AC 3.8, et c'est la tache C5 a la lettre.

    **La position se verifie sur la liste que le CODE parcourt**, jamais sur
    celle que la fabrique ecrit : `_upsert` trie le registre par `chain_id`, si
    bien que l'ordre d'appel de la fabrique ne decide de rien. Ce piege a ete
    paye deux fois sur ce depot.

    Trois elements et la cible au milieu ferment deux mutants a la fois : un
    `find` qui rend le premier (`M25`), et un `continue` devenu `break` qui
    s'arrete au dernier (11.4b).
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    parcourue = profile_designation.designated_profiles(projet)
    rang = [e["chain_id"] for e in parcourue].index(
        PROFILS[RANG_DE_LA_CIBLE]["chain_id"])

    assert len(parcourue) == 3
    assert 0 < rang < len(parcourue) - 1, [e["chain_id"] for e in parcourue]
    entrees = calib.entrees_du_projet(projet)
    profils = [e for e in entrees if e.est_un_profil]
    assert len(profils) == 3, [e.nom for e in entrees]
    assert profils[rang].entree["chain_id"] == parcourue[rang]["chain_id"]
    # Les trois sont distinguables sur **cinq** axes : un remplissage uniforme
    # rendrait toute permutation invisible.
    for cle in ("chain_id", "designated_from", "designated_at",
                "retained_patch_count"):
        assert len({e[cle] for e in parcourue}) == 3, (cle, parcourue)


def test_C5_un_find_fautif_qui_rendrait_le_PREMIER_profil_se_demasque(tmp_path):
    """Le volet actif de `C5` : la cible n'est ni la premiere ni la derniere.

    Sans ce test, `test_C1_le_curseur_part_sur_le_profil_par_DEFAUT_du_projet`
    pourrait passer sur une fabrique dont le defaut serait en tete.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    entrees = calib.entrees_du_projet(projet)
    par_defaut = [rang for rang, e in enumerate(entrees) if e.par_defaut]

    assert par_defaut == [RANG_DE_LA_CIBLE]
    assert entrees[0].par_defaut is False
    assert entrees[len(PROFILS) - 1].par_defaut is False


# ===========================================================================
# La grille, la ligne d'etat, et le clavier
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_l_ecran_tient_le_plancher_80x24_meme_avec_HUIT_profils(tmp_path, banc,
                                                                ascii_seul):
    """`EPIC11-ARB-21` : dix-sept lignes de zone centrale, 76 colonnes utiles.

    **Huit profils et non trois** : c'est le regime ou la liste deborde, donc
    celui ou la fenetre `…` doit exister. Un ecran mesure seulement sur sa
    fabrique nominale ne dit rien du jour ou un projet en porte dix.
    """
    profils = tuple(
        {"chain_id": f"{300 + 100 * rang}-tiff-{chr(97 + rang) * 12}",
         "source": f"profil-{rang}.json", "patchs": 10 + rang,
         "avant": 1.0 + rang, "date": f"2026-08-0{rang + 1}T08:00:00Z"}
        for rang in range(8))
    projet = _projet(tmp_path, profils=profils, rang_du_defaut=4)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet, lots=2,
                      dpi_du_scan=DPI_DU_SCAN_DIVERGENT)
    rendu = _rendu(ecran, banc, app=_app(ecran, ascii_seul=ascii_seul))

    lignes = _lignes_utiles(rendu)
    assert len(lignes) <= 17, (len(lignes), rendu)
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= 76, (jetons.colonnes(ligne), ligne)
    if ascii_seul:
        assert rendu.isascii(), [l for l in lignes if not l.isascii()]
    points = jetons.points_d_abregement(ascii_seul)
    assert points in rendu, "la liste deborde : elle doit porter ses `…`"


@pytest.mark.parametrize("ascii_seul", MODES)
def test_l_ecran_NOMINAL_tient_aussi_le_plancher(tmp_path, banc, ascii_seul):
    """Le volet symetrique : trois profils tiennent **sans** aucun `…`.

    Sans lui, une liste qui se replierait toujours passerait le test precedent.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet, lots=2)
    rendu = _rendu(ecran, banc, app=_app(ecran, ascii_seul=ascii_seul))

    lignes = _lignes_utiles(rendu)
    assert len(lignes) <= 17, (len(lignes), rendu)
    # **La mesure porte sur la ligne de repli, pas sur les points** : « autre
    # fichier… » porte legitimement une ellipse dans son NOM, et un `not in`
    # sur le rendu entier confondrait les deux.
    points = jetons.points_d_abregement(ascii_seul)
    assert [l for l in lignes if l.strip() == points] == [], lignes


def test_la_ligne_d_etat_porte_une_MESURE_et_rien_d_autre(tmp_path, banc):
    """`EPIC11-ARB-56` : aucune touche, aucun conseil, aucun motif de conception.

    Elle compte les profils et dit sur quoi le retenu s'appliquera -- deux
    faits, verbatim de la maquette (l. 22). Le compte est mesure aux **trois**
    cardinaux, parce que le cas a un element est le seul ou la faute d'accord se
    voie.
    """
    # **Deux profils et deux lots : exactement ce que la maquette dessine.**
    # Comparer un verbatim a une fabrique de trois profils obligerait a
    # recopier la ligne en la retouchant, ce qui detruirait la mesure.
    projet = _projet(tmp_path, profils=PROFILS[:2], rang_du_defaut=1)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet, lots=2)

    async def scenario(_pilote):
        return ecran.etat()

    etat = _monte(_app(ecran), scenario, banc)
    ligne_de_la_maquette = (_RACINE / "_bmad-output/planning-artifacts/ux-designs"
                            / "ux-tui-2026-08-27/maquettes/E3-5-scan-calibration.txt"
                            ).read_text(encoding="utf-8").splitlines()[21][2:78].rstrip()
    # **Verbatim de la maquette**, lue et non recopiee : la fabrique porte trois
    # profils et deux lots, exactement ce que le dessin annonce.
    assert etat == ligne_de_la_maquette, (etat, ligne_de_la_maquette)
    for interdit in ("⏎", "Tab", "Échap", "F1", "appuyez", "pensez"):
        assert interdit not in etat, (interdit, etat)

    seul, _ = _ecran(tmp_path, banc,
                     dossier=_projet(tmp_path, profils=PROFILS[:1], nom="un"),
                     lots=1)
    aucun, _ = _ecran(tmp_path, banc,
                      dossier=_projet(tmp_path, profils=(), nom="zero"))

    async def deux(_pilote):
        return seul.etat(), aucun.etat()

    etat_seul, etat_aucun = _monte(_app(seul, projet="un"), deux, banc)
    assert etat_seul == ("1 profil désigné dans ce projet · "
                         "le retenu s'applique au lot"), etat_seul
    assert etat_aucun == calib.ETAT_SANS_PROFIL, etat_aucun


def test_la_frappe_imprimable_est_CONSOMMEE_et_F1_traverse(tmp_path, banc):
    """`EPIC11-ARB-68` et la garde des touches annoncees.

    La ligne de raccourcis de cet ecran n'annonce **aucune** sortie : laisser
    remonter une frappe jusqu'au binding applicatif `q` fermerait l'application
    sur une touche que rien n'annonce. `F1` et `Échap`, eux, sont annonces :
    ils traversent jusqu'a l'application, qui les cable.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, prises = _ecran(tmp_path, banc, dossier=projet)

    async def scenario(_pilote):
        return (ecran.traiter("q", "q"), ecran.traiter("f1"),
                ecran.traiter("escape"))

    frappe, f1, echap = _monte(_app(ecran), scenario, banc)
    assert frappe is True, "la frappe est consommee"
    assert f1 is False and echap is False, "les deux touches annoncees traversent"
    assert prises == []


def test_le_curseur_ne_SORT_JAMAIS_de_la_liste(tmp_path, banc):
    """`↑↓` bornent, ils ne bouclent pas -- meme regle que le menu d'atelier."""
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet)

    async def scenario(_pilote):
        for _ in range(20):
            ecran.traiter("up")
        haut = ecran.choix.curseur
        for _ in range(20):
            ecran.traiter("down")
        return haut, ecran.choix.curseur

    haut, bas = _monte(_app(ecran), scenario, banc)
    assert haut == 0
    assert bas == len(PROFILS) + 1


def test_le_rappel_de_retenue_est_REQUIS_et_non_optionnel():
    """Finding `K3`, paye quatre fois : « un `Callable | None = None` assorti
    d'un `if ... is not None` fait de l'oubli de cablage un silence ».

    Le rendre requis fait de l'oubli une **erreur d'appel**, que la garde des
    rappels cables n'a alors plus a rattraper.
    """
    with pytest.raises(TypeError):
        calib.EcranChoixDeCalibration()


def test_le_rang_peint_est_bien_celui_de_l_entree_sous_le_curseur(tmp_path,
                                                                  banc):
    """`EPIC11-ARB-45` : « le curseur *est* la selection ».

    Le rang peint est **derive** de la fenetre : deux comptes de lignes
    divergeraient a la premiere ligne inseree au-dessus de la liste, et le
    curseur se peindrait alors sur une autre entree sans que rien ne le dise.
    C'est la famille du mutant `M33`, et la cible est **au milieu**.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DE_LA_CIBLE)
    ecran, _ = _ecran(tmp_path, banc, dossier=projet)

    async def scenario(_pilote):
        ecran.choix.curseur = RANG_DE_LA_CIBLE
        ecran.rafraichir()
        return ecran.rang_du_curseur(), _lignes_utiles(_texte(ecran))

    rang, lignes = _monte(_app(ecran), scenario, banc)
    attendu = PROFILS[RANG_DE_LA_CIBLE]["source"]
    assert attendu in lignes[rang], (rang, lignes)
    assert jetons.GLYPHES["curseur"] in lignes[rang], lignes[rang]
