# -*- coding: utf-8 -*-
"""Couche 3 de la revue de la vague 2 : le PARCOURS, joue au clavier.

Ces bancs ne mesurent aucune fonction prise a part : ils montent l'inventaire
par le point d'entree du PRODUIT (`ouvrir_l_inventaire_du_projet`), sur un
projet REEL, et frappent les touches qu'Egan frappe -- `→`, `↓`, `Espace`,
`Suppr`. C'est la seule mesure qui reponde a la question des constats de
terrain du 2026-09-06 : « planches (l'ensemble) [...] n'est pas
selectionnable », « masters (l'ensemble des masters d'un lot) n'est pas
selectionnable », « retirer un jeu de frames extraites seul : non cable ou
inexistant ».

**Deux d'entre eux ont ete ecrits ROUGES a dessein** (finding `C3-1`) et sont
VERTS depuis le correctif `05770fe7f`. Le defaut qu'ils portaient : le porteur
`_CablageDeLaSuppression` gardait l'arbre qu'il avait a la construction, et
`EcranInventaireDuProjet.reprendre` en pose un AUTRE des le premier montage.
`lot_ancetre` cherchait alors le noeud courant dans un arbre qui ne le contient
plus, rendait `None`, et TOUTE cible fine -- groupe compris -- se voyait
refuser. Le porteur lit desormais `self.ecran.arbre` a chaque frappe.

> **Ce paragraphe a ete corrige le 2026-09-07**, a la relecture du correctif.
> Il disait « sont ROUGES a dessein » au present, et le fichier entier rendait
> 7 verts : la prose declarait ouvert ce que son propre commit avait ferme
> quelques minutes plus tot. C'est le defaut que ce depot paie « le jour ou une
> prose exacte devient fausse deux commits plus tard », ici en zero commit.

Le troisieme banc est la CONTRE-MESURE : le meme parcours, le seul
remplacement d'arbre neutralise, va jusqu'au disque. C'est lui qui isole la
cause plutot que de la supposer.

Le quatrieme mesure la RACINE sans passer par une touche, et le cinquieme la
FAMILLE : le porteur garde une seconde copie du dossier de projet, et rien ne
disait qu'elle reste celle de l'ecran.
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
from mixed_media_utility.tui import projet_inventaire as pi
from mixed_media_utility.tui import projet_suppression as ps
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.execution import EcranRefus


# ---------------------------------------------------------------------------
# Fabrique : un projet REEL, aux membres DISTINGUABLES et de rangs differents.
# ---------------------------------------------------------------------------

#: Trois planches de rangs 1, 2, 3 -- distinguables par le nom ET par le rang,
#: parce qu'un remplissage uniforme cacherait une permutation (regle des
#: fabriques, point 1). Les octets sont premiers a l'oeil : un poids agrege qui
#: prendrait le premier fichier au lieu de la somme rendrait un nombre
#: plausible sur des tailles egales.
PLANCHES = [("planches/p_plan-04_12p5_L_2f-aaa.pdf", 1, 11),
            ("planches/p_plan-04_12p5_L_2f-aaa_v2.pdf", 2, 22),
            ("planches/p_plan-04_12p5_L_2f-aaa_v3.pdf", 3, 33)]
MASTERS = [("outputs/plan-04_12p5_mmu_prores_hq.mov", "prores_hq", 4004),
           ("outputs/plan-04_12p5_mmu_dnxhr_hqx.mov", "dnxhr_hqx", 5005)]
FRAMES = [("extract-frames/plan-04_12p5/f0.tiff", 101),
          ("extract-frames/plan-04_12p5/f1.tiff", 202)]


def _projet(tmp_path: Path) -> Path:
    """Un lot qui porte les TROIS natures de groupe visees par les constats."""
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "plan-04"}]
    document["lots"] = [{
        "lot_id": "plan-04_12p5", "rush_id": "plan-04",
        "frames_dir": "extract-frames/plan-04_12p5",
        # `profile_id` et non `profile` : c'est la cle que le coeur LIT
        # (`_masters_declares`), et une fixture qui se trompe de cle mesure la
        # fixture -- le coeur refuse alors « aucun master au profil ... ».
        "encoded_masters": [{"path": p, "profile_id": profil}
                            for p, profil, _ in MASTERS],
        # `version_rank` par entree : sans lui, le coeur lit rang 1 pour toutes
        # et UNE cible emporte la famille entiere.
        "sheets_pdfs": [{"path": p, "version_rank": r} for p, r, _ in PLANCHES],
        "sheets_version_watermark": 3,
    }]
    (chemin / "project.json").write_text(json.dumps(document), encoding="utf-8")
    for relatif, octets in ([(p, o) for p, _, o in PLANCHES]
                            + [(p, o) for p, _, o in MASTERS] + FRAMES):
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)
    return chemin


def _tout_deplier_au_clavier(inventaire) -> None:
    """`→` puis `↓` sur chaque ligne, plusieurs passes, comme un operateur.

    Deplier par `noeud.deplie = True` mesurerait l'arbre ; ici on mesure la
    TOUCHE, qui est ce que le constat met en cause.
    """
    for _ in range(6):
        for _ in range(40):
            inventaire.traiter("up")
        for _ in range(len(inventaire.arbre.lignes_visibles())):
            inventaire.traiter("right")
            inventaire.traiter("down")
    for _ in range(60):
        inventaire.traiter("up")


def _viser_au_clavier(inventaire, fragment: str) -> str:
    """Descendre jusqu'a la premiere ligne qui porte `fragment`. Rend son nom."""
    noms = [noeud.nom for noeud in inventaire.arbre.lignes_visibles()]
    rangs = [rang for rang, nom in enumerate(noms) if fragment in nom]
    assert rangs, f"aucune ligne ne porte {fragment!r} : {noms}"
    for _ in range(rangs[0]):
        inventaire.traiter("down")
    return inventaire.arbre.courant.nom


