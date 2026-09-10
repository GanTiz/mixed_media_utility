# -*- coding: utf-8 -*-
"""Les quatre ecrans du palier 0 (story 11.2, tasks 3, 4 et 6).

**Deux regles de mesure, payees par cinq defauts a la vague 1**, et elles
gouvernent tout ce fichier :

1. le banc n'a **pas de pilote de terminal**. Un test de clavier injecte le nom
   de touche **tel que le parseur le produit** -- `alt+q` aussi bien que `q` --
   plutot que de passer par `pilote.press`, qui court-circuite la couche
   fautive ;
2. le banc n'a **pas d'ecran**. Interroger `render_strips()` FORCE le
   compositeur a recalculer, donc on voit toujours un etat coherent, y compris
   sur un ecran monte mais non redessine. Pour cette famille, on mesure
   **l'etat du widget** -- `_running`, `is_attached`, l'identite des enfants --
   et **jamais `app.rang` ni `screen.titre` seuls**.
"""
import json
import re
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.tui import (ecran_projet, explorateur, jetons,
                                     projets)
from mixed_media_utility.tui.coque import CoqueTui, PalierTemoin


# ---------------------------------------------------------------------------
# Fabriques. **Trois projets, distinguables, dates differentes** -- la regle du
# depot. Un remplissage uniforme rendrait toute permutation invisible.
# ---------------------------------------------------------------------------

DATES = ("2026-08-14T10:00:00Z", "2026-08-21T10:00:00Z", "2026-08-26T10:00:00Z")
NOMS = ("tests_calibration", "film_court_2026", "projet_demo")


def _trois_recents(tmp_path) -> tuple[list[Path], projets.Recents]:
    """Trois projets reels et leur liste, du plus ancien au plus recent.

    L'ordre des noms n'est **pas** celui des dates : `NOMS[0]` est le plus
    ancien, si bien qu'un tri fautif par nom rendrait un ordre different du tri
    par date, et se ferait voir.
    """
    chemins = [creer_projet(tmp_path, nom).chemin for nom in NOMS]
    recents = projets.Recents(tmp_path / "reglages" / "recents-v1.json")
    for chemin, date in zip(chemins, DATES):
        recents.noter_ouverture(chemin, quand=date)
    return chemins, recents


def _manifeste_de(chemin: Path, rushes: int, etats) -> None:
    """Reecrit le manifeste d'un projet deja cree, pour lui donner SES chiffres.

    Chaque projet de la liste recoit des cardinaux differents : une ligne de
    recent qui rendrait toujours ceux du premier projet reste verte tant que
    les trois projets comptent la meme chose.
    """
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": f"r{n}"} for n in range(rushes)]
    document["lots"] = [{"lot_id": f"lot_{n}", "state": etat}
                        for n, etat in enumerate(etats)]
    (chemin / "project.json").write_text(json.dumps(document), encoding="utf-8")


def _cardinaux_rendus(ligne: str) -> list[tuple[str, str]]:
    """Les couples (lettre, cardinal) **lus sur la ligne rendue**, dans l'ordre.

    On lit ce que l'operateur voit, et non les deux tuples de production :
    c'est tout l'objet de la mesure. `ligne_de_recent` joint
    `projets.LEGENDE_DES_CARDINAUX` et `Compteurs.tous` par un `zip`
    **positionnel** entre deux tuples ecrits a deux endroits differents ;
    permuter l'un des deux ne se voit que sur le rendu, et seulement si les
    cardinaux different entre eux.

    La colonne de droite est le dernier champ separe du nom par au moins deux
    espaces (`_ligne` garantit ce creux minimal) ; a l'interieur, les cinq
    jetons sont separes par ` · ` et chacun est un cardinal colle a sa lettre.
    """
    droite = re.split(r"\s{2,}", ligne.strip())[-1]
    return [(lettre, cardinal)
            for cardinal, lettre in re.findall(r"(\d+|\u00b7)([A-Z])", droite)]


def _app(ecran, **kwargs) -> CoqueTui:
    """Une coque dont le palier 0 est l'ecran mesure, et le palier 1 un temoin.

    **Deux paliers, pas un** : avec un seul, « remonter d'un palier » et
    « remonter jusqu'a la racine » seraient indistinguables -- et c'est
    exactement ce que l'AC 7 separe.
    """
    return CoqueTui(paliers=[ecran, PalierTemoin("Ateliers", "q quitter")],
                    **kwargs)


def _texte(ecran) -> str:
    """Le corps rendu de la zone centrale, en texte.

    On lit le **modele du widget** (ce qu'on lui a demande d'afficher), pas le
    compositeur : `render_strips()` recalculerait et masquerait un ecran monte
    mais non redessine (lecon de banc 2).
    """
    """Le texte **tel qu'il s'affiche**, balises de couleur retirees.

    Depuis `EPIC11-ARB-47` le widget porte du balisage : mesurer sa chaine brute
    compterait des balises comme des colonnes, et chercher un libelle dedans
    echouerait des qu'il est colore.
    """
    return jetons.texte_affiche(str(ecran._corps.content))


# ---------------------------------------------------------------------------
# AC 1 -- la liste des recents
# ---------------------------------------------------------------------------

def test_le_plus_recent_est_en_tete_a_l_ecran(tmp_path, banc):
    """AC 1.1, mesure sur le RENDU et non sur le modele seul."""
    chemins, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        return _texte(pilote.app.screen)

    rendu = banc(_app(ecran), scenario)
    positions = [rendu.index(chemin.name) for chemin in reversed(chemins)]
    assert positions == sorted(positions), rendu


def test_entree_sur_le_recent_du_MILIEU_ouvre_CELUI_LA(tmp_path, banc):
    """AC 1.2. La cible est au milieu : un `⏎` qui ouvrirait toujours le
    premier de la liste reste vert si la cible est en tete."""
    chemins, recents = _trois_recents(tmp_path)
    ouverts = []
    ecran = ecran_projet.EcranProjet(recents=recents, ouvrir=ouverts.append)

    async def scenario(pilote):
        # La liste est [projet_demo, film_court_2026, tests_calibration].
        pilote.app.screen.traiter("down")     # -> film_court_2026, le MILIEU
        pilote.app.screen.traiter("enter")

    banc(_app(ecran), scenario)
    assert ouverts == [chemins[1]], ouverts
    assert chemins[1].name == "film_court_2026"


def test_ouvrir_remonte_le_projet_en_tete_des_recents(tmp_path, banc):
    """AC 1.2, second volet : la liste est mise a jour AVANT la descente."""
    chemins, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents, ouvrir=lambda _: None)

    async def scenario(pilote):
        pilote.app.screen.traiter("down")
        pilote.app.screen.traiter("enter")

    banc(_app(ecran), scenario)
    assert recents.lire()[0].chemin == chemins[1]


def test_suppr_retire_la_ligne_et_le_dit(tmp_path, banc):
    """AC 1.3, et la phrase est mesuree : c'est elle qui leve l'ambiguite."""
    chemins, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)
    avant = sorted(p.name for p in chemins[2].rglob("*"))

    async def scenario(pilote):
        pilote.app.screen.traiter("delete")   # sur projet_demo, en tete
        pilote.app.screen.rafraichir()
        return _texte(pilote.app.screen), pilote.app.screen.etat()

    rendu, etat = banc(_app(ecran), scenario)
    assert "projet_demo" not in rendu, rendu
    assert "n'est pas touche" in etat, etat
    assert sorted(p.name for p in chemins[2].rglob("*")) == avant
    assert (chemins[2] / "project.json").is_file()


def test_la_phrase_sur_suppr_est_a_l_ecran_avant_meme_qu_on_l_utilise(tmp_path, banc):
    """AC 1.3 : « l'ecran le dit » -- avant le geste, pas apres.

    `EPIC11-ARB-39` : « c'est exactement l'ambiguite qu'un operateur redoute
    devant une touche `Suppr` posee a cote de noms de projets ». Une phrase qui
    n'apparait qu'apres coup ne leve pas cette crainte-la.
    """
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        return _texte(pilote.app.screen)

    assert "le dossier du projet n'est pas touche" in banc(_app(ecran), scenario)


def test_aucun_recent__pas_de_liste_vide_decorative(tmp_path, banc):
    """AC 1.4. Mesure sur l'ETAT de l'ecran, pas sur le texte : le curseur doit
    etre d'emblee sur le champ de chemin."""
    ecran = ecran_projet.EcranProjet(
        recents=projets.Recents(tmp_path / "vide.json"))

    async def scenario(pilote):
        return pilote.app.screen.zone, _texte(pilote.app.screen)

    zone, rendu = banc(_app(ecran), scenario)
    assert zone == ecran_projet.ZONE_CHEMIN
    # Depuis la story 11.2b, la place de la liste vide est prise par
    # l'explorateur lui-meme : il n'y a plus de phrase decorative a lire, il y a
    # des dossiers a parcourir. L'intention de l'AC est mieux tenue, pas moins.
    assert "Valider" in rendu, rendu


def test_un_recent_disparu_reste_liste_avec_sa_croix(tmp_path, banc):
    """AC 1.5. « Un disque externe debranche n'est pas un projet supprime. »"""
    chemins, recents = _trois_recents(tmp_path)
    import shutil
    shutil.rmtree(chemins[1])                       # film_court_2026 disparait

    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        return _texte(pilote.app.screen)

    rendu = banc(_app(ecran), scenario)
    assert "film_court_2026" in rendu, rendu
    assert jetons.GLYPHES["absent"] in rendu, rendu


def test_ouvrir_un_recent_disparu_ne_descend_PAS(tmp_path, banc):
    """AC 1.5, second volet : « son ouverture propose de le retirer »."""
    chemins, recents = _trois_recents(tmp_path)
    import shutil
    shutil.rmtree(chemins[2])                       # projet_demo, en tete

    ouverts = []
    ecran = ecran_projet.EcranProjet(recents=recents, ouvrir=ouverts.append)

    async def scenario(pilote):
        pilote.app.screen.traiter("enter")
        return pilote.app.screen.zone

    assert banc(_app(ecran), scenario) == ecran_projet.ZONE_REFUS
    assert ouverts == []


def test_un_projet_illisible_affiche_le_point_median_et_non_zero(tmp_path, banc):
    """AC 1.6. `·` = pas encore lu. **`0` serait un chiffre faux presente comme
    une mesure**, ce que `DESIGN.md` refuse au meme titre qu'un majorant
    presente comme mesure."""
    chemins, recents = _trois_recents(tmp_path)
    (chemins[2] / "project.json").write_text("{ casse", encoding="utf-8")

    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        largeur = jetons.largeur_utile(pilote.app.size.width)
        return pilote.app.screen.ligne_de_recent(0, largeur)

    ligne = banc(_app(ecran), scenario)
    # L'assertion porte sur les CINQ jetons de la colonne de droite, pas sur la
    # simple presence du glyphe : `0 rush` -- la forme d'avant les initiales --
    # ne peut plus apparaitre dans aucune ligne, quelle que soit la faute, et
    # une assertion qui ne peut plus echouer ne mesure plus rien.
    neutre = jetons.GLYPHES["neutre"]
    assert _cardinaux_rendus(ligne) == [(lettre, neutre) for lettre
                                        in ("R", "L", "P", "S", "M")], ligne
    assert not any(caractere.isdigit()
                   for caractere in re.split(r"\s{2,}", ligne.strip())[-1]), (
        "un projet illisible ne rend AUCUN chiffre : `0` serait faux", ligne)


def test_un_projet_vide_affiche_bien_ZERO(tmp_path, banc):
    """Volet symetrique du precedent : `0` et « non lu » ne se confondent pas."""
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        largeur = jetons.largeur_utile(pilote.app.size.width)
        return pilote.app.screen.ligne_de_recent(0, largeur)

    ligne = banc(_app(ecran), scenario)
    assert _cardinaux_rendus(ligne) == [("R", "0"), ("L", "0"), ("P", "0"),
                                        ("S", "0"), ("M", "0")], ligne


# ---------------------------------------------------------------------------
# AC 1.6 -- l'appariement lettre <-> cardinal
#
# Les cinq valeurs sont **deux a deux distinctes**, et les trois projets de la
# liste comptent **des choses differentes** : c'est la regle des fabriques du
# depot, et c'est la seule facon de voir une permutation. Les deux tests
# ci-dessus, qui rendaient cinq fois `0` puis cinq fois `·`, sont aveugles a
# celle-ci par construction.
# ---------------------------------------------------------------------------

#: Le manifeste de chaque projet, indexe par son RANG dans la liste des
#: recents (rang 0 = le plus recemment ouvert), et ce que sa ligne doit rendre.
#:
#: Le lot du milieu est celui qui porte les cinq valeurs distinctes, et la
#: liste des etats n'est pas dans l'ordre de la chaine : un comptage qui
#: suivrait le rang du lot dans la liste au lieu de son etat rendrait les
#: memes chiffres sur une fixture triee.
#:
#: 7 rushes declares ; 4 lots ; 3 ont ATTEINT `pdf` (pdf, encode, scan) ;
#: 2 ont atteint `scan` (encode, scan) ; 1 a atteint `encode`.
CARDINAUX_PAR_RANG = {
    0: ((2, ("extraction", "pdf")),
        [("R", "2"), ("L", "2"), ("P", "1"), ("S", "0"), ("M", "0")]),
    1: ((7, ("extraction", "pdf", "encode", "scan")),
        [("R", "7"), ("L", "4"), ("P", "3"), ("S", "2"), ("M", "1")]),
    2: ((9, ("encode",) * 6),
        [("R", "9"), ("L", "6"), ("P", "6"), ("S", "6"), ("M", "6")]),
}


