# -*- coding: utf-8 -*-
"""Story 11.5, lot E bis -- la QUATRIEME forme de source (AC 3.6, reecrite).

**Ce banc et lui seul mesure le lot E bis.** La regle de decoupage de la fiche
est stricte et elle a ete payee trois fois sur ce depot : « aucun lot ne partage
un fichier de banc avec un autre ». `git add -N` et `git commit -- <chemins>`
protegent par FICHIER, jamais a l'interieur d'un fichier.

**Ce que ce lot ferme.** `EPIC7-ARB-88` compte quatre formes d'entree -- un
dossier d'images, un PDF, une image seule, et **une sequence de chemins qui fait
UN lot**. La quatrieme etait injoignable depuis la TUI : l'explorateur validait
une entree et n'avait aucune selection multiple. La story 11.2c la lui a donnee
le 2026-08-31, et sa ligne de sprint dit mot pour mot « elle debloque la
QUATRIEME forme de source de `scan` ». `E3-1` est le site qui la consomme.

**Regle des fabriques** (`CLAUDE.md`), appliquee ici a ses trois points :

1. **au moins deux elements distinguables** -- les sources d'une selection
   portent des noms ET des poids differents. Deux fichiers de meme taille
   rendraient invisible une ligne qui afficherait le poids du voisin ;
2. **la cible n'est jamais en premiere position** -- les mesures de vocabulaire
   et de poids visent `RANG_DE_LA_CIBLE`, qui n'est pas `0` ;
3. **trois elements et la cible AU MILIEU des qu'une boucle compte** -- la liste
   des sources est **parcourue** par `lignes_des_sources`, et le filtre d'un
   dossier coche est parcouru par `_fichiers_du_dossier` : les deux fabriques
   portent donc trois elements et placent leur cible au rang du milieu, verifie
   sur la liste que le code PARCOURT et non sur celle que la fabrique ecrit.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import scan_ingest
from mixed_media_utility.tui import atelier_scan, ecran_projet, jetons
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Les maquettes du depot, lues **sur le disque** : une mesure qui recopierait
#: leur texte ne mesurerait plus que sa propre copie.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")

#: Le rang de la source visee par les mesures de vocabulaire et de poids : **le
#: second des trois**, donc ni le premier (un `sources[0]` fautif y survivrait)
#: ni le dernier (un `continue` -> `break` y survivrait).
RANG_DE_LA_CIBLE = 1

#: Les trois poids de la fabrique, en octets, **tous differents**. L'ecart est
#: large : une ligne qui prendrait le poids du voisin se lirait a l'oeil nu dans
#: le rouge d'un test, et `taille_lisible` ne les arrondit pas au meme mot.
POIDS = (3_000, 17_000, 41_000)


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def _image(chemin: Path, octets: int) -> Path:
    """Une source d'un poids EXACT, sans passer par un encodeur d'image.

    Le contenu n'a pas a etre une image lisible : le seul chemin de coeur que ce
    banc traverse est `mesurer_la_source`, qui pese les fichiers et lit leur dpi
    par `_measure_file_dpi` -- laquelle rend `None` sur tout ce qu'elle n'ouvre
    pas, sans lever. Peindre trois TIFF reels donnerait des poids qu'on ne
    choisit pas, et c'est **le poids** que ces mesures confrontent.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(b"\x00" * octets)
    return chemin


def _pdf_de_trois_pages(chemin: Path) -> Path:
    """Un PDF REEL de trois pages -- le compte doit sortir du document.

    Contrairement a :func:`_image`, le contenu ne peut pas etre du remplissage :
    le cardinal d'une selection melangee se lit en OUVRANT le PDF
    (`scan_ingest._cardinal_des_pages`), et un faux PDF y compterait pour une
    page par la branche de secours -- le banc serait alors vert sur un produit
    qui ne sait pas compter les pages d'un PDF.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdfcanvas

    chemin.parent.mkdir(parents=True, exist_ok=True)
    canevas = pdfcanvas.Canvas(str(chemin), pagesize=A4)
    for rang in range(3):
        canevas.setFillColorRGB(1, 0, 0)
        canevas.rect(100, 400 + rang, 300, 300, stroke=0, fill=1)
        canevas.showPage()
    canevas.save()
    return chemin


def _trois_sources(tmp_path, dossier="prestataire") -> list[Path]:
    """Trois sources distinguables, dans l'ordre d'AFFICHAGE de l'explorateur.

    Les noms sont choisis pour que le tri de l'explorateur -- sans accent, nom
    par nom -- rende exactement cet ordre : la cible du milieu doit etre au
    milieu de la liste que le code parcourt, pas de celle que ce fichier ecrit.
    """
    racine = tmp_path / dossier
    return [_image(racine / f"planche_{rang + 1:02d}.tiff", poids)
            for rang, poids in enumerate(POIDS)]


def _huit_sources(tmp_path) -> list[Path]:
    """Huit sources : **trois de plus que la zone n'en montre**.

    `HAUTEUR_DES_SOURCES` vaut cinq, et le `…` de tete en mange une des qu'on a
    defile : il faut donc plus de cinq sources pour que le defilement existe, et
    assez pour que la borne haute se distingue d'un `total - hauteur` naif.
    """
    racine = tmp_path / "lot_long"
    return [_image(racine / f"planche_{rang + 1:02d}.tiff", 1_000 * (rang + 1))
            for rang in range(8)]


def _app(ecran, **kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                    contexte=Contexte(projet="projet_demo"), **kwargs)


def _monte(app, scenario, banc):
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def _texte(ecran) -> str:
    """Le texte **tel qu'il s'affiche**, balises de couleur retirees."""
    return jetons.texte_affiche(str(ecran._corps.content))


def _depot_avec(sources, tmp_path=None, ascii_seul=False):
    """Un `E3-1` dont la source designee est la SELECTION donnee.

    La designation passe par `designer`, donc par le coeur : c'est lui qui rend
    la forme, et l'ecran ne la redecide jamais (`EPIC7-ARB-88`).
    """
    ecran = atelier_scan.EcranScanDepot()
    ecran.formulaire.poser_la_source(atelier_scan.designer(list(sources)))
    return ecran


def _lignes_rendues(ecran, banc, ascii_seul=False) -> list[str]:
    async def scenario(_pilote):
        ecran.rafraichir()
        return _texte(ecran).splitlines()

    return _monte(_app(ecran, ascii_seul=ascii_seul), scenario, banc)


def _ligne_de_maquette(nom: str, rang: int) -> str:
    """Le contenu d'une ligne de maquette, cadre et marges retires."""
    lignes = (MAQUETTES / nom).read_text(encoding="utf-8").split("\n")
    return lignes[rang - 1][1:-1].strip()


