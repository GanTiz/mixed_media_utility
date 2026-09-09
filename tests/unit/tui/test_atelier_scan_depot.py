# -*- coding: utf-8 -*-
"""Story 11.5, lot B -- le menu du Scan et le depot (AC 2, AC 3, AC 4).

**Ce banc et lui seul mesure le lot B.** La regle de decoupage de la fiche est
stricte, et elle a ete payee trois fois sur ce depot : « aucun lot ne partage un
fichier de banc avec un autre ». `git add -N` et `git commit -- <chemins>`
protegent par FICHIER, jamais a l'interieur d'un fichier -- le commit `82e64de`
du 2026-08-30 a embarque ~200 lignes du lot voisin sous un message qui parlait
d'autre chose, alors que les deux agents appliquaient la regle a la lettre.

**Regle des fabriques** (`CLAUDE.md`), appliquee ici a ses trois points :

1. **deux elements distinguables au moins** -- les deux sources de l'AC 3.4 sont
   de formes differentes (un dossier, un PDF) et de cardinaux differents, jamais
   un remplissage uniforme ;
2. **la cible n'est pas en premiere position** -- les tests de
   vocabulaire visent la SECONDE source, celle qu'un `sources[0]` raterait ;
3. **trois elements et la cible AU MILIEU des qu'une boucle compte** -- la
   mesure du dpi porte sur **toutes** les pages (`_measure_pages_dpi`), donc une
   boucle compte : le lot de l'AC 4.5 porte trois fichiers et le divergent est
   le second des trois. Et **la position se verifie sur la liste que le code
   PARCOURT** (`_discover_folder_pages`, qui trie), jamais sur celle que la
   fabrique ecrit -- c'est le finding le plus grave de la revue de la vague 3.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

_SRC = str(Path(__file__).resolve().parents[3] / "src")
#: Le pied du palier temoin. Il n'est pas invente : `E3-1` et `E3-1b` le
#: dessinent, et la confrontation en fin de fichier le verifie a leur source.
PIED_DU_PALIER = "Q quitter"

if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import scan_ingest
from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io import profile_designation
from mixed_media_utility.tui import atelier_scan, explorateur, jetons
from mixed_media_utility.tui.coque import (
    Contexte,
    CoqueTui,
    EcranPasEncore,
    PalierTemoin,
)
from mixed_media_utility.tui.ecran_projet import CoutureExplorateur

from outils_frontiere import chaines_de_code

#: Les deux regimes, portes par tout test qui touche au rendu. « Ne jamais
#: ajuster un test au code : tout test parametre porte les deux regimes. »
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le dpi que declarent les pages **saines** des fabriques, et celui de la page
#: divergente. Le divergent est plus BAS : c'est la plus basse qui borne la
#: finesse reellement disponible, et c'est elle que le coeur retient.
DPI_SAIN = 600
DPI_DIVERGENT = 300

#: Le rang de la page divergente dans le lot de trois : **le second**. Ni le
#: premier (mutant « rendre le premier »), ni le dernier (mutant `continue` ->
#: `break`, qui arrete la passe au premier ecart). Voir le point 3 du docstring.
RANG_DIVERGENT = 1

#: Le rang de la source visee par les tests de vocabulaire : **la seconde des
#: deux**. Une fabrique dont la cible est en tete laisserait vivre un
#: `sources[0]`.
RANG_DE_LA_CIBLE = 1


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def _page(chemin: Path, *, dpi: int | None, teinte: int) -> Path:
    """Une page PNG qui **declare** son dpi, ou qui n'en declare aucun.

    PNG et non TIFF, comme `test_mesure_de_dpi_avant_ingestion.py` : Pillow ne
    rend pas `info["dpi"]` d'un TIFF ecrit par `cv2.imwrite` puis resauve. La
    teinte differe d'une page a l'autre -- deux pages identiques rendraient
    toute permutation invisible, et c'est le premier point de la regle des
    fabriques.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(chemin), np.full((40, 60, 3), teinte, dtype=np.uint8))
    if dpi is not None:
        Image.open(chemin).save(chemin, dpi=(dpi, dpi))
    return chemin


def _lot_de_trois_pages(racine: Path, *, divergent: bool = True) -> list[Path]:
    """Trois pages, la divergente **au milieu** (AC 4.5).

    `divergent=False` est le **volet symetrique** : les trois pages declarent
    alors le meme dpi, et la mesure doit rendre celui-la. Sans lui, une
    implementation qui rendrait toujours `DPI_DIVERGENT` serait verte.
    """
    dpis = [DPI_SAIN, DPI_SAIN, DPI_SAIN]
    if divergent:
        dpis[RANG_DIVERGENT] = DPI_DIVERGENT
    return [_page(racine / f"page_{rang + 1:02d}.png", dpi=dpi,
                  teinte=10 + 40 * rang)
            for rang, dpi in enumerate(dpis)]


