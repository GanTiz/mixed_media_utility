# -*- coding: utf-8 -*-
"""Le PARCOURS des suites de `E6-3` et `E6-3b` : le clavier, puis l'ecran d'arrivee.

**Le manque que ce banc ferme, et il est mesure** (`MQ-4` / `MQ-5`, audit du
parcours complet du 2026-09-06, retrouve le meme jour sur ce module-ci par la
frontiere `test_couverture_des_suites.py`). `projet_suppression` declare
**quatre** suites -- `SUITE_REESSAYER`, `SUITE_OUVRIR`, `SUITE_RETOUR`,
`SUITE_OUVRIR_PROJET` --, deux ecrans valides et livres les portent, et les
deux etaient construits **sans `sur_suite`**.
`execution.EcranResultat.__init__` le dit en toutes lettres : « Absent, toute
suite autre que le retour mene a l'ecran "pas encore" ». Au clavier, sur les
deux ecrans de compte rendu d'une suppression, « Reessayer », « Ouvrir le
dossier » et « Ouvrir le dossier du projet » tombaient donc dans le filet.

C'est la cinquieme occurrence du meme mode de panne dans cet epic (`E9`, `I3`,
`MQ-4`/`MQ-5`, `MQ-8`) : **un composant livre, teste, et cable nulle part dans
l'application est un composant que le produit n'a pas.**

Pourquoi ce banc et pas seulement la table de couverture
---------------------------------------------------------
`test_couverture_des_suites.py` mesure qu'une branche est **nommee**, pas
qu'elle mene quelque part d'utile -- elle le dit elle-meme : « un
`if suite == SUITE_PDF: return` la satisferait ». Celui-ci part du **clavier**
et confronte l'**ecran d'arrivee**, sur le modele de
`test_porte_de_l_inventaire.py`. Les deux mesures sont complementaires : celle-la
attrape l'oubli, celle-ci attrape l'erreur.

**Ce banc joue l'APPLICATION DU PRODUIT, jamais une fixture** pour les sept
parcours nominaux : `chaine_du_produit()`, sept frappes jusqu'a l'inventaire,
`Suppr`, la validation de l'issue qui ecrit, puis les suites. Une chaine
assemblee a la main est **precisement** ce qui a masque `E9` pendant deux
vagues.

**Le coeur est le VRAI coeur, sur le VRAI disque**, y compris pour l'echec
partiel : seul `Path.unlink` refuse, une fois, sur un fichier nomme -- c'est
l'idiome deja employe par
`tests/unit/test_suppression_element_de_projet.py::test_un_echec_de_suppression_de_fichier_se_VOIT_dans_le_rapport`,
et c'est le seul moyen de produire un droit refuse dans un conteneur ou l'on
est `root` (mesure : `unlink` sur un fichier d'un dossier `0555` **reussit**).

Ce que ce banc a MESURE et qui n'etait pas suppose
---------------------------------------------------
« Reessayer » rejoue le coeur, et le coeur **est rejouable** : sur un echec
partiel, `remove_project_element` restaure le manifeste d'avant (« des lors que
des fichiers restent, le lot EXISTE encore [...] le geste redevient
rejouable »). Mesure faite avant d'ecrire la branche, sur le regime de ce banc :
premier appel `supprime=False` avec un reste, lot **encore declare** ; second
appel `supprime=True`, `fichiers_a_supprimer` reduit **au seul survivant**, lot
retire. Le reessai ne recompte donc pas ce qui est deja parti.

Regle des fabriques (`CLAUDE.md`, les QUATRE points)
-----------------------------------------------------
La collection dont l'ordre compte ici est **la liste des suites** -- c'est elle
que `rang_du_curseur` indexe, et un balayage tronque d'un bord y colorerait la
mauvaise ligne sans jamais planter.

* le projet porte **deux rushes**, **quatre lots** et des fichiers de poids
  **tous distincts** (11, 101, 1001, 10001 octets) : jamais un remplissage
  uniforme, une permutation ne se verrait pas ;
* le lot vise est au **milieu** du manifeste, ni premier ni dernier -- un
  `find` fautif qui rendrait toujours le premier se demasque ;
* les **trois** suites d'`E6-3` sont jouees en **tete**, au **milieu** et en
  **queue**, et les **deux** de `E6-3b` en **tete** et en **queue**. Le milieu
  demasque un aiguillage fautif, les deux bords demasquent un balayage tronque,
  qui est un autre mode de panne ;
* les **restes** sont **deux** fichiers dans **deux dossiers differents**, l'un
  en tete et l'autre en queue de la liste rendue par le coeur : c'est ce qui
  fait travailler le parent commun de :func:`dossier_des_restes` au lieu de le
  laisser sur un dossier unique.
"""
from __future__ import annotations

import json
import pathlib
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io import project_layout
from mixed_media_utility.project_maintenance import (ProjectMaintenanceError,
                                                     RapportSuppression)
from mixed_media_utility.project_inventory import NATURE_LOT
from mixed_media_utility.tui import projet_suppression as ps
from mixed_media_utility.tui import projets
from mixed_media_utility.tui.atelier_extraction_ecriture import (
    ChaineReelle, chaine_du_produit)
from mixed_media_utility.tui.coque import EcranPasEncore
from mixed_media_utility.tui.execution import EcranRefus
from mixed_media_utility.tui.panneau import Issue
from mixed_media_utility.tui.projet_inventaire import EcranInventaireDuProjet