def test_chaque_LETTRE_de_la_ligne_porte_SON_cardinal(tmp_path, banc):
    """AC 1.6, `EPIC11-ARB-55` : `7R · 4L · 3P · 2S · 1M`, dans CET ordre.

    L'appariement se fait par un `zip` positionnel entre deux tuples ecrits
    dans deux modules differents -- `projets.Compteurs.tous` d'un cote,
    `projets.LEGENDE_DES_CARDINAUX` de l'autre. Rien ne verifiait que le `P`
    est bien devant le cardinal des planches : permuter l'un ou l'autre ferait
    lire a l'operateur « 3 planches / 2 scannes » quand c'est « 2 planches /
    3 scannes », sur tout projet reel -- c'est-a-dire des que deux lots sont a
    des etats differents.

    La mesure porte sur la **ligne rendue**, pas sur le modele : c'est le seul
    endroit ou les deux tuples se rencontrent. Et elle porte sur les **trois**
    lignes, dont la cible n'est pas la premiere : une ligne qui rendrait
    toujours les cardinaux du recent de tete ne se demasque pas autrement.
    """
    chemins, recents = _trois_recents(tmp_path)
    # `_trois_recents` note du plus ancien au plus recent : le rang 0 de la
    # liste rendue est donc `chemins[2]`, et la cible du milieu `chemins[1]`.
    for rang, ((rushes, etats), _attendu) in CARDINAUX_PAR_RANG.items():
        _manifeste_de(chemins[2 - rang], rushes, etats)

    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        largeur = jetons.largeur_utile(pilote.app.size.width)
        return [pilote.app.screen.ligne_de_recent(rang, largeur)
                for rang in sorted(CARDINAUX_PAR_RANG)]

    lignes = banc(_app(ecran), scenario)
    for rang, ligne in zip(sorted(CARDINAUX_PAR_RANG), lignes):
        attendu = CARDINAUX_PAR_RANG[rang][1]
        assert _cardinaux_rendus(ligne) == attendu, (rang, ligne)

    # Volet symetrique : la ligne du milieu porte bien cinq valeurs deux a deux
    # distinctes. Sans lui, la fixture pourrait deriver vers un remplissage
    # uniforme -- et les assertions ci-dessus resteraient vertes en cessant de
    # mesurer quoi que ce soit.
    cardinaux = [valeur for _lettre, valeur in CARDINAUX_PAR_RANG[1][1]]
    assert len(set(cardinaux)) == 5, cardinaux


def test_les_cardinaux_de_la_ligne_sont_ceux_que_le_MODELE_compte(tmp_path,
                                                                  banc):
    """Second volet du precedent : l'ecran ne recopie pas une table a lui.

    Le test ci-dessus fige les chiffres attendus dans le test ; celui-ci les
    confronte a ce que `projets.compter` mesure sur le meme projet. Les deux
    ensemble disent la chose entiere : le modele compte juste, ET l'ecran
    appose la bonne lettre devant chaque cardinal.
    """
    chemins, recents = _trois_recents(tmp_path)
    (rushes, etats), attendu = CARDINAUX_PAR_RANG[1]
    _manifeste_de(chemins[1], rushes, etats)

    compteurs = projets.compter(chemins[1])
    par_champ = {"R": compteurs.rushes, "L": compteurs.lots,
                 "P": compteurs.planches, "S": compteurs.scans,
                 "M": compteurs.masters}
    assert par_champ == {lettre: int(valeur) for lettre, valeur in attendu}

    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        largeur = jetons.largeur_utile(pilote.app.size.width)
        return pilote.app.screen.ligne_de_recent(1, largeur)

    ligne = banc(_app(ecran), scenario)
    assert _cardinaux_rendus(ligne) == [
        (lettre, str(par_champ[lettre])) for lettre in ("R", "L", "P", "S", "M")
    ], ligne


# ---------------------------------------------------------------------------
# AC 3 -- le champ de chemin
# ---------------------------------------------------------------------------

def test_tab_mene_a_l_explorateur_puis_DANS_la_saisie(tmp_path, banc):
    """AC 2.6 (11.2b) : `Tab` entre dans la saisie du chemin et en sort,
    **et rien d'autre**. Contradiction relevee par Egan sur la v2 : « Le curseur
    est toujours dans la liste. D'ou la proposition : tab entre et sort de la
    saisie. »"""
    base = tmp_path / "projects"
    for nom in ("projet_demo", "projet_hiver", "projet_hiver_v2"):
        (base / nom).mkdir(parents=True)
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        cible.traiter("tab")
        assert cible.zone == ecran_projet.ZONE_CHEMIN
        assert not cible.explorateur.dans_la_saisie, "Tab ne saisit pas d'emblee"
        cible.traiter("tab")
        dans = cible.explorateur.dans_la_saisie
        cible.traiter("tab")
        return dans, cible.explorateur.dans_la_saisie

    dans, ressorti = banc(_app(ecran), scenario)
    assert dans is True
    assert ressorti is False, "Tab en SORT aussi -- sinon on y reste enferme"


def test_dans_la_saisie_les_fleches_deplacent_le_CARET_et_pas_le_dossier(
        tmp_path, banc):
    """AC 2.7 (11.2b), verbatim d'Egan : « les fleches gauche et droite peuvent
    servir a corriger une frappe et naviguer dans le texte tape »."""
    (tmp_path / "projects").mkdir()
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        cible.traiter("tab")
        cible.traiter("tab")
        exp = cible.explorateur
        avant_dossier, avant_caret = exp.dossier, exp.caret
        cible.traiter("left")
        return avant_dossier, avant_caret, exp.dossier, exp.caret

    dossier_avant, caret_avant, dossier_apres, caret_apres = banc(
        _app(ecran), scenario)
    assert caret_apres == caret_avant - 1
    assert dossier_apres == dossier_avant, "le dossier n'a PAS bouge"


def test_hors_saisie_les_fleches_naviguent_dans_l_arborescence(tmp_path, banc):
    """Volet symetrique : les memes touches, l'autre etat, l'autre effet."""
    (tmp_path / "projects" / "dedans").mkdir(parents=True)
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        cible.traiter("tab")
        exp = cible.explorateur
        exp.dossier = tmp_path / "projects"
        exp.relire()
        depart = exp.dossier
        cible.traiter("right")
        entre = exp.dossier
        cible.traiter("left")
        return depart, entre, exp.dossier

    depart, entre, remonte = banc(_app(ecran), scenario)
    assert entre == depart / "dedans"
    assert remonte == depart


def test_une_LETTRE_saute_dans_la_liste_et_ne_declenche_aucune_action(
        tmp_path, banc):
    """AC 2.4 et 2.5 (11.2b). La fabrique produit TROIS dossiers distinguables
    et la cible n'est pas en premiere position : un saut fautif qui rendrait
    toujours la premiere entree ne se demasque pas autrement."""
    base = tmp_path / "arbo"
    for nom in ("01_reperages", "azalee", "zebre"):
        (base / nom).mkdir(parents=True)
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        cible.traiter("tab")
        exp = cible.explorateur
        exp.dossier = base
        exp.relire()
        cible.traiter("", "z")
        apres_lettre = exp.entree_courante.chemin.name
        cible.traiter("", "0")
        return apres_lettre, exp.entree_courante.chemin.name, cible.zone

    lettre, chiffre, zone = banc(_app(ecran), scenario)
    assert lettre == "zebre", "la lettre saute a la TROISIEME entree"
    assert chiffre == "01_reperages", "les chiffres sautent aussi"
    assert zone == ecran_projet.ZONE_CHEMIN, "aucune lettre n'est une action"


def test_le_chemin_absolu_resolu_est_AFFICHE(tmp_path, banc, monkeypatch):
    """AC 3.3 (11.2) : montrer la saisie et valider autre chose serait un
    mensonge. Depuis la 11.2b, c'est la barre d'adresse de l'explorateur qui
    porte ce chemin, et la ligne d'etat le porte EN ENTIER.

    **Ce banc mesurait la LONGUEUR de son `tmp_path`**, et c'est le faux rouge
    du parallelisme que la vague 4 a paye (les deux couches aveugles l'ont
    formule independamment). Sous `-n 4`, `xdist` insere `popen-gwN/` dans
    `tmp_path` : le chemin passe au-dela des 76 colonnes utiles du plancher, la
    ligne d'etat l'abrege par le debut -- ce qu'elle DOIT faire --, et le test
    rougissait sur un comportement correct. En serie il passait. L'ecart ne
    disait donc rien du produit, seulement de l'endroit ou pytest avait pose son
    dossier temporaire.

    Les deux regimes sont desormais mesures **explicitement**, sur une longueur
    de chemin que ce banc FORCE au lieu de la subir :

    * fenetre calculee sur le chemin -- la ligne d'etat le porte **en entier** ;
    * fenetre au **plancher** -- elle porte le **meme** chemin, abrege par le
      DEBUT. Sans ce second volet, elargir la fenetre rendrait la premiere
      assertion vraie pour rien : une ligne d'etat vide de tout chemin ne serait
      plus demasquee que par une egalite qu'on aurait pu affaiblir.
    """
    monkeypatch.chdir(tmp_path)
    utile_au_plancher = jetons.largeur_utile(jetons.LARGEUR_PLANCHER)
    racine = str(tmp_path.resolve())
    # Le nom du dossier vise est CALCULE pour que son chemin absolu depasse a
    # coup sur la largeur utile du plancher, quelle que soit la longueur de
    # `tmp_path` -- c'est exactement ce qui rend le volet du plancher
    # deterministe en serie comme sous `-n 4`. Quand `tmp_path` est deja long
    # (le cas `xdist`), le rembourrage tombe a zero et le depassement tient de
    # lui-meme.
    rembourrage = max(utile_au_plancher + 8 - len(racine) - len("/projects"), 0)
    vise = "projects" + "_" * rembourrage
    (tmp_path / vise).mkdir()
    attendu = str((tmp_path / vise).resolve())
    assert jetons.colonnes(attendu) > utile_au_plancher, (
        "le volet du plancher n'a de sens que sur un chemin qui deborde")
    _, recents = _trois_recents(tmp_path)

    async def scenario(pilote):
        cible = pilote.app.screen
        cible.traiter("tab")
        cible.traiter("tab")
        exp = cible.explorateur
        exp.saisie, exp.caret = "", 0
        for caractere in vise:
            cible.traiter("", caractere)
        return str(exp.dossier), cible.etat()

    # Assez large pour que le chemin tienne : cadre et marges compris, c'est ce
    # que `largeur_utile` retire.
    large = max(jetons.LARGEUR_PLANCHER,
                jetons.colonnes(attendu) + 2 * jetons.BORDURE + 2 * jetons.MARGE)
    dossier, etat = banc(_app(ecran_projet.EcranProjet(recents=recents)),
                         scenario, taille=(large, 24))
    assert Path(dossier).is_absolute()
    assert dossier == attendu
    assert etat == attendu, "la ligne d'etat porte le chemin COMPLET"

    # Volet du plancher : le meme chemin, abrege PAR LE DEBUT et jamais par la
    # fin -- la fin est ce que l'operateur vient de taper.
    _, au_plancher = banc(_app(ecran_projet.EcranProjet(recents=recents)),
                          scenario)
    points = explorateur.symbole(explorateur.ELLIPSE)
    assert au_plancher != attendu, "au plancher, ce chemin ne tient pas"
    assert au_plancher.startswith(points), au_plancher
    assert attendu.endswith(au_plancher[len(points):]), (
        "abrege par le DEBUT : la queue du chemin est intacte")
    assert jetons.colonnes(au_plancher) <= utile_au_plancher


def test_un_chemin_trop_long_est_tronque_PAR_LE_DEBUT_dans_la_saisie(
        tmp_path, banc):
    """AC 5.1 et 5.2 (11.2b), sur la reserve d'Egan : « il va y avoir une saute
    c'est moyen ». Un SEUL comportement d'abregement, cale sur la fin -- ce que
    l'operateur vient de taper reste visible, la racine est ce qu'il coute le
    moins cher de perdre. C'est le seul endroit de la TUI ou l'on tronque par le
    debut, et `abreger_chemin` (qui coupe au milieu) n'a donc pas sa place ici.
    """
    profond = tmp_path.joinpath(*[f"un_dossier_au_nom_long_{n}" for n in range(6)])
    profond.mkdir(parents=True)
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        cible.traiter("tab")
        exp = cible.explorateur
        exp.dossier = profond
        exp.relire()
        cible.rafraichir()
        return _texte(cible)

    rendu = banc(_app(ecran), scenario)
    assert "un_dossier_au_nom_long_5" in rendu, "la FIN survit"
    assert "…" in rendu, rendu
    for ligne in rendu.splitlines():
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne


def test_aucune_correspondance_n_est_pas_un_refus(tmp_path, banc):
    """AC 3.5 : mesure de l'ABSENCE du glyphe, avec volet symetrique plus bas.

    `zzz_rien` n'existe ni comme dossier ni comme fichier, et c'est ce qui rend
    l'assertion encore juste depuis la story 11.15 : `ADRESSE_INEXISTANTE` ne
    couvre plus que ce qui n'existe VRAIMENT pas. Le regime symetrique -- un
    chemin de fichier colle dans ce meme ecran, qui ne montre pas les
    fichiers -- est mesure dans `test_barre_d_adresse_sur_un_fichier.py`.
    """
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        cible.traiter("tab")
        cible.traiter("tab")
        exp = cible.explorateur
        exp.saisie, exp.caret = "", 0
        for caractere in str(tmp_path / "zzz_rien"):
            cible.traiter("", caractere)
        cible.rafraichir()
        return _texte(cible), cible.zone, cible.etat()

    rendu, zone, etat = banc(_app(ecran), scenario)
    assert zone == ecran_projet.ZONE_CHEMIN
    assert etat == explorateur.ADRESSE_INEXISTANTE, etat
    assert jetons.GLYPHES["absent"] not in rendu, rendu


