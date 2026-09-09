# -*- coding: utf-8 -*-
"""Les deux PORTES de media du palier Projet (lot H, 2026-09-07).

**Ce banc mesure un CABLAGE, pas un comportement d'ecran.** `EcranRushes`,
`EcranDeclaration` (`E2-1e`), `EcranRefusDeConflit` (`E2-1f`) et
`EcranRefusRelink` (`E2-1d`) ont chacun leur banc depuis la story 11.4 ; ce
qu'aucun d'eux ne peut voir est qu'ils soient atteignables depuis `E6-1`.
C'est le mode de panne `E9` de cet epic -- « un composant livre, teste, et
cable nulle part dans l'application est un composant que le produit n'a pas »
--, paye cinq fois, et c'est exactement ce qu'Egan a rencontre le 2026-09-06 :

    « Ajouter un media au projet depuis le disque : n'existe pas encore
    (normal ? ou non cable ?) »

Ce que la MESURE a repondu, et qui contredisait le brief du lot
----------------------------------------------------------------
Le brief annoncait, pour `Ctrl+A`, « le coeur existe, le dessin est a
decliner ». C'est **moins** que ce qui existait : le parcours d'ecran entier
etait la, du choix de fichier au compte rendu, en passant par le panneau
chiffre d'`EPIC11-ARB-4` et par le refus de conflit d'`EPIC11-ARB-232`. Il n'y
avait donc aucun dessin a decliner, et en decliner un aurait produit la
seconde redaction que ce depot paie chaque fois qu'il en fabrique une. Ce banc
mesure la porte, pas un second ecran.

**Ce banc joue l'APPLICATION DU PRODUIT sur les deux tests de bout en bout**
-- `chaine_du_produit()`, le point d'entree reel --, jamais une chaine
assemblee a la main : c'est cette assemblee manuelle qui a masque `E9` pendant
deux vagues.

Regle des fabriques, ses quatre points
---------------------------------------
Le projet de ce banc porte **trois rushes distinguables** -- trois cadences,
trois resolutions, trois cardinaux de frames --, et les tests de position
placent la cible **au milieu** (`m-milieu`) *et* **a chaque bord**
(`a-premier`, `z-dernier`). Un aiguillage qui rendrait « le premier rush
delie » reste vert sur une cible de tete ; un balayage tronque reste vert sur
une cible de milieu. Les deux modes de panne sont mesures.

Le drapeau que ce banc fait varier
-----------------------------------
`ascii_seul`, sur les deux motifs de refus des portes : « une garde qui ne fait
varier aucun de ses drapeaux ne mesure qu'un seul chemin » (`CLAUDE.md`,
2026-09-06). Un motif calibre en geometrie UTF-8 et coupe en repli ASCII est le
defaut exact de `coque.Palier.bandeau`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
for chemin in (str(_RACINE / "src"), str(_RACINE / "tests" / "unit")):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.tui import jetons, projet_inventaire as pi
from mixed_media_utility.tui import projet_medias as pm
from mixed_media_utility.tui import projets
from mixed_media_utility.tui.atelier_extraction import (BUT_AJOUTER,
                                                        BUT_RELINK,
                                                        EcranRushes,
                                                        ZONE_EXPLORATEUR,
                                                        ZONE_LISTE)
from mixed_media_utility.tui.atelier_extraction_ecriture import (
    ChaineReelle, chaine_du_produit)
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui import rushes as modele_des_rushes

#: Le regime de la recette d'Egan, frappe par frappe : `⏎` ouvre le projet le
#: plus recent, `↓↓↓↓` descend jusqu'a l'entree *Projet*, `⏎` y entre, puis
#: `⏎` ouvre *Gestion des medias*, qui est la PREMIERE entree du palier.
JUSQU_A_L_INVENTAIRE = ("enter", "down", "down", "down", "down", "enter",
                        "enter")

#: Les trois rushes, tous distinguables, l'absent designe par le test.
RUSHES = (
    ("a-premier", 25.0, 1920, 1080, 6300),
    ("m-milieu", 50.0, 1280, 720, 37900),
    ("z-dernier", 24.0, 4096, 2160, 3012),
)


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def _entree_de_rush(rush_id, fps, largeur, hauteur, chemin) -> dict:
    from fractions import Fraction

    exacte = Fraction(fps).limit_denominator(1000)
    return {"rush_id": rush_id, "source_name": f"{rush_id}.mov",
            "fps_source": fps,
            "fps_source_exact": f"{exacte.numerator}/{exacte.denominator}",
            "resolution_source": {"width": largeur, "height": hauteur},
            "source_metadata_absent_fields": [],
            "source_path": chemin,
            "source_start_timecode": "00:00:00:00"}


def _projet(tmp_path, absents=()) -> Path:
    """Un projet REEL, ses trois rushes, ceux qu'on nomme rendus introuvables.

    Les rushes presents pointent vers des fichiers **qui existent** ; les
    absents vers un dossier qui n'existe pas. C'est ce que
    `relink.statut_de_liaison` lit pour distinguer `lie` d'`absent`, et un
    banc qui pointerait tout vers le neant ne distinguerait plus les deux
    familles -- donc ne verrait pas un refus rendu sur la mauvaise.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    sources = tmp_path / "rushes"
    sources.mkdir(exist_ok=True)
    entrees, lots = [], []
    for rush_id, fps, largeur, hauteur, frames in RUSHES:
        if rush_id in absents:
            source = tmp_path / "volume-debranche" / f"{rush_id}.mov"
        else:
            source = sources / f"{rush_id}.mov"
            source.write_bytes(b"\x00" * 32)
        entrees.append(_entree_de_rush(rush_id, fps, largeur, hauteur,
                                       str(source)))
        lots.append({"lot_id": f"{rush_id}_lot", "rush_id": rush_id,
                     "state": "extraction", "source_frame_count": frames,
                     "source_frame_count_is_exact": True})
    manifeste = chemin / "project.json"
    document = json.loads(manifeste.read_text(encoding="utf-8"))
    document["rushes"] = entrees
    document["lots"] = lots
    manifeste.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return chemin


