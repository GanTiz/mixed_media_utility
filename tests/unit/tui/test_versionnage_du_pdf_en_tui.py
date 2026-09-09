# -*- coding: utf-8 -*-
"""Story 11.7, lot G -- `E5-3b` / `E5-3c`, le conflit de tirage (AC 7).

**Ce banc et lui seul mesure le lot G.** La regle de decoupage de la fiche est
stricte et le depot l'a payee : `git add -N` et `git commit -- <chemins>`
protegent par FICHIER, jamais a l'interieur d'un fichier, et le commit `82e64de`
du 2026-08-30 a embarque ~200 lignes du lot voisin sous un message qui parlait
d'autre chose alors que les deux agents appliquaient la regle a la lettre.

**Regle des fabriques** (`CLAUDE.md`), a ses quatre points, et il y a **deux**
listes que le code parcourt :

1. la file des conflits (`PasseDeConflits.conflits`), parcourue par
   `ordonner_par_lot` -- **cinq conflits**, la cible scannee **au milieu** (rang
   2 sur 0..4). Une cible en tete laisse vivre un `conflits[0]`, une cible en
   queue laisse vivre un `continue` -> `break` ;
2. les **restants** (`PasseDeConflits.restants`), parcourus par
   `emport_de_la_masse` -- la cible scannee y est au **milieu** aussi, ce qui est
   verifie explicitement plutot que suppose : les deux listes different d'un
   element, et une position juste sur la premiere peut etre fausse sur la
   seconde ;
3. **des valeurs distinguables** : cinq identifiants de lot differents, cinq
   poids differents, deux rangs differents. Un remplissage uniforme rendrait
   toute permutation invisible -- et le poids de la masse, somme de trois valeurs
   distinctes, ne peut alors pas tomber juste par accident ;
4. **la position se verifie sur la liste que le CODE parcourt**, et non sur
   l'ordre dans lequel la fabrique ecrit ses lots : l'ordre du produit est celui
   d'`ordonner_par_lot`, qui n'est PAS celui de la fabrique. C'est precisement ce
   qui permet de mesurer l'ordre « par lot » comme un ordre **choisi**.

**Rien n'est tape a la main de ce que le produit sait construire** : le nom du
tirage sort de `io.naming.build_sheets_pdf_filename`, le texte du refus de rangs
epuises de `io.version_ranks.refus_de_rangs_epuises`, la borne des rangs de
`io.naming.VERSION_RANK_MAX`, l'origine de `io.version_ranks.RANG_ORIGINE`. Une
valeur recopiee coinciderait le jour ou elle est ecrite et divergerait sans
qu'aucune etape n'echoue.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import pdf_composition
from mixed_media_utility.io import naming, pdf_manifest, scan_manifest, version_ranks
from mixed_media_utility.tui import atelier_pdf_versions as versions
from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.panneau import ChoixExclusif

from outils_frontiere import identifiants

#: Les deux regimes, portes par tout test qui touche au rendu. « Ne jamais
#: ajuster un test au code : tout test parametre porte les deux regimes. »
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le plancher d'`EPIC11-ARB-21`, et la zone ecrivable qui s'en deduit.
PLANCHER = (80, 24)
UTILE = jetons.largeur_utile(PLANCHER[0])
HAUTEUR_DU_CENTRE = jetons.HAUTEUR_CENTRE_AU_PLANCHER

#: Le projet des maquettes -- confronter le rendu au dessin sans rien inventer.
PROJET = "projet_demo"

#: Les cinq lots de la passe, **dans l'ordre de la fabrique**. Il n'est pas
#: l'ordre alphabetique : c'est ce qui rend l'ordre « par lot » mesurable comme
#: un choix. Le lot **scanne** est `plan-04_08`, au milieu des cinq une fois
#: triees, et deja au milieu de la fabrique -- les deux positions sont
#: verifiees, l'une n'impliquant pas l'autre.
LOTS_DE_LA_FABRIQUE = ("plan-09_25", "plan-02_12p5", "plan-04_08",
                       "plan-07_02", "plan-01_16")

#: Le lot **scanne** de la passe. Il est au milieu de la liste triee comme de la
#: liste de fabrique : c'est ce que la regle des fabriques exige des qu'une
#: boucle compte, et l'issue de masse compte.
LOT_SCANNE = "plan-04_08"

#: Le lot que l'ecran juge en premier -- le **premier de l'ordre par lot**, qui
#: n'est pas le premier de la fabrique.
LOT_COURANT = "plan-01_16"

#: Cinq poids differents, en megaoctets. Leur somme partielle ne peut pas tomber
#: juste par accident : un remplissage uniforme rendrait indiscernables « la
#: masse a saute le scanne » et « la masse a tout emporte ».
POIDS = {"plan-01_16": 111, "plan-02_12p5": 222, "plan-04_08": 444,
         "plan-07_02": 777, "plan-09_25": 999}

#: Le rang du tirage present, et celui que le coeur propose. Les deux sont
#: **donnes** : la TUI ne calcule aucun rang (`EPIC11-ARB-92`).
RANG_PRESENT = 3
RANG_PROPOSE = 4

#: Le rush des lots de la fabrique. Un seul suffit : ce banc mesure des rangs de
#: TIRAGE, qui sont un fait du lot (`EPIC11-ARB-175`).
RUSH = "plan-04"

#: Le gabarit du lot montre par les maquettes.
GABARIT = "tpl-a4-paysage-6f-v2"

#: Les trois mesures que `E5-3b` et `E5-3c` DESSINENT sur le tirage present.
#: Elles etaient tapees en clair dans deux fabriques, donc recopiees deux fois
#: du meme dessin sans que rien ne le dise. Nommees ici une fois, elles sont
#: confrontees a leur source en fin de fichier -- une valeur recopiee coincide
#: le jour ou elle est ecrite et derive ensuite sans qu'aucune etape n'echoue.
PAGES_DESSINEES = 21
POIDS_DESSINE_MO = 352
QUAND_DESSINE = "26/08 à 16:22"
QUAND_COURT_DESSINE = "26/08"


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def _tirage(lot_id: str, *, scanne: bool = False,
            rang_propose: int = RANG_PROPOSE) -> versions.TirageEnConflit:
    """Un conflit distinguable de tous les autres : lot, poids, etat de scan."""
    return versions.TirageEnConflit(
        nom=naming.build_sheets_pdf_filename(PROJET, RUSH, lot_id,
                                             RANG_PRESENT,
                                             template_id=GABARIT),
        lot_id=lot_id,
        rang=RANG_PRESENT,
        rang_propose=rang_propose,
        pages=PAGES_DESSINEES,
        frames=124,
        poids_mo=POIDS[lot_id],
        quand=QUAND_DESSINE,
        quand_court=QUAND_COURT_DESSINE,
        mise_en_page=versions.mise_en_page_du_gabarit(GABARIT),
        scanne=scanne,
        quand_scanne="27/08" if scanne else None,
    )


def _passe(courant: str = LOT_COURANT) -> versions.PasseDeConflits:
    """Les cinq conflits, **dans l'ordre du produit**, celui d'`ordonner_par_lot`.

    La fabrique les ecrit dans un autre ordre a dessein : un banc qui les
    ecrirait deja tries ne verrait pas la difference entre « le produit trie » et
    « le produit rend ce qu'on lui donne ».
    """
    conflits = versions.ordonner_par_lot(
        _tirage(lot_id, scanne=(lot_id == LOT_SCANNE))
        for lot_id in LOTS_DE_LA_FABRIQUE)
    rang = [conflit.lot_id for conflit in conflits].index(courant)
    return versions.PasseDeConflits(conflits=conflits, rang_courant=rang)


def _app(ecran, **kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                    contexte=Contexte(projet=PROJET), **kwargs)


def _ecran(passe: versions.PasseDeConflits | None = None,
           retenues: list | None = None) -> versions.EcranConflitDeTirage:
    return versions.EcranConflitDeTirage(
        passe if passe is not None else _passe(),
        retenir=(retenues.append if retenues is not None else (lambda _: None)))


def _texte(widget) -> str:
    """Le texte **tel qu'il s'affiche**, balises de couleur retirees."""
    return jetons.texte_affiche(str(widget.content))


def _rendu(ecran, banc, app=None, avant=None) -> tuple[str, str]:
    """`(cartouche, issues)` tels que l'ecran monte les rend.

    `avant` joue les frappes **pendant** que l'ecran est monte : une assertion
    posee apres la fermeture du gestionnaire de contexte ne mesurerait rien,
    l'arbre de widgets n'existant plus.
    """
    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        if avant is not None:
            avant(ecran)
            ecran.rafraichir()
        return _texte(ecran._cartouche), _texte(ecran._issues)

    return banc(app or _app(ecran), scenario)


def _sans_retours(texte: str) -> str:
    """Le texte, blancs replies -- pour confronter a une phrase d'Egan.

    `jetons.envelopper` coupe la mention sur plusieurs lignes : la comparer
    telle quelle ferait rougir une mise en forme correcte. Ce qui doit etre
    mesure est que **rien n'a ete reformule**, pas que rien n'a ete replie -- le
    repli est precisement le travail de l'ecran.
    """
    return " ".join(texte.split())


# ===========================================================================
# G1 -- `E5-3b` : trois issues, et DEUX positions du curseur assertees
# ===========================================================================

def test_G1_l_ensemble_des_issues_de_E5_3b_est_EXACT():
    """AC 7.1 + `EPIC11-ARB-177` : quatre issues, et **exactement** celles-la.

    « Au moins celles-la » ne mesurerait rien : une issue destructive de plus,
    ajoutee par distraction, passerait. L'ensemble est donc compare a l'egalite,
    et l'ordre est mesure a part -- la masse est **apres** l'unitaire
    (contrainte 1 d'`EPIC11-ARB-177`).
    """
    passe = _passe()
    choix = versions.choix_du_conflit(passe)
    assert [issue.cle for issue in choix.issues] == [
        versions.CLE_CREER, versions.CLE_REMPLACER, versions.CLE_MASSE,
        versions.CLE_ANNULER]
    assert {issue.cle for issue in choix.issues if issue.ecrit} == {
        versions.CLE_REMPLACER, versions.CLE_MASSE}


def test_G1_le_curseur_AU_MONTAGE_vise_Creer_la_vN():
    """AC 7.2a -- la position est **nommee**, jamais relue du composant.

    « C'est une assertion du banc, jamais un effet de bord observe : le test
    nomme la position attendue plutot que de relire ce que le composant a fait. »
    L'assertion porte donc sur la CLE de l'issue visee, et le rang n'y sert que
    de second temoin.
    """
    choix = versions.choix_du_conflit(_passe())
    assert choix.issues[choix.curseur].cle == versions.CLE_CREER
    assert choix.curseur == 0
    assert not choix.issues[choix.curseur].ecrit


def test_G1_le_curseur_au_montage_n_est_JAMAIS_une_issue_qui_ecrit():
    """`EPIC11-ARB-7`, sur les **deux** etats de l'ecran.

    Le volet symetrique est la seconde boucle : l'invariant serait vert sur un
    ecran dont aucune issue n'ecrit, c'est-a-dire sans rien mesurer. On verifie
    donc qu'il y a bien une issue qui ecrit dans l'etat ecrasable.
    """
    for courant, ecrivantes in ((LOT_COURANT, 2), (LOT_SCANNE, 1)):
        choix = versions.choix_du_conflit(_passe(courant))
        assert not choix.issues[choix.curseur].ecrit, courant
        assert len([i for i in choix.issues if i.ecrit]) == ecrivantes - 1 or (
            courant == LOT_COURANT)
    ecrasable = versions.choix_du_conflit(_passe(LOT_COURANT))
    assert ecrasable.action_qui_ecrit is not None


def test_G1_l_invariant_du_curseur_est_APPELE_et_non_reecrit():
    """`ChoixExclusif.__post_init__` est le seul a placer le curseur.

    Le mesurer plutot que de le croire : on donne au composant une liste dont la
    premiere issue ecrit, et l'on verifie qu'il deplace -- si le module du lot G
    posait son propre curseur, cette propriete-la vivrait a deux endroits.
    """
    temoin = ChoixExclusif(versions.issues_des_rangs_epuises(
        _tirage(LOT_COURANT)))
    assert temoin.issues[0].ecrit
    assert temoin.curseur != 0
    assert not temoin.issues[temoin.curseur].ecrit


@pytest.mark.parametrize("ascii_seul", MODES)
def test_G1_apres_deplacement_l_ecran_rend_ce_que_E5_3b_DESSINE(banc,
                                                                ascii_seul):
    """AC 7.2b -- **le second instant**, celui que la maquette montre.

    Egan demande l'avertissement « au moment du choix de l'ecrasement » : c'est
    cet instant-la que `E5-3b` dessine, curseur sur `Remplacer ce tirage`. Les
    deux assertions -- montage et deplacement -- sont independantes ; ni l'une ni
    l'autre ne suppose l'autre.
    """
    ecran = _ecran()
    cartouche, issues = _rendu(
        ecran, banc, app=_app(ecran, ascii_seul=ascii_seul),
        avant=lambda ecr: ecr.traiter("down"))

    assert ecran.choix.issues[ecran.choix.curseur].cle == versions.CLE_REMPLACER
    table = jetons.glyphes(ascii_seul)
    lignes = issues.splitlines()
    assert issues.count(table["curseur"]) == 1, issues
    ligne = lignes[ecran.rang_du_curseur()]
    attendu = (jetons.replier_ascii(versions.LIBELLE_REMPLACER) if ascii_seul
               else versions.LIBELLE_REMPLACER)
    assert table["curseur"] in ligne and attendu in ligne, (ligne, lignes)
    # Le cartouche est bien celui du tirage ecrasable, mention comprise.
    assert _sans_retours(cartouche).endswith(_sans_retours(
        jetons.replier_ascii(versions.MENTION_DE_L_ECRASEMENT) if ascii_seul
        else versions.MENTION_DE_L_ECRASEMENT))


def test_G1_deplacer_le_curseur_ne_RETIENT_rien():
    """`EPIC11-ARB-7` : parcourir n'est pas choisir.

    Un curseur qui retiendrait au passage ferait de la derniere issue survolee
    une preselection -- exactement ce que l'arbitrage ferme.
    """
    retenues: list = []
    ecran = _ecran(retenues=retenues)
    ecran.traiter("down")
    ecran.traiter("down")
    assert retenues == []
    ecran.traiter("enter")
    assert [issue.cle for issue in retenues] == [versions.CLE_MASSE]


# ===========================================================================
# G2 -- les deux phrases d'Egan, mesurees MOT POUR MOT
# ===========================================================================

#: La mention de `E5-3b`, **retapee ici a partir du verbatim d'Egan** du
#: 2026-09-02 : « On y ajoute la mention "Si cette page a déjà été imprimée,
#: n'écrasez pas cette planche sous peine de générer des conflits de version" ».
#: La recopie est ici **volontaire et c'est tout l'objet du test** : comparer la
#: constante du produit a elle-meme ne mesurerait rien.
VERBATIM_DE_L_ECRASEMENT = ("Si cette page a déjà été imprimée, n'écrasez pas "
                            "cette planche sous peine de générer des conflits "
                            "de version")

#: La reecriture du soir, **retapee du verbatim d'Egan** : « ce tirage a deja
#: ete imprime. Vous ne pouvez pas l'ecraser car cela pourrait causer des
#: conflits de version. » Les accents sont poses et la premiere lettre passe en
#: majuscule -- les deux ecarts sont nommes dans le module, et le test mesure la
#: suite des **mots**, qui est ce que « mot pour mot » designe.
VERBATIM_DU_TIRAGE_SCANNE = ("Ce tirage a déjà été imprimé. Vous ne pouvez pas "
                             "l'écraser car cela pourrait causer des conflits "
                             "de version.")


def test_G2_la_mention_de_E5_3b_est_le_verbatim_d_Egan_MOT_POUR_MOT():
    """AC 7.10 -- **verbatim**, jamais par mots-cles.

    « C'est une phrase qu'Egan a redigee, et une paraphrase serait le defaut que
    le pare-arbitrage du depot existe pour empecher. »
    """
    assert versions.MENTION_DE_L_ECRASEMENT == VERBATIM_DE_L_ECRASEMENT


def test_G2_la_mention_de_E5_3c_est_la_REECRITURE_du_2026_09_02():
    """Retour d'Egan du soir : le message de `E5-3c` etait trop long.

    Deux phrases contre quatre lignes de cartouche. Le test mesure la suite des
    mots a l'egalite -- une reformulation « equivalente » passerait un test par
    mots-cles et serait exactement ce qui est refuse.
    """
    assert versions.MENTION_DU_TIRAGE_SCANNE == VERBATIM_DU_TIRAGE_SCANNE
    assert versions.MENTION_DU_TIRAGE_SCANNE.split() == (
        VERBATIM_DU_TIRAGE_SCANNE.split())


def test_G2_le_MECANISME_a_disparu_de_l_ecran___frontiere_negative():
    """Le mecanisme vit dans les documents de decision, **pas a l'ecran**.

    Verbatim d'Egan : « le mecanisme n'est pas la raison qu'un operateur a
    besoin de lire ». La redaction retiree expliquait le QR, le rang grave et
    « deux choses au meme numero » ; aucun de ces mots ne doit revenir dans un
    texte affiche par ce module.

    **Volet symetrique** : les mots cherches existent bien -- ils sont dans le
    document de decision --, sans quoi la frontiere serait verte parce que son
    vocabulaire ne designe plus rien.
    """
    interdits = ("QR", "son rang dans", "deux choses au même numéro")
    affiches = "\n".join((
        versions.MENTION_DU_TIRAGE_SCANNE, versions.MENTION_DE_L_ECRASEMENT,
        versions.TITRE_DU_CONFLIT, versions.TITRE_DU_CONFLIT_SCANNE,
        versions.GLOSE_DU_SCAN, versions.GLOSE_SANS_SCAN,
        versions.ETAT_DU_TIRAGE_SCANNE, versions.ETAT_DU_TIRAGE_SCANNE_DATE,
    ))
    for mot in interdits:
        assert mot not in affiches, (mot, affiches)

    decision = (Path(__file__).resolve().parents[3] / "_bmad-output"
                / "implementation-artifacts"
                / "decisions-2026-09-02-epic11-arb-176-scan-au-rang.md")
    assert decision.is_file(), decision
    assert "QR" in decision.read_text(encoding="utf-8")


@pytest.mark.parametrize("ascii_seul", MODES)
def test_G2_la_mention_est_repliee_par_la_largeur_et_JAMAIS_abregee(banc,
                                                                    ascii_seul):
    """Le repli coupe entre les mots ; il n'abrege pas.

    Une mention passee par `jetons.abreger_nom` porterait une ellipse, donc
    perdrait des mots -- ce qui est le contraire de « mot pour mot ». On mesure
    donc que le texte affiche, blancs replies, **contient** la phrase entiere.
    """
    ecran = _ecran(_passe(LOT_SCANNE))
    cartouche, _ = _rendu(ecran, banc, app=_app(ecran, ascii_seul=ascii_seul))
    attendue = (jetons.replier_ascii(versions.MENTION_DU_TIRAGE_SCANNE)
                if ascii_seul else versions.MENTION_DU_TIRAGE_SCANNE)
    assert _sans_retours(attendue) in _sans_retours(cartouche)
    assert jetons.ELLIPSE not in cartouche
    assert "..." not in cartouche


# ===========================================================================
# G3 -- `E5-3c` : deux issues, et l'ecrasement n'est PAS offert
# ===========================================================================

def test_G3_l_ensemble_des_issues_de_E5_3c_est_EXACT():
    """AC 7.9c -- `{créer la vN, appliquer aux N restants, annuler}`.

    **L'AC en annonce deux ; il y en a trois, et l'ecart est assume** :
    `EPIC11-ARB-177` a ajoute l'issue de masse aux DEUX etats de l'ecran apres la
    redaction de l'AC, et la maquette validee la dessine. L'ensemble reste exact,
    et sa propriete dure -- aucune issue destructive -- est mesuree juste apres.
    """
    choix = versions.choix_du_conflit(_passe(LOT_SCANNE))
    assert [issue.cle for issue in choix.issues] == [
        versions.CLE_CREER, versions.CLE_MASSE, versions.CLE_ANNULER]


def test_G3_l_ecrasement_n_est_PAS_offert_sur_un_tirage_scanne():
    """Frontiere **negative** de l'AC 7.9a, avec son volet symetrique.

    `EPIC11-ARB-174`, verbatim d'Egan : « **S'il est scanné on ne peut de fait
    pas l'écraser.** » Le volet symetrique est la seconde assertion : la meme
    fabrique, le meme code, un tirage NON scanne -- et l'issue reapparait. Sans
    lui, la frontiere serait verte le jour ou `LIBELLE_REMPLACER` change de nom.
    """
    scanne = versions.choix_du_conflit(_passe(LOT_SCANNE))
    assert versions.CLE_REMPLACER not in {i.cle for i in scanne.issues}
    assert versions.LIBELLE_REMPLACER not in "\n".join(
        i.libelle for i in scanne.issues)
    assert not any(issue.ecrit for issue in scanne.issues)

    ecrasable = versions.choix_du_conflit(_passe(LOT_COURANT))
    assert versions.CLE_REMPLACER in {i.cle for i in ecrasable.issues}


def test_G3_deux_issues_au_moins_restent___jamais_un_blocage_sec():
    """`EPIC11-ARB-89` / `-104` : l'objet reste **versionnable**.

    « Jamais une, toujours au moins deux, et jamais zero. » Sur un tirage scanne
    ce sont `Créer la vN` et `Annuler` ; c'est l'ecrasement seul qui tombe, pas
    la possibilite d'agir.
    """
    for courant in (LOT_COURANT, LOT_SCANNE):
        choix = versions.choix_du_conflit(_passe(courant))
        assert len(choix.issues) >= 2, courant
        assert choix.sortie_sans_ecriture is not None, courant
    # Un conflit UNIQUE -- la masse tombe -- garde ses deux issues.
    seul = versions.PasseDeConflits(conflits=(_tirage(LOT_SCANNE, scanne=True),))
    assert [i.cle for i in versions.choix_du_conflit(seul).issues] == [
        versions.CLE_CREER, versions.CLE_ANNULER]


@pytest.mark.parametrize("ascii_seul", MODES)
def test_G3_la_ligne_d_etat_de_E5_3c_est_un_INTERDIT_en_croix(banc, ascii_seul):
    """AC 7.9d : `✕`, pas `▲` -- c'est un interdit, pas une reserve.

    Et `EPIC11-ARB-56` : la ligne ne porte aucune touche, aucun conseil d'usage,
    aucun motif de conception. Elle nomme ce qui n'est pas offert et pourquoi,
    tous deux **constatables**.
    """
    ecran = _ecran(_passe(LOT_SCANNE))
    table = jetons.glyphes(ascii_seul)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return _texte(ecran.query_one("#etat"))

    etat = banc(_app(ecran, ascii_seul=ascii_seul), scenario)
    assert etat.startswith(table["absent"]), etat
    assert table["substitute"] not in etat, etat
    assert "27/08" in etat
    for interdit in ("⏎", "Échap", "touche", "appuyez", "parce que"):
        assert interdit not in etat, (interdit, etat)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_G3_la_ligne_d_etat_de_E5_3b_est_une_RESERVE_chiffree(banc, ascii_seul):
    """L'autre etat : `▲`, et **des mesures** -- pages, poids, date.

    Le volet qui compte : elle dit `ce tirage n'est pas scanné`, ce qui est le
    fait qui autorise l'ecrasement, et elle ne le dit pas du LOT.
    """
    ecran = _ecran()

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return _texte(ecran.query_one("#etat"))

    etat = banc(_app(ecran, ascii_seul=ascii_seul), scenario)
    table = jetons.glyphes(ascii_seul)
    assert etat.startswith(table["substitute"]), etat
    assert str(POIDS[LOT_COURANT]) in etat and "26/08" in etat
    assert "tirage" in etat and " lot " not in etat, etat


# ===========================================================================
# G4 -- « scanne » se deduit AU RANG, jamais de l'etat du LOT
# ===========================================================================

def _lot_du_manifeste(lot_id: str, rangs_scannes=None) -> dict:
    lot = {"lot_id": lot_id, "rush_id": RUSH, "template_id": GABARIT,
           "state": scan_manifest.SCAN_LOT_STATE}
    if rangs_scannes is not None:
        lot[scan_manifest.SCANNED_VERSION_RANKS_FIELD] = list(rangs_scannes)
    return lot


def test_G4_un_lot_scanne_au_v1_ne_rend_pas_son_v3_INECRASABLE():
    """`EPIC11-ARB-176`, et c'est le defaut exact que l'arbitrage ferme.

    « Applique tel quel, l'interdit refuserait d'ecraser un `v4` jamais imprime
    au seul motif que le `v3` du meme lot a ete scanne -- c'est-a-dire un blocage
    sec sur un objet innocent, exactement ce qu'`EPIC11-ARB-89` interdit. »

    Le lot porte l'etat de scan **et** un rang scanne qui n'est pas celui du
    tirage juge : le produit doit lire le rang, pas l'etat.
    """
    lot = _lot_du_manifeste(LOT_COURANT, [1])
    assert lot["state"] == scan_manifest.SCAN_LOT_STATE
    entree = {pdf_manifest.SHEETS_INVENTORY_KEY: f"pdf/{LOT_COURANT}_v3.pdf",
              "version_rank": RANG_PRESENT}
    conflit = versions.conflit_du_tirage(None, lot, entree, rang=RANG_PRESENT,
                                         rang_propose=RANG_PROPOSE)
    assert conflit.scanne is False
    assert conflit.ecrasable is True

    # Le meme lot, le meme etat, mais le rang du tirage juge est cite : l'interdit
    # tombe. Sans ce second volet la premiere assertion serait verte sur un
    # produit qui ne lit rien du tout.
    cite = versions.conflit_du_tirage(
        None, _lot_du_manifeste(LOT_COURANT, [1, RANG_PRESENT]), entree,
        rang=RANG_PRESENT, rang_propose=RANG_PROPOSE)
    assert cite.scanne is True and cite.ecrasable is False


def test_G4_la_cle_ABSENTE_ne_vaut_pas_le_rang_1_scanne():
    """AC 7.11c -- le repli est **asserte**, jamais implicite.

    « Le manifeste ne porte pas la cle » veut dire « **on ne sait pas** quel
    tirage a ete scanne », jamais « le rang 1 l'a ete ». Un manifeste ecrit avant
    `EPIC11-ARB-176` ne rend donc aucun rang, et le tirage d'origine y reste
    ecrasable -- avec l'avertissement d'Egan sous les yeux, ce qu'il a tranche :
    « On fait confiance a l'operateur.ice. »

    Les trois formes qui ne sont pas une liste de rangs sont mesurees ensemble :
    absente, mal typee, et porteuse de valeurs qui n'en sont pas.
    """
    for lot in (_lot_du_manifeste(LOT_COURANT),
                {"lot_id": LOT_COURANT,
                 scan_manifest.SCANNED_VERSION_RANKS_FIELD: "1"},
                {"lot_id": LOT_COURANT,
                 scan_manifest.SCANNED_VERSION_RANKS_FIELD: [None, True, "3"]}):
        assert versions.rangs_scannes(lot) == frozenset(), lot
    assert versions.rangs_scannes(
        _lot_du_manifeste(LOT_COURANT, [1, 3])) == frozenset({1, 3})


def test_G4_le_lecteur_de_rang_du_payload_a_AU_MOINS_UN_site_d_appel():
    """`EPIC11-ARB-176` : le chainon manquant est **ecrit**, et il est branche.

    Mesure du 2026-09-02, avant la story : `payload_version_rank` n'avait
    **aucun** site d'appel dans `src/` en dehors de sa propre definition -- le
    rang traversait l'impression, le papier et le decodage, et s'arretait juste
    avant d'etre ecrit au manifeste. La frontiere exige nommement
    `io/scan_manifest.py` : un appel interne au module qui DEFINIT la fonction
    suffirait sinon a la rendre verte.
    """
    coeur = Path(scan_manifest.__file__)
    appels = set()
    for noeud in ast.walk(ast.parse(coeur.read_text(encoding="utf-8"))):
        if isinstance(noeud, ast.Call):
            cible = noeud.func
            nom = (cible.attr if isinstance(cible, ast.Attribute)
                   else getattr(cible, "id", None))
            if nom:
                appels.add(nom)
    assert "payload_version_rank" in appels, sorted(appels)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_G4_le_GLYPHE_de_la_ligne_Scannee_distingue_les_deux_etats(ascii_seul):
    """Le second canal de `DESIGN.md` section 5 : la couleur est **doublee** par
    un glyphe, et les deux etats n'en portent pas le meme.

    `·` neutre au non -- « un tirage non scanne n'est ni un manque ni un refus,
    c'est le cas courant, et une ligne rouge sonnerait l'alarme sur le seul etat
    qui autorise l'ecrasement » -- et `▲` au oui. Un glyphe unique rendrait les
    deux etats indiscernables pour qui lit sans couleur, c'est-a-dire pour le
    regime que le repli ASCII sert.

    **Trouve par la campagne de mutation** (`M19`, survivant du premier tour) :
    aucun test ne regardait le glyphe de cette ligne, alors que c'est lui qui
    porte le fait que tout l'ecran raconte.
    """
    table = jetons.glyphes(ascii_seul)

    def _ligne_scannee(tirage) -> str:
        lignes = [ligne for ligne
                  in versions.lignes_du_cartouche(tirage, ascii_seul)
                  if ligne.startswith(versions.LIBELLE_DU_SCAN)]
        assert len(lignes) == 1, lignes
        return lignes[0]

    non = _ligne_scannee(_tirage(LOT_COURANT))
    oui = _ligne_scannee(_tirage(LOT_SCANNE, scanne=True))
    assert table["neutre"] in non and table["substitute"] not in non, non
    assert table["substitute"] in oui and table["neutre"] not in oui, oui
    assert table["absent"] not in oui, oui


def test_G4_la_glose_de_la_ligne_Scannee_porte_sur_le_TIRAGE_jamais_le_lot():
    """La redaction d'avant `EPIC11-ARB-176` disait « ce lot ». Elle est perimee.

    Le glose est le seul endroit de l'ecran ou la portee de la deduction se lit :
    « aucun scan ne cite ce **tirage** ». Un mot different y ferait dire a l'ecran
    l'inverse de ce que le produit mesure.
    """
    assert "tirage" in versions.GLOSE_SANS_SCAN
    assert "lot" not in versions.GLOSE_SANS_SCAN
    assert "tirage" in versions.GLOSE_DU_SCAN
    assert "lot" not in versions.GLOSE_DU_SCAN
    lignes = versions.lignes_du_cartouche(_tirage(LOT_COURANT))
    scannee = [ligne for ligne in lignes
               if ligne.startswith(versions.LIBELLE_DU_SCAN)]
    assert len(scannee) == 1, lignes
    assert versions.GLOSE_SANS_SCAN in scannee[0]


# ===========================================================================
# G5 -- le rang est AFFICHE, jamais calcule (frontiere AST)
# ===========================================================================

#: Le vocabulaire de coeur qui **calcule** un rang. Meme table que la frontiere
#: du lot C, rejouee sur le module du lot G : une frontiere posee sur le paquet
#: entier reste verte le jour ou l'on oublie d'y verser un module neuf, celle-ci
#: nomme sa cible.
CALCULS_DE_RANG = ("prochain_rang", "ligne_d_eau", "rangs_liberables",
                   "est_en_queue", "resolve_sheets_version_rank",
                   "sheets_version_watermark")


def test_G5_le_module_du_lot_G_ne_CALCULE_aucun_rang():
    """`EPIC11-ARB-92`, verbatim d'Egan : « **il ne faut pas rendre le rang** ».

    Le mode de panne que ca ferme est le pire du versionnage : deux feuilles de
    papier differentes portant le meme « tirage N ». Une fois l'encre seche,
    aucun fichier ne rattrape cela.

    **Volet symetrique** : le vocabulaire interdit existe bien au coeur, sans
    quoi cette frontiere serait verte pour la mauvaise raison.
    """
    module = Path(versions.__file__)
    vus = identifiants(module)
    assert not (vus & set(CALCULS_DE_RANG)), sorted(vus & set(CALCULS_DE_RANG))
    assert set(CALCULS_DE_RANG) & identifiants(Path(pdf_composition.__file__))


def test_G5_le_module_du_lot_G_n_importe_JAMAIS_cli():
    """Frontiere de la story 11.4b, rejouee sur le module neuf.

    Le volet symetrique est la seconde assertion : le module importe bien du
    coeur, donc la mesure regarde un fichier qui a des imports.
    """
    noms = identifiants(Path(versions.__file__))
    assert "cli" not in noms
    assert not any(nom.endswith(".cli") for nom in noms), sorted(noms)
    assert {"pdf_manifest", "scan_manifest"} <= noms, sorted(noms)


def test_G5_le_rang_affiche_est_celui_qu_on_a_DONNE():
    """L'ecran annonce `v4` parce qu'on lui a dit 4, pas parce qu'il a compte.

    Trois rangs proposes differents rendent trois libelles differents : un
    produit qui deriverait le rang du tirage present (3 -> 4) serait vert sur le
    seul cas ou les deux coincident, et cette fabrique le demasque.
    """
    for propose in (2, 7, 42):
        tirage = _tirage(LOT_COURANT, rang_propose=propose)
        passe = versions.PasseDeConflits(conflits=(tirage,))
        libelle = versions.choix_du_conflit(passe).issues[0].libelle
        assert libelle == f"Créer la v{propose}", libelle
    assert versions.ordinal_du_tirage(version_ranks.RANG_ORIGINE).startswith(
        f"{version_ranks.RANG_ORIGINE}er")


# ===========================================================================
# G6 -- afficher un rang ne le CONSOMME pas
# ===========================================================================

def test_G6_monter_l_ecran_puis_annuler_n_ECRIT_rien(tmp_path, banc):
    """AC 7.7 -- la ligne d'eau ne bouge pas, et **rien n'est ecrit**.

    La mesure ne se fait **pas par condensat** : « un condensat ne prouve pas
    qu'un fichier n'a pas ete touche quand la fixture est deterministe -- une
    reecriture rend exactement les memes octets ». Elle se fait aux **inodes**,
    au `st_mtime_ns`, et par un **temoin** depose dans le dossier vise.

    **Ce que ce test ne mesure pas, dit plutot que tu** : l'arbitrage E (« un
    affichage ne consomme pas un rang ») n'est pas tranche. Ce qui est mesure ici
    est plus etroit et ne depend d'aucune decision : ce module n'ecrit **nulle
    part**, donc il ne peut pas consommer quoi que ce soit.
    """
    projet = tmp_path / "projet"
    projet.mkdir()
    manifeste = projet / "project.json"
    lot = _lot_du_manifeste(LOT_COURANT, [1])
    lot["sheets_version_watermark"] = RANG_PRESENT
    manifeste.write_text(json.dumps({"lots": [lot]}), encoding="utf-8")
    temoin = projet / "temoin.txt"
    temoin.write_text("intact", encoding="utf-8")

    avant = {chemin: (chemin.stat().st_ino, chemin.stat().st_mtime_ns)
             for chemin in (manifeste, temoin)}
    avant_contenu = json.loads(manifeste.read_text(encoding="utf-8"))

    ecran = _ecran()
    _rendu(ecran, banc, avant=lambda ecr: ecr.traiter("down"))

    for chemin, empreinte in avant.items():
        assert (chemin.stat().st_ino, chemin.stat().st_mtime_ns) == empreinte, (
            chemin)
    apres = json.loads(manifeste.read_text(encoding="utf-8"))
    assert apres == avant_contenu
    assert apres["lots"][0]["sheets_version_watermark"] == RANG_PRESENT
    assert sorted(p.name for p in projet.iterdir()) == ["project.json",
                                                        "temoin.txt"]


# ===========================================================================
# G7 -- les rangs epuises : un refus qui NOMME ses issues
# ===========================================================================

def _refus_du_coeur(lot_id: str) -> str:
    """Le texte du coeur, **construit par le coeur** et jamais tape ici."""
    return version_ranks.refus_de_rangs_epuises(
        "planches", lot_id, "Deux issues: retirer le DERNIER tirage ou "
        "ecraser sciemment un tirage existant.")


@pytest.mark.parametrize("ascii_seul", MODES)
def test_G7_le_refus_du_coeur_est_affiche_TEL_QUEL(banc, ascii_seul):
    """AC 7.8 -- le texte du coeur voyage **verbatim**, l'ecran le relaie.

    Une seconde redaction cote TUI divergerait du coeur au premier ajustement, et
    c'est le coeur qui connait les bornes reelles.
    """
    refus = _refus_du_coeur(LOT_COURANT)
    ecran = versions.EcranRangsEpuises(_tirage(LOT_COURANT), refus,
                                       retenir=lambda issue: None)
    cartouche, _ = _rendu(ecran, banc, app=_app(ecran, ascii_seul=ascii_seul))
    attendu = jetons.replier_ascii(refus) if ascii_seul else refus
    assert _sans_retours(attendu) in _sans_retours(cartouche)
    assert str(naming.VERSION_RANK_MAX) in cartouche


def test_G7_le_refus_offre_TOUJOURS_au_moins_deux_issues():
    """`EPIC11-ARB-89` -- « un refus qui n'offre aucune issue est aussi fautif
    qu'une destruction silencieuse ».

    Les deux etats sont mesures : trois issues quand l'ecrasement conscient reste
    permis, deux quand le tirage est scanne -- et **jamais** une seule.
    """
    ecrasable = versions.issues_des_rangs_epuises(_tirage(LOT_COURANT))
    assert [issue.cle for issue in ecrasable] == [
        versions.CLE_REMPLACER, versions.CLE_RETIRER_DE_LA_PASSE,
        versions.CLE_ANNULER]
    scanne = versions.issues_des_rangs_epuises(
        _tirage(LOT_SCANNE, scanne=True))
    assert [issue.cle for issue in scanne] == [
        versions.CLE_RETIRER_DE_LA_PASSE, versions.CLE_ANNULER]
    for issues in (ecrasable, scanne):
        assert len(issues) >= 2
        assert any(not issue.ecrit for issue in issues)


def test_G7_l_ecran_de_refus_ne_dit_JAMAIS_echec():
    """`DESIGN.md` section 9 : il nomme ce qui n'a pas eu lieu.

    Volet symetrique : le titre existe et il est non vide -- une frontiere posee
    sur une chaine vide serait verte sans rien mesurer.
    """
    assert versions.TITRE_DES_RANGS_EPUISES
    assert "échec" not in versions.TITRE_DES_RANGS_EPUISES.lower()
    assert "erreur" not in versions.TITRE_DES_RANGS_EPUISES.lower()


# ===========================================================================
# L'ORDRE des N conflits -- « Par lot », et c'est un ordre CHOISI
# ===========================================================================

def test_l_ordre_des_conflits_est_PAR_LOT_et_non_celui_du_manifeste():
    """Reponse d'Egan du 2026-09-02, mot pour mot : « **Par lot** ».

    C'est ce qui ferme le dernier point ouvert d'`EPIC11-ARB-177` (« a poser
    explicitement plutot qu'a laisser l'ordre du manifeste decider en silence »).

    **Le test le mesure comme un CHOIX** : la fabrique ecrit les cinq lots dans
    un ordre qui n'est pas l'ordre par lot, et les deux ordres sont compares
    **tous les deux**. Un banc dont la fabrique serait deja triee ne verrait
    aucune difference entre « le produit trie » et « le produit rend ce qu'on lui
    donne » -- il serait vert sur un produit qui ne trie rien.
    """
    donnes = [_tirage(lot_id) for lot_id in LOTS_DE_LA_FABRIQUE]
    obtenu = [conflit.lot_id for conflit in versions.ordonner_par_lot(donnes)]

    assert obtenu == sorted(LOTS_DE_LA_FABRIQUE)
    assert obtenu != list(LOTS_DE_LA_FABRIQUE), (
        "la fabrique doit donner un ordre DIFFERENT de l'ordre par lot, sans "
        "quoi ce test est vert sur un produit qui ne trie pas")
    assert len(obtenu) == len(LOTS_DE_LA_FABRIQUE)


def test_l_ordre_par_lot_est_TOTAL___aucun_conflit_ne_se_perd_ni_ne_double():
    """Le tri **conserve** la file : cinq conflits entrent, cinq sortent.

    Un tri qui dedoublonnerait par lot perdrait un conflit -- et un conflit perdu
    est un tirage ecrase sans que personne n'ait tranche.
    """
    donnes = [_tirage(lot_id) for lot_id in LOTS_DE_LA_FABRIQUE]
    obtenu = versions.ordonner_par_lot(donnes)
    assert sorted(c.lot_id for c in obtenu) == sorted(LOTS_DE_LA_FABRIQUE)
    assert len({id(c) for c in obtenu}) == len(donnes)


# ===========================================================================
# L'ISSUE DE MASSE -- ses trois contraintes, chacune mesuree
# ===========================================================================

def test_la_masse_n_est_JAMAIS_la_premiere_issue_atteinte_au_montage():
    """Contrainte 1 d'`EPIC11-ARB-177` -- « a plus forte raison une qui ecrit
    N fois ».

    Deux mesures, parce que la contrainte en porte deux : le curseur ne la vise
    pas au montage, **et** elle est posee apres l'issue unitaire dans la liste.
    """
    for courant in (LOT_COURANT, LOT_SCANNE):
        choix = versions.choix_du_conflit(_passe(courant))
        cles = [issue.cle for issue in choix.issues]
        assert choix.issues[choix.curseur].cle != versions.CLE_MASSE, courant
        assert cles.index(versions.CLE_MASSE) > cles.index(
            versions.CLE_CREER), courant


def test_la_masse_NOMME_ce_qu_elle_emporte_en_cardinal_ET_en_poids():
    """Contrainte 2 -- « un `appliquer aux 4 restants` muet sur les megaoctets
    serait MOINS informatif que l'ecran qu'il remplace ».

    Les deux chiffres sont mesures separement : le cardinal des lots emportes et
    le poids en megaoctets, **derive de la fabrique** et jamais recopie.
    """
    passe = _passe()
    consequences = versions.consequences_des_issues(passe)
    ligne = consequences[versions.CLE_MASSE]

    restants = passe.restants
    emportes = [c for c in restants if not c.scanne]
    poids = sum(POIDS[c.lot_id] for c in emportes)
    assert f"{len(emportes)} lots" in ligne, ligne
    assert f"{poids:,}".replace(",", " ") + " Mo" in ligne, ligne
    assert "Mo" in ligne


def test_la_masse_SAUTE_le_tirage_scanne___et_elle_le_DIT():
    """Le saut est **affiche**, pas seulement journalise.

    « Un lot ecarte sans que l'ecran le nomme serait une decision cachee, ce
    qu'`ARB-89` proscrit au meme titre qu'une destruction silencieuse. »

    La cible scannee est **au milieu** des restants -- verifie ici plutot que
    suppose : un `break` a la premiere rencontre, ou un saut qui ne compterait que
    le premier element, resterait vert sur une cible en tete ou en queue.
    """
    passe = _passe()
    restants = passe.restants
    rangs_scannes = [rang for rang, c in enumerate(restants) if c.scanne]
    assert rangs_scannes == [1], [c.lot_id for c in restants]
    assert 0 < rangs_scannes[0] < len(restants) - 1

    emport = versions.emport_de_la_masse(restants, destructif=True)
    assert emport.sautes == 1
    assert emport.lots == len(restants) - 1
    assert emport.poids_mo == sum(POIDS[c.lot_id] for c in restants
                                  if not c.scanne)
    ligne = versions.consequence_de_la_masse(emport)
    assert versions.SAUT_DE_LA_MASSE[False].format(sautes=1) in ligne, ligne
    assert "scanné" in ligne


def test_le_saut_ne_s_ECRIT_PAS_quand_il_n_y_a_rien_a_sauter():
    """Volet symetrique : `0 sauté` se lirait comme une reserve la ou il n'y en
    a aucune.

    Sans ce test, la mesure precedente serait verte sur un produit qui ecrit la
    mention de saut **tout le temps**, c'est-a-dire sur un produit qui ne mesure
    rien.
    """
    restants = tuple(_tirage(lot_id) for lot_id in ("a_1", "b_2", "c_3")
                     if POIDS.setdefault(lot_id, 10))
    emport = versions.emport_de_la_masse(restants, destructif=True)
    assert emport.sautes == 0
    ligne = versions.consequence_de_la_masse(emport)
    assert "sauté" not in ligne and "sautés" not in ligne, ligne
    assert "3 lots" in ligne


def test_la_masse_de_E5_3c_n_efface_RIEN_et_ne_saute_personne():
    """« Une meme entree, deux poids, selon l'issue qu'elle prolonge. »

    `Remplacer` etant tombe, « ce choix » ne peut designer que `Créer la vN` : la
    masse cree N versions, n'efface rien, et n'a personne a sauter -- creer la vN
    d'un tirage scanne est precisement ce que `E5-3c` offre.
    """
    passe = _passe(LOT_SCANNE)
    ligne = versions.consequences_des_issues(passe)[versions.CLE_MASSE]
    assert ligne == f"{len(passe.restants)} versions créées — rien n'est effacé"
    assert "effacés" not in ligne
    assert not versions.choix_du_conflit(passe).issues[1].ecrit


def test_la_masse_douce_n_emporte_AUCUN_poids___dans_le_modele_aussi():
    """Le poids de la masse non destructive vaut zero **dans le modele**.

    La ligne affichee dit deja « rien n'est effacé », mais elle ne rend pas le
    chiffre : un `poids_mo` qui porterait la somme des restants serait donc
    invisible a l'ecran d'aujourd'hui **et faux pour tout ecran de demain**.

    **Trouve par la campagne de mutation** (`M21`, survivant du premier tour) :
    le mutant remplissait ce champ sans qu'aucun test ne le voie. C'est la
    definition d'une surface non mesuree, pas celle d'un mutant equivalent.
    """
    restants = _passe().restants
    doux = versions.emport_de_la_masse(restants, destructif=False)
    assert doux.poids_mo == 0
    assert doux.lots == len(restants)
    assert doux.sautes == 0
    assert doux.destructif is False
    # Volet symetrique : la meme fabrique, en destructif, porte bien un poids.
    assert versions.emport_de_la_masse(restants, destructif=True).poids_mo > 0


def test_la_masse_reste_UNE_ISSUE_PARMI_D_AUTRES():
    """Contrainte 3 -- « jamais une seule, jamais un blocage sec ».

    Les issues unitaires demeurent des deux cotes : c'est ce qui distingue le
    choix 3 d'`EPIC11-ARB-177` d'une selection en masse qui remplacerait l'ecran.
    """
    for courant, attendues in ((LOT_COURANT, {versions.CLE_CREER,
                                              versions.CLE_REMPLACER,
                                              versions.CLE_ANNULER}),
                               (LOT_SCANNE, {versions.CLE_CREER,
                                             versions.CLE_ANNULER})):
        cles = {i.cle for i in versions.choix_du_conflit(_passe(courant)).issues}
        assert attendues <= cles, (courant, cles)
        assert versions.CLE_MASSE in cles


def test_la_masse_n_est_pas_offerte_sur_le_DERNIER_conflit():
    """Une issue qui n'emporterait rien serait un bouton mort.

    Le volet symetrique est la seconde assertion : sur l'avant-dernier, elle est
    la et elle annonce **un** conflit restant.
    """
    passe = _passe()
    dernier = versions.PasseDeConflits(conflits=passe.conflits,
                                       rang_courant=len(passe.conflits) - 1)
    assert versions.CLE_MASSE not in {
        i.cle for i in versions.choix_du_conflit(dernier).issues}

    avant_dernier = versions.PasseDeConflits(conflits=passe.conflits,
                                             rang_courant=len(passe.conflits) - 2)
    issues = versions.choix_du_conflit(avant_dernier).issues
    masse = [i for i in issues if i.cle == versions.CLE_MASSE]
    assert len(masse) == 1
    # **La chaine ATTENDUE, et non `libelle_de_la_masse(1)`.** Cette ligne
    # comparait le produit a lui-meme : elle etait verte quel que soit le
    # gabarit, accord compris. Trouve par la couche 2 (finding C2-5).
    assert masse[0].libelle == "Appliquer ce choix au conflit restant"


# ===========================================================================
# G8 -- ensembles exacts, et ce qui DIVERGE entre deux rangs
# ===========================================================================

def test_G8_entre_une_passe_v1_et_une_passe_v4_l_ecran_ne_diverge_QUE_sur_l_issue():
    """AC 7.12, a l'echelle de l'ecran : l'ensemble exact de ce qui change.

    « Une assertion positive laisse passer toute divergence supplementaire. Ce
    champ diverge ne mesure rien ; l'ensemble des chemins qui divergent est
    **exactement** {X} mesure l'exception ET son unicite. »

    Ici : deux conflits identiques au seul `rang_propose` pres. La seule ligne qui
    doit changer est celle de `Créer la vN`. Une ligne de cartouche qui bougerait
    voudrait dire que le rang propose a fuite dans un endroit ou il n'a rien a
    faire -- typiquement le rang du tirage PRESENT, qui est un autre fait.
    """
    def _lignes(rang: int) -> list[str]:
        tirage = _tirage(LOT_COURANT, rang_propose=rang)
        passe = versions.PasseDeConflits(conflits=(tirage,))
        return (versions.lignes_du_cartouche(tirage)
                + [i.libelle for i in versions.choix_du_conflit(passe).issues])

    origine, quatre = _lignes(version_ranks.RANG_ORIGINE), _lignes(4)
    assert len(origine) == len(quatre)
    divergentes = {rang for rang, (a, b) in enumerate(zip(origine, quatre))
                   if a != b}
    assert len(divergentes) == 1, [(origine[r], quatre[r])
                                   for r in sorted(divergentes)]
    rang = divergentes.pop()
    assert origine[rang] == versions.libelle_de_la_creation(
        version_ranks.RANG_ORIGINE)
    assert quatre[rang] == versions.libelle_de_la_creation(4)


def test_G8_l_ensemble_exact_des_lignes_du_cartouche_de_chaque_etat():
    """Les deux cartouches, par leurs libelles de gauche, a l'egalite.

    `E5-3c` ne porte **pas** la ligne `Mise en page` -- il a une mention plus
    longue a montrer, et la mise en page n'est pas ce qu'un operateur a besoin de
    lire pour comprendre qu'il ne peut pas ecraser.
    """
    def _libelles(tirage) -> list[str]:
        return [ligne.split("  ")[0]
                for ligne in versions.lignes_du_cartouche(tirage)
                if ligne and not ligne.startswith(("▲", "·", " "))]

    assert _libelles(_tirage(LOT_COURANT)) == [
        versions.LIBELLE_DU_LOT, versions.LIBELLE_DE_LA_DATE,
        versions.LIBELLE_DU_CONTENU, versions.LIBELLE_DE_LA_MISE_EN_PAGE,
        versions.LIBELLE_DU_SCAN]
    assert _libelles(_tirage(LOT_SCANNE, scanne=True)) == [
        versions.LIBELLE_DU_LOT, versions.LIBELLE_DE_LA_DATE,
        versions.LIBELLE_DU_CONTENU, versions.LIBELLE_DU_SCAN]


# ===========================================================================
# La grille -- 80x24, dans les DEUX regimes
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_deux_ecrans_tiennent_dans_la_grille_PLANCHER(banc, ascii_seul):
    """`EPIC11-ARB-21` : 80x24, et `E5-3b` y tient **a la ligne pres**.

    C'est l'ecran le plus haut du lot -- neuf lignes de cartouche, deux de cadre,
    six d'issues. Une ligne de confort de plus le ferait deborder, et un ecran
    tronque ment sur ce qui tient.
    """
    for passe in (_passe(), _passe(LOT_SCANNE)):
        ecran = _ecran(passe)
        cartouche, issues = _rendu(ecran, banc,
                                   app=_app(ecran, ascii_seul=ascii_seul))
        lignes = cartouche.splitlines() + issues.splitlines()
        # +2 : le cadre du cartouche, pose par la bordure du conteneur.
        assert len(lignes) + 2 <= HAUTEUR_DU_CENTRE, (
            passe.courant.lot_id, len(lignes))
        for ligne in lignes:
            assert jetons.colonnes(ligne) <= UTILE, (
                ligne, jetons.colonnes(ligne))


@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucun_glyphe_UTF8_ne_survit_au_repli_ASCII(banc, ascii_seul):
    """Le repli ne laisse passer **aucun** glyphe de la table UTF-8.

    Mesure dans les deux regimes : en UTF-8 les glyphes doivent etre la, en ASCII
    aucun ne doit rester. Un test qui ne jouerait que le repli serait vert sur un
    ecran qui ne dessine rien.
    """
    ecran = _ecran()
    cartouche, issues = _rendu(ecran, banc,
                               app=_app(ecran, ascii_seul=ascii_seul))
    rendu = cartouche + issues
    # **Les glyphes deja ASCII sont ecartes de la mesure**, et il faut le dire :
    # `GLYPHES["invite"]` vaut `>`, qui est aussi le curseur du repli. Les
    # compter ferait rougir un repli parfaitement correct -- et un test ajuste
    # ensuite au code aurait relache la mesure entiere pour ce seul cas.
    presents = {glyphe for glyphe in jetons.GLYPHES.values()
                if not glyphe.isascii() and glyphe in rendu}
    if ascii_seul:
        assert not presents, presents
        assert jetons.GLYPHES_ASCII["curseur"] in rendu
    else:
        assert {jetons.GLYPHES["curseur"], jetons.GLYPHES["substitute"],
                jetons.GLYPHES["neutre"]} <= presents, presents


def test_aucune_lettre_n_est_un_raccourci_sur_ces_deux_ecrans():
    """`EPIC11-ARB-45` / `-126` : **fleche seule** hors des listes a cocher.

    Et la frappe imprimable est **consommee** : laisser remonter `q` fermerait
    l'application sur une touche que rien n'annonce.
    """
    ecran = _ecran()
    depart = ecran.choix.curseur
    for lettre in ("q", "r", "c", "a"):
        assert ecran.traiter("x", lettre) is True
        assert ecran.choix.curseur == depart, lettre
    assert versions.RACCOURCIS_DU_CONFLIT == (
        "⏎ valider  ↑↓ choisir  Échap retour  F1 aide")


def test_la_ligne_de_raccourcis_tient_dans_les_DEUX_regimes():
    """MESURE: 44/44 colonnes (utf8/ascii), budget `UTILE` = 76."""
    utf8 = jetons.colonnes(versions.RACCOURCIS_DU_CONFLIT)
    ascii_ = jetons.colonnes(
        jetons.replier_ascii(versions.RACCOURCIS_DU_CONFLIT))
    assert utf8 <= UTILE and ascii_ <= UTILE, (utf8, ascii_)


# ===========================================================================
# Le bandeau -- la portee du conflit, par lot
# ===========================================================================

def test_le_bandeau_porte_la_PORTEE_du_conflit_et_l_etat_du_tirage():
    """`1 conflit sur 5 · tirage présent`, et sa variante scannee.

    Les deux etats portent le **meme** cardinal : ce sont deux etats du meme
    premier conflit d'une meme passe, et un bandeau different les aurait fait
    lire comme deux passes.
    """
    passe = _passe()
    assert passe.portee == f"1 conflit sur {len(LOTS_DE_LA_FABRIQUE)}"
    assert _ecran(passe).objet_du_bandeau().endswith("tirage présent")
    scanne = _passe(LOT_SCANNE)
    assert scanne.portee == f"3 conflit sur {len(LOTS_DE_LA_FABRIQUE)}"
    assert _ecran(scanne).objet_du_bandeau().endswith("tirage scanné")


def test_une_passe_sans_conflit_est_REFUSEE_a_la_construction():
    """Un jugement sans objet n'est pas un jugement.

    Le refuser a la construction le rend impossible plutot qu'improbable -- meme
    geste que `ChoixExclusif`, qui refuse une issue unique.
    """
    with pytest.raises(ValueError):
        versions.PasseDeConflits(conflits=())


# ===========================================================================
# G9 -- accords et separateurs, sur des cas ATTEIGNABLES (finding C2-5)
# ===========================================================================
#
# Les trois cas fermes ici sont **atteignables en production**, et deux d'entre
# eux le sont par le chemin nominal :
#
# * `1 conflit restant` l'est des qu'une passe porte DEUX conflits ;
# * la source partielle l'est par un tirage declare a l'inventaire dont le
#   fichier ne repond plus (`_mo_du_fichier` et `_quand_du_fichier` rendent
#   `None` sur `OSError`), ou par `makepdf._entree_du_rang` qui rend `None`
#   quand l'inventaire est plus court que ce que le coeur annonce ;
# * la masse destructive sans emport l'est quand le conflit courant est
#   ecrasable et que tous les restants sont scannes.
#
# Le banc de `libelle_de_la_masse` etait **tautologique** -- il comparait le
# produit a lui-meme, donc aucune mutation du gabarit ne le faisait rougir. La
# ligne corrigee est dans `test_la_masse_n_est_pas_offerte_sur_le_DERNIER_conflit`.


def test_le_libelle_de_la_masse_S_ACCORDE_a_UN_seul_conflit_restant():
    """Les deux formes, ecrites, et non le produit compare a lui-meme.

    Les deux voisins immediats du gabarit portent deja une forme singuliere --
    `SAUT_DE_LA_MASSE` et `MOT_DES_VERSIONS`. Celui-ci ne l'avait pas, et
    rendait `aux 1 conflits restants` sur le cas multi-lots courant.
    """
    assert versions.libelle_de_la_masse(1) == (
        "Appliquer ce choix au conflit restant")
    assert versions.libelle_de_la_masse(4) == (
        "Appliquer ce choix aux 4 conflits restants")


def _tirage_a_source_partielle(**muets) -> versions.TirageEnConflit:
    """Un tirage dont la source ne repond que pour une partie des mesures."""
    complet = dict(pages=PAGES_DESSINEES, poids_mo=POIDS_DESSINE_MO,
                   quand=QUAND_DESSINE, quand_court=QUAND_COURT_DESSINE)
    complet.update(muets)
    return versions.TirageEnConflit(
        nom="", lot_id=LOT_COURANT, rang=RANG_PRESENT,
        rang_propose=RANG_PROPOSE, **complet)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_une_source_MUETTE_ne_laisse_pas_de_SEPARATEUR_orphelin(ascii_seul):
    """`▲   · ce tirage n'est pas scanné` : un separateur sans rien devant.

    Le module retire partout ailleurs les segments qu'il ne sait pas remplir --
    « il vaut mieux une ligne plus courte qu'un chiffre invente ». Le separateur
    de tete etait la seule exception, et il annoncait une mesure qui n'existe
    pas.
    """
    muet = _tirage_a_source_partielle(pages=None, poids_mo=None, quand=None,
                                      quand_court=None)
    ligne = versions.ligne_d_etat(muet, ascii_seul)
    table = jetons.glyphes(ascii_seul)
    assert ligne == f"{table['substitute']}  ce tirage n'est pas scanné", ligne
    assert versions.SEPARATEUR not in ligne


@pytest.mark.parametrize("ascii_seul", MODES)
def test_une_source_PARTIELLE_garde_ce_qu_elle_sait_et_TAIT_le_reste(ascii_seul):
    """Le volet symetrique, et il ferme le survivant `M06` de la couche 2.

    Un `and` devenu `or` sur `poids_mo is not None and quand_court` rend
    `352 Mo écrits le None`. Aucun banc ne construisait un conflit a source
    partielle : les deux moities sont donc mesurees separement.
    """
    sans_date = versions.ligne_d_etat(
        _tirage_a_source_partielle(quand=None, quand_court=None), ascii_seul)
    assert f"{PAGES_DESSINEES} pages" in sans_date
    assert "None" not in sans_date and "Mo" not in sans_date, sans_date

    sans_poids = versions.ligne_d_etat(
        _tirage_a_source_partielle(poids_mo=None), ascii_seul)
    assert f"{PAGES_DESSINEES} pages" in sans_poids
    assert "None" not in sans_poids and "Mo" not in sans_poids, sans_poids

    sans_pages = versions.ligne_d_etat(
        _tirage_a_source_partielle(pages=None), ascii_seul)
    assert "page" not in sans_pages, sans_pages
    assert (f"{POIDS_DESSINE_MO} Mo écrits le {QUAND_COURT_DESSINE}"
            in sans_pages)


def test_la_masse_DESTRUCTIVE_qui_n_emporte_RIEN_ne_promet_pas_un_effacement():
    """`0 lot · 0 Mo effacés` promet une destruction qui n'aura pas lieu.

    Le cas : le conflit courant est ecrasable, et **tous** les restants sont
    scannes. La consequence dit alors ce qui est vrai -- rien n'est efface --
    et garde la reserve, qui est la seule information de la ligne.
    """
    emport = versions.EmportDeLaMasse(lots=0, poids_mo=0, sautes=1,
                                      destructif=True)
    ligne = versions.consequence_de_la_masse(emport)
    assert ligne == "rien n'est effacé — 1 sauté, il est scanné", ligne
    assert "0 lot" not in ligne and "0 Mo" not in ligne


def test_la_masse_destructive_qui_emporte_QUELQUE_CHOSE_le_CHIFFRE_toujours():
    """Volet symetrique : sans lui, la mesure ci-dessus serait verte sur un
    produit qui aurait cesse de chiffrer ce qu'il efface -- c'est-a-dire sur
    l'inverse de la contrainte 2 d'`EPIC11-ARB-177`."""
    ligne = versions.consequence_de_la_masse(
        versions.EmportDeLaMasse(lots=2, poids_mo=1332, sautes=1,
                                 destructif=True))
    assert ligne == "2 lots · 1 332 Mo effacés — 1 sauté, il est scanné", ligne


# ===========================================================================
# Les deux maquettes du conflit, LUES a leur source plutot que recopiees
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc citait `E5-3b` et `E5-3c` par
# leur code, y compris dans le titre de sa docstring, et n'ouvrait ni l'un ni
# l'autre : dix-neuf de ses valeurs en etaient recopiees. Le fichier annonce
# pourtant, des sa docstring, que « rien n'est tape a la main de ce que le
# produit sait construire » -- la promesse tenait pour le COEUR (les noms
# viennent de `io.naming`, les refus de `io.version_ranks`) et pas pour le
# DESSIN.
#
# Ce qui est confronte est, chaque fois que possible, ce que le PRODUIT rend :
# `versions.RACCOURCIS_DU_CONFLIT`, `versions.libelle_de_la_masse`,
# `PasseDeConflits.portee`, `objet_du_bandeau()`. Une constante de banc
# comparee a elle-meme ne mesurerait rien -- c'est deja ce que la section G2
# dit de ses deux verbatims.
#
# **Les deux verbatims d'Egan gagnent ici une TROISIEME source**, et c'est le
# point qui compte. G2 les retape a la main depuis la note d'Egan, deliberement
# (« comparer la constante du produit a elle-meme ne mesurerait rien »). Le
# dessin est une source de plus, independante des deux autres : la note, le
# module, le dessin doivent dire la meme phrase. Une derive de l'un des trois
# rougit desormais.

#: Les maquettes, a leur source.
MAQUETTES = (Path(_SRC).parents[0] / "_bmad-output" / "planning-artifacts"
             / "ux-designs" / "ux-tui-2026-08-27" / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies.

    Le repliement des espaces n'est pas une complaisance : le cartouche coupe
    les longues phrases sur deux lignes (« ...n'écrasez pas cette / planche
    sous peine... »), et une phrase qui doit etre mesuree MOT POUR MOT ne peut
    pas l'etre autrement. Le volet negatif plus bas montre qu'il n'absorbe
    rien d'autre.
    """
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