def _pdf(chemin: Path, pages: int = 8) -> Path:
    """Un PDF de `pages` pages, chacune portant une image embarquee.

    Le cardinal est un **choix de fabrique** : 8 pages est le chiffre de la
    maquette `E3-1b`, et il differe du cardinal du dossier voisin -- deux
    sources qui porteraient le meme compte rendraient invisible toute confusion
    entre elles.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    photo = chemin.parent / "photo.jpg"
    Image.fromarray(
        np.random.default_rng(0).integers(0, 255, (200, 300, 3), dtype=np.uint8)
    ).save(photo, quality=80)
    toile = pdfcanvas.Canvas(str(chemin), pagesize=A4)
    for _ in range(pages):
        toile.drawImage(ImageReader(str(photo)), 50, 400, width=300, height=200)
        toile.showPage()
    toile.save()
    return chemin


#: Le cardinal du dossier de la fabrique a deux sources, et celui du PDF. Ils
#: sont **differents** a dessein : c'est ce qui rend visible une ligne qui
#: annoncerait le compte de l'autre source.
PAGES_DU_DOSSIER = 3
PAGES_DU_PDF = 8


def _deux_sources(tmp_path) -> list[Path]:
    """Deux sources de **formes differentes**, la cible en SECONDE position.

    Un dossier de trois images d'abord, un PDF de huit pages ensuite. Les tests
    de vocabulaire visent `sources[RANG_DE_LA_CIBLE]`, c'est-a-dire le PDF : une
    fabrique qui l'aurait mis en tete laisserait vivre un `sources[0]`, et c'est
    le deuxieme point de la regle des fabriques.
    """
    dossier = tmp_path / "depot" / "planches"
    _lot_de_trois_pages(dossier, divergent=False)
    return [dossier, _pdf(tmp_path / "depot" / "planches_lot25.pdf",
                          PAGES_DU_PDF)]


def _projet(tmp_path, profil: dict | None = None, nom="projet_demo") -> Path:
    """Un projet reel, cree par le coeur, dont on complete le manifest.

    Le profil par defaut est pose **sous la forme qu'il a au manifest** -- une
    entree autoportante, telle que `record_designated_profile` l'ecrit --, et
    non par un profil de calibration complet : ce que l'AC 2.2 mesure est le
    chemin de LECTURE de l'ecran, pas le producteur du coeur, qui a son propre
    banc.
    """
    chemin = creer_projet(tmp_path, nom).chemin
    if profil is not None:
        manifeste = json.loads((chemin / "project.json").read_text(
            encoding="utf-8"))
        section = dict(manifeste.get(profile_designation.COLOR_SECTION_KEY, {}))
        section[profile_designation.DEFAULT_PROFILE_KEY] = profil
        manifeste[profile_designation.COLOR_SECTION_KEY] = section
        (chemin / "project.json").write_text(json.dumps(manifeste),
                                             encoding="utf-8")
    return chemin


#: Deux profils **distinguables**, et la cible est le second : un pied qui
#: prendrait « le premier profil du projet » se demasque. Le premier est celui
#: du registre, le second le defaut -- ce sont deux cles differentes du
#: manifest, et les confondre est exactement le defaut que `EPIC5-ARB-83`
#: ferme.
PROFIL_DU_REGISTRE = {"chain_id": "chaine-alpha",
                      profile_designation.ENTRY_SOURCE_KEY: "alpha.json"}
PROFIL_PAR_DEFAUT = {"chain_id": "chaine-zeta",
                     profile_designation.ENTRY_SOURCE_KEY:
                         "hp-envy-4520-tiff-600.json"}


def _app(ecran, projet="projet_demo", **kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Ateliers", PIED_DU_PALIER), ecran],
                    contexte=Contexte(projet=projet), **kwargs)


def _monte(app, scenario, banc):
    """Monter jusqu'a l'ecran mesure puis derouler le scenario."""
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


def _jusqu_a_valider(ecran) -> None:
    """Amener le curseur sur la ligne `Valider` **par la touche annoncee**.

    `Tab` et non une affectation directe : le retour terrain du 2026-09-06
    porte autant sur l'ACCES a la ligne que sur son existence, et un banc qui
    poserait `formulaire.champ` sauterait justement ce qu'Egan a signale. La
    boucle est bornee par le cardinal du parcours -- un `Tab` qui n'avancerait
    pas ferait une boucle infinie plutot qu'un rouge.
    """
    for _ in range(len(ecran.formulaire.champs())):
        if ecran.formulaire.champ == atelier_scan.CHAMP_VALIDER:
            return
        ecran.traiter("tab")
    assert ecran.formulaire.champ == atelier_scan.CHAMP_VALIDER, (
        "`Tab` n'atteint pas la ligne d'action", ecran.formulaire.champs())


def _rendu(ecran, banc, app=None, **kwargs) -> str:
    async def scenario(_pilote):
        return _texte(ecran)

    return _monte(app or _app(ecran, **kwargs), scenario, banc)


# ===========================================================================
# AC 2 -- le menu d'atelier, et le vocabulaire qui n'y entre pas
# ===========================================================================

def test_le_menu_du_Scan_porte_EXACTEMENT_DEUX_entrees():
    """AC 2.1, en **ensemble exact** et non en assertion positive.

    « L'ensemble des X est EXACTEMENT {...} » mesure l'exception ET son
    unicite (`CLAUDE.md`) : une assertion « Detecter est la » laisserait entrer
    une troisieme entree sans rien dire. Et c'est precisement ce qui est arrive
    -- l'entree « Recalibrer un lot ecrit » a vecu dans la fiche jusqu'a ce
    qu'Egan demande « peut-on vraiment recalibrer un lot deja ecrit ? ».
    """
    assert [e.nom for e in atelier_scan.ENTREES_DU_MENU] == [
        "Détecter des planches", "Calibrer une chaîne"]


def test_aucune_entree_ne_promet_une_RECALIBRATION_qui_n_existe_pas():
    """AC 2.1 -- `EPIC11-ARB-101`, note 2. Comptage a zero **avec son volet**.

    `cli.apply_calibration` est un talon du POC : l'entree promettait une
    capacite que le coeur n'a jamais eue. Le comptage porte sur les chaines de
    CODE du module, docstrings exclus -- le docstring de `ENTREES_DU_MENU`
    explique justement pourquoi l'entree est partie, donc il porte le mot, et un
    grep de texte s'y ferait affaiblir.
    """
    textes = chaines_de_code(Path(atelier_scan.__file__))
    assert [t for t in textes if "recalibrer" in t.lower()] == []
    # Volet symetrique : la mesure regarde bien quelque chose.
    assert "recalibrer" in "Recalibrer un lot ecrit".lower()


def test_les_deux_entrees_sont_a_l_ecran_DANS_L_ORDRE_de_la_chaine(
        tmp_path, banc):
    """AC 2.1 : l'ORDRE est mesure, pas seulement la presence -- on detecte
    avant de calibrer, et le curseur part donc sur le parcours principal."""
    ecran = atelier_scan.EcranScanMenu(dossier=_projet(tmp_path))
    rendu = _rendu(ecran, banc)
    positions = [rendu.index(e.nom) for e in atelier_scan.ENTREES_DU_MENU]
    assert positions == sorted(positions), rendu


def test_CHAQUE_entree_du_menu_est_visible_et_NOMMEE(tmp_path, banc):
    """AC 2.1 : « **visible et nommee**, jamais masquee ».

    Elle porte aussi sa phrase : une entree reduite a son nom ne dirait pas ce
    qu'elle fera, et c'est ce que l'operateur lit pour choisir.

    **Les DEUX entrees y passent, et plus seulement la seconde.** Le test
    d'origine ne regardait que « Calibrer une chaine » parce qu'elle etait la
    seule non construite ; elle est construite depuis le lot H de la story
    11.6, et la propriete qu'il mesurait -- une entree se voit et se nomme,
    qu'elle mene ou non -- vaut pour toutes.
    """
    ecran = atelier_scan.EcranScanMenu(dossier=_projet(tmp_path))
    rendu = _rendu(ecran, banc)
    for entree in atelier_scan.ENTREES_DU_MENU:
        assert entree.nom in rendu, (entree.cle, rendu)
        assert entree.phrase.split(",")[0] in rendu, (entree.cle, rendu)


def test_AUCUNE_entree_du_menu_n_est_plus_NON_CONSTRUITE(tmp_path):
    """L'ensemble des entrees non construites est **exactement vide**.

    C'est l'autre moitie du lot H : les deux ecrans que le menu annoncait sont
    livres. Une assertion sur la seule entree « calibrer » laisserait une
    troisieme entree revenir a `construite=False` sans que rien ne le dise.
    """
    assert [entree.cle for entree in atelier_scan.ENTREES_DU_MENU
            if not entree.construite] == []


def test_le_MECANISME_de_l_entree_non_construite_MORD_ENCORE(tmp_path, banc):
    """Volet symetrique, et il est la raison d'etre de ce test.

    Le mecanisme reste : « Recalibrer un lot ecrit » reviendra au menu le jour
    ou une story de coeur livrera la commande (`EPIC11-ARB-101`, note 2). En
    retirant la derniere entree qui l'employait, on l'aurait sorti de la mesure
    **en silence** -- exactement ce que les frontieres negatives de ce depot
    existent pour empecher. Il se mesure donc sur une entree **fabriquee**.

    Et l'echeance ne vient plus d'une constante de module : elle appartient a
    l'entree (`EntreeDeMenu.quand`), parce que celle qui vivait la
    (`QUAND_LA_CALIBRATION`) nommait une echeance **echue**.
    """
    demain = atelier_scan.EntreeDeMenu(
        "recalibrer", "Recalibrer un lot écrit",
        "Réappliquer un profil à des frames déjà écrites.",
        construite=False, quand="la commande de cœur qui l'applique")
    ecran = atelier_scan.EcranScanMenu(dossier=_projet(tmp_path))
    ecran.entrees = atelier_scan.ENTREES_DU_MENU + (demain,)

    async def scenario(pilote):
        ecran.traiter("down")
        ecran.traiter("down")
        ecran.traiter("enter")
        await pilote.pause()
        courant = pilote.app.screen
        return type(courant), courant.lignes()

    classe, lignes = _monte(_app(ecran), scenario, banc)
    assert classe is EcranPasEncore
    assert any(demain.nom in ligne for ligne in lignes), lignes
    assert any(demain.quand in ligne for ligne in lignes), lignes


def test_une_entree_non_construite_SANS_echeance_est_REFUSEE():
    """L'invariant qui remplace la constante : **sans la date, pas d'entree**.

    « Sans la date, on ne distingue pas "pas encore fait" de "abandonne" »
    (`EcranPasEncore`). Une echeance vide se rendrait par une ligne **absente**,
    c'est-a-dire par l'ambiguite meme que cet ecran ferme -- et elle serait
    invisible a la relecture. La construction leve donc, plutot que de laisser
    poser l'entree muette.

    Volet symetrique dans le meme test : une entree **construite** n'a pas a
    dire quand elle arrive, elle est la.
    """
    with pytest.raises(ValueError):
        atelier_scan.EntreeDeMenu("x", "X", "phrase", construite=False)
    assert atelier_scan.EntreeDeMenu("x", "X", "phrase").quand == ""


def test_l_entree_CONSTRUITE_appelle_le_rappel_injecte(tmp_path, banc):
    """AC 2.1, volet symetrique du test precedent : sans lui, un menu qui
    enverrait **les deux** entrees vers `EcranPasEncore` serait vert."""
    vues = []
    ecran = atelier_scan.EcranScanMenu(dossier=_projet(tmp_path),
                                       entrer=vues.append)

    async def scenario(pilote):
        ecran.traiter("enter")
        await pilote.pause()
        return type(pilote.app.screen)

    classe = _monte(_app(ecran), scenario, banc)
    assert [e.cle for e in vues] == ["detecter"]
    assert classe is not EcranPasEncore


def test_AUCUNE_branche_de_l_entree_du_menu_n_est_MUETTE(tmp_path, banc):
    """AC 2.1, second volet : une entree **construite** dont le rappel n'est pas
    cable ne consomme pas la touche sur rien.

    Le silence de cette branche a ete trouve par la garde des rappels cables
    (`test_rappels_cables.py`), pas par la relecture -- et c'est exactement la
    panne « une touche qui ne fait rien et ne dit rien est indistinguable d'un
    clavier casse », sept fois payee sur cet epic.
    """
    ecran = atelier_scan.EcranScanMenu(dossier=_projet(tmp_path), entrer=None)

    async def scenario(pilote):
        ecran.traiter("enter")
        await pilote.pause()
        courant = pilote.app.screen
        return type(courant), courant.lignes()

    classe, lignes = _monte(_app(ecran), scenario, banc)
    assert classe is EcranPasEncore
    assert any("Détecter des planches" in ligne for ligne in lignes), lignes


def test_le_depot_SANS_RAPPEL_de_detection_NOMME_ce_qui_manque(tmp_path, banc):
    """Meme regle sur le depot : le lot B **demande** la detection, il ne la
    lance pas. Sans rappel cable, l'ecran nomme ce qui manque plutot que
    d'avaler la validation d'un formulaire pourtant complet."""
    dossier = _deux_sources(tmp_path)[0]
    ecran = atelier_scan.EcranScanDepot(detecter=None)

    async def scenario(pilote):
        ecran.formulaire.poser_la_source(atelier_scan.designer(dossier))
        for chiffre in "600":
            ecran.traiter("", chiffre)
        # **Le geste passe par la ligne `Valider`** depuis le retour terrain du
        # 2026-09-06 : `⏎` sur le champ de dpi descend, il ne lance plus.
        _jusqu_a_valider(ecran)
        ecran.traiter("enter")
        await pilote.pause()
        courant = pilote.app.screen
        return type(courant), courant.lignes()

    classe, lignes = _monte(_app(ecran), scenario, banc)
    assert classe is EcranPasEncore
    assert any(atelier_scan.CE_QUI_MANQUE_POUR_DETECTER in ligne
               for ligne in lignes), lignes


def test_le_pied_porte_le_PROFIL_PAR_DEFAUT_du_projet(tmp_path, banc):
    """AC 2.2, et la cible n'est **pas** le premier profil du manifest.

    Deux entrees cohabitent -- le registre et le defaut --, et ce sont deux cles
    differentes. Un pied qui prendrait « le premier profil du projet » rendrait
    `chaine-alpha` ; celui-ci doit rendre le defaut, `hp-envy-4520-tiff-600`.
    """
    dossier = _projet(tmp_path, profil=PROFIL_PAR_DEFAUT)
    manifeste = json.loads((dossier / "project.json").read_text(
        encoding="utf-8"))
    section = manifeste[profile_designation.COLOR_SECTION_KEY]
    section[profile_designation.DESIGNATED_PROFILES_KEY] = [
        PROFIL_DU_REGISTRE, PROFIL_PAR_DEFAUT]
    (dossier / "project.json").write_text(json.dumps(manifeste),
                                          encoding="utf-8")

    rendu = _rendu(atelier_scan.EcranScanMenu(dossier=dossier), banc)
    assert atelier_scan.LIBELLE_DU_PROFIL in rendu, rendu
    assert "hp-envy-4520-tiff-600" in rendu, rendu
    assert "chaine-alpha" not in rendu, rendu


def test_le_pied_dit_l_ABSENCE_plutot_que_de_rester_VIDE(tmp_path, banc):
    """AC 2.2 : « ou "aucun profil designe" -- **jamais une ligne vide** ».

    Un pied absent et un pied qui dit « aucun » ne portent pas la meme
    information : le premier se lit comme un defaut d'affichage.
    """
    rendu = _rendu(atelier_scan.EcranScanMenu(dossier=_projet(tmp_path)), banc)
    assert atelier_scan.PIED_SANS_PROFIL in rendu, rendu


def test_le_pied_d_un_ecran_SANS_DOSSIER_dit_aussi_l_absence(banc):
    """AC 2.2, borne : un menu monte hors projet ne leve pas et ne se tait
    pas."""
    rendu = _rendu(atelier_scan.EcranScanMenu(dossier=None), banc)
    assert atelier_scan.PIED_SANS_PROFIL in rendu, rendu


def test_le_curseur_du_menu_teinte_l_ENTREE_ENTIERE_et_pas_sa_premiere_ligne(
        tmp_path, banc):
    """`EPIC11-ARB-101`, note 1 d'Egan : « Detecter les planches et la premiere
    ligne de description sont en bleu. Pas la seconde ligne de description. [...]
    il faut revoir la logique de colorisation pour qu'elle considere les lignes
    en entier. »

    Une ligne de continuation ne porte, par construction, aucun glyphe : aucune
    reconnaissance par motif ne peut la trouver, il faut la **donner**. La mesure
    porte donc sur l'ensemble EXACT des rangs passes a `jetons.peindre`, et sur
    le fait que l'entree tient bien sur PLUSIEURS lignes -- une entree d'une
    seule ligne rendrait la regression invisible.
    """
    ecran = atelier_scan.EcranScanMenu(dossier=_projet(tmp_path))

    async def scenario(pilote):
        utile = jetons.largeur_utile(pilote.app.size.width)
        lignes = ecran.lignes()
        premiere = ecran.rangs_du_curseur()
        hauteur = len(ecran.lignes_d_entree(0, utile))
        ecran.traiter("down")
        seconde = ecran.rangs_du_curseur()
        return lignes, premiere, seconde, hauteur

    lignes, premiere, seconde, hauteur = _monte(_app(ecran), scenario, banc)
    assert hauteur >= 2, "une entree d'une seule ligne ne mesure pas la note 1"
    assert premiere == list(range(2, 2 + hauteur)), premiere
    # Le curseur DEPLACE change l'ensemble : un `rangs_du_curseur` qui rendrait
    # toujours la premiere entree passerait l'assertion precedente.
    assert set(premiere).isdisjoint(seconde), (premiere, seconde)
    for rang in premiere + seconde:
        assert 0 <= rang < len(lignes), (rang, len(lignes))


#: Le vocabulaire de nos documents de decision, **verbatim** de l'AC 2.3 et du
#: banc du menu des ateliers (`test_ecran_ateliers.py`). Recopie ici parce que
#: c'est un inventaire ferme de trois termes et non une valeur du produit : ce
#: qui doit rester unique est la LISTE des modules mesures, pas les mots.
TERMES_DE_DOCUMENT_DE_DECISION = ("palier", "parcours a part", "feuille cli")


def test_aucun_terme_de_nos_documents_de_decision_a_l_ecran():
    """AC 2.3 -- frontiere de vocabulaire, `EPIC11-ARB-28`.

    « "Parcours a part" est du vocabulaire de document de decision : ca dit
    qu'une commande de coeur est distincte, ca ne dit a personne ou cliquer. »
    La mesure porte sur les chaines de CODE, docstrings exclus : le docstring de
    ce module parle de paliers et de parcours, et un grep de texte s'y ferait
    affaiblir a la premiere prose.
    """
    textes = chaines_de_code(Path(atelier_scan.__file__))
    fautives = [t for t in textes
                if any(mot in t.lower()
                       for mot in TERMES_DE_DOCUMENT_DE_DECISION)]
    assert fautives == [], fautives


def test_la_frontiere_de_vocabulaire_MORD():
    """AC 2.4 -- volet symetrique. Sans lui, une frontiere qui ne mesurerait
    plus rien serait verte, et c'est le seul mode de panne qu'une frontiere
    negative ne voit pas d'elle-meme.

    **Trois phrases fautives, la cible AU MILIEU** : une passe qui s'arreterait
    au premier terme trouve laisserait vivre les deux autres.
    """
    fautives = ["Remonter au palier 0",
                "Le scan est un parcours a part",
                "Voir la feuille cli"]
    trouves = [phrase for phrase in fautives
               if any(mot in phrase.lower()
                      for mot in TERMES_DE_DOCUMENT_DE_DECISION)]
    assert trouves == fautives


# ===========================================================================
# AC 3 -- un seul champ de source, trois formes, et c'est l'explorateur
# ===========================================================================

def test_le_depot_consomme_l_explorateur_LIVRE_avec_montrer_fichiers():
    """AC 3.1 : `montrer_fichiers=True`, et c'est bien LE composant livre.

    « Ecrire cinq explorateurs pour cinq ecrans serait la faute que la story
    existe pour eviter » (`explorateur.py`). `EPIC11-ARB-48` nomme `E3-1` comme
    l'un de ses cinq sites, et la 11.2b l'a livre sans le cabler ici.
    """
    ecran = atelier_scan.EcranScanDepot()
    assert isinstance(ecran.explorateur, explorateur.Explorateur)
    assert ecran.explorateur.montrer_fichiers is True


def test_le_module_du_depot_n_ecrit_AUCUN_second_explorateur():
    """AC 3.1, volet symetrique : le module ne definit aucune classe
    d'explorateur a lui. Sans cette mesure, un ecran qui reimplementerait la
    navigation a cote passerait le test precedent."""
    import ast

    arbre = ast.parse(Path(atelier_scan.__file__).read_text(encoding="utf-8"))
    classes = [n.name for n in ast.walk(arbre)
               if isinstance(n, ast.ClassDef)]
    assert [n for n in classes if "xplorateur" in n] == [], classes
    # Volet symetrique de la mesure elle-meme : elle trouve bien des classes.
    assert set(classes) >= {"EcranScanDepot", "EcranScanMenu"}, classes


@pytest.mark.parametrize("nom,retenu", [
    ("planches.tif", True),
    ("planches.tiff", True),
    ("planches.PDF", True),          # la casse ne decide de rien
    ("planches.png", True),
    ("notes.txt", False),
    ("planches.mov", False),
])
def test_le_filtre_accepte_RETIENT_ce_que_l_ingestion_sait_lire(nom, retenu):
    """AC 3.1 : « un `accepte=` qui retient les formes que l'ingestion sait
    lire ». Les extensions sont LUES du coeur : une seconde redaction
    refuserait un fichier que l'ingestion accepte."""
    assert atelier_scan.source_acceptable(Path(nom)) is retenu


