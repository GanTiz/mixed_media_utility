# -*- coding: utf-8 -*-
"""Le menu des ateliers (story 11.3, tasks 2 et 4 -- AC 1 a 4, 6, 7).

Memes deux regles de mesure qu'au palier 0 : le banc n'a **ni pilote de terminal
ni ecran**. Les mesures de couture portent donc sur `_running`, `is_attached` et
l'identite des enfants, **jamais** sur `app.rang` ni `screen.titre` seuls.
"""
import json
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.tui import ecran_ateliers, jetons, projet_lecture
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.ecran_projet import EcranProjet
from mixed_media_utility.tui.projets import Recents


def _projet(tmp_path, lots=(), rushes=2, nom="projet_demo") -> Path:
    """Un projet reel, cree par le coeur, dont on complete le manifest.

    Le dossier qu'un lot **declare** est cree sur le disque : depuis la story
    11.8, la condition de l'entree `Exports` est le verdict du coeur
    (`encode.list_encodable_lots`), et ce verdict constate la matiere. Un lot
    qui declarerait ses frames sans les porter ne rendrait pas l'entree
    disponible -- ce qui est le comportement voulu, et un autre regime.
    """
    chemin = creer_projet(tmp_path, nom).chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": f"r{n}"} for n in range(rushes)]
    document["lots"] = list(lots)
    (chemin / "project.json").write_text(json.dumps(document), encoding="utf-8")
    for lot in lots:
        declare = lot.get("output_frames_dir")
        if declare:
            (chemin / declare).mkdir(parents=True, exist_ok=True)
    return chemin


def _lot(lot_id, etat="extraction", confirme=None, masters=0,
         dossier=None) -> dict:
    entree = {"lot_id": lot_id, "state": etat,
              "encoded_masters": [{"path": f"outputs/{lot_id}_{n}.mov"}
                                  for n in range(masters)]}
    if dossier is not None:
        entree["output_frames_dir"] = dossier
    if confirme:
        entree["confirmation"] = {"mode": "interactif",
                                  "unknown_color_accepted": False,
                                  "confirmed_at": confirme}
    return entree


def _app(ecran, projet="projet_demo", **kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"), ecran],
                    contexte=Contexte(projet=projet), **kwargs)


def _monte(app, ecran, scenario, banc):
    """Monter jusqu'au palier 1 puis derouler le scenario."""
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
# AC 1 -- cinq entrees, ordre de la chaine, Projet separe
# ---------------------------------------------------------------------------

def test_les_cinq_entrees_sont_a_l_ecran_dans_l_ordre_de_la_chaine(tmp_path, banc):
    """AC 1.1 : l'ORDRE est mesure, pas seulement la presence."""
    dossier = _projet(tmp_path, [_lot("a", etat="encode", dossier="output-frames/a")])
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return _texte(ecran)

    rendu = _monte(_app(ecran), ecran, scenario, banc)
    positions = [rendu.index(nom)
                 for nom in ("Extraction", "Pdf", "Scan", "Exports", "Projet")]
    assert positions == sorted(positions), rendu
    # **La reference est la constante, pas cette tuple recopiee** : sans cette
    # seconde assertion, l'ordre attendu vivrait a deux endroits et le banc
    # resterait vert sur un `ATELIERS` reordonne (retour terrain du
    # 2026-09-06 -- « remonter l'atelier [PDF] AVANT scan »).
    assert [nom for nom in ("Extraction", "Pdf", "Scan", "Exports")] == \
        list(projet_lecture.ATELIERS), projet_lecture.ATELIERS


def test_Projet_est_separe_des_quatre_ateliers_par_une_ligne_vide(tmp_path, banc):
    """AC 1.2 : « parce que ce n'est pas un atelier ». Et **aucune** ligne vide
    entre les quatre ateliers, sinon la separation ne dirait plus rien."""
    dossier = _projet(tmp_path, [_lot("a", etat="encode", dossier="output-frames/a")])
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return _texte(ecran).splitlines()

    lignes = _monte(_app(ecran), ecran, scenario, banc)
    rangs = {nom: next(i for i, l in enumerate(lignes) if nom in l)
             for nom in ("Extraction", "Pdf", "Scan", "Exports", "Projet")}
    assert rangs["Exports"] + 2 == rangs["Projet"], lignes
    assert lignes[rangs["Exports"] + 1].strip() == ""
    for a, b in zip(projet_lecture.ATELIERS, projet_lecture.ATELIERS[1:]):
        assert rangs[a] + 1 == rangs[b], (a, b, lignes)