#: Le regime de `MQ-8`, frappe par frappe : `⏎` ouvre le projet le plus
#: recent, `↓↓↓↓` descend jusqu'a l'entree *Projet*, `⏎` y entre, `⏎` ouvre
#: *Gestion des medias*.
JUSQU_A_L_INVENTAIRE = ("enter", "down", "down", "down", "down", "enter",
                        "enter")

#: Le lot vise. Il est au **milieu** des quatre lots du manifeste, et il porte
#: DEUX dossiers de frames -- c'est ce qui donne des restes dans deux dossiers.
LOT_VISE = "m-milieu_25"

#: Les deux dossiers de frames d'un lot, **lus** de `io/project_layout` et
#: jamais composes a la main : c'est le seul lieu du depot ou ces noms sont
#: ecrits, et le seul qui connaisse la cohabitation du nom neuf et de celui
#: d'avant (`EPIC11-ARB-222`). Une frontiere negative de
#: `test_vocabulaire_de_la_tui.py` mesure ce geste sur les bancs aussi.
FRAMES = project_layout.EXTRACT_FRAMES_DIRNAME
FRAMES_SCANNEES = project_layout.SCAN_FRAMES_DIRNAME

#: Les deux fichiers que le verrou refuse. L'un est en **tete** de la liste que
#: le coeur rend, l'autre en **queue** : un balayage tronque d'un bord dans
#: `dossier_des_restes` se verrait. Le coeur rend cette liste TRIEE, et `aaa`
#: precede `zzz` : les deux bords sont donc bien ceux qu'on croit, ce que la
#: premiere assertion du parcours verifie.
#:
#: **Ils vivent dans DEUX SOUS-DOSSIERS FRERES, et c'est un mutant qui l'a
#: impose** (`SUP-02` de la campagne du 2026-09-06). La premiere redaction les
#: mettait dans deux dossiers de PREMIER niveau, si bien que leur parent commun
#: etait le dossier du projet lui-meme -- exactement ce que « Ouvrir le dossier
#: du projet » ouvre. Les deux destinations coincidaient donc dans la fixture,
#: et le mutant qui les PERMUTE **survivait** : aucune assertion ne pouvait les
#: distinguer. Deux freres poses un cran plus bas rendent le parent commun
#: distinct des trois autres candidats -- le projet, et chacun des deux
#: dossiers pris seul.
RESTES = (f"{FRAMES}/{LOT_VISE}/aaa/aaa_bloque.tiff",
          f"{FRAMES}/{LOT_VISE}/zzz/zzz_bloque.tiff")

#: Le parent commun attendu : ni le projet, ni l'un des deux freres.
DOSSIER_DES_RESTES = f"{FRAMES}/{LOT_VISE}"


# ---------------------------------------------------------------------------
# Les fabriques -- DEUX rushes, QUATRE lots, des poids TOUS DISTINCTS
# ---------------------------------------------------------------------------