# ---------------------------------------------------------------------------
# AC 4 -- les trois refus et la bifurcation
# ---------------------------------------------------------------------------

def _mener_au_refus(ecran, cible) -> None:
    """Taper un chemin et valider. Le chemin est **pose caractere par
    caractere** : c'est ce que fait l'operateur, et une saisie posee d'un bloc
    sauterait la recomposition des propositions."""
    if ecran.zone == ecran_projet.ZONE_RECENTS:
        ecran.traiter("tab")               # des recents vers l'explorateur
    if not ecran.explorateur.dans_la_saisie:
        ecran.traiter("tab")               # de la liste vers la saisie
    # La saisie s'ouvre PREREMPLIE du dossier courant -- c'est ce qui permet de
    # coller par-dessus ou de corriger la fin. On la vide pour taper un chemin
    # neuf, comme l'operateur le ferait en selectionnant tout.
    ecran.explorateur.saisie, ecran.explorateur.caret = "", 0
    for caractere in str(cible):
        ecran.traiter("", caractere)
    ecran.traiter("enter")


def test_refus_dossier_sans_project_json(tmp_path, banc):
    """AC 4.1 (a)."""
    dossier = tmp_path / "rushes_bruts"
    dossier.mkdir()
    (dossier / "un_rush.mov").write_bytes(b"x")
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        _mener_au_refus(pilote.app.screen, dossier)
        pilote.app.screen.rafraichir()
        return pilote.app.screen.diagnostic, _texte(pilote.app.screen)

    diagnostic, rendu = banc(_app(ecran), scenario)
    assert diagnostic.etat == projets.SANS_PROJET
    assert "project.json" in rendu
    assert jetons.GLYPHES["absent"] in rendu


@pytest.mark.parametrize("contenu, fragment", [
    ("{ casse", "Expecting property name"),
    ('{"schema_version": "9.9"}', "is not a supported manifest schema_version"),
])
def test_refus_project_json_illisible_rend_le_motif_du_coeur(
        tmp_path, banc, contenu, fragment):
    """AC 4.1 (b) -- **un seul refus, deux motifs**, rendus VERBATIM."""
    dossier = tmp_path / "projet_casse"
    dossier.mkdir()
    (dossier / "project.json").write_text(contenu, encoding="utf-8")
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        _mener_au_refus(pilote.app.screen, dossier)
        pilote.app.screen.rafraichir()
        return pilote.app.screen.diagnostic, _texte(pilote.app.screen)

    diagnostic, rendu = banc(_app(ecran), scenario)
    assert diagnostic.etat == projets.PROJET_ILLISIBLE
    # Le motif est **replie**, pas abrege : il occupe plusieurs lignes et
    # aucun mot n'en est perdu. La comparaison se fait donc sur le texte
    # remis a plat -- assert sur la chaine contigue mesurerait la mise en
    # page, pas la preservation du motif.
    assert fragment in " ".join(rendu.split()), rendu


def test_les_trois_suites_du_refus_menent_QUELQUE_PART(tmp_path, banc):
    """AC 4.4 : « les trois menent quelque part ». Rien d'inerte."""
    dossier = tmp_path / "rushes_bruts"
    dossier.mkdir()
    (dossier / "x.mov").write_bytes(b"x")
    _, recents = _trois_recents(tmp_path)

    for cle, attendu in ((ecran_projet.ISSUE_RECENTS, ecran_projet.ZONE_RECENTS),
                         (ecran_projet.ISSUE_CORRIGER, ecran_projet.ZONE_CHEMIN)):
        crees = []
        ecran = ecran_projet.EcranProjet(recents=recents, creer=crees.append)

        async def scenario(pilote, cle=cle):
            cible = pilote.app.screen
            _mener_au_refus(cible, dossier)
            # **Viser puis valider** : depuis `EPIC11-ARB-45` la validation
            # suit le CURSEUR. `retenir(cle)` ecrivait le modele sans bouger le
            # curseur, donc la validation aurait suivi une autre issue.
            cible.choix.viser(cle)
            cible.traiter("enter")
            return cible.zone

        assert banc(_app(ecran), scenario) == attendu, cle

    crees = []
    ecran = ecran_projet.EcranProjet(recents=recents, creer=crees.append)

    async def scenario(pilote):
        cible = pilote.app.screen
        _mener_au_refus(cible, dossier)
        cible.choix.viser(ecran_projet.ISSUE_CREER)
        cible.traiter("enter")

    banc(_app(ecran), scenario)
    assert crees == [dossier.resolve()], crees


def test_un_reflexe_de_validation_n_ECRIT_rien(tmp_path, banc):
    """AC 4.4 / `EPIC11-ARB-7`, et `⏎` par reflexe ne declenche RIEN."""
    dossier = tmp_path / "rushes_bruts"
    dossier.mkdir()
    (dossier / "x.mov").write_bytes(b"x")
    _, recents = _trois_recents(tmp_path)
    crees = []
    ecran = ecran_projet.EcranProjet(recents=recents, creer=crees.append)

    async def scenario(pilote):
        cible = pilote.app.screen
        _mener_au_refus(cible, dossier)
        assert cible.choix.retenue is None, "rien n'est retenu au montage"
        sous_le_curseur = cible.choix.issues[cible.choix.curseur]
        cible.traiter("enter")                    # reflexe
        return cible.zone, sous_le_curseur

    zone, sous_le_curseur = banc(_app(ecran), scenario)
    # `EPIC11-ARB-45` : la validation n'est plus muette, elle suit le curseur.
    # Ce que `EPIC11-ARB-7` garde est mesure ici : **l'issue sous le curseur au
    # montage n'ecrit pas**. Un reflexe ouvre donc le formulaire de creation --
    # qui EST le panneau de confirmation (`EPIC11-ARB-46`) --, il n'ecrit rien.
    assert sous_le_curseur.ecrit is False
    assert sous_le_curseur.cle == ecran_projet.ISSUE_CREER, (
        "sur un dossier sans project.json, le geste nominal est « creer ici » "
        "(EPIC11-ARB-40)")
    assert crees, "l'issue mene quelque part -- elle ouvre le formulaire"
    assert not (dossier / "project.json").exists(), (
        "un reflexe a ecrit un projet ; il ne doit qu'OUVRIR le formulaire")


def test_le_curseur_ne_retient_rien_en_passant(tmp_path, banc):
    """`EPIC11-ARB-7` : « parcourir n'est pas choisir »."""
    dossier = tmp_path / "rushes_bruts"
    dossier.mkdir()
    (dossier / "x.mov").write_bytes(b"x")
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        _mener_au_refus(cible, dossier)
        cible.traiter("down")
        cible.traiter("down")
        cible.traiter("up")
        return cible.choix.retenue

    assert banc(_app(ecran), scenario) is None


def test_un_dossier_ABSENT_bifurque_sans_etre_un_refus(tmp_path, banc):
    """`EPIC11-ARB-40`, et c'est le renversement que la story porte."""
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        _mener_au_refus(cible, tmp_path / "pas_encore_la")
        cible.rafraichir()
        return cible.diagnostic, _texte(cible)

    diagnostic, rendu = banc(_app(ecran), scenario)
    assert diagnostic.etat == projets.ABSENT_A_CREER
    assert not diagnostic.est_un_refus
    assert jetons.GLYPHES["absent"] not in rendu, rendu
    assert "Creer un projet ici" in rendu


def test_un_dossier_VIDE_bifurque_sans_croix(tmp_path, banc):
    """AC 4.3 : « un dossier vide n'est pas une anomalie, c'est un point de
    depart »."""
    vide = tmp_path / "tout_neuf"
    vide.mkdir()
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        _mener_au_refus(cible, vide)
        cible.rafraichir()
        return cible.diagnostic, _texte(cible)

    diagnostic, rendu = banc(_app(ecran), scenario)
    assert diagnostic.etat == projets.VIDE_A_CREER
    assert jetons.GLYPHES["absent"] not in rendu, rendu


def test_aucun_ecran_du_palier_zero_n_affiche_une_LIGNE_DE_COMMANDE(tmp_path):
    """AC 4.5 -- frontiere de comptage a zero, `EPIC11-ARB-22`.

    « Un refus qui affiche a l'operateur la ligne de commande qu'il aurait du
    taper. Sur le premier ecran, au premier lancement, pour le premier geste :
    c'est exactement la decouverte que la TUI existe pour supprimer. »
    """
    from outils_frontiere import chaines_de_code

    source = Path(ecran_projet.__file__)
    sous_commandes = ("extract", "scan", "makepdf", "encode", "previz",
                      "relink", "reconstruct-project", "set-default-profile")
    fautives = [texte for texte in chaines_de_code(source)
                if any(f"mmu {commande}" in texte for commande in sous_commandes)]
    assert fautives == [], fautives


def test_la_frontiere_de_ligne_de_commande_MORD():
    """Volet symetrique : une phrase fautive doit sortir de la mesure."""
    sous_commandes = ("extract", "scan", "makepdf")
    fautive = "Aucun projet ici. Lancez `mmu extract --project ...` d'abord."
    assert any(f"mmu {commande}" in fautive for commande in sous_commandes)


def test_aucun_refus_ne_propose_de_REPARER(tmp_path):
    """AC 4.2 -- frontiere de vocabulaire sur les textes du module."""
    from outils_frontiere import chaines_de_code

    interdits = ("reparer", "corriger le fichier", "reconstruire")
    textes = chaines_de_code(Path(ecran_projet.__file__))
    textes += chaines_de_code(Path(projets.__file__))
    fautives = [t for t in textes
                if any(mot in t.lower() for mot in interdits)]
    assert fautives == [], fautives


# ---------------------------------------------------------------------------
# AC 5 -- la creation
# ---------------------------------------------------------------------------

def test_l_apercu_annonce_ce_que_le_COEUR_cree(tmp_path, banc):
    """AC 5.2, et c'est l'ecart 1 de la fiche.

    La maquette `E0-4` annonce `frames/` et `outputs/`, que le coeur ne cree
    pas, et omet `logs/`, qu'il cree. L'apercu est derive de `BASE_SUBDIRS`.
    """
    ecran = ecran_projet.EcranCreation(dossier_parent=str(tmp_path),
                                       nom="planche_hiver_2026")

    async def scenario(pilote):
        return _texte(pilote.app.screen)

    rendu = banc(_app(ecran), scenario)
    for nom in ("scans", "planches", "logs", "versions"):
        assert f"{nom}/" in rendu, (nom, rendu)
    for absent in ("frames/", "outputs/"):
        assert absent not in rendu, (absent, rendu)


def test_l_apercu_dit_bien_ce_qui_sera_cree_sur_le_disque(tmp_path, banc):
    """Volet symetrique du precedent, et le SEUL qui prouve que l'apercu ne
    ment pas : on cree pour de vrai, et on compare a ce qui etait annonce."""
    ecran = ecran_projet.EcranCreation(dossier_parent=str(tmp_path), nom="pour_de_vrai")

    async def scenario(pilote):
        rendu = _texte(pilote.app.screen)
        pilote.app.screen.valider()
        return rendu

    rendu = banc(_app(ecran), scenario)
    reels = sorted(p.name for p in (tmp_path / "pour_de_vrai").iterdir()
                   if p.is_dir())
    annonces = sorted(nom for nom in ("scans", "planches", "logs", "versions",
                                      "frames", "outputs", "output-frames")
                      if f"{nom}/" in rendu)
    assert annonces == reels, (annonces, reels)


#: L'exception est NOMMEE, jamais un seuil, et elle est datee.
#:
#: `EPIC11-ARB-225` renomme `patches/` en `planches/`. Le nom neuf entre donc
#: dans `BASE_SUBDIRS`, et cette frontiere -- qui derive sa liste de la
#: constante, donc l'a surveille sans qu'on ait rien a poser -- a
#: immediatement attrape la LEGENDE de l'ecran de projets : `("P", "planches")`
#: est le mot francais du cardinal affiche, pas un segment de chemin.
#:
#: Le precedent d'a cote a choisi l'autre sortie : `("S", "scannés")` dit le
#: participe justement parce que `scans` est un nom de dossier. Elle ne se
#: transpose pas ici -- « planchés » n'existe pas, et le cardinal compte bien
#: des planches. On nomme donc l'exception plutot que de degrader l'ecran.
#:
#: Ce qu'elle ne couvre pas, dit plutot que tu : la frontiere mesure une
#: egalite de chaine nue, et `planches` est un mot ordinaire du domaine. Elle
#: rougira sur tout affichage futur qui l'emploie seul. La mesure fine des
#: compositions de CHEMIN vit dans `test_vocabulaire_de_la_tui.py`, a l'AST.
LEGENDES_QUI_NE_SONT_PAS_DES_CHEMINS = frozenset({
    ("projets.py", "planches"),
})


def test_aucun_nom_de_dossier_n_est_ecrit_en_LITTERAL_dans_la_tui(paquet_tui):
    """AC 5.2 -- frontiere de comptage a zero, avec volet symetrique.

    Deux listes de dossiers divergeraient au premier ajout cote coeur, et c'est
    la TUI qui aurait tort sans que rien ne le dise.
    """
    from outils_frontiere import chaines_de_code
    from mixed_media_utility.io.project_layout import BASE_SUBDIRS

    fautives = []
    for source in sorted(paquet_tui.rglob("*.py")):
        for texte in chaines_de_code(source):
            if (source.name, texte) in LEGENDES_QUI_NE_SONT_PAS_DES_CHEMINS:
                continue
            if any(texte == nom or texte == f"{nom}/" for nom in BASE_SUBDIRS):
                fautives.append((source.name, texte))
    assert fautives == [], fautives