# ===========================================================================
# Eb1 -- le site monte l'explorateur en mode selection, et le dit
# ===========================================================================

def test_E3_1_monte_l_explorateur_en_mode_SELECTION_sans_perdre_ses_reglages():
    """AC 3.6 : le site demande `selection_multiple`, **et les deux autres
    reglages restent ce qu'ils etaient**.

    L'assertion porte sur les trois reglages a la fois plutot que sur le seul
    qui change : un montage qui gagnerait la selection en perdant son `accepte`
    accepterait n'importe quel fichier comme source, et aucune mesure du lot B
    ne le verrait -- elles portent sur le rendu, pas sur le cablage.
    """
    ecran = atelier_scan.EcranScanDepot()
    exp = ecran.explorateur
    assert exp.selection_multiple is True
    assert exp.montrer_fichiers is True
    # Le predicat est celui du module, **par identite de fonction** : une copie
    # de la regle d'extensions divergerait au premier format ajoute au coeur.
    assert exp._accepte is atelier_scan.source_acceptable


def test_le_champ_de_source_dit_SOURCES_MULTIPLES_et_jamais_un_chemin(
        tmp_path, banc):
    """Eb1, note 5 d'Egan verbatim : « si fichiers multiples on dit *sources
    multiples* ».

    La mesure est **negative en plus d'etre positive** : aucun des trois noms
    n'apparait dans la ligne du champ. Un ecran qui y ecrirait le premier chemin
    de la sequence ferait passer une designation de trois planches pour une
    seule, et une assertion qui se contenterait de chercher « sources
    multiples » ailleurs dans l'ecran ne le verrait pas.
    """
    sources = _trois_sources(tmp_path)
    ecran = _depot_avec(sources)
    lignes = _lignes_rendues(ecran, banc)
    champ = [l for l in lignes if atelier_scan.LIBELLE_SOURCE in l]
    assert len(champ) == 1, lignes
    assert atelier_scan.LIBELLE_SOURCES_MULTIPLES in champ[0], champ
    assert [s.name for s in sources if s.name in champ[0]] == [], champ


def test_le_resume_dit_SOURCES_MULTIPLES_puis_le_compte_et_le_poids(tmp_path):
    """Eb1 et Eb2 : la tete nomme la designation, la suite dit ce qu'elle pese.

    Egalite de chaine **entiere** et non recherche de morceaux : « le resume
    contient *sources multiples* » laisserait passer n'importe quel ordre et
    n'importe quel separateur, alors que c'est la ligne que l'operateur lit
    avant de lancer une passe.
    """
    source = atelier_scan.designer(list(_trois_sources(tmp_path)))
    # Le poids est ecrit **en toutes lettres** et non derive de
    # `taille_lisible(sum(POIDS))` : la deriver rendrait ce test tautologique --
    # il mesurerait la fonction par elle-meme, et le survivant de la story 5.9
    # est ne exactement de ce geste. 61 000 octets font 60 ko en base 1024.
    assert atelier_scan.resume_de_la_source(source) == (
        f"{atelier_scan.LIBELLE_SOURCES_MULTIPLES} · 3 fichiers · 60 ko")
    assert sum(POIDS) == 61_000, "et la fabrique pese bien ce qu'on croit"


