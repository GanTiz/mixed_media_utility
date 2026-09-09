# -*- coding: utf-8 -*-
"""Le palier Projet et ses deux commandes (story 11.3, task 3 -- AC 5).

Le point de cette fiche est une **couture** : le profil pose ici est celui que
l'atelier Scan proposera en vague 4. La mesure est donc faite **sur le
producteur**, faute de quoi personne ne la ferait avant la vague 4 -- et ce
serait exactement la classe « defaut de couture entre deux stories » que la
retrospective de l'Epic 7 instruit.
"""
import json
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[3]
for chemin in (str(_RACINE / "src"), str(_RACINE / "tests" / "unit")):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

import pytest

from mixed_media_utility import color_calibration as cc
from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io import calibration_profile, profile_designation
from mixed_media_utility.tui import jetons, palier_projet
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

# Meme fabrique de profil que `test_profil_designe.py` : trois profils
# distinguables **au coefficient pres**, produits par les vrais
# producteurs du coeur plutot que par un document ecrit a la main.
import test_calibration_page_source as couleur


# ---------------------------------------------------------------------------
# Fabriques. **Trois profils distinguables au coefficient pres**, comme
# `test_profil_designe.py` les fabrique deja : la regle du depot vaut ici aussi,
# et la cible n'est jamais le premier.
# ---------------------------------------------------------------------------

#: Trois identites de chaine, **volontairement pas dans l'ordre alphabetique de
#: leur rang** : la cible usuelle des tests ci-dessous (`CHAINES[2]`) n'est ni la
#: premiere ecrite ni la premiere du dossier une fois trie. Une resolution qui
#: prendrait « le premier fichier de `versions/calibration/` » se demasque.
CHAINES = ("chaine-alpha", "chaine-zeta", "chaine-mu")

#: Trois presses **reelles**, distinguables au coefficient pres -- les memes que
#: `test_profil_designe.py` emploie. Ce sont des fonctions de presse, pas des
#: scalaires : les profils sont produits par les vrais producteurs du coeur.
PRESSES = (
    couleur._NOMINAL_PRESS,
    couleur._DEVIANT_PRESS,
    couleur._press(0.960, (0.0200, 0.0310, 0.0180)),
)


def _document(chain_id: str, press) -> dict:
    profil = couleur._calibration_profile(press=press)
    return cc.profile_to_document(
        profil, chain_id=chain_id, source_page_id=f"{chain_id}-p0",
        template_id=couleur.TEMPLATE, read_patch_count=18,
        retained_patch_count=18,
        ink_floor_excluded=cc.correction_form_excludes_ink_floor(
            profil.correction_id))


def _profils_externes(tmp_path) -> list[Path]:
    """Trois profils autonomes, **hors de tout projet** : la forme dans
    laquelle un profil voyage (`EPIC5-ARB-83`)."""
    chemins = []
    for rang, (chaine, presse) in enumerate(zip(CHAINES, PRESSES)):
        dossier = tmp_path / "ailleurs" / f"poste_{rang}"
        dossier.mkdir(parents=True, exist_ok=True)
        chemin = dossier / f"{chaine}.json"
        chemin.write_text(
            calibration_profile.serialize_profile(_document(chaine, presse)),
            encoding="utf-8")
        chemins.append(chemin)
    return chemins


def _app(ecran, **kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Ateliers", "q quitter"), ecran],
                    contexte=Contexte(projet="projet_demo"), **kwargs)


def _monte(app, scenario, banc):
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def _texte(ecran) -> str:
    """Le texte **tel qu'il s'affiche**, balises de couleur retirees.

    Depuis `EPIC11-ARB-47` le widget porte du balisage : mesurer sa chaine brute
    compterait des balises comme des colonnes, et chercher un libelle dedans
    echouerait des qu'il est colore.
    """
    return jetons.texte_affiche(str(ecran._corps.content))


# ---------------------------------------------------------------------------
# AC 5.1 et 5.6 -- deux commandes, et deux seulement
# ---------------------------------------------------------------------------