def _parcours(banc, chemin: Path, fragment: str, jusqu_au_disque: bool):
    """Monter l'inventaire du PRODUIT et jouer le parcours jusqu'au bout."""
    socle = PalierTemoin("Projet", "q quitter")
    app = CoqueTui(paliers=[socle], contexte=Contexte(projet="projet_demo"))
    vu: dict[str, object] = {}

    async def tour(pilote):
        pi.ouvrir_l_inventaire_du_projet(socle, chemin)
        await pilote.pause()
        inventaire = pilote.app.screen
        _tout_deplier_au_clavier(inventaire)
        vu["ligne"] = _viser_au_clavier(inventaire, fragment)
        vu["dessin_avant"] = inventaire.arbre.ligne(inventaire.arbre.curseur)
        inventaire.traiter("space", " ")
        vu["coche"] = inventaire.arbre.courant.coche
        vu["dessin_apres"] = inventaire.arbre.ligne(inventaire.arbre.curseur)
        vu["message"] = inventaire._message
        # Le curseur part AILLEURS : la selection cochee doit primer
        # (`EPIC11-ARB-257`), et sans ce deplacement le banc ne saurait pas
        # laquelle des deux lectures il mesure.
        inventaire.traiter("down")
        inventaire.traiter("delete")
        await pilote.pause()
        vu["ecran"] = pilote.app.screen
        vu["classe"] = type(pilote.app.screen).__name__
        vu["code"] = getattr(pilote.app.screen, "code", None)
        if not jusqu_au_disque:
            return vu
        ecran = pilote.app.screen
        if not isinstance(ecran, ps.EcranSuppressionConfirmation):
            return vu
        cles = [issue.cle for issue in ecran.choix.issues]
        rang = cles.index(ps.CLE_SUPPRIMER)
        while ecran.choix.curseur != rang:
            ecran.traiter("down" if ecran.choix.curseur < rang else "up")
        ecran.traiter("enter")
        # **On attend la CONDITION, jamais un compte de tours.** Un `range(6)`
        # de `pause()` mesure la vitesse du conteneur, pas l'avancement du
        # produit : sous charge -- trois agents sur la machine, ce que ce depot
        # a mesure deux fois --, la suppression qui detruit pour de vrai n'est
        # pas conclue quand le banc lit l'ecran, et le banc rougit sans qu'une
        # ligne de code ait bouge. Signale par le lot A de la fermeture de la
        # vague 2, qui l'a paye sur son propre banc.
        #
        # La borne reste la pour qu'un produit reellement bloque echoue au lieu
        # de suspendre la suite entiere -- une attente non bornee est le defaut
        # symetrique.
        #
        # **Les DEUX ecrans transitoires sont nommes, et la premiere redaction
        # n'en nommait qu'un.** Attendre « ne plus etre la confirmation »
        # rendait la main sur `EcranSuppressionEnCours`, c'est-a-dire AVANT que
        # le disque ait bouge : trois rouges immediats. Une condition trop
        # faible n'est pas plus sure qu'un compte fixe -- elle est juste fausse
        # plus vite, ce qui est la seule bonne nouvelle de l'affaire.
        transitoires = (ps.EcranSuppressionConfirmation,
                        ps.EcranSuppressionEnCours)
        for _ in range(200):
            if not isinstance(pilote.app.screen, transitoires):
                break
            await pilote.pause()
        vu["final"] = type(pilote.app.screen).__name__
        return vu

    return banc(app, tour)