def test_la_liste_navigable_est_EN_DESSOUS_du_resume(tmp_path, banc):
    """« en dessous la liste navigable » (note 5) : l'ORDRE est mesure.

    Une liste posee au-dessus du resume, ou entre les champs, satisferait toute
    mesure de presence. Le rang se lit sur les lignes rendues.
    """
    sources = _trois_sources(tmp_path)
    lignes = _lignes_rendues(_depot_avec(sources), banc)
    rang_resume = next(r for r, l in enumerate(lignes)
                       if l.strip().startswith(
                           atelier_scan.LIBELLE_SOURCES_MULTIPLES + " ·"))
    rangs = [next(r for r, l in enumerate(lignes) if s.name in l)
             for s in sources]
    assert rangs == sorted(rangs), (rangs, lignes)
    assert min(rangs) > rang_resume, (rang_resume, rangs, lignes)


def test_chaque_source_porte_SON_poids_et_pas_celui_d_une_autre(
        tmp_path, banc):
    """Eb1 : « a cote d'un fichier juste son poids » (note 5).

    **La cible est la source du MILIEU**, et les trois poids sont differents :
    une ligne qui prendrait `sources[0]`, ou qui decalerait l'appariement d'un
    rang, se demasque ici et nulle part ailleurs. C'est le mutant `M33` de la
    story 5.6 -- l'appariement positionnel inverse que 165 tests laissaient
    passer parce que toutes les fabriques remplissaient uniformement.
    """
    sources = _trois_sources(tmp_path)
    lignes = _lignes_rendues(_depot_avec(sources), banc)
    cible = sources[RANG_DE_LA_CIBLE]
    ligne = next(l for l in lignes if cible.name in l)
    from mixed_media_utility.tui.explorateur import taille_lisible
    assert taille_lisible(POIDS[RANG_DE_LA_CIBLE]) in ligne, ligne
    # Et elle ne porte AUCUN des deux autres poids : l'ensemble des poids lus
    # sur cette ligne est exactement celui de sa source.
    autres = [taille_lisible(p) for rang, p in enumerate(POIDS)
              if rang != RANG_DE_LA_CIBLE]
    assert [p for p in autres if p in ligne] == [], (ligne, autres)


def test_une_designation_d_un_SEUL_element_n_est_PAS_multiple(tmp_path):
    """La forme est **lue du coeur**, jamais deduite de la longueur.

    `scan_ingest._reconnaitre_la_source` ramene une sequence d'un element au cas
    a un chemin. Un ecran qui deciderait « multiple » sur `len(...) > 1` dirait
    la meme chose ; sur `len(...) >= 1`, il annoncerait « sources multiples »
    pour une image seule cochee. La mesure porte donc sur la forme rendue.
    """
    sources = _trois_sources(tmp_path)
    seule = atelier_scan.designer([sources[RANG_DE_LA_CIBLE]])
    assert seule.est_multiple is False
    assert seule.forme == scan_ingest.FORME_IMAGE
    assert seule.chemin == sources[RANG_DE_LA_CIBLE]
    assert atelier_scan.LIBELLE_SOURCES_MULTIPLES not in \
        atelier_scan.resume_de_la_source(seule)


# ===========================================================================
# Eb2 -- le cardinal et le poids sont ceux de la SELECTION (`EPIC11-ARB-123`)
# ===========================================================================

def test_le_compte_d_un_dossier_coche_est_CE_QUE_LE_SCAN_PRENDRA(tmp_path,
                                                                 banc):
    """`EPIC11-ARB-123`, mesure **sur le site reel** et non sur le composant.

    Le filtre `accepte` du site s'applique a l'interieur d'un dossier coche, et
    les caches en sont exclus. La fabrique porte **trois** entrees dans le
    dossier -- une image retenue, un `.txt` refuse **au milieu**, une image
    cachee -- parce que `_fichiers_du_dossier` les PARCOURT : une cible en tete
    ou en queue laisserait vivre une faute de terminaison de boucle.

    Ce que ce test ajoute a ceux de la 11.2c : ils mesurent le composant avec un
    `accepte` de banc. Celui-ci mesure `atelier_scan.source_acceptable`, c'est-a-
    dire la table d'extensions du coeur, sur l'explorateur que `E3-1` monte.
    """
    dossier = tmp_path / "rushes"
    retenue = _image(dossier / "aa_planche.tiff", POIDS[0])
    _image(dossier / "mm_notes.txt", POIDS[1])          # refuse par `accepte`
    _image(dossier / ".zz_cachee.tiff", POIDS[2])       # cachee

    ecran = atelier_scan.EcranScanDepot()
    exp = ecran.explorateur
    exp.dossier = dossier.parent
    exp.relire()
    rangs = [e.chemin.name for e in exp.entrees]
    exp.curseur = rangs.index("rushes")
    assert exp.basculer_la_coche() is None, "le dossier se coche"

    from mixed_media_utility.tui.explorateur import taille_lisible
    ligne = exp.ligne_de_validation()
    assert "1 fichier" in ligne, ligne
    assert taille_lisible(retenue.stat().st_size) in ligne, ligne
    # Et il ne compte NI le refuse NI le cache : l'ensemble des poids possibles
    # est mesure, pas seulement celui qu'on attend.
    for exclu in (POIDS[1], POIDS[2], POIDS[0] + POIDS[1],
                  POIDS[0] + POIDS[1] + POIDS[2]):
        assert taille_lisible(exclu) not in ligne, (exclu, ligne)