def test_la_LEGENDE_exemptee_existe_VRAIMENT_dans_la_tui(paquet_tui):
    """Volet symetrique de l'exception ci-dessus, sans lequel elle pourrit.

    Une exception nommee qui ne designe plus rien -- module renomme, legende
    reformulee -- reste verte pour toujours et couvre alors ce qu'elle n'a
    jamais eu a couvrir. On mesure donc qu'elle mord encore.
    """
    from outils_frontiere import chaines_de_code

    for nom_de_module, texte in LEGENDES_QUI_NE_SONT_PAS_DES_CHEMINS:
        source = paquet_tui / nom_de_module
        assert source.is_file(), nom_de_module
        assert texte in set(chaines_de_code(source)), (nom_de_module, texte)


def test_la_frontiere_des_noms_de_dossiers_MORD():
    """Volet symetrique : un litteral doit bien sortir de la mesure."""
    from mixed_media_utility.io.project_layout import BASE_SUBDIRS

    faux = ["scans", "planches"]
    assert any(t == nom for t in faux for nom in BASE_SUBDIRS)


def test_creer_pose_l_arborescence_et_le_project_json(tmp_path, banc):
    """AC 5.3 : la creation passe par le coeur, et se relit."""
    crees = []
    ecran = ecran_projet.EcranCreation(dossier_parent=str(tmp_path), nom="mon_projet",
                                       apres_creation=crees.append)

    async def scenario(pilote):
        pilote.app.screen.valider()

    banc(_app(ecran), scenario)
    cible = tmp_path / "mon_projet"
    assert crees == [cible]
    assert (cible / "project.json").is_file()
    manifeste = json.loads((cible / "project.json").read_text(encoding="utf-8"))
    assert manifeste["project_id"] == "mon_projet"


def test_le_dossier_parent_manquant_est_annonce_AVANT_d_ecrire(tmp_path, banc):
    """AC 5.4 (`EPIC11-ARB-40`). Le glyphe est `substitute`, **pas** `absent` :
    ce n'est pas un refus."""
    parent = tmp_path / "pas" / "encore" / "la"
    ecran = ecran_projet.EcranCreation(dossier_parent=str(parent), nom="mon_projet")

    async def scenario(pilote):
        return _texte(pilote.app.screen), pilote.app.screen.etat()

    rendu, etat = banc(_app(ecran), scenario)
    assert jetons.GLYPHES["substitute"] in rendu, rendu
    assert jetons.GLYPHES["absent"] not in rendu, rendu
    assert "sera cree" in rendu
    assert not parent.exists(), "l'apercu ne doit RIEN ecrire"
    assert "n'existe pas encore" in etat


def test_le_parent_manquant_est_cree_sur_PLUSIEURS_niveaux(tmp_path, banc):
    """AC 5.4, second volet : « y compris sur plusieurs niveaux »."""
    parent = tmp_path / "un" / "deux" / "trois"
    ecran = ecran_projet.EcranCreation(dossier_parent=str(parent), nom="mon_projet")

    async def scenario(pilote):
        pilote.app.screen.valider()

    banc(_app(ecran), scenario)
    assert (parent / "mon_projet" / "project.json").is_file()


def test_une_cible_portant_deja_un_projet_echoue_AVANT_TOUT_ECRIT(tmp_path, banc):
    """AC 5.5 -- comptage a zero, avec volet symetrique.

    « Creer ce qui n'existe pas n'est pas ecraser ce qui existe. »
    """
    existant = creer_projet(tmp_path, "deja_la").chemin
    avant = sorted(p.name for p in existant.rglob("*"))
    horodatage = (existant / "project.json").stat().st_mtime

    ecran = ecran_projet.EcranCreation(dossier_parent=str(tmp_path), nom="deja_la")

    async def scenario(pilote):
        pilote.app.screen.valider()
        return pilote.app.screen.etat()

    etat = banc(_app(ecran), scenario)
    assert sorted(p.name for p in existant.rglob("*")) == avant
    assert (existant / "project.json").stat().st_mtime == horodatage
    assert "ouvrir" in etat.lower(), etat


def test_un_nom_qui_est_un_CHEMIN_est_refuse_et_l_apercu_n_est_pas_calcule(
        tmp_path, banc):
    """AC 5.6 : le refus tombe AVANT le premier `mkdir`."""
    ecran = ecran_projet.EcranCreation(dossier_parent=str(tmp_path), nom="a/b")

    async def scenario(pilote):
        rendu = _texte(pilote.app.screen)
        pilote.app.screen.valider()
        return rendu, pilote.app.screen.etat()

    rendu, etat = banc(_app(ecran), scenario)
    assert "Renseignez les deux champs" in rendu, rendu
    assert "chemin" in etat.lower(), etat
    assert not (tmp_path / "a").exists()


def test_le_project_json_de_la_tui_est_IDENTIQUE_a_celui_de_la_gui(tmp_path, banc):
    """AC 5.7 -- contrat d'artefact, `created` mis a part."""
    ecran = ecran_projet.EcranCreation(dossier_parent=str(tmp_path / "par_la_tui"),
                                       nom="jumeau")

    async def scenario(pilote):
        pilote.app.screen.valider()

    banc(_app(ecran), scenario)
    par_la_gui = creer_projet(tmp_path / "par_la_gui", "jumeau").chemin

    def lire(dossier):
        document = json.loads((dossier / "project.json").read_text(encoding="utf-8"))
        document.pop("created")
        return document

    assert lire(tmp_path / "par_la_tui" / "jumeau") == lire(par_la_gui)


# ---------------------------------------------------------------------------
# AC 7 -- la couture des paliers, mesuree sur l'ECRAN
# ---------------------------------------------------------------------------

def test_ouvrir_descend_et_echap_remonte_D_UN_palier(tmp_path, banc):
    """AC 7.1 et 7.2, avec DEUX bandeaux compares -- pas un seul."""
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)
    app = _app(ecran)
    ecran._ouvrir = lambda dossier: (
        setattr(app, "contexte", app.contexte.__class__(projet=dossier.name)),
        app.descendre())[-1]

    async def scenario(pilote):
        avant = pilote.app.screen.bandeau()
        pilote.app.screen.traiter("enter")
        await pilote.pause()
        pendant = pilote.app.screen.bandeau()
        pilote.app.action_remonter()
        await pilote.pause()
        return avant, pendant, pilote.app.screen.bandeau()

    avant, pendant, apres = banc(app, scenario)
    assert "aucun projet" in avant
    assert "projet_demo" in pendant
    assert "Ateliers" in pendant
    assert "projet_demo" in apres and "Ateliers" not in apres


def test_le_palier_zero_survit_a_un_aller_retour(tmp_path, banc):
    """AC 7.4 -- **mesure d'ecran, pas de modele**.

    `app.rang` et `screen.titre` sont justes des deux cotes du defaut de
    palier detruit par `textual` : ils ont rendu trois mesures successives
    aveugles le 2026-08-28. On mesure donc `_running`, `is_attached` et
    l'identite des enfants.
    """
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)
    app = _app(ecran)
    ecran._ouvrir = lambda _: app.descendre()

    async def scenario(pilote):
        avant = (ecran._running, ecran.is_attached,
                 [id(w) for w in ecran.walk_children()])
        pilote.app.screen.traiter("enter")
        await pilote.pause()
        pilote.app.action_remonter()
        await pilote.pause()
        return avant, (ecran._running, ecran.is_attached,
                       [id(w) for w in ecran.walk_children()])

    avant, apres = banc(app, scenario)
    assert avant[0] is True and apres[0] is True
    assert avant[1] is True and apres[1] is True
    assert avant[2] == apres[2], "les enfants ont ete detruits et recomposes"


def test_une_touche_collee_a_echap_n_est_pas_inerte(tmp_path, banc):
    """**Lecon de banc 1** : le nom de touche est injecte tel que le parseur le
    produit. `Echap` puis `Suppr` rend `alt+delete`, et rien ne le
    reconnaitrait sans la normalisation de la coque."""
    chemins, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        from textual import events
        await pilote.app.on_event(events.Key("alt+delete", None))
        await pilote.pause()
        return [e.chemin for e in recents.lire()]

    restants = banc(_app(ecran), scenario)
    assert chemins[2] not in restants, restants


# ---------------------------------------------------------------------------
# AC 8 -- grille, glyphes, replis
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fabrique", ["projet", "creation"])
def test_les_ecrans_tiennent_le_plancher_80x24(tmp_path, banc, fabrique):
    """AC 8.1, au plancher EXACT -- « un ecran qui tient a 100x30 et deborde a
    80x24 est un defaut que seule cette taille demasque »."""
    _, recents = _trois_recents(tmp_path)
    ecran = (ecran_projet.EcranProjet(recents=recents) if fabrique == "projet"
             else ecran_projet.EcranCreation(dossier_parent=str(tmp_path), nom="x"))

    async def scenario(pilote):
        return _texte(pilote.app.screen)

    rendu = banc(_app(ecran), scenario)
    lignes = rendu.splitlines()
    assert len(lignes) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, len(lignes)
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne


@pytest.mark.parametrize("fabrique", ["projet", "creation"])
def test_le_repli_ascii_ne_laisse_aucun_caractere_hors_ascii(tmp_path, banc,
                                                             fabrique):
    """AC 8.3, sur les deux ecrans, **cadre compris** pour ce qui est rendu."""
    chemins, recents = _trois_recents(tmp_path)
    import shutil
    shutil.rmtree(chemins[1])            # un disparu, pour que `✕` soit rendu
    ecran = (ecran_projet.EcranProjet(recents=recents) if fabrique == "projet"
             else ecran_projet.EcranCreation(dossier_parent=str(tmp_path / "absent"),
                                             nom="x"))

    async def scenario(pilote):
        return (_texte(pilote.app.screen), pilote.app.screen.raccourcis,
                pilote.app.screen.etat())

    for morceau in banc(_app(ecran, ascii_seul=True), scenario):
        replie = jetons.replier_ascii(morceau)
        assert replie.isascii(), replie


def test_trois_etats_de_recent_donnent_trois_chaines_SANS_COULEUR(tmp_path, banc):
    """AC 8.2 : « la couleur ne porte jamais seule une information ».

    Present, disparu, et illisible : trois etats, trois chaines distinctes,
    rendues **sans aucune couleur**.
    """
    chemins, recents = _trois_recents(tmp_path)
    import shutil
    shutil.rmtree(chemins[1])
    (chemins[0] / "project.json").write_text("{ casse", encoding="utf-8")
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        largeur = jetons.largeur_utile(pilote.app.size.width)
        return [pilote.app.screen.ligne_de_recent(rang, largeur)
                for rang in range(3)]

    lignes = banc(_app(ecran, sans_couleur=True), scenario)
    droites = [ligne.split(None, 1)[1] if " " in ligne else ligne
               for ligne in lignes]
    assert len(set(droites)) == 3, droites


# ---------------------------------------------------------------------------
# Revue vague 2 bis -- C1, C2, C7, C16
#
# Quatre defauts fonctionnels, mesures **par le chemin de l'operateur** : le
# collage doit arriver dans la barre d'adresse, la lettre de saut ne doit pas
# fermer l'application, la touche des caches doit etre annoncee, et la legende
# des cinq initiales doit etre a l'ecran. Un test qui n'appellerait que la
# fonction fautive laisserait chacun de ces quatre passer.
# ---------------------------------------------------------------------------

def _arborescence(tmp_path, noms, racine="arbo"):
    """Un dossier peuple. **Au moins deux entrees distinguables** (regle des
    fabriques) : une cible toujours placee ailleurs qu'en premiere position est
    la seule facon de demasquer un `find` qui rendrait le premier element."""
    base = tmp_path / racine
    for nom in noms:
        (base / nom).mkdir(parents=True)
    assert len(noms) >= 2, noms
    return base


def _dans_l_explorateur(ecran, dossier, dans_la_saisie=False):
    """Amener l'ecran en `ZONE_CHEMIN` sur `dossier`, liste ou saisie."""
    ecran.traiter("tab")
    exp = ecran.explorateur
    exp.dossier = dossier
    exp.relire()
    if dans_la_saisie:
        ecran.traiter("tab")
        exp.saisie, exp.caret = "", 0
    ecran.rafraichir()
    return exp


# -- C1 : le collage --------------------------------------------------------

def test_le_collage_du_TERMINAL_arrive_dans_la_barre_d_adresse(tmp_path, banc):
    """C1 / AC 5.7 : `Paste` est **le** chemin du collage, et il est branche.

    Le geste de l'operateur differe selon le systeme -- `Ctrl+Maj+V` sous GNOME
    Terminal, `Cmd+V` sous macOS, clic droit sous Windows Terminal -- mais tous
    passent par le *bracketed paste*, que `textual` active au demarrage : le
    terminal livre le texte dans un evenement `Paste`, **sans qu'aucune touche
    n'atteigne l'application**. Le test injecte donc l'evenement par le meme
    point d'entree que le pilote (`App.on_event`), et mesure ce que l'operateur
    voit : le chemin colle dans la barre d'adresse rendue.
    """
    from textual import events

    base = _arborescence(tmp_path, ("brut", "etalonne"),
                         racine="13_plans_de_coupe_colles")
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        exp = _dans_l_explorateur(cible, tmp_path, dans_la_saisie=True)
        await pilote.app.on_event(events.Paste(str(base)))
        await pilote.pause()
        cible.rafraichir()
        return exp.saisie, _texte(cible)

    saisie, rendu = banc(_app(ecran), scenario)
    assert saisie == str(base), "le modele porte le chemin colle"
    assert "13_plans_de_coupe_colles" in rendu, (
        "le collage doit se VOIR dans la barre d'adresse, pas seulement dans "
        f"le modele : {rendu!r}")