def _projet_a_quatre_lots(tmp_path) -> Path:
    """Un projet reel, dont le lot vise n'est **ni le premier ni le dernier**.

    Les poids sont tous distincts (11, 101, 1001, 10001 octets) : une fabrique
    uniforme rendrait invisible tout desappariement entre un noeud de l'arbre
    et le lot qu'il designe.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "a-premier"}, {"rush_id": "z-second"}]
    document["lots"] = [
        {"lot_id": "a-premier_12p5", "rush_id": "a-premier",
         "frames_dir": f"{FRAMES}/a-premier_12p5"},
        {"lot_id": LOT_VISE, "rush_id": "a-premier",
         "frames_dir": f"{FRAMES}/{LOT_VISE}",
         "output_frames_dir": f"{FRAMES_SCANNEES}/{LOT_VISE}"},
        {"lot_id": "z-second_8", "rush_id": "z-second",
         "frames_dir": f"{FRAMES}/z-second_8"},
        {"lot_id": "z-second_50", "rush_id": "z-second",
         "frames_dir": f"{FRAMES}/z-second_50"},
    ]
    (chemin / "project.json").write_text(json.dumps(document),
                                         encoding="utf-8")
    for relatif, octets in (
            (f"{FRAMES}/a-premier_12p5/f0.tiff", 11),
            (RESTES[0], 101),
            (f"{FRAMES}/{LOT_VISE}/mmm_libre.tiff", 202),
            (RESTES[1], 303),
            (f"{FRAMES_SCANNEES}/{LOT_VISE}/n0.tiff", 404),
            (f"{FRAMES}/z-second_8/h0.tiff", 1001),
            (f"{FRAMES}/z-second_50/i0.tiff", 10001)):
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)
    return chemin


def _chaine_sur(chemin: Path, tmp_path) -> ChaineReelle:
    """La chaine **du produit**, ouverte sur ce projet par sa liste de recents."""
    recents = projets.Recents(tmp_path / "reglages" / "recents-v1.json")
    recents.noter_ouverture(chemin)
    return chaine_du_produit(recents=recents)


@pytest.fixture
def verrou(monkeypatch):
    """Un `unlink` qui refuse les fichiers nommes, tant qu'on ne le desarme pas.

    C'est l'idiome deja employe par le banc du coeur : dans un conteneur ou
    l'on est `root`, aucun droit de systeme de fichiers ne produit un refus --
    mesure faite, `unlink` sur un fichier d'un dossier `0555` reussit.
    """
    bloques = {Path(reste).name for reste in RESTES}
    original = pathlib.Path.unlink

    def unlink_verrouille(self, *args, **mots):
        if self.name in bloques:
            raise OSError("fichier verrouille (simule)")
        return original(self, *args, **mots)

    monkeypatch.setattr(pathlib.Path, "unlink", unlink_verrouille)
    return bloques


# ---------------------------------------------------------------------------
# La navigation du produit, jusqu'au compte rendu
# ---------------------------------------------------------------------------

async def _jusqu_a_l_inventaire(pilote) -> EcranInventaireDuProjet:
    await pilote.press(*JUSQU_A_L_INVENTAIRE)
    await pilote.pause()
    ecran = pilote.app.screen
    assert isinstance(ecran, EcranInventaireDuProjet), type(ecran).__name__
    return ecran


async def _jusqu_au_compte_rendu(pilote):
    """Sept frappes, `Suppr` sur le lot vise, puis l'issue qui ECRIT.

    Le curseur est amene sur le lot par des `↓` **reels** : viser a la main
    sauterait le clavier que ce banc existe pour mesurer. L'issue qui ecrit
    est atteinte par des `↑↓` reels elle aussi -- le curseur part sur une
    issue qui n'ecrit pas (`EPIC11-ARB-7`), il faut donc s'en eloigner.
    """
    inventaire = await _jusqu_a_l_inventaire(pilote)
    for _ in range(len(inventaire.arbre)):
        courant = inventaire.arbre.courant
        if courant is not None and courant.nom == LOT_VISE:
            break
        await pilote.press("down")
        await pilote.pause()
    assert inventaire.arbre.courant is not None
    assert inventaire.arbre.courant.nom == LOT_VISE
    assert inventaire.arbre.courant.nature == NATURE_LOT
    await pilote.press("delete")
    await pilote.pause()
    confirmation = pilote.app.screen
    assert isinstance(confirmation, ps.EcranSuppressionConfirmation), \
        type(confirmation).__name__
    rangs = [rang for rang, issue in enumerate(confirmation.choix.issues)
             if issue.cle == ps.CLE_SUPPRIMER]
    assert rangs, [i.cle for i in confirmation.choix.issues]
    ecart = rangs[0] - confirmation.choix.curseur
    await pilote.press(*(("down",) * ecart if ecart > 0
                         else ("up",) * -ecart))
    await pilote.pause()
    await pilote.press("enter")
    await pilote.pause()
    return pilote.app.screen


async def _choisir_la_suite(pilote, ecran, suite: str):
    """Amener le curseur sur `suite` par des `↑↓` reels, puis `⏎`."""
    assert suite in ecran.suites, (suite, ecran.suites)
    ecart = ecran.suites.index(suite) - ecran.curseur
    await pilote.press(*(("down",) * ecart if ecart > 0 else ("up",) * -ecart))
    await pilote.pause()
    assert ecran.suites[ecran.curseur] == suite
    await pilote.press("enter")
    await pilote.pause()
    return pilote.app.screen


# ---------------------------------------------------------------------------
# `E6-3b` -- le chemin nominal : tout est parti
# ---------------------------------------------------------------------------

def test_le_PRODUIT_mene_de_Suppr_a_E6_3b_AVEC_son_parcours_cable(tmp_path,
                                                                  banc):
    """Le compte rendu monte **cable**, et c'est exactement ce qui manquait.

    La mesure porte sur `_sur_suite` et non sur un texte : un ecran de compte
    rendu dont le parcours est `None` est indistinguable, a l'oeil, de celui
    qui est cable -- jusqu'a ce qu'on presse `⏎`.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    ecran = banc(chaine.app, _jusqu_au_compte_rendu)

    assert isinstance(ecran, ps.EcranReussiteDeSuppression), type(ecran).__name__
    assert ecran._sur_suite is not None, (
        "le compte rendu est monte sans parcours : « Ouvrir le dossier du "
        "projet » tombe dans le filet « pas encore »")


def test_sur_E6_3b_les_suites_sont_CELLES_DE_LA_MAQUETTE_dans_l_ordre(tmp_path,
                                                                      banc):
    """`E6-3b` dessine deux suites, dans cet ordre, et pas une troisieme.

    L'egalite est **exacte** : `EcranResultat` ajoute d'office sa propre
    `RETOUR` quand l'appelant n'en met pas, ce qui produirait ici DEUX retours
    -- l'un menant a l'inventaire, l'autre aux ateliers.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    ecran = banc(chaine.app, _jusqu_au_compte_rendu)

    assert ecran.suites == [ps.SUITE_OUVRIR_PROJET, ps.SUITE_RETOUR]


def test_sur_E6_3b_OUVRIR_LE_PROJET_est_en_TETE_dit_le_chemin_et_reste(
        tmp_path, banc):
    """La suite de **tete** : elle DIT, et **l'ecran ne change pas**.

    Descendre d'un palier pour annoncer qu'un dossier a ete ouvert ferait
    perdre le compte rendu au moment meme ou l'operateur va le comparer au
    contenu du dossier. Le fait affiche est une **mesure** -- un chemin, ou un
    motif nomme -- et jamais une touche ni un conseil (`EPIC11-ARB-56`).
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        ecran = await _jusqu_au_compte_rendu(pilote)
        assert ecran.suites[0] == ps.SUITE_OUVRIR_PROJET, ecran.suites
        apres = await _choisir_la_suite(pilote, ecran, ps.SUITE_OUVRIR_PROJET)
        return apres, ecran._etat_courant

    apres, fait = banc(chaine.app, scenario)

    assert isinstance(apres, ps.EcranReussiteDeSuppression), type(apres).__name__
    assert not isinstance(apres, EcranPasEncore)
    assert fait.endswith(str(chemin)), fait