def lignes_du_dessin(nom: str) -> list[str]:
    """Les lignes du dessin, cadre retire, ESPACES INTERNES INTACTS.

    Le repliement de `dessin_de_la_maquette` mange les espaces doubles ; il le
    faut pour les phrases coupees en deux lignes, mais il rend alors
    indiscernables `⏎ valider  ↑↓ choisir` et `⏎ valider ↑↓ choisir`. La ligne
    de raccourcis vit precisement de ses espaces doubles, qui separent ses
    quatre couples. Elle se mesure donc ici, ou rien n'est replie.
    """
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    sans_cadre = "".join(" " if c in CADRE_DU_DESSIN else c for c in brut)
    return [ligne.strip() for ligne in sans_cadre.splitlines()]


def _valeurs_communes() -> tuple[str, ...]:
    """Ce que les DEUX dessins portent, rendu par le produit.

    Repliees comme le dessin l'est : le cartouche coupe ses longues phrases,
    et une comparaison non repliee ne les retrouverait jamais.
    """
    return tuple(" ".join(valeur.split()) for valeur in (
        PROJET,
        f"{PAGES_DESSINEES} pages",
        QUAND_DESSINE,
        f"Créer la v{RANG_PROPOSE}",
        versions.libelle_de_la_masse(len(LOTS_DE_LA_FABRIQUE) - 1),
    ))