def test_le_palier_porte_exactement_TROIS_entrees():
    """Story 11.11, AC 2.1 -- l'ensemble est EXACTEMENT trois, et dans l'ordre.

    **Il en portait DEUX**, et le nom de ce test le disait : `EPIC11-ARB-18`
    (`Q4-b`) avait tranche « deux commandes, et non trois ». La troisieme
    n'annule pas cet arbitrage, elle en sort : `-18` refusait un ecran de
    `relink` a cote des deux commandes de CYCLE DE VIE, et
    `EPIC11-ARB-155` ajoute une entree d'une autre nature -- la gestion des
    medias, dont le premier ecran est un inventaire qui LIT.

    L'ordre est celui d'`E6-0` : la gestion des medias en TETE. Un test qui ne
    mesurerait que l'ensemble laisserait passer une permutation, et
    `test_valider_par_REFLEXE...` en depend -- c'est la premiere entree que
    `⏎` suit.
    """
    choix = palier_projet.entrees_du_palier()
    assert [issue.cle for issue in choix.issues] == [
        "project", "set-default-profile", "reconstruct-project"]


def test_aucune_entree_n_est_preselectionnee():
    """`EPIC11-ARB-7`, garanti a la construction par `ChoixExclusif`."""
    assert palier_projet.entrees_du_palier().retenue is None


def test_les_cles_NOMMENT_la_commande_de_coeur_servie():
    """`EPIC11-ARB-36`, d'un cran au-dessus : une entree qui ne nommerait pas
    sa commande obligerait a lire le code pour savoir ce qu'elle lance."""
    from mixed_media_utility import cli

    assert palier_projet.ENTREE_PROFIL == cli.SET_DEFAULT_PROFILE_COMMAND
    assert palier_projet.ENTREE_RECONSTRUCTION == "reconstruct-project"


def test_le_palier_n_a_AUCUN_ecran_de_relink():
    """AC 5.6 -- `EPIC11-ARB-23` : « `relink` n'a pas d'ecran dans la TUI ».

    **La mesure a change, l'arbitrage non, et il faut dire les deux.** Ce test
    comptait a ZERO les occurrences du mot `relink` dans les chaines du
    module ; `E6-0`, validee le 2026-09-04, ecrit ce mot dans la phrase de la
    troisieme entree (« Gérer les médias du projet : ajout, relink et
    suppression ») et `E6-1` lui donne une porte, `Ctrl+L` sur un objet
    declare et absent. Le comptage a zero est donc FALSIFIE par une maquette
    validee, et c'est un ecart nomme au registre de la story 11.11.

    Ce que `EPIC11-ARB-23` protegeait tient toujours, et c'est ce que ce test
    mesure desormais : le palier n'a **aucune classe d'ecran** de relink et
    aucune entree de menu qui n'ouvre que ca. Le relink est un GESTE de
    l'inventaire, pas une commande du palier.

    **Elle lit les noms DEFINIS autant que les noms REFERENCES**, et il a fallu
    la couche 3 de la revue pour le voir : `identifiants()` collecte `ast.Name`,
    `ast.Attribute` et les alias d'import, **jamais** `ClassDef.name`. Une
    classe `EcranRelinkDuRush` definie ici et jamais citee par son nom lui
    etait invisible -- mutant injecte, **SURVIVANT sur 30 verts**, sous une
    docstring qui promettait « aucune classe d'ecran de relink ». La case de
    l'ecart 17 etait cochee sur une garantie non rendue.

    Le volet symetrique porte desormais sur une source de SYNTHESE passee aux
    VRAIES fonctions -- voir
    :func:`test_la_frontiere_du_RELINK_mord_sur_un_module_fautif`. L'ancien
    filtrait un tuple litteral (`[n for n in ("EcranRelink", "poser") ...]`),
    ce qui prouvait que l'operateur `in` de Python fonctionne : la tautologie
    exacte que la section 6.2 de la politique de revue nomme.
    """
    from outils_frontiere import definitions, identifiants

    chemin = Path(palier_projet.__file__)
    noms = identifiants(chemin) | definitions(chemin)
    assert [n for n in noms if "relink" in n.lower()] == []
    assert [cle for cle in palier_projet.LIBELLES
            if "relink" in cle.lower()] == []