def test_sur_E6_3b_RETOUR_est_en_QUEUE_et_mene_a_L_INVENTAIRE(tmp_path, banc):
    """La suite de **queue** : l'inventaire, pas le menu des ateliers.

    **La surcharge du libelle ne suffisait pas** : les deux ecrans posent
    `RETOUR = SUITE_RETOUR` (« Retour a l'inventaire »), mais
    `EcranResultat.choisir` traitait sa propre `RETOUR` par
    `revenir_aux_ateliers()`, deux stations plus haut. L'ecran annoncait une
    destination et en servait une autre.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        ecran = await _jusqu_au_compte_rendu(pilote)
        assert ecran.suites[-1] == ps.SUITE_RETOUR, ecran.suites
        apres = await _choisir_la_suite(pilote, ecran, ps.SUITE_RETOUR)
        noms = (sorted(n.nom for n in apres.arbre.tous())
                if isinstance(apres, EcranInventaireDuProjet) else [])
        return apres, noms

    apres, noms = banc(chaine.app, scenario)

    assert isinstance(apres, EcranInventaireDuProjet), type(apres).__name__
    # L'arbre est RELU : un arbre garde de l'ouverture listerait encore le lot
    # que le coeur vient de retirer -- un apercu qui ment (`EPIC11-ARB-46`).
    assert LOT_VISE not in noms, noms
    # ... et les trois autres lots sont toujours la : une relecture qui rendrait
    # un arbre vide serait pire qu'un arbre perime.
    assert {"a-premier_12p5", "z-second_8", "z-second_50"} <= set(noms), noms


# ---------------------------------------------------------------------------
# `E6-3` -- il RESTE des fichiers
# ---------------------------------------------------------------------------

def test_le_PRODUIT_mene_a_E6_3_quand_des_fichiers_RESISTENT(tmp_path, banc,
                                                             verrou):
    """La fuite que la story existe pour fermer, jouee sur le vrai coeur."""
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    ecran = banc(chaine.app, _jusqu_au_compte_rendu)

    assert isinstance(ecran, ps.EcranResultatDeSuppression), type(ecran).__name__
    assert ecran.rapport.fichiers_non_supprimes == RESTES, \
        ecran.rapport.fichiers_non_supprimes
    assert ecran.suites == [ps.SUITE_REESSAYER, ps.SUITE_OUVRIR,
                            ps.SUITE_RETOUR]
    assert ecran._sur_suite is not None, (
        "`E6-3` est monte sans parcours : ses trois suites tombent dans le "
        "filet « pas encore »")


def test_sur_E6_3_REESSAYER_est_en_TETE_rejoue_le_coeur_et_mene_a_E6_3b(
        tmp_path, banc, verrou):
    """La suite de **tete**, et la **seule des quatre qui ecrive**.

    Le verrou est desarme avant la frappe : c'est le regime reel -- l'operateur
    ferme l'application qui tenait le fichier, puis reessaie. Le compte rendu
    est **remplace** et non empile : trois reessais laisseraient sinon trois
    `E6-3` l'un sur l'autre.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        ecran = await _jusqu_au_compte_rendu(pilote)
        assert ecran.suites[0] == ps.SUITE_REESSAYER, ecran.suites
        hauteur = len(pilote.app.screen_stack)
        verrou.clear()          # le fichier n'est plus verrouille
        apres = await _choisir_la_suite(pilote, ecran, ps.SUITE_REESSAYER)
        return apres, hauteur, len(pilote.app.screen_stack)

    apres, avant, apres_hauteur = banc(chaine.app, scenario)

    assert isinstance(apres, ps.EcranReussiteDeSuppression), type(apres).__name__
    assert apres.rapport.supprime is True
    # Le reessai ne recompte pas ce qui est deja parti : il ne vise que les
    # survivants.
    assert set(apres.rapport.fichiers_a_supprimer) == set(RESTES), \
        apres.rapport.fichiers_a_supprimer
    assert apres_hauteur == avant, (
        f"le compte rendu a ete EMPILE ({avant} -> {apres_hauteur}) au lieu "
        f"d'etre remplace : trois reessais demanderaient trois remontees")
    assert apres._sur_suite is not None, (
        "le compte rendu du reessai est monte sans parcours")
    for reste in RESTES:
        assert not (chemin / reste).exists(), reste


