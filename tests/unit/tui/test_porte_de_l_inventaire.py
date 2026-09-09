# -*- coding: utf-8 -*-
"""La PORTE de l'inventaire : ce que le PRODUIT ouvre sur « Gestion des médias ».

**Le manque que ce banc ferme, et il est mesure** (`MQ-8`, audit du parcours
complet du 2026-09-06). `EcranInventaireDuProjet` -- `E6-1`, story 11.11, lot B
-- est ecrit, exporte et mesure par 129 tests, et **aucun module de `tui/` ne
le construit**. Son seul point d'injection possible est
`ChaineReelle.entrer_commande`, qui envoyait **les trois** entrees du palier
Projet vers `EcranPasEncore`. La premiere de ces trois est celle que la
maquette validee `E6-0-projet-palier.txt` dessine **en tete** -- « Gestion des
médias », `palier_projet.ENTREE_MEDIAS` --, parce que c'est celle qui sert le
plus souvent.

C'est la quatrieme occurrence du meme mode de panne dans cet epic (`E9`, `I3`,
puis `MQ-4`/`MQ-5` la meme nuit) : **un composant livre, teste, et cable nulle
part dans l'application est un composant que le produit n'a pas.**

**Ce banc joue l'APPLICATION DU PRODUIT, jamais une fixture.** Il monte
`chaine_du_produit()` -- le point d'entree reel, celui qui injecte les
parcours -- et il frappe les touches du regime exact de l'audit :

    `mmu-tui` -> `⏎` -> `↓↓↓↓` -> `⏎` -> `⏎`

Un banc qui assemblerait la chaine a la main est **precisement** ce qui a
masque `E9` pendant deux vagues : « c'est cette assemblee manuelle qui a masque
le manque -- la recette passait par la demo, jamais par le point d'entree du
produit » (`ChaineReelle`).

Les quatre refus du coeur, et pourquoi ils sont ici
---------------------------------------------------
`project_inventory.inventorier_le_projet` leve **quatre refus publies** --
`ProjetIntrouvable`, `ManifesteIntrouvable`, `ManifesteIllisible`,
`ManifesteIncoherent`. Recensement fait avant d'ecrire une ligne, et refait au
premier geste de ce lot :

    grep -rn "ProjetIntrouvable\\|ManifesteIllisible" src/ --include=*.py \\
        | grep -v project_inventory.py

rendait **zero ligne** : aucun module de `tui/` ne les importait, ne les
attrapait ni ne les nommait. Un `project.json` illisible aurait donc rendu une
**trace de pile** a l'ecran -- un cran pire que le blocage sec
qu'`EPIC11-ARB-89` interdit deja. Les quatre regimes sont donc joues **sur le
disque reel**, jamais par un double qui leverait a la demande : c'est la lecon
du 2026-09-02, « une fixture de synthese peut fabriquer une panne que le
terrain n'a pas », prise dans l'autre sens.

**Deux issues, et pas trois** (`EPIC11-ARB-147`, 2026-08-31). Ces quatre refus
ne detruisent rien : ils disent qu'un projet ne se lit pas. `ARB-147` a corrige
le jour meme une AC qui appliquait `ARB-89` **par ressemblance de forme** a un
refus qui n'ecrivait rien -- « un refus qui ne detruit rien n'a pas besoin
d'issue de secours, et lui en fabriquer une produit un ecran qui demande de
choisir entre deux facons de ne rien faire ». L'ecran monte est donc
`execution.EcranRefus`, **existant et deja valide**, dont les deux sorties sont
`⏎ revenir aux ateliers` et `Q quitter`. Aucun ecran neuf n'est dessine ici :
`EPIC11-ARB-144` l'interdit tant qu'aucune maquette ne le porte, et aucune ne
dessine ce refus-la.

Regle des fabriques, les QUATRE points
--------------------------------------
Le projet de ce banc porte **deux rushes** aux **deux lots chacun**, tous de
tailles differentes -- jamais un remplissage uniforme. Les cibles sont posees
en **tete**, au **milieu** et en **queue** :

* les trois entrees du palier Projet sont jouees **toutes les trois**, et
  celle qui change de destination est en **tete** : un aiguillage qui rendrait
  toujours la premiere destination resterait vert sur elle seule ;
* les quatre refus sont joues **tous les quatre**, et le banc de
  :func:`code_du_refus` place la cible au **premier**, au **milieu** et au
  **dernier** rang de la table des refus -- un balayage tronque d'un bord est
  un autre mode de panne que l'aiguillage fautif, et c'est celui que ce depot
  paie le plus souvent en mutants survivants.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.project_inventory import (InventaireError,
                                                   ManifesteIllisible,
                                                   ManifesteIncoherent,
                                                   ManifesteIntrouvable,
                                                   NATURE_LOT,
                                                   ProjetIntrouvable)
from mixed_media_utility.tui import palier_projet, projets
from mixed_media_utility.tui.atelier_extraction_ecriture import (
    ChaineReelle, chaine_du_produit)
from mixed_media_utility.tui.coque import EcranPasEncore
from mixed_media_utility.tui.execution import EcranRefus
from mixed_media_utility.tui.palier_profil_defaut import EcranProfilParDefaut
from mixed_media_utility.tui.panneau import Issue
from mixed_media_utility.tui.projet_inventaire import (
    CE_QUI_MANQUE_A_LA_SUPPRESSION, EcranInventaireDuProjet)
from mixed_media_utility.tui.projet_suppression import (
    EcranSuppressionConfirmation)

#: Le regime exact de `MQ-8`, frappe par frappe. `⏎` ouvre le projet le plus
#: recent, `↓↓↓↓` descend jusqu'a l'entree *Projet* -- cinquieme et derniere du
#: menu des ateliers --, `⏎` y entre.
JUSQU_AU_PALIER_PROJET = ("enter", "down", "down", "down", "down", "enter")


# ---------------------------------------------------------------------------
# Les fabriques -- DEUX rushes, DEUX lots chacun, tous DISTINGUABLES
# ---------------------------------------------------------------------------

def _projet_a_deux_rushes(tmp_path) -> Path:
    """Un projet reel a deux rushes et quatre lots, tous de poids differents.

    Les poids sont **tous distincts** (11, 101, 1001, 10001 octets) : une
    fabrique uniforme rendrait invisible tout desappariement entre un noeud de
    l'arbre et le lot qu'il designe, et c'est le defaut central que la regle
    des fabriques de ce depot existe pour attraper.

    Les noms sont choisis pour que l'ordre alphabetique ne soit pas l'ordre
    d'ecriture : `z-second` est declare apres `a-premier` mais le precede
    nulle part, si bien qu'un balayage qui rendrait le premier rencontre se
    voit.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "a-premier"}, {"rush_id": "z-second"}]
    document["lots"] = [
        {"lot_id": "a-premier_25", "rush_id": "a-premier",
         "frames_dir": "extract-frames/a-premier_25"},
        {"lot_id": "a-premier_12p5", "rush_id": "a-premier",
         "frames_dir": "extract-frames/a-premier_12p5"},
        {"lot_id": "z-second_8", "rush_id": "z-second",
         "frames_dir": "extract-frames/z-second_8"},
        {"lot_id": "z-second_50", "rush_id": "z-second",
         "frames_dir": "extract-frames/z-second_50"},
    ]
    (chemin / "project.json").write_text(json.dumps(document),
                                         encoding="utf-8")
    for relatif, octets in (
            ("extract-frames/a-premier_25/f0.tiff", 11),
            ("extract-frames/a-premier_12p5/f0.tiff", 101),
            ("extract-frames/z-second_8/f0.tiff", 1001),
            ("extract-frames/z-second_50/f0.tiff", 10001)):
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)
    return chemin