#: Les deux dessins et ce que chacun porte EN PROPRE, en plus du commun. Deux
#: elements distinguables : `E5-3b` est le seul a offrir l'ecrasement, `E5-3c`
#: le seul a l'interdire. Une permutation des deux se verrait.
DESSINS_DU_CONFLIT = [
    ("E5-3b", "E5-3b-pdf-tirage-existe.txt",
     ("tirage présent", VERBATIM_DE_L_ECRASEMENT,
      "ce tirage n'est pas scanné",
      f"{POIDS_DESSINE_MO} Mo écrits le {QUAND_COURT_DESSINE}")),
    ("E5-3c", "E5-3c-pdf-tirage-scanne.txt",
     ("tirage scanné", VERBATIM_DU_TIRAGE_SCANNE,
      "versions créées — rien n'est effacé")),
]


@pytest.mark.parametrize(("code", "fichier", "propres"), DESSINS_DU_CONFLIT,
                         ids=[c for c, _, _ in DESSINS_DU_CONFLIT])
def test_les_valeurs_du_conflit_sont_VERBATIM_de_leur_maquette(
        code, fichier, propres):
    """Chaque valeur est DANS le dessin, lu sur disque a ce tour-ci.

    Ce n'est pas une ressemblance, c'est une appartenance : le jour ou une
    maquette change, ce test rouge NOMME l'ecart (`EPIC11-ARB-144`) plutot que
    de le laisser filer jusqu'a une divergence silencieuse entre le produit et
    un dessin approuve.
    """
    dessin = dessin_de_la_maquette(fichier)
    for attendu in _valeurs_communes() + tuple(propres):
        assert " ".join(attendu.split()) in dessin, (code, attendu)