def test_un_collage_HORS_de_la_saisie_ne_compose_pas_deux_chemins(tmp_path,
                                                                  banc):
    """Volet symetrique du precedent : le collage ne va que dans la saisie.

    La liste n'a pas de point d'insertion ; y deverser un chemin absolu a la
    suite du dossier courant produirait une adresse faite de deux chemins colles
    -- `/home/x/rushes/home/x/autre`. Le collage y est donc sans effet, et
    aucune ligne de raccourcis ne le promet dans cet etat.
    """
    from textual import events

    base = _arborescence(tmp_path, ("alpha", "zebre"))
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        exp = _dans_l_explorateur(cible, base)          # la LISTE a le focus
        avant = exp.dossier
        await pilote.app.on_event(events.Paste(str(tmp_path)))
        await pilote.pause()
        return avant, exp.dossier, exp.saisie, cible.raccourcis

    avant, apres, saisie, raccourcis = banc(_app(ecran), scenario)
    assert apres == avant, "un collage dans la liste ne deplace rien"
    assert saisie is None, "il n'ouvre pas non plus la saisie a l'aveugle"
    assert "oller" not in raccourcis, raccourcis


def test_ctrl_v_ne_colle_pas_en_silence__il_DIT_quoi_presser(tmp_path, banc):
    """C1, second volet : la touche que le terminal n'a pas prise.

    Si `ctrl+v` parvient jusqu'a l'application, c'est precisement que le
    terminal ne l'a pas interpretee comme un collage -- il n'y a donc aucun
    texte a coller avec elle, et l'application n'a aucun acces au presse-papier
    du systeme. Elle repond en nommant le geste reel plutot qu'en ne faisant
    rien : « une touche annoncee qui n'agit pas » est le mode de panne que la
    coque nomme elle-meme.
    """
    base = _arborescence(tmp_path, ("alpha", "zebre"))
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        exp = _dans_l_explorateur(cible, base, dans_la_saisie=True)
        consommee = cible.traiter("ctrl+v")
        cible.rafraichir()
        return (consommee, cible.etat(), exp.saisie,
                str(cible.query_one("#etat").content))

    consommee, etat, saisie, peinte = banc(_app(ecran), scenario)
    assert consommee is True, "la touche est consommee, pas laissee filer"
    assert etat == ecran_projet.PHRASE_COLLAGE, etat
    assert "Ctrl+Maj+V" in peinte and "Cmd+V" in peinte, (
        f"le motif doit etre PEINT en ligne d'etat, pas seulement calcule : "
        f"{peinte!r}")
    assert saisie == "", "et elle n'ecrit rien dans la saisie"


def test_aucune_ligne_de_raccourcis_ne_promet_plus_Ctrl_V_coller():
    """C1, frontiere negative : le libelle faux a disparu, l'annonce reste.

    `Ctrl+V coller` etait une promesse qu'aucun terminal ne tient. Le volet
    symetrique est indispensable : une ligne qui aurait simplement perdu toute
    mention du collage passerait la premiere assertion sans rien annoncer.
    """
    lignes = {nom: valeur for nom, valeur in vars(ecran_projet).items()
              if nom.startswith("RACCOURCIS_") and isinstance(valeur, str)}
    assert len(lignes) >= 4, sorted(lignes)
    for nom, ligne in lignes.items():
        assert "Ctrl+V" not in ligne, (nom, ligne)
    assert "Coller" in ecran_projet.RACCOURCIS_SAISIE, (
        ecran_projet.RACCOURCIS_SAISIE)
    replie = jetons.replier_ascii(ecran_projet.RACCOURCIS_SAISIE)
    assert jetons.colonnes(replie) <= jetons.largeur_utile(80), replie


# -- C2 : la lettre de saut ne quitte pas -----------------------------------

def test_une_lettre_SANS_correspondance_ne_ferme_PAS_l_application(tmp_path,
                                                                   banc):
    """C2 : `q` quittait l'application ou sautait, selon le dossier.

    `sauter` rend faux quand aucune entree ne commence par la lettre ; l'ecran
    laissait alors filer l'evenement, qui remontait jusqu'au binding applicatif
    `q` et **fermait la TUI** -- une perte de travail silencieuse, et non
    annoncee : `RACCOURCIS_CHEMIN` ne porte aucune sortie. Le test passe par
    `pilote.press`, seul chemin qui traverse la couche des bindings.

    La fabrique porte trois dossiers distinguables, **aucun** en `q`, et la
    cible du volet symetrique est en TROISIEME position.
    """
    base = _arborescence(tmp_path, ("alpha", "rushes", "zebre"))
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        exp = _dans_l_explorateur(cible, base)
        await pilote.press("q")
        await pilote.pause()
        # `_exit` est l'effet exact du binding `q` (`App.exit` le pose avant
        # meme de poster son message) : c'est la mesure de « l'application
        # s'est fermee », et non un proxy.
        return pilote.app._exit, cible.zone, exp.entree_courante.chemin.name

    ferme, zone, sous_le_curseur = banc(_app(ecran), scenario)
    assert ferme is False, "une lettre de saut ne ferme JAMAIS l'application"
    assert zone == ecran_projet.ZONE_CHEMIN
    assert sous_le_curseur == "alpha", "et le curseur n'a pas bouge"


def test_la_meme_lettre_saute_bien_quand_une_entree_commence_par_elle(tmp_path,
                                                                      banc):
    """Volet symetrique : la touche consommee reste une touche qui AGIT.

    La cible `quinconce/` est en troisieme position sur trois : un saut fautif
    qui rendrait toujours la premiere entree resterait vert autrement.
    """
    base = _arborescence(tmp_path, ("alpha", "rushes", "quinconce"))
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        exp = _dans_l_explorateur(cible, base)
        depart = exp.entree_courante.chemin.name
        await pilote.press("q")
        await pilote.pause()
        return pilote.app._exit, depart, exp.entree_courante.chemin.name

    ferme, depart, arrivee = banc(_app(ecran), scenario)
    assert ferme is False
    assert depart == "alpha"
    assert arrivee == "quinconce", "la lettre saute a la TROISIEME entree"


def test_dans_les_recents_la_touche_q_quitte_TOUJOURS(tmp_path, banc):
    """Second volet symetrique, et le plus important : la correction de C2 ne
    debranche pas la sortie **la ou elle est annoncee**. `RACCOURCIS_RECENTS`
    porte `Q quitter` ; consommer la lettre partout aurait rendu la ligne
    menteuse dans l'autre sens.

    **Et c'est ici que les deux moities de la regle des majuscules se mesurent
    ensemble** (lot `O`, 2026-08-30) : la ligne annonce `Q`, la touche pressee
    est `q`, et l'application se ferme. Une ligne mise en majuscule dont on
    aurait « corrige » le binding au passage rendrait ce test rouge -- c'est
    exactement le piege que la regle documente dans `coque.py`.
    """
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        assert cible.zone == ecran_projet.ZONE_RECENTS
        consommee = cible.traiter("q", "q")
        await pilote.press("q")
        await pilote.pause()
        return consommee, pilote.app._exit

    consommee, ferme = banc(_app(ecran), scenario)
    assert consommee is False, "l'ecran laisse passer `q` vers le binding"
    assert ferme is True, "et l'application se ferme, comme la ligne le promet"
    assert "Q quitter" in ecran_projet.RACCOURCIS_RECENTS
    assert "q quitter" not in ecran_projet.RACCOURCIS_RECENTS, (
        "la LETTRE annoncee est en majuscule -- regle des majuscules de "
        "raccourci, ecrite dans `coque.py`")


# -- C7 : Ctrl+H annonce ----------------------------------------------------

def test_Ctrl_H_est_ANNONCE_dans_un_dossier_qui_porte_des_caches(tmp_path,
                                                                 banc):
    """C7 / `EPIC11-ARB-56` : la touche « quitte la ligne d'etat pour celle des
    raccourcis, ou est sa place ». La sortie avait ete faite, l'entree non.

    La mesure porte sur la ligne **peinte**, et sur les deux etats de la
    bascule : une ligne qui perdrait `Ctrl+H` des la premiere pression
    laisserait l'operateur sans moyen annonce de remasquer les caches.
    """
    base = _arborescence(tmp_path, ("alpha", "zebre"))
    (base / ".cache_interne").mkdir()
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        exp = _dans_l_explorateur(cible, base)
        cible._appliquer_la_zone()
        cible.rafraichir()
        masques = str(cible.query_one("#raccourcis").content)
        cible.traiter("ctrl+h")
        cible.rafraichir()
        return masques, str(cible.query_one("#raccourcis").content), \
            exp.montrer_caches

    masques, montres, bascule = banc(_app(ecran), scenario)
    assert "Ctrl+H" in masques, masques
    assert bascule is True, "la bascule a bien agi"
    assert "Ctrl+H" in montres, (
        "la touche reste annoncee une fois les caches montres : sinon on ne "
        f"peut plus les remasquer -- {montres!r}")


def test_sans_aucun_cache_la_ligne_garde_ses_jetons_de_navigation(tmp_path,
                                                                  banc):
    """Volet symetrique de C7 : la ligne est CONTEXTUELLE, pas amputee partout.

    « Elle ne montre que ce qui marche sur l'ecran courant » (`DESIGN.md` 4) :
    dans un dossier sans element cache, `Ctrl+H` ne change rien a l'ecran, et
    la ligne garde a la place `Tab chemin` et `↑↓ liste` -- que les sept jetons
    ne permettent pas de tenir ensemble dans les 76 colonnes.
    """
    base = _arborescence(tmp_path, ("alpha", "zebre"))
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        _dans_l_explorateur(cible, base)
        cible._appliquer_la_zone()
        cible.rafraichir()
        return cible.raccourcis

    ligne = banc(_app(ecran), scenario)
    assert ligne == ecran_projet.RACCOURCIS_CHEMIN, ligne
    assert "Ctrl+H" not in ligne, ligne
    assert "Tab chemin" in ligne, ligne


def test_les_deux_lignes_de_la_liste_tiennent_la_grille_dans_LES_DEUX_modes():
    """La ligne « caches » est neuve : sa largeur est mesuree **apres repli**.

    `…` vaut une colonne et `...` en vaut trois ; mesurer avant de replier
    mesurerait l'autre mode. Les deux variantes sont verifiees ensemble parce
    que c'est leur echange qui est le risque : une variante qui tiendrait et
    l'autre non ferait deborder l'ecran selon le dossier ouvert.
    """
    for nom in ("RACCOURCIS_CHEMIN", "RACCOURCIS_CHEMIN_CACHES",
                "RACCOURCIS_SAISIE"):
        ligne = getattr(ecran_projet, nom)
        replie = jetons.replier_ascii(ligne)
        assert replie.isascii(), (nom, replie)
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), (
            nom, jetons.colonnes(ligne))
        assert jetons.colonnes(replie) <= jetons.largeur_utile(80), (
            nom, jetons.colonnes(replie))


# -- C16 : la legende des cinq cardinaux ------------------------------------

def test_la_legende_des_cinq_cardinaux_est_A_L_ECRAN(tmp_path, banc):
    """C16 / AC 7.5, maquette `X9` : l'operateur lit `7R · 4L · 3P · 2S · 1M`.

    Sans legende, rien ne dit ce que `P` et `M` comptent -- et c'est le point
    precis ou l'ecart assume d'`EPIC11-ARB-55` doit etre visible : ces cardinaux
    comptent des **lots ayant atteint un etat**, pas des objets sur le disque.
    La mesure porte sur la ligne d'etat PEINTE, et confronte chaque couple a
    `projets.LEGENDE_DES_CARDINAUX` : une legende recopiee dans l'ecran
    divergerait au premier ajustement du modele.
    """
    chemins, recents = _trois_recents(tmp_path)
    _manifeste_de(chemins[1], 7, ("extraction", "pdf", "encode", "scan"))
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        return str(cible.query_one("#etat").content), cible.etat()

    peinte, etat = banc(_app(ecran), scenario)
    for lettre, mot in projets.LEGENDE_DES_CARDINAUX:
        assert f"{lettre} {mot}" in peinte, (lettre, mot, peinte)
    assert etat == ecran_projet.legende_des_cardinaux()
    # Les cinq lettres de la legende sont exactement celles de la ligne rendue.
    largeur = jetons.largeur_utile(80)

    async def scenario_ligne(pilote):
        return pilote.app.screen.ligne_de_recent(1, largeur)

    ligne = banc(_app(ecran_projet.EcranProjet(recents=recents)),
                 scenario_ligne)
    assert [lettre for lettre, _ in _cardinaux_rendus(ligne)] == [
        lettre for lettre, _ in projets.LEGENDE_DES_CARDINAUX], ligne
    assert jetons.colonnes(peinte) <= largeur, peinte