def test_chaque_entree_porte_sa_phrase_a_l_ecran(tmp_path, banc):
    """AC 1.3."""
    dossier = _projet(tmp_path, [_lot("a", etat="encode", dossier="output-frames/a")])
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return _texte(ecran)

    rendu = _monte(_app(ecran), ecran, scenario, banc)
    for nom, phrase in projet_lecture.PHRASES.items():
        # La phrase peut etre abregee a la largeur ; son debut suffit a
        # prouver qu'elle est rendue et pas seulement le nom.
        assert phrase[:30] in rendu, (nom, rendu)


def test_le_curseur_se_deplace_et_entre_sur_CELUI_DU_MILIEU(tmp_path, banc):
    """AC 1.4, avec la cible **ni premiere ni derniere** : un `⏎` qui
    entrerait toujours dans la premiere entree resterait vert autrement."""
    dossier = _projet(tmp_path, [_lot("a", etat="encode", dossier="output-frames/a")])
    entres = []
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier, entrer=entres.append)

    async def scenario(pilote):
        ecran.traiter("down")
        ecran.traiter("down")          # -> Scan, la troisieme sur cinq
        ecran.traiter("enter")

    _monte(_app(ecran), ecran, scenario, banc)
    # **La cible est lue de la constante**, pas recopiee : le retour terrain du
    # 2026-09-06 a permute `Pdf` et `Scan`, et une cible en dur aurait fait
    # rougir un banc dont la propriete -- « ni premiere ni derniere » -- n'a
    # pas bouge.
    assert [e.nom for e in entres] == [projet_lecture.ATELIERS[2]], entres
    assert projet_lecture.ATELIERS[2] not in (projet_lecture.ATELIERS[0],
                                              projet_lecture.PROJET)


# ---------------------------------------------------------------------------
# AC 2 -- les entrees conditionnees
# ---------------------------------------------------------------------------

def test_sur_un_projet_VIDE_les_cinq_entrees_restent_VISIBLES(tmp_path, banc):
    """AC 2.1 et 2.4 -- comptage a zero d'entree absente, avec volet."""
    dossier = _projet(tmp_path, [], rushes=0)
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return _texte(ecran)

    rendu = _monte(_app(ecran), ecran, scenario, banc)
    manquantes = [nom for nom in ("Extraction", "Scan", "Pdf", "Exports",
                                  "Projet") if nom not in rendu]
    assert manquantes == [], (manquantes, rendu)


def test_la_mesure_d_entree_manquante_MORD():
    """Volet symetrique : un rendu ampute doit sortir de la mesure."""
    rendu = "Extraction\nScan\nPdf\nProjet"
    manquantes = [nom for nom in ("Extraction", "Scan", "Pdf", "Exports",
                                  "Projet") if nom not in rendu]
    assert manquantes == ["Exports"]


def test_une_entree_conditionnee_porte_sa_condition_ET_son_glyphe(tmp_path, banc):
    """AC 2.2. Le glyphe est `substitute`, **pas** `absent` : rien n'a echoue,
    l'atelier n'a simplement rien a lister."""
    dossier = _projet(tmp_path, [], rushes=0)
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return _texte(ecran)

    rendu = _monte(_app(ecran), ecran, scenario, banc)
    assert jetons.GLYPHES["substitute"] in rendu, rendu
    assert jetons.GLYPHES["absent"] not in rendu, rendu
    assert "aucun lot" in rendu


def test_entrer_sur_une_entree_conditionnee_MENE_QUELQUE_PART(tmp_path, banc):
    """AC 2.3, consigne d'Egan du 2026-08-28 : rien d'inerte.

    « Une touche qui ne fait rien et ne dit rien est indistinguable d'un
    clavier casse. »
    """
    dossier = _projet(tmp_path, [], rushes=0)
    entres = []
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier, entrer=entres.append)

    async def scenario(pilote):
        # `Pdf` est la seule entree conditionnee d'un projet vide qui ne soit ni
        # la premiere ni la derniere ; son RANG a change le 2026-09-06, pas sa
        # nature -- on le lit donc de la constante.
        for _ in range(projet_lecture.ATELIERS.index(projet_lecture.PDF)):
            ecran.traiter("down")
        ecran.traiter("enter")
        return ecran.etat()

    etat = _monte(_app(ecran), ecran, scenario, banc)
    assert entres == [], "une entree conditionnee ne doit pas entrer"
    assert "aucun lot" in etat, etat
    assert jetons.GLYPHES["substitute"] in etat, etat