def _chaine_sur(chemin: Path, tmp_path) -> ChaineReelle:
    """La chaine **du produit**, ouverte sur ce projet par sa liste de recents.

    C'est `chaine_du_produit` et non `ChaineReelle(...)` : le premier injecte
    les parcours, le second est la version degradee que seuls les bancs
    montent. Mesurer le second serait mesurer un produit qui n'existe pas.
    """
    recents = projets.Recents(tmp_path / "reglages" / "recents-v1.json")
    recents.noter_ouverture(chemin)
    return chaine_du_produit(recents=recents)


def _jouer(chaine: ChaineReelle, touches, banc, apres_le_palier=None,
           lire=None):
    """Frapper `touches` sur l'application montee, rendre l'ecran du dessus.

    `apres_le_palier` est appele une fois le palier Projet atteint et **avant**
    la derniere frappe : c'est ce qui permet de casser le manifeste sous les
    pieds de l'operateur, qui est le regime reel des quatre refus.

    `lire` est applique a l'ecran **pendant** que l'application est montee, et
    son resultat voyage a cote de l'ecran. Ce n'est pas du confort : tout ce
    qui touche a `self.app` -- et le rendu d'un ecran en est -- leve une fois
    le gestionnaire de contexte referme, comme le conftest le dit deja.
    """
    async def scenario(pilote):
        await pilote.press(*JUSQU_AU_PALIER_PROJET)
        await pilote.pause()
        if apres_le_palier is not None:
            apres_le_palier()
        await pilote.press(*touches)
        await pilote.pause()
        ecran = pilote.app.screen
        return ecran if lire is None else (ecran, lire(ecran))

    return banc(chaine.app, scenario)