def test_la_legende_se_replie_en_ASCII_avant_toute_mesure(tmp_path, banc):
    """Volet ASCII de C16 : le repli precede la mesure, et rien ne se perd."""
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        return str(cible.query_one("#etat").content), cible.etat()

    peinte, rendue = banc(_app(ecran, ascii_seul=True), scenario)
    # **Les deux, et pas seulement la peinte** : `poser_etat` replie une
    # derniere fois avant d'ecrire, si bien qu'un `etat()` reste en UTF-8
    # arriverait quand meme ASCII a l'ecran -- et le repli manquant ne se
    # verrait qu'au premier appelant qui MESURE `etat()` avant de le peindre,
    # ou `…` vaut une colonne et `...` en vaut trois. Mesure trouvee par
    # reinjection : sans cette ligne, retirer le repli de
    # `legende_des_cardinaux` laissait le test vert.
    assert rendue.isascii(), rendue
    assert peinte.isascii(), peinte
    assert jetons.colonnes(peinte) <= jetons.largeur_utile(80), peinte
    for lettre, _mot in projets.LEGENDE_DES_CARDINAUX:
        assert f"{lettre} " in peinte, (lettre, peinte)
    assert "..." not in peinte, ("la legende ne doit pas etre abregee : elle "
                                 f"tient -- {peinte!r}")


def test_sans_aucun_recent_la_legende_ne_dit_rien(tmp_path, banc):
    """Volet symetrique : expliquer des initiales que personne ne voit serait
    le bavardage qu'`EPIC11-ARB-56` interdit a cette ligne. Sans liste, pas de
    cardinaux -- donc pas de legende."""
    recents = projets.Recents(tmp_path / "reglages" / "recents-v1.json")
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        cible = pilote.app.screen
        return cible.zone, cible.etat()

    zone, etat = banc(_app(ecran), scenario)
    assert zone == ecran_projet.ZONE_CHEMIN, "pas de liste : le champ a le focus"
    assert "rushes" not in etat, etat


# ---------------------------------------------------------------------------
# Revue vague 2 bis -- C18, B5, F-17
#
# Trois findings de la couche 3, et un fil commun : **l'explorateur est un seul
# composant, a cinq sites**. `C18` mesure qu'`E0-4` le monte vraiment (la story
# devait cabler deux sites, elle en avait cable un) ; `B5` mesure l'interdit
# d'`EPIC11-ARB-2` -- « `Echap` ne remonte JAMAIS d'un dossier » -- sur les
# trois etats ou la touche existe ; `F-17` mesure que la meme touche n'y porte
# plus quatre libelles.
# ---------------------------------------------------------------------------

_MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
              / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
              / "maquettes")


def _raccourcis_de_la_maquette(prefixe: str) -> str:
    """La ligne de raccourcis d'une maquette validee, hors de son cadre.

    On lit **la maquette**, pas une transcription : c'est la seule facon que la
    mesure survive a un ajustement de la maquette, et le finding `F-17` est
    precisement un ecart entre les deux qu'aucun test ne voyait.
    """
    fichier = next(_MAQUETTES.glob(f"{prefixe}-*.txt"))
    lignes = [ligne for ligne in fichier.read_text(encoding="utf-8").splitlines()
              if ligne.startswith("│") and "⏎" in ligne]
    assert lignes, f"aucune ligne de raccourcis dans {fichier.name}"
    return lignes[-1].strip("│").strip()


def _libelles_de_ligne(ligne: str) -> dict[str, str]:
    """Les couples (touche, libelle) d'une ligne de raccourcis.

    Les jetons sont separes par au moins **deux** espaces depuis
    `EPIC11-ARB-122` (2026-08-31) -- c'etait trois auparavant, et ce lecteur
    portait donc le separateur en dur, la ou une frontiere le mesure desormais
    (`test_AUCUNE_ligne_de_raccourcis_ne_porte_TROIS_blancs`). Chaque jeton est
    une touche suivie de son libelle.

    **Un libelle ne peut donc plus contenir deux espaces consecutifs**, ce qui
    est vrai de toutes les lignes du depot -- verifie -- et ce que la frontiere
    ci-dessus garantit pour les suivantes.
    """
    return {jeton.split(" ", 1)[0]: jeton.split(" ", 1)[1]
            for jeton in re.split(r"\s{2,}", ligne.strip()) if " " in jeton}


def _arborescence_imbriquee(tmp_path):
    """Trois dossiers distinguables, dont le DEUXIEME porte deux enfants.

    Regle des fabriques : jamais un remplissage uniforme, et la cible n'est pas
    en premiere position -- un `find` fautif qui rendrait toujours le premier
    element ne se demasque pas autrement. L'imbrication est ce qui rend
    `remonter()` visible : sans elle, `Echap` route vers `remonter()` ne
    changerait rien et le mutant `M5` survivrait a un test pourtant ecrit.
    """
    base = tmp_path / "rushes_2026"
    for nom in ("01_alpha", "02_cible", "03_zebre"):
        (base / nom).mkdir(parents=True)
    for nom in ("brut", "etalonne"):
        (base / "02_cible" / nom).mkdir()
    return base, base / "02_cible"


def _lignes_accentuees(contenu) -> list[str]:
    """Les lignes rendues en GRAS + couleur d'accentuation, dans l'ordre.

    `rich` pose les styles en intervalles d'offsets sur tout le bloc : sans le
    decoupage ligne a ligne, un test ne peut dire que « un style est pose
    quelque part », ce qui ne distingue pas la bonne ligne d'une autre.
    """
    accent = jetons.couleur("accent")
    return [ligne.plain for ligne in contenu.split(chr(10))
            if any(accent in str(s.style) and "bold" in str(s.style)
                   for s in ligne.spans)]


def _creation_sur(base, nom="planche_hiver_2026"):
    return ecran_projet.EcranCreation(dossier_parent=str(base), nom=nom)


# -- C18 : `E0-4` monte le MEME explorateur ---------------------------------

def test_E0_4_choisit_son_dossier_parent_DANS_l_explorateur(tmp_path, banc):
    """C18 / AC 1.3 : le champ « dossier parent » passe par l'explorateur.

    Le parcours complet de l'operateur, au clavier : `Tab` ouvre l'explorateur,
    `↓` puis `→` descendent dans un dossier qui n'est **pas** le premier, `⏎`
    retient ce dossier comme parent. La mesure porte sur les deux bouts -- ce
    que l'ecran RESSEMBLE (les lignes de l'explorateur, pas deux champs texte)
    et ce que le modele retient -- parce que le defaut sanctionne etait
    exactement de declarer l'un en ayant livre l'autre.
    """
    base, cible = _arborescence_imbriquee(tmp_path)
    ecran = _creation_sur(base)

    async def scenario(pilote):
        e = pilote.app.screen
        avant = _texte(e)
        e.traiter("tab")
        e.rafraichir()
        dans_l_explorateur = _texte(e)
        e.traiter("down")            # la cible est au DEUXIEME rang
        e.traiter("enter")
        e.rafraichir()
        return (avant, dans_l_explorateur, e.dossier_parent, e.zone, e.cible,
                _texte(e))

    avant, pendant, parent, zone, apercu, apres = banc(_app(ecran), scenario)
    assert ecran_projet.LIBELLE_NOM in avant, avant
    # Ce que seul l'explorateur produit : l'etiquette du parent et celle du bas.
    assert "Valider" in pendant, pendant
    assert "02_cible" in pendant and "03_zebre" in pendant, pendant
    assert parent == str(cible), (parent, str(cible))
    assert zone == ecran_projet.ZONE_FORMULAIRE, zone
    # **L'apercu se mesure sur le modele et non sur la ligne peinte** : celle-ci
    # abrege un chemin de banc plus long que la grille, et l'assertion mesurerait
    # alors l'abregement plutot que le dossier retenu.
    assert apercu == cible / "planche_hiver_2026", (apercu, cible)
    assert ecran_projet.LIBELLE_NOM in apres, "on est revenu au formulaire"


def test_l_explorateur_de_E0_4_est_le_MEME_composant__pas_une_copie(tmp_path,
                                                                    banc):
    """C18 / `EPIC11-ARB-48` : « un composant unique [...] cinq sites ».

    Trois mesures, parce que trois choses pouvaient etre recopiees plutot que
    partagees : la classe, le RENDU, et la ligne de raccourcis. La derniere est
    celle qui a manque a la vague precedente -- un site peut monter le bon
    modele et annoncer les mauvaises touches, et c'est le finding `F-17`.
    """
    base, _ = _arborescence_imbriquee(tmp_path)
    ecran = _creation_sur(base)

    async def scenario(pilote):
        e = pilote.app.screen
        e.traiter("tab")
        e.rafraichir()
        attendues = e.explorateur.lignes(
            pilote.app.size.width, titre=ecran_projet.TITRE_CREER,
            libelle=ecran_projet.LIBELLE_PARENT, ascii_seul=False)
        return (type(e.explorateur), e.explorateur.montrer_fichiers,
                e.lignes(), attendues, e.raccourcis)

    classe, fichiers, rendues, attendues, raccourcis = banc(_app(ecran),
                                                            scenario)
    assert classe is explorateur.Explorateur, classe
    assert fichiers is False, "on choisit un DOSSIER, pas un fichier"
    assert rendues == attendues, (
        "`E0-4` doit rendre la zone centrale de l'explorateur telle quelle -- "
        "la recomposer serait le cinquieme rendu que l'arbitrage interdit")
    assert raccourcis == ecran_projet.RACCOURCIS_CHEMIN, raccourcis


def test_les_deux_sites_montrent_la_MEME_chose_sur_le_MEME_dossier(tmp_path,
                                                                   banc):
    """C18, volet le plus fort : `E0-2` et `E0-4` sur le meme dossier rendent
    les memes lignes, au titre et au libelle du champ pres.

    Un site qui aurait sa propre copie du rendu passerait les mesures
    precedentes des lors qu'elle serait fidele au depart ; elle divergerait au
    premier ajustement. Comparer les deux sites entre eux est la seule mesure
    qui ne se laisse pas satisfaire par une copie conforme.
    """
    base, _ = _arborescence_imbriquee(tmp_path)
    _, recents = _trois_recents(tmp_path)

    async def scenario_ouvrir(pilote):
        e = pilote.app.screen
        _dans_l_explorateur(e, base)
        return e.lignes()

    async def scenario_creer(pilote):
        e = pilote.app.screen
        e.traiter("tab")
        e.explorateur.dossier = base
        e.explorateur.relire()
        e.rafraichir()
        return e.lignes()

    ouvrir = banc(_app(ecran_projet.EcranProjet(recents=recents)),
                  scenario_ouvrir)
    creer = banc(_app(_creation_sur(base)), scenario_creer)
    assert len(ouvrir) == len(creer), (len(ouvrir), len(creer))
    differentes = [(a, b) for a, b in zip(ouvrir, creer) if a != b]
    # Seules deux lignes different : le titre de l'ecran et le libelle du champ.
    assert len(differentes) == 2, differentes
    assert ecran_projet.TITRE_OUVRIR in differentes[0][0]
    assert ecran_projet.TITRE_CREER in differentes[0][1]
    assert ecran_projet.LIBELLE_CHEMIN in differentes[1][0]
    assert ecran_projet.LIBELLE_PARENT in differentes[1][1]


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_rang_du_curseur_de_E0_4_est_PASSE_a_la_peinture(tmp_path, banc,
                                                            ascii_seul):
    """C18, et le troisieme defaut du developpement, a ne pas reintroduire.

    L'auto-detection de `jetons.peindre` cherche le glyphe de curseur en TETE
    de ligne ; les lignes de l'explorateur sont indentees, donc elle ne trouve
    rien -- et ne colore rien, **en silence**. Le rang doit etre passe
    explicitement, comme sur `E0-2`.

    Le curseur est place au DEUXIEME rang : un rang constant qui vaudrait zero
    peindrait la bonne ligne sur une liste ou la cible est en tete. Le repli
    ASCII est dans la mesure parce qu'il y confond le glyphe d'invite et celui
    du curseur, et qu'une ligne peinte en trop s'y lit differemment.
    """
    base, _ = _arborescence_imbriquee(tmp_path)
    ecran = _creation_sur(base)

    async def scenario(pilote):
        e = pilote.app.screen
        e.traiter("tab")
        e.traiter("down")
        e.rafraichir()
        return e._corps.content, e.explorateur.entree_courante.nom

    contenu, nom = banc(_app(ecran, ascii_seul=ascii_seul), scenario)
    accentuees = _lignes_accentuees(contenu)
    assert len(accentuees) == 1, (accentuees, jetons.texte_affiche(contenu))
    assert nom in accentuees[0], (nom, accentuees)
    assert jetons.glyphes(ascii_seul)["curseur"] in accentuees[0], accentuees


def test_Tab_sur_E0_4_mene_a_l_explorateur_puis_DANS_la_saisie(tmp_path, banc):
    """C18 + `EPIC11-ARB-51` : `Tab` garde son geste, sur les trois etats.

    Trois pressions successives, les trois etats releves : le formulaire, la
    liste de l'explorateur, la barre d'adresse. La ligne de raccourcis est
    relevee a chaque fois -- une bascule qui agirait sans que la ligne suive
    laisserait l'operateur devant des touches fausses.
    """
    base, _ = _arborescence_imbriquee(tmp_path)
    ecran = _creation_sur(base)

    async def scenario(pilote):
        e = pilote.app.screen
        etapes = [(e.zone, e.explorateur.dans_la_saisie, e.raccourcis)]
        for _ in range(2):
            e.traiter("tab")
            etapes.append((e.zone, e.explorateur.dans_la_saisie, e.raccourcis))
        return etapes

    etapes = banc(_app(ecran), scenario)
    assert etapes == [
        (ecran_projet.ZONE_FORMULAIRE, False, ecran_projet.RACCOURCIS_CREATION),
        (ecran_projet.ZONE_CHEMIN, False, ecran_projet.RACCOURCIS_CHEMIN),
        (ecran_projet.ZONE_CHEMIN, True, ecran_projet.RACCOURCIS_SAISIE),
    ], etapes