def test_le_poids_du_resume_est_la_somme_EXACTE_des_sources_listees(
        tmp_path, banc):
    """Eb2 : les deux moities de l'ecran repondent au **meme** ensemble.

    C'est le defaut que `EPIC11-ARB-123` ferme, sous sa forme locale : la ligne
    du bas et la colonne de droite « repondaient a deux questions differentes
    avec deux nombres differents, simultanement a l'ecran ». Ici le total du
    resume est confronte a la somme de ce que les lignes affichent.
    """
    sources = _trois_sources(tmp_path)
    designee = atelier_scan.designer(list(sources))
    assert sum(octets for _, octets in designee.sources) == \
        designee.mesure.octets == sum(POIDS)
    assert designee.cardinal == len(sources)


def test_le_cardinal_annonce_est_celui_de_la_SELECTION_et_non_du_DOSSIER(
        tmp_path, banc):
    """Note 4 d'Egan : le resume compte la selection, pas le contenu du dossier.

    Le dossier porte cinq images, deux sont designees : c'est `2` que l'ecran
    annonce. Un ecran qui mesurerait le dossier parent dirait `5`, ce qui est
    exactement la mesure que la maquette `X6` portait avant ce lot.
    """
    racine = tmp_path / "vrac"
    toutes = [_image(racine / f"p{rang}.tiff", 1_000 + rang)
              for rang in range(5)]
    designee = atelier_scan.designer([toutes[1], toutes[3]])
    assert designee.cardinal == 2
    assert atelier_scan.resume_de_la_source(designee).startswith(
        f"{atelier_scan.LIBELLE_SOURCES_MULTIPLES} · 2 fichiers · ")


# ===========================================================================
# `EPIC7-ARB-88` -- aucune coercition : la selection part TELLE QUELLE
# ===========================================================================

def test_la_selection_part_au_coeur_TELLE_QUELLE(tmp_path, banc):
    """`EPIC7-ARB-88` : « c'est l'ingestion qui distingue les quatre formes, et
    elle seule ».

    L'ecran ne compose pas un dossier commun, ne garde pas le premier chemin, et
    ne trie pas : il passe la sequence. L'assertion porte sur la **liste
    entiere** -- une egalite, pas une appartenance --, sinon un appelant qui
    n'enverrait que la premiere source la satisferait.
    """
    sources = _trois_sources(tmp_path)
    recu = []
    ecran = atelier_scan.EcranScanDepot(
        detecter=lambda chemin, dpi: recu.append((chemin, dpi)))
    ecran.formulaire.poser_la_source(atelier_scan.designer(list(sources)))
    ecran.formulaire.dpi = "600"

    async def scenario(pilote):
        # **Le geste passe par la ligne `Valider`**, atteinte par `Tab` --
        # retour terrain d'Egan du 2026-09-06 : `⏎` sur le champ de dpi
        # descend desormais, il ne lance plus.
        ecran.formulaire.champ = atelier_scan.CHAMP_DPI
        ecran.traiter("enter")
        assert recu == [], "⏎ sur le dpi ne lance plus : il descend"
        while ecran.formulaire.champ != atelier_scan.CHAMP_VALIDER:
            ecran.traiter("tab")
        ecran.traiter("enter")
        await pilote.pause()

    _monte(_app(ecran), scenario, banc)
    assert recu == [(list(sources), 600)], recu
    # Et ce n'est ni un dossier ni un chemin unique : la forme survit au trajet.
    assert not isinstance(recu[0][0], Path), recu


def test_un_DOSSIER_parmi_plusieurs_sources_est_refuse_par_le_COEUR_verbatim(
        tmp_path, banc):
    """Le refus vient du coeur, **il est rendu mot pour mot, et rien n'est
    pose**.

    C'est la contrepartie de « aucune coercition » : l'ecran n'ecarte pas le
    dossier pour faire passer la selection -- ce serait ingerer autre chose que
    ce que l'operateur a coche --, il laisse l'ingestion refuser et affiche son
    motif (`EPIC11-ARB-30`).
    """
    sources = _trois_sources(tmp_path)
    dossier = tmp_path / "un_dossier"
    dossier.mkdir()
    ecran = atelier_scan.EcranScanDepot()
    exp = ecran.explorateur
    exp.dossier = tmp_path / "prestataire"
    exp.relire()
    for entree in exp.entrees:
        if entree.chemin in (sources[0], sources[RANG_DE_LA_CIBLE]):
            exp.curseur = exp.entrees.index(entree)
            exp.basculer_la_coche()
    exp._selection[dossier] = True
    exp._resolu[dossier] = {}

    async def scenario(pilote):
        ecran.zone = atelier_scan.ZONE_EXPLORATEUR
        ecran._valider_l_explorateur()
        await pilote.pause()
        return ecran._etat_a_dire

    dit = _monte(_app(ecran), scenario, banc)
    assert "Un dossier s'ingere en designant le dossier" in dit, dit
    assert ecran.formulaire.source is None, "rien n'est pose sur un refus"