def test_la_frontiere_du_RELINK_mord_sur_un_module_fautif(tmp_path):
    """Le volet symetrique, sur la VRAIE fonction et une source de synthese.

    Trois formes qu'un ecran de relink pourrait prendre, et la mesure doit
    voir les trois. La premiere est celle qui SURVIVAIT : une classe definie
    et jamais referencee.
    """
    from outils_frontiere import definitions, identifiants

    fautifs = {
        "classe_definie.py": (
            "class EcranRelinkDuRush:\n"
            "    \"\"\"Exactement ce qu'EPIC11-ARB-23 refuse.\"\"\"\n"),
        "fonction_definie.py": "def ouvrir_le_relink():\n    return None\n",
        "nom_reference.py": "from .ailleurs import EcranRelink\nX = EcranRelink\n",
    }
    for nom, source in fautifs.items():
        chemin = tmp_path / nom
        chemin.write_text(source, encoding="utf-8")
        noms = identifiants(chemin) | definitions(chemin)
        vus = [n for n in noms if "relink" in n.lower()]
        assert vus, f"{nom} : la frontiere ne VOIT pas cet ecran de relink"

    # Et un module sain reste sain : la mesure ne rougit pas sur tout.
    sain = tmp_path / "sain.py"
    sain.write_text("class EcranPasEncore:\n    pass\n", encoding="utf-8")
    assert [n for n in identifiants(sain) | definitions(sain)
            if "relink" in n.lower()] == []


def test_le_palier_n_appelle_JAMAIS_cli_py():
    """AC 5.2 : `cli.py` imprime sur `stderr` et rend un code retour.

    L'appeler depuis une TUI enverrait des lignes **sous** l'ecran dessine, et
    rendrait un entier la ou l'interface a besoin d'un document ou d'un refus
    nomme. Mesure a l'AST, pas au texte : le docstring du module explique
    justement pourquoi il ne le fait pas, et un grep y mordrait.
    """
    from outils_frontiere import identifiants

    noms = identifiants(Path(palier_projet.__file__))
    fautifs = [n for n in noms if n.endswith("cli") or n.endswith(".cli")]
    assert fautifs == [], fautifs


# ---------------------------------------------------------------------------
# AC 5.2 et 5.3 -- `set-default-profile`, et la couture avec Scan
# ---------------------------------------------------------------------------

def test_le_profil_pose_est_celui_que_SCAN_lira(tmp_path):
    """AC 5.3, et c'est le coeur de la story.

    La cible est le **troisieme** profil : un appel fautif qui prendrait
    toujours le premier fichier d'un dossier resterait vert autrement.
    """
    projet = creer_projet(tmp_path, "projet_demo").chemin
    profils = _profils_externes(tmp_path)

    pose = palier_projet.poser_le_profil_par_defaut(projet, profils[2])

    entree, chemin = palier_projet.profil_par_defaut(projet)
    assert entree is not None
    assert chemin is not None and chemin.is_file()
    assert pose.chaine == CHAINES[2]
    assert pose.chemin == chemin


def test_l_artefact_est_celui_du_coeur_et_non_une_seconde_ecriture(tmp_path):
    """AC 5.2, contrat d'artefact : le fichier ecrit sous
    `versions/calibration/` est **exactement** le document du coeur."""
    projet = creer_projet(tmp_path, "projet_demo").chemin
    profils = _profils_externes(tmp_path)

    pose = palier_projet.poser_le_profil_par_defaut(projet, profils[1])

    ecrit = json.loads(pose.chemin.read_text(encoding="utf-8"))
    origine = json.loads(profils[1].read_text(encoding="utf-8"))
    assert ecrit["chain_id"] == origine["chain_id"]
    assert ecrit["coefficients"] == origine["coefficients"]