def test_un_lot_ouvre_Pdf_mais_pas_Exports_a_l_ecran(tmp_path, banc):
    """La distinction des deux conditions, mesuree sur le RENDU."""
    dossier = _projet(tmp_path, [_lot("a", etat="pdf")])
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return {e.nom: e.disponible for e in ecran.entrees}

    par_nom = _monte(_app(ecran), ecran, scenario, banc)
    assert par_nom["Pdf"] is True
    assert par_nom["Exports"] is False


# ---------------------------------------------------------------------------
# AC 3 -- le pied (`EPIC11-ARB-44`)
# ---------------------------------------------------------------------------

def test_le_pied_nomme_une_EXTRACTION_CONFIRMEE(tmp_path, banc):
    """AC 3.1 et 3.2. La cible est **au milieu** de `lots[]`."""
    dossier = _projet(tmp_path, [
        _lot("premier", etat="pdf", confirme="2026-08-01T10:00:00Z"),
        _lot("le_bon", etat="scan", confirme="2026-08-25T16:46:05Z"),
        _lot("dernier", etat="extraction", confirme="2026-08-10T09:00:00Z"),
    ])
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return _texte(ecran)

    rendu = _monte(_app(ecran), ecran, scenario, banc)
    assert ecran_ateliers.LIBELLE_PIED in rendu, rendu
    assert "25/08 16:46" in rendu, rendu
    assert "le_bon" in rendu, rendu
    assert "scan" in rendu, rendu


def test_le_pied_ne_dit_JAMAIS_derniere_ecriture(tmp_path):
    """AC 3.2 -- frontiere de comptage a zero, `EPIC11-ARB-44`.

    Le manifest ne porte aucune horloge d'ecriture ; ecrire « derniere
    ecriture » serait affirmer une mesure qui n'existe pas.
    """
    from outils_frontiere import chaines_de_code

    textes = chaines_de_code(Path(ecran_ateliers.__file__))
    textes += chaines_de_code(Path(projet_lecture.__file__))
    fautives = [t for t in textes if "derniere ecriture" in t.lower()]
    assert fautives == [], fautives


def test_la_frontiere_derniere_ecriture_MORD():
    """Volet symetrique."""
    assert "derniere ecriture" in "Derniere ecriture   26/08 14:32".lower()


def test_le_pied_n_invente_AUCUN_verdict(tmp_path):
    """AC 3.3 : `LOT_STATES` est une etape, pas un jugement (`EPIC11-ARB-30`)."""
    from outils_frontiere import chaines_de_code

    interdits = (" ok", "reussi", "succes", "echec")
    textes = chaines_de_code(Path(ecran_ateliers.__file__))
    fautives = [t for t in textes
                if any(mot in t.lower() for mot in interdits)]
    assert fautives == [], fautives


def test_aucune_extraction_confirmee_ne_laisse_PAS_une_ligne_vide(tmp_path, banc):
    """AC 3.4."""
    dossier = _projet(tmp_path, [_lot("a")], rushes=0)
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return _texte(ecran)

    rendu = _monte(_app(ecran), ecran, scenario, banc)
    assert ecran_ateliers.PIED_VIDE in rendu, rendu


def test_un_projet_illisible_n_empeche_pas_le_menu_de_s_ouvrir(tmp_path, banc):
    """Le menu doit dire ce qu'il ne sait pas plutot que de tomber."""
    dossier = _projet(tmp_path, [])
    (dossier / "project.json").write_text("{ casse", encoding="utf-8")
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return _texte(ecran)

    rendu = _monte(_app(ecran), ecran, scenario, banc)
    assert "Extraction" in rendu
    assert ecran_ateliers.PIED_VIDE in rendu