def test_designer_MESURE_avant_de_coercer_et_ne_leve_aucun_TypeError(tmp_path):
    """Le piege deja paye a `scan_detect.py:250-260`, sous sa forme locale.

    `SourceDesignee(Path(chemin), mesurer(chemin))` evalue l'argument de GAUCHE
    d'abord : une sequence y levait un `TypeError` nu **avant** que le coeur ait
    pu la reconnaitre -- « un message Python affiche sur une carte de tache » a
    la place d'un motif lisible. La mesure passe donc avant toute coercition, et
    ce test le verifie sur une sequence que le coeur REFUSE : c'est le seul
    regime ou l'ordre des deux se voit.

    **Le refus employe ici a change de nature le 2026-09-01, et il fallait le
    changer.** Ce banc tenait sa sequence refusee d'un PDF glisse au milieu
    d'images -- un refus qu'`EPIC11-ARB-157` a supprime. Il est repose sur le
    seul refus de selection que cet arbitrage **conserve explicitement** : un
    dossier n'entre pas dans une selection, « il est deja une forme d'entree a
    lui seul ». Choisir ce refus-la n'est pas indifferent : il est stable par
    construction, la ou tout refus d'EXTENSION est susceptible d'etre leve au
    prochain format accepte -- ce qui vient exactement d'arriver a celui-ci.

    Le refus est en position CENTRALE dans la sequence : en tete, un code qui
    ne regarderait que le premier element serait vert pour la mauvaise raison.
    """
    intrus = tmp_path / "prestataire" / "un_dossier"
    intrus.mkdir(parents=True, exist_ok=True)
    sources = _trois_sources(tmp_path)
    with pytest.raises(scan_ingest.ScanIngestError) as refus:
        atelier_scan.designer([sources[0], intrus, sources[2]])
    assert "ne porte que des pages" in str(refus.value), str(refus.value)
    assert "un_dossier" in str(refus.value)


def test_un_PDF_EST_desormais_une_source_parmi_plusieurs(tmp_path):
    """`EPIC11-ARB-157` -- et ce banc disait exactement l'inverse avant lui.

    Il mesurait que « le coeur refuse un PDF a l'interieur d'une selection »,
    et en tirait que la moitie « nombre de pages » de la note 5 d'Egan etait
    **inatteignable**. C'etait vrai, et c'est precisement ce qui l'a bloque :
    il avait coche un seul PDF. Egan a tranche le 2026-09-01 -- « on doit tout
    accepter : pdf seul, dans un dossier, avec des images ... tout en vrac ».

    Ce que le banc mesure desormais, et c'est plus fort que « ca ne leve
    plus » : le cardinal de la selection compte les PAGES des deux natures
    reunies. Le PDF porte trois pages et l'image une, la selection en annonce
    **quatre** -- un cardinal qui rendrait `2` (les fichiers) serait vert sous
    une assertion « ca ne leve pas » et faux a l'ecran.

    Le PDF est en SECONDE position dans la designation et **premier** dans
    l'ordre du tri (`p_planches` contre `t_planche`), pour que la mesure ne
    puisse pas etre confondue avec celle d'un appariement positionnel.
    """
    dossier = tmp_path / "vrac"
    dossier.mkdir(parents=True, exist_ok=True)
    autre = _image(dossier / "t_planche.tiff", POIDS[0])
    pdf = _pdf_de_trois_pages(dossier / "p_planches.pdf")

    source = atelier_scan.designer([autre, pdf])
    assert source.forme == scan_ingest.FORME_SELECTION
    assert source.cardinal == 4
    assert source.fichiers == 2
    # Le mot suit ce que le nombre compte : quatre pages sur deux fichiers ne
    # se dit pas « 4 fichiers ».
    assert atelier_scan.unite_du_cardinal(source) == "page"


def test_un_dossier_d_IMAGES_dit_toujours_FICHIER(tmp_path):
    """Le volet symetrique : `EPIC11-ARB-26` n'a pas bouge la ou il mordait.

    L'elargissement ne doit rien emporter avec lui. Un dossier qui ne porte que
    des images a autant de pages que de fichiers, et il continue de dire
    « fichier » -- c'est le cas nominal, et c'est celui qu'une regle ecrite
    trop large aurait casse en silence.
    """
    dossier = tmp_path / "que_des_images"
    dossier.mkdir(parents=True, exist_ok=True)
    for rang, poids in enumerate(POIDS[:3]):
        _image(dossier / f"planche_{rang}.tiff", poids)

    source = atelier_scan.designer(dossier)
    assert source.cardinal == source.fichiers == 3
    assert atelier_scan.unite_du_cardinal(source) == "fichier"