def test_le_filtre_de_l_ecran_est_CELUI_LA_et_pas_un_autre(tmp_path):
    """AC 3.1 : le predicat passe a l'explorateur est bien `source_acceptable`.

    **Mesure par le comportement**, jamais par identite d'objet : c'est ce que
    l'explorateur fait de deux fichiers voisins qui compte. Un fichier hors
    filtre reste **visible** et n'est pas validable -- le masquer ferait croire
    qu'il n'est pas la, ce qui est la regle d'`Entree.validable`.

    **Deux fichiers distinguables, et le refuse en SECONDE position** : le
    fichier retenu arrive en tete apres le tri, donc un filtre qui accepterait
    tout se demasque sur le second.
    """
    depot = tmp_path / "depot"
    depot.mkdir()
    (depot / "planches.pdf").write_bytes(b"%PDF-1.4\n")
    (depot / "zzz_notes.txt").write_text("pas une source", encoding="utf-8")
    ecran = atelier_scan.EcranScanDepot()
    ecran.explorateur.dossier = depot
    ecran.explorateur.relire()

    par_nom = {e.chemin.name: e for e in ecran.explorateur.entrees}
    assert list(par_nom) == ["planches.pdf", "zzz_notes.txt"], list(par_nom)
    assert par_nom["planches.pdf"].validable is True
    assert par_nom["zzz_notes.txt"].validable is False