def test_sur_E6_3_REESSAYER_qui_ECHOUE_ENCORE_reste_sur_E6_3(tmp_path, banc,
                                                             verrou):
    """Le volet symetrique : un reessai qui ne passe pas ne ment pas.

    Sans lui, une branche qui monterait `E6-3b` **inconditionnellement** apres
    un reessai resterait verte sur le test ci-dessus -- et annoncerait « tout
    est parti » avec deux fichiers toujours sur le disque.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        ecran = await _jusqu_au_compte_rendu(pilote)
        return await _choisir_la_suite(pilote, ecran, ps.SUITE_REESSAYER)

    apres = banc(chaine.app, scenario)

    assert isinstance(apres, ps.EcranResultatDeSuppression), type(apres).__name__
    assert apres.rapport.fichiers_non_supprimes == RESTES
    for reste in RESTES:
        assert (chemin / reste).exists(), reste


def test_sur_E6_3_OUVRIR_est_AU_MILIEU_dit_le_PARENT_COMMUN_et_reste(
        tmp_path, banc, verrou):
    """La suite du **milieu** -- celle qu'un aiguillage fautif emporte.

    Les deux restes vivent dans deux dossiers differents ; le dossier ouvert
    est donc leur **parent commun**, c'est-a-dire le dossier du projet. En
    ouvrir un seul cacherait l'autre derriere un libelle qui ne le dit pas.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        ecran = await _jusqu_au_compte_rendu(pilote)
        assert ecran.suites[1] == ps.SUITE_OUVRIR, ecran.suites
        apres = await _choisir_la_suite(pilote, ecran, ps.SUITE_OUVRIR)
        return apres, ecran._etat_courant

    apres, fait = banc(chaine.app, scenario)

    assert isinstance(apres, ps.EcranResultatDeSuppression), type(apres).__name__
    # **Le chemin est epingle par EGALITE de fin, pas par inclusion** : le
    # dossier du projet est un PREFIXE de tous les candidats, si bien qu'un
    # `in` resterait vert sur n'importe lequel -- c'est ce qui a laisse
    # survivre `SUP-02`.
    assert fait.endswith(str(chemin / DOSSIER_DES_RESTES)), fait
    assert not fait.endswith(str(chemin)), (
        "c'est le dossier du PROJET qui a ete ouvert, pas celui des restes")


def test_sur_E6_3_RETOUR_est_en_QUEUE_et_mene_a_L_INVENTAIRE(tmp_path, banc,
                                                             verrou):
    """La suite de **queue** du second ecran. Le lot RESTE declare.

    Le coeur restaure le manifeste sur un echec partiel : l'inventaire relu
    doit donc **toujours** porter le lot -- l'y voir disparaitre serait un
    apercu qui ment dans l'autre sens.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        ecran = await _jusqu_au_compte_rendu(pilote)
        apres = await _choisir_la_suite(pilote, ecran, ps.SUITE_RETOUR)
        noms = (sorted(n.nom for n in apres.arbre.tous())
                if isinstance(apres, EcranInventaireDuProjet) else [])
        return apres, noms

    apres, noms = banc(chaine.app, scenario)

    assert isinstance(apres, EcranInventaireDuProjet), type(apres).__name__
    assert LOT_VISE in noms, noms


# ---------------------------------------------------------------------------
# Le filet -- un ENSEMBLE EXACT, et les inconnues aux DEUX bords
# ---------------------------------------------------------------------------

def test_les_suites_qui_TOMBENT_DANS_LE_FILET_sont_un_ENSEMBLE_EXACT(tmp_path,
                                                                     banc):
    """Les quatre suites reelles menent quelque part ; **elles seules**.

    **Le mutant que ce test existe pour tuer** est celui de `M23` du lot
    `MQ-A`, pris par l'autre bout : un aiguillage trop large -- un `else` qui
    ouvrirait le dossier, ou une derniere branche sans garde -- ferait qu'une
    suite ajoutee demain agirait au lieu de nommer son absence. Aucune
    assertion prise suite par suite ne le voit ; l'egalite d'ensemble, si.

    Les deux libelles inconnus sont poses en **tete** et en **queue** de la
    liste jouee : c'est aux bords qu'un balayage tronque se cache.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)
    libelles = ["suite-inconnue-de-tete", ps.SUITE_REESSAYER, ps.SUITE_OUVRIR,
                ps.SUITE_OUVRIR_PROJET, ps.SUITE_RETOUR,
                "suite-inconnue-de-queue"]

    async def scenario(pilote):
        ecran = await _jusqu_au_compte_rendu(pilote)
        plan, rapport = ecran.plan, ecran.rapport
        issue = Issue(ps.CLE_ANNULER, "sans ecriture")
        au_filet = []
        for libelle in libelles:
            ps.suivre(ecran, plan, rapport, issue, libelle)
            await pilote.pause()
            if isinstance(pilote.app.screen, EcranPasEncore):
                au_filet.append(libelle)
                pilote.app.action_remonter()
                await pilote.pause()
            while not isinstance(pilote.app.screen,
                                 (ps.EcranReussiteDeSuppression,
                                  ps.EcranResultatDeSuppression)):
                # `Retour` a bien mene a l'inventaire : on redescend sur le
                # compte rendu pour jouer la suite suivante.
                pilote.app.descendre(ecran)
                await pilote.pause()
        return au_filet

    au_filet = banc(chaine.app, scenario)

    assert au_filet == ["suite-inconnue-de-tete", "suite-inconnue-de-queue"], \
        au_filet


# ---------------------------------------------------------------------------
# Les unites -- sans coque, la ou la coque n'apporte rien
# ---------------------------------------------------------------------------

def _plan(projet) -> ps.PlanDeSuppression:
    return ps.PlanDeSuppression(projet=Path(projet), cible={"lot_id": LOT_VISE},
                                libelle=f"{PREFIXE_DESSINE_DU_LIBELLE}{LOT_VISE}",
                                rapport=_rapport())


def _rapport(restes: tuple[str, ...] = RESTES) -> RapportSuppression:
    return RapportSuppression(cible=LOT_VISE, fichiers_a_supprimer=RESTES,
                              dry_run=False, supprime=not restes,
                              fichiers_non_supprimes=restes)