def test_l_ecran_retient_la_SELECTION_et_non_l_entree_sous_le_curseur(
        tmp_path, banc):
    """Finding 1 de la revue de la 11.2c, renvoye **nommement** a cette story.

    « `valider()` s'elargit, `cible_de_validation()` non -- et un site lit la
    seconde. » La ligne du bas annonce la selection ; si l'ecran lisait la cible,
    il retiendrait autre chose que ce qu'il vient de promettre.

    La fabrique le rend visible : les deux sources cochees sont la **premiere**
    et celle du **milieu**, et le curseur est laisse sur la **derniere**, qui
    n'est pas cochee. Un ecran qui lirait la cible poserait une source unique --
    et une fabrique qui aurait laisse le curseur sur une entree cochee ne
    distinguerait pas les deux lectures.
    """
    sources = _trois_sources(tmp_path)
    ecran = atelier_scan.EcranScanDepot()
    exp = ecran.explorateur
    exp.dossier = tmp_path / "prestataire"
    exp.relire()
    noms = [e.chemin.name for e in exp.entrees]
    for rang in (0, RANG_DE_LA_CIBLE):
        exp.curseur = noms.index(sources[rang].name)
        exp.basculer_la_coche()
    exp.curseur = noms.index(sources[2].name)
    assert exp.est_cochee(sources[2]) is False, "le curseur est sur une NON cochee"

    async def scenario(pilote):
        ecran.zone = atelier_scan.ZONE_EXPLORATEUR
        ecran._valider_l_explorateur()
        await pilote.pause()

    _monte(_app(ecran), scenario, banc)
    posee = ecran.formulaire.source
    assert posee is not None and posee.est_multiple, posee
    assert [c for c, _ in posee.sources] == [sources[0],
                                             sources[RANG_DE_LA_CIBLE]]


# ===========================================================================
# Le defilement -- celui de l'explorateur, et sa borne haute
# ===========================================================================

def test_la_DERNIERE_source_est_atteignable_par_defilement(tmp_path, banc):
    """La borne haute est `total - hauteur + 1`, et **pas** `total - hauteur`.

    La ligne `…` de tete se reserve dans la hauteur des qu'on a defile : la
    borne « evidente » laisserait la derniere source cachee derriere le `…` qui
    annonce justement qu'elle existe. C'est le motif ecrit de
    `jetons.fenetre_de_liste`, et il ne se mesure qu'en marchant jusqu'au bout.
    """
    sources = _huit_sources(tmp_path)
    ecran = _depot_avec(sources)

    async def scenario(pilote):
        vues = set()
        for _ in range(20):
            ecran.rafraichir()
            await pilote.pause()
            texte = _texte(ecran)
            vues |= {s.name for s in sources if s.name in texte}
            ecran.traiter("down")
        return vues, ecran.formulaire.premier_visible

    vues, premier = _monte(_app(ecran), scenario, banc)
    assert vues == {s.name for s in sources}, sorted(vues)
    assert premier == len(sources) - atelier_scan.HAUTEUR_DES_SOURCES + 1


def test_le_defilement_est_BORNE_des_deux_cotes(tmp_path, banc):
    """Ni au-dessus de la premiere source, ni au-dela de la derniere.

    Les deux bornes sont mesurees : une seule laisserait vivre la moitie du
    mutant. Et la touche rend **faux** quand rien ne bouge -- l'ecran ne se
    repeint pas pour rien, et une touche qui rendrait toujours vrai ferait
    croire a un defilement sur une liste immobile.
    """
    ecran = _depot_avec(_huit_sources(tmp_path))
    forme = ecran.formulaire
    assert forme.premier_visible == 0
    assert forme.defiler_les_sources(-1) is False
    assert forme.premier_visible == 0
    for _ in range(20):
        forme.defiler_les_sources(1)
    haut = forme.premier_visible
    assert forme.defiler_les_sources(1) is False
    assert forme.premier_visible == haut


def test_une_liste_qui_TIENT_ne_defile_pas_et_ne_l_ANNONCE_pas(tmp_path, banc):
    """Volet symetrique du precedent, sur les deux surfaces a la fois.

    Trois sources tiennent dans les cinq lignes : `↑↓` n'a rien a faire, et la
    ligne de raccourcis ne doit donc pas l'annoncer. Une touche inerte annoncee
    est indistinguable d'un clavier casse -- c'est le motif deja ecrit sur
    `_valider_le_formulaire`, applique ici.
    """
    court = _depot_avec(_trois_sources(tmp_path))
    long = _depot_avec(_huit_sources(tmp_path))

    async def scenario(pilote):
        for ecran in (court, long):
            ecran._appliquer_la_zone()
        await pilote.pause()
        return court.raccourcis, long.raccourcis

    court_ligne, long_ligne = _monte(_app(court), scenario, banc)
    assert court.formulaire.sources_defilent is False
    assert court.formulaire.defiler_les_sources(1) is False
    assert court_ligne == atelier_scan.RACCOURCIS_DEPOT
    assert long_ligne == atelier_scan.RACCOURCIS_DEPOT_MULTIPLE
    assert court_ligne != long_ligne