def _app(ecran=None, **kwargs) -> CoqueTui:
    """Une coque a UN palier temoin, sur laquelle les portes empilent."""
    paliers = [PalierTemoin("Projet", "q quitter")]
    if ecran is not None:
        paliers.append(ecran)
    return CoqueTui(paliers=paliers, contexte=Contexte(projet="projet_demo"),
                    **kwargs)


def _ouvrir(app, ouvreur, banc, **reste):
    """Monter l'application, appeler la porte, rendre l'ecran du dessus."""
    resultats = {}

    async def tour(pilote):
        resultats["rendu"] = ouvreur(pilote.app, **reste)
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, tour)
    return resultats["rendu"], ecran


#: Les rappels que les deux portes injectent dans `EcranRushes`. Les doubler
#: est ce qui rend ce banc mesurable **sans ffmpeg et sans video** : ce qu'il
#: mesure est le cablage, pas le coeur de la declaration, qui a le sien.
def _cablage_double(traces: dict) -> dict:
    def preparer(dossier, cible, **reste):
        traces.setdefault("preparees", []).append((Path(dossier), Path(cible),
                                                   reste))
        return object()

    def ecrire(preparee):
        traces.setdefault("ecrites", []).append(preparee)
        return "rush-neuf"

    def cadences(app, dossier, rush_id):
        traces.setdefault("cadences", []).append((Path(dossier), rush_id))

    return {"preparer": preparer, "ecrire": ecrire, "cadences": cadences}


# ---------------------------------------------------------------------------
# `Ctrl+A` -- la porte de l'AJOUT
# ---------------------------------------------------------------------------