def test_le_dossier_des_restes_est_le_PARENT_COMMUN_des_DEUX_bords(tmp_path):
    """Deux restes, deux dossiers, chacun a un bord de la liste rendue.

    Un balayage qui sauterait le premier ou le dernier reste rendrait un
    parent **plus profond** -- donc un dossier qui cache l'autre --, et il ne
    leverait pas : c'est le mode de panne que le quatrieme point de la regle
    des fabriques attrape.
    """
    commun = ps.dossier_des_restes(_plan(tmp_path), _rapport())
    assert commun == tmp_path / DOSSIER_DES_RESTES
    # ... et ce n'est **ni** le projet **ni** l'un des deux freres : les trois
    # autres candidats sont nommes, sans quoi une permutation de destination
    # resterait invisible (mutant `SUP-02`).
    assert commun != tmp_path
    # Un seul reste : c'est SON dossier, et le `.parent` se voit -- sans lui,
    # on rendrait le FICHIER.
    seul_en_tete = ps.dossier_des_restes(_plan(tmp_path),
                                         _rapport((RESTES[0],)))
    seul_en_queue = ps.dossier_des_restes(_plan(tmp_path),
                                          _rapport((RESTES[1],)))
    assert seul_en_tete == tmp_path / DOSSIER_DES_RESTES / "aaa"
    assert seul_en_queue == tmp_path / DOSSIER_DES_RESTES / "zzz"
    assert seul_en_tete != seul_en_queue != commun


def test_aucun_reste_ne_rend_AUCUN_dossier_plutot_que_la_racine(tmp_path):
    """Rendre le projet quand rien ne reste ouvrirait un dossier pour rien.

    La phrase est alors :data:`AUCUN_DOSSIER_A_OUVRIR` -- une suite qui ne
    rendrait rien serait la suite decorative du finding `K3`.
    """
    assert ps.dossier_des_restes(_plan(tmp_path), _rapport(())) is None
    assert ps.ouvrir_le_dossier_des_restes(None, _plan(tmp_path),
                                           _rapport(())) == \
        ps.AUCUN_DOSSIER_A_OUVRIR


def test_les_QUATRE_suites_portent_des_libelles_DISTINCTS():
    """Deux suites au meme libelle feraient de la seconde une branche morte.

    L'aiguillage compare des chaines ; c'est la meme mesure que
    `test_couverture_des_suites.py` porte sur tous les modules, reprise ici
    pour que ce banc ne dependre pas de l'ordre de collecte.
    """
    libelles = [ps.SUITE_REESSAYER, ps.SUITE_OUVRIR, ps.SUITE_RETOUR,
                ps.SUITE_OUVRIR_PROJET]
    assert len(set(libelles)) == 4, libelles


def test_REESSAYER_NOMME_le_refus_du_coeur_plutot_que_de_planter(tmp_path,
                                                                 banc):
    """`EPIC11-ARB-89` : jamais un blocage sec, jamais une trace de pile.

    Le regime est reel et il est **nomme** dans la docstring de
    :func:`reessayer_la_suppression` : la cible `planche` ne restaure pas
    l'entree du manifeste apres un echec partiel, si bien qu'un reessai y
    rend `ProjectMaintenanceError`. Le message voyage **verbatim**
    (`EPIC11-ARB-30`).

    **L'ecran d'arrivee est un REFUS depuis `EPIC11-ARB-260`, et ce test
    affirmait `EcranPasEncore` avant le 2026-09-06** -- garde plutot
    qu'efface. Un reessai qui echoue n'annonce aucun ecran a venir : il
    constate que le manifeste ne porte plus la cible. Le volet negatif est
    mesure avec le positif, parce que c'est leur difference qui compte.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)
    refus = "Lot inconnu du manifeste de ce projet: 'm-milieu_25'"

    def coeur_qui_refuse(*args, **mots):
        raise ProjectMaintenanceError(refus)

    async def scenario(pilote):
        await _jusqu_a_l_inventaire(pilote)
        ecran = ps.EcranResultatDeSuppression(_plan(chemin), _rapport())
        pilote.app.descendre(ecran)
        await pilote.pause()
        ps.reessayer_la_suppression(
            ecran, ecran.plan, Issue(ps.CLE_SUPPRIMER, "Supprimer", ecrit=True),
            retirer_du_projet=coeur_qui_refuse)
        await pilote.pause()
        arrivee = pilote.app.screen
        return (arrivee, str(getattr(arrivee, "message", "")),
                str(getattr(arrivee, "code", "")))

    arrivee, message, code = banc(chaine.app, scenario)

    assert isinstance(arrivee, EcranRefus), type(arrivee).__name__
    assert not isinstance(arrivee, EcranPasEncore), type(arrivee).__name__
    assert refus == message, message
    assert code == "PROJECT_MAINTENANCE_ERROR", code


def test_remonter_a_l_inventaire_SANS_inventaire_ne_VIDE_pas_la_pile(tmp_path,
                                                                     banc):
    """Le regime d'un banc qui monte `E6-3` seul : on remonte d'UN cran.

    Depiler jusqu'a la racine y serait pire que ne rien faire -- l'operateur
    perdrait tout son contexte pour une suite qui promet un retour d'un cran.
    Le volet symetrique du test de queue ci-dessus : sans lui, une boucle
    `while len(stack) > 1: pop()` sans garde resterait verte.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        await pilote.press("enter")     # le menu des ateliers, sans inventaire
        await pilote.pause()
        ecran = ps.EcranResultatDeSuppression(_plan(chemin), _rapport())
        pilote.app.descendre(ecran)
        await pilote.pause()
        hauteur = len(pilote.app.screen_stack)
        rendu = ps.remonter_a_l_inventaire(ecran, ecran.plan)
        await pilote.pause()
        return rendu, hauteur, len(pilote.app.screen_stack)

    rendu, avant, apres = banc(chaine.app, scenario)

    assert rendu is False
    assert apres == avant - 1, (avant, apres)