def test_un_profil_venu_DE_N_IMPORTE_OU_est_accepte(tmp_path):
    """`EPIC5-ARB-82` : « aucun refus lie au projet » d'ou vient le profil.

    Le profil vit ici dans un dossier qui n'est **pas** sous le projet, et qui
    n'est meme pas un projet.
    """
    projet = creer_projet(tmp_path, "projet_demo").chemin
    profils = _profils_externes(tmp_path)
    assert "ailleurs" in str(profils[0])
    assert not (profils[0].parent / "project.json").exists()

    pose = palier_projet.poser_le_profil_par_defaut(projet, profils[0])
    assert pose.chaine == CHAINES[0]


def test_aucun_test_de_PROVENANCE_dans_le_module(tmp_path):
    """`EPIC5-ARB-82`, frontiere : rien ici ne regarde d'ou vient le fichier."""
    from outils_frontiere import chaines_de_code

    textes = chaines_de_code(Path(palier_projet.__file__))
    interdits = ("hors du projet", "profil etranger", "provenance")
    assert [t for t in textes
            if any(mot in t.lower() for mot in interdits)] == []


def test_une_cible_qui_n_est_pas_un_projet_est_refusee(tmp_path):
    """AC 5.2, troisieme point : le refus porte sur **la cible**, jamais sur la
    provenance du profil. Le distinguo est celui du coeur, il se reprend."""
    pas_un_projet = tmp_path / "juste_un_dossier"
    pas_un_projet.mkdir()
    profils = _profils_externes(tmp_path)

    with pytest.raises(palier_projet.CibleSansProjet) as refus:
        palier_projet.poser_le_profil_par_defaut(pas_un_projet, profils[0])
    # Le refus NOMME la cible, et dit explicitement qu'il ne porte pas sur le
    # profil : c'est le distinguo d'`EPIC5-ARB-82`, et il est dans le message.
    assert "project.json" in str(refus.value)
    assert "porte sur la cible" in str(refus.value)
    # **Rien n'a ete ecrit** : le refus tombe AVANT l'appel au coeur.
    assert list(pas_un_projet.iterdir()) == []


def test_le_refus_de_cible_n_existe_PAS_dans_le_coeur(tmp_path):
    """Volet symetrique, et c'est lui qui justifie `CibleSansProjet`.

    `import_designated_profile` ecrit sans broncher dans n'importe quel
    dossier : la garde vit dans `cli.py`, **avant** l'appel. Un appelant qui
    passe par `io/` -- ce que la TUI doit faire, `cli.py` imprimant sur
    `stderr` et rendant un code retour -- la saute entierement, et poserait une
    arborescence `versions/calibration/` dans un dossier quelconque.

    **Si le coeur venait a porter la garde, ce test tomberait** et forcerait a
    retirer la duplication, au lieu de la laisser survivre en silence. C'est la
    forme « tolerance qui se relit » plutot que « tolerance qu'on oublie ».
    """
    pas_un_projet = tmp_path / "encore_un_dossier"
    pas_un_projet.mkdir()
    profils = _profils_externes(tmp_path)

    profile_designation.import_designated_profile(
        pas_un_projet, profils[0], as_default=True)
    assert (pas_un_projet / "versions").is_dir(), (
        "le coeur refuse desormais une cible sans projet : retirer "
        "CibleSansProjet de tui/palier_projet.py et cette duplication")


def test_reposer_un_profil_remplace_le_precedent(tmp_path):
    """Le geste de l'operateur qui redesigne. La cible du second appel n'est ni
    la meme ni la premiere : un remplacement fautif se verrait."""
    projet = creer_projet(tmp_path, "projet_demo").chemin
    profils = _profils_externes(tmp_path)

    palier_projet.poser_le_profil_par_defaut(projet, profils[0])
    palier_projet.poser_le_profil_par_defaut(projet, profils[2])

    entree, _ = palier_projet.profil_par_defaut(projet)
    assert CHAINES[2] in json.dumps(entree), entree