# ---------------------------------------------------------------------------
# La porte elle-meme -- `MQ-8`
# ---------------------------------------------------------------------------

def test_le_PRODUIT_ouvre_l_INVENTAIRE_sur_Gestion_des_medias(tmp_path, banc):
    """`MQ-8` en une ligne : sept frappes, et l'inventaire s'ouvre.

    Avant ce lot, la septieme frappe rendait `EcranPasEncore`. La mesure porte
    sur le **type de l'ecran monte** et non sur son texte : un ecran « pas
    encore » qui citerait l'inventaire dans sa phrase passerait un grep.
    """
    chemin = _projet_a_deux_rushes(tmp_path)
    ecran = _jouer(_chaine_sur(chemin, tmp_path), ("enter",), banc)

    assert not isinstance(ecran, EcranPasEncore), (
        "la porte de l'inventaire n'est toujours pas posee : « Gestion des "
        "médias » tombe dans le filet")
    assert isinstance(ecran, EcranInventaireDuProjet), type(ecran).__name__


def test_l_inventaire_OUVERT_PAR_LE_PRODUIT_porte_le_VRAI_projet(tmp_path,
                                                                 banc):
    """L'arbre est celui du disque, pas un arbre vide monte pour la forme.

    Un cablage qui construirait `EcranInventaireDuProjet()` **sans arbre**
    passerait le test ci-dessus : l'ecran existe, il est du bon type, et il
    affiche `E6-1a` -- la lecture en cours -- indefiniment. Les deux rushes et
    les quatre lots sont donc comptes, et les DEUX rushes le sont : un arbre
    tronque d'un bord rendrait le premier et tairait le second.
    """
    chemin = _projet_a_deux_rushes(tmp_path)
    ecran = _jouer(_chaine_sur(chemin, tmp_path), ("enter",), banc)

    assert isinstance(ecran, EcranInventaireDuProjet), type(ecran).__name__
    assert ecran.arbre is not None, "l'ecran est reste en lecture"
    assert not ecran.en_lecture
    noms = {noeud.nom for noeud in ecran.arbre.tous()}
    assert {"a-premier", "z-second"} <= noms, sorted(noms)
    assert {"a-premier_25", "a-premier_12p5",
            "z-second_8", "z-second_50"} <= noms, sorted(noms)
    # Le poids est LU du coeur : les quatre tailles distinctes s'additionnent.
    assert ecran.arbre.poids_total == 11 + 101 + 1001 + 10001