def test_le_REMPLACEMENT_ne_depile_QUE_l_ecran_de_celui_qui_le_demande(
        tmp_path, banc):
    """La garde de :func:`remplacer_le_compte_rendu`, mesuree par son envers.

    Sans elle, un appel venu d'ailleurs -- un reessai dont l'ecran a deja ete
    depile par une autre suite, par exemple -- depilerait l'ecran de quelqu'un
    d'autre. Le test place donc un ecran ETRANGER au sommet et verifie que
    rien n'est retire sous lui.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        await _jusqu_a_l_inventaire(pilote)
        ancien = ps.EcranResultatDeSuppression(_plan(chemin), _rapport())
        etranger = ps.EcranReussiteDeSuppression(_plan(chemin), _rapport(()))
        pilote.app.descendre(etranger)
        await pilote.pause()
        hauteur = len(pilote.app.screen_stack)
        nouveau = ps.EcranResultatDeSuppression(_plan(chemin), _rapport())
        ps.remplacer_le_compte_rendu(pilote.app, ancien, nouveau)
        await pilote.pause()
        return hauteur, len(pilote.app.screen_stack), \
            etranger in pilote.app.screen_stack

    avant, apres, etranger_intact = banc(chaine.app, scenario)

    assert apres == avant + 1, (avant, apres)
    assert etranger_intact, "l'ecran d'un autre a ete depile"


def test_une_RELECTURE_REFUSEE_laisse_l_arbre_PRECEDENT_et_ne_leve_pas(
        tmp_path, banc):
    """`EPIC11-ARB-89` sur la relecture : un arbre vide serait pire que perime.

    Le regime est reel et joue **sur le disque** : le `project.json` cesse
    d'etre du JSON pendant que l'inventaire est monte -- c'est la lecon du
    2026-09-02 prise dans le bon sens, une panne de terrain plutot qu'une
    fixture qui leve a la demande.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        inventaire = await _jusqu_a_l_inventaire(pilote)
        avant = sorted(n.nom for n in inventaire.arbre.tous())
        (chemin / "project.json").write_text("{ ceci n'est pas du JSON",
                                             encoding="utf-8")
        from mixed_media_utility.tui.projet_inventaire import (
            relire_l_inventaire)
        rendu = relire_l_inventaire(inventaire, chemin)
        await pilote.pause()
        return rendu, avant, sorted(n.nom for n in inventaire.arbre.tous())

    rendu, avant, apres = banc(chaine.app, scenario)

    assert rendu is False
    assert apres == avant, (avant, apres)
    assert LOT_VISE in apres, apres


@pytest.mark.parametrize("avec_restes", [False, True], ids=["E6-3b", "E6-3"])
def test_ECHAP_tient_la_promesse_de_sa_ligne_de_raccourcis(tmp_path, banc,
                                                           monkeypatch,
                                                           avec_restes):
    """`Échap inventaire` mene a l'inventaire, sur les DEUX ecrans.

    **Le meme defaut que `SUITE_RETOUR`, par l'autre touche.**
    :data:`RACCOURCIS_RESULTAT` -- verbatim des deux maquettes -- annonce
    « Échap inventaire », et `EcranResultat.on_key` traitait `escape` par
    `revenir_aux_ateliers()`, deux stations plus haut. C'est la touche
    qu'Egan presse en premier pour sortir d'un compte rendu.

    Les deux ecrans sont joues : celui qui n'a pas de restes et celui qui en a.
    Ne mesurer que l'un des deux laisserait l'autre partir aux ateliers, et
    c'est exactement le mode de panne que ce lot ferme -- une moitie cablee.
    """
    chemin = _projet_a_quatre_lots(tmp_path)
    if avec_restes:
        original = pathlib.Path.unlink
        bloques = {Path(reste).name for reste in RESTES}

        def unlink_verrouille(self, *args, **mots):
            if self.name in bloques:
                raise OSError("fichier verrouille (simule)")
            return original(self, *args, **mots)

        monkeypatch.setattr(pathlib.Path, "unlink", unlink_verrouille)
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        ecran = await _jusqu_au_compte_rendu(pilote)
        assert RACCOURCI_DESSINE_DU_RETOUR in ecran.raccourcis, ecran.raccourcis
        attendu = (ps.EcranResultatDeSuppression if avec_restes
                   else ps.EcranReussiteDeSuppression)
        assert isinstance(ecran, attendu), type(ecran).__name__
        await pilote.press("escape")
        await pilote.pause()
        return pilote.app.screen

    apres = banc(chaine.app, scenario)

    assert isinstance(apres, EcranInventaireDuProjet), type(apres).__name__


# ===========================================================================
# Les maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc appelle `RACCOURCIS_RESULTAT`
# « verbatim des deux maquettes » dans une docstring et n'ouvrait ni `E6-3`
# ni `E6-3b`. « Verbatim » est exactement la promesse qu'une recopie ne peut
# pas tenir : elle est vraie le jour ou on l'ecrit, puis le dessin bouge sans
# elle.