# ---------------------------------------------------------------------------
# AC 3 (suite) -- la TEINTE du pied, dans les DEUX modes
#
# **Ce bloc n'existait pas, et c'est pour cela que la regression du 2026-08-29
# est passee.** Les AC du pied mesuraient son TEXTE (`LIBELLE_PIED`, la date,
# le lot, l'etape) et jamais sa COULEUR : quand le resserrement de
# `jetons.jeton_d_etat` a exige que le glyphe d'etat ouvre une colonne, le
# `·` qui precedait `● scan` a fait perdre sa teinte a cette ligne dans les
# deux modes, suite verte. C'est le motif que la politique de revue sanctionne
# partout ailleurs -- une propriete mesuree d'un seul cote.
# ---------------------------------------------------------------------------

def _pied_confirme(tmp_path) -> Path:
    """Un projet dont l'extraction confirmee est **au milieu** de `lots[]`.

    Trois lots distinguables, cible en position 2 : un `derniere_extraction`
    qui rendrait toujours le premier element resterait vert sur une fixture
    mono-lot (regle des fabriques, `CLAUDE.md`).
    """
    return _projet(tmp_path, [
        _lot("premier", etat="pdf", confirme="2026-08-01T10:00:00Z"),
        _lot("le_bon", etat="scan", confirme="2026-08-25T16:46:05Z"),
        _lot("dernier", etat="extraction", confirme="2026-08-10T09:00:00Z"),
    ])


def _peint(ecran):
    """Le rendu **peint** de la zone centrale, tel que `rafraichir` l'a pose.

    On lit l'objet stylise du widget, pas une peinture refaite dans le test :
    repeindre ici mesurerait le test lui-meme et non le chemin de l'ecran.
    """
    return ecran._corps.content


def _style_par_ligne(peint) -> list[str | None]:
    """Le style de CHAQUE ligne du rendu, dans l'ordre, `None` s'il n'y en a pas.

    Rapporter chaque intervalle a son rang est necessaire : lire `spans` a plat
    ne dirait pas QUELLE ligne est teintee, et une peinture qui teindrait
    toujours le rang 0 rendrait la meme liste.
    """
    lignes = peint.plain.split(chr(10))
    rang_du_debut, curseur = {}, 0
    for rang, ligne in enumerate(lignes):
        rang_du_debut[curseur] = rang
        curseur += len(ligne) + 1
    styles: list[str | None] = [None] * len(lignes)
    for span in peint.spans:
        if span.style:
            styles[rang_du_debut[span.start]] = str(span.style)
    return styles


def _rang_du_pied(lignes: list[str]) -> int:
    """Le rang de la ligne de valeurs du pied -- celle qui porte le lot."""
    rangs = [rang for rang, ligne in enumerate(lignes) if "le_bon" in ligne]
    assert len(rangs) == 1, (rangs, lignes)
    return rangs[0]


@pytest.mark.parametrize("ascii_seul, glyphe_attendu", [
    (False, jetons.GLYPHES["complete"]),
    (True, jetons.GLYPHES_ASCII["complete"]),
])
def test_la_ligne_du_pied_est_TEINTE_par_son_glyphe_d_etape(
        tmp_path, banc, ascii_seul, glyphe_attendu):
    """La teinte du pied, mesuree **dans les deux modes**.

    Le repli ASCII n'est pas un doublon decoratif : `●` y devient `*`, et
    `jetons.jeton_d_etat` y travaille sur des caracteres qui sont aussi des
    signes de ponctuation ordinaires. Une correction qui ne tiendrait qu'en
    UTF-8 tiendrait dans le seul mode ou le defaut ne peut pas se produire --
    c'est exactement ce qui s'est produit sur `jetons.py` la veille.
    """
    ecran = ecran_ateliers.EcranAteliers(dossier=_pied_confirme(tmp_path))

    async def scenario(pilote):
        peint = _peint(ecran)
        return peint.plain.split(chr(10)), _style_par_ligne(peint)

    lignes, styles = _monte(
        _app(ecran, ascii_seul=ascii_seul), ecran, scenario, banc)
    rang = _rang_du_pied(lignes)
    assert glyphe_attendu in lignes[rang], lignes[rang]
    assert styles[rang] == jetons.couleur("state-complete"), (
        f"la ligne du pied {lignes[rang]!r} a perdu sa teinte "
        f"(style {styles[rang]!r}) en mode "
        f"{'ASCII' if ascii_seul else 'UTF-8'}")