def test_la_porte_de_l_AJOUT_monte_E2_1_explorateur_OUVERT(tmp_path, banc):
    """La touche dit « depuis le disque » : l'ecran rendu demande un chemin.

    Laisser l'operateur sur la liste des rushes lui ferait deviner `Tab`, ce
    qui est le defaut `MQ-1` deja paye sur cet ecran-la. Le mode est celui des
    FICHIERS : on designe une video, pas un dossier.
    """
    chemin = _projet(tmp_path)
    traces: dict = {}
    rendu, ecran = _ouvrir(_app(), pm.ouvrir_l_ajout_de_media, banc,
                           dossier_projet=chemin, **_cablage_double(traces))

    assert rendu is True
    assert isinstance(ecran, EcranRushes), type(ecran).__name__
    assert ecran.zone == ZONE_EXPLORATEUR, ecran.zone
    assert ecran.but == BUT_AJOUTER, ecran.but
    assert ecran.mode == modele_des_rushes.MODE_DESIGNER, ecran.mode
    assert ecran.explorateur.montrer_fichiers is True
    # Rien n'a ete prepare ni ecrit : ouvrir une porte n'ecrit pas
    # (`EPIC11-ARB-4`).
    assert traces == {}


def test_la_porte_de_l_AJOUT_porte_le_VRAI_projet_et_ses_TROIS_rushes(
        tmp_path, banc):
    """Un cablage qui monterait `EcranRushes(Path("."))` passerait le test
    precedent : l'ecran existe, il est du bon type, et sa liste est vide.

    Les **trois** rushes sont comptes, la tete et la queue comprises : une
    liste tronquee d'un bord rendrait celui du milieu et tairait les autres.
    """
    chemin = _projet(tmp_path)
    traces: dict = {}
    _rendu, ecran = _ouvrir(_app(), pm.ouvrir_l_ajout_de_media, banc,
                            dossier_projet=chemin, **_cablage_double(traces))

    assert ecran.dossier == chemin, ecran.dossier
    noms = [r.rush_id for r in ecran.liste.rushes]
    assert noms == [r[0] for r in RUSHES], noms


def test_les_DEUX_temps_de_la_declaration_sont_INJECTES_et_portent_le_dossier(
        tmp_path, banc):
    """Finding `K3` : le rappel accepte doit avoir son injecteur.

    Le dossier est **lie a la porte** : `EcranRushes` appelle `preparer(cible)`
    sans dossier, et le relire ailleurs ferait dependre l'ecriture d'un menu
    que cet ecran-ci n'a pas. Ce banc mesure que le dossier qui arrive au
    coeur est bien celui du projet ouvert, et pas `Path.cwd()`.

    `force_distinct` est **transporte** : c'est la deuxieme issue de `E2-1f`
    (`EPIC11-ARB-232`), et une porte qui l'avalerait rendrait cette issue
    decorative.
    """
    chemin = _projet(tmp_path)
    traces: dict = {}
    _rendu, ecran = _ouvrir(_app(), pm.ouvrir_l_ajout_de_media, banc,
                            dossier_projet=chemin, **_cablage_double(traces))
    video = tmp_path / "rushes" / "a-premier.mov"

    assert ecran._preparer is not None and ecran._ecrire is not None
    ecran._preparer(video)
    ecran._preparer(video, force_distinct=True)
    assert traces["preparees"] == [(chemin, video, {}),
                                   (chemin, video, {"force_distinct": True})]
    assert ecran._ecrire(object()) == "rush-neuf"


def test_le_rappel_d_EXTRACTION_est_injecte_lui_aussi(tmp_path, banc):
    """`⏎` sur un rush lie doit extraire ICI comme il extrait dans l'atelier.

    Une touche qui marche la ou l'on n'est pas ne marche pas (finding `I8`,
    pris par le bout le plus couteux) : sans ce rappel, l'ecran atteint depuis
    l'inventaire aurait repondu « pas encore » a un `⏎` que l'atelier
    Extraction honore.

    La cible est le rush de **queue**, jamais celui sous le curseur au
    montage : un cablage qui aurait fige le premier resterait vert sur lui.
    """
    chemin = _projet(tmp_path)
    traces: dict = {}
    _rendu, ecran = _ouvrir(_app(), pm.ouvrir_l_ajout_de_media, banc,
                            dossier_projet=chemin, **_cablage_double(traces))

    assert ecran._extraire is not None
    ecran._extraire("z-dernier")
    assert traces["cadences"] == [(chemin, "z-dernier")]


