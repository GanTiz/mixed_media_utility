# -*- coding: utf-8 -*-
"""`EPIC11-ARB-158` -- la navigation du formulaire de calibration (`E3-9`).

**Ce banc et lui seul mesure ce lot.** Aucun autre n'y ecrit.

Verbatim d'Egan, 2026-09-01, qui EST la specification :

> Il faudrait passer d'un champ a l'autre avec les fleches haut-bas et non avec
> tab. Le choix du oui/non n'est pas instinctif, la touche entree renvoie a la
> validation. Il faudrait donc naviguer avec les fleches gauche et droite mais
> on ne le fait nulle part ailleurs. Il faut donc que le toggle s'enclenche avec
> espace oui/non avec oui surligne et on ecrit "Espace Oui/non" quand le curseur
> est sur ce champ dans l'aide en pied de page. La validation avec Entree n'est
> pas claire. Il faut qu'il y ait un choix explicite en bas du formulaire :
> Valider. On y accede en descendant avec les fleches.

**Le raisonnement d'Egan est conserve, pas seulement sa conclusion** : il ecarte
lui-meme les fleches gauche/droite (« on ne le fait nulle part ailleurs ») avant
de choisir `Espace`. La coherence du parcours prime sur la commodite du
controle, et c'est ce que le banc mesure -- pas seulement que `Espace` marche.

**`Espace` est LIBRE dans ce parcours, et c'est verifie plutot que suppose.**
La touche est prise dans l'explorateur du DEPOT (`E3-1`), ou elle coche
(`selection_multiple=True`). L'explorateur de `E3-9` ne l'est pas : sa ligne de
raccourcis ne porte pas `Espace cocher`, et `raccourcis_de_l_explorateur` ne
l'ajoute que sous `selection_multiple`. Un test le mesure ci-dessous, dans les
deux sens -- sans quoi ce lot creerait l'exception muette que le brief interdit.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility.tui import atelier_scan_calibrate as calib
from mixed_media_utility.tui import ecran_projet, explorateur, jetons
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le pied du palier temoin. Il n'est pas invente : `E1-1`, le menu des
#: ateliers que ce temoin double, le dessine -- et la confrontation en fin de
#: fichier le verifie a sa source.
PIED_DU_PALIER = "Q quitter"


def _app(ecran, ascii_seul: bool = False) -> CoqueTui:
    app = CoqueTui([PalierTemoin("Ateliers", PIED_DU_PALIER), ecran],
                   Contexte("projet", "Scan"),
                   ascii_seul=ascii_seul)
    return app


def _pieds_apres_une_touche(ecran, mention: str) -> set[str]:
    """Les champs dont le pied porte `mention`, **apres une vraie touche**.

    **Le detour par `↓` n'est pas du zele, il ferme un defaut mesure.** La
    premiere redaction de ce banc posait `formulaire.champ` puis appelait
    `_appliquer_la_zone()` a la main. Elle mesurait donc la TABLE du pied, pas
    ce que l'operateur lit : le produit n'appelait `_appliquer_la_zone` qu'au
    changement de ZONE, si bien que le pied restait fige pendant qu'on
    descendait dans le formulaire. Le banc etait vert, l'ecran muet.

    Un test qui appelle lui-meme le mecanisme qu'il veut mesurer ne mesure que
    ce mecanisme. On passe donc par la touche, comme l'operateur.
    """
    champs = ecran.formulaire.champs()
    ecran.formulaire.champ = champs[0]
    ecran._appliquer_la_zone()
    portent = {champs[0]} if mention in ecran.raccourcis else set()
    for _ in range(len(champs) - 1):
        ecran.zone = calib.ZONE_FORMULAIRE
        ecran.traiter("down")
        if mention in ecran.raccourcis:
            portent.add(ecran.formulaire.champ)
    return portent


def _ecran_pret(tmp_path: Path):
    """`E3-9` avec un scan pose et une mesure : les SIX lignes existent.

    La ligne de reprise n'apparait qu'avec une mesure, et le banc en a besoin --
    c'est la sixieme cible de la navigation, et un formulaire a cinq lignes ne
    distinguerait pas « la boucle saute une ligne » de « la boucle s'arrete ».
    """
    class _Mesure:
        forme, cardinal, octets, dpi, fichiers = "pdf", 4, 1000, 300.0, 1
    class _Source:
        mesure = _Mesure()
        chemin = tmp_path / "planche.pdf"
        forme, cardinal, dpi, fichiers = "pdf", 4, 300.0, 1
        est_multiple = False
    ecran = calib.EcranCalibrerLaChaine(tmp_path, calibrer=lambda _f: None)
    ecran.formulaire.poser_le_scan(_Source())
    return ecran


# --- point 1 : les fleches haut/bas parcourent les champs -------------------


def test_les_FLECHES_parcourent_les_champs_et_Tab_n_est_plus_annonce(
    tmp_path: Path
) -> None:
    """Point 1 d'Egan : « d'un champ a l'autre avec les fleches haut-bas ».

    La descente est mesuree sur **la liste que le code parcourt**
    (`formulaire.champs()`), et elle traverse les SEPT lignes -- les six
    d'origine plus `Valider`. Une mesure sur deux ou trois pas ne distinguerait
    pas une boucle correcte d'une boucle qui s'arrete a la premiere.
    """
    ecran = _ecran_pret(tmp_path)
    champs = ecran.formulaire.champs()
    assert len(champs) == 7, champs

    # Le depart est POSE : `poser_le_scan` avance deja le curseur, et partir de
    # la ou il se trouve ferait mesurer une rotation plutot qu'un parcours.
    ecran.formulaire.champ = champs[0]
    vus = [ecran.formulaire.champ]
    for _ in range(len(champs) - 1):
        ecran.traiter("down")
        vus.append(ecran.formulaire.champ)
    assert vus == list(champs)

    # Et la remontee rend EXACTEMENT le chemin inverse : une descente juste
    # avec une remontee fausse serait verte sous une mesure a sens unique.
    remonte = [ecran.formulaire.champ]
    for _ in range(len(champs) - 1):
        ecran.traiter("up")
        remonte.append(ecran.formulaire.champ)
    assert remonte == list(reversed(champs))


def test_la_ligne_de_raccourcis_n_annonce_PLUS_Tab_mais_les_FLECHES(
    tmp_path: Path
) -> None:
    """« et non avec tab » : la ligne ne doit plus vendre `Tab`.

    Ensemble EXACT sur les lignes du module, pas une appartenance : une
    variante oubliee qui continuerait d'annoncer `Tab champ` serait verte sous
    « la ligne courante ne porte pas Tab ».
    """
    lignes = {nom: valeur for nom, valeur in vars(calib).items()
              if nom.startswith("RACCOURCIS_") and isinstance(valeur, str)}
    assert lignes, "aucune ligne de raccourcis trouvee : le banc mesurerait a vide"
    portant_tab = {nom for nom, v in lignes.items() if "Tab" in v}
    assert portant_tab == set()


# --- point 2 : Espace bascule le oui/non, l'option retenue est surlignee ----


def test_ESPACE_bascule_le_oui_non_et_SEULEMENT_sur_ce_champ(
    tmp_path: Path
) -> None:
    """Point 2 : « le toggle s'enclenche avec espace ».

    Et le volet qui compte autant : `Espace` **ne bascule que la**. Sur les
    trois champs de saisie, une espace est un CARACTERE qui doit s'ecrire --
    `EPIC11-ARB-68` (« toute lettre imprimable est du texte a cote d'un champ
    de saisie ») vaut aussi pour l'espace, et un commentaire est precisement
    l'endroit ou l'on en tape.
    """
    ecran = _ecran_pret(tmp_path)
    ecran.formulaire.champ = calib.CHAMP_DEFAUT
    depart = ecran.formulaire.devient_le_defaut
    ecran.traiter("space")
    assert ecran.formulaire.devient_le_defaut is not depart
    ecran.traiter("space")
    assert ecran.formulaire.devient_le_defaut is depart

    # Sur un champ de saisie, l'espace S'ECRIT.
    ecran.formulaire.champ = calib.CHAMP_COMMENTAIRE
    for touche in "ab":
        ecran.traiter(touche, touche)
    ecran.traiter("space", " ")
    ecran.traiter("c", "c")
    assert ecran.formulaire.commentaire == "ab c"
    # et il n'a rien bascule au passage
    assert ecran.formulaire.devient_le_defaut is depart


@pytest.mark.parametrize("ascii_seul", MODES)
def test_l_option_RETENUE_est_surlignee_et_l_autre_non(
    tmp_path: Path, ascii_seul: bool, banc
) -> None:
    """Point 2, seconde moitie : « avec oui surligne ».

    Le surlignage est porte par la CASSE, et il double le glyphe `(•)` plutot
    que de le remplacer -- `DESIGN.md` section 5 : « aucune information n'est
    portee par la couleur seule », et ici aucune ne l'est par le glyphe seul.

    **La casse plutot qu'une peinture intra-ligne, et c'est un choix assume** :
    `jetons.peindre` colore des LIGNES ENTIERES, et un surlignage de sous-chaine
    demanderait d'y ajouter un mecanisme -- partage par tous les ecrans du
    produit -- pour un quart d'un retour. La casse tient la grille a l'identique,
    survit au repli ASCII, et se mesure.

    L'ensemble mesure est EXACT : exactement une option est en majuscules.
    « oui est en majuscules » laisserait passer les deux qui le seraient.
    """
    ecran = _ecran_pret(tmp_path)

    async def scenario(pilote):
        rendu = {}
        for pris in (False, True):
            ecran.formulaire.devient_le_defaut = pris
            rendu[pris] = ecran.ligne_du_choix()
        return rendu

    rendu = banc(_app(ecran, ascii_seul), scenario)

    non_retenu = rendu[False]
    assert calib.CHOIX_NON.upper() in non_retenu
    assert calib.CHOIX_OUI.upper() not in non_retenu
    assert calib.CHOIX_OUI in non_retenu

    oui_retenu = rendu[True]
    assert calib.CHOIX_OUI.upper() in oui_retenu
    assert calib.CHOIX_NON.upper() not in oui_retenu
    assert calib.CHOIX_NON in oui_retenu


# --- point 3 : l'aide du pied, SEULEMENT sur ce champ ----------------------


def test_le_pied_porte_Espace_Oui_non_SEULEMENT_sur_le_champ_du_choix(
    tmp_path: Path
) -> None:
    """Point 3 : « quand le curseur est sur ce champ », et nulle part ailleurs.

    L'ensemble des champs dont le pied porte la mention est mesure EXACTEMENT.
    Une assertion « sur le champ du choix, la mention est la » serait verte sur
    un pied qui la porterait partout -- c'est-a-dire sur le defaut inverse, et
    celui-la est pire : une ligne de raccourcis qui ment.
    """
    ecran = _ecran_pret(tmp_path)
    assert _pieds_apres_une_touche(ecran, calib.RACCOURCI_ESPACE) == {
        calib.CHAMP_DEFAUT}


def test_le_pied_annonce_le_geste_de_CHAQUE_champ_et_jamais_une_touche_inerte(
    tmp_path: Path
) -> None:
    """Le corollaire, et il est la regle du depot plutot qu'un ajout.

    « Une touche annoncee qui ne fait rien et ne dit rien est indistinguable
    d'un clavier casse. » Le volet symetrique se mesure ici : le pied n'annonce
    `⏎` que sur les champs ou `⏎` fait quelque chose.
    """
    ecran = _ecran_pret(tmp_path)
    assert _pieds_apres_une_touche(ecran, "⏎") == {
        calib.CHAMP_SCAN, calib.CHAMP_REPRISE, calib.CHAMP_VALIDER}


# --- point 4 : un « Valider » explicite en bas -----------------------------


def test_VALIDER_est_la_DERNIERE_ligne_et_seule_ELLE_lance_la_passe(
    tmp_path: Path, banc
) -> None:
    """Point 4 : « un choix explicite en bas du formulaire : Valider ».

    Deux moities, et la seconde est celle qui repond au grief d'Egan (« la
    validation avec Entree n'est pas claire ») : `⏎` sur les autres champs ne
    lance PLUS la calibration. L'ensemble des champs qui lancent est mesure
    exactement.
    """
    lances = []
    ecran = _ecran_pret(tmp_path)
    ecran._calibrer = lambda formulaire: lances.append(formulaire.champ)
    ecran.formulaire.dpi = "300"

    assert ecran.formulaire.champs()[-1] == calib.CHAMP_VALIDER

    async def scenario(pilote):
        qui_lance = set()
        for cle in ecran.formulaire.champs():
            # **La zone est REMISE a chaque tour**, et l'oublier rendait ce
            # test vert pour la mauvaise raison : `⏎` sur le champ du scan
            # ouvre l'explorateur, et toutes les touches suivantes partaient
            # alors dans CETTE zone -- aucune n'atteignait plus le formulaire.
            # Un banc qui n'aurait essaye que la ligne `Valider` n'aurait
            # jamais vu le piege.
            ecran.zone = calib.ZONE_FORMULAIRE
            ecran.formulaire.champ = cle
            avant = len(lances)
            ecran.traiter("enter")
            if len(lances) > avant:
                qui_lance.add(cle)
        return qui_lance

    assert banc(_app(ecran), scenario) == {calib.CHAMP_VALIDER}


def test_on_ATTEINT_Valider_en_DESCENDANT_depuis_le_premier_champ(
    tmp_path: Path
) -> None:
    """« On y accede en descendant avec les fleches » -- litteralement.

    Mesure du GESTE et non de la structure : `champs()[-1]` dit ou la ligne est
    dans la liste, pas qu'on l'atteint. Six `↓` depuis le premier champ doivent
    y mener.
    """
    ecran = _ecran_pret(tmp_path)
    ecran.formulaire.champ = ecran.formulaire.champs()[0]
    for _ in range(len(ecran.formulaire.champs()) - 1):
        ecran.traiter("down")
    assert ecran.formulaire.champ == calib.CHAMP_VALIDER


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_formulaire_tient_le_plancher_80x24_avec_sa_ligne_de_plus(
    tmp_path: Path, ascii_seul: bool, banc
) -> None:
    """La ligne `Valider` est une ligne DE PLUS : la grille doit tenir.

    C'est la contrainte que le brief rappelle, et le seul moyen de la mesurer
    est de rendre l'ecran entier a la taille plancher, dans les deux regimes.
    """
    ecran = _ecran_pret(tmp_path)
    ecran.formulaire.champ = calib.CHAMP_VALIDER

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return ecran.lignes()

    lignes = banc(_app(ecran, ascii_seul), scenario)
    utile = 80 - 4
    for ligne in lignes:
        assert jetons.colonnes(jetons.ajuster(ligne, utile, ascii_seul)) <= utile
    assert len(lignes) <= 24 - 4, len(lignes)


# --- la verification que le brief exige : Espace n'est pris nulle part ------


def test_ESPACE_n_est_PAS_pris_par_l_explorateur_de_CET_ecran(
    tmp_path: Path
) -> None:
    """« Si `Espace` est deja pris ailleurs, dis-le plutot que de creer une
    exception muette » -- verifie dans les DEUX sens.

    Volet positif : l'explorateur du DEPOT, lui, prend bien `Espace` (il coche).
    Sans ce volet, le test serait vert sur un produit qui aurait perdu la coche
    partout -- et il ne mesurerait alors plus rien du tout.
    """
    du_scan = calib.EcranCalibrerLaChaine(
        tmp_path, calibrer=lambda _f: None).explorateur
    assert du_scan.selection_multiple is False
    assert "Espace" not in ecran_projet.raccourcis_de_l_explorateur(du_scan)

    cocheur = explorateur.Explorateur(tmp_path, montrer_fichiers=True,
                                      selection_multiple=True)
    assert "Espace" in ecran_projet.raccourcis_de_l_explorateur(cocheur)


# ===========================================================================
# Les maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E3-1` et `E3-9` des sa
# docstring de module et n'ouvrait aucun dessin : le pied de son palier temoin
# en etait recopie a la main. Un double dont le pied n'est pas celui du dessin
# mesure un ecran que personne n'a approuve.

#: Les dessins repris ici, a leur source.
MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

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


def test_le_PIED_du_palier_temoin_est_celui_du_menu_des_ATELIERS():
    """`Q quitter` vient de `E1-1`, le palier que le temoin DOUBLE.

    Trois dessins, trois reponses distinctes -- si les trois repondaient
    pareil, la mesure serait muette :

    * `E1-1`, le menu des ateliers, le dessine : c'est la source du pied que
      `PalierTemoin("Ateliers", ...)` rejoue ;
    * `E3-1` le dessine aussi. L'y trouver ne dit rien de la filiation : c'est
      un autre ecran qui porte le meme pied ;
    * `E3-9` -- l'ecran que CE banc monte -- ne le dessine pas : son pied
      s'arrete a `Échap menu Scan`, sans sortie directe. Le palier porte la
      sortie, l'ecran pose dessus ne l'herite pas.
    """
    ateliers = dessin_de_la_maquette("E1-1-menu-ateliers.txt")
    depot = dessin_de_la_maquette("E3-1-scan-depot.txt")
    formulaire = dessin_de_la_maquette("E3-9-scan-calibrate.txt")
    assert PIED_DU_PALIER in ateliers
    assert PIED_DU_PALIER in depot
    assert PIED_DU_PALIER not in formulaire


def test_les_DEUX_explorateurs_different_par_ce_que_leur_pied_DESSINE():
    """`E3-1` offre `↑↓ sources`, `E3-9` non -- c'est la difference dessinee.

    Ce banc mesure que l'explorateur du depot coche (`selection_multiple`) et
    que celui de la calibration ne coche pas. Le dessin ne montre pas
    `Espace`, mais il montre le symptome de la meme difference : le depot
    navigue entre PLUSIEURS sources, la calibration n'en designe qu'une.
    """
    depot = dessin_de_la_maquette("E3-1-scan-depot.txt")
    formulaire = dessin_de_la_maquette("E3-9-scan-calibrate.txt")
    assert "↑↓ sources" in depot
    assert "↑↓ sources" not in formulaire


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative, et elle NOMME une limite plutot que de la taire.

    `Espace` -- la touche que ce banc mesure d'un bout a l'autre -- n'est
    dessinee dans AUCUN des trois : le pied de l'explorateur est un survol,
    pas un etat approuve. Ce que ce banc tient de `Espace`, il le tient du
    code et non d'une maquette, et l'ecrire ici evite qu'une relecture croie
    le contraire.
    """
    ateliers = dessin_de_la_maquette("E1-1-menu-ateliers.txt")
    depot = dessin_de_la_maquette("E3-1-scan-depot.txt")
    formulaire = dessin_de_la_maquette("E3-9-scan-calibrate.txt")
    assert PIED_DU_PALIER + " et revenir" not in ateliers
    assert "Q fermer" not in ateliers
    for dessin in (ateliers, depot, formulaire):
        assert "Espace" not in dessin