@pytest.mark.parametrize(("code", "fichier"),
                         [(c, f) for c, f, _ in DESSINS_DU_CONFLIT],
                         ids=[c for c, _, _ in DESSINS_DU_CONFLIT])
def test_la_ligne_de_raccourcis_est_celle_du_dessin_ESPACES_COMPRIS(code,
                                                                    fichier):
    """`RACCOURCIS_DU_CONFLIT` est une LIGNE du dessin, a l'egalite.

    A l'egalite et non par appartenance : une ligne de raccourcis plus longue
    que le dessin ne serait pas un detail, elle deborderait la grille. Et sans
    repliement, parce que les espaces doubles y separent les quatre couples --
    c'est ce que `lignes_du_dessin` preserve.
    """
    assert versions.RACCOURCIS_DU_CONFLIT in lignes_du_dessin(fichier), code


def test_la_PORTEE_de_la_passe_est_celle_que_les_deux_dessins_annoncent():
    """`1 conflit sur 5` vient du produit, et les deux dessins la portent.

    Le cardinal de cinq n'est pas decoratif : les dessins montrent cinq
    conflits parce qu'une issue de masse ne se voit pas sur un seul restant.
    Une fabrique ramenee a deux lots ferait rougir ici, ce qui est le but.
    """
    portee = _passe().portee
    assert portee == f"1 conflit sur {len(LOTS_DE_LA_FABRIQUE)}"
    for _, fichier, _ in DESSINS_DU_CONFLIT:
        assert portee in dessin_de_la_maquette(fichier)