# ---------------------------------------------------------------------------
# `Ctrl+L` -- la porte du RELINK
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cible", ["a-premier", "m-milieu", "z-dernier"])
def test_la_porte_du_RELINK_vise_le_rush_DEMANDE_a_CHAQUE_place(
        tmp_path, banc, cible):
    """Le curseur est pose sur la cible AVANT que l'explorateur n'ouvre.

    C'est structurel : `EcranRushes._ouvrir_l_explorateur` memorise sa cible en
    demandant `liste.rush_a_relinker()`, c'est-a-dire **le rush sous le
    curseur**. Sans le `viser`, un projet a trois rushes absents relinkerait le
    premier de la liste au lieu de celui que l'inventaire designe -- le mode de
    panne de `_find_lot` en 5.7.

    Les trois places sont jouees : la tete demasque un cablage fige sur le
    premier, la queue un balayage tronque, le milieu un `find` fautif.
    """
    chemin = _projet(tmp_path, absents=[r[0] for r in RUSHES])
    traces: dict = {}
    rendu, ecran = _ouvrir(_app(), pm.ouvrir_le_relink_du_rush, banc,
                           dossier_projet=chemin, rush_id=cible,
                           **_cablage_double(traces))

    assert rendu is True
    assert isinstance(ecran, EcranRushes), type(ecran).__name__
    assert ecran.zone == ZONE_EXPLORATEUR, ecran.zone
    assert ecran.but == BUT_RELINK, ecran.but
    assert ecran.mode == modele_des_rushes.MODE_RETROUVER, ecran.mode
    assert ecran.explorateur.montrer_fichiers is False
    assert ecran.liste.courant.rush_id == cible
    # Le rush que le geste traitera, memorise a l'ouverture et jamais relu.
    assert ecran._vise == cible, ecran._vise
    assert traces == {}


def test_la_porte_du_RELINK_DIT_qu_un_rush_est_deja_lie(tmp_path, banc):
    """`EPIC11-ARB-89` / `-258` : un refus se dit, et il n'est pas un mur.

    L'ecran monte **quand meme**, sur sa liste : c'est justement la que
    l'operateur corrige son tir. Le renvoyer au palier lui ferait recommencer
    la navigation.

    La cible est en **queue**, et deux rushes absents l'encadrent : un cablage
    qui aurait teste « le premier rush de la liste est-il lie » aurait rendu le
    refus sur la mauvaise famille.
    """
    chemin = _projet(tmp_path, absents=("a-premier", "m-milieu"))
    traces: dict = {}
    rendu, ecran = _ouvrir(_app(), pm.ouvrir_le_relink_du_rush, banc,
                           dossier_projet=chemin, rush_id="z-dernier",
                           **_cablage_double(traces))

    assert rendu is True
    assert isinstance(ecran, EcranRushes), type(ecran).__name__
    assert ecran.zone == ZONE_LISTE, ecran.zone
    assert ecran.but is None, ecran.but
    assert ecran._etat_a_dire == pm.MOTIF_RUSH_DEJA_LIE.format(
        rush_id="z-dernier")
    assert ecran.liste.courant.rush_id == "z-dernier"