# ---------------------------------------------------------------------------
# L'ecran
# ---------------------------------------------------------------------------

def test_l_ecran_montre_les_deux_entrees_et_leur_phrase(tmp_path, banc):
    projet = creer_projet(tmp_path, "projet_demo").chemin
    ecran = palier_projet.EcranPalierProjet(dossier=projet)

    async def scenario(pilote):
        return _texte(ecran)

    rendu = _monte(_app(ecran), scenario, banc)
    for cle in (palier_projet.ENTREE_PROFIL,
                palier_projet.ENTREE_RECONSTRUCTION):
        assert palier_projet.LIBELLES[cle] in rendu, rendu
        assert palier_projet.PHRASES[cle][:30] in rendu, rendu


def test_valider_par_REFLEXE_suit_la_premiere_entree_sans_ECRIRE(tmp_path, banc):
    """`EPIC11-ARB-7` : « il ne veut pas que la touche reste muette »."""
    projet = creer_projet(tmp_path, "projet_demo").chemin
    entres = []
    ecran = palier_projet.EcranPalierProjet(dossier=projet,
                                            entrer=entres.append)

    async def scenario(pilote):
        ecran.traiter("enter")
        return ecran.etat()

    etat = _monte(_app(ecran), scenario, banc)
    # `EPIC11-ARB-45` : la validation suit le curseur, elle n'est plus muette.
    # Les TROIS entrees du palier menent a un ecran qui LIT avant toute
    # ecriture (`EPIC11-ARB-4`), donc suivre la premiere par reflexe n'ecrit
    # rien -- c'est la forme que garde `EPIC11-ARB-7`. La premiere est
    # desormais la gestion des medias, dont le premier ecran est l'inventaire.
    assert [issue.cle for issue in entres] == [palier_projet.ENTREE_MEDIAS]
    assert all(not issue.ecrit for issue in entres)
    assert etat == ""


def test_choisir_la_DERNIERE_entree_declenche_LA_DERNIERE(tmp_path, banc):
    """La cible est en QUEUE : ni la premiere, ni au milieu.

    Un `valider` fautif qui rendrait `issues[0]` resterait vert sur une cible
    de tete ; un balayage TRONQUE -- qui saute la derniere entree -- resterait
    vert sur une cible du milieu. Ce sont deux modes de panne distincts, et le
    second ne se demasque qu'au bord (regle des fabriques, point 4).
    """
    projet = creer_projet(tmp_path, "projet_demo").chemin
    entres = []
    ecran = palier_projet.EcranPalierProjet(dossier=projet,
                                            entrer=entres.append)

    async def scenario(pilote):
        ecran.traiter("down")
        ecran.traiter("down")
        ecran.traiter("space")
        ecran.traiter("enter")

    _monte(_app(ecran), scenario, banc)
    assert [i.cle for i in entres] == [palier_projet.ENTREE_RECONSTRUCTION]


def test_l_ecran_dit_TROIS_etats_du_profil_par_defaut(tmp_path, banc):
    """Aucun profil ; un profil present ; un profil dont le fichier a disparu.

    Le troisieme n'est **pas** le premier : `default_profile_path` rend `None`
    quand le fichier a disparu, mais « l'entree de manifest reste vraie de ce
    que le projet a utilise ». Le taire ferait croire qu'il n'y en a jamais eu.
    """
    projet = creer_projet(tmp_path, "projet_demo").chemin
    ecran = palier_projet.EcranPalierProjet(dossier=projet)

    async def scenario(pilote):
        return list(ecran.lignes_du_profil())

    aucun = _monte(_app(ecran), scenario, banc)
    assert aucun == ["aucun profil de calibration par defaut"]

    profils = _profils_externes(tmp_path)
    pose = palier_projet.poser_le_profil_par_defaut(projet, profils[2])
    ecran_pose = palier_projet.EcranPalierProjet(dossier=projet)

    async def scenario_pose(pilote):
        return list(ecran_pose.lignes_du_profil())

    present = _monte(_app(ecran_pose), scenario_pose, banc)
    assert any(jetons.GLYPHES["complete"] in ligne for ligne in present), present

    pose.chemin.unlink()
    ecran_disparu = palier_projet.EcranPalierProjet(dossier=projet)

    async def scenario_disparu(pilote):
        return list(ecran_disparu.lignes_du_profil())

    disparu = _monte(_app(ecran_disparu), scenario_disparu, banc)
    assert any(jetons.GLYPHES["substitute"] in ligne for ligne in disparu), disparu
    assert disparu != aucun
    assert disparu != present