#: Le raccourci de retour, dessine au pied des DEUX comptes rendus.
RACCOURCI_DESSINE_DU_RETOUR = "Échap inventaire"

#: Le jeton que `EPIC11-ARB-246` a RETIRE de ces deux ecrans (Q21, Egan le
#: 2026-09-06). Il etait dessine au pied des deux maquettes jusqu'au
#: 2026-09-06 ; la mesure ci-dessous a change de SENS le meme jour, et c'est
#: son volet negatif qui la tient desormais.
JETON_RETIRE_DU_JOURNAL = "Tab journal"

#: Le prefixe du libelle de suppression, dessine par `E6-3b`. Le lot qui le
#: SUIT, lui, n'est pas dessine : ce banc emploie deliberement `m-milieu_25`
#: la ou le dessin montre `plan-04_12p5`, pour que la cible ne soit ni en
#: tete ni en queue de ses collections. La confrontation mesure les deux
#: faits plutot que d'en taire un.
PREFIXE_DESSINE_DU_LIBELLE = "tout le lot "

#: Les dessins repris ici, a leur source.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕▓▒░█"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"

#: Les deux comptes rendus, et c'est une fabrique a DEUX elements
#: distinguables : l'un a des restes, l'autre non, et la mesure les separe.
DESSINS_DU_COMPTE_RENDU = (
    ("E6-3", "E6-3-projet-suppression-resultat.txt"),
    ("E6-3b", "E6-3b-projet-suppression-reussie.txt"),
)


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


@pytest.mark.parametrize("code,fichier", DESSINS_DU_COMPTE_RENDU,
                         ids=[c for c, _ in DESSINS_DU_COMPTE_RENDU])
def test_le_RACCOURCI_de_retour_est_dessine_par_CHACUN_des_deux(code, fichier):
    """Le « verbatim des deux maquettes » de la docstring, enfin mesure.

    Un par un et non « au moins un des deux » : les deux pieds sont
    identiques, ce qui est justement ce qui rend une mesure globale
    trompeuse -- elle resterait verte si un seul dessin le portait.

    **Ce banc a change de SENS le 2026-09-06, et c'est ce que « verbatim »
    coute quand le dessin bouge.** Il exigeait
    ``"Tab journal " + RACCOURCI_DESSINE_DU_RETOUR`` ; `EPIC11-ARB-246` a
    retire ce jeton des deux ecrans le jour meme, les maquettes ont ete
    corrigees A LA SOURCE (`EPIC11-ARB-142`), et les deux parametres ont
    rougi. La mesure est donc reprise par son volet NEGATIF -- le jeton doit
    etre absent --, seul volet qui attrape une reapparition. Le cardinal
    ferme la porte de derriere : un pied dessine deux fois passerait les
    deux autres assertions.
    """
    dessin = dessin_de_la_maquette(fichier)
    assert RACCOURCI_DESSINE_DU_RETOUR in dessin, code
    assert JETON_RETIRE_DU_JOURNAL not in dessin, code
    assert dessin.count(RACCOURCI_DESSINE_DU_RETOUR) == 1, code


def test_les_DEUX_comptes_rendus_sont_DISTINGUABLES_malgre_leur_pied_commun():
    """Volet symetrique : meme pied, contenus opposes.

    Sans lui, la mesure ci-dessus serait aussi vraie de deux copies du meme
    fichier, et l'appariement code/dessin pourrait etre permute sans que
    rien ne rougisse. `E6-3` est l'echec (des restes), `E6-3b` la reussite.
    """
    incomplet = dessin_de_la_maquette("E6-3-projet-suppression-resultat.txt")
    reussi = dessin_de_la_maquette("E6-3b-projet-suppression-reussie.txt")

    assert incomplet != reussi
    assert "Suppression INCOMPLÈTE" in incomplet
    assert "Suppression INCOMPLÈTE" not in reussi
    assert "Rang libéré" in reussi
    assert "Rang libéré" not in incomplet


def test_le_PREFIXE_du_libelle_est_dessine_mais_PAS_le_lot_qui_le_suit():
    """La moitie recopiee et la moitie qui ne l'est pas, mesurees separement.

    `E6-3b` dessine « tout le lot plan-04_12p5 ». Ce banc construit « tout le
    lot m-milieu_25 » : le prefixe vient du dessin, l'identifiant vient de la
    regle des fabriques -- `m-milieu_25` est nomme pour etre au MILIEU d'une
    collection de quatre lots, ce que `plan-04_12p5` ne garantirait pas.

    Confronter le libelle assemble ferait donc rougir a tort. Confronter le
    seul prefixe sans dire pourquoi laisserait croire a une recopie
    complete. La mesure dit les deux.
    """
    reussi = dessin_de_la_maquette("E6-3b-projet-suppression-reussie.txt")
    assert PREFIXE_DESSINE_DU_LIBELLE in reussi
    assert PREFIXE_DESSINE_DU_LIBELLE + "plan-04_12p5" in reussi

    assert LOT_VISE not in reussi
    assert PREFIXE_DESSINE_DU_LIBELLE + LOT_VISE not in reussi


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    for _, fichier in DESSINS_DU_COMPTE_RENDU:
        dessin = dessin_de_la_maquette(fichier)
        assert "Échap ateliers" not in dessin
        assert "Échap retour" not in dessin