# ---------------------------------------------------------------------------
# `C3-1` -- ce que le clavier rend AUJOURD'HUI, sur le cablage du produit.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fragment,constat", [
    ("planches —", "l. 17 : l'ensemble des planches"),
    ("masters —", "l. 23 : l'ensemble des masters d'un lot"),
    ("frames —", "l. 16 : le jeu de frames extraites seul"),
])
def test_C3_1_le_parcours_CLAVIER_atteint_la_confirmation_sur_les_trois_constats(
        tmp_path, banc, fragment, constat):
    """Les trois constats du 2026-09-06, joues au clavier. VERT depuis `05770fe7f`.

    La case se dessine et `Espace` la remplit -- cette moitie-la etait deja
    livree et ce banc l'assert aussi, pour que la regression inverse se voie.
    Ce qui manquait etait la SUITE : `Suppr` montait un ecran de REFUS au lieu
    du point de jugement `E6-2`, parce que `lot_ancetre` interrogeait un arbre
    perime.

    **Ecrit rouge, il est le frontiere NEGATIVE du correctif**, et c'est mesure
    plutot que suppose : le back-pointeur `cablage.ecran = ecran` retire de
    `ouvrir_l_inventaire_du_projet`, les trois parametrages de ce banc meurent
    (mutant `C3-1-R1`, 2026-09-07 -- 7 rouges sur 7 dans ce fichier). Sans lui
    le porteur retomberait sur son arbre de construction, en silence.
    """
    chemin = _projet(tmp_path)
    vu = _parcours(banc, chemin, fragment, jusqu_au_disque=False)

    assert "[" in vu["dessin_avant"], (
        f"{constat}: la ligne ne porte aucune case a cocher "
        f"({vu['dessin_avant']!r})")
    assert vu["coche"] is True, f"{constat}: Espace n'a pas coche la ligne"
    assert not isinstance(vu["ecran"], EcranRefus), (
        f"{constat}: Suppr rend un REFUS ({vu['code']}) la ou le produit "
        f"annonce pouvoir supprimer -- ligne visee {vu['ligne']!r}")
    assert isinstance(vu["ecran"], ps.EcranSuppressionConfirmation), vu["classe"]


# ---------------------------------------------------------------------------
# La CONTRE-MESURE : le meme parcours, le seul remplacement d'arbre neutralise.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fragment,restants", [
    ("planches —", "planches"),
    ("masters —", "outputs"),
    ("frames —", "extract-frames"),
])
def test_la_CONTRE_MESURE_isole_la_cause_le_parcours_va_jusqu_au_DISQUE(
        tmp_path, banc, monkeypatch, fragment, restants):
    """Le parcours entier, `reprendre` NEUTRALISE -- et il reste utile apres.

    **A l'origine c'etait une contre-mesure de diagnostic** : sans elle, `C3-1`
    pouvait s'expliquer par dix causes ; avec elle il n'en restait qu'une, le
    meme parcours aboutissant des lors que l'arbre n'etait plus remplace.

    **Depuis le correctif il mesure autre chose, et c'est pour ca qu'il reste**
    : le chemin ou aucun remplacement n'a lieu. Le test jumeau ci-dessus joue
    le produit reel, ou `reprendre` repose un arbre a chaque montage ; les deux
    ensemble font varier le drapeau « l'arbre a-t-il ete remplace », dans les
    deux sens, sur un cas ou ca changeait tout. Un correctif qui n'aurait
    marche que dans un des deux regimes se verrait.
    """
    monkeypatch.setattr(pi.EcranInventaireDuProjet, "reprendre",
                        lambda self: None)
    chemin = _projet(tmp_path)
    vu = _parcours(banc, chemin, fragment, jusqu_au_disque=True)

    assert isinstance(vu["ecran"], ps.EcranSuppressionConfirmation), vu["classe"]
    assert vu["final"] in ("EcranReussiteDeSuppression",
                           "EcranResultatDeSuppression"), vu["final"]
    dossier = chemin / restants
    presents = sorted(f.name for f in dossier.rglob("*") if f.is_file()) \
        if dossier.exists() else []
    assert presents == [], (
        f"le groupe {fragment!r} devait partir en entier, il reste {presents}")