def test_l_ecran_HERITE_de_CoutureExplorateur_et_ne_recable_AUCUNE_touche():
    """AC 3.2 : « il herite de `CoutureExplorateur` et ne recable aucune touche
    a la main ».

    La mesure porte sur l'**identite de la fonction** : redefinir le routage
    sous le meme nom passerait un `issubclass` sans rien tenir, et c'est
    exactement la moitie de promesse que le finding `C18` a mesuree.
    """
    assert issubclass(atelier_scan.EcranScanDepot, CoutureExplorateur)
    assert (atelier_scan.EcranScanDepot._traiter_l_explorateur
            is CoutureExplorateur._traiter_l_explorateur)
    assert atelier_scan.EcranScanDepot.coller is CoutureExplorateur.coller


def test_les_DEUX_natures_se_voient_ENSEMBLE_avec_leur_mesure(tmp_path, banc):
    """AC 3.3 : `dossier · 142 fichiers`, `fichier · 78 Mo`. **Pas de selecteur
    de mode** (`EPIC11-ARB-26`) : les deux sont dans la MEME liste.

    Le dossier porte un compte de **fichiers** et non de sous-dossiers
    (`EPIC11-ARB-121` : « ce qu'on compte suit ce que le site cherche »), et le
    fichier porte sa taille.
    """
    depot = tmp_path / "depot"
    _lot_de_trois_pages(depot / "planches", divergent=False)
    _pdf(depot / "planches_lot25.pdf", PAGES_DU_PDF)
    ecran = atelier_scan.EcranScanDepot()

    async def scenario(pilote):
        ecran.explorateur.dossier = depot
        ecran.explorateur.relire()
        ecran.zone = atelier_scan.ZONE_EXPLORATEUR
        ecran.rafraichir()
        await pilote.pause()
        return _texte(ecran)

    rendu = _monte(_app(ecran), scenario, banc)
    lignes = rendu.splitlines()
    # **Ensemble exact**, et non « la ligne existe » : une seconde ligne qui
    # porterait un compte de fichiers serait une mesure de plus, sur quoi ?
    comptes = [l for l in lignes if f"{PAGES_DU_DOSSIER} fichiers" in l]
    assert len(comptes) == 1, rendu
    assert "planches/" in comptes[0], comptes[0]

    poids = explorateur.taille_lisible(
        (depot / "planches_lot25.pdf").stat().st_size)
    tailles = [l for l in lignes
               if "planches_lot25.pdf" in l and poids in l]
    assert len(tailles) == 1, rendu