def test_la_liste_qui_tient_EXACTEMENT_dans_la_zone_ne_defile_pas(tmp_path):
    """La **borne** du defilement, mesuree a l'egalite et non a cote.

    Cinq sources tiennent exactement dans les cinq lignes : `fenetre_de_liste`
    les rend toutes (`total <= hauteur`). Une condition ecrite `>=` au lieu de
    `>` annoncerait un defilement qui ferait GLISSER la premiere source hors de
    vue sur une liste complete -- et une fabrique a trois et huit elements ne
    voit jamais ce rang-la. C'est le point 2 bis de la regle des fabriques
    applique a une borne plutot qu'a une position.
    """
    racine = tmp_path / "pile"
    sources = [_image(racine / f"p{rang}.tiff", 500 + rang)
               for rang in range(atelier_scan.HAUTEUR_DES_SOURCES)]
    forme = _depot_avec(sources).formulaire
    assert forme.sources_defilent is False
    assert forme.defiler_les_sources(1) is False
    assert forme.premier_visible == 0


def test_un_poids_qui_ne_se_MESURE_pas_se_dit_et_ne_vaut_pas_zero(tmp_path,
                                                                  banc):
    """`DESIGN.md` section 3 : jamais `0`, jamais une valeur devinee.

    Un `0` se lirait comme un fichier vide, c'est-a-dire comme une mesure. La
    ligne porte le glyphe d'absence, exactement comme le temps restant inconnu.
    """
    absent = tmp_path / "disparue" / "planche_99.tiff"
    assert atelier_scan.poids_du_fichier(absent) is None
    ligne = atelier_scan.ligne_d_une_source(absent, None, 76, "·")
    assert ligne.rstrip().endswith("·"), ligne
    assert "0" not in ligne, ligne


def test_la_ligne_de_position_dit_ce_qui_est_VISIBLE_sur_le_TOTAL(
        tmp_path, banc):
    """`…   1-4 sur 8` : la ligne de position de l'explorateur, pas une autre.

    Elle est ce qui rend le defilement decouvrable sans curseur. Le compte du
    haut est celui des lignes **rendues**, et le test le confronte au nombre de
    noms reellement lus -- une ligne de position qui mentirait d'un rang serait
    invisible autrement.
    """
    sources = _huit_sources(tmp_path)
    lignes = _lignes_rendues(_depot_avec(sources), banc)
    vus = [s.name for s in sources
           if any(s.name in ligne for ligne in lignes)]
    position = [l for l in lignes if " sur " in l and jetons.ELLIPSE in l]
    assert len(position) == 1, lignes
    assert f"1-{len(vus)} sur {len(sources)}" in position[0], (position, vus)


def test_un_DEFILEMENT_ENGAGE_porte_le_point_de_TETE_autant_que_de_QUEUE(
        tmp_path, banc):
    """Les deux `…` de la fenetre, et le premier est le plus facile a perdre.

    Sans le `…` de tete, la zone montre quatre sources et **ne dit pas** qu'il y
    en a au-dessus : l'operateur qui a defile croit voir le debut de son lot. La
    ligne de position, elle, reste juste -- c'est pour cela que ce defaut ne se
    voit qu'en comptant les points, jamais en lisant les chiffres.
    """
    ecran = _depot_avec(_huit_sources(tmp_path))
    for _ in range(2):
        ecran.formulaire.defiler_les_sources(1)
    lignes = _lignes_rendues(ecran, banc)
    points = [l for l in lignes if jetons.ELLIPSE in l]
    assert len(points) == 2, lignes
    assert points[0].strip() == jetons.ELLIPSE, points
    assert " sur 8" in points[1], points


def test_la_source_designee_REMET_la_liste_en_tete(tmp_path, banc):
    """Une vue gardee montrerait le milieu d'une liste de trois apres en avoir
    parcouru huit -- une zone vide, sans que rien ne le dise."""
    ecran = _depot_avec(_huit_sources(tmp_path))
    for _ in range(3):
        ecran.formulaire.defiler_les_sources(1)
    assert ecran.formulaire.premier_visible > 0
    ecran.formulaire.poser_la_source(
        atelier_scan.designer(list(_trois_sources(tmp_path))))
    assert ecran.formulaire.premier_visible == 0


# ===========================================================================
# Eb3 (volet local) -- la ligne du mode selection, et sa maquette
# ===========================================================================

def test_la_ligne_du_mode_SELECTION_est_CELLE_des_trois_maquettes_validees(
        tmp_path):
    """La ligne du produit et celle des maquettes, **lues sur le disque**.

    `Espace cocher` marchait sans qu'aucune ligne ne l'annonce (finding 2 de la
    revue de la 11.2c, « le budget est a refaire au moment ou l'ecran existe »).
    La confrontation porte sur les **trois** maquettes du mode et sur `X6`, qui
    l'a rejoint avec ce lot : une seule d'entre elles laisserait les autres
    deriver.
    """
    ligne = ecran_projet.RACCOURCIS_CHEMIN_SELECTION
    assert ligne, "anti-vacuite : la constante existe et n'est pas vide"
    for nom in ("X6-explorateur-fichiers.txt", "X10-selection-rien-coche.txt",
                "X11-selection-trois-cochees.txt",
                "X11b-selection-bas-avec-nom.txt"):
        assert _ligne_de_maquette(nom, 23) == ligne, nom
    # Elle tient la grille dans les deux regimes -- la mesure qui a fait tomber
    # `↑↓ liste`.
    assert jetons.colonnes(ligne) <= jetons.largeur_utile()
    replie = jetons.replier_ascii(ligne)
    assert replie.isascii() and jetons.colonnes(replie) <= jetons.largeur_utile()