def test_l_ecran_tient_le_plancher_80x24(tmp_path, banc):
    projet = creer_projet(tmp_path, "projet_demo").chemin
    profils = _profils_externes(tmp_path)
    palier_projet.poser_le_profil_par_defaut(projet, profils[2])
    ecran = palier_projet.EcranPalierProjet(dossier=projet)

    async def scenario(pilote):
        return _texte(ecran)

    rendu = _monte(_app(ecran), scenario, banc)
    lignes = rendu.splitlines()
    assert len(lignes) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, len(lignes)
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne


# ---------------------------------------------------------------------------
# AC 5.4 et 5.5 -- `reconstruct-project`, et le panneau chiffre qui le precede
# ---------------------------------------------------------------------------

from mixed_media_utility.io import payload as payload_io  # noqa: E402


def _payload_de_page(page_index: int, page_count: int = 3,
                     lot_id: str = "lot-001") -> dict:
    """Un payload de page, a la forme **exacte** du contrat 2.0.

    Meme fabrique que `test_reconstruct_cli.py` : la version est **lue au
    contrat** et non ecrite en litteral -- un litteral decrirait une planche que
    le lecteur refuse.
    """
    return {
        "schema_version": payload_io.PAYLOAD_SCHEMA_VERSION,
        "project_id": "example-001",
        "rush_id": "rush-001",
        "lot_id": lot_id,
        "page_index": page_index,
        "page_count": page_count,
        "page_role": payload_io.PAGE_ROLE_IMAGES,
        "fps_target": 24.0,
        "timecode_base_fps": "25/1",
        "template_id": "template-a4-16x9",
        "patch_preset_id": "patch-preset-mvp",
        "target_colorspace": "rec709",
        "gamut_map_id": "gamut-map-none-1",
        "slots": [{"slot_index": page_index,
                   "frame_timecode": f"00:00:0{page_index}:00"}],
    }


def _trois_pages(tmp_path) -> list[Path]:
    """**Trois** fichiers de payload, distinguables par leur page.

    Ils sont ecrits par `serialize_payload`, le **vrai** producteur du texte
    imprime : un `json.dumps` nu ecrirait un document qu'aucun tirage ne porte
    et que le parseur refuse comme perime.
    """
    dossier = tmp_path / "qr_lus"
    dossier.mkdir(parents=True, exist_ok=True)
    chemins = []
    for page in range(3):
        chemin = dossier / f"page_{page}.txt"
        chemin.write_text(
            payload_io.serialize_payload(_payload_de_page(page)),
            encoding="utf-8")
        chemins.append(chemin)
    return chemins


def test_les_payloads_passent_par_parse_payload_et_non_par_json_loads(tmp_path):
    """AC 5.4, et le defaut est deja paye une fois.

    La commande lisait autrefois un `json.loads` nu, donc exigeait un document a
    cles **longues** -- exactement celui que `parse_payload` refuse comme
    perime. Aucune entree ne satisfaisait les deux cotes a la fois.

    La mesure : le texte ecrit par le **vrai** producteur (cles courtes) se lit,
    et le `json.dumps` du dictionnaire a cles longues est **refuse**.
    """
    pages = _trois_pages(tmp_path)
    documents = palier_projet.lire_les_payloads(pages)
    assert len(documents) == 3
    assert [d["page_index"] for d in documents] == [0, 1, 2]

    a_cles_longues = tmp_path / "faux.txt"
    a_cles_longues.write_text(json.dumps(_payload_de_page(0)), encoding="utf-8")
    with pytest.raises(Exception):
        palier_projet.lire_les_payloads([a_cles_longues])