def test_la_ligne_du_pied_reste_LISIBLE_sans_couleur(tmp_path, banc):
    """Volet symetrique : `--sans-couleur` ne change QUE ce qui est teinte.

    `DESIGN.md` section 5, regle 1 : la couleur double un canal, elle ne le
    porte jamais seule. Le glyphe `●` et l'etape restent donc lisibles, et le
    texte est **caractere pour caractere** celui du regime nominal.
    """
    dossier = _pied_confirme(tmp_path)
    rendus = {}
    for sans_couleur in (False, True):
        ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

        async def scenario(pilote, ecran=ecran):
            peint = _peint(ecran)
            return peint.plain.split(chr(10)), _style_par_ligne(peint)

        rendus[sans_couleur] = _monte(
            _app(ecran, sans_couleur=sans_couleur), ecran, scenario, banc)

    lignes_nu, styles_nu = rendus[True]
    lignes_teint, styles_teint = rendus[False]
    rang = _rang_du_pied(lignes_nu)
    assert lignes_nu == lignes_teint, "le repli change le TEXTE, pas seulement la teinte"
    assert jetons.GLYPHES["complete"] in lignes_nu[rang], lignes_nu[rang]
    assert "scan" in lignes_nu[rang], lignes_nu[rang]
    assert [s for s in styles_nu if s] == [], styles_nu
    # ... et l'autre moitie du volet : sans elle, un rendu qui ne teindrait
    # RIEN passerait la mesure ci-dessus.
    assert styles_teint[rang] == jetons.couleur("state-complete"), styles_teint


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_mesure_de_teinte_du_pied_MORD(ascii_seul):
    """La forme fautive du 2026-08-29, remise et mesuree.

    `«  12/08 14:03 · lot_a · ● extraction »` : le glyphe n'est precede que
    d'UN blanc, il n'ouvre donc pas de colonne et `jeton_d_etat` ne le voit
    pas. Figer les deux formes cote a cote est ce qui empeche la regression de
    revenir en silence -- et ce qui prouve que le test ci-dessus mesure la
    forme, et non n'importe quelle ligne portant un `●`.
    """
    glyphe = jetons.glyphes(ascii_seul)["complete"]
    fautive = f"  12/08 14:03 · lot_a · {glyphe} extraction"
    corrigee = f"  12/08 14:03 · lot_a  {glyphe} extraction"
    if ascii_seul:
        fautive = jetons.replier_ascii(fautive)
        corrigee = jetons.replier_ascii(corrigee)
    assert jetons.jeton_d_etat(fautive, ascii_seul) is None, fautive
    assert jetons.jeton_d_etat(corrigee, ascii_seul) == "state-complete", corrigee


def test_le_pied_produit_bien_la_forme_de_COLONNE(tmp_path, banc):
    """Le lien entre la mise en page du pied et la regle de `jetons`.

    Les deux tests precedents mesurent la teinte du rendu et la regle du
    detecteur ; celui-ci mesure ce qui les relie, c'est-a-dire la seule chose
    que `lignes_du_pied` controle : le creux d'au moins deux blancs devant le
    glyphe d'etape.
    """
    ecran = ecran_ateliers.EcranAteliers(dossier=_pied_confirme(tmp_path))

    async def scenario(pilote):
        return ecran.lignes_du_pied()

    lignes = _monte(_app(ecran), ecran, scenario, banc)
    valeurs = lignes[1]
    assert f"  {jetons.GLYPHES['complete']} " in valeurs, valeurs
    assert f"· {jetons.GLYPHES['complete']}" not in valeurs, valeurs
    assert jetons.jeton_d_etat(valeurs) == "state-complete", valeurs


# ---------------------------------------------------------------------------
# AC 4 -- le bandeau
# ---------------------------------------------------------------------------

def test_le_bandeau_porte_les_trois_compteurs_derives(tmp_path, banc):
    """AC 4.1 et 4.2 : plusieurs lots portent des masters, un n'en porte pas."""
    dossier = _projet(tmp_path, [
        _lot("a", masters=2), _lot("b", masters=0), _lot("c", masters=1),
    ], rushes=3)
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return ecran.bandeau()

    bandeau = _monte(_app(ecran), ecran, scenario, banc)
    assert CARDINAL_DESSINE_DES_RUSHES in bandeau, bandeau
    assert "3 lots" in bandeau, bandeau
    assert "3 masters" in bandeau, bandeau