def test_la_porte_du_RELINK_DIT_qu_un_rush_est_HORS_manifeste(tmp_path, banc):
    """Un noeud d'ORPHELIN de `E6-1` porte la nature `rush` et n'a **aucune**
    entree `rushes[]` : `ListeDesRushes.viser` leve alors `KeyError`.

    Ce n'est pas un cas de laboratoire -- c'est ce que l'arbre greffe pour tout
    rush trouve sur le disque et absent du manifeste. Le refus dit ce qui
    MARCHE : c'est `Ctrl+A` qui declare.
    """
    chemin = _projet(tmp_path, absents=("m-milieu",))
    traces: dict = {}
    rendu, ecran = _ouvrir(_app(), pm.ouvrir_le_relink_du_rush, banc,
                           dossier_projet=chemin, rush_id="jamais-declare",
                           **_cablage_double(traces))

    assert rendu is True
    assert ecran.zone == ZONE_LISTE, ecran.zone
    assert ecran._etat_a_dire == pm.MOTIF_RUSH_HORS_MANIFESTE.format(
        rush_id="jamais-declare")
    # La liste n'a pas bouge : aucun curseur pose au hasard.
    assert ecran.liste.curseur == 0


def test_les_motifs_des_portes_TIENNENT_la_zone_utile_dans_les_DEUX_modes():
    """`EPIC11-ARB-21` : rien ne se coupe au plancher de 80 colonnes.

    Le drapeau `ascii_seul` **varie**, et il change quelque chose : les deux
    motifs portent un `é` et un `à` qui se replient, et le second porte un
    tiret. Un motif calibre dans une seule geometrie est le defaut de
    `coque.Palier.bandeau`, paye le 2026-09-06 sur onze ecrans.

    L'identifiant employe est realiste et long : un rush nomme sur dix
    caracteres, comme ceux du manifeste de ce banc.
    """
    utile = jetons.largeur_utile(80)
    motifs = [pm.MOTIF_RUSH_DEJA_LIE.format(rush_id="plan-04_25"),
              pm.MOTIF_RUSH_HORS_MANIFESTE.format(rush_id="plan-04_25")]
    for ascii_seul in (False, True):
        for motif in motifs:
            rendu = jetons.replier_ascii(motif) if ascii_seul else motif
            assert jetons.colonnes(rendu) <= utile, (motif, ascii_seul,
                                                     jetons.colonnes(rendu))


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_refus_de_la_porte_SE_REPLIE_comme_les_autres(tmp_path, banc,
                                                         ascii_seul):
    """La regle des drapeaux : le mode varie, et il change quelque chose.

    **Le defaut que ce banc ferme, et il etait present** : `EcranRushes.etat()`
    rend `_etat_a_dire` **tel quel** -- chacun de ses producteurs ayant deja
    replie. Une porte qui poserait sa phrase brute serait la seule ligne d'etat
    de cet ecran a ne pas se replier, et l'ecart ne se verrait qu'en `--ascii`.
    C'est le defaut de `coque.Palier.bandeau`, paye le 2026-09-06 sur onze
    ecrans sur quatorze.

    En `--ascii`, la ligne rendue ne doit porter **aucun** caractere hors ASCII
    -- ni le `é` de « déclare », ni le `à` de « là ».
    """
    chemin = _projet(tmp_path, absents=("a-premier", "m-milieu"))
    traces: dict = {}
    _rendu, ecran = _ouvrir(_app(ascii_seul=ascii_seul),
                            pm.ouvrir_le_relink_du_rush, banc,
                            dossier_projet=chemin, rush_id="z-dernier",
                            **_cablage_double(traces))

    rendu = ecran.etat()
    assert rendu, "la porte n'a rien dit"
    assert rendu.isascii() is ascii_seul, (ascii_seul, rendu)
    assert jetons.colonnes(rendu) <= jetons.largeur_utile(80), rendu


def test_les_DEUX_portes_rendent_FAUX_hors_application():
    """Aucune application montee -> faux, et l'appelant sait que rien n'a bouge.

    C'est la premiere des sorties d'`EPIC11-ARB-89`, et elle est mesuree comme
    les autres : une porte qui leverait ici ferait tomber l'inventaire sur une
    touche annoncee.

    L'appelant est un **ecran reel non monte**, jamais un objet nu : `textual`
    fait de `Screen.app` une propriete qui leve `NoActiveAppError` -- et c'est
    ce refus-la que `_application_montee` absorbe. Un `object()` leverait un
    `AttributeError`, c'est-a-dire une autre panne, et le banc mesurerait alors
    autre chose que ce qu'il croit.
    """
    orphelin = PalierTemoin("Projet", "q quitter")
    assert pm.ouvrir_l_ajout_de_media(orphelin, Path("/nulle-part")) is False
    assert pm.ouvrir_le_relink_du_rush(orphelin, Path("/nulle-part"),
                                       "rush") is False