def test_les_deux_dessins_se_DISTINGUENT_sur_l_ecrasement():
    """Le volet symetrique, sans quoi la table passerait en ne mesurant rien.

    Les deux ecrans sont le meme lot, le meme tirage, la meme date : seule la
    ligne `Scanné` change, et avec elle la liste des issues
    (`EPIC11-ARB-174`). Si les deux verbatims etaient dans les deux dessins,
    la confrontation ci-dessus serait verte sans rien distinguer.
    """
    existe = dessin_de_la_maquette("E5-3b-pdf-tirage-existe.txt")
    scanne = dessin_de_la_maquette("E5-3c-pdf-tirage-scanne.txt")
    assert VERBATIM_DE_L_ECRASEMENT in existe
    assert VERBATIM_DE_L_ECRASEMENT not in scanne
    assert VERBATIM_DU_TIRAGE_SCANNE in scanne
    assert VERBATIM_DU_TIRAGE_SCANNE not in existe
    assert "tirage présent" in existe and "tirage présent" not in scanne
    assert "tirage scanné" in scanne and "tirage scanné" not in existe


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : le pli absorbe la mise en page, PAS un ecart.

    Quatre contre-exemples, dont trois a un caractere ou un mot pres. Sans
    eux, une comparaison toujours vraie passerait les trois tests ci-dessus.
    """
    existe = dessin_de_la_maquette("E5-3b-pdf-tirage-existe.txt")
    assert f"{PAGES_DESSINEES + 1} pages" not in existe
    assert VERBATIM_DE_L_ECRASEMENT.replace("planche", "page") not in existe
    assert (versions.RACCOURCIS_DU_CONFLIT + "  Q quitter"
            not in lignes_du_dessin("E5-3b-pdf-tirage-existe.txt"))
    assert (versions.RACCOURCIS_DU_CONFLIT.replace("  ", " ")
            not in lignes_du_dessin("E5-3b-pdf-tirage-existe.txt")), (
        "les espaces doubles ne sont pas absorbes par lignes_du_dessin")
    assert "1 conflit sur 2" not in existe