def test_un_fichier_de_payload_absent_est_refuse_AVANT_toute_lecture(tmp_path):
    pages = _trois_pages(tmp_path)
    with pytest.raises(palier_projet.PayloadIntrouvable) as refus:
        palier_projet.lire_les_payloads(pages[:2] + [tmp_path / "nulle_part.txt"])
    assert "nulle_part" in str(refus.value)


def test_l_apercu_n_ECRIT_RIEN(tmp_path):
    """AC 5.5 / `EPIC11-ARB-4` : « rien n'est ecrit avant ce panneau ».

    Comptage a zero, avec volet symetrique juste apres.
    """
    projet = tmp_path / "a_reconstruire"
    projet.mkdir()
    pages = _trois_pages(tmp_path)

    apercu = palier_projet.apercu_de_reconstruction(projet, pages)

    assert apercu.pages == 3
    assert apercu.rushes == 1
    assert apercu.lots == 1
    assert list(projet.iterdir()) == [], "l'apercu a ecrit sur le disque"


def test_l_ecriture_MORD_la_ou_l_apercu_ne_mordait_pas(tmp_path):
    """Volet symetrique du precedent : sans lui, le comptage a zero serait vert
    meme si la reconstruction n'ecrivait jamais rien."""
    projet = tmp_path / "a_reconstruire"
    projet.mkdir()
    pages = _trois_pages(tmp_path)

    ecrit = palier_projet.reconstruire_le_projet(projet, pages)

    assert ecrit.chemin.is_file()
    assert list(projet.iterdir()) != []


def test_l_apercu_et_l_ecriture_donnent_LES_MEMES_CHIFFRES(tmp_path):
    """C'est ce qui empeche le panneau de mentir.

    `reconstruct_project_manifest` est une couche pure : l'apercu et l'ecriture
    partagent litteralement le meme calcul. Deux calculs distincts pourraient
    diverger, et c'est le panneau -- le point de jugement -- qui mentirait.
    """
    projet = tmp_path / "a_reconstruire"
    projet.mkdir()
    pages = _trois_pages(tmp_path)

    apercu = palier_projet.apercu_de_reconstruction(projet, pages)
    ecrit = palier_projet.reconstruire_le_projet(projet, pages)

    assert (apercu.pages, apercu.rushes, apercu.lots) == \
           (ecrit.pages, ecrit.rushes, ecrit.lots)


def test_le_project_json_reconstruit_VALIDE_au_schema_du_coeur(tmp_path):
    """L'ecriture atomique du coeur valide un temporaire AVANT de le mettre en
    place : un document que le coeur refuserait ne peut pas atterrir."""
    from mixed_media_utility.io.manifest import validate_manifest

    projet = tmp_path / "a_reconstruire"
    projet.mkdir()
    ecrit = palier_projet.reconstruire_le_projet(projet, _trois_pages(tmp_path))
    assert validate_manifest(ecrit.chemin)["schema_version"]


@pytest.mark.parametrize("fabrique, attendu", [
    ("reconstruction", ("Pages lues", "Rushes reconstruits", "Lots reconstruits")),
    ("profil", ("Chaine de scan", "Forme de correction")),
])
def test_les_panneaux_portent_leurs_lignes_chiffrees(tmp_path, fabrique, attendu):
    """AC 5.5 : les deux commandes ecrivent, donc les deux passent par le
    panneau chiffre de la story 11.1. **Aucun second panneau n'est ecrit ici.**"""
    if fabrique == "reconstruction":
        projet = tmp_path / "a_reconstruire"
        projet.mkdir()
        panneau = palier_projet.panneau_de_reconstruction(
            palier_projet.apercu_de_reconstruction(projet, _trois_pages(tmp_path)))
    else:
        projet = creer_projet(tmp_path, "projet_demo").chemin
        apercu = palier_projet.apercu_de_profil(
            projet, _profils_externes(tmp_path)[2])
        panneau = palier_projet.panneau_de_profil(apercu)

    libelles = [ligne.libelle for ligne in panneau.lignes]
    for libelle in attendu:
        assert libelle in libelles, libelles