# ---------------------------------------------------------------------------
# Le PRODUIT -- de `mmu-tui` a l'ecran, sans chaine assemblee a la main
# ---------------------------------------------------------------------------

def _chaine_sur(chemin: Path, tmp_path) -> ChaineReelle:
    recents = projets.Recents(tmp_path / "reglages" / "recents-v1.json")
    recents.noter_ouverture(chemin)
    return chaine_du_produit(recents=recents)


def test_le_PRODUIT_ouvre_l_AJOUT_par_Ctrl_A_depuis_l_inventaire(
        tmp_path, banc):
    """Huit frappes et un `Ctrl+A` : l'explorateur de designation s'ouvre.

    **C'est le seul verdict qui distingue « l'ecran est ecrit » de « le produit
    a l'ecran »**, et c'est exactement ce qu'Egan a mesure a la main le
    2026-09-06 en trouvant un « pas encore ». La mesure porte sur le TYPE de
    l'ecran monte : un `EcranPasEncore` qui citerait l'ajout dans sa phrase
    passerait un grep, et c'est ce texte-la qui a masque `MQ-4` et `MQ-5`.
    """
    from mixed_media_utility.tui.coque import EcranPasEncore

    chemin = _projet(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        await pilote.press(*JUSQU_A_L_INVENTAIRE)
        await pilote.pause()
        inventaire = pilote.app.screen
        await pilote.press("ctrl+a")
        await pilote.pause()
        return inventaire, pilote.app.screen

    inventaire, ecran = banc(chaine.app, scenario)

    assert isinstance(inventaire, pi.EcranInventaireDuProjet), type(
        inventaire).__name__
    assert not isinstance(ecran, EcranPasEncore), (
        "la porte de l'ajout n'est pas posee : `Ctrl+A` tombe encore dans le "
        "filet de `EcranInventaireDuProjet._pas_encore`")
    assert isinstance(ecran, EcranRushes), type(ecran).__name__
    assert ecran.zone == ZONE_EXPLORATEUR and ecran.but == BUT_AJOUTER
    assert ecran.dossier == chemin, ecran.dossier


def test_le_PRODUIT_ouvre_le_RELINK_par_Ctrl_L_sur_le_rush_DESIGNE(
        tmp_path, banc):
    """Meme parcours, `Ctrl+L` sur un rush declare absent.

    La cible est le rush du **milieu**, et l'inventaire est parcouru a la
    fleche jusqu'a lui : un cablage qui aurait relinke « le premier rush
    delie » resterait vert si la cible etait en tete. Les trois rushes sont
    absents, donc les trois sont des cibles legitimes et seule celle que
    l'arbre designe doit passer.
    """
    from mixed_media_utility.tui.coque import EcranPasEncore

    chemin = _projet(tmp_path, absents=[r[0] for r in RUSHES])
    chaine = _chaine_sur(chemin, tmp_path)

    async def scenario(pilote):
        await pilote.press(*JUSQU_A_L_INVENTAIRE)
        await pilote.pause()
        inventaire = pilote.app.screen
        inventaire.arbre.viser("m-milieu")
        await pilote.press("ctrl+l")
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(chaine.app, scenario)

    assert not isinstance(ecran, EcranPasEncore), (
        "la porte du relink n'est pas posee : `Ctrl+L` tombe encore dans le "
        "filet de `EcranInventaireDuProjet._pas_encore`")
    assert isinstance(ecran, EcranRushes), type(ecran).__name__
    assert ecran.but == BUT_RELINK, ecran.but
    assert ecran._vise == "m-milieu", ecran._vise