def test_le_NOM_du_projet_reste_une_SAISIE_de_texte(tmp_path, banc):
    """Volet symetrique de C18 : le second champ n'est pas un chemin.

    « Le nom du projet reste une saisie de texte : ce n'est pas un chemin a
    parcourir. » Une frappe dans le formulaire va donc au nom, et **jamais** au
    dossier parent -- que seule la validation de l'explorateur ecrit. Sans ce
    volet, un ecran qui n'ecrirait plus rien du tout passerait le test
    precedent.
    """
    base, _ = _arborescence_imbriquee(tmp_path)
    ecran = ecran_projet.EcranCreation(dossier_parent=str(base), nom="")

    async def scenario(pilote):
        e = pilote.app.screen
        for lettre in "hiver":
            e.traiter(lettre, lettre)
        e.traiter("backspace")
        e.rafraichir()
        return e.nom, e.dossier_parent, _texte(e)

    nom, parent, rendu = banc(_app(ecran), scenario)
    assert nom == "hive", nom
    assert parent == str(base), "la frappe n'a pas touche au dossier parent"
    assert "hive" in rendu, rendu


def test_l_explorateur_de_E0_4_s_ouvre_LA_OU_le_champ_pointe(tmp_path, banc):
    """C18, cas nominal de correction d'une valeur deja saisie.

    Le champ porte deja un dossier ; `Tab` doit ouvrir l'explorateur **la**, et
    non sur le dossier de lancement -- sans quoi corriger une valeur presque
    bonne coute de retraverser toute l'arborescence. La cible n'est pas en
    premiere position parmi ses freres.
    """
    base, cible = _arborescence_imbriquee(tmp_path)
    ecran = _creation_sur(cible)

    async def scenario(pilote):
        e = pilote.app.screen
        e.traiter("tab")
        e.rafraichir()
        return e.explorateur.dossier, sorted(
            entree.nom for entree in e.explorateur.entrees)

    dossier, noms = banc(_app(ecran), scenario)
    assert dossier == cible, (dossier, cible)
    assert noms == ["brut/", "etalonne/"], noms


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_l_explorateur_de_E0_4_tient_la_grille_80x24(tmp_path, banc,
                                                     ascii_seul):
    """C18 / AC 8.1 et 8.3 : la zone centrale d'`E0-4` est neuve, donc mesuree.

    **Le repli ASCII se fait avant la mesure de largeur** : `…` vaut une
    colonne et `...` en vaut trois, donc mesurer avant de replier mesurerait
    l'autre mode. La ligne d'etat et la ligne de raccourcis entrent dans la
    mesure : elles changent avec l'etat, et c'est l'etat neuf qu'on mesure.
    """
    base, _ = _arborescence_imbriquee(tmp_path)
    ecran = _creation_sur(base)

    async def scenario(pilote):
        e = pilote.app.screen
        e.traiter("tab")
        e.rafraichir()
        return _texte(e), e.etat(), e.raccourcis

    rendu, etat, raccourcis = banc(_app(ecran, ascii_seul=ascii_seul), scenario)
    lignes = rendu.splitlines()
    assert len(lignes) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, len(lignes)
    for morceau in lignes + [etat]:
        # Ces deux-la sont rendus DANS le mode : le repli, quand il a lieu, a
        # deja eu lieu avant la mesure de largeur. Les replier ici une seconde
        # fois mesurerait l'autre mode -- `…` vaut une colonne, `...` en vaut
        # trois --, et ferait echouer le mode UTF-8 sur une faute imaginaire.
        assert jetons.colonnes(morceau) <= jetons.largeur_utile(80), morceau
        if ascii_seul:
            assert morceau.isascii(), morceau
    # La ligne de raccourcis, elle, est une constante repliee par la coque au
    # moment de peindre : elle se mesure donc dans les DEUX modes.
    replie = jetons.replier_ascii(raccourcis)
    assert replie.isascii(), replie
    assert jetons.colonnes(raccourcis) <= jetons.largeur_utile(80), raccourcis
    assert jetons.colonnes(replie) <= jetons.largeur_utile(80), replie


# -- B5 : `Echap` ne remonte JAMAIS d'un dossier (`EPIC11-ARB-2`) -----------

def test_Echap_dans_la_LISTE_ne_remonte_JAMAIS_d_un_dossier(tmp_path, banc):
    """B5 / AC 2.8, mutant `M5`. `Echap` sort de l'explorateur, `←` remonte.

    L'interdit est verbatim d'`EPIC11-ARB-2` et le tableau des arbitrages de la
    fiche l'attribuait a cette AC, sans qu'aucun test ne porte le mot `escape`.
    L'explorateur est **dans un sous-dossier** : sans imbrication, router
    `Echap` vers `remonter()` ne changerait rien de visible et le mutant
    survivrait a un test pourtant ecrit.
    """
    base, cible = _arborescence_imbriquee(tmp_path)
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        e = pilote.app.screen
        exp = _dans_l_explorateur(e, cible)
        avant = exp.dossier
        consommee = e.traiter("escape")
        return avant, exp.dossier, exp.dans_la_saisie, e.zone, consommee

    avant, apres, saisie, zone, consommee = banc(_app(ecran), scenario)
    assert apres == avant == cible, (avant, apres)
    assert apres.parent != apres, "le dossier a bien un parent ou remonter"
    assert consommee is True and zone == ecran_projet.ZONE_RECENTS, (
        consommee, zone)
    assert saisie is False


def test_Echap_dans_la_SAISIE_ne_remonte_JAMAIS_d_un_dossier(tmp_path, banc):
    """B5, second etat de l'explorateur : la barre d'adresse a le focus.

    L'etat compte : `Echap` y est route avant tout test sur `dans_la_saisie`,
    donc une mesure faite sur la seule liste laisserait la moitie du mutant en
    vie.
    """
    base, cible = _arborescence_imbriquee(tmp_path)
    _, recents = _trois_recents(tmp_path)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        e = pilote.app.screen
        exp = _dans_l_explorateur(e, cible, dans_la_saisie=True)
        avant = exp.dossier
        consommee = e.traiter("escape")
        return avant, exp.dossier, e.zone, consommee

    avant, apres, zone, consommee = banc(_app(ecran), scenario)
    assert apres == avant == cible, (avant, apres)
    assert consommee is True and zone == ecran_projet.ZONE_RECENTS, (
        consommee, zone)


def test_Echap_sur_E0_4_ne_remonte_JAMAIS_d_un_dossier(tmp_path, banc):
    """B5, troisieme site : le meme interdit sur le meme composant.

    C'est ce que « un composant, cinq sites » veut dire pour une frontiere :
    l'interdit vaut la ou le composant est monte, pas seulement la ou il a ete
    mesure la premiere fois. Ici `Echap` revient au formulaire -- et le dossier
    courant ne bouge pas d'un cran.
    """
    base, cible = _arborescence_imbriquee(tmp_path)
    ecran = _creation_sur(cible)

    async def scenario(pilote):
        e = pilote.app.screen
        e.traiter("tab")
        avant = e.explorateur.dossier
        consommee = e.traiter("escape")
        return avant, e.explorateur.dossier, e.zone, consommee, e.raccourcis

    avant, apres, zone, consommee, raccourcis = banc(_app(ecran), scenario)
    assert apres == avant == cible, (avant, apres)
    assert consommee is True and zone == ecran_projet.ZONE_FORMULAIRE, (
        consommee, zone)
    assert raccourcis == ecran_projet.RACCOURCIS_CREATION, raccourcis


@pytest.mark.parametrize("site", ["ouvrir", "creer"])
def test_la_fleche_GAUCHE_remonte_bien__elle(tmp_path, banc, site):
    """Volet symetrique de B5, sur les deux sites : la mesure MORD.

    Sans lui, un explorateur ou plus rien ne remonterait passerait les trois
    tests precedents -- ils n'affirment qu'une absence de mouvement. `←` est la
    touche qu'`EPIC11-ARB-2` designe pour remonter, et c'est elle qui doit
    bouger.
    """
    base, cible = _arborescence_imbriquee(tmp_path)
    if site == "ouvrir":
        _, recents = _trois_recents(tmp_path)
        ecran = ecran_projet.EcranProjet(recents=recents)
    else:
        ecran = _creation_sur(cible)

    async def scenario(pilote):
        e = pilote.app.screen
        if site == "ouvrir":
            exp = _dans_l_explorateur(e, cible)
        else:
            e.traiter("tab")
            exp = e.explorateur
        avant = exp.dossier
        e.traiter("left")
        return avant, exp.dossier, e.zone

    avant, apres, zone = banc(_app(ecran), scenario)
    assert avant == cible and apres == base, (avant, apres, base)
    assert zone == ecran_projet.ZONE_CHEMIN, "et l'on reste dans l'explorateur"


# -- F-17 : une touche, un libelle ------------------------------------------

def test_les_lignes_de_l_explorateur_sont_CELLES_des_maquettes_validees(
        tmp_path):
    """F-17 : le code ne diverge plus des neuf maquettes validees.

    La mesure LIT les maquettes plutot que d'en recopier le texte : un ecart
    entre les deux est precisement ce qu'aucun test ne voyait. `X1` porte la
    ligne de la liste, `X5` celle de la saisie, `X7` celle des caches.

    **Il n'y a plus aucun ecart assume, et c'est la revue du 2026-08-31 qui
    l'a obtenu.** L'ancienne redaction en revendiquait un : `Ctrl+V coller`
    avait quitte la ligne de saisie au finding `C1` -- une promesse qu'aucun
    terminal ne tient, le collage passant par l'evenement `Paste` -- et la
    maquette gardait l'ancien libelle. Ce n'etait pas un ecart assume, c'etait
    une maquette perimee : elle porte desormais `Coller : terminal`, comme le
    produit. `ECARTS_ASSUMES` reste, VIDE, parce qu'une table vide dit « on a
    regarde » la ou son absence ne dirait rien.

    **La mesure porte sur l'ensemble EXACT des touches, plus sur leur
    intersection** (finding `R12` de la revue du 2026-08-31). L'ancienne version
    ne comparait que les touches COMMUNES aux deux : une assertion positive, qui
    laisse passer toute divergence supplementaire. Elle est restee verte pendant
    que `X7` perdait `↑↓ liste` que le produit venait de reprendre -- la maquette
    montrait donc une ligne plus pauvre que l'ecran livre, et rien ne le disait.
    C'est le piege que `CLAUDE.md` nomme : « l'ensemble des chemins qui divergent
    est **exactement** {X} » mesure l'exception ET son unicite.
    """
    assert ecran_projet.RACCOURCIS_CHEMIN == _raccourcis_de_la_maquette("X1"), (
        ecran_projet.RACCOURCIS_CHEMIN, _raccourcis_de_la_maquette("X1"))
    #: Les ecarts assumes, nommes touche par touche. Vide aujourd'hui : chaque
    #: fois qu'une case s'y ajouterait, c'est une maquette validee qui cesse de
    #: decrire l'ecran livre, et ca se decide plutot que ca ne se subit.
    ECARTS_ASSUMES: dict[str, set[str]] = {"X5": set(), "X7": set()}
    for prefixe, ligne in (("X5", ecran_projet.RACCOURCIS_SAISIE),
                           ("X7", ecran_projet.RACCOURCIS_CHEMIN_CACHES)):
        maquette = _libelles_de_ligne(_raccourcis_de_la_maquette(prefixe))
        code = _libelles_de_ligne(ligne)
        assert len(maquette) >= 3 and len(code) >= 3, (
            "anti-vacuite : la lecture des libelles doit MORDRE des deux cotes",
            prefixe, sorted(maquette), sorted(code))
        assert set(maquette) - set(code) == ECARTS_ASSUMES[prefixe], (
            f"{prefixe} : la maquette porte des touches que le produit n'a pas, "
            f"hors ecart assume : {sorted(set(maquette) - set(code))}")
        assert set(code) - set(maquette) == set(), (
            f"{prefixe} : le produit porte des touches que la maquette ignore, "
            f"donc la maquette validee est perimee : "
            f"{sorted(set(code) - set(maquette))}")
        for touche in set(maquette) & set(code):
            assert code[touche] == maquette[touche], (prefixe, touche,
                                                      code[touche],
                                                      maquette[touche])


def test_l_explorateur_nomme_ses_touches_d_UNE_SEULE_facon(tmp_path):
    """F-17 : `⏎` dit `valider` et `Échap` dit `sortir`, dans les trois lignes.

    Les libelles livres etaient `⏎ ouvrir` et `Échap récents` : tous deux
    faux des qu'`E0-4` monte le meme composant -- la touche n'y ouvre rien et
    ne mene pas aux recents. Le volet symetrique verifie que la lecture des
    libelles MORD, sans quoi un analyseur qui ne trouverait aucune touche
    rendrait ce test vert sur n'importe quelle ligne.
    """
    lignes = {nom: getattr(ecran_projet, nom)
              for nom in ("RACCOURCIS_CHEMIN", "RACCOURCIS_CHEMIN_CACHES",
                          "RACCOURCIS_SAISIE")}
    for nom, ligne in lignes.items():
        libelles = _libelles_de_ligne(ligne)
        assert libelles.get("⏎") == "valider", (nom, libelles)
        assert libelles.get("Échap") == "sortir", (nom, libelles)
    # Le volet symetrique : l'analyseur lit bien le mot, quel qu'il soit.
    assert _libelles_de_ligne("⏎ ouvrir   Échap récents") == {
        "⏎": "ouvrir", "Échap": "récents"}