def test_Suppr_DEPUIS_LE_PRODUIT_monte_le_point_de_jugement(tmp_path, banc):
    """La COUTURE complete : sept frappes, puis `Suppr`, et `E6-2` s'ouvre.

    C'est le second volet de `MQ-8`, et il est distinct du premier :
    l'inventaire peut tres bien s'ouvrir **sans** que son rappel de suppression
    soit injecte. Dans ce cas `Suppr` monte `EcranPasEncore` en nommant
    :data:`CE_QUI_MANQUE_A_LA_SUPPRESSION` -- l'absence se dit, mais la
    troisieme operation d'`EPIC11-ARB-89` (« sans laquelle les deux premieres
    sont une fuite ») n'existe toujours pas dans le produit.

    Le curseur est amene sur un **lot** par des `↓` reels, jamais par
    `arbre.viser(...)` : viser a la main sauterait precisement le clavier que
    ce banc existe pour mesurer. La cible n'est donc **pas** la premiere ligne
    de l'arbre -- un `Suppr` qui viserait toujours la racine resterait vert sur
    elle.
    """
    chemin = _projet_a_deux_rushes(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        await pilote.press(*JUSQU_AU_PALIER_PROJET, "enter")
        await pilote.pause()
        inventaire = pilote.app.screen
        assert isinstance(inventaire, EcranInventaireDuProjet), \
            type(inventaire).__name__
        for _ in range(len(inventaire.arbre)):
            courant = inventaire.arbre.courant
            if courant is not None and courant.nature == NATURE_LOT:
                break
            await pilote.press("down")
            await pilote.pause()
        vise = inventaire.arbre.courant
        await pilote.press("delete")
        await pilote.pause()
        return vise, pilote.app.screen

    vise, ecran = banc(chaine.app, scenario)
    assert vise is not None and vise.nature == NATURE_LOT, vise
    # Un lot n'est jamais une racine : la cible n'est donc pas en tete d'arbre.
    assert vise.profondeur > 0, vise
    assert not (isinstance(ecran, EcranPasEncore)
                and CE_QUI_MANQUE_A_LA_SUPPRESSION in str(
                    getattr(ecran, "ce_qui_manque", ""))), (
        "l'inventaire est ouvert mais son rappel de suppression n'est pas "
        "injecte : `Suppr` nomme ce qui manque au lieu de juger")
    assert isinstance(ecran, EcranSuppressionConfirmation), type(ecran).__name__
    assert vise.nom in str(ecran.plan.libelle) or vise.nom in str(
        ecran.plan.cible), (vise.nom, ecran.plan)


# ---------------------------------------------------------------------------
# Les deux AUTRES entrees -- elles gardent leur filet, et son echeance
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("descentes,entree", [
    (2, palier_projet.ENTREE_RECONSTRUCTION),
])
def test_les_DEUX_AUTRES_entrees_gardent_leur_filet_DATE(tmp_path, banc,
                                                         descentes, entree):
    """Non-regression : seule `ENTREE_MEDIAS` change de destination.

    La reconstruction n'a toujours **aucune porte vers un fichier** dans le
    produit, et le lot `MQ-A` lui a pose son echeance
    (`ChaineReelle.QUAND_LA_PORTE_VERS_UN_FICHIER`). Un aiguillage trop large
    -- « toute entree du palier ouvre l'inventaire » -- passerait le test de la
    porte et l'emporterait en silence.

    **`ENTREE_PROFIL` a quitte ce parametre le 2026-09-06** : elle a gagne son
    ecran (`palier_profil_defaut`, retour terrain d'Egan), donc elle ne tombe
    plus au filet. Le rang du **milieu**, que ce parametre couvrait, est repris
    par `test_porte_du_profil_par_defaut.py`, qui frappe precisement la
    deuxieme entree ; ici la cible reste en **queue**, et la tete est mesuree
    par le test de la porte ci-dessus.
    """
    chemin = _projet_a_deux_rushes(tmp_path)
    touches = tuple(["down"] * descentes + ["enter"])
    ecran = _jouer(_chaine_sur(chemin, tmp_path), touches, banc)

    assert isinstance(ecran, EcranPasEncore), type(ecran).__name__
    assert palier_projet.LIBELLES[entree] in str(ecran.ce_qui_manque)
    assert str(ecran.quand) == ChaineReelle.QUAND_LA_PORTE_VERS_UN_FICHIER


def test_les_cles_qui_ouvrent_l_inventaire_sont_un_ENSEMBLE_EXACT(tmp_path,
                                                                 banc):
    """`ENTREE_MEDIAS` et **elle seule** ouvre `E6-1`. Repli compris.

    **Le mutant qui a impose ce test** (`M23` de la campagne du 2026-09-06,
    survivant a vingt-deux autres) : le repli de la table de destinations,
    `destinations.get(issue.cle, filet)`, mute en
    `destinations.get(issue.cle, self.gestion_des_medias)`. Une entree que
    `palier_projet` declarerait demain **sans la cabler** ouvrirait alors
    l'inventaire du projet a la place de nommer son absence -- et aucun des
    seize tests de ce fichier ne le voyait, parce qu'aucun ne frappait une
    entree inconnue. Les trois entrees reelles sont toutes dans la table :
    c'est **ce qui n'etait pas observe** qui manquait, pas ce qui l'etait.

    La mesure est un **ensemble exact** et non trois assertions positives --
    meme patron que la branche par defaut de `ChaineReelle.entrer`, mesuree en
    ensemble exact par `test_atelier_pdf_menu.py`, et pour le meme motif : une
    branche mal placee qui emporterait une entree cablee est invisible a toute
    assertion prise entree par entree.

    L'entree inconnue ne se frappe pas au clavier -- le palier n'offre que ses
    trois entrees --, donc le rappel est appele directement. C'est la seule
    facon d'atteindre son repli, et un repli qu'on n'atteint pas est un repli
    qu'on ne mesure pas.
    """
    chemin = _projet_a_deux_rushes(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)
    # Trois entrees reelles, DISTINGUABLES, plus une quatrieme inconnue posee
    # en QUEUE : c'est le rang ou un repli fautif se cache.
    cles = [palier_projet.ENTREE_MEDIAS, palier_projet.ENTREE_PROFIL,
            palier_projet.ENTREE_RECONSTRUCTION, "entree-neuve-non-cablee"]

    async def scenario(pilote):
        await pilote.press(*JUSQU_AU_PALIER_PROJET)
        await pilote.pause()
        ouvrent = []
        for cle in cles:
            chaine.entrer_commande(Issue(cle, f"Libelle de {cle}"))
            await pilote.pause()
            ecran = pilote.app.screen
            if isinstance(ecran, EcranInventaireDuProjet):
                ouvrent.append(cle)
            elif cle == palier_projet.ENTREE_PROFIL:
                # Depuis le 2026-09-06, cette entree-la ouvre son propre ecran
                # plutot que le filet. Ce qui se mesure ici reste que ce n'est
                # **pas** l'inventaire : la porte du profil a son banc a elle.
                assert isinstance(ecran, EcranProfilParDefaut), type(
                    ecran).__name__
            else:
                assert isinstance(ecran, EcranPasEncore), (cle, type(ecran))
                assert str(ecran.quand) == \
                    ChaineReelle.QUAND_LA_PORTE_VERS_UN_FICHIER, cle
            pilote.app.action_remonter()
            await pilote.pause()
        return ouvrent

    ouvrent = banc(chaine.app, scenario)
    assert ouvrent == [palier_projet.ENTREE_MEDIAS], ouvrent


# ---------------------------------------------------------------------------
# Les QUATRE refus du coeur -- joues sur le DISQUE REEL
# ---------------------------------------------------------------------------

def _casser_le_dossier(chemin: Path):
    """`ProjetIntrouvable` : le dossier disparait sous les pieds."""
    import shutil
    shutil.rmtree(chemin)


def _casser_le_manifeste_absent(chemin: Path):
    """`ManifesteIntrouvable` : le `project.json` est efface."""
    (chemin / "project.json").unlink()


def _casser_le_manifeste_illisible(chemin: Path):
    """`ManifesteIllisible` : ce n'est plus du JSON."""
    (chemin / "project.json").write_text("{ ceci n'est pas du JSON",
                                         encoding="utf-8")


def _casser_le_manifeste_incoherent(chemin: Path):
    """`ManifesteIncoherent` : `rushes` n'est pas une liste."""
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = {"a-premier": {}}
    (chemin / "project.json").write_text(json.dumps(document),
                                         encoding="utf-8")


#: Les quatre refus, **dans l'ordre ou le coeur les leve**, et le geste qui
#: produit chacun sur le disque. La table est parcourue en entier : la cible
#: est donc jouee en tete, aux deux rangs du milieu, et en queue.
LES_QUATRE_REFUS = (
    (ProjetIntrouvable, _casser_le_dossier),
    (ManifesteIntrouvable, _casser_le_manifeste_absent),
    (ManifesteIllisible, _casser_le_manifeste_illisible),
    (ManifesteIncoherent, _casser_le_manifeste_incoherent),
)


@pytest.mark.parametrize("classe,casser", LES_QUATRE_REFUS,
                         ids=lambda v: getattr(v, "__name__", ""))
def test_un_refus_du_coeur_rend_un_ECRAN_et_jamais_une_trace_de_pile(
        tmp_path, banc, classe, casser):
    """Les quatre refus publies, joues sur le disque, du premier au dernier.

    **Ce que ce test mesurait avant le lot** : rien -- aucun module de `tui/`
    ne nommait ces exceptions, si bien qu'un manifeste illisible remontait
    jusqu'a `textual`, qui peint une trace de pile par-dessus l'interface.

    Le message voyage **verbatim** (`EPIC11-ARB-30` : « le code **et** la
    phrase viennent du coeur ; la TUI met en forme -- elle n'interprete pas,
    elle ne resume pas, elle ne requalifie pas »). On mesure donc une
    **sur-chaine exacte**, comme le fait deja le banc d'`EcranRefus`.
    """
    chemin = _projet_a_deux_rushes(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)
    ecran, lignes = _jouer(chaine, ("enter",), banc,
                           apres_le_palier=lambda: casser(chemin),
                           lire=lambda e: "\n".join(e.lignes())
                           if hasattr(e, "lignes") else "")

    assert isinstance(ecran, EcranRefus), type(ecran).__name__
    # Le refus que le coeur aurait leve, leve pour de vrai : la phrase de
    # l'ecran est celle-la, mot pour mot.
    from mixed_media_utility.project_inventory import inventorier_le_projet
    with pytest.raises(classe) as leve:
        inventorier_le_projet(chemin)
    assert ecran.message == str(leve.value)
    # Sur-chaine EXACTE du texte leve, mesuree sur le rendu de l'ecran et non
    # sur son seul attribut : c'est la que la TUI aurait pu resumer.
    assert str(leve.value) in lignes


@pytest.mark.parametrize("classe,casser", LES_QUATRE_REFUS,
                         ids=lambda v: getattr(v, "__name__", ""))
def test_le_refus_NOMME_le_refus_du_coeur_par_son_CODE(tmp_path, banc,
                                                       classe, casser):
    """Le code du refus est celui du coeur, pas une requalification de la TUI.

    Les quatre refus du coeur n'ont pas d'attribut `code` : ce sont des
    classes. Le code affiche est donc **derive de leur nom**, mecaniquement --
    une table serait une seconde redaction, qui perimerait en silence le jour
    ou un cinquieme refus serait publie.
    """
    from mixed_media_utility.tui.projet_inventaire import code_du_refus

    chemin = _projet_a_deux_rushes(tmp_path)
    ecran = _jouer(_chaine_sur(chemin, tmp_path), ("enter",), banc,
                   apres_le_palier=lambda: casser(chemin))

    assert ecran.code == code_du_refus(classe("peu importe"))
    # Le code NOMME ce refus-la, et pas un autre : la comparaison porte sur la
    # classe reellement levee, jamais sur une chaine ecrite a la main ici.
    assert classe.__name__.upper().startswith(ecran.code.split("_")[0]), (
        ecran.code, classe.__name__)


def test_le_code_du_refus_DISTINGUE_les_quatre_et_les_place_a_CHAQUE_BORD():
    """Les quatre codes sont distincts, et la derivation tient aux deux bords.

    **Le quatrieme point de la regle des fabriques**, applique a la table des
    refus : un `code_du_refus` qui rendrait toujours le premier refus connu, ou
    qui balaierait la table en sautant sa derniere entree, resterait vert tant
    que la cible est au milieu. Les quatre sont donc confrontees deux a deux,
    la tete (`ProjetIntrouvable`) et la queue (`ManifesteIncoherent`)
    comprises.
    """
    from mixed_media_utility.tui.projet_inventaire import code_du_refus

    codes = [code_du_refus(classe("peu importe"))
             for classe, _ in LES_QUATRE_REFUS]
    assert len(set(codes)) == 4, codes
    assert codes[0] == "PROJET_INTROUVABLE"
    assert codes[-1] == "MANIFESTE_INCOHERENT"
    assert all(code.isupper() and " " not in code for code in codes), codes


def test_un_CINQUIEME_refus_du_coeur_serait_pris_lui_aussi():
    """`InventaireError` est attrapee par sa BASE, jamais quatre fois.

    Un cablage qui listerait les quatre classes une a une laisserait passer le
    cinquieme refus publie -- et c'est exactement le mode de panne que la
    revue du 2026-08-31 a trouve sur les champs de ligne d'eau : une surface
    declaree que personne n'ecrit. La mesure porte sur le comportement, pas sur
    la lecture du code : un refus de synthese, inconnu du module de parcours,
    doit rendre un ecran.
    """
    from mixed_media_utility.tui import projet_inventaire as ppp

    class RefusInedit(InventaireError):
        """Un cinquieme refus, publie demain."""

    ecran = ppp.refus_de_l_inventaire(RefusInedit("le coeur dit non"))
    assert isinstance(ecran, EcranRefus)
    assert ecran.message == "le coeur dit non"
    assert ecran.code == "REFUS_INEDIT"


def test_l_ecran_de_refus_offre_AU_MOINS_DEUX_ISSUES_et_aucun_blocage_sec():
    """`EPIC11-ARB-89` : jamais une seule sortie, jamais un blocage sec.

    **Et jamais trois non plus** (`EPIC11-ARB-147`) : ces refus ne detruisent
    rien, donc leur fabriquer une issue de secours produirait « un ecran qui
    demande de choisir entre deux facons de ne rien faire ». Les deux sorties
    d'`EcranRefus` -- revenir aux ateliers, quitter -- sont celles d'un ecran
    **deja valide**, et c'est pourquoi ce lot n'en dessine aucun
    (`EPIC11-ARB-144`).
    """
    from mixed_media_utility.tui import projet_inventaire as ppp

    ecran = ppp.refus_de_l_inventaire(ProjetIntrouvable("rien a lire"))
    raccourcis = ecran.raccourcis
    assert "⏎" in raccourcis and "Q" in raccourcis, raccourcis
    assert hasattr(ecran, "on_key"), "l'ecran de refus n'a aucune touche"