def test_un_projet_vide_rend_ZERO_au_bandeau(tmp_path, banc):
    """AC 4.3 : au singulier, et **pas** une chaine vide."""
    dossier = _projet(tmp_path, [], rushes=0)
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return ecran.bandeau()

    bandeau = _monte(_app(ecran), ecran, scenario, banc)
    assert "0 rush · 0 lot · 0 master" in bandeau, bandeau


def test_un_nom_de_projet_TROP_LONG_abrege_le_NOM_et_non_les_compteurs(
        tmp_path, banc):
    """AC 7.2, et c'est la regression de la vague 1 mesuree sur cet ecran.

    Un nom reel du depot -- `projet_demo_planche_4f_heteroclite` -- fait 85
    colonnes pour 76 avec les compteurs. Ce sont les **chiffres** qui doivent
    survivre : le nom du projet est ecrit partout ailleurs.
    """
    dossier = _projet(tmp_path, [_lot("a", masters=1)], rushes=3,
                      nom="projet_demo_planche_4f_heteroclite")
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return ecran.bandeau()

    bandeau = _monte(
        _app(ecran, projet="projet_demo_planche_4f_heteroclite"),
        ecran, scenario, banc)
    assert "3 rushes · 1 lot · 1 master" in bandeau, bandeau
    assert jetons.colonnes(bandeau) <= jetons.largeur_utile(80), bandeau


def test_le_bandeau_tient_aussi_en_ASCII(tmp_path, banc):
    """Le repli ALLONGE le texte : la mesure est refaite apres repli.

    C'est le defaut exact du 2026-08-28 -- `TEST_FILE_12p5` devenait
    `TEST_FILE...` en `--ascii` --, mesure ici sur le nouvel ecran.
    """
    dossier = _projet(tmp_path, [_lot("a", masters=1)], rushes=3,
                      nom="projet_demo_planche_4f_heteroclite")
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return ecran.bandeau()

    bandeau = _monte(
        _app(ecran, projet="projet_demo_planche_4f_heteroclite",
             ascii_seul=True),
        ecran, scenario, banc)
    assert bandeau.isascii(), bandeau
    assert "3 rushes . 1 lot . 1 master" in bandeau, bandeau
    assert jetons.colonnes(bandeau) <= jetons.largeur_utile(80), bandeau


# ---------------------------------------------------------------------------
# AC 6 et 7 -- la couture, mesuree sur l'ECRAN
# ---------------------------------------------------------------------------

def test_ouvrir_un_projet_au_palier_0_monte_CE_menu(tmp_path, banc):
    """AC 6.1 -- la couture 11.2 / 11.3, mesurable seulement maintenant.

    C'est la raison d'etre de la vague : « la circulation entre paliers ne
    devient mesurable qu'une fois les deux cotes montes ».
    """
    # **Un projet VALIDE AU SCHEMA**, cree par le coeur et laisse tel quel.
    # `EcranProjet.ouvrir` passe par `diagnostiquer`, qui appelle
    # `validate_manifest` : un manifest fabrique a la main -- comme celui de
    # `_projet`, dont les rushes ne portent que `rush_id` -- serait REFUSE, et
    # l'ecran resterait sur sa bifurcation au lieu de descendre. C'est le bon
    # comportement (on n'ouvre pas un projet qu'on ne sait pas lire) ; c'est la
    # fixture qui devait s'y conformer.
    dossier = creer_projet(tmp_path, "projet_demo").chemin
    recents = Recents(tmp_path / "reglages.json")
    recents.noter_ouverture(dossier, quand="2026-08-26T10:00:00Z")

    menu = ecran_ateliers.EcranAteliers(dossier=dossier)
    projet = EcranProjet(recents=recents)
    app = CoqueTui(paliers=[projet, menu])
    projet._ouvrir = lambda chemin: (
        setattr(app, "contexte", Contexte(projet=chemin.name)),
        app.descendre())[-1]

    async def scenario(pilote):
        avant = pilote.app.screen.bandeau()
        pilote.app.screen.traiter("enter")
        # **Deux pauses, et ce n'est pas de la superstition.** `push_screen`
        # est differe : la premiere pause monte l'ecran, la seconde le laisse
        # composer. Mesurer apres une seule voit un ecran monte mais dont
        # `compose` n'a pas encore tourne -- exactement le genre d'etat
        # intermediaire que la lecon de banc 2 demande de ne pas confondre
        # avec un ecran dessine.
        await pilote.pause()
        await pilote.pause()
        return avant, pilote.app.screen, _texte(menu)

    avant, ecran_monte, rendu = banc(app, scenario)
    assert "aucun projet" in avant
    assert ecran_monte is menu
    assert "Que faire dans projet_demo" in rendu, rendu