def test_aucun_libelle_de_Tab_ne_designe_DEUX_destinations(tmp_path, banc):
    """F-17, le coeur du finding : `Tab` portait quatre noms pour un geste.

    La mesure est **comportementale**, pas textuelle : pour chacun des quatre
    etats ou `Tab` agit, on releve le libelle annonce, on presse la touche, et
    on regarde ou l'on arrive. L'invariant : *aucun libelle ne designe deux
    destinations*. C'est exactement ce que le code livre violait --
    `Tab chemin` menait a l'explorateur depuis les recents et a la barre
    d'adresse depuis la liste.

    Deux assertions de plus, que la seule fonctionnalite ne donne pas :
    **les deux sites qui entrent dans l'explorateur annoncent le meme mot**
    (sinon `Tab champ` d'`E0-4` reviendrait sans rien casser), et **il n'y a
    que trois noms pour quatre etats**, la ou le finding en comptait quatre.
    """
    base, _ = _arborescence_imbriquee(tmp_path)
    _, recents = _trois_recents(tmp_path)

    def ou_suis_je(e):
        if e.zone != ecran_projet.ZONE_CHEMIN:
            return "hors de l'explorateur"
        return ("la barre d'adresse" if e.explorateur.dans_la_saisie
                else "la liste de l'explorateur")

    def franchir(e):
        """Le libelle annonce, puis la destination reellement atteinte."""
        libelle = _libelles_de_ligne(e.raccourcis)["Tab"]
        e.traiter("tab")
        return libelle, ou_suis_je(e)

    async def scenario_ouvrir(pilote):
        e = pilote.app.screen
        releve = {"les recents": franchir(e)}
        # **Un dossier sans element cache**, et ce n'est pas de confort :
        # `RACCOURCIS_CHEMIN_CACHES` n'annonce pas `Tab` (les sept jetons ne
        # tiennent pas dans 76 colonnes), donc un dossier de depart portant un
        # `.git` ferait lire la mauvaise ligne.
        e.explorateur.dossier = base
        e.explorateur.relire()
        e._appliquer_la_zone()
        releve["la liste"] = franchir(e)
        releve["la saisie"] = franchir(e)
        return releve

    async def scenario_creer(pilote):
        e = pilote.app.screen
        return {"le formulaire E0-4": franchir(e)}

    releves = banc(_app(ecran_projet.EcranProjet(recents=recents)),
                   scenario_ouvrir)
    releves.update(banc(_app(_creation_sur(base)), scenario_creer))

    destinations = {}
    for depart, (libelle, arrivee) in releves.items():
        destinations.setdefault(libelle, set()).add(arrivee)
    fautifs = {libelle: sorted(ou) for libelle, ou in destinations.items()
               if len(ou) > 1}
    assert fautifs == {}, ("un meme libelle pour deux destinations", fautifs,
                           releves)
    assert releves["les recents"][0] == releves["le formulaire E0-4"][0], (
        "meme geste -- entrer dans l'explorateur --, donc meme mot", releves)
    assert sorted(destinations) == ["chemin", "explorateur", "liste"], (
        sorted(destinations), releves)


def test_aucune_ligne_du_palier_zero_ne_dit_plus_Tab_champ():
    """F-17, frontiere negative avec son volet symetrique.

    `Tab champ` etait le quatrieme nom, et il n'a plus d'objet : le champ
    parent n'est plus une saisie. Le volet symetrique verifie que le balayage
    voit bien toutes les lignes -- une garde qui n'en verrait aucune serait
    verte sur tout.
    """
    lignes = {nom: valeur for nom, valeur in vars(ecran_projet).items()
              if nom.startswith("RACCOURCIS_") and isinstance(valeur, str)}
    lignes["EcranCreation.raccourcis"] = ecran_projet.EcranCreation.raccourcis
    lignes["EcranProjet.raccourcis"] = ecran_projet.EcranProjet.raccourcis
    assert len(lignes) >= 6, sorted(lignes)
    assert any("Tab " in ligne for ligne in lignes.values()), sorted(lignes)
    for nom, ligne in lignes.items():
        assert "Tab champ" not in ligne, (nom, ligne)


# ---------------------------------------------------------------------------
# Revue vague 2 bis -- E11 : la borne HAUTE de la ligne des recents
#
# `max(2, creux)` tenait la borne BASSE et n'avait aucune borne haute. Les
# chiffres, mesures au plancher (76 colonnes utiles) avant correction, avec les
# cinq cardinaux de `EPIC11-ARB-55` :
#
#     nom = 50 colonnes -> ligne = 76 colonnes  ok
#     nom = 51 colonnes -> ligne = 77 colonnes  DEBORDE -> ajuste : `… ` (M mange)
#     nom = 54 colonnes -> ligne = 80 colonnes  DEBORDE -> `3R · 2L · 1P · 0S…`
#     nom = 28 ideogrammes (51 colonnes) -> ligne = 77 colonnes  DEBORDE
#
# Le premier cardinal perdu est le `M` -- le plus tardif de la chaine, celui
# qu'`EPIC11-ARB-55` venait d'ajouter --, parce que `jetons.ajuster` coupe par
# la FIN. Les fixtures d'avant cette revue ne pouvaient pas voir le defaut :
# `_trois_recents` porte des noms de 17 caracteres au plus, pour un seuil a 51.
# ---------------------------------------------------------------------------

#: Trois noms de recent **distinguables et de largeurs croissantes**, dont deux
#: depassent le seuil (51 colonnes de nom, cardinaux compris). Le premier
#: tient : sans lui, une correction qui abregerait TOUS les noms resterait
#: verte. Le troisieme est en ideogrammes, ou chaque caractere vaut deux
#: colonnes -- **32 caracteres pour 53 colonnes** : une borne posee sur `len()`
#: le croirait a l'aise, et c'est ce mutant-la qu'il tue.
NOMS_LONGS = (
    "2026-08-14_tournage_court",                                    # 25 col
    "2026-08-21_tournage_exterieur_nuit_camera_B_prise_02_bis",     # 56 col
    "2026-08-26_" + "日" * 21,                                  # 53 col
)


def _recents_aux_noms(tmp_path, noms) -> projets.Recents:
    """Des projets reels portant `noms` sur le disque, notes du plus ancien au
    plus recent.

    Le dossier est **cree sous un identifiant ASCII puis renomme** : le schema
    v2 refuse un identifiant hors `^[A-Za-z0-9_-]+$`, alors qu'un dossier de
    projet, lui, peut porter n'importe quel nom sur le disque -- un projet
    renomme apres coup, ou pose sur un volume japonais. C'est exactement le cas
    que la ligne des recents doit tenir.

    Les cardinaux different d'un projet a l'autre : une ligne qui rendrait
    toujours ceux du premier resterait verte sur une fixture uniforme.
    """
    chemins = []
    for rang, nom in enumerate(noms):
        cree = creer_projet(tmp_path, f"source_{rang}").chemin
        cible = tmp_path / nom
        cree.rename(cible)
        _manifeste_de(cible, rang + 1, ("extraction", "pdf", "encode",
                                        "scan")[:rang + 1])
        chemins.append(cible)
    recents = projets.Recents(tmp_path / "reglages" / "recents-v1.json")
    for rang, chemin in enumerate(chemins):
        recents.noter_ouverture(chemin, quand=f"2026-08-{14 + rang:02d}T10:00:00Z")
    return recents


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_un_nom_de_recent_trop_long_cede_AVANT_les_cardinaux(tmp_path, banc,
                                                             ascii_seul):
    """E11. La ligne tient les 76 colonnes, et les CINQ initiales survivent.

    L'assertion porte sur les cinq couples, `M` compris : c'est lui que le
    garde-fou mangeait en premier, et une assertion de simple largeur
    resterait verte sur une correction qui abregerait la colonne de droite.

    **Les deux modes**, parce que le repli ASCII precede la mesure : `…` vaut
    une colonne, `...` en vaut trois, et une correction qui abregerait apres
    avoir mesure ferait deborder de deux colonnes la ligne calee juste.
    """
    recents = _recents_aux_noms(tmp_path, NOMS_LONGS)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        largeur = jetons.largeur_utile(pilote.app.size.width)
        return largeur, [pilote.app.screen.ligne_de_recent(rang, largeur)
                         for rang in range(len(NOMS_LONGS))]

    largeur, lignes = banc(_app(ecran, ascii_seul=ascii_seul), scenario)
    assert largeur == 76, largeur
    for rang, ligne in enumerate(lignes):
        assert jetons.colonnes(ligne) <= largeur, (
            f"rang {rang}, ascii={ascii_seul} : {jetons.colonnes(ligne)} "
            f"colonnes pour {largeur} -- {ligne!r}")
        assert [lettre for lettre, _ in _cardinaux_rendus(ligne)] == [
            lettre for lettre, _ in projets.LEGENDE_DES_CARDINAUX], (
            f"rang {rang}, ascii={ascii_seul} : un cardinal a ete mange par le "
            f"garde-fou -- {ligne!r}")
    # Volet symetrique : la fixture ATTEINT le defaut. Sans cette mesure, des
    # noms courts rendraient les assertions ci-dessus vertes sans rien
    # mesurer -- c'est exactement ce qui rendait `_trois_recents` aveugle.
    trop_larges = [nom for nom in NOMS_LONGS
                   if jetons.colonnes(nom) + 2 + 2 + 22 > largeur]
    assert len(trop_larges) >= 2, (
        "la fixture doit porter au moins deux noms qui debordent, dont un en "
        f"double chasse -- {[(n, jetons.colonnes(n)) for n in NOMS_LONGS]}")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_un_nom_de_recent_trop_long_est_abrege_AU_MILIEU(tmp_path, banc,
                                                         ascii_seul):
    """Volet symetrique : ce n'est pas la ligne qui est coupee, c'est le nom --
    et par le milieu.

    Deux dossiers d'un meme tournage ne se distinguent qu'a leur QUEUE
    (`_camera_A` contre `_camera_B`) et ne se datent qu'a leur TETE. Une
    troncature par la fin rendrait deux lignes identiques : c'est le mode de
    panne que `jetons.abreger_nom` existe pour empecher.

    La cible est le rang **1**, jamais le rang 0 : un abregement qui ne
    porterait que sur la premiere ligne ne se demasquerait pas autrement.
    """
    recents = _recents_aux_noms(tmp_path, NOMS_LONGS)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        largeur = jetons.largeur_utile(pilote.app.size.width)
        return [pilote.app.screen.ligne_de_recent(rang, largeur)
                for rang in range(len(NOMS_LONGS))]

    lignes = banc(_app(ecran, ascii_seul=ascii_seul), scenario)
    # `_recents_aux_noms` note du plus ancien au plus recent : le rang 0 de la
    # liste rendue est le DERNIER de `NOMS_LONGS`. Le nom latin trop long est
    # donc au rang 1.
    points = "..." if ascii_seul else "…"
    cible = lignes[1]
    gauche = re.split(r"\s{2,}", cible.strip())[0]
    assert points in gauche, (
        f"le nom doit porter la marque d'abregement -- {cible!r}")
    assert gauche.startswith("2026-08-21_"), (
        f"la TETE porte la date et doit survivre -- {cible!r}")
    assert gauche.endswith("_bis"), (
        f"la QUEUE porte la variante et doit survivre -- {cible!r}")
    # Et le nom court, lui, n'est PAS touche : une correction qui abregerait
    # tout le monde passerait les assertions ci-dessus.
    court = re.split(r"\s{2,}", lignes[2].strip())[0]
    assert court == NOMS_LONGS[0], (court, NOMS_LONGS[0])
    assert points not in court, court


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_ligne_de_recent_mesure_en_COLONNES_et_non_en_caracteres(
        tmp_path, banc, ascii_seul):
    """Le mutant « mesurer en `len()` » doit mourir ici, et nulle part ailleurs.

    Le nom en ideogrammes du rang 0 fait 32 caracteres pour 53 colonnes : une
    borne posee sur `len()` le croirait a l'aise et laisserait la ligne
    deborder. La mesure porte donc sur la ligne rendue **en colonnes**, et le
    volet symetrique verifie que les deux comptes different bel et bien sur
    cette fixture -- sans quoi le test ne separerait pas les deux mesures.
    """
    recents = _recents_aux_noms(tmp_path, NOMS_LONGS)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        largeur = jetons.largeur_utile(pilote.app.size.width)
        return pilote.app.screen.ligne_de_recent(0, largeur)

    ligne = banc(_app(ecran, ascii_seul=ascii_seul), scenario)
    assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), (
        jetons.colonnes(ligne), ligne)
    assert jetons.colonnes(NOMS_LONGS[2]) > len(NOMS_LONGS[2]), (
        "la fixture doit porter de la double chasse, sans quoi `len()` et "
        f"`colonnes()` sont le meme test -- {NOMS_LONGS[2]!r}")


def test_les_ecrans_tiennent_le_plancher_sur_un_recent_TRES_long(tmp_path,
                                                                 banc):
    """Le volet « ecran entier » de E11, sur la fixture qui atteint le defaut.

    `test_les_ecrans_tiennent_le_plancher_80x24` mesure la meme chose mais sur
    `_trois_recents`, dont le nom le plus long fait 17 caracteres : il ne
    pouvait pas voir ce defaut. C'est le meme test, avec une fixture qui peut.
    """
    recents = _recents_aux_noms(tmp_path, NOMS_LONGS)
    ecran = ecran_projet.EcranProjet(recents=recents)

    async def scenario(pilote):
        return _texte(pilote.app.screen)

    lignes = banc(_app(ecran), scenario).splitlines()
    assert len(lignes) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, len(lignes)
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), (
            jetons.colonnes(ligne), ligne)