@pytest.mark.parametrize("rang,attendu", [
    (0, f"{PAGES_DU_DOSSIER} fichiers"),
    (RANG_DE_LA_CIBLE, f"{PAGES_DU_PDF} pages"),
])
def test_le_resume_parle_dans_le_VOCABULAIRE_DE_LA_FORME(tmp_path, rang,
                                                          attendu):
    """AC 3.4 : « pages pour un PDF, fichiers pour un dossier ».

    **Fabrique a deux sources de formes differentes**, et le cas qui compte vise
    la SECONDE : un `sources[0]` se demasque ici. Le premier cas est le volet
    symetrique -- sans lui, un resume qui dirait toujours « pages » passerait.
    """
    sources = _deux_sources(tmp_path)
    assert RANG_DE_LA_CIBLE != 0, "la cible ne doit pas etre la premiere"
    resume = atelier_scan.resume_de_la_source(
        atelier_scan.designer(sources[rang]))
    assert attendu in resume, resume


def test_un_PDF_de_huit_pages_n_est_JAMAIS_annonce_huit_FICHIERS(tmp_path):
    """AC 3.5 : « le vocabulaire n'est pas cosmetique, et le test le dit ».

    Confondre pages et fichiers est ce qui ferait declarer un lot incomplet a
    tort. L'assertion est **negative et positive a la fois** : dire seulement
    « 8 pages est la » laisserait passer une ligne qui porterait les deux.
    """
    pdf = _deux_sources(tmp_path)[RANG_DE_LA_CIBLE]
    resume = atelier_scan.resume_de_la_source(atelier_scan.designer(pdf))
    assert f"{PAGES_DU_PDF} pages" in resume, resume
    assert f"{PAGES_DU_PDF} fichiers" not in resume, resume
    assert "1 PDF" in resume, resume


def test_une_IMAGE_SEULE_se_dit_au_SINGULIER_et_en_fichier(tmp_path):
    """AC 3.4, troisieme forme d'entree (`EPIC7-ARB-88`) : une image seule.

    Le singulier n'est pas de la cosmetique de banc : c'est la seule fabrique ou
    « 1 fichiers » se verrait, et c'est aussi la seule qui distingue
    « declarent » de « declare » dans la mention de mesure. Sans elle, un
    pluriel pose sans condition passerait -- les deux autres fabriques portent
    trois et huit elements.
    """
    seule = _page(tmp_path / "seule" / "planche.png", dpi=DPI_SAIN, teinte=30)
    source = atelier_scan.designer(seule)
    assert atelier_scan.resume_de_la_source(source).startswith("1 fichier ·")
    assert "1 fichiers" not in atelier_scan.resume_de_la_source(source)
    mention = atelier_scan.mention_de_la_mesure(source)
    assert mention == f"le fichier déclare {DPI_SAIN} dpi", mention
    assert "les 1" not in mention, mention


def test_un_PDF_D_UNE_SEULE_page_dit_LA_page_et_non_LE_fichier(tmp_path):
    """AC 3.4 / AC 4.2, volet symetrique du singulier : l'article suit l'unite.

    Les deux formes a un element doivent rendre deux phrases **differentes** :
    un article pose sans table dirait « le page », et un `unite_du_cardinal`
    devenu constant dirait « le fichier » sur un PDF. Une seule des deux
    fabriques ne ferme ni l'un ni l'autre.
    """
    source = atelier_scan.designer(_pdf(tmp_path / "une.pdf", 1))
    assert atelier_scan.resume_de_la_source(source).startswith("1 PDF · 1 page ")
    mention = atelier_scan.mention_de_la_mesure(source)
    assert mention.startswith("la page déclare "), mention
    assert "fichier" not in mention, mention


def test_le_resume_COMPTE_les_pages_et_ne_les_ENUMERE_pas(tmp_path):
    """AC 3.4, `EPIC11-ARB-101` note 6 : « Pas la peine de lister toutes les
    pages. Juste de les compter suffit non ? En ligne c'est illisible au dela
    d'un certain nombre en plus. »"""
    pdf = _deux_sources(tmp_path)[RANG_DE_LA_CIBLE]
    resume = atelier_scan.resume_de_la_source(atelier_scan.designer(pdf))
    assert "page 1" not in resume, resume
    assert f"page {PAGES_DU_PDF}" not in resume, resume


def test_le_resume_porte_le_POIDS_de_ce_qui_sera_lu(tmp_path):
    """AC 3.4 : `1 PDF · 8 pages · 1,2 Go`. Le poids est la troisieme moitie
    de la ligne, et c'est la seule qui dise ce que la passe va couter."""
    dossier = _deux_sources(tmp_path)[0]
    resume = atelier_scan.resume_de_la_source(atelier_scan.designer(dossier))
    octets = sum(c.stat().st_size for c in dossier.iterdir())
    assert explorateur.taille_lisible(octets) in resume, (resume, octets)


def test_le_resume_dit_RIEN_ENCORE_tant_qu_aucune_source_n_est_designee(
        tmp_path, banc):
    """AC 3.4, etat initial de `E3-1` : la zone « Ce qui sera lu » ne reste pas
    vide -- une zone vide se lit comme un defaut de rendu."""
    ecran = atelier_scan.EcranScanDepot(dossier=_projet(tmp_path))
    rendu = _rendu(ecran, banc)
    assert atelier_scan.TITRE_DU_RESUME in rendu, rendu
    assert atelier_scan.LIBELLE_RIEN_ENCORE in rendu, rendu


def test_designer_une_source_N_ECRIT_RIEN_sur_le_disque(tmp_path):
    """AC 3.1, et c'est l'invariant qui rend la story ouvrable : le depot
    **mesure**, il n'ingere pas.

    Mesure aux **inodes** et au `st_mtime_ns`, jamais par condensat : « une
    reecriture rend exactement les memes octets » quand la fixture est
    deterministe (`CLAUDE.md`). Un temoin est depose dans le bac a sable pour
    que la disparition d'un fichier compte comme une divergence.
    """
    sources = _deux_sources(tmp_path)
    temoin = tmp_path / "depot" / "TEMOIN.txt"
    temoin.write_text("ne doit pas bouger", encoding="utf-8")

    def empreinte():
        return {(c.relative_to(tmp_path).as_posix(), c.stat().st_ino,
                 c.stat().st_mtime_ns)
                for c in sorted(tmp_path.rglob("*")) if c.is_file()}

    avant = empreinte()
    for source in sources:
        atelier_scan.designer(source)
    assert empreinte() == avant