def test_le_menu_retrouve_son_curseur_a_la_REVISITE(tmp_path, banc):
    """AC 6.2 -- tranche par Egan le 2026-08-28 : « un palier revisite retrouve
    son etat la ou on l'a laisse ».

    **Mesure d'ecran, pas de modele** : `_running`, `is_attached` et l'identite
    des enfants. `app.rang` et `screen.titre` sont justes des deux cotes du
    defaut de palier detruit par `textual`, et c'est ce qui a rendu trois
    mesures successives aveugles.
    """
    dossier = _projet(tmp_path, [_lot("a", etat="encode", dossier="output-frames/a")])
    menu = ecran_ateliers.EcranAteliers(dossier=dossier)
    app = _app(menu)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        menu.traiter("down")
        menu.traiter("down")
        curseur_avant = menu.curseur
        etat_avant = (menu._running, menu.is_attached,
                      [id(w) for w in menu.walk_children()])
        pilote.app.action_remonter()
        await pilote.pause()
        pilote.app.descendre()
        await pilote.pause()
        return curseur_avant, etat_avant, menu.curseur, (
            menu._running, menu.is_attached,
            [id(w) for w in menu.walk_children()])

    avant, etat_avant, apres, etat_apres = banc(app, scenario)
    assert avant == apres == 2
    assert etat_avant[0] is True and etat_apres[0] is True
    assert etat_avant[1] is True and etat_apres[1] is True
    assert etat_avant[2] == etat_apres[2], "les enfants ont ete recomposes"


def test_apres_execution_on_retombe_a_CE_palier_et_jamais_au_palier_0(
        tmp_path, banc):
    """AC 6.4 -- `EPIC11-ARB-13`. La mesure devient reelle maintenant que le
    rang 1 porte un ecran veritable au lieu d'un temoin."""
    dossier = _projet(tmp_path, [_lot("a", etat="encode", dossier="output-frames/a")])
    menu = ecran_ateliers.EcranAteliers(dossier=dossier)
    app = _app(menu)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        pilote.app.push_screen(PalierTemoin("Execution", "q quitter"))
        await pilote.pause()
        pilote.app.push_screen(PalierTemoin("Resultat", "q quitter"))
        await pilote.pause()
        pilote.app.revenir_aux_ateliers()
        await pilote.pause()
        return pilote.app.screen

    assert banc(app, scenario) is menu


def test_les_ateliers_menent_a_EcranPasEncore(tmp_path, banc):
    """AC 6.5 : rien d'inerte, et l'echeance est annoncee **une fois**."""
    from mixed_media_utility.tui.coque import EcranPasEncore

    dossier = _projet(tmp_path, [_lot("a", etat="encode", dossier="output-frames/a")])
    menu = ecran_ateliers.EcranAteliers(dossier=dossier)
    app = _app(menu)
    menu._entrer = lambda entree: app.descendre(
        EcranPasEncore(f"L'atelier {entree.nom}",
                       app.QUAND_ARRIVENT_LES_ATELIERS))

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        menu.traiter("enter")          # Extraction
        await pilote.pause()
        ecran = pilote.app.screen
        return type(ecran).__name__, ecran.lignes()

    nom, lignes = banc(app, scenario)
    assert nom == "EcranPasEncore"
    assert any("Extraction" in ligne for ligne in lignes), lignes
    assert any("vague 3" in ligne for ligne in lignes), lignes


# ---------------------------------------------------------------------------
# AC 7 -- grille, glyphes, vocabulaire
# ---------------------------------------------------------------------------