def test_aucun_panneau_du_palier_ne_porte_de_MAJORANT(tmp_path):
    """Les trois comptes sont **mesures** sur un manifest deja calcule, pas
    estimes. Un majorant ici mentirait sur sa propre precision."""
    projet = tmp_path / "a_reconstruire"
    projet.mkdir()
    panneau = palier_projet.panneau_de_reconstruction(
        palier_projet.apercu_de_reconstruction(projet, _trois_pages(tmp_path)))
    assert not panneau.porte_un_majorant


def test_l_apercu_de_profil_n_ECRIT_RIEN(tmp_path):
    """AC 5.5 / `EPIC11-ARB-4` : « rien n'est ecrit avant ce panneau ».

    Un panneau construit sur le resultat de la pose serait un panneau **de
    resultat** portant le titre « A ecrire » : il ne pourrait plus rien
    empecher. Comptage a zero, volet symetrique juste apres.
    """
    projet = creer_projet(tmp_path, "projet_demo").chemin
    avant = sorted(chemin.name
                   for chemin in (projet / "versions").rglob("*.json"))

    apercu = palier_projet.apercu_de_profil(projet, _profils_externes(tmp_path)[2])

    apres = sorted(chemin.name
                   for chemin in (projet / "versions").rglob("*.json"))
    assert apres == avant == []
    assert palier_projet.profil_par_defaut(projet)[0] is None
    assert apercu.chaine == CHAINES[2]


def test_la_pose_MORD_la_ou_l_apercu_ne_mordait_pas(tmp_path):
    """Volet symetrique : sans lui, le comptage a zero resterait vert meme si
    la pose n'ecrivait jamais rien."""
    projet = creer_projet(tmp_path, "projet_demo").chemin
    palier_projet.poser_le_profil_par_defaut(projet, _profils_externes(tmp_path)[2])
    assert sorted(chemin.name
                  for chemin in (projet / "versions").rglob("*.json")) != []
    assert palier_projet.profil_par_defaut(projet)[0] is not None


def test_l_apercu_et_la_pose_annoncent_LES_MEMES_TROIS_VALEURS(tmp_path):
    """C'est ce qui empeche le panneau de mentir.

    Le chemin est le point sensible : son radical est l'etiquette du document
    quand il en porte une, son `chain_id` sinon. Une seconde formule ecrite
    cote TUI divergerait au premier profil etiquete -- meme defaut que du cote
    de `EcranCreation`, et il est deja paye ici.
    """
    projet = creer_projet(tmp_path, "projet_demo").chemin
    source = _profils_externes(tmp_path)[2]

    apercu = palier_projet.apercu_de_profil(projet, source)
    pose = palier_projet.poser_le_profil_par_defaut(projet, source)

    assert (apercu.chaine, apercu.forme, apercu.chemin) ==            (pose.chaine, pose.forme, pose.chemin)


def test_l_apercu_refuse_une_cible_SANS_PROJET_avant_de_lire_la_source(tmp_path):
    """La garde de cible vaut des l'apercu, sinon un panneau s'afficherait pour
    une ecriture qui sera refusee juste apres."""
    pas_un_projet = tmp_path / "dossier_quelconque"
    pas_un_projet.mkdir()
    with pytest.raises(palier_projet.CibleSansProjet):
        palier_projet.apercu_de_profil(pas_un_projet,
                                       tmp_path / "meme_pas_un_fichier.json")