def test_une_source_ILLISIBLE_rend_le_motif_du_coeur_VERBATIM(tmp_path, banc):
    """AC 3.1 : le refus du coeur traverse tel quel.

    « Un motif du coeur est deja une phrase pour l'operateur, et la resumer le
    detruirait » (`EPIC11-ARB-30`). L'ecran reste sur l'explorateur : la cible
    est fautive, pas le geste.
    """
    vide = tmp_path / "vide"
    vide.mkdir()
    ecran = atelier_scan.EcranScanDepot()

    async def scenario(pilote):
        ecran.explorateur.dossier = tmp_path
        ecran.explorateur.relire()
        ecran.zone = atelier_scan.ZONE_EXPLORATEUR
        ecran.explorateur.curseur = next(
            rang for rang, e in enumerate(ecran.explorateur.entrees)
            if e.chemin == vide)
        ecran._valider_l_explorateur()
        await pilote.pause()
        return ecran.etat(), ecran.zone, ecran.formulaire.source

    etat, zone, source = _monte(_app(ecran), scenario, banc)
    # « Aucune page », et non plus « Aucune page image » : depuis
    # `EPIC11-ARB-157` le refus nomme les DEUX familles de page-fichier,
    # PDF compris. Le message disait « extensions reconnues: .png, ... »
    # sans le `.pdf`, et un operateur dont le dossier ne portait que des
    # PDF y lisait, litteralement, que le PDF n'etait pas reconnu.
    assert "Aucune page" in etat, etat
    assert ".pdf" in etat, etat
    assert zone == atelier_scan.ZONE_EXPLORATEUR
    assert source is None


# ===========================================================================
# AC 4 -- le dpi est offert, jamais pose
# ===========================================================================

def test_le_champ_de_dpi_est_VIDE_au_montage_et_marque_REQUIS(tmp_path, banc):
    """AC 4.1 : « elle **n'est pas** preremplie. Le champ reste requis, et
    **vide** » (`EPIC11-ARB-38`, verbatim)."""
    ecran = atelier_scan.EcranScanDepot(dossier=_projet(tmp_path))
    rendu = _rendu(ecran, banc)
    assert ecran.formulaire.dpi == ""
    assert atelier_scan.MENTION_REQUIS_DPI in rendu, rendu


def test_les_mentions_REQUIS_disparaissent_a_mesure_qu_on_remplit(tmp_path,
                                                                  banc):
    """AC 4.1 : la colonne des mentions dit **ce qui manque encore**.

    Une mention qui resterait une fois le champ rempli ne dirait plus rien --
    c'est la moitie que le mutant `M17` de la campagne exploitait : « requis »
    pose sans condition survivait a tous les tests, parce qu'aucun ne mesurait
    sa DISPARITION.

    La mesure est un **ensemble exact** a chacun des trois etats : rien,
    la source seule, la source et le dpi. « La mention est la » laisserait
    passer une mention de trop.
    """
    dossier = _deux_sources(tmp_path)[0]
    ecran = atelier_scan.EcranScanDepot()

    def manquantes():
        """L'ensemble des mentions que les deux champs requis affichent."""
        return {ecran.mention_du_champ(cle)
                for cle in (atelier_scan.CHAMP_SOURCE,
                            atelier_scan.CHAMP_DPI)} - {""}

    async def scenario(pilote):
        vide = manquantes()
        ecran.formulaire.poser_la_source(atelier_scan.designer(dossier))
        avec_source = manquantes()
        for chiffre in "600":
            ecran.traiter("", chiffre)
        await pilote.pause()
        return vide, avec_source, manquantes()

    vide, avec_source, complet = _monte(_app(ecran), scenario, banc)
    assert vide == {atelier_scan.MENTION_REQUIS,
                    atelier_scan.MENTION_REQUIS_DPI}, vide
    assert avec_source == {atelier_scan.MENTION_REQUIS_DPI}, avec_source
    assert complet == set(), complet


def test_la_detection_est_INACCESSIBLE_tant_que_le_dpi_est_vide(tmp_path,
                                                                banc):
    """AC 4.1 : « l'action de detection est **inaccessible** tant qu'il l'est »
    (`DESIGN.md` 7.3), et elle **dit pourquoi** -- une touche annoncee qui ne
    fait rien et ne dit rien est indistinguable d'un clavier casse."""
    lances = []
    dossier = _deux_sources(tmp_path)[0]
    ecran = atelier_scan.EcranScanDepot(
        detecter=lambda chemin, dpi: lances.append((chemin, dpi)))

    async def scenario(pilote):
        ecran.formulaire.poser_la_source(atelier_scan.designer(dossier))
        ecran.traiter("enter")
        await pilote.pause()
        return ecran.etat()

    etat = _monte(_app(ecran), scenario, banc)
    assert lances == []
    assert atelier_scan.PHRASE_DPI_REQUIS in etat, etat


def test_un_dpi_SAISI_rend_la_detection_accessible(tmp_path, banc):
    """AC 4.1, volet symetrique : sans lui, un ecran qui ne detecterait
    **jamais** serait vert. Le chemin et le dpi passes au rappel sont mesures --
    un rappel appele avec les mauvais arguments est un faux succes."""
    lances = []
    dossier = _deux_sources(tmp_path)[0]
    ecran = atelier_scan.EcranScanDepot(
        detecter=lambda chemin, dpi: lances.append((chemin, dpi)))

    async def scenario(pilote):
        ecran.formulaire.poser_la_source(atelier_scan.designer(dossier))
        for chiffre in "600":
            ecran.traiter("", chiffre)
        # `⏎` sur le champ de dpi **descend** (retour terrain du 2026-09-06) :
        # on mesure donc qu'il ne lance rien la, puis qu'il lance sur `Valider`.
        ecran.traiter("enter")
        assert lances == [], "⏎ sur le dpi ne lance plus : il descend"
        _jusqu_a_valider(ecran)
        ecran.traiter("enter")
        await pilote.pause()
        return ecran.etat()

    _monte(_app(ecran), scenario, banc)
    assert lances == [(dossier, 600)]


def test_la_mesure_est_AFFICHEE_a_cote_du_champ_et_JAMAIS_substituee(
        tmp_path, banc):
    """AC 4.2 : « affichee a cote du champ **des le depot** », et « confrontee
    au DPI declare, **jamais substituee** ».

    Les deux moities comptent : la mesure est a l'ecran ET le champ reste vide.
    Mesurer seulement la premiere laisserait vivre un champ prerempli, qui est
    exactement ce que `EPIC11-ARB-38` interdit.
    """
    dossier = _deux_sources(tmp_path)[0]
    ecran = atelier_scan.EcranScanDepot()

    async def scenario(pilote):
        ecran.formulaire.poser_la_source(atelier_scan.designer(dossier))
        ecran.rafraichir()
        await pilote.pause()
        return _texte(ecran)

    rendu = _monte(_app(ecran), scenario, banc)
    assert f"déclarent {DPI_SAIN} {atelier_scan.UNITE_DPI}" in rendu, rendu
    assert ecran.formulaire.dpi == ""
    assert ecran.formulaire.peut_detecter is False


def test_la_mention_de_mesure_parle_le_VOCABULAIRE_DE_LA_FORME(tmp_path):
    """AC 4.2 croisee avec l'AC 3.4, et c'est la meme redaction du vocabulaire.

    La cible est la SECONDE source : « les 8 pages declarent 600 dpi » sur un
    PDF, jamais « les 8 fichiers ».
    """
    sources = _deux_sources(tmp_path)
    mention = atelier_scan.mention_de_la_mesure(
        atelier_scan.designer(sources[RANG_DE_LA_CIBLE]))
    assert f"les {PAGES_DU_PDF} pages" in mention, mention
    assert "fichiers" not in mention, mention