def test_le_site_E3_1_ANNONCE_le_mode_quand_l_explorateur_est_ouvert(
        tmp_path, banc):
    """La ligne contextuelle suit la zone : c'est `DESIGN.md` section 4, « elle
    ne montre que ce qui marche sur l'ecran courant ».

    Mesure **comportementale** : on ouvre l'explorateur par le geste, et on lit
    la ligne que l'ecran porte alors. Un test qui appellerait
    `raccourcis_de_l_explorateur` directement ne mesurerait pas le cablage.
    """
    _trois_sources(tmp_path)
    ecran = atelier_scan.EcranScanDepot()
    ecran.explorateur.dossier = tmp_path / "prestataire"

    async def scenario(pilote):
        avant = ecran.raccourcis
        ecran.traiter("enter")
        await pilote.pause()
        return avant, ecran.raccourcis

    avant, apres = _monte(_app(ecran), scenario, banc)
    assert avant == atelier_scan.RACCOURCIS_DEPOT_SANS_SOURCE
    assert apres == ecran_projet.RACCOURCIS_CHEMIN_SELECTION
    assert avant != apres


# ===========================================================================
# Eb4 -- la maquette `E3-1` montre la forme multiple, `E3-1b` est intacte
# ===========================================================================

def test_la_maquette_E3_1_montre_la_forme_MULTIPLE(tmp_path):
    """Eb4 : la maquette dit ce que l'ecran fait, et sa ligne de raccourcis
    coincide au CARACTERE PRES avec la constante du produit.

    La mesure lit la maquette plutot que d'en recopier le texte : un ecart entre
    les deux est precisement ce qu'aucun test ne voyait avant la frontiere
    `F-17`. Elle rougit donc **dans les deux sens** -- une ligne de code qui
    bouge sans sa maquette, une maquette qui bouge sans son ecran.
    """
    grille = (MAQUETTES / "E3-1-scan-depot.txt").read_text(
        encoding="utf-8").split("\n")[:24]
    corps = "\n".join(grille)
    assert corps.count(atelier_scan.LIBELLE_SOURCES_MULTIPLES) == 2, corps
    assert " sur 8" in corps, "la maquette montre la liste QUI DEFILE"
    assert _ligne_de_maquette("E3-1-scan-depot.txt", 23) == \
        atelier_scan.RACCOURCIS_DEPOT_MULTIPLE


def test_la_maquette_E3_1b_ne_parle_PAS_de_sources_multiples(tmp_path):
    """Eb4, volet symetrique : `E3-1b` est l'ecran a **une** source designee.

    Sans cette mesure, une passe de maquettes qui aurait recopie `E3-1` sur
    `E3-1b` rendrait le test precedent vert tout en detruisant la seule
    maquette qui montre le vocabulaire d'un PDF (`1 PDF · 8 pages`).
    """
    corps = (MAQUETTES / "E3-1b-scan-depot-fichier-unique.txt").read_text(
        encoding="utf-8")
    assert atelier_scan.LIBELLE_SOURCES_MULTIPLES not in corps
    assert "1 PDF · 8 pages" in corps
    assert _ligne_de_maquette("E3-1b-scan-depot-fichier-unique.txt", 23) == \
        atelier_scan.RACCOURCIS_DEPOT


# ===========================================================================
# La grille et le repli -- borne de ce lot
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_depot_MULTIPLE_tient_le_plancher_80x24(tmp_path, banc, ascii_seul):
    """`EPIC11-ARB-21` : mesurer au plancher exact.

    Le formulaire multiple est le plus haut des trois etats du depot -- il
    ajoute la liste et son blanc a la ligne de reprise. Un ecran qui tient a
    100x30 et deborde a 80x24 est un defaut que seule cette taille demasque.
    """
    ecran = _depot_avec(_huit_sources(tmp_path))
    lignes = _lignes_rendues(ecran, banc, ascii_seul=ascii_seul)
    assert len(lignes) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, lignes
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne


def test_la_liste_des_sources_se_replie_en_ASCII(tmp_path, banc):
    """Le `…` de la ligne de position vaut trois colonnes en repli, pas une.

    « Le repli precede la mesure » (`jetons.points_d_abregement`) : une zone qui
    choisirait ses points APRES avoir compte deborderait de deux colonnes.
    """
    ecran = _depot_avec(_huit_sources(tmp_path))
    lignes = _lignes_rendues(ecran, banc, ascii_seul=True)
    assert all(ligne.isascii() for ligne in lignes), lignes
    position = [l for l in lignes if " sur 8" in l]
    assert len(position) == 1 and "..." in position[0], lignes