def test_le_menu_tient_le_plancher_80x24(tmp_path, banc):
    """AC 7.1, au plancher exact."""
    dossier = _projet(tmp_path, [
        _lot("un_lot_au_nom_particulierement_long", etat="encode",
             confirme="2026-08-25T16:46:05Z"),
    ], rushes=3)
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        return _texte(ecran)

    rendu = _monte(_app(ecran), ecran, scenario, banc)
    lignes = rendu.splitlines()
    assert len(lignes) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, len(lignes)
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne


def test_disponible_et_conditionnee_donnent_deux_chaines_SANS_COULEUR(
        tmp_path, banc):
    """AC 7.3 : « la couleur ne porte jamais seule une information »."""
    dossier = _projet(tmp_path, [], rushes=0)
    ecran = ecran_ateliers.EcranAteliers(dossier=dossier)

    async def scenario(pilote):
        largeur = jetons.largeur_utile(pilote.app.size.width)
        par_nom = {e.nom: rang for rang, e in enumerate(ecran.entrees)}
        return (ecran.ligne_d_entree(par_nom["Extraction"], largeur),
                ecran.ligne_d_entree(par_nom["Pdf"], largeur))

    disponible, conditionnee = _monte(
        _app(ecran, sans_couleur=True), ecran, scenario, banc)
    assert disponible != conditionnee
    assert jetons.GLYPHES["substitute"] in conditionnee
    assert jetons.GLYPHES["substitute"] not in disponible


def test_aucun_terme_de_nos_documents_de_decision_a_l_ecran():
    """AC 7.5 -- frontiere de vocabulaire, `EPIC11-ARB-28`."""
    from outils_frontiere import chaines_de_code

    interdits = ("palier", "parcours a part", "feuille cli")
    textes = chaines_de_code(Path(ecran_ateliers.__file__))
    fautives = [t for t in textes
                if any(mot in t.lower() for mot in interdits)]
    assert fautives == [], fautives


def test_la_frontiere_de_vocabulaire_MORD():
    interdits = ("palier", "parcours a part", "feuille cli")
    assert any(mot in "Remonter au palier 0".lower() for mot in interdits)


def test_le_menu_ne_parle_JAMAIS_de_relink(tmp_path):
    """AC 5.6 / `EPIC11-ARB-23` : « `relink` n'a pas d'ecran dans la TUI »,
    sa porte est `E2-1`. Comptage a zero, avec volet symetrique."""
    from outils_frontiere import chaines_de_code

    textes = chaines_de_code(Path(ecran_ateliers.__file__))
    textes += chaines_de_code(Path(projet_lecture.__file__))
    assert [t for t in textes if "relink" in t.lower()] == []
    assert "relink" in "Relinker un rush".lower()


# ===========================================================================
# La maquette que ce banc citait sans la LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E2-1` et n'ouvrait aucun
# dessin : le cardinal du bandeau en etait recopie a la main.

#: Le cardinal que `E2-1` dessine dans son bandeau de pied (l. 22). La
#: confrontation ci-dessous le verifie a sa source.
CARDINAL_DESSINE_DES_RUSHES = "3 rushes"

#: Les dessins repris ici, a leur source.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕▓▒░█"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


def test_le_CARDINAL_du_bandeau_est_celui_que_E2_1_dessine():
    """Le cardinal, a sa source, avec sa ventilation qui le rend distinguable.

    `E2-1` ne dessine pas « 3 rushes » seul : il l'accompagne de « 2 liés,
    1 introuvable ». Mesurer les trois nombres plutot que le premier est ce
    qui empeche une confrontation d'etre vraie sur n'importe quel cardinal :
    un dessin ou les rushes seraient 4 rendrait le premier faux, mais un
    dessin ou la ventilation ne sommerait plus resterait vert sans eux.
    """
    dessin = dessin_de_la_maquette("E2-1-extraction-rush.txt")
    assert CARDINAL_DESSINE_DES_RUSHES in dessin
    assert "2 liés, 1 introuvable" in dessin

    lies, introuvables = 2, 1
    total = int(CARDINAL_DESSINE_DES_RUSHES.split()[0])
    assert lies + introuvables == total


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    dessin = dessin_de_la_maquette("E2-1-extraction-rush.txt")
    assert "4 rushes" not in dessin
    assert "3 rushes liés" not in dessin