def test_le_geste_de_reprise_est_Tab_puis_Entree_et_JAMAIS_une_lettre(
        tmp_path, banc):
    """AC 4.3, `EPIC11-ARB-68` et `EPIC11-ARB-101` note 7, tranche par Egan.

    « Aucune lettre n'est un raccourci dans un champ de saisie, **sans exception
    et sans ordre de priorite a maintenir** ». La mesure a donc **deux
    moities** : `Tab` puis `⏎` reprend la valeur, et la lettre `m` -- celle que
    la maquette proposait -- s'ECRIT dans le champ au lieu d'agir.
    """
    dossier = _deux_sources(tmp_path)[0]
    ecran = atelier_scan.EcranScanDepot()

    async def scenario(pilote):
        ecran.formulaire.poser_la_source(atelier_scan.designer(dossier))
        ecran.traiter("", "m")            # une lettre, dans le champ de dpi
        lettre_ecrite = ecran.formulaire.dpi
        ecran.formulaire.dpi = ""
        ecran.traiter("tab")              # du champ de dpi vers la reprise
        champ = ecran.formulaire.champ
        ecran.traiter("enter")
        await pilote.pause()
        return lettre_ecrite, champ, ecran.formulaire.dpi

    lettre, champ, dpi = _monte(_app(ecran), scenario, banc)
    assert lettre == "m", "une lettre frappee doit s'ecrire, jamais agir"
    assert champ == atelier_scan.CHAMP_REPRISE
    assert dpi == str(DPI_SAIN)
    assert ecran.formulaire.dpi_valide == DPI_SAIN


def test_la_reprise_N_EST_PAS_UN_CHAMP_quand_rien_n_est_mesure(tmp_path):
    """AC 4.3 / AC 4.4 : une ligne qui proposerait de reprendre ce qui n'a pas
    ete mesure serait une cible qui ne fait rien, et `Tab` s'y arreterait pour
    rien."""
    sans_mesure = tmp_path / "sans_mesure"
    _page(sans_mesure / "page_01.png", dpi=None, teinte=10)
    _page(sans_mesure / "page_02.png", dpi=None, teinte=50)
    formulaire = atelier_scan.FormulaireDuDepot()
    formulaire.poser_la_source(atelier_scan.designer(sans_mesure))
    assert formulaire.champs() == (atelier_scan.CHAMP_SOURCE,
                                   atelier_scan.CHAMP_DPI,
                                   atelier_scan.CHAMP_VALIDER)
    assert formulaire.reprendre_la_mesure() is False
    assert formulaire.dpi == ""


@pytest.mark.parametrize("ascii_seul", MODES)
def test_une_mesure_ABSENTE_ne_montre_RIEN_a_la_place(tmp_path, banc,
                                                      ascii_seul):
    """AC 4.4 : « jamais `0`, jamais `--`, jamais une valeur devinee ».

    Meme regle que le temps restant (`DESIGN.md` section 3). Les deux regimes
    sont portes : un repli ASCII qui ferait apparaitre `--` a la place du
    glyphe neutre serait exactement la valeur devinee qu'on interdit.
    """
    sans_mesure = tmp_path / "sans_mesure"
    _page(sans_mesure / "page_01.png", dpi=None, teinte=10)
    _page(sans_mesure / "page_02.png", dpi=None, teinte=50)
    ecran = atelier_scan.EcranScanDepot()

    async def scenario(pilote):
        ecran.formulaire.poser_la_source(atelier_scan.designer(sans_mesure))
        ecran.rafraichir()
        await pilote.pause()
        return _texte(ecran)

    rendu = _monte(_app(ecran, ascii_seul=ascii_seul), scenario, banc)

    def replie(texte: str) -> str:
        """Le texte tel qu'il s'affiche dans le regime mesure.

        Sans ce repli, la moitie ASCII du test cherchait `Résolution de scan`
        dans un rendu qui porte `Resolution de scan` -- elle n'aurait jamais
        rien trouve, donc jamais rien mesure.
        """
        return jetons.replier_ascii(texte) if ascii_seul else texte

    assert replie(atelier_scan.LIBELLE_REPRISE) not in rendu, rendu
    assert replie("déclare") not in rendu, rendu
    assert "0 dpi" not in rendu, rendu
    # **La mesure porte sur la LIGNE du champ de dpi**, pas sur l'ecran entier :
    # le filet de separation s'ecrit `--` en repli ASCII, et une assertion posee
    # sur tout le rendu mesurerait le filet au lieu du champ.
    libelle = replie(atelier_scan.LIBELLE_DPI)
    ligne_du_dpi = next(l for l in rendu.splitlines() if libelle in l)
    for devine in ("--", "0", "?"):
        assert devine not in ligne_du_dpi.split(libelle)[1], (devine,
                                                              ligne_du_dpi)


def test_la_mesure_porte_sur_TOUTES_les_pages_la_divergente_AU_MILIEU(
        tmp_path):
    """AC 4.5 -- **trois** fichiers, la divergence AU MILIEU.

    « La mesure porte sur toutes les pages, donc une **boucle** compte »
    (CLAUDE.md, point 2 bis). Trois mutants tombent sur cette seule fabrique :
    `paths[0]`, `max` au lieu de `min`, et une boucle qui s'arrete au premier
    ecart -- il y a une page saine APRES la divergente, donc l'arret se voit.

    **La position se verifie sur la liste que le code PARCOURT** : c'est
    `_discover_folder_pages` qui trie, et c'est son ordre qui compte, jamais
    celui dans lequel la fabrique a ecrit.
    """
    dossier = tmp_path / "trois"
    _lot_de_trois_pages(dossier)
    parcourus, _ignores = scan_ingest._discover_folder_pages(dossier)
    assert len(parcourus) == 3, parcourus
    mesures = [scan_ingest._measure_file_dpi(c) for c in parcourus]
    assert mesures[RANG_DIVERGENT] == pytest.approx(DPI_DIVERGENT, abs=1.0)
    assert RANG_DIVERGENT not in (0, len(parcourus) - 1), parcourus

    source = atelier_scan.designer(dossier)
    assert source.dpi == pytest.approx(DPI_DIVERGENT, abs=1.0)
    assert atelier_scan.dpi_lisible(source.dpi) == str(DPI_DIVERGENT)


def test_un_lot_HOMOGENE_rend_le_dpi_qu_il_declare(tmp_path):
    """AC 4.5, volet symetrique : sans lui, une implementation qui rendrait
    toujours la valeur la plus basse **connue de la fabrique** serait verte."""
    dossier = tmp_path / "trois_sains"
    _lot_de_trois_pages(dossier, divergent=False)
    source = atelier_scan.designer(dossier)
    assert source.dpi == pytest.approx(DPI_SAIN, abs=1.0)


def test_la_reprise_pose_la_mesure_DIVERGENTE_et_pas_une_autre(tmp_path):
    """AC 4.3 croisee avec l'AC 4.5 : ce que la reprise pose est **la mesure du
    lot**, pas le dpi de la premiere page.

    C'est la moitie qui manquerait a un test de reprise pose sur un lot
    homogene : les trois pages y declarent la meme chose, donc toute erreur
    d'appariement y est invisible.
    """
    dossier = tmp_path / "trois"
    _lot_de_trois_pages(dossier)
    formulaire = atelier_scan.FormulaireDuDepot()
    formulaire.poser_la_source(atelier_scan.designer(dossier))
    assert formulaire.reprendre_la_mesure() is True
    assert formulaire.dpi == str(DPI_DIVERGENT)
    assert formulaire.dpi != str(DPI_SAIN)