def test_le_porteur_de_la_suppression_LIT_l_arbre_COURANT_de_l_ecran(
        tmp_path, banc):
    """`C3-1` par sa racine, sans passer par une touche.

    **Ce test a change d'enonce avec le correctif, et la nuance porte.** Sa
    premiere redaction -- celle de la couche 3 qui a trouve le defaut --
    exigeait `ecran.arbre is porteur.arbre`, c'est-a-dire que les deux objets
    soient LE MEME. C'etait la mesure du mecanisme soupconne, pas de la
    propriete voulue : le correctif retenu ne synchronise pas l'attribut du
    porteur, il lui fait **lire l'arbre de l'ecran a chaque frappe**. Exiger
    l'identite des attributs aurait interdit le correctif le plus robuste des
    deux -- une synchronisation redevient perimee au remplacement suivant, une
    lecture au moment de la frappe ne le peut pas.

    Ce qui est mesure ici est donc la propriete elle-meme : **quel arbre le
    porteur emploie**. On remplace l'arbre de l'ecran APRES le montage par un
    arbre reconnaissable, et on verifie que c'est celui-la que la suppression
    lit -- ce qu'aucune comparaison d'attributs ne dirait.
    """
    chemin = _projet(tmp_path)
    socle = PalierTemoin("Projet", "q quitter")
    app = CoqueTui(paliers=[socle], contexte=Contexte(projet="projet_demo"))
    vu: dict[str, object] = {}

    async def tour(pilote):
        pi.ouvrir_l_inventaire_du_projet(socle, chemin)
        await pilote.pause()
        inventaire = pilote.app.screen
        porteur = inventaire._supprimer.__self__

        # Un arbre RECONNAISSABLE, pose apres coup : c'est le geste que
        # `reprendre` fait a chaque montage, joue explicitement pour que la
        # mesure ne depende pas de l'ordre des montages.
        temoin = pi.ArbreDuProjet(racines=[], titre="TEMOIN")
        inventaire.arbre = temoin

        vu["lu_par_le_porteur"] = _arbre_lu_par(porteur)
        vu["temoin"] = temoin
        return None

    banc(app, tour)

    assert vu["lu_par_le_porteur"] is vu["temoin"], (
        "le porteur de la suppression n'emploie pas l'arbre COURANT de "
        "l'ecran : toute filiation qu'il lit est cherchee dans un arbre "
        "perime, et `lot_ancetre` rend None sur toute cible fine.")


def _arbre_lu_par(porteur):
    """L'arbre que `porteur.supprimer` passerait a `cabler_la_suppression`.

    Mesure par INTERCEPTION plutot que par lecture d'attribut : c'est
    precisement la lecon du finding `C3-1`, ou l'attribut disait une chose et
    l'emploi une autre. On remplace le cableur le temps d'une frappe et on
    releve son deuxieme argument positionnel.
    """
    import mixed_media_utility.tui.projet_suppression as _ps

    releve: dict[str, object] = {}
    vrai = _ps.cabler_la_suppression

    def espion(ecran, arbre, projet, **kw):
        releve["arbre"] = arbre
        return lambda noeud: True

    _ps.cabler_la_suppression = espion
    try:
        porteur.supprimer(None)
    finally:
        _ps.cabler_la_suppression = vrai
    return releve.get("arbre")


def test_le_porteur_garde_une_SECONDE_copie_du_DOSSIER_et_elle_suit_l_ecran(
        tmp_path, banc):
    """La FAMILLE de `C3-1`, un champ plus loin -- pose le 2026-09-07.

    Le correctif a ferme l'ARBRE : le porteur le lit de l'ecran a chaque
    frappe. Il n'a pas ferme le **dossier de projet**, qui est le meme fait
    detenu deux fois -- `_CablageDeLaSuppression.projet` d'un cote,
    `EcranInventaireDuProjet.dossier` de l'autre, tous deux poses depuis le
    seul `dossier_projet` d'`ouvrir_l_inventaire_du_projet`.

    **Ils ne peuvent pas diverger aujourd'hui, et c'est justement pourquoi ce
    banc existe** : aucun chemin ne reaffecte l'un des deux, l'inventaire etant
    remonte a neuf a chaque entree dans la gestion des medias
    (`atelier_extraction_ecriture` relit `self.palier_projet.dossier` au site
    d'appel). Rien ne le MESURAIT pour autant, et c'est exactement l'etat dans
    lequel l'arbre etait la veille : deux detenteurs d'un meme fait, dont l'un
    devient perime le jour ou quelqu'un reaffecte l'autre.

    Le porteur ecrit avec sa copie -- `ouvrir_la_suppression(projet=...)` --
    pendant que `reprendre` relit le disque avec celle de l'ecran. Une
    divergence ferait donc supprimer dans un projet et relire l'autre.
    """
    chemin = _projet(tmp_path)
    socle = PalierTemoin("Projet", "q quitter")
    app = CoqueTui(paliers=[socle], contexte=Contexte(projet="projet_demo"))
    vu: dict[str, object] = {}

    async def tour(pilote):
        pi.ouvrir_l_inventaire_du_projet(socle, chemin)
        await pilote.pause()
        inventaire = pilote.app.screen
        porteur = inventaire._supprimer.__self__
        vu["porteur"] = porteur.projet
        vu["ecran"] = inventaire.dossier
        return None

    banc(app, tour)

    assert vu["porteur"] == vu["ecran"], (
        "le porteur de la suppression et l'ecran ne designent plus le meme "
        "projet : l'un supprimerait la ou l'autre relit.")