def test_Tab_fait_le_TOUR_des_champs_et_ne_se_bloque_nulle_part(tmp_path):
    """AC 4.1 et AC 4.3 : le formulaire tient sur quatre lignes, et `Tab` les
    parcourt en boucle -- une borne rendrait la ligne de reprise atteignable
    dans un seul sens.

    **Quatre champs, et les cibles AU MILIEU** : partir du premier et arriver au
    dernier laisserait vivre un `Tab` qui sauterait les deux du milieu.

    La quatrieme est `Valider`, ajoutee le 2026-09-06 sur retour terrain
    d'Egan -- « il manque un bouton valider [...] le seul moyen de valider est
    de faire Enter sur le DPI, pas intuitif ». C'est `Tab` et non les fleches
    qui l'atteint : `↑↓` fait defiler la liste des sources sur cet ecran.
    """
    dossier = tmp_path / "trois"
    _lot_de_trois_pages(dossier)
    formulaire = atelier_scan.FormulaireDuDepot()
    formulaire.source = atelier_scan.designer(dossier)
    formulaire.champ = atelier_scan.CHAMP_SOURCE
    vus = []
    for _ in range(5):
        vus.append(formulaire.champ)
        formulaire.avancer()
    assert vus == [atelier_scan.CHAMP_SOURCE, atelier_scan.CHAMP_DPI,
                   atelier_scan.CHAMP_REPRISE, atelier_scan.CHAMP_VALIDER,
                   atelier_scan.CHAMP_SOURCE]


def test_designer_une_source_NE_TOUCHE_PAS_au_dpi_deja_saisi(tmp_path):
    """AC 4.2 : « jamais substituee ». Une source redesignee ne doit pas
    effacer -- ni remplacer -- ce que l'operateur a frappe."""
    sources = _deux_sources(tmp_path)
    formulaire = atelier_scan.FormulaireDuDepot()
    formulaire.champ = atelier_scan.CHAMP_DPI
    for chiffre in "425":
        formulaire.frapper(chiffre)
    formulaire.poser_la_source(atelier_scan.designer(
        sources[RANG_DE_LA_CIBLE]))
    assert formulaire.dpi == "425"


@pytest.mark.parametrize("saisi", ["", "abc", "0", "-3", "60 0"])
def test_un_dpi_INVALIDE_ne_rend_JAMAIS_la_detection_accessible(saisi,
                                                                 tmp_path):
    """AC 4.1 : « vide **ou invalide** » (`DESIGN.md` 7.3). La validation est
    celle du coeur -- `scan_ingest.validate_scan_dpi` --, jamais une seconde
    regle ecrite dans l'ecran."""
    dossier = _deux_sources(tmp_path)[0]
    formulaire = atelier_scan.FormulaireDuDepot(
        source=atelier_scan.designer(dossier), dpi=saisi)
    assert formulaire.dpi_valide is None
    assert formulaire.peut_detecter is False


def test_le_plafond_de_faute_de_frappe_est_CELUI_DU_COEUR(tmp_path):
    """AC 4.1, volet symetrique du precedent : la borne n'est pas recopiee.

    Un dpi juste sous le plafond du coeur passe, un dpi juste au-dessus est
    refuse. Une seconde regle ecrite dans l'ecran accepterait une valeur que
    l'ingestion refuserait dix secondes plus tard.
    """
    dossier = _deux_sources(tmp_path)[0]
    source = atelier_scan.designer(dossier)
    sous = atelier_scan.FormulaireDuDepot(
        source=source, dpi=str(scan_ingest.MAX_SCAN_DPI))
    dessus = atelier_scan.FormulaireDuDepot(
        source=source, dpi=str(scan_ingest.MAX_SCAN_DPI + 1))
    assert sous.dpi_valide == scan_ingest.MAX_SCAN_DPI
    assert dessus.dpi_valide is None


# ===========================================================================
# Les deux ecrans tiennent la grille et le repli -- borne du lot B
# (la mesure exhaustive des sept ecrans appartient au lot F)
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_menu_et_le_depot_tiennent_le_plancher_80x24(tmp_path, banc,
                                                        ascii_seul):
    """`EPIC11-ARB-21` : mesurer au plancher exact, et pas au-dessus -- un ecran
    qui tient a 100x30 et deborde a 80x24 est un defaut que seule cette taille
    demasque. Les deux regimes sont portes."""
    dossier = _projet(tmp_path, profil=PROFIL_PAR_DEFAUT)
    source = _deux_sources(tmp_path)[RANG_DE_LA_CIBLE]
    menu = atelier_scan.EcranScanMenu(dossier=dossier)
    depot = atelier_scan.EcranScanDepot(dossier=dossier)

    async def scenario_du_depot(pilote):
        depot.formulaire.poser_la_source(atelier_scan.designer(source))
        depot.rafraichir()
        await pilote.pause()
        return _texte(depot)

    rendus = [_rendu(menu, banc, app=_app(menu, ascii_seul=ascii_seul)),
              _monte(_app(depot, ascii_seul=ascii_seul), scenario_du_depot,
                     banc)]
    for rendu in rendus:
        lignes = rendu.splitlines()
        assert len(lignes) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, lignes
        for ligne in lignes:
            assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne


def test_les_deux_lignes_de_raccourcis_du_depot_DIFFERENT_par_ce_que_fait_Entree(
        tmp_path, banc):
    """Le pied change quand une source est designee, et il ne ment sur aucun
    des deux etats.

    **Reecrit le 2026-09-06.** Il disait « `⏎` ouvre l'explorateur tant
    qu'aucune source n'est designee, et lance la detection ensuite » : la
    seconde moitie etait deja fausse d'une ligne sur deux -- le pied annoncait
    « ⏎ détecter » depuis `Source`, ou `⏎` ouvre l'explorateur. Le pied dit
    desormais le geste de la LIGNE COURANTE (`PIED_PAR_CHAMP`), et ces deux
    constantes-ci sont celles du champ de dpi, ou `⏎` ne fait que descendre :
    elles n'annoncent donc plus `⏎` du tout."""
    dossier = _deux_sources(tmp_path)[0]
    ecran = atelier_scan.EcranScanDepot()

    async def scenario(pilote):
        avant = ecran.raccourcis
        ecran.formulaire.poser_la_source(atelier_scan.designer(dossier))
        ecran._appliquer_la_zone()
        await pilote.pause()
        return avant, ecran.raccourcis

    avant, apres = _monte(_app(ecran), scenario, banc)
    assert avant == atelier_scan.RACCOURCIS_DEPOT_SANS_SOURCE
    assert apres == atelier_scan.RACCOURCIS_DEPOT
    assert avant != apres


# ===========================================================================
# La maquette que ce banc citait sans la LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E3-1` et `E3-1b` et
# n'ouvrait aucun dessin : le pied de son palier temoin en etait recopie.
# Un double dont le pied n'est pas celui du dessin mesure un ecran que
# personne n'a approuve.

#: La maquette dont le pied est repris ici, a sa source.
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


def test_le_PIED_du_palier_temoin_est_celui_des_DEUX_dessins():
    """`Q quitter` est dessine par `E3-1` ET par `E3-1b`, en fin de pied.

    Les deux ecrans du depot ont des pieds DIFFERENTS -- `E3-1` offre
    `↑↓ sources`, `E3-1b` non, parce qu'il n'a qu'un fichier -- et ils
    finissent tous deux par `Q quitter`. Mesurer les deux plutot qu'un seul
    est ce qui distingue une fin de pied commune d'une coincidence.
    """
    depot = dessin_de_la_maquette("E3-1-scan-depot.txt")
    unique = dessin_de_la_maquette("E3-1b-scan-depot-fichier-unique.txt")
    assert PIED_DU_PALIER in depot
    assert PIED_DU_PALIER in unique
    assert "↑↓ sources" in depot
    assert "↑↓ sources" not in unique


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    depot = dessin_de_la_maquette("E3-1-scan-depot.txt")
    assert PIED_DU_PALIER + " et revenir" not in depot
    assert "Q fermer" not in depot
